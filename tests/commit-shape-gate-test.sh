#!/usr/bin/env bash
# Tests for the commit-shape gate. Each case pipes a hook payload into the
# gate and asserts its output. Exit code is the number of failing cases.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
GATE="$REPO/plugins/harness/hooks/commit-shape-gate.sh"
TMP="$(mktemp -d)"
TMP2="$(mktemp -d)"
DATA="$(mktemp -d)"
trap 'rm -rf "$TMP" "$TMP2" "$DATA"' EXIT
fails=0
export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t

payload() { printf '{"tool_name":"Bash","tool_input":{"command":"%s"},"cwd":"%s"}' "$1" "$2"; }
gcommit() { git -C "$TMP" commit -q --allow-empty -m "$1"; }
check() { # name expected_fragment actual_out
  local name="$1" want="$2" got="$3"
  case "$got" in
    *"$want"*) echo "PASS: $name" ;;
    *) echo "FAIL: $name"; echo "  want: <$want>"; echo "  got:  <$got>"; fails=$((fails+1)) ;;
  esac
}
expect_silent() { # name actual_out
  local name="$1" got="$2"
  if [ -z "$got" ]; then echo "PASS: $name"
  else echo "FAIL: $name"; echo "  want: silence"; echo "  got:  <$got>"; fails=$((fails+1)); fi
}
expect_event() { # name expected_fragment (over the recorded event stream)
  check "$1" "$2" "$(cat "$DATA/commit-shape-gate-events.jsonl" 2>/dev/null)"
}

git -C "$TMP" init -q

# 1. non-commit command: silent
out="$(payload 'ls -la' "$TMP" | "$GATE")"
expect_silent "non-commit command is silent" "$out"

# 2. grandfathered HEAD (old commit): silent
GIT_COMMITTER_DATE='2020-01-01T00:00:00' GIT_AUTHOR_DATE='2020-01-01T00:00:00' gcommit "old commit, no shape"
out="$(payload 'git commit -m x' "$TMP" | "$GATE")"
expect_silent "grandfathered HEAD is silent" "$out"

# 3. fresh commit without shape: feedback names the requirement
gcommit "bad commit, no shape"
out="$(payload 'git commit -m bad' "$TMP" | "$GATE")"
check "missing shape yields feedback" "required per the oracle-ladder skill" "$out"

# 4. fresh compliant commit: silent
gcommit "$(printf 'good[x]: proper commit\n\n[ORACLE]\nmechanism and justification.\n\nOracle: [principal:tacit|principal]')"
out="$(payload 'git commit -m good' "$TMP" | "$GATE")"
expect_silent "compliant commit is silent" "$out"

# 5. kill switch: silent even on violation
gcommit "bad again"
out="$(payload 'git commit -m bad' "$TMP" | HARNESS_COMMIT_SHAPE_GATE_DISABLE=1 "$GATE")"
expect_silent "kill switch silences the gate" "$out"

# 6. fixup!/squash!/amend! subjects are exempt at commit time
git -C "$TMP" commit -q --allow-empty --fixup=HEAD
out="$(payload 'git commit --fixup=HEAD' "$TMP" | "$GATE")"
expect_silent "fixup commit is silent" "$out"
git -C "$TMP" commit -q --allow-empty --squash=HEAD~1
out="$(payload 'git commit --squash=HEAD~1' "$TMP" | "$GATE")"
expect_silent "squash commit is silent" "$out"
gcommit "amend! bad again"
out="$(payload 'git commit -m amend' "$TMP" | "$GATE")"
expect_silent "amend commit is silent" "$out"

# 7-11. push-time stack shape, in a fresh repo with a simulated origin
git -C "$TMP2" init -q -b main
echo a >"$TMP2/a" && git -C "$TMP2" add a && git -C "$TMP2" commit -q -m "base"
echo b >"$TMP2/b" && git -C "$TMP2" add b && git -C "$TMP2" commit -q -m "feat[x]: logical change"

# 7. push with no origin refs resolvable: silent (fail open)
out="$(payload 'git push -u origin main' "$TMP2" | "$GATE")"
expect_silent "push without origin refs is silent" "$out"

