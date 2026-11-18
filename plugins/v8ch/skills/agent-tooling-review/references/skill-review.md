# Skill review

## Activation and non-activation

Check metadata, name, description, entry points, and examples against the tasks that should and should not trigger the skill. Follow the actual discovery mechanism of the target client. Do not assume a skill is active merely because its folder exists.

## Instruction contradictions and workflow gaps

Trace prerequisites, ordering, failure branches, retries, and stop conditions. Identify impossible or conflicting instructions and concrete paths where the agent can skip a required check or exceed authority.

## References and bundled code

Resolve every referenced path from the skill's real installation layout. Inspect bundled scripts, templates, and commands for their effects, argument handling, exit behavior, and error reporting. Check that instructions use those assets correctly.

## Dependencies

Confirm named tools, versions, permissions, and platform APIs are available where the skill expects them. A dependency mentioned without an executable path is a coverage limitation until it causes a concrete failure.

## Unnecessary context or control

Identify instructions or loaded material that materially obscure task selection, duplicate higher-priority rules, or force irrelevant work. Explain the behavioral cost; brevity or style alone is not a defect.

## Supported requirements versus stylistic preferences

Anchor findings to the issue, contract, client behavior, or reproduced consequence. Offer optional prose preferences separately, if useful, and never present them as defects.
