# agentic-harness

## What this is

The shared Claude Code instruction set for tmrtx repos — 4 governance policies
(homomorphism, CIA-7, CIA-8, CIA-9) and 5 workflow skills (specification,
implementation-loop, commit-protocol, pull-request, scope-issue) — packaged as
marketplace **`agentic-harness`** containing the single plugin **`harness`**.
Consumer repos import the plugin instead of carrying copy-pasted instruction files
that drift apart.

Repo layout:

```
agentic-harness/
├── .claude-plugin/
│   └── marketplace.json                  # marketplace catalog (repo root)
└── plugins/
    └── harness/
        ├── .claude-plugin/
        │   └── plugin.json               # plugin manifest — deliberately NO version field
        └── skills/
            ├── commit-protocol/SKILL.md
            ├── executable-expectations/SKILL.md
            ├── homomorphism/SKILL.md
            ├── implementation-loop/SKILL.md
            ├── implementation-principles/SKILL.md
            ├── pull-request/SKILL.md
            ├── scope-issue/SKILL.md
            ├── single-source-of-truth/SKILL.md
            └── specification/SKILL.md
```

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

## Skill namespacing

Plugin skills are namespaced `harness:<skill>`. User-invocable skills get a slash
command form; the three `user-invocable: false` governance policies have no slash form
and are model-loaded via the Skill tool.

| Skill | Code | Invocation |
|---|---|---|
| `harness:commit-protocol` | — | `/harness:commit-protocol` |
| `harness:executable-expectations` | `CIA-8` | model-invoked only |
| `harness:homomorphism` | `homomorphism` | model-invoked only |
| `harness:implementation-loop` | — | `/harness:implementation-loop` |
| `harness:implementation-principles` | `CIA-7` | model-invoked only |
| `harness:pull-request` | — | `/harness:pull-request` |
| `harness:scope-issue` | — | `/harness:scope-issue` |
| `harness:single-source-of-truth` | `CIA-9` | `/harness:single-source-of-truth` |
| `harness:specification` | — | `/harness:specification` |
