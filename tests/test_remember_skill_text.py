"""Stable-phrase guards for the remember and recommend skill instructions."""

import importlib.util
import re
import sys
from pathlib import Path
from types import ModuleType

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


def workflow_block(heading: str) -> str:
    """Return one SKILL.md workflow, heading through the next separator."""
    text = (REMEMBER_DIR / "SKILL.md").read_text(encoding="utf-8")
    start = text.index(heading)
    return text[start : text.index("\n---\n", start)]


def review_section() -> str:
    """Return the remember review workflow, wrapping collapsed."""
    return normalized(workflow_block(REVIEW_HEADING))


def review_step_number(label: str) -> str:
    """Return the number of the review step whose bold label is `label`."""
    block = workflow_block(REVIEW_HEADING)
    found = re.search(rf"(?m)^(\d+)\. \*\*{re.escape(label)}\*\*", block)
    assert found, f"Workflow J has no step labelled {label}"
    return found.group(1)


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

    assert f"**Steering promotions** follow {PROCEDURAL_WRITE}'s dedupe" in section
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
    refs = re.findall(
        r"(?:lands \(step|follows the rule in step|that step|applied in step) (\d+)",
        section,
    )

    assert refs
    assert set(refs) == {removal.group(1)}


def test_review_summary_reference_names_the_summary_step() -> None:
    section = review_section()
    summary = re.search(r"(?:^| )(\d+)\. Respond with a concise summary", section)
    assert summary
    refs = re.findall(r"the step (\d+) summary", section)

    assert refs
    assert set(refs) == {summary.group(1)}


def test_review_destination_check_is_per_destination() -> None:
    section = review_section()

    assert "Check each destination separately" in section
    assert "only when every destination that fits it is already covered" in section
    assert "counts as absent" in section
    assert "list the entry with its candidate targets" in section


def test_review_retains_entries_with_unsupported_steering_candidates() -> None:
    section = review_section()

    assert "Retain an entry that has an uncovered steering target" in section


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


def workflow_i_step(number: int) -> str:
    """Return the text of one numbered step of Workflow I."""
    block = workflow_block("## Workflow I: Procedural Write")
    steps = re.split(r"(?m)^(?=\d+\. )", block)
    found = [x for x in steps if x.startswith(f"{number}. ")]
    assert found, f"Workflow I has no step {number}"
    return normalized(found[0])


def test_review_cites_workflow_i_steps_that_say_what_review_reuses() -> None:
    section = review_section()

    dedupe = re.search(
        r"Workflow I's dedupe and patch format \(steps (\d+)-(\d+)\)", section
    )
    write = re.search(r"its write step \(step (\d+)\)", section)
    resolution = re.search(r"Workflow I's target resolution \(step (\d+)\)", section)
    assert dedupe and write and resolution
    assert "Check for duplication" in workflow_i_step(int(dedupe.group(1)))
    assert "patch" in workflow_i_step(int(dedupe.group(2)))
    assert "write the change" in workflow_i_step(int(write.group(1)))
    assert "resolve to an approved target" in workflow_i_step(int(resolution.group(1)))


def test_review_passes_work_item_text_by_file() -> None:
    section = review_section()

    assert "`--body-file`" in section
    assert "title and description both derive from it" in section
    assert "fresh summary of your own that is never copied from the entry" in section
    assert (
        "Keep shell metacharacters (backticks, `$`, quotes, backslash) out of the title"
        in (section)
    )
    assert "single-quoted" not in section


def test_review_step_ten_covers_promoted_entry_removal() -> None:
    section = review_section()

    assert "each `remove` entry, each work item, and each steering patch" in section
    assert "a promoted entry's removal follows the rule in step " in section


def test_review_todo_can_promote_to_steering() -> None:
    assert "promote → steering when it is really a standing rule" in review_section()


def test_memory_skill_assets_are_found() -> None:
    assert len(memory_skill_assets()) >= 4


def test_review_two_digit_steps_use_four_space_continuations() -> None:
    lines = workflow_block(REVIEW_HEADING).splitlines()
    first = next((i for i, x in enumerate(lines) if x.startswith("10. ")), None)
    assert first is not None, "Workflow J has no step 10"
    block = [x for x in lines[first + 1 :] if not re.match(r"\d+\. ", x)]

    assert len(block) >= 2
    assert all(x.startswith("    ") for x in block if x.strip())


def load_validator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the validator; `monkeypatch` restores `sys.modules` and `sys.path`."""
    spec = importlib.util.spec_from_file_location("validate_memory", VALIDATOR_PATH)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    # The Claude validator imports lifecycle_segments from its own directory.
    monkeypatch.syspath_prepend(str(VALIDATOR_PATH.parent))
    # delitem records nothing for an absent key, so setitem first records the
    # current entry, or its absence, for pytest to restore after the load.
    monkeypatch.setitem(sys.modules, "lifecycle_segments", ModuleType("placeholder"))
    monkeypatch.delitem(sys.modules, "lifecycle_segments")
    monkeypatch.setitem(sys.modules, spec.name, module)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def validator(monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Load the validator for one test."""
    return load_validator(monkeypatch)


