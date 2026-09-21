# `23-first-peripheral-without-modes`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `23-first-peripheral-without-modes` case. The validator must emit exactly 1 diagnostic(s):
FIRST_PERIPHERAL_MODES

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/state.toml|decisions.first_peripheral_modes|FIRST_PERIPHERAL_MODES`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/23-first-peripheral-without-modes/generation-roots/fictional-pac
```

Expected exit code: 1.
