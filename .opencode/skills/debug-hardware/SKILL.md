---
name: debug-hardware
description: >-
  Use when an authorized example or hardware-in-the-loop case has failed and
  hal-coordinator requires source-blind reproducible localization in a distinct
  debugging 07-tests handoff. Dispatch and search terms: failing HIL test,
  reproducible observation, failure localization, probe log, teardown, public
  API, distinct debug run, 07-tests handoff. Wrong for reading HAL source,
  editing drivers, host-unit debugging, bypassing ownership, running cargo fmt,
  committing, or performing unapproved device operations.
compatibility: opencode
---

# Debug a Failing Hardware Test

```halucinator-skill-contract
stage: write-tests
participants: hal-tester
emitter: hal-tester
emits: 07-tests|halucinator/handoff/07-tests-<source-name>-debug-<run-id>.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,tests.api_handoff,tests.board_interlock.authorization,tests.board_interlock.board_id,tests.board_interlock.check_token,tests.board_interlock.lease_epoch,tests.coverage.evidence,tests.coverage.id,tests.coverage.reason,tests.coverage.status,tests.coverage.test_case,tests.dependencies.crate,tests.dependencies.features,tests.dependencies.identity,tests.execution_scope,tests.hardware_runs.evidence,tests.hardware_runs.lease_epoch,tests.hardware_runs.operation_attempt,tests.hardware_runs.operation_id,tests.hardware_runs.post_safe_state,tests.hardware_runs.pre_safe_state,tests.hardware_runs.status,tests.hardware_runs.teardown,tests.hardware_runs.test_case,tests.name,tests.output_kind,tests.owned_files,tests.recovery_attempts,tests.review_input_manifest,tests.safe_state_procedure.assertion_ids,tests.safe_state_procedure.board_id,tests.safe_state_procedure.facts_handoff,tests.safe_state_procedure.procedure,tests.setup_record
checks: build-only-ci,format-lint,hardware-admission,hardware-execution,independent-review,live-conventions-read,target-build-link,workflow-references-read
consumes: 06-driver|coverage.complete,coverage.incomplete,driver.build_contract.cargo_chip_feature,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.build_contract.rust_compilation_target,driver.capabilities,driver.dependencies.crate,driver.dependencies.features,driver.dependencies.identity,driver.name,driver.public_api,driver.public_test_record,driver.requirement_ids,driver.scope_kind,driver.trait_obligations.dependency_crate,driver.trait_obligations.obligations,driver.trait_obligations.trait,handoff.blockers,handoff.inputs,handoff.notes,handoff.status,scope.decision,scope.revision,driver.facts_handoff,driver.test_hardware_facts
consumes: 07-tests|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,tests.api_handoff,tests.board_interlock.authorization,tests.board_interlock.board_id,tests.board_interlock.check_token,tests.board_interlock.lease_epoch,tests.coverage.evidence,tests.coverage.id,tests.coverage.reason,tests.coverage.status,tests.coverage.test_case,tests.dependencies.crate,tests.dependencies.features,tests.dependencies.identity,tests.execution_scope,tests.hardware_runs.evidence,tests.hardware_runs.lease_epoch,tests.hardware_runs.operation_attempt,tests.hardware_runs.operation_id,tests.hardware_runs.post_safe_state,tests.hardware_runs.pre_safe_state,tests.hardware_runs.status,tests.hardware_runs.teardown,tests.hardware_runs.test_case,tests.name,tests.output_kind,tests.owned_files,tests.recovery_attempts,tests.review_input_manifest,tests.safe_state_procedure.assertion_ids,tests.safe_state_procedure.board_id,tests.safe_state_procedure.facts_handoff,tests.safe_state_procedure.procedure,tests.setup_record
writes: hal-tester|test-candidate-evidence
writes: hal-tester|test-candidate-manifests
writes: hal-tester|test-candidate-source
writes: hal-tester|tests-handoff
supplies-delta: hal-tester|test-records
```

This stage localizes a failure that was already observed. It narrows where the
defect lives; it does not repair it, and it never opens the implementation to
find out.

## When to use

