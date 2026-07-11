---
name: commit-protocol
description: This repository's commit protocol — the pre-commit test gate, the title format, and the PROBLEM/CAUSE/SOLUTION commit body. Use whenever committing in this repo — preparing, writing, or amending a commit, or running `git commit`.
---

# Commit Protocol

A commit is the smallest unit a reviewer reads.

Its message must give teleological, causal, and practical understanding of the commit.

1. **Pre-commit gate:** All tests must pass before committing.
2. Commit Title Format: <type>[OPTIONAL:<silo>][<component>]: <action-verb> <what-changed>
3. Commit Body Structure: Commit message body should lead to reviewers gaining a causal, teleological and practical understanding of the commit:
   1. [PROBLEM] - Problem Statement: Formulate the problem that this commit will address (content after `[PROBLEM]` line).
   2. [ROOT-CAUSE] - Root-Cause Analysis: Elaborate the causal mechanics that created this problem (content after `[CAUSE]` line).
   3. [CHANGE] - The Change: Describe your approach and justify this approach over alternatives considered (content after `[CHANGE]` line).

Writing instructions:
- Follow BLUF (bottom line up front), Minto Pyramid, Given-New Principles for writing the commit message.
- Prefer an active voice over a passive voice.
- Avoid mixing abstraction levels in the text.
