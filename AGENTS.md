# Working on a new Embassy HAL

## Scope of this file

This file governs work on a **new `embassy-<vendor>` HAL crate** destined
for upstream `embassy-rs/embassy`.

If you are reading this inside the **halucinator** repository itself, you
are working on the toolkit — the agents and skills that produce HALs, not
a HAL. See `README.md`. The rules below still describe the domain those
agents operate in, so they remain useful context.

## Prerequisite

Work happens inside a clone of `embassy-rs/embassy`. The new crate lives
at `embassy-<vendor>/`, a sibling of `embassy-mcxa/`, `embassy-stm32/`,
and the rest. Paths in this file are relative to the repository root and
are expected to resolve. If they do not, stop and say so rather than
guessing at the contents.

---

## The two references

Every agent relies on these two sources. Neither is optional.

### 1. `embassy-mcxa/` — the north star

`embassy-mcxa` is the most recently designed HAL in the tree and the
pattern this project replicates. **`embassy-mcxa/DEVGUIDE.md` is the
single most important file to read before writing any HAL code.** It is
the closest thing embassy has to a "how to write a HAL" guide, and it was
written specifically to be generalised to other HALs.

Read it first. Cite it by section when you make a design decision.

Map of what to read for each concern:

| Concern | Read |
|---|---|
| Whole-crate conventions | `embassy-mcxa/DEVGUIDE.md` |
| Manifest, features, docs metadata | `embassy-mcxa/Cargo.toml`, DEVGUIDE §"The `Cargo.toml` file" |
| Codegen, `_generated.rs` | `embassy-mcxa/build.rs`, `embassy-mcxa/build_common.rs` |
| `peripherals!`, `interrupt_mod!`, `init` | `embassy-mcxa/src/lib.rs`, DEVGUIDE §"The top level of the crate" |
| Per-chip divergence | `embassy-mcxa/src/chips/` |
| Clock tree, gating, reset, power | `embassy-mcxa/src/clocks/`, especially `gate.rs` and `periph_helpers.rs` |
| Time driver | `embassy-mcxa/src/ostimer.rs` |
| Peripheral driver anatomy | `embassy-mcxa/src/i2c/` — the reference implementation |
| Interrupt-driven async, cancel safety | `embassy-mcxa/src/i2c/controller.rs`, DEVGUIDE §"Asynchronous (Interrupt-Driven) Drivers" |
| Buffered / DMA / mode variants | `embassy-mcxa/src/lpuart/` |
| Examples | `examples/mcxa2xx/`, `examples/mcxa5xx/` |
| CI, toolchain, formatting | `ci.sh`, `rust-toolchain.toml`, `rustfmt.toml`, `CONTRIBUTING.md` |

`embassy-mcxa` is a north star, not scripture. Where it has a known wart,
DEVGUIDE usually says so. Follow the documented intent over a local
accident.

### 2. "Making Smaller Things" — the design discipline

<https://balbi.sh/posts/making-smaller-things/>

The article is the design philosophy for every type this project
introduces. Fetch it when you need the full argument. Its operative rules,
restated so you do not have to:

- **Functional core, imperative shell.** Pure functions — encode, decode,
  baud-rate maths, descriptor layout — take values and return values. No
  registers, no `async`, no HAL types. The shell touches hardware and has
  almost no branches. In a HAL the shell is the register poke; everything
  that computes *what* to poke belongs in the core and is testable on the
  host.
- **Primitives at the edges, meaning in the middle.** Registers are `u32`.
  A bus carries bytes. Those primitives are parsed **once**, at the
  boundary, into a type that cannot be wrong; everything inside speaks the
  parsed type.
- **Parse, don't validate.** A check that hands back the same loose type
  invites every downstream function to re-check it. A check that hands
  back a *different* type is evidence the check happened. `Config` is not
  a `u32` that was inspected — it is a thing that could not have been
  built from a bad value.
- **Count inhabitants.** `set_config(u8, u8, u8)` is 16,777,216 reachable
  states of which ~96 are legal. Three enums are 96, all legal. Making a
  type smaller does not add safety; it deletes the obligation — the range
  checks, the error variants, the tests for them, and the doc sentence
  that drifts.
- **`encode` is total, `decode` is partial.** Every value you can
  construct is a legal register encoding, so encoding cannot fail.
  Decoding meets reserved bit patterns the silicon can produce, so it
  returns `Result`. That asymmetry is real; do not flatten it.
- **Test by exhaustion where the domain is small.** 96 inhabitants is a
  `for` loop, not a sampling strategy. Save property testing for the
  genuinely large input space — arbitrary bytes arriving from hardware.
- **The failure mode is over-encoding.** Typestate on everything, a
  newtype per loop counter, a sealed trait per axis — that is the wrong
  abstraction with the compiler enforcing it, which makes it *more*
  expensive to undo. The heuristic: encode the invariant a caller could
  plausibly get wrong **at a call site**. Newtype what crosses a boundary.
  Leave the loop counter alone.

