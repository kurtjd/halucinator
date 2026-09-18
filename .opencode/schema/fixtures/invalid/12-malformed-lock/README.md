# `12-malformed-lock`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `MALFORMED_LOCK`

- Expected file: `halucinator/.run/write-driver-schema-demo-c100ce44.lock`
- Expected field: `-`
- Defect: The lock file is not parseable TOML (unterminated string, bare values, empty key).

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/12-malformed-lock/generation-roots/fictional-pac
```

Expected exit code: 1.
