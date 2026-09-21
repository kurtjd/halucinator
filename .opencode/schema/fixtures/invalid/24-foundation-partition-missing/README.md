# `24-foundation-partition-missing`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `24-foundation-partition-missing` case. The validator must emit exactly 1 diagnostic(s):
FOUNDATION_PARTITION

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/04-pac.toml|pac.foundation|FOUNDATION_PARTITION`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/24-foundation-partition-missing/generation-roots/fictional-pac
```

Expected exit code: 1.
