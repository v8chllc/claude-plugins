"""Parity and portability guards for the consensus-review skill.

The scripts, templates, and fixtures are byte-identical to the Codex copy in
``v8chllc/codex-plugins`` apart from each module's docstring, which names its
toolchain. ``parity-manifest.json`` pins a hash per file over the
docstring-stripped content, so an edit on one side fails here until the other
side moves with it.
"""

import ast
import hashlib
import json
import re
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SKILL_DIR = REPO_ROOT / "plugins/v8ch/skills/consensus-review"
AGENTS_DIR = REPO_ROOT / "plugins/v8ch/agents"
FIXTURES_DIR = REPO_ROOT / "tests/fixtures/consensus-review"
MANIFEST_PATH = SKILL_DIR / "parity-manifest.json"

# A skill or role asset must never name the plugin's own install path: the
# orchestrator passes ${CLAUDE_SKILL_DIR}, and the Codex copy resolves the path
# relative to SKILL.md. A literal path breaks whenever either moves.
HARDCODED_SKILL_PATH_RE = re.compile(r"plugins/v8ch/skills/[^\s`'\"]*/scripts/")

CONSENSUS_REVIEW_AGENTS = (
    "architecture-reviewer",
    "consensus-review-fixer",
    "consensus-review-poster",
    "correctness-reviewer",
    "review-synthesizer",
    "standards-reviewer",
)


def strip_module_docstring(source: str) -> str:
    """Return Python source with its module docstring removed."""
    tree = ast.parse(source)
    body = tree.body
    if not body:
        return source
    first = body[0]
    if not (isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant)):
        return source
    if not isinstance(first.value.value, str):
        return source
    lines = source.splitlines(keepends=True)
    assert first.end_lineno is not None
    del lines[first.lineno - 1 : first.end_lineno]
    return "".join(lines)


def parity_digest(path: Path) -> str:
    """Hash a parity-tracked file, ignoring a Python module docstring."""
    raw = path.read_bytes()
    if path.suffix == ".py":
        raw = strip_module_docstring(raw.decode("utf-8")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def parity_files() -> list[Path]:
    """Return every file the manifest must cover, in a stable order."""
    return sorted(
        [
            *(SKILL_DIR / "scripts").glob("*.py"),
            *(SKILL_DIR / "templates").glob("*.md.tmpl"),
            *FIXTURES_DIR.glob("*.json"),
            *FIXTURES_DIR.glob("*.md"),
        ]
    )


def load_manifest() -> dict[str, str]:
    payload = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    files: dict[str, str] = payload["files"]
    return files


def test_manifest_covers_exactly_the_parity_tracked_files() -> None:
    expected = {str(path.relative_to(REPO_ROOT)) for path in parity_files()}
    assert set(load_manifest()) == expected


@pytest.mark.parametrize(
    "relative_path",
    sorted(str(path.relative_to(REPO_ROOT)) for path in parity_files()),
)
def test_parity_tracked_file_matches_its_manifest_hash(relative_path: str) -> None:
    manifest = load_manifest()
    assert manifest[relative_path] == parity_digest(REPO_ROOT / relative_path), (
        f"{relative_path} changed. Apply the same change to the codex-plugins "
        "copy, then regenerate parity-manifest.json in both repositories."
    )


def test_stripping_a_module_docstring_leaves_the_rest_of_the_source() -> None:
    source = '#!/usr/bin/env python\n"""Doc.\n\nMore.\n"""\n\nimport os\n'
    assert strip_module_docstring(source) == "#!/usr/bin/env python\n\nimport os\n"


def test_stripping_is_a_no_op_without_a_module_docstring() -> None:
    source = 'import os\n\n\ndef f() -> None:\n    """Not a module docstring."""\n'
    assert strip_module_docstring(source) == source


def test_two_scripts_differing_only_in_docstring_hash_alike(tmp_path: Path) -> None:
    claude = tmp_path / "claude.py"
    codex = tmp_path / "codex.py"
    claude.write_text('"""Claude copy."""\n\nVALUE = 1\n', encoding="utf-8")
    codex.write_text('"""Codex copy."""\n\nVALUE = 1\n', encoding="utf-8")
    assert parity_digest(claude) == parity_digest(codex)

    codex.write_text('"""Codex copy."""\n\nVALUE = 2\n', encoding="utf-8")
    assert parity_digest(claude) != parity_digest(codex)


def instruction_assets() -> list[Path]:
    """Return the skill and role assets that must stay path-portable."""
    return sorted(
        [
            SKILL_DIR / "SKILL.md",
            *(SKILL_DIR / "references").glob("*.md"),
            *(AGENTS_DIR / f"{name}.md" for name in CONSENSUS_REVIEW_AGENTS),
        ]
    )


@pytest.mark.parametrize("asset", instruction_assets(), ids=lambda path: path.name)
def test_instruction_assets_do_not_hardcode_the_skill_script_path(asset: Path) -> None:
    text = asset.read_text(encoding="utf-8")
    match = HARDCODED_SKILL_PATH_RE.search(text)
    hit = match.group(0) if match else ""
    assert match is None, (
        f"{asset.relative_to(REPO_ROOT)} hardcodes '{hit}'. "
        "Use ${CLAUDE_SKILL_DIR}/scripts/<name>.py instead."
    )


def test_the_regex_catches_a_hardcoded_path() -> None:
    assert HARDCODED_SKILL_PATH_RE.search(
        "uv run plugins/v8ch/skills/consensus-review/scripts/recover_context.py 7"
    )
    assert not HARDCODED_SKILL_PATH_RE.search(
        "uv run ${CLAUDE_SKILL_DIR}/scripts/recover_context.py 7"
    )


def write_manifest() -> None:
    """Regenerate parity-manifest.json from the files on disk.

    Run as ``python tests/test_consensus_review_parity.py`` after an intentional
    parity change, in both repositories, in the same pull request.
    """
    payload = {
        "description": (
            "sha256 per parity-tracked file, over content with any Python module "
            "docstring removed. Identical in claude-plugins and codex-plugins. "
            "Regenerate with tests/test_consensus_review_parity.py."
        ),
        "files": {
            str(path.relative_to(REPO_ROOT)): parity_digest(path)
            for path in parity_files()
        },
    }
    MANIFEST_PATH.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {len(payload['files'])} hashes to {MANIFEST_PATH}")


if __name__ == "__main__":
    write_manifest()
