from __future__ import annotations

import importlib.util
import json
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[1]
    / "plugins"
    / "v8ch"
    / "skills"
    / "remember"
    / "scripts"
    / "stop_capture.py"
)
SPEC = importlib.util.spec_from_file_location("stop_capture", SCRIPT)
assert SPEC and SPEC.loader
STOP_CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(STOP_CAPTURE)


def test_capture_writes_one_idempotent_main_agent_segment(tmp_path: Path) -> None:
    payload = {
        "hook_event_name": "Stop",
        "session_id": "session-1",
        "last_assistant_message": "Completed the task.",
    }

    assert STOP_CAPTURE.capture(tmp_path, payload) == 0
    assert STOP_CAPTURE.capture(tmp_path, payload) == 0

    paths = list((tmp_path / ".remember" / "turns").glob("*.json"))
    assert len(paths) == 1
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["session_id"] == "session-1"
    assert record["last_assistant_message"] == "Completed the task."


def test_capture_ignores_subagents_and_non_stop_events(tmp_path: Path) -> None:
    assert (
        STOP_CAPTURE.capture(
            tmp_path,
            {"hook_event_name": "Stop", "agent_id": "subagent"},
        )
        == 0
    )
    assert (
        STOP_CAPTURE.capture(
            tmp_path,
            {"hook_event_name": "StopFailure", "session_id": "x"},
        )
        == 0
    )
    assert not (tmp_path / ".remember" / "turns").exists()


def test_cleanup_retains_newest_verified_segment(tmp_path: Path) -> None:
    turns = tmp_path / ".remember" / "turns"
    turns.mkdir(parents=True)
    summary = tmp_path / ".remember" / "memory" / "2026-08-12.md"
    summary.parent.mkdir()
    summary.write_text("summary", encoding="utf-8")
    root = str(tmp_path.resolve())
    for index in range(2):
        record = {
            "project_root": root,
            "captured_at": f"2026-08-12T00:0{index}:00Z",
            "summarized_at": f"2026-08-12T00:0{index}:00Z",
            "summary_path": ".remember/memory/2026-08-12.md",
        }
        (turns / f"{index}.json").write_text(json.dumps(record), encoding="utf-8")

    assert STOP_CAPTURE.cleanup_candidates(tmp_path) == [turns / "0.json"]
