# Shared Memory Operations

This plugin-root directory owns memory operations used directly by both
`remember` and `recommend`. Neither skill depends on the other's workflow
steps or files. Claude instructions resolve these assets from
`${CLAUDE_PLUGIN_ROOT}/memory/` in an installed plugin.

| Shared asset | Operation |
| --- | --- |
| `references/types.md` | Curated entry types, templates, and evidence rules |
| `references/procedural-targets.md` | Procedural target allowlist and routing |
| `references/journal-format.md` | Daily journal entry format and dedupe marker |
| `references/recording.md` | Curated duplicate/update, journal append/retry, and procedural write rules |
| `scripts/validate_memory.py` | Read-only validation CLI and optional fast-track steering operation |
| `scripts/segment_format.py` | Cross-toolchain lifecycle segment schema used by validation |

Remember retains its Claude hook setup, capture, segment lifecycle, legacy
directive, and lifecycle-specific reference. Recommend owns recommendation
selection, approval, validation preflight, and application order. Both skills
call the shared validator and recording contract directly.
