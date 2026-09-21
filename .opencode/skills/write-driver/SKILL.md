---
name: write-driver
description: >-
  Use when hal-coordinator dispatches one named peripheral or hardware-semantic
  subsystem against a ready `05-platform` handoff, or when a previous
  `06-driver-<name>` stopped at partial or blocked. Dispatch and search terms:
  write a peripheral driver, GPIO pin ownership and mux and embedded-hal-async
  Wait, Embassy time driver and tick rate and counter rollover, I2C and SPI and
  UART bus drivers, `Instance` and `Info` and `Mode` and type erasure, clock
  gating and reset through the clocks subsystem, interrupt-driven async, waker
  ordering, cancel safety, host tests of the functional core, 06-driver handoff.
  Wrong for shared crate files, manifests, linker scripts or CI, PAC and SVD
  work, authoring or running examples and hardware-in-the-loop tests, committing,
  or claiming silicon results.
compatibility: opencode
---

# Write a peripheral driver

```halucinator-skill-contract
stage: write-driver
participants: hal-driver
emitter: hal-driver
emits: 06-driver|halucinator/handoff/06-driver-<name>.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,driver.build_contract.cargo_chip_feature,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.build_contract.rust_compilation_target,driver.capabilities,driver.dependencies.crate,driver.dependencies.features,driver.dependencies.identity,driver.facts_handoff,driver.name,driver.owned_files,driver.public_api,driver.public_test_record,driver.requirement_ids,driver.scope_kind,driver.test_hardware_facts,driver.trait_obligations.dependency_crate,driver.trait_obligations.obligations,driver.trait_obligations.trait,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision
checks: format-lint-build,generated-mappings,independent-review,live-reference-read,pure-host-tests,target-link-ci,trait-conformance
consumes: 05-platform|coverage.complete,coverage.incomplete,handoff.blockers,handoff.inputs,handoff.notes,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
writes: hal-driver|clock-modules
writes: hal-driver|driver-candidates
writes: hal-driver|driver-evidence
writes: hal-driver|driver-handoff
writes: hal-driver|peripheral-modules
supplies-delta: hal-driver|driver-records
supplies-delta: hal-driver|platform-notes
supplies-delta: hal-driver|roadmap
supplies-delta: hal-driver|sources-catalog
```

This stage produces **one** implemented peripheral or hardware-semantic
subsystem for one exact MCU, with its functional core tested on the host where
one exists, its upstream trait obligations worked as a checklist, and a
tester-safe public API projection. It is one skill for every peripheral: the
peripheral-specific obligations live in profiles, not in separate skills.

## When to use

Use this skill when **hal-coordinator** dispatches `write-driver` for a named
subsystem against a `05-platform` handoff that validates and is `ready`, or when
a previous run left `06-driver-<name>` at `partial` or `blocked` and the recorded
next action is now possible.

Load the universal [driver checklist](./references/driver-checklist.md) and the
[driver record reference](./references/driver-record.md) before any file is
authored, then exactly one profile:

| Positive classification | Profile |
|---|---|
| A digital pin subsystem: pin ownership, mux, level, pull, drive, pin interrupts | [`profiles/gpio.md`](./references/profiles/gpio.md) |
| The single global Embassy time service: monotonic timestamps, tick rate, queued alarms | [`profiles/time-driver.md`](./references/profiles/time-driver.md) |
| A transaction or stream bus: I2C, SPI, UART, or another peripheral with the same shape | [`profiles/bus.md`](./references/profiles/bus.md) |
| None of the above, established by a recorded positive finding | the universal checklist alone |

The fourth row is legal **only after** a positive finding that no specialized
profile applies. A guess is not a finding: an unclassified or uncertain
peripheral yields `partial` or `blocked`. Fail closed.

`profiles/bus.md` is the attractor. The bus shape — `Instance`, `Info`, `Mode`,
one constructor per mode, one `WaitCell` per instance — is the most detailed
pattern in the corpus and the one an agent reaches for under context pressure.
Selecting it for GPIO or for the time service is the single most likely failure
of this stage, and both of those profiles say so normatively.

## Ownership and boundaries

