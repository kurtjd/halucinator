# `05-input-hash-mismatch`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `05-input-hash-mismatch` case. The validator must emit exactly 1 diagnostic(s):
INPUT_HASH_MISMATCH

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/02-facts.toml|handoff.inputs|INPUT_HASH_MISMATCH`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/05-input-hash-mismatch/generation-roots/fictional-pac
```

Expected exit code: 1.
