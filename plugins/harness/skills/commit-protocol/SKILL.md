---
name: commit-protocol
description: This repository's commit protocol — the pre-commit test gate, the title format, the PROBLEM/ROOT-CAUSE/CHANGE/ORACLE commit body, and the steering-text token-diff line. Use whenever committing in this repo — preparing, writing, or amending a commit, or running `git commit`.
---

# Commit Protocol

A commit is the smallest unit a reviewer reads.

Its message must give teleological, causal, and practical understanding of the commit.

1. **Pre-commit gate:** All tests must pass before committing.
2. Commit Title Format: <type>[OPTIONAL:<silo>][<component>]: <action-verb> <what-changed>
3. Commit Body Structure: Commit message body should lead to reviewers gaining a causal, teleological and practical understanding of the commit:
   1. [PROBLEM] - Problem Statement: Formulate the problem that this commit will address (content after `[PROBLEM]` line).
   2. [ROOT-CAUSE] - Root-Cause Analysis: Elaborate the causal mechanics that created this problem (content after `[ROOT-CAUSE]` line).
   3. [CHANGE] - The Change: Describe your approach and justify this approach over alternatives considered (content after `[CHANGE]` line).
      - Steering-text commits close this section with a token-cost line. Steering text is anything loaded into an agent's or model's context to direct behavior: CLAUDE.md, skills, agent definitions, commands, prompts. Context is the budget such text spends in every future session; the line puts that recurring cost next to the content it buys, so the reviewer weighs both at once. Compute it with this skill's `scripts/token_diff.py` - run with no arguments it measures the staged steering files; pass paths to widen or narrow the set - which counts the diff through the Anthropic count_tokens endpoint (counts are model-specific estimates, so the line names the model): `Token diff: +<added>/-<removed> (net <n>, <model>)`. When counting is impossible - no credentials, no network - record `Token diff: unavailable (<reason>)`: an unmeasured cost stays visible where a silent omission would hide it. Paste the script's output line verbatim - a paraphrase obscures the actionable reason when counting degrades.
   4. [ORACLE] - The Oracle: One labeled line per element - Class and Ground truth each with the reasoning for the classification, Mechanism, and Oracle (the ORC code from oracle-state.json) (content after `[ORACLE]` line).
4. **Oracle trailer:** Each commit carries an `Oracle: [<oracle-class>|<ground-truth>]` git trailer. The dimensions come from the `oracle-ladder` skill. The ledger (`oracles.jsonl`) condenses trailer, verification, and target per change.

Writing instructions — the reader is a maintainer or model under load; structure serves their eyes, not the author's:
- BLUF; one idea per sentence; plain statement before term of art; active voice.
- Bullets for parallel facts (mechanics, deletions, alternatives, mechanism items); blank lines between idea groups. Section labels alone are not structure.
- Put detail where the reader's uncertainty is: a self-evident diff earns a compressed [CHANGE]; a non-obvious motivation earns an expanded [PROBLEM].
- Ground every statement in the commit itself: no review-round narration, no PR/issue/governance-code chaining; state judgments in problem terms.
- Wrap near 72 columns; one abstraction level per sentence.
