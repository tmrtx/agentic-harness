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
# Redirect any bytecode writes to a fresh directory, so the no-bytecode case
# below is decidable regardless of what a past run left in the repo tree.
export PYTHONPYCACHEPREFIX="$TMP/pyc"

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
#    and the invocation that measures a commit already made
fcommit "plugins/harness/skills/foo/SKILL.md" "steer" "$SHAPE"
out="$(payload 'git commit -m skill' "$TMP" | "$GATE")"
check "steering commit without token line yields feedback" "Token diff" "$out"
check "feedback names the post-commit invocation" "--base HEAD^ --target HEAD" "$out"

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

# 12. the gate compiles no token_diff bytecode to disk. All gate runs above
# imported token_diff, and the redirect captures any cache write it makes
# (interpreter startup caches its own stdlib modules there too, so the
# assertion targets the module, not the directory).
if find "$TMP/pyc" -name 'token_diff*' 2>/dev/null | grep -q .; then
  echo "FAIL: gate wrote token_diff bytecode under $TMP/pyc"; fails=$((fails+1))
else
  echo "PASS: gate writes no token_diff bytecode"
fi

# 13. pattern import failure fails open: hooks copied without the sibling
# skills tree still deliver the shape finding, and only skip the token check
mkdir -p "$TMP/lonehooks"
cp -R "$REPO/plugins/harness/hooks/." "$TMP/lonehooks/"
out="$(payload 'git commit -m both' "$TMP" | "$TMP/lonehooks/commit-shape-gate.sh")"
check "lone gate still names the shape" "required per the oracle-ladder skill" "$out"
case "$out" in *"Token diff"*) echo "FAIL: lone gate claimed the token check: $out"; fails=$((fails+1)) ;; *) echo "PASS: lone gate skips only the token check" ;; esac

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
