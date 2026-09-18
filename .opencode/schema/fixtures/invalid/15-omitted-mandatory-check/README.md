# `15-omitted-mandatory-check`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `CHECK_MISSING`

- Expected file: `halucinator/handoff/04-pac.toml`
- Expected field: `checks`
- Defect: The mandatory `format-lint` check entry is absent from the closed 04 check set.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/15-omitted-mandatory-check/generation-roots/fictional-pac
```

Expected exit code: 1.
