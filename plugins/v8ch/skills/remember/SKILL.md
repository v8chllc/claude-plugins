---
name: remember
description: "Load existing project memory, set up memory storage, record structured memories, or capture session notes across three lanes: daily journal, curated memory, and procedural memory. Trigger when: user says 'remember [type] [content]' or 'remember that [content]'; user invokes /remember with or without args; user invokes /remember setup, /remember session, /remember procedure, /remember workflow, /remember standard, or /remember review; user says 'setup remember', 'remember in this project', or 'initialize memory here'. For /recommend commands use the recommend skill."
---

# Remember Skill

Manages three memory lanes for the current working directory:

1. **Daily Journal** — episodic session notes in `.remember/memory/YYYY-MM-DD.md`
2. **Curated Memory** — durable structured entries in `.remember/MEMORY.md`
3. **Procedural Memory** — behavior-changing guidance in approved agent-facing targets

See `references/types.md` for curated memory type templates and examples.
See `references/claude-md-directive.md` for the legacy generated directive block
that setup may remove from `CLAUDE.md` only by exact match.
See `references/journal-format.md` for journal entry format and dedupe marker spec.
See `references/procedural-targets.md` for the approved procedural target allowlist.
Use `scripts/validate_memory.py` for deterministic memory validation, JSON
reporting, and setup-aware Memory Fast-Track steering checks.
Use `scripts/hook_setup.py` to enable, disable, and report the opt-in lifecycle
capture channels, and `scripts/lifecycle_capture.py` as the handler it installs.

---

## Trigger patterns

**Manual load — any of:**
- `/remember` (no args)

**Setup — any of:**
- `/remember setup`
- Natural language: "setup remember", "remember in this project", "initialize memory here"

**Validation:**
- `/remember validate`
- `/remember validate --json`
- Natural language: "validate remember", "validate memory"

**Journal write:**
- `/remember session`
- Natural language: "capture this session", "write to journal"

**Recommend:** use the `recommend` skill (`/recommend session`, `/recommend curated`, `/recommend procedural`).

**Review — slash command or natural language:**
- `/remember review`
- "review memory", "audit memories", "clean up remember"

**Procedural write:**
- `/remember procedure <text>`
- `/remember workflow <text>`
- `/remember standard <text>`

**Lifecycle capture (opt-in, one channel at a time):**
- `/remember hook enable stop-capture`
- `/remember hook disable stop-capture`
- `/remember hook enable session-end-capture`
- `/remember hook disable session-end-capture`
- `/remember hook status`

**Segment cleanup:**
- `/remember clean`
- `/remember clean --apply`

**Record — slash command:**
- `/remember entity <identifier>`
- `/remember decision <text>`
- `/remember error <text>`
- `/remember context <text>`
- `/remember preference <text>`
- `/remember todo <text>`

**Record — natural language (auto-invoke):**
- "Remember the entity `<identifier>`"
- "Remember the decision `<text>`"
- "Remember the error `<text>`"
- "Remember the context `<text>`"
- "Remember the preference `<text>`"
- "Remember the todo `<text>`"
- "Remember that `<text>`" — type inferred from content

---

## Workflow A: Manual Load / Status

Triggered by `/remember` with no args.

1. Read `README.md` and `CLAUDE.md` when present, then run `ls -1` and
   `git ls-files` as separate commands. Return a concise project brief before
   memory status; do this even if memory is uninitialized.
2. Check whether `.remember/MEMORY.md` and `.remember/memory/` exist in cwd.
   If either is missing, report that `/remember setup` is needed. Do not create files.
3. Read `.remember/MEMORY.md` when present.
4. Find dated journal files matching `.remember/memory/YYYY-MM-DD.md` and
   select the most recent one by date. Ignore non-dated files. This selection
   is not limited to today or yesterday; load the newest dated journal even if
   it is weeks or months old.
5. If a dated journal exists, read it. Otherwise, explicitly report that no
   dated daily journal exists.
6. Respond with a concise status report:
   - durable memory loaded from `.remember/MEMORY.md`
   - most recent dated journal loaded, including its path, or no dated daily
     journal exists
   - optional procedural targets present or missing:
     `CODING_STANDARDS.md`, `ARCHITECTURE_STANDARDS.md`,
     `WORKFLOW_STANDARDS.md`

## Workflow B: Setup

Triggered by `/remember setup` or natural language setup phrases.

### Core memory setup

1. Create `.remember/` in cwd if it is missing.
2. Create `.remember/memory/` for the journal lane if it is missing.
3. If `.remember/MEMORY.md` is missing, write this stub:

```
# Memory

<!-- This file is read by Claude at the start of every session.        -->
<!-- Use /remember to record entries, or edit directly.                 -->
<!-- Types: entity | decision | error | context | preference | todo     -->

## entity

## decision

## context

## error

## preference

## todo
```

