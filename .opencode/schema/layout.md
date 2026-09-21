# Runtime artifact layout and coordination

The destination repository retains `halucinator/docs/` and `halucinator/pac/` from `AGENTS.md:172-257` and adds:

```text
halucinator/
  state.toml
  scope/scope-<8hex>.toml
  handoff/01-sources.toml ... 08-review-<artifact>.toml
  test-candidates/<name>/
    src/**
    <manifest>.toml
    INVENTORY.md
    evidence/**
  .run/<lock-id>.lock
```

Handoffs are mutable current records at deterministic paths. Their bytes become immutable only when another artifact pins them by FileRef hash: replacement makes the pin stale. Scope decisions remain immutable append-only records. `state.toml` is committed mutable coordination. Add `/halucinator/.run/` to the destination root `.gitignore` in M3.

## Committed test-candidate revisions

`halucinator/test-candidates/<name>/` is ratified here as a committed, reviewable location, not scratch. Its members are exactly:

- `src/**` - the black-box test and example sources of one test revision, ownership class `test-candidate-source`;
- the candidate manifests and `INVENTORY.md`, ownership class `test-candidate-manifests`;
- `evidence/**` - raw captured run output, ownership class `test-candidate-evidence`.

All three classes are owned by `hal-tester` (`.opencode/ownership.toml:241-254`). This tree is **never** placed under `.run` and is **never** ignored: a gitignored tree is neither reviewable by an independent reviewer nor durable across clones, which is exactly the property typed evidence FileRefs depend on. The destination root `.gitignore` therefore adds only `/halucinator/.run/` and carries no pattern that matches any test-candidate path.

The destination `.gitattributes` records the byte policy for this tree as exactly these four lines:

```gitattributes
halucinator/test-candidates/*/src/** text eol=lf
halucinator/test-candidates/*/*.toml text eol=lf
halucinator/test-candidates/*/INVENTORY.md text eol=lf
halucinator/test-candidates/*/evidence/** -text
```

Source, manifests and the inventory are normalized text so that a hash is stable across platforms; captured evidence is binary-safe so that a run capture is preserved byte for byte and its FileRef hash means what it claims.

`hal-integrator` materializes both the ignore entry and the attribute lines when `hal-coordinator` dispatches it. Two limitations remain open and are **not** closed by this ratification. H9 is open: the byte policy above is specified here but is not installed in any destination by this schema, so a clone without those lines has no policy at all. E10 is open: the validator checks the four mandated lines literally as text and never invokes `git check-attr`, so the *effective* Git attributes of a working tree remain unverified (`validate.md:83`).

## Named roots and paths

`PathRef` defaults to repository root when `root` is absent. Allowed forms:

```toml
x = { path = "halucinator/docs/..." }
y = { root = "generation:vendor-pac", path = "data/svd/..." }
```

`repo` must be omitted rather than written. External names match `generation:[a-z][a-z0-9-]{0,31}` and are declared by name and authorization in `[[roots.generation]]` in state. Their absolute host locations are supplied explicitly at validation/operation time (`--root generation:<name>=<absolute-path>`); paths are never guessed or committed. This models existing external generation support (`AGENTS.md:220-246`; `generation-and-checks.md:336-341,386`).

Paths use `/`, are nonempty relative paths. The exact path `.` denotes the selected root itself; otherwise paths contain no `.`, `..`, empty segment, backslash, colon, NUL, drive prefix, UNC/device namespace, percent-encoded separator, or segment ending space/dot. Reject Windows reserved names case-insensitively even with extension: `CON`, `PRN`, `AUX`, `NUL`, `CLOCK$`, `COM1`-`COM9`, `LPT1`-`LPT9`. Resolve component-by-component without following an escaping symlink, junction, mount point, or other reparse point; canonical root comparison is case-insensitive on Windows and must use volume identity plus normalized components, not string prefix. Existing targets must remain within the selected root. Nonexistent targets are allowed only when their nearest existing parent passes the same test.

