# Fixture expectations manifest

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

This file is the contract between the fixture author and the validator
implementer. `tools/selfcheck.py` check 3 asserts that each invalid fixture
exits 1 and emits the code recorded in its own `README.md`; the table below is
the same information in one place.

## Valid fixture

`fixtures/valid/` must exit **0** with **no diagnostics** when invoked as:

```text
python .opencode/schema/validate.py .opencode/schema/fixtures/valid/root \
  --root generation:fictional-pac=<abs>/.opencode/schema/fixtures/valid/generation-roots/fictional-pac
```

The `--root` binding must be an absolute path; `validate.md` forbids
drive-relative and guessed locations, so the caller (self-check) resolves it.

## Invalid fixtures

Each exits **1** and emits at least the named code on stderr, with a
diagnostic naming the listed file and field.

| Fixture | Code | File | Field | Code origin |
|---|---|---|---|---|
| `01-unknown-field` | `UNKNOWN_FIELD` | `halucinator/handoff/01-sources.toml` | `sources.note` | minted here |
| `02-missing-required` | `MISSING_FIELD` | `halucinator/handoff/01-sources.toml` | `sources.route` | minted here |
| `03-illegal-enum` | `ILLEGAL_ENUM` | `halucinator/handoff/01-sources.toml` | `sources.route` | minted here |
| `04-ready-dependency-not-ready` | `DEPENDENCY_NOT_READY` | `halucinator/handoff/04-pac.toml` | `handoff.inputs` | minted here |
| `05-input-hash-mismatch` | `INPUT_HASH_MISMATCH` | `halucinator/handoff/02-facts.toml` | `handoff.inputs` | minted here |
| `06-stale-review` | `STALE_REVIEW` | `halucinator/handoff/08-review-pac.toml` | `review.artifact` | named in `validate.md` |
| `07-in-progress-handoff` | `HANDOFF_IN_PROGRESS` | `halucinator/handoff/02-facts.toml` | `handoff.status` | minted here |
| `08-lock-complete-conflict` | `LOCK_COMPLETE_CONFLICT` | `halucinator/.run/review-pac-068841a2.lock` | `-` | minted here |
| `09-narrowed-ready-scope` | `NARROWED_READY_SCOPE` | `halucinator/handoff/01-sources.toml` | `coverage.incomplete` | minted here |
| `10-path-escape` | `PATH_ESCAPE` | `halucinator/handoff/06-driver-schema-demo.toml` | `driver.owned_files` | minted here |
| `11-noncanonical-digest` | `NONCANONICAL_DIGEST` | `halucinator/handoff/02-facts.toml` | `handoff.inputs` | minted here |
| `12-malformed-lock` | `MALFORMED_LOCK` | `halucinator/.run/write-driver-schema-demo-c100ce44.lock` | `-` | minted here |
| `13-review-nonaccepting` | `REVIEW_NONACCEPTING` | `halucinator/handoff/04-pac.toml` | `checks.independent-review` | minted here |
| `14-driver-api-private-leak-key` | `DRIVER_API_LEAK` | `halucinator/handoff/06-driver-schema-demo.toml` | `driver.public_api` | minted here |
| `15-omitted-mandatory-check` | `CHECK_MISSING` | `halucinator/handoff/04-pac.toml` | `checks` | minted here |
| `16-not-applicable-without-reason` | `NOT_APPLICABLE_NO_REASON` | `halucinator/handoff/03-svd.toml` | `checks.correction-effects` | minted here |
| `17-incomplete-status-partition` | `COVERAGE_PARTITION` | `halucinator/handoff/05-platform.toml` | `coverage.complete` | minted here |
| `18-stale-non-review-evidence` | `STALE_EVIDENCE` | `halucinator/handoff/02-facts.toml` | `handoff.notes` | named in `validate.md` |
| `19-route-incompatibility` | `ROUTE_INCOMPATIBILITY` | `halucinator/handoff/03-svd.toml` | `svd.route` | minted here |
| `20-missing-dependency-identity` | `DEPENDENCY_IDENTITY` | `halucinator/handoff/05-platform.toml` | `platform.dependencies` | minted here |
| `21-windows-unsafe-lock-id` | `LOCK_ID_UNSAFE` | `halucinator/.run/write-tests%3aschema-demo-ac472d03.lock` | `-` | minted here |
| `22-unknown-schema-version` | `SCHEMA_VERSION` | `halucinator/handoff/01-sources.toml` | `handoff.schema` | named in `validate.md` |
| `23-first-peripheral-without-modes` | `FIRST_PERIPHERAL_MODES` | `halucinator/state.toml` | `decisions.first_peripheral_modes` | minted here |
| `24-foundation-partition-missing` | `FOUNDATION_PARTITION` | `halucinator/handoff/04-pac.toml` | `pac.foundation` | minted here |
| `25-scope-deleted-predecessor` | `SCOPE_DELETED_PREDECESSOR` | `halucinator/scope/scope-1111bbbb.toml` | `previous` | minted here |
| `26-scope-second-initial` | `SCOPE_SECOND_INITIAL` | `halucinator/scope/scope-5555ffff.toml` | `previous` | minted here |
| `27-scope-fork` | `SCOPE_FORK` | `halucinator/scope/scope-2222cccc.toml` | `previous` | minted here |
| `28-scope-orphan` | `SCOPE_ORPHAN` | `halucinator/scope/scope-3333dddd.toml` | `previous` | minted here |
| `29-scope-cycle` | `SCOPE_CYCLE` | `halucinator/scope/scope-1111bbbb.toml` | `previous` | minted here |

## Diagnostic codes minted by this fixture set

`validate.md` specifies the diagnostic line shape and names only
`SCHEMA_VERSION`, `STALE_EVIDENCE`, `STALE_REVIEW`, `RESOURCE_LIMIT`,
`PATH_INSPECTION` and `ATTRIBUTES_UNVERIFIED`. The remaining 23 codes above are
**minted by this fixture set**, uniformly as the fixture slug in
`SCREAMING_SNAKE_CASE` with redundant words dropped. They are a proposal, not a
specification. If the coordinator prefers different spellings, change this table
and the per-fixture `README.md` files together; the validator must agree with
both.

## Known multi-code fixtures

Three fixtures unavoidably satisfy more than one rule because the defect
entails it. Each is still named for its primary rule:

- `06-stale-review` — `validate.md` line 23 states review artifact mismatch
  yields `STALE_REVIEW` *additionally* to the evidence-level code, so
  `STALE_EVIDENCE` is expected alongside it by specification.
- `27-scope-fork` — two tips necessarily also violate "state points to the
  unique tip".
- `29-scope-cycle` — a cycle cannot have hash-matching predecessor `FileRef`s
  in both directions, so a predecessor-hash mismatch is inherent to the case.

`26-scope-second-initial` and `28-scope-orphan` each produce one disconnected
node in addition to their named defect; a second initial node and a node with an
absent predecessor are disconnected by construction.
