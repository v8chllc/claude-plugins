#!/usr/bin/env uv run
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Manage disposable external evidence and explicitly approved publication."""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import quote, urlsplit


def guard(root: Path, run: Path, output: Path) -> None:
    if not run.is_absolute() or run.is_symlink():
        raise ValueError("run directory must be an absolute, isolated directory")
    resolved = run.resolve(strict=True)
    if resolved.is_relative_to(root) or not run.name.startswith("post-merge-review-"):
        raise ValueError("run directory must be outside the reviewed checkout")
    if (
        not output.is_absolute()
        or not output.is_relative_to(run)
        or ".." in output.parts
    ):
        raise ValueError("output must stay within the supplied run directory")
    path = run
    for part in output.relative_to(run).parts:
        path /= part
        if path.is_symlink():
            raise ValueError("output path must not traverse a symlink")


def prepare(root: Path, platform: str, reference: int, merge: str) -> Path:
    if reference < 1 or not re.fullmatch(r"[0-9a-f]{40}", merge):
        raise ValueError("reference must be positive and merge must be a full SHA")
    parent = Path(tempfile.gettempdir()).resolve()
    if parent.is_relative_to(root):
        raise ValueError("temporary directory must be outside the reviewed checkout")
    return Path(tempfile.mkdtemp(prefix=f"post-merge-review-{platform}-{reference}-"))


def api(
    cli: str, endpoint: str, payload: Path | None = None, hostname: str | None = None
) -> dict[str, object]:
    command = [cli, "api", endpoint]
    if hostname:
        command += ["--hostname", hostname]
    if payload is not None:
        command += ["--method", "POST", "--input", str(payload)]
    result = subprocess.run(command, capture_output=True, text=True, check=True)
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise ValueError("platform returned a malformed comment")
    return value


class HTMLLinks(HTMLParser):
    """Collect rendered HTML link and image destinations, including entities."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.targets: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.targets.extend(
            value
            for name, value in attrs
            if name in ("href", "src") and value is not None
        )


def reject_local_links(text: str) -> None:
    """Check inline, reference, autolink and HTML destinations before posting."""
    # Every reference form resolves through a definition; inspect definitions even
    # when unused rather than risk publishing an inaccessible evidence destination.
    destination = r"(<[^>\n]*>|[^\s)]+)"
    targets = re.findall(r"\]\(\s*" + destination, text)
    targets += re.findall(
        r"(?m)^[ \t]*(?:(?:>[ \t]*|(?:[-+*]|\d+[.)])[ \t]+)[ \t]*)*"
        r"\[(?:\\.|[^\]\\])+\]:[ \t]*(?:\n[ \t]*(?:>[ \t]*)*)?" + destination,
        text,
    )
    targets += re.findall(r"<([A-Za-z][A-Za-z0-9+.-]*:[^<>\s]+)>", text)
    html = HTMLLinks()
    html.feed(text)
    html.close()
    targets += html.targets
    for target in targets:
        target = unescape(target.removeprefix("<").removesuffix(">"))
        # CommonMark permits backslash escapes for ASCII punctuation in URLs.
        target = re.sub(r"\\([!\"#$%&'()*+,\-./:;<=>?@\[\]\\^_`{|}~])", r"\1", target)
        parsed = urlsplit(target)
        remote = parsed.scheme.lower() in ("http", "https") and bool(parsed.netloc)
        remote = remote or (target.startswith("//") and bool(parsed.netloc))
        if not remote and not target.startswith("#"):
            raise ValueError("posted text must not link to local files")
    if re.search(r"\bfile:", text, re.IGNORECASE):
        raise ValueError("posted text must not link to local files")


def publish(
    root: Path,
    run: Path,
    platform: str,
    repository: str,
    reference: int,
    text_file: Path,
    approved_file: Path | None,
    hostname: str,
) -> dict[str, object]:
    guard(root, run, text_file)
    if approved_file is None:
        return {"outcome": "not_published", "reason": "exact text was not approved"}
    guard(root, run, approved_file)
    text = text_file.read_bytes().decode("utf-8")
    if text_file.read_bytes() != approved_file.read_bytes() or not text.strip():
        raise ValueError("publication text differs from explicitly approved text")
    reject_local_links(text)
    if reference < 1 or not re.fullmatch(r"[^/\s]+(?:/[^/\s]+)+", repository):
        raise ValueError("invalid repository or reference")
    cli = "gh" if platform == "github" else "glab"
    endpoint = (
        f"repos/{repository}/issues/{reference}/comments"
        if platform == "github"
        else f"projects/{quote(repository, safe='')}/merge_requests/{reference}/notes"
    )
    payload = run / "publish.json"
    guard(root, run, payload)
    with payload.open("x", encoding="utf-8") as stream:
        json.dump({"body": text}, stream)
    posted = api(cli, endpoint, payload, hostname)
    comment_id = posted.get("id")
    if type(comment_id) is not int:
        raise ValueError("post returned no comment identity; do not retry")
    read_endpoint = (
        f"repos/{repository}/issues/comments/{comment_id}"
        if platform == "github"
        else f"{endpoint}/{comment_id}"
    )
    readback = api(cli, read_endpoint, hostname=hostname)
    if readback.get("body") != text:
        raise ValueError("posted body read-back mismatch; do not edit, delete or retry")
    url = (
        posted.get("html_url")
        if platform == "github"
        else f"https://{hostname}/{repository}/-/merge_requests/{reference}#note_{comment_id}"
    )
    if not isinstance(url, str) or not url.startswith("https://"):
        raise ValueError("post returned no comment URL; do not retry")
    return {"outcome": "published", "url": url}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-dir", required=True, type=Path)
    commands = parser.add_subparsers(dest="command", required=True)
    reserve = commands.add_parser("prepare")
    reserve.add_argument("--platform", required=True, choices=("github", "gitlab"))
    reserve.add_argument("--reference", required=True, type=int)
    reserve.add_argument("--merge", required=True)
    for name in ("check", "cleanup", "publish"):
        command = commands.add_parser(name)
        command.add_argument("--run-dir", required=True, type=Path)
        if name == "check":
            command.add_argument("path", type=Path)
        if name == "publish":
            command.add_argument(
                "--platform", required=True, choices=("github", "gitlab")
            )
            command.add_argument("--repository", required=True)
            command.add_argument("--reference", required=True, type=int)
            command.add_argument("--text-file", required=True, type=Path)
            command.add_argument("--approved-file", type=Path)
            command.add_argument("--hostname")
    args = parser.parse_args()
    try:
        root = args.repo_dir.resolve(strict=True)
        resolved = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--show-toplevel"],
            capture_output=True,
            text=True,
            check=True,
        )
        if Path(resolved.stdout.strip()).resolve() != root:
            raise ValueError("repo-dir must name the Git repository root")
        if args.command == "prepare":
            result: dict[str, object] = {
                "outcome": "ready",
                "path": str(prepare(root, args.platform, args.reference, args.merge)),
            }
        elif args.command == "publish":
            result = publish(
                root,
                args.run_dir,
                args.platform,
                args.repository,
                args.reference,
                args.text_file,
                args.approved_file,
                args.hostname
                or ("github.com" if args.platform == "github" else "gitlab.com"),
            )
        else:
            output = args.path if args.command == "check" else args.run_dir
            guard(root, args.run_dir, output)
            if args.command == "cleanup":
                shutil.rmtree(args.run_dir)
            result = {"outcome": "ready", "path": str(output)}
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        print(json.dumps({"outcome": "incomplete", "gap": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
