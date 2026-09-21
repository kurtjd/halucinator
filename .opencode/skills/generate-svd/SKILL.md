---
name: generate-svd
description: >-
  Use when a ready `01-sources` handoff exists and the register description for
  one exact MCU must be reviewed, normalized or authored before a PAC can be
  generated, or when an earlier `03-svd` stopped at partial or blocked. Dispatch
  and search terms: vendor SVD review, CMSIS-SVD authoring, chiptool transforms,
  extraction mode, namespaces, structural inventory, representation limits,
  preparation replay, 03-svd handoff. Wrong for gathering documentation,
  extracting cited hardware facts, emitting Rust, assembling metapac metadata,
  or scaffolding a HAL crate.
compatibility: opencode
---

# Generate SVD

```halucinator-skill-contract
stage: generate-svd
participants: hal-svd
emitter: hal-svd
emits: 03-svd|halucinator/handoff/03-svd.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,svd.extraction_mode,svd.includes,svd.namespace_mode,svd.prepared_manifest,svd.representation_limits,svd.route,svd.source,svd.transforms,svd.unresolved_facts
checks: correction-effects,information-limits,input-identity,preparation-replay,schema-validation,source-fact-comparison,structural-inventory,xml-well-formed
consumes: 01-sources|handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,sources.catalog,sources.route,sources.cited_notes,sources.documents.source_id,sources.documents.document,sources.documents.revision,sources.documents.format,sources.documents.source
consumes: 02-facts|handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,facts.notes,facts.citations.source_id,facts.citations.note,facts.categories,facts.contradictions,facts.citations.assertion_id,facts.citations.scope_item,facts.citations.claim,facts.citations.source,facts.citations.location.kind,facts.citations.location.page,facts.citations.location.line_start,facts.citations.location.line_end,facts.citations.locator.kind,facts.citations.locator.value,facts.citations.excerpt
writes: hal-svd|pac-project
writes: hal-svd|svd-handoff
writes: hal-svd|svd-pac-notes
supplies-delta: hal-svd|sources-catalog
```

This stage ends with checked register-description inputs and a reproducible
typed handoff. It does not produce Rust, and it does not produce hardware facts.

## When to use

Use this skill when **hal-coordinator** dispatches `generate-svd` for a target
whose `01-sources` handoff validates, or when a previous run left `03-svd` at
`partial` or `blocked` and the recorded next action is now possible.

A supplied vendor SVD changes the starting point; it does not skip review.
Review or author only the exact part, core and peripheral scope supplied for
this run, and report partial coverage as partial rather than as whole-chip
support.

## Ownership and boundaries

The owning agent is **hal-svd**. It materializes three ownership classes:
`pac-project`, the durable SVD inputs and transforms plus the derived run
directories under the selected PAC project; `svd-pac-notes`, the preparation
record; and `svd-handoff`, the deterministic
`halucinator/handoff/03-svd.toml`.

The first entry of `handoff.notes` is the preparation record at the exact
deterministic path `<documentation>/notes/SVD.md`, resolved against the
documentation root recorded in state. That path is fixed by
[`03-svd.md`](../../schema/03-svd.md) and is the same path on every run of every
target.

`SOURCES.md` is class `sources-catalog` and is owned by **hal-integrator**.
This skill authors the catalog delta that registers the stable project and SVD
input locations; **hal-coordinator** dispatches **hal-integrator** to
materialize it and returns its FileRef.

**hal-svd is not a facts producer.** If new hardware assertions must be
extracted from a manual, return to **hal-coordinator** and name the missing
facts. Do not attempt direct delegation, and do not read a register value out
of a vendor file and call it a cited finding. Every question, review request,
gate and next-stage dispatch routes through **hal-coordinator**.

Do not install tools, extract PDFs, configure hardware, flash, run target code,
emit Rust, set Cargo features, or assemble metapac metadata.

## Inputs

Always consume the validated `01-sources` leaves declared in the contract:
`handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`,
`scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete`,
`sources.catalog`, `sources.route`, `sources.documents` (each entry binding a
`source_id` to a `document` title, `revision`, `format` and a hash-pinned
`source`) and `sources.cited_notes`. Also read coordinator-owned state: the `target.*`
identity, `scope.current_revision`, `scope.current_decision`, and
`roots.documentation`, `roots.sources`, `roots.pac_project` and
`roots.svd_inputs`.

On the **`author-from-docs`** route additionally consume the validated
`02-facts` leaves declared in the contract. That handoff is produced by
`extract-hardware-facts`, the sole `02-facts` emitter, run by **hal-datasheet**
under its own typed gate. Validate it as step 2 requires, then admit it when it
is `ready`.

