# Validator contract

Python 3.11+, standard library only, with exactly one deliberate exception: the citation verifier shells out to `pdftotext` from a single isolated function. CLI: `python .opencode/schema/validate.py ROOT [--root generation:<name>=<absolute-path>]... [--kind all|state|01-sources|02-facts|03-svd|04-pac|05-platform|06-driver|07-tests|08-review]`. Exit 0 valid, 1 validation failure, 2 invocation/environment/read failure. Default all. The validator not running is never acceptance.

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
| `CITATION_UNVERIFIED` | A source ID has no unique `SourceDocument`; the CitationRef source differs from the bound document; format and location variant disagree; `pdftotext` is absent, fails, times out, overflows or exits nonzero; UTF-8 source bytes are invalid; the location is out of range; an excerpt constraint fails; or neither normalized matching attempt succeeds. The remedy names the cause and the exact command, and for a missing binary it names the package: install `poppler-utils` (or `xpdf-utils` where that package supplies `pdftotext`), then rerun `pdftotext -layout -f <page> -l <page> <source> -`. |
| `BOARD_INTERLOCK_CONFLICT` | A new claimant's post-create rescan finds any other structurally valid lock with an intersecting `board:<board_id>` resource classified live or ambiguous, or an operation's epoch or check token does not equal the current lock. The new claimant removes only its own new lock and fails; an existing lock is never touched. |
| `BOARD_RECOVERY_REQUIRED` | A lock is interrupted; process identity is ambiguous or a PID was reused; child operation completion or quiescence is unconfirmed; board state is unknown; a safe-state record is absent, mismatched, or carries an unknown hazard or an outstanding human action; recovery lineage is invalid; or release is requested before `recovery-verified` and a safe board state. |

## Citation verification

For `format="pdf"` the validator itself runs `pdftotext -layout -f N -l N SOURCE -`, where `N` is the one-based physical PDF page ordinal. For `format="utf8-text"` it decodes the hash-pinned bytes as strict UTF-8 and narrows to the inclusive one-based line range. Agent-authored extraction files are not consulted and are not representable in the schema: trusting one would make the gate assert only that an agent copied its own text.

`run_pdftotext` is the only function in this validator permitted to invoke an external program. It uses argument-array execution with no shell, a 30-second timeout, captured stdout and stderr, and a 16 MiB output cap. A missing executable, timeout, nonzero exit, output overflow or decode failure emits `CITATION_UNVERIFIED` for that citation and validation continues for every other file and check. It never skips, never aborts the run, and never converts the gate to not-applicable. All other validator code is Python 3.11 standard library only and invokes no external executable.

Normalization is deliberately aggressive, because false-rejecting an honest register-table excerpt would get the gate routed around, which is worse than a wider match. Source and excerpt are NFKC-normalized and fully case-folded; soft hyphens are removed; CRLF, CR, LF, U+0085, U+2028 and U+2029 collapse to one line separator; a line-end ASCII hyphen is rejoined only when the nearest non-horizontal character on both sides is a Unicode letter or mark, so `FIFO-` followed by `0` stays two tokens and digit-bearing ranges are never altered; every remaining whitespace run becomes one space. Attempt 1 is exact substring matching on the normalized strings. Attempt 2 tolerates column interleaving: excerpt tokens must occur in order and exactly, with at most eight nonmatching source tokens between adjacent excerpt tokens and at most `min(256, 2*excerpt_token_count)` skipped tokens overall. An excerpt over 256 tokens or a selected region over 100,000 tokens emits `RESOURCE_LIMIT`, never a truncated match.

**Every viable start is inspected.** Attempt 2 tries every position at which the excerpt's leading token occurs, not a capped prefix of them: capping the search false-rejects an honest excerpt that begins with a common word, and a gate that false-rejects honest evidence is a gate people route around. The search carries a declared work bound; reaching it emits `RESOURCE_LIMIT` and never a finding that the excerpt is absent, because reporting absence about a region the verifier did not finish searching is that same false rejection wearing a different code. The nearest-candidate diagnostic likewise inspects every start; when the exact span-by-span scoring would exceed its own bound, a sliding multiset-overlap prefilter over the whole region selects the windows that are scored exactly, and the diagnostic says which scan it performed.

