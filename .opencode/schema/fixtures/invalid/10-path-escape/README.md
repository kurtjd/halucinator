# `10-path-escape`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `PATH_ESCAPE`

- Expected file: `halucinator/handoff/06-driver-schema-demo.toml`
- Expected field: `driver.owned_files`
- Defect: An owned-file PathRef contains `..` segments that leave the repository root.

Derived from `fixtures/valid/` by re-materializing the whole tree in the order
specified by `fixtures.md#hash-materialization-order` with this one change
injected, so every other digest in the tree remains correct.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/10-path-escape/generation-roots/fictional-pac
```

Expected exit code: 1.
