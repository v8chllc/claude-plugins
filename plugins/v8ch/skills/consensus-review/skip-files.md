# Consensus Review — Skip List

This is the canonical skip list for all consensus reviewer agents. Do not review files matching any of these patterns — skip them silently:

- `**/__pycache__/**`, `**/*.pyc`, `**/.pytest_cache/**`, `**/.mypy_cache/**`, `**/.ruff_cache/**`
- `**/*.egg-info/**`, `**/dist/**`, `**/build/**`, `**/*.lock`
- `ai_docs/**/*.md` — external scraped docs
- `settings/**` — configuration templates
- `steering/**/*.md` — high-level guidance docs
- `skills/codex/global/.system/**`
- `**/LICENSE.md`, `**/*.DS_Store`, `**/.venv/**`, `**/.vscode/**`, `**/.idea/**`
