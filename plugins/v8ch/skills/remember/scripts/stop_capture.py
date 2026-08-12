#!/usr/bin/env python3
"""Project-local storage for opt-in Claude Code Stop capture.

Copy this file to ``.claude/hooks/remember-stop-capture.py`` when enabling the
hook.  The capture command receives Claude's Stop hook payload on stdin and
never writes curated or procedural memory.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path


def segment_key(session_id: str, message: str) -> str:
    return hashlib.sha256(f"{session_id}\0{message}".encode()).hexdigest()


def capture(root: Path, payload: dict[str, object]) -> int:
    if payload.get("agent_id") or payload.get("hook_event_name") != "Stop":
        return 0
    session_id = payload.get("session_id")
    message = payload.get("last_assistant_message")
    if not isinstance(session_id, str) or not isinstance(message, str) or not message:
        return 0
    key = segment_key(session_id, message)
    turns = root / ".remember" / "turns"
    turns.mkdir(parents=True, exist_ok=True)
    path = turns / f"{key}.json"
    if path.exists():
        return 0
    record = {
        "version": 1,
        "idempotency_key": key,
        "project_root": str(root.resolve()),
        "session_id": session_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "last_assistant_message": message,
    }
    path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return 0


def eligible_segments(root: Path) -> list[tuple[Path, dict[str, object]]]:
    """Return valid unsummarized segments for this project in capture order."""
    result: list[tuple[Path, dict[str, object]]] = []
    for path in (root / ".remember" / "turns").glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if (
            isinstance(record, dict)
            and record.get("project_root") == str(root.resolve())
            and not record.get("summarized_at")
        ):
            result.append((path, record))
    return sorted(result, key=lambda item: str(item[1].get("captured_at", "")))


def cleanup_candidates(root: Path) -> list[Path]:
    """Return only older verified summarized files that are safe to remove."""
    verified: list[tuple[Path, dict[str, object]]] = []
    for path in (root / ".remember" / "turns").glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        summary = record.get("summary_path") if isinstance(record, dict) else None
        if (
            isinstance(record, dict)
            and record.get("project_root") == str(root.resolve())
            and record.get("summarized_at")
            and isinstance(summary, str)
            and (root / summary).is_file()
        ):
            verified.append((path, record))
    verified.sort(key=lambda item: str(item[1].get("summarized_at", "")))
    return [path for path, _ in verified[:-1]]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", default=".")
    args = parser.parse_args()
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        return 0
    return capture(Path(args.root), payload if isinstance(payload, dict) else {})


if __name__ == "__main__":
    raise SystemExit(main())
