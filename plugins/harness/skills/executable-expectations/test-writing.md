# Test Writing

The concrete practices that satisfy `CIA-8` (Executable Expectations): this skill applies
those directives, so see the control for the contract they serve. The sections below show
what homomorphic tests look like in code, and how to recognize a test that has drifted onto
solution structure.

## Test class naming

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

## Assert against known values

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

## Caching tests need fresh instances

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

## No fixtures in specs

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

## Before writing a test

1. What user question does this class answer?
2. What known expected value can I assert against?
3. Am I testing state or behavior? (Behavior survives refactoring)
4. Would this break if I renamed a column? (If yes, rewrite)

## Review symptoms

When reviewing tests, treat each of these as a symptom that a test is coupled to solution
structure rather than problem structure. Each points at the directive it breaks; the fix is
to rewrite the test to target the observable outcome.

- [ ] Mocks internal collaborators or asserts on call sequences — mechanism coupling (`CIA-8.2`).
- [ ] Breaks during a pure refactoring even though behavior was preserved — solution-structure coupling (`CIA-8.4`).
- [ ] Has a case that cannot be traced to a real user scenario — non-requisite variety (`CIA-8.3`).
- [ ] Adds coverage with no corresponding behavioral specification — coverage theater (`CIA-8.5`).
