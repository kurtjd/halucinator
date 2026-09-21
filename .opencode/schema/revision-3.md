# Revision 3 final audit

## Directive disposition

| Directive | Disposition | Landing |
|---|---|---|
| A-1 | closed | `state.md#immutable-scope-decision`; `validate.md#structural-validation`; fixtures 25-29. |
| A-2 | closed | `layout.md` current-record/hash-pin model; stale replacement in `validate.md`. |
| A-3 | closed | Mirror booleans deleted from 04/05/06; canonical check applicability rules. |
| A-4 | closed | Fields deleted or readers cited in state; final audit below. |
| A-5 | closed | Cooperative-only limitation in `layout.md` and `validate.md`. |
| B-1 | closed | Clock anomaly/PID precedence in `layout.md`. |
| B-2 | closed | Global re-attestation in `handoff-common.md`. |
| B-3 | closed | Scope publication ordering in `state.md`. |
| B-4 | closed | `layout.md` says v1 reserves identities and enumerates M6 additions. |
| C-1 | closed | Review example pins the reviewed PAC inventory artifact, not the mutable PAC handoff. |
| C-2 | closed | Fixtures/worked examples both enumerate ten TOML documents. |
| C-3 | closed | Static fixtures 25/26 dropped; operational limitation in `validate.md`. |
| C-4 | closed | `fixtures.md#hash-materialization-order`. |
| C-5 | closed | Normative limits moved into `validate.md`. |
| C-6 | closed | Mechanical set reduced to five exact tokens in terminology/selfcheck. |
| C-7 | closed | GPIO/time rows reclassified in `traceability.md`. |
| C-8 | closed | Blockers forbidden for partial; check outcomes/coverage carry remainder. |

## Complexity delta from revision 2

Removed nine field paths: seven mirror booleans, `pac.api_locations`, and `Dependency.contract`. Added no artifact field. Net **-9 fields**. Added only validator/protocol rules, not persisted schema structures.

## Final writer-reader audit method

Method: enumerate every normative field declaration and every nested record member across common, state, 01-08, and lock schema; grep all schema documents/examples for the exact field token; require one producing skill/agent citation and one consuming skill/agent or named operational component. Grouping below is exhaustive by record rather than repeating identical primitive members.

| Record/fields | Writer | Named reader |
|---|---|---|
| common handoff header/status/inputs/notes/blockers | owning stage | validator and immediate downstream admission (`AGENTS.md:236-246`) |
| scope revision/decision; coverage | architect decision + owning stage | validator and all scoped consumers (`generate-svd/SKILL.md:43-50`) |
| checks id/status/evidence/reason | owning stage | validator, reviewer, closure gates |
| FileRef/PathRef members | owning record | validator/path resolver/hash checker |
| CitationRef members | datasheet/stage | SVD/driver/test/reviewer citation gates (`hal-datasheet.md:140-153`) |
| Dependency crate/identity/features | scaffold/driver/test producer | time-driver intake (`write-time-driver/SKILL.md:68-70`) and builds |
| state schema/generation | state mutation tool | M3 cooperative CAS writer and validator; not tamper detection |
| target fields/package tag | documentation intake/architect | SVD/scaffold consumers (`generate-svd/SKILL.md:43-50`; `scaffold-hal/SKILL.md:55-70`) |
| state scope/current decision | architect | validator/downstream stages |
| architect decisions/foundation requirements | architect before PAC dispatch | PAC generator and scaffold (`generation-and-checks.md:98-175`) |
| documentation/source/PAC/SVD/generator/crate/roadmap roots | selecting owner | individual readers cited in `state.md` |
| external root name/authorization | architect/user | validator root binder/path safety |
| stage id/status/handoff | state writer | coordinator/validator (`AGENTS.md:147-151`) |
| scope decision schema/revision/previous/included/excluded/reason | architect | validator lineage plus downstream scope gates |
| 01 source fields | documentation intake | SVD intake (`generate-svd/SKILL.md:43-67`) |
| 02 fact fields | datasheet analyst | SVD and cited hardware consumers |
| 03 SVD recipe/result fields | SVD producer | PAC admission (`generation-and-checks.md:103-112`) |
| 04 PAC identity/features/foundation/fork fields | PAC producer | scaffold gate (`scaffold-hal/SKILL.md:90-112`) |
| 05 platform identity/contracts/dependencies/first driver fields | scaffold producer | GPIO/time driver intake |
| 06 driver/API/trait/fact/build/test fields | driver | tester and reviewer |
| 07 test scope/API/artifact/coverage/run fields | tester | reviewer and driver evidence record |
| 08 review artifact/scope/dependencies/findings/verdict/lineage | reviewer | independent-review checks and recheck resumption |
| lock common/state-update fields | lock/state tooling | validator and M3 cooperative state writer |
| board/PAC lock exception fields | future M6 components | reserved identities only; exception register in `layout.md` |

No non-M6 persisted field lacks a named reader. Free-form semantic sufficiency remains review-dependent and is stated as a validator limit.

## Deferred work

No new revision-3 directive is deferred. Existing M6 durable transaction/HIL recovery and M3 `.gitattributes` wiring remain as previously recorded. M6 TODO wording: “Using a schema-version transition, add owner fencing, operation phase/last operation, board recovery detail, PAC baseline and candidate manifests, and a durable recovery/transaction record outside `.run`; v1 lock identities alone do not provide recovery or transactionality.”

## Residual risk

The validator cannot prove opaque foundation locations or free-form tester API completeness, detect uncooperative state overwrite, prove authorization authenticity, or infer implementation leakage semantically. These are normative limits, not hidden claims.