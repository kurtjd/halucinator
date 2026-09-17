---
name: write-time-driver
description: >-
  Use when implementing, resuming, testing, or reviewing an Embassy time driver
  for an exact MCU: monotonic timestamps, timer/RTC resource reservation, tick
  rates, counter rollover, queued alarm scheduling, and interrupt-driven wakeups.
  Supports hal-driver implementation and source-blind hal-tester validation
  through write-examples with independent timing evidence. Not a general timer,
  PWM, capture, or calendar API workflow.
compatibility: opencode
---

# Write Time Driver

Select the entry for your specialist role. **hal-architect** supplies the task,
scope, dependencies, and handoff; specialists select this skill. This is a
shared time service, not a bus driver instantiated for every timer future.

## Choose the role first

| Role | Read and follow |
|---|---|
| **hal-driver** | The implementation procedure below, [implementation checklist](./references/time-checklist.md), [public validation specification](./references/time-validation.md), and [record reference](./references/time-record.md). |
| **hal-tester** | For time-driver work, read only the [public validation specification](./references/time-validation.md) and supplied public material. Combine its cases and measurement requirements with `write-examples` for build/run/retest and public records. |
| **hal-reviewer** | The [implementation checklist](./references/time-checklist.md), [public validation specification](./references/time-validation.md), and actual review handoff as read-only audit criteria, not writing procedures. |

**Tester entry ends here.** Do not follow the implementation procedure, load
the private checklist or full time-driver record, or inspect HAL bodies.
Skill selection does not relax source blindness or other agent permissions.

## Implementation scope

The remaining procedure belongs to **hal-driver**. Record whether the architect
dispatched a full selected time service or bounded scaffold support:

- **Full time service:** the selected global timebase, scheduled wakeups, public
  integration, and required software plus independent hardware evidence.
- **Scaffold support:** only the time functionality needed by the selected
  foundation. Retain `scaffold-hal`'s complete foundation-PAC gate and build-only
  smoke check. This task requires its real dependencies, not an already finished
  scaffold, and does not imply full runtime validation of the service.

Limit work to the cited counter/timer/RTC resources and support needed for that
scope. Do not introduce general-purpose timer, PWM, capture, calendar, watchdog,
or unrelated DMA APIs. Sleep/clock-transition behavior is included only when
already required by the selected scope; otherwise record its limitations.
Do not copy the architect's temporary milestone into this reusable skill.

## Implementation procedure

### 1. Inspect and resume

Read `AGENTS.md` from the actual working repository root, not relative to the
skill installation. Use its artifact policy and the record reference to inspect
the handed-over target, prior decisions, scoped source/PAC coverage, and current
driver/build inputs. Preserve unrelated and dirty work; resolve conflicting
ownership instead of requiring a commit/stash or overwriting existing intent.
Ask only for missing decisions that block this scope.

### 2. Require live contracts and hardware evidence

Before the affected implementation, read:

- The live `embassy-mcxa/DEVGUIDE.md`, time-driver implementation identified by
  `AGENTS.md`'s concern map, and applicable init, clock, interrupt, singleton,
  feature, and build integration. Missing live references are blockers, not
  permission to copy a frozen template or use a remembered checkout.
- The actual `embassy-time-driver`, `embassy-time`, executor, and queue versions
  involved. Use the public validation reference's contract sources; do not
  impose an obsolete alarm interface or a new dependency version on the HAL.
- The supplied source list and cited notes for selected timer resources, clock
  rate/stability, counter encoding/width/read semantics, overflow service needs,
  compare/alarm behavior, interrupt acknowledgment, and supported power modes.
- Generated PAC provenance and the registers/accessors/metadata needed for
  those resources and their foundation dependencies. Missing structure returns
  through the architect to **hal-svd**; missing meaning to **hal-datasheet**.

Do not invent constants, replace missing PAC accessors with raw registers, or
hand-edit generated output. A missing in-scope foundation item during scaffold
support keeps the stricter all-scaffold-code block in force. Unrelated peripheral
omissions do not block verified time-service coverage.

### 3. Establish the service and implementation

Apply the implementation checklist against the selected live contracts and
hardware facts. Record decisions with citations and map them to the public TIME
requirements. Return work outside the assigned ownership through **hal-architect**
rather than widening the task to make a build or link pass.

Implement iteratively, following the checklist's production-arithmetic test
guidance and running focused checks after substantive edits. Do not substitute
successful stubs for the required service.

### 4. Return independent handoffs

Return to **hal-architect**, not directly dispatched subagents:

- **Tester:** the intake defined by the public validation reference and links
  to existing source-blind records, never implementation notes or bodies.
- **Reviewer:** changed files, versioned contracts, live/hardware citations,
  resource and ordering decisions, input identity, host/build results, and
  actual public tester evidence or blockers.

### 5. Verify and close the recorded scope

Derive commands and feature combinations from the live checkout. Require:

- Repository formatting/lint, selected target builds, and tests of pure
  arithmetic at meaningful boundaries, exhaustive for small legal domains.
- Tick-feature agreement, resource reservation, generated interrupt/mapping
  checks, and applicable incompatible-selection checks without indiscriminate
  `--all-features` or artificial future chip features.
- An actual source-blind target link using real public initialization and time
  consumers, with exactly one selected global driver and build-only CI coverage.
  `cargo check` alone cannot establish driver linkage.
- Independent **hal-reviewer** acceptance for the agreed surface. Required
  findings must be resolved by their owner and rechecked; unavailable or stale
  review, or `ready with fixes`, is not acceptance.

Apply the record's scope-specific completion criteria and separate
software/hardware statuses to the resulting evidence.

## Implementation output

Summarize target/scope, public service and resource/tick decisions, changed files
and citations, verification status and evidence links, separate handoffs, and
unresolved owners/actions. Attribute each result to what actually ran.
