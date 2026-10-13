"""Guard the caller handoff and lower-score fixer routing."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "plugins/v8ch/skills/consensus-review/SKILL.md"
POSTER = REPO_ROOT / "plugins/v8ch/agents/consensus-review-poster.md"


def test_advisory_route_follows_successful_post_and_precedes_fixer() -> None:
    workflow = SKILL.read_text(encoding="utf-8")
    posting = workflow.index("Capture the comment URL")
    handoff = workflow.index("review_contract.py advisory")
    fixer = workflow.index(
        "- `passing` or `failing` — run `references/fix-workflow.md`"
    )

    assert posting < handoff < fixer
    assert "reason` `post_failed` and stop" in workflow[posting:handoff]
    assert "including a caller-capped invocation" in workflow[handoff:fixer]
    assert "REVIEW_COMPLETE_WITH_FINDINGS" in workflow[handoff:fixer]
    assert "reviewed_sha` exactly as supplied to the poster" in workflow[handoff:fixer]


def test_passing_summary_assigns_open_findings_to_caller() -> None:
    poster = POSTER.read_text(encoding="utf-8")
    passing_rule = poster.split("- `passing` —", 1)[1].split("- `failing` —", 1)[0]
    assert "The caller will disposition the open findings" in passing_rule
    assert "A fix cycle will address" not in passing_rule
