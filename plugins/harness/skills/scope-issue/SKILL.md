---
name: scope-issue
description: Scope this session's change into a self-contained GitHub issue and open it
argument-hint: [what to scope - required]
disable-model-invocation: true
---

Target Scope: **$ARGUMENTS**

You will open a GitHub issue for the target scope (`gh issue create`).

The issue's job is to make the reader (a) believe the problem is real, (b)
understand why it matters, and (c) recognize when it's done.

Hard constraints:
- **Hermetic**: every motivation, finding, and number lives in the text.
  You may link a notebook or PR; you must never depend on one.
- **No solution design**: no signatures, no formulas, no file lists, no
  parameter tables, no architecture. If this session already settled a
  decision that genuinely constrains the solution, state it in one line
  with its reason. That is the ceiling.
- **One screen**: if it doesn't fit, you are designing, not scoping.
