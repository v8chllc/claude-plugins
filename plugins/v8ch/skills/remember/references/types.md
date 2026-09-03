# Memory Types

Six structured types. Five are curated memory in `.remember/MEMORY.md`;
`context` is local-only state in `.remember/local/context.md`. Use these
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

## context

Current project state, what is in progress, and what is blocked.

**Stored in `.remember/local/context.md`, never in `.remember/MEMORY.md`.** That
directory is gitignored, so context stays in the checkout that wrote it. Context
is state as of a moment on one machine; shared through Git it reads as durable
fact on every other checkout long after it stopped being true.

Update this type rather than appending a new entry — the file holds at most one
active context entry.

Template:
```
<!-- context -->
Status: <phase or state>
In progress: <what is being worked on>
Blocked: <optional>
Next: <optional>
Updated: <YYYY-MM-DD>
```

Example:
```
<!-- context -->
Status: Migrating auth layer from session cookies to JWT
In progress: Implementing refresh token rotation
Blocked: Waiting on security review of token storage approach
Next: Update frontend to handle 401 + refresh flow
Updated: 2025-05-25
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

Template:
```
<!-- todo -->
Todo: <short action-oriented title>
Source: <conversation | review | bug | plan | user>
Status: <open | blocked | done | obsolete>
Next action: <specific next step>
Owner: <optional>
Created: <YYYY-MM-DD>
Work item: <optional link/id if created>
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
