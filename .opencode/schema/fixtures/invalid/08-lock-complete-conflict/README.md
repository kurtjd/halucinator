# `08-lock-complete-conflict`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `08-lock-complete-conflict` case. The validator must emit exactly 1 diagnostic(s):
LOCK_COMPLETE_CONFLICT

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/.run/review-pac-068841a2.lock|-|LOCK_COMPLETE_CONFLICT`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/08-lock-complete-conflict/generation-roots/fictional-pac
```

Expected exit code: 1.
