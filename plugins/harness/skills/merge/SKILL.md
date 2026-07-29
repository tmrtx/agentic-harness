---
name: merge
description: Assist with landing a pull request end to end — rebase, fold the journey, drop scaffolding, repair messages, push, rebase-merge, record the landing.
disable-model-invocation: true
---

your objective is to move a pull request over the finish line.

your tasks will involve actions like:
- rebasing because the main history was rewritten
- determining the whether to keep or discard commits with the assistance of `${CLAUDE_SKILL_DIR}/scripts/classify_stack.py`
- rewrite the commit stack by folding commits, edit out suites failing the
  earn-its-place table (`harness:executable-expectations`) surgery on the
  commits themselves and/or rewriting commit messages.
- merge the pull request
- comment on the pull request when asked to close.

keep in mind:
- you are not concerned with the already merged commits.