`target-id` and `vendor-id` retain the distinct normalization rules in `terminology.md` and `AGENTS.md:204-210`.

## Lock identity and format

Canonical stage IDs may contain `:` and never become filenames. Lock ID is `<slug>-<digest8>`: slug is canonical stage ID lowercased with each non-alphanumeric run replaced by `-`, trimmed, max 40 characters; digest8 is the first eight lowercase hex characters of SHA-256 over UTF-8 canonical stage ID. Filename is `<lock-id>.lock`. Validator recomputes it. Example: canonical `write-tests:schema-demo` has a computed lock filename, never literal colon. Fixtures calculate the exact digest.

Every lock requires: `schema=2`, canonical `stage`, `status="in-progress"`, `kind=stage|board-test|pac-integration|state-update`, unpredictable `owner`, `host`, positive `pid`, UTC timestamps `acquired_at`/`heartbeat_at`, and sorted unique `resources` including `stage:<stage>`. Kind-specific fields are forbidden elsewhere:

- `state-update`: resource `global:state`; `state_generation` integer and `state_sha256` digest.
- `board-test`: `board_id`, `authorization` FileRef, `board_state=unknown|safe|active`, `board:<board_id>`, and the schema-2 interlock members below.
- `pac-integration`: `canonical` PathRef, `candidate` PathRef, and `path:<root-qualified-canonical>`.

## The worktree-local, single-operator board interlock

A `board-test` lock is a **worktree-local, single-operator interlock**. It is a strong default and a statement of intent, not a sandbox. It is not a lease, not a broker, and not a cross-clone guarantee: another clone, another worktree or another operator is invisible to it, and a direct probe or programmer command bypasses it entirely. `.opencode/schema/runtime.py` arbitrates cooperating worktree-local callers; direct writers and other clones are outside it. The word "lease" survives only inside the field name `lease_epoch`, for compact identity.

Schema-2 members: `lease_epoch`, 32 lowercase hex generated with `secrets.token_hex(16)`; `check_token`, 64 lowercase hex generated with `secrets.token_hex(32)`; `owner_process_identity` exact `{scheme,value}` with scheme `windows-filetime|linux-startticks|unavailable`; `operation_phase` from `acquired|preparing|active|teardown|recovery-pending|recovery-verified`; `operation_attempt`, a nonnegative integer raised before each target-affecting operation; optional `operation_id`, 32 lowercase hex, required while an operation is in flight; `last_operation` from `none|attach|reset|load-ram|program-flash|run|halt|detach|power-change|fixture-change`; optional `child_session` exact `{kind,identity,started_at,completed_at?}`; `safe_state`, a FileRef to a SafeStateObservation, required exactly when the board is safe or the phase is `recovery-verified` and forbidden while active or unknown; `recovery_attempts`, an append-only ordered FileRef array; and optional `override_record`. The validator checks syntax and equality only. It cannot check that `lease_epoch` was unpredictably generated, and `check_token` is not physical fencing.

Phase and state must agree: `active` implies `board_state="active"`; `recovery-pending` implies `unknown`; `recovery-verified` implies `safe` plus a `safe_state` record.

Acquisition winner semantics are deliberate: create the candidate exclusively, flush it, then rescan. If the rescan finds **any other** valid intersecting board lock, the new claimant always removes only its own candidate and fails, regardless of timestamps or inferred creation order. An existing lock is never touched and never stolen. An ambiguous lock blocks exactly as a live one does. If no prior lock is visible at all - including in a fresh clone - the interlock is created in `recovery-pending` with `board_state="unknown"`, never `acquired`: **absence is not evidence of prior safe teardown.**

