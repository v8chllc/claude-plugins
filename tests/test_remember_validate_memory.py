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

## context

<!-- context -->
Status: Implementing validation
In progress: Adding focused tests
Updated: 2026-07-03

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


def test_invalid_memory_reports_required_fields_and_duplicate_context(
    tmp_path: Path,
) -> None:
    write_valid_memory(tmp_path)
    memory_path = tmp_path / ".remember" / "MEMORY.md"
    extra_context = """
<!-- context -->
Status: Duplicate context
Updated: 2026-07-03
"""
    memory_text = f"{memory_path.read_text(encoding='utf-8')}{extra_context}"
    memory_path.write_text(
        memory_text,
        encoding="utf-8",
    )

    result = run_validate(tmp_path, "--json")

    assert result.returncode == 1
    payload = json.loads(result.stdout)
    codes = {issue["code"] for issue in payload["issues"]}
    assert "duplicate_context_entries" in codes
    assert "required_field_missing" in codes
    assert any("In progress" in issue["message"] for issue in payload["issues"])


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


def test_steering_detection_and_application(tmp_path: Path) -> None:
    write_valid_memory(tmp_path)
    steering_path = tmp_path / STEERING_FILE
    steering_path.write_text("# Agent Instructions\n", encoding="utf-8")

    detect_result = run_validate(tmp_path, "--json", "--check-steering")
    detect_payload = json.loads(detect_result.stdout)

    assert detect_result.returncode == 0
    assert detect_payload["status"] == "pass"
    assert any(
        issue["code"] == "fast_track_steering_missing"
        for issue in detect_payload["issues"]
    )

    apply_result = run_validate(tmp_path, "--apply-fast-track", "--json")
    apply_payload = json.loads(apply_result.stdout)

    assert apply_result.returncode == 0
    assert apply_payload["fast_track_added"] is True
    steering_text = steering_path.read_text(encoding="utf-8")
    assert "## Memory Fast-Track Workflow" in steering_text
    assert (
        SETUP_COMMAND in steering_text or "fast-track memory updates" in steering_text
    )
