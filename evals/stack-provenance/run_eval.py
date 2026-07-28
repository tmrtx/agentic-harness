#!/usr/bin/env python3
"""Eval runner for the stack-provenance classifier (calibrates ORC-8).

Dataset: commits from tmrtx/mono-repo PR history, labeled fold/keep by the
principal's recorded actions (squash requests, hand-folds at landing,
verbatim merges) plus the stated rubric for the open cohort; split by whole
PR so holdout PRs contributed nothing to rubric tuning. The judge input is
what the stack itself carries: the commit message plus the ordered sibling
subjects of the same branch — never PR comments, later fold outcomes, or
merge results, which would leak the label.

Calls `claude -p` (pinned Haiku, no tools, JSON-schema output) once per case
per trial from a neutral cwd (no project context contaminates the call).
Grades by exact match; reports both error directions: fold-recall (missed
folds pass the gate) and keep-specificity (legitimate commits blocked).
"""
import argparse, importlib.util, json, os, subprocess, sys, threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
# The judge's verdict-determining pieces — prompt shape, output schema,
# neutral cwd — are the merge skill's classifier, importlib-loaded so eval
# and deployment cannot drift apart. Invocation policy (timeout, retry)
# stays local: it affects availability, never the verdict distribution.
_spec = importlib.util.spec_from_file_location("judge", os.path.normpath(os.path.join(
    HERE, "..", "..", "plugins", "harness", "skills", "merge", "scripts", "classify_stack.py")))
gate = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gate)

def classify(prompt_text, message, model, stack=None, timeout=240):
    full = gate.build_prompt(prompt_text, message, stack)
    r = subprocess.run(
        ["claude", "-p", full, "--model", model, "--tools", "",
         "--output-format", "json", "--json-schema", gate.SCHEMA,
         "--no-session-persistence"],
        capture_output=True, text=True, timeout=timeout, cwd=gate.neutral_cwd())
    if r.returncode != 0:
        return None, f"exit {r.returncode}: {r.stderr[:200]}"
    try:
        out = json.loads(r.stdout)
        so = out.get("structured_output") or {}
        v = so.get("verdict")
        return (v, so.get("reason", "")) if v in ("fold", "keep") else (None, "no verdict")
    except Exception as e:
        return None, f"parse: {e}"

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", default=os.path.join(HERE, "dataset.jsonl"))
    ap.add_argument("--prompt", default=os.path.normpath(os.path.join(
        HERE, "..", "..", "plugins", "harness", "skills", "merge", "rubric.md")))
    ap.add_argument("--split", default="dev", choices=["dev", "holdout", "all"])
    ap.add_argument("--trials", type=int, default=3)
    ap.add_argument("--model", default="claude-haiku-4-5-20251001")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()

    prompt_text = open(args.prompt).read()
    cases = [json.loads(l) for l in open(args.dataset)]
    if args.split != "all":
        cases = [c for c in cases if c["split"] == args.split]

    results = defaultdict(list)   # id -> [(trial, verdict, reason)]
    lock = threading.Lock()
    done = [0]
    total = len(cases) * args.trials

    def work(case, trial):
        text = case["subject"] + "\n\n" + case["message"] if not case["message"].startswith(case["subject"]) else case["message"]
        try:
            v, reason = classify(prompt_text, text, args.model, case.get("stack"))
            if v is None:
                v, reason = classify(prompt_text, text, args.model, case.get("stack"))  # one retry
        except Exception as e:
            v, reason = None, f"error: {e.__class__.__name__}"
        with lock:
            results[case["id"]].append((trial, v, reason))
            done[0] += 1
            if done[0] % 25 == 0:
                print(f"  {done[0]}/{total}", file=sys.stderr, flush=True)

    with ThreadPoolExecutor(args.jobs) as ex:
        futs = [ex.submit(work, c, t) for t in range(args.trials) for c in cases]
        for f in futs:
            f.result()

    # ---- metrics ----
    def rates(pred_of):
        cm = Counter()
        for c in cases:
            p = pred_of(c["id"])
            cm[(c["label"], p)] += 1
        fold_n = cm[("fold", "fold")] + cm[("fold", "keep")] + cm[("fold", None)]
        keep_n = cm[("keep", "keep")] + cm[("keep", "fold")] + cm[("keep", None)]
        fold_recall = cm[("fold", "fold")] / fold_n if fold_n else 0
        keep_spec = cm[("keep", "keep")] / keep_n if keep_n else 0
        prec_d = cm[("fold", "fold")] + cm[("keep", "fold")]
        fold_prec = cm[("fold", "fold")] / prec_d if prec_d else 0
        acc = (cm[("fold", "fold")] + cm[("keep", "keep")]) / len(cases)
        f1 = 2 * fold_prec * fold_recall / (fold_prec + fold_recall) if fold_prec + fold_recall else 0
        return dict(fold_recall=fold_recall, keep_specificity=keep_spec,
                    fold_precision=fold_prec, accuracy=acc, f1_fold=f1, cm=dict(
                        tp=cm[("fold", "fold")], fn=cm[("fold", "keep")] + cm[("fold", None)],
                        tn=cm[("keep", "keep")], fp=cm[("keep", "fold")]))

    per_trial = []
    for t in range(args.trials):
        # slice by the trial that produced the verdict, not completion order
        per_trial.append(rates(lambda cid, t=t: next(
            (v for tr, v, _ in results[cid] if tr == t), None)))

    def majority(cid):
        vs = [v for _, v, _ in results[cid] if v]
        if not vs:
            return None
        return Counter(vs).most_common(1)[0][0]
    maj = rates(majority)

    print(f"\n== split={args.split} n={len(cases)} trials={args.trials} model={args.model}")
    for t, m in enumerate(per_trial):
        print(f" trial {t}: fold_recall={m['fold_recall']:.3f} keep_spec={m['keep_specificity']:.3f} acc={m['accuracy']:.3f} f1={m['f1_fold']:.3f} cm={m['cm']}")
    print(f" majority: fold_recall={maj['fold_recall']:.3f} keep_spec={maj['keep_specificity']:.3f} acc={maj['accuracy']:.3f} f1={maj['f1_fold']:.3f} cm={maj['cm']}")

    flips = {cid: [v for _, v, _ in results[cid]] for cid in results
             if len(set(v for _, v, _ in results[cid])) > 1}
    if flips:
        print(f" unstable ({len(flips)}): {sorted(flips)}")

    print("\n== misclassified (by majority):")
    for c in cases:
        m = majority(c["id"])
        if m != c["label"]:
            reasons = "; ".join(sorted({r[:110] for _, v, r in results[c["id"]] if v == m}))
            print(f"  [{c['label']:>4}→{m}] {c['id']} ({c['hardness']}, {c['provenance']}) {c['subject'][:80]}")
            print(f"        model: {reasons[:220]}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump({"split": args.split, "n": len(cases), "trials": args.trials,
                       "model": args.model, "per_trial": per_trial, "majority": maj,
                       "verdicts": {cid: [[tr, v, r] for tr, v, r in vs] for cid, vs in results.items()}},
                      f, indent=1)
        print(f"\nwritten: {args.out}")

if __name__ == "__main__":
    main()
