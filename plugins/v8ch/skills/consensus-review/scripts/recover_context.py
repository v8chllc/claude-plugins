#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///

"""Recover consensus-review history from a PR/MR thread for the Claude plugin.

The PR/MR thread is the durable audit trail. This script fetches its comments,
keeps the ones carrying a valid schema-v2 ``consensus-review`` block, lists
schema-v1 review comments as legacy history, and resolves the scope basis for
the next cycle: the delta since the latest v2 reviewed SHA when that SHA is
still an ancestor of HEAD, and the full diff otherwise.

Byte-identical to the Codex copy in ``v8chllc/codex-plugins`` apart from this
docstring.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from review_contract import (
    DELTA_SINCE_PREFIX,
    FULL_DIFF,
    ContractError,
    is_legacy_review,
    parse_metadata_block,
    strip_metadata_block,
    validate_metadata,
)

GH = shutil.which("gh")
GLAB = shutil.which("glab")
GIT = shutil.which("git")

SCORE_SOURCE = "raw review score"

_DETAILS_OPEN = "<details>"
_DETAILS_CLOSE = "</details>"
_SUMMARY_CLOSE = "</summary>"


@dataclass(frozen=True)
class ReviewComment:
    """A PR/MR comment carrying a consensus-review metadata block."""

    metadata: dict[str, Any]
    body: str
    created_at: str
    url: str
    author: str
    legacy: bool

    @property
    def cycle(self) -> int:
        raw = self.metadata.get("cycle")
        try:
            return int(raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return 0

    @property
    def score(self) -> str:
        raw = self.metadata.get("score")
        try:
            return f"{int(raw)}/100"  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return "?/100"

    @property
    def status(self) -> str:
        return str(self.metadata.get("status") or "unknown")


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


def normalize_comment(raw: dict[str, Any]) -> dict[str, str]:
    """Normalize a GitHub or GitLab comment object into common fields."""
    author = raw.get("author") or raw.get("user") or {}
    if isinstance(author, dict):
        author_name = str(author.get("login") or author.get("username") or "")
    else:
        author_name = str(author)
    return {
        "body": str(raw.get("body") or raw.get("note") or ""),
        "created_at": str(
            raw.get("created_at") or raw.get("createdAt") or raw.get("created") or ""
        ),
        "url": str(raw.get("html_url") or raw.get("web_url") or raw.get("url") or ""),
        "author": author_name,
    }


def parse_review_comments(raw_comments: list[dict[str, Any]]) -> list[ReviewComment]:
    """Keep the valid schema-v2 reviews plus the schema-v1 legacy reviews.

    A comment whose metadata fails validation is ignored entirely, so a
    malformed or hand-edited block can never supply history or a scope basis.
    """
    reviews: list[ReviewComment] = []
    for raw in raw_comments:
        normalized = normalize_comment(raw)
        payload = parse_metadata_block(normalized["body"])
        if payload is None:
            continue
        try:
            metadata = validate_metadata(payload)
            legacy = False
        except ContractError:
            if not is_legacy_review(payload):
                continue
            metadata = payload
            legacy = True
        reviews.append(
            ReviewComment(
                metadata=metadata,
                body=normalized["body"],
                created_at=normalized["created_at"],
                url=normalized["url"],
                author=normalized["author"],
                legacy=legacy,
            )
        )
    return sorted(reviews, key=lambda review: (review.cycle, review.created_at))


def extract_surviving_body(body: str) -> str:
    """Return the review report from a posted comment body.

    The comment wraps the report in one ``<details>`` element. Falling back to
    the metadata-stripped body keeps a hand-edited or legacy comment readable.
    """
    stripped = strip_metadata_block(body)
    start = stripped.find(_DETAILS_OPEN)
    if start == -1:
        return stripped
    summary_end = stripped.find(_SUMMARY_CLOSE, start)
    if summary_end == -1:
        return stripped
    content_start = summary_end + len(_SUMMARY_CLOSE)
    end = stripped.find(_DETAILS_CLOSE, content_start)
    if end == -1:
        return stripped
    return stripped[content_start:end].strip() or stripped


def run_command(command: list[str], repo_dir: str | Path) -> str:
    """Run a platform command and return its stdout, raising on a failure."""
    result = subprocess.run(command, cwd=repo_dir, capture_output=True, text=True)
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode, command, result.stdout, result.stderr
        )
    return result.stdout


def decode_json_stream(payload: str) -> list[Any]:
    """Decode one or more concatenated JSON values.

    ``gh api --paginate`` and ``glab api --paginate`` emit one JSON array per
    page, concatenated with no enclosing array. A plain ``json.loads`` raises on
    the second page, so every review thread past the first page of comments
    would fail to recover.
    """
    decoder = json.JSONDecoder()
    values: list[Any] = []
    text = payload.strip()
    index = 0
    while index < len(text):
        value, offset = decoder.raw_decode(text, index)
        values.append(value)
        index = offset
        while index < len(text) and text[index] in " \t\r\n":
            index += 1
    return values


def flatten_comment_pages(payload: str) -> list[dict[str, Any]]:
    """Flatten paginated JSON array pages into one comment list."""
    comments: list[dict[str, Any]] = []
    for page in decode_json_stream(payload):
        if isinstance(page, list):
            comments.extend(item for item in page if isinstance(item, dict))
        elif isinstance(page, dict):
            comments.append(page)
    return comments


def fetch_github_comments(
    number: int, repo_dir: str | Path = "."
) -> list[dict[str, Any]]:
    """Fetch GitHub PR issue-level comments through gh.

    Note: this retrieves issue-level comments only, not inline review comments
    attached to diff lines. Consensus-review posts issue-level comments.
    """
    if not GH:
        raise FileNotFoundError("gh executable not found in PATH")
    payload = run_command(
        [
            GH,
            "api",
            f"repos/{{owner}}/{{repo}}/issues/{number}/comments",
            "--paginate",
        ],
        repo_dir,
    )
    return flatten_comment_pages(payload)


def fetch_gitlab_comments(
    number: int, repo_dir: str | Path = "."
) -> list[dict[str, Any]]:
    """Fetch GitLab MR notes through glab."""
    if not GLAB:
        raise FileNotFoundError("glab executable not found in PATH")
    payload = run_command(
        [
            GLAB,
            "api",
            f"projects/:id/merge_requests/{number}/notes",
            "--paginate",
        ],
        repo_dir,
    )
    return flatten_comment_pages(payload)


def fetch_platform_comments(
    number: int, *, platform: str, repo_dir: str | Path = "."
) -> list[dict[str, Any]]:
    """Fetch PR/MR comments for the selected platform."""
    if platform == "gitlab":
        return fetch_gitlab_comments(number, repo_dir)
    return fetch_github_comments(number, repo_dir)


def load_comments_json(path: Path) -> list[dict[str, Any]]:
    """Load platform-style comments from a JSON file instead of fetching them."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    comments = payload.get("comments", []) if isinstance(payload, dict) else payload
    if not isinstance(comments, list):
        raise ValueError(
            "comments JSON must be a list or an object with a comments list"
        )
    return [comment for comment in comments if isinstance(comment, dict)]


