#!/usr/bin/env python3
"""Which writing-guard signals are allowed to block, and on what evidence.

    python3 tests/writing-guard-fp-validation.py             # the report
    python3 tests/writing-guard-fp-validation.py --write     # + regenerate the
                                                             #   constants block

THE RULE, AND WHY IT IS THIS ONE
--------------------------------
A blocking gate that fires on writing the user accepts is worse than no gate:
it costs the rest of the session and it teaches the writer to distrust it. So a
candidate signal qualifies for blocking only when it fires on NONE of the texts
the user accepted. One false positive disqualifies it to the advisory tier,
where it can inform without stopping anybody.

The accepted texts are in tests/writing-guard-corpus.json, and the set is small
on purpose. Two pre-registered labeling rounds produced 51 answers and only
three trustworthy acceptances: one text rated okay twice on byte-identical
presentation, one rated good, and one pull-request body the user praised in
their own words. A fourth acceptance was removed from the floor after it
flipped okay -> bad on a repeat. `ORCHESTRATION.md` "ROUND-2 RECONCILED
VERDICTS" item 1 fixes the set; this harness does not get to widen it.

WHAT A PASS HERE DOES AND DOES NOT MEAN
---------------------------------------
Zero fires on three texts is a floor, not a false-positive rate. The report
prints, for every signal, how many of those texts it could even apply to: a
title-scoped signal is vacuously quiet on a text with no title, and two of the
three accepted texts have none. Read the applicability column before believing
a qualification.

The bad-side fire rates are descriptive context only. The pre-registration
forbids fitting anything to those labels, and nothing here is fitted: the
qualification rule reads the accepted texts alone, and the bad-side numbers are
printed so a reader can see whether a qualified signal catches anything at all.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
sys.path.insert(0, os.path.join(REPO, 'plugins', 'harness', 'hooks'))

import writing_guard_detectors as D             # noqa: E402

CORPUS = os.path.join(HERE, 'writing-guard-corpus.json')

# The 30 round-1 items the user labelled bad are the user's own prose and stay
# in the initiative tree; this harness reads them when that tree is present and
# says so plainly when it is not.
BAD_SET_ROOT = ('/home/tmrts/workspace/mono-repo/.claude/worktrees/'
                'writing-guard/scratch/2026-08-21-writing-guard/curation')


def signals(item):
    text = D.Text(item['text'], mono_title=item['mono_title'])
    return D.raw_signals(text), text


def applicable(name, text):
    """Can this signal say anything about this text at all?"""
    if name in D.TITLE_SCOPED:
        return text.title is not None and text.title_sentence is not None
    return True


def score(items):
    """{signal: {'fires': [ids], 'applicable': [ids], 'quiet': [ids]}}"""
    out = {n: {'fires': [], 'applicable': [], 'quiet': []}
           for n in D.CANDIDATE_SIGNALS}
    for item in items:
        sig, text = signals(item)
        for name in D.CANDIDATE_SIGNALS:
            row = out[name]
            if applicable(name, text):
                row['applicable'].append(item['id'])
            if sig[name]:
                row['fires'].append(item['id'])
            else:
                row['quiet'].append(item['id'])
    return out


def union_fires(scores, names):
    """The texts at least one of these signals fires on - what a gate built
    from them would actually stop."""
    hit = set()
    for name in names:
        hit.update(scores[name]['fires'])
    return sorted(hit)


def load_bad_set():
    """The round-1 bad items, or None when the initiative tree is absent."""
    items_path = os.path.join(BAD_SET_ROOT, 'round1-items.json')
    labels_path = os.path.join(BAD_SET_ROOT, 'round1-labels.json')
    if not (os.path.exists(items_path) and os.path.exists(labels_path)):
        return None
    with open(items_path, encoding='utf-8') as fh:
        items = {i['id']: i for i in json.load(fh)['items']}
    with open(labels_path, encoding='utf-8') as fh:
        labels = json.load(fh)['answers']
    return [{'id': a['id'], 'text': items[a['id']]['text'],
             'mono_title': bool(items[a['id']]['monospace'])}
            for a in labels if a['label'] == 'bad' and a['id'] in items]


def report():
    with open(CORPUS, encoding='utf-8') as fh:
        corpus = json.load(fh)
    trusted = corpus['okay_set_trusted']
    single = corpus['okay_set_single_measurement']

    trusted_scores = score(trusted)
    single_scores = score(single)
    bad = load_bad_set()
    bad_scores = score(bad) if bad else None

    qualified = tuple(n for n in D.CANDIDATE_SIGNALS
                      if not trusted_scores[n]['fires'])

    lines = []
    add = lines.append
    add('WRITING-GUARD FALSE-POSITIVE VALIDATION')
    add('')
    add('Accepted texts the blocking tier must stay quiet on (%d):' % len(trusted))
    for it in trusted:
        add('  %-12s %-5s %s' % (it['id'], '%dw' % len(it['text'].split()),
                                 '; '.join(it['labels'])))
    add('')
    add('%-46s %-9s %-11s %s' % ('candidate signal', 'verdict',
                                 'applicable', 'fires on'))
    add('-' * 92)
    for name in D.CANDIDATE_SIGNALS:
        row = trusted_scores[name]
        verdict = 'BLOCKING' if not row['fires'] else 'advisory'
        add('%-46s %-9s %2d of %-4d %s'
            % (name, verdict, len(row['applicable']), len(trusted),
               ', '.join(row['fires']) or '-'))
    add('')
    add('Qualified for blocking: %s'
        % (', '.join(qualified) if qualified else 'NONE'))
    add('')
    add('Single-measurement accepted texts (not part of the rule; context only):')
    for name in D.CANDIDATE_SIGNALS:
        row = single_scores[name]
        add('  %-46s applicable %d of %d, fires on %s'
            % (name, len(row['applicable']), len(single),
               ', '.join(row['fires']) or '-'))
    add('')
    if bad_scores is None:
        add('Bad-side fire rates: UNAVAILABLE (the initiative payload is not on '
            'this machine: %s)' % BAD_SET_ROOT)
    else:
        add('Bad-side fire rates over the %d round-1 items the user rejected '
            '(descriptive, never a gate):' % len(bad))
        for name in D.CANDIDATE_SIGNALS:
            row = bad_scores[name]
            add('  %-46s %2d of %2d fire, applicable to %d'
                % (name, len(row['fires']), len(bad), len(row['applicable'])))
        caught = union_fires(bad_scores, qualified)
        add('  %-46s %2d of %2d' % ('ALL QUALIFIED SIGNALS TOGETHER',
                                    len(caught), len(bad)))
        add('  A gate built from the qualified signals stops that many of the '
            'texts the user rejected. The rest pass: this tier is the '
            'worst-offender gate, not the acceptance bar.')
    add('')
    add('Advisory-tier signals, which no result here can promote:')
    for name in D.ADVISORY_ONLY:
        add('  %s' % name)
    return qualified, trusted_scores, single_scores, bad_scores, '\n'.join(lines)


def constants_block(qualified, trusted_scores, bad_scores, trusted, single):
    """The generated tuple, with the evidence that produced it beside it."""
    payload = {}
    for name in D.CANDIDATE_SIGNALS:
        row = trusted_scores[name]
        entry = {
            'tier': 'blocking' if name in qualified else 'advisory',
            'accepted_texts_applicable': len(row['applicable']),
            'accepted_texts_total': len(trusted),
            'fires_on_accepted': row['fires'],
        }
        if bad_scores:
            entry['fires_on_rejected'] = '%d of %d' % (
                len(bad_scores[name]['fires']), len(bad_scores[name]['quiet'])
                + len(bad_scores[name]['fires']))
        payload[name] = entry
    out = ['BLOCKING_SIGNALS = (']
    for name in qualified:
        out.append('    %r,' % name)
    out.append(')')
    out.append('FP_VALIDATION = ' + json.dumps(payload, indent=4,
                                               sort_keys=True))
    return '\n'.join(out)


def write_constants(block):
    path = os.path.join(REPO, 'plugins', 'harness', 'hooks',
                        'writing_guard_detectors.py')
    with open(path, encoding='utf-8') as fh:
        src = fh.read()
    new, n = re.subn(r'(?s)(# BEGIN GENERATED\n).*?(# END GENERATED)',
                     lambda m: m.group(1) + block + '\n' + m.group(2), src)
    if n != 1:
        raise SystemExit('generated block markers not found in %s' % path)
    with open(path, 'w', encoding='utf-8') as fh:
        fh.write(new)
    return path


def main(argv):
    with open(CORPUS, encoding='utf-8') as fh:
        corpus = json.load(fh)
    qualified, trusted_scores, single_scores, bad_scores, text = report()
    print(text)
    if '--write' in argv:
        block = constants_block(qualified, trusted_scores, bad_scores,
                                corpus['okay_set_trusted'],
                                corpus['okay_set_single_measurement'])
        print('\nwrote %s' % write_constants(block))
    elif '--emit-constants' in argv:
        print()
        print(constants_block(qualified, trusted_scores, bad_scores,
                              corpus['okay_set_trusted'],
                              corpus['okay_set_single_measurement']))
    # The harness is also a test: a signal that fires on accepted writing must
    # not be sitting in the shipped blocking tier.
    leaked = [n for n in D.BLOCKING_SIGNALS if trusted_scores.get(n, {}).get('fires')]
    if leaked:
        print('\nFAIL: shipped blocking tier contains signals that fire on '
              'accepted writing: %s' % ', '.join(leaked))
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
