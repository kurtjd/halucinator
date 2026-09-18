# `11-noncanonical-digest`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `NONCANONICAL_DIGEST`

- Expected file: `halucinator/handoff/02-facts.toml`
- Expected field: `handoff.inputs`
- Defect: The pinned digest of `01-sources.toml` is byte-correct but written in uppercase hex.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/11-noncanonical-digest/generation-roots/fictional-pac
```

Expected exit code: 1.
