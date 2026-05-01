#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.10"
# dependencies = [
#   "typer>=0.9.0",
#   "python-dotenv>=1.0.0",
# ]
# ///

"""
Consensus Review Context Recovery

Reads consensus-review audit history from PR/MR comments. The PR/MR thread is
the durable source of truth; local files may be used as scratch space during a
single invocation, but recovery never depends on `.rouge` state.

Comment detection:
  Audit comments contain a hidden HTML metadata block rendered by
  post_review_comment.py::

      <!-- consensus-review
      {"schema_version": 1, "type": "review", "cycle": 1}
      -->

Platform detection:
  Reads DEV_SEC_OPS_PLATFORM from .env at the working directory root.
  "github" (default) fetches PR comments with gh.
  "gitlab" fetches MR notes with glab.
  Override with --platform github|gitlab if needed.
"""

import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any

import typer
from dotenv import dotenv_values

GH = shutil.which("gh")
GLAB = shutil.which("glab")

_METADATA_RE = re.compile(
    r"<!--\s*consensus-review\s*(.*?)\s*-->",
    re.DOTALL,
)
_SCORE_RE = re.compile(r"Quality Score.*?(\d+)/100", re.IGNORECASE)
_SUMMARY_RE = re.compile(
    r"### Summary\s*\n(?P<summary>.*?)(?:\n<details>|\n### |\Z)",
    re.DOTALL,
)
_DETAILS_RE = re.compile(
    # Matches the first <details> block in a comment body. Audit comments
    # wrap their full content in a single top-level <details> element, so
    # .search() capturing only the first match is intentional.
    #
    # HARD RULE: synthesized comment bodies posted by consensus-review-poster
    # must NOT contain nested <details> blocks.  This regex uses a non-greedy
    # .*? match and will stop at the first </details> it encounters; nested
    # blocks would cause truncation.  Enforce this constraint in
    # post_review_context.py::_build_comment_body and in any template that
    # wraps content inside a <details> element.
    r"<details>\s*<summary>.*?</summary>\s*(?P<details>.*?)\s*</details>",
    re.DOTALL | re.IGNORECASE,
)
_INLINE_ACCEPTED_RE = re.compile(
    r"^\d+\.\s+\[([A-Z]+)\]\s+(.+?)[ \t]+[—-][ \t]+`?([^`\n]+?)`?\s*$",
    re.MULTILINE,
)
# Marker prefix written by git-ops/scripts/post_review_context.py.
# Both files must agree on this shape; if the marker changes, update both.
_REVIEW_CONTEXT_MARKER = "<!-- review-context"
_ROUGE_CONTEXT_RE = re.compile(
    r"<!--\s*review-context\s*(\{.*?\})\s*-->",
    re.DOTALL,
)
_SPEC_DETAILS_RE = re.compile(
    r"<details>\s*<summary>Spec</summary>\s*(.*?)\s*</details>",
    re.DOTALL | re.IGNORECASE,
)
_PLAN_DETAILS_RE = re.compile(
    r"<details>\s*<summary>Plan</summary>\s*(.*?)\s*</details>",
    re.DOTALL | re.IGNORECASE,
)

# Format: "N. <title> — `<file>` (<source>)"
# The `source` group captures the reviewer name (e.g. "correctness-reviewer")
# as rendered by post_review_comment.py.
_INLINE_OPTED_IN_RE = re.compile(
    r"^\d+\.\s+(.+?)[ \t]+[—-][ \t]+`?([^`\n]+?)`?[ \t]+\((.+?)\)\s*$",
    re.MULTILINE,
)

