# Start a HAL workflow

This tutorial takes a first-time halucinator user from an installed toolkit to
the first typed stage boundary: a validated documentation intake. At that point,
the source catalog and preserved documents exist, and
`halucinator/handoff/01-sources.toml` says whether the next stage may proceed.
The tutorial stops there deliberately; it does not claim that a HAL has been
built.

## What is demonstrated, and what is not

The artifact formats in this tutorial are demonstrated. The repository contains
a complete fictional fixture tree, the schema validator accepts that tree, and
the self-check suite exercises fixture acceptance and rejection. The agent and
skill definitions and the installation procedure are also present in the
repository.

The conversation below is **illustrative, not a recording**. No halucinator run
has yet built a HAL in a real Embassy checkout or operated real hardware.
Coordinator replies, model behavior, timing, documentation collection in a real
project, and every later stage are specified by the agent and skill contracts
but have not been observed end to end. In particular, SVD preparation, PAC
generation, crate scaffolding, drivers, and board execution are not proven by
the fixture.

## 1. Prepare the environment

Complete [the prerequisites](PREREQUISITES.md) first. You need an Embassy clone,
the required local tools, the exact identity of the target MCU, access to its
source documents, and enough board context to answer the intake questions.

Install halucinator **into the root of that Embassy checkout**, not into this
toolkit repository. The installation moves `AGENTS.md`, the complete
`.opencode/` tree, and the root OpenCode configuration in different ways, and it
must preserve any files already present. Follow the authoritative fresh-install
or merge instructions in [README.md](README.md), then restart OpenCode because
its configuration is read at startup.

After restart, confirm that `hal-coordinator` is the active primary agent. All
HAL workflow stages enter through it; do not invoke a specialist directly.

## 2. Send the first message

From the root of the Embassy checkout, send this exact message to
`hal-coordinator`:

```text
Start a new Embassy HAL workflow. Establish the exact MCU identity and initial scope with me, then dispatch documentation intake.
```

This is the point at which a newcomer is no longer guessing: send the message
above to `hal-coordinator`, answer its target and scope questions without
substituting a related part, and then answer the documentation specialist's
questions about source documents and bench context.

The coordinator contract requires it to establish the exact target and scope
before dispatch. It records those decisions in typed state and passes them to
the documentation specialist. That specialist, not the coordinator, subsequently
requests the source documents and bench context. The contract is defined in
[the coordinator agent](.opencode/agents/hal-coordinator.md); it is a
specification of the exchange, not evidence that a model will reproduce the
wording below.

## 3. Complete the intake interview

The exchange has two owners. First, expect the coordinator to establish:

1. **Exact target identity.** Give the vendor's exact MCU part number. Supply
   the package and silicon revision if known; absence is better than a guessed
   value.
2. **Initial scope.** Describe the first intended peripheral or use case and
   anything intentionally excluded. The coordinator turns that request into
   scope items. In this vocabulary, foundation work means crate-wide capability
   needed by drivers, such as initialization or interrupt metadata; you need not
   design those pieces yourself.

After dispatch, the documentation specialist requests the source set and bench
context: the exact target's manual, errata, datasheet, board schematic and guide,
supporting documents, and any existing SVD, followed by the probe or programmer,
debug interface, loader and version, host environment, board access, and existing
loading instructions. It is legitimate to answer that no board is available.
Physical hardware is not required for documentation intake or later build and
link validation, and reporting no board is better than inventing one. These are
setup facts, not authorization to touch hardware.

Here is the **illustrative shape** of that exchange. It uses the repository's
transparently fictional fixture identity and does not represent an observed
session:

```text
Coordinator: What are the exact vendor and MCU part number?
User: Vendor: Unobtainium Circuits. MCU: UC-NOT-A-REAL-MCU-0001.

Coordinator: What should the initial scope include and exclude?
User: Use the committed fixture scope: include the initialization foundation,
interrupt metadata, and the fictional schema-demo peripheral; exclude ADC.

Documentation specialist: Supply the source documents and any existing SVD,
then describe the board and bench context.
User: Use the committed fictional fixture source. No board, package, silicon
revision, or bench setup has been selected for this schema fixture. Do not infer
them.
```

For a real target, answer with facts from your project rather than adapting the
fictional names. If an identity is missing or contradictory, the specified
workflow blocks and asks for resolution instead of guessing.

