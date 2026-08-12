from __future__ import annotations

import importlib.util
import json
import os
import stat
import sys
from pathlib import Path

import pytest

SCRIPT = (
    Path(__file__).parents[1]
    / "plugins"
    / "v8ch"
    / "skills"
    / "remember"
    / "scripts"
    / "hook_setup.py"
)
SPEC = importlib.util.spec_from_file_location("hook_setup", SCRIPT)
assert SPEC and SPEC.loader
SETUP = importlib.util.module_from_spec(SPEC)
# Register before executing so the module's dataclasses can resolve their own
# module namespace.
sys.modules[SPEC.name] = SETUP
SPEC.loader.exec_module(SETUP)

STOP = SETUP.CHANNELS["stop-capture"]
SESSION_END = SETUP.CHANNELS["session-end-capture"]


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / ".remember" / "memory").mkdir(parents=True)
    (tmp_path / ".remember" / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    return tmp_path


def settings(root: Path) -> dict:
    return json.loads((root / ".claude" / "settings.json").read_text(encoding="utf-8"))


def commands(root: Path, event: str) -> list[str]:
    groups = settings(root)["hooks"][event]
    return [entry["command"] for group in groups for entry in group["hooks"]]


def test_source_handler_is_committed_executable() -> None:
    assert SETUP.HANDLER_SOURCE.stat().st_mode & stat.S_IXUSR


def test_enable_installs_executable_handler_and_registration(project: Path) -> None:
    result = SETUP.enable(project, STOP)

    handler = project / ".claude" / "hooks" / "remember-stop-capture.py"
    assert result["action"] == "enabled"
    assert handler.stat().st_mode & 0o777 == SETUP.HANDLER_MODE
    assert os.access(handler, os.X_OK)
    assert handler.read_text(encoding="utf-8") == SETUP.HANDLER_SOURCE.read_text(
        encoding="utf-8"
    )
    entry = settings(project)["hooks"]["Stop"][0]["hooks"][0]
    assert entry["command"] == (
        "${CLAUDE_PROJECT_DIR}/.claude/hooks/remember-stop-capture.py"
    )
    assert entry["args"] == ["--root", "${CLAUDE_PROJECT_DIR}", "--kind", "stop"]


def test_enable_requires_initialized_memory(tmp_path: Path) -> None:
    with pytest.raises(SETUP.SetupError, match="not initialized"):
        SETUP.enable(tmp_path, STOP)
    assert not (tmp_path / ".claude").exists()


def test_enable_does_not_register_a_handler_that_failed_to_install(
    project: Path, monkeypatch
) -> None:
    def fail_install(root: Path, channel) -> Path:
        raise SETUP.SetupError("install failed")

    monkeypatch.setattr(SETUP, "install_handler", fail_install)

    with pytest.raises(SETUP.SetupError, match="install failed"):
        SETUP.enable(project, STOP)

    assert not (project / ".claude" / "settings.json").exists()


def test_channels_are_independently_enabled_and_disabled(project: Path) -> None:
    SETUP.enable(project, STOP)
    SETUP.enable(project, SESSION_END)

    assert len(commands(project, "Stop")) == 1
    assert len(commands(project, "SessionEnd")) == 1

    SETUP.disable(project, STOP)

    assert "Stop" not in settings(project)["hooks"]
    assert len(commands(project, "SessionEnd")) == 1
    assert not (project / ".claude" / "hooks" / "remember-stop-capture.py").exists()
    assert (project / ".claude" / "hooks" / "remember-session-end-capture.py").is_file()


def test_re_enable_refreshes_without_duplicating(project: Path) -> None:
    SETUP.enable(project, STOP)
    handler = project / ".claude" / "hooks" / "remember-stop-capture.py"
    handler.write_text("stale\n", encoding="utf-8")
    handler.chmod(0o644)

    result = SETUP.enable(project, STOP)

    assert result["action"] == "refreshed"
    assert len(commands(project, "Stop")) == 1
    assert os.access(handler, os.X_OK)
    assert "stale" not in handler.read_text(encoding="utf-8")


def test_enable_replaces_a_legacy_registration(project: Path) -> None:
    legacy = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": (
                                "${CLAUDE_PROJECT_DIR}/.claude/hooks/"
                                "remember-stop-capture.py"
                            ),
                            "timeout": 5,
                        }
                    ]
                }
            ]
        }
    }
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(
        json.dumps(legacy), encoding="utf-8"
    )

    SETUP.enable(project, STOP)

    entries = [
        entry
        for group in settings(project)["hooks"]["Stop"]
        for entry in group["hooks"]
    ]
    assert len(entries) == 1
    assert entries[0]["args"] == ["--root", "${CLAUDE_PROJECT_DIR}", "--kind", "stop"]


