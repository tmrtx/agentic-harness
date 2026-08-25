#!/usr/bin/env python3
"""Steering-text token diff for the commit protocol's [CHANGE] section.

Measures a commit's changes to steering files through the Anthropic
token-count endpoint (POST {base_url}/v1/messages/count_tokens, GA, free,
rate-limited separately from message creation) and prints the
`Token diff:` line whose format the commit-protocol SKILL.md defines.

File selection: positional paths name the files; with none given, the
set derives from the cwd repo's diff itself, filtered by STEERING_RE
below - the single home of the steering-path pattern (the commit-shape
gate imports it). Derivation makes a recorded figure re-derivable
without knowing what the author typed. A named path absent on both
sides aborts to `unavailable`: a wrong list must not read as a
measured zero.

Named paths are measured against the repository that OWNS them, not the
cwd's: the corpus and the measuring session routinely live in different
repositories (this plugin is self-consumed - a session working in a
consumer repo is exactly the one that discovers a steering edit), so an
absolute path, or a relative one that names a file on disk, resolves to
its own repo's HEAD -> index. A relative path naming nothing on disk
keeps the documented repo-root-relative reading against the cwd repo
(deleted files, historical measures). One invocation measures one repo:
paths spanning two abort - half a figure must not read as the whole.

Comparison sides default to HEAD -> index (the commit being composed).
`--base`/`--target` take any revision, so a recorded figure re-derives
later: token_diff.py --base <sha>^ --target <sha>.

Measurement semantics:
- One count per file side, with byte-identical request framing on both
  sides, so the request wrapper cancels exactly in the subtraction.
- Per-file deltas aggregate as added (sum of growth) and removed (sum of
  shrinkage). Per-file counting mirrors how steering files actually load -
  each as its own context block - and avoids the token merges a
  concatenated count would fabricate at file boundaries.
- An added or deleted file measures against a one-token sentinel baseline
  (the endpoint rejects empty content), so single-digit deltas are noise.
- Counts are model-specific estimates and pinned model IDs keep them
  reproducible, so the line names the model (default: claude-opus-5;
  override with --model or ANTHROPIC_TOKEN_DIFF_MODEL).
- File contents are sent to the Anthropic API.

Counting reads ANTHROPIC_TOKEN_DIFF_KEY and nothing else. The generic names
are deliberately not consulted: Claude Code claims ANTHROPIC_API_KEY for its
own auth, so a shared name set once for counting would silently redirect a
session's model calls - including this skill's own subagent judges - onto that
key's billing. One variable, one purpose - and the endpoint follows the same
isolation: sessions repoint the generic ANTHROPIC_BASE_URL at local proxies
that do not serve count_tokens, so counting reads only
ANTHROPIC_TOKEN_DIFF_BASE_URL (default https://api.anthropic.com).

Exit codes: 0 counted; 2 printed a `Token diff: unavailable (<reason>)`
line (expected degradation: missing credentials, unreachable endpoint,
unresolvable files - the metric is informational and must never block a
commit); 1 usage or git error, nothing usable printed.
"""

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request

API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-5"
SENTINEL = "x"
API_KEY_ENV = "ANTHROPIC_TOKEN_DIFF_KEY"

# Conservative operational net for steering text - files loaded into
# agent/model context. The commit-protocol skill's intent-based definition
# governs beyond it; the commit-shape gate imports this constant rather
# than keeping a second copy.
STEERING_RE = (r"(^|/)(CLAUDE|AGENTS)\.md$"
               r"|(^|/)(skills|agents|commands)/.*\.md$"
               r"|(^|/)\.claude/.*\.md$")


class Unavailable(Exception):
    """Counting cannot proceed; degrade to the `unavailable` line."""


