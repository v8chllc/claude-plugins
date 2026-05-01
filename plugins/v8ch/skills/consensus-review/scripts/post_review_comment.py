#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.9.0",
# ]
# ///

"""
Render and post consensus-review PR/MR comments.

This script:
1. Reads DEV_SEC_OPS_PLATFORM from .env at the workspace root
2. Loads a standalone markdown template for the requested comment type
3. Renders the final body from structured inputs supplied by the calling agent
4. Posts the comment to GitHub (gh) or GitLab (glab)

Status determination and summary authorship still live in the calling agent.
This script owns deterministic rendering and transport only.
"""

import json
import re
import shutil
import subprocess
from enum import StrEnum
from pathlib import Path
from string import Template
from typing import Annotated

import typer

# Resolve absolute paths for external tools at module load (prevents PATH hijacking)
GH = shutil.which("gh")
GLAB = shutil.which("glab")

# Status emoji mapping for three-state review status
STATUS_EMOJI = {
    "clean": "\u2705",  # ✅
    "passing": "\U0001f7e1",  # 🟡
    "failing": "\u274c",  # ❌
}

TEMPLATE_FILENAMES = {
    "review": "review-comment.md.tmpl",
    "fix_validation": "fix-validation-comment.md.tmpl",
    "acceptance": "acceptance-comment.md.tmpl",
    "additional_acceptance": "additional-acceptance-comment.md.tmpl",
    "low_confidence_opt_in": "low-confidence-opt-in-comment.md.tmpl",
    "recommendations": "recommendations-comment.md.tmpl",
}


class _CommentType(StrEnum):
    review = "review"
    fix_validation = "fix_validation"
    acceptance = "acceptance"
    additional_acceptance = "additional_acceptance"
    low_confidence_opt_in = "low_confidence_opt_in"
    recommendations = "recommendations"


class _ReviewStatus(StrEnum):
    clean = "clean"
    passing = "passing"
    failing = "failing"


app = typer.Typer()


def read_platform_from_env(repo_dir: str | Path = ".") -> str:
    """Read DEV_SEC_OPS_PLATFORM from the repo-local .env file."""
    env_path = Path(repo_dir) / ".env"
    if not env_path.exists():
        return "github"

    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line.startswith("DEV_SEC_OPS_PLATFORM="):
                raw = line[len("DEV_SEC_OPS_PLATFORM=") :]
                value = raw.strip().strip('"').strip("'")
                return value.lower()

    return "github"


def build_summary_lines(summary_file: str) -> list[str]:
    """Read pre-generated bullet summary lines from a file."""
    content = Path(summary_file).read_text(encoding="utf-8").strip()
    return [line for line in content.splitlines() if line.strip()]


def read_required_text(path: str, *, label: str) -> str:
    """Read a required text file and fail if it is empty."""
    try:
        content = Path(path).read_text(encoding="utf-8").strip()
    except OSError as e:
        raise ValueError(f"Failed to read {label} '{path}': {e}") from e
    if not content:
        raise ValueError(f"{label.capitalize()} file is empty.")
    return content


def infer_comment_type(comment_type: str | None, review_file: str | None) -> str:
    """Resolve the comment type from explicit input or legacy review-file inference."""
    if comment_type:
        return comment_type
    if not review_file:
        raise ValueError("Comment type is required when no review file is provided.")
    review_name = Path(review_file).name
    return "fix_validation" if review_name.startswith("fix-") else "review"


def template_dir() -> Path:
    """Return the template directory located beside the skill scripts."""
    return Path(__file__).resolve().parent.parent / "templates"


def load_template(comment_type: str) -> Template:
    """Load the markdown template for a comment type."""
    template_name = TEMPLATE_FILENAMES[comment_type]
    template_path = template_dir() / template_name
    try:
        content = template_path.read_text(encoding="utf-8")
    except OSError as e:
        raise ValueError(f"Failed to read template '{template_path}': {e}") from e
    return Template(content)


def cycle_suffix(cycle: int | None) -> str:
    """Return a formatted cycle suffix for comment titles."""
    return f"{cycle:02d}" if cycle is not None else ""


def render_comment(comment_type: str, context: dict[str, str]) -> str:
    """Render a markdown comment from the selected template."""
    return load_template(comment_type).substitute(context)


