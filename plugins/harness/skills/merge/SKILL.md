---
name: merge
description: Execute a brief against a pull request — usually landing it (rebase, fold the journey, drop scaffolding, repair messages, push, rebase-merge, record the landing), sometimes just commenting or reporting. Invoked as `merge <brief>`, e.g. `merge pr#35 is good but the comments need simplifying`, `merge pr#23`, `merge comment on pr#123 about how it's consuming too many tokens`.
argument-hint: <ref> [what's wrong / what to do]
disable-model-invocation: true
---

your objective is to execute the brief against a pull request. usually that means moving
it over the finish line.

## reading the brief

everything after `merge` is the brief. it is prose, not a command language — read it the
way a colleague would. fill four slots:

| slot | how |
|---|---|
| target | `pr#35`, `#35`, `35`, or a description ("the tokenizer one"). if absent, resolve from the current branch; if that fails, ask. |
| disposition | does the author believe it's ready? "is good but", "looks fine except", "lgtm apart from" → ready modulo the stated exceptions. |
| mutations | requested changes to the stack: commit messages, code comments, folding, splitting, dropping suites. zero or more. |
| terminal action | merge / comment-only / report-and-stop. |

worked examples:

- `pr#23` → full landing sequence, house style, no questions.
- `pr#35 is good but comments need to be simplified` → land, with an extra mutation pass
  over comments. "comments" is kind-ambiguous → one question (see below), then proceed.
- `pr#45 is good but commit messages are garbage` → land, "garbage" is ambiguous
  → counterfactual questions (1 at a time) until intent alignment → rewrite
  the messages.
- `comment on PR#123 about how it's consuming too many tokens` → question tool
  to get approval on the comment or feedback, repeat until approval → post the
  comment. do not touch the branch. do not merge.
- `why is PR#12 3000 lines` → report only. no worktree, no mutation, no merge.
- `PR#61 and PR#62 are both good` → serialize; land the first, then the second. if they
  conflict, escalate.

## authorization

merge is the only action here you cannot walk back. it is authorized when the brief
asserts readiness, or when the brief is a bare target. it is never inferred from a brief
whose verb is comment / review / check / look at / why.

the brief states the author's *belief*, not fact. verify independently: mergeable state,
ci, unresolved review threads, and that the requested mutations actually landed. any
conflict between brief and reality is a stop-and-report, not an override. "is good" does
not authorize merging over a red suite.

if a requested mutation could not be performed, or has unforeseen consequences do not merge and then escalate.

## clarification

ask upfront only when the brief is ambiguous **in kind** — where guessing wrong wastes the
work:

- "comments" → code comments in the diff / the review thread on the pr / commit message
  bodies
- "the tests" → a specific suite / all new tests / the scaffolding you were going to drop
  anyway
- the target can't be resolved
- the brief contradicts house style (e.g. asks you to keep a suite that fails the
  earn-its-place table) — surface the conflict, let the author overrule it explicitly

usual style: earn-its-place for suites, no defensive writing, no semantic
chaining, models&maintainers are the audience. cite the rule and proceed. if you
find yourself wanting to ask and no rule covers it, note the gap in your final
report — that is a hole in this skill, and it is worth more than the answer.

every question opens with a plain-language tldr: what happened, why it matters,
what is being decided — self-contained, no session context assumed. the
operator merges many stacks across many sessions and arrives at your question
cold; a question that presumes your context earns "i don't understand what's
going on" and wastes the round trip.

for changes, ground each option in a counterfactual before asking — sample one
representative case and show before/after. options are worlds to pick between,
not questions about preference:

    header: which comments
    options:
      - code comments in the diff — 12 of them, 9 restate the line below
      - the review thread on pr#35
      - commit message bodies

    header: how far
    options:
      - drop restatements, keep the 3 that explain why
        `// increment the counter` / `counter += 1`  →  `counter += 1`
      - keep all, compress each to one line
      - drop every comment the diff added

for anything that survives past the questions: do the work in the worktree, then show the
result — `git log` before/after, or the message diff — and confirm once, immediately
before push. that is the single gate. one round trip, not a tree.

when a mutation drops or rewrites reviewable artifacts (tests, comments,
messages), the gate shows each candidate's full source in the question tool's
previews — one conceptual group per question, one artifact per drop-option —
because the owner judges from source, not from your summary. their verdict
overrules the house table in either direction; record overrides with their
reason.

## typical actions

your tasks will involve actions such as:
- rebasing because the main history was rewritten
- determining whether to keep or discard commits with the assistance of
  `${CLAUDE_SKILL_DIR}/scripts/classify_stack.py`. the classifier serves one
  goal: a landed stack sized by responsibility, not by authored commit count.
  per-commit bisect/revert isolation only pays when the change carries weight,
  so a small-responsibility branch folds to a single protocol commit even when
  authored and reviewed as a series. the rubric judges per-commit provenance
  only — "the whole branch is one responsibility" is the merger's read, and
  folding an inherited reviewed stack is an operator call: surface it at the
  gate, don't assume it.
- rewriting the commit stack: folding commits, editing out suites failing the
  earn-its-place table (`harness:executable-expectations`), surgery on the commits
  themselves, rewriting commit messages
- extra mutation passes named in the brief
- merging the pull request
- commenting on the pull request

## verification

before push, prove the surgery did only what was claimed:

- message-only rewrite → `git rev-parse HEAD^{tree}` matches the pre-rewrite tree exactly.
  if it doesn't, you dropped or moved code, escalate don't investigate.
- comment-only surgery → the diff touches only comment lines, and the suite is green.
- dropped a suite → name it and the earn-its-place clause it failed, in the record.
- always → rerun `classify_stack.py`, then read the resulting log top to bottom as a
  maintainer with no context. if the story doesn't land, fold again.

for every pull request you merge:
1. verbatim quote the user request;
2. tersely compile all the questions you had to ask and my answers to them;
3. and post it as a comment on the pull request to document what you were asked for observability.

## keep in mind

- you are not concerned with the already merged commits.
- you might need to eliminate unnecessary defensive writing or semantic chaining
  from the commits to make them easier to comprehend and consume less tokens
  (because models are the audience of those commit messages as well as the
  maintainers).
- you need a worktree to isolate everything you're doing from the repository.