**hal-driver** implements; it owns no shared file, no target test and no commit.
Every cross-owner transition returns to **hal-coordinator**. Specialists never
dispatch peers.

| Owner | Materializes here | Never here |
|---|---|---|
| **hal-driver** | classes `peripheral-modules`, `clock-modules`, `driver-candidates`, `driver-evidence`, `driver-handoff`; the implementation, its host tests, its check evidence and the `06` handoff | shared files, manifests, linker scripts, CI, examples, target tests, commits |
| **hal-coordinator** | class `roadmap`, exactly `halucinator/docs/<target-id>/notes/ROADMAP.md`; the target, bounded scope, selected subsystem and its modes; and every dispatch | implementation or shared files |
| **hal-integrator** | classes `driver-records`, `platform-notes`, `sources-catalog`, and every shared crate file; and it is the **sole committer** | driver logic, test logic, scope decisions |
| **hal-tester** | the source-blind link-check and validation binaries under `halucinator/test-candidates/<name>/` | reading this skill, this driver's source, or any canonical path |
| **hal-reviewer** | the `08-review` verdict only | any file this stage produces |

Cross-owner deltas: this stage authors semantic content for
`driver-records`, `platform-notes`, `sources-catalog` and `roadmap`, and
**hal-coordinator** dispatches the registry owner — **hal-integrator** for the
first three, **hal-coordinator** itself for the roadmap — to materialize each
delta and return its FileRef.

`driver-records` is owned by **hal-integrator** and registers three patterns:
`notes/GPIO.md`, `notes/TIME-DRIVER.md`, and `notes/drivers/**`. A GPIO task
supplies the first, a time-driver task the second, and **every other driver —
bus or unprofiled — supplies a generic durable record at
`halucinator/docs/<target-id>/notes/drivers/<name>.md`**. In all three cases
**hal-driver** authors the semantic delta only; **hal-coordinator** dispatches
**hal-integrator** to materialize the file and return its FileRef, and
**hal-driver** never writes that path itself. The typed `06`, its hashed
`handoff.notes`, its check evidence and its citations remain the primary
machine-readable record; the durable note is the human-readable companion, not
a substitute for either.

Do not hand-roll clock gating or reset in a peripheral module; that policy lives
in `clocks`, which is also yours, and is extended there. Do not edit the PAC or
generated output. A missing register, accessor or metadata item returns through
**hal-coordinator** to **hal-svd**; a missing hardware meaning returns to
**hal-datasheet**. Do not flash a board or run target code.

## Inputs

Consume the validated `05-platform` leaves declared in the contract. The
admission vocabulary is exactly the producer's field names:

