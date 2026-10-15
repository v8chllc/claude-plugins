"""Shared version-3 lifecycle segment schema used by memory validation."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

SEGMENT_VERSION = 3
SEGMENT_PLATFORMS = ("claude", "codex")
STOP_KIND = "stop"
SESSION_END_KIND = "session-end"
SEGMENT_KINDS = (STOP_KIND, SESSION_END_KIND)
SEGMENT_FIELDS = frozenset(
    {
        "version",
        "platform",
        "kind",
        "key",
        "project_root",
        "session_id",
        "captured_at",
        "text",
        "reason",
        "transcript_path",
        "summarized_at",
        "summary_path",
    }
)
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"
TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{6}Z$")


def segment_filename(platform: str, kind: str, key: str) -> str:
    return f"{platform}-{kind}-{key}.json"


def memory_dir(root: Path) -> Path:
    return root / ".remember" / "memory"


def summary_inside_memory(root: Path, value: str) -> bool:
    """Return whether a relative summary path stays inside the journal directory."""
    path = Path(value)
    if path.is_absolute():
        return False
    return (root / path).resolve().parent == memory_dir(root).resolve()


def summary_target(root: Path, value: str) -> Path | None:
    """Return the existing journal file named by a valid relative path."""
    if not summary_inside_memory(root, value):
        return None
    target = (root / Path(value)).resolve()
    return target if target.is_file() else None


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def valid_segment(root: Path, path: Path, record: Any) -> bool:
    """Return whether a version-3 segment belongs to this project root."""
    if not isinstance(record, dict) or set(record) != SEGMENT_FIELDS:
        return False
    if record["version"] != SEGMENT_VERSION:
        return False
    platform = record["platform"]
    kind = record["kind"]
    key = record["key"]
    if platform not in SEGMENT_PLATFORMS or kind not in SEGMENT_KINDS:
        return False
    if not _nonempty_str(key):
        return False
    if path.name != segment_filename(platform, kind, key):
        return False
    if not _nonempty_str(record["session_id"]):
        return False
    if record["project_root"] != str(root.resolve()):
        return False
    if not isinstance(record["captured_at"], str) or not TIMESTAMP_RE.match(
        record["captured_at"]
    ):
        return False
    if not isinstance(record["text"], str):
        return False
    reason = record["reason"]
    if kind == STOP_KIND:
        if reason is not None:
            return False
    elif not _nonempty_str(reason):
        return False
    transcript = record["transcript_path"]
    if transcript is not None and not _nonempty_str(transcript):
        return False
    summarized = record["summarized_at"]
    summary = record["summary_path"]
    if summarized is None and summary is None:
        return True
    if not _nonempty_str(summarized) or not _nonempty_str(summary):
        return False
    if not TIMESTAMP_RE.match(summarized):
        return False
    return summary_inside_memory(root, summary)
