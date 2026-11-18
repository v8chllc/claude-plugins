# Repository profile template

Copy this block into the repository's agent steering document, under the heading
shown. The manager reads it at resolve; `workflows/contracts/repository-profile.md`
defines what each field means and what happens when one is absent.

A keyed block, rather than prose, for three reasons: the manager reads sixteen
values without inferring them, a reader can tell a stated value from a default,
and each key can be checked against the skill's universal prohibitions — a
profile narrows authority and can never widen it.

## The block

````markdown
## Agent workflow profile

```yaml
autonomy: checkpointed        # or: autonomous, to skip sponsor plan approval
tracking: required            # or: none
coordination_repository: <owner>/<repository where run issues live>
branch_naming: "type/short-description"
commit_style: conventional
merge_method: rebase          # reported to the sponsor; the run never merges
required_gates:
  - <external check that must pass, and how to poll it>
review_capability: consensus-review  # or: agent-tooling-review (change-set, feature, chore)
journey: none                 # or: "automated: <command>", or "manual: <where results are recorded>"
loop_ceiling: 0               # the most slices a loop may run without a checkpoint
quality_commands:
  - <lint>
  - <format check>
  - <type check>
  - <tests>
release_steps:
  - <version bump, manifest update, or publication step a change requires>
prohibited_actions:
  - <command, branch, or path this repository forbids>
deploy_triggers: none         # or: <ref, branch, or command that reaches production>
data_sensitivity:
  - <value that must never be logged, committed, or sent to a live service>
synchronized_with: none       # or: <repository that carries the same change>
```
````

Omit a key you have no value for. An omitted key resolves from the workspace
named child block for this repository, then the workspace default child block,
then the conservative field default when the run starts from a workspace
holding this repository. Without that workspace, it resolves from the field default. Resolution is per
field, so stating a few keys costs you nothing on the rest. The run records
which source supplied each field.

## Worked example

A public plugin repository whose releases are consumed from a cache:

````markdown
## Agent workflow profile

```yaml
autonomy: autonomous
tracking: required
branch_naming: "type/short-description"
commit_style: conventional
merge_method: rebase
required_gates:
  - CI checks on the PR head SHA
review_capability: consensus-review
quality_commands:
  - uv run ruff check .
  - uv run ruff format --check .
  - uv run mypy .
  - uv run pytest
release_steps:
  - bump the version in plugins/<name>/.<toolchain>-plugin/plugin.json in the
    same pull request; a merged change with no bump ships a version already
    present in installed caches
prohibited_actions:
  - never copy private content into this public repository
deploy_triggers: none
data_sensitivity: none
synchronized_with: <the sibling repository>
```
````

## Workspace named-child example

The workspace document can keep its own profile separate from shared child defaults and optional sparse named overrides. The heading supplies the full `owner/repo` identity; add no identity field to the YAML.

````markdown
## Agent workflow profile

### This repository

```yaml
coordination_repository: example/planning
review_capability: consensus-review
```

### Child repository defaults

```yaml
autonomy: autonomous
tracking: required
coordination_repository: example/planning
branch_naming: "type/short-description"
commit_style: conventional
merge_method: rebase
required_gates: none
review_capability: consensus-review
quality_commands: ["uv run pytest"]
release_steps: none
prohibited_actions: ["never merge"]
deploy_triggers: none
data_sensitivity: none
synchronized_with: none
```

### Child repository: example/widgets

```yaml
review_capability: agent-tooling-review
```
````

For `example/widgets` and unnamed `example/tools`, neither repository states its own profile. Each row below lists the resolved value and its source. Unstated `journey` and `loop_ceiling` demonstrate field defaults; the named block overrides only `review_capability`.

| Field | `example/widgets` value | Source | `example/tools` value | Source |
| --- | --- | --- | --- | --- |
| `autonomy` | autonomous | default child block | autonomous | default child block |
| `tracking` | required | default child block | required | default child block |
| `coordination_repository` | example/planning | default child block | example/planning | default child block |
| `branch_naming` | type/short-description | default child block | type/short-description | default child block |
| `commit_style` | conventional | default child block | conventional | default child block |
| `merge_method` | rebase | default child block | rebase | default child block |
| `required_gates` | none | default child block | none | default child block |
| `review_capability` | agent-tooling-review | named child block: example/widgets | consensus-review | default child block |
| `journey` | none | field default | none | field default |
| `loop_ceiling` | 0 | field default | 0 | field default |
| `quality_commands` | ["uv run pytest"] | default child block | ["uv run pytest"] | default child block |
| `release_steps` | none | default child block | none | default child block |
| `prohibited_actions` | ["never merge"] | default child block | ["never merge"] | default child block |
| `deploy_triggers` | none | default child block | none | default child block |
| `data_sensitivity` | none | default child block | none | default child block |
| `synchronized_with` | none | default child block | none | default child block |

If `example/widgets` states `review_capability: consensus-review` in its own profile, that value wins over the named block's `agent-tooling-review`. Resolution remains repository profile, named child block, default child block, field default. Record the tier for each inherited field in the coordination record's resolved-profile prose, keeping the existing `profile_inherited` and `profile_defaults` lists.

## What a missing profile costs

Nothing breaks. Every field resolves from the matching named child block, then
the default child block when there is a workspace, then the field defaults: plan approval becomes a sponsor
checkpoint, a repository issue is required, every push is assumed to reach
production, and all data is treated as sensitive. The one field with no workable
default is `coordination_repository`: without it no run has a home, so a
workspace profile usually states it once for every repository it holds. The cost is interruption — the
sponsor answers questions the repository could have answered once — and, where a
workspace supplied the value instead, a rule that does not travel with the
repository to another checkout.

A rule stated in prose elsewhere in the steering document is still binding, and
the reviewers and the builder read it. It just does not reach the manager as a
profile value, so the run reports that field as defaulted.