| Admission concern | Consumed field |
|---|---|
| Crate under work | `platform.crate_manifest`, `platform.pac_manifest` |
| Startup and API contract | `platform.startup_clock_contract`, `platform.foundation_api` |
| Available subsystems | `platform.supporting_subsystems` |
| Selected subsystem | `platform.first_driver`, `platform.first_driver_modes` |
| Dependency contracts | `platform.dependencies.crate`, `platform.dependencies.identity`, `platform.dependencies.features` |
| Provenance | `platform.source_ids`, `platform.cited_notes`, `platform.roadmap` |
| Lineage | `handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

Read separately from coordinator-owned state: the `target.*` identity, the
dispatched subsystem name, its scope kind and modes, the requirement IDs, the
Cargo chip feature, the Rust compilation target, the destination crate and the
documentation roots. Read the hashed `ARCHITECTURE.md` as the design input and
the hashed `SOURCES.md` for source IDs and cited notes.

A `blocked` predecessor permits no consumption. A `partial` one permits
read-only inspection and disposable candidate work under
`halucinator/candidates/driver-*/` only: no canonical placement and no
downstream `ready`. One missing in-scope register, accessor, interrupt or
metadata item blocks the affected implementation; unrelated peripheral gaps do
not. Never bridge either gap with raw register access or an invented constant.

## Outputs

- The peripheral module tree, and any clock extension it needs, at canonical
  paths when the predecessor is `ready`, or under
  `halucinator/candidates/driver-*/src/**` while it is `partial`.
- Host-side unit tests of the functional core, exhaustive over small legal
  domains.
- A hashed classification record naming the selected profile and the positive
  finding that selected it, carried in `handoff.notes`.
- Record deltas: `notes/GPIO.md` for a GPIO task, `notes/TIME-DRIVER.md` for the
  time driver, otherwise `notes/drivers/<name>.md`, plus the ROADMAP, SOURCES and
  platform-note deltas the work implies, each materialized by its registry owner.
- `halucinator/handoff/06-driver-<name>.toml`, carrying `driver.name`,
  `driver.scope_kind`, `driver.owned_files`, `driver.capabilities`, the complete
  tester-safe `driver.public_api`, `driver.dependencies`,
  `driver.trait_obligations`, `driver.test_hardware_facts`,
  `driver.build_contract`, `driver.requirement_ids`, the optional
  `driver.public_test_record`, the seven canonical checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock whose resources
   intersect this instance — the stage resource `stage:write-driver:<name>` and
   one `path:<root-qualified-target>` resource per file this run may mutate — and
   classify each as live, interrupted or ambiguous. Recovery is scoped to
   `write-driver:<name>` by **intersecting path resources**, never to all
   `write-driver` work: a resuming driver that claims every `write-driver` lock
   treats a sibling driver's live run as its own interruption. Live means
   concurrency: do not interfere and do not recover. Ambiguous means wait one
   30-second refresh interval, reread, and fail closed if it is still ambiguous.
   Interrupted, or ambiguous still unresolved, means recovery: do not mutate the
   suspect output, inventory and hash it into a recovery Markdown FileRef,
   compare it against the last valid handoff, and publish `partial` with empty
   blockers when unaffected fresh candidate work remains or `blocked` with an
   `interrupted:write-driver:<name>` blocker when it does not. Record the
   comparison, the disposition and the new candidate location before an
   authorized actor removes the lock. Resume only in a fresh candidate, never in
   place. An absent `06-driver-<name>.toml` is **not** proof that no prior
   dispatch ran: `halucinator/.run/` is gitignored and invisible to a fresh
   clone, so a missing handoff and a missing lock together are silence, not
   evidence.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `05-platform`.
   Exit 0 with silent output is necessary; a missing interpreter, Python below
   3.11, a timeout, a nonzero exit, or not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or an unrelated ambiguous lock
   as a named blocker rather than ignoring it.
3. **Load the predecessor and the dispatch payload.** Load the exact
   `05-platform` leaves through the admission mapping above, and separately load
   the coordinator-owned target, subsystem name, scope kind, modes, requirement
   IDs, chip feature, compilation target and roots. Preserve dirty and unrelated
   worktree edits; never require a commit or a stash. On a missing mandatory
   input, return `blocked`.
4. **Classify the peripheral and select exactly one profile.** Classify the
   dispatched subsystem against the four rows in "When to use" using the cited
   hardware facts and the platform contract, and select exactly one profile.
   Selecting the universal checklist alone requires a positive finding that
   neither the GPIO, the time-service nor the bus shape applies. A subsystem you
   cannot classify with a cited reason is not a bus by default: publish `partial`
   with the classification recorded as incomplete coverage, or `blocked` when the
   missing hardware meaning must come from **hal-datasheet**. Fail closed.
5. **Record the selected profile and the classification rationale.** Record the
   selected profile, the positive finding that selected it, the rejected
   alternatives and their reasons in a hashed Markdown record referenced from
   `handoff.notes`. This guard is **advisory, not mechanical**: the typed schema is
   frozen and no `06-driver` leaf can encode a profile discriminator —
   `driver.capabilities` and `driver.public_api` are free-form string arrays and
   `driver.scope_kind` is only `full` or `scaffold-support` — so no validator can
   confirm that the recorded profile is the one that was followed. Only the
   independent review can.
6. **Select the working root and acquire the instance lock.** Select the
   canonical module paths when the predecessor is `ready`, or an unused
   `halucinator/candidates/driver-*/` root while it is `partial`, check the
   complete write and delete footprint, and acquire the `kind="stage"` lock
   carrying `stage:write-driver:<name>` **and one `path:` resource per file this
   run may mutate**, held through publication. A name-only lock is insufficient:
   `clock-modules` is shared between concurrent driver dispatches, so two drivers
   extending the clock tree collide unless their path resources intersect.
   `.opencode/schema/layout.md` gives the lock naming rule and
   `.opencode/agents/hal-integrator.md` the worked form.
7. **Load the live references and record what was read.** Load
   `embassy-mcxa/DEVGUIDE.md` and the concern-specific files named by `AGENTS.md`
   in the actual checkout, together with the profile's own reading list, and
   record the sections, files, source IDs and hardware citations actually read.
   Discharge `live-reference-read` from that citation set. A remembered pattern
   from this toolkit is not a live reference, and a missing live reference blocks
   the affected implementation.
8. **Compare the declared capabilities against PAC and platform coverage.**
   Compare each capability in scope against the generated PAC accessors, the
   generated singleton and interrupt mappings, and the `platform.foundation_api`
   and `platform.supporting_subsystems` the scaffold established, and discharge
   `generated-mappings` without editing generated output — or record it
   `not-applicable` with a reason the reviewer audits, because a generic driver
   ID has no safe cross-peripheral derivation. A missing accessor returns through
   **hal-coordinator** to **hal-svd**.
9. **Author the public API and count its inhabitants.** Author the public types
   first: every field with a finite legal domain is an enum, never a `u8` or a
   `u32`; `Default` is the hardware-nominal reset configuration and never one
   board's tuning; out-of-range values are rejected rather than masked; errors
   are split by operation and marked `#[non_exhaustive]` with no module `Result`
   alias; and no import is a wildcard. Record the inhabitant count of each type
   against the legal states the hardware admits.
