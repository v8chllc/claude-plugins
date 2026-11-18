# Run state and published records

Run state lives on the run issue and the pull requests. Local scratch files are disposable and are never evidence.

## Authorship

The manager coordinates and records; it never writes review or evidence text. A read-only role, such as the plan agent, returns its text and the manager posts it unedited and reads the posted body back. A role with shell access, such as a reviewer, verifier, or chore check agent, posts its own result. The manager links that comment from the coordination record and reads it back. A failed post stops the run `BLOCKED`; the manager posts nothing in its place. The manager authors only its coordination records, terminal snapshot, plan when applicable, retrospective, sponsor decisions it witnesses, and finding disposition comments. Every role follows this rule.

Every fact has one owner. The run issue owns what belongs to the run: why it exists, its criteria, the plan, the coordination record, the snapshot, and the retrospective. Each pull request owns what belongs to its repository: the diff, the review cycles, the verification comment, and the merge. Neither restates the other; they link.

## The run issue

An issue in the resolved `coordination_repository`, created by the sponsor before kickoff. Each repository issue the run needs is one of its sub-issues. The manager reads it and writes comments on it, and never creates, edits, or closes an issue.

Before the run's home is confirmed, there may be no valid run issue to write to. If the run issue cannot be read, `coordination_repository` cannot be resolved or conflicts, or the run issue is outside that repository, the manager posts nothing: no coordination record, terminal snapshot, or retrospective. The terminal output carries the retrospective in the shape below and the signal states why the run stopped. A missing sub-issue for a repository whose `tracking` is `required` is checked after the home is confirmed; that stop uses the valid run issue for its record, snapshot, and retrospective. Each orchestrator's readiness and resolve steps specify its routing and signals.

A run issue can hold several runs: a retry after `NEEDS_REFINEMENT` is a new `run_id` on the same issue, a unit of work split across two pull requests gets one run per pull request, and a corrective run continues a pull request an earlier run left open. Every comment below carries its `run_id`.

## Corrective run

A corrective run is a new `run_id` on the same run issue that continues a pull request an earlier run left open and unmerged, to deliver scope the sponsor added or corrected after that run ended. It is not the next part of a split unit: that part starts only after the earlier one merges, opens its own pull request, and takes a baseline that includes the merge. A corrective run needs no merge, because it changes the pull request the earlier run opened.

- **Declared by the run issue.** A run is corrective only when the run issue's own text says this run continues an earlier run's pull requests. A kickoff, a comment, or an inference from open pull requests never makes it so. When an earlier run on the issue left a pull request open and unmerged and the run issue declares no continuation, readiness stops with `NEEDS_REFINEMENT`: whether to continue that pull request or open a second one is the sponsor's choice.
- **Checked at readiness,** for each pull request continued. It is open and unmerged; a merged one makes this a next-part run, so stop with `NEEDS_REFINEMENT`. Its head equals the `head_sha` in the earlier run's terminal snapshot; a head that moved means another writer pushed, so stop `BLOCKED`, naming the commit.
- **Checkout.** Each repository's checkout is on the continued branch at that head, clean, in place of the default branch.
- **Record.** Each repository entry carries `continues`: `{"run_id": "<earlier run_id>", "head_sha": "<its snapshot head_sha>"}`, or `null` in a run that continues nothing. `branch` and `pull_request` name the continued ones from the run's first record. `baseline` is the merge base of the continued branch and the default branch, so review and verification cover the whole pull request, not only this run's commits. The earlier run's records, snapshot, and retrospective are its history and are never edited.
- **Bringing the branch current.** When the default branch has moved and the pull request no longer merges cleanly, the builder brings the branch current before implementing. Where the profile's `merge_method` is `rebase`, it rebases the branch onto the default branch and pushes with `--force-with-lease=<branch>:<head_sha>`, the `head_sha` from `continues`. That push is the one force-push a run may make: only of the continued pull request's own branch, never a default branch, and only before this run's first review. Under any other merge method it merges the default branch in. The builder resolves a mechanical conflict, such as two version bumps to the same literal. A conflict whose resolution the acceptance criteria do not settle, because it would change behavior or choose between two rules, is a question for the sponsor, never the builder's call.
- **Plan.** The plan covers every criterion of the run issue as it now reads, earlier and added alike, and names which ones the continued head already satisfies, citing the earlier run's result comment. Citing is not verification: verification checks every criterion again.
- **Implement.** New commits on the continued branch. History is never rewritten except by the rebase above. A release step the pull request already carries past the default branch, such as a version bump, counts for this run and is not repeated.
- **Publish.** No new pull request. Return the continued one to draft and append a record naming it.
- **Review and verification.** The run's review budget is its own, never what the earlier run spent. Review continues the pull request's own history: the review capability's recovered scope, a delta from the last reviewed head, stands, because every cycle is given the current plan and verification checks every criterion again. An unchanged head covered by the latest clean review takes the no-delta path below; a revised plan alone does not require another invocation. Only when the last reviewed head is no longer an ancestor of the branch, as after the rebase above, does the first review cover the full diff from `baseline`. Verification is never carried over: check every criterion anew, even when the head is unchanged.
- **Terminal.** The run writes its own snapshot and retrospective; the retrospective names the run it continued.

