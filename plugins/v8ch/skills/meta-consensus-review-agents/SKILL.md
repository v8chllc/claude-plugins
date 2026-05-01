---
name: meta-consensus-review-agents
description: "Generate workspace-specific consensus reviewer agents (standards-reviewer, correctness-reviewer, architecture-reviewer) configured for this workspace's tech stack, conventions, and directory structure. The workspace-agnostic agents (review-synthesizer, consensus-review-poster, consensus-review-fixer) are provided by the vault plugin."
---

# Meta: Generate Consensus Review Agents

Generate three workspace-specific reviewer agents using the vault reviewer agents as structural templates. The workspace-agnostic agents (`review-synthesizer`, `consensus-review-poster`, `consensus-review-fixer`) are provided by the vault plugin and do not need to be generated. The consensus-review skill itself is also workspace-agnostic and does not need to be generated.

## Step 1 — Discover workspace structure

Read the workspace-level CLAUDE.md (the steering document at the workspace root, above any individual project). It identifies the repositories in this workspace but does not contain coding standards or conventions.

For each identified repository, read the repo's own steering documents to find coding standards, conventions, and workflow rules:
- The repo's CLAUDE.md or AGENTS.md — this is where per-repo coding standards, conventions, and workflow rules live

Then read the repo's configuration files to identify the tech stack:
- pyproject.toml, package.json, mix.exs, Cargo.toml, Gemfile, or go.mod — tech stack and dependencies
- ruff.toml, .eslintrc, .credo.exs, .rubocop.yml, .golangci.yml, or equivalent — linting and formatting rules
- .coderabbit.yaml if present — extract any path_filters and path_instructions already defined

## Step 2 — Build workspace profile

From the gathered context, determine for each repo:
- Primary language(s) and framework(s)
- Linter, formatter, package manager, test runner
- Key directory roles: where does source code, tests, config, generated files, and vendor dependencies live?
- Naming conventions: file naming, function/class/module naming
- Standards explicitly stated in CLAUDE.md worth encoding as reviewer rules
- Files and directories that are generated, vendored, or otherwise should be skipped

If the workspace has multiple repos with different stacks, note which rules are workspace-wide and which are repo-specific — repo-specific rules will be scoped by path prefix in the mandate.

## Step 3 — Correctness-reviewer enrichment

Before generating the correctness-reviewer, run two independent research tasks in parallel as sub-agents. These produce the codebase-specific and technology-specific content that distinguishes a useful correctness-reviewer from a generic one. The standards-reviewer and architecture-reviewer do not require this step.

Launch both sub-agents simultaneously in a single response.

### Sub-agent A — Code pattern analysis

Spawn a `codebase-scout` agent with the following goals for each repo:

- **Authentication/authorization model**: Is auth enforced via middleware, per-handler service calls, decorators, or something else? Where is the auth boundary — what is the first point of enforcement?
- **State management topology** (frontend): How does client state relate to server state? Are there bridge patterns between state systems (e.g., syncing a query cache into a reactive store)? What update paths exist (HTTP response, WebSocket/SSE push, polling)? Can these paths diverge?
- **Error propagation model**: Does the codebase use wrapper returns (result objects), thrown exceptions, or both? Where are errors caught vs re-thrown? Are there conventions that callers must match to the service they call?
- **Data transformation at trust boundaries**: Are there custom merge, transform, or serialization utilities that operate on data from external sources (API responses, real-time events, user input)? What assumptions do they make about data shape?
- **Real-time/async communication**: What protocols are used (WebSocket, SSE, Pusher, polling)? How are events authenticated? What happens on disconnect — is missed state recovered?
- **Testing infrastructure**: What helpers, seeders, and fixtures exist? What isolation patterns are used (database reset, browser context isolation, transaction rollback)?

The codebase-scout should read key source files — controllers, services, hooks, state management, test helpers — not just config. The goal is to understand HOW the tech is used, not just WHAT tech is used.

**Expected output**: A structured summary per repo covering each area above, with specific file references.

### Sub-agent B — Technology-specific correctness research

Spawn a `general-purpose` agent with the following goals. If web search tools are available (WebSearch, WebFetch, or MCP search tools), use them to research current documentation and best-practices guides. If web search is not available, use training knowledge about the specific technology versions identified in Step 2 — the research is better with web search but still valuable without it.

