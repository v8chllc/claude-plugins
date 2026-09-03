#!/usr/bin/env python3
"""Validate Remember memory files and optional fast-track steering."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from lifecycle_segments import valid_segment

MEMORY_TYPES = ("entity", "decision", "context", "error", "preference", "todo")
MEMORY_SECTIONS = ("entity", "decision", "error", "preference", "todo")
LOCAL_CONTEXT_DIR = ".remember/local"
LOCAL_CONTEXT_FILE = ".remember/local/context.md"
REQUIRED_FIELDS = {
    "entity": ("Entity", "Type", "Location", "Purpose", "Dependencies"),
    "decision": ("Decision", "Date", "Rationale"),
    "context": ("Status", "In progress", "Updated"),
    "error": ("Symptom", "Root cause", "Fix", "Status"),
    "preference": ("Preference", "Scope"),
    "todo": ("Todo", "Source", "Status", "Next action", "Created"),
}
JOURNAL_NAME_RE = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
JOURNAL_BLOCK_RE = re.compile(r"<!--\s*remember-journal(?P<body>.*?)-->", re.DOTALL)
MARKER_RE = re.compile(r"<!--\s*(?P<kind>[a-z][a-z-]*)\s*-->")
HEADING_RE = re.compile(r"^##\s+(?P<section>[A-Za-z][A-Za-z -]*)\s*$", re.MULTILINE)
FAST_TRACK_HEADING = "## Memory Fast-Track Workflow"
FAST_TRACK_REQUIRED_TOKENS = (
    "CODING_STANDARDS.md",
    "WORKFLOW_STANDARDS.md",
    ".remember/MEMORY.md",
    ".remember/memory/",
)
STALE_CONTEXT_CLAUSE_RE = re.compile(
    r"single\s+(?:active\s+)?`context`\s+entry", re.IGNORECASE
)


@dataclass(frozen=True)
class Issue:
    severity: str
    code: str
    path: str
    message: str
    suggested_fix: str | None = None

    def as_dict(self) -> dict[str, str]:
        data = {
            "severity": self.severity,
            "code": self.code,
            "path": self.path,
            "message": self.message,
        }
        if self.suggested_fix:
            data["suggested_fix"] = self.suggested_fix
        return data


def add_issue(
    issues: list[Issue],
    severity: str,
    code: str,
    path: Path | str,
    message: str,
    suggested_fix: str | None = None,
) -> None:
    issues.append(
        Issue(
            severity=severity,
            code=code,
            path=str(path),
            message=message,
            suggested_fix=suggested_fix,
        )
    )


def parse_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key.strip()] = value.strip()
    return fields


def memory_entries(text: str) -> list[tuple[str, str]]:
    matches = list(MARKER_RE.finditer(text))
    entries: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        entries.append((match.group("kind"), text[start:end]))
    return entries


def validate_memory_file(root: Path, issues: list[Issue]) -> None:
    memory_path = root / ".remember" / "MEMORY.md"
    journal_dir = root / ".remember" / "memory"
    if not memory_path.exists():
        add_issue(
            issues,
            "error",
            "memory_file_missing",
            memory_path,
            "Memory is not initialized; .remember/MEMORY.md is missing.",
            "Run /remember setup before validating or writing memory.",
        )
        return
    if not journal_dir.exists():
        add_issue(
            issues,
            "error",
            "journal_dir_missing",
            journal_dir,
            "Memory is partially initialized; .remember/memory/ is missing.",
            "Run $remember setup to create the journal lane.",
        )

    text = memory_path.read_text(encoding="utf-8")
    sections = {
        match.group("section").strip().lower() for match in HEADING_RE.finditer(text)
    }
    for memory_type in MEMORY_SECTIONS:
        if memory_type not in sections:
            add_issue(
                issues,
                "error",
                "memory_section_missing",
                memory_path,
                f"Missing required section ## {memory_type}.",
                f"Add a ## {memory_type} section to .remember/MEMORY.md.",
            )
    if "context" in sections:
        add_issue(
            issues,
            "warning",
            "legacy_context_section",
            memory_path,
            "Found a legacy ## context section; context now lives in "
            f"{LOCAL_CONTEXT_FILE}.",
            "Remove the ## context section from .remember/MEMORY.md.",
        )

    for kind, block in memory_entries(text):
        if kind not in MEMORY_TYPES:
            add_issue(
                issues,
                "error",
                "unknown_memory_marker",
                memory_path,
                f"Unknown memory entry marker <!-- {kind} -->.",
                f"Use one of: {', '.join(MEMORY_TYPES)}.",
            )
            continue
        if kind == "context":
            add_issue(
                issues,
                "error",
                "context_entry_in_memory_file",
                memory_path,
                "Curated context must not live in .remember/MEMORY.md; that "
                "file is shared through Git and context goes stale on other "
                "checkouts.",
                f"Move the entry to {LOCAL_CONTEXT_FILE} and remove it here.",
            )
            continue
        fields = parse_fields(block)
        for required in REQUIRED_FIELDS[kind]:
            if not fields.get(required):
                add_issue(
                    issues,
                    "error",
                    "required_field_missing",
                    memory_path,
                    f"{kind} entry is missing required field {required}.",
                    f"Add {required}: <value> to the {kind} entry.",
                )


def local_context_ignored(root: Path) -> bool | None:
    """Report whether `.remember/local/` is ignored, or None outside Git."""
    try:
        result = subprocess.run(
            ["git", "check-ignore", "-q", LOCAL_CONTEXT_DIR],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return None
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def validate_local_context(root: Path, issues: list[Issue]) -> None:
    local_dir = root / ".remember" / "local"
    context_path = local_dir / "context.md"
    if local_dir.is_dir() and local_context_ignored(root) is False:
        add_issue(
            issues,
            "error",
            "local_context_not_ignored",
            local_dir,
            f"{LOCAL_CONTEXT_DIR} is not ignored by Git; local context must "
            "never be shared with another checkout.",
            f"Add {LOCAL_CONTEXT_DIR}/ to .gitignore.",
        )
    if not context_path.is_file():
        return
    text = context_path.read_text(encoding="utf-8")
    context_count = 0
    for kind, block in memory_entries(text):
        if kind != "context":
            add_issue(
                issues,
                "error",
                "unknown_memory_marker",
                context_path,
                f"Unknown memory entry marker <!-- {kind} -->.",
                "The local context file holds <!-- context --> entries only.",
            )
            continue
        context_count += 1
        fields = parse_fields(block)
        for required in REQUIRED_FIELDS["context"]:
            if not fields.get(required):
                add_issue(
                    issues,
                    "error",
                    "required_field_missing",
                    context_path,
                    f"context entry is missing required field {required}.",
                    f"Add {required}: <value> to the context entry.",
                )
    if context_count > 1:
        add_issue(
            issues,
            "error",
            "duplicate_context_entries",
            context_path,
            f"Found {context_count} active context entries; keep at most one.",
            "Merge current state into a single <!-- context --> entry.",
        )


def validate_journals(root: Path, issues: list[Issue]) -> None:
    journal_dir = root / ".remember" / "memory"
    if not journal_dir.exists():
        return
    for path in sorted(p for p in journal_dir.iterdir() if p.is_file()):
        if path.suffix != ".md":
            continue
        if not JOURNAL_NAME_RE.match(path.name):
            add_issue(
                issues,
                "error",
                "bad_journal_filename",
                path,
                "Journal filename must use YYYY-MM-DD.md.",
                "Rename the journal file to a local-date name like 2026-07-03.md.",
            )
        text = path.read_text(encoding="utf-8")
        blocks = list(JOURNAL_BLOCK_RE.finditer(text))
        if text.strip() and not blocks:
            add_issue(
                issues,
                "error",
                "journal_metadata_missing",
                path,
                "Journal file has content but no remember-journal metadata block.",
                "Add a <!-- remember-journal ... --> block before each session entry.",
            )
            continue
        for block in blocks:
            fields = parse_fields(block.group("body"))
            for required in (
                "source",
                "kind",
                "session_hash",
                "captured_at",
                "window_start",
                "window_end",
            ):
                if not fields.get(required):
                    add_issue(
                        issues,
                        "error",
                        "journal_metadata_field_missing",
                        path,
                        f"remember-journal block is missing {required}.",
                        f"Add {required}: <value> to the metadata block.",
                    )
            if fields.get("kind") and fields["kind"] != "session":
                add_issue(
                    issues,
                    "error",
                    "journal_kind_invalid",
                    path,
                    "remember-journal kind must be session.",
                    "Set kind: session in the metadata block.",
                )


def validate_lifecycle_segments(root: Path, issues: list[Issue]) -> None:
    turns = root / ".remember" / "turns"
    if not turns.is_dir():
        return
    for path in sorted(turns.glob("*.json")):
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError):
            record = None
        if not valid_segment(root, path, record):
            add_issue(
                issues,
                "error",
                "lifecycle_segment_invalid",
                path,
                "Lifecycle segment metadata or filename is invalid for this project.",
                "Retain the file for manual review; do not synthesize or clean it.",
            )


def detect_branch(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "<default-branch>"
    value = result.stdout.strip()
    if value.startswith("origin/"):
        return value.removeprefix("origin/")
    return "<default-branch>"


def detect_platform(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=root,
            check=False,
            capture_output=True,
            text=True,
        )
    except OSError:
        return "unknown"
    remote = result.stdout.lower()
    if "github" in remote:
        return "GitHub"
    if "gitlab" in remote:
        return "GitLab"
    return "unknown"


def fast_track_section(toolchain: str, branch: str, platform: str) -> str:
    steering_name = "AGENTS.md" if toolchain == "codex" else "CLAUDE.md"
    pr_term = "pull request" if platform == "GitHub" else "merge request"
    command = "gh pr merge" if platform == "GitHub" else "glab mr merge"
    return f"""
{FAST_TRACK_HEADING}

