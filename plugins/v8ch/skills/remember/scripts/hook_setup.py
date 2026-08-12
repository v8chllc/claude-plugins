#!/usr/bin/env python3
"""Install, remove, and report Claude Remember lifecycle capture hooks.

Each capture channel is independent: enabling or disabling one never touches
the other channel or any unrelated hook.  Settings edits are atomic and
schema-preserving, and an unreadable settings file is reported rather than
overwritten.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import stat
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

HANDLER_SOURCE = Path(__file__).with_name("lifecycle_capture.py")
HANDLER_MODE = 0o755
PROJECT_DIR = "${CLAUDE_PROJECT_DIR}"
SETTINGS_RELATIVE = Path(".claude") / "settings.json"
HOOKS_RELATIVE = Path(".claude") / "hooks"


class SetupError(Exception):
    """Raised when the requested change cannot be made safely."""


@dataclass(frozen=True)
class Channel:
    name: str
    event: str
    kind: str
    handler: str
    timeout: int = 5

    @property
    def handler_path(self) -> Path:
        return HOOKS_RELATIVE / self.handler

    def registration(self) -> dict[str, Any]:
        return {
            "type": "command",
            "command": f"{PROJECT_DIR}/{self.handler_path.as_posix()}",
            "args": ["--root", PROJECT_DIR, "--kind", self.kind],
            "timeout": self.timeout,
        }


CHANNELS = {
    channel.name: channel
    for channel in (
        Channel(
            name="stop-capture",
            event="Stop",
            kind="stop",
            handler="remember-stop-capture.py",
        ),
        Channel(
            name="session-end-capture",
            event="SessionEnd",
            kind="session-end",
            handler="remember-session-end-capture.py",
        ),
    )
}


def require_memory(root: Path) -> None:
    if not (root / ".remember" / "MEMORY.md").is_file():
        raise SetupError(
            "Memory is not initialized; .remember/MEMORY.md is missing. "
            "Run /remember setup first."
        )
    if not (root / ".remember" / "memory").is_dir():
        raise SetupError(
            "Memory is partially initialized; .remember/memory/ is missing. "
            "Run /remember setup first."
        )


def load_settings(path: Path) -> dict[str, Any]:
    """Return parsed settings, or raise rather than discard an unreadable file."""
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as error:
        raise SetupError(f"Cannot read {path}: {error}") from error
    if not text.strip():
        return {}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as error:
        raise SetupError(
            f"{path} is not valid JSON ({error}). Repair it by hand; "
            "Remember will not overwrite it."
        ) from error
    if not isinstance(data, dict):
        raise SetupError(
            f"{path} must contain a JSON object. Repair it by hand; "
            "Remember will not overwrite it."
        )
    return data


def write_settings(path: Path, data: dict[str, Any]) -> None:
    """Replace settings atomically so an interruption keeps the prior state."""
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=".settings-",
        suffix=".json",
        delete=False,
    )
    temp = Path(handle.name)
    try:
        with handle:
            handle.write(json.dumps(data, indent=2) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp, path)
    except OSError as error:
        temp.unlink(missing_ok=True)
        raise SetupError(f"Cannot write {path}: {error}") from error


def owns_entry(entry: Any, channel: Channel) -> bool:
    """Match Remember-owned entries, including legacy shell-form registrations."""
    if not isinstance(entry, dict):
        return False
    command = entry.get("command")
    return isinstance(command, str) and channel.handler in command


def strip_channel(settings: dict[str, Any], channel: Channel) -> bool:
    """Remove every registration for ``channel``; leave everything else alone."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return False
    groups = hooks.get(channel.event)
    if not isinstance(groups, list):
        return False
    removed = False
    kept_groups: list[Any] = []
    for group in groups:
        if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
            kept_groups.append(group)
            continue
        entries = [item for item in group["hooks"] if not owns_entry(item, channel)]
        if len(entries) == len(group["hooks"]):
            kept_groups.append(group)
            continue
        removed = True
        if entries:
            group["hooks"] = entries
            kept_groups.append(group)
    if not removed:
        return False
    if kept_groups:
        hooks[channel.event] = kept_groups
    else:
        del hooks[channel.event]
    if not hooks:
        del settings["hooks"]
    return True


def install_handler(root: Path, channel: Channel) -> Path:
    destination = root / channel.handler_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        shutil.copyfile(HANDLER_SOURCE, destination)
        destination.chmod(HANDLER_MODE)
    except OSError as error:
        raise SetupError(f"Cannot install {destination}: {error}") from error
    return destination


