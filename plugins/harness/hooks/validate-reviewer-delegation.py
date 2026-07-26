"""PreToolUse gate: the reviewer subagent takes governance codes, nothing else.

The reviewer's contract (agents/reviewer.md) is that a delegation carries only
a comma-separated list of governance codes — or nothing, for full coverage —
because any other prose is the author of the work framing their own review.
This gate makes that contract deterministic instead of advisory: a delegation
to the reviewer whose prompt is not in the accepted grammar is denied, and the
deny reason teaches the caller how to re-delegate.

The gate fails closed. When it cannot read the payload it cannot tell whose
delegation it is judging, so it exits 2 — the one code PreToolUse treats as
blocking — and the launch is held until the gate is fixed. Enforcement
failures must surface as breakage that prompts a repair, never as a silent
bypass of review.
"""
import json
import re
import sys

# Bare "reviewer" is gated too: a delegation can reach this agent without the
# plugin namespace, and closing that bypass is worth the collision with a
# consumer-local agent that happens to shadow the name. Case-insensitive for
# the same reason: the gate must not hinge on how the caller cased the name.
REVIEWER = re.compile(r"(harness:)?reviewer\Z", re.IGNORECASE)
# A comma-separated list of governance codes (`CIA-7`, `CIA-8.2`, ...),
# or blank / the literal phrase "full coverage" to run every phase.
CODES_ONLY = re.compile(
    r"\s*(CIA-\d+(\.\d+)?(\s*,\s*CIA-\d+(\.\d+)?)*|full\s+coverage)?\s*\Z",
    re.IGNORECASE,
)

DENY_REASON = (
    "Blocked by harness policy: the reviewer takes only a comma-separated "
    "list of governance codes as its delegation prompt — e.g. 'CIA-7,CIA-8' "
    "or 'CIA-7.3' — or 'full coverage' (or an empty prompt) to run every "
    "phase. It derives the diff and its intent from the repository itself; "
    "summaries, file pointers, or notes on what was already checked let the "
    "author frame their own review, so they are rejected rather than "
    "forwarded. Re-delegate with the codes alone."
)


def main():
    try:
        tool_input = json.load(sys.stdin).get("tool_input") or {}
        subagent = tool_input.get("subagent_type") or ""
        if not subagent:
            # every call on the matched tools is a subagent launch, so a
            # payload with no readable agent identity is a payload this
            # gate cannot judge — not a payload outside its jurisdiction
            raise ValueError("no readable subagent_type in tool_input")
        if not REVIEWER.fullmatch(subagent):
            return
        prompt = tool_input.get("prompt") or ""
        conforms = bool(CODES_ONLY.fullmatch(prompt))
    except Exception as exc:
        print(
            "reviewer delegation gate failed (%s: %s); blocking the launch "
            "until the gate is fixed" % (type(exc).__name__, exc),
            file=sys.stderr,
        )
        sys.exit(2)
    if conforms:
        return
    print(
        json.dumps(
            {
                "hookSpecificOutput": {
                    "hookEventName": "PreToolUse",
                    "permissionDecision": "deny",
                    "permissionDecisionReason": DENY_REASON,
                }
            }
        )
    )


if __name__ == "__main__":
    main()
