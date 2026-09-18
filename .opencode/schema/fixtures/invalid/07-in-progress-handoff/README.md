# `07-in-progress-handoff`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `HANDOFF_IN_PROGRESS`

- Expected file: `halucinator/handoff/02-facts.toml`
- Expected field: `handoff.status`
- Defect: `handoff.status` is `"in-progress"`, a lock-only status leaked into a handoff.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/07-in-progress-handoff/generation-roots/fictional-pac
```

Expected exit code: 1.
