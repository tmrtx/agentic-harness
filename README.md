# agentic-harness

## What this is

The shared Claude Code instruction set for tmrtx repos — a body of governance policies
and workflow skills packaged as marketplace **`agentic-harness`** containing the single
plugin **`harness`**.

## Working in the repository

For idioms, patterns, and best practices, your ONLY sources are official
Anthropic documentation: docs.claude.com, and anthropic.com pages authored by
Anthropic (e.g. "Claude Code: Best practices for agentic coding" and related
engineering posts).

Do NOT use any non-Anthropic source. Fetch and read the actual doc pages; do not
answer from memory alone. If a page 404s, find its current location via the docs
site navigation.

## Update propagation

**`git push` to this repo is the entire release step.** `plugin.json` deliberately
omits `version`, so the plugin's version *is* the git commit SHA — every push is a new
version. Do **not** add a `version` field: update detection compares resolved versions,
so an unbumped version string would make every future push a silent no-op for existing
consumers.

- Consumers whose marketplace entry sets `autoUpdate: true` refresh at the next
  Claude Code startup and see a `/reload-plugins` prompt.
- Manual path: `/plugin marketplace update agentic-harness` then `/plugin update harness`.
- Mid-session refresh: `/reload-plugins`.
- Already-running sessions keep the old cached version until reload (cache retention
  is roughly 7 days).

## Consumer onboarding

Check this into the consumer repo's `.claude/settings.json` (merge with existing keys):

```json
{
  "extraKnownMarketplaces": {
    "agentic-harness": {
      "source": { "source": "github", "repo": "tmrtx/agentic-harness" },
      "autoUpdate": true
    }
  },
  "enabledPlugins": {
    "harness@agentic-harness": true
  }
}
```

Equivalent CLI:

```sh
claude plugin marketplace add tmrtx/agentic-harness --scope project
claude plugin install harness@agentic-harness --scope project
```

First use in a repo triggers a **one-time consent flow**: accept the marketplace trust
prompt and the plugin install prompt. Until accepted, the harness skills are absent
from that user's sessions.

Per-user opt-out: a user can disable the plugin for themselves without touching the
shared settings by adding to the repo's `.claude/settings.local.json`:

```json
{
  "enabledPlugins": {
    "harness@agentic-harness": false
  }
}
```

## Headless / daemon consumers: load the plugin locally

The marketplace path above assumes an interactive user: the one-time consent flow
needs a human to accept it, and keeping the shared plugin store healthy needs git
credentials at session start (see the auto-update caveat below). A headless
consumer — a daemon driving sessions through the Agent SDK, CI — has neither: it
cannot answer the consent prompts, and when the store breaks it cannot repair it;
every `harness:*` invocation then fails with `Unknown skill` (this is exactly how
tmrtx/pipeline's executioner loop failed).

Headless consumers should bypass the store entirely and serve the plugin from a
clone they own and refresh themselves:

- CLI: `claude --plugin-dir <clone>/plugins/harness`
- Agent SDK: `ClaudeAgentOptions(plugins=[{"type": "local", "path": "<clone>/plugins/harness"}])`

A local plugin wins over an installed marketplace copy of the same name, so this
composes with a repo whose `.claude/settings.json` also enables
`harness@agentic-harness` for interactive users. Track releases the same way any
consumer does — pull the clone before session start (`git pull --ff-only`); the
clone's commit SHA is the version being served.

## Private-repo auto-update caveat (GH_TOKEN / GITHUB_TOKEN)

This repo is **private**. Interactive installs and manual `/plugin marketplace update`
use your normal git auth (gh CLI, keychain, ssh-agent). But **background startup
auto-updates run without git credential helpers** — if no token is present in the shell
environment, auto-update of the private marketplace silently fails.

- Export `GH_TOKEN` or `GITHUB_TOKEN` (with `repo` scope) in the shell environment
  that launches Claude Code.
- Set `CLAUDE_CODE_PLUGIN_KEEP_MARKETPLACE_ON_FAILURE=1` to prevent the marketplace
  cache from being wiped when a background pull fails.
- Fallback: the manual update path above always works via your interactive git auth.

## Pinning options

By default consumers track `main` (latest SHA). To pin:

1. **Pin the marketplace at add time**: `claude plugin marketplace add tmrtx/agentic-harness@<ref>`
   (branch, tag, or commit SHA).
2. **Pin a plugin source in `marketplace.json`**: add `ref` (branch/tag) or `sha`
   (exact commit) to the plugin's `source` entry — `sha` wins if both are set.
3. **Explicit `version` freeze**: adding a `version` string to `plugin.json` freezes
   update detection — pushes become no-ops for existing users until the version is
   bumped. This is the opposite of this repo's intent; only use it if you want
   release-gated updates.
4. **Stable/latest channels**: run two marketplaces (e.g. this repo at `main` as
   *latest* and a second marketplace entry pinned to a tag as *stable*) and let each
   consumer choose which one to enable.
