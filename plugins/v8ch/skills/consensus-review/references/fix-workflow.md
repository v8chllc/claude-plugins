# Fix Workflow

Repairs the findings from one review cycle, validates the result with the
repository's own quality commands, commits directly with `git`, and pushes to the
PR/MR head branch.

This workflow is PR/MR-only. A local review never fixes. It runs when the
synthesized status is `passing` or `failing`; a `clean` review skips it.

Fix evidence lives in the commit body. No fix-validation comment is posted, and
no other skill is invoked.

## Step 1 — Invoke the fixer

Invoke `v8ch:consensus-review-fixer` with:

- the synthesized report for the current cycle;
- `RECOVERED_CONTEXT`;
- the cycle number;
- the scratch directory for the fix log;
- the repository directory and the absolute skill directory.

The fixer gives every current finding exactly one disposition — `fixed`,
`declined`, `partial`, or `work-item-required` — applies the in-scope changes,
runs the repository's documented quality commands plus a mutation check per fix,
and writes one fix log holding everything the commit body needs.

The raw score is the only threshold input. There are no fix modes, no target
thresholds, and no score-gap targeting.

## Step 2 — Read the fixer's result

- **Fix log written, no quality failures** — continue to Step 3.
- **`QUALITY_FAILURES`** — the repository's quality commands still fail and the
  fixer could not resolve them. Commit nothing. Emit `QUALITY_FAILURES` with the
  score, the review URL, and the failing commands, then stop.

  Leave the fixer's edits in the working tree. They are most of a repair, and
  discarding them loses work with no record. Say in the final report that the
  tree holds uncommitted changes, because the next invocation's default scope is
  `git diff HEAD` and will review them as local work.
- **No files changed** — `git status --porcelain` is empty. There is nothing to
  commit or push; go straight to the terminal signal for the cycle.

## Step 3 — Commit

Stage the fixer's changes and create one conventional commit directly with
`git`. Do not invoke a commit-composing skill.

The commit body records:

- the raw score and the cycle number;
- every finding's disposition;
- the quality commands and their results;
- one mutation check per fix;
- the work-item records the fixer wrote under `## Work Items Required`.

## Step 4 — Push

Verify the current branch equals the PR/MR head ref:

- `github`: `gh pr view <number> --json headRefName -q .headRefName`
- `gitlab`: `glab mr view <number> -F json | jq -r .source_branch`

On a mismatch, emit `ABORT` with `reason` `branch_mismatch` and do not push.

Otherwise run `git push` and capture the pushed commit SHAs.

## Step 5 — Return to the orchestrator

Report the pushed SHAs and the work-item records, then let the orchestrator
decide the next step against its three-review budget:

- Budget remaining — start the next review cycle.
- Budget exhausted, findings remain `partial` or `work-item-required` — emit
  `BLOCKERS_REMAIN`.
- The fix log leaves a current finding with no disposition — the pass was
  incomplete. Commit whatever landed, then emit `BLOCKERS_REMAIN` naming that
  finding, whatever the budget allows.
- Budget exhausted, nothing outstanding but no `clean` review — emit
  `PUSH_COMPLETE`.

## Work items

This skill never creates tracking items. It carries the fixer's work-item
records into the commit body and into the terminal signal's `work_items` list,
and stops there.
