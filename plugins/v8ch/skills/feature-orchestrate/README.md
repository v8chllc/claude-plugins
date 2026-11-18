# feature-orchestrate

The Claude Code workflow shipped by the `v8ch` plugin. Its role agents use Claude Code’s Agent, SendMessage, and Skill tools.

Delivers added behavior, or a mix of added and changed behavior, across one or more participating repositories, with one pull request per repository. It carries the work from readiness through bounded implementation slices, independent review, a frozen head and fresh verification, and an open, merge-ready pull request the sponsor merges.

Use `change-set-orchestrate` for changes or corrections to existing behavior.

## Requirements

- A GitHub Project board tracking the run issue, with statuses for in progress and in review.
- A coordination issue in `coordination_repository`, with one sub-issue per participating repository.
- `git` and authenticated `gh`, with access to the repositories, issues, pull requests and Project board.
- A sandboxed environment. The skill's agents run commands, edit files, push branches and publish to GitHub; it is intended for sandboxed environments only.

## Files

| Path | What it holds |
| --- | --- |
| `SKILL.md` | The lifecycle, authority boundaries, run records, and terminal signals |
| `references/slice-lifecycle.md` | The ten-step slice lifecycle, stop conditions by step, the checkpoint decision, and loop mode |
| `references/review.md` | Who fixes under each review capability, what counts as a finding, accepting a finding as-is, and class audits |
| `references/result-comment.md` | The fresh verifier's result comment and output rules |
| `workflows/contracts/run-state.md` | Shared contract: the run issue, coordination record, plan comment, snapshot, and retrospective |
| `workflows/contracts/repository-profile.md`, `workflows/contracts/profile-template.md` | Shared contract: the profile fields, including `journey` and `loop_ceiling` |
| `workflows/contracts/status-block.md` | Shared contract: the manager-status block a supervisor reads |
| `../../agents/feature-*-agent.md` | The plan, build, review, and fresh verify roles, as Claude Code subagents |

## What it needs

**From the environment:** `git` and `gh`, authenticated, with `gh` v2.99.0 or later when evidence includes images or video; and the review capability the profile's `review_capability` names.

**From the repository:** a profile in its steering document. `journey` names the command the verifier runs, and `loop_ceiling` caps unchecked slices; both default conservatively.

**From the sponsor:** a run issue with concrete, jointly satisfiable criteria; the split, when a unit of work needs two pull requests; and a decision on any surviving verification row requiring a sponsor exception.
