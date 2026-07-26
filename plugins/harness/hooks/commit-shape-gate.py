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
    # Steering-text commits must carry the [CHANGE] section's `Token diff:`
    # line. The steering-path pattern's single home is the token-diff script;
    # if it cannot be loaded, only this check is skipped - the gate fails open.
    try:
        import importlib.util
        script = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..",
                              "skills", "commit-protocol", "scripts", "token_diff.py")
        spec = importlib.util.spec_from_file_location("token_diff", script)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        files = git("log", "-1", "--format=", "--name-only").stdout.splitlines()
        steering = next((f for f in files if re.search(module.STEERING_RE, f)), None)
        if steering and not re.search(r"^Token diff: ", body, re.M):
            problems.append("it changes steering text (" + steering + ") without "
                            "the `Token diff:` line the commit-protocol skill "
                            "requires in [CHANGE]; compute it with that skill's "
                            "scripts/token_diff.py or record "
                            "`Token diff: unavailable (<reason>)`")
    except Exception:
        pass

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
