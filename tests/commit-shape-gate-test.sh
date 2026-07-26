#!/usr/bin/env bash
# Tests for the commit-shape gate. Each case pipes a hook payload into the
# gate and asserts its output. Exit code is the number of failing cases.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$REPO/plugins/harness/hooks/commit-shape-gate.sh"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fails=0

payload() { printf '{"tool_name":"Bash","tool_input":{"command":"%s"},"cwd":"%s"}' "$1" "$2"; }
gcommit() { git -C "$TMP" -c user.email=t@t -c user.name=t commit -q --allow-empty -m "$1"; }
check() { # name expected_fragment actual_out
  local name="$1" want="$2" got="$3"
  case "$got" in
    *"$want"*) echo "PASS: $name" ;;
    *) echo "FAIL: $name"; echo "  want: <$want>"; echo "  got:  <$got>"; fails=$((fails+1)) ;;
  esac
}

git -C "$TMP" init -q
PYC="$REPO/plugins/harness/skills/commit-protocol/scripts/__pycache__"
PYC_PRE="$([ -d "$PYC" ] && echo 1 || echo 0)"

# 1. non-commit command: silent
out="$(payload 'ls -la' "$TMP" | "$GATE")"
check "non-commit command is silent" "" "$out"
[ -z "$out" ] || fails=$((fails+1))

# 2. grandfathered HEAD (old commit): silent
GIT_COMMITTER_DATE='2020-01-01T00:00:00' GIT_AUTHOR_DATE='2020-01-01T00:00:00' gcommit "old commit, no shape"
out="$(payload 'git commit -m x' "$TMP" | "$GATE")"
[ -z "$out" ] && echo "PASS: grandfathered HEAD is silent" || { echo "FAIL: grandfathered HEAD produced output: $out"; fails=$((fails+1)); }

# 3. fresh commit without shape: feedback names the requirement
gcommit "bad commit, no shape"
out="$(payload 'git commit -m bad' "$TMP" | "$GATE")"
check "missing shape yields feedback" "required per the oracle-ladder skill" "$out"

# 4. fresh compliant commit: silent
gcommit "$(printf 'good[x]: proper commit\n\n[ORACLE]\nmechanism and justification.\n\nOracle: [principal:tacit|principal]')"
out="$(payload 'git commit -m good' "$TMP" | "$GATE")"
[ -z "$out" ] && echo "PASS: compliant commit is silent" || { echo "FAIL: compliant commit produced output: $out"; fails=$((fails+1)); }

# 5. kill switch: silent even on violation
gcommit "bad again"
out="$(payload 'git commit -m bad' "$TMP" | HARNESS_COMMIT_SHAPE_GATE_DISABLE=1 "$GATE")"
[ -z "$out" ] && echo "PASS: kill switch silences the gate" || { echo "FAIL: kill switch ignored: $out"; fails=$((fails+1)); }

# Steering-text cases: commits that change agent/model-steering files must
# carry the [CHANGE] section's `Token diff:` line.
fcommit() { # path content message
  mkdir -p "$TMP/$(dirname "$1")"
  printf '%s' "$2" > "$TMP/$1"
  git -C "$TMP" add "$1"
  git -C "$TMP" -c user.email=t@t -c user.name=t commit -q -m "$3"
}
SHAPE="$(printf 'x[y]: t\n\n[ORACLE]\nm.\n\nOracle: [static|specified]')"

# 6. skill edit with commit shape but no token line: feedback names the line
fcommit "plugins/harness/skills/foo/SKILL.md" "steer" "$SHAPE"
out="$(payload 'git commit -m skill' "$TMP" | "$GATE")"
check "steering commit without token line yields feedback" "Token diff" "$out"

# 7. CLAUDE.md edit without token line: feedback names the line
fcommit "CLAUDE.md" "steer more" "$SHAPE"
out="$(payload 'git commit -m claudemd' "$TMP" | "$GATE")"
check "CLAUDE.md commit without token line yields feedback" "Token diff" "$out"

# 8. steering commit carrying a measured token line: silent
fcommit "plugins/harness/skills/foo/SKILL.md" "steer v2" \
  "$(printf 'x[y]: t\n\nToken diff: +12/-3 (net +9, claude-opus-5)\n\n[ORACLE]\nm.\n\nOracle: [static|specified]')"
out="$(payload 'git commit -m measured' "$TMP" | "$GATE")"
[ -z "$out" ] && echo "PASS: measured steering commit is silent" || { echo "FAIL: measured steering commit produced output: $out"; fails=$((fails+1)); }

# 9. steering commit recording counting as unavailable: silent
fcommit "agents/reviewer.md" "steer agent" \
  "$(printf 'x[y]: t\n\nToken diff: unavailable (no credentials)\n\n[ORACLE]\nm.\n\nOracle: [static|specified]')"
out="$(payload 'git commit -m unavail' "$TMP" | "$GATE")"
[ -z "$out" ] && echo "PASS: unavailable-token steering commit is silent" || { echo "FAIL: unavailable-token steering commit produced output: $out"; fails=$((fails+1)); }

# 10. non-steering commit without token line: silent
fcommit "src/app.py" "print('hi')" "$SHAPE"
out="$(payload 'git commit -m code' "$TMP" | "$GATE")"
[ -z "$out" ] && echo "PASS: non-steering commit needs no token line" || { echo "FAIL: non-steering commit produced output: $out"; fails=$((fails+1)); }

# 11. shapeless steering commit: both findings arrive in one message
fcommit "commands/do.md" "steer command" "no shape at all"
out="$(payload 'git commit -m both' "$TMP" | "$GATE")"
check "shapeless steering commit names the shape" "required per the oracle-ladder skill" "$out"
check "shapeless steering commit also names the token line" "Token diff" "$out"

# 12. the gate leaves no bytecode behind in the plugin tree
PYC_POST="$([ -d "$PYC" ] && echo 1 || echo 0)"
[ "$PYC_POST" = "$PYC_PRE" ] && echo "PASS: gate writes no bytecode into the plugin tree" || { echo "FAIL: gate created $PYC"; fails=$((fails+1)); }

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
