---
name: write-examples
description: >-
  Use when hal-coordinator dispatches black-box validation for a driver whose
  tester-safe public API is already published, or when a previous
  `07-tests-<name>` stopped at partial or blocked. Dispatch and search terms:
  public-API examples, hardware-in-the-loop tests, test candidates under
  halucinator/test-candidates, build-only scaffold link checks, documented
  physical setup, RAM-first load and run, teardown and raw evidence,
  `07-tests` handoff; canonical `examples/`, `tests/`, manifests and `ci.sh`
  are assigned to hal-integrator. Wrong for reading or fixing HAL
  implementation, writing host-side unit tests, owning shared startup or clock
  policy, editing canonical example/test/CI files, or committing.
compatibility: opencode
---

# Write Examples and Hardware Tests

```halucinator-skill-contract
stage: write-tests
participants: hal-tester
emitter: hal-tester
emits: 07-tests|halucinator/handoff/07-tests-<name>.toml|checks.evidence,checks.id,checks.reason,checks.status,coverage.complete,coverage.incomplete,handoff.blockers,handoff.can_progress,handoff.inputs,handoff.notes,handoff.schema,handoff.stage,handoff.status,scope.decision,scope.revision,tests.api_handoff,tests.coverage.evidence,tests.coverage.id,tests.coverage.reason,tests.coverage.status,tests.coverage.test_case,tests.dependencies.crate,tests.dependencies.features,tests.dependencies.identity,tests.execution_scope,tests.hardware_runs.evidence,tests.hardware_runs.status,tests.hardware_runs.teardown,tests.hardware_runs.test_case,tests.name,tests.output_kind,tests.owned_files,tests.review_input_manifest,tests.setup_record
checks: build-only-ci,format-lint,hardware-admission,hardware-execution,independent-review,live-conventions-read,target-build-link,workflow-references-read
consumes: 06-driver|handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,driver.name,driver.scope_kind,driver.capabilities,driver.public_api,driver.dependencies.crate,driver.dependencies.identity,driver.dependencies.features,driver.trait_obligations.dependency_crate,driver.trait_obligations.trait,driver.trait_obligations.obligations,driver.test_hardware_facts.source_id,driver.test_hardware_facts.document,driver.test_hardware_facts.revision,driver.test_hardware_facts.locator,driver.test_hardware_facts.note,driver.build_contract.cargo_chip_feature,driver.build_contract.rust_compilation_target,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.requirement_ids,driver.public_test_record
writes: hal-tester|test-candidate-evidence
writes: hal-tester|test-candidate-manifests
writes: hal-tester|test-candidate-source
writes: hal-tester|tests-handoff
supplies-delta: hal-tester|ci
supplies-delta: hal-tester|example-binaries
supplies-delta: hal-tester|example-manifest
supplies-delta: hal-tester|example-support
supplies-delta: hal-tester|hil-tests
supplies-delta: hal-tester|runtime-wiring
supplies-delta: hal-tester|test-records
```

This stage produces independent black-box evidence about a public API the tester
is not permitted to read the implementation of. A suite that passes first time
has told you nothing you did not already believe.

## When to use

Use this skill when **hal-coordinator** dispatches `write-tests` against a
validated `ready` `06-driver`, or against a validated **partial** `06-driver`
solely for the fresh disposable candidate authoring needed to close that
driver's `target-link-ci` check. Partial admission never permits canonical
mutation, hardware operation, or a `ready` `07-tests`; propagate `partial` until
the exact driver handoff is finalized. This is the bounded break in a real
cycle — a driver's `ready` requires `target-link-ci`, which requires a candidate
this stage authors — and it is exactly the disposable fresh-candidate work
[`handoff-common.md`](../../schema/handoff-common.md) already permits off a
`partial` predecessor. The skill also applies when **hal-coordinator** dispatches
an explicitly **build-only** scaffold link check, which closes only the
build-only gate, or when a previous run left `07-tests-<name>` at `partial` or
`blocked` and the recorded next action is now possible.

Read the [public test-record reference](./references/test-record.md) at intake.
For hardware-validation work, also read and follow the
[hardware-execution procedure](./references/hardware-execution.md) before any
setup planning or target-affecting operation. Combine both with the
[universal validation profile](./references/profiles/universal.md), which applies
to every driver, and with exactly the positively classified category profile
where one applies. A missing required reference blocks the affected work; never
fall back to a remembered procedure.

