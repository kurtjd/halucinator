# `26-scope-second-initial`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `SCOPE_SECOND_INITIAL`

- Expected file: `halucinator/scope/scope-5555ffff.toml`
- Expected field: `previous`
- Defect: A second decision declares `previous = { kind = "initial" }`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/26-scope-second-initial/generation-roots/fictional-pac
```

Expected exit code: 1.
