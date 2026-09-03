import json
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent
MARKETPLACE_PATH = REPO_ROOT / ".claude-plugin" / "marketplace.json"
ALLOWED_AGENT_COLORS = {"blue", "cyan", "green", "yellow", "magenta", "red"}


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
    assert manifest["version"] == "1.2.1"
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
        "meta-consensus-review-agents",
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
        "acceptance-recommender",
        "consensus-review-fixer",
        "consensus-review-poster",
        "opt-in-recommender",
        "review-synthesizer",
    }

    for agent_file in agent_files:
        frontmatter = parse_frontmatter(agent_file)
        assert frontmatter["name"] == agent_file.stem
        assert frontmatter["description"]
        assert frontmatter["model"] in {"inherit", "sonnet", "opus", "haiku"}
        assert frontmatter["color"] in ALLOWED_AGENT_COLORS
        assert isinstance(frontmatter["tools"], list)
        assert all(isinstance(tool, str) and tool for tool in frontmatter["tools"])


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