def build_metadata_block(metadata: dict[str, object]) -> str:
    """Render the hidden metadata block used for PR/MR audit recovery."""
    payload = {
        key: value
        for key, value in metadata.items()
        if value is not None and value != ""
    }
    payload.setdefault("schema_version", 1)
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"<!-- consensus-review\n{encoded}\n-->"


def with_metadata(body: str, metadata: dict[str, object]) -> str:
    """Prefix a rendered comment body with consensus-review metadata."""
    return f"{build_metadata_block(metadata)}\n\n{body}"


def get_status(status_arg: str | None, is_clean: bool) -> str:
    """Resolve the final status from --status or legacy --is-clean flag.

    Args:
        status_arg: Value from --status option (clean, passing, or failing)
        is_clean: Legacy --is-clean flag value

    Returns:
        Resolved status string: 'clean', 'passing', or 'failing'
    """
    if status_arg:
        return status_arg
    return "clean" if is_clean else "failing"


def extract_quality_score(review_text: str) -> int | None:
    """Extract the raw quality score from a synthesizer review report."""
    match = re.search(r"^### Quality Score:\s+(\d+)/100\s*$", review_text, re.MULTILINE)
    if not match:
        return None
    return int(match.group(1))


def build_review_comment_body(
    details_text: str,
    *,
    comment_type: str,
    status: str,
    summary_file: str,
    cycle: int | None,
    before_score: int | None = None,
    after_score: int | None = None,
) -> str:
    """Build a rendered review or fix-validation comment."""
    icon = STATUS_EMOJI.get(status, STATUS_EMOJI["failing"])
    summary_lines = build_summary_lines(summary_file)
    summary_text = "\n".join(summary_lines)
    resolved_before_score: int | None = None
    if comment_type == "review":
        resolved_before_score = before_score
        if resolved_before_score is None:
            resolved_before_score = extract_quality_score(details_text)
        if resolved_before_score is None:
            raise ValueError(
                "Review comments require a raw score in the review file header "
                "or via --before-score."
            )
        before_score_text = str(resolved_before_score)
    else:
        before_score_text = ""

    body = render_comment(
        comment_type,
        {
            "icon": icon,
            "cycle_suffix": cycle_suffix(cycle),
            "summary_text": summary_text,
            "details_text": details_text,
            "before_score": before_score_text,
            "after_score": str(after_score) if after_score is not None else "N/A",
        },
    )
    metadata: dict[str, object] = {
        "schema_version": 1,
        "type": comment_type,
        "cycle": cycle,
        "status": status,
    }
    if comment_type == "review":
        metadata["score"] = resolved_before_score
    return with_metadata(body, metadata)


def build_findings_comment_body(
    *,
    comment_type: str,
    cycle: int | None,
    findings_file: str,
    before_score: int | None,
    after_score: int | None,
) -> str:
    """Build a rendered findings-list comment."""
    findings_text = read_required_text(findings_file, label="findings")
    if comment_type == "acceptance":
        if before_score is None or after_score is None:
            raise ValueError(
                "Acceptance comments require --before-score and --after-score."
            )
        before_score_label = "Raw score"
        after_score_label = "Adjusted score"
        score_block = (
            f"### Score Impact\n"
            f"- {before_score_label}: {before_score}/100\n"
            f"- {after_score_label}: {after_score}/100"
        )
        closing_note = (
            "These findings will be excluded from scoring in future review cycles."
        )
    elif comment_type == "additional_acceptance":
        if before_score is None or after_score is None:
            raise ValueError(
                "Additional acceptance comments require --before-score and "
                "--after-score."
            )
        before_score_label = "Score before additional acceptance"
        after_score_label = "Score after additional acceptance"
        score_block = (
            f"### Score Impact\n"
            f"- {before_score_label}: {before_score}/100\n"
            f"- {after_score_label}: {after_score}/100"
        )
        closing_note = (
            "These newly accepted findings will be excluded from scoring in future "
            "review cycles."
        )
    else:
        score_block = ""
        closing_note = (
            "These low-confidence findings were explicitly opted in for fixing this "
            "cycle. They remain informational until a later review validates the "
            "result."
        )
    body = render_comment(
        comment_type,
        {
            "cycle_suffix": cycle_suffix(cycle),
            "findings_text": findings_text,
            "score_block": score_block,
            "closing_note": closing_note,
            "before_score": str(before_score) if before_score is not None else "N/A",
            "after_score": str(after_score) if after_score is not None else "N/A",
        },
    )
    return with_metadata(
        body,
        {
            "schema_version": 1,
            "type": comment_type,
            "cycle": cycle,
            "before_score": before_score,
            "after_score": after_score,
        },
    )


