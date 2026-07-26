#!/usr/bin/env python3
"""Steering-text token diff for the commit protocol's [CHANGE] section.

Measures a commit's changes to steering files through the Anthropic
token-count endpoint (POST {base_url}/v1/messages/count_tokens, GA, free,
rate-limited separately from message creation) and prints the
`Token diff:` line whose format the commit-protocol SKILL.md defines.

File selection: positional paths (repo-root-relative) name the files;
with none given, the set derives from the diff itself, filtered by
STEERING_RE below - the single home of the steering-path pattern (the
commit-shape gate imports it). Derivation makes a recorded figure
re-derivable without knowing what the author typed. A named path absent
on both sides aborts to `unavailable`: a wrong list must not read as a
measured zero.

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
  override with --model).
- File contents are sent to the Anthropic API.

Credentials resolve in order: ANTHROPIC_API_KEY, ANTHROPIC_AUTH_TOKEN, an
`ant` CLI login. ANTHROPIC_BASE_URL overrides the endpoint host.

Exit codes: 0 counted; 2 printed a `Token diff: unavailable (<reason>)`
line (expected degradation: missing credentials, unreachable endpoint,
unresolvable files - the metric is informational and must never block a
commit); 1 usage or git error, nothing usable printed.
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import urllib.error
import urllib.request

API_VERSION = "2023-06-01"
DEFAULT_MODEL = "claude-opus-5"
SENTINEL = "x"

# Conservative operational net for steering text - files loaded into
# agent/model context. The commit-protocol skill's intent-based definition
# governs beyond it; the commit-shape gate imports this constant rather
# than keeping a second copy.
STEERING_RE = (r"(^|/)(CLAUDE|AGENTS)\.md$"
               r"|(^|/)(skills|agents|commands)/.*\.md$"
               r"|(^|/)\.claude/.*\.md$")


class Unavailable(Exception):
    """Counting cannot proceed; degrade to the `unavailable` line."""


def git_blob(spec):
    """Content of `git show <spec>`, or None when the path is absent there."""
    r = subprocess.run(["git", "show", spec], capture_output=True)
    return r.stdout.decode("utf-8", "replace") if r.returncode == 0 else None


def derive_paths(base, target):
    """Steering files changed between the comparison sides, repo-relative.

    --no-renames keeps both sides of a rename in the set; folded to the
    destination alone, moved content would read as a pure addition.
    """
    args = (["git", "diff", "--name-only", "--no-renames", base, target] if target
            else ["git", "diff", "--name-only", "--no-renames", "--cached", base])
    r = subprocess.run(args, capture_output=True, text=True)
    if r.returncode != 0:
        raise Unavailable("git diff failed: %s" % r.stderr.strip())
    return [p for p in r.stdout.splitlines() if p and re.search(STEERING_RE, p)]


def resolve_credentials():
    key = os.environ.get("ANTHROPIC_API_KEY")
    if key:
        return {"x-api-key": key}
    token = os.environ.get("ANTHROPIC_AUTH_TOKEN")
    if not token and shutil.which("ant"):
        r = subprocess.run(
            ["ant", "auth", "print-credentials", "--access-token"],
            capture_output=True, text=True, timeout=15,
        )
        if r.returncode == 0 and r.stdout.strip():
            token = r.stdout.strip()
    if token:
        headers = {"authorization": "Bearer " + token}
        if token.startswith("sk-ant-oat"):
            headers["anthropic-beta"] = "oauth-2025-04-20"
        return headers
    return None


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
                        default=DEFAULT_MODEL)
    parser.add_argument("--base", default="HEAD",
                        help="revision for the before side (default: HEAD)")
    parser.add_argument("--target", default=None,
                        help="revision for the after side (default: the index)")
    parser.add_argument("paths", nargs="*",
                        help="steering files, repo-root-relative; default: "
                             "files in the diff matching STEERING_RE")
    args = parser.parse_args()

    inside = subprocess.run(["git", "rev-parse", "--is-inside-work-tree"],
                            capture_output=True)
    if inside.returncode != 0:
        print("token_diff.py: not inside a git work tree", file=sys.stderr)
        return 1

    added = removed = 0
    try:
        paths = args.paths or derive_paths(args.base, args.target)
        if not paths:
            # An empty derivation is a selection problem, not a measurement:
            # printing a line here would record a falsehood about a commit
            # that did change steering text. Exit 1 - nothing paste-able.
            scope = ("%s..%s" % (args.base, args.target) if args.target
                     else "staged")
            print("token_diff.py: no steering-pattern files in the %s diff; "
                  "stage the changes first, or measure an existing commit "
                  "with --base <sha>^ --target <sha>" % scope, file=sys.stderr)
            return 1
        headers = resolve_credentials()
        if headers is None:
            raise Unavailable("no Anthropic API credentials: set "
                              "ANTHROPIC_API_KEY or ANTHROPIC_AUTH_TOKEN, "
                              "or `ant auth login`")
        counter = Counter(
            args.model, headers,
            os.environ.get("ANTHROPIC_BASE_URL", "https://api.anthropic.com"),
        )
        for path in paths:
            before = git_blob("%s:%s" % (args.base, path))
            target_spec = "%s:%s" % (args.target, path) if args.target else ":%s" % path
            after = git_blob(target_spec)
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
