# `02-facts.toml`

Stage `extract-facts`.

Fields: `facts.notes` nonempty FileRef[] required; `facts.citations` CitationRef[] required; `facts.categories` sorted enum[] required from `register-layout|field-encodings|dependencies|interrupts|errata|pin-mux|memory-runtime`; `facts.contradictions` string[] required. The schema-2 CitationRef is specified in `handoff-common.md`: every entry carries an assertion ID, the supported scope item, the claim, the bound source ID and FileRef, a tagged machine location, the printed locator, the matched excerpt, and the reasoning note. Produced at `hal-datasheet.md:103-113,134-153`, consumed by `generate-svd/SKILL.md:58-67` and later cited-hardware gates. `suggested_public_types_note` is deleted: no concrete downstream admission reads it.

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `citations-complete` | mandatory | `hal-datasheet.md:103-113,140-153`. |
| `citations-verified` | mandatory when `facts.citations` is nonempty; otherwise not-applicable with a reason | Schema 2. The validator derives text from each bound source and verifies every citation; the check may be recorded `passed` only when it did. |
| `summary-field-cross-check` | mandatory when category `register-layout` is present; otherwise not-applicable | `hal-datasheet.md:105-109`. |
| `field-encodings-exhaustive` | mandatory when category `field-encodings` is present; otherwise not-applicable | `hal-datasheet.md:54-56,126-128`. |
| `pdf-layout-extraction` | mandatory when any input path ends `.pdf`; otherwise not-applicable | `hal-datasheet.md:80-102`. |

What `citations-verified` proves is narrow and exact: either exact normalized substring occurrence, or exact ordered-token occurrence within the declared gap bounds, at the declared location of the hash-pinned bytes the cited source ID binds to. It cannot prove semantic entailment of the claim, visual contiguity of the quotation, OCR correctness, the truth of the recorded title or revision beyond the catalog record, or vendor truth. Independent review compares claim, excerpt, rendered source and printed locator; a passing gate never replaces that. When `pdftotext` is absent the gate fails with `CITATION_UNVERIFIED` and a remedy naming the package and the exact rerun command; it never downgrades itself to not-applicable, because a gate that can be bypassed by uninstalling a binary is not a gate.

For authoring SVD, ready additionally requires categories needed by current scope; exact requirement is carried by scope/foundation IDs rather than a fixed universal category list.