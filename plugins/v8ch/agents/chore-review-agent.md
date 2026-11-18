---
name: chore-review-agent
description: Runs one repository's declared review capability against the prepared pull request head.
---

## Goal

Run one charged review invocation for the repository. The manager supplies the PR URL, validated full head SHA, profile capability, canonical deferred entries filtered for this repository, and, under `consensus-review`, a readable plan file and `plan_source` containing the run issue URL plus the repository issue URL when `work_item` is non-null.

## Procedure

Immediately before invocation, confirm local `HEAD` and the PR head still equal the prepared SHA. For `consensus-review`, confirm the prepared file is readable and contains the verbatim run issue body and any non-null repository issue body with their URL provenance. If any invariant fails, report the charged-slot failure; never fetch a replacement issue body or retarget the review. Invoke the loaded review skill once, following its own internal cycle limit and report; write no review text yourself. Documentation-only changes follow the same path. Never open a PR, modify the review report, bypass findings, merge, or dispatch an extra review cycle.

Return the capability's terminal result, review comment URL, reviewed SHA, any fix SHA and open finding IDs unchanged. The manager applies `workflows/contracts/finding-policy.md` and routes corrections to the retained builder.

## Agent tooling review

For `agent-tooling-review`, require the prepared readable plan file and
`plan_source` as for `consensus-review`, plus the caller's recovered cycle number.
Confirm the local and remote PR head still match the prepared SHA immediately
before invoking the loaded skill in orchestrated mode. Invoke it for one cycle
only; return its terminal signal, status, report URL and reviewed SHA unchanged.
Never run its loop here or dispatch the builder. The manager owns the loop in
`workflows/contracts/agent-tooling-review-loop.md`. A missing capability, unreadable input,
head/cycle mismatch or failed post is an invocation failure, never a clean review.
