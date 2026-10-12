"""Contract guard for caller-capped consensus-review failure routing."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / "plugins/v8ch/skills/consensus-review/references/fix-workflow.md"


def _normalize_whitespace(text: str) -> str:
    return " ".join(text.split())


def _numbered_route(routing: str, item: int, next_item: int) -> str:
    return routing.split(f"{item}. ", 1)[1].split(f"{next_item}. ", 1)[0]


def test_mutation_failure_reaches_capped_terminal_routing() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fixer_result = workflow.split("## Step 2 — Read the fixer's result", 1)[1].split(
        "## Step 3 — Commit", 1
    )[0]
    mutation_unproven = fixer_result.split("- **`MUTATION_UNPROVEN`**", 1)[1].split(
        "- **`QUALITY_FAILURES`**", 1
    )[0]
    routing = workflow.split("## Step 5 — Return to the orchestrator", 1)[1]
    capped_route = _numbered_route(routing, 1, 2)
    mutation_route = _numbered_route(routing, 2, 3)

    assert "continue to Step 5 without committing" in _normalize_whitespace(
        mutation_unproven
    )
    assert "return `BLOCKERS_REMAIN`" not in mutation_unproven
    assert "Caller-declared single-cycle cap" in capped_route
    assert "unproven_findings" in capped_route
    assert "MUTATION_UNPROVEN" in mutation_route
    assert "BLOCKERS_REMAIN" in mutation_route


def test_quality_failure_reaches_capped_terminal_routing() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fixer_result = workflow.split("## Step 2 — Read the fixer's result", 1)[1].split(
        "## Step 3 — Commit", 1
    )[0]
    quality_failures = fixer_result.split("- **`QUALITY_FAILURES`**", 1)[1].split(
        "- **No files changed**", 1
    )[0]
    routing = workflow.split("## Step 5 — Return to the orchestrator", 1)[1]
    capped_route = _numbered_route(routing, 1, 2)

    assert (
        "Preserve the failed commands and continue to Step 5 without committing"
        in _normalize_whitespace(quality_failures)
    )
    assert "return `QUALITY_FAILURES`" not in quality_failures
    assert "Caller-declared single-cycle cap" in capped_route
    assert "failed_commands" in capped_route
