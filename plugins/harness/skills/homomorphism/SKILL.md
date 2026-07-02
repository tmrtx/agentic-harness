---
name: homomorphism
description: The foundational principle that a solution's shape must mirror the problem's structure — the homomorphism test, requisite variety, and single source of truth. Use when reasoning about design quality, code or test structure, duplication, abstraction, indirection, or when CIA-7, CIA-8, or CIA-9 cite homomorphism as a prerequisite.
user-invocable: false
metadata:
  code: homomorphism
---

# Homomorphism

A solution must be **homomorphic to the problem structure**: its shape mirrors how users
think about what the system should do, not the accidents of how it happens to be built.
This holds for any solution artifact — code, tests, or documents alike.

## Problem structure vs. solution structure

- **Problem structure**: The domain concepts, user goals, and behavioral requirements—how users think about what the system should do.
- **Solution structure**: The code organization, class hierarchies, and implementation mechanisms—how the system happens to be built.

## The homomorphism test

A change local in the problem domain should map to a change local in the solution domain.

A small change in requirements should produce a small, localized change in the solution.
If a small requirement change forces a large or scattered change, the solution is
non-homomorphic and needs rework.

## Why it matters

Non-homomorphism is a liability disguised as an asset. Forced structure compounds cost:
each forced change makes the next harder, and the time "saved" is borrowed at high
interest—repaid through bugs, difficult debugging, and resistance to change.

## Requisite variety

A direct corollary: the solution must carry **exactly the problem's variety—no more, no
less**.

- **Insufficient variety**: the solution is *dumber* than the problem—manual repetition,
  coordination by convention, verbosity standing in for a concept the solution cannot
  name. Remedy: reify the latent abstraction.
- **Non-requisite variety**: the solution is *noisier* than the problem—irrelevant
  variation, or unnecessary indirection that relocates complexity without reducing it.
  Remedy: attenuate or consolidate.

## Single source of truth

Requisite variety applied to *representation*: each concept belongs in exactly one place.
Stating a concept in N places makes the representation noisier than the concept space—non-requisite
variety—and the copies drift apart over time. So:

- **One home per concept.** Every concept has a single authoritative location. New material
  either extends an existing home or becomes one; it never adds a second copy.
- **Reference, don't restate.** Everything else points to the home instead of repeating it.
  A reference is a single canonical handle, not a restated name-plus-location.
- **A home is a leaf.** References point one way: from consumer to home. A home names none
  of its consumers, so the reference graph is acyclic. (This file is an example—it defines
  the principle and points at nothing.)
- **Parallel structure is not duplication.** Sibling documents may share a skeleton, and an
  index may point at many homes; repeating *structure* or *pointers* is fine. Repeating
  *content* is not.
