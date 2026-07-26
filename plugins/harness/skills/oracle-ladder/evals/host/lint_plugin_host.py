#!/usr/bin/env python3
"""Contamination lint for the `quill` sandbox and its case prompts.

Sibling of lint_host.py, not a replacement: `courier` keeps its over-broad
denylist. That list is unusable here. `quill`'s product is a Claude Code
plugin, so `hook`, `matcher`, `PreToolUse`, `permission`, `settings`, `deny`,
`kill switch` and `exit code` are the repository's own vocabulary — banning
them would mean the host could not be written at all, and writing around them
would produce a repository no plugin team would recognize.

So the boundary moves. What has to be absent is not tooling vocabulary but
two other things:

  1. anything that names or paraphrases the skill under measurement — its
     name, its levels, its recording artifacts, its section markers;
  2. anything that tells a reader a measurement is happening.

Hence a narrowed token list, plus one set rule. The six level names are each
ordinary English on their own ("a static check", "at runtime", "the principal
maintainer"), so banning them outright would be as unusable as the courier
list. Three or more of them in a single file is not ordinary English — it is
the ladder, spelled out. That is what fails.

Usage:
    python3 lint_plugin_host.py <sandbox-dir> [...]        # walk tree + git log
    python3 lint_plugin_host.py --prompts <evals-plugin.json>
Exit 0 = clean. Any hit prints file:line and exits 1.

`.git/` internals are skipped; commit messages are scanned via git log.
`.claude/skills/oracle-ladder/` is skipped because the with-skill arm
legitimately carries the skill there — but the rest of `.claude/` IS scanned,
unlike in lint_host.py, because this host's own governance lives in it and is
therefore host content like any other file.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

# Names the skill, its exhaust, or the fact of a measurement.
TOKENS = [
    "oracle",           # covers oracle-state.json, oracles.jsonl, [ORACLE]
    "orc-",
    "rung",
    "ladder",
    "ground truth",
    "ground-truth",
    "oracle-state.json",
    "oracles.jsonl",
    "[oracle]",
    "eval",             # also catches evaluate/evaluation: intentional
    "ablation",
    "baseline",
]
PATTERN = re.compile("|".join(re.escape(t) for t in TOKENS), re.IGNORECASE)

# Each of these is ordinary English alone. Three together is the ladder.
LEVEL_SET = ["intrinsic", "static", "runtime", "statistical",
             "experimental", "principal"]
LEVEL_PATTERNS = [(t, re.compile(re.escape(t), re.IGNORECASE)) for t in LEVEL_SET]
LEVEL_LIMIT = 3

SKIP_TOP = (".git",)
SKIP_PATHS = (("`.claude`", ".claude", "skills", "oracle-ladder"),)


def scan_text(label: str, text: str) -> list[str]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        m = PATTERN.search(line)
        if m:
            hits.append(label + ":" + str(n) + ": '" + m.group(0)
                        + "' in: " + line.strip()[:100])
    return hits


def scan_level_set(label: str, text: str) -> list[str]:
    """Fail a file that co-locates LEVEL_LIMIT or more of the level names."""
    present = [t for t, p in LEVEL_PATTERNS if p.search(text)]
    if len(present) >= LEVEL_LIMIT:
        return [label + ": " + str(len(present)) + " level names co-occur ("
                + ", ".join(present) + "); " + str(LEVEL_LIMIT)
                + " or more in one file fails"]
    return []


def skipped(parts: tuple[str, ...]) -> bool:
    if parts and parts[0] in SKIP_TOP:
        return True
    for _, *prefix in SKIP_PATHS:
        if list(parts[:len(prefix)]) == prefix:
            return True
    return False


def scan_dir(root: Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        rel = path.relative_to(root)
        if skipped(rel.parts) or path.is_dir():
            continue
        text = path.read_text(errors="replace")
        hits.extend(scan_text(str(rel), text))
        hits.extend(scan_level_set(str(rel), text))
        m = PATTERN.search(path.name)
        if m:
            hits.append(str(rel) + ": filename contains '" + m.group(0) + "'")
    if (root / ".git").exists():
        log = subprocess.run(["git", "log", "--format=%H %B"], cwd=root,
                             capture_output=True, text=True).stdout
        hits.extend(scan_text("git-log", log))
        for sha_block in log.split("\n\n"):
            if sha_block.strip():
                hits.extend(scan_level_set("git-log", sha_block))
    return hits


def scan_prompts(path: Path) -> list[str]:
    hits = []
    data = json.loads(path.read_text())
    for case in data.get("evals", []):
        label = "prompt[" + str(case.get("name", case.get("id"))) + "]"
        prompt = case.get("prompt", "")
        hits.extend(scan_text(label, prompt))
        hits.extend(scan_level_set(label, prompt))
    return hits


def main() -> int:
    args = sys.argv[1:]
    hits: list[str] = []
    checked: list[str] = []
    while args:
        arg = args.pop(0)
        if arg == "--prompts":
            target = Path(args.pop(0))
            hits.extend(scan_prompts(target))
            checked.append("prompts:" + target.name)
        else:
            target = Path(arg)
            hits.extend(scan_dir(target))
            checked.append(str(target))
    for h in hits:
        print(h)
    print("lint: " + str(len(hits)) + " hit(s) across " + ", ".join(checked))
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
