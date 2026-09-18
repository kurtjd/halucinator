# TODO

Backlog for the halucinator toolkit, derived from the five-agent review
(coordinator, architect, reviewer, reliability, docs) of commit `2d073c1`.

This file is the durable record of every known gap. It is also the risk
register: a deferred item must stay visible here rather than silently
riding to the end.

## Legend

| Mark | Meaning |
|---|---|
| `[ ]` | Open, scheduled into a milestone |
| `[~]` | Open, deliberately deferred — rationale recorded inline |
| `[x]` | Done |

Every item carries the evidence that produced it. `file:line` citations
are against `2d073c1` and may drift as the work lands; the claim, not the
line number, is the thing to preserve.

---

## A. Handoff typing — the structural defect

The toolkit argues for parse-don't-validate (`AGENTS.md:58-105`) and then
passes untyped Markdown prose between every stage. Three references
explicitly decline a schema (`source-list-format.md:3-5`,
`preparation-and-checks.md:234-241`, `generation-and-checks.md:322-330`).
Consumers therefore re-derive what producers already knew, which costs
tokens and loses fields.

- [x] **A1** Define one typed per-stage handoff format. Every stage emits
  it; every consumer reads it instead of re-deriving. *(Closed in
  `.opencode/schema/handoff-common.md` and the eight per-kind schemas.)*
- [x] **A2** `SOURCES.md` has no field for declared scope, yet three
  stages block on it (`generate-svd/SKILL.md:45-47`,
  `generation-and-checks.md:98`, `scaffold-hal/SKILL.md:62-70`). *(Closed
  by the `state.toml` scope and immutable scope decisions in
  `.opencode/schema/state.md`.)*
- [x] **A3** No `core` field anywhere. Demanded four times downstream
  (`generate-svd/SKILL.md:48`, `generation-and-checks.md:107,161,332`),
  silently lost at the PAC→scaffold boundary. `Silicon revision` is not
  core revision. *(Closed by `state.target.core`, distinct from silicon
  revision, with PAC→scaffold continuity validated.)*
- [x] **A4** Enum drift between producer and consumer, verified by grep:
  `gather-documentation/SKILL.md:164,167` writes
  `Review/normalize existing input` / `Author from cited documentation`;
  `generate-svd/SKILL.md:60,62` reads `Review/normalize supplied SVD` /
  `Author from cited findings`. Two of three tokens differ verbatim, and
  the entry *conditions* differ semantically, so the route is not
  derivable from the written field. *(Closed in `.opencode/schema/03-svd.md`
  by the single producer-evaluable `svd.route` enum: intake decides
  accessibility; `generate-svd` decides applicability.)*
- [x] **A5** Six unreconciled status vocabularies. Only `blocked` is
  common across stages. `test-record.md:80` requires one scheme while
  `:93` defines another for the same rows, with no stated mapping. *(Closed
  by one `ready|partial|blocked` vocabulary with mutually exclusive
  predicates; `in-progress` is valid only inside `.run/*.lock`.)*
- [x] **A6** Stage done-ness is unreadable from disk. `Intake status:`
  defaults to `in progress` — a fourth value outside the returned enum
  (`source-list-format.md:151`) — and no skill in the repo ever reads it.
  Write-only. An interrupted intake is indistinguishable from one never
  started. *(Closed within one worktree: `state.toml` stage status plus
  `.run/*.lock` interruption detection; cross-clone detection remains
  open — see F8 and F10.)*
- [x] **A7** The two most load-bearing handoff artifacts have no
  filenames. The SVD preparation note (`preparation-and-checks.md:241-260`)
  and the PAC generation record (`generation-and-checks.md:325`) are prose
  with soft defaults, discoverable only via a free-text bullet the
  consumer never quotes. The same file pins external GitHub deps to
  40-hex SHAs (`generation-and-checks.md:33-49`). *(Closed by deterministic
  handoff filenames plus pinned `notes/SVD.md` and `notes/PAC.md`; M3 also
  names the exact `<documentation>/notes/SVD.md` and
  `<documentation>/notes/PAC.md` paths in both skills and references and
  deletes the soft alternatives.)*
- [x] **A8** Write-only fields that nothing reads:
  `Next SVD action and source IDs` (`source-list-format.md:159`),
  `Hardware-analysis prerequisites`,
  `Hardware-setup questions for hal-architect`. *(Closed by a writer/reader
  audit; unread fields deleted: `platform.requires_hardware_runtime`,
  `pac.api_locations`, `Dependency.contract`, and seven applicability
  booleans.)*
- [x] **A9** Consumer admission vocabulary does not match producer
  headings. `generation-and-checks.md:105-112` substitutes a 6-row table
  for the note's 5 headings; `Representation limits` and `Consumers` have
  no upstream heading, and `Handoff` has no admission row. *(Closed: PAC
  admission now maps one-to-one onto `svd.route`, `svd.source`, the recipe
  quad, `svd.prepared_manifest`, `svd.representation_limits`,
  `svd.unresolved_facts`, `checks.*`, `handoff.inputs` and `scope.*`; the
  `Consumers` and `Representation limits` pseudo-fields are deleted.)*
- [x] **A10** Nine null sentinels coexist with no mapping (`unknown`,
  `not provided`, `none`, `not checked`, `none recorded`, `not selected`,
  `none yet`, `unverified`, `in progress`). `source-list-format.md` never
  marks a field required or optional. *(Closed by one null rule: optional
  key absence, empty collections for known-empty, no sentinel strings;
  every field is marked required or optional.)*
- [x] **A11** `hal-tester`'s input contract is a field list with no
  format (`hal-tester.md:57-58`). For any peripheral without a skill
  there is no field list at all, so the blinding is enforced against an
  undefined input. *(Closed by the tester-safe public contract in
  `.opencode/schema/06-driver.md`, with a `DRIVER_API_LEAK` tripwire on
  forbidden tokens `pac::` and `unsafe {`.)*