10. **Author the implementation as a functional core and an imperative shell.**
    Author the pure value-to-value logic — divisors, encodings, timing and layout
    arithmetic — free of registers, `async` and HAL types, and keep the
    register-touching shell nearly branch-free, following the universal checklist
    and the selected profile clause by clause. Encoding is total; decoding is
    partial and returns a `Result`.
11. **Run the host tests over the functional core.** Run the host-side unit tests
    of that pure logic, exhaustive over small legal domains and covering the
    relevant invalid boundaries, and discharge `pure-host-tests` from those runs —
    or record it `not-applicable` with a reason the reviewer audits when the
    subsystem genuinely has no host-testable core. Tests must exercise the
    production functions; a separate model built only to obtain host evidence
    proves that the model agrees with itself.
12. **Validate each implemented upstream trait obligation.** Validate every
    implemented `embedded-hal`, `embedded-hal-async`, `embedded-io` or
    `embassy-time-driver` contract against its own documentation used as a
    checklist, record which obligations were verified and how in
    `driver.trait_obligations`, and discharge `trait-conformance`. The check is
    `not-applicable` only when no upstream trait is implemented.
13. **Run the formatting, lint and build matrix.** Run the repository-required
    formatting and lint checks for every touched surface and build for every chip
    feature combination the crate claims, deriving commands and features from the
    live checkout rather than an indiscriminate `--all-features`, and discharge
    `format-lint-build`. A missing tool leaves a check `unrun`; it does not make
    it inapplicable.
14. **Publish the preliminary tester-safe handoff and validate it.** Publish a
    `partial` `06-driver-<name>` carrying the complete tester-safe
    `driver.public_api`, the profile-classification note, `driver.capabilities`,
    `driver.test_hardware_facts`, `driver.build_contract`,
    `driver.requirement_ids` and the current `driver.owned_files`, preserving a
    hashed snapshot and recovery record of any deterministic handoff `state.toml`
    currently pins before replacing it, and run
    `python .opencode/schema/validate.py <repository-root> --kind all` again.
    This breaks a real cycle: `ready` here requires `target-link-ci`, the tester
    normally admits only a `ready` `06`, and specialists cannot dispatch each
    other. A `partial` predecessor permits fresh disposable candidate work under
    `.opencode/schema/handoff-common.md`, so **hal-coordinator** may now dispatch
    **hal-tester** for candidate-only authoring and **hal-integrator** to link it.
    Neither may claim `ready` nor mutate a canonical path until this handoff is
    finalized. **hal-coordinator** freezes exactly one `06` revision per test
    cycle; publish no further `06` until that cycle closes or is cancelled, or
    repeated republishing starves testing. Send only public signatures,
    observable contracts, versioned traits, build requirements and cited facts:
    no bodies, no private names, no register sequences, no interrupt logic, no
    implementation paths, no disassembly and no language-server response carrying
    a body.