**Holder death is not operation death.** Before launching any probe or runner child, the attempt is raised, the operation ID and child process-group, Windows Job or session identity are recorded, the phase is set active, and the record is flushed. Completion is recorded only after the child and its descendants have terminated and the observation channel is quiescent. If the holder or the helper dies, recovery must assume the child may still be transferring or driving pins. Logical state is declared unknown **before reconnecting**, because attaching a debugger is itself a target-affecting operation, and no attach, reset or reconnect is permitted until the operator confirms termination and quiescence, or physically isolates board and probe, in an override or recovery-attempt record.

Recovery transitions are `active|preparing|teardown|ambiguous -> recovery-pending`. Entry needs no produced evidence, which breaks the circularity of requiring evidence that can only be produced from inside recovery. Each action appends a new immutable attempt FileRef; an interrupted recovery appends outcome `interrupted` and stays pending. Only a latest `verified` attempt with a matching SafeStateObservation reaches `recovery-verified`, from which release or a fresh acquisition is permitted. Attempts are never overwritten, reordered or removed.

**Recovery must be completable without bypassing the interlock.** Entry needing no evidence is only half of it: an operator also has to be able to look at the board to find out whether it is safe. If every target operation were refused until recovery was already verified, the circularity would simply have moved, and the only remaining exits would be physically isolating every fixture or going around the helper - which teaches operators to go around it, and is worse than having no interlock at all. There is therefore one narrow, explicitly authorized transition, `begin-recovery-operation`. It is reachable only from `recovery-pending` or from a recovery-scoped operation already in flight. It permits only observation and isolation - `attach`, `reset`, `halt`, `detach`, `power-change`, `fixture-change` - and carries no way to load, program or run code on a board whose state nobody has established. It marks the lock `operation_scope="recovery"`, so ordinary test work and release both keep refusing, and completing it returns the interlock to `recovery-pending` with the board still **unknown**: a recovery operation gathers observations, it never advances toward release. It does not require the board authorization, because that record gates authorized *test* work and making an interrupted board safe is not test work.

The board stays `unknown` for the whole of that window. **Attaching a debugger drives pins**, so it is itself a target-affecting operation and cannot be the step that establishes safety; it is how the operator gathers the observations a SafeStateObservation then records.

An unreadable lock is **not** an absent lock. A `.lock` file that cannot be read, decoded, parsed or structurally validated claims resources of unknown extent, so it blocks acquisition of any board rather than being skipped. Skipping it would make a corrupted live claim indistinguishable from no claim at all, which is two operators on one device - the hazard the mechanism exists to prevent. Structural validation requires `schema`, `stage`, `status`, `kind`, `owner`, `host`, a positive integer `pid`, both timestamps and a string-only `resources` array, plus `board_id` on a `board-test` lock.

Every FileRef the helper records or acts on carries a **mandatory** canonical SHA-256 and is opened, hashed and re-verified before the transition it justifies and again before release. An unpinned reference is a name, not evidence: the bytes behind it can change freely after they were attested. Runtime bookkeeping the helper keeps on the live lock - `operation_scope`, `last_recovery_outcome`, `last_verified_safe_state` - is local to `.run` and is never part of a published handoff.

`before-board-op` narrows the check-use window but cannot close it. A holder can pass the check, pause, lose or override its epoch, and then resume a direct command, so recovery must always assume surviving operations and direct callers must route operation start and completion through the helper. Closing this residual requires the deferred broker.

## Acquire, liveness, release

Acquire validates all locks, rejects intersecting resources, creates exclusively, flushes, and rescans; the race loser removes only its own lock. Owner refreshes heartbeat atomically at least every 30 seconds and immediately around protected operations. Only these observations are admissible: local hostname equality; OS process existence; OS process-birth identity matching `owner_process_identity`; a heartbeat parsed against current UTC; and explicit operator override evidence. On Windows the helper obtains the process creation FILETIME through stdlib `ctypes` calls to `OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION)` and `GetProcessTimes`; on Linux it reads the `/proc/<pid>/stat` start-ticks field without converting it to wall time. Other platforms record `scheme="unavailable"`. A reader classifies:

