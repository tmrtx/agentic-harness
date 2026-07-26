---
name: oracle-ladder
description: Classify the oracle behind any expectation and place it on the ladder — intrinsic, static, runtime, statistical, experimental, principal — with its ground truth (specified, derived, implicit, principal). Use whenever installing, changing, or reviewing an expectation about agent behavior or work products; whenever modifying any instruction file (skills, CLAUDE.md, commands, agent prompts) — such changes carry a recorded oracle; and whenever choosing how a rule should be enforced rather than written.
---

# The Oracle Ladder

## Why

An expectation needs a declared oracle. The oracle is the way anyone —
human, script, or model — tells whether the expectation held. Without one,
a failed expectation cannot be debugged. Nothing separates a model failure
from a wording failure from a stale assumption. The rule gets re-litigated
instead. Declaring the oracle turns a wish into an expectation. The ladder
orders the forms a declaration can take. Height means less judgment in the
verdict. Less judgment leaves less to argue about after the fact.

## Classification

The questions run in order. The first match places the oracle. The question
is the rung's definition.

0. `intrinsic` — Can a violating artifact even be constructed? No → intrinsic.
1. `static` — Is the verdict a total function of the artifact at rest —
   deterministic, recomputable at any time, consulting no execution trace
   of the system under verification? Yes → static. The checker's own
   execution is irrelevant; machinery never determines class.
2. `runtime` — Is the verdict a decidable predicate over a single execution
   or trace of the system under verification? Yes → runtime.
3. `statistical` — Does the verdict need aggregation over samples, or a
   threshold with a nonzero error rate? Yes → statistical.
4. `experimental` — Does the verdict require a counterfactual variant that
   does not exist yet? Yes → experimental.
5. `principal` — Is the ground truth a human preference? Yes → principal.
   The tag `:tacit` marks a preference that cannot yet be articulated. The
   tag `:preference` marks one that could be, but has not been formalized.

Class is a property of the verdict. It is not a property of the machinery
that computes it, nor of the point in the pipeline where it fires. The
machinery table maps class to mechanism; the mapping is not invertible.

A placement has two dimensions. Collapsing them misfiles the common case of
a human hand-checking a written rule.

    oracle-class:  intrinsic | static | runtime | statistical | experimental | principal
    ground-truth:  specified | derived | implicit | principal

`ground-truth` names where the reference standard lives. `specified`:
written down. `derived`: computed from other artifacts. `implicit`: expected
without being written anywhere. `principal`: held by the principal.

## Policy

- A expectation should aim to sit at the highest rung attainable (Rung 0). The
  higher the rung, the more likely it'll be accepted into the repository,
  'principal' having the highest rejection rate.
- Justification grows superlinearly. Rung 0's justification is self-evident.
  Each rung needs to justify what makes attaining a higher rung by reframing the
  problem not possible. A principal placement (Rung 5) needs to have a very
  strong justification and accompanied evidence (approaches considered and not
  used for each rung above) and also justification why the fallback
  'experimental' oracle (eval workflow) wasn't available and has to create
  burden for the 'principal'.
- Every placement is recorded. Intrinsic placements are included. An
  impossibility is still an expectation. Unrecorded, it is invisible to the
  ratchet and silently un-owned.
- A commit carries the oracle that verifies it. The trailer holds the two
  dimensions. The `[ORACLE]` section holds the mechanism and the
  justification. The ledger condenses trailer, oracle section, and target.
  Corpus state predating this rule is grandfathered until touched.

## Recording

A commit declares its oracle in two places. The trailer holds the
constrained dimensions:

    Oracle: [<oracle-class>|<ground-truth>]

These dimensions classify how *this commit* was verified. They are not the
class of an expectation the commit installs — that lives in the expectation's
own state entry. Every commit has a verifier, while only some commits install
anything, so a trailer required on all of them can only mean the former. A
commit that ships a static checker and is verified by running that checker's
suite carries `runtime`: the reading is the machinery-versus-class separation
holding, not breaking. Reaching for the class just computed is the easy error
here, because classifying is what you were doing a moment ago.

The commit body holds an `[ORACLE]` section: one labeled line per
element, so the classification is checkable against the questions.

    [ORACLE]
    Class: <rung> - <the first-match reasoning>.
    Ground truth: <source> - <where the standard lives>.
    Mechanism: <the check, rubric, comparison, or checkpoint>.
    Oracle: <ORC code from the state>.

Two artifacts at the repository root persist this.

`oracle-state.json` is the current oracle inventory: one coded entry
(`ORC-<n>`) per oracle in force, holding its dimensions, mechanism, and
subject. A climb edits the entry.

`oracles.jsonl` is the append-only ledger: one line per governed change,
condensing the trailer dimensions, the `[ORACLE]` section, and the
target. It cites the verifying oracle by code. Ledger snapshots stay
immutable when the state later climbs. Constrained fields come first;
free text comes last.

    {"since":"<date>","oracle":"ORC-<n>","oracle-class":"<rung>",
     "ground-truth":"<source>","target":"<what changed>",
     "justification":"<graduated by depth>"}

## Operationalizing in Claude Code

The ladder is platform-free. This section is its Claude Code instantiation. It expires with that platform's contract.

| rung         | example machinery                                                                                                     |
|--------------|-----------------------------------------------------------------------------------------------------------------------|
| intrinsic    | permission deny rules; tool removal; PreToolUse deny                                                                  |
| static       | command hooks; plugin validation; CI checks; token-budget lints                                                       |
| runtime      | self-recording gates, one event line per fired / denied / errored under `${CLAUDE_PLUGIN_DATA}`; PostToolUse feedback |
| statistical  | hooks with a written rubric; agent hooks when the judge needs repository state too                                    |
| experimental | resident skill-creator eval workflow (with/without runs, assertions, grading)                                         |
| principal    | PR review checkpoint; spec consensus with exported decisions                                                          |

Gate economics. Each line prices an asymmetry.

- A gate is judged by expected value, not check correctness. Silent breakage
  is worse than no gate: a believed-in gate replaces the vigilance it
  automated. Misfiring is worse than no gate when its cost exceeds what it
  catches.
- The exit code selects channel and audience. 0: the harness reads stdout
  JSON. 2: the model reads stderr and the action blocks. Other: the human
  sees a notice and the action proceeds. A missed violation is usually
  repairable downstream. A false block costs the session's remainder. Doubt
  therefore resolves open. The exception is an irreversible violation:
  detection after the fact recovers nothing, so doubt licenses the block.
- Blast radius orders placement. early flight tool errors has a large blast
  radius on the final outcome whereas an error towards the end of the flight has
  a very small blast radius.
- `${CLAUDE_PLUGIN_ROOT}` is replaced on update. Durable state lives in
  `${CLAUDE_PLUGIN_DATA}`, schema-versioned, fingerprinted to the content it
  vouches for.
- A broken gate looks exactly like a passing one from outside. Each gate
  therefore ships an env-var kill switch and self-records its events.
  Consumers can disable a plugin, not one hook inside it.
