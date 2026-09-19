# Universal Validation Profile

This is the **peripheral-agnostic, tester-safe validation profile**. It applies
to **every** driver, without exception and without classification. **hal-tester**
loads it on every `write-tests` dispatch; a category profile is added on top of
it, never instead of it.

It exists so that no tester is ever blocked by a missing profile. Before this
file existed, only GPIO and time drivers had public validation guidance, which
meant a tester dispatched against any other peripheral had no required reference
to load and no permitted fallback — `write-examples` forbids substituting a
remembered procedure for a missing reference. This profile is the reference that
always exists.

It describes observable behavior of a public API, not the target HAL's
implementation or private state. It prescribes no register access, no internal
design and no private hook.

## Intake and ownership

**hal-coordinator** supplies the exact MCU, package and board context, the
selected scope, the tester-safe public API and its behavioral contracts, the
applicable source IDs, the cited notes, and the actual documentation, PAC and
build locations. That supply includes the chip feature, the compilation target,
the public initialization and interrupt-binding requirements, the memory and
runtime facts, and an observation facility. Function bodies, private notes and
the full implementation record are never supplied and are never requested.

Use only public material and the permitted example and build files inside
**hal-tester**'s source boundary. Report API ambiguity, missing contracts or
missing observability to **hal-coordinator** as a finding. Do not read or repair
the implementation to resolve one. Specialists do not dispatch peers: every
question, repair, review request and scope change returns to **hal-coordinator**.

## Composition

Read `AGENTS.md` at the handed-over working repository root — sections "Artifact
storage and handoff" and "Hardware testing" — for the shared boundaries. Resolve
it from the actual working repository, never relative to the skill installation;
a missing policy is a blocker.

This profile supplies cases and fixture requirements to `write-examples`. It is
not a second execution loop. Authoring, setup, load and run, repair and retest,
and the public record all follow `write-examples` and its required
[test-record](../test-record.md) and
[hardware-execution](../hardware-execution.md) references.

Requirements here are a **minimum**. The tester derives further independent,
adversarial cases from the public API, the upstream trait contracts and the
cited hardware facts.

## Contract sources

Read the documentation for the **actual dependency versions in the executing
checkout**. A published "latest" page identifies a contract; it does not
establish the version this HAL builds against.

In the matrix, **U** means the applicable upstream dependency contract named in
`driver.trait_obligations`, **H** the supplied public HAL contract and toolkit
requirements, and **M** cited MCU and board facts. Add the exact dependency
version, or the document title and number, revision, and section, table or page,
to each applicable case.

## Verification matrix

For every row, record applicability, the concrete configuration, the expected
result, the case or artifact, the owner, and the evidence. **Host** means tests
of actual pure production logic on the development machine, owned by
**hal-driver**, and is conditional on such logic existing. **Build** means
compilation and actual target linking; **HIL** means an observed agent-run
hardware test; both are owned by **hal-tester**. **Review** is independent
implementation review by **hal-reviewer**.

