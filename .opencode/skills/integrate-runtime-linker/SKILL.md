---
name: integrate-runtime-linker
description: >-
  Use when hal-coordinator dispatches the third scaffold-hal platform slice
  after clock and interrupt snapshots exist, for memory.x, linker sections,
  vectors, runtime features, stack or heap placement, RAM-first link variants
  and ELF inspection. Dispatch and search terms: memory.x, link.x, runtime,
  vectors, stack, heap, RAM-first, ELF, target link, platform snapshot,
  partial 05-platform handoff. Wrong for publishing a ready platform,
  independent canonical placement, loading hardware, peripheral drivers,
  clocks, interrupt metadata, DMA, or test logic.
compatibility: opencode
---

# Integrate the runtime and linker

```halucinator-skill-contract
stage: scaffold-hal
participants: hal-integrator
emitter: hal-integrator
emits: 05-platform|halucinator/handoff/05-platform.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
checks: advertised-builds,build-only-ci,format-lint,foundation-coverage,generated-mappings,independent-review,live-reference-read,negative-chip-selection,pure-host-tests,target-link
consumes: 05-platform|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
writes: hal-integrator|crate-manifest
writes: hal-integrator|example-support
writes: hal-integrator|integration-candidates
writes: hal-integrator|linker
writes: hal-integrator|platform-handoff
writes: hal-integrator|platform-lib
writes: hal-integrator|runtime-wiring
```

This slice makes the crate actually link for its target and proves it by
inspecting the produced ELF image — not by observing that a build command
exited zero.

## When to use

Use this skill when **hal-coordinator** dispatches the third and last platform
slice of the `scaffold-hal` stage, after the clocks slice and the interrupt
slice have each published their `partial` `05-platform`, and the corresponding
snapshots exist under the integration candidate. Use it for `memory.x`, linker
section layout, vector and runtime integration, boot assumptions, stack and
heap placement, the separately named RAM-first link variant, and target-link
verification by ELF inspection.

Use it again on resumption, when an earlier invocation of this slice left the
candidate incomplete and the recorded next action is now possible.

Do not use it to publish a `ready` platform, to move any canonical byte, or to
touch a device.

## Ownership and boundaries

The owning and emitting agent is **hal-integrator**. It materializes seven
classes it owns in [`ownership.toml`](../../ownership.toml): `linker`,
`runtime-wiring`, `platform-lib`, `crate-manifest`, `example-support`,
`integration-candidates` and `platform-handoff`. Clock modules are not in that
set: `clock-modules` is owned by **hal-driver** and was materialized by the
clocks slice. Do not edit it here; a clock defect returns through
**hal-coordinator** to its owner.

**This slice performs candidate-only mutation.** Every linker, runtime,
manifest and library byte it writes lands inside
`halucinator/candidates/integration-<id>/`, and nothing else. **This slice can
never perform canonical placement independently**, at any status, under any
schedule pressure, and regardless of how complete the candidate looks. Canonical
runtime and linker placement belongs only to the final consolidated scaffold
integration, after every slice has published and the peer review has accepted.
Relying on the broader integrator contract to imply that boundary is not
sufficient, which is why it is restated here as a rule of this skill.

This slice is the third of three ordered platform slices. It is not final, it
obtains no independent review of its own, and **it may never publish `ready`**.
Only the final consolidator, `scaffold-hal`, creates composite evidence for all
ten canonical checks, requests the peer review, publishes the single `ready`
`05-platform`, and performs canonical placement.

Phase I holds one continuously heartbeated platform-session lock established by
**hal-integrator**, covering `stage:scaffold-hal`, `global:hal-integration` and
one `path:` resource per mutable candidate or owned file. This slice joins that
already-authorized session; it does not acquire a second, conflicting lock.
Shared-session participation is procedural and unenforced in schema 1: no
fencing token is claimed and no multi-agent lease exists.

Generating a RAM-first link variant is a build-time configuration, not a
hardware authorization. This slice performs no flash, no load, no reset, no
probe attach and no target run. Hardware execution keeps its downstream owner.

## Inputs

Consume the current live `05-platform` — **not** `04-pac`. The predecessor of
this slice is the interrupt slice's `partial` platform handoff, and the
admission vocabulary is exactly that kind's field names:

| Admission concern | Consumed field |
|---|---|
| Status and progress | `handoff.status`, `handoff.can_progress`, `handoff.blockers`, `handoff.schema`, `handoff.stage` |
| Lineage | `handoff.inputs`, `handoff.notes`, `scope.revision`, `scope.decision` |
| Coverage | `coverage.complete`, `coverage.incomplete` |
| Evidence | `checks.id`, `checks.status`, `checks.evidence`, `checks.reason` |
| Crate and PAC identity | `platform.crate_manifest`, `platform.pac_manifest`, `platform.dependencies.crate`, `platform.dependencies.identity`, `platform.dependencies.features` |
| Startup contract | `platform.startup_clock_contract`, `platform.supporting_subsystems`, `platform.foundation_api` |
| Planning and citations | `platform.roadmap`, `platform.source_ids`, `platform.cited_notes` |
| First driver | `platform.first_driver`, `platform.first_driver_modes` |

Read separately, from coordinator-owned state, the documentation root, the
target identity, the Rust compilation target, the current scope revision and
decision, and the integration candidate root.

Read the cited hardware facts this slice depends on: the memory map with its
region origins and lengths, the vector table location and size, the reset and
boot entry assumptions, and any boot ROM or remap behavior. Every one of those
values comes from a cited manual section or table, or from the PAC, under
HAL-RULE-01 and HAL-RULE-02. **Never invent a memory region, an origin, a
length or a vector address.** A missing memory fact returns through
**hal-coordinator** to **hal-datasheet**; it is not estimated from a similar
part.

A `blocked` predecessor permits no consumption. A `partial` predecessor is the
normal case here and permits candidate work only.

## Outputs

- Candidate-only `memory.x` and `link*.x` under the integration candidate,
  derived entirely from cited memory facts.
- Candidate-only vector and runtime integration, runtime feature selection in
  the candidate manifest, and stack and heap placement.
- A separately named RAM-first link variant configuration, generated but not
  executed.
- Durable slice-local evidence under
  `halucinator/candidates/integration-<id>/evidence/runtime/`, including the
  linker map, the target-link log and the ELF inspection log.
- A fresh immutable snapshot of the consumed predecessor at
  `halucinator/candidates/integration-<id>/snapshots/05-platform-after-interrupts.toml`.
- A `partial` `halucinator/handoff/05-platform.toml`, and nothing stronger.
- Every slice-local FileRef returned to `scaffold-hal` for consolidation.

## Procedure

1. **Inspect and classify entry state.** Inspect the continuously held
   platform-session lock and every runtime and linker `path:` resource, and
   classify each as live, interrupted or ambiguous. Live means concurrency: do
   not interfere and do not recover. Ambiguous means wait one 30-second refresh
   interval, reread, and fail closed if it is still ambiguous. Interrupted, or
   ambiguous still unresolved after that reread, means recovery: do not mutate
   the suspect output, inventory and hash it into a recovery Markdown FileRef,
   compare it against the last valid handoff, and publish `partial` with empty
   blockers when unaffected fresh-candidate work remains or `blocked` with an
   `interrupted:scaffold-hal` blocker when it does not. Record the comparison,
   the disposition, the new candidate location and the resource recovery before
   an authorized actor removes the lock. Verify that every runtime and linker
   file this slice will read or write is named by a `path:` resource of the
   session before touching it. Resume only in a fresh candidate location, never
   as a canonical replacement in place.
2. **Validate before consumption.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading the live
   `05-platform`. Exit 0 with silent output is necessary; a missing interpreter,
   a timeout, a nonzero exit, or simply not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or an unrelated ambiguous
   lock surfaced by the all-kinds gate as a named blocker, never silently.
3. **Preserve the predecessor snapshot.** Preserve the validated live
   `05-platform` by copying its exact raw bytes to the fresh immutable path
   `halucinator/candidates/integration-<id>/snapshots/05-platform-after-interrupts.toml`,
   hash the snapshot, verify byte equality against the validated live singleton,
   and pin **that snapshot FileRef — not the live singleton path** — in
   `handoff.inputs`. Later replacement of the singleton cannot change snapshot
   bytes, which is exactly why the snapshot is what this slice cites.
