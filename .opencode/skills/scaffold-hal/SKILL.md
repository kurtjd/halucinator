---
name: scaffold-hal
description: >-
  Use when hal-coordinator dispatches the crate-level platform foundation for
  one exact MCU against a ready `04-pac` handoff, or when a previous
  `05-platform` stopped at partial or blocked. Dispatch and search terms:
  scaffold the HAL crate, Cargo chip feature, Rust compilation target, crate
  manifest, build.rs code generation and generated mappings, `peripherals!` and
  `interrupt_mod!` plumbing, `init` and startup policy, clocks and reset gating
  assigned to hal-driver, `memory.x` and linker and runtime wiring materialized
  by hal-integrator, ARCHITECTURE.md startup/clock/API contracts assigned to
  hal-architect, roadmap and dispatch owned by hal-coordinator, 05-platform
  handoff. Wrong for implementing the first peripheral driver, preparing SVDs
  or generating the PAC, authoring or running examples and hardware-in-the-loop
  tests, or claiming silicon results.
compatibility: opencode
---

# Scaffold HAL

```halucinator-skill-contract
stage: scaffold-hal
participants: hal-architect,hal-coordinator,hal-driver,hal-integrator,hal-tester
emitter: hal-integrator
emits: 05-platform|halucinator/handoff/05-platform.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
checks: advertised-builds,build-only-ci,format-lint,foundation-coverage,generated-mappings,independent-review,live-reference-read,negative-chip-selection,pure-host-tests,target-link
consumes: 04-pac|handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,pac.crate_manifest,pac.package,pac.revision.kind,pac.revision.value,pac.cargo_chip_feature,pac.runtime_features,pac.metadata_features,pac.rust_compilation_target,pac.source_ids,pac.cited_notes,pac.temporary_fork,pac.foundation.id,pac.foundation.kind,pac.foundation.location,pac.foundation.status,pac.foundation.evidence
consumes: 05-platform|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
writes: hal-architect|architecture-spec
writes: hal-coordinator|roadmap
writes: hal-driver|clock-modules
writes: hal-integrator|build-generation
writes: hal-integrator|chip-modules
writes: hal-integrator|ci
writes: hal-integrator|crate-manifest
writes: hal-integrator|example-binaries
writes: hal-integrator|example-manifest
writes: hal-integrator|example-support
writes: hal-integrator|integration-candidates
writes: hal-integrator|linker
writes: hal-integrator|platform-handoff
writes: hal-integrator|platform-lib
writes: hal-integrator|platform-notes
writes: hal-integrator|runtime-wiring
supplies-delta: hal-architect|platform-notes
supplies-delta: hal-driver|platform-notes
supplies-delta: hal-tester|example-binaries
supplies-delta: hal-tester|example-manifest
supplies-delta: hal-tester|example-support
```

This stage produces a driver-ready, reviewed, software-verified platform
foundation for one exact MCU inside a frozen integration candidate. It does not
produce a complete HAL, implement the first planned peripheral, or establish
anything about silicon.

## When to use

Use this skill when **hal-coordinator** dispatches `scaffold-hal` against a
`04-pac` handoff that validates and is `ready`, or when a previous run left
`05-platform` at `partial` or `blocked` and the recorded next action is now
possible.

Start from one exact MCU and core, one Cargo chip feature, one Rust compilation
target, one documented startup clock path, and one first planned peripheral with
its exact modes. All of those are **hal-coordinator** decisions carried in state,
not decisions taken here.

Read [the scaffold record reference](./references/scaffold-record.md) before any
file is authored. Scoping pressure to "finish the UART end to end" does not move
the first peripheral into this stage: record its modes, scaffold only the
foundations it needs, and leave the driver to the next dispatch.

## Ownership and boundaries

This stage is three jobs — decision, design, implementation — that were once one
procedure. They are now cut along the agent boundaries the registry already
records, and **every cross-owner transition returns to hal-coordinator**.
Specialists never dispatch peers.

