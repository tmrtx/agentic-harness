# Test Writing

The concrete practices that satisfy `CIA-8` (Executable Expectations): this skill applies
those directives, so see the control for the contract they serve. The sections below show
what homomorphic tests look like in code, and how to recognize a test that has drifted onto
solution structure.

## Every case must earn its variety

Each case names a distinct scenario — a different branch, boundary, or failure mode in
problem terms (`CIA-8.3`).

**Bad:**
```python
@pytest.mark.parametrize("qty", [1, 2, 3, 4, 5, 6, 7, 8, 9])
def test_no_discount_below_ten(qty): ...   # nine cases, one behavior — noise
```

**Good:**
```python
@pytest.mark.parametrize("qty, total", [(9, 90), (10, 95)])  # last full-price unit count,
def test_discount_starts_at_ten_units(qty, total): ...       # first discounted one
```

If two cases can only be told apart by reading the implementation, one of them is
coverage theater (`CIA-8.5`).

## Name tests after behavior

Test names and docstrings are **user questions**, not implementation concepts. A reader
should learn what the system does from the names alone, without opening the
implementation (`CIA-8.5`).

**Bad:**
```python
class TestOrderServiceImpl:   # implementation concept
class TestHelpers:            # organized by code layout, not behavior
def test_process_2(): ...     # names nothing
```

**Good:**
```python
class TestVolumeDiscount:
    def test_discount_applies_at_ten_units(self): ...
    def test_nine_units_pay_full_price(self): ...
```

## The oracle must be independent

The expected value is where a test gets its authority (`CIA-8.6`). Deriving it by re-running
the transformation under test — even reformulated, even "independently" recomputed from raw
inputs — produces a mirror: both sides encode the same understanding, so a misread spec
passes on both and only wiring mistakes can fail.

**Bad:**
```python
def test_total_applies_volume_discount(self):
    order = make_order(qty=12, unit_price=10.0)
    expected = 12 * 10.0 * (1 - DISCOUNT_RATE)   # the implementation, restated
    assert price(order) == expected              # code vs. itself — cannot disagree
```

**Good:**
```python
def test_twelve_units_pay_114(self):
    order = make_order(qty=12, unit_price=10.0)
    assert price(order) == 114.0   # 120 minus the 5% break, computed by hand
```

When outputs are too rich to hand-compute (series, frames, whole documents), construct
inputs whose answers are knowable without executing the formula: analytic cases (a constant
series' mean *is* that constant; returns built as `k·flow` recover slope `k` exactly),
invariants (appending future input must not change past output), and orderings ("the thin
day ranks below the deep day"). A formula-shaped spec is tested by pinning what the formula
*claims*, never by re-encoding the formula.

## Review symptoms

When reviewing tests, treat each of these as a symptom that a test is coupled to solution
structure rather than problem structure. Each points at the directive it breaks; the fix is
to rewrite the test to target the observable outcome.

- [ ] Mocks internal collaborators or asserts on call sequences — mechanism coupling (`CIA-8.2`).
- [ ] Expected value produced by re-running the transformation under test, or an equivalent reformulation of it — tautological oracle (`CIA-8.6`).
- [ ] Breaks during a pure refactoring even though behavior was preserved — solution-structure coupling (`CIA-8.4`).
- [ ] Has a case that cannot be traced to a real user scenario — non-requisite variety (`CIA-8.3`).
- [ ] Adds coverage with no corresponding behavioral specification — coverage theater (`CIA-8.5`).