# Format: "N. [F-REVIEW_NUMBER] [SEVERITY] <title> — `<file>`"
# Lines come from the recommendations comment template
# (recommendations-comment.md.tmpl). The `review_number` group preserves the
# synthesizer's canonical `[F-N]` index so the human reviewer can resolve the
# recommendation back to the original finding.
_INLINE_RECOMMENDATION_RE = re.compile(
    r"^\d+\.\s+\[F-(\d+)\]\s+\[([A-Z]+)\]\s+(.+?)[ \t]+[—-][ \t]+`?([^`\n]+?)`?\s*$",
    re.MULTILINE,
)
_RECOMMENDATIONS_ACCEPTANCE_SECTION_RE = re.compile(
    r"###\s+Recommended for Acceptance\s*\n(?P<body>.*?)(?=\n###\s|\Z)",
    re.DOTALL,
)
_RECOMMENDATIONS_OPT_IN_SECTION_RE = re.compile(
    r"###\s+Recommended for Opt-In\s*\n(?P<body>.*?)(?=\n###\s|\Z)",
    re.DOTALL,
)
# Strips template FORMAT RULE blocks (HTML comments) before regex parsing
# recommendations sections.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)

app = typer.Typer()


@dataclass(frozen=True)
class AuditComment:
    """A PR/MR comment that contains consensus-review metadata."""

    metadata: dict[str, Any]
    body: str
    created_at: str
    url: str
    author: str

    @property
    def cycle(self) -> int:
        raw = self.metadata.get("cycle")
        if raw is None:
            return 0
        try:
            return int(raw)
        except (TypeError, ValueError):
            return 0

    @property
    def comment_type(self) -> str:
        raw = self.metadata.get("type")
        return str(raw) if raw is not None else "unknown"


def _read_platform(override: str | None, repo_dir: str | Path = ".") -> str:
    """Return the normalized platform name from --platform override or .env."""
    if override:
        return override.strip().lower()
    env = dotenv_values(Path(repo_dir) / ".env")
    raw: str = env.get("DEV_SEC_OPS_PLATFORM") or "github"
    return raw.strip().strip('"').strip("'").lower()


def _extract_score_from_text(text: str) -> str:
    """Return 'NN/100' from review text, or '?/100' if not found."""
    match = _SCORE_RE.search(text)
    return f"{match.group(1)}/100" if match else "?/100"


def _parse_accepted_findings(text: str) -> list[dict[str, str]]:
    """Extract accepted findings from posted comment bodies."""
    return [
        {
            "severity": m.group(1),
            "title": m.group(2).strip(),
            "file": m.group(3).strip(),
        }
        for m in _INLINE_ACCEPTED_RE.finditer(text)
    ]


def _parse_opted_in_findings(text: str) -> list[dict[str, str]]:
    """Extract low-confidence opt-ins from posted comment bodies."""
    return [
        {
            "title": m.group(1).strip(),
            "file": m.group(2).strip(),
            "source": m.group(3).strip(),
        }
        for m in _INLINE_OPTED_IN_RE.finditer(text)
    ]


def _parse_recommendation_lines(text: str) -> list[dict[str, str]]:
    """Extract recommendation entries from a single template section body."""
    return [
        {
            "review_number": m.group(1),
            "severity": m.group(2),
            "title": m.group(3).strip(),
            "file": m.group(4).strip(),
        }
        for m in _INLINE_RECOMMENDATION_RE.finditer(text)
    ]


def _parse_acceptance_recommendations(text: str) -> list[dict[str, str]]:
    """Extract acceptance recommendations from a recommendations comment body.

    Scopes parsing to the ``Recommended for Acceptance`` section so opt-in
    lines from the same comment are not collected here. HTML comments (e.g.
    FORMAT RULE examples in the template) are stripped before parsing so
    example lines do not produce phantom entries.
    """
    match = _RECOMMENDATIONS_ACCEPTANCE_SECTION_RE.search(text)
    if not match:
        return []
    cleaned = _HTML_COMMENT_RE.sub("", match.group("body"))
    return _parse_recommendation_lines(cleaned)


def _parse_opt_in_recommendations(text: str) -> list[dict[str, str]]:
    """Extract opt-in recommendations from a recommendations comment body.

    HTML comments (e.g. FORMAT RULE examples in the template) are stripped
    before parsing so example lines do not produce phantom entries.
    """
    match = _RECOMMENDATIONS_OPT_IN_SECTION_RE.search(text)
    if not match:
        return []
    cleaned = _HTML_COMMENT_RE.sub("", match.group("body"))
    return _parse_recommendation_lines(cleaned)


