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
runs the repository's documented quality commands plus repair-appropriate proof,
and writes one fix log holding everything the commit body needs.

Read `references/repair-proof.md` in full. It is the normative classification
and acceptance contract for the fixer and this workflow.

The raw score is the only threshold input. There are no fix modes, no target
thresholds, and no score-gap targeting.

The fixer ends on one word: `COMPLETE`, `MUTATION_UNPROVEN`, or
`QUALITY_FAILURES`.

## Step 2 — Read the fixer's result

The fixer returns a fix-log path and one terminal word. It never emits a signal:
this workflow returns an outcome, and the orchestrator emits the run's single
terminal signal.

- **`COMPLETE`** — every current finding carries a disposition, the fixer's
  proof duties are complete, and the quality commands passed. Continue to the
  independent text repair verification below.
- **`MUTATION_UNPROVEN`** — fixer-owned proof could not be confirmed. Preserve
  the affected finding IDs and continue to Step 5 without committing.
- **`QUALITY_FAILURES`** — the repository's quality commands still fail and the
  fixer could not resolve them. Commit nothing and return `QUALITY_FAILURES` with
  the failing commands.

  Leave the fixer's edits in the working tree. They are most of a repair, and
  discarding them loses work with no record. State in the final report that the
  tree holds uncommitted changes and name them: a PR/MR re-run reviews the
  platform diff, so those edits are **not** in the next cycle's scope. Commit or
  discard them before re-running.
- **No files changed** — `git status --porcelain` is empty. Nothing is committed
  or pushed, so `PUSH_COMPLETE`, which reports pushed commits, never applies.
  Return `NO_CHANGE` with an empty SHA list and let Step 5 route it.

For `COMPLETE`, invoke `v8ch:repair-proof-reviewer` with the synthesized report,
the fix log, the repository-relative fixer diff, the repository directory, and
the expected text-only finding IDs derived from the fixer's result, the
repository directory, and the absolute skill directory. The role reads the
shared contract and returns an independent verification record. Validate the
complete record against the contract and append it to the fix log. Any invalid
or `PROOF_UNPROVEN` result preserves the affected finding IDs and continues to
Step 5 without committing.

## Step 3 — Commit

Stage the fixer's changes and create one conventional commit directly with
`git`. Do not invoke a commit-composing skill.

A non-zero `git commit` is `ABORT` with `reason` `command_failed`; put the
command and its stderr in `message`. Nothing is pushed.

The commit body records:

- the raw score and the cycle number;
- every finding's disposition;
- the quality commands and their results;
- one mutation check per code or configuration repair;
- the independent text repair verification records, with finding IDs and
  inspected corrections;
- the work-item records the fixer wrote under `## Work Items Required`.

## Step 4 — Push

Verify the current branch equals the PR/MR head ref:

- `github`: `gh pr view <number> --json headRefName -q .headRefName`
- `gitlab`: `glab mr view <number> -F json | jq -r .source_branch`

On a mismatch, `ABORT` with `reason` `branch_mismatch` and do not push. If the
query itself fails, `ABORT` with `reason` `command_failed` and do not push: an
unanswered query is not a matching branch.

Push to an explicit remote and ref rather than relying on the branch's upstream,
which may point at a fork or a stale remote:

```bash
git push origin HEAD:<head-ref>
```

A non-zero push is `ABORT` with `reason` `command_failed`. The commit exists
locally in that case, so name its SHA in `message`; the work is not lost, it is
unpushed.

On success, capture the pushed commit SHAs.

## Step 5 — Return to the orchestrator

Report the outcome, the pushed SHAs (or an empty list), and the work-item
records. The orchestrator routes, in this order — the first match wins, so two
identical runs cannot end on different signals:

1. Caller-declared single-cycle cap on a PR/MR — emit
   `CAPPED_REVIEW_COMPLETE` with this review's URL, score, status, any pushed
   fix commit SHAs, work items, `fixer_outcome`, `failed_commands`, and
   `unproven_findings`. Do not start another review. This signal does not claim
   that a fix commit has been reviewed or that findings closed. A failed proof
   or quality pass has an empty SHA list and carries its details here.
2. The fix log leaves a current finding with no disposition, the fixer returned
   `MUTATION_UNPROVEN`, or independent verification returned `PROOF_UNPROVEN` —
   `BLOCKERS_REMAIN`, naming those findings, whatever the budget allows.
3. Outcome `QUALITY_FAILURES` — `QUALITY_FAILURES` with the failing commands.
4. Budget remaining — start the next review cycle rather than ending the run.
5. Budget exhausted, findings remain `partial` or `work-item-required` —
   `BLOCKERS_REMAIN`.
6. Budget exhausted, commits were pushed, no `clean` review — `PUSH_COMPLETE`.
7. Budget exhausted, nothing was committed (outcome `NO_CHANGE`) —
   `MAX_REVIEWS_REACHED`. `PUSH_COMPLETE` reports pushed commits and never
   applies here.

## Work items

This skill never creates tracking items. It carries the fixer's work-item
records into the commit body and into the terminal signal's `work_items` list,
and stops there.
