# `17-incomplete-status-partition`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `COVERAGE_PARTITION`

- Expected file: `halucinator/handoff/05-platform.toml`
- Expected field: `coverage.complete`
- Defect: `complete` ∪ `incomplete` omits `peripheral:schema-demo`, so the coverage partition is incomplete.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/17-incomplete-status-partition/generation-roots/fictional-pac
```

Expected exit code: 1.
