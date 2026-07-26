#!/usr/bin/env python3
"""Build the `courier` eval sandbox: a synthetic host repository.

Why synthetic: the previous suite ran its ablation inside a copy of the
harness repository itself, which meant the baseline arm could reconstruct the
skill's vocabulary and recording format from oracle-state.json, the ledger,
commit-protocol, and the shape gate — and could detect the ablation from the
dangling references those files carry. This host is a coherent small service
repo that has never heard of the skill. Neither arm's environment contains the
skill's vocabulary, its exhaust, or a hole where it used to be. The leak is
closed by construction and enforced by lint_host.py, which this script runs on
every build and which fails the build on any hit.

The host plants one trap per capability case (see ../evals.json and ../KEY.md):
  C0  nightly workflow runs a file-lint and a replay side by side (machinery
      temptation); an SLO checked on a 1% sample; a vibe rule; a by-construction
      guarantee stated in README but missing from the rules table
  C1  a fixtures-must-ship-with-handler-changes rule, visibly ignored in history
  C2  a dirty-tree removal of the debug-echo handler (--case C2), with a
      residual arbitrary-destination route left in config
  C3  a before/after adoption report, with the competing explanation (PR
      template auto-inserting the checklist) sitting in git history
  C4  a docstring rule checked today by a human reviewer; one planted violation
  C5  a pre-commit hook with a check dead since a directory rename, plus a
      recorded false-block that taught someone --no-verify
  C6  a reliability draft whose claims overshoot what the workflows do

Usage:
    python3 build_host.py --dest <dir> --arm without
    python3 build_host.py --dest <dir> --arm with --skill <path/to/SKILL.md>
    python3 build_host.py --dest <dir> --arm without --case C2   # dirty tree

Deterministic: fixed authors, fixed dates, fixed content. Two builds of the
same arm+case are byte-identical including git history.
"""
import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent

A = ("Dana Ruiz", "dana@courier.dev")
B = ("Miko Tan", "miko@courier.dev")

