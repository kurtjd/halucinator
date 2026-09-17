---
name: generate-pac
description: >-
  Generate or regenerate a Rust peripheral access crate for an Embassy HAL
  from a checked SVD preparation handoff. Use for PAC generator setup, metapac
  assembly, Cargo packaging, missing generated accessors or metadata, and
  resuming incomplete PAC generation. Does not prepare SVDs, invent hardware
  facts, implement HAL drivers, or publish crates.
compatibility: opencode
---

# Generate PAC

The owning agent is **hal-svd**. This stage produces a usable, reproducible
PAC for the declared scope, not just emitted Rust files. **hal-architect**
supplies the checked preparation handoff and consumer requirements, coordinates
missing evidence and independent review, and gates progression to `scaffold-hal`.

Read [Generation and Checks](./references/generation-and-checks.md) before
selecting commands, metadata structure, or output paths.

## Boundaries

- Start with one exact MCU/core and the approved functionality, dependencies,
  and exclusions. Prefer shared peripheral-IP definitions plus per-chip
  metadata for new work. A reusable structure is not family-wide support.
- Never hand-edit generated Rust or extracted YAML. Fix authoritative source
  inputs, metadata, or generator/setup templates, then regenerate. Register
  description changes return to `generate-svd`; missing hardware meaning goes
  through **hal-architect** to **hal-datasheet**.
- Own PAC packaging and its advertised build configurations under the
  architect's feature policy. Do not implement the HAL or change its dependency
  declaration here.
- Do not extract PDFs, install or upgrade tools automatically, commit, publish,
  flash, or run target code. No direct subagent dispatch from **hal-svd**.
  Target-link smoke binaries and bench work retain their downstream owners.

## Procedure

### 1. Resume the checked handoff

Load the handed-over `SOURCES.md` and preparation note, reusing their target
and scope. Verify the admission checklist and input identities in the
[Establish reproducible inputs](./references/generation-and-checks.md) section
after the architect's preparation gate. Missing or stale required evidence
blocks generation and returns through **hal-architect**; changed inputs
invalidate dependent checks and review, not unrelated history.

### 2. Select paths and protect existing work

Reuse preparation's selected PAC project under `AGENTS.md`'s storage policy.
Apply the checks in the [Project paths and ownership](./references/generation-and-checks.md) section
before commands. Record stable locations in `SOURCES.md` and exact run paths in
the generation record and handoff. An absent generator or crate is normal on
the first run, not a prerequisite failure.

### 3. Establish the generation route

Read the live MCXA DEVGUIDE and relevant manifest/build-metadata consumers,
then inspect the selected generator and schema using the
[Inspected reference implementation](./references/generation-and-checks.md) section.
Cite live source or DEVGUIDE sections for architectural decisions. Reuse an
applicable generator and its pins, or establish minimal tooling for the approved
scope using chiptool's backend. Do not copy NXP hardware/runtime assumptions or
create a universal generator framework.

### 4. Assemble source-backed metadata and packaging

Build the inventory from checked preparation and cited consumer requirements
using the [Expected inventory and metadata](./references/generation-and-checks.md)
and [Representation limits](./references/generation-and-checks.md) sections.
Follow the reference's reproducible input-promotion and crate-setup procedure.
Include the required target/runtime and host metadata interfaces; generated
APIs and metadata must match the approved scope while preserving unrelated
existing support.

### 5. Generate and check a candidate

Generate into a fresh isolated candidate, preserving diagnostics and the live
crate. Apply every required gate in the [Check applicability](./references/generation-and-checks.md)
section using the procedures in [Builds and pure checks](./references/generation-and-checks.md).
Compilation alone is not completeness evidence. Fix the owning input or
generator and rerun, or return the blocker; do not narrow scope after a failure
without the architect's approval.

### 6. Replay and integrate verified output

Follow the [Replay and final integration](./references/generation-and-checks.md) section:
require identical generated inventories and bytes before materializing owned
output. Preserve live edits, verify final output identity, and rerun final-path
consumer builds as specified there.

### 7. Record and return for the gate

Maintain the record specified in the [Generation record and handoff](./references/generation-and-checks.md)
section in the selected documentation notes and link it from `SOURCES.md`. Return through
**hal-architect** for independent **hal-reviewer** review and recheck of required
findings. Do not invoke `scaffold-hal` yourself.

## Completion and output

Use **ready for the declared scope**, **partial**, or **blocked**, with reasons.
Ready requires all required checks for the unchanged declared scope; independent
review must also pass before stage closure. Failed, unrun or stale required
checks and unresolved required findings are not acceptance. Partial output is
not a narrower completed scope.

Return the record path, status and next action with the reference's complete
handoff. State that no HAL implementation, publication or hardware operation
was performed; software evidence is not proof of silicon behavior or upstream
acceptance.
