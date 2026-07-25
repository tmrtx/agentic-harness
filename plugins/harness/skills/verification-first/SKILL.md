---
name: verification-first
description: Select the mechanism of action for any expectation about agent behavior — name its oracle, classify it, map it to an enforcement mechanism, place it by false-positive economics. Use whenever installing, changing, or reviewing an expectation about how work happens — "make sure X always happens", "add a rule / check / gate / lint", proposing or editing an instruction, CLAUDE.md line, hook, or CI check, converting a manual review habit into automation, or diagnosing why an existing rule keeps being ignored — even when the request names no mechanism, and especially when the default response would be adding prose.
---

# Verification-First Mechanism Selection

## Purpose

Every expectation about agent behavior needs a declared **oracle** — a way anyone
(human, script, or model) can tell whether it was met. An expectation living only in
prose has no oracle: when it fails, you cannot tell whether the model, the wording, or
the author's assumptions failed (underdetermination), so it can be neither delegated
nor debugged — only re-litigated.

Two asymmetries drive everything below:

- **Attention is probabilistic; invocation is deterministic.** Instruction text
  competes for a model's attention and degrades under context pressure — whether it
  is even considered is chance. Its cost tracks its residency: always-resident prose
  (CLAUDE.md, every skill `description`) bills every session whether or not it ever
  fires; on-demand prose (a skill body, a reference) bills the working context of
  each session that loads it, and adds the risk that routing never loads it at all.
  A mechanism runs at exactly the moment it matters, every time, and costs nothing
  until then. The guarantee covers invocation, not verdict: a script
  decides deterministically; a model-judge decides probabilistically, with an error
  rate that can be measured and tuned. So "must hold every time" is purchasable only
  where the oracle is decidable — routing a rubric through a prompt hook buys *always
  evaluated*, not *always right* — and no amount of louder prose buys either. (CIA-9
  §2 draws the same deterministic-gate conclusion for invariants.)

- **Quality is cheapest at the source.** An expectation enforced at authoring time
  costs one interaction; caught at review, a round-trip; missed, it compounds
  downstream. So *evaluation* wants to happen as early as the oracle allows — while
  how hard the verdict may bite at each point (feedback or a block) is a separate
  question, priced in step 4 by what an error there would interrupt.

CIA-8 gives code changes their oracle (tests as the specification). This skill extends
the same demand to expectations about *how work happens* — process, instructions,
agent behavior. The whole procedure is one calculation applied three ways: what oracle
does this expectation admit, what is the cheapest evaluator adequate to that oracle,
and — at each candidate placement — what would an erroneous block interrupt versus
what would a miss cost.

## The procedure

Given an expectation — "X should always/never happen", "instructions must stay under
budget", "tests should assert outcomes":

1. **Name the oracle.** Complete, in observable terms: "this expectation was met
   iff ___". If the sentence won't complete, there is nothing to enforce yet — you are
   holding a wish. Sharpen it until an oracle appears, or record it as intent with its
   ladder (`CIA-9.1`), explicitly marked unenforced — so no reader budgets vigilance
   against a gate that does not exist.

2. **Classify the oracle** by the kind of evaluator the expectation admits:

   | `oracle-class` | The oracle is… | Examples |
   |---|---|---|
   | `decidable-check` | a script's exit code | diff size, token budget, required section present, tests ran |
   | `rubric` | a model judging against written criteria | generality of a new rule, cohesion of a module |
   | `trace-monitor` | evidence in the session record | "the reviewer ran before this PR" |
   | `ablation-only` | comparing runs with vs. without | "this instruction actually improves outcomes" |

3. **Map class → cheapest adequate evaluator.** The current platform inventory, and
   the force behind each pairing:

   | `oracle-class` | Mechanism | The force behind the pairing |
   |---|---|---|
   | `decidable-check` | command hook in-session; CI as out-of-session backstop | a script is the cheapest and most repeatable evaluator there is; model judgment spent on a decidable question is judgment wasted |
   | `rubric` | prompt hook (single-turn model judge); agent hook when the judge must consult repo state; reviewer-agent phase at review time | model judgment is the costliest evaluator and the only one that works here — so the criteria get written down, and the false-positive rate is the builder's to measure and tune |
   | `trace-monitor` | the gate self-records; denials land in the session trace by construction | the session record is evidence, not an API — its format shifts between versions, so pipelines parsing it break silently while agents reading it don't |
   | `ablation-only` | eval harness: with/without comparison in fresh sessions | the oracle here *is* a comparison, so it is enforceable exactly where such a harness exists; where none does, declaring the class honestly beats simulating enforcement with prose |

   The classes are stable; the inventory grows with the platform. A new mechanism
   slots in by the same rule that built this table: cheapest evaluator adequate to
   the oracle.

4. **Place it by comparing both costs.** Two terms, not one. An erroneous block's
   damage is proportional to what it interrupts: mid-flight, the error enters the
   model's context and pollutes every decision after it — the session becomes the
   casualty; at a terminal boundary (push, PR creation), the thinking is done and a
   false positive costs one retry; out of session (CI), a red build and no session at
   all. A missed violation's damage runs on the other axis: most process expectations
   are detectable and repairable downstream, so a miss costs a deferred fix — which is
   why strictness usually rises toward the boundaries, where blocking is cheap and a
   miss would surface anyway. The gradient inverts when a violation is irreversible or
   its cost unbounded — a destructive command, a secret leaving the repo: detection
   after the fact recovers nothing, so even the costliest block (mid-flight) is the
   cheap side of the comparison. Place by that comparison, not by which end is easiest
   to build; the mechanics of what each placement can express are in the reference
   below.

5. **Prose is the declared residue.** Whatever survives the search for an oracle as
   genuinely judgment-shaped becomes instruction text carrying its full ladder
   (`CIA-9.1`). The procedure's contribution here is honesty: prose chosen *after*
   the search failed is a known limitation; prose chosen by default pre-empts the
   search — and reads as enforced when it isn't.

## Building it

Before building any enforcement mechanism — a hook today, whatever the inventory
holds tomorrow — read [`references/building-gates.md`](references/building-gates.md).
A gate is judged by its expected value, not by the correctness of its check; the
reference carries the failure economics (how gates misfire into sessions, and how
they break silently) that the check's correctness says nothing about, and it opens
with the test that separates its durable claims from those that expire with the
current hook platform's contract.

## Anti-patterns

Each is the same error — the form of an oracle without one:

- **A sentence doing a script's job.** The sentence pays the residency tax of
  wherever it lives and holds probabilistically; the script it dodged would hold
  deterministically and bill nothing until violated.
- **The precautionary mid-session stop that never priced the violation.** "To be
  safe" names only one side of the placement comparison. When the violation it guards
  against is detectable and repairable downstream, the block's expected cost — a
  poisoned session per false positive — is the larger term, and safety argues for
  feedback; when the violation is irreversible, the same comparison licenses the
  stop. Pricing both sides is what separates the two.
- **"The model should check…" with no written criteria.** A rubric-class oracle with
  no rubric evaluates nothing; it is prose wearing a gate's costume.
- **Pipelines parsing session transcripts.** Coupled to an observation instead of a
  contract, they break silently on format shifts — and silent breakage in a
  believed-in monitor is worse than its absence.
- **An unenforced expectation presented as enforced.** Readers budget vigilance as if
  a gate exists, and a believed-in gate replaces exactly the attention that would have
  caught the violation.
