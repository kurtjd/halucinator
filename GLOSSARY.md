# Glossary

This reference defines terms as the halucinator toolkit uses them. It does not
replace the live Embassy sources that a HAL workflow must read. Terms are
alphabetical; cross-references point to the governing corpus.

## Admission gate

The coordinator's stage-entry rule. A validated handoff with
`handoff.status = ready` permits normal downstream consumption. `partial`
permits only read-only inspection and schema-defined disposable candidate work;
`blocked` permits no downstream consumption. See the
[common handoff consumption contract](.opencode/schema/handoff-common.md#consumption-contract)
and [the two typed gates](README.md#the-two-typed-gates).

## Acceptance gate

The coordinator's final review rule. Only the typed review verdict `ready`
accepts an artifact; `ready-with-fixes` and `not-ready` do not. The reviewer
supplies the verdict but does not apply the gate. See the
[`08-review` schema](.opencode/schema/08-review.md) and
[the two typed gates](README.md#the-two-typed-gates).

## Blinding

The source-access restriction used to make `hal-tester` exercise a driver's
public contract without reading its implementation. It is a strong default,
not a sandbox: command approvals, filenames, diagnostics, history, and other
tools can still reveal information. An observed implementation-body leak
invalidates that test run. See
[Why `hal-tester` is blindfolded](README.md#why-hal-tester-is-blindfolded).

## Candidate

An isolated, non-canonical work product used for implementation, generation,
integration, or testing before admission, checks, and review permit publication
to the canonical location. Candidate and replay outputs must not replace a
previously verified artifact on failure. See
[the working-artifact layout](README.md#working-artifacts) and the
[`generate-pac` output rules](.opencode/skills/generate-pac/SKILL.md#outputs).

## Canonical

The live destination artifact that downstream work consumes, as distinct from
a disposable candidate or replay. Canonical mutation requires a ready
predecessor and the owning agent; a failed or partial candidate must not replace
it. See the [common handoff consumption contract](.opencode/schema/handoff-common.md#consumption-contract)
and [`generate-pac` publication procedure](.opencode/skills/generate-pac/SKILL.md#procedure).

## chiptool

The register-description tool used by the SVD and PAC toolchain to extract SVD
data into YAML intermediate representation, apply ordered transforms, check that
representation, and, in the later generation workflow, support Rust generation.
Its transforms correct the authoritative input; generated output is not edited
by hand. The toolkit documents an inspected revision but does not bundle the
binary. See the
[SVD reference toolchain](.opencode/skills/generate-svd/references/preparation-and-checks.md#reference-toolchain)
and [where the PAC comes from](AGENTS.md#where-the-pac-comes-from).

## DEVGUIDE

`embassy-mcxa/DEVGUIDE.md` in the user's live Embassy checkout. The toolkit
treats it as the closest available guide to writing a modern Embassy HAL and
requires contributors to read it before choosing crate or driver patterns. It
is not shipped here. See [the two references](AGENTS.md#the-two-references) and
the [driver live-reference checklist](.opencode/skills/write-driver/references/driver-checklist.md#live-reference-reading).

## Functional core / imperative shell

The design split in which pure value-to-value work—encoding, decoding, timing,
layout, and divisor calculations—stays free of registers, async execution, and
HAL types, while a small shell performs hardware access with few branches. This
makes the core host-testable and keeps hardware policy visible. See
[the design discipline](AGENTS.md#2-making-smaller-things--the-design-discipline)
and the [driver finite-type checklist](.opencode/skills/write-driver/references/driver-checklist.md#finite-types-and-the-functional-core).

## `Gate`

An `embassy-mcxa` example name for an implementation of the general clock,
reset, and power management contract. It is not a required name or shape for a
new target: the target must state its actual policy owners, acquisition and
initialization, reset arbitration, lifetime accounting or its explicit absence,
teardown and quiescence, frequency source or irrelevance, and cancellation
behavior. This repository does not contain the `embassy-mcxa` source, so it does
not specify a `Gate` API signature. See [HAL-RULE-04](AGENTS.md#hard-rules) and
the [`write-clocks` boundary](.opencode/skills/write-clocks/SKILL.md#when-to-use).

## Handoff

A schema-versioned TOML artifact passed between pipeline stages. Every handoff
has common status, scope, coverage, checks, inputs, notes, and blockers, plus
kind-specific fields. Current deterministic paths run from
`halucinator/handoff/01-sources.toml` through
`halucinator/handoff/08-review-<artifact>.toml`, with parameterized driver and
test filenames. See the [common handoff contract](.opencode/schema/handoff-common.md)
and the [runtime artifact layout](.opencode/schema/layout.md).

The eight kind definitions are
[`01-sources`](.opencode/schema/01-sources.md),
[`02-facts`](.opencode/schema/02-facts.md),
[`03-svd`](.opencode/schema/03-svd.md),
[`04-pac`](.opencode/schema/04-pac.md),
[`05-platform`](.opencode/schema/05-platform.md),
[`06-driver`](.opencode/schema/06-driver.md),
[`07-tests`](.opencode/schema/07-tests.md), and
[`08-review`](.opencode/schema/08-review.md).

## HIL

Hardware-in-the-loop validation: a test or bounded demonstration that loads and
runs target code against a physically prepared board and observes behavior
through a public channel. It belongs to `write-examples` and `hal-tester`, needs
explicit readiness and authorization, and is distinct from host tests and
build-only checks. The toolkit contains execution policy but no universal probe
adapter, device database, or output parser. See
[Hardware Execution](.opencode/skills/write-examples/references/hardware-execution.md)
and the [open HIL tooling gaps](TODO.md#h-promises-without-implementation).

## Lease

Not the name of halucinator's board-exclusion mechanism. The mechanism is a
**worktree-local, single-operator board interlock** and is explicitly not a
lease, broker, sandbox, or cross-clone guarantee. The word survives only in the
field name `lease_epoch`, where it provides compact identity for one interlock
epoch. See [the board interlock contract](.opencode/schema/layout.md#the-worktree-local-single-operator-board-interlock)
and [hardware execution section 0](.opencode/skills/write-examples/references/hardware-execution.md#0-acquire-the-worktree-local-board-interlock).

## Metapac

A PAC organization based on shared peripheral-IP definitions plus per-chip
metadata that records which instances a part contains. In this toolkit it is
the preferred structure for new PAC work because one peripheral definition can
serve multiple compatible chips without claiming family-wide support. See
[where the PAC comes from](AGENTS.md#where-the-pac-comes-from) and the
[`generate-pac` entry conditions](.opencode/skills/generate-pac/SKILL.md#when-to-use).

## North star

The live `embassy-mcxa` crate used as the primary pattern library for a new HAL.
It guides structure and conventions but is not scripture: documented intent
wins over a local wart, and target-specific hardware choices must not be copied
by analogy. See [the north-star reference](AGENTS.md#1-embassy-mcxa--the-north-star).

## `OnDrop`

The cancellation guard named by the driver rules for an armed hardware region.
The rules require it to perform cleanup if a future is dropped, and require the
success path to call `defuse` only after the operation has safely completed its
cleanup. The corpus states this
required pattern but does not define the type's API signature, because the
implementation lives in the user's Embassy checkout. See
[HAL-RULE-09](AGENTS.md#hard-rules) and the
[driver cancellation checklist](.opencode/skills/write-driver/references/driver-checklist.md#cancellation-drop-and-reuse).

## PAC

Peripheral access crate: generated Rust access to the target's register and
interrupt description. The workflow contract requires reproducible production
from source-backed SVD data, transforms, metadata, and generator inputs, and
forbids hand-editing generated output. The toolkit currently ships no complete
PAC generator setup, schema, templates, or tooling; it asks the workflow to
establish minimal source-backed tooling in the selected PAC project. A usable
PAC is an input to HAL scaffolding, not the HAL itself. See
[PAC placement and origin](AGENTS.md#pac-placement),
[`generate-pac`](.opencode/skills/generate-pac/SKILL.md), and the
[open generator gap](TODO.md#h-promises-without-implementation).

## SVD

The CMSIS System View Description XML register description used as an input to
the PAC toolchain. A vendor SVD is an input rather than a deliverable: the
workflow contract requires it to be checked against cited facts, requires
recorded chiptool transforms where supported, and requires representation limits
to be preserved before prepared data is admitted to PAC generation. See
[`generate-svd`](.opencode/skills/generate-svd/SKILL.md) and
[SVD preparation](.opencode/skills/generate-svd/references/preparation-and-checks.md).

## target-id

The documentation and derived-run identifier formed from the exact vendor and
part identifiers: separate them with `-`, lowercase them, replace each run of
non-ASCII-alphanumeric characters with `-`, and trim edge hyphens. It identifies
a workspace path but is not proof that an existing directory belongs to the
same target. See the
[source-list naming rule](.opencode/skills/gather-documentation/references/source-list-format.md#location)
and [artifact storage](AGENTS.md#artifact-storage-and-handoff).

## Teleprobe

A name the corpus applies to target-side test binaries and target declarations
used by Embassy's hardware-test infrastructure. The toolkit requires the live
checkout's established test pattern to be inspected rather than prescribing a
portable teleprobe command. It ships no teleprobe command procedure, manifest
template, or result protocol. See the [pipeline testing split](AGENTS.md#the-pipeline),
the [`write-examples` integration step](.opencode/skills/write-examples/SKILL.md#procedure),
and the [recorded tooling gap](TODO.md#h-promises-without-implementation).

## Typed verdict

The closed review result in an `08-review` handoff:
`ready`, `ready-with-fixes`, or `not-ready`. Only `ready` is an accepting token.
The fixed vocabulary prevents prose such as “looks good” from silently becoming
gate authority. See the [`08-review` schema](.opencode/schema/08-review.md).

## typestate

A technique that represents allowed protocol states in types so invalid state
transitions cannot be expressed. The toolkit mentions it chiefly as an
over-encoding risk: use it only for an invariant a caller could plausibly get
wrong at a boundary, rather than creating a state type for every internal step.
See [Making Smaller Things in the design discipline](AGENTS.md#2-making-smaller-things--the-design-discipline).

## `WaitCell`

An `embassy-mcxa` example of per-instance asynchronous waiter state. The corpus
uses it to illustrate the need to separate instance state from shared banks,
interrupt routes, clocks, and resets; it does not require one `WaitCell` per
instance on every target. This repository does not contain the implementation,
so no API signature is asserted here. See the
[`hal-driver` architecture boundary](.opencode/agents/hal-driver.md) and
[`write-driver` ownership boundary](.opencode/skills/write-driver/SKILL.md#ownership-and-boundaries).
