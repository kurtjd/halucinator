# `25-scope-deleted-predecessor`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `25-scope-deleted-predecessor` case. The validator must emit exactly 2 diagnostic(s):
PATH_INSPECTION, SCOPE_DELETED_PREDECESSOR

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/scope/scope-1111bbbb.toml|previous|SCOPE_DELETED_PREDECESSOR`
Expected diagnostic: `halucinator/scope/scope-1111bbbb.toml|previous.decision|PATH_INSPECTION`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/25-scope-deleted-predecessor/generation-roots/fictional-pac
```

Expected exit code: 1.
