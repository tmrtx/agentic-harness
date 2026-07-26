#!/usr/bin/env python3
"""Code-graded assertions for the oracle-ladder skill's recording artifacts.

The mechanical half of the skill's expectations is a total function of the
artifacts at rest: a commit body either carries the `[ORACLE]` section or it
does not, the trailer either parses or it does not, the ledger either grew by
an append or it was rewritten. Judging that by eye across dozens of runs is
slow and drifts between graders, so this checker owns those verdicts and the
LLM grader is left with the questions that actually need judgment.

The trailer regex here is deliberately the same one the shipped commit-shape
gate uses. If the two ever disagree, the eval would be grading a contract the
repository does not enforce.

Usage:
    python3 check_record.py --outputs <run>/outputs \\
        --baseline-ledger <path/to/oracles.jsonl before the run> \\
        --expect-class 'principal' --expect-ground-truth 'principal' \\
        --require-commit

Prints a JSON object: {"checks": [{"text", "passed", "evidence"}, ...]}
Exit status is 0 whenever the checker ran, whatever the verdicts — a failing
assertion is data, not a checker error.
"""

import argparse
import json
import re
import sys
from pathlib import Path

RUNGS = {"intrinsic", "static", "runtime", "statistical", "experimental", "principal"}
GROUND_TRUTHS = {"specified", "derived", "implicit", "principal"}
LEDGER_KEYS = {"since", "oracle", "oracle-class", "ground-truth", "target", "justification"}

# Same shape the commit-shape gate enforces (plugins/harness/hooks/commit-shape-gate.py).
SECTION_RE = re.compile(r"^\[ORACLE\]\s*$", re.M)
TRAILER_RE = re.compile(r"^Oracle: \[([^|\]\s]+)\|([^|\]\s]+)\]\s*$", re.M)
ORC_RE = re.compile(r"\bORC-\d+\b")


def base_rung(value: str) -> str:
    """Strip a tag: `principal:tacit` places on the `principal` rung."""
    return value.split(":", 1)[0]


class Checks:
    def __init__(self) -> None:
        self.items: list[dict] = []

    def add(self, text: str, passed: bool, evidence: str) -> None:
        self.items.append({"text": text, "passed": bool(passed), "evidence": evidence[:600]})


def read(path: Path) -> str | None:
    try:
        return path.read_text()
    except OSError:
        return None


def check_commit(checks: Checks, body: str | None, expect_class: str | None,
                 expect_ground_truth: str | None, state: dict | None) -> None:
    if body is None:
        checks.add("A commit was made", False, "no commit-message.txt in outputs/")
        return
    checks.add("A commit was made", True, f"commit body captured, {len(body.splitlines())} lines")

    section = SECTION_RE.search(body)
    checks.add("Commit body carries an [ORACLE] section header on its own line",
               bool(section), "found" if section else f"no [ORACLE] line in:\n{body[:300]}")

    trailer = TRAILER_RE.search(body)
    checks.add("Commit carries a well-formed Oracle: [<class>|<ground-truth>] trailer",
               bool(trailer), trailer.group(0) if trailer else "no trailer matching the gate's regex")

    if trailer:
        cls, gt = trailer.group(1), trailer.group(2)
        checks.add("Trailer oracle-class is one of the six rungs",
                   base_rung(cls) in RUNGS, f"class={cls}")
        checks.add("Trailer ground-truth is one of the four sources",
                   base_rung(gt) in GROUND_TRUTHS, f"ground-truth={gt}")
        if expect_class:
            ok = base_rung(cls) == expect_class
            checks.add(f"Oracle class is `{expect_class}` (the rung this change actually admits)",
                       ok, f"got {cls}, expected {expect_class}")
        if expect_ground_truth:
            ok = base_rung(gt) == expect_ground_truth
            checks.add(f"Ground truth is `{expect_ground_truth}`", ok,
                       f"got {gt}, expected {expect_ground_truth}")

    if section:
        tail = body[section.end():]
        labels = {"Class": r"^\s*Class:", "Ground truth": r"^\s*Ground[- ]truth:",
                  "Mechanism": r"^\s*Mechanism:", "Oracle": r"^\s*Oracle:"}
        missing = [k for k, pat in labels.items() if not re.search(pat, tail, re.M | re.I)]
        checks.add("[ORACLE] section has all four labeled lines (Class, Ground truth, Mechanism, Oracle)",
                   not missing, "complete" if not missing else f"missing: {', '.join(missing)}")

        cited = ORC_RE.findall(tail)
        if state is not None:
            ok = bool(cited) and any(c in state for c in cited)
            checks.add("[ORACLE] section cites an ORC code that exists in oracle-state.json",
                       ok, f"cited={cited or 'none'}, state has {sorted(state)}")

    protocol = [s for s in ("[PROBLEM]", "[ROOT-CAUSE]", "[CHANGE]") if s not in body]
    checks.add("Oracle recording did not displace the commit protocol's other body sections",
               not protocol, "all present" if not protocol else f"missing: {', '.join(protocol)}")