## What each skill names

This contract is shared by every orchestrator skill. Each skill's `SKILL.md` has a "Run records" section that names four things:

- its **workflow**, the skill's own name, recorded in the required `workflow` JSON field;
- its **run identifier prefix**;
- its **heading word**, used in the plan and retrospective headings;
- its **phases**, the values `phase` may take, in workflow order;

plus any **extra record fields** it adds, and its proof comment. The examples below use `change-set-orchestrate`, whose `workflow` is `change-set-orchestrate`, whose prefix is `change-set`, and whose heading word is `Change Set`.

## Record types and workflow identity

Every orchestrator writes the same two exact markers: `<!-- orchestration-record`
for a coordination record and `<!-- orchestration-snapshot` for a terminal snapshot.
The manager also writes `<!-- orchestration-retrospective` on its retrospective;
change-set and feature managers write `<!-- orchestration-plan` on each accepted
plan revision. A decision's witness writes `<!-- orchestration-decision` on the
run issue. The change-set and feature verifiers and the chore check agent write
`<!-- orchestration-result` on their pull request evidence comments. The review
capability's own marker continues to identify each review report.
The JSON object inside every orchestration marker requires `run_id` and `role`. A code-bound decision or result for one repository requires its full 40-character `head_sha`; a decision covering several repositories' code carries a sorted `heads` map from full `owner/repo` names to full 40-character SHAs. A feature result additionally carries the complete `frozen_commits` map. The terminal snapshot binds code through the full `head_sha` in each applicable `repos` entry. The plan and retrospective markers make no independent current-head code claim. The writer sets `role` to `manager`, `supervisor`, `verifier`, or `check_agent` as assigned below. Markers are records, not authority: a role value describes its claimed writer and grants no permission or authenticated identity. Scope authority stays with sponsor-approved issue-body edits, additional-review authorization with its authenticated URL handoff, and merge authority with the sponsor.

The JSON object inside the coordination and snapshot markers requires `workflow`, exactly one of
`change-set-orchestrate`, `feature-orchestrate`, or `chore-orchestrate`, alongside
the required fields documented below. Each skill declares its own value; the
marker identifies the record type, never the workflow. Workflow-specific phases
and extra fields are interpreted using `workflow`.

Consumers select the exact marker for the record type, parse its JSON, and select
the current `run_id`; a snapshot is never a coordination record. Require a valid
`workflow` matching the run's selected skill and reject a missing, unknown, or
mismatched value rather than inferring it from the run ID. Resume from the latest
complete coordination record for that run and workflow.

This is a breaking format change: writers and readers use only these shared
markers, with no legacy-marker compatibility. Historical comments remain
unchanged. Roll out between runs with no pending corrective run dependent on the
previous format.

## Run identifier

One `run_id` per invocation: `<prefix>-<UTC YYYYMMDDTHHMMSSZ>`, such as `change-set-20260915T142530Z`. A correction after a terminal signal starts a new `run_id` and never edits an earlier record.

## Run scratch directory

Every file a run writes outside its repositories' checkouts lives in one directory, `${TMPDIR:-/tmp}/<run_id>/`: the prepared plan file, comment bodies written for `--body-file`, check scripts and their output, and any baseline or scratch checkout. Nothing a run writes goes anywhere else outside a checkout, so one removal leaves nothing behind.

- The manager creates it at resolve with `mkdir -p -m 700 "${TMPDIR:-/tmp}/<run_id>"`, and gives its path to every agent and skill the run dispatches. A resuming manager derives the same path from the `run_id`, and creates it again if it is gone.
- An agent writes its temporary files only there, in a subdirectory named for its role and round, such as `verify-1/`. It never writes them inside a checkout, and never removes the directory.
- Published text never names the directory's absolute path. Cite a scratch file by its path inside the directory, such as `verify-1/checks.py`, and publish its content wherever a reader needs to re-run it.
- The manager removes the directory once, after the retrospective is posted, on every terminal path that created it: `rm -r -- "${TMPDIR:-/tmp}/<run_id>"`, then `git -C <checkout> worktree prune` in each repository checkout, so no worktree stays registered there. A file removed sooner, such as the prepared plan file, is removed with `rm -- <file>`.
- Never remove with `-f`, `--force`, or a short-flag group that contains `f`, such as `-rf`. Codex refuses a forced `rm` when approvals are off, as they are for a headless manager, so a run that relies on one leaves its files behind.

## Coordination record

A marker comment on the run issue, **appended** at every phase change and whenever a pull request opens. Never edit one. Each marker is complete, not a delta: a fresh manager resumes from the latest marker for the current `run_id`, and the earlier markers are the run's history.