4. **Load cited memory facts.** Load the exact snapshot leaves through the
   admission mapping above, then load the cited memory-map, vector, reset and
   boot facts with their manual section or table numbers, or their PAC paths.
   A region whose origin or length has no citation is a blocker, not a default.
5. **Record live linker and runtime references.** Record the live checkout's
   linker script conventions, runtime crate wiring, target configuration and
   build conventions that this integration must match, with the exact files and
   revisions read, and discharge `live-reference-read` from that record. A
   remembered convention is not a read reference.
6. **Compare foundation coverage.** Compare every required memory and runtime
   item — regions, sections, vector placement, stack and heap symbols, runtime
   feature set — against the cited facts and the PAC surface that must back it,
   and discharge `foundation-coverage` from the comparison log. Record an
   uncovered item as uncovered; do not narrow the requirement to match what was
   produced.
7. **Author candidate-only linker and runtime wiring.** Author `memory.x`, the
   linker section layout, the vector and runtime integration, the runtime
   feature selection and the stack and heap placement **only inside the
   integration candidate**. Every address, origin and length is transcribed from
   a cited fact. Perform no canonical placement here or anywhere in this skill.
8. **Generate candidate-only RAM-first configuration.** Generate the RAM-first
   link variant as a separately named candidate configuration alongside the
   default one, so the two are selectable and neither shadows the other.
   Generating it authorizes no device operation and is not evidence that any
   image was loaded or ran, under HAL-RULE-11.
9. **Run ELF inspection.** Run the image inspection over the linked candidate
   and record the entry point, the vector table placement, the load and run
   addresses, the emitted sections and their order, the stack and heap symbols,
   and the image bounds against each region, then discharge the slice-local
   `generated-mappings` from that log. Compare each observed address with the
   cited fact it should satisfy; a section that merely exists proves nothing
   about where it landed.
10. **Run slice-local software checks.** Run the repository-required formatting
    and lint checks over the runtime and linker integration and discharge
    `format-lint`; link the candidate for its advertised target and discharge
    `target-link` from the actual link log and map. Record `advertised-builds`,
    `build-only-ci` and `negative-chip-selection` as `unrun`, each with an
    evidence FileRef stating plainly that the complete-platform form of that
    check belongs to consolidation and why this slice cannot discharge it.
    Record `pure-host-tests` as `not-applicable` with a reason when this slice
    authored no pure value-to-value logic; a missing tool never makes a check
    inapplicable.
11. **Publish the final partial slice and validate it.** Publish only a
    `partial` `halucinator/handoff/05-platform.toml`, writing durable evidence
    and notes first and preserving the hashed snapshot and recovery record of
    the handoff that `state.toml` currently pins before replacing it, then run
    `python .opencode/schema/validate.py <repository-root> --kind all` again.
    Where referenced bytes legitimately changed on resumption, re-attest first:
    preserve the superseded evidence, create replacement evidence at a new path
    rather than overwriting one, and rerun only the affected checks. Never
    delete old evidence to regain validation. State is never updated before the
    handoff validates.
12. **Return the Phase I lock.** Return the platform implementation lock to the
    coordinator-held session after durable publication, so that the peer review
    happens with no platform lock held. Obtain no independent review here:
    `independent-review` stays `unrun` with its pending evidence FileRef,
    because only the consolidator requests it. When it is eventually requested,
    only review.verdict=ready accepts; ready-with-fixes and not-ready do not.
    Perform no canonical placement on the way out.
13. **Return to final consolidation.** Return every slice-local FileRef — the
    snapshot, the evidence logs, the candidate linker and runtime files and the
    published `partial` handoff — to `scaffold-hal`, which alone creates the
    consolidated attestation for all ten canonical checks, obtains the review,
    publishes the sole `ready` `05-platform` and performs canonical placement.
    State that no canonical byte moved and no hardware operation was performed.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `advertised-builds` | Record that complete-platform builds remain pending consolidation | `halucinator/candidates/integration-<id>/evidence/runtime/advertised-builds-pending.md` |
