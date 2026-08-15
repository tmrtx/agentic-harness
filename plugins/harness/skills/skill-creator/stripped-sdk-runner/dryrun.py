#!/usr/bin/env python3
"""Stopped-at-reasoning dry runs — the pre-ship behavioral X-ray.

Distilled from the 2026-08-14 dry-run experiments: reasoning chains
contain defect ENACTMENT — the model performing a misreading in its
plan rather than stating it anywhere — that no readback or
self-report surfaces. A dry run captures the chain a prompt would
produce BEFORE any side effect exists: think.py's forced round 1
runs with the target environment's FULL tool roster declared
alongside, so the model reasons inside a tooled environment and the
reasoning arrives as the think calls' input — and no working round
is ever sent. The default roster is the real thing: Claude Code's
own tool declarations captured verbatim from the wire, in a file
whose name carries the CLI version and capture date (see
default_roster / ROSTER_FILE); a synthetic or trimmed roster
defeats the X-ray, because the model plans with the tools it sees. A non-think call the model smuggles into the forced
round is first-action signal too: recorded (cochannel_calls), never
executed — nothing here can execute one.

Optional probe, on by default: one more round on the SAME session —
the transcript the model actually produced, every call answered
"Acknowledged.", tool_choice {"type": "any"} — hung up right after
the FIRST tool_use block completes (the halt fires at whatever
block starts next). The first intended action arrives with full
args for the price of re-billing the transcript as input plus about
one call's output. Only that first block is complete by
construction; a later block cut off at its start stays in rounds
for audit but is never reported as an action. A halted round's
usage counts only what streamed before the hang-up, so the probe's
output_tokens are a floor, not the bill.

Verdict is round 1's, via think.bad_round — transport, a native
thinking block (halted at first sight, 2-5 tokens), billed thinking
(the 0-thinking backstop), refusal, a missing forced call — and any
of them skips the probe. Probe failures never invalidate thoughts
already in hand; they land in first_action as {"none": reason}
("think" = the first free choice was more reasoning, kept in
probe_thoughts).

CLI:
    python3 dryrun.py --system-prompt-file sys.txt "user text"
        [--tools-file roster.json]    [--no-probe]
Prints the result dict as JSON; exits 0 iff verdict == "ok".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bare_runner  # noqa: E402
import think  # noqa: E402

ROSTER_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "roster-claude-code-2.1.233-20260815.json")


def default_roster():
    """Claude Code's own tool roster, captured verbatim from the wire:
    the tools array of the /v1/messages request a direct
    `claude -p "Say hi." --model claude-opus-5` sends (claude-cli
    2.1.233, 2026-08-15; pristine container, wire_capture.py in
    front of a 401 stub, nothing reached the API). The file name
    carries the CLI version and capture date. Cross-checked against
    an Agent SDK 0.3.233 capture of the same CLI version: all 20
    schemas and 18/20 descriptions byte-identical; the CLI itself
    varies the other two per mode — Agent's delegation guidance and
    the model display name inside Bash's commit-trailer line — so
    tool descriptions are also model- and version-dependent (pick
    the model you dry-run for; opus-5 here). MCP servers, per-repo
    skills, and interactive-only tools are never in a -p capture —
    pass `tools` for a customized target. Re-freeze by re-running
    the rig against a newer CLI, dropping in a new dated
    roster-claude-code-* file, and pointing ROSTER_FILE at it."""
    return json.load(open(ROSTER_FILE, encoding="utf-8"))


def _probe_halt():
    """The probe's hang-up lever: let the first tool_use block stream
    to completion, drop the line at whatever starts next."""
    seen = []

    def halt(cb):
        if seen:
            return True
        if cb.get("type") == "tool_use":
            seen.append(cb)
        return False

    return halt


def dry_run(
    system_text,
    user_text,
    tools=None,
    model=bare_runner.DEFAULT_MODEL,
    effort=bare_runner.DEFAULT_EFFORT,
    probe=True,
    max_tokens=None,
    thinking=None,
    timeout=1200,
):
    """One stopped-at-reasoning rollout. Returns {verdict, thoughts,
    cochannel_calls, first_action, probe_thoughts,
    native_thinking_tokens, output_tokens, session_id, rounds};
    verdict "ok" iff round 1 delivered the forced think call with 0
    thinking tokens billed. `tools` is the target environment's
    roster, declared verbatim alongside think; None means
    default_roster() — the shipped Claude Code capture — and [] a
    bare dry run. first_action is None when unprobed, {name, input}
    of the first complete call, or {"none": reason}. rounds are the
    raw stream_round results, usage included, for audit."""
    roster = [think.THINK] + (default_roster() if tools is None
                              else list(tools))
    body, sid = bare_runner.build_body(
        system_text,
        user_text,
        model,
        effort,
        max_tokens=max_tokens,
        thinking=thinking,
        tools=roster,
        tool_choice={"type": "tool", "name": think.THINK["name"]},
    )

    def summary(verdict, rounds, thoughts=None, cochannel=None,
                first_action=None, probe_thoughts=None):
        return {
            "verdict": verdict,
            "thoughts": thoughts,
            "cochannel_calls": cochannel or [],
            "first_action": first_action,
            "probe_thoughts": probe_thoughts,
            "native_thinking_tokens": sum(
                think.native_tokens(r) for r in rounds
            ),
            "output_tokens": sum(
                (r["usage"].get("output_tokens") or 0) for r in rounds
            ),
            "session_id": sid,
            "rounds": rounds,
        }

    r1 = bare_runner.stream_round(body, halt=think.halt_native,
                                  timeout=timeout)
    bad = think.bad_round(r1, think.THINK["name"])
    if bad:
        return summary("%s (round 1)" % bad, [r1])
    thoughts = think.thoughts_text(r1["tool_calls"])
    cochannel = [
        {"name": c["name"], "input": c["input"]}
        for c in r1["tool_calls"]
        if c["name"] != think.THINK["name"]
    ]

    first_action, probe_thoughts, rounds = None, None, [r1]
    if probe:
        body2, _ = bare_runner.build_body(
            system_text,
            None,
            model,
            effort,
            max_tokens=max_tokens,
            thinking=thinking,
            tools=roster,
            tool_choice={"type": "any"},
            messages=body["messages"] + think.acknowledged(r1["tool_calls"]),
            session_id=sid,
        )
        r2 = bare_runner.stream_round(body2, halt=_probe_halt(),
                                      timeout=timeout)
        rounds.append(r2)
        first = r2["tool_calls"][:1]  # only the first block is complete
        if first and first[0]["name"] != think.THINK["name"]:
            first_action = {"name": first[0]["name"],
                            "input": first[0]["input"]}
        elif first:
            first_action = {"none": "think"}
            probe_thoughts = think.thoughts_text(first)
        else:
            first_action = {
                "none": r2["stop_reason"] or "http %d" % r2["status"]
            }
    return summary("ok", rounds, thoughts=thoughts, cochannel=cochannel,
                   first_action=first_action, probe_thoughts=probe_thoughts)


def _cli():
    import argparse

    ap = argparse.ArgumentParser(
        description="Stopped-at-reasoning dry run; prints the result "
        "dict as JSON."
    )
    ap.add_argument("--system-prompt-file", required=True)
    ap.add_argument(
        "--tools-file",
        default=None,
        help="JSON list of the target environment's tool definitions, "
        "declared verbatim alongside think; omitted = the shipped "
        "Claude Code roster (the dated roster-claude-code-* capture)",
    )
    ap.add_argument("--model", default=bare_runner.DEFAULT_MODEL)
    ap.add_argument("--effort", default=bare_runner.DEFAULT_EFFORT)
    ap.add_argument("--max-tokens", type=int, default=None)
    ap.add_argument(
        "--no-probe",
        action="store_true",
        help="round 1 only: skip the first-intended-action probe",
    )
    ap.add_argument(
        "--no-thinking",
        action="store_true",
        help="send the CLI's disabled-thinking shape (needed to force "
        "tool_choice on the 4.5 family; defeats the 0-thinking claim)",
    )
    ap.add_argument("--timeout", type=int, default=1200)
    ap.add_argument(
        "user_text",
        nargs="?",
        default=None,
        help="user turn; read from stdin when omitted",
    )
    a = ap.parse_args()
    if not os.path.exists(a.system_prompt_file):
        raise SystemExit("system prompt file missing: %s"
                         % a.system_prompt_file)
    user_text = a.user_text if a.user_text is not None else sys.stdin.read()
    tools = (
        json.load(open(a.tools_file, encoding="utf-8"))
        if a.tools_file
        else None
    )
    r = dry_run(
        open(a.system_prompt_file, encoding="utf-8").read(),
        user_text,
        tools=tools,
        model=a.model,
        effort=a.effort,
        probe=not a.no_probe,
        max_tokens=a.max_tokens,
        thinking=False if a.no_thinking else None,
        timeout=a.timeout,
    )
    json.dump(r, sys.stdout, indent=1)
    sys.stdout.write("\n")
    sys.exit(0 if r["verdict"] == "ok" else 1)


if __name__ == "__main__":
    _cli()
