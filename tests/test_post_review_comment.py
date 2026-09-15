import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "plugins/v8ch/skills/consensus-review/scripts"
SCRIPT_PATH = SCRIPTS_DIR / "post_review_comment.py"
FIXTURES_DIR = REPO_ROOT / "tests/fixtures/consensus-review"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

REPORT = """### Quality Score: 91/100 — Passing

### Run Provenance

Delegation: parallel-subagents. Plan: none.

### Evidence

- **Files examined:** src/render.py
- **Commands run:** uv run ruff check .

### Must Fix

#### [F-1] [HIGH] Empty row list renders a header with no body

**Location:** src/render.py:48
"""

SUMMARY = "- Review passed with a score of 91/100. A fix cycle follows.\n"

REQUIRED_ARGS = [
    "--delegation-mode",
    "parallel-subagents",
    "--plan-source",
    "none",
    "--reviewed-sha",
    "1a2b3c4",
    "--scope-basis",
    "full-diff",
    "--files-touched",
    "3",
    "--findings-opened",
    "2",
    "--findings-closed",
    "1",
]


def load_post_review_comment() -> ModuleType:
    spec = importlib.util.spec_from_file_location("post_review_comment", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: a dataclass with stringized annotations resolves
    # them through sys.modules, which importlib.util does not populate for us.
    sys.modules["post_review_comment"] = module
    spec.loader.exec_module(module)
    return module


def write_inputs(tmp_path: Path, *, report: str = REPORT, summary: str = SUMMARY):
    review_file = tmp_path / "review-02.md"
    review_file.write_text(report, encoding="utf-8")
    summary_file = tmp_path / "summary-02.md"
    summary_file.write_text(summary, encoding="utf-8")
    return review_file, summary_file


def base_args(review_file: Path, summary_file: Path, **overrides: str) -> list[str]:
    args = [
        "--pr-number",
        "7",
        "--review-file",
        str(review_file),
        "--summary-file",
        str(summary_file),
        "--cycle",
        "2",
        "--status",
        "passing",
        *REQUIRED_ARGS,
    ]
    for flag, value in overrides.items():
        option = f"--{flag.replace('_', '-')}"
        index = args.index(option)
        args[index + 1] = value
    return args


def capture_posts(module: ModuleType, monkeypatch: pytest.MonkeyPatch) -> list[dict]:
    posted: list[dict[str, Any]] = []

    def record(platform: str):
        def fake(pr_number: int, body: str, repo_dir: str = ".") -> None:
            posted.append(
                {
                    "platform": platform,
                    "pr_number": pr_number,
                    "body": body,
                    "repo_dir": repo_dir,
                }
            )

        return fake

    monkeypatch.setattr(module, "post_comment_github", record("github"))
    monkeypatch.setattr(module, "post_comment_gitlab", record("gitlab"))
    return posted


def test_read_platform_defaults_to_github_without_an_env_file(tmp_path: Path) -> None:
    module = load_post_review_comment()
    assert module.read_platform_from_env(tmp_path) == "github"


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("DEV_SEC_OPS_PLATFORM=github\n", "github"),
        ("DEV_SEC_OPS_PLATFORM=gitlab\n", "gitlab"),
        ('DEV_SEC_OPS_PLATFORM="gitlab"\n', "gitlab"),
        ("DEV_SEC_OPS_PLATFORM=GitLab\n", "gitlab"),
        ("OTHER=1\n", "github"),
    ],
)
def test_read_platform_from_env(tmp_path: Path, raw: str, expected: str) -> None:
    module = load_post_review_comment()
    (tmp_path / ".env").write_text(raw, encoding="utf-8")
    assert module.read_platform_from_env(tmp_path) == expected


def test_explicit_platform_overrides_the_env_file(tmp_path: Path) -> None:
    module = load_post_review_comment()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n", encoding="utf-8")
    assert module.resolve_platform("github", tmp_path) == "github"
    assert module.resolve_platform(None, tmp_path) == "gitlab"


def test_summary_accepts_one_to_three_bullets() -> None:
    module = load_post_review_comment()
    assert module.validate_summary("- one\n") == "- one"
    assert module.validate_summary("- one\n\n- two\n- three\n").count("\n") == 2


