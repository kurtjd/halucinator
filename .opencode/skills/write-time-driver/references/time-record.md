# Time Driver Record

For **hal-driver** and **hal-architect** to maintain and **hal-reviewer** to
audit. This is the private service decision/evidence index, not **hal-tester**'s
public test record. Send the tester only public signatures, contracts, cited
facts, and the source-blind validation handoff.

## Location and identity

Follow "Artifact storage and handoff" in the actual working repository's root
`AGENTS.md`, not a file relative to the skill installation. Reuse an explicit or
applicable recorded location; otherwise use `notes/TIME-DRIVER.md` in the selected
documentation directory. Link from the source list, roadmap, and any supporting
scaffold record rather than duplicating those records here.

Record exact MCU/revision/package and relevant board facts, destination crate,
scope kind (full time service or scaffold support), owned files, chip features
and compilation target, exclusions, and actual source/PAC/record paths. Identify
unknowns with the decisions they block rather than filling them from memory.

## Decisions and contracts

- Source IDs and hardware citations with title/document number, revision, and
  section/table/page; generated PAC provenance and selected resource coverage.
- Live MCXA/DEVGUIDE citations and actual driver, time-consumer, queue, and
  executor versions/contracts. Existing PAC/fork and scaffold coverage gates
  still apply; record substitutions and dependent rechecks without losing history.
- Reserved counter/timer/RTC/compare/interrupt resources and their ownership,
  clock/reset/power/init contracts, and feature-dependent user availability.
- Counter representation/width, tick source/divisor/exported rate, time range,
  extension/service-latency assumptions, compare horizon/lead time, queue backend
  and applicable capacity, pre-init behavior, and supported idle/clock modes.
- Public configuration and service signatures, finite-type decisions where
  needed, and shared-service scheduling/cancellation guarantees. Do not copy
  private decisions into the tester handoff or redefine the upstream contracts.
- TIME requirement applicability and agreed evidence plan. Link the public test
  record for case-specific configurations, timing references, tolerances,
  measurements, and coverage gaps rather than maintaining a second test plan.

## Evidence index

| Time | Check/decision | Input identity | Command/cwd/target/features | Result or record link | Depends on |
|---|---|---|---|---|---|

Record each required software gate from the skill and its observed outcome.
Identify inputs with the commit plus tool-computed hashes of relevant dirty and
untracked code/build inputs, or an equivalent content snapshot. HEAD alone is
insufficient in a dirty tree. Do not require a commit/stash or invent a time/hash.
Exclude this record from tested inputs unless it affects the check.

Link the tester's existing `write-examples` public test record and raw evidence,
using its identity/status format rather than copying logs or execution policy.
That record contains the TIME case mapping and independent timing measurements.
Link reviewer scope/input identity, findings, owner/disposition, and rechecks.

## Status and resumption

| Dimension | Meaning |
|---|---|
| Software | `in progress`, `blocked`, or `software verified` under the skill's software gates and required independent review/rechecks. |
| Hardware | Use the linked `write-examples` record's statuses for the required TIME cases. |

Full time-service validation requires both `software verified` and passing
current evidence for the agreed required hardware cases, with no unresolved
required finding. Scaffold support can satisfy its own build-only gate with
hardware `not run`; record that narrower scope and the remaining validation
handoff.

On resume or change, compare API/source/PAC versions, code/build inputs, selected
rates/resources/features, toolchain, image, clock/power setup, fixture and timing
reference, and execution mode. Preserve old entries, invalidate only dependent
decisions/results/review, and rerun before clearing blockers. Do not change
inputs during a check or review; refreshed setup/authorization and public-run
evidence follow `write-examples`, not a duplicate procedure here.

For every blocker or uncovered claim, state affected scope/requirements, owner,
next action, and evidence needed under the public validation reference's
applicability and timing-evidence rules. Keep toolkit checks distinct from
actual HAL/HIL runs.
