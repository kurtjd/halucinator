---
name: gather-documentation
description: >-
  Use when a new Embassy HAL target has been named but its reference manual,
  datasheet, errata, EVB schematic, board user guide or vendor SVD have not yet
  been collected and recorded, or when an earlier intake stopped part way.
  Dispatch and search terms: documentation intake, source list, SOURCES.md,
  exact MCU part number, board revision, vendor SVD search, source hashes,
  01-sources handoff. Wrong for extracting cited register facts, preparing or
  correcting an SVD, generating a PAC, scaffolding a crate, or setting up,
  flashing or running hardware.
compatibility: opencode
---

# Gather Documentation

```halucinator-skill-contract
stage: gather-documentation
participants: hal-datasheet
emitter: hal-datasheet
emits: 01-sources|halucinator/handoff/01-sources.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,sources.catalog,sources.cited_notes,sources.documents.document,sources.documents.format,sources.documents.revision,sources.documents.source,sources.documents.source_id,sources.route
checks: available-content-resolves,local-source-hashes,requested-inputs-accounted,svd-search-complete
consumes: none|none
writes: hal-datasheet|vendor-source-bytes
writes: hal-datasheet|sources-handoff
supplies-delta: hal-datasheet|sources-catalog
```

This is the intake stage of the pipeline. It establishes the exact target, the
documents that describe it, and one recorded SVD starting point, and it
publishes the typed `01-sources` handoff every later stage admits against.

## When to use

Use this skill when the coordinator dispatches `gather-documentation` for a
named target, or when a previous intake left `01-sources` at `partial` or
`blocked` and the recorded gaps are now actionable.

Do not use it to convert a PDF, interpret a schematic, extract a register fact,
choose an extraction mode, or reason about a peripheral's behavior. Those are
later stages. Finding a vendor SVD during intake does not skip `generate-svd`;
it only changes that stage's starting point.

## Ownership and boundaries

The owning agent is **hal-datasheet**. It materializes two ownership classes
itself: `vendor-source-bytes`, the preserved originals and downloads under the
selected documentation root, and `sources-handoff`, the deterministic
`halucinator/handoff/01-sources.toml`.

`SOURCES.md` is the `sources-catalog` class and is **owned by
hal-integrator**. This skill authors the catalog delta — the exact records,
coverage rows and search-log lines to add or update — and **hal-coordinator**
dispatches **hal-integrator** to materialize it and return its FileRef. The
datasheet agent never writes that file directly.

Every question, routing decision, capability gap and next-stage dispatch goes
to **hal-coordinator**. Do not address the architect, and do not invoke a
downstream skill as a shortcut.

Collect hardware setup requirements, but do not install tools, run vendor
scripts, connect a probe, flash a board, or test RAM execution.

## Inputs

Read the coordinator-supplied state rather than guessing any of it:

- `target.vendor`, `target.mcu_part_number`, `target.target_id`,
  `target.vendor_id`, `target.package`, and, when recorded,
  `target.silicon_revision`, `target.core`, `target.board`,
  `target.board_revision`;
- `scope.current_revision` and `scope.current_decision`;
- `roots.documentation`, `roots.sources` and, when already selected,
  `roots.generation`.

A missing or self-contradictory target identity or scope decision is returned
to **hal-coordinator** as a blocker. Do not substitute a family part, a
remembered working directory or a plausible default.

There is no predecessor handoff: the contract declares `consumes: none|none`.
The `--kind all` gate still runs first, because a stale or unvalidatable
artifact elsewhere in `halucinator/` must be named, not stepped over.

Read [the storage rules and source-list template](./references/source-list-format.md)
before selecting a location, and
[the common handoff contract](../../schema/handoff-common.md) for the status
and absence rules restated below.

## Outputs

- Preserved source bytes under the selected documentation root's `sources/`,
  one directory per source ID, with originals never moved or deleted.
- A `SOURCES.md` delta authored here and materialized by **hal-integrator**.
- `halucinator/handoff/01-sources.toml`, carrying `sources.catalog`,
  `sources.route`, `sources.documents` (one binding entry per source, each
  carrying `source_id`, `document`, `revision`, `format` and a hash-pinned
  `source`), `sources.cited_notes`, the four canonical checks, coverage and scope.

`sources.route` is producer-evaluable and is exactly one of `review-supplied`,
`author-from-docs` or `unresolved`. Supplied means an accessible SVD exists;
author means the search completed without one and register documentation is
accessible; unresolved means the search or access did not complete.
Applicability is a downstream judgement and is never asserted here.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering this stage
   and the catalog resource, and classify each as live, interrupted or
   ambiguous. Live means concurrency: do not interfere. Ambiguous means wait one
   30-second refresh interval, reread, and fail closed if it is still ambiguous.
   Interrupted, or ambiguous still unresolved, means recovery: do not mutate the
   suspect output, inventory and hash it into a recovery Markdown FileRef,
   compare it against the last valid handoff, and publish `partial` with empty
   blockers when unaffected fresh work remains or `blocked` with an
   `interrupted:gather-documentation` blocker when it does not. Record the
   comparison, the disposition and the new candidate location before an
   authorized actor removes the lock. Resume only in a fresh location.
