#!/usr/bin/env python3
"""Live wire-contract test — the probe matrix.

The rule the runner is built on is:

    a wire element belongs on the request iff removing it breaks a
    live call, or is recorded as a deliberate exception

which is a claim about a live API, so only a live API can check it. A
comment recording "probed 2026-08-28" rots silently; this does not. Run
it when the runner changes, and periodically, because the thing under
test is somebody else's server.

MODEL CHOICE IS LOAD-BEARING. haiku-4-5 does not enforce the billing
gate: it answers 200 with no billing line at all. Every ablation must
run against a gate-enforcing model (sonnet-5, opus-5) or it will
"prove" the line is optional — a mistake that has been made before.
The exemption is asserted below rather than merely written down, so
the trap stays visible.

Cost: ~20 calls at max_tokens 16, plus one real rollout.

Run: python3 integration_test.py          (exit 0 = green)
     INTEGRATION_MODEL=claude-opus-5 python3 integration_test.py
"""
import http.client
import json
import os
import sys
import time
import urllib.parse

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import bare_runner  # noqa: E402

GATED = os.environ.get("INTEGRATION_MODEL", "claude-sonnet-5")
EXEMPT = os.environ.get("INTEGRATION_EXEMPT_MODEL",
                        "claude-haiku-4-5-20251001")
BILLING = bare_runner.BILLING
CALLER = "You are a careful assistant."
FAILS = []
NOTES = []
LAST_HEADERS = []   # response header names of the most recent call()


