# `04-ready-dependency-not-ready`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `DEPENDENCY_NOT_READY`

- Expected file: `halucinator/handoff/04-pac.toml`
- Expected field: `handoff.inputs`
- Defect: `03-svd` is honestly `partial` (`preparation-replay` unrun) and `state.stages` agrees, but `04-pac` is still `ready`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/04-ready-dependency-not-ready/generation-roots/fictional-pac
```

Expected exit code: 1.