```text
**change-set-orchestrate** run change-set-20260915T142530Z — phase `implement`

<!-- orchestration-record
{"workflow":"change-set-orchestrate","run_id":"change-set-20260915T142530Z","role":"manager","phase":"implement","repos":[{"name":"<owner/repo>","work_item":"<repository issue URL, or null>","baseline":"<sha>","branch":"<branch>","profile_inherited":["merge_method"],"profile_defaults":["autonomy"],"pull_request":null,"continues":null,"proof_repair":{"consumed":false,"trigger_result_url":null,"reviewed_sha":null,"test_only_sha":null,"result_url":null},"additional_review":{"supervisor_identifier":null,"supervisor_identity_source":null,"authorization_url":null,"reviewed_commit":null,"review_result":null,"fix_commit":null,"consumed":false}}],"plan":"<plan comment URL, or null>","plan_accepted":true,"review_invocations":{"<repo>":1},"relays":[{"approved_at":"2026-09-15T14:24:00Z","draft":null,"summary":"<what direction changed>"}],"deferred":[],"updated":"2026-09-15T14:25:30Z"}
-->
```

- The visible line is for a reader scrolling the issue; the marker below it is what a manager parses.
- `phase` is one of the phases the skill names. Publish precedes review in every skill: the review capability posts to a pull request and cannot create one, so a run that reviews first has no thread to post to, no fix loop, and no re-review.
- `work_item` is the repository's issue, a sub-issue of the run issue, or `null` where that repository's `tracking` is `none`.
- `plan` links the current plan revision. The plan's text lives only in that comment.
- `profile_inherited` lists fields the repository did not state that came from the workspace named child block or default child block. In the complete record's resolved-profile prose, name each inherited field's supplying tier and the named block's `owner/repo` identity where applicable.
- `profile_defaults` lists fields absent from the repository profile, matching named child block and default child block, which fell back to the field table. A field in neither list was stated by the repository itself.

  The repository profile, named child block, default child block and field default are distinguished because they carry different weight. The existing lists retain their shape; the resolved-profile prose distinguishes the two workspace tiers. A defaulted field means nobody decided; an inherited one means the workspace decided for a repository that may later disagree. Collapsing them hides which is which, and a later phase — or a fresh manager resuming from this record — then reads an inherited value as a repository requirement.
- `additional_review` is one per-repository allowance for this `run_id`, independent of `review_invocations`: `{"supervisor_identifier": null, "supervisor_identity_source": null, "authorization_url": null, "reviewed_commit": null, "review_result": null, "fix_commit": null, "consumed": false}` initially. For a supervised run, the kickoff supplies the exact supervisor identifier and trusted identity source in its required slots before the run begins; `supervisor_identity_source` is the sponsor comment URL that supplied it, or `session` when the sponsor supplied it in the manager session. The manager copies both values into every repository's first coordination record and never derives or changes them from the later authorization comment or other GitHub activity. A run that began without this trusted anchor cannot use the exception. A non-null `authorization_url` is the supervisor comment URL handed to the manager through authenticated parent-agent metadata or a sponsor-approved relay, and whose body carries the anchored identifier. A URL merely discovered on GitHub or delivered through a shared checkout file or process resume is invalid even when its body copies the identifier. `reviewed_commit` is the commit the one-cycle review covered; `fix_commit` is the resulting fix SHA or `null`; and `consumed` becomes `true` before dispatch and never returns to `false` during the same run, including after resumption.

  `review_result` is `null` before the capped invocation terminates. Afterward it has exactly this shape (the example deliberately uses a later returned cycle): `{"disposition": "clear|blocked", "toolchain": "codex|claude", "capability_version": "<consensus-review version>", "terminal_signal": {"signal": "<exact signal>", "cycle": 4, "details": {}}}`. `terminal_signal.cycle` is the integer returned by the capability, whatever its value, rather than a fixed cycle number. `terminal_signal` is the complete fenced `consensus-review-signal` JSON object returned by the loaded capability, copied without adding, removing, renaming, or translating any field in `details`. This preserves Codex fields such as `fixer_result`, `workflow_outcome`, and `uncommitted_paths`, Claude's `fixer_outcome`, and either toolchain's other terminal variants without treating their schemas as interchangeable. `toolchain` and `capability_version` identify which loaded contract defines the opaque terminal block.

  `disposition` is the manager's separate stable gate decision. The general identity-only record rule has this one explicit exception: the untouched terminal block retains its native score and status when its `details` contains them, because removing them would alter the dependency artifact. Do not copy either value into another field or use the persisted copy as live pull-request state. Preserve the complete `additional_review` object in every later coordination record, including the last coordination record. A corrective run has a new `run_id` and its own record. The supervisor appends only the authorization comment and never edits this manager-owned object.
