# `01-sources.toml`

Stage `gather-documentation`.

Fields: `sources.catalog` FileRef required; `sources.route` required enum `review-supplied|author-from-docs|unresolved`; `sources.documents` required nonempty array of `SourceDocument`, sorted and unique by `source_id`; `sources.cited_notes` FileRef[] required. Producer owns all at intake (`gather-documentation/SKILL.md:154-195`); `generate-svd` reads them (`generate-svd/SKILL.md:43-67`). The former broad `sources.coverage` is deleted: the catalog is its only durable reader and already owns it.

Schema 2 replaces the two independently-membered v1 fields with one binding array. A free-standing ID list and a free-standing file list could disagree about which bytes an ID named; `sources.documents` makes that disagreement unrepresentable. Each `SourceDocument` is exact `{source_id,document,revision,format,source}`: `source_id` a nonempty stable catalog ID; `document` the exact recorded title; `revision` the exact recorded revision; `format` the enum `pdf|utf8-text`, which is exactly the set the verifier can derive searchable text from; and `source` a hash-pinned FileRef to the authoritative bytes. A `CitationRef.source_id` selects exactly one entry, and the citation's own `source` FileRef must equal that entry's. Title and revision are read from the selected document rather than duplicated into every citation.

Other formats are not mechanically citable. A vendor SVD or XML file is a machine-readable input, not quoted manual evidence. HTML must first be preserved as an admitted UTF-8 text snapshot. A scanned or image-only PDF that yields no matching text fails closed and requires a text-capable authoritative source; no OCR path is authorized.

Route is producer-evaluable: supplied means an accessible SVD is present; author means search completed without one and register documentation is accessible; unresolved means search/access incomplete. Applicability/fact sufficiency remain downstream decisions.

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `requested-inputs-accounted` | mandatory | `gather-documentation/SKILL.md:181-184`. |
| `available-content-resolves` | mandatory | same. |
| `local-source-hashes` | mandatory when `sources.documents` is nonempty; otherwise not-applicable | `gather-documentation/SKILL.md:143-150`. |
| `svd-search-complete` | mandatory when route is `author-from-docs`; otherwise not-applicable | `gather-documentation/SKILL.md:162-171`. |

Write-only legacy next-action/setup fields remain only in Markdown and are not schema fields.