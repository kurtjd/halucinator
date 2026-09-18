# `23-first-peripheral-without-modes`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `FIRST_PERIPHERAL_MODES`

- Expected file: `halucinator/state.toml`
- Expected field: `decisions.first_peripheral_modes`
- Defect: `decisions.first_peripheral` is present but `first_peripheral_modes` was deleted.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/23-first-peripheral-without-modes/generation-roots/fictional-pac
```

Expected exit code: 1.