| Owner | Materializes here | Never here |
|---|---|---|
| **hal-coordinator** | class `roadmap`, the exact path `halucinator/docs/<target-id>/notes/ROADMAP.md`; the target, bounded scope, Cargo chip feature, Rust compilation target, destination crate, first peripheral and its modes, foundation requirements; and every dispatch | implementation or shared files |
| **hal-architect** | class `architecture-spec`, exactly `halucinator/docs/*/notes/ARCHITECTURE.md`, carrying the startup, clock and public API **contracts** | any code, any manifest, any decision, any dispatch |
| **hal-driver** | class `clock-modules`, `embassy-*/src/clocks/**`, and the host-side unit tests of its functional core — authored in the `write-clocks` slice, not re-authored at consolidation | shared files, manifests, CI, commits |
| **hal-integrator** | every shared file: `integration-candidates`, `crate-manifest`, `build-generation`, `platform-lib`, `chip-modules`, `linker`, `runtime-wiring`, `example-binaries`, `example-manifest`, `example-support`, `ci`, `platform-notes` and `platform-handoff`; and it is the **sole committer** | test logic, design contracts, scope decisions |
| **hal-tester** | nothing canonical; it authors the source-blind link-check binary, its manifest and its support files as deltas | canonical example, test or CI files |
| **hal-reviewer** | the `08-review` verdict only | any file this stage produces |

The clock subsystem is **hal-driver**'s. It is implemented against the contract
**hal-architect** specified in `ARCHITECTURE.md`; the architect does not
implement it, and no driver hand-rolls gating or reset outside `clocks`.

This stage is the **sole final consolidator** of the platform chain.
**hal-coordinator** dispatches `write-clocks`, then `integrate-interrupts`, then
`integrate-runtime-linker`, each of which publishes only a `partial`
`05-platform` inside the one continuously held Phase-I platform session and
moves no canonical byte. This skill **admits the final slice snapshot as a typed
input, verifies the ordered chain behind it**, creates the composite evidence,
obtains the independent review with no platform lock held, performs canonical
placement, and publishes the single `ready` `05-platform`. No slice may do any
of those five things, and this stage re-authors none of their work: it
consolidates what they produced and blocks on what they did not.

`SCAFFOLD.md` and `STARTUP.md` are class `platform-notes`, owned and materialized
by **hal-integrator**. **hal-architect** and **hal-driver** author semantic
deltas into them; **hal-coordinator** dispatches the integrator to materialize
each delta and returns its FileRef. The tester's example binary, example manifest
and example support files are deltas of integrator-owned classes on the same
route.

Nothing is edited in place. Shared work happens in one disposable integration
candidate under `halucinator/candidates/integration-*/`, driver work under
`halucinator/candidates/driver-*/` while an upstream handoff is still `partial`,
and tester work under `halucinator/test-candidates/<name>/`. **hal-integrator**
holds a `kind="stage"` lock whose resources contain `stage:scaffold-hal`, the
exact string `global:hal-integration`, and one `path:` entry per touched file,
across baseline verification, shared edits, final checks, staging and the commit.

`global:hal-integration` is a cooperative convention. Lock resources are
unrestricted sorted strings, so nothing mechanically fences a process that
ignores it. A durable integration journal, owner fencing and a cross-clone crash
marker are **deferred**; today this stage has discipline and hashes, and no
document here may claim otherwise.

Do not change SVD or PAC schemas, hand-edit generated output, copy an MCXA
hardware assumption, publish, flash a board, or run target code. A missing
hardware meaning returns through **hal-coordinator** to **hal-datasheet**; a
missing register or metadata item returns to **hal-svd**.

## Inputs

Consume the validated, `ready` `04-pac` leaves declared in the contract. The
admission vocabulary is exactly the producer's field names:

