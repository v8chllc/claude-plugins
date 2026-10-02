import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
ALLOWED_AGENT_COLORS = {"blue", "cyan", "green", "yellow", "magenta", "red"}
ALLOWED_AGENT_EFFORTS = {"low", "medium", "high", "max"}


def load_json(path: Path) -> dict[str, object]:
    data: dict[str, object] = json.loads(path.read_text(encoding="utf-8"))
    return data


def parse_frontmatter(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    raw_header = text.split("---", 2)[1]
    header: dict[str, Any] = {}
    for raw_line in raw_header.splitlines():
        if not raw_line or ":" not in raw_line:
            continue
        key, raw_value = raw_line.split(":", 1)
        value = raw_value.strip()
        if value.startswith("["):
            header[key] = json.loads(value)
        else:
            header[key] = value
    return header


def test_marketplace_points_to_valid_plugin_manifest() -> None:
    marketplace = load_json(MARKETPLACE_PATH)

    assert marketplace["name"] == "v8ch"
    plugins = marketplace["plugins"]
    assert isinstance(plugins, list)
    assert len(plugins) == 1

    entry = plugins[0]
    assert entry["name"] == "v8ch"
    assert entry["source"] == "./plugins/v8ch"

    plugin_root = (REPO_ROOT / entry["source"]).resolve()
    assert plugin_root.is_dir()
    assert plugin_root.is_relative_to(REPO_ROOT.resolve())

    manifest = load_json(plugin_root / ".claude-plugin" / "plugin.json")
    assert manifest["name"] == entry["name"]
    assert manifest["version"] == "2.0.3"
    assert manifest["description"]


def test_plugin_manifest_uses_default_component_discovery() -> None:
    manifest_path = REPO_ROOT / "plugins" / "v8ch" / ".claude-plugin" / "plugin.json"
    manifest = load_json(manifest_path)
    plugin_root = manifest_path.parent.parent

    assert "skills" not in manifest
    assert "agents" not in manifest
    assert (plugin_root / "skills").is_dir()
    assert (plugin_root / "agents").is_dir()


def test_all_plugin_skills_have_metadata() -> None:
    skill_root = REPO_ROOT / "plugins" / "v8ch" / "skills"
    skill_files = sorted(skill_root.glob("*/SKILL.md"))
    assert {path.parent.name for path in skill_files} == {
        "consensus-review",
        "recommend",
        "remember",
    }

    for skill_file in skill_files:
        text = skill_file.read_text(encoding="utf-8")
        assert text.startswith("---\n")
        header = text.split("---", 2)[1]
        assert "\nname:" in f"\n{header}"
        assert "\ndescription:" in f"\n{header}"


def test_plugin_agents_use_claude_plugin_frontmatter() -> None:
    agent_root = REPO_ROOT / "plugins" / "v8ch" / "agents"
    agent_files = sorted(agent_root.glob("*.md"))
    assert {path.stem for path in agent_files} == {
        "architecture-reviewer",
        "consensus-review-fixer",
        "consensus-review-poster",
        "correctness-reviewer",
        "review-synthesizer",
        "standards-reviewer",
    }

    for agent_file in agent_files:
        frontmatter = parse_frontmatter(agent_file)
        assert frontmatter["name"] == agent_file.stem
        assert frontmatter["description"]
        assert frontmatter["model"] in {"inherit", "sonnet", "opus", "haiku"}
        assert frontmatter["color"] in ALLOWED_AGENT_COLORS
        assert isinstance(frontmatter["tools"], list)
        assert all(isinstance(tool, str) and tool for tool in frontmatter["tools"])
        if "effort" in frontmatter:
            assert frontmatter["effort"] in ALLOWED_AGENT_EFFORTS


def test_consensus_review_reviewers_are_read_only_and_run_at_medium_effort() -> None:
    """The three reviewers ship with the plugin; none is generated per workspace."""
    agent_root = REPO_ROOT / "plugins" / "v8ch" / "agents"
    read_only = {"Read", "Grep", "Glob"}

    for name in ("standards-reviewer", "correctness-reviewer", "architecture-reviewer"):
        frontmatter = parse_frontmatter(agent_root / f"{name}.md")
        assert frontmatter["model"] == "opus"
        assert frontmatter["effort"] == "medium"
        tools = set(frontmatter["tools"])
        assert read_only <= tools
        # Only the standards reviewer runs the repository's lint and type checks.
        assert ("Bash" in tools) == (name == "standards-reviewer")
        assert not tools & {"Edit", "Write", "NotebookEdit"}


def test_removed_consensus_review_assets_are_gone() -> None:
    plugin_root = REPO_ROOT / "plugins" / "v8ch"
    skill_dir = plugin_root / "skills" / "consensus-review"

    assert not (plugin_root / "skills" / "meta-consensus-review-agents").exists()
    assert not (plugin_root / "agents" / "acceptance-recommender.md").exists()
    assert not (plugin_root / "agents" / "opt-in-recommender.md").exists()
    assert not (skill_dir / "skip-files.md").exists()
    assert sorted(path.name for path in (skill_dir / "templates").iterdir()) == [
        "review-comment.md.tmpl"
    ]


def test_consensus_review_skill_is_standalone_and_always_autonomous() -> None:
    skill_text = (
        REPO_ROOT / "plugins/v8ch/skills/consensus-review/SKILL.md"
    ).read_text(encoding="utf-8")

    assert "always autonomous" in skill_text
    assert "AUTONOMOUS=" not in skill_text
    assert "MAX_AUTONOMOUS_CYCLES" not in skill_text
    assert "Mode detection" not in skill_text
    assert "Interactive branch" not in skill_text
    assert "on_quality_failure" not in skill_text
    assert "Ask the user" not in skill_text
    assert "v8ch:standards-reviewer" in skill_text
    assert "${CLAUDE_SKILL_DIR}/scripts/recover_context.py" in skill_text
    assert "MAX_REVIEWS_REACHED" in skill_text
    assert "meta-consensus-review-agents" not in skill_text


def test_remember_skill_uses_manual_load_and_explicit_setup() -> None:
    skill_dir = REPO_ROOT / "plugins" / "v8ch" / "skills" / "remember"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    assert "Workflow A: Manual Load / Status" in skill_text
    assert "Workflow B: Setup" in skill_text
    assert "`/remember setup`" in skill_text
    assert "Do not create files." in skill_text
    assert "do not inject a memory-load directive" in skill_text
    assert "exactly matches the reference content" in skill_text
    assert "Inject `references/claude-md-directive.md`" not in skill_text


def test_remember_manual_load_selects_the_latest_dated_journal() -> None:
    skill_dir = REPO_ROOT / "plugins" / "v8ch" / "skills" / "remember"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    assert "select the most recent one by date" in skill_text
    assert "Ignore non-dated files." in skill_text
    assert "not limited to today or yesterday" in skill_text
    assert "no dated daily journal exists" in " ".join(skill_text.split())


def test_remember_documents_opt_in_lifecycle_capture() -> None:
    skill_dir = REPO_ROOT / "plugins" / "v8ch" / "skills" / "remember"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")

    assert "/remember hook enable stop-capture" in skill_text
    assert "/remember hook enable session-end-capture" in skill_text
    assert ".claude/settings.json" in skill_text
    assert "session_id" in skill_text
    assert "last_assistant_message" in skill_text
    assert "default-disabled" in skill_text
    assert "scripts/hook_setup.py" in skill_text
    assert "scripts/lifecycle_segments.py" in skill_text
    assert "${CLAUDE_SKILL_DIR}" in skill_text


def test_remember_lifecycle_workflow_uses_xml_prompt_sections() -> None:
    skill_dir = REPO_ROOT / "plugins" / "v8ch" / "skills" / "remember"
    skill_text = (skill_dir / "SKILL.md").read_text(encoding="utf-8")
    workflow = skill_text.split("## Workflow E1:")[1].split("## Workflow F:")[0]

    for section in ("instructions", "context", "constraints", "output_contract"):
        assert f"<{section}>" in workflow
        assert f"</{section}>" in workflow
