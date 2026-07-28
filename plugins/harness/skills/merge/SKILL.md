---
name: merge
description: Land a reviewed PR end to end — rebase, fold the journey, drop scaffolding, repair messages, push, rebase-merge, record the landing. Use only when the user invokes /merge; never on the implementer's path, whose stack is a licensed scratchpad.
disable-model-invocation: true
---

# /merge — land it so no hand has to

Hand-landing leaks: fixes reverted, references dangling, the reasoning behind
every drop dying at the click.

1. **Rebase** onto the base branch.
2. **Judge** with `${CLAUDE_SKILL_DIR}/scripts/classify_stack.py`: each commit
   is `fold` (it answers this branch's own history) or `keep`. It is ≈0.69 both
   ways — confirm every verdict, since a false fold destroys state.
3. **Rewrite the stack** in one `git rebase -i`: `fixup` each `fold` into the
   commit it corrects, `edit` out suites failing the earn-its-place table
   (`harness:executable-expectations`), reword each message to its landed
   content (`harness:commit-protocol`). Two `keep`s never become one.
4. **Verify**: one commit per `keep`, tree unchanged but for the dropped suites.
5. **Land**: `git push --force-with-lease`, rebase-merge, then comment the sha,
   the drops and why, and the pre-fold head the force-push strands. Close every
   sibling PR this supersedes, naming it and why it lost.
