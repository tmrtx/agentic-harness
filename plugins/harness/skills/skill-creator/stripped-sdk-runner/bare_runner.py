"""Bare rollouts — direct /v1/messages submissions with a clean scored
turn. Import `rollout()`, or run as a CLI (prints JSON).

WHY THIS EXISTS: `claude -p` is a perfectly good transport with one
disqualifying flaw for scored rollouts — it injects a
<system-reminder> block (userEmail, currentDate, "may or may not be
relevant" context) into the USER TURN, and the model treats it as
task-relevant signal. That contamination, not the transport, is the
reason this runner submits directly.

WHAT IT SENDS: the bare minimum a live probe proves necessary, and
nothing else. Everything else the CLI puts on the wire — betas,
X-Stainless-* headers, metadata identity, context_management, x-app,
per-family effort defaults — was probed unnecessary and is not sent
(the list is recorded above BILLING). A subscription rollout differs
from an API-key rollout in auth and billing, and in one behavioural
default: reasoning is ON unless the caller passes thinking=False (see
family_thinking). Nothing else is injected — with no effort= the
model gets no effort, exactly as on a plain API call.

The survivors, each carrying its probe evidence at its definition:
the billing line leading the system prompt (the one thing that is
genuinely gated — see BILLING), Authorization, anthropic-version, and
three kept by preference rather than necessity (Content-Type,
User-Agent, X-Claude-Code-Session-Id). max_tokens is supplied when
omitted because the API requires the field.

Probes date to 2026-08-28 and MUST be re-run against sonnet-5 or
opus-5. haiku-4-5 does not enforce the billing gate, so a matrix run
against haiku alone concludes the line is optional and ships a runner
that 429s on every real model. integration_test.py is that matrix.

Options, all OFF by default:
- cache=True: ephemeral 1h cache_control on the caller's system
  block (no beta header needed).
- output_format={json schema}: structured outputs via output_config
  {"format": ...} (no beta header needed); the reply text is the
  conforming JSON.
- tools=[...] / tool_choice={...}: on the wire verbatim, adjacent;
  tool calls come back parsed in the result's tool_calls.
- messages=[...] / session_id=...: a full transcript in place of the
  single user turn, for multi-round tool loops under one session id.
  Round bodies build with build_body(); stream_round(body, halt=...)
  sends one live — halt sees each content_block_start and a truthy
  return hangs up on the spot, which is how a wrong channel choice
  (e.g. a native thinking block) is cut off for 2-5 tokens.

Auth: ANTHROPIC_STRIPPED_SDK_RUNNER when set (a token of the runner's
own), otherwise the subscription OAuth token from
~/.claude/.credentials.json, re-read per call so a concurrent claude
session's refresh is picked up. The token is the only credential the
runner needs. There is no ANTHROPIC_API_KEY path.

Calls go to ANTHROPIC_BASE_URL when set, api.anthropic.com otherwise
— point it at wire_capture.py to record the wire when debugging.
Quota exhaustion arrives as HTTP 429/5xx, never as scoreable text; it
becomes a bounded pause-and-retry, and the attempt count is returned.

CLI:
    python3 bare_runner.py --system-prompt-file sys.txt "user text"
    echo "user text" | python3 bare_runner.py --system-prompt-file sys.txt
Prints the rollout result dict as JSON; exits 0 iff a reply arrived.
"""

import http.client
import json
import os
import sys
import time
import urllib.parse
import uuid

DEFAULT_MODEL = os.environ.get("BARE_RUNNER_MODEL", "claude-opus-5")
# rollout() sends no effort unless the caller passes one. think.py and
# dryrun.py pass this constant explicitly; it is their default, not
# the runner's.
DEFAULT_EFFORT = os.environ.get("BARE_RUNNER_EFFORT", "xhigh")
MAX_TOKENS_ENV = os.environ.get("BARE_RUNNER_MAX_TOKENS")
TOKEN_ENV = "ANTHROPIC_STRIPPED_SDK_RUNNER"
CREDENTIALS = os.path.expanduser("~/.claude/.credentials.json")

