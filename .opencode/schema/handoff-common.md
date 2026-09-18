# Common handoff contract

## Shared tables

Every handoff contains exactly `[handoff]`, `[scope]`, `[coverage]`, `[[checks]]`, and its kind-specific tables.

| Field | Type | Required | Meaning | Writer / reader trace |
|---|---|---:|---|---|
| `handoff.schema` | integer | yes | exactly `1` | Every stage boundary (`AGENTS.md:236-246`). |
| `handoff.stage` | enum | yes | `gather-documentation`, `extract-facts`, `generate-svd`, `generate-pac`, `scaffold-hal`, `write-driver`, `write-tests`, `review` | Pipeline (`AGENTS.md:109-151`). |
| `handoff.status` | enum | yes | `ready`, `partial`, `blocked` | Stage outputs (`generate-svd/SKILL.md:166-174`; `generate-pac/SKILL.md:100-106`; `test-record.md:85-99`). |
| `handoff.can_progress` | boolean | conditional | required exactly when status is not `ready` | Producers already distinguish actionable next work from external blockers in completion outputs; downstream admission consumes it (`generate-svd/SKILL.md:64-67`; `write-examples/SKILL.md:139-150`). |
| `handoff.inputs` | FileRef[] | yes | complete direct evidence inputs; only initial intake may be empty | Identity gates (`generate-svd/SKILL.md:52-56`; `generation-and-checks.md:119-124`). |
| `handoff.notes` | FileRef[] | yes | detailed records | Handoff policy (`AGENTS.md:236-252`). |
| `handoff.blockers` | string[] | yes | external actions preventing all progress; permitted only for `blocked` | Every completion contract. |
| `scope.revision` | scope-revision ID | yes | immutable scope decision ID | Scope gates (`generate-svd/SKILL.md:43-50`; `scaffold-hal/SKILL.md:60-70`). |
| `scope.decision` | FileRef | yes | matching immutable `halucinator/scope/<revision>.toml` | Same consumers; prevents silent scope rebasing (`generate-svd/SKILL.md:168-174`; `generate-pac/SKILL.md:102-106`). |
| `coverage.complete` | scope-item ID[] | yes | completed included IDs | Scoped completion gates above. |
| `coverage.incomplete` | scope-item ID[] | yes | unfinished included IDs | Same. |
| `checks` | Check[] | yes | one entry for every check ID defined by the artifact schema; no others | Existing per-stage gates, enumerated in each kind document. |

### Mutually exclusive status predicates

The immutable scope decision supplies `included`. Complete and incomplete are disjoint, duplicate-free, sorted, and their union equals included.

- `ready`: incomplete is empty, complete equals included, `can_progress` is absent, and blockers are empty.
- `partial`: `can_progress=true` and either incomplete is nonempty or at least one applicable check is `unrun`/`failed`; work can continue without an external action. Blockers are empty; remaining work is expressed by incomplete coverage and check outcomes.
- `blocked`: `can_progress=false`, blockers are nonempty, and either incomplete is nonempty or at least one applicable check is `unrun`/`failed`; no further scoped progress is possible without a named external action.

Thus zero completed items is representable as partial or blocked, and no durable state satisfies two statuses.

## Primitive types

- **Scope item ID:** 3-80 lowercase ASCII characters, grammar `[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*:[a-z0-9][a-z0-9._-]*`; unique within a decision. The namespace is an opaque owner/domain (`peripheral:gpio`, `foundation:reset-api`). It standardizes identity, not vendor spelling.
- **Scope revision ID:** `scope-` plus eight lowercase hexadecimal digits. It is an opaque minted ID, not a sequence claim.
- **PathRef:** exact `{path="..."}` for repository root or `{root="generation:<name>",path="..."}` for a named authorized root. See `layout.md`.
- **FileRef / ArtifactRef:** PathRef plus `sha256`, exactly 64 lowercase hexadecimal characters. **Test:** if changing file content should invalidate the claim, the field is a FileRef. Roots and directory/output locations alone may be PathRef.
- **CitationRef:** exact `{source_id,document,revision,locator,note}` where `note` is a FileRef. Every cited field is nonempty (`hal-datasheet.md:140-153`).
- **Check:** exact `{id,status,evidence}` for `passed|failed|unrun`, where evidence is FileRef; or `{id,status="not-applicable",reason}` with nonempty reason. Evidence and reason are mutually exclusive. Check IDs are closed per artifact kind.
- **Dependency:** exact `{crate,identity,features}`. `identity` is a nonempty exact version requirement or source revision and features is a sorted unique string array. Time-driver intake reads these (`write-time-driver/SKILL.md:68-70`); claimed trait semantics belong only in `trait_obligations`.

Unknown fields are invalid at every depth. Required strings are nonempty. Arrays declared as sets are sorted and unique; ordered recipe arrays retain order.

## Absence and tagged variants

Optional means key absence; empty collection means known empty. When unknown and inapplicable differ to a consumer, use a tagged table rather than absence:

- target package: `{kind="known",value="..."}`, `{kind="unknown"}`, or `{kind="not-applicable"}`;
- PAC revision: `{kind="revision",value="..."}` or `{kind="workspace"}`;
- review lineage: `{kind="initial"}` or `{kind="recheck",previous=<FileRef>}`.

Legacy null/status sentinels are forbidden in typed fields.

## Consumption contract

Validator success is necessary before consumption. `blocked` permits no downstream consumption. `partial` permits read-only inspection and disposable fresh-candidate work only: no canonical replacement, production-file mutation, hardware operation, or downstream `ready`. Consumers carry the upstream status, blockers, and incomplete coverage forward. `ready` permits normal admission subject to all other gates. Missing Python, Python below 3.11, timeout, validator error/nonzero exit, or not invoking the validator is **not a pass** and blocks consumption.


## Re-attestation after evidence changes

When referenced bytes legitimately change, preserve superseded evidence and review records, create replacement evidence, rerun only affected checks, obtain a new review where the changed bytes were reviewed, and replace the deterministic current handoff/state references through the state CAS. Never delete old evidence or old review records to regain validation. `review.lineage` records review rechecks only; it is not the general supersession mechanism.
## Schema evolution

Version 1 validators accept only `schema=1`. Any unknown version fails closed with `SCHEMA_VERSION`. A future version 2 requires a written migration specification, new fixtures, and an explicit rewrite into new files; validators never reinterpret version 1 or silently ignore version-2 fields. Existing version-1 evidence remains version 1 and is revalidated by its validator.