This lands on the same ground DEVGUIDE reaches from the other direction.
DEVGUIDE §"Error types" says split one fat `Error` into `CreateError` /
`SendError` / `RecvError` so users never match on an impossible variant —
that is the inhabitant argument applied to error types. DEVGUIDE
§"Configuration" says validate rather than silently mask. Where the two
references agree, the rule is not negotiable.

---

## The pipeline

New-HAL work runs in this order. Each stage has an owning agent.

```
gather-documentation  →  hal-datasheet
        ↓
generate-svd          →  hal-svd
        ↓
generate-pac          →  hal-svd
        ↓
scaffold-hal          →  hal-architect
        ↓
peripheral drivers    →  hal-driver   (one per peripheral, repeated)
        ↓
examples & HIL tests  →  hal-tester   (black-box, per peripheral)
        ↓                 write-examples
        ↓
review                →  hal-reviewer (gates every stage above)
```

`hal-tester` is deliberately blinded: it is given a peripheral's public
API in its prompt and is denied read access to `embassy-*/src/**`. A
tester that has read the driver writes tests that agree with the
driver, including where the driver is wrong. Whoever dispatches it must
therefore supply the API surface in the prompt — it has no other way to
obtain it, and that is the point.

Testing splits by where the test runs:

- **Host-side unit tests of the functional core** — baud divisors,
  encode/decode, timing maths — belong to `hal-driver`. They are how it
  develops, and the small-domain ones should be exhaustive loops rather
  than sampled.
- **Anything that runs on target** — `examples/<chip>/`,
  `tests/<chip>/` teleprobe binaries, and their `ci.sh` wiring —
  belongs to `hal-tester`.

`hal-architect` owns the roadmap and decides when a stage is complete
enough to move on. Stages are not strictly serial — a driver may send you
back to `gather-documentation` for a register the manual described badly —
but the dependency direction never reverses. You cannot write a driver for
a register the PAC does not expose.

`hal-tester` selects `write-examples` for the generic example/HIL workflow and
the applicable peripheral's public validation guidance for specific cases.

### Hardware testing

**hal-tester** owns documented physical setup guidance and hardware execution
for the scope dispatched by **hal-architect**. The user performs physical setup;
the agent runs tests. Target-affecting operations require confirmed readiness
and authorization for the named device and operations. The architect relays
setup-required handoffs when needed; dispatch alone is not authorization.

The tester must follow `write-examples`' hardware-execution and public-record
references for loading, running, retries, teardown, and evidence. Source
blindness and tool approvals remain mandatory, including during debugging.
Other agents keep their existing ownership; driver and shared-startup fixes
return through the architect to their owners. Documentation, generation, and
build-only scaffold checks do not authorize hardware operations. Required
runtime evidence cannot be replaced by a successful build or unavailable setup.

### Artifact storage and handoff

Keep documentation and the complete PAC project under one `halucinator/`
directory in the working repository, normally the Embassy checkout. New work
uses this layout:

```text
halucinator/
  docs/<target-id>/
    SOURCES.md
    sources/
    extracted/
    notes/
  pac/<vendor>/
    data/
      svd/<target-id>/
        sources/
        transforms/
      metadata/
        peripherals/
    generator/
    <vendor>-pac/
    derived/
      svd/<target-id>/<run-id>/
        baseline/
        prepared/
        replay/
      pac/<target-id>/<run-id>/
        candidate/
        replay/
```

`target-id` uses the vendor and exact part naming rule in
`gather-documentation`'s source-list reference. For a new PAC project, normalize
the exact vendor name to lowercase ASCII, replacing runs of non-alphanumeric
characters with `-` and trimming edge hyphens. This is `<vendor>` above; reuse
an applicable recorded PAC identity instead of deriving a second project for
another chip. An empty identifier or a collision between distinct projects
requires an explicit name. A shared vendor name does not prove compatibility.

Documentation originals, extractions, and cited research/review notes belong
under `docs/`. Active SVD inputs, corrections, metadata, generation tooling,
and the consumable crate stay together in the PAC project. Preserve gathered
originals and their source IDs when recording pristine generation-input copies;
do not create independently maintained copies of the same input. Separate
durable `data/` and `generator/` inputs from regenerable crate and `derived/`
outputs. Create directories only when needed, not an empty tree at intake.

For each location, prefer an explicit user-supplied path, then a previously
recorded path for the same target or applicable PAC project, then the default
above. Reuse existing recorded layouts, including legacy documentation,
`halucinator/svd/<target-id>/`, root-level PAC crates, and authorized external
generation projects. Check identity before reuse; a matching folder name is
not proof. Do not silently migrate, move, delete, or overwrite earlier artifacts
to adopt the default. An explicit path override is not a migration request.
Preserve source provenance, originals, and unrelated changes.

Use the defaults without a location interview. Resolve paths and symlinks
from the working repository root before writing; defaults and documentation
must remain inside it. An existing external generation location requires
explicit authorization and a named root, never an assumed sibling checkout.
Ask only about conflicting records, unsafe/inaccessible paths, or missing
target/evidence handoff details, not whether a usable default is acceptable.

