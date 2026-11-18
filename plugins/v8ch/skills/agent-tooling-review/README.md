# Agent Tooling Review

Invoke `v8ch:agent-tooling-review` with local changes, a branch/base comparison, explicit files, or a GitHub PR URL or number. State the intended behavior when it is not evident from the change. The reviewer reports defects and coverage limits; only a PR input posts its one report as a PR comment. A local invocation returns the report in chat.

Set `review_capability: agent-tooling-review` to use it in `change-set-orchestrate`, `feature-orchestrate`, or `chore-orchestrate`. Each workflow manager follows the shared `workflows/contracts/agent-tooling-review-loop.md` at the plugin root for the bounded review/fix/re-review loop, and its retained builder makes fixes. Reports use severity-derived `clean`, `passing` or `failing` status; there is no score. Standalone invocation still performs one review. The entry document loads only the reference guides relevant to the changed artifacts.

## Requirements

- For GitHub pull request review: `git` and authenticated `gh`, with access to the repository and permission to post pull request comments.
- Local changes, branch/base comparisons and explicit-file reviews need a readable checkout; they return their report locally.