Block only for a reason the evidence actually shows: a `blocked` `02-facts`
predecessor, which permits no consumption; a `02-facts` whose `facts.categories`
do not cover the register, field, encoding, access, reset or interrupt scope
this run must represent; or unresolved entries in `facts.contradictions` that
bear on that scope. Record the named blocker, return it to **hal-coordinator**,
and stop. A `partial` `02-facts` permits read-only inspection and disposable
fresh-candidate work only. Never block on the ground that no producer exists —
one does. Do not synthesize facts, and do not relabel the route to get past the
gate.

On the **`review-supplied`** route the run may start from accepted cited notes
alone, but accessibility is never applicability. The `input-identity` evidence
must identify the accessible SVD through its `sources.documents` entry, which
binds that source ID to the exact hash-pinned file, so an unsuitable-but-accessible file cannot be
quietly relabelled. A coordinator-dispatched independent review of the route's
applicability is required procedurally before any downstream admission; it is
recorded as a hashed note and a `handoff.inputs` dependency, not as an invented
check or field. Mechanical citation-truth checking is not available and is not
claimed.

On the **`unresolved`** route nothing is admitted.

Read [Preparation and Checks](./references/preparation-and-checks.md) before
choosing any command, and
[the common handoff contract](../../schema/handoff-common.md) for the status
rules restated below.

## Outputs

- Durable SVD inputs under the selected PAC project: the original or authored
  SVD, ordered transforms and their includes.
- Fresh derived `baseline/`, `prepared/` and `replay/` run output.
- The preparation record at `<documentation>/notes/SVD.md`.
- A `SOURCES.md` delta authored here and materialized by **hal-integrator**.
- `halucinator/handoff/03-svd.toml`, carrying `svd.route`, `svd.source`, the
  ordered `svd.transforms` and `svd.includes`, `svd.prepared_manifest`,
  `svd.extraction_mode`, `svd.namespace_mode`, `svd.representation_limits`,
  `svd.unresolved_facts`, the eight canonical checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering this stage
   and its run and catalog resources, and classify each as live, interrupted or
   ambiguous. Live means concurrency: do not interfere. Ambiguous means wait one
   30-second refresh interval, reread, and fail closed if it is still ambiguous.
   Interrupted, or ambiguous still unresolved, means recovery: do not mutate the
   suspect output, inventory and hash it into a recovery Markdown FileRef,
   compare it against the last valid handoff, and publish `partial` with empty
   blockers when unaffected fresh derived work remains or `blocked` with an
   `interrupted:generate-svd` blocker when it does not. Record the comparison,
   the disposition and the new run location before an authorized actor removes
   the lock. Resume only in a fresh run directory, never in place.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `01-sources` or
   `02-facts`. Exit 0 with silent output is necessary; a missing interpreter, a
   timeout, a nonzero exit, or not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or ambiguous lock as a named
   blocker rather than stepping over it.
3. **Load the predecessor handoff and state.** Load the exact `01-sources`
   leaves and, on the author route, the exact `02-facts` leaves. A `blocked`
   predecessor permits no consumption; a `partial` one permits read-only
   inspection and disposable fresh-candidate work only. Carry the upstream
   status, blockers and incomplete coverage forward.
4. **Select the route and record its evidence.** Select `svd.route` equal to
   the upstream `sources.route` where that route is not `unresolved`, and
   discharge `input-identity` from evidence that names the exact SVD FileRef and
   its source ID, the hashes of every durable input, and, on the supplied route,
   the coordinator-dispatched applicability review. Changed bytes require a new
   source record and invalidate the dependent checks.
5. **Select the artifact and run locations.** Select the PAC project, the
   `data/svd/<target-id>/` input root and the next unused derived run directory
   exactly as the reference specifies. A supplied SVD is an input, not
   permission to write beside it.
6. **Validate the source XML against a schema.** Validate the original or
   authored XML with structured tooling and a trusted local CMSIS-SVD schema
   matching its declared version, discharging `xml-well-formed` and
   `schema-validation` separately. A missing schema or validator is an `unrun`
   check, not a pass.
7. **Compare the description against the cited findings.** Compare effective
   register properties — after inheritance, arrays and aliases are resolved —
   against the cited findings, and discharge `source-fact-comparison` from that
   record. Parser defaults are not hardware evidence, and a vendor-only value
   stays vendor-only until checked.
8. **Author only what the citations support.** Author CMSIS-SVD XML for the
   declared scope when no suitable SVD exists, using the matching schema and
   representing only supported device, peripheral, register, field, encoding,
   access, reset and interrupt facts. Omit an unsupported non-required property
   and record the gap; stop the affected scope rather than inserting a plausible
   required value. Never copy another chip's CPU or memory map.
