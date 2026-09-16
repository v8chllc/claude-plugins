---
name: consensus-review
description: Runs an autonomous, evidence-gated consensus code review. Use when reviewing code changes, before pushing a PR, or as the review step in a development workflow. Runs three independent reviewers in parallel, synthesizes a consequence-ranked report with a 1-100 quality score, and posts one review comment per cycle to the PR or MR. On a PR or MR it also fixes and re-reviews, up to three reviews per invocation. Accepts an optional plan file as review context. Scope defaults to all local changes; also accepts a PR/MR number, a base commit SHA, a branch diff, or an explicit file list.
---

# Consensus Review

Three reviewers examine the change independently, a synthesizer ranks their
findings by consequence and scores the result, and — on a PR or MR — one comment
per cycle records it. That comment thread is the audit trail: later cycles
recover it, and it is the only durable *comment* this skill writes. A fix cycle
also writes a commit, whose body carries the fix evidence.

The run is always autonomous. There are no operator prompts and no interactive
branches. It ends with exactly one terminal signal.

## Success criteria

- Three reviewer reports, each with a complete Evidence section.
- One synthesized report carrying a score, a status, and numbered findings.
- On a PR/MR: one posted review comment per cycle, and fix evidence in the fix
  commit body rather than in a second comment.
- Exactly one fenced `consensus-review-signal` block as the last output.

## Inputs

1. **PR/MR number** (optional) — when present, the diff comes from the platform
   and the thread is the audit trail.
2. **Plan file** (optional) — review context only. A plan never sets a severity
   and never deducts points.
3. **Scope** — resolved by the ladder below.

## Scope ladder

Take the first match:

1. **PR/MR number** — fetch with `gh pr diff <number>` or `glab mr diff
   <number>`, reading `DEV_SEC_OPS_PLATFORM` from `.env` at the repository root.
   Before anything else, confirm local `HEAD` equals the PR/MR head SHA. On a
   mismatch, emit `ABORT` with `reason` `head_mismatch` and stop.
2. **Base commit SHA** — `git diff <sha>`, plus `git ls-files --others
   --exclude-standard`.
3. **Branch diff** — the `git diff` range for that branch.
4. **Explicit file list** — `git diff -- <paths>`.
5. **Default** — `git diff HEAD`, plus `git ls-files --others
   --exclude-standard`.

For levels 2 and 5, read each untracked file in full and include its contents in
the diff, labeled as a new file.

If the resolved scope is empty, emit `NO_DIFF` and stop.

## Cycle scope

Cycle 01 reviews the full diff.

A later cycle reviews `git diff <reviewed_sha>..HEAD`, where `reviewed_sha` comes
from the latest valid schema-v2 review comment, and also confirms whether the
prior cycle's findings closed. The narrowing is by time, not by file: every
commit since that SHA is in scope whatever it touches, so a regression a fix
introduced anywhere is still reviewed.

Review the full diff, and state that basis in the comment, when there is no
prior review, when the only prior review is legacy schema v1, or when the
recorded SHA is no longer an ancestor of `HEAD`. `recover_context.py` resolves
this and prints both the basis and the reason.

## Roles

Six roles ship with this plugin. Invoke each by its namespaced name, so a
project-level agent sharing a bare name is never selected:

| Role | Invoke as |
| --- | --- |
| Standards review | `v8ch:standards-reviewer` |
| Correctness review | `v8ch:correctness-reviewer` |
| Architecture review | `v8ch:architecture-reviewer` |
| Synthesis | `v8ch:review-synthesizer` |
| Posting | `v8ch:consensus-review-poster` |
| Fixing | `v8ch:consensus-review-fixer` |

Only the three reviewers are delegated, and they run as one parallel batch:
their work is genuinely independent, and none of them reads another's output.
Everything else in the run is yours. Record the delegation mode as
`parallel-subagents`, or `sequential-fallback` if the batch could not run in
parallel and you ran the reviewers one at a time instead.

Pass each role the absolute skill directory, `${CLAUDE_SKILL_DIR}`, in its
prompt. Agents do not receive skill variables.

## Workflow

1. **Recover context.** With a PR/MR number:

   ```bash
   uv run ${CLAUDE_SKILL_DIR}/scripts/recover_context.py <number> --repo-dir <repo-root>
   ```

   Keep the output as `RECOVERED_CONTEXT`. It gives the next cycle number — use
   it, do not recompute it — the scope basis with its reason, and the prior
   reviews in full. Without a PR/MR number, the cycle is `0` and there is no
   recovered context.

2. **Read the repository.** Read the changed-file context a reviewer cannot get
   from the diff alone: the callers, the invariants the change relies on, and
   the failure paths it touches.

3. **Snapshot the working tree.** The reviewers and the synthesizer only read;
   this is how that is enforced. Record both:

   ```bash
   git rev-parse HEAD
   git status --porcelain=v1 --untracked-files=all
   ```

4. **Run the three reviewers in one parallel batch.** Issue all three calls in a
   single response. Give each one the diff, the changed-file context, the plan
   when supplied, `RECOVERED_CONTEXT` when it exists, and
   `${CLAUDE_SKILL_DIR}`.

