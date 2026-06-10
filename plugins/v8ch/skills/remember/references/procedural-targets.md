# Procedural Memory Targets

Procedural memory records behavior-changing guidance for future agents. It has
higher blast radius than curated or journal memory. Only write to the approved
target set listed here.

---

## Approved targets

| Target | Purpose |
|--------|---------|
| `AGENTS.md` | Repo or workspace operating rules — how agents should work in this context |
| `CODING_STANDARDS.md` | Code style, testing conventions, language-specific rules |
| `ARCHITECTURE_STANDARDS.md` | Architecture boundaries, invariants, system design constraints |
| `WORKFLOW_STANDARDS.md` | Agent-facing workflow standards — repeatable multi-step routines |
| Relevant skill files | Repeatable tool integrations or skill-specific multi-step routines |

Resolve the path relative to the current workspace or repo root unless the
candidate clearly belongs to a specific child repository.

---

## Routing rules

Use these signals to classify a procedural candidate into the right target:

- **Repo/workspace operating rules** (how agents behave in this project, what to
  check before committing, what not to do): → `AGENTS.md`
- **Code style or testing conventions** (naming conventions, linting rules, test
  patterns, language idioms): → `CODING_STANDARDS.md`
- **Architecture constraints** (module boundaries, service separation, invariants
  that must not be violated, approved/forbidden patterns): → `ARCHITECTURE_STANDARDS.md`
- **Multi-step agent workflows** (how to run a repeatable process, what sequence
  of steps an agent should follow): → `WORKFLOW_STANDARDS.md`
- **Tool-specific or skill-specific routines** (how to use a particular CLI,
  integration steps for a specific tool, workflow taught by a skill): → relevant skill file

---

## Fail-closed rule

If a candidate does not fit any approved target:

1. Surface it to the user as unsupported.
2. Describe what the candidate says and why it does not map to an approved target.
3. Ask for explicit user direction:
   - Is there a skill file that owns this area?
   - Should a new standards file be created?
   - Should this be recorded as curated memory instead?
4. Do not write to an arbitrary workspace, product, team, or process document
   outside the approved set.

---

## Creating missing targets

Do not automatically create procedural target files during setup.

- Report missing targets as optional managed files.
- Offer to create stubs only when the user asks or when a procedural write
  requires the file.
- Create `WORKFLOW_STANDARDS.md` first when workflow procedural memory is
  expected and no workflow standards file exists.
- Create `CODING_STANDARDS.md` or `ARCHITECTURE_STANDARDS.md` just in time when
  a specific procedural write needs that target.
- Always get approval before creating a new standards file.

### Stub format for `WORKFLOW_STANDARDS.md`

```md
# Workflow Standards

Agent-facing workflow standards for this workspace.

<!-- Add repeatable multi-step workflow guidance here. -->
```

### Stub format for `CODING_STANDARDS.md`

```md
# Coding Standards

Code style and testing conventions for this workspace.

<!-- Add language-specific rules, naming conventions, and test patterns here. -->
```

### Stub format for `ARCHITECTURE_STANDARDS.md`

```md
# Architecture Standards

Architecture boundaries and invariants for this workspace.

<!-- Add module boundaries, forbidden patterns, and system design constraints here. -->
```

---

## Dedupe before writing

Before proposing a procedural write:

1. Read the existing target file.
2. Check whether related guidance already exists.
3. If guidance is already covered: mark `skip`.
4. If guidance is partially covered: propose an update patch to the existing section.
5. If guidance is missing: propose a concise new entry or rule.

Prefer updating existing guidance over appending duplicate rules.
