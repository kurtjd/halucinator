# Documentation Workspace and Source List

Keep documentation in the working repository, not a temporary folder. The
Markdown source list and later research notes may not be reconstructable.

`SOURCES.md` is the durable human record; it is **not** the machine-readable
contract. That contract is the typed `01-sources` handoff at
`halucinator/handoff/01-sources.toml`, defined by
[`01-sources.md`](../../../schema/01-sources.md) and
[the common handoff contract](../../../schema/handoff-common.md), and it is what
every downstream stage admits against. The catalog carries prose, provenance and
the search log; the handoff carries `sources.catalog`, `sources.route`,
`sources.documents` - one entry per source binding its `source_id` to a
`document` title, a `revision`, a `format` and a hash-pinned `source` FileRef -
`sources.cited_notes` and the four canonical checks. Keep the two consistent and do not invent a third index.

`SOURCES.md` is ownership class `sources-catalog` and is materialized by
**hal-integrator**. `gather-documentation` authors its delta and routes
materialization through **hal-coordinator**.

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
- Omit a field nobody supplied rather than filling it with a plausible default
  or a sentinel word. Optional means key absence; known-empty means an empty
  collection; there are no sentinel strings such as `unknown`, `not provided`,
  `none`, `not checked`, `none recorded`, `not selected`, `none yet`,
  `unverified` or `in progress`. A gap that matters is a Source Coverage row and
  a Search Log entry, both of which say what was attempted; a field whose value
  is the word for missing reads as data and is not data. Distinguish
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

Replace placeholders with collected information, and **delete any line whose
value was never established** rather than filling it with a sentinel. Repeat the
source record for each document, revision, or SVD. Maintain the coverage table
even for inputs that could not be obtained: a coverage row records an attempt,
which a missing field cannot. For an absent board, record that context instead
of inventing a board or declaring its schematic nonexistent.

Availability uses exactly one of `not-searched`, `located`, `available`,
`inaccessible`, `not-found` or `confirmed-unavailable`, each of which is a
classification of the search, not a null. Source IDs and note paths are lists:
an empty list is written `[]`.

```markdown
# Documentation Sources

## Target

- Documentation directory: <repository-relative path>
- Vendor: <exact name>
- MCU part: <exact part number>
- Last updated: <date>

Record `Package`, `Silicon revision`, `Board name/type` and `Board revision`
only once each is established, and delete the line until then.

## Hardware Setup Context

Record only the answers the user actually gave, one line each, from: probe or
programmer and debug interface; current loader/tool and version; host OS and
local or remote board access; current firmware-loading procedure; debug, boot
or RAM-loading documentation.

- Evidence: user-reported; no tool compatibility or hardware operation verified

## Source Coverage

| Input | Availability | Source IDs | Applicability or gap |
|---|---|---|---|
| Reference manual | available | doc-001 | Covers the exact part at revision 3 |
| Errata | not-searched | [] | Search this before any revision-specific claim |
| Datasheet | available | doc-002 | Covers the selected package |
| Board schematic | not-found | [] | Searched the vendor board page on <date> |
| Board guide/connectors/jumpers | not-searched | [] | Blocked on the board revision |
| Supporting documents | not-searched | [] | Not yet requested |
| Vendor SVD | confirmed-unavailable | [] | Vendor support page states no SVD is published |
| Loader/debug/RAM-loading instructions | not-searched | [] | User-reported setup only |

## Source Records

### doc-001

- Kind: <reference manual, schematic, SVD, etc.>
- Title and document number: <exact title and number>
- Revision and publication date: <as printed>
- Availability: available
- Covered parts/packages/boards/revisions: <as listed on the cover or portal>
- Applicability to this target and evidence: <what was checked, and how>
- Origin: <user supplied, official vendor, or community candidate>
- Local path: <path relative to SOURCES.md, or explicit reference-only path>
- SHA-256 of local bytes: <64 lowercase hexadecimal characters>
- Retrieved/accessed: <date>

Add `Source page and download/repository URL`, `Pack/SDK version, repository
revision, and member path`, `Metadata checked against`, `Known access/sharing
restrictions` and `Caveats or superseded source IDs` only where each is
established. Delete a line rather than asserting that its value is missing, and
never invent a digest: an uncomputed hash means the `local-source-hashes` check
is `unrun`, which the handoff records.

## Search Log

| Input sought | Date | Sites/repositories checked | Outcome or limitation |
|---|---|---|---|

## Gaps and Handoff

- SVD starting point: review-supplied | author-from-docs | unresolved
- Missing/uncertain inputs, affected work, and next actions: <list>
- Existing cited findings: <relative notes paths, or an empty list>

The stage-owned location lines — PAC project root, SVD artifact directory, SVD
preparation note, PAC generator directory, generated PAC crate directory and PAC
generation note — are added by the owning stage when that stage runs. Intake
leaves them out entirely. The intake status itself is not recorded here: it is
`handoff.status` in `01-sources.toml`, which is exactly one of `ready`,
`partial` or `blocked`.
```