def _quota_pause(status, attempts):
    """The one home for transport-status policy: quota statuses pause
    (bounded, env-tunable, read at call time) and return True so the
    caller retries; 401 is fatal with the refresh hint; anything else
    is the caller's result."""
    if status in (429, 503, 529) and attempts <= int(
        os.environ.get("BARE_RUNNER_QUOTA_MAX_WAITS", "12")
    ):
        time.sleep(int(os.environ.get("BARE_RUNNER_QUOTA_WAIT_S", "300")))
        return True
    if status == 401:
        raise SystemExit(
            "HTTP 401 from the API — OAuth token rejected; "
            "run any claude command to refresh it, then retry"
        )
    return False

# ---- The wire, and why each survivor is on it.
#
# Probed live against /v1/messages on 2026-08-28. The rule: an element
# is here only if removing it breaks a live call, or is recorded below
# as a deliberate exception. Everything the CLI sends that is NOT here
# was probed unnecessary and deleted — all ten betas (oauth-2025-04-20
# included), the seven X-Stainless-* headers, metadata.user_id
# identity, context_management, x-app, Connection, Accept, and
# anthropic-dangerous-direct-browser-access. Structured outputs,
# cache_control, tools and forced tool_choice all work with no beta.
#
# ABLATE ONLY AGAINST sonnet-5 / opus-5. haiku-4-5 does NOT enforce
# the billing gate below (200 without it, 3/3), so a matrix run against
# haiku alone "proves" the line is optional and ships a runner that
# 429s on every real model. That mistake has been made twice.

# REQUIRED, and the subtlest thing here. The API reads the LEADING
# system text as the subscription billing claim:
#   present and first          -> 200        (sonnet-5, opus-5)
#   absent                     -> 429 rate_limit_error, 3/3
#   present but NOT first      -> 429        (sonnet-5 and opus-5)
#   first block "hello"        -> 429        (the text itself is read)
#   sent as an HTTP header     -> 429        (must be in the body)
# It is a prefix check on the rendered system prompt, not a check on
# block structure: a plain string "<billing>\n\nyour prompt" is also
# 200, and "your prompt\n\n<billing>" is 429. Hence: first, always.
#
# The VALUES rot-proof themselves. Both keys must be present, but
# neither value is validated — cc_version=0.0.0 returns 200 on sonnet
# and opus, cc_entrypoint=api returns 200. Dropping either key gives
# 400 invalid_request_error (a parse failure, distinct from the 429),
# as does a bare "x-anthropic-billing-header:". So the 2.1.220.cf8
# below never needs re-freezing when the CLI moves; it only has to
# stay well-formed.
BILLING = (
    "x-anthropic-billing-header: cc_version=2.1.220.cf8; " "cc_entrypoint=sdk-cli;"
)
CACHE_1H = {"type": "ephemeral", "ttl": "1h"}
# NOT required (a bare curl UA is accepted, as is none at all). Kept by
# owner preference, and left at the CLI string deliberately rather than
# renamed — changing it would be a decision, not a removal.
USER_AGENT = "claude-cli/2.1.220 (external, sdk-cli)"


def _family(model):
    """The families differ for real, probed 2026-08-28: adaptive
    thinking and output_config.effort are 5-family only — haiku-4-5
    answers 400 "adaptive thinking is not supported on this model" and
    400 "This model does not support the effort parameter". Consulted
    by family_thinking() and the max_tokens default."""
    return "4.5" if "-4-5" in model else "5"


def family_thinking(model, max_tokens=None):
    """The per-family ENABLED-thinking shape, and build_body's default.

    Reasoning is ON by default — an owner decision, and the one
    behavioural default the runner keeps. Scored rollouts want it, and
    think.py's forced-tool scheme outright depends on it: a billed 0
    means the model chose the tool over an AVAILABLE private pass,
    which is the entire claim. dryrun.py inherits that.

    display must be set EXPLICITLY: the CLI omits it and the server
    then suppresses the reasoning summary (billed, never streamed);
    "summarized" is the one value that streams it. It is also what
    makes think.py's 2-5-token abort rail work at all — an unstreamed
    thinking block never reaches halt_native.

    Forced tool_choice rejects type "enabled" (400 "Thinking may not be
    enabled when tool_choice forces tool use", both families) but
    accepts "adaptive". That is why the scheme is 5-family and why 4.5
    needs thinking=False, exactly as think.py already documents."""
    if _family(model) == "4.5":
        mt = max_tokens or (int(MAX_TOKENS_ENV) if MAX_TOKENS_ENV else 32000)
        return {"budget_tokens": mt - 1, "type": "enabled",
                "display": "summarized"}
    return {"type": "adaptive", "display": "summarized"}


