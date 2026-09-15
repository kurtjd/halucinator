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
| Agents (6) | written |
| Skills | 1 written, 4 not yet written |

[gather-documentation](.opencode/skills/gather-documentation/SKILL.md)
is implemented. `generate-svd`, `generate-pac`, `scaffold-hal`, and
`write-examples` are still being designed. For those stages, agents
work directly from `AGENTS.md` and from `embassy-mcxa`.

## Prerequisite

halucinator assumes you are working **inside a clone of
`embassy-rs/embassy`**, with your new crate at `embassy-<vendor>/`
alongside `embassy-mcxa/`.

This is deliberate. Rather than embedding snapshots of embassy
patterns that go stale, the agents cite live paths —
`embassy-mcxa/DEVGUIDE.md`, `embassy-mcxa/src/i2c/controller.rs`,
`embassy-mcxa/src/clocks/gate.rs`. Outside an embassy checkout those
citations do not resolve and the agents are largely useless.

## Install

Two things move, and they move differently.

**`AGENTS.md`** — copy to the root of your embassy checkout, or merge
into the one already there.

**Agents and skills**: copy or symlink the whole `.opencode/` directory,
including the skills' bundled references. Merge into an existing
`.opencode/` directory, preserving unrelated files and configuration.

The commands below overwrite matching files.

Per project:

```sh
# POSIX
cp halucinator/AGENTS.md /path/to/embassy/AGENTS.md
mkdir -p /path/to/embassy/.opencode
cp -R halucinator/.opencode/. /path/to/embassy/.opencode/
```

```powershell
# PowerShell
Copy-Item halucinator\AGENTS.md D:\path\to\embassy\AGENTS.md
New-Item -ItemType Directory -Force -Path D:\path\to\embassy\.opencode
Copy-Item -Recurse -Force -Path halucinator\.opencode\* -Destination D:\path\to\embassy\.opencode\
```

Or install the agents and skills globally, for every project:

```sh
mkdir -p ~/.config/opencode
cp -R halucinator/.opencode/. ~/.config/opencode/
```

```powershell
New-Item -ItemType Directory -Force -Path "$HOME\.config\opencode"
Copy-Item -Recurse -Force -Path halucinator\.opencode\* -Destination "$HOME\.config\opencode\"
```

Restart opencode afterwards. Config is read once at startup and is not
hot-reloaded.

## The references

Everything here rests on two sources, both cited throughout
`AGENTS.md`:

- **`embassy-mcxa/`** — the north star. `DEVGUIDE.md` in that crate is
  the closest thing embassy has to a "how to write a HAL" guide, and
  it was written to be generalised. Read it first.
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
scaffold-hal          →  hal-architect
        ↓
peripheral drivers    →  hal-driver   (one per peripheral, repeated)
        ↓
examples & HIL tests  →  hal-tester   (black-box, per peripheral)
        ↓                 write-examples
        ↓
review                →  hal-reviewer (gates every stage above)
```

Stages are not strictly serial — a driver regularly sends you back to
the manual — but the dependency direction never reverses. You cannot
write a driver for a register the PAC does not expose.

## The agents

| Agent | Mode | Owns | Edits |
|---|---|---|---|
| `hal-architect` | primary | Roadmap, phase gating, crate scaffolding, `init`, feature policy, delegation | yes |
| `hal-datasheet` | subagent | Documentation intake and reference-manual extraction: register semantics, init sequences, clock/reset dependencies, field encodings, errata | yes |
| `hal-svd` | subagent | SVD authoring, chiptool transforms, metapac metadata, PAC generation | yes |
| `hal-driver` | subagent | One peripheral end to end: `Instance`/`Info`, mode type-state, interrupt handlers, DMA, `embedded-hal` impls | yes |
| `hal-tester` | subagent | `examples/<chip>/`, `tests/<chip>/` teleprobe binaries, `ci.sh` wiring — adversarial, black-box | yes |
| `hal-reviewer` | subagent | Adversarial audit against DEVGUIDE and the type discipline | **no** |

`hal-architect` is the entry point. It sequences the work and
dispatches the rest.

Three boundaries worth knowing:

- **`hal-svd` owns PAC generation as well as SVD.** They are one
  toolchain domain — chiptool transforms, metapac metadata, the
  generator. Splitting them would produce an agent that hands over a
  file and does nothing else.
- **`hal-datasheet` extracts *meaning*; `hal-svd` extracts
  *structure*.** Offsets and bit ranges become SVD. Initialisation
  sequences, clock dependencies, legal field encodings and errata
  become notes that `hal-driver` reads.
- **Tests split by where they run.** Host-side unit tests of a
  driver's pure functions — baud maths, encode/decode — belong to
  `hal-driver`, which needs them to develop. Anything that runs on
  target belongs to `hal-tester`.

### Why `hal-tester` is blindfolded

`hal-tester` is denied read access to `embassy-*/src/**` in its
frontmatter, and is given the peripheral's public API in its prompt
instead.

This is the whole point of the agent. A tester that has read the driver
writes tests that agree with the driver — including everywhere the
driver is wrong. Removing its ability to look makes its tests a genuine
second opinion, and turns "I can't test this, the API doesn't expose
it" into a design finding rather than a workaround.

Two honest caveats. The deny patterns cover `read` and `grep`; `bash`
is gated at `ask` for everything except `cargo build`/`check`/`clippy`/
`fmt`, so a determined agent could still shell out to read a file and
you would see the prompt. And the pattern keys on `embassy-*/src/**`,
so a HAL crate placed somewhere else is not covered. This is a strong
default and an explicit statement of intent, not a sandbox.

`hal-tester` never flashes a board. It produces binaries plus bench
instructions — wiring, commands, expected output, and the failure
signature — and a human runs them.

`hal-datasheet` depends on `pdftotext -layout`. Reference manuals are
multi-column and register tables carry their meaning in the column
alignment; without `-layout` the extraction produces noise that still
looks like data, which is exactly how invented offsets reach code.

## Naming

HAL, plus the thing you must stop a language model from doing to
register offsets.

## License

TBD.