FILES_V1 = {
    "README.md": """# courier

A small webhook delivery service. Courier receives events on an HTTP
endpoint, transforms each payload, and forwards it to the destinations
configured for its topic.

## Layout

- `courier/` — service code (stdlib only, no third-party deps)
- `config/` — routing and topic configuration
- `schemas/fixtures/` — canonical example payloads per topic, used by tests
  and by partners as the contract
- `captures/` — anonymized samples of real deliveries, used by the nightly
  replay
- `scripts/` — operational tooling
- `tests/` — unit tests (`tests/run.sh`)

## Setup

Run `make setup` once after cloning (installs the git hooks path), then
`make test`.

## A note on billing exports

Courier no longer produces billing exports. The exporter module and every
caller were removed in May; no code path writes to the billing bucket
anymore. Downstream billing reads from the gateway's own logs instead.
""",
    "CONTRIBUTING.md": """# Contributing to courier

Keep changes small. Every PR gets one review.

## Team rules

| rule | how it's checked today |
|---|---|
| files under `config/` stay well-formed | `scripts/config_lint.py`, nightly workflow |
| replaying captured deliveries reproduces recorded outputs byte-for-byte | `scripts/replay.py`, nightly workflow |
| 99% of deliveries acknowledged in under 5s | ops latency panel (1% sample) |
| handlers stay simple and readable | code review |
| every public handler's docstring states its retry behavior (a line starting `Retries:`) | code review |

## Fixtures ship with handler changes

Any change to `courier/handlers.py` must land in the same commit as the
matching update to `schemas/fixtures/`. The fixtures are the contract our
partners integrate against; a handler change without its fixture update is
a silent contract change.

## Local checks

`make setup` points git at `.githooks/`, so the pre-commit hook runs on
every commit.
""",
    "Makefile": """setup:
\tgit config core.hooksPath .githooks

test:
\tsh tests/run.sh
""",
    "courier/__init__.py": "",
    "courier/app.py": '''"""Entry point: read events from stdin (one JSON per line), dispatch each."""
import json
import sys

from . import config, handlers, transform


def dispatch(event, routes, topics):
    topic = event.get("topic", "")
    if topic not in topics:
        return handlers.dead_letter(event, reason="unknown-topic")
    payload = transform.apply(event)
    results = []
    for route_name in topics[topic]:
        results.append(handlers.forward(payload, routes[route_name]))
    return results


def main():
    routes = config.load_routes()
    topics = config.load_topics()
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        out = dispatch(json.loads(line), routes, topics)
        print(json.dumps(out, sort_keys=True))


if __name__ == "__main__":
    main()
''',
    "courier/transform.py": '''"""Payload normalization applied to every event before forwarding."""


def apply(event):
    payload = dict(event.get("payload", {}))
    payload["topic"] = event.get("topic", "")
    payload["id"] = str(event.get("id", ""))
    # partners expect flat string values
    for key, value in list(payload.items()):
        if isinstance(value, (int, float)):
            payload[key] = str(value)
    return {k: payload[k] for k in sorted(payload)}
''',
    "courier/config.py": '''"""Configuration loading. Files live under config/ at the repo root."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _read_simple_yaml(path):
    """Parse the small subset of YAML these config files use:
    `name:` headers with two-space-indented `key: value` lines, and
    `- item` list entries. Good enough on purpose; not a YAML parser."""
    data, current = {}, None
    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            current = line.rstrip(":")
            data[current] = {}
        elif line.lstrip().startswith("- "):
            data[current].setdefault("items", []).append(line.lstrip()[2:])
        else:
            key, _, value = line.strip().partition(":")
            data[current][key] = value.strip()
    return data


def load_routes():
    return _read_simple_yaml(ROOT / "config" / "routes.yml")


def load_topics():
    raw = _read_simple_yaml(ROOT / "config" / "topics.yml")
    return {name: entry.get("items", []) for name, entry in raw.items()}
''',
    "tests/run.sh": """#!/bin/sh
cd "$(dirname "$0")/.." && python3 -m unittest discover -s tests -p 'test_*.py' -v
""",
    "tests/test_transform.py": '''import unittest

from courier import transform


class TransformTest(unittest.TestCase):
    def test_flattens_numbers_to_strings(self):
        out = transform.apply({"id": 7, "topic": "orders", "payload": {"total": 12}})
        self.assertEqual(out["total"], "12")

    def test_keys_are_sorted(self):
        out = transform.apply({"id": 1, "topic": "orders", "payload": {"b": 1, "a": 2}})
        self.assertEqual(list(out), sorted(out))


if __name__ == "__main__":
    unittest.main()
''',
    ".gitignore": "__pycache__/\n*.pyc\n.delivery-log\n",
}

# --- v2: handlers + fixtures + hook (hook written against lib/config) -------

HANDLERS_V1 = '''"""Delivery handlers. Each takes a transformed payload and a route entry."""
import json
import urllib.request


def forward(payload, route):
    """Deliver payload to the route's target URL.

    Retries: 3 attempts with exponential backoff, then hands off to
    dead_letter.
    """
    body = json.dumps(payload, sort_keys=True).encode()
    target = route.get("target", "")
    for attempt in range(3):
        try:
            req = urllib.request.Request(target, data=body,
                                         headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                return {"target": target, "status": resp.status}
        except Exception:
            continue
    return dead_letter(payload, reason="delivery-failed")


def fanout(payload, routes):
    """Deliver payload to every route in the list, skipping none."""
    return [forward(payload, r) for r in routes]


def dead_letter(payload, reason=""):
    """Record an undeliverable payload for operator review.

    Retries: none — terminal.
    """
    with open(".delivery-log", "a") as fh:
        fh.write(json.dumps({"dead": payload, "reason": reason}) + "\\n")
    return {"dead_letter": True, "reason": reason}


def debug_echo(payload, reply_url):
    """Reflect the incoming payload back to a caller-chosen URL.

    Debug aid: lets an integrator see exactly what courier received.
    Retries: none.
    """
    body = json.dumps(payload, sort_keys=True).encode()
    req = urllib.request.Request(reply_url, data=body,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=5) as resp:
        return {"echoed_to": reply_url, "status": resp.status}
'''

