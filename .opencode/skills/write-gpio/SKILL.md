---
name: write-gpio
description: >-
  Use when implementing, resuming, testing, or reviewing GPIO for an exact MCU
  in an Embassy HAL: digital input/output, pin ownership and mux, GPIO interrupts,
  embedded-hal digital traits, embedded-hal-async Wait, and hardware loopback
  validation. Supports hal-driver implementation and source-blind hal-tester
  validation, including documented user setup and agent-run hardware tests.
compatibility: opencode
---

# Write GPIO

Select the entry for your specialist role. **hal-architect** supplies the task
and bounded scope; the specialist selects this skill.

## Choose the role first

| Role | Read and follow |
|---|---|
| **hal-driver** | The implementation procedure below, [implementation checklist](./references/gpio-checklist.md), [public validation specification](./references/gpio-validation.md), and [record reference](./references/gpio-record.md). |
| **hal-tester** | Only the [public validation specification](./references/gpio-validation.md) and the supplied public API, cited hardware/board/build facts, and permitted example/build files. Follow that reference's intake, setup, execution, and output procedure. |
| **hal-reviewer** | The [implementation checklist](./references/gpio-checklist.md) and [public validation specification](./references/gpio-validation.md) as read-only audit criteria, plus the actual review handoff and live references. Do not run a writing procedure. |

**Tester entry ends here.** Do not follow the implementation procedure, load its
checklist or full GPIO record, inspect HAL bodies, or satisfy implementation-only
source-reading gates. Skill selection does not change agent permissions.

## Implementation scope

The rest of this file is for **hal-driver**, with acceptance coordinated by
**hal-architect**. Use one of the architect's explicitly recorded scopes:

- **Full GPIO task:** the selected MCU/pin/mode surface, including supported
  interrupt-driven async and the full `embedded_hal_async::digital::Wait`
  contract unless the user explicitly bounds that task otherwise. Required
  source-blind hardware validation is part of completion.
- **Scaffold support:** only the GPIO/pin-mux support required by the selected
  foundation. Preserve `scaffold-hal`'s foundation-PAC gate and build/link-only
  smoke check. This subset neither requires a finished scaffold before starting
  nor constitutes completion of the later full GPIO task or HIL matrix.

No unrelated alternate-function drivers, generic pin-control framework, timers,
PWM, DMA, debounce, or low-power expansion. Consume the concrete scope from the
architect rather than copying its temporary milestone into this reusable skill.

## Implementation procedure

### 1. Inspect and resume

Inspect the architect's handoff, live checkout, existing GPIO/scaffold records,
and relevant dirty edits. Establish identity, scope, and locations using the
record reference, and apply its resumption rules before implementation. Preserve
unrelated edits and resolve overlapping intent rather than overwriting it.
Ask only for missing/conflicting facts; unknown board wiring blocks only
decisions that depend on it.

### 2. Gate on live evidence

Before driver implementation, require:

- The live `embassy-mcxa/DEVGUIDE.md` and the actual GPIO/pin-mux implementation
  in this checkout. Discover its layout instead of assuming a particular module
  path. Read relevant init, singleton/codegen, interrupt, clock, example, and
  build conventions. Missing live references block implementation; this toolkit
  is not a snapshot substitute.
- The supplied documentation directory, `SOURCES.md`, relevant source IDs and
  cited notes, with provenance recorded as specified in the record reference.
- Generated PAC provenance and checked coverage for the selected GPIO/pin mux,
  clock/reset dependencies, interrupts, and generated pin mappings. Missing
  required accessors or metadata return through the architect to **hal-svd**;
  no raw-register workaround or generated-code edits.
- Cited mode encodings, electrical capabilities, pin availability, reset/init
  behavior, shared-resource and interrupt semantics, and a usable central
  clock/reset contract. Missing hardware meaning returns to **hal-datasheet**.

Do not begin the affected implementation without its required evidence. During
a scaffold-support dispatch, any missing foundation PAC item retains the
stricter all-scaffold-code block from `scaffold-hal`. Unrelated peripheral gaps
do not block a covered GPIO scope. Record named blockers and owners rather than
silently dropping async or inventing constants.

### 3. Establish contracts

Apply the implementation checklist and record decisions with live-reference
and hardware citations. Map the public validation requirement IDs to selected
capabilities and planned evidence using that reference's applicability rules.
Return changes outside the assigned ownership, including shared init/build
contracts, through **hal-architect** rather than widening the task.

### 4. Implement and check locally

Implement digital operations and supported interrupt-backed waits against the
checklist and public contracts, including the checklist's host-test guidance.
After each substantive change, run the cheapest relevant host test or trait/build
check. Derive commands and features from the live checkout, not an indiscriminate
mutually exclusive `--all-features` invocation. Repair only the owned slice.

### 5. Return independent handoffs

Return these to **hal-architect**, not directly dispatched subagents:

- **Tester handoff:** the intake specified by the public validation reference,
  plus applicable source-blind setup/run material. Never send the private
  implementation record.
- **Reviewer handoff:** changed implementation and build files, live reference
  and hardware citations, public requirement mapping, current input identity,
  software results, and the tester's actual results or named blockers.

### 6. Review and close the recorded scope

All applicable software gates require current evidence:

- Repository formatting/lint and builds for the advertised in-scope features.
- Tests of useful pure logic, upstream trait conformance, and applicable
  ownership/capability rejection checks using existing test infrastructure.
- Generated pin/peripheral/interrupt mappings checked against cited metadata,
  without hand-editing generated output.
- An actual source-blind target link using public initialization and GPIO traits,
  with relevant build-only CI coverage; `cargo check` alone is not a link.
- Independent **hal-reviewer** acceptance of the full agreed surface. Required
  findings must be resolved through their owner and rechecked; `ready with
  fixes`, stale review, or an unavailable reviewer is not acceptance.

Apply the record reference's status and scope-specific completion criteria.
It keeps the software gate above separate from the public matrix's HIL results
and defines which evidence must be renewed after changes.

## Implementation output

Summarize the updated GPIO record: scope and public API, changes and citations,
software/hardware statuses, evidence links, unresolved owners/actions, and next
stage. Include the separate handoffs above and attribute each result to the
agent and environment that actually ran the check.
