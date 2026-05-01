# Fix Workflow

Applies targeted fixes, posts fix-validation audit comments, runs code-quality tooling, composes commits, and pushes the PR/MR branch after a consensus review cycle.

**Prerequisite:** this workflow is PR/MR-only. A PR or MR number must be present. The latest review, prior fix validations, acceptances, and opt-ins are recovered from PR/MR comments with `recover_context.py`; the active session does not need to contain the current review text. Local reviews do not have a durable audit trail and cannot use this workflow.

Run sub-steps 0 through 8 in order. The PR/MR thread is the durable source of truth. Temporary files may be created in a scratch directory only to pass comment-sourced review/fix text into scripts and agents.

## Step 0 — Resolve latest-cycle artifacts from comments

Create or choose a scratch directory, then run:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/recover_context.py <number> --repo-dir <repo-root> --scratch-dir <scratch-dir> --json-summary
```

The script fetches PR/MR comments, selects the latest consensus-review cycle, writes disposable scratch files from comment bodies, and prints a machine-readable resolver summary. Keep:
- `RESOLVER_SUMMARY` — the printed JSON summary, including source comment URLs, accepted findings, current-cycle additional acceptances, current-cycle low-confidence opt-ins, and cycle gaps.
- `CURRENT_REVIEW_FILE` — `scratch_paths.latest_review` from the summary. If absent, stop and report that no consensus-review comment exists for this PR/MR.
- `CURRENT_FIX_FILE` — `scratch_paths.latest_fix_validation` when present. If absent, continue and surface the missing fix-validation as a cycle gap.
- `RECOVERED_CONTEXT` — the markdown context from `recover_context.py` without `--json-summary`, if a downstream agent needs human-readable history.

The scratch review and fix files are regenerated from PR/MR comments and are not durable audit records. If the active session also has the latest review text, it may be used only as an explicitly scratch fast path when it matches the recovered latest cycle.

## Step 1 — Fix-start additional acceptance

If `AUTONOMOUS=true`, skip this step entirely. Per spec, additional acceptance is not offered in autonomous mode — the autonomous opt-in/acceptance choices were already made in the review skill's Step 5 (and surfaced via the recommendations comment).

Before invoking the fixer, give the operator one more chance to defer findings.

1. Use `CURRENT_REVIEW_FILE`, regenerated from the latest review comment.
2. Use `RESOLVER_SUMMARY` and `RECOVERED_CONTEXT` to identify findings already accepted in PR/MR comments, including current-cycle additional acceptances if a previous fix attempt already posted them.
3. From the current review, list the **unaccepted** must-fix and should-fix findings.
4. If there are no unaccepted findings, skip to Step 2.
5. Present the unaccepted findings and ask: "Accept additional findings before running the fixer? (yes/no/select)"
   - **yes** — accept all listed unaccepted findings
   - **no** — proceed to Step 2 without changes
   - **select** — operator specifies which findings to accept by number
6. On accept, invoke `consensus-review-poster` to post an additional acceptance comment. Pass:
   - comment type: `additional_acceptance`
   - only the newly accepted findings
   - prior adjusted score
   - new adjusted score
   - PR/MR number
   - cycle number
   - repo dir, skill dir, and scratch directory

Do not write or update an `accepted-*.md` file. The additional-acceptance PR/MR comment is the durable record.

## Step 2 — Low-confidence opt-in

Give the operator an explicit opt-in to fix low-confidence findings that the fixer would otherwise skip.

**Interactive (`AUTONOMOUS=false`):**

1. Use `CURRENT_REVIEW_FILE` and extract entries from the **Low-Confidence Findings — Informational** section.
2. Use current-cycle acceptance choices from Step 1 and accepted findings from `RESOLVER_SUMMARY`/`RECOVERED_CONTEXT` to remove accepted findings.
3. If no unaccepted low-confidence findings remain, skip to Step 3.
4. Present the unaccepted low-confidence findings and ask: "Fix any of these low-confidence findings? (yes/no/select)"
   - **yes** — opt in to every listed finding
   - **no** — proceed without opting in any
   - **select** — operator specifies which findings to opt in by number
5. Record the opted-in titles as `OPTED_IN_LOW_CONF` for Step 3.
6. If `OPTED_IN_LOW_CONF` is non-empty, invoke `consensus-review-poster` to post a low-confidence opt-in comment. Pass:
   - comment type: `low_confidence_opt_in`
   - the opted-in low-confidence findings
   - PR/MR number
   - cycle number
   - repo dir, skill dir, and scratch directory

Always prompt fresh each cycle. Historical opt-ins in `RECOVERED_CONTEXT` are informational only and must not be carried over automatically.

**Autonomous (`AUTONOMOUS=true`):**

Do not prompt. Read `current_cycle_opt_in_recommendations` from the recommendations comment surfaced via `recover_context.py` (the `RESOLVER_SUMMARY` exposes this list, and the scratch file `opt-in-recommendations-{cycle:02d}.md` contains the full text).

1. Treat that list as `OPTED_IN_LOW_CONF` for Step 3.
2. If `OPTED_IN_LOW_CONF` is non-empty, invoke `consensus-review-poster` to post a `low_confidence_opt_in` comment with those items. Pass:
   - comment type: `low_confidence_opt_in`
   - the opted-in low-confidence findings (from the recommender)
   - PR/MR number
   - cycle number
   - repo dir, skill dir, and scratch directory
3. If the recommender list is empty, skip posting and proceed with an empty `OPTED_IN_LOW_CONF`.

Historical opt-ins from earlier cycles in `RECOVERED_CONTEXT` are informational only and are not carried over.

## Step 3 — Invoke fixer

Invoke `consensus-review-fixer` with:
- `CURRENT_REVIEW_FILE`, the scratch review file regenerated from PR/MR comments
- Full `RESOLVER_SUMMARY` and `RECOVERED_CONTEXT` from PR/MR comments
- Cycle number: `CYCLE`
- Scratch directory for the temporary fix log
- Target threshold: 85 (passing) — or 95 if user explicitly requests "clean" target
- Opted-in low-confidence finding titles: `OPTED_IN_LOW_CONF` plus any current-cycle opt-ins recovered in `RESOLVER_SUMMARY` (possibly empty)

The fixer owns the full Target Thresholds specification and the Score-Gap Targeting Strategy — see `plugins/vault/agents/consensus-review-fixer.md` for the authoritative description of both behaviors. To target clean, explicitly pass `target_threshold: 95` to the fixer.

## Step 4 — Read fixer signal

- `ALL_RESOLVED` → all targeted findings fixed, proceed
- `THRESHOLD_REACHED` → score target met, some findings deferred, proceed
- `BLOCKERS_REMAIN` → guardrailed findings unresolved; surface them explicitly and recommend running the next review cycle (`/consensus-review` again). Do NOT re-invoke the fixer. Continue to Steps 5–8 so any partial fixes that did land are still committed.

In autonomous mode (`AUTONOMOUS=true`), additionally emit the `BLOCKERS_REMAIN` exit signal block before continuing to Step 5. Use the same fenced `consensus-review-signal` JSON block format documented in the SKILL.md "Exit signals" appendix. Include the unresolved finding titles in `details` (for example: `{"signal": "BLOCKERS_REMAIN", "cycle": N, "details": {"unresolved": ["title-a", "title-b"]}}`). Continuing to Steps 5–8 still applies — partial fixes are committed and the autonomous run also emits a final `PUSH_COMPLETE` (or `ABORT`) signal in Step 8 in the usual way.

## Step 5 — Post fix validation

Invoke `consensus-review-poster` with:
- Comment type: `fix_validation`
- The fix log text returned by the fixer, or the scratch fix-log file written by the fixer
- PR/MR number
- Cycle number
- Repo dir, skill dir, and scratch directory

The poster writes any summary scratch file it needs and calls `post_review_comment.py`. The posted PR/MR comment is the durable fix-validation audit artifact.

## Step 6 — Run code quality tools

Guard: run only if the fixer modified files. Check with `git status --porcelain`; if empty, skip Steps 6–8.

Invoke the `code-quality` skill (runs mypy, ruff lint/format, and pytest, fixing failures until all checks pass).

### `on_quality_failure` policy

This step has a configurable failure policy with default `continue`. Behavior:

- **Interactive (`AUTONOMOUS=false`):** the policy is ignored. Current behavior is preserved — if `code-quality` cannot resolve all issues, record the failure and continue. Step 7 still commits what is clean, and the unresolved tooling issues are surfaced to the operator at the end of the run.

- **Autonomous (`AUTONOMOUS=true`):** read the policy from the trigger phrase (see the SKILL.md mode-detection appendix for the `on_quality_failure: abort` token). If the trigger does not specify a policy, default to `continue`.
  - **`continue` (default):** record `code-quality` failures, proceed to Steps 7 and 8, and append the `QUALITY_FAILURES` signal block to the final output alongside the run's terminal signal (`PUSH_COMPLETE` or `BLOCKERS_REMAIN`). Both signal blocks are emitted in Step 8 — `QUALITY_FAILURES` first, then the terminal signal.
  - **`abort`:** record `code-quality` failures, skip Steps 7 and 8 entirely, and emit only the `ABORT` signal block. No commit, no push. Include the failure summary in `details` (for example: `{"signal": "ABORT", "cycle": N, "details": {"reason": "quality_failures", "tools": ["mypy", "pytest"]}}`).

## Step 7 — Compose commits

Guard: run only if there are changes to commit (`git status --porcelain` non-empty).

Invoke the `git-ops` skill to group the applied fixes into conventional commits. If Step 6 surfaced unresolved tooling failures, still commit the clean changes — do not abort.

## Step 8 — Push commits to the PR branch

Guard: run only if Step 7 created commits.

1. Verify the current branch matches the PR head ref:
   - `github`: `gh pr view {number} --json headRefName -q .headRefName`
   - `gitlab`: `glab mr view {number} -F json | jq -r .source_branch`

   If the current branch does not match, stop and report the mismatch — do not push. In autonomous mode (`AUTONOMOUS=true`), additionally emit the `ABORT` exit signal block with `details.reason="branch_mismatch"` (for example: `{"signal": "ABORT", "cycle": N, "details": {"reason": "branch_mismatch", "expected": "<head-ref>", "actual": "<current-branch>"}}`).

2. Push to origin: `git push`.

3. Report the pushed commit SHAs and the PR/MR URL.

If Step 6 surfaced unresolved `code-quality` failures, re-surface them now alongside the push report so the operator knows follow-up is required.

In autonomous mode (`AUTONOMOUS=true`), emit terminal signal blocks as the final output:

- On a successful push, emit `PUSH_COMPLETE` with the pushed commit SHAs in `details` (for example: `{"signal": "PUSH_COMPLETE", "cycle": N, "details": {"shas": ["abc123", "def456"], "url": "<pr-or-mr-url>"}}`).
- If the fixer reported `BLOCKERS_REMAIN` in Step 4, emit the `BLOCKERS_REMAIN` signal here as the terminal signal instead of `PUSH_COMPLETE` (the partial fixes that landed are still pushed; the cycle ends without a clean push).
- If Step 6 recorded `code-quality` failures under the `continue` policy, also emit a `QUALITY_FAILURES` signal block before the terminal signal. Order: `QUALITY_FAILURES` first, then `PUSH_COMPLETE` (or `BLOCKERS_REMAIN`).
