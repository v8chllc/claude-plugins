from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

SCRIPT = (
    Path(__file__).parents[1]
    / "plugins"
    / "v8ch"
    / "skills"
    / "remember"
    / "scripts"
    / "validate_memory.py"
)
STEERING_FILE = "CLAUDE.md"
SETUP_COMMAND = "/remember setup"
TOOLCHAIN = "claude"


def write_valid_memory(root: Path) -> None:
    memory_dir = root / ".remember" / "memory"
    memory_dir.mkdir(parents=True)
    (root / ".remember" / "MEMORY.md").write_text(
        """# Memory

## entity

<!-- entity -->
Entity: Remember validation helper
Type: Module
Location: plugins/v8ch/skills/remember/scripts/validate_memory.py
Purpose: Validates Remember memory files
Dependencies: none

## decision

<!-- decision -->
Decision: Keep validation file-based
Date: 2026-07-03
Rationale: Validation should not require network access

## error

<!-- error -->
Symptom: Memory files drift out of shape
Root cause: No validation preflight
Fix: Run validation before writes
Status: watch

## preference

<!-- preference -->
Preference: Keep memory concise
Scope: global

## todo

<!-- todo -->
Todo: Add more validation checks
Source: plan
Status: open
Next action: Add tests
Created: 2026-07-03
""",
        encoding="utf-8",
    )
    (memory_dir / "2026-07-03.md").write_text(
        """<!-- remember-journal
source: manual
kind: session
session_hash: abc123
captured_at: 2026-07-03T00:00:00Z
window_start: 2026-07-03T00:00:00Z
window_end: 2026-07-03T00:10:00Z
-->

## 00:10 Session

### What happened
Added validation coverage.
""",
        encoding="utf-8",
    )


def run_validate(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), "--root", str(root), *args],
        check=False,
        capture_output=True,
        text=True,
    )


