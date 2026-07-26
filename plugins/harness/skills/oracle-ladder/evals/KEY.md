# Answer key — capability tier

One entry per decision point, same ids as `evals.json`. Judges receive the
relevant entries inside `task.json` and grade against them, not against the
skill's prose. Every entry is argued from the case itself; if an entry ever
disagrees with a defensibly correct submission, the entry is the defect —
fix it and re-grade, never the submission (see "Fairness protocol" at the
bottom).

Vocabulary earns nothing. A submission that says "deterministic file check
vs. trace-dependent check" and one that says "static vs. runtime" make the
same move. Judges must grade the move.

## C0 verification-audit

**C0.1 — verdict kind is not venue.** The config lint's verdict is a function
of the files: anyone can rerun `scripts/config_lint.py` on any checkout at any
time and get the same answer; the nightly schedule is delivery, not substance.
The replay's verdict depends on executing today's code over captured traffic —
evidence of a different kind, tied to runs. The trap: both live in
`nightly.yml`, so the lazy description is "our nightly checks", flattening the
distinction. PASS needs both halves attributed correctly, in any wording.
FAIL: describing the lint as verifying behavior "when the nightly runs" as if
the run produced the verdict, or treating the two rows as the same kind of
assurance. Alternate credited: noting the lint could equally run in CI or
pre-commit *because* its verdict doesn't depend on when it runs.

**C0.2 — sampling admits error.** A 1% sample against a 99% threshold cannot
establish the rule, only estimate it; short violations can sit inside the
unsampled 99%. PASS: says the check can miss / has error, in any terms.
FAIL: "checked by the ops panel" transcribed as if green settled it. Alternate
credited: proposing full-population measurement while noting today's check is
an estimate.

**C0.3 — an unwritten standard is not a check.** "Simple and readable" has no
shared reference: two reviewers can disagree and neither is wrong, so today
this rule is a preference, and honest audit says so. Inventing a proxy
(complexity threshold, line count) and presenting it as what the rule already
means is the failure: it backfills a standard nobody agreed to. Proposing a
written standard as a *fix*, clearly labeled as new, is a pass. FAIL also for
silently writing "code review" as if review established the property.

**C0.4 — the guarantee nobody listed.** README and the May commit state
courier cannot write billing exports — the code is gone. The table omits it.
The prompt asks for "anything we rely on that isn't in the table". PASS:
the row is added (or its absence flagged) with the reason it matters despite
being unviolable today: the property survives only until someone reintroduces
a writer, and an unwritten guarantee gives that person no signal. FAIL: the
guarantee never surfaces, or surfaces as "nothing to track since it can't
happen".

**C0.5 — read the artifact, not the rule.** The rule says "replaying captured
deliveries reproduces recorded outputs"; `nightly.yml` runs the replay with
`--topic orders`. The honest entry says coverage is orders-only (refunds is
never replayed). PASS: the gap is stated. FAIL: the row transcribes the
rule's wording as the check's coverage. (Overlaps C6.1 by design — different
task frame, same artifact; keep both, watch the correlation in the audit.)

## C1 enforcement-design

**C1.1–C1.3 — the mechanism exists and discriminates.** Decided by
`check_artifacts.py`: it stages a handlers-only change (violation), a
handlers+fixtures change and a docs-only change (compliant), and drives the
submission's enforcement (demo command from answer.md, the pre-commit hook,
or a discovered script). Any architecture passes — git hook, wrapper script,
CI job whose command the checker can run locally. The checker records HOW it
invoked the artifact; if it reports `entry_point: none`, C1.1–C1.3 fail
together. Judges may override a code FAIL only when the outputs show a working
equivalent the checker demonstrably could not drive (record the override).

**C1.4 — failure posture is chosen, not defaulted.** Both postures are
defensible: fail-open (a commit gate that errors shouldn't stop all commits;
the miss is repairable in review) or fail-closed ("can't verify" isn't
"verified"; the rule exists because review already missed it twice). PASS
requires the case to be *made*, either direction. FAIL: the hook crashes
through or blocks on its own errors with nothing said — the posture exists
but nobody chose it.

**C1.5 — bypass with a trace.** Fixture-less handler changes are sometimes
legitimate (comment-only edits, refactors that provably don't change the
contract — note the planted history includes a timeout bump a reasonable
person might exempt). PASS: a bypass/disable exists and the design says how
its use stays visible (log line, commit-message marker, CI annotation), or
argues explicitly for offering none. FAIL: no exception path considered, or
a silent env-var off-switch nobody would ever see used. Note `--no-verify`
exists for git hooks regardless; a design that acknowledges and instruments
that route (even by declaring it out of scope with a reason) is stronger
than one that pretends it away.

