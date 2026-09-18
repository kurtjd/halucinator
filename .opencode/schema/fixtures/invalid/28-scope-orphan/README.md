# `28-scope-orphan`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `SCOPE_ORPHAN`

- Expected file: `halucinator/scope/scope-3333dddd.toml`
- Expected field: `previous`
- Defect: `scope-3333dddd` names predecessor `scope-4444eeee`, which was never minted; the node is unreachable from the initial node.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/28-scope-orphan/generation-roots/fictional-pac
```

Expected exit code: 1.