def test_valid_memory_json_output_passes(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["status"] == "pass"
    assert payload["counts"] == {"errors": 0, "warnings": 0, "issues": 0}
    assert payload["issues"] == []


def test_missing_required_field_is_reported(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    memory_path = tmp_path / ".remember" / "MEMORY.md"
    memory_path.write_text(
        memory_path.read_text(encoding="utf-8").replace(
            "Scope: global",
            "Scope:",
        ),
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "required_field_missing" in codes
    assert any("Scope" in issue["message"] for issue in payload["issues"])


def test_context_entry_in_memory_file_is_an_error(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    memory_path = tmp_path / ".remember" / "MEMORY.md"
    legacy_context = """
## context

<!-- context -->
Status: Implementing validation
In progress: Adding focused tests
Updated: 2026-07-03
"""
    memory_path.write_text(
        f"{memory_path.read_text(encoding='utf-8')}{legacy_context}",
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "context_entry_in_memory_file" in codes
    assert "legacy_context_section" in codes
    severities = {issue["code"]: issue["severity"] for issue in payload["issues"]}
    assert severities["context_entry_in_memory_file"] == "error"
    assert severities["legacy_context_section"] == "warning"


def test_bad_journal_filename_and_missing_metadata_are_reported(
    tmp_path: Path,
) -> None:
    write_valid_memory(tmp_path)
    (tmp_path / ".remember" / "memory" / "today.md").write_text(
        "## Session without metadata\n",
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "bad_journal_filename" in codes
    assert "journal_metadata_missing" in codes


def test_malformed_journal_metadata_is_reported(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    (tmp_path / ".remember" / "memory" / "2026-07-04.md").write_text(
        """<!-- remember-journal
source: manual
kind: note
-->
""",
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "journal_metadata_field_missing" in codes
    assert "journal_kind_invalid" in codes


def test_valid_v3_segments_from_both_platforms_pass(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    turns = tmp_path / ".remember" / "turns"
    turns.mkdir()
    root = str(tmp_path.resolve())
    records = {
        "claude-stop-stop-key.json": {
            "version": 3,
            "platform": "claude",
            "kind": "stop",
            "key": "stop-key",
            "project_root": root,
            "session_id": "session-1",
            "captured_at": "2026-08-12T00:00:00.000000Z",
            "text": "Done.",
            "reason": None,
            "transcript_path": None,
            "summarized_at": None,
            "summary_path": None,
        },
        "codex-session-end-end-key.json": {
            "version": 3,
            "platform": "codex",
            "kind": "session-end",
            "key": "end-key",
            "project_root": root,
            "session_id": "session-2",
            "captured_at": "2026-08-12T00:01:00.000000Z",
            "text": "",
            "reason": "other",
            "transcript_path": "/tmp/transcript.jsonl",
            "summarized_at": None,
            "summary_path": None,
        },
    }
    for name, record in records.items():
        (turns / name).write_text(json.dumps(record), encoding="utf-8")

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 0


def test_legacy_v1_segment_is_reported_as_invalid(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    turns = tmp_path / ".remember" / "turns"
    turns.mkdir()
    (turns / "stop-legacy.json").write_text(
        json.dumps(
            {
                "version": 1,
                "kind": "stop",
                "idempotency_key": "legacy",
                "project_root": str(tmp_path.resolve()),
                "session_id": "session-1",
                "captured_at": "2026-08-12T00:00:00+00:00",
                "last_assistant_message": "Done.",
            }
        ),
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(
        issue["code"] == "lifecycle_segment_invalid" for issue in payload["issues"]
    )


def test_invalid_lifecycle_segment_is_reported(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    turns = tmp_path / ".remember" / "turns"
    turns.mkdir()
    (turns / "claude-stop-wrong.json").write_text(
        json.dumps(
            {
                "version": 3,
                "platform": "claude",
                "kind": "stop",
                "key": "different-key",
                "project_root": str(tmp_path.resolve()),
                "session_id": "session-1",
                "captured_at": "2026-08-12T00:00:00.000000Z",
                "text": "Done.",
                "reason": None,
                "transcript_path": None,
                "summarized_at": None,
                "summary_path": None,
            }
        ),
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert any(
        issue["code"] == "lifecycle_segment_invalid" for issue in payload["issues"]
    )


def write_local_context(root: Path, body: str) -> Path:
    local_dir = root / ".remember" / "local"
    local_dir.mkdir(parents=True, exist_ok=True)
    context_path = local_dir / "context.md"
    context_path.write_text(body, encoding="utf-8")
    return context_path


VALID_LOCAL_CONTEXT = """<!-- context -->
Status: Implementing validation
In progress: Adding focused tests
Updated: 2026-07-03
"""


def test_valid_local_context_passes(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    write_local_context(tmp_path, VALID_LOCAL_CONTEXT)

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["issues"] == []


def test_missing_local_context_is_not_an_issue(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    (tmp_path / ".remember" / "local").mkdir(parents=True)

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["issues"] == []


def test_duplicate_local_context_entries_are_reported(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    write_local_context(
        tmp_path,
        """<!-- context -->
Status: Implementing validation
In progress: Adding focused tests
Updated: 2026-07-03

<!-- context -->
Status: Second entry
In progress: Something else
Updated: 2026-07-04
""",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "duplicate_context_entries" in codes


def test_local_context_missing_required_field_is_reported(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    write_local_context(
        tmp_path,
        """<!-- context -->
Status: Implementing validation
Updated: 2026-07-03
""",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "required_field_missing" in codes
    assert any("In progress" in issue["message"] for issue in payload["issues"])


def test_unknown_marker_in_local_context_is_reported(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    write_local_context(
        tmp_path,
        """<!-- decision -->
Decision: Wrong lane
Date: 2026-07-03
Rationale: Decisions belong in MEMORY.md
""",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "unknown_memory_marker" in codes


def init_git_repo(root: Path) -> None:
    for args in (
        ["init", "--quiet"],
        ["config", "user.email", "test@example.com"],
        ["config", "user.name", "Test"],
    ):
        subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


def test_unignored_local_context_is_reported_in_a_git_repo(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_memory(tmp_path)
    write_local_context(tmp_path, VALID_LOCAL_CONTEXT)

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "local_context_not_ignored" in codes


def test_ignored_local_context_passes_in_a_git_repo(tmp_path: Path) -> None:
    init_git_repo(tmp_path)
    write_valid_memory(tmp_path)
    write_local_context(tmp_path, VALID_LOCAL_CONTEXT)
    (tmp_path / ".gitignore").write_text(".remember/local/\n", encoding="utf-8")

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    assert payload["issues"] == []


def test_generated_fast_track_section_reports_no_drift(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    (tmp_path / STEERING_FILE).write_text("# Steering\n", encoding="utf-8")

    applied = run_validate(
        tmp_path, "--json", "--toolchain", TOOLCHAIN, "--apply-fast-track"
    )
    assert applied.returncode == 0
    assert json.loads(applied.stdout)["fast_track_added"] is True

    result = run_validate(
        tmp_path, "--json", "--toolchain", TOOLCHAIN, "--check-steering"
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "fast_track_steering_drift" not in codes


def test_fast_track_drift_reports_missing_allowlist_paths(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    (tmp_path / STEERING_FILE).write_text(
        f"""# Steering

## Memory Fast-Track Workflow

Allowed paths:

- `{STEERING_FILE}`
- `CODING_STANDARDS.md`
- `.remember/MEMORY.md`
""",
        encoding="utf-8",
    )

    result = run_validate(
        tmp_path, "--json", "--toolchain", TOOLCHAIN, "--check-steering"
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    drift = [
        issue
        for issue in payload["issues"]
        if issue["code"] == "fast_track_steering_drift"
    ]
    assert drift
    assert any("WORKFLOW_STANDARDS.md" in issue["message"] for issue in drift)
    assert any(".remember/memory/" in issue["message"] for issue in drift)
    assert all(issue["severity"] == "warning" for issue in drift)


def test_fast_track_drift_reports_stale_context_clause(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    (tmp_path / STEERING_FILE).write_text(
        f"""# Steering

## Memory Fast-Track Workflow

Allowed paths:

- `{STEERING_FILE}`
- `CODING_STANDARDS.md`
- `WORKFLOW_STANDARDS.md`
- `.remember/MEMORY.md`
- `.remember/memory/*.md`

4. Resolve conflicts only in allowed memory files; preserve journal chronology
   and update the single active `context` entry instead of duplicating it.
""",
        encoding="utf-8",
    )

    result = run_validate(
        tmp_path, "--json", "--toolchain", TOOLCHAIN, "--check-steering"
    )

    assert result.returncode == 0
    payload = json.loads(result.stdout)
    drift = [
        issue
        for issue in payload["issues"]
        if issue["code"] == "fast_track_steering_drift"
    ]
    assert len(drift) == 1
    assert "context" in drift[0]["message"]


def test_drift_check_does_not_rewrite_the_steering_file(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    steering_path = tmp_path / STEERING_FILE
    original = f"""# Steering

## Memory Fast-Track Workflow

Allowed paths:

- `{STEERING_FILE}`
"""
    steering_path.write_text(original, encoding="utf-8")

    run_validate(tmp_path, "--json", "--toolchain", TOOLCHAIN, "--check-steering")

    assert steering_path.read_text(encoding="utf-8") == original
