---
name: instruction-writing
code: CIA-9
prerequisites: homomorphism
description: CIA-9 — instruction-writing regulations for the governance corpus; empowered delegation (instructions carry intent — goals, rationale, assumptions — not bare procedure), refine failing instructions rather than accrete patches, one home per concept, reference by canonical code, no duplicated or drifting guidance. Use when planning to modify, modifying, reviewing any instruction, CLAUDE.md, skills, commands, rules, agent prompts, or instruction/governance file.
---

# CIA-9: Instruction Writing

## 1. Purpose & Scope

This control defines mandatory **instruction-writing** regulations for the project's **governance corpus**—the instruction and governance files that tell agents how to work.

It exists to keep the corpus a trustworthy delegation instrument: every instruction carries the intent that produced it, and every concept has exactly one authoritative home. Out of scope: code logic, data, and ordinary project documentation.

Non-compliance compounds—bare rules outlive the assumptions that justified them, and duplicated guidance drifts silently into contradiction.

---

## 2. Core Principle: Empowered Delegation

Instructions must **carry their intent**—objective, rationale, assumptions—**never bare procedure**.

Every instruction is a delegation: the author decides at writing time; agents execute later, inside situations the author never saw. This is the principal–agent problem in the LLM space, and there are two ways to bridge the gap:

- **Constrained delegation** transmits *conclusions*—prescribed procedures, fixed plans, guardrails. These are correct exactly while every assumption behind them holds. When one breaks, the agent complies its way into failure: capable models follow instructions literally, so a stale rule gets executed as written, not quietly reconciled with reality.
- **Empowered delegation** transmits *intent*—the goal, the rationale, and the assumptions: the **ladder of inference** that produced the rule. While the premises hold, the agent executes what the author would have prescribed anyway. When a premise breaks, the agent climbs down to the highest rung still standing, re-derives the action the intent demands, and flags the stale rung so the corpus gets repaired.

The corpus must delegate the empowered way. Model capability has moved the bottleneck: delegation quality is no longer limited by the agent's judgment but by the fidelity of the intent it receives. A rule shipped without its why can only be obeyed or violated; a rule shipped with its why can be applied, adapted, or correctly set aside—and the agent can tell which the situation calls for.

**The empowered-delegation litmus test**: invalidate one assumption behind an instruction. If the recorded intent lets the agent (a) notice the instruction went stale and (b) still decide as the author would, seeing what the agent now sees, the delegation is empowered. If the agent's only options are literal compliance or guessing, the instruction is a bare constraint—write down the ladder that produced it.

**Why this matters for governance**: a corpus of bare constraints ages badly. Every shift in the environment silently invalidates some procedure; agents comply into failure or route around the guidance; each incident gets patched with another bare rule, and the corpus grows more brittle as it grows. Intent degrades gracefully—goals outlive the procedures compiled from them—and the recorded ladder is what lets a future editor tell a load-bearing rule from a fence whose reason has expired.

**Prescription is compiled intent, not a rival principle**: exact steps remain correct on narrow bridges—fragile, irreversible, or contract-bound operations with one safe path (a migration sequence, a release gate, a wire format)—and an invariant that must always hold belongs in a deterministic gate (a hook), not in louder prose. But a procedure is a cache of decisions made under assumptions: ship it with the intent it was compiled from. Nor is empowerment vagueness—an intent too thin to re-derive from delegates nothing but risk. State the goal, the rationale, the assumptions, and the boundaries.

---

## 3. Control Directives

Below are **non-negotiable** directives constituting the CIA-9 Governance Integrity mandate.

1. **CIA-9.1 Communicate Intent** <TODO>
   - every instruction ships with the ladder that produced it—goal, rationale, assumptions—so agents can re-derive the decision when the world shifts
   - prescribe bare steps only on narrow bridges (fragile, irreversible, contract-bound operations), and even then say why

2. **CIA-9.2 Refine, Don't Accrete** <TODO>
   - when an instruction fails—misread, misfiring, or gone stale—repair that instruction: climb to the broken rung of its ladder and fix it at its one home, or prune the rule entirely; never append a compensating rule on top
   - a workaround rule is single-loop learning: it corrects the symptom inside the existing frame and leaves the defective assumption in place, still generating failures while the corpus bloats toward contradiction; refinement is double-loop learning—question the assumption itself, and the whole failure class disappears
   - a new instruction is warranted only by a new concept, never by the failure of an existing one

3. **CIA-9.3 No Conflicting Standards** <TODO>

4. **CIA-9.4 Single Source of Truth for Concepts** <TODO>
   - define once, refer elsewhere
   - litmus: one policy change → one local edit; a second edit site means the concept has a second home

5. **CIA-9.5 Progressive Disclosure** <TODO>
   - structure instructions such that they are loaded exactly when they're needed. not before (causing context dilution and performance degradations), not after (defeats the whole purpose).
