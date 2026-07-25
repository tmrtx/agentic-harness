# Evals for the oracle-ladder skill

A skill that classifies oracles should carry one. This suite is the skill's own
placement: `experimental | derived` — the verdict on whether the ladder changes
behavior requires a counterfactual variant, so the harness runs with/without
pairs in fresh sessions and reads the delta.

Nothing here loads at runtime. Bundled files next to `SKILL.md` cost tokens only
when something reads them, so the suite is free to consumers who never run it.

## What the suite claims

The ladder's value is not that an agent can recite six rung names. The
repository already leaks the vocabulary: `oracle-state.json`, `oracles.jsonl`,
and `commit-protocol` all name the dimensions, and an agent with none of the
skill can reconstruct the format from them. So the suite is built so the
baseline keeps all of that. What the ladder has to add on top is:

- **classification discipline** — the first-match order, and the rule that
  machinery never determines class;
- **justification depth** — graduated downward, so a low rung carries its case;
- **complete records** — including the placements that feel too obvious to
  record.

Each eval targets a point where a capable agent, reasoning from the repository
alone, plausibly lands somewhere defensible but wrong.

| eval | tests |
|---|---|
| 0 `record-instruction-change` | a routine instruction edit gets a full record: rung, section, trailer, ledger line |
| 1 `static-not-runtime-trap` | a CI job that executes does not drag the verdict off `static` |
| 2 `choose-enforcement-machinery` | the gate economics get priced, not just a hook proposed |
| 3 `statistical-vs-experimental` | the measurement and the causal claim get separated |
| 4 `intrinsic-still-recorded` | "nothing to test" does not become "nothing to record" |

## Grading

Split by what each half can actually decide.

**Code** (`check_record.py`) owns every verdict that is a total function of the
artifacts at rest — the `[ORACLE]` section, the trailer, the ledger's
append-only invariant, whether a cited `ORC-` code resolves. These are fast,
reproducible, and identical across graders. The trailer regex is deliberately
the one the shipped commit-shape gate uses; if they ever diverge, the suite
would be grading a contract the repository does not enforce.

**A judge** owns what needs reading: whether the argument was made, whether the
instinct was rejected on the right grounds, whether the justification is
proportionate. Judge runs are graded blind — outputs are staged under opaque
ids so the grader cannot see which arm produced them — and by a different model
than the one that produced them.

Assertions carry a `[code]` or `[judge]` prefix so a reader of the results
knows which kind of verdict they are looking at.

`reference/` holds a hand-written correct answer for eval 0. It exists to prove
two things at once: the task is solvable, and the graders pass a known-good
artifact. Run it first — a checker that fails the reference is broken, and any
run it grades afterward is noise.

```sh
python3 evals/check_record.py --outputs evals/reference \
  --baseline-ledger oracles.jsonl --expect-class principal \
  --expect-ground-truth principal --require-commit
```

## Running the suite

The orchestration is agent-driven; `skill-creator` is the harness. The shape
that matters, and the reasons it takes that shape:

1. **Build one sandbox per run** from a clean checkout with
   `skills/oracle-ladder/` removed, and make each eval's premise true in it
   (eval 0 needs a dirty `specification/SKILL.md`; eval 4 needs `WebSearch`
   removed from `reviewer.md` against a baseline commit that had it). Every
   trial starts from its own copy, because shared state between runs turns
   infrastructure flakiness into what looks like a behavior difference.
2. **Spawn both arms in the same batch.** The with-skill run is handed the
   `SKILL.md` path; the baseline is handed nothing. Both are told the sandbox
   is their whole world, so neither can read the skill off the real checkout.
3. **Grade end state, not path.** Agents reach the same place by different
   routes; grading the route penalizes valid ones.
4. **Record `total_tokens` and `duration_ms`** from each run as it finishes.
   A skill that buys accuracy with a large token bill is a trade the reader
   should get to see, and the numbers are not recoverable later.

Instructions have to hold every time, not once, so the honest metric across
repeated trials is the probability that *all* of them pass, not that one did.
Single-run numbers are a smoke test; treat them as such.

## Keeping the suite honest

The failure mode to watch for is a suite that agrees with the skill by
construction. Several assertions are drawn from the skill's own content, which
means they measure whether the skill transmitted its content — not whether that
content is right. Read them that way.

Two audits are worth repeating each round:

- **Non-discriminating assertions.** An assertion both arms always pass is
  measuring the repository, not the skill. Eval 0's format checks are already
  in this category: `commit-protocol` and the shape gate secure them without
  the ladder. They stay because they are regression cover, but they should not
  be read as evidence the skill works.
- **Unfair assertions.** If a run fails an assertion while being defensibly
  right, the assertion is wrong and gets fixed — not the run. This has already
  happened once: eval 1 originally demanded a `[static|specified]` trailer, and
  both arms answered `[runtime|specified]` on the sound reasoning that the
  trailer records the oracle verifying *this commit* rather than the class of
  the check being installed. The assertion now grades internal consistency.
