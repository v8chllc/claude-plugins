# Status block

The block a manager emits so a supervisor reads state rather than prose. It is
the last content of a non-terminal turn that ends; on a terminal turn it sits
immediately before the final terminal signal. It never ends a turn by itself.

An orchestrator declares this contract by pointing at this file. It is stated
here once; a skill that restates it creates a second copy that drifts.

```manager-status
run_id: change-set-20260915T142530Z
turn: 7
phase: implement
repos: [<repo>@<branch>]
did: <one line — what this turn actually changed or ran>
resolved: <decisions settled this turn, or none>
relays: <sponsor relay approval time, draft path, and summary for this turn, or none>
verified: <claim — artifact, or none>
next: <the single next action>
waiting_on: none | sponsor: <question>
quiet_until: <duration or timestamp, or none>
budget: review_invocations <n>/2 · corrections <n>
profile_inherited: [<fields taken from the named child block or default child block>]
profile_defaults: [<fields absent from all three profile tiers>]
deviations: none | <severity>: <departure from plan or skill rules>
risks: <anything the sponsor would want flagged, or none>
```

## Rules for the manager

- Keep `profile_inherited` as a field list. The linked coordination record's resolved-profile prose names each inherited field's supplying tier (named child block with its `owner/repo` identity, or default child block). Resolve per field: repository profile, named child block, default child block, field default.

- One block per supervised ending turn, on an idle or blocked turn too. It is
  last on a non-terminal turn. On a terminal turn, put it immediately before
  the final terminal signal; nothing follows that signal. Long turns are fine:
  the block reports everything the turn did.
- **Writing a block never ends a turn.** Only a sponsor question or a terminal
  signal does. A manager that treats each phase's block as a stopping point
  makes the sponsor type "Continue" between phases.
- `did` states what happened, not what was intended. A turn that changed
  nothing says so.
- `relays` reports this turn's entries from the durable relay history defined by
  `run-state.md`; use `none` only when no relay was received this turn.
- `verified` holds only claims with an artifact: a path, a command plus
  inspected output, a commit SHA, or a URL. A claim without one belongs in
  `next`.
- `deviations` is never silently empty. Each departure is named in the turn it
  happens, with a severity, one per line.
- A deviation records a departure from the plan or the skill's rules. It never
  stands in for an unmet acceptance criterion: a criterion the work cannot meet
  as written goes to the sponsor for amendment, in whatever phase it surfaces.

| Severity | Meaning | Supervisor disposition |
| --- | --- | --- |
| `minor` | Reversible and inside the plan's intent: a different file layout, an extra test, a command run in a different order | Note silently |
| `material` | Changes what the run delivers or how it is proved: a plan decision revised, a criterion approached differently, a check substituted | Draft for the sponsor |
| `critical` | Crosses a rule the sponsor set: unapproved scope taken, a budget exceeded, authority widened, evidence weakened | Interrupt now |

The manager assigns the severity. The supervisor re-reads the deviation at its
source and may raise it, never lower it. A deviation the manager omits and the
supervisor finds is `critical` by default, because the omission is the problem.

Conformance to a stated rule is not a deviation.

## Rules for the supervisor

- Read the block as a claim, never as a fact. Everything in `verified` has an
  artifact by contract; check one when it carries a decision.
- A `critical` the supervisor itself prompted is not evidence of a breach. Say
  so plainly rather than letting it stand in the record.
