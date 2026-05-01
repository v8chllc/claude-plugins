import importlib.util
import json
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

from typer.testing import CliRunner

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "plugins/vault/skills/git-ops/scripts/post_review_context.py"
)


def load_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("post_review_context", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# ---------------------------------------------------------------------------
# _build_comment_body
# ---------------------------------------------------------------------------


def test_build_comment_body_returns_none_when_neither_given() -> None:
    module = load_module()
    assert module._build_comment_body(None, None) is None
    assert module._build_comment_body("", "") is None
    assert module._build_comment_body("   ", "   ") is None


def test_build_comment_body_spec_only() -> None:
    module = load_module()
    body = module._build_comment_body("My spec text", None)
    assert body is not None
    assert body.startswith("<!-- review-context")
    assert "<summary>Spec</summary>" in body
    assert "My spec text" in body
    assert "<summary>Plan</summary>" not in body


def test_build_comment_body_plan_only() -> None:
    module = load_module()
    body = module._build_comment_body(None, "My plan text")
    assert body is not None
    assert body.startswith("<!-- review-context")
    assert "<summary>Plan</summary>" in body
    assert "My plan text" in body
    assert "<summary>Spec</summary>" not in body


def test_build_comment_body_both() -> None:
    module = load_module()
    body = module._build_comment_body("Spec content", "Plan content")
    assert body is not None
    assert "<summary>Spec</summary>" in body
    assert "Spec content" in body
    assert "<summary>Plan</summary>" in body
    assert "Plan content" in body


def test_build_comment_body_marker_is_valid_json() -> None:
    module = load_module()
    body = module._build_comment_body("spec", "plan")
    assert body is not None
    import re

    match = re.search(r"<!--\s*review-context\s*(\{.*?\})\s*-->", body, re.DOTALL)
    assert match is not None
    metadata = json.loads(match.group(1))
    assert metadata["schema_version"] == 1
    assert metadata["type"] == "planning_context"
    assert metadata["has_spec"] is True
    assert metadata["has_plan"] is True


def test_build_comment_body_marker_reflects_presence_flags() -> None:
    module = load_module()
    import re

    spec_only = module._build_comment_body("spec", None)
    assert spec_only is not None
    match = re.search(r"<!--\s*review-context\s*(\{.*?\})\s*-->", spec_only, re.DOTALL)
    assert match is not None
    meta = json.loads(match.group(1))
    assert meta["has_spec"] is True
    assert meta["has_plan"] is False


def test_build_comment_body_truncates_large_content() -> None:
    module = load_module()
    large_spec = "x" * (module._MAX_BODY_CHARS + 5_000)
    body = module._build_comment_body(large_spec, None)
    assert body is not None
    assert body.endswith(module._TRUNCATION_NOTICE)
    body_before = body[: -len(module._TRUNCATION_NOTICE)]
    assert body_before.count("<details>") == body_before.count("</details>")


# ---------------------------------------------------------------------------
# _read_platform
# ---------------------------------------------------------------------------


def test_read_platform_defaults_to_github(tmp_path: Path) -> None:
    module = load_module()
    assert module._read_platform(None, tmp_path) == "github"


def test_read_platform_override_wins(tmp_path: Path) -> None:
    module = load_module()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n")
    assert module._read_platform("github", tmp_path) == "github"


def test_read_platform_from_env(tmp_path: Path) -> None:
    module = load_module()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n")
    assert module._read_platform(None, tmp_path) == "gitlab"


# ---------------------------------------------------------------------------
# CLI — no-op when no files given
# ---------------------------------------------------------------------------


def test_cli_exits_cleanly_when_no_files(tmp_path: Path) -> None:
    module = load_module()
    runner = CliRunner()
    with (
        patch.object(module, "_post_github") as mock_gh,
        patch.object(module, "_post_gitlab") as mock_gl,
    ):
        result = runner.invoke(module.app, ["42", "--repo-dir", str(tmp_path)])
    assert result.exit_code == 0
    mock_gh.assert_not_called()
    mock_gl.assert_not_called()


# ---------------------------------------------------------------------------
# CLI — GitHub happy path
# ---------------------------------------------------------------------------


def test_cli_posts_github_with_spec_and_plan(tmp_path: Path) -> None:
    module = load_module()
    spec = tmp_path / "spec.md"
    spec.write_text("Build X")
    plan = tmp_path / "plan.md"
    plan.write_text("1. Do Y")
    runner = CliRunner()

    captured: dict[str, object] = {}

    def fake_post(pr_number: int, body: str, repo_dir: Path) -> None:
        captured["pr_number"] = pr_number
        captured["body"] = body

    with patch.object(module, "_post_github", side_effect=fake_post):
        result = runner.invoke(
            module.app,
            [
                "99",
                "--platform",
                "github",
                "--spec-file",
                str(spec),
                "--plan-file",
                str(plan),
                "--repo-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0
    assert captured["pr_number"] == 99
    body = captured["body"]
    assert isinstance(body, str)
    assert body.startswith("<!-- review-context")
    assert "Build X" in body
    assert "1. Do Y" in body
    assert "<summary>Spec</summary>" in body
    assert "<summary>Plan</summary>" in body


# ---------------------------------------------------------------------------
# CLI — GitLab happy path
# ---------------------------------------------------------------------------


def test_cli_posts_gitlab_with_spec_only(tmp_path: Path) -> None:
    module = load_module()
    spec = tmp_path / "spec.md"
    spec.write_text("Do Z")
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n")
    runner = CliRunner()

    captured: dict[str, object] = {}

    def fake_post(mr_number: int, body: str, repo_dir: Path) -> None:
        captured["mr_number"] = mr_number
        captured["body"] = body

    with patch.object(module, "_post_gitlab", side_effect=fake_post):
        result = runner.invoke(
            module.app,
            [
                "7",
                "--spec-file",
                str(spec),
                "--repo-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0
    assert captured["mr_number"] == 7
    body = captured["body"]
    assert isinstance(body, str)
    assert "Do Z" in body
    assert "<summary>Spec</summary>" in body
    assert "<summary>Plan</summary>" not in body


# ---------------------------------------------------------------------------
# CLI — empty files produce no-op
# ---------------------------------------------------------------------------


def test_cli_skips_post_when_files_are_empty(tmp_path: Path) -> None:
    module = load_module()
    spec = tmp_path / "spec.md"
    spec.write_text("   ")
    plan = tmp_path / "plan.md"
    plan.write_text("")
    runner = CliRunner()

    with (
        patch.object(module, "_post_github") as mock_gh,
        patch.object(module, "_post_gitlab") as mock_gl,
    ):
        result = runner.invoke(
            module.app,
            [
                "10",
                "--platform",
                "github",
                "--spec-file",
                str(spec),
                "--plan-file",
                str(plan),
                "--repo-dir",
                str(tmp_path),
            ],
        )

    assert result.exit_code == 0
    mock_gh.assert_not_called()
    mock_gl.assert_not_called()


# ---------------------------------------------------------------------------
# _post_github — subprocess integration (mocked)
# ---------------------------------------------------------------------------


def test_post_github_creates_when_no_existing_comment(tmp_path: Path) -> None:
    module = load_module()
    body = "<!-- review-context\n{}\n-->\n## Planning Context\n"
    list_response = MagicMock(returncode=0, stdout=json.dumps([]), stderr="")
    create_response = MagicMock(returncode=0, stdout="", stderr="")

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
        calls.append(cmd)
        if "pr" in cmd and "comment" in cmd:
            return create_response
        return list_response

    with patch.object(module, "GH", "/usr/bin/gh"):
        with patch("subprocess.run", side_effect=fake_run):
            module._post_github(42, body, tmp_path)

    assert any("comment" in c for c in calls)
    assert not any("PATCH" in c for c in calls)


def test_post_github_updates_existing_comment(tmp_path: Path) -> None:
    module = load_module()
    body = "<!-- review-context\n{}\n-->\n## Planning Context\n"
    existing = [{"id": 999, "body": "<!-- review-context\nold content"}]
    list_response = MagicMock(returncode=0, stdout=json.dumps(existing), stderr="")
    patch_response = MagicMock(returncode=0, stdout="", stderr="")

    calls: list[list[str]] = []

    def fake_run(cmd: list[str], **_kwargs: object) -> MagicMock:
        calls.append(cmd)
        if "PATCH" in cmd:
            return patch_response
        return list_response

    with patch.object(module, "GH", "/usr/bin/gh"):
        with patch("subprocess.run", side_effect=fake_run):
            module._post_github(42, body, tmp_path)

    assert any("PATCH" in c for c in calls)
    assert any("comments/999" in part for c in calls for part in c)
    assert not any("pr" in c and "comment" in c for c in calls)
