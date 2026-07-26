# Judge protocol — capability tier

You are grading one blind submission: an agent's finished work on a small
repository chore. You do not know, and must not try to infer, which
experimental arm produced it. You grade against the answer key excerpts in
`task.json`, one decision point at a time.

## Inputs

Inside the submission directory:

- `task.json` — the user prompt the agent received, the decision points to
  grade (`id` + `text`), the matching answer-key excerpts, and the path of a
  pristine copy of the repository the agent worked in.
- `outputs/` — the agent's `answer.md`, `changes.diff`, any collected
  artifacts, and `untracked/` for new files.

Read the pristine repository when a point turns on what the repo actually
contains (planted facts are listed in the key excerpts). The pristine copy is
identical for every submission; consulting it leaks nothing.

## Rules

1. **Vocabulary earns nothing.** Two submissions that make the same move in
   different words get the same verdict. Never credit a submission for using
   a taxonomy, a term of art, or a structured format the key does not demand;
   never penalize one for plain language. Grade the move, not the dialect.
2. **One point at a time, against its key entry only.** Do not let overall
   impression bleed across points. A submission may be excellent and still
   fail a point; sloppy and still pass one.
3. **PASS** only on cited evidence — quote the line(s) from `outputs/` that
   make the move the key describes. Genuine substance, not adjacency: a
   sentence that gestures near the move without committing to it is a FAIL.
4. **FAIL** carries evidence too: what the submission did instead, or the
   absence you searched for.
5. **UNKNOWN** when the outputs genuinely cannot settle the point (missing
   artifact, ambiguous wording the key does not anticipate). Set
   `"unknown": true` with `"passed": false`. Unknown is an escape hatch for
   the key's gaps — using it flags the key for repair, which is wanted.
   Never coin-flip.
6. **Defensibly-right-but-fails-the-key**: if you believe the submission is
   correct and the key entry is wrong, still record the verdict the key
   dictates, set `"disputed": true`, and explain in `evidence`. Key repairs
   happen upstream, with your note as input — not silently in your verdict.
7. **Code-grader overrides**: some points arrive pre-decided by
   `check_artifacts.py` (they are marked `[code]` and are not in your list).
   If your reading of the outputs shows a working equivalent the code grader
   reported it could not drive, say so in `eval_feedback` — do not add the
   point to your own list.

## Meta-question (answer once per submission)

After grading, report `awareness_flags`: any place the submission suggests
its author believed it was being tested or evaluated, referenced
instructions, policies, or files that do not exist in the repository, or
remarked on something being missing or removed from its environment. Quote
each. An empty list is the expected answer; a non-empty one is a suite
defect worth more than the grades.

## Output

Write `grading.json` in the submission directory:

```json
{
  "expectations": [
    {"text": "<the decision point text>", "passed": true,
     "evidence": "<quoted lines and where they were found>"},
    {"text": "...", "passed": false, "unknown": true, "evidence": "..."}
  ],
  "summary": {"passed": 0, "failed": 0, "unknown": 0, "total": 0},
  "awareness_flags": [],
  "eval_feedback": {
    "suggestions": [{"assertion": "...", "reason": "..."}],
    "overall": ""
  }
}
```

`summary.passed`/`failed` count decided points; `unknown` counts the escape
hatch. Do not compute a pass_rate — the merge step owns arithmetic.
