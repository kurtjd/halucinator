# `01-unknown-field`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `UNKNOWN_FIELD`

- Expected file: `halucinator/handoff/01-sources.toml`
- Expected field: `sources.note`
- Defect: An extra key `note` was added to `[sources]`.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/01-unknown-field/generation-roots/fictional-pac
```

Expected exit code: 1.
