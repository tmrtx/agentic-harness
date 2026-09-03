# Stripped SDK runner

A Python client for Claude's `/v1/messages` API. Requests are billed to
the `claude` subscription rather than to an API key. It depends on the
Python standard library only.

## Why not `claude -p`

`claude -p` inserts a `<system-reminder>` block into the user turn. The
block carries the user's email, the current date, and a note that the
content may or may not be relevant. The model reads that block as part
of the task. If the answers are being scored, the reminder becomes part
of what is scored. This runner sends the caller's system prompt and
user text and nothing else.

## What a request contains

Each request carries only what the API requires for a subscription
call:

- an `Authorization` header with the subscription's OAuth token
- an `anthropic-version` header
- a billing line as the first block of the system prompt
- `max_tokens`, supplied when the caller omits it

Three headers are sent by choice rather than necessity: `Content-Type`,
`User-Agent`, and `X-Claude-Code-Session-Id`. Everything else the CLI
sends (beta flags, `X-Stainless-*` headers, account identity metadata,
context management) was tested against the live API, found
unnecessary, and removed. Each element that remains has a comment in
`bare_runner.py` recording what happens when it is removed.

When re-testing the request shape, use `claude-sonnet-5` or
`claude-opus-5`. `claude-haiku-4-5` does not enforce the billing line,
so a test against haiku alone concludes that the line is optional when
every other model requires it. This mistake has been made before.

## bare_runner.py

Sends one prompt and returns the reply.

```python
from bare_runner import rollout

r = rollout("system.txt", "your question")
r["text"]        # the reply text
r["thinking"]    # the streamed reasoning summary, or None
r["tool_calls"]  # tool_use blocks with parsed input
r["usage"]       # token counts
```

The result also carries `model`, `stop_reason`, `status`, `attempts`,
`session_id`, and `raw` (the error body of a non-200 response).

From a shell:

```
python3 bare_runner.py --system-prompt-file sys.txt "your question"
```

The user text can also be piped on stdin. The CLI prints the result as
JSON and exits 0 when a reply arrived.

**Defaults.** The model is `claude-opus-5`, overridable with
`BARE_RUNNER_MODEL` or `--model`. Reasoning is on by default because
scored rollouts want it; pass `thinking=False` (`--no-thinking`) to
disable it. Every other option is off unless requested:

- `tools=` and `tool_choice=` for tool use
- `output_format=` for a JSON reply conforming to a schema
- `cache=True` for prompt caching with a one-hour cache
- `effort=` for `output_config.effort` (5-family models only)

**Retry on a bad reply.** `rollout_with_retry(system_file, user_text,
accept)` calls `accept(text)` on the reply and retries once when it
returns False. It returns the result and the number of extra attempts.

**Multi-turn tool loops.** `build_body()` builds one request body and
returns it with a session id. `stream_round(body, sid, halt=)` sends
it. `halt` is called with each content block as the block starts
streaming; returning True closes the connection at that point, after a
few tokens. This is how think.py and dryrun.py stop a round as soon as
the model's first choice of channel is visible.

**Auth.** The token comes from `ANTHROPIC_STRIPPED_SDK_RUNNER` when
set, otherwise from `~/.claude/.credentials.json`. There is no API-key
path. An expired or rejected token exits with a message telling you to
run a `claude` command to refresh it.

**Quota.** HTTP 429, 503, and 529 responses cause a pause and a retry.
The pause is `BARE_RUNNER_QUOTA_WAIT_S` seconds (default 300), at most
`BARE_RUNNER_QUOTA_MAX_WAITS` times (default 12). The attempt count is
returned in the result.

**Billing check.** A 200 response billed to the subscription carries
`anthropic-ratelimit-unified-*` headers. If a 200 arrives without
them, the runner prints a warning to stderr, once per process, listing
the headers it expected and the ones it got.

## think.py

Returns the model's reasoning as ordinary text instead of private
thinking tokens.

The model is forced through two tool calls. In round one, `tool_choice`
forces a tool named `think`, so the reasoning arrives as that tool's
`thoughts` argument. In round two, the runner answers each `think` call
with the tool result "Acknowledged." and forces a tool named `output`,
so the answer arrives as that tool's argument. Confirmed runs billed
zero thinking tokens with reasoning volume comparable to native
thinking. The reasoning is still paid for: it bills as ordinary output
tokens, and the scheme costs two requests.

