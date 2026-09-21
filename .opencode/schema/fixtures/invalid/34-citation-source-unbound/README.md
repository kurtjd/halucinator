# `34-citation-source-unbound`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: `facts.citations[0].source_id` names `doc-404`, which selects no
`sources.documents[]` entry. A citation whose source ID binds to no bytes
cannot be derived from anything, so the gate fails closed rather than
treating the unbound ID as an unverifiable-but-acceptable claim.

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/02-facts.toml|facts.citations.0.source_id|CITATION_UNVERIFIED`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/34-citation-source-unbound/generation-roots/fictional-pac
```

Expected exit code: 1.
