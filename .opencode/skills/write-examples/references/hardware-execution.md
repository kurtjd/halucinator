# Hardware Execution

This is **hal-tester**'s generic setup and execution procedure for
`write-examples`. Peripheral validation references supply the specific fixtures,
stimuli, and expected behavior; they do not replace these execution gates.
Use the test-record reference loaded by the skill for evidence fields. Sections
1 and 2 discharge the `hardware-admission` check; sections 4 and 5 discharge
`hardware-execution`. Every setup question, repair and review request returns
through **hal-coordinator**; this procedure dispatches nobody.

An explicitly build-only task does not enter this procedure or require hardware
readiness. For runtime work, source blindness remains mandatory throughout:
use public contracts, permitted build/ELF metadata, and captured test output,
not HAL bodies, debugger source views, or disassembly to reconstruct them.
Tool approvals remain required; this procedure grants no extra permissions.

## 0. Acquire the worktree-local board interlock

Before section 1 and before **any** target-affecting operation, take the
interlock for the exact physical device:

```sh
python .opencode/schema/runtime.py acquire-board --root <repository-root> \
  --stage <stage> --board <board_id> --authorization <authorization-fileref>
```

It records an unpredictable `lease_epoch` and a `check_token`; keep both, and
pass them to every later command. Acquisition failing with
`BOARD_INTERLOCK_CONFLICT` means another claimant holds or may hold this board:
stop, do not remove the other lock, and report it.

Call this what it is. It is a **worktree-local, single-operator interlock**, not
a lease, a broker or a sandbox. It cannot see another clone of this repository,
another operator at the same bench, or a probe command typed directly into a
terminal. It is a strong default and a statement of intent, not enforcement.

`before-board-op` narrows the window between checking the token and using the
device; it cannot close it. A holder can pass the check, pause, lose or override
its epoch, and then resume a direct command. Treat any overlap as unknown and
stop.

If no prior lock is visible - including in a fresh clone - the helper creates the
interlock in `recovery-pending` with `board_state=unknown`, not `acquired`.
Absence of a lock is not evidence that a previous run tore the board down
safely. Go to section 6 before touching the device.

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
Shared linker/startup changes return through **hal-coordinator** to their owner,
which is **hal-integrator** for linker, runtime and CI wiring and **hal-driver**
for clock and reset implementation.
Do not turn a test into a custom loader or instrumentation project.

## 2. Confirm readiness and authorization

Obtain user confirmation of the physical setup appropriate to that step and
authorization for the named device operations. A connected probe, installed
flashing tool, available credential, or build-only dispatch is not consent.
The user performs physical actions, not test commands. Missing tool/device
access is a blocker, not a reason to substitute a human-run recipe.

If the specialist cannot ask directly, return a **setup-required** handoff to
**hal-coordinator**: cited instructions, exact outstanding questions, named
device, and requested operations. Resume with the recorded confirmation. Reconfirm when
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
modes. This workflow never performs mass erase, security unlock, fuse or
option-byte operations, or destructive recovery. No authorization obtained
within this workflow makes any of them permissible.

A RAM run does not validate normal flash boot, bootloader handoff, or power-cycle
behavior. If those are required, arrange separately authorized coverage and keep
the gap open until observed. Retain each execution mode's results independently.

## 4. Load, run, and capture

Revalidate the interlock immediately before each target-affecting operation,
then record the operation and the child it will launch:

```sh
python .opencode/schema/runtime.py before-board-op --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token>
python .opencode/schema/runtime.py begin-board-operation --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token> \
  --operation <none|attach|reset|load-ram|program-flash|run|halt|detach|power-change|fixture-change> \
  --child-kind <process-group|windows-job|external> --child-identity <identity>
```

`begin-board-operation` increments the attempt, records the operation ID and the
probe/runner child session, and sets the board active **before** the child is
launched. Attaching a debugger is itself a target-affecting operation and needs
its own `begin-board-operation`.

Record completion only after the child **and all its descendants** have
terminated and the observation channel is quiescent:

```sh
python .opencode/schema/runtime.py complete-board-operation --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token> \
  --operation-id <operation_id>
```

