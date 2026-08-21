"""PreToolUse gate: prose the reader cannot follow does not get published.

Two surfaces, one judgment. An Artifact publish is linted from the file at
rest; a `git commit` is linted from the message inside the command. The
mechanisms and their tiers live in writing_guard_detectors.py; this file is the
plumbing - payload in, decision out, attempts counted, bypasses recorded.

THREE RULES THIS FILE EXISTS TO KEEP
------------------------------------
1. It never says which words failed. A writer handed the failing span edits
   that span, which buys compliance with the detector and nothing for the
   reader. So a denial carries the principle, the target, and a pointer to the
   writing-guard skill by the name the platform loads it under.
2. It blocks twice and then gets out of the way. A gate that can stall a
   session indefinitely is a gate people disable. The third attempt at the same
   text passes, tells the user, and appends the whole text to a log they can
   read.
3. It fails open, loudly. Every internal error exits 0 with a marker line on
   stderr, because a silently broken gate is worse than no gate: it replaces
   the vigilance it automated.
"""
import hashlib
import json
import os
import re
import shlex
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

MARKER = 'HARNESS-WRITING-GUARD-FAIL-OPEN'
MAX_BYTES = 400000          # a page bigger than this is not prose being judged
ATTEMPT_TTL = 6 * 3600      # an attempt chain older than this is a new chain
MAX_ENTRIES = 200
BLOCKS_ALLOWED = 2          # then the writer gets through
SHINGLE = 3                 # words per shingle in the near-duplicate test
SKETCH_K = 64
SAME_TEXT_JACCARD = 0.45    # below this, a retry is a different subject

GIT_COMMIT = re.compile(r'\bgit\b[^|;&]*\bcommit\b')
UNEXPANDED = ('$(', '`', '${')


# ------------------------------------------------------------------ surfaces
def artifact_subject(tool_input):
    """The file an Artifact publish would render, or None to stay silent."""
    action = tool_input.get('action')
    if action is not None and action != 'publish':
        return None                      # listing, commenting, assets: not prose
    path = tool_input.get('file_path')
    if not path or not os.path.isfile(path):
        return None
    try:
        with open(path, encoding='utf-8', errors='replace') as fh:
            src = fh.read(MAX_BYTES)
    except OSError:
        return None
    if not src.strip():
        return None
    return {'text': src, 'mono_title': False,
            'is_html': path.lower().endswith(('.html', '.htm')),
            'surface': 'Artifact publish'}


OPERATORS = ('&&', '||', ';', '|', '&')


def _commit_argv(command):
    """The `git commit ...` words of a command line, or None.

    Tokenizing the whole line and then splitting at shell operators is what
    keeps a multi-line message intact. A commit message is quoted, so its blank
    lines and body sit inside one argument; splitting the raw command string on
    newlines - the obvious cheap move - would cut that body away from the flag
    that carries it, and the gate would judge a subject line alone.
    """
    try:
        argv = shlex.split(command)
    except ValueError:
        return None                      # unbalanced quotes: not ours to guess
    segments, cur = [], []
    for token in argv:
        if token in OPERATORS:
            segments.append(cur)
            cur = []
        else:
            cur.append(token)
    segments.append(cur)
    for seg in segments:
        if 'git' in seg and 'commit' in seg \
                and seg.index('commit') > seg.index('git'):
            return seg
    return None


def commit_message(command, cwd):
    """The message a `git commit` would write, or None when it is not visible.

    Silence is the right answer for a message the gate cannot read: a heredoc,
    a command substitution, an --amend that reuses the old message. The
    PostToolUse commit-shape gate still sees the commit afterwards; this gate
    only judges what it can read before the fact.
    """
    if not GIT_COMMIT.search(command):
        return None
    argv = _commit_argv(command)
    if argv is None:
        return None
    parts, i = [], 0
    while i < len(argv):
        a = argv[i]
        value = kind = None
        if a in ('-m', '--message'):
            kind, value = 'text', argv[i + 1] if i + 1 < len(argv) else None
            i += 1
        elif a.startswith('--message='):
            kind, value = 'text', a.split('=', 1)[1]
        elif a.startswith('-m') and len(a) > 2 and not a.startswith('--'):
            kind, value = 'text', a[2:]
        elif a in ('-F', '--file'):
            kind, value = 'file', argv[i + 1] if i + 1 < len(argv) else None
            i += 1
        elif a.startswith('--file='):
            kind, value = 'file', a.split('=', 1)[1]
        elif re.match(r'^-[a-zA-Z]+$', a) and a.endswith('m') and len(a) > 2:
            kind, value = 'text', argv[i + 1] if i + 1 < len(argv) else None
            i += 1
        i += 1
        if kind is None:
            continue
        if value is None or any(s in value for s in UNEXPANDED):
            return None                  # the shell would expand it; we cannot
        if kind == 'file':
            path = value if os.path.isabs(value) else os.path.join(cwd, value)
            try:
                with open(path, encoding='utf-8', errors='replace') as fh:
                    value = fh.read(MAX_BYTES)
            except OSError:
                return None
        parts.append(value)
    message = '\n\n'.join(p for p in parts if p.strip())
    if not message.strip():
        return None
    return {'text': message, 'mono_title': True, 'is_html': False,
            'surface': 'git commit message'}


