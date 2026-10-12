import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "plugins/v8ch/skills/consensus-review/scripts"
FIXTURES_DIR = REPO_ROOT / "tests/fixtures/consensus-review"
SKILL_FILE = REPO_ROOT / "plugins/v8ch/skills/consensus-review/SKILL.md"
POSTER_AGENT = REPO_ROOT / "plugins/v8ch/agents/consensus-review-poster.md"

if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import review_contract as contract  # noqa: E402


def load_fixture(name: str) -> dict[str, Any]:
    data: dict[str, Any] = json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))
    return data


SCORING = load_fixture("scoring-cases.json")
METADATA = load_fixture("metadata-cases.json")


def build_findings(raw: list[dict[str, Any]]) -> list[contract.Finding]:
    return [
        contract.Finding(
            identifier=entry["identifier"],
            section=entry["section"],
            severity=entry["severity"],
        )
        for entry in raw
    ]


def score_breakdown(severities: list[str], score: int) -> str:
    rows = [
        "### Score Breakdown",
        "",
        "| Finding | Deduction |",
        "| --- | --- |",
    ]
    rows.extend(
        f"| [F-{index}] {severity} | −{contract.SEVERITY_DEDUCTIONS[severity]} |"
        for index, severity in enumerate(severities, start=1)
    )
    rows.append(f"| **Final score** | **{score}/100** |")
    return "\n".join(rows)


def metadata_case(case: dict[str, Any]) -> dict[str, Any]:
    payload = dict(METADATA["valid"])
    payload.update(case.get("overrides", {}))
    for key in case.get("remove", []):
        payload.pop(key)
    return payload


@pytest.mark.parametrize(
    "case", SCORING["cases"], ids=[case["name"] for case in SCORING["cases"]]
)
def test_scoring_cases_match_the_contract(case: dict[str, Any]) -> None:
    findings = build_findings(case["findings"])
    score = contract.score_findings(findings)
    assert score == case["expected_score"]
    assert contract.review_status(score, findings) == case["expected_status"]


def test_deduction_table_matches_the_contract() -> None:
    assert contract.SEVERITY_DEDUCTIONS == {
        "CRITICAL": 20,
        "HIGH": 10,
        "MEDIUM": 5,
        "LOW": 2,
    }


def test_reviewer_count_never_changes_a_deduction() -> None:
    """Three reviewers raising one defect deduct what one reviewer deducts.

    The synthesizer merges duplicates before scoring, so the contract sees one
    finding either way and has no reviewer-count input at all.
    """
    single = [contract.Finding("F-1", contract.MUST_FIX, "HIGH")]
    assert contract.score_findings(single) == 90
    assert contract.deduction(single[0]) == 10


def test_plan_notes_deduct_nothing() -> None:
    note = contract.Finding("P-1", contract.PLAN_NOTE)
    assert contract.deduction(note) == 0
    assert contract.score_findings([note]) == 100


def test_plan_note_rejects_a_severity() -> None:
    with pytest.raises(contract.ContractError):
        contract.Finding("P-1", contract.PLAN_NOTE, "HIGH")


def test_finding_requires_a_known_severity() -> None:
    with pytest.raises(contract.ContractError):
        contract.Finding("F-1", contract.MUST_FIX, "BLOCKER")


def test_finding_requires_a_known_section() -> None:
    with pytest.raises(contract.ContractError):
        contract.Finding("F-1", "nice-to-have", "LOW")


def test_clean_needs_both_the_score_and_an_empty_blocker_list() -> None:
    blocked = [contract.Finding("F-1", contract.SHOULD_FIX, "LOW")]
    assert contract.review_status(98, blocked) == contract.STATUS_PASSING
    assert contract.review_status(98, []) == contract.STATUS_CLEAN


def test_statuses_are_mutually_exclusive_across_the_boundaries() -> None:
    assert contract.review_status(84, []) == contract.STATUS_FAILING
    assert contract.review_status(85, []) == contract.STATUS_PASSING
    assert contract.review_status(94, []) == contract.STATUS_PASSING
    assert contract.review_status(95, []) == contract.STATUS_CLEAN