When explicitly requested by the user, agents may fast-track memory-only updates
so other systems that read `origin/{branch}` can pick them up quickly.

Trigger phrases include:

- "fast-track memory updates"
- "commit and merge memory"
- "push memory to origin"
- "make these memories available to other systems"
- "fast-track memory by direct push" - use only for the direct-push exception

This workflow is allowed only when all pending changes are limited to memory or
memory/procedural-memory guidance files:

- `{steering_name}`
- `CODING_STANDARDS.md`
- `WORKFLOW_STANDARDS.md`
- `.remember/MEMORY.md`
- `.remember/memory/*.md`

If any other tracked, staged, modified, deleted, or untracked path is present,
stop and ask the user whether to handle that work separately. Do not include
non-memory files in a memory fast-track.

`.remember/local/` holds gitignored local-only context. It never appears in
`git status --short`, so it cannot reach this gate. Do not add it to the
allowlist.

Required sequence:

1. Confirm the user explicitly requested a memory fast-track.
2. Inspect `git status --short` and fail closed unless only allowed memory paths
   are present.
3. Fetch and integrate the latest `origin/{branch}` before committing.
4. Resolve conflicts only in allowed memory files; preserve journal chronology
   and dedupe structured entries in `.remember/MEMORY.md`.
5. Review memory content for obvious secrets or sensitive account data.
6. Run `git diff --check`.
7. Commit with a conventional memory message such as
   `chore(memory): fast-track memory updates`.
