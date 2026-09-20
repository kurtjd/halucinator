# Universal driver implementation checklist

For **hal-driver**, and for **hal-reviewer** as read-only audit criteria.
**hal-tester** never reads this file: its tester-safe validation guidance is a
separate tree, and this one is implementation-aware by construction.

These obligations apply to **every** peripheral, whichever profile was selected.
Apply them together with exactly one profile, or alone when `write-driver`'s
classification step recorded a positive finding that no profile applies. This
reference prescribes obligations, not MCU registers and not a frozen Rust API.
Requirement IDs belong to the coordinator's dispatch, not to this file.

## Live-reference reading

- Read the live `embassy-mcxa/DEVGUIDE.md` and the actual implementation of the
  nearest comparable subsystem **in this checkout** before choosing types or
  ordering. Discover the layout rather than assuming a module path. Relevant
  sections include "The top level of the crate", "Type Erasure and
  Constructors", "Configuration", "Error types", "Bringing Up Clocks and
  Resets", "Implementing Upstream Trait Contracts", "Asynchronous
  (Interrupt-Driven) Drivers", and "Shared Static State and DMA".
- Record the actual section and file citations from the executing checkout.
  Missing live references block the affected implementation; this toolkit is not
  a snapshot substitute, and a remembered checkout is not a live reference.
- Follow documented intent over a local wart where the two differ, and say which
  you followed.
- Read the supplied documentation directory, `SOURCES.md`, the relevant source
  IDs and cited notes, and record provenance as the record reference specifies.
- Transfer the design discipline, never another target's counter encodings,
  clocks, register semantics or interrupt assumptions by analogy.

## Generated accessors and the memory map

- Use generated PAC field accessors. Replacement offsets, bitfield constants,
  hand-written raw register definitions and volatile accesses to a computed
  address are all the same defect: the driver has started re-encoding the memory
  map instead of describing hardware meaning.
- A block of private constants behind an allow-dead-code attribute is the usual
  symptom. Missing metadata or accessors return through **hal-coordinator** to
  **hal-svd**; a computed selection is not a license to bypass the PAC.
- Never hand-edit generated output.

## Finite types and the functional core

- Apply `AGENTS.md`'s finite-type discipline. A field with four legal values has
  a four-inhabitant type. Count the inhabitants of every public type against the
  legal states the hardware admits, and record the count.
- Parse at the boundary into a type that cannot be wrong, and speak the parsed
  type inside. A check that returns the same loose type invites every downstream
  function to re-check it.
- Encoding is total: every value you can construct is a legal register encoding,
  so it cannot fail. Decoding is partial: it meets reserved patterns the silicon
  can produce, so it returns a `Result`. Do not flatten that asymmetry.
- Keep the pure value-to-value logic — divisors, encodings, timing and layout
  arithmetic — free of registers, `async` and HAL types, and keep the
  register-touching shell nearly branch-free.
- Resist over-encoding. Encode the invariant a caller could plausibly get wrong
  at a call site, and newtype what crosses a boundary. A newtype per loop
  counter is the wrong abstraction with the compiler enforcing it.
- Reject out-of-range configuration rather than masking it. `Default` is the
  hardware-nominal reset configuration, never one dev board's tuning.
- Split errors by operation, mark them `#[non_exhaustive]`, and define no module
  `Result` alias. Use `Infallible` where an operation genuinely cannot fail, and
  keep fallible construction errors separate from infallible operations.
- No wildcard imports.

## Clocks, reset and shared resources

- Keep clock, reset and power policy in one owning layer and verify every
  minimum lifecycle element: policy owners, acquisition/initialization, reset
  arbitration, lifetime accounting or its explicit absence, teardown/quiescence,
  frequency source or irrelevance, and cancellation behavior. A peripheral module
  that configures the same resource has put the policy in two places that can
  disagree.
- Retain lifetime or wake ownership only when the contract requires it; record
  its explicit absence otherwise.
