"""The consensus-review evidence gate exists twice: in the skill's step 5 and in
the review synthesizer's step 1. When the copies disagree on one report, the
review has no defined outcome, so each role's outcome is pinned in both."""

import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL = REPO_ROOT / "plugins/v8ch/skills/consensus-review/SKILL.md"
SYNTHESIZER = REPO_ROOT / "plugins/v8ch/agents/review-synthesizer.md"
REVIEWER_AGENTS = REPO_ROOT / "plugins/v8ch/agents"

# Each clause states one role's `Commands run` outcome. Both gates must carry
# every clause verbatim, after whitespace and the `v8ch:` prefix are normalized.
OUTCOME_CLAUSES = [
    "`standards-reviewer` output whose `Commands run` names no command — "
    "`none` in any form, such as `none (read-only review)` — also failed its pass",
    "`Commands run: none` in any form from `correctness-reviewer` or "
    "`architecture-reviewer` is a complete, passing answer",
    "A `correctness-reviewer` or `architecture-reviewer` output whose "
    "`Commands run` names any command failed its pass",
]


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text.replace("v8ch:", ""))


def section(text: str, start: str, end: str) -> str:
    begin = text.index(start)
    return text[begin : text.index(end, begin)]


def skill_gate() -> str:
    text = SKILL.read_text(encoding="utf-8")
    return normalize(section(text, "**Apply the evidence gate.**", "\n6. **"))


def synthesizer_gate() -> str:
    text = SYNTHESIZER.read_text(encoding="utf-8")
    return normalize(section(text, "## Step 1", "\n## Step 2"))


@pytest.mark.parametrize("clause", OUTCOME_CLAUSES)
def test_both_gates_state_the_same_outcome(clause: str) -> None:
    assert clause in skill_gate(), f"SKILL.md step 5 no longer states: {clause}"
    assert clause in synthesizer_gate(), (
        f"review-synthesizer.md step 1 no longer states: {clause}"
    )


def test_the_synthesize_step_handles_a_failed_status() -> None:
    text = normalize(
        section(SKILL.read_text(encoding="utf-8"), "**Synthesize.**", "\n8. **")
    )
    assert "`### Review Status: FAILED`" in text
    assert "A pass that fails a second time, at either gate" in text
    assert "`EVIDENCE_FAILED`" in text


def test_ignored_cache_attribution_matches_reviewer_tool_grants() -> None:
    text = normalize(
        section(
            SKILL.read_text(encoding="utf-8"),
            "**Re-check the working tree.**",
            "\n7. **",
        )
    )
    attribution = (
        "`standards-reviewer` runs the repository's lint, type, and test commands"
    )
    assert attribution in text
    for role in ("standards", "correctness", "architecture"):
        agent = (REVIEWER_AGENTS / f"{role}-reviewer.md").read_text(encoding="utf-8")
        tools = section(agent, "tools: [", "]")
        assert ('"Bash"' in tools) is (role == "standards")
