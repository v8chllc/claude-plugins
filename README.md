# claude-plugins

Plugin, skill, and agent assets for Claude/Codex workflows.

## Installation

In Claude Code, add the marketplace and install the plugin:

```text
/plugin marketplace add v8chllc/claude-plugins
/plugin install v8ch@v8ch
```

The plugin includes `consensus-review`, `post-merge-review`, `remember`, and
`recommend`, plus these delivery workflows:

- `v8ch:chore-orchestrate` — mechanically checkable chores.
- `v8ch:change-set-orchestrate` — changes to existing behavior.
- `v8ch:feature-orchestrate` — added behavior across participating repositories.
- `v8ch:agent-tooling-review` — skills, agents, and tooling review.
- `v8ch:supervise` — supervision of another agent’s orchestrated run.

The orchestrators and `supervise` are intended for sandboxed environments only.
Read each skill’s Requirements before invoking it: they require authenticated
GitHub access, coordination issues, and a Project board. `supervise` also uses
`.prompts/` and launches managers with permission-bypass flags.

## Repository Layout

- `plugins/` contains plugin-owned assets, grouped by owner or organization.
- `plugins/<owner>/agents/` contains agent definitions and supporting prompts.
- `plugins/<owner>/skills/<skill-name>/` contains skill packages.
- `plugins/<owner>/skills/<skill-name>/scripts/` contains helper scripts used by skills.
- `tests/` contains Python tests for plugin and skill behavior.

## Development

Use mise as the tool-version manager. Install the selected Node version first:

```sh
mise install
```

Install the repository-managed dependencies before running checks:

```sh
npm ci
uv sync
```

Run the quality suite:

```sh
npm run lint:md
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

GitHub Actions runs these checks on each push. See `CODING_STANDARDS.md` for code style and testing expectations.
