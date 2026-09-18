# Consumer-precondition traceability, revision 2

Every row names an actual producer or classifies an execution-time condition. Check IDs are the same IDs specified in artifact schemas; there is no parallel gate vocabulary.

| Consumer (file:line) | Precondition | Producer | Field/check | Classification |
|---|---|---|---|---|
| `generate-svd/SKILL.md:43-50` | docs, source list, target, scope, part/core/revision | state + 01 + scope decision | roots/target; `sources.catalog`; `scope.*` | typed producer |
| `generate-svd/SKILL.md:52-56` | current input hashes/revisions | 01/common | FileRefs, `input-identity` | typed producer |
| `generate-svd/SKILL.md:58-67` | producer-evaluable route; facts for author route | 01 + 02 | `sources.route`; facts/citations/checks | typed producer |
| `generation-and-checks.md:98-112` | accepted scope, core, dependencies, exclusions, consumer requirements | `hal-coordinator` before PAC dispatch | state current scope/target/decisions/foundation requirements | typed coordinator decision; removed from 03 writer |
| `generation-and-checks.md:108-110` | source/SVD/recipe/check evidence | 03 | source/transforms/modes and closed checks | typed producer |
| `generation-and-checks.md:111` | representation-limit assessment | 03 | `information-limits` check evidence plus `svd.representation_limits` | typed producer |
| `generation-and-checks.md:112` | chip/runtime/metadata needs | `hal-coordinator` | state decisions/foundation requirements | typed producer |
| `scaffold-hal/SKILL.md:55-70` | target, package/board, PAC, immutable scope, feature/target, first peripheral/modes, roadmap | state + 04 | tagged package; decisions; roots; PAC fields | typed producer; modes co-required |
| `scaffold-hal/SKILL.md:84-89` | live DEVGUIDE/MCXA references available/read | executing scaffold agent | `live-reference-read` | execution-time external condition |
| `scaffold-hal/SKILL.md:90-96` | sources/citations/PAC provenance and exact foundation facts | 04 + state + 02 | PAC refs and exact foundation partition | typed producer; no broad categories |
| `scaffold-hal/SKILL.md:97-106` | every required foundation item present | 04 | `pac.foundation` exact partition; `foundation-coverage` | typed producer/gate |
| `scaffold-hal/SKILL.md:203-217` | format/lint, builds, negative selection, host tests, mappings, link, CI, review | scaffold agent + reviewer | closed 05 check IDs | execution evidence |
| `write-gpio/SKILL.md:60-66` | live implementation/reference availability | executing driver agent | `live-reference-read` | execution-time external condition |
| `write-gpio/SKILL.md:67-75` | source/PAC coverage and cited contracts | 05/04/02 | platform PAC/citations/foundation API/startup contract | typed producer |
| `write-gpio/SKILL.md:112-123` | software, trait, mapping, link/CI, review gates | driver + reviewer | closed 06 check IDs | execution evidence |
| `write-time-driver/SKILL.md:62-67` | live MCXA/time references | executing driver agent | `live-reference-read` | execution-time external condition |
| `write-time-driver/SKILL.md:68-70` | actual dependency versions/contracts | 05/06 | structured `dependencies` | typed producer |
| `write-time-driver/SKILL.md:71-76` | timer facts and PAC coverage | 05/04/02 | cited notes, PAC manifest/foundation | typed producer |
| `write-time-driver/SKILL.md:104-118` | build/arithmetic/mapping/tick/link/CI/review | driver + reviewer | closed 06 check IDs and dependency contracts | execution evidence |
| `gpio-validation.md:9-20` | exact identity/scope/public API/source/facts/features/target/init/interrupt/memory/observation | 06 + state | public API, dependency/trait/fact/build references | typed references plus semantic-completeness review; free-form material is not machine-proven |
| `time-validation.md:8-23` | public intake plus init/resources/rate/idle/observation/accuracy contracts | 06 | API/capabilities/dependencies/facts/build/requirements references | typed references plus semantic-completeness review; contract completeness is not machine-proven |
| `write-examples/SKILL.md:19-23` | required workflow references | executing tester | `workflow-references-read` | execution-time external condition |
| `write-examples/SKILL.md:27-65` | public-only API/facts and build target | 06 | tester-safe fields/FileRefs | typed producer |
| `write-examples/SKILL.md:69-80` | live example/HIL/build conventions | executing tester | `live-conventions-read` | execution-time external condition |
| `write-examples/SKILL.md:105-124` | format/build/link/CI | tester | 07 closed checks | execution evidence |
| `hardware-execution.md:14-83` | device/runner/operations, electrical facts, readiness, authorization, RAM/link/load, observation | user + tester public record | `hardware-admission` FileRef evidence; lock authorization FileRef | execution-time external admission |
| `hardware-execution.md:85-115` | bounded run/capture/teardown | tester | `hardware-execution`; hardware run evidence | execution evidence |
| `hal-reviewer.md:121-139` | contracts/citations/runs and applicable live references/manual sections | reviewed artifact + reviewer | review dependencies; closed review checks | typed + execution-time condition |
| `hal-reviewer.md:155-171` | scope/findings/full verdict | reviewer | 08 fields | typed producer |
| all review-gated closures | accepting current review | 08 | independent-review check FileRef, verdict/artifact/dependencies | typed producer |

## Field writer audit

- `hal-coordinator` alone writes target identity, immutable scope decisions, Cargo chip feature, Rust compilation target, first-driver decisions, and foundation requirements before dispatch (`.opencode/ownership.toml:207-219,282-284`). `hal-architect` writes only the architecture specification.
- Each specialist writes only its own handoff after possessing its result.
- Reviewer writes only 08; producer handoffs reference completed reviews as check evidence when closing.
- `hal-tester` authors test content, test evidence, and the 07 handoff in its own committed test-candidate tree; `hal-integrator` materializes durable records, including the canonical test record (`.opencode/ownership.toml:257-264`). The integrator materializes durable records; the tester never writes them.
- M6-only lock fields are listed centrally in `layout.md`; no other field lacks a current named reader.

Deleted for lack of a concrete reader: `sources.coverage`, `facts.suggested_public_types_note`, free PAC representation-limits field, bare platform public-contract note. Review recheck was retained only as tagged lineage because resumption/recheck gates read it.

## Result

This revision walks 30 grouped rows, including all eleven previously omitted execution-time preconditions. The previously overstated rows were re-derived: consumer requirements now come from state; preparation tool details are evidenced by closed checks/notes; first-driver choice is explicitly coordinator-owned; foundation coverage is exact; dependency versions are structured; tester/API and reviewer claims now name concrete fields rather than broad note categories.