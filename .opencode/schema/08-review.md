# `08-review-<artifact>.toml`

Stage `review`.

Required: `review.artifact_id`; `review.artifact` ArtifactRef; `review.scope` and `review.unreviewed` scope-item IDs; `review.dependencies` FileRef[] for evidence reviewed; `review.findings` exact `{severity,location,summary,owner,status}` with severity `blocking|convention|api|contract|unverified` and status `open|resolved|not-applicable`; `review.verdict=ready|ready-with-fixes|not-ready`; tagged `review.lineage={kind="initial"}` or `{kind="recheck",previous=<FileRef>}`. Produced by `hal-reviewer.md:155-171`, consumed by every independent-review check. Lineage's concrete reader is the reviewer resumption/recheck gate (`scaffold-record.md:85-90`; `gpio-record.md:49-51`).

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `applicable-references-read` | mandatory | `hal-reviewer.md:131-139`. |
| `artifact-identity` | mandatory | review input identity/recheck gates cited above. |
| `hardware-claims-cited` | mandatory when review scope includes any `hardware:` or `foundation:fact-` ID; otherwise not-applicable | `hal-reviewer.md:121-139`. |
| `upstream-contracts-reviewed` | mandatory when reviewed artifact declares trait obligations/dependencies; otherwise not-applicable | `hal-reviewer.md:121-125,166-167`. |

Only verdict `ready` accepts, requiring no open blocking/API/contract/unverified finding and no required unreviewed scope. Changing artifact or dependency evidence makes review stale.