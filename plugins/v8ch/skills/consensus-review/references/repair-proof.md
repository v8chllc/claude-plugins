# Repair Proof Contract

This is the normative contract for classifying and accepting repair proof. The
fixer and fix workflow link here instead of restating these rules.

## Classification

Classify each applied repair by its changed content, independent of its file
extension.

- A **text-only repair** changes prose that no agent or tool executes or
  interprets as code or configuration.
- A **code or configuration repair** changes executable content, configuration,
  or a command, script block, or configuration snippet embedded in prose.
- A repair containing both classes must satisfy the proof requirements for
  both.

## Evidence producers

The fixer proves code or configuration repairs. For each such repair marked
`fixed`, or `partial` where that content changed, it runs a focused check and a
mutation check: remove or invert the repair, confirm the named check fails, and
restore the repair. A check that does not fail under mutation is not confirmed.

The independent `v8ch:repair-proof-reviewer` proves text-only repairs after the
fixer finishes. It is read only. For each text-only repair marked `fixed`, or
`partial` where that content changed, it compares the final text with the
finding and intended correction, then records `accepted` or `rejected`, the
inspected correction, and its reason. The fixer may describe its change but may
not attest to its correctness.

A `declined` or `work-item-required` finding applies no repair and needs no
proof.

## Independent verification procedure

Before invoking the reviewer, the workflow derives the expected text-only
finding IDs from the fixer's dispositions and repository-relative diff. Include
every `fixed` finding whose applied repair has a text-only part and every
`partial` finding where a text-only part changed. Pass that expected set to the
reviewer with the other inputs.

The reviewer independently derives the actual text-only repair IDs from the
synthesized report, fix log, and repository-relative diff. It must not use the
workflow's expected set as the source of that inventory. It compares the actual
set with the expected set and fails verification on any missing or unexpected
ID. For every ID in the union of those sets, it reads the synthesized finding,
the fix log, and the final changed text, then compares the repair with the
finding's intended correction without raising new findings or judging code and
configuration parts. Its complete result uses this schema:

```markdown
## Independent Text Repair Verification

- **[F-N]** — `accepted` | `rejected` — <correction inspected and reason>
```

There must be exactly one record for every expected ID and no records for other
IDs in a verified result. When both sets are empty, use `None.` instead of a
finding record. End with `VERIFIED` only when the independently derived actual
set equals the expected set and every repair is present and accepted. Otherwise
end with `PROOF_UNPROVEN` followed by every rejected, missing, or unexpected
finding ID.

## Acceptance

A repair is proven only when every code or configuration part has a confirmed
mutation check and every text-only part has an independent `accepted` record.
The fix workflow must validate the entire independent result before committing;
the terminal marker alone is insufficient. It accepts the result only when the
heading occurs once, the reviewer states that its independently derived actual
set equals the expected set, every record matches the schema, every expected ID
occurs exactly once as `accepted`, no unexpected ID occurs, `None.` is used only
when both sets are empty, and the last nonblank line is `VERIFIED`.

A missing, malformed, duplicate, rejected, unexpected, or incomplete record,
or a missing or incorrect terminal marker, is `PROOF_UNPROVEN`. Name every
affected finding ID and commit nothing. Repository quality commands must also
pass before any commit.

The commit body records the mutation checks and the independent text repair
verification records.
