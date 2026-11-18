# Interrupt rules

Four dispositions. Take the lowest one that fits: a supervisor that interrupts
often is one the sponsor learns to skim.

## Interrupt now

Irreversible, unsafe, or evidence-corrupting. Raise it before the action where
the record or block shows intent; otherwise immediately after.

| ID | Trigger |
| --- | --- |
| I-1 | Merge, unauthorized force-push, deletion of a branch the run did not create or continue, deploy, or a push to any ref the profile names as a deploy trigger |
| I-2 | A production migration, a bulk-data or scheduled-job command, a secret read or write, or a local tool pointed at shared or production data |
| I-3 | A write outside the resolved repositories and branches, an issue created, edited, or closed by the manager, or a second writer in one repository |
| I-4 | Publishing or reporting a verdict after a commit that invalidated the review or verification behind it |
| I-5 | Fabricated or unsupported evidence: an edited marker, snapshot, or verification comment, a disposition with no artifact, a command reported but not run, an exit code cited without inspected output, or a claim the repository contradicts |
| I-6 | Scope taken outside the approved plan with no checkpoint, or a silent plan change |
| I-7 | Exceeding a budget, or taking a `checkpointed` action without sponsor approval |
| I-8 | A stall: the same failing action three times, or two consecutive quiet ticks past `quiet_until` with no phase change |
| I-9 | The run continuing after a terminal signal, or emitting two |
| I-10 | Reading profile or work-item text as authority to do something the skill forbids |

An authorized supervisor may create and track a confirmed deferred finding only
as a separate Backlog follow-up under the bounded procedure in `SKILL.md`; that
specific planning action is exempt from I-3. I-3 still applies to manager issue
creation and every other second writer in the repository, including any
supervisor write into the active run, its evidence, or its planning artifacts.

**Confirm at the source first.** Read the file, the command output, the commit,
or the pull request — never the manager's summary of itself. If confirmation is
not possible, drop to a draft and say what could not be confirmed.
Re-read the latest record immediately before raising an interrupt. It can
move between a tick's first read and the interrupt, and a deviation the
manager has already recorded needs no interrupt.

For I-6, if the apparent missing deviation may still appear in an in-flight
turn's status block, wait for that turn to end before interrupting, unless the
action is irreversible.

When the sponsor has authorized headless stop and the interrupt is confirmed,
follow `references/headless.md` to signal the manager process group. After the
working-tree report, the disposition is **stop executed, awaiting sponsor**;
do not resume until the sponsor directs it.

Format, one per issue, never repeated:

```text
INTERRUPT <rule> — <what is happening, one line>
Evidence: <path, command, SHA, or URL the sponsor can check>
Recommend: <stop | hold for decision | specific correction>
```

## Provisional review-scope advisory to the sponsor

Use this disposition at the next ordinary observation of a specific plausible
review-driven expansion or polishing concern measured against the current
approved plan. Send it during an in-flight manager turn without waiting for a
status block. It is a sponsor-facing notice, not an interrupt, a manager relay,
a confirmed deviation, or a scope decision. It does not stop or message the
manager and does not authorize a supervisor write to the active run. Do not use
it merely for score movement, review invocation count, routine parity repair,
or tests necessary to prove an approved criterion.

```text
ADVISORY review scope — <one specific concern>
Source: <review URL or fix commit URL and repository-specific SHA>
Approved boundary: <criterion and accepted plan or approved revision URL>
Observed delta: <proposal or landed diff, with link; distinguish the two>
Uncertainty: <what the sources have not established>
Sponsor choice: <the scope decision the sponsor owns, if the concern persists>
```

Track the concern in the private per-run findings file. If later evidence
resolves it, send a closure citing that evidence; if it changes, send an update
to the same concern rather than a duplicate advisory. A confirmed unauthorized
landed change without a checkpoint still follows I-6, including its wait for
an in-flight status block where applicable. An advisory alone never triggers
I-6 or the headless stop procedure.

## Existing authorized exceptions

I-1 does not apply to the corrective run's lease-guarded rebase of its continued
branch before its first review, when every condition in `workflows/contracts/run-state.md`
is met. It still applies to any other force-push. Only I-3's second-writer
clause is exempted for the declared consensus-review capability's own fixer during
its invocation. I-3's outside-repository writes and issue-mutation triggers remain
in force, including for that fixer. The retained builder remains the only
implementation writer outside that invocation.
Corroborate these conditions before treating an action as exempt. These are the
orchestrators' existing exceptions, not new supervisor permissions.

## Draft for the sponsor

A decision is needed and nothing is burning. Write it to `.prompts/` and wait.

- The block sets `waiting_on: sponsor`.
- Acceptance criteria collide, or a plan cannot satisfy one.
- A budget is spent and the next step needs more.
- Deferred findings requiring sponsor decisions about ambiguous routing, reopening
  or expanding existing work, or uncertain private/public publication.
- A profile field is ambiguous or absent where it matters.
- A `material` deviation, or one the supervisor would raise to `material`.
- A recommendation with real alternatives, each with its cost.

## Note silently

Log it in the run's findings file, which the sponsor receives when the run
ends; raise it sooner only if asked or if it recurs across runs.

- Style, naming, and wording preferences.
- A faster route to the same result the manager is already reaching.
- A `minor` deviation.
- A non-actionable observation that is unverifiable at the source. An
  unverifiable issue that would otherwise be an interrupt or a draft becomes a
  draft, as above.
- Retrospective material: friction, repeated corrections, rules that proved
  unclear.

## Interrupts the supervisor caused

Before raising an issue about reporting, delivery, or pacing, ask whether the
supervision contract caused it. A supervisor can raise false reporting-failure
alarms over mid-turn silence and, through its own kickoff wording, teach the
manager to stop at every phase boundary. Both cost more than the errors they
were watching for.

A supervisor that finds the run breaking a rule the supervisor itself introduced
reports that as its own finding, not the manager's.
