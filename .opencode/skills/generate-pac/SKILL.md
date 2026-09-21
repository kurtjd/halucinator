---
name: generate-pac
description: >-
  Use when a ready `03-svd` preparation handoff exists and a Rust peripheral
  access crate must be generated, regenerated or repaired for one exact MCU, or
  when an earlier `04-pac` stopped at partial or blocked. Dispatch and search
  terms: PAC generator setup, metapac assembly, shared peripheral blocks, chip
  metadata, Cargo chip feature, runtime and metadata features, generation
  replay, final-path build, 04-pac handoff. Wrong for preparing or correcting
  SVDs, extracting hardware facts, implementing HAL drivers, scaffolding the
  HAL crate, or publishing a crate.
compatibility: opencode
---

# Generate PAC

```halucinator-skill-contract
stage: generate-pac
participants: hal-svd
emitter: hal-svd
emits: 04-pac|halucinator/handoff/04-pac.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,pac.cargo_chip_feature,pac.cited_notes,pac.crate_manifest,pac.foundation.evidence,pac.foundation.id,pac.foundation.kind,pac.foundation.location,pac.foundation.status,pac.metadata_features,pac.package,pac.revision.kind,pac.revision.value,pac.runtime_features,pac.rust_compilation_target,pac.source_ids,pac.temporary_fork,scope.decision,scope.revision
checks: expected-inventory,final-path-build,format-lint,generation-replay,host-metadata-api,independent-review,input-identity,negative-chip-selection,pure-host-tests,representation-limits,target-build-api
consumes: 03-svd|handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,checks.id,checks.status,checks.evidence,checks.reason,svd.route,svd.source,svd.transforms,svd.includes,svd.prepared_manifest,svd.extraction_mode,svd.namespace_mode,svd.representation_limits,svd.unresolved_facts
writes: hal-svd|pac-handoff
writes: hal-svd|pac-project
writes: hal-svd|svd-pac-notes
supplies-delta: hal-svd|sources-catalog
```

This stage produces a usable, reproducible, independently reviewed PAC for the
declared scope — not merely emitted Rust files.

## When to use

Use this skill when **hal-coordinator** dispatches `generate-pac` against a
`03-svd` handoff that validates and is `ready`, or when a previous run left
`04-pac` at `partial` or `blocked` and the recorded next action is now possible.

Start from one exact MCU and core and the coordinator-approved functionality,
dependencies and exclusions. Prefer shared peripheral-IP definitions plus
per-chip metadata for new work; a reusable structure is not family-wide support.

Read [Generation and Checks](./references/generation-and-checks.md) before
selecting any command, metadata structure or output path.

## Ownership and boundaries

The owning agent is **hal-svd**. It materializes three ownership classes:
`pac-project`, the generator, metadata, candidate and replay runs and the
canonical crate under the selected PAC project; `svd-pac-notes`, the generation
record; and `pac-handoff`, the deterministic
`halucinator/handoff/04-pac.toml`.

The first entry of `handoff.notes` is the generation record at the exact
deterministic path `<documentation>/notes/PAC.md`, resolved against the
documentation root recorded in state. That path is fixed by
[`04-pac.md`](../../schema/04-pac.md) and is the same path on every run.

`SOURCES.md` is class `sources-catalog` and is owned by **hal-integrator**.
This skill authors the catalog delta that registers the stable generator and
crate locations; **hal-coordinator** dispatches **hal-integrator** to
materialize it and returns its FileRef.

Never hand-edit generated Rust or extracted YAML. Fix the authoritative source
input, the metadata or the generator template and regenerate. A register
description change returns to `generate-svd`; a missing hardware meaning returns
through **hal-coordinator** to **hal-datasheet**. Every question, review request,
scope change and next-stage dispatch routes through **hal-coordinator**.

Do not extract PDFs, install or upgrade tools automatically, commit, publish,
flash, or run target code. Target-link smoke binaries and bench work keep their
downstream owners.

## Inputs