@pytest.mark.parametrize(
    "summary",
    [
        "",
        "no bullet here",
        "- one\n- two\n- three\n- four\n",
        "- one\nnot a bullet\n",
    ],
)
def test_summary_rejects_the_wrong_shape(summary: str) -> None:
    module = load_post_review_comment()
    with pytest.raises(module.ContractError):
        module.validate_summary(summary)


def test_report_must_carry_merged_evidence() -> None:
    module = load_post_review_comment()
    with pytest.raises(module.ContractError, match="Evidence"):
        module.validate_report("### Quality Score: 91/100 — Passing\n")


def test_report_must_not_nest_a_details_block() -> None:
    module = load_post_review_comment()
    report = REPORT + "\n<details><summary>extra</summary>hidden</details>\n"
    with pytest.raises(module.ContractError, match="details"):
        module.validate_report(report)


def test_score_comes_only_from_the_report_heading() -> None:
    """No override exists: published metadata cannot contradict the report."""
    module = load_post_review_comment()
    assert module.resolve_score(REPORT) == 91
    with pytest.raises(module.ContractError):
        module.resolve_score("### Evidence\n")
    assert "--score" not in module.build_parser().format_help()


def test_comment_body_opens_with_exact_v2_metadata(tmp_path: Path) -> None:
    module = load_post_review_comment()
    body = module.build_comment_body(
        report_text=REPORT,
        summary_text=SUMMARY,
        cycle=2,
        status="passing",
        score=91,
        delegation_mode="parallel-subagents",
        plan_source="none",
        reviewed_sha="1a2b3c4",
        scope_basis="full-diff",
        files_touched=3,
        findings_opened=2,
        findings_closed=1,
    )
    marker, encoded, _ = body.split("\n", 2)
    assert marker == "<!-- consensus-review"
    metadata = json.loads(encoded)
    assert metadata == {
        "cycle": 2,
        "delegation_mode": "parallel-subagents",
        "files_touched": 3,
        "findings_closed": 1,
        "findings_opened": 2,
        "plan_source": "none",
        "reviewed_sha": "1a2b3c4",
        "schema_version": 2,
        "scope_basis": "full-diff",
        "score": 91,
        "status": "passing",
        "type": "review",
    }
    assert encoded == json.dumps(metadata, sort_keys=True, separators=(",", ":"))


def test_comment_body_renders_the_template_without_placeholders() -> None:
    module = load_post_review_comment()
    body = module.build_comment_body(
        report_text=REPORT,
        summary_text=SUMMARY,
        cycle=2,
        status="passing",
        score=91,
        delegation_mode="parallel-subagents",
        plan_source="supplied: .plan/feature.md",
        reviewed_sha="1a2b3c4",
        scope_basis="delta-since:9f3a25e",
        files_touched=3,
        findings_opened=2,
        findings_closed=1,
    )
    assert "### \U0001f7e1 Consensus Review — Cycle 02" in body
    assert "*Score: 91/100 (Passing).*" in body
    assert (
        "Delegation: parallel-subagents. Plan: supplied: .plan/feature.md. "
        "Scope: delta-since:9f3a25e. Reviewed: 1a2b3c4." in body
    )
    assert "<summary>Evidence and full findings</summary>" in body
    assert "[F-1] [HIGH]" in body
    assert "${" not in body
    assert body.count("<details>") == 1


@pytest.mark.parametrize(
    ("status", "icon"),
    [("clean", "✅"), ("passing", "\U0001f7e1"), ("failing", "❌")],
)
def test_status_icons(status: str, icon: str) -> None:
    module = load_post_review_comment()
    body = module.build_comment_body(
        report_text=REPORT,
        summary_text=SUMMARY,
        cycle=1,
        status=status,
        score=91,
        delegation_mode="parallel-subagents",
        plan_source="none",
        reviewed_sha="1a2b3c4",
        scope_basis="full-diff",
        files_touched=1,
        findings_opened=0,
        findings_closed=0,
    )
    assert f"### {icon} Consensus Review" in body


def test_main_posts_to_github_by_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path)
    posted = capture_posts(module, monkeypatch)

    exit_code = module.main(
        base_args(review_file, summary_file) + ["--repo-dir", str(tmp_path)]
    )

    assert exit_code == 0
    assert len(posted) == 1
    assert posted[0]["platform"] == "github"
    assert posted[0]["pr_number"] == 7
    assert '"schema_version":2' in posted[0]["body"]


