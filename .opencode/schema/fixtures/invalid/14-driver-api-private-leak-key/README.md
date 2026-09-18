# `14-driver-api-private-leak-key`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `DRIVER_API_LEAK`

- Expected file: `halucinator/handoff/06-driver-schema-demo.toml`
- Expected field: `driver.public_api`
- Defect: A `public_api` entry contains a PAC register write sequence rather than a public signature.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/14-driver-api-private-leak-key/generation-roots/fictional-pac
```

Expected exit code: 1.
