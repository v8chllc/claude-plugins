"""Pin the shipped procedures and their authority and identity boundaries."""

from pathlib import Path

SKILL = (
    Path(__file__).resolve().parents[1]
    / "plugins/v8ch/skills/post-merge-review/SKILL.md"
)


def text() -> str:
    return SKILL.read_text(encoding="utf-8")


def test_metadata_and_named_procedures() -> None:
    skill = text()
    assert "\nname: post-merge-review\n" in skill
    assert "GitHub" in skill.split("---")[1]
    assert "GitLab" in skill.split("---")[1]
    assert "## Review run\n" in skill
    assert "## Triage run\n" in skill


def test_review_role_wiring_and_unchanged_evidence_gate() -> None:
    review = text().split("## Review run\n")[1].split("## Shared report\n")[0]
    for role in (
        "standards-reviewer",
        "correctness-reviewer",
        "architecture-reviewer",
        "review-synthesizer",
    ):
        assert f"v8ch:{role}" in review
    for phrase in (
        "${CLAUDE_SKILL_DIR}",
        "absolute skill directory",
        "Files examined",
        "Commands run",
        "EVIDENCE_FAILED",
        "failed_passes",
        "parallel-subagents",
        "sequential-fallback",
        "No poster or fixer runs",
        "unchanged",
        "posts nothing and changes nothing",
        "snapshot",
    ):
        assert phrase in review
    assert "format --metadata" in review
    assert "report_contract.py validate" in review


def test_terminal_signal_contract() -> None:
    signals = text().split("## Review terminal signals\n")[1]
    for token in (
        "post-merge-review-signal",
        "REVIEW_COMPLETE",
        "score",
        "status",
        "reference",
        "merge_commit",
        "NO_DIFF",
        "EVIDENCE_FAILED",
        "failed_passes",
        "ABORT",
        "reason",
        "message",
        "not_merged",
        "merge_commit_mismatch",
        "diff_mismatch",
        "platform_auth",
        "command_failed",
        "exactly one fenced block",
        "nothing after it",
        "null",
    ):
        assert token in signals


def test_triage_is_read_only_vetted_and_checkpointed() -> None:
    triage = text().split("## Triage run\n")[1].split("## Review terminal signals\n")[0]
    for phrase in (
        "validate <report>",
        "Invalid input stops",
        "merge commit",
        "report order",
        "reported",
        "severity",
        "Urgent follow-up",
        "Routine follow-up",
        "Optional follow-up",
        "No action",
        "never raises",
        "read-only",
        "never creates a tracker",
        "Stop for sponsor approval after each drafted follow-up",
        "no switch that disables vetting or severity alignment",
        "Noted",
        "Plan Notes",
        "receive no disposition",
        "never learns where follow-ups are filed",
    ):
        assert phrase in triage
    assert "`### Must Fix` starts at\n   `Urgent follow-up`" in triage
    assert "`### Should Fix` starts at `Routine follow-up`" in triage


def test_every_fresh_role_receives_post_merge_authority_context() -> None:
    text = " ".join(SKILL.read_text().split())
    reviewers = text.split("3. **Delegate independent reviews.**")[1].split(
        "4. **Apply the evidence gate unchanged.**"
    )[0]
    for restriction in (
        "Append the following invocation-specific context after each unchanged prompt",
        "every initial, fallback and retry invocation",
        "actual prepared repository root, merge SHA, absolute reserved run directory",
        "caller-prepared compatible dependencies and safe selected-check environment",
        "explicit workspace/database-reuse authorization and its limits",
        "generic role directions to install dependencies or write external scratch "
        "are narrowed",
        "do not install tools/dependencies",
        "Do not let a check bootstrap missing dependencies",
        "Leave unprepared or unsafe checks unrun",
        "Existing evidence-gate requirements still apply",
        "only in the supplied ignored run directory",
        "role-prefixed names",
        "`check <relative-output-path>`",
        "create the file exclusively",
        "No outside scratch writes",
        "private-backup changes",
    ):
        assert restriction in reviewers
    synthesizer = text.split("5. **Synthesize once evidence passes.**")[1].split(
        "6. **Format, validate and return.**"
    )[0]
    assert "Append the complete invocation-specific context from step 3" in synthesizer
    assert "every synthesis retry" in synthesizer
    assert "fresh context must receive these limits explicitly" in synthesizer
    assert "The synthesizer alone decides score and status" in synthesizer
