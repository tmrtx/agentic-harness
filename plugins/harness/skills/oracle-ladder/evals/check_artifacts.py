#!/usr/bin/env python3
"""Code grader for the capability tier's build-shaped points (C1, C4, C5).

Grades behavior, not text: it copies the run's finished sandbox, stages
planted violation / compliant scenarios, drives whatever enforcement artifact
the submission built, and reads exit codes. Any architecture can pass — the
checker discovers entry points from (a) the demo command answer.md was asked
to include, (b) the pre-commit hook, (c) new or modified executable scripts.
When it cannot drive anything it says so (`entry_point: none`) and the
affected points fail with that evidence; the judge may override with recorded
evidence if the outputs demonstrate a working equivalent (see KEY.md).

Emits JSON: {"checks": [{"id", "passed", "evidence"}, ...]} — ids match
evals.json / KEY.md. Exit 0 whenever the checker ran; verdicts are data.

Usage:
    python3 check_artifacts.py --case C1 --sandbox <run sandbox> --answer <answer.md>
"""
import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

GIT_ENV = ["-c", "user.name=grader", "-c", "user.email=grader@local"]


def sh(cwd, cmd, timeout=60):
    try:
        res = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True,
                             timeout=timeout, shell=isinstance(cmd, str))
        return res.returncode, (res.stdout + res.stderr)
    except subprocess.TimeoutExpired:
        return 124, "<timeout>"
    except Exception as exc:  # noqa: BLE001 - checker must never crash on a run
        return 125, f"<checker error: {exc}>"


def fresh_copy(sandbox: Path) -> Path:
    dest = Path(tempfile.mkdtemp(prefix="grade-")) / "repo"
    shutil.copytree(sandbox, dest, symlinks=True)
    # settle any outstanding work so synthetic staging is the only diff
    sh(dest, ["git", *GIT_ENV, "add", "-A"])
    sh(dest, ["git", *GIT_ENV, "-c", "core.hooksPath=/dev/null",
              "commit", "-q", "--allow-empty", "-m", "wip"])
    return dest


def reset(repo: Path):
    sh(repo, ["git", "reset", "-q", "--hard", "HEAD"])
    sh(repo, ["git", "clean", "-qfd"])


def stage(repo: Path, edits: dict[str, str]):
    """Append content to files (creating them if needed) and stage everything."""
    for rel, addition in edits.items():
        path = repo / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a") as fh:
            fh.write(addition)
    sh(repo, ["git", *GIT_ENV, "add", "-A"])


def demo_commands(answer: str) -> list[str]:
    """Pull plausible single-line commands out of answer.md."""
    cands = []
    for block in re.findall(r"```[a-z]*\n(.*?)```", answer, re.S):
        lines = [l.strip() for l in block.strip().splitlines() if l.strip()]
        if len(lines) == 1:
            cands.append(lines[0].lstrip("$ ").strip())
    for line in answer.splitlines():
        line = line.strip()
        if line.startswith("$ "):
            cands.append(line[2:].strip())
    runnable = re.compile(r"^(sh|bash|python3?|\./|\.githooks/|git |make |scripts/|tests/)")
    seen, out = set(), []
    for c in cands:
        if runnable.match(c) and c not in seen:
            seen.add(c)
            out.append(c)
    return out[:6]


def discovered_scripts(repo: Path, pristine_hook: str) -> list[str]:
    """New/modified executables that look like checks."""
    out = []
    hook = repo / ".githooks" / "pre-commit"
    if hook.exists() and hook.read_text() != pristine_hook:
        out.append(str(hook.relative_to(repo)))
    _, listing = sh(repo, ["git", "log", "--format=", "--name-only", "-3"])
    _, status = sh(repo, ["git", "diff", "HEAD~1", "--name-only"])
    for rel in set(listing.split() + status.split()):
        p = repo / rel
        if (rel.startswith(("scripts/", "tests/", "tools/", ".githooks/"))
                and p.is_file() and rel != ".githooks/pre-commit"
                and p.suffix in (".py", ".sh", "")):
            out.append(rel)
    return out


