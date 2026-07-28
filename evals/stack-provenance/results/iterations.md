# Rubric calibration journal

Model: claude-haiku-4-5-20251001 unless noted. Dev = 96 cases (62 keep / 34
fold), holdout = 41 cases (25 keep / 16 fold), split by whole PR before any
tuning. Numbers are majority-vote across trials; single-trial spread shown in
the result JSONs. The gate runs a single call per commit, so per-trial rates
estimate deployment; majority rates show ceiling stability. (Recorded runs
predate a runner fix: their per-trial rows slice by completion order, not
trial index — read them as spread cohorts; majority rows are unaffected.
Holdout trials were near-identical, so the distinction is cosmetic there.)

| rubric | input | dev fold-recall | dev keep-spec | change driving it |
|---|---|---|---|---|
| v1 | message only | 0.735 | 0.903 | baseline: predates-the-branch rubric |
| v2 | message only | 0.824 | 0.839 | repair-vs-extend distinction; same-PR review-marker cues — model began inventing branch provenance |
| v3 | + stack subjects | 1.000 | 0.839 | sibling context resolves unstated provenance — but area overlap read as authorship |
| v4 | + ordered stack | 0.941 | 0.871 | direction law (repairs flow backward) + authorship law (refactoring an area ≠ authoring it) |
| v5 | ordered stack | 0.912 | 0.935 | wrong-vs-unfinished: completing a sibling's deliberate decomposition is state, not repair |

## Holdout protocol (v5 frozen, single run, 3 trials)

- haiku majority: fold-recall 0.625, keep-spec 0.840 (trials: 0.625/0.840, 0.625/0.840, 0.750/0.880)
- sonnet (claude-sonnet-5, same frozen rubric) majority: 0.625/0.840 —
  indistinguishable from haiku, with a near-identical error set. The residual
  errors are input-information-bound, not capacity-bound: the messages
  genuinely narrate pre-existing problems, and only diff-level context or the
  era standard resolves them. The climb buys nothing; the gate stays on haiku.
- Error decomposition:
  - all 4 false blocks are PR #315 commits — a pre-2026-07-20 PR merged
    verbatim, whose review-finding commits on branch-born code would be folds
    under the standard the principal has since articulated. On the 17
    holdout keeps from every other PR: 0 false blocks.
  - 4 of 6 misses are PR #304 field-run repairs whose messages defensibly
    read as pre-existing-workflow fixes (the branch reified a script that
    "drifted for a year"); the evidence-discipline rule that protects
    keep-specificity excuses exactly this narration. The other 2 are #341's
    marker-free structural repairs.
- Dev→holdout gap: the holdout concentrates the two hardest archetypes
  (era-boundary keeps, narrated-as-pre-existing folds); dev numbers should
  be read as ceiling, holdout as floor.

## Merge-frame re-run (v6 — consumption reframe only)

The pivot from push-time gate to merge-time instrument changed the rubric's
framing sentences (where the verdict is consumed), never its fold/keep
criteria. One holdout re-run under the shipped wording: majority 0.688/0.800
(trials 0.562/0.800, 0.750/0.760, 0.562/0.840) vs 0.625/0.840 under the
push-frame wording it was tuned in — inside trial spread in both directions,
same error families (#304 field-run narrations missed; #315 era keeps
flagged). The calibration transfers.

## Known blind spot (excluded from labels, documented in dataset builder)

A superseded-approach commit — journey only relative to its replacement —
reads clean in its own message and stack position. Catching it needs
diff-level analysis; out of scope for this oracle.