def test_main_posts_to_gitlab_when_the_env_file_selects_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path)
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n", encoding="utf-8")
    posted = capture_posts(module, monkeypatch)

    exit_code = module.main(
        base_args(review_file, summary_file) + ["--repo-dir", str(tmp_path)]
    )

    assert exit_code == 0
    assert posted[0]["platform"] == "gitlab"


def test_main_platform_flag_beats_the_env_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path)
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n", encoding="utf-8")
    posted = capture_posts(module, monkeypatch)

    exit_code = module.main(
        base_args(review_file, summary_file)
        + ["--repo-dir", str(tmp_path), "--platform", "github"]
    )

    assert exit_code == 0
    assert posted[0]["platform"] == "github"


@pytest.mark.parametrize(
    "overrides",
    [
        {"reviewed_sha": "ABC1234"},
        {"reviewed_sha": "abc12"},
        {"scope_basis": "since:abc1234"},
        {"plan_source": ".plan/feature.md"},
        {"files_touched": "-1"},
    ],
    ids=[
        "uppercase-sha",
        "short-sha",
        "bad-scope",
        "bad-plan-source",
        "negative-count",
    ],
)
def test_main_rejects_invalid_metadata_without_posting(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    overrides: dict[str, str],
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path)
    posted = capture_posts(module, monkeypatch)

    exit_code = module.main(
        base_args(review_file, summary_file, **overrides)
        + ["--repo-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert posted == []
    assert "Error:" in capsys.readouterr().err


def test_main_rejects_an_empty_review_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path, report="   \n")
    posted = capture_posts(module, monkeypatch)

    exit_code = module.main(
        base_args(review_file, summary_file) + ["--repo-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert posted == []
    assert "empty" in capsys.readouterr().err


def test_main_reports_a_missing_platform_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path)
    monkeypatch.setattr(module, "GH", None)

    exit_code = module.main(
        base_args(review_file, summary_file) + ["--repo-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert "gh executable not found" in capsys.readouterr().err


def test_main_reports_a_failed_post(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_post_review_comment()
    review_file, summary_file = write_inputs(tmp_path)

    def fail(pr_number: int, body: str, repo_dir: str = ".") -> None:
        raise subprocess.CalledProcessError(1, ["gh"])

    monkeypatch.setattr(module, "post_comment_github", fail)

    exit_code = module.main(
        base_args(review_file, summary_file) + ["--repo-dir", str(tmp_path)]
    )

    assert exit_code == 1
    assert "failed to post comment" in capsys.readouterr().err


def test_github_and_gitlab_transports_shell_out_to_their_clients(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_post_review_comment()
    calls: list[list[str]] = []

    def fake_run(command: list[str], **kwargs: Any) -> None:
        calls.append(command)

    monkeypatch.setattr(module.subprocess, "run", fake_run)
    monkeypatch.setattr(module, "GH", "/usr/bin/gh")
    monkeypatch.setattr(module, "GLAB", "/usr/bin/glab")

    module.post_comment_github(7, "body", repo_dir=".")
    module.post_comment_gitlab(4, "body", repo_dir=".")

    assert calls[0] == ["/usr/bin/gh", "pr", "comment", "7", "--body", "body"]
    assert calls[1] == ["/usr/bin/glab", "mr", "note", "4", "--message", "body"]


def test_only_the_review_template_ships() -> None:
    templates = sorted(
        path.name
        for path in (SCRIPT_PATH.parent.parent / "templates").glob("*.md.tmpl")
    )
    assert templates == ["review-comment.md.tmpl"]


def test_the_script_still_renders_the_frozen_wire_format() -> None:
    """The rendered comment is the wire format both toolchains read.

    ``review-comment-v2.md`` is the frozen output for the fixture report and
    summary. A change here is a change to what the sibling toolchain must parse,
    so it fails until both repositories move together.
    """
    module = load_post_review_comment()
    expected = (FIXTURES_DIR / "review-comment-v2.md").read_text(encoding="utf-8")
    rendered = module.build_comment_body(
        report_text=(FIXTURES_DIR / "review-report.md")
        .read_text(encoding="utf-8")
        .strip(),
        summary_text=(FIXTURES_DIR / "review-summary.md").read_text(encoding="utf-8"),
        cycle=2,
        status="passing",
        score=91,
        delegation_mode="parallel-subagents",
        plan_source="none",
        reviewed_sha="1a2b3c4",
        scope_basis="full-diff",
        files_touched=3,
        findings_opened=2,
        findings_closed=1,
    )
    assert rendered == expected
