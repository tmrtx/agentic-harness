#!/usr/bin/env bash
# Commit-shape gate: static-class oracle for the commit protocol's [ORACLE]
# section and Oracle trailer. PostToolUse feedback, never a block; fails open
# on every internal error. Kill switch: HARNESS_COMMIT_SHAPE_GATE_DISABLE.
# The hook payload arrives on stdin and must flow through to the python
# process untouched, so the logic lives in the sibling .py file - a heredoc
# here would displace the payload as python's stdin.
[ -n "$HARNESS_COMMIT_SHAPE_GATE_DISABLE" ] && exit 0
command -v python3 >/dev/null 2>&1 || exit 0
exec python3 "$(dirname "$0")/commit-shape-gate.py"