def sha_is_ancestor(sha: str, head: str, repo_dir: str | Path = ".") -> bool | None:
    """Return whether sha is an ancestor of head, or None when unverifiable."""
    if not GIT:
        return None
    result = subprocess.run(
        [GIT, "merge-base", "--is-ancestor", sha, head],
        cwd=repo_dir,
        capture_output=True,
        text=True,
    )
    if result.returncode == 0:
        return True
    if result.returncode == 1:
        return False
    return None


def resolve_scope_basis(
    reviews: list[ReviewComment], *, head: str = "HEAD", repo_dir: str | Path = "."
) -> tuple[str, str]:
    """Return the scope basis for the next cycle and the reason for it."""
    current = [review for review in reviews if not review.legacy]
    if not current:
        return FULL_DIFF, "no prior schema-v2 review comment on this PR/MR"

    latest = current[-1]
    sha = str(latest.metadata["reviewed_sha"])
    ancestry = sha_is_ancestor(sha, head, repo_dir)
    if ancestry is None:
        return (
            FULL_DIFF,
            f"could not verify that reviewed SHA {sha} from cycle "
            f"{latest.cycle:02d} is an ancestor of {head}",
        )
    if not ancestry:
        return (
            FULL_DIFF,
            f"reviewed SHA {sha} from cycle {latest.cycle:02d} is no longer an "
            f"ancestor of {head}",
        )
    return (
        f"{DELTA_SINCE_PREFIX}{sha}",
        f"latest schema-v2 review is cycle {latest.cycle:02d}, reviewed {sha}",
    )


