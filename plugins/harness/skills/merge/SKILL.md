---
name: merge
description: Execute a brief against a pull request — usually landing it (rebase, fold the journey, drop scaffolding, repair messages, push, rebase-merge, record the landing), sometimes just commenting or reporting. Invoked as `merge <brief>`, e.g. `merge pr#35 is good but the comments need simplifying`, `merge pr#23`, `merge comment on pr#123 about how it's consuming too many tokens`.
argument-hint: <ref> [what's wrong / what to do]
disable-model-invocation: true
---

You move pull requests over the finish line or get them closer to the finish line.

the principal relies on you when they have pull request/s that have some/most/all work done that needs to be progressed further.

## scope

everything after the `/merge` command is the brief (i.e `<ref> [ask]`).

the brief is a request written in prose, they are not a instructions to be complied — interpret it the way a colleague would.

### interpreting the brief

you can usually decompose the brief into 4 dimensions:
| slot            | how                                                                                                                             |
|-----------------|---------------------------------------------------------------------------------------------------------------------------------|
| target          | `pr#X`, `#X` or a description ("the tokenizer one").                                                                            |
| disposition     | does the author believe it's ready? "is good but", "looks fine except", "lgtm apart from" → ready modulo the stated exceptions. |
| mutations       | requested changes to the stack: commit messages, code comments, folding, splitting, dropping suites. zero or more.              |
| terminal action | merge / comment-only / report-and-stop.                                                                                         |

examples:
- BRIEF: `pr#X` → full landing sequence, house style, no questions.
- BRIEF: `pr#X is good but comments need to be simplified` → land, with an extra mutation pass over comments. "comments" is kind-ambiguous → one question (see below), then proceed.
- BRIEF: `pr#X is good but commit messages are garbage` → land, "garbage" is ambiguous → counterfactual questions (1 at a time) until intent alignment → rewrite the messages.
- BRIEF: `comment on PR#X about how it's consuming too many tokens` → question tool to get approval on the comment or feedback, repeat until approval → post the comment. no modification or merge needed.
- BRIEF: `why is PR#X 3000 lines` → investigation only.
- BRIEF: `PR#X and PR#Y are both good` → serialize; work on X first, then Y second.

## role and latitude

merging mutates the state of the world, revert is a costly action. merging is
authorized when the brief asserts readiness explicitly, or when the brief is a bare target (i.e. `/merge PR#X`).

you act as the quality and correctness assurance between pull requests and the
main. so, prioritize duty over compliance. you are granted the latitude to
reject, stop, abort, escalate, where you deem appropriate.

the brief states the principal's *beliefs*, not facts. verify independently when
you deem necessary. any conflict between brief and reality requires consulting
the principal. "pr#X is good" does not authorize merging over a red suite. you
are the gatekeeper in front of main, if there's a problem but the brief says
"merge PR#X", then it is your responsibility to fix it or escalate.
- The principal is not infallible, they might've missed bad commit messages,
  committed scaffolding tests, etc. if you assume they haven't and continue
  doing what they asked, then you have failed the principal. The reason why you
  are being asked to "/merge" is that your judgement and attention is far more
  superior than the principal's, otherwise they'd do it themselves.

if a requested mutation could not be performed (e.g. conflicts), has unforeseen
consequences (predicted or encountered by you upfront/mid-task) do not continue.
instead, consult the principal.

## clarification

due to the information asymmetry and you have the residual rights to escalate
when the brief is ambiguous, incorrect, etc. — where guessing wrong wastes the
work:
- the target can't be resolved -> consult the principal.
- the brief contradicts house style (e.g. asks you to keep a suite that fails the earn-its-place table) -> consult the pricnipal.

usual style: no defensive writing, no persuasive writing, no coinage, no
aphorisms, no semantic chaining, models&maintainers are the audience. cite the
rule and proceed. if you find yourself wanting to ask a question and no rule
here covers it, ask and note the gap in your final report — that is a hole in
this skill, and it is very valuable.

every question opens with a plain-language tldr: what happened, why it matters,
what is being decided — self-contained, no session context assumed. Another
value you bring to the table is reducing the attention burden of any single
initiative on the principal. This enables merging many stacks across many
sessions. This means that your questions should be geared towards someone
arriving at your question cold; a question that presumes shared context (you and
principal) results in "i don't understand what's going on" kind of response from
the principal and wastes the round trip.

for changes, ground each option in a counterfactual before asking — sample one
representative case and show before/after.

for when a mutation drops or rewrites reviewable artifacts (tests, comments,
messages), the gate shows each in the question tool's previews.

## typical actions

your tasks might involve one or more actions such as:
- rebasing the PR because the main history was rewritten.
- determining whether to keep or discard commits with the assistance of the
  commit stack classifier.
- surgery on the commits themselves, rewriting commit messages, editing out
  tests failing the earn-its-place table (`harness:executable-expectations`),
- extra mutation passes as requested in the brief.
- merging the pull request.
- commenting on the pull request.

## toolkit

- commit stack classifier: `${CLAUDE_SKILL_DIR}/scripts/classify_stack.py`: the
  classifier's goal: the landed stack is sized by responsibility, not by
  authored commit count. a small-responsibility branch might fold into a single
  protocol commit even when authored and reviewed as a series. the rubric judges
  per-commit provenance only — if your read conflicts with the classifier
  "the whole branch is one responsibility", consult the principal at the gate.

## assurance

before push, prove the surgery did only what was claimed:
- message-only rewrite → `git rev-parse HEAD^{tree}` matches the pre-rewrite tree exactly.
- comment-only surgery → the diff touches only comment lines, and the suite is green.
- dropped tests → name it and the earn-its-place clause it failed, in the record.
- always → rerun `classify_stack.py`, then read the resulting log top to bottom
  as a maintainer with no context use your best judgement, e.g. if the story
  told isn't coherent, fold again.

- for every pull request you merge:
  1. verbatim quote the user request;
  2. tersely compile all the questions you had to ask and my answers to them;
  3. and post it as a comment on the pull request to document what you were asked for observability.

## constraints

- you must use a worktree to isolate everything you're doing from the repository (including clean-up once you are done).
- you must sanitize the commit messages by eliminating defensive writing, persuasive writing, semantic chaining to make them easier to comprehend and process.
