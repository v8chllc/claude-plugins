# Lifecycle Segment Format

Remember owns the Claude capture and segment lifecycle. The shared parser at
`../../../memory/scripts/segment_format.py` validates the common record schema.

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
