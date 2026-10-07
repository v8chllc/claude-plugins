"""Stable-phrase guards for the remember and recommend skill instructions."""

import importlib.util
import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILLS_DIR = REPO_ROOT / "plugins/v8ch/skills"
REMEMBER_DIR = SKILLS_DIR / "remember"
TYPES_PATH = REMEMBER_DIR / "references/types.md"
VALIDATOR_PATH = REMEMBER_DIR / "scripts/validate_memory.py"
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
    assert "Reclassify the entry as `remove`" in section


def test_review_routes_promotions_through_their_write_paths() -> None:
    section = review_section()

    assert f"**Steering promotions** go through {PROCEDURAL_WRITE}" in section
    assert "fail closed" in section
    assert "tracking rules in the repository's steering" in section
    assert "propose an issue in the current repository" in section
    assert "propose the parent too" in section


def test_review_removes_promoted_entries_without_a_pointer() -> None:
    section = review_section()

    assert "only when every proposed promotion for it was approved" in section
    assert "If any proposed promotion for an entry is declined or fails" in section
    assert "is approved and lands (step " in section
    assert "decisions included" in section
    assert "leave no pointer" in section
    assert "leave the entry unchanged" in section
    assert "update `todo` entries with the `Work item` field" not in section


def test_review_step_references_name_the_removal_step() -> None:
    section = review_section()
    removal = re.search(r"(?:^| )(\d+)\. Apply only approved items", section)
    assert removal
    refs = re.findall(r"(?:lands \(step|follows the rule in step) (\d+)", section)

    assert refs
    assert set(refs) == {removal.group(1)}


def test_review_summary_reference_names_the_summary_step() -> None:
    section = review_section()
    summary = re.search(r"(?:^| )(\d+)\. Respond with a concise summary", section)
    assert summary
    refs = re.findall(r"in the step (\d+) summary", section)

    assert refs == [summary.group(1)]


def test_review_destination_check_is_per_destination() -> None:
    section = review_section()

    assert "Check each destination separately" in section
    assert "only when every destination that fits it is already covered" in section
    assert "counts as absent" in section
    assert "list the entry with its candidate targets" in section


def test_review_retains_entries_with_unsupported_steering_candidates() -> None:
    section = review_section()

    assert (
        "Retain an entry that has an unsupported or ambiguous steering candidate"
        in section
    )


def test_review_flags_more_public_work_item_destinations() -> None:
    section = review_section()

    assert "more public than the current repository" in section
    assert (
        "leave private detail from the entry out of its title and description"
        in section
    )


def test_review_summary_groups_and_needs_per_item_approval() -> None:
    section = review_section()

    assert "summary grouped by outcome" in section
    assert "Group promotions by destination" in section
    assert "Nothing is removed, written, or created without per-item approval" in (
        section
    )


def test_review_runs_validation_before_classifying() -> None:
    section = review_section()

    assert "scripts/validate_memory.py" in section
    assert section.index("validate_memory.py") < section.index("Classify each entry")


def test_review_delegates_steering_writes_to_named_steps() -> None:
    section = review_section()

    assert "Workflow I step 5 does" in section
    assert "review never creates a missing target" in section


def test_review_passes_work_item_text_by_file() -> None:
    section = review_section()

    assert "`--body-file`" in section
    assert "title and description both derive from it" in section
    assert "fresh summary of your own that is never copied from the entry" in section
    assert "single-quoted" not in section
    assert "never interpolate entry text into the command line" in section


def test_review_step_ten_covers_promoted_entry_removal() -> None:
    section = review_section()

    assert "each `remove` entry, each work item, and each steering patch" in section
    assert "a promoted entry's removal follows the rule in step " in section


def test_review_todo_can_promote_to_steering() -> None:
    assert "promote → steering when it is really a standing rule" in review_section()


def test_memory_skill_assets_are_found() -> None:
    assert len(memory_skill_assets()) >= 4


def test_review_two_digit_steps_use_four_space_continuations() -> None:
    text = (REMEMBER_DIR / "SKILL.md").read_text(encoding="utf-8")
    start = text.index(REVIEW_HEADING)
    lines = text[start : text.index("\n---\n", start)].splitlines()
    first = next((i for i, x in enumerate(lines) if x.startswith("10. ")), None)
    assert first is not None, "Workflow J has no step 10"
    block = [x for x in lines[first + 1 :] if not re.match(r"\d+\. ", x)]

    assert len(block) >= 2
    assert all(x.startswith("    ") for x in block if x.strip())


def test_memory_type_lists_agree() -> None:
    spec = importlib.util.spec_from_file_location("validate_memory", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The validator imports lifecycle_segments from its own directory.
    script_dir = str(VALIDATOR_PATH.parent)
    sys.path.insert(0, script_dir)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    finally:
        sys.modules.pop(spec.name, None)
        sys.path.remove(script_dir)
    types = list(module.MEMORY_TYPES)
    skill = (REMEMBER_DIR / "SKILL.md").read_text(encoding="utf-8")
    heading = re.search(r"^# Memory$", skill, re.M)
    assert heading
    stub = skill[heading.start() :]
    stub = stub[: stub.index("```")]
    comment = re.search(r"<!-- Types: (.*?) +-->", stub)
    assert comment
    workflow_d = re.search(r"classify as one of: (.*?)\.\n", skill)
    assert workflow_d

    assert re.findall(r"^## (\w+)$", TYPES_PATH.read_text("utf-8"), re.M) == types
    assert re.findall(r"^## (\w+)$", stub, re.M) == types
    assert comment.group(1).split(" | ") == types
    assert re.findall(r"`(\w+)`", workflow_d.group(1)) == types
    # The Record trigger lists in remember and recommend's candidate list are
    # prose; only the remember slash-command triggers are checked here.
    start = skill.index("**Record — slash command:**")
    triggers = skill[start : skill.index("**Record — natural language", start)]
    assert re.findall(r"`/remember (\w+) <", triggers) == types


def test_types_opening_has_no_type_count() -> None:
    opening = TYPES_PATH.read_text("utf-8").split("---", 1)[0]
    # The whole opening is pinned so a type count cannot return in any wording.
    sentence = "Each type below is curated memory in `.remember/MEMORY.md`."
    expected = f"# Memory Types {sentence} Use these templates when writing entries."
    assert normalized(opening) == expected


def test_todo_template_marks_work_item_legacy() -> None:
    text = normalized(TYPES_PATH.read_text(encoding="utf-8"))

    assert "Work item: <legacy; leave empty" in text
    assert "<optional link/id if created>" not in text


def test_recommend_notes_that_todos_are_not_recommended() -> None:
    text = normalized((SKILLS_DIR / "recommend/SKILL.md").read_text(encoding="utf-8"))

    clause = "todos are recorded with `/remember todo`, not recommended"
    assert text.count(clause) == 2


def test_review_work_item_coverage_uses_one_bar() -> None:
    section = review_section()

    assert "open or closed as completed" in section
    assert "closed as not planned or as a duplicate" in section
    assert "open or done" not in section


def test_review_summary_states_the_retain_exception_and_follow_up() -> None:
    section = review_section()

    assert "except an entry that step 11 retains" in section
    assert "naming the `/remember procedure/workflow/standard <text>`" in section


def test_review_resolves_every_steering_outcome_in_the_destination_check() -> None:
    section = review_section()
    check = section.index("**Destination check**")
    steering = section.index("**Steering promotions**")

    assert section.index("report the entry as unsupported", check) < steering
    assert section.index("review never creates a missing target", check) < steering
