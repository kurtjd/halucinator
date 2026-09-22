# Profile: transaction and stream buses

Selected **only on a positive classification** that the dispatched subsystem is
a transaction or stream bus — I2C, SPI, UART, or another peripheral with the
same shape: a controller or endpoint that owns pins and a clock, is constructed
once per instance, moves bytes or frames in operations that can be cancelled,
and reports errors per operation.

For **hal-driver** and read-only **hal-reviewer**. **hal-tester** uses the
separate tester-safe validation guidance, not this implementation-aware profile.

Apply this profile **together with** the universal
[driver checklist](../driver-checklist.md). This profile is the default an agent
reaches for under context pressure; it is wrong for GPIO and wrong for the
global time service, and both of those profiles say so normatively. If the
classification step did not positively establish the bus shape, this file does
not apply.

## Read before you write

This file prescribes obligations and a reading order. It contains **no register
facts**, because `AGENTS.md` HAL-RULE-01 forbids inventing them and no bus
register on the target MCU can be known from here.

Read, in the executing checkout:

- `embassy-mcxa/DEVGUIDE.md`, at minimum the sections "Type Erasure and
  Constructors", "Configuration: Defaults and Validation", "Error types", "Bringing Up Clocks and
  Resets", "Checking Errors", "Implementing Upstream Trait Contracts",
  "Asynchronous (Interrupt-Driven) Drivers" and "Shared Static State and DMA".
- `embassy-mcxa/src/i2c/`, the reference implementation of a bus driver, and
  `embassy-mcxa/src/i2c/controller.rs` for the interrupt-driven async and
  cancel-safety shape.
- `embassy-mcxa/src/lpuart/`, the reference for buffered, DMA and other mode
  variants sharing one public surface.
- The reference manual sections for the target instance: the register layout,
  the field encodings, the baud or clock divisor derivation, the FIFO and
  threshold semantics, the error and status flags with their clear semantics,
  and the interrupt enable and pending semantics. Cite each one.

Record what you actually read. A remembered pattern is not a live reference, and
a missing live reference blocks the affected implementation.

## The instance trio

- A sealed instance trait extending the clock `Gate` and naming the
  per-peripheral clock configuration, carrying an accessor for a `&'static`
  runtime `Info` and any per-instance constants; a public instance trait adding
  the associated interrupt type. One `static INFO` per instance, holding the
  register handle and the wait cell.
- Erase instance and pin generics. The driver struct is parameterized by one
  lifetime and one mode, not by a generic per pin and per instance. Instance and
  pin generics appear only on the constructor, where they do the type-checking
  work, and are erased immediately afterwards. Generics are a cost paid by every
  user.
- The mode is a sealed marker type, not a runtime field. An `enum Mode` field is
  a runtime answer to a compile-time question. Where a blocking, an async and a
  DMA variant differ only in how bytes move, share the public methods over a
  sealed async-capable bound and dispatch the difference through a small private
  trait.
- One constructor per mode, all funnelling into one private inner constructor
  that performs the mode-independent bring-up. A DMA mode owns its channels for
  the driver's lifetime.

## Clock bring-up and configuration

- Make exactly the lifecycle calls the target contract requires for the
  instance. Retain a returned frequency for the baud and timing arithmetic, and
  retain wake or lifetime ownership, only when the contract requires it. Never poke a clock or
  reset register from the bus module.
- The baud or clock divisor derivation is functional core: a pure function from
  the source frequency and the requested rate to an encoded divisor and the
  achieved rate, with no registers in it. Test it on the host, exhaustively over
  the small legal domains, and prove the rounding and the achieved-rate error
  against the cited rate and resolution rather than asserting them.
- `Default` is the hardware-nominal reset configuration. Reject an
  unrepresentable rate, word length, parity or threshold with a construction
  error rather than masking it to the nearest legal value.

## Transactions, errors and cancellation

- Split the error taxonomy by operation — construction, send, receive — mark
  each `#[non_exhaustive]`, and define no module `Result` alias. A user matching
  on a variant the operation cannot produce is a defect in the type, not in the
  user.
- **Observe and account for every relevant error condition according to cited
  read and clear semantics before returning.** Preserve unrelated and control
  bits and leave no recoverable condition latched. Read-to-clear state need not
  and sometimes cannot be snapshotted first: W1C, W0C and read-to-clear
  registers each clear differently. Returning on the first condition leaves the
  others latched and wedges the peripheral for the next transaction.
- The handler masks the enable bits it owns and wakes. It does **not** advance
  the transfer. The future re-arms the source inside its wait predicate and
  re-checks the real condition. Where one interrupt backs several waiters, a
  global event wakes all of them.
- Guard every armed region with `OnDrop`, and `defuse` only on the success path.
  For a DMA mode the guard also disables the peripheral's DMA request and
  quiesces the channel, so that a cancelled transfer leaves no engine writing
  into a buffer the future no longer owns.
- Reset the module-global mutable state — descriptor rings, flags, waker tables —
  at the top of construction. The ownership token proves you own the live
  peripheral; it does not prove this is the first construction.
- Around DMA, place the memory barriers where the reference implementation does,
  and treat cache coherency as a separate, unhandled concern: if the design
  relies on non-cacheable SRAM, make that explicit in a linker section or an
  assertion, not in a comment.

## Upstream traits

Implement the actual versions of the applicable `embedded-hal`,
`embedded-hal-async` and `embedded-io` traits. Work each trait's documentation
as a checklist of obligations and record which ones were verified and how: the
zero-length operation, the partial transfer, the flush-versus-idle distinction,
the error mapping, and the cancellation semantics are exactly the requirements a
single happy-path example never exercises.

## Review focus

Review the ordering argument and the cancellation paths, not the successful
transfer. Check that the mode variants share one public surface without one of
them silently degrading, that the error clear covers every flag the manual
defines, and that the divisor arithmetic was tested against cited rates rather
than against itself. Use `write-driver`'s completion gates and the
[driver record](../driver-record.md) rules instead of duplicating them here.
