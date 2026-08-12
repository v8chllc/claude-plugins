#!/usr/bin/env python3
"""Tests for the shared version-3 lifecycle segment store."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

SCRIPT = (
    Path(__file__).parents[1]
    / "plugins"
    / "v8ch"
    / "skills"
    / "remember"
    / "scripts"
    / "lifecycle_segments.py"
)
SPEC = importlib.util.spec_from_file_location("lifecycle_segments", SCRIPT)
assert SPEC and SPEC.loader
SEGMENTS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(SEGMENTS)

CAPTURE_SCRIPT = SCRIPT.with_name("lifecycle_capture.py")
CAPTURE_SPEC = importlib.util.spec_from_file_location(
    "lifecycle_capture", CAPTURE_SCRIPT
)
assert CAPTURE_SPEC and CAPTURE_SPEC.loader
CAPTURE = importlib.util.module_from_spec(CAPTURE_SPEC)
CAPTURE_SPEC.loader.exec_module(CAPTURE)

SUMMARY_RELATIVE = ".remember/memory/2026-08-12.md"


def initialize_memory(root: Path) -> Path:
    (root / ".remember" / "memory").mkdir(parents=True)
    (root / ".remember" / "MEMORY.md").write_text("# Memory\n", encoding="utf-8")
    summary = root / SUMMARY_RELATIVE
    summary.write_text("summary\n", encoding="utf-8")
    return summary


def turns(root: Path) -> Path:
    return root / ".remember" / "turns"


def record(
    root: Path,
    *,
    platform: str = "claude",
    kind: str = "stop",
    key: str = "key-1",
    session_id: str = "session-1",
    captured_at: str = "2026-08-12T00:00:00.000000Z",
    text: str = "done",
    reason: str | None = None,
    transcript_path: str | None = None,
    summarized_at: str | None = None,
    summary_path: str | None = None,
) -> dict[str, Any]:
    return {
        "version": 3,
        "platform": platform,
        "kind": kind,
        "key": key,
        "project_root": str(root.resolve()),
        "session_id": session_id,
        "captured_at": captured_at,
        "text": text,
        "reason": reason,
        "transcript_path": transcript_path,
        "summarized_at": summarized_at,
        "summary_path": summary_path,
    }


def write(root: Path, payload: dict[str, Any]) -> Path:
    turns(root).mkdir(parents=True, exist_ok=True)
    name: str = SEGMENTS.segment_filename(
        payload["platform"], payload["kind"], payload["key"]
    )
    path = turns(root) / name
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def read(path: Path) -> dict[str, Any]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return data


def run_cli(root: Path, *args: str) -> dict[str, Any]:
    process = subprocess.run(
        [sys.executable, str(SCRIPT), *args, "--root", str(root)],
        capture_output=True,
        text=True,
        check=False,
        timeout=60,
    )
    assert process.returncode == 0, process.stderr
    result: dict[str, Any] = json.loads(process.stdout)
    return result


# --- Round trip ---------------------------------------------------------


def test_v3_round_trip_from_capture_through_stamping(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    CAPTURE.capture(
        tmp_path,
        {
            "hook_event_name": "Stop",
            "session_id": "session-1",
            "last_assistant_message": "Completed the task.",
        },
        "stop",
    )

    pending = SEGMENTS.eligible_segments(tmp_path)
    assert len(pending) == 1
    path, stored = pending[0]
    assert stored["version"] == 3
    assert stored["platform"] == "claude"
    assert path.name == SEGMENTS.segment_filename("claude", "stop", stored["key"])

    result = SEGMENTS.mark_summarized(tmp_path, SUMMARY_RELATIVE)

    assert result["marked"] == 1
    stamped = read(path)
    assert stamped["summarized_at"] == result["summarized_at"]
    assert stamped["summary_path"] == SUMMARY_RELATIVE
    assert SEGMENTS.valid_segment(tmp_path, path, stamped)
    assert SEGMENTS.eligible_segments(tmp_path) == []


def test_capture_writes_a_flat_store_with_no_subdirectories(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    CAPTURE.capture(
        tmp_path,
        {
            "hook_event_name": "Stop",
            "session_id": "session-1",
            "last_assistant_message": "Completed the task.",
        },
        "stop",
    )

    assert [item for item in turns(tmp_path).iterdir() if item.is_dir()] == []


# --- Mixed-platform discovery and stamping ------------------------------


def test_pending_returns_both_platforms_ordered_by_captured_at(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    write(
        tmp_path,
        record(
            tmp_path,
            platform="claude",
            key="claude-1",
            captured_at="2026-08-12T00:00:02.000000Z",
        ),
    )
    write(
        tmp_path,
        record(
            tmp_path,
            platform="codex",
            key="codex-1",
            captured_at="2026-08-12T00:00:01.000000Z",
        ),
    )

    payload = run_cli(tmp_path, "pending")

    assert [item["platform"] for item in payload["segments"]] == ["codex", "claude"]
    stamps = [item["captured_at"] for item in payload["segments"]]
    assert stamps == sorted(stamps)
    assert payload["platforms"] == {"claude": 1, "codex": 1}


def test_mark_summarized_stamps_every_platform_with_one_checkpoint(
    tmp_path: Path,
) -> None:
    initialize_memory(tmp_path)
    paths = [
        write(tmp_path, record(tmp_path, platform="claude", key="claude-1")),
        write(
            tmp_path,
            record(
                tmp_path,
                platform="codex",
                kind="session-end",
                key="codex-1",
                text="",
                reason="clear",
                captured_at="2026-08-12T00:00:01.000000Z",
            ),
        ),
    ]

    result = SEGMENTS.mark_summarized(tmp_path, SUMMARY_RELATIVE)

    assert result["marked"] == 2
    assert result["platforms"] == {"claude": 1, "codex": 1}
    assert {read(path)["summarized_at"] for path in paths} == {result["summarized_at"]}
    assert SEGMENTS.eligible_segments(tmp_path) == []


def test_already_stamped_segments_are_not_restamped(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    path = write(
        tmp_path,
        record(
            tmp_path,
            platform="codex",
            key="codex-1",
            summarized_at="2026-08-12T00:00:00.000000Z",
            summary_path=SUMMARY_RELATIVE,
        ),
    )
    before = path.read_bytes()

    assert SEGMENTS.mark_summarized(tmp_path, SUMMARY_RELATIVE)["marked"] == 0
    assert path.read_bytes() == before


def test_mark_summarized_rejects_a_summary_outside_memory(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    path = write(tmp_path, record(tmp_path))

    result = SEGMENTS.mark_summarized(tmp_path, "notes/2026-08-12.md")

    assert result == {"error": "summary_path_missing_or_outside_memory"}
    assert read(path)["summarized_at"] is None


# --- Malformed and legacy input -----------------------------------------


def test_legacy_v1_and_v2_files_are_skipped_never_stamped_or_deleted(
    tmp_path: Path,
) -> None:
    initialize_memory(tmp_path)
    turns(tmp_path).mkdir(parents=True, exist_ok=True)
    legacy_v1 = turns(tmp_path) / "stop-deadbeef.json"
    legacy_v1.write_text(
        json.dumps(
            {
                "version": 1,
                "kind": "stop",
                "idempotency_key": "deadbeef",
                "project_root": str(tmp_path.resolve()),
                "session_id": "legacy",
                "captured_at": "2026-08-12T14:39:31+00:00",
                "last_assistant_message": "legacy v1",
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    legacy_v2 = turns(tmp_path) / "legacy-v2.md"
    legacy_v2.write_text(
        "<!-- remember-turn\nversion: 2\nplatform: codex\n-->\n\nlegacy v2\n",
        encoding="utf-8",
    )
    broken = turns(tmp_path) / "claude-stop-broken.json"
    broken.write_text("{not json", encoding="utf-8")
    before = (legacy_v1.read_bytes(), legacy_v2.read_bytes(), broken.read_bytes())
    write(tmp_path, record(tmp_path, key="live-1"))

    pending = SEGMENTS.eligible_segments(tmp_path)

    assert [item[1]["key"] for item in pending] == ["live-1"]
    SEGMENTS.mark_summarized(tmp_path, SUMMARY_RELATIVE)
    SEGMENTS.clean(tmp_path, apply=True)
    assert (
        legacy_v1.read_bytes(),
        legacy_v2.read_bytes(),
        broken.read_bytes(),
    ) == before


def test_half_written_summarized_pair_is_rejected(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    write(
        tmp_path,
        record(
            tmp_path,
            key="half-1",
            summarized_at="2026-08-12T00:00:00.000000Z",
            summary_path=None,
        ),
    )
    write(
        tmp_path,
        record(
            tmp_path,
            key="half-2",
            captured_at="2026-08-12T00:00:01.000000Z",
            summarized_at=None,
            summary_path=SUMMARY_RELATIVE,
        ),
    )

    assert SEGMENTS.read_segments(tmp_path) == []
    assert SEGMENTS.eligible_segments(tmp_path) == []


def test_records_with_unknown_or_missing_keys_are_invalid(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    extra = record(tmp_path, key="extra-1")
    extra["last_assistant_message"] = "legacy field"
    path = write(tmp_path, extra)
    assert not SEGMENTS.valid_segment(tmp_path, path, extra)

    missing = record(tmp_path, key="missing-1")
    del missing["transcript_path"]
    path = write(tmp_path, missing)
    assert not SEGMENTS.valid_segment(tmp_path, path, missing)


def test_offset_and_second_precision_timestamps_are_invalid(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    for stamp in ("2026-08-12T14:39:31Z", "2026-08-12T14:50:28.391649+00:00"):
        candidate = record(tmp_path, key="ts-1", captured_at=stamp)
        path = write(tmp_path, candidate)
        assert not SEGMENTS.valid_segment(tmp_path, path, candidate)


def test_records_from_another_project_or_platform_are_invalid(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    foreign = record(tmp_path, key="foreign-1")
    foreign["project_root"] = "/elsewhere"
    path = write(tmp_path, foreign)
    assert not SEGMENTS.valid_segment(tmp_path, path, foreign)

    unknown = record(tmp_path, platform="warp", key="warp-1")
    path = write(tmp_path, unknown)
    assert not SEGMENTS.valid_segment(tmp_path, path, unknown)


def test_filename_must_match_platform_kind_and_key(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    turns(tmp_path).mkdir(parents=True, exist_ok=True)
    payload = record(tmp_path, key="mismatch-1")
    path = turns(tmp_path) / "codex-stop-mismatch-1.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    assert not SEGMENTS.valid_segment(tmp_path, path, payload)
    assert SEGMENTS.read_segments(tmp_path) == []


def test_empty_text_session_end_record_is_valid(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    payload = record(
        tmp_path,
        kind="session-end",
        key="end-1",
        text="",
        reason="clear",
        transcript_path=str(tmp_path / "transcript.jsonl"),
    )
    path = write(tmp_path, payload)

    assert SEGMENTS.valid_segment(tmp_path, path, payload)
    assert [item[1]["key"] for item in SEGMENTS.eligible_segments(tmp_path)] == [
        "end-1"
    ]


def test_stop_reason_must_be_null_and_session_end_reason_must_be_set(
    tmp_path: Path,
) -> None:
    initialize_memory(tmp_path)
    stop_with_reason = record(tmp_path, key="stop-1", reason="clear")
    path = write(tmp_path, stop_with_reason)
    assert not SEGMENTS.valid_segment(tmp_path, path, stop_with_reason)

    end_without_reason = record(tmp_path, kind="session-end", key="end-1", reason=None)
    path = write(tmp_path, end_without_reason)
    assert not SEGMENTS.valid_segment(tmp_path, path, end_without_reason)


def test_missing_store_degrades_to_no_segments(tmp_path: Path) -> None:
    assert SEGMENTS.read_segments(tmp_path) == []
    assert SEGMENTS.eligible_segments(tmp_path) == []
    assert run_cli(tmp_path, "pending")["segments"] == []


# --- Cleanup ------------------------------------------------------------


def test_cleanup_retires_older_checkpoints_across_platforms(tmp_path: Path) -> None:
    initialize_memory(tmp_path)
    memory = tmp_path / ".remember" / "memory"
    (memory / "old.md").write_text("old\n", encoding="utf-8")
    old = write(
        tmp_path,
        record(
            tmp_path,
            platform="codex",
            key="codex-old",
            summarized_at="2026-08-11T00:00:00.000000Z",
            summary_path=".remember/memory/old.md",
        ),
    )
    kept = [
        write(
            tmp_path,
            record(
                tmp_path,
                platform="claude",
                key="claude-new",
                summarized_at="2026-08-12T00:00:00.000000Z",
                summary_path=SUMMARY_RELATIVE,
            ),
        ),
        write(
            tmp_path,
            record(
                tmp_path,
                platform="codex",
                kind="session-end",
                key="codex-new",
                text="",
                reason="clear",
                summarized_at="2026-08-12T00:00:00.000000Z",
                summary_path=SUMMARY_RELATIVE,
            ),
        ),
    ]
    unverifiable = write(
        tmp_path,
        record(
            tmp_path,
            platform="claude",
            key="claude-missing-summary",
            summarized_at="2026-08-12T00:00:00.000000Z",
            summary_path=".remember/memory/missing.md",
        ),
    )

    assert SEGMENTS.cleanup_candidates(tmp_path) == [old]

    SEGMENTS.clean(tmp_path, apply=True)

    assert not old.exists()
    assert all(path.exists() for path in kept)
    assert unverifiable.exists()
