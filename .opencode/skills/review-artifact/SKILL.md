---
name: review-artifact
description: >-
  Use when hal-coordinator supplies a frozen artifact, complete dependency
  closure and artifact-specific review profile and requires an independent
  08-review verdict or recheck. Dispatch and search terms: frozen candidate,
  artifact identity, hardware citations, upstream contracts, findings,
  ready-with-fixes, not-ready, 08-review handoff. Wrong for editing or fixing
  artifacts, committing, dispatching peers, applying gate decisions, or
  reviewing unfrozen bytes.
compatibility: opencode
---

# Review a frozen artifact

```halucinator-skill-contract
stage: review
participants: hal-reviewer
emitter: hal-reviewer
emits: 08-review|halucinator/handoff/08-review-<artifact>.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,review.artifact,review.artifact_id,review.dependencies,review.findings.location,review.findings.owner,review.findings.severity,review.findings.status,review.findings.summary,review.lineage.kind,review.lineage.previous,review.scope,review.unreviewed,review.verdict,scope.decision,scope.revision
checks: applicable-references-read,artifact-identity,hardware-claims-cited,upstream-contracts-reviewed
consumes: 01-sources|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,sources.catalog,sources.cited_notes,sources.documents.document,sources.documents.format,sources.documents.revision,sources.documents.source,sources.documents.source_id,sources.route
consumes: 02-facts|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,facts.categories,facts.citations.assertion_id,facts.citations.claim,facts.citations.excerpt,facts.citations.location.kind,facts.citations.location.line_end,facts.citations.location.line_start,facts.citations.location.page,facts.citations.locator.kind,facts.citations.locator.value,facts.citations.note,facts.citations.scope_item,facts.citations.source,facts.citations.source_id,facts.contradictions,facts.notes,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision
consumes: 03-svd|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,svd.extraction_mode,svd.includes,svd.namespace_mode,svd.prepared_manifest,svd.representation_limits,svd.route,svd.source,svd.transforms,svd.unresolved_facts
consumes: 04-pac|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,pac.cargo_chip_feature,pac.cited_notes,pac.crate_manifest,pac.foundation.evidence,pac.foundation.id,pac.foundation.kind,pac.foundation.location,pac.foundation.status,pac.metadata_features,pac.package,pac.revision.kind,pac.revision.value,pac.runtime_features,pac.rust_compilation_target,pac.source_ids,pac.temporary_fork,scope.decision,scope.revision
consumes: 05-platform|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,platform.cited_notes,platform.crate_manifest,platform.dependencies.crate,platform.dependencies.features,platform.dependencies.identity,platform.first_driver,platform.first_driver_modes,platform.foundation_api,platform.pac_manifest,platform.roadmap,platform.source_ids,platform.startup_clock_contract,platform.supporting_subsystems,scope.decision,scope.revision
consumes: 06-driver|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,driver.build_contract.cargo_chip_feature,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.build_contract.rust_compilation_target,driver.capabilities,driver.dependencies.crate,driver.dependencies.features,driver.dependencies.identity,driver.facts_handoff,driver.name,driver.owned_files,driver.public_api,driver.public_test_record,driver.requirement_ids,driver.scope_kind,driver.test_hardware_facts,driver.trait_obligations.dependency_crate,driver.trait_obligations.obligations,driver.trait_obligations.trait,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision
consumes: 07-tests|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,tests.api_handoff,tests.board_interlock.authorization,tests.board_interlock.board_id,tests.board_interlock.check_token,tests.board_interlock.lease_epoch,tests.coverage.evidence,tests.coverage.id,tests.coverage.reason,tests.coverage.status,tests.coverage.test_case,tests.dependencies.crate,tests.dependencies.features,tests.dependencies.identity,tests.execution_scope,tests.hardware_runs.evidence,tests.hardware_runs.lease_epoch,tests.hardware_runs.operation_attempt,tests.hardware_runs.operation_id,tests.hardware_runs.post_safe_state,tests.hardware_runs.pre_safe_state,tests.hardware_runs.status,tests.hardware_runs.teardown,tests.hardware_runs.test_case,tests.name,tests.output_kind,tests.owned_files,tests.recovery_attempts,tests.review_input_manifest,tests.safe_state_procedure.assertion_ids,tests.safe_state_procedure.board_id,tests.safe_state_procedure.facts_handoff,tests.safe_state_procedure.procedure,tests.setup_record
writes: hal-reviewer|review-handoff
supplies-delta: hal-reviewer|review-notes
```

