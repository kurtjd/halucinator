# `24-foundation-partition-missing`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `FOUNDATION_PARTITION`

- Expected file: `halucinator/handoff/04-pac.toml`
- Expected field: `pac.foundation`
- Defect: `foundation:interrupt-metadata` is required in state but has no `[[pac.foundation]]` entry.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/24-foundation-partition-missing/generation-roots/fictional-pac
```

Expected exit code: 1.