## Ownership and boundaries

**hal-tester** is the emitter and owns exactly four classes:
`test-candidate-source` (`halucinator/test-candidates/*/src/**`),
`test-candidate-manifests` (`halucinator/test-candidates/*/*.toml` and
`INVENTORY.md`), `test-candidate-evidence`
(`halucinator/test-candidates/*/evidence/**`), and `tests-handoff`
(`halucinator/handoff/07-tests-*.toml`). It owns **no** canonical HAL or test
file.

Every canonical surface is **hal-integrator**'s, and the tester reaches it only
as a `supplies-delta`: `example-binaries` (`examples/*/src/bin/**`),
`example-manifest` (`examples/*/Cargo.toml`), `example-support`
(`examples/*/*.x`, `examples/*/.cargo/**`, `examples/*/build.rs`), `hil-tests`
(`tests/*/**`), `runtime-wiring`, `ci` (`ci.sh`) and `test-records`
(`halucinator/docs/*/notes/tests/**`). **hal-coordinator** dispatches
**hal-integrator** to materialize each delta into a disposable integration
candidate and returns its FileRef. The tester never edits `ci.sh`, never places
a canonical binary, and never commits.

Return every question, finding, repair, review request and scope change to
**hal-coordinator**. Specialists do not dispatch peers, and the tester does not
route work to **hal-architect**.

### Your blindness, stated honestly

The tester is denied read access to HAL source on purpose: a tester that has
read the driver writes tests that agree with the driver, including where the
driver is wrong. Work only from the supplied public API and contracts, the cited
hardware and board facts, and the permitted build files. Do not read HAL bodies,
copied private notes, full implementation records, or debugger source and
disassembly to reconstruct an implementation. Skill selection does not change
agent permissions.

**Perfect blindness is impossible, and this is a strong default plus a statement
of intent, not a sandbox.** `bash` is gated at `ask`; `grep` is matched against
the regex query rather than the searched path; `glob` and `list` return
filenames, which carry structure; and compiler, macro and build-script
diagnostics, dep-info and incremental files, generated documentation, Git
history, LSP responses and tool payloads can all quote source.
Compiler-visible public API and type detail is acceptable; a body excerpt is
not. If one is seen, say so: the run is invalid and **hal-coordinator** must
dispatch a fresh tester context. Nothing enforces that, which is why it has to
be said.

`state.decisions.destination_crate` can name an arbitrary path, so a static deny
glob cannot be guaranteed to cover the HAL source, and agent frontmatter cannot
interpolate a runtime path. The mechanism that would close this is **deferred**;
there is no dynamic frontmatter generation. The review-only mitigation is that
**hal-coordinator** and **hal-integrator** compare the resolved destination crate
against the tester's deny globs, disclose any uncovered path in the dispatch, and
the tester must not read it. That is mitigation, not closure.

Respect the selected peripheral, modes and execution scope. No automatic
hardware CI, no new peripheral introduced merely to provide logging or timeouts,
no custom loader project. Build-only authorization never implies a device
operation.

## Inputs

Consume the validated, `ready` `06-driver` leaves declared in the contract. The
admission vocabulary is exactly the producer's field names:

| Admission concern | Consumed field |
|---|---|
| Subject | `driver.name`, `driver.scope_kind`, `driver.capabilities` |
| Public surface | `driver.public_api` |
| Dependencies | `driver.dependencies.crate`, `driver.dependencies.identity`, `driver.dependencies.features` |
| Upstream obligations | `driver.trait_obligations.dependency_crate`, `driver.trait_obligations.trait`, `driver.trait_obligations.obligations` |
| Cited hardware facts | `driver.test_hardware_facts.source_id`, `.document`, `.revision`, `.locator`, `.note` |
| Build contract | `driver.build_contract.cargo_chip_feature`, `.rust_compilation_target`, `.init_calls`, `.memory_runtime`, `.observation` |
| Requirements and record | `driver.requirement_ids`, `driver.public_test_record` |
| Lineage | `handoff.status`, `handoff.inputs`, `handoff.notes`, `handoff.blockers`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` |

`driver.owned_files` is deliberately not consumed here. It may be a hash input
for the validator or **hal-integrator**; the tester never reads the
implementation it names.

A driver scope may produce several `06-driver-*` handoffs. The validator resolves
`tests.api_handoff` by path to the exact `06-driver` handoff, and when the suite
is `ready` it requires that driver handoff to be `ready`. That binding is by
path, not by name, so the operative discipline is unchanged: **hal-coordinator**
names the exact `tests.api_handoff` FileRef for the suite.

A `blocked` predecessor permits no consumption. A `partial` one permits
candidate-only work and no downstream `ready`. An unknown fact blocks only the
decisions that depend on it. A required hardware run is never reclassified as
build-only because hardware is unavailable; that is a blocker.

Resolve two decisions at intake and record them:

- **`tests.output_kind`** — `example`, `validation` or `both`. An example
  demonstrates use; it does not satisfy a validation requirement.
- **`tests.execution_scope`** — `build-only` or `hardware-validation`. Reuse the
  explicit dispatch; resolve an unclear scope through **hal-coordinator** before
  any device operation, and continue only unambiguous software work meanwhile.

## Outputs

- One revision under `halucinator/test-candidates/<name>/`, with its source, its
  manifest and `INVENTORY.md`, and its raw logs under `evidence/`.
- Deltas for the canonical `examples/<chip>/` binaries, their manifest and
  support files, the `tests/<chip>/` HIL binaries, the runtime wiring, the
  build-only `ci.sh` entry and the durable test record — each materialized by
  **hal-integrator**.
- The public setup record and the hardware-admission and execution evidence
  where the scope is `hardware-validation`.
- `halucinator/handoff/07-tests-<name>.toml`, where `<name>` equals `tests.name`,
  carrying `tests.api_handoff`, `tests.owned_files`, `tests.dependencies`,
  `tests.output_kind`, `tests.execution_scope`, `tests.setup_record` where
  applicable, `tests.review_input_manifest`, the `[[tests.coverage]]` rows, the
  `[[tests.hardware_runs]]` rows with their teardown, the eight canonical
  checks, coverage and scope.

## Procedure

1. **Inspect and classify entry state.** Inspect every lock covering the
   `write-tests` stage, the test-candidate resource and the
   `global:hal-integration` resource, and classify each as live, interrupted or
   ambiguous. Live means concurrency: do not interfere. Ambiguous means wait one
   30-second refresh interval, reread, and fail closed if it is still ambiguous.
   Interrupted, or ambiguous still unresolved, means recovery: do not mutate the
   suspect output, inventory and hash it into a recovery Markdown FileRef,
   compare it against the last valid handoff, and publish `partial` with empty
   blockers when unaffected fresh candidate work remains or `blocked` with an
   `interrupted:write-tests` blocker when it does not. Record the comparison, the
   disposition and the new candidate location before an authorized actor removes
   the lock. Resume only in a fresh candidate revision, never in place.
2. **Validate before consuming the predecessor.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding **before** semantically reading `06-driver`. Exit
   0 with silent output is necessary; a missing interpreter, a timeout, a nonzero
   exit, or not running it is not a pass and blocks consumption. Report an
   unrelated stale artifact or ambiguous lock as a named blocker, and confirm
   with **hal-coordinator** that the consumed handoff is the exact
   `tests.api_handoff` intended for this name. When that exact API handoff is
   `partial`, continue only for the coordinator-authorized fresh candidate and
   link cycle, mutate nothing canonical, and preserve `partial` status.
3. **Load the workflow references and the predecessor.** Load this skill's
   test-record and hardware-execution references, then load
   `references/profiles/universal.md`, which applies to every driver. Classify
   the driver from the coordinator-supplied public contract and its positive
   rationale: add `gpio.md`, `time-driver.md` or `bus.md` when that category is
   positively established, and use universal-only when the record positively
   establishes that none applies. A missing or uncertain classification is
   `partial` or `blocked`, never permission to guess. Then load the exact
   `06-driver` leaves through the admission mapping above. Record every profile
   and reference read under `workflow-references-read`; a missing required
   reference is a blocker, not a reason to improvise.
4. **Inspect the live example and test conventions.** Inspect the checkout's
   permitted example and HIL layouts, manifests, target and link configuration,
   `ci.sh`, toolchain, formatting and contribution rules, and discharge
   `live-conventions-read` from what was actually read. Use the actual applicable
   patterns; teleprobe target declarations and RTT facilities apply only where
   the live setup uses them. Do not invent a board identifier or require
   infrastructure a reference board happens to have.
5. **Author the candidate test logic.** Author one behavior per example and
   separately identifiable validation cases under
   `halucinator/test-candidates/<name>/src/`, with its manifest and
   `INVENTORY.md`, deriving cases independently from the requirement IDs and the
   actual upstream trait obligations. A supplied checklist is a minimum, not an
   oracle derived from the driver. Apply the generic case families below where
   they are meaningful, give every test explicit assertions, an expected
   completion and an actionable failure signature, and report API ambiguity or
   unreachable behavior as a finding instead of reading the driver.
6. **Request materialization into the integration candidate.** Request through
   **hal-coordinator** that **hal-integrator** copy the test delta verbatim into
   a disposable integration candidate under
   `halucinator/candidates/integration-*/`, place the example and HIL binaries,
   their manifest, support files and runtime wiring, and wire the build-only
   `ci.sh` entry. The tester places no canonical file and runs no canonical
   build.
7. **Record the integrator's software evidence.** Request through
   **hal-coordinator** that **hal-integrator** run the repository-required
   formatting and lint checks over the candidate, and build and actually link
   every advertised in-scope binary and configuration, remembering that
   `cargo check` is not a link and that an indiscriminate `--all-features` is
   not a matrix, and build the build-only CI path, preserving separately
   authorized hardware-CI gates and documented exclusions with their reason and
   impact. You run none of those builds yourself: compiler, macro and
   build-script diagnostics quote implementation source and would defeat your
   blinding. Record the integrator's sanitized results, which carry no
   HAL-source excerpt, and discharge `format-lint`, `target-build-link` and
   `build-only-ci` from them. A build-only task stops after this step and
   returns its link results, the public setup requirements for future runtime
   work and a review handoff.
8. **Request hardware admission.** For `hardware-validation`, follow the
   hardware-execution reference to identify the exact fixture, probe or named HIL
   device, runner and intended operations, give the user cited physical setup
   instructions, and obtain separate confirmation of physical readiness and
   authorization for the named device operations. Discharge
   `hardware-admission` from evidence recording the device, runner, operations,
   electrical facts, readiness, authorization, RAM/link/load facts and
   observation path. Record it `not-applicable` with a reason when the scope is
   `build-only`.
9. **Run the authorized hardware cases and capture raw evidence.** Load and run
   the verified image yourself under bounded runners and per-case deadlines,
   capture raw logs into the candidate's `evidence/`, follow the documented safe
   teardown for successful and failed runs alike, and discharge
   `hardware-execution`. A successful load, empty output or process exit alone is
   not a pass. Record it `not-applicable` with a reason when the scope is
   `build-only`.
10. **Compare observations against expectations and route repairs.** Compare
    every captured observation with its recorded expectation, preserve the
    failing image, fixture, commands and logs before changing anything, and route
    each finding by owner through **hal-coordinator** using the table below.
    Uncertain failure ownership is a finding, not authority to open the driver;
    a failing case is retained unless an independently justified contract or test
    correction changes it, and that reason is recorded.
11. **Publish the preliminary handoff, validate it, and obtain the review.**
    Publish the preliminary `07-tests-<name>` with candidate ArtifactRefs,
    preserving a hashed snapshot and recovery record of any deterministic handoff
    `state.toml` currently pins before replacing it, run
    `python .opencode/schema/validate.py <repository-root> --kind all` again,
    then request through **hal-coordinator** the independent **hal-reviewer**
    review over `tests.review_input_manifest` and the frozen candidate, and
    discharge `independent-review` from the accepting verdict. Only
    review.verdict=ready accepts; ready-with-fixes and not-ready do not.
12. **Re-attest, republish the canonical references, and run the final gate.**
    Re-attest where referenced bytes changed — preserve the superseded evidence
    and review records, create replacement evidence at a new path rather than
    overwriting one, rerun only the affected checks, and obtain a new review
    where the reviewed bytes changed — then, after **hal-integrator** places and
    commits the reviewed bytes, republish the final
    `halucinator/handoff/07-tests-<name>.toml` with canonical ArtifactRefs,
    validate it, let **hal-coordinator** update `state.toml` through the
    compare-and-swap sequence, run the final `--kind all` gate, and return the
    record path, status and next action. Limit every runtime claim to the
    hardware and cases actually observed.

Generic case families, applied only where they are meaningful: cancellation
followed immediately by another operation; drop, reborrow and reconstruction
through legal public ownership paths; safely induced errors followed by
recovery rather than only the first error report; small, boundary and
documented-limit inputs, with configuration rejection where an invalid value can
actually be expressed; trait-based calls as well as inherent methods; concurrent
permitted users; and bounded repeated, stress and soak operations. Do not
manufacture an impossible input through unsafe access, weaken an upstream
contract, or turn one peripheral's failure model into a requirement for another.

Repair routing, every entry returning through **hal-coordinator**:

| Finding | Next action |
|---|---|
| Owned candidate or harness defect | Fix the candidate without weakening its contract, request a fresh integration candidate build, and rerun the affected cases. |
| Driver or API defect, or an unresolved contract | Return the public reproduction, the expected and observed results and the logs to **hal-coordinator**, which routes them to **hal-driver** and **hal-reviewer**. Do not inspect or repair HAL bodies. |
| Missing hardware meaning or PAC support | Return through **hal-coordinator** to **hal-datasheet** or **hal-svd**; do not invent a value or bypass the PAC. |
| Shared startup, linker, build or CI defect | Return through **hal-coordinator** to **hal-integrator** or **hal-driver**, with permitted build and ELF evidence only. |
| Missing setup, permission, tool or instrumentation | Record a named blocker and the exact next action; do not silently hand test execution to the user. |

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `build-only-ci` | Record the integrator's build of the repository's build-only CI path over the integration candidate | `halucinator/test-candidates/<name>/evidence/build-only-ci.log` |
| `format-lint` | Record the integrator's run of the repository-required formatting and lint checks over the candidate | `halucinator/test-candidates/<name>/evidence/format-lint.log` |
| `hardware-admission` | Record the fixture, runner, named operations, electrical facts, readiness and authorization | `halucinator/test-candidates/<name>/evidence/hardware-admission.md`, or `reason (no evidence FileRef)` when the scope is `build-only` |
| `hardware-execution` | Run the authorized cases on the confirmed fixture and capture raw logs and teardown | `halucinator/test-candidates/<name>/evidence/hardware-execution.log`, or `reason (no evidence FileRef)` when the scope is `build-only` |
| `independent-review` | Request the coordinator-dispatched review over `tests.review_input_manifest` and record its accepting verdict | `halucinator/handoff/08-review-tests-<name>.toml` |
| `live-conventions-read` | Record the live example, HIL, manifest, CI and toolchain conventions actually inspected | `halucinator/test-candidates/<name>/evidence/live-conventions.md` |
| `target-build-link` | Record the integrator's build and actual link of every advertised in-scope binary and configuration | `halucinator/test-candidates/<name>/evidence/target-build-link.log` |
| `workflow-references-read` | Load the test-record, hardware-execution and peripheral validation references and record which were read | `halucinator/test-candidates/<name>/evidence/workflow-references.md` |

The validator wiring above is an **honor system**. The self-check can prove this
skill contains the instruction; it cannot prove an agent ran it, and
`validate.py` cannot attest to its own earlier invocation. The same is true of
source blindness, the locks and the review gate: they are discipline plus
disclosure, and no part of this document may describe them as enforcement.
Typed evidence hashes freshness, not relevance.

## Exit criteria

### ready

Predicate: `coverage.incomplete` is empty, `coverage.complete` equals the
included scope, `handoff.can_progress` is absent, `handoff.blockers` is empty,
the consumed `06-driver` is `ready` against the current `scope.revision` and
`scope.decision`, `tests.owned_files` and `tests.review_input_manifest` resolve
to the reviewed bytes that were placed canonically, `tests.dependencies`
identities and features are current, every applicable check is `passed`, and the
independent review accepted. A `build-only` scope additionally has every
`[[tests.hardware_runs]]` entry `not-run`; a `hardware-validation` scope has
every required applicable run `passed` with safe teardown, a present
`tests.setup_record`, and no unresolved required finding. Only
review.verdict=ready accepts; ready-with-fixes and not-ready do not. Build-only
software completion never closes a peripheral's separate hardware gate.

### partial

Predicate: `handoff.can_progress=true`, `handoff.blockers` is empty, and either
`coverage.incomplete` is nonempty or at least one applicable check is `unrun` or
`failed`. A candidate revision that **hal-integrator** has not yet materialized
and built is `partial` by construction, with candidate ArtifactRefs rather than
canonical ones.

### blocked

Predicate: `handoff.can_progress=false`, `handoff.blockers` is nonempty, and
either `coverage.incomplete` is nonempty or at least one applicable check is
`unrun` or `failed`. Missing physical setup, absent operation authorization, an
unavailable tool, probe or fixture, and an unavailable reviewer are all blockers.
Never downgrade a required hardware-validation scope to build-only to clear one.

## Application example

For driver `uart` on `AX100` with a loopback fixture, the coordinator dispatches
`hardware-validation` for both an example and assertion-based validation. The
emitted handoff, published at `halucinator/handoff/07-tests-uart-loopback.toml`
because `tests.name` is `uart-loopback`:

```toml
[handoff]
schema = 1
stage = "write-tests"
status = "ready"
inputs = [
  { path = "halucinator/handoff/06-driver-uart.toml", sha256 = "5c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" },
]
notes = [
  { path = "halucinator/docs/acme-ax100/notes/tests/uart-loopback/TESTS.md", sha256 = "6d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c" },
]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e" }

