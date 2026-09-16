# claude-plugins

Plugin, skill, and agent assets for Claude/Codex workflows.

## Repository Layout

- `plugins/` contains plugin-owned assets, grouped by owner or organization.
- `plugins/<owner>/agents/` contains agent definitions and supporting prompts.
- `plugins/<owner>/skills/<skill-name>/` contains skill packages.
- `plugins/<owner>/skills/<skill-name>/scripts/` contains helper scripts used by skills.
- `tests/` contains Python tests for plugin and skill behavior.

## Development

Install the repository-managed dependencies before running checks:

```sh
npm ci
uv sync
```

Run the quality suite:

```sh
npm run lint:md
uv run black --check .
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest
```

GitHub Actions runs these checks on each push. See `CODING_STANDARDS.md` for code style and testing expectations.