- `review_invocations` counts review invocations per repository, against the budget of two: calls of the declared review skill. It does not count the review-and-fix cycles inside one invocation, of which there are up to three.
- **Clean-review coverage and no-delta record.** The current pull request head is covered only when it equals the reviewed head SHA named by the latest clean review comment on that pull request. Identify completed reviews from the manager-owned coordination records across runs on this pull request, in record-append order; the last completed review wins across reviewers and capabilities. Under `consensus-review`, a clean result requires a posted final-cycle comment URL and a terminal `REVIEW_COMPLETE` with a clean status, or a `CAPPED_REVIEW_COMPLETE` that meets the clean, no-fix rule below. Under `agent-tooling-review`, a clean result requires the latest posted cycle report at the current full head, its successful terminal signal, no open blocking or major finding, and a terminal disposition for every finding from every cycle, as `agent-tooling-review-loop.md` defines. `NO_DIFF`, an acknowledgment, a pending review, and `REVIEW_COMPLETE_WITH_FINDINGS` never establish coverage. If the latest completed review’s result, head, or comment identity is missing or ambiguous, treat the head as uncovered. A clean review of an older head cannot cover a different current head, and an earlier clean comment cannot override a later review that changed the review state. Before review accounting, the manager checks that identity and, when it matches, appends a distinct no-delta comment to the pull request naming the covering review comment URL and the unchanged head SHA. This is a no-delta record, not a review cycle or a new review comment; it does not increment `review_invocations`. Link the no-delta URL in the visible text of the next complete coordination record, without changing the record schema. For a revised plan, compare the unchanged pull request diff against every revised criterion, record the comparison and plan revision in that no-delta comment, and proceed to verification only if the diff still satisfies the plan. The sponsor may explicitly order a fresh review of the unchanged head; record that direction and use the normal review invocation gate. A moved or uncovered head requires review, except for the feature workflow’s or change-set workflow’s consumed, recorded automatic test-only fix round, with an exact tests-only delta from the last clean reviewed head and fresh verification of affected criteria and paired sponsor rows at the current head as defined below.
- **Charged-invocation trace.** For each charged invocation, reconcile the returned review cycle comment URL or URLs with the pull request. Append a complete coordination record whose visible text names the reviewed head, completion outcome, and comment URL or URLs; if none was posted, name the charged invocation, head, and concrete no-comment outcome, including `NO_DIFF`, interrupted dispatch, or the observed failure. A charged count alone never implies a posted review or a clean head.
- `relays` is an append-only list of sponsor relays received by this manager, each `{"approved_at":"<UTC timestamp>","draft":"<path, or null>","summary":"<what direction changed>"}`. The next coordination record after receipt includes the new entry and preserves earlier ones. The status block for that turn names the same relay. The supervisor's local verbatim relay log is separate from this published summary.
- `continues` names the earlier run and head a corrective run continues, or `null`; see Corrective run.
- `updated` is the UTC time the marker is written, read from the clock at write time (`date -u +%Y-%m-%dT%H:%M:%SZ`), never estimated or copied from an earlier record.
- `deferred` holds manager-owned records of scope pushed out of this run:
  `{"summary": "...", "reason": "...", "work_item": null, "repository": null}`. The optional `repository` is an `owner/repo` string naming one member of `repos`; absent or `null` means run-wide. A value outside the participating repositories is a record error the manager reports, never silently drops. Before each review invocation, prepare a filtered input of the unchanged canonical list containing only entries for that repository and run-wide entries. Never remove or edit an entry to tailor the review input. In a single-repository run the input remains the same list unless an entry explicitly names a different repository, which is a record error. The builder
  prepares the record and the manager preserves it. An authorized supervisor
  independently corroborates confirmed findings and may create separately
  tracked Backlog follow-ups under the supervise skill; when there is no
  supervisor, the sponsor receives the record. The manager and builder do not
  create issues. A follow-up issue is a separate planning artifact: its URL
  stays in the supervisor's local finding-to-issue mapping and sponsor report,
  never written back into this active run's `deferred` record, issue body,
  coordination comments, plan, snapshot, or pull request evidence.
- A skill's extra record fields sit beside these. They never rename or repurpose a shared one.
- The record holds identity — URLs, SHAs, branch names — and the run's own state. It never copies a pull request's state, such as open, a review score, or check results; read those from the pull request.
- Only the manager writes markers, one at a time.

### Review invocation gate

Before each new budgeted review invocation, first apply the clean-review coverage and no-delta rule above, unless the sponsor explicitly ordered review. The manager then completes one preparation boundary for the repository being reviewed. It checks the remaining review budget and resolves the pull request from the latest record. It validates every `deferred.repository` against the run's repository set, then prepares only entries owned by this repository or run-wide entries without changing the canonical list. It reads that pull request's current head SHA from the platform, confirms local `HEAD` equals that observed platform SHA, and uses the matching SHA as the validated head input for this invocation. A fresh or resumed manager performs this check again before a new invocation; a stale head supplied by an earlier preparation is never reused. Under `consensus-review`, the manager also takes the non-null plan URL from the latest record, fetches that comment's exact, non-empty body into a readable file in the run scratch directory, and pairs the file with `plan_source` `supplied: <plan comment URL>` and the prepared `deferred` input. For a change-set or feature `consensus-review` invocation, the manager also fetches the applicable `Acceptance Criteria` and `Regression Guards` sections from both the run issue and this repository's work item (when non-null) into a separate, non-empty readable file in the run scratch directory. Label each source with its issue URL, preserve each section's wording and `AC-n` identifiers verbatim, and omit only absent sections. The run issue may add shared criteria or guards even when the repository work item exists; include those alongside the repository sections. It passes that file as the skill's acceptance criteria and Regression Guards input. Keep the file paired with this invocation's validated head and plan source; do not substitute another issue's criteria or guards. When a correction round has posted a new plan revision, the latest record points to that revision, so this preparation never falls back to an earlier one. The manager owns the prepared plan file and, when applicable, the criteria-and-guards file through the invocation and removes each with `rm -- <file>` on every path out after the review agent finishes or dispatch is abandoned. For `agent-tooling-review`, materialize the latest plan comment verbatim with its URL and `plan_source` in the same readable file shape; record its `updatedAt` and recheck it before charging. When the workflow has no plan comment, use its run-state overlay to materialize the run issue and any non-null repository issue bodies verbatim with their URLs. For workflows with a plan comment, a changed plan comment after a confirmed charge leaves the slot consumed and stops for sponsor disposition. Recover the capability's next cycle number through its bundled poster before each review-agent dispatch, as `agent-tooling-review-loop.md` defines. These checks validate and materialize every required input before accounting; a missing, unreadable, or mismatched input or an exhausted budget follows the skill's existing stop or sponsor-escalation rule and consumes no slot.

