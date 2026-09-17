# Time Driver Implementation Checklist

For **hal-driver** and read-only **hal-reviewer**. **hal-tester** uses the
separate public validation reference, not this private implementation guidance.
TIME IDs refer to that matrix; keep expected public behavior defined there.

Read the live MCXA time driver and DEVGUIDE sections relevant to "The top level
of the crate", "Bringing Up Clocks and Resets", "Implementing Upstream Trait
Contracts", "Asynchronous (Interrupt-Driven) Drivers", and "Shared Static State
and DMA". Cite actual sections/files from the executing checkout and follow
documented intent over a local wart. Transfer the design discipline, not MCXA
counter encodings, clocks, registers, or interrupt assumptions.

## Global integration and lifecycle

Addresses **TIME-01, TIME-02, TIME-11, TIME-13**.

- Register the service through the versioned driver mechanism identified in
  the public reference's "Contract sources" section. Check feature-dependent
  registration and resource availability against TIME-01.
- Depend on the driver interface and suitable queue utilities for the service;
  use high-level `embassy-time` in consumers/tests rather than introducing an
  unnecessary dependency on it for the backend.
- Reserve every counter, compare channel, IRQ route, and other resource the
  service needs. A logical global clock may use more than one hardware resource;
  ownership must prevent conflicting user drivers. Coordinate singleton/feature
  availability and init ordering with the architect instead of taking an
  untracked second register handle.
- Apply `Gate`/`enable_and_reset` and power/frequency policy through the central
  clocks layer at the owning initialization boundary. Retain any necessary
  lifetime guards with the service, not a user's `Timer` future. Do not reset
  shared hardware or discard another client's state on repeated scheduling.
- Satisfy the actual thread-safety/context contract (`Send + Sync + 'static` in
  the current trait) with appropriate synchronization. A local interrupt mask
  is not automatically multicore exclusion. Avoid forcing `Instance`/`Mode`,
  per-transfer constructors, or a newtype for every internal count onto a
  shared service; use meaningful types at real boundaries under `AGENTS.md`.
- Establish a fault-free pre-init timestamp path and publication of initialized
  state. A contract-permitted initial value must remain monotonic across init;
  it is not permission for a permanent zero-time stub after initialization.
  Do not read a clock-gated/inaccessible register to find out whether it is safe.
- Dropping a timer future does not transfer ownership of the global clock or
  alarm to that future. Apply cancellation rules to resources the operation
  actually owns; do not attach a stop-all `OnDrop` or reset to each timer.
  Follow the selected Timer/queue contract for stale wakes and cancellation.
- Keep the chosen timebase valid through declared executor-idle/power modes.
  If clock switching or sleep would stop/change it, either implement the already
  agreed continuity contract or make that unsupported mode unavailable through
  the owning policy. Do not silently freeze time or add out-of-scope power APIs.

## Timestamp and tick arithmetic

Addresses **TIME-02 through TIME-05, TIME-07, TIME-08**.

- Agree on the hardware clock, divisor, exported tick rate, and `TICK_HZ`
  feature selection. Fixed or finite rates must not let a consumer silently
  select a different unit. Prove any conversion and rounding against actual
  rate/resolution and avoid silent truncation or intermediate overflow.
- Read the documented counter representation correctly, including split,
  latched, asynchronously updated, down-counting, or encoded counters where
  applicable. Establish a consistent timestamp across task/ISR reads; do not
  infer atomicity or read order from register width alone.
- Extend a short hardware counter as needed to meet the driver's long-range
  monotonic contract. Analyze overflow detection and epoch updates with a read
  straddling rollover, a pending overflow, and delayed interrupt service. One
  pending flag may not count multiple missed wraps. Prove the service interval
  assumptions for supported operation instead of assuming timely interrupts.
- Keep timestamp extension and compare/deadline arithmetic correct at carry,
  maximum value, and conversion boundaries. Handle queue sentinel/empty values
  according to the actual utility contract; do not accidentally treat a sentinel
  as a reachable compare or wrap a distant timestamp into an immediate alarm.
- Test the actual pure arithmetic at boundary values and exhaust finite small
  configuration domains. Reduced domains must exercise the production logic,
  not a separate simulation that merely agrees with the implementation. Label
  host evidence separately from observed hardware rollover and clock accuracy.

## Queue, alarms, and interrupt ordering

Addresses **TIME-06 through TIME-12, TIME-14**.

- Reuse a suitable `embassy-time-queue-utils` backend and follow its versioned
  contract, executor/waker compatibility, capacity behavior, and expiration
  semantics. Do not invent a scheduler, hardcode a queue capacity from one
  chip, or enqueue one integrated queue item in multiple queues concurrently.
- For the current `Queue` interface, a changed `schedule_wake` result requires
  finding the next expiration and arranging its alarm; `next_expiration(now)`
  processes expired entries. Check the exact chosen version rather than
  treating these names as a complete target implementation.
- Coordinate queue updates, timestamp reads, and compare/IRQ programming.
  Handle an earlier new deadline, a deadline already due, or one that passes
  while the compare is being armed. Recheck the condition after arming and
  arrange progress without losing that event or sleeping until a full wrap.
- Respect the documented compare horizon and minimum programming lead time.
  Use the established approach to long deadlines rather than truncating the
  epoch. Clearing stale flags must not clear a newly arrived event; acknowledge
  only owned sources according to the PAC/manual semantics.
- A time ISR may process expirations and rearm the next alarm; do not blindly
  impose the bus-driver rule that an ISR only masks and wakes one transfer.
  Analyze locking and waker side effects, including possible reentrancy, and
  preserve ordering between task and interrupt scheduling paths.
- Wake notifications are hints. Multiple timer futures may share a task/waker;
  queue coalescing, early wakes, or a canceled timer's stale wake must not cause
  incorrect future completion or strand the other timers under the public
  contracts in TIME-09 through TIME-12.
- Distinguish processing already-due work from busy-waiting for counter progress.
  Scheduling/interrupt paths must make progress without polling until the next
  deadline, unbounded retry on an unarmable compare, or starving other work.
  Any documented setup handshake must obey the existing bounded-setup rules.

## Review focus

Check the whole selected resource lifecycle and the queue/IRQ ordering argument,
not only successful delay examples. Cross-check clock facts, wake deadlines,
timing-reference tolerances, and actual feature/link evidence. Public consumers
and host arithmetic do not replace an unreviewed hardware read or ordering path.
Use the skill's completion gates and record rules instead of duplicating those
checklists here.
