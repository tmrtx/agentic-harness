#!/usr/bin/env bash
# Tests for the writing guard. Each case pipes a hook payload into the gate and
# asserts what a caller can observe: the decision the harness reads off stdout,
# the marker line on stderr, and the files the gate leaves behind. Exit code is
# the number of failing cases.
#
# The gate is a PreToolUse hook on two surfaces - the Artifact tool (a file at
# rest) and a Bash `git commit` (the message inside the command) - so every case
# below is one of those two payload shapes.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$REPO/plugins/harness/hooks/writing-guard.sh"
CORPUS="$REPO/tests/writing-guard-corpus.json"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fails=0

# Hermetic state: the gate keeps its attempt counters under CLAUDE_PLUGIN_DATA
# and its bypass log under $HOME/.claude, so the suite owns both directories and
# never touches the developer's own.
export CLAUDE_PLUGIN_DATA="$TMP/plugin-data"
export HOME="$TMP/home"
BYPASS="$HOME/.claude/writing-guard-bypass.jsonl"
mkdir -p "$CLAUDE_PLUGIN_DATA" "$HOME"

# --- payload builders -------------------------------------------------------
# python3 does the JSON quoting: commit messages carry quotes and newlines that
# printf would mangle, and a mangled payload tests nothing the harness would
# ever send.
# The 2>/dev/null on each builder is for the cases where the gate exits before
# reading stdin (the kill switch): the builder then takes a broken pipe, which
# is correct behaviour and not a test result.
artifact_payload() { # file_path [action]
  python3 -c 'import json,sys
ti={"file_path":sys.argv[1]}
if len(sys.argv)>2 and sys.argv[2]: ti["action"]=sys.argv[2]
print(json.dumps({"tool_name":"Artifact","tool_input":ti,"cwd":sys.argv[3],
                  "hook_event_name":"PreToolUse"}))' "$1" "${2:-}" "$TMP" 2>/dev/null
}
bash_payload() { # command
  python3 -c 'import json,sys
print(json.dumps({"tool_name":"Bash","tool_input":{"command":sys.argv[1]},
                  "cwd":sys.argv[2],"hook_event_name":"PreToolUse"}))' "$1" "$TMP" 2>/dev/null
}
other_payload() {
  printf '{"tool_name":"Write","tool_input":{"file_path":"/tmp/x"},"hook_event_name":"PreToolUse"}'
}

# --- assertions -------------------------------------------------------------
pass() { echo "PASS: $1"; }
fail() { echo "FAIL: $1"; shift; for l in "$@"; do echo "  $l"; done; fails=$((fails+1)); }

assert_silent() { # name output
  [ -z "$2" ] && pass "$1" || fail "$1" "expected no output" "got: <$2>"
}
assert_contains() { # name needle haystack
  case "$3" in *"$2"*) pass "$1" ;; *) fail "$1" "want substring: <$2>" "got: <$3>" ;; esac
}
assert_missing() { # name needle haystack
  case "$3" in *"$2"*) fail "$1" "must not contain: <$2>" "got: <$3>" ;; *) pass "$1" ;; esac
}
assert_denied() { # name output
  assert_contains "$1" '"permissionDecision": "deny"' "$2"
}

# The gate blocks a text twice and then stands aside, so every case that has to
# see a first attempt starts from an empty attempt store. Section 5 is where
# the counting itself is under test.
reset_state() { rm -rf "$CLAUDE_PLUGIN_DATA" "$HOME/.claude"; mkdir -p "$CLAUDE_PLUGIN_DATA"; }

# The no-leak rule has two halves. An explanation may teach the principle, but
# it may never hand back the failing words, and it may never point at where they
# are: either one lets a writer comply lexically without understanding.
assert_no_span_quotes() { # name input_file message
  local hit
  hit="$(python3 -c '
import json, re, sys
text = open(sys.argv[1], encoding="utf-8").read()
msg = " ".join(json.dumps(sys.argv[2]).split()).lower()
words = re.findall(r"[A-Za-z0-9_/.-]+", text)
for i in range(len(words) - 5):
    shingle = " ".join(words[i:i+6]).lower()
    if shingle in msg:
        print(shingle); break
' "$2" "$3")"
  [ -z "$hit" ] && pass "$1" || fail "$1" "message quotes six words of the input: <$hit>"
}
assert_no_locations() { # name message
  local hit
  hit="$(python3 -c '
import re, sys
m = re.search(r"(?i)\b(line|lines|sentence|paragraph|heading|word|column|char|character|position|offset)\s*#?\s*\d",
              sys.argv[1])
print(m.group(0) if m else "")
' "$2")"
  [ -z "$hit" ] && pass "$1" || fail "$1" "message locates the span: <$hit>"
}

