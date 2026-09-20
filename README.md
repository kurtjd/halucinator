# halucinator

An opencode toolkit for designing and implementing a new
[embassy](https://github.com/embassy-rs/embassy) HAL.

It ships an `AGENTS.md` and a set of specialist agents that encode how
`embassy-mcxa` was built, so a new `embassy-<vendor>` crate arrives at
review looking like it belongs in the tree.

No HAL source lives here. This repository is the toolkit.

## Status

| Component | State |
|---|---|
| `AGENTS.md` | written |
| Agents | 8 written |
| Ownership registry | `.opencode/ownership.toml`, 45 file classes |
| Example root config | `docs/opencode.json`, `default_agent: hal-coordinator` |
| Skills | 6 written |

[gather-documentation](.opencode/skills/gather-documentation/SKILL.md),
[generate-svd](.opencode/skills/generate-svd/SKILL.md),
[generate-pac](.opencode/skills/generate-pac/SKILL.md),
[scaffold-hal](.opencode/skills/scaffold-hal/SKILL.md),
[write-driver](.opencode/skills/write-driver/SKILL.md), and
[write-examples](.opencode/skills/write-examples/SKILL.md) are implemented.
Three of the eight agents — `hal-coordinator`, `hal-integrator` and
`hal-reviewer` — have no dedicated skill at all, and `hal-architect` has no
design-only skill of its own; all four run on their agent contract, plus
whatever domain skill the dispatched task names.

## Prerequisite

halucinator assumes you are working **inside a clone of
`embassy-rs/embassy`**, with your new crate at `embassy-<vendor>/`
alongside `embassy-mcxa/`.

This is deliberate. Rather than embedding snapshots of embassy
patterns that go stale, the agents cite live paths —
`embassy-mcxa/DEVGUIDE.md`, `embassy-mcxa/src/i2c/controller.rs`,
`embassy-mcxa/src/clocks/gate.rs`. Outside an embassy checkout those
citations do not resolve and the agents are largely useless.

## Working artifacts

Documentation and the complete PAC project share one `halucinator/` parent in
the working repository, normally the Embassy checkout:

- `halucinator/docs/<target-id>/`: source list, collected originals,
  extracted text, and cited research, roadmap, review, and bench notes. The
  roadmap has one exact path: `halucinator/docs/<target-id>/notes/ROADMAP.md`.
- `halucinator/pac/<vendor>/`: SVDs, transforms, metadata, generator, and the
  consumable `<vendor>-pac/` crate, with separate derived runs.
- `halucinator/candidates/driver-*/` and `halucinator/candidates/integration-*/`:
  scratch implementation and full-crate candidates, worked on before anything
  canonical is touched.
- `halucinator/test-candidates/<name>/`: the tester's black-box test revisions —
  source, manifests, and raw run evidence. These are **committed**, not hidden
  scratch: a gitignored directory is neither reviewable nor durable across
  clones. The schema ratifies this layout in
  [`.opencode/schema/layout.md`](.opencode/schema/layout.md).

See [artifact storage and handoff](AGENTS.md#artifact-storage-and-handoff)
for defaults, overrides, and preserving existing locations, and
[PAC placement](AGENTS.md#pac-placement) for local dependency setup. HAL source,
examples, and HIL tests retain their upstream/build-system layouts.

## Install

Three things move, and they move differently.

**`AGENTS.md`** — copy to the root of your embassy checkout, or merge
into the one already there.

**Agents, skills and the ownership registry**: copy or symlink the whole
`.opencode/` directory, including `.opencode/ownership.toml` and the skills'
bundled references. Merge into an existing `.opencode/` directory, preserving
unrelated files and configuration.

**`opencode.json`** — the root config that sets `default_agent` to
`hal-coordinator`. Without it a user who follows the install lands on the
built-in `build` agent and bypasses the whole topology. Merge it into an
existing root config rather than overwriting one. Inside this toolkit
checkout `docs/opencode.json` is **inert product material**: it is shipped
to a user's Embassy clone and is not the configuration this repository runs
under. A config that looks live here is exactly the confusion the checkout
context guard exists to prevent.

The commands below are a **fresh install**. Every one of them refuses when
the destination already exists, because upstream Embassy may carry its own
`AGENTS.md` or `opencode.json` and silently replacing it loses work. When a
destination exists, stop and diff/merge it manually: compare the shipped file
with the existing one, carry over the halucinator sections, and keep unrelated
configuration.

Per project:

```sh
# POSIX
[ ! -e /path/to/embassy/AGENTS.md ] || exit 1
[ ! -e /path/to/embassy/opencode.json ] || exit 1
[ ! -e /path/to/embassy/.opencode ] || exit 1
cp halucinator/AGENTS.md /path/to/embassy/AGENTS.md
cp halucinator/docs/opencode.json /path/to/embassy/opencode.json
mkdir -p /path/to/embassy/.opencode
cp -R halucinator/.opencode/. /path/to/embassy/.opencode/
```

```powershell
# PowerShell
if (Test-Path -LiteralPath D:\path\to\embassy\AGENTS.md) { throw "AGENTS.md exists; diff and merge manually" }
if (Test-Path -LiteralPath D:\path\to\embassy\opencode.json) { throw "opencode.json exists; diff and merge manually" }
if (Test-Path -LiteralPath D:\path\to\embassy\.opencode) { throw ".opencode exists; diff and merge manually" }
Copy-Item halucinator\AGENTS.md D:\path\to\embassy\AGENTS.md
Copy-Item halucinator\docs\opencode.json D:\path\to\embassy\opencode.json
New-Item -ItemType Directory -Path D:\path\to\embassy\.opencode
Copy-Item -Recurse -Path halucinator\.opencode\* -Destination D:\path\to\embassy\.opencode\
```

Or install the agents and skills globally, for every project:

```sh
[ ! -e ~/.config/opencode/opencode.json ] || exit 1
mkdir -p ~/.config/opencode
cp -R halucinator/.opencode/. ~/.config/opencode/
cp halucinator/docs/opencode.json ~/.config/opencode/opencode.json
```

```powershell
if (Test-Path -LiteralPath "$HOME\.config\opencode\opencode.json") { throw "global config exists; diff and merge manually" }
New-Item -ItemType Directory -Path "$HOME\.config\opencode" -ErrorAction SilentlyContinue
Copy-Item -Recurse -Path halucinator\.opencode\* -Destination "$HOME\.config\opencode\"
Copy-Item halucinator\docs\opencode.json "$HOME\.config\opencode\opencode.json"
```

Restart opencode afterwards. Config is read once at startup and is not
hot-reloaded.

## The references

Everything here rests on two sources, both cited throughout
`AGENTS.md`:

- **`embassy-mcxa/`** — the north star. `DEVGUIDE.md` in that crate is
  the closest thing embassy has to a "how to write a HAL" guide, and
  it was written to be generalized. Read it first.
- **["Making Smaller Things"](https://balbi.sh/posts/making-smaller-things/)**
  — the design discipline. Functional core and imperative shell;
  primitives at the edges and meaning in the middle; parse rather than
  validate; count the inhabitants of every type you introduce; and the
  failure mode of over-encoding.

The two agree more than they differ. Where they agree, `AGENTS.md`
treats the rule as non-negotiable.

## The pipeline

```
gather-documentation  →  hal-datasheet
        ↓
generate-svd          →  hal-svd
        ↓
generate-pac          →  hal-svd
        ↓
scaffold-hal          →  hal-architect (design)
                         hal-driver    (clocks, startup semantics)
                         hal-integrator (shared files, manifests, wiring)
        ↓
peripheral drivers    →  hal-driver   (one per peripheral, repeated)
        ↓
examples & HIL tests  →  hal-tester   (black-box logic and evidence)
        ↓                 hal-integrator (placement, manifests, CI)
        ↓                 write-examples
        ↓
review                →  hal-reviewer (typed verdict on a frozen candidate)
```

`hal-coordinator` sits above every row: it owns sequencing, dispatch, and
both gates. Stages are not strictly serial — a driver regularly sends you
back to the manual — but the dependency direction never reverses. You cannot
write a driver for a register the PAC does not expose.

The peripheral-drivers row runs on one generic per-peripheral procedure,
[write-driver](.opencode/skills/write-driver/SKILL.md): it applies the
universal driver obligations to every peripheral and then selects a GPIO,
Embassy-time-service or bus profile for the subsystem at hand, so a bus shape
is never treated as universal.

## The agents

`.opencode/ownership.toml` is the single machine-readable source of truth for
which agent may write which file class, and who may commit. The table below is
a projection of it.

| Agent | Mode | Owns | Writes |
|---|---|---|---|
| `hal-coordinator` | primary | Workflow decisions, scope, sequencing, dispatch, roadmap, and both gates; no implementation and no commit | `halucinator/state.toml`, `halucinator/scope/*.toml`, `halucinator/docs/<target-id>/notes/ROADMAP.md` |
| `hal-architect` | subagent | Design specifications only: module boundaries, APIs, trait shapes, startup and clock contracts, invariants, failure modes | `notes/ARCHITECTURE.md` only — no HAL, PAC, test, generated, manifest, linker or runtime code |
| `hal-datasheet` | subagent | Vendor source bytes, extraction, cited fact notes, contradictions and unknowns, and the `01`/`02` handoffs | `docs/<target-id>/sources/**`, `extracted/**`, `notes/FACTS.md` and `notes/facts/**`, its two handoffs |
| `hal-svd` | subagent | Machine-readable SVD, chiptool transforms, metapac and interrupt metadata, PAC generation, and the `03`/`04` handoffs | `halucinator/pac/**`, `notes/SVD.md`, `notes/PAC.md`, its two handoffs |
| `hal-driver` | subagent | One peripheral or hardware-semantic subsystem end to end, including clocks, its host functional-core tests, record delta content, and the `06` handoff | `embassy-*/src/**` and `halucinator/candidates/driver-*/src/**`, excluding `lib.rs`, `chips/**` and `_generated.rs`; its handoff |
| `hal-tester` | subagent | Black-box test logic, setup guidance, authorized run evidence, and the `07` handoff; no canonical HAL or test file | `halucinator/test-candidates/**` and its handoff only. Read-blinded from HAL source; `cargo fmt` denied |
| `hal-integrator` | subagent | Sole writer of shared and crate-level files, durable records, `SOURCES.md`, canonical test files — and **sole committer** | `embassy-*/Cargo.toml`, `build.rs`, `memory.x`, `link*.x`, `src/lib.rs`, `src/chips/**`, `src/_generated.rs`, `examples/*/**`, `tests/*/**`, `ci.sh`, `rust-toolchain.toml`, `rustfmt.toml`, `.gitattributes`, `.gitignore`, the durable records, and the `05` handoff |
| `hal-reviewer` | subagent | Findings and the `08` typed verdict | Its own verdict handoff and **nothing else**. It never edits, fixes, or commits an artifact it reviews |

### Entry point and dispatch

All Embassy HAL work enters through `hal-coordinator`. Specialist HAL agents are
dispatched only by `hal-coordinator` with the typed payload their agent contract
requires. Generic agents—including `build`, `plan`, `general`, `explore`,
`coder`, `integrator`, `architect`, `reviewer`, and `tester`—may be used only
for a bounded support task that `hal-coordinator` explicitly delegates. A
generic agent may not own a workflow stage, mutate canonical HAL/PAC/test
artifacts, change scope or decisions, accept a gate, or substitute for a HAL
specialist. If routing is ambiguous, return to `hal-coordinator` rather than
falling back.

Specialists never dispatch peers: every one of the seven declares `task: deny`.
Work that belongs to another agent goes back to `hal-coordinator`.

### The two typed gates

Both gates are `hal-coordinator`'s, and both are token comparisons rather than
judgement calls.

**Admission.** Only `handoff.status = ready` admits canonical mutation and
downstream completion. `partial` admits only read-only inspection and the
schema-defined disposable candidate work — never a canonical write, and never
a downstream `ready` claim. `blocked` admits nothing.

**Acceptance.** Only `review.verdict = ready` accepts. `ready-with-fixes` and
`not-ready` do not. A required finding is resolved by its owner and rechecked;
a stale or unavailable review is not acceptance.

Three boundaries worth knowing:

- **`hal-svd` owns PAC generation as well as SVD.** They are one
  toolchain domain — chiptool transforms, metapac metadata, the
  generator. Splitting them would produce an agent that hands over a
  file and does nothing else.
- **`hal-datasheet` owns epistemology; `hal-svd` owns representation.**
  The seam is not "meaning versus structure": `hal-datasheet` already
  extracts offsets, widths, access and reset values. It turns vendor
  evidence into *cited hardware assertions, contradictions, applicability
  and unknowns*. `hal-svd` turns accepted assertions into a
  *machine-readable SVD, transform and PAC representation*. That makes it a
  trust boundary rather than a formatting step: `hal-svd` must never turn
  an absent fact into a plausible value. A register nobody cited stays
  absent.
- **Tests split by where they run.** Host-side unit tests of a
  driver's pure functions — baud maths, encode/decode — belong to
  `hal-driver`, which needs them to develop. Anything that runs on
  target belongs to `hal-tester`.

### Why `hal-tester` is blindfolded

`hal-tester` is denied read access to `embassy-*/src/**`, to
`halucinator/candidates/**`, and to every `*.rs` and `*.x` file, then granted
read access back to `halucinator/test-candidates/**`. It is given the
peripheral's public API in its prompt instead.

This is the whole point of the agent. A tester that has read the driver
writes tests that agree with the driver — including everywhere the
driver is wrong. Removing its ability to look makes its tests a genuine
second opinion, and turns "I can't test this, the API doesn't expose
it" into a design finding rather than a workaround.

**Perfect blindness is impossible.** This is a strong default and an explicit
statement of intent, not a sandbox. The known escape hatches:

- `bash` is gated at `ask`, not denied, so a determined agent can shell out to
  read a file — and you will see the prompt.
- `grep` is `ask` because OpenCode matches grep permission against the *regex
  query*, not the searched path, so it cannot be path-enforced at all.
- Compiler, macro-expansion and build-script diagnostics quote source. So do
  LSP responses, generated documentation, dep-info and incremental files.
  Compiler-visible public API and type details are acceptable; body excerpts
  are not. That is why the tester runs no mutating Cargo command itself:
  `hal-integrator` builds the isolated candidate and returns only sanitized
  `{category, error_code, test_location, public_signature_mismatch, message}`.
- `glob` and `list` still reveal filenames.

Schema 2 constrains `destination_crate` to a repository-root one-segment
`embassy-<vendor_id>`; a named root, a nested path or an alias is rejected with
`ILLEGAL_ENUM`. That root is covered by the deny glob `embassy-*/**`. This
closes configured-path coverage, not perfect blindness: `bash` is `ask`, `grep`
is matched against the query rather than the path, and filenames, compiler and
build-script diagnostics, history and tools remain leak paths; observed body
text invalidates the run.

An observed leak invalidates that run, and `hal-coordinator` must dispatch a
fresh tester context. Nothing mechanically enforces that.

The user prepares the physical setup; `hal-tester` loads and runs the authorized
tests and returns evidence. It selects
[write-examples](.opencode/skills/write-examples/SKILL.md) for the RAM-first
build/run/retest workflow, combined with the peripheral's public validation
guidance for specific cases. [AGENTS.md](AGENTS.md) keeps the shared ownership
and authorization boundaries.

`hal-datasheet` depends on `pdftotext -layout`. Reference manuals are
multi-column and register tables carry their meaning in the column
alignment; without `-layout` the extraction produces noise that still
looks like data, which is exactly how invented offsets reach code.

## Known skill/agent ownership conflicts

The eight-agent topology landed without touching any `SKILL.md`. Several skills
therefore still assign ownership, dispatch or verdict vocabulary to the wrong
agent. **The agent contract and `.opencode/ownership.toml` win; the skill's
domain procedure applies only inside the dispatched agent's ownership
boundary.** Every agent carries that precedence sentence and the IDs of the
conflicts that affect it.

The skill retrofit and the M4 driver consolidation have since resolved
conflicts 1–11 in the skill layer: the six skills — `gather-documentation`,
`generate-svd`, `generate-pac`, `scaffold-hal`, `write-driver`,
`write-examples` — now state ownership, dispatch and verdict vocabulary
consistent with the agents, so the cited line ranges below record what was
wrong rather than what a reader will find today. Conflicts 6 and 9 are
historical: the two skills they cited, `write-gpio` and `write-time-driver`,
were consolidated into `write-driver` and no longer exist, so their entries
carry no link. The precedence rule stays stated in every agent, because an
installed agent may still meet an unreconciled or third-party skill.

The verified conflicts, defined here once so no agent file copies a
citation that can drift:

1. [`scaffold-hal/SKILL.md:129-146`](.opencode/skills/scaffold-hal/SKILL.md)
   assigns manifests, generation wiring, crate root, chip structure,
   initialization **and clocks** to `hal-architect`. Shared files belong to
   `hal-integrator`, clocks implementation to `hal-driver`, and design only to
   `hal-architect`.
2. [`scaffold-hal/SKILL.md:148-179`](.opencode/skills/scaffold-hal/SKILL.md)
   makes `hal-architect` dispatch drivers and the tester, and asks the tester
   for binaries and CI wiring. Dispatch routes through `hal-coordinator`; file
   placement and CI belong to `hal-integrator`.
3. [`write-examples/SKILL.md:67-87,105-124,168-174`](.opencode/skills/write-examples/SKILL.md)
   tells the tester to write binaries into `examples/` and `tests/`, wire CI,
   run formatting, and return changed files. The tester owns logic and
   evidence; `hal-integrator` owns candidate builds and final placement.
4. [`generate-svd/SKILL.md:150-164`](.opencode/skills/generate-svd/SKILL.md)
   and [`generate-pac/SKILL.md:93-98`](.opencode/skills/generate-pac/SKILL.md)
   tell `hal-svd` to register its record in `SOURCES.md` and return to
   `hal-architect`. `SOURCES.md` writes belong to `hal-integrator`; routing
   belongs to `hal-coordinator`.
5. [`gather-documentation/SKILL.md:63-74`](.opencode/skills/gather-documentation/SKILL.md)
   tells `hal-datasheet` to create or update `SOURCES.md`. It owns the initial
   content; `hal-integrator` materializes every edit, because the catalog is
   shared by five stages.
6. Historical, in the now-deleted `write-gpio/references/gpio-record.md:3-11`
   and `write-time-driver/references/time-record.md:3-14`: they assigned the
   durable GPIO and time-driver records jointly to `hal-driver` and
   `hal-architect` and asked them to link `SOURCES.md`. Record content is
   `hal-driver`'s; every record and `SOURCES.md` file write is
   `hal-integrator`'s.
7. [`test-record.md:3-23`](.opencode/skills/write-examples/references/test-record.md)
   assigns public record and log maintenance to `hal-tester`. Content and
   evidence are the tester's; the committed file writes are
   `hal-integrator`'s.
8. [`scaffold-record.md:3-30`](.opencode/skills/scaffold-hal/references/scaffold-record.md)
   makes `SCAFFOLD.md` and the roadmap `hal-architect`-maintained. `SCAFFOLD.md`
   is `hal-integrator`'s; the roadmap is `hal-coordinator`'s.
9. Historical, in the now-deleted `write-gpio/SKILL.md:99-123` and
   `write-time-driver/SKILL.md:94-118`: they routed tester and reviewer
   handoffs through `hal-architect` and quoted the legacy spaced rejection
   spelling instead of the typed verdict tokens. Routing is
   `hal-coordinator`'s; the tokens are `ready`, `ready-with-fixes`
   and `not-ready`.
10. [`gather-documentation/SKILL.md:15-17,38-39,173-177,192-193,198-199`](.opencode/skills/gather-documentation/SKILL.md)
    routes the intake handoff, the unanswered interview questions, the
    unimplemented-downstream gap, the hardware-setup questions, and the
    intake-completion gate to `hal-architect`. All five are
    `hal-coordinator`'s: it sequences, it dispatches, and it holds both gates.
    `hal-architect` writes design specifications and nothing else.
11. [`write-examples/SKILL.md:35-37,55-57,142-144,159-165`](.opencode/skills/write-examples/SKILL.md)
    routes the tester's scope questions, its execution-scope resolution, its
    driver/PAC/shared-startup repair handoffs, and its review handoff and task
    closure through `hal-architect`. Every one of those routes through
    `hal-coordinator` instead, which dispatches the owning agent — `hal-driver`
    for a driver defect, `hal-svd` for a PAC gap, `hal-integrator` for shared
    startup, linker or build wiring — and `hal-reviewer` for the verdict.

## Naming

HAL, plus the thing you must stop a language model from doing to
register offsets.

## License

TBD.
