---
name: chore-orchestrate
argument-hint: <run issue URL>
description: Delivers a settled, mechanically checkable chore across any number of repositories under one run issue, through reviewed, open pull requests and check-agent tables at their final heads.
---

# Chore Orchestrate

## Goal

Deliver a settled chore whose acceptance criteria can each be checked by a command at the pull request head. The run issue and repository sub-issues define the work. One retained builder per repository implements it, the declared review capability reviews it, and a dedicated check agent publishes final-head checks. Leave open pull requests for the sponsor to merge.

## Reductions relative to `change-set-orchestrate`

1. No plan agent, plan comment, or plan acceptance. The run issue and its sub-issues are the plan.
2. No judging verifier. A dedicated check agent runs the final-head table without judging claims.
3. At most two review invocations per repository, with no supervisor-authorized extra cycle.
4. No builder removal or inversion proof per criterion. The criterion check run at the final head is the proof.

These are the only process reductions. All repository requirements, the safety list, authority limits, tracking, regression guards, review finding policy, publication rules, and required gates of `change-set-orchestrate` remain in force. Documentation-only pull requests receive the same review as any other change; there is no exemption.

## Inputs and prerequisites

At resolve, reject `review_capability: coderabbit` with `DEPENDENCY_MISSING` before creating a branch.

- A sponsor-created run issue in the resolved coordination repository, with repository issues as sub-issues where tracking is required. Its acceptance criteria and the sub-issues are the plan. Use `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md` and its chore overlay `${CLAUDE_SKILL_DIR}/references/chore-run-state.md`.
- Resolve each profile field from the repository profile, then the workspace named child block, then the workspace default child block, then `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/repository-profile.md` field defaults. Record each field's source and the baseline commit. Read the default branch, local changes, repository instructions, and current issue text before creating a branch.
- `git` and authenticated `gh`; writable clean checkouts on their default branches, or the continued clean branch for a declared corrective run. Check review capability at resolve, before a branch: Claude `v8ch:consensus-review` version 2.0.8 or later, invoked through the Skill tool. A missing capability stops `DEPENDENCY_MISSING`. Under `agent-tooling-review`, require the loaded skill with orchestrated-mode support and its bundled poster/recovery helper; its absence stops `DEPENDENCY_MISSING`.

## Constraints and authority

Safe actions, taken without asking: reading any file, running the profile's quality commands, running non-destructive git commands, creating branches and commits, pushing a working branch, opening a pull request, commenting on the run issue or a pull request, and moving the run issue's board status. Creating, editing, or closing an issue is not among them: the sponsor creates the run issue and every repository issue, and a run that needs one stops rather than creating it.

Actions requiring the sponsor: adding a repository to the run, taking work outside the issue-defined plan, resolving a merge conflict the acceptance criteria do not settle, and any action the profile marks `checkpointed`. Under `checkpointed`, get sponsor approval of the issue-defined scope before implementation; this is no plan acceptance.

**The review budget is at most two review invocations per repository, with no extra cycle or sponsor-approved third invocation.** Under `consensus-review`, one invocation is one call of the review skill, including its internal review-and-fix cycles. Under `agent-tooling-review`, one invocation is one pass of `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/agent-tooling-review-loop.md`, with up to three single-cycle reviews and retained-builder fixes. A lower repository cap binds first. A corrective run has its own budget. Charge and persist invocations as `${CLAUDE_SKILL_DIR}/references/chore-run-state.md` says. An exhausted budget cannot be reset by resuming. No supervisor authorization grants another cycle.

Never, whatever the profile or the repository's steering document says: merge, force-push, delete a branch this run did not create or continue, deploy, run a production migration, read or write secrets, run bulk-data or scheduled-job commands, or point a local tool at shared or production data. The profile can forbid more; it can never permit past this list. The one force-push a run may make is a corrective run's lease-guarded rebase of its continued branch, as `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md` defines; never a default branch. A repository workflow that merges or pushes to a default branch does not apply inside a run: this list controls, and the sponsor runs that workflow outside the run.

A defect found outside the issue-defined plan is dispositioned once: take it only when the planned change cannot land without it, defer it to a new work item, or decline it with a reason. Record the disposition. Size, proximity, and reviewer preference never justify taking it.

**Regression guards.** The run issue or a repository sub-issue may carry Regression Guards: conditions that already hold at baseline and must remain true. Review covers each guard, and the check agent checks and reports it at the final head. A guard is not an acceptance criterion and needs no baseline failure.

Every comment the run posts is read back before its URL is recorded. For non-proof comments, a mismatched body is a failed post. Comments are never edited or deleted.

After readiness, ask the sponsor to amend an issue criterion this work cannot meet as written; continue against the amended text. Stop `NEEDS_REFINEMENT` only when the sponsor declines. An issue edit changes the review input: re-read the run issue and any non-null repository issue before review and final-head check.