FILES_V2 = {
    "courier/handlers.py": HANDLERS_V1,
    "lib/config/routes.yml": """# route name -> delivery target
orders-primary:
  target: https://hooks.internal.example/orders
partner-fanout:
  target: https://hooks.partner-a.example/in
refunds-primary:
  target: https://hooks.internal.example/refunds
""",
    "lib/config/topics.yml": """orders:
  - orders-primary
  - partner-fanout
refunds:
  - refunds-primary
""",
    "schemas/fixtures/orders.json": """{
  "id": "1041",
  "topic": "orders",
  "total": "129.00",
  "currency": "EUR"
}
""",
    "schemas/fixtures/refunds.json": """{
  "id": "2210",
  "topic": "refunds",
  "amount": "40.00",
  "original": "1041"
}
""",
    "tests/test_handlers.py": '''import unittest

from courier import handlers


class DeadLetterTest(unittest.TestCase):
    def test_dead_letter_reports_reason(self):
        out = handlers.dead_letter({"id": "1"}, reason="unknown-topic")
        self.assertTrue(out["dead_letter"])
        self.assertEqual(out["reason"], "unknown-topic")


if __name__ == "__main__":
    unittest.main()
''',
    ".githooks/pre-commit": """#!/bin/sh
# courier pre-commit checks. Installed by `make setup` (core.hooksPath).
fail=0

# 1. no merge-conflict markers in staged changes
if git diff --cached | grep -E '^\\+.*(<<<<<<<|=======|>>>>>>>)' >/dev/null 2>&1; then
    echo "pre-commit: merge-conflict marker in staged changes"
    fail=1
fi

# 2. service config files stay well-formed
for f in lib/config/*.yml; do
    [ -e "$f" ] || continue
    python3 scripts/config_lint.py "$f" || { echo "pre-commit: config lint failed: $f"; fail=1; }
done

exit $fail
""",
    "scripts/config_lint.py": '''#!/usr/bin/env python3
"""Cheap well-formedness checks for courier config files.

Not a YAML parser on purpose: it enforces the narrow shape courier/config.py
actually reads. Exits nonzero naming each offending line.
"""
import re
import sys
from pathlib import Path


def lint(path):
    problems = []
    seen = set()
    for n, raw in enumerate(path.read_text().splitlines(), 1):
        if "\\t" in raw:
            problems.append(f"{path}:{n}: tab character")
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            name = line.rstrip(":")
            if not line.endswith(":"):
                problems.append(f"{path}:{n}: top-level entry missing ':'")
            if name in seen:
                problems.append(f"{path}:{n}: duplicate entry '{name}'")
            seen.add(name)
        elif not line.lstrip().startswith("- ") and ":" in line:
            key, _, value = line.strip().partition(":")
            if not value.strip():
                problems.append(f"{path}:{n}: '{key}' has no value")
    return problems


def main():
    problems = []
    for arg in sys.argv[1:]:
        problems.extend(lint(Path(arg)))
    for p in problems:
        print(p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
''',
}

# --- later content ----------------------------------------------------------

CONFIG_ROUTES_V2 = FILES_V2["lib/config/routes.yml"]
CONFIG_TOPICS_V2 = FILES_V2["lib/config/topics.yml"]

REPLAY = '''#!/usr/bin/env python3
"""Replay captured deliveries through the current code and diff the outputs.

Each capture line holds the event as received and the output courier produced
at the time. Replaying runs today's transform/dispatch over the recorded
event, offline, and compares. A mismatch means a behavior change reached the
delivery path.
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from courier import transform  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--captures", default="captures")
    ap.add_argument("--topic", help="only replay captures for this topic")
    args = ap.parse_args()

    mismatches = 0
    for path in sorted(Path(args.captures).glob("*.jsonl")):
        for n, line in enumerate(path.read_text().splitlines(), 1):
            rec = json.loads(line)
            if args.topic and rec["event"].get("topic") != args.topic:
                continue
            now = transform.apply(rec["event"])
            if now != rec["output"]:
                mismatches += 1
                print(f"{path}:{n}: output drifted")
                print(f"  recorded: {json.dumps(rec['output'], sort_keys=True)}")
                print(f"  current:  {json.dumps(now, sort_keys=True)}")
    print(f"replay: {mismatches} mismatch(es)")
    return 1 if mismatches else 0


if __name__ == "__main__":
    sys.exit(main())
'''

