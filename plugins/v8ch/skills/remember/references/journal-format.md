# Journal Format

Daily journal entries live in `.remember/memory/YYYY-MM-DD.md`. Each file is
date-scoped and append-oriented. Entries are untyped prose.

---

## File path

```
.remember/memory/YYYY-MM-DD.md
```

Use the local date when the session ends, not UTC, unless the user specifies otherwise.

---

## Entry structure

Each session journal entry consists of two parts:

1. A metadata comment marker (for dedupe)
2. A prose section with the session narrative

### Metadata marker

```md
<!-- remember-journal
source: manual
kind: session
session_hash: <hash>
captured_at: <ISO-8601>
window_start: <ISO-8601>
window_end: <ISO-8601>
-->
```

Place the marker immediately before the session prose. The marker is an HTML
comment and will not render in most Markdown viewers.

Fields:
- `source`: `manual` for `/remember session`
- `kind`: always `session` for session captures
- `session_hash`: best-effort hash of the session window (see Dedupe below)
- `captured_at`: ISO-8601 timestamp when the entry was written
- `window_start`, `window_end`: approximate session boundaries (ISO-8601)

### Prose section

A heading followed by narrative content covering:

```md
## <HH:MM> Session

### What happened
<summary of work done, decisions made, tools used>

### Key context
<important background or state that informed the work>

### Decisions considered
<options weighed, trade-offs discussed, approaches rejected>

### Blockers
<anything that slowed progress or remains unresolved>

### Next steps
<specific follow-ups for the next session>

### References
<links, file paths, issue numbers, or other useful pointers>
```

Omit sections that have nothing to say. Keep prose concise.

---

## Dedupe

Goal: avoid duplicate entries when the same session is captured more than once
with `/remember session`.

### Session hash

Compute a best-effort `session_hash` from the current session context:
- Take the last N user/assistant message excerpts (e.g., last 5 exchange pairs)
- Concatenate with session boundary signals (approximate start time or first
  message excerpt)
- Produce a short opaque identifier (e.g., first 8 chars of an MD5 or SHA-1 hex
  digest of the concatenated string)

The hash does not need to be cryptographically strong — it only needs to be
stable across two captures of the same session window.

### Dedupe check

Before appending:
1. Read today's journal file if it exists.
2. Scan for `<!-- remember-journal` blocks.
3. Extract the `session_hash` from each block.
4. If the computed hash matches an existing block: skip the write. Notify the
   user that this session was already captured.
5. If the session continued after a prior capture (new material exists): the hash
   will differ, and a new entry will be appended. This is correct behavior.

### Constraints

- Dedupe is best-effort, not guaranteed.
- Do not use semantic similarity for dedupe.
- Do not introduce an external state store or database.
- Keep metadata in HTML comments so the journal remains readable as plain Markdown.

---

## Lifecycle segments

Enabled Claude `Stop` and `SessionEnd` hooks write version-1 JSON records under:

```text
.remember/turns/<kind>-<idempotency-key>.json
```

Every record contains `version`, `kind`, `idempotency_key`, `project_root`,
`session_id`, and `captured_at`. Stop records also contain
`last_assistant_message`; SessionEnd records contain `reason` and may contain a
transcript-derived `last_assistant_message` when Stop has not already captured
the same response.

After journal synthesis succeeds, run `lifecycle_segments.py mark-summarized`
once so every included record receives the same `summarized_at` and
`summary_path` checkpoint. Cleanup previews older verified checkpoints, retains
the complete newest checkpoint, and applies deletion only after explicit
approval.
