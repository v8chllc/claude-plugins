# chore-orchestrate

Delivers a settled, mechanically checkable chore across any number of repositories from a sponsor-created run issue to reviewed, open pull requests. The run issue and any required repository issue bodies define the work. The check agent runs every criterion, guard and quality command at each final PR head.

`SKILL.md` defines the lifecycle and exactly five reductions relative to `change-set-orchestrate`. `${CLAUDE_PLUGIN_ROOT}/agents/chore-build-agent.md`, `${CLAUDE_PLUGIN_ROOT}/agents/chore-review-agent.md`, and `${CLAUDE_PLUGIN_ROOT}/agents/chore-check-agent.md` are the role agents. `references/chore-run-state.md` overlays the byte-identical shared `run-state.md` without changing full-assurance workflows. `references/final-head-check.md` defines the check agent's proof comment. Other references retain the shared repository profile, review, status and publication contracts.

Invoke `v8ch:chore-orchestrate` with a run issue URL. Documentation-only changes receive review. An ineligible item or a mid-run assurance gap ends `NOT_APPLICABLE` and names `change-set-orchestrate`.

## Requirements

- A GitHub Project board tracking the run issue, with statuses for in progress and in review.
- A coordination issue in `coordination_repository`, with one sub-issue per participating repository.
- `git` and authenticated `gh`, with access to the repositories, issues, pull requests and Project board.
- A sandboxed environment. The skill's agents run commands, edit files, push branches and publish to GitHub; it is intended for sandboxed environments only.