This stage audits **one frozen artifact** against an artifact-specific review
profile and emits **one typed verdict**. The contract enumerates `01-sources`
through `07-tests` as the supported predecessor kinds; **one invocation selects
exactly one predecessor kind**, named by the dispatch, and consumes that kind
alone. It never consumes all seven at once.

## When to use

Use this skill when **hal-coordinator** dispatches an initial review or a
recheck and supplies the complete payload **hal-reviewer** requires: the
artifact ID and primary ArtifactRef, the complete frozen set, the review scope,
the architecture specification, the dependency closure, the citations and
contracts, the live Embassy references, any prior review, and the declared
exclusions. A missing mandatory input yields `blocked`; it is not something to
reconstruct by guessing.

Use it also when a previous `08-review-<artifact>` stopped at `partial` or
`blocked` and the recorded next action is now possible, or when previously
reviewed bytes changed and a recheck is required.

Do not use it while the artifact is still being written. A review of unfrozen
bytes is a verdict about nothing: the hashes recorded in `review.artifact` and
`review.dependencies` describe a state that no longer exists by the time the
verdict is read, and the accepting verdict then launders an unreviewed change
through the gate. If the payload does not establish that the set is frozen,
return `blocked` rather than reviewing what happens to be on disk.

## Ownership and boundaries

**hal-reviewer** audits; it fixes nothing, commits nothing and dispatches
nobody. Its only writable path is `halucinator/handoff/08-review-*.toml`. Every
cross-owner transition returns to **hal-coordinator**.

| Owner | Materializes here | Never here |
|---|---|---|
| **hal-reviewer** | class `review-handoff`, exactly `halucinator/handoff/08-review-<artifact>.toml`; and the semantic content of the review note | any file under review, any shared file, any commit, any dispatch |
| **hal-integrator** | class `review-notes`, exactly `halucinator/docs/*/notes/REVIEW-*.md`; and it is the **sole committer** | findings content, verdicts, scope decisions |
| **hal-coordinator** | the dispatch, the scope decision, `state.toml`, and the **application** of this verdict as a gate | findings content or the verdict token |
| **hal-driver**, **hal-integrator**, **hal-svd**, **hal-datasheet**, **hal-tester** | the fixes this review's findings name | the verdict on their own work |

Cross-owner delta: this stage **authors** the semantic content of the review
note, but the `review-notes` class is **owned and materialized by
hal-integrator** per [`ownership.toml`](../../ownership.toml). Route it that
way: hand the authored note content to **hal-coordinator**, which dispatches
**hal-integrator** to materialize `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md`
and return its FileRef. Pin that returned FileRef in `handoff.notes` and in
check evidence. Never write that path directly, and never use `writes` for it.

**Never edit or fix the artifact under review.** Report the defect, its
`file:line`, the conditions under which it manifests, the shape of the fix and
the agent that owns it. A reviewer who repairs the artifact has reviewed its own
patch. Gate authority sits with **hal-coordinator**: this stage supplies the
verdict, the coordinator applies it. Do not claim gate authority, do not soften
a rejection into prose, and do not attach an accepting verdict to open blocking
findings.

`bash` is `ask`, not a sandbox. The read-only stance is a commitment, not a
runtime guarantee: an approved command or an external tool could still modify
the artifact between the hash and the verdict.

## Inputs

Consume exactly one predecessor kind, selected by the dispatch, reading the
leaves the contract declares for that kind. The admission vocabulary is the
producer's own field names; the concerns are common across kinds:

