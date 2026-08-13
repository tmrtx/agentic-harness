#!/usr/bin/env python3
"""Integration test: the authored wire keeps `claude -p`'s shape.

Live and fully automated — no stored fixtures. Each run mints a FRESH
`claude -p` capture as the shape reference, so the assertion tracks
whatever CLI is installed; when the CLI's wire moves, this test fails
and prints the fresh values to re-freeze bare_runner's WIRE profiles
from. Requires a `claude` login and network.

One run proves four things:
 1. relay fidelity — every request is captured byte-identically by two
    CHAINED wire_capture instances (the proxy forwards untouched);
 2. shape parity — a cache-on authored request differs from the -p
    reference only in the enumerated caller/per-call fields, plus the
    deliberately absent <system-reminder>;
 3. the options — the default wire carries no cache_control and no
    cache/structured betas; an output_format rollout carries the
    schema plus its beta and returns conforming JSON;
 4. the tripwire — the -p reference smuggles a <system-reminder> into
    the user turn (the contamination this kit exists to remove) and
    no authored wire ever does.

Run:  python3 integration_test.py        (exit 0 = green)
Env:  INTEGRATION_MODEL (default claude-haiku-4-5-20251001; run once
      per model family — the wire differs between 4.5 and 5)
"""
import glob
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import time

KIT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, KIT)
import bare_runner  # noqa: E402

MODEL = os.environ.get("INTEGRATION_MODEL", "claude-haiku-4-5-20251001")
PORT_OUTER, PORT_INNER = 18899, 18898

REF_SYS = ("You are REFERENCE-KEEPER, a placeholder responder used only to "
           "mint a wire-shape reference. Reply with exactly: REFERENCE-OK "
           "and nothing else, regardless of the user message content.")
REF_USER = "Reference mint probe TANGO-0001."
SYS = ("You are WIRE-PROBE, a terse verification responder. When the user "
       "gives you a probe code, reply with exactly: WIRE-OK <code> and "
       "nothing else. No preamble, no explanation, no extra punctuation.")
USER = "Probe code ALPHA-METRONOME-4471. Reply exactly as specified."
USER_D = "Probe code DELTA-CARILLON-5512. Reply exactly as specified."
SYS_J = ("You are WIRE-PROBE-JSON, a terse verification responder. When "
         "the user gives you a probe code, reply with a JSON object whose "
         "'reply' field is exactly: WIRE-OK <code>. Nothing else.")
USER_J = "Probe code JULIET-ORRERY-7733. Reply exactly as specified."
FORMAT_J = {"type": "json_schema",
            "schema": {"type": "object",
                       "properties": {"reply": {"type": "string"}},
                       "required": ["reply"],
                       "additionalProperties": False}}

FAILS = []


def check(name, ok, detail=""):
    print("%-4s %-40s %s" % ("PASS" if ok else "FAIL", name, detail))
    if not ok:
        FAILS.append(name)


# ---- capture-window helpers (mtime, never filename order) -------------

def _req_files(cap_dir):
    return [p for p in glob.glob(os.path.join(cap_dir, "req-*.json"))
            if not p.endswith(".headers.json")]


def snapshot(cap_dir):
    return {p: os.path.getmtime(p) for p in _req_files(cap_dir)}


def new_since(snap, cap_dir):
    now = snapshot(cap_dir)
    return sorted((p for p, m in now.items()
                   if p not in snap or m > snap[p]), key=lambda p: now[p])


