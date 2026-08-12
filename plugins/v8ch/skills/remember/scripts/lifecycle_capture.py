#!/usr/bin/env python3
"""Project-local capture handler for opt-in Claude Code lifecycle hooks.

``hook_setup.py`` copies this file into ``.claude/hooks/`` once per enabled
channel and registers it with ``--kind stop`` or ``--kind session-end``.  The
handler reads a hook payload on stdin, writes at most one immutable segment
under ``.remember/turns/``, and never writes curated or procedural memory.

Segments use the shared ``version: 3`` format defined by
``lifecycle_segments.py``: one flat store, ``platform`` as a record field, and
filenames of the form ``{platform}-{kind}-{key}.json``.  The schema is repeated
here rather than imported because installed handlers are standalone copies of
this file.

The handler is quiet: it prints nothing and always exits successfully so a
capture failure can never interrupt a Claude Code session.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

SEGMENT_VERSION = 3
PLATFORM = "claude"
STOP_KIND = "stop"
SESSION_END_KIND = "session-end"
SEGMENT_KINDS = (STOP_KIND, SESSION_END_KIND)
HOOK_EVENTS = {STOP_KIND: "Stop", SESSION_END_KIND: "SessionEnd"}
MAX_TRANSCRIPT_BYTES = 1024 * 1024
TIMESTAMP_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def now_stamp() -> str:
    """Return the fixed-width UTC stamp the shared segment format requires."""
    return datetime.now(UTC).strftime(TIMESTAMP_FORMAT)


def digest(*parts: str) -> str:
    return hashlib.sha256("\0".join(parts).encode()).hexdigest()


def stop_key(session_id: str, message: str) -> str:
    return digest(STOP_KIND, session_id, message)


def session_end_key(session_id: str, reason: str) -> str:
    return digest(SESSION_END_KIND, session_id, reason)


def turns_dir(root: Path) -> Path:
    return root / ".remember" / "turns"


def segment_path(root: Path, kind: str, key: str) -> Path:
    return turns_dir(root) / f"{PLATFORM}-{kind}-{key}.json"


def transcript_message(payload: dict[str, object]) -> str | None:
    """Return the final assistant text from the transcript, if readable.

    SessionEnd payloads carry no ``last_assistant_message``, so terminal
    segments fall back to the transcript file named by the payload.
    """
    location = payload.get("transcript_path")
    if not isinstance(location, str) or not location:
        return None
    try:
        with Path(location).open("rb") as handle:
            handle.seek(0, os.SEEK_END)
            size = handle.tell()
            start = max(0, size - MAX_TRANSCRIPT_BYTES)
            handle.seek(start)
            transcript_tail = handle.read().decode("utf-8", errors="ignore")
    except OSError:
        return None
    lines = transcript_tail.splitlines()
    if start and lines:
        lines = lines[1:]
    for line in reversed(lines):
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(entry, dict) or entry.get("type") != "assistant":
            continue
        message = entry.get("message")
        message_content = message.get("content") if isinstance(message, dict) else None
        if isinstance(message_content, str) and message_content.strip():
            return message_content
        if not isinstance(message_content, list):
            continue
        texts = [
            block["text"]
            for block in message_content
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
            handle.write(body)
            handle.flush()
            os.fsync(handle.fileno())
        os.link(temporary, path)
    except (FileExistsError, OSError):
        pass
    finally:
        temporary.unlink(missing_ok=True)


def transcript_location(payload: dict[str, object]) -> str | None:
    """Return the payload's transcript path, carried through but never followed."""
    location = payload.get("transcript_path")
    return location if isinstance(location, str) and location else None


def build_record(
    root: Path,
    kind: str,
    key: str,
    session_id: str,
    text: str,
    reason: str | None,
    transcript_path: str | None,
) -> dict[str, object]:
    """Return one complete v3 segment: all twelve keys, nullables explicit."""
    return {
        "version": SEGMENT_VERSION,
        "platform": PLATFORM,
        "kind": kind,
        "key": key,
        "project_root": str(root.resolve()),
        "session_id": session_id,
        "captured_at": now_stamp(),
        "text": text,
        "reason": reason,
        "transcript_path": transcript_path,
        "summarized_at": None,
        "summary_path": None,
    }


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
        build_record(
            root,
            STOP_KIND,
            key,
            session_id,
            text=message,
            reason=None,
            transcript_path=transcript_location(payload),
        ),
    )


def capture_session_end(root: Path, payload: dict[str, object]) -> None:
    session_id = payload.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        return
    reason = payload.get("reason")
    if not isinstance(reason, str) or not reason:
        return
    key = session_end_key(session_id, reason)
    message = transcript_message(payload)
    # Stop owns turn text: only carry the final message when Stop did not
    # already capture that exact response for this session.  A terminal segment
    # legitimately carries no text at all, which the format records as "".
    if (
        not message
        or segment_path(root, STOP_KIND, stop_key(session_id, message)).exists()
    ):
        message = ""
    write_segment(
        segment_path(root, SESSION_END_KIND, key),
        build_record(
            root,
            SESSION_END_KIND,
            key,
            session_id,
            text=message,
            reason=reason,
            transcript_path=transcript_location(payload),
        ),
    )


def capture(root: Path, payload: dict[str, object], kind: str) -> int:
    """Capture one segment for ``kind``; always report success."""
    if kind not in SEGMENT_KINDS:
        return 0
    if (
        not (root / ".remember" / "MEMORY.md").is_file()
        or not (root / ".remember" / "memory").is_dir()
    ):
        return 0
    if payload.get("agent_id"):
        return 0
    if payload.get("hook_event_name") != HOOK_EVENTS[kind]:
        return 0
    if kind == STOP_KIND:
        capture_stop(root, payload)
    else:
        capture_session_end(root, payload)
    return 0


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
