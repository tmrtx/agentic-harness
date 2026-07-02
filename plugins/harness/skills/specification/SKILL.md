---
name: specification
description: This repository's planning methodology — turn an implicit problem into a plan a reviewer can predict and shape before any code is written, via Problem Reification → Counterfactual Demonstration → Feedback Integration. Use whenever scoping or planning a non-trivial change, writing a spec or plan document, or proposing what code will look like before implementing it.
---

# Specification

The objective is to facilitate reviewers three capabilities:
- **Predict** what will change, before implementation begins.
- **Understand** the proposed change well enough in order to provide feedback before it's too late.
- **Explicate** the outcome after the plan is implemented.

## Part 1: Problem Reification

### Purpose
Transform an implicit problem ("this code feels wrong") into an explicit structure that everyone can reason about.

### Expected Outcome
A **problem specification** that:
- Names the domain concepts (e.g., "Report has Sections, each Section has Metrics")
- Identifies structural mismatches between problem and implementation
- Uses the stakeholder's vocabulary, not generic software patterns

### Why This Matters
One cannot evaluate a solution without first agreeing on the problem. A refactoring plan that says "extract method" is useless. A plan that says "the report has 5 sections but the code has 12 functions" is actionable.

### Anti-patterns
- Jumping to implementation patterns (SOLID, DRY) without showing the problem structure
- Using abstract vocabulary ("improve cohesion") instead of concrete domain terms
- Assuming the reader shares your mental model of the codebase

---

## Part 2: Counterfactual Demonstration

### Purpose
Demonstrate what the code *could* look like, enabling evaluation of the proposed change before committing.

### Expected Outcome
For each identified issue, provide:
- **Current code snippet** (the problem, in context)
- **Proposed code snippet** (the solution, in same context)
- **Value statement** (what becomes easier/harder after the change)

### Why This Matters
Abstractions are hard to evaluate. Concrete code is easy to evaluate. A counterfactual makes the abstract concrete.

The counterfactual is a **contract**: "If you approve this, the final code will look like this."

### Key Properties
- Counterfactuals must be **idiomatic** to the codebase's existing style
- Counterfactuals must be **minimal** - show only what changes, not a rewrite
- Counterfactuals must be **honest** - if the real implementation will be messier, show that

### Anti-patterns
- Showing idealized code that won't survive contact with real constraints
- Omitting the "value statement" (reviewers can't evaluate without knowing the goal)
- Providing counterfactuals in a style inconsistent with the codebase (e.g., OOP when it prefers functional)


## Success Criteria

A collaboration succeeds when:

1. **The reviewer could have written the plan themselves** - the plan reflects their intent, not your preferences
2. **The implementation matches the counterfactuals** - no surprises
3. **Reviewers can provide specific feedback** - they know exactly where to look and what to comment on