**A worked consequence of the gap budget, stated rather than buried.** Excerpt tokens `reset value zero` match source tokens `reset unrelated value unrelated zero`, because each gap is within the eight-token bound and the total is within the budget. Ordered-token occurrence is not visual contiguity and not quotation: aggressive normalization buys tolerance of real column layout and pays for it in exactly this way. A reviewer comparing the claim against the rendered page is the only thing that catches an excerpt assembled this way.

Failure is closed but never mysterious. The `CITATION_UNVERIFIED` payload is bounded to 2048 UTF-8 bytes and reports the assertion ID, source ID and hash, the physical page or line range, the exact attempted command with paths quoted for display, the attempt-1 normalized excerpt, the attempt-2 token list, and the closest candidate window scored with `difflib.SequenceMatcher` to four decimals. Truncation is marked. Secrets and unrelated source bytes are never printed.

**What it proves:** either exact normalized substring occurrence, or exact ordered-token occurrence within the stated gap bounds, at the selected location, derived by the verifier from hash-pinned authoritative bytes bound to the cited source ID.

**What it cannot prove:** visual contiguity, semantic entailment, OCR correctness, the truth of a title or revision beyond the catalog record, vendor truth, or that an agent ever invoked this validator. Aggressive normalization raises false-match risk, and column interleaving can manufacture an adjacency that is not present as one visual quotation. Independent review must compare claim, excerpt, rendered source and locator.
## Structural validation

Reject parse errors, unknown fields/versions, missing fields, wrong types (boolean is not integer), invalid enums/IDs/tagged variants, duplicate/unsorted sets, filename/body mismatch, invalid paths, and scope/status/check invariants. Compute each kind's exact check-ID set from its schema: every listed ID appears exactly once, no invented ID. Enforce each conditional predicate over fields in that handoff; applicable checks cannot be not-applicable, and inapplicable checks must be not-applicable with reason. Ready requires every applicable check passed. For `driver.public_api`, case-sensitive occurrence of either closed forbidden token `pac::` or `unsafe {` emits `DRIVER_API_LEAK`; this is an obvious-leak tripwire, not proof of leak freedom.

Discover every `halucinator/scope/scope-*.toml` file, bounded by resource limits. Validate all files, not only the current reference. They must form exactly one connected append-only chain: exactly one initial node; every revision node has one present hash-matching predecessor; every non-tip has exactly one successor; no orphan, fork, cycle, duplicate revision, or unreachable node; and state points to the unique tip with matching hash. Previous decisions may never be deleted. A handoff pinned to a noncurrent revision is historical and cannot be current/consumed. Validate foundation requirements by exact ID/kind/location equality and exact covered/missing partition. Validate dependency identity nonempty and first-peripheral/modes co-presence.

Dependency graph for ready: sources none; facts requires ready sources; SVD requires ready sources and, for author route, ready facts; PAC requires ready SVD plus current coordinator decisions; platform requires ready PAC; driver requires ready platform; tests resolves `tests.api_handoff` by path to an existing `06-driver` handoff, rehashes its raw bytes, and, when tests is ready, requires that exact driver handoff to be ready (suite and driver names need not match, and a binding that resolves to nothing or to another kind emits `ILLEGAL_ENUM` at any status); review requires parseable current reviewed artifact. A partial upstream permits only partial disposable downstream work under the common consumption contract; blocked forbids starting consumption. PAC/state continuity is exact: `pac.cargo_chip_feature` equals current `state.decisions.cargo_chip_feature`, and `pac.rust_compilation_target` equals current `state.decisions.rust_compilation_target`; either mismatch emits `DEPENDENCY_NOT_READY`. For every state stage entry, `state.stages[].status` equals the referenced handoff's `handoff.status`; mismatch emits `DEPENDENCY_NOT_READY`, including state `ready` referencing a partial or blocked handoff.