def build_recommendations_comment_body(
    *,
    cycle: int | None,
    acceptance_findings_file: str,
    opt_in_findings_file: str,
) -> str:
    """Build a rendered recommendations comment.

    Renders both ``Recommended for Acceptance`` and ``Recommended for Opt-In``
    sections from two separate findings files. Each findings file should contain
    a numbered markdown list whose lines follow the format documented in
    ``recommendations-comment.md.tmpl`` (machine-parsed by recover_context.py's
    ``_INLINE_RECOMMENDATION_RE``).
    """
    acceptance_findings_text = read_required_text(
        acceptance_findings_file, label="acceptance recommendations"
    )
    opt_in_findings_text = read_required_text(
        opt_in_findings_file, label="opt-in recommendations"
    )
    closing_note = (
        "Advisory only — apply recommendations in a follow-up acceptance or "
        "opt-in step before they affect scoring."
    )
    body = render_comment(
        "recommendations",
        {
            "cycle_suffix": cycle_suffix(cycle),
            "acceptance_findings_text": acceptance_findings_text,
            "opt_in_findings_text": opt_in_findings_text,
            "closing_note": closing_note,
        },
    )
    return with_metadata(
        body,
        {
            "schema_version": 1,
            "type": "recommendations",
            "cycle": cycle,
        },
    )


def post_comment_github(pr_number: int, body: str, repo_dir: str = ".") -> None:
    """Post a comment to a GitHub PR."""
    if not GH:
        raise FileNotFoundError("gh executable not found in PATH")
    subprocess.run(
        [GH, "pr", "comment", str(pr_number), "--body", body],
        cwd=repo_dir,
        check=True,
    )


def post_comment_gitlab(pr_number: int, body: str, repo_dir: str = ".") -> None:
    """Post a note to a GitLab MR."""
    if not GLAB:
        raise FileNotFoundError("glab executable not found in PATH")
    subprocess.run(
        [GLAB, "mr", "note", str(pr_number), "--message", body],
        cwd=repo_dir,
        check=True,
    )


