# Channels

Four sources carry a headless run; an interactive run has the first three.
They update at different moments, and reading one alone produces false conclusions.

## What each carries

**The coordination record** — the latest marker comment on the run issue for the
current `run_id`, holding phase, per-repository issue, baseline, branch, profile
sources, pull requests, plan link, budgets, and deferred scope. The manager
appends a complete marker inside a turn, at every phase change and whenever a
pull request opens, so it is the only channel that moves between turn
boundaries. It is the primary channel, and the one a resuming manager reads.
Earlier markers are history: read them to see when a phase changed, never for
current state.

**The status block** — read its shape and terminal-turn ordering from
`workflows/contracts/status-block.md`. Rich, but delivered
on the manager's turn boundaries, not the supervisor's schedule. Where the
manager's session captures turns to a local store the supervisor can read, the
block arrives there; otherwise the sponsor relays it.

**The repositories and the host** — commits, branches, pull requests, checks,
comments. This is fact rather than claim, and it is what every corroboration
resolves to.

**The manager stream** — the headless manager's JSONL output and process state
under `.prompts/runs/<run issue key>/`. It shows session identity, streamed
activity, and the turn boundary. Read it with the run issue and repository;
stream text alone does not prove a reported action occurred.

| Platform | Identity and progress observed | Turn outcome |
| --- | --- | --- |
| Claude Code 2.1.290 | `session_id` on every event; `assistant` and `user` events have `timestamp`; `tool_progress` and `system` task events were seen | The last `result` before process exit is the turn output; parse its status block and any terminal signal using `workflows/contracts/status-block.md` terminal-turn ordering. More than one `result` may precede exit. |
| codex-cli 0.159.0 | `thread.started.thread_id` on the first event; `turn.started`, `item.started`, and `item.completed` were seen | `turn.completed` followed by process exit; the status block is in `last-message.txt` written by `-o`. `turn.completed` carried only token usage. |
| codex-cli 0.160.1 | The same events as codex-cli 0.159.0, across a fresh launch and two `resume` relays; each resume emitted `thread.started` with the recorded `thread_id` | As codex-cli 0.159.0 |

Codex event timestamps and a universal tool-call schema are **unverified** in
these captures. Use the stream file's modification time for Codex silence. A
field not shown in the Claude Code 2.1.290 or codex-cli 0.159.0 captures is
unverified, not a parser requirement. Follow `references/headless.md` for launch and resume.

## Reading them together

| Blocks | Repository | Record | Reading |
| --- | --- | --- | --- |
| nothing new | unchanged | current | Quiet. One line, stop. |
| nothing new | new commits | current for the phase | A turn is in flight. Wait. |
| nothing new | new commits | stale by a phase | The record rule was skipped. Raise once, not an interrupt. |
| new block, no state | any | any | A turn ended reporting nothing. A real lapse. |
| new block | contradicts the block | any | Corroboration failed. Interrupt, rule I-5. |
| nothing new | unchanged | unchanged, past `quiet_until` | Possible stall. Second consecutive tick makes it rule I-8. |

For a headless run, consume the turn-boundary result determined by
`references/headless.md` before parsing the final result. A live manager's
stream silence alone is not a stall; apply I-8's remaining signals.

**Never read repository activity without a new block as a reporting failure.**
That is a turn in progress. A supervisor that calls it a contract violation
can lead the manager to accept it into its own record as a `critical` deviation
that later has to be withdrawn.

## What a supervisor cannot see

For an interactive run, whether the manager is thinking or has stopped. Neither
the record nor the repositories distinguish a long turn from a dead session.
For a headless run, the recorded process and stream show liveness and event
silence, though they do not reveal the manager's reasoning. Report only what
those sources establish.

Anything inside a turn that produced no artifact: reasoning, a discarded
approach, a tool call that changed nothing. A run's thinking is not a channel.
