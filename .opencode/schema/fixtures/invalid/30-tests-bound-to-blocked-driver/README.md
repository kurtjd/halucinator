# `30-tests-bound-to-blocked-driver`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `30-tests-bound-to-blocked-driver` case. The validator must emit exactly 1 diagnostic(s):
DEPENDENCY_NOT_READY

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/07-tests-beta-loopback.toml|tests.api_handoff|DEPENDENCY_NOT_READY`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/30-tests-bound-to-blocked-driver/generation-roots/fictional-pac
```

Expected exit code: 1.
