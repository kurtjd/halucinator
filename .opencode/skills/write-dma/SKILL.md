---
name: write-dma
description: >-
  Use when hal-coordinator dispatches a shared DMA subsystem against a ready
  05-platform handoff, or resumes a distinct DMA 06-driver handoff after
  partial or blocked. Dispatch and search terms: DMA channel ownership,
  request routing, descriptors, barriers, cancellation, cache coherency,
  non-cacheable memory, shared DMA state, 06-driver-dma handoff. Wrong for
  peripheral-specific transfer APIs, linker materialization, target tests,
  hardware debugging, PAC edits, shared crate wiring, or commits.
compatibility: opencode
---

# Write the shared DMA subsystem

```halucinator-skill-contract
stage: write-driver
participants: hal-driver
emitter: hal-driver
emits: 06-driver|halucinator/handoff/06-driver-dma.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,driver.build_contract.cargo_chip_feature,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.build_contract.rust_compilation_target,driver.capabilities,driver.dependencies.crate,driver.dependencies.features,driver.dependencies.identity,driver.facts_handoff,driver.name,driver.owned_files,driver.public_api,driver.public_test_record,driver.requirement_ids,driver.scope_kind,driver.test_hardware_facts,driver.trait_obligations.dependency_crate,driver.trait_obligations.obligations,driver.trait_obligations.trait,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision
checks: format-lint-build,generated-mappings,independent-review,live-reference-read,pure-host-tests,target-link-ci,trait-conformance
consumes: 05-platform|coverage.complete,coverage.incomplete,handoff.blockers,handoff.inputs,handoff.notes,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
writes: hal-driver|driver-candidates
writes: hal-driver|driver-evidence
writes: hal-driver|driver-handoff
writes: hal-driver|peripheral-modules
supplies-delta: hal-driver|driver-records
supplies-delta: hal-driver|platform-notes
supplies-delta: hal-driver|roadmap
supplies-delta: hal-driver|sources-catalog
```

DMA is not one more peripheral. Its state — channels, request routing, descriptor
memory and the coherency policy over it — is contended by every peripheral that
ever transfers through it, so a mistake here is not local to one driver. That
contention is the whole reason this subsystem gets its own skill rather than one
more `write-driver` dispatch.

## When to use

Use this skill when **hal-coordinator** dispatches the shared DMA subsystem
against a `05-platform` handoff that validates and is `ready`, or when a previous
run left `halucinator/handoff/06-driver-dma.toml` at `partial` or `blocked` and
the recorded next action is now possible.

Use it for channel ownership and allocation, request routing, descriptor layout
and lifetime, memory ordering and barriers, transfer cancellation, and the
cache-coherency policy the transfers depend on.

Do not use it for a peripheral's own DMA-mode API — a UART writing through a
channel is that peripheral's dispatch and consumes this subsystem's public
surface. Do not use it to materialize a linker script, to author or run target
tests, to debug on hardware, to edit the PAC, to wire shared crate files, or to
commit.

## Ownership and boundaries

**hal-driver** implements the subsystem and owns no shared file, no target test
and no commit. Every cross-owner transition returns to **hal-coordinator**;
specialists never dispatch peers.

| Owner | Materializes here | Never here |
|---|---|---|
| **hal-driver** | classes `peripheral-modules`, `driver-candidates`, `driver-evidence`, `driver-handoff`; the DMA implementation, its host tests and the `06-driver-dma` handoff | shared files, manifests, linker scripts, CI, examples, target tests, commits |
| **hal-coordinator** | class `roadmap`, exactly `halucinator/docs/<target-id>/notes/ROADMAP.md`; the target, bounded scope and every dispatch | implementation or shared files |
| **hal-integrator** | classes `driver-records`, `platform-notes`, `sources-catalog`, every shared crate file and the linker scripts; and it is the **sole committer** | driver logic, test logic, scope decisions |
| **hal-tester** | the source-blind link-check and validation binaries under `halucinator/test-candidates/<name>/` | reading this skill, this subsystem's source, or any canonical path |
| **hal-reviewer** | the `08-review` verdict only | any file this stage produces |

