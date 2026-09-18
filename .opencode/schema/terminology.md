# Canonical terminology

This file establishes vocabulary for new and changed toolkit files. Existing files are not rewritten here; later work performs that migration.

# Canonical concepts

- `workflow stage`: One producer-owned unit in the HAL pipeline that emits one handoff kind. Rejected: `phase` (exists), `step` (exists), `milestone` (exists).
- `target identity`: The tuple identifying one HAL effort: vendor, MCU part number, and, when known, package, silicon revision, and core. Rejected: bare `target` when the tuple is not meant (exists), bare `chip` (exists), bare `part` (exists), `exact MCU` (exists).
- `MCU part number`: The vendor's exact ordering code, preserved verbatim. Rejected: `part` as shorthand (exists), `chip` as shorthand (exists).
- `package`: The physical package or ordering-code package variant. Rejected: `package type` (exists).
- `silicon revision`: The die revision to which errata and behavior apply; it is not a core. Rejected: `core revision` when silicon is meant (not found).
- `core`: The processor core selected within the MCU, including its architecture variant when known. Rejected: `silicon revision` when core is meant (exists as a conflation).
- `Cargo chip feature`: The Cargo feature selecting generated support for one MCU/core combination. Rejected: bare `chip feature` (exists), `target feature` (exists).
- `Rust compilation target`: The Rust target triple used to compile target code. Rejected: bare `target` (exists), `build target` (exists).
- `typestate`: A type-level state distinction that removes invalid runtime states. Rejected: `type-state` (exists), `Typestate` (exists).
- `behavior`: Observable semantics. Rejected: `behaviour` (exists).
- `normalize`: Convert to a declared canonical representation. Rejected: `normalise` (exists).
- `initialization`: Bringing software or hardware from reset into its declared usable state. Rejected: `initialisation` (exists).

## Enforcement scope

The parenthetical labels describe the repository at commit `2d073c1`. M1 does not alter those legacy occurrences. Mechanical enforcement applies only to the exact unambiguous tokens `type-state`, `Typestate`, `behaviour`, `normalise`, and `initialisation`, case-sensitive as written. Governance covers tracked toolkit prose. `tools/selfcheck.py` inspects only added/changed tracked prose relative to the checked-in baseline, excluding this file's Rejected entries, fixtures, code fences, inline code, URLs, code identifiers, and quoted legacy text. Root `TODO.md` is explicitly excluded because it is untracked coordinator working state under active revision; this narrow exception must not expand to other tracked or inconvenient files. Stage/identity shorthand and other rejected phrases are review-only conventions because ordinary prose makes safe grep enforcement impossible.
