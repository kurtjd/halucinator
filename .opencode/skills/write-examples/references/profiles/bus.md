# Bus Validation Profile

This is the **public, tester-safe validation profile** for a serial bus driver —
UART, SPI, I2C or a comparable transfer-oriented peripheral. **hal-tester** loads
it in addition to [`universal.md`](./universal.md) **only when the
coordinator-supplied public contract positively establishes that the driver under
test is a bus driver**. GPIO and time drivers have their own profiles. An
uncertain classification fails closed: it is `partial` or `blocked` and returns
to **hal-coordinator**, never a guess.

It describes **observable behavior of a public API only**. It prescribes no
register sequence, no internal design and no private hook, and it asserts no
hardware fact. Every electrical, pin, clock and timing fact used by a case comes
from the cited documentation supplied at intake — `AGENTS.md` HAL-RULE-01 forbids
inventing one, and HAL-RULE-02 requires the document title and number, revision,
and section, table or page beside the claim.

## Intake and ownership

**hal-coordinator** supplies the exact MCU, package and board context, the
selected scope and roles, the public API signatures and behavioral contracts, the
applicable source IDs, the cited notes, and the actual documentation, PAC and
build locations. That supply includes the supported bus roles and modes, the
addressing or framing configuration surface, the chip features, the compilation
target, the public initialization and interrupt-binding requirements, the memory
and runtime facts including any DMA requirements, and an observation facility.

Use only public material and the permitted example and build files inside
**hal-tester**'s source boundary. Report API ambiguity, an unstated error model
or missing observability to **hal-coordinator** as a finding rather than reading
or repairing the implementation.

## Composition

Read `AGENTS.md` at the handed-over working repository root, sections "Artifact
storage and handoff" and "Hardware testing", for the shared boundaries; resolve
it from the actual working repository, never relative to the skill installation.
This profile supplies bus cases and fixture requirements to `write-examples` and
its required [test-record](../test-record.md) and
[hardware-execution](../hardware-execution.md) references. It is not a second
execution loop.

## Contract sources

Read the documentation for the **actual dependency versions in the executing
checkout**, for exactly the traits listed in `driver.trait_obligations` — for
example the `embedded-hal` and `embedded-hal-async` bus traits, or the
`embedded-io` and `embedded-io-async` read and write traits where the driver
claims them. Treat each listed obligation as a checklist item with its own case:
those are precisely the requirements one happy-path echo never exercises.

Below, **U** means the applicable upstream trait contract, **H** the supplied
public HAL contract and toolkit requirements, and **M** cited MCU and board
facts. Add the exact dependency version, or the document title and number,
revision, and section, table or page, to each applicable case.

## Verification matrix

For every row, record applicability, the concrete role, mode and configuration,
the expected result, the case or artifact, the owner, and the evidence. **Host**
means tests of actual pure production logic on the development machine, owned by
**hal-driver**, conditional on such logic existing. **Build** means compilation
and actual target linking; **HIL** means an observed agent-run hardware test,
both owned by **hal-tester**. **Review** is independent implementation review by
**hal-reviewer**.

