# Architecture Standards

## Scope

These standards apply to the Claude Plugins repository. They define structural
boundaries for plugin skills, helper scripts, templates, and agent-owned
workflow interpretation.

## Helper Script Boundaries

- Keep helper scripts focused on deterministic infrastructure work: source data,
  normalize unstable tool output, compute mechanical query parameters, render
  deterministic templates, and perform transport operations.
- Do not put subjective interpretation, prioritization, final narrative
  authorship, or business judgment into helper scripts when the source content
  is messy, account-specific, or preference-sensitive.
- For workflows that require judgment, use agent instructions or LLM-facing
  Markdown guidance/templates to define categories, grounding rules, and output
  shape.
- Keep generated evidence and rendered artifacts traceable to source fields so
  an agent can ground interpretive summaries without re-running the source
  integration.
- Prefer scripts that expose narrow, testable contracts and leave summary
  authorship or status determination to the calling skill or agent.
