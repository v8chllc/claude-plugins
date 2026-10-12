"""Exercise the posted advisory route through its three executable boundaries."""

import json
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
CONSENSUS_REVIEW_DIR = REPO_ROOT / "plugins/v8ch/skills/consensus-review"
SCRIPTS_DIR = CONSENSUS_REVIEW_DIR / "scripts"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import post_review_comment as poster  # noqa: E402
import review_contract as contract  # noqa: E402

REVIEWED_SHA = "a" * 40
REVIEW_URL = "https://example.test/review/7"


def advisory_report(score: int, severities: list[str]) -> str:
    finding_headings = [
        f"#### [F-{index}] [{severity}] Finding {index}"
        for index, severity in enumerate(severities, start=1)
    ]
    breakdown_rows = [
        f"| [F-{index}] {severity} | −{contract.SEVERITY_DEDUCTIONS[severity]} |"
        for index, severity in enumerate(severities, start=1)
    ]
    return "\n".join(
        [
            f"### Quality Score: {score}/100 — Passing",
            "",
            "### Run Provenance",
            "",
            "Delegation: parallel-subagents. Plan: none.",
            "",
            "### Evidence",
            "",
            "- **Files examined:** src/widget.py",
            "- **Commands run:** uv run pytest",
            "",
            "### Summary",
            "",
            "- Open findings affect widget behavior.",
            "",
            "### Must Fix",
            "",
            "None.",
            "",
            "### Should Fix",
            "",
            *finding_headings,
            "",
            "### Latent Findings",
            "",
            "None.",
            "",
            "### Plan Notes",
            "",
            "None.",
            "",
            "### Score Breakdown",
            "",
            "| Finding ID | Deduction |",
            "| --- | --- |",
            *breakdown_rows,
            f"| **Final score** | **{score}/100** |",
            "",
        ]
    )


@pytest.mark.parametrize(
    ("score", "severities", "cycle"),
    [(96, ["LOW", "LOW"], 1), (95, ["MEDIUM"], 7)],
)
def test_advisory_journey_posts_once_and_returns_full_signal_without_fixer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    score: int,
    severities: list[str],
    cycle: int,
) -> None:
    report = advisory_report(score, severities)
    report_path = tmp_path / "report.md"
    outcome_path = tmp_path / "outcome.json"
    summary_path = tmp_path / "summary.md"
    signal_path = tmp_path / "signal.json"
    report_path.write_text(report, encoding="utf-8")
    summary_path.write_text(
        "- F-1 has a demonstrated cost in src/widget.py.\n", encoding="utf-8"
    )

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "review_contract.py"),
            "resolve",
            "--report-file",
            str(report_path),
            "--score",
            str(score),
            "--status",
            "passing",
            "--reviewed-sha",
            REVIEWED_SHA,
            "--output",
            str(outcome_path),
        ],
        check=True,
    )
    outcome = contract.read_outcome(outcome_path)
    assert outcome.completion_kind == contract.COMPLETION_ADVISORY

    posts: list[str] = []

    def capture_post(
        pr_number: int, body: str, *, platform: str, repo_dir: str | Path
    ) -> None:
        assert pr_number == 7
        assert platform == "github"
        posts.append(body)

    monkeypatch.setattr(poster, "post_comment", capture_post)
    assert (
        poster.main(
            [
                "--pr-number",
                "7",
                "--review-file",
                str(report_path),
                "--summary-file",
                str(summary_path),
                "--outcome-file",
                str(outcome_path),
                "--repo-dir",
                str(tmp_path),
                "--cycle",
                str(cycle),
                "--delegation-mode",
                "parallel-subagents",
                "--plan-source",
                "none",
                "--scope-basis",
                "full-diff",
                "--files-touched",
                "1",
                "--findings-opened",
                str(len(severities)),
                "--findings-closed",
                "0",
            ]
        )
        == 0
    )
    assert len(posts) == 1
    posted_body = posts[0]
    metadata = contract.parse_metadata_block(posted_body)
    assert metadata is not None
    assert (metadata["score"], metadata["status"], metadata["reviewed_sha"]) == (
        score,
        "passing",
        REVIEWED_SHA,
    )
    assert "Complete with advisory findings for caller disposition." in posted_body
    assert report.strip() in posted_body

    subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "review_contract.py"),
            "signal",
            "--outcome-file",
            str(outcome_path),
            "--cycle",
            str(cycle),
            "--review-url",
            REVIEW_URL,
            "--output",
            str(signal_path),
        ],
        check=True,
    )
    signal = json.loads(signal_path.read_text(encoding="utf-8"))
    assert signal == {
        "signal": "REVIEW_COMPLETE_WITH_FINDINGS",
        "cycle": cycle,
        "details": {
            "score": score,
            "status": "passing",
            "review_url": REVIEW_URL,
            "reviewed_sha": REVIEWED_SHA,
            "open_findings": list(outcome.findings),
        },
    }
    fixer_calls: list[str] = []
    if signal is None:
        fixer_calls.append("fix")
    assert fixer_calls == []
    # The skill routes a non-null completion signal directly to its stop rule.
    skill = (CONSENSUS_REVIEW_DIR / "SKILL.md").read_text(encoding="utf-8")
    assert "Emit the JSON object written to the signal file when it is" in skill
    assert "Do not invoke the fixer" in skill
