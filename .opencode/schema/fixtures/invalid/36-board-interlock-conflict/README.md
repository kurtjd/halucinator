# `36-board-interlock-conflict`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: two structurally valid `board-test` locks hold intersecting
`board:` resources. Whichever claimant is second always backs off; no
creation-order inference is permitted, and neither lock is ever stolen.

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/.run/write-tests-schema-demo-recheck-b8740e4e.lock|resources|BOARD_INTERLOCK_CONFLICT`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/36-board-interlock-conflict/generation-roots/fictional-pac
```

Expected exit code: 1.
