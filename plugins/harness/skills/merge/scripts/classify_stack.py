#!/usr/bin/env python3
"""Journey/state classifier for a finished PR stack (ORC-8) — the merger's
instrument, not a gate. Run inside the repository on the branch to judge:

    python3 classify_stack.py [--base origin/main] [--model <id>] [--repo DIR]

Emits one JSON object per outgoing commit (oldest first) on stdout:

    {"sha": …, "subject": …, "verdict": "fold"|"keep"|null, "reason": …}

`fold`: the commit answers this branch's own history (a repair of an earlier
commit, a review-finding fix) — the merger folds it into the commit it
corrects before rebase-merging. `keep`: its problem predates the branch — it
survives as landed history. `null`: the judge was unreachable; decide by
hand. Leftover fixup!/squash!/amend! subjects are folds by definition and
spend no model call; merge commits are never judged.

The verdict is statistical, calibrated on the principal's recorded fold
history (evals/stack-provenance; held-out rates in results/). The judge sees
only what the stack itself carries — each commit's message plus the ordered
sibling subjects — through claude-haiku-4-5-20251001 with all tools
disabled, from a neutral cwd so no repository context can leak into it.
"""
import argparse, json, os, re, subprocess, sys, tempfile
from concurrent.futures import ThreadPoolExecutor

MODEL = os.environ.get("HARNESS_STACK_PROVENANCE_MODEL", "claude-haiku-4-5-20251001")
MAX_SCAN = 200        # a branch this far past base is not an agent stack
SQUASH_RE = re.compile(r"^(fixup|squash|amend)! ")
SCHEMA = json.dumps({"type": "object",
                     "properties": {"verdict": {"type": "string", "enum": ["fold", "keep"]},
                                    "reason": {"type": "string"}},
                     "required": ["verdict", "reason"], "additionalProperties": False})
RUBRIC_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "rubric.md")


def build_prompt(rubric, message, stack):
    # The judge's whole input — single home, importlib-loaded by the eval
    # runner so the calibrated rates measure the shipped judge by
    # construction. The ordered sibling listing gives the judge the same
    # view the stack carries — what this branch built, and which commits
    # precede the judged one — so unstated provenance resolves without
    # guessing direction.
    ctx = ""
    if stack:
        ctx = ("\n<outgoing-stack ordered=oldest-first>\n"
               + "\n".join("- " + s for s in stack)
               + "\n</outgoing-stack>\n")
    return (rubric + ctx + "\n<commit-message>\n" + message + "\n</commit-message>\n"
            + "\nAnswer with the JSON verdict.")


def neutral_cwd():
    # The judge must not load any repo's CLAUDE.md or plugins — that context
    # is irrelevant to the verdict and costs tokens per call.
    return tempfile.gettempdir()


def classify(rubric, message, stack):
    # Returns (verdict, reason); (None, reason) on any judge failure.
    prompt = build_prompt(rubric, message, stack)
    override = os.environ.get("HARNESS_STACK_PROVENANCE_CLASSIFIER")
    try:
        if override:
            r = subprocess.run(override, shell=True, input=prompt,
                               capture_output=True, text=True, timeout=120)
            if r.returncode != 0:
                return None, "judge override exited %d" % r.returncode
            parsed = json.loads(r.stdout)
        else:
            r = subprocess.run(
                ["claude", "-p", prompt, "--model", MODEL, "--tools", "",
                 "--output-format", "json", "--json-schema", SCHEMA,
                 "--no-session-persistence"],
                capture_output=True, text=True, timeout=240, cwd=neutral_cwd())
            if r.returncode != 0:
                return None, "judge exited %d: %s" % (r.returncode, r.stderr[:120])
            parsed = json.loads(r.stdout).get("structured_output")
        if parsed and parsed.get("verdict") in ("fold", "keep"):
            return parsed["verdict"], parsed.get("reason", "")
        return None, "no verdict in judge output"
    except Exception as e:
        return None, "judge failed: %s" % type(e).__name__


def resolve_base(git):
    refs = git("for-each-ref", "--format=%(refname) %(symref:short)",
               "refs/remotes/origin/HEAD", "refs/remotes/origin/main",
               "refs/remotes/origin/master")
    if refs.returncode != 0:
        return None
    seen = {}
    for line in refs.stdout.splitlines():
        name, _, sym = line.partition(" ")
        seen[name] = sym.strip()
    return (seen.get("refs/remotes/origin/HEAD")
            or ("origin/main" if "refs/remotes/origin/main" in seen else None)
            or ("origin/master" if "refs/remotes/origin/master" in seen else None))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default=None,
                    help="range base; default origin/HEAD -> origin/main -> origin/master")
    ap.add_argument("--repo", default=os.getcwd())
    ap.add_argument("--jobs", type=int, default=4)
    args = ap.parse_args()

    def git(*a):
        return subprocess.run(["git", "-C", args.repo, *a],
                              capture_output=True, text=True, timeout=10)

    base = args.base or resolve_base(git)
    if not base:
        print("classify_stack: no base branch resolvable", file=sys.stderr)
        return 1
    rng = git("log", "--no-merges", "--max-count=" + str(MAX_SCAN),
              "--format=%H%x00%s%x00%B%x01", base + "..HEAD")
    if rng.returncode != 0:
        print("classify_stack: " + rng.stderr.strip(), file=sys.stderr)
        return 1
    commits = []
    for chunk in rng.stdout.split("\x01"):
        chunk = chunk.strip("\n")
        if chunk:
            sha, subject, body = chunk.split("\x00", 2)
            commits.append((sha, subject, body.strip()))
    commits.reverse()  # oldest first, matching the listing the judge reads
    if not commits:
        return 0

    rubric = open(RUBRIC_PATH).read()

    def listing_for(pos):
        return [">>> the commit under judgment <<<" if i == pos
                else ("(earlier) " if i < pos else "(later) ") + subj
                for i, (_, subj, _) in enumerate(commits)]

    def judge(pos):
        sha, subject, body = commits[pos]
        if SQUASH_RE.match(subject):
            return {"sha": sha, "subject": subject, "verdict": "fold",
                    "reason": "fixup!/squash!/amend! machinery names the commit it folds into"}
        verdict, reason = classify(rubric, body, listing_for(pos))
        return {"sha": sha, "subject": subject, "verdict": verdict, "reason": reason}

    with ThreadPoolExecutor(min(args.jobs, len(commits))) as ex:
        for row in ex.map(judge, range(len(commits))):
            print(json.dumps(row), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
