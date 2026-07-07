---
name: executable-expectations
code: CIA-8
prerequisites: homomorphism
description: CIA-8 — mandatory test-first regulations; tests are written before implementation, assert observable outcomes rather than mechanisms, derive expected values independently of the implementation, survive refactoring unchanged, and serve as the specification. Use whenever writing or modifying tests, implementing a feature or fix that changes behavior, doing TDD, or evaluating test coverage or test quality.
user-invocable: false
paths:
  - "**/*.py"
  - "**/*.nix"
  - "**/*.hs"
  - "**/*.el"
---

# CIA-8: Executable Expectations

## 1. Purpose & Scope

This control defines mandatory **Test-First** regulations to maintain **system integrity** throughout the project. It targets all new code, features, and refactor efforts, ensuring tests provide **real-world coverage** and remain aligned with user needs. Non-compliance with these directives will lead to major penalties.

---

## 2. Core Principle: Test Homomorphism

Tests must be **homomorphic to the problem structure**, not the solution structure.

**Homomorphism litmus test**: a small change in requirements should produce a small,
localized change in tests. A pure refactoring (structure changed, behavior preserved)
should produce **zero** test changes.

**Why this matters for tests**: non-homomorphic tests create false confidence. They
pass when code matches an implementation pattern but fail to catch behavioral
regressions. Worse, they resist refactoring—breaking whenever structure changes—creating
pressure to avoid improving code. Tests coupled to solution structure are liabilities
disguised as assets.

---

## 3. Control Directives

Below are **non-negotiable** directives constituting the CIA-8 Testing Integrity mandate.

1. **CIA-8.1 Write Tests Before Implementation**
   - *Guiding Principle*: "A failing test defines the gap you're about to fill."
   - **Requirement**: Every new or modified feature must begin with at least one failing test that captures intended behavior before coding the solution.
   - **Rationale**: Writing tests first forces problem-structure thinking before a solution structure exists to couple to. Post-hoc tests tend to mirror implementation because that's what's in front of you. But order alone is not independence: a test derived from the same formula the code will implement mirrors the code before the code exists (`CIA-8.6`).

2. **CIA-8.2 Test Outcomes, Not Mechanisms**
   - *Guiding Principle*: "Validate what the system does, not how it does it."
   - **Requirement**: Tests must assert on observable outcomes—outputs, state changes visible to users, system behaviors—never on internal mechanisms, call sequences, or implementation details.
   - **Rationale**: Users care about outcomes. Mechanisms are implementation details that may change during refactoring. Tests coupled to mechanisms are non-homomorphic: they break when structure changes even though behavior is preserved.
   - **Diagnostic**: If a test checks "was this method called" or "is this internal state set," it's testing solution structure. Ask instead: "What outcome should the user observe?"

3. **CIA-8.3 Requisite Variety**
   - *Guiding Principle*: "Tests capture exactly the problem's variety—no more, no less."
   - **Requirement**: Every test case must map to a real scenario, edge case, or failure mode that users could encounter. Tests covering impossible cases or implementation artifacts are prohibited. (See `homomorphism` for the general dumber/noisier framing.)
   - **Rationale** (test-specific symptoms):
     - **Insufficient variety** (test suite *dumber* than the problem): tests miss important cases; bugs reach production that "passed all tests."
     - **Non-requisite variety** (test suite *noisier* than the problem): tests cover cases that don't matter—excessive maintenance, busywork, "coverage theater."
   - **Diagnostic**: For each test case, ask: "What real scenario does this represent?" If you cannot name one, the test is non-requisite variety and must be removed.

4. **CIA-8.4 Refactoring Immunity**
   - *Guiding Principle*: "Red → Green → Refactor—and the tests don't break."
   - **Requirement**: Tests must survive pure refactoring unchanged. If refactoring breaks tests, those tests must be rewritten to target problem structure.
   - **Rationale**: The refactor step is the proof of homomorphism. If tests let you freely restructure code without breaking, they're testing the right thing. If they break, they were coupled to solution structure.
   - **Diagnostic**: Before committing tests, mentally simulate refactoring the implementation. Would the tests still pass? If not, you're testing the wrong thing.

5. **CIA-8.5 Tests Are the Specification**
   - *Guiding Principle*: "Tests define the formal contract for the system."
   - **Requirement**: All behavioral requirements must be expressed as tests. If behavior isn't specified in a test, it's not a requirement—it's an implementation accident that may change. Non-cosmetic changes are prohibited without accompanying test additions/modifications.
   - **Rationale**: Tests as specification ensures the problem structure is explicitly captured. Reading the tests should tell you what the system does from a user's perspective, without needing to read the implementation.
   - **Diagnostic**: Can someone understand the system's behavior by reading only the tests? If tests only make sense after reading the code, they're not specifying problem structure—they're annotating solution structure.

6. **CIA-8.6 Independent Oracles**
   - *Guiding Principle*: "A test must be able to disagree with the code it tests."
   - **Requirement**: Expected values must come from a source independent of the implementation: hand-computed constants, constructed inputs with analytically known answers, properties and invariants (causality, monotonicity, conservation, orderings), or contrasts between scenarios. A test must never derive its expectation by re-executing the transformation under test—nor an equivalent reformulation of it, even one recomputed "independently" from raw inputs.
   - **Rationale**: A mirrored oracle is the degenerate case of solution-structure coupling: the test does not merely couple to the solution, it *restates* it, so code is verified against itself. It reproduces its author's misunderstanding—a misread spec yields the same wrong value on both sides and the test passes—and it silently blesses divergences from the spec instead of surfacing them. Such a test can catch wiring mistakes, nothing more. This applies with full force when the specification is itself a formula: re-encoding the formula in the test satisfies `CIA-8.5` in letter while voiding it in substance.
   - **Diagnostic**: For each assertion, ask: "Where does the expected value come from—could this test fail if I had misread the spec?" If the expectation is produced by the same computation the implementation performs, rewrite the oracle, not the assertion: pin the spec's claims on cases whose answers are knowable *without executing it*—degenerate inputs with closed-form answers, required invariances, known orderings.

---

## 4. Practical Application

The concrete practices that satisfy these directives — worked examples and a review
checklist — live in [`test-writing.md`](test-writing.md). Open it when writing,
structuring, or reviewing tests.