def test_similar_unrelated_handler_name_is_preserved(project: Path) -> None:
    unrelated = {
        "hooks": {
            "Stop": [
                {
                    "hooks": [
                        {
                            "type": "command",
                            "command": "./audit-remember-stop-capture.py",
                        }
                    ]
                }
            ]
        }
    }
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(
        json.dumps(unrelated), encoding="utf-8"
    )

    SETUP.enable(project, STOP)
    SETUP.disable(project, STOP)

    assert settings(project) == unrelated


def test_unrelated_settings_and_hooks_are_preserved(project: Path) -> None:
    original = {
        "permissions": {"allow": ["Bash(git status)"]},
        "hooks": {
            "Stop": [{"hooks": [{"type": "command", "command": "./other.sh"}]}],
            "PreToolUse": [
                {"matcher": "Bash", "hooks": [{"type": "command", "command": "./b.sh"}]}
            ],
        },
    }
    (project / ".claude").mkdir()
    (project / ".claude" / "settings.json").write_text(
        json.dumps(original), encoding="utf-8"
    )

    SETUP.enable(project, STOP)
    SETUP.disable(project, STOP)

    assert settings(project) == original


def test_invalid_settings_are_reported_and_never_overwritten(project: Path) -> None:
    path = project / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text("{ broken", encoding="utf-8")

    with pytest.raises(SETUP.SetupError, match="not valid JSON"):
        SETUP.enable(project, STOP)

    assert path.read_text(encoding="utf-8") == "{ broken"


@pytest.mark.parametrize("content", ("", "[]", '{"hooks": []}'))
def test_invalid_settings_shapes_are_preserved(project: Path, content: str) -> None:
    path = project / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text(content, encoding="utf-8")

    with pytest.raises(SETUP.SetupError):
        SETUP.enable(project, STOP)

    assert path.read_text(encoding="utf-8") == content


def test_disable_is_safe_when_nothing_is_installed(project: Path) -> None:
    result = SETUP.disable(project, SESSION_END)

    assert result["action"] == "already-disabled"
    assert not (project / ".claude" / "settings.json").exists()


def test_status_reports_each_channel(project: Path) -> None:
    SETUP.enable(project, SESSION_END)

    payload = SETUP.status(project)
    states = {item["channel"]: item for item in payload["channels"]}

    assert payload["memory_initialized"] is True
    assert states["session-end-capture"]["state"] == "enabled"
    assert states["session-end-capture"]["handler_executable"] is True
    assert states["stop-capture"]["state"] == "disabled"
    assert states["stop-capture"]["registrations"] == 0


def test_status_can_report_one_channel(project: Path, capsys) -> None:
    SETUP.enable(project, SESSION_END)

    payload = SETUP.status(project, SESSION_END)

    assert [item["channel"] for item in payload["channels"]] == ["session-end-capture"]
    assert (
        SETUP.main(["status", "session-end-capture", "--root", str(project), "--json"])
        == 0
    )
    rendered = json.loads(capsys.readouterr().out)
    assert [item["channel"] for item in rendered["channels"]] == ["session-end-capture"]


def test_status_flags_a_registered_but_non_executable_handler(project: Path) -> None:
    SETUP.enable(project, STOP)
    (project / ".claude" / "hooks" / "remember-stop-capture.py").chmod(0o644)

    states = {item["channel"]: item for item in SETUP.status(project)["channels"]}

    assert states["stop-capture"]["state"] == "disabled"
    assert states["stop-capture"]["registrations"] == 1
    assert states["stop-capture"]["handler_executable"] is False


def test_main_requires_a_channel_for_enable(project: Path) -> None:
    assert SETUP.main(["enable", "--root", str(project)]) == 1


def test_main_status_emits_json(project: Path, capsys) -> None:
    assert SETUP.main(["status", "--root", str(project), "--json"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert [item["state"] for item in payload["channels"]] == ["disabled", "disabled"]


def test_main_status_fails_when_settings_state_is_unknown(
    project: Path, capsys
) -> None:
    path = project / ".claude" / "settings.json"
    path.parent.mkdir()
    path.write_text("{broken", encoding="utf-8")

    assert SETUP.main(["status", "--root", str(project), "--json"]) == 1
    payload = json.loads(capsys.readouterr().out)
    assert all("settings_error" in channel for channel in payload["channels"])
