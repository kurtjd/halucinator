# `28-scope-orphan`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `28-scope-orphan` case. The validator must emit exactly 2 diagnostic(s):
PATH_INSPECTION, SCOPE_ORPHAN

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/scope/scope-3333dddd.toml|previous|SCOPE_ORPHAN`
Expected diagnostic: `halucinator/scope/scope-3333dddd.toml|previous.decision|PATH_INSPECTION`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/28-scope-orphan/generation-roots/fictional-pac
```

Expected exit code: 1.
