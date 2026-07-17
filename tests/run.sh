#!/bin/sh
# Run every test suite. The pre-push release gate in CLAUDE.md invokes this,
# so a suite that is not green cannot ship to consumers.
set -u
status=0
for t in "$(dirname "$0")"/*.test.sh; do
  echo "== $t"
  sh "$t" || status=1
done
exit $status