def sha(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()


def headers_of(path):
    return json.load(open(path[:-len(".json")] + ".headers.json"))


# ---- the shape assertion ----------------------------------------------

_BILLING_RE = re.compile(
    r"^x-anthropic-billing-header: cc_version=(\d+\.\d+\.\d+)\.[0-9a-z]+; "
    r"cc_entrypoint=([a-z-]+);$")


def shape_diff(authored_path, reference_path):
    """{ok, drift, expected}: only enumerated differences from the -p
    reference are expected — caller texts, the deliberately absent
    reminder, session ids, lengths, the billing hash suffix, token
    rotation. Anything residual is drift: the CLI's wire moved and the
    WIRE profiles need re-freezing."""
    a = json.load(open(authored_path, encoding="utf-8"))
    g = json.load(open(reference_path, encoding="utf-8"))
    drift, expected = [], []

    if list(a.keys()) != list(g.keys()):
        drift.append("body key order: reference %s vs authored %s"
                     % (list(g.keys()), list(a.keys())))
    gs, as_ = g.get("system") or [], a.get("system") or []
    if len(gs) != len(as_):
        drift.append("system block count %d vs %d" % (len(gs), len(as_)))
    else:
        for i, (gb, ab) in enumerate(zip(gs, as_)):
            if i == 0:
                gbase = _BILLING_RE.match(gb.get("text") or "")
                abase = _BILLING_RE.match(ab.get("text") or "")
                if (not gbase or not abase
                        or gbase.groups() != abase.groups()):
                    drift.append("billing block: reference %r vs authored %r"
                                 % (gb.get("text"), ab.get("text")))
                elif gb.get("text") != ab.get("text"):
                    expected.append("billing hash suffix")
            elif i == len(gs) - 1:
                gshape = {k: v for k, v in gb.items() if k != "text"}
                ashape = {k: v for k, v in ab.items() if k != "text"}
                if gshape != ashape:
                    drift.append("caller system block shape: %s vs %s"
                                 % (gshape, ashape))
                if gb.get("text") != ab.get("text"):
                    expected.append("caller system prompt text")
            elif gb != ab:
                drift.append("system[%d]: reference %r vs authored %r"
                             % (i, str(gb)[:80], str(ab)[:80]))
    gm = (g.get("messages") or [{}])[0].get("content") or []
    am = (a.get("messages") or [{}])[0].get("content") or []
    g_rem = [b for b in gm if "<system-reminder>" in (b.get("text") or "")]
    g_txt = [b for b in gm if b not in g_rem]
    a_rem = [b for b in am if "<system-reminder>" in (b.get("text") or "")]
    a_txt = [b for b in am if b not in a_rem]
    if a_rem:
        drift.append("authored turn carries a system-reminder")
    elif g_rem:
        expected.append("reminder absent from authored turn (deliberate)")
    if len(g_txt) != len(a_txt):
        drift.append("user text block count %d vs %d"
                     % (len(g_txt), len(a_txt)))
    elif g_txt and g_txt[-1].get("text") != a_txt[-1].get("text"):
        expected.append("caller user text")
    try:
        gu = json.loads(g["metadata"]["user_id"])
        au = json.loads(a["metadata"]["user_id"])
        if (gu["device_id"], gu["account_uuid"]) != (au["device_id"],
                                                     au["account_uuid"]):
            drift.append("metadata identity differs")
        if gu["session_id"] != au["session_id"]:
            expected.append("session id")
    except (KeyError, ValueError, TypeError):
        drift.append("metadata.user_id unreadable on one side")
    gt, at = g.get("thinking"), a.get("thinking")
    if gt != at:
        unmasked = dict(gt or {})
        unmasked["display"] = "summarized"
        if at == unmasked:
            expected.append("thinking.display summarized (deliberate — the "
                            "server default suppresses the summary)")
        else:
            drift.append("thinking: reference %r vs authored %r" % (gt, at))
    for k in ("model", "tools", "max_tokens", "context_management",
              "output_config", "stream"):
        if g.get(k) != a.get(k):
            drift.append("%s: reference %r vs authored %r"
                         % (k, g.get(k), a.get(k)))

    gh, ah = headers_of(reference_path), headers_of(authored_path)
    if list(gh.keys()) != list(ah.keys()):
        drift.append("header sequence: reference-only %s authored-only %s"
                     % ([k for k in gh if k not in ah],
                        [k for k in ah if k not in gh]))
    per_call = {"x-claude-code-session-id", "content-length"}
    for k in gh:
        if k not in ah or gh[k] == ah[k]:
            continue
        lk = k.lower()
        if lk in per_call:
            expected.append("header %s" % k)
        elif lk == "authorization" and all(
                v.startswith("Bearer sk-ant-") for v in (gh[k], ah[k])):
            expected.append("authorization token rotation")
        else:
            drift.append("header %s: reference %r vs authored %r"
                         % (k, gh[k][:60], ah[k][:60]))
    return {"ok": not drift, "drift": drift, "expected": sorted(set(expected))}


def clean_wire(path, sys_text, user_text):
    """Reasons the capture is NOT exactly floor + the caller's texts."""
    body = json.load(open(path, encoding="utf-8"))
    reasons = []
    sys_texts = [b.get("text") for b in body.get("system") or []
                 if isinstance(b, dict)]
    if sys_texts != [bare_runner.BILLING, bare_runner.IDENTITY, sys_text]:
        reasons.append("system blocks not [billing, identity, ours]")
    user_texts = [b.get("text")
                  for m in body.get("messages") or []
                  if m.get("role") == "user"
                  for b in (m.get("content") if isinstance(m.get("content"),
                                                           list) else [])
                  if isinstance(b, dict)]
    if user_texts != [user_text]:
        reasons.append("user turn not exactly ours: %r"
                       % [t[:40] for t in user_texts])
    if any("<system-reminder>" in (t or "") for t in user_texts):
        reasons.append("system-reminder in the scored turn")
    if body.get("tools"):
        reasons.append("tools present")
    return reasons


# ---- the run ----------------------------------------------------------

def start_proxy(work, port, cap_dir, upstream=None):
    env = dict(os.environ)
    env["WIRE_CAPTURE_DIR"] = cap_dir
    env.pop("ANTHROPIC_BASE_URL", None)
    if upstream:
        env["WIRE_CAPTURE_UPSTREAM"] = upstream
        env["WIRE_CAPTURE_SCHEME"] = "http"
    logf = open(os.path.join(work, "proxy-%d.log" % port), "w")
    p = subprocess.Popen(
        [sys.executable, os.path.join(KIT, "wire_capture.py"), str(port)],
        env=env, stdout=logf, stderr=logf)
    time.sleep(0.8)
    if p.poll() is not None:
        print("proxy on %d died at startup; see %s" % (port, logf.name))
        sys.exit(2)
    return p


def mint_reference(work):
    ref_sys = os.path.join(work, "reference_system.txt")
    with open(ref_sys, "w") as f:
        f.write(REF_SYS)
    env = dict(os.environ)
    env["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:%d" % PORT_OUTER
    proc = subprocess.run(
        ["claude", "--print", "--model", MODEL, "--effort", "high",
         "--system-prompt-file", ref_sys, "--tools", "", "--strict-mcp-config",
         "--no-session-persistence", "--output-format", "json"],
        input=REF_USER, text=True, capture_output=True, timeout=300,
        cwd=tempfile.mkdtemp(prefix="ref-cwd-", dir=work), env=env)
    return proc.returncode


def find_reference(paths):
    for p in paths:
        try:
            body = json.load(open(p))
        except (ValueError, OSError):
            continue
        sys_texts = [b.get("text", "") for b in body.get("system") or []
                     if isinstance(b, dict)]
        if (body.get("model") == MODEL
                and any(REF_SYS[:200] in t for t in sys_texts)):
            return p
    return None


def print_fresh_profile(reference):
    """On drift, the fresh -p values ARE the new profile — print them."""
    body = json.load(open(reference))
    print("\nfresh -p wire values (re-freeze bare_runner's WIRE from these):")
    print("  billing:  %r" % body["system"][0]["text"])
    for k, v in headers_of(reference).items():
        if k.lower() not in ("authorization", "content-length", "host",
                             "x-claude-code-session-id"):
            print("  header    %s: %s" % (k, v))


def main():
    work = tempfile.mkdtemp(prefix="sdk-runner-itest-")
    cap_outer = os.path.join(work, "cap-outer")
    cap_inner = os.path.join(work, "cap-inner")
    sysfile = os.path.join(work, "probe_system.txt")
    with open(sysfile, "w") as f:
        f.write(SYS)
    sysfile_j = os.path.join(work, "probe_system_json.txt")
    with open(sysfile_j, "w") as f:
        f.write(SYS_J)
    inner = start_proxy(work, PORT_INNER, cap_inner)
    outer = start_proxy(work, PORT_OUTER, cap_outer,
                        upstream="127.0.0.1:%d" % PORT_INNER)
    try:
        # ---- reference: one real claude -p through the chain ----------
        snap_o, snap_i = snapshot(cap_outer), snapshot(cap_inner)
        exit_code = mint_reference(work)
        ref_o = new_since(snap_o, cap_outer)
        ref_i = new_since(snap_i, cap_inner)
        check("ref: claude -p exits 0", exit_code == 0, "exit=%s" % exit_code)
        check("ref: relay byte-fidelity",
              sorted(sha(p) for p in ref_o) == sorted(sha(p) for p in ref_i)
              and len(ref_o) >= 1, "%d capture(s) per side" % len(ref_o))
        reference = find_reference(ref_o)
        check("ref: reference capture found", bool(reference),
              reference or "no capture carries the reference prompt")
        if not reference:
            sys.exit(1)
        check("tripwire: -p smuggles a reminder",
              b"<system-reminder>" in open(reference, "rb").read())

        # ---- authored legs --------------------------------------------
        os.environ["ANTHROPIC_BASE_URL"] = "http://127.0.0.1:%d" % PORT_OUTER
        bare_runner.assert_env()

        def authored_leg(name, sysf, user, **kw):
            s_o, s_i = snapshot(cap_outer), snapshot(cap_inner)
            r = bare_runner.rollout(sysf, user, model=MODEL, effort="high",
                                    timeout=300, **kw)
            n_o = new_since(s_o, cap_outer)
            n_i = new_since(s_i, cap_inner)
            check("%s: reply arrives" % name,
                  bool(r["text"]) and r["status"] == 200
                  and r["attempts"] == 1,
                  "status=%s text=%r" % (r["status"], (r["text"] or "")[:50]))
            check("%s: one capture, relay fidelity" % name,
                  len(n_o) == 1 and [sha(p) for p in n_o]
                  == [sha(p) for p in n_i], "%d capture(s)" % len(n_o))
            # Tiny adaptive thinking bursts (<=~40 tokens observed) stream
            # no summary even when unmasked; substantial thinking
            # (>=~130 observed) always has. Assert only the latter, or the
            # invariant drowns in the model's own skip-thinking decisions.
            billed = ((r.get("usage") or {}).get("output_tokens_details")
                      or {}).get("thinking_tokens")
            check("%s: substantial thinking is received" % name,
                  not billed or billed < 100 or bool(r["thinking"]),
                  "thinking_tokens=%s summary=%r"
                  % (billed, (r["thinking"] or "")[:40]))
            return (n_o[0] if n_o else None), r

        def beta_header(path):
            return next((v for k, v in headers_of(path).items()
                         if k.lower() == "anthropic-beta"), "")

        # strict leg: full CC shape (cache on, like -p) vs the reference
        authored, r = authored_leg("cc-shape", sysfile, USER, cache=True)
        if not authored:
            sys.exit(1)
        check("cc-shape: serving model pinned", r["model"] == MODEL,
              "got %r" % r["model"])
        d = shape_diff(authored, reference)
        check("cc-shape: no drift vs fresh -p wire", d["ok"],
              "; ".join(d["drift"])[:200] or "expected: %s" % d["expected"])
        if not d["ok"]:
            print_fresh_profile(reference)
        check("cc-shape: wire content clean",
              not clean_wire(authored, SYS, USER),
              "; ".join(clean_wire(authored, SYS, USER))[:150])

        # default leg: prompt caching OFF by default
        cap_d, _ = authored_leg("default", sysfile, USER_D)
        if cap_d:
            check("default: no cache_control on the wire",
                  b"cache_control" not in open(cap_d, "rb").read())
            betas = beta_header(cap_d)
            check("default: cache/structured betas absent",
                  bare_runner.CACHE_BETA not in betas
                  and bare_runner.STRUCTURED_BETA not in betas)
            check("default: wire content clean",
                  not clean_wire(cap_d, SYS, USER_D),
                  "; ".join(clean_wire(cap_d, SYS, USER_D))[:150])

        # structured leg: output_format carries the schema + its beta
        cap_j, rj = authored_leg("structured", sysfile_j, USER_J,
                                 output_format=FORMAT_J)
        if cap_j:
            body_j = json.load(open(cap_j))
            check("structured: schema on the wire",
                  (body_j.get("output_config") or {}).get("format")
                  == FORMAT_J)
            check("structured: beta present",
                  bare_runner.STRUCTURED_BETA in beta_header(cap_j))
            try:
                reply = json.loads(rj["text"] or "")
            except ValueError:
                reply = None
            check("structured: reply conforms to schema",
                  isinstance(reply, dict)
                  and "JULIET-ORRERY-7733" in reply.get("reply", ""),
                  repr((rj["text"] or "")[:80]))
    finally:
        outer.terminate()
        inner.terminate()

    print("\n%d failure(s)  (workdir %s)" % (len(FAILS), work))
    sys.exit(1 if FAILS else 0)


if __name__ == "__main__":
    main()