def base_url():
    return (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip(
        "/"
    )


def oauth_token():
    # A dedicated token in the environment wins over the CLI's credentials,
    # so rollouts can run on their own auth instead of riding on (and racing
    # the refresh of) the interactive session's. Unset -> the CLI's files.
    #
    # Quota follows the TOKEN'S ACCOUNT. Whether that isolates a rollout
    # from the interactive session depends entirely on the two tokens
    # belonging to different subscriptions; the override does not create a
    # separate bucket by itself. Utilization figures from two tokens are
    # therefore not comparable until you know whose they are —
    # anthropic-organization-id on any response says which account a token
    # actually spends against. An override token may also carry a narrower
    # scope set (one seen here lacks user:profile), which affects account
    # endpoints but not inference.
    override = os.environ.get(TOKEN_ENV, "").strip()
    if override:
        return override
    try:
        oauth = json.load(open(CREDENTIALS))["claudeAiOauth"]
        token = oauth["accessToken"]
    except (OSError, ValueError, KeyError):
        raise SystemExit(
            "no subscription OAuth token at %s — log in with "
            "`claude` first" % CREDENTIALS
        )
    if oauth.get("expiresAt", 0) / 1000.0 < time.time():
        raise SystemExit(
            "subscription OAuth token expired — run any claude "
            "command to refresh it, then retry"
        )
    return token


def assert_env():
    # A key in the environment means someone is expecting API billing, but this
    # runner only ever sends the OAuth bearer — fail loud rather than bill elsewhere.
    assert not os.environ.get("ANTHROPIC_API_KEY"), (
        "ANTHROPIC_API_KEY is set — bare_runner has no API-key path and would "
        "charge the subscription instead; unset it before running rollouts"
    )
    # The token is the only credential the runner needs.
    oauth_token()


def build_body(
    system_text,
    user_text,
    model,
    effort=None,
    max_tokens=None,
    thinking=None,
    cache=False,
    output_format=None,
    tools=None,
    tool_choice=None,
    messages=None,
    session_id=None,
):
    """(body, session_id): the caller's request, plus the billing line
    and nothing else. Every optional key is absent unless the caller
    asked for it, so a rollout behaves like the same call made with an
    API key — that parity is the invariant this runner keeps.

    max_tokens is the one exception: the API requires the field, so it
    is supplied when omitted, at the per-family value the CLI uses.

    thinking: None gets family_thinking(model) — reasoning is ON by
    default, an owner decision, because scored rollouts want it and
    every caller here depends on it. False sends the explicit disabled
    shape; a dict goes through verbatim. This is the one behavioural
    default the runner keeps; effort and the rest inject nothing.

    `messages` replaces the single user turn with a full transcript
    (user_text is then unused); pass the returned session_id back in so
    a conversation's rounds share one id."""
    fam = _family(model)
    if max_tokens is None:
        max_tokens = (
            int(MAX_TOKENS_ENV)
            if MAX_TOKENS_ENV
            else (32000 if fam == "4.5" else 64000)
        )
    if thinking is None:
        thinking = family_thinking(model, max_tokens)
    elif thinking is False:
        thinking = {"type": "disabled"}
    output_config = {"effort": effort} if effort else None
    if output_format:
        output_config = dict(output_config or {})
        output_config["format"] = output_format
    sid = session_id or str(uuid.uuid4())
    # The billing line leads, always — see BILLING. Position is the
    # contract; a caller block ahead of it costs a 429.
    sys_blocks = [
        {"type": "text", "text": BILLING},
        {"type": "text", "text": system_text},
    ]
    if cache:
        sys_blocks[-1]["cache_control"] = dict(CACHE_1H)
    body = {
        "model": model,
        "messages": messages
        or [{"role": "user", "content": [{"type": "text", "text": user_text}]}],
        "system": sys_blocks,
        "max_tokens": max_tokens,
    }
    # Absent, not empty: the CLI sends "tools": [] on every request and
    # an empty array is still a non-default the caller never asked for.
    if tools:
        body["tools"] = list(tools)
    if tool_choice:
        body["tool_choice"] = tool_choice
    if thinking:
        body["thinking"] = thinking
    if output_config:
        body["output_config"] = output_config
    # Not dressing: the reply reader is an SSE folder, so the transport
    # is streaming by construction. It does not change what the model
    # produces.
    body["stream"] = True
    return body, sid


def _headers(sid, body_len):
    """Everything the runner puts on the wire, and the whole of it.

    REQUIRED (probed 2026-08-28 on sonnet-5, which enforces the gate):
      Authorization      — 401 without it ("OAuth access token is
                           invalid" on a bad one, so this is the
                           subscription path, not an API-key path)
      anthropic-version  — 400 "anthropic-version: header is required"
    NOT required, kept deliberately:
      Content-Type       — 200 without it; sent because an API-key SDK
                           call sends it and parity is the invariant
      User-Agent         — see USER_AGENT
      X-Claude-Code-Session-Id — owner decision; harmless, and it gives
                           the returned session id a real referent
    Host and Accept-Encoding: identity are added by http.client. The
    identity encoding is what lets stream_round read line-at-a-time;
    stdlib cannot decode gzip off a live stream."""
    return [
        ("Authorization", "Bearer " + oauth_token()),
        ("Content-Type", "application/json"),
        ("User-Agent", USER_AGENT),
        ("X-Claude-Code-Session-Id", sid),
        ("anthropic-version", "2023-06-01"),
        ("Content-Length", str(body_len)),
    ]


UNIFIED_PREFIX = "anthropic-ratelimit-unified-"
_WARNED_UNBILLED = [False]   # once per process; tests reset it


def _warn_unbilled(status, headers):
    """Warn when a 200 came back WITHOUT the subscription's unified
    rate-limit headers — i.e. when the call was not billed to the
    subscription.

    Why this can be trusted, probed 2026-08-28 with an API key as the
    negative control: the two rate-limit families partition cleanly.
    Subscription (OAuth) 200s carry twelve anthropic-ratelimit-unified-*
    headers and zero per-tier ones; API-key 200s carry twelve per-tier
    headers (requests / tokens / input-tokens / output-tokens limits)
    and zero unified ones, 4/4. So absence on a 200 is diagnostic
    rather than merely unusual — which a one-armed test could not have
    shown, since every subscription probe trivially agrees with itself.

    A WARNING, never an exception, and never on a non-200: these header
    names belong to Anthropic, and a rename must degrade to noise
    rather than break every rollout. Error responses legitimately carry
    no rate-limit family at all (probed on 400/401/429).

    The runner cannot actually reach this state today — it sends only
    the OAuth bearer, and an API key presented that way is refused 401
    — so this is a tripwire against a future auth path, not a live
    hazard."""
    if status != 200 or _WARNED_UNBILLED[0]:
        return
    got = sorted(k.lower() for k, _ in headers
                 if k.lower().startswith("anthropic-ratelimit-"))
    if any(k.startswith(UNIFIED_PREFIX) for k in got):
        return
    _WARNED_UNBILLED[0] = True
    sys.stderr.write(
        "bare_runner: WARNING — this 200 was not billed to the "
        "subscription.\n"
        "  expected: %s* headers\n"
        "  got:      %s\n"
        "  The reply is unaffected; the billing account is not the one "
        "this runner is for.\n"
        % (UNIFIED_PREFIX, ", ".join(got) or "no anthropic-ratelimit-* "
           "headers at all")
    )


def _post(url, body_bytes, sid, timeout):
    """(connection, response) for one POSTed body — caller closes."""
    u = urllib.parse.urlsplit(url)
    cls = (
        http.client.HTTPSConnection
        if u.scheme == "https"
        else http.client.HTTPConnection
    )
    c = cls(u.netloc, timeout=timeout)
    c.putrequest("POST", (u.path.rstrip("/")) + "/v1/messages")
    for k, v in _headers(sid, len(body_bytes)):
        c.putheader(k, v)
    c.endheaders(body_bytes)
    return c, c.getresponse()


def _send(url, body_bytes, sid, timeout):
    c, r = _post(url, body_bytes, sid, timeout)
    try:
        _warn_unbilled(r.status, r.getheaders())
        return r.status, r.read()
    finally:
        c.close()


def _fold(lines, halt=None):
    """Fold an SSE line stream into (blocks, model, stop, usage, error).
    blocks are API-shaped content blocks — text / thinking / tool_use,
    tool inputs parsed from their accumulated partial json, ready to
    echo in an assistant turn (thinking blocks carry summary text only,
    no signature: display, never echo). halt(content_block) is consulted
    at each content_block_start; truthy stops reading right there with
    stop "halted" — on a live source that is the cheap hang-up."""
    blocks, parts, model, stop, usage, err = [], [], None, None, {}, None
    for line in lines:
        if not line.startswith(b"data: "):
            continue
        try:
            obj = json.loads(line[6:])
        except ValueError:
            continue
        t = obj.get("type")
        if t == "message_start":
            mm = obj.get("message") or {}
            model = mm.get("model")
            usage.update(mm.get("usage") or {})
        elif t == "content_block_start":
            cb = dict(obj.get("content_block") or {})
            # signature (thinking) and caller (tool_use) are response
            # decoration, not request vocabulary — echoing them rides
            # on server tolerance, so they never reach the blocks.
            cb.pop("signature", None)
            cb.pop("caller", None)
            if cb.get("type") == "tool_use":
                cb["input"] = {}
            blocks.append(cb)
            parts.append("")
            if halt and halt(cb):
                stop = "halted"
                break
        elif t == "content_block_delta" and blocks:
            d = obj.get("delta") or {}
            dt = d.get("type")
            if dt == "text_delta":
                blocks[-1]["text"] = blocks[-1].get("text", "") + (
                    d.get("text") or ""
                )
            elif dt == "thinking_delta":
                blocks[-1]["thinking"] = blocks[-1].get("thinking", "") + (
                    d.get("thinking") or ""
                )
            elif dt == "input_json_delta":
                parts[-1] += d.get("partial_json") or ""
        elif t == "message_delta":
            usage.update(obj.get("usage") or {})
            stop = (obj.get("delta") or {}).get("stop_reason") or stop
        elif t == "error":
            err = obj
    for cb, part in zip(blocks, parts):
        if cb.get("type") == "tool_use":
            try:
                cb["input"] = json.loads(part) if part else {}
            except ValueError:
                cb["input"] = {"partial_json": part}
    return blocks, model, stop, usage, err


def _digest(blocks):
    """(text, thinking, tool_calls) — the joined conveniences."""
    text = "".join(b.get("text") or "" for b in blocks if b.get("type") == "text")
    think = "".join(
        b.get("thinking") or "" for b in blocks if b.get("type") == "thinking"
    )
    calls = [b for b in blocks if b.get("type") == "tool_use"]
    return text or None, think or None, calls


def _parse(status, data):
    """(blocks, model, stop, usage, error) from a buffered response."""
    if status == 200:
        return _fold(iter(data.splitlines()), None)
    try:
        obj = json.loads(data)
    except ValueError:
        obj = {"unparseable": data[:200].decode("utf-8", "replace")}
    return [], None, None, {}, obj


def _result(status, attempts, sid, folded):
    blocks, model, stop, usage, err = folded
    text, think, calls = _digest(blocks)
    return {
        "text": text,
        "thinking": think,
        "tool_calls": calls,
        "model": model,
        "stop_reason": stop,
        "usage": usage,
        "status": status,
        "attempts": attempts,
        "session_id": sid,
        "raw": err,
    }


def stream_round(body, sid=None, halt=None, timeout=600):
    """One live exchange for an already-built body (from build_body):
    the reply streams line-at-a-time, and halt(content_block) is
    consulted at each content_block_start — truthy hangs up on the spot
    (stop "halted"). A first-block hang-up costs 2-5 tokens: the probe
    / abort lever. Returns the same result dict as rollout(). Quota
    pauses and retries the same way.

    `sid` is the session id sent in the X-Claude-Code-Session-Id
    header. Pass build_body's second return value to keep a
    conversation's rounds under one id; omitting it mints a fresh
    one."""
    sid = sid or str(uuid.uuid4())
    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    url = base_url()
    attempts = 0
    while True:
        attempts += 1
        c, r = _post(url, body_bytes, sid, timeout)
        try:
            _warn_unbilled(r.status, r.getheaders())
            if _quota_pause(r.status, attempts):
                continue
            if r.status != 200:
                folded = _parse(r.status, r.read())
            else:
                folded = _fold(iter(r.readline, b""), halt)
            return _result(r.status, attempts, sid, folded)
        finally:
            c.close()


def rollout(
    system_file,
    user_text,
    model=DEFAULT_MODEL,
    effort=None,
    max_tokens=None,
    thinking=None,
    cache=False,
    output_format=None,
    tools=None,
    tool_choice=None,
    timeout=600,
):
    """Returns {text, thinking, tool_calls, model, stop_reason, usage,
    status, attempts, session_id, raw}; text is None on hard failure.
    thinking is the streamed reasoning summary (None when the model did
    not think or thinking is disabled). tool_calls are API-shaped
    tool_use blocks with parsed input, ready to echo in an assistant
    turn. With output_format, text is the schema-conforming JSON
    string. Reasoning is on by default; pass thinking=False to disable
    it. Buffered; for a live stream with an early hang-up lever, build
    the body and use stream_round."""
    if not os.path.exists(system_file):
        raise SystemExit("system prompt file missing: %s" % system_file)
    system_text = open(system_file, encoding="utf-8").read()
    body, sid = build_body(
        system_text,
        user_text,
        model,
        effort,
        max_tokens,
        thinking,
        cache,
        output_format,
        tools=tools,
        tool_choice=tool_choice,
    )
    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    url = base_url()
    attempts = 0
    while True:
        attempts += 1
        status, data = _send(url, body_bytes, sid, timeout)
        if not _quota_pause(status, attempts):
            break
    return _result(status, attempts, sid, _parse(status, data))


def _replied(r):
    """A reply arrived: text or tool calls on a 200. The one home for
    the concept — the CLI's exit test and the retry helper share it."""
    return r["status"] == 200 and bool(r["text"] or r["tool_calls"])


def rollout_with_retry(system_file, user_text, accept, **kw):
    """`accept(text) -> bool` decides whether a TEXT reply satisfies
    your contract; a tool-only reply is a reply with no text to judge
    and returns as-is (write tool contracts against rollout directly).
    One retry on a rejected or missing reply, then the best available
    is returned (caller decides how to score/surface it — a broken
    contract is a process signal, not noise). The extra count is wire
    attempts beyond the first, for capture accounting when a proxy
    records."""

    def satisfied(r):
        return _replied(r) and (accept(r["text"]) if r["text"] else True)

    r1 = rollout(system_file, user_text, **kw)
    extra = r1["attempts"] - 1
    if satisfied(r1):
        return r1, extra
    r2 = rollout(system_file, user_text, **kw)
    extra += r2["attempts"]
    return (r2 if satisfied(r2) or _replied(r2) else r1), extra


def _cli():
    import argparse

    ap = argparse.ArgumentParser(
        description="One bare rollout; prints the result dict as JSON."
    )
    ap.add_argument("--system-prompt-file", required=True)
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument(
        "--effort",
        default=None,
        help="output_config.effort; unset sends no effort at all, as a "
        "plain API call does (5-family only — 4.5 answers 400)",
    )
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument(
        "--cache",
        action="store_true",
        help="prompt caching, the CLI's 1h shape (default off)",
    )
    ap.add_argument(
        "--output-format",
        metavar="JSON",
        default=None,
        help="structured output format, e.g. "
        '\'{"type":"json_schema","schema":{...}}\'',
    )
    ap.add_argument(
        "--tools",
        metavar="JSON",
        default=None,
        help='tool definitions, e.g. \'[{"name":...,"input_schema":...}]\'',
    )
    ap.add_argument(
        "--tool-choice",
        metavar="JSON",
        default=None,
        help='e.g. \'{"type":"tool","name":"think"}\'',
    )
    ap.add_argument(
        "--no-thinking",
        action="store_true",
        help="send the disabled-thinking shape (reasoning is on by "
        "default; the 4.5 family needs this to force tool_choice)",
    )
    ap.add_argument("--timeout", type=int, default=600)
    ap.add_argument(
        "user_text",
        nargs="?",
        default=None,
        help="user turn; read from stdin when omitted",
    )
    a = ap.parse_args()
    user_text = a.user_text if a.user_text is not None else sys.stdin.read()
    fmt = json.loads(a.output_format) if a.output_format else None
    r = rollout(
        a.system_prompt_file,
        user_text,
        model=a.model,
        effort=a.effort,
        max_tokens=a.max_tokens,
        thinking=False if a.no_thinking else None,
        cache=a.cache,
        output_format=fmt,
        tools=json.loads(a.tools) if a.tools else None,
        tool_choice=json.loads(a.tool_choice) if a.tool_choice else None,
        timeout=a.timeout,
    )
    json.dump(r, sys.stdout, indent=1)
    sys.stdout.write("\n")
    sys.exit(0 if _replied(r) else 1)


if __name__ == "__main__":
    _cli()
