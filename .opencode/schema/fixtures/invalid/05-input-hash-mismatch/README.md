# `05-input-hash-mismatch`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `INPUT_HASH_MISMATCH`

- Expected file: `halucinator/handoff/02-facts.toml`
- Expected field: `handoff.inputs`
- Defect: The pinned digest of `01-sources.toml` is `b`*64 and does not match its bytes.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/05-input-hash-mismatch/generation-roots/fictional-pac
```

Expected exit code: 1.