def git_blob(repo, spec):
    """Content of `git show <spec>` in REPO, or None when absent there."""
    r = subprocess.run(["git", "-C", repo, "show", spec], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def derive_paths(repo, base, target):
    """Steering files changed between the comparison sides, repo-relative."""
    args = (["git", "-C", repo, "diff", "--name-only", base, target] if target
            else ["git", "-C", repo, "diff", "--name-only", "--cached", base])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise Unavailable("git diff failed: %s" % r.stderr.strip())
    return [p for p in r.stdout.splitlines() if p and re.search(STEERING_RE, p)]


def repo_root(start):
    """Toplevel of the work tree containing directory START, or None."""
    r = subprocess.run(["git", "-C", start, "rev-parse", "--show-toplevel"],
                       capture_output=True, text=True)
    return os.path.realpath(r.stdout.strip()) if r.returncode == 0 else None


def resolve_named(path, cwd_root):
    """A named PATH as (owning-repo root, repo-relative path).

    Filesystem-true resolution first - an absolute path, or a relative
    one that names something on disk, belongs to the repo that owns it
    on disk, wherever the script runs (a staged deletion resolves
    through its nearest existing ancestor). A relative path naming
    nothing on disk falls back to the documented repo-root-relative
    reading against the cwd repo, so deleted files and historical
    measures keep working from inside their repo."""
    fs = os.path.realpath(path)
    if os.path.isabs(path) or os.path.lexists(path):
        probe = fs if os.path.isdir(fs) else (os.path.dirname(fs) or ".")
        while not os.path.isdir(probe):
            parent = os.path.dirname(probe)
            if parent == probe:
                break
            probe = parent
        root = repo_root(probe)
        if not root or not (fs == root or fs.startswith(root + os.sep)):
            raise Unavailable("path is outside any git work tree: %s" % path)
        return root, os.path.relpath(fs, root)
    if cwd_root is None:
        raise Unavailable(
            "relative path %s names nothing on disk and the cwd is not a "
            "work tree - run from the repository that owns it" % path)
    return cwd_root, path


class Counter:
    def __init__(self, model, headers, base_url):
        self.model = model
        self.headers = headers
        self.url = base_url.rstrip("/") + "/v1/messages/count_tokens"
        self.memo = {}

    def count(self, text):
        if text in self.memo:
            return self.memo[text]
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": text}],
        }).encode()
        req = urllib.request.Request(
            self.url, data=body, method="POST",
            headers={
                "content-type": "application/json",
                "anthropic-version": API_VERSION,
                **self.headers,
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                tokens = int(json.load(resp)["input_tokens"])
        except urllib.error.HTTPError as e:
            raise Unavailable("count_tokens HTTP %d" % e.code)
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            raise Unavailable("count_tokens unreachable: %s" % getattr(e, "reason", e))
        except (ValueError, KeyError):
            raise Unavailable("count_tokens returned an unexpected response")
        self.memo[text] = tokens
        return tokens


class Parser(argparse.ArgumentParser):
    def error(self, message):
        # Usage errors exit 1; exit 2 is reserved for "printed an
        # `unavailable` line", so callers can paste stdout whenever rc is 0 or 2.
        self.print_usage(sys.stderr)
        self.exit(1, "%s: error: %s\n" % (self.prog, message))


def main():
    parser = Parser(
        description="Emit the commit protocol's `Token diff:` line for steering files.",
    )
    parser.add_argument("--model",
                        default=os.environ.get("ANTHROPIC_TOKEN_DIFF_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base", default="HEAD",
                        help="revision for the before side (default: HEAD)")
    parser.add_argument("--target", default=None,
                        help="revision for the after side (default: the index)")
    parser.add_argument("paths", nargs="*",
                        help="steering files, repo-root-relative; default: "
                             "files in the diff matching STEERING_RE")
    args = parser.parse_args()

    cwd_root = repo_root(".")
    # Deriving the file set needs a repo to diff, and only the cwd names
    # one; named paths carry their own repo, so the cwd gates nothing.
    if not args.paths and cwd_root is None:
        print("token_diff.py: not inside a git work tree", file=sys.stderr)
        return 1

    key = os.environ.get(API_KEY_ENV)
    if not key:
        print("Token diff: unavailable (no counting credential: set %s)" % API_KEY_ENV)
        return 2

    counter = Counter(
        args.model, {"x-api-key": key},
        os.environ.get("ANTHROPIC_TOKEN_DIFF_BASE_URL", "https://api.anthropic.com"),
    )
    added = removed = 0
    try:
        if args.paths:
            resolved = [resolve_named(p, cwd_root) for p in args.paths]
            roots = sorted(set(root for root, _ in resolved))
            if len(roots) > 1:
                raise Unavailable(
                    "named paths span repositories: %s - one line measures "
                    "one commit in one repo" % " vs ".join(roots))
            repo, paths = roots[0], [rel for _, rel in resolved]
        else:
            repo, paths = cwd_root, derive_paths(cwd_root, args.base,
                                                 args.target)
        if not paths:
            raise Unavailable("no steering-pattern files in the diff")
        for path in paths:
            before = git_blob(repo, "%s:%s" % (args.base, path))
            target_spec = "%s:%s" % (args.target, path) if args.target else ":%s" % path
            after = git_blob(repo, target_spec)
            if not before and not after:
                raise Unavailable("path not found on either side: %s" % path)
            delta = (counter.count(after if after else SENTINEL)
                     - counter.count(before if before else SENTINEL))
            print("token_diff.py: %s %+d" % (path, delta), file=sys.stderr)
            added += max(delta, 0)
            removed += max(-delta, 0)
    except Unavailable as e:
        print("Token diff: unavailable (%s)" % e)
        return 2

    print("Token diff: +%d/-%d (net %+d, %s)" % (added, removed, added - removed,
                                                 args.model))
    return 0


if __name__ == "__main__":
    sys.exit(main())
