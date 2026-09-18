# `06-stale-review`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `STALE_REVIEW`

- Expected file: `halucinator/handoff/08-review-pac.toml`
- Expected field: `review.artifact`
- Defect: `review.artifact` pins a canonical digest of different bytes than the PAC inventory it names.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/06-stale-review/generation-roots/fictional-pac
```

Expected exit code: 1.
