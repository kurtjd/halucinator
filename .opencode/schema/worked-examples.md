# Complete hand-written example set

These are ten complete TOML documents: state, one supporting scope decision, and eight artifact-kind handoffs for the transparently fictional **Unobtainium Circuits UC-NOT-A-REAL-MCU-0001**. They are TOML syntax templates, not hardware evidence. Every shown placeholder is exactly 64 lowercase `a` characters; it is a deliberate hash placeholder valid in shape but not content. Fixture authors replace every placeholder with the raw-byte SHA-256 of the named file. `scope-0123abcd` is the example's immutable scope revision.

## Scope decision

```toml
schema = 1
revision = "scope-0123abcd"
previous = { kind = "initial" }
included = ["foundation:init-api", "foundation:interrupt-metadata", "peripheral:schema-demo"]
excluded = ["peripheral:adc"]
reason = "Initial fictional schema fixture"
```

## 1. `halucinator/state.toml`

```toml
schema = 1
generation = 9

[target]
vendor = "Unobtainium Circuits"
mcu_part_number = "UC-NOT-A-REAL-MCU-0001"
target_id = "unobtainium-circuits-uc-not-a-real-mcu-0001"
vendor_id = "unobtainium-circuits"
package = { kind = "unknown" }
core = "fictional-core"

[scope]
current_revision = "scope-0123abcd"
current_decision = { path = "halucinator/scope/scope-0123abcd.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }

[decisions]
cargo_chip_feature = "uc-not-a-real-mcu-0001"
rust_compilation_target = "thumbv7em-none-eabi"
destination_crate = { path = "embassy-unobtainium" }
first_peripheral = "schema-demo"
first_peripheral_modes = ["blocking"]
foundation_requirements = [
  { id = "foundation:init-api", kind = "api", location = "embassy_unobtainium::init" },
  { id = "foundation:interrupt-metadata", kind = "metadata", location = "metadata.interrupts" },
]

[roots]
documentation = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001" }
sources = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md" }
pac_project = { root = "generation:fictional-pac", path = "." }
svd_inputs = { root = "generation:fictional-pac", path = "data/svd/unobtainium-circuits-uc-not-a-real-mcu-0001" }
generator = { root = "generation:fictional-pac", path = "generator" }
pac_crate = { root = "generation:fictional-pac", path = "unobtainium-pac" }
roadmap = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ROADMAP.md" }
generation = [
  { name = "fictional-pac", authorization = { path = "halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/EXTERNAL-ROOT.md", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" } },
]

[[stages]]
id = "gather-documentation"
status = "ready"
handoff = { path = "halucinator/handoff/01-sources.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "extract-facts"
status = "ready"
handoff = { path = "halucinator/handoff/02-facts.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "generate-svd"
status = "ready"
handoff = { path = "halucinator/handoff/03-svd.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "generate-pac"
status = "ready"
handoff = { path = "halucinator/handoff/04-pac.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "scaffold-hal"
status = "partial"
handoff = { path = "halucinator/handoff/05-platform.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "write-driver:schema-demo"
status = "partial"
handoff = { path = "halucinator/handoff/06-driver-schema-demo.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "write-tests:schema-demo"
status = "partial"
handoff = { path = "halucinator/handoff/07-tests-schema-demo.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
[[stages]]
id = "review:pac"
status = "ready"
handoff = { path = "halucinator/handoff/08-review-pac.toml", sha256 = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
```

## Shared header convention in examples 2-9

Each repeats full tables; nothing is implied.

## 2. `01-sources.toml`

```toml
[handoff]
schema=1
stage="gather-documentation"
status="ready"
inputs=[]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
incomplete=[]
[[checks]]
id="requested-inputs-accounted"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-checks.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="available-content-resolves"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-checks.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="local-source-hashes"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/intake-checks.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="svd-search-complete"
status="not-applicable"
reason="An accessible fictional SVD was supplied."
[sources]
catalog={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/SOURCES.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
route="review-supplied"
source_ids=["doc-001"]
available=[{root="generation:fictional-pac",path="data/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/fixture.svd",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
cited_notes=[]
```

## 3. `02-facts.toml`

