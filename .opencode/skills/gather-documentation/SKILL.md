---
name: gather-documentation
description: >-
  Collect MCU and evaluation-board documentation before starting an Embassy HAL.
  Use for documentation intake, identifying the exact target part and board,
  gathering reference manuals, datasheets, errata, EVB schematics and board
  guides, locating a vendor SVD, or resuming an incomplete source collection.
  Records sources and gaps in the working repository's documentation directory.
  Does not extract register facts, generate SVDs or PACs, or set up hardware.
compatibility: opencode
---

# Gather Documentation

The owning agent is **hal-datasheet**. This skill establishes the target and
its source documents; it does not perform that agent's later hardware analysis.
**hal-architect** coordinates the handoff to the other agents.

## Boundaries

- Keep gathered documents, the source list, and later research artifacts
  in the working repository under the location selected using `AGENTS.md`'s
  "Artifact storage and handoff" rule. Do not change unrelated files,
  configuration, or ignore rules.
- Leave PDF conversion (`pdftotext -layout`), schematic interpretation, and
  cited hardware-fact extraction to subsequent **hal-datasheet** work.
  Missing extraction tools do not prevent source collection.
- Leave SVD validation/transforms and PAC generation to **hal-svd**. Collect
  hardware setup requirements, but do not install tools, run vendor scripts,
  connect to a probe, flash a board, or test RAM execution.

## Procedure

### 1. Identify the target

Reuse answers in the request or an explicitly supplied source list. Ask only
for missing or conflicting information, in short groups rather than one large
questionnaire. If the agent cannot ask questions directly, return the pending
questions to **hal-architect** instead of guessing.

Establish the vendor and exact MCU part number first. Ask for the package and
silicon revision if known, and the EVB or custom-board name and revision if
there is a board. Preserve the user's exact identifiers. If several parts are
planned, identify the first part for this run; family-level documentation is
not evidence that every member is covered. An unresolved part number needs
clarification before collecting a supposedly matching document set.

Unknown package, silicon revision, or board details are valid answers. Record
them as unknown and describe which later applicability checks they prevent.

### 2. Select or resume the documentation directory

Read [the storage rules and source-list template](./references/source-list-format.md).
Follow its legacy-record check before starting a new collection, and show the
actual selected path relative to the repository root.

Check that the destination stays inside the working repository, resolving
symlinks and existing parent directories before creating anything. If access
is denied or the location is unsuitable, ask for another in-repository
directory. Do not change the user's permissions or write to a different
repository as a fallback.

Load an existing `SOURCES.md` before interviewing again. Check its MCU and
board identity before reuse; do not silently mix different targets or
overwrite another board's setup. A different MCU, board, or known board
revision requires a separate documentation directory in the repository;
filling in a previously unknown identifier does not. If a new identifier
conflicts with existing sources or findings, record the conflict and ask
before reuse. Keep previous source records and research notes intact.

Create or update `SOURCES.md` in that directory using the template. Record
partial progress so a missing document does not require restarting the interview.
Preserve paths to any later SVD preparation records on reruns. Intake does not
create SVD preparation directories; `generate-svd` selects and records them
when that work begins.

### 3. Ask for the sources and bench context

Accept local paths, attachments, or URLs, and reuse anything already supplied.
Ask for these inputs in order, skipping questions already answered:

1. **Reference manual** for the exact MCU or a family explicitly covering it.
2. **Errata**, if available. Ask about a separate errata sheet or corrections
   included in another vendor document. Lack of a supplied sheet does not
   establish that no errata exists.
3. **Datasheet**, including the selected package's pin and electrical data.
4. **EVB schematic and board user guide**, matching the board revision,
   including connector, jumper, and solder-bridge documentation. For a custom
   board, accept the user's schematic or available board documentation.
5. **Other supporting documents** the user considers relevant: application
   notes, SDK documentation, boot/debug guides, or board-specific addenda.
6. **Existing SVD**, including its origin and intended devices if known.

Also ask: "How do you currently load firmware, and what probe or tool do you
have?" Record the probe/programmer, interface, loader/tool and version if
known, host OS and local/remote board access, and any existing instructions.
Ask whether they have documentation for debugging or loading/running from RAM.
An answer of "not set up yet" is fine. These are user-reported setup facts,
not evidence of tool support or successful operation. Do not ask the user to
prove `probe-rs` support or RAM feasibility during intake.

### 4. Locate missing inputs

Use supplied sources first, then search for missing documents and SVDs,
preferring official vendor product pages, documentation portals, SDK
repositories, and device-support packs. Look inside documented pack/SDK
contents for SVDs when no standalone download is listed. Community results
are candidates with explicit provenance, not automatically authoritative.

