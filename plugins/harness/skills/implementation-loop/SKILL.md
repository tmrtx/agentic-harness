---
name: implementation-loop
description: This repository's implementation workflow — transform an approved plan into code through a tight feedback loop with the test suite, decomposing every change into the smallest atomic iterations ("make the change easy, then make the easy change"). Use whenever implementing a plan or spec, coding a feature or fix, refactoring, or making any code change in this repo.
---

# Implementation Protocol
## Purpose
Transform the intentions into implementation through a tight feedback loop with the test suite.

## Core Principle: Make the Change Easy, Then Make the Easy Change

This is `CIA-7.1` applied to the workflow. Every implementation step has two parts:
1. **Make the change easy**: Add tests, refactor prerequisites, create scaffolding—without changing behavior
2. **Make the easy change**: Now that the path is clear, make the actual change

This separation is critical. Mixing "preparation" with "change" creates risk and obscures intent.

## Expected Outcome
Code changes that:
- Match the counterfactuals (within reasonable adaptation to real constraints)
- Are validated by the test suite at every step
- Leave the test suite stronger than before

## Why This Matters
The counterfactuals were a contract. The implementation must honor that contract, or the approval was meaningless. The test suite is the mechanism that enforces this contract.

## Toolkit

### Tight Feedback Loop

**Running tests is free and fast. Use this to your advantage.**

Decompose every change into the smallest possible iterations. The more iterations, the better. Each iteration should be:
1. A single, atomic modification
2. Immediately validated by the test suite
3. Committed or ready to commit

For each iteration:

1. **Run tests**: Verify baseline is green before you touch anything.
2. **Make the smallest possible change**: One function, one rename, one extraction. Not two.
3. **Run tests again**: Must pass. If red, fix immediately—don't proceed.
4. **Repeat**: The next iteration starts now.

**Prefer 20 tiny iterations over 3 medium ones.** Each test run takes seconds. Each debugging session after a big change takes minutes to hours. The math favors many small steps.

Signs you're doing it right:
- You run tests after every change.
- Each change is trivially correct by inspection
- When a test fails, you know exactly which line caused it

Signs you're doing it wrong:
- You've gone minutes without running tests
- You're "almost done" with a change that touches 5 files (if a change is large, step back, apply preparatory refactoring to make changing easier, then make the change).
- You're not sure which of your recent edits broke the test (the scope of your changes are too big and violate TDD)

### Test-Driven Refactoring

Refactoring is not an excuse to skip refining tests—it's the opposite. The discipline
lives in `CIA-8` and `CIA-7.5`: before touching code, ensure tests characterize
the behavior; if they're missing, write characterization tests first against the
current implementation as your safety net.

The test suite is your safety net—if it has holes, patch them before jumping.

### Key Properties
- **Incremental delivery**: Each logical unit of change is verified before proceeding
- **Test-first verification**: Run existing tests after each change to catch regressions early
- **Test-augmented implementation**: Add tests where coverage is missing before making changes
- **Divergence disclosure**: If implementation must diverge from the counterfactual, explain why

### Anti-patterns
- Batching all changes into one massive commit
- Skipping tests because "it's just refactoring"
- Editing code and its tests in one untested step. change one, run the suite, then the other, so a failure points at a single edit (this is about cadence; CIA-8.5 still requires that behavior changes come *with* tests)
- Running tests only at the end (delays feedback, increases debugging cost)
