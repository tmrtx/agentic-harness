---
name: scope-issue
description: Scope this session's change into a hermetic GitHub issue and open it
argument-hint: [what to scope - required]
disable-model-invocation: true
---

Target Scope: **$ARGUMENTS**

Your objective is to craft a github issue the target scope (using `gh issue create`).

The text must be **hermetic** — it stands alone for a reader with zero prior context: every
motivation, concept, finding, number, and decision lives IN the text. You may *link* a
notebook or PR but must never depend on one ("see the notebook" for rationale is banned).
Do **not** include a config / parameters section.

Extract the problem, rationale, decisions, and their supporting evidence from this
session's investigation.

Notes:
- Don't assume issue-specific background (only general repo-wide knowledge) from the readers.
- Utilize capabilities of markdown to the fullest to increase readability and reduce cognitive load.
- Follow a progressive disclosure writing style.

Reify the problem before the solution.

Sections:
- **Problem** — the gap in domain terms, assuming no background.
- **Approach** — what will change, the mechanism, the logic, the rationale behind the change.
- **Definition** — the precise change: names, signatures, formulas, or behaviour as applicable, in a table where it helps.
- **Context** — to illuminate the readers who haven't been through the same investigation.
- **Scope** — integration seams, and every design decision stated in-text with
  its rationale and numbers. Default to additive and behaviour-preserving.
- **Out of scope** — what you deliberately left out, for parsimony.
- **Executable Expectations** — concrete cases per `CIA-8`.
- **Expectations** — a checklist.
