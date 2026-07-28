---
name: merge
description: Land a finished PR by folding its scratchpad stack into state commits and rebase-merging. Use only when the user invokes /merge on a reviewed branch — never on the implementer's path; the implementer's stack is a licensed scratchpad whose journey commits are mined data.
disable-model-invocation: true
---

# /merge — fold the journey, land the state

The implementer's branch carries its journey on purpose — repairs of its own
commits, review-finding fixes — and the principal mines that record from the
PR. Landed history is what `blame` and `bisect` consume, so the fold happens
here, at merge time, and nowhere earlier.

1. Judge the stack: `python3 scripts/classify_stack.py` (in the repo, on the
   branch). Each `fold` verdict names a commit that answers this branch's own
   history, with the model's reason; the verdict is statistical (calibrated
   error rates: `evals/stack-provenance/results/`), so overrule it where your
   own reading of the stack disagrees — you, not it, are the merger.
2. Fold each journey commit into the commit it corrects; rewrite the target's
   message as if the correction had always been part of it. Keep structural
   and behavioral change in separate commits (`CIA-7.5`); never collapse the
   branch to one commit. Mechanics: `git commit --fixup=<target>` per fold,
   then `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash <base>` — plain
   `--autosquash` exits successfully **without folding** before git 2.44.
3. Re-run the judge on the folded stack: a clean pass (no folds) verifies the
   result; then rebase-merge, so history lands linear and the PR retains the
   pre-squash commits for later analysis.