5. **Apply the evidence gate.** A reviewer output without an `## Evidence`
   section carrying both `Files examined` and `Commands run` failed its pass.
   Rerun that reviewer once. On a second failure, emit `EVIDENCE_FAILED` with
   the failed pass names and stop, with no score.

6. **Re-check the working tree.** Take the step 3 snapshot again and compare. On
   any difference, emit `ABORT` with `reason` `read_only_role_mutated` and post
   nothing.

   The comparison covers new commits and changes to tracked and untracked paths
   inside the repository. It does not cover ignored paths — reviewers run the
   repository's lint, type, and test commands, which write caches there — nor
   anything outside the repository. Those limits are why the roles are also told
   not to write, rather than relying on this check alone.

7. **Synthesize.** Invoke `v8ch:review-synthesizer` with all three outputs
   labeled in full, the delegation mode, the plan source, and
   `RECOVERED_CONTEXT`. It decides the score and the status; you do not
   recompute either. Repeat step 6 afterwards.

8. **Return or post.**
   - **No PR/MR number:** return the report as-is, emit `REVIEW_COMPLETE` with
     `review_url` `null`, and stop. A local review never fixes.
   - **PR/MR number:** invoke `v8ch:consensus-review-poster` once with the
     report, the PR/MR number, the cycle, the status, the score, the delegation
     mode, the plan source, the reviewed SHA, the scope basis, the blast-radius
     counts, the repository directory, `${CLAUDE_SKILL_DIR}`, and a scratch
     directory. Capture the comment URL. If posting fails, emit `ABORT` with
     `reason` `post_failed`.

9. **Branch on the status.**
   - `clean` — emit `REVIEW_COMPLETE` and stop.
   - `passing` or `failing` — run `references/fix-workflow.md`, then review
     again if the budget allows. That workflow returns an outcome; this skill
     emits the signal, following the precedence list in its Step 5 so two
     identical runs cannot end on different signals.

## Budget

At most three reviews per invocation. Every invocation gets a fresh budget,
whatever the PR/MR's cycle count and whichever toolchain wrote the earlier
cycles. Cycle numbers themselves accumulate with no cap.

When the third review is still not `clean`, the run ends on the first matching
signal in the fix workflow's Step 5 precedence list. In short: unresolved
findings give `BLOCKERS_REMAIN`, a pushed third-cycle fix gives `PUSH_COMPLETE`,
and a third review that produced no commit gives `MAX_REVIEWS_REACHED`. Without
that order, one run could end on either signal.

## Plan handling

A supplied plan is review context. Record its source identically in the report's
Run Provenance line and in the `plan_source` metadata: the literal `none` when
no plan was supplied, otherwise `supplied: <path or short description>`. Never
recover a plan from PR/MR comments.

## Citations

Everything published — the comment, the summary, the report — cites
repository-relative paths of tracked files, or links. Never absolute paths, home
directory paths, or untracked scratch files. Readers have no checkout of this
machine.

## Length

The synthesized report and the posted comment are the deliverables; keep them to
what the contract specifies. Your own output outside the signal block is at most
a few lines: what was reviewed, the score and status, and the comment URL. Do
not narrate the steps as you take them, do not restate the report, and do not
summarize the findings a second time.

## Terminal signals

Every run ends with exactly one fenced block as its last output:

````markdown
```consensus-review-signal
{"signal": "<SIGNAL>", "cycle": <int>, "details": {}}
```
````

`cycle` is the PR/MR cycle number, or `0` for a local review. `details` carries
exactly the keys listed below, all of them required. A value that does not exist
at that point is `null`; a list with no entries is `[]`.

| Signal | When | `details` keys |
| --- | --- | --- |
| `REVIEW_COMPLETE` | A local review returned its report, or a PR/MR review reached `clean` | `score`, `status`, `review_url` |
| `NO_DIFF` | Nothing to review | `scope` |
| `EVIDENCE_FAILED` | A reviewer failed the evidence gate twice | `failed_passes` |
| `QUALITY_FAILURES` | Quality commands still fail after the fix pass; nothing is committed and the fixer's edits stay in the working tree | `score`, `review_url`, `failed_commands` |
| `BLOCKERS_REMAIN` | The fix cycle pushed, but findings remain `partial` or `work-item-required` and the budget allows no further review, or the fixer returned a finding with no disposition | `score`, `review_url`, `commit_shas`, `work_items` |
| `PUSH_COMPLETE` | Fixes were committed and pushed, and the budget is exhausted before a `clean` review | `score`, `review_url`, `commit_shas`, `work_items` |
| `MAX_REVIEWS_REACHED` | The third review is still not `clean` | `score`, `status`, `review_url`, `work_items` |
| `ABORT` | An unrecoverable error | `reason`, `message`, `score`, `review_url` |

`ABORT` `reason` is one of `command_failed`, `head_mismatch`, `branch_mismatch`, `platform_auth`,
`post_failed`, `read_only_role_mutated`. `work_items` entries are the records
the fixer wrote under `## Work Items Required`.

## Stop rules

- Stop after the signal block. Nothing follows it.
- Never prompt the operator, at any point, for any reason.
- Never invoke a skill, and never invoke an agent outside `v8ch`.
- Never merge, deploy, force-push, or create tracking items.
