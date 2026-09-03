#!/usr/bin/env python3
"""Offline behavior test: no network, no login — a local canned
/v1/messages server plays the API. Covers what integration_test.py
(the live probe matrix) cannot cheaply: response parsing, tool_calls,
stream_round's halt lever, refusal surfacing, quota retry, billing
attribution warnings, the think-tool two-round transcript mechanics,
and the dry run's stopped-at-reasoning mechanics. It also freezes the
minimal wire as an exhaustive set, which is the guard against dressing
creeping back on.

Run: python3 offline_test.py   (exit 0 = green)
"""
import contextlib
import io
import json
import os
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# "No login" is part of this tier's contract: the token env
# short-circuits the credentials read, and HOME points at an empty
# fixture (bare_runner resolves ~/.claude/.credentials.json at import)
# so nothing here can touch the real CLI files even by accident.
_HOME = tempfile.mkdtemp(prefix="offline-home-")
os.environ["HOME"] = _HOME
os.environ["BARE_RUNNER_QUOTA_WAIT_S"] = "0"
os.environ["ANTHROPIC_STRIPPED_SDK_RUNNER"] = "sk-ant-test-offline"
KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import bare_runner  # noqa: E402
import think  # noqa: E402
import dryrun  # noqa: E402

FAILS = []


