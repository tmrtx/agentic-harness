# agentic-harness

## What this is

The shared Claude Code instruction set for tmrtx repos — a body of governance policies
and workflow skills packaged as marketplace **`agentic-harness`** containing the single
plugin **`harness`**. Each skill lives in its own `plugins/harness/skills/<name>/`
directory and declares its own purpose, code, and invocation in `SKILL.md` frontmatter;
that directory is the authoritative inventory, so this README describes the conventions
rather than restating the list. Consumer repos import the plugin instead of carrying
copy-pasted instruction files that drift apart.

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
            └── <name>/                   # one directory per skill (the inventory)
                ├── SKILL.md              # required — frontmatter declares name, code, invocation
                └── …                     # optional supporting files, loaded on demand
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

Plugin skills are namespaced `harness:<skill>`, where `<skill>` is the directory name.
How a skill is invoked follows from its own `SKILL.md` frontmatter — the frontmatter *is*
the registry, so there is no table here to keep in sync (this is `CIA-9` applied to the
README itself):

- **Slash form** — a skill is user-invocable as `/harness:<skill>` unless its frontmatter
  sets `user-invocable: false`, in which case Claude loads it via the Skill tool and/or
  its `paths:` globs auto-activate it while matching files are open.
- **Code** — a governance policy declares a canonical `code:` (e.g. `CIA-8`); everything
  else cites that code. The set of declared codes is the registry (see `CIA-9`).
- **Supporting files** — a skill's larger, task-scoped material lives in plain `.md` files
  beside its `SKILL.md` and loads only when `SKILL.md` links to it (progressive
  disclosure).
