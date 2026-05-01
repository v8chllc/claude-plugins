---
name: consensus-review
description: Runs a multi-agent consensus code review. Use when reviewing code changes, before pushing a PR, or as the review step in a development workflow. Spawns three independent reviewers (standards-reviewer, correctness-reviewer, architecture-reviewer) in parallel, then passes their outputs to review-synthesizer for a tiered consensus report with a 1-100 quality score. Accepts an optional plan file; when provided, reviewers also check for plan divergences. Scope defaults to all local changes (staged, unstaged, and untracked); also accepts a base commit SHA, branch diff, or explicit file list.
---

# Consensus Review

Orchestrates three independent reviewer agents and one synthesis agent to produce a stable, tiered consensus review. When a PR or MR number is provided, the PR/MR comment thread is the durable audit trail and the source of truth for future cycles.

## Mode detection

Before running Step 0, parse the user's trigger phrase to decide between **interactive** and **autonomous** modes. Set the `AUTONOMOUS` flag once and use it for the rest of the run.

Set `AUTONOMOUS=true` when either of the following matches the trigger:

- The phrase matches the regex `\b(autonomous|autonomously|non-interactive)\b`, case-insensitive.
- The phrase contains the literal sentinel `[rouge-workflow]`.

Otherwise set `AUTONOMOUS=false`.

**Trigger examples:**

- `review PR 123` → `AUTONOMOUS=false` (interactive default).
- `review PR 123 autonomously` → `AUTONOMOUS=true`.
- `run a non-interactive consensus review on MR 47` → `AUTONOMOUS=true`.
- `[rouge-workflow] consensus review for PR 9` → `AUTONOMOUS=true` (the `[rouge-workflow]` sentinel is added by Rouge automation and forces autonomous mode regardless of other wording).

In autonomous mode, do not prompt the operator for any input during the run. Steps that would otherwise prompt must instead use the documented autonomous branch or emit a `consensus-review-signal` block (see "Exit signals" appendix) and stop.

### Trigger-phrase parsing

The trigger phrase is parsed once at the start of the run. The full set of recognized tokens:

- **Autonomous keywords:** `autonomous`, `autonomously`, `non-interactive` (regex `\b(autonomous|autonomously|non-interactive)\b`, case-insensitive). Any match sets `AUTONOMOUS=true`.
- **Sentinel:** the literal string `[rouge-workflow]`. Its presence sets `AUTONOMOUS=true`.
- **Optional `on_quality_failure: abort` token** — recognized in autonomous mode only. If the trigger phrase contains the literal token `on_quality_failure: abort`, set the fix-workflow Step 6 failure policy to `abort` (see `references/fix-workflow.md` Step 6). Any other value, or no token, leaves the policy at the default `continue`. In interactive mode this token is ignored.

## Prerequisites

Eight agents are required. They live in two locations:

**Workspace-specific reviewers** (`.claude/agents/` at the workspace root) — must be generated per workspace because their review mandates depend on the project's standards, test fixtures, and architecture:
- `standards-reviewer`
- `correctness-reviewer`
- `architecture-reviewer`

If any of these three are missing, generate them using the `/meta-consensus-review-agents` command.

**Plugin-scoped agents** (shipped with the vault plugin at `plugins/vault/agents/`) — workspace-agnostic and already installed when the plugin is enabled:
- `review-synthesizer` — synthesizes the three reviewers into a consensus report
- `consensus-review-poster` — posts structured review, fix-validation, acceptance, and opt-in comments to the PR/MR
- `consensus-review-fixer` — applies targeted fixes from the consensus report
- `acceptance-recommender` — recommends findings whose fix is "no code change required"
- `opt-in-recommender` — recommends Low-Confidence findings worth a one-shot fix attempt

## Inputs Required

1. **PR/MR number** (optional) — if provided, the diff is fetched from the platform and all audit persistence happens through PR/MR comments.
2. **Plan file** (optional) — path to the implementation plan the code was built against. If not provided, reviewers evaluate intrinsic code quality only; plan conformance checks are skipped.
3. **Code changes** — specify the scope as one of:
   - *(default)* All local changes: staged, unstaged, and untracked files
   - A base commit SHA to compare the working tree against
   - A branch diff
   - An explicit file list

## Audit Source of Truth

For PR/MR runs, do not create or depend on `.rouge` review directories. The durable audit trail is the PR/MR thread. Every consensus-review comment posted by `consensus-review-poster` includes hidden `consensus-review` metadata that `recover_context.py` reads on later cycles.

Local scratch files are allowed only to bridge agent/script interfaces during the current invocation. Treat them as disposable; never use them as historical truth.

## Steps

### Step 0 — Recover prior cycle context (PR/MR number only)