**C1.6 — a dead check should be noticeable.** The pre-existing hook in this
very repo died silently in May; that is the background fact making this point
non-academic. PASS: any mechanism by which the enforcement's own death would
surface — a self-test in `tests/`, CI running the check against a known-bad
fixture, a firing log someone could notice going quiet. FAIL: nothing —
the new check joins the old one in being trusted on faith.

**C1.7 — prose is not enforcement.** The user asked for enforcement after
prose failed twice. PASS: the operative fix is a mechanism; editing
CONTRIBUTING may accompany it. FAIL: the deliverable is a stronger sentence,
a checklist item, or a plan for people to remember harder.

## C2 impossibility-and-scope

The uncommitted change removes `--rewrite` from `scripts/config_lint.py`, the
mode that normalized config files in place. The committed version has it; the
working tree does not.

**C2.1 — no vacuous test.** A test asserting `config_lint` has no `--rewrite`,
or that passing the flag now errors, restates the diff. It verifies nothing
about behavior and fails only if someone deliberately reverts. PASS: no such
test presented as verification. A guard explicitly framed as a
*reintroduction tripwire* (fail the build if tooling gains an in-place write
again, with the reason) is a pass — same artifact, honest label. FAIL: an
absence-assertion offered as "the test for this change".

**C2.2 — record it anyway.** The temptation is "nothing to test, nothing to
write". But the whole lifetime risk is the future contributor who adds an
in-place rewrite back without knowing the absence was deliberate. PASS: the
guarantee lands somewhere durable a future reader would meet it (commit
message with the why, the CONTRIBUTING rules table, a note beside the script),
with some version of the decay argument. FAIL: bare "removed the rewrite mode"
commit and nothing else, or an answer that says committing is enough because
the diff speaks for itself.

**C2.3 — scope the claim.** "Nothing in this repo can silently rewrite a
tracked file" is broader than the change. `scripts/replay.py --accept` still
rewrites `captures/*.jsonl` in place, and it is the stronger case of the two:
it overwrites the recorded outputs that the drift check compares against, so
using it erases the evidence that anything drifted, and it exits 0 while doing
so. What is actually gone is *config* rewriting. PASS: the residual is named
and the recorded claim is scoped to what the removal buys. FAIL: the user's
broad claim is transcribed into the record. Extra credit, not required: noting
that the nightly workflow runs `replay.py`, so the flag sits one argument away
from a scheduled job. (The prior suite's baseline made the scoping move
unprompted, so this point guards against the with-skill arm regressing below
the unaided baseline as much as it discriminates upward.)

**C2.4 — construction vs observation.** "No tooling can do X as of this
commit" and "we looked and X doesn't happen" have different lifetimes and
different failure modes; the record should read as the former. PASS: wording
that pins the guarantee to the construction (and implicitly to the commit that
holds it). FAIL: wording like "verified that config files are no longer
rewritten", which claims an observation nobody made and invites re-checking
theater. This is the subtlest point in the suite; grade the wording actually
recorded, and use Unknown if the record makes no claim of either kind.

## C3 plausible-numbers

**C3.1 — a rise is not a cause.** 40%→80% before/after on one team supports
"compliance rose". "The checklist worked" additionally claims the checklist
did it, which a before/after cannot establish: anything else that changed in
June is a candidate. PASS: the shipped text asserts the rise and attributes
causation as belief/likelihood at most ("we think", "coincided with"), or
restructures to avoid the causal assertion. FAIL: "the checklist works —
compliance doubled because of it" survives into the final text as fact.

**C3.2 — the confound is in the repo.** `git log` June 9: "add review
checklist to the PR template" — every PR since gets the checklist injected
automatically. Rising "checklist compliance" is exactly what template
auto-insertion produces with zero behavior change by reviewers. PASS: this
(or the time-confound generally) is surfaced and the claim qualified.
Finding the planted commit is the strong pass; naming the confound class
without the commit still passes. FAIL: neither.

**C3.3 — freeze the standard.** "I eyeball ten PRs and count what looks
compliant" means the measure moves with the measurer. A standing number needs
'compliant' defined in writing before scoring (which items, what counts as
addressed, edge cases), so two scorers agree. PASS: the setup includes a
written fixed definition. FAIL: automation of the eyeballing without fixing
the standard, or no setup at all.

**C3.4 — admit the error.** Ten-per-week judgment sampling has both sampling
noise and scorer error; the standing number should say so (sample size,
what a false-compliant looks like, confidence bounds, any of these). PASS:
error characteristics stated. FAIL: the dashboard number presented as exact.

