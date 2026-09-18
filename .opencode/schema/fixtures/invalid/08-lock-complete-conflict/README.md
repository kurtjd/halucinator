# `08-lock-complete-conflict`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `LOCK_COMPLETE_CONFLICT`

- Expected file: `halucinator/.run/review-pac-068841a2.lock`
- Expected field: `-`
- Defect: A stage lock for `review:pac` exists while `state.stages` records that stage `ready`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/08-lock-complete-conflict/generation-roots/fictional-pac
```

Expected exit code: 1.
