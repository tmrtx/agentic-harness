---
name: pull-request
description: Open, create, modify a pull request. Use whenever opening, creating, or updating a pull request, or writing a PR description or change summary.
---

# Pull Request

## Purpose
Enable verification of the work and provide specific feedback.

## Expected Outcome
A pull request description — the **walkthrough** — that:
- Formulates the problem that PR aims to address.
- Documents the process followed to produce the PR.
  * The walkthrough should document divergences encountered, i.e. "what we said we'd do" vs "what we did".
- Highlights the key events.

## Why This Matters
Code review is cognitively expensive. A walkthrough reduces the burden by pre-organizing the changes according to the reviewer's mental model.

## Key Properties
- The walkthrough must be **hermetic** - it stands alone for a reader with zero prior context: every motivation, decision, and number lives IN the text. External links are allowed only for genuine dependencies (e.g. the repo a PR consumes) or out-of-scope tracking issues - never as required reading
- The walkthrough should be **navigable** - file paths and line numbers enable jumping to specific changes
- The walkthrough should be **honest** - if something didn't go as planned, say so

## Anti-patterns
- Writing documentation that requires reading all the code to understand
- Omitting the teleology (a list of changes without rationale is useless)