```toml
[handoff]
schema=1
stage="extract-facts"
status="ready"
inputs=[{path="halucinator/handoff/01-sources.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
incomplete=[]
[[checks]]
id="citations-complete"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/fact-checks.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="summary-field-cross-check"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/fact-checks.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="field-encodings-exhaustive"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/fact-checks.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="pdf-layout-extraction"
status="not-applicable"
reason="The fictional fixture source is text, not PDF."
[facts]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
citations=[{source_id="doc-001",document="FICTIONAL FIXTURE",revision="fixture-1",locator="schema-only",note={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}}]
categories=["field-encodings","register-layout"]
contradictions=[]
```

## 4. `03-svd.toml`

```toml
[handoff]
schema=1
stage="generate-svd"
status="ready"
inputs=[{path="halucinator/handoff/01-sources.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},{path="halucinator/handoff/02-facts.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
incomplete=[]
[[checks]]
id="input-identity"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="xml-well-formed"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="schema-validation"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="source-fact-comparison"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="correction-effects"
status="not-applicable"
reason="No transforms are present."
[[checks]]
id="structural-inventory"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="information-limits"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="preparation-replay"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SVD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[svd]
route="review-supplied"
source={root="generation:fictional-pac",path="data/svd/unobtainium-circuits-uc-not-a-real-mcu-0001/sources/fixture.svd",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
transforms=[]
includes=[]
extraction_mode="peripheral"
namespace_mode="none"
representation_limits=[]
unresolved_facts=[]
```

## 5. `04-pac.toml`

```toml
[handoff]
schema=1
stage="generate-pac"
status="ready"
inputs=[{path="halucinator/handoff/03-svd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
incomplete=[]
[[checks]]
id="input-identity"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="expected-inventory"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="representation-limits"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="target-build-api"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="host-metadata-api"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="negative-chip-selection"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="pure-host-tests"
status="not-applicable"
reason="The fictional generator declares no authored pure logic."
[[checks]]
id="format-lint"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="generation-replay"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="final-path-build"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="independent-review"
status="passed"
evidence={path="halucinator/handoff/08-review-pac.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[pac]
crate_manifest={root="generation:fictional-pac",path="unobtainium-pac/INVENTORY.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
package="unobtainium-pac"
revision={kind="workspace"}
cargo_chip_feature="uc-not-a-real-mcu-0001"
runtime_features=["pac","rt"]
metadata_features=["metadata"]
rust_compilation_target="thumbv7em-none-eabi"
source_ids=["doc-001"]
cited_notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
temporary_fork=false
[[pac.foundation]]
id="foundation:init-api"
kind="api"
location="embassy_unobtainium::init"
status="covered"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[pac.foundation]]
id="foundation:interrupt-metadata"
kind="metadata"
location="metadata.interrupts"
status="covered"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
```

## 6. `05-platform.toml`

This candidate is honestly partial: review has not run, while disposable work may continue. Its scope coverage is complete, but one mandatory check remains unrun.

```toml
[handoff]
schema=1
stage="scaffold-hal"
status="partial"
can_progress=true
inputs=[{path="halucinator/handoff/04-pac.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
incomplete=[]
[[checks]]
id="live-reference-read"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="foundation-coverage"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="format-lint"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="advertised-builds"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="negative-chip-selection"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="pure-host-tests"
status="not-applicable"
reason="No pure platform logic is declared."
[[checks]]
id="generated-mappings"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="target-link"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="build-only-ci"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="independent-review"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/SCAFFOLD.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[platform]
crate_manifest={path="embassy-unobtainium/Cargo.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
roadmap={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/ROADMAP.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
startup_clock_contract={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
supporting_subsystems=["foundation:init-api","foundation:interrupt-metadata"]
foundation_api=["pub fn init(config: Config) -> Peripherals"]
pac_manifest={root="generation:fictional-pac",path="unobtainium-pac/INVENTORY.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
source_ids=["doc-001"]
cited_notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
dependencies=[{crate="unobtainium-pac",identity="fixture-rev-1",features=["pac","rt"]}]
first_driver="schema-demo"
first_driver_modes=["blocking"]
```

## 7. `06-driver-schema-demo.toml`

Because its platform input is partial, `owned_files` is under an explicitly disposable candidate root, not the production crate.

