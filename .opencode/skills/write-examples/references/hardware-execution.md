# Hardware Execution

This is **hal-tester**'s generic setup and execution procedure for
`write-examples`. Peripheral validation references supply the specific fixtures,
stimuli, and expected behavior; they do not replace these execution gates.
Use the test-record reference loaded by the skill for evidence fields.

An explicitly build-only task does not enter this procedure or require hardware
readiness. For runtime work, source blindness remains mandatory throughout:
use public contracts, permitted build/ELF metadata, and captured test output,
not HAL bodies, debugger source views, or disassembly to reconstruct them.
Tool approvals remain required; this procedure grants no extra permissions.

## 1. Identify the fixture and supported runner

Before a target-affecting operation, identify the exact board/MCU and revision,
probe or named HIL device, runner, and intended operations. Resolve ambiguous
device selection before attaching, resetting, loading, or running. Check actual
tool versions, supported commands, device access, and a public observation
channel. A named tool is not evidence it supports this target or loading mode.

Use gathered MCU and board documentation to give the user exact physical setup
instructions with pin/header mappings, voltage and load constraints, required
instrumentation, power/reset sequencing, and citations. Account for existing
firmware and boot states, including safe setup before loading and safe teardown
afterward. Missing electrical facts block the affected setup; never guess a
connection or assume a powered pin is harmless. Do not invent a resistor value,
memory address, or loader flag to complete a recipe.

If preparation firmware is needed before wiring, treat it as its own authorized
device operation. Plan each intermediate power, reset, and connection state;
the final fixture being safe does not establish that the preparation is safe.
Shared linker/startup changes return through **hal-architect** to their owner.
Do not turn a test into a custom loader or instrumentation project.

## 2. Confirm readiness and authorization

Obtain user confirmation of the physical setup appropriate to that step and
authorization for the named device operations. A connected probe, installed
flashing tool, available credential, or build-only dispatch is not consent.
The user performs physical actions, not test commands. Missing tool/device
access is a blocker, not a reason to substitute a human-run recipe.

If the specialist cannot ask directly, return a **setup-required** handoff to
**hal-architect**: cited instructions, exact outstanding questions, named device,
and requested operations. Resume with the recorded confirmation. Reconfirm when
hardware, wiring, power arrangements, operation scope, or risks change; do not
reuse confirmation for a different fixture or more destructive loading mode.

## 3. Select and verify the execution mode

**Prefer RAM execution** when a supported path preserves the behavior under
test. Before loading, verify from cited target facts and actual runner support:

- The selected memory is executable and debug-loadable, with room for code,
  constants, data/BSS, stack, and test/log buffers. Writable RAM alone is not
  evidence of executable RAM.
- The image is genuinely RAM-linked. Inspect ELF load and execution ranges and
  the permitted linker/runtime contract, including data initialization, entry,
  stack, interrupt vectors or trap routing, and required synchronization. Do
  not simply copy a flash-linked image into RAM.
- The complete loader operation avoids nonvolatile erase/program operations;
  verify commands for the installed tool version rather than guessing flags.
  A flash algorithm running from RAM is still flash programming.
- A documented start/reset sequence invokes real public HAL initialization,
  rather than inheriting clocks, pins, or interrupts from previous firmware.
  Account for reset/power-loss behavior and any required reload.

RAM loading still overwrites volatile state and operates real peripherals, so
readiness and authorization still apply. Prefer an established loading path.
If RAM is unsupported, unverified, too small, or unsuitable for a required test,
record why; an ordinary failed assertion is not evidence that RAM is unsupported.

Flash is allowed only when the named device and intended erase/program ranges
are explicitly authorized. Explain that existing firmware may be overwritten
and request approval if it is not already recorded. Never silently turn RAM-only
authorization into flash programming or discard failed evidence when switching
modes. Ordinary testing does not authorize mass erase, security unlock,
fuse/option-byte changes, or destructive recovery.

A RAM run does not validate normal flash boot, bootloader handoff, or power-cycle
behavior. If those are required, arrange separately authorized coverage and keep
the gap open until observed. Retain each execution mode's results independently.

## 4. Load, run, and capture

Match the confirmed fixture, authorized operations, verified image, and runner
immediately before execution. Do not change tested inputs mid-run. Load and run
the binary yourself, using bounded runners and per-case deadlines. Use an
available host-side deadline when the target time driver is unverified; do not
add a time or logging driver merely to make the harness work.

Require explicit assertions and recognized completion/observation records. A
successful load, empty output, or process exit alone is not a test pass. For an
intentionally continuous example, define a bounded observation window and safe
stop in advance; report the observed demonstration, not an assertion-suite pass.

Capture raw logs and the record reference's image, setup, authorization, command,
and outcome evidence. Distinguish assertion failure, panic, timeout, transport
error, and unavailable hardware. Preserve failures before any bounded authorized
retry. Stop on unsafe or unexpected hardware behavior; do not repeatedly reset
a failing fixture or silently widen the operation scope.

## 5. Teardown and return evidence

Follow the documented safe teardown for both successful and failed runs. Do not
blindly restart unrelated firmware while the fixture is connected. Request any
physical disconnection or power action from the user and record outstanding
actions; do not claim the fixture is safe when that has not been established.

Keep build/link evidence separate from hardware results and limit runtime claims
to the actual hardware and cases observed. Missing setup, tools, instrumentation,
or required runs leave named blockers. Return the public test record and failures
to the main skill's evaluate/iterate step; execution is not permission to inspect
or repair the HAL implementation.
