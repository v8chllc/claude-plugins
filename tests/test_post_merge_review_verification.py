"""Exercise ignored-output boundaries and bind scenario use to the shipped skill."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/v8ch/skills/post-merge-review"
HELPER = SKILL / "scripts/artifacts.py"
SHA = "0" * 40


def git(repo: Path, *args: str) -> str:
    return subprocess.check_output(["git", "-C", str(repo), *args], text=True)


@pytest.fixture
def project(tmp_path: Path) -> Path:
    repo = tmp_path / "project"
    repo.mkdir()
    git(repo, "init", "--quiet")
    git(repo, "config", "user.name", "Synthetic")
    git(repo, "config", "user.email", "synthetic@example.invalid")
    (repo / ".gitignore").write_text(".local/\n")
    (repo / "source.py").write_text("value = 1\n")
    git(repo, "add", ".")
    git(repo, "commit", "--quiet", "-m", "fixture")
    return repo


def helper(repo: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(HELPER), "--repo-dir", str(repo), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def reserve(repo: Path) -> subprocess.CompletedProcess[str]:
    return helper(
        repo, "prepare", "--platform", "github", "--reference", "12", "--merge", SHA
    )


def source_snapshot(repo: Path) -> tuple[str, str, bytes, bytes]:
    return (
        git(repo, "rev-parse", "HEAD"),
        git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        (repo / "source.py").read_bytes(),
        (repo / ".gitignore").read_bytes(),
    )


def test_ignored_runs_are_unique_and_do_not_change_source(project: Path) -> None:
    (project / "untracked.txt").write_text("caller draft\n")
    backup = project / ".local/private-backup"
    backup.parent.mkdir()
    backup.write_bytes(b"private sentinel")
    before = source_snapshot(project)
    first, second = reserve(project), reserve(project)
    assert first.returncode == second.returncode == 0
    paths = [json.loads(result.stdout)["path"] for result in (first, second)]
    assert paths[0] != paths[1]
    for path in paths:
        output = f"{path}/verification.md"
        assert helper(project, "check", output).returncode == 0
        with (project / output).open("x") as stream:
            stream.write("separate verification evidence\n")
    assert source_snapshot(project) == before
    assert (project / "untracked.txt").read_text() == "caller draft\n"
    assert backup.read_bytes() == b"private sentinel"
    assert (project / paths[0] / "verification.md").read_text().startswith("separate")


def test_unignored_destination_is_gap_before_any_write(project: Path) -> None:
    (project / ".gitignore").write_text("# caller has not prepared ignores\n")
    before = source_snapshot(project)
    result = reserve(project)
    assert result.returncode == 1
    assert json.loads(result.stdout)["outcome"] == "incomplete"
    assert "not ignored" in json.loads(result.stdout)["gap"]
    assert not (project / ".local").exists()
    assert source_snapshot(project) == before


def test_each_output_is_rechecked_for_ignore_exceptions(project: Path) -> None:
    result = reserve(project)
    path = json.loads(result.stdout)["path"]
    # A later caller change to ignore rules must not authorize unignored evidence.
    (project / ".gitignore").write_text(".local/**\n!.local/**/\n!.local/**/leak.txt\n")
    result = helper(project, "check", f"{path}/leak.txt")
    assert result.returncode == 1
    assert "not ignored" in result.stdout
    assert not (project / path / "leak.txt").exists()


def test_symlink_output_cannot_escape_to_private_backup(project: Path) -> None:
    outside = project.parent / "private"
    outside.mkdir()
    sentinel = outside / "sentinel"
    sentinel.write_text("untouched")
    (project / ".local").symlink_to(outside, target_is_directory=True)
    result = reserve(project)
    assert result.returncode == 1
    assert "symlink" in result.stdout
    assert sorted(path.name for path in outside.iterdir()) == ["sentinel"]
    assert sentinel.read_text() == "untouched"


def test_tracked_output_is_rejected_even_under_ignore_rule(project: Path) -> None:
    tracked = project / ".local/post-merge-review/existing.md"
    tracked.parent.mkdir(parents=True)
    tracked.write_text("tracked source")
    git(project, "add", "--force", str(tracked))
    result = helper(project, "check", ".local/post-merge-review/existing.md")
    assert result.returncode == 1
    assert "tracked source" in result.stdout
    assert tracked.read_text() == "tracked source"


@pytest.mark.parametrize("path", ["../escape", "/tmp/escape", ".local/other"])
def test_output_must_stay_within_post_merge_artifacts(project: Path, path: str) -> None:
    assert helper(project, "check", path).returncode == 1


def test_procedure_binds_real_checks_and_separate_outcomes() -> None:
    skill = " ".join((SKILL / "SKILL.md").read_text().split())
    for required in (
        "## Verification run",
        "scripts/artifacts.py",
        "check <relative-output-path>",
        "before every comparison",
        "git rev-parse HEAD",
        "equals its full `merge_commit`",
        "just-produced or existing valid review",
        "started: false",
        "exact command, cwd, purpose",
        "actual stdout/stderr",
        "diagnostic command's exit 0",
        '"signal":"VERIFICATION_COMPLETE"',
        "`passed`, `failed` or `incomplete`",
        "Do not silently install",
        "Explicitly authorized reuse",
        "reset databases",
        "return the gap in chat without writing a report",
    ):
        assert required in skill


def test_claim_qualification_preserves_report_and_draft_limits() -> None:
    skill = " ".join((SKILL / "SKILL.md").read_text().split())
    for required in (
        "split failure and impact clauses",
        "`reproduced`, `contradicted` or `unverified`",
        "Full contradiction must be explicit",
        "original ID, location, section, severity and merge identity",
        "preserve the original report byte-for-byte",
        "Carry only supported premises into a work draft",
        "excluded premises and gaps",
        "Stop for sponsor approval after each drafted follow-up",
        "Vetting may lower a disposition and never raises it",
        "No action",
    ):
        assert required in skill