Only after preparation succeeds does the manager increase that repository's `review_invocations` count by exactly one, append a complete coordination record, and confirm the posted body by reading it back under the skill's comment-posting and read-back rule. Only after the charge is confirmed may the manager dispatch the review agent. If posting or read-back fails, do not dispatch; report the actual failure. A synchronized sibling needs its own preparation and confirmed charge before its own invocation.

The review agent confirms immediately before invoking the declared capability that the prepared plan file and any prepared criteria-and-guards file remain readable and that the checkout and pull request still have the prepared head. These are post-charge invariant checks, not deferred input preparation: their failure reports that prepared state changed after accounting, and the charged slot remains consumed. The agent never fetches or substitutes a plan after dispatch.

One completed invocation consumes one slot. Internal consensus-review review-and-fix cycles and an orchestrator's continuation of the same invocation consume no additional slots. Under `agent-tooling-review`, one charged invocation contains at most three single-cycle reviews and retained-builder corrections; internal cycles consume no additional slots. Every later budgeted invocation, including one after corrections, passes through this gate again. Verification does not change `review_invocations`.

If execution stops after the increased count is confirmed but before dispatch, the slot remains charged and the charged-invocation trace names interrupted dispatch when no comment exists. On resumption, use the latest confirmed coordination record: never silently decrement or reset its count, and never infer that a charged invocation was unused. If whether review launched or remains running is uncertain, ask the sponsor before another dispatch. When the sponsor confirms that review never launched, resume the existing charged invocation: rerun the preparation boundary's read-only checks against the current pull request and local `HEAD`, recreate the readable temporary plan file from the latest record's plan comment under `consensus-review` or `agent-tooling-review` (or the issue bodies under the chore overlay), and for change-set or feature `consensus-review`, recreate the criteria-and-guards file from the applicable run issue and repository work-item sections with the same source labels and verbatim content, and dispatch with those newly prepared inputs without increasing `review_invocations` again. This preparation replaces the disposable inputs lost during interruption and never reuses a stale prepared head. If preparation fails, follow the gate's existing stop or sponsor-escalation rule and leave the slot charged. Additional budget still needs the skill's existing sponsor approval. The charged count records budget consumption only; it is not evidence that review started or finished, or that review covered the current head. Establish those facts from the review's actual artifacts.

### Advisory consensus-review handoff

`REVIEW_COMPLETE_WITH_FINDINGS` is a completed, posted review of `reviewed_sha`, with `score` and `status` still `passing`. Its `review_url` names the posted report; `open_findings` gives ordered `{id, section}` pairs from `Should Fix` only. The review skill has not run its fixer for this signal. Confirm that the pull request's current head and local `HEAD` both equal `reviewed_sha` before deciding or verifying; a mismatch returns to the review invocation gate. Read the report at `review_url` for the finding text. Do not infer a clean review from the passing score alone.

For each returned finding, record exactly one decision on the pull request against `reviewed_sha`: `declined` only with a reproduction showing the finding is wrong, `deferred` with a work-item record in the run's `deferred` list, `fix_requested`, or escalated to the sponsor with a `orchestration-decision` marker. Record all IDs and sections in signal order and post the complete disposition comment before verification. A decision to defer without a filed issue still gets a work-item record for the authorized supervisor or sponsor; the manager does not create the issue. A `fix_requested` decision is provisional; `declined` and `deferred` are terminal. If any ID is missing, duplicated, or undecided, stop before verification. A head with all findings declined or deferred may continue to verification or scope on that same reviewed SHA.

