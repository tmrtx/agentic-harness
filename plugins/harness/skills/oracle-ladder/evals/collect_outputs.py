#!/usr/bin/env python3
"""Collect a finished run's outputs from its sandbox into a run directory.

Grabs: answer.md, changes.diff (working tree + commits vs the `base` tag the
builder leaves), commit messages beyond base, per-case collected files
(evals.json `collect`), and new untracked files. Judges and code graders see
outputs/; the mutated sandbox itself stays on disk for check_artifacts.py.

Usage: python3 collect_outputs.py --sandbox <dir> --eval-id N --dest <run-dir>
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent

TIERS = {
    "courier": ("evals.json", "KEY.md"),
    "plugin": ("evals-plugin.json", "KEY-plugin.md"),
}


def sh(cwd, *cmd):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True).stdout


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--sandbox", type=Path, required=True)
    ap.add_argument("--eval-id", type=int, required=True)
    ap.add_argument("--dest", type=Path, required=True, help="run dir; outputs/ created inside")
    ap.add_argument("--tier", choices=sorted(TIERS), default="courier",
                    help="stratum: courier (transfer) or plugin (headline)")
    args = ap.parse_args()

    spec = next(e for e in json.loads((EVALS_DIR / TIERS[args.tier][0]).read_text())["evals"]
                if e["id"] == args.eval_id)
    out = args.dest / "outputs"
    out.mkdir(parents=True, exist_ok=True)
    sb = args.sandbox

    diff = sh(sb, "git", "diff", "base") or "(no tracked changes vs base)\n"
    (out / "changes.diff").write_text(diff)

    msgs = sh(sb, "git", "log", "base..HEAD", "--format=%B%n---%n")
    if msgs.strip():
        (out / "commit-message.txt").write_text(msgs)

    for rel in ["answer.md", *spec.get("collect", [])]:
        src = sb / rel
        if src.exists() and rel != "commit-message.txt":
            dest = out / Path(rel).name
            dest.write_text(src.read_text())

    untracked = sh(sb, "git", "ls-files", "--others", "--exclude-standard").split()
    for rel in untracked:
        if rel.startswith(".claude/") or rel == "answer.md":
            continue
        src = sb / rel
        dest = out / "untracked" / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            dest.write_text(src.read_text())
        except (UnicodeDecodeError, OSError):
            shutil.copy2(src, dest)

    print(f"collected {args.dest}/outputs: "
          f"{', '.join(sorted(p.name for p in out.iterdir()))}")


if __name__ == "__main__":
    main()
