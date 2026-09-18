# `19-route-incompatibility`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `ROUTE_INCOMPATIBILITY`

- Expected file: `halucinator/handoff/03-svd.toml`
- Expected field: `svd.route`
- Defect: `svd.route` is `author-from-docs` while `sources.route` in `01-sources` is `review-supplied`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/19-route-incompatibility/generation-roots/fictional-pac
```

Expected exit code: 1.