def run_entry(repo: Path, entry: str) -> tuple[int, str]:
    if " " not in entry and "/" in entry:
        # a bare path: prefer its own shebang, fall back to an interpreter
        rc, out = sh(repo, [f"./{entry}" if not entry.startswith((".", "/")) else entry])
        if rc == 125:
            interp = "python3" if entry.endswith(".py") else "sh"
            rc, out = sh(repo, [interp, entry])
        return rc, out
    if entry.endswith(".py") and not entry.startswith(("python", "sh", "bash")):
        return sh(repo, ["python3", entry])
    return sh(repo, entry)  # shell string (demo command)


def find_working_entry(repo: Path, candidates: list[str],
                       violation: dict[str, str], compliant: dict[str, str]):
    """An entry 'works' when it complains on the violation and not on compliance."""
    for entry in candidates:
        reset(repo)
        stage(repo, violation)
        rc_v, out_v = run_entry(repo, entry)
        reset(repo)
        stage(repo, compliant)
        rc_c, out_c = run_entry(repo, entry)
        reset(repo)
        if rc_v not in (0, 124, 125, 127) and rc_c == 0:
            return entry, (rc_v, out_v), (rc_c, out_c)
    return None, None, None


def grade_c1(repo: Path, answer: str, pristine_hook: str):
    checks = []
    violation = {"courier/handlers.py": "\n# tuning note\n"}
    compliant = {"courier/handlers.py": "\n# tuning note\n",
                 "schemas/fixtures/orders.json": "\n"}
    neutral = {"README.md": "\n<!-- doc touch -->\n"}
    candidates = demo_commands(answer) + discovered_scripts(repo, pristine_hook)
    entry, v, c = find_working_entry(repo, candidates, violation, compliant)
    if entry is None:
        ev = f"entry_point: none (tried {candidates or 'nothing discoverable'})"
        checks.append({"id": "C1.1", "passed": False, "evidence": ev})
        checks.append({"id": "C1.2", "passed": False, "evidence": ev})
        checks.append({"id": "C1.3", "passed": False, "evidence": ev})
        return checks
    checks.append({"id": "C1.1", "passed": True, "evidence": f"entry_point: {entry}"})
    checks.append({"id": "C1.2", "passed": True,
                   "evidence": f"violation -> exit {v[0]}: {v[1][:200]}"})
    reset(repo)
    stage(repo, neutral)
    rc_n, out_n = run_entry(repo, entry)
    reset(repo)
    ok = c[0] == 0 and rc_n == 0
    checks.append({"id": "C1.3", "passed": ok,
                   "evidence": f"compliant -> exit {c[0]}; unrelated-only -> exit {rc_n}: "
                               f"{(c[1] + ' | ' + out_n)[:200]}"})
    return checks


FANOUT_RE = re.compile(r'(def fanout\([^)]*\):\n(\s*)""")(.*?)(""")', re.S)


def set_fanout_docstring(repo: Path, with_retries: bool) -> bool:
    """Force the fanout docstring into violating or compliant state.

    The submission may legitimately have fixed the planted violation as part
    of 'make the situation better', so the checker reconstructs both states
    rather than assuming the tree is still violating."""
    handlers = repo / "courier" / "handlers.py"
    if not handlers.exists():
        return False
    text = handlers.read_text()
    body = ("Deliver payload to every route in the list.\n\n"
            "\\g<2>Retries: per-route, inherits forward().\n\\g<2>"
            if with_retries else
            "Deliver payload to every route in the list.")
    new, n = FANOUT_RE.subn(r"\g<1>" + body + r"\g<4>", text, count=1)
    if n:
        handlers.write_text(new)
    return bool(n)


