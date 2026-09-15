#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Render and post the consensus-review comment for the Claude Code plugin.

Reads the platform from ``DEV_SEC_OPS_PLATFORM`` or ``--platform``, validates
every schema-v2 field against ``review_contract``, renders
``templates/review-comment.md.tmpl``, and posts the result with ``gh`` or
``glab``. Status and summary authorship stay with the calling role; this script
owns validation, deterministic rendering, and transport.

Byte-identical to the Codex copy in ``v8chllc/codex-plugins`` apart from this
docstring.
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path
from string import Template

from review_contract import (
    ContractError,
    build_metadata,
    extract_quality_score,
    render_metadata_block,
    status_label,
)

# Resolve absolute paths for external tools at module load (prevents PATH hijacking)
GH = shutil.which("gh")
GLAB = shutil.which("glab")

STATUS_EMOJI = {
    "clean": "✅",
    "passing": "🟡",
    "failing": "❌",
}

TEMPLATE_NAME = "review-comment.md.tmpl"
EVIDENCE_HEADING = "### Evidence"
MIN_SUMMARY_BULLETS = 1
MAX_SUMMARY_BULLETS = 3


def read_platform_from_env(repo_dir: str | Path = ".") -> str:
    """Read DEV_SEC_OPS_PLATFORM from the repo-local .env file."""
    env_path = Path(repo_dir) / ".env"
    if not env_path.exists():
        return "github"

    with open(env_path, encoding="utf-8") as handle:
        for raw_line in handle:
            line = raw_line.strip()
            if line.startswith("DEV_SEC_OPS_PLATFORM="):
                value = line[len("DEV_SEC_OPS_PLATFORM=") :]
                return value.strip().strip('"').strip("'").lower()

    return "github"


def resolve_platform(override: str | None, repo_dir: str | Path = ".") -> str:
    """Return the platform from the explicit override or the repo-local .env."""
    if override:
        return override.strip().lower()
    return read_platform_from_env(repo_dir)


def read_required_text(path: str | Path, *, label: str) -> str:
    """Read a required text file and fail if it is missing or empty."""
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
    except OSError as error:
        raise ContractError(f"Failed to read {label} '{path}': {error}") from error
    if not content:
        raise ContractError(f"The {label} file '{path}' is empty.")
    return content


def validate_summary(summary_text: str) -> str:
    """Validate the one-to-three bullet summary authored by the poster role."""
    lines = [line.strip() for line in summary_text.splitlines() if line.strip()]
    if not all(line.startswith("- ") for line in lines):
        raise ContractError("Every summary line must be a markdown bullet ('- ').")
    if not MIN_SUMMARY_BULLETS <= len(lines) <= MAX_SUMMARY_BULLETS:
        raise ContractError(
            f"The summary must hold {MIN_SUMMARY_BULLETS} to {MAX_SUMMARY_BULLETS} "
            f"bullets, got {len(lines)}."
        )
    return "\n".join(lines)


def validate_report(report_text: str) -> None:
    """Reject a report that cannot be posted or recovered intact."""
    if EVIDENCE_HEADING not in report_text:
        raise ContractError(
            "The report is missing its merged '### Evidence' section; the "
            "synthesizer did not complete."
        )
    if "<details>" in report_text.lower():
        raise ContractError(
            "The report contains a <details> block. The comment wraps the report "
            "in one <details> element, and a nested block truncates recovery."
        )


def resolve_score(report_text: str) -> int:
    """Return the raw score from the report's Quality Score heading.

    The heading is the only source. An override flag would let a caller publish
    metadata that contradicts the visible report, and the synthesizer alone
    decides the score.
    """
    extracted = extract_quality_score(report_text)
    if extracted is None:
        raise ContractError(
            "No raw score found. The report needs a '### Quality Score: N/100' heading."
        )
    return extracted


def template_path() -> Path:
    """Return the review template shipped beside the skill scripts."""
    return Path(__file__).resolve().parent.parent / "templates" / TEMPLATE_NAME


def load_template() -> Template:
    """Load the review comment template."""
    path = template_path()
    try:
        return Template(path.read_text(encoding="utf-8"))
    except OSError as error:
        raise ContractError(f"Failed to read template '{path}': {error}") from error


def build_provenance_line(
    *, delegation_mode: str, plan_source: str, scope_basis: str, reviewed_sha: str
) -> str:
    """Render the single provenance line shown above the summary."""
    return (
        f"Delegation: {delegation_mode}. Plan: {plan_source}. "
        f"Scope: {scope_basis}. Reviewed: {reviewed_sha}."
    )


