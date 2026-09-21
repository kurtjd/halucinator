# Working on a new Embassy HAL

## Scope of this file

This file governs work on a **new `embassy-<vendor>` HAL crate** destined
for upstream `embassy-rs/embassy`.

## Start here

HAL-workflow agents must apply the [checkout context guard](#checkout-context-guard)
before following the rest of this file. Then use this map to go directly to
the material needed for the task:

| Need | Go to |
|---|---|
| Find the next workflow stage and its owner | [The pipeline](#the-pipeline) |
| Store or hand off documentation and PAC artifacts | [Artifact storage and handoff](#artifact-storage-and-handoff) |
| Check a non-negotiable constraint | [Hard rules](#hard-rules) |
| Choose the relevant north-star implementation | [`embassy-mcxa` concern map](#1-embassy-mcxa--the-north-star) |
| Apply the project's type-design discipline | [Making Smaller Things](#2-making-smaller-things--the-design-discipline) |

## Checkout context guard

This guard binds the eight `hal-*` HAL-workflow agents: each of them must
classify the checkout **read-only** before anything else, and must not write,
lock or dispatch while classifying.

A non-HAL agent — a maintenance agent working outside the HAL workflow, dispatched
to the halucinator toolkit itself — is not bound by this guard and proceeds
normally.

That exclusion is settled by agent identity alone and never by an agent's own
judgement of its task. A `hal-*` agent is bound here whatever it believes its
current work to be; it may not relabel itself a maintenance agent to escape the
refusal, and the refusal it owes stays terminal.

Use the following marker predicates when inspecting a directory. Every named
path is relative to the directory being inspected.

- The TOOLKIT predicate is true when `README.md`, `docs/opencode.json`,
  `.opencode/ownership.toml` and `tools/selfcheck.py` all exist and `README.md`
  contains the sentence `No HAL source lives here`.
- The EMBASSY predicate is true when the `embassy-mcxa` crate contains
  `DEVGUIDE.md`.
- A predicate is false when at least one required path is observed missing, or,
  for the TOOLKIT predicate, when `README.md` is readable and does not contain
  the required sentence.
- A predicate is indeterminate when it is not false and at least one observation
  needed to decide it fails because a path is inaccessible or unreadable.

Classify as follows:

- **TOOLKIT** when the selected directory satisfies the TOOLKIT predicate.
  TOOLKIT wins even if Embassy markers also appear: it takes precedence over
  EMBASSY, because a toolkit checkout can legitimately vendor Embassy-looking
  files while containing no HAL to work on.
- **EMBASSY** only when every TOOLKIT predicate that must be considered is false
  and the selected directory satisfies the EMBASSY predicate.
- **AMBIGUOUS** otherwise, including when no classification root can be resolved,
  a TOOLKIT predicate that must be excluded is indeterminate, or the selected
  directory's EMBASSY predicate is indeterminate.

Resolve and classify the root using this bounded, read-only procedure:

1. From the invocation directory, attempt `git rev-parse --show-toplevel`
   exactly once. Do not install Git, retry with another Git command, search for
   a `.git` directory, or modify the checkout.
2. Treat Git's result as usable only when it is one non-empty path naming an
   accessible directory that is either the invocation directory or one of its
   ancestors. Otherwise treat the result as failed or malformed and use step 5.
3. For a usable Git result, inspect each directory on the finite path beginning
   at the invocation directory and ending at the Git-reported root, inclusive,
   exactly once for the TOOLKIT predicate.
   - If one or more inspected directories satisfy the TOOLKIT predicate, select
     the nearest such directory to the invocation directory as the resolved
     root and classify TOOLKIT. This is the nested-toolkit veto; do not admit
     the Git-reported root as EMBASSY.
   - If none satisfies the TOOLKIT predicate but any inspected TOOLKIT predicate
     is indeterminate, retain the Git-reported directory as the resolved root
     and classify AMBIGUOUS.
   - Otherwise select the Git-reported directory as the resolved root. Classify
     EMBASSY if its EMBASSY predicate is true, and AMBIGUOUS if that predicate
     is false or indeterminate.
4. A classification produced by step 3 is final. Do not inspect parents above
   the Git-reported root.
5. If Git is unavailable, the command fails, its output is empty or malformed,
   or the reported directory cannot be inspected, inspect the invocation
   directory and each of its parents exactly once, stopping at the filesystem
   root. This is the bounded parent fallback for non-Git exports as well as Git
   and permission failures.
6. During bounded parent fallback:
   - If one or more inspected directories satisfy the TOOLKIT predicate, select
     the nearest such directory to the invocation directory as the resolved
     root and classify TOOLKIT.
   - Otherwise, if any inspected TOOLKIT predicate is indeterminate, leave the
     root unresolved and classify AMBIGUOUS; an Embassy marker cannot override
     a toolkit identity that could not be excluded.
   - Otherwise, if one or more inspected directories satisfy the EMBASSY
     predicate, select the nearest such directory to the invocation directory
     as the resolved root and classify EMBASSY.
   - Otherwise leave the root unresolved and classify AMBIGUOUS.
7. A missing path is an observed absence. An inaccessible or unreadable path is
   an inspection failure, not an absence. Never guess either result. Record
   every inspection failure in the refusal diagnostics.

On TOOLKIT or AMBIGUOUS, respond exactly:

HAL workflow not started: run toolkit maintenance with a non-HAL agent, or
install halucinator into an Embassy checkout.

Immediately after that sentence, report the classification, root-resolution
result, and marker observations in this form. Repeat the marker-observation
block for every directory inspected; do not report only directories that
satisfied a predicate.

```text
Classification: <TOOLKIT|AMBIGUOUS>
Invocation directory: <absolute path>
Resolved root: <absolute path|unresolved>
Root resolution: <git|bounded parent fallback>
Resolution detail: <success, nested-toolkit veto, or concise Git or path failure>

Marker observations:
Directory: <absolute inspected directory>
- README.md: <present|missing|inspection failed: reason>
- README.md contains `No HAL source lives here`: <yes|no|not inspectable>
- docs/opencode.json: <present|missing|inspection failed: reason>
- .opencode/ownership.toml: <present|missing|inspection failed: reason>
- tools/selfcheck.py: <present|missing|inspection failed: reason>
- EMBASSY marker (`DEVGUIDE.md` in the `embassy-mcxa` crate):
  <present|missing|inspection failed: reason>

Recovery:
- TOOLKIT: run toolkit maintenance with a non-HAL agent, or start the HAL
  workflow from an Embassy clone.
- AMBIGUOUS: resolve every reported inspection failure. If the checkout is
  sparse or incomplete, use a complete Embassy clone containing the
  `embassy-mcxa` crate's `DEVGUIDE.md`. If halucinator is already installed
  globally, start a new HAL-agent invocation from that Embassy clone; do not
  reinstall it merely to change the invocation directory.
- AMBIGUOUS with a usable Git root and no inspection failure: a complete
  Embassy export that is not itself a Git worktree and sits inside an unrelated
  Git worktree is not a supported layout. Move it outside that worktree, or
  give it its own Git boundary, then start a new HAL-agent invocation there.
```

Then return immediately and list the observed markers. No retry, no lock, no
state publication, no write, no subdispatch. A clear refusal is better than a
loop against paths that do not exist. This classification is conservative
evidence about the checkout, not proof of identity, and nothing mechanical
proves an agent performed it.

Minimum context: the HAL workflow needs an `embassy-rs/embassy` clone. The new
crate lives in the `embassy-<vendor>` directory, alongside the `embassy-mcxa`
and `embassy-stm32` crates and the rest. In a toolkit checkout those expected
HAL paths do not resolve, and that is the point of the guard above:
`README.md`, `docs/opencode.json`, `.opencode/ownership.toml` and
`tools/selfcheck.py` identify the halucinator toolkit when `README.md` also says
`No HAL source lives here`. A sparse checkout that omits the `embassy-mcxa`
crate's `DEVGUIDE.md` is operationally incomplete and must classify AMBIGUOUS.
The ownership registry may come from either a checkout-local or a global
OpenCode installation; it is an installation prerequisite, not an Embassy
checkout identity marker.

## The two references

Every agent relies on these two sources. Neither is optional.

### 1. `embassy-mcxa/` — the north star

`embassy-mcxa` is the designated north-star HAL for this toolkit, and the
whole crate is the pattern this project replicates. Use the concern
map below as the entry point: read `embassy-mcxa/DEVGUIDE.md` first, then follow
the row for the work at hand. **`embassy-mcxa/DEVGUIDE.md` is the single most
important file to read before writing any HAL code.** It is the closest thing
embassy has to a "how to write a HAL" guide, and it was written specifically
to be generalised to other HALs.

Cite it by section when you make a design decision.

Map of what to read for each concern:

| Concern | Read |
|---|---|
| Whole-crate conventions | `embassy-mcxa/DEVGUIDE.md` |
| Manifest, features, docs metadata | `embassy-mcxa/Cargo.toml`, DEVGUIDE §"The `Cargo.toml` file" |
| Codegen, `_generated.rs` | `embassy-mcxa/build.rs`, `embassy-mcxa/build_common.rs` |
| `peripherals!`, `interrupt_mod!`, `init` | `embassy-mcxa/src/lib.rs`, DEVGUIDE §"The top level of the crate - `lib.rs`" |
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
§"Configuration: Defaults and Validation" says validate rather than silently
mask. Where the two references agree, the rule is not negotiable.

---

## The pipeline

New-HAL work runs in this order. Each stage has an owning agent.
`hal-coordinator` is the hub: it establishes the target and scope, dispatches
every stage below, and applies the admission and acceptance gates. Specialists
never dispatch peers; work that belongs to another agent returns to
`hal-coordinator`.

```
gather-documentation  →  hal-datasheet
        ↓
extract-hardware-facts → hal-datasheet
        ↓
generate-svd          →  hal-svd
        ↓
generate-pac          →  hal-svd
        ↓
scaffold-hal          →  hal-architect  (design specification)
                         hal-driver     (clocks and startup semantics)
                         hal-integrator (shared files, manifests, wiring)
        ↓
peripheral drivers
  write-driver        →  hal-driver   (one per peripheral, repeated)
  write-dma           →  hal-driver   (shared DMA subsystem)
        ↓
examples & HIL tests
  write-examples      →  hal-tester   (black-box logic and evidence)
                         hal-integrator (placement, manifests, CI)
        ↓
review                →  hal-reviewer (typed verdict on a frozen candidate)
```

`hal-integrator` is the sole writer of shared and crate-level files —
manifests, `build.rs`, `src/lib.rs`, `src/chips/**`, linker
scripts, `examples/`, `tests/`, `ci.sh` and the durable records — and the sole
committer. Clocks are not a shared file in that sense: `embassy-*/src/clocks/**`
stays with `hal-driver`, which implements it against the contract
`hal-architect` specified.

`hal-tester` is deliberately blinded: it is given a peripheral's public
API in its prompt and is denied read access to `embassy-*/src/**`. A
tester that has read the driver writes tests that agree with the
driver, including where the driver is wrong. `hal-coordinator` must
therefore supply the API surface in the prompt — the tester has no other way
to obtain it, and that is the point. Perfect blindness is impossible:
`bash` is gated at `ask`, `grep` is matched against the query rather than the
path, and compiler, macro and build-script diagnostics quote source. This is a
strong default and a statement of intent, not a sandbox.

Testing splits by where the test runs:

- **Host-side unit tests of the functional core** — baud divisors,
  encode/decode, timing maths — belong to `hal-driver`. They are how it
  develops, and the small-domain ones should be exhaustive loops rather
  than sampled.
- **Anything that runs on target** — `examples/<chip>/`,
  `tests/<chip>/` teleprobe binaries, and their `ci.sh` wiring —
  runs for `hal-tester`. The tester owns the *test logic and the
  evidence*; `hal-integrator` owns *where the files land*, their manifests,
  and the CI wiring. The tester writes its revision under
  `halucinator/test-candidates/<name>/` and never a canonical path.

`hal-coordinator` owns the roadmap at
`halucinator/docs/<target-id>/notes/ROADMAP.md` and decides when a stage is
complete enough to move on. Stages are not strictly serial — a driver may send
you back to `gather-documentation` for a register the manual described badly —
but the dependency direction never reverses. You cannot write a driver for
a register the PAC does not expose.

`hal-tester` selects `write-examples` for the generic example/HIL workflow and
the applicable peripheral's public validation guidance for specific cases.

### Hardware testing

**hal-tester** owns documented physical setup guidance and hardware execution
for the scope dispatched by **hal-coordinator**. The user performs physical
setup; the agent runs tests. Target-affecting operations require confirmed
readiness and authorization for the named device and operations. The
coordinator relays setup-required handoffs when needed; dispatch alone is not
authorization.

The tester must follow `write-examples`' hardware-execution and public-record
references for loading, running, retries, teardown, and evidence. Source
blindness and tool approvals remain mandatory, including during debugging.
Other agents keep their existing ownership; driver and shared-startup fixes
return through the coordinator to their owners. Documentation, generation, and
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

`hal-coordinator` passes the actual selected documentation directory,
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

These are failure conditions, not preferences. The `HAL-RULE-01` through `HAL-RULE-12` identifiers are stable and may be cited by skills, handoffs, and review findings.

1. **[HAL-RULE-01] No invented hardware facts.** Register offsets, bit positions, reset
   values, clock topology, and errata come from the reference manual or
   the PAC. If you do not have the citation, say "I need the manual
   section for X" and stop. A plausible-looking offset is worse than no
   offset, because it compiles.

2. **[HAL-RULE-02] Cite the source for hardware claims.** Manual section number, table
   number, or the PAC path. "The datasheet says" without a number is not
   a citation.

3. **[HAL-RULE-03] No `u8`/`u32` in a public signature where an enum fits.** If the
   field has four legal values, the type has four inhabitants. See the
   design discipline above.

4. **[HAL-RULE-04] Never duplicate clock, reset, or power policy in a peripheral
   driver.** One architected owning layer records, per resource, policy
   owners, acquisition/initialization, reset arbitration, lifetime accounting
   or its explicit absence, teardown/quiescence, frequency source or
   irrelevance, and cancellation behavior. Peripheral modules use that
   contract. A driver that configures the same resource itself means the
   policy is now configured in two places that can disagree. `Gate` and
   `enable_and_reset` are MCXA examples, not required names or shapes: a
   target may have shared reset domains, reference-counted gates, immutable
   always-on clocks, split clock and reset controllers, or no lifetime power
   vote at all, and must state its actual form.
   DEVGUIDE §"Bringing Up Clocks and Resets".

5. **[HAL-RULE-05] Never vendor a forked PAC.** A `Cargo.toml` pointing a dependency at
   a personal fork must not merge. Fix the PAC upstream and pin the accepted
   upstream commit by immutable revision. A fork pin is acceptable only as a
   local, temporary aid while the upstream PAC PR is in review.

6. **[HAL-RULE-06] Never hand-edit generated code.** `_generated.rs` and the PAC crate
   are outputs. Fix the generator or the metadata.

7. **[HAL-RULE-07] Observe and account for every relevant error condition according to cited
   read and clear semantics before returning.** Preserve unrelated and control
   bits and leave no recoverable condition latched. Read-to-clear state need
   not and sometimes cannot be snapshotted first: a W1C flag is cleared by
   writing one to it, a W0C flag by writing zero, and a read-to-clear flag by
   the read itself.
   An early return on the first error leaves the others latched and the
   peripheral wedged.
   DEVGUIDE §"Checking Errors".

8. **[HAL-RULE-08] Register the waker before checking the condition.** Check-then-
   register loses any completion that lands in the window, and the future
   sleeps forever. DEVGUIDE §"Asynchronous (Interrupt-Driven) Drivers".

9. **[HAL-RULE-09] A dropped future must not leave hardware running.** Guard any armed
   region with `OnDrop` and `defuse` on the success path.

10. **[HAL-RULE-10] No busy-wait on an async path.** On a single-threaded executor it
    stalls every task, watchdog included, and a bit that never changes
    hangs the system.

11. **[HAL-RULE-11] Do not claim behaviour you have not observed.** "This should work on
    hardware" is not a result. Name what you ran, what you did not run,
    and what needs a bench.

12. **[HAL-RULE-12] No wildcard imports.** They cause surprising semver breakage and
    make provenance unreadable.

---

## Working style

- Read before writing. Start with the `embassy-mcxa` concern map above and read
  the part of the north-star crate that matches the work; `src/i2c/` is the
  reference implementation for peripheral driver anatomy, not the fallback
  for every concern.
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
