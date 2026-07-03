# Working on this repository

This repo is a Claude Code plugin marketplace: the `harness` plugin under `plugins/harness/`
distributes the shared instruction set (governance policies + workflow skills) to consumer
repositories. See `README.md` for propagation, onboarding, and pinning details.

## Invariants

- **Never add a `version` field to `plugins/harness/.claude-plugin/plugin.json`.**
  `claude plugin validate` warns "No version specified" — that warning is intentional.
  The git commit SHA is the version; a static version string makes every future push a
  silent no-op for existing consumers.
- **Every push to `main` is a release.** Consumers auto-update at their next session start.
  Gate before pushing: `claude plugin validate plugins/harness && claude plugin validate .`
  must exit 0 with only the no-version warning.
- Skills live at `plugins/harness/skills/<name>/SKILL.md` — one home per concept; consumer
  repos reference these, never copy them.

## Self-consumption

This repo installs its own plugin (`harness@agentic-harness`, GitHub source), so the
methodology skills (`harness:commit-protocol`, `harness:pull-request`, `harness:specification`,
…) apply when working here — follow the commit protocol for every commit. Sessions serve the
last *pushed* release, one step behind the working tree; after pushing a skill change, run
`/reload-plugins` to use it immediately.