Record the sites or repositories searched, search date, and outcome. Search
the exact part and its documented family; do not substitute a similarly named
chip or board. After checking the applicable official sources, report remaining
gaps rather than repeatedly guessing URLs. If search, download, or authenticated
access is unavailable, say which capability is missing and request a user
supplied source. Never bypass an access restriction or request credentials.

Distinguish **not provided**, **not searched**, **located**, **available**,
**inaccessible**, **not found**, and **confirmed unavailable**. A link without
retrievable document content is only located. "Not found" records the scope
of a search, not proof of nonexistence. "Confirmed unavailable" requires
attributed confirmation and its scope; no published errata sheet does not
mean that the silicon has no errata.

### 5. Preserve and describe the sources

- Preserve user originals and vendor bytes. Copy or download into the chosen
  directory's `sources/` subdirectory without overwriting another source. If
  copying is not permitted or practical, retain an explicit reference-only path and note the
  dependency on its continued availability. Do not move or delete originals,
  even when a user-supplied file already lives in their checkout.
- Use file-edit tools for the Markdown record and available download/archive
  tools for source material. Keep archive extraction inside the authorized
  workspace; reject paths or symlinks that escape it. Do not execute packaged
  installers or scripts to obtain documentation.
- Check the actual file type and accessibility, not just the extension. An
  HTML login/error page saved with a PDF filename is not an available manual.
  Do not claim a download succeeded when only a web summary was retrieved.
- Record each document's title/number, revision/date, provenance and covered
  parts or boards using its cover, metadata, or vendor listing when available.
  If these cannot be checked without deeper analysis, mark them unverified.
  Keep applicability separate from availability: a readable wrong-part manual
  is still unsuitable. Do not convert the full manual to establish intake.
- Give each distinct source/revision a stable ID. Record its relative local
  path, retrieval date, and a tool-computed SHA-256 for local bytes. If hashing
  is unavailable, record "not checked"; never invent a digest. Record licensing
  or sharing restrictions when known; do not assume permission to redistribute.
  Keep credentials and temporary authenticated URLs out of the source list.
- On reruns, check that referenced files still exist and verify their hashes
  before reuse. Record changed bytes or revisions as new source records, not
  silent replacements for something already cited. Reacquire missing public
  sources where possible; ask again for missing local-only inputs. Preserve
  earlier IDs, gaps, and notes, updating their status rather than erasing history.

### 6. Record gaps and hand off

For each missing or uncertain input, record what is blocked and the next
action. A missing schematic prevents trustworthy board-specific wiring but
need not prevent MCU documentation work. A missing manual blocks hardware
claims not supported by another cited source. An unknown silicon revision
leaves revision-specific errata applicability unresolved.

Record one SVD starting point for **hal-svd**:

- **Review/normalize existing input**: a candidate SVD was acquired or is
  accessible by reference. Identify its source ID and any coverage uncertainty;
  availability does not establish register correctness.
- **Author from cited documentation**: no suitable SVD was found after the
  recorded search, or its unavailability is confirmed. Flag `generate-svd` as
  required, plus any missing manual facts needed before authoring can start.
- **Unresolved**: lookup was not completed, access failed, or coverage remains
  too uncertain to choose an input. State the next lookup or user question.

Finding a vendor SVD does not skip `generate-svd`; it changes that stage's
starting point. This skill does not invoke it. If the downstream skill is
still unimplemented, name the gap for **hal-architect** instead of claiming it
ran. Record board/tooling/RAM-loading questions for future hardware preparation
under **hal-architect**, without changing the current human-only hardware rule.

## Completion and output

Before finishing, check that every requested input has a source entry or an
explicit gap, all "available" sources resolve to real content, and all new
intake artifacts are in the chosen repository documentation directory. Report
the files created or updated, and preserve unrelated repository changes.

Return:

1. **Target**: exact MCU and board, including unresolved identifiers.
2. **Location**: repository-relative documentation-directory and `SOURCES.md` paths.
3. **Sources**: source IDs, revisions and availability/applicability summary.
4. **Gaps**: affected downstream work and the next question or action.
5. **Handoff**: SVD starting point and hardware-setup questions for
   **hal-architect**, plus any existing cited-note paths needed next.
6. **Status**: intake complete, complete with gaps, or blocked, with the reason.
   State that collection did not validate hardware facts or run hardware.

Intake completion means the requested inputs are accounted for, not that every
source exists or that the next stage is ready. **hal-architect** decides that
gate. Downstream agents receive repository-relative paths and source IDs;
they must not depend on this conversation or a remembered working directory.