def check(name, ok, detail=""):
    print("%-4s %-52s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        FAILS.append(name)


def call(headers, body, timeout=120):
    """(status, error_type) for one raw POST. No retry, no quota pause —
    this tier reads status codes as evidence, so nothing may smooth
    them over."""
    u = urllib.parse.urlsplit(bare_runner.base_url())
    cls = (http.client.HTTPSConnection if u.scheme == "https"
           else http.client.HTTPConnection)
    raw = json.dumps(body).encode()
    c = cls(u.netloc, timeout=timeout)
    try:
        c.putrequest("POST", (u.path.rstrip("/")) + "/v1/messages")
        for k, v in headers:
            c.putheader(k, v)
        c.putheader("Content-Length", str(len(raw)))
        c.endheaders(raw)
        r = c.getresponse()
        data = r.read()
        del LAST_HEADERS[:]
        LAST_HEADERS.extend(k.lower() for k, _ in r.getheaders())
        if r.status == 200:
            return 200, ""
        try:
            return r.status, (json.loads(data).get("error") or {}).get("type", "")
        except ValueError:
            return r.status, data[:60].decode("utf-8", "replace")
    finally:
        c.close()
        time.sleep(0.4)


def dress(auth=True, version=True, ctype=True, extra=()):
    """The runner's own header set, with each element removable. Built
    from bare_runner._headers so the test cannot drift from the code it
    describes — if a header is added there, it appears here."""
    live = bare_runner._headers("integration-test", 0)
    keep = []
    for k, v in live:
        lk = k.lower()
        if lk == "content-length":
            continue
        if lk == "authorization" and not auth:
            continue
        if lk == "anthropic-version" and not version:
            continue
        if lk == "content-type" and not ctype:
            continue
        keep.append((k, v))
    return keep + list(extra)


def body(model, system=(BILLING,), max_tokens=16, **kw):
    b = {"model": model, "max_tokens": max_tokens,
         "messages": [{"role": "user", "content": "hi"}]}
    if system is not None:
        b["system"] = [{"type": "text", "text": t} for t in system]
    b.update(kw)
    return b


def control(model, why):
    """A 200 on the minimal dress, asserted between ablations. Its job
    is to tell a real rate limit apart from the gate: both answer 429,
    and only an immediately-following 200 distinguishes them."""
    st, et = call(dress(), body(model))
    if st != 200:
        NOTES.append("control failed (%s %s) %s — results after this "
                     "point are unreliable; re-run when quota recovers"
                     % (st, et, why))
    return st == 200


def main():
    bare_runner.assert_env()
    print("gate-enforcing model: %s\nexempt model:         %s\n"
          % (GATED, EXEMPT))

    # -- the minimal dress is SUFFICIENT ---------------------------------
    # One probe retires every deleted element at once: if this returns
    # 200, then betas, stainless headers, metadata, context_management,
    # x-app and the rest are all unnecessary AS A GROUP. Removing them
    # one at a time could never show that.
    for model in (GATED, EXEMPT):
        st, et = call(dress(), body(model))
        check("minimal dress is sufficient (%s)" % model, st == 200,
              "%s %s" % (st, et))

    # -- each survivor is NECESSARY -------------------------------------
    st, et = call(dress(auth=False), body(GATED))
    check("Authorization required", st == 401, "%s %s" % (st, et))

    st, et = call(dress(version=False), body(GATED))
    check("anthropic-version required", st == 400, "%s %s" % (st, et))

    ok = control(GATED, "before the billing ablations")
    st, et = call(dress(), body(GATED, system=None))
    check("billing line required on a gated model", st == 429 and ok,
          "%s %s" % (st, et))

    # Position, not mere presence: the API reads the LEADING system text
    # as the billing claim. This is the expectation that keeps
    # build_body prepending rather than appending.
    st, et = call(dress(), body(GATED, system=(CALLER, BILLING)))
    check("billing line must lead the system prompt", st == 429,
          "%s %s" % (st, et))

    # Not probed here: "an arbitrary first block does not satisfy it"
    # (429) and "a billing line missing cc_version is malformed" (400).
    # Both are recorded at BILLING's definition, but neither guards a
    # decision in this code — the runner always sends the one
    # well-formed constant, so no edit to it could be caught by either
    # probe. They would characterise the API, not test the runner.

    st, et = call(dress(), body(GATED, system=(
        "x-anthropic-billing-header: cc_version=0.0.0; "
        "cc_entrypoint=sdk-cli;",)))
    check("billing VALUES are not read — cc_version may be anything",
          st == 200, "%s %s — if this fails the constant now rots and "
          "needs a refresh strategy" % (st, et))

    # -- the trap, asserted so it cannot be forgotten --------------------
    st, et = call(dress(), body(EXEMPT, system=None))
    check("haiku-4-5 does NOT enforce the gate (never ablate on it)",
          st == 200, "%s %s" % (st, et))

    # Not probed here: that the three headers kept by preference
    # (Content-Type, User-Agent, X-Claude-Code-Session-Id) are indeed
    # optional. Nothing breaks either way, since the runner sends them
    # regardless. Re-probe all three at the moment one is to be dropped.

    # -- features work with NO beta header -------------------------------
    TOOL = {"name": "think", "input_schema": {
        "type": "object", "properties": {"thoughts": {"type": "string"}},
        "required": ["thoughts"]}}
    features = [
        ("tools + forced tool_choice", dict(
            tools=[TOOL], tool_choice={"type": "tool", "name": "think"})),
        ("structured output", dict(output_config={"format": {
            "type": "json_schema", "schema": {
                "type": "object", "properties": {"a": {"type": "string"}},
                "required": ["a"], "additionalProperties": False}}})),
        ("adaptive thinking + summarized display", dict(
            max_tokens=2000,
            thinking={"type": "adaptive", "display": "summarized"})),
        ("effort in output_config", dict(output_config={"effort": "low"})),
        ("streaming", dict(stream=True)),
    ]
    for name, kw in features:
        st, et = call(dress(), body(GATED, **kw))
        check("%s needs no beta" % name, st == 200, "%s %s" % (st, et))

    # think.py's scheme, which is the reason family_thinking() exists:
    # forced tool_choice rejects type "enabled" but accepts "adaptive".
    st, et = call(dress(), body(
        GATED, max_tokens=2000,
        thinking=bare_runner.family_thinking(GATED),
        tools=[TOOL], tool_choice={"type": "tool", "name": "think"}))
    check("forced tool_choice + family_thinking (think.py's shape)",
          st == 200, "%s %s" % (st, et))

    st, et = call(dress(), body(
        GATED, max_tokens=2000,
        thinking={"type": "enabled", "budget_tokens": 1024},
        tools=[TOOL], tool_choice={"type": "tool", "name": "think"}))
    check("forced tool_choice still rejects thinking type 'enabled'",
          st == 400, "%s %s — if this passes, the provider relaxed the "
          "rule and think.py's 4.5 caveat can be revisited" % (st, et))

    # -- billing attribution -------------------------------------------
    # A 200 proves acceptance, never attribution. The unified family is
    # what sees billing, and it is diagnostic because the NEGATIVE arm
    # was measured too: with an API key the same request returns twelve
    # per-tier headers (requests / tokens / input-tokens / output-tokens)
    # and ZERO unified ones, 4/4 — the families partition cleanly. That
    # arm is deliberately not re-run here: it would bill a second
    # account from a test.
    st, et = call(dress(), body(GATED))
    unified = [k for k in LAST_HEADERS
               if k.startswith(bare_runner.UNIFIED_PREFIX)]
    per_tier = [k for k in LAST_HEADERS
                if k.startswith("anthropic-ratelimit-")
                and not k.startswith(bare_runner.UNIFIED_PREFIX)]
    check("subscription 200 carries the unified rate-limit family",
          st == 200 and bool(unified) and not per_tier,
          "unified=%d per-tier=%d" % (len(unified), len(per_tier)))

    # -- end to end: the runner's own wire earns a reply -----------------
    work = os.path.join(os.environ.get("TMPDIR", "/tmp"),
                        "integration-sysprompt.txt")
    with open(work, "w") as f:
        f.write("Answer with exactly one word.")
    r = bare_runner.rollout(work, "Say OK.", model=GATED, max_tokens=64)
    check("rollout() on the live wire returns a reply",
          r["status"] == 200 and bool(r["text"]),
          "status=%s text=%r" % (r["status"], (r["text"] or "")[:40]))
    # Not asserted here: "thinks by default" and "no <system-reminder>
    # on the wire". Both inspect a locally built body and make no
    # network call, so they belong in offline_test.py, which asserts
    # both.

    for n in NOTES:
        print("\nNOTE: %s" % n)
    print("\n%d failure(s)" % len(FAILS))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
