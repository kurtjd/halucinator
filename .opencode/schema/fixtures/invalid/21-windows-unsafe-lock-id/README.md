# `21-windows-unsafe-lock-id`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `21-windows-unsafe-lock-id` case. The validator must emit exactly 1 diagnostic(s):
LOCK_ID_UNSAFE

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/.run/write-tests%3aschema-demo-ac472d03.lock|-|LOCK_ID_UNSAFE`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/21-windows-unsafe-lock-id/generation-roots/fictional-pac
```

Expected exit code: 1.
