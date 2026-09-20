# `07-in-progress-handoff`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: the `07-in-progress-handoff` case. The validator must emit exactly 4 diagnostic(s):
DEPENDENCY_NOT_READY, HANDOFF_IN_PROGRESS, ILLEGAL_ENUM

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/02-facts.toml|handoff.status|HANDOFF_IN_PROGRESS`
Expected diagnostic: `halucinator/handoff/02-facts.toml|handoff.status|ILLEGAL_ENUM`
Expected diagnostic: `halucinator/handoff/06-driver-schema-demo.toml|driver.facts_handoff|DEPENDENCY_NOT_READY`
Expected diagnostic: `halucinator/state.toml|stages.extract-facts.status|DEPENDENCY_NOT_READY`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/07-in-progress-handoff/generation-roots/fictional-pac
```

Expected exit code: 1.
