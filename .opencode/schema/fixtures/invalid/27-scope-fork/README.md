# `27-scope-fork`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `SCOPE_FORK`

- Expected file: `halucinator/scope/scope-2222cccc.toml`
- Expected field: `previous`
- Defect: `scope-0123abcd` has two successors, `scope-1111bbbb` and `scope-2222cccc`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/27-scope-fork/generation-roots/fictional-pac
```

Expected exit code: 1.