Cross-owner deltas: this stage **authors semantic content only** for
`driver-records`, `platform-notes` and `sources-catalog`, all three owned and
materialized by **hal-integrator**, and for `roadmap`, owned and materialized by
**hal-coordinator**. Route every one of those four through **hal-coordinator**,
which dispatches the registry owner and returns its FileRef. Never write a file
in those classes directly.

Clock, reset and power bring-up for the DMA controller use the selected target
lifecycle contract in the owning layer, never a duplicate in the DMA module. Do
not invent a gate/guard where none exists. A DMA module poking a clock-control register means the gating policy
now lives in two places that can disagree.

The coherency policy is recorded here and materialized elsewhere. When the design
needs cache maintenance, a non-cacheable section or a specific descriptor memory
placement, record that dependency explicitly and route the linker or memory-map
delta through **hal-coordinator** to **hal-integrator**. This skill does not
write linker files.

A missing accessor, channel or request-mux metadata item returns through
**hal-coordinator** to **hal-svd**; a missing hardware meaning returns to
**hal-datasheet**. Never bridge either gap with raw register access or an
invented constant.

## Inputs

Consume the validated `05-platform` leaves declared in the contract:

| Admission concern | Consumed field |
|---|---|
| Crate under work | `platform.crate_manifest`, `platform.pac_manifest` |
| Startup and API contract | `platform.startup_clock_contract`, `platform.foundation_api` |
| Available subsystems | `platform.supporting_subsystems` |
| Selected subsystem and modes | `platform.first_driver`, `platform.first_driver_modes` |
| Dependency contracts | `platform.dependencies.crate`, `platform.dependencies.identity`, `platform.dependencies.features` |
| Provenance | `platform.source_ids`, `platform.cited_notes`, `platform.roadmap` |
| Lineage | `handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

Read separately from coordinator-owned state: the `target.*` identity, the DMA
scope kind and modes, the requirement IDs, the Cargo chip feature, the Rust
compilation target, the destination crate and the documentation roots.

Read the cited hardware facts for the channel count, the request-source
numbering, the descriptor layout, the transfer-size and address-alignment
constraints, the error and completion flags, and the memory attributes of every
region a descriptor or buffer may occupy. **Never invent a DMA request number, a
channel count or a descriptor field.** Every one comes from a cited manual
locator or from generated PAC metadata.

A `blocked` predecessor permits no consumption. A `partial` one permits
read-only inspection and disposable candidate work under
`halucinator/candidates/driver-dma/` only: no canonical placement and no
downstream `ready`.

## Outputs

- The DMA module tree at canonical paths when the predecessor is `ready`, or
  under `halucinator/candidates/driver-dma/src/**` while it is `partial`.
- Host-side unit tests of the functional core — descriptor layout, request
  selection, transfer-length and alignment arithmetic — exhaustive over small
  legal domains.
- A hashed coherency-policy record naming the cache-maintenance or
  non-cacheable-memory dependency, the cited facts behind it, and the linker or
  memory-map delta requested from **hal-integrator**.
- Record deltas for `driver-records`, `platform-notes`, `sources-catalog` and
  `roadmap`, each materialized by its registry owner.
- Check evidence under `halucinator/candidates/driver-dma/evidence/`.
- `halucinator/handoff/06-driver-dma.toml`, carrying `driver.name`,
  `driver.scope_kind`, `driver.owned_files`, `driver.capabilities`, the complete
  tester-safe `driver.public_api`, `driver.dependencies`,
  `driver.trait_obligations`, `driver.test_hardware_facts`,
  `driver.build_contract`, `driver.requirement_ids`, the optional
  `driver.public_test_record`, the seven canonical checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock whose resources
   intersect this dispatch — the stage resource `stage:write-driver:dma` and one
   `path:<root-qualified-target>` resource per file this run may mutate — and
   classify each as live, interrupted or ambiguous. Live means concurrency: do
   not interfere and do not recover. Ambiguous means wait one 30-second refresh
   interval, reread, and fail closed if it is still ambiguous. Interrupted, or
   ambiguous still unresolved, means recovery: do not mutate the suspect output,
   inventory and hash it into a recovery Markdown FileRef, compare it against the
   last valid handoff, and publish `partial` with empty blockers when unaffected
   fresh candidate work remains or `blocked` with an
   `interrupted:write-driver:dma` blocker when it does not. Record the
   comparison, the disposition and the new candidate location before an
   authorized actor removes the lock. Resume only in a fresh candidate, never in
   place. An absent `06-driver-dma.toml` is not proof that no prior dispatch ran:
   `halucinator/.run/` is gitignored and invisible to a fresh clone.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `05-platform`.
   Exit 0 with silent output is necessary; a missing interpreter, Python below
   3.11, a timeout, a nonzero exit, or not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or an unrelated ambiguous lock
   as a named blocker rather than ignoring it.
3. **Select the working root and acquire the DMA lock before any mutable read.**
   Select the canonical DMA module paths when the predecessor is `ready`, or an
   unused `halucinator/candidates/driver-dma/` root while it is `partial`;
   enumerate the complete write and delete footprint — every DMA module file,
   every `embassy-*/src/clocks/**` file this run may extend, and every evidence
   file — and acquire one `kind="stage"` lock carrying `stage:write-driver:dma`
   **plus one `path:` resource for each of those files**, held unbroken through
   handoff publication. Acquire it **before reading any mutable baseline**, not
   merely before writing. Ownership-class overlap does not serialize writes; only
   intersecting `path:` resources do. Without them the lost update is concrete: a
   clocks slice reads `src/clocks/gate.rs` at V0, this run reads V0, the clocks
   slice writes Vc, this run writes Vu derived from V0, and Vc is gone with no
   diagnostic. `.opencode/schema/layout.md` gives the lock naming rule.
4. **Load the predecessor, the dispatch payload and the cited DMA facts.** Load
   the exact `05-platform` leaves through the admission mapping above, the
   coordinator-owned target, scope kind, modes, requirement IDs, chip feature,
   compilation target and roots, and the cited channel count, request-source
   numbering, descriptor layout, alignment and transfer-size limits, error and
   completion flags, and memory attributes. Preserve dirty and unrelated worktree
   edits; never require a commit or a stash. On a missing mandatory input, return
   `blocked`.
5. **Load the live references and record what was read.** Load
   `embassy-mcxa/DEVGUIDE.md` and the concern-specific files named by `AGENTS.md`
   in the actual checkout, together with the live shared-state and DMA guidance
   the destination crate already carries, and record the sections, files, source
   IDs and hardware citations actually read. Discharge `live-reference-read` from
   that citation set. A remembered pattern from this toolkit is not a live
   reference, and a missing live reference blocks the affected implementation.
6. **Compare every channel and request identity against generated metadata.**
   Compare each channel index, each request-source selection and each descriptor
   register field in scope against the generated PAC accessors and the generated
   singleton and interrupt mappings, and discharge `generated-mappings` without
   editing generated output. A disagreement is a metadata defect, not a driver
   workaround: it returns through **hal-coordinator** to **hal-svd**.
7. **Author the ownership and descriptor types.** Author the public types so
   that an invalid channel, request-source or descriptor-lifetime combination
   cannot be constructed at all, rather than being rejected at run time: a
   channel is an owned `Peri`-style resource with a lifetime, a request source is
   an enum over the cited legal sources, and a descriptor borrows its buffers for
   at least as long as the transfer can touch them. No `u8` or `u32` appears in a
   public signature where an enum fits. `Default` is the hardware-nominal reset
   configuration. Errors are split by operation, marked `#[non_exhaustive]`, with
   no module-wide `Result` alias and no wildcard import.
8. **Author the functional core and the imperative shell.** Author descriptor
   layout, request selection, alignment checking and transfer-length arithmetic
   as pure value-to-value functions free of registers, `async` and HAL types, and
   keep the register-touching shell nearly branch-free. Encoding a value you were
   able to construct is total; decoding a register pattern the silicon can
   produce is partial and returns a `Result`. Use only that contract for clock,
   reset and power bring-up. Do not invent a gate/guard where none exists.
9. **Author cancellation and memory ordering.** Guard the armed region with
   `OnDrop` and `defuse` only on the success path, so a dropped transfer future
   disables the peripheral request, quiesces the channel, waits for the channel
   to leave its active state without busy-waiting on an async path, applies the
   required barriers in the cited order, and resets the shared channel state so
   the next claimant starts clean. **Account for every relevant error condition
   using cited per-register read/clear semantics before returning**, preserving
   unrelated and control bits and leaving no recoverable condition latched; a
   W1C, a W0C and a read-to-clear flag each clear differently, and read-to-clear
   state cannot always be snapshotted first. An early return on the first
   condition found leaves the rest latched and the channel wedged.
10. **Record the coherency policy and route its delta.** Record explicitly, in a
    hashed Markdown record referenced from `handoff.notes`, whether the design
    requires cache maintenance around buffers, a non-cacheable section, or a
    specific descriptor placement, with the cited memory-attribute facts behind
    it, and request through **hal-coordinator** that **hal-integrator**
    materialize any linker or memory-map delta. Silently assuming coherent
    memory is the failure this step exists to prevent.
11. **Run the host tests and validate the trait obligations.** Run the host-side
    unit tests over the functional core — exhaustive over the legal channel and
    request domains where those domains are small, and covering the invalid
    alignment and length boundaries — and discharge `pure-host-tests`. Validate
    every implemented upstream trait contract against its own documentation used
    as a checklist, record what was verified in `driver.trait_obligations`, and
    discharge `trait-conformance`; that check is `not-applicable` only when no
    upstream trait is implemented.
12. **Run the formatting, lint and build matrix.** Run the repository-required
    formatting and lint checks for every touched surface and build for every chip
    feature combination the crate claims, deriving commands and features from the
    live checkout rather than an indiscriminate `--all-features`, and discharge
    `format-lint-build`. A missing tool leaves a check `unrun`; it never makes it
    inapplicable.
13. **Publish the preliminary tester-safe handoff and validate it.** Publish a
    `partial` `06-driver-dma` carrying the complete tester-safe
    `driver.public_api`, the coherency record, `driver.capabilities`,
    `driver.test_hardware_facts`, `driver.build_contract`,
    `driver.requirement_ids` and the current `driver.owned_files`, preserving a
    hashed snapshot and recovery record of any deterministic handoff `state.toml`
    currently pins before replacing it, and run
    `python .opencode/schema/validate.py <repository-root> --kind all` again.
    Send only public signatures, observable contracts, versioned traits, build
    requirements and cited facts: no bodies, no private names, no register
    sequences, no interrupt logic and no language-server response carrying a
    body. `hal-tester` is denied this source on purpose, and a leaked `pac::`
    path or `unsafe {` block in the public projection defeats the reason its
    tests are worth anything.
14. **Request the target link and the independent review.** Request through
    **hal-coordinator** that **hal-integrator** build the tester-authored binary
    to an actual linked image for the cited memory and runtime facts with the
    build-only CI path exercised, and discharge `target-link-ci` from that linked
    artifact; `cargo check` is not a link. Then request through
    **hal-coordinator** the independent **hal-reviewer** review over the changed
    implementation, the cancellation and barrier reasoning, the coherency record
    and the public API projection, and discharge `independent-review` from the
    accepting verdict. Only review.verdict=ready accepts; ready-with-fixes and
    not-ready do not. A stale review, an unavailable reviewer or an unresolved
    required finding is not acceptance.
15. **Re-attest, publish the final handoff, and run the final gate.** Re-attest
    where referenced bytes changed: preserve the superseded evidence and review
    records, create replacement evidence at a **new** path rather than
    overwriting one, rerun only the affected checks, and obtain a new review
    where the reviewed bytes changed. Never delete old evidence or an old review
    record to regain validation. Then rewrite the final
    `halucinator/handoff/06-driver-dma.toml`, run
    `python .opencode/schema/validate.py <repository-root> --kind all` on it, let
    **hal-coordinator** update `state.toml` through the compare-and-swap sequence
    — upserting the single `state.stages[]` entry whose ID is
    `write-driver:dma` by ID, never blindly appending — and run the final
    `--kind all` gate.
16. **Return or restart after contention.** Return the record paths, status and
    next action, and release the lock only after durable publication. Any
    contention, or any mutable baseline whose bytes changed while the lock was
    held or between acquisition and read, requires restarting from a fresh
    baseline in a fresh candidate root rather than merging by hand. State that no
    shared file, linker file, commit, publication or hardware operation was
    performed.

When a required tool, target, formatter, schema, linker utility, probe, runner or
reviewer is unavailable, record the attempted command, discovered identity,
failure output, affected check and exact remedy in a new hashed evidence FileRef.
Leave the affected check `unrun`; never mark it `not-applicable`. Ask the user to
install or expose the named capability, provide an approved existing path or
runner, or request a coordinator-owned scope decision; the agent does not install
tools. Publish `partial` with `can_progress=true` and empty blockers when
unaffected work remains, using truthful coverage: `coverage.incomplete` may
remain empty when the `unrun` check alone makes the handoff partial. Publish
`blocked` with `can_progress=false` and a named `environment:<capability>`
blocker when no scoped work can continue. On resumption, rerun entry-state
classification and the `--kind all` gate, verify the supplied identity, create
replacement evidence at a fresh path, rerun affected checks and re-attest.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `format-lint-build` | Run the repository formatting and lint checks and build every advertised chip feature combination | `halucinator/candidates/driver-dma/evidence/format-lint-build.log` |
| `generated-mappings` | Compare every channel index and request-source identity against the generated PAC metadata | `halucinator/candidates/driver-dma/evidence/generated-mappings.log` |
| `independent-review` | Request the coordinator-dispatched review over the implementation, cancellation and coherency evidence | `halucinator/handoff/08-review-driver-dma.toml` |
| `live-reference-read` | Record the live DEVGUIDE sections, checkout files, source IDs and DMA citations actually read | `halucinator/candidates/driver-dma/evidence/live-references.md` |
| `pure-host-tests` | Run the exhaustive descriptor, alignment and request-routing tests over the functional core | `halucinator/candidates/driver-dma/evidence/pure-host-tests.log` |
| `target-link-ci` | Build a public DMA construction and transfer image to an actual linked artifact and exercise its CI path | `halucinator/candidates/driver-dma/evidence/target-link-ci.log` |
| `trait-conformance` | Validate every implemented upstream trait obligation against its own documentation | `halucinator/candidates/driver-dma/evidence/trait-conformance.log`, or `reason (no evidence FileRef)` when no upstream trait is implemented |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. The lock is the same
kind of discipline: lock resources are unrestricted strings and fence nothing
mechanically. Typed evidence hashes freshness, not relevance — a reviewer still
judges whether an artifact discharges the check it is attached to.

**No transitive invalidation exists in this toolkit.** This skill can only
*procedurally* confirm that its linker and coherency dependencies are current: an
invalidated or superseded `05-platform`, or a later change to the linker script
or memory map that the coherency policy depends on, does **not** mechanically
mark this `06-driver-dma` stale, and nothing recomputes it. Re-verify those
dependencies by hand on every resumption and say plainly in the handoff notes
when you did. Treating the recorded coherency policy as guaranteed-current is a
claim the schema does not support.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
the consumed `05-platform` is `ready` against the current `scope.revision` and
`scope.decision`, every applicable check is `passed`, the coherency dependency
was re-verified by hand and recorded, and the independent review accepted. Only
review.verdict=ready accepts; ready-with-fixes and not-ready do not. Ready here
means **software** readiness for the next dispatch; it establishes nothing about
silicon.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Only disposable candidate work under
`halucinator/candidates/driver-dma/` continues, and the deliberate tester-safe
publication at step 13 is one of these.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names the affected requirement IDs, the owner, the
next action and the evidence needed, and identifies a missing accessor, hardware
meaning, linker delta, tool, access, dispatch or decision that only somebody
outside this stage can supply.

## Application example

For the fictional exact MCU `unobtainium-circuits-uc-not-a-real-mcu-0001` in
crate `embassy-unobtainium`, the coordinator dispatches the shared DMA subsystem
against a `ready` `05-platform`. Channel ownership, descriptor transfer and
request routing are implemented; the descriptor and request-routing arithmetic is
the functional core and is exhausted on the host; no upstream trait is
implemented at this scope, so `trait-conformance` is recorded `not-applicable`
with a reason. The link and the review are still outstanding, so the handoff is
`partial`:

```toml
[handoff]
schema = 1
stage = "write-driver"
status = "partial"
can_progress = true
inputs = [
  { path = "halucinator/handoff/05-platform.toml", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/drivers/dma.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" }

[coverage]
complete = ["foundation:init-api", "foundation:interrupt-metadata"]
incomplete = ["peripheral:schema-demo"]

[driver]
name = "dma"
scope_kind = "scaffold-support"
owned_files = [
  { path = "halucinator/candidates/driver-dma/src/dma/mod.rs", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" },
]
capabilities = ["channel-ownership", "descriptor-transfer", "request-routing"]
public_api = ["pub struct Channel<'d>", "pub struct Transfer<'d>", "pub enum Request"]
dependencies = [{ crate = "unobtainium-pac", identity = "fixture-rev-1", features = ["rt"] }]
trait_obligations = []
test_hardware_facts = []
requirement_ids = ["foundation:dma"]

[driver.build_contract]
cargo_chip_feature = "uc-not-a-real-mcu-0001"
rust_compilation_target = "thumbv7em-none-eabi"
init_calls = ["embassy_unobtainium::init(Config::default())"]
memory_runtime = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "5555555555555555555555555555555555555555555555555555555555555555" }
observation = "A linked fictional fixture image constructs one public DMA channel and transfer."

[[checks]]
id = "live-reference-read"
status = "passed"
evidence = { path = "halucinator/candidates/driver-dma/evidence/live-references.md", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }

[[checks]]
id = "format-lint-build"
status = "passed"
evidence = { path = "halucinator/candidates/driver-dma/evidence/format-lint-build.log", sha256 = "7777777777777777777777777777777777777777777777777777777777777777" }

[[checks]]
id = "pure-host-tests"
status = "passed"
evidence = { path = "halucinator/candidates/driver-dma/evidence/pure-host-tests.log", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }

[[checks]]
id = "trait-conformance"
status = "not-applicable"
reason = "The fictional DMA scaffold-support surface implements no upstream trait."

[[checks]]
id = "generated-mappings"
status = "passed"
evidence = { path = "halucinator/candidates/driver-dma/evidence/generated-mappings.log", sha256 = "9999999999999999999999999999999999999999999999999999999999999999" }

[[checks]]
id = "target-link-ci"
status = "unrun"
evidence = { path = "halucinator/candidates/driver-dma/evidence/target-link-ci-pending.md", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

[[checks]]
id = "independent-review"
status = "unrun"
evidence = { path = "halucinator/candidates/driver-dma/evidence/review-pending.md", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }
```

A fact nobody established is an absent key or an empty collection, never a
sentinel word. Every channel index, request number and descriptor field above is
fictional and carries no hardware claim.

## Quick reference

| Element | Value |
|---|---|
| Stage | `write-driver`, instance `write-driver:dma` |
| Emitter | `hal-driver`; `hal-integrator` is the sole committer |
| Emitted handoff | `halucinator/handoff/06-driver-dma.toml`, kind `06-driver` |
| Consumes | `05-platform` only |
| Checks | `format-lint-build`, `generated-mappings`, `independent-review`, `live-reference-read`, `pure-host-tests`, `target-link-ci`, `trait-conformance` |
| Owned classes | `peripheral-modules`, `driver-candidates`, `driver-evidence`, `driver-handoff` |
| Deltas | `driver-records`, `platform-notes`, `sources-catalog` via `hal-integrator`; `roadmap` via `hal-coordinator` |
| Candidate root | `halucinator/candidates/driver-dma/` while the predecessor is `partial` |
| Lock | `stage:write-driver:dma` plus one `path:` resource per mutable DMA, clock or evidence file, acquired before any mutable read |
| Linker and coherency | recorded here, materialized by `hal-integrator`; currency is procedural only |
| Sibling skill | [`write-driver`](../write-driver/SKILL.md) for an ordinary peripheral |
| Schema | [`06-driver`](../../schema/06-driver.md), [`handoff-common`](../../schema/handoff-common.md) |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, applicable checks `passed`, accepting review |

## Common mistakes

- **Reading a mutable baseline before acquiring its `path:` resource.** This is
  the concrete lost update: the clocks slice reads `gate.rs` at V0, this run
  reads V0, the clocks slice writes Vc, this run writes Vu derived from V0, and
  Vc disappears with no diagnostic. Class overlap does not serialize writes.
- **Holding a name-only `stage:write-driver:dma` lock.** The clock modules and
  the evidence directory are shared with concurrent driver dispatches; without
  intersecting path resources the collision is invisible.
- **Assuming coherent memory.** A transfer that works on a cache-disabled bring-up
  image and fails later is the classic symptom. Record the cache-maintenance or
  non-cacheable dependency explicitly and route the linker delta.
- **Believing an invalidated `05-platform` marks this handoff stale.** It does
  not; there is no transitive invalidation. Re-verify by hand and say so.
- **Writing a linker script here.** It belongs to `hal-integrator` and reaches it
  through `hal-coordinator`.
- **Inventing a request number or a channel count.** A plausible constant
  compiles, which is exactly why it is worse than no constant.
- **Taking a channel index as a `u32` in a public signature.** A finite legal
  domain is an enum or an owned channel resource; the run-time range check and
  its error variant then stop existing.
- **Leaving a channel armed when the future drops.** Without `OnDrop` and a
  success-path `defuse`, the peripheral request stays enabled and the hardware
  writes into a buffer nobody owns any more.
- **Returning on the first error flag.** The rest stay latched and the channel
  wedges.
- **Busy-waiting for a channel to go idle on an async path.** On a
  single-threaded executor it stalls every task, watchdog included.
- **Duplicating the DMA clock/reset policy.** Use that contract, or the policy
  exists in two places that disagree. Do not invent a gate/guard where none
  exists.
- **Leaking `pac::` or `unsafe {` into `driver.public_api`.** The tester is
  blinded on purpose and consumes that projection directly.
- **Deleting superseded evidence to make a rerun pass.** It converts a traceable
  supersession into an untraceable one.
- **Describing the lock or the validator wiring as enforcement.** Both are honor
  systems, and saying otherwise makes every reader trust an attestation nobody
  made.
