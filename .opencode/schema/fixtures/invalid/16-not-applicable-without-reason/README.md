# `16-not-applicable-without-reason`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `16-not-applicable-without-reason` case. The validator must emit exactly 1 diagnostic(s):
NOT_APPLICABLE_NO_REASON

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/03-svd.toml|checks.correction-effects|NOT_APPLICABLE_NO_REASON`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/16-not-applicable-without-reason/generation-roots/fictional-pac
```

Expected exit code: 1.
