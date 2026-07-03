# Test Writing

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
