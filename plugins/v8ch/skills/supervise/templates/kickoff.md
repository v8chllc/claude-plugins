# Kickoff template

The block a sponsor pastes into a fresh manager session. Fill every slot,
add the corrective line only for a corrective run, and send it unchanged
otherwise. For `chore-orchestrate`, omit both supervisor identity lines from
the filled manager prompt; its record has no `additional_review` field.

It is short on purpose: the orchestrator skill states the lifecycle, the
budgets, and the prohibitions. A kickoff that restates them gives the manager two
sources for one rule, and the copies drift as the skill changes. What the skill
cannot know is the work, the layout, and that someone is watching.

---

```text
You are the manager for a <SKILL> run. Run the <SKILL> skill from
<SKILL PATH> and follow it as written; this prompt adds the run issue and the
reporting contract, and overrides nothing.

Run issue: <RUN ISSUE>. Its sub-issues are the repository issues.
Repositories in scope: <REPOS AND WHERE THEY ARE CHECKED OUT>.
Supervisor identifier: <SUPERVISOR IDENTIFIER>.
Supervisor identity source: <SUPERVISOR IDENTITY SOURCE>.
<CORRECTIVE>

Authority: you may read anything, run each repository's documented quality
commands, create branches, commit, push, and open pull requests. You may not
merge, deploy, or touch any repository outside those named. Cloning
repositories into a run worktree, when a documented quality command does it so
its checks can run, does not touch another repository; never commit, push, or
open a pull request in those clones. Force-push is
permitted only for the skill's existing lease-guarded corrective-rebase exception.
The declared consensus-review capability's own fixer is the existing exception
to the retained builder's sole-writer rule, only during its invocation.

Report contract: read `workflows/contracts/status-block.md` from the installed plugin root and follow
its block shape and terminal-turn ordering for every ending turn. Writing
a block is not a reason to end a turn: finish a phase, write the coordination
record and the block, and continue into the next phase in the same turn. Only a
sponsor question or a terminal signal ends a turn.

Append a coordination record to the run issue at every phase change and whenever
a pull request opens, before any block claims the new state. That record is what the supervisor reads between
your turns, and what a resuming manager reads instead of replaying this thread.
Apply the relay persistence rules in `workflows/contracts/run-state.md`, resolved
from the installed plugin root two directories above the orchestrator’s skill directory.

Start at the first phase.
```

---

## Slots

| Slot | What goes in it |
| --- | --- |
| `<SKILL>` | The orchestrator: `change-set-orchestrate`, or a sibling |
| `<SKILL PATH>` | Where that skill's `SKILL.md` lives in the installed `v8ch` plugin |
| `<RUN ISSUE>` | The run issue's URL, in the coordination repository |
| `<SUPERVISOR IDENTIFIER>` | The exact supervisor agent or session identifier supplied through the sponsor or authenticated parent-agent channel before the run begins; required for a supervised run except `chore-orchestrate`, where it is not applicable and its prompt line is omitted |
| `<SUPERVISOR IDENTITY SOURCE>` | `session` when the sponsor supplies the identifier in the manager session, or the sponsor comment URL that supplied it; required for a supervised run except `chore-orchestrate`, where it is not applicable and its prompt line is omitted |
| `<CORRECTIVE>` | Corrective runs only: `This run continues run <earlier run_id>, as the run issue states; its pull requests are <URLs>.` Delete the line otherwise. The run issue's text is what makes the run corrective; this line only points at it |
| `<REPOS AND WHERE THEY ARE CHECKED OUT>` | Repository names and their paths relative to the session's working directory |

## Before sending

- The run issue exists, with a sub-issue for every repository whose profile
  requires one. The supervisor checks this, and creates them only when the
  sponsor directs.
- Every repository in scope is on its default branch, clean, and synced; for a
  corrective run, on the continued branch at the earlier run's head, clean.
- Any capability the skill declares — a review skill and its minimum version —
  is loaded in the manager's session, not only installed: a plugin updated after
  that session started needs a reload there before kickoff.
- Every acceptance criterion that depends on deferred scope names those
  deferred items in the run issue body, or in the sub-issue that carries it:
  a verifier reads the issues, never the coordination records.
- Run the designated orchestrator's preflight from the supervisor's own toolchain port; work through failed checks under the supervise skill's readiness fix rule, and rerun it before launch.
- A supervisor session is open, or the run produces no drafts and no interrupts.
  For a supervised run, the filled prompt contains that session's exact
  supervisor identifier and trusted identity source so the manager can copy
  both into every repository's first coordination record. For `chore-orchestrate`,
  both identity slots are not applicable: omit both lines from the manager prompt,
  because chore records omit `additional_review`.

## The kickoff file

Write the filled kickoff to `.prompts/kickoff-<run issue>-<date>.md` in this
order, for the manager launch, so the filled prompt can be sent unchanged:

1. A title naming the run issue, the orchestrator, and the date.
2. One short paragraph saying where to paste: the manager's toolchain, the
   directory its session starts in, the review-capability version it must have
   loaded, and the directory it works in when that differs from where it starts.
3. The filled prompt, alone inside a `text` fence. Notes about the prompt never
   go inside the fence: the sponsor copies the fence and nothing else.
4. **Verified before sending**: each item from "Before sending" above that the
   supervisor confirmed at the source, with what it checked, such as an issue
   URL, the commit a checkout is at, or a command's output.
5. **Sponsor checks before sending**: each item the supervisor could not
   confirm, such as whether the manager's session has loaded the review
   capability.

Every "Before sending" item appears in exactly one of the last two sections.
When a slot changes, rewrite the whole file rather than appending to it, so the
fence never holds an out-of-date prompt.