def _extract_summary(text: str) -> str:
    """Return the concise summary block from a posted review/fix comment."""
    match = _SUMMARY_RE.search(text)
    if not match:
        return "*Summary not found in comment body.*"
    summary = match.group("summary").strip()
    return summary or "*Summary was empty.*"


def _extract_metadata(text: str) -> dict[str, Any] | None:
    """Return consensus-review metadata from a comment body, if present."""
    match = _METADATA_RE.search(text)
    if not match:
        return None
    try:
        metadata = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    if not isinstance(metadata, dict):
        return None
    if metadata.get("schema_version") != 1:
        return None
    if not metadata.get("type"):
        return None
    return metadata


def _normalise_comment(raw: dict[str, Any]) -> dict[str, str]:
    """Normalize GitHub/GitLab comment JSON into common fields."""
    author = raw.get("author") or raw.get("user") or {}
    if isinstance(author, dict):
        author_name = str(author.get("login") or author.get("username") or "")
    else:
        author_name = str(author)
    return {
        "body": str(raw["body"] if "body" in raw else raw.get("note", "")),
        "created_at": str(raw.get("createdAt") or raw.get("created_at") or ""),
        "url": str(raw.get("url") or raw.get("web_url") or ""),
        "author": author_name,
    }


def parse_audit_comments(raw_comments: list[dict[str, Any]]) -> list[AuditComment]:
    """Filter raw platform comments down to consensus-review audit comments."""
    audit_comments: list[AuditComment] = []
    for raw in raw_comments:
        normalized = _normalise_comment(raw)
        metadata = _extract_metadata(normalized["body"])
        if metadata is None:
            continue
        audit_comments.append(
            AuditComment(
                metadata=metadata,
                body=normalized["body"],
                created_at=normalized["created_at"],
                url=normalized["url"],
                author=normalized["author"],
            )
        )
    return sorted(audit_comments, key=lambda c: (c.cycle, c.created_at, c.comment_type))


def _run_json(command: list[str], repo_dir: str | Path) -> Any:
    """Run a platform command that returns JSON."""
    result = subprocess.run(
        command,
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, command, result.stdout, result.stderr
        )
    return json.loads(result.stdout or "null")


def fetch_github_comments(
    number: int, repo_dir: str | Path = "."
) -> list[dict[str, Any]]:
    """Fetch GitHub PR issue-level comments through gh.

    Note: This retrieves only issue-level (top-level) PR comments, not inline
    review comments attached to specific diff lines.
    """
    if not GH:
        raise FileNotFoundError("gh executable not found in PATH")
    payload = _run_json([GH, "pr", "view", str(number), "--json", "comments"], repo_dir)
    if not isinstance(payload, dict):
        return []
    comments = payload.get("comments", [])
    return comments if isinstance(comments, list) else []


def fetch_gitlab_comments(
    number: int, repo_dir: str | Path = "."
) -> list[dict[str, Any]]:
    """Fetch GitLab MR notes through glab."""
    if not GLAB:
        raise FileNotFoundError("glab executable not found in PATH")
    payload = _run_json(
        [GLAB, "api", f"projects/:id/merge_requests/{number}/notes", "--paginate"],
        repo_dir,
    )
    return payload if isinstance(payload, list) else []


def fetch_platform_comments(
    number: int,
    *,
    platform: str,
    repo_dir: str | Path = ".",
) -> list[dict[str, Any]]:
    """Fetch PR/MR comments for the selected platform."""
    if platform == "gitlab":
        return fetch_gitlab_comments(number, repo_dir)
    return fetch_github_comments(number, repo_dir)


