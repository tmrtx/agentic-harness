# Stripped SDK runner — bare model calls with a clean scored turn

Direct `/v1/messages` submissions over the `claude` subscription
login. Python stdlib only.

WHY: `claude -p` is a perfectly good transport with one disqualifying
flaw for scored rollouts — it injects a `<system-reminder>` block
(userEmail, currentDate, "may or may not be relevant" context) into
the USER TURN, and the model treats it as task-relevant signal. This
runner submits the CLI's wire shape without that contamination:
billing-header block and CLI headers in exact order and casing kept;
the SDK identity line ("You are a Claude agent…") deliberately
absent, because it is steering text and nothing but the caller's
words may steer a scored rollout; the user turn carries your text
and nothing else.

## bare_runner.py
- Library: `rollout(system_file, user_text, model=, effort=,
  max_tokens=, thinking=, cache=, output_format=, tools=,
  tool_choice=, timeout=)` returns `{text, thinking, tool_calls,
  model, stop_reason, usage, status, attempts, session_id, raw}`.
  `rollout_with_retry(..., accept)` adds one retry under your reply
  contract (accept judges text; a tool-only reply returns as-is). Model/effort default to BARE_RUNNER_MODEL /
  BARE_RUNNER_EFFORT (claude-opus-5 / xhigh).
- Reasoning is captured by default: the authored `thinking` carries
  `display: "summarized"` — the one deliberate addition over the -p
  wire, because the CLI omits the field and the server then BILLS
  thinking tokens while never streaming the summary. The streamed
  summary text returns as `thinking`; pass `thinking=False` for the
  CLI's disabled shape (which also drops context_management, as the
  CLI does — the clear_thinking strategy 400s without thinking), or
  an explicit dict to control display yourself. Tiny adaptive bursts (tens of tokens) may stream no
  summary even when unmasked — `usage.output_tokens_details`
  disambiguates a skipped summary from disabled thinking.
- CLI: `python3 bare_runner.py --system-prompt-file sys.txt "text"`
  (user text from stdin when omitted) prints the result dict as
  JSON; flags mirror the keyword arguments (`--cache`,
  `--output-format '<json schema>'`, ...). Exits 0 iff a reply
  arrived.
- The wire differs per MODEL FAMILY (observed live from `-p`): the
  4.5 family sends max_tokens 32000 with thinking {budget 31999,
  enabled} at every effort; the 5 family (opus-5, fable-5, sonnet-5)
  sends 64000, thinking {adaptive}, effort inside output_config, and
  a longer beta list.
- Options, all OFF by default: `cache=True` — the CLI's
  prompt-caching shape (ephemeral 1h + extended-cache-ttl beta);
  `output_format={json schema}` — structured outputs
  (output_config.format + structured-outputs beta; the reply text is
  the conforming JSON); `tools=[...]` / `tool_choice={...}` — on the
  wire verbatim, tool calls back parsed in `tool_calls`. The beta
  list tracks the features used, exactly as the CLI's does.
- Multi-round: `build_body(..., messages=, session_id=)` builds one
  round's body over a full transcript under one session id;
  `stream_round(body, halt=)` sends it live — halt sees each
  content_block_start and a truthy return hangs up on the spot
  (stop_reason "halted"; a first-block hang-up costs 2–5 tokens, the
  probe / abort lever). Streaming sends Accept-Encoding identity —
  the one other deliberate wire exception, since line-at-a-time
  reads cannot pass through stdlib gzip.
- Auth is `ANTHROPIC_STRIPPED_SDK_RUNNER` when that variable is set,
  otherwise the CLI's own files; identity always comes from those
  files (`~/.claude/.credentials.json`, `~/.claude.json`), token
  re-read per call. There is no ANTHROPIC_API_KEY path. Quota arrives as
  HTTP 429/5xx — never scoreable text — and becomes a bounded pause
  (BARE_RUNNER_QUOTA_WAIT_S / _QUOTA_MAX_WAITS).
- Calls go to ANTHROPIC_BASE_URL when set, api.anthropic.com
  otherwise.

## think.py
- Reasoning as a tool call — the forced two-round scheme from the
  2026-08-13 experiments: round 1 forces a `think`
  call (the reasoning arrives as the calls' `thoughts` input —
  parallel calls all count and join), round 2 returns
  "Acknowledged." and forces `write_answer`. Confirmed runs billed
  0 thinking tokens with reasoning volume on par with native
  thinking. Forcing is required — unforced, the models drift back
  to built-in thinking.
- `run(system_text, user_text, model=, effort=, answer_fields=, ...)`
  returns `{verdict, thoughts, answer, native_thinking_tokens,
  output_tokens, session_id, rounds}`; "ok" iff both forced calls
  arrived with 0 thinking tokens billed. `answer_fields=(...)` types
  the answer into write_answer's input schema — the refusal-free
  replacement for structured output (fable refuses
  output_config.format after a reasoning-tool call; tool input schemas
  were never refused). `probe(body)` reads one content block and
  hangs up: the 2–5-token channel check.
