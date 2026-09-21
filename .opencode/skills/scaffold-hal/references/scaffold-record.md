# Scaffold Record

This reference is the content specification for the durable scaffold records of
stage `scaffold-hal`. It is not a HAL template, a PAC schema or a duplicate
roadmap, and it is not the exit gate: the exit predicates live in
`## Exit criteria` of [the skill](../SKILL.md) and the published status is
exactly `ready`, `partial` or `blocked`.

## Who writes what

`SCAFFOLD.md` and `STARTUP.md` are ownership class `platform-notes`, at
`halucinator/docs/*/notes/SCAFFOLD.md` and
`halucinator/docs/*/notes/STARTUP.md`. **hal-integrator** owns and materializes
both.

| Content | Semantic author | Materializer |
|---|---|---|
| Identity, bounded scope, first driver and modes, included and deferred work | **hal-coordinator** | **hal-integrator** |
| Roadmap, at exactly `halucinator/docs/<target-id>/notes/ROADMAP.md` | **hal-coordinator** | **hal-coordinator** (class `roadmap`) |
| Startup, clock and public API contracts | **hal-architect** in `ARCHITECTURE.md` (class `architecture-spec`), summarized here as a delta | **hal-integrator** |
| Clock, reset and frequency implementation notes and host-test results | **hal-driver** as a delta | **hal-integrator** |
| Shared-file inventory, candidate location, build and link evidence | **hal-integrator** | **hal-integrator** |
| Public setup and link-check evidence | **hal-tester** as a delta | **hal-integrator** |

Every delta is routed through **hal-coordinator**, which dispatches
**hal-integrator** to materialize it and returns its FileRef. No author edits a
class another agent owns.

Use repository-relative paths so the record survives moving the checkout.
Resolve paths and symlinks and confirm they remain inside the actual working
repository. Preserve prior decisions, blockers and evidence on resume: amend the
affected entries rather than replacing the file, because a source or PAC change
invalidates only the evidence that depends on it.

## Required sections

### Identity and scope

- Documentation directory and `SOURCES.md` path
- Destination crate
- Exact vendor and MCU part, package, silicon revision, board and board revision
- Cargo chip feature and Rust compilation target
- First planned peripheral and exact modes, explicitly assigned to the next
  stage
- Included supporting subsystems and deferred work
- The roadmap path, linked and never duplicated

An unresolved identity is recorded as an absent fact together with the decision
it blocks, not as a sentinel value in a typed field.

### Provenance and foundation coverage

- Applicable source IDs and cited-note paths
- Hardware citations as source ID, title or document number, revision, and
  section, table or page
- PAC crate, package, version or revision, selected chip feature, and generation
  provenance
- Checked foundation coverage for clock and reset, `init`, interrupts and
  peripherals, the generated mappings, `memory.x` and the linker and runtime
  wiring, and each in-scope supporting subsystem
- Missing unrelated PAC coverage, clearly marked non-blocking
- Temporary fork state. A fork permits disposable candidate work and prevents a
  `ready` handoff. Record its replacement by a permitted upstream release or
  revision, the rechecked coverage and the rerun evidence; preserve the history
  without treating it as permanent taint.

Any missing in-scope foundation register, accessor, interrupt or metadata item
blocks all scaffold implementation, including the structural files. Record that
only intake, record maintenance, inspection and analysis may proceed until
**hal-svd** closes the gap. Never substitute raw register access.

### Bounded decisions and contracts

- The selected startup clock and `init` path and what remains deferred, citing
  `ARCHITECTURE.md`
- Supporting-subsystem dependency order and the owner of each
- Public clock gating, reset, frequency and lifetime-guard contracts
- Top-level configuration and `init` policy
- Architectural citations to live MCXA files and DEVGUIDE sections
- Hardware citations for every hardware-specific decision

Record public API signatures and behavioral contracts needed by downstream
agents, never implementation bodies. Count legal inhabitants for each new public
finite type and state which invalid states cannot be expressed.

### Candidate, lock and shared-file inventory

- The integration candidate root under `halucinator/candidates/integration-*/`,
  and any `halucinator/candidates/driver-*/` or
  `halucinator/test-candidates/<name>/` revision it consumed
- The `kind="stage"` lock actually held, including `stage:scaffold-hal`,
  `global:hal-integration` and each `path:` resource
- Every shared file the integrator materialized, with its ownership class
- The canonical placement, if it happened, and the commit that carried it

