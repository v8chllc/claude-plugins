---
name: recommend
description: "Recommend and apply memory updates from the current session. Use when the user invokes /recommend session (journal + curated + procedural promotions), /recommend curated (curated promotions only), or /recommend procedural (procedural promotions only)."
---

# Recommend Skill

Routes `/recommend` commands to memory recommendation workflows.

See `../remember/references/types.md` for curated memory entry templates.
See `../remember/references/procedural-targets.md` for approved procedural write targets.
See `../remember/references/journal-format.md` for journal entry format and dedupe marker spec.
Use `../remember/scripts/validate_memory.py` as a validation preflight before
applying any approved memory changes.

---

## Routing

Read `$ARGUMENTS`:
- `session` → run Workflow F (Recommend Session)
- `curated` → run Workflow E (Recommend Curated)
- `procedural` → run Workflow G (Recommend Procedural)
- empty or unrecognized → ask: "Which recommendations would you like? `session`, `curated`, or `procedural`?"

---

## Workflow E: Recommend Curated

Triggered by `/recommend curated`.

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Review current session context.
3. Identify durable curated candidates:
   - `decision`: explicit technical or workflow choices and their rationale.
   - `error`: failure modes, fixes, gotchas, or validation issues discovered.
   - `context`: current project state, active work, blockers, or next steps. Written to `.remember/local/context.md`, never to `.remember/MEMORY.md`.
   - `preference`: repeated or explicit user working preferences.
   - `entity`: important codebase objects discussed in enough detail to locate and describe.
4. Exclude ephemeral information: one-off commands, transient status, vague observations, unconfirmed guesses, or facts already covered.
5. Compare candidates against `.remember/MEMORY.md`, and any `context` candidate against `.remember/local/context.md`. Mark each as `add`, `update`, or `skip`. Prefer updating the existing local `context` entry over adding a second one.
6. Present recommendations only; do not write automatically.
7. For each recommendation include: action, type, subject, reason it is durable, proposed entry text using the template from `../remember/references/types.md`.
8. Ask which to apply.
9. Before writing approved entries, run
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude`.
   If validation fails, report the issues and do not write unless the user
   explicitly confirms proceeding despite the malformed memory state.
10. Apply each approved entry to its own target. `context` replaces the single
    entry in `.remember/local/context.md`; never write `context` to
    `.remember/MEMORY.md`. For every other type, check `.remember/MEMORY.md` for
    an existing entry with the same name or subject; if found, update in place,
    otherwise append under the correct `## <type>` section.

---

## Workflow F: Recommend Session

Triggered by `/recommend session`.

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Write a journal entry for this session to `.remember/memory/YYYY-MM-DD.md`. Compute a best-effort `session_hash` from available context; if an entry with that hash already exists in today's file, skip silently. See `../remember/references/journal-format.md` for format and hash approach.
3. Internally read `.remember/MEMORY.md`, `.remember/local/context.md` when
   present, the captured journal entry, and full session context for
   recommendation quality. Do not present this as a user-facing manual load
   operation.
4. Identify curated candidates (entity, decision, error, context, preference) and procedural candidates (workflow lessons, coding/arch standards, skill/tool routines).
5. Resolve each procedural candidate to an approved target from `../remember/references/procedural-targets.md`. If no target fits, mark as unsupported.
6. Dedupe curated candidates against `.remember/MEMORY.md`, and any `context`
   candidate against `.remember/local/context.md`; dedupe procedural candidates
   against their respective target files. Classify existing local context as
   `update` or `skip`, never `add`.
7. Present recommendations grouped by target and action: `add`, `update`, `skip`. List unsupported procedural candidates separately with a note.
8. Before applying approved changes, run
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude`.
   If validation fails, report the issues and do not write unless the user
   explicitly confirms proceeding despite the malformed memory state.
9. Apply only approved changes:
   - Curated: `context` replaces the single entry in `.remember/local/context.md`. For every other type, check `.remember/MEMORY.md` for an existing entry with the same name or subject; update in place if found, otherwise append under the correct `## <type>` section.
   - Procedural: write only to files listed in `../remember/references/procedural-targets.md`.

---

## Workflow G: Recommend Procedural

Triggered by `/recommend procedural`.

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Internally read `.remember/MEMORY.md`, current session context, and today's
   journal file if present for recommendation quality. Do not present this as a
   user-facing manual load operation.
3. Identify procedural candidates only: workflow lessons, coding/arch standards, skill/tool routines.
4. Resolve each to an approved target from `../remember/references/procedural-targets.md`. If no target fits, mark as unsupported; do not write elsewhere.
5. Read existing guidance in each resolved target file.
6. Classify candidates as `add`, `update`, or `skip` against the file's current content.
7. Propose a concise patch per target. Present for user review.
8. Before applying approved changes, run
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude`.
   If validation fails, report the issues and do not write unless the user
   explicitly confirms proceeding despite the malformed memory state.
9. Apply only approved changes. Write only to files listed in `../remember/references/procedural-targets.md`.

$ARGUMENTS
