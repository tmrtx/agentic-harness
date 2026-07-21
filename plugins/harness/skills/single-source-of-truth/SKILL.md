---
name: single-source-of-truth
code: CIA-9
prerequisites: homomorphism
description: CIA-9 — single-source-of-truth regulations for the governance corpus; one home per concept, reference by canonical code, no duplicated or drifting guidance. Use when creating or editing CLAUDE.md, skills, commands, rules, agent prompts, or any instruction/governance file.
---

# CIA-9: Single Source of Truth

## 1. Purpose & Scope

This control defines mandatory **single-source-of-truth** regulations for the project's
**governance corpus**—the files that tell agents how to work: `CLAUDE.md`, the `skills/`,
the commands, the workflows, and the agent prompts.

It exists to prevent the organic growth of duplicated, drifting, and
circularly-referenced guidance. Out of scope: code logic, data, and ordinary
project documentation.

Non-compliance compounds—copies diverge silently and end
up contradicting one another.

---

## 2. Core Principle: Corpus Homomorphism

The governance corpus must be **homomorphic to the concept space**.

**The corpus homomorphism test**: a change to "commit protocol" should have one local edit. If
a single policy change forces edits across several files, the corpus is non-homomorphic
and the concept has more than one home.

**Why this matters for governance**: duplicated guidance does not just bloat—it drifts
into contradiction, and agents reading two copies receive conflicting instructions. The
single source is the only one that can be trusted to be current.

---

## 3. Control Directives

Below are **non-negotiable** directives constituting the CIA-9 Governance Integrity
mandate.

1. **CIA-9.1 Single Source of Truth for Concepts** <TODO>
   - define once, refer elsewhere

2. **CIA-9.2 No Conflicting Standards** <TODO>

3. **CIA-9.3 Progressive Disclosure** <TODO>

---

## 4. Compliance & Enforcement

---

## 5. Practical Application

### 5.1 Reference by canonical code

- Each control declares its `code:` in frontmatter (`CIA-7`, `CIA-8`, `CIA-9`,
  `homomorphism`). The set of these frontmatter codes **is** the registry: a code resolves
  to the file whose frontmatter declares it. There is no separate index to maintain.
- Cite the code: `CIA-7.1`, `CIA-8`, `homomorphism`. A sub-code (`CIA-7.1`)
  resolves to its control's home (`CIA-7`).

---

## 6. References & Changelog
