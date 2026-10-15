"""Guards for the shared memory boundary and recommendation write order."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "plugins/v8ch"
REMEMBER = ROOT / "skills/remember/SKILL.md"
RECOMMEND = ROOT / "skills/recommend/SKILL.md"
SHARED = ROOT / "memory"
VALIDATOR = "${CLAUDE_PLUGIN_ROOT}/memory/scripts/validate_memory.py"


def workflow(name: str) -> str:
    text = RECOMMEND.read_text(encoding="utf-8")
    start = text.index(f"## Workflow {name}:")
    return text[start:].split("\n---\n", 1)[0]


def test_recommend_owns_every_recommendation_route() -> None:
    remember = REMEMBER.read_text(encoding="utf-8")
    recommend = RECOMMEND.read_text(encoding="utf-8")
    for heading in ("Recommend Curated", "Recommend Session", "Recommend Procedural"):
        assert heading not in remember
        assert heading in recommend
    assert "use the `recommend` skill" in remember


def test_approved_writes_follow_preflight_on_all_routes() -> None:
    for route in ("E", "F", "G"):
        text = workflow(route)
        approval = (
            text.lower().index("ask which to apply")
            if route != "G"
            else text.lower().index("ask which")
        )
        preflight = text.index(VALIDATOR)
        apply = text.index("Apply only approved", preflight)
        assert approval < preflight < apply
        assert "recording.md" in text[apply:]


def test_both_skills_use_same_shared_operations_without_cross_skill_assets() -> None:
    for path in (REMEMBER, RECOMMEND):
        text = path.read_text(encoding="utf-8")
        for asset in (
            "types.md",
            "procedural-targets.md",
            "journal-format.md",
            "recording.md",
        ):
            assert f"../../memory/references/{asset}" in text
        assert VALIDATOR in text
        assert "../remember/" not in text
        assert "../recommend/" not in text


def test_shared_recording_contract_preserves_dedupe_and_target_boundary() -> None:
    recording = (SHARED / "references/recording.md").read_text(encoding="utf-8")
    assert "same name or" in recording
    assert "update the entry in place" in recording
    assert "session_hash" in recording
    assert "skip the append" in recording
    assert "reject unsupported" in recording
    assert "after approval and before any curated or procedural step" in recording


def test_validator_imports_only_shared_segment_parser() -> None:
    validator = (SHARED / "scripts/validate_memory.py").read_text(encoding="utf-8")
    assert "from segment_format import valid_segment" in validator
    assert "lifecycle_segments" not in validator.split("import valid_segment")[0]
