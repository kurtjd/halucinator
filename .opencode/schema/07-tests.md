# `07-tests-<name>.toml`

Stage `write-tests`; filename name equals `tests.name`.

Required: `tests.name`; `output_kind=example|validation|both`; `execution_scope=build-only|hardware-validation`; `api_handoff` FileRef; `owned_files` ArtifactRef[]; `dependencies` Dependency[]; `setup_record` FileRef for hardware-validation and absent for build-only; `review_input_manifest` ArtifactRef; `[[tests.coverage]]`; `[[tests.hardware_runs]]`. Produced/consumed by `write-examples/SKILL.md:42-172` and `test-record.md:25-110`.

Coverage is exact `{id,status,test_case,evidence}` for passed/failed/blocked, or `{id,status="not-applicable",test_case,reason}`. `test_case` always names the case; `reason` is separate. Evidence is always FileRef when present.

## Worktree-local interlock and safe-state records

Hardware-validation records bind to the worktree-local, single-operator board interlock described in `layout.md`. It is a strong default and a statement of intent, not a sandbox: it does not exclude another clone, another worktree, or another operator, and a direct probe command bypasses it entirely.

| Field | Type | Required |
|---|---|---:|
| `tests.board_interlock` | exact `{board_id,lease_epoch,check_token,authorization}` with FileRef `authorization` | hardware-validation only; forbidden for build-only |
| `tests.safe_state_procedure` | `SafeStateProcedureRef` | hardware-validation only; forbidden for build-only |
| `tests.recovery_attempts` | ordered FileRef[], copied exactly from the lock before release | hardware-validation only; may be empty |

Each hardware run is exact `{test_case,status,teardown,lease_epoch,operation_attempt,operation_id,pre_safe_state,post_safe_state?,evidence?}`. For `not-run`, evidence is absent, teardown is `not-applicable`, and the epoch/attempt/operation and safe-state members are absent. Every other status records the epoch, a nonnegative attempt, the operation ID, and a `pre_safe_state` FileRef; `post_safe_state` is required for `passed` and `failed` and may be absent only for `blocked`, which forces recovery.

`SafeStateProcedureRef` is exact `{board_id,facts_handoff,assertion_ids,procedure}`. It binds the procedure to one physical device identity and to verified assertions in a ready `02-facts` handoff. It does not prove the procedure is physically sufficient; that judgement is review's.

A `SafeStateObservation` is a standalone record carrying `schema`, `board_id`, `lease_epoch`, `operation_attempt`, optional `operation_id`, `observed_at`, a `SafeStateProcedureRef`, exactly six `HazardObservation` entries - one each for `outputs`, `dma`, `interrupts`, `external-loads`, `reset-halt`, `probe` - and `outstanding_human_actions`. Any hazard observed `unknown`, any missing hazard kind, or any outstanding human action means the board is not safe. Recovery-attempt records are append-only: a retry writes a new numbered file and appends its FileRef; removal, reordering, replacement, and nonconsecutive attempt numbers are refused.

Holder death is not operation death. A probe or runner child may still be transferring or driving pins after the process that launched it has gone, so device state is declared unknown before any reconnect - attaching a debugger is itself a target-affecting operation. Publication order is fixed: raw operation evidence, then post-safe-state evidence, then the observation record, then the lock update to safe or `recovery-verified`, then the exact recovery lineage copied into the pending handoff material, then a re-read and verify, then interlock release, and only then this handoff. A lock is never released on the strength of a handoff published later.

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