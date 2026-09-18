# `22-unknown-schema-version`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `SCHEMA_VERSION`

- Expected file: `halucinator/handoff/01-sources.toml`
- Expected field: `handoff.schema`
- Defect: `handoff.schema` is `2`; version 1 validators must fail closed.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/22-unknown-schema-version/generation-roots/fictional-pac
```

Expected exit code: 1.