Consume the validated, `ready` `03-svd` leaves declared in the contract. The
admission vocabulary is exactly the producer's field names — there is no
separate prose taxonomy and no `Consumers` pseudo-field:

| Admission concern | Consumed field |
|---|---|
| Route | `svd.route` |
| Source | `svd.source` |
| Recipe | `svd.transforms`, `svd.includes`, `svd.extraction_mode`, `svd.namespace_mode` |
| Prepared output | `svd.prepared_manifest` |
| Representation limits | `svd.representation_limits` |
| Unresolved facts | `svd.unresolved_facts` |
| Evidence | `checks.*` — every canonical `03-svd` check with its status, evidence and reason |
| Lineage | `handoff.inputs`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

Consumer requirements are **not** in `03-svd`. Read them separately from
coordinator-owned state: `decisions.cargo_chip_feature`,
`decisions.rust_compilation_target`, `decisions.destination_crate`,
`decisions.foundation_requirements`, the `target.*` identity,
`scope.current_revision` and `scope.current_decision`, and the
`roots.pac_project`, `roots.svd_inputs`, `roots.generator`, `roots.pac_crate`
and `roots.documentation` paths.

A `blocked` predecessor permits no consumption. A `partial` one permits
read-only inspection and disposable fresh-candidate work only: no canonical
crate replacement and no downstream `ready`. Missing or stale required admission
evidence is a blocker returned to **hal-coordinator**, never a reason to infer
registers from emitted Rust.

## Outputs

- Durable generator, setup-template and metadata inputs under the selected PAC
  project.
- Isolated `candidate/` and `replay/` run output, and, after every gate passes,
  the canonical crate at the selected path.
- The generation record at `<documentation>/notes/PAC.md`.
- A `SOURCES.md` delta authored here and materialized by **hal-integrator**.
- `halucinator/handoff/04-pac.toml`, carrying `pac.crate_manifest`,
  `pac.package`, the tagged `pac.revision`, `pac.cargo_chip_feature`,
  `pac.runtime_features`, `pac.metadata_features`,
  `pac.rust_compilation_target`, `pac.source_ids`, `pac.cited_notes`,
  `pac.temporary_fork`, the `[[pac.foundation]]` partition, the eleven canonical
  checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering this stage
   and the PAC-integration and catalog resources, and classify each as live,
   interrupted or ambiguous. Live means concurrency: do not interfere. Ambiguous
   means wait one 30-second refresh interval, reread, and fail closed if it is
   still ambiguous. Interrupted, or ambiguous still unresolved, means recovery:
   do not mutate the suspect output, inventory and hash it into a recovery
   Markdown FileRef, compare it against the last valid handoff, and publish
   `partial` with empty blockers when unaffected fresh candidate work remains or
   `blocked` with an `interrupted:generate-pac` blocker when it does not. Record
   the comparison, the disposition and the new candidate location before an
   authorized actor removes the lock. Resume only in a fresh candidate or replay
   run, never in place.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `03-svd`. Exit 0
   with silent output is necessary; a missing interpreter, a timeout, a nonzero
   exit, or not running it is not a pass and blocks consumption. Report an
   unrelated stale artifact or ambiguous lock as a named blocker.
3. **Load the predecessor and the coordinator decisions.** Load the exact
   `03-svd` leaves through the admission mapping above, and separately load the
   coordinator-owned decisions, foundation requirements and roots listed under
   Inputs.
4. **Compare every admission field against its evidence.** Compare each consumed
   field with the record and evidence it names, and discharge `input-identity`
   from the resulting identity log: hashes of the original or authored SVD, the
   ordered transforms and includes, the modes, the tool identity, the generator
   code, the packaging templates and the dependency resolution. A Git HEAD or a
   version banner alone does not identify bytes.
5. **Select the run and crate locations.** Select the next unused
   `derived/pac/<target-id>/<run-id>/` with separate `candidate/` and `replay/`
   directories, and check the full write and delete footprint before any
   command. Candidate, replay and canonical outputs must not overlap or sit
   inside one another's cleanup directories.
