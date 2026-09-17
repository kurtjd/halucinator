# GPIO Implementation Checklist

For **hal-driver** and read-only **hal-reviewer** use. **hal-tester** uses the
separate public validation reference, not this implementation-aware checklist.
The `GPIO-01` through `GPIO-15` IDs below refer to that specification loaded by
`write-gpio`; do not redefine the public contracts here.

Read the live MCXA GPIO implementation and `embassy-mcxa/DEVGUIDE.md` before
choosing types or ordering. Relevant sections include "The top level of the
crate", "Type Erasure and Constructors", "Configuration", "Error types",
"Bringing Up Clocks and Resets", "Asynchronous (Interrupt-Driven) Drivers",
and "Shared Static State and DMA". Record the actual section/file citations
from the executing checkout. This reference prescribes obligations, not MCU
registers or a frozen Rust API.

## Ownership and pin availability

Addresses **GPIO-01, GPIO-03, GPIO-06, GPIO-14, GPIO-15**.

- Reuse the live `peripherals!`, `Peri`, pin ownership, and GPIO type-erasure
  patterns. Generic identity can do its checking at construction without
  becoming a generic on every stored pin. Do not mechanically impose the I2C
  `Instance`/`Info`/`Mode` shape on GPIO or add runtime claim registries.
- Apply `AGENTS.md`'s finite-type discipline. Describe reconstruction through
  the actual ownership/reborrow API; `Drop` does not reissue a singleton.
- Validate exact MCU/package pin maps and dedicated debug, boot, oscillator,
  or other function ownership from citations. Follow the live feature policy
  for conditional singleton availability. Implement only the required mux
  relationships, not unrelated peripheral drivers or a new pinctrl framework.
- Separate ownership of a pin from shared banks, interrupt routes, clock gates,
  reset lines, and power guards. Construction/reconfiguration/drop of one pin
  must not reset the bank, discard another waiter's state, mask its shared IRQ,
  or release a clock still needed by siblings.
- Keep gating/reset/power policy in clocks through the established `Gate` and
  `enable_and_reset` contract at the owning initialization layer. Do not call
  bank reset on every pin constructor. Retain required shared lifetime guards
  with the resource owner. Architect-owned initialization and build-policy
  changes return through **hal-architect**.
- Reset stale state only within the resource actually owned. A per-pin token
  does not authorize clearing a global waker table. Shared-resource teardown
  must make all affected outstanding waits progress under the public contract,
  rather than silently strand them.

## Digital operations and configuration

Addresses **GPIO-02 through GPIO-06**.

- Use cited legal level, pull, drive, and direction/mux configurations. Defaults
  must not encode one board's tuning. Invalid inputs are rejected, not masked.
  Expose open-drain or other electrical modes only with documented semantics;
  do not silently invent emulation.
- Determine initial latch, direction, mux, and input-enable ordering from the
  manual so changing to output does not intentionally drive an unintended
  value. Review intermediate states and drop/reconfiguration too. Register
  ordering alone is not observed evidence of electrical glitch freedom.
- Read sampled input for input-state operations and commanded output state for
  `StatefulOutputPin`. Verify toggle's contract. Do not substitute input voltage
  for the output latch because it happens to match in an unloaded loopback.
- Use documented atomic set/clear/toggle accessors where available; otherwise
  use the checkout's synchronization appropriate to the actual concurrency
  model. A local interrupt mask is not automatically a multicore lock. Preserve
  unrelated bits and respect read-clear and write-one-to-clear semantics.
- Use generated PAC accessors, not replacement offsets/bitfield constants or
  handwritten raw register definitions. Missing metadata/accessors go to
  **hal-svd** through the architect; computed pin selections are not a license
  to re-encode the memory map.
- Implement the actual versions of `ErrorType`, `InputPin`, `OutputPin`, and
  `StatefulOutputPin` where their contracts apply. Use `Infallible` when the
  operation genuinely cannot fail. Keep fallible construction errors separate
  from infallible pin operations; do not invent shared impossible variants or
  a module `Result` alias.

## Interrupt-driven waits

Addresses **GPIO-07 through GPIO-14**.

- Determine from hardware facts which pins and resources can satisfy the full
  `Wait` contract. Scarce interrupt channels or routes need an explicit
  ownership/capability model; no silently unusable methods after pin type erasure.
- Follow the live IRQ binding or automatic-init model. Identify shared vectors,
  pending/enable behavior, event latching, and synchronization from citations.
  Never copy MCXA register semantics to another target by analogy.
- Keep observed event completion distinct from current input level where the
  contract requires it. A wake is a scheduling hint, not sufficient proof of
  the requested event. Already-satisfied level waits and new-edge waits have
  different conditions; do not implement every method as a level poll.
- Analyze stale-event cleanup, waker registration, arming, condition checking,
  ISR, and repoll as one ordering argument. Register before checking and close
  the arm/check window using the established synchronization and documented
  event behavior. Clearing a pending bit after arming can discard the new event.
- The ISR handles only the owned sources, retains required completion evidence,
  masks/acknowledges as documented, and wakes the appropriate waiters. Avoid
  interrupt storms on asserted level sources. Do not clear other pins' pending
  bits or use `unpend()` to hide a still-asserted source. Rearming must not erase
  the event a future is trying to observe.
- Cover every armed interval with `OnDrop` before cancellation can abandon it.
  Cleanup on cancellation/error, and on success before defusing the guard, must
  disarm the owned wait and leave reusable state. Check cancel-before-first-poll,
  cancel-after-arming, event-versus-drop, and immediate new waits. Stale wakers
  or events must not satisfy a later generation or disrupt siblings.
- No busy-wait on an async path, endless-pending or panic placeholders, and no
  timer-polled replacement for supported interrupt-driven GPIO. Use the actual
  live waker pattern; introducing a new async engine is not the objective.

## Verification and review

- Keep pure encoding/configuration or event-state logic testable where it
  naturally exists. Exhaust small legal domains and relevant invalid boundaries
  in tests of production functions. Do not create a disconnected hardware model
  or simulator solely to obtain host tests; explain when GPIO has no useful
  host-testable core.
- Review owned-state isolation and async ordering even when loopback passes.
  Finite hardware stress cannot exhaust all interleavings, and host models
  cannot establish electrical behavior. Use the public validation matrix to
  identify the required runtime evidence without prescribing the tester's code.
