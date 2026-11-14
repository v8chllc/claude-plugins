#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Reserve ignored post-merge outputs without changing source or ignore rules."""

import argparse
import json
import re
import subprocess
import sys
import uuid
from pathlib import Path

BASE = Path(".local/post-merge-review")


def git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", "-C", str(root), *args], capture_output=True, text=True, check=False
    )


def guard(root: Path, relative: Path) -> None:
    if relative.is_absolute() or ".." in relative.parts:
        raise ValueError("output must be a repository-relative path without '..'")
    if not relative.is_relative_to(BASE) or relative == BASE:
        raise ValueError("output must be beneath .local/post-merge-review/")
    path = root
    for part in relative.parts:
        path /= part
        if path.is_symlink():
            raise ValueError("output path must not traverse a symlink")
    tracked = git(root, "ls-files", "--", relative.as_posix())
    if tracked.returncode or tracked.stdout:
        raise ValueError("output path contains tracked source")
    ignored = git(root, "check-ignore", "--quiet", "--", relative.as_posix())
    if ignored.returncode:
        raise ValueError(f"setup gap: {relative.as_posix()} is not ignored")


def prepare(root: Path, platform: str, reference: int, merge: str) -> Path:
    if reference < 1 or not re.fullmatch(r"[0-9a-f]{40}", merge):
        raise ValueError("reference must be positive and merge must be a full SHA")
    relative = BASE / f"{platform}-{reference}" / merge / uuid.uuid4().hex
    # Check before mkdir, and again for every actual output before it is written.
    guard(root, relative)
    for name in ("review.md", "verification.md", "evidence.txt"):
        guard(root, relative / name)
    (root / relative.parent).mkdir(parents=True, exist_ok=True)
    (root / relative).mkdir(mode=0o700, exist_ok=False)
    return relative


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    reserve = commands.add_parser("prepare")
    reserve.add_argument("--platform", required=True, choices=("github", "gitlab"))
    reserve.add_argument("--reference", required=True, type=int)
    reserve.add_argument("--merge", required=True)
    check = commands.add_parser("check")
    check.add_argument("path", type=Path)
    args = parser.parse_args()
    try:
        root = args.repo_dir.resolve(strict=True)
        resolved = git(root, "rev-parse", "--show-toplevel")
        if resolved.returncode or Path(resolved.stdout.strip()).resolve() != root:
            raise ValueError("repo-dir must name the Git repository root")
        if args.command == "prepare":
            relative = prepare(root, args.platform, args.reference, args.merge)
        else:
            relative = args.path
            guard(root, relative)
        print(json.dumps({"outcome": "ready", "path": relative.as_posix()}))
        return 0
    except (OSError, ValueError) as exc:
        print(json.dumps({"outcome": "incomplete", "gap": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
