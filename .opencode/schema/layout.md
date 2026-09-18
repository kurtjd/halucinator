# Runtime artifact layout and coordination

The destination repository retains `halucinator/docs/` and `halucinator/pac/` from `AGENTS.md:172-257` and adds:

```text
halucinator/
  state.toml
  scope/scope-<8hex>.toml
  handoff/01-sources.toml ... 08-review-<artifact>.toml
  .run/<lock-id>.lock
```

Handoffs are mutable current records at deterministic paths. Their bytes become immutable only when another artifact pins them by FileRef hash: replacement makes the pin stale. Scope decisions remain immutable append-only records. `state.toml` is committed mutable coordination. Add `/halucinator/.run/` to the destination root `.gitignore` in M3.

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

Every lock requires: `schema=1`, canonical `stage`, `status="in-progress"`, `kind=stage|board-test|pac-integration|state-update`, unpredictable `owner`, `host`, positive `pid`, UTC timestamps `acquired_at`/`heartbeat_at`, and sorted unique `resources` including `stage:<stage>`. Kind-specific fields are forbidden elsewhere:

- `state-update`: resource `global:state`; `state_generation` integer and `state_sha256` digest.
- `board-test`: `board_id`, `authorization` FileRef, `board_state=unknown|safe|active`, and `board:<board_id>`.
- `pac-integration`: `canonical` PathRef, `candidate` PathRef, and `path:<root-qualified-canonical>`.

## Acquire, liveness, release

Acquire validates all locks, rejects intersecting resources, creates exclusively, flushes, and rescans; race loser removes only its own lock. Owner refreshes heartbeat atomically at least every 30 seconds and immediately around protected operations. A reader classifies:

- live: heartbeat age <=120 seconds and, on same host, PID exists;
- interrupted: same-host PID absent, or heartbeat age >120 seconds and owner cannot be positively confirmed;
- ambiguous: heartbeat >120 seconds but remote/permission prevents liveness proof.

Same-host positive PID evidence dominates timestamp anomalies and classifies live. A negative heartbeat age or heartbeat more than 120 seconds in the future is ambiguous, never live. Live means do not interfere. Ambiguous—including remote clock skew—means wait one 30-second refresh interval, reread, then fail closed if still ambiguous. Interrupted means run recovery below; time alone never permits deletion. Owner releases only after durable output; board requires safe teardown, integration requires final identity check.

## Stage recovery

Do not mutate suspect outputs. Inventory and hash them into a recovery Markdown FileRef, compare against the last valid handoff, and resume only in a new candidate location. Emit partial with empty blockers if unaffected candidate work can proceed, recording interruption in hashed notes/check evidence and incomplete coverage; otherwise emit blocked with an `interrupted:<stage>` blocker. Record comparison, chosen disposition, new candidate, and resource recovery before an authorized actor removes the lock. Never resume canonical replacement in place.

A live lock at session entry is concurrency, not interruption. Only the classification above triggers recovery.

## State mutation serialization

Every state mutation acquires `global:state`. Read state, verify current `generation` and raw-byte SHA-256 equal lock values, apply one logical update, write and fsync a sibling temporary file, re-read/revalidate current state and compare again, then atomically replace and fsync the parent directory where supported. Increment generation by exactly one. A mismatch aborts and retries from a fresh read; never merge from a stale snapshot or truncate in place. This generation/CAS is cooperative lock discipline only, not tamper detection or lost-history detection; an uncooperative writer can still replace valid-looking state.

## Explicit limitation and M6-only exception register

Gitignored locks exist only in one worktree. A fresh clone cannot see a crash marker. Therefore `.run` detects interrupted PAC replacement only within that worktree and **does not close F8**. Durable cross-clone recoverability needs a committed transaction marker, deferred to M6.

Version 1 reserves identities only. Fields with no M1 operational reader are limited to: board lock `board_id`, `authorization`, `board_state` (future M6 hardware lease/recovery component); PAC lock `canonical`, `candidate` (future M6 canonical-integration recovery component). They are deliberate M6 exceptions required by F3/F8. M6 must use schema version transition to add owner fencing token, operation phase/last operation, board recovery detail, PAC baseline and candidate manifests, and a durable record outside `.run`; v1 fields alone are insufficient for recovery or transactionality. State-update fields are consumed by the M3 state writer/validator and are not exceptions.