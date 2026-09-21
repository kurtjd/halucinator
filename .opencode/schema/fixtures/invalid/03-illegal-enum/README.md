# `03-illegal-enum`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `03-illegal-enum` case. The validator must emit exactly 2 diagnostic(s):
ILLEGAL_ENUM, ROUTE_INCOMPATIBILITY

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/01-sources.toml|sources.route|ILLEGAL_ENUM`
Expected diagnostic: `halucinator/handoff/03-svd.toml|svd.route|ROUTE_INCOMPATIBILITY`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/03-illegal-enum/generation-roots/fictional-pac
```

Expected exit code: 1.
