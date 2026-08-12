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
    / "lifecycle_capture.py"
)
SPEC = importlib.util.spec_from_file_location("lifecycle_capture", SCRIPT)
assert SPEC and SPEC.loader
CAPTURE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(CAPTURE)

SEGMENT_SCRIPT = SCRIPT.with_name("lifecycle_segments.py")
SEGMENT_SPEC = importlib.util.spec_from_file_location(
    "lifecycle_segments", SEGMENT_SCRIPT
)
assert SEGMENT_SPEC and SEGMENT_SPEC.loader
SEGMENTS = importlib.util.module_from_spec(SEGMENT_SPEC)
SEGMENT_SPEC.loader.exec_module(SEGMENTS)

STOP_PAYLOAD = {
    "hook_event_name": "Stop",
    "session_id": "session-1",
    "last_assistant_message": "Completed the task.",
}


def initialize_memory(root: Path) -> None:
    (root / ".remember" / "memory").mkdir(parents=True)
    (root / ".remember" / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")


def segments(root: Path) -> list[Path]:
    return sorted((root / ".remember" / "turns").glob("*.json"))


def write_transcript(root: Path, text: str) -> Path:
    path = root / "transcript.jsonl"
    lines = [
        {"type": "user", "message": {"role": "user", "content": "hi"}},
        {
            "type": "assistant",
            "message": {
                "role": "assistant",
                "content": [{"type": "text", "text": text}],
            },
        },
    ]
    path.write_text(
        "\n".join(json.dumps(line) for line in lines) + "\n", encoding="utf-8"
    )
    return path


def test_stop_writes_one_idempotent_main_agent_segment(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop") == 0
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop") == 0

    paths = segments(tmp_path)
    assert len(paths) == 1
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["version"] == 3
    assert record["platform"] == "claude"
    assert record["kind"] == "stop"
    assert record["session_id"] == "session-1"
    assert record["text"] == "Completed the task."
    assert record["reason"] is None
    assert record["summarized_at"] is None
    assert record["summary_path"] is None
    assert set(record) == set(SEGMENTS.SEGMENT_FIELDS)
    assert paths[0].name == f"claude-stop-{record['key']}.json"
    assert SEGMENTS.TIMESTAMP_RE.match(record["captured_at"])
    assert SEGMENTS.valid_segment(tmp_path, paths[0], record)


def test_capture_ignores_subagents_and_mismatched_events(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    assert CAPTURE.capture(tmp_path, {**STOP_PAYLOAD, "agent_id": "sub"}, "stop") == 0
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "session-end") == 0
    assert CAPTURE.capture(tmp_path, {"hook_event_name": "Stop"}, "stop") == 0
    assert not (tmp_path / ".remember" / "turns").exists()


def test_capture_allows_a_main_session_started_with_a_custom_agent(
    tmp_path: Path,
) -> None:
    initialize_memory(tmp_path)
    payload = {**STOP_PAYLOAD, "agent_type": "custom-main-agent"}

    assert CAPTURE.capture(tmp_path, payload, "stop") == 0
    assert len(segments(tmp_path)) == 1


def test_session_end_uses_transcript_fallback(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "session-2",
        "reason": "clear",
        "transcript_path": str(write_transcript(tmp_path, "Final answer.")),
    }

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0
    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0

    paths = segments(tmp_path)
    assert len(paths) == 1
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["kind"] == "session-end"
    assert record["reason"] == "clear"
    assert record["text"] == "Final answer."
    assert record["transcript_path"] == str(tmp_path / "transcript.jsonl")
    assert SEGMENTS.valid_segment(tmp_path, paths[0], record)


def test_session_end_does_not_duplicate_a_stop_message(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop") == 0
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "session-1",
        "reason": "logout",
        "transcript_path": str(write_transcript(tmp_path, "Completed the task.")),
    }

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0

    records = [
        json.loads(path.read_text(encoding="utf-8")) for path in segments(tmp_path)
    ]
    terminal = [record for record in records if record["kind"] == "session-end"]
    assert len(records) == 2
    assert terminal[0]["text"] == ""
    assert terminal[0]["reason"] == "logout"


def test_session_end_records_terminal_context_without_a_transcript(
    tmp_path: Path,
) -> None:
    initialize_memory(tmp_path)
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "session-3",
        "reason": "other",
    }

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0

    path = segments(tmp_path)[0]
    record = json.loads(path.read_text(encoding="utf-8"))
    assert record["reason"] == "other"
    assert record["text"] == ""
    assert record["transcript_path"] is None
    assert SEGMENTS.valid_segment(tmp_path, path, record)


def test_session_end_survives_an_unreadable_transcript(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "session-4",
        "reason": "other",
        "transcript_path": str(tmp_path / "missing.jsonl"),
    }

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0
    assert len(segments(tmp_path)) == 1


def test_session_end_ignores_invalid_utf8_in_transcript(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    transcript = tmp_path / "transcript.jsonl"
    transcript.write_bytes(b"\xff\xfe\n")
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "session-4",
        "reason": "other",
        "transcript_path": str(transcript),
    }

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0
    assert len(segments(tmp_path)) == 1


def test_capture_skips_uninitialized_memory_and_missing_session_end_reason(
    tmp_path: Path,
) -> None:
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop") == 0
    assert segments(tmp_path) == []

    initialize_memory(tmp_path)
    payload = {"hook_event_name": "SessionEnd", "session_id": "session-1"}
    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0
    assert segments(tmp_path) == []


def test_main_exits_quietly_on_malformed_stdin(tmp_path: Path, monkeypatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert CAPTURE.main(["--root", str(tmp_path), "--kind", "stop"]) == 0
    assert not (tmp_path / ".remember").exists()
