import json
import sys
from pathlib import Path
from typing import Any

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / "plugins/v8ch/skills/consensus-review/scripts"
FIXTURES_DIR = REPO_ROOT / "tests/fixtures/consensus-review"

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


def test_extract_quality_score_reads_the_report_heading() -> None:
    report = "intro\n\n### Quality Score: 73/100 — Failing\n\nrest\n"
    assert contract.extract_quality_score(report) == 73
    assert contract.extract_quality_score("no heading here") is None


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
