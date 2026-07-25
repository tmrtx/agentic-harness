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

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
