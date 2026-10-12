"""Contract guards for consensus-review repair proof and capped outcomes."""

from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "plugins/v8ch/skills/consensus-review"
AGENT_DIR = REPO_ROOT / "plugins/v8ch/agents"


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def test_repair_proof_policy_has_one_normative_source() -> None:
    contract = read(SKILL_DIR / "references/repair-proof.md")
    fixer = read(AGENT_DIR / "consensus-review-fixer.md")
    workflow = read(SKILL_DIR / "references/fix-workflow.md")
    reviewer = read(AGENT_DIR / "repair-proof-reviewer.md")

    assert "normative contract" in contract
    assert "references/repair-proof.md" in fixer
    assert "references/repair-proof.md" in workflow
    for duplicated_rule in (
        "A **text-only repair** changes",
        "remove or invert the repair",
        "A repair is proven only when",
    ):
        assert duplicated_rule in contract
        assert duplicated_rule not in fixer
        assert duplicated_rule not in workflow
        assert duplicated_rule not in reviewer

    assert "## Independent verification procedure" in contract
    assert "correction inspected and reason" in contract
    assert "accepted` | `rejected" not in reviewer


def test_text_repairs_require_an_independent_read_only_reviewer() -> None:
    reviewer_path = AGENT_DIR / "repair-proof-reviewer.md"
    reviewer = read(reviewer_path)
    workflow = read(SKILL_DIR / "references/fix-workflow.md")
    header = yaml.safe_load(reviewer.split("---", 2)[1])

    assert set(header["tools"]) == {"Read", "Grep", "Glob"}
    assert "v8ch:repair-proof-reviewer" in workflow
    assert workflow.index("v8ch:repair-proof-reviewer") < workflow.index(
        "## Step 3 — Commit"
    )
    assert "PROOF_UNPROVEN" in workflow
    assert "independent text repair verification records" in workflow


def test_independent_verification_fails_closed() -> None:
    contract = read(SKILL_DIR / "references/repair-proof.md")
    workflow = read(SKILL_DIR / "references/fix-workflow.md")

    assert "derive the expected text-only finding IDs" in contract
    assert "every expected ID occurs\nexactly once as `accepted`" in contract
    assert "the terminal marker alone is insufficient" in contract
    for invalid_result in (
        "missing",
        "malformed",
        "duplicate",
        "rejected",
        "unexpected",
        "incomplete",
    ):
        assert invalid_result in contract
    assert "missing or incorrect terminal marker" in contract
    assert "expected text-only finding IDs derived from the fixer's result" in workflow
    assert "Validate the\ncomplete record against the contract" in workflow


def test_capped_review_routes_before_fixer_failure_signals() -> None:
    workflow = read(SKILL_DIR / "references/fix-workflow.md")
    routing = workflow.split("## Step 5 — Return to the orchestrator", 1)[1]
    capped = routing.index("Caller-declared single-cycle cap")

    assert capped < routing.index("MUTATION_UNPROVEN")
    assert capped < routing.index("Outcome `QUALITY_FAILURES`")
    for detail in ("fixer_outcome", "failed_commands", "unproven_findings"):
        assert f"`{detail}`" in routing


def test_capped_signal_schema_carries_fixer_failure_details() -> None:
    skill = read(SKILL_DIR / "SKILL.md")
    capped_row = next(
        line
        for line in skill.splitlines()
        if line.startswith("| `CAPPED_REVIEW_COMPLETE`")
    )
    for key in ("fixer_outcome", "failed_commands", "unproven_findings"):
        assert f"`{key}`" in capped_row
