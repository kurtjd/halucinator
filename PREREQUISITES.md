# Prerequisites

This is a reference matrix for preparing a halucinator run. The requirements
below are derived from the toolkit's own contracts and procedures. The toolkit
has not been exercised end to end in a real Embassy checkout or on real
hardware, so none of these rows is an observed compatibility claim.

The hard precondition is a clone of `embassy-rs/embassy`. Install halucinator
into that clone before starting OpenCode. The stages through target build and
link checks do not inherently require physical hardware, but they may still
block on absent target-specific tooling, including the open H2 PAC-generator
setup gap. A board, probe, and runner first become relevant for authorized
`write-examples` HIL execution.

## Prerequisite matrix

| Prerequisite | What it is and why it is needed | First stage that needs it | Status | POSIX check | PowerShell check |
|---|---|---|---|---|---|
| Embassy checkout | A clone of `embassy-rs/embassy`. Agents read the live `embassy-mcxa/DEVGUIDE.md` and implementation rather than a bundled snapshot. The rules require refusal outside a checkout with the three classification markers. The scaffold contract designates a new repository-root sibling at `embassy-<vendor>/` as the eventual destination; that crate need not exist at intake. | Before the pipeline starts | Required | `test -f Cargo.toml && test -f embassy-mcxa/DEVGUIDE.md && test -f .opencode/ownership.toml` | `Test-Path -LiteralPath Cargo.toml; Test-Path -LiteralPath embassy-mcxa/DEVGUIDE.md; Test-Path -LiteralPath .opencode/ownership.toml` |
| OpenCode and installed toolkit config | OpenCode runs the agents and skills. The install must place or merge `AGENTS.md`, `.opencode/`, and `opencode.json` in the Embassy checkout. The shipped config selects `hal-coordinator`. OpenCode reads config once, so restart it after installation. | Before the pipeline starts | Required | `opencode --version && test -f AGENTS.md && test -f .opencode/ownership.toml && test -f opencode.json` | `opencode --version; Test-Path -LiteralPath AGENTS.md; Test-Path -LiteralPath .opencode\ownership.toml; Test-Path -LiteralPath opencode.json` |
| Python 3.11 or newer | Runs the typed handoff validator and board-interlock helper. In this toolkit checkout it also runs `tools/selfcheck.py`. These programs use the standard-library `tomllib` module and explicitly state Python 3.11+. | Before any handoff is consumed; toolkit maintenance uses it immediately | Required | `python3 -c 'import sys; assert sys.version_info >= (3, 11); print(sys.version)'` | `python -c "import sys; assert sys.version_info >= (3, 11); print(sys.version)"` |
| `pdftotext -layout` | Poppler/Xpdf PDF extraction used both to preserve table alignment during fact extraction and by the schema-2 citation verifier to derive text from hash-pinned PDF bytes. Without it, PDF citation verification fails closed. | `gather-documentation` intake identifies PDF availability; `extract-hardware-facts` first executes it | Required when admitted evidence includes PDF; not applicable to UTF-8-text-only evidence | `command -v pdftotext && pdftotext -v` | `Get-Command pdftotext; pdftotext -v` |
| chiptool | Extracts SVD content, applies transforms, checks YAML intermediate representation, and supports the PAC generation toolchain. The selected revision and CLI must be inspected and recorded. The toolkit does not bundle chiptool. | `generate-svd`; reused by `generate-pac` as selected tooling | Required when the selected SVD/PAC recipe uses it | `command -v chiptool && chiptool --help` | `Get-Command chiptool; chiptool --help` |
| CMSIS-SVD schema and XML validator | A trusted local schema matching the source's declared SVD version, plus structured XML tooling. The corpus names `xmllint` as an example and requires network entity resolution to be disabled for untrusted input. The schema file itself is not bundled. | `generate-svd` | Required for the `schema-validation` check; absence leaves it `unrun` | `command -v xmllint && xmllint --version` | `Get-Command xmllint; xmllint --version` |
| Rust toolchain | `rustc`, Cargo, formatting, linting, host tests, generator builds, PAC builds, and HAL builds. The live Embassy checkout's toolchain policy is authoritative; this toolkit does not prescribe a separate Rust version. | `generate-svd` if chiptool must be built; otherwise no later than `generate-pac` | Required | `rustc --version && cargo --version && rustup show active-toolchain` | `rustc --version; cargo --version; rustup show active-toolchain` |
| Rust cross-compilation target | The coordinator-selected target triple needed to compile PAC and HAL code for the MCU. The schema fixture uses `thumbv7em-none-eabi` as a fixture value, not as a universal target. | `generate-pac` target-build checks | Required for the selected target | `rustup target list --installed` | `rustup target list --installed` |
| Target linker and binary inspection tools | The selected target must link, and runtime/linker integration inspects ELF load and execution ranges. Exact tools come from the live checkout and selected Rust target; the toolkit does not prescribe one external linker package for every target. | `scaffold-hal`, specifically runtime/linker integration | Required; exact external package is target-dependent | `rustc -vV && cargo --version` | `rustc -vV; cargo --version` |
| Debug probe, runner, and physical board | A probe plus a checkout-supported runner, such as an applicable probe-rs or teleprobe setup, loads and observes target code. The exact device, runner version, operations, public observation channel, wiring, and power conditions must be established. The toolkit bundles no universal adapter or device database. | `write-examples` hardware admission and HIL execution | Optional for build-only work; required only for an authorized hardware run after the user prepares the board | `command -v probe-rs || command -v teleprobe` | `Get-Command probe-rs -ErrorAction SilentlyContinue; Get-Command teleprobe -ErrorAction SilentlyContinue` |