def test_status_labels() -> None:
    assert contract.status_label("clean") == "Fully Clean"
    assert contract.status_label("passing") == "Passing"
    assert contract.status_label("failing") == "Failing"
    with pytest.raises(contract.ContractError):
        contract.status_label("unknown")


def test_valid_metadata_fixture_passes_validation() -> None:
    assert contract.validate_metadata(dict(METADATA["valid"]))


@pytest.mark.parametrize(
    "case",
    METADATA["valid_variants"],
    ids=[case["name"] for case in METADATA["valid_variants"]],
)
def test_valid_metadata_variants(case: dict[str, Any]) -> None:
    assert contract.validate_metadata(metadata_case(case))


@pytest.mark.parametrize(
    "case", METADATA["invalid"], ids=[case["name"] for case in METADATA["invalid"]]
)
def test_invalid_metadata_is_rejected(case: dict[str, Any]) -> None:
    with pytest.raises(contract.ContractError):
        contract.validate_metadata(metadata_case(case))


def test_metadata_key_set_is_exactly_the_twelve_contract_keys() -> None:
    assert contract.METADATA_KEYS == {
        "cycle",
        "delegation_mode",
        "files_touched",
        "findings_closed",
        "findings_opened",
        "plan_source",
        "reviewed_sha",
        "schema_version",
        "scope_basis",
        "score",
        "status",
        "type",
    }
    assert set(METADATA["valid"]) == contract.METADATA_KEYS


def test_metadata_is_rejected_when_it_is_not_an_object() -> None:
    with pytest.raises(contract.ContractError):
        contract.validate_metadata(["not", "an", "object"])


def test_build_metadata_matches_the_contract_example() -> None:
    payload = contract.build_metadata(
        cycle=1,
        status="clean",
        score=100,
        delegation_mode="parallel-subagents",
        plan_source="none",
        reviewed_sha="0000000",
        scope_basis="full-diff",
        files_touched=0,
        findings_opened=0,
        findings_closed=0,
    )
    assert payload == METADATA["valid"]
    block = contract.render_metadata_block(payload)
    assert block == f"<!-- consensus-review\n{METADATA['encoded']}\n-->"


def test_metadata_block_round_trips_through_a_comment_body() -> None:
    payload = contract.build_metadata(
        cycle=3,
        status="failing",
        score=71,
        delegation_mode="sequential-fallback",
        plan_source="supplied: .plan/feature.md",
        reviewed_sha="abc1234",
        scope_basis="delta-since:9f3a25e",
        files_touched=9,
        findings_opened=4,
        findings_closed=2,
    )
    body = f"{contract.render_metadata_block(payload)}\n\n### Review body\n"
    recovered = contract.parse_metadata_block(body)
    assert recovered is not None
    assert contract.validate_metadata(recovered) == payload
    assert contract.strip_metadata_block(body) == "### Review body"


def test_parse_metadata_block_tolerates_missing_and_malformed_blocks() -> None:
    assert contract.parse_metadata_block("no metadata here") is None
    assert (
        contract.parse_metadata_block("<!-- consensus-review\n{not json\n-->") is None
    )
    assert contract.parse_metadata_block("<!-- consensus-review\n[1, 2]\n-->") is None


def test_legacy_v1_reviews_are_recognized_but_not_valid_v2() -> None:
    legacy = {"schema_version": 1, "type": "review", "cycle": 2, "score": 64}
    assert contract.is_legacy_review(legacy)
    with pytest.raises(contract.ContractError):
        contract.validate_metadata(legacy)


def test_non_review_v1_comment_types_are_not_legacy_reviews() -> None:
    assert not contract.is_legacy_review(
        {"schema_version": 1, "type": "fix_validation", "cycle": 2}
    )
    assert not contract.is_legacy_review({"schema_version": 2, "type": "review"})


def test_plan_source_and_scope_basis_helpers() -> None:
    assert contract.validate_plan_source("none") == "none"
    assert contract.validate_plan_source("supplied: docs/plan.md")
    assert contract.validate_scope_basis("full-diff") == "full-diff"
    assert contract.validate_scope_basis("delta-since:abc1234")
    with pytest.raises(contract.ContractError):
        contract.validate_plan_source(None)
    with pytest.raises(contract.ContractError):
        contract.validate_scope_basis(7)


