# `17-incomplete-status-partition`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `17-incomplete-status-partition` case. The validator must emit exactly 1 diagnostic(s):
COVERAGE_PARTITION

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/05-platform.toml|coverage.complete|COVERAGE_PARTITION`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/17-incomplete-status-partition/generation-roots/fictional-pac
```

Expected exit code: 1.
