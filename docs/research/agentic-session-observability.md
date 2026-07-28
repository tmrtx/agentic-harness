# Agentic Session Observability — Platform Evaluation

**Date:** 2026-07-28
**Question:** Is self-hosted Langfuse still the right platform for observing agentic
coding sessions (Claude Code), given a workload that is now long-horizon and
tool-dominated rather than single-call?

---

## BLUF

**STAY.**

Langfuse is no longer the single-call-logging tool it was when you picked it.
Between the v4 data-model rewrite and the typed-observation vocabulary, it has
re-architected around agent runs — and it did so in the direction this workload
actually needs. Every shortfall found so far remains integration-side, and the
pattern holds under adversarial checking.

Three findings drive the verdict:

1. **Design fitness is real, not marketing.** v4 made the *step* the primary
   queryable object and deprecated trace-level I/O. Typed observations
   (`agent`, `tool`, `chain`, `retriever`, `evaluator`, `guardrail`) are
   first-class, and agent graphs render off them automatically. This is
   agentic-first architecture, not a retrofit.
2. **Visualization is the weakest axis, and it is a ceiling on debugging, not
   on modeling.** Langfuse renders agent graphs, trace timelines, and genuinely
   good custom dashboards. It does not do time-travel replay or cross-run
   trajectory diffing — and neither does any self-hostable alternative.
3. **Adoption is the strongest axis and it just got stronger.** Most widely
   deployed open-source LLM observability platform, 26M+ SDK installs/month,
   63 Fortune 500 deployments, now owned by ClickHouse. Ecosystem risk on this
   choice is lower today than when you made it.

The only worthwhile addition is a **local transcript viewer** for
single-session forensics. That is one binary, not a platform decision.

---

## The decisive question, answered

> **Is the gap in Langfuse's data model, or in what the integration feeds it?**

**In the integration.** All three known shortfalls are things the hook plugin
failed to send, not things the data model cannot hold.

| Shortfall | Langfuse capability that was available | Verdict |
|---|---|---|
| Reasoning text dropped | Observations accept arbitrary `input`/`output` payloads | Integration-side |
| Cache TTL mispriced | Arbitrary `usage_details` keys, custom model pricing tiers, ingested cost overrides inferred ([Cost tracking][cost]) | Integration-side |
| Resumed sessions duplicated | — (see below) | Integration-side, **no platform safety net** |

**Cache pricing, concretely.** Anthropic prices cache writes at **1.25× base
input for the 5-minute TTL and 2× for the 1-hour TTL**, reads at 0.1×, and the
API already splits the buckets as
`usage.cache_creation.ephemeral_5m_input_tokens` /
`ephemeral_1h_input_tokens` ([Prompt caching][caching]). Langfuse accepts both
as separate `usage_details` keys with their own prices. Collapsing them into
one bucket at one multiplier misprices 1-hour writes by 60% — arithmetic in the
integration, not a platform limit. One trap to carry into the patch: Langfuse
"treats every key in `usage_details` as a separate, non-overlapping bucket," so
sending the parent `cache_creation_input_tokens` *alongside* its two TTL
children double-counts both tokens and cost.

**The one that bends the pattern.** Langfuse states that traces and
observations are **immutable**: "Once ingested, they are final and cannot be
reliably updated," and in v4 "ingested data is not deduplicated on the read
path… Re-inserting therefore creates duplicate records rather than replacing
the original" ([Tracing data updates][updates]). So the obvious fix — emit
deterministic IDs and let the platform upsert — **does not work on v4**. The
integration must track a per-session high-water mark instead. Still an
integration change, so the verdict holds, but note the direction of travel: v3
used `ReplacingMergeTree` with event-sourced merges by primary key
([DeepWiki][deepwiki] — community-maintained, **unverified against source**),
and v4 traded that idempotency for read performance. If the integration was
quietly relying on upsert semantics, v4 removes the floor.

Scores are the sanctioned exception: identified by `id` + `name` + `timestamp`
at date granularity, and re-ingesting with all three matching overwrites. Post-hoc
enrichment of a session belongs there.

---

## Fitness for agentic-tracing-first design

This is the axis the mission actually turns on, so it gets the most weight.

### The hypothesis, tested

> *"The primary object should be the session, not the generation."*

Half-right — and the half that is right has already been shipped.

