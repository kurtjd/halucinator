# `14-driver-api-private-leak-key`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `14-driver-api-private-leak-key` case. The validator must emit exactly 1 diagnostic(s):
DRIVER_API_LEAK

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/06-driver-schema-demo.toml|driver.public_api|DRIVER_API_LEAK`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/14-driver-api-private-leak-key/generation-roots/fictional-pac
```

Expected exit code: 1.
