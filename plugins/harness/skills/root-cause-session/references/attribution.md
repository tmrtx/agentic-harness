# Attribution and the Corpus Fix

How to move from "here is what the agent did" to "here is the instruction
defect", and how to fix the corpus so the behavior cannot recur.

## Classify the cause

For each candidate instruction that was provably in context (see
`transcript-format.md` on proving that), classify:

- **Commanded** — a sentence instructs the behavior. The fix is to rewrite
  that sentence.
- **Licensed** — the text permits or over-promises, and the agent's reasoning
  cites it as justification. Typical shape: a rationale that claims a practice
  guarantees an outcome it does not ("test-first ensures homomorphism by
  design"). The fix tempers the claim and points at the guard that actually
  covers the failure mode.
- **Unguarded (gap)** — nothing commands or licenses the defect, but no
  directive, diagnostic, or checklist item *names* it either, so neither the
  author-agent nor the reviewer had a rule to catch it. The proof of a gap is
  mechanical: run every existing diagnostic against the defective artifact and
  record pass/fail. A defect that passes them all is a gap, and the fix is a
  new directive with a diagnostic that fails on the observed artifact.
- **Extra-instructional** — the driver was outside the corpus: repository
  precedent ("existing code does it this way"), the shape of the spec (a
  formula-shaped spec invites formula-restating artifacts), or missing context
  (the governing text was never loaded). Fix the exemplar code, the spec
  template, or the loading path — and consider whether the corpus should gain
  a guard against the driver anyway.

Causes compound. A typical real finding is a gap *plus* precedent *plus*
description-only loading; report every link, ranked by leverage.

## Evidence standard

- **Quote the decision.** The agent's own `thinking`/`text` at the moment of
  the defective choice is primary evidence; cite the record index. Do not
  paraphrase what can be quoted.
- **Demonstrate, don't argue.** Find one concrete divergence the defect
  produced or blessed — an input, a value, a diff line — and show it. An
  attribution that cannot point at a concrete demonstration is a hypothesis,
  not a finding.
- **Prove the counterfactual.** Show that under the fixed text, the observed
  artifact fails a named diagnostic. A fix that would not have caught the
  original incident fixes nothing.

## Fixing the corpus

- **One home per concept.** Fix the skill that owns the concept; everything
  else (reviewer prompts, checklists, sibling directives) must gain the rule
  by reference to that home, never by restating it.
- **Survive description-only loading.** If the incident shows the agent acted
  on the description line alone, the new rule must be legible from the
  description line alone — amend the frontmatter description, not only the
  body.
- **Append, don't renumber.** New directives take the next free code; existing
  codes are referenced elsewhere and must not shift.
- **Branch discipline.** The marketplace clone is a live release channel: a
  push to `main` ships to every consumer at their next session start. Commit
  the fix on a branch, leave the clone checked out on a clean `main` (a dirty
  or diverged `main` breaks plugin auto-update pulls), and leave the push to a
  human. Until pushed and reloaded, sessions still serve the old text.

## Worked example (2026-07, PR #107 "TestCapacity")

Symptom: a delegated agent implemented a per-setup capacity feature and its
central test recomputed the feature's own formula chain and asserted the
production column equals it — a test that verifies the code against itself.

- **Decision quote** (transcript record 96, thinking): *"…independently
  recomputing the spec formula … This mirrors how existing tests validate
  other indicators—they recompute the spec formula inline and assert the
  column matches."*
- **Demonstration**: the issue specified `rolling(30)`; implementation *and*
  test both wrote `min_periods=1` — the mirrored oracle encoded the divergence
  instead of catching it.
- **Loading**: only one `Skill` call all session (commit protocol). The
  test-writing control's full text never entered context; the agent worked
  from its description line plus repo precedent.
- **Diagnostics run**: the defective test asserted on an observable output,
  survived refactoring, named a real scenario, read as a spec — every existing
  diagnostic passed. → **Unguarded gap**, compounded by extra-instructional
  precedent (existing mirror tests) and description-only loading.
- **Fix**: a new directive — "Independent Oracles", taking the next free code
  (CIA-8.6) — whose diagnostic, "could this test fail if the spec was
  misread?", fails on the artifact; the frontmatter description amended to
  survive description-only loading; the reviewer given the move by reference.
  Landed per the branch discipline above: committed on a branch in the
  marketplace clone for human review and release. Exemplar mirror tests in
  the consumer repo were rewritten in a follow-up PR.
