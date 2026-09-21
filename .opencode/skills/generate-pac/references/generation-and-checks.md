# PAC Generation and Checks

Use this reference with `generate-pac`. It defines the generation contract and
checks, not a fixed vendor schema or a replacement for live source inspection.
Reuse the checked [SVD preparation handoff](../../generate-svd/references/preparation-and-checks.md)
and the downstream [foundation coverage contract](../../scaffold-hal/references/scaffold-record.md#provenance-and-foundation-coverage).

## Project paths and ownership

Follow `AGENTS.md`'s "Artifact storage and handoff" and "PAC placement" policy
for layout, path selection and safety. Reuse preparation's selected PAC project
and SVD inputs; select metadata, generator and crate locations under that policy.

For new work, generation runs use `derived/pac/<target-id>/<run-id>/` inside the
selected project, with separate `candidate/` and `replay/` directories. Choose
the next unused run label such as `run-001` at the recorded or default run root;
do not reuse a populated run or clear it for convenience.

Before commands, inspect the full write/delete footprint, including temporary
files, Cargo outputs and configured target directories, and apply the shared
path-safety rules. Reject output paths that equal or contain durable inputs or
documentation. Candidate, replay and canonical crate outputs must not overlap
or sit inside one another's cleanup directories.

Record input/output ownership and the live destination's pre-run state before
generating. Preserve dirty and untracked work without demanding a clean tree,
commit or stash; unresolved overlaps block integration.
Use file-edit tools for authored metadata, generator/setup inputs and records;
generated files come from the recorded generator, not manual shell rewrites.

## Inspected reference implementation

The reference is `nxp-pac` revision
`0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b`, used by the inspected
[MCXA manifest](https://raw.githubusercontent.com/embassy-rs/embassy/f8506dc5f0022ccb62c75bd2707da913c6979375/embassy-mcxa/Cargo.toml).
Its normal PAC dependency enables runtime support; its build dependency disables
defaults and enables metadata. MCXA256 and MCXA577 take the metapac route.
Inspect the live consumer and selected project for the actual run; these are
reference facts, not a command to change another project's dependency pin.

| Concern | Inspected source and behavior |
|---|---|
| Project separation | [Repository layout](https://github.com/embassy-rs/nxp-pac/tree/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b) has sibling `data/`, `generator/`, and consumable `nxp-pac/` |
| Chip registration | [ChipDescription and CHIPS](https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/generator/src/lib.rs) identify chip, cores, metadata name and metapac route |
| Dispatch | [generate and generate_chip](https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/generator/src/commands/generate.rs) export shared blocks, read chip JSON through `metadata::generate`, then assemble each selected core |
| Shared blocks and chip assembly | [generate_meta_peripherals and generate_core](https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/generator/src/metapac.rs) use chiptool `GenBlock` and `GenCommon`, emit shared modules, chip instances, interrupts, vectors and linker support |
| Consumer features | [PAC manifest](https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/nxp-pac/Cargo.toml) separates `pac`, `rt`, `metadata`, `defmt` and chip features |
| Chip selection | [PAC build script](https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/nxp-pac/build.rs) requires exactly one chip and adds runtime link-search for that chip |
| Backend pin | [Generator manifest](https://github.com/embassy-rs/nxp-pac/blob/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/generator/Cargo.toml) pins chiptool `e5ab29fff80a7cbe271631dbf7e4233c52dd8e32` as a library |

The [generator README](https://github.com/embassy-rs/nxp-pac/tree/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/generator)
documents these commands from that project's root:

```sh
cargo run -p generator -- --help
cargo run -p generator -- generate MCXA577
```

These are reference-specific examples, not commands to run blindly in Embassy
or against a live output crate. Read the chosen source/help and establish a
safe isolated layout or an explicit output-root implementation first. Record
the working directory and all actual options. The reference also requires an
external formatter; check the selected toolchain and formatter instead of
installing or upgrading tools automatically.

Important behaviors in the inspected implementation:

- `generate_meta_peripherals` processes all non-raw peripheral YAML, even when
  a single chip was selected. A chip flag does not bound every output file.
- Shared peripheral output and the selected chip directory are cleaned during
  generation. Replaying directly into a populated project can destroy work.
- Missing/invalid block mappings or absent YAML can cause peripherals to be
  skipped with warnings. Chip module emission can also skip an instance without
  an address. A zero exit status is not completeness evidence. Check exported
  metadata against the Rust API as well as against independent expectations.
- The inspected metapac routines emit source/runtime artifacts, not every crate
  support file. Do not claim that they regenerate the manifest or build script.
  For a new toolkit project, supply reproducible packaging/setup templates with
  the generator. Reused projects retain their documented authored/output
  boundaries; preserve authored support files instead of treating them as
  disposable generated output.

The [peripheral-source README](https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/data/metadata/peripherals/README.md)
allows curated YAML as authoritative metapac input, including manual changes.
That is not permission to hand-edit this toolkit's extracted IR. For new work,
reproduce promoted shared-block inputs from the checked SVD/transform pipeline.
For existing curated inputs, establish provenance, applicability and the actual
source boundary; do not silently relabel a generated file as authoritative.

Chiptool's [direct generate command](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/commands/generate.rs)
loads an SVD, applies transforms and emits Rust plus linker support. It does not
by itself establish the shared-IP metadata and complete packaging contract
above. Reuse an applicable existing route, but do not substitute this command
for metapac assembly merely because it produces compilable Rust.

## Establish reproducible inputs

Require the validated, `ready` `03-svd` handoff, the coordinator-approved scope
decision and the coordinator-owned consumer requirements. A previous crate, HAL
scaffold or `SCAFFOLD.md` is not a prerequisite. Missing required preparation
evidence is a blocker, not a reason to infer registers from emitted Rust.

Admission uses the producer's field names. Every row below names a field that
`generate-svd` actually publishes, so an omission is detectable rather than a
heading the consumer invented:

| Admission concern | Consumed field | Required evidence before generation |
|---|---|---|
| Route | `svd.route` | Equals the upstream `sources.route`; the route-applicability review was obtained |
| Source | `svd.source` | The exact original or authored SVD FileRef, with a matching recorded byte identity and an applicable revision |
| Recipe | `svd.transforms`, `svd.includes`, `svd.extraction_mode`, `svd.namespace_mode` | Ordered corrections and includes, or an empty ordered array when there are no corrections, plus the exact modes used in baseline, prepared and replay |
| Prepared output | `svd.prepared_manifest` | Present with a matching recorded identity when prepared YAML is reused; otherwise reproduced from the checked inputs |
| Representation limits | `svd.representation_limits` | Every source-only fact and its consumer impact is recorded; no required guarantee is silently treated as represented |
| Unresolved facts | `svd.unresolved_facts` | Empty, because a `ready` preparation has none |
| Evidence | `checks.*` | Every canonical `03-svd` check is `passed`, or `not-applicable` with a reason, for these exact inputs |
| Lineage | `handoff.inputs`, `scope.revision`, `scope.decision`, `coverage.complete`, `coverage.incomplete` | The declared scope matches the current coordinator-owned decision, with no silently dropped required item |

Scope, chip, target, runtime and metadata requirements are **not** in `03-svd`.
Read them separately from coordinator-owned state, together with the PAC project
and SVD input roots. Missing board facts block only the requirements that depend
on them.

Missing or stale admission evidence returns through `hal-coordinator` before
emission. A new generator or crate path can still be selected by the normal
default rules.

Inventory and identify all effective inputs: original/authored SVDs, transforms
and included files in order, preparation modes, shared-block sources or their
promotion recipe, chip metadata, generator code, packaging templates, build
configuration, dependency resolution and tools. Hash actual bytes, including
relevant dirty/untracked inputs. A Git HEAD or version banner alone does not
identify them. Preserve checked source IDs and source-sharing restrictions.

For an existing applicable generator, reuse its schema, backend pin and layout.
For a new project, author the minimal generator/setup layer for the approved
scope using chiptool's backend. Read the live schema and consumer APIs before
choosing metadata fields or Cargo features. Prefer metapac structure without
registering hypothetical chips or copying an NXP hardware/runtime assumption.
Missing backend/runtime support is a named dependency to resolve through
hal-coordinator, not a reason to guess architecture-specific code.

Use structured XML/YAML/JSON/TOML tooling for their respective inputs. Preserve
the checked preparation pipeline: no skipped transforms, duplicate correction
application, unrecorded namespace changes or manual edits to extracted YAML.
If promotion needs naming or scope projection, encode it reproducibly, identify
the expected matches and verify retained content against the checked result.
Hardware description corrections return to `generate-svd`; metadata assembly
and emission defects are repaired here at their authoritative source.

Establish packaging as well as Rust emission. Cover crate identity, implemented
chip features, module exports, dependencies, target/runtime integration and the
host metadata interface required by the consumer. Keep new setup templates in
`generator/`, outside emitted output. Derive Cargo membership, targets, versions,
lockfile handling and build configuration from the actual checkout. Do not
invent a package license, upstream URL, release revision or publication status.
The local dependency path is a bring-up arrangement, not an upstream acceptance
claim. Do not vendor an existing upstream PAC fork under a new path to evade
the fork policy.

## Expected inventory and metadata

Write the expected inventory before generation using cited findings and checked
preparation, independently of the generator's own success list. Distinguish
the selected target's coverage from unrelated support in an existing project.
Required metadata may include supporting dependencies, but it is not permission
to advertise extra peripherals or expand the coordinator's milestone.

| Concern | Required comparison for the declared scope |
|---|---|
| Identity and selection | Exact part/core/revision, source applicability, implemented chip feature and consumer targets |
| Block reuse | Actual compatible peripheral IP, version and block mapping; similarity of names alone is insufficient |
| Device instances | Every required peripheral name, base address, block/type path and association is present in both Rust and exported metadata |
| Register layout | Offsets, widths, alignment, arrays/strides, clusters and documented aliases match expanded source expectations |
| Fields and values | Bit ranges, effective access, legal encodings, reserved patterns and generated accessor/value types agree with the source-backed contract |
| Interrupts/runtime | Source names, numbers, peripheral associations, reserved vector slots and runtime/link artifacts are consistent with the actual architecture |
| Foundation metadata | Every clock/reset/init and required supporting-subsystem fact consumed by the HAL build is available; optional unused data stays explicitly out of scope |
| Output scope | Every required item exists; newly emitted APIs and metadata do not silently add excluded support; unrelated existing chips remain intact |

A metadata entry without an address or valid block link is not an implemented
peripheral. Unresolved required facts block assembly; unsupported optional
fields remain omitted and recorded, not populated with zeros or guessed
values. Runtime requirements outside the supplied evidence/scope return to the
coordinator for a decision. Do not truncate a required vector table to hide a gap.

Inventory an explicit nonempty file set before structural or compile checks.
Compare source/prepared inventories with emitted Rust and chip metadata using
structured or Rust-aware tooling where available. Focused compilation probes
can assert required public paths/types; a few successful probes or textual
matches do not replace the full inventory comparison. Investigate all warnings,
skips, missing files and unintended selector matches.

### Representation limits

Retain the preparation reference's information-limit assessment. At the cited
chiptool revision, block YAML is not a complete device description and lacks
reset values/masks and full access/side-effect semantics. Check those facts
against source XML and cited notes; do not claim that generated setters enforce
write-once or write-one-to-clear behavior merely because they compile.

Distinguish an understood source-only fact from an unresolved hardware fact or
a required guarantee that the selected representation cannot supply. Document
the first with its consumer impact; block the latter cases. Do not demand a
reset accessor the generator does not provide or substitute a default zero.
Any legal-value test must reflect the actual API: not all reserved encodings
round-trip, and reads and writes can have different meanings.

## Check applicability

Record the check set and expected outcomes before running it. These are gates,
not a menu from which to select only the checks that pass:

| Check | When required |
|---|---|
| Input identity, preparation admission and source integrity | Every run |
| Expected/prepared/Rust/metadata inventory and scope comparison | Every run, for all declared items and consumer mappings |
| Representation-limit and consumer-impact assessment | Every run, including an explicit result when no relevant omission exists |
| Target builds and public API probes | Every advertised in-scope target/runtime configuration |
| Host metadata build and API probe | Whenever build-time metadata is a consumer requirement |
| Missing/incompatible chip-selection checks | Wherever the selected feature policy rejects those combinations; no invented chip features |
| Pure host tests | For authored/changed pure generation or configuration logic and claimed value/layout contracts |
| Formatting and lint | As required by the live repository policy for the touched surfaces |
| Exact generation/setup replay and final output identity | Every run |
| Final-path consumer builds | Every required consumer configuration after materialization |

Record each check as passed, failed, unrun, or not applicable with a concrete
reason. Missing tools or permissions do not make a check inapplicable. No
required failed or unrun check may be waived to claim readiness; resolve it
and rerun, or return partial/blocked. Only hal-coordinator can approve a scope
change, and the revised scope needs its own complete evidence.

## Builds and pure checks

Derive commands from the selected project and live repository policy. Verify
available tools and permissions first; missing tools, target support or required
formatter checks stay unrun and prevent readiness. Do not install or upgrade
them automatically. Give commands an explicit cwd, manifest, target and feature
set, and record any Cargo configuration that changes their meaning.

For a candidate with established paths and feature lists, the check shape is:

```sh
cargo check --manifest-path "$pac_manifest" \
  --target "$rust_target" --no-default-features --features "$target_features"
```

`target_features` contains the actual chip and register/runtime features the
consumer needs. Build every advertised in-scope option, including runtime and
optional formatting support when claimed. Compile focused probes that use the
required public register and interrupt APIs, not just an empty dependent crate.

When build-time metadata is part of the contract, also check its host-only
configuration and compile a probe using the required public metadata interface:

```sh
cargo check --manifest-path "$pac_manifest" \
  --target "$host_target" --no-default-features --features "$metadata_features"
```

Get `host_target` from the selected compiler's `rustc -vV`, not the MCU target
or a remembered machine. An inherited Cargo default target can otherwise make
an apparent host check cross-compile instead. The metadata feature list must
include the real chip selection where required. In the MCXA reference, metadata
and runtime are separate consumers; passing one does not verify the other.

Test missing and incompatible chip selections according to the actual feature
policy. Verify the intended diagnostic, not any nonzero exit from a missing
tool or unrelated build error. Do not use indiscriminate `--all-features` for
mutually exclusive chips or invent a second chip just for a negative test.
Mark an inapplicable combination as such with a reason.

Run the repository-required formatting and lint checks for touched generator,
setup and generated code using the selected tools and applicable policy. Test
pure layout/encoding/configuration logic on the host where it exists; exhaust
small legal domains and check invalid/reserved boundaries where the API defines
them. Never dereference MMIO, call hardware initialization, or require a board
for a host test. Do not add universal reset round-trip assertions to an API that
does not model resets.

These are PAC software checks. `cargo check` is not a target link test or proof
that interrupt vectors execute. The scaffold stage's source-blind tester owns
the actual firmware link and bench instructions; do not pull that work into
PAC generation to compensate for missing software evidence here.

## Replay and final integration

Record source, generator, setup, metadata, dependency and toolchain identities
before the run, then verify inputs remained unchanged. Include actual relevant
dirty/untracked bytes or an equivalent content snapshot, not only HEAD. Do not
change inputs during generation, a check, or review. On change, preserve old
evidence, invalidate dependents and rerun before claiming readiness.

Replay the complete recorded generation/setup pipeline from the same durable
inputs into a second unused output directory. Reproduce promoted derived
blocks through their recorded preparation recipe when needed; do not use the
candidate Rust as input. Compare both the complete generated file inventory and
file contents, including metadata, crate support and runtime/link artifacts.
Build caches are not generated PAC deliverables and belong outside that
comparison. Filesystem modification times are not file contents, but timestamps,
paths or other nondeterministic text embedded in generated files are bytes and
must match. Any inventory or byte difference fails replay, even with a known
cause. Do not add post-hoc exclusions or hand-normalize cosmetic differences.
Fix determinism at the generator/input/tool boundary and rerun.

The expected output set must be nonempty and complete in both runs. Failed
generation cannot leave stale prior files satisfying the inventory. Retain
failed run evidence; do not delete previous successful outputs or overwrite
their notes to make a replay look clean.

After all candidate checks and replay succeed, materialize only owned output
through the generator/setup process at the selected canonical crate path.
Before replacing anything, compare the live destination with its recorded
pre-run state, including dirty/untracked files and edits made during candidate
verification. Do not discard a user edit because it is in generated output.
Reproduce an understood intended change in authoritative inputs and rerun the
checks, or return the conflicting paths and diff to hal-coordinator for an
ownership/intent decision. Never merge such edits by hand into emitted code.
Remove obsolete generated files only when ownership and replacement
are established; never perform broad cleanup of the shared project's `data/`,
`generator/`, documentation or unrelated supported chips. Unresolved conflicts
block integration. A failed candidate must not replace a previously verified
crate.

Verify that integrated files match the checked candidate, then rerun
location-sensitive consumer builds at the final path. Workspace membership,
relative dependencies and Cargo configuration can differ from staging even
when source bytes match. Record the final state and paths for review. No
automatic commit, publish, flash, target execution or HAL dependency edit is
part of integration.

## Generation record and handoff

The generation record is not a soft convention. Its path is the exact
deterministic `<documentation>/notes/PAC.md`, resolved against the documentation
root recorded in state, and it is the **first** entry of `handoff.notes` in
`halucinator/handoff/04-pac.toml`. The schema fixes it at
[`04-pac.md`](../../../schema/04-pac.md); the ownership class is
`svd-pac-notes`, owned by `hal-svd`. Reuse the same-scope record on a rerun and
disambiguate conflicting records instead of replacing them.

Register the stable artifact locations and the record link in `SOURCES.md`
through the catalog delta that `hal-coordinator` has `hal-integrator`
materialize. Exact run paths and check evidence belong in the record and the
typed handoff, not in parallel fields in the source catalog. Preserve prior
evidence and record what supersedes it; create no second source list.

The record carries the human-readable detail; the typed handoff carries the
machine-readable contract. Keep the two consistent:

| Handoff field | What the record must support |
|---|---|
| `pac.crate_manifest` | the canonical crate manifest actually built and reviewed |
| `pac.package`, `pac.revision` | crate identity, with the tagged `revision` value or `workspace` |
| `pac.cargo_chip_feature` | the implemented chip feature required by the consumer |
| `pac.runtime_features`, `pac.metadata_features` | the advertised in-scope feature sets that were built |
| `pac.rust_compilation_target` | the exact target triple the consumer compiles for |
| `pac.source_ids`, `pac.cited_notes` | the checked source IDs and the cited preparation notes |
| `pac.temporary_fork` | false in a ready PAC; a fork pin is a bring-up aid, never an acceptance claim |
| `pac.foundation` | one entry per coordinator-owned foundation requirement, exactly partitioning them, each `covered` with evidence or `missing` |
| `checks.*` | one entry per canonical check, with its evidence FileRef or its `not-applicable` reason |
| `coverage.*`, `scope.*`, `handoff.inputs` | the declared scope and the exact `03-svd` bytes consumed |

Include in the record:

1. **Scope and consumers:** exact target/core/revision, approved functionality,
   required foundation dependencies, exclusions, roadmap link, chip features,
   compilation targets, runtime and metadata contracts. Record an unestablished
   fact and the requirement it prevents rather than guessing it.
2. **Roots and ownership:** named working/authorized repositories, documentation
   and source-list paths, PAC project, SVD inputs/transforms, metadata, generator,
   canonical crate and candidate/replay paths. Record explicit/reused/default
   selection and generated-versus-authored ownership. Source-list links are
   relative to `SOURCES.md`; downstream handoffs use repository-relative paths
   or paths relative to an explicitly named authorized root.
3. **Provenance:** preparation-record path and readiness, original/authored input
   identities, ordered transforms/includes, promoted block recipe, cited facts,
   generator/templates, dependency and tool/formatter revisions, actual hashes
   and applicable license/sharing limitations. Hardware citations keep document
   title/number, revision, and section/table/page in addition to source IDs.
4. **Expected and generated delta:** checked inventories and API/metadata
   changes, required foundation coverage, excluded/unrelated support, warnings,
   representation limits and downstream breaking changes. A generated metadata
   list alone is not the expected inventory.
5. **Evidence:** observed time, tested-state identity, exact command, cwd,
   target/features/options, outcomes, artifacts, replay comparisons, final-path
   builds and unrun checks. Never fabricate timestamps, hashes or successful
   checks. Invalidate only dependent evidence when inputs change.
6. **Result and gate:** the stage status `ready`, `partial` or `blocked`;
   blockers with owners/actions, review request/findings/recheck disposition,
   and outstanding bench evidence. Software readiness does not bypass the
   coordinator-dispatched independent review over `pac.crate_manifest`:
   Only review.verdict=ready accepts; ready-with-fixes and not-ready do not.
   Unresolved required findings prevent closure even when every software check
   passes.
7. **Scaffold handoff:** actual dependency crate path and identity, chip and
   runtime/metadata features, target, required API/metadata locations, complete
   checked foundation coverage, source IDs, cited notes and remaining gaps.
   Missing in-scope foundation items block all scaffold implementation; an
   unrelated deferred peripheral does not. For the default HAL location the
   path dependency is `../halucinator/pac/<vendor>/<vendor>-pac`.

State explicitly that no HAL implementation, publication or hardware operation
was performed. A freshly generated local PAC is not a vendored personal fork,
but placing a fork inside the checkout does not remove the fork restriction.
Upstream acceptance and publication readiness remain separate decisions.

## Skill acceptance scenarios

Validate the procedural contract separately from actual PAC generation. When
an authorized bounded fixture and tools are available, record its provenance
and execute generation, both required consumers and replay. Otherwise report
those executable checks as unrun; a scenario walkthrough is not a real-chip
test result. No fixture may invent hardware facts to pass a stage gate.

| Scenario | Required outcome |
|---|---|
| Checked preparation, no corrections needed | No gratuitous transform; complete bounded crate, required consumer builds and matching replay |
| First run, no generator or crate | Establish minimal source-backed tooling/setup in the selected project; no separate repository prerequisite |
| New target with no supplied/recorded paths | Reuse preparation's default project; data, generator, crate and run outputs remain under it |
| Additional chip in an applicable PAC project | Reuse shared tooling and verified IP; preserve unrelated existing support and scope limits |
| Legacy/custom/authorized external locations | Reuse named roots and actual paths; no silent migration or assumed sibling checkout |
| Explicit override with earlier artifacts | Select new work without moving, deleting or overwriting the earlier artifacts |
| Missing target, source list, scope or preparation handoff | Return precise missing fields through hal-coordinator; no guessed previous target |
| Source/tool/metadata bytes change on resume | Preserve records, invalidate dependent preparation/checks/review and rerun |
| No block mapping, missing YAML or missing base address | Failed independent inventory even when generator warns and exits successfully |
| Empty output, dropped inherited/array entry or missing accessor | Failed completeness check even when emitted Rust compiles |
| One chip selected but extra shared outputs emitted | Check actual file/API/metadata scope; restrict new output reproducibly without deleting unrelated prior support |
| Required metadata and Rust instances disagree | Failed consumer contract; repair authoritative metadata or generator, not emitted Rust |
| Reset/access fact omitted by the IR | Preserve cited source meaning and assess consumer impact; do not claim absent enforcement or invent reset zero |
| Required fact/guarantee cannot be represented | Block that requirement through hal-coordinator; no raw-register or wrong-architecture workaround |
| Missing tool, formatter, target or permission | Named unrun check/blocker; no silent install, upgrade or fabricated success |
| Target PAC builds but host metadata fails | The stage cannot be `ready` when both consumers are required; repair generator/setup inputs and rerun |
| Missing/incompatible chip selection | Expected feature-policy diagnostic; unrelated failure is not a passing negative test |
| Destructive generator, unsafe path or overlapping roots | Stop before unsafe writes; use authorized isolated output, not cleanup of live inputs |
| Dirty generated files or unrelated files in output | Preserve and reconcile ownership before integration; no commit/stash demand or blind overwrite |
| Replay differs in inventory or bytes | Failed reproducibility; retain evidence and repair deterministic generation inputs/tooling |
| Candidate passes but final-path build fails | The stage cannot be `ready`; resolve location/workspace setup through its source, then recheck final state |
| Missing foundation item versus unrelated excluded peripheral | First blocks scaffold implementation; second does not expand scope or block the declared scope |
| Software checks pass but required review remains | Return for hal-coordinator's dispatched independent review; no automatic stage closure or scaffold invocation |
