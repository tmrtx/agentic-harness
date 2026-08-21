---
name: writing-guard
code: WG
description: WG — how to write prose a person reads; every noun phrase resolves where it is read, every opening says who is doing what, no framing ahead of the point, no contrast in a title. Use whenever writing user-facing prose — a final message, a question to the user, a commit message, a PR description, or an artifact's prose.
---

# WG: Writing Guard

The reader arrives cold, without your session, and stops at the first defect: *"as soon as I saw something unacceptable, I stopped reading and labeled it as unacceptable."* The cost he names is a mental stack — *"I always feel like I'm running a bracket matching algorithm mentally. I don't want to do that."*

**Every sentence closes what it opens**, so the reader's stack never has to hold anything.

## Directives

1. **WG-1 Define It or Name It in Full**
   - Every definite noun phrase resolves where it is read: a proper name, a full path, or defined in that sentence. Never a first-mention "the fallback".
   - He wrote: *"just use that space to define the thing or use a full reference so I can comprehend wtf it is talking about."*

2. **WG-2 Openings Say Who Does What**
   - The first clause names who is doing what, and to which part — in the opening, the title, and under every heading.
   - He stops at the first defect, so an opening defect ends the read: across four commit messages — two source texts, one of them rewritten in three registers — he marked the title and the first line under each heading, 14 of 16 marks, nothing in between.

3. **WG-3 Point Before Qualification**
   - Nothing abstract stands between a sentence's start and its point, anywhere: no "The result: ...".
   - *"I've read 6 words, yet I have no idea what the sentence is about ... I'll have to find the key details by reading and then I have to re-read it with the key details in mind."*

4. **WG-4 No Contrast in a Title**
   - Keep "[X], not [Y]" out of titles and headings; state X.
   - He named that shape himself in a commit title — *"completely unaccaptable stuff"*. The rule stops at the title deliberately: an accepted commit carries the same shape in its body, so nothing licenses a wider rule yet.

5. **WG-5 Report Shape**
   - A final message says what you did, what you found, where the result is, and what is next — first person, systems named, each claim carrying its numbers.
   - It is the one shape he has accepted, and it answers *"what works? what was the problem? why was it replaced?"* before he asks. Untested in a commit message.

Artifacts additionally follow `artifact-reader-contract` for page design.

## The one text rated good (1 of 50 answered)

It was authored as a pass-bar rewrite for labeling round 2 (corpus `auth-0006`) rather than drawn from history, so the figures inside it illustrate the register and measure no real file.

> I went through the Langfuse observations for 2026-07-27 to 2026-08-13: 139 artifact publications across 35 sessions, and the 202 user turns that followed them. About 25 of those turns asked for a correction, spread over roughly 10 sessions.
>
> They fall into five groups: claims sent without the reasoning behind them, decisions left for you to assemble, session coinage and codes, layouts that scatter what one judgment needs, and truncation with no way to expand it.
>
> The skill I wrote from them is at `~/.claude/skills/artifact-reader-contract/SKILL.md`: six rules, 240 tokens of operative text against the 250-token budget.
>
> Next: re-measure how often these follow-ups happen after the skill has been in use for a few weeks.

Nothing here is left open: every count says what it counts, "five groups" is discharged in its own sentence, the path is written out where "the skill" would have gone, and "240 tokens" arrives with the budget that makes the number mean something.

## Oracle

The standard is the 50 labels the user gave over two labeling rounds, held in mono-repo `scratch/2026-08-21-writing-guard/curation/round1-labels.json` and `curation/round2/round2-labels.json` and analyzed in `sweep/ROUND2-ANALYSIS.md`. This skill's oracle is therefore statistical over specified ground truth (`Oracle: [statistical|specified]`): one accepted text cannot confirm WG-1 to WG-5, and one rejection cannot refute any of them. The accepted set holds one repeat-confirmed "okay" and one "good" the user qualified as "closest to good" — too thin for a numeric bar. Round 3 measures whether WG-5 survives in a commit message.