def next_cycle(reviews: list[ReviewComment]) -> int:
    """Return the next cycle number; cycle numbers accumulate across toolchains."""
    return max((review.cycle for review in reviews), default=0) + 1


def provenance_line(review: ReviewComment) -> str:
    """Render one provenance line for a recovered review."""
    if review.legacy:
        return f"Score: {review.score}. Status: {review.status}. Schema: v1 (legacy)."
    metadata = review.metadata
    return (
        f"Score: {review.score}. Status: {review.status}. "
        f"Delegation: {metadata['delegation_mode']}. Plan: {metadata['plan_source']}. "
        f"Scope: {metadata['scope_basis']}. Reviewed: {metadata['reviewed_sha']}. "
        f"Blast radius: {metadata['files_touched']} files, "
        f"{metadata['findings_opened']} opened, {metadata['findings_closed']} closed."
    )


def build_context_output(
    *,
    number: int,
    platform: str,
    reviews: list[ReviewComment],
    scope_basis: str,
    scope_reason: str,
) -> str:
    """Build the recovered-context report consumed by the orchestrating skill."""
    label = "MR" if platform == "gitlab" else "PR"
    lines = [
        "# RECOVERED_CONTEXT",
        "",
        f"**Platform:** {platform}",
        f"**{label} number:** {number}",
        "**Audit source:** PR/MR comments",
        f"**Next cycle:** {next_cycle(reviews):02d}",
        f"**Score source:** {SCORE_SOURCE}",
        f"**Scope basis:** {scope_basis}",
        f"**Scope reason:** {scope_reason}",
        "",
    ]

    current = [review for review in reviews if not review.legacy]
    legacy = [review for review in reviews if review.legacy]

    if not reviews:
        lines += [
            "## Prior Reviews",
            "",
            "None. This is the first cycle.",
            "",
        ]
        return "\n".join(lines)

    lines += ["## Prior Reviews", ""]
    if current:
        for review in current:
            lines += [
                f"### Cycle {review.cycle:02d}",
                "",
                f"*{provenance_line(review)}*",
                f"*Comment:* {review.url or 'URL unavailable'}",
                "",
                extract_surviving_body(review.body),
                "",
            ]
    else:
        lines += ["None. This is the first schema-v2 cycle.", ""]

    if legacy:
        lines += [
            "## Legacy Reviews",
            "",
            "> Schema-v1 comments. Listed as history only: they never supply a",
            "> narrowing basis, and their other v1 comment types are ignored.",
            "",
        ]
        for review in legacy:
            lines += [
                f"- Cycle {review.cycle:02d} — {review.score} "
                f"({review.status}) — {review.url or 'URL unavailable'}",
            ]
        lines.append("")

    return "\n".join(lines)


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""
    parser = argparse.ArgumentParser(
        description="Recover consensus-review history from a PR/MR thread.",
    )
    parser.add_argument("number", type=int, metavar="NUMBER", help="PR/MR number")
    parser.add_argument(
        "--platform",
        choices=["github", "gitlab"],
        default=None,
        help="Override DEV_SEC_OPS_PLATFORM detection",
    )
    parser.add_argument(
        "--repo-dir",
        default=".",
        help="Git repository directory where gh/glab/git commands run",
    )
    parser.add_argument(
        "--comments-json",
        default=None,
        help="Read comments from a JSON file instead of fetching them",
    )
    parser.add_argument(
        "--head",
        default="HEAD",
        help="Revision the recorded SHA is checked against",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """Print recovered PR/MR context. Returns a process exit code."""
    args = build_parser().parse_args(argv)
    platform = resolve_platform(args.platform, args.repo_dir)

    try:
        raw_comments = (
            load_comments_json(Path(args.comments_json))
            if args.comments_json
            else fetch_platform_comments(
                args.number, platform=platform, repo_dir=args.repo_dir
            )
        )
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        detail = str(error)
        if isinstance(error, subprocess.CalledProcessError) and error.stderr:
            detail = f"{error}: {error.stderr.strip()}"
        print(f"Error: failed to recover PR/MR comments: {detail}", file=sys.stderr)
        return 1

    reviews = parse_review_comments(raw_comments)
    scope_basis, scope_reason = resolve_scope_basis(
        reviews, head=args.head, repo_dir=args.repo_dir
    )
    print(
        build_context_output(
            number=args.number,
            platform=platform,
            reviews=reviews,
            scope_basis=scope_basis,
            scope_reason=scope_reason,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
