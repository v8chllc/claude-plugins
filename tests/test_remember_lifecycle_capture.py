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

STOP_PAYLOAD = {
    "hook_event_name": "Stop",
    "session_id": "session-1",
    "last_assistant_message": "Completed the task.",
}


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
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop") == 0
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop") == 0

    paths = segments(tmp_path)
    assert len(paths) == 1
    record = json.loads(paths[0].read_text(encoding="utf-8"))
    assert record["kind"] == "stop"
    assert record["session_id"] == "session-1"
    assert record["last_assistant_message"] == "Completed the task."


def test_capture_ignores_subagents_and_mismatched_events(tmp_path: Path) -> None:
    assert CAPTURE.capture(tmp_path, {**STOP_PAYLOAD, "agent_id": "sub"}, "stop") == 0
    assert CAPTURE.capture(tmp_path, {**STOP_PAYLOAD, "agent_type": "sub"}, "stop") == 0
    assert CAPTURE.capture(tmp_path, STOP_PAYLOAD, "session-end") == 0
    assert CAPTURE.capture(tmp_path, {"hook_event_name": "Stop"}, "stop") == 0
    assert not (tmp_path / ".remember" / "turns").exists()


def test_session_end_uses_transcript_fallback(tmp_path: Path) -> None:
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
    assert record["last_assistant_message"] == "Final answer."


def test_session_end_does_not_duplicate_a_stop_message(tmp_path: Path) -> None:
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
    assert "last_assistant_message" not in terminal[0]
    assert terminal[0]["reason"] == "logout"


def test_session_end_records_terminal_context_without_a_transcript(
    tmp_path: Path,
) -> None:
    payload = {"hook_event_name": "SessionEnd", "session_id": "session-3"}

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0

    record = json.loads(segments(tmp_path)[0].read_text(encoding="utf-8"))
    assert record["reason"] == "other"
    assert "last_assistant_message" not in record


def test_session_end_survives_an_unreadable_transcript(tmp_path: Path) -> None:
    payload = {
        "hook_event_name": "SessionEnd",
        "session_id": "session-4",
        "reason": "other",
        "transcript_path": str(tmp_path / "missing.jsonl"),
    }

    assert CAPTURE.capture(tmp_path, payload, "session-end") == 0
    assert len(segments(tmp_path)) == 1


def test_eligible_segments_include_both_kinds_and_skip_invalid(tmp_path: Path) -> None:
    CAPTURE.capture(tmp_path, STOP_PAYLOAD, "stop")
    CAPTURE.capture(
        tmp_path,
        {"hook_event_name": "SessionEnd", "session_id": "session-1", "reason": "clear"},
        "session-end",
    )
    turns = tmp_path / ".remember" / "turns"
    (turns / "broken.json").write_text("{not json", encoding="utf-8")
    (turns / "foreign.json").write_text(
        json.dumps({"kind": "stop", "project_root": "/elsewhere"}), encoding="utf-8"
    )
    (turns / "unknown.json").write_text(
        json.dumps({"kind": "prompt", "project_root": str(tmp_path.resolve())}),
        encoding="utf-8",
    )

    kinds = sorted(record["kind"] for _, record in CAPTURE.eligible_segments(tmp_path))
    assert kinds == ["session-end", "stop"]


def test_cleanup_retains_newest_verified_segment_across_kinds(tmp_path: Path) -> None:
    turns = tmp_path / ".remember" / "turns"
    turns.mkdir(parents=True)
    summary = tmp_path / ".remember" / "memory" / "2026-08-12.md"
    summary.parent.mkdir()
    summary.write_text("summary", encoding="utf-8")
    root = str(tmp_path.resolve())
    for index, kind in enumerate(("stop", "session-end")):
        record = {
            "kind": kind,
            "project_root": root,
            "captured_at": f"2026-08-12T00:0{index}:00Z",
            "summarized_at": f"2026-08-12T00:0{index}:00Z",
            "summary_path": ".remember/memory/2026-08-12.md",
        }
        (turns / f"{kind}-{index}.json").write_text(
            json.dumps(record), encoding="utf-8"
        )
    unverified = {
        "kind": "stop",
        "project_root": root,
        "summarized_at": "2026-08-12T00:00:00Z",
        "summary_path": ".remember/memory/missing.md",
    }
    (turns / "stop-unverified.json").write_text(
        json.dumps(unverified), encoding="utf-8"
    )

    assert CAPTURE.cleanup_candidates(tmp_path) == [turns / "stop-0.json"]


def test_main_exits_quietly_on_malformed_stdin(tmp_path: Path, monkeypatch) -> None:
    import io

    monkeypatch.setattr("sys.stdin", io.StringIO("not json"))
    assert CAPTURE.main(["--root", str(tmp_path), "--kind", "stop"]) == 0
    assert not (tmp_path / ".remember").exists()
