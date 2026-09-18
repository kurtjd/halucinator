# `13-review-nonaccepting`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `REVIEW_NONACCEPTING`

- Expected file: `halucinator/handoff/04-pac.toml`
- Expected field: `checks.independent-review`
- Defect: `04-pac` records `independent-review` passed, but the pinned review verdict is `ready-with-fixes`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/13-review-nonaccepting/generation-roots/fictional-pac
```

Expected exit code: 1.
