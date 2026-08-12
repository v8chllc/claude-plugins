#!/usr/bin/env python3
"""Inspect, mark, and clean Claude Remember lifecycle segments."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

SEGMENT_VERSION = 1
SEGMENT_KINDS = ("stop", "session-end")


def turns_dir(root: Path) -> Path:
    return root / ".remember" / "turns"


def summary_target(root: Path, value: str) -> Path | None:
    path = Path(value)
    if path.is_absolute():
        return None
    target = (root / path).resolve()
    memory = (root / ".remember" / "memory").resolve()
    if target.parent != memory or not target.is_file():
        return None
    return target


def valid_segment(root: Path, path: Path, record: Any) -> bool:
    if not isinstance(record, dict) or record.get("version") != SEGMENT_VERSION:
        return False
    kind = record.get("kind")
    key = record.get("idempotency_key")
    if kind not in SEGMENT_KINDS or not isinstance(key, str) or not key:
        return False
    if path.name != f"{kind}-{key}.json":
        return False
    required = ("project_root", "session_id", "captured_at")
    if not all(
        isinstance(record.get(field), str) and record[field] for field in required
    ):
        return False
    if record["project_root"] != str(root.resolve()):
        return False
    if kind == "stop" and not isinstance(record.get("last_assistant_message"), str):
        return False
    if kind == "session-end" and not isinstance(record.get("reason"), str):
        return False
    summarized = record.get("summarized_at")
    summary = record.get("summary_path")
    return (summarized is None and summary is None) or (
        isinstance(summarized, str)
        and bool(summarized)
        and isinstance(summary, str)
        and bool(summary)
    )


def read_segments(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    result: list[tuple[Path, dict[str, Any]]] = []
    for path in turns_dir(root).glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            continue
        if valid_segment(root, path, record):
            result.append((path, record))
    return result


def eligible_segments(root: Path) -> list[tuple[Path, dict[str, Any]]]:
    pending = [
        (path, record)
        for path, record in read_segments(root)
        if record.get("summarized_at") is None
    ]
    return sorted(pending, key=lambda item: (item[1]["captured_at"], item[0].name))


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
    if summary_target(root, summary_path) is None:
        return {"error": "summary_path_missing_or_outside_memory"}
    pending = eligible_segments(root)
    stamp = datetime.now(UTC).isoformat()
    for path, record in pending:
        updated = dict(record)
        updated["summarized_at"] = stamp
        updated["summary_path"] = summary_path
        atomic_write(path, updated)
    return {
        "marked": len(pending),
        "summarized_at": stamp,
        "summary_path": summary_path,
    }


def cleanup_candidates(root: Path) -> list[Path]:
    verified = [
        (path, record)
        for path, record in read_segments(root)
        if isinstance(record.get("summary_path"), str)
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
    if args.command == "pending":
        result: dict[str, Any] = {
            "segments": [
                {
                    "path": str(path.relative_to(root)),
                    "kind": record["kind"],
                    "captured_at": record["captured_at"],
                }
                for path, record in eligible_segments(root)
            ]
        }
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
