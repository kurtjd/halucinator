# Profile: GPIO

Selected when the dispatched subsystem is a digital pin subsystem: pin
ownership, mux, level, pull, drive, direction, and pin interrupts.

For **hal-driver** and read-only **hal-reviewer** use. **hal-tester** uses the
separate tester-safe validation guidance, not this implementation-aware profile.
Requirement IDs come from that public specification and from the coordinator's
dispatch; do not redefine the public contracts here.

Apply this profile **together with** the universal
[driver checklist](../driver-checklist.md), which already carries the
live-reference, generated-accessor, waker-ordering, cancellation, busy-wait and
host-testing rules. What follows is GPIO-specific.

## GPIO is not a bus

**Normative.** Reuse the live `peripherals!`, `Peri`, pin-ownership and GPIO
type-erasure patterns of the checkout. Generic identity can do its checking at
construction without becoming a generic on every stored pin. **Do not
mechanically impose the bus `Instance` / `Info` / `Mode` shape on GPIO**, and do
not add a runtime claim registry. A pin is not a transaction endpoint: it has no
per-transfer constructor, no transfer mode, and no error taxonomy split by
transfer direction. Importing that shape produces types whose inhabitants the
hardware cannot reach and deletes the ones it can.

## Ownership and pin availability

- Apply `AGENTS.md`'s finite-type discipline. Describe reconstruction through
  the actual ownership and reborrow API; `Drop` does not reissue a singleton.
- Validate the exact MCU and package pin maps from citations, including
  dedicated debug, boot, oscillator and other function ownership. Follow the
  live feature policy for conditional singleton availability. Implement only the
  required mux relationships, not unrelated peripheral drivers and not a new
  pin-control framework.
- Separate ownership of a pin from the shared banks, interrupt routes, clock
  gates, reset lines and power guards behind it. Construction, reconfiguration
  or drop of one pin must not reset the bank, discard another waiter's state,
  mask its shared interrupt, or release a clock a sibling still needs.
- Use the selected lifecycle contract at the owning bank/initialization
  boundary, and specify shared reset arbitration and lifetime accounting or its
  explicit absence. Do **not** call bank reset from every pin constructor. Changes to the owning initialization
  layer or to build policy return through **hal-coordinator**.
- Reset stale state only within the resource actually owned. A per-pin token
  does not authorize clearing a global waker table. Shared-resource teardown
  must make every affected outstanding wait progress under the public contract
  rather than silently stranding it.

## Digital operations and configuration

- Use cited legal level, pull, drive, and direction or mux configurations.
  Defaults must not encode one board's tuning. Invalid inputs are rejected, not
  masked. Expose open-drain or other electrical modes only with documented
  semantics; do not silently invent emulation.
- Determine the initial latch, direction, mux and input-enable ordering from the
  manual, so that changing to output does not drive an unintended value. Review
  the intermediate states and the drop and reconfiguration paths too. Register
  ordering alone is not observed evidence of electrical glitch freedom.
- Read **sampled input** for input-state operations and the **commanded output
  state** for `StatefulOutputPin`. Verify toggle's contract. Do not substitute
  input voltage for the output latch because the two happen to match in an
  unloaded loopback.
- Use documented atomic set, clear and toggle accessors where they exist;
  otherwise use the checkout's synchronization appropriate to the actual
  concurrency model. A local interrupt mask is not automatically a multicore
  lock. Preserve unrelated bits and respect read-clear and write-one-to-clear
  semantics.
- Implement the actual versions of `ErrorType`, `InputPin`, `OutputPin` and
  `StatefulOutputPin` where their contracts apply. Use `Infallible` when the
  operation genuinely cannot fail. Keep fallible construction errors separate
  from infallible pin operations; do not invent a shared impossible variant or a
  module `Result` alias.

## Interrupt-driven waits

- Determine from hardware facts which pins and resources can satisfy the full
  `embedded_hal_async::digital::Wait` contract. Scarce interrupt channels or
  routes need an explicit ownership or capability model; there must be no
  silently unusable method after pin type erasure.
- Follow the live interrupt-binding or automatic-initialization model. Identify
  shared vectors, pending and enable semantics, event latching and
  synchronization from citations. Never copy another target's register semantics
  by analogy.
- Keep **observed event completion** distinct from **current input level** where
  the contract requires it. A wake is a scheduling hint, not proof of the
  requested event. An already-satisfied level wait and a new-edge wait have
  different conditions; do not implement every method as a level poll.
- Analyze stale-event cleanup, waker registration, arming, condition checking,
  the handler and the repoll as one ordering argument. Register before checking,
  and close the arm-then-check window using the established synchronization and
  the documented event semantics. Clearing a pending bit after arming can
  discard the new event.
- The handler services only the owned sources, retains the required completion
  evidence, masks and acknowledges as documented, and wakes the appropriate
  waiters. Avoid interrupt storms on an asserted level source. Do not clear
  another pin's pending bits and do not unpend a still-asserted source. Rearming
  must not erase the event a future is trying to observe.
- Cover every armed interval with `OnDrop` before cancellation can abandon it.
  Cleanup on cancellation or error, and on success before defusing the guard,
  must disarm the owned wait and leave reusable state. Exercise
  cancel-before-first-poll, cancel-after-arming, event-versus-drop, and an
  immediate new wait. A stale waker or event must not satisfy a later generation
  or disturb a sibling.
- No busy-wait on an async path, no endless-pending or panic placeholder, and no
  timer-polled replacement for supported interrupt-driven GPIO. Use the live
  waker pattern; introducing a new async engine is not the objective.

## Verification and review

- Keep the pure encoding, configuration and event-state logic testable where it
  naturally exists. Exhaust the small legal domains and the relevant invalid
  boundaries in tests of the **production** functions. Do not create a
  disconnected hardware model or simulator solely to obtain host tests; explain
  instead when GPIO has no useful host-testable core.
- Review owned-state isolation and async ordering even when a loopback passes.
  Finite hardware stress cannot exhaust the interleavings, and host models
  cannot establish electrical behavior. Use the tester-safe validation matrix to
  identify the required runtime evidence without prescribing the tester's code.