# --- fixtures ---------------------------------------------------------------
# Synthetic, not corpus texts: a fixture that trips the guard has to be readable
# inside the test, and the user's own rejected prose is not this repository's to
# carry. Each fixture states which mechanism it is built to trip.
VIOLATING_MD="$TMP/violating.md"
cat > "$VIOLATING_MD" <<'EOF'
# The rollout still stalled on retry, not on startup

Escalation logic for the queued handlers themselves: the fallback reads the
region before the normalization runs.
EOF
# Trips, in the title: a definite phrase naming something the text never
# introduced, and the "[X], not [Y]" contrast. Trips, in the first sentence: an
# abstract framing phrase closed by a colon ahead of the point.

VIOLATING_HTML="$TMP/violating.html"
cat > "$VIOLATING_HTML" <<'EOF'
<title>The rollout still stalled on retry, not on startup</title>
<h1>The rollout still stalled on retry, not on startup</h1>
<p>Escalation logic for the queued handlers themselves: the fallback reads the
region before the normalization runs.</p>
EOF

CLEAN_MD="$TMP/clean.md"
cat > "$CLEAN_MD" <<'EOF'
# Token counter for a selected region

I added a command called `tmrts/count-tokens`. It sends a selected region to
Anthropic's count_tokens endpoint and prints how many tokens came back. It
answered in 180 ms on a 2,400-word draft.

Next: measure how often a commit message crosses 250 tokens.
EOF

VIOLATING_COMMIT='fix[emacs][ai]: the region counter is a guard on inputs, not a report on outputs

[PROBLEM]
The fallback reads the region before the normalization runs.'
CLEAN_COMMIT='feat[emacs][ai]: count tokens in a selected region

[PROBLEM]
Nobody could tell how many tokens a draft would cost before sending it.'

# ===========================================================================
# 1. The gate is silent everywhere it does not apply
# ===========================================================================
out="$(other_payload | "$GATE" 2>&1)"
assert_silent "a tool that is neither Artifact nor Bash is silent" "$out"

out="$(bash_payload 'ls -la' | "$GATE" 2>&1)"
assert_silent "a Bash command that is not a commit is silent" "$out"

out="$(artifact_payload "$VIOLATING_MD" list | "$GATE" 2>&1)"
assert_silent "an Artifact action other than publish is silent" "$out"

out="$(artifact_payload "$TMP/does-not-exist.md" | "$GATE" 2>&1)"
assert_silent "an unreadable Artifact file is silent" "$out"

out="$(bash_payload 'git commit -m "$(build_message)"' | "$GATE" 2>&1)"
assert_silent "a commit message the gate cannot extract is silent" "$out"

out="$(bash_payload 'git commit --amend --no-edit' | "$GATE" 2>&1)"
assert_silent "a commit that carries no message is silent" "$out"

out="$(artifact_payload "$VIOLATING_MD" | HARNESS_WRITING_GUARD_DISABLE=1 "$GATE" 2>&1)"
assert_silent "the kill switch silences the gate" "$out"

# ===========================================================================
# 2. A broken gate says so instead of passing silently
# ===========================================================================
out="$(printf 'not json at all' | "$GATE" 2>&1)"; rc=$?
assert_contains "an internal error emits the fail-open marker" "WRITING-GUARD-FAIL-OPEN" "$out"
[ "$rc" -eq 0 ] && pass "a fail-open exits 0" || fail "a fail-open exits 0" "exit was $rc"

out="$(printf 'not json at all' | "$GATE" 2>/dev/null)"
assert_silent "a fail-open decides nothing on stdout" "$out"

# ===========================================================================
# 3. Artifact publish: violating prose is denied, accepted prose is not
# ===========================================================================
reset_state
out="$(artifact_payload "$VIOLATING_MD" publish | "$GATE" 2>/dev/null)"
assert_denied "a violating Artifact publish is denied" "$out"
assert_contains "the denial names the writing skill by path" \
  "plugins/harness/skills/writing-guard/SKILL.md" "$out"
assert_no_span_quotes "the denial quotes no span of the file" "$VIOLATING_MD" "$out"
assert_no_locations "the denial does not locate the span" "$out"

reset_state
out="$(artifact_payload "$VIOLATING_HTML" publish | "$GATE" 2>/dev/null)"
assert_denied "a violating HTML Artifact publish is denied" "$out"

out="$(artifact_payload "$CLEAN_MD" publish | "$GATE" 2>&1)"
assert_silent "a clean Artifact publish is silent" "$out"

out="$(artifact_payload "$CLEAN_MD" | "$GATE" 2>&1)"
assert_silent "a clean Artifact publish with no action field is silent" "$out"

# ===========================================================================
# 4. Commit messages: the same judgment on the other surface
# ===========================================================================
reset_state
out="$(bash_payload "git commit -m '$VIOLATING_COMMIT'" | "$GATE" 2>/dev/null)"
assert_denied "a violating commit message is denied" "$out"
printf '%s' "$VIOLATING_COMMIT" > "$TMP/violating-commit.txt"
assert_no_span_quotes "the commit denial quotes no span of the message" \
  "$TMP/violating-commit.txt" "$out"

