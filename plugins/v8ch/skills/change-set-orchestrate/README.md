# change-set-orchestrate

The Claude Code workflow shipped by the `v8ch` plugin. Its role agents use Claude Code’s Agent, SendMessage, and Skill tools.

Delivers one change set end to end — tooling, documentation, CI, dependency, or
refactor work that changes or corrects existing behavior — across one or more participating repositories under one run issue, and leaves an open pull request the sponsor merges.

New behavior, or a mix of new and changed behavior, belongs to the feature workflow.

## Requirements

- A GitHub Project board tracking the run issue, with statuses for in progress and in review.
- A coordination issue in `coordination_repository`, with one sub-issue per participating repository.
- `git` and authenticated `gh`, with access to the repositories, issues, pull requests and Project board.
- A sandboxed environment. The skill's agents run commands, edit files, push branches and publish to GitHub; it is intended for sandboxed environments only.

## Files

| Path | What it holds |
| --- | --- |
| `SKILL.md` | The lifecycle, authority boundaries, and terminal signals |
| `workflows/contracts/repository-profile.md` | The sixteen profile fields, their defaults, and the narrow-only rule |
| `workflows/contracts/profile-template.md` | A copy-paste profile block and a worked example |
| `workflows/contracts/run-state.md` | The shared run-state contract: the run issue, the appended coordination record, the plan comment, snapshot, and retrospective |
| `workflows/contracts/finding-policy.md` | The shared full-assurance review finding policy |
| `references/verification-comment.md` | This skill's verification comment |
| `../../agents/change-set-plan-agent.md` | Plans only what is expensive to reverse; writes nothing |
| `../../agents/change-set-build-agent.md` | The sole writer in one repository |
| `../../agents/change-set-review-agent.md` | Runs one repository's review invocation through the review capability from manager-prepared inputs; writes no review text |
| `../../agents/change-set-verify-agent.md` | Chooses a falsifying check per criterion and posts the evidence; given identifiers only |

## What it needs

**From the environment:** `git`, `uv`, and `gh`, authenticated, and the review
capability the profile's `review_capability` names. Under `consensus-review`,
the default, that is the `v8ch:consensus-review` skill at 2.0.8 or later — without it the
run stops at resolve, before any branch exists, with `DEPENDENCY_MISSING`
rather than reviewing its own work. The verifier posts the result directly.

**From the repository:** a profile in its steering document
(`workflows/contracts/profile-template.md`). Every field but one has a conservative
default, so a repository with no profile still runs — it just asks the sponsor
more often — provided a workspace profile states `coordination_repository`.
That field defaults to `none`, and a run with no coordination repository cannot
start. In a
workspace holding several repositories, each field resolves from the repository profile, then its matching named child
block, then the workspace default child block, then the field default. The
field that changes the run most is `autonomy`:

- `autonomous` — the manager checks the plan against the run issue's acceptance
  criteria and accepts it. Sponsor checkpoints still apply as defined below.
- `checkpointed` (the default) — the sponsor approves the plan before any code
  changes.

**From the sponsor:** a run issue in the coordination repository, with a
sub-issue for each repository whose profile requires one, and acceptance criteria
that are concrete and jointly satisfiable. The run creates no issues. The run stops with `NEEDS_REFINEMENT` when they are not,
naming the collision rather than inventing a resolution.

## What it asks the sponsor

Sponsor decisions cover adding a repository, exceeding the review budget,
taking work outside the approved plan, resolving a merge conflict the criteria
do not settle, accepting escalated major evidence findings, and actions the
profile marks `checkpointed`. A criterion that cannot be met as written also
returns for sponsor amendment. `SKILL.md` owns the exact routing and exceptions.

## What it never does

Merge, unauthorized force-push, deploy, run a production migration, read or
write secrets,
run bulk-data or scheduled-job commands, or point a local tool at shared or
production data. Only a corrective run may use the lease-guarded rebase
exception in `workflows/contracts/run-state.md`. A profile can forbid more; it can never
permit past this list.

## Where the run leaves its state

The run issue carries the run: a coordination record appended at every phase
change, so a fresh manager resumes from the latest; the accepted plan, one
comment per revision; a terminal snapshot written once; and a retrospective. Each
pull request carries its repository's facts: reviews, the verification comment,
and fix evidence in commit bodies. Each links the other. Local scratch is never
evidence.

## Running it

Invoke `v8ch:change-set-orchestrate` with the run issue URL and any scope note. When a
supervisor is watching, follow `workflows/contracts/status-block.md` for the status block
the manager emits on each ending turn.
