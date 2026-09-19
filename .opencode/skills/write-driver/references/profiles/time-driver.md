# Profile: Embassy time driver

Selected when the dispatched subsystem is **the** single global Embassy time
service: monotonic timestamps, tick rate, timer or RTC resource reservation,
counter rollover, and queued alarm scheduling.

For **hal-driver** and read-only **hal-reviewer**. **hal-tester** uses the
separate tester-safe validation guidance, not this implementation-aware profile.
Requirement IDs come from that public specification; keep the expected public
behavior defined there.

Apply this profile **together with** the universal
[driver checklist](../driver-checklist.md). What follows is time-service
specific. Transfer the design discipline, never another target's counter
encodings, clocks, registers or interrupt assumptions.

## A shared service is not a bus

**Normative.** Satisfy the actual thread-safety and context contract —
`Send + Sync + 'static` in the current trait — with appropriate synchronization.
A local interrupt mask is not automatically multicore exclusion. **Avoid forcing
`Instance` or `Mode`, per-transfer constructors, or a newtype for every internal
count onto a shared service**; use meaningful types at real boundaries under
`AGENTS.md`. There is exactly one global clock for the whole program: it has no
per-user instance, no transfer mode, and no constructor that a timer future
calls.

## Global integration and lifecycle

- Register the service through the versioned driver mechanism identified in the
  public reference's contract-sources section. Check feature-dependent
  registration and resource availability against the applicable requirement.
- Depend on the driver interface and suitable queue utilities for the service;
  use the high-level time API in consumers and tests rather than introducing an
  unnecessary dependency on it for the backend.
- Reserve every counter, compare channel, interrupt route and other resource the
  service needs. A logical global clock may use more than one hardware resource;
  ownership must prevent conflicting user drivers. Coordinate singleton and
  feature availability and initialization ordering through **hal-coordinator**
  instead of taking an untracked second register handle.
- Apply `Gate` and `enable_and_reset` and the power and frequency policy through
  the central `clocks` layer at the owning initialization boundary. Retain any
  necessary lifetime guard with the service, not with a user's timer future. Do
  not reset shared hardware or discard another client's state on repeated
  scheduling.
- Establish a fault-free pre-initialization timestamp path and a defined
  publication of initialized state. A contract-permitted initial value must
  remain monotonic across initialization; it is not permission for a permanent
  zero-time stub afterwards. Do not read a clock-gated or inaccessible register
  to find out whether it is safe to read.
- Dropping a timer future does not transfer ownership of the global clock or of
  an alarm to that future. Apply cancellation rules to the resources the
  operation actually owns; do not attach a stop-all `OnDrop` or a reset to each
  timer. Follow the selected timer and queue contract for stale wakes and
  cancellation.
- Keep the chosen timebase valid through the declared executor-idle and power
  modes. If clock switching or sleep would stop or change it, either implement
  the already agreed continuity contract or make that mode unavailable through
  the owning policy. Do not silently freeze time and do not add out-of-scope
  power APIs.

## Timestamp and tick arithmetic

- Agree on the hardware clock, the divisor, the exported tick rate and the
  `TICK_HZ` feature selection. Fixed or finite rates must not let a consumer
  silently select a different unit. Prove every conversion and rounding against
  the actual rate and resolution, and avoid silent truncation or intermediate
  overflow.
- Read the documented counter representation correctly, including split,
  latched, asynchronously updated, down-counting or encoded counters where
  applicable. Establish a consistent timestamp across task and handler reads; do
  not infer atomicity or read order from register width alone.
- Extend a short hardware counter as needed to meet the long-range monotonic
  contract. Analyze overflow detection and epoch updates against a read
  straddling rollover, a pending overflow, and delayed interrupt service. One
  pending flag may not count multiple missed wraps. Prove the service-interval
  assumptions for supported operation instead of assuming timely interrupts.
- Keep timestamp extension and compare or deadline arithmetic correct at carry,
  at the maximum value, and at conversion boundaries. Handle queue sentinel and
  empty values according to the actual utility contract; do not treat a sentinel
  as a reachable compare or wrap a distant timestamp into an immediate alarm.
- Test the actual pure arithmetic at boundary values and exhaust the finite
  small configuration domains. A reduced domain must exercise the **production**
  logic, not a separate simulation that merely agrees with the implementation.
  Label host evidence separately from observed hardware rollover and clock
  accuracy.

## Queue, alarms, and interrupt ordering

- Reuse a suitable `embassy-time-queue-utils` backend and follow its versioned
  contract, executor and waker compatibility, capacity behavior and expiration
  semantics. Do not invent a scheduler, hardcode a queue capacity from one chip,
  or enqueue one integrated queue item in two queues concurrently.
- For the current `Queue` interface, a changed `schedule_wake` result requires
  finding the next expiration and arranging its alarm, and `next_expiration(now)`
  processes expired entries. Check the exact chosen version rather than treating
  these names as a complete target implementation.
- Coordinate queue updates, timestamp reads and compare or interrupt
  programming. Handle an earlier new deadline, a deadline already due, and one
  that passes while the compare is being armed. Recheck the condition after
  arming and arrange progress without losing that event or sleeping until a full
  wrap.
- Respect the documented compare horizon and the minimum programming lead time.
  Use the established approach to long deadlines rather than truncating the
  epoch. Clearing stale flags must not clear a newly arrived event; acknowledge
  only owned sources according to the PAC and manual semantics.
- **Normative exception.** A time handler **may** process expirations and rearm
  the next alarm; **do not blindly impose the bus rule that a handler only masks
  and wakes one transfer.** Analyze locking and waker side effects, including
  possible reentrancy, and preserve ordering between the task and interrupt
  scheduling paths.
- Wake notifications are hints. Several timer futures may share a task and a
  waker; queue coalescing, an early wake, or a canceled timer's stale wake must
  not cause an incorrect future completion or strand the other timers under the
  public contracts.
- Distinguish processing already-due work from busy-waiting for counter
  progress. The scheduling and interrupt paths must make progress without
  polling until the next deadline, without unbounded retry on an unarmable
  compare, and without starving other work. Any documented setup handshake obeys
  the existing bounded-setup rules.

## Review focus

Check the whole selected resource lifecycle and the queue and interrupt ordering
argument, not only a successful delay example. Cross-check the clock facts, the
wake deadlines, the timing-reference tolerances, and the actual feature and link
evidence. Public consumers and host arithmetic do not replace an unreviewed
hardware read or ordering path. Use `write-driver`'s completion gates and the
[driver record](../driver-record.md) rules instead of duplicating them here.