- Reset module-global mutable state — descriptor rings, flags, waker tables — at
  the top of construction, and only within the resource actually owned. An
  ownership token proves you own the live peripheral; it does not prove this is
  the first construction, and a per-instance token does not authorize clearing a
  global table.
- Separate ownership of one instance from the shared banks, interrupt routes,
  clock gates, reset lines and power guards behind it. Construction,
  reconfiguration or drop of one must not reset the shared block, discard
  another waiter's state, mask a shared interrupt, or release a clock a sibling
  still needs.
- Shared-resource teardown must make every affected outstanding wait progress
  under the public contract rather than silently stranding it.

## Interrupt-driven async

- **Register the waker before checking the condition.** Check-then-register
  loses any completion that lands in the window, and the future then sleeps
  forever. Treat stale-event cleanup, waker registration, arming, condition
  checking, the interrupt handler and the repoll as **one** ordering argument,
  and close the arm-then-check window with the checkout's established
  synchronization. Clearing a pending bit after arming can discard the new event.
- A wake is a scheduling hint, not proof that the requested condition holds.
  Re-check the real condition after every wake.
- The handler services only the sources it owns, retains the completion evidence
  the future needs, masks and acknowledges as the manual documents, and wakes the
  appropriate waiters. It does not clear another instance's pending bits and does
  not quiet a still-asserted level source by unpending it.
- Follow the live interrupt-binding or automatic-initialization model of the
  checkout. Identify shared vectors, pending and enable semantics, event latching
  and synchronization from citations.
- **No busy-wait on an async path.** On a single-threaded executor it stalls
  every task, the watchdog included, and a bit that never changes hangs the
  system. A bounded one-time handshake during setup is acceptable; an unbounded
  poll inside an `async fn` is not. Endless-pending stubs, panic placeholders and
  timer-polled replacements for supported interrupt-driven hardware are all
  rejected.
- **Observe and account for every relevant error condition according to cited
  read and clear semantics before returning.** Preserve unrelated and control
  bits and leave no recoverable condition latched. Read-to-clear state need not
  and sometimes cannot be snapshotted first: a W1C flag clears on writing one, a
  W0C flag on writing zero, and a read-to-clear flag on the read itself. An
  early return on the first condition leaves the others latched and the
  peripheral wedged.

## Cancellation, drop and reuse

- **A dropped future must not leave hardware running.** Cover every armed
  interval with `OnDrop` before cancellation can abandon it, and `defuse` only on
  the success path.
- Cleanup on cancellation, on error, and on success before defusing, must disarm
  the wait the operation actually owns and leave state reusable by the next
  operation. Apply cancellation to owned resources only; a shared service is not
  transferred to the future that happened to be waiting on it.
- Exercise cancel-before-first-poll, cancel-after-arming, event-versus-drop and
  an immediate new operation on the same resource. A stale waker or a stale
  latched event must not satisfy a later generation or disturb a sibling.
- Use the checkout's actual waker pattern. Introducing a new async engine is not
  the objective.

## Host testing and review limits

- Keep the pure encoding, configuration, arithmetic and event-state logic
  testable where it naturally exists, and test the **production** functions.
  Exhaust small legal domains and the relevant invalid boundaries: ninety-six
  inhabitants is a loop, not a sampling strategy. Save property testing for the
  genuinely large input space, such as arbitrary bytes arriving from hardware.
- Do not build a disconnected hardware model or simulator solely to obtain host
  tests. A model that agrees with the implementation proves only that it agrees
  with the implementation. Where a subsystem has no useful host-testable core,
  say so and record the check `not-applicable` with that reason.
- Work each implemented upstream trait's documentation as a checklist of
  obligations and record which ones were verified and how. Those are exactly the
  requirements a single happy-path example never exercises.
- Review owned-state isolation and the async ordering argument even when a
  hardware loopback passes. Finite hardware stress cannot exhaust the
  interleavings, and host models establish nothing electrical.
- Do not claim behavior you have not observed. Name what ran, what did not, and
  what needs a bench.
