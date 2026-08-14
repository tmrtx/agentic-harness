"""Bare rollouts — normal Claude Code-shaped submissions with a clean
scored turn. Import `rollout()`, or run as a CLI (prints JSON).

WHY THIS EXISTS: `claude -p` is a perfectly good transport with one
disqualifying flaw for scored rollouts — it injects a
<system-reminder> block (userEmail, currentDate, "may or may not be
relevant" context) into the USER TURN, and the model treats it as
task-relevant signal. That contamination, not the transport, is the
reason this runner submits directly. Everything else about the CLI's
wire is kept — billing-header block, headers in CLI order and casing
— because those identify how subscription traffic is billed,
categorized, and served. Two deliberate exceptions: the CLI's SDK
identity line ("You are a Claude agent…") is absent, because it is
steering text and nothing but the caller's words may steer a scored
rollout; and live streaming (stream_round) sends Accept-Encoding
identity, because line-at-a-time reads cannot pass through stdlib
gzip. The system carries billing + the caller's text, the user turn
the caller's text, and NOTHING else.

The WIRE profiles below are frozen from captured `claude -p` requests
(CLI 2.1.220), one per model family — the families genuinely differ
on the wire: the 4.5 family ("-4-5" in the id) sends max_tokens 32000
and thinking {budget_tokens: 31999, enabled} at every effort; the 5
family (opus-5, fable-5, sonnet-5) sends max_tokens 64000, thinking
{adaptive}, effort inside output_config, and a longer beta list. The
beta list also tracks the features a request uses, exactly like the
CLI's. integration_test.py guards all of it against a freshly minted
-p capture; when the CLI updates and the test reports drift,
re-freeze from the values it prints.

Options, all OFF by default:
- cache=True: the CLI's prompt-caching shape (ephemeral 1h
  cache_control on the caller block, extended-cache-ttl beta).
- output_format={json schema}: structured outputs (output_config
  {"format": ...} plus the structured-outputs beta); the reply text
  is the conforming JSON.
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
session's refresh is picked up. Identity (device_id, account_uuid)
comes from ~/.claude.json — the same sources the CLI reads. There is
no ANTHROPIC_API_KEY path.

Calls go to ANTHROPIC_BASE_URL when set, api.anthropic.com otherwise
— point it at wire_capture.py to record the wire when debugging.
Quota exhaustion arrives as HTTP 429/5xx, never as scoreable text; it
becomes a bounded pause-and-retry, and the attempt count is returned.

CLI:
    python3 bare_runner.py --system-prompt-file sys.txt "user text"
    echo "user text" | python3 bare_runner.py --system-prompt-file sys.txt
Prints the rollout result dict as JSON; exits 0 iff a reply arrived.
"""

import gzip
import http.client
import json
import os
import sys
import time
import urllib.parse
import uuid

DEFAULT_MODEL = os.environ.get("BARE_RUNNER_MODEL", "claude-opus-5")
DEFAULT_EFFORT = os.environ.get("BARE_RUNNER_EFFORT", "xhigh")
MAX_TOKENS_ENV = os.environ.get("BARE_RUNNER_MAX_TOKENS")
TOKEN_ENV = "ANTHROPIC_STRIPPED_SDK_RUNNER"
CREDENTIALS = os.path.expanduser("~/.claude/.credentials.json")
CLAUDE_JSON = os.path.expanduser("~/.claude.json")

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

# ---- WIRE profiles: frozen from captured claude -p requests (2.1.220).
BILLING = (
    "x-anthropic-billing-header: cc_version=2.1.220.cf8; " "cc_entrypoint=sdk-cli;"
)
CACHE_1H = {"type": "ephemeral", "ttl": "1h"}
CONTEXT_MANAGEMENT = {"edits": [{"type": "clear_thinking_20251015", "keep": "all"}]}
USER_AGENT = "claude-cli/2.1.220 (external, sdk-cli)"
BETAS_45 = [
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "thinking-token-count-2026-05-13",
    "context-management-2025-06-27",
    "prompt-caching-scope-2026-01-05",
    "claude-code-20250219",
    "advisor-tool-2026-03-01",
]
BETAS_5 = [
    "claude-code-20250219",
    "oauth-2025-04-20",
    "interleaved-thinking-2025-05-14",
    "thinking-token-count-2026-05-13",
    "context-management-2025-06-27",
    "prompt-caching-scope-2026-01-05",
    "mid-conversation-system-2026-04-07",
    "advisor-tool-2026-03-01",
    "effort-2025-11-24",
    "afk-mode-2026-01-31",
]
CACHE_BETA = "extended-cache-ttl-2025-04-11"
STRUCTURED_BETA = "structured-outputs-2025-12-15"
STAINLESS = [
    ("X-Stainless-Arch", "x64"),
    ("X-Stainless-Lang", "js"),
    ("X-Stainless-OS", "Linux"),
    ("X-Stainless-Package-Version", "0.94.0"),
]
STAINLESS_RT = [
    ("X-Stainless-Runtime", "node"),
    ("X-Stainless-Runtime-Version", "v26.3.0"),
    ("X-Stainless-Timeout", "600"),
]


