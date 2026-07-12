# Test Writing

The concrete practices that satisfy `CIA-8` (Executable Expectations): this skill applies
those directives, so see the control for the contract they serve. The sections below show
what homomorphic tests look like in code, and how to recognize a test that has drifted onto
solution structure.

For a test to earn its place, require at least one:

| Criterion                  | Question to ask                                                            |
|----------------------------|----------------------------------------------------------------------------|
| Non-trivial transformation | Could this computation be wrong? (edge cases, boundaries, algorithm logic) |
| Low observability          | Would failure be silent or delayed—unnoticed during normal use?            |
| Contract stability         | Must this behavior remain stable across future changes?                    |

## Test behavior not identity

- **Specification test**: Encodes a behavioral contract that (a) involves
  computation/transformation, (b) has non-trivial failure modes, and (c)
  provides regression detection for invariants you might violate unknowingly in
  the future.
- **Tautology test**: Asserts `x == x` with extra ceremony. There's no
  transformation being validated—only that you copy-pasted consistently.

Tautology tests create **Connascence of Value**—test and implementation share a
literal, so any change to one demands a mechanical change to the other, with
zero bug-catching power.

The tautology test catches nothing—change the constant, change the test, no bug
detected. Test and implementation share a literal, so any edit demands a
mechanical mirror-edit with zero bug-catching power.

Tautology tests test identity, not behavior.

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

## Review symptoms

When reviewing tests, treat each of these as a symptom that a test is coupled to solution
structure rather than problem structure. Each points at the directive it breaks; the fix is
to rewrite the test to target the observable outcome.

- [ ] Mocks internal collaborators or asserts on call sequences — mechanism coupling (`CIA-8.2`).
- [ ] Breaks during a pure refactoring even though behavior was preserved — solution-structure coupling (`CIA-8.4`).
- [ ] Has a case that cannot be traced to a real user scenario — non-requisite variety (`CIA-8.3`).
- [ ] Adds coverage with no corresponding behavioral specification — coverage theater (`CIA-8.5`).
