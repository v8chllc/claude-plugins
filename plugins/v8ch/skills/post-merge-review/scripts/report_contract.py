#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Format and validate the shared post-merge report without changing synthesis."""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

KEYS = {
    "schema_version",
    "type",
    "platform",
    "reference",
    "merge_commit",
    "target_branch",
    "scope_basis",
    "score",
    "status",
    "files_touched",
    "findings",
}
LABELS = {"clean": "Fully Clean", "passing": "Passing", "failing": "Failing"}
SECTIONS = [
    "Run Provenance",
    "Evidence",
    "Summary",
    "Must Fix",
    "Should Fix",
    "Plan Notes",
    "Noted",
    "Behavior Deltas",
    "Score Breakdown",
]
FINDING = re.compile(r"#### \[F-([1-9][0-9]*)\] \[(CRITICAL|HIGH|MEDIUM|LOW)\] .+")


def heading(metadata: dict[str, Any]) -> str:
    label = "PR #" if metadata["platform"] == "github" else "MR !"
    return (
        f"**Post-merge review** of {label}{metadata['reference']} at merge commit "
        f"`{metadata['merge_commit']}`."
    )


def metadata_valid(metadata: object) -> dict[str, Any]:
    if not isinstance(metadata, dict) or set(metadata) != KEYS:
        raise ValueError("metadata must have exactly the contract keys")
    if any(value is None for value in metadata.values()):
        raise ValueError("metadata values cannot be null")
    for key in ("schema_version", "reference", "score", "files_touched", "findings"):
        if type(metadata[key]) is not int:
            raise ValueError(f"{key} must be an integer")
    if metadata["schema_version"] != 1 or metadata["type"] != "post-merge-report":
        raise ValueError("unsupported report schema or type")
    if metadata["platform"] not in ("github", "gitlab"):
        raise ValueError("unsupported platform")
    if (
        metadata["reference"] < 1
        or metadata["files_touched"] < 0
        or metadata["findings"] < 0
    ):
        raise ValueError("invalid count")
    sha = metadata["merge_commit"]
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise ValueError("merge_commit must be a full lowercase SHA")
    if (
        not isinstance(metadata["target_branch"], str)
        or not metadata["target_branch"].strip()
    ):
        raise ValueError("target_branch must be non-empty")
    if metadata["scope_basis"] != "net-diff":
        raise ValueError("unsupported scope_basis")
    score, status = metadata["score"], metadata["status"]
    if not 1 <= score <= 100 or not isinstance(status, str) or status not in LABELS:
        raise ValueError("invalid score or status")
    if (score < 85) != (status == "failing") or (status == "clean" and score < 95):
        raise ValueError("score and status disagree")
    return metadata


def report_headings(report: str) -> list[str]:
    """Read headings outside fenced examples, which are report data."""
    result = []
    fence: str | None = None
    for line in report.splitlines():
        match = re.match(r"^(`{3,}|~{3,})", line)
        if match:
            token = match.group(1)
            if fence is None:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = None
            continue
        if fence is None and line.startswith("#"):
            result.append(line)
    if fence is not None:
        raise ValueError("unclosed report fence")
    return result


def validate_report(text: str) -> dict[str, Any]:
    if "\r" in text or text.startswith("\ufeff"):
        raise ValueError("report must use UTF-8 without BOM and LF line endings")
    lines = text.splitlines()
    if len(lines) < 7 or lines[0] != "<!-- post-merge-review" or lines[2] != "-->":
        raise ValueError("missing metadata block")
    metadata = metadata_valid(json.loads(lines[1]))
    canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    if lines[1] != canonical:
        raise ValueError("metadata must use canonical sorted-key compact JSON")
    if lines[3] != heading(metadata) or lines[4] != "":
        raise ValueError("identity heading disagrees with metadata")
    expected = (
        f"### Quality Score: {metadata['score']}/100 — {LABELS[metadata['status']]}"
    )
    if lines[5] != expected:
        raise ValueError("score heading disagrees with metadata")
    headings = report_headings("\n".join(lines[5:]))
    sections = [line for line in headings if line.startswith("### ")]
    if sections != [expected, *[f"### {name}" for name in SECTIONS]]:
        raise ValueError("invalid synthesizer section order or forbidden section")
    section = ""
    count = 0
    for line in headings:
        if line.startswith("### "):
            section = line[4:]
        elif line.startswith("#### [F-"):
            finding = FINDING.fullmatch(line)
            if not finding or section not in ("Must Fix", "Should Fix"):
                raise ValueError("invalid finding heading or section")
            count += 1
            if int(finding.group(1)) != count:
                raise ValueError("finding IDs must be consecutive in report order")
    if count != metadata["findings"]:
        raise ValueError("finding count disagrees with metadata")
    return metadata


def format_report(metadata: dict[str, Any], synthesis: str) -> str:
    """Prefix the unchanged synthesizer output, then validate the whole result."""
    metadata_valid(metadata)
    encoded = json.dumps(metadata, sort_keys=True, separators=(",", ":"))
    result = (
        f"<!-- post-merge-review\n{encoded}\n-->\n{heading(metadata)}\n\n{synthesis}"
    )
    validate_report(result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("report", type=Path)
    render = commands.add_parser("format")
    render.add_argument("--metadata", type=Path, required=True)
    render.add_argument("--synthesis", type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.command == "validate":
            metadata = validate_report(args.report.read_bytes().decode("utf-8"))
            print(json.dumps(metadata, sort_keys=True, separators=(",", ":")))
        else:
            metadata = json.loads(args.metadata.read_bytes().decode("utf-8"))
            synthesis = args.synthesis.read_bytes().decode("utf-8")
            sys.stdout.write(format_report(metadata, synthesis))
    except (OSError, UnicodeError, ValueError, TypeError) as error:
        print(f"invalid report: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
