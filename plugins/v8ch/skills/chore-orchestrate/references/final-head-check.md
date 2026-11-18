# Chore check agent final-head check

At each pull request's current head, create a clean detached worktree under the run scratch directory. Record its full SHA and check that `git status --porcelain` is empty before and after running checks. Run one concrete command per acceptance criterion and Regression Guard, plus every resolved profile quality command, in that worktree. A command must decide its row at this head. Quote enough actual output to support the result; record a command that could not run as `not_verified`, never as a pass. If any criterion cannot be decided this way, stop `NOT_APPLICABLE` with `abandoned_mid_run` and name `change-set-orchestrate`.

Post one full comment per pull request from a body file with `--body-file` and read it back. A changed head invalidates the table, including a documentation-only head. Do not take the PR out of draft until all rows pass and review and required gates cover the same SHA.

```markdown
### Chore final-head check — run <run_id>

**Head:** <full SHA>

<!-- orchestration-result
{"run_id":"<run_id>","role":"check_agent","kind":"check","head_sha":"<full SHA>","outcome":"pass|fail","criteria":[{"id":"AC-1","disposition":"pass|fail|not_verified","question":null}]}
-->
**Worktree:** clean before and after checks

| Item | Command | Result | Output |
| --- | --- | --- | --- |
| AC-1 | `<exact command>` | pass/fail/not_verified | <labelled fenced output block below> |
| Guard: <name> | `<exact command>` | pass/fail/not_verified | <labelled fenced output block below> |
| Quality: <name> | `<exact command>` | pass/fail/not_verified | <labelled fenced output block below> |

<details><summary>Output</summary>

**AC-1:** <command, exit status and inspected output in one fence>

**Guard: <name>:** <command, exit status and inspected output in one fence>

**Quality: <name>:** <command, exit status and inspected output in one fence>

</details>
```

Include every applicable criterion, guard and quality command, even when there are no guards. The check agent owns the table and its comment; the builder's earlier test report does not substitute for it. The manager links the returned comment URL from the coordination record and reads the posted body back. A failed post or read-back stops `BLOCKED`; the manager never posts substitute evidence.

Label each quoted output block `Full output` or `Excerpt`, as the change-set verifier's `references/verification-comment.md` does. Mark every cut, including a cut at the beginning or end, with `[… <n> lines omitted]` and the exact count. Put the command and exit status in the same fence as the inspected output. Use a fence longer than any run of backticks or tildes inside it.

The check agent writes the marker on its full final-head table. Fill `criteria` from every `AC-n` row, excluding guards and quality commands. Set `outcome` to `pass` only when every criterion, Regression Guard, and profile quality command passes; otherwise set `fail`.
