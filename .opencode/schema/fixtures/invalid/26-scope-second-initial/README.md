# `26-scope-second-initial`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `26-scope-second-initial` case. The validator must emit exactly 1 diagnostic(s):
SCOPE_SECOND_INITIAL

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/scope/scope-5555ffff.toml|previous|SCOPE_SECOND_INITIAL`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/26-scope-second-initial/generation-roots/fictional-pac
```

Expected exit code: 1.