If the trigger includes a PR or MR number, run context recovery before doing anything else:

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/recover_context.py <number> --repo-dir <repo-root>
```

The script reads `DEV_SEC_OPS_PLATFORM` from `.env` at the repo root to determine GitHub vs GitLab, fetches PR/MR comments, and parses consensus-review metadata blocks. Override with `--platform github|gitlab` if needed.

Read the full output and keep it as `RECOVERED_CONTEXT`. It tells you:
- The platform and audit source
- The next cycle number — use this as `CYCLE`; do not recompute it
- Prior review/fix summaries and comment URLs
- Operator-accepted findings that must not be re-raised or fixed
- Historical low-confidence opt-ins, which are informational only and must be prompted fresh each cycle

If no prior consensus-review comments exist, the script still outputs `CYCLE = 01`. Continue normally.

---

### Step 1 — Gather inputs

Determine the code scope using the following priority ladder. Check each level in order and use the first match.

**Priority 1 — PR/MR number given**

If the trigger includes a PR or MR number:

1. Read `DEV_SEC_OPS_PLATFORM` from `.env` at the workspace root.
2. Fetch the diff using the appropriate command:
   - `github`: `gh pr diff <number>`
   - `gitlab`: `glab mr diff <number>`
3. Use the fetched diff as the full code scope.
4. Skip all git diff commands below.

**Priority 2 — Base commit SHA given**

```bash
git diff <sha>
git ls-files --others --exclude-standard
```

Read the full content of each untracked file and include it in the diff passed to reviewers, labeled clearly as a new file.

**Priority 3 — Branch diff given**

Use the appropriate `git diff` range for that branch.

**Priority 4 — Explicit file list given**

Diff only those files using `git diff -- <file1> <file2> ...`.

**Priority 5 — Default (nothing specified)**

```bash
git diff HEAD
git ls-files --others --exclude-standard
```

Read the full content of each untracked file and include it in the diff passed to reviewers, labeled clearly as a new file.

If no changes are found at Priority 5:

- **Interactive (`AUTONOMOUS=false`):** ask the user to clarify scope.
- **Autonomous (`AUTONOMOUS=true`):** do not prompt. Emit the `NO_DIFF` exit signal block (see "Exit signals" appendix) and stop.

If a plan file path was provided, read it in full. If no plan file was provided but `RECOVERED_CONTEXT` contains a Planning Context section with a plan, use that recovered plan — do not emit the "no plan file" notice in this case. If neither a plan file nor a recovered plan is available, notify the user before proceeding:

> **Note:** No plan file provided. Reviewing changes for intrinsic quality only — plan conformance checks will be skipped.

### Step 2 — Run three reviewers in parallel

Spawn all three reviewer agents simultaneously using the Agent tool. Run all three calls in a single response — do not wait for one to complete before starting the others.

Agents to invoke (by subagent_type):
- `standards-reviewer`
- `correctness-reviewer`
- `architecture-reviewer`

Each agent receives the full code diff and the plan document when one was provided. Do not persist raw reviewer outputs to `.rouge`. Keep their exact outputs in memory for synthesis and for the PR/MR audit comment.

### Step 3 — Synthesize

Once all three reviewer outputs are returned, invoke `review-synthesizer` with all three reviewer outputs in full, clearly labeled, plus review history:

```text
## standards-reviewer Output
[Full standards-reviewer output]
---
## correctness-reviewer Output
[Full correctness-reviewer output]
---
## architecture-reviewer Output
[Full architecture-reviewer output]
---
## Review History
Current cycle: [CYCLE or "none"]
Audit source: PR/MR comments or "none"
[If PR/MR: paste RECOVERED_CONTEXT in full.]
```

The synthesizer uses recovered accepted findings to suppress accepted items and calibrate recurring findings across cycles.

### Step 4 — Post review, then run recommenders, then post recommendations

**If no PR/MR number was given:** present the synthesizer output directly to the user without summarizing or modifying it. Stop here.

**If a PR/MR number was given:** post the review comment first (so the synthesizer's `[F-N]` numbering becomes canonical on the PR/MR thread), then run the recommenders in parallel, then post the consolidated recommendations comment.

**Step 4a — Post the review comment.** Invoke `consensus-review-poster` with:

- Comment type: `review`
- The synthesizer output in full
- The three raw reviewer outputs in full as audit appendices
- The PR/MR number
- `RECOVERED_CONTEXT`
- The cycle number: `CYCLE`
- The repo dir where `gh`/`glab` commands should run
- The skill dir: `${CLAUDE_SKILL_DIR}`
- A scratch directory for temporary summary/review files, if the poster needs one

The poster owns status determination, summary authorship, temporary file creation, template-backed rendering, metadata generation, and script invocation. The posted PR/MR comment is the durable review audit artifact. Capture and report the PR/MR comment URL.

**Step 4b — Spawn the recommenders in parallel.** Once the review comment is posted, spawn `acceptance-recommender` and `opt-in-recommender` simultaneously using the Agent tool, in a single response. Pass each recommender the full synthesizer output (with its `[F-N]` numbering intact). Keep their outputs in memory.

Recommender failure rule: if either recommender fails or returns an error, treat its recommended list as empty and continue. The review comment was already posted in Step 4a, so it is not affected by recommender failure under any circumstance.

**Step 4c — Post the recommendations comment.** Invoke `consensus-review-poster` with:

- Comment type: `recommendations`
- The acceptance-recommender's "Recommended for Acceptance" list (or empty if it failed)
- The opt-in-recommender's "Opt-In Recommendations" list (or empty if it failed)
- The PR/MR number
- The cycle number: `CYCLE`
- The repo dir, skill dir, and scratch directory as usual

This comment is advisory only — it does not adjust scores and does not auto-apply findings. Report the recommendations comment URL alongside the review comment URL.

### Step 5 — Acceptance (PR/MR number given)

The acceptance step has two branches. Pick exactly one based on the `AUTONOMOUS` flag set during Mode detection.

**Interactive branch (`AUTONOMOUS=false`):**

Read the recommendations comment posted in Step 4c (or, equivalently, the in-memory acceptance-recommender output). If it lists one or more recommended-for-acceptance findings:

1. Present the recommended-for-acceptance findings to the operator.
2. Ask: "Accept these findings? (yes/no/select)"
   - **yes** — accept all listed findings
   - **no** — skip acceptance; proceed to Step 6
   - **select** — operator specifies which findings to accept by number
3. For accepted findings, invoke `consensus-review-poster` immediately with:
   - Comment type: `acceptance`
   - The selected findings with severity, title, file, and rationale
   - Raw score and adjusted score
   - PR/MR number
   - Cycle number
   - Repo dir, skill dir, and scratch directory as usual

Do not write an `accepted-*.md` audit file. The posted acceptance comment is the durable record and future cycles recover it from the PR/MR thread.

If the operator declines acceptance, no acceptance comment is posted.

**Autonomous branch (`AUTONOMOUS=true`):**

Do not prompt. If the acceptance-recommender produced one or more recommended-for-acceptance findings, post an `acceptance` comment for every finding it flagged — there is no operator filtering in autonomous mode. Invoke `consensus-review-poster` with:

- Comment type: `acceptance`
- The full acceptance-recommender list, including severity, title, file, and rationale
- Raw score and adjusted score (from the acceptance-recommender output)
- PR/MR number
- Cycle number
- Repo dir, skill dir, and scratch directory as usual

If the acceptance-recommender returned "None." (or failed and was treated as empty in Step 4b), skip this step and proceed to Step 6 without posting an acceptance comment.

### Step 6 — Fix issues (optional, PR/MR number required)

When the user asks to fix issues from the review, run the fix workflow defined in `references/fix-workflow.md`.

The fix workflow covers: fix-start additional acceptance, low-confidence opt-in, fixer invocation, fixer signal handling, fix validation posting, code quality tooling, commit composition, and push to the PR branch.

**Prerequisite:** the fix workflow is PR/MR-only. A PR or MR number must have been provided. The workflow resolves the latest review, fix-validation state, acceptances, and opt-ins from PR/MR comments and regenerates any needed scratch files. Local reviews do not have a durable audit trail and are not eligible for the fix workflow.

## Exit signals

In autonomous mode the skill cannot prompt for input, so it communicates terminal states by emitting a fenced `consensus-review-signal` block as the very last thing it writes before stopping. The block is a JSON object with this schema:

```consensus-review-signal
{"signal": "<value>", "cycle": N, "details": {...}}
```

- `signal` is one of the five values listed below.
- `cycle` is the current cycle number as an integer (e.g. `1`, `3`).
- `details` is a free-form JSON object with whatever context the caller will need to act on the signal. Keep keys short and lowercase.

Exit signal values:

- **`NO_DIFF`** — Step 1 Priority 5 found no local changes and `AUTONOMOUS=true`. The skill emits this signal instead of asking the operator for scope, then stops.
- **`QUALITY_FAILURES`** — code-quality tooling failed during a fix workflow and the failures could not be resolved automatically. Use this signal to surface lint, format, type, or test failures that block the fix from being committed.
- **`PUSH_COMPLETE`** — fixes were applied, validated, committed, and pushed successfully. The autonomous run completed its work for this cycle.
- **`BLOCKERS_REMAIN`** — the fixer ran but at least one finding still has status `unresolved` or `partial` after fix validation. The cycle ends without a clean push.
- **`ABORT`** — an unrecoverable error prevented the workflow from continuing (for example, a missing dependency, an unauthenticated `gh`/`glab` client, or a malformed plan file). Include the failing step and a short error string in `details`.

The interactive path does not emit signal blocks. It returns text and prompts to the operator as before.
