#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Resolve a merged GitHub/GitLab change and check its net diff at HEAD."""

import argparse
import ast
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlparse

Runner = Callable[[list[str], Path], str]


class ScopeError(Exception):
    def __init__(self, reason: str, message: str) -> None:
        super().__init__(message)
        self.reason = reason


def run(command: list[str], cwd: Path) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, check=False)
    except OSError as error:
        raise ScopeError("command_failed", str(error)) from error
    if result.returncode:
        stderr = result.stderr.decode("utf-8", errors="replace")
        reason = "command_failed"
        if command[0] in ("gh", "glab") and re.search(
            r"(?i)\b(401|403|authentication|authenticate|not logged|unauthorized)\b",
            stderr,
        ):
            reason = "platform_auth"
        raise ScopeError(
            reason, f"{command[0]} exited {result.returncode}: {stderr.strip()}"
        )
    return result.stdout.decode("utf-8", errors="surrogateescape")


def reference_number(
    reference: str, platform: str, repository: str, hostname: str
) -> int:
    if reference.isdecimal() and int(reference) > 0:
        return int(reference)
    parsed = urlparse(reference)
    suffix = (
        r"/pull/([1-9][0-9]*)"
        if platform == "github"
        else r"/-/merge_requests/([1-9][0-9]*)"
    )
    match = re.fullmatch(re.escape("/" + repository) + suffix + r"/?", parsed.path)
    if parsed.scheme != "https" or parsed.netloc != hostname or not match:
        raise ScopeError(
            "command_failed",
            "reference must identify a PR/MR in the selected repository",
        )
    return int(match.group(1))


def diff_path(value: str) -> str | None:
    value = value.split("\t", 1)[0]
    if value == "/dev/null":
        return None
    if value.startswith('"'):
        try:
            value = ast.literal_eval(value)
            value = value.encode("latin-1").decode("utf-8")
        except (ValueError, SyntaxError, UnicodeError):
            raise ScopeError("command_failed", "unsupported quoted diff path") from None
    if not value.startswith(("a/", "b/")):
        raise ScopeError("command_failed", "invalid diff path")
    return value[2:]


def validate_diff(diff: str, read_file: Callable[[str], bytes | None]) -> int:
    """Check added lines and deleted files against the merge tree, not the PR head."""
    old: str | None = None
    new: str | None = None
    remaining_old = remaining_new = 0
    files = 0
    for line in diff.split("\n"):
        if line.startswith("diff --git "):
            if remaining_old or remaining_new:
                raise ScopeError("command_failed", "truncated platform diff")
            old = new = None
            files += 1
        elif remaining_old or remaining_new:
            if line.startswith("+"):
                remaining_new -= 1
                data = read_file(new) if new else None
                if data is None or line[1:].encode(
                    "utf-8", errors="surrogateescape"
                ) not in data.split(b"\n"):
                    raise ScopeError(
                        "diff_mismatch", f"added line missing at merge commit: {new}"
                    )
            elif line.startswith("-"):
                remaining_old -= 1
            elif line.startswith(" "):
                remaining_old -= 1
                remaining_new -= 1
            elif line != "\\ No newline at end of file":
                raise ScopeError("command_failed", "malformed platform diff hunk")
            if remaining_old < 0 or remaining_new < 0:
                raise ScopeError("command_failed", "invalid platform diff hunk counts")
        elif line.startswith("--- "):
            old = diff_path(line[4:])
        elif line.startswith("+++ "):
            new = diff_path(line[4:])
            if new is None and old is not None and read_file(old) is not None:
                raise ScopeError(
                    "diff_mismatch", f"deleted file exists at merge commit: {old}"
                )
        elif line.startswith("@@ "):
            match = re.match(r"@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@", line)
            if not match:
                raise ScopeError(
                    "command_failed", "malformed platform diff hunk header"
                )
            remaining_old = int(match.group(2) or "1")
            remaining_new = int(match.group(4) or "1")
    if remaining_old or remaining_new:
        raise ScopeError("command_failed", "truncated platform diff")
    if diff.strip() and files == 0:
        raise ScopeError("command_failed", "platform diff is not a unified git diff")
    return files