Use this skill when **hal-coordinator** dispatches localization work against a
preserved failure: a `07-tests-<source-name>` handoff carrying a `failed`
coverage row, a `failed` hardware run, or a `failed` applicable check, together
with the exact `06-driver` handoff its `tests.api_handoff` names. Use it also
when a previous debugging revision stopped at `partial` or `blocked` and the
recorded next action is now possible.

Do not use it to invent a failure that nobody observed, to widen an authorized
hardware scope, or to convert a build-only check into a device operation. A
successful build is not a runtime result, and an unavailable fixture is a
blocker rather than a narrower scope.

Read the [hardware-execution procedure](../write-examples/references/hardware-execution.md)
and the [public test-record reference](../write-examples/references/test-record.md)
before any setup planning or target-affecting operation, together with the
[universal validation profile](../write-examples/references/profiles/universal.md)
and exactly the positively classified category profile where one applies. A
missing required reference blocks the affected work; never fall back to a
remembered procedure.

## Ownership and boundaries

**hal-tester** is the emitter and owns exactly four classes:
`test-candidate-source` (`halucinator/test-candidates/*/src/**`),
`test-candidate-manifests` (`halucinator/test-candidates/*/*.toml` and
`INVENTORY.md`), `test-candidate-evidence`
(`halucinator/test-candidates/*/evidence/**`), and `tests-handoff`
(`halucinator/handoff/07-tests-*.toml`). It owns **no** canonical HAL or test
file. The durable `test-records` class is **hal-integrator**'s; the tester
supplies its semantic content as a delta and **hal-coordinator** dispatches
**hal-integrator** to materialize it and return the FileRef. Ownership is
recorded once, in [`ownership.toml`](../../ownership.toml).

Repairs are routed, never performed here. A driver or public-contract defect, a
missing hardware fact or PAC gap, a shared startup, linker, build or CI defect,
and an environment gap all return through **hal-coordinator** to their owners.
Specialists do not dispatch peers. `cargo fmt` and committing are denied to this
agent; builds and canonical placement belong to **hal-integrator**.

### Your blindness, stated honestly, and why this stage strains it

A tester that has read the driver writes tests that agree with the driver,
**including where the driver is wrong**. Debugging is the moment that temptation
peaks: a case fails, the public surface looks correct, and the answer feels one
search away. It is not. Localize from public observations or report that you
cannot.

**Perfect blindness is impossible. This is a strong default plus a statement of
intent, not a sandbox.** The real escape hatches, enumerated rather than
implied:

- `bash` is gated at `ask`, and an approved command can print anything.
- `grep` is matched against the regex query rather than the searched path.
- `glob` and `list` return filenames, which carry structure.
- Compiler, macro and build-script diagnostics quote source, as do dep-info and
  incremental files.
- Generated documentation, LSP responses, Git history and tool payloads can all
  reproduce implementation detail.
- The destination crate path is chosen at run time, so the static permission
  globs cannot be guaranteed to cover it. That gap is disclosed and deferred
  (TODO A18, M6); the mitigation is a coordinator and integrator comparison of
  the resolved path against the deny globs plus a prohibition, not a mechanism.

A reliability review found that this skill adds **exposure frequency** rather
than a new channel: its repeated rebuild and localization loops walk past the
same hatches many more times than a single authoring pass does. Treat each loop
as a fresh opportunity to leak, not as a settled question.

Compiler-visible public API and type detail is acceptable; a body excerpt is
not. If one is seen, say so: the run is invalid and **hal-coordinator** must
dispatch a fresh tester context. Nothing enforces that, which is why it has to
be said. Load only the declared public leaves of `06-driver` and the failing
`07-tests`. No implementation, no driver candidate, no Rust bodies, no linker
scripts, no disassembly, and no private diagnostic payload. Route every build
through **hal-coordinator** to **hal-integrator** and record only its sanitized
output.

## Inputs

Two validated predecessors, both consumed by exact path:

| Admission concern | Consumed field |
|---|---|
| Failing subject | `tests.name`, `tests.output_kind`, `tests.execution_scope` from the failing `07-tests` |
| Failing evidence | `tests.coverage.id`, `.status`, `.test_case`, `.evidence`, `.reason`; `tests.hardware_runs.test_case`, `.status`, `.evidence`, `.teardown`; `checks.id`, `.status`, `.evidence`, `.reason` |
| Failing lineage and inventory | `handoff.schema`, `handoff.stage`, `handoff.status`, `handoff.can_progress`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `coverage.complete`, `coverage.incomplete`, `scope.revision`, `scope.decision`, `tests.api_handoff`, `tests.owned_files`, `tests.review_input_manifest`, `tests.setup_record`, `tests.dependencies.crate`, `.identity`, `.features` |
| Public surface under test | `driver.name`, `driver.scope_kind`, `driver.capabilities`, `driver.public_api`, `driver.requirement_ids`, `driver.public_test_record` |
| Dependencies and obligations | `driver.dependencies.crate`, `.identity`, `.features`; `driver.trait_obligations.dependency_crate`, `.trait`, `.obligations` |
| Cited hardware facts | `driver.facts_handoff` plus the verified assertion IDs in `driver.test_hardware_facts`; the claim, source, location, printed locator, excerpt and note are resolved through that validator-checked handoff, never restated by the driver |
| Build contract | `driver.build_contract.cargo_chip_feature`, `.rust_compilation_target`, `.init_calls`, `.memory_runtime`, `.observation` |
| Driver lineage | `handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

`driver.owned_files` is deliberately not consumed. It may be a hash input for
the validator or for **hal-integrator**; the tester never reads the
implementation it names.

`tests.api_handoff` is resolved by path to the exact `06-driver` handoff, not by
name, so **hal-coordinator** names the exact FileRef. A `blocked` predecessor
permits no consumption. A `partial` one permits candidate-only work and no
downstream `ready`.

## Outputs

- One fresh revision under `halucinator/test-candidates/<source-name>-debug-<run-id>/`,
  with its probe source, its manifest, `INVENTORY.md`, and raw logs under
  `evidence/`.
- The preserved record of the original failure: its image identity, commands,
  setup, authorization, observations and teardown, hashed into evidence.
- The `test-records` delta, materialized by **hal-integrator**.
- `halucinator/handoff/07-tests-<source-name>-debug-<run-id>.toml`, where
  `tests.name` equals `<source-name>-debug-<run-id>`.

### The distinct output lineage rule

If the consumed handoff is `halucinator/handoff/07-tests-<source-name>.toml`,
the emitted handoff is:

```text
halucinator/handoff/07-tests-<source-name>-debug-<run-id>.toml
tests.name = "<source-name>-debug-<run-id>"
```

`<run-id>` is a nonempty lowercase `[a-z0-9-]+` identifier selected fresh for
each debugging revision. **The complete output filename must differ from every
consumed `07-tests` filename, and in-place replacement of the consumed handoff
is prohibited.** `07` names are repeatable and are not constrained by the
singleton-kind rule, so nothing mechanical stops a self-replacement; the reason
it is forbidden is that the original failing `07-tests` FileRef stays pinned in
`handoff.inputs`, and replacing those bytes makes this handoff's own input
reference stale and its lineage unrecoverable. The original failing `07-tests`
FileRef therefore remains pinned in `handoff.inputs`, and `tests.api_handoff`
names the exact `06-driver-*` handoff by path.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering the
   `write-tests` stage, the test-candidate resource, the `global:hal-integration`
   resource and the named board, and classify each as live, interrupted or
   ambiguous; treat the schema-1 board-lock fields as reserved metadata rather
   than an operational lease. Live means concurrency: do not interfere.
   Ambiguous means wait one 30-second refresh interval, reread, and fail closed
   if it is still ambiguous. Interrupted, or ambiguous still unresolved, means
   recovery: do not mutate the suspect output, inventory and hash it into a
   recovery Markdown FileRef, compare it against the last valid handoff, and
   publish `partial` with empty blockers when unaffected fresh-candidate work
   remains or `blocked` with an `interrupted:write-tests` blocker when it does
   not. Record the comparison, the disposition and the new candidate location
   before an authorized actor removes the lock. Resume only in a fresh debugging
   revision, never in place.
2. **Validate before consuming either predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading the failing
   `07-tests` or the public `06-driver`. Exit 0 with silent output is necessary;
   a missing interpreter, a timeout, a nonzero exit, or not running it is not a
   pass and blocks consumption. Report an unrelated stale artifact or ambiguous
   lock as a named blocker.
3. **Select a distinct debug name.** Select `<source-name>-debug-<run-id>`,
   confirm that no handoff, candidate directory or evidence path of that name
   already exists, and confirm that the resulting filename differs from every
   consumed `07-tests` filename. In-place replacement of the consumed handoff is
   prohibited; the consumed FileRef stays pinned in `handoff.inputs`.
4. **Load only public inputs.** Load exactly the declared leaves of the failing
   `07-tests` and the `06-driver` named by `tests.api_handoff`, and nothing else.
   Do not read implementation source, driver candidates, linker scripts,
   disassembly or private diagnostics, and do not reconstruct an implementation
   from filenames, documentation or build output.
5. **Load workflow references.** Load the tester-safe hardware-execution and
   test-record references and the applicable validation profiles, record which
   were actually read, and discharge `workflow-references-read`. A missing
   required reference is a blocker, not a reason to improvise.
6. **Inspect live conventions.** Inspect the checkout's permitted runner, load,
   setup, observation and teardown conventions, its manifests, toolchain,
   formatting and contribution rules, and discharge `live-conventions-read` from
   what was actually read. Do not invent a board identifier or assume
   infrastructure a reference board happens to have.
7. **Preserve the original failure.** Preserve, before changing anything, the
   original `07-tests` FileRef, the failing image identity, the exact commands,
   the physical setup, the authorization that covered it, every observation and
   the teardown that was or was not performed, hashed into new evidence at fresh
   paths. Never overwrite an evidence path and never delete a pinned record to
   make a rerun look clean.
8. **Select one-variable probes.** Select public-API or fixture observations
   that each change exactly one variable and that distinguish plausible owners —
   test logic, integration and build wiring, environment, or the driver contract
   itself. A probe that cannot be expressed through the public surface is a
   finding about the surface, not permission to open the implementation.
9. **Request candidate rebuilds.** Request through **hal-coordinator** that
   **hal-integrator** copy the debug delta verbatim into a disposable
   integration candidate, run the repository-required formatting and lint checks,
   build and actually link every advertised in-scope binary, and build the
   build-only CI path. Record only the sanitized results, which carry no
   implementation excerpt, and discharge `format-lint`, `target-build-link` and
   `build-only-ci` from them. Run none of those builds yourself: their
   diagnostics quote source and would defeat your blinding.
10. **Request hardware admission and acquire the interlock.** Require that
    **hal-coordinator** permits at most one hardware dispatch per named board,
    then take the **worktree-local, single-operator interlock** for that exact
    device with `runtime.py acquire-board` before any target-affecting
    operation, keeping the returned `lease_epoch` and `check_token`. It is a
    strong default and a statement of intent, not a sandbox: it cannot see
    another clone, another operator at the same bench, or a probe command typed
    directly into a terminal, and `before-board-op` narrows but cannot close the
    window between checking the token and using the device. Reconfirm the exact board identity and its documented safe starting
    state immediately before any target-affecting operation, identify the
    fixture, probe, runner and intended operations, give the user cited physical
    setup instructions, and obtain separate confirmation of physical readiness
    and explicit authorization for the named device and operations. Dispatch
    alone is not authorization. Discharge `hardware-admission` from that record,
    or record it `not-applicable` with a reason when the scope is `build-only`.
11. **Run bounded reproductions.** Revalidate with `before-board-op` and record
    the operation and its probe/runner child with `begin-board-operation`
    immediately before each target-affecting operation - attaching a debugger is
    one - then run only the authorized cases under bounded runners and per-case
    deadlines, capturing raw logs into the revision's `evidence/`. Call
    `complete-board-operation` only after the child and all its descendants have
    terminated and the observation channel is quiescent: **holder death is not
    operation death**, and a surviving probe or runner session can still be
    transferring or driving pins after the agent that started it has gone. Then
    establish safe state in order - quiesce controllable activity, establish the
    cited non-driving and reset or halt state, have the operator de-energize
    external loads, collect all six hazard observations, classify safe, and only
    then authorize a fixture change - keeping the **never join driven outputs**
    and **configure input before output** rules additive rather than replaced.
    Follow the documented safe teardown for successful and failing runs alike,
    and `release-board` only after the safe-state record exists. If the run was
    interrupted, declare the board state unknown **before** reconnecting and use
    `begin-board-recovery`; then authorize each observation through
    `begin-recovery-operation`, which is the only command that permits an
    operation while the board is unknown - ordinary `begin-board-operation`
    keeps refusing, so without it recovery cannot be completed at all. It is
    narrow, not a general unlock: observation operations only, never a load,
    program or run, and completing one leaves the board still unknown. Close
    each with `complete-board-operation` and its `--operation-id`, append an
    attempt for every try with `append-recovery-attempt`, and continue until
    `verify-board-recovery` accepts a matching safe-state observation; never
    infer teardown from a process exit or from elapsed time. Discharge `hardware-execution` from **whether the
    execution procedure itself ran correctly** — authorized operations only, on
    the reconfirmed board, within the deadlines, with teardown performed and raw
    observations preserved. A successful load, empty output or a zero exit is
    not a pass, and a successful build is never a runtime result.
12. **Record the observation separately from the check.** Record what the device
    actually did in `tests.coverage` and `tests.hardware_runs`, whose status
    vocabularies exist precisely to carry a failing case. **A correctly executed
    reproduction of a genuine defect leaves `hardware-execution` `passed` and
    the affected `tests.coverage` and `tests.hardware_runs` rows `failed`.**
    That is the expected shape of a successful localization: the check attests
    the procedure, the rows attest the misbehavior. Collapsing the two —
    marking the check `failed` because the device failed — destroys the
    distinction between "the reproduction did not run" and "the reproduction ran
    and reproduced the defect", and makes the skill's most useful outcome
    unreachable. `hardware-execution` is `failed` only when the procedure itself
    failed: an unauthorized or unreconfirmed operation, a deadline or runner
    fault that prevented the bounded case from completing, missing teardown, an
    overlapping run, or lost raw observations.
13. **Record interrupted hardware honestly.** Record hardware state as unknown
    in evidence whenever teardown is missing after an interruption, or whenever
    an operation overlapped another run on the same board. Missing teardown
    after an interruption forces `blocked`, and no result from an overlapping or
    interrupted run may be marked `passed` — not the check, and not any coverage
    or hardware-run row. There is no interrupted-HIL recovery machinery and no
    universal between-test safe state; say so rather than implying one.
14. **Compare evidence and route ownership.** Compare every captured observation
    against its recorded expectation, state which owners the evidence excludes
    and which it leaves open, and route each finding through
    **hal-coordinator** to its owner — **hal-driver** for a driver or contract
    defect, **hal-datasheet** or **hal-svd** for a missing hardware fact or PAC
    gap, **hal-integrator** for shared wiring, build or CI, and the user for an
    environment gap. Uncertain ownership is a finding, not authority to open the
    implementation.
15. **Publish and review.** Publish the preliminary distinct handoff, preserving
    a hashed snapshot and recovery record of any deterministic handoff
    `state.toml` currently pins before replacing it, run
    `python .opencode/schema/validate.py <repository-root> --kind all` again,
    request through **hal-coordinator** the independent **hal-reviewer** review
    over `tests.review_input_manifest` and the frozen revision, discharge
    `independent-review` from the accepting verdict, re-attest where referenced
    bytes changed by creating replacement evidence at new paths and rerunning
    only the affected checks, rewrite the final distinct handoff, validate it,
    let **hal-coordinator** update `state.toml` through the compare-and-swap
    sequence, and run the final `--kind all` gate. Only review.verdict=ready
    accepts; ready-with-fixes and not-ready do not.

When a required tool, target, formatter, schema, linker utility, probe, runner
or reviewer is unavailable, record the attempted command, discovered identity,
failure output, affected check and exact remedy in a new hashed evidence
FileRef. Leave the affected check `unrun`; never mark it `not-applicable`. Ask
the user to install or expose the named capability, provide an approved existing
path or runner, or request a coordinator-owned scope decision; the agent does
not install tools. Publish `partial` with `can_progress=true` and empty blockers
when unaffected work remains, using truthful coverage: `coverage.incomplete` may
remain empty when the `unrun` check alone makes the handoff partial. Publish
`blocked` with `can_progress=false` and a named `environment:<capability>`
blocker when no scoped work can continue. On resumption, rerun entry-state
classification and the `--kind all` gate, verify the supplied identity, create
replacement evidence at a fresh path, rerun affected checks and re-attest.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `build-only-ci` | Record the integrator's build of the debug candidate's build-only CI path | `halucinator/test-candidates/<name>/evidence/debug-build-only-ci.log` |
| `format-lint` | Record the integrator's sanitized formatting and lint results | `halucinator/test-candidates/<name>/evidence/debug-format-lint.log` |
| `hardware-admission` | Record board identity, safe starting state, named operations, readiness and authorization | `halucinator/test-candidates/<name>/evidence/debug-hardware-admission.md`, or `reason (no evidence FileRef)` when the scope is `build-only` |
| `hardware-execution` | Record that the bounded authorized reproductions ran correctly, within deadlines, with teardown performed and raw observations preserved; the device's own pass or failure is recorded in `tests.coverage` and `tests.hardware_runs`, not here | `halucinator/test-candidates/<name>/evidence/debug-hardware-execution.log`, or `reason (no evidence FileRef)` when the scope is `build-only` |
| `independent-review` | Request the coordinator-dispatched review of the distinct debugging record and record its accepting verdict | `halucinator/handoff/08-review-tests-<name>.toml` |
| `live-conventions-read` | Record the permitted runner, setup and teardown conventions actually inspected | `halucinator/test-candidates/<name>/evidence/debug-live-conventions.md` |
| `target-build-link` | Record the integrator's actual linked debug image | `halucinator/test-candidates/<name>/evidence/debug-target-build-link.log` |
| `workflow-references-read` | Load the tester-safe workflow and validation references and record which were read | `halucinator/test-candidates/<name>/evidence/debug-workflow-references.md` |

The validator wiring in the procedure is an **honor system**. The self-check can
prove this skill contains the instruction; it cannot prove that an agent ran it,
and [`validate.py`](../../schema/validate.py) cannot attest to its own earlier
invocation. The same holds for source blindness, the locks, the procedural board
exclusion and the review gate: they are discipline plus disclosure, and no part
of this document may describe them as enforcement. Typed evidence hashes
freshness, not relevance.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
the `06-driver` named by `tests.api_handoff` is `ready` and current against
`scope.revision` and `scope.decision`, the original failing `07-tests` FileRef
is pinned in `handoff.inputs` under a filename different from this handoff's
own, every applicable check is `passed`, every required reproduction ran to
completion under authorization with safe teardown and preserved raw
observations, every observation is faithfully recorded in `tests.coverage` and
`tests.hardware_runs`, and the independent review accepted. Only
review.verdict=ready accepts; ready-with-fixes and not-ready do not. **Ready
means the localization evidence is complete — not that the defect is fixed.**
A `failed` `tests.coverage` or `tests.hardware_runs` row therefore does not
prevent `ready`: reproducing the defect is the point of the stage, and the
reproduced failure is the evidence. `coverage.complete` and
`coverage.incomplete` describe the localization scope this revision covered, not
whether the device behaved. The repair belongs to another owner and is routed
through **hal-coordinator**.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. A debugging revision that **hal-integrator** has not yet materialized
and built is `partial` by construction, with candidate ArtifactRefs rather than
canonical ones.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. Missing teardown after an interruption always satisfies
this branch, with hardware state recorded as unknown; so do an overlapping run
on the named board, absent operation authorization, and an unavailable probe,
fixture, tool or reviewer. No result from an overlapping or interrupted run may
be marked `passed`.

## Application example

The suite `schema-demo` failed on the fictional
`unobtainium-circuits-uc-not-a-real-mcu-0001` fixture, so **hal-coordinator**
dispatches localization. The tester selects the run identifier `001`, giving the
revision `schema-demo-debug-001` and the distinct handoff
`halucinator/handoff/07-tests-schema-demo-debug-001.toml`. The consumed failing
handoff, `halucinator/handoff/07-tests-schema-demo.toml`, stays pinned in
`handoff.inputs` and is not replaced. The reproduction ran correctly under
authorization, within its deadline, with teardown performed — so
`hardware-execution` is `passed` — and it reproduced the defect, so the
`tests.coverage` and `tests.hardware_runs` rows are `failed`. The review has not
yet been obtained, so the handoff is `partial`:

```toml
[handoff]
schema = 2
stage = "write-tests"
status = "partial"
can_progress = true
inputs = [
  { path = "halucinator/handoff/07-tests-schema-demo.toml", sha256 = "1111111111111111111111111111111111111111111111111111111111111111" },
  { path = "halucinator/handoff/06-driver-schema-demo.toml", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" },
]
notes = [
  { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-record.md", sha256 = "3333333333333333333333333333333333333333333333333333333333333333" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "4444444444444444444444444444444444444444444444444444444444444444" }

[coverage]
complete = []
incomplete = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]

[tests]
name = "schema-demo-debug-001"
output_kind = "validation"
execution_scope = "hardware-validation"
api_handoff = { path = "halucinator/handoff/06-driver-schema-demo.toml", sha256 = "2222222222222222222222222222222222222222222222222222222222222222" }
owned_files = [
  { path = "halucinator/test-candidates/schema-demo-debug-001/src/schema_demo_debug.rs", sha256 = "5555555555555555555555555555555555555555555555555555555555555555" },
]
dependencies = [{ crate = "embassy-unobtainium", identity = "fixture-rev-1", features = ["uc-not-a-real-mcu-0001"] }]
setup_record = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-hardware-admission.md", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }
review_input_manifest = { path = "halucinator/test-candidates/schema-demo-debug-001/INVENTORY.md", sha256 = "7777777777777777777777777777777777777777777777777777777777777777" }
recovery_attempts = []

[tests.board_interlock]
board_id = "fictional-fixture-board-01"
lease_epoch = "0123456789abcdef0123456789abcdef"
check_token = "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
authorization = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/authorization.md", sha256 = "9999999999999999999999999999999999999999999999999999999999999999" }

[tests.safe_state_procedure]
board_id = "fictional-fixture-board-01"
facts_handoff = { path = "halucinator/handoff/02-facts.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
assertion_ids = ["fixture.schema-demo.reset-value", "fixture.schema-demo.safe-output-state"]
procedure = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/safe-state-procedure.md", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }

[[tests.coverage]]
id = "SCHEMA-01"
status = "failed"
test_case = "schema-demo-debug-reproduction"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-hardware-execution.log", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }

[[tests.hardware_runs]]
test_case = "schema-demo-debug-reproduction"
status = "failed"
lease_epoch = "0123456789abcdef0123456789abcdef"
operation_attempt = 1
operation_id = "89abcdef0123456789abcdef01234567"
pre_safe_state = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/safe-state/0123456789abcdef0123456789abcdef-0.toml", sha256 = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" }
post_safe_state = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/safe-state/0123456789abcdef0123456789abcdef-1.toml", sha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-hardware-execution.log", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }
teardown = "The fictional fixture runner returned the target to its documented safe state."

[[checks]]
id = "workflow-references-read"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-workflow-references.md", sha256 = "9999999999999999999999999999999999999999999999999999999999999999" }

[[checks]]
id = "live-conventions-read"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-live-conventions.md", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-format-lint.log", sha256 = "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb" }