```toml
[handoff]
schema=1
stage="write-driver"
status="partial"
can_progress=true
inputs=[{path="halucinator/handoff/05-platform.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=[]
incomplete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
[[checks]]
id="live-reference-read"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="format-lint-build"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="pure-host-tests"
status="not-applicable"
reason="No pure driver logic is declared."
[[checks]]
id="trait-conformance"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="generated-mappings"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="target-link-ci"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="independent-review"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/DRIVER.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[driver]
name="schema-demo"
scope_kind="full"
owned_files=[{path="halucinator/candidates/schema-demo/src/schema_demo.rs",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
capabilities=["blocking"]
public_api=["pub struct SchemaDemo<'d>","pub fn SchemaDemo::new(peripheral: Peripheral) -> SchemaDemo<'_>","impl embedded_hal::digital::ErrorType for SchemaDemo<'_>"]
dependencies=[{crate="embedded-hal",identity="1.0.0",features=[]}]
trait_obligations=[{dependency_crate="embedded-hal",trait="embedded_hal::digital::ErrorType",obligations=["Expose the public associated error type."]}]
test_hardware_facts=[]
build_contract={cargo_chip_feature="uc-not-a-real-mcu-0001",rust_compilation_target="thumbv7em-none-eabi",init_calls=["embassy_unobtainium::init(Config::default())"],memory_runtime={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/STARTUP.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"},observation="debugger-visible completion marker"}
requirement_ids=["SCHEMA-01"]
```

## 8. `07-tests-schema-demo.toml`

```toml
[handoff]
schema=1
stage="write-tests"
status="partial"
can_progress=true
inputs=[{path="halucinator/handoff/06-driver-schema-demo.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=[]
incomplete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
[[checks]]
id="workflow-references-read"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="live-conventions-read"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="format-lint"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="target-build-link"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="build-only-ci"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="hardware-admission"
status="not-applicable"
reason="Execution scope is build-only."
[[checks]]
id="hardware-execution"
status="not-applicable"
reason="Execution scope is build-only."
[[checks]]
id="independent-review"
status="unrun"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[tests]
name="schema-demo"
output_kind="validation"
execution_scope="build-only"
api_handoff={path="halucinator/handoff/06-driver-schema-demo.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
owned_files=[{path="examples/unobtainium/src/bin/schema_demo.rs",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
dependencies=[{crate="embedded-hal",identity="1.0.0",features=[]}]
review_input_manifest={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/INVENTORY.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[tests.coverage]]
id="SCHEMA-01"
status="blocked"
test_case="schema-demo-build"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/tests/schema-demo/TESTS.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[tests.hardware_runs]]
test_case="schema-demo-build"
status="not-run"
teardown="not-applicable"
```

## 9. `08-review-pac.toml`

```toml
[handoff]
schema=1
stage="review"
status="ready"
inputs=[{root="generation:fictional-pac",path="unobtainium-pac/INVENTORY.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
notes=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/REVIEW-PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
blockers=[]
[scope]
revision="scope-0123abcd"
decision={path="halucinator/scope/scope-0123abcd.toml",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[coverage]
complete=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
incomplete=[]
[[checks]]
id="applicable-references-read"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/REVIEW-PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="artifact-identity"
status="passed"
evidence={path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/REVIEW-PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
[[checks]]
id="hardware-claims-cited"
status="not-applicable"
reason="The reviewed scope contains no hardware fact ID."
[[checks]]
id="upstream-contracts-reviewed"
status="not-applicable"
reason="The PAC artifact declares no upstream trait obligation."
[review]
artifact_id="pac"
artifact={root="generation:fictional-pac",path="unobtainium-pac/INVENTORY.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}
scope=["foundation:init-api","foundation:interrupt-metadata","peripheral:schema-demo"]
unreviewed=[]
dependencies=[{path="halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/PAC.md",sha256="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"}]
findings=[]
verdict="ready"
lineage={kind="initial"}
```

## Cross-reference rules

All handoff `scope.decision` values equal state current decision. Every handoff input names an existing prior handoff/artifact. Review input and artifact name the PAC it reviews; PAC independent-review evidence names that review. This intentional two-file finalization is materialized review-first from a non-ready PAC candidate, then PAC current record is replaced with the ready bytes; the review pins the PAC inventory artifact, not the mutable PAC handoff bytes. State is written last with hashes of current handoffs.

## Hand-authorability result

The set is writable, but the PAC check list is long. It was simplified by using one closed flat check list, one flat foundation partition, one shared evidence type, and architect decisions in state instead of nested per-stage decision objects. The worked set deliberately leaves downstream candidate stages partial rather than fabricating three additional reviews. That is a valid durable state and exercises the global partial-consumption contract.