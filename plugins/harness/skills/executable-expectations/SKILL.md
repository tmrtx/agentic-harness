---
name: executable-expectations
code: CIA-8
prerequisites: homomorphism
description: CIA-8 — mandatory test-first regulations; tests are written before implementation, assert observable outcomes rather than mechanisms, survive refactoring unchanged, and serve as the specification. Use whenever writing or modifying tests, implementing a feature or fix that changes behavior, doing TDD, or evaluating test coverage or test quality.
user-invocable: false
paths:
  - "**/*.py"
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
   - **Rationale**: Writing tests first forces problem-structure thinking before a solution structure exists to couple to. Post-hoc tests tend to mirror implementation because that's what's in front of you. Test-first ensures homomorphism by design.

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

---

## 4. Compliance & Enforcement

1. **Monitoring**
   - Code reviews verify tests are homomorphic to problem structure: asserting outcomes, not mechanisms.
   - Refactoring PRs are audited—if tests broke during pure refactoring, those tests violated homomorphism and must be flagged.
   - Test cases are reviewed for requisite variety: each must map to a nameable real scenario.

2. **Non-Compliance Indicators**
   - Tests that mock internal collaborators or assert on call sequences (mechanism coupling).
   - Tests that break during refactoring despite behavior being preserved (solution structure coupling).
   - Test cases that cannot be traced to a real user scenario (non-requisite variety).
   - Coverage without corresponding behavioral specification (coverage theater).

3. **Non-Compliance Handling**
   - Submitting a PR with non-homomorphic tests (mechanism-coupled, refactoring-fragile, or non-requisite variety) will trigger a **Critical Test Integrity Review**.
   - Violations require test rewrites targeting problem structure before merge.

4. **Escalation**
   - Repeated violations will trigger a **Formal Compliance Audit**.

---

## 5. Practical Application

### 5.1 Test Class Naming

Class names and docstrings should be **user questions**, not implementation concepts.

**Bad:**
```python
class TestExperimentPairedLosses:  # Implementation concept
class TestExperimentAnswersResearcherQuestions:  # Vague, not a question
```

**Good:**
```python
class TestUncertaintyQuantification:
    """Does the candidate improve on the baseline?"""

class TestModelCaching:
    """Are identical configs reused across experiments?"""

class TestFoldConsistency:
    """Is the improvement consistent across time periods?"""
```

Each class answers one specific question the user has.

### 5.2 Assert Against Known Values

Never assert `is not None` or check column existence. Assert against expected values.

**Bad:**
```python
def test_can_trace_to_trade(self, experiment):
    result = experiment.run(config)
    best = result.paired_losses.nlargest(1, "difference").iloc[0]

    assert best["symbol"] is not None  # What does this prove?
    assert best["timestamp"] is not None
```

**Good:**
```python
def test_best_improvement_maps_to_known_trade(self, experiment):
    result = experiment.run(config_with_known_best_trade)
    best = result.paired_losses.nlargest(1, "difference").iloc[0]

    assert best["symbol"] == "BTCUSDT"
    assert best["timestamp"] == expected_timestamp
```

The good test sets up a scenario where we *know* what the answer should be.

### 5.3 Caching Tests Need Fresh Instances

To verify caching, create separate instances with the same config.

**Bad:**
```python
def test_caching(self, experiment):
    experiment.run(config)  # First run
    experiment.run(config)  # Same object - proves nothing about cache
```

**Good:**
```python
def test_shared_baseline_trains_once(self, make_experiment):
    exp1 = make_experiment(baseline=shared, candidate=a)
    exp2 = make_experiment(baseline=shared, candidate=b)

    exp1.run(config1)  # Trains shared + a
    exp2.run(config2)  # Reuses shared, trains only b

    assert training_calls["shared"] == 1
```

### 5.4 No Fixtures in Specs

Specs describe *what*, not *how*. Implementation details like fixtures belong in test files, not planning docs.

**Bad (in a spec):**
```python
@pytest.fixture
def make_training_fn():
    def _make(samples):
        # ... implementation details
```

**Good (in a spec):**
```python
class TestUncertaintyQuantification:
    def test_better_candidate_shows_high_confidence(self, experiment):
        result = experiment.run(config_where_candidate_improves)
        assert result.p_improvement > 0.9
```

### 5.5 Diagnostic

Before writing a test:
1. What user question does this class answer?
2. What known expected value can I assert against?
3. Am I testing state or behavior? (Behavior survives refactoring)
4. Would this break if I renamed a column? (If yes, rewrite)

---

## 6. References & Changelog