| ID | Requirement and scenario | Expected result | Basis | Evidence and owner |
|---|---|---|---|---|
| UNIV-01 | Construct the peripheral through every advertised public path; attempt duplicate ownership of the same instance and unsupported instance or capability combinations using the existing compile-test facilities. | Legal public uses compile; illegal ownership and capability combinations are rejected as documented, without an unsafe bypass. | H, M | Build: tester; Review: reviewer |
| UNIV-02 | Drop the constructed peripheral and reconstruct it through legal public ownership, reborrowing and reconstruction paths; repeat after a completed operation and after a failed one. | Reconstruction succeeds; no stale retained state prevents reuse or changes observed results on the second construction. | H | HIL: tester; Review: reviewer |
| UNIV-03 | Apply each advertised public configuration value and combination; where an invalid value can actually be expressed through the public surface, apply it. | Documented behavior is observed for legal values; an invalid value is rejected rather than silently truncated, masked or clamped. | H, M | Host when applicable: driver; HIL: tester; Review: reviewer |
| UNIV-04 | Exercise smallest, largest, empty and documented-limit inputs on every operation that takes a size, count, duration or buffer. | Boundary inputs behave as documented; nothing overruns, wraps silently or reports success for work it did not perform. | U, H | Host when applicable: driver; HIL: tester; Review: reviewer |
| UNIV-05 | Where the API is asynchronous, cancel before first poll and cancel after the operation is armed, then immediately start another operation on the same instance. | No abandoned operation blocks the next one, causes a false completion, or leaves the peripheral unusable. Constructing a future does not arm it. | U, H | HIL: tester; Review: reviewer |
| UNIV-06 | Safely induce each error the public contract can report, then continue using the peripheral. | The reported error matches the contract, and normal operation resumes afterwards; the first error is not the end of the recorded scenario. | U, H, M | HIL: tester; Review: reviewer |
| UNIV-07 | Induce an error and then immediately induce a second, different one where the fixture allows. | The second error is reported correctly; no earlier condition remains latched in a way that misreports or suppresses it. | U, H, M | HIL: tester; Review: reviewer |
| UNIV-08 | Operate one instance while constructing, reconfiguring or dropping another that shares the documented resources. | The first instance's configuration and operation remain intact; the peripherals are isolated as documented. | H, M | HIL: tester; Review: reviewer |
| UNIV-09 | Run concurrent permitted users from several tasks, and repeated operations within one task with repeated polls. | Every required operation completes; shared wakers or coalesced signalling neither strand a peer nor complete an operation before its contract allows. | U, H | HIL: tester; Review: reviewer |
| UNIV-10 | Call the peripheral through each implemented upstream trait as well as through its inherent methods, checking every obligation listed in `driver.trait_obligations`. | Trait-based and inherent calls agree, and each listed obligation is separately exercised rather than assumed from one happy path. | U, H | Build/HIL: tester; Review: reviewer |
| UNIV-11 | Build and actually link every advertised in-scope feature combination, chip feature and configuration through public initialization, including the build-only CI path. | Every advertised combination links; `cargo check` is not a link and an indiscriminate `--all-features` is not a matrix. | H | Build: tester; Review: reviewer |
| UNIV-12 | Run bounded repeated, stress and soak operations within the agreed run budget, mixing cancellation, error recovery and reuse. | No progressive degradation, resource exhaustion or undocumented failure; a finite run is not proof of every interleaving and its bound is recorded. | U, H | HIL: tester; Review: reviewer |
| UNIV-13 | Record, for every row above, whether it applies to this driver, and for each inapplicable row the cited capability limit or the explicitly agreed scope that makes it so. | Every row has a recorded disposition; non-applicability is a cited decision, never an omission. | H, M | Build/HIL: tester; Review: reviewer |

## Recording non-applicability

A row is inapplicable only when a **cited capability limit** or the **explicitly
agreed scope** makes it so. An unsupported hardware capability is a different
fact from an unknown capability, missing PAC metadata, unimplemented behavior,
an unreachable public surface, or unavailable equipment.

Record an inapplicable row as coverage status `not-applicable` with a reason
naming that citation or that scope decision. Missing equipment, missing
instrumentation or missing evidence leaves the required case `blocked`, not
`not-applicable` and never `passed`. A scaffold-support subset closes only its
assigned checks and does not claim completion of the full matrix.

Scope reductions return to **hal-coordinator** for an explicit decision. Do not
quietly delete, relabel or narrow a failing or blocked case to make the record
close.

## Results and handoff

Use `write-examples`' public test-record and output format. Include the
requirement-to-case mapping, the configuration and fixture actually used, the
expected and observed outcomes, the recorded bounds of every stress run, and the
unresolved API or instrumentation findings. Reuse the existing source-blind
setup and run record when one is supplied; do not create a duplicate test log or
redefine its statuses here.

Return that record through **hal-coordinator**, which links it from the full
driver record without exposing implementation sections to the tester. For
repairs and retesting, follow `write-examples`' "Compare observations against
expectations and route repairs" step; this matrix remains the acceptance
specification.