| Admission concern | Consumed field |
|---|---|
| Producer status and lineage | `handoff.status`, `handoff.can_progress`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `handoff.schema`, `handoff.stage` |
| Scope binding | `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |
| Producer self-attestation | `checks.id`, `checks.status`, `checks.evidence`, `checks.reason` |
| Kind-specific substance | the remaining leaves the contract lists for the selected kind — `sources.*`, `facts.*`, `svd.*`, `pac.*`, `platform.*`, `driver.*` or `tests.*` |

Read separately from coordinator-owned state: the target identity, the artifact
ID, the primary ArtifactRef, the complete frozen set, the review scope, the
declared exclusions, the selected review profile inputs, the documentation
roots, and any prior `08-review-<artifact>` for lineage.

A `blocked` predecessor permits no consumption; report it and return `blocked`.
A `partial` one permits read-only inspection and a review whose own status
cannot be `ready`, because a review cannot certify more than its input admits.
Live Embassy references — `embassy-mcxa/DEVGUIDE.md` and the concern-specific
files `AGENTS.md` names — are read from the actual checkout; a remembered
pattern from this toolkit is not a live reference, and its absence blocks the
affected judgement rather than lowering it.

## Outputs

- `halucinator/handoff/08-review-<artifact>.toml`, carrying
  `review.artifact_id`, the `review.artifact` ArtifactRef, `review.scope`,
  `review.unreviewed`, `review.dependencies`, every `review.findings` entry with
  its `severity`, `location`, `summary`, `owner` and `status`, the tagged
  `review.lineage`, exactly one `review.verdict`, the four canonical checks,
  coverage and scope. This is the **only** file this stage writes.
- The authored content of `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md`,
  recording the frozen inventory and its hashes, every reference, contract and
  manual locator actually read, the claim-by-claim citation comparison, the
  findings in severity order, and an explicit statement of what was not
  examined — **materialized by hal-integrator**, routed through
  **hal-coordinator**, and pinned here by the FileRef it returns.
- A returned narrative: scope reviewed and deliberately not reviewed, blocking
  defects first, convention divergence, type and API findings, contract
  findings, unverified claims, and the typed verdict with the FileRef carrying
  it.

Severity is honest in both directions: a style preference is not `blocking`, and
a lost wakeup is not `convention`. `review.unreviewed` is populated honestly —
an unexamined surface is a recorded gap, never an implicit pass.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock applicable to the
   `review` stage and to this artifact's resources — the stage resource
   `stage:review:<artifact>` and the path resource for
   `halucinator/handoff/08-review-<artifact>.toml` — and classify each as live,
   interrupted or ambiguous, **without modifying the reviewed artifact or any
   other agent's output**. Live means concurrency: do not interfere and do not
   recover. Ambiguous means wait one 30-second refresh interval, reread, and
   fail closed if it is still ambiguous. Interrupted, or ambiguous still
   unresolved after that reread, means recovery: do not mutate the suspect
   output, inventory and hash it into a recovery Markdown FileRef, compare it
   against the last valid handoff, and publish `partial` with empty blockers
   when unaffected fresh review work remains or `blocked` with an
   `interrupted:review:<artifact>` blocker when it does not. Record the
   comparison, the disposition and the new location before an authorized actor
   removes the lock. Also inspect any prior `08-review-<artifact>` and classify
   this run as `{kind="initial"}` or `{kind="recheck",previous=<FileRef>}`. An
   absent handoff is not proof that no prior dispatch ran: `halucinator/.run/`
   is gitignored and invisible to a fresh clone, so a missing handoff and a
   missing lock together are silence, not evidence.
2. **Validate before consuming the selected producer handoff.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading the selected
   producer handoff or opening any byte of the frozen artifact. Exit 0 with
   silent output is necessary; a missing interpreter, Python below 3.11, a
   timeout, a nonzero exit, or simply not running it is not a pass and blocks
   consumption. Report an unrelated stale artifact or an unrelated ambiguous
   lock surfaced by the all-kinds gate as a named blocker rather than ignoring
   it.
3. **Load the review profile.** Load exactly one profile, selected from the
   **producer kind and the artifact class** named in the dispatch — never from
   the verdict anyone hopes to reach. Selecting the profile from the desired
   outcome is the classic inversion by which a gate becomes advisory: the
   obligations shrink until whatever was built satisfies them. Record the
   selected profile and the kind and class that selected it. An artifact whose
   class cannot be established from the payload is `blocked`, not reviewed under
   a guess.
4. **Compare artifact identity.** Compare the complete frozen set and the
   dependency closure, file by file, against the ArtifactRef and FileRefs the
   producer declared, hashing every member rather than sampling, and discharge
   `artifact-identity` from that comparison. Any member whose hash differs from
   the declaration, or that the declaration omits, means the set is not frozen
   as described: record it and return `partial` or `blocked` rather than
   reviewing bytes nobody attested to.
5. **Load applicable references.** Load the architecture specification, the live
   Embassy references and DEVGUIDE sections the profile names, the upstream
   trait documentation, the cited hardware notes and any prior review, record
   exactly which sections, files and source IDs were read, and discharge
   `applicable-references-read` from that record. Divergence needs a reference,
   not an impression; a reference you could not open leaves the affected
   judgement in `review.unreviewed`.
6. **Compare hardware claims against their citations.** Compare every hardware
   assertion the artifact depends on — offsets, bit positions, reset values,
   sequences, clock topology, errata — against its source identity, revision,
   locator and supporting note, opening the manual yourself where a citation is
   offered, and discharge `hardware-claims-cited`. Record `not-applicable` with
   a reason only when the review scope contains no `hardware:` or
   `foundation:fact-` item. A claim you did not verify against its locator is an
   `unverified` finding, never a pass.
7. **Compare upstream contracts against their obligations.** Compare every
   declared dependency and trait obligation — `embedded-hal`,
   `embedded-hal-async`, `embedded-io`, `embassy-usb-driver`,
   `embassy-time-driver` — against its own documentation used as a checklist,
   together with the declared crate identities and features, and discharge
   `upstream-contracts-reviewed`. Record `not-applicable` with a reason only
   when the reviewed artifact declares none. Compiling against a trait is not
   honoring it.
8. **Record findings, unreviewed scope and one typed verdict.** Record every
   finding with its `severity`, `location` as `file:line`, `summary`, the
   `owner` agent that owns the fix, and its `status`; order the worst first;
   populate `review.scope` and `review.unreviewed` so that every surface the
   payload included is either reviewed or named as a gap; and record exactly one
   `review.verdict`. Separate what was verified from what was inferred, and name
   which parts of the verdict depended on evidence you were shown rather than
   produced. Per HAL-RULE-11, a surface not examined is recorded in
   `review.unreviewed` rather than passed over in silence.
9. **Request review-note materialization.** Request through **hal-coordinator**
   that **hal-integrator** materialize the authored review note at
   `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md` and return its
   FileRef, then pin that FileRef in `handoff.notes` and in the evidence of the
   checks it discharges. Do not write that path: `review-notes` is owned by
   **hal-integrator**, and this stage supplies only the delta.
10. **Publish the preliminary and final handoffs and validate each.** Publish
    the preliminary `08-review-<artifact>`, preserving a hashed snapshot and
    recovery record of any deterministic handoff `state.toml` currently pins
    before replacing it, and run
    `python .opencode/schema/validate.py <repository-root> --kind all` after the
    write. Re-attest where referenced bytes changed: preserve the superseded
    evidence and the superseded review records, create replacement evidence at a
    **new** path rather than overwriting one, and rerun only the affected
    checks. **Never delete old evidence or an old review record to regain
    validation.** Then rewrite the final handoff, validate it again, let
    **hal-coordinator** update `state.toml` through the compare-and-swap
    sequence and apply the gate, and return the record paths, the status and the
    next action. State that no artifact under review, no shared file, no commit
    and no hardware operation was touched.

Only review.verdict=ready accepts; ready-with-fixes and not-ready do not.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `applicable-references-read` | Record every architecture, live reference and contract inspected | `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md` |
| `artifact-identity` | Compare the complete frozen artifact set and dependencies with recorded FileRefs | `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md` |
| `hardware-claims-cited` | Compare hardware claims with source identity, revision, locator and supporting note | `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md`, or `reason (no evidence FileRef)` when review scope contains no hardware fact ID |
| `upstream-contracts-reviewed` | Compare every declared dependency and trait obligation against its documentation | `halucinator/docs/<target-id>/notes/REVIEW-<artifact>.md`, or `reason (no evidence FileRef)` when the artifact declares none |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. Two further limits
belong in every verdict that relies on them. First, **typed evidence hashes
freshness, not relevance**: the validator proves that FileRef hashes match and
that the handoff has the right shape, but it cannot prove that the examination
was thorough or that a given piece of evidence actually discharges the check it
is attached to — that stays reviewer judgement. Second, the `07 → 08` edge is
**procedural, not a validator-enforced graph edge**: an arbitrary `08-review`
does not statically prove which producer handoff the coordinator selected, so
the selection is recorded in `handoff.inputs` and in the review note and is
believed on that record alone.

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

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
`review.unreviewed` is empty for the required scope, every applicable check is
`passed`, and `review.verdict="ready"` with no open `blocking`, `api`,
`contract` or `unverified` finding. Only review.verdict=ready accepts;
ready-with-fixes and not-ready do not. Ready here means the review completed and
accepted the frozen bytes it hashed; **hal-coordinator** still applies the gate.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. **This status does not accept the artifact.** A non-`ready` review
status is not a soft pass and never discharges a downstream
`independent-review`: it records that the review itself is unfinished. A
`partial` publication pins, through `handoff.notes`, the review note naming what
was examined, what remains, and why.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. **This status does not accept the artifact either.** A
blocker names the affected scope items, the owner, the next action and the
evidence needed, and identifies a missing payload item, unfrozen artifact,
unreachable reference, missing citation source, tool or decision that only
somebody outside this stage can supply. A missing mandatory dispatch input lands
here, as does an artifact that is still being written.

## Application example

For exact MCU `unobtainium-circuits-uc-not-a-real-mcu-0001` the coordinator
dispatches an initial review of the frozen `embassy-unobtainium` integration
candidate, selecting the `05-platform` producer kind and the platform artifact
class. The frozen inventory and the architecture note hash as declared, so
`artifact-identity` and `applicable-references-read` pass. The included scope
carries no `hardware:` or `foundation:fact-` item and the reviewed inventory
declares no upstream trait obligation, so the remaining two checks are recorded
`not-applicable` with reasons rather than being silently skipped. No finding is
open, `review.unreviewed` is empty, and the verdict is the accepting token. The
emitted handoff:

```toml
[handoff]
schema = 1
stage = "review"
status = "ready"
inputs = [
  { path = "halucinator/candidates/integration-001/INVENTORY.md", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/REVIEW-PLATFORM.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" }

[coverage]
complete = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]
incomplete = []

[review]
artifact_id = "platform"
artifact = { path = "halucinator/candidates/integration-001/INVENTORY.md", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" }
scope = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]
unreviewed = []
dependencies = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ARCHITECTURE.md", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" },
]
findings = []
verdict = "ready"