6. **Author the expected inventory before generating.** Author the expected
   device, register, field, interrupt and metadata inventory from the checked
   preparation and the cited consumer requirements, independently of the
   generator's own success list. This is written **before** generation so that
   the comparison is not a restatement of the output.
7. **Generate the candidate crate.** Generate into the fresh isolated candidate
   through the recorded generator and setup process, preserving all diagnostics
   and the live crate. A zero exit status is not completeness evidence.
8. **Compare expected against generated.** Compare the authored expectation
   with the emitted Rust and the exported chip metadata over an explicitly
   enumerated nonempty file set, and discharge `expected-inventory` from that
   comparison. A metadata entry without an address or a valid block link is not
   an implemented peripheral, and a few successful compilation probes do not
   replace the inventory comparison.
9. **Record the representation limits and their consumer impact.** Record every
   source-only fact the selected representation cannot carry, carry forward
   `svd.representation_limits`, and discharge `representation-limits` with an
   explicit result even when no relevant omission exists. Do not claim that a
   generated setter enforces write-once or write-one-to-clear behavior because
   it compiles.
10. **Build every advertised target configuration.** Build the candidate for
    each advertised in-scope target and runtime feature set and compile focused
    probes over the required public register and interrupt APIs, discharging
    `target-build-api`.
11. **Build the host metadata configuration.** Build the host-only metadata
    configuration and compile a probe over the required public metadata
    interface, discharging `host-metadata-api`, using the host triple from the
    selected compiler's `rustc -vV`. Record it `not-applicable` with a reason
    only when `pac.metadata_features` is empty.
12. **Run the chip-selection negative checks.** Run the missing and incompatible
    chip-selection cases against the actual feature policy and verify the
    intended diagnostic, discharging `negative-chip-selection`. An unrelated
    build error or a missing tool is not a passing negative test.
13. **Run the host tests and the repository lint policy.** Run the pure host
    tests over authored layout, encoding and configuration logic and discharge
    `pure-host-tests`, or record it `not-applicable` with a reason the reviewer
    audits. Run the repository-required formatting and lint checks for every
    touched surface and discharge `format-lint`. A missing tool or permission
    leaves a check `unrun`; it does not make it inapplicable.
14. **Run the generation replay.** Replay the complete
    recorded pipeline from the same durable inputs into a second unused
    directory, never from the candidate Rust, compare the complete inventory and
    the file contents, and discharge `generation-replay`. Any inventory or byte
    difference fails replay even with a known cause; fix determinism at the
    generator, input or tool boundary and rerun.
15. **Publish the verified crate and rebuild at the final path.** Materialize
    only owned output at the canonical crate path after every candidate check and
    the replay pass, compare the live destination with its recorded pre-run
    state first, then rerun the location-sensitive consumer builds there and
    discharge `final-path-build`. A failed candidate must never replace a
    previously verified crate, and an unresolved ownership conflict blocks
    integration.
