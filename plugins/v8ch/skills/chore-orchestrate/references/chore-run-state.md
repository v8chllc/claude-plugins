# Chore run-state overlay

Use the vendored `run-state.md` for run home, corrective runs, scratch, coordination markers, PR bodies, relay persistence, snapshots and retrospectives. This overlay changes only fields and procedures that depend on the five declared reductions. It never changes the shared contract for other skills.

## Record shape

Use the shared `orchestration-record` and `orchestration-snapshot` markers with required `workflow: "chore-orchestrate"`, run ID prefix `chore`, heading word `Chore`, and the phases in `SKILL.md`. In every complete coordination record set `plan: null` and `plan_accepted: null`: no plan comment is posted and no plan acceptance occurs. Omit `additional_review` because its exception does not apply here. Add top-level `not_applicable_stage: null` until `NOT_APPLICABLE`, then set exactly `never_started` or `abandoned_mid_run`. Add per-repository `check_comment: null` until the check agent posts a final-head table, then set its URL. Never omit or reset these fields on a later record. The shared `review_invocations`, `relays`, `deferred`, repository identities, and profile-source fields retain their meanings.

`never_started` means eligibility rejected the item before a branch was created. `abandoned_mid_run` means the run began and later discovered that more assurance was needed; preserve any partial work on its branch. A `NOT_APPLICABLE` record and terminal snapshot name `change-set-orchestrate` as the next workflow and carry the stage. No `NOT_APPLICABLE` path silently changes phase to a full-assurance workflow.

## Review invocation preparation

The shared review invocation gate applies, except its plan-comment lookup is replaced. Before counting an invocation, validate the PR's current head equals local `HEAD`, the remaining budget, the unchanged canonical deferred membership, and the current issue bodies. Under `consensus-review`, when `work_item` is non-null, materialize both issue bodies verbatim in a readable scratch file, with their URLs as provenance and `plan_source` `supplied: <run issue URL> + <repository issue URL>`. When `work_item` is null because `tracking` is `none`, materialize only the run issue body and use `plan_source` `supplied: <run issue URL>`. Read the issue bodies fresh when preparing each review invocation.
Under `consensus-review`, increase `review_invocations` by one only after preparation succeeds, append a complete record, and read it back before dispatch. A failed post never launches review. If dispatch after a confirmed charge is uncertain, ask the sponsor; never silently decrement. If the sponsor confirms it never launched, redo the read-only preparation and resume that charged invocation. At most two invocations per repository; no sponsor-approved third invocation or supervisor-authorized extra cycle. Internal review-and-fix cycles do not increment the invocation count. This hard cap overrides the shared `run-state.md` example that offers sponsor approval for an additional invocation. A new head pushed after the third internal review remains pending; if the second invocation is spent, stop `BLOCKED` rather than dispatching another review.

## Proof identity and snapshot

The check agent posts the `final-head-check.md` table from a file and returns its URL; the manager links it in the record and reads it back. A failed post stops `BLOCKED` and the manager posts no replacement. A complete current-head check comment URL is the repository's `check_comment`; the snapshot's `verification_comment` is exactly that full comment URL. Never infer identity from the newest comment. A correction at a moved head posts a new full table and replaces only the URL in the next complete record. Each check covers every criterion, guard and quality command at the current full SHA in a clean worktree. There is a dedicated check-agent dispatch, but no judging verifier, audit or recovery.

The terminal snapshot otherwise follows `run-state.md`. For `NOT_APPLICABLE`, add `not_applicable_stage` and `next_workflow: change-set-orchestrate` to the snapshot JSON; the visible line names the same route. Do not invent a PR or proof URL if work never started.

## Agent tooling review accounting

The shared loop is `agent-tooling-review-loop.md`. Chore replaces the shared
run-state plan-comment lookup with the issue-body preparation above: materialize
both issue bodies verbatim, or only the run issue when tracking is none, with
URLs and `plan_source`. Keep `plan: null`; the readable scratch
file is review context, not a plan comment. Clean it up after review.

Charge and read back one complete record before dispatch. One invocation runs
up to three single-cycle reviews with retained-builder corrections. Persist
cycle identities and report/disposition links in coordination commentary. If
launch is uncertain, follow the shared sponsor-reconciliation rule.
Chore permits at most two invocations; neither a sponsor-approved third
invocation nor a supervisor-authorized extra cycle applies.