[review.lineage]
kind = "initial"

[[checks]]
id = "applicable-references-read"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/REVIEW-PLATFORM.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" }

[[checks]]
id = "artifact-identity"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/REVIEW-PLATFORM.md", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" }

[[checks]]
id = "hardware-claims-cited"
status = "not-applicable"
reason = "The fictional review scope contains no hardware: or foundation:fact- item."

[[checks]]
id = "upstream-contracts-reviewed"
status = "not-applicable"
reason = "The reviewed fictional inventory declares no upstream trait obligation."
```

The paths and hashes above are fictional schema shape, not evidence. A fact
nobody established is an absent key or an empty collection, never a sentinel
word.

## Quick reference

| Element | Value |
|---|---|
| Stage | `review`, one instance per artifact, `review:<artifact>` |
| Emitter | `hal-reviewer`; `hal-integrator` is the sole committer |
| Emitted handoff | `halucinator/handoff/08-review-<artifact>.toml`, kind `08-review` |
| Consumes | exactly one of `01-sources`, `02-facts`, `03-svd`, `04-pac`, `05-platform`, `06-driver`, `07-tests`, selected by the dispatch |
| Checks | `applicable-references-read`, `artifact-identity`, `hardware-claims-cited`, `upstream-contracts-reviewed` |
| Owned class | `review-handoff` only — the single writable path |
| Delta | `review-notes`, registry owner **hal-integrator**, routed through **hal-coordinator** |
| Profile selection | from producer kind and artifact class, never from the desired verdict |
| Verdict vocabulary | `ready`, `ready-with-fixes`, `not-ready`, per [`08-review.md`](../../schema/08-review.md) |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Gate authority | **hal-coordinator** applies the verdict; this stage only supplies it |
| Lineage | `{kind="initial"}` or `{kind="recheck",previous=<FileRef>}`; rechecks only, not general supersession |
| Findings | `severity` one of `blocking`, `convention`, `api`, `contract`, `unverified`; `status` one of `open`, `resolved`, `not-applicable`; each with `location` and `owner` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Status meaning | `partial` and `blocked` do not accept the artifact |
| Limits | evidence hashes freshness, not relevance; the `07 → 08` edge is procedural |
| Related contracts | [`hal-reviewer.md`](../../agents/hal-reviewer.md), [`handoff-common.md`](../../schema/handoff-common.md), [`ownership.toml`](../../ownership.toml) |

## Common mistakes

- **Reviewing bytes that are still being written.** The verdict then describes a
  state that no longer exists, and the accepting token launders an unreviewed
  change through the gate. Establish the frozen set, or return `blocked`.
- **Selecting the profile from the hoped-for verdict.** The obligations shrink
  until whatever was built satisfies them. Select from producer kind and
  artifact class, and record what selected it.
- **Sampling the frozen set instead of hashing all of it.** `artifact-identity`
  is an equality over the complete set and its dependency closure; a spot check
  proves that one file did not change.
- **Fixing the defect you found.** It is the most natural reflex and it destroys
  the review: the reviewer has now reviewed its own patch, and `hal-reviewer`
  has no write access to that path anyway. Report the fix shape and its owner.
- **Writing `REVIEW-<artifact>.md` directly.** That class is owned by
  **hal-integrator**. Authoring its content is this stage's job; materializing
  it is not. Route the delta through **hal-coordinator**.
- **Treating `partial` as a soft pass.** A non-`ready` review status records an
  unfinished review, not a qualified acceptance, and it discharges no downstream
  `independent-review`.
- **Leaving an unexamined surface out of `review.unreviewed`.** Silence about
  what was skipped reads downstream as an implicit pass, which is exactly the
  claim HAL-RULE-11 forbids.
- **Approving on a green build or a working example.** Type-checking proves
  nothing about silicon, and the expensive faults in an async HAL are ordering
  faults invisible to the test written by whoever caused them.
- **Inflating a style preference to `blocking`, or softening a lost wakeup to
  `convention`.** Both destroy the signal that severity ordering exists to
  carry.
- **Consuming all seven predecessor kinds at once.** The contract enumerates
  alternatives; a dispatch selects one.
- **Claiming the gate.** The verdict is supplied here and applied by
  **hal-coordinator**; a reviewer that decides the gate has become the producer's
  peer rather than its check.
- **Deleting a superseded review record to make a recheck validate.** It
  converts a traceable supersession into an untraceable one, and it is the most
  tempting shortcut when a late check fails.
- **Quoting only the rejecting verdicts.** Stating what fails to accept, without
  stating what does, turns the gate into advice. Use the exact sentence with the
  hyphenated tokens.
- **Describing the validator wiring, the lock or the `07 → 08` edge as
  enforcement.** All three are procedural, and saying otherwise makes every
  reader trust an attestation nobody made.
