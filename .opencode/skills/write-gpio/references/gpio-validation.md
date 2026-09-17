# GPIO Validation

This is the **public, tester-safe specification** for `write-gpio`. Both
**hal-driver** and **hal-tester** use its requirements; **hal-reviewer** audits
their coverage. It contains no target HAL implementation or prescribed private
design. Requirements are a minimum: the tester derives independent adversarial
cases from the public API, upstream contracts, and cited hardware facts.

## Intake and ownership

**hal-architect** supplies the exact MCU, package and board context, selected
scope, public API signatures and behavioral contracts, applicable source IDs,
cited notes, and actual documentation/PAC/build locations. Include supported
pin capabilities, chip features, compilation target, public initialization and
interrupt-binding requirements, memory/runtime facts, and an observation
facility. Do not send function bodies or the full implementation record.

Use only public material and permitted example/build files under **hal-tester**'s
source boundary. Report API ambiguity or missing observability rather than
reading or fixing the implementation.

Read and follow `AGENTS.md` at the handed-over working repository root, sections
"Artifact storage and handoff" and "Hardware testing", for shared boundaries.
Do not resolve it relative to the skill installation; a missing policy is a
blocker. **hal-tester** also invokes `write-examples` and follows its required
hardware-execution and public-record references. This document supplies GPIO
cases and fixture requirements to that workflow, not a second execution loop.
Implementation and review readers use the GPIO contracts, not the tester's
writing or hardware-execution procedures.

## Contract sources

Read the documentation for the actual dependency versions in the checkout:

- [embedded-hal digital traits](https://docs.rs/embedded-hal/latest/embedded_hal/digital/index.html):
  `ErrorType`, `InputPin`, `OutputPin`, and `StatefulOutputPin` where applicable.
- [StatefulOutputPin](https://docs.rs/embedded-hal/latest/embedded_hal/digital/trait.StatefulOutputPin.html):
   the output-state contract used by GPIO-04.
- [embedded-hal-async Wait](https://docs.rs/embedded-hal-async/latest/embedded_hal_async/digital/trait.Wait.html):
   the five level/edge contracts used by GPIO-07 through GPIO-11.

Below, **D** means the applicable digital trait contract, **W** the `Wait`
contract, **H** the supplied public HAL contract and toolkit requirements, and
**M** cited MCU/board facts. Add the exact dependency version or document
title/number, revision, and section/table/page to each applicable case. These
links do not replace the executing checkout's versions or target citations.

## Verification matrix

For every row, record applicability, concrete pins/capabilities, expected result,
case/artifact, owner, and evidence. **Host** means tests of actual pure production
logic on the development machine, owned by **hal-driver**; it is conditional on
such logic existing. **Build** means compilation and actual target linking;
**HIL** means an observed agent-run hardware test, both owned by **hal-tester**.
**Review** is independent implementation review by **hal-reviewer**.

| ID | Requirement and scenario | Expected result | Basis | Evidence and owner |
|---|---|---|---|---|
| GPIO-01 | Construct supported pins/modes; attempt duplicate ownership and unsupported capabilities using the existing compile-test facilities. | Legal public uses compile; illegal ownership/capability combinations are rejected as documented, without unsafe bypasses. | H, M | Build: tester; Review: reviewer |
| GPIO-02 | Drive low/high and a bounded pattern into a connected input, using inherent methods and digital traits. | Sampled input matches each stable driven value; errors follow the public contract. | D, M | HIL: tester |
| GPIO-03 | Construct outputs with each initial level; drop and reconstruct through legal public ownership/reborrowing. | Initial and subsequent state match the contract; no stale state prevents reuse. Electrical transition claims need appropriate instruments. | H, M | HIL: tester; Review: reviewer |
| GPIO-04 | Read commanded output state and toggle it; distinguish that state from sampled input without electrically contending outputs. | `is_set_high`/`is_set_low` describe the commanded drive state; toggle changes that state. | D, M | HIL: tester; Review: reviewer |
| GPIO-05 | Exercise each advertised pull, drive, or open-drain configuration with an appropriate fixture; check invalid configuration boundaries where expressible. | Documented behavior, including release versus drive, is observed; invalid input is rejected rather than truncated. | H, M | Host when applicable: driver; HIL: tester; Review: reviewer |
| GPIO-06 | Operate one pin while constructing, reconfiguring, or dropping another sharing the documented port resources. | The first pin's configuration and operation remain intact. | H, M | HIL: tester; Review: reviewer |
| GPIO-07 | `wait_for_high`: start both high and low; for low, drive high after the wait has started. | Already-high completes without another edge; otherwise completion follows the high event, even if the signal returns low before repoll. | W, M | HIL: tester; Review: reviewer |
| GPIO-08 | `wait_for_low`: start both low and high; for high, drive low after the wait has started. | Already-low completes without another edge; otherwise completion follows the low event, even if the signal returns high before repoll. | W, M | HIL: tester; Review: reviewer |
| GPIO-09 | `wait_for_rising_edge`: start both low and high; generate the necessary low-to-high transition. | Starting high alone does not complete the wait; a new rising event does, including a captured pulse before repoll. | W, M | HIL: tester; Review: reviewer |
| GPIO-10 | `wait_for_falling_edge`: start both high and low; generate the necessary high-to-low transition. | Starting low alone does not complete the wait; a new falling event does, including a captured pulse before repoll. | W, M | HIL: tester; Review: reviewer |
| GPIO-11 | `wait_for_any_edge`: start in each state and drive the opposite state. | Either transition completes; a stable starting level alone does not. | W, M | HIL: tester; Review: reviewer |
| GPIO-12 | Cancel before first poll and after arming, then immediately wait again; repeat using legal drop/reborrow/reconstruction paths. | No abandoned wait blocks the next operation or causes a false completion; other pins remain usable. | H, W, M | HIL: tester; Review: reviewer |
| GPIO-13 | Vary event timing around the first poll and later polls; delay repoll after a captured event; include repeated polls, stale events, and bounded stress. | No false completion or lost captured event; each required completion occurs within the test deadline. A finite run is not proof of every interleaving. | H, W, M | HIL: tester; Review: reviewer; Host if pure state logic exists: driver |
| GPIO-14 | Run independent waits on pins sharing an interrupt/resource; cancel one and stimulate the other, then repeat with roles exchanged where supported. | The correct wait completes; the other is neither falsely completed nor stranded by its sibling. | H, W, M | HIL: tester; Review: reviewer |
| GPIO-15 | Build/link every advertised in-scope feature combination through public initialization and the applicable traits; run the selected hardware cases on identified fixtures. | Builds and runtime results identify their actual scope; no untested chip, pin, mode, or boot path is claimed. | D, W, H, M | Build/HIL: tester; Review: reviewer |

An unsupported hardware capability is different from unknown capability, missing
PAC metadata, unimplemented behavior, or unavailable equipment. Only a cited
capability limit or the explicitly agreed scope makes a row inapplicable. Missing
equipment or evidence leaves required cases blocked. A scaffold-support subset
does not claim completion of the full GPIO matrix. Scope reductions return to
**hal-architect** for an explicit decision; do not quietly remove failing cases.

## Prepare a physical setup

1. Select accessible output/input pins from the supplied board and MCU/package
   documentation, within the public API's capabilities. Require a suitable
   interrupt-capable input for async cases. Check header-to-MCU mapping and
   attached loads or debug/boot/oscillator conflicts under `write-examples`'
   hardware procedure; never invent a jumper position or resistor value.
2. Provide a connection table with connector/pin, MCU pin, role, destination, and
   citation. Plan mode transitions so the jumper never joins two driven outputs,
   including while existing firmware boots or test firmware is prepared. Apply
   that procedure to any preparation image, power sequence, and confirmation.
3. Prefer one documented output connected to one documented input. A driven
   loopback cannot measure pulls; shared-interrupt isolation may need additional
   pins and independent stimuli. Request extra setup only for required coverage.

## GPIO-specific stimulus

Within `write-examples`' authorized execution loop:

1. For loopback, establish input mode safely before driving the output, then
   check stable low/high states and patterns. Reverse roles only when supported
   and with a transition that never leaves both ends driving. Coordinate async
   stimuli through public test code so waits are actually polled/armed before
   the event where the case requires it. Merely constructing an async future
   does not arm it. Exercise initially satisfied levels separately from edges.
2. Use bounded trials and host-side runner deadlines. For negative expectations,
   verify that the wait remains pending during a defined no-event interval,
   then cancel or provide the required event; an intentional pending wait must
   not be confused with a hung test. Avoid reliance on an unvalidated
   `embassy-time` implementation for the deadline. Test cancellation, immediate
   reuse, captured pulses, and applicable shared-resource cases independently.

GPIO self-loopback can hide correlated output/input mistakes. Include meaningful
negative controls and independently documented pin mappings. Use independent
stimulus or instrument measurements when required by the claim. Do not infer
voltage accuracy, glitch freedom, edge timing, all race interleavings, or
whole-chip coverage from two pins reporting the expected digital values.
Record unavailable instrumentation as an evidence gap, not a pass.

## Results and handoff

Use `write-examples`' public test-record and output format. Include the GPIO
requirement-to-case mapping, fixture and pin capabilities, expected/observed
outcomes, and unresolved API or instrumentation findings. Reuse the existing
source-blind setup/run record when supplied; do not create a duplicate GPIO
test log or redefine its statuses here.

Return that record through **hal-architect**, which links it from the full GPIO
record without exposing implementation sections to the tester. For repairs and
retesting, the tester follows `write-examples`' "Evaluate, repair through the
owner, and retest" section; this matrix remains the GPIO acceptance specification.