```python
import think

r = think.run(system_text, "your question")
r["thoughts"]  # the reasoning text
r["answer"]    # the answer
r["verdict"]   # "ok", or a description of what went wrong
```

Both tools have no description and one string field named after the
tool (`think` takes `thoughts`, `output` takes `output`). A description
would be extra steering text sent with every request, and the forced
`tool_choice` is what makes the model use the tool.

Pass `answer_fields=("premise", "conclusion")` to get the answer as a
dict with those keys. The fields become the `output` tool's input
schema. The API's structured-output option is not used because some
models refuse it after a reasoning tool call; a tool schema has never
been refused.

Failure handling:

- If the model starts a native thinking block instead of calling the
  tool, the round is closed within a few tokens and the verdict is
  `native-thinking`. The same verdict is given when the response
  reports any billed thinking tokens.
- A refusal is reported as the verdict rather than returned as an
  empty answer.
- A transport error or a missing forced call is reported as the
  verdict, with the round it happened in.

Thinking stays enabled in every request, so a billed count of zero
means the model chose the tool over an available private pass. The 4.5
model family rejects forced `tool_choice` while thinking is enabled, so
pass `thinking=False` for those models. That defeats the zero-thinking
claim and is useful only for plumbing tests.

## dryrun.py

Shows what the model would do with a task before anything can execute.

It runs think.py's first round with a target environment's full tool
list declared alongside the `think` tool, so the model plans as it
would inside that environment. Nothing is executed; no tool has an
implementation here. The result holds the reasoning chain and, when
the probe is on, the first action the model intended to take with its
arguments filled in. Any other tool call the model makes in the forced
round is recorded in `cochannel_calls` and never executed.

```
python3 dryrun.py "the task you want to check"
```

The probe is on by default. It sends one more round on the same
session with `tool_choice` set to `any` and closes the connection as
soon as the first tool call has streamed completely. `first_action` is
then `{"name": ..., "input": ...}`, or `{"none": reason}` when the
model chose to reason further or the round failed. Pass `--no-probe`
to skip it.

This catches a failure that asking the model does not: the model
misreading the task and acting on the misreading in its plan, while
still describing the task correctly when asked to restate it.

The default environment under `envs/` is a captured Claude Code
session: the system prompt and the 23 tool definitions an interactive
`claude` session sends on its first request (CLI 2.1.233, captured
2026-08-15), recorded verbatim. A synthetic or trimmed environment
defeats the purpose, because the model plans with the prompt and tools
it sees. Override with `--tools-file` and `--system-prompt-file`. MCP
servers and repository skills are not in the capture; pass your own
tools file for a customized target.

## wire_capture.py

A capture proxy for debugging. It relays requests to the API unchanged
and writes each request body and its headers to disk first.

```
python3 wire_capture.py 8899
ANTHROPIC_BASE_URL=http://127.0.0.1:8899 python3 bare_runner.py ...
```

Captures go to `WIRE_CAPTURE_DIR` (default `/tmp/cc-sniff/capture`) as
`req-NNNN.json` with a `req-NNNN.headers.json` beside it.

Warning: the header files include the `Authorization` header with the
OAuth token. Treat the capture directory as secret and delete it when
you are done.

## offline_test.py

```
python3 offline_test.py
```

Needs no network and no login. A local server answers from canned
responses. It covers response parsing, tool calls, the `halt`
callback, refusals, quota retries, the billing warning, the think.py
two-round transcript, the dryrun.py round and probe, and both CLIs. It
also asserts the exact set of headers and body keys the runner sends,
so any addition to the request fails here.

## integration_test.py

```
python3 integration_test.py
INTEGRATION_MODEL=claude-opus-5 python3 integration_test.py
```

Needs a real login. It makes about twenty calls at `max_tokens` 16 plus
one normal rollout. It checks the request contract against the live
API rather than trusting the comments in the code:

- the minimal request is accepted
- removing `Authorization`, `anthropic-version`, or the billing line
  fails in the documented way, and a billing line that is not the first
  system block fails too
- `claude-haiku-4-5` accepts a request with no billing line, which is
  why it must not be used for these checks
- tools, forced `tool_choice`, structured output, adaptive thinking,
  effort, and streaming all work without beta headers
- forced `tool_choice` works with adaptive thinking and is rejected
  with thinking type `enabled`
- a subscription 200 carries the unified rate-limit headers

Run it after changing the runner, and occasionally otherwise. The API
it tests can change without notice.
