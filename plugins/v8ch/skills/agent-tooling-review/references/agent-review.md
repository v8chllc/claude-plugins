# Agent definition review

## Registration and discovery

Confirm filename, metadata, location, and the client's current registration path. Trace how a caller actually invokes the agent.

## Delegation conditions

Check when the parent delegates, when it retains work, and whether conditions are mutually consistent. Verify that delegated tasks have bounded scope.

## Supplied context

Check inputs, repository state, identifiers, and authority passed to the agent. Follow missing-input behavior and whether the agent can distinguish source text from instructions.

## Supported configuration

Compare model, isolation, permission, and lifecycle fields with current official documentation for the target client and version. Record that version for capability-dependent findings.

## Available tools

Check the actual allowed tools and access needed by each step, including side effects, network access, and child delegation. Do not infer a permission from prose.

## Handoff

Check output shape, evidence, result ownership, and what the parent does when the agent fails or returns partial work.

## Stopping behavior

Trace success, refusal, blocked, timeout, and retry paths; confirm the agent stops before unauthorized writes or repeated work.

## Instructions versus runtime-enforced restrictions

Separate behavioral requests in the prompt from restrictions enforced by the client or sandbox. Report a concrete bypass or impossible instruction; do not credit a prose rule as a runtime guard.
