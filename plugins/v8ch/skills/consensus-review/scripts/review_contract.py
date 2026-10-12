"""Executable consensus-review v2 contract for the Claude Code plugin.

Holds the scoring rules (C-1) and the audit-metadata schema (C-5) that
``post_review_comment.py`` and ``recover_context.py`` share. Keeping both in one
module is what makes a rendered comment recoverable by the sibling toolchain:
the Codex copy in ``v8chllc/codex-plugins`` is byte-identical to this file apart
from this docstring, which ``parity-manifest.json`` enforces in both
repositories.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 2
COMMENT_MARKER = "consensus-review"
COMMENT_TYPE = "review"
OUTCOME_SCHEMA_VERSION = 1
OUTCOME_KEYS = frozenset(
    {
        "schema_version",
        "score",
        "status",
        "reviewed_sha",
        "findings",
        "advisory",
        "summary",
    }
)

SEVERITIES: tuple[str, ...] = ("CRITICAL", "HIGH", "MEDIUM", "LOW")
SEVERITY_DEDUCTIONS: dict[str, int] = {
    "CRITICAL": 20,
    "HIGH": 10,
    "MEDIUM": 5,
    "LOW": 2,
}

MUST_FIX = "must-fix"
SHOULD_FIX = "should-fix"
LATENT = "latent"
PLAN_NOTE = "plan-note"
SECTIONS: tuple[str, ...] = (MUST_FIX, SHOULD_FIX, LATENT, PLAN_NOTE)
BLOCKING_SECTIONS: frozenset[str] = frozenset({MUST_FIX, SHOULD_FIX})

SCORE_MAX = 100
SCORE_FLOOR = 1
CLEAN_MIN_SCORE = 95
PASSING_MIN_SCORE = 85

STATUS_CLEAN = "clean"
STATUS_PASSING = "passing"
STATUS_FAILING = "failing"
STATUSES: tuple[str, ...] = (STATUS_CLEAN, STATUS_PASSING, STATUS_FAILING)

STATUS_LABELS: dict[str, str] = {
    STATUS_CLEAN: "Fully Clean",
    STATUS_PASSING: "Passing",
    STATUS_FAILING: "Failing",
}

DELEGATION_MODES: tuple[str, ...] = ("parallel-subagents", "sequential-fallback")

NO_PLAN_SOURCE = "none"
SUPPLIED_PLAN_PREFIX = "supplied: "

FULL_DIFF = "full-diff"
DELTA_SINCE_PREFIX = "delta-since:"

METADATA_KEYS: frozenset[str] = frozenset(
    {
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
)
COUNT_KEYS: tuple[str, ...] = ("files_touched", "findings_opened", "findings_closed")

_WINDOWS_DRIVE_RE = re.compile(r"^[A-Za-z]:[\\/]")

SHA_RE = re.compile(r"^[0-9a-f]{7,40}$")
QUALITY_HEADING_RE = re.compile(
    r"^### Quality Score:\s*(\d+)/100 — (Fully Clean|Passing|Failing)$",
    re.MULTILINE,
)
FINDING_HEADING_RE = re.compile(
    r"^#### \[(F-\d+)\] \[(CRITICAL|HIGH|MEDIUM|LOW)\] (.+)$"
)
FINDING_SECTIONS = {
    "### Must Fix": MUST_FIX,
    "### Should Fix": SHOULD_FIX,
    "### Latent Findings": LATENT,
}
METADATA_BLOCK_RE = re.compile(
    rf"<!--\s*{COMMENT_MARKER}\s*(.*?)\s*-->",
    re.DOTALL,
)


class ContractError(ValueError):
    """Raised when a value violates the consensus-review v2 contract."""


@dataclass(frozen=True)
class Finding:
    """One emitted finding, as the synthesizer classified it.

    ``severity`` is required everywhere except Plan Notes, which carry no
    severity tag and never deduct.
    """

    identifier: str
    section: str
    severity: str | None = None

    def __post_init__(self) -> None:
        if self.section not in SECTIONS:
            raise ContractError(
                f"Unknown section '{self.section}'; expected one of "
                f"{', '.join(SECTIONS)}."
            )
        if self.section == PLAN_NOTE:
            if self.severity is not None:
                raise ContractError(
                    f"Plan note '{self.identifier}' must not carry a severity."
                )
            return
        if self.severity not in SEVERITIES:
            raise ContractError(
                f"Finding '{self.identifier}' has severity {self.severity!r}; "
                f"expected one of {', '.join(SEVERITIES)}."
            )


@dataclass(frozen=True)
class ReviewOutcome:
    """One validated report outcome shared by posting and terminal signaling."""

    score: int
    status: str
    reviewed_sha: str
    findings: tuple[dict[str, str], ...]
    advisory: bool
    summary: str


def deduction(finding: Finding) -> int:
    """Return the points a single finding deducts.

    A latent finding deducts at the severity of its would-be failure, so it is
    scored like any other defect. Plan Notes deduct nothing. Reviewer count is
    not an input: a finding raised once deducts exactly what the same finding
    raised three times deducts.
    """
    if finding.section == PLAN_NOTE:
        return 0
    return SEVERITY_DEDUCTIONS[str(finding.severity)]


def score_findings(findings: Iterable[Finding]) -> int:
    """Score a report: start at 100, deduct once per emitted defect, floor at 1."""
    total = SCORE_MAX - sum(deduction(finding) for finding in findings)
    return max(total, SCORE_FLOOR)


def review_status(score: int, findings: Iterable[Finding]) -> str:
    """Return the single status for a score and its findings.

    The three statuses are mutually exclusive: ``clean`` needs both a score of
    95 or more and no open Must Fix or Should Fix finding, so a high score with
    an open blocker is ``passing`` rather than ``clean``.
    """
    if score < PASSING_MIN_SCORE:
        return STATUS_FAILING
    has_blocker = any(finding.section in BLOCKING_SECTIONS for finding in findings)
    if score >= CLEAN_MIN_SCORE and not has_blocker:
        return STATUS_CLEAN
    return STATUS_PASSING


def status_label(status: str) -> str:
    """Return the report heading label for a status."""
    try:
        return STATUS_LABELS[status]
    except KeyError:
        raise ContractError(f"Unknown status '{status}'.") from None


def open_findings(report_text: str) -> list[dict[str, str]]:
    """Strictly read governed findings from a report in report order.

    Every level-four heading inside a governed section is a finding heading.
    Rejecting malformed headings and repeated IDs prevents the durable comment
    and caller-facing terminal payload from describing different finding sets.
    """
    section: str | None = None
    findings: list[dict[str, str]] = []
    identifiers: set[str] = set()
    for line in report_text.splitlines():
        if line.startswith("### "):
            section = FINDING_SECTIONS.get(line.strip())
            continue
        if section is None:
            continue
        if not line.startswith("####"):
            continue
        match = FINDING_HEADING_RE.match(line)
        if not match:
            raise ContractError(
                f"Malformed finding heading in section '{section}': {line!r}."
            )
        identifier, severity, title = match.groups()
        if identifier in identifiers:
            raise ContractError(f"Duplicate finding identifier '{identifier}'.")
        identifiers.add(identifier)
        findings.append(
            {
                "id": identifier,
                "severity": severity,
                "section": section,
                "title": title,
            }
        )
    return findings


def advisory_completion(
    score: int, status: str, findings: Iterable[dict[str, str]]
) -> bool:
    """Return whether a posted review can hand open findings to its caller."""
    if score < CLEAN_MIN_SCORE or status != STATUS_PASSING:
        return False
    sections = [finding["section"] for finding in findings]
    return MUST_FIX not in sections and SHOULD_FIX in sections


def outcome_summary(score: int, status: str, advisory: bool) -> str:
    """Return the canonical first summary bullet for a resolved outcome."""
    if status == STATUS_CLEAN:
        return f"- Review passed with a score of {score}/100. No fixes are required."
    if advisory:
        return (
            f"- Review passed with a score of {score}/100. "
            "The caller will disposition the open findings."
        )
    if status == STATUS_PASSING:
        return (
            f"- Review passed with a score of {score}/100. "
            "A fix cycle will address the open findings."
        )
    return (
        f"- Review failed with a score of {score}/100. Fixes are required before merge."
    )


def resolve_review_outcome(
    report_text: str, *, score: int, status: str, reviewed_sha: str
) -> ReviewOutcome:
    """Resolve and validate the single outcome consumed across boundaries."""
    if status not in STATUSES:
        raise ContractError(
            f"Unknown status '{status}'; expected one of {', '.join(STATUSES)}."
        )
    _require_int(score, key="score", minimum=SCORE_FLOOR, maximum=SCORE_MAX)
    _require_sha(reviewed_sha, key="reviewed_sha")
    validate_status_band(status, score)
    heading = QUALITY_HEADING_RE.search(report_text)
    if not heading:
        raise ContractError(
            "The report needs an exact '### Quality Score: N/100 — <label>' heading."
        )
    report_score = int(heading.group(1))
    report_label = heading.group(2)
    if report_score != score or report_label != status_label(status):
        raise ContractError(
            "The report Quality Score heading contradicts the resolved "
            f"status {status!r} and score {score}."
        )

    findings = tuple(open_findings(report_text))
    has_blocker = any(finding["section"] in BLOCKING_SECTIONS for finding in findings)
    if status == STATUS_CLEAN and has_blocker:
        raise ContractError(
            "A clean review cannot contain Must Fix or Should Fix findings."
        )
    if status == STATUS_PASSING and score >= CLEAN_MIN_SCORE and not has_blocker:
        raise ContractError(
            "A passing review at the clean score threshold needs an open blocker."
        )
    advisory = advisory_completion(score, status, findings)
    summary = outcome_summary(score, status, advisory)
    return ReviewOutcome(score, status, reviewed_sha, findings, advisory, summary)


def serialize_outcome(outcome: ReviewOutcome) -> dict[str, Any]:
    """Return the stable JSON payload used across orchestration boundaries."""
    return {
        "schema_version": OUTCOME_SCHEMA_VERSION,
        "score": outcome.score,
        "status": outcome.status,
        "reviewed_sha": outcome.reviewed_sha,
        "findings": list(outcome.findings),
        "advisory": outcome.advisory,
        "summary": outcome.summary,
    }


def deserialize_outcome(payload: object) -> ReviewOutcome:
    """Validate and reconstruct a resolved outcome artifact."""
    if not isinstance(payload, dict) or set(payload) != OUTCOME_KEYS:
        raise ContractError("Resolved outcome has an invalid key set.")
    if payload["schema_version"] != OUTCOME_SCHEMA_VERSION:
        raise ContractError(
            f"Resolved outcome schema must be {OUTCOME_SCHEMA_VERSION}."
        )
    score = _require_int(
        payload["score"], key="score", minimum=SCORE_FLOOR, maximum=SCORE_MAX
    )
    status = payload["status"]
    if not isinstance(status, str) or status not in STATUSES:
        raise ContractError("Resolved outcome has an invalid status.")
    validate_status_band(status, score)
    reviewed_sha = _require_sha(payload["reviewed_sha"], key="reviewed_sha")
    raw_findings = payload["findings"]
    if not isinstance(raw_findings, list):
        raise ContractError("Resolved outcome findings must be a list.")
    findings: list[dict[str, str]] = []
    identifiers: set[str] = set()
    for raw in raw_findings:
        if not isinstance(raw, dict) or set(raw) != {
            "id",
            "severity",
            "section",
            "title",
        }:
            raise ContractError("Resolved outcome contains an invalid finding.")
        if not all(isinstance(value, str) for value in raw.values()):
            raise ContractError("Resolved outcome finding values must be strings.")
        finding = dict(raw)
        if not re.fullmatch(r"F-\d+", finding["id"]):
            raise ContractError("Resolved outcome contains an invalid finding ID.")
        if finding["id"] in identifiers:
            raise ContractError(f"Duplicate finding identifier '{finding['id']}'.")
        identifiers.add(finding["id"])
        if (
            finding["severity"] not in SEVERITIES
            or finding["section"] not in FINDING_SECTIONS.values()
        ):
            raise ContractError(
                "Resolved outcome contains an invalid finding classification."
            )
        if not finding["title"]:
            raise ContractError("Resolved outcome finding title must not be empty.")
        findings.append(finding)
    advisory = advisory_completion(score, status, findings)
    has_blocker = any(finding["section"] in BLOCKING_SECTIONS for finding in findings)
    if status == STATUS_CLEAN and has_blocker:
        raise ContractError("A clean outcome cannot contain blocking findings.")
    if status == STATUS_PASSING and score >= CLEAN_MIN_SCORE and not has_blocker:
        raise ContractError("A passing outcome at 95 or above needs an open blocker.")
    if payload["advisory"] is not advisory:
        raise ContractError("Resolved outcome advisory flag contradicts its findings.")
    if not isinstance(payload["summary"], str):
        raise ContractError("Resolved outcome summary must be a string.")
    outcome = ReviewOutcome(
        score, status, reviewed_sha, tuple(findings), advisory, payload["summary"]
    )
    if outcome_summary(score, status, advisory) != payload["summary"]:
        raise ContractError("Resolved outcome summary is invalid.")
    return outcome


def read_outcome(path: str | Path) -> ReviewOutcome:
    """Read one resolved outcome artifact from disk."""
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise ContractError(
            f"Failed to read resolved outcome '{path}': {error}"
        ) from error
    return deserialize_outcome(payload)


def write_json(path: str | Path, payload: object) -> None:
    """Write a deterministic JSON artifact."""
    Path(path).write_text(
        json.dumps(payload, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


def completion_signal(
    outcome: ReviewOutcome,
    *,
    cycle: int,
    review_url: str | None,
    post_succeeded: bool,
) -> dict[str, Any] | None:
    """Build the deterministic terminal signal after the posting attempt.

    ``None`` means the validated result requires the fixer. Posting failure has
    precedence over every review outcome and can never produce completion.
    """
    _require_int(cycle, key="cycle", minimum=1, maximum=None)
    if not post_succeeded:
        return {
            "signal": "ABORT",
            "cycle": cycle,
            "details": {
                "reason": "post_failed",
                "message": "The review comment was not posted.",
                "score": outcome.score,
                "review_url": None,
            },
        }
    if not isinstance(review_url, str) or not review_url:
        raise ContractError("A successful post requires a non-empty review URL.")
    if outcome.status == STATUS_CLEAN:
        return {
            "signal": "REVIEW_COMPLETE",
            "cycle": cycle,
            "details": {
                "score": outcome.score,
                "status": outcome.status,
                "review_url": review_url,
            },
        }
    if outcome.advisory:
        return {
            "signal": "REVIEW_COMPLETE_WITH_FINDINGS",
            "cycle": cycle,
            "details": {
                "score": outcome.score,
                "status": outcome.status,
                "review_url": review_url,
                "reviewed_sha": outcome.reviewed_sha,
                "open_findings": list(outcome.findings),
            },
        }
    return None


def _require_int(value: object, *, key: str, minimum: int, maximum: int | None) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ContractError(f"Metadata '{key}' must be an integer, got {value!r}.")
    if value < minimum:
        raise ContractError(f"Metadata '{key}' must be >= {minimum}, got {value}.")
    if maximum is not None and value > maximum:
        raise ContractError(f"Metadata '{key}' must be <= {maximum}, got {value}.")
    return value


def _require_sha(value: object, *, key: str) -> str:
    if not isinstance(value, str) or not SHA_RE.match(value):
        raise ContractError(
            f"Metadata '{key}' must be 7-40 lowercase hex characters, got {value!r}."
        )
    return value


def validate_plan_source(value: object) -> str:
    """Validate the plan-source value shared by the report and the metadata.

    The value is published twice, in the Run Provenance line and in the metadata
    block, and read by people with no checkout of the machine that produced it.
    A path that resolves only there is refused for the same reason findings may
    not cite one.
    """
    if not isinstance(value, str) or not value:
        raise ContractError("Metadata 'plan_source' must be a non-empty string.")
    if value == NO_PLAN_SOURCE:
        return value
    if value.startswith(SUPPLIED_PLAN_PREFIX) and value[len(SUPPLIED_PLAN_PREFIX) :]:
        suffix = value[len(SUPPLIED_PLAN_PREFIX) :].strip()
        if suffix.startswith(("/", "~")) or _WINDOWS_DRIVE_RE.match(suffix):
            raise ContractError(
                "Metadata 'plan_source' must not publish an absolute or "
                f"home-directory path, got {suffix!r}. Cite the plan by its "
                "repository-relative path or by a short description."
            )
        return value
    raise ContractError(
        "Metadata 'plan_source' must be 'none' or "
        f"'{SUPPLIED_PLAN_PREFIX}<path or short description>', got {value!r}."
    )


def validate_scope_basis(value: object) -> str:
    """Validate a scope basis of ``full-diff`` or ``delta-since:<sha>``."""
    if not isinstance(value, str):
        raise ContractError(f"Metadata 'scope_basis' must be a string, got {value!r}.")
    if value == FULL_DIFF:
        return value
    if value.startswith(DELTA_SINCE_PREFIX):
        _require_sha(value[len(DELTA_SINCE_PREFIX) :], key="scope_basis")
        return value
    raise ContractError(
        f"Metadata 'scope_basis' must be '{FULL_DIFF}' or "
        f"'{DELTA_SINCE_PREFIX}<sha>', got {value!r}."
    )


def validate_metadata(payload: object) -> dict[str, Any]:
    """Return the payload when it is a valid schema-v2 review block.

    Raises ``ContractError`` otherwise. Callers that recover history treat any
    error as "ignore this comment"; callers that publish treat it as a failure.
    """
    if not isinstance(payload, dict):
        raise ContractError("Metadata must be a JSON object.")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(
            f"Metadata 'schema_version' must be {SCHEMA_VERSION}, got "
            f"{payload.get('schema_version')!r}."
        )
    keys = set(payload)
    missing = sorted(METADATA_KEYS - keys)
    unexpected = sorted(keys - METADATA_KEYS)
    if missing or unexpected:
        raise ContractError(
            "Metadata key set mismatch"
            + (f"; missing: {', '.join(missing)}" if missing else "")
            + (f"; unexpected: {', '.join(unexpected)}" if unexpected else "")
            + "."
        )
    if payload["type"] != COMMENT_TYPE:
        raise ContractError(
            f"Metadata 'type' must be '{COMMENT_TYPE}', got {payload['type']!r}."
        )
    _require_int(payload["cycle"], key="cycle", minimum=1, maximum=None)
    _require_int(payload["score"], key="score", minimum=SCORE_FLOOR, maximum=SCORE_MAX)
    if payload["status"] not in STATUSES:
        raise ContractError(
            f"Metadata 'status' must be one of {', '.join(STATUSES)}, got "
            f"{payload['status']!r}."
        )
    if payload["delegation_mode"] not in DELEGATION_MODES:
        raise ContractError(
            "Metadata 'delegation_mode' must be one of "
            f"{', '.join(DELEGATION_MODES)}, got {payload['delegation_mode']!r}."
        )
    validate_status_band(payload["status"], payload["score"])
    validate_plan_source(payload["plan_source"])
    _require_sha(payload["reviewed_sha"], key="reviewed_sha")
    validate_scope_basis(payload["scope_basis"])
    for key in COUNT_KEYS:
        _require_int(payload[key], key=key, minimum=0, maximum=None)
    return payload


def validate_status_band(status: str, score: int) -> None:
    """Reject a status the score cannot support.

    ``review_status`` also consults the finding set, which metadata does not
    carry, so only the score bands are checkable here: below the passing
    threshold the status is always ``failing``, at or above it never is, and
    ``clean`` additionally needs the clean threshold. Without this, a caller can
    publish ``clean`` over a report headed 60/100 — the comment would show one
    verdict, the metadata another, and recovery would route on the metadata.
    """
    if score < PASSING_MIN_SCORE and status != STATUS_FAILING:
        raise ContractError(
            f"A score below {PASSING_MIN_SCORE} is '{STATUS_FAILING}', got "
            f"status {status!r} with score {score}."
        )
    if score >= PASSING_MIN_SCORE and status == STATUS_FAILING:
        raise ContractError(
            f"Status '{STATUS_FAILING}' contradicts a score of {score}."
        )
    if status == STATUS_CLEAN and score < CLEAN_MIN_SCORE:
        raise ContractError(
            f"Status '{STATUS_CLEAN}' needs a score of at least "
            f"{CLEAN_MIN_SCORE}, got {score}."
        )


def build_metadata(
    *,
    cycle: int,
    status: str,
    score: int,
    delegation_mode: str,
    plan_source: str,
    reviewed_sha: str,
    scope_basis: str,
    files_touched: int,
    findings_opened: int,
    findings_closed: int,
) -> dict[str, Any]:
    """Build and validate the schema-v2 metadata payload for a review comment."""
    payload: dict[str, Any] = {
        "cycle": cycle,
        "delegation_mode": delegation_mode,
        "files_touched": files_touched,
        "findings_closed": findings_closed,
        "findings_opened": findings_opened,
        "plan_source": plan_source,
        "reviewed_sha": reviewed_sha,
        "schema_version": SCHEMA_VERSION,
        "scope_basis": scope_basis,
        "score": score,
        "status": status,
        "type": COMMENT_TYPE,
    }
    return validate_metadata(payload)


def render_metadata_block(payload: dict[str, Any]) -> str:
    """Render the hidden metadata block that opens every review comment."""
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return f"<!-- {COMMENT_MARKER}\n{encoded}\n-->"


def parse_metadata_block(body: str) -> dict[str, Any] | None:
    """Return the decoded metadata object from a comment body, if it has one.

    Returns the raw object without schema checks so callers can tell a legacy
    v1 comment from a malformed one.
    """
    match = METADATA_BLOCK_RE.search(body)
    if not match:
        return None
    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def is_legacy_review(payload: dict[str, Any]) -> bool:
    """Return True for a schema-v1 review comment kept as legacy history."""
    return payload.get("schema_version") == 1 and payload.get("type") == COMMENT_TYPE


def strip_metadata_block(body: str) -> str:
    """Remove the hidden metadata block from a comment body."""
    return METADATA_BLOCK_RE.sub("", body, count=1).strip()


def build_parser() -> argparse.ArgumentParser:
    """Build the command boundary used by the orchestration prompt."""
    parser = argparse.ArgumentParser(description="Resolve consensus-review outcomes.")
    commands = parser.add_subparsers(dest="command", required=True)

    resolve = commands.add_parser("resolve", help="Write a resolved outcome artifact")
    resolve.add_argument("--report-file", required=True)
    resolve.add_argument("--score", type=int, required=True)
    resolve.add_argument("--status", choices=STATUSES, required=True)
    resolve.add_argument("--reviewed-sha", required=True)
    resolve.add_argument("--output", required=True)

    signal = commands.add_parser("signal", help="Write a terminal signal artifact")
    signal.add_argument("--outcome-file", required=True)
    signal.add_argument("--cycle", type=int, required=True)
    signal.add_argument("--review-url")
    signal.add_argument("--post-failed", action="store_true")
    signal.add_argument("--output", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Resolve an outcome or construct its post-bound terminal signal."""
    args = build_parser().parse_args(argv)
    try:
        if args.command == "resolve":
            report_text = Path(args.report_file).read_text(encoding="utf-8")
            outcome = resolve_review_outcome(
                report_text,
                score=args.score,
                status=args.status,
                reviewed_sha=args.reviewed_sha,
            )
            write_json(args.output, serialize_outcome(outcome))
        else:
            outcome = read_outcome(args.outcome_file)
            signal = completion_signal(
                outcome,
                cycle=args.cycle,
                review_url=args.review_url,
                post_succeeded=not args.post_failed,
            )
            write_json(args.output, signal)
    except (ContractError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
