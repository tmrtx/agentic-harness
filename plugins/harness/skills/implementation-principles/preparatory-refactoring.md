# Preparatory Refactoring

## 4. Compliance & Enforcement

1. **Monitoring**
   - Code reviews verify changes are homomorphic: small requirement changes should produce small code changes.
   - Refactoring PRs are audited for behavior preservation—tests must not change during pure refactoring.
   - Abstractions are reviewed for requisite variety: each must earn its cognitive cost.

2. **Non-Compliance Indicators**
   - Changes scattered across many files for a simple requirement (non-homomorphic structure).
   - Single-use abstractions that add indirection without reducing complexity (non-requisite variety).
   - Refactoring mixed with behavior changes in the same commit (violates small steps).
   - Design patterns applied without diagnosing the specific structural problem (cargo-culting).

3. **Anti-Patterns**

   | Anti-Pattern | Violates |
   |--------------|----------|
   | Big bang refactoring | CIA-7.5 |
   | Speculative refactoring | CIA-7.2 |
   | Refactoring without tests | CIA-7.5 |
   | Cargo-culting patterns | CIA-7.1 |
   | "No time" fallacy | CIA-7.1 |

   - **Big bang refactoring** — High risk, hard to review, difficult to bisect. Prefer the strangler fig pattern: gradually replace components while keeping the system running.
   - **Speculative refactoring** — Refactoring for hypothetical future changes. You don't know what structure future changes will need. Manifestations: premature extraction, speculative hierarchies, pattern application before understanding variation points. Diagnose *current* friction first. Often the need is to consolidate, not extract.
   - **Refactoring without tests** — Structural changes without a safety net. Write characterization tests first (capture current behavior), then refactor.
   - **Cargo-culting patterns** — Applying patterns as "best practice" without diagnosing the structural problem. Patterns are remedies for specific ailments. Diagnose first—identify the cohesion/coupling issue—then select the pattern.
   - **"No time" fallacy** — Skipping prep under time pressure. This usually takes *longer* and creates bugs. Prep refactoring pays for itself in reduced debugging.

---

## 5. Practical Application

### 5.1 Cognitive Symptoms

These are signs of non-homomorphic code—what you experience during mental simulation:

| Symptom | Structural Cause |
|---------|------------------|
| Can't reason locally | Low cohesion |
| Abstraction levels blur (SLAP violation) | Poor layering |
| Irrelevant details intrude | Non-requisite variety |
| Fear of breakage | High coupling |

These symptoms are *outcomes*. To fix them, address the structural causes.

### 5.2 Connascence Taxonomy

Connascence is a detailed taxonomy of coupling. Reduce connascence by: lowering strength (identity → value → name), improving locality (keep connascent code close), reducing degree (fewer components involved).

| Type | Description | Refactoring Direction |
|------|-------------|----------------------|
| Name | Must agree on a name | Weakest; often acceptable |
| Type | Must agree on a type | Use polymorphism to abstract |
| Meaning | Must agree on meaning of values (e.g., `1 = admin`) | Replace with explicit types/enums |
| Position | Must agree on order of parameters | Use named parameters, objects |
| Algorithm | Must agree on an algorithm (e.g., hashing) | Consolidate into single source |
| Execution | Must execute in a specific order | Make ordering explicit or remove dependency |
| Timing | Must execute at specific times relative to each other | Redesign to remove temporal dependency |
| Value | Values must change together | Consolidate into single unit |
| Identity | Must reference the same object | Strongest; work hard to eliminate |

### 5.3 Planning Checklist

Once friction points are identified, plan a sequence of small, safe refactorings:

1. **List the refactorings needed** — Be specific: "extract method X from Y", "move function A to module B"
2. **Order by dependency** — Some refactorings enable others; find the right sequence
3. **Keep each step atomic** — Each refactoring should leave the code working
4. **Preserve behavior** — Preparatory refactoring changes structure, not behavior

Present the plan before executing:
- Explain what structural issues you identified
- Describe the refactorings you'll perform and why
- Clarify how this makes the eventual change easier
- Then execute the refactorings before the feature change
