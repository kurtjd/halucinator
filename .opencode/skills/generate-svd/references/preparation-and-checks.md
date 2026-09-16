# SVD Preparation and Checks

This reference covers register descriptions, not PAC crate generation. Chiptool
can extract SVD data, apply corrections, and check its intermediate representation
(IR) without emitting Rust. The source SVD and cited findings remain necessary:
the extracted YAML is neither a rewritten XML SVD nor a lossless hardware record.

## Artifact locations

Select the SVD root using `AGENTS.md`'s "Artifact storage and handoff" rule.
Find recorded locations in `SOURCES.md` and its linked preparation notes.
Reuse the vendor-and-part `target-id` normalization from the
[source-list storage rules](../../gather-documentation/references/source-list-format.md),
not the basename of a custom documentation directory. Verify the exact part,
core/revision and declared scope before reusing artifacts; names alone do not
establish compatibility.

`sources/` under the SVD root contains authored SVDs or pristine vendor input
copies; `transforms/` contains the ordered correction rules and includes. Treat
these as durable, version-controlled inputs, subject to source-sharing rights,
not disposable output. Preserve gathered originals and source IDs under the
selected documentation root. If an input is referenced rather than copied,
record its provenance and continued-availability dependency explicitly.

For derived output, choose the next unused run label such as `run-001` without
asking, and use its separate `baseline/`, `prepared/`, and `replay/` directories.
Do not reuse a populated run directory or delete files to free one. Create
directories only when needed; do not change ignore rules or automatically stage
files. Existing recorded layouts keep their actual paths and subdirectory names.

Keep review records and citations under `notes/` in the actual documentation
directory from the handoff, which may be a legacy or custom location. Record
the selected SVD root in `SOURCES.md` relative to that source list; in the default
layout that is `../../svd/<target-id>/`. Record any separately authorized
generation repository root explicitly rather than resolving its paths against
the documentation repository. Handoffs name roots and repository-relative paths.

## Reference toolchain

