# Driver handoff and durable record

For **hal-driver** to author and **hal-reviewer** to audit. **hal-tester** never
receives this file or its content: send the tester only public signatures,
observable contracts, versioned traits, build requirements and cited hardware
and board facts.

This reference covers two things that are deliberately not the same: the typed
`06-driver-<name>.toml` handoff, and the durable private record that the handoff
pins by hash.

## Where the record lives

Follow the working repository's root `AGENTS.md`, section "Artifact storage and
handoff", for every location — not a policy relative to the skill installation.
Prefer an explicit user-supplied path, then a previously recorded path for the
same target, then the default.

Record placement is **profile-conditional**, because `.opencode/ownership.toml`
registers exactly two paths in the `driver-records` class:

| Selected profile | Durable record |
|---|---|
| GPIO | `notes/GPIO.md` in the selected documentation directory, class `driver-records`, materialized by **hal-integrator** |
| Time driver | `notes/TIME-DRIVER.md` in the selected documentation directory, class `driver-records`, materialized by **hal-integrator** |
| Bus, or no profile on a positive finding | the typed `06` itself, hashed `handoff.notes` records under the driver's own candidate root, check evidence, and citations |

There is no `notes/DRIVER-<name>.md`. Creating one would require adding a
pattern to the ownership registry, which is an agent-layer change: return that
need to **hal-coordinator** rather than writing an unowned file.

Where a `driver-records` path applies, **hal-driver** authors the semantic
delta and **hal-coordinator** dispatches **hal-integrator** to materialize it
and return its FileRef. Link it from `SOURCES.md`, from the authoritative
roadmap, and from any supporting scaffold record instead of duplicating those
records; each of those links is itself a cross-owner delta on the same route.

## Identity and scope

- Exact vendor and MCU, relevant package and silicon revision, destination
  crate, chip features, Rust compilation target, and the actual documentation,
  source-list and PAC paths.
- Scope kind — a full subsystem task or bounded scaffold support — together with
  the selected instances, modes, electrical options, async capabilities, required
  dependencies, owned files, exclusions and exit criteria.
- The selected profile, the positive finding that selected it, and the rejected
  alternatives with their reasons.
- Applicable roadmap and scaffold links. An unresolved fact is recorded as
  unresolved, together with the decisions it blocks; it is never filled from
  memory.
- Per-capability disposition — supported, documented as unsupported,
  unimplemented, or blocked — using the public validation applicability rules.

## Provenance and decisions

- Source IDs, cited-note paths, document title and number, revision, and section,
  table or page for every hardware and board claim.
- PAC source, version and revision, generated provenance, chip feature, and the
  checked coverage for the registers, accessors, interrupts, mux and clock or
  reset support this subsystem needs.
- Live DEVGUIDE and checkout file citations, and the selected public ownership
  and API, the finite-type inventory with inhabitant counts, and the
  initialization, shared-resource, interrupt and teardown contracts. Keep public
  signatures clearly distinguishable from private design.
- Reserved resources and their ownership, the versioned upstream trait, queue
  and executor contracts relied on, and any feature-dependent availability.
- PAC fork or replacement history and the rechecks it affects, subject to the
  existing upstream and scaffold provenance gates.
- Validation requirement IDs, their cited contract basis, applicability, owners,
  planned evidence, and any deferred work approved through **hal-coordinator**.

## Evidence index

| Time | Check or decision | Input identity | Command, cwd, target, features | Result or record link | Depends on |
|---|---|---|---|---|---|

One row per canonical check in `write-driver`'s gate, including the reason for
any check recorded `not-applicable`. For review, record the reviewer, the scope
and input identity, the findings, the responsible owner, the disposition and the
recheck.

Identify the actual tested inputs: the commit plus tool-computed hashes of the
relevant dirty and untracked code and build inputs, or an equivalent content
snapshot. HEAD alone is insufficient in a dirty tree. Do not invent a timestamp
or a hash, and do not require a commit or a stash to obtain identity. Exclude
this record itself from the tested inputs unless it affects the check.

Link the tester's source-blind `write-examples` public test record and its raw
evidence, using that record's identity and status format. Reuse the existing
public artifacts, keep them separate from this private record, and record their
selected paths; do not copy logs or execution procedures here. That record holds
the requirement-to-case mapping and any independent measurements.

| Public run record | Image or input identity | Requirements covered | Depends on |
|---|---|---|---|

## Status

Status is the typed stage vocabulary of the `06` handoff — `ready`, `partial`,
`blocked` — and nothing else. There is no separate software or hardware status
table: the typed `06` status plus the linked `07-tests-<name>` handoff carries
everything the superseded two-dimension table used to. A fourth vocabulary
cannot be published, so it cannot be relied on.

A full hardware scope additionally carries a current `driver.public_test_record`.
A scaffold-support scope satisfies its own narrower gate with no hardware run;
label that scope and its remaining validation handoff explicitly, and never
promote it to full closure.

## Re-attestation and invalidation

These clauses are normative.

- **Do not change inputs during a check or a review.** A change made while a
  check is running invalidates the check, not the input.
- A change to code, to the source documents or PAC, to the toolchain, to the
  selected features, to the image, to the fixture, to the board, or to the
  execution mode **invalidates only the decisions, results and review that
  depend on it.** Compare each of those dimensions on resumption and on every
  change, and determine dependence rather than assuming it.
- **Preserve the old entries.** Record the invalidation, create replacement
  evidence at a new path rather than overwriting one, and rerun the affected
  checks **before** clearing any blocker. Never delete old evidence or an old
  review record to regain validation.
- Obtain a new review wherever the reviewed bytes changed. `review.lineage`
  records review rechecks only; it is not a general supersession mechanism.
- Reconfirm setup and authorization whenever they no longer match, as
  `write-examples`' hardware-execution procedure requires. Refreshed setup,
  authorization and public-run evidence follow that procedure, not a duplicate
  one here.
- Keep toolkit procedural checks distinct from runs of an actual target HAL.
  A green self-check of this toolkit is not a driver result.

## Blockers

For each blocker record affected requirements and scope, owner, next action, and
evidence needed. Missing tools or hardware never silently lower the gate.
Distinguish toolkit procedural checks from runs of an actual target HAL.
