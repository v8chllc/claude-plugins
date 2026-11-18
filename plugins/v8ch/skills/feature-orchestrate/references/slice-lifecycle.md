# Slice lifecycle

The builder implements the approved plan as a sequence of bounded slices, one commit each. Every slice follows the same ten steps, and the manager decides at each checkpoint whether the next slice may start.

## The ten steps

1. **Orient.** Read the repository's guidance, inspect the working tree, confirm the slice is still incomplete, and reconcile the approved plan against the repository's governing documents. Report any required work the plan does not name. A plan is not an authority: a required behavior it omits is still required.
2. **Bound.** State the slice's outcome, the files or modules in scope, its tests, its constraints, and its explicit non-goals. A bound that cannot name its files, tests, and non-goals is itself a stop, because the scope checks at steps 4 and 8 measure against it, and a vague bound disables them silently.
3. **Research.** Verify version-sensitive framework or provider behavior from primary upstream documentation.
4. **Implement** the smallest complete change that satisfies the slice.
5. **Validate narrowly** with focused tests and checks while iterating.
6. **Validate broadly.** Run every applicable command in the profile's `quality_commands`, and exercise the relevant local runtime path.
7. **Self-review** the combined diff for correctness, architecture, privacy, security, and missing tests. This catches mechanical problems early; it shares the builder's blind spots, so it never substitutes for the review phase.
8. **Repair and repeat.** Address what validation or self-review found and rerun the affected gates.
9. **Map coverage.** For each `AC-n` this slice touches, record the test or journey step that covers it, as a locator.
10. **Checkpoint.** Commit the slice with the profile's commit style and report.

A failing check is backpressure, not permission to weaken the check or change a requirement. A flaky or environment-blocked check is diagnosed and reported accurately.

## Stop conditions by step

The builder stops and reports to the manager when a condition below surfaces. Each is checked at the step where it first becomes visible, so a loop with nobody watching still checks it.

| Step | Conditions that surface here |
| --- | --- |
| 1. Orient | Unexpected changes overlap the planned edit and cannot be preserved. A governing document already conflicts with the working tree. |
| 2. Bound | An open choice would materially change product behavior or architecture. The slice cannot be bounded without crossing into a module another slice owns. |
| 3. Research | Upstream behavior contradicts a governing decision. The work needs a runtime dependency the plan does not name. Verification would require credentials or provider configuration. |
| 4. Implement | The change requires editing outside the scope stated at step 2. The only available implementation weakens a safety, privacy, authorization, or test boundary. An action in the profile's `prohibited_actions` or a `deploy_triggers` entry is required. |
| 5. Validate narrowly | A required result cannot be verified. Passing would require a value named in `data_sensitivity` or a live service the repository forbids tests to contact. |
| 6. Validate broadly | A gate is environment-blocked or flaky and cannot be diagnosed. Verification needs shared or production data or infrastructure. |
| 7. Self-review | The review surfaces a governing-document conflict, or a problem whose remedy is an architecture change rather than a repair. |
| 8. Repair and repeat | Three consecutive repair iterations fail the same gate. The only available fix weakens a gate or a boundary, or pushes edits outside the stated scope. |
| 9. Map coverage | A criterion has no test or journey locator. Reconciling the code with a governing decision would require editing the decision. |
| 10. Checkpoint | The loop's slice ceiling is reached. The plan is complete. A merge, a push to the default branch, or a deployment is the next action. |

A failing gate at step 5 or 6 is not a stop: it returns to step 8. Only the three-consecutive-failures rule turns repeated failure into a stop; without it a loop grinds against one gate indefinitely. Scope is checked twice, at step 4 and at step 8, both against the bound stated at step 2.

## Checkpoint report

At step 10 the builder reports:

- the slice and bound actually implemented;
- the files changed and the commit;
- focused checks, the quality commands run, and any runtime verification;
- the self-review result;
- the `AC-n` to test or journey locator coverage map from step 9;
- deviations, unverified claims, risks, and stop conditions; and
- the proposed next slice or the exact next action.

## Checkpoint decision

The manager authorizes the next slice only when all of these hold:

- the work stayed inside its bound;
- the coverage map names a test or journey step for every touched criterion;
- every applicable gate passed;
- no governing conflict or open decision appeared;
- no stop condition applies; and
- the next slice follows the plan's dependency order.

Otherwise it requests an in-scope correction from the same builder or escalates to the sponsor. A builder whose context or channel is lost ends the run's implementation: the manager stops and reports rather than substituting a new writer or inferring completion from the working tree.

## Loop mode

The manager may let the builder run several slices without a checkpoint only when both hold:

- the kickoff authorizes a loop with a slice ceiling; and
- the profile's `loop_ceiling` is not lower than that ceiling.

A loop checks every stop condition above at its step, stops hard at the slice ceiling and at the end of the plan, and never opens a pull request, merges, pushes to the default branch, or deploys.

Work whose substance is safety, privacy, or authorization runs checkpointed regardless of the profile or the kickoff. The rule is set by the kind of work, not by where it sits in a plan, so it applies whenever those boundaries are a slice's substance rather than incidental to it.

## Participating repository order

The manager records a dependency DAG and a stable order for independent slices in the approved plan. It dispatches one eligible slice at a time to the retained builder of its owner repository. A failed slice holds advancement to every other slice; its same builder corrects it within the three-consecutive-failure budget. Resume only after all required gates pass. A scope decision or exhausted budget goes to the sponsor. See `references/multi-repository.md`.
