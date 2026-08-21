#!/usr/bin/env bash
# Writing guard: PreToolUse gate on Artifact publishes and git commit messages.
# Denies prose whose opening the reader cannot follow, twice, then stands aside
# and records the bypass. Fails open on every internal error, with the marker
# line HARNESS-WRITING-GUARD-FAIL-OPEN on stderr so a broken gate is visible
# rather than silently permissive. Kill switch: HARNESS_WRITING_GUARD_DISABLE.
# The hook payload arrives on stdin and must flow through to the python process
# untouched, so the logic lives in the sibling .py file - a heredoc here would
# displace the payload as python's stdin.
[ -n "$HARNESS_WRITING_GUARD_DISABLE" ] && exit 0
if ! command -v python3 >/dev/null 2>&1; then
  echo "HARNESS-WRITING-GUARD-FAIL-OPEN: python3 not found" >&2
  exit 0
fi
exec python3 "$(dirname "$0")/writing-guard.py"