def is_executable(path: Path) -> bool:
    return path.is_file() and bool(path.stat().st_mode & stat.S_IXUSR)


def enable(root: Path, channel: Channel) -> dict[str, Any]:
    require_memory(root)
    settings_path = root / SETTINGS_RELATIVE
    settings = load_settings(settings_path)
    # Drop any prior or duplicate registration first so re-enabling refreshes
    # the entry in place instead of stacking a second one.
    refreshed = strip_channel(settings, channel)
    hooks = settings.setdefault("hooks", {})
    groups = hooks.setdefault(channel.event, [])
    if not isinstance(groups, list):
        raise SetupError(
            f"{settings_path} has a non-list hooks.{channel.event} value. "
            "Repair it by hand; Remember will not overwrite it."
        )
    groups.append({"hooks": [channel.registration()]})
    write_settings(settings_path, settings)
    handler = install_handler(root, channel)
    return {
        "channel": channel.name,
        "action": "refreshed" if refreshed else "enabled",
        "event": channel.event,
        "handler": str(handler.relative_to(root)),
        "settings": str(settings_path.relative_to(root)),
    }


def disable(root: Path, channel: Channel) -> dict[str, Any]:
    settings_path = root / SETTINGS_RELATIVE
    settings = load_settings(settings_path)
    removed = strip_channel(settings, channel)
    if removed:
        write_settings(settings_path, settings)
    handler = root / channel.handler_path
    handler_removed = handler.is_file()
    handler.unlink(missing_ok=True)
    return {
        "channel": channel.name,
        "action": "disabled" if removed or handler_removed else "already-disabled",
        "event": channel.event,
        "registration_removed": removed,
        "handler_removed": handler_removed,
    }


def channel_status(root: Path, channel: Channel) -> dict[str, Any]:
    settings_path = root / SETTINGS_RELATIVE
    try:
        settings = load_settings(settings_path)
        settings_error = None
    except SetupError as error:
        settings = {}
        settings_error = str(error)
    hooks = settings.get("hooks")
    groups = hooks.get(channel.event) if isinstance(hooks, dict) else None
    registered = 0
    if isinstance(groups, list):
        for group in groups:
            entries = group.get("hooks") if isinstance(group, dict) else None
            if isinstance(entries, list):
                registered += sum(1 for item in entries if owns_entry(item, channel))
    handler = root / channel.handler_path
    state: dict[str, Any] = {
        "channel": channel.name,
        "event": channel.event,
        "state": "enabled" if registered and is_executable(handler) else "disabled",
        "registrations": registered,
        "handler_installed": handler.is_file(),
        "handler_executable": is_executable(handler),
    }
    if settings_error:
        state["settings_error"] = settings_error
    return state


def status(root: Path) -> dict[str, Any]:
    return {
        "root": str(root),
        "memory_initialized": (root / ".remember" / "MEMORY.md").is_file(),
        "channels": [channel_status(root, channel) for channel in CHANNELS.values()],
    }


def render_status(payload: dict[str, Any]) -> str:
    lines = [f"Remember lifecycle hooks in {payload['root']}"]
    if not payload["memory_initialized"]:
        lines.append("Memory is not initialized; run /remember setup first.")
    for channel in payload["channels"]:
        lines.append(
            f"- {channel['channel']} ({channel['event']}): {channel['state']}; "
            f"registrations: {channel['registrations']}; "
            f"handler executable: {channel['handler_executable']}"
        )
        if "settings_error" in channel:
            lines.append(f"  Settings: {channel['settings_error']}")
    return "\n".join(lines)


def render_change(payload: dict[str, Any]) -> str:
    return f"{payload['channel']} ({payload['event']}): {payload['action']}"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "command", choices=("enable", "disable", "status"), help="Action to perform"
    )
    parser.add_argument(
        "channel",
        nargs="?",
        choices=tuple(CHANNELS),
        help="Capture channel; required for enable and disable",
    )
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root")
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    try:
        if args.command == "status":
            payload = status(root)
            renderer = render_status
        else:
            if not args.channel:
                raise SetupError(f"{args.command} requires a channel name.")
            channel = CHANNELS[args.channel]
            payload = (
                enable(root, channel)
                if args.command == "enable"
                else disable(root, channel)
            )
            renderer = render_change
    except SetupError as error:
        if args.json:
            print(json.dumps({"status": "error", "message": str(error)}, indent=2))
        else:
            print(str(error), file=sys.stderr)
        return 1
    print(
        json.dumps(payload, indent=2, sort_keys=True)
        if args.json
        else renderer(payload)
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