| `build-only-ci` | Record that complete-platform CI remains pending consolidation | `halucinator/candidates/integration-<id>/evidence/runtime/build-only-ci-pending.md` |
| `format-lint` | Run formatting and lint checks over runtime/linker integration | `halucinator/candidates/integration-<id>/evidence/runtime/format-lint.log` |
| `foundation-coverage` | Compare memory/runtime requirements with cited facts and PAC coverage | `halucinator/candidates/integration-<id>/evidence/runtime/foundation-coverage.log` |
| `generated-mappings` | Inspect ELF vectors, sections, addresses, stack and heap symbols | `halucinator/candidates/integration-<id>/evidence/runtime/elf-sections.log` |
| `independent-review` | Record that review belongs only to final consolidation | `halucinator/candidates/integration-<id>/evidence/runtime/review-pending.md` |
| `live-reference-read` | Record live runtime/linker references read | `halucinator/candidates/integration-<id>/evidence/runtime/live-references.md` |
| `negative-chip-selection` | Record that complete feature negatives remain pending consolidation | `halucinator/candidates/integration-<id>/evidence/runtime/negative-selection-pending.md` |
| `pure-host-tests` | Record why no new pure host logic was authored | `reason (no evidence FileRef)` |
| `target-link` | Build the candidate link and inspect its actual ELF image | `halucinator/candidates/integration-<id>/evidence/runtime/target-link.log` |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove that an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. The shared
platform-session lock is the same kind of procedural discipline, not
enforcement. Typed evidence hashes freshness, not relevance: a reviewer still
has to judge whether an ELF log discharges the address it is attached to.

Snapshot semantics are inherited, not independently parsed. The live singleton
is validated immediately before byte-identical snapshotting, and later
validation hashes the snapshot for freshness; `validate.py` does not discover
candidate snapshots as handoffs and does not reparse them as a kind. That
limitation is disclosed here rather than hidden behind the word "validated".
Nothing in schema 1 transitively invalidates a linker layout when a memory fact
later changes; currency is procedural.

When a required tool, target, formatter, schema, linker utility, probe, runner
or reviewer is unavailable, record the attempted command, discovered identity,
failure output, affected check and exact remedy in a new hashed evidence
FileRef. Leave the affected check `unrun`; never mark it `not-applicable`. Ask
the user to install or expose the named capability, provide an approved existing
path/runner, or request a coordinator-owned scope decision; the agent does not
install tools. Publish `partial` with `can_progress=true` and empty blockers
when unaffected work remains, using truthful coverage: `coverage.incomplete` may
remain empty when the `unrun` check alone makes the handoff partial. Publish
`blocked` with `can_progress=false` and a named `environment:<capability>`
blocker when no scoped work can continue. On resumption, rerun entry-state
classification and the `--kind all` gate, verify the supplied identity, create
replacement evidence at a fresh path, rerun affected checks and re-attest.

## Exit criteria

### ready

Predicate: unreachable for this skill. Even if `coverage.incomplete` were empty,
`handoff.blockers` empty and every applicable check `passed`, this non-final
slice must return to `scaffold-hal`; it must not publish `ready`, because only
the final consolidator creates the composite evidence and holds the accepting
review that a `ready` platform asserts.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and at
least one applicable complete-platform check is `unrun` or `failed`;
`coverage.incomplete` may truthfully be empty or nonempty. This is the only
status this slice publishes on a successful run.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names an external fact, tool, access or decision
action that only somebody outside this slice can take.

## Application example

The emitted handoff for the third platform slice of a fictional part, after the
candidate linked and its ELF was inspected:

