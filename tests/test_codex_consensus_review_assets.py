import tomllib
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CODEX_ROOT = REPO_ROOT / "codex"
SKILL_DIR = CODEX_ROOT / "skills" / "consensus-review"
AGENT_DIR = CODEX_ROOT / "agents"


def test_codex_consensus_review_skill_assets_exist() -> None:
    assert (SKILL_DIR / "SKILL.md").is_file()
    assert (SKILL_DIR / "agents" / "openai.yaml").is_file()
    assert (SKILL_DIR / "references" / "fix-workflow.md").is_file()
    assert (SKILL_DIR / "scripts" / "post_review_comment.py").is_file()
    assert (SKILL_DIR / "scripts" / "recover_context.py").is_file()
    assert (SKILL_DIR / "templates" / "review-comment.md.tmpl").is_file()


def test_codex_consensus_review_agents_parse_as_toml() -> None:
    agent_paths = sorted(AGENT_DIR.glob("*.toml"))
    agent_names = {path.name for path in agent_paths}
    assert "codebase-scout.toml" in agent_names
    assert "consensus-review-fixer.toml" in agent_names
    assert "consensus-review-poster.toml" in agent_names
    assert "review-synthesizer.toml" in agent_names

    for path in agent_paths:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
        assert data["name"]
        assert data["description"]
        assert data["developer_instructions"]


def test_codex_consensus_review_skill_uses_codex_paths_and_agents() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")
    fix_workflow = (SKILL_DIR / "references" / "fix-workflow.md").read_text(
        encoding="utf-8"
    )

    assert "~/.codex/skills/consensus-review/scripts/recover_context.py" in skill_text
    assert ".codex/agents/" in skill_text
    assert "spawn a Codex subagent" in skill_text
    assert ".claude/agents/" not in skill_text
    assert "plugins/vault/skills/meta-consensus-review-agents" not in skill_text
    assert "PR/MR comments" in skill_text
    assert "consensus-review-fixer" in fix_workflow
    assert "plugins/vault/agents/" not in fix_workflow


def test_codex_consensus_review_skill_documents_pr_comment_audit_artifacts() -> None:
    skill_text = (SKILL_DIR / "SKILL.md").read_text(encoding="utf-8")

    assert "PR/MR comment thread is the durable audit trail" in skill_text
    assert "Do not persist raw reviewer outputs to `.rouge`" in skill_text
    assert "The posted PR/MR comment is the durable review audit artifact" in skill_text
    assert "RECOVERED_CONTEXT" in skill_text
