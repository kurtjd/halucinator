# `04-pac.toml`

Stage `generate-pac`; first note is deterministic `<documentation>/notes/PAC.md` FileRef.

Required: `pac.crate_manifest` ArtifactRef; `pac.package`; tagged `pac.revision` (`revision` value or `workspace`); `pac.cargo_chip_feature`; `pac.runtime_features` and `metadata_features` sorted string[]; `pac.rust_compilation_target`; `pac.source_ids` sorted string[]; `pac.cited_notes` FileRef[]; `pac.temporary_fork` boolean; and `[[pac.foundation]]`. Produced by `generation-and-checks.md:322-365`, consumed by `scaffold-hal/SKILL.md:90-112`. `pac.api_locations` is deleted because exact foundation requirements own required API/metadata locations.

Each foundation entry is exact `{id,kind,location,status,evidence}`. ID/kind/location equals one coordinator-owned foundation requirement. Status is `covered|missing`; evidence FileRef is required only for covered. Entries exactly partition all requirements. Ready permits only covered.

Canonical checks:

| ID | Applicability | Source |
|---|---|---|
| `input-identity` | mandatory | `generation-and-checks.md:96-124`. |
| `expected-inventory` | mandatory | `generation-and-checks.md:152-182`. |
| `representation-limits` | mandatory | `generation-and-checks.md:184-197,204-215`. |
| `target-build-api` | mandatory | `generation-and-checks.md:209,231-242`. |
| `host-metadata-api` | mandatory when metadata_features nonempty; otherwise not-applicable | `generation-and-checks.md:210,243-255`. |
| `negative-chip-selection` | mandatory when Cargo chip feature is present, as it always is in a ready PAC; otherwise not-applicable | `generation-and-checks.md:211,257-261`. |
| `pure-host-tests` | producer records passed or not-applicable with required reason; reviewer audits the reason | `generation-and-checks.md:212,263-269`. |
| `format-lint` | mandatory | `generation-and-checks.md:213,263-269`. |
| `generation-replay` | mandatory | `generation-and-checks.md:214,276-299`. |
| `final-path-build` | mandatory | `generation-and-checks.md:215,301-320`. |
| `independent-review` | mandatory; accepting 08 review over crate manifest | `generate-pac/SKILL.md:93-105`. |

Ready requires core/coordinator decisions, all requirements covered, fork false, and applicable checks passed.