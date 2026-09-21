---
name: write-clocks
description: >-
  Use when hal-coordinator dispatches the first scaffold-hal platform slice for
  clock-tree, power-domain, gate, reset, frequency-calculation, and
  target-specific clock/reset/power lifecycle work; MCXA Gate and
  enable_and_reset are search examples only. Dispatch and search terms: clock
  tree, power domains, clock gates, resets, lifecycle contract, startup clock
  contract,
  platform slice, partial 05-platform handoff. Wrong for publishing a ready
  platform, canonical placement, peripheral-local clock pokes, interrupts,
  linker/runtime integration, DMA, tests, or uncited hardware claims.
compatibility: opencode
---

# Write the clock subsystem platform slice

```halucinator-skill-contract
stage: scaffold-hal
participants: hal-driver,hal-integrator
emitter: hal-integrator
emits: 05-platform|halucinator/handoff/05-platform.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
checks: advertised-builds,build-only-ci,format-lint,foundation-coverage,generated-mappings,independent-review,live-reference-read,negative-chip-selection,pure-host-tests,target-link
consumes: 04-pac|coverage.complete,coverage.incomplete,handoff.blockers,handoff.inputs,handoff.notes,handoff.status,pac.cargo_chip_feature,pac.cited_notes,pac.crate_manifest,pac.foundation.evidence,pac.foundation.id,pac.foundation.kind,pac.foundation.location,pac.foundation.status,pac.metadata_features,pac.package,pac.revision.kind,pac.revision.value,pac.runtime_features,pac.rust_compilation_target,pac.source_ids,pac.temporary_fork,scope.decision,scope.revision
writes: hal-driver|clock-modules
writes: hal-driver|driver-evidence
writes: hal-integrator|integration-candidates
writes: hal-integrator|platform-handoff
supplies-delta: hal-driver|platform-notes
```

This is the **first of three ordered platform slices** that together prepare one
`05-platform` handoff for one exact MCU. The chain is `write-clocks`, then the
interrupt slice, then the runtime and linker slice, then `scaffold-hal` as the
sole final consolidator. This slice establishes the clock subsystem that
[HAL-RULE-04](../../../AGENTS.md) points every peripheral driver at: the clock
tree, power domains, gates, resets, frequency calculation, and the
target-specific ownership/lifecycle contract containing every minimum element
above; it may be shared, split, reference-counted, initialization-only, or
always-on. MCXA's `Gate` and `enable_and_reset` are one example of such a
contract, not required names. A driver that pokes a gating register directly is configuring the same
policy in a second place that can disagree with this one.

## When to use

Use this skill when **hal-coordinator** dispatches the clock platform slice
against a `04-pac` handoff that validates, or when a previous clock-slice run
left the singleton `05-platform` at `partial` or `blocked` and the recorded next
action is now possible.

Do not use it to publish a `ready` platform, to move any canonical byte, to
create composite platform evidence, or to obtain independent review. Those four
acts belong solely to the final consolidator, and this slice performs none of
them. Do not use it for interrupt metadata, runtime or linker integration, DMA,
examples or target tests, or for peripheral-local clock pokes that belong inside
the clock subsystem instead.

## Ownership and boundaries

**hal-driver** implements the clock subsystem. **hal-integrator** is the emitter
because it owns `platform-handoff`, the integration candidate tree and the
platform session. Specialists never dispatch peers; every cross-owner
transition returns to **hal-coordinator**.

| Owner | Materializes here | Never here |
|---|---|---|
| **hal-driver** | classes `clock-modules` and `driver-evidence`: the clock tree, power, gate and reset modules, their host tests and their slice-local logs | shared crate files, manifests, linker scripts, CI, interrupts, the handoff itself, commits |
| **hal-integrator** | classes `integration-candidates` and `platform-handoff`: the candidate integration tree, the slice snapshot, the `partial` `05-platform`; and the platform-session lock | clock logic, review verdicts, scope decisions, any `ready` platform, any canonical placement |
| **hal-coordinator** | the target, bounded scope, the roadmap, and every dispatch | implementation or shared files |
| **hal-reviewer** | nothing in this slice: review belongs to final consolidation | any byte this slice produces |