`global:hal-integration` is a cooperative convention that fences nothing
mechanically. A durable integration journal, owner fencing and a cross-clone
crash marker are deferred; record the discipline actually followed rather than
claiming a guarantee.

### Verification evidence

Record observed runs in a table:

| Run time | Tested-state identity | Check | Command/cwd | Target/features | Outcome/artifact | Depends on |
|---|---|---|---|---|---|---|

Identify tested inputs with the commit plus tool-computed hashes of the relevant
dirty and untracked code and build inputs, or an equivalent content snapshot;
HEAD alone is insufficient in a dirty tree. Exclude `SCAFFOLD.md` itself unless
it affects the check. This records state without requiring a commit or a stash.
If a time or an identity cannot be established, do not invent it: the check
remains `unrun` and is rerun before closure.

Cover all ten canonical checks — `live-reference-read`, `foundation-coverage`,
`format-lint`, `advertised-builds`, `negative-chip-selection`,
`pure-host-tests`, `generated-mappings`, `target-link`, `build-only-ci` and
`independent-review` — using the schema Check vocabulary `passed`, `failed`,
`unrun` or `not-applicable` with a reason. Name the actual linked smoke
artifact; `cargo check` is not a link test. Distinguish process-scenario testing
of this toolkit from verification of a real HAL checkout.

Do not change inputs during a check or a review. A code, build-input, toolchain
or feature change invalidates the dependent evidence and findings: preserve the
superseded entries, create replacement evidence at a new path, and rerun only
the affected checks before clearing a blocker.

### Review, status and handoff

Record the reviewer, the reviewed scope and input identity, the findings, the
responsible owner, the disposition and the recheck evidence. Only
review.verdict=ready accepts; ready-with-fixes and not-ready do not, and an
unresolved required finding or an unreviewed required surface is not acceptance.

Record the published handoff status as exactly one of `ready`, `partial` or
`blocked`, using the skill's exit predicates. `ready` here means
frozen-candidate software readiness for the first driver dispatch; it is not a
claim about silicon, a complete peripheral driver or upstream acceptance.
Deferred out-of-scope work and separately dispatched hardware validation do not
prevent `ready` for this scope, and this stage's own checks remain build-only.

Also record:

- Each blocker, its affected scope, owner, next action and the evidence needed
- Pending hardware-validation handoffs and links to subsystem setup and run
  records
- The first-driver handoff inputs: exact MCU, modes, public foundation API and
  contracts, PAC identity, source IDs, cited notes, live MCXA references and
  host-test expectations
- The source-blind tester handoff: public signatures and contracts and cited
  build, memory and board facts only, never bodies

Do not paste the roadmap. Link it and record only scaffold-specific evidence and
changes to downstream readiness.

## Resume checklist

These checklists are operator aids. A ticked box is never the exit predicate.

- [ ] Identity matches the code, `SOURCES.md`, the PAC chip feature and the
      existing record.
- [ ] Dirty and unrelated user edits are preserved; overlapping intent is
      resolved rather than overwritten or forced into a commit or stash.
- [ ] Locks were classified as live, interrupted or ambiguous, and any recovery
      resumed in a fresh candidate rather than in place.
- [ ] Source and PAC provenance, code and build inputs, toolchain and features
      still match the recorded evidence.
- [ ] A change invalidated only the dependent decisions and checks, and the
      superseded evidence was preserved at its original path.
- [ ] The record and the actual public API agree, and no implementation body
      leaked.
- [ ] Blockers and review findings remain until fresh evidence closes them.
- [ ] The roadmap remains a link, not a duplicate.

## Completion checklist

- [ ] One exact MCU, one Cargo chip feature and one startup clock path are
      advertised.
- [ ] Foundation coverage and PAC provenance are verified and the temporary fork
      is cleared.
- [ ] Real `init` and the complete selected target lifecycle contract exist in
      `embassy-*/src/clocks/**`, authored by **hal-driver** against the
      architect's contract. MCXA names such as `Gate` and `enable_and_reset` are
      examples, required only if that contract selects them.
- [ ] Only the necessary supporting subsystems are complete; the first
      peripheral remains the next stage.
- [ ] Every applicable check has current recorded evidence and a schema Check
      status.
- [ ] The target smoke binary actually links and the build-only CI path builds
      it, with no hardware runner invoked.
- [ ] The review accepted the frozen candidate, and the reviewed bytes are the
      bytes placed canonically.
- [ ] The published status is one of `ready`, `partial` or `blocked`, and it
      matches the skill's exit predicate.
- [ ] Hardware execution is explicitly unclaimed.
