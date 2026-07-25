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
1. `static` — Is the verdict a total function of the artifact, with no
   execution and no threshold? Yes → static.
2. `runtime` — Is the verdict a decidable predicate over a single execution
   or trace? Yes → runtime.
3. `statistical` — Does the verdict need aggregation over samples, or a
   threshold with a nonzero error rate? Yes → statistical.
4. `experimental` — Does the verdict require a counterfactual variant that
   does not exist yet? Yes → experimental.
5. `principal` — Is the ground truth a human preference? Yes → principal.
   The tag `:tacit` marks a preference that cannot yet be articulated. The
   tag `:preference` marks one that could be, but has not been formalized.

A placement has two dimensions. Collapsing them misfiles the common case of
a human hand-checking a written rule.

    oracle-class:  intrinsic | static | runtime | statistical | experimental | principal
    ground-truth:  specified | derived | implicit | principal

`ground-truth` names where the reference standard lives. `specified`:
written down. `derived`: computed from other artifacts. `implicit`: expected
without being written anywhere. `principal`: held by the principal.

## Policy

- An expectation sits at the highest rung its verdict admits with today's
  artifacts. A lower seat is a recorded state, not a failure. The climb is
  the artifact that changes a question's answer: a written rubric, a built
  harness, a constraint.
- Justification grows downward. Rungs 0–2 justify themselves; the oracle is
  its own case. A statistical placement carries its rubric. An experimental
  placement carries its comparison design and cost. A principal placement
  carries the reasons nothing higher is attainable yet.
- Every placement is recorded. Intrinsic placements are included. An
  impossibility is still an expectation. Unrecorded, it is invisible to the
  ratchet and silently un-owned.
- A commit carries the oracle that verifies it. The trailer holds the two
  dimensions. The `[VERIFICATION]` section holds the mechanism and the
  justification. The ledger condenses trailer, verification, and target.
  Corpus state predating this rule is grandfathered until touched.

## Recording

A commit declares its oracle in two places. The trailer holds the
constrained dimensions:

    Oracle: [<oracle-class>|<ground-truth>]

The commit body holds a `[VERIFICATION]` section. It states the oracle
mechanism and the justification, graduated by depth.

`oracles.jsonl` at the repository root is the condensed record. One line
combines a change's trailer dimensions, its verification section, and its
target. Constrained fields come first; free text comes last.

    {"code":"ORC-<n>","since":"<date>","oracle-class":"<rung>",
     "ground-truth":"<source>","target":"<what was changed>",
     "oracle":"<the mechanism in force>","justification":"<graduated by depth>"}

## Operationalizing in Claude Code

The ladder is platform-free. This section is its Claude Code instantiation.
It expires with that platform's contract.

| rung | machinery |
|---|---|
| intrinsic | permission deny rules; tool removal; PreToolUse deny — the deny holds in every permission mode, including bypass |
| static | command hooks; plugin validation; CI checks; token-budget lints |
| runtime | self-recording gates, one event line per fired / denied / errored under `${CLAUDE_PLUGIN_DATA}`; PostToolUse feedback |
| statistical | prompt hooks with a written rubric; agent hooks when the judge needs repository state; reviewer-agent phases |
| experimental | eval harness with with/without pairs in fresh sessions |
| principal | PR review checkpoint; spec consensus with exported decisions |

Gate economics. Each line prices an asymmetry.

- A gate is judged by expected value, not check correctness. Silent breakage
  is worse than no gate: a believed-in gate replaces the vigilance it
  automated. Misfiring is worse than no gate when its cost exceeds what it
  catches.
- Coverage belongs to the action, not the tool. Routes include the CLI form,
  the MCP tool, and the plugin-scoped MCP name. A one-route gate
  redistributes violations. Matchers are case-sensitive. A bare
  `mcp__server` matches nothing.
- The exit code selects channel and audience. 0: the harness reads stdout
  JSON. 2: the model reads stderr and the action blocks. Other: the human
  sees a notice and the action proceeds. A missed violation is usually
  repairable downstream. A false block costs the session's remainder. Doubt
  therefore resolves open. The exception is an irreversible violation:
  detection after the fact recovers nothing, so doubt licenses the block.
- Blast radius orders placement. Mid-flight errors poison everything after
  them. A terminal boundary costs one retry. Out of session costs no
  session at all.
- `${CLAUDE_PLUGIN_ROOT}` is replaced on update. Durable state lives in
  `${CLAUDE_PLUGIN_DATA}`, schema-versioned, fingerprinted to the content it
  vouches for.
- A broken gate looks exactly like a passing one from outside. Each gate
  therefore ships an env-var kill switch and self-records its events.
  Consumers can disable a plugin, not one hook inside it.
