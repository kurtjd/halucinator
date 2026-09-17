---
name: scaffold-hal
description: >-
  Use when starting or resuming the crate-level foundation for one exact MCU in
  a new Embassy HAL, after documentation and generated PAC work are available
  and before implementing the first planned peripheral driver.
compatibility: opencode
---

# Scaffold HAL

The owning agent is **hal-architect**. This stage produces a driver-ready,
software-verified foundation for one exact MCU. It does not produce a complete
HAL, implement the first planned peripheral, or prove behavior on silicon.

Read [the scaffold record reference](./references/scaffold-record.md) before
changing the HAL. Keep `SCAFFOLD.md` beside the explicitly handed-over
`SOURCES.md`; reuse an existing supplied scaffold record.

## Boundaries

- Start with one exact MCU and advertise only implemented chip features.
- Choose the first planned peripheral and its modes during intake. That driver
  is the next stage, not part of scaffolding.
- Implement one cited startup clock path. Do not expand into hypothetical PLL,
  dynamic-switching, low-power, or family-wide support.
- Include only supporting GPIO/pin mux, DMA, time-driver, or other subsystems
  required by that path and the first peripheral. Delegate them to
  **hal-driver** in dependency order.
- Keep clock/reset policy central: real `Gate`, `enable_and_reset`, and
  frequency plumbing are required. A no-op implementation or successful stub
  is not a scaffold.
- Do not change SVD/PAC schemas, hand-edit generated output, copy an MCXA
  hardware assumption, make automatic commits, publish, flash a board, or run
  hardware.

## Procedure

### 1. Inspect and resume safely

Inspect the Embassy repository root, worktree, destination crate, roadmap,
documentation handoff, PAC, and any partial scaffold before asking questions.
Read existing records first and reuse supplied answers. Ask short questions
only for missing or conflicting decisions.

Do not require a clean worktree, prerequisite commit, or stash. Preserve dirty
and unrelated edits. Reconcile overlapping changes explicitly; if ownership or
intent cannot be resolved, stop on that conflict rather than overwriting it.
Resolve repository-relative paths, symlinks, and existing parents before
writing, and confirm their resolved locations remain inside the actual working
repository. If a required record path is unavailable or escapes it, ask for
another in-repository path. Never fall back to a remembered target or another
repository.

On resume, compare the exact target, source revisions, PAC identity, bounded
scope, code/build inputs, toolchain, and features with `SCAFFOLD.md`. Changes
invalidate only dependent decisions and evidence. Preserve unaffected facts,
prior evidence, and blocker history; do not erase the record wholesale.

### 2. Fix the bounded scope

Record these decisions before implementation:

1. Embassy root, destination `embassy-<vendor>` crate, and exact MCU.
2. Package and board context, including unknowns.
3. One chip feature and compilation target for the initial MCU.
4. First planned peripheral and exact intended modes.
5. One documented startup clock path.
6. Only the supporting subsystems required by items 4 and 5.
7. Included and deferred work, exit criteria, and the roadmap path.

A board-specific clock or pin value is not a universal HAL default. An unknown
identifier blocks only decisions that depend on it. Keep one roadmap
authoritative; link it instead of copying the pipeline into `SCAFFOLD.md`. If
none exists, **hal-architect** establishes one repository-local roadmap and
records its location.

**Scope counter:** pressure to "finish the UART end to end" does not move UART
into this stage. Record blocking/async/DMA as its planned modes, scaffold only
their necessary foundations, and hand the UART driver to the next stage.

### 3. Gate implementation on evidence

Require all of the following before changing scaffold code:

- The live `embassy-mcxa/DEVGUIDE.md` and the concern-specific MCXA files named
  by `AGENTS.md` in this Embassy checkout. Read the corresponding files for the
  actual run and cite relevant DEVGUIDE sections; do not use this toolkit as a
  frozen substitute.
- The explicitly handed-over repository-relative documentation directory,
  `SOURCES.md`, applicable source IDs, and cited hardware-note paths. Hardware
  citations retain title/document number, revision, and section/table/page.
- A generated PAC whose provenance, version or revision, chip feature,
  interrupt/peripheral metadata, and foundation coverage have been checked.
- Cited facts for the selected clock/init path and memory/link requirements,
  plus pin and board facts when the bounded scope uses them.