Cross-owner delta: this slice authors semantic content for `platform-notes`, a
class whose registry owner in [`ownership.toml`](../../ownership.toml) is
**hal-integrator**, not **hal-driver**. **hal-coordinator** dispatches
**hal-integrator** to materialize the `notes/STARTUP.md` startup-clock-contract
delta and to return its FileRef. This slice never writes that path itself.

The PAC is an input. A missing clock, gate or reset accessor returns through
**hal-coordinator** to **hal-svd**; a missing hardware meaning returns to
**hal-datasheet**. Never bridge either gap with raw register access or an
invented constant, and never hand-edit generated output.

## Inputs

Consume the validated `04-pac` leaves declared in the contract. The admission
vocabulary is exactly the producer's field names:

| Admission concern | Consumed field |
|---|---|
| Crate under work | `pac.crate_manifest`, `pac.package` |
| Identity of the generated crate | `pac.revision.kind`, `pac.revision.value`, `pac.temporary_fork` |
| Build contract | `pac.cargo_chip_feature`, `pac.rust_compilation_target`, `pac.metadata_features`, `pac.runtime_features` |
| Foundation coverage | `pac.foundation.id`, `pac.foundation.kind`, `pac.foundation.status`, `pac.foundation.location`, `pac.foundation.evidence` |
| Provenance | `pac.source_ids`, `pac.cited_notes` |
| Lineage | `handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

Read separately from coordinator-owned state: the exact target identity, the
selected documentation root and its `SOURCES.md`, the hashed `ARCHITECTURE.md`
design input, the destination crate, and the platform-session identity the
integrator established.

A `blocked` predecessor permits no consumption. Every clock file this run will
read or write must already be named by a `path:` resource of the held platform
session before its mutable baseline is read.

## Outputs

- The clock subsystem under `halucinator/candidates/driver-clocks/src/clocks/**`
  while the platform remains a candidate: the pure source, divider and frequency
  calculations, the selected target lifecycle API, power/reset sequencing and
  explicit ownership/absence rules.
- Host-side unit tests of those pure calculations, exhaustive over the small
  legal clock domains.
- Slice-local evidence under `halucinator/candidates/driver-clocks/evidence/`
  and pending-check records under
  `halucinator/candidates/integration-<id>/evidence/clocks/`.
- A `platform-notes` delta recording the startup clock contract, materialized by
  **hal-integrator**.
- A `partial` `halucinator/handoff/05-platform.toml`, plus a fresh hashed
  snapshot of its exact bytes at a candidate path for the next slice to pin in
  its `handoff.inputs`.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock whose resources
   intersect this slice — the platform-session lock carrying
   `stage:scaffold-hal`, `global:hal-integration` and one `path:` resource per
   candidate or owned clock file — and classify each as live, interrupted or
   ambiguous. Live means concurrency: do not interfere and do not recover.
   Ambiguous means wait one 30-second refresh interval, reread, and fail closed
   if it is still ambiguous. Interrupted, or ambiguous still unresolved, means
   recovery: do not mutate the suspect output, inventory and hash it into a
   recovery Markdown FileRef, compare it against the last valid handoff, and
   publish `partial` with empty blockers when unaffected fresh candidate work
   remains or `blocked` with an `interrupted:scaffold-hal` blocker when it does
   not. Record the comparison, the disposition and the new candidate location
   before an authorized actor removes the lock. Resume only in a fresh candidate
   root, never in place. An absent `05-platform.toml` is not proof that no prior
   slice ran: `halucinator/.run/` is gitignored and invisible to a fresh clone,
   so a missing handoff and a missing lock together are silence, not evidence.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `04-pac`. Exit 0
   with silent output is necessary; a missing interpreter, Python below 3.11, a
   timeout, a nonzero exit, or not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or an unrelated ambiguous
   lock as a named blocker rather than ignoring it.
3. **Select and acquire the platform session before any mutable read.** Select
   the candidate roots, enumerate the complete write and delete footprint, and
   have **hal-integrator** acquire the Phase-I platform-session lock with
   `stage:scaffold-hal`, `global:hal-integration` and **one `path:` resource for
   every mutable clock and integration file** — each clock module, each candidate
   evidence root and the singleton handoff path — and hold it continuously
   through publication. **hal-driver** joins that already-authorized session and
   verifies that every file it will read or write is named by a `path:` resource
   **before** reading any mutable baseline; it does not acquire a conflicting
   second lock. Ownership-class overlap does not serialize writes; only
   intersecting lock resources do. Without them a concrete lost update follows:
   this slice reads `src/clocks/gate.rs` at V0, a concurrent driver reads V0,
   this slice writes Vc, the driver writes Vu derived from V0, and Vc is silently
   lost. On contention, abandon the stale baseline and restart from a freshly
   read one. The naming rule is in [`layout.md`](../../schema/layout.md) and the
   worked form in [`hal-integrator.md`](../../agents/hal-integrator.md); the
   session is cooperative and procedural, with no fencing token in the typed
schema.
4. **Load the facts, the PAC leaves and the design contract.** Load the exact
   `04-pac` leaves through the admission mapping above, and separately the
   coordinator-owned target, roots, hashed `ARCHITECTURE.md` and hashed
   `SOURCES.md`. Preserve dirty and unrelated worktree edits; never require a
   commit or a stash. On a missing mandatory input, return `blocked`.
5. **Load the live references and record what was read.** Load
   `embassy-mcxa/DEVGUIDE.md` and the clock, gate, reset and power files
   `AGENTS.md` names in the actual checkout, together with the reference-manual
   sections describing the clock tree, and record the sections, files, source
   IDs and hardware citations actually read. Discharge `live-reference-read`
   from that citation set. A remembered pattern from this toolkit is not a live
   reference, and a missing live reference blocks the affected implementation.
6. **Compare the required clock items against PAC foundation coverage.** Compare
   every in-scope clock source, divider, power domain, gate and reset against
   `pac.foundation.*` and the generated accessors, and discharge
   `foundation-coverage` from that comparison. A missing accessor returns
   through **hal-coordinator** to **hal-svd**; it is never worked around.
7. **Author the functional core.** Author the pure value-to-value logic — clock
   source selection, divider search, frequency calculation and register encoding
   — free of registers, `async` and HAL types. Every field with a finite legal
   domain is an enum, never a `u8` or a `u32`; encoding is total and decoding is
   partial and returns a `Result`; out-of-range values are rejected rather than
   masked; no import is a wildcard. Cite the manual section or table, or the PAC
   path, for every hardware constant.
8. **Author the clock shell.** Author the selected lifecycle contract and every
   minimum element, introducing a gate or a lifetime guard only when cited
   semantics require it, keeping the register-touching shell nearly branch-free, and
   place every one of them **only in clock-owned files**. This is the single
   place gating and reset policy lives; no peripheral module may reimplement it.
9. **Run the host tests over the clock calculations.** Run the host-side unit
   tests of the functional core, exhausting the small legal clock domains rather
   than sampling them, covering the invalid boundaries, and exercising the
   production functions rather than a parallel model. Discharge
   `pure-host-tests` from those runs.
10. **Compare the clock, gate and reset mappings against generated metadata.**
    Compare each clock instance, gate and reset the subsystem exposes against the
    generated singleton and metadata mappings, and discharge the slice-local
    `generated-mappings` from that comparison, editing no generated output.
11. **Run the slice-local software checks and record the pending ones.** Run the
    repository-required formatting and lint checks over the clock slice and
    discharge the slice-local `format-lint`. Then record each complete-platform
    check this slice cannot discharge — `advertised-builds`, `build-only-ci`,
    `negative-chip-selection`, `target-link` and `independent-review` — as
    `unrun`, each pinned to a hashed evidence FileRef stating why it is pending
    consolidation and who will discharge it. Never publish one of those as
    `passed` and never as `not-applicable`. `independent-review` in particular is
    obtained only by the final consolidator, whose gate is: Only
    review.verdict=ready accepts; ready-with-fixes and not-ready do not.
12. **Publish the partial slice, snapshot it, and validate it.** Publish
    **only** a `partial` `05-platform` through **hal-integrator**: write the
    durable evidence and notes first, let **hal-coordinator** dispatch
    **hal-integrator** to materialize the `platform-notes` startup-clock-contract
    delta and return its FileRef, preserve a hashed snapshot and recovery record
    of any deterministic handoff `state.toml` currently pins before replacing it,
    write the handoff, and run
    `python .opencode/schema/validate.py <repository-root> --kind all` again.
    Then copy the validated singleton's exact raw bytes to a fresh path such as
    `halucinator/candidates/integration-<id>/snapshots/05-platform-after-clocks.toml`,
    hash it, and verify the snapshot bytes equal the validated live singleton so
    the next slice can pin the snapshot FileRef rather than the live path.
13. **Return the held session to the coordinator.** Return the session identity,
    the snapshot FileRef, the evidence paths, the status and the next action to
    **hal-coordinator**. Do not release the Phase-I lock, do not publish `ready`,
    do not create the consolidated platform evidence, do not request review and
    do not move any canonical byte. State explicitly that no `ready` platform,
    no canonical placement, no commit and no hardware operation was performed.

When a required tool, target, formatter, schema, linker utility, probe, runner or reviewer is unavailable, record the attempted command, discovered identity, failure output, affected check and exact remedy in a new hashed evidence FileRef. Leave the affected check `unrun`; never mark it `not-applicable`. Ask the user to install or expose the named capability, provide an approved existing path/runner, or request a coordinator-owned scope decision; the agent does not install tools. Publish `partial` with `can_progress=true` and empty blockers when unaffected work remains, using truthful coverage: `coverage.incomplete` may remain empty when the `unrun` check alone makes the handoff partial. Publish `blocked` with `can_progress=false` and a named `environment:<capability>` blocker when no scoped work can continue. On resumption, rerun entry-state classification and the `--kind all` gate, verify the supplied identity, create replacement evidence at a fresh path, rerun affected checks and re-attest.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `advertised-builds` | Record that complete-platform advertised builds remain pending consolidation | `halucinator/candidates/integration-<id>/evidence/clocks/advertised-builds-pending.md` |
| `build-only-ci` | Record that complete-platform CI remains pending consolidation | `halucinator/candidates/integration-<id>/evidence/clocks/build-only-ci-pending.md` |
| `format-lint` | Run formatting and lint checks over the clock slice | `halucinator/candidates/driver-clocks/evidence/format-lint.log` |
| `foundation-coverage` | Compare clock, gate, reset and power requirements with PAC coverage | `halucinator/candidates/driver-clocks/evidence/foundation-coverage.log` |
| `generated-mappings` | Compare clock, gate and reset mappings with generated metadata | `halucinator/candidates/driver-clocks/evidence/generated-mappings.log` |
| `independent-review` | Record that independent review belongs only to final scaffold consolidation | `halucinator/candidates/integration-<id>/evidence/clocks/review-pending.md` |
| `live-reference-read` | Record live DEVGUIDE and clock references read | `halucinator/candidates/driver-clocks/evidence/live-references.md` |
| `negative-chip-selection` | Record that complete feature-policy negatives remain pending consolidation | `halucinator/candidates/integration-<id>/evidence/clocks/negative-selection-pending.md` |
| `pure-host-tests` | Run exhaustive host tests over clock calculations | `halucinator/candidates/driver-clocks/evidence/pure-host-tests.log` |
| `target-link` | Record that complete-platform target link remains pending consolidation | `halucinator/candidates/integration-<id>/evidence/clocks/target-link-pending.md` |

Pending checks are emitted as `unrun`, never as `passed` and never as
`not-applicable`.

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. The platform session
is the same kind of discipline: lock resources are unrestricted strings and
fence nothing mechanically, and slice snapshots inherit their semantic
validation from the immediately preceding successful validation plus byte
equality — the validator does not independently discover candidate snapshots.
Typed evidence hashes freshness, not relevance.

## Exit criteria

### ready

Predicate: unreachable for this skill. Even with `coverage.incomplete` empty,
`handoff.blockers` empty and every applicable check `passed`, this non-final
slice must return to the final consolidator rather than publish `ready`;
publishing a platform `ready` is reserved to `scaffold-hal` alone, so this
predicate is never satisfiable here.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and at
least one applicable complete-platform check is `unrun` or `failed`;
`coverage.incomplete` may be empty or nonempty and must remain truthful. This is
the only status this slice publishes on a successful run.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names the affected requirement, the owner, the
next action and the evidence needed, and identifies a missing accessor, hardware
meaning, tool, access, dispatch or decision that only somebody outside this
slice can supply.

## Application example

For the fictional target `unobtainium-circuits-uc-not-a-real-mcu-0001` the
coordinator dispatches the clock slice against a validated `04-pac`.
**hal-integrator** acquires the platform session naming every clock module and
candidate path; **hal-driver** authors the divider search and frequency
calculation as the functional core, exhausts them on the host, and places
the selected target lifecycle implementation only in its owning modules.
The five complete-platform checks are recorded `unrun` against pending records.
The emitted handoff:

```toml
[handoff]
schema = 2
stage = "scaffold-hal"
status = "partial"
can_progress = true
inputs = [
  { path = "halucinator/handoff/04-pac.toml", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" }

[coverage]
complete = ["foundation:init-api"]
incomplete = ["foundation:interrupt-metadata", "peripheral:schema-demo"]

[platform]
crate_manifest = { path = "halucinator/candidates/integration-001/Cargo.toml", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" }
roadmap = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ROADMAP.md", sha256 = "5555555555555555555555555555555555555555555555555555555555555555" }
startup_clock_contract = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" }
supporting_subsystems = ["foundation:init-api"]
foundation_api = ["pub fn init(config: Config) -> Peripherals"]
pac_manifest = { path = "halucinator/pac/unobtainium/unobtainium-pac/Cargo.toml", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }
source_ids = ["doc-001"]
cited_notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md", sha256 = "7777777777777777777777777777777777777777777777777777777777777777" },
]
dependencies = [{ crate = "unobtainium-pac", identity = "fixture-rev-1", features = ["rt"] }]
first_driver = "schema-demo"
first_driver_modes = ["blocking"]

[[checks]]
id = "live-reference-read"
status = "passed"
evidence = { path = "halucinator/candidates/driver-clocks/evidence/live-references.md", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }

[[checks]]
id = "foundation-coverage"
status = "passed"
evidence = { path = "halucinator/candidates/driver-clocks/evidence/foundation-coverage.log", sha256 = "9999999999999999999999999999999999999999999999999999999999999999" }

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/candidates/driver-clocks/evidence/format-lint.log", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

[[checks]]
id = "advertised-builds"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/clocks/advertised-builds-pending.md", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }

[[checks]]
id = "negative-chip-selection"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/clocks/negative-selection-pending.md", sha256 = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" }

[[checks]]
id = "pure-host-tests"
status = "passed"
evidence = { path = "halucinator/candidates/driver-clocks/evidence/pure-host-tests.log", sha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }

[[checks]]
id = "generated-mappings"
status = "passed"
evidence = { path = "halucinator/candidates/driver-clocks/evidence/generated-mappings.log", sha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" }

[[checks]]
id = "target-link"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/clocks/target-link-pending.md", sha256 = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" }

[[checks]]
id = "build-only-ci"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/clocks/build-only-ci-pending.md", sha256 = "1212121212121212121212121212121212121212121212121212121212121212" }

[[checks]]
id = "independent-review"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/clocks/review-pending.md", sha256 = "1313131313131313131313131313131313131313131313131313131313131313" }
```

A fact nobody established is an absent key or an empty collection, never a
sentinel word. The paths and hashes above are fictional schema-shape material,
not evidence.

## Quick reference

| Element | Value |
|---|---|
| Stage | `scaffold-hal`, first of three ordered platform slices |
| Emitter | `hal-integrator`, because it owns `platform-handoff` |
| Implementer | `hal-driver`, which owns `clock-modules` and `driver-evidence` |
| Emitted handoff | `halucinator/handoff/05-platform.toml`, kind `05-platform`, **`partial` only** |
| Consumes | `04-pac` only; later slices consume `05-platform` snapshots instead |
| Checks | `advertised-builds`, `build-only-ci`, `format-lint`, `foundation-coverage`, `generated-mappings`, `independent-review`, `live-reference-read`, `negative-chip-selection`, `pure-host-tests`, `target-link` |
| Discharged here | `format-lint`, `foundation-coverage`, `generated-mappings`, `live-reference-read`, `pure-host-tests` |
| Left `unrun` | `advertised-builds`, `build-only-ci`, `independent-review`, `negative-chip-selection`, `target-link`, each with a pending-record FileRef |
| Delta | `platform-notes` authored here, materialized by `hal-integrator` via `hal-coordinator` |
| Lock | one platform session with `stage:scaffold-hal`, `global:hal-integration` and one `path:` resource per mutable file, acquired before any mutable read and held through publication |
| Snapshot | validated singleton bytes copied and hashed to `halucinator/candidates/integration-<id>/snapshots/05-platform-after-clocks.toml` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | belongs to final consolidation: Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Ready | unreachable here; only the final consolidator publishes a platform `ready` |
| Reserved to the consolidator | composite evidence, independent review, canonical placement, `ready`, state update |
| Deferred | fencing tokens and durable multi-agent leases; the session is cooperative in the typed schema |

## Common mistakes

- **Publishing `ready` because every discharged check passed.** Five checks are
  `unrun` by construction here. A `ready` from a non-final slice erases the
  chain's whole point, which is that one `05-platform` singleton is written by
  several slices in turn.
- **Marking a complete-platform check `not-applicable`.** `target-link` and
  `build-only-ci` are entirely applicable; they are simply not this slice's to
  run. `not-applicable` makes the final handoff look discharged when nothing was
  proven, which is exactly the defect that rejected the original design.
- **Reading a mutable clock baseline before the session names its path.** Class
  overlap does not serialize writes. Only intersecting `path:` resources do, and
  without them a concurrent driver's write derived from the same V0 baseline
  silently discards this slice's.
- **Treating contention as something to work through.** A changed baseline means
  the read is stale. Restart from a freshly read baseline instead of merging.
- **Overwriting the live singleton without snapshotting it first.** The next
  slice pins the snapshot FileRef, not the live path; replacing the singleton
  with no snapshot leaves the successor pinning bytes that no longer exist.
- **Creating composite platform evidence here.** Composite evidence over all ten
  checks is the consolidator's job and uses every slice-local log as input.
  Producing it early guarantees it is stale before the platform is complete.
- **Requesting independent review from this slice.** Review is taken over the
  frozen complete candidate with no platform lock held, once.
- **Duplicating clock or reset policy in a peripheral module later.** This slice
  exists so that policy lives in exactly one place, reached through the selected
  lifecycle contract; copying MCXA names without matching hardware is also a
  defect.
- **Writing `notes/STARTUP.md` directly.** `platform-notes` is owned by
  **hal-integrator**; this slice authors the content and routes materialization
  through **hal-coordinator**.
- **Quoting an offset or a divider limit from memory.** No invented hardware
  facts: cite the manual section or table, or the PAC path, or stop and ask.
- **Claiming the platform session or the validator wiring is enforcement.** Both
  are honor systems, and saying otherwise makes every reader trust an
  attestation nobody made.
