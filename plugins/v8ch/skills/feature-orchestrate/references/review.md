# Review

The review phase settles an independent review of the pull request's head before the manager freezes the head for verification. The profile's `review_capability` names the gate of record, and the manager triggers every review of it: nothing reviews a pull request on its own, so a pull request's draft state never decides whether a review runs.

Before the capability starts a new invocation, the manager applies the review invocation gate in `workflows/contracts/run-state.md`.

## Who invokes

Under `agent-tooling-review`, follow `workflows/contracts/agent-tooling-review-loop.md`; a fresh review agent runs one recovered cycle at a time from the manager-prepared plan, head and deferred inputs. The manager owns the loop and records terminal dispositions for every finding.

Under `consensus-review`, a fresh review agent runs each invocation, never the manager. It is given only the invocation gate's prepared inputs — the repository and its checkout, the pull request number, the validated head SHA, the prepared plan file and its source URL, the manager-prepared `deferred` input filtered to this repository and run-wide entries, and the readable criteria-and-guards file — and invokes the review skill exactly as that skill defines. It returns the cycle comment URLs, the final status, and the skill's signal, and the manager records and routes them. The manager never runs the review skill in its own context, and never authors, edits, copies, or templates a review report, a synthesis, or any review text: the review skill's own roles write every report.

In a synchronized pair, each repository gets its own review invocation, by its own review agent, and its own report. A report, a synthesis, or any review text is never copied, templated, or string-replaced from one repository into the other.

## Who fixes

| `review_capability` | Who applies fixes |
| --- | --- |
| `consensus-review` | The review skill's own fixer, inside its invocation. Give it the approved plan and the skill's acceptance criteria and Regression Guards input; do not give it `deferred`. Apply `workflows/contracts/finding-policy.md` after every fix commit. |
| `agent-tooling-review` | The retained builder, after the manager routes in-scope findings. A repair head needs a new review cycle. |

These are the only writers a run has: the retained builder, and consensus-review's fixer only while that capability is invoked.

## Review bound

Flag only gaps affecting correctness, security, privacy, authorization, a stated criterion or Regression Guard, or the accepted plan. Put style, suggestions, and nitpicks into one `noted` list in the result comment. They need no individual disposition and are not fixed unless the sponsor asks. A fix cannot change a criterion, guard, or plan decision or add scope; route a plan-level change to the sponsor as an issue edit and `orchestration-decision` marker. Read outside tool comments once: route a gap in those categories as a finding and otherwise note it.

## Shared finding policy

Apply `workflows/contracts/finding-policy.md` to every finding from every reviewed head. It owns what counts as a finding, dispositions, the clean condition, class audits, late findings, and assessment after a moved head. This reference owns only capability mechanics and role routing.

For `REVIEW_COMPLETE_WITH_FINDINGS`, apply the complete "Advisory consensus-review handoff" section in `workflows/contracts/run-state.md`; the manager decides, posts the terminal disposition comment, and routes `fix_requested` IDs to the builder. Consensus review's ordinary fixer dispositions findings inside its invocation. Deferrals follow `workflows/contracts/finding-policy.md`.
