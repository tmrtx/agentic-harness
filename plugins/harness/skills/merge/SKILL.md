---
name: merge
description: Land a reviewed PR end to end — rebase, fold its journey into state commits, drop scaffolding, repair messages, merge on GitHub, record the landing. Use only when the user invokes /merge on a reviewed branch — never on the implementer's path; the implementer's stack is a licensed scratchpad whose journey commits are mined data.
disable-model-invocation: true
---

# /merge — land it so no hand has to

The principal otherwise lands by hand: cherry-pick the keepers, strip the
scaffolding, squash the fixups, rewrite the message, push, close the PR without
a word. That surgery is where landing defects come from — review fixes
reverted, references left dangling — and none of its reasoning survives as
data. Land here instead, and leave the record on the PR.

1. **Rebase onto the base branch.** Main moves daily.
2. **Fold the journey.** Landed history is what `blame` and `bisect` consume,
   so it narrates the result. Run `python3
   ${CLAUDE_SKILL_DIR}/scripts/classify_stack.py` in the repo, on the branch:
   it marks each commit `fold` (it answers this branch's own history — a repair
   of an earlier commit, a review-finding fix) or `keep`, with reasons.
   The verdict is statistical (`evals/stack-provenance/results/`); overrule it
   where your own reading of the stack disagrees — you are the merger. Fold
   each into the commit it corrects: `git commit --fixup=<target>`, then
   `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <base>` — plain
   `--autosquash` exits successfully **without folding** before git 2.44. Keep
   structural and behavioral change in separate commits (`CIA-7.5`); never
   collapse the branch to one commit.
3. **Drop the scaffolding.** A suite that fails the earn-its-place table
   (`harness:executable-expectations`) built the change; it is not the change.
   Run it, cite it in `[CHANGE]`, delete it. Tests that pin lasting observable
   behavior stay.
4. **Repair the messages** (`harness:commit-protocol`): each describes its
   commit as it now stands — folded corrections read as if they had always been
   part of it, dropped scaffolding leaves no trace, nothing refers forward.
5. **Verify.** `git diff <pre-fold head> HEAD` shows the step-3 deletions and
   nothing else: folding preserves the tree, so any other hunk is a review fix
   or a file dropped without deciding to. A clean re-run of the judge (no
   folds) confirms the stack.
6. **Merge and reconcile.** Rebase-merge on GitHub — main lands linear, the PR
   keeps its pre-fold commits as mined data. Comment the landing delta (`landed
   as <sha>; dropped <what> because <why>`), and close every sibling PR on the
   same symptom naming the winner and what decided it. A decision left off the
   PR teaches nobody.
