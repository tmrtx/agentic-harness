---
name: single-source-of-truth
code: CIA-9
prerequisites: homomorphism
description: CIA-9 — single-source-of-truth regulations for the governance corpus; one home per concept, reference by canonical code, no duplicated or drifting guidance. Use when creating or editing CLAUDE.md, skills, commands, rules, agent prompts, or any instruction/governance file.
---

# CIA-9: Single Source of Truth

## 1. Purpose & Scope

This control defines mandatory **single-source-of-truth** regulations for the project's **governance corpus**—the files that tell agents how to work: `CLAUDE.md`, the `skills/`, the commands, the workflows, and the agent prompts.

It exists to prevent the organic growth of duplicated, drifting, and circularly-referenced guidance. Out of scope: code logic, data, and ordinary project documentation.

Non-compliance compounds—copies diverge silently and end up contradicting one another.

---

## 2. Core Principle: Corpus Homomorphism

The governance corpus must be **homomorphic to the concept space**.

**The corpus homomorphism test**: adding a single step to the way the agent creates commits should require a single local change. If that's not the case, then the corpus is non-homomorphic and needs to be refined.

**Why this matters for governance**: nono-homomorphic instructions doesn't just bloat—it drifts into stale copies, contradiction, and agents reading two copies receive conflicting instructions and so much more problems.

---

## 3. Control Directives

Below are **non-negotiable** directives constituting the CIA-9 Governance Integrity mandate.

1. **CIA-9.1 No Conflicting Standards** <TODO>

2. **CIA-9.2 Single Source of Truth for Concepts** <TODO>
   - define once, refer elsewhere

3. **CIA-9.3 Progressive Disclosure** <TODO>
   - structure instructions such that they are loaded exactly when they're needed. not before (causing context dilution and performance degradations), not after (defeats the whole purpose).
