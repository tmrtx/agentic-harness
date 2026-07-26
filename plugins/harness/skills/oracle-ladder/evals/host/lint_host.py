#!/usr/bin/env python3
"""Contamination lint for the courier sandbox and the capability prompts.

Purpose 1 of this suite's design is "no contamination path": the baseline arm
must not be able to reconstruct the skill from its environment, and must not
be able to detect that anything was removed. The host is synthetic, so the
guarantee is enforceable mechanically: no file in the sandbox, no commit
message in its history, and no case prompt may contain the skill's vocabulary
or anything evaluation-shaped.

The token list is deliberately over-broad ("static", "runtime", "skill",
"eval" are ordinary words). That is affordable because every byte of the host
is authored here; an accidental hit during future editing should fail loudly
and be rewritten around, not waved through.

Usage:
    python3 lint_host.py <sandbox-dir> [...]      # walk tree + git log
    python3 lint_host.py --prompts <evals.json>   # scan case prompts
Exit 0 = clean. Any hit prints file:line and exits 1.

`.claude/` is skipped: the with-skill arm legitimately carries the skill
there. `.git/` internals are skipped; commit messages are scanned via git log.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

TOKENS = [
    "oracle", "orc-", "rung", "ladder", "intrinsic",
    "ground truth", "ground-truth", "principal", "specified", "derived",
    "statistical", "experimental", "static", "runtime",
    "skill", "eval", "governance", "expectation", "ablation", "baseline",
]
PATTERN = re.compile("|".join(re.escape(t) for t in TOKENS), re.IGNORECASE)


def scan_text(label: str, text: str) -> list[str]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        m = PATTERN.search(line)
        if m:
            hits.append(f"{label}:{n}: '{m.group(0)}' in: {line.strip()[:100]}")
    return hits


def scan_dir(root: Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        parts = rel.parts
        if parts and parts[0] in (".git", ".claude"):
            continue
        if path.is_dir():
            continue
        hits.extend(scan_text(str(rel), path.read_text(errors="replace")))
        m = PATTERN.search(path.name)
        if m:
            hits.append(f"{rel}: filename contains '{m.group(0)}'")
    if (root / ".git").exists():
        log = subprocess.run(["git", "log", "--format=%H %B"], cwd=root,
                             capture_output=True, text=True).stdout
        hits.extend(scan_text("git-log", log))
    return hits


def scan_prompts(path: Path) -> list[str]:
    hits = []
    data = json.loads(path.read_text())
    for case in data.get("evals", []):
        label = f"prompt[{case.get('name', case.get('id'))}]"
        hits.extend(scan_text(label, case.get("prompt", "")))
    return hits


def main() -> int:
    args = sys.argv[1:]
    hits = []
    checked = []
    while args:
        arg = args.pop(0)
        if arg == "--prompts":
            target = Path(args.pop(0))
            hits.extend(scan_prompts(target))
            checked.append(f"prompts:{target.name}")
        else:
            target = Path(arg)
            hits.extend(scan_dir(target))
            checked.append(str(target))
    for h in hits:
        print(h)
    print(f"lint: {len(hits)} hit(s) across {', '.join(checked)}")
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