A review handoff pins reviewed artifacts, not the mutable producer handoff; pinning the latter would create a finalization hash cycle. An `independent-review` check passes only when evidence is an `08-review` FileRef whose verdict is ready, scope revision matches, all dependency hashes remain current, and the reviewed artifact matches the producer kind. PAC compares `review.artifact` with `pac.crate_manifest`; platform compares it with `platform.crate_manifest`; tests compare it with `tests.review_input_manifest`. For a driver, the reviewed artifact is the complete set of `driver.owned_files`: compare it order-independently with the review handoff's `handoff.inputs`, reject duplicates on either side, and require exact FileRef equality with no missing or extra path/hash pair. Driver set mismatch emits `STALE_REVIEW`. `review.artifact` must be one member of that driver input set and identifies the primary artifact only; it does not replace the set comparison. Review itself has no independent-review check, avoiding a cycle.

Hash every FileRef raw bytes with SHA-256: no decoding, BOM/newline transformation, or Windows conversion. All evidence paths, including handoff inputs and non-review checks, are rehashed. Replacing a deterministic current handoff changes its bytes and yields `STALE_EVIDENCE` for every old pin; review artifact/dependency mismatch additionally yields `STALE_REVIEW`. Re-attestation follows `handoff-common.md`, never deletion. Directories cannot be hashed.

## Authoritative static fixture cases

The validator's static rejection suite is derived from `tools/schema-fixtures.toml`, which is the single in-tree source of both the fixture set and its expected diagnostics. It is exactly: `01-unknown-field`, `02-missing-required`, `03-illegal-enum`, `04-ready-dependency-not-ready`, `05-input-hash-mismatch`, `06-stale-review`, `07-in-progress-handoff`, `08-lock-complete-conflict`, `09-narrowed-ready-scope`, `10-path-escape`, `11-noncanonical-digest`, `12-malformed-lock`, `13-review-nonaccepting`, `14-driver-api-private-leak-key`, `15-omitted-mandatory-check`, `16-not-applicable-without-reason`, `17-incomplete-status-partition`, `18-stale-non-review-evidence`, `19-route-incompatibility`, `20-missing-dependency-identity`, `21-windows-unsafe-lock-id`, `22-unknown-schema-version`, `23-first-peripheral-without-modes`, `24-foundation-partition-missing`, `25-scope-deleted-predecessor`, `26-scope-second-initial`, `27-scope-fork`, `28-scope-orphan`, `29-scope-cycle`, `30-tests-bound-to-blocked-driver`, `31-tests-api-handoff-wrong-kind`, `32-noncanonical-singleton-filename`, `33-citation-excerpt-absent`, `34-citation-source-unbound`, `35-destination-crate-nonroot`, `36-board-interlock-conflict`, and `37-board-recovery-required`. This list must equal `fixtures.md`.
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

Hash and occurrence checks prove bytes and the bounded relation stated, nothing wider; the claimant may still have fabricated execution evidence. No external attester exists, and no check here can detect that class of falsehood. M6 does not propagate beyond declared current one-hop bindings; cycles/missing graph nodes are not represented. Transitive dependency invalidation is deferred to post-M7, so a stale hash two hops upstream is not reported and a reader must not infer that it is handled.

The validator checks shape, identity, status, dependency, and freshness. It verifies citations only in the exact, bounded sense described above; it does not verify hardware truth, semantic completeness of prose, behavioral correctness, trait compliance, authorization authenticity, electrical safety, generated-code provenance, honest execution, or cross-clone crash state. Review-check applicability derived from reviewed producer contents is not machine-proven; `upstream-contracts-reviewed` may be not-applicable only with a reviewer-audited reason. Scope-dependent facts-category completeness, and whether driver scope requires a public hardware-test record, are reviewer-enforced and not mechanically inferred. Resource limits, reparse-point refusal, Windows reserved-name rejection, and live-lock classification are implemented but unexercised by fixtures and remain unverified surface. `.run` cannot close F8. Foundation `location` is opaque: exact equality does not prove semantic sufficiency. API leak detection cannot prove free-form public material contains no implementation clue. State generation/CAS protects cooperating writers only and cannot detect tampering or reconstruct overwritten history. External-root authorization authenticity is not proven. A green result is necessary, never sufficient.