out="$(bash_payload "git commit -m '$CLEAN_COMMIT'" | "$GATE" 2>&1)"
assert_silent "a clean commit message is silent" "$out"

reset_state
out="$(bash_payload "git add -A && git commit -m '$VIOLATING_COMMIT'" | "$GATE" 2>/dev/null)"
assert_denied "a commit inside a command chain is denied" "$out"

reset_state
printf '%s' "$VIOLATING_COMMIT" > "$TMP/msg.txt"
out="$(bash_payload "git commit -F $TMP/msg.txt" | "$GATE" 2>/dev/null)"
assert_denied "a commit message passed by file is denied" "$out"

# ===========================================================================
# 5. Two blocks, then the writer gets through and the bypass is recorded
# ===========================================================================
reset_state
one="$(artifact_payload "$VIOLATING_MD" publish | "$GATE" 2>/dev/null)"
two="$(artifact_payload "$VIOLATING_MD" publish | "$GATE" 2>/dev/null)"
three="$(artifact_payload "$VIOLATING_MD" publish | "$GATE" 2>/dev/null)"
assert_denied "attempt 1 on the same text is denied" "$one"
assert_denied "attempt 2 on the same text is denied" "$two"
assert_missing "attempt 3 on the same text is not denied" '"permissionDecision"' "$three"
assert_contains "attempt 3 carries an advisory for the user" "writing guard" "$three"
assert_no_span_quotes "the advisory quotes no span of the file" "$VIOLATING_MD" "$three"
[ -s "$BYPASS" ] && pass "attempt 3 appends to the bypass log" \
  || fail "attempt 3 appends to the bypass log" "no entry at $BYPASS"
python3 -c '
import json, sys
e = json.loads(open(sys.argv[1], encoding="utf-8").readlines()[-1])
missing = [k for k in ("timestamp", "tool", "hash", "verdicts", "text") if k not in e]
assert not missing, "missing fields: %s" % missing
assert "rollout" in e["text"], "the bypassed text was not recorded"
assert e["verdicts"], "no verdicts recorded"
' "$BYPASS" 2>/dev/null \
  && pass "the bypass entry carries timestamp, tool, hash, verdicts and the text" \
  || fail "the bypass entry carries timestamp, tool, hash, verdicts and the text"

# A near-identical retry belongs to the same attempt chain. An author who
# reworded one phrase has not started a new subject, and counting that as a new
# text would hand out blocks without end.
reset_state
EDITED_MD="$TMP/violating-edited.md"
sed 's/queued handlers/queued workers/' "$VIOLATING_MD" > "$EDITED_MD"
artifact_payload "$VIOLATING_MD" publish | "$GATE" >/dev/null 2>&1
artifact_payload "$EDITED_MD" publish | "$GATE" >/dev/null 2>&1
three="$(artifact_payload "$VIOLATING_MD" publish | "$GATE" 2>/dev/null)"
assert_missing "a lightly edited retry counts against the same chain" \
  '"permissionDecision"' "$three"

# An unrelated text starts its own chain rather than inheriting the count.
reset_state
OTHER_MD="$TMP/other-violating.md"
cat > "$OTHER_MD" <<'EOF'
# The migration still hung on shutdown, not on boot

Retention semantics for the archived buckets themselves: the collector drops
the manifest before the compaction finishes.
EOF
artifact_payload "$VIOLATING_MD" publish | "$GATE" >/dev/null 2>&1
artifact_payload "$VIOLATING_MD" publish | "$GATE" >/dev/null 2>&1
out="$(artifact_payload "$OTHER_MD" publish | "$GATE" 2>/dev/null)"
assert_denied "a different text starts its own attempt chain" "$out"

# ===========================================================================
# 6. The false-positive floor: every text the user accepted still gets through
# ===========================================================================
reset_state
python3 -c '
import json, os, sys
corpus = json.load(open(sys.argv[1], encoding="utf-8"))
out = sys.argv[2]
for i, item in enumerate(corpus["okay_set_trusted"]):
    # A commit-genre text is judged on the commit surface, a document on the
    # Artifact surface: the guard reads a title differently on each.
    surface = "commit" if item["mono_title"] else "artifact"
    p = os.path.join(out, "okay-%d.%s" % (i, "txt" if surface == "commit" else "md"))
    open(p, "w", encoding="utf-8").write(item["text"])
    print("%s\t%s\t%s" % (item["id"], surface, p))
' "$CORPUS" "$TMP" > "$TMP/okayset.tsv"
while IFS="$(printf '\t')" read -r id surface path; do
  if [ "$surface" = commit ]; then
    out="$(bash_payload "git commit -F $path" | "$GATE" 2>&1)"
  else
    out="$(artifact_payload "$path" publish | "$GATE" 2>&1)"
  fi
  assert_silent "accepted text $id is not blocked" "$out"
done < "$TMP/okayset.tsv"

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