- Guard rails wired in: a native thinking block aborts at its first
  streamed block, stop_reason "refusal" becomes the verdict rather
  than silence, and billed thinking_tokens must be 0.
- The scheme's vocabulary is public — THINK, halt_native,
  bad_round, native_tokens, thoughts_text, acknowledged — so
  sibling schemes (dryrun.py) compose instead of copying.

## dryrun.py
- Stopped-at-reasoning dry runs — the pre-ship behavioral X-ray.
  WHY (2026-08-14 dry-run experiments): reasoning chains contain
  defect enactment — the model performing a misreading in its plan
  rather than stating it anywhere — that no readback or self-report
  surfaces. The dry run captures that chain from a prompt before
  any side effect exists.
- `dry_run(system_text, user_text, tools=, model=, effort=, probe=,
  ...)` runs think.py's forced round 1 with the target
  environment's FULL tool roster declared alongside — the model
  reasons inside a tooled environment and the chain arrives as the
  think calls' input — and never sends a working round (probe off:
  exactly one request reaches the wire). Calls smuggled into the
  forced round are recorded (`cochannel_calls`), never executed.
- The default roster is the real thing: `roster-claude-code.json`,
  the 20-tool declaration Claude Code itself puts on the wire,
  captured verbatim from a default Agent SDK `query()`
  (claude-cli 2.1.233 / agent-sdk 0.3.233, 2026-08-15; pristine
  container, wire_capture.py in front of a 401 stub — the request
  was recorded, nothing reached the API, all 11 retry bodies
  byte-identical). `tools=None` declares it; `tools=[]` dry-runs
  bare; pass your own list for a customized target — MCP servers
  and per-repo skills are never in a default capture. Re-freeze by
  re-running that rig against a newer SDK and replacing the file.
  Returns `{verdict, thoughts, cochannel_calls, first_action,
  probe_thoughts, native_thinking_tokens, output_tokens,
  session_id, rounds}`; verdict "ok" iff round 1 delivered the
  forced call with 0 thinking tokens billed — think.py's rails.
- The probe (on by default): one more round on the SAME session —
  the transcript the model actually produced, every call answered
  "Acknowledged.", tool_choice `{"type": "any"}` — hung up right
  after the FIRST tool_use block completes. The first intended
  action arrives with full args and nothing can execute. Cost: the
  transcript re-billed as input plus about one call's output; a
  halted round's usage counts only what streamed before the
  hang-up, so the probe's output_tokens are a floor. A probe that
  keeps reasoning or refuses degrades `first_action` to
  `{"none": reason}` (extra reasoning kept in `probe_thoughts`),
  never the verdict.
- CLI: `python3 dryrun.py --system-prompt-file sys.txt "user text"`
  (`--tools-file` overrides the shipped roster; `--no-probe` for
  round-1-only). Prints the result dict as JSON; exits 0 iff
  verdict "ok".

## wire_capture.py
- Debug/verification proxy, kept lean for when the wire needs to be
  seen: relays traffic byte-for-byte untouched and writes each JSON
  POST body to the capture dir as `req-NNNN.json` (+ `.headers.json`
  sibling). Distilled from the full cc-sniff proxy; its Langfuse
  export, timing marks, and thinking.display rewrite are deliberately
  absent (a capture tool must not mutate the wire).
- `python3 wire_capture.py 8899`, then point ANTHROPIC_BASE_URL at
  it. Env: WIRE_CAPTURE_DIR / _UPSTREAM / _SCHEME. The counter seeds
  past existing captures so restarts never overwrite evidence; read
  capture windows by mtime, never filename order. Captures include
  auth headers — treat the dir as secret material.

## integration_test.py
- `python3 integration_test.py` — live, fully automated, no stored
  fixtures. Each run mints a FRESH `claude -p` capture as the shape
  reference through two CHAINED wire_capture instances, then runs
  four authored rollouts (cache-on CC shape, default, structured,
  tools + forced tool_choice) through the same chain and asserts:
  relay byte-fidelity, shape
  parity of the cache-on wire vs the reference (only caller texts,
  the deliberately absent reminder, session ids, lengths, and the
  billing hash suffix may differ), the option contracts, clean
  authored wires, and the tripwire — the `-p` reference smuggles a
  reminder, no authored wire ever does. On drift it prints the fresh
  wire values to re-freeze bare_runner's profiles from.
- Run once per model family (`INTEGRATION_MODEL=claude-opus-5`) —
  the wire differs between the 4.5 and 5 families.

## offline_test.py
- `python3 offline_test.py` — no network, no login: a local canned
  /v1/messages server plays the API. Covers what the live test
  cannot cheaply: response parsing, tool_calls, stream_round's halt
  lever, refusal surfacing, quota retry, the think-tool two-round
  transcript mechanics, and the dry run's stopped-at-reasoning
  mechanics.
