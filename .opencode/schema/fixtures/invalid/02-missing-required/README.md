# `02-missing-required`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `MISSING_FIELD`

- Expected file: `halucinator/handoff/01-sources.toml`
- Expected field: `sources.route`
- Defect: The required `sources.route` key was deleted.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/02-missing-required/generation-roots/fictional-pac
```

Expected exit code: 1.