def _family(model):
    return "4.5" if "-4-5" in model else "5"


def _betas(model, cache, structured):
    base = list(BETAS_45 if _family(model) == "4.5" else BETAS_5)
    if cache:
        base.append(CACHE_BETA)
    if structured:
        base.append(STRUCTURED_BETA)
    return ",".join(base)


def base_url():
    return (os.environ.get("ANTHROPIC_BASE_URL") or "https://api.anthropic.com").rstrip(
        "/"
    )


def oauth_token():
    # A dedicated token in the environment wins over the CLI's credentials,
    # so rollouts can run on their own auth instead of riding on (and racing
    # the refresh of) the interactive session's. Unset -> the CLI's files.
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


def account_identity():
    """(device_id, account_uuid) from ~/.claude.json — the CLI's own
    sources for metadata.user_id."""
    try:
        cj = json.load(open(CLAUDE_JSON))
        return cj["userID"], cj["oauthAccount"]["accountUuid"]
    except (OSError, ValueError, KeyError):
        raise SystemExit(
            "no account identity in %s — run `claude` once on "
            "this machine first" % CLAUDE_JSON
        )


def assert_env():
    # A key in the environment means someone is expecting API billing, but this
    # runner only ever sends the OAuth bearer — fail loud rather than bill elsewhere.
    assert not os.environ.get("ANTHROPIC_API_KEY"), (
        "ANTHROPIC_API_KEY is set — bare_runner has no API-key path and would "
        "charge the subscription instead; unset it before running rollouts"
    )
    oauth_token()
    account_identity()


def build_body(
    system_text,
    user_text,
    model,
    effort,
    max_tokens=None,
    thinking=None,
    cache=False,
    output_format=None,
    tools=None,
    tool_choice=None,
    messages=None,
    session_id=None,
):
    """(body, session_id): the CLI's request shape for the model's
    family — same key order, same floor blocks, same metadata sources —
    with the user turn carrying ONLY the caller's text. `messages`
    replaces the single user turn with a full transcript (user_text is
    then unused); pass the returned session_id back in so a
    conversation's rounds share one session."""
    fam = _family(model)
    if max_tokens is None:
        max_tokens = (
            int(MAX_TOKENS_ENV)
            if MAX_TOKENS_ENV
            else (32000 if fam == "4.5" else 64000)
        )
    if thinking is None:
        # display must be set EXPLICITLY: the CLI omits it and the server
        # then suppresses the reasoning summary (billed, never streamed).
        # "summarized" is the one value that streams it; "omitted" streams
        # nothing; every other value is HTTP 400. Verified live by the
        # cc-sniff rewrite this knowledge is inherited from.
        thinking = (
            {
                "budget_tokens": max_tokens - 1,
                "type": "enabled",
                "display": "summarized",
            }
            if fam == "4.5"
            else {"type": "adaptive", "display": "summarized"}
        )
    elif thinking is False:
        thinking = {"type": "disabled"}
    output_config = None
    if fam == "5":
        output_config = {"effort": effort}
    if output_format:
        output_config = dict(output_config or {})
        output_config["format"] = output_format
    device_id, account_uuid = account_identity()
    sid = session_id or str(uuid.uuid4())
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
        "tools": list(tools or []),
    }
    if tool_choice:
        body["tool_choice"] = tool_choice
    body.update(
        {
            "metadata": {
                "user_id": json.dumps(
                    {
                        "device_id": device_id,
                        "account_uuid": account_uuid,
                        "session_id": sid,
                    },
                    separators=(",", ":"),
                )
            },
            "max_tokens": max_tokens,
            "thinking": thinking,
        }
    )
    if thinking.get("type") != "disabled":
        # The CLI's disabled-thinking calls omit context_management (the
        # clear_thinking strategy 400s without thinking) — observed on the
        # -p title side call and confirmed live.
        body["context_management"] = json.loads(json.dumps(CONTEXT_MANAGEMENT))
    if output_config:
        body["output_config"] = output_config
    body["stream"] = True
    return body, sid


