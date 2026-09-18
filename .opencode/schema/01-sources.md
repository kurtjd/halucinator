# `01-sources.toml`

Stage `gather-documentation`.

Fields: `sources.catalog` FileRef required; `sources.route` required enum `review-supplied|author-from-docs|unresolved`; `sources.source_ids` sorted string[] required; `sources.available` FileRef[] required; `sources.cited_notes` FileRef[] required. Producer owns all at intake (`gather-documentation/SKILL.md:154-195`); `generate-svd` reads them (`generate-svd/SKILL.md:43-67`). The former broad `sources.coverage` is deleted: the catalog is its only durable reader and already owns it.

Route is producer-evaluable: supplied means an accessible SVD is present; author means search completed without one and register documentation is accessible; unresolved means search/access incomplete. Applicability/fact sufficiency remain downstream decisions.

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `requested-inputs-accounted` | mandatory | `gather-documentation/SKILL.md:181-184`. |
| `available-content-resolves` | mandatory | same. |
| `local-source-hashes` | mandatory when `sources.available` nonempty; otherwise not-applicable | `gather-documentation/SKILL.md:143-150`. |
| `svd-search-complete` | mandatory when route is `author-from-docs`; otherwise not-applicable | `gather-documentation/SKILL.md:162-171`. |

Write-only legacy next-action/setup fields remain only in Markdown and are not schema fields.