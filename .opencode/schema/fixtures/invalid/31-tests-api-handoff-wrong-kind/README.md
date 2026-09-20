# `31-tests-api-handoff-wrong-kind`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `31-tests-api-handoff-wrong-kind` case. The validator must emit exactly 1 diagnostic(s):
ILLEGAL_ENUM

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/07-tests-beta-loopback.toml|tests.api_handoff|ILLEGAL_ENUM`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/31-tests-api-handoff-wrong-kind/generation-roots/fictional-pac
```

Expected exit code: 1.
