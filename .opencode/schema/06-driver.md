# `06-driver-<name>.toml`

Stage `write-driver`; filename name equals `driver.name`.

Required: `driver.name`; `scope_kind=full|scaffold-support`; `owned_files` ArtifactRef[]; `capabilities`; complete tester-safe `public_api`; structured `dependencies`; `trait_obligations` exact `{dependency_crate,trait,obligations:string[]}[]`; `facts_handoff` FileRef; `test_hardware_facts` sorted unique assertion-ID string[]; `build_contract` exact `{cargo_chip_feature,rust_compilation_target,init_calls:string[],memory_runtime:FileRef,observation}`; `requirement_ids`; optional `public_test_record` FileRef. Sources: `gpio-record.md:13-61`, `time-record.md:8-54`; consumers `gpio-validation.md:9-20`, `time-validation.md:8-23`.

A driver cannot originate a hardware citation. `driver.facts_handoff` names one exact `02-facts` handoff, and `driver.test_hardware_facts` lists only assertion IDs present in it. The validator resolves that handoff, requires kind `02-facts`, the current scope revision, `ready` status, a `passed` `citations-verified` check, a current hash, and the presence of every named assertion. Testers and debuggers receive the resolved claim, source metadata, location, excerpt and note through that binding rather than an agent-authored duplicate, so the same verification gate protects them transitively. This proves the assertions were verified as occurrences; it does not prove semantic entailment of the behavior the test assumes, which stays with review.

Tester admissibility: public signatures, observable contracts, versioned traits, build requirements, and cited facts only. Bodies, private names/state, PAC sequences, interrupt logic, algorithms, implementation paths, disassembly, and LSP bodies are forbidden.

The validator performs one intentionally small obvious-leak check over every `driver.public_api` string. Matching is case-sensitive substring search for the closed tokens `pac::` and `unsafe {`. Any match emits `DRIVER_API_LEAK`. This is only a tripwire; it cannot prove the surface leak-free, so independent review remains mandatory.

Canonical checks:

| ID | Applicability | Source |
|---|---|---|
| `live-reference-read` | mandatory | GPIO `write-gpio/SKILL.md:60-66`; time `write-time-driver/SKILL.md:62-70`. |
| `format-lint-build` | mandatory | GPIO `write-gpio/SKILL.md:112-116`; time `:104-109`. |
| `pure-host-tests` | passed or not-applicable with required reason; reviewer audits reason | same gates. |
| `trait-conformance` | mandatory when trait_obligations nonempty; otherwise not-applicable | GPIO `write-gpio/SKILL.md:114-116`; `AGENTS.md:353-357`. |
| `generated-mappings` | passed or not-applicable with required reason because generic driver IDs have no safe cross-peripheral derivation; reviewer audits the reason | GPIO `write-gpio/SKILL.md:117-118`; time `:110-112`. |
| `target-link-ci` | mandatory | GPIO `write-gpio/SKILL.md:119-120`; time `:113-115`. |
| `independent-review` | mandatory | GPIO `write-gpio/SKILL.md:121-123`; time `:116-118`. |

Ready requires all applicable checks passed. Full hardware scope also requires a current public test record.