| Admission concern | Consumed field |
|---|---|
| Crate under test | `pac.crate_manifest`, `pac.package`, `pac.revision.kind`, `pac.revision.value` |
| Build contract | `pac.cargo_chip_feature`, `pac.runtime_features`, `pac.metadata_features`, `pac.rust_compilation_target` |
| Foundation partition | `pac.foundation.id`, `pac.foundation.kind`, `pac.foundation.location`, `pac.foundation.status`, `pac.foundation.evidence` |
| Provenance | `pac.source_ids`, `pac.cited_notes` |
| Fork state | `pac.temporary_fork` |
| Lineage | `handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

Also consume the validated `05-platform` leaves declared in the contract's
second `consumes:` line. That input is **not** the live singleton: it is the
immutable snapshot the last slice published inside the integration candidate,
`halucinator/candidates/integration-<id>/snapshots/05-platform-after-runtime.toml`,
pinned by hash in `handoff.inputs`. Snapshot semantics are inherited from the
slices: each slice validated the live singleton immediately before copying it
byte-identically, and later validation hashes the snapshot for freshness.
`validate.py` does not discover candidate snapshots as handoffs and does not
reparse them as a kind, so the snapshot's admissibility rests on the byte
equality each slice verified — a procedural guarantee, stated as one.

The slice chain is `write-clocks`, then `integrate-interrupts`, then
`integrate-runtime-linker`. Each is `partial`, and each pins its own predecessor
snapshot in `handoff.inputs`, so the ordered chain is recoverable from the final
snapshot by following those pins. Nothing mechanical enforces the order or the
chain: no `05-platform` leaf carries a slice discriminator, the typed schema is
frozen, and repeatable `05` snapshot filenames are not validator-visible. The
chain walk below is therefore discipline plus hashes, and no reader may treat it
as enforcement.

Read separately from coordinator-owned state: `decisions.cargo_chip_feature`,
`decisions.rust_compilation_target`, `decisions.destination_crate`,
`decisions.foundation_requirements`, the next-driver selection and its modes, the
`target.*` identity, `scope.current_revision`, `scope.current_decision`, and the
`roots.documentation`, `roots.pac_crate` and destination-crate paths. Read the
hashed `ARCHITECTURE.md` as the design input.

A `blocked` predecessor permits no consumption. A `partial` one permits
read-only inspection and disposable candidate work only: no canonical placement
and no downstream `ready`. A `pac.temporary_fork` of `true` permits candidate
work and prevents `ready`. One missing foundation register, accessor, interrupt
or metadata item blocks **all** scaffold implementation, including the manifest,
the build wiring, the crate root and the chip module; intake, records,
inspection and analysis may continue. Never bridge either gap with raw register
access or an invented constant.

## Outputs

- `ARCHITECTURE.md` from **hal-architect**, carrying the startup, clock and
  public API contracts.
- `halucinator/docs/<target-id>/notes/ROADMAP.md` from **hal-coordinator**,
  linked and never duplicated.
- Clock modules and their host-side unit tests from **hal-driver**, produced by
  the `write-clocks` slice and admitted here, not re-authored here.
- One disposable integration candidate under
  `halucinator/candidates/integration-*/`, carrying the three ordered slice
  snapshots under `snapshots/`, and, only after an accepting review, the
  canonical shared files, examples and CI wiring from **hal-integrator**.
- `SCAFFOLD.md` and `STARTUP.md`, materialized by **hal-integrator** from
  architect and driver deltas.
- `halucinator/handoff/05-platform.toml`, carrying `platform.crate_manifest`,
  `platform.pac_manifest`, `platform.roadmap`, `platform.startup_clock_contract`,
  `platform.foundation_api`, the ordered `platform.supporting_subsystems`,
  `platform.first_driver` and its nonempty `platform.first_driver_modes`,
  `platform.dependencies`, `platform.source_ids`, `platform.cited_notes`, the
  ten canonical checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering this stage
   and the `global:hal-integration`, candidate and note resources, and classify
   each as live, interrupted or ambiguous. Live means concurrency: do not
   interfere. Ambiguous means wait one 30-second refresh interval, reread, and
   fail closed if it is still ambiguous. Interrupted, or ambiguous still
   unresolved, means recovery: do not mutate the suspect output, inventory and
   hash it into a recovery Markdown FileRef under `notes/recovery/`, compare it
   against the last valid handoff, and publish `partial` with empty blockers when
   unaffected fresh candidate work remains or `blocked` with an
   `interrupted:scaffold-hal` blocker when it does not. Record the comparison,
   the disposition and the new candidate location before an authorized actor
   removes the lock. Resume only in a fresh integration candidate, never in
   place.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `04-pac`. Exit 0
   with silent output is necessary; a missing interpreter, a timeout, a nonzero
   exit, or not running it is not a pass and blocks consumption. Report an
   unrelated stale artifact or ambiguous lock as a named blocker.
3. **Load the predecessor and the coordinator-owned decisions.** Load the exact
   `04-pac` leaves through the admission mapping above, and separately load the
   coordinator-owned target, bounded scope, Cargo chip feature, Rust compilation
   target, destination crate, first peripheral and modes, and foundation
   requirements. Preserve dirty and unrelated worktree edits; never require a
   commit or a stash.
4. **Record the coordinator-owned scope and roadmap.** Record the bounded scope,
   the included supporting subsystems and the deferred work, and let
   **hal-coordinator** maintain the single authoritative roadmap at
   `halucinator/docs/<target-id>/notes/ROADMAP.md`. Link it; never copy the
   pipeline into `SCAFFOLD.md`.
5. **Author the architecture specification against live references.**
   **hal-architect** authors `ARCHITECTURE.md` with the startup, clock and public
   API contracts, citing the live `embassy-mcxa/DEVGUIDE.md` sections and the
   concern-specific files named by `AGENTS.md` in the actual checkout, plus the
   source IDs and hardware citations for every hardware-specific decision.
   Discharge `live-reference-read` from that citation set; a remembered pattern
   from this toolkit is not a live reference.
6. **Compare the foundation requirements against PAC coverage.** Compare each
   coordinator-owned foundation requirement with the `[[pac.foundation]]`
   partition and the generated crate, and discharge `foundation-coverage` before
   any implementation begins. Unrelated peripheral omissions do not block;
   one missing in-scope item blocks all implementation and returns to
   **hal-svd**.
7. **Select the integration candidate and acquire the lock.** Select an unused
   `halucinator/candidates/integration-*/` root, check the complete write and
   delete footprint, and let **hal-integrator** acquire the `kind="stage"` lock
   carrying `stage:scaffold-hal`, `global:hal-integration` and one `path:` entry
   per touched file. Candidate, canonical and recovery locations must not
   overlap.
8. **Load the final slice snapshot and walk the slice chain.** Admit
   `halucinator/candidates/integration-<id>/snapshots/05-platform-after-runtime.toml`,
   hash it, and pin that FileRef in `handoff.inputs`. Then walk its
   `handoff.inputs` back through the `integrate-interrupts` and `write-clocks`
   snapshots, verifying that all three exist, hash as pinned, name the same
   integration candidate, and carry the same `scope.revision` and
   `scope.decision` as this run. Verify that the clock modules the chain
   attributes to **hal-driver** are present in the candidate and that their
   host-test evidence is the evidence the clock slice pinned; discharge
   `pure-host-tests` from those runs, or record it `not-applicable` with a
   reason the reviewer audits. **Author no clock code here.** `clock-modules` is
   **hal-driver**'s and was implemented by the `write-clocks` slice against the
   architect's contract; re-authoring it in this stage puts the same policy in
   two places and makes the slice's review meaningless. A missing snapshot, a
   hash mismatch, an out-of-order chain, a snapshot describing a different
   candidate or scope, or a chain that does not account for all three slices is
   a named blocker returned to **hal-coordinator**, never a gap this stage fills
   by re-implementing the slice.
9. **Compare the candidate's shared platform files against the admitted chain.**
   Confirm that the candidate the slices built actually carries the crate
   manifest and Embassy docs metadata, the build and code-generation
   integration, the crate root with `peripherals!` and `interrupt_mod!`
   plumbing, the chip module, the `init` and configuration policy, and
   `memory.x` with the linker and runtime wiring — each attributable to the
   slice that produced it, each still inside the candidate and not at a
   canonical path. **hal-integrator** repairs only what this verification shows
   to be inconsistent with the admitted contract, and any substantive gap
   returns to **hal-coordinator** for the owning slice rather than being
   re-authored here. Compare the generated singleton, interrupt and build
   mappings against the PAC metadata across the whole candidate and discharge
   `generated-mappings` without editing generated output.
10. **Run the formatting, lint and build matrix.** Run the repository-required
    formatting and lint checks for every touched surface and discharge
    `format-lint`; build the candidate for the advertised MCU and every in-scope
    feature combination and discharge `advertised-builds`; run the missing and
    incompatible chip-selection cases against the live feature policy and
    discharge `negative-chip-selection`, without an indiscriminate
    `--all-features` and without a fabricated future chip feature. A missing tool
    leaves a check `unrun`; it does not make it inapplicable.
11. **Request the source-blind target link.** Request through
    **hal-coordinator** that **hal-tester** author a minimal binary that calls
    the real public initialization and links for the cited memory and runtime
    facts, supplying only the public signatures and contracts, the chip feature
    and compilation target, the cited memory/runtime and board facts, and the
    claimed feature combinations. Send no bodies, no implementation files and no
    LSP response exposing one. The tester authors that binary and nothing else:
    it runs no build, because compiler, macro and build-script diagnostics quote
    implementation source and would defeat its blinding. **hal-coordinator** then
    dispatches **hal-integrator** to compile and link the authored binary inside
    the candidate and to return sanitized results carrying no HAL-source excerpt.
    Discharge `target-link` from that actual linked artifact; `cargo check` is
    not a link. The dispatch is **build-only**: no device operation is performed.
12. **Build the build-only CI path.** Build the repository's build-only CI entry
    for the new surfaces in the candidate and discharge `build-only-ci`, with no
    hardware runner invoked and no separately authorized hardware gate enabled.
13. **Publish the preliminary handoff, validate it, and obtain the review.**
    Author the `SCAFFOLD.md` and `STARTUP.md` deltas, let **hal-coordinator**
    dispatch **hal-integrator** to materialize them and return their FileRefs,
    preserve a hashed snapshot and recovery record of any deterministic handoff
    `state.toml` currently pins before replacing it, publish the preliminary
    `05-platform`, run
    `python .opencode/schema/validate.py <repository-root> --kind all` again,
    then create fresh **composite evidence** at new paths for every one of the
    ten canonical checks, taking each slice-local log as an input FileRef,
    listing all of them, and attesting the complete candidate rather than any
    one slice. Release the Phase-I platform session lock, then request through
    **hal-coordinator** the independent **hal-reviewer** review over
    `platform.crate_manifest` and the frozen candidate — peer review happens
    with **no platform lock held** — and discharge `independent-review` from the
    accepting verdict. Only review.verdict=ready accepts; ready-with-fixes and
    not-ready do not.
14. **Re-attest, place canonically, publish the final handoff, and run the final
    gate.** Re-attest where referenced bytes changed — preserve the superseded
    evidence and review records, create replacement evidence at a new path
    rather than overwriting one, rerun only the affected checks, and obtain a
    new review where the reviewed bytes changed — then let **hal-integrator**
    reacquire the platform lock, revalidate every candidate, composite-evidence
    and review hash against what the review accepted, and perform **canonical
    placement**: copy the reviewed bytes verbatim to their canonical paths and
    commit. Any contention or changed baseline aborts this phase and restarts
    from fresh validation and review. Publish the final
    `halucinator/handoff/05-platform.toml` — the only `ready` `05-platform` this
    stage produces — run `python .opencode/schema/validate.py <repository-root> --kind all` over it,
    let **hal-coordinator** update `state.toml`
    through the compare-and-swap sequence, run the final `--kind all` gate, and
    return the record paths, status and next action. State that no peripheral
    driver, publication or hardware operation was performed.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `advertised-builds` | Build the candidate for the advertised MCU and every in-scope feature combination | `halucinator/candidates/integration-<id>/evidence/advertised-builds.log` |
| `build-only-ci` | Build the repository's build-only CI entry for the new surfaces | `halucinator/candidates/integration-<id>/evidence/build-only-ci.log` |
| `format-lint` | Run the repository-required formatting and lint checks for every touched surface | `halucinator/candidates/integration-<id>/evidence/format-lint.log` |
| `foundation-coverage` | Compare each coordinator-owned foundation requirement with the `[[pac.foundation]]` partition and the generated crate | `halucinator/candidates/integration-<id>/evidence/foundation-coverage.log` |
| `generated-mappings` | Compare the generated singleton, interrupt and build mappings against the PAC metadata | `halucinator/candidates/integration-<id>/evidence/generated-mappings.log` |
| `independent-review` | Request the coordinator-dispatched review over `platform.crate_manifest` and record its accepting verdict | `halucinator/handoff/08-review-platform.toml` |
| `live-reference-read` | Record the live DEVGUIDE sections, MCXA files, source IDs and hardware citations actually read | `halucinator/docs/<target-id>/notes/ARCHITECTURE.md` citation section, captured as a FileRef |
| `negative-chip-selection` | Run the missing and incompatible chip-selection cases against the live feature policy | `halucinator/candidates/integration-<id>/evidence/negative-chip-selection.log`, or `reason (no evidence FileRef)` when the live policy documents no negative combination |
| `pure-host-tests` | Run the host tests over the pure clock, configuration and encoding logic | `halucinator/candidates/integration-<id>/evidence/pure-host-tests.log`, or `reason (no evidence FileRef)` when no such logic was authored |
| `target-link` | Build the source-blind smoke binary to an actual linked image using the cited memory and runtime facts | `halucinator/candidates/integration-<id>/evidence/target-link.log` |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. Locks, the
compare-and-swap sequence and the review gate are the same kind of discipline:
`global:hal-integration` fences nothing mechanically. Typed evidence hashes
freshness, not relevance — a reviewer still judges whether an artifact discharges
the check it is attached to.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
the consumed `04-pac` is `ready` against the current `scope.revision` and
`scope.decision` with `pac.temporary_fork` false, every applicable check is
`passed`, `platform.dependencies` identities and features are current, the
reviewed bytes are the frozen candidate that was placed canonically, and the
independent review accepted. Only review.verdict=ready accepts; ready-with-fixes
and not-ready do not. Ready here means frozen-candidate **software** readiness
for the first driver dispatch; it establishes nothing about silicon, a complete
peripheral driver, or upstream acceptance.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Only disposable candidate work continues; a candidate that has not
passed every gate and an accepting review never reaches a canonical path, and
partial output is not a narrower completed scope.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names a missing foundation item, hardware
meaning, tool, access, dispatch or decision that only somebody outside this
stage can supply.

## Application example

For exact MCU `unobtainium-circuits-uc-not-a-real-mcu-0001`, `SOURCES.md` and the cited notes cover reset, the
internal-oscillator startup path, the SRAM layout, UART0 pins and its DMA
request, while the generated PAC covers those foundation registers but lacks ADC
metadata. The coordinator selects UART0 in blocking and DMA modes as the first
driver. Scaffold only `unobtainium-circuits-uc-not-a-real-mcu-0001`, the documented internal-oscillator path, the
central gate, reset and frequency plumbing, pin mux and DMA support; the ADC gap
does not block. The three ordered slices have already run in integration
candidate `001`, so this stage admits their final snapshot
`snapshots/05-platform-after-runtime.toml` alongside `04-pac` and verifies the
chain behind it. The emitted handoff:

```toml
[handoff]
schema = 2
stage = "scaffold-hal"
status = "ready"
inputs = [
  { path = "halucinator/handoff/04-pac.toml", sha256 = "4c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" },
  { path = "halucinator/candidates/integration-001/snapshots/05-platform-after-runtime.toml", sha256 = "5d2f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f709" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md", sha256 = "6d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" },
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ARCHITECTURE.md", sha256 = "7e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "8f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e" }

[coverage]
complete = ["foundation:init-api", "foundation:clock-gate", "subsystem:pin-mux", "subsystem:dma"]
incomplete = []

[platform]
crate_manifest = { path = "embassy-unobtainium/Cargo.toml", sha256 = "91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80" }
pac_manifest = { path = "halucinator/pac/unobtainium/unobtainium-pac/Cargo.toml", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" }
roadmap = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ROADMAP.md", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }
startup_clock_contract = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }
foundation_api = [
  "pub fn init(config: Config) -> Peripherals",
  "target lifecycle contract: owners; acquire/init; reset arbitration; lifetime accounting/absence; teardown/quiescence; frequency; cancellation",
]
supporting_subsystems = ["subsystem:pin-mux", "subsystem:dma"]
first_driver = "uart"
first_driver_modes = ["blocking", "dma"]
source_ids = ["doc-001", "doc-002"]
cited_notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" },
]

