"""Packaging guards for workflows installed with the Claude v8ch plugin."""

import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PLUGIN = ROOT / "plugins/v8ch"
SKILLS = (
    "agent-tooling-review",
    "change-set-orchestrate",
    "chore-orchestrate",
    "feature-orchestrate",
    "supervise",
)
CONTRACTS = (
    "agent-tooling-review-loop.md",
    "finding-policy.md",
    "profile-template.md",
    "repository-profile.md",
    "run-state.md",
    "status-block.md",
    "verification-base.md",
)


@pytest.mark.parametrize("name", SKILLS)
def test_promoted_skill_metadata(name: str) -> None:
    text = (PLUGIN / "skills" / name / "SKILL.md").read_text()
    assert f"\nname: {name}\n" in text
    assert "\ndescription: " in text


def test_shared_contracts_have_one_plugin_home() -> None:
    folder = PLUGIN / "workflows/contracts"
    assert {p.name for p in folder.iterdir()} == set(CONTRACTS)
    for name in CONTRACTS:
        assert (folder / name).read_text().strip()
        assert not list((PLUGIN / "skills").rglob(name))


@pytest.mark.parametrize("workflow", ("change-set", "chore", "feature"))
def test_orchestrators_invoke_namespaced_role_agents(workflow: str) -> None:
    text = (PLUGIN / f"skills/{workflow}-orchestrate/SKILL.md").read_text()
    roles = (
        ("build", "check", "review")
        if workflow == "chore"
        else ("build", "plan", "review", "verify")
    )
    for role in roles:
        assert f"v8ch:{workflow}-{role}-agent" in text


@pytest.mark.parametrize("skill", (*SKILLS[1:4], "supervise"))
def test_orchestrators_reach_shared_run_state(skill: str) -> None:
    text = (PLUGIN / f"skills/{skill}/SKILL.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/workflows/contracts/run-state.md" in text


def test_promoted_assets_have_no_source_checkout_paths() -> None:
    assets = [p for s in SKILLS for p in (PLUGIN / "skills" / s).rglob("*.md")]
    assets += list((PLUGIN / "workflows/contracts").glob("*.md"))
    assets += [p for p in (PLUGIN / "agents").glob("*-agent.md")]
    assert assets, "no promoted instruction assets inspected"
    forbidden = re.compile(
        r"\.claude/(?:agents|skills)/|\.agents/(?:skills|contracts)/"
        r"|project-management-workspace|workspace root|/Users/"
    )
    for asset in assets:
        assert not forbidden.search(asset.read_text()), asset.relative_to(ROOT)


def test_workflow_release_and_descriptions() -> None:
    manifest = json.loads((PLUGIN / ".claude-plugin/plugin.json").read_text())
    assert tuple(map(int, manifest["version"].split("."))) > (2, 0, 20)
    assert (
        f'"{manifest["version"]}"'
        in (ROOT / "tests/test_claude_marketplace.py").read_text()
    )
    marketplace = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
    assert "orchestrat" in manifest["description"].lower()
    assert "orchestrat" in marketplace["plugins"][0]["description"].lower()


def test_readme_installs_and_lists_promoted_skills() -> None:
    text = (ROOT / "README.md").read_text()
    assert "## Installation\n" in text
    assert "/plugin marketplace add v8chllc/claude-plugins" in text
    assert "/plugin install v8ch@v8ch" in text
    for name in SKILLS:
        assert f"v8ch:{name}" in text


def test_sponsor_judgement_shared_contract() -> None:
    base = (PLUGIN / "workflows/contracts/verification-base.md").read_text()
    for rule in (
        "— sponsor judgement: <question>",
        "separate, check-decided `AC-n` criterion paired with it",
        "state the sponsor must judge is reachable",
        "`pending_sponsor`, never a verifier's `pass`",
        "excluded from the workflow's overall verification result",
        "pre-merge review at the merge-ready head",
        "failed judgement is fixed by a corrective run",
        "verdict is not a regression test; the paired criterion is the lasting guard",
    ):
        assert rule in base
    state = (PLUGIN / "workflows/contracts/run-state.md").read_text()
    assert (
        "include every `pending_sponsor` row with its exact question "
        "in the terminal snapshot"
    ) in state


def test_shared_authorship_and_finding_dispositions() -> None:
    state = (PLUGIN / "workflows/contracts/run-state.md").read_text()
    policy = (PLUGIN / "workflows/contracts/finding-policy.md").read_text()
    assert state.count("## Authorship") == 1
    assert (
        "manager coordinates and records; it never writes review or evidence text"
    ) in state
    assert "A failed post stops the run `BLOCKED`" in state
    assert "`declined` only when a reproduction shows" in policy
    assert "escalated to the sponsor with an `orchestration-decision` marker" in policy
    assert "citation check" not in policy


def test_feature_run_state_preserves_decision_and_result_identity() -> None:
    state = (PLUGIN / "workflows/contracts/run-state.md").read_text()
    assert "## Sponsor decision marker" in state
    assert "<!-- orchestration-decision" in state
    assert '"role":"supervisor"' in state
    assert "supervisor_identifier" in state
    assert "`outcome`" in state and "`result_comment_url`" in state
    assert '"evidence_review":null' not in state


@pytest.mark.parametrize("workflow", ("change-set", "chore", "feature"))
def test_orchestrators_share_status_contract_without_restatement(workflow: str) -> None:
    text = (PLUGIN / f"skills/{workflow}-orchestrate/SKILL.md").read_text()
    assert "${CLAUDE_PLUGIN_ROOT}/workflows/contracts/status-block.md" in text
    assert "skills/supervise/references" not in text
    assert "```manager-status" not in text


def test_kickoff_resolves_shared_paths_from_installed_plugin_root() -> None:
    text = (PLUGIN / "skills/supervise/templates/kickoff.md").read_text()
    assert (
        "`workflows/contracts/status-block.md` from the installed plugin root" in text
    )
    assert "`workflows/contracts/run-state.md`, resolved" in text
    assert (
        "plugin root two directories above the orchestrator’s skill directory" in text
    )
    assert "<SKILL PATH>/workflows/" not in text
    assert "supervise skill's workflows/contracts/" not in text
