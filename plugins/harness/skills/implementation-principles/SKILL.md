---
name: implementation-principles
code: CIA-7
prerequisites: homomorphism
description: CIA-7 — mandatory preparatory-refactoring principles that keep code structure homomorphic to the problem structure (make the change easy first, requisite variety, cohesion, coupling, small steps, connascence). Use whenever changing code structure — refactoring, extracting, moving, or reshaping code — or when a feature or fix does not land cleanly in the existing structure.
user-invocable: false
---

# CIA-7: Implementation Principles

## 1. Purpose & Scope

This control defines mandatory **Preparatory Refactoring** regulations to maintain **structural integrity** throughout the project. It targets all code modifications—features, fixes, and refactors—ensuring changes land cleanly without forcing functionality into unsuitable structures. Non-compliance compounds technical debt.

---

## 2. Core Principle: Homomorphism

Code structure must be **homomorphic to the problem structure**.

**Homomorphism litmus test**: a change in requirements should produce a code
change proportional in size and in locality. If either condition fails—if a
small requirement change forces a large rewrite, or scatters edits across many
units—the code is non-homomorphic and must be refactored before the modification is made.

**Why this matters for code**: modifying non-homomorphic code compounds cost.
Each mismatch between problem structure and code structure adds coupling. if
requirements grow linearly (O(N)), the effort required to implement them will
grow quadratically (O(N²)) or worse, each change will make the next harder. The
time "saved" is borrowed at high interest—paid back through bugs, difficult
debugging, and slower future development.

---

## 3. Control Directives

Below are **non-negotiable** directives constituting the CIA-7 Implementation Integrity mandate.

1. **CIA-7.1 Make the Change Easy First**
   - *Guiding Principle*: "Make the change easy, then make the easy change." — Kent Beck
   - **Requirement**: When a change doesn't map cleanly to the existing structure, refactor the structure first so the change becomes trivial. Separate structural improvements from behavioral changes.
   - **Rationale**: Preparatory refactoring reshapes the solution structure until it becomes homomorphic to the problem structure. Then the change lands exactly where it should, affecting only what it should.
   - **Diagnostic**: Mentally simulate the change. If you must trace through scattered locations, blur abstraction levels, or fear breakage—the structure needs prep work first.

2. **CIA-7.2 Requisite Variety**
   - *Guiding Principle*: "Code has exactly the structure the problem requires—no more, no less."
   - **Requirement**: Code must match problem complexity. Insufficient abstraction and excessive indirection are both violations. (See `homomorphism` for the general dumber/noisier framing.)
   - **Rationale** (code-specific symptoms):
     - **Insufficient variety** (code *dumber* than the problem): repeating patterns manually, coordinating by convention, verbosity compensating for concepts the code cannot name. Remedy: reify the latent abstraction.
     - **Non-requisite variety** (code *noisier* than the problem): handling identical cases, over-parameterization, layers that relocate complexity without reducing it. Remedy: attenuate or consolidate.
   - **Diagnostic**: For each abstraction, ask: "Does this earn its cognitive cost through reuse, variation isolation, or scope reduction?" If not, it's non-requisite.

3. **CIA-7.3 Cohesion**
   - *Guiding Principle*: "Related things belong together."
   - **Requirement**: Code that changes together must live together. A concept must not be scattered across modules.
   - **Rationale**: Low cohesion forces you to gather pieces from everywhere to understand one thing. This is the structural cause of "can't reason locally."
   - **Diagnostic**: To understand concept X, how many files must you open? If more than one, cohesion may be too low.

4. **CIA-7.4 Coupling**
   - *Guiding Principle*: "Unrelated things must not be entangled."
   - **Requirement**: Changes must not propagate across module boundaries unnecessarily. Modules must not depend on each other's internals.
   - **Rationale**: High coupling means you can't change X without changing Y. This is the structural cause of "fear of breakage."
   - **Diagnostic**: If changing module A requires changes to module B (and they're not inherently related), coupling is too high.

5. **CIA-7.5 Small Steps**
   - *Guiding Principle*: "Many tiny refactorings beat one big restructuring."
   - **Requirement**: Each refactoring step must leave the code working. Run tests at each modification. Never mix refactoring with behavior changes in a single commit.
   - **Rationale**: Atomic steps are safe, reviewable, and bisectable. Big-bang changes are high risk and hard to debug.
   - **Diagnostic**: Can you revert to any intermediate state and have working code? If not, steps are too large.

---

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

---

## 6. References & Changelog
