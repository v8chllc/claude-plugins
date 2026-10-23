"""Pin the consensus review finding bound and repair scope in shipped prompts."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "plugins/v8ch"
SKILL = ROOT / "skills/consensus-review/SKILL.md"
WORKFLOW = ROOT / "skills/consensus-review/references/fix-workflow.md"
AGENTS = ROOT / "agents"
REVIEWERS = (
    "standards-reviewer.md",
    "correctness-reviewer.md",
    "architecture-reviewer.md",
)


def test_every_reviewer_applies_the_same_finding_bound() -> None:
    for name in REVIEWERS:
        text = (AGENTS / name).read_text(encoding="utf-8")
        assert (
            "Flag a gap only when it affects correctness, security, privacy or "
            "authorization" in text
        )
        assert "a stated acceptance criterion or Regression Guard, or the plan" in text
        assert "## Noted" in text
        assert "without a severity or requested fix" in " ".join(text.split())


def test_architecture_cost_and_duplication_obey_finding_bound() -> None:
    text = (AGENTS / "architecture-reviewer.md").read_text(encoding="utf-8")
    structure = text.split("## Step 1", 1)[1].split("## Step 2", 1)[0]
    duplication = text.split("**Duplication with a concrete maintenance cost**", 1)[
        1
    ].split("- **Prompt assets**", 1)[0]
    assert "report it as a finding only when its" in structure
    assert "demonstrated consequence meets the finding bound" in structure
    assert "Report it as a finding only" in duplication
    assert "demonstrated consequence meets the finding bound" in duplication
    assert "otherwise\n  put the observation in Noted" in duplication


def test_committed_output_obeys_finding_bound_in_every_reviewer() -> None:
    for name in REVIEWERS:
        text = (AGENTS / name).read_text(encoding="utf-8")
        output_rule = text.split("Vendored dependencies, build output", 1)[1].split(
            "## Severity", 1
        )[0]
        assert "consider it one observation" in output_rule
        assert "finding bound to decide whether it is a finding or Noted" in (
            output_rule
        )


def test_synthesis_carries_one_unscored_noted_list_outside_findings() -> None:
    text = (AGENTS / "review-synthesizer.md").read_text(encoding="utf-8")
    assert "Before scoring, enforce the finding bound yourself" in text
    assert "Move every other\nobservation to one Noted list" in text
    assert (
        "do not assign severities, finding IDs,\ndeductions, or individual dispositions"
        in text
    )
    report = text.split("Emit these sections in this order", 1)[1]
    assert report.count("### Noted") == 1
    assert report.index("### Plan Notes") < report.index("### Noted")
    assert report.index("### Noted") < report.index("### Behavior Deltas")


def test_fixer_cannot_expand_or_rewrite_run_scope() -> None:
    fixer = (AGENTS / "consensus-review-fixer.md").read_text(encoding="utf-8")
    workflow = WORKFLOW.read_text(encoding="utf-8")
    assert (
        "Never change an acceptance criterion, Regression Guard, or plan decision"
        in fixer
    )
    assert "never add scope to close a finding" in fixer
    assert "within the original scope" in fixer
    assert "Do not edit the plan or redefine the supplied inputs" in fixer
    assert "Noted list also needs no individual disposition" in fixer
    assert "acceptance criteria, Regression Guards, and supplied plan" in workflow


def test_skill_accepts_and_passes_optional_run_criteria_and_guards() -> None:
    text = SKILL.read_text(encoding="utf-8")
    inputs = text.split("## Inputs", 1)[1].split("## Scope ladder", 1)[0]
    assert "**Acceptance criteria and Regression Guards** (optional)" in inputs
    assert "as text or file paths" in inputs
    assert "do not invent them" in inputs
    reviewers = text.split("4. **Run the three reviewers", 1)[1].split(
        "5. **Apply the evidence gate", 1
    )[0]
    synthesis = text.split("7. **Synthesize.", 1)[1].split("8. **Return or post.", 1)[0]
    assert "acceptance criteria and Regression Guards" in reviewers
    assert "criteria and Regression Guards" in synthesis