Langfuse v4 moves to an **observations-first** model: "one immutable
observations table. A trace is all rows that share a `trace_id`," with
trace-level input/output **deprecated** and every operation "a first-class
queryable object" ([Langfuse v4][v4]). The stated motivation is agentic systems
specifically — inspecting a particular tool invocation or agent step without
reconstructing a nested hierarchy. Claimed effect: ≥10× dashboard load
improvement on large projects.

That is neither generation-primary nor session-primary. It is **step-primary**,
and for this workload step-primary is the better target. The questions you
actually ask across a fleet of coding sessions are step-shaped: *which Bash
calls failed across 400 sessions*, *what did compaction cost last week*, *which
subagent type burns the most tokens*. Session-primary storage would force you
to open 400 sessions to answer any of them.

The right formulation is: **session-first is the correct rendering default and
the wrong storage default.** Langfuse got the storage right. The rendering is
where it is thin — see the next section.

### Is the agent vocabulary real, or a relabelling?

Real. Langfuse ships ten observation types, six of which are agent-shaped:
`agent` ("decides on the application flow and can use tools"), `tool` ("single
action… function/API call"), `chain`, `retriever`, `evaluator`, and `guardrail`,
alongside the original `span` / `generation` / `event` and `embedding`
([Observation types][obs-types]). These are not cosmetic: the presence of any
type beyond `span`/`event`/`generation` is what *triggers* agent-graph
rendering ([Agent graphs][graphs]). The type system is load-bearing.

### What a Claude Code session maps onto

| Requirement | Mechanism | Status |
|---|---|---|
| Session as a unit | `sessionId` propagated across traces; session view, scores, annotations, bookmarks, sharing ([Sessions][sessions]) | ✅ (IDs <200 chars; session UUIDs fine) |
| Subagent tree | Nested observations typed `agent` | ✅ |
| Tool timeline | Observations typed `tool` + trace timeline view | ✅ per trace, ❌ across a session |
| Compaction / interrupts as filterable events | Observations typed `event`; v4 queries observations directly | ✅ |
| Cost incl. cache TTLs | Arbitrary `usage_details` + custom pricing + ingested-cost priority | ✅ |
| Reasoning text | Arbitrary observation `input`/`output` | ✅ stored, ❌ no dedicated rendering |
| Agent graph | Auto-inferred from observation types, timings, nesting | ⚠️ beta |
| Replay | Session view "displays a replay of interactions" | ⚠️ trace list, not time-travel |
| Cross-run diffing | Dataset/experiment comparison only | ❌ for arbitrary sessions |

Nothing in the ❌/⚠️ column is a data-model limitation. All three are rendering
ergonomics, and none of them is what broke.

### Standards posture — the thing that caps switching cost

Langfuse is an OpenTelemetry backend with a native OTLP endpoint
(`/api/public/otel`) and "aims to be compliant with the OpenTelemetry GenAI
semantic conventions" ([OTel integration][otel-int]). That matters more than
any single feature, because the GenAI conventions are consolidating: client
spans exited experimental in early 2026, agent spans are experimental but
stable in practice, and OpenTelemetry itself graduated CNCF on 2026-05-21.

Two consequences. First, ecosystem reach comes for free — OpenLLMetry and
OpenLIT extend coverage to Java, Go, AutoGen, and Semantic Kernel without
Langfuse writing SDKs. Second, and more important for this decision: **both
ends of your pipeline are standard**, so staying does not increase switching
cost later. If Langfuse degrades, you re-point an OTLP endpoint.

### A structural shortcut worth taking

Claude Code emits OTel spans natively in beta
(`CLAUDE_CODE_ENHANCED_TELEMETRY_BETA=1`), producing the span tree the hook is
currently reconstructing by hand ([Monitoring][monitoring]):

```
claude_code.interaction
├── claude_code.llm_request
├── claude_code.hook
└── claude_code.tool
    ├── claude_code.tool.blocked_on_user
    └── claude_code.tool.execution
```

`agent_id` and `parent_agent_id` on the `llm_request` and `tool` spans are the
**subagent tree, already assembled**. `cache_read_tokens` /
`cache_creation_tokens` land on `llm_request`. `start_type` on the session
metric is valued `"fresh"` / `"resume"` / `"continue"` / `"agents_view"` — a
native resumption signal. GenAI aliases (`gen_ai.system`,
`gen_ai.request.model`, `gen_ai.tool.call.id`) are emitted alongside.

Since Langfuse ingests OTLP natively, this deletes most of the parser that
produced all three bugs. Two caveats keep the transcript in the picture:
compaction emits **nothing** on the OTel path, and subagent spans have been
reported landing in a separate trace with their own `session.id` rather than
nested under the parent (v2.1.142; **unverified**, version-specific — check
your build).

---

## Visualization

The honest weak axis. Assessed by what the UI actually renders.

### What Langfuse renders well

**Agent graphs** are the strongest agent-specific visual, with two modes that
answer different questions ([Agent graphs][graphs]):

- **Aggregated** — "steps that share a name are merged into a single node with
  a counter," e.g. `retrieve_docs (3/3)`. Loops render as cycles rather than
  long chains. This is the *shape* of the agent.
- **Expanded** — "every call is its own node… and loops unroll into a directed
  acyclic graph in execution order." This is one specific *run*.

For a coding agent that repeatedly cycles Read → Edit → Bash → Read, the
aggregated view is exactly the right default and the expanded view is exactly
the right drill-down. Caveat: **beta**, and the graph is *inferred* from
observation types, timings, and nesting rather than declared — so bad
instrumentation yields a bad graph silently.

**Custom dashboards** are more capable than the category average
([Custom dashboards][dashboards]). Line, bar, time-series, and pie charts;
widgets can source from **traces, observations, or evaluation scores** —
observation-level widgets are the ones that matter here, since that is where
tool calls and subagent steps live. Metrics include count, latency, cost, and
scores; grouping by user, model, time, and trace name; filters on metadata,
timestamps, user properties, model parameters, tags, and score thresholds. As
of July 2026, home-page charts are reusable on custom dashboards, widgets copy
across projects, and whole dashboards export/import as JSON — which makes a
fleet-monitoring dashboard a version-controllable artifact rather than
click-ops. *(Whether you can group by observation **type** or **name** — the
natural axis for "cost by tool" — is not stated in the docs and is
**unverified**; test it before designing dashboards around it.)*

**Trace timeline view** exists for latency debugging within a single trace.

### What it does not render

- **No time-travel replay.** The session view is a trace list described as "a
  replay of interactions" — not a scrubbable re-execution. AgentOps' rewind-and-
  replay debugging has no Langfuse equivalent.
- **No cross-trace tool timeline for a whole session.** You get per-trace
  timelines and a session-level list of traces; you do not get one continuous
  tool timeline across a multi-hour session. For long-horizon work this is the
  most-missed view.
- **No cross-run trajectory diffing.** Dataset/experiment comparison diffs
  *eval runs*, not two agent sessions against the same task.
- **No dedicated reasoning rendering.** Thinking text stores and searches as
  observation I/O; there is no affordance that treats it as reasoning.

### How competitors compare on visualization specifically

**LangGraph Studio / LangSmith** is the strongest agent visualization in the
category: the full graph animated in real time, **state diffs at every node
boundary**, step-through execution, and replay from any checkpoint. Two
disqualifiers here. It is tightly coupled to LangGraph — the node-level state
model is what makes the diffs possible, and Claude Code is not a LangGraph
agent. And Studio is explicitly **a local development tool that connects to
localhost, not designed for remote or production use**; production
observability falls back to LangSmith's hosted dashboard, which is proprietary
and not self-hostable on your terms.

**AgentOps** is the session-replay leader — time-travel debugging that rewinds
an agent run to pinpoint where a reasoning path diverged. The SDK is MIT; the
dashboard is hosted. You would be trading self-hosting for replay.

**Braintrust** has strong timeline replay showing execution sequence and
per-span timing, and the most generous free tier (1M spans/month). **No
self-hosting at all** — a hard disqualifier given your constraint.

**Arize Phoenix** is OTel/OpenInference-native with Claude Agent SDK
instrumentation, self-hostable, but licensed **Elastic License 2.0** — not
OSI-open. Its session model is thinner than Langfuse's; specifics
**unverified** (the sessions docs page 404'd during research).

**Net:** the visualizations Langfuse lacks are (a) owned by platforms you
cannot self-host, or (b) owned by a framework you do not use. There is no
self-hostable, permissively-licensed platform that beats Langfuse on agent
visualization today. This is a genuine ceiling — it is just not a ceiling
migration lifts.

---

## Widespread usage and ecosystem

The axis where the case for staying is strongest, and the one that changed most
since the original decision.

**Langfuse.** The most widely adopted open-source LLM-specific observability
platform. Ended 2025 above 20K GitHub stars with **26M+ SDK installs per
month**; 2026 star counts are reported between **24.6K and 31.5K** (sources
disagree — treat as directional, not precise). Enterprise penetration is the
more meaningful signal: **63 Fortune 500 companies**, including **19 of the
Fortune 50**, by early 2026 ([ClickHouse blog][ch-blog]; adoption figures
sourced from vendor and secondary reporting — **directionally corroborated
across sources, individually unverified**).

**The acquisition is a de-risking event, not a new risk.** ClickHouse acquired
Langfuse on 2026-01-16 alongside a $400M Series D that valued ClickHouse at
$15B ([ClickHouse blog][ch-blog]; [SiliconANGLE][siliconangle]). The MIT
license stays intact, self-hosting remains "a first-class option," and the
roadmap is unchanged. Crucially, Langfuse v3 already ran on ClickHouse
internally *before* any deal — the technical fit predates the acquisition, which
makes the continuity commitments more credible than the genre usually warrants.
Two years ago the live risk on this choice was *will this startup survive*.
That risk is now materially lower.

**Why this axis matters more than feature parity.** For a self-hosted
observability platform you intend to run for years, ecosystem size determines
integration coverage you never have to write, community fixes for bugs you
never have to file, upgrade paths that stay tested, and the ability to hire
someone who already knows the tool. A feature gap closes in a release; an
ecosystem gap does not.

**Comparators.** Comet Opik is the only credible like-for-like on licensing —
Apache 2.0 with **no feature gating between free and paid** — and its adoption
is real: 40M+ traces/day, 150K+ developers, ~12.5K stars in its first 8–9
months. It is the fallback if Langfuse's open-source commitments decay. But
swapping one OTel-ingesting, self-hostable trace store for another buys nothing
the integration patch does not already deliver, and costs a migration.

The broader market grew from $1.97B (2025) to $2.69B (2026), with Gartner
projecting 60% of software engineering teams adopting AI evaluation platforms by
2028. Category consolidation favors the incumbent with the largest install base.

---

## Steelman: stay and patch

The strongest honest case against migrating, stated at full strength.

**1. The evidence is unanimous and adversarially checked.** Three independent
shortfalls, three integration causes, each traced to a specific documented
Langfuse capability the integration does not use. That is not a sampling
artifact. A platform that keeps getting blamed for its caller's bugs is not the
problem.

**2. Migration relitigates the same bugs on a new substrate.** The integration
is what produces wrong reasoning capture, wrong cache arithmetic, and duplicate
emission on resume. Every one of those follows the code to a new platform. You
would pay a migration and still owe the patch — with a fresh schema, fresh
ingestion semantics, and a fresh set of unknown-unknowns to find in production.

**3. Langfuse moved toward this workload, not away.** Observations-first storage,
a typed agent vocabulary that drives graph rendering, agent graphs, and
observation-level dashboard widgets are all recent and all agent-shaped. The
platform is tracking the category shift the mission describes, in the same
direction.

**4. Adoption and ownership both improved.** Most-deployed OSS platform in the
category, 63 Fortune 500 deployments, now backed by a $15B infrastructure
company that was already its storage engine. The durability question that
mattered two years ago has a better answer today than it did then.

**5. Nothing on the market is a strict upgrade.** The better visualizations are
locked behind SaaS-only (Braintrust), hosted backends (AgentOps), or a framework
you do not use (LangGraph Studio). The one genuinely comparable OSS platform
(Opik) is a lateral move.

**6. Exit cost stays flat.** Both ends are standard OTel. Staying does not
increase switching cost.

**Where the steelman honestly weakens.**

- **Self-hosting got heavier.** v3+ requires ClickHouse, Redis, S3/MinIO, and
  Postgres. Langfuse recommends ≥4 cores / 16 GiB and ~100 GiB storage, and
  states plainly that "the docker compose setup lacks high-availability,
  scaling capabilities, and backup functionality" and is **not recommended for
  production** ([Docker Compose][compose]). One box works as a
  single-point-of-failure appliance you back up yourself.
- **Nine features sit behind a commercial key** — project-level RBAC, data
  retention policies, audit logs, server-side data masking, SCIM, and others
  ([License key][license]). Core tracing, sessions, scores, and the API are MIT
  and unlimited, so nothing blocks this workload — but "MIT, fully open" is not
  the whole story, and **server-side data masking** is the one gated feature a
  coding-session tracer might genuinely want, since transcripts carry source
  code and shell commands.
- **v4 is not a stable self-host target yet.** Cloud preview since 2026-03-10;
  the self-hosted v4 build shipped as a **pre-release** for migration feedback.
  If you are on self-hosted v3, plan the integration patch against v3 semantics
  and treat the v4 migration as separate work.

---

## Gaps nobody solves

Not Langfuse-specific. Open across the category; migration fixes none of them.

1. **Compaction is invisible.** Claude Code emits no compaction telemetry at
   all, and no platform models "what did the agent forget, and what did that
   cost." For a long-horizon workload where compaction is a primary failure
   mode, the highest-value signal in the system is the one nobody captures.
   This is the single largest gap found.
2. **Cross-run trajectory diffing does not exist.** Every platform diffs *eval
   runs* against a dataset. None diffs two agent *trajectories* — "same task,
   two sessions, where did they diverge." Most claimed, least delivered
   capability in the category.
3. **Resumption has no identity anywhere.** No platform models "the same
   logical session, resumed." Claude Code emits `start_type: "resume"` and
   stops; correlation is the caller's problem everywhere.
4. **Interrupts are barely instrumented.** The only signal is
   `source: "user_abort"` on `claude_code.tool_decision`, scoped to dismissing a
   permission prompt. Esc mid-stream produces nothing.
5. **No cross-trace session timeline.** Universal: platforms render timelines
   within a trace and lists across a session. One continuous tool timeline over
   a multi-hour session does not exist anywhere.
6. **Per-TTL cache cost attribution is weak everywhere.** Anthropic splits the
   buckets; most integrations and most platform-side model catalogs collapse
   them.

---

## Landscape scan

| Platform | Self-host | License | Agentic-first design | Visualization | Adoption |
|---|---|---|---|---|---|
| **Langfuse** | Yes (heavy stack; compose not prod-recommended) | MIT core; 9 features gated | Observations-first storage; 6 agent-shaped observation types | Agent graphs (2 modes, beta); trace timeline; strong custom dashboards | Most-deployed OSS; 26M installs/mo; 63 F500 |
| **Comet Opik** | Yes (docker compose) | Apache 2.0, **no gating** | Full trace trees for multi-step agents; threads | Production dashboards | 40M traces/day; 150K devs; ~12.5K stars |
| **Arize Phoenix** | Yes (Docker/K8s/cloud) | **Elastic License 2.0** | OTel/OpenInference-native; Claude Agent SDK instrumentation | Thinner session model (**unverified**) | Established in OSS observability |
| **AgentOps** | SDK only; backend hosted | SDK MIT | Purpose-built for agents, not retrofitted | **Session replay + time-travel** — category leader | 400+ LLM/framework integrations |
| **Braintrust** | **No** | Proprietary SaaS | Eval-centric | Timeline replay w/ per-span timing | 1M spans/mo free tier |
| **LangSmith + Studio** | Paid tier only | Proprietary | LangGraph-coupled | **Node-level state diffs**, step-through, replay-from-checkpoint — best in category, but local-dev-only and LangGraph-bound | Large LangChain ecosystem |
| **claude-devtools** | Local only | **Unverified** | Purpose-built for Claude Code transcripts | Thinking sections, recursive subagent trees, per-tool renderers, cross-session search | Niche tool |

Comparative rankings and overhead figures from vendor blog comparisons (e.g.
"AgentOps 12% vs Langfuse 15% overhead") come from content-marketing sources
with no published methodology and are **unverified**. I would not weight them.

**The one addition worth making.** `claude-devtools` and `claude-replay` are
purpose-built for this exact workload and cost nothing: they read `~/.claude/`
directly, run locally with no API keys or subscription, and render the subagent
trees, per-tool views, and thinking sections Langfuse's session view does not
([claude-devtools][cdt]; [claude-replay][replay]). Langfuse as fleet-level
system of record — cost, aggregation, evals, cross-session queries — plus a
local viewer for single-session forensics. Complementary, not competing; verify
the license before adopting.

---

## Recommended sequence

1. **Fix cache pricing.** Emit `ephemeral_5m_input_tokens` and
   `ephemeral_1h_input_tokens` as separate `usage_details` buckets at 1.25× and
   2× base input, or send `cost_details` directly. Do not also send the parent
   `cache_creation_input_tokens` — Langfuse double-counts overlapping buckets.
2. **Fix resumption.** Add a per-session high-water-mark cursor. Do not rely on
   ID-based deduplication; v4 does not provide it.
3. **Emit typed observations.** Map subagents to `agent`, tool calls to `tool`,
   LLM calls to `generation`, compaction and interrupts to `event`. This is what
   turns agent-graph rendering on — it is inferred from types, so untyped
   instrumentation silently yields no graph.
4. **Pilot the native OTel exporter** against a scratch project. If the span
   tree lands cleanly, delete the transcript-derived structure code and keep the
   transcript only for what OTel drops (reasoning text, compaction).
5. **Build the fleet dashboard** on observation-level widgets and export it as
   JSON into version control. Verify first whether grouping by observation type
   or name is supported — the "cost by tool" axis depends on it.
6. **Add a local session viewer** for forensics. One binary, no platform change.
7. **Re-evaluate in ~2 quarters**, gated on three signals: whether ClickHouse
   honors the MIT and self-hosting commitments; whether self-hosted v4 reaches
   GA with observations-first intact; and whether agent graphs exit beta.

---

## Sources

- [Langfuse — Observability data model](https://langfuse.com/docs/observability/data-model)
- [Langfuse — Sessions][sessions]
- [Langfuse — Observation types][obs-types]
- [Langfuse — Agent graphs][graphs]
- [Langfuse — Custom dashboards][dashboards]
- [Langfuse — Token and cost tracking][cost]
- [Langfuse — How to update traces, observations, and scores?][updates]
- [Langfuse — Fast Preview: Faster and Observations-First (v4)][v4]
- [Langfuse — OpenTelemetry integration][otel-int]
- [Langfuse — Self-hosting: Docker Compose][compose]
- [Langfuse — Self-hosting: License key][license]
- [DeepWiki — Langfuse tracing system][deepwiki] *(community-maintained; unverified)*
- [ClickHouse — ClickHouse welcomes Langfuse][ch-blog]
- [SiliconANGLE — ClickHouse raises $400M, acquires Langfuse][siliconangle]
- [Claude Code — Monitoring (OpenTelemetry)][monitoring]
- [Claude Platform — Prompt caching][caching]
- [LangSmith Studio — docs](https://docs.langchain.com/langsmith/studio)
- [LangGraph Studio: visual debugger for agent graphs](https://markaicode.com/langgraph-studio-visual-debugger-agent-graphs/) *(third-party; unverified)*
- [Arize Phoenix (GitHub)](https://github.com/Arize-ai/phoenix)
- [Comet Opik (GitHub)](https://github.com/comet-ml/opik)
- [claude-devtools — transcripts][cdt]
- [claude-replay][replay]
- [Best AI agent observability tools 2026 (Latitude)](https://latitude.so/blog/best-ai-agent-observability-tools-2026-comparison) *(vendor blog; unverified)*

Cache-TTL multipliers were additionally cross-checked against the bundled
`claude-api` skill reference, which agrees with the linked platform
documentation. Adoption figures (stars, installs, Fortune 500 counts, Opik
volumes) come from vendor announcements and secondary reporting; they
corroborate each other directionally but no individual figure was verified
against a primary counter.

[sessions]: https://langfuse.com/docs/observability/features/sessions
[obs-types]: https://langfuse.com/docs/observability/features/observation-types
[graphs]: https://langfuse.com/docs/observability/features/agent-graphs
[dashboards]: https://langfuse.com/docs/metrics/features/custom-dashboards
[cost]: https://langfuse.com/docs/observability/features/token-and-cost-tracking
[updates]: https://langfuse.com/faq/all/tracing-data-updates
[v4]: https://langfuse.com/docs/v4
[otel-int]: https://langfuse.com/integrations/native/opentelemetry
[compose]: https://langfuse.com/self-hosting/docker-compose
[license]: https://langfuse.com/self-hosting/license-key
[deepwiki]: https://deepwiki.com/langfuse/langfuse/8.1-tracing-system
[ch-blog]: https://clickhouse.com/blog/clickhouse-acquires-langfuse-open-source-llm-observability
[siliconangle]: https://siliconangle.com/2026/01/16/database-maker-clickhouse-raises-400m-acquires-ai-observability-startup-langfuse/
[monitoring]: https://code.claude.com/docs/en/monitoring-usage
[caching]: https://platform.claude.com/docs/en/build-with-claude/prompt-caching
[cdt]: https://claude-dev.tools/docs/transcripts
[replay]: https://github.com/es617/claude-replay