@pytest.mark.parametrize(
    "value",
    [
        "supplied: /Users/someone/plan.md",
        "supplied: ~/plans/feature.md",
        "supplied: /tmp/plan.md",
        "supplied: C:\\plans\\feature.md",
    ],
)
def test_an_absolute_or_home_plan_path_is_refused(value: str) -> None:
    """plan_source is published twice and read without this checkout."""
    with pytest.raises(contract.ContractError, match="absolute or"):
        contract.validate_plan_source(value)


@pytest.mark.parametrize(
    ("severities", "expected_score", "expected_advisory"),
    [
        (["LOW", "LOW"], 96, True),
        (["MEDIUM"], 95, True),
        (["LOW", "LOW", "LOW"], 94, False),
        ([], 100, False),
    ],
)
def test_advisory_boundary_and_clean_review(
    severities: list[str], expected_score: int, expected_advisory: bool
) -> None:
    findings = [
        contract.Finding(f"F-{index}", contract.SHOULD_FIX, severity)
        for index, severity in enumerate(severities, start=1)
    ]
    score = contract.score_findings(findings)
    status = contract.review_status(score, findings)
    report = "\n".join(
        ["### Must Fix", "None.", "### Should Fix"]
        + [
            f"#### [F-{index}] [{severity}] Finding {index}"
            for index, severity in enumerate(severities, start=1)
        ]
        + ["### Latent Findings", "None."]
    )
    assert score == expected_score
    assert (
        contract.advisory_completion(score, status, contract.open_findings(report))
        is expected_advisory
    )


def test_open_findings_preserve_report_order_including_latent() -> None:
    report = """### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] First current finding

#### [F-2] [LOW] Second current finding

### Latent Findings

#### [F-3] [HIGH] Future failure

### Plan Notes

#### This is a plan note

### Score Breakdown

| [F-5] LOW | -2 |
"""
    findings = contract.open_findings(report)
    assert findings == [
        {
            "id": "F-1",
            "severity": "MEDIUM",
            "section": contract.SHOULD_FIX,
            "title": "First current finding",
        },
        {
            "id": "F-2",
            "severity": "LOW",
            "section": contract.SHOULD_FIX,
            "title": "Second current finding",
        },
        {
            "id": "F-3",
            "severity": "HIGH",
            "section": contract.LATENT,
            "title": "Future failure",
        },
    ]
    assert contract.advisory_completion(95, "passing", findings)


def test_advisory_rejects_open_must_fix_even_at_95() -> None:
    report = (
        "### Must Fix\n\n#### [F-1] [LOW] Blocking finding\n\n"
        "### Should Fix\n\nNone.\n\n### Latent Findings\n\nNone.\n"
    )
    assert not contract.advisory_completion(
        98, "passing", contract.open_findings(report)
    )


@pytest.mark.parametrize(
    ("score", "heading", "finding_headings", "cycle"),
    [
        (96, "96/100 — Passing", ["[F-1] [LOW] First", "[F-2] [LOW] Second"], 1),
        (95, "95/100 — Passing", ["[F-1] [MEDIUM] One"], 7),
    ],
)
def test_advisory_outcome_builds_exact_later_cycle_terminal_payload(
    score: int, heading: str, finding_headings: list[str], cycle: int
) -> None:
    report = "\n".join(
        [
            f"### Quality Score: {heading}",
            "",
            "### Evidence",
            "",
            "### Must Fix",
            "",
            "None.",
            "",
            "### Should Fix",
            "",
            *[f"#### {finding}" for finding in finding_headings],
            "",
            "### Latent Findings",
            "",
            "None.",
            "",
            score_breakdown(
                [
                    finding.split("[", 2)[2].split("]", 1)[0]
                    for finding in finding_headings
                ],
                score,
            ),
        ]
    )
    outcome = contract.resolve_review_outcome(
        report, score=score, status="passing", reviewed_sha="abc1234"
    )
    signal = contract.completion_signal(
        outcome,
        cycle=cycle,
        review_url="https://example.test/review/1",
        post_succeeded=True,
    )
    assert signal == {
        "signal": "REVIEW_COMPLETE_WITH_FINDINGS",
        "cycle": cycle,
        "details": {
            "score": score,
            "status": "passing",
            "review_url": "https://example.test/review/1",
            "reviewed_sha": "abc1234",
            "open_findings": [
                *[
                    {
                        "id": heading.split("]", 1)[0][1:],
                        "severity": heading.split("[", 2)[2].split("]", 1)[0],
                        "section": contract.SHOULD_FIX,
                        "title": heading.split("] ", 2)[2],
                    }
                    for heading in finding_headings
                ],
            ],
        },
    }


def test_failed_post_aborts_before_advisory_completion() -> None:
    report = """### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] One finding

### Latent Findings

None.

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| [F-1] MEDIUM | −5 |
| **Final score** | **95/100** |
"""
    outcome = contract.resolve_review_outcome(
        report, score=95, status="passing", reviewed_sha="abc1234"
    )
    assert contract.completion_signal(
        outcome,
        cycle=4,
        review_url=None,
        post_succeeded=False,
    ) == {
        "signal": "ABORT",
        "cycle": 4,
        "details": {
            "reason": "post_failed",
            "message": "The review comment was not posted.",
            "score": 95,
            "review_url": None,
        },
    }


def test_resolve_and_signal_command_boundaries_preserve_the_reviewed_sha(
    tmp_path: Path,
) -> None:
    report_file = tmp_path / "report.md"
    outcome_file = tmp_path / "outcome.json"
    signal_file = tmp_path / "signal.json"
    report_file.write_text(
        """### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] One finding

### Latent Findings

None.

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| [F-1] MEDIUM | −5 |
| **Final score** | **95/100** |
""",
        encoding="utf-8",
    )
    script = SCRIPTS_DIR / "review_contract.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "resolve",
            "--report-file",
            str(report_file),
            "--score",
            "95",
            "--status",
            "passing",
            "--reviewed-sha",
            "abc1234",
            "--output",
            str(outcome_file),
        ],
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            str(script),
            "signal",
            "--outcome-file",
            str(outcome_file),
            "--cycle",
            "8",
            "--review-url",
            "https://example.test/review/8",
            "--output",
            str(signal_file),
        ],
        check=True,
    )

    outcome = json.loads(outcome_file.read_text(encoding="utf-8"))
    signal = json.loads(signal_file.read_text(encoding="utf-8"))
    assert outcome["reviewed_sha"] == "abc1234"
    assert signal["details"]["reviewed_sha"] == outcome["reviewed_sha"]


def test_resolve_command_rejects_an_invalid_report_without_an_artifact(
    tmp_path: Path,
) -> None:
    report_file = tmp_path / "invalid-report.md"
    output_file = tmp_path / "outcome.json"
    report_file.write_text("### Evidence\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "review_contract.py"),
            "resolve",
            "--report-file",
            str(report_file),
            "--score",
            "95",
            "--status",
            "passing",
            "--reviewed-sha",
            "abc1234",
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "exactly one Quality Score heading" in result.stderr
    assert not output_file.exists()


@pytest.mark.parametrize(
    "outcome_text", [None, "{not json\n"], ids=["missing", "malformed"]
)
def test_signal_command_rejects_an_unreadable_outcome_without_an_artifact(
    tmp_path: Path, outcome_text: str | None
) -> None:
    outcome_file = tmp_path / "outcome.json"
    output_file = tmp_path / "signal.json"
    if outcome_text is not None:
        outcome_file.write_text(outcome_text, encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "review_contract.py"),
            "signal",
            "--outcome-file",
            str(outcome_file),
            "--cycle",
            "3",
            "--review-url",
            "https://example.test/review/3",
            "--output",
            str(output_file),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error: Failed to read resolved outcome" in result.stderr
    assert not output_file.exists()


def test_resolve_command_rejects_an_unwritable_output(tmp_path: Path) -> None:
    report_file = tmp_path / "report.md"
    output_directory = tmp_path / "outcome.json"
    report_file.write_text(
        """### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] One finding

### Latent Findings

None.
""",
        encoding="utf-8",
    )
    output_directory.mkdir()

    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPTS_DIR / "review_contract.py"),
            "resolve",
            "--report-file",
            str(report_file),
            "--score",
            "95",
            "--status",
            "passing",
            "--reviewed-sha",
            "abc1234",
            "--output",
            str(output_directory),
        ],
        capture_output=True,
        text=True,
    )

    assert result.returncode == 1
    assert "Error:" in result.stderr
    assert output_directory.is_dir()


