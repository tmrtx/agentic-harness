---
name: commit-protocol
description: This repository's commit protocol — the pre-commit test gate, the title format, and the PROBLEM/CAUSE/SOLUTION commit body. Use whenever committing in this repo — preparing, writing, or amending a commit, or running `git commit`.
---

# Commit Protocol

A commit is the smallest unit a reviewer reads.

Its message must let them reconstruct *why* the change exists before they read
the diff - the cause that forced it and the reasoning behind the solution.

Its message must give causal, teleological, and practical understanding of the commit.

1. **Pre-commit gate:** All tests must pass before committing.
2. Commit Title Format: <type>[OPTIONAL:<silo>][<component>]: <action-verb> <what-changed>
3. Commit Body Structure: Your commit message body should lead to reviewers gaining a causal, teleological and practical understanding of the commit:
   1. [PROBLEM] - Problem Statement: Formulate the problem that this commit will address (content after `[PROBLEM]` line).
   2. [CAUSE] - Root-Cause Analysis: Elaborate the causal mechanics that created this problem. What assumptions, design decisions, or implementation details led to this issue? (content after `[CAUSE]` line).
   3. [SOLUTION] - Solution Approach: Describe your approach and justify this approach over alternatives considered (content after `[SOLUTION]` line).
