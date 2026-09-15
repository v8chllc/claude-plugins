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
SCRIPT_PATH = SCRIPTS_DIR / "recover_context.py"
POST_SCRIPT_PATH = SCRIPTS_DIR / "post_review_comment.py"
FIXTURES_DIR = REPO_ROOT / "tests/fixtures/consensus-review"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))


def load_module(name: str, path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    # Register before exec: a dataclass with stringized annotations resolves
    # them through sys.modules, which importlib.util does not populate for us.
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def load_recover_context() -> ModuleType:
    return load_module("recover_context", SCRIPT_PATH)


def load_post_review_comment() -> ModuleType:
    return load_module("post_review_comment_for_recover", POST_SCRIPT_PATH)


def fixture_comments(name: str) -> list[dict[str, Any]]:
    payload = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    comments: list[dict[str, Any]] = payload["comments"]
    return comments


def github_comment(body: str, *, created_at: str = "2026-09-10T12:00:00Z") -> dict:
    return {
        "id": 1,
        "body": body,
        "created_at": created_at,
        "html_url": "https://github.com/v8chllc/example/pull/7#issuecomment-1",
        "user": {"login": "review-bot"},
    }


def rendered_comment(**overrides: Any) -> str:
    """Render a v2 comment with the sibling script, as a real thread would hold."""
    module = load_post_review_comment()
    kwargs: dict[str, Any] = {
        "report_text": (FIXTURES_DIR / "review-report.md")
        .read_text(encoding="utf-8")
        .strip(),
        "summary_text": (FIXTURES_DIR / "review-summary.md").read_text(
            encoding="utf-8"
        ),
        "cycle": 1,
        "status": "passing",
        "score": 91,
        "delegation_mode": "parallel-subagents",
        "plan_source": "none",
        "reviewed_sha": "1a2b3c4",
        "scope_basis": "full-diff",
        "files_touched": 3,
        "findings_opened": 2,
        "findings_closed": 1,
    }
    kwargs.update(overrides)
    return str(module.build_comment_body(**kwargs))


def stub_ancestry(
    module: ModuleType, monkeypatch: pytest.MonkeyPatch, result: bool | None
) -> None:
    monkeypatch.setattr(
        module, "sha_is_ancestor", lambda sha, head, repo_dir=".": result
    )


def test_read_platform_defaults_to_github_without_an_env_file(tmp_path: Path) -> None:
    module = load_recover_context()
    assert module.read_platform_from_env(tmp_path) == "github"


def test_platform_override_beats_the_env_file(tmp_path: Path) -> None:
    module = load_recover_context()
    (tmp_path / ".env").write_text("DEV_SEC_OPS_PLATFORM=gitlab\n", encoding="utf-8")
    assert module.resolve_platform(None, tmp_path) == "gitlab"
    assert module.resolve_platform("github", tmp_path) == "github"


def test_normalize_handles_both_platform_shapes() -> None:
    module = load_recover_context()
    github = module.normalize_comment(
        {
            "body": "b",
            "created_at": "2026-09-10T12:00:00Z",
            "html_url": "https://example/1",
            "user": {"login": "octocat"},
        }
    )
    assert github == {
        "body": "b",
        "created_at": "2026-09-10T12:00:00Z",
        "url": "https://example/1",
        "author": "octocat",
    }
    gitlab = module.normalize_comment(
        {
            "note": "n",
            "created_at": "2026-09-11T09:00:00Z",
            "web_url": "https://example/2",
            "author": {"username": "maintainer"},
        }
    )
    assert gitlab["body"] == "n"
    assert gitlab["url"] == "https://example/2"
    assert gitlab["author"] == "maintainer"


def test_a_v2_comment_rendered_by_the_poster_is_recovered_intact() -> None:
    module = load_recover_context()
    reviews = module.parse_review_comments([github_comment(rendered_comment())])

    assert len(reviews) == 1
    review = reviews[0]
    assert review.legacy is False
    assert review.cycle == 1
    assert review.score == "91/100"
    assert review.status == "passing"
    assert review.metadata["reviewed_sha"] == "1a2b3c4"
    recovered = module.extract_surviving_body(review.body)
    expected = (FIXTURES_DIR / "review-report.md").read_text(encoding="utf-8").strip()
    assert recovered == expected


def test_exact_v2_key_set_is_required() -> None:
    module = load_recover_context()
    valid = json.loads(
        (FIXTURES_DIR / "metadata-cases.json").read_text(encoding="utf-8")
    )["valid"]

    extra = dict(valid, adjusted_score=92)
    missing = {key: value for key, value in valid.items() if key != "findings_closed"}
    bodies = [
        github_comment(f"<!-- consensus-review\n{json.dumps(payload)}\n-->\n\nbody")
        for payload in (extra, missing)
    ]

    assert module.parse_review_comments(bodies) == []


def test_a_malformed_v2_comment_is_ignored_entirely() -> None:
    module = load_recover_context()
    reviews = module.parse_review_comments(fixture_comments("comments-github.json"))

    cycles = [(review.cycle, review.legacy) for review in reviews]
    assert cycles == [(1, True), (2, False)]
    assert module.next_cycle(reviews) == 3


def test_a_legacy_v1_review_is_history_only(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    legacy = {
        "schema_version": 1,
        "type": "review",
        "cycle": 4,
        "status": "failing",
        "score": 64,
    }
    comment = github_comment(
        f"<!-- consensus-review\n{json.dumps(legacy)}\n-->\n\nLegacy body"
    )
    reviews = module.parse_review_comments([comment])

    assert [review.legacy for review in reviews] == [True]
    assert module.next_cycle(reviews) == 5

    stub_ancestry(module, monkeypatch, True)
    basis, reason = module.resolve_scope_basis(reviews)
    assert basis == "full-diff"
    assert "no prior schema-v2 review" in reason


def test_a_v1_comment_of_another_type_is_ignored() -> None:
    module = load_recover_context()
    payload = {"schema_version": 1, "type": "recommendations", "cycle": 2}
    comment = github_comment(
        f"<!-- consensus-review\n{json.dumps(payload)}\n-->\n\nRecommendations"
    )
    assert module.parse_review_comments([comment]) == []


def test_a_non_consensus_comment_is_ignored() -> None:
    module = load_recover_context()
    assert module.parse_review_comments([github_comment("Looks good to me.")]) == []


def test_scope_narrows_when_the_reviewed_sha_is_still_an_ancestor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    reviews = module.parse_review_comments([github_comment(rendered_comment())])
    stub_ancestry(module, monkeypatch, True)

    basis, reason = module.resolve_scope_basis(reviews)
    assert basis == "delta-since:1a2b3c4"
    assert "cycle 01" in reason


def test_scope_falls_back_when_the_reviewed_sha_is_no_longer_an_ancestor(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    reviews = module.parse_review_comments([github_comment(rendered_comment())])
    stub_ancestry(module, monkeypatch, False)

    basis, reason = module.resolve_scope_basis(reviews)
    assert basis == "full-diff"
    assert "no longer an ancestor" in reason


def test_scope_falls_back_when_ancestry_cannot_be_verified(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    reviews = module.parse_review_comments([github_comment(rendered_comment())])
    stub_ancestry(module, monkeypatch, None)

    basis, reason = module.resolve_scope_basis(reviews)
    assert basis == "full-diff"
    assert "could not verify" in reason


def test_scope_uses_the_latest_v2_review_not_the_latest_comment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    comments = [
        github_comment(
            rendered_comment(cycle=1, reviewed_sha="aaaaaaa"),
            created_at="2026-09-10T10:00:00Z",
        ),
        github_comment(
            rendered_comment(cycle=2, reviewed_sha="bbbbbbb"),
            created_at="2026-09-10T11:00:00Z",
        ),
    ]
    reviews = module.parse_review_comments(comments)
    stub_ancestry(module, monkeypatch, True)

    assert module.resolve_scope_basis(reviews)[0] == "delta-since:bbbbbbb"


def test_no_prior_review_reviews_the_full_diff() -> None:
    module = load_recover_context()
    basis, reason = module.resolve_scope_basis([])
    assert basis == "full-diff"
    assert "no prior schema-v2 review" in reason


def test_sha_is_ancestor_maps_git_exit_codes(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_recover_context()
    monkeypatch.setattr(module, "GIT", "/usr/bin/git")

    def with_code(code: int):
        def fake(command: list[str], **kwargs: Any) -> Any:
            return subprocess.CompletedProcess(command, code, "", "")

        return fake

    monkeypatch.setattr(module.subprocess, "run", with_code(0))
    assert module.sha_is_ancestor("abc1234", "HEAD") is True
    monkeypatch.setattr(module.subprocess, "run", with_code(1))
    assert module.sha_is_ancestor("abc1234", "HEAD") is False
    monkeypatch.setattr(module.subprocess, "run", with_code(128))
    assert module.sha_is_ancestor("abc1234", "HEAD") is None

    monkeypatch.setattr(module, "GIT", None)
    assert module.sha_is_ancestor("abc1234", "HEAD") is None


def test_github_fetch_uses_the_paginated_issue_comments_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    monkeypatch.setattr(module, "GH", "/usr/bin/gh")
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], repo_dir: Any) -> str:
        captured["command"] = command
        captured["repo_dir"] = repo_dir
        return '[{"body": "x"}]'

    monkeypatch.setattr(module, "run_command", fake_run)
    assert module.fetch_github_comments(7, "/repo") == [{"body": "x"}]
    assert captured["command"] == [
        "/usr/bin/gh",
        "api",
        "repos/{owner}/{repo}/issues/7/comments",
        "--paginate",
    ]
    assert captured["repo_dir"] == "/repo"


def test_gitlab_fetch_uses_the_paginated_notes_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()
    monkeypatch.setattr(module, "GLAB", "/usr/bin/glab")
    captured: dict[str, Any] = {}

    def fake_run(command: list[str], repo_dir: Any) -> str:
        captured["command"] = command
        return '[{"note": "x"}]'

    monkeypatch.setattr(module, "run_command", fake_run)
    assert module.fetch_gitlab_comments(4, ".") == [{"note": "x"}]
    assert captured["command"] == [
        "/usr/bin/glab",
        "api",
        "projects/:id/merge_requests/4/notes",
        "--paginate",
    ]


def test_fetch_requires_the_platform_client(monkeypatch: pytest.MonkeyPatch) -> None:
    module = load_recover_context()
    monkeypatch.setattr(module, "GH", None)
    monkeypatch.setattr(module, "GLAB", None)
    with pytest.raises(FileNotFoundError, match="gh"):
        module.fetch_platform_comments(7, platform="github")
    with pytest.raises(FileNotFoundError, match="glab"):
        module.fetch_platform_comments(7, platform="gitlab")


def test_run_command_raises_on_a_failed_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    module = load_recover_context()

    def fake(command: list[str], **kwargs: Any) -> Any:
        return subprocess.CompletedProcess(command, 1, "", "unauthorized")

    monkeypatch.setattr(module.subprocess, "run", fake)
    with pytest.raises(subprocess.CalledProcessError):
        module.run_command(["gh"], ".")


def test_paginated_pages_decode_into_one_comment_list() -> None:
    """``gh``/``glab`` --paginate emit one JSON array per page, concatenated."""
    module = load_recover_context()
    two_pages = '[{"body": "a"}]\n[{"body": "b"}]'
    assert module.flatten_comment_pages(two_pages) == [{"body": "a"}, {"body": "b"}]
    assert module.flatten_comment_pages('[{"body": "a"}]') == [{"body": "a"}]
    assert module.flatten_comment_pages('[{"body": "a"}, 3, null]') == [{"body": "a"}]
    assert module.flatten_comment_pages("") == []


def test_load_comments_json_accepts_both_shapes(tmp_path: Path) -> None:
    module = load_recover_context()
    listed = tmp_path / "list.json"
    listed.write_text(json.dumps([{"body": "a"}, "skip me"]), encoding="utf-8")
    assert module.load_comments_json(listed) == [{"body": "a"}]

    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(json.dumps({"comments": [{"body": "b"}]}), encoding="utf-8")
    assert module.load_comments_json(wrapped) == [{"body": "b"}]

    invalid = tmp_path / "invalid.json"
    invalid.write_text(json.dumps({"comments": 5}), encoding="utf-8")
    with pytest.raises(ValueError):
        module.load_comments_json(invalid)


def test_main_reports_the_github_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_recover_context()
    stub_ancestry(module, monkeypatch, True)

    exit_code = module.main(
        [
            "7",
            "--platform",
            "github",
            "--repo-dir",
            str(tmp_path),
            "--comments-json",
            str(FIXTURES_DIR / "comments-github.json"),
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert out.startswith("# RECOVERED_CONTEXT")
    assert "**Platform:** github" in out
    assert "**PR number:** 7" in out
    assert "**Next cycle:** 03" in out
    assert "**Score source:** raw review score" in out
    assert "**Scope basis:** delta-since:1a2b3c4" in out
    assert "### Cycle 02" in out
    assert "Delegation: parallel-subagents. Plan: none." in out
    assert "Blast radius: 3 files, 2 opened, 1 closed." in out
    assert "## Legacy Reviews" in out
    assert "Cycle 01 — 64/100" in out
    assert "[F-1] [HIGH]" in out
    assert "Missing findings_closed" not in out


def test_main_reports_the_gitlab_thread(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_recover_context()
    stub_ancestry(module, monkeypatch, True)

    exit_code = module.main(
        [
            "4",
            "--platform",
            "gitlab",
            "--repo-dir",
            str(tmp_path),
            "--comments-json",
            str(FIXTURES_DIR / "comments-gitlab.json"),
        ]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "**Platform:** gitlab" in out
    assert "**MR number:** 4" in out
    assert "**Next cycle:** 03" in out
    assert "### Cycle 02" in out
    assert "Pipeline is green" not in out


def test_main_reports_an_empty_thread_as_the_first_cycle(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_recover_context()
    empty = tmp_path / "empty.json"
    empty.write_text(json.dumps({"comments": []}), encoding="utf-8")

    exit_code = module.main(
        ["7", "--repo-dir", str(tmp_path), "--comments-json", str(empty)]
    )

    assert exit_code == 0
    out = capsys.readouterr().out
    assert "**Next cycle:** 01" in out
    assert "**Scope basis:** full-diff" in out
    assert "None. This is the first cycle." in out


def test_main_reports_a_fetch_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    module = load_recover_context()

    def fail(*args: Any, **kwargs: Any) -> Any:
        raise subprocess.CalledProcessError(1, ["gh"], "", "unauthorized")

    monkeypatch.setattr(module, "fetch_platform_comments", fail)

    exit_code = module.main(["7", "--repo-dir", str(tmp_path)])

    assert exit_code == 1
    assert "failed to recover PR/MR comments" in capsys.readouterr().err


def test_extract_surviving_body_falls_back_without_a_details_block() -> None:
    module = load_recover_context()
    body = "<!-- consensus-review\n{}\n-->\n\nPlain body"
    assert module.extract_surviving_body(body) == "Plain body"
