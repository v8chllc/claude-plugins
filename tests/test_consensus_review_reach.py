"""Pin reachable finding grades and the current report shape."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent / "plugins/v8ch"
AGENTS = ROOT / "agents"
SKILL = ROOT / "skills/consensus-review/SKILL.md"


def severity(name: str) -> str:
    text = (AGENTS / name).read_text(encoding="utf-8")
    return text.split("## Severity\n", 1)[1].split("\n## ", 1)[0]


@pytest.mark.parametrize("name", ["standards-reviewer.md", "architecture-reviewer.md"])
def test_severity_routes_maintenance_only_observations_to_noted(name: str) -> None:
    section = severity(name)
    normalized = " ".join(section.split())
    assert (
        "maintenance cost, convention, style, or structure goes in Noted at any size"
        in normalized
    )
    grades = re.findall(
        r"(?ms)^- \*\*(?:CRITICAL|HIGH|MEDIUM|LOW)\*\*.*?"
        r"(?=\n- \*\*|\n\n|\Z)",
        section,
    )
    assert len(grades) == 4
    assert all("maintenance cost" not in grade for grade in grades)
    assert "- **MEDIUM**" in section
    assert "- **LOW**" in section
    assert "current code can reach" in section


def test_correctness_severity_requires_current_reach() -> None:
    section = severity("correctness-reviewer.md")
    assert "current code can reach" in section
    assert "goes in Noted without a severity" in section
    assert "Name the condition" in section
    assert "no reachable trigger" not in section


def test_current_assets_have_no_latent_section_or_hypothetical_grade() -> None:
    assets = [
        *AGENTS.glob("*reviewer.md"),
        AGENTS / "review-synthesizer.md",
        AGENTS / "consensus-review-fixer.md",
        SKILL,
    ]
    for asset in assets:
        text = asset.read_text(encoding="utf-8")
        assert "Latent Findings" not in text, asset
        assert "would-be failure" not in text, asset
    synthesizer = (AGENTS / "review-synthesizer.md").read_text(encoding="utf-8")
    sections = synthesizer.split("Emit these sections in this order", 1)[1].split(
        "```", 2
    )[1]
    for heading in ("### Must Fix", "### Should Fix", "### Plan Notes", "### Noted"):
        assert heading in sections
    assert "condition in its Noted bullet" in synthesizer
