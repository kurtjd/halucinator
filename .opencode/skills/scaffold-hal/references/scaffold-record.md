# Scaffold Record

Use this reference to create or maintain `SCAFFOLD.md` beside the explicitly
handed-over `SOURCES.md`. It is a durable handoff and evidence record, not a HAL
template, PAC schema, or duplicate roadmap.

Use repository-relative paths so the record survives moving the checkout.
Resolve paths and symlinks and confirm they remain inside the actual working
repository. If the required location is unavailable or escapes it, ask for
another in-repository path instead of falling back elsewhere. Preserve prior
decisions, blockers, and evidence on resume. Amend affected entries rather than
replacing the file; source or PAC changes invalidate only evidence that depends
on them.

## Required sections

### Identity and scope

- Documentation directory and `SOURCES.md` path
- Destination crate
- Exact vendor and MCU part, package, silicon revision, board and board revision
- Initial chip feature and Rust compilation target
- First planned peripheral and exact modes, explicitly assigned to next stage
- Included supporting subsystems and deferred work
- Authoritative roadmap path

Use `unknown` for an unresolved identity. Record which decision it blocks.
Link the existing authoritative roadmap. If none exists, **hal-architect**
establishes one inside the working repository and records its location here;
do not duplicate it in `SCAFFOLD.md`.

### Provenance and foundation coverage

- Applicable source IDs and cited-note paths
- Hardware citations as source ID, title/document number, revision, and
  section/table/page
- PAC crate/source, version or revision, selected chip feature, and generation
  provenance
- Checked PAC coverage for clock/reset, init, interrupts/peripherals, generated
  mappings, and each in-scope supporting subsystem
- Missing unrelated PAC coverage, clearly marked non-blocking
- Temporary fork status, if any; it prevents `software verified` only while in
  use. Record replacement by a permitted upstream release/revision, rechecked
  coverage, and rerun affected evidence; preserve history without permanent
  rejection.

Any missing in-scope foundation register, accessor, interrupt, or metadata item
blocks all scaffold code implementation, including structural files. Record
that only intake, record maintenance, inspection, and analysis may proceed
until **hal-svd** closes the gap. Never substitute raw register access.

### Bounded decisions and contracts

- Selected startup clock/init path and what remains deferred
- Supporting-subsystem dependency order and delegation owner
- Public clock gating, reset, frequency, and lifetime-guard contracts
- Top-level configuration/init policy
- Architectural citations to live MCXA files and DEVGUIDE sections
- Hardware citations for every hardware-specific decision

Record public API signatures and behavioral contracts needed by downstream
agents, but never implementation bodies. Count legal inhabitants for new public
finite types and state which invalid states cannot be expressed.

### Verification evidence

Record observed runs in a table:

| Run time | Tested-state identity | Check | Command/cwd | Target/features | Outcome/artifact | Depends on |
|---|---|---|---|---|---|---|

Identify tested inputs with the commit plus tool-computed hashes of relevant
dirty and untracked code/build inputs, or an equivalent content snapshot; HEAD
alone is insufficient in a dirty tree. Exclude `SCAFFOLD.md` unless it affects
the check. This records state without requiring a commit or stash. If time or
identity cannot be established, do not invent it: mark the evidence unverified
and rerun before closure.

Cover formatting/lint, advertised builds, applicable negative chip selection,
host functional-core tests, generated mapping checks, the actual target link,
build-only CI, and independent review/recheck. Name the linked smoke artifact;
do not describe `cargo check` as a link test. Distinguish process-scenario
testing of this skill from verification of a real HAL checkout.

For review, record reviewer, reviewed scope, findings, owner/disposition, and
recheck evidence. `ready with fixes` or any unresolved required finding does
not satisfy the gate.
Do not change inputs during a check or review. Code, build-input, toolchain, or
feature changes invalidate dependent evidence and findings; preserve old
entries, then use fresh evidence to clear blockers.

### Blockers, status, and handoff

- Status: `in progress`, `blocked`, or `software verified`
- Each blocker, affected scope, owner, next action, and evidence needed
- Pending human bench validation; state that no hardware was flashed or run
- First peripheral handoff: exact MCU, modes, public foundation API/contracts,
  PAC identity, source IDs, cited notes, live MCXA references, and host-test
  expectations
- Source-blind tester handoff: public signatures/contracts and cited build,
  memory, and board facts only; no bodies

Do not paste the roadmap. Link it and record only scaffold-specific exit
criteria, evidence, and changes to downstream readiness.

## Resume checklist

- [ ] Identity matches the code, `SOURCES.md`, PAC feature, and existing record.
- [ ] Dirty and unrelated user edits are preserved; overlapping intent is
      resolved rather than overwritten or forced into a commit/stash.
- [ ] Source/PAC provenance, code/build inputs, toolchain, and features still
      match recorded evidence.
- [ ] Changes have invalidated the affected decisions/checks only.
- [ ] Record and actual public API agree; no implementation bodies leaked.
- [ ] Blockers and review findings remain until evidence closes them.
- [ ] Roadmap remains a link, not a duplicate.

## Completion checklist

- [ ] One exact MCU and one startup clock path are advertised.
- [ ] Foundation PAC coverage and provenance are verified.
- [ ] Real init, `Gate`, `enable_and_reset`, and frequency plumbing exist.
- [ ] Only necessary support subsystems are complete; first peripheral remains
      the next stage.
- [ ] All applicable software checks have current recorded evidence.
- [ ] Target smoke binary actually links and build-only CI covers it.
- [ ] Independent review has no unresolved required finding and affected fixes
      were rechecked.
- [ ] Status accurately reflects remaining work or blockers.
- [ ] Hardware execution is explicitly unclaimed.