def check_ledger(checks: Checks, ledger_text: str | None, baseline_text: str,
                 state: dict | None, expect_class: str | None) -> None:
    if ledger_text is None:
        checks.add("Ledger (oracles.jsonl) captured in outputs", False, "file absent")
        return

    baseline = [l for l in baseline_text.splitlines() if l.strip()]
    lines = [l for l in ledger_text.splitlines() if l.strip()]

    checks.add("A ledger line was appended for this change",
               len(lines) > len(baseline), f"{len(baseline)} lines before, {len(lines)} after")

    kept = lines[:len(baseline)] == baseline
    checks.add("The ledger stayed append-only (existing snapshots untouched)",
               kept, "prior lines byte-identical" if kept else "a pre-existing ledger line was rewritten")

    bad = [l for l in lines if not _parses(l)]
    checks.add("Every ledger line is valid JSON", not bad,
               "all parse" if not bad else f"{len(bad)} line(s) fail to parse, e.g. {bad[0][:160]}")

    new = [json.loads(l) for l in lines[len(baseline):] if _parses(l)]
    if new:
        entry = new[-1]
        missing = sorted(LEDGER_KEYS - set(entry))
        checks.add("The new ledger line carries every required field",
                   not missing, "complete" if not missing else f"missing: {', '.join(missing)}")
        cls = base_rung(str(entry.get("oracle-class", "")))
        gt = base_rung(str(entry.get("ground-truth", "")))
        checks.add("The new ledger line's class and ground-truth are drawn from the ladder's vocabulary",
                   cls in RUNGS and gt in GROUND_TRUTHS,
                   f"oracle-class={entry.get('oracle-class')}, ground-truth={entry.get('ground-truth')}")
        if expect_class:
            checks.add(f"The new ledger line records class `{expect_class}`",
                       cls == expect_class, f"got {entry.get('oracle-class')}")
        if state is not None:
            code = str(entry.get("oracle", ""))
            checks.add("The new ledger line cites an oracle code that exists in oracle-state.json",
                       code in state, f"cites {code or 'nothing'}, state has {sorted(state)}")


def _parses(line: str) -> bool:
    try:
        json.loads(line)
        return True
    except json.JSONDecodeError:
        return False


def check_state(checks: Checks, state: dict | None, raw: str | None) -> None:
    if raw is None:
        checks.add("State (oracle-state.json) captured in outputs", False, "file absent")
        return
    if state is None:
        checks.add("oracle-state.json is valid JSON", False, raw[:200])
        return
    required = {"oracle-class", "ground-truth", "since", "subject", "mechanism"}
    broken = {k: sorted(required - set(v)) for k, v in state.items()
              if isinstance(v, dict) and required - set(v)}
    checks.add("Every oracle-state.json entry carries class, ground-truth, since, subject, mechanism",
               not broken, "all complete" if not broken else f"incomplete: {broken}")


def check_answer_trailer(checks: Checks, answer: str | None, expect_class: str | None,
                         expect_ground_truth: str | None) -> None:
    """For advice-shaped evals: the answer must hand over a usable trailer.

    The class assertions only fire when the eval declares an expected value.
    Some questions admit more than one correct trailer — the oracle that
    verifies the commit is not always the oracle of the thing the commit
    installs — and a checker that insists on one string would fail a right
    answer for being right in the other way. Those evals leave the expectation
    unset and let the judge grade internal consistency instead.
    """
    if answer is None:
        checks.add("An answer was produced", False, "no answer.md in outputs/")
        return
    trailer = TRAILER_RE.search(answer)
    loose = re.search(r"Oracle:\s*\[\s*([a-z:]+)\s*\|\s*([a-z:]+)\s*\]", answer)
    m = trailer or loose
    checks.add("The answer hands over a well-formed Oracle: [<class>|<ground-truth>] trailer",
               bool(m), m.group(0) if m else "no trailer offered in the answer")
    if not m:
        return
    cls, gt = base_rung(m.group(1)), base_rung(m.group(2))
    checks.add("The trailer it hands over uses a real rung and a real ground-truth source",
               cls in RUNGS and gt in GROUND_TRUTHS, m.group(0))
    if expect_class:
        checks.add(f"The trailer it hands over classifies the change as `{expect_class}`",
                   cls == expect_class, f"got {m.group(1)}")
    if expect_ground_truth:
        checks.add(f"The trailer it hands over records ground truth `{expect_ground_truth}`",
                   gt == expect_ground_truth, f"got {m.group(2)}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--outputs", type=Path, required=True)
    ap.add_argument("--baseline-ledger", type=Path)
    ap.add_argument("--expect-class")
    ap.add_argument("--expect-ground-truth")
    ap.add_argument("--require-commit", action="store_true")
    ap.add_argument("--answer-trailer", action="store_true",
                    help="grade the trailer offered in answer.md instead of a commit")
    args = ap.parse_args()

    out = args.outputs
    checks = Checks()

    raw_state = read(out / "oracle-state.json")
    try:
        state = json.loads(raw_state) if raw_state else None
    except json.JSONDecodeError:
        state = None

    if args.require_commit:
        check_commit(checks, read(out / "commit-message.txt"), args.expect_class,
                     args.expect_ground_truth, state)
        if args.baseline_ledger:
            check_ledger(checks, read(out / "oracles.jsonl"),
                         args.baseline_ledger.read_text(), state, args.expect_class)
        check_state(checks, state, raw_state)

    if args.answer_trailer:
        check_answer_trailer(checks, read(out / "answer.md"),
                             args.expect_class or "", args.expect_ground_truth or "")

    passed = sum(c["passed"] for c in checks.items)
    print(json.dumps({
        "checks": checks.items,
        "summary": {"passed": passed, "failed": len(checks.items) - passed, "total": len(checks.items)},
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
