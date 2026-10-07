# Memory Types

Structured types, all curated memory in `.remember/MEMORY.md`. Use these
templates when writing entries.

---

## entity

A key object in the codebase: module, class, service, API, or database.

Template:
```
<!-- entity -->
Entity: <name>
Type: <Class | Service | API | Database | Module>
Location: <path>
Purpose: <one line>
Dependencies: <comma-separated, or none>
Notes: <optional>
```

Example:
```
<!-- entity -->
Entity: UserAuthService
Type: Class
Location: src/auth/service.py
Purpose: Handles JWT issuance, validation, and refresh logic
Dependencies: UserRepository, RedisSessionStore
Notes: Intentionally stateless — session data lives in Redis, not the instance
```

---

## decision

The why behind a technical or architectural choice. The most valuable type — captures
reasoning that is otherwise lost.

Template:
```
<!-- decision -->
Decision: <what was decided>
Date: <YYYY-MM-DD>
Rationale: <why>
Do not reverse: <consequence of reverting — omit if not significant>
```

Example:
```
<!-- decision -->
Decision: Use SQLite for local dev, PostgreSQL in production
Date: 2025-05-20
Rationale: Dev/prod parity not needed for this service; keeps onboarding simple
Do not reverse: Saves ~15 min of setup per new dev machine
```

---

## error

A known failure mode, gotcha, or bug — and how to fix it.

Template:
```
<!-- error -->
Symptom: <what goes wrong>
Root cause: <why it happens>
Fix: <how to resolve>
Status: <resolved | watch>
```

Example:
```
<!-- error -->
Symptom: uv run fails with "no project found" in CI
Root cause: pyproject.toml not in the working directory at job start
Fix: Add `working-directory: ./backend` to the CI job step
Status: resolved
```

---

## preference

How the user likes to work. Applies across sessions and is not project-specific.
Preferences guide Claude's behavior without requiring repeated instruction.

Template:
```
<!-- preference -->
Preference: <the preference>
Scope: <global | <language> | <tool>>
```

Examples:
```
<!-- preference -->
Preference: Use uv instead of pip for all Python package operations
Scope: python
```

```
<!-- preference -->
Preference: Concise responses — no trailing summaries after completing a task
Scope: global
```

```
<!-- preference -->
Preference: snake_case for Python identifiers, camelCase for TypeScript
Scope: global
```

---

## todo

A durable follow-up item that should not be lost between sessions. Promote to a work item
(issue, task, ticket) when ready for execution.

A todo is only ever `open` or `blocked`. Promoting a todo to a work item, or
completing or abandoning it, removes it from `.remember/MEMORY.md`; a completed or
obsolete todo is removed, not marked.

Template:
```
<!-- todo -->
Todo: <short action-oriented title>
Source: <conversation | review | bug | plan | user>
Status: <open | blocked>
Next action: <specific next step>
Owner: <optional>
Created: <YYYY-MM-DD>
Work item: <legacy; leave empty — promotion removes the todo>
```

Examples:
```
<!-- todo -->
Todo: Migrate auth middleware to shared library
Source: review
Status: open
Next action: Extract auth middleware from api-gateway into shared-lib
Owner: backend-team
Created: 2025-06-01
Work item:
```

```
<!-- todo -->
Todo: Update CORS configuration for staging
Source: bug
Status: blocked
Next action: Confirm allowed origins list with infra team
Created: 2025-05-28
Work item:
```
