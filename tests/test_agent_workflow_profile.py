from __future__ import annotations

import re
from pathlib import Path
from typing import cast

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
PROFILE_HEADING = "## Agent workflow profile"
EXPECTED_PROFILE = {
    "tracking": "required",
    "merge_method": "rebase",
    "quality_commands": [
        "npm run lint:md",
        "uv run black --check .",
        "uv run ruff check .",
        "uv run ruff format --check .",
        "uv run mypy",
        "uv run pytest",
    ],
    "release_steps": [
        "whenever a file under plugins/<name>/ changes, bump the version in "
        "plugins/<name>/.claude-plugin/plugin.json and the literal version in "
        "tests/test_claude_marketplace.py in the same pull request"
    ],
    "prohibited_actions": [
        "never move private vault content into this public repository",
        "never merge; the sponsor merges",
    ],
    "synchronized_with": "v8chllc/codex-plugins",
}
SETUP_COMMANDS = {"npm ci", "uv sync"}


def load_profile(text: str) -> dict[str, object]:
    if text.count(PROFILE_HEADING) != 1:
        raise AssertionError(f"expected exactly one {PROFILE_HEADING!r} heading")
    section = text.split(PROFILE_HEADING, maxsplit=1)[1]
    match = re.search(r"```yaml\n(.*?)\n```", section, flags=re.DOTALL)
    assert match is not None, "agent workflow profile YAML block is missing"
    profile = yaml.safe_load(match.group(1))
    assert isinstance(profile, dict), "agent workflow profile must be a mapping"
    return profile


def workflow_commands(text: str) -> set[str]:
    workflow = yaml.safe_load(text)
    commands: set[str] = set()
    for job in workflow["jobs"].values():
        for step in job["steps"]:
            run = step.get("run")
            if run:
                commands.update(
                    line.strip() for line in run.splitlines() if line.strip()
                )
    return commands


def profile_quality_commands(profile: dict[str, object]) -> list[str]:
    commands = profile.get("quality_commands")
    assert isinstance(commands, list)
    assert all(isinstance(command, str) for command in commands)
    return cast(list[str], commands)


def assert_quality_commands_in_ci(
    quality_commands: list[str], ci_commands: set[str]
) -> None:
    missing = [command for command in quality_commands if command not in ci_commands]
    assert not missing, "CI is missing profile quality command(s): " + ", ".join(
        missing
    )


def shell_commands(text: str) -> set[str]:
    blocks = re.findall(r"```(?:sh|bash)\n(.*?)\n```", text, flags=re.DOTALL)
    return {
        line.strip()
        for block in blocks
        for line in block.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def test_agent_workflow_profile_is_exact() -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())

    assert list(profile) == list(EXPECTED_PROFILE)
    assert profile == EXPECTED_PROFILE


@pytest.mark.parametrize("document", ["README.md", "CODING_STANDARDS.md"])
def test_documented_commands_match_profile(document: str) -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())
    expected = SETUP_COMMANDS | set(profile_quality_commands(profile))

    assert shell_commands((ROOT / document).read_text()) == expected


def test_profile_quality_commands_are_in_ci() -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())
    workflow_text = (ROOT / ".github/workflows/code-quality.yml").read_text()

    assert "pip install" not in workflow_text
    assert "uv sync --locked" in workflow_commands(workflow_text)
    assert_quality_commands_in_ci(
        profile_quality_commands(profile), workflow_commands(workflow_text)
    )


def test_ci_drift_diagnostic_names_missing_command() -> None:
    missing_command = "uv run pytest"

    with pytest.raises(AssertionError, match=re.escape(missing_command)):
        assert_quality_commands_in_ci([missing_command], set())
