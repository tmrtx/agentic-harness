#!/usr/bin/env bash
# Tests for the merge skill's stack classifier. Each case runs the CLI over a
# fixture repo with the judge stubbed via HARNESS_STACK_PROVENANCE_CLASSIFIER,
# so no case depends on network, auth, or a live model. Exit code is the
# number of failing cases.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$REPO/plugins/harness/skills/merge/scripts/classify_stack.py"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fails=0

MARKS="$TMP/judge-calls"
STUB="$TMP/stub.sh"
cat > "$STUB" <<'EOS'
#!/bin/sh
input=$(cat)
echo call >> "$MARKS_FILE"
[ "${STUB_EXIT:-0}" != 0 ] && exit "$STUB_EXIT"
v="${STUB_VERDICT:-keep}"
if [ -n "${STUB_FOLD_MATCH:-}" ] && printf '%s' "$input" | grep -q "$STUB_FOLD_MATCH"; then v=fold; fi
printf '{"verdict":"%s","reason":"stub reason"}' "$v"
EOS
chmod +x "$STUB"
export HARNESS_STACK_PROVENANCE_CLASSIFIER="MARKS_FILE=$MARKS $STUB"

run() { python3 "$CLI" --repo "$WORK" "$@" 2>"$TMP/err"; }
calls() { [ -f "$MARKS" ] && wc -l < "$MARKS" | tr -d ' ' || echo 0; }
check() { # name want got
  case "$3" in *"$2"*) echo "PASS: $1" ;; *) echo "FAIL: $1"; echo "  want <$2>"; echo "  got  <$3>"; fails=$((fails+1)) ;; esac
}
check_eq() { # name want got
  if [ "$3" = "$2" ]; then echo "PASS: $1"; else echo "FAIL: $1 (want=$2 got=$3)"; fails=$((fails+1)); fi
}

WORK="$TMP/work"; ORIGIN="$TMP/origin"
git init -q --bare "$ORIGIN"
git init -q "$WORK"
G() { git -C "$WORK" -c user.email=t@t -c user.name=t "$@"; }
G remote add origin "$ORIGIN"
G commit -q --allow-empty -m "base: initial state"
G push -q origin HEAD:main
G fetch -q origin
G remote set-head origin main
G checkout -q -b claude/test
G commit -q --allow-empty -m "$(printf 'feat[x]: pre-existing problem\n\n[PROBLEM]\nOld friction.\n')"
G commit -q --allow-empty -m "$(printf 'fix[x]: repair the previous commit\n\n[PROBLEM]\nThe previous commit broke X.\n')"

# 1. one JSON row per commit, oldest first, judge called once per commit
out="$(run)"; rc=$?
check_eq "clean exit" 0 "$rc"
check_eq "one row per commit" 2 "$(printf '%s\n' "$out" | wc -l | tr -d ' ')"
check "rows are verdict JSON" '"verdict": "keep"' "$out"
first_subj="$(printf '%s\n' "$out" | head -1 | python3 -c 'import json,sys; print(json.load(sys.stdin)["subject"])')"
check "oldest commit first" "feat[x]: pre-existing problem" "$first_subj"
check_eq "judge called per commit" 2 "$(calls)"

# 2. selective fold verdicts carry the judge's reason
out="$(STUB_FOLD_MATCH='previous commit broke' run)"
folds="$(printf '%s\n' "$out" | grep -c '"verdict": "fold"')"
check_eq "fold verdict lands on the journey commit" 1 "$folds"
check "fold row carries reason" "stub reason" "$out"

# 3. fixup! machinery folds deterministically, no judge call
G commit -q --allow-empty -m "fixup! feat[x]: pre-existing problem"
n_before="$(calls)"
out="$(run)"
check "fixup row is fold" '"reason": "fixup!/squash!/amend! machinery' "$out"
check_eq "fixup spends no judge call" "$((n_before + 2))" "$(calls)"
G reset -q --hard HEAD~1

# 4. merge commits are never judged
G checkout -q -b side origin/main
G commit -q --allow-empty -m "$(printf 'feat[z]: side work\n\n[PROBLEM]\nOld need.\n')"
G checkout -q claude/test
G merge -q --no-ff -m "merge side" side
out="$(STUB_FOLD_MATCH='merge side' run)"
check_eq "merge commit yields no row and no fold" 0 "$(printf '%s\n' "$out" | grep -c '"verdict": "fold"')"

# 5. judge failure yields null verdict with a reason, exit stays 0
out="$(STUB_EXIT=3 run)"; rc=$?
check_eq "judge failure exits 0" 0 "$rc"
check "failed rows are null verdicts" '"verdict": null' "$out"

# 6. --base overrides resolution
out="$(run --base origin/main)"; rc=$?
check_eq "explicit base accepted" 0 "$rc"

# 7. origin/main fallback when origin/HEAD is unset
git -C "$WORK" symbolic-ref -d refs/remotes/origin/HEAD
out="$(run)"; rc=$?
check_eq "origin/main fallback resolves" 0 "$rc"

# 8. no base at all: clean error on stderr, nonzero exit
LONE="$TMP/lone"; git init -q "$LONE"
git -C "$LONE" -c user.email=t@t -c user.name=t commit -q --allow-empty -m solo
python3 "$CLI" --repo "$LONE" >/dev/null 2>"$TMP/err"; rc=$?
check_eq "no-base exits nonzero" 1 "$rc"
check "no-base names the problem" "no base branch resolvable" "$(cat "$TMP/err")"

echo
echo "failures: $fails"
exit "$fails"
