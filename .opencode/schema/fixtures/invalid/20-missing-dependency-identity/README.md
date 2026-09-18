# `20-missing-dependency-identity`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `DEPENDENCY_IDENTITY`

- Expected file: `halucinator/handoff/05-platform.toml`
- Expected field: `platform.dependencies`
- Defect: The `unobtainium-pac` dependency has an empty `identity`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/20-missing-dependency-identity/generation-roots/fictional-pac
```

Expected exit code: 1.