Verify coverage, not mere PAC availability. Unrelated peripheral omissions do
not block scaffolding. However, one missing register, accessor, interrupt, or
metadata item required by clocks, reset, init, generated singleton/interrupt
mapping, memory, or a required supporting subsystem blocks **all scaffold code
implementation**, including the manifest, codegen wiring, crate root, and chip
module. Until **hal-svd** supplies verified complete foundation coverage, only
intake, record maintenance, inspection, and analysis may continue. Missing
hardware meaning returns to **hal-datasheet**. Do not bridge either gap with raw
register access or invented constants.

A personal PAC fork permitted by `AGENTS.md` may support local work in
progress. It cannot support status `software verified` or a completed handoff.
Replacing it with a permitted upstream released version or revision, rechecking
foundation coverage, and rerunning affected evidence clears this current
blocker; preserve the fork history without treating it as permanent taint.

### 4. Read the live patterns and record decisions

Use the concern map in `AGENTS.md`. At minimum, inspect the live MCXA DEVGUIDE,
manifest, build integration, crate root, selected chip structure, clocks gate
and helper implementation, the relevant init/time/supporting subsystem files,
examples, CI, toolchain, and contribution rules. Follow documented intent over
a local accident.

Record architectural decisions with live MCXA file or DEVGUIDE citations and
hardware decisions with source IDs plus hardware citations. Apply the type
discipline from `AGENTS.md`: keep calculations pure, reject invalid public
inputs, use meaningful finite types at call boundaries, test small domains
exhaustively, and avoid typestate or newtypes that encode no plausible caller
mistake.

### 5. Implement the architect-owned foundation

**hal-architect** owns:

- `Cargo.toml`, Embassy package/docs metadata, and the single-MCU feature
  policy;
- build/code-generation integration without editing generated output;
- crate-root modules, singleton `peripherals!`, and `interrupt_mod!` plumbing;
- chip-specific structure needed by the selected MCU;
- top-level configuration and `init` policy; and
- the public clocks boundary and dependency order.

Implement initialization against cited hardware. `init` must select and apply
the agreed clock path and return real peripheral tokens. Required drivers must
reach clock/reset through the central `Gate` and `enable_and_reset` contract,
including the usable frequency result and any lifetime guard required by the
live pattern. Do not make incomplete initialization compile by returning
success from no-op clock, reset, GPIO, DMA, or time functions.

### 6. Delegate supporting subsystems

Dispatch one **hal-driver** task per required supporting subsystem, in
dependency order, with:

- exact MCU, file ownership, and bounded behavior;
- applicable source IDs and cited-note paths;
- relevant live MCXA files and DEVGUIDE sections;
- PAC identity and required registers/interrupt metadata;
- the public contract it must satisfy; and
- host-test expectations for pure configuration, encoding, and arithmetic.

GPIO/pin mux, DMA, and a time driver are included only when the selected path
or first planned peripheral needs them. Link each subsystem's selected record
from `SCAFFOLD.md`; specialists select their own applicable skills. The first
peripheral itself remains a separate, later **hal-driver** dispatch. If a
required specialist is unavailable, record the blocked delegation and next
action; do not impersonate it or claim it ran.

### 7. Obtain a source-blind link check

Give **hal-tester** only the public API/contracts and cited build/board facts:

- exact chip feature, compilation target, and public initialization calls;
- public configuration and peripheral-token signatures, without bodies;
- cited memory/runtime/link information and any public observation facility;
- applicable board facts and source IDs; and
- claimed feature combinations and expected build-only CI placement.

Request a minimal target binary that calls real initialization and links,
build-only CI wiring, and a public setup/hardware-validation handoff for a later
**hal-tester** task. Mark the dispatch **build-only scaffold support**.
Never send HAL source,
function bodies, copied implementation files, or an LSP response exposing
bodies. Do not invent an unrelated logging driver merely to print success;
debugger observation or an already available public facility is sufficient.
For this scaffold check, the tester compiles and links but does not load, flash,
or run the binary on hardware. Separately dispatched runtime validation follows
`AGENTS.md`'s "Hardware testing" policy; it is not implied by this link check.

### 8. Verify, review, and close

Derive commands, working directories, targets, and feature combinations from
the live checkout. Record every run's time, command, cwd, features, observed
outcome, and tested-state identity. Use the commit plus tool-computed hashes of
relevant dirty and untracked inputs, or an equivalent content snapshot; HEAD
alone is insufficient in a dirty tree, and `SCAFFOLD.md` itself is not an input
unless it affects the check. Do not require a commit or stash. If identity
cannot be established, mark the evidence unverified and rerun before closure;
never invent a timestamp or hash.

Do not change inputs during a check or review. If code, build inputs, toolchain,
or features change, invalidate dependent evidence and review findings, preserve
their history, and rerun before clearing blockers.
All applicable checks below are required for `software verified`:

- formatting and lint for touched code under repository policy;
- builds for the advertised MCU and every in-scope option;
- negative chip-selection checks for missing or incompatible selection where
  applicable, without indiscriminate mutually-exclusive `--all-features` or
  fake future chip features;
- host tests for pure clock/configuration/encoding logic, exhaustive for small
  legal domains and covering invalid boundaries and arithmetic limits;
- generated singleton, interrupt, and build mappings checked against PAC
  metadata, without editing generated output;
- an actual target link of the source-blind smoke binary using cited
  memory/runtime facts (`cargo check` alone is insufficient);
- relevant build-only CI coverage, with no hardware runner invoked; and
- independent **hal-reviewer** review of the full agreed foundation.

Resolve every required blocking review finding through its owner, then rerun
checks affected by the change and obtain reviewer recheck where needed.
`ready with fixes`, an unresolved required finding, or an unreviewed required
surface is not acceptance. Missing tools, link evidence, live references, or
required dispatches leave a named blocker; they do not lower the gate.

Use only these statuses:

| Status | Meaning |
|---|---|
| `in progress` | Work or applicable software evidence remains. |
| `blocked` | A named dependency, conflict, tool, link, or required review prevents progress or closure. |
| `software verified` | Every applicable software gate passed and required review findings were resolved and rechecked. |

Deferred out-of-scope work and pending separately dispatched hardware validation
do not prevent `software verified` for this scaffold scope. That status is not
proof of silicon behavior, a complete peripheral driver, or upstream acceptance.

## Concise application example

For exact MCU `VND1234`, suppose `SOURCES.md` and cited notes cover its reset,
internal-oscillator startup, SRAM layout, UART0 pins, and DMA request, while the
generated PAC covers those foundation registers but lacks ADC metadata. Plan
UART0 in blocking and DMA modes. Scaffold only `VND1234`, the documented
internal-oscillator path, central gate/reset/frequency plumbing, pin mux, and
DMA support; the ADC gap does not block. Hand the UART0 driver to the next
stage. The stage remains `blocked` until the smoke binary links and independent
review findings are resolved, even if the library already passes `cargo check`.

## Quick reference

| Question | Answer |
|---|---|
| PAC has unrelated gaps? | Continue if verified foundation coverage is complete. |
| Required foundation PAC item missing? | Block all scaffold code; only intake, records, inspection, and analysis continue until **hal-svd** closes it. |
| Hardware fact or citation missing? | Block affected decision and return to **hal-datasheet**. |
| Dirty worktree? | Preserve it; reconcile actual overlaps without commit/stash demands. |
| Source or PAC revision changed? | Invalidate and rerun only dependent evidence. |
| First peripheral requested now? | Record its modes and dependencies; driver remains next stage. |
| Tester needs context? | Send public signatures/contracts and cited facts, never bodies. |
| Clean check but no link/tests/review? | Not `software verified`. |
| Required agent/reference unavailable? | Record `blocked`; never fabricate completion. |

## Common mistakes

- Advertising a chip family because the crate layout anticipates one. Support
  starts with the one implemented feature.
- Treating PAC presence as proof that foundation registers and metadata exist.
- Continuing manifest or structural scaffold code after any required foundation
  PAC item is found missing.
- Copying MCXA register choices instead of copying its architectural pattern.
- Adding successful no-op init or clock stubs to reach a green build.
- Pulling the first planned peripheral into scaffold scope.
- Giving **hal-tester** implementation source or running hardware as part of
  this build-only scaffold smoke check.
- Treating `cargo check`, `ready with fixes`, or stale evidence as completion.
- Requiring dirty user work to be committed or stashed before proceeding.
- Invalidating every old hardware claim when only one source changed.
- Duplicating the roadmap inside `SCAFFOLD.md`.

## Completion output

Return:

1. **Target and bounded scope**: exact MCU, chip feature/target, clock path,
   supporting subsystems, and first peripheral/modes reserved for next stage.
2. **Files and decisions**: changed files plus live MCXA/DEVGUIDE and hardware
   citations.
3. **Delegation**: each specialist result, including blocked or unavailable
   dispatches.
4. **Verification**: commands, cwd, features, outcomes, link artifact, CI, and
   independent review disposition.
5. **Records**: repository-relative `SOURCES.md`, `SCAFFOLD.md`, and roadmap
   paths.
6. **Status and handoff**: `in progress`, `blocked`, or `software verified`,
   blockers with owners/actions, and the next peripheral-driver prompt inputs.

Report this scaffold's verification as build-only; link any separate hardware
results without merging the two.
