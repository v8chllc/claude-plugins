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
DOCUMENTED_COMMAND_BLOCKS = [
    (
        "README.md",
        "## Development",
        (
            "Install the repository-managed dependencies before running checks:",
            "Run the quality suite:",
        ),
    ),
    (
        "CODING_STANDARDS.md",
        "## Quality Checks",
        (
            "Install the repository-managed dependencies:",
            "Run the same checks used by CI before pushing:",
        ),
    ),
]


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


def command_block_after(text: str, label: str) -> str:
    match = re.search(
        rf"^{re.escape(label)}\n\n```(?:sh|bash)\n(?P<commands>.*?)\n```",
        text,
        flags=re.DOTALL | re.MULTILINE,
    )
    assert match is not None, f"documented command block is missing after: {label}"
    return match.group("commands")


def assert_documented_commands(
    text: str, block_labels: tuple[str, str], expected: set[str]
) -> None:
    actual = {
        line.strip()
        for label in block_labels
        for line in command_block_after(text, label).splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }
    missing = sorted(expected - actual)
    unexpected = sorted(actual - expected)
    if actual != expected:
        raise AssertionError(
            f"documented commands differ; missing: {missing}; unexpected: {unexpected}"
        )


def test_agent_workflow_profile_is_exact() -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())

    assert list(profile) == list(EXPECTED_PROFILE)
    assert profile == EXPECTED_PROFILE


@pytest.mark.parametrize(
    ("document", "section_heading", "block_labels"), DOCUMENTED_COMMAND_BLOCKS
)
def test_documented_commands_match_profile(
    document: str, section_heading: str, block_labels: tuple[str, str]
) -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())
    expected = SETUP_COMMANDS | set(profile_quality_commands(profile))

    assert section_heading in (ROOT / document).read_text()
    assert_documented_commands((ROOT / document).read_text(), block_labels, expected)


@pytest.mark.parametrize(
    ("document", "section_heading", "block_labels"), DOCUMENTED_COMMAND_BLOCKS
)
def test_documented_command_check_ignores_unrelated_shell_examples(
    document: str, section_heading: str, block_labels: tuple[str, str]
) -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())
    expected = SETUP_COMMANDS | set(profile_quality_commands(profile))
    text = (ROOT / document).read_text()
    nested_example = "\n\n### Unrelated Example\n\n```sh\necho unrelated\n```"
    text = text.replace(section_heading, section_heading + nested_example, 1)

    assert_documented_commands(text, block_labels, expected)


@pytest.mark.parametrize(
    ("document", "section_heading", "block_labels"), DOCUMENTED_COMMAND_BLOCKS
)
def test_documented_command_check_rejects_extra_quality_commands(
    document: str, section_heading: str, block_labels: tuple[str, str]
) -> None:
    profile = load_profile((ROOT / "AGENTS.md").read_text())
    expected = SETUP_COMMANDS | set(profile_quality_commands(profile))
    text = (ROOT / document).read_text()
    assert section_heading in text
    text = text.replace("uv run pytest\n```", "uv run pytest\npytest\n```", 1)

    with pytest.raises(AssertionError, match=r"unexpected: \['pytest'\]"):
        assert_documented_commands(text, block_labels, expected)


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