git -C "$TMP2" update-ref refs/remotes/origin/main "$(git -C "$TMP2" rev-parse HEAD~1)"
git -C "$TMP2" symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main

# 8. clean outgoing range: silent
out="$(payload 'git push origin main' "$TMP2" | "$GATE")"
expect_silent "clean outgoing range is silent" "$out"

# 9. unsquashed fixup in the outgoing range: feedback names the fold recipe
echo b2 >"$TMP2/b" && git -C "$TMP2" add b && git -C "$TMP2" commit -q --fixup=HEAD
out="$(payload 'git push --force-with-lease' "$TMP2" | "$GATE")"
check "unsquashed fixup at push yields feedback" "--autosquash" "$out"

# 10. the documented fold recipe empties the range's fixups: silent again
GIT_SEQUENCE_EDITOR=: git -C "$TMP2" rebase -i --autosquash origin/main >/dev/null 2>&1
out="$(payload 'git push --force-with-lease' "$TMP2" | "$GATE")"
expect_silent "folded stack push is silent" "$out"

# 11. the other exempt prefixes are detected at push too, and the feedback
# names their case
git -C "$TMP2" commit -q --allow-empty -m "amend! feat[x]: logical change"
out="$(payload 'git push --force-with-lease' "$TMP2" | "$GATE")"
check "amend leftover at push yields feedback naming its case" "amend!" "$out"

# 12. base fallback when origin/HEAD is not set: origin/main, then (after the
# main ref is gone) origin/master — one repo, refs swapped between phases
T="$(mktemp -d)"
git -C "$T" init -q -b work
git -C "$T" commit -q --allow-empty -m "base"
git -C "$T" update-ref refs/remotes/origin/main HEAD
git -C "$T" commit -q --allow-empty -m "feat[y]: change"
git -C "$T" commit -q --allow-empty --fixup=HEAD
out="$(payload 'git push' "$T" | "$GATE")"
check "origin/main fallback resolves the outgoing range" "origin/main" "$out"
git -C "$T" update-ref refs/remotes/origin/master refs/remotes/origin/main
git -C "$T" update-ref -d refs/remotes/origin/main
out="$(payload 'git push' "$T" | "$GATE")"
check "origin/master fallback resolves the outgoing range" "origin/master" "$out"
rm -rf "$T"

# 13. partial shape ([ORACLE] section without the trailer): feedback
gcommit "$(printf 'part[x]: section without trailer\n\n[ORACLE]\nmechanism only.')"
out="$(payload 'git commit -m part' "$TMP" | "$GATE")"
check "section without trailer yields feedback" "required per the oracle-ladder skill" "$out"

# 14. a fired gate emits its feedback and self-records one event line under
# CLAUDE_PLUGIN_DATA
out="$(payload 'git commit -m part' "$TMP" | CLAUDE_PLUGIN_DATA="$DATA" "$GATE")"
check "fired gate still yields feedback with recording on" "required per the oracle-ladder skill" "$out"
expect_event "fired gate self-records" '"fired"'

# 15. an internally erroring gate stays silent, exits 0, and self-records
out="$(printf 'not json' | CLAUDE_PLUGIN_DATA="$DATA" "$GATE")"; rc=$?
expect_silent "erroring gate is silent" "$out"
if [ "$rc" -eq 0 ]; then echo "PASS: erroring gate exits 0"
else echo "FAIL: erroring gate exited $rc"; fails=$((fails+1)); fi
expect_event "erroring gate self-records" '"errored"'

# 16. combined `git commit && git push` in one call: both detectors join into
# one feedback and one recorded event, and events carry the v1 schema tag
git -C "$TMP2" commit -q --allow-empty --fixup=HEAD
git -C "$TMP2" commit -q --allow-empty -m "plain[x]: unshaped fresh commit"
out="$(payload 'git commit -m plain && git push' "$TMP2" | CLAUDE_PLUGIN_DATA="$DATA" "$GATE")"
check "combined call carries the commit feedback" "required per the oracle-ladder skill" "$out"
check "combined call carries the push feedback too" "--autosquash" "$out"
expect_event "combined event records both kinds" '"commit-shape+push-shape"'
expect_event "events carry the v1 schema tag" '"v": 1'

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
