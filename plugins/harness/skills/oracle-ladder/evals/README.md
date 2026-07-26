# Evals for the oracle-ladder skill

A skill that classifies oracles should carry one. This suite is the skill's
own placement: `experimental | derived` — whether the ladder changes behavior
needs a counterfactual, so the harness runs with/without arms in fresh
sandboxes and reads the delta. Nothing here loads at runtime; bundled files
cost tokens only when read.

## What this suite measures, and what the last one measured instead

The first suite ran its ablation inside a copy of this repository with only
the skill directory deleted. That design had two fatal properties, found by
running it:

1. **The environment was a crib.** `oracle-state.json`, `oracles.jsonl`,
   `commit-protocol`, and the shape gate teach the vocabulary, the schema,
   and the recording obligation. 56 of 63 assertions passed in both arms;
   the whole +11% delta lived in seven assertions.
2. **The ablation announced itself.** Dangling references ("required per the
   oracle-ladder skill") told the baseline something had been removed, and
   baselines said so in their answers and compensated.

So it measured the repository's redundancy, not the skill. The claim worth
measuring is the deployment claim: *in a repository with no oracle culture,
does the skill make verification reasoning and enforcement design measurably
more disciplined?* That is what a consumer buys, and it is the only framing
in which the baseline arm is clean.

## Two tiers

**Capability tier** (`evals.json`, the headline) — 7 chores in a synthetic
host repository, `courier` (built by `host/build_host.py`): a small webhook
service with a real git history and one planted trap per case. Prompts are
ordinary asks — audit our checks, enforce this rule, do I need to write this
down, finalize this report — with zero ladder vocabulary. The unit of
measurement is the **decision point**: each case has 4–7, each keyed in
`KEY.md` with the correct move, why, acceptable alternates, and the plausible
wrong move. Points are graded semantically ([judge], blind, vocabulary earns
nothing) or behaviorally ([code], `check_artifacts.py` drives whatever the
agent built against planted violation/compliant fixtures). Every point is
designed to be failable by either arm; per Anthropic's evals guidance,
capability cases should start at a low pass rate and leave headroom.

**Transmission tier** (`transmission.json`) — 2 with-skill-only cases in a
copy of this repository, graded by `check_record.py`. These verify the
recording contract still transmits (trailer, `[ORACLE]` section, ledger
append-only, intrinsic-still-recorded). Passes here are **not evidence of
value** — the prior run proved the environment produces most of this format
without the skill. They are regression cover with a ~100% target, kept out
of the headline. There is no baseline arm here on purpose: running one is
how the old suite manufactured 56 dead assertions.

Trigger coverage stays in `trigger-evals.json` (should/should-not-trigger
prompts), unchanged: triggering and output quality are separate measurements.

## How the leak is closed

- The host is synthetic and fully authored: no file, commit message, or
  prompt contains the skill's vocabulary or exhaust. `host/lint_host.py`
  enforces this with an over-broad denylist ("oracle", "rung", "skill",
  "eval", "static", …) and runs on every build; a hit fails the build.
- Nothing is removed from the baseline sandbox, so there is nothing to
  detect: both arms get the same coherent repo, differing only by
  `.claude/skills/oracle-ladder/SKILL.md` and one loading sentence in the
  executor prompt (the same asymmetry real skill loading has).
- Fresh sandbox per run, fresh git history per build — no prior-trial
  artifacts, no shared state (the documented cross-trial inflation vector).
- Closure is also *measured*, not just designed: judges answer an
  awareness meta-question per submission (did the output betray any sense of
  being tested, or reference absent instructions?), and `summarize.py`
  prints any flag loudly. The prior suite would have failed this check.

## Grading architecture

- **Code decides** what is a total function of artifacts: the built
  enforcement blocks the planted violation and passes the compliant case;
  the hook stopped globbing the renamed directory; the recording files parse
  and append (transmission tier).
- **A judge decides** what needs reading, blind (opaque submission ids,
  `stage_blind.py`), one decision point at a time against its `KEY.md`
  entry, with an Unknown escape hatch and a different model from the solver
  (`judge.md`). Key entries are argued from the cases, not quoted from the
  skill — so a regression in the skill shows up as with-skill answers
  making wrong moves, not as the key drifting along with the prose.
- **A human decides** key disputes: judges record `disputed` verdicts
  instead of silently overriding, and the fairness protocol in `KEY.md`
  says how a wrong key entry gets fixed and re-graded.

## Reading the numbers

`summarize.py` merges verdicts into per-run `grading.json` (compatible with
skill-creator's `aggregate_benchmark.py` and viewer) and writes
`discrimination.md`:

- arm means over decision points — the headline;
- per-point discrimination buckets — points both arms always pass are
  flagged **RETIREMENT CANDIDATE** (they measure the environment; retire or
  demote them), points only the baseline wins are investigated as fairness
  defects first;
- all-points-pass per case per arm — the pass^k view; instructions must
  hold every time, so the honest unit across repeated trials is the run
  where nothing slipped;
- awareness flags and the fairness log.

Single runs are a smoke test. Report at ≥3 runs per arm and read the
stddev before believing a delta.

## Keeping headroom

Saturation is handled structurally, not once:

- The with-skill arm is *supposed* to score below 100% here: several points
  (claim scoping C2.3, anti-sandbagging C6.3, the reverse misfile C4, the
  compliance-pressure points C3) sit at or past the skill's current teaching
  edge. When the skill improves, those move; the audit shows which.
- The retirement protocol: any point in "both always pass" across two
  consecutive iterations gets retired to a comment or rewritten harder.
  The traps bank (KEY.md's "plausible wrong move" lines) is where new,
  harder variants come from.
- Known-weak points are labelled in `KEY.md` ("Known-weak points, kept
  deliberately") — read the headline with them discounted.

## Running

See `RUNBOOK.md` for the exact orchestration (sandbox builds, executor
prompts verbatim, collection, code grading, blind staging, judging, merge).
Validate the graders before trusting a run:

```sh
python3 evals/host/build_host.py --dest /tmp/ht --arm without   # lint runs, must pass
python3 evals/check_record.py --outputs evals/reference \
  --baseline-ledger evals/reference/baseline-oracles.jsonl \
  --expect-class principal --expect-ground-truth principal --require-commit
```

`reference/` is a hand-written correct transmission-tier answer: a checker
that fails it is broken, and any run it grades afterward is noise.
`check_artifacts.py` is validated the same way in RUNBOOK step 0 (known-good
and known-bad artifacts must split).

## Honesty ledger

Claims this suite makes about itself, and their status:

- "The baseline cannot reconstruct the skill from the environment" —
  enforced by construction + lint + measured by awareness flags.
- "Most points can fail in either arm" — by design; verified per iteration
  by the discrimination buckets, with named exceptions (C3.5, C6.4 are
  anti-refusal guardrails and expected to sit in both-always-pass).
- "A deliberate regression shows up" — mechanically for the format contract
  (transmission tier fails) and behaviorally for the teaching (key is
  skill-independent, so a mistaught with-skill arm fails capability
  points); not yet demonstrated end-to-end with a sabotaged skill — worth
  doing once as a suite self-test.
- Judge blindness is *approximate*: with-skill answers may speak the
  skill's dialect, and no staging can hide dialect. Mitigations: semantic
  keys, vocabulary-earns-nothing rule, per-point isolation, non-solver
  judge model. Residual risk is real and stated.

## Iteration notes

**Pilot on the new rig (2026-07-26).** 11 runs: C2, C4, C5 across two batches,
2 runs per arm for C2 and C5 with-skill, 1–2 elsewhere. Not a headline — too few runs, and one case could not run at
all. What it established:

- **The rig works and the baseline is strong.** With no oracle culture in the
  host and no vocabulary to copy, baseline runs independently derived the
  skill's central gate insight. One found the pre-commit config lint had been
  globbing a path that moved in May, silently passing for two months, and
  wrote "a green check inspecting nothing looks identical to one that passed".
  Another refused to bypass a false-blocking hook with `--no-verify` on the
  grounds that doing so is what eroded trust in the hook. Both are C5.4 and
  C5.5 territory reached unaided. Expect the enforcement-design advantage
  measured by the previous suite to shrink here, and treat that as a result.
- **X1 was found and added.** All 6 with-skill runs planted the recording
  apparatus at the host root; 0 of 5 baselines did. See X1 in `KEY.md`.
- **Two grader defects, both found by running rather than reading.** C5.2
  matched `lib/config` anywhere in the hook, so it failed a run for
  explaining in a comment the fix it had just made — penalizing exactly what
  C5.3 rewards. Fixed to ignore comments, with a re-broken hook confirming it
  still bites. The count of fairness defects found per pilot is itself worth
  tracking: two suites, two defects, both only visible under execution.
- **C2 was rewritten because it could not reliably run.** Its original
  prompt was phrased around reflecting a payload to a caller-chosen URL, and
  that wording trips a safety classifier: one arm died mid-run with an AUP
  flag while the same case succeeded in another batch. A case that sometimes
  cannot execute cannot measure, and a flaky-by-classifier case is worse than
  a missing one because the failure looks like a result.

  The case now removes the `--rewrite` mode from `scripts/config_lint.py` — the
  repo's own tooling, which is the kind of work this harness is actually used
  for. The structure is unchanged and the trap is sharper: `replay.py --accept`
  still rewrites `captures/*.jsonl` in place, so the class the user declares
  gone is not gone, and the surviving member is the worse one — it overwrites
  the recorded outputs the drift check compares against, erasing the evidence
  that anything drifted, and exits 0 while doing it. Verified end to end: the
  committed script has the mode, the working tree does not, and `--accept`
  demonstrably rewrites tracked records.
- **Rung names earn nothing, as intended.** The with-skill C2 run classified
  the deletion `static` rather than `intrinsic`, arguing a violating artifact
  is still constructible because `urllib.request` remains imported and
  `forward()` has the same shape. The key grades the moves, so this cost it
  nothing — the right outcome, and a check on the key's own design.