| ID | Requirement and scenario | Expected result | Basis | Evidence and owner |
|---|---|---|---|---|
| BUS-01 | Construct each advertised instance in each advertised role — controller and target where both are claimed — and attempt duplicate ownership of one instance and unsupported pin or instance combinations using the existing compile-test facilities. | Legal public uses compile; illegal combinations are rejected as documented, without an unsafe bypass. A role the contract does not claim is recorded inapplicable, not assumed. | H, M | Build: tester; Review: reviewer |
| BUS-02 | Apply each advertised configuration value — bit rate or clock, framing, addressing, polarity or parity, and any documented limit — including an invalid value wherever the public surface can actually express one. | Legal configuration is accepted and observably in effect; an invalid value is rejected rather than silently truncated or clamped. Rate accuracy claims need an independent measurement, not the driver's own report. | H, M | Host when applicable: driver; HIL: tester; Review: reviewer |
| BUS-03 | Perform a single minimal transfer in the blocking mode on a documented fixture, in each claimed direction. | The bytes observed at the far end equal the bytes submitted, in order; the call returns the documented count or result. | U, H, M | HIL: tester |
| BUS-04 | Repeat BUS-03 in each additional advertised mode — asynchronous and DMA-backed where claimed — with the same data and fixture. | Every mode produces the same observable result as the blocking mode; a mode the contract does not claim is recorded inapplicable with its citation. | U, H, M | HIL: tester; Review: reviewer |
| BUS-05 | Exercise transfer boundaries: zero-length where the contract permits it, one byte, a length crossing any documented internal boundary, and the documented maximum. | Each boundary length behaves as documented; nothing reports success for bytes it did not move, and no length silently wraps or is truncated. | U, H | Host when applicable: driver; HIL: tester; Review: reviewer |
| BUS-06 | Issue several back-to-back transfers on one instance without reconstruction, mixing directions and lengths where the role permits. | Each transfer's data is delimited correctly; no residue from one transfer appears in the next, and no transfer is dropped or duplicated. | U, H | HIL: tester; Review: reviewer |
| BUS-07 | Cancel an asynchronous transfer before its first poll and again after it is armed, then immediately start another transfer on the same instance. | No abandoned transfer blocks the next one, completes falsely, or leaves the bus or its buffers unusable. Constructing a future does not arm it; arrange the poll deliberately. | U, H | HIL: tester; Review: reviewer |
| BUS-08 | Cancel a DMA-backed transfer at the same two points where DMA is claimed, then start another. | The next transfer is correct and complete; a dropped transfer leaves no hardware still moving data into or out of a buffer that is gone. | U, H, M | HIL: tester; Review: reviewer |
| BUS-09 | Safely induce each error the public contract can report — for example a framing, parity, overrun or arbitration condition, exactly as the supplied contract and cited facts define them — using only the fixture and the public surface. | The reported error matches the contract for that condition; no error is invented for a condition the contract does not define. | U, H, M | HIL: tester; Review: reviewer |
| BUS-10 | After each induced error, perform a normal transfer on the same instance without reconstructing it; then induce a second, different error where the fixture allows and check it is reported. | The peripheral recovers and the following transfer succeeds; no earlier condition remains latched so that it suppresses, repeats or misreports the next one. | U, H, M | HIL: tester; Review: reviewer |
| BUS-11 | Where the role permits, exercise the documented behavior when the far end does not respond, responds late, or stops mid-transfer. | The documented outcome occurs within the documented bound; the call does not hang unbounded, and an undocumented outcome is a finding, not a new requirement. | U, H, M | HIL: tester; Review: reviewer |
| BUS-12 | Operate one instance while constructing, reconfiguring, or dropping another that shares the documented resources — a peer instance, a shared clock domain, or a shared interrupt. | The first instance's configuration and in-flight transfer remain intact; an independent transfer on the peer is neither falsely completed nor stranded. | H, M | HIL: tester; Review: reviewer |
| BUS-13 | Drive the bus from several tasks or several futures within one task, exactly as far as the public sharing surface permits, and no further. | Every permitted concurrent user completes correctly; the API prevents unsynchronized concurrent use rather than corrupting a transfer. | U, H | HIL: tester; Review: reviewer |
| BUS-14 | Call every operation through each implemented upstream trait as well as through its inherent methods, and check each obligation listed in `driver.trait_obligations` separately. | Trait-based and inherent calls agree, and every listed obligation has its own case and result rather than being inferred from one echo. | U, H | Build/HIL: tester; Review: reviewer |
| BUS-15 | Build and actually link every advertised in-scope mode, feature combination and chip feature through public initialization, then run bounded repeated and soak transfers within the agreed run budget. | Every advertised combination links; sustained traffic shows no progressive loss, stall or resource exhaustion, and the run bound is recorded. A finite run is not proof of every interleaving. | U, H, M | Build/HIL: tester; Review: reviewer |

An unsupported role or mode is different from an unknown one, missing PAC
metadata, unimplemented behavior, an unreachable public surface, or unavailable
equipment. Only a cited capability limit or the explicitly agreed scope makes a
row inapplicable; record that citation as the reason. Missing equipment,
instrumentation or a second device leaves the required case `blocked`. Scope
reductions return to **hal-coordinator** for an explicit decision.

## Fixture and stimulus notes

1. Select the bus pins from the supplied board and MCU package documentation,
   within the public API's capabilities, and provide a connection table giving
   connector and pin, MCU pin, role, destination and citation. Check
   header-to-MCU mapping and any attached loads or debug, boot and oscillator
   conflicts under `write-examples`' hardware-execution procedure. Never invent a
   jumper position, a pull-up value, a termination or a supply voltage.
2. Plan role and mode transitions so that no wiring ever joins two driven
   outputs, including while existing firmware boots and while test firmware is
   being prepared. Apply that to any preparation image, power sequence and
   confirmation.
3. A self-loopback can hide correlated transmit and receive mistakes, and it
   cannot exercise a genuine second party, arbitration, or a far-end stall.
   Include meaningful negative controls, and record the cases a loopback cannot
   reach as requiring a second device or an instrument rather than as passes.
4. Use bounded trials and host-side runner deadlines, and avoid depending on an
   unvalidated time implementation for those deadlines. For a negative
   expectation, confirm the operation stays pending across a defined no-event
   interval before cancelling or supplying the event, so an intentionally pending
   transfer is not mistaken for a hung test.
5. Do not infer bit-rate accuracy, signal integrity, glitch freedom, setup and
   hold margins, every race interleaving, or whole-chip coverage from a pair of
   pins reporting the expected bytes. Record unavailable instrumentation as an
   evidence gap, not a pass.

## Results and handoff

Use `write-examples`' public test-record and output format. Include the bus
requirement-to-case mapping, the roles, modes and configuration exercised, the
fixture and its citations, the expected and observed results, the recorded bounds
of every soak run, and the unresolved API or instrumentation findings. Reuse the
existing source-blind setup and run record when supplied.

Return that record through **hal-coordinator**, which links it from the full
driver record without exposing implementation sections to the tester. For repairs
and retesting, follow `write-examples`' "Compare observations against
expectations and route repairs" step; this matrix remains the bus acceptance
specification.
