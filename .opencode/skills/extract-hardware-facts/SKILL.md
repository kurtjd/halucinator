---
name: extract-hardware-facts
description: >-
  Use when hal-coordinator dispatches cited hardware-fact extraction from a
  ready 01-sources handoff, or when a previous 02-facts handoff stopped at
  partial or blocked. Dispatch and search terms: pdftotext -layout, register
  layout, field encodings, clock and reset dependencies, initialization
  sequences, interrupts, pin mux, errata, contradictions, CitationRef,
  02-facts handoff. Wrong for collecting documents, choosing SVD
  representation, generating a PAC, designing APIs, writing HAL code, or
  mechanically verifying citation truth.
compatibility: opencode
---

# Extract hardware facts

```halucinator-skill-contract
stage: extract-facts
participants: hal-datasheet
emitter: hal-datasheet
emits: 02-facts|halucinator/handoff/02-facts.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,facts.categories,facts.citations.document,facts.citations.locator,facts.citations.note,facts.citations.revision,facts.citations.source_id,facts.contradictions,facts.notes,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision
checks: citations-complete,field-encodings-exhaustive,pdf-layout-extraction,summary-field-cross-check
consumes: 01-sources|coverage.complete,coverage.incomplete,handoff.blockers,handoff.inputs,handoff.notes,handoff.status,scope.decision,scope.revision,sources.available,sources.catalog,sources.cited_notes,sources.route,sources.source_ids
writes: hal-datasheet|fact-notes
writes: hal-datasheet|facts-handoff
writes: hal-datasheet|vendor-extractions
supplies-delta: hal-datasheet|sources-catalog
```

This stage turns collected documentation into cited hardware assertions and a
reproducible typed handoff. It does not choose a register representation, emit
XML or Rust, or decide scope.

## When to use

Use this skill when **hal-coordinator** dispatches `extract-facts` for a target
whose `01-sources` handoff validates, or when a previous run left `02-facts` at
`partial` or `blocked` and the recorded next action is now possible.

Typical triggers: a driver stage needs a register layout the manual describes
badly; `generate-svd` on the `author-from-docs` route needs cited findings; a
field enumeration was reported as partial; a contradiction between a register
summary table and the per-field description needs recording.

Extract only the documented scope supplied for this run, and report partial
coverage as partial rather than as whole-chip understanding.

## Ownership and boundaries

The owning agent is **hal-datasheet**. It materializes three ownership classes:
`vendor-extractions`, the layout-preserving text under
`<documentation>/extracted/`; `fact-notes`, the cited record at
`<documentation>/notes/FACTS.md` plus `<documentation>/notes/facts/**` and
`<documentation>/notes/fact-checks.md`; and `facts-handoff`, the deterministic
`halucinator/handoff/02-facts.toml`.

`SOURCES.md` is class `sources-catalog` and is owned by **hal-integrator**.
This skill authors the catalog delta that registers new extractions and fact
notes; **hal-coordinator** dispatches **hal-integrator** to materialize it and
returns its FileRef. Never write that file directly.

**hal-datasheet does not choose a representation.** Namespace policy, SVD
transforms and PAC metadata belong to `hal-svd`. Do not design an API, do not
decide scope, do not write driver logic, and do not read a register value out of
a vendor SVD or a generated PAC and record it as a cited manual finding. A PAC
disagreement is worth recording as a contradiction; it is not a citation.

Every question, review request, gate and next-stage dispatch routes through
**hal-coordinator**.

## Inputs

Consume the validated `01-sources` leaves declared in the contract:
`handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`,
`scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete`,
`sources.catalog`, `sources.route`, `sources.source_ids`, `sources.available`
and `sources.cited_notes`. Also read coordinator-owned state: the `target.*`
identity, `scope.current_revision`, `scope.current_decision`, and the
`roots.documentation` and `roots.sources` bindings.

A `blocked` predecessor permits no consumption at all. A `partial` one permits
read-only inspection and disposable fresh extraction only — no canonical
replacement and no downstream `ready`. An `unresolved` `sources.route` admits
nothing. These rules are restated from
[the common handoff contract](../../schema/handoff-common.md); the emitted kind
and its canonical checks are defined in [`02-facts.md`](../../schema/02-facts.md).

