# Headless manager

The supervisor Authority section in `../SKILL.md` owns every condition for
running these commands. Apply those conditions before any command below. This
reference supplies commands and grants no further authority.

## Decisions

- Use the toolchain default and readiness authority in the supervisor skill unless
  the sponsor decides otherwise; the sponsor supplies the run issue and scope. Set
  `RUN` to an absolute `.prompts/runs/<run issue key>/` directory (for example
  `.prompts/runs/OPS-42/`) and `WORKSPACE` to the manager's checkout. Retain
  `kickoff.txt`, `pid`, `session-id`, `stream.jsonl`, `stderr.log`,
  `last-message.txt` for Codex and `relay.txt` there.
  The files are gitignored.
- The sponsor's launch authority covers the permission-bypass flag used below:
  Claude Code uses `--dangerously-skip-permissions`; Codex uses
  `--dangerously-bypass-approvals-and-sandbox`. These flags do not change the
  manager's task authority.
- One manager process group owns one turn. `nohup perl -MPOSIX` calls
  `POSIX::setsid()` and then `exec`s the manager. The recorded PID equals its
  PGID. The process-group exit is the turn boundary, including any child.
- No helper program, startup parser, or automatic lock recovery is used. A
  supervisor reads the stream and process state directly.

## Acquire and release the operation lock

Before each launch, resume, or stop, run this as its own shell tool invocation.
The lock directory persists after that shell exits and stays held through the
later liveness and action invocations. Retain the printed `LOCK_OWNER` value for
the explicit release step. An existing lock goes to the sponsor; do not remove or reuse it,
even if its owner appears gone. The lock has exactly one owner file.

```sh
if ! mkdir -p "$RUN"; then
  printf '%s\n' "cannot create run directory $RUN" >&2
  exit 1
fi
LOCK="$RUN/.operation-lock"
if ! mkdir "$LOCK"; then
  printf '%s\n' "operation lock exists for $RUN; sponsor decision required" >&2
  exit 1
fi
LOCK_OWNER=$(uuidgen)
printf '%s\n' "$LOCK_OWNER" > "$LOCK/owner"
printf 'LOCK_OWNER=%s\n' "$LOCK_OWNER"
```

After the operation succeeds or fails, run the release fence as a separate
shell tool invocation and pass the exact `LOCK_OWNER` printed by acquisition in
that invocation's environment. Release only when it matches the owner file. A
missing value or changed owner leaves the lock in place for the sponsor. Never
clear someone else's lock.

```sh
LOCK="$RUN/.operation-lock"
test -n "${LOCK_OWNER:-}" || exit 1
test -f "$LOCK/owner" || exit 1
test "$(cat "$LOCK/owner")" = "$LOCK_OWNER" || exit 1
rm "$LOCK/owner" && rmdir "$LOCK"
```

## Check liveness before each operation

Under the lock, read the recorded PID and all members of that process group.
Run this before **every** launch, resume, and stop or signal, immediately before
the action. `ps` is read-only. Do not infer a dead run from the leader alone: a
child may remain in its group. Check the PGID column equals the recorded PID.

```sh
PID=$(cat "$RUN/pid" 2>/dev/null || true)
if test -n "$PID"; then
  case "$PID" in *[!0-9]*) printf '%s\n' 'invalid recorded PID; sponsor decision required' >&2; exit 1 ;; esac
  ps -axo pid=,pgid=,stat=,command= | \
    awk -v group="$PID" '$2 == group && $3 !~ /^Z/ { print }'
fi
```

Interpret every returned row before acting. For Claude Code, the manager row
must contain `claude` and the preset ID from `session-id`: `--session-id <ID>`
on launch or `--resume <ID>` on relay. For Codex, the manager row on **every
turn** must contain `codex` and the absolute `$RUN/last-message.txt` argument.
The recorded PID must be the group's PGID; a different command or identity is
a sponsor decision. If a matching manager or child is live, **do not launch or
resume**. A live group blocks a second writer. If the group has no members, a
relay may resume the recorded session ID only; it never starts a new session.
For stop, signal only a validated live group. Do not signal a reused PID or a
group with a mismatched identity.

## Restart after a readiness or resolve stop