15. **Request the target link and the independent review.** Request through
    **hal-coordinator** that **hal-integrator** build the tester-authored binary
    to an actual linked image for the cited memory and runtime facts with the
    build-only CI path exercised, and discharge `target-link-ci` from that linked
    artifact; `cargo check` is not a link. Then request through
    **hal-coordinator** the independent **hal-reviewer** review over the changed
    implementation, the citation set and the public API projection, and discharge
    `independent-review` from the accepting verdict. Only review.verdict=ready
    accepts; ready-with-fixes and not-ready do not. A stale review, an
    unavailable reviewer or an unresolved required finding is not acceptance.
16. **Re-attest, publish the final handoff, and run the final gate.** Re-attest
    where referenced bytes changed: preserve the superseded evidence and the
    superseded review records, create replacement evidence at a **new** path
    rather than overwriting one, rerun only the affected checks, and obtain a new
    review where the reviewed bytes changed. **Never delete old evidence or old
    review records to regain validation.** Then rewrite the final
    `halucinator/handoff/06-driver-<name>.toml`, run `python .opencode/schema/validate.py <repository-root> --kind all` over it, let
    **hal-coordinator** update `state.toml` through the compare-and-swap
    sequence — upserting the single `state.stages[]` entry whose ID is
    `write-driver:<name>` **by ID, never blindly appending**, because duplicate
    IDs collapse by last-wins assignment during validation — run the final
    `--kind all` gate, and return the record paths, status and next action. State
    that no shared file, commit, publication or hardware operation was performed.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `format-lint-build` | Run the repository formatting and lint checks and build every claimed chip feature combination | `halucinator/candidates/driver-<name>/evidence/format-lint-build.log` |
| `generated-mappings` | Compare the declared capabilities against the generated singleton, interrupt and accessor mappings | `halucinator/candidates/driver-<name>/evidence/generated-mappings.log`, or `reason (no evidence FileRef)` when the subsystem has no derivable generated mapping |
| `independent-review` | Request the coordinator-dispatched review over the implementation, citations and public API, and record its accepting verdict | `halucinator/handoff/08-review-driver-<name>.toml` |
| `live-reference-read` | Record the live DEVGUIDE sections, checkout files, source IDs and hardware citations actually read | the hashed classification and citation record referenced from `handoff.notes` |
| `pure-host-tests` | Run the host tests over the functional core, exhaustive on small legal domains | `halucinator/candidates/driver-<name>/evidence/pure-host-tests.log`, or `reason (no evidence FileRef)` when the subsystem has no host-testable core |
| `target-link-ci` | Build the tester-authored binary to an actual linked image and exercise the build-only CI path | `halucinator/candidates/driver-<name>/evidence/target-link-ci.log` |
| `trait-conformance` | Validate each implemented upstream trait obligation against its own documentation | `halucinator/candidates/driver-<name>/evidence/trait-conformance.log`, or `reason (no evidence FileRef)` when no upstream trait is implemented |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. The instance lock, the
frozen `06` revision and the compare-and-swap sequence are the same kind of
discipline: lock resources are unrestricted strings and fence nothing
mechanically. Typed evidence hashes freshness, not relevance — a reviewer still
judges whether an artifact discharges the check it is attached to.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
the consumed `05-platform` is `ready` against the current `scope.revision` and
`scope.decision`, every applicable check is `passed`, `driver.dependencies`
identities and features are current, the reviewed bytes are the ones placed at
their final paths, and the independent review accepted. Only
review.verdict=ready accepts; ready-with-fixes and not-ready do not. A full
hardware scope additionally carries a current `driver.public_test_record`. Ready
here means **software** readiness for the next dispatch; it establishes nothing
about silicon.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Only disposable candidate work continues. A `partial` publication must
pin, through `handoff.notes`, a driver record naming every prior suspect path
with its hash, the chosen disposition, and the new authorized candidate root.
The deliberate tester-safe publication at step 14 is a `partial`, and partial
output is not a narrower completed scope.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names the affected requirement IDs, the owner,
the next action and the evidence needed, and identifies a missing accessor,
hardware meaning, tool, access, dispatch or decision that only somebody outside
this stage can supply. A missing tool never silently lowers the gate.

