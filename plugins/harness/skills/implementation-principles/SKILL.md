---
name: implementation-principles
code: CIA-7
prerequisites: homomorphism
description: CIA-7 — mandatory preparatory-refactoring principles that keep code structure homomorphic to the problem structure (make the change easy first, requisite variety, cohesion, coupling, small steps, connascence). Use whenever changing code structure — refactoring, extracting, moving, or reshaping code — or when a feature or fix does not land cleanly in the existing structure.
user-invocable: false
paths:
  - "**/*.py"
  - "**/*.nix"
  - "**/*.hs"
  - "**/*.el"
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

## 4. Practical Application

The cognitive symptoms, connascence taxonomy, planning checklist, and anti-patterns
that put these directives into practice live in
[`preparatory-refactoring.md`](preparatory-refactoring.md). Open it when a change does
not land cleanly and you need to reshape the structure first.

---

## 5. References & Changelog
