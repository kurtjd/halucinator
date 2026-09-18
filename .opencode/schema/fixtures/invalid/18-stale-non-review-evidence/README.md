# `18-stale-non-review-evidence`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `STALE_EVIDENCE`

- Expected file: `halucinator/handoff/02-facts.toml`
- Expected field: `handoff.notes`
- Defect: The pinned digest of `FACTS.md` (non-review evidence) is `b`*64 and does not match its bytes.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/18-stale-non-review-evidence/generation-roots/fictional-pac
```

Expected exit code: 1.
