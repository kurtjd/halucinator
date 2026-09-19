# Validator contract

Python 3.11+, standard library only. CLI: `python .opencode/schema/validate.py ROOT [--root generation:<name>=<absolute-path>]... [--kind all|state|01-sources|02-facts|03-svd|04-pac|05-platform|06-driver|07-tests|08-review]`. Exit 0 valid, 1 validation failure, 2 invocation/environment/read failure. Default all. The validator not running is never acceptance.

Diagnostics on stderr, sorted:

```text
ERROR <root-qualified-path>:<dotted-field> [<CODE>] expected <expectation>; found <repr<=160>; action: <remedy>
```

Use `-` for whole file. No expected-invalid traceback.

## Closed diagnostic codes

This vocabulary is closed. Adding, removing, or renaming a code is schema-version-affecting. Emit the most specific applicable code; `HANDOFF_IN_PROGRESS` takes precedence over generic `ILLEGAL_ENUM` when committed `handoff.status` is `in-progress`.

| Code | Emission rule |
|---|---|
| `UNKNOWN_FIELD` | A table contains a field its schema does not define. |
| `MISSING_FIELD` | A required field is absent. |
| `ILLEGAL_ENUM` | An enum value is illegal, or a cross-artifact binding names a target of the wrong kind or no target at all, except committed `in-progress`. |
| `DEPENDENCY_NOT_READY` | A ready handoff depends on a non-ready required stage. |
| `INPUT_HASH_MISMATCH` | A `handoff.inputs` digest does not match raw bytes. |
| `STALE_EVIDENCE` | Any other evidence FileRef no longer matches. |
| `STALE_REVIEW` | Reviewed artifact/dependency bytes no longer match. |
| `HANDOFF_IN_PROGRESS` | Committed handoff uses lock-only status `in-progress`; takes precedence over `ILLEGAL_ENUM`. |
| `LOCK_COMPLETE_CONFLICT` | A lock exists for a state-ready stage. |
| `NARROWED_READY_SCOPE` | Ready coverage silently narrows declared scope. |
| `PATH_ESCAPE` | A path escapes or violates its selected root. |
| `NONCANONICAL_DIGEST` | A digest is not 64 lowercase hexadecimal characters. |
| `MALFORMED_LOCK` | A lock violates its structural schema. |
| `REVIEW_NONACCEPTING` | A required review is absent, stale, or not `ready`. |
| `DRIVER_API_LEAK` | Tester-facing `driver.public_api` contains a forbidden token. |
| `CHECK_MISSING` | A canonical check ID is omitted. |
| `NOT_APPLICABLE_NO_REASON` | A not-applicable check lacks a nonempty reason. |
| `COVERAGE_PARTITION` | Complete/incomplete do not exactly partition included scope. |
| `ROUTE_INCOMPATIBILITY` | Sources and SVD routes are incompatible. |
| `DEPENDENCY_IDENTITY` | Dependency identity is absent or empty. |
| `LOCK_ID_UNSAFE` | Lock filename is not the mandated safe slug-plus-digest. |
| `SCHEMA_VERSION` | Schema version is unsupported. |
| `FIRST_PERIPHERAL_MODES` | First peripheral and nonempty modes are not co-present. |
| `FOUNDATION_PARTITION` | PAC foundation entries do not exactly partition requirements. |
| `SCOPE_DELETED_PREDECESSOR` | A scope predecessor is referenced but absent. |
| `SCOPE_SECOND_INITIAL` | More than one scope decision claims initial lineage. |
| `SCOPE_FORK` | One scope decision has multiple successors. |
| `SCOPE_ORPHAN` | A scope node is disconnected from the chain. |
| `SCOPE_CYCLE` | Scope lineage contains a cycle. |
| `RESOURCE_LIMIT` | A declared validation bound is exceeded. |
| `PATH_INSPECTION` | Safe path/reparse inspection cannot be completed. |
| `ATTRIBUTES_UNVERIFIED` | Required Git byte policy cannot be established. |
## Structural validation

Reject parse errors, unknown fields/versions, missing fields, wrong types (boolean is not integer), invalid enums/IDs/tagged variants, duplicate/unsorted sets, filename/body mismatch, invalid paths, and scope/status/check invariants. Compute each kind's exact check-ID set from its schema: every listed ID appears exactly once, no invented ID. Enforce each conditional predicate over fields in that handoff; applicable checks cannot be not-applicable, and inapplicable checks must be not-applicable with reason. Ready requires every applicable check passed. For `driver.public_api`, case-sensitive occurrence of either closed forbidden token `pac::` or `unsafe {` emits `DRIVER_API_LEAK`; this is an obvious-leak tripwire, not proof of leak freedom.