`--operation-id` is the identity `begin-board-operation` returned for the
attempt you are closing; the helper refuses without it, so keep it beside the
epoch and the token.

**Holder death is not operation death.** If the agent or host dies, the probe or
runner child it started may still be transferring or driving pins. A dead parent
proves nothing about the board. Never infer that an operation ended from a
process exit, an exit code, or elapsed time.

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

## 5. Safe state, teardown and interlock release

Establish safe state in **this order**, before any human contact with the
fixture:

1. Quiesce controllable DMA, interrupt and peripheral activity.
2. Establish the cited non-driving output state and the cited reset or halt
   state.
3. Ask the operator to de-energize external loads.
4. Collect all six hazard observations - outputs, DMA, interrupts, external
   loads, reset/halt, probe - with the operator confirmation any physically
   observed hazard requires.
5. Classify the board safe only when every hazard is accounted for and no
   outstanding human action remains.
6. Only then authorize the fixture change.

A different order needs verified assertion IDs specific to that board and
fixture. The existing GPIO and bus rules are **additive** and are never replaced
by this list: **never join driven outputs**, and **configure input before
output**.

Follow the documented safe teardown for both successful and failed runs. Do not
blindly restart unrelated firmware while the fixture is connected. Request any
physical disconnection or power action from the user and record outstanding
actions; do not claim the fixture is safe when that has not been established.

Then release, in this order: write the raw evidence; write the immutable
safe-state observation; update the live lock to reference it; re-read and verify
the epoch, attempt and evidence; and only then

```sh
python .opencode/schema/runtime.py release-board --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token>
```

The `07-tests` handoff is published **after** release and refers to those
immutable records. A lock is never released on the strength of a handoff that
does not exist yet.

## 6. Recovery when a run is interrupted

On entry, and whenever the interlock is interrupted or ambiguous, classify
before touching the target. **Declare the board state unknown before
reconnecting** - attaching a debugger drives pins, so it cannot be the step that
establishes safety.

```sh
python .opencode/schema/runtime.py begin-board-recovery --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token>
python .opencode/schema/runtime.py begin-recovery-operation --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token> \
  --operation <attach|reset|halt|detach|power-change|fixture-change>
python .opencode/schema/runtime.py complete-board-operation --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token> \
  --operation-id <operation_id>
python .opencode/schema/runtime.py append-recovery-attempt --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token> \
  --attempt-file <attempt-fileref> --attempt-number <n> \
  --outcome <interrupted|failed|verified>
python .opencode/schema/runtime.py verify-board-recovery --root <repository-root> \
  --stage <stage> --epoch <lease_epoch> --token <check_token> \
  --safe-state <safe-state-fileref>
```

`begin-recovery-operation` is the one command that makes this route completable.
Ordinary `begin-board-operation` keeps refusing while the board is unknown, by
design, so without it recovery is a room with no door: you could enter
`recovery-pending` and never observe anything. It is a narrow authorization, not
a general unlock - it permits only the observation operations above, never a
load, a program or a run; it marks the lock `operation_scope = "recovery"` so
`release-board` also keeps refusing; and completing one returns the interlock to
`recovery-pending` with the board **still unknown**. A recovery operation never
advances toward release on its own. Close each with `complete-board-operation`
and its `--operation-id`, exactly as for an ordinary operation.

Entering `recovery-pending` needs no produced evidence, deliberately: requiring
proof before recovery may begin is circular. Identify the recorded child
session and confirm it and its descendants are terminated and quiescent, or have
the operator physically disconnect and de-energize board and probe. Append a new
attempt file for every try; attempts are append-only and are never reordered,
replaced or removed. Only a verified attempt with a matching safe-state
observation reaches `recovery-verified`, and only from there may the board be
released or freshly acquired.

Never infer teardown from a process exit or from elapsed time. A timeout proves
that something is slow, not that anything stopped.

Keep build/link evidence separate from hardware results and limit runtime claims
to the actual hardware and cases observed. Missing setup, tools, instrumentation,
or required runs leave named blockers. Return the public test record and failures
to the main skill's evaluate/iterate step; execution is not permission to inspect
or repair the HAL implementation.
