"""Pin the named deferred input and its single-consumer routing."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins/v8ch"
SKILL = ROOT / "skills/consensus-review/SKILL.md"
SYNTHESIZER = ROOT / "agents/review-synthesizer.md"
POSTER = ROOT / "agents/consensus-review-poster.md"
REVIEWERS_AND_FIXER = (
    "architecture-reviewer.md",
    "correctness-reviewer.md",
    "standards-reviewer.md",
    "consensus-review-fixer.md",
)


def test_skill_accepts_deferred_and_routes_it_only_to_synthesizer() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    inputs = skill.split("## Inputs\n", 1)[1].split("## Scope ladder\n", 1)[0]
    synthesis = skill.split("7. **Synthesize.**", 1)[1].split(
        "8. **Return or post.**", 1
    )[0]
    plan_handling = skill.split("## Plan handling\n", 1)[1].split("## Citations\n", 1)[
        0
    ]
    for phrase in (
        "caller-supplied `deferred` JSON text or a file path",
        "A local review accepts a\n   `deferred` file only",
        "never recovered from PR/MR comments",
        "Only the synthesizer consumes this input",
        "non-empty string `summary` and",
        "`reason`, `work_item` as string or null",
        "A null or omitted repository is run-wide",
    ):
        assert phrase in inputs
    assert "the `deferred` input\n   and its source" in synthesis
    assert "the reviewed repository" in synthesis
    assert "`none` when the input is absent or an\nempty array" in plan_handling
    assert "otherwise `supplied: <path or short description>`" in plan_handling
    assert "only the synthesizer receives the input itself" in plan_handling


def test_synthesizer_keeps_new_or_uncertain_defects_as_findings() -> None:
    text = SYNTHESIZER.read_text(encoding="utf-8")
    rule = text.split("## Step 4 — Classify what remains\n", 1)[1].split(
        "When a plan is supplied", 1
    )[0]
    for phrase in (
        "Parse `deferred` as a JSON array in its supplied order",
        "An omitted or null repository is run-wide",
        "do no cross-repository matching",
        "exactly one Plan Note titled",
        "`Unparseable deferred input` with a 0 deduction",
        "by judgment, not string matching",
        "Matches deferred entry <n>",
        "no `[F-N]` number, a 0",
        "is not sent to the fixer",
        "new instance of a deferred defect",
        "a defect widened by the reviewed diff, or an unsure match",
        "remains a finding at\nits own severity",
    ):
        assert phrase in rule
    assert "Deferred: <none | supplied: source>." in text


def test_poster_hands_deferred_source_to_schema_3_script() -> None:
    text = POSTER.read_text(encoding="utf-8")
    assert "copy `Deferred:` into\n  `--deferred-source`" in text
    assert "--deferred-source '<none | supplied: source>'" in text
    assert "`schema_version: 3`" in text


def test_reviewers_and_fixer_do_not_receive_deferred() -> None:
    for name in REVIEWERS_AND_FIXER:
        assert (
            "deferred"
            not in (ROOT / "agents" / name).read_text(encoding="utf-8").lower()
        )
