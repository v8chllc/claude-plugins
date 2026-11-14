"""Exercise disposable outputs and approval-gated publication with local CLI stubs."""

import json
import os
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
    (repo / ".gitignore").write_text("# no output ignore setup\n")
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


def reserve(repo: Path) -> Path:
    result = helper(
        repo, "prepare", "--platform", "github", "--reference", "12", "--merge", SHA
    )
    assert result.returncode == 0, result.stdout
    return Path(json.loads(result.stdout)["path"])


def snapshot(repo: Path) -> tuple[str, dict[str, bytes]]:
    return (
        git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        {
            str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob("*")
            if path.is_file() and ".git" not in path.parts
        },
    )


@pytest.mark.parametrize("procedure", ["Review", "Verification", "Triage", "Publish"])
def test_external_runs_need_no_ignore_and_cleanup_all_role_files(
    project: Path, procedure: str
) -> None:
    (project / "source.py").write_text("dirty caller source\n")
    (project / "untracked.txt").write_text("caller review\n")
    (project / "private-backup").write_bytes(b"private sentinel")
    before = snapshot(project)
    runs = []
    for _ in range(2):
        run = reserve(project)
        runs.append(run)
        assert run.is_absolute() and not run.is_relative_to(project)
        try:
            for name in (
                "review.md",
                "verification.md",
                "standards.txt",
                "correctness.txt",
                "architecture.txt",
                "synthesizer.txt",
            ):
                output = run / name
                assert (
                    helper(
                        project, "check", "--run-dir", str(run), str(output)
                    ).returncode
                    == 0
                )
                with output.open("x") as stream:
                    stream.write(f"{procedure} temporary evidence")
            assert snapshot(project) == before
        finally:
            assert helper(project, "cleanup", "--run-dir", str(run)).returncode == 0
        assert not run.exists()
    assert runs[0] != runs[1]
    assert snapshot(project) == before


@pytest.mark.parametrize("escape", ["symlink", "checkout", "parent"])
def test_external_guard_protects_source_and_private_backup(
    project: Path, escape: str
) -> None:
    run = reserve(project)
    sentinel = project / "private-backup"
    sentinel.write_text("untouched")
    try:
        if escape == "symlink":
            (run / "link").symlink_to(project, target_is_directory=True)
            output = run / "link/private-backup"
        elif escape == "checkout":
            output = sentinel
        else:
            output = run / "../escape"
        assert (
            helper(project, "check", "--run-dir", str(run), str(output)).returncode == 1
        )
        assert sentinel.read_text() == "untouched"
    finally:
        assert helper(project, "cleanup", "--run-dir", str(run)).returncode == 0
    assert sentinel.read_text() == "untouched"


@pytest.mark.parametrize("platform", ["github", "gitlab"])
@pytest.mark.parametrize(
    "case", ["approved", "declined", "changed", "mismatch", "local-link"]
)
def test_publish_exact_approval_and_readback(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    platform: str,
    case: str,
) -> None:
    cli = "gh" if platform == "github" else "glab"
    stub = tmp_path / cli
    calls = tmp_path / "calls.jsonl"
    payload = tmp_path / "posted.json"
    stub.write_text(
        "#!"
        + sys.executable
        + "\n"
        + r"""
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["STUB_CALLS"], "a") as out:
    out.write(json.dumps(args) + "\n")
store = pathlib.Path(os.environ["STUB_PAYLOAD"])
if "--input" in args:
    data = json.loads(pathlib.Path(args[args.index("--input") + 1]).read_text())
    store.write_text(json.dumps(data))
    print(json.dumps({"id": 17, "html_url": "https://github.com/example/project/pull/12#issuecomment-17"}))
else:
    data = json.loads(store.read_text())
    if os.environ["STUB_CASE"] == "mismatch":
        data["body"] += "changed by platform"
    print(json.dumps(data))
"""
    )
    stub.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("STUB_CALLS", str(calls))
    monkeypatch.setenv("STUB_PAYLOAD", str(payload))
    monkeypatch.setenv("STUB_CASE", case)
    before = snapshot(project)
    run = reserve(project)
    try:
        text = "Complete review\n\nEvidence: synthetic pass.\n"
        if case == "local-link":
            text += "[evidence](./evidence.txt)\n"
        (run / "comment.md").write_text(text)
        args = [
            "publish",
            "--run-dir",
            str(run),
            "--platform",
            platform,
            "--repository",
            "example/project",
            "--reference",
            "12",
            "--text-file",
            str(run / "comment.md"),
        ]
        if case != "declined":
            (run / "approved.md").write_text(
                text if case != "changed" else "old approved text"
            )
            args += ["--approved-file", str(run / "approved.md")]
        result = helper(project, *args)
        response = json.loads(result.stdout)
        if case in ("declined", "changed", "local-link"):
            assert not calls.exists()
            assert response["outcome"] == (
                "not_published" if case == "declined" else "incomplete"
            )
        else:
            recorded = [json.loads(line) for line in calls.read_text().splitlines()]
            assert len(recorded) == 2
            assert recorded[0][0] == recorded[1][0] == "api"
            assert "--input" in recorded[0] and "POST" in recorded[0]
            assert "--input" not in recorded[1] and "POST" not in recorded[1]
            assert json.loads(payload.read_text())["body"] == text
            if platform == "github":
                assert recorded[0][1] == "repos/example/project/issues/12/comments"
                assert recorded[1][1] == "repos/example/project/issues/comments/17"
            else:
                assert (
                    recorded[0][1]
                    == "projects/example%2Fproject/merge_requests/12/notes"
                )
                assert recorded[1][1].endswith("/notes/17")
            if case == "mismatch":
                assert (
                    result.returncode == 1 and "read-back mismatch" in response["gap"]
                )
            else:
                assert result.returncode == 0 and response["outcome"] == "published"
                assert response["url"].startswith("https://")
    finally:
        assert helper(project, "cleanup", "--run-dir", str(run)).returncode == 0
    assert not run.exists() and snapshot(project) == before


def test_procedure_binds_real_checks_and_separate_outcomes() -> None:
    skill = " ".join((SKILL / "SKILL.md").read_text().split())
    for required in (
        "## Verification run",
        "scripts/artifacts.py",
        "check --run-dir <run-dir> <absolute-output-path>",
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


def test_publish_step_requires_witnessed_exact_text_approval_and_cleanup() -> None:
    skill = " ".join((SKILL / "SKILL.md").read_text().split())
    publish = skill.split("## Publish")[1].split("## Review terminal signals")[0]
    for required in (
        "explicit sponsor approval of that exact text and destination",
        "A helper flag or file alone never grants approval",
        "Any text or destination change needs renewed approval",
        "Declining or absent approval posts nothing",
        "--approved-file <run-dir>/approved.md",
        "read-back mismatch",
        "never silently accept, edit, delete or retry",
        "Remove this temporary directory on success, decline and error",
    ):
        assert required in publish
