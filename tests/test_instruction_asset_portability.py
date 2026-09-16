"""Plugin-wide portability guards for shipped Markdown instructions."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGIN_DIR = REPO_ROOT / "plugins/v8ch"

# A plugin instruction asset must never name the plugin's checkout path. Match
# both a script file and the scripts directory itself. Claude provides
# ${CLAUDE_SKILL_DIR} for same-skill scripts and ${CLAUDE_PLUGIN_ROOT} for
# cross-skill references; both remain portable in the installed cache.
HARDCODED_SKILL_SCRIPTS_RE = re.compile(
    r"plugins/v8ch/skills/[^\s`'\"]*/scripts(?:/|\b)"
)


def instruction_assets() -> list[Path]:
    """Return every Markdown instruction asset shipped by the plugin."""
    return sorted(PLUGIN_DIR.rglob("*.md"))


@pytest.mark.parametrize("asset", instruction_assets(), ids=lambda path: path.name)
def test_instruction_assets_do_not_hardcode_skill_scripts(asset: Path) -> None:
    text = asset.read_text(encoding="utf-8")
    match = HARDCODED_SKILL_SCRIPTS_RE.search(text)
    hit = match.group(0) if match else ""
    assert match is None, (
        f"{asset.relative_to(REPO_ROOT)} hardcodes '{hit}'. "
        "Use ${CLAUDE_SKILL_DIR} or ${CLAUDE_PLUGIN_ROOT} instead."
    )


@pytest.mark.parametrize(
    "command",
    [
        "uv run plugins/v8ch/skills/consensus-review/scripts/recover_context.py 7",
        "cd plugins/v8ch/skills/remember/scripts && python validate_memory.py",
    ],
)
def test_hardcoded_skill_scripts_are_rejected(command: str) -> None:
    assert HARDCODED_SKILL_SCRIPTS_RE.search(command)


@pytest.mark.parametrize(
    "command",
    [
        "uv run ${CLAUDE_SKILL_DIR}/scripts/recover_context.py 7",
        "python ${CLAUDE_PLUGIN_ROOT}/skills/remember/scripts/validate_memory.py",
    ],
)
def test_claude_plugin_path_substitutions_are_permitted(command: str) -> None:
    assert not HARDCODED_SKILL_SCRIPTS_RE.search(command)


def test_memory_skills_use_installed_plugin_paths_for_validation() -> None:
    remember = (PLUGIN_DIR / "skills/remember/SKILL.md").read_text(encoding="utf-8")
    recommend = (PLUGIN_DIR / "skills/recommend/SKILL.md").read_text(encoding="utf-8")

    assert remember.count("${CLAUDE_SKILL_DIR}/scripts/validate_memory.py") == 7
    assert (
        recommend.count(
            "${CLAUDE_PLUGIN_ROOT}/skills/remember/scripts/validate_memory.py"
        )
        == 3
    )
