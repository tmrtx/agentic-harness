---
name: review-pr
description: Review a pull request for harness governance-control violations and publish each as a review comment
disable-model-invocation: true
---

Your objective is to ensure that the changes don't cause violations of **$ARGUMENTS**
within the context of the whole repository (not just the code adjacent to the PR).

Start by researching the context and the background for the PR — from the PR text
and its commits only; reading the comments or discussion threads would bias the
review.

Then have the `reviewer` subagent review the changes and filter its findings
down to the violations of **$ARGUMENTS** — the reviewer's coverage is fixed
by its committed definition, so directives outside it surface nothing.

Finally, point out each violation as inline review comments (each well-written
in markdown and referencing the violated directive by canonical code). Don't
make recommendations, just focus on the problem and trust the reader's
intelligence and autonomy. Don't write a verbose reply; if there are no
violations -> no need to write anything. Don't prefilter, or preprocess the
priorities of violations; trust the reader, convey the problem and let them do
with it what they want (e.g. no "minor"/"major" labeling — drop the reviewer's
severities).