Each command checks only that a named executable or marker is visible. It does
not establish target compatibility, correct wiring, sufficient permissions, or
successful end-to-end operation.

## Checkout and OpenCode installation

The [checkout context guard](AGENTS.md#checkout-context-guard) requires agents
to classify the working directory before any HAL workflow action. The Embassy classification
requires a root `Cargo.toml`, `embassy-mcxa/DEVGUIDE.md`, and the installed
ownership file. It does not require the destination crate to exist at intake;
the scaffold contract assigns the repository-root sibling named
`embassy-<vendor>/` as the eventual destination. The rules require a toolkit or ambiguous checkout to be
refused. The self-check verifies the guard text, not that an agent performs the
classification or refusal.

Follow the [fresh-install or merge procedure](README.md#install). Existing
`AGENTS.md`, `.opencode/`, or `opencode.json` must be diffed and merged rather
than overwritten. After installing or changing the config, restart OpenCode;
the configuration is read once at startup and is not hot-reloaded. The toolkit
does not state a minimum OpenCode version, so `opencode --version` verifies
presence only.

## Python validation

Python 3.11+ is a verified floor in the source headers for
[`validate.py`](.opencode/schema/validate.py),
[`runtime.py`](.opencode/schema/runtime.py), and
[`tools/selfcheck.py`](tools/selfcheck.py). Before a stage consumes a handoff,
the procedure runs:

```sh
python .opencode/schema/validate.py <repository-root> --kind all
```

Exit code 0 with silent output is necessary. A missing interpreter, an older
interpreter, timeout, nonzero exit, or failure to invoke the validator is not a
pass. This requirement is specified and validator-enforced where invoked; the
corpus also states that no static check can prove an agent invoked it earlier.
See the [consumption contract](.opencode/schema/handoff-common.md#consumption-contract)
and [validator reference](.opencode/schema/validate.md).

## PDF extraction and citation verification

Use `pdftotext` with `-layout`. Multi-column register tables carry meaning in
column alignment; extraction without layout preservation can produce noise that
still resembles valid data. The citation validator independently invokes the
tool for the cited physical page.

When the executable is absent, reproduce the corpus remedy exactly:

> Install `poppler-utils` (or `xpdf-utils` where that package supplies
> `pdftotext`), then rerun:
> `pdftotext -layout -f <page> -l <page> <source> -`.

The gate fails with `CITATION_UNVERIFIED`; it does not become
`not-applicable`. A pass proves a normalized occurrence in the bound source
bytes at the declared location. It does not prove semantic entailment, visual
contiguity, OCR correctness, or vendor truth. See the
[`pdftotext` failure contract](.opencode/schema/validate.md) and the
[fact-extraction procedure](.opencode/skills/extract-hardware-facts/SKILL.md#procedure).

A scanned or image-only PDF that yields no matching text is not mechanically
citable in the current workflow. No OCR path is authorized. Obtain a
text-capable authoritative edition or record the affected scope as blocked, as
required by the [`01-sources` schema](.opencode/schema/01-sources.md).

On Windows, the toolkit has not verified a specific package manager or Poppler
distribution. Install a distribution that exposes `pdftotext` on `PATH`, verify
it with `Get-Command pdftotext`, and then rerun the concrete command reported by
the validator. This Windows installation guidance is unverified; the executable
check and validator command are the specified boundary.

## SVD and PAC tooling gaps

The SVD procedure names `xmllint` only as an example. Any structured validator
must use a trusted local CMSIS-SVD schema matching the document's declared
version and must record the schema and validator identities. A missing schema or
validator leaves the required check `unrun`; XML well-formedness alone does not
establish schema conformance or hardware correctness. See
[Establish the source baseline](.opencode/skills/generate-svd/references/preparation-and-checks.md#establish-the-source-baseline).

The toolkit documents chiptool commands and an inspected pinned reference, but
it does not ship chiptool. More importantly, it ships no PAC generator, PAC
schema, templates, or complete generator setup. The `generate-pac` procedure
asks the workflow to establish minimal source-backed tooling in the selected PAC
project. The backlog records this as an open capability gap, not a ready-made
prerequisite that can be installed from this repository. See
[`generate-pac`](.opencode/skills/generate-pac/SKILL.md) and
[`TODO.md` item H2](TODO.md#h-promises-without-implementation).

## Rust targets, linking, and hardware

The exact Rust target is a coordinator decision derived from the selected MCU
and live checkout. Install that exact target before `generate-pac` target builds;
the presence of a different embedded target proves nothing. The corpus does not
state a Rust version floor or one universal linker package, so this reference
does not invent either.

No physical board is needed for documentation intake, fact extraction, SVD
preparation, PAC generation, platform scaffolding, driver host tests, or
build-only test integration. Hardware becomes necessary only when the selected
`write-examples` scope includes a hardware run. At that point the user performs
the physical setup and explicitly authorizes the named operations; an installed
runner or connected probe is not consent.

The runner must be the one supported by the live checkout and actual device.
The toolkit mentions probe-rs and teleprobe as possible ecosystem shapes but
does not mandate either executable, and it ships no command procedure, manifest
template, device database, or output parser for arbitrary hardware. Follow the
[hardware execution gates](.opencode/skills/write-examples/references/hardware-execution.md)
and treat the [open tooling gaps](TODO.md#h-promises-without-implementation)
as limitations, not implied capability.

Before any target-affecting operation, use the worktree-local board interlock
described in the [runtime layout](.opencode/schema/layout.md#the-worktree-local-single-operator-board-interlock).
It is not a lease, broker, sandbox, or cross-clone exclusion mechanism. Its
presence does not remove the requirement for physical readiness and explicit
authorization.
