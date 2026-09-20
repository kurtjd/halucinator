---
name: integrate-interrupts
description: >-
  Use when hal-coordinator dispatches the second scaffold-hal platform slice
  after a clock-slice snapshot exists, for NVIC mappings, interrupt ownership,
  priorities, generated declarations and interrupt_mod! integration. Dispatch
  and search terms: NVIC, vectors, interrupt metadata, priorities, generated
  declarations, interrupt_mod!, platform snapshot, partial 05-platform handoff.
  Wrong for publishing a ready platform, canonical placement, inventing
  interrupt numbers, peripheral ISR behavior, clocks, linker/runtime, DMA,
  tests, or PAC metadata edits.
compatibility: opencode
---

# Integrate interrupts

```halucinator-skill-contract
stage: scaffold-hal
participants: hal-integrator
emitter: hal-integrator
emits: 05-platform|halucinator/handoff/05-platform.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
checks: advertised-builds,build-only-ci,format-lint,foundation-coverage,generated-mappings,independent-review,live-reference-read,negative-chip-selection,pure-host-tests,target-link
consumes: 05-platform|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
writes: hal-integrator|build-generation
writes: hal-integrator|chip-modules
writes: hal-integrator|integration-candidates
writes: hal-integrator|platform-handoff
writes: hal-integrator|platform-lib
```

This is the **second of three ordered platform slices** and it may never publish
a `ready` platform. It carries interrupt integration forward inside the
integration candidate and hands a `partial` platform view to the next slice.

## When to use

Use this skill when **hal-coordinator** dispatches the interrupt slice of
`scaffold-hal` for one exact MCU, inside an already-authorized and continuously
held platform session, after the clock slice has published its `partial`
platform view and its snapshot exists. Use it again when a previous interrupt
slice stopped at `partial` or `blocked` and the recorded next action is now
possible.

The slice chain is fixed: the clock slice, then this interrupt slice, then the
runtime and linker slice, then `scaffold-hal` as the sole final consolidator.
Only that consolidator creates composite evidence, obtains the independent
review, performs canonical placement and publishes the single `ready`
`05-platform`.

The subject matter is NVIC mappings, interrupt ownership, priority policy,
generated interrupt declarations and `interrupt_mod!` integration. Peripheral
interrupt service logic, clock policy, runtime and linker wiring, DMA, examples
and hardware tests all keep their own owners.

## Ownership and boundaries

The owning agent is **hal-integrator**, which is also the emitter. It
materializes five classes it owns, per
[`ownership.toml`](../../ownership.toml): `integration-candidates`, the
candidate tree and its evidence and snapshots; `build-generation`, the build
script and the generated interrupt declarations it produces;
`chip-modules`, the per-chip modules that name the vectors a part carries;
`platform-lib`, the crate-level `interrupt_mod!` integration; and
`platform-handoff`, the deterministic `halucinator/handoff/05-platform.toml`.

No canonical byte moves during this slice. Every authored file lands in the
integration candidate. This skill does not perform canonical placement, does not
request the independent platform review, and does not publish `ready` — those
belong to the final consolidator alone.

Never invent an interrupt number or a vector position. Every mapping comes from
an accepted cited hardware fact or from exported PAC metadata, per HAL-RULE-01
and HAL-RULE-02. Never hand-edit generated code: `_generated.rs` and the PAC
crate are outputs, and a missing or wrong interrupt entry is fixed in the
generator or in the PAC metadata and regenerated, per HAL-RULE-06. A PAC
metadata defect returns through **hal-coordinator** to the PAC owner; a missing
hardware meaning returns through **hal-coordinator** to the documentation owner.
Do not claim runtime interrupt delivery this slice has not observed, per
HAL-RULE-11.

This slice joins the already-held platform session identity rather than
acquiring a second lock, and verifies that every interrupt file it will read or
write is named by a `path:` resource of that session before reading its mutable
baseline. Session continuity is procedural and unenforced in schema 1; no
fencing token is claimed.

## Inputs

Consume the current live `05-platform` — not `04-pac` — through the immutable
snapshot this slice preserves from it. The consumed leaves are exactly the
contract's `consumes` list; the load-bearing ones for interrupt work are:

| Admission concern | Consumed field |
|---|---|
| Candidate crate under integration | `platform.crate_manifest` |
| PAC the declarations must agree with | `platform.pac_manifest`, `platform.dependencies.crate`, `platform.dependencies.identity`, `platform.dependencies.features` |
| Foundation surface already established | `platform.foundation_api`, `platform.supporting_subsystems` |
| Startup and clock contract the vectors sit above | `platform.startup_clock_contract` |
| Planned first driver and its modes | `platform.first_driver`, `platform.first_driver_modes` |
| Cited hardware provenance | `platform.source_ids`, `platform.cited_notes` |
| Plan of record | `platform.roadmap` |
| Evidence so far | `checks.id`, `checks.status`, `checks.evidence`, `checks.reason` |
| Lineage | `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `handoff.can_progress`, `handoff.schema`, `handoff.stage`, `handoff.status`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

Read separately from coordinator-owned state: the target identity, the selected
documentation root, the accepted interrupt facts and their source IDs, the PAC
project and generated-metadata roots, the integration candidate root and the
coordinator-approved interrupt priority policy.

A `blocked` predecessor permits no consumption. Missing or stale admission
evidence is a blocker returned to **hal-coordinator**, never a reason to infer a
vector number from emitted Rust.

## Outputs

- Generated interrupt declarations and the build-script inputs that produce
  them, inside the integration candidate.
- Per-chip interrupt modules and the crate-level `interrupt_mod!` integration,
  inside the integration candidate.
- Slice-local evidence under
  `halucinator/candidates/integration-<id>/evidence/interrupts/`, including a
  recorded pending rationale for every complete-platform check this slice cannot
  discharge.
- A fresh immutable predecessor snapshot and a fresh successor snapshot under
  `halucinator/candidates/integration-<id>/snapshots/`.
- `halucinator/handoff/05-platform.toml` republished with `status = "partial"`,
  pinning the predecessor snapshot in `handoff.inputs`.

## Procedure

1. **Inspect and classify entry state.** Inspect the continuously held platform
   session lock, the `stage:scaffold-hal` and `global:hal-integration`
   resources, and every `path:` resource covering an interrupt file this slice
   may read or write, and classify each as live, interrupted or ambiguous. Live
   means concurrency: do not interfere and do not recover. Ambiguous means wait
   one 30-second refresh interval, reread, and fail closed if it is still
   ambiguous. Interrupted, or ambiguous still unresolved after that reread,
   means recovery: do not mutate the suspect output, inventory and hash it into
   a recovery Markdown FileRef, compare it against the last valid handoff, and
   publish `partial` with empty blockers when unaffected fresh-candidate work
   remains or `blocked` with an `interrupted:scaffold-hal` blocker when it does
   not. Record the comparison, the chosen disposition, the new candidate
   location and the resource recovery before an authorized actor removes the
   lock. Resume only in a fresh candidate location, never in place.
2. **Validate before consumption.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading the live
   `05-platform`. Exit 0 with silent output is necessary; a missing interpreter,
   a timeout, a nonzero exit, or simply not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or an unrelated ambiguous
   lock surfaced by the all-kinds gate as a named blocker.
3. **Preserve the predecessor snapshot.** Copy the exact raw bytes of the
   just-validated live `05-platform` to a fresh unused snapshot path such as
   `halucinator/candidates/integration-<id>/snapshots/05-platform-after-clocks.toml`,
   compare the snapshot bytes against the validated live singleton for byte
   equality, hash the snapshot, and pin **that snapshot FileRef — never the live
   singleton path — in `handoff.inputs`**. This is what keeps the input FileRef
   fresh once this slice replaces the singleton. Never overwrite an existing
   snapshot path.
4. **Load interrupt inputs.** Load the exact snapshot leaves through the
   admission mapping above, together with the exported PAC interrupt metadata,
   the accepted cited interrupt facts and their source IDs, and the
   coordinator-approved priority policy. Record the citation — manual section or
   table number, or the PAC metadata path — for every interrupt number, vector
   position and priority constraint. An uncited number stops the slice.
5. **Load live references.** Load the applicable live conventions for generated
   interrupt declarations, `interrupt_mod!` and per-chip interrupt modules in
   the destination repository, record what was read with its identity, and
   discharge `live-reference-read` from that record.
6. **Compare foundation coverage.** Compare every interrupt item and vector the
   included scope requires against what the PAC metadata and the accepted facts
   actually supply, over an explicitly enumerated nonempty item set, and
   discharge the slice-local `foundation-coverage` from that comparison. A
   metadata entry with no interrupt number is not a covered vector.
7. **Author declarations and ownership.** Author the generated interrupt
   declarations, the `interrupt_mod!` integration, the priority assignment and
   the interrupt ownership wiring **only inside the integration candidate**,
   through the build script and the metadata that produce them rather than by
   editing generated output.
8. **Compare generated mappings.** Compare the cited facts, the PAC interrupt
   metadata, the generated declarations, the per-chip modules and the
   `interrupt_mod!` surface against each other, and discharge
   `generated-mappings` from that four-way comparison. A successful compile is
   not a mapping comparison.
9. **Run slice-local software checks.** Run the repository-required formatting
   and lint checks over every interrupt surface this slice touched and discharge
   `format-lint`. Record `pure-host-tests` as `not-applicable` with a reason
   when, as in the ordinary case, this slice authors no pure value-to-value
   logic; if it did author such logic, run those host tests instead. Record
   `advertised-builds`, `target-link`, `build-only-ci`,
   `negative-chip-selection` and `independent-review` as `unrun`, each with a
   fresh hashed evidence FileRef stating that the check is a complete-platform
   obligation pending final consolidation. Never mark a complete-platform check
   `passed` from slice-local evidence, and never downgrade one to
   `not-applicable` to clear it.
10. **Publish the partial slice and validate it.** Write the durable evidence
    and notes first, then publish `halucinator/handoff/05-platform.toml` with
    `status = "partial"`, and run
    `python .opencode/schema/validate.py <repository-root> --kind all` again
    after that write. Preserve a fresh successor snapshot of the published
    bytes for the next slice. Re-attest where referenced bytes changed on a
    resumption: preserve the superseded evidence, create replacement evidence at
    a new path rather than overwriting one, and rerun only the affected checks.
    **hal-coordinator** updates `state.toml` through the compare-and-swap
    sequence only after the handoff validates.
11. **Return the held session.** Return the snapshot paths, the session
    identity, the published `partial` status and the next action to
    **hal-coordinator**, still holding the platform session for the next slice.
    State explicitly that no canonical placement, no consolidated attestation
    across all ten canonical checks, no independent platform review and no
    `ready` publication was performed, and that the platform review gate
    remains the final consolidator's. Only
    review.verdict=ready accepts; ready-with-fixes and not-ready do not.

When a required tool, target, formatter, schema, linker utility, probe, runner
or reviewer is unavailable, record the attempted command, discovered identity,
failure output, affected check and exact remedy in a new hashed evidence
FileRef. Leave the affected check `unrun`; never mark it `not-applicable`. Ask
the user to install or expose the named capability, provide an approved existing
path or runner, or request a coordinator-owned scope decision; the agent does
not install tools. Publish `partial` with `can_progress=true` and empty blockers
when unaffected work remains, using truthful coverage: `coverage.incomplete` may
remain empty when the `unrun` check alone makes the handoff partial. Publish
`blocked` with `can_progress=false` and a named `environment:<capability>`
blocker when no scoped work can continue. On resumption, rerun entry-state
classification and the `--kind all` gate, verify the supplied identity, create
replacement evidence at a fresh path, rerun affected checks and re-attest.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `advertised-builds` | Record that complete-platform builds remain pending consolidation | `halucinator/candidates/integration-<id>/evidence/interrupts/advertised-builds-pending.md` |
| `build-only-ci` | Record that complete-platform CI remains pending consolidation | `halucinator/candidates/integration-<id>/evidence/interrupts/build-only-ci-pending.md` |
| `format-lint` | Run formatting and lint checks over interrupt integration | `halucinator/candidates/integration-<id>/evidence/interrupts/format-lint.log` |
| `foundation-coverage` | Compare required vectors and metadata with PAC coverage | `halucinator/candidates/integration-<id>/evidence/interrupts/foundation-coverage.log` |
| `generated-mappings` | Compare facts, PAC metadata, generated declarations and `interrupt_mod!` | `halucinator/candidates/integration-<id>/evidence/interrupts/generated-mappings.log` |
| `independent-review` | Record that review belongs only to final consolidation | `halucinator/candidates/integration-<id>/evidence/interrupts/review-pending.md` |
| `live-reference-read` | Record live interrupt conventions read | `halucinator/candidates/integration-<id>/evidence/interrupts/live-references.md` |
| `negative-chip-selection` | Record that complete feature negatives remain pending consolidation | `halucinator/candidates/integration-<id>/evidence/interrupts/negative-selection-pending.md` |
| `pure-host-tests` | Record why no new pure logic was authored | `reason (no evidence FileRef)` |
| `target-link` | Record that complete-platform linking remains pending consolidation | `halucinator/candidates/integration-<id>/evidence/interrupts/target-link-pending.md` |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. It is procedural
evidence discipline, not runtime enforcement.

Two further limits are disclosed rather than papered over. The snapshot's
semantic validity is **inherited**, not independently rediscovered: the live
singleton is validated immediately before byte-identical snapshotting, and later
validation hashes the snapshot FileRef for freshness but does not discover a
candidate snapshot as a handoff. And the shared platform session is an
honor-system coordination mechanism with no fencing token in schema 1. Typed
evidence hashes freshness, not relevance: a reviewer still has to judge whether
an artifact discharges the check it is attached to.

## Exit criteria

### ready

Predicate: unreachable for this skill. Even if incomplete coverage were empty,
blockers empty and all applicable checks passed, this non-final slice must
return to `scaffold-hal`; it must not publish `ready`.

### partial

Predicate: `handoff.can_progress=true`, blockers are empty, and at least one
applicable complete-platform check is `unrun` or `failed`; incomplete coverage
may truthfully be empty or nonempty.

### blocked

Predicate: `handoff.can_progress=false`, blockers are nonempty, and either
incomplete coverage is nonempty or an applicable check is `unrun` or `failed`.

## Application example

The emitted handoff for the interrupt slice of a fictional part, pinning the
clock-slice snapshot as its input:

```toml
[handoff]
schema = 1
stage = "scaffold-hal"
status = "partial"
can_progress = true
inputs = [
  { path = "halucinator/candidates/integration-001/snapshots/05-platform-after-clocks.toml", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" }

[coverage]
complete = ["foundation:init-api", "foundation:interrupt-metadata"]
incomplete = ["peripheral:schema-demo"]

[platform]
crate_manifest = { path = "halucinator/candidates/integration-001/Cargo.toml", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" }
roadmap = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ROADMAP.md", sha256 = "5555555555555555555555555555555555555555555555555555555555555555" }
startup_clock_contract = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }
supporting_subsystems = ["foundation:init-api", "foundation:interrupt-metadata"]
foundation_api = ["pub fn init(config: Config) -> Peripherals"]
pac_manifest = { path = "halucinator/pac/unobtainium/unobtainium-pac/Cargo.toml", sha256 = "7777777777777777777777777777777777777777777777777777777777777777" }
source_ids = ["doc-001"]
cited_notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" },
]
dependencies = [{ crate = "unobtainium-pac", identity = "fixture-rev-1", features = ["rt"] }]
first_driver = "schema-demo"
first_driver_modes = ["blocking"]

[[checks]]
id = "live-reference-read"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/live-references.md", sha256 = "9999999999999999999999999999999999999999999999999999999999999999" }

[[checks]]
id = "foundation-coverage"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/foundation-coverage.log", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/format-lint.log", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }

[[checks]]
id = "advertised-builds"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/advertised-builds-pending.md", sha256 = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" }

[[checks]]
id = "negative-chip-selection"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/negative-selection-pending.md", sha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }

[[checks]]
id = "pure-host-tests"
status = "not-applicable"
reason = "This interrupt integration slice introduces no pure value-to-value logic."

[[checks]]
id = "generated-mappings"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/generated-mappings.log", sha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" }

[[checks]]
id = "target-link"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/target-link-pending.md", sha256 = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" }

[[checks]]
id = "build-only-ci"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/build-only-ci-pending.md", sha256 = "1212121212121212121212121212121212121212121212121212121212121212" }

[[checks]]
id = "independent-review"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/interrupts/review-pending.md", sha256 = "1313131313131313131313131313131313131313131313131313131313131313" }
```

The paths and hashes are fictional schema-shape material, not evidence. The
part name is deliberately not a real MCU, and the example states no interrupt
number at all.

## Quick reference

| Element | Value |
|---|---|
| Stage | `scaffold-hal`, second of three ordered platform slices |
| Emitter | `hal-integrator` |
| Emitted handoff | `halucinator/handoff/05-platform.toml`, kind `05-platform`, always `partial` |
| Consumes | `05-platform` — the live singleton, through an immutable candidate snapshot |
| Input FileRef | the fresh snapshot path, never the live singleton path |
| Checks | `advertised-builds`, `build-only-ci`, `format-lint`, `foundation-coverage`, `generated-mappings`, `independent-review`, `live-reference-read`, `negative-chip-selection`, `pure-host-tests`, `target-link` |
| Discharged here | `live-reference-read`, `foundation-coverage`, `generated-mappings`, `format-lint`; `pure-host-tests` not-applicable with a reason |
| Left `unrun` | `advertised-builds`, `target-link`, `build-only-ci`, `negative-chip-selection`, `independent-review`, each with a pending-rationale FileRef |
| Reserved to the consolidator | composite evidence, independent review, canonical placement, `ready` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Routing | every question, review request, scope change and dispatch returns to `hal-coordinator` |
| Schema reference | [`05-platform.md`](../../schema/05-platform.md), [`handoff-common.md`](../../schema/handoff-common.md) |

## Common mistakes

- **Pinning the live singleton path in `handoff.inputs`.** The next singleton
  write changes those bytes, and the recorded hash goes stale the moment this
  slice publishes. Pin the immutable snapshot copied and byte-compared in step
  three.
- **Publishing `ready` because every slice-local check passed.** Four slices
  each writing one singleton with one entry per check ID is exactly how a
  complete-looking platform handoff ends up proving only the last slice. Only
  the final consolidator publishes platform `ready`.
- **Marking a complete-platform check `not-applicable` to clear it.** A check
  this slice cannot discharge is `unrun` with an evidence FileRef recording why
  it is pending consolidation. `not-applicable` is legitimate for
  `pure-host-tests` alone, and only when no pure value-to-value logic was
  authored.
- **Reading `04-pac` as the predecessor.** This slice consumes `05-platform`.
  The PAC reaches it through `platform.pac_manifest` and the dependency
  identity already recorded there.
- **Inventing an interrupt number or a vector position.** A plausible number
  compiles and then silently routes the wrong handler. Every number comes from a
  cited manual section or table, or from exported PAC metadata.
- **Hand-editing `_generated.rs` to add a missing vector.** The next
  regeneration erases the edit and the mapping comparison was never valid. Fix
  the generator or the PAC metadata.
- **Acquiring a second lock.** The platform session is already held and
  heartbeated across all three slices. Join it and verify the `path:` resources
  cover every interrupt file, rather than opening a conflicting session.
- **Overwriting a snapshot or an evidence path on resumption.** It converts a
  traceable supersession into an untraceable one. Create replacement evidence at
  a new path and preserve the superseded record.
- **Claiming interrupts fire.** This slice performed no target run. Naming what
  was not run is the only honest form of that statement.