def test_signal_command_has_no_independent_reviewed_sha_input() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS_DIR / "review_contract.py"), "signal", "--help"],
        check=True,
        capture_output=True,
        text=True,
    )
    signal_help = result.stdout
    assert "--reviewed-sha" not in signal_help


@pytest.mark.parametrize(
    ("severities", "score", "cycle", "post_failed", "expected_signal"),
    [
        (["LOW", "LOW"], 96, 1, False, "REVIEW_COMPLETE_WITH_FINDINGS"),
        (["MEDIUM"], 95, 7, False, "REVIEW_COMPLETE_WITH_FINDINGS"),
        (["LOW", "LOW", "LOW"], 94, 3, False, None),
        (["MEDIUM"], 95, 8, True, "ABORT"),
    ],
)
def test_outcome_commands_route_the_exact_posted_review(
    tmp_path: Path,
    severities: list[str],
    score: int,
    cycle: int,
    post_failed: bool,
    expected_signal: str | None,
) -> None:
    report_file = tmp_path / "report.md"
    outcome_file = tmp_path / "outcome.json"
    signal_file = tmp_path / "signal.json"
    findings = [
        f"#### [F-{index}] [{severity}] Finding {index}"
        for index, severity in enumerate(severities, start=1)
    ]
    report_file.write_text(
        "\n".join(
            [
                f"### Quality Score: {score}/100 — Passing",
                "### Evidence",
                "### Must Fix",
                "None.",
                "### Should Fix",
                *findings,
                "### Latent Findings",
                "None.",
                score_breakdown(severities, score),
            ]
        ),
        encoding="utf-8",
    )
    script = SCRIPTS_DIR / "review_contract.py"
    subprocess.run(
        [
            sys.executable,
            str(script),
            "resolve",
            "--report-file",
            str(report_file),
            "--score",
            str(score),
            "--status",
            "passing",
            "--reviewed-sha",
            "abc1234",
            "--output",
            str(outcome_file),
        ],
        check=True,
    )
    signal_command = [
        sys.executable,
        str(script),
        "signal",
        "--outcome-file",
        str(outcome_file),
        "--cycle",
        str(cycle),
        "--output",
        str(signal_file),
    ]
    if post_failed:
        signal_command.append("--post-failed")
    else:
        signal_command.extend(["--review-url", "https://example.test/review/7"])
    subprocess.run(signal_command, check=True)
    outcome = json.loads(outcome_file.read_text(encoding="utf-8"))
    signal = json.loads(signal_file.read_text(encoding="utf-8"))
    assert outcome["reviewed_sha"] == "abc1234"
    assert [finding["id"] for finding in outcome["findings"]] == [
        f"F-{number}" for number in range(1, len(severities) + 1)
    ]
    if expected_signal is None:
        assert signal is None
        return
    assert signal["signal"] == expected_signal
    assert signal["cycle"] == cycle
    assert signal["details"]["score"] == score
    if post_failed:
        assert signal["details"]["reason"] == "post_failed"
        assert signal["details"]["review_url"] is None
    else:
        assert signal["details"]["status"] == "passing"
        assert signal["details"]["review_url"] == "https://example.test/review/7"
        assert signal["details"]["reviewed_sha"] == outcome["reviewed_sha"]
        assert signal["details"]["open_findings"] == outcome["findings"]


