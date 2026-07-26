# Working on this repository

This repo is a Claude Code plugin marketplace: the `harness` plugin under `plugins/harness/`
distributes the shared instruction set (governance policies + workflow skills) to consumer
repositories. See `README.md` for propagation, onboarding, and pinning details.

## Staleness prevention

When working on any task here, spawn one or more Opus subagents to research
current best practices for the relevant topic/s from the Anthropic documentation
and wait the findings before proceeding, ensuring the repository remains at the
methodology frontier.

## Invariants

- **Never add a `version` field to `plugins/harness/.claude-plugin/plugin.json`.**
  `claude plugin validate` warns "No version specified" — that warning is intentional.
  The git commit SHA is the version; a static version string makes every future push a
  silent no-op for existing consumers.
- **Every push to `main` is a release.** Consumers auto-update at their next session start.
  Gate before pushing: `claude plugin validate plugins/harness && claude plugin validate .`
  must exit 0 with only the no-version warning.

## Self-consumption

This repository installs its own plugin (`harness@agentic-harness`, GitHub
source), so the governance policies and workflow skills defined here apply when
contributing.

## Agent branch history

On the agent's own unmerged `claude/*` branch, rewriting history is authorized
and expected — `git commit --amend`, `git commit --fixup` + `git rebase
--autosquash`, `git reset --soft` + recommit, and `git push --force-with-lease`
to that same branch — per the harness `commit-protocol` stack regulation.
Never rewrite the default branch, merged history, or another author's branch.
