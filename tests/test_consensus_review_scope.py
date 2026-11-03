"""Pin the PR/MR-only inputs and early unsupported-scope abort."""

from pathlib import Path

SKILL = (
    Path(__file__).resolve().parents[1]
    / "plugins/v8ch/skills/consensus-review/SKILL.md"
)


def test_pr_mr_reference_is_required_and_missing_input_aborts() -> None:
    text = SKILL.read_text(encoding="utf-8")
    inputs = text.split("## Inputs\n")[1].split("## Scope ladder\n")[0]
    assert "**PR/MR reference** (required)" in inputs
    assert "Without one, emit `ABORT`" in inputs
    assert "`reason` `unsupported_scope`" in inputs
    assert "a PR/MR number\n   or URL is required" in inputs
    assert "Do not infer scope from a commit, branch, or paths" in inputs


def test_scope_still_uses_platform_diff_and_checks_head() -> None:
    text = SKILL.read_text(encoding="utf-8")
    scope = text.split("## Scope ladder\n")[1].split("## Cycle scope\n")[0]
    assert "gh pr diff <number>" in scope
    assert "glab mr diff <number>" in scope
    assert "confirm local `HEAD` equals the PR/MR head SHA" in scope
    assert "head_mismatch" in scope
    assert "NO_DIFF" in scope
    assert "Without a PR/MR number" not in text
    signals = text.split("## Terminal signals\n")[1]
    assert "local only:" not in signals
