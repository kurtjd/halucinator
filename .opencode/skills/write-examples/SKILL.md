---
name: write-examples
description: >-
  Use when creating, building, running, or resuming public-API examples and
  hardware-in-the-loop tests for an Embassy HAL. Owns hal-tester's generic
  build/link, documented user setup, RAM-first load/run, result evaluation,
  and repair/retest workflow. Also supports explicitly build-only scaffold
  checks. Combine with the applicable peripheral's public validation guidance.
compatibility: opencode
---

# Write Examples and Hardware Tests

**hal-tester** owns this workflow. It selects the applicable peripheral's
**public validation** entry/reference for cases, fixture constraints, and
expected behavior. This skill owns the reusable binary and execution mechanics;
do not copy peripheral matrices here or re-enter this workflow when loading one.

Read the [public test-record reference](./references/test-record.md) at intake.
For hardware-validation tasks, also read and follow the
[hardware-execution procedure](./references/hardware-execution.md) before setup
planning or target-affecting operations. Missing required references block the
affected work; do not fall back to a remembered procedure.

## Boundaries

- Work only from the supplied public API/contracts, cited hardware/board facts,
  and permitted example/build files. Do not read HAL bodies, copied private
  notes, full implementation records, or debugger source/disassembly to infer
  the implementation. Skill selection does not change agent permissions.
- Own example/HIL binaries, their local build configuration, build-only CI
  integration, and public setup/run evidence. Driver code and private host
  tests belong to **hal-driver**; shared startup, feature, and clock policy
  remain with their existing owners.
- Return setup questions, findings, and other-agent work to **hal-architect**.
  Do not dispatch specialists. The architect supplies the task and scope; the
  tester selects its skills and designs independent tests.
- Respect the selected peripheral/modes and execution scope. No automatic
  hardware CI, new peripheral to provide logging/timeouts, or custom loader
  project. Build-only authorization never implies a device operation.

## 1. Inspect the handoff and resume

Read `AGENTS.md` from the handed-over working repository root, not relative to
the skill installation. Its artifact policy supplies location precedence and
path safety; keep existing layouts and unrelated edits. Inspect the supplied
public records and relevant test/build files before asking for missing facts.

Complete the record reference's "Identity and scope" fields from the handoff,
resolving missing or conflicting facts. Distinguish these two decisions:

- **Output kind:** a usage example, an assertion-based validation binary, or
  both. An example demonstrates use; it does not automatically satisfy a
  validation requirement.
- **Execution scope:** `build-only` or `hardware-validation`. Reuse an explicit
  dispatch/record; if unclear, resolve it through the architect before device
  operations. Continue only the unambiguous software work in the meantime.

Reuse the applicable public record and apply its resumption rules before relying
on earlier evidence.

A build-only task needs the facts required to compile/link its selected target,
not a connected board, probe, or confirmed wiring. Unknown facts block only the
decisions that depend on them. A required hardware run cannot be reclassified
as build-only simply because hardware is unavailable.

## 2. Turn public requirements into binaries

Read the live checkout's permitted example/HIL layouts and build conventions:
the relevant `examples/mcxa2xx/`, `examples/mcxa5xx/`, and `tests/mcxa2xx/`
references, manifests, target/link configuration, `ci.sh`, toolchain, formatting,
and contribution rules. Use their actual applicable patterns, not copied MCU
constants or assumed module names. Missing required live references are blockers.

Reuse suitable existing binaries and public test helpers. Keep examples in
`examples/<chip>/` and HIL binaries in `tests/<chip>/` according to the checkout.
Use its established harness, logging, panic, and runner integration; for example,
teleprobe target declarations and RTT facilities apply only where that live
setup uses them. Do not invent a board identifier or require unavailable
infrastructure merely because a reference board has it.

Write one behavior per example and separately identifiable validation cases.
Make names distinguish peripheral, mode, and purpose (trait, loopback, stress,
or soak) using local conventions. Put cited fixture requirements beside the
binary or link its public setup record. Do not embed an entire policy in every
example. Tests need explicit assertions, expected completion, and actionable
failure signatures.

