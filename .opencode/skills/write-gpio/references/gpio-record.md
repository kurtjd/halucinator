# GPIO Record

For **hal-driver** and **hal-architect** to maintain, and **hal-reviewer** to
audit. Do not give **hal-tester** this full implementation/evidence record.
Supply public API/contracts and a separate source-blind setup/run handoff.

Follow the working repository's root `AGENTS.md`, section "Artifact storage and
handoff", for all locations, not a policy relative to the skill installation.
Reuse an explicit or applicable recorded GPIO record; otherwise use
`notes/GPIO.md` in the selected documentation directory. Link it from
`SOURCES.md`, the authoritative roadmap, and any supporting scaffold record.

## Identity and scope

- Exact vendor/MCU, relevant package and silicon revision, destination crate,
  chip features, build target, and actual documentation/source-list/PAC paths.
- Scope kind: full GPIO task or bounded scaffold support; selected pins/ports,
  digital modes, electrical options, async capabilities, required dependencies,
  owned files, exclusions, and exit criteria.
- Applicable roadmap/scaffold links. An unresolved fact is `unknown`, with the
  decisions it blocks.
- Per-capability disposition: supported, documented unsupported, unknown,
  unimplemented, or blocked, using the public validation applicability rules.

## Provenance and decisions

- Source IDs, cited-note paths, document title/number, revision, and
  section/table/page for hardware and board claims.
- PAC source/version/revision, generated provenance, chip feature, and checked
  coverage for pins, GPIO, mux, interrupts, and required clock/reset support.
- Live MCXA file/DEVGUIDE citations and the selected public ownership/API,
  finite-type inventory, initialization, shared-resource, interrupt, and teardown
  contracts. Keep public signatures clearly distinguishable from private design.
- PAC fork/replacement history and affected rechecks, subject to existing
  upstream/scaffold provenance gates.
- Validation requirement IDs, their cited contract basis, applicability, owners,
  planned evidence, and deferred work approved by the architect/user.

## Software and review evidence

| Time | Input identity | Check | Command/cwd | Target/features | Outcome/artifact | Depends on |
|---|---|---|---|---|---|---|

Identify actual tested inputs: commit plus tool-computed hashes of relevant dirty
and untracked code/build inputs, or an equivalent content snapshot. HEAD alone
is insufficient in a dirty tree. Exclude this record unless it affects the check.
Do not invent timestamps or hashes, or require a commit/stash to obtain identity.

Use one row per required software check in `write-gpio`'s completion gate,
including reasons for inapplicability. For review, record reviewer, scope and
input identity, findings, responsible owner, disposition, and recheck.

## Public setup and hardware runs

Link the tester's source-blind `write-examples` test record, with GPIO coverage
from the public validation reference's "Results and handoff" section. Reuse
existing public artifacts, keep them separate from this implementation record,
and record their selected paths; do not copy logs or execution procedures here.

| Public run record | Image/input identity | Requirements covered | Hardware status | Depends on |
|---|---|---|---|---|

## Status and resumption

Record separate statuses:

| Dimension | Values and meaning |
|---|---|
| Software | `in progress`, `blocked`, or `software verified`, according to `write-gpio`'s software completion gate. |
| Hardware | Aggregate the per-case statuses in `write-examples`' public test record; required GPIO cases must all pass for an overall `passed` status. |

Full GPIO validation requires `software verified` and `passed` hardware status
for the agreed scope, with no unresolved required findings. Scaffold support
can satisfy its own software-only gate with hardware `not run`; label that scope
and its later GPIO/HIL handoff explicitly. Never promote it to full GPIO closure.

Do not change inputs during checks/review. Code, source/PAC, toolchain, features,
image, fixture, board, or execution-mode changes invalidate only dependent
decisions, results, and review. Preserve old entries, record invalidation, and
rerun before clearing blockers. Reconfirm setup/authorization when it no longer
matches, as required by `write-examples`' hardware-execution procedure.

For each blocker record affected requirements/scope, owner, next action, and
evidence needed. Missing tools/hardware never silently lower the gate. Distinguish
toolkit procedural checks from runs of an actual target HAL.