- [x] **A12** `hal-reviewer`'s accepting token is never enumerated
  downstream. Five call sites quote only the rejected value
  (`write-examples/SKILL.md:161`, `write-gpio/SKILL.md:122`,
  `write-time-driver/SKILL.md:118`, `scaffold-hal/SKILL.md:221`,
  `scaffold-record.md:86`). The value that *is* acceptance is unwritten.
  *(Closed by the `ready|ready-with-fixes|not-ready` verdict enum; only
  `ready` accepts. M2 made `hal-coordinator` and `hal-reviewer` state the
  accepting token in prose. M3 makes all call sites in the five retrofitted
  skills state the accepting sentence, and a case-insensitive scan finds no
  `not ready` or `ready with fixes` survivor in them. `write-gpio` and
  `write-time-driver` still carry the legacy spelling and are M4's.)*
- [x] **A13** Path-base ambiguity. The catalog-to-root translation clause
  lives only in the producer's reference (`source-list-format.md:78-79`);
  `generate-svd` never mentions it. Two normalization rules coexist:
  `<target-id>` is vendor+part, `<vendor>` is vendor only. *(Closed by one
  repository-root path base with named authorized roots, and distinct
  target and vendor normalization rules.)*
- [ ] **A14** The typed schema is defined, validated and fixture-tested.
  *Progress: the typed chain `01-sources → 03-svd → 04-pac → 05-platform`
  now flows on the `review-supplied` route. Each producer writes a
  deterministic handoff — `halucinator/handoff/01-sources.toml`,
  `03-svd.toml`, `04-pac.toml`, `05-platform.toml` — and each consumer's
  declared admission matches the producer's declared emission field for
  field, verified against the AST-derived registry from
  `.opencode/schema/validate.py`. The `unresolved` source route correctly
  admits nothing. The chain still stalls in two places. At `01 → 02`, on
  the `author-from-docs` route, `generate-svd` cannot reach `ready` without
  a ready `02-facts`. At `05 → 06`, no retrofitted procedure produces a
  typed `06-driver`, so `write-examples` must not be invoked as a
  typed-ready continuation from `05`. It is not that no typed producer
  exists: M2 already made `hal-datasheet` a typed `02-facts` emitter and
  `hal-driver` a typed `06-driver` emitter in their agent contracts. What
  is missing at both boundaries is a template-conforming skill procedure —
  one carrying the validator wiring, deterministic publication sequence,
  canonical check discharge and typed exit predicates. M5 owns the facts
  procedure; M4 owns the driver procedure. Given a valid ready `06-driver`,
  `write-examples`'s `06 → 07` admission is already field-correct. Owner:
  M4 and M5 for the two missing procedures.*
- [x] **A15** `halucinator/test-candidates/` is an M2-local convention. The
  tester's committed test revisions live there because `.run/` is gitignored
  and therefore neither reviewable nor durable across clones, but M2 may not
  edit `.opencode/schema/*`, so `layout.md` does not know the root exists.
  Ratify it in layout policy, and settle the `.gitattributes`/`.gitignore`
  consequences of committing test source, manifests and raw logs. *(Closed
  in `.opencode/schema/layout.md`: the committed root, `src/**`, manifests,
  `INVENTORY.md` and `evidence/**` are ratified with three ownership classes;
  the root is never `.run` and never ignored, and the destination
  `.gitignore` and four `.gitattributes` lines are specified. This does not
  close H9 or E10.)*
- [x] **A16** Schema prose still attributes decisions to the architect.
  `.opencode/schema/state.md` and `.opencode/schema/04-pac.md` call scope,
  the Cargo chip feature, the first peripheral and the foundation
  requirements architect-owned; under the eight-agent topology they are
  `hal-coordinator`'s. Only the attribution is wrong — no field shape
  changes. *(Closed in `.opencode/schema/state.md`, `04-pac.md`,
  `traceability.md` and `03-svd.md`: attribution now belongs to
  `hal-coordinator`, and stale tester-record ownership in `traceability.md`
  is corrected. Residual architect terminology in
  `.opencode/schema/validate.py:1049-1066` is A20; M3 was forbidden from
  editing the validator.)*
- [x] **A17** `.opencode/schema/selfcheck.md` is stale. It documents five
  agents and the old tester-only permission keys, and describes none of the
  thirteen topology checks M2 added to `tools/selfcheck.py`. *(Closed by the
  rewritten self-check reference: eight agents with one primary, generic
  heterogeneous permission parsing, all 32 invoked checks, the AST-derived
  registry, raw-fence parsing, bounds and timeouts, the uniform allowlist,
  and the honour-system limitation.)*
- [ ] **A18** An arbitrary `state.decisions.destination_crate` defeats the
  static permission globs. The tester's blinding denies `embassy-*/**` and
  the driver and integrator are bounded by `embassy-*/` patterns; a HAL crate
  placed anywhere else is outside all of them, and agent frontmatter cannot
  interpolate a runtime path. Investigate destination-aware policy without
  claiming dynamic frontmatter generation. *Owner: M3 to investigate.*
- [ ] **A19** **ESCALATED — validator soundness defect.**
  `.opencode/schema/validate.py:1525-1527` stores only the first discovered
  handoff per stage in `world.by_stage`, so multiple `06-driver-<name>`
  handoffs collapse into one entry. Ready dependency admission at
  `.opencode/schema/validate.py:1068-1091` then looks up only that first
  entry, and no rule proves `tests.api_handoff` names the
  `06-driver-<name>.toml` matching `tests.name`. With multiple drivers, a
  `07-tests-<name>` handoff can therefore become `ready` against the wrong
  driver's API handoff. This was found by exercising the M1 schema against
  a real M3 consumer, exactly what this milestone's sequencing was designed
  to surface. Reviewer assessment: repair needs no field name, diagnostic
  code, wire-format or schema-version change. Validator matching logic
  should resolve `tests.api_handoff` to the exact named and hash-matching
  `06`, with multi-driver fixtures proving correct and incorrect pairings.
  M3 was forbidden from editing the validator, so it remains untouched and
  is disclosed in `write-examples/SKILL.md`. *Recommended owner: M4, which
  authors the generic typed `06` producer and must make that boundary
  operational.*
- [ ] **A20** Architect terminology remains in
  `.opencode/schema/validate.py:1049-1066` after A16 corrected the prose.
  This is attribution only, with no field change. M3 could not edit the
  validator. *Owner: M4, with A19, since both are validator edits.*

---

## B. Agent topology

- [x] **B1** No `hal-coordinator`. `hal-architect` currently owns both
  decisions and platform implementation
  (`scaffold-hal/SKILL.md:129-146`), which is two jobs. *(Closed by
  `.opencode/agents/hal-coordinator.md`: the only `mode: primary` agent, sole
  gate authority, owning `workflow-state`, `scope-decisions` and `roadmap`
  and no implementation.)*
- [x] **B2** `hal-architect` must stop writing code. Today it owns
  `Cargo.toml`, build integration, `peripherals!`, `interrupt_mod!`,
  `init`, and the clocks boundary. *(Closed: the architect's only writable
  class is `architecture-spec`, one file — `notes/ARCHITECTURE.md`. Shared
  files moved to `hal-integrator`, clocks to `hal-driver`.)*
- [x] **B3** `hal-datasheet` seam is described wrong. `README.md:159-162`
  frames it as "meaning vs structure", but datasheet already extracts
  offsets, widths, access and reset values (`hal-datasheet.md:50-67`).
  The real seam is *cited hardware assertions* vs *machine-readable
  representation*. *(Closed: README now frames it as epistemology versus
  representation and names it a trust boundary — `hal-svd` must never turn
  an absent fact into a plausible value.)*
- [ ] **B4** `hal-datasheet`'s hardware-analysis half has no skill.
  `hal-datasheet.md:78-79` separates it explicitly; only the collection
  half is covered. Its output format (`hal-datasheet.md:140-153`) and the
  skill's (`gather-documentation/SKILL.md:186-195`) are two different
  seven-item lists nobody reconciles. *M2 created no skill, so this is
  untouched; the agent marks the gap as unlinked prose. Owner: M5, with
  D7.*
- [x] **B5** `hal-reviewer` does not exist as a stage. `AGENTS.md:127`
  claims it gates everything; the reviewer never claims it, has no skill,
  has `edit:deny` + `task:deny` (no gate authority), describes its output
  as *"for recording"* (`hal-reviewer.md:131`), and is absent from four of
  the files covering the stages it supposedly gates. *(Closed: gate authority
  sits explicitly with `hal-coordinator`, and the reviewer is a real typed
  stage — it emits an `08` verdict, authors the `REVIEW-*.md` findings content,
  holds a narrow write permission for exactly that handoff, and has an explicit
  dispatch payload. Its own skill is the only residual, and that is tracked as
  D12, so nothing distinct remains under this entry.)*
- [x] **B6** `hal-tester` is `edit: allow`, unrestricted
  (`hal-tester.md:30`) — read-blinded from HAL source, write-enabled
  everywhere. *(Closed: the tester's edit map is `*: deny` reopened only for
  `halucinator/test-candidates/**` and its own `07` handoff, and `cargo
  fmt*` is denied outright.)*
- [x] **B7** Tester blindness is claimed "by construction"
  (`hal-tester.md:53-56`) while `README.md:180-185` admits it is not a
  sandbox. Both cannot be true. Deny globs cover only
  `embassy-*/src/**` — not `bash`, `git show`, LSP output, build
  diagnostics, generated docs, or alternate crate locations. *(Closed: the
  "by construction" claim is gone. README and the agent both state that
  perfect blindness is impossible and enumerate the escape hatches —
  `bash: ask`, `grep` matched against the query rather than the path,
  compiler/macro/build-script output, LSP, generated docs, glob/list
  filenames, and the uncovered destination crate. The residual permission
  gap is tracked as A18.)*
- [ ] **B8** Loading `write-gpio` or `write-time-driver` loads the full
  implementation procedure into the tester's context before the "stop
  reading here" row can take effect (`write-gpio/SKILL.md:17-32`). Heading
  order cannot fix this because loading a skill exposes the whole body
  before any stop-reading row takes effect. *Owner: M4, which must make
  implementation and validation role-safe so the tester loads validation
  only.*
- [x] **B9** No `hal-integrator`. Nothing owns wiring tester-authored
  test modules into the crate, nor the serialized commit point. *(Closed by
  `.opencode/agents/hal-integrator.md`: sole writer of 21 shared file
  classes and, via `[operations].commit_owner`, the sole committer. Every
  other agent's `bash` map ends with `git commit*: deny`.)*
- [x] **B10** `hal-driver.md` states no ownership sentence at all.
  *(Closed: every agent now carries one ownership sentence, repeated
  verbatim in its machine-readable contract fence and checked against the
  prose.)*
- [x] **B11** Routing contradictions: `hal-datasheet.md:129-132` hands
  findings peer-to-peer to `hal-svd`/`hal-driver` and never mentions the
  hub; `hal-svd.md` never mentions `hal-architect`; `hal-driver.md` never
  mentions `hal-reviewer`; `hal-driver.md:106-109` names no recipient.
  *(Closed: every specialist declares `dispatched-by: hal-coordinator`,
  `may-dispatch: none` and `task: deny`. There is one hub and no
  peer-to-peer route.)*
- [x] **B12** `clocks` is claimed three ways
  (`hal-architect.md:110-114`, `hal-driver.md:132-134`,
  `scaffold-hal/SKILL.md:30-32,139`) and is absent from scaffold's own
  delegation list (`scaffold-hal/SKILL.md:160`). No spec, trait shape or
  signature exists anywhere. `PreEnableParts` has zero hits in any skill.
  *(Closed across agents and skills: the registry and the re-cut
  `scaffold-hal/SKILL.md:129-146` give `embassy-*/src/clocks/**` to
  `hal-driver`, implemented against the architect's contract, and name the
  old architect assignment as a common mistake.)*
- [x] **B13** Interrupt table claimed by both `hal-svd.md:67` and
  `hal-architect.md:136`. *(Closed: interrupt metadata is `hal-svd`'s;
  `hal-architect` no longer mentions it, and the generated mapping file
  `embassy-*/src/_generated.rs` is `hal-integrator`'s `build-generation`
  class.)*
- [x] **B14** No dispatch policy protecting against generic-agent
  fallback. A request like "add UART support" can route to `coder`,
  `general`, or `integrator` and bypass every specialist constraint.
  *(Closed by the dispatch policy block carried verbatim in both
  `README.md` and `hal-coordinator.md`, plus `opencode.json` setting
  `default_agent` so a user lands on the hub rather than the built-in
  `build` agent.)*

---

## C. Unowned work

Verified as grep-absences across all agents and skills.

- [x] **C1** `memory.x` / linker scripts. Zero hits.
  `hardware-execution.md:33` and `write-examples/SKILL.md:144` route
  linker defects *away* to "their owner"; nobody is named. Yet
  `scaffold-hal/SKILL.md:214-215` gates `software verified` on an actual
  target link, and RAM-first execution
  (`hardware-execution.md:58-61`) needs a RAM-linked image. *(Closed by the
  `linker` file class in `.opencode/ownership.toml`, owned by
  `hal-integrator`, covering `embassy-*/memory.x`, `embassy-*/link*.x` and
  their integration-candidate counterparts. The RAM-first linker
  *procedure* is still missing — see H5.)*
- [x] **C2** `build.rs` and `_generated.rs`. Zero hits in scaffold.
  `AGENTS.md:52` names `_generated.rs` in the concern map; the skill that
  creates it never names it. *(Closed by the `build-generation` class,
  owned by `hal-integrator`, which overrides the broad
  `peripheral-modules` pattern so the driver cannot write it.)*
- [x] **C3** `ci.sh` the file. Zero hits in scaffold; it only *reads* CI
  (`:119`) and *requests* wiring from the tester (`:177-179`).
  `hal-tester.md:8` claims "the `ci.sh` wiring",
  `write-examples/SKILL.md:71` reads it. Nobody owns the file. *(Closed by
  the `ci` class, owned by `hal-integrator`. The tester no longer claims
  it; `write-examples/SKILL.md` still does — README conflict 3, D18.)*
- [x] **C4** Runtime integration: `cortex-m-rt`, `embassy-executor`,
  `critical-section`, `defmt`, panic handler. Zero hits in scaffold.
  *(Closed by the `runtime-wiring` class — `embassy-*/Cargo.toml`,
  `examples/*/Cargo.toml`, `tests/*/Cargo.toml` — owned by
  `hal-integrator`, which also owns `platform-lib` and the toolchain and
  format policy files.)*
- [ ] **C5** Toolchain / target / probe installation. `install` is
  forbidden (`generate-pac/SKILL.md:34`, `generate-svd/SKILL.md:84`) and
  a missing formatter or target makes `ready` / `software verified`
  structurally unreachable with no remedy path
  (`generation-and-checks.md:225-226`, `scaffold-hal/SKILL.md:222-223`).
- [x] **C6** The roadmap file is required
  (`hal-architect.md:158-160`, `scaffold-hal/SKILL.md:73-76`,
  `scaffold-record.md:25`) with no filename and no default path, while
  its sibling `SCAFFOLD.md` has both. *(Closed: the exact path
  `halucinator/docs/<target-id>/notes/ROADMAP.md` is named in
  `hal-coordinator.md`, in `README.md`, and in the `roadmap` registry
  class, and selfcheck rejects any agent that refers to a roadmap without
  naming it.)*
- [x] **C7** `hal-reviewer` dispatch payload. `scaffold-hal` §6 and §7
  give explicit bulleted payloads for driver and tester; §8 requires
  reviewer review (`:217`) with no dispatch step and no payload spec.
  *(Closed: `hal-reviewer.md` now states its mandatory payload — artifact
  ID and primary ArtifactRef, the complete frozen set, scope,
  `ARCHITECTURE.md`, the dependency closure, citations and contracts, live
  references, any prior review, exclusions, and an owner per finding — and
  returns `blocked` on a missing mandatory input.)*
- [~] **C8** Upstream PR preparation. Zero hits for `pull request` /
  `merge`. `scaffold-hal/SKILL.md:234-235` explicitly disclaims upstream
  acceptance while `hal-architect.md:27-29` states the goal is an
  upstreamable HAL. *Deferred: the pipeline must first run end-to-end.*
- [~] **C9** Multi-chip family expansion. `scaffold-hal/SKILL.md:264-265`
  forbids a layout that anticipates a family; `AGENTS.md:270+` makes the
  metapac's rationale family-serving; `hal-svd.md:43-45` calls shared IP
  "the point". The two references actively disagree. *Deferred.*
- [~] **C10** Regression across chips. `hal-driver.md:127-128` requires
  building every chip feature combination; no stage, owner, or CI wiring
  exists. *Deferred with C9.*

---

## D. Skills

- [ ] **D1** Per-driver skills do not scale. Two of ~14 peripherals have
  skills. The documented fallback — read `embassy-mcxa/src/i2c/` — is the
  exact behavior both checklists warn against
  (`gpio-checklist.md:22-23`, `time-checklist.md:97-98`).
- [ ] **D2** The tester is self-blocked for unskilled peripherals.
  `write-examples/SKILL.md:22-23` says missing required references block
  the work and forbids falling back to a remembered procedure. Read
  literally, a UART tester is blocked by its own skill — and
  `scaffold-hal/SKILL.md:78-80` uses UART as its worked example.
- [x] **D3** No common skill template. Only `scaffold-hal` has an example,
  quick reference, and common-mistakes section (`:237-277`). Checklists
  are checkboxes in one place (`scaffold-record.md:107-131`) and prose in
  another (`gpio-checklist.md:16-115`). *(Closed by the canonical
  `docs/skill-template.md`, mechanically enforced by `skill-structure`,
  `skill-contracts`, `skill-trigger-frontmatter`, `skill-status-vocabulary`
  and `skill-validator-wiring`.)*
- [x] **D4** `scaffold-hal` is three skills in one 297-line procedure:
  architectural decisions, platform implementation, and delegation
  orchestration. *(Closed by re-cutting `scaffold-hal` along M2's agent
  boundaries: the coordinator decides and dispatches; the architect writes
  only `ARCHITECTURE.md`; the driver owns clocks; the integrator owns every
  shared file and is sole committer; the tester supplies deltas only; and
  the reviewer supplies the verdict only.)*
- [x] **D5** `scaffold-hal` frontmatter is not dispatchable — it never
  surfaces its major terms (clocks, `init`, `interrupt_mod!`, `memory.x`,
  linker, generated mappings). *(Closed: the trigger-form frontmatter names
  clocks, `init`, `interrupt_mod!`, generated mappings, `memory.x` and
  linker/runtime wiring while assigning rather than claiming each.)*
- [x] **D6** `gather-documentation`, `generate-svd` and `generate-pac`
  frontmatter lead with capability summaries rather than "Use when"
  triggers, inviting description-only execution without loading the body.
  *(Closed: all three descriptions now lead with `Use when` and state what
  each skill is `Wrong for`.)*
- [ ] **D7** Missing skill: hardware-fact extraction (see B4).
- [ ] **D8** Missing skill: clock tree bring-up.
- [ ] **D9** Missing skill: interrupts / NVIC / `interrupt_mod!`.
- [ ] **D10** Missing skill: runtime + linker integration (`memory.x`).
- [ ] **D11** Missing skill: DMA subsystem.
- [ ] **D12** Missing skill: artifact review (the reviewer's own skill).
- [ ] **D13** Missing skill: generic driver scaffolding, replacing the
  per-peripheral skills.
- [ ] **D14** Missing skill: hardware debugging of a failing driver.
- [~] **D15** Missing skill: upstream PR preparation. *Deferred with C8.*
- [~] **D16** Missing skill: chip-family expansion. *Deferred with C9.*
- [ ] **D17** Operational rules that static validation cannot express need
  runtime tests: consuming a `partial` input to mutate canonical or
  production artifacts, raw-colon lock filenames (unmaterializable on
  NTFS), live-lock PID/clock classification, and `state.toml` CAS races.
  All four are recorded as limitations in `.opencode/schema/validate.md`.
  *Deferred out of M3: `validate_locks()` validates lock structure and
  resources but never inspects PID or heartbeat, and no state publisher
  implementing compare-and-swap exists. Operational tests written now would
  embed the algorithms under test and prove only the test code. The Windows
  raw-colon lock filename case is individually safe but not worth a separate
  mechanism before the operational tooling exists. Owner: M6, with F10/F11,
  which introduce that tooling.*
- [ ] **D18** Skill ownership text contradicts the agent contracts. M2 could
  not edit a `SKILL.md`, so nine verified conflicts remain, enumerated once
  in `README.md` and referenced by ID from each affected agent: skills still
  assign shared files and clocks to `hal-architect`, binaries and CI to
  `hal-tester`, `SOURCES.md` writes to `hal-datasheet` and `hal-svd`, durable
  records to `hal-driver`/`hal-architect`, `SCAFFOLD.md` and the roadmap to
  `hal-architect`, dispatch to `hal-architect` rather than
  `hal-coordinator`, and the legacy spaced rejection spelling rather than
  the typed verdict tokens. *Progress: the retrofit resolves the skill-layer
  conflicts in the five retrofitted skills. Two remain: conflict 6 assigns
  the GPIO and time durable records jointly to `hal-driver` and
  `hal-architect`, and conflict 9 routes their tester and reviewer handoffs
  through `hal-architect` and uses the legacy spaced verdict spellings.
  Both cite `write-gpio` and `write-time-driver`, which M3 deliberately did
  not touch and M4 replaces. Owner: M4.*
- [ ] **D19** Unratified evidence-path conventions. The retrofitted skills'
  validation tables cite evidence path categories such as
  `halucinator/candidates/integration-<id>/evidence/…` and
  `derived/pac/<target-id>/<run-id>/candidate/*.log`, plus an
  `08-review-pac-crate.toml` artifact slug extrapolated from
  `.opencode/schema/layout.md`'s `08-review-<artifact>.toml`. They are
  consistent with the run layouts the references already mandate and fall
  under owned roots, but remain conventions rather than ratified layout.
  *Owner: M6, with the layout work.*
- [ ] **D20** `README.md`'s conflict inventory is annotated, not audited.
  M3 annotated which of the eleven listed skill/agent conflicts the retrofit
  resolved in the skill layer, retaining every ID and identifying text so
  the agents' declared ID sets still match. That classification came from
  M3's scope rather than a per-conflict audit, and the entries' line-range
  citations are now stale. A per-conflict audit and citation refresh are
  restructuring work. *Owner: M7.*

---

## E. Correctness and safety

- [ ] **E1** No citation verification. Rule 1 forbids invented hardware
  facts (`AGENTS.md:291-299`) but a syntactically plausible section
  number satisfies the output shape and survives to silicon. This is the
  highest-severity gap in the project: the one failure mode that produces
  confident, compiling, wrong output.
- [ ] **E2** Silent corruption chain. A hallucinated offset becomes a
  wrong SVD, a wrong PAC, a driver that compiles and does nothing, and a
  bench session that blames the driver. No detection exists before the
  bench.
- [ ] **E3** MCXA implementation choices are mandated as universal
  architecture. `AGENTS.md:305-309`, `hal-architect.md:110-114` and
  `hal-driver.md:61-80` require the MCXA `Gate`, `enable_and_reset`,
  `PreEnableParts` and `WakeGuard` shapes for arbitrary vendors. The
  invariant is universal; the type names are an example.
- [ ] **E4** Rule 7's "clear them in one write" (`AGENTS.md:319-321`,
  `hal-driver.md:89-92`) is destructive where flags span registers or mix
  W1C/W0C/read-only/control bits. The operation must derive from cited
  per-register semantics.
- [ ] **E5** `hal-driver.md:102-105` tells the agent to read the MCXA
  implementation *before* target analysis, priming NXP register
  assumptions into a model about to interpret a different vendor's PDF.
- [ ] **E6** No transitive invalidation. Every record says dependent
  evidence must be invalidated, but it is manual and local
  (`scaffold-record.md:88-90`, `gpio-record.md:77-81`,
  `test-record.md:101-105`). Stale records stay labelled
  `software verified` / `passed`. *Progress: hash-pinned evidence now
  makes stale records detectable via `STALE_EVIDENCE` / `STALE_REVIEW`,
  and `.opencode/schema/handoff-common.md` defines a re-attestation
  protocol. The five retrofitted skills now carry the sequence from
  `.opencode/schema/handoff-common.md:59-61` as executable steps, including
  "never delete old evidence or old review records to regain validation".
  The `write-gpio` and `write-time-driver` records are not retrofitted, and
  nothing mechanically detects a false claim. Owner: M4 for the remaining
  records; the false-claim mechanism remains E7.*
- [ ] **E7** No mechanism makes a false verification claim detectable.
  Records are ordinary Markdown written by the same agent doing the work.
- [ ] **E8** `AGENTS.md`'s dual-purpose framing is unsafe. `:15-19`
  requires `embassy-mcxa/` paths to resolve or work stops; in this
  checkout none resolve, so literal compliance halts even toolkit
  maintenance.
- [ ] **E9** The install commands overwrite a destination `AGENTS.md`
  (`README.md:66-82`) despite the prose saying "or merge" (`:59-64`).
- [ ] **E10** `.opencode/schema/validate.py` does not invoke
  `git check-attr`; it requires the mandated `.gitattributes` lines
  literally at the destination root, because the fixture roots live
  inside this repository's worktree. Git precedence and nested overrides
  are therefore unevaluated, and portable hash policy is unverified
  against effective Git attributes. *Owner: M3.*
- [ ] **E11** The driver `independent-review` artifact-equality path has no
  fixture; `06-driver`'s check is `unrun` in the valid set, so the
  implemented set-comparison is unexercised surface. *Owner: M3.*
- [ ] **E12** Implemented but unexercised validator surface: resource
  limits, reparse-point refusal, Windows reserved-name rejection, and
  live-lock classification. No fixture reaches any of them. *Owner: M3.*

---

## F. Concurrency and hardware safety

Zero concurrency vocabulary exists across all agents and skills:
`parallel`, `simultaneous`, `serialize`, `contention`, `at once`,
`one at a time`, standalone `lock` — all zero hits.

- [ ] **F1** No shared-file amendment protocol. `scaffold-hal` assigns
  `Cargo.toml`, `peripherals!`, `interrupt_mod!` and build integration to
  one owner (`:131-139`) and never says how later per-peripheral work
  amends them. `extend`, `subsequent`, `each driver`, `per-peripheral`
  are all zero hits. *Progress: M2 supplies the discipline at the agent
  layer — `.opencode/ownership.toml` gives every shared file exactly one
  owner, `hal-integrator` is its sole writer, and every amendment runs under
  the `global:hal-integration` stage lock against a frozen candidate
  (`hal-integrator.md`, sections "Integration lock" and "Frozen candidate
  order"). The retrofitted skills now defer to that discipline and no longer
  describe in-place production edits. Residual: durable journalling, owner
  fencing and cross-clone crash markers are still required. Owner: M6.*
- [ ] **F2** `ci.sh` and `examples/<chip>/Cargo.toml` are shared write
  targets with no merge discipline. `[[bin]]` and `Cargo.toml` are zero
  hits across all nine tester-side files. *Progress: both are now registry
  classes with `hal-integrator` as sole writer (`ci`, `example-manifest`,
  `example-support`, `runtime-wiring`), and the tester no longer writes them
  at all — it hands over test logic and the integrator places it. The
  retrofitted skills defer to the `global:hal-integration` lock, frozen
  candidate order and committed candidate roots and no longer assign CI
  wiring to the tester. Residual: durable journalling, owner fencing and
  cross-clone crash markers are still required. Owner: M6.*
- [ ] **F3** No lease on the single physical board.
  `hardware-execution.md` is singular throughout; two concurrently
  dispatched testers would each hold genuine device authorization and
  interleave resets, loads and runs on the same MCU. The failure mode is
  physical, not a merge conflict. *Progress: `.opencode/schema/layout.md`
  reserves a `board:<board_id>` lease keyed by physical device rather than
  by stage, but M1 implements no reader, so no exclusion is enforced yet.
  Owner: M6.*
- [ ] **F4** No interrupted-HIL recovery. If the host or agent dies
  mid-run, no record can confirm teardown, and no next-session procedure
  declares device state unknown
  (`hardware-execution.md:104-115`).
- [ ] **F5** No universal between-test safe state — outputs
  high-impedance, DMA/interrupts quiesced, loads de-energized, reset
  asserted before fixture changes.
- [~] **F6** No flash wear budget. RAM-first reduces operations and
  ranges require authorization (`hardware-execution.md:74-83`), but no
  erase/program counter or retry budget exists. *Deferred: mitigated by
  RAM-first.*
- [~] **F7** No probe-wedge recovery: half-open debug session, locked
  probe, held reset, stale server process. *Deferred.*
- [ ] **F8** Canonical PAC integration is a sequence, not a transaction
  (`generation-and-checks.md:301-320`). Power loss mid-integration leaves
  mixed old/new output with no `integration-in-progress` marker.
  *Progress: `.run/<stage>.lock` now marks canonical PAC integration, but
  it is gitignored and therefore detects interruption only within one
  worktree; a durable committed transaction marker is still required.
  Owner: M6.*
- [ ] **F9** Scaffold edits production files in place with no candidate
  tree or checkpoint; `SCAFFOLD.md` can lag the code. *Progress: a candidate
  tree now exists and is committed rather than hidden —
  `halucinator/candidates/integration-*/` for the full-crate candidate,
  `halucinator/candidates/driver-*/` for disposable driver work, and
  `halucinator/test-candidates/<name>/` for test revisions — and the frozen
  ordering in `hal-integrator.md` requires build, verification and review in
  that candidate before any canonical byte moves. The retrofitted skills now
  defer to the `global:hal-integration` lock, frozen candidate order and
  committed candidate roots and no longer describe in-place production edits.
  Residual: durable journalling, owner fencing, cross-clone crash markers and
  a mechanical tie from `SCAFFOLD.md` to the bytes it describes are still
  required. Owner: M6.*
- [ ] **F10** Locks are gitignored, so crash evidence does not survive a
  fresh clone or a second machine. `.opencode/schema/layout.md` states
  this limitation explicitly; a durable record outside `.run/` is
  required for cross-clone recovery. *Owner: M6.*
- [ ] **F11** The M6-only lock fields reserve identities only. Board lease
  and HIL recovery still need operation phase, last-attempted operation,
  board recovery detail (active image, RAM/flash mode, reset/halt state,
  probe session, safe-state procedure, teardown evidence), an owner
  fencing token, and PAC baseline/candidate manifests. Adding them
  requires the schema-version transition defined in
  `.opencode/schema/handoff-common.md`. *Owner: M6.*
- [ ] **F13** No durable integration journal. `hal-integrator` is now the
  sole writer of every shared and canonical file and the sole committer, and
  M2 gives it prose discipline only: a `kind="stage"` lock carrying a
  cooperative `global:hal-integration` resource, a preflight, and a
  "do not continue in place — resume in a fresh candidate" recovery rule.
  Nothing records which phase an interrupted integration reached, so a crash
  between "copy exact bytes to canonical paths" and "commit" is
  indistinguishable from one that never started. This generalizes F8 from the
  PAC to every canonical mutation and needs F10's cross-clone durability and
  F11's phase and fencing fields; it is not a separate mechanism, and closing
  it requires the `schema = 2` transition. *Owner: M6, with F8/F10/F11.*
- [ ] **F14** No durable coordinator dispatch ledger. `hal-coordinator`
  writes its intent, owner, inputs, expected output and exit criteria to
  `halucinator/docs/<target-id>/notes/ROADMAP.md` before dispatching, but
  `state.stages[]` requires a *returned* handoff FileRef, so
  dispatched-but-never-returned work has no typed representation at all. A
  fresh session sees a stage lock with no handoff and can only guess. The
  ROADMAP is prose and is not a transaction ledger. Recording in-progress
  dispatch typedly needs `schema = 2` and belongs with F10/F11's recovery
  work. *Owner: M6, with F10/F11.*
- [ ] **F12** `state.toml` compare-and-swap protects cooperating writers
  only. An uncooperative writer can overwrite it with valid TOML and a
  plausible generation, and the validator cannot reconstruct the prior
  value. Recorded in `.opencode/schema/validate.md` limits. *Owner: M6.*

---

## G. Documentation

- [ ] **G1** No getting-started tutorial. The path dead-ends after
  restart (`README.md:96-99`) and "hal-architect is the entry point"
  (`:150-151`) with no prompt to type and no expected response.
- [ ] **G2** No worked artifact set. Templates exist
  (`source-list-format.md:81-164`); completed examples do not. Nobody can
  see what good output looks like.
- [x] **G3** No `opencode.json` anywhere. Nothing sets `default_agent`, so
  a user who follows the install gets the built-in `build` agent.
  *(Closed by the root `opencode.json` setting
  `default_agent: hal-coordinator`, checked for strict JSON and for the
  default agent resolving to an existing primary agent. The install
  procedure copies it as a third item alongside `AGENTS.md` and
  `.opencode/`.)*
- [x] **G4** The GPIO/time-only scope restriction lives only in
  `hal-architect.md:51-95`. README advertises general peripheral drivers
  (`:127-132`) and never mentions it. *(Closed: the temporary restriction is
  removed from `hal-architect.md`. Scope now lives in `hal-coordinator`'s
  `state.toml`, an immutable scope decision, and the ROADMAP, and contains
  user-requested items only — an unsupported workflow is excluded or
  blocked, never silently accepted. The remaining gap is capability, not
  documentation: only GPIO and time have driver skills — see H1 and D13.)*
- [x] **G5** Terminology drift: stage / phase / step / milestone used
  interchangeably; target / chip / part / exact-MCU for overlapping
  identities; `type-state` (`README.md:146`) vs `Typestate`
  (`AGENTS.md:93-98`); British `behaviour` / `normalise` /
  `initialisation` in agents vs American in skills. *(Closed by the canon
  in `.opencode/schema/terminology.md`; mechanical enforcement covers only
  the five unambiguous tokens `type-state`, `Typestate`, `behaviour`,
  `normalise`, and `initialisation`; migration of legacy occurrences is
  M3/M7.)*
- [ ] **G6** `AGENTS.md` at 360 lines does four jobs: design philosophy
  (`:23-105`), pipeline (`:109-170`), artifact policy (`:172-283`), hard
  rules (`:287-360`). Philosophy precedes action.
- [x] **G7** Hard rules have no stable IDs, so skills and review findings
  must restate their prose to cite them. *(Closed by adding
  `HAL-RULE-01`…`HAL-RULE-12` inline to `AGENTS.md`.)*
- [ ] **G8** No glossary. SVD, PAC, metapac, chiptool, teleprobe, HIL,
  DEVGUIDE, typestate, `Gate`, `WaitCell`, `OnDrop` all appear undefined.
- [ ] **G9** No prerequisite matrix. Embassy checkout (`README.md:28-38`),
  `pdftotext` (`:193-196`), chiptool, XML validators, Rust targets, probe
  and runner are scattered across five documents.
- [ ] **G10** No `CONTRIBUTING.md`. The repo explains how agents build
  HALs, not how to add a skill or agent.
- [x] **G11** No skill template document. *(Closed by the canonical
  `docs/skill-template.md`, whose structure is mechanically enforced by the
  five skill-template checks named in D3.)*
- [ ] **G12** `embassy-mcxa` is cited narrowly. `src/i2c/` is the standing
  fallback; the whole crate is the north star and the concern map
  (`AGENTS.md:41-52`) should be the entry point.
- [ ] **G13** README manually counts six agents and seven skills
  (`:14-26`) — drift-prone.
- [ ] **G14** License is `TBD` (`README.md:203-205`) while the install
  procedure copies the toolkit into other repositories.
- [~] **G15** No changelog or versioning story for skills. *Deferred.*
- [~] **G16** Quoted DEVGUIDE section names are not exact current
  headings (`AGENTS.md:44,104`). *Deferred: fix when the concern map is
  next revalidated.*
- [~] **G17** Global install copies `.opencode/node_modules`
  (present in this checkout). *Deferred: packaging concern.*

---

## H. Promises without implementation

Asserted capabilities with no procedure sufficient to perform them.

- [ ] **H1** General peripheral-driver generation
  (`README.md:127-132`) — only GPIO and time exist.
- [ ] **H2** PAC generator setup (`generate-pac/SKILL.md:4-8`) ships no
  generator, schema, templates or tooling; it instructs the agent to
  author "minimal tooling" after inspecting NXP
  (`generation-and-checks.md:126-132`). That is a design assignment, not
  a capability.
- [~] **H3** Teleprobe HIL (`AGENTS.md:143-145`, `hal-tester.md:4-8`) —
  no command procedure, manifest template or result protocol.
  `write-examples/SKILL.md:75-80` says to copy whatever the live checkout
  has. *Deferred: depends on a live checkout.*
- [~] **H4** Hardware execution across arbitrary devices
  (`README.md:187-191`) — no loader/probe adapters, device database or
  output parser. *Deferred with H3.*
- [ ] **H5** RAM-first loading (`hardware-execution.md:50-83`) is policy
  with no linker-generation procedure or ELF inspection command set.
  Blocked on C1.
- [x] **H6** Automated stage gating — no state machine or validator.
  Completion is whatever the current model says after reading Markdown.
  *(Closed: `.opencode/schema/validate.py` enforces schema, dependency graph,
  scope lineage, freshness and review gating, and every retrofitted skill
  invokes it before consumption, at publication and at the final all-gate.
  Enforcement remains an honour system: self-check proves a skill contains
  the instructions, never that an agent ran them, and the validator cannot
  attest to its own prior execution. See H11.)*
- [ ] **H7** Generated-code and fork provenance enforcement
  (`AGENTS.md:311-317`) — no check detects edits to generated output or
  scans dependency URLs and revisions.
- [~] **H8** Skill acceptance testing. The SVD and PAC references list
  acceptance scenarios (`preparation-and-checks.md:262-287`,
  `generation-and-checks.md:372-404`) with no fixtures, runner or
  recorded results. *Deferred.*
- [ ] **H9** The `.gitattributes` byte policy specified in
  `.opencode/schema/validate.md` is not installed anywhere. Raw-byte
  SHA-256 hashes are stable only where `core.autocrlf=false`; a clone
  configured otherwise breaks every hash. *Owner: M3.*
- [ ] **H10** The 944-file fixture tree was generated by a script that
  lives outside the repository. The fixtures are committed and
  self-sufficient, but nothing in-tree can regenerate them and no owner is
  named. *Owner: M3 or M7.*
- [ ] **H11** Validator invocation is an honour system. The retrofitted
  skills wire the validator at every required point and self-check proves
  those instructions are present, but nothing proves an agent ran them and
  the validator cannot attest to its own prior execution. This limitation is
  recorded in `.opencode/schema/selfcheck.md` and `docs/skill-template.md`;
  no M3 text describes the wiring as runtime enforcement. *Owner: M6.*

---

## What the review found working

Recorded so it is not lost in a refactor.

- SVD/PAC derived-run discipline: fresh unused run directories, never
  reuse a populated run, corrections applied from the original input
  rather than the last result, byte-identical replay, candidate/replay
  isolation before canonical replacement, expected-vs-generated inventory
  comparison (`preparation-and-checks.md:22-34,228-232`,
  `generation-and-checks.md:14-29,284-299`).
- Anti-vacuity rules — "a call with no files is not evidence"
  (`preparation-and-checks.md:195-196`), and the parallel rule at
  `generation-and-checks.md:296-299`. The most machine-checkable content
  in the corpus.
- Hardware authorization: exact fixture and named operations, separate
  physical-readiness and operation authorization, reconfirmation after
  changes, mass erase / unlock / fuse / option-byte operations prohibited
  outright (`hardware-execution.md:14-48,74-83`).
- GPIO loopback electrical care: never join driven outputs, configure
  input before output (`gpio-validation.md:82-105`).
- Record invalidation contracts in the `write-*` records
  (`gpio-record.md:77-81`, `time-record.md:69-74`,
  `test-record.md:101-105`) — genuine resumption, the best in the set.
- Degraded paths that fail closed: missing foundation PAC items block all
  scaffold implementation (`scaffold-hal/SKILL.md:97-106`); a failed
  partial output may not be redeclared as a narrower completed scope
  (`generate-svd/SKILL.md:168-173`, `generate-pac/SKILL.md:102-106`).
- The `embassy-mcxa` concern map (`AGENTS.md:27-56`) — turns an abstract
  dependency into per-task file paths.