16. **Author the generation record and the catalog delta.** Author the record at
    `<documentation>/notes/PAC.md` using the reference's
    [record and handoff fields](./references/generation-and-checks.md#generation-record-and-handoff),
    then request through **hal-coordinator** that **hal-integrator** materialize
    the `SOURCES.md` delta and return its FileRef.
17. **Publish the preliminary handoff, validate it, and obtain the review.**
    Publish the preliminary `04-pac`, preserving a hashed snapshot and recovery
    record of any deterministic handoff `state.toml` currently pins before
    replacing it, run
    `python .opencode/schema/validate.py <repository-root> --kind all` again,
    then request through **hal-coordinator** the independent **hal-reviewer**
    review over `pac.crate_manifest`, and discharge `independent-review` from the
    accepting verdict. Only review.verdict=ready accepts; ready-with-fixes and
    not-ready do not.
18. **Re-attest, publish the final handoff, and run the final gate.** Re-attest
    where referenced bytes changed — preserve the superseded evidence and review
    records, create replacement evidence at a new path rather than overwriting
    one, rerun only the affected checks, and obtain a new review where the
    reviewed bytes changed — then publish the final
    `halucinator/handoff/04-pac.toml`, run `python .opencode/schema/validate.py <repository-root> --kind all` over it, let **hal-coordinator**
    update `state.toml` through the compare-and-swap sequence, run the final
    `--kind all` gate, and return the record path, status and next action. State
    that no HAL implementation, publication or hardware operation was performed.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `expected-inventory` | Compare the independently authored expectation with the emitted Rust and exported metadata | `derived/pac/<target-id>/<run-id>/candidate/expected-inventory.log` |
| `final-path-build` | Build the location-sensitive consumer configurations at the canonical crate path | `derived/pac/<target-id>/<run-id>/candidate/final-path-build.log` |
| `format-lint` | Run the repository-required formatting and lint checks for the touched surfaces | `derived/pac/<target-id>/<run-id>/candidate/format-lint.log` |
| `generation-replay` | Run the replay from the durable inputs into a second unused directory and compare inventory and bytes | `derived/pac/<target-id>/<run-id>/replay/replay-diff.log` |
| `host-metadata-api` | Build the host metadata configuration and compile the metadata-interface probe | `derived/pac/<target-id>/<run-id>/candidate/host-metadata-api.log`, or `reason (no evidence FileRef)` when `pac.metadata_features` is empty |
| `independent-review` | Request the coordinator-dispatched review over `pac.crate_manifest` and record its accepting verdict | `halucinator/handoff/08-review-pac-crate.toml` |
| `input-identity` | Validate the predecessor handoff and compare every admission field with its hashed evidence | `derived/pac/<target-id>/<run-id>/candidate/identity.log` |
| `negative-chip-selection` | Run the missing and incompatible chip-selection cases and verify the intended diagnostic | `derived/pac/<target-id>/<run-id>/candidate/negative-chip-selection.log` |
| `pure-host-tests` | Run the host tests over authored layout, encoding and configuration logic | `derived/pac/<target-id>/<run-id>/candidate/pure-host-tests.log`, or `reason (no evidence FileRef)` when no such logic was authored |
| `representation-limits` | Record every source-only fact and its consumer impact | `<documentation>/notes/PAC.md` representation-limit section, captured as a FileRef |
| `target-build-api` | Build every advertised in-scope target configuration and compile the register and interrupt probes | `derived/pac/<target-id>/<run-id>/candidate/target-build-api.log` |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. Typed evidence hashes
freshness, not relevance: it does not prove that a command received a nonempty
file set, that a replay used durable inputs, or that an artifact discharges the
check it is attached to. The reference's anti-vacuity and run-discipline rules
therefore remain normative.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
the consumed `03-svd` is `ready` against the current `scope.revision` and
`scope.decision`, `pac.temporary_fork` is `false`, the `[[pac.foundation]]`
entries exactly partition the coordinator-owned foundation requirements and
every entry's `status` is `covered`, every applicable check is `passed`, and the
independent review accepted. Only review.verdict=ready accepts;
ready-with-fixes and not-ready do not.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Only fresh disposable candidate work continues; a failed candidate
never replaces the verified crate, and partial output is not a narrower
completed scope.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names an external evidence, tool, access or
decision action that only somebody outside this stage can take.

## Application example

The emitted handoff for a bounded single-peripheral crate with a metadata
consumer:

```toml
[handoff]
schema = 2
stage = "generate-pac"
status = "ready"
inputs = [
  { path = "halucinator/handoff/03-svd.toml", sha256 = "3c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e" }

[coverage]
complete = ["foundation:init-api", "peripheral:schema-demo"]
incomplete = []

[pac]
crate_manifest = { path = "halucinator/pac/unobtainium/unobtainium-pac/Cargo.toml", sha256 = "91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80" }
package = "unobtainium-pac"
cargo_chip_feature = "uc-not-a-real-mcu-0001"
runtime_features = ["rt"]
metadata_features = ["metadata"]
rust_compilation_target = "thumbv8m.main-none-eabihf"
source_ids = ["doc-001", "doc-002"]
cited_notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" },
]
temporary_fork = false

[pac.revision]
kind = "workspace"

[[pac.foundation]]
id = "foundation:init-api"
kind = "api"
location = "unobtainium_pac::SCHEMADEMO"
status = "covered"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/expected-inventory.log", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }

[[checks]]
id = "input-identity"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/identity.log", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }

[[checks]]
id = "expected-inventory"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/expected-inventory.log", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }

[[checks]]
id = "representation-limits"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" }

[[checks]]
id = "target-build-api"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/target-build-api.log", sha256 = "d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4" }

[[checks]]
id = "host-metadata-api"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/host-metadata-api.log", sha256 = "e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5" }

[[checks]]
id = "negative-chip-selection"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/negative-chip-selection.log", sha256 = "f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6" }

[[checks]]
id = "pure-host-tests"
status = "not-applicable"
reason = "The generator emits no authored layout or encoding logic for this scope; every value type is produced by the pinned chiptool backend."

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/format-lint.log", sha256 = "08192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7" }

[[checks]]
id = "generation-replay"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/replay/replay-diff.log", sha256 = "192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }

[[checks]]
id = "final-path-build"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/pac/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/candidate/final-path-build.log", sha256 = "2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f70819" }

[[checks]]
id = "independent-review"
status = "passed"
evidence = { path = "halucinator/handoff/08-review-pac-crate.toml", sha256 = "3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a" }
```

`pac.revision` is a tagged table: `{ kind = "workspace" }` for a workspace-
inherited version, or `{ kind = "revision", value = "0.1.0" }`. A fact nobody
established is an absent key or an empty collection, never a sentinel word.

## Quick reference

| Element | Value |
|---|---|
| Stage | `generate-pac` |
| Emitter | `hal-svd` |
| Emitted handoff | `halucinator/handoff/04-pac.toml`, kind `04-pac` |
| First note | exactly `<documentation>/notes/PAC.md` |
| Consumes | `03-svd` only; consumer requirements come from coordinator-owned state |
| Checks | `expected-inventory`, `final-path-build`, `format-lint`, `generation-replay`, `host-metadata-api`, `independent-review`, `input-identity`, `negative-chip-selection`, `pure-host-tests`, `representation-limits`, `target-build-api` |
| Catalog | `SOURCES.md`, class `sources-catalog`, owned by `hal-integrator`; this skill supplies the delta |
| Routing | every question, review request, scope change and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, `temporary_fork` false, foundation fully covered, applicable checks `passed`, accepting review |

## Common mistakes

- **Inventing an admission taxonomy.** The admission vocabulary is the producer's
  field names. A row named `Consumers` describes no field anybody publishes, and
  a consumer that quotes a heading the producer never wrote cannot detect that
  the producer omitted it.
- **Reading consumer requirements out of `03-svd`.** They were deliberately
  removed from that kind. They live in coordinator-owned state.
- **Treating the record path as a convention.** The first note is exactly
  `<documentation>/notes/PAC.md`. A soft alternative makes the most load-bearing
  artifact in the stage discoverable only by reading prose.
- **Replaying from the candidate Rust.** Replay proves determinism from durable
  inputs. Feeding it the candidate proves the candidate equals itself.
- **Letting a failed candidate reach the canonical path.** It silently replaces
  a verified crate with an unverified one, and the next stage cannot tell.
- **Quoting only the rejecting verdict.** Stating what does not accept, without
  stating what does, turns the gate into advice. Use the exact sentence.
- **Hand-editing generated Rust to pass a check.** The defect is in the input,
  the metadata or the generator. The edit is erased by the next regeneration and
  invalidates the replay in the meantime.
- **Calling a missing tool an inapplicable check.** It is `unrun`, which blocks
  readiness.
- **Claiming `cargo check` proves the target links or the vectors execute.** It
  does not. That evidence belongs to the source-blind tester downstream.
