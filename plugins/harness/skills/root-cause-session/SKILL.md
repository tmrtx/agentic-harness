---
name: root-cause-session
description: Trace a defective agent output back through its session transcript to the instruction text — or instruction gap — that produced it, then fix the corpus at its single source of truth. The postmortem command for delegated sessions — run with a session id and a symptom (a bad test, a wrong fix, scope creep) to get an evidence-chain from artifact defect to decision moment to governing instruction, and a corpus fix proven against the original artifact.
argument-hint: "[session id] [what went wrong — artifact + defect]"
disable-model-invocation: true
---

# Root-Cause a Session

An agent produced something defective. The artifact can be patched in a
minute; the reason it was produced will keep producing. This workflow traces
the defect back to the sentence — or the missing sentence — that caused it,
with transcript evidence at every link, and lands the fix in the instruction
corpus so the class of defect dies, not the instance.

Inputs: a session id and a symptom (`$ARGUMENTS`). If either is missing, ask
for it before starting — the session id cannot be guessed, and a vague
symptom ("the tests are bad") must be sharpened into an artifact plus a
defect before step 1 can pin it.

## Method

Work the five steps in order; each produces evidence the next consumes.

### 1. Reify the symptom

Obtain the artifact itself — `gh pr diff`, the file, the message — and pin
the defect to exact lines. State in one sentence what a correct artifact
would have looked like. Do not proceed on a paraphrase of the complaint;
every later claim anchors to these lines.

### 2. Map the session

Resolve and skeleton the transcript:

```
python3 scripts/transcript.py map <session-id>
```

Note the user prompts (what was actually asked), `Skill` invocations,
`forkedFrom` lineage, and any sidechains. Subagent transcripts live beside
the session file and are read with the same script — a decision made inside
a delegated task is invisible in the parent. Record anatomy, sibling
directories, and caveats (tool results arrive in `user`-role records) are
documented in `references/transcript-format.md`.

### 3. Reconstruct the effective instruction set

Establish what governing text was **actually in context** at the decision —
not what should have been. Evidence: `Skill` tool calls, `Read`s of
instruction files, injected attachments, and the always-present description
lines (`skill_listing`, CLAUDE.md). Then verify whether the full body of the
relevant control ever loaded — `grep` the transcript for a distinctive phrase
from it. Description-only loading is the most common finding and changes
where the fix must land (see the description/body distinction in
`references/transcript-format.md`). Pin the exact instruction *version* the
session served via the snapshot path in any `Skill` result.

### 4. Find the decision moment

Locate where the defect was chosen:

```
python3 scripts/transcript.py grep <session-id> <artifact-identifier>
python3 scripts/transcript.py show <session-id> <idx> --kind thinking,text
```

Start from the first occurrence of the artifact's identifiers (class name,
column, filename) and read the surrounding `thinking`. The agent's stated
justification is primary evidence — quote it verbatim with its record index.
It usually names its source: an instruction phrase, a repo precedent, a spec
sentence.

### 5. Attribute, then fix the corpus

Classify each candidate cause — **commanded**, **licensed**, **unguarded
gap**, or **extra-instructional** — per the definitions, evidence standard,
and gap-proof procedure in `references/attribution.md`. The evidence bar:
quote the decision, demonstrate one concrete divergence the defect produced
or blessed, and for gap claims run every existing diagnostic against the
artifact and record that all pass.

Then fix at the single source of truth, under four constraints:

- edit the skill that owns the concept; everywhere else gains the rule by
  reference;
- if the incident showed description-only loading, amend the frontmatter
  description too — a body-only fix cannot reach the failure mode;
- commit on a branch in the marketplace clone and leave the clone on a clean
  `main` — a push to `main` is a release to every consumer, so pushing stays
  with a human;
- prove the counterfactual: under the fixed text, the original artifact must
  fail a named diagnostic.

The full fix protocol is in `references/attribution.md`.

## Deliverable

An evidence-chain report, most load-bearing link first:

1. the defect, at `file:line` in the artifact;
2. the decision, quoted from the transcript with record index;
3. the instruction text or gap, quoted from the exact version served, with
   its classification;
4. the concrete demonstration;
5. the fix diff and its counterfactual check;
6. residual causes the corpus fix does not reach (exemplar code, spec shape),
   each with a proposed follow-up.

Every claim cites a transcript record index or a `file:line`. If the
instructions turn out not to be implicated — the corpus neither commanded,
licensed, nor failed to guard — say so plainly and name the
extra-instructional driver instead; a forced instruction fix is itself
corpus noise.

## Additional Resources

- **`scripts/transcript.py`** — `map` / `grep` / `show` over a session or
  subagent transcript; resolves bare session ids.
- **`references/transcript-format.md`** — record anatomy, attachment types,
  fork/sidechain semantics, where instruction text lives on disk, the
  description/body distinction.
- **`references/attribution.md`** — cause taxonomy, evidence standard, corpus
  fix protocol, and a worked example (the PR #107 mirror-oracle incident).