Discover every `halucinator/scope/scope-*.toml` file, bounded by resource limits. Validate all files, not only the current reference. They must form exactly one connected append-only chain: exactly one initial node; every revision node has one present hash-matching predecessor; every non-tip has exactly one successor; no orphan, fork, cycle, duplicate revision, or unreachable node; and state points to the unique tip with matching hash. Previous decisions may never be deleted. A handoff pinned to a noncurrent revision is historical and cannot be current/consumed. Validate foundation requirements by exact ID/kind/location equality and exact covered/missing partition. Validate dependency identity nonempty and first-peripheral/modes co-presence.

Dependency graph for ready: sources none; facts requires ready sources; SVD requires ready sources and, for author route, ready facts; PAC requires ready SVD plus current coordinator decisions; platform requires ready PAC; driver requires ready platform; tests resolves `tests.api_handoff` by path to an existing `06-driver` handoff, rehashes its raw bytes, and, when tests is ready, requires that exact driver handoff to be ready (suite and driver names need not match, and a binding that resolves to nothing or to another kind emits `ILLEGAL_ENUM` at any status); review requires parseable current reviewed artifact. A partial upstream permits only partial disposable downstream work under the common consumption contract; blocked forbids starting consumption. PAC/state continuity is exact: `pac.cargo_chip_feature` equals current `state.decisions.cargo_chip_feature`, and `pac.rust_compilation_target` equals current `state.decisions.rust_compilation_target`; either mismatch emits `DEPENDENCY_NOT_READY`. For every state stage entry, `state.stages[].status` equals the referenced handoff's `handoff.status`; mismatch emits `DEPENDENCY_NOT_READY`, including state `ready` referencing a partial or blocked handoff.

A review handoff pins reviewed artifacts, not the mutable producer handoff; pinning the latter would create a finalization hash cycle. An `independent-review` check passes only when evidence is an `08-review` FileRef whose verdict is ready, scope revision matches, all dependency hashes remain current, and the reviewed artifact matches the producer kind. PAC compares `review.artifact` with `pac.crate_manifest`; platform compares it with `platform.crate_manifest`; tests compare it with `tests.review_input_manifest`. For a driver, the reviewed artifact is the complete set of `driver.owned_files`: compare it order-independently with the review handoff's `handoff.inputs`, reject duplicates on either side, and require exact FileRef equality with no missing or extra path/hash pair. Driver set mismatch emits `STALE_REVIEW`. `review.artifact` must be one member of that driver input set and identifies the primary artifact only; it does not replace the set comparison. Review itself has no independent-review check, avoiding a cycle.

Hash every FileRef raw bytes with SHA-256: no decoding, BOM/newline transformation, or Windows conversion. All evidence paths, including handoff inputs and non-review checks, are rehashed. Replacing a deterministic current handoff changes its bytes and yields `STALE_EVIDENCE` for every old pin; review artifact/dependency mismatch additionally yields `STALE_REVIEW`. Re-attestation follows `handoff-common.md`, never deletion. Directories cannot be hashed.

## Authoritative static fixture cases

The validator's static rejection suite is exactly: `01-unknown-field`, `02-missing-required`, `03-illegal-enum`, `04-ready-dependency-not-ready`, `05-input-hash-mismatch`, `06-stale-review`, `07-in-progress-handoff`, `08-lock-complete-conflict`, `09-narrowed-ready-scope`, `10-path-escape`, `11-noncanonical-digest`, `12-malformed-lock`, `13-review-nonaccepting`, `14-driver-api-private-leak-key`, `15-omitted-mandatory-check`, `16-not-applicable-without-reason`, `17-incomplete-status-partition`, `18-stale-non-review-evidence`, `19-route-incompatibility`, `20-missing-dependency-identity`, `21-windows-unsafe-lock-id`, `22-unknown-schema-version`, `23-first-peripheral-without-modes`, `24-foundation-partition-missing`, `25-scope-deleted-predecessor`, `26-scope-second-initial`, `27-scope-fork`, `28-scope-orphan`, `29-scope-cycle`, `30-tests-bound-to-blocked-driver`, `31-tests-api-handoff-wrong-kind`, and `32-noncanonical-singleton-filename`. This list must equal `fixtures.md`.
## Git byte policy

