"""Post one agent-tooling-review report to a GitHub pull request."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

MARKER = re.compile(r"<!-- agent-tooling-review\s*\n(.*?)\n-->", re.DOTALL)
STATUSES = {"clean", "passing", "failing"}


def gh_command(command: list[str]) -> list[str]:
    """Keep both read and write calls safe with Windows command shims."""
    if os.name == "nt" and Path(command[0]).suffix.lower() in {".cmd", ".bat"}:
        if any(re.search(r'[&|<>^()%!"\r\n]', part) for part in command):
            raise ValueError("cmd.exe metacharacters are not allowed in command paths")
        return [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", *command]
    return command


def valid_marker(value: object) -> bool:
    """Treat comments as untrusted data; admit only the versioned identity."""
    return (
        isinstance(value, dict)
        and value.get("schema_version") == 1
        and type(value.get("cycle")) is int
        and value["cycle"] > 0
        and isinstance(value.get("reviewed_sha"), str)
        and re.fullmatch(r"[0-9a-f]{40}", value["reviewed_sha"]) is not None
        and isinstance(value.get("status"), str)
        and value["status"] in STATUSES
    )


def render_report(body: str, cycle: int, reviewed_sha: str, status: str) -> str:
    metadata = dict(
        schema_version=1, cycle=cycle, reviewed_sha=reviewed_sha, status=status
    )
    if not valid_marker(metadata) or MARKER.search(body):
        raise ValueError("invalid or duplicate review metadata")
    return (
        body.rstrip()
        + "\n\n<!-- agent-tooling-review\n"
        + json.dumps(metadata)
        + "\n-->\n"
    )


def recover_context(
    comments: list[dict[str, object]], head: str, poster_login: str
) -> dict[str, object]:
    """Recover cycle identity and scope only from valid posted markers."""
    if not poster_login:
        raise ValueError("authenticated poster login is required")
    records: list[tuple[dict[str, object], dict[str, object]]] = []
    for comment in comments:
        author = comment.get("author")
        body = comment.get("body")
        if (
            not isinstance(author, dict)
            or author.get("login") != poster_login
            or not isinstance(body, str)
        ):
            continue
        matches = MARKER.findall(body)
        if len(matches) != 1:
            continue
        try:
            metadata = json.loads(matches[0])
        except (ValueError, TypeError):
            continue
        if valid_marker(metadata):
            records.append((metadata, comment))
    if not records:
        return dict(
            next_cycle=1, scope_basis="full_diff: no valid prior marker", prior=[]
        )
    metadata, _ = max(records, key=lambda pair: int(str(pair[0]["cycle"])))
    sha = str(metadata["reviewed_sha"])
    ancestor = subprocess.run(
        ["git", "merge-base", "--is-ancestor", sha, head],
        check=False,
        capture_output=True,
        text=True,
        timeout=120,
    )
    return dict(
        next_cycle=max(int(str(record["cycle"])) for record, _ in records) + 1,
        scope_basis=f"{sha}..{head}"
        if ancestor.returncode == 0
        else "full_diff: prior SHA is not an available ancestor",
        prior=[comment for _, comment in records],
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", required=True, help="GitHub owner/repo")
    parser.add_argument("--pr", required=True, type=int, help="Pull request number")
    parser.add_argument("--body-file", type=Path, help="Report file")
    parser.add_argument("--cycle", type=int)
    parser.add_argument("--reviewed-sha")
    parser.add_argument("--status", choices=sorted(STATUSES))
    parser.add_argument("--recover", action="store_true", help="Read prior PR reviews")
    args = parser.parse_args()

    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.repo):
        parser.error("--repo must be owner/repo")
    if args.pr < 1:
        parser.error("--pr must be a positive number")
    if not args.recover and (
        args.body_file is None
        or not args.body_file.is_file()
        or not args.body_file.read_text(encoding="utf-8").strip()
    ):
        parser.error("--body-file must name a non-empty report file")

    gh = shutil.which("gh")
    if gh is None:
        parser.error("gh was not found on PATH")
    metadata = (args.cycle, args.reviewed_sha, args.status)
    if any(value is not None for value in metadata) and not all(
        value is not None for value in metadata
    ):
        parser.error("--cycle, --reviewed-sha and --status must be supplied together")
    if args.recover:
        if args.body_file is not None or any(value is not None for value in metadata):
            parser.error("--recover cannot be combined with posting arguments")
        try:
            result = subprocess.run(
                gh_command(
                    [
                        gh,
                        "pr",
                        "view",
                        str(args.pr),
                        "--repo",
                        args.repo,
                        "--json",
                        "comments,headRefOid",
                    ]
                ),
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
            if result.returncode:
                print(result.stderr or result.stdout, file=sys.stderr, end="")
                return result.returncode
            data = json.loads(result.stdout)
            head = data["headRefOid"]
            local = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            ).stdout.strip()
            if local != head:
                parser.error(
                    "PR/local-head mismatch; recovery requires the PR checkout"
                )
            actor = subprocess.run(
                gh_command([gh, "api", "user", "--jq", ".login"]),
                check=True,
                capture_output=True,
                text=True,
                timeout=120,
            ).stdout.strip()
            print(json.dumps(recover_context(data["comments"], head, actor)))
            return 0
        except (
            OSError,
            ValueError,
            KeyError,
            TypeError,
            subprocess.SubprocessError,
        ) as exc:
            print(f"review recovery failed: {exc}", file=sys.stderr)
            return 1
    assert args.body_file is not None
    rendered: str | None = None
    if args.cycle is not None:
        try:
            rendered = render_report(
                args.body_file.read_text(encoding="utf-8"), *metadata
            )
        except ValueError as exc:
            parser.error(str(exc))
    command = [
        gh,
        "pr",
        "comment",
        str(args.pr),
        "--repo",
        args.repo,
        "--body-file",
        str(args.body_file),
    ]
    try:
        gh_command(command)
    except ValueError as exc:
        parser.error(str(exc))

    try:
        with tempfile.TemporaryDirectory(prefix="agent-tooling-review-") as scratch:
            if rendered is not None:
                report = Path(scratch) / "report.md"
                report.write_text(rendered, encoding="utf-8")
                command[-1] = str(report)
            result = subprocess.run(
                gh_command(command),
                check=False,
                capture_output=True,
                text=True,
                timeout=120,
            )
    except subprocess.TimeoutExpired:
        print("gh pr comment timed out after 120 seconds", file=sys.stderr)
        return 124
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if result.returncode:
        print(result.stderr or result.stdout, file=sys.stderr, end="")
        return result.returncode
    print(result.stdout.strip())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
