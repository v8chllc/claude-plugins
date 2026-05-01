import importlib.util
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "plugins/v8ch/skills/consensus-review/scripts/post_review_comment.py"
)


def load_post_review_comment() -> ModuleType:
    spec = importlib.util.spec_from_file_location("post_review_comment", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_read_platform_default_when_env_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    monkeypatch.chdir(tmp_path)
    assert module.read_platform_from_env() == "github"


def test_read_platform_github(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_post_review_comment()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=github\n")
    monkeypatch.chdir(tmp_path)
    assert module.read_platform_from_env() == "github"


def test_read_platform_gitlab(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_post_review_comment()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n")
    monkeypatch.chdir(tmp_path)
    assert module.read_platform_from_env() == "gitlab"


def test_read_platform_handles_quoted_values(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    (tmp_path / ".env").write_text('DEV_SEC_OPS_PLATFORM="gitlab"\n')
    monkeypatch.chdir(tmp_path)
    assert module.read_platform_from_env() == "gitlab"


def test_read_platform_case_insensitive(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=GitLab\n")
    monkeypatch.chdir(tmp_path)
    assert module.read_platform_from_env() == "gitlab"


def test_read_platform_uses_repo_dir(tmp_path: Path) -> None:
    module = load_post_review_comment()
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n")
    assert module.read_platform_from_env(repo_dir) == "gitlab"


def test_get_status_explicit_wins() -> None:
    module = load_post_review_comment()
    assert module.get_status("clean", False) == "clean"
    assert module.get_status("failing", True) == "failing"
    assert module.get_status("passing", True) == "passing"


def test_get_status_is_clean_fallback() -> None:
    module = load_post_review_comment()
    assert module.get_status(None, True) == "clean"
    assert module.get_status(None, False) == "failing"


def test_build_summary_lines_filters_blank(tmp_path: Path) -> None:
    module = load_post_review_comment()
    summary = tmp_path / "summary.md"
    summary.write_text("- First\n\n- Second\n\n  \n- Third\n")
    lines = module.build_summary_lines(str(summary))
    assert lines == ["- First", "- Second", "- Third"]


def test_infer_comment_type_from_filename(tmp_path: Path) -> None:
    module = load_post_review_comment()
    review = tmp_path / "review-03.md"
    review.write_text("x")
    fix_log = tmp_path / "fix-03.md"
    fix_log.write_text("x")
    assert module.infer_comment_type(None, str(review)) == "review"
    assert module.infer_comment_type(None, str(fix_log)) == "fix_validation"


def test_build_review_comment_body_uses_review_template(tmp_path: Path) -> None:
    module = load_post_review_comment()
    summary = tmp_path / "summary.md"
    summary.write_text("- All good\n")

    body = module.build_review_comment_body(
        "## Consensus Review Report\n\n### Quality Score: 92/100\n\n## Review body",
        comment_type="review",
        status="clean",
        summary_file=str(summary),
        cycle=3,
    )

    assert body.startswith("<!-- consensus-review")
    assert '"type":"review"' in body
    assert '"cycle":3' in body
    assert '"score":92' in body
    assert "### ✅ Review" in body
    assert "*Cycle: 03*" in body
    assert "*Score: 92*" in body
    assert "### Summary" in body
    assert "- All good" in body
    assert "<summary>Full consensus review</summary>" in body
    assert "## Review body" in body
    assert "${" not in body


def test_build_review_comment_body_requires_or_derives_score(tmp_path: Path) -> None:
    module = load_post_review_comment()
    summary = tmp_path / "summary.md"
    summary.write_text("- All good\n")

    with pytest.raises(Exception, match="Review comments require a raw score"):
        module.build_review_comment_body(
            "## Review body",
            comment_type="review",
            status="clean",
            summary_file=str(summary),
            cycle=3,
        )


def test_build_fix_validation_comment_body_uses_fix_template(tmp_path: Path) -> None:
    module = load_post_review_comment()
    summary = tmp_path / "fix-summary.md"
    summary.write_text("- Fix Validation — Cycle 03: 1 of 2 findings unresolved.\n")

    body = module.build_review_comment_body(
        "## Status Table",
        comment_type="fix_validation",
        status="failing",
        summary_file=str(summary),
        cycle=3,
    )

    assert "### Review Findings Fixed" in body
    assert "*Cycle: 03*" in body
    assert "Adjusted Score" not in body
    assert "<summary>Full fix log</summary>" in body
    assert "## Status Table" in body
    assert "${" not in body


def test_build_acceptance_comment_body_uses_acceptance_template(tmp_path: Path) -> None:
    module = load_post_review_comment()
    findings = tmp_path / "findings.md"
    findings.write_text("1. [MEDIUM] Keep defensive guard — `foo.py`\n")
    body = module.build_findings_comment_body(
        comment_type="acceptance",
        cycle=2,
        findings_file=str(findings),
        before_score=88,
        after_score=93,
    )

    assert body.startswith("<!-- consensus-review")
    assert '"type":"acceptance"' in body
    assert '"before_score":88' in body
    assert '"after_score":93' in body
    assert "### Review Findings Accepted: Agent Reviewer" in body
    assert "*Cycle: 02*" in body
    assert "*Initial Score: 88*" in body
    assert "*Adjusted Score: 93*" in body
    assert "### Accepted Findings" in body
    assert "1. [MEDIUM] Keep defensive guard — `foo.py`" in body
    assert "- Raw score: 88/100" in body
    assert "- Adjusted score: 93/100" in body
    assert "${" not in body


def test_build_additional_acceptance_comment_body_uses_template(tmp_path: Path) -> None:
    module = load_post_review_comment()
    findings = tmp_path / "findings.md"
    findings.write_text("1. [LOW] Leave telemetry hook — `bar.py`\n")
    body = module.build_findings_comment_body(
        comment_type="additional_acceptance",
        cycle=4,
        findings_file=str(findings),
        before_score=90,
        after_score=94,
    )

    assert "### Review Findings Accepted: Human Reviewer" in body
    assert "*Cycle: 04*" in body
    assert "*Initial Score: 90*" in body
    assert "*Adjusted Score: 94*" in body
    assert "### Accepted Findings" in body
    assert "- Score before additional acceptance: 90/100" in body
    assert "- Score after additional acceptance: 94/100" in body
    assert "${" not in body


def test_build_low_confidence_opt_in_comment_body_uses_template(tmp_path: Path) -> None:
    module = load_post_review_comment()
    findings = tmp_path / "opted-in.md"
    findings.write_text(
        "1. Missing retry fallback — `worker.py` "
        "(low-confidence reviewer: correctness-reviewer)\n"
    )

    body = module.build_findings_comment_body(
        comment_type="low_confidence_opt_in",
        cycle=6,
        findings_file=str(findings),
        before_score=None,
        after_score=None,
    )

    assert "### Informational Review Findings Added" in body
    assert "*Cycle: 06*" in body
    assert "Adjusted Score" not in body
    assert "### Added Findings" in body
    assert "Missing retry fallback" in body
    assert (
        "These low-confidence findings were explicitly opted in for fixing this "
        "cycle." in body
    )
    assert "${" not in body


def test_main_fails_on_empty_review_file(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    review = tmp_path / "review.md"
    review.write_text("")
    summary = tmp_path / "summary.md"
    summary.write_text("- line\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "1",
            "--comment-type",
            "review",
            "--review-file",
            str(review),
            "--summary-file",
            str(summary),
        ],
    )
    assert result.exit_code == 1
    assert "Review file is empty" in result.output


def test_main_posts_github_review_happy_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    review = tmp_path / "review.md"
    review.write_text(
        "## Consensus Review Report\n\n### Quality Score: 91/100\n\n## Review body\n"
    )
    summary = tmp_path / "summary.md"
    summary.write_text("- Good\n")
    monkeypatch.chdir(tmp_path)

    captured: dict[str, object] = {}

    def fake_github(pr_number: int, body: str, repo_dir: str = ".") -> None:
        captured["pr_number"] = pr_number
        captured["body"] = body
        captured["repo_dir"] = repo_dir

    monkeypatch.setattr(module, "post_comment_github", fake_github)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "42",
            "--comment-type",
            "review",
            "--review-file",
            str(review),
            "--summary-file",
            str(summary),
            "--cycle",
            "3",
            "--status",
            "clean",
        ],
    )
    assert result.exit_code == 0
    assert captured["pr_number"] == 42
    body = captured["body"]
    assert isinstance(body, str)
    assert body.startswith("<!-- consensus-review")
    assert '"status":"clean"' in body
    assert "### ✅ Review" in body
    assert "*Cycle: 03*" in body
    assert "*Score: 91*" in body
    assert "## Review body" in body
    assert "${" not in body


def test_main_posts_gitlab_acceptance_when_repo_dir_env_is_set(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    findings = tmp_path / "findings.md"
    findings.write_text("1. [HIGH] Keep migration split — `migrate.py`\n")
    repo_dir = tmp_path / "repo"
    repo_dir.mkdir()
    (repo_dir / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n")
    monkeypatch.chdir(tmp_path)

    captured: dict[str, object] = {}

    def fake_gitlab(pr_number: int, body: str, repo_dir: str = ".") -> None:
        captured["pr_number"] = pr_number
        captured["body"] = body
        captured["repo_dir"] = repo_dir

    monkeypatch.setattr(module, "post_comment_gitlab", fake_gitlab)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "7",
            "--comment-type",
            "acceptance",
            "--findings-file",
            str(findings),
            "--repo-dir",
            str(repo_dir),
            "--cycle",
            "5",
            "--before-score",
            "84",
            "--after-score",
            "89",
        ],
    )
    assert result.exit_code == 0
    assert captured["pr_number"] == 7
    body = captured["body"]
    assert isinstance(body, str)
    assert "### Review Findings Accepted: Agent Reviewer" in body
    assert "*Cycle: 05*" in body
    assert "*Initial Score: 84*" in body
    assert "*Adjusted Score: 89*" in body
    assert "- Raw score: 84/100" in body
    assert captured["repo_dir"] == str(repo_dir)


def test_main_posts_github_low_confidence_opt_in(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    findings = tmp_path / "opted-in.md"
    findings.write_text(
        "1. Missing retry fallback — `worker.py` "
        "(low-confidence reviewer: correctness-reviewer)\n"
    )
    monkeypatch.chdir(tmp_path)

    captured: dict[str, object] = {}

    def fake_github(pr_number: int, body: str, repo_dir: str = ".") -> None:
        captured["pr_number"] = pr_number
        captured["body"] = body
        captured["repo_dir"] = repo_dir

    monkeypatch.setattr(module, "post_comment_github", fake_github)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "11",
            "--comment-type",
            "low_confidence_opt_in",
            "--findings-file",
            str(findings),
            "--cycle",
            "6",
        ],
    )
    assert result.exit_code == 0
    assert captured["pr_number"] == 11
    body = captured["body"]
    assert isinstance(body, str)
    assert "### Informational Review Findings Added" in body
    assert "*Cycle: 06*" in body
    assert "Adjusted Score" not in body
    assert "${" not in body


def test_extract_quality_score() -> None:
    module = load_post_review_comment()
    review = (
        "## Consensus Review Report\n\n"
        "### Quality Score: 87/100\n"
        "### Score if recommended acceptances applied: 92/100\n"
    )
    assert module.extract_quality_score(review) == 87


def test_main_requires_findings_file_for_acceptance(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "8",
            "--comment-type",
            "acceptance",
            "--before-score",
            "80",
            "--after-score",
            "90",
        ],
    )
    assert result.exit_code == 1
    assert "Findings-list comments require --findings-file" in result.output


def test_build_recommendations_comment_body_uses_template(tmp_path: Path) -> None:
    module = load_post_review_comment()
    acceptance = tmp_path / "acceptance-recs.md"
    acceptance.write_text(
        "1. [F-3] [HIGH] Dead variable in _run_json "
        "— `scripts/recover_context.py:228`\n"
    )
    opt_in = tmp_path / "opt-in-recs.md"
    opt_in.write_text("1. [F-7] [LOW] Stale comment reference — `src/util.py`\n")

    body = module.build_recommendations_comment_body(
        cycle=2,
        acceptance_findings_file=str(acceptance),
        opt_in_findings_file=str(opt_in),
    )

    assert body.startswith("<!-- consensus-review")
    assert '"type":"recommendations"' in body
    assert '"cycle":2' in body
    assert '"schema_version":1' in body
    assert "### Review Recommendations" in body
    assert "*Cycle: 02*" in body
    assert "### Recommended for Acceptance" in body
    assert "### Recommended for Opt-In" in body
    assert (
        "1. [F-3] [HIGH] Dead variable in _run_json — `scripts/recover_context.py:228`"
        in body
    )
    assert "1. [F-7] [LOW] Stale comment reference — `src/util.py`" in body
    assert "${" not in body


def test_main_posts_github_recommendations(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    acceptance = tmp_path / "acceptance-recs.md"
    acceptance.write_text("1. [F-1] [MEDIUM] Defensive null check — `src/foo.py`\n")
    opt_in = tmp_path / "opt-in-recs.md"
    opt_in.write_text("None.\n")
    monkeypatch.chdir(tmp_path)

    captured: dict[str, object] = {}

    def fake_github(pr_number: int, body: str, repo_dir: str = ".") -> None:
        captured["pr_number"] = pr_number
        captured["body"] = body
        captured["repo_dir"] = repo_dir

    monkeypatch.setattr(module, "post_comment_github", fake_github)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "55",
            "--comment-type",
            "recommendations",
            "--cycle",
            "4",
            "--acceptance-findings-file",
            str(acceptance),
            "--opt-in-findings-file",
            str(opt_in),
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["pr_number"] == 55
    body = captured["body"]
    assert isinstance(body, str)
    assert '"type":"recommendations"' in body
    assert '"cycle":4' in body
    assert "### Review Recommendations" in body
    assert "*Cycle: 04*" in body
    assert "### Recommended for Acceptance" in body
    assert "### Recommended for Opt-In" in body
    assert "Defensive null check" in body
    assert "None." in body
    assert "${" not in body


def test_main_recommendations_requires_both_files(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    acceptance = tmp_path / "acceptance-recs.md"
    acceptance.write_text("1. [F-1] [HIGH] X — `f.py`\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "1",
            "--comment-type",
            "recommendations",
            "--cycle",
            "1",
            "--acceptance-findings-file",
            str(acceptance),
        ],
    )

    assert result.exit_code == 1
    assert (
        "Recommendations comments require --acceptance-findings-file"
        " and --opt-in-findings-file"
    ) in result.output


def test_recommendations_template_filename_registered() -> None:
    module = load_post_review_comment()
    assert (
        module.TEMPLATE_FILENAMES["recommendations"]
        == "recommendations-comment.md.tmpl"
    )
    # All five existing types are still registered for backward compatibility.
    for legacy_type in (
        "review",
        "fix_validation",
        "acceptance",
        "additional_acceptance",
        "low_confidence_opt_in",
    ):
        assert legacy_type in module.TEMPLATE_FILENAMES


def test_main_recommendations_requires_cycle(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_post_review_comment()
    acceptance = tmp_path / "acceptance-recs.md"
    acceptance.write_text("1. [F-1] [HIGH] X — `f.py`\n")
    opt_in = tmp_path / "opt-in-recs.md"
    opt_in.write_text("None.\n")
    monkeypatch.chdir(tmp_path)

    runner = CliRunner()
    result = runner.invoke(
        module.app,
        [
            "--pr-number",
            "1",
            "--comment-type",
            "recommendations",
            "--acceptance-findings-file",
            str(acceptance),
            "--opt-in-findings-file",
            str(opt_in),
            # intentionally omit --cycle
        ],
    )

    assert result.exit_code == 1
    assert "Recommendations comments require --cycle" in result.output
