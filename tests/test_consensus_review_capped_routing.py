"""Contract guard for caller-capped consensus-review failure routing."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
WORKFLOW = REPO_ROOT / "plugins/v8ch/skills/consensus-review/references/fix-workflow.md"


def test_mutation_failure_reaches_capped_terminal_routing() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    fixer_result = workflow.split("## Step 2 — Read the fixer's result", 1)[1].split(
        "## Step 3 — Commit", 1
    )[0]
    mutation_unproven = fixer_result.split("- **`MUTATION_UNPROVEN`**", 1)[1].split(
        "- **`QUALITY_FAILURES`**", 1
    )[0]
    routing = workflow.split("## Step 5 — Return to the orchestrator", 1)[1]

    assert "continue to Step 5 without\n  committing" in mutation_unproven
    assert "return `BLOCKERS_REMAIN`" not in mutation_unproven
    assert routing.index("Caller-declared single-cycle cap") < routing.index(
        "MUTATION_UNPROVEN"
    )