def build_comment_body(
    *,
    report_text: str,
    summary_text: str,
    cycle: int,
    status: str,
    score: int,
    delegation_mode: str,
    plan_source: str,
    reviewed_sha: str,
    scope_basis: str,
    files_touched: int,
    findings_opened: int,
    findings_closed: int,
) -> str:
    """Build the full review comment, metadata block first."""
    validate_report(report_text)
    metadata = build_metadata(
        cycle=cycle,
        status=status,
        score=score,
        delegation_mode=delegation_mode,
        plan_source=plan_source,
        reviewed_sha=reviewed_sha,
        scope_basis=scope_basis,
        files_touched=files_touched,
        findings_opened=findings_opened,
        findings_closed=findings_closed,
    )
    body = load_template().substitute(
        {
            "icon": STATUS_EMOJI[status],
            "cycle_suffix": f"{cycle:02d}",
            "score": str(score),
            "status_label": status_label(status),
            "provenance_line": build_provenance_line(
                delegation_mode=delegation_mode,
                plan_source=plan_source,
                scope_basis=scope_basis,
                reviewed_sha=reviewed_sha,
            ),
            "summary_text": validate_summary(summary_text),
            "details_text": report_text,
        }
    )
    return f"{render_metadata_block(metadata)}\n\n{body}"


def post_comment_github(pr_number: int, body: str, repo_dir: str | Path = ".") -> None:
    """Post a comment to a GitHub PR."""
    if not GH:
        raise FileNotFoundError("gh executable not found in PATH")
    subprocess.run(
        [GH, "pr", "comment", str(pr_number), "--body", body],
        cwd=repo_dir,
        check=True,
    )


def post_comment_gitlab(pr_number: int, body: str, repo_dir: str | Path = ".") -> None:
    """Post a note to a GitLab MR."""
    if not GLAB:
        raise FileNotFoundError("glab executable not found in PATH")
    subprocess.run(
        [GLAB, "mr", "note", str(pr_number), "--message", body],
        cwd=repo_dir,
        check=True,
    )


def post_comment(
    pr_number: int, body: str, *, platform: str, repo_dir: str | Path = "."
) -> None:
    """Post the rendered comment to the selected platform."""
    if platform == "gitlab":
        post_comment_gitlab(pr_number, body, repo_dir=repo_dir)
    else:
        post_comment_github(pr_number, body, repo_dir=repo_dir)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Post the consensus-review comment to a GitHub PR or GitLab MR.",
    )
    parser.add_argument(
        "--pr-number", type=int, required=True, help="PR/MR number to comment on"
    )
    parser.add_argument(
        "--comment-type",
        choices=["review"],
        default="review",
        help="Comment type; the review comment is the only type v2 posts",
    )
    parser.add_argument(
        "--review-file",
        required=True,
        help="Path to the synthesized review report",
    )
    parser.add_argument(
        "--summary-file",
        required=True,
        help="Path to the file holding the 1-3 bullet summary",
    )
    parser.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository directory where gh/glab commands run",
    )
    parser.add_argument(
        "--platform",
        choices=["github", "gitlab"],
        default=None,
        help="Override DEV_SEC_OPS_PLATFORM detection",
    )
    parser.add_argument(
        "--cycle", type=int, required=True, help="Review cycle number (>= 1)"
    )
    parser.add_argument(
        "--status",
        choices=["clean", "passing", "failing"],
        required=True,
        help="Review status decided by the synthesizer",
    )
    parser.add_argument(
        "--delegation-mode",
        choices=["parallel-subagents", "sequential-fallback"],
        required=True,
        help="How the three reviewers ran",
    )
    parser.add_argument(
        "--plan-source",
        required=True,
        help="'none', or 'supplied: <path or short description>'",
    )
    parser.add_argument(
        "--reviewed-sha", required=True, help="Reviewed HEAD SHA (7-40 lowercase hex)"
    )
    parser.add_argument(
        "--scope-basis",
        required=True,
        help="'full-diff' or 'delta-since:<sha>'",
    )
    parser.add_argument(
        "--files-touched", type=int, required=True, help="Files in the reviewed scope"
    )
    parser.add_argument(
        "--findings-opened", type=int, required=True, help="Findings opened this cycle"
    )
    parser.add_argument(
        "--findings-closed",
        type=int,
        required=True,
        help="Prior-cycle findings confirmed closed",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Render and post one review comment. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    platform = resolve_platform(args.platform, args.repo_dir)

    try:
        report_text = read_required_text(args.review_file, label="review")
        summary_text = read_required_text(args.summary_file, label="summary")
        body = build_comment_body(
            report_text=report_text,
            summary_text=summary_text,
            cycle=args.cycle,
            status=args.status,
            score=resolve_score(report_text),
            delegation_mode=args.delegation_mode,
            plan_source=args.plan_source,
            reviewed_sha=args.reviewed_sha,
            scope_basis=args.scope_basis,
            files_touched=args.files_touched,
            findings_opened=args.findings_opened,
            findings_closed=args.findings_closed,
        )
    except ContractError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1

    try:
        post_comment(args.pr_number, body, platform=platform, repo_dir=args.repo_dir)
    except FileNotFoundError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    except subprocess.CalledProcessError as error:
        print(
            f"Error: failed to post comment (exit code {error.returncode}): {error}",
            file=sys.stderr,
        )
        return 1

    print(
        f"Posted cycle {args.cycle:02d} review comment to {platform} #{args.pr_number}."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