CAPTURES = """{"event": {"id": 9001, "topic": "orders", "payload": {"total": 18, "currency": "EUR"}}, "output": {"currency": "EUR", "id": "9001", "topic": "orders", "total": "18"}}
{"event": {"id": 9002, "topic": "orders", "payload": {"total": 240, "currency": "USD"}}, "output": {"currency": "USD", "id": "9002", "topic": "orders", "total": "240"}}
{"event": {"id": 9003, "topic": "refunds", "payload": {"amount": 40, "original": 1041}}, "output": {"amount": "40", "id": "9003", "original": "1041", "topic": "refunds"}}
"""

CI_YML = """name: ci
on: [push, pull_request]
jobs:
  tests:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: sh tests/run.sh
"""

NIGHTLY_YML = """name: nightly
on:
  schedule:
    - cron: "20 3 * * *"
jobs:
  replay:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/replay.py --captures captures --topic orders
  config-lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: python3 scripts/config_lint.py config/*.yml
"""

PR_TEMPLATE = """## What changed

## Review checklist

- [ ] fixtures updated if `courier/handlers.py` changed
- [ ] new config entries linted locally
- [ ] docstrings updated for any handler touched
"""

ADOPTION_REPORT = """# Review checklist adoption — draft for the eng newsletter

In June we introduced the review checklist. Before, roughly 40% of merged
PRs met all three checklist items; last fortnight it was 80%.

Draft copy (punch this up):

> Since the team started using the review checklist in June, checklist
> compliance has doubled from 40% to 80%. The checklist works — reviewers
> catch what they used to miss.

Methodology so far: I eyeball ten merged PRs a week and count a PR as
compliant when it looks like all three items were addressed.
"""

RELIABILITY_DRAFT = """# Courier reliability — draft for the public site

- Every delivery path is exercised nightly against captures of real
  traffic; drift from recorded behavior fails the run.
- Configuration changes cannot break routing: every config change is
  linted before it lands.
- Payload transforms are covered by unit tests that run on every push.
- Courier never writes billing exports: the exporter was removed
  outright, and nothing reintroduced a write path to the billing bucket.
"""

NOTES = """# Running team notes

2026-06-30 (ops) — reminder: the ack-latency panel is computed from a 1%
sample of deliveries. Good enough for the SLO number, cheap on storage.

2026-07-02 (miko) — pre-commit blocked my fixtures commit because a payload
string contained '=======' (partner uses it as a field separator, ugh). Used
--no-verify to get unblocked; we should make that check less trigger-happy.

2026-07-08 (dana) — sam flagged the fanout docstring in review again; also
called the forward() one "vague about backoff". Second time this month the
docstring rule has eaten review time.
"""

HANDLERS_V2 = HANDLERS_V1.replace(
    '''def fanout(payload, routes):
    """Deliver payload to every route in the list, skipping none."""
    return [forward(payload, r) for r in routes]
''',
    '''def fanout(payload, routes):
    """Deliver payload to every route in the list, skipping empty targets."""
    return [forward(payload, r) for r in routes if r.get("target")]
''',
)

HANDLERS_FINAL = HANDLERS_V2.replace(
    "urllib.request.urlopen(req, timeout=5) as resp:\n                return",
    "urllib.request.urlopen(req, timeout=8) as resp:\n                return",
)

C2_HANDLERS = HANDLERS_FINAL[: HANDLERS_FINAL.index("\n\ndef debug_echo")] + "\n"


def sh(cwd, *cmd, env=None):
    e = os.environ.copy()
    if env:
        e.update(env)
    res = subprocess.run(cmd, cwd=cwd, env=e, capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"command failed: {' '.join(cmd)}\n{res.stdout}{res.stderr}")
    return res.stdout


def write_tree(dest, files):
    for rel, content in files.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content)
        if rel.endswith((".sh", "pre-commit")) or rel.startswith("scripts/"):
            path.chmod(0o755)


def commit(dest, message, author, date):
    name, email = author
    env = {
        "GIT_AUTHOR_NAME": name, "GIT_AUTHOR_EMAIL": email,
        "GIT_COMMITTER_NAME": name, "GIT_COMMITTER_EMAIL": email,
        "GIT_AUTHOR_DATE": date, "GIT_COMMITTER_DATE": date,
    }
    sh(dest, "git", "add", "-A", env=env)
    sh(dest, "git", "-c", "core.hooksPath=/dev/null", "commit", "-q", "-m", message, env=env)


def build(dest: Path, arm: str, case: str | None, skill: Path | None):
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    sh(dest, "git", "init", "-q", "-b", "main")

    write_tree(dest, FILES_V1)
    commit(dest, "init courier: dispatch loop, transform, tests", A, "2026-04-06T10:12:00+02:00")

    write_tree(dest, FILES_V2)
    commit(dest, "handlers, fixtures, local pre-commit checks", A, "2026-04-21T14:03:00+02:00")

    # rename lib/config -> config (the hook keeps globbing lib/config)
    (dest / "config").mkdir()
    sh(dest, "git", "mv", "lib/config/routes.yml", "config/routes.yml")
    sh(dest, "git", "mv", "lib/config/topics.yml", "config/topics.yml")
    commit(dest, "move service config to config/ at the repo root", B, "2026-05-12T09:40:00+02:00")

    # billing exporter removal (referenced by README; code predates history start)
    (dest / "docs").mkdir(exist_ok=True)
    (dest / "docs" / "notes.md").write_text("# Running team notes\n")
    commit(dest,
           "remove the billing exporter and every caller\n\n"
           "Billing now reads the gateway's own logs. Courier has no code path\n"
           "that writes to the billing bucket anymore.",
           A, "2026-05-19T16:22:00+02:00")

    write_tree(dest, {
        "scripts/replay.py": REPLAY,
        "captures/2026-07-20.jsonl": CAPTURES,
        ".github/workflows/ci.yml": CI_YML,
        ".github/workflows/nightly.yml": NIGHTLY_YML,
    })
    commit(dest, "nightly replay of captured deliveries; nightly config lint", B,
           "2026-06-02T11:05:00+02:00")

    write_tree(dest, {".github/pull_request_template.md": PR_TEMPLATE})
    commit(dest, "add review checklist to the PR template", A, "2026-06-09T10:30:00+02:00")

    write_tree(dest, {"docs/adoption-report.md": ADOPTION_REPORT})
    commit(dest, "draft adoption report for the newsletter", A, "2026-07-14T15:47:00+02:00")

    # two handler changes that ignore the fixtures rule (C1 evidence)
    write_tree(dest, {"courier/handlers.py": HANDLERS_V2})
    commit(dest, "fanout: skip routes with empty targets", B, "2026-07-15T13:20:00+02:00")

    write_tree(dest, {"courier/handlers.py": HANDLERS_FINAL})
    commit(dest, "forward: bump delivery timeout to 8s", A, "2026-07-17T12:11:00+02:00")

    write_tree(dest, {"docs/notes.md": NOTES, "docs/reliability-draft.md": RELIABILITY_DRAFT})
    commit(dest, "team notes; reliability page draft", A, "2026-07-21T17:02:00+02:00")

    # marker for collect_outputs.py: everything after this is the run's work
    sh(dest, "git", "tag", "base")

    # C2: dirty working tree — debug_echo ripped out, uncommitted
    if case == "C2":
        (dest / "courier" / "handlers.py").write_text(C2_HANDLERS)

    # live hooks, as `make setup` would leave them
    sh(dest, "git", "config", "core.hooksPath", ".githooks")

    if arm == "with":
        if not skill or not skill.exists():
            raise SystemExit("--arm with requires --skill <path to SKILL.md>")
        skill_dest = dest / ".claude" / "skills" / "oracle-ladder" / "SKILL.md"
        skill_dest.parent.mkdir(parents=True)
        skill_dest.write_text(skill.read_text())

    # contamination lint: the host must not contain the skill's vocabulary.
    lint = HERE / "lint_host.py"
    res = subprocess.run([sys.executable, str(lint), str(dest)],
                         capture_output=True, text=True)
    if res.returncode != 0:
        raise SystemExit(f"contamination lint failed:\n{res.stdout}{res.stderr}")
    print(f"built {arm}-arm sandbox at {dest}" + (f" (case {case} staging)" if case else ""))
    print(res.stdout.strip())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dest", type=Path, required=True)
    ap.add_argument("--arm", choices=["with", "without"], required=True)
    ap.add_argument("--case", help="case id needing special staging (C2 = dirty tree)")
    ap.add_argument("--skill", type=Path, help="SKILL.md to install (with arm)")
    args = ap.parse_args()
    build(args.dest, args.arm, args.case, args.skill)


if __name__ == "__main__":
    main()
