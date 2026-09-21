# `33-citation-excerpt-absent`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: `facts.citations[0].excerpt` quotes a sentence that does not occur
at the cited lines of the pinned fictional manual. Every hash in the tree
stays current, so nothing masks the citation failure. This is the case the
gate exists for: the excerpt is plausible prose the verifier cannot derive.

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/02-facts.toml|facts.citations.0.excerpt|CITATION_UNVERIFIED`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/33-citation-excerpt-absent/generation-roots/fictional-pac
```

Expected exit code: 1.