## Application example

For exact MCU `unobtainium-circuits-uc-not-a-real-mcu-0001` the coordinator dispatches `uart` in blocking and DMA
modes against a `ready` `05-platform`. The subsystem is classified positively as
a stream bus, so `profiles/bus.md` is selected and the finding is recorded; the
GPIO and time-service profiles are recorded as rejected with reasons. The baud
divisor search and the frame encoder are the functional core and are exhausted
on the host over the legal divisor range; `embedded-io-async` supplies the trait
obligations. No peripheral-specific skill exists for UART, and none is needed.
The emitted handoff:

```toml
[handoff]
schema = 2
stage = "write-driver"
status = "ready"
inputs = [
  { path = "halucinator/handoff/05-platform.toml", sha256 = "4c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" },
]
notes = [
  { path = "halucinator/candidates/driver-uart/evidence/classification.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "8f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e" }

[coverage]
complete = ["peripheral:uart"]
incomplete = []

[driver]
name = "uart"
scope_kind = "full"
capabilities = ["blocking-transmit", "blocking-receive", "dma-transmit", "dma-receive"]
public_api = [
  "pub struct Uart<'d, M: Mode>",
  "pub fn new_blocking(peri: Peri<'d, T>, tx: Peri<'d, impl TxPin<T>>, rx: Peri<'d, impl RxPin<T>>, config: Config) -> Result<Uart<'d, Blocking>, CreateError>",
  "pub enum Parity { None, Even, Odd }",
  "pub enum StopBits { One, Two }",
  "pub async fn write(&mut self, buf: &[u8]) -> Result<usize, SendError>",
]
owned_files = [
  { path = "embassy-unobtainium/src/uart/mod.rs", sha256 = "91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80" },
  { path = "embassy-unobtainium/src/uart/config.rs", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" },
]
requirement_ids = ["UART-01", "UART-02", "UART-03"]
public_test_record = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/uart.md", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }
facts_handoff = { path = "halucinator/handoff/02-facts.toml", sha256 = "d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4" }
test_hardware_facts = ["fixture.uart.fifo-depth", "fixture.uart.reset-value"]

[driver.build_contract]
cargo_chip_feature = "uc-not-a-real-mcu-0001"
rust_compilation_target = "thumbv8m.main-none-eabihf"
init_calls = ["embassy_unobtainium::init(Default::default())"]
memory_runtime = { path = "embassy-unobtainium/memory.x", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }
observation = "A linked image calling init and constructing Uart in blocking and DMA modes."

[[driver.dependencies]]
crate = "unobtainium-pac"
identity = "0.1.0"
features = ["uc-not-a-real-mcu-0001", "rt"]

[[driver.trait_obligations]]
dependency_crate = "embedded-io-async"
trait = "Write"
obligations = [
  "write returns Ok(0) only when buf is empty",
  "flush completes only after the transmitter is idle",
]

[[checks]]
id = "live-reference-read"
status = "passed"
evidence = { path = "halucinator/candidates/driver-uart/evidence/classification.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" }

[[checks]]
id = "format-lint-build"
status = "passed"
evidence = { path = "halucinator/candidates/driver-uart/evidence/format-lint-build.log", sha256 = "e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5" }

[[checks]]
id = "pure-host-tests"
status = "passed"
evidence = { path = "halucinator/candidates/driver-uart/evidence/pure-host-tests.log", sha256 = "f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6" }

[[checks]]
id = "trait-conformance"
status = "passed"
evidence = { path = "halucinator/candidates/driver-uart/evidence/trait-conformance.log", sha256 = "08192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7" }

[[checks]]
id = "generated-mappings"
status = "passed"
evidence = { path = "halucinator/candidates/driver-uart/evidence/generated-mappings.log", sha256 = "192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }

[[checks]]
id = "target-link-ci"
status = "passed"
evidence = { path = "halucinator/candidates/driver-uart/evidence/target-link-ci.log", sha256 = "2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f70819" }

[[checks]]
id = "independent-review"
status = "passed"
evidence = { path = "halucinator/handoff/08-review-driver-uart.toml", sha256 = "3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a" }
```