For `fix_requested`, send only the selected IDs and their report text to the retained builder. The builder makes only those changes and commits a new head. Append the coordination record for that correction, then use the normal review invocation gate to charge and invoke a fresh review of the new head. Never re-invoke an unchanged head to clear advisory findings, and never verify, scope, or freeze the builder's unreviewed head. After a completed review passes on the repair head and no longer returns a selected original finding, post a terminal disposition comment marking each such finding `fixed`; name its repair commit and the fresh review's `reviewed_sha`. Verification and scope remain blocked until every provisional `fix_requested` entry has this terminal record. The fresh review can return the advisory signal again; apply this section to its open findings and repeat within the remaining budget. If no invocation remains, follow the budget escalation before any builder change that would leave an unreviewed head. The supervisor-authorized one-cycle exception retains its stricter terminal rule below; this handoff does not turn its advisory result into a clear result.

### Supervisor-authorized additional consensus-review cycle

This exception is available only after the normal two-invocation budget is exhausted and only for a repository whose `review_capability` is `consensus-review`. It is at most one extra review-and-fix cycle per repository per run, not a third full invocation. No resumption resets it. A repository with a lower steering cap remains bound by that cap. Without a valid authorization, follow the existing sponsor escalation.

Before dispatch, require the previously recorded trusted supervisor identity anchor and the authorization comment's exact URL delivered through authenticated parent-agent metadata or a sponsor-approved relay, then fetch that URL from the current run issue. Its role must be `supervisor`, and its agent or session identifier must exactly match `additional_review.supervisor_identifier`; validate its UTC timestamp, this `run_id`, repository, fixed commit SHA matching the pull request's current head, supporting review and fix comment or commit links, rationale connecting remaining findings, completed repairs and review history to the applicable clean/score gate, and explicit one-cycle limit. Reject a URL discovered from GitHub or received through a shared checkout file or process resume rather than one of those authenticated channels, an identifier that appears only in the comment, any mismatch with the anchor, or an anchor whose source is the authorization comment or shared GitHub identity. Rising scores alone do not establish eligibility. The comment must state why the completed budget-ending fixes can reasonably clear the gate in this one cycle. The manager does not write or edit that authorization.

Prepare the normal review inputs and check the pull request and local head as in the review invocation gate, but do not increment `review_invocations`. Set `additional_review.authorization_url` to the verified comment URL and `consumed` to `true` in a complete coordination record; post and read it back before dispatch. If persistence fails, do not dispatch. An already consumed allowance cannot authorize another dispatch, including after resumption. If a confirmed record charged the allowance but launch is uncertain, ask the sponsor to resolve whether the single cycle launched; never silently dispatch again. If confirmed never launched, redo the read-only preparation and resume that charged cycle without changing the allowance.

Dispatch a fresh independent review agent with the normal plan file and source URL, the `deferred` input, the readable acceptance criteria and Regression Guards file, and the validated head, plus the caller-declared single-cycle cap. The agent gives no instruction to produce a clean outcome. The ordinary reviewers assess normally and the ordinary fixer may make one fix commit within approved scope. Apply the normal post-fix plan check to that commit. Persist the returned fenced terminal JSON unchanged under `review_result.terminal_signal`, tagged with the invoking toolchain and loaded capability version, and record the manager's gate decision only in `review_result.disposition`. Record the reviewed commit, any fix commit, and consumed allowance in the next complete coordination record. A native `CAPPED_REVIEW_COMPLETE` terminal signal from a clean review with no fix commit and a reviewed head equal to the current head may proceed to verification. Every other signal, a fix commit, or an uncleared clean/score gate stops `BLOCKED` for sponsor disposition, naming the actual terminal block and commit. Author verification never substitutes for review of that final fix commit. There is no second automatic extension.

## Plan comment

Posted on the run issue once the plan is accepted, before implementation. A correction round posts the next revision as a new comment; an earlier revision is never edited.

```markdown
### <heading word> plan — run <run_id>, revision <n>

<the accepted plan, as the plan agent returned it>

<!-- orchestration-plan
{"run_id":"<run_id>","role":"manager","workflow":"change-set-orchestrate|feature-orchestrate","revision":1,"written":"<UTC>"}
-->
```

The manager appends this marker to every accepted plan revision, after the
unaltered plan text. `revision` is the heading's integer revision; the plan
records intended work and makes no current-head code claim. A corrective plan
that cites an earlier result still leaves code coverage to current-head review
and verification.

## Pull request body

Each pull request links both ways:

- `Closes #<n>` for its own repository issue, when `work_item` is not `null` and this pull request completes that issue. Same repository only. When a unit of work is split across pull requests, only the last one closes the issue; each earlier one names it on a plain line, `Part of #<n>`, so merging it leaves the issue open for the rest.
- One plain line naming the run issue: `Run: <run issue URL>`. Never a closing keyword: a cross-repository keyword closes the run issue when the first pull request of a pair merges.

## Verification comment

