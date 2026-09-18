# `25-scope-deleted-predecessor`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `SCOPE_DELETED_PREDECESSOR`

- Expected file: `halucinator/scope/scope-1111bbbb.toml`
- Expected field: `previous`
- Defect: The tip's named predecessor `scope-0123abcd.toml` has been deleted from the append-only chain.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/25-scope-deleted-predecessor/generation-roots/fictional-pac
```

Expected exit code: 1.
