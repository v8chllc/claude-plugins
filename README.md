# claude-plugins

Plugin, skill, and agent assets for Claude/Codex workflows.

## Repository Layout

- `plugins/` contains plugin-owned assets, grouped by owner or organization.
- `plugins/<owner>/agents/` contains agent definitions and supporting prompts.
- `plugins/<owner>/skills/<skill-name>/` contains skill packages.
- `plugins/<owner>/skills/<skill-name>/scripts/` contains helper scripts used by skills.
- `tests/` contains Python tests for plugin and skill behavior.

## Development

Install Node dependencies before running Markdown checks:

```sh
npm ci
npm run lint:md
```

Python quality tools are configured in `pyproject.toml`:

```sh
black --check .
ruff check .
ruff format --check .
mypy
pytest
```

GitHub Actions runs these checks on each push. See `CODING_STANDARDS.md` for code style and testing expectations.