- live: same host, the PID exists, and its birth identity equals the recorded one; or remote with heartbeat age at most 120 seconds;
- interrupted: same host and the PID is absent, or the PID exists with a **different** birth identity, which is a reused PID and not the same owner;
- ambiguous: same host but identity cannot be inspected, or remote with heartbeat age over 120 seconds.

Same-host PID-plus-birth-identity evidence dominates timestamp anomalies and classifies live. A negative heartbeat age or a heartbeat more than 120 seconds in the future is ambiguous, never live. A timeout never proves death, so a stale remote heartbeat stays ambiguous. Live means do not interfere. Ambiguous - including remote clock skew - means wait one 30-second refresh interval, reread, then fail closed if still ambiguous. Interrupted means run recovery below; time alone never permits deletion. Owner releases only after durable output; a board requires a verified safe teardown, and integration requires a final identity check.

Permanent ambiguity is a deliberate safe denial of service. The recorded escape hatch requires an operator-authored record of board ID, the old lock's raw hash, the observed host, PID and start time, why inspection is inconclusive, confirmation that the prior owner and every child debug or programming session are terminated or that board and probe are physically disconnected and de-energized, the identity and time of the confirmer, and an explicit acknowledgement that board state remains unknown. It archives the old lock, creates a new epoch in `recovery-pending`, and permits recovery only - never tests.

Windows durability is explicit. Lock creation uses create-new semantics, flushes user-space buffers and `fsync`s the file. A replacement keeps source and destination on the same volume through a sibling temporary plus `os.replace`, and retries only documented transient sharing violations with bounded delays of 50, 100, 200 and 400 milliseconds. Exhaustion fails closed and leaves the temporary file and the old lock as recovery evidence. Directory-flush capability is probed once; where required durability cannot be established the helper blocks target-affecting operations rather than claiming persistence. A delete-sharing failure never triggers lock stealing.

## Stage recovery

Do not mutate suspect outputs. Inventory and hash them into a recovery Markdown FileRef, compare against the last valid handoff, and resume only in a new candidate location. Emit partial with empty blockers if unaffected candidate work can proceed, recording interruption in hashed notes/check evidence and incomplete coverage; otherwise emit blocked with an `interrupted:<stage>` blocker. Record comparison, chosen disposition, new candidate, and resource recovery before an authorized actor removes the lock. Never resume canonical replacement in place.

A live lock at session entry is concurrency, not interruption. Only the classification above triggers recovery.

## State mutation serialization

Every state mutation acquires `global:state`. Read state, verify current `generation` and raw-byte SHA-256 equal lock values, apply one logical update, write and fsync a sibling temporary file, re-read/revalidate current state and compare again, then atomically replace and fsync the parent directory where supported. Increment generation by exactly one. A mismatch aborts and retries from a fresh read; never merge from a stale snapshot or truncate in place. This generation/CAS is cooperative lock discipline only, not tamper detection or lost-history detection; an uncooperative writer can still replace valid-looking state.

## Explicit limitation and M6-only exception register

Gitignored locks exist only in one worktree. A fresh clone cannot see a crash marker. Therefore `.run` detects interrupted PAC replacement only within that worktree and **does not close F8**. Durable cross-clone recoverability needs a committed transaction marker outside `.run`, and it is deferred to post-M7 along with the hardware-operation broker and the shared lease authority a cross-clone board exclusion would need.

Schema 2 spends the board-lock identity fields that version 1 reserved: the interlock epoch, check token, owner process identity, operation phase and attempt, child session, safe state and recovery lineage above are now operational, not placeholders. What version 2 still does **not** provide is a durable record outside one worktree. A fresh clone cannot know that a previous run died with the board active, so board exclusion across clones and operators remains open. PAC baseline and candidate manifests and the durable canonical-integration journal remain open for the same reason.