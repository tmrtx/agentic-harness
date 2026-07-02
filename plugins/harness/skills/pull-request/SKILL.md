---
name: pull-request
description: Open, create, modify a pull request. Use whenever opening, creating, or updating a pull request, or writing a PR description or change summary.
---

# Pull Request

## Purpose
Enable verification of the work and provide specific feedback.

## Expected Outcome
A pull request description — the **walkthrough** — that:
- Lists each change with its location (file:line)
- Maps changes back to the original plan
- Highlights any divergences from the approved counterfactuals

## Why This Matters
Code review is cognitively expensive. A walkthrough reduces the burden by pre-organizing the changes according to the reviewer's mental model (the plan).

## Key Properties
- The walkthrough should be **diffable** - one should be able to compare "what we said we'd do" vs "what we did"
- The walkthrough should be **navigable** - file paths and line numbers enable jumping to specific changes
- The walkthrough should be **honest** - if something didn't go as planned, say so

## Anti-patterns
- Only documenting the happy path
- Writing documentation that requires reading all the code to understand
- Omitting the "why" (a list of changes without rationale is useless)
