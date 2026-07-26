import json, os, re, subprocess, sys, time

# Transient squash machinery: folded before push per the commit-protocol stack
# regulation, so its shape lives in the target commit, not in itself.
SQUASH_RE = re.compile(r"^(fixup|squash|amend)! ")
# Bound the push-range walk; a branch this far past base is not an agent stack.
MAX_SCAN = 1000


def record(event, detail):
    # Self-recording per the oracle-ladder gate norm: a broken gate looks
    # exactly like a passing one from outside. Best-effort, never raises.
    try:
        data = os.environ.get("CLAUDE_PLUGIN_DATA")
        if not data:
            return
        os.makedirs(data, exist_ok=True)
        with open(os.path.join(data, "commit-shape-gate-events.jsonl"), "a") as f:
            f.write(json.dumps({"v": 1, "ts": int(time.time()),
                                "event": event, "detail": detail}) + "\n")
    except Exception:
        pass


def commit_finding(git):
    head = git("log", "-1", "--format=%H%n%ct%n%s%n%B")
    if head.returncode != 0:
        return None
    parts = head.stdout.split("\n", 3)
    if len(parts) < 4:
        return None
    sha, ct, subject, body = parts
    # HEAD older than the command predates it; grandfathered history is not
    # this gate's subject. Squash-machinery subjects are exempt.
    if abs(time.time() - int(ct)) > 300 or SQUASH_RE.match(subject):
        return None
    if (re.search(r"^\[ORACLE\]\s*$", body, re.M)
            and re.search(r"^Oracle: \[[^|\]\s]+\|[^|\]\s]+\]\s*$", body, re.M)):
        return None
    return ("commit-shape",
            "Commit " + sha[:7] + ": the [ORACLE] section and the "
            "Oracle: [<oracle-class>|<ground-truth>] trailer are required per the "
            "oracle-ladder skill. `git commit --amend` adds them.")


def push_finding(git):
    refs = git("for-each-ref", "--format=%(refname) %(symref:short)",
               "refs/remotes/origin/HEAD", "refs/remotes/origin/main",
               "refs/remotes/origin/master")
    if refs.returncode != 0:
        return None
    seen = {}
    for line in refs.stdout.splitlines():
        name, _, sym = line.partition(" ")
        seen[name] = sym.strip()
    base = seen.get("refs/remotes/origin/HEAD", "")
    if not base and "refs/remotes/origin/main" in seen:
        base = "origin/main"
    if not base and "refs/remotes/origin/master" in seen:
        base = "origin/master"
    if not base:
        return None
    rng = git("log", "--format=%s", "--max-count=" + str(MAX_SCAN), base + "..HEAD")
    if rng.returncode != 0:
        return None
    leftover = [s for s in rng.stdout.splitlines() if SQUASH_RE.match(s)]
    if not leftover:
        return None
    return ("push-shape",
            "Pushed history carries " + str(len(leftover)) + " unsquashed "
            "fixup!/squash!/amend! commit(s). Fold them (`GIT_SEQUENCE_EDITOR=: "
            "git rebase -i --autosquash " + base + "`) and `git push "
            "--force-with-lease` - the commit-protocol stack regulation: unmerged "
            "commits represent state, never journey.")


try:
    payload = json.load(sys.stdin)
    if payload.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (payload.get("tool_input") or {}).get("command", "")
    checks = []
    if re.search(r"\bgit\b[^|;&]*\bcommit\b", cmd):
        checks.append(commit_finding)
    if re.search(r"\bgit\b[^|;&]*\bpush\b", cmd):
        checks.append(push_finding)
    if not checks:
        sys.exit(0)
    cwd = payload.get("cwd") or os.getcwd()

    def git(*args):
        return subprocess.run(["git", "-C", cwd, *args],
                              capture_output=True, text=True, timeout=10)

    findings = [f for f in (c(git) for c in checks) if f]
    if findings:
        record("fired", "+".join(k for k, _ in findings))
        print(json.dumps({"hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "additionalContext": " ".join(n for _, n in findings)}}))
    sys.exit(0)
except SystemExit:
    raise
except Exception as e:
    record("errored", type(e).__name__)
    sys.exit(0)
