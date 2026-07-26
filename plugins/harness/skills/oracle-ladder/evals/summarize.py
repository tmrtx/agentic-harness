#!/usr/bin/env python3
"""Merge code + judge verdicts into per-run grading.json, then audit the suite.

Per run:  expectations in evals.json order; [code] points from the run's
code-grading.json (written by check_artifacts.py), [judge] points from the
blind submission's grading.json. pass_rate counts decided points only;
unknowns are carried separately and reported.

Per iteration (written to discrimination.md and stdout):
  - arm-level mean pass rate over decision points (the headline)
  - per-point discrimination buckets — the suite's own health check: points
    both arms always pass are flagged for retirement, and the "skill wins /
    baseline wins" lists are the actual content of the measurement
  - per-case all-points-pass rate per arm (the pass^k view: an instruction
    has to hold every time, so the honest unit is the run where nothing
    slipped)
  - awareness flags (any is a contamination alarm), disputed verdicts,
    unknowns, and judge eval_feedback (the fairness log)

Usage: python3 summarize.py <iteration-dir>
Then:  python3 -m scripts.aggregate_benchmark <iteration-dir> (from skill-creator)
"""
import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

EVALS_DIR = Path(__file__).resolve().parent

TIERS = {
    "courier": ("evals.json", "KEY.md"),
    "plugin": ("evals-plugin.json", "KEY-plugin.md"),
}


def load_judge(it: Path, manifest: dict, eval_dir: str, config: str, run: str):
    for token, m in manifest.items():
        if (m["eval_dir"], m["config"], m["run"]) == (eval_dir, config, run):
            path = it.parent / f"_blind-{it.name}" / f"submission-{token}" / "grading.json"
            if path.exists():
                return json.loads(path.read_text())
    return None


