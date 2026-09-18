# `16-not-applicable-without-reason`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `NOT_APPLICABLE_NO_REASON`

- Expected file: `halucinator/handoff/03-svd.toml`
- Expected field: `checks.correction-effects`
- Defect: `correction-effects` is `not-applicable` with neither `reason` nor `evidence`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/16-not-applicable-without-reason/generation-roots/fictional-pac
```

Expected exit code: 1.