9. **Record the corrections and prove their effects.** Record each necessary
   correction as a cited chiptool transform with its source ID, document
   revision and section, apply the ordered corrections from the original input
   into a separate prepared output, and discharge `correction-effects` from the
   expected-versus-observed match record. Record it `not-applicable` with a
   reason only when there are zero transforms. An unexpected match, a missing
   match or a missing intended effect fails the check even when the tool exits
   successfully.
10. **Run the structural checks on an explicit nonempty set.** Run the
    reference's inventory and structural checks over an explicitly enumerated,
    nonempty file set and discharge `structural-inventory` from the result. A
    call with no files is not evidence, and a glob that could be empty or could
    select stale files is not an explicit set.
11. **Record what the representation cannot carry.** Record every fact the IR
    omits — reset values and masks, the full access and side-effect model,
    device-level data absent from block YAML — into `svd.representation_limits`
    and discharge `information-limits` from that assessment. An understood
    omission travels as a cited source fact; it is never a claim that generated
    code enforces the behavior.
12. **Run the preparation replay.** Replay from the same
    original or authored SVD, transform and include bytes, tool revision, modes
    and options into a new unused output directory, compare inventory and
    contents with the prepared result, and discharge `preparation-replay` from
    that comparison. An unrun replay is not reproducibility.