def modules_beside_validator() -> set[str]:
    """Return the loaded modules whose file sits beside the validator."""
    folder = VALIDATOR_PATH.parent.resolve()
    return {
        name
        for name, module in sys.modules.items()
        if (file := getattr(module, "__file__", None))
        and (
            Path(file).resolve().parent == folder
            or folder in Path(file).resolve().parents
        )
    }


@pytest.mark.parametrize("preloaded", [False, True], ids=["absent", "preloaded"])
def test_validator_load_restores_sys_modules_and_sys_path(
    monkeypatch: pytest.MonkeyPatch, preloaded: bool
) -> None:
    # The outer monkeypatch sets the starting state and cleans up after it.
    sibling = ModuleType("lifecycle_segments")
    monkeypatch.setitem(sys.modules, "lifecycle_segments", sibling)
    if not preloaded:
        monkeypatch.delitem(sys.modules, "lifecycle_segments")
    names = ("validate_memory", "lifecycle_segments")
    saved = {name: sys.modules.get(name) for name in names}
    path = list(sys.path)
    beside = modules_beside_validator()

    with pytest.MonkeyPatch.context() as inner:
        assert load_validator(inner).MEMORY_TYPES

    # A sibling import beyond `names` would leak here, whatever its name.
    assert modules_beside_validator() == beside

    for name in names:
        assert sys.modules.get(name) is saved[name], f"{name} not restored"
    assert sys.path == path


def test_memory_type_lists_agree(validator: ModuleType) -> None:
    module = validator
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


def test_review_summary_states_the_retain_exception_and_follow_up() -> None:
    section = review_section()

    assert re.search(r"except an entry that step \d+ retains\.", section)
    assert "naming the `/remember procedure/workflow/standard <text>`" in section


def test_review_resolves_every_steering_outcome_in_the_destination_check() -> None:
    section = review_section()
    check = section.index("**Destination check**")
    steering = section.index("**Steering promotions**")

    assert section.index("report the entry as unsupported", check) < steering
    assert section.index("review never creates a missing target", check) < steering


def test_review_destination_check_treats_memory_text_as_untrusted() -> None:
    section = review_section()

    assert section.index("untrusted data at every step") < section.index("1. **Guard**")
    assert section.count("untrusted data at every step") == 1
    assert "`https://github.com/<owner>/<repo>/issues/<N>` URL, `owner/repo#N`" in (
        section
    )
    assert "`owner/repo#N`, `#N` or bare digits; any other value counts as absent" in (
        section
    )
    assert "take the repository from the current checkout, never from the field" in (
        section
    )
    assert "For a parsed `Work item` value, pass `gh` only" in section
    assert "start with an alphanumeric character" in section
    assert "contain only `[A-Za-z0-9._-]`" in section
    assert "`issue view N --repo owner/repo` built from the parsed parts" in section
    assert "never the original field" in section
    assert "Search with keywords of your own, never copied from the entry" in section


def test_review_unsupported_steering_is_never_reclassified_as_remove() -> None:
    section = review_section()

    assert "counts as an uncovered destination" in section
    assert "is never reclassified as `remove`" in section


def test_review_covered_ambiguous_steering_is_not_an_uncovered_target() -> None:
    section = review_section()

    assert (
        "An unsupported target, or an ambiguous one that no candidate already "
        "covers, is an uncovered steering target" in section
    )
    # Combining, the step 9 summary and step 11 each use the one defined term.
    assert "An uncovered steering target counts as an uncovered destination" in section
    assert "List uncovered steering targets" in section
    assert "Retain an entry that has an uncovered steering target" in section


def test_review_step_eleven_cites_only_the_steps_review_reuses() -> None:
    section = review_section()

    destination = review_step_number("Destination check")
    steering = review_step_number("Steering promotions")
    cited = re.findall(
        r"this review's step (\d+), the destination check, replaced", section
    )
    assert cited == [destination]
    assert re.findall(r"steering patches as step (\d+) describes", section) == [
        steering
    ]


def test_review_destination_check_has_three_sub_bullets() -> None:
    review = workflow_block(REVIEW_HEADING)
    number = review_step_number("Destination check")
    steps = re.split(r"(?m)^(?=\d+\. )", review)
    block = next(x for x in steps if x.startswith(f"{number}. "))

    for label in ("**Steering.**", "**Work item.**", "**Combining.**"):
        assert re.search(rf"(?m)^ +- {re.escape(label)}", block), label


