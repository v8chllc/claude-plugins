"""Guard the synthesizer's sponsor-decision classification contract."""

import re
from pathlib import Path

SYNTHESIZER = (
    Path(__file__).resolve().parent.parent / "plugins/v8ch/agents/review-synthesizer.md"
)


def classification_rule() -> str:
    """Return the synthesizer's classification instructions as searchable text."""
    text = SYNTHESIZER.read_text(encoding="utf-8")
    step_2 = text.index("## Step 2 — Deduplicate")
    step_3 = text.index("## Step 3 — Drop")
    step_4 = text.index("## Step 4 — Classify")
    step_5 = text.index("## Step 5 — Score")
    assert step_2 < step_3 < step_4 < step_5
    return re.sub(r"\n(?!\n)", " ", text[step_4:step_5])


def test_sponsor_decision_entries_route_rejected_fixes_to_unscored_notes() -> None:
    """Require rejected fixes to become unnumbered, unscored Plan Notes."""
    rule = classification_rule()
    for clause in (
        "finding's proposed fix and failure statement",
        "every parsed `D-<n>` entry",
        "implement a `Rejected:` alternative",
        "reverse the decision text",
        "route that contradiction to Plan Notes",
        "`**Plan reference:**`",
        "no severity tag",
        "no `[F-N]` number",
        "a 0 deduction",
    ):
        assert clause in rule


def test_demonstrated_severe_failure_and_independent_defects_stay_ranked() -> None:
    """Keep demonstrated severe failures and independent defects ranked."""
    rule = classification_rule()
    for clause in (
        "demonstrated CRITICAL or",
        "HIGH failure is the exception",
        "keep the defect in Must Fix",
        "send it to the fixer as an ordinary finding",
        "rank any independent defect normally",
        "matches no entry",
        "exactly as before",
        "Cite both entries when decisions",
    ):
        assert clause in rule


def test_missing_and_malformed_sections_use_none_default() -> None:
    """Require the missing-section default and one malformed-section note."""
    rule = classification_rule()
    for clause in (
        "A missing section is `None.`",
        "single line `None.`",
        "`- **D-<n>:** `",
        "starting at 1 and increasing without gaps or leading zeroes",
        "`  - Rejected: <alternative>`",
        "`  - Source: <URL>`",
        "more than one `### Sponsor decisions` heading",
        "treat all its entries as `None.`",
        "exactly one Plan Note titled",
        "`Unparseable sponsor decisions section`",
        "with a 0 deduction",
    ):
        assert clause in rule
