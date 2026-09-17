# Documentation Workspace and Source List

Keep documentation in the working repository, not a temporary folder. The
Markdown source list and later research notes may not be reconstructable.
There is no JSON schema or separate generated index to maintain.

## Location

Use `AGENTS.md`'s "Artifact storage and handoff" rule to select the
documentation directory, defaulting to `halucinator/docs/<target-id>/` for
a new collection. Check recorded locations against the target and board setup.

Load handed-off source lists and records before choosing a new location. When
no location is recorded in the handoff, check for an existing `SOURCES.md` at
the default and at the former `halucinator-docs/<target-id>/` location before
creating one. Resume an unambiguous matching record where it already lives.
If records conflict or leave the choice ambiguous, ask which to resume; do not
merge them or choose by folder name alone. Do not scan unrelated targets for a
replacement. An explicit override does not authorize moving or overwriting
previous records or originals; migration requires a separate user request.

- `target-id`: vendor and exact part number, lowercased, with runs of characters
  other than ASCII letters/digits replaced by `-` and edge hyphens removed.
  Separate the vendor and part number with `-` before normalization. If the
  result is empty, request an explicit directory. Preserve the original
  identifiers verbatim in the source list.
- Check the recorded identity before reuse; a normalized name is not proof of
  identity. Resolve collisions or distinct board setups with a separate
  directory in the repository instead of overwriting a record.

Use the default without an extra configuration interview. Resolve paths from
the repository root, including symlink targets and existing parent directories;
the chosen location must remain inside that repository. If it cannot be used,
ask for another in-repository directory rather than storing artifacts elsewhere.

```text
halucinator/docs/<target-id>/
  SOURCES.md
  sources/
    doc-001/
      <original-filename>
  extracted/
  notes/
```

`extracted/` and `notes/` are created later by hal-datasheet, when it converts
and analyzes documents. Intake need not create empty directories. Use source
IDs in derived filenames to distinguish revisions. Paths inside `SOURCES.md`
are relative to that file, and handoff paths are relative to the repository
root, so moving the checkout does not change the documentation location.

`generate-svd` and `generate-pac` select their artifact locations under
`AGENTS.md`'s shared storage policy. Intake does not create their directories
or relocate collected SVDs; preserve originals and source IDs. Later stages
record stable locations and link their preparation/generation notes here.

## Recording Rules

- `SOURCES.md` is the durable intake record. Update it with file-edit tools.
  Keep it alongside the source documents and research notes in the repository.
- Use stable IDs such as `doc-001`; never recycle an ID for different bytes or
  a different revision. Keep old records when the selected revision changes.
- Paths to stored material are relative to `SOURCES.md`. A reference-only
  original may have an absolute local path, explicitly marked as such. Do not
  mistake that machine-specific path for portable provenance.
- Record unknown fields as `unknown`, not plausible defaults. Distinguish
  user-reported metadata from metadata checked against the source. Each source
  has its own availability and applicability, as defined in the skill.
- Later hardware notes cite a source ID, title/document number, revision, and
  section/table/page. Distinguish printed page labels from PDF page indexes
  where they differ. An absolute filesystem path alone is not a citation.
- Keep later HAL code/documentation citations meaningful independently of
  local paths. SVDs and transforms are durable generation inputs, separate from
  research notes; gathered documents do not substitute for versioned inputs.
- Preserve later-stage records on intake reruns. The owning stage fills the
  unselected stable-location and note fields. Exact run paths and check evidence
  belong in stage notes and handoffs, not parallel fields in this catalog.
  Translate catalog-relative paths to the named roots required by the shared
  handoff policy.

## Source List Template

Replace placeholders with collected information. Repeat the source record for
each document, revision, or SVD. Maintain the coverage table even for inputs
that could not be obtained. For an absent board, record that context instead
of inventing a board or declaring its schematic nonexistent.

```markdown
# Documentation Sources

## Target

- Documentation directory: <repository-relative path>
- Vendor: <exact name>
- MCU part: <exact part number>
- Package: unknown
- Silicon revision: unknown
- Board name/type: unknown
- Board revision: unknown
- Last updated: <date>

## Hardware Setup Context

- Probe/programmer and debug interface: unknown
- Current loader/tool and version: unknown
- Host OS and local/remote board access: unknown
- Current firmware-loading procedure: unknown
- Debug/boot/RAM-loading documentation: unknown
- Evidence: user-reported; no tool compatibility or hardware operation verified

## Source Coverage

| Input | Availability | Source IDs | Applicability or gap |
|---|---|---|---|
| Reference manual | not provided | none | unknown |
| Errata | not provided | none | unknown |
| Datasheet | not provided | none | unknown |
| Board schematic | not provided | none | unknown |
| Board guide/connectors/jumpers | not provided | none | unknown |
| Supporting documents | not provided | none | unknown |
| Vendor SVD | not provided | none | unknown |
| Loader/debug/RAM-loading instructions | not provided | none | unknown |

## Source Records

### doc-001

- Kind: <reference manual, schematic, SVD, etc.>
- Title and document number: unknown
- Revision and publication date: unknown
- Availability: not provided
- Covered parts/packages/boards/revisions: unknown
- Applicability to this target and evidence: unverified
- Origin: <user supplied, official vendor, or community candidate>
- Source page and download/repository URL: unknown
- Pack/SDK version, repository revision, and member path, if applicable: unknown
- Local path: <path relative to SOURCES.md, or explicit reference-only path>
- SHA-256 of local bytes: not checked
- Retrieved/accessed: unknown
- Metadata checked against: unknown
- Known access/sharing restrictions: unknown
- Caveats or superseded source IDs: none recorded

## Search Log

| Input sought | Date | Sites/repositories checked | Outcome or limitation |
|---|---|---|---|

## Gaps and Handoff

- Intake status: in progress
- SVD starting point: unresolved
- PAC project root: not selected
- SVD artifact directory: not selected
- SVD preparation note: none yet
- PAC generator directory: not selected
- Generated PAC crate directory: not selected
- PAC generation note: none yet
- Next SVD action and source IDs: unknown
- Hardware-analysis prerequisites: unknown
- Hardware-setup questions for hal-architect: unknown
- Missing/uncertain inputs, affected work, and next actions: <list>
- Existing cited findings: <relative notes paths, or none yet>
```
