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
| Agents (5) | written |
| Skills | **not yet written** |

The agents reference four skills by name — `gather-documentation`,
`generate-svd`, `generate-pac`, `scaffold-hal`. Those are still being
designed. Until they exist the agents work directly from `AGENTS.md`
and from `embassy-mcxa`, which is most of the value anyway.

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

**Agents** — copy or symlink into the target repository. opencode has
a `skills.paths` config key but **no equivalent for agents**: they are
only discovered under `.opencode/agent(s)/` in the project or
`~/.config/opencode/agent(s)/` globally. There is no config line that
points at this repository.

Per project:

```sh
# POSIX
cp halucinator/AGENTS.md          /path/to/embassy/AGENTS.md
mkdir -p                          /path/to/embassy/.opencode/agents
cp halucinator/.opencode/agents/*.md /path/to/embassy/.opencode/agents/
```

```powershell
# PowerShell
Copy-Item halucinator\AGENTS.md D:\path\to\embassy\AGENTS.md
New-Item -ItemType Directory -Force -Path D:\path\to\embassy\.opencode\agents
Copy-Item halucinator\.opencode\agents\*.md D:\path\to\embassy\.opencode\agents\
```

Or install the agents globally, for every project:

```sh
cp halucinator/.opencode/agents/*.md ~/.config/opencode/agents/
```

```powershell
Copy-Item halucinator\.opencode\agents\*.md $HOME\.config\opencode\agents\
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
review                →  hal-reviewer (gates every stage above)
```

Stages are not strictly serial — a driver regularly sends you back to
the manual — but the dependency direction never reverses. You cannot
write a driver for a register the PAC does not expose.

## The agents

| Agent | Mode | Owns | Edits |
|---|---|---|---|
| `hal-architect` | primary | Roadmap, phase gating, crate scaffolding, `init`, feature policy, delegation | yes |
| `hal-datasheet` | subagent | Reference-manual extraction: register semantics, init sequences, clock/reset dependencies, field encodings, errata | yes |
| `hal-svd` | subagent | SVD authoring, chiptool transforms, metapac metadata, PAC generation | yes |
| `hal-driver` | subagent | One peripheral end to end: `Instance`/`Info`, mode type-state, interrupt handlers, DMA, `embedded-hal` impls | yes |
| `hal-reviewer` | subagent | Adversarial audit against DEVGUIDE and the type discipline | **no** |

`hal-architect` is the entry point. It sequences the work and
dispatches the rest.

Two boundaries worth knowing:

- **`hal-svd` owns PAC generation as well as SVD.** They are one
  toolchain domain — chiptool transforms, metapac metadata, the
  generator. Splitting them would produce an agent that hands over a
  file and does nothing else.
- **`hal-datasheet` extracts *meaning*; `hal-svd` extracts
  *structure*.** Offsets and bit ranges become SVD. Initialisation
  sequences, clock dependencies, legal field encodings and errata
  become notes that `hal-driver` reads.

`hal-datasheet` depends on `pdftotext -layout`. Reference manuals are
multi-column and register tables carry their meaning in the column
alignment; without `-layout` the extraction produces noise that still
looks like data, which is exactly how invented offsets reach code.

## Naming

HAL, plus the thing you must stop a language model from doing to
register offsets.

## License

TBD.
