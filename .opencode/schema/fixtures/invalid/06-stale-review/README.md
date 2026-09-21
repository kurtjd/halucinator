# `06-stale-review`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `06-stale-review` case. The validator must emit exactly 3 diagnostic(s):
REVIEW_NONACCEPTING, STALE_EVIDENCE, STALE_REVIEW

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/04-pac.toml|checks.independent-review|REVIEW_NONACCEPTING`
Expected diagnostic: `halucinator/handoff/08-review-pac.toml|review.artifact|STALE_EVIDENCE`
Expected diagnostic: `halucinator/handoff/08-review-pac.toml|review.artifact|STALE_REVIEW`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/06-stale-review/generation-roots/fictional-pac
```

Expected exit code: 1.
