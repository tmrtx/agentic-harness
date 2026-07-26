# Runbook — oracle-ladder eval suite

Agent-driven orchestration. `$EVALS` is this directory; `$WS` is a scratch
workspace (e.g. the session scratchpad); `$SKILL` is
`plugins/harness/skills/oracle-ladder/SKILL.md` at the revision under test.
Solver model: the model whose behavior you care about (prior iterations:
the default top-tier model). Judge model: a **different** model.

## 0. Validate the graders (once per session, ~2 min)

```sh
python3 $EVALS/check_record.py --outputs $EVALS/reference \
  --baseline-ledger $EVALS/reference/baseline-oracles.jsonl \
  --expect-class principal --expect-ground-truth principal --require-commit
```
All checks must pass. Then check_artifacts.py both ways: build a sandbox,
grade it untouched as a C5 submission (expect C5.1/C5.2 FAIL), then apply an
obviously good hook and expect PASS. A grader that cannot split known-good
from known-bad invalidates the iteration.

## 1. Build sandboxes

One fresh sandbox per (case, arm, run). Case ids 0–6 map to C0–C6; only C2
needs `--case C2` (dirty tree). The build lints for contamination and fails
loudly on a hit.

```sh
python3 $EVALS/host/build_host.py --dest $WS/sb/c<ID>-without-r<K> --arm without [--case C2]
python3 $EVALS/host/build_host.py --dest $WS/sb/c<ID>-with-r<K>    --arm with --skill $SKILL [--case C2]
python3 $EVALS/host/build_host.py --dest $WS/sb/_pristine          --arm without   # judges' repo context
```

## 2. Solve

Spawn one executor subagent per sandbox, both arms of a case in the same
batch. Executor prompt, verbatim (fill `{SANDBOX}` and `{PROMPT}` from
`evals.json`; the bracketed paragraph is the ONLY with-arm difference):

```
You are doing a task for a user in the repository at {SANDBOX}. That
repository is your entire world: do not read, search, or reference anything
outside it, and do not use the network. Work directly in the repository.

[with arm only:] This repository has a Claude Code skill at
.claude/skills/oracle-ladder/SKILL.md. Its description matches this task,
so it has been loaded for you: read it before starting and apply it where
it applies.

The user's request:

{PROMPT}

Write your reply to the user as {SANDBOX}/answer.md. If you commit, use
author "Dev <dev@courier.local>". Do not create files outside the
repository. When the work is done, stop.
```

Record `total_tokens` and `duration_ms` from each completed subagent into
`run-K/timing.json` (`{"total_tokens": N, "duration_ms": M,
"total_duration_seconds": M/1000}`) immediately — they are not recoverable
later.

## 3. Collect

Layout: `$IT/eval-<ID>-<name>/<with_skill|without_skill>/run-<K>/`.

```sh
python3 $EVALS/collect_outputs.py --sandbox $WS/sb/c<ID>-<arm>-r<K> \
  --eval-id <ID> --dest $IT/eval-<ID>-<name>/<config>/run-<K>
```

Keep the mutated sandboxes until step 4 is done.

## 4. Code grading (cases 1, 4, 5)

```sh
python3 $EVALS/check_artifacts.py --case C1 \
  --sandbox $WS/sb/c1-<arm>-r<K> \
  --answer  $IT/eval-1-enforcement-design/<config>/run-<K>/outputs/answer.md \
  --pristine-hook $WS/sb/_pristine/.githooks/pre-commit \
  > $IT/eval-1-enforcement-design/<config>/run-<K>/code-grading.json
```
Same for C4 and C5 (C5 needs no `--answer`). Read the evidence lines; if a
run failed with `entry_point: none` but its outputs describe a working
mechanism, note it for the judge-override path (KEY.md, fairness protocol).

## 5. Blind judging

```sh
python3 $EVALS/stage_blind.py $IT --pristine $WS/sb/_pristine
```

Spawn one judge subagent per submission, on a model different from the
solver. Judge prompt:

```
You are a grader. Read {EVALS}/judge.md and follow it exactly. Your
submission directory is {BLIND}/submission-<token>. Grade every decision
point in its task.json against the key excerpts, write grading.json as
specified, and answer the awareness meta-question. Do not attempt to
identify which experimental arm produced the submission.
```

Do not open `.blind-manifest-*.json` until all judge gradings are written.

## 6. Merge, audit, render

```sh
python3 $EVALS/summarize.py $IT                # per-run grading.json + discrimination.md
cd /root/.claude/skills/skill-creator && \
  python3 -m scripts.aggregate_benchmark $IT --skill-name oracle-ladder
python3 /root/.claude/skills/skill-creator/eval-viewer/generate_review.py $IT \
  --skill-name oracle-ladder --benchmark $IT/benchmark.json --static $WS/review.html
```

Read `discrimination.md` before the headline: awareness flags (any = leak,
fix before trusting numbers), baseline-wins rows (fairness defects first),
retirement candidates (two iterations in that bucket = retire or harden).

## 7. Transmission tier (with-skill only, per skill edit)

For each case in `transmission.json`: copy this repository to a scratch dir
(`git clone --no-hardlinks . $WS/tx-<id>` from the repo root keeps it
self-contained), run the case's `setup` commands in the copy, snapshot
`oracles.jsonl` as the baseline ledger, then run the executor prompt (the
skill is present normally — no ablation, no loading paragraph needed beyond
the repo's own plugin). Collect `commit-message.txt` (`git log -1
--format=%B`), `oracles.jsonl`, `oracle-state.json` into `outputs/`, then:

```sh
python3 $EVALS/check_record.py --outputs <outputs> \
  --baseline-ledger <snapshot> --require-commit \
  --expect-class <grader.expect_class> --expect-ground-truth <grader.expect_ground_truth>
```

Report transmission results separately from the capability headline, always
labelled as regression cover.

## Iteration hygiene

- ≥3 runs per arm per case before reading a delta as real; single runs are
  smoke tests.
- Never reuse a sandbox across runs; never let a solver see a graded
  sibling.
- When a key entry loses a dispute, fix KEY.md, re-grade affected runs,
  and say so in the iteration notes.
- After each iteration, append one paragraph to the iteration notes: which
  points discriminated, which retired, what got harder.