A restart launches a new manager session with a fresh run ID on the same run issue; it is not a relay or a resume. Apply the supervisor's readiness fix rule and rerun preflight first. Acquire the operation lock and perform the liveness and platform identity check above; do not proceed while any member of the earlier process group is live. Before the restart launch, move the earlier run's `stream.jsonl`, `stderr.log` and `last-message.txt` into `$RUN/<earlier run_id>/` so the new launch cannot overwrite them. Use the actual earlier run ID as `EARLIER_RUN_ID`; do not reuse an existing archive. Preserve any present kickoff, PID and session identity there too, then write the fresh kickoff to `$RUN/kickoff.txt`. Missing output from a failed turn is permitted; record absent files in findings.

```sh
ARCHIVE="$RUN/$EARLIER_RUN_ID"
mkdir "$ARCHIVE" || exit 1
for name in stream.jsonl stderr.log last-message.txt kickoff.txt pid session-id; do
  if test -f "$RUN/$name"; then
    mv "$RUN/$name" "$ARCHIVE/$name" || exit 1
  else
    printf 'restart archive: %s absent\n' "$name" >> "$RUN/findings.md"
  fi
done
```

Retain the same operation lock through archiving and launch. Repeat the liveness check immediately before launch using the archived PID and session identity, so moving those files never bypasses the earlier group check. Launch through the next section, not the relay commands, then record the new process and session identity and release the lock. Establish the new run ID from its coordination record and resume monitoring; never treat the earlier terminal snapshot as the new run's outcome.

## Launch

Read `kickoff.txt` and the resolved toolchain choice. For Claude Code, choose a
UUID and write it to `session-id` before launch. After launch, read the first
stream event with `session_id` and confirm it matches. With the operation lock
held, after the liveness check shows no live manager:

```sh
cd "$WORKSPACE" || exit 1
nohup perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV' -- \
  claude -p "$(cat "$RUN/kickoff.txt")" --session-id "$(cat "$RUN/session-id")" \
  --output-format stream-json --verbose --dangerously-skip-permissions \
  > "$RUN/stream.jsonl" 2> "$RUN/stderr.log" < /dev/null &
printf '%s\n' "$!" > "$RUN/pid"
```

For Codex, use this launch instead. Inspect the first `thread.started` event in
`stream.jsonl` and write its `thread_id` to `session-id`. If it is absent or
unclear, report that to the sponsor; do not invent an ID. The `-o` file holds
the final message, and is overwritten on each turn.

```sh
cd "$WORKSPACE" || exit 1
nohup perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV' -- \
  codex exec --json -C "$WORKSPACE" -o "$RUN/last-message.txt" \
  --dangerously-bypass-approvals-and-sandbox "$(cat "$RUN/kickoff.txt")" \
  > "$RUN/stream.jsonl" 2> "$RUN/stderr.log" < /dev/null &
printf '%s\n' "$!" > "$RUN/pid"
```

Release the acquired operation lock after recording the PID and checking the
first platform identity event. Stream reading is an observation, not an
additional startup parser or automatic retry.

## Sponsor relay at a turn boundary

Wait for process-group exit and acquire the lock. Run the liveness check again:
a live group means **relay not sent**. A missing or conflicting `session-id`
is a sponsor decision. Never start a new session for a relay.

A relay begins with this fixed header:

```text
SPONSOR RELAY (approved <UTC timestamp>; draft <path>)
```

Use `draft none` when there is no draft. Put the sponsor-approved text after
the header, followed by the relay-persistence instruction defined by the
manager's `workflows/contracts/run-state.md`. Before sending, append the exact full
text and its approval source to `.prompts/findings-<run_id>.md`; save the same
text in `$RUN/relay.txt`. This local log does not replace the manager's
published relay history.

For Claude Code, resume only the recorded session. Append the new turn to the
same stream and stderr files:

```sh
cd "$WORKSPACE" || exit 1
nohup perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV' -- \
  claude -p --resume "$(cat "$RUN/session-id")" "$(cat "$RUN/relay.txt")" \
  --output-format stream-json --verbose --dangerously-skip-permissions \
  >> "$RUN/stream.jsonl" 2>> "$RUN/stderr.log" < /dev/null &
printf '%s\n' "$!" > "$RUN/pid"
```

For Codex, copy `last-message.txt` aside only when it exists because `-o` overwrites it. If it is absent, skip the copy-aside and log the skip in findings; a failed turn may never have written the file.
`resume <thread_id>` uses the recorded `session-id`:

```sh
if test -f "$RUN/last-message.txt"; then
  cp "$RUN/last-message.txt" "$RUN/last-message-before-relay.txt" || { exit 1; }
else
  printf '%s\n' 'Codex relay: skip the copy-aside; last-message.txt absent' >> "$RUN/findings.md"
fi
cd "$WORKSPACE" || exit 1
nohup perl -MPOSIX -e 'POSIX::setsid(); exec @ARGV' -- \
  codex exec --json -C "$WORKSPACE" -o "$RUN/last-message.txt" \
  --dangerously-bypass-approvals-and-sandbox resume "$(cat "$RUN/session-id")" \
  "$(cat "$RUN/relay.txt")" \
  >> "$RUN/stream.jsonl" 2>> "$RUN/stderr.log" < /dev/null &
printf '%s\n' "$!" > "$RUN/pid"
```

Read the first new `thread.started.thread_id` from the appended Codex stream
segment and compare it with `session-id`. A mismatch goes to the sponsor; do
not send another relay. For Claude Code, confirm the new `session_id` matches.
Release the operation lock after recording the PID and checking the identity.
At turn end, use `last-message.txt` for Codex's status block. For Claude Code,
read the last `result` before process exit and save its final text to
`last-message.txt`; a `result` can precede exit. Read the complete final output
and locate the status block and any terminal signal according to
`workflows/contracts/status-block.md` terminal-turn ordering; do not require the status
block to end a terminal result.

## Additional-review authorization URL handoff

The supervisor never sends this URL by writing it into the shared checkout or
by using a raw process resume. Those mechanisms authenticate the resumed
manager session, but they do not prove that the supervisor anchored at kickoff
supplied the URL; another process with checkout access could reproduce them.

Deliver the exact URL through authenticated parent-agent messaging when that
channel is available. Otherwise give it to the sponsor and use the complete
Sponsor relay procedure above after the sponsor approves the relay. The relay's
approval source is the attribution evidence. Never treat the posted comment,
the GitHub account that posted it, `$RUN`, or the operation lock as proof of the
supervisor's identity.

## Confirmed interrupt and stop

Confirm the interrupt at its source under `references/interrupt-rules.md`.
Acquire the lock and repeat the liveness and platform identity check before
signaling. Set `PID` to the validated PGID. This attempts to send SIGINT to the
whole group, then checks it for up to ten seconds after successful delivery.
Attempt SIGTERM only if members remain.

```sh
if ! kill -INT "-$PID" 2>/dev/null; then
  if test -n "$(ps -axo pgid=,stat= | awk -v group="$PID" '$1 == group && $2 !~ /^Z/ { print; exit }')"; then
    STOP_DISPOSITION='SIGINT delivery failed; process group remains live, awaiting sponsor'
  else
    STOP_DISPOSITION='process group exited before SIGINT delivery, awaiting sponsor'
  fi
else
  for attempt in 1 2 3 4 5 6 7 8 9 10; do
    test -z "$(ps -axo pgid=,stat= | awk -v group="$PID" '$1 == group && $2 !~ /^Z/ { print; exit }')" && break
    sleep 1
  done
  if test -n "$(ps -axo pgid=,stat= | awk -v group="$PID" '$1 == group && $2 !~ /^Z/ { print; exit }')"; then
    if kill -TERM "-$PID" 2>/dev/null; then
      STOP_DISPOSITION='SIGTERM sent; process-group exit unconfirmed, awaiting sponsor'
    elif test -n "$(ps -axo pgid=,stat= | awk -v group="$PID" '$1 == group && $2 !~ /^Z/ { print; exit }')"; then
      STOP_DISPOSITION='SIGTERM delivery failed; process group remains live, awaiting sponsor'
    else
      STOP_DISPOSITION='process group exited before SIGTERM delivery, awaiting sponsor'
    fi
  else
    STOP_DISPOSITION='stop executed, awaiting sponsor'
  fi
fi
printf 'STOP_DISPOSITION=%s\n' "$STOP_DISPOSITION"
```

Perform the read-only working-tree report immediately after the command: branch,
uncommitted changes, and any `.git/*.lock` files in every in-scope repository.
Use `git status --short --branch` and a read-only search for `.git/*.lock`.
**Do not clean, reset, or remove** a repository lock. Consume the fence's exact
`STOP_DISPOSITION=<message>` output line and publish `<message>` verbatim as the
sponsor-facing stop disposition alongside the working-tree report. The fence
selects the complete message from observed signal delivery and group state; do
not reinterpret it or report a signal as sent separately. A disposition that
says the group remains live or exit is unconfirmed does not describe the
checkout as stopped. Wait for direction before any resume, then release only
the operation lock this operation acquired.