Raw hashes require the destination root `.gitattributes` policy M3 must install:

```gitattributes
halucinator/state.toml text eol=lf
halucinator/scope/*.toml text eol=lf
halucinator/handoff/*.toml text eol=lf
halucinator/docs/**/*.md text eol=lf
halucinator/docs/**/sources/** -text
halucinator/pac/** -text
halucinator/candidates/** text eol=lf
halucinator/.run/*.lock text eol=lf
examples/** text eol=lf
embassy-unobtainium/** text eol=lf
```

More-specific project rules may classify PAC text files as `text eol=lf`, but generated/source bytes must have an explicit policy. The validator reads the destination-root `.gitattributes` and requires the mandated lines literally; it does not invoke `git check-attr`. Missing declarations emit `ATTRIBUTES_UNVERIFIED` and block ready handoffs. The validator does not evaluate Git precedence or nested overrides; portable hash policy remains unverified against effective Git attributes.

## State and locks

Recompute state stage-handoff hashes/backlinks. Validate lock filenames from canonical IDs, resources, timestamps, and kinds. State-ready plus matching lock is error. Intersecting resources are error. Classify live/interrupted/ambiguous as `layout.md`; never delete. Validate state generation nonnegative; mutation CAS is operational protocol, not reconstructable after the fact.

## Named roots and Windows safety

Require exactly one CLI binding for each named generation root used by selected artifacts, reject undeclared/unused duplicate bindings, and resolve each once. Reject duplicate root names. Apply component-safe algorithm from `layout.md` using `os.path.splitdrive`, `pathlib`, `os.lstat`, Windows reparse metadata where available, `os.path.commonpath`, and case-normalized volume/component comparisons. Never use string-prefix containment. Refuse unsupported reparse-point inspection rather than following it. A generation binding itself must be absolute, must not use drive-relative (`C:foo`), UNC/device namespace unless explicitly authorized as that exact binding, and must exist as a directory; artifact paths remain relative within it.

## Resource bounds

Before content validation: at most 256 schema TOML files, 4096 total referenced files, 8 MiB per TOML/Markdown/evidence file, 64 MiB per opaque source/artifact file, TOML/table nesting depth 12, array length 4096, string length 64 KiB, and traversed path components 64. Never recursively walk artifact directories; discover only fixed schema globs and explicit refs. Track visited directories by `(volume,file-id)` where available, otherwise resolved canonical path, and stop on repeats. Any limit or inability to inspect a junction/reparse point is exit 1 with `RESOURCE_LIMIT` or `PATH_INSPECTION`, not truncation.

Raw-colon lock filenames cannot be materialized on NTFS. Static fixture `21-windows-unsafe-lock-id` therefore covers the representable percent-encoded-colon bypass of the required slug-plus-digest algorithm; raw-colon rejection requires an operational test.

Fixture `17-incomplete-status-partition` means the authorable coverage-partition violation: complete/incomplete fail to partition included scope. The partial-status predicate is not independently falsifiable in a static fixture without also fabricating an accepting independent review.

CAS mismatch during concurrent publication, live-lock classification requiring a real PID/clock, and consuming a partial input to mutate canonical or production artifacts are operational violations outside static validation; they are not static fixture cases.

## Explicit limits

The validator checks shape, identity, status, dependency, and freshness. It does not verify PDF citations, hardware truth, semantic completeness of prose, behavioral correctness, trait compliance, authorization authenticity, electrical safety, generated-code provenance, honest execution, or cross-clone crash state. Review-check applicability derived from reviewed producer contents is not machine-proven; `upstream-contracts-reviewed` may be not-applicable only with a reviewer-audited reason. Scope-dependent facts-category completeness, and whether driver scope requires a public hardware-test record, are reviewer-enforced and not mechanically inferred. Resource limits, reparse-point refusal, Windows reserved-name rejection, and live-lock classification are implemented but unexercised by fixtures and remain unverified surface. `.run` cannot close F8. Foundation `location` is opaque: exact equality does not prove semantic sufficiency. API leak detection cannot prove free-form public material contains no implementation clue. State generation/CAS protects cooperating writers only and cannot detect tampering or reconstruct overwritten history. External-root authorization authenticity is not proven. A green result is necessary, never sufficient.