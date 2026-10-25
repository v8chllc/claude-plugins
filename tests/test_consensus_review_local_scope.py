"""Pin the documented local review scope and signals."""

from pathlib import Path

SKILL = (
    Path(__file__).resolve().parents[1]
    / "plugins/v8ch/skills/consensus-review/SKILL.md"
)


def test_local_scope_and_preconditions_follow_the_contract() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    inputs = skill.split("## Inputs\n", 1)[1].split("## Scope ladder\n", 1)[0]
    scope = skill.split("## Scope ladder\n", 1)[1].split("## Cycle scope\n", 1)[0]

    assert "PR/MR number or URL" in inputs
    assert "ignore any other" in inputs
    assert "For a URL, extract its PR/MR\n   number" in scope
    assert "plan file" in inputs
    assert "acceptance criteria and Regression Guards" in inputs
    assert "each identified as that input" in inputs
    assert "review_budget: single_cycle" in inputs
    for argument in ("commit SHA", "branch", "list of paths", "path not identified"):
        assert argument in inputs

    assert "git diff\n      <base> HEAD" in scope
    assert "git merge-base\n      <ref> HEAD" in scope
    assert "origin/HEAD" in scope
    assert "local `main`" in scope
    assert "without fetching" in scope
    assert "uncommitted changes and untracked files" in scope
    checks = (
        "unsupported_scope",
        "git status --porcelain=v1 --untracked-files=all",
        "dirty_worktree",
        "no_base",
        "NO_DIFF",
    )
    assert [scope.index(check) for check in checks] == sorted(
        scope.index(check) for check in checks
    )
    for message in (
        "Name the argument in `message`",
        "current branch's commits since it left the",
        "working tree must be clean, with nothing untracked",
        "commit or",
        "default branch could not be resolved",
        "fetch or set `origin/HEAD`",
    ):
        assert message in scope


def test_local_signals_report_resolved_scope() -> None:
    skill = SKILL.read_text(encoding="utf-8")
    scope = skill.split("## Scope ladder\n", 1)[1].split("## Cycle scope\n", 1)[0]
    signals = skill.split("## Terminal signals\n", 1)[1]

    assert "<ref>@<base-sha>..HEAD@<head-sha>" in scope
    assert "full\n40-character lowercase SHA" in scope
    assert "in the report and in `details.scope`" in scope
    assert "`details.scope` on\nlocal `NO_DIFF` and `REVIEW_COMPLETE`" in scope
    assert "On a PR/MR, `details` is unchanged" in scope
    assert "local only: `scope`" in signals
    assert "local: `<ref>@<base-sha>..HEAD@<head-sha>`" in signals
    for reason in ("unsupported_scope", "dirty_worktree", "no_base"):
        assert reason in signals.split("## Stop rules", 1)[0]
