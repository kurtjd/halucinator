# `05-platform.toml`

Stage `scaffold-hal`.

Required: `platform.crate_manifest` ArtifactRef; `platform.roadmap` FileRef; `platform.startup_clock_contract` FileRef; ordered `platform.supporting_subsystems` scope-item IDs; `platform.foundation_api` public signatures; `platform.pac_manifest` ArtifactRef; `platform.source_ids`; `platform.cited_notes` FileRef[]; `platform.dependencies` Dependency[]; `platform.first_driver`; nonempty `platform.first_driver_modes`. Produced by `scaffold-record.md:15-105`, consumed by driver intake (`write-gpio/SKILL.md:49-89`; `write-time-driver/SKILL.md:51-88`).

Canonical checks:

| ID | Applicability | Source |
|---|---|---|
| `live-reference-read` | mandatory | `scaffold-hal/SKILL.md:84-89,114-127`. |
| `foundation-coverage` | mandatory | `scaffold-hal/SKILL.md:93-106`. |
| `format-lint` | mandatory | `scaffold-hal/SKILL.md:203-205`. |
| `advertised-builds` | mandatory | `scaffold-hal/SKILL.md:206`. |
| `negative-chip-selection` | mandatory because the initial Cargo chip feature is required; not-applicable requires reason only if live policy documents no negative combination | `scaffold-hal/SKILL.md:207-209`. |
| `pure-host-tests` | passed or not-applicable with required reason; reviewer audits the reason | `scaffold-hal/SKILL.md:210-211`. |
| `generated-mappings` | mandatory | `scaffold-hal/SKILL.md:212-213`. |
| `target-link` | mandatory | `scaffold-hal/SKILL.md:214-215`. |
| `build-only-ci` | mandatory | `scaffold-hal/SKILL.md:216`. |
| `independent-review` | mandatory | `scaffold-hal/SKILL.md:217-223`. |

Ready requires applicable checks passed and dependency identities/features current.