## Eligibility

Check after confirming the run's home and before creating a branch. No repository limit applies.

1. Each acceptance criterion can be decided by a command at a repository head. A criterion requiring subjective judgment is ineligible. Reject any criterion marked `— sponsor judgement:`; chore accepts only command-decided criteria.
2. The issue-defined design is settled: no unresolved choice, alternative, or design decision remains.

An item failing any condition stops `NOT_APPLICABLE`, names `change-set-orchestrate`, and records `not_applicable_stage: never_started`. If the run discovers after it begins that it needs more assurance, stop the same `NOT_APPLICABLE`, name `change-set-orchestrate`, and record `not_applicable_stage: abandoned_mid_run`. Preserve partial work on its branch for sponsor disposition. Never turn an ineligible item into an informal exception.

## Shared finding policy

Apply `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/finding-policy.md` to review findings and reviewed heads, using the run issue and any non-null repository issue body as scope. Validate each `deferred.repository` against the participating set and pass only repository-owned and run-wide entries to review. The manager does not write, edit, or copy the review report.

## Run records and supervision

Use the shared `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md` and the narrow chore overlay `${CLAUDE_SKILL_DIR}/references/chore-run-state.md`. The `workflow` value is `chore-orchestrate`, run ID prefix `chore`, heading word `Chore`; phases are `readiness`, `resolve`, `implement`, `publish`, `review`, `check`, `merge_ready`, `retrospective`. The proof comment is `${CLAUDE_SKILL_DIR}/references/final-head-check.md`. The overlay defines `not_applicable_stage`, `plan: null`, proof identity and omitted evidence fields.

Append a complete coordination record on each phase change and whenever a pull request opens, before claiming the new state. A supervised ending turn includes the manager-status block as `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/status-block.md` defines, including its terminal-turn ordering. Apply relay persistence from `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md`. A phase change is not a reason to end a turn. Only a sponsor question or terminal signal ends one. Put a sponsor question on the run issue and read it back before ending; never use an interactive input tool for it. When the sponsor answers the manager's own question, the manager must append and read back an `orchestration-decision` marker on the run issue as the shared run-state contract defines, then record its URL before applying the answer.

At resolve, check presence in each repository work item issue, or the run issue when it supplies the criteria: each acceptance criterion has an `AC-n` identifier, and Acceptance Criteria and Regression Guards naming their commands are present. This is a presence check, not a quality judgment. Missing identifiers or sections stop `NEEDS_REFINEMENT` before implementation.

## Preflight

When invoked for preflight with a named run issue URL, run the stop conditions of the Readiness and Resolve steps below and nothing else; do not restate their checks here. Report each check as pass or fail with its reason, then stop without entering the run workflow. This is a presence and stop-condition check, plus the baseline check where those steps require it, not a quality judgment.

A preflight writes nothing: no record, comment, board change, scratch directory, branch or pull request. Running a criterion's check in the repository's checkout is not a write for this purpose; do not perform the workflow steps' writes or terminal publication.

## Workflow

1. **Readiness.** Read the run issue and its sub-issues verbatim. Confirm the run issue can be read, the participating repositories resolve one `coordination_repository`, and the run issue lives there, in that order. Before a valid home is confirmed, a stop posts no record or snapshot. Check concrete, jointly satisfiable criteria; an already-true condition belongs under Regression Guards. Check corrective-run declarations in `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md`, then eligibility. A failed eligibility check ends `NOT_APPLICABLE` with `never_started`. Confirm the issue bodies' current revision for review input.
   Run each criterion's check: a criterion whose check already passes at the baseline ends `NEEDS_REFINEMENT` and belongs in Regression Guards; check clauses inside a longer criterion too. Run the check in the repository's checkout at the default branch head; a checkout not clean at that head is itself a failed check. A check shared by a synchronized pair must be shown to fail: confirm it fails at the baseline for its own reason, not because it matches nothing.
   For a corrective run, the baseline check's checkout is a separate, already-existing clean checkout of the same repository at the default branch head. Resolve that checkout read-only with `git worktree list --porcelain`; verify its `HEAD` against the default-branch head and its clean status with `git status --porcelain`. Keep the continued checkout clean on its continued branch at the earlier snapshot's head, unchanged. If no such baseline checkout exists, report this baseline check as failed with that reason; never create a checkout, switch a branch or modify either checkout during preflight. This execution location does not replace the corrective run's merge-base baseline for review and final-head checks.
2. **Resolve.** Resolve profile field sources, baseline commits, tracking and any dependent merge order. A missing required sub-issue ends `NEEDS_REFINEMENT`. Check the review dependency before any branch. Move the run issue to in progress, append the record, and create the run scratch directory. There is no plan comment or acceptance.
3. **Implement.** Dispatch one retained `v8ch:chore-build-agent` subagent (`${CLAUDE_PLUGIN_ROOT}/agents/chore-build-agent.md`) per repository, serialized unless file ownership is exclusive. Give the builder the run issue and any non-null repository issue bodies and URLs, baseline, profile, and scratch directory. Corrections return to the same builder. The builder runs quality commands and criterion checks and reports out-of-plan findings.
4. **Publish.** Before pushing, the manager reads the full diff in each repository against its issue scope and searches for stale references to anything the change retires, by vocabulary and filenames. Route in-scope leftovers to the builder. Push and open a draft pull request per repository, using `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md`'s closing-keyword rules. Append a record immediately for each opened PR. Keep synchronized sibling PRs in draft together.
5. **Review.** Under `agent-tooling-review`, follow `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/agent-tooling-review-loop.md` and its severity-gated pass condition; prepare the plan file as for `consensus-review` and use a fresh review agent for each cycle. For `consensus-review`, follow the path below. Invoke the declared capability through a fresh `v8ch:chore-review-agent` subagent (`${CLAUDE_PLUGIN_ROOT}/agents/chore-review-agent.md`) per repository at the PR head. Documentation-only changes use this identical path. Before charging an invocation, prepare inputs as `${CLAUDE_SKILL_DIR}/references/chore-run-state.md` defines. Under `consensus-review`, write the verbatim run issue body and any non-null repository issue body with URLs to one readable plan file in scratch and pass it with `plan_source`. Persist the charge and read the record back before dispatch. The review bound covers correctness, security, privacy, authorization, stated criteria, Regression Guards and the issue-defined plan; put style, suggestions and nitpicks in one noted list. Route in-bound findings to the retained builder for `fixed`, reproduction-backed `declined`, `deferred`, or sponsor escalation with a `orchestration-decision` marker. A fix head needs another review: internal review-and-fix cycles stay in the same invocation until its cycle budget ends; only then does a new invocation consume another slot. With the budget spent and an open in-scope finding, stop `BLOCKED`.
6. **Check.** At each PR's current final head, dispatch a fresh dedicated `v8ch:chore-check-agent` subagent (`${CLAUDE_PLUGIN_ROOT}/agents/chore-check-agent.md`) with identifiers only: the run ID, issue URLs, repository and PR identifiers, current head SHA and scratch location. The agent resolves the profile from repository steering. The agent reads the criteria and commands from the issues, runs every `AC-n` check, every regression guard, and every profile quality command in a clean detached worktree under scratch, and posts one `${CLAUDE_SKILL_DIR}/references/final-head-check.md` table per PR. Link its returned URL from the record and read the comment back; a failed post or read-back stops `BLOCKED`, and the manager posts no evidence in its place. Persist its identity in the record. A moved head invalidates the table and review, and requires a new review and check. Failed criterion checks return to the builder and review while budget remains; when spent, stop `VERIFICATION_FAILED`. An unrelated quality failure stops `QUALITY_FAILURES`.
7. **Merge-ready.** Require a current-head review passing its capability gate (under `agent-tooling-review`, no open blocking or major finding and every finding dispositioned; under `consensus-review`, no open in-scope finding), a current-head check table with every applicable row passing, a clean worktree, and all required gates passing at that head. Recheck the head before taking any PR out of draft. Keep all participating PRs in draft until all pass, then mark them ready, append the record, and report the profile's merge method. Never merge.
8. **Retrospective.** Settle every delegated agent the manager started before appending the terminal snapshot: each has returned, or has been stopped and its stop recorded in the final coordination record. The terminal snapshot is the run's last record; after it, post nothing to the run issue except the retrospective. On every terminal path after the home is confirmed, append one terminal snapshot, move the run issue to in review for `READY_TO_MERGE`, and post one retrospective with the `orchestration-retrospective` marker. Remove scratch afterward as `${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md` says. The retrospective observes which reduction, if any, admitted a defect, and which retained step bought little, with an owner and future check for adopted or revised practices.

## Terminal output

Report changed repositories, PR URLs, check results, and sponsor decisions, then end with exactly one fenced block:

```chore-orchestrate-signal
{"signal":"<SIGNAL>","run_id":"<id>","details":{}}
```

`READY_TO_MERGE`, `NEEDS_REFINEMENT`, `BLOCKED`, `VERIFICATION_FAILED`, `QUALITY_FAILURES`, `DEPENDENCY_MISSING`, and `ABORT` have the change-set meanings with the check-agent table standing in for verification. `NOT_APPLICABLE` means eligibility failed before work or assurance needs grew mid-run; `details` names `change-set-orchestrate` and the recorded stage. Stop after the signal. Do not merge, deploy, or start unrequested follow-up work.