`hal-architect` passes the actual selected documentation directory,
`SOURCES.md` path, exact target, relevant source IDs, and cited-note paths
to every downstream agent that needs them. For SVD/PAC work, also pass the
selected PAC project root, SVD input/transform root, and actual derived run
paths; add the generator directory and generated crate path when relevant.
Record stable artifact locations and stage-note links in the source list; keep
exact run paths and evidence in stage notes and handoffs. Consumers share the
selected project, not independently chosen defaults for each stage.
Handoff paths are repository-relative, or relative to an explicitly named
authorized generation root. Consumers use those paths rather than reconstructing
defaults or guessing a previously used target.

Keep hardware citations useful independently of local paths: document
title/number, revision, and section/table/page still belong in findings
and downstream code. Never copy HAL implementation into the documentation
directory to bypass `hal-tester`'s source restrictions. Supply only its
public API and the relevant cited hardware/board facts.

HAL source, examples, and HIL tests stay in their upstream/build-system
locations. Co-locating SVD data with the later PAC does not require creating
a generator, Cargo workspace, or crate during documentation intake or SVD
preparation. Only the owning stage creates its needed files.

### PAC placement

The in-tree PAC does not require a separate or nested Git repository.
Directory nesting does not determine Cargo workspace membership; follow the
live checkout's build structure.

The HAL may use a local Cargo path dependency during bring-up. From the default
`embassy-<vendor>/` location it is `../halucinator/pac/<vendor>/<vendor>-pac`.
This does not establish upstream acceptance or publication readiness, or relax
the fork and generated-code rules below.

### Where the PAC comes from

`embassy-mcxa` depends on `nxp-pac`, which is generated, not hand-written.
That repository is the model for `generate-svd` and `generate-pac`:

- Vendor SVD files are inputs, not deliverables.
- **chiptool** transforms clean them up into something usable.
- The project is moving from per-chip PACs to a **metapac**: shared
  peripheral-IP definitions plus per-chip metadata naming which
  peripherals a given part contains. This is what lets one driver serve
  every chip carrying the same IP block, instead of a copy per part.
  MCXA256 and MCXA577 are metapac parts.
- The generated crate is **never** hand-edited. A missing register is
  fixed in the metadata and regenerated.

---

## Hard rules

These are failure conditions, not preferences.

1. **No invented hardware facts.** Register offsets, bit positions, reset
   values, clock topology, and errata come from the reference manual or
   the PAC. If you do not have the citation, say "I need the manual
   section for X" and stop. A plausible-looking offset is worse than no
   offset, because it compiles.

2. **Cite the source for hardware claims.** Manual section number, table
   number, or the PAC path. "The datasheet says" without a number is not
   a citation.

3. **No `u8`/`u32` in a public signature where an enum fits.** If the
   field has four legal values, the type has four inhabitants. See the
   design discipline above.

4. **Never hand-roll clock gating or reset in a driver.** That policy
   lives in the `clocks` subsystem and is reached through the `Gate` trait
   and `enable_and_reset`. A driver poking `MRCC`/`SPC`/`SCG` directly
   means the policy is now configured in two places that can disagree.
   DEVGUIDE §"Bringing Up Clocks and Resets".

5. **Never vendor a forked PAC.** A `Cargo.toml` pointing a dependency at
   a personal fork must not merge. Fix the PAC upstream and pin the
   released revision. A fork pin is acceptable only as a local, temporary
   aid while the upstream PAC PR is in review.

6. **Never hand-edit generated code.** `_generated.rs` and the PAC crate
   are outputs. Fix the generator or the metadata.

7. **Clear all error flags before returning.** An early return on the
   first error leaves the others latched and the peripheral wedged.
   DEVGUIDE §"Checking Errors".

8. **Register the waker before checking the condition.** Check-then-
   register loses any completion that lands in the window, and the future
   sleeps forever. DEVGUIDE §"Asynchronous (Interrupt-Driven) Drivers".

9. **A dropped future must not leave hardware running.** Guard any armed
   region with `OnDrop` and `defuse` on the success path.

10. **No busy-wait on an async path.** On a single-threaded executor it
    stalls every task, watchdog included, and a bit that never changes
    hangs the system.

11. **Do not claim behaviour you have not observed.** "This should work on
    hardware" is not a result. Name what you ran, what you did not run,
    and what needs a bench.

12. **No wildcard imports.** They cause surprising semver breakage and
    make provenance unreadable.

---

## Working style

- Read before writing. `embassy-mcxa` has already solved most of what you
  are about to solve; the cost of reading `src/i2c/` is far lower than the
  cost of a review cycle that says "look at how i2c does it".
- Prefer patching the PAC over working around it in a driver. A driver
  describes behaviour; it does not re-encode the memory map.
- Keep `cargo fmt` and `clippy` clean. They are CI failures in this
  repository, not preferences. `rustfmt.toml` at the root is authoritative
  and `ci.sh` is what CI runs.
- When implementing a trait defined elsewhere — `embedded-hal`,
  `embedded-hal-async`, `embedded-io`, `embassy-usb-driver` — treat its
  documentation as a checklist of obligations and verify each one.
  Those are precisely the requirements a single happy-path example never
  exercises.
- State what you did not do. An unverified assumption that is named is a
  known risk; an unverified assumption that is silent is a bug waiting for
  someone else.