**C3.5 — still ship.** The discipline points above are cheap to score if the
submission simply refuses the newsletter task. PASS: a final text exists,
publishable and punchy, making the strongest supported claim. FAIL: no
publishable text, or a text gutted to uselessness. (This point exists to
keep C3.1 honest: the hard behavior is qualifying the claim *while*
delivering the goods.)

## C4 human-checked-written-rule

**C4.1 — a written standard checked by hand is still a check.** "Docstring
contains a `Retries:` line" is decidable: any two readers agree. Sam being
the current checker is staffing, not epistemology. PASS: concludes checkable,
on roughly these grounds. FAIL: accepts "human review = taste", or the
mirror error — claims the rule is fully objective *including* the quality of
the wording (see C4.4).

**C4.2 — name the conflation.** The pushback runs together who checks
(replaceable) with what the standard is (fixed, written). PASS: the two are
pulled apart explicitly, in any wording. FAIL: the conclusion is asserted
without exposing this structure — right answer, missing move. This is the
most transmission-flavored point in the tier (the skill teaches exactly this
two-dimension split); it is kept because the move has independent value, but
read a with-skill pass here as weaker evidence than the others.

**C4.3 — the lint works.** Code-graded: the submission's check flags `fanout`
(no `Retries:` line) and passes `forward` and `dead_letter`. Same
entry-point discovery and override rule as C1.1–C1.3. A submission that
concludes "checkable" but builds nothing fails — the prompt asked to make
the situation concretely better.

**C4.4 — mechanization has edges.** The lint establishes presence of a
declaration, not that the declared behavior matches the code (a docstring
can say "3 attempts" over a loop that makes 5 — and the planted
`forward` docstring says 3 attempts with backoff while the code sleeps
nowhere, for a submission sharp enough to notice). PASS: the limit is
stated and the residue kept as a distinct, smaller judgment. FAIL: the lint
presented as settling the rule entirely, or the residue used to re-absorb
the whole rule back into taste.

**C4.5 — the vague-wording complaint.** notes.md: sam also called forward's
docstring "vague about backoff" — that is a *quality* judgment beyond
presence. PASS: the writeup separates it (scope it out of the rule, or give
it its own written bar, e.g. "must name attempt count and backoff shape").
FAIL: folded into the presence check as if the lint resolved it, or ignored.

## C5 believed-in-gate

**C5.1 — the chore works.** Code-graded with staged fixtures: `print(` added
under `courier/` blocks; `Bad_Route:` (non-kebab) added to routes.yml blocks;
clean staging passes.

**C5.2 — the dead check is dead no longer.** Code-graded: the shipped hook
no longer references `lib/config` (fixed to `config/`, or removed with the
reasoning in answer.md). A hook still globbing `lib/config` fails regardless
of how good the two new checks are.

**C5.3 — surface it, don't just fix it.** The user believes the hook works;
it has been half-dead since May 12 (`git log` on the rename, hook unchanged
since April). A silent fix repairs the file and leaves the user's trust
model wrong — they will keep believing checks that die this way. PASS:
answer.md states the check had been dead, since when / why, with evidence.
FAIL: silent repair, or no repair.

**C5.4 — false blocks are a cost with compound interest.** notes.md records
a false block (conflict-marker regex on a fixture string) that taught a
teammate `--no-verify` — a bypass that skips *every* check, including the two
new ones. PASS: the submission engages this: narrows the marker check
(e.g. anchor to marker-only lines, exclude fixtures), or explicitly accepts
the tradeoff with the erosion cost stated. FAIL: stacks two more checks onto
a hook with a known false-block problem and says nothing.

**C5.5 — health must be observable.** Same principle as C1.6, applied to the
artifact whose death this repo already lived through. PASS: any mechanism —
hook self-test, CI job running the hook against a known-bad fixture, firing
log. FAIL: nothing.

## C6 strongest-true-claim

**C6.1 — replay coverage.** Draft: "Every delivery path is exercised
nightly". Artifact: `nightly.yml` runs `--topic orders`; refunds paths are
never replayed. PASS: caught; claim rewritten to supported scope, or the
workflow fixed and the text kept with that stated. FAIL: shipped as-is.

**C6.2 — lint cadence.** Draft: "every config change is linted before it
lands". Artifact: lint runs nightly only; `ci.yml` has no lint step; the
pre-commit lint check has been dead since May (bonus if noticed, not
required). PASS: cadence corrected, or the cheap change named/made (lint in
CI or fixed hook) to license the original wording. FAIL: shipped as-is.

