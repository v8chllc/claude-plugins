# MCP server review

## Discovery and schemas

Check server registration, transport, capability listing, tool names, descriptions, input and output schemas, and their fit with real client calls. Verify schema validation at the server boundary.

## Server implementation and error handling

Trace handler dispatch, side effects, async and cancellation paths, timeouts, error conversion, and resource cleanup. Review supporting code with ordinary correctness checks.

## Authentication, authorization and input validation

Identify the caller identity, credential flow, authorization decision per operation, and trust boundary for untrusted tool arguments or remote content. Inspect write and destructive paths especially closely. Do not read secrets to test this.

## Client wiring

Confirm the server launches in the target client, environment variables and paths resolve, capabilities appear, and the client can call them. Keep client-specific behavior distinct from protocol behavior.

## Repository tooling and Inspector

Use existing tests, schema validators, lint, and build commands. MCP Inspector may help in an authorized disposable environment; it is not a substitute for source inspection or authorization tests. Record exact commands and versions used.

## Limits when server source or runtime access is absent

For a remote server with no inspectable source, review visible schemas, configuration, client traces, and documented behavior. State implementation and security coverage as partial. Without runtime access, do not claim launch, auth, or error paths passed.