@app.command()
def main(
    pr_number: Annotated[
        int,
        typer.Option("--pr-number", help="PR/MR number to comment on"),
    ],
    review_file: Annotated[
        Path | None,
        typer.Option(
            "--review-file",
            exists=True,
            readable=True,
            help=(
                "Path to review or fix-log markdown used for review/fix-validation"
                " comments"
            ),
        ),
    ] = None,
    repo_dir: Annotated[
        str,
        typer.Option(
            "--repo-dir",
            show_default=True,
            help="Path to the git repo directory where gh/glab commands should run",
        ),
    ] = ".",
    summary_file: Annotated[
        Path | None,
        typer.Option(
            "--summary-file",
            exists=True,
            readable=True,
            help="Path to file containing pre-generated bullet summary lines",
        ),
    ] = None,
    findings_file: Annotated[
        Path | None,
        typer.Option(
            "--findings-file",
            exists=True,
            readable=True,
            help=(
                "Path to file containing a preformatted findings list"
                " for findings-based comments"
            ),
        ),
    ] = None,
    acceptance_findings_file: Annotated[
        Path | None,
        typer.Option(
            "--acceptance-findings-file",
            exists=True,
            readable=True,
            help=(
                "Path to file containing a preformatted list of"
                " acceptance recommendations (recommendations comment type)"
            ),
        ),
    ] = None,
    opt_in_findings_file: Annotated[
        Path | None,
        typer.Option(
            "--opt-in-findings-file",
            exists=True,
            readable=True,
            help=(
                "Path to file containing a preformatted list of"
                " opt-in recommendations (recommendations comment type)"
            ),
        ),
    ] = None,
    comment_type: Annotated[
        _CommentType | None,
        typer.Option(
            "--comment-type",
            help=(
                "Comment type to render: review, fix_validation, acceptance, "
                "additional_acceptance, low_confidence_opt_in, or recommendations."
                " If omitted, review/fix_validation is inferred from --review-file"
                " for backward compatibility."
            ),
        ),
    ] = None,
    cycle: Annotated[
        int | None,
        typer.Option(
            "--cycle",
            help="Optional review cycle number for the title suffix",
        ),
    ] = None,
    before_score: Annotated[
        int | None,
        typer.Option(
            "--before-score",
            help="Score shown before acceptance-related comment updates",
        ),
    ] = None,
    after_score: Annotated[
        int | None,
        typer.Option(
            "--after-score",
            help="Score shown after acceptance-related comment updates",
        ),
    ] = None,
    status: Annotated[
        _ReviewStatus | None,
        typer.Option(
            "--status",
            help=(
                "Review status: clean (\u2705), passing (\U0001f7e1),"
                " or failing (\u274c)"
            ),
        ),
    ] = None,
    is_clean: Annotated[
        bool,
        typer.Option(
            "--is-clean/--no-is-clean",
            help=(
                "[DEPRECATED] Use --status=clean instead."
                " Kept for backward compatibility."
            ),
        ),
    ] = False,
) -> None:
    """Post a consensus-review comment to a GitHub PR or GitLab MR."""

    # Convert enum values to plain strings for downstream helpers
    comment_type_str: str | None = comment_type.value if comment_type else None
    status_str: str | None = status.value if status else None
    review_file_str: str | None = str(review_file) if review_file else None
    summary_file_str: str | None = str(summary_file) if summary_file else None
    findings_file_str: str | None = str(findings_file) if findings_file else None
    acceptance_findings_file_str: str | None = (
        str(acceptance_findings_file) if acceptance_findings_file else None
    )
    opt_in_findings_file_str: str | None = (
        str(opt_in_findings_file) if opt_in_findings_file else None
    )

    # 1. Read platform from .env
    platform = read_platform_from_env(repo_dir)

    # 2. Resolve comment type and build the comment body
    try:
        resolved_comment_type = infer_comment_type(comment_type_str, review_file_str)
        if resolved_comment_type in {"review", "fix_validation"}:
            if not review_file_str:
                raise ValueError(
                    "Review or fix-validation comments require --review-file."
                )
            if not summary_file_str:
                raise ValueError(
                    "Review or fix-validation comments require --summary-file."
                )
            details_text = read_required_text(review_file_str, label="review")
            resolved_status = get_status(status_str, is_clean)
            comment_body = build_review_comment_body(
                details_text,
                comment_type=resolved_comment_type,
                status=resolved_status,
                summary_file=summary_file_str,
                cycle=cycle,
                before_score=before_score,
                after_score=after_score,
            )
        elif resolved_comment_type == "recommendations":
            if cycle is None:
                raise ValueError("Recommendations comments require --cycle.")
            if acceptance_findings_file_str is None or opt_in_findings_file_str is None:
                raise ValueError(
                    "Recommendations comments require --acceptance-findings-file"
                    " and --opt-in-findings-file."
                )
            comment_body = build_recommendations_comment_body(
                cycle=cycle,
                acceptance_findings_file=acceptance_findings_file_str,
                opt_in_findings_file=opt_in_findings_file_str,
            )
        else:
            if findings_file_str is None:
                raise ValueError("Findings-list comments require --findings-file.")
            comment_body = build_findings_comment_body(
                comment_type=resolved_comment_type,
                cycle=cycle,
                findings_file=findings_file_str,
                before_score=before_score,
                after_score=after_score,
            )
    except ValueError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None

    # 3. Post the comment
    try:
        if platform == "gitlab":
            post_comment_gitlab(pr_number, comment_body, repo_dir=repo_dir)
        else:
            # Default to github for any other value
            post_comment_github(pr_number, comment_body, repo_dir=repo_dir)
    except FileNotFoundError as e:
        typer.echo(f"Error: {e}", err=True)
        raise typer.Exit(1) from None
    except subprocess.CalledProcessError as e:
        typer.echo(
            f"Error: Failed to post comment (exit code {e.returncode}): {e}", err=True
        )
        raise typer.Exit(1) from None


if __name__ == "__main__":
    app()
