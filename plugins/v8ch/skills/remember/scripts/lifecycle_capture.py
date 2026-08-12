#!/usr/bin/env python3
"""Project-local capture handler for opt-in Claude Code lifecycle hooks.

``hook_setup.py`` copies this file into ``.claude/hooks/`` once per enabled
channel and registers it with ``--kind stop`` or ``--kind session-end``.  The
handler reads a hook payload on stdin, writes at most one immutable segment
under ``.remember/turns/``, and never writes curated or procedural memory.

The handler is quiet: it prints nothing and always exits successfully so a
capture failure can never interrupt a Claude Code session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

SEGMENT_VERSION = 1
STOP_KIND = "stop"
SESSION_END_KIND = "session-end"
SEGMENT_KINDS = (STOP_KIND, SESSION_END_KIND)
HOOK_EVENTS = {STOP_KIND: "Stop", SESSION_END_KIND: "SessionEnd"}


def digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def stop_key(session_id: str, message: str) -> str:
    return digest(STOP_KIND, session_id, message)


def session_end_key(session_id: str, reason: str) -> str:
    return digest(SESSION_END_KIND, session_id, reason)


def turns_dir(root: Path) -> Path:
    return root / ".remember" / "turns"


def segment_path(root: Path, kind: str, key: str) -> Path:
    return turns_dir(root) / f"{kind}-{key}.json"


def transcript_message(payload: dict[str, object]) -> str | None:
    """Return the final assistant text from the transcript, if readable.

    SessionEnd payloads carry no ``last_assistant_message``, so terminal
    segments fall back to the transcript file named by the payload.
    """
    location = payload.get("transcript_path")
    if not isinstance(location, str) or not location:
        return None
    try:
        lines = Path(location).read_text(encoding="utf-8").splitlines()
    except OSError:
        return None
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str) and content.strip():
            return content
        if not isinstance(content, list):
            continue
        texts = [
            block["text"]
            for block in content
            if isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
        ]
        joined = "\n".join(text for text in texts if text.strip())
        if joined:
            return joined
    return None


def write_segment(path: Path, record: dict[str, object]) -> None:
    """Write one immutable segment, leaving any existing file untouched."""
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(record, indent=2, sort_keys=True) + "\n"
    try:
        with path.open("x", encoding="utf-8") as handle:
            handle.write(body)
    except (FileExistsError, OSError):
        return


def capture_stop(root: Path, payload: dict[str, object]) -> None:
    session_id = payload.get("session_id")
    message = payload.get("last_assistant_message")
    if not isinstance(session_id, str) or not session_id:
        return
    if not isinstance(message, str) or not message:
        return
    key = stop_key(session_id, message)
    write_segment(
        segment_path(root, STOP_KIND, key),
        {
            "version": SEGMENT_VERSION,
            "kind": STOP_KIND,
            "idempotency_key": key,
            "project_root": str(root.resolve()),
            "session_id": session_id,
            "captured_at": datetime.now(UTC).isoformat(),
            "last_assistant_message": message,
        },
    )


def capture_session_end(root: Path, payload: dict[str, object]) -> None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return
    raw_reason = payload.get("reason")
    reason = raw_reason if isinstance(raw_reason, str) and raw_reason else "other"
    key = session_end_key(session_id, reason)
    record: dict[str, object] = {
        "version": SEGMENT_VERSION,
        "kind": SESSION_END_KIND,
        "idempotency_key": key,
        "project_root": str(root.resolve()),
        "session_id": session_id,
        "captured_at": datetime.now(UTC).isoformat(),
        "reason": reason,
    }
    message = transcript_message(payload)
    # Stop owns turn text: only carry the final message when Stop did not
    # already capture that exact response for this session.
    if (
        message
        and not segment_path(root, STOP_KIND, stop_key(session_id, message)).exists()
    ):
        record["last_assistant_message"] = message
    write_segment(segment_path(root, SESSION_END_KIND, key), record)


def capture(root: Path, payload: dict[str, object], kind: str) -> int:
    """Capture one segment for ``kind``; always report success."""
    if kind not in SEGMENT_KINDS:
        return 0
    if payload.get("agent_id") or payload.get("agent_type"):
        return 0
    if payload.get("hook_event_name") != HOOK_EVENTS[kind]:
        return 0
    if kind == STOP_KIND:
        capture_stop(root, payload)
    else:
        capture_session_end(root, payload)
    return 0


def read_segments(root: Path) -> list[tuple[Path, dict[str, object]]]:
    """Return valid segments of any known kind belonging to this project."""
    result: list[tuple[Path, dict[str, object]]] = []
    for path in turns_dir(root).glob("*.json"):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        if not isinstance(record, dict):
            continue
        if record.get("kind") not in SEGMENT_KINDS:
            continue
        if record.get("project_root") != str(root.resolve()):
            continue
        result.append((path, record))
    return result


def eligible_segments(root: Path) -> list[tuple[Path, dict[str, object]]]:
    """Return unsummarized segments of both kinds in capture order."""
    pending = [
        (path, record)
        for path, record in read_segments(root)
        if not record.get("summarized_at")
    ]
    return sorted(pending, key=lambda item: str(item[1].get("captured_at", "")))


def cleanup_candidates(root: Path) -> list[Path]:
    """Return only older verified summarized files that are safe to remove."""
    verified: list[tuple[Path, dict[str, object]]] = []
    for path, record in read_segments(root):
        summary = record.get("summary_path")
        if (
            record.get("summarized_at")
            and isinstance(summary, str)
            and (root / summary).is_file()
        ):
            verified.append((path, record))
    verified.sort(key=lambda item: str(item[1].get("summarized_at", "")))
    return [path for path, _ in verified[:-1]]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root")
    parser.add_argument(
        "--kind",
        choices=SEGMENT_KINDS,
        default=STOP_KIND,
        help="Lifecycle channel this handler serves",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError):
        return 0
    if not isinstance(payload, dict):
        return 0
    try:
        return capture(args.root, payload, args.kind)
    except OSError:
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
