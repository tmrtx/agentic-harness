# Building Gates — Platform Contract and Failure Economics

A gate is judged by its expected value: violations caught, minus the cost of its
errors. Two failure modes dominate the loss side. Silent breakage is worse than no
gate unconditionally: everyone budgets vigilance as if the gate held, and a
believed-in gate replaces exactly the attention it automated. Misfiring into
sessions is worse than no gate whenever the misfire cost exceeds what the gate
catches — that comparison is what a builder prices throughout this file. What
follows mixes two kinds of claim, and the durability test is per claim, not per
section: a claim travels to any enforcement mechanism, current or future, when the
cost it prices exists independently of exit codes, routes, and hook events —
credibility, calibration, locality, the session tax; a claim that names those
carriers is the current hook platform's contract and expires with it. The right
construction falls out of pricing both.

## Routes and matchers

Any action worth gating is reachable by several routes: the CLI form through Bash
(`gh pr create`), the MCP tool form (`mcp__github__create_pull_request`), and — for
hooks shipped inside a plugin — the plugin-scoped MCP name
(`mcp__plugin_<plugin>_<server>__<tool>`). A gate covering one route does not reduce
violations; it redistributes them to the ungated routes. Coverage is a property of
the action, not of any single tool.

Matcher semantics that silently zero out coverage: matching is case-sensitive, and a
bare `mcp__server` is an exact match that matches nothing — reaching a server's tools
takes `mcp__server__.*`.

## Exit codes, and where words land

The exit code selects the channel and the audience; structured stdout on success
carries the verdict's detail:

| exit | effect | who reads its output |
|---|---|---|
| `0` | proceed; stdout parsed as JSON and honored | the harness |
| `2` | block; stderr injected into the model's context | the model |
| other | proceed; message surfaced as a notice | the human only |

A gate's own failure holds no privileged row: an unhandled nonzero exit lands in
"other" — a passing notice to the human, nothing to the model — while an error the
script swallows, or malformed stdout on exit 0, surfaces only in the debug log. On
either path the action proceeds and the session never learns.

The asymmetry that follows: a missed violation is caught and repaired downstream at
bounded cost in the common, reversible case, while a false block costs the remainder
of the session, and more of it the earlier it fires. In that common case a gate
resolves its doubt — missing state, unparseable input — to exit 0 and silence,
because routing doubt to exit 2 converts every ambiguity into a workflow outage. A
gate guarding an irreversible or unbounded violation inherits the opposite default
from the same comparison: detection after the fact recovers nothing, so doubt
resolves toward blocking and the false positives are the price of the guarantee —
the skill's placement step is where a gate learns which case it is in. The gate's
own crash is a choice in neither case: an unhandled failure exits into the "other"
row and proceeds with only a human notice — one more reason self-recording exists.

Exit-2 stderr becomes model *input*. What serves the model is what is missing and the
command that supplies it, stated as fact. System-voice imperatives ("YOU MUST…") add
nothing the block didn't already say, and text shaped like an instruction stream can
trip prompt-injection defenses — surfacing to the human instead of steering the agent.

## Placement mechanics

What makes terminal-boundary gates trustworthy: a PreToolUse `deny` holds in every
permission mode, including bypass. What makes mid-session denial expensive: a
prompt-hook denial at PreToolUse ends the turn by default (`continueOnBlock` exists
to change that). The mid-session alternative: PostToolUse `additionalContext` reaches
the model as ordinary feedback without ending anything — nested under
`hookSpecificOutput`, because placed top-level it is silently ignored.

Stop hooks are the last backstop and the easiest to overdraw: `stop_hook_active`
marks re-entry, and the harness force-releases after 8 consecutive blocks. A stop
gate that cannot converge does worse than fail — each spurious block teaches the
agent that blocks are noise, spending the credibility every other gate depends on.

## State

`${CLAUDE_PLUGIN_ROOT}` is replaced wholesale on plugin update — anything written
there has the lifetime of one plugin version. Durable state lives in
`${CLAUDE_PLUGIN_DATA}`, which persists across updates. Updates can also land
mid-session while the old scripts keep running until reload, so a state file can meet
a reader older than its writer — a schema-version marker inside the file is what lets
either end notice the skew instead of silently corrupting.

A marker is evidence only of what it fingerprints. A bare "reviewed ✓" outlives the
tree it reviewed and goes on authorizing unreviewed work; a marker keyed to commit
plus working-tree hash expires exactly when its subject changes.

## Kill switches

Consumers can disable a plugin, not one hook inside it. Without a per-gate switch,
the only remedy for a single misfiring gate is disabling the entire harness — every
other gate becomes collateral. A per-gate environment-variable switch, checked before
anything else and exiting 0 silently, keeps a local failure local.

## Self-recording

From the outside, a broken gate and a passing gate look identical: denials do land in
the session trace by construction, but a gate's own failures reach the model never,
the human at best as a passing notice, a swallowed error only the debug log — and
gates resolve doubt open in the common case. The one artifact that answers "is it still
running?", "how often does it fire?", and "what is its false-positive rate?" is the
gate appending a structured line per event — fired / denied / errored — under
`${CLAUDE_PLUGIN_DATA}`. For rubric gates, this record is also the calibration data
the tuning burden requires.

## Budgets

One wall, three fences. The wall: a `description` beyond 1,024 characters exceeds
the platform's documented limit and fails skill validation — no judgment involved.
The fences are corpus-sized defaults adopted from Anthropic's authoring guidance:
SKILL.md under 500 lines and ~5k tokens, CLAUDE.md under 200 lines. Each fence is
sized against the residency of what it bounds (the cost model in the skill's
Purpose): CLAUDE.md and every `description` are always resident and bill every
session, while a SKILL.md body bills the working context of each session that
triggers it — displacing task-relevant context exactly when the skill is needed.
The trade in both cases is that cost against the marginal value of the guidance
carried, which leaves two remedies when a file outgrows its fence: move detail
behind a progressively-disclosed reference (CIA-9.5), so it bills only the sessions
that follow the pointer, or show the length earns its keep (an ablation, a model
family with different context economics). Nothing moves the wall. Tokenizers differ
by ~30% between model families, so counting means the token-counting API against
the model actually in use, not a rule of thumb.

## The out-of-session backstop

Out of session there is no session to poison, so the placement comparison collapses
toward strictness: a false positive costs a red build and a fix. A check worth
in-session feedback is therefore usually worth a strict out-of-session twin — and
the twin is what makes softening the in-session form safe. Which command constitutes
the backstop is each repository's own contract: the marketplace repository that
distributes this plugin gates its releases on `claude plugin validate`; a consumer
repository gates on its own suite.
