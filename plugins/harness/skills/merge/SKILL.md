---
name: merge
description: Land a reviewed PR end to end — rebase, fold its journey into state commits, drop scaffolding, repair messages, push, rebase-merge, record the landing. Use only when the user invokes /merge on a reviewed branch — never on the implementer's path; the implementer's stack is a licensed scratchpad whose journey commits are mined data.
disable-model-invocation: true
---

# /merge — land it so no hand has to

The principal otherwise lands by hand — cherry-pick the keepers, strip the
scaffolding, squash the fixups, rewrite the message, close the PR without a
word. That surgery is where landing defects come from (review fixes reverted,
references left dangling) and none of its reasoning survives as data. Land
here instead, and leave the record on the PR.

1. **Rebase onto the base branch.** Main moves daily.
2. **Judge the stack.** Run `python3
   ${CLAUDE_SKILL_DIR}/scripts/classify_stack.py` in the repo, on the branch:
   each commit gets `fold` (it answers this branch's own history — a repair of
   an earlier commit, a review-finding fix) or `keep`, with a reason. Held-out
   fold precision and recall are both ≈0.69 and a false fold destroys a state
   commit, so read every verdict against your own reading of the stack; the
   instrument saves you the first pass, not the judgment.
3. **Rewrite the stack into landed shape**, in one `git rebase -i <base>`:
   - **fold** — move each `fold` commit's line directly under the commit it
     corrects and mark it `fixup`. (`git commit --fixup=` commits the index,
     so against these already-made commits it exits 0 having done nothing;
     `--autosquash` only pre-marks subjects already named `fixup!`, and
     without `-i` it exits 0 folding nothing before git 2.44.)
   - **drop scaffolding** — `edit` the commit that introduced a suite failing
     the earn-its-place table and remove it there
     (`harness:executable-expectations`).
   - **reword** — each message describes its commit as it now stands
     (`harness:commit-protocol`): folded corrections read as if they had
     always been part of it, dropped scaffolding leaves no trace, nothing
     refers forward.

   Folding is the only collapse; two `keep` commits never become one
   (`CIA-7.5`).
4. **Verify.** The stack now holds one commit per `keep`, and `git diff
   <pre-fold head> HEAD` shows the scaffolding deletions and nothing else —
   folding preserves the tree, so any other hunk is a review fix or a file
   dropped without deciding to.
5. **Land it.** `git push --force-with-lease`, then rebase-merge on GitHub so
   main stays linear. Comment the landing delta: the landed sha, what was
   dropped and why, and the pre-fold head — the force-push leaves that journey
   only in GitHub's event log, and it is what the classifier learns from.
   Close every sibling PR this one supersedes, naming it and why it lost. A
   decision left off the PR teaches nobody.