Each skill names the comment its verifier or check agent posts, and the terminal snapshot links its full URL as `verification_comment`. Every full proof comment carries exactly one `orchestration-result` marker with `run_id`, `role`, `kind`, `head_sha`, `outcome`, and `criteria`. `kind` is `verification` with `role: verifier` for change-set and feature, or `check` with `role: check_agent` for chore. `outcome` is `pass` or `fail` for feature, change-set, and chore, according to their full table. `criteria` is an ordered array with exactly one entry per current `AC-n`: `{"id":"AC-1","disposition":"pass|gap|fail|not_verified|underived|pending_sponsor","question":null}`. A `pending_sponsor` entry has its exact nonempty sponsor question instead of `null`. The marker's dispositions agree with the visible current-head table; regression guards and quality commands stay in that table, outside `criteria`. A feature result also includes `frozen_commits`, the full participating commit map; `head_sha` equals this pull request's entry. Feature criterion and coverage rows show their human-readable source issue `owner/repo#n` beside local `AC-n` in the visible result comment, outside the marker. A superseding full proof gets a new marker; an erratum that changes no disposition carries no new result marker. The posting role writes its own body to a file, posts it with `--body-file`, and reads the posted body back; the manager never authors evidence. A failed post or read-back stops `BLOCKED`. A comment is never edited or deleted. For feature runs, the fresh verifier returns one result URL per affected pull request, the frozen commit map, and `pass` or `fail`. The manager verifies each returned URL and head before recording it. For change-set and chore, keep their existing typed full-proof and erratum URL handoff; route only from the returned full proof identity, never the latest comment.

## Terminal snapshot

Appended to the run issue once, when the run reaches its terminal signal, and never edited. Before appending it, settle every delegated agent the manager started: each has returned, or has been stopped with the stop recorded in the final coordination record. If an agent cannot be confirmed stopped, append a coordination record naming each unsettled agent and the failed stop as a `BLOCKED` hold, ask the sponsor for disposition, and leave the terminal snapshot pending until every agent is settled. A run that stops before its home is confirmed, as described above, appends none. It freezes what the sponsor is handed. For feature and change-set runs, include every `pending_sponsor` row with its exact question in the terminal snapshot at the checked head; these rows are pre-merge review inputs and never a verification result or sponsor checkpoint in this run. The terminal snapshot is the run's last record; after it, post nothing else to the run issue except the retrospective.

```text
**change-set-orchestrate** run change-set-20260915T142530Z — terminal `READY_TO_MERGE`

<!-- orchestration-snapshot
{"workflow":"change-set-orchestrate","run_id":"change-set-20260915T142530Z","role":"manager","signal":"READY_TO_MERGE","repos":[{"name":"<repo>","pull_request":"<URL>","head_sha":"<sha>","review_comment":"<URL of the final review comment, or null>","verification_comment":"<URL, or null>","pending_sponsor":[]}],"written":"2026-09-15T16:02:11Z"}
-->
```

Merge commits are not recorded: the sponsor merges after the run ends, and the pull request records the merge.

## Retrospective

One comment on the run issue per terminal path, including failures and blocked runs, except when the run stops before its home is confirmed as described above. Settle every delegated agent before the terminal snapshot. An unsettled agent takes the `BLOCKED` hold above; do not post a retrospective or terminal snapshot while its stop remains unconfirmed. After the snapshot, the retrospective is the only run-issue post. On a pre-home stop, put the retrospective in terminal output in the same shape, and post no comment. Every posted retrospective includes the marker below; a terminal-output-only retrospective has no posted marker:

```markdown
### <heading word> retrospective — run <run_id>

**Outcome:** <signal>

**Observations**

- <observation> — Adopt | Revise | Defer | Reject — <owner and the check that will confirm it, for Adopt and Revise>

<!-- orchestration-retrospective
{"run_id":"<run_id>","role":"manager","workflow":"<workflow>","signal":"<terminal signal>","written":"<UTC>"}
-->
```

No transcripts, no raw logs, and no restating the diff. An `Adopt` or `Revise` observation without an owner and a future check is incomplete.
The retrospective marker records the run's terminal signal after the
terminal snapshot and makes no independent current-head code claim. The snapshot's `repos` entries carry those full heads.

## Automatic proof-repair identity

Each repository entry in a complete coordination record carries `proof_repair: {"consumed":false,"trigger_result_url":null,"reviewed_sha":null,"test_only_sha":null,"result_url":null}` before verification. Before dispatching the one automatic test-only round, set `consumed` to `true`, bind the full triggering verifier result URL, the last clean reviewed full SHA, and name each affected eligible row with its source issue `owner/repo#n` beside its local `AC-n` in the visible coordination record, then append and read back the complete record. Never reset `consumed` in this run, including after resumption or another failed verification. On return record the full test-only head SHA and superseding full result URL. If dispatch was interrupted, resume that same round from its record; do not allocate a second round. A changed proof result does not reopen eligibility. For feature runs, apply this per participating repository while preserving the complete frozen map.

## Feature participating-set identity

For `feature-orchestrate`, the manager adds `frozen_commits` to complete coordination records and the terminal snapshot: a sorted map of every participating full `owner/repo` name to full 40-character SHAs, or `null` before freeze. Each repository entry has `frozen_sha`, `outcome`, and `result_comment_url`; the latter two are `null` before verification. Feature records carry top-level `waiting_on: null` or a sponsor exception question. When non-null, `frozen_sha` equals its map entry and the result URL points to the verifier's comment at that map. `slices` is an ordered list of repository and commit pairs. The terminal snapshot includes `outcome`, the verifier's `verification_comment` URL, and every `pending_sponsor` row and question. Any participating head change invalidates verification at the old head.

