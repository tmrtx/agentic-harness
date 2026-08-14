#!/usr/bin/env python3
"""Reasoning as a tool call — the forced two-round scheme.

Distilled from the 2026-08-13 deep-think experiments (claude-opus-5
and claude-fable-5): the model's private reasoning pass — billed as
thinking tokens, never shown — moves into an ordinary tool call,
where it becomes text you hold: loggable, auditable, measurable,
feedable to other systems. Confirmed runs billed 0 thinking tokens
with reasoning volume on par with native thinking; the reasoning is
not free — the same volume bills as ordinary output tokens, plus a
second request. The shipped tool is named `think` and carries no
description (see the note above THINK).

The scheme. Both rounds FORCE the channel with tool_choice — unforced,
opus never chose the tool on the production request (5/5 draws) and
fable abandoned it on the hard problem (3/3); forced rounds opened
with the tool call 23/23:

 round 1  tools=[think, write_answer], tool_choice→think:
          the reasoning arrives as the calls' `thoughts` input
          (parallel calls all count and join).
 round 2  tool result "Acknowledged.", tool_choice→write_answer:
          the answer arrives as the call's input.

Typed answers: pass answer_fields=("premise", ...) and the fields
become write_answer's input schema — NOT output_config.format, which
fable refuses after a reasoning-tool call (4/4 draws: HTTP 200,
stop_reason "refusal", zero content). Tool input schemas were never
refused (~30/30 tool-call responses).

Guard rails, all wired in:
 - a native thinking block aborts the round at its first streamed
   block — 2-5 tokens spent, verdict "native-thinking";
 - stop_reason "refusal" becomes the verdict, never silence;
 - closing check: billed thinking_tokens must be 0 on every round.
Thinking stays ENABLED (the family default) in every request: a
billed 0 means the model chose the tool, not that the private pass
was disabled. Caveat: the API rejects forced tool_choice under the
4.5 family's enabled-thinking shape — pass thinking=False there for
plumbing tests; the scheme's claims are 5-family.

CLI:
    python3 think.py --system-prompt-file sys.txt "user text"
    ... --answer-fields premise,reflection,answer
Prints the result dict as JSON; exits 0 iff verdict == "ok".
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bare_runner  # noqa: E402

# The reasoning tool carries NO description: any description is
# steering text riding along with every request, and the forced scheme
# does not need one — forcing, not wording, makes the model use the
# tool, wording impacts how it does it.
#
# The NAME is the one remaining steering surface, and it was swept
# (2026-08-14, fable, description-less, Frobenius probe): think,
# deep_think, extended_thinking, ultrathink, deliberate, reason,
# think_hard. Two findings held; one did not. Held: `reason` is
# refused outright 3/3 — the refusal boundary reaches bare names; and
# `think` is the most volume-stable name tested (sd ~70 on ~1,000
# reasoning tokens, n=7). Did not hold: `extended_thinking`'s apparent
# depth premium (~+31% mean on fable) came with 4x the draw variance
# (857-1788 vs think's 917-1126), an unstable mean between batches,
# and an inverted ordering on opus; answer volume and correctness were
# flat across all names. `think` stays — per-draw depth is not
# reliably purchasable by naming.
THINK = {
    "name": "think",
    "input_schema": {
        "type": "object",
        "properties": {"thoughts": {"type": "string"}},
        "required": ["thoughts"],
        "additionalProperties": False,
    },
}


def write_answer_tool(answer_fields=None):
    """The delivery tool; answer_fields turns its input schema into the
    answer template (the refusal-free replacement for structured
    output)."""
    fields = list(answer_fields or ["answer"])
    return {
        "name": "write_answer",
        "description": "Deliver your complete final answer to the user.",
        "input_schema": {
            "type": "object",
            "properties": {f: {"type": "string"} for f in fields},
            "required": fields,
            "additionalProperties": False,
        },
    }


def _halt_native(cb):
    return cb.get("type") in ("thinking", "redacted_thinking")


def _native(r):
    return ((r["usage"].get("output_tokens_details") or {}).get("thinking_tokens")) or 0


def _bad(r, tool):
    """The failure shapes, in check order: transport, the private pass
    (streamed or billed), refusal, a missing forced call."""
    if r["status"] != 200:
        return "http %d" % r["status"]
    if r["stop_reason"] == "halted" or _native(r):
        return "native-thinking"
    if r["stop_reason"] == "refusal":
        return "refusal"
    if not any(c["name"] == tool for c in r["tool_calls"]):
        return "stop %s, no %s call" % (r["stop_reason"], tool)
    return None


def probe(body, timeout=600):
    """The 2-5-token channel check: stream until the FIRST content
    block, hang up, report (channel, name) — ("thinking", None) means
    the model went to the private pass, ("tool_use", "think")
    means the scheme holds, ("refusal", None) means zero content.
    tool_choice never appears in the recorded conversation, so any
    single round can be probed alone against a reconstructed history."""
    first = []
    r = bare_runner.stream_round(
        body, halt=lambda cb: first.append(cb) or True, timeout=timeout
    )
    if first:
        return first[0].get("type"), first[0].get("name")
    return r["stop_reason"] or "http %d" % r["status"], None


def run(
    system_text,
    user_text,
    model=bare_runner.DEFAULT_MODEL,
    effort=bare_runner.DEFAULT_EFFORT,
    answer_fields=None,
    max_tokens=None,
    thinking=None,
    timeout=1200,
):
    """The two-round forced scheme. Returns {verdict, thoughts, answer,
    native_thinking_tokens, output_tokens, session_id, rounds};
    verdict "ok" iff both rounds delivered their forced call with 0
    thinking tokens billed. answer is the `answer` string, or the full
    input dict when answer_fields names the sections. rounds are the
    raw stream_round results, usage included, for audit."""
    tools = [THINK, write_answer_tool(answer_fields)]

    def build(tool, messages=None, sid=None):
        return bare_runner.build_body(
            system_text,
            user_text,
            model,
            effort,
            max_tokens=max_tokens,
            thinking=thinking,
            tools=tools,
            tool_choice={"type": "tool", "name": tool},
            messages=messages,
            session_id=sid,
        )

    def summary(verdict, rounds, thoughts=None, answer=None):
        return {
            "verdict": verdict,
            "thoughts": thoughts,
            "answer": answer,
            "native_thinking_tokens": sum(_native(r) for r in rounds),
            "output_tokens": sum(
                (r["usage"].get("output_tokens") or 0) for r in rounds
            ),
            "session_id": rounds[0]["session_id"],
            "rounds": rounds,
        }

    body, sid = build(THINK["name"])
    r1 = bare_runner.stream_round(body, halt=_halt_native, timeout=timeout)
    bad = _bad(r1, THINK["name"])
    if bad:
        return summary("%s (round 1)" % bad, [r1])
    # The model may emit several reasoning calls in one response; keep
    # them all and replay the transcript it actually produced.
    calls = [c for c in r1["tool_calls"] if c["name"] == THINK["name"]]
    thoughts = "\n\n".join(c["input"].get("thoughts") or "" for c in calls)

    messages = body["messages"] + [
        {"role": "assistant", "content": calls},
        {
            "role": "user",
            "content": [
                {
                    "type": "tool_result",
                    "tool_use_id": c["id"],
                    "content": "Acknowledged.",
                }
                for c in calls
            ],
        },
    ]
    body2, _ = build("write_answer", messages=messages, sid=sid)
    r2 = bare_runner.stream_round(body2, halt=_halt_native, timeout=timeout)
    bad = _bad(r2, "write_answer")
    if bad:
        return summary("%s (round 2)" % bad, [r1, r2], thoughts=thoughts)
    inp = next(c for c in r2["tool_calls"] if c["name"] == "write_answer")["input"]
    answer = inp if answer_fields else inp.get("answer")
    return summary("ok", [r1, r2], thoughts=thoughts, answer=answer)


def _cli():
    import argparse

    ap = argparse.ArgumentParser(
        description="Forced think-tool scheme; prints the result dict as JSON."
    )
    ap.add_argument("--system-prompt-file", required=True)
    ap.add_argument("--model", default=bare_runner.DEFAULT_MODEL)
    ap.add_argument("--effort", default=bare_runner.DEFAULT_EFFORT)
    ap.add_argument(
        "--answer-fields",
        default=None,
        help="comma-separated section names; they become "
        "write_answer's input schema and the answer arrives typed",
    )
    ap.add_argument("--max-tokens", type=int, default=None)
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
        raise SystemExit("system prompt file missing: %s" % a.system_prompt_file)
    user_text = a.user_text if a.user_text is not None else sys.stdin.read()
    fields = (
        [f.strip() for f in a.answer_fields.split(",")] if a.answer_fields else None
    )
    r = run(
        open(a.system_prompt_file, encoding="utf-8").read(),
        user_text,
        model=a.model,
        effort=a.effort,
        answer_fields=fields,
        max_tokens=a.max_tokens,
        thinking=False if a.no_thinking else None,
        timeout=a.timeout,
    )
    json.dump(r, sys.stdout, indent=1)
    sys.stdout.write("\n")
    sys.exit(0 if r["verdict"] == "ok" else 1)


if __name__ == "__main__":
    _cli()