[[platform.dependencies]]
crate = "unobtainium-pac"
identity = "0.1.0"
features = ["uc-not-a-real-mcu-0001", "rt"]

[[checks]]
id = "live-reference-read"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ARCHITECTURE.md", sha256 = "7e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d" }

[[checks]]
id = "foundation-coverage"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/foundation-coverage.log", sha256 = "d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4" }

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/format-lint.log", sha256 = "e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5" }

[[checks]]
id = "advertised-builds"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/advertised-builds.log", sha256 = "f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6" }

[[checks]]
id = "negative-chip-selection"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/negative-chip-selection.log", sha256 = "08192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7" }

[[checks]]
id = "pure-host-tests"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/pure-host-tests.log", sha256 = "192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }

[[checks]]
id = "generated-mappings"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/generated-mappings.log", sha256 = "2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f70819" }

[[checks]]
id = "target-link"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/target-link.log", sha256 = "3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a" }

[[checks]]
id = "build-only-ci"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/build-only-ci.log", sha256 = "4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b" }

[[checks]]
id = "independent-review"
status = "passed"
evidence = { path = "halucinator/handoff/08-review-platform.toml", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" }
```

A fact nobody established is an absent key or an empty collection, never a
sentinel word.

## Quick reference

| Element | Value |
|---|---|
| Stage | `scaffold-hal` |
| Emitter | `hal-integrator`, the sole committer |
| Emitted handoff | `halucinator/handoff/05-platform.toml`, kind `05-platform` |
| Consumes | `04-pac`, plus the final slice `05-platform` as an immutable candidate snapshot; decisions and roots come from coordinator-owned state |
| Slice chain | `write-clocks`, `integrate-interrupts`, `integrate-runtime-linker`; admitted here as `snapshots/05-platform-after-runtime.toml` and walked back by pinned inputs, procedurally and unenforced |
| Checks | `advertised-builds`, `build-only-ci`, `format-lint`, `foundation-coverage`, `generated-mappings`, `independent-review`, `live-reference-read`, `negative-chip-selection`, `pure-host-tests`, `target-link` |
| Decisions and roadmap | `hal-coordinator`; roadmap is exactly `halucinator/docs/<target-id>/notes/ROADMAP.md` |
| Design contracts | `hal-architect`, only `halucinator/docs/*/notes/ARCHITECTURE.md` |
| Clocks | `hal-driver`, `embassy-*/src/clocks/**`, plus host-side unit tests; produced by the `write-clocks` slice and admitted here |
| Shared files | `hal-integrator`, in `halucinator/candidates/integration-*/` first |
| Candidate roots | `halucinator/candidates/integration-*/`, `halucinator/candidates/driver-*/`, `halucinator/test-candidates/<name>/` |
| Lock | `kind="stage"` with `stage:scaffold-hal` and `global:hal-integration`, cooperative only |
| Routing | every question, delta, review request, scope change and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, fork false, applicable checks `passed`, accepting review over the frozen candidate |
| Deferred | durable integration journal, owner fencing, cross-clone crash markers |

## Common mistakes

- **Routing target, scope or the roadmap to `hal-architect`.** Those are
  `hal-coordinator` decisions. The architect writes `ARCHITECTURE.md` and
  nothing else.
- **Re-authoring a slice's work instead of consolidating it.** Clocks,
  interrupt plumbing and the runtime and linker wiring were produced by the
  three slices and reviewed as their output. Writing them again here creates a
  second copy of the same policy, discards the slice's review, and reintroduces
  exactly the multi-writer hazard the slicing removed. Verify, and block on what
  is missing.
- **Publishing `ready` without admitting the final slice snapshot.** The
  snapshot and the chain behind it are the only typed evidence that the three
  slices ran, ran in order, and describe this candidate. Without them the
  consolidation asserts a lineage nobody recorded.
- **Assigning clocks to the architect.** `clock-modules` is `hal-driver`'s, and
  a clock implementation written by the designer of its own contract is reviewed
  by nobody.
- **Editing a canonical shared file in place.** It destroys the frozen-candidate
  order and makes recovery from an interrupted integration guesswork.
- **Having a specialist dispatch a peer.** Every cross-owner transition returns
  to `hal-coordinator`; a direct dispatch leaves the coordinator's state wrong.
- **Declaring `writes` for a class another agent owns.** `SCAFFOLD.md` is
  `platform-notes` and belongs to `hal-integrator`; the architect and driver
  supply deltas.
- **Advertising a chip family because the layout anticipates one.** Support
  starts with the one implemented feature.
- **Treating PAC presence as foundation coverage.** Verify the partition; one
  missing in-scope item blocks every implementation file.
- **Adding a no-op `init` or clock stub to reach a green build.** A successful
  stub is the most expensive kind of false evidence in this stage.
- **Giving `hal-tester` implementation source, or running hardware, for the
  build-only link check.** The link check compiles and links; it operates no
  device.
- **Quoting only the rejecting verdict.** Stating what does not accept, without
  stating what does, turns the review gate into advice. Use the exact sentence.
- **Calling a missing tool an inapplicable check.** It is `unrun`, which blocks
  readiness.
- **Treating `cargo check` as a target link, or a checkbox as an exit
  predicate.** The exit predicates are the three above; a checklist is an
  operator aid.
- **Describing `global:hal-integration` or the validator wiring as
  enforcement.** Both are honor systems, and saying otherwise makes every reader
  trust an attestation nobody made.