def check(name, ok, detail=""):
    print("%-4s %-46s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        FAILS.append(name)


# ---- canned server ----------------------------------------------------
REQS = []    # (body, headers) per request, in arrival order
CANNED = []  # response queue: (status, events-list | error-dict)

# Probed 2026-08-28 with an API key as the negative control: the two
# rate-limit families partition cleanly — subscription traffic gets
# anthropic-ratelimit-unified-* and no per-tier headers, API-key
# traffic gets the per-tier limits and no unified ones. That is what
# makes absence diagnostic, so both are modelled here.
UNIFIED_SAMPLE = ["anthropic-ratelimit-unified-status",
                  "anthropic-ratelimit-unified-5h-utilization"]
PER_TIER_SAMPLE = ["anthropic-ratelimit-requests-remaining",
                   "anthropic-ratelimit-tokens-remaining"]
SEND_UNIFIED = [True]   # False => play an API-key-billed response


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        REQS.append((body, dict(self.headers)))
        status, payload = CANNED.pop(0)
        if status == 200:
            data = b"".join(b"data: " + json.dumps(e).encode() + b"\n\n"
                            for e in payload)
            ctype = "text/event-stream"
        else:
            data = json.dumps(payload).encode()
            ctype = "application/json"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        # The real API answers subscription 200s with the unified
        # rate-limit family, so the canned one must too — otherwise
        # every test here trips the billing-attribution warning. Flip
        # SEND_UNIFIED to play an API-key-billed response instead.
        if status == 200 and SEND_UNIFIED[0]:
            for k in UNIFIED_SAMPLE:
                self.send_header(k, "allowed")
        elif status == 200:
            for k in PER_TIER_SAMPLE:
                self.send_header(k, "1000")
        self.end_headers()
        try:
            self.wfile.write(data)
        except BrokenPipeError:  # client hung up mid-stream (halt) — fine
            pass

    def log_message(self, *a):
        pass


def start(system_text, user_text, sysfile):
    with open(sysfile, "w") as f:
        f.write(system_text)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:%d" % srv.server_address[1]


def fresh():
    del REQS[:]
    del CANNED[:]


# ---- canned SSE event builders ----------------------------------------
def ev_start(model="claude-opus-5", inp=10):
    return {"type": "message_start",
            "message": {"model": model, "usage": {"input_tokens": inp,
                                                  "output_tokens": 1}}}


def ev_block(i, cb):
    return {"type": "content_block_start", "index": i, "content_block": cb}


def ev_text(i, t):
    return {"type": "content_block_delta", "index": i,
            "delta": {"type": "text_delta", "text": t}}


def ev_json(i, j):
    return {"type": "content_block_delta", "index": i,
            "delta": {"type": "input_json_delta", "partial_json": j}}


def ev_bstop(i):
    return {"type": "content_block_stop", "index": i}


def ev_end(stop, out, think=0):
    return {"type": "message_delta", "delta": {"stop_reason": stop},
            "usage": {"output_tokens": out,
                      "output_tokens_details": {"thinking_tokens": think}}}


def text_reply(text, out=42):
    return [ev_start(), {"type": "ping"},
            ev_block(0, {"type": "text", "text": ""}), ev_text(0, text),
            ev_bstop(0), ev_end("end_turn", out)]


def tool_reply(name, parts, tid="tu_1", out=100, think=0):
    # "caller" mirrors the live wire (observed 2026-08-14): response
    # decoration the runner must strip before blocks are echo-ready.
    return ([ev_start(),
             ev_block(0, {"type": "tool_use", "id": tid, "name": name,
                          "input": {}, "caller": {"type": "direct"}})]
            + [ev_json(0, p) for p in parts]
            + [ev_bstop(0), ev_end("tool_use", out, think)])


THINKING_REPLY = [ev_start(),
                  ev_block(0, {"type": "thinking", "thinking": "",
                               "signature": ""}),
                  {"type": "content_block_delta", "index": 0,
                   "delta": {"type": "thinking_delta", "thinking": "hm"}},
                  ev_end("end_turn", 9, 9)]

SYS = "You are a canned-wire probe."
USER = "Probe input."
TOOL = think.THINK
FORCE = {"type": "tool", "name": "think"}
# A synthetic stand-in for a target environment's tool roster.
ROSTER = [
    {"name": "search_files",
     "description": "Search the workspace for a pattern.",
     "input_schema": {"type": "object",
                      "properties": {"pattern": {"type": "string"}},
                      "required": ["pattern"]}},
    {"name": "edit_file",
     "description": "Replace text in a file.",
     "input_schema": {"type": "object",
                      "properties": {"path": {"type": "string"},
                                     "old": {"type": "string"},
                                     "new": {"type": "string"}},
                      "required": ["path", "old", "new"]}},
]


# The minimal wire, frozen as an EXHAUSTIVE set. Subset assertions
# ("authorization in headers") cannot see dressing creeping back, and
# creeping back is the failure this tier exists to catch — every entry
# below was either probed REQUIRED or is a deliberate, recorded
# exception. integration_test.py holds the live half: that each
# survivor breaks the call when removed.
WIRE_HEADERS = {
    "authorization",              # required: 401 without
    "anthropic-version",          # required: 400 without
    "content-type",               # not required (200 without); parity
    "user-agent",                 # not required; kept by preference
    "x-claude-code-session-id",   # not required; kept by preference
    "content-length",             # HTTP
    "host",                       # HTTP, added by http.client
    "accept-encoding",            # HTTP, identity, added by http.client
}
# thinking is here because reasoning is ON by default — the one
# behavioural default the runner keeps, by owner decision. max_tokens
# because the API requires the field. Nothing else is injected.
WIRE_BODY = {"model", "messages", "system", "max_tokens", "thinking",
             "stream"}


def header_names(headers):
    return {k.lower() for k in headers}


def main():
    work = os.path.join(os.environ.get("TMPDIR", "/tmp"), "offline-sysprompt.txt")
    start(SYS, USER, work)

    # -- plain rollout: reply parsed, wire is floor + caller only -------
    fresh()
    CANNED.append((200, text_reply("hello world")))
    r = bare_runner.rollout(work, USER)
    check("rollout: text reply parsed",
          r["text"] == "hello world" and r["stop_reason"] == "end_turn"
          and r["tool_calls"] == [] and r["status"] == 200
          and r["attempts"] == 1 and r["usage"].get("output_tokens") == 42
          and r["usage"].get("input_tokens") == 10
          and r["model"] == "claude-opus-5",
          "got %r" % {k: r[k] for k in ("text", "stop_reason", "status")})
    body, headers = REQS[0]
    sys_texts = [b["text"] for b in body["system"]]
    # The founding contract: `claude -p` contaminates the user turn with
    # a <system-reminder> and the model scores it as task signal. This
    # runner must never do that.
    check("user turn carries the caller's text and nothing else",
          body["messages"] == [{"role": "user", "content": [
              {"type": "text", "text": USER}]}]
          and "<system-reminder>" not in json.dumps(body))

    # Position is the contract, not presence: a caller block ahead of
    # the billing line costs a 429 indistinguishable from quota, which
    # the runner would then sit in a retry loop over.
    check("billing line leads the system prompt, caller's follows",
          sys_texts == [bare_runner.BILLING, SYS])

    # The minimal contract, asserted EXHAUSTIVELY. These two are the
    # regression guard on the whole change: anything re-added to the
    # wire — a beta, a stainless header, metadata, context_management
    # — fails here rather than silently altering how the model answers.
    check("wire: exactly the minimal header set, nothing more",
          header_names(headers) == WIRE_HEADERS,
          "extra=%s missing=%s"
          % (sorted(header_names(headers) - WIRE_HEADERS),
             sorted(WIRE_HEADERS - header_names(headers))))
    check("wire: exactly the minimal body keys, nothing more",
          set(body) == WIRE_BODY,
          "extra=%s missing=%s" % (sorted(set(body) - WIRE_BODY),
                                   sorted(WIRE_BODY - set(body))))
    # Asserted BY VALUE, not against family_thinking() — comparing
    # build_body's output to the function build_body calls would be
    # f(x) == f(x) and catch nothing. What matters observably: the
    # model reasons (owner decision), and display is "summarized",
    # without which the server bills thinking tokens and streams no
    # summary at all — a silent loss of the thing being paid for.
    check("thinking is on by default, with the summary unmasked",
          body["thinking"].get("type") != "disabled"
          and body["thinking"].get("display") == "summarized",
          "thinking=%r" % (body.get("thinking"),))
    check("wire: session id header carries the returned id",
          headers["X-Claude-Code-Session-Id"] == r["session_id"])

    # -- billing attribution: a 200 that was not subscription-billed ----
    # The runner's invariant is parity with an API-key call in
    # everything BUT billing, so the one thing it must not do quietly is
    # bill somewhere else. A 200 cannot see that; the rate-limit family
    # can. Warning, never an exception — these header names are
    # Anthropic's to change, and a rename must degrade to noise rather
    # than break every rollout.
    fresh()
    CANNED.append((200, text_reply("billed")))
    bare_runner._WARNED_UNBILLED[0] = False
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        bare_runner.rollout(work, USER)
    check("billing: subscription 200 warns about nothing",
          err.getvalue() == "", "stderr=%r" % err.getvalue()[:120])

    fresh()
    SEND_UNIFIED[0] = False
    CANNED.append((200, text_reply("elsewhere")))
    bare_runner._WARNED_UNBILLED[0] = False
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        r = bare_runner.rollout(work, USER)
    SEND_UNIFIED[0] = True
    warned = err.getvalue()
    check("billing: 200 without unified headers warns, expected/got",
          r["text"] == "elsewhere"          # non-fatal: the reply survives
          and "expected" in warned and "got" in warned
          and "anthropic-ratelimit-unified" in warned
          and "anthropic-ratelimit-requests-remaining" in warned,
          "stderr=%r" % warned[:160])

    # Once per process: this is a configuration fault, not a per-request
    # one, and a scored run must not drown in repeats of it.
    fresh()
    SEND_UNIFIED[0] = False
    CANNED.append((200, text_reply("a")))
    CANNED.append((200, text_reply("b")))
    bare_runner._WARNED_UNBILLED[0] = False
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        bare_runner.rollout(work, USER)
        bare_runner.rollout(work, USER)
    SEND_UNIFIED[0] = True
    check("billing: the warning is emitted once per process",
          err.getvalue().count("expected") == 1,
          "count=%d" % err.getvalue().count("expected"))

    # -- tools + forced tool_choice, input split across json deltas -----
    fresh()
    CANNED.append((200, tool_reply("think",
                                   ['{"thoug', 'hts": "abc"}'])))
    r = bare_runner.rollout(work, USER, tools=[TOOL], tool_choice=FORCE)
    check("rollout: forced call parsed across deltas",
          r["tool_calls"] == [{"type": "tool_use", "id": "tu_1",
                               "name": "think",
                               "input": {"thoughts": "abc"}}]
          and r["text"] is None and r["stop_reason"] == "tool_use")
    body, headers = REQS[0]
    # A feature adds the keys it owns and moves NOTHING else: the
    # header set and the rest of the body are unchanged by tools.
    check("tools go through verbatim and perturb nothing else",
          body["tools"] == [TOOL] and body["tool_choice"] == FORCE
          and header_names(headers) == WIRE_HEADERS
          and set(body) == WIRE_BODY | {"tools", "tool_choice"},
          "body=%s" % sorted(set(body)))

    # -- cache: caller block cached, billing bare, beta added -----------
    fresh()
    CANNED.append((200, text_reply("cached")))
    bare_runner.rollout(work, USER, cache=True)
    body, headers = REQS[0]
    # Probed 2026-08-28: cache_control works with no beta header.
    check("cache: caller block carries 1h, billing bare, no beta",
          "cache_control" not in body["system"][0]
          and body["system"][-1].get("cache_control")
          == {"type": "ephemeral", "ttl": "1h"}
          and header_names(headers) == WIRE_HEADERS)

    # -- rollout_with_retry: accept judges text; a rejected text retries
    #    once, a tool-only reply returns as-is without a wasted call ----
    fresh()
    CANNED.append((200, text_reply("bad")))
    CANNED.append((200, text_reply("good")))
    r, extra = bare_runner.rollout_with_retry(work, USER,
                                              lambda t: t == "good")
    check("retry: rejected text retries once",
          r["text"] == "good" and extra == 1 and len(REQS) == 2)
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "t"}'])))
    r, extra = bare_runner.rollout_with_retry(work, USER, lambda t: False,
                                              tools=[TOOL],
                                              tool_choice=FORCE)
    check("retry: tool-only reply returns without retry",
          [c["name"] for c in r["tool_calls"]] == ["think"]
          and extra == 0 and len(REQS) == 1,
          "%d request(s)" % len(REQS))

    # -- quota: 429 then 200 --------------------------------------------
    fresh()
    CANNED.append((429, {"type": "error",
                         "error": {"type": "rate_limit_error"}}))
    CANNED.append((200, text_reply("after quota")))
    r = bare_runner.rollout(work, USER)
    # attempts is the runner's own accounting, and the retry must carry
    # identical headers and body.
    check("quota: 429 pauses then retries, retry dressed the same",
          r["text"] == "after quota" and r["attempts"] == 2
          and len(REQS) == 2
          and header_names(REQS[0][1]) == header_names(REQS[1][1])
          and REQS[0][0] == REQS[1][0])

    # -- stream_round: halt hangs up at the first thinking block --------
    fresh()
    CANNED.append((200, THINKING_REPLY))
    b, _ = bare_runner.build_body(SYS, USER, "claude-opus-5", "xhigh")
    r = bare_runner.stream_round(
        b, halt=lambda cb: cb.get("type") == "thinking")
    check("stream_round: halt on thinking",
          r["stop_reason"] == "halted" and r["status"] == 200)

    # -- stream_round: quota pauses and retries, same policy as rollout -
    fresh()
    CANNED.append((503, {"type": "error",
                         "error": {"type": "overloaded_error"}}))
    CANNED.append((200, tool_reply("think", ['{"thoughts": "q"}'])))
    r = bare_runner.stream_round(b)
    check("stream_round: 503 pauses then retries",
          r["attempts"] == 2 and r["status"] == 200
          and [c["input"] for c in r["tool_calls"]] == [{"thoughts": "q"}])

    # -- stream_round: a refusal is surfaced, never silence -------------
    fresh()
    CANNED.append((200, [ev_start(), ev_end("refusal", 0)]))
    r = bare_runner.stream_round(b)
    check("stream_round: refusal surfaces",
          r["stop_reason"] == "refusal" and r["text"] is None
          and r["tool_calls"] == [])

    # -- build_body: messages + session id first-class ------------------
    history = [{"role": "user", "content": [{"type": "text", "text": "q"}]},
               {"role": "assistant", "content": [{"type": "text",
                                                  "text": "a"}]}]
    b2, sid2 = bare_runner.build_body(SYS, None, "claude-opus-5", "xhigh",
                                      messages=history, session_id="sid-1")
    check("build_body: messages + session_id first-class",
          b2["messages"] == history and sid2 == "sid-1")

    # -- think: the forced two-round scheme ------------------------
    fresh()
    CANNED.append((200, tool_reply("think",
                                   ['{"thoughts": "let me think"}'],
                                   tid="tu_r1", out=500)))
    CANNED.append((200, tool_reply("output", ['{"output": "42"}'],
                                   tid="tu_r2", out=300)))
    res = think.run(SYS, USER)
    check("think: ok verdict, thoughts + answer",
          res["verdict"] == "ok" and res["thoughts"] == "let me think"
          and res["answer"] == "42"
          and res["native_thinking_tokens"] == 0
          and res["output_tokens"] == 800)
    b1, b2 = REQS[0][0], REQS[1][0]
    check("think: both rounds forced, one session",
          b1["tool_choice"] == {"type": "tool", "name": "think"}
          and b2["tool_choice"] == {"type": "tool", "name": "output"}
          and b1["tools"] == b2["tools"]
          and REQS[0][1]["X-Claude-Code-Session-Id"]
          == REQS[1][1]["X-Claude-Code-Session-Id"])
    check("think: round 2 replays the tool transcript",
          b2["messages"] == b1["messages"] + [
              {"role": "assistant", "content": [
                  {"type": "tool_use", "id": "tu_r1", "name": "think",
                   "input": {"thoughts": "let me think"}}]},
              {"role": "user", "content": [
                  {"type": "tool_result", "tool_use_id": "tu_r1",
                   "content": "Acknowledged."}]}])

    # -- think: parallel think calls all count ----------------
    # The tool description invites "call it again if you need more
    # room"; nothing the model sent may be dropped, and round 2 must
    # replay the transcript the model actually produced.
    fresh()
    CANNED.append((200, [
        ev_start(),
        ev_block(0, {"type": "tool_use", "id": "tu_a", "name": "think",
                     "input": {}, "caller": {"type": "direct"}}),
        ev_json(0, '{"thoughts": "PART ONE"}'), ev_bstop(0),
        ev_block(1, {"type": "tool_use", "id": "tu_b", "name": "think",
                     "input": {}, "caller": {"type": "direct"}}),
        ev_json(1, '{"thoughts": "PART TWO"}'), ev_bstop(1),
        ev_end("tool_use", 600)]))
    CANNED.append((200, tool_reply("output", ['{"output": "done"}'])))
    res = think.run(SYS, USER)
    r2_msgs = REQS[1][0]["messages"]
    check("think: parallel calls join, both replayed",
          res["verdict"] == "ok"
          and res["thoughts"] == "PART ONE\n\nPART TWO"
          and [c["id"] for c in r2_msgs[-2]["content"]] == ["tu_a", "tu_b"]
          and [t["tool_use_id"] for t in r2_msgs[-1]["content"]]
          == ["tu_a", "tu_b"],
          "thoughts=%r" % (res["thoughts"],))

    # -- think: answer fields become output's schema ---------------
    fresh()
    fields = ["premise", "answer"]
    CANNED.append((200, tool_reply("think", ['{"thoughts": "t"}'])))
    CANNED.append((200, tool_reply(
        "output", ['{"premise": "p", "answer": "a"}'])))
    res = think.run(SYS, USER, answer_fields=fields)
    schema = REQS[1][0]["tools"][1]["input_schema"]
    check("think: answer_fields typed into the tool",
          res["verdict"] == "ok"
          and res["answer"] == {"premise": "p", "answer": "a"}
          and list(schema["properties"]) == fields
          and schema["required"] == fields)

    # -- think guard rails -----------------------------------------
    fresh()
    CANNED.append((200, THINKING_REPLY))
    res = think.run(SYS, USER)
    check("think: native thinking aborts round 1",
          res["verdict"] == "native-thinking (round 1)"
          and res["answer"] is None and len(REQS) == 1)

    fresh()  # billed-thinking backstop: tool call arrived, but usage says 500
    CANNED.append((200, tool_reply("think", ['{"thoughts": "t"}'],
                                   think=500)))
    res = think.run(SYS, USER)
    check("think: billed-thinking backstop",
          res["verdict"] == "native-thinking (round 1)" and len(REQS) == 1)

    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "kept"}'])))
    CANNED.append((200, [ev_start(), ev_end("refusal", 0)]))
    res = think.run(SYS, USER)
    check("think: round-2 refusal surfaces, thoughts kept",
          res["verdict"] == "refusal (round 2)" and res["thoughts"] == "kept")

    # -- think: the remaining failure shapes surface as verdicts ---
    fresh()
    CANNED.append((500, {"type": "error",
                         "error": {"type": "api_error"}}))
    res = think.run(SYS, USER)
    check("think: transport failure surfaces",
          res["verdict"] == "http 500 (round 1)" and len(REQS) == 1)

    fresh()  # forced think, but an output call arrives
    CANNED.append((200, tool_reply("output", ['{"output": "no"}'])))
    res = think.run(SYS, USER)
    check("think: missing forced call surfaces",
          res["verdict"] == "stop tool_use, no think call (round 1)")

    # -- think.probe: first block, then hang up --------------------
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "x"}'])))
    b, _ = bare_runner.build_body(SYS, USER, "claude-opus-5", "xhigh",
                                  tools=[TOOL], tool_choice=FORCE)
    check("think.probe: channel decision",
          think.probe(b) == ("tool_use", "think"))
    fresh()
    CANNED.append((200, THINKING_REPLY))
    check("think.probe: native thinking read",
          think.probe(b) == ("thinking", None))
    fresh()
    CANNED.append((200, [ev_start(), ev_end("refusal", 0)]))
    check("think.probe: refusal read",
          think.probe(b) == ("refusal", None))

    # -- dryrun: round 1 forces think with the roster declared;
    #    no working round is ever sent when the probe is off ------------
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "map first"}'],
                                   out=500)))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER, probe=False)
    check("dryrun: round-1-only, thoughts in hand",
          res["verdict"] == "ok" and res["thoughts"] == "map first"
          and res["first_action"] is None and res["probe_thoughts"] is None
          and res["cochannel_calls"] == [] and len(REQS) == 1
          and res["output_tokens"] == 500
          and res["native_thinking_tokens"] == 0,
          "got %r, %d request(s)" % (res["verdict"], len(REQS)))
    body = REQS[0][0]
    check("dryrun: forced think rides with the full roster",
          body["tools"] == [think.THINK] + ROSTER
          and body["tool_choice"] == {"type": "tool", "name": "think"})

    # -- dryrun probe: transcript replayed under tool_choice any; the
    #    first intended action arrives complete, then the line drops ----
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "plan"}'],
                                   tid="tu_d1", out=500)))
    CANNED.append((200, [
        ev_start(),
        ev_block(0, {"type": "tool_use", "id": "tu_d2",
                     "name": "search_files", "input": {},
                     "caller": {"type": "direct"}}),
        ev_json(0, '{"pattern": '), ev_json(0, '"TODO"}'), ev_bstop(0),
        # a second action begins; the dry run must hang up, not read on
        ev_block(1, {"type": "tool_use", "id": "tu_d3", "name": "edit_file",
                     "input": {}, "caller": {"type": "direct"}}),
        ev_json(1, '{"path": "x"}'), ev_bstop(1),
        ev_end("tool_use", 80)]))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    check("dryrun probe: first complete action, then hang up",
          res["verdict"] == "ok" and res["thoughts"] == "plan"
          and res["first_action"] == {"name": "search_files",
                                      "input": {"pattern": "TODO"}}
          and res["rounds"][1]["stop_reason"] == "halted"
          # the audit contract: the block the hang-up cut off stays in
          # rounds — empty input, never digested into first_action
          and [c["input"] for c in res["rounds"][1]["tool_calls"]]
          == [{"pattern": "TODO"}, {}],
          "first_action=%r" % (res["first_action"],))
    b1, b2 = REQS[0][0], REQS[1][0]
    check("dryrun probe: any-tool round rides the replayed session",
          b2["tool_choice"] == {"type": "any"}
          and b2["tools"] == b1["tools"]
          and REQS[0][1]["X-Claude-Code-Session-Id"]
          == REQS[1][1]["X-Claude-Code-Session-Id"]
          and b2["messages"] == b1["messages"] + [
              {"role": "assistant", "content": [
                  {"type": "tool_use", "id": "tu_d1", "name": "think",
                   "input": {"thoughts": "plan"}}]},
              {"role": "user", "content": [
                  {"type": "tool_result", "tool_use_id": "tu_d1",
                   "content": "Acknowledged."}]}])

    # -- dryrun: an action smuggled into the forced round is recorded
    #    and the probe replays the transcript the model actually made ---
    fresh()
    CANNED.append((200, [
        ev_start(),
        ev_block(0, {"type": "tool_use", "id": "tu_s1", "name": "think",
                     "input": {}, "caller": {"type": "direct"}}),
        ev_json(0, '{"thoughts": "quick check"}'), ev_bstop(0),
        ev_block(1, {"type": "tool_use", "id": "tu_s2",
                     "name": "search_files", "input": {}}),
        ev_json(1, '{"pattern": "cfg"}'), ev_bstop(1),
        ev_end("tool_use", 400)]))
    CANNED.append((200, tool_reply("edit_file",
                                   ['{"path": "a", "old": "b", "new": "c"}'],
                                   tid="tu_s3", out=60)))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    r2_msgs = REQS[1][0]["messages"]
    check("dryrun: cochannel call recorded, replayed, acknowledged",
          res["verdict"] == "ok"
          and res["cochannel_calls"] == [{"name": "search_files",
                                          "input": {"pattern": "cfg"}}]
          and res["first_action"] == {"name": "edit_file",
                                      "input": {"path": "a", "old": "b",
                                                "new": "c"}}
          and [c["id"] for c in r2_msgs[-2]["content"]] == ["tu_s1", "tu_s2"]
          and [t["tool_use_id"] for t in r2_msgs[-1]["content"]]
          == ["tu_s1", "tu_s2"],
          "cochannel=%r" % (res["cochannel_calls"],))

    # -- dryrun probe: the model may keep reasoning instead of acting ---
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "t1"}'],
                                   tid="tu_k1")))
    CANNED.append((200, tool_reply("think", ['{"thoughts": "still unsure"}'],
                                   tid="tu_k2", out=90)))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    check("dryrun probe: more reasoning kept, labeled, not an action",
          res["verdict"] == "ok" and res["first_action"] == {"none": "think"}
          and res["probe_thoughts"] == "still unsure"
          and res["thoughts"] == "t1")

    # -- dryrun probe: no call at all degrades first_action only --------
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "kept"}'])))
    CANNED.append((200, [ev_start(), ev_end("refusal", 0)]))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    check("dryrun probe: probe refusal, thoughts stay the product",
          res["verdict"] == "ok" and res["thoughts"] == "kept"
          and res["first_action"] == {"none": "refusal"})

    # -- dryrun guard rails: a bad round 1 aborts before any probe ------
    fresh()
    CANNED.append((200, THINKING_REPLY))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    check("dryrun: native thinking aborts, probe never sent",
          res["verdict"] == "native-thinking (round 1)"
          and res["thoughts"] is None and res["first_action"] is None
          and len(REQS) == 1, "%d request(s)" % len(REQS))

    fresh()  # 0-thinking guard: the call arrived but usage says 500
    CANNED.append((200, tool_reply("think", ['{"thoughts": "t"}'],
                                   think=500)))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    check("dryrun: billed-thinking backstop, probe never sent",
          res["verdict"] == "native-thinking (round 1)" and len(REQS) == 1)

    fresh()
    CANNED.append((200, [ev_start(), ev_end("refusal", 0)]))
    res = dryrun.dry_run(SYS, USER, tools=ROSTER)
    check("dryrun: round-1 refusal surfaces as the verdict",
          res["verdict"] == "refusal (round 1)" and len(REQS) == 1)

    # -- dryrun default env: the shipped captured environments ----------
    shipped = dryrun.default_roster()
    replica = json.load(open(os.path.join(
        KIT, "envs", "replicated-env-20260814", "tools.json"),
        encoding="utf-8"))
    check("env rosters: wire-shape tool entries, no think collision",
          all(isinstance(r, list) and r
              and all(sorted(t) == ["description", "input_schema", "name"]
                      for t in r)
              and think.THINK["name"] not in [t["name"] for t in r]
              for r in (shipped, replica)))
    check("env system prompt: nonempty, the captured CLI identity",
          dryrun.default_system().startswith(
              "You are Claude Code, Anthropic's official CLI for Claude."))
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "real"}'])))
    res = dryrun.dry_run(SYS, USER, probe=False)
    check("dryrun: tools omitted declares the shipped roster verbatim",
          res["verdict"] == "ok"
          and REQS[0][0]["tools"] == [think.THINK] + shipped)
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "bare"}'])))
    res = dryrun.dry_run(SYS, USER, tools=[], probe=False)
    check("dryrun: tools=[] stays bare, think alone on the wire",
          res["verdict"] == "ok" and REQS[0][0]["tools"] == [think.THINK])

    # -- CLI: the tools flags are usable end-to-end ---------------------
    # A tool-only reply IS the reply (exit 0), and --no-thinking exists
    # because the 4.5 family — the quick-test family — rejects forced
    # tool_choice with thinking enabled.
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "cli"}'])))
    p = subprocess.run(
        [sys.executable, os.path.join(KIT, "bare_runner.py"),
         "--system-prompt-file", work, "--no-thinking",
         "--tools", json.dumps([TOOL]), "--tool-choice", json.dumps(FORCE),
         USER],
        capture_output=True, text=True)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = {}
    body = REQS[0][0] if REQS else {}
    check("cli: forced tool run exits 0, call in JSON",
          p.returncode == 0
          and [c.get("input") for c in out.get("tool_calls") or []]
          == [{"thoughts": "cli"}]
          and body.get("thinking") == {"type": "disabled"}
          and "context_management" not in body,
          "exit=%s stderr=%r" % (p.returncode, p.stderr[-120:]))

    # -- dryrun CLI: roster file + --no-probe usable end-to-end ---------
    fresh()
    CANNED.append((200, tool_reply("think", ['{"thoughts": "cli dry"}'])))
    tf = os.path.join(os.environ.get("TMPDIR", "/tmp"), "offline-roster.json")
    with open(tf, "w") as f:
        json.dump(ROSTER, f)
    p = subprocess.run(
        [sys.executable, os.path.join(KIT, "dryrun.py"),
         "--tools-file", tf,   # system prompt deliberately omitted:
         "--no-probe", "--no-thinking", USER],  # the shipped default
        capture_output=True, text=True)
    try:
        out = json.loads(p.stdout)
    except ValueError:
        out = {}
    body = REQS[0][0] if REQS else {}
    check("dryrun cli: exits 0, shipped system default, one request",
          p.returncode == 0 and out.get("thoughts") == "cli dry"
          and out.get("first_action") is None and len(REQS) == 1
          and body.get("tools") == [think.THINK] + ROSTER
          and body.get("system", [{}, {}])[1].get("text")
          == dryrun.default_system(),
          "exit=%s stderr=%r" % (p.returncode, p.stderr[-120:]))

    print("\n%d failure(s)" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
