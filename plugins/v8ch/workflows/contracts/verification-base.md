# Shared verification base

`feature-orchestrate` and `change-set-orchestrate` use this contract for the parts of verification they share. Their own verification references define different dispositions and any additional checks.

## Criteria and evidence

A feature or change-set criterion may end with `— sponsor judgement: <question>`. The question must be nonempty, and the issue must name a separate, check-decided `AC-n` criterion paired with it. Readiness rejects either omission. Chore does not accept this form: every chore criterion remains command-decided. A criterion without this form follows the ordinary verification rules below.

For a sponsor-judged criterion, verify that its paired criterion passes and that the state the sponsor must judge is reachable at the checked full head. Record the operation or journey steps that reproduce that state at that head, the paired criterion identifier and evidence locator, and the exact question. Give the sponsor-judged row `pending_sponsor`, never a verifier's `pass`, only when the paired criterion is `pass` and the judged state is reachable. Otherwise give the sponsor row `not_verified`, cite the paired criterion's disposition and evidence or the unreachable state, and state what would make judgement possible. A pending row is excluded from the workflow's overall verification result and does not stop the run from reaching merge-ready. The sponsor judges it during pre-merge review at the merge-ready head. A failed judgement is fixed by a corrective run continuing the open pull request. The verdict is not a regression test; the paired criterion is the lasting guard. Whenever a paired criterion is re-verified, re-verify its sponsor-judged row at the same head; never carry forward an earlier `pending_sponsor` disposition.

Read each current issue criterion by its `AC-n` identifier. Run the applicable check at the current full head SHA, inspect its output, and give the criterion a locator to that check and output. A visible-user criterion needs a rendering test or journey step. A check that can skip must show that its query actually ran. When in doubt whether a test would catch a regression, break the behavior in a scratch worktree and see whether the check fails.

A criterion whose outcome requires a state reached through an operation needs a check through that operation. A canonical fixture counts when built by that operation, or when a passing conformance test ties it to the operation's output. If the real path cannot run, use the workflow's unverified disposition; a direct-state fixture alone does not establish the criterion.

## Head and record

The independent verifier works at a clean checkout of the current reviewed or frozen full SHA. A moved head invalidates the result; the workflow's review and head-change rules determine the next step. The verifier authors and posts its own result comment from a body file with `gh pr comment --body-file`, reads the posted body back, and returns the exact comment URL and checked SHA. A failed post or read-back stops `BLOCKED`; the manager posts no substitute evidence.

The visible summary names the head and result and lists every `pending_sponsor` row with its exact question. The detailed record names each `AC-n`, its disposition and locator, the commands run, exit status, inspected output, Regression Guards and profile quality commands. Label every quoted output block `Full output` or `Excerpt`. Mark every cut, including the beginning or end, with `[… <n> lines omitted]` and the exact count. A summary never substitutes for inspected output.
