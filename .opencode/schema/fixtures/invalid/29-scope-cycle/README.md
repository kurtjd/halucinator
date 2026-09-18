# `29-scope-cycle`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `SCOPE_CYCLE`

- Expected file: `halucinator/scope/scope-1111bbbb.toml`
- Expected field: `previous`
- Defect: `scope-1111bbbb` and `scope-2222cccc` name each other as predecessor, alongside a valid single-node chain rooted at `scope-5555ffff`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/29-scope-cycle/generation-roots/fictional-pac
```

Expected exit code: 1.