The examples are based on chiptool revision
`e5ab29fff80a7cbe271631dbf7e4233c52dd8e32`, pinned by the
[nxp-pac generator manifest at revision 0c2b68a](https://github.com/embassy-rs/nxp-pac/blob/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/generator/Cargo.toml).
This is an inspected reference, not a request to replace another project's pin.
Check the selected revision's source and CLI before adapting commands. Record
the tool's build/source provenance; its version banner may not identify the
commit. Do not silently install a tool or invent flags to bridge a mismatch.

The reference [CLI](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/main.rs)
separates these operations:

| Operation | Input and output | Use here |
|---|---|---|
| `extract-all` / `extract-peripheral` | SVD to peripheral/block YAML, with optional transforms | Prepare and inspect register descriptions |
| `transform` | YAML IR to separate YAML IR using transform rules | Check corrections to an existing IR input |
| `check` | YAML IR to structural diagnostics | Check the explicit prepared-file set |
| `generate` / `gen-block` / `gen-common` | Register descriptions to Rust | Out of scope |

## Establish the source baseline

Use structured XML tooling and a trusted local CMSIS-SVD schema matching the
source's declared version. Record the schema origin/revision and validator
version. Do not enable external-entity expansion or network entity resolution
for an untrusted input. A missing schema or validator is an unrun check, not a
successful validation.

For example, with `xmllint` and the matching local schema already available:

```sh
xmllint --nonet --noout --schema "$svd_schema" "$svd_input"
```

Here and below, variables stand for established input paths and options, not
defaults to guess. Resolve paths using the selected layout and recorded inputs,
and validate write destinations against their authorized roots and symlinks
before execution. Do not turn that check into an approval question for a usable
default. Record the working directory so relative paths are replayable. Check
and report failures rather than suppressing diagnostics.

Schema validation does not establish applicability or hardware correctness.
Compare effective properties after documented inheritance and array expansion,
not just the leaf XML elements. In the declared scope, check:

| Concern | Evidence and comparison |
|---|---|
| Identity and scope | Exact part/core/revision, peripheral instances, applicable source revisions and errata |
| Addresses and layout | Peripheral bases, address units, register/cluster offsets, widths, arrays and strides, documented aliases |
| Fields | Bit positions and widths, reserved ranges, field arrays, effective access and any side effects |
| Encodings | Every documented legal encoding and its meaning, reserved values, read/write-specific meanings |
| Reset | Effective reset value and mask, unknown bits, reset conditions; no substitution of zero for unknown |
| Access | Read/write permissions, write-once behavior, read side effects and modified-write semantics such as write-one-to-clear |
| Interrupts | Source names, numbers and associations; distinguish peripheral interrupts from core exceptions |
| Completeness | Expected items versus source items, inherited definitions, skipped content, unresolved contradictions |

Compare register summaries with cited field descriptions. Cite the source ID,
document title/number, revision, and section/table/page for each hardware finding
or correction. A vendor-only value stays vendor-only until checked; parser
defaults and a similarly named peripheral are not corroborating evidence.

For authoring, use the same checklist and matching schema. Do not populate a
required device property from habit just to produce valid XML. Optional unknowns
can remain absent with a recorded limitation; required unknowns block authoring
the affected scope. A small reviewed peripheral is a bounded deliverable, not
evidence that the rest of the chip is described.

## Extract and apply corrections

At the reference revision, [shared extraction options and transform loading](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/commands/mod.rs)
provide `--svd`, repeatable `--transform`, and `--namespaces`. Included transform
files run before the containing file's transforms; their order and contents are
part of the reproducible input set. Relative includes resolve against the
containing transform file. Preserve all included dependencies and their hashes.

[Extraction modes](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/commands/extract_all.rs)
are meaningfully different:

- `peripheral` applies transforms separately to each extracted peripheral.
- `block` converts the device to one IR, applies transforms, then extracts
  referenced blocks. Device-wide selectors need this context.
- `--namespaces` accepts `none`, `block`, or `block-with-regs-vals` at this
  revision. Match the selected transform rules and keep the choice fixed
  between baseline, prepared, and replay runs.

Do not rely on defaults to choose the context in which a selector runs. Reuse
existing rule conventions where present; for new rules, choose and record a
consistent naming scheme without designing a Rust crate. `extract-all` visits
the SVD beyond a single reviewed peripheral. Inventory all output, but only
claim review coverage for the declared scope.

Given existing input paths, verified option values, and separate unused output
directories, establish a baseline without transforms:

```sh
chiptool extract-all \
  --svd "$svd_input" \
  --mode "$extraction_mode" \
  --namespaces "$namespace_mode" \
  --output "$baseline_dir"
```

Apply the cited corrections from the original input, not from the last result:

```sh
chiptool extract-all \
  --svd "$svd_input" \
  --mode "$extraction_mode" \
  --namespaces "$namespace_mode" \
  --transform "$transforms_file" \
  --output "$prepared_dir"
```

Repeat `--transform` in the recorded order for multiple top-level files. When
there are no corrections, omit it; do not create an empty correction merely to
fit the example. Preserve baseline diagnostics even when a known defect is
corrected in the prepared output.

For an existing YAML input, the separate
[transform command](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/commands/transform.rs)
can inspect a correction without generating Rust:

```sh
chiptool transform \
  --input "$baseline_yaml" \
  --output "$prepared_yaml" \
  --transform "$transforms_file"
```

This is YAML-to-YAML, not XML-to-XML. A rule requiring device-wide context cannot
be tested on an extracted peripheral file that lacks that context. Do not apply
the same correction through extraction and then again through `transform` in
one pipeline unless that is explicitly the intended sequence.

For each required correction, establish the expected matches before it runs
and the expected effect afterwards. Account for earlier transforms changing
names. Check actual affected items and counts against that expectation, including
unintended matches. Structural validation and a successful process exit do not
prove a corrective selector matched. A required no-match or no-effect rule is
a failed check; classify a rule as conditional only with explicit applicability
evidence. On updated vendor input, an already-fixed defect calls for reviewing
the stale rule, not pretending that a no-op applied a correction.

If a change cannot be expressed at this tool revision, retain the cited finding
and report what remains wrong and what downstream work is blocked. Do not
invent YAML transform variants or alter generated IR by hand. Malformed XML
cannot be repaired by a transform that runs after parsing; return that blocker
instead of modifying the vendor original.

## Structural checks and information limits

Inventory output before checking it. Confirm that expected files and items
exist, then pass an explicit nonempty list to chiptool, for example:

```sh
chiptool check "$prepared_yaml"
```

The [check implementation](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/commands/check.rs)
accepts multiple file paths and fails on reported IR errors. A call with no
files is not evidence. Do not blindly pass a glob that could be empty or select
stale files. Inspect references, ranges, overlaps and enums in the reported
scope. Intentional register aliases need citations and a narrowly documented
check policy; broad `--allow-*` switches can also hide unintended defects.

In particular, successful extraction/checking is not sufficient because:

- The reference SVD loader expands inherited properties but sets
  `ValidateLevel::Disabled`. Extraction is not strict CMSIS-SVD validation;
  retain the independent XML/schema results.
- The [IR register type](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/ir.rs)
  has no reset-value or reset-mask field. Check those against source XML and
  cited findings, and carry any correction as an explicit finding rather than
  claiming that a chiptool transform changed a nonexistent IR property.
- The [SVD conversion](https://github.com/embassy-rs/chiptool/blob/e5ab29fff80a7cbe271631dbf7e4233c52dd8e32/src/svd2ir.rs)
  maps write-once to write and read-write-once to read-write. The field IR also
  lacks the full SVD access/side-effect model. Preserve these facts separately
  and assess the impact on the intended consumer; do not claim they are enforced.
- Extracted block YAML contains blocks, fieldsets, and enums, not the complete
  device record. It cannot stand in for peripheral bases or interrupt
  associations. Keep those in the source SVD and cited findings for the later
  stage; do not assemble metapac metadata here.
- Warnings or skipped definitions can leave structurally valid but incomplete
  output. Compare the expected source inventory with the extracted inventory,
  including inherited definitions, arrays, and read/write-specific encodings.

Treat an understood representation omission differently from an unresolved
hardware fact or an unsupported required correction. Document the omission and
preserve its evidence; block any requirement that needs a representation or
guarantee not provided. Neither Rust generation nor a hardware run is needed
or permitted to complete these checks in this skill.

Replay from the same original/authored SVD, transform/include bytes, tool
revision, modes, and options into a new output directory. Compare both the file
inventory and contents with the prepared result. Record unexplained differences
as failures; do not delete unrelated files, hand-edit outputs, or describe an
unrun replay as reproducible.

## Preparation record and handoff

Keep the record in the documentation directory's `notes/` and register its path
and the selected SVD artifact directory in `SOURCES.md`. Reuse an existing record
for the same scope and location, preserving earlier results when inputs change.
No second source catalog or new machine-readable schema is required. Include:

1. **Scope and roots:** target/core/revision, reviewed and excluded peripherals,
  source repository root, actual documentation and SVD roots, and the run's
  baseline/prepared/replay paths. Record whether each root was explicitly
  supplied, reused, or defaulted. Resolve each relative path against its named
  root, not the agent's working directory.
2. **Inputs:** source IDs/revisions/hashes, original or authored SVD path,
   ordered transforms and includes with hashes, and cited findings. Record
   unknown hashes/revisions as unchecked, never fabricated.
3. **Review and corrections:** per-item source citation, baseline value or
   structure, expected correction, selector context/matches, observed result,
   and unresolved facts. Distinguish source-verified from vendor-only entries.
4. **Checks:** schema origin/version, exact tools/revisions, working directory,
   commands/options, output inventory, results and warnings, replay comparison,
   and unrun checks. Separate XML, source-fact, and IR validation evidence.
5. **Handoff:** reproducible input paths, optional prepared YAML paths,
   facts absent from IR, downstream impact, coverage gaps, readiness for the
   declared scope, and next action through **hal-architect**. No Rust PAC or
   hardware behavior has been verified by this stage.

## Skill acceptance scenarios

Exercise the workflow on a bounded, source-backed example when the tools and
sources are available. Record the exact fixture provenance and which checks
were actually executed. A procedural fixture is not evidence about real silicon.

| Scenario | Required outcome |
|---|---|
| Applicable supplied SVD, no defect in reviewed scope | No gratuitous correction; preserved original; scoped checks and handoff |
| Supplied SVD with a documented correction | Cited transform matches the intended input, changes the intended items, and preserves unrelated items |
| No suitable SVD, complete cited findings | Authored XML for only the declared scope; schema and fact checks; no guessed required properties |
| Missing citation, conflicting sources, or wrong part | Explicit affected scope and return to hal-architect; no invented hardware value |
| Malformed XML or unsupported correction | Blocker before the unsupported operation; no vendor overwrite or fabricated transform |
| Required transform matches nothing or too much | Failed effect check even if the tool exits successfully |
| Empty/missing output or skipped expected item | Failed inventory check; no vacuous success from checking zero files |
| Reset/access fact absent from IR | Source comparison and explicit limitation; no claim the IR preserved or verified it |
| Source hash/revision changes on resume | Preserve old source IDs; invalidate and rerun affected checks from the new input |
| Tool, schema, or permission unavailable | Review may continue, but required executable checks remain unrun and readiness is partial/blocked |
| Missing source/target/scope handoff | Request only the missing evidence through hal-architect; an absent SVD root alone is not a blocker |
| New target, no supplied or recorded SVD root | Use `halucinator/svd/<target-id>/` and a fresh derived run without asking; no PAC/Cargo setup |
| Recorded custom or legacy roots | Reuse their actual paths and subdirectory names; no silent move to defaults |
| Explicit override with existing artifacts | Select the override for new work, preserving old records and inputs; migration requires a separate request |
| Conflicting records or unsafe/inaccessible destination | Ask about that specific conflict; no overwrite, permission workaround, or guessed external root |
| Existing derived run | Select a fresh run label; preserve all earlier baseline/prepared/replay output |
| Identical inputs replayed | Matching inventories and contents; original bytes and unrelated changes preserved |