def load_comments_json(path: Path) -> list[dict[str, Any]]:
    """Load normalized or platform-style comments from a JSON fixture/file."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        comments = payload.get("comments", [])
    else:
        comments = payload
    if not isinstance(comments, list):
        raise ValueError(
            "comments JSON must be a list or an object with a comments list"
        )
    return [comment for comment in comments if isinstance(comment, dict)]


def _metadata_score(comment: AuditComment) -> str:
    """Return the score string from a review comment.

    Prefers the structured metadata field. Falls back to body-text scanning
    only when the metadata field is absent or non-numeric, which occurs on
    older PR threads written before schema_version 1 added the score field.
    """
    raw = comment.metadata.get("score")
    if raw is None:
        raw = comment.metadata.get("before_score")
    if raw is None:
        return _extract_score_from_text(comment.body)
    try:
        return f"{int(raw)}/100"
    except (TypeError, ValueError):
        return _extract_score_from_text(comment.body)


def _strip_metadata(text: str) -> str:
    """Remove the hidden consensus-review metadata block from a comment body."""
    return _METADATA_RE.sub("", text, count=1).strip()


def _extract_details_text(text: str) -> str:
    """Return full review/fix details from a posted comment body when present."""
    match = _DETAILS_RE.search(text)
    if not match:
        return _strip_metadata(text)
    details = match.group("details").strip()
    return details or _strip_metadata(text)


def _latest_review_comment(audit_comments: list[AuditComment]) -> AuditComment | None:
    reviews = [c for c in audit_comments if c.comment_type == "review"]
    return reviews[-1] if reviews else None


def _latest_fix_comment_for_cycle(
    audit_comments: list[AuditComment], cycle: int
) -> AuditComment | None:
    fixes = [
        c
        for c in audit_comments
        if c.comment_type == "fix_validation" and c.cycle == cycle
    ]
    return fixes[-1] if fixes else None


def _parsed_findings_with_source(
    comments: list[AuditComment],
    parser: Any,
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for comment in comments:
        for finding in parser(comment.body):
            findings.append(
                {
                    **finding,
                    "cycle": comment.cycle,
                    "comment_type": comment.comment_type,
                    "comment_url": comment.url,
                }
            )
    return findings


def extract_planning_context(
    raw_comments: list[dict[str, Any]],
) -> dict[str, Any] | None:
    """Find and parse the Rouge review-context comment from raw PR/MR comments.

    Returns a dict with spec, plan, has_spec, has_plan, schema_version, and
    url when a valid planning_context marker is found, or None otherwise.
    """
    # NOTE: This function re-normalizes each raw comment via _normalise_comment even
    # though parse_audit_comments also normalizes.  The double traversal is intentional
    # here because extract_planning_context operates on the *original* raw list (which
    # may include non-audit comments) rather than the filtered AuditComment list.  If
    # extract_planning_context is extended to inspect additional comment types beyond
    # rouge planning-context comments, revisit whether a shared normalized
    # representation should be passed to avoid duplicate normalization.  Adding new
    # consensus-review audit comment types (review, fix_validation, recommendations,
    # etc.) does NOT trigger this obligation.
    for raw in raw_comments:
        normalized = _normalise_comment(raw)
        body = normalized["body"]
        meta_match = _ROUGE_CONTEXT_RE.search(body)
        if meta_match is None:
            continue
        try:
            metadata = json.loads(meta_match.group(1))
        except json.JSONDecodeError:
            continue
        if not isinstance(metadata, dict) or metadata.get("schema_version") != 1:
            continue
        spec: str | None = None
        plan: str | None = None
        spec_match = _SPEC_DETAILS_RE.search(body)
        if spec_match:
            spec = spec_match.group(1).strip() or None
        plan_match = _PLAN_DETAILS_RE.search(body)
        if plan_match:
            plan = plan_match.group(1).strip() or None
        return {
            "schema_version": metadata.get("schema_version"),
            "has_spec": metadata.get("has_spec", False),
            "has_plan": metadata.get("has_plan", False),
            "spec": spec,
            "plan": plan,
            "url": normalized["url"],
        }
    return None


def resolve_audit_artifacts(
    *,
    number: int,
    platform: str,
    audit_comments: list[AuditComment],
    scratch_dir: Path | None = None,
    planning_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Resolve latest-cycle artifacts from PR/MR comments and write scratch files."""
    latest_review = _latest_review_comment(audit_comments)
    latest_cycle = latest_review.cycle if latest_review else 0
    next_cycle = latest_cycle + 1
    latest_fix = (
        _latest_fix_comment_for_cycle(audit_comments, latest_cycle)
        if latest_review
        else None
    )

    review_cycles = {
        c.cycle for c in audit_comments if c.comment_type == "review" and c.cycle > 0
    }
    fix_cycles = {
        c.cycle
        for c in audit_comments
        if c.comment_type == "fix_validation" and c.cycle > 0
    }
    cycle_gaps = [
        {"cycle": cycle, "reason": "missing fix-validation comment"}
        for cycle in sorted(review_cycles - fix_cycles)
    ]

    accepted_comments = [
        c
        for c in audit_comments
        if c.comment_type in {"acceptance", "additional_acceptance"}
    ]
    additional_acceptance_comments = [
        c
        for c in audit_comments
        if c.comment_type == "additional_acceptance" and c.cycle == latest_cycle
    ]
    low_confidence_comments = [
        c for c in audit_comments if c.comment_type == "low_confidence_opt_in"
    ]
    current_low_confidence_comments = [
        c for c in low_confidence_comments if c.cycle == latest_cycle
    ]
    recommendations_comments = [
        c for c in audit_comments if c.comment_type == "recommendations"
    ]
    current_recommendations_comments = [
        c for c in recommendations_comments if c.cycle == latest_cycle
    ]

    scratch_paths: dict[str, str] = {}
    summary: dict[str, Any] = {
        "schema_version": 1,
        "number": number,
        "platform": platform,
        "audit_source": "PR/MR comments",
        "latest_cycle": latest_cycle,
        "next_cycle": next_cycle,
        "latest_review": None,
        "latest_fix_validation": None,
        "cycle_gaps": cycle_gaps,
        "accepted_findings": _parsed_findings_with_source(
            accepted_comments,
            _parse_accepted_findings,
        ),
        "current_cycle_additional_acceptances": _parsed_findings_with_source(
            additional_acceptance_comments,
            _parse_accepted_findings,
        ),
        "low_confidence_opt_ins": _parsed_findings_with_source(
            low_confidence_comments,
            _parse_opted_in_findings,
        ),
        "current_cycle_low_confidence_opt_ins": _parsed_findings_with_source(
            current_low_confidence_comments,
            _parse_opted_in_findings,
        ),
        "current_cycle_acceptance_recommendations": _parsed_findings_with_source(
            current_recommendations_comments,
            _parse_acceptance_recommendations,
        ),
        "current_cycle_opt_in_recommendations": _parsed_findings_with_source(
            current_recommendations_comments,
            _parse_opt_in_recommendations,
        ),
        "source_comment_urls": {
            "reviews": [
                c.url for c in audit_comments if c.comment_type == "review" and c.url
            ],
            "fix_validations": [
                c.url
                for c in audit_comments
                if c.comment_type == "fix_validation" and c.url
            ],
            "acceptances": [c.url for c in accepted_comments if c.url],
            "low_confidence_opt_ins": [c.url for c in low_confidence_comments if c.url],
            "recommendations": [c.url for c in recommendations_comments if c.url],
        },
        "scratch_paths": scratch_paths,
        "planning_context": planning_context,
    }

    if latest_review:
        summary["latest_review"] = {
            "cycle": latest_review.cycle,
            "status": latest_review.metadata.get("status"),
            "score": _metadata_score(latest_review),
            "url": latest_review.url,
            "created_at": latest_review.created_at,
        }
    if latest_fix:
        summary["latest_fix_validation"] = {
            "cycle": latest_fix.cycle,
            "status": latest_fix.metadata.get("status"),
            "url": latest_fix.url,
            "created_at": latest_fix.created_at,
        }

    if scratch_dir is None:
        return summary

    scratch_dir.mkdir(parents=True, exist_ok=True)
    if latest_review:
        review_path = scratch_dir / f"review-{latest_review.cycle:02d}.md"
        review_path.write_text(
            _extract_details_text(latest_review.body) + "\n",
            encoding="utf-8",
        )
        scratch_paths["latest_review"] = str(review_path)
    if latest_fix:
        fix_path = scratch_dir / f"fix-{latest_fix.cycle:02d}.md"
        fix_path.write_text(
            _extract_details_text(latest_fix.body) + "\n",
            encoding="utf-8",
        )
        scratch_paths["latest_fix_validation"] = str(fix_path)

    if current_recommendations_comments:
        # Use the most recent recommendations comment for the latest cycle.
        latest_rec = current_recommendations_comments[-1]
        acceptance_lines = _parse_acceptance_recommendations(latest_rec.body)
        opt_in_lines = _parse_opt_in_recommendations(latest_rec.body)
        acceptance_path = (
            scratch_dir / f"acceptance-recommendations-{latest_rec.cycle:02d}.md"
        )
        acceptance_path.write_text(
            "\n".join(
                f"{i}. [F-{f['review_number']}] [{f['severity']}] "
                f"{f['title']} — `{f['file']}`"
                for i, f in enumerate(acceptance_lines, start=1)
            )
            + ("\n" if acceptance_lines else "None.\n"),
            encoding="utf-8",
        )
        scratch_paths["current_cycle_acceptance_recommendations"] = str(acceptance_path)
        opt_in_path = scratch_dir / f"opt-in-recommendations-{latest_rec.cycle:02d}.md"
        opt_in_path.write_text(
            "\n".join(
                f"{i}. [F-{f['review_number']}] [{f['severity']}] "
                f"{f['title']} — `{f['file']}`"
                for i, f in enumerate(opt_in_lines, start=1)
            )
            + ("\n" if opt_in_lines else "None.\n"),
            encoding="utf-8",
        )
        scratch_paths["current_cycle_opt_in_recommendations"] = str(opt_in_path)

    summary_path = scratch_dir / f"resolver-summary-{latest_cycle:02d}.json"
    summary_path.write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return summary


