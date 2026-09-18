# `02-facts.toml`

Stage `extract-facts`.

Fields: `facts.notes` nonempty FileRef[] required; `facts.citations` CitationRef[] required; `facts.categories` sorted enum[] required from `register-layout|field-encodings|dependencies|interrupts|errata|pin-mux|memory-runtime`; `facts.contradictions` string[] required. Produced at `hal-datasheet.md:103-113,134-153`, consumed by `generate-svd/SKILL.md:58-67` and later cited-hardware gates. `suggested_public_types_note` is deleted: no concrete downstream admission reads it.

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `citations-complete` | mandatory | `hal-datasheet.md:103-113,140-153`. |
| `summary-field-cross-check` | mandatory when category `register-layout` is present; otherwise not-applicable | `hal-datasheet.md:105-109`. |
| `field-encodings-exhaustive` | mandatory when category `field-encodings` is present; otherwise not-applicable | `hal-datasheet.md:54-56,126-128`. |
| `pdf-layout-extraction` | mandatory when any input path ends `.pdf`; otherwise not-applicable | `hal-datasheet.md:80-102`. |

For authoring SVD, ready additionally requires categories needed by current scope; exact requirement is carried by scope/foundation IDs rather than a fixed universal category list.