[coverage]
complete = ["requirement:uart-blocking-echo", "requirement:uart-dma-echo"]
incomplete = []

[tests]
name = "uart-loopback"
output_kind = "both"
execution_scope = "hardware-validation"
api_handoff = { path = "halucinator/handoff/06-driver-uart.toml", sha256 = "5c1f0b7a2d4e6f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }
owned_files = [
  { path = "tests/ax100/src/bin/uart_loopback.rs", sha256 = "8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f" },
  { path = "examples/ax100/src/bin/uart_echo.rs", sha256 = "91a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f80" },
]
setup_record = { path = "halucinator/test-candidates/uart-loopback/evidence/hardware-admission.md", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" }
review_input_manifest = { path = "halucinator/test-candidates/uart-loopback/INVENTORY.md", sha256 = "b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2" }

[[tests.dependencies]]
crate = "embassy-acme"
identity = "0.1.0"
features = ["ax100", "defmt"]

[[tests.coverage]]
id = "requirement:uart-blocking-echo"
status = "passed"
test_case = "uart_loopback::blocking_echo"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/hardware-execution.log", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }

[[tests.coverage]]
id = "requirement:uart-parity-error"
status = "not-applicable"
test_case = "uart_loopback::parity_error"
reason = "The public configuration surface cannot express a parity mismatch on a single-device loopback fixture, so the case is unreachable through the API under test."

[[tests.hardware_runs]]
test_case = "uart_loopback::blocking_echo"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/run-001.log", sha256 = "d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4" }
teardown = "Probe detached and target power removed by the user; fixture wiring left in the documented safe state."

[[checks]]
id = "workflow-references-read"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/workflow-references.md", sha256 = "e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5" }

[[checks]]
id = "live-conventions-read"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/live-conventions.md", sha256 = "f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6" }

[[checks]]
id = "format-lint"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/format-lint.log", sha256 = "08192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f7" }

[[checks]]
id = "target-build-link"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/target-build-link.log", sha256 = "192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708" }

[[checks]]
id = "build-only-ci"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/build-only-ci.log", sha256 = "2a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f70819" }

[[checks]]
id = "hardware-admission"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/hardware-admission.md", sha256 = "a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091" }

[[checks]]
id = "hardware-execution"
status = "passed"
evidence = { path = "halucinator/test-candidates/uart-loopback/evidence/hardware-execution.log", sha256 = "c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3" }

[[checks]]
id = "independent-review"
status = "passed"
evidence = { path = "halucinator/handoff/08-review-tests-uart-loopback.toml", sha256 = "3b4c5d6e7f8091a2b3c4d5e6f708192a3b4c5d6e7f8091a2b3c4d5e6f708192a" }
```

A fact nobody established is an absent key or an empty collection, never a
sentinel word. Coverage status is `passed`, `failed`, `blocked` or
`not-applicable`; hardware-run status is `passed`, `failed`, `blocked` or
`not-run`; a Check is `passed`, `failed`, `unrun` or `not-applicable`. None of
those three is the stage vocabulary.

## Quick reference

| Element | Value |
|---|---|
| Stage | `write-tests` |
| Emitter | `hal-tester` |
| Emitted handoff | `halucinator/handoff/07-tests-<name>.toml`, kind `07-tests`, `<name>` equals `tests.name` |
| Consumes | the exact validated `06-driver` named by `tests.api_handoff` — `ready` normally, `partial` only for the bounded candidate and link cycle |
| Validation profiles | always `references/profiles/universal.md`, plus exactly the positively classified `gpio.md`, `time-driver.md` or `bus.md` |
| Checks | `build-only-ci`, `format-lint`, `hardware-admission`, `hardware-execution`, `independent-review`, `live-conventions-read`, `target-build-link`, `workflow-references-read` |
| Tester-owned classes | `test-candidate-source`, `test-candidate-manifests`, `test-candidate-evidence`, `tests-handoff` |
| Integrator-owned deltas | `example-binaries`, `example-manifest`, `example-support`, `hil-tests`, `runtime-wiring`, `ci`, `test-records` |
| Candidate root | `halucinator/test-candidates/<name>/` with `src/`, its manifest, `INVENTORY.md` and `evidence/` |
| Routing | every question, repair, review request and dispatch returns to `hal-coordinator` |
| Validator | `python .opencode/schema/validate.py <repository-root> --kind all`, before consumption and after each handoff write |
| Review gate | Only review.verdict=ready accepts; ready-with-fixes and not-ready do not. |
| Typed vocabularies | coverage `passed/failed/blocked/not-applicable`; hardware run `passed/failed/blocked/not-run`; Check `passed/failed/unrun/not-applicable`; stage `ready/partial/blocked` |
| Deferred | destination-crate deny-glob coverage |

## Common mistakes

- **Claiming a canonical file.** `examples/`, `tests/`, their manifests, the
  runtime wiring and `ci.sh` belong to `hal-integrator`. The tester supplies a
  delta and names the materializer.
- **Routing to `hal-architect`.** Setup questions, findings and repairs return
  to `hal-coordinator`; the architect writes the architecture specification and
  dispatches nobody.
- **Using `bus.md` for a non-bus.** Bus-shaped `Instance`/`Info`/`Mode`,
  transfer, DMA and ISR patterns are not universal. Apply `bus.md` only after
  positive classification; GPIO and time drivers have their own profiles, and
  uncertain classification fails closed.
- **Skipping `universal.md` because a category profile was loaded.** The
  universal profile applies to every driver and a category profile is added on
  top of it, never in place of it.
- **Reading the driver to resolve an ambiguity.** That produces tests that agree
  with the implementation, including where it is wrong. Report the ambiguity.
- **Describing blindness as guaranteed.** `bash` is `ask`, `grep` matches the
  query rather than the path, and diagnostics quote source. Say so.
- **Calling the destination-crate gap closed.** The mitigation is a disclosed
  comparison and a prohibition, not a mechanism, and dynamic frontmatter
  generation does not exist.
- **Reusing a confirmation for a different fixture or a more destructive load
  mode.** Physical readiness and operation authorization are separate facts and
  both are reconfirmed when anything changes.
- **Reclassifying a required hardware run as build-only.** Unavailable hardware
  is a blocker, not a narrower scope.
- **Treating a successful load, empty output or a zero exit as a pass.** A test
  needs an explicit assertion and a recognized completion record.
- **Deleting or relabelling a failing case.** Preserve the failing image,
  fixture, commands and logs before anything changes.
- **Mangling the typed vocabularies.** Coverage, hardware-run and Check statuses
  are their own closed sets, and none of them is the stage status.
- **Quoting only the rejecting verdict.** Stating what does not accept, without
  stating what does, turns the gate into advice. Use the exact sentence.
