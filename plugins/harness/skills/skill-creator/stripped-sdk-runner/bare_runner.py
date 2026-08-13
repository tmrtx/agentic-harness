"""Bare rollouts — normal Claude Code-shaped submissions with a clean
scored turn. Import `rollout()`, or run as a CLI (prints JSON).

WHY THIS EXISTS: `claude -p` is a perfectly good transport with one
disqualifying flaw for scored rollouts — it injects a
<system-reminder> block (userEmail, currentDate, "may or may not be
relevant" context) into the USER TURN, and the model treats it as
task-relevant signal. That contamination, not the transport, is the
reason this runner submits directly. Everything else about the CLI's
wire is kept — billing-header block, SDK identity line, headers in
CLI order and casing — because those identify how subscription
traffic is billed, categorized, and served. The user turn carries the
caller's text and NOTHING else.

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

Options, both OFF by default:
- cache=True: the CLI's prompt-caching shape (ephemeral 1h
  cache_control on identity + caller blocks, extended-cache-ttl beta).
- output_format={json schema}: structured outputs (output_config
  {"format": ...} plus the structured-outputs beta); the reply text
  is the conforming JSON.

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

QUOTA_WAIT_S = int(os.environ.get("BARE_RUNNER_QUOTA_WAIT_S", "300"))
QUOTA_MAX_WAITS = int(os.environ.get("BARE_RUNNER_QUOTA_MAX_WAITS", "12"))

# ---- WIRE profiles: frozen from captured claude -p requests (2.1.220).
BILLING = (
    "x-anthropic-billing-header: cc_version=2.1.220.cf8; " "cc_entrypoint=sdk-cli;"
)
IDENTITY = "You are a Claude agent, built on Anthropic's Claude Agent SDK."
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
    system_text, user_text, model, effort, max_tokens, thinking, cache, output_format
):
    """(body, session_id): the CLI's request shape for the model's
    family — same key order, same floor blocks, same metadata sources —
    with the user turn carrying ONLY the caller's text."""
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
    sid = str(uuid.uuid4())
    sys_blocks = [
        {"type": "text", "text": BILLING},
        # {"type": "text", "text": IDENTITY},
        {"type": "text", "text": system_text},
    ]
    if cache:
        sys_blocks[1]["cache_control"] = dict(CACHE_1H)
        sys_blocks[2]["cache_control"] = dict(CACHE_1H)
    body = {
        "model": model,
        "messages": [
            {"role": "user", "content": [{"type": "text", "text": user_text}]}
        ],
        "system": sys_blocks,
        "tools": [],
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
    if thinking.get("type") != "disabled":
        # The CLI's disabled-thinking calls omit context_management (the
        # clear_thinking strategy 400s without thinking) — observed on the
        # -p title side call and confirmed live.
        body["context_management"] = json.loads(json.dumps(CONTEXT_MANAGEMENT))
    if output_config:
        body["output_config"] = output_config
    body["stream"] = True
    return body, sid


def _headers(betas, sid, attempt, body_len, netloc):
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
            ("Accept-Encoding", "gzip, deflate, br, zstd"),
            ("Content-Length", str(body_len)),
        ]
    )


def _send(url, betas, body_bytes, sid, attempt, timeout):
    u = urllib.parse.urlsplit(url)
    cls = (
        http.client.HTTPSConnection
        if u.scheme == "https"
        else http.client.HTTPConnection
    )
    c = cls(u.netloc, timeout=timeout)
    try:
        c.putrequest(
            "POST",
            (u.path.rstrip("/")) + "/v1/messages",
            skip_host=True,
            skip_accept_encoding=True,
        )
        for k, v in _headers(betas, sid, attempt, len(body_bytes), u.netloc):
            c.putheader(k, v)
        c.endheaders(body_bytes)
        r = c.getresponse()
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


