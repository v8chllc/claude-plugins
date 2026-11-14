"""Exercise shipped temporary-directory and direct posting instructions."""

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "plugins/v8ch/skills/post-merge-review"


def text() -> str:
    return (SKILL / "SKILL.md").read_text()


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


def snapshot(repo: Path) -> tuple[str, dict[str, bytes]]:
    return (
        git(repo, "status", "--porcelain=v1", "--untracked-files=all"),
        {
            str(path.relative_to(repo)): path.read_bytes()
            for path in repo.rglob("*")
            if path.is_file() and ".git" not in path.parts
        },
    )


@pytest.mark.parametrize("procedure", ["Review", "Verification", "Triage"])
def test_external_runs_need_no_ignore_and_cleanup_all_role_files(
    project: Path, tmp_path: Path, procedure: str
) -> None:
    skill = text()
    assert "create one directory with `mktemp -d` outside" in skill
    assert 'remove its directory with `rm -r -- "<run-dir>"`' in skill
    (project / "source.py").write_text("dirty caller source\n")
    (project / "untracked.txt").write_text("caller review\n")
    (project / "private-backup").write_bytes(b"private sentinel")
    before = snapshot(project)
    runs = []
    for _ in range(2):
        # Execute the literal shipped creation command in a caller-prepared
        # external TMPDIR; no checkout output rule or helper participates.
        run = Path(
            subprocess.check_output(
                ["sh", "-c", "mktemp -d"],
                cwd=project,
                env={**os.environ, "TMPDIR": str(tmp_path)},
                text=True,
            ).strip()
        )
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
                (run / name).write_text(f"{procedure} temporary evidence")
            assert snapshot(project) == before
        finally:
            subprocess.run(["rm", "-r", "--", str(run)], check=True)
        assert not run.exists()
    assert runs[0] != runs[1]
    assert snapshot(project) == before


@pytest.mark.parametrize("procedure", ["Review", "Verification"])
@pytest.mark.parametrize("platform", ["github", "gitlab"])
@pytest.mark.parametrize("post_fails", [False, True])
def test_direct_report_posting_uses_one_cli_call_and_returns_url(
    project: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    procedure: str,
    platform: str,
    post_fails: bool,
) -> None:
    skill = text()
    assert (
        "approval step, posting-text parsing, filtering, link scanning or read-back"
        in (" ".join(skill.split()))
    )
    section = skill.split(f"## {procedure} run\n")[1].split("\n## ")[0]
    assert "Post the" in section and "comment URL" in section
    cli = "gh" if platform == "github" else "glab"
    example = next(
        command
        for command in re.findall(r"```bash\n(.*?)\n```", skill, re.DOTALL)
        if command.startswith(cli + " ")
    )
    calls = tmp_path / "calls.jsonl"
    payload = tmp_path / "posted.txt"
    stub = tmp_path / cli
    anchor = (
        "pull/12#issuecomment-17"
        if platform == "github"
        else "-/merge_requests/12#note_17"
    )
    url = f"https://{platform}.com/example/project/{anchor}"
    stub.write_text(
        "#!"
        + sys.executable
        + "\n"
        + r"""
import json, os, pathlib, sys
args = sys.argv[1:]
with open(os.environ["STUB_CALLS"], "a") as out:
    out.write(json.dumps(args) + "\n")
if args[:2] == ["pr", "comment"]:
    body = pathlib.Path(args[args.index("--body-file") + 1]).read_bytes()
else:
    assert args[:3] == ["mr", "note", "create"], args
    assert "--resolvable=false" in args
    body = sys.stdin.buffer.read()
pathlib.Path(os.environ["STUB_PAYLOAD"]).write_bytes(body)
if os.environ["STUB_FAIL"] == "True":
    print("synthetic posting unavailable", file=sys.stderr)
    sys.exit(1)
print(os.environ["STUB_URL"])
"""
    )
    stub.chmod(0o700)
    monkeypatch.setenv("PATH", str(tmp_path) + os.pathsep + os.environ["PATH"])
    monkeypatch.setenv("STUB_CALLS", str(calls))
    monkeypatch.setenv("STUB_PAYLOAD", str(payload))
    monkeypatch.setenv("STUB_FAIL", str(post_fails))
    monkeypatch.setenv("STUB_URL", url)
    before = snapshot(project)
    run = Path(
        subprocess.check_output(
            ["sh", "-c", "mktemp -d"],
            env={**os.environ, "TMPDIR": str(tmp_path)},
            text=True,
        ).strip()
    )
    try:
        # The instruction posts the produced report, with no parsing or gate.
        # Include syntax formerly filtered by the removed publication helper.
        report = (
            b"Complete report\r\nFile: sample.py\r\n"
            b"[local]\r\n[local]:\r\n /tmp/evidence.txt\r\n"
            b'<a href="./evidence.txt">evidence</a>\r\n'
        )
        report_file = "review.md" if procedure == "Review" else "verification.md"
        (run / report_file).write_bytes(report)
        command = (
            example.replace("<reviewed-pr-url>", url.split("#")[0])
            .replace("<reviewed-mr-url>", url.split("#")[0])
            .replace("<run-dir>", str(run))
            .replace("<report-file>", report_file)
        )
        result = subprocess.run(
            ["sh", "-c", command], cwd=project, capture_output=True, text=True
        )
        assert result.returncode == int(post_fails)
        assert result.stdout.strip() == ("" if post_fails else url)
        assert ("synthetic posting unavailable" in result.stderr) == post_fails
        recorded = [json.loads(line) for line in calls.read_text().splitlines()]
        assert len(recorded) == 1
        assert url.split("#")[0] in recorded[0]
        assert payload.read_bytes() == report
    finally:
        subprocess.run(["rm", "-r", "--", str(run)], check=True)
    assert not run.exists() and snapshot(project) == before


def test_procedure_binds_real_checks_and_separate_outcomes() -> None:
    skill = " ".join(text().split())
    for required in (
        "## Verification run",
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
    skill = " ".join(text().split())
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


def test_no_temporary_file_or_posting_helper() -> None:
    skill = text()
    assert not (SKILL / "scripts/artifacts.py").exists()
    assert "## Publish\n" not in skill
    assert "scripts/artifacts.py" not in skill
    assert "--approved-file" not in skill
    assert "There is no posting helper" in skill
