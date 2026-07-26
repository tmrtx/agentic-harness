#!/usr/bin/env python3
"""Stage each run's outputs under an opaque id so judges grade blind.

For every eval-*/<config>/run-* with outputs, creates
<iteration>/../_blind-<iteration>/submission-<token>/ holding a copy of
outputs/ and a task.json with the prompt, the [judge] decision points, and
the matching KEY.md excerpts. The token is salted with the iteration name so
mappings are not stable across iterations. The manifest mapping tokens back
to runs is written next to the iteration dir; judges must not read it.

Usage: python3 stage_blind.py <iteration-dir> [--pristine <sandbox-path>]
"""
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent


def key_excerpts() -> dict[str, str]:
    """Map decision-point id -> its KEY.md entry (ranges like C1.1–C1.3 expand)."""
    text = (EVALS_DIR / "KEY.md").read_text()
    blocks: dict[str, str] = {}
    current_ids: list[str] = []
    current: list[str] = []

    def flush():
        for cid in current_ids:
            blocks[cid] = "\n".join(current).strip()

    for line in text.splitlines():
        if line.startswith("**C"):
            flush()
            header_ids = re.findall(r"C\d+\.\d+", line)
            expanded = list(header_ids)
            m = re.search(r"(C(\d+)\.(\d+))[–-](C\2\.(\d+))", line)
            if m:
                lo, hi = int(m.group(3)), int(m.group(5))
                expanded = [f"C{m.group(2)}.{i}" for i in range(lo, hi + 1)]
            current_ids, current = expanded, [line]
        elif line.startswith("## ") and current_ids:
            flush()
            current_ids, current = [], []
        elif current_ids:
            current.append(line)
    flush()
    return blocks


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("iteration", type=Path)
    ap.add_argument("--pristine", default="",
                    help="path to a pristine without-arm sandbox, given to judges as repo context")
    args = ap.parse_args()
    it = args.iteration

    evals = json.loads((EVALS_DIR / "evals.json").read_text())
    by_id = {e["id"]: e for e in evals["evals"]}
    keys = key_excerpts()

    blind = it.parent / f"_blind-{it.name}"
    if blind.exists():
        shutil.rmtree(blind)
    blind.mkdir()
    manifest = {}

    for eval_dir in sorted(it.glob("eval-*")):
        eid = int(eval_dir.name.split("-")[1])
        spec = by_id[eid]
        for cfg_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
            for run in sorted(cfg_dir.glob("run-*")):
                if not (run / "outputs").exists() or not list((run / "outputs").glob("*")):
                    continue
                token = hashlib.sha1(
                    f"{it.name}|{eid}|{cfg_dir.name}|{run.name}".encode()
                ).hexdigest()[:10]
                dest = blind / f"submission-{token}"
                shutil.copytree(run / "outputs", dest / "outputs")
                points = []
                for exp in spec["expectations"]:
                    if not exp.startswith("[judge]"):
                        continue
                    pid = exp.split()[1]
                    points.append({"id": pid, "text": exp,
                                   "key": keys.get(pid, "(no key entry — treat as underspecified, use unknown)")})
                (dest / "task.json").write_text(json.dumps({
                    "user_prompt": spec["prompt"],
                    "pristine_repo": args.pristine,
                    "decision_points": points,
                    "protocol": "see judge.md next to evals.json; vocabulary earns nothing; "
                                "unknown is available and welcome; report awareness_flags",
                }, indent=2))
                manifest[token] = {"eval_id": eid, "eval_dir": eval_dir.name,
                                   "config": cfg_dir.name, "run": run.name}

    (it.parent / f".blind-manifest-{it.name}.json").write_text(json.dumps(manifest, indent=2))
    for t, m in manifest.items():
        print(f"submission-{t}  <-  {m['eval_dir']}/{m['config']}/{m['run']}")


if __name__ == "__main__":
    main()
