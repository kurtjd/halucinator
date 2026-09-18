# `09-narrowed-ready-scope`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `NARROWED_READY_SCOPE`

- Expected file: `halucinator/handoff/01-sources.toml`
- Expected field: `coverage.incomplete`
- Defect: `status="ready"` but `peripheral:schema-demo` sits in `coverage.incomplete`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/09-narrowed-ready-scope/generation-roots/fictional-pac
```

Expected exit code: 1.
