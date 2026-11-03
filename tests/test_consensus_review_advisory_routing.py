"""Guard the caller handoff and lower-score fixer routing."""

from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "plugins/v8ch/skills/consensus-review/SKILL.md"
POSTER = REPO_ROOT / "plugins/v8ch/agents/consensus-review-poster.md"


def workflow_steps() -> tuple[str, str, str]:
    workflow = SKILL.read_text(encoding="utf-8")
    return (
        workflow,
        workflow.split("8. **Return or post.**", 1)[1].split(
            "9. **Resolve advisory routing", 1
        )[0],
        workflow.split("9. **Resolve advisory routing", 1)[1].split("## Budget", 1)[0],
    )


def test_missing_reference_aborts_before_posting() -> None:
    workflow, posting_step, _ = workflow_steps()
    inputs = workflow.split("## Inputs\n")[1].split("## Scope ladder\n")[0]
    assert "Without one, emit `ABORT`" in inputs
    assert "`reason` `unsupported_scope`" in inputs
    assert "- **No PR/MR reference:**" not in posting_step
    assert "- **PR/MR number:**" in posting_step


def test_advisory_route_follows_successful_post_and_precedes_fixer() -> None:
    workflow, _, routing_step = workflow_steps()
    posting = workflow.index("Capture the comment URL")
    handoff = workflow.index("review_contract.py advisory")
    fixer = workflow.index(
        "- `passing` or `failing` — run `references/fix-workflow.md`"
    )

    assert posting < handoff < fixer
    assert "reason` `post_failed` and stop" in workflow[posting:handoff]
    assert "single advisory eligibility decision point" in routing_step


def test_clean_route_follows_a_null_advisory_result() -> None:
    _, _, routing_step = workflow_steps()
    list_route = routing_step.index("- **List result**")
    clean_route = routing_step.index("- **Null result with `clean` status**")
    fixer_route = routing_step.index("- `passing` or `failing`")
    assert list_route < clean_route < fixer_route
    assert "CAPPED_REVIEW_COMPLETE" in routing_step[clean_route:fixer_route]
    assert "REVIEW_COMPLETE" in routing_step[clean_route:fixer_route]


def test_advisory_route_applies_after_cycle_one() -> None:
    _, _, routing_step = workflow_steps()
    assert "every review cycle, including cycles after cycle one" in routing_step


def test_advisory_route_stops_without_invoking_the_fixer() -> None:
    _, _, routing_step = workflow_steps()
    list_route = routing_step.split("- **List result**", 1)[1].split(
        "- **Null result", 1
    )[0]
    assert "REVIEW_COMPLETE_WITH_FINDINGS" in list_route
    assert "Stop without invoking the fixer" in list_route
    assert "reviewed_sha` exactly as supplied to the poster" in list_route


def test_passing_summary_assigns_open_findings_to_caller() -> None:
    poster = POSTER.read_text(encoding="utf-8")
    passing_rule = poster.split("- `passing` —", 1)[1].split("- `failing` —", 1)[0]
    assert "The caller will disposition the open findings" in passing_rule
    assert "A fix cycle will address" not in passing_rule