[[checks]]
id = "target-build-link"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-target-build-link.log", sha256 = "cccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccccc" }

[[checks]]
id = "build-only-ci"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-build-only-ci.log", sha256 = "dddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddddd" }

[[checks]]
id = "hardware-admission"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-hardware-admission.md", sha256 = "6666666666666666666666666666666666666666666666666666666666666666" }

[[checks]]
id = "hardware-execution"
status = "passed"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/debug-hardware-execution.log", sha256 = "8888888888888888888888888888888888888888888888888888888888888888" }

[[checks]]
id = "independent-review"
status = "unrun"
evidence = { path = "halucinator/test-candidates/schema-demo-debug-001/evidence/review-pending.md", sha256 = "eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee" }
```

A fact nobody established is an absent key or an empty collection, never a
sentinel word. Coverage status is `passed`, `failed`, `blocked` or
`not-applicable`; hardware-run status is `passed`, `failed`, `blocked` or
`not-run`; a Check is `passed`, `failed`, `unrun` or `not-applicable`. None of
those three is the stage vocabulary, which is `ready`, `partial` or `blocked`.

## Quick reference

| Element | Value |
|---|---|
| Stage | `write-tests` |
| Emitter | `hal-tester` |
| Emitted handoff | `halucinator/handoff/07-tests-<source-name>-debug-<run-id>.toml`, `tests.name` equal to `<source-name>-debug-<run-id>` |
| Consumes | the failing `07-tests-<source-name>` and the exact `06-driver` its `tests.api_handoff` names |
| Lineage rule | the output filename differs from every consumed `07-tests`; in-place replacement is prohibited; the consumed FileRef stays pinned in `handoff.inputs` |
| `run-id` | nonempty lowercase `[a-z0-9-]+`, fresh per debugging revision |
| Checks | `build-only-ci`, `format-lint`, `hardware-admission`, `hardware-execution`, `independent-review`, `live-conventions-read`, `target-build-link`, `workflow-references-read` |
| Candidate root | `halucinator/test-candidates/<source-name>-debug-<run-id>/` with `src/`, its manifest, `INVENTORY.md` and `evidence/` |
| Builds | requested through `hal-coordinator` from `hal-integrator`; sanitized output only |
| Board exclusion | procedural single dispatch per named board; no lease reader exists (TODO F3) |
| Before operations | reconfirm exact board identity and safe starting state; dispatch alone is not authorization |
| Interruption | missing teardown forces `blocked`, hardware state recorded as unknown, no `passed` result |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write; an honor system |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| `ready` means | localization evidence is complete, not that the defect is fixed |

## Common mistakes

- **Replacing the failing handoff in place.** It is the single most natural
  thing to do and it destroys the lineage: the consumed FileRef pinned in
  `handoff.inputs` goes stale against its own bytes. Select a fresh `run-id` and
  a distinct filename.
- **Reusing a `run-id` across revisions.** Two debugging passes then write the
  same evidence paths, and the superseded observations disappear exactly when a
  reviewer needs them.
- **Opening the implementation "just to confirm".** A failing case plus a
  correct-looking public surface is precisely the situation the blinding exists
  for. The unresolved question is a finding.
- **Treating the deny globs as a sandbox.** `bash` is `ask`, `grep` matches the
  query rather than the path, diagnostics quote source, and the destination
  crate path is not covered. Say so; do not imply enforcement.
- **Running the build yourself to see the error faster.** Compiler, macro and
  build-script output quotes implementation source. Route it through
  `hal-coordinator` to `hal-integrator` and take the sanitized result.
- **Describing board exclusion as a lease.** Schema 1 reserves the fields and
  implements no reader. The exclusion is one coordinator dispatch per named
  board, procedurally, plus reconfirmation immediately before operations.
- **Skipping reconfirmation because the board was confirmed an hour ago.**
  Readiness and authorization are separate facts and both expire when anything
  changes — the fixture, the load mode, or simply the interval.
- **Marking `hardware-execution` `failed` because the device failed.** The check
  asks whether the execution procedure ran correctly; the device's misbehavior
  belongs in `tests.coverage` and `tests.hardware_runs`. Conflating them makes a
  correctly executed reproduction indistinguishable from a reproduction that
  never ran, and puts `ready` permanently out of reach for the one outcome this
  skill exists to produce.
- **Marking an interrupted run `passed` because the observation looked right.**
  An overlapping or interrupted run yields no `passed` result — not the check
  and not any row — and missing teardown forces `blocked` with hardware state
  recorded as unknown.
- **Changing more than one variable per probe.** Two simultaneous changes
  produce an observation that excludes no owner, which is the same as no
  observation at all.
- **Declaring `ready` because the cause was identified.** Ready is complete
  localization evidence; the repair belongs to another owner and returns through
  `hal-coordinator`.
- **Fixing the driver, the wiring or the environment yourself.** None of those
  classes is the tester's, `cargo fmt` and committing are denied, and a repair
  performed here is unreviewable.
- **Quoting only the rejecting verdict.** Stating what does not accept, without
  stating what does, turns the gate into advice. Use the exact sentence.
