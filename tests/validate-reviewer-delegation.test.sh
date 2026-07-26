#!/bin/sh
# Executable expectations (CIA-8) for the reviewer delegation gate.
#
# The unit under test is the gate as consumers receive it: the command
# registered in plugins/harness/hooks/hooks.json for subagent launches,
# executed the way Claude Code executes plugin hooks (sh -c, with
# CLAUDE_PLUGIN_ROOT set, payload on stdin). Given a PreToolUse payload,
# it stays silent and exits 0 (the delegation proceeds), emits a deny
# decision teaching the accepted delegation grammar, or — when the gate
# itself cannot run or cannot read the payload — exits 2, the one code
# PreToolUse treats as blocking: a broken gate blocks delegation until
# it is fixed, never silently un-gates review.
set -u
cd "$(dirname "$0")/.."
PLUGIN_ROOT="$PWD/plugins/harness"
fails=0
total=0

# The registered gate: the PreToolUse command whose matcher covers both
# subagent-launch tool names ("Agent", and "Task" for pre-2.1.63).
GATE_CMD=$(python3 - <<'PY'
import json, re
cfg = json.load(open("plugins/harness/hooks/hooks.json"))
for entry in cfg["hooks"]["PreToolUse"]:
    try:
        if re.fullmatch(entry["matcher"], "Agent") and re.fullmatch(entry["matcher"], "Task"):
            print(entry["hooks"][0]["command"])
            break
    except re.error:
        pass
PY
)
if [ -z "$GATE_CMD" ]; then
  echo "FAIL: hooks.json registers no PreToolUse command covering both Agent and Task"
  exit 1
fi

# check <allow|deny|block> <case name> [plugin root] [PATH]  (payload on stdin)
check() {
  expected="$1"
  name="$2"
  root="${3:-$PLUGIN_ROOT}"
  searchpath="${4:-$PATH}"
  total=$((total + 1))
  out=$(CLAUDE_PLUGIN_ROOT="$root" PATH="$searchpath" /bin/sh -c "$GATE_CMD" 2>/dev/null)
  status=$?
  if [ "$expected" = "block" ]; then
    # blocking is spoken through exit code 2 alone: any other code lets
    # the launch proceed, and a decision on stdout would be a deny
    if [ "$status" -eq 2 ] && [ -z "$out" ]; then
      echo "  ok $name"
    else
      echo "FAIL $name: expected exit 2 with no output, got exit $status (stdout: ${out:-<empty>})"
      fails=$((fails + 1))
    fi
    return
  fi
  if [ "$status" -ne 0 ]; then
    echo "FAIL $name: exited $status (allow and deny both exit 0)"
    fails=$((fails + 1))
    return
  fi
  got=$(printf '%s' "$out" | python3 -c '
import json, sys
raw = sys.stdin.read().strip()
if not raw:
    print("allow")
    raise SystemExit
try:
    d = json.loads(raw)["hookSpecificOutput"]
except Exception:
    print("garbled")
    raise SystemExit
if d.get("permissionDecision") != "deny":
    print("garbled")
elif not all(s in d.get("permissionDecisionReason", "") for s in ("CIA-", "full coverage")):
    # the deny must teach both accepted forms, or the teaching text has
    # drifted from the grammar it enforces
    print("deny-without-guidance")
else:
    print("deny")
')
  if [ "$got" = "$expected" ]; then
    echo "  ok $name"
  else
    echo "FAIL $name: expected $expected, got $got (stdout: ${out:-<empty>})"
    fails=$((fails + 1))
  fi
}

# --- Delegations that must be rejected ---------------------------------

check deny "freeform task description (the observed misuse)" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","description":"Review auth changes","prompt":"Review the changes I made to the auth flow. I refactored the token refresh in src/auth.ts and already checked the tests pass."}}
EOF

check deny "freeform prompt via the post-rename Agent tool" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"harness:reviewer","prompt":"Take a look at my parser rework; the interesting parts are in src/parse/."}}
EOF

check deny "codes followed by steering prose" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"CIA-7, CIA-8 — focus on the parser; the tests were already reviewed"}}
EOF

check deny "codes joined as prose instead of commas" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"CIA-7 and CIA-8"}}
EOF

check deny "multiline prompt with quotes" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"CIA-7\nAlso note: the \"legacy\" module is out of scope."}}
EOF

check deny "unqualified agent name still reaches the same agent" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"reviewer","prompt":"Please review my latest commit for structural problems."}}
EOF

check deny "case-variant agent name still reaches the same agent" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"Harness:Reviewer","prompt":"Please review my latest commit for structural problems."}}
EOF

# --- Delegations that must pass ----------------------------------------

check allow "canonical no-space code list" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"harness:reviewer","prompt":"CIA-7,CIA-8"}}
EOF

check allow "comma-separated codes with spaces" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","description":"Governance review","prompt":"CIA-7, CIA-8"}}
EOF

check allow "single sub-code" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"CIA-7.3"}}
EOF

check allow "lowercased code" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"cia-8"}}
EOF

check allow "empty prompt requests full coverage" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":""}}
EOF

check allow "explicit full-coverage phrase" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"full coverage"}}
EOF

check allow "code outside the reviewer's coverage is its call, not the gate's" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"harness:reviewer","prompt":"CIA-9"}}
EOF

# --- Out of the gate's jurisdiction ------------------------------------

check allow "other subagents keep freeform prompts" <<'EOF'
{"tool_name":"Task","tool_input":{"subagent_type":"general-purpose","prompt":"Search the codebase for usages of the legacy token refresh and summarize them."}}
EOF

check allow "near-name consumer agents stay ungated" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"code-reviewer","prompt":"Review the diff for style issues and summarize."}}
EOF

# --- Failure of the gate itself blocks ---------------------------------
# The gate cannot tell whose delegation it is failing on, so a gate that
# cannot run or cannot read the payload blocks the launch outright. That
# is the point: enforcement failures surface as breakage that prompts a
# fix, never as a silent bypass of review. (The matcher fires for every
# subagent launch, so until fixed this blocks them all.)

check block "unparseable payload blocks rather than bypasses" <<'EOF'
this is not json
EOF

check block "malformed reviewer payload blocks rather than bypasses" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"harness:reviewer","prompt":{"not":"a string"}}}
EOF

check block "unreadable agent identity blocks rather than bypasses" <<'EOF'
{"tool_name":"Task","tool_input":{"prompt":"the subagent_type field is missing: every call on this tool is a delegation, so the gate cannot tell whether this one is the reviewer's"}}
EOF

EMPTY_ROOT=$(mktemp -d)
trap 'rm -rf "$EMPTY_ROOT"' EXIT

check block "missing gate script blocks delegation until repaired" "$EMPTY_ROOT" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"harness:reviewer","prompt":"freeform prompt that a live gate would deny"}}
EOF

check block "machine without python3 blocks rather than silently un-gating" "$PLUGIN_ROOT" "$EMPTY_ROOT" <<'EOF'
{"tool_name":"Agent","tool_input":{"subagent_type":"harness:reviewer","prompt":"freeform prompt that a live gate would deny"}}
EOF

# ------------------------------------------------------------------------
echo
if [ "$fails" -eq 0 ]; then
  echo "PASS: $total/$total cases"
else
  echo "FAIL: $fails of $total cases failed"
  exit 1
fi
