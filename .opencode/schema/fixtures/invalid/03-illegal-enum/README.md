# `03-illegal-enum`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `ILLEGAL_ENUM`

- Expected file: `halucinator/handoff/01-sources.toml`
- Expected field: `sources.route`
- Defect: `sources.route` is `"supplied"`, outside `review-supplied|author-from-docs|unresolved`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/03-illegal-enum/generation-roots/fictional-pac
```

Expected exit code: 1.
