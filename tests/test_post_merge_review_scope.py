"""Prove merged-tree scope with real git history and mocked read-only APIs."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/v8ch/skills/post-merge-review/scripts/resolve_scope.py"
spec = importlib.util.spec_from_file_location("post_merge_scope", SCRIPT)
assert spec and spec.loader
scope = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scope)


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", *args], cwd=repo, text=True).strip()


@pytest.fixture
def rebased(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    git(repo, "config", "user.email", "test@example.invalid")
    git(repo, "config", "user.name", "Test")
    (repo / "file.txt").write_text("base\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    git(repo, "checkout", "-b", "feature")
    (repo / "file.txt").write_text("base\nfirst\n")
    git(repo, "commit", "-am", "first")
    (repo / "other.txt").write_text("second\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "second")
    original_head = git(repo, "rev-parse", "HEAD")
    diff = subprocess.check_output(
        ["git", "diff", base, original_head], cwd=repo, text=True
    )
    git(repo, "checkout", "main")
    (repo / "unrelated").write_text("main advanced\n")
    git(repo, "add", ".")
    git(repo, "commit", "-m", "advance main")
    git(repo, "checkout", "feature")
    git(repo, "rebase", "main")
    git(repo, "checkout", "main")
    git(repo, "merge", "--ff-only", "feature")
    merged = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", merged)
    assert merged != original_head
    check = subprocess.run(
        ["git", "merge-base", "--is-ancestor", original_head, "main"], cwd=repo
    )
    assert check.returncode == 1
    return repo, merged, diff


def runner_for(sha: str, diff: str, merged: bool = True):
    def runner(command: list[str], cwd: Path) -> str:
        if command[0] == "git":
            return str(scope.run(command, cwd))
        assert "--method" in command and command[command.index("--method") + 1] == "GET"
        endpoint = command[command.index("GET") + 1]
        if endpoint.endswith("/diffs?per_page=100&page=1"):
            return json.dumps(
                [
                    dict(
                        old_path="file.txt",
                        new_path="file.txt",
                        new_file=False,
                        deleted_file=False,
                        diff="@@ -1 +1,2 @@\n base\n+first\n",
                    ),
                    dict(
                        old_path="other.txt",
                        new_path="other.txt",
                        new_file=True,
                        deleted_file=False,
                        diff="@@ -0,0 +1 @@\n+second\n",
                    ),
                ]
            )
        if "pulls/12" in endpoint or "merge_requests/12" in endpoint:
            if "Accept: application/vnd.github.diff" in command:
                return diff
            return json.dumps(
                dict(
                    merged=merged,
                    state="merged" if merged else "opened",
                    merge_commit_sha=sha,
                    base={"ref": "main"},
                    target_branch="main",
                )
            )
        return json.dumps(dict(default_branch="main"))

    return runner


@pytest.mark.parametrize("platform", ["github", "gitlab"])
def test_matching_rebase_merge_uses_net_diff(rebased, platform: str) -> None:
    repo, sha, diff = rebased
    result = scope.resolve_scope(
        platform, "owner/repo", "12", repo, runner=runner_for(sha, diff)
    )
    assert result["merge_commit"] == sha
    assert result["files_touched"] == 2
    assert "+first" in result["diff"]
    assert "+first" not in git(repo, "show", "--format=", "HEAD")


def test_tree_missing_added_line_fails(rebased) -> None:
    repo, sha, diff = rebased
    (repo / "file.txt").write_text("base\n")
    git(repo, "commit", "-am", "wrong merge tree")
    sha = git(repo, "rev-parse", "HEAD")
    git(repo, "update-ref", "refs/remotes/origin/main", sha)
    with pytest.raises(scope.ScopeError, match="added line missing") as error:
        scope.resolve_scope(
            "github", "owner/repo", "12", repo, runner=runner_for(sha, diff)
        )
    assert error.value.reason == "diff_mismatch"


@pytest.mark.parametrize(
    ("merged", "wrong_sha", "reason"),
    [
        (False, False, "not_merged"),
        (True, True, "merge_commit_mismatch"),
    ],
)
def test_wrong_state_or_checkout_aborts(
    rebased, merged: bool, wrong_sha: bool, reason: str
) -> None:
    repo, sha, diff = rebased
    with pytest.raises(scope.ScopeError) as error:
        scope.resolve_scope(
            "github",
            "owner/repo",
            "12",
            repo,
            runner=runner_for("a" * 40 if wrong_sha else sha, diff, merged),
        )
    assert error.value.reason == reason


def test_deleted_file_must_be_absent() -> None:
    diff = "diff --git a/gone b/gone\n--- a/gone\n+++ /dev/null\n@@ -1 +0,0 @@\n-old\n"
    assert scope.validate_diff(diff, lambda path: None) == 1
    with pytest.raises(scope.ScopeError) as error:
        scope.validate_diff(diff, lambda path: b"old\n")
    assert error.value.reason == "diff_mismatch"


def test_added_line_starting_with_header_markers_is_checked() -> None:
    diff = "diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -0,0 +1 @@\n++++ content\n"
    assert scope.validate_diff(diff, lambda path: b"+++ content\n") == 1
    with pytest.raises(scope.ScopeError) as error:
        scope.validate_diff(diff, lambda path: b"other\n")
    assert error.value.reason == "diff_mismatch"


@pytest.mark.parametrize(
    "diff",
    [
        "not a diff",
        "diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -1 +1 @@\n-old\n",
    ],
)
def test_malformed_or_truncated_diff_rejected(diff: str) -> None:
    with pytest.raises(scope.ScopeError) as error:
        scope.validate_diff(diff, lambda path: b"new\n")
    assert error.value.reason == "command_failed"


def test_empty_diff_and_url_reference(rebased) -> None:
    repo, sha, _ = rebased
    result = scope.resolve_scope(
        "github",
        "owner/repo",
        "https://github.com/owner/repo/pull/12",
        repo,
        runner=runner_for(sha, ""),
    )
    assert result["diff"] == ""
    assert result["files_touched"] == 0
    with pytest.raises(scope.ScopeError):
        scope.reference_number(
            "https://github.com/other/repo/pull/12",
            "github",
            "owner/repo",
            "github.com",
        )


def test_cli_abort_is_structured_and_read_only(tmp_path: Path) -> None:
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--platform",
            "github",
            "--repo",
            "owner/repo",
            "--reference",
            "invalid",
            "--repo-dir",
            str(tmp_path),
        ],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 1
    signal = json.loads(result.stdout)
    assert signal["signal"] == "ABORT"
    assert signal["details"]["reason"] == "command_failed"
    assert list(tmp_path.iterdir()) == []


def test_crlf_and_unicode_line_separators_are_literal_file_content() -> None:
    diff = "diff --git a/a b/a\n--- a/a\n+++ b/a\n@@ -0,0 +1 @@\n+first\r\n"
    assert scope.validate_diff(diff, lambda path: b"first\r\n") == 1
    diff = diff.replace("first\r", "first\u0085second")
    assert scope.validate_diff(diff, lambda path: "first\u0085second\n".encode()) == 1
