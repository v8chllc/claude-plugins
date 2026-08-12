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

Lifecycle segments live in one store shared by every toolchain. Enabled Claude
`Stop` and `SessionEnd` hooks write `version: 3` JSON records under:

```text
.remember/turns/<platform>-<kind>-<key>.json
```

The store is flat and non-recursive: `platform` is a record field, never a
directory. Claude writes `platform: "claude"` and reads records written by any
supported platform, so one synthesis run covers everything captured in the
workspace.

Every record carries exactly these twelve keys, with nullable keys present as an
explicit `null` rather than omitted:

| Key | Type | Rules |
| --- | --- | --- |
| `version` | integer | Always `3`. |
| `platform` | string | `claude` or `codex`. |
| `kind` | string | `stop` or `session-end`. |
| `key` | string | Non-empty idempotency key, unique per `(platform, kind)`. |
| `project_root` | string | Absolute workspace root; must match the reader's root. |
| `session_id` | string | Non-empty. |
| `captured_at` | string | `YYYY-MM-DDTHH:MM:SS.ffffffZ`. |
| `text` | string | Assistant response text; `""` for a terminal segment with none. Never `null`. |
| `reason` | string \| null | Non-null only when `kind` is `session-end`. |
| `transcript_path` | string \| null | Carried through; never followed. |
| `summarized_at` | string \| null | Same timestamp encoding as `captured_at`. |
| `summary_path` | string \| null | Relative path that resolves inside `.remember/memory/`. |

Timestamps use six-digit microseconds and a literal `Z` suffix, never an offset
form. The encoding is fixed-width, so lexicographic order equals chronological
order and `pending` returns segments ascending by `captured_at`.

`summarized_at` and `summary_path` are written and cleared together. A record
with one set and the other `null` is rejected as invalid, never repaired.

There is no reader for any earlier segment format. A file that is not a valid v3
record is skipped as malformed: it is never parsed, never stamped, and never
deleted.

After journal synthesis succeeds, run `lifecycle_segments.py mark-summarized`
once so every included record — from every platform — receives the same
`summarized_at` and `summary_path` checkpoint. A run writes one journal entry
covering every segment it summarized, with a single `session_hash` over all
source keys regardless of platform. Cleanup previews older verified checkpoints,
retains the complete newest checkpoint, and applies deletion only after explicit
approval.
