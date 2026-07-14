---
name: instruction-authoring
description: Write an instruction artifact — a skill, slash command, or subagent prompt — that transmits intent instead of dumping procedure. Use whenever authoring a new skill, command, or agent prompt, revising or tightening an existing one, or cutting an over-built draft back to its intent. For crafting the artifact itself — not for organizing or deduplicating an instruction corpus.
---

# Instruction Authoring

An instruction artifact briefs an agent that will act with none of the context
you hold now. Transmit the goal, the
test that tells whether it is met, and the constraints the agent cannot infer;
trust it with everything else. Procedure does not survive contact with the
task; intent does. Size to the non-inferable payload — usually a few lines —
and add sections, files, or scripts only when the payload forces them.

## The request is the spec

When the requester states the task in their own words, those words are the
artifact's core: embed them, first person intact. Do not paraphrase them into
a title and an intro, re-explain them as numbered steps, expand them into a
taxonomy, or armor them with self-policing invariants — a request restated as
a pipeline has replaced intent with a guess at procedure. Add only what the
request cannot say: the invocation wiring, and any contract the agent could
not reconstruct — the exact tool call, the format that breaks when varied.
Where such a contract exists but you do not know it, point at its source of
truth instead of inventing it. Cutting a contract the task needs is as wrong
as adding procedure it does not.

## Who invokes it decides its shape

Classify by who supplies the intent, not by the noun the request used — "a
task I keep giving you" is a user-run command even when the requester calls it
a skill.

- A **command the user runs deliberately**: disable model invocation; declare
  the argument hint and read the argument as the request defines it; keep the
  description a label; open with the task itself — no title.
- A **skill that fires on its own**: the description is the trigger — what it
  does and when to use it; purpose, never an inventory of contents.
- A **subagent receiving delegated work**: its body is its whole world —
  everything non-inferable goes in it; its description tells the delegator
  when to reach for it.

The folder name is the artifact's name. The body is paid for on every load —
keep it one screen: past that you are elaborating, not briefing.

## Know it worked

Test in a fresh session; the context you wrote in hides the gaps. Check
separately that the artifact fires when it should, and that what it produces
is right. It is finished when its owner keeps the next output without a round
of corrections.
