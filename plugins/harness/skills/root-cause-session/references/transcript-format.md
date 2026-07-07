# Session Transcript Anatomy

Where session evidence lives on disk and how to read it. Everything here is
navigable with `scripts/transcript.py`; drop to `python3 -c` / `jq` only for
questions the script does not answer.

## Locations

- **Transcript**: `~/.claude/projects/<slug>/<session-id>.jsonl`, where `<slug>`
  is the session's working directory with `/` replaced by `-` (cwd `/data` →
  slug `-data`). One JSON record per line.
- **Sibling directory** `~/.claude/projects/<slug>/<session-id>/`:
  - `subagents/agent-<id>.jsonl` (+ `.meta.json`) — full transcripts of
    subagents the session spawned, in the same record format (the script reads
    them directly). A decision made inside a delegated task lives here, not in
    the parent transcript.
  - `tool-results/` — oversized tool outputs referenced from the transcript.

## Record shape

Each line is an object; the fields that matter for forensics:

- `type` — `user`, `assistant`, or `attachment`.
- `message.content` — a plain string (a typed user prompt) or a list of blocks:
  - `text` — what the user saw.
  - `thinking` — the agent's private reasoning. **Primary evidence**: decisions
    are usually justified here before any edit is made.
  - `tool_use` — `{name, input}`. `Skill` calls, `Read`/`Edit`/`Write` paths,
    and `Bash` commands reconstruct what the agent loaded and touched.
  - `tool_result` — `content` is a string or a list of `{type: "text", text}`.
- **Caution**: `type: user` records carry both real user prompts *and*
  `tool_result` blocks (results return in the user role). Distinguish by
  block kind, not by role.
- `attachment.type` — harness-injected context. Observed types:
  `skill_listing` (the one-line descriptions of every available skill —
  always-in-context knowledge), `agent_listing_delta`, `deferred_tools_delta`,
  `edited_text_file` (snippet re-shown after an external file modification).
- `isSidechain: true` — subagent traffic mirrored into the parent file.
- `forkedFrom: {sessionId, messageUuid}` — this session was forked; inherited
  records are re-recorded in this file, so read it standalone, but attribute
  early records to the parent lineage when timelines matter.
- `timestamp`, `cwd`, `gitBranch`, `promptId`, `uuid`/`parentUuid` — ordering
  and threading metadata.

## Where instruction text lives

To compare "what the corpus says" with "what the agent saw", know the three
copies of a plugin skill:

- **Marketplace clone** (the git source): `~/.claude/plugins/marketplaces/<marketplace>/`.
  This is a real checkout of the plugin repository — the place to *fix*
  instructions. A push to its `main` is a release to every consumer.
- **Served snapshot**: `~/.claude/plugins/cache/<marketplace>/<plugin>/<sha>/`.
  Content-addressed by commit; this is what sessions actually load. A `Skill`
  tool result states its base directory, pinning exactly which snapshot — and
  therefore which text version — the session ran under.
- **Active version**: `~/.claude/plugins/installed_plugins.json`
  (`installPath`, `gitCommitSha`, `lastUpdated`).

## The description/body distinction

The single most common forensic finding: **the full instruction text was never
in context**. A skill's one-line `description` is always present (via
`skill_listing` and any CLAUDE.md index); its body enters context only if the
transcript shows a `Skill` invocation, a `Read` of the SKILL.md path, or a
path-triggered injection. Before attributing behavior to a paragraph of
doctrine, prove that paragraph was ever loaded — `grep` the transcript for a
distinctive phrase from it. If only the description was present, the
description *is* the instruction set that governed the behavior, and any fix
must reach the description line to be effective.
