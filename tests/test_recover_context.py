import importlib.util
import json
from pathlib import Path
from types import ModuleType

import pytest
from typer.testing import CliRunner

SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "plugins/v8ch/skills/consensus-review/scripts/recover_context.py"
)

POST_SCRIPT_PATH = (
    Path(__file__).resolve().parent.parent
    / "plugins/v8ch/skills/consensus-review/scripts/post_review_comment.py"
)


def load_post_review_comment_for_recover() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "post_review_comment_for_recover", POST_SCRIPT_PATH
    )
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_recover_context() -> ModuleType:
    spec = importlib.util.spec_from_file_location("recover_context", SCRIPT_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def audit_body(metadata: dict[str, object], visible_body: str) -> str:
    payload = {"schema_version": 1, **metadata}
    encoded = json.dumps(payload, sort_keys=True)
    return f"<!-- consensus-review\n{encoded}\n-->\n\n{visible_body}"


def write_comments(path: Path, comments: list[dict[str, object]]) -> None:
    path.write_text(json.dumps({"comments": comments}), encoding="utf-8")


def test_parse_accepted_findings_inline_format() -> None:
    module = load_recover_context()
    text = (
        "1. [HIGH] Missing error handling — `src/foo.py`\n"
        "2. [MEDIUM] Unused variable — `src/bar.py`\n"
    )
    findings = module._parse_accepted_findings(text)
    assert findings == [
        {"severity": "HIGH", "title": "Missing error handling", "file": "src/foo.py"},
        {"severity": "MEDIUM", "title": "Unused variable", "file": "src/bar.py"},
    ]


def test_parse_opted_in_findings_inline_format() -> None:
    module = load_recover_context()
    text = (
        "1. Potential race condition — `src/foo.py` "
        "(low-confidence reviewer: correctness-reviewer)\n"
        "2. Stale comment reference — `src/util.py` "
        "(low-confidence reviewer: standards-reviewer)\n"
    )
    findings = module._parse_opted_in_findings(text)
    assert findings == [
        {
            "title": "Potential race condition",
            "file": "src/foo.py",
            "source": "low-confidence reviewer: correctness-reviewer",
        },
        {
            "title": "Stale comment reference",
            "file": "src/util.py",
            "source": "low-confidence reviewer: standards-reviewer",
        },
    ]


def test_parse_audit_comments_filters_non_consensus_comments() -> None:
    module = load_recover_context()
    raw_comments = [
        {"body": "ordinary comment", "createdAt": "2026-01-01T00:00:00Z"},
        {
            "body": audit_body(
                {"type": "review", "cycle": 1, "status": "passing", "score": 88},
                "### Summary\n- Good\n",
            ),
            "createdAt": "2026-01-01T00:01:00Z",
            "url": "https://example.test/comment/1",
        },
    ]

    comments = module.parse_audit_comments(raw_comments)

    assert len(comments) == 1
    assert comments[0].comment_type == "review"
    assert comments[0].cycle == 1
    assert comments[0].url == "https://example.test/comment/1"


def test_first_cycle_from_empty_pr_comments(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(comments_json, [])

    result = runner.invoke(
        module.app,
        ["123", "--platform", "github", "--comments-json", str(comments_json)],
    )

    assert result.exit_code == 0
    assert "Next cycle:** 01" in result.output
    assert "No prior consensus-review comments found" in result.output
    assert "Audit source:** PR/MR comments" in result.output
    assert "PR 123" in result.output


def test_prior_cycle_context_from_pr_comments(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(
        comments_json,
        [
            {
                "body": audit_body(
                    {"type": "review", "cycle": 1, "status": "failing", "score": 78},
                    "### ❌ Review\n\n### Summary\n- Found 3 must-fix items\n\n"
                    "<details>\n<summary>Full consensus review</summary>\n\n"
                    "### Quality Score: 78/100\n\n</details>\n",
                ),
                "createdAt": "2026-01-01T00:00:00Z",
                "url": "https://example.test/review-1",
            },
            {
                "body": audit_body(
                    {"type": "fix_validation", "cycle": 1, "status": "clean"},
                    "### Review Findings Fixed\n\n### Summary\n"
                    "- Fix Validation: All 3 findings from cycle 1 review resolved.\n\n"
                    "<details>\n<summary>Full fix log</summary>\n\n## Status Table\n",
                ),
                "createdAt": "2026-01-01T00:10:00Z",
                "url": "https://example.test/fix-1",
            },
            {
                "body": audit_body(
                    {
                        "type": "acceptance",
                        "cycle": 1,
                        "before_score": 78,
                        "after_score": 85,
                    },
                    "### Accepted Findings\n"
                    "1. [HIGH] Defensive null check — `src/service.py`\n",
                ),
                "createdAt": "2026-01-01T00:11:00Z",
            },
            {
                "body": audit_body(
                    {"type": "low_confidence_opt_in", "cycle": 1},
                    "### Added Findings\n"
                    "1. Stale comment reference — `src/util.py` "
                    "(low-confidence reviewer: standards-reviewer)\n",
                ),
                "createdAt": "2026-01-01T00:12:00Z",
            },
        ],
    )

    result = runner.invoke(
        module.app,
        ["100", "--platform", "github", "--comments-json", str(comments_json)],
    )

    assert result.exit_code == 0
    assert "Next cycle:** 02" in result.output
    assert (
        "| 01 | 78/100 | failing | present | https://example.test/review-1 |"
        in result.output
    )
    assert "Found 3 must-fix items" in result.output
    assert "Fix Validation: All 3 findings" in result.output
    assert "Defensive null check" in result.output
    assert "Total accepted: 1 findings" in result.output
    assert "Stale comment reference" in result.output
    assert "Total historical opt-ins: 1 findings" in result.output
    assert "Latest fix validation: cycle 01" in result.output


def test_resolves_latest_cycle_scratch_artifacts_from_github_comments(
    tmp_path: Path,
) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    scratch_dir = tmp_path / "scratch"
    write_comments(
        comments_json,
        [
            {
                "body": audit_body(
                    {"type": "review", "cycle": 1, "status": "passing", "score": 86},
                    "### ✅ Review\n\n### Summary\n- Cycle 1 summary\n\n"
                    "<details>\n<summary>Full consensus review</summary>\n\n"
                    "### Quality Score: 86/100\n\nOld review details.\n\n</details>\n",
                ),
                "createdAt": "2026-01-01T00:00:00Z",
                "url": "https://example.test/review-1",
            },
            {
                "body": audit_body(
                    {"type": "fix_validation", "cycle": 1, "status": "clean"},
                    "### Review Findings Fixed\n\n### Summary\n- Fixed cycle 1\n\n"
                    "<details>\n<summary>Full fix log</summary>\n\n"
                    "## Status Table\n\nOld fix log.\n\n</details>\n",
                ),
                "createdAt": "2026-01-01T00:10:00Z",
                "url": "https://example.test/fix-1",
            },
            {
                "body": audit_body(
                    {"type": "review", "cycle": 2, "status": "failing", "score": 73},
                    "### ❌ Review\n\n### Summary\n- Latest review summary\n\n"
                    "<details>\n<summary>Full consensus review</summary>\n\n"
                    "### Quality Score: 73/100\n\n"
                    "Latest review details.\n\n</details>\n",
                ),
                "createdAt": "2026-01-02T00:00:00Z",
                "url": "https://example.test/review-2",
            },
            {
                "body": audit_body(
                    {
                        "type": "additional_acceptance",
                        "cycle": 2,
                        "before_score": 73,
                        "after_score": 78,
                    },
                    "### Accepted Findings\n"
                    "1. [MEDIUM] Accepted restart finding — `src/accepted.py`\n",
                ),
                "createdAt": "2026-01-02T00:01:00Z",
                "url": "https://example.test/additional-2",
            },
            {
                "body": audit_body(
                    {"type": "low_confidence_opt_in", "cycle": 2},
                    "### Added Findings\n"
                    "1. Restart opt-in — `src/opt_in.py` "
                    "(low-confidence reviewer: correctness-reviewer)\n",
                ),
                "createdAt": "2026-01-02T00:02:00Z",
                "url": "https://example.test/opt-in-2",
            },
        ],
    )

    result = runner.invoke(
        module.app,
        [
            "100",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
            "--scratch-dir",
            str(scratch_dir),
            "--json-summary",
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(result.output)
    assert summary["latest_cycle"] == 2
    assert summary["next_cycle"] == 3
    assert summary["latest_review"]["url"] == "https://example.test/review-2"
    assert summary["latest_fix_validation"] is None
    assert summary["cycle_gaps"] == [
        {"cycle": 2, "reason": "missing fix-validation comment"}
    ]
    assert summary["current_cycle_additional_acceptances"] == [
        {
            "severity": "MEDIUM",
            "title": "Accepted restart finding",
            "file": "src/accepted.py",
            "cycle": 2,
            "comment_type": "additional_acceptance",
            "comment_url": "https://example.test/additional-2",
        }
    ]
    assert summary["current_cycle_low_confidence_opt_ins"] == [
        {
            "title": "Restart opt-in",
            "file": "src/opt_in.py",
            "source": "low-confidence reviewer: correctness-reviewer",
            "cycle": 2,
            "comment_type": "low_confidence_opt_in",
            "comment_url": "https://example.test/opt-in-2",
        }
    ]

    review_path = Path(summary["scratch_paths"]["latest_review"])
    assert review_path.read_text(encoding="utf-8") == (
        "### Quality Score: 73/100\n\nLatest review details.\n"
    )
    assert "latest_fix_validation" not in summary["scratch_paths"]
    assert "summary" not in summary["scratch_paths"]


def test_resolves_gitlab_note_comments_with_fix_validation(
    tmp_path: Path,
) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "gitlab-comments.json"
    scratch_dir = tmp_path / "scratch"
    write_comments(
        comments_json,
        [
            {
                "note": audit_body(
                    {"type": "review", "cycle": 4, "status": "passing", "score": 88},
                    "### ✅ Review\n\n### Summary\n- GitLab review summary\n\n"
                    "<details>\n<summary>Full consensus review</summary>\n\n"
                    "GitLab latest review.\n\n</details>\n",
                ),
                "created_at": "2026-01-04T00:00:00Z",
                "web_url": "https://gitlab.example.test/review-4",
                "author": {"username": "bot"},
            },
            {
                "note": audit_body(
                    {"type": "fix_validation", "cycle": 4, "status": "clean"},
                    "### Review Findings Fixed\n\n### Summary\n- GitLab fix summary\n\n"
                    "<details>\n<summary>Full fix log</summary>\n\n"
                    "GitLab fix log.\n\n</details>\n",
                ),
                "created_at": "2026-01-04T00:03:00Z",
                "web_url": "https://gitlab.example.test/fix-4",
            },
        ],
    )

    result = runner.invoke(
        module.app,
        [
            "200",
            "--platform",
            "gitlab",
            "--comments-json",
            str(comments_json),
            "--scratch-dir",
            str(scratch_dir),
            "--json-summary",
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(result.output)
    assert summary["platform"] == "gitlab"
    assert summary["latest_cycle"] == 4
    assert summary["cycle_gaps"] == []
    assert (
        summary["latest_fix_validation"]["url"] == "https://gitlab.example.test/fix-4"
    )
    assert (
        Path(summary["scratch_paths"]["latest_review"]).read_text(encoding="utf-8")
        == "GitLab latest review.\n"
    )
    assert (
        Path(summary["scratch_paths"]["latest_fix_validation"]).read_text(
            encoding="utf-8"
        )
        == "GitLab fix log.\n"
    )


def test_first_cycle_gitlab_label(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(comments_json, [])

    result = runner.invoke(
        module.app,
        ["456", "--platform", "gitlab", "--comments-json", str(comments_json)],
    )

    assert result.exit_code == 0
    assert "Next cycle:** 01" in result.output
    assert "MR 456" in result.output
    assert "Platform:** gitlab" in result.output


def test_platform_default_when_env_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(comments_json, [])
    monkeypatch.chdir(tmp_path)

    result = runner.invoke(module.app, ["999", "--comments-json", str(comments_json)])

    assert result.exit_code == 0
    assert "Platform:** github" in result.output


def _rouge_context_body(
    spec_text: str | None = None,
    plan_text: str | None = None,
    has_spec: bool | None = None,
    has_plan: bool | None = None,
) -> str:
    payload = json.dumps(
        {
            "has_plan": has_plan if has_plan is not None else bool(plan_text),
            "has_spec": has_spec if has_spec is not None else bool(spec_text),
            "schema_version": 1,
            "type": "planning_context",
        },
        sort_keys=True,
    )
    parts = [f"<!-- review-context\n{payload}\n-->\n## Planning Context\n"]
    if spec_text:
        parts.append(
            f"<details>\n<summary>Spec</summary>\n\n{spec_text}\n\n</details>\n"
        )
    if plan_text:
        parts.append(
            f"<details>\n<summary>Plan</summary>\n\n{plan_text}\n\n</details>\n"
        )
    return "\n".join(parts)


def test_extract_planning_context_with_spec_and_plan() -> None:
    module = load_recover_context()
    spec = "Do X, Y, and Z."
    plan = "1. Implement X\n2. Implement Y"
    raw = [
        {
            "body": _rouge_context_body(spec_text=spec, plan_text=plan),
            "createdAt": "2026-01-01T00:00:00Z",
            "url": "https://example.test/context",
        },
        {"body": "ordinary comment", "createdAt": "2026-01-01T00:01:00Z"},
    ]

    result = module.extract_planning_context(raw)

    assert result is not None
    assert result["spec"] == spec
    assert result["plan"] == plan
    assert result["url"] == "https://example.test/context"
    assert result["has_spec"] is True
    assert result["has_plan"] is True
    assert result["schema_version"] == 1


def test_extract_planning_context_spec_only() -> None:
    module = load_recover_context()
    spec = "Build the widget."
    raw = [
        {
            "body": _rouge_context_body(spec_text=spec),
            "createdAt": "2026-01-01T00:00:00Z",
            "url": "https://example.test/ctx",
        }
    ]

    result = module.extract_planning_context(raw)

    assert result is not None
    assert result["spec"] == spec
    assert result["plan"] is None
    assert result["has_spec"] is True
    assert result["has_plan"] is False


def test_extract_planning_context_returns_none_when_absent() -> None:
    module = load_recover_context()
    raw = [
        {"body": "ordinary comment", "createdAt": "2026-01-01T00:00:00Z"},
        {
            "body": audit_body(
                {"type": "review", "cycle": 1, "status": "clean", "score": 100},
                "### Summary\n- Clean.\n",
            ),
            "createdAt": "2026-01-01T00:01:00Z",
        },
    ]

    assert module.extract_planning_context(raw) is None


def test_extract_planning_context_ignores_wrong_schema_version() -> None:
    module = load_recover_context()
    bad_payload = json.dumps({"schema_version": 2, "type": "planning_context"})
    body = f"<!-- review-context\n{bad_payload}\n-->\n## Planning Context\n"
    raw = [{"body": body, "createdAt": "2026-01-01T00:00:00Z"}]

    assert module.extract_planning_context(raw) is None


def test_json_summary_includes_planning_context(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    spec = "Build the widget."
    write_comments(
        comments_json,
        [
            {
                "body": _rouge_context_body(spec_text=spec),
                "createdAt": "2026-01-01T00:00:00Z",
                "url": "https://example.test/ctx",
            }
        ],
    )

    result = runner.invoke(
        module.app,
        [
            "123",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
            "--json-summary",
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(result.output)
    assert summary["planning_context"] is not None
    assert summary["planning_context"]["spec"] == spec
    assert summary["planning_context"]["plan"] is None
    assert summary["planning_context"]["url"] == "https://example.test/ctx"


def test_json_summary_planning_context_none_when_absent(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(comments_json, [])

    result = runner.invoke(
        module.app,
        [
            "123",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
            "--json-summary",
        ],
    )

    assert result.exit_code == 0
    summary = json.loads(result.output)
    assert summary["planning_context"] is None


def test_build_context_output_includes_planning_context(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    spec = "Build the thing."
    plan = "1. Step A\n2. Step B"
    write_comments(
        comments_json,
        [
            {
                "body": _rouge_context_body(spec_text=spec, plan_text=plan),
                "createdAt": "2026-01-01T00:00:00Z",
                "url": "https://example.test/ctx",
            }
        ],
    )

    result = runner.invoke(
        module.app,
        ["123", "--platform", "github", "--comments-json", str(comments_json)],
    )

    assert result.exit_code == 0
    assert "Planning Context" in result.output
    assert spec in result.output
    assert plan in result.output
    assert "Source Specification" in result.output
    assert "Implementation Plan" in result.output


def test_build_context_output_shows_not_found_when_no_context(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(comments_json, [])

    result = runner.invoke(
        module.app,
        ["123", "--platform", "github", "--comments-json", str(comments_json)],
    )

    assert result.exit_code == 0
    assert "Planning Context" in result.output
    assert "Not found." in result.output


def _recommendations_body(
    *,
    cycle: int,
    acceptance_lines: list[str],
    opt_in_lines: list[str],
) -> str:
    acceptance_text = "\n".join(acceptance_lines) if acceptance_lines else "None."
    opt_in_text = "\n".join(opt_in_lines) if opt_in_lines else "None."
    visible = (
        "### Review Recommendations\n\n"
        f"*Cycle: {cycle:02d}*\n\n"
        "---\n\n"
        "### Recommended for Acceptance\n\n"
        f"{acceptance_text}\n\n"
        "### Recommended for Opt-In\n\n"
        f"{opt_in_text}\n\n"
        "These recommendations are advisory.\n"
    )
    return audit_body({"type": "recommendations", "cycle": cycle}, visible)


def test_parse_recommendations_acceptance_and_opt_in_sections() -> None:
    module = load_recover_context()
    body = _recommendations_body(
        cycle=2,
        acceptance_lines=[
            "1. [F-3] [HIGH] Dead variable in _run_json"
            " — `scripts/recover_context.py:228`",
            "2. [F-5] [MEDIUM] Defensive null check — `src/service.py:42`",
        ],
        opt_in_lines=[
            "1. [F-7] [LOW] Stale comment reference — `src/util.py:12`",
        ],
    )

    acceptance = module._parse_acceptance_recommendations(body)
    opt_in = module._parse_opt_in_recommendations(body)

    assert acceptance == [
        {
            "review_number": "3",
            "severity": "HIGH",
            "title": "Dead variable in _run_json",
            "file": "scripts/recover_context.py:228",
        },
        {
            "review_number": "5",
            "severity": "MEDIUM",
            "title": "Defensive null check",
            "file": "src/service.py:42",
        },
    ]
    assert opt_in == [
        {
            "review_number": "7",
            "severity": "LOW",
            "title": "Stale comment reference",
            "file": "src/util.py:12",
        },
    ]


def test_resolve_recommendations_filters_to_latest_cycle(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    scratch_dir = tmp_path / "scratch"
    write_comments(
        comments_json,
        [
            {
                "body": audit_body(
                    {"type": "review", "cycle": 1, "status": "passing", "score": 86},
                    "### Summary\n- cycle 1\n",
                ),
                "createdAt": "2026-01-01T00:00:00Z",
                "url": "https://example.test/review-1",
            },
            {
                "body": _recommendations_body(
                    cycle=1,
                    acceptance_lines=[
                        "1. [F-1] [HIGH] Old acceptance — `src/old.py`",
                    ],
                    opt_in_lines=[
                        "1. [F-2] [LOW] Old opt-in — `src/old.py`",
                    ],
                ),
                "createdAt": "2026-01-01T00:01:00Z",
                "url": "https://example.test/recs-1",
            },
            {
                "body": audit_body(
                    {"type": "review", "cycle": 2, "status": "failing", "score": 73},
                    "### Summary\n- cycle 2\n",
                ),
                "createdAt": "2026-01-02T00:00:00Z",
                "url": "https://example.test/review-2",
            },
            {
                "body": _recommendations_body(
                    cycle=2,
                    acceptance_lines=[
                        "1. [F-3] [MEDIUM] New acceptance — `src/new.py`",
                    ],
                    opt_in_lines=[
                        "1. [F-4] [LOW] New opt-in — `src/new.py`",
                    ],
                ),
                "createdAt": "2026-01-02T00:01:00Z",
                "url": "https://example.test/recs-2",
            },
        ],
    )

    result = runner.invoke(
        module.app,
        [
            "100",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
            "--scratch-dir",
            str(scratch_dir),
            "--json-summary",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    # Only cycle-2 recommendations are surfaced as current; cycle-1 are not
    # auto-applied (informational only).
    assert summary["current_cycle_acceptance_recommendations"] == [
        {
            "review_number": "3",
            "severity": "MEDIUM",
            "title": "New acceptance",
            "file": "src/new.py",
            "cycle": 2,
            "comment_type": "recommendations",
            "comment_url": "https://example.test/recs-2",
        }
    ]
    assert summary["current_cycle_opt_in_recommendations"] == [
        {
            "review_number": "4",
            "severity": "LOW",
            "title": "New opt-in",
            "file": "src/new.py",
            "cycle": 2,
            "comment_type": "recommendations",
            "comment_url": "https://example.test/recs-2",
        }
    ]
    assert summary["source_comment_urls"]["recommendations"] == [
        "https://example.test/recs-1",
        "https://example.test/recs-2",
    ]
    acceptance_path = Path(
        summary["scratch_paths"]["current_cycle_acceptance_recommendations"]
    )
    opt_in_path = Path(summary["scratch_paths"]["current_cycle_opt_in_recommendations"])
    assert acceptance_path.name == "acceptance-recommendations-02.md"
    assert opt_in_path.name == "opt-in-recommendations-02.md"
    assert (
        acceptance_path.read_text(encoding="utf-8")
        == "1. [F-3] [MEDIUM] New acceptance — `src/new.py`\n"
    )
    assert (
        opt_in_path.read_text(encoding="utf-8")
        == "1. [F-4] [LOW] New opt-in — `src/new.py`\n"
    )


def test_resolve_no_recommendations_returns_empty_lists(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(
        comments_json,
        [
            {
                "body": audit_body(
                    {"type": "review", "cycle": 1, "status": "passing", "score": 86},
                    "### Summary\n- cycle 1\n",
                ),
                "createdAt": "2026-01-01T00:00:00Z",
            },
        ],
    )

    result = runner.invoke(
        module.app,
        [
            "100",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
            "--json-summary",
        ],
    )

    assert result.exit_code == 0, result.output
    summary = json.loads(result.output)
    assert summary["current_cycle_acceptance_recommendations"] == []
    assert summary["current_cycle_opt_in_recommendations"] == []
    assert summary["source_comment_urls"]["recommendations"] == []


def test_older_recommendations_surfaced_as_historical_only(tmp_path: Path) -> None:
    module = load_recover_context()
    runner = CliRunner()
    comments_json = tmp_path / "comments.json"
    write_comments(
        comments_json,
        [
            {
                "body": audit_body(
                    {"type": "review", "cycle": 1, "status": "failing", "score": 70},
                    "### Summary\n- cycle 1\n",
                ),
                "createdAt": "2026-01-01T00:00:00Z",
            },
            {
                "body": _recommendations_body(
                    cycle=1,
                    acceptance_lines=[
                        "1. [F-1] [HIGH] Older acceptance — `src/older.py`",
                    ],
                    opt_in_lines=[],
                ),
                "createdAt": "2026-01-01T00:01:00Z",
                "url": "https://example.test/older-recs",
            },
            {
                "body": audit_body(
                    {"type": "review", "cycle": 2, "status": "failing", "score": 75},
                    "### Summary\n- cycle 2\n",
                ),
                "createdAt": "2026-01-02T00:00:00Z",
            },
        ],
    )

    # Markdown context output should include historical recommendations and
    # advisory framing, but the JSON summary should NOT auto-promote the
    # older comment into the current-cycle lists.
    md_result = runner.invoke(
        module.app,
        [
            "100",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
        ],
    )
    assert md_result.exit_code == 0, md_result.output
    assert "Review Recommendations (Historical)" in md_result.output
    assert "Older acceptance" in md_result.output
    assert "advisory" in md_result.output

    json_result = runner.invoke(
        module.app,
        [
            "100",
            "--platform",
            "github",
            "--comments-json",
            str(comments_json),
            "--json-summary",
        ],
    )
    assert json_result.exit_code == 0, json_result.output
    summary = json.loads(json_result.output)
    assert summary["latest_cycle"] == 2
    assert summary["current_cycle_acceptance_recommendations"] == []
    assert summary["current_cycle_opt_in_recommendations"] == []


def test_recommendations_round_trip_no_phantom_entries(tmp_path: Path) -> None:
    """Round-trip test: rendered template body must not produce phantom entries.

    The recommendations-comment template embeds FORMAT RULE example lines
    inside HTML comments. Those comments must be stripped before parsing so
    that only the real findings supplied by the caller are returned.
    """
    rc_module = load_recover_context()
    prc_module = load_post_review_comment_for_recover()

    # Write real findings files (one acceptance, one opt-in)
    acceptance_file = tmp_path / "acceptance-recs.md"
    acceptance_file.write_text(
        "1. [F-2] [HIGH] Missing input validation — `src/api/handler.py:42`\n"
    )
    opt_in_file = tmp_path / "opt-in-recs.md"
    opt_in_file.write_text(
        "1. [F-9] [LOW] Stale comment reference — `src/util.py:12`\n"
    )

    # Render via the real template (includes HTML FORMAT RULE comment blocks)
    body = prc_module.build_recommendations_comment_body(
        cycle=1,
        acceptance_findings_file=str(acceptance_file),
        opt_in_findings_file=str(opt_in_file),
    )

    # Parse the rendered body — must return only the real findings
    acceptance_parsed = rc_module._parse_acceptance_recommendations(body)
    opt_in_parsed = rc_module._parse_opt_in_recommendations(body)

    assert acceptance_parsed == [
        {
            "review_number": "2",
            "severity": "HIGH",
            "title": "Missing input validation",
            "file": "src/api/handler.py:42",
        }
    ], f"Expected exactly one acceptance entry, got: {acceptance_parsed}"

    assert opt_in_parsed == [
        {
            "review_number": "9",
            "severity": "LOW",
            "title": "Stale comment reference",
            "file": "src/util.py:12",
        }
    ], f"Expected exactly one opt-in entry, got: {opt_in_parsed}"

    # Also verify "None." case returns empty lists
    none_acceptance_file = tmp_path / "acceptance-none.md"
    none_acceptance_file.write_text("None.\n")
    none_opt_in_file = tmp_path / "opt-in-none.md"
    none_opt_in_file.write_text("None.\n")

    none_body = prc_module.build_recommendations_comment_body(
        cycle=1,
        acceptance_findings_file=str(none_acceptance_file),
        opt_in_findings_file=str(none_opt_in_file),
    )

    assert rc_module._parse_acceptance_recommendations(none_body) == []
    assert rc_module._parse_opt_in_recommendations(none_body) == []
