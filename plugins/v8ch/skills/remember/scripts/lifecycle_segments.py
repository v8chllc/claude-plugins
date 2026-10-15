#!/usr/bin/env python3
"""Inspect, mark, and clean shared Remember lifecycle segments.

The store is a single flat directory, ``.remember/turns/``, shared by every
toolchain that captures lifecycle segments.  Records are ``version: 3`` JSON
objects named ``{platform}-{kind}-{key}.json``; ``platform`` is a record field,
never a directory. The shared ``memory/scripts/segment_format.py`` owns the
v3 parser used by validation and this lifecycle CLI.

There is no reader for any earlier format.  A file that is not a valid v3
record is skipped as malformed: never parsed, never stamped, never deleted.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from collections import Counter
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[3] / "memory" / "scripts"))
from segment_format import (  # noqa: E402
    SEGMENT_FIELDS as SEGMENT_FIELDS,
)
from segment_format import (
    SEGMENT_PLATFORMS,
    TIMESTAMP_FORMAT,
    summary_target,
    valid_segment,
)
from segment_format import (
    TIMESTAMP_RE as TIMESTAMP_RE,
)
from segment_format import (
    segment_filename as segment_filename,
)
from segment_format import (
    summary_inside_memory as summary_inside_memory,
)

PLATFORM = "claude"


def now_stamp() -> str:
    """Return the fixed-width UTC stamp the contract requires."""
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def turns_dir(root: Path) -> Path:
    return root / ".remember" / "turns"


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