The recorded one automatic test-only fix round for a `gap` or coverage-row `not_verified` is the sole exception to a new current-head review. The manager confirms and records that the delta from the last clean reviewed head contains only tests addressing those rows, freezes the new head, and has the verifier re-verify every affected criterion and paired sponsor row without a separate review or review-budget charge. The prior clean review covers unchanged product code; the new result names both heads. Another test-only change, a documentation change, or a product-code change returns through the review invocation gate; documentation changes re-verify affected criteria and paired sponsor rows, while product-code changes receive full applicable verification.

A surviving gap, a coverage row that a test cannot close, or a criterion's own `not_verified` row keeps all pull requests draft pending a sponsor exception. The manager posts a complete coordination record with `waiting_on` and current result URLs, then obtains and reads back an `orchestration-decision` marker identifying amendment, reasoned override, or stop. An override binds the exact rows, current heads, and result URLs; a later head or result requires a fresh decision. Amendment returns to verification of the amended criterion. Only a read-back override permits merge-ready with a named unresolved row. There is no routine merge route for unresolved proof.

## Sponsor decision marker

Every sponsor decision made in a supervisor session or applied through an issue-body
edit is witnessed by the supervisor, who must append one `orchestration-decision`
comment on the run issue. When the sponsor answers a manager's own question,
the manager must append this marker. The witness posts from a body file and
reads back the comment before linking it. No witness edits an earlier marker.

```text
**supervise** — sponsor decision D-2

<!-- orchestration-decision
{"run_id":"<run_id>","role":"supervisor","id":"D-2","repository":"<owner/repo, or null>","head_sha":null,"decision":"<exact decision>","binds":"criterion|guard|process","amends":"<edited issue URL, or null>","supersedes":null,"source":{"kind":"comment","url":"<sponsor comment URL>"},"decided_at":"<UTC>","written":"<UTC>"}
-->
```

For a proof override, the manager's marker takes this form (using `heads` instead of `repository` and `head_sha` for a multi-repository decision):

```text
<!-- orchestration-decision
{"run_id":"<run_id>","role":"manager","id":"D-3","repository":"<owner/repo>","head_sha":"<current full SHA>","decision":"<sponsor choice; each affected row with source issue owner/repo#n, AC-n, and disposition>","choice":"override","result_comment_urls":{"<pull request URL>":"<current full result URL>"},"reason":"<nonempty sponsor rationale>","binds":"process","amends":null,"supersedes":null,"source":{"kind":"comment","url":"<sponsor comment URL>"},"decided_at":"<UTC>","written":"<UTC>"}
-->
```

For a manager-witnessed answer, set `role` to `manager` and use the same schema. A proof override adds `choice: "override"`, `result_comment_urls` (a map from each affected pull request URL to its current full verifier result URL), and `reason` (the sponsor's nonempty rationale). Its `decision` text names each affected criterion or coverage row with its source issue `owner/repo#n` beside local `AC-n`, plus its disposition from the referenced full result; no structured row identifiers are required. It uses `binds: "process"` and `amends: null` unless the sponsor also edits a criterion; an amendment is a separate `choice: "amend"` marker with the edited issue URL, and a stop uses `choice: "stop"`. For an override, bind `head_sha` or `heads` to every affected current full head SHA. Before accepting the marker and again before merge-ready, compare each named source issue, local criterion, coverage kind where applicable, and disposition with the visible current-head result comment and require an override-eligible disposition: a feature criterion row may be `gap` or `not_verified`, a feature coverage row may be `gap` or `not_verified`, and a change-set criterion row may be `not_verified` or `underived`. Reject `pass`, `fail`, `pending_sponsor`, and `skipped`, and reject any other disposition not explicitly allowed for that workflow and row type. Compare every recorded head and result URL to the current proof identity. A changed head or a superseding result invalidates the override even when the head is unchanged; obtain a new sponsor decision. Do not interpret the generic `decision` text as an override when these fields are absent.
For a decision tied to one reviewed pull request head, including a finding
escalation against `reviewed_sha`, set `repository` to that full `owner/repo`
and `head_sha` to the exact full 40-character reviewed SHA. A later head does
not inherit the decision. For a decision jointly tied to several reviewed
heads, set `repository` and `head_sha` to `null` and add `heads`, a sorted map
of every applicable `owner/repo` to its full 40-character SHA. A process
decision or sponsor-approved issue-body edit that does not cover a code head
sets `head_sha` to `null` and omits `heads`. Do not infer a code head from the
decision's posting time, source URL, repository alone, or a later snapshot.
`id` is `D-n`, unique and increasing on the run issue, including corrective
runs. `binds` is `criterion`, `guard`, or `process`; the first two require
`amends` to name the sponsor-approved edited issue, and `process` requires
`null`. `supersedes` names a replaced decision ID or is `null`; current
markers are those no later marker supersedes, in comment order. `source` is a
sponsor comment URL or `{"kind":"session"}`. The marker records a witnessed
choice; the role field and comment author do not authenticate or grant authority.
