---
name: commit-protocol
description: This repository's commit protocol — the pre-commit test gate, the title format, the PROBLEM/ROOT-CAUSE/CHANGE/ORACLE commit body, and the stack regulation governing branch history. Use whenever committing in this repo, changing code in response to review feedback, or pushing a branch — `git commit`, `--amend`, `--fixup`, `rebase --autosquash`, `push --force-with-lease`.
---

# Commit Protocol

A commit is the smallest unit a reviewer reads.

Its message must give teleological, causal, and practical understanding of the commit.

1. **Pre-commit gate:** All tests must pass before committing.
2. Commit Title Format: <type>[OPTIONAL:<silo>][<component>]: <action-verb> <what-changed>
3. Commit Body Structure: Commit message body should lead to reviewers gaining a causal, teleological and practical understanding of the commit:
   1. [PROBLEM] - Problem Statement: Formulate the problem that this commit will address (content after `[PROBLEM]` line).
   2. [ROOT-CAUSE] - Root-Cause Analysis: Elaborate the causal mechanics that created this problem (content after `[ROOT-CAUSE]` line).
   3. [CHANGE] - The Change: Describe your approach and justify this approach over alternatives considered (content after `[CHANGE]` line).
   4. [ORACLE] - The Oracle: One labeled line per element - Class and Ground truth each with the reasoning for the classification, Mechanism, and Oracle (the ORC code from oracle-state.json) (content after `[ORACLE]` line).
4. **Oracle trailer:** Each commit carries an `Oracle: [<oracle-class>|<ground-truth>]` git trailer. The dimensions come from the `oracle-ladder` skill. The ledger (`oracles.jsonl`) condenses trailer, verification, and target per change.

Writing instructions:
- Adhere to Zinsser's philosophy of writing well, follow BLUF (bottom line up front), Minto Pyramid, Given-New Principles for writing the commit message.
- Prefer an active voice over a passive voice.
- Avoid mixing abstraction levels in the text.

## The Stack

The rules above govern one commit; these govern the branch.

**Unmerged commits represent the state of the output, never the journey that
produced it.** A branch under review proposes a final state of the repository,
decomposed into the commits a deliberate author would design for that diff.
Construction iterations are folded into that decomposition — regrouped into
reviewable units that keep structural and behavioral change separate
(`CIA-7.5`) — never collapsed into one commit. Until merge, history is a
draft and rewriting it is the branch's normal operation; after merge it is the
permanent record that `blame`, `bisect`, and every future session consume. The
journey is never merged into history.

**Journey test**: if a commit's `[PROBLEM]` was created by the same branch — a
defect in an earlier unmerged commit, a review finding against one — the
commit is journey: fold it into the commit it corrects and rewrite that
commit's message as if the correction had always been part of it. A problem
that exists independently of the branch's own commits, including a new
requirement raised during review, is state and earns its own commit.

Fold at the latest before every push. Mechanics:

- correction to the tip → `git commit --amend`
- correction to an earlier commit → `git commit --fixup=<sha>`, then
  `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <base>`
  (plain `--autosquash` silently no-ops before git 2.44)
- decomposition itself wrong → `git reset --soft <merge-base>`, recommit
- publishing a rewrite → `git push --force-with-lease`

Claude Code note — run the commands exactly as written: exports don't survive
between shell calls, and an editor-blocked rebase gets backgrounded mid-rebase
instead of failing.

**Authority**: platform defaults guard history rewriting because it can
destroy collaborators' work; an agent's own unmerged branch has no such
collaborator, and `--force-with-lease` aborts the push if that assumption
ever fails — so on that branch, folding is authorized, not guarded. The
consuming repository's `CLAUDE.md` carries the explicit grant. Hard boundary:
never rewrite the default branch, merged history, or another author's branch;
where a harness forbids rewriting outright (e.g. the GitHub Action), append
and disclose the uncurated stack in the walkthrough instead.
