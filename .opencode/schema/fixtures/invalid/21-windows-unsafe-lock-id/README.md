# `21-windows-unsafe-lock-id`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `LOCK_ID_UNSAFE`

- Expected file: `halucinator/.run/write-tests%3aschema-demo-ac472d03.lock`
- Expected field: `-`
- Defect: The lock filename percent-encodes the canonical stage ID's colon instead of applying the mandated slug+digest8 algorithm.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/21-windows-unsafe-lock-id/generation-roots/fictional-pac
```

Expected exit code: 1.