def build_context_output(
    *,
    number: int,
    platform: str,
    audit_comments: list[AuditComment],
    planning_context: dict[str, Any] | None = None,
) -> str:
    """Build the markdown context block consumed by the orchestrating skill."""
    platform_label = "MR" if platform == "gitlab" else "PR"
    review_comments = [c for c in audit_comments if c.comment_type == "review"]
    fix_comments = [c for c in audit_comments if c.comment_type == "fix_validation"]
    accepted_comments = [
        c
        for c in audit_comments
        if c.comment_type in {"acceptance", "additional_acceptance"}
    ]
    opted_in_comments = [
        c for c in audit_comments if c.comment_type == "low_confidence_opt_in"
    ]
    recommendation_comments = [
        c for c in audit_comments if c.comment_type == "recommendations"
    ]

    max_cycle = max((c.cycle for c in review_comments), default=0)
    next_cycle = max_cycle + 1

    lines: list[str] = [
        f"## Consensus Review — Prior Cycle Context for {platform_label} {number}",
        "",
        f"**Platform:** {platform}",
        "**Audit source:** PR/MR comments",
        f"**Next cycle:** {next_cycle:02d}",
        "",
    ]

    if planning_context:
        spec = planning_context.get("spec")
        plan = planning_context.get("plan")
        ctx_url = planning_context.get("url") or "n/a"
        lines += ["### Planning Context", "", f"*Source:* {ctx_url}", ""]
        if spec:
            lines += [
                "<details>",
                "<summary>Source Specification</summary>",
                "",
                spec,
                "",
                "</details>",
                "",
            ]
        if plan:
            lines += [
                "<details>",
                "<summary>Implementation Plan</summary>",
                "",
                plan,
                "",
                "</details>",
                "",
            ]
        if not spec and not plan:
            lines += ["*Planning context comment found but no content extracted.*", ""]
    else:
        lines += ["### Planning Context", "", "Not found.", ""]

    if not audit_comments:
        lines.append(
            "No prior consensus-review comments found. This is the first cycle."
        )
        lines.append("")
        return "\n".join(lines)

    if review_comments:
        fix_cycles = {c.cycle for c in fix_comments}
        lines += [
            "### Prior Cycles",
            "",
            "| Cycle | Score | Status | Fix validation | Comment |",
            "|-------|-------|--------|----------------|---------|",
        ]
        for comment in review_comments:
            cycle = f"{comment.cycle:02d}"
            score = _metadata_score(comment)
            status = str(comment.metadata.get("status") or "unknown")
            fix_label = "present" if comment.cycle in fix_cycles else "absent"
            url = comment.url or "n/a"
            lines.append(f"| {cycle} | {score} | {status} | {fix_label} | {url} |")
        lines.append("")

    if review_comments or fix_comments:
        lines += ["### Cycle Summaries", ""]
        for comment in [*review_comments, *fix_comments]:
            cycle = f"{comment.cycle:02d}"
            score = (
                _metadata_score(comment) if comment.comment_type == "review" else "fix"
            )
            label = "Review" if comment.comment_type == "review" else "Fix validation"
            lines.append(f"**{label} cycle {cycle} ({score}):**")
            lines.append(_extract_summary(comment.body))
            lines.append("")

    if accepted_comments:
        lines += [
            "### Operator-Accepted Findings",
            "",
            "> These findings were explicitly accepted in the PR/MR thread.",
            "> The synthesizer and fixer must not re-raise or address them.",
            "",
        ]
        total = 0
        for comment in accepted_comments:
            findings = _parse_accepted_findings(comment.body)
            lines.append(
                f"**From {comment.comment_type} comment, cycle {comment.cycle:02d}:**"
            )
            if findings:
                total += len(findings)
                lines.extend(
                    f"- [{f['severity']}] {f['title']} — `{f['file']}`"
                    for f in findings
                )
            else:
                lines.append("*No parseable accepted findings found in comment body.*")
            lines.append("")
        if total:
            lines.append(
                f"Total accepted: {total} findings. "
                "These are excluded from scoring in future cycles."
            )
            lines.append("")
    else:
        lines += ["### Operator-Accepted Findings", "", "None.", ""]

    if opted_in_comments:
        lines += [
            "### Opted-In Low-Confidence Findings (Historical)",
            "",
            (
                "> Historical only — low-confidence opt-in must be prompted "
                "fresh each cycle."
            ),
            "",
        ]
        total_opted_in = 0
        for comment in opted_in_comments:
            findings = _parse_opted_in_findings(comment.body)
            lines.append(f"**From cycle {comment.cycle:02d}:**")
            if findings:
                total_opted_in += len(findings)
                lines.extend(
                    f"- {f['title']} — `{f['file']}` ({f['source']})" for f in findings
                )
            else:
                lines.append(
                    "*No parseable low-confidence opt-ins found in comment body.*"
                )
            lines.append("")
        if total_opted_in:
            lines.append(
                f"Total historical opt-ins: {total_opted_in} findings "
                f"across {len(opted_in_comments)} comment(s)."
            )
            lines.append("")
    else:
        lines += [
            "### Opted-In Low-Confidence Findings (Historical)",
            "",
            "None.",
            "",
        ]

    if recommendation_comments:
        lines += [
            "### Review Recommendations (Historical)",
            "",
            (
                "> advisory only — see SKILL.md Step 4c for the full rule."
                " Each line preserves the synthesizer's `[F-REVIEW_NUMBER]`."
            ),
            "",
        ]
        total_recs = 0
        for comment in recommendation_comments:
            acceptance = _parse_acceptance_recommendations(comment.body)
            opt_in = _parse_opt_in_recommendations(comment.body)
            lines.append(f"**From cycle {comment.cycle:02d}:**")
            if acceptance:
                total_recs += len(acceptance)
                lines.append("- Recommended for Acceptance:")
                lines.extend(
                    f"  - [F-{f['review_number']}] [{f['severity']}] "
                    f"{f['title']} — `{f['file']}`"
                    for f in acceptance
                )
            if opt_in:
                total_recs += len(opt_in)
                lines.append("- Recommended for Opt-In:")
                lines.extend(
                    f"  - [F-{f['review_number']}] [{f['severity']}] "
                    f"{f['title']} — `{f['file']}`"
                    for f in opt_in
                )
            if not acceptance and not opt_in:
                lines.append("*No parseable recommendations found in comment body.*")
            lines.append("")
        if total_recs:
            lines.append(
                f"Total historical recommendations: {total_recs} entries "
                f"across {len(recommendation_comments)} comment(s)."
            )
            lines.append("")
    else:
        lines += [
            "### Review Recommendations (Historical)",
            "",
            "None.",
            "",
        ]

    latest_review = review_comments[-1] if review_comments else None
    latest_fix = fix_comments[-1] if fix_comments else None
    lines += ["### Latest Audit References", ""]
    if latest_review:
        lines.append(
            f"- Latest review: cycle {latest_review.cycle:02d} — "
            f"{latest_review.url or 'comment URL unavailable'}"
        )
    if latest_fix:
        lines.append(
            f"- Latest fix validation: cycle {latest_fix.cycle:02d} — "
            f"{latest_fix.url or 'comment URL unavailable'}"
        )
    if not latest_review and not latest_fix:
        lines.append("None.")
    lines.append("")
    fix_cycles = {comment.cycle for comment in fix_comments}
    gap_cycles = [
        comment.cycle for comment in review_comments if comment.cycle not in fix_cycles
    ]
    if gap_cycles:
        lines += [
            "### Cycle Gaps",
            "",
            (
                "The following review cycles have no fix-validation comment. "
                "Continue with the recovered PR/MR context, but surface these "
                "gaps to the fixer:"
            ),
            "",
        ]
        lines.extend(
            f"- Cycle {cycle:02d}: missing fix-validation comment"
            for cycle in gap_cycles
        )
        lines.append("")

    return "\n".join(lines)