13. **Author the preparation record.** Author the record at
    `<documentation>/notes/SVD.md` using the reference's
    [record and handoff fields](./references/preparation-and-checks.md#preparation-record-and-handoff),
    preserving earlier results rather than erasing them.
14. **Request materialization of the catalog delta.** Request, through
    **hal-coordinator**, that **hal-integrator** materialize the `SOURCES.md`
    delta registering the stable project and SVD input locations, and return its
    FileRef. Durable evidence and notes are written first; the catalog is
    materialized and hashed before the final handoff.
15. **Publish the preliminary handoff and validate it.** Publish the preliminary
    `03-svd`, preserving a hashed snapshot and recovery record of any
    deterministic handoff `state.toml` currently pins before replacing it, then
    run `python .opencode/schema/validate.py <repository-root> --kind all`
    again.
16. **Re-attest any changed bytes.** Re-attest on resumption and on the
    transition from the preliminary handoff to the final one: preserve the
    superseded evidence and review records, create replacement evidence at a new
    path rather than overwriting one, rerun only the affected checks, obtain a
    new applicability review where the reviewed bytes changed, and never delete
    an old record to regain validation.
17. **Publish the final handoff and run the final gate.** Publish the final
    `halucinator/handoff/03-svd.toml`, run `python .opencode/schema/validate.py <repository-root> --kind all` over it, let **hal-coordinator**
    update `state.toml` through the compare-and-swap sequence — state is never
    updated before the handoff validates — and run the final `--kind all` gate.
18. **Return to hal-coordinator.** Return the record path, the target and scope,
    the description delta, the checks including every `unrun` one, the status
    and the next action. State that no Rust generation, compilation or hardware
    operation was performed.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `correction-effects` | Compare each transform's expected matches and effect against the observed result | `derived/svd/<target-id>/<run-id>/prepared/correction-effects.log`, or `reason (no evidence FileRef)` when there are zero transforms |
| `information-limits` | Record every fact the IR cannot carry and its consumer impact | `<documentation>/notes/SVD.md` representation-limit section, captured as a FileRef |
| `input-identity` | Validate the predecessor handoff and compare the exact SVD FileRef, source ID and input hashes | `derived/svd/<target-id>/<run-id>/baseline/identity.log` |
| `preparation-replay` | Run the replay from the durable original inputs into a fresh directory and compare inventory and bytes | `derived/svd/<target-id>/<run-id>/replay/replay-diff.log` |
| `schema-validation` | Validate the XML against a trusted local CMSIS-SVD schema of the declared version | `derived/svd/<target-id>/<run-id>/baseline/schema-validation.log` |
| `source-fact-comparison` | Compare effective register properties against the cited findings | `<documentation>/notes/SVD.md` comparison table, captured as a FileRef |
| `structural-inventory` | Run the structural check over an explicitly enumerated nonempty file set | `derived/svd/<target-id>/<run-id>/prepared/structural-inventory.log` |
| `xml-well-formed` | Validate that the original or authored XML parses with structured tooling | `derived/svd/<target-id>/<run-id>/baseline/xml-well-formed.log` |

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
`svd.unresolved_facts` is empty, `svd.route` equals the upstream
`sources.route`, the `01-sources` input is `ready`, the `02-facts` input is
`ready` on the `author-from-docs` route, the coordinator-dispatched
route-applicability review has been obtained, and every applicable check is
`passed`.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Only fresh disposable derived work continues; no canonical
replacement.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names an external fact, tool or access action —
including a `blocked`, absent or scope-incomplete `02-facts` input on the author
route.

Never narrow the declared scope after a failed run to reach `ready`. A narrower
scope is a new coordinator-owned scope decision with its own complete evidence.

## Application example

The emitted handoff for a supplied vendor SVD with one cited correction:

```toml
[handoff]
schema = 2
stage = "generate-svd"
status = "ready"
inputs = [
  { path = "halucinator/handoff/01-sources.toml", sha256 = "3c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e" }

[coverage]
complete = ["peripheral:schema-demo"]
incomplete = []

[svd]
route = "review-supplied"
source = { path = "halucinator/pac/unobtainium/data/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/fictional-fixture.svd", sha256 = "91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80" }
transforms = [
  { path = "halucinator/pac/unobtainium/data/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/transforms/fictional-fixture.yaml", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" },
]
includes = []
prepared_manifest = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/prepared/INVENTORY.md", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }
extraction_mode = "block"
namespace_mode = "block-with-regs-vals"
representation_limits = [
  "Block YAML carries no reset value or reset mask; SCHEMADEMO.CTRL reset 0x0000_0010 travels as a cited source fact only.",
]
unresolved_facts = []

[[checks]]
id = "input-identity"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/baseline/identity.log", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }

[[checks]]
id = "xml-well-formed"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/baseline/xml-well-formed.log", sha256 = "d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4" }

[[checks]]
id = "schema-validation"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/baseline/schema-validation.log", sha256 = "e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5" }

[[checks]]
id = "source-fact-comparison"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" }

[[checks]]
id = "correction-effects"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/prepared/correction-effects.log", sha256 = "f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6" }

[[checks]]
id = "structural-inventory"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/prepared/structural-inventory.log", sha256 = "08192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7" }

[[checks]]
id = "information-limits"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" }

[[checks]]
id = "preparation-replay"
status = "passed"
evidence = { path = "halucinator/pac/unobtainium/derived/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/run-001/replay/replay-diff.log", sha256 = "192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }
```

With zero transforms, `transforms` is `[]` and the `correction-effects` entry
carries `status = "not-applicable"` with a `reason` naming the absence of
corrections — never a sentinel value in place of a missing field.

## Quick reference

| Element | Value |
|---|---|
| Stage | `generate-svd` |
| Emitter | `hal-svd` |
| Emitted handoff | `halucinator/handoff/03-svd.toml`, kind `03-svd` |
| First note | exactly `<documentation>/notes/SVD.md` |
| Consumes | `01-sources` always; `02-facts` on the `author-from-docs` route |
| Checks | `correction-effects`, `information-limits`, `input-identity`, `preparation-replay`, `schema-validation`, `source-fact-comparison`, `structural-inventory`, `xml-well-formed` |
| Catalog | `SOURCES.md`, class `sources-catalog`, owned by `hal-integrator`; this skill supplies the delta |
| Routing | every question, review request, gate and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, empty unresolved facts, route equality, applicability review obtained, applicable checks `passed` |

## Common mistakes

- **Reaching `ready` on the author route without `02-facts`.**
  `extract-hardware-facts` produces it; admit a `ready` one. When it is absent,
  `blocked`, or does not cover this run's scope, the correct outcome is a named
  blocker and a return to `hal-coordinator`, not an SVD authored from a vendor
  file read as if it were a manual.
- **Treating an accessible SVD as an applicable one.** `input-identity` must
  name the exact FileRef and source ID, and the applicability review is
  procedural, not optional judgement.
- **Producing hardware facts here.** `hal-svd` is not a facts producer. A
  register value that no citation supports is an invented hardware fact.
- **Reusing a populated derived run directory.** Every run gets a fresh unused
  label; freeing one by deleting files destroys the evidence a replay compares
  against.
- **Applying corrections to the previous output.** Corrections apply from the
  original input. Chaining them through the last result makes the recipe
  unreplayable and hides a rule that no longer matches.
- **Passing a glob to the structural check.** A call with no files exits zero
  and proves nothing. Enumerate an explicit nonempty set.
- **Calling a transform successful because the tool exited zero.** A required
  rule that matched nothing, or matched too much, is a failed check.
- **Narrowing scope after a failure.** That converts an unresolved defect into
  an invisible one. Ask `hal-coordinator` for a new scope decision instead.
- **Returning questions to the architect.** The architect is not in this
  stage's topology.