## 4. Let documentation intake establish the source set

The coordinator dispatches the `gather-documentation` procedure to the owning
documentation specialist. The procedure requests and accounts for the exact
target's source material, preserves source bytes, records provenance and hashes,
and searches for an SVD starting point. Read the full procedure in
[`gather-documentation`](.opencode/skills/gather-documentation/SKILL.md) and its
[`SOURCES.md` format](.opencode/skills/gather-documentation/references/source-list-format.md).

The resulting documentation workspace uses this shape:

```text
halucinator/docs/<target-id>/
  SOURCES.md
  sources/
  extracted/
  notes/
halucinator/handoff/01-sources.toml
```

`SOURCES.md` is the durable human catalog. `sources/` preserves originals under
stable source identities. When source conversion is required, derived searchable
text belongs under `extracted/`; an empty directory need not be created during
intake. Notes hold the evidence used by intake checks. The TOML handoff is the
machine-readable contract and does not replace the catalog.

Do not treat the directory diagram as a promise that every directory always
exists. The source-list rules require directories to be created only when they
are needed. The committed fixture uses a UTF-8 text source directly, so it needs
no separate extraction.

You can inspect the demonstrated example rather than relying on a second example
invented here:

- [the complete worked artifact set](.opencode/schema/worked-examples.md)
- [the validated fictional source catalog](.opencode/schema/fixtures/valid/root/halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md)
- [the preserved fictional source](.opencode/schema/fixtures/valid/root/halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/FICTIONAL-MANUAL.txt)
- [the validated `01-sources.toml`](.opencode/schema/fixtures/valid/root/halucinator/handoff/01-sources.toml)

The fixture labels itself as fictional and is a schema example only. It supplies
no hardware evidence.

### If no vendor SVD exists

A missing vendor SVD is not automatically a blocker. If the SVD search completes
and accessible register documentation exists, intake selects the
`author-from-docs` route. Fact extraction must then produce a validated, `ready`
`02-facts` handoff covering the declared register scope before the SVD stage may
author a citation-backed description. The authoring stage represents only what
those citations support.

If the search is incomplete or the required documentation is inaccessible,
intake records the route as `unresolved`; that route is never `ready` and admits
nothing downstream. A supplied SVD instead selects `review-supplied`, but access
to a file does not prove that it applies to the exact target.

## 5. Read the first typed handoff

The following is the real `01-sources.toml` from the committed valid fixture,
reformatted only across lines for readability. The linked file is authoritative
and contains the computed hashes:

```toml
checks = [
  { id = "requested-inputs-accounted", status = "passed", evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-checks.md", sha256 = "5536373a9acfe48f9b85242b4363d714363dd21b3da41a101ea95b5b37e6d801" } },
  { id = "available-content-resolves", status = "passed", evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-checks.md", sha256 = "5536373a9acfe48f9b85242b4363d714363dd21b3da41a101ea95b5b37e6d801" } },
  { id = "local-source-hashes", status = "passed", evidence = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-checks.md", sha256 = "5536373a9acfe48f9b85242b4363d714363dd21b3da41a101ea95b5b37e6d801" } },
  { id = "svd-search-complete", status = "not-applicable", reason = "An accessible fictional SVD was supplied." },
]

[handoff]
schema = 2
stage = "gather-documentation"
status = "ready"
inputs = []
notes = [{ path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md", sha256 = "e908389aaa93cf7b84f221f1d7e25458e98fdb5666546cfb92c1c21b0e9f8993" }]
blockers = []

[scope]
revision = "scope-0123abcd"
decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "aac600f1cabeaecbb41f133f29983ee594fbb8a84233d63c0723646b0876b2e6" }

[coverage]
complete = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]
incomplete = []

[sources]
route = "review-supplied"
documents = [{ source_id = "doc-001", document = "FICTIONAL FIXTURE REFERENCE MANUAL", revision = "fixture-1", format = "utf8-text", source = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/FICTIONAL-MANUAL.txt", sha256 = "894dd80782d29d54fd2c85f49eda6f0905f44ab3cbfdedd7b76429f9c4a3da3e" } }]
cited_notes = []
catalog = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md", sha256 = "e908389aaa93cf7b84f221f1d7e25458e98fdb5666546cfb92c1c21b0e9f8993" }
```

The decisive field is near the top:

```toml
[handoff]
status = "ready"
```