@app.command()
def main(
    mr_number: Annotated[int, typer.Argument(metavar="NUMBER")],
    platform: Annotated[
        str | None,
        typer.Option(
            "--platform",
            show_default=False,
            help=(
                "Override platform detection. Accepted values: github, gitlab. "
                "Defaults to DEV_SEC_OPS_PLATFORM in .env, or 'github' if absent."
            ),
        ),
    ] = None,
    repo_dir: Annotated[
        Path,
        typer.Option(
            "--repo-dir",
            exists=True,
            file_okay=False,
            dir_okay=True,
            readable=True,
            help="Git repository directory where gh/glab commands should run.",
        ),
    ] = Path("."),
    comments_json: Annotated[
        Path | None,
        typer.Option(
            "--comments-json",
            exists=True,
            readable=True,
            help="Read comments from JSON instead of fetching from gh/glab.",
        ),
    ] = None,
    scratch_dir: Annotated[
        Path | None,
        typer.Option(
            "--scratch-dir",
            file_okay=False,
            dir_okay=True,
            help=(
                "Write disposable latest-cycle artifacts recovered from PR/MR "
                "comments into this directory."
            ),
        ),
    ] = None,
    json_summary: Annotated[
        bool,
        typer.Option(
            "--json-summary",
            help=(
                "Print the machine-readable resolver summary instead of "
                "markdown context."
            ),
        ),
    ] = False,
) -> None:
    """Output prior-cycle context recovered from PR/MR comments."""
    resolved_platform = _read_platform(platform, repo_dir)

    try:
        raw_comments = (
            load_comments_json(comments_json)
            if comments_json is not None
            else fetch_platform_comments(
                mr_number,
                platform=resolved_platform,
                repo_dir=repo_dir,
            )
        )
    except (FileNotFoundError, ValueError, subprocess.CalledProcessError) as e:
        detail = str(e)
        if isinstance(e, subprocess.CalledProcessError) and e.stderr:
            detail = f"{e}: {e.stderr.strip()}"
        typer.echo(f"Error: failed to recover PR/MR comments: {detail}", err=True)
        raise typer.Exit(1) from None

    audit_comments = parse_audit_comments(raw_comments)
    planning_context = extract_planning_context(raw_comments)
    summary = resolve_audit_artifacts(
        number=mr_number,
        platform=resolved_platform,
        audit_comments=audit_comments,
        scratch_dir=scratch_dir,
        planning_context=planning_context,
    )
    if json_summary:
        typer.echo(json.dumps(summary, indent=2, sort_keys=True))
        return
    typer.echo(
        build_context_output(
            number=mr_number,
            platform=resolved_platform,
            audit_comments=audit_comments,
            planning_context=planning_context,
        )
    )


if __name__ == "__main__":
    app()
