#!/usr/bin/env python3
"""Inspect, mark, and clean shared Remember lifecycle segments.

The store is a single flat directory, ``.remember/turns/``, shared by every
toolchain that captures lifecycle segments.  Records are ``version: 3`` JSON
objects named ``{platform}-{kind}-{key}.json``; ``platform`` is a record field,
never a directory.  This module is the sole authority on the v3 schema: capture,
validation, and CLI paths all read it from here.

There is no reader for any earlier format.  A file that is not a valid v3
record is skipped as malformed: never parsed, never stamped, never deleted.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SEGMENT_VERSION = 3
PLATFORM = "claude"
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


def now_stamp() -> str:
    """Return the fixed-width UTC stamp the contract requires."""
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def turns_dir(root: Path) -> Path:
    return root / ".remember" / "turns"


def segment_filename(platform: str, kind: str, key: str) -> str:
    return f"{platform}-{kind}-{key}.json"


def memory_dir(root: Path) -> Path:
    return root / ".remember" / "memory"


def summary_inside_memory(root: Path, value: str) -> bool:
    """Return whether ``value`` is a relative path inside ``.remember/memory``."""
    path = Path(value)
    if path.is_absolute():
        return False
    return (root / path).resolve().parent == memory_dir(root).resolve()


def summary_target(root: Path, value: str) -> Path | None:
    """Return the existing journal file named by ``value``, or ``None``."""
    if not summary_inside_memory(root, value):
        return None
    target = (root / Path(value)).resolve()
    return target if target.is_file() else None


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value)


def valid_segment(root: Path, path: Path, record: Any) -> bool:
    """Return whether ``record`` is a v3 segment belonging to ``root``."""
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
    # Pairing rule: both set or both null; anything else is rejected, not repaired.
    if not _nonempty_str(summarized) or not _nonempty_str(summary):
        return False
    if not TIMESTAMP_RE.match(summarized):
        return False
    return summary_inside_memory(root, summary)


def read_segments(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Return every valid v3 segment in the flat store, malformed files skipped."""
    directory = turns_dir(root)
    try:
        paths = sorted(directory.glob("*.json"))
    except OSError:
        return []
    result: list[tuple[Path, dict[str, Any]]] = []
    for path in paths:
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if valid_segment(root, path, record):
            result.append((path, record))
    return result


def eligible_segments(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    """Return unsummarized segments from every platform, oldest first."""
    pending = [
        (path, record)
        for path, record in read_segments(root)
        if record["summarized_at"] is None
    ]
    return sorted(pending, key=lambda item: (item[1]["captured_at"], item[0].name))


def platform_counts(records: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(record["platform"] for record in records)
    return {platform: counts.get(platform, 0) for platform in SEGMENT_PLATFORMS}


def atomic_write(path: Path, record: dict[str, Any]) -> None:
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f".{path.name}.",
        suffix=".tmp",
        delete=False,
    )
    temporary = Path(handle.name)
    try:
        with handle:
            handle.write(json.dumps(record, indent=2, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def mark_summarized(root: Path, summary_path: str) -> dict[str, Any]:
    """Stamp every pending segment with one checkpoint, regardless of platform."""
    if summary_target(root, summary_path) is None:
        return {"error": "summary_path_missing_or_outside_memory"}
    pending = eligible_segments(root)
    stamp = now_stamp()
    for path, record in pending:
        updated = dict(record)
        updated["summarized_at"] = stamp
        updated["summary_path"] = summary_path
        atomic_write(path, updated)
    return {
        "marked": len(pending),
        "platforms": platform_counts([record for _, record in pending]),
        "summarized_at": stamp,
        "summary_path": summary_path,
    }


def cleanup_candidates(root: Path) -> list[Path]:
    """Return retired segments: verified, but not in the newest checkpoint."""
    verified = [
        (path, record)
        for path, record in read_segments(root)
        if isinstance(record["summary_path"], str)
        and summary_target(root, record["summary_path"]) is not None
    ]
    newest_checkpoint = max(
        ((record["summarized_at"], record["summary_path"]) for _, record in verified),
        default=("", ""),
    )
    return [
        path
        for path, record in verified
        if (record["summarized_at"], record["summary_path"]) != newest_checkpoint
    ]


def clean(root: Path, apply: bool) -> dict[str, Any]:
    candidates = cleanup_candidates(root)
    if apply:
        for path in candidates:
            path.unlink()
    return {
        "apply": apply,
        "segments": [str(path.relative_to(root)) for path in candidates],
    }


def pending_payload(root: Path) -> dict[str, Any]:
    segments = eligible_segments(root)
    return {
        "segments": [
            {
                "path": str(path.relative_to(root)),
                "platform": record["platform"],
                "kind": record["kind"],
                "key": record["key"],
                "session_id": record["session_id"],
                "captured_at": record["captured_at"],
                "reason": record["reason"],
                "text": record["text"],
            }
            for path, record in segments
        ],
        "platforms": platform_counts([record for _, record in segments]),
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("pending", "mark-summarized", "clean"))
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--summary-path")
    parser.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    result: dict[str, Any]
    if args.command == "pending":
        result = pending_payload(root)
    elif args.command == "mark-summarized":
        if not args.summary_path:
            build_parser().error("mark-summarized requires --summary-path")
        result = mark_summarized(root, args.summary_path)
    else:
        result = clean(root, args.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 1 if result.get("error") else 0


if __name__ == "__main__":
    raise SystemExit(main())
