---
name: generate-svd
description: >-
  Prepare a register description before generating an Embassy HAL's PAC.
  Use for reviewing or normalizing a supplied vendor SVD, authoring CMSIS-SVD
  from cited register findings when no suitable SVD exists, correcting register
  descriptions with chiptool transforms, checking SVD coverage, or resuming
  incomplete SVD preparation. Does not generate Rust PACs or scaffold crates.
compatibility: opencode
---

# Generate SVD

The owning agent is **hal-svd**. This skill ends with checked register-description
inputs and a reproducible handoff, not a Rust crate. **hal-architect** supplies
the documentation handoff, obtains missing findings from **hal-datasheet**, and
decides whether the declared scope is ready for `generate-pac`.

## Boundaries

- Review or author only the exact part, core, and peripheral/register scope
  supplied for this run. Report partial coverage as partial, not whole-chip
  support. A supplied SVD changes the starting point; it does not skip review.
- Preserve vendor SVDs and user originals byte-for-byte. Corrections to vendor
  input belong in cited, reproducible transforms. Authored SVD XML is a source
  input; extracted YAML is derived output and is not hand-edited.
- Use chiptool only for extraction, transforms, and structural checks here.
  Leave Rust emission, PAC crate setup, Cargo features, dependency pins,
  and metapac assembly to `generate-pac` under **hal-architect**'s scope policy.
  Publication is a separate decision. Do not invoke the next stage as a
  validation shortcut.
- Do not install tools, extract PDFs, configure hardware, flash, or run target
  code. Missing hardware facts go through **hal-architect** to **hal-datasheet**;
  do not attempt direct subagent delegation from **hal-svd**.
- Follow `AGENTS.md`'s "Artifact storage and handoff" rule. Select the shared
  PAC project but create only the SVD data and run directories needed here.
  Neither a generator nor a Cargo crate is a prerequisite or deliverable.

## Procedure

### 1. Resume the evidence handoff

Load the supplied repository-relative documentation directory, `SOURCES.md`,
relevant source IDs, and cited-note paths. Reuse the recorded target and SVD
starting point rather than repeating intake. If the documentation location,
source list, target, or requested scope is missing, return the missing handoff
fields to **hal-architect** rather than guessing a path or a previous target.
Establish the exact part, relevant core/revision, and requested peripherals
before treating family data as evidence. Unknown identifiers remain unknown;
name the applicability checks they prevent.

Check that sources and existing preparation artifacts still resolve. Verify
available input hashes and revisions before reusing earlier results. Changed
bytes require a new source record and rechecking affected findings, transforms,
and outputs; do not silently replace an already cited source or reuse stale
validation. Preserve earlier findings and record what supersedes them.

Choose the route supported by the evidence:

- **Review/normalize supplied SVD:** an accessible SVD is applicable to the
  target, or its remaining applicability questions are explicitly bounded.
- **Author from cited findings:** no suitable SVD was found in the recorded
  search, and the required register facts are available from **hal-datasheet**.
- **Unresolved:** source access, applicability, or necessary findings are
  missing or contradictory. Return the affected scope and the precise next
  action to **hal-architect**. Request documentation intake or hardware analysis
  as appropriate; do not manufacture an SVD to get past the gate.

Intake completion is not hardware-fact verification. A vendor SVD can establish
what the vendor supplied, but does not establish agreement with the manual.
Missing board or probe details do not block MCU register work unless a specific
fact in the requested scope depends on them.

### 2. Establish paths and checks

Read [Preparation and Checks](./references/preparation-and-checks.md) before
choosing commands. Apply the shared storage rule and the reference's SVD-specific
artifact details. Inspect existing changes, select fresh run outputs, and record
their locations as specified there. A supplied SVD is an input, not permission
to write beside it. Use file-edit tools for authored XML, transforms, and
Markdown records.

Check the available XML/schema validator and the selected chiptool revision,
provenance, and command help. Reuse an existing tool pin; a version banner alone
may not identify its revision. Do not install or upgrade tools automatically.
If a required tool or permission is unavailable, continue evidence review where
useful, but mark the corresponding executable checks unrun and the stage partial
or blocked, not ready.