def _headers(betas, sid, attempt, body_len, netloc, accept_encoding=None):
    """The CLI's header sequence — names, order, casing — with only the
    per-call values fresh."""
    return (
        [
            ("Accept", "application/json"),
            ("Authorization", "Bearer " + oauth_token()),
            ("Content-Type", "application/json"),
            ("User-Agent", USER_AGENT),
            ("X-Claude-Code-Session-Id", sid),
        ]
        + STAINLESS
        + [("X-Stainless-Retry-Count", str(attempt - 1))]
        + STAINLESS_RT
        + [
            ("anthropic-beta", betas),
            ("anthropic-dangerous-direct-browser-access", "true"),
            ("anthropic-version", "2023-06-01"),
            ("x-app", "cli"),
            ("Connection", "keep-alive"),
            ("Host", netloc),
            ("Accept-Encoding", accept_encoding or "gzip, deflate, br, zstd"),
            ("Content-Length", str(body_len)),
        ]
    )


def _post(url, betas, body_bytes, sid, attempt, timeout, accept_encoding=None):
    """(connection, response) for one POSTed body — caller closes."""
    u = urllib.parse.urlsplit(url)
    cls = (
        http.client.HTTPSConnection
        if u.scheme == "https"
        else http.client.HTTPConnection
    )
    c = cls(u.netloc, timeout=timeout)
    c.putrequest(
        "POST",
        (u.path.rstrip("/")) + "/v1/messages",
        skip_host=True,
        skip_accept_encoding=True,
    )
    for k, v in _headers(
        betas, sid, attempt, len(body_bytes), u.netloc, accept_encoding
    ):
        c.putheader(k, v)
    c.endheaders(body_bytes)
    return c, c.getresponse()


def _send(url, betas, body_bytes, sid, attempt, timeout):
    c, r = _post(url, betas, body_bytes, sid, attempt, timeout)
    try:
        data = r.read()
        enc = (r.getheader("content-encoding") or "").lower()
        if enc == "gzip":
            data = gzip.decompress(data)
        elif enc:
            raise SystemExit(
                "response compressed as %r — stdlib cannot "
                "decode it; route through wire_capture.py "
                "(it forces identity upstream)" % enc
            )
        return r.status, data
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


def _betas_for(body):
    """The beta list a built body needs, derived from the body itself —
    the cache and structured-output betas track their features exactly,
    the way the CLI's list tracks its own."""
    cache = any("cache_control" in b for b in body.get("system") or [])
    structured = "format" in (body.get("output_config") or {})
    return _betas(body["model"], cache, structured)


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


def stream_round(body, halt=None, timeout=600):
    """One live exchange for an already-built body (from build_body):
    betas and session id derive from the body, the reply streams
    line-at-a-time, and halt(content_block) is consulted at each
    content_block_start — truthy hangs up on the spot (stop "halted").
    A first-block hang-up costs 2-5 tokens: the probe / abort lever.
    Returns the same result dict as rollout(). Quota pauses and
    retries the same way."""
    betas = _betas_for(body)
    sid = json.loads(body["metadata"]["user_id"])["session_id"]
    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    url = base_url()
    attempts = 0
    while True:
        attempts += 1
        c, r = _post(url, betas, body_bytes, sid, attempts, timeout, "identity")
        try:
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
    effort=DEFAULT_EFFORT,
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
    string. Buffered, CLI-exact wire; for a live stream with an early
    hang-up lever, build the body and use stream_round."""
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
    betas = _betas_for(body)
    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    url = base_url()
    attempts = 0
    while True:
        attempts += 1
        status, data = _send(url, betas, body_bytes, sid, attempts, timeout)
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
    ap.add_argument("--effort", default=DEFAULT_EFFORT)
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
        help="send the CLI's disabled-thinking shape (the 4.5 family "
        "rejects forced tool_choice with thinking enabled)",
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