2. **Validate before consuming anything.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding before reading state or any existing artifact.
   Exit 0 with silent output is necessary. A missing interpreter, a timeout, a
   nonzero exit, or not running it at all is not a pass. Report a stale
   unrelated artifact or an ambiguous unrelated lock as a named blocker.
3. **Load the target identity and scope.** Load the state fields listed under
   Inputs, preserve the user's exact identifiers, and name which applicability
   checks an unknown package, silicon revision or board revision prevents. An
   unresolved part number is a question for **hal-coordinator**, not a guess.
4. **Select the documentation root.** Select or resume the documentation
   directory under the reference's rules, resolving symlinks and existing
   parents so the destination stays inside the working repository. Check the
   recorded identity of any existing catalog before reuse; a matching folder
   name is not proof. A different MCU, board or known board revision needs its
   own directory.
5. **Request the sources and the bench context.** Request, in short groups and
   skipping anything already answered: the reference manual for the exact MCU;
   errata, including corrections folded into another document; the datasheet
   with the selected package's pin and electrical data; the EVB schematic and
   board user guide matching the board revision; supporting documents; and any
   existing SVD with its origin and intended devices. Also request the probe or
   programmer, interface, loader and version, host OS, board access and any
   existing loading or RAM-execution instructions. These are user-reported setup
   facts, not evidence of tool support.
6. **Select and search for the missing inputs.** Select supplied sources first,
   then search official vendor product pages, documentation portals, SDK
   repositories and device-support packs, including inside documented pack and
   SDK contents. Search the exact part and its documented family; never
   substitute a similarly named chip. Record the sites searched, the date and
   the outcome, and discharge `svd-search-complete` from that log on the
   `author-from-docs` route. A community result is a candidate with explicit
   provenance, not an authority. Never bypass an access restriction or request
   credentials.
7. **Preserve the source bytes.** Preserve user originals and vendor bytes by
   copying or downloading into `sources/` without overwriting another source.
   Retain an explicit reference-only path where copying is not permitted, and
   record the dependency on its continued availability. Keep archive extraction
   inside the authorized workspace and reject paths or symlinks that escape it.
   Do not execute packaged installers to obtain documentation.
8. **Classify availability and applicability separately.** Classify each input
   as not searched, located, available, inaccessible, not found, or confirmed
   unavailable, and check the actual file type rather than the extension: an
   HTML login page saved with a `.pdf` name is not an available manual. Discharge
   `available-content-resolves` from that content inspection. A readable
   wrong-part manual is still unsuitable, so keep applicability separate.
9. **Record the identities and hashes.** Record each source's stable ID,
   title and document number, revision or date, provenance, covered parts and
   relative local path, and compute a tool-computed SHA-256 for every local
   byte stream to discharge `local-source-hashes`. When `sources.documents` is
   empty, record that check as `not-applicable` with a reason instead. Never
   invent a digest, and keep credentials and temporary authenticated URLs out of
   the record.
10. **Record the gaps and the route.** Record, for every missing or uncertain
    input, what it blocks and the next action, then select `sources.route`.
    On `review-supplied` the route evidence must identify the accessible SVD
    as one `sources.documents` entry binding its source ID to the hash-pinned
    file, and must record the remaining applicability
    uncertainty; accessibility is never applicability. On `author-from-docs`
    the search evidence proves the search completed, not that any fact was
    extracted. `unresolved` can never be `ready`.
11. **Compare the requested inputs against the record.** Compare the completion
    inventory with the requested input list and discharge
    `requested-inputs-accounted` from it: every requested input has either a
    source entry or an explicit recorded gap.
12. **Request materialization of the catalog delta.** Request, through
    **hal-coordinator**, that **hal-integrator** materialize the authored
    `SOURCES.md` delta and return its FileRef, and place that FileRef in
    `sources.catalog`. Durable evidence and notes are written before this, and
    the catalog is materialized and hashed before the handoff is written.
13. **Publish the preliminary handoff and validate it.** Publish the evidence
    FileRefs and the preliminary `01-sources`, preserving a hashed snapshot and
    recovery record of any deterministic handoff `state.toml` currently pins
    before replacing it, then run
    `python .opencode/schema/validate.py <repository-root> --kind all` again.
14. **Re-attest any changed bytes.** Re-attest when referenced bytes legitimately
    change: preserve the superseded evidence, create replacement evidence at a
    new path rather than overwriting one, rerun only the affected checks, and
    never delete an old evidence record to regain validation.
15. **Publish the final handoff and run the final gate.** Publish the final
    `halucinator/handoff/01-sources.toml`, run `python .opencode/schema/validate.py <repository-root> --kind all` over it, let **hal-coordinator**
    update `state.toml` through the compare-and-swap sequence — state is never
    updated before the handoff validates — and run the final `--kind all` gate.
