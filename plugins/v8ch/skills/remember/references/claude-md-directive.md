## Memory

On session start: read `.remember/MEMORY.md`. If `.remember/` does not exist,
create it and create a stub `.remember/MEMORY.md` with sections for each type.
Also check `.remember/memory/` for today's journal file and read it if present.

When you learn something worth preserving, route it to the appropriate lane:

- **Curated memory** (durable facts): append to `.remember/MEMORY.md` under the correct
  type section using the templates below. Prefer updating an existing entry over creating
  a duplicate. For `context`, update the existing entry rather than appending a new one.
- **Procedural memory** (behavior-changing guidance): write only to approved agent-facing
  targets — `AGENTS.md`, `CODING_STANDARDS.md`, `ARCHITECTURE_STANDARDS.md`,
  `WORKFLOW_STANDARDS.md`, or relevant skill files. Do not write procedural memory to
  arbitrary workspace or product documents. Require confirmation before applying.
- **Daily journal** (episodic session notes): append to `.remember/memory/YYYY-MM-DD.md`.
  Use `/remember session` or `/recommend session` to capture the current session.

### Curated memory types

**entity** — a key object in the codebase (module, class, service, API, database)

    <!-- entity -->
    Entity: <name>
    Type: <Class | Service | API | Database | Module>
    Location: <path>
    Purpose: <one line>
    Dependencies: <comma-separated, or none>
    Notes: <optional>

**decision** — the why behind a technical or architectural choice

    <!-- decision -->
    Decision: <what was decided>
    Date: <YYYY-MM-DD>
    Rationale: <why>
    Do not reverse: <consequence of reverting — omit if not significant>

**error** — a known failure mode, gotcha, or bug and its fix

    <!-- error -->
    Symptom: <what goes wrong>
    Root cause: <why it happens>
    Fix: <how to resolve>
    Status: <resolved | watch>

**context** — current project state, in-progress work, blockers (one entry; update in place)

    <!-- context -->
    Status: <phase or state>
    In progress: <what is being worked on>
    Blocked: <optional>
    Next: <optional>
    Updated: <YYYY-MM-DD>

**preference** — how the user likes to work; applies across sessions

    <!-- preference -->
    Preference: <the preference>
    Scope: <global | <language> | <tool>>

**todo** — a durable follow-up item; promote to a work item when ready

    <!-- todo -->
    Todo: <short action-oriented title>
    Source: <conversation | review | bug | plan | user>
    Status: <open | blocked | done | obsolete>
    Next action: <specific next step>
    Owner: <optional>
    Created: <YYYY-MM-DD>
    Work item: <optional link/id if created>
