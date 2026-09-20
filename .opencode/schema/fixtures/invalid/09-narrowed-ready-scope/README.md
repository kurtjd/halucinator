# `09-narrowed-ready-scope`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `09-narrowed-ready-scope` case. The validator must emit exactly 1 diagnostic(s):
NARROWED_READY_SCOPE

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/01-sources.toml|coverage.incomplete|NARROWED_READY_SCOPE`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/09-narrowed-ready-scope/generation-roots/fictional-pac
```

Expected exit code: 1.