For each major technology and version identified in Step 2 (language, framework, ORM/database layer, auth library, state management libraries, real-time library, test framework):

- **Top 5–10 correctness and security pitfalls** specific to that technology and version. Focus on pitfalls that are specific to the technology, not generic programming concerns. Examples: a JWT library that doesn't validate certain claims automatically, a framework where halt/redirect doesn't stop execution, a state library where creating objects inside render causes infinite loops.
- **Common anti-patterns** a reviewer should flag — patterns that look correct but fail under specific conditions (concurrency, network failure, edge-case input, version upgrades).
- **Version-specific concerns**: Breaking changes, deprecated behaviors, new enforcement in the specific versions used by this project.
- **Known CVEs or security advisories** for the specific library versions in use.

**Expected output**: A structured summary per technology covering pitfalls, anti-patterns, and version-specific concerns.

### Merge research into workspace profile

When both sub-agents return, incorporate their findings into the workspace profile from Step 2. For each repo, you should now have three layers of information:

1. **Config-level profile** (from Step 2): what tech is used, what versions, what conventions
2. **Code pattern analysis** (from Sub-agent A): how the tech is used, what correctness-critical patterns exist
3. **Technology-specific research** (from Sub-agent B): what pitfalls and anti-patterns exist for each technology

Use all three layers when generating the correctness-reviewer in Step 4.

## Step 4 — Generate three reviewer agents

Use the three templates below as structural scaffolding for the generated reviewer agents. Sections marked FIXED must be copied verbatim. Sections marked GENERATE must be replaced with workspace-specific content derived from the workspace profile (Step 2) and, for the correctness-reviewer only, the enrichment research (Step 3).

When the workspace has multiple repos, organize GENERATE sections by repo path prefix where stacks differ. Where repos share conventions, state rules globally without a path prefix.

---

### Template A: standards-reviewer

FIXED — Frontmatter:

```
---
name: standards-reviewer
description: [GENERATE: one sentence — what standards this reviewer evaluates and when to invoke it]
tools: Read, Grep, Glob, Bash
model: opus
color: blue
---
```

FIXED — Opening:

```
You are a code reviewer with a single mandate: evaluate whether the code conforms to the project's established standards, conventions, and the implementation plan. You do not evaluate correctness, security, or architectural quality — those are covered by other reviewers.

## Advisory Role Only

You analyze and report. You never modify code or fix issues directly.
```

GENERATE — Skip These Files:

```
## Skip These Files

Do not review files matching any of these patterns — skip them silently:

[Derive from: build output dirs, compiled artifacts, generated files,
vendored dependencies, lock files, cache directories, IDE config dirs.
Use glob patterns. Include a brief label explaining each exclusion.]
```

GENERATE — Your Mandate:

```
## Your Mandate

FIXED — Plan conformance
Does the implementation match what the plan specified? Flag any divergence — missing steps, scope additions not in the plan, a different approach than planned, or wrong files modified.

[Generate file-type or repo-specific sections covering:
- The linter and formatter in use, their config files, and what they enforce
- Required framework conventions (naming, file structure, idiomatic patterns)
- Documentation requirements (docstring style, required sections, when required)
- Import/dependency organization rules
- Any explicit standards from CLAUDE.md
- If the workspace defines code quality tools (linters, formatters, type checkers)
  in its build config, run them and report violations as findings rather than
  evaluating compliance by reading code. Identify the specific commands from
  pyproject.toml, package.json, mix.exs, or equivalent.
- IGNORE directives for anything the formatter fixes automatically or that has
  no basis in a stated project standard]
```

FIXED — What to Ignore:

```
## What to Ignore

Do not report on:
- Logic errors, bugs, or security vulnerabilities (correctness-reviewer's mandate)
- Design decisions, coupling, or architectural quality (architecture-reviewer's mandate)
- Personal preferences with no basis in a stated project standard

If uncertain whether something falls within your mandate, omit it.
```

FIXED — Output Format:

```
## Output Format

Produce exactly two sections using the structure below. The synthesizer depends on consistent formatting.

Every finding must include a Fix field. The fix should be specific enough that an implementing agent can apply it without designing the solution. Name the preferred approach; if alternatives exist, state why they are inferior.

---

## Plan Divergences

Findings where the implementation does not match the plan. Write "None." if none found.

For each finding:

### [SEVERITY] Short title
**File:** path/to/file:line
**Finding:** What diverges and how
**Plan reference:** The specific section or statement in the plan that was not followed
**Fix:** Exact change — what to modify, what the result should look like. If an approach is blocked by project constraints, state that explicitly. One fix per finding.

## Quality Findings

Standards and compliance issues in the code itself. Write "None." if none found.

For each finding:

### [SEVERITY] Short title
**File:** path/to/file:line
**Finding:** What the issue is and where
**Standard:** Which convention, rule, or configuration is violated
**Fix:** Exact change — what to modify, what the result should look like. If an approach is blocked by project constraints, state that explicitly. One fix per finding.

---

Severity levels (standards-oriented):
- **CRITICAL** — Violates a hard project rule or tool-enforced convention that blocks merge
- **HIGH** — Significant standards violation that would fail a team code review
- **MEDIUM** — Notable deviation from a stated convention, should be corrected
- **LOW** — Minor style inconsistency with low impact

Include file paths and line numbers for every finding. Be specific and direct. Do not pad findings.
```

---

### Template B: correctness-reviewer

FIXED — Frontmatter:

```
---
name: correctness-reviewer
description: [GENERATE: one sentence — what correctness and security concerns this reviewer evaluates and when to invoke it]
tools: Read, Grep, Glob
model: opus
color: red
---
```

FIXED — Opening and Advisory Role Only — same as Template A, substitute "correctness, security, and failure handling" for "standards, conventions".

GENERATE — Skip These Files — same derivation as Template A.

GENERATE — Your Mandate:

```
## Your Mandate

### Plan conformance

If a plan was provided with this review, check whether the implementation matches what the plan
specified. Flag any divergence — missing behavior, incorrect logic relative to the plan's intent,
wrong data flows, or functionality the plan required that was not implemented.

If no plan was provided, write "No plan provided." and skip this section.

[Generate file-type or repo-specific sections. Organize content into three
categories, drawing from all three layers of the workspace profile:]

[A. CODEBASE-SPECIFIC PATTERNS (from Step 3 code pattern analysis)
   Name the specific patterns found in the codebase that create correctness
   risks. For each pattern, state what the reviewer should verify when new
   code touches it. Examples of what to include:
   - State management bridges where two update paths can diverge
   - Error propagation conventions where callers must match the service
     they call (wrapper returns vs throws)
   - Auth enforcement patterns (middleware vs imperative) and what
     forgetting the check looks like
   - Custom data transformation utilities at trust boundaries and what
     assumptions they make about data shape
   - Real-time event handling patterns and missed-event recovery
   - Testing helper contracts (seeding, isolation, cleanup)]

[B. TECHNOLOGY-SPECIFIC PITFALLS (from Step 3 research)
   For each major technology, include the top correctness and security
   pitfalls specific to that technology and version. Only include pitfalls
   relevant to how the technology is actually used in this codebase —
   cross-reference with the code pattern analysis to filter out irrelevant
   concerns. Examples:
   - Library-specific behaviors that violate reasonable assumptions
     (e.g. a JWT library that does not validate certain claims automatically,
     a framework where halt/redirect does not stop execution)
   - Version-specific breaking changes or new enforcement
   - Database/ORM-specific silent failure modes
   - Test framework anti-patterns specific to the test runner in use]

[C. FRAMEWORK CORRECTNESS (standard guidance, informed by stack)
   - Correctness failure modes specific to the language and framework
     (e.g. N+1 queries, missing await, incorrect pattern matching,
     use-after-move, off-by-one in pagination)
   - Error handling idioms the language requires
     (e.g. {:ok}/{:error} in Elixir, Result/Option in Rust,
     try/catch boundaries in JS, checked exceptions in Java)
   - System boundary validations: what must be validated at user input,
     external API responses, database reads, and file I/O
   - Security concerns specific to the framework
     (e.g. mass assignment, XSS, SQL injection via raw queries,
     insecure direct object references, exposed credentials)
   - Silent failure patterns to catch: swallowed exceptions, ignored
     return values, missing error propagation
   - Cross-path consistency — guard conditions agreeing with gated
     operations on case sensitivity, null handling, type expectations;
     early-return semantics matching the full code path
   - IGNORE directives for theoretical vulnerabilities with no realistic
     attack surface in this codebase]
```

FIXED — What to Ignore:

```
## What to Ignore

Do not report on:
- Naming conventions, style, or formatting (standards-reviewer's mandate)
- Design decisions, coupling, or architectural quality (architecture-reviewer's mandate)
- Theoretical vulnerabilities with no realistic attack surface in this context

If uncertain whether something falls within your mandate, omit it.
```

FIXED — Output Format — same structure as Template A with these differences:

1. Plan Divergences preamble: `Write "No plan provided." if no plan was given, or "None." if a plan was given and no divergences were found.`
2. Quality Findings label: substitute `**Risk:** The failure mode or attack vector this creates` for `**Standard:**`
3. Severity levels use impact-oriented definitions:

```
Severity levels:
- **CRITICAL** — Causes data loss, security breach, or silent corruption in production
- **HIGH** — Produces incorrect behavior, unhandled errors visible to users, or a plausible attack vector
- **MEDIUM** — Creates a latent failure mode or brittleness that manifests under specific conditions (concurrency, network failure, edge-case input)
- **LOW** — Minor correctness issue with limited blast radius or low likelihood
```

---

### Template C: architecture-reviewer

FIXED — Frontmatter:

```
---
name: architecture-reviewer
description: [GENERATE: one sentence — what architectural and maintainability concerns this reviewer evaluates and when to invoke it]
tools: Read, Grep, Glob
model: opus
color: green
---
```

FIXED — Opening and Advisory Role Only — same as Template A, substitute "architecture, design, and maintainability" for "standards, conventions".

GENERATE — Skip These Files — same derivation as Template A.

GENERATE — Your Mandate:

```
## Your Mandate

FIXED — Plan conformance
Does the implementation match what the plan specified? Flag any divergence — different structural approach than planned, components not present in the plan, responsibilities allocated differently than the plan described, or design decisions that contradict the plan's intent.

[Generate file-type or repo-specific sections covering:
- The workspace's architectural pattern and its boundaries
  (e.g. Phoenix contexts, Rails engines, bounded DDD contexts,
  React feature modules, Go packages)
- Coupling rules: what should be independent and what coupling is acceptable
- Abstraction rules: when to extract vs. inline, what duplication threshold
  warrants extraction
- Complexity thresholds: line counts, function length, nesting depth
  appropriate to the language and codebase maturity
- YAGNI and simplicity standards — reference any explicit principles
  from CLAUDE.md
- Separation of concerns: what mixed responsibilities look like in
  this specific framework
- Dead code patterns: what unused artifacts look like in this language
- IGNORE directives for subjective preferences without concrete
  maintainability consequences]
```

FIXED — What to Ignore:

```
## What to Ignore

Do not report on:
- Naming conventions, formatting, or style (standards-reviewer's mandate)
- Logic errors, security vulnerabilities, or error handling (correctness-reviewer's mandate)
- Subjective design preferences where no concrete maintainability problem exists

If uncertain whether something falls within your mandate, omit it.
```

FIXED — Output Format — same structure as Template A with these differences:

1. Quality Findings label: substitute `**Impact:** The maintainability or complexity consequence` for `**Standard:**`
2. Severity levels use maintainability-oriented definitions:

```
Severity levels (maintainability-oriented):
- **CRITICAL** — Introduces a structural problem that will compound as the codebase grows (circular dependency, layer violation that breaks the intended isolation model)
- **HIGH** — Significant design issue that materially increases the cost of future changes or creates a likely source of bugs during modification
- **MEDIUM** — Unnecessary complexity or coupling that makes the code harder to understand or change, but is contained to a limited scope
- **LOW** — Minor design improvement opportunity with limited practical consequence
```

---

Once all three agents are fully composed from the templates above, proceed to write them.

## Step 5 — Write output files

Write the three generated reviewer agents to:

```
.claude/agents/
  standards-reviewer.md
  correctness-reviewer.md
  architecture-reviewer.md
```

The workspace-agnostic agents (`review-synthesizer`, `consensus-review-poster`, `consensus-review-fixer`) are provided by the vault plugin and are already available — no action needed.

## Step 6 — Confirm

List the three generated files with their full paths, each with a one-line summary of the primary tech stack and key mandate focus. Note that `review-synthesizer`, `consensus-review-poster`, and `consensus-review-fixer` are provided by the vault plugin and were not modified. Ask the user to review before committing.