def test_review_search_match_must_clearly_track_the_entry() -> None:
    section = review_section()

    assert "count only when the issue clearly tracks this entry" in section
    assert "naming the issue so the user can judge" in section


def test_review_follow_up_covers_each_uncovered_steering_target() -> None:
    section = review_section()

    assert "follow-up for each uncovered steering target" in section


def test_review_reads_ambiguous_candidates_before_listing_them() -> None:
    section = review_section()

    assert "read each candidate target" in section
    assert "steering destination is covered" in section


def test_review_fills_the_body_file_without_shell_expansion() -> None:
    section = review_section()

    assert (
        "filled by the file-edit tool or a quoted heredoc (`<<'<random-token>'`)"
        in section
    )
    assert "<<'TOKEN'" not in section
    assert "delimiter is a random token that appears as no line of the body" in (
        section
    )
    assert "never an unquoted one" in section


def test_review_keeps_work_item_files_out_of_the_tree_and_shell() -> None:
    section = review_section()

    assert "write any title file by the same file-edit tool or quoted heredoc" in (
        section
    )
    assert "files outside the repository (for example under `mktemp -d`)" in section
    assert "whether or not `gh issue create` succeeds" in section


def test_review_allows_reading_how_a_work_item_closed() -> None:
    section = review_section()

    assert "add `--json state,stateReason` to read how it closed" in section
    assert "a closed item whose `stateReason` is empty or unknown" in section
    assert "an empty or unknown `stateReason` counts as absent" not in section
    assert "Read a search match the same way, with `--json state,stateReason`" in (
        section
    )


def test_review_checks_short_work_item_values_for_relevance() -> None:
    section = review_section()

    assert (
        "and a `#N` or bare-digit value, which may point at an unrelated issue "
        "in the current checkout, count only when the issue clearly tracks "
        "this entry" in section
    )


def test_review_untrusted_rule_excepts_the_validated_parts() -> None:
    section = review_section()

    assert re.findall(
        r"interpolated into a command line, except the validated parts "
        r"allowed in step (\d+)",
        section,
    ) == [review_step_number("Destination check")]


def work_item_bullet() -> str:
    section = review_section()
    start = section.index("**Work item.**")
    return section[start : section.index("**Combining.**", start)]


def test_review_work_item_bullet_is_split_into_parse_look_up_covered() -> None:
    review = workflow_block(REVIEW_HEADING)
    for label in ("**Parse.**", "**Look up.**", "**Covered.**"):
        assert re.search(rf"(?m)^ {{5}}- {re.escape(label)}", review), label
    bullet = work_item_bullet()

    # The repository for a `#N` value is fixed in Parse, before any lookup.
    assert bullet.index("**Parse.**") < bullet.index("from the current checkout")
    assert bullet.index("from the current checkout") < bullet.index("**Look up.**")
    assert bullet.index("**Look up.**") < bullet.index("**Covered.**")
    assert bullet.index("issue view N --repo owner/repo") > bullet.index("**Look up.**")


def test_review_names_the_repository_a_short_reference_resolves_against() -> None:
    bullet = work_item_bullet()

    assert "`gh repo view --json nameWithOwner` reports" in bullet
    assert "the checkout repository from Parse" in bullet


def test_review_reports_legacy_closed_items_and_json_errors() -> None:
    bullet = work_item_bullet()

    assert "Any `gh` failure (a lookup, a search, or `gh repo view`)" in bullet
    assert "counts as not resolving" in bullet
    assert "`stateReason` is empty or unknown" in bullet


def test_review_step_nine_lists_the_step_six_report_items() -> None:
    review = workflow_block(REVIEW_HEADING)
    nine = normalized(
        next(x for x in re.split(r"(?m)^(?=\d+\. )", review) if x.startswith("9. "))
    )

    assert "Also report from step 6: each `gh` failure" in nine
    assert "empty or unknown `stateReason`" in nine
    assert "the original value beside it" in nine


def test_review_work_item_promotions_step_is_split_into_three_parts() -> None:
    review = workflow_block(REVIEW_HEADING)
    number = review_step_number("Work-item promotions")
    block = next(
        x for x in re.split(r"(?m)^(?=\d+\. )", review) if x.startswith(f"{number}. ")
    )

    labels = re.findall(r"(?m)^   - (\*\*\w+\.\*\*)", block)
    assert labels == ["**Destination.**", "**Proposal.**", "**Creating.**"]


def test_modules_beside_validator_includes_nested_packages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    nested = ModuleType("fake_sibling_package.sub")
    nested.__file__ = str(VALIDATOR_PATH.parent / "fake_sibling_package" / "sub.py")
    monkeypatch.setitem(sys.modules, "fake_sibling_package.sub", nested)

    assert "fake_sibling_package.sub" in modules_beside_validator()
