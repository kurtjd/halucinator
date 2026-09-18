# `state.toml` and scope-decision schemas

## State

| Field | Type | Required | Meaning | Trace |
|---|---|---:|---|---|
| `schema` | integer | yes | `1` | Typed state boundary. |
| `generation` | integer | yes | nonnegative CAS generation | Shared durable stage state (`AGENTS.md:147-151`); concurrency guard for M3 writer. |
| `target.vendor`, `target.mcu_part_number`, `target.target_id`, `target.vendor_id` | string | yes | exact/normalized identity | `gather-documentation/SKILL.md:41-49`; `source-list-format.md:22-29`; `AGENTS.md:204-210`. |
| `target.package` | tagged package table | yes | known/unknown/not-applicable | Intake asks and permits unknown (`gather-documentation/SKILL.md:41-49`); scaffold consumes package (`scaffold-hal/SKILL.md:65`). |
| `target.silicon_revision`, `target.core`, `target.board`, `target.board_revision` | string | no | known values only | Same intake; core consumed at `generate-svd/SKILL.md:48-50`. |
| `scope.current_revision` | scope ID | yes | coordinator-selected immutable decision | Scope consumers above. |
| `scope.current_decision` | FileRef | yes | exact decision bytes | Prevents silent narrowed-ready relabeling. |
| `decisions.cargo_chip_feature`, `rust_compilation_target`, `destination_crate` | string/PathRef | no | coordinator-owned PAC/scaffold decisions | `generate-pac/SKILL.md:14-17`; `scaffold-hal/SKILL.md:62-70`. |
| `decisions.first_peripheral` | string | no | coordinator-selected next driver | `scaffold-hal/SKILL.md:67`. |
| `decisions.first_peripheral_modes` | string[] | no | required, nonempty exactly when first peripheral exists | Same. |
| `decisions.foundation_requirements` | FoundationRequirement[] | yes | coordinator-owned PAC consumer requirements established before PAC dispatch | `generation-and-checks.md:98-112,160-175`; supplied by `hal-coordinator` `generate-pac/SKILL.md:14-17`. |
| `roots.documentation`, `roots.sources`, `roots.pac_project`, `roots.svd_inputs`, `roots.generator`, `roots.pac_crate`, `roots.roadmap` | PathRef | conditionally required by stage | selected roots | Documentation/SOURCES are read by `generate-svd/SKILL.md:43-47`; PAC project/SVD roots by `generate-pac/SKILL.md:49-55`; generator/crate by `generation-and-checks.md:336-365`; roadmap by `scaffold-hal/SKILL.md:70-76`. |
| `roots.generation` | `{name,authorization:FileRef}[]` | yes | named external roots requiring explicit runtime bindings; may be empty | External policy citations in `layout.md`. |
| `stages` | `{id,status,handoff:FileRef}[]` | yes | completed/partial/blocked stage snapshots; absent stage never started | Stage gating (`AGENTS.md:147-151`). |

`FoundationRequirement` is exact `{id,kind,location}`: ID is a scope-item ID in namespace `foundation`; kind enum `api|metadata|runtime|link|fact`; location is a required public API/metadata path or cited contract locator string. IDs are sorted unique. These are not hardware claims; `hal-coordinator` derives them from the accepted scope decision and recorded consumer needs before PAC dispatch.

## Immutable scope decision

Stored at `halucinator/scope/<revision>.toml`:

```toml
schema = 1
revision = "scope-0123abcd"
previous = { kind = "initial" }
included = ["foundation:init-api", "peripheral:schema-demo"]
excluded = ["peripheral:adc"]
reason = "Initial fictional fixture scope"
```

`previous` is `{kind="initial"}` or `{kind="revision",revision="...",decision=<FileRef>}`. Included is nonempty; included/excluded are sorted unique and disjoint. `hal-coordinator` owns this decision (`AGENTS.md:147-151`; `.opencode/ownership.toml:207-219,282-284`; `scaffold-hal/SKILL.md:60-76`). A scope change mints a new revision/file and updates state under the global state lock. Previous scope files may never be deleted. Publish by exclusive-create, validate, fsync the file, fsync its parent, then update state through CAS. Existing handoffs stay pinned to old bytes and become non-current; dependents must be regenerated. The validator discovers and validates the complete lineage as specified in `validate.md`.