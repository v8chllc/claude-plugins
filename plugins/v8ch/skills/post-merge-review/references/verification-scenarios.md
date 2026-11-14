# Disposable Verification and Triage scenarios

Use this recipe to exercise the named procedures with generic local evidence.
It is validation input, not a second implementation of Verification. The agent
follows SKILL.md, chooses the verdict from inspected evidence and returns the
actual report, signal and qualified draft. Automated checks of wording alone do
not establish these behaviors.

Prepare a disposable Git project outside any product checkout. The caller adds
`.local/` to that project's `.gitignore`, commits a `sample.py` containing:

```python
def render(rows):
    return rows[0]
```

Prepare `origin/main` at that commit. Supply a valid shared review bound to that
commit using the existing report formatter; retain its exact bytes. The finding
is F-1, HIGH, Must Fix, `sample.py:2`: “Empty input raises IndexError; every input
raises IndexError.” The second clause deliberately overstates the impact.
No private or external report is needed. Treat this as an existing review for
later Verification. For the immediate-entry case, first return this validated
review with its unchanged REVIEW_COMPLETE contract, then enter Verification in
a separate procedure invocation with that exact review. The fixture replaces
review generation only; it does not bypass review validation or Verification.

Use the current Python executable for these selected commands from the project:

| Case | Selected command body (`python -c`) | Purpose and expected evidence |
| --- | --- | --- |
| passing | `from sample import render; assert render([1]) == 1` | acceptance; exit 0, no reproduced defect for this narrow check |
| failing | `from sample import render; assert render([]) == ''` | acceptance; nonzero IndexError |
| reproduced defect | `from sample import render; exec('try:\n render([])\nexcept IndexError:\n print("reproduced empty-input failure")\nelse:\n raise AssertionError("not reproduced")')` | diagnostic; exit 0 proves a defect, so overall failed |
| contradicted impact | `from sample import render; assert render([1]) == 1; print('nonempty input succeeds')` | diagnostic; disproves “every input raises” only |

Prevent Python bytecode writes with `PYTHONDONTWRITEBYTECODE=1`, and direct any
other generated evidence into the reserved ignored run. For a finding-bearing
report the passing command alone leaves that finding's untested clauses
unverified, hence incomplete. Also exercise a valid clean review with no
findings and the passing command: that case can be passed. The failing and
reproduced-defect cases are failed. Pair the two diagnostic commands to produce
a partial-contradiction claim table; Triage must draft only the empty-input
problem and visibly exclude the contradicted all-input impact. Approve no real
filing. Confirm it stops for sponsor approval of this one draft. For full
contradiction, supply a separate valid review whose sole claim is “nonempty
input raises”; the nonempty command contradicts it, and Triage returns No action
with no work draft while retaining F-1/HIGH/Must Fix and the immutable report.

For incomplete readiness, select a uniquely absent executable, and separately
declare an unavailable/reset-required test database. Inspect availability
without executing the check or resetting/installing anything. Record exact
missing prerequisite, started=false and no exit result. Reuse the prepared
workspace for the available checks with explicit caller authorization; no fresh
checkout or environment is required.

For artifacts, snapshot tracked and untracked source and their bytes, retain a
private ignored backup sentinel outside the output subtree, and run the skill's
artifact helper before any report writes. Repeat at the same merge and confirm
different output directories and unchanged earlier evidence. In a second
project without an ignore rule, reservation must fail before `.local` is
created; return the setup gap in chat. Never edit that project's ignore rules
as part of the procedure. Also exercise a symlinked output and an ignore
exception for an actual output; both must be rejected before a write.

Record every command, actual output/exit status, report byte comparison,
source/environment/private-backup comparison and resulting signal. For paired
ports compare baseline definitions with baseline definitions, then head
definitions and this same scenario matrix at both heads. Identify all four
commits and only necessary role/path wiring differences. This recipe needs no
platform calls, installation, publication, filing or product fixes.