# ------------------------------------------------- attempt chains, by content
# An author told their opening is unreadable rewords it and tries again, so the
# text of attempt two is never byte-identical to attempt one. Counting exact
# hashes would therefore hand out blocks without end. The chain is keyed by
# near-duplication instead: word-triple shingles, a bottom-k sketch so the
# state file stays small, and a Jaccard estimate over the two sketches.
def _sketch(text):
    words = re.findall(r'[a-z0-9]+', text.lower())
    if len(words) < SHINGLE:
        words = words or ['']
        shingles = {' '.join(words)}
    else:
        shingles = {' '.join(words[i:i + SHINGLE])
                    for i in range(len(words) - SHINGLE + 1)}
    hashes = sorted(int(hashlib.md5(s.encode('utf-8')).hexdigest()[:12], 16)
                    for s in shingles)
    return hashes[:SKETCH_K]


def _jaccard(a, b):
    """Bottom-k estimate: of the k smallest hashes either sketch knows, how
    many are in both."""
    if not a or not b:
        return 0.0
    union = sorted(set(a) | set(b))[:SKETCH_K]
    if not union:
        return 0.0
    both = set(a) & set(b)
    return sum(1 for h in union if h in both) / float(len(union))


def _state_path():
    base = os.environ.get('CLAUDE_PLUGIN_DATA') or os.environ.get('TMPDIR') \
        or '/tmp'
    try:
        os.makedirs(base, exist_ok=True)
    except OSError:
        base = '/tmp'
    return os.path.join(base, 'writing-guard-attempts.json')


def record_attempt(text):
    """How many times this text - or a near-duplicate - has been blocked, now
    including this one."""
    path, now = _state_path(), time.time()
    entries = []
    try:
        with open(path, encoding='utf-8') as fh:
            entries = json.load(fh).get('entries', [])
    except (OSError, ValueError):
        entries = []
    entries = [e for e in entries if now - e.get('last', 0) < ATTEMPT_TTL]

    sketch = _sketch(text)
    digest = hashlib.sha256(text.encode('utf-8')).hexdigest()[:16]
    for e in entries:
        if _jaccard(sketch, e.get('sketch', [])) >= SAME_TEXT_JACCARD:
            e['count'] += 1
            e['last'] = now
            e['sketch'] = sketch          # follow the text as it is reworded
            count = e['count']
            break
    else:
        entries.append({'hash': digest, 'sketch': sketch, 'count': 1,
                        'last': now})
        count = 1

    entries = sorted(entries, key=lambda e: e['last'])[-MAX_ENTRIES:]
    tmp = path + '.%d' % os.getpid()
    try:
        with open(tmp, 'w', encoding='utf-8') as fh:
            json.dump({'version': 1, 'entries': entries}, fh)
        os.replace(tmp, path)
    except OSError:
        pass                              # a lost count costs one extra block
    return count, digest


def bypass_log_path():
    base = os.environ.get('CLAUDE_CONFIG_DIR') \
        or os.path.join(os.path.expanduser('~'), '.claude')
    return os.path.join(base, 'writing-guard-bypass.jsonl')


def record_bypass(entry):
    path = bypass_log_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, 'a', encoding='utf-8') as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + '\n')
    except OSError:
        pass


# -------------------------------------------------------------------- output
def deny(reason):
    print(json.dumps({'hookSpecificOutput': {
        'hookEventName': 'PreToolUse',
        'permissionDecision': 'deny',
        'permissionDecisionReason': reason}}))


def advise(message):
    # PreToolUse has no channel that injects context into the model (the event
    # takes permissionDecision and permissionDecisionReason only), and deciding
    # "allow" here would auto-approve a tool call the user's own permission
    # rules might otherwise ask about. So the third attempt decides nothing and
    # tells the human instead, which is what systemMessage is for.
    print(json.dumps({'systemMessage': message}))


def main():
    if os.environ.get('HARNESS_WRITING_GUARD_DISABLE'):
        return 0
    payload = json.load(sys.stdin)
    tool = payload.get('tool_name')
    tool_input = payload.get('tool_input') or {}
    cwd = payload.get('cwd') or os.getcwd()

    # The matcher is re-checked here: hooks.json routes two matchers into this
    # one script, and a settings file elsewhere could route a third.
    if tool == 'Artifact':
        subject = artifact_subject(tool_input)
    elif tool == 'Bash':
        subject = commit_message(tool_input.get('command', ''), cwd)
    else:
        return 0
    if subject is None:
        return 0

    # Imported here, not at the top: the Bash matcher fires on every command in
    # the session, and building the detectors' head-boundary pattern costs more
    # than deciding that `ls -la` is not a commit message.
    import writing_guard_detectors as D

    verdict = D.analyze(subject['text'], mono_title=subject['mono_title'],
                        is_html=subject['is_html'])
    if not verdict['blocking']:
        return 0

    count, digest = record_attempt(subject['text'])
    if count <= BLOCKS_ALLOWED:
        deny('%s\nThis is attempt %d. The guard stops this text %d times, then '
             'stands aside and records it for the user to read.'
             % (D.deny_message(verdict['blocking']), count, BLOCKS_ALLOWED))
        return 0

    record_bypass({
        'timestamp': time.strftime('%Y-%m-%dT%H:%M:%S%z'),
        'tool': tool,
        'surface': subject['surface'],
        'hash': digest,
        'attempts': count,
        'verdicts': {'blocking': verdict['blocking'],
                     'advisory': verdict['advisory']},
        'text': subject['text'],
    })
    advise('The writing guard has already objected twice to this text and is '
           'standing aside. What it objects to and the text itself are in %s.'
           % bypass_log_path())
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except Exception as exc:                                  # noqa: BLE001
        # Loud, single-line, and greppable: a gate that breaks quietly is a
        # gate everyone keeps trusting.
        sys.stderr.write('%s: %s: %s\n'
                         % (MARKER, type(exc).__name__, str(exc)[:200]))
        sys.exit(0)