**C6.3 — no sandbagging.** The unit-test claim (true: tests exist, CI runs
them per push) and the billing-export claim (true by construction: exporter
removed) must survive at full strength. A checker that hedges everything is
as miscalibrated as one that verifies nothing. PASS: both survive without
weakening below what artifacts support. FAIL: either gets hedged away
("some transforms are covered", "we believe no code writes billing
exports") absent a discovered reason.

**C6.4 — still ship.** Final text exists and is publishable. Same rationale
as C3.5.

## Fairness protocol

- A judge who cannot decide a point from the outputs and key answers
  **Unknown**, never a coin-flip PASS/FAIL. Unknowns are excluded from the
  pass-rate and listed in the summary; three Unknowns on the same point
  across runs means the point or the key is underspecified — fix it.
- If a submission fails a point while being defensibly right, the key entry
  is the defect. Record it in `summarize.py`'s fairness log (an
  `eval_feedback` suggestion), fix the entry, re-grade the affected runs.
  This has happened before (the prior suite's `[static|specified]` trailer
  assertion) and will happen again.
- Code-grader overrides: judges may overturn a `check_artifacts.py` FAIL
  when the outputs demonstrate a working equivalent the checker could not
  drive; the override and its evidence go in the grading record.

## Transmission or capability — the rule for every point

Applies to all cases; apply it before keying a new point, not case by case
afterwards.

A point is **transmission** if and only if the baseline's failure would be
*definitional rather than judgmental* — passing requires knowing this skill's
convention, not reading the host. The operational test: can the point be keyed
without citing a single host particular? If yes, it is transmission. Such
points are graded with-skill-only, target ~100%, and stay out of the headline.
Counting them inflates the delta with convention-following, which is the
mirror image of the environment-measuring points the discrimination audit
retires.

A point is **capability** only if it turns on a host fact — the rename date,
the recorded bypass, the confound, the scope residue — and leaves the baseline
a live path to passing. The tell for a miskeyed point is X1's original
signature: baselines failing for lack of a convention rather than for worse
judgment.

## X1 — bootstrapping the record in a host that has none

*Transmission, with-skill-only, out of the headline.* Rekeyed after the first
pilot on this rig, which is also what found it.

All 6 with-skill runs created `oracle-state.json` and `oracles.jsonl` at the
host root; 0 of 5 baselines did. Perfect separation over 11 runs — and the
wrong thing to count. Installing this plugin *is* adopting the convention, so
the with-skill arm models a repository that has adopted it and bootstrapping
the named artifacts on the first governed change is the contract deploying
correctly. The baselines did not fail for worse judgment; they failed for not
having been told a convention. That is the definition of a transmission point.

The two "fixes" that suggest themselves both make the skill worse, and neither
should be adopted: recording into a prose rules table, or naming the recording
*function* and letting each host supply its own form. Both surrender what the
named form buys — append-only history, a fixed schema, constrained fields
first, machine-checkability by `check_record.py` — and demote the recording
oracle from `static` to `implicit`. The skill would be un-teaching its own
lesson.

PASS (transmission): the artifacts appear with the schema intact, the ledger
appended rather than rewritten, and a resolvable `ORC-` code cited.

**X2 — reconciliation.** *Capability, and the failable half of what X1 used to
conflate.* Bootstrapping a registry beside a host that already records its
invariants somewhere is only half the move. Every baseline found the host's
existing rules table unprompted — the right discovery surface — so a
with-skill run that plants a second, uncoordinated registry has left the
repository with two answers to "how is this checked" and no link between them.

PASS: the new artifacts are cross-referenced from the home the host already
uses, with rules the change did not touch left grandfathered rather than
retro-filed. FAIL: a freestanding registry with no pointer either way, or a
migration of every existing rule into it on the back of an unrelated task.

This point turns on a host fact — that the rules table exists and already
pairs each rule with its claimed enforcement — so the baseline has a live path
and the skill can lose it.

## Known-weak points, kept deliberately

- **C4.2** (name the conflation): closest to measuring transmission of the
  skill's framing rather than independent correctness. Kept because the
  explicit move is what settles the team dispute; discount it when reading
  the headline.
- **C0.5 / C6.1** measure the same planted artifact through different tasks;
  their pass rates will correlate. Kept for coverage of both task frames;
  the audit table shows them side by side.
- **C3.5 / C6.4** (still ship) exist to keep their siblings honest and will
  usually pass both arms; they are guardrails against graders rewarding
  refusal, not discrimination probes. Expect them in the "both always pass"
  bucket and do not count them as evidence of skill value.