def grade_c4(repo: Path, answer: str, pristine_hook: str):
    candidates = demo_commands(answer) + discovered_scripts(repo, pristine_hook)
    for entry in candidates:
        reset(repo)
        if not set_fanout_docstring(repo, with_retries=False):
            break  # fanout unrecognizable; fall through to judge
        rc_v, out_v = run_entry(repo, entry)
        if rc_v in (0, 124, 125, 127) or "fanout" not in out_v:
            reset(repo)
            continue
        reset(repo)
        set_fanout_docstring(repo, with_retries=True)
        rc_f, out_f = run_entry(repo, entry)
        reset(repo)
        ok = rc_f == 0
        return [{"id": "C4.3", "passed": ok,
                 "evidence": f"entry_point: {entry}; missing Retries -> exit {rc_v} "
                             f"(flags fanout); with Retries present -> exit {rc_f}: "
                             f"{'silent' if ok else out_f[:150]}"}]
    return [{"id": "C4.3", "passed": False,
             "evidence": f"no runnable check flagged a Retries-less fanout and quieted "
                         f"once it was declared (tried {candidates or 'nothing discoverable'})"}]


def grade_c5(repo: Path):
    checks = []
    hook = repo / ".githooks" / "pre-commit"
    if not hook.exists():
        ev = ".githooks/pre-commit missing from finished sandbox"
        return [{"id": "C5.1", "passed": False, "evidence": ev},
                {"id": "C5.2", "passed": False, "evidence": ev}]

    def run_hook():
        rc, out = sh(repo, ["./.githooks/pre-commit"])
        if rc == 125:  # not directly executable — fall back to sh
            rc, out = sh(repo, ["sh", ".githooks/pre-commit"])
        return rc, out

    reset(repo)
    stage(repo, {"courier/transform.py": '\nprint("debug")\n'})
    rc_p, out_p = run_hook()
    reset(repo)
    stage(repo, {"config/routes.yml": "Bad_Route:\n  target: https://x.example/y\n"})
    rc_k, out_k = run_hook()
    reset(repo)
    stage(repo, {"docs/notes.md": "\n2026-07-26 (dana) - retro moved to thursday.\n"})
    rc_ok, out_ok = run_hook()
    reset(repo)
    passed = rc_p != 0 and rc_k != 0 and rc_ok == 0
    checks.append({"id": "C5.1", "passed": passed,
                   "evidence": f"print-> exit {rc_p} ({out_p.strip()[:80]}); "
                               f"kebab-> exit {rc_k} ({out_k.strip()[:80]}); "
                               f"clean-> exit {rc_ok} ({out_ok.strip()[:80]})"})
    text = hook.read_text()
    dead = "lib/config" in text
    checks.append({"id": "C5.2", "passed": not dead,
                   "evidence": "hook still globs lib/config/ (dead since the May rename)"
                   if dead else "no lib/config reference in the shipped hook"})
    return checks


PRISTINE_HOOK_MARKER = "courier pre-commit checks"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--case", required=True, choices=["C1", "C4", "C5"])
    ap.add_argument("--sandbox", type=Path, required=True,
                    help="the run's finished (mutated) sandbox")
    ap.add_argument("--answer", type=Path, help="answer.md from the run")
    ap.add_argument("--pristine-hook", type=Path,
                    help="the unmodified .githooks/pre-commit, for change detection")
    args = ap.parse_args()

    answer = args.answer.read_text() if args.answer and args.answer.exists() else ""
    pristine = (args.pristine_hook.read_text()
                if args.pristine_hook and args.pristine_hook.exists() else "")
    repo = fresh_copy(args.sandbox)
    try:
        if args.case == "C1":
            checks = grade_c1(repo, answer, pristine)
        elif args.case == "C4":
            checks = grade_c4(repo, answer, pristine)
        else:
            checks = grade_c5(repo)
    finally:
        shutil.rmtree(repo.parent, ignore_errors=True)
    print(json.dumps({"checks": checks}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
