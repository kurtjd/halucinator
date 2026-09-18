# `03-svd.toml`

Stage `generate-svd`; first note is deterministic `<documentation>/notes/SVD.md` as a FileRef. Architect decisions are not written here.

Required fields: `svd.route` enum `review-supplied|author-from-docs`; `svd.source` FileRef; ordered `svd.transforms` and `svd.includes` FileRef[]; optional `svd.prepared_manifest` ArtifactRef; `svd.extraction_mode` enum `peripheral|block`; `svd.namespace_mode` enum `none|block|block-with-regs-vals`; `svd.representation_limits` string[]; `svd.unresolved_facts` string[]. Produced by `preparation-and-checks.md:234-260`; PAC reads them at `generation-and-checks.md:103-112,184-197`. Consumer requirements were removed and now belong to architect-owned state.

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `input-identity` | mandatory | `generate-svd/SKILL.md:52-56`. |
| `xml-well-formed` | mandatory | `preparation-and-checks.md:56-77`. |
| `schema-validation` | mandatory | same. |
| `source-fact-comparison` | mandatory | `generate-svd/SKILL.md:92-112`. |
| `correction-effects` | mandatory when transforms nonempty; otherwise not-applicable | `generate-svd/SKILL.md:114-129`. |
| `structural-inventory` | mandatory | `generate-svd/SKILL.md:131-145`. |
| `information-limits` | mandatory | `preparation-and-checks.md:201-225`. |
| `preparation-replay` | mandatory | `generate-svd/SKILL.md:147-148`. |

Ready requires all applicable checks passed, no unresolved facts, and route equal the sources route; author route also requires ready fact input.