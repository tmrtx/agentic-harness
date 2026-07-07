#!/usr/bin/env python3
"""Mine a Claude Code session transcript (JSONL) for root-cause forensics.

Subcommands:
  map  SESSION                 one line per record: index, type, block kinds,
                               tool names, prompt/skill snippets; header shows
                               path, record count, fork lineage.
  grep SESSION PATTERN [-i]    records containing PATTERN, matched against the
                               record's decoded string content (so quotes and
                               newlines in doctrine text match naturally), with
                               the same anatomy line as `map`.
  show SESSION IDX [IDX ...]   dump a record's content blocks;
       [--kind k1,k2] [--max-chars N]
                               kinds: text thinking tool_use tool_result

SESSION is a path to a .jsonl file, or a bare session id resolved against
~/.claude/projects/*/<id>.jsonl.
"""
import argparse
import json
import sys
from pathlib import Path


def resolve(session: str) -> Path:
    p = Path(session)
    if p.is_file():
        return p
    hits = sorted(Path.home().glob(f".claude/projects/*/{session}.jsonl"))
    if not hits:  # subagent transcripts live under <session-id>/subagents/
        hits = sorted(Path.home().glob(
            f".claude/projects/*/*/subagents/{session}.jsonl"))
    if not hits:
        sys.exit(f"no transcript found for {session!r} "
                 f"(looked in ~/.claude/projects/*/ and */subagents/)")
    if len(hits) > 1:
        print(f"note: {len(hits)} matches, using {hits[0]}", file=sys.stderr)
    return hits[0]


def records(path: Path):
    with open(path) as f:
        for i, line in enumerate(f):
            try:
                yield i, json.loads(line), line
            except json.JSONDecodeError:
                yield i, {}, line


def snippet(s: str, n: int = 90) -> str:
    s = " ".join(str(s).split())
    return s[:n] + ("…" if len(s) > n else "")


def anatomy(rec: dict) -> str:
    """One-line structural summary of a record."""
    typ = rec.get("type", "?")
    side = " [sidechain]" if rec.get("isSidechain") else ""
    if typ == "attachment":
        att = rec.get("attachment", {})
        return f"attachment:{att.get('type', '?')}{side}"
    content = rec.get("message", {}).get("content")
    kinds = []
    if isinstance(content, str):
        kinds.append(f'str "{snippet(content, 60)}"')
    elif isinstance(content, list):
        for c in content:
            k = c.get("type", "?")
            if k == "tool_use":
                name = c.get("name", "")
                extra = ""
                if name == "Skill":
                    extra = f"[{c.get('input', {}).get('skill', '')}]"
                elif name in ("Read", "Write", "Edit"):
                    extra = f"[{snippet(c.get('input', {}).get('file_path', ''), 50)}]"
                kinds.append(f"tool_use:{name}{extra}")
            elif k == "text":
                kinds.append(f'text "{snippet(c.get("text", ""), 60)}"')
            elif k == "thinking":
                kinds.append("thinking")
            else:
                kinds.append(k)
    return f"{typ}{side} " + " | ".join(kinds)


def cmd_map(args):
    path = resolve(args.session)
    lines = list(records(path))
    fork = next((r.get("forkedFrom") for _, r, _ in lines
                 if r.get("forkedFrom")), None)
    print(f"# {path} — {len(lines)} records"
          + (f" — forkedFrom {fork.get('sessionId')}" if fork else ""))
    for i, rec, _ in lines:
        print(f"{i:5d}  {anatomy(rec)}")


def strings(obj):
    """Every string leaf in a decoded record, for natural-text matching."""
    if isinstance(obj, str):
        yield obj
    elif isinstance(obj, dict):
        for v in obj.values():
            yield from strings(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from strings(v)


def cmd_grep(args):
    path = resolve(args.session)
    pat = args.pattern.lower() if args.ignore_case else args.pattern
    n = 0
    for i, rec, raw in records(path):
        # match decoded text, not the raw line: in raw JSON a quoted phrase
        # is \"-escaped and never matches
        hay = "\n".join(strings(rec)) or raw
        if args.ignore_case:
            hay = hay.lower()
        if pat in hay:
            print(f"{i:5d}  {anatomy(rec)}")
            n += 1
    print(f"# {n} matching records", file=sys.stderr)


def cmd_show(args):
    path = resolve(args.session)
    want = set(args.kind.split(",")) if args.kind else None
    idxs = set(args.idx)
    seen = set()
    for i, rec, _ in records(path):
        if i not in idxs:
            continue
        seen.add(i)
        print(f"===== record {i}: {anatomy(rec)}")
        if rec.get("type") == "attachment":
            print(snippet(json.dumps(rec.get("attachment")), args.max_chars))
            continue
        content = rec.get("message", {}).get("content")
        if isinstance(content, str):
            print(content[:args.max_chars])
            continue
        for c in content or []:
            k = c.get("type")
            if want and k not in want:
                continue
            print(f"----- {k}")
            if k == "text":
                body = c.get("text", "")
            elif k == "thinking":
                body = c.get("thinking", "")
            elif k == "tool_use":
                body = f"{c.get('name')} {json.dumps(c.get('input'), indent=1)}"
            elif k == "tool_result":
                inner = c.get("content")
                if isinstance(inner, list):
                    body = "\n".join(cc.get("text", "") for cc in inner
                                     if isinstance(cc, dict))
                else:
                    body = str(inner)
            else:
                body = json.dumps(c)
            print(body[:args.max_chars])
            if len(body) > args.max_chars:
                print(f"…[{len(body) - args.max_chars} chars truncated]")
    for i in sorted(idxs - seen):
        print(f"# no record {i} in this transcript", file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    m = sub.add_parser("map", help="session skeleton, one line per record")
    m.add_argument("session")
    m.set_defaults(fn=cmd_map)

    g = sub.add_parser("grep", help="find records containing a pattern")
    g.add_argument("session")
    g.add_argument("pattern")
    g.add_argument("-i", "--ignore-case", action="store_true")
    g.set_defaults(fn=cmd_grep)

    s = sub.add_parser("show", help="dump content blocks of records")
    s.add_argument("session")
    s.add_argument("idx", nargs="+", type=int)
    s.add_argument("--kind", help="comma-separated: text,thinking,tool_use,tool_result")
    s.add_argument("--max-chars", type=int, default=3000)
    s.set_defaults(fn=cmd_show)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