### 3. Review or author the source description

**With a supplied SVD:** preserve the original and establish a baseline inventory
for the declared scope. Parse it with structured XML tooling, check its schema
version, and compare the effective register properties with the cited findings.
Resolve inheritance, arrays, and aliases rather than inspecting only textually
present values. Separate verified facts, vendor-only claims, and gaps. Record
which manual section or applicable erratum justifies each correction. A correct
SVD may need no transforms or structural changes.

**Without a suitable SVD:** author CMSIS-SVD XML from cited findings for the
declared scope. Use the matching schema and represent required device properties,
peripheral bases, offsets, widths, fields, encodings, access, reset information,
and interrupt facts only when supported. Do not copy a similar chip's CPU,
memory map, or defaults. Omit unsupported optional facts and record the gap; if
a required property cannot be established, stop that scope instead of inserting
a plausible value. Keep citations in the accompanying review record.

For both routes, follow the source-comparison checklist in the reference.
Distinguish XML well-formedness, schema compliance, and agreement with hardware
documentation. Parser defaults are not hardware evidence. Contradictory manual
sections and unresolved revision-specific errata are findings, not choices to
resolve by preference.

### 4. Record corrections and prove their effects

Keep necessary vendor corrections in chiptool transform files, with their
source IDs, document revisions, and section/table/page citations recorded beside
the correction or in an unambiguous linked review entry. Record transform order,
included files, and the naming/namespace assumptions their selectors require.
Avoid normalization that serves no demonstrated need.

Use the reference's effect checks for each required correction. Unexpected or
missing matches, or a missing intended effect, fail the check even when chiptool
exits successfully.

If the source cannot be parsed or a correction is unsupported, report the
blocker and downstream impact. Request corrected input or separately authorized
input preparation; do not alter vendor originals or claim a note fixed the
machine-readable description.

### 5. Prepare and check without generating Rust

Use the selected chiptool's non-Rust operations from the reference to extract
and inspect a baseline, then apply the ordered corrections from the original
input into a separate prepared output. Omit transforms entirely when none are
needed. Choose extraction mode and namespaces consistently with the actual
rules, and record them for replay.

Run the reference's inventory and structural checks on an explicit nonempty
set of relevant YAML files. Keep reviewed coverage distinct from wider
extraction, and investigate warnings or skipped items.

Compare the prepared representation with the cited expected result, not just the
previous output. Use the reference's information-limit checklist to preserve and
check facts omitted from the IR. A chiptool check is not an audit of the silicon.

Replay the preparation using the reference's reproducibility check. Source
changes invalidate affected earlier checks.

### 6. Record the result and hand off

Write or update a clearly scoped preparation note using the reference's
[record and handoff fields](./references/preparation-and-checks.md#preparation-record-and-handoff).
Register its path and stable artifact locations in `SOURCES.md` without erasing
prior records.

Hand off the original or authored SVD, ordered transforms and included files,
optional extracted YAML, citations, checks, and outstanding semantic facts.
YAML is not a corrected XML SVD and is not a complete substitute for those
inputs. Do not claim unsupported facts were retained or corrected by chiptool.

Return to **hal-architect** for the stage gate and any review or further
**hal-datasheet** work. Do not invoke `generate-pac`; the architect dispatches
it only after accepting the preparation handoff.

## Completion and output

Use **ready for the declared scope**, **partial**, or **blocked**, with reasons.
Ready requires all required checks for that scope to have run successfully,
corrections to have their intended effects, and no unresolved required facts or
representation problems. Explicit, understood IR omissions can travel as cited
source facts; they are not proof those facts exist in generated code. Missing
checks or unresolved defects cannot be hidden by reducing the reported scope
after the run; ask **hal-architect** to approve a narrower scope instead.

Return the preparation-note path and summarize its target/scope, description
delta, verification (including unrun checks), status, and next action. The
reference defines the full source, path, and evidence fields; do not omit them
from the note. Report register-description changes instead of the agent's
Rust-oriented generated delta. State that no Rust PAC generation, compilation,
or hardware operation was performed.