def test_report_parser_ignores_fenced_findings_but_rejects_forged_score() -> None:
    report = """### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] Actual finding

### Latent Findings

None.

```markdown
#### [F-2] [HIGH] Example only
```

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| [F-1] MEDIUM | −5 |
| **Final score** | **95/100** |
"""
    outcome = contract.resolve_review_outcome(
        report, score=95, status="passing", reviewed_sha="abc1234"
    )
    assert [finding["id"] for finding in outcome.findings] == ["F-1"]
    with pytest.raises(contract.ContractError, match="deductions"):
        contract.resolve_review_outcome(
            report.replace("95/100", "96/100"),
            score=96,
            status="passing",
            reviewed_sha="abc1234",
        )


def test_advisory_payload_includes_accompanying_latent_finding() -> None:
    report = """### Quality Score: 96/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [LOW] Current finding

### Latent Findings

#### [F-2] [LOW] Latent companion

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| [F-1] LOW | −2 |
| [F-2] LOW | −2 |
| **Final score** | **96/100** |
"""
    outcome = contract.resolve_review_outcome(
        report, score=96, status="passing", reviewed_sha="abc1234"
    )
    signal = contract.completion_signal(
        outcome,
        cycle=9,
        review_url="https://example.test/review/9",
        post_succeeded=True,
    )
    assert signal is not None
    assert [finding["section"] for finding in signal["details"]["open_findings"]] == [
        contract.SHOULD_FIX,
        contract.LATENT,
    ]


def test_report_requires_exact_finding_sections_and_ids() -> None:
    report = """### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] Current finding

### Latent Findings

None.

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| [F-1] MEDIUM | −5 |
| **Final score** | **95/100** |
"""
    with pytest.raises(contract.ContractError, match="Finding sections"):
        contract.resolve_review_outcome(
            report.replace("### Latent Findings", "### Future Findings"),
            score=95,
            status="passing",
            reviewed_sha="abc1234",
        )
    with pytest.raises(contract.ContractError, match="sequential"):
        contract.resolve_review_outcome(
            report.replace("[F-1]", "[F-2]"),
            score=95,
            status="passing",
            reviewed_sha="abc1234",
        )


@pytest.mark.parametrize(
    "contradiction",
    [
        "| F-1 | -2 |",
        "| F-1 | -5 |\n| **Final score** | **98/100** |",
    ],
)
def test_report_rejects_a_contradictory_score_breakdown(contradiction: str) -> None:
    report = """### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] Current finding

### Latent Findings

None.

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| F-1 | -5 |
| **Final score** | **95/100** |
"""
    breakdown = "| F-1 | -5 |\n| **Final score** | **95/100** |"
    with pytest.raises(contract.ContractError, match="Score Breakdown"):
        contract.resolve_review_outcome(
            report.replace(breakdown, contradiction),
            score=95,
            status="passing",
            reviewed_sha="abc1234",
        )


@pytest.mark.parametrize(
    ("notes", "plan_rows", "valid"),
    [
        ("None.", "", True),
        ("#### Note A", "| Plan notes (1) | 0 |\n", True),
        ("#### Note A\n\n#### Note B", "| Plan notes (2) | 0 |\n", True),
        ("None.", "| Plan notes (999) | 0 |\n", False),
        ("None.", "| Plan notes (0) | 0 |\n", False),
        ("#### Note A", "", False),
        ("#### Note A", "| Plan notes (2) | 0 |\n", False),
        ("#### Note A", "| Plan notes (1) | 0 |\n| Plan notes (1) | 0 |\n", False),
    ],
)
def test_plan_note_rows_match_report_entries(
    notes: str, plan_rows: str, valid: bool
) -> None:
    report = f"""### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] Current finding

### Latent Findings

None.

### Plan Notes

{notes}

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| F-1 | -5 |
{plan_rows}| **Final score** | **95/100** |
"""
    if valid:
        contract.resolve_review_outcome(
            report, score=95, status="passing", reviewed_sha="abc1234"
        )
    else:
        with pytest.raises(contract.ContractError, match="plan-note count"):
            contract.resolve_review_outcome(
                report, score=95, status="passing", reviewed_sha="abc1234"
            )