Source documents are the reference manual for register detail, the datasheet for
electrical limits and maximum frequencies, the errata for silicon deviations,
and the board guide and schematic for pin mapping. They are different documents
with different jobs; a locator must name the one it came from.

## Outputs

- Layout-preserving extractions under `<documentation>/extracted/`, plus the
  `pdftotext -layout` command log naming input, page range and output.
- The cited fact record at `<documentation>/notes/FACTS.md` and the per-topic
  notes under `<documentation>/notes/facts/`, each assertion carrying its source
  identity, document revision, locator and a quoted supporting excerpt.
- The cross-check record at `<documentation>/notes/fact-checks.md`.
- A `SOURCES.md` delta authored here and materialized by **hal-integrator**.
- `halucinator/handoff/02-facts.toml`, carrying `facts.notes`,
  `facts.citations`, `facts.categories`, `facts.contradictions`, the four
  canonical checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering this stage
   and its extraction and catalog resources, and classify entry state as live,
   interrupted or ambiguous. Live means concurrency: do not interfere. Ambiguous
   means wait one 30-second refresh interval, reread, and fail closed if it is
   still ambiguous. Interrupted, or ambiguous still unresolved, means recovery:
   do not mutate the suspect output, inventory and hash it into a recovery
   Markdown FileRef, compare it against the last valid handoff, and publish
   `partial` with empty blockers when unaffected fresh extraction remains or
   `blocked` with an `interrupted:extract-facts` blocker when it does not.
   Record the comparison, the disposition and the new extraction location before
   an authorized actor removes the lock. Resume only in a fresh location, never
   in place.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `01-sources`.
   Exit 0 with silent output is necessary; a missing interpreter, a timeout, a
   nonzero exit, or not running it is not a pass and blocks consumption. Report
   an unrelated stale artifact or an ambiguous unrelated lock as a named blocker
   rather than stepping over it.
3. **Load the admitted sources.** Load exactly the contract leaves, resolve each
   admitted document through its source ID in `sources.source_ids`, and confirm
   it is accessible at the recorded path with the recorded hash. Reject an
   `unresolved` route, stop on a `blocked` predecessor, and restrict a `partial`
   predecessor to fresh disposable extraction.
4. **Select the cited scope.** Select only the register, clock/reset/power
   dependency, interrupt, pin-mux, errata and memory/runtime facts the scope
   decision includes, and map each to a scope item ID so coverage can be
   reported per item rather than per chapter.
5. **Generate layout-preserving extraction.** Run `pdftotext -layout` over each
   PDF source, extracting located page ranges rather than whole manuals, and
   record the exact command, input FileRef, page range and output path into the
   extraction log. Discharge `pdf-layout-extraction` from that log; record it
   `not-applicable` with a reason only when no input path ends `.pdf`. If a
   table is still mangled after `-layout`, quote the raw extraction and record
   the defect — never reconstruct the intended alignment.
6. **Record cited assertions.** Record every assertion into the hashed fact
   notes with its source ID, document title, document revision, locator
   (section, table or page), the scope item it applies to, the claim itself, and
   a **quoted supporting excerpt** copied from the layout-preserving extraction.
   The excerpt is the evidence a later citation-verification stage will check;
   it is carried here and is not mechanically verified here. Record locators as
   you go, not afterwards from memory.
7. **Compare summaries and field detail.** Compare each register summary table
   against the per-register and per-field descriptions — offset, width, reset
   value, access — and discharge `summary-field-cross-check` from the comparison
   record. Record it `not-applicable` with a reason only when the
   `register-layout` category is absent. A disagreement is a finding, not a
   choice: record both readings.
8. **Record exhaustive encodings.** Record every legal encoding and every
   reserved encoding of each described field, with the meaning the manual gives
   it, and discharge `field-encodings-exhaustive` from that enumeration. Record
   it `not-applicable` with a reason only when the `field-encodings` category is
   absent. A field reported as having N legal values without all N having been
   read produces an enum that panics on real silicon.
9. **Record dependencies and sequences.** Record the clock, reset and power
   dependencies each peripheral needs, its frequency and voltage limits, the
   ordered initialization and teardown sequences with their documented wait
   conditions, the interrupt numbers and flag-clear semantics, the pin mux
   options, and every applicable erratum with its documented workaround.
