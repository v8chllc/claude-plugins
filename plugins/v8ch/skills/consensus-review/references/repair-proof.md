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

## Acceptance

A repair is proven only when every code or configuration part has a confirmed
mutation check and every text-only part has an independent `accepted` record.
The fix workflow must check both before committing. Missing or rejected proof
returns `MUTATION_UNPROVEN`, names the affected finding IDs, and commits
nothing. Repository quality commands must also pass before any commit.

The commit body records the mutation checks and the independent text repair
verification records.