16. **Return to hal-coordinator.** Return the target, the repository-relative
    documentation and catalog paths, the source IDs and availability summary,
    the gaps with their next actions, the selected route, and the status. State
    that intake validated no hardware fact and ran no hardware.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `available-content-resolves` | Inspect each available source's actual content and file type, not its extension | `<documentation>/notes/intake-availability.md` |
| `local-source-hashes` | Record a tool-computed SHA-256 for every locally stored source byte stream | `<documentation>/notes/intake-hashes.md`, or `reason (no evidence FileRef)` when `sources.documents` is empty |
| `requested-inputs-accounted` | Compare the requested input list against the completion inventory | `<documentation>/notes/intake-inventory.md` |
| `svd-search-complete` | Record the sites searched, the date and the outcome for the SVD lookup | `<documentation>/notes/intake-svd-search.md`, or `reason (no evidence FileRef)` off the author route |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. Typed evidence hashes
freshness, not relevance: a reviewer still judges whether an artifact discharges
the check it is attached to.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
`sources.route` is not `unresolved`, and every applicable check
(`requested-inputs-accounted`, `available-content-resolves`,
`local-source-hashes` where `sources.documents` is nonempty, and
`svd-search-complete` on the `author-from-docs` route) is `passed`. Ready means
the requested intake is accounted for; it does not mean a hardware fact is
established or that `02-facts` exists.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Useful intake or search can continue without an external action.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names an external identity, access or source
action that only somebody outside this stage can take.

## Application example

The emitted handoff for a target whose manual and datasheet are stored locally
and whose SVD search completed without a usable vendor file:

```toml
[handoff]
schema = 1
stage = "gather-documentation"
status = "ready"
inputs = []
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-inventory.md", sha256 = "3c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" }

[coverage]
complete = ["foundation:documentation-intake"]
incomplete = []

[sources]
catalog = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md", sha256 = "7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e" }
route = "author-from-docs"
cited_notes = []

[[sources.documents]]
source_id = "doc-001"
document = "FICTIONAL FIXTURE REFERENCE MANUAL"
revision = "fixture-1"
format = "pdf"
source = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/doc-001/fictional-reference-manual.pdf", sha256 = "91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80" }

[[sources.documents]]
source_id = "doc-002"
document = "FICTIONAL FIXTURE DATASHEET"
revision = "fixture-1"
format = "pdf"
source = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/doc-002/fictional-datasheet.pdf", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" }

[[checks]]
id = "requested-inputs-accounted"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-inventory.md", sha256 = "3c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }

[[checks]]
id = "available-content-resolves"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-availability.md", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }

[[checks]]
id = "local-source-hashes"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-hashes.md", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }

[[checks]]
id = "svd-search-complete"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-svd-search.md", sha256 = "d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4" }
```

A silicon revision the user could not supply is represented by the absence of
`target.silicon_revision` in state, not by a sentinel string. An input that was
searched for and not located is a recorded coverage gap plus a search-log row,
never a field whose value is the word for missing.

## Quick reference

| Element | Value |
|---|---|
| Stage | `gather-documentation` |
| Emitter | `hal-datasheet` |
| Emitted handoff | `halucinator/handoff/01-sources.toml`, kind `01-sources` |
| Consumes | nothing; this is intake |
| Checks | `available-content-resolves`, `local-source-hashes`, `requested-inputs-accounted`, `svd-search-complete` |
| Catalog | `SOURCES.md`, class `sources-catalog`, owned by `hal-integrator`; this skill supplies the delta |
| Routing | every question, gate and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, route not `unresolved`, applicable checks `passed` |

## Common mistakes

- **Writing `SOURCES.md` directly.** It is `hal-integrator`'s class. Author the
  delta, route it through `hal-coordinator`, and place the returned FileRef in
  `sources.catalog`.
- **Returning questions to the architect.** The architect is not in this
  stage's topology. Everything routes through `hal-coordinator`.
- **Calling an accessible SVD applicable.** `review-supplied` requires the file
  as a hash-pinned `source` FileRef on a `sources.documents` entry whose
  `source_id` is the catalog ID, with the remaining uncertainty recorded.
  Accessibility
  is not applicability, and relabelling an unsuitable file is the one intake
  error that survives all the way to generated Rust.
- **Publishing `ready` on the `unresolved` route.** The route is part of the
  predicate, not commentary.
- **Recording a sentinel for a value nobody supplied.** Optional means key
  absence and known-empty means an empty collection. A field whose value is the
  word `unknown` validates, reads as data, and is not data.
- **Treating a downloaded login page as a source.** Check content, not the
  filename, and discharge `available-content-resolves` from that inspection.
- **Claiming intake readiness implies fact readiness.** `01-sources` ready says
  the requested inputs are accounted for. `02-facts` is a separate stage with
  no skill in this toolkit yet.