def _parse(status, data, streamed):
    """(text, thinking, model, stop_reason, usage, error). Buffered SSE
    parse: no live consumer here, and buffering sidesteps encoding
    concerns. thinking is the reasoning-summary text the wire streamed."""
    if status != 200 or not streamed:
        try:
            obj = json.loads(data)
        except ValueError:
            return (
                None,
                None,
                None,
                None,
                None,
                {"unparseable": data[:200].decode("utf-8", "replace")},
            )
        if obj.get("type") == "message":
            text = "".join(
                b.get("text", "")
                for b in obj.get("content", [])
                if isinstance(b, dict) and b.get("type") == "text"
            )
            think = "".join(
                b.get("thinking", "")
                for b in obj.get("content", [])
                if isinstance(b, dict) and b.get("type") == "thinking"
            )
            return (
                text or None,
                think or None,
                obj.get("model"),
                obj.get("stop_reason"),
                obj.get("usage"),
                None,
            )
        return None, None, None, None, None, obj
    text, think, model, stop, usage, err = "", "", None, None, {}, None
    for line in data.splitlines():
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
        elif t == "content_block_delta":
            d = obj.get("delta") or {}
            if d.get("type") == "text_delta":
                text += d.get("text") or ""
            elif d.get("type") == "thinking_delta":
                think += d.get("thinking") or ""
        elif t == "message_delta":
            usage.update(obj.get("usage") or {})
            stop = (obj.get("delta") or {}).get("stop_reason") or stop
        elif t == "error":
            err = obj
    return (text or None), (think or None), model, stop, usage, err


def rollout(
    system_file,
    user_text,
    model=DEFAULT_MODEL,
    effort=DEFAULT_EFFORT,
    max_tokens=None,
    thinking=None,
    cache=False,
    output_format=None,
    timeout=600,
):
    """Returns {text, thinking, model, stop_reason, usage, status,
    attempts, session_id, raw}; text is None on hard failure. thinking
    is the streamed reasoning summary (None when the model did not
    think or thinking is disabled). With output_format, text is the
    schema-conforming JSON string."""
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
    )
    betas = _betas(model, cache, bool(output_format))
    body_bytes = json.dumps(body, separators=(",", ":"), ensure_ascii=False).encode()
    url = base_url()
    attempts = 0
    while True:
        attempts += 1
        status, data = _send(url, betas, body_bytes, sid, attempts, timeout)
        if status in (429, 503, 529) and attempts <= QUOTA_MAX_WAITS:
            time.sleep(QUOTA_WAIT_S)
            continue
        break
    if status == 401:
        raise SystemExit(
            "HTTP 401 from the API — OAuth token rejected; "
            "run any claude command to refresh it, then retry"
        )
    text, think, model_id, stop, usage, err = _parse(status, data, True)
    return {
        "text": text,
        "thinking": think,
        "model": model_id,
        "stop_reason": stop,
        "usage": usage,
        "status": status,
        "attempts": attempts,
        "session_id": sid,
        "raw": err,
    }


def rollout_with_retry(system_file, user_text, accept, **kw):
    """`accept(text) -> bool` decides whether a reply satisfies your
    contract. One retry on a rejected reply, then the best available is
    returned (caller decides how to score/surface it — a broken contract
    is a process signal, not noise). The extra count is wire attempts
    beyond the first, for capture accounting when a proxy records."""
    r1 = rollout(system_file, user_text, **kw)
    extra = r1["attempts"] - 1
    if r1["text"] and accept(r1["text"]):
        return r1, extra
    r2 = rollout(system_file, user_text, **kw)
    extra += r2["attempts"]
    return (
        r2 if r2["text"] and accept(r2["text"]) else (r2 if r2["text"] else r1)
    ), extra


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
        cache=a.cache,
        output_format=fmt,
        timeout=a.timeout,
    )
    json.dump(r, sys.stdout, indent=1)
    sys.stdout.write("\n")
    sys.exit(0 if r["text"] and r["status"] == 200 else 1)


if __name__ == "__main__":
    _cli()
