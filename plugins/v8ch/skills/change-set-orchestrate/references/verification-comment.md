# Verification comment

The comment that records `change-set-orchestrate`'s verification of one pull request. The shared run-state contract (`workflows/contracts/run-state.md`) names this comment in the terminal snapshot as `verification_comment`.

Use `workflows/contracts/verification-base.md` for the common evidence and publication rules; this reference defines the change-set layout and proof identity.

Posted by the verify agent under the posting and read-back rule in `workflows/contracts/run-state.md`:

```markdown
### Change Set verification — run <run_id>, head <short sha>

**Head:** `<sha>` — **Supersedes:** <URL of the verification comment this replaces, or none>

<!-- orchestration-result
{"run_id":"<run_id>","role":"verifier","kind":"verification","head_sha":"<full sha>","outcome":"pass|fail","criteria":[{"id":"AC-1","disposition":"pass|fail|not_verified|underived|pending_sponsor","question":null}]}
-->
**Supports:** <when this full comment carries a recheck: this comment, row <k>; omit otherwise>
**Dispositions at <short sha>:** pass <P>, fail <F>, not_verified <N>, underived <U>, pending_sponsor <S>

- <each `fail`, `not_verified`, or `underived` criterion, by row number and a few words; or "No failures or gaps">
- **Pending sponsor judgement:** <every `pending_sponsor` row number, `AC-n`, and exact question; or none>
- **Conclusion:** <one line: whether every check-decided criterion passed at this head; pending sponsor rows do not affect the conclusion>
- **Result:** <when this comment carries a recheck: what it ran and showed; omit otherwise>

<details><summary>Criteria, checks, and evidence — head <short sha></summary>

**Inputs:** <exactly what the verifier was given: run ID, run issue URL, repository, pull request, head SHA>
**Shared inputs:** <for shared criteria only: the bound check and sibling identifiers (repository, pull request number, recorded head SHA); otherwise none>

| # | Criterion | Check | Disposition | Head | Evidence |
| --- | --- | --- | --- | --- | --- |
| <row number; one row per criterion> | <criterion text, verbatim> | <the check that would show it unmet> | pass \| fail \| not_verified \| underived \| pending_sponsor | <short sha the disposition was reached at> | <path:line, link, or the row's block under Evidence below; a replaced row begins "replaces <old disposition> at <old sha>"> |

**Quality commands:** <source that supplied them: repository profile, named child block, default child block, or manifest> — <each command> — <pass or fail; its output is under Evidence>
**Replaced checks:** <criterion — old check — reason tied to the criterion's text, or none>
**Observations:** <anything checked outside every criterion, and each regression guard run at the head, each numbered, its evidence under Evidence, or none>

<details><summary>Evidence</summary>

**Row <k>:** <the command and inspected output for the row numbered <k> in the table, fenced with the command, exit status, and inspected output>

**Quality command <n>:** <the command and its inspected output at the head, fenced with the command, exit status, and inspected output>

**Observation <n>:** <the command and inspected output, fenced with the command, exit status, and inspected output>

</details>

<details><summary>Check scripts</summary>

<the full text of every check script run, fenced with the command, exit status, and inspected output>

</details>

</details>

<details><summary>Recheck evidence — row <k>; omit this section when there is no recheck</summary>

**Ran at:** `<sha>`

<the command and its inspected output, and full text of every check script it ran, fenced with the command, exit status, and inspected output>

</details>
```

- `pending_sponsor` is excluded from the conclusion about whether check-decided criteria passed. Its Evidence cell identifies the passing paired `AC-n`, reachability check and reproduction steps at this head. A missing paired `pass` or unreachable state makes this sponsor row `not_verified`, citing the pair or state, and cannot be `pending_sponsor`. Re-verify this row whenever its paired criterion is re-verified.
- The disposition counts cover only the rows for this head. A row is replaced, never duplicated, when its criterion is verified again; the new row's Evidence cell begins "replaces <old disposition> at <old sha>", which is how the earlier disposition is retired.
- A shared criterion uses the one bound check across every applicable recorded head; if it cannot run on one, each applicable proof records `not_verified`. An interaction criterion cites joint evidence exercising the repositories together. Sibling pull requests are read-only inputs only for shared criteria.
- A disposition with no evidence is invalid. An exit code counts only when the agent inspected the output it refers to.
- `underived` means no check could falsify the criterion; it states why and is never a pass. For each `not_verified` or `underived` row, name a test that would decide it when one exists; only such rows qualify for the one automatic test-only fix round. A sponsor exception is recorded separately in an `orchestration-decision` marker and never rewrites this row.
- A check that passes against the baseline commit proves nothing and is replaced, with the reason recorded.
- A claim outside every criterion is an observation, never a row: it takes no disposition and counts toward no criterion.
- The heading, full head, disposition counts, and bullets are the visible summary; everything inside `<details>` is the complete record. A blank line follows every `<summary>` line. The verifier reads every collapsed section it consumes; the visible summary never substitutes for evidence. Each quoted command output and check script goes in its own fence longer than any run of backticks or tildes inside it, with the command and exit status. Label each block `Full output` or `Excerpt`; mark every cut, including a cut at the beginning or end, with `[… <n> lines omitted]` and an exact count. A split comment repeats the summary and identifies `**Part:** <k> of <m> of <first-part URL>` on later parts.
- A regression guard, from an issue's Regression Guards section, is an observation, never a row: its check ran at the head, with its result and quoted output. It needs no baseline failure and takes no disposition.

A supplemental recheck may be a linked section of this full comment or of an erratum. It supports the named row at the current pull request head and is never posted as a standalone comment.

An erratum is permitted only when no disposition changes. It names the amended full comment, its head, and `**Disposition changed:** no`, then quotes the exact original and replacement text in separate fenced blocks under a `Corrected text` details section. A changed disposition requires a full superseding comment at the current head. A recheck carried by an erratum names `**Supports:** <amended comment URL, row <k>>` and the current head; a recheck on a superseded comment or another head is not evidence about what ships.

```markdown
### Change Set verification erratum — run <run_id>, head <short sha>

**Head:** `<sha>` — **Amends:** <URL of the full verification comment amended>
**Supports:** <when this erratum carries a recheck: amended comment URL, row <k>; omit otherwise>
**Disposition changed:** no

- **Correction:** <what text was corrected>
- **Result:** <when this erratum carries a recheck: what it ran and showed; omit otherwise>

<details><summary>Corrected text</summary>

**Original:**
<the exact original text in a fenced block>

**Replacement:**
<the exact replacement text in a fenced block>

</details>

<details><summary>Recheck evidence — row <k>; omit this section when there is no recheck</summary>

**Ran at:** `<sha>`

<the command and its inspected output, and full text of every check script it ran, fenced with the command, exit status, and inspected output>

</details>
```

## Returned proof identity

A full comment returns `proof_comment_url` as its own URL and `erratum_url: null`. An erratum returns `proof_comment_url` as the full comment identified by `**Amends:**`, and `erratum_url` as its own URL. A failed identity lookup, failed post, or no-post verifier returns neither new identity. The orchestrator passes only `proof_comment_url` to the terminal snapshot; it retains `erratum_url` as a linked correction note.

The verifier writes the marker on every full verification comment, including a failing result. Fill `criteria` from all current-head rows; a `pending_sponsor` row uses its exact question. Errata do not carry a new result marker.
