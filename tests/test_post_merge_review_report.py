"""Exercise the canonical report through its formatter and strict consumer."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "plugins/v8ch/skills/post-merge-review/scripts/report_contract.py"
FIXTURE = ROOT / "tests/fixtures/post-merge-review/report.md"
spec = importlib.util.spec_from_file_location("post_merge_report", SCRIPT)
assert spec and spec.loader
contract = importlib.util.module_from_spec(spec)
spec.loader.exec_module(contract)


def parts():
    report = FIXTURE.read_text(encoding="utf-8")
    return json.loads(report.splitlines()[1]), report.split("\n\n", 1)[1]


def test_formatter_produces_fixture_without_rewriting_synthesis() -> None:
    metadata, synthesis = parts()
    result = contract.format_report(metadata, synthesis)
    assert result == FIXTURE.read_text(encoding="utf-8")
    assert contract.validate_report(result) == metadata
    assert result.endswith(synthesis)


@pytest.mark.parametrize("key", sorted(contract.KEYS))
def test_missing_and_null_keys_rejected(key: str) -> None:
    metadata, synthesis = parts()
    del metadata[key]
    with pytest.raises(ValueError):
        contract.format_report(metadata, synthesis)
    metadata, synthesis = parts()
    metadata[key] = None
    with pytest.raises(ValueError):
        contract.format_report(metadata, synthesis)


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("extra", 1),
        ("platform", "other"),
        ("reference", "12"),
        ("reference", True),
        ("reference", 0),
        ("merge_commit", "a" * 39),
        ("merge_commit", "A" * 40),
        ("score", 0),
        ("score", 101),
        ("score", True),
        ("score", 84),
        ("status", "clean"),
        ("status", "unknown"),
        ("files_touched", -1),
        ("findings", 2),
        ("findings", True),
        ("target_branch", ""),
        ("scope_basis", "commit-diff"),
        ("schema_version", 2),
        ("type", "review"),
    ],
)
def test_invalid_metadata_rejected(key: str, value: object) -> None:
    metadata, synthesis = parts()
    metadata[key] = value
    with pytest.raises(ValueError):
        contract.format_report(metadata, synthesis)


@pytest.mark.parametrize(
    ("old", "new"),
    [
        ("PR #12", "PR #13"),
        ("PR #12", "MR !12"),
        ("90/100 — Passing", "91/100 — Passing"),
        ("90/100 — Passing", "90/100 — Fully Clean"),
        ("### Plan Notes", "### Latent Findings"),
        ("[F-1] [HIGH]", "[F-1] [INVALID]"),
        ("[F-1] [HIGH]", "[F-2] [HIGH]"),
        ("### Must Fix", "### Other"),
        ("\n", "\r\n"),
    ],
)
def test_invalid_structure_rejected(old: str, new: str) -> None:
    report = FIXTURE.read_text(encoding="utf-8").replace(old, new)
    with pytest.raises(ValueError):
        contract.validate_report(report)


def test_noncanonical_metadata_rejected() -> None:
    lines = FIXTURE.read_text(encoding="utf-8").splitlines(keepends=True)
    lines[1] = json.dumps(json.loads(lines[1]), indent=2) + "\n"
    with pytest.raises(ValueError):
        contract.validate_report("".join(lines))


@pytest.mark.parametrize(
    ("score", "status", "label"),
    [
        (100, "clean", "Fully Clean"),
        (95, "passing", "Passing"),
        (84, "failing", "Failing"),
        (1, "failing", "Failing"),
    ],
)
def test_valid_score_bands_and_gitlab_identity(
    score: int, status: str, label: str
) -> None:
    metadata, synthesis = parts()
    metadata.update(platform="gitlab", score=score, status=status)
    synthesis = synthesis.replace("90/100 — Passing", f"{score}/100 — {label}")
    report = contract.format_report(metadata, synthesis)
    assert "of MR !12" in report
    assert contract.validate_report(report)["platform"] == "gitlab"


def test_cli_format_validate_and_invalid_bytes(tmp_path: Path) -> None:
    metadata, synthesis = parts()
    meta, synth, report = [
        tmp_path / name for name in ("meta.json", "synth.md", "report.md")
    ]
    meta.write_text(json.dumps(metadata))
    synth.write_text(synthesis)
    command = [
        sys.executable,
        str(SCRIPT),
        "format",
        "--metadata",
        str(meta),
        "--synthesis",
        str(synth),
    ]
    result = subprocess.run(command, capture_output=True, check=True)
    report.write_bytes(result.stdout)
    command = [sys.executable, str(SCRIPT), "validate", str(report)]
    result = subprocess.run(command, capture_output=True, check=True)
    assert json.loads(result.stdout) == metadata
    report.write_bytes(b"\xff")
    result = subprocess.run(command, capture_output=True)
    assert result.returncode == 1
    assert b"invalid report" in result.stderr