4. If `CLAUDE.md` exists, compare its `## Memory` section to
   `references/claude-md-directive.md`.
   - If the section exactly matches the reference content, remove that generated
     section from `CLAUDE.md`.
   - If a `## Memory` section exists but differs from the reference content,
     leave it unchanged and report that manual review is needed.
   - If no `## Memory` section exists, leave `CLAUDE.md` unchanged.
5. Do not create `CLAUDE.md` and do not inject a memory-load directive.
6. Confirm to the user with a summary of files created, existing files reused,
   directive cleanup performed, and any manual review needed.
7. Run validation and steering detection from the repository root:
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude --check-steering`.
   Report the validation status and issues. Validation must not mutate files.
8. If `CLAUDE.md` is missing a `## Memory Fast-Track Workflow` section, report
   the gap and ask whether to append generated Claude-appropriate guidance.
   Apply it only after user approval with:
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude --apply-fast-track`.
   If `CLAUDE.md` has related but non-matching fast-track guidance, avoid
   destructive edits and ask for manual review or explicit approval.

### Status report

After core memory is confirmed present, inspect and report:

- **Journal lane**: is `.remember/memory/` present? List today's journal file if it exists.
- **Procedural targets**: for each of `CODING_STANDARDS.md`, `ARCHITECTURE_STANDARDS.md`, `WORKFLOW_STANDARDS.md` — present or missing? Report as optional managed targets. Do not create them automatically; offer stubs only on request.
- **Validation**: summarize pass/fail counts and actionable issues from
  `scripts/validate_memory.py`.
- **Memory Fast-Track steering**: report present, missing, added after approval,
  skipped, or manual-review-needed.

---

## Workflow C: Record (typed)

Triggered by `/remember <type> <content>` or natural language equivalent.

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first and stop.
2. **Resolve type**: from explicit arg or inferred from natural language phrasing.
3. **Gather content**:
   - `entity`: search the codebase for `<identifier>` (grep/glob for class, function, or file). Fill template fields from what is found. Confirm with user before writing.
   - `decision`: use provided text. If no date is given, use today's date. Ask for `Rationale` if not supplied.
   - `error`, `context`, `preference`: use provided text. Fill template fields. Ask for missing required fields if content is too sparse.
   - `todo`: use provided text. If no date is given, use today's date. Ask for `Next action` if not supplied. Set `Status: open` by default.
4. **Duplicate check**: search `.remember/MEMORY.md` for an existing entry with the same name or subject. If found, offer to update in place rather than append.
5. Append (or update) the entry under the correct `## <type>` section using the template from `references/types.md`.
6. Confirm to user: type recorded, subject, and whether it was added or updated.

---

## Workflow D: Inferred type

Triggered by "Remember that `<text>`" with no explicit type keyword.

1. Read `<text>` and classify as one of: `entity`, `decision`, `error`, `context`, `preference`, `todo`.
2. Tell the user: "I'll record this as a `<type>`. Does that look right?"
3. On confirmation: continue as Workflow C from step 3.
4. On rejection: ask the user to specify the type, then continue as Workflow C from step 3.

---

## Workflow E: Journal Write (`/remember session`)

Triggered by `/remember session` or natural language journal phrases.

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first and stop.
2. Read every valid, project-matching, unsummarized `.remember/turns/*.json`
   segment in chronological order, including segments created before `/clear`.
   Both `stop` and `session-end` segments are valid input; treat a `session-end`
   segment as terminal-session context for its `reason`, and skip any file whose
   `kind` is missing or unrecognized.
3. Compose one complete journal summary from those segments and the available
   live context. If no eligible segments exist, use live context as before.
4. Write the journal entry first. Only after it succeeds, update each included
   segment with `summarized_at` and `summary_path`. On failure, write neither marker.
5. Confirm the journal path and segment count.

## Workflow E1: Lifecycle Hook Management

<instructions>
Run `scripts/hook_setup.py` for every enable, disable, and status request. Never
hand-edit `.claude/settings.json` and never copy a handler yourself.

- `/remember hook enable <channel>`:
  `python plugins/v8ch/skills/remember/scripts/hook_setup.py enable <channel> --root .`
- `/remember hook disable <channel>`:
  `python plugins/v8ch/skills/remember/scripts/hook_setup.py disable <channel> --root .`
- `/remember hook status`:
  `python plugins/v8ch/skills/remember/scripts/hook_setup.py status --root .`

Pass `<channel>` exactly as `stop-capture` or `session-end-capture`. When the
user names no channel, ask which one; enable only the channel they name.
Report the helper output. When the helper exits non-zero, relay its message and
stop.
</instructions>

<context>
Both channels are default-disabled, opt-in, and independent. The helper writes
project scope only: `.claude/settings.json` and `.claude/hooks/`. It never
touches `~/.claude`.

