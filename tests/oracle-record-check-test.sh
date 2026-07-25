#!/usr/bin/env bash
# Tests for the oracle-record checker that grades the oracle-ladder evals.
# The checker decides whether eval runs pass, so a checker that mis-grades
# turns every downstream measurement into noise without ever looking broken.
# Each case mutates one property of a known-good record and asserts that the
# checker notices exactly that property. Exit code is the number of failures.
set -u
REPO="$(cd "$(dirname "$0")/.." && pwd)"
SKILL="$REPO/plugins/harness/skills/oracle-ladder"
CHECK="$SKILL/evals/check_record.py"
REF="$SKILL/evals/reference"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT
fails=0

command -v python3 >/dev/null 2>&1 || { echo "SKIP: python3 unavailable"; exit 0; }

run() { # outputs_dir [extra args...] -> checker JSON
  local dir="$1"; shift
  python3 "$CHECK" --outputs "$dir" --baseline-ledger "$REF/baseline-oracles.jsonl" \
    --expect-class principal --expect-ground-truth principal --require-commit "$@"
}
field() { python3 -c "import json,sys; print(json.load(sys.stdin)$1)"; }
verdict() { # json substring-of-assertion -> True/False
  python3 -c "
import json,sys
d=json.load(sys.stdin)
m=[c for c in d['checks'] if '''$1''' in c['text']]
print(m[0]['passed'] if m else 'MISSING')"
}
check() { # name expected actual
  if [ "$2" = "$3" ]; then echo "PASS: $1"
  else echo "FAIL: $1"; echo "  want: <$2>"; echo "  got:  <$3>"; fails=$((fails+1)); fi
}

# 1. The reference solution passes every assertion. If this breaks, the eval
#    tasks are no longer provably solvable and nothing downstream is trustworthy.
out="$(run "$REF")"
check "reference solution passes every check" "0" "$(printf '%s' "$out" | field "['summary']['failed']")"

# 2. A commit with no Oracle trailer fails the trailer check and only it.
cp -r "$REF" "$TMP/no-trailer"
grep -v '^Oracle: \[' "$REF/commit-message.txt" > "$TMP/no-trailer/commit-message.txt"
out="$(run "$TMP/no-trailer")"
check "missing trailer is caught" "False" "$(printf '%s' "$out" | verdict "well-formed Oracle:")"
check "missing trailer does not disturb the section check" "True" \
  "$(printf '%s' "$out" | verdict "[ORACLE] section header")"

# 3. A rewritten ledger snapshot breaks the append-only invariant. The ledger
#    is the record of what was true at the time; editing history erases it.
cp -r "$REF" "$TMP/rewritten"
python3 - "$TMP/rewritten/oracles.jsonl" <<'PY'
import json, sys
p = sys.argv[1]
lines = [l for l in open(p).read().splitlines() if l.strip()]
first = json.loads(lines[0]); first["justification"] = "retconned"
lines[0] = json.dumps(first)
open(p, "w").write("\n".join(lines) + "\n")
PY
out="$(run "$TMP/rewritten")"
check "rewritten ledger history is caught" "False" "$(printf '%s' "$out" | verdict "append-only")"

# 4. A ledger line citing an unknown oracle code is caught. A dangling code
#    reads as a recorded oracle while pointing at nothing.
cp -r "$REF" "$TMP/dangling"
python3 - "$TMP/dangling/oracles.jsonl" <<'PY'
import json, sys
p = sys.argv[1]
lines = [l for l in open(p).read().splitlines() if l.strip()]
last = json.loads(lines[-1]); last["oracle"] = "ORC-999"
lines[-1] = json.dumps(last)
open(p, "w").write("\n".join(lines) + "\n")
PY
out="$(run "$TMP/dangling")"
check "ledger citing an unknown oracle code is caught" "False" \
  "$(printf '%s' "$out" | verdict "cites an oracle code that exists")"

# 5. A wrong rung is caught even when every other part of the shape is right.
#    Shape compliance is the cheap half; the placement is the point.
cp -r "$REF" "$TMP/wrong-rung"
sed 's/^Oracle: \[principal:tacit|principal\]/Oracle: [static|specified]/' \
  "$REF/commit-message.txt" > "$TMP/wrong-rung/commit-message.txt"
out="$(run "$TMP/wrong-rung")"
check "wrong rung is caught" "False" "$(printf '%s' "$out" | verdict "Oracle class is")"
check "wrong rung still parses as a well-formed trailer" "True" \
  "$(printf '%s' "$out" | verdict "well-formed Oracle:")"

# 6. An eval that declares no expected class must not invent one. Questions
#    with more than one defensible trailer are graded on consistency instead,
#    so the assertion has to be absent rather than present-and-lenient.
mkdir -p "$TMP/advice"
printf 'The check is static. For the commit:\n\nOracle: [runtime|specified]\n' \
  > "$TMP/advice/answer.md"
out="$(python3 "$CHECK" --outputs "$TMP/advice" --answer-trailer)"
check "an answer's trailer is found and accepted on shape" "True" \
  "$(printf '%s' "$out" | verdict "hands over a well-formed")"
check "no expected class means no class assertion" "MISSING" \
  "$(printf '%s' "$out" | verdict "classifies the change as")"
out="$(python3 "$CHECK" --outputs "$TMP/advice" --answer-trailer --expect-class static)"
check "a declared expected class is enforced" "False" \
  "$(printf '%s' "$out" | verdict "classifies the change as")"

echo "---"
[ "$fails" -eq 0 ] && echo "ALL PASS" || echo "$fails FAILURE(S)"
exit "$fails"
