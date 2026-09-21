# Public Test Record

This is **hal-tester**'s source-blind evidence format for `write-examples`, also
consumed by **hal-coordinator**, **hal-integrator** and **hal-reviewer**. Include
public contracts, build facts, fixtures, and results only, never HAL bodies or
private design notes. Keep software and hardware evidence separate and attribute
each run to its owner.

## Who writes what

**hal-tester** owns and materializes only its four classes: the candidate source
under `halucinator/test-candidates/*/src/**`, its manifests and `INVENTORY.md`,
its raw logs under `evidence/**`, and the `07-tests-*` handoff.

The durable record described here is ownership class `test-records`, at
`halucinator/docs/*/notes/tests/**`, owned and materialized by
**hal-integrator**. So are the canonical `examples/*` binaries, manifests and
support files, the `tests/*` HIL binaries, the runtime wiring and `ci.sh`. The
tester authors each of those as a `supplies-delta`; **hal-coordinator**
dispatches **hal-integrator** to materialize it and returns its FileRef. The
tester edits no canonical file and makes no commit.

## Location and reuse

Follow "Artifact storage and handoff" in the working repository's root
`AGENTS.md`, not a policy relative to the skill installation. Prefer the supplied
or applicable recorded public setup/run record, including one already linked
by a peripheral record. Do not create a competing record or move existing logs
just to adopt this format; add missing fields to the established public record.

For a new task with no recorded location, the record is
`notes/tests/<task-id>/TESTS.md` within the selected documentation directory.
Use the existing roadmap task identifier as a filename-safe name; if none
exists, derive a short lowercase ASCII name from the recorded peripheral and
mode scope, matching `tests.name`. A collision with a different task needs a
distinct identifier, not an overwrite. Raw logs stay beside the tester-owned
candidate under `halucinator/test-candidates/<name>/evidence/`; the canonical
record links them. Link the record from the source list, roadmap, and applicable
peripheral record; do not duplicate the roadmap here.

## Required sections

### Identity and scope

- Exact target, relevant package/revision/board facts, public API and dependency
  versions, peripheral/modes/capabilities, owned files, and exclusions.
- Output kind, execution scope, and exit criteria selected at workflow intake.
- Working repository, documentation/source-list and applicable peripheral
  record paths; source IDs with document title/number, revision, and
  section/table/page. Record an unresolved fact as absent together with the
  decision it blocks, not as a guessed value or a sentinel in a typed field.
- Public init/interrupt and memory/runtime contracts, actual target/features,
  permitted reference/build files, and result channel where runtime is required.

### Coverage and expectations

| Requirement/source | Capability and applicability | Case/binary | Fixture/stimulus | Expected observation | Evidence needed | Outcome/gap |
|---|---|---|---|---|---|---|

Keep peripheral requirement IDs authoritative; reference rather than redefine
their contracts. Add independent cases with their own source basis. Missing
equipment/evidence is blocked coverage, not unsupported hardware. Retain the
decision and justification for any scope or expected-outcome change.

### Software checks and input identity

| Time | Check/command/cwd | Toolchain/target/features | Input identity | Outcome/artifact | Depends on |
|---|---|---|---|---|---|

Cover the skill's format/lint/build/link and build-only CI requirements. Record
the actual linked artifact and hash; HEAD alone does not identify dirty inputs.
Use the coordinator-supplied source/build snapshot identifier plus tool-computed
hashes of owned dirty/untracked test/build inputs and the image, or an equivalent
complete content identity. Do not read HAL internals to compute identity, require
a commit/stash, or invent timestamps/hashes. If identity is unavailable, mark the
evidence unverified and obtain the missing snapshot before closure.

### Hardware setup and runs

For runtime work, record the setup and decisions established by the
hardware-execution procedure:

- Exact board/MCU/revision, probe or named HIL device, runner/version and public
  observation channel; cited connection table, electrical/load constraints,
  instrumentation, safe power/reset/preparation/teardown sequence.
- User setup confirmation and its time, named-device operation authorization,
  actual authorized erase/program ranges if applicable, outstanding questions,
  and any later changes/reconfirmation. Physical setup and execution consent
  are distinct facts; record both.
- Chosen RAM/flash mode, image load/execution ranges and capacity evidence,
  startup/stack/vector or trap/reset contract, verified loader behavior,
  fallback reason if any, and image identity linked to software checks.

| Run/time | Case | Setup/authorization | Image/input identity | Mode/tool/command/cwd/deadline | Expected | Observed/raw log | Status/teardown |
|---|---|---|---|---|---|---|---|

Use the hardware procedure's outcome classifications for every attempt. Include
failed runs, each retry's reason and bound, actual teardown, and outstanding user
actions. Build-only tasks record every hardware run as `not-run`, with evidence
absent and teardown `not-applicable`, and with any future setup handoff, without
requiring a fixture.

### Review, status, and resumption

Record reviewer, reviewed scope/input identity, findings, responsible owner,
disposition, and recheck evidence. Only review.verdict=ready accepts;
ready-with-fixes and not-ready do not.

The published status of this stage is exactly one of the three stage values
`ready`, `partial` or `blocked`, decided by the skill's exit predicates. There is
no separate software or hardware overall status. The per-item vocabularies are
distinct and must not be mangled into it:

| Dimension | Values |
|---|---|
| Stage status (`handoff.status`) | `ready`, `partial`, `blocked` |
| Coverage row (`tests.coverage.status`) | `passed`, `failed`, `blocked`, `not-applicable` |
| Hardware run (`tests.hardware_runs.status`) | `passed`, `failed`, `blocked`, `not-run` |
| Check (`checks.status`) | `passed`, `failed`, `unrun`, `not-applicable` |

A `ready` build-only scope has every hardware run `not-run`. A `ready`
hardware-validation scope has every required applicable run `passed` with safe
teardown, a present `tests.setup_record`, and no unresolved required finding.
Build-only software completion cannot close a separate peripheral HIL gate. Keep
RAM results distinct from normal flash boot and power-cycle coverage, and limit
claims to the tested hardware and cases. Link public results from the full
peripheral record.

Preserve old runs when inputs change. Compare API, sources, toolchain, features,
test/harness code, image, fixture, board, runner, and execution mode on resume;
invalidate only dependent decisions/results/review and rerun before closure.
Do not change inputs during a check or review. Refresh setup/authorization as
required by the hardware procedure. A changed image cannot inherit a prior pass.

For each blocker, name affected cases/scope, owner, next action, and evidence
needed. Separate actual target runs from toolkit workflow/metadata checks.
Return a concise status summary with links to this record and its raw evidence,
not copies of the full record in every handoff.
