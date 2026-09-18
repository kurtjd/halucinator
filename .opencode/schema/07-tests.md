# `07-tests-<name>.toml`

Stage `write-tests`; filename name equals `tests.name`.

Required: `tests.name`; `output_kind=example|validation|both`; `execution_scope=build-only|hardware-validation`; `api_handoff` FileRef; `owned_files` ArtifactRef[]; `dependencies` Dependency[]; `setup_record` FileRef for hardware-validation and absent for build-only; `review_input_manifest` ArtifactRef; `[[tests.coverage]]`; `[[tests.hardware_runs]]`. Produced/consumed by `write-examples/SKILL.md:42-172` and `test-record.md:25-110`.

Coverage is exact `{id,status,test_case,evidence}` for passed/failed/blocked, or `{id,status="not-applicable",test_case,reason}`. `test_case` always names the case; `reason` is separate. Hardware run is `{test_case,status,evidence,teardown}` for blocked/failed/passed; for `not-run`, evidence is absent and teardown is `not-applicable`. Evidence is always FileRef when present.

Canonical checks:

| ID | Rule | Source |
|---|---|---|
| `workflow-references-read` | mandatory | `write-examples/SKILL.md:19-23`. |
| `live-conventions-read` | mandatory | `write-examples/SKILL.md:69-80`. |
| `format-lint` | mandatory | `write-examples/SKILL.md:105-110`. |
| `target-build-link` | mandatory | same. |
| `build-only-ci` | mandatory | `write-examples/SKILL.md:112-124`. |
| `hardware-admission` | conditional on hardware-validation | `hardware-execution.md:14-83`. |
| `hardware-execution` | conditional on hardware-validation | `hardware-execution.md:85-115`. |
| `independent-review` | mandatory | `write-examples/SKILL.md:156-166`. |

Hardware-admission evidence must record exact device/runner/operations, electrical setup facts, readiness, authorization, RAM/link/load facts, and observation path. Ready build-only has all hardware runs `not-run`; ready hardware-validation has every required applicable run passed with safe teardown.