# Memory Recording Operations

These rules are shared by direct Remember records and approved Recommend
changes. Use `types.md`, `journal-format.md`, and `procedural-targets.md` for
their respective formats and allowable targets.

## Curated entry add or update

1. Check `.remember/MEMORY.md` for an existing entry with the same name or
   subject under its `## <type>` section. Treat matching content as a duplicate
   and skip it.
2. For an existing subject, update the entry in place. Otherwise append the
   formatted entry under its type section. Never append a second entry for the
   same subject.
3. For decision and error updates, keep existing `Evidence` only while it
   supports the revised claim. Replace it with applicable checkable evidence
   or omit it when none is available. Follow `types.md` for the untrusted-data
   and source rules.

## Journal append and retry dedupe

1. Compose the entry according to `journal-format.md`, using the local date
   and a best-effort `session_hash` for the covered session window.
2. Read today's `.remember/memory/YYYY-MM-DD.md` if it exists. If a
   `remember-journal` marker already has that hash, skip the append. This makes
   retries idempotent for the same window. A later window with new material
   receives a new hash and a new appended entry.
3. Append the marker and prose entry together. Do not replace earlier entries.
   For captured lifecycle segments, mark them summarized only after the journal
   write succeeds.

## Procedural target write

1. Resolve the target through `procedural-targets.md`; reject unsupported
   targets and do not write them without explicit user direction.
2. Read existing target guidance. Skip a duplicate rule, update a partially
   covered rule in place, or add a concise new rule.
3. Present the patch for approval. Create a missing allowed target only after
   approval, then apply only the approved patch.

For a recommendation, the Recommend workflow must run the shared validation
preflight after approval and before any curated or procedural step above.
