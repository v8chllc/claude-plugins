"""Stable-phrase guards for the remember and recommend skill instructions."""

from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "plugins/v8ch/skills"
REMEMBER_DIR = SKILLS_DIR / "remember"
TYPES_PATH = REMEMBER_DIR / "references/types.md"
LEGACY_DIRECTIVE = REMEMBER_DIR / "references/claude-md-directive.md"
REVIEW_HEADING = "## Workflow J: Review"
PROCEDURAL_WRITE = "Workflow I"

# Tokens that only the removed local context lane ever used.
LEGACY_LANE_TOKENS = (
    ".remember/local",
    "context.md",
    "<!-- context -->",
    "`context`",
    "/remember context",
    "Remember the context",
)


def normalized(text: str) -> str:
    """Collapse wrapping so phrase checks ignore Markdown line breaks."""
    return " ".join(text.split())


def memory_skill_assets() -> list[Path]:
    """Return remember and recommend Markdown, except the legacy directive."""
    assets = [
        *(SKILLS_DIR / "remember").rglob("*.md"),
        *(SKILLS_DIR / "recommend").rglob("*.md"),
    ]
    return sorted(path for path in assets if path != LEGACY_DIRECTIVE)


def review_section() -> str:
    """Return the remember review workflow, heading through the next separator."""
    text = (REMEMBER_DIR / "SKILL.md").read_text(encoding="utf-8")
    start = text.index(REVIEW_HEADING)
    end = text.index("\n---\n", start)
    return normalized(text[start:end])


def test_todo_status_is_open_or_blocked_only() -> None:
    text = TYPES_PATH.read_text(encoding="utf-8")

    assert "Status: <open | blocked>" in text
    assert "done | obsolete" not in text
    assert "a completed or obsolete todo is removed" in normalized(text)


def test_legacy_directive_is_still_shipped() -> None:
    assert LEGACY_DIRECTIVE.is_file()


@pytest.mark.parametrize(
    "asset",
    memory_skill_assets(),
    ids=lambda path: str(path.relative_to(SKILLS_DIR)),
)
def test_memory_skill_text_has_no_local_context_lane(asset: Path) -> None:
    text = asset.read_text(encoding="utf-8")

    hits = [token for token in LEGACY_LANE_TOKENS if token in text]

    assert not hits, f"{asset.relative_to(REPO_ROOT)} still mentions {hits}"


def test_review_classifies_into_four_outcomes() -> None:
    section = review_section()

    for outcome in (
        "`retain`",
        "`remove`",
        "`promote → work item`",
        "`promote → steering`",
    ):
        assert outcome in section
    assert "`act`" not in section
    assert (
        "Every entry type is eligible for whichever promotion destination fits"
        in section
    )


def test_review_checks_the_destination_before_proposing() -> None:
    section = review_section()

    assert "**Destination check**: before proposing any promotion" in section
    assert "reclassify the entry as `remove`" in section


def test_review_routes_promotions_through_their_write_paths() -> None:
    section = review_section()

    assert f"**Steering promotions** go through {PROCEDURAL_WRITE}" in section
    assert "fail closed" in section
    assert "tracking rules in the repository's steering" in section
    assert "propose an issue in the current repository" in section
    assert "propose the parent too" in section


def test_review_removes_promoted_entries_without_a_pointer() -> None:
    section = review_section()

    assert "only after every approved destination for it has landed" in section
    assert "decisions included" in section
    assert "leave no pointer" in section
    assert "A declined or failed promotion leaves the entry unchanged" in section
    assert "update `todo` entries with the `Work item` field" not in section


def test_review_summary_groups_and_needs_per_item_approval() -> None:
    section = review_section()

    assert "summary grouped by outcome" in section
    assert "Group promotions by destination" in section
    assert "Nothing is removed, written, or created without per-item approval" in (
        section
    )