10. **Record contradictions and citation coverage.** Populate
    `facts.contradictions` with every disagreement found between documents,
    between a summary and its detail, or between a document and a generated PAC,
    and discharge `citations-complete` by comparing each recorded assertion
    against its source identity, locator and supporting note. An assertion
    without all five CitationRef fields is not complete.
11. **Request catalog materialization.** Request, through **hal-coordinator**,
    that registry owner **hal-integrator** materialize the `SOURCES.md` delta
    registering the new extraction and fact-note locations, and return its
    FileRef. Durable evidence and notes are written first; the catalog is
    materialized and hashed before the final handoff.
12. **Publish the preliminary handoff and validate it.** Write the durable notes
    and evidence, preserve a hashed snapshot and recovery record of any
    deterministic handoff `state.toml` currently pins before replacing it,
    publish the preliminary `02-facts`, and run
    `python .opencode/schema/validate.py <repository-root> --kind all` again.
13. **Re-attest and publish the final handoff.** Preserve the superseded
    evidence and review records, create replacement evidence at a **new** path
    rather than overwriting one, rerun only the affected checks, publish the
    final `halucinator/handoff/02-facts.toml`, validate it, let
    **hal-coordinator** update `state.toml` through the compare-and-swap
    sequence — state is never updated before the handoff validates — and run the
    final `--kind all` gate. Never delete an old record to regain validation.
14. **Return to hal-coordinator.** Return the record paths, the target and
    scope, the categories recorded, the contradictions, the checks including
    every `unrun` one, the status and the next action. State explicitly that no
    representation was chosen, no code was emitted and no hardware was operated.

`pdftotext -layout` is mandatory because register-table meaning lives entirely
in the column alignment; without it the extraction interleaves columns and
produces noise that still looks like data, which is how invented offsets reach
code. The validator wiring in steps 2, 12 and 13 is an **honor system**: the
self-check can prove this skill contains the instruction, but it cannot prove an
agent ran it, and `validate.py` cannot attest to its own earlier invocation. It
is evidence discipline, never enforcement.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `citations-complete` | Compare every assertion with its source identity, locator and supporting note | `<documentation>/notes/fact-checks.md` |
| `field-encodings-exhaustive` | Compare every described field with all legal and reserved encodings | `<documentation>/notes/facts/field-encodings.md`, or `reason (no evidence FileRef)` when the category is absent |
| `pdf-layout-extraction` | Run `pdftotext -layout` and record the command, input and page range | `<documentation>/extracted/pdf-layout-extraction.log`, or `reason (no evidence FileRef)` when no input is PDF |
| `summary-field-cross-check` | Compare register summaries with detailed register and field descriptions | `<documentation>/notes/fact-checks.md`, or `reason (no evidence FileRef)` when register layout is absent |

Typed evidence hashes freshness, not relevance. None of these checks establishes
that a locator names a section that exists or that an excerpt was copied rather
than composed. **This skill claims no mechanical citation verification.** What it
guarantees is that `02-facts` *carries* the material such verification needs: a
per-fact source ID, document revision and locator in the CitationRef, and a
quoted supporting excerpt in the hashed fact note. The residual gap is named
under Common mistakes and is a confirmed escalation, not an oversight.

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
the `01-sources` input is `ready`, every recorded assertion carries a complete
CitationRef, and every applicable check is `passed`.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. Only fresh disposable extraction continues; no canonical replacement
and no downstream `ready`.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. A blocker names an external fact, document, tool or access
action — an undelivered manual chapter, an inaccessible errata document, or an
absent extraction capability.

A recorded contradiction does not by itself prevent `ready`: it is a finding the
downstream stage must see. An assertion the documents do not support does
prevent it, and the remedy is incomplete coverage, never a plausible value.
Never narrow the declared scope after a failed run to reach `ready`.

## Application example

The emitted handoff for the fictional fixture target
`unobtainium-circuits-uc-not-a-real-mcu-0001`, extracted from one PDF source:

```toml
[handoff]
schema = 1
stage = "extract-facts"
status = "ready"
inputs = [
  { path = "halucinator/handoff/01-sources.toml", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/doc-001/fictional-reference-manual.pdf", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" }

[coverage]
complete = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]
incomplete = []

[facts]
notes = [
  { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" },
]
categories = ["dependencies", "field-encodings", "interrupts", "register-layout"]
contradictions = []

[[facts.citations]]
source_id = "doc-001"
document = "FICTIONAL FIXTURE REFERENCE MANUAL"
revision = "fixture-1"
locator = "Fictional section 1, fictional page 1"
note = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/facts/schema-demo.md", sha256 = "5555555555555555555555555555555555555555555555555555555555555555" }

[[checks]]
id = "citations-complete"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/fact-checks.md", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }

[[checks]]
id = "field-encodings-exhaustive"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/facts/field-encodings.md", sha256 = "7777777777777777777777777777777777777777777777777777777777777777" }

[[checks]]
id = "pdf-layout-extraction"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/extracted/pdf-layout-extraction.log", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }

[[checks]]
id = "summary-field-cross-check"
status = "passed"
evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/fact-checks.md", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }
```

The direct PDF entry in `handoff.inputs` is what makes `pdf-layout-extraction`
applicable. With no PDF input, that entry carries `status = "not-applicable"`
with a `reason` naming the absence of a PDF source — never a sentinel value in
place of a missing field. The same rule governs the two category-conditional
checks when `register-layout` or `field-encodings` is absent from
`facts.categories`.

## Quick reference

| Element | Value |
|---|---|
| Stage | `extract-facts` |
| Emitter | `hal-datasheet` |
| Emitted handoff | `halucinator/handoff/02-facts.toml`, kind `02-facts` |
| First note | `<documentation>/notes/FACTS.md` |
| Consumes | `01-sources` |
| Checks | `citations-complete`, `field-encodings-exhaustive`, `pdf-layout-extraction`, `summary-field-cross-check` |
| Categories | `register-layout`, `field-encodings`, `dependencies`, `interrupts`, `errata`, `pin-mux`, `memory-runtime` |
| Mandatory tool | `pdftotext -layout`, with page ranges and a recorded command log |
| Catalog | `SOURCES.md`, class `sources-catalog`, owned by `hal-integrator`; this skill supplies the delta |
| Routing | every question, review request, gate and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write; honor system |
| Ready | empty incomplete, complete equals included scope, `can_progress` absent, empty blockers, complete CitationRefs, applicable checks `passed` |

## Common mistakes

- **Extracting without `-layout`.** The converter exits zero and produces
  plausible-looking text with the columns interleaved. Offsets read from that
  text are invented facts wearing a citation.
- **Recording a locator from memory after reading the chapter.** Locators drift
  by a section or a table number, and the drift is invisible until someone tries
  to reread the source. Record each locator at the moment of reading.
- **Citing the PAC or a vendor SVD as a manual.** A generated artifact is a
  second reading, not a source. A disagreement between it and the manual belongs
  in `facts.contradictions`.
- **Interpolating an offset from a neighboring register.** Sequential registers
  are not reliably sequential, and the interpolated value compiles.
- **Enumerating a field partially.** Reporting N legal encodings without having
  read all N, and omitting the reserved ones, produces an enum that panics on
  hardware. `field-encodings-exhaustive` means exhaustive.
- **Resolving a contradiction by choosing.** Picking the reading that looks
  right discards exactly the signal the next stage needs. Record both and say
  which document each came from.
- **Treating a complete CitationRef as a verified one.** Every field can be
  nonempty and syntactically plausible while the section number is fabricated.
  Schema 1 also has no field binding one assertion to one excerpt — the excerpt
  lives in the hashed note, and only a human or a later stage can compare the
  two. Full citation verification is escalated, not implemented; do not write
  prose implying this stage performs it.
- **Marking an `unrun` check `not-applicable` to reach `ready`.** A missing
  extraction tool makes a check `unrun` and the handoff `partial`. Relabelling
  it as inapplicable deletes the remedy record.
- **Choosing a representation here.** Namespace policy, transforms and metadata
  belong to `hal-svd`. Naming them here creates a second place that decision can
  be made.
- **Overwriting an extraction to rerun a check.** Replacement evidence goes to a
  new path; the superseded record is preserved.