The rest of the document binds that status to a scope revision, coverage,
checks, catalog, source identity, and exact file hashes. A bare claim of success
without those bindings is not this handoff. The normative field definitions are
in [the `01-sources` schema](.opencode/schema/01-sources.md) and
[the common handoff contract](.opencode/schema/handoff-common.md).

## 6. Understand the admission gate

Before consuming the handoff, the specified workflow validates the artifact and
its referenced files. Validator success is necessary, but status still controls
what the next stage may do:

- `ready` admits canonical mutation and normal downstream completion, subject to
  the other gates.
- `partial` admits read-only inspection and fresh disposable candidate work
  only. It forbids canonical replacement, production-file mutation, hardware
  operations, and a downstream `ready` claim.
- `blocked` admits nothing until the named external blocker is resolved.

A `partial` result is recorded progress, not a pass and not necessarily an
unexpected failure. Ask the coordinator to identify the failed or unrun checks,
incomplete coverage, and recorded next actions. Resume the same stage after
those actions become possible; until then, only the permitted inspection or
disposable candidate work may continue. For `blocked`, resolve the named
external identity, source, access, fact, tool, or environment action first, then
return through the coordinator.

This comparison is the admission gate; it is not a model's assessment that the
work looks complete. The common contract defines mutually exclusive predicates
for all three statuses. The coordinator owns the gate and must also reject stale
scope revisions, changed hashes, and invalid upstream lineage.

The demonstrated fixture has `handoff.status = "ready"`, empty incomplete
coverage, empty blockers, and the required intake checks represented. That
proves that the committed artifact tree has the accepted schema shape and
internally consistent references under the validator. It does not prove that a
real source supports a hardware claim, that an agent actually performed the
document search, or that the coordinator applied the gate in a real run.

### Validate the current artifacts

From the root of the Embassy checkout, validate the complete current artifact
set with:

```text
python .opencode/schema/validate.py . --kind all
```

Where state declares an authorized external generation root, add one binding for
each root using
`--root generation:<name>=<absolute-path>`. A successful validation exits 0 and
prints nothing. Exit 1 reports a validation failure; exit 2 reports an
invocation, environment, or read failure. Not running the validator is not a
pass. This is the specified command; this walkthrough has not run it against a
user's Embassy checkout.

### Check the meaning, not only the shape

Later citation validation proves only that an excerpt occurs, under the
validator's bounded matching rules, at the selected location in hash-pinned
source bytes. It cannot prove that the excerpt supports the claim. Before
accepting a hardware claim, inspect the rendered source at every printed locator
and confirm that the excerpt actually entails the claim for the exact target.
The pipeline's independent reviewer is another model, not an external attester;
the reader remains the final semantic backstop.

## 7. Stop at the first durable checkpoint

The first natural stopping point is a validated `01-sources` handoff recorded as
`ready`. Stop after confirming all of the following in your Embassy checkout:

1. `halucinator/docs/<target-id>/SOURCES.md` identifies the exact target and
   accounts for the requested source inputs.
2. Preserved originals exist under `sources/`, and any required derived text is
   under `extracted/`.
3. `halucinator/handoff/01-sources.toml` validates against schema version 2.
4. Its `[handoff]` table contains `status = "ready"`, with empty blockers and no
   incomplete scope coverage.
5. The coordinator reports the intake handoff as admitted rather than merely
   produced.

At this checkpoint, documentation intake is accounted for. No hardware fact has
yet been established merely because intake is ready, no HAL exists merely
because the next stage is admitted, and no board operation is authorized. Save
the current artifact paths and the coordinator's list of anything unverified
before continuing to fact extraction.

## Stopping and resuming

After an interruption, restart with `hal-coordinator`; do not delete a lock or
continue writing into suspect output. The specified recovery procedure
classifies the lock, inventories and hashes partial output, compares it with the
last valid handoff, validates current artifacts, and resumes eligible work in a
fresh candidate or run location rather than in place. A live lock means another
cooperating operation is active, while an ambiguous lock fails closed.

State updates use a generation check and compare-and-swap discipline. A
generation conflict means rereading current state and retrying from that state,
not merging a stale copy. These recovery rules are specified in
[the runtime layout](.opencode/schema/layout.md) and
[the state schema](.opencode/schema/state.md); they have not been exercised in a
real Embassy workflow.
