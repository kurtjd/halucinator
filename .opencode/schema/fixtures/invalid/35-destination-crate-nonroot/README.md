# `35-destination-crate-nonroot`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: `state.decisions.destination_crate` is nested at
`crates/embassy-unobtainium` instead of the repository-root single segment
`embassy-unobtainium`. A nested destination is not covered by the tester's
`embassy-*/**` denial, which is the configured-path half of A18.

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/state.toml|decisions.destination_crate|ILLEGAL_ENUM`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/35-destination-crate-nonroot/generation-roots/fictional-pac
```

Expected exit code: 1.
