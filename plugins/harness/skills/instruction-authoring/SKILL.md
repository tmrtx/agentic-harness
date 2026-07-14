---
name: instruction-authoring
description: Write an instruction artifact — a skill, slash command, or subagent prompt — that transmits intent instead of dumping procedure, so its owner keeps it without a refinement round. Use whenever authoring a new skill, command, or agent prompt, revising one that isn't landing, or cutting an over-built draft back to its intent. For crafting the artifact itself — not for organizing or deduplicating an instruction corpus.
---

# Instruction Authoring

An instruction artifact — a skill, a command, an agent prompt — briefs an agent
that will act with none of the context you hold now. Transmit three things: the
goal, the test that tells whether the goal is met, and the constraints the agent
cannot infer. Trust it with everything else. Steps do not survive contact with
the task; intent does.

## Size it before you write

Answer for the task at hand, not in the abstract:

- **What is this for?** The one goal that, unmet, makes the artifact worthless.
- **Who invokes it?** A command the user runs supplies intent at call time and
  can stay near-empty; an artifact that fires on its own carries intent itself.
- **What does the agent already do right?** That, you do not write.
- **What can it not infer?** The fragile contract, the exact format, the tool
  invoked just so. That is the payload.

The answers set the size — usually a few lines. Add sections, references, or
scripts only when an answer above forces them.

## The request is the spec

When the requester has stated the task in their own words, those words are the
artifact's core: embed them. An artifact that restates its request as a heading,
an intro, and a pipeline has replaced the intent with a guess at a procedure.
Add only what the request cannot say for itself: the invocation wiring and the
non-inferable contracts.

## Specify as tightly as the task is fragile

A step that breaks when permuted — a tool invoked just so, an external
contract — gets the exact sequence; that precision is payload, not procedure.
A judgment call — several valid approaches, context deciding — gets the goal
and latitude; a procedure there only fights the agent. Both directions fail:
stripping a sequence a fragile step needs breaks the artifact as surely as
caging a judgment call in invented steps bloats it. Carry the task's variety —
no more, no less.

## Wire the invocation

- A **command the user runs deliberately**: disable model invocation, take the
  argument, keep the description a label — the user already knows what it does.
- A **skill that fires on its own**: the description is the trigger the model
  matches requests against — what it does and when to use it; purpose, never an
  inventory of contents.
- A **subagent receiving delegated work**: its description tells the delegator
  when to reach for it; its body is the subagent's whole world, so everything
  non-inferable goes in it.

Name it for its job; the folder name is the name. Keep the body one screen —
it is paid for on every load. Long reference material earns a separate file
only with a note saying when to open it.

## Over-building, caught in the draft

Read the draft against these; here the fix is always to cut:

- **Manufactured procedure** — a taxonomy, request-shape, or format spec the
  agent would have improvised correctly.
- **Thoroughness past the boundary** — a section made "complete" by doing a
  neighboring artifact's job.
- **Ceremony** — the request restated as heading and intro, a section skeleton
  nobody asked for.
- **Apparatus on a hand-run command** — trigger phrases and self-policing
  invariants on something the user invokes deliberately.
- **Ban-lists and theater** — enumerated forbidden phrasings where one positive
  rule suffices; processes no agent can perform.

## Know it worked

Test in a fresh session — the context you wrote in hides the gaps. Check
separately that the artifact fires when it should, and that what it produces is
right. It is finished when its owner keeps the next output without a round of
corrections.
