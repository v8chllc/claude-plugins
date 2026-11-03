<!-- post-merge-review
{"files_touched":3,"findings":1,"merge_commit":"0123456789abcdef0123456789abcdef01234567","platform":"github","reference":12,"schema_version":1,"scope_basis":"net-diff","score":90,"status":"passing","target_branch":"main","type":"post-merge-report"}
-->
**Post-merge review** of PR #12 at merge commit `0123456789abcdef0123456789abcdef01234567`.

### Quality Score: 90/100 — Passing

### Run Provenance

Delegation: parallel-subagents. Plan: none. Deferred: none.

### Evidence

- **Files examined:** src/report.py, tests/test_report.py
- **Commands run:** uv run pytest tests/test_report.py

### Summary

- The empty-input path has one demonstrated defect.

### Must Fix

#### [F-1] [HIGH] Empty input raises before rendering the placeholder

**Location:** src/report.py:12

**Failure:** Calling `render([])` raises `IndexError` instead of returning the documented empty-input result.

**Fix:** Handle empty input before reading the first row.

**Reviewers:** correctness-reviewer

### Should Fix

None.

### Plan Notes

None.

### Noted

None.

### Behavior Deltas

```behavior-deltas
deltas: none
basis: This review introduces no code changes.
```

### Score Breakdown

| Finding | Deduction |
| --- | --- |
| [F-1] HIGH | −10 |
| **Final score** | **90/100** |