| Channel | Event | Handler installed at | Captures |
| --- | --- | --- | --- |
| `stop-capture` | `Stop` | `.claude/hooks/remember-stop-capture.py` | The completed main-agent response from `session_id` plus `last_assistant_message` |
| `session-end-capture` | `SessionEnd` | `.claude/hooks/remember-session-end-capture.py` | Terminal-session context: `session_id` plus the end `reason` |

Both handlers are copies of `scripts/lifecycle_capture.py`, installed with mode
`0755` and registered in exec form:

```json
{"hooks":{"Stop":[{"hooks":[{"type":"command","command":"${CLAUDE_PROJECT_DIR}/.claude/hooks/remember-stop-capture.py","args":["--root","${CLAUDE_PROJECT_DIR}","--kind","stop"],"timeout":5}]}]}}
```

`SessionEnd` payloads carry no `last_assistant_message`, so that handler falls
back to the final assistant text in `transcript_path`. It omits the message when
a Stop segment already holds that exact text, so the two channels never store
the same response twice.

Segments are immutable JSON files at `.remember/turns/<kind>-<key>.json` with
`kind` set to `stop` or `session-end`.
</context>

<constraints>
- Enable requires initialized memory; the helper stops when `.remember/MEMORY.md`
  or `.remember/memory/` is missing.
- Enabling or disabling one channel leaves the other channel and every unrelated
  hook and setting intact.
- Re-enabling refreshes the handler and its single registration; it never adds a
  duplicate.
- Invalid or non-object settings JSON stops the run with a repair instruction and
  is never overwritten.
- Handlers stay quiet, exit successfully on any failure, ignore subagent events,
  write no partial data, and never invoke recommendations or edit curated or
  procedural memory.
</constraints>

<output_contract>
Report in this order:
1. The command run and the channel it targeted.
2. The resulting state of both channels, taken from the helper.
3. The next action when the helper reported an error; otherwise the reminder
   that capture starts with the next matching lifecycle event.
</output_contract>

## Workflow E2: Cleanup

<instructions>
`/remember clean` previews removable segments. `/remember clean --apply` deletes
them. Read segments through `cleanup_candidates()` in
`scripts/lifecycle_capture.py`; do not select files by name or timestamp
yourself.
</instructions>

<constraints>
- Delete only segments that have both `summarized_at` and an existing
  `summary_path`, of either valid kind.
- Retain the newest verified summarized segment.
- Never delete active, unsummarized, malformed, unknown-kind, wrong-project, or
  unverifiable files.
</constraints>

<output_contract>
List each candidate path with its kind, then the count deleted or previewed.
</output_contract>

---

## Workflow F: Recommend Curated

Invoked by the `recommend` skill (`/recommend curated`).

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Review current session context.
3. Identify durable curated candidates:
   - `decision`: explicit technical or workflow choices and their rationale.
   - `error`: failure modes, fixes, gotchas, or validation issues discovered.
   - `context`: current project state, active work, blockers, or next steps.
   - `preference`: repeated or explicit user working preferences.
   - `entity`: important codebase objects discussed in enough detail to locate and describe.
4. Exclude ephemeral information: one-off commands, transient status, vague observations, unconfirmed guesses, or facts already covered.
5. Compare candidates against `.remember/MEMORY.md`. Mark each as `add`, `update`, or `skip`. Prefer updating the existing `context` entry.
6. Present recommendations only; do not write automatically.
7. For each recommendation include: action, type, subject, reason it is durable, proposed entry text using the template from `references/types.md`.
8. Ask which to apply. On approval, continue through Workflow C from duplicate check.
9. Before writing approved entries, run validation:
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude`.
   If validation fails, report the issues and do not write unless the user
   explicitly confirms proceeding despite the malformed memory state.

---

## Workflow G: Recommend Session

Invoked by the `recommend` skill (`/recommend session`).

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Run journal write logic (Workflow E steps 2–6) as a prerequisite. If already captured (dedupe), skip silently and continue.
3. Review the captured journal entry and full session context.
4. Identify curated candidates (entity, decision, error, context, preference) and procedural candidates (workflow lessons, coding/arch standards, skill/tool routines).
5. Resolve each procedural candidate to an approved target from `references/procedural-targets.md`. If no target fits, mark as unsupported.
6. Dedupe curated candidates against `.remember/MEMORY.md`; dedupe procedural candidates against their respective target files.
7. Present recommendations grouped by target and action: `add`, `update`, `skip`. List unsupported procedural candidates separately with a note.
8. Apply only approved changes. For curated approvals, continue through Workflow C. For procedural approvals, continue through Workflow I.
9. Before applying approved curated or procedural changes, run validation:
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude`.
   If validation fails, report the issues and do not write unless the user
   explicitly confirms proceeding despite the malformed memory state.

---

## Workflow H: Recommend Procedural

Invoked by the `recommend` skill (`/recommend procedural`).

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Review current session context and today's journal file if present.
3. Identify procedural candidates only: workflow lessons, coding/arch standards, skill/tool routines.
4. Resolve each to an approved target from `references/procedural-targets.md`. If no target fits, mark as unsupported; do not write elsewhere.
5. Read existing guidance in each resolved target file.
6. Classify candidates as `add`, `update`, or `skip` against the file's current content.
7. Propose a concise patch per target. Present for user review.
8. Apply only approved changes (Workflow I).
9. Before applying approved procedural changes, run validation:
   `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude`.
   If validation fails, report the issues and do not write unless the user
   explicitly confirms proceeding despite the malformed memory state.

---

## Workflow I: Procedural Write (`/remember procedure/workflow/standard <text>`)

Triggered by `/remember procedure <text>`, `/remember workflow <text>`, or `/remember standard <text>`.

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first and stop.
2. Parse `<text>` and resolve to an approved target file using `references/procedural-targets.md`.
   - If text maps clearly to one target: proceed.
   - If ambiguous: present candidates and ask the user to choose.
   - If no target fits: surface as unsupported; ask for explicit user direction. Do not write elsewhere.
3. Read existing guidance in the resolved target file. Check for duplication.
4. Propose the addition or update as a patch and present it to the user.
5. On approval: write the change. Prefer updating existing guidance over appending duplicate rules.
6. If the target file does not exist: offer to create it with a stub before writing. Create only on approval.

---

## Workflow J: Review (`/remember review`)

Triggered by `/remember review`, "review memory", "audit memories", or "clean up remember".

1. **Guard**: check `.remember/MEMORY.md` and `.remember/memory/` exist. If
   either is missing, tell the user to run `/remember setup` first.
2. Read `.remember/MEMORY.md` and collect all entries across every type section.
3. For each entry, classify as one of:
   - `retain`: still accurate and useful.
   - `remove`: stale, duplicated, obsolete, superseded, or no longer actionable.
   - `act`: requires follow-up.
4. Apply type-specific review criteria:
   - `entity`: retain if the code object still exists and remains important; remove if deleted, renamed without update, duplicated, or too trivial; act if documentation or dependencies need updating.
   - `decision`: retain if the rationale is still valid; remove if superseded or contradicted by a newer decision; act if implementation or documentation appears incomplete.
   - `error`: retain if the failure mode may recur; remove if obsolete (resolved and unlikely to recur); act if status is `watch` and there is an unresolved mitigation.
   - `context`: retain only if current; remove or update if stale. Collapse duplicates; flag extras for removal.
   - `preference`: retain unless contradicted by a newer preference; remove duplicates or overly narrow one-off preferences.
   - `todo`: retain if still valid; remove if `done`, `obsolete`, or duplicated; act if `open` or `blocked` and specific enough to become a work item.
5. For `todo` entries classified as `act`, propose new work items (title, description, suggested tracking mechanism). Do not create automatically.
6. Respond with a concise summary: total entries reviewed, counts per classification, memories to remove, memories to act upon, proposed work items.
7. Ask which removals and actions to apply. On approval: remove entries, create work items if requested (e.g., `gh issue create`), update `todo` entries with the `Work item` field.

---

## Workflow K: Validate (`/remember validate`)

Triggered by `/remember validate`, `/remember validate --json`, "validate
remember", or "validate memory".

1. Run `scripts/validate_memory.py` from the repository root:
   - Human-readable: `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude --check-steering`
   - JSON: `python plugins/v8ch/skills/remember/scripts/validate_memory.py --root . --toolchain claude --check-steering --json`
2. Validation checks `.remember/MEMORY.md` for required type sections, known
   entry markers, required fields, and duplicate active `context` entries.
3. Validation checks `.remember/memory/YYYY-MM-DD.md` journal filenames and
   `remember-journal` metadata blocks.
4. Validation reports issues without mutating files by default. Only append
   generated Memory Fast-Track steering after explicit user approval with
   `--apply-fast-track`.
5. JSON output includes overall `status`, `counts`, and `issues` containing
   `severity`, `code`, `path`, `message`, and optional `suggested_fix`.
6. Respond with the helper output and a concise next action for any failures.

---

## Edge cases

- **Unknown type in args**: "Remember the widget `<text>`" — treat as Workflow D, infer type from content.
- **Empty subject on record command**: `/remember entity` with no identifier — ask the user to provide the subject.
- **`CLAUDE.md` absent**: do not create it during setup.
- **No durable curated recommendations**: say no memory-worthy updates were found; do not modify files.
- **Procedural candidate with no approved target**: surface as unsupported; present to the user as a manual decision rather than writing elsewhere.

---

$ARGUMENTS