def main():
    it = Path(sys.argv[1])
    tier = sys.argv[2] if len(sys.argv) > 2 else "courier"
    evals = json.loads((EVALS_DIR / TIERS[tier][0]).read_text())
    by_id = {e["id"]: e for e in evals["evals"]}
    manifest_path = it.parent / f".blind-manifest-{it.name}.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}

    fairness, awareness = [], []

    for eval_dir in sorted(it.glob("eval-*")):
        eid = int(eval_dir.name.split("-")[1])
        spec = by_id[eid]
        for cfg_dir in sorted(p for p in eval_dir.iterdir() if p.is_dir()):
            for run in sorted(cfg_dir.glob("run-*")):
                if not (run / "outputs").exists():
                    continue
                code_path = run / "code-grading.json"
                code = {}
                if code_path.exists():
                    for c in json.loads(code_path.read_text())["checks"]:
                        code[c["id"]] = c
                judge_data = load_judge(it, manifest, eval_dir.name, cfg_dir.name, run.name)
                judge = {}
                if judge_data:
                    for e in judge_data.get("expectations", []):
                        pid = e["text"].split()[1] if e["text"].startswith("[judge]") else e["text"].split()[0]
                        judge[pid] = e
                    for flag in judge_data.get("awareness_flags", []):
                        awareness.append(f"{eval_dir.name}/{cfg_dir.name}/{run.name}: {flag}")
                    fb = judge_data.get("eval_feedback", {})
                    for s in fb.get("suggestions", []):
                        fairness.append(f"{eval_dir.name}/{cfg_dir.name}: {s}")

                rows, unknown = [], 0
                for exp in spec["expectations"]:
                    pid = exp.split()[1]
                    if exp.startswith("[code]"):
                        c = code.get(pid)
                        rows.append({"text": exp, "passed": bool(c and c["passed"]),
                                     "evidence": c["evidence"] if c else "code grading missing"})
                    else:
                        j = judge.get(pid)
                        if j is None:
                            rows.append({"text": exp, "passed": False, "unknown": True,
                                         "evidence": "judge grading missing"})
                            unknown += 1
                        else:
                            if j.get("unknown"):
                                unknown += 1
                            if j.get("disputed"):
                                fairness.append(f"{eval_dir.name}/{cfg_dir.name}/{run.name} "
                                                f"DISPUTED {pid}: {j.get('evidence', '')[:200]}")
                            rows.append({"text": exp, "passed": bool(j["passed"]),
                                         **({"unknown": True} if j.get("unknown") else {}),
                                         "evidence": j.get("evidence", "")})
                decided = [r for r in rows if not r.get("unknown")]
                passed = sum(r["passed"] for r in decided)
                out = {
                    "expectations": rows,
                    "summary": {"passed": passed, "failed": len(decided) - passed,
                                "total": len(decided), "unknown": unknown,
                                "pass_rate": round(passed / len(decided), 4) if decided else 0.0},
                    "timing": {},
                }
                (run / "grading.json").write_text(json.dumps(out, indent=2))
                print(f"{eval_dir.name}/{cfg_dir.name}/{run.name}: {passed}/{len(decided)}"
                      + (f" ({unknown} unknown)" if unknown else ""))

    # ---- suite audit ------------------------------------------------------
    by_point = defaultdict(lambda: defaultdict(list))
    by_case_run = defaultdict(lambda: defaultdict(list))
    for g in sorted(it.glob("eval-*/*/run-*/grading.json")):
        config = g.parent.parent.name
        case = g.parent.parent.parent.name
        data = json.loads(g.read_text())
        allpass = True
        for e in data["expectations"]:
            if e.get("unknown"):
                continue
            by_point[(case, e["text"])][config].append(bool(e["passed"]))
            allpass = allpass and bool(e["passed"])
        by_case_run[case][config].append(allpass)

    lines = ["# Suite audit", ""]

    lines.append("## Arm means over decision points")
    arm_points = defaultdict(list)
    for (_case, _), cfgs in by_point.items():
        for cfg, vals in cfgs.items():
            arm_points[cfg].extend(vals)
    for cfg, vals in sorted(arm_points.items()):
        lines.append(f"- {cfg}: {sum(vals)}/{len(vals)} = {sum(vals)/len(vals):.0%}")

    lines.append("\n## All-points-pass per case (pass^k view)")
    for case, cfgs in sorted(by_case_run.items()):
        row = ", ".join(f"{cfg}: {sum(v)}/{len(v)}" for cfg, v in sorted(cfgs.items()))
        lines.append(f"- {case}: {row}")

    buckets = defaultdict(list)
    for (case, text), cfgs in by_point.items():
        w = cfgs.get("with_skill", [])
        o = cfgs.get("without_skill", [])
        wr = sum(w) / len(w) if w else None
        orr = sum(o) / len(o) if o else None
        if wr is None or orr is None:
            buckets["incomplete (one arm only)"].append((case, text, wr, orr))
        elif wr == orr == 1.0:
            buckets["both always pass — RETIREMENT CANDIDATE"].append((case, text, wr, orr))
        elif wr == orr == 0.0:
            buckets["both always fail — headroom or defect"].append((case, text, wr, orr))
        elif wr > orr:
            buckets["skill wins"].append((case, text, wr, orr))
        elif orr > wr:
            buckets["baseline wins — investigate"].append((case, text, wr, orr))
        else:
            buckets["tied, partial"].append((case, text, wr, orr))

    lines.append("\n## Per-point discrimination")
    order = ["skill wins", "baseline wins — investigate", "tied, partial",
             "both always fail — headroom or defect",
             "both always pass — RETIREMENT CANDIDATE", "incomplete (one arm only)"]
    for b in order:
        rows = buckets.get(b)
        if not rows:
            continue
        lines.append(f"\n### {b} ({len(rows)})")
        for case, text, wr, orr in sorted(rows):
            f_w = "  — " if wr is None else f"{wr:.0%}"
            f_o = "  — " if orr is None else f"{orr:.0%}"
            lines.append(f"- with={f_w} without={f_o}  {text[:110]}")

    lines.append("\n## Awareness flags (must be empty; any entry is a leak)")
    lines.extend([f"- {a}" for a in awareness] or ["- none"])

    lines.append("\n## Fairness log (disputed verdicts, judge feedback)")
    lines.extend([f"- {f}" for f in fairness] or ["- none"])

    report = "\n".join(lines) + "\n"
    (it / "discrimination.md").write_text(report)
    print("\n" + report)


if __name__ == "__main__":
    main()