def platform_change(
    platform: str,
    repository: str,
    number: int,
    hostname: str,
    cwd: Path,
    runner: Runner = run,
) -> tuple[dict[str, Any], str, str]:
    if platform == "github":

        def api(endpoint: str, diff: bool = False) -> str:
            command = ["gh", "api", "--hostname", hostname, "--method", "GET", endpoint]
            if diff:
                command += ["-H", "Accept: application/vnd.github.diff"]
            return runner(command, cwd)

        item = json.loads(api(f"repos/{repository}/pulls/{number}"))
        if not item.get("merged"):
            raise ScopeError("not_merged", "PR is not merged")
        branch = json.loads(api(f"repos/{repository}"))["default_branch"]
        diff = api(f"repos/{repository}/pulls/{number}", True)
    else:
        project = quote(repository, safe="")

        def api(endpoint: str, diff: bool = False) -> str:
            return runner(
                ["glab", "api", "--hostname", hostname, "--method", "GET", endpoint],
                cwd,
            )

        item = json.loads(api(f"projects/{project}/merge_requests/{number}"))
        if item.get("state") != "merged":
            raise ScopeError("not_merged", "MR is not merged")
        branch = json.loads(api(f"projects/{project}"))["default_branch"]
        chunks = []
        page = 1
        while True:
            changes = json.loads(
                api(
                    f"projects/{project}/merge_requests/{number}/diffs?per_page=100&page={page}"
                )
            )
            if not isinstance(changes, list):
                raise ScopeError("command_failed", "invalid GitLab diff response")
            for change in changes:
                if change.get("too_large") or change.get("collapsed"):
                    raise ScopeError("command_failed", "GitLab diff is incomplete")
                old, new = change["old_path"], change["new_path"]
                old_header = "/dev/null" if change["new_file"] else "a/" + old
                new_header = "/dev/null" if change["deleted_file"] else "b/" + new
                chunks.append(
                    f"diff --git a/{old} b/{new}\n"
                    f"--- {old_header}\n+++ {new_header}\n{change['diff']}"
                )
            if len(changes) < 100:
                break
            page += 1
        diff = "\n".join(chunks)
        item["base"] = {"ref": item["target_branch"]}
    return item, branch, diff


def resolve_scope(
    platform: str,
    repository: str,
    reference: str,
    cwd: Path,
    hostname: str | None = None,
    runner: Runner = run,
) -> dict[str, Any]:
    if platform not in ("github", "gitlab"):
        raise ScopeError("command_failed", "unsupported platform")
    hostname = hostname or ("github.com" if platform == "github" else "gitlab.com")
    number = reference_number(reference, platform, repository, hostname)
    item, branch, diff = platform_change(
        platform, repository, number, hostname, cwd, runner
    )
    sha = item.get("merge_commit_sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[a-f0-9]{40}", sha):
        raise ScopeError("command_failed", "merged change has no full merge_commit_sha")
    if item["base"]["ref"] != branch:
        raise ScopeError("command_failed", "change did not target the default branch")
    if runner(["git", "rev-parse", "HEAD"], cwd).strip() != sha:
        raise ScopeError("merge_commit_mismatch", "HEAD is not the merge commit")
    runner(
        ["git", "merge-base", "--is-ancestor", sha, f"refs/remotes/origin/{branch}"],
        cwd,
    )
    cache: dict[str, bytes | None] = {}

    def read_file(path: str) -> bytes | None:
        if path not in cache:
            exists = runner(["git", "ls-tree", "--full-tree", sha, "--", path], cwd)
            cache[path] = (
                runner(["git", "show", f"{sha}:{path}"], cwd).encode(
                    "utf-8", errors="surrogateescape"
                )
                if exists
                else None
            )
        return cache[path]

    files = validate_diff(diff, read_file)
    return dict(
        platform=platform,
        reference=number,
        merge_commit=sha,
        target_branch=branch,
        scope_basis="net-diff",
        files_touched=files,
        diff=diff,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform", choices=("github", "gitlab"), required=True)
    parser.add_argument("--repo", required=True)
    parser.add_argument("--reference", required=True)
    parser.add_argument("--repo-dir", type=Path, default=Path.cwd())
    parser.add_argument("--hostname")
    args = parser.parse_args()
    try:
        result = resolve_scope(
            args.platform, args.repo, args.reference, args.repo_dir, args.hostname
        )
        print(json.dumps(result, sort_keys=True))
    except (ScopeError, ValueError, KeyError, TypeError, UnicodeError) as error:
        reason = error.reason if isinstance(error, ScopeError) else "command_failed"
        print(
            json.dumps(
                {
                    "signal": "ABORT",
                    "details": {"reason": reason, "message": str(error)},
                }
            )
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
