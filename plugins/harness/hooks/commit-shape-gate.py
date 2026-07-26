import json, os, re, subprocess, sys, time

try:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (payload.get("tool_input") or {}).get("command", "")
    if not re.search(r"\bgit\b[^|;&]*\bcommit\b", cmd):
        sys.exit(0)
    cwd = payload.get("cwd") or os.getcwd()

    def git(*args):
        return subprocess.run(["git", "-C", cwd, *args],
                              capture_output=True, text=True, timeout=10)

    head = git("log", "-1", "--format=%H|%ct")
    if head.returncode != 0 or "|" not in head.stdout:
        sys.exit(0)
    sha, ct = head.stdout.strip().split("|", 1)
    if abs(time.time() - int(ct)) > 300:
        sys.exit(0)  # HEAD predates this command; grandfathered history is not this gate's subject

    body = git("log", "-1", "--format=%B").stdout
    problems = []
    if not (re.search(r"^\[ORACLE\]\s*$", body, re.M)
            and re.search(r"^Oracle: \[[^|\]\s]+\|[^|\]\s]+\]\s*$", body, re.M)):
        problems.append("the [ORACLE] section and the "
                        "Oracle: [<oracle-class>|<ground-truth>] trailer are "
                        "required per the oracle-ladder skill")
    if not problems:
        sys.exit(0)

    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PostToolUse",
        "additionalContext": "Commit " + sha[:7] + ": " + "; also, ".join(problems)
        + ". `git commit --amend` adds them."}}))
    sys.exit(0)
except SystemExit:
    raise
except Exception:
    sys.exit(0)