@pytest.mark.parametrize(
    "trailing_row",
    ["| F-1 | -5 |", "| Plan notes (1) | 0 |"],
)
def test_score_breakdown_final_row_must_be_last(trailing_row: str) -> None:
    report = f"""### Quality Score: 95/100 — Passing

### Evidence

### Must Fix

None.

### Should Fix

#### [F-1] [MEDIUM] Current finding

### Latent Findings

None.

### Plan Notes

#### Note A

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| F-1 | -5 |
| Plan notes (1) | 0 |
| **Final score** | **95/100** |
{trailing_row}
"""
    with pytest.raises(contract.ContractError, match="must end with the final score"):
        contract.resolve_review_outcome(
            report, score=95, status="passing", reviewed_sha="abc1234"
        )


def test_deserialization_uses_the_authoritative_status_policy(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    finding = {
        "id": "F-1",
        "severity": "LOW",
        "section": contract.SHOULD_FIX,
        "title": "Current finding",
    }
    monkeypatch.setattr(
        contract,
        "review_status",
        lambda score, findings: contract.STATUS_CLEAN,
    )
    payload = {
        "schema_version": contract.OUTCOME_SCHEMA_VERSION,
        "score": 98,
        "status": contract.STATUS_CLEAN,
        "reviewed_sha": "abc1234",
        "findings": [finding],
        "advisory": False,
        "summary": contract.outcome_summary(98, contract.STATUS_CLEAN, False),
    }

    outcome = contract.deserialize_outcome(payload)

    assert outcome.status == contract.STATUS_CLEAN


@pytest.mark.parametrize(
    "heading",
    [
        "#### [F-x] [LOW] Bad identifier",
        "#### [F-1] [INFO] Bad severity",
        "#### [F-1] Missing severity",
        "####[F-1] [LOW] Missing heading space",
    ],
)
def test_open_findings_reject_malformed_governed_headings(heading: str) -> None:
    with pytest.raises(contract.ContractError, match="Malformed finding heading"):
        contract.open_findings(
            f"### Must Fix\n\nNone.\n\n### Should Fix\n\n{heading}\n\n"
            "### Latent Findings\n\nNone.\n"
        )


def test_open_findings_reject_duplicate_ids_across_governed_sections() -> None:
    report = """### Must Fix

None.

### Should Fix

#### [F-1] [LOW] First

### Latent Findings

#### [F-1] [MEDIUM] Duplicate
"""
    with pytest.raises(contract.ContractError, match="unique and sequential"):
        contract.open_findings(report)


def test_posted_advisory_branch_precedes_the_fixer() -> None:
    skill = SKILL_FILE.read_text(encoding="utf-8")
    assert "Delegate all six roles" in skill
    assert "Only the three reviewers run as one parallel batch" in skill
    branch = skill.split("9. **Branch on the resolved outcome.**", 1)[1].split(
        "## Budget", 1
    )[0]
    assert branch.index("`REVIEW_COMPLETE_WITH_FINDINGS`") < branch.index(
        "`references/fix-workflow.md`"
    )
    assert "Do not invoke the fixer" in branch
    assert "review_contract.py signal" in branch
    assert "validated findings" in branch
    assert "outcome-file" in branch
    assert "`post_failed`" in skill
    assert "`score`, `status`, `review_url`, `reviewed_sha`, `open_findings`" in skill

    poster = POSTER_AGENT.read_text(encoding="utf-8")
    assert "The caller will disposition the open findings" in poster
    assert "keep metadata status `passing`" in poster


def test_a_repository_relative_plan_path_is_accepted() -> None:
    assert contract.validate_plan_source("supplied: .plan/feature.md")
    assert contract.validate_plan_source("supplied: the linked issue body")
    assert contract.validate_plan_source("none") == "none"


@pytest.mark.parametrize(
    ("status", "score", "ok"),
    [
        ("failing", 84, True),
        ("passing", 85, True),
        ("clean", 95, True),
        ("clean", 94, False),
        ("passing", 84, False),
        ("failing", 85, False),
    ],
)
def test_the_status_band_follows_the_score(status: str, score: int, ok: bool) -> None:
    if ok:
        contract.validate_status_band(status, score)
        return
    with pytest.raises(contract.ContractError):
        contract.validate_status_band(status, score)