A fact nobody established is an absent key or an empty collection, never a
sentinel word.

## Quick reference

| Element | Value |
|---|---|
| Stage | `write-driver`, one instance per subsystem, `write-driver:<name>` |
| Emitter | `hal-driver`; `hal-integrator` is the sole committer |
| Emitted handoff | `halucinator/handoff/06-driver-<name>.toml`, kind `06-driver` |
| Consumes | `05-platform` only; the subsystem, modes and requirement IDs come from coordinator-owned state |
| Checks | `format-lint-build`, `generated-mappings`, `independent-review`, `live-reference-read`, `pure-host-tests`, `target-link-ci`, `trait-conformance` |
| Universal reading | [driver checklist](./references/driver-checklist.md), [driver record](./references/driver-record.md) |
| Profiles | exactly one of [gpio](./references/profiles/gpio.md), [time-driver](./references/profiles/time-driver.md), [bus](./references/profiles/bus.md), or none on a positive finding |
| Owned classes | `peripheral-modules`, `clock-modules`, `driver-candidates`, `driver-evidence`, `driver-handoff` |
| Deltas | `driver-records` (`GPIO.md`, `TIME-DRIVER.md`, otherwise `drivers/<name>.md`), `platform-notes`, `sources-catalog` via `hal-integrator`; `roadmap` via `hal-coordinator` |
| Candidate root | `halucinator/candidates/driver-*/` while the predecessor is `partial` |
| Lock | `kind="stage"` with `stage:write-driver:<name>` plus one `path:` resource per mutable file, cooperative only |
| Cycle break | a validated tester-safe `partial` `06`, one frozen revision per test cycle |
| Routing | every question, delta, review request, scope change and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, applicable checks `passed`, accepting review |
| Deferred | a profile discriminator in the typed schema |

## Common mistakes

- **Reaching for `profiles/bus.md` by default.** It is the most detailed profile
  and therefore the most attractive one. GPIO is not a bus and the time service
  is not a bus; selecting bus for either imports constructors, modes and
  transaction semantics that do not apply and deletes the ones that do.
- **Treating "no profile matched" as a classification.** It is a finding that
  must be positively established and recorded. An unclassified peripheral is
  `partial` or `blocked`, never a bus by default.
- **Believing the profile record is enforced.** No `06-driver` leaf can carry a
  profile discriminator, so nothing but the review can tell whether the recorded
  profile is the one that was followed.
- **Scoping recovery to `write-driver` rather than `write-driver:<name>`.** It
  makes a sibling driver's live run look like your own interruption, and the
  recovery path then mutates somebody else's work.
- **Holding a name-only lock.** `clock-modules` is shared across concurrent
  driver dispatches; without intersecting `path:` resources two drivers extend
  the clock tree at once.
- **Waiting for `ready` before the tester can start.** That is the cycle: publish
  the validated tester-safe `partial` instead, and freeze one revision per test
  cycle so testing is not starved by republication.
- **Appending a second `state.stages[]` entry on resumption.** Duplicate IDs
  collapse by last-wins assignment, so the append silently discards one of them.
  Upsert by ID.
- **Hand-rolling clock gating in a peripheral module.** The policy then exists in
  two places that can disagree. Extend `clocks`.
- **Checking a condition and then registering the waker.** A completion that
  lands in that window is lost and the future sleeps forever.
- **Returning on the first error flag.** The others stay latched and the
  peripheral wedges.
- **Deleting superseded evidence or a superseded review to make a rerun pass.**
  It converts a traceable supersession into an untraceable one, and it is the
  most tempting shortcut when a late check fails.
- **Sending the tester a body, a register sequence or a language-server
  response.** Source blindness is the reason its tests are worth anything.
- **Quoting only the rejecting verdict.** Stating what does not accept, without
  stating what does, turns the gate into advice. Use the exact sentence.
- **Describing the lock, the frozen revision or the validator wiring as
  enforcement.** All three are honor systems, and saying otherwise makes every
  reader trust an attestation nobody made.