Derive cases independently from the peripheral requirements and actual upstream
trait contracts. A provided checklist is a minimum, not an oracle derived from
the driver. Apply these generic case families only where meaningful:

- Cancellation followed immediately by another operation.
- Drop/reborrow/reconstruction using legal public ownership paths.
- Safely induced errors followed by recovery, not just the first error report.
- Small, boundary, and documented-limit inputs; configuration rejection where
  invalid values can actually be expressed.
- Trait-based calls as well as inherent methods, concurrent permitted users,
  and bounded repeated/stress/soak operations.

Report API ambiguity and inaccessible behavior instead of reading the driver.
Do not manufacture impossible inputs through unsafe access, weaken an upstream
contract, or turn one peripheral's failure model into a requirement for another.

## 3. Build, lint, and link

Derive commands, cwd, targets, dependencies, and feature combinations from the
actual checkout. Run repository formatting/lint checks and compile/link every
advertised in-scope binary/configuration. Do not use mutually exclusive
`--all-features` indiscriminately. `cargo check` is not an actual target link.

Wire the binaries into the repository's build-only CI conventions and verify
that path builds them. Preserve separately authorized hardware-CI gates, such
as credential conditions, and documented exclusions; do not enable runs merely
because a credential exists. Record exclusions with their reason and impact.

Record software checks and linked artifact identity using the record's evidence
and resumption rules. For a failure, use step 5's ownership table before repeating
the affected check.

**Build-only tasks stop before the next step.** Return build/link results,
public setup requirements or missing facts for future runtime work, and a
review handoff. Do not require hardware access to close a build-only gate or
claim the peripheral's separate hardware-validation gate is complete.

## 4. Set up and execute

For `hardware-validation`, follow the required hardware-execution reference,
applying the peripheral reference's fixture and stimulus requirements. That
procedure owns the readiness checks, loading, run, teardown, and setup-required
pause/resume handoff; return here to evaluate the captured results.

## 5. Evaluate, repair through the owner, and retest

Compare captured observations with each case's recorded expectation. Preserve
the failing input/image, fixture, commands, and logs before changing anything.
Do not relabel a failure as unsupported hardware or delete the case to pass.

| Finding | Next action |
|---|---|
| Owned example/harness defect | Fix the harness without weakening its contract, rebuild, and rerun affected cases. |
| Driver/API defect or unresolved contract | Return the public reproduction, expected/observed result, and logs through the architect to the driver author/reviewer. Do not inspect or fix HAL bodies. |
| Missing hardware meaning or PAC support | Return through the architect to the documentation/PAC owner; do not invent values or bypass the PAC. |
| Shared startup/linker/build defect | Return through the architect to the owning author, with permitted build/ELF evidence. |
| Missing setup, permission, tool, or instrumentation | Record a blocker and exact next action; do not silently hand test execution to the user. |

Uncertain failure ownership is a finding, not authority to open the driver.
Retain a failing case unless an independently justified contract/test correction
changes it, and record that reason. Use bounded retries for known transport or
fixture issues; stop and hand off when no justified local action remains.

After a repair, apply the record's resumption rules and repeat the affected
build and hardware steps. The hardware procedure determines when readiness or
operation authorization must be renewed.

## 6. Review and close the selected task

Return the public test/build changes, requirement coverage, citations, current
input identities, run evidence, and findings to **hal-architect** for independent
**hal-reviewer** review. Required findings must be resolved by their owner and
rechecked; stale review, an unavailable reviewer, or `ready with fixes` does
not close the task. The tester remains source-blind during this loop.

Apply the test record's scope-specific completion criteria and separate software
and hardware statuses. The architect closes only the selected task; unresolved
coverage and evidence gaps remain recorded there.

## Output

Return scope/output kind, public API and requirement coverage, changed binaries
and CI wiring, software results, public test-record/log paths, hardware outcomes
or setup-required handoff, review disposition, and unresolved owners/actions.
The peripheral's implementation record links this public evidence instead of
copying it or exposing private decisions to the tester.
