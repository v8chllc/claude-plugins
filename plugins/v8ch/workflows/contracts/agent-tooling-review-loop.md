# Agent tooling review loop

Use when a workflow's resolved `review_capability` is `agent-tooling-review`.
The loaded skill performs one read-only review cycle and posts its own report.
Only the retained builder writes to the target branch. The manager never writes,
edits or copies a review report. Apply `finding-policy.md`; this contract changes
the severity gate and invocation mechanics, not the authorization requirements
for declining findings, the scope boundary, class audits or deferral records.
The workflow's own review budget and post-pass step remain in its skill.

## Preparation and budget

Follow the workflow's run-state reference: prepare the current head, issue
bodies, readable plan file, `plan_source` and filtered deferred entries, then
charge and read back the complete coordination record before dispatch. One
charged invocation contains up to three completed review cycles. Recover the
next cycle number from the loaded skill's bundled poster (`--recover`) before
each dispatch. Numbers remain cumulative across invocations; a new invocation
does not reset pull request history. Never exceed the workflow's review budget.

On resumption, read the latest record, pull request reports, disposition
comments and fix commits to establish the active invocation, its completed
cycles and pending work. Do not reset its count, repeat an uncertain dispatch
or charge an internal cycle. If launch or accounting cannot be reconciled, ask
the sponsor before proceeding.

## Review, disposition and correction

1. Dispatch a fresh workflow review agent with the prepared inputs and recovered
   cycle. Immediately confirm local and pull request heads match the prepared
   SHA. The agent invokes the loaded skill once in orchestrated mode. Require a
   successful terminal signal, posted report read-back, matching cycle, head and
   status, and a current-head report. A mismatch, unavailable capability,
   failed post or missing signal is not a pass; stop `BLOCKED` with the actual
   gap. Never infer success from no findings alone.
2. Send every finding, including unresolved findings from prior reports, to
   the retained builder for exactly one disposition: `fixed` with validation
   evidence, `declined` only when a reproduction shows the finding is wrong,
   `deferred` with a canonical work-item record, or escalated to the sponsor
   with an `orchestration-decision` marker. Safety, privacy, authorization and
   test findings cannot be declined. The manager and builder do not create
   deferred issues. No missing or duplicate IDs may pass the gate. An
   escalation holds the run until the sponsor decides; it is not a clean-review
   disposition.
3. If an in-scope blocking or major finding requires repair, the builder
   pushes one fix commit whose body lists every disposition and the validation
   run. Minor findings alone never trigger a fix commit or another cycle:
   disposition them under the shared policy; unresolved authorization questions
   escalate. Mark a finding `fixed` only with evidence for the correction. Audit
   the fix against issue-defined scope before re-review; revert unapproved
   scope additions.
4. The manager posts one disposition comment from a file, names the reviewed
   head, report URL, finding IDs, dispositions, fix commit (if any) and deferred
   records, then reads it back. Preserve all prior reports and dispositions. A
   new report with no findings never silently clears an earlier undispositioned
   finding.
5. After a fix commit, refresh head and issue-body checks and the readable plan
   file, then repeat with a fresh reviewer inside the same invocation. A changed
   issue after charging follows the workflow's run-state reference. Stop the
   invocation after at most three reviews. A fix pushed after its third review
   remains pending review: use a new prepared, charged invocation if the
   workflow's budget permits. Never proceed to the next step after pass at an
   unreviewed fix head.

## Pass and handoff

Pass only when the review completed at the current local and remote head, no
blocking or major finding remains open, and every finding from every cycle has
a terminal disposition. `clean` or `passing` status alone is insufficient. A
properly declined or deferred finding is dispositioned under the shared policy;
an escalation awaits sponsor decision and cannot pass this gate; the
severity-derived report status is never rewritten by the manager.

Record the final report URL and reviewed SHA, then proceed to the workflow's
next step after pass. A changed head invalidates both review and any later
proof. An exhausted budget with an open in-scope blocking or major finding
stops `BLOCKED`; no supervisor-authorized extra cycle applies to this
capability. Report coverage limits and dispositions with the result; do not
convert missing coverage into findings.
