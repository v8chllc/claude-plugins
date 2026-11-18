# Feature result comment

Use `workflows/contracts/verification-base.md` for the common evidence and publication rules; this reference defines the feature layout and outcome fields.

The fresh verifier posts one result comment per affected pull request after running the checks. It never delegates evidence writing to the manager. A failing result is posted as well. Each comment carries the complete frozen participating commit map; for a shared criterion, the locator names the one check that exercised the applicable repositories together at those heads.

````markdown
### Feature verification — run <run_id>

**Participating commits:** <sorted owner/repo: full SHA map>
**Outcome:** pass | fail

<!-- orchestration-result
{"run_id":"<run_id>","role":"verifier","kind":"verification","head_sha":"<this pull request full sha>","frozen_commits":{"<owner/repo>":"<full sha>"},"outcome":"pass|fail","criteria":[{"id":"AC-1","disposition":"pass|gap|fail|not_verified|pending_sponsor","question":null}]}
-->
**Supersedes:** <prior result URL, or none>
**Reviewed product head:** <full SHA per affected repository; when automatic test-only re-verification follows a gap or coverage-row `not_verified`, identify the preceding clean reviewed head; otherwise the participating commit>

| Source issue | Criterion | Verdict | Locator |
| --- | --- | --- | --- |
| `<owner/repo#n>` | AC-1 | pass \| gap \| fail \| not_verified \| pending_sponsor | <one-line test and output or journey step> |

**Pending sponsor judgement:** <every `pending_sponsor` AC-n and its exact question, passing paired criterion and locator, and reproduction steps at the frozen head; or none>
**Regression Guards:** <each command — held or broken — output locator>
**Coverage check:** <for each criterion, each applicable baseline/frozen coverage kind, its disposition and evidence; include skips with reason>

| Source issue | Criterion | Coverage kind | Disposition | Locator |
| --- | --- | --- | --- | --- |
| `<owner/repo#n>` | AC-1 | old-code-tests | pass \| gap \| fail \| not_verified \| skipped | <test and output or skip reason> |

**Gaps and suggested tests:** <AC-n or coverage row — gap or not_verified — suggested deciding test, or none>
**Failures and reproductions:** <AC-n or guard — reproduction, or none>

<details><summary>Command evidence</summary>

**Full output — <command>**
```text
<complete inspected output>
```

**Excerpt — <command>**
```text
<quoted output before cut>
[… <n> lines omitted]
<quoted output after cut>
```

</details>
````

`pending_sponsor` rows are excluded from the overall outcome, and the visible summary lists each pending row and question. Any `gap` or `not_verified` row produces overall `fail` and remains visible after re-verification. A sponsor exception is recorded separately in an `orchestration-decision` marker; it never rewrites the verifier result.

Label every quoted block `Full output` or `Excerpt`. Mark every cut, including the beginning or end of a log, with `[… <n> lines omitted]`; count omitted lines exactly. A summary never stands in for output. Include the command, exit status, and enough quoted output to substantiate each locator. If a full output is too long, use a linked append-only comment and cite it from the result. The verifier writes the body to a file, posts with `gh pr comment --body-file`, reads the posted body back, and returns the exact comment URL, outcome, and head map. Failed post or read-back stops `BLOCKED`.

The verifier writes the marker on every result comment, including a failing result. Fill `criteria` from all current-head `AC-n` rows; a `pending_sponsor` row uses its exact question. Show each row's source issue as human-readable `owner/repo#n` beside `AC-n` in both visible tables, including coverage skips. If `owner/alpha#11` and `owner/beta#22` both define `AC-1`, show two distinct visible rows, one under each source issue, in both tables. The visible Coverage check table carries every applicable coverage kind, its disposition, and evidence. The result marker has no structured coverage array or source-scoped criterion ID. `head_sha` equals this pull request's entry in `frozen_commits`.