```toml
[handoff]
schema = 1
stage = "scaffold-hal"
status = "partial"
can_progress = true
inputs = [
  { path = "halucinator/candidates/integration-001/snapshots/05-platform-after-interrupts.toml", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" }

[coverage]
complete = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]
incomplete = []

[platform]
crate_manifest = { path = "halucinator/candidates/integration-001/Cargo.toml", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" }
roadmap = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ROADMAP.md", sha256 = "5555555555555555555555555555555555555555555555555555555555555555" }
startup_clock_contract = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" }
supporting_subsystems = ["foundation:init-api", "foundation:interrupt-metadata"]
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
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/live-references.md", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }

[[checks]]
id = "foundation-coverage"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/foundation-coverage.log", sha256 = "9999999999999999999999999999999999999999999999999999999999999999" }

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/format-lint.log", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

[[checks]]
id = "advertised-builds"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/advertised-builds-pending.md", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }

[[checks]]
id = "negative-chip-selection"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/negative-selection-pending.md", sha256 = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" }

[[checks]]
id = "pure-host-tests"
status = "not-applicable"
reason = "This runtime/linker integration slice introduces no pure value-to-value logic."

[[checks]]
id = "generated-mappings"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/elf-sections.log", sha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }

[[checks]]
id = "target-link"
status = "passed"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/target-link.log", sha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" }

[[checks]]
id = "build-only-ci"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/build-only-ci-pending.md", sha256 = "ffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff" }

[[checks]]
id = "independent-review"
status = "unrun"
evidence = { path = "halucinator/candidates/integration-001/evidence/runtime/review-pending.md", sha256 = "1212121212121212121212121212121212121212121212121212121212121212" }
```

The paths are fictional and the hashes are placeholders: this is a schema-shape
example, not evidence. A fact nobody established is an absent key or an empty
collection, never a sentinel word.

## Quick reference

| Element | Value |
|---|---|
| Stage | `scaffold-hal`, third and last platform slice |
| Emitter | `hal-integrator` |
| Emitted handoff | `halucinator/handoff/05-platform.toml`, kind `05-platform`, `partial` only |
| Consumes | the live `05-platform`, pinned as an immutable candidate snapshot, never `04-pac` |
| Snapshot | `halucinator/candidates/integration-<id>/snapshots/05-platform-after-interrupts.toml`, hashed and byte-verified |
| Mutation scope | candidate-only; canonical placement belongs solely to final consolidation |
| Checks | `advertised-builds`, `build-only-ci`, `format-lint`, `foundation-coverage`, `generated-mappings`, `independent-review`, `live-reference-read`, `negative-chip-selection`, `pure-host-tests`, `target-link` |
| Discharged here | `live-reference-read`, `foundation-coverage`, `format-lint`, `generated-mappings`, `target-link` |
| Pending consolidation | `advertised-builds`, `build-only-ci`, `negative-chip-selection`, `independent-review` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after the handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Ready | unreachable here; only `scaffold-hal` may publish a `ready` platform |
| Routing | every question, review request, scope change and dispatch returns to `hal-coordinator` |

## Common mistakes

- **Publishing `ready` because the candidate links.** A linked candidate is one
  slice's result. The `ready` platform asserts composite evidence and an
  accepting review that only `scaffold-hal` ever holds and this slice never
  held, so a `ready` here is a claim about work nobody did.
- **Performing canonical placement "since everything passed".** It is the exact
  failure the two-phase design exists to prevent. Candidate-only means
  candidate-only at every status.
- **Pinning the live singleton path in `handoff.inputs`.** The singleton is
  replaced by this slice's own publication, so the citation would end up
  describing the successor rather than the predecessor. Pin the snapshot.
- **Snapshotting without verifying byte equality.** An unverified copy inherits
  none of the predecessor's validation, and the inheritance is the only thing
  that makes the snapshot admissible.
- **Treating `cargo build` exit zero as `target-link`.** It is not. The check is
  discharged by inspecting the produced image: entry point, vector placement,
  load and run addresses, sections, stack and heap symbols, and bounds.
- **Inventing a region origin or length to make the link succeed.** A linker
  script that links is not a linker script that is correct, and the invented
  number survives into every downstream image. Return the missing memory fact
  through `hal-coordinator`.
- **Calling the RAM-first variant a hardware result.** Generating an image is
  not loading it and not running it. Say what was built and what was not run.
- **Marking a pending check `not-applicable`.** `advertised-builds`,
  `build-only-ci` and `negative-chip-selection` are applicable at the complete
  platform; here they are `unrun` with evidence saying so.
- **Editing the clock modules while "already in there".** They belong to
  `hal-driver`, and a second writer is how two owners disagree about one file.
- **Describing the session lock or the validator wiring as enforcement.** Both
  are honor systems, and saying otherwise makes every reader trust an
  attestation nobody made.