8. Prefer a short-lived branch plus a {pr_term}; use `{command}` when available.
9. Use direct push to `origin/{branch}` only when the user explicitly requests
   direct-push fast-tracking.
10. Fetch after merge or push and verify `origin/{branch}` contains the memory
    commit before reporting completion.
""".strip()


def fast_track_body(text: str) -> str:
    start = text.find(FAST_TRACK_HEADING)
    if start == -1:
        return ""
    body = text[start + len(FAST_TRACK_HEADING) :]
    match = re.search(r"^##\s", body, re.MULTILINE)
    return body[: match.start()] if match else body


def check_fast_track_drift(
    path: Path,
    text: str,
    steering_file: str,
    issues: list[Issue],
) -> None:
    body = fast_track_body(text)
    missing = [
        token
        for token in (steering_file, *FAST_TRACK_REQUIRED_TOKENS)
        if token not in body
    ]
    if missing:
        add_issue(
            issues,
            "warning",
            "fast_track_steering_drift",
            path,
            "Memory Fast-Track allowlist is missing: " + ", ".join(missing) + ".",
            "Restore the missing paths to the allowlist; the gate fails open "
            "for any path it does not name.",
        )
    if STALE_CONTEXT_CLAUSE_RE.search(body):
        add_issue(
            issues,
            "warning",
            "fast_track_steering_drift",
            path,
            "Memory Fast-Track conflict step still references a single active "
            f"context entry; context now lives in {LOCAL_CONTEXT_FILE}.",
            "Update the conflict-resolution step to dedupe structured entries "
            "in .remember/MEMORY.md.",
        )


def inspect_steering(
    root: Path,
    issues: list[Issue],
    toolchain: str,
    steering_file: str,
    apply_fast_track: bool,
) -> bool:
    path = root / steering_file
    if not path.exists():
        add_issue(
            issues,
            "warning",
            "steering_file_missing",
            path,
            f"{steering_file} does not exist; fast-track steering cannot be checked.",
            f"Create {steering_file} before installing Memory Fast-Track guidance.",
        )
        return False
    text = path.read_text(encoding="utf-8")
    if FAST_TRACK_HEADING in text:
        check_fast_track_drift(path, text, steering_file, issues)
        return False
    lower = text.lower()
    if "memory" in lower and "fast-track" in lower:
        add_issue(
            issues,
            "warning",
            "custom_fast_track_review",
            path,
            "A related memory fast-track section exists but does not match "
            "the expected heading.",
            f"Review manually or add a {FAST_TRACK_HEADING} section explicitly.",
        )
        return False
    if apply_fast_track:
        branch = detect_branch(root)
        platform = detect_platform(root)
        section = fast_track_section(toolchain, branch, platform)
        separator = "\n\n" if text.endswith("\n") else "\n\n"
        path.write_text(f"{text}{separator}{section}\n", encoding="utf-8")
        return True
    add_issue(
        issues,
        "warning",
        "fast_track_steering_missing",
        path,
        f"{steering_file} does not contain a Memory Fast-Track Workflow section.",
        "Run validation with --apply-fast-track after user approval to append one.",
    )
    return False


def result_payload(issues: list[Issue], fast_track_added: bool) -> dict[str, Any]:
    errors = sum(1 for issue in issues if issue.severity == "error")
    warnings = sum(1 for issue in issues if issue.severity == "warning")
    return {
        "status": "fail" if errors else "pass",
        "counts": {
            "errors": errors,
            "warnings": warnings,
            "issues": len(issues),
        },
        "fast_track_added": fast_track_added,
        "issues": [issue.as_dict() for issue in issues],
    }


def render_human(payload: dict[str, Any]) -> str:
    counts = payload["counts"]
    lines = [
        f"Remember validation: {payload['status']}",
        (
            f"Errors: {counts['errors']}; warnings: {counts['warnings']}; "
            f"issues: {counts['issues']}"
        ),
    ]
    if payload["fast_track_added"]:
        lines.append("Memory Fast-Track steering was added.")
    if payload["issues"]:
        lines.append("")
        lines.append("Issues:")
        for issue in payload["issues"]:
            lines.append(
                f"- [{issue['severity']}] {issue['code']} ({issue['path']}): "
                f"{issue['message']}"
            )
            if "suggested_fix" in issue:
                lines.append(f"  Fix: {issue['suggested_fix']}")
    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="Project root")
    parser.add_argument(
        "--json", action="store_true", help="Emit machine-readable JSON"
    )
    parser.add_argument(
        "--check-steering",
        action="store_true",
        help="Check whether steering contains Memory Fast-Track guidance",
    )
    parser.add_argument(
        "--apply-fast-track",
        action="store_true",
        help="Append generated Memory Fast-Track guidance after user approval",
    )
    parser.add_argument(
        "--toolchain",
        choices=("codex", "claude"),
        default="claude",
        help="Toolchain wording for generated steering",
    )
    parser.add_argument(
        "--steering-file",
        default=None,
        help="Steering file to inspect; defaults to CLAUDE.md for Claude",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    root = args.root.resolve()
    issues: list[Issue] = []
    validate_memory_file(root, issues)
    validate_local_context(root, issues)
    validate_journals(root, issues)
    validate_lifecycle_segments(root, issues)
    fast_track_added = False
    if args.check_steering or args.apply_fast_track:
        steering_file = args.steering_file or (
            "AGENTS.md" if args.toolchain == "codex" else "CLAUDE.md"
        )
        fast_track_added = inspect_steering(
            root,
            issues,
            args.toolchain,
            steering_file,
            args.apply_fast_track,
        )
    payload = result_payload(issues, fast_track_added)
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_human(payload))
    return 1 if payload["status"] == "fail" else 0


if __name__ == "__main__":
    sys.exit(main())
