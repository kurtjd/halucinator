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
- [x] **A14** The typed schema is defined, validated and fixture-tested.
  *(Closed by M5, and this is M5's headline: the pipeline
  `01 → 02 → 03 → 04 → 05 → 06 → 07 → 08` now traverses end to end, and the
  last capability stall is gone. Each producer writes a deterministic
  handoff — `halucinator/handoff/01-sources.toml`, `02-facts.toml`,
  `03-svd.toml`, `04-pac.toml`, `05-platform.toml`, `06-driver-<name>.toml`,
  `07-tests-<name>.toml`, `08-review-<artifact>.toml` — and each consumer's
  declared admission matches the producer's declared emission field for
  field, verified against the AST-derived registry from
  `.opencode/schema/validate.py`. The `unresolved` source route correctly
  admits nothing.*

  *What is typed and what is merely procedural must not be conflated.
  `01→02`, `02→03` on the author route, `03→04`, `04→05`, `05→06` and
  `06→07` are **validator-enforced dependency edges**, and `06→07` is bound
  by exact path via A19's `tests.api_handoff` resolution. **`07→08`
  selection is procedural**: an `08-review` records which artifact it
  reviewed, but nothing statically proves which producer handoff the
  coordinator selected and froze for that review. The internal ordering of
  the three `05-platform` slices is likewise procedural — see A23, which
  records that gap and owns it.*

  *M5 removed the stall by adding `extract-hardware-facts` as the
  template-conforming `02-facts` producer, so `generate-svd` on the
  `author-from-docs` route can now reach `ready`. M3 closed `01 → 05`,
  M4 closed `05 → 06 → 07`.*

  *The `07` emitter set is two, not one. Correcting the stale M4 claim
  previously recorded here: `write-examples` is the ordinary
  `07-tests-<name>` producer from a `06-driver` handoff. `debug-hardware`
  is a second `07-tests` emitter: it consumes a preserved failing
  `07-tests` plus its exact `06-driver`, and publishes a distinct
  `07-tests-<source-name>-debug-<run-id>` revision without replacing the
  original.*

  *What M5 shipped and then caught, recorded because it happened:*

  1. *Two independent premium spec reviews returned **`not-ready`** on M5's
     first design, in which four skills independently wrote the singleton
     `05-platform.toml`. A later slice could silently erase an earlier
     slice's platform view, and because the canonical ten-check set carries
     one entry per check ID, a final handoff could look complete while
     proving only the last slice. Restructured into an ordered
     snapshot-consuming chain with exactly one consolidator: `write-clocks`,
     `integrate-interrupts` and `integrate-runtime-linker` emit partial
     views only, and `scaffold-hal` is the sole final consolidator,
     consuming the final slice snapshot.*
  2. *The compliance review found **five blocking defects in the committed
     state**. Two mattered most: `generate-svd` still told the agent to stop
     because no facts skill existed — which would have left this entry's
     headline claim false — and `write-driver` still asserted that driver
     evidence had no registered ownership class, contradicting C11.*
  3. *A latent defect of the **exact M4 shape** was found and fixed: the
     skill-reference scanner matched only the verb prefixes
     `write|review|generate|gather|scaffold|extract`, so
     `integrate-interrupts`, `integrate-runtime-linker` and `debug-hardware`
     would have been **silently skipped**. Same failure as M4's hard-coded
     review-gated tuple: a derivation that looks general and is not.*
  4. *`review-artifact`'s accepting-verdict sentence was asserted by
     nothing. It **emits** verdicts rather than consuming a gate, so it fell
     outside the derived gated set. The derivation was sound; the coverage
     was not. Fixed by making the `08-review` emitter a subject too.*
  5. *Two self-checks initially rejected **conforming** corpus and had to be
     narrowed. The worked-example analyzer rejected `trait_obligations = []`
     — the template's own mandated form for a known-empty collection, and a
     form `validate.py` accepts. A check that rejects the canon is a defect
     in the check.*
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
  heterogeneous permission parsing, every invoked check, the AST-derived
  registry, raw-fence parsing, bounds and timeouts, and the honour-system
  limitation. M4 retired the two-generation allowlist section with the file
  itself and documented the 33 checks that now run.)*
- [x] **A18** An arbitrary `state.decisions.destination_crate` defeats the
  static permission globs. The tester's blinding denies `embassy-*/**` and
  the driver and integrator are bounded by `embassy-*/` patterns; a HAL crate
  placed anywhere else is outside all of them, and agent frontmatter cannot
  interpolate a runtime path. Investigate destination-aware policy without
  claiming dynamic frontmatter generation. *(Closed by M6.
  **MECHANICALLY ENFORCED:** schema 2 constrains `destination_crate` to a
  repository-root one-segment `embassy-<vendor_id>`, rejecting a named root, a
  nested path or an alias with `ILLEGAL_ENUM`, so the configured destination is
  always inside the tester's `embassy-*/**` deny glob; `tester-destination-coverage`
  additionally requires `hal-tester.md`, `write-examples/SKILL.md` and `README.md`
  to state the constraint, its coverage, and the residual in that order.
  **DOCUMENTED ONLY:** overall blindness. `bash` is `ask`, `grep` is matched
  against the query rather than the path, and filenames, compiler and
  build-script diagnostics, history and tools still quote source. The corpus now
  says so instead of claiming closure.)*
- [x] **A19** **ESCALATED — validator soundness defect.** *(Closed by M4 in
  `.opencode/schema/validate.py`: a `World.by_path` index now supplements
  `by_stage`, so `06-driver-<name>` handoffs no longer collapse into one
  entry. `07-tests` resolves `tests.api_handoff` by path to a real
  `06-driver` at any status, emitting `ILLEGAL_ENUM` when the binding
  resolves to nothing or to another kind, and when the `07` is `ready` it
  requires that exact driver handoff to be ready with `DEPENDENCY_NOT_READY`.
  `write-tests` was removed from the generic `by_stage` dependency map and
  exact singleton filenames are enforced for `01`–`05`. No
  `tests.name == driver.name` rule was added: two reviews rejected it
  because `write-examples`'s own canonical example binds
  `tests.name = "uart-loopback"` to `06-driver-uart.toml`. No new diagnostic
  code; `schema = 1` unchanged. Fixtures 30, 31 and 32 and the second
  accepted root `fixtures/valid-multi-driver/` prove correct and incorrect
  pairings. The stale disclosure in `write-examples/SKILL.md` was corrected.)*
- [x] **A20** Architect terminology in
  `.opencode/schema/validate.py:1049-1066` and in
  `.opencode/schema/validate.md`'s dependency-graph clause. *(Closed by M4:
  attribution only, no field, code or schema change. The validator prose and
  the `PAC requires ready SVD plus current coordinator decisions` clause in
  `validate.md` now name `hal-coordinator`.)*
- [ ] **A21** No typed peripheral inventory in `02-facts`.
  `.opencode/schema/02-facts.md` carries cited fact notes, categories and
  contradictions, but no typed list of the peripherals the reference manual
  actually describes. `write-driver` therefore has no typed source for "which
  peripherals exist on this part" and must degrade to
  `state.decisions.first_peripheral` and `peripheral:*` scope IDs chosen by
  the coordinator. M4 deliberately invented no field: adding one is a schema
  change and belongs with the facts procedure. *Escalated by M5, not closed:
  `extract-hardware-facts` now exists and emits `02-facts`, so the procedure
  this entry was waiting on has landed — and it still carries categories and
  citations rather than a typed peripheral inventory. The scope IDs and
  coordinator decisions remain the procedural substitute. M5 did not violate
  `schema = 1` to fake the field. Owner: M6, with A22's schema-version
  transition.*
- [ ] **A22** No typed peripheral-taxonomy or profile discriminator.
  `write-driver` selects a GPIO, Embassy-time-service or bus profile, and
  that choice determines its architecture, lifecycle and scheduling rules —
  but `schema = 1` is frozen and no `06-driver` leaf can encode it.
  `driver.capabilities` and `driver.public_api` are free-form strings, and
  `driver.scope_kind` admits only `full|scaffold-support`. The only guard
  that the declared profile matches the implementation is hashed prose plus
  independent review, which is **advisory, not mechanical**: a driver can
  claim a bus profile and implement a time service without any typed
  contradiction. *Escalated by M5, not closed: the discriminator is still
  absent, selection remains hashed prose plus review, and `write-dma` adds
  another driver shape to the set the discriminator would have to span.
  Closing it needs the schema-version transition in
  `.opencode/schema/handoff-common.md`. Owner: M6.*
- [ ] **A23** Platform slice lineage is typed only at the boundary. M5 split
  platform work into three partial-view slices — `write-clocks`,
  `integrate-interrupts`, `integrate-runtime-linker` — consumed in order and
  finally consolidated by `scaffold-hal`, which reads the final slice
  snapshot. The stage boundary into `05-platform` is typed; the chain inside
  it is not. `schema = 1` cannot identify which slice produced a given
  snapshot, and cannot enforce slice order. Candidate snapshots are neither
  discovered nor reparsed by `.opencode/schema/validate.py`; hashes prove
  freshness only, never provenance. A reordered or incomplete chain can
  therefore satisfy the typed stage boundary if procedural review misses it.
  Closing it requires a schema-version transition or validator-visible
  snapshot metadata. *M6 deliberately added no lineage field: the narrowed
  schema-2 package covers citation verification and the HIL interlock only, and
  an unapproved provenance field would have implied a closure that does not
  exist. The corpus states that the validator cannot independently prove slice
  order or provenance. Still open. Owner: post-M7.*

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
- [x] **B4** `hal-datasheet`'s hardware-analysis half has no skill.
  `hal-datasheet.md:78-79` separates it explicitly; only the collection
  half is covered. Its output format (`hal-datasheet.md:140-153`) and the
  skill's (`gather-documentation/SKILL.md:186-195`) are two different
  seven-item lists nobody reconciles. *(Closed by M5's
  `.opencode/skills/extract-hardware-facts/`: the template-conforming
  hardware-analysis procedure and the sole typed `02-facts` emitter,
  consuming `01-sources`. The two unreconciled seven-item lists are
  superseded by one typed emission. This is the procedure A14's `01 → 02`
  boundary was stalled on; the residual that `02-facts` still carries no
  typed peripheral inventory is A21, and that citations are unverified is
  E1.)*
- [x] **B5** `hal-reviewer` does not exist as a stage. `AGENTS.md:127`
  claims it gates everything; the reviewer never claims it, has no skill,
  has `edit:deny` + `task:deny` (no gate authority), describes its output
  as *"for recording"* (`hal-reviewer.md:131`), and is absent from four of
  the files covering the stages it supposedly gates. *(Closed: gate authority
  sits explicitly with `hal-coordinator`, and the reviewer is a real typed
  stage — it emits an `08` verdict, authors the `REVIEW-*.md` findings content,
  holds a narrow write permission for exactly that handoff, and has an explicit
  dispatch payload. Its own skill is the only residual, and that is tracked as
  D12. M5 closes that residual too: `.opencode/skills/review-artifact/` is
  the reviewer's own typed procedure, emitting `08-review` from any one of
  `01`–`07`, so the reviewer now supplies its own procedure rather than
  borrowing the dispatching skill's. Nothing remains under this entry.)*
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
- [x] **B8** Loading a driver skill loaded the full implementation procedure
  into the tester's context before any "stop reading here" row could take
  effect. *(Closed by M4: `write-gpio` and `write-time-driver` are deleted,
  their validation matrices migrated to tester-safe profiles under
  `.opencode/skills/write-examples/references/profiles/`, and the tester now
  loads `write-examples` and nothing else. `hal-tester.md` states "Never load
  `write-driver`, its implementation procedure, private checklist, or driver
  record", and the new `validation-guidance-isolation` self-check is a
  **bounded lexical tripwire** over everything under `write-examples/`: it
  rejects a relative link that resolves into `.opencode/skills/write-driver/`
  and fourteen concrete implementation tokens, and is self-tested against seven
  near-misses. It is the same shape as the two-token `DRIVER_API_LEAK` tripwire
  in `.opencode/schema/06-driver.md`, with the same limit — it catches the named
  links and tokens and nothing else. Semantic implementation guidance written as
  plain prose ("write the control register, then enable its interrupt") matches
  no token and passes. The tripwire raises the cost of the cheap, mechanical
  leak; human review remains the real boundary.)*
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
  *procedure* was still missing and tracked as H5; M5 closes that too, in
  `.opencode/skills/integrate-runtime-linker/`, which owns candidate
  linker and runtime work, RAM-first candidate configuration and ELF
  load/run-address inspection. Nothing remains under this entry.)*
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
  *Partial after M5. The seven new skills do supply the missing half: each
  gives explicit `unrun` handling, a remedy paragraph, and an
  `environment:<capability>` blocker naming what is absent and who must
  install it, so a missing target no longer reads as an unexplained stall.
  The pre-M5 SVD, PAC, scaffold, driver and test procedures still mostly
  stop at `unrun` or `blocked` without the same complete
  installation/exposure handoff, so the toolkit now says two different
  things depending on which stage you are in. Remaining: audit and
  standardize the remedy wording across the pre-M5 procedures before
  closing. Owner: M6.*
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
- [x] **C11** No registered ownership class for driver evidence.
  `.opencode/ownership.toml` gives `driver-candidates` the pattern
  `halucinator/candidates/driver-*/src/**` and `peripheral-modules` the
  patterns `embassy-*/src/**` and `halucinator/candidates/driver-*/src/**`,
  so `halucinator/candidates/driver-*/evidence/**` matches **no**
  `[[file_classes]]` entry — verified against the registry. The comparable
  integrator class `integration-candidates` covers
  `halucinator/candidates/integration-*/**`, the whole subtree. `write-driver`'s
  evidence logs and its profile-classification record therefore have no
  registered owner, while the tester's equivalent
  (`test-candidate-evidence`) does. Widening the pattern or adding a class
  is an ownership-registry change. *(Closed by M5: a `driver-evidence`
  class is registered in `.opencode/ownership.toml`, and the owning skill
  and agent both claim it. `write-driver`'s stale prose asserting that
  driver evidence had "no registered class" is corrected — the compliance
  review caught that contradiction still standing in the committed state,
  which would have left the registry and the skill disagreeing about a gap
  this entry had just closed.)*
- [x] **C12** No generic durable driver-record path. `driver-records` registers
  exactly `halucinator/docs/*/notes/GPIO.md` and
  `halucinator/docs/*/notes/TIME-DRIVER.md`. A bus driver, or any driver whose
  profile is not one of those two, has no durable record file to be written
  into and relies entirely on the typed `06-driver`, the hashed
  `handoff.notes`, evidence FileRefs and citations. A generic path — a
  per-peripheral `notes/drivers/<name>.md`, say — needs an ownership-registry
  change, which M4 was not scoped to make. *(Closed by M5: `driver-records`
  is widened with `notes/drivers/**`, so the generic per-peripheral
  `notes/drivers/<name>.md` path is registered. The write is split along the
  established seam rather than handing the driver a canonical file:
  `hal-driver` authors the delta, and `hal-integrator` materializes it via
  `hal-coordinator`. `write-dma` is the first driver to need this — its
  record is neither GPIO nor time.)*

---

## D. Skills

- [x] **D1** Per-driver skills do not scale. *(Closed by M4: the two
  per-peripheral skills are replaced by one generic
  `.opencode/skills/write-driver/`, which applies the universal driver
  obligations to every peripheral and then selects a GPIO, Embassy-time-service
  or bus profile from `references/profiles/`. The documented fallback is no
  longer "read `embassy-mcxa/src/i2c/` and improvise" but a template-conforming
  procedure with a private checklist and driver record.)*
- [x] **D2** The tester is self-blocked for unskilled peripherals. *(Closed by
  M4: `write-examples` now carries a `universal` tester-safe validation profile
  alongside `gpio`, `time-driver` and `bus`, so a UART tester has a required
  reference to load and is no longer blocked by its own skill.)*
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
- [x] **D7** Missing skill: hardware-fact extraction (see B4). *(Closed by
  M5: `.opencode/skills/extract-hardware-facts/`, owned by `hal-datasheet`,
  emitting `02-facts` from `01-sources`.)*
- [x] **D8** Missing skill: clock tree bring-up. *(Closed by M5:
  `.opencode/skills/write-clocks/`, owned by `hal-driver` with
  `hal-integrator` as emitter, consuming `04-pac` and emitting a
  **`05-platform` partial view only** — it is the first of three slices and
  never the consolidator. B12's clocks assignment and the architect's
  contract are unchanged.)*
- [x] **D9** Missing skill: interrupts / NVIC / `interrupt_mod!`. *(Closed
  by M5: `.opencode/skills/integrate-interrupts/`, owned by
  `hal-integrator`, consuming the preceding `05-platform` snapshot and
  emitting a **partial view only**.)*
- [x] **D10** Missing skill: runtime + linker integration (`memory.x`).
  *(Closed by M5: `.opencode/skills/integrate-runtime-linker/`, owned by
  `hal-integrator`, consuming the preceding `05-platform` snapshot and
  emitting a **partial view only**. It also carries the RAM-first candidate
  configuration and ELF inspection procedure that closes H5, and is the
  named owner C1 was missing.)*
- [x] **D11** Missing skill: DMA subsystem. *(Closed by M5:
  `.opencode/skills/write-dma/`, owned by `hal-driver`, consuming
  `05-platform` and emitting `06-driver-dma`. It is the first driver whose
  durable record is neither GPIO nor time, which is what forced C12.)*
- [x] **D12** Missing skill: artifact review (the reviewer's own skill).
  *(Closed by M5: `.opencode/skills/review-artifact/`, owned by
  `hal-reviewer`, consuming any one of `01`–`07` and emitting `08-review`.
  This closes B5's last residual. Its accepting-verdict sentence was
  initially asserted by nothing — as an emitter of verdicts rather than a
  consumer of a gate, it fell outside the derived gated set; fixed by making
  the `08-review` emitter a subject of that check too.)*
- [x] **D13** Missing skill: generic driver scaffolding, replacing the
  per-peripheral skills. *(Closed by M4: `.opencode/skills/write-driver/`
  with `references/driver-checklist.md`, `references/driver-record.md` and
  `references/profiles/{gpio,time-driver,bus}.md`. It is mapped in
  `SKILL_SPEC` as the typed `06-driver` producer consuming `05-platform`,
  and passes all thirteen skill-contract checks. This also retired M3's
  time-boxed exemption: `tools/skill-template-allowlist.tsv` existed only to
  let `write-gpio` and `write-time-driver` lag the template, and with them
  gone the file, its parser, the `M3_CHECKS` registry, the `m3_check`
  decorator, every `excluded: frozenset[str]` parameter and the
  `skill-generation-allowlist` check were all deleted together. Deleting the
  data alone would have been unsafe — `skill_exclusions()` failed **open to
  the empty set**, so a check reading a vanished file would have kept
  reporting `PASS` while asserting nothing. The thirteen remaining
  skill-contract checks are now ordinary functions invoked directly from
  `main()`. Eleven scan every discovered skill; two are narrowed by an explicit
  documented predicate rather than by any exemption file — `skill-note-paths`
  applies only to `generate-svd` and `generate-pac`, the two stages with a
  deterministic first-note path, and `skill-verdict` applies only to skills
  declaring the `independent-review` check. Each check was shown to reject a
  deliberately non-conforming skill **within its applicability class**, rather
  than merely to pass today. The applicability classes were not initially
  correct: the compliance review of M4 found that the review-gated set was a
  hard-coded tuple omitting `write-driver`, so the review gate `write-driver`
  declares was asserted against nothing and both of its accepting-verdict
  sentences could be deleted with the suite still exiting 0. Recorded because it
  happened, not because it did not. The fix derives the gated set from each
  skill's parsed `checks:` declaration, fails with `SKILL_VERDICT_NO_TARGETS`
  if that set is ever empty, and was proven by a negative mutation in a
  throwaway copy: with both sentences removed the suite exits 1 with
  `SKILL_VERDICT_SENTENCE_MISSING`.)*
- [x] **D14** Missing skill: hardware debugging of a failing driver.
  *(Closed by M5: `.opencode/skills/debug-hardware/`, owned by `hal-tester`,
  consuming a `06-driver` plus its preserved failing `07-tests` and emitting
  a `07-tests` revision under a **distinct** name —
  `07-tests-<source-name>-debug-<run-id>` — so the failing evidence is never
  replaced. This makes the toolkit's `07` emitter set two, not one, which is
  the stale claim corrected in A14. Source blindness is unchanged: the
  debugger is still denied `embassy-*/src/**` and still works from the
  public contract, which is the hardest constraint in the skill and the
  reason it is a tester skill rather than a driver one.)*
- [~] **D15** Missing skill: upstream PR preparation. *Deferred with C8.*
- [~] **D16** Missing skill: chip-family expansion. *Deferred with C9.*
- [x] **D17** Operational rules that static validation cannot express need
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
  which introduce that tooling.* *(Closed by M6.
  **ENFORCED, over the constructed cases only:** `.opencode/schema/runtime.py`
  is the production helper, `.opencode/schema/test_runtime.py` drives it as a
  subprocess, and `runtime-protocol-tests` runs that suite inside the
  self-check, requiring all eight named faults. Separately, black-box checks
  drive the CLI in a throwaway directory and confirm the helper refuses absent
  evidence, refuses an override without a record, refuses a live owner, and
  performs a real compare-and-swap.
  **HONOUR SYSTEM - operability beyond the paths actually constructed.**
  Coverage is derived from test NAMES and DOCSTRINGS: a test named for a fault
  it does not inject is invisible to the gate. More importantly, a green suite
  is not a demonstration that the documented route works: this recheck found
  two defects the suite did not - a second recovery operation that silently
  dropped the first child session from the lock, so a probe that may still be
  driving pins stops being recorded, and runtime-written locks that the static
  validator rejects, so helper and validator disagreed about a legal worktree.
  Both are being repaired in the helper and this entry deliberately claims
  nothing about them until they land and are checked. **No recovery has been
  taken end to end on real hardware.** Treat the path as specified and
  unit-exercised, not as shown to work. The broker, cross-clone and
  physical-truth residuals are closed by nothing in M6 - F15, F16, F17.)*
- [x] **D18** Skill ownership text contradicts the agent contracts. M2 could
  not edit a `SKILL.md`, so nine verified conflicts remain, enumerated once
  in `README.md` and referenced by ID from each affected agent: skills still
  assign shared files and clocks to `hal-architect`, binaries and CI to
  `hal-tester`, `SOURCES.md` writes to `hal-datasheet` and `hal-svd`, durable
  records to `hal-driver`/`hal-architect`, `SCAFFOLD.md` and the roadmap to
  `hal-architect`, dispatch to `hal-architect` rather than
  `hal-coordinator`, and the legacy spaced rejection spelling rather than
  the typed verdict tokens. *(Closed by M4: the retrofit resolved the
  skill-layer conflicts in the five retrofitted skills, and M4 resolved the
  last two by deleting the skills they cited. Conflicts 6 and 9 are now
  recorded in `README.md` as historical text with no dangling links: the
  GPIO and time durable records and their routing/verdict prose lived in
  `write-gpio` and `write-time-driver`, which `write-driver` replaces. Every
  conflict ID and its identifying text is preserved, so the eight agents'
  declared conflict-ID sets still match the inventory. D20's per-conflict
  audit and citation refresh remain open with M7.)*
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

- [x] **E1** No citation verification. Rule 1 forbids invented hardware
  facts (`AGENTS.md:291-299`) but a syntactically plausible section
  number satisfies the output shape and survives to silicon. This is the
  highest-severity gap in the project: the one failure mode that produces
  confident, compiling, wrong output. *Escalated by M5, not closed.
  `extract-hardware-facts` materially improves the raw material: every fact
  in `02-facts` now carries a source ID, a document revision, a locator and
  a hashed quoted excerpt, so M6 finally has something to verify against.
  What is still missing is the verification itself — nothing checks that the
  locator resolves to a real place in a real document, and nothing checks
  that the quoted excerpt actually supports the assertion attached to it.
  The skill explicitly disclaims mechanical verification rather than
  implying it, which is the right disclosure and not a fix. A fabricated
  locator with a fabricated excerpt still passes every check in the suite.
  Owner: M6, with E2.* *(Closed by M6.
  **MECHANICALLY ENFORCED:** schema 2 replaces the independently-membered
  source list with a `sources.documents` binding of source ID to hash-pinned
  bytes; the v2 `CitationRef` carries `assertion_id`, `scope_item`, `claim`,
  `source_id`, `source`, a tagged `location` (`pdf-page` or `text-lines`),
  printed `locator`, `excerpt` and `note`; and the mandatory `citations-verified`
  check makes `validate.py` itself re-derive the cited location from those bytes
  - running `pdftotext -layout -f <page> -l <page> <source> -` for a PDF - and
  match the normalized excerpt, failing closed with `CITATION_UNVERIFIED` and a
  `poppler-utils` remedy when the tool is missing. There is deliberately no
  agent-authored extraction field. `citation-verification-corpus` holds the six
  E1 files to that story and rejects any that still routes evidence through an
  agent extraction, retains a retired v1 leaf, drops the remedy, or describes
  the gate without stating what it cannot prove - that last check is **corpus
  wording only**, unlike the verifier above it, which genuinely derives text
  from pinned bytes and is the one mechanism in this milestone that does what
  its name says.
  **DOCUMENTED ONLY:** the gate proves normalized occurrence at the cited
  location, not visual contiguity, semantic entailment, OCR correctness, vendor
  truth, or that an agent ran the validator. Aggressive normalization can join
  column-separated text, so review still owns support. E2's end-to-end
  corruption chain is narrowed, not closed.)*
- [ ] **E2** Silent corruption chain. A hallucinated offset becomes a
  wrong SVD, a wrong PAC, a driver that compiles and does nothing, and a
  bench session that blames the driver. No detection exists before the
  bench. *Narrowed by M6's E1 gate: an offset whose excerpt does not occur at
  the cited location in the bound source bytes is now rejected before the SVD.
  An offset whose excerpt does occur but does not mean what the claim says is
  still undetected, and nothing downstream of `02-facts` re-derives it. Still
  open. Owner: post-M7.*
- [x] **E3** MCXA implementation choices are mandated as universal
  architecture. `AGENTS.md:305-309`, `hal-architect.md:110-114` and
  `hal-driver.md:61-80` required, for arbitrary vendors, the shapes that are
  only MCXA examples - `Gate`, `enable_and_reset`, `PreEnableParts` and
  `WakeGuard`. The invariant is universal; those type names are an example. *(Closed by M6.
  **LEXICALLY ENFORCED - corpus text, nothing more:** `mcxa-example-boundary`
  scans a derived subject set of governed files and rejects a sentence
  containing one of a small set of MCXA helper tokens unless that same sentence
  also contains one of a small set of framing words; it requires two files to
  contain eight literal contract terms and six to contain a
  framed-mention phrase. That is the whole of what a program decides here.
  **HONOUR SYSTEM - everything the item is actually about:** that the lifecycle
  contract is *universal*, that a target's real ownership shape is stated, that
  the eight terms are used rather than merely present, and that a generated HAL
  does not copy MCXA topology under other names. The check's own PASS line says
  so: a corpus mandating a `UniversalGate` and a required instance trio matches
  no token and passes. Rewording satisfies this check; redesigning is what the
  item asked for, and nothing verifies that. Carried as H17.)*
- [x] **E4** Rule 7's "clear them in one write" (`AGENTS.md:319-321`,
  `hal-driver.md:89-92`) is destructive where flags span registers or mix
  W1C/W0C/read-only/control bits. The operation must derive from cited
  per-register semantics. *(Closed by M6.
  **LEXICALLY ENFORCED - corpus text, nothing more:** `error-clear-semantics`
  rejects three literal phrases in six named files and requires four literal
  terms in each, plus W1C and W0C somewhere in the group. A file can satisfy
  every one of those string tests while describing the wrong procedure.
  **HONOUR SYSTEM - everything the item is actually about:** that a driver
  observes every relevant condition, preserves unrelated and control bits, and
  leaves nothing recoverable latched. No driver is compiled, no register is
  read, and no cited per-register semantics are checked against any manual.
  Carried as H17.)*
- [x] **E5** `hal-driver.md:102-105` tells the agent to read the MCXA
  implementation *before* target analysis, priming NXP register
  assumptions into a model about to interpret a different vendor's PDF.
  *(Closed by M6. **STRUCTURALLY ENFORCED in one file:**
  `target-first-driver-order` asserts
  the four reading-order anchors in `hal-driver.md` - validate payload and write
  the target capability/invariant inventory first, then skill selection, then
  profile applicability, then "only now" the live `embassy-mcxa` references -
  requires `## What you do` to be renamed `## Conditional implementation
  obligations` and placed after them, and rejects any `embassy-mcxa/`
  implementation path appearing before the inventory bullet ends.
  **HONOUR SYSTEM:** this asserts the ORDER OF SENTENCES IN ONE MARKDOWN FILE.
  The defect was an agent reading another vendor's implementation before
  analysing its own target, and nothing observes what an agent reads, in what
  order, or whether it read the inventory bullet at all. Reordering a document
  is not reordering a behavior. Carried as H17.)*
- [~] **E6** No transitive invalidation. Every record says dependent
  evidence must be invalidated, but it is manual and local
  (`scaffold-record.md:88-90`, `driver-record.md`,
  `test-record.md:101-105`). Stale records stay labelled
  `software verified` / `passed`. *Partial. Hash-pinned evidence makes stale
  records detectable via `STALE_EVIDENCE` / `STALE_REVIEW`,
  `.opencode/schema/handoff-common.md` defines a re-attestation protocol,
  the retrofitted skills carry it as executable steps including "never
  delete old evidence or old review records to regain validation", and M4's
  `write-driver/references/driver-record.md` carries hashing and the
  normative re-attestation clauses, so the last unretrofitted record is
  gone. Remaining: there is still **no transitive dependency graph** — an
  invalidated `05-platform` does not mechanically mark every `06-driver` and
  `07-tests` derived from it — and still **no false-claim detector**.
  Detection improved; propagation did not. M6 deliberately built no dependency
  graph and changed no schema graph; `validate.md` now states that M6 does not
  propagate beyond declared current one-hop bindings and that cycles and missing
  graph nodes are not represented. Still open, carried as E14. Owner: post-M7.*
- [ ] **E7** No mechanism makes a false verification claim detectable.
  Records are ordinary Markdown written by the same agent doing the work.
  *Unchanged by M4: hashing the driver record improves stale-evidence
  detection, not claim truthfulness. Owner: M6, with E6's residual.*
  *M6 disposition: **DOCUMENTED, not closed.** `claim-truth-limit` mechanically
  requires `validate.md`, `hal-coordinator`, `hal-integrator`, `hal-reviewer`,
  `hal-tester` and `docs/skill-template.md` to disclose that a claimant may have
  fabricated execution evidence and that no external attester exists - so the
  **disclosure** is enforced. The **detector** is not built and M6 did not
  attempt one: a check that could detect a false claim about work never done is
  exactly what this item asks for, and disclosing its absence is not the same as
  supplying it. Still open. Owner: post-M7.*
- [x] **E8** `AGENTS.md`'s dual-purpose framing is unsafe. `:15-19`
  requires `embassy-mcxa/` paths to resolve or work stops; in this
  checkout none resolve, so literal compliance halts even toolkit
  maintenance. *(Closed by M6, and this milestone is its own live evidence: an
  earlier M6 attempt deadlocked because it dispatched an agent whose only
  write-allow glob is `halucinator/docs/*/notes/ARCHITECTURE.md`, a path that
  does not exist in a toolkit checkout, so the agent could write nothing and
  looped. **MECHANICALLY ENFORCED:** `checkout-context-guard` requires all eight
  agents and `AGENTS.md` to carry the exact no-action sentence, all three
  classifications, the rule that TOOLKIT wins even when Embassy markers also
  appear, and the prohibition on retry and subdispatch; `AGENTS.md` must name
  the four conservative markers and the README sentence it probes for, and
  `README.md` must note that `docs/opencode.json` is inert product material.
  **DOCUMENTED ONLY:** no classification is executed here. An agent that ignores
  the guard is invisible to the check, which is why the guard text itself says
  the classification is conservative evidence, not proof of identity.)*
- [x] **E15** The M6 checkout guard was scoped to every reader of `AGENTS.md`
  rather than to the HAL workflow, reproducing E8's defect in mirror image and
  making it stronger: E8's prerequisite *implied* that literal compliance halts
  toolkit maintenance, while the unscoped guard *mandated* the halt. Demonstrated,
  not theoretical: a generic `reviewer` agent dispatched to run the M6 compliance
  review refused twice with the guard's own no-action sentence, and was right to,
  because "before anything else, classify" outranks a dispatch instruction - even
  one explicitly authorizing it as the non-HAL agent the remedy names. The guard
  opened with a bare imperative and named no subject. *(Closed.
  **LEXICALLY ENFORCED - guard TEXT, not guard BEHAVIOR:**
  `checkout-context-guard` requires two distinct
  sentences in `AGENTS.md` and in each of the eight `hal-*` guard blocks - one
  tying the `hal-*` HAL-workflow family to the classification obligation, and a
  separate one releasing a non-HAL maintenance agent - matched as sentence-level
  co-occurrence over open wording families rather than one literal, and it
  explicitly refuses to accept the operator-facing remedy sentence as the
  release. The `hal-*` refusal is unchanged: terminal, no retry, no lock, no
  state publication, no write, no subdispatch.
  **HONOUR SYSTEM - the classification itself:** no classification is executed
  by any check. Nothing observes an agent classifying a checkout, refusing,
  returning without a retry, or declining to subdispatch; the eight files are
  read as strings. In particular the check cannot distinguish a correctly scoped
  exclusion from one worded so broadly that a `hal-*` agent reads itself out of
  the guard, so the corpus carries that weight in prose: the exclusion is
  settled by agent identity alone and never by an agent's own judgement of its
  task. A wording that let any agent self-certify its work as maintenance would
  satisfy the check and reintroduce E8. This is a review obligation.)*
- [x] **E9** The install commands overwrite a destination `AGENTS.md`
  (`README.md:66-82`) despite the prose saying "or merge" (`:59-64`).
  *(Closed by M6. **ENFORCED, PER BLOCK - not per destination:**
  `install-no-overwrite` rejects the "overwrite matching files" announcement,
  forbids `-Force` anywhere, and requires that a fenced block containing a copy
  also contain **at least one** absence guard - `[ ! -e ... ] || exit 1` for
  POSIX, `Test-Path -LiteralPath` ... `throw` for PowerShell.
  **HONOUR SYSTEM - guard-to-copy correspondence.** The check's own PASS line
  admits it: a block that guards its first destination and then copies three
  more unguarded **passes**. Establishing one-to-one guard-before-copy ordering
  needs a shell parser this harness does not have. The README's blocks do guard
  every destination today, and that is a fact about the current bytes, checked
  by a human, not a property the check maintains. A user who edits or ignores
  the commands is outside it either way. Carried as H17.)*
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
- [x] **E13** Fixture assertion strength is not uniform. M4 gave the fixture
  harness **opt-in exact-diagnostic assertion** — code plus file plus field,
  and no extra diagnostics — and uses it for the three new multi-driver
  fixtures 30, 31 and 32. Fixtures 01–29 keep the legacy contains-code
  behavior, because `EXPECTATIONS.md` documents cases where one malformed
  artifact unavoidably raises several codes. A fixture that merely contains
  its declared code can pass while also emitting an unrelated regression, so
  the older fixtures assert less than they appear to. Tightening them means
  auditing each multi-code case and recording the full expected set, which is
  a separate normalization pass rather than a side effect of any milestone's
  feature work. *Owner: M6.* *(Closed by M6.
  **MECHANICALLY ENFORCED:** the legacy contains-code mode is gone. Every
  invalid fixture root declares one
  `Expected diagnostic: <file>|<field>|<code>` line per expected diagnostic, and
  `fixtures` requires the sorted exact diagnostic **set** - not a multiset,
  because `Reporter.lines` deduplicates - to equal the declaration, so a missing
  or an extra diagnostic now fails. All 37 invalid roots are covered.
  **DOCUMENTED ONLY:** exactness is not adequacy. That the declared set is the
  *right* set remains a review judgement.)*
- [~] **E14** Transitive dependency invalidation is deferred to post-M7; closing it requires typed direct handoff edges, cycle/missing-node validation and reverse-reachability propagation across distinct driver and test nodes. Owner: post-M7.

- [x] **E15b/E16** Two M6 review findings, recorded together because they share
  a cause: M6 shipped safety machinery without checking that the corpus using it
  was consistent with it.
  **(a) Invented hardware facts in the shipped corpus.** The milestone whose
  purpose is stopping invented hardware facts contained them: `acme` /
  `acme-ax100` stood in `halucinator/docs/<target-id>/` and
  `halucinator/pac/<vendor>/`
  positions across seven skills, `AX100` / `AX100RM` stood beside manual,
  section, table and revision markers in two files, and `write-driver` carried a
  retired schema-1 `driver.test_hardware_facts` **table array** - the shape
  schema 2 replaces with a list of verified assertion IDs - whose invented
  manual and section number were the most citation-shaped text in the toolkit.
  A reader copying that worked example would have learned both an invented fact
  and a citation shape the validator no longer accepts.
  **(b) The interlock was never invoked.** `hardware-execution.md` performed
  attach, load, run and teardown with no `acquire-board`, `before-board-op`,
  `begin-board-operation`, `complete-board-operation` or `release-board`, and no
  recovery command anywhere in either tester-emitted skill tree. The entire
  F3/F4/F5 safety claim rested on a helper that the only procedure needing it
  walked straight past. *(Closed.
  **ENFORCED, and only this narrowly.** Two halves of
  `no-invented-hardware-in-corpus` are genuinely decidable from the corpus's own
  rules and need no hardware knowledge: exactly one target/vendor segment is
  permitted under `halucinator/docs|pac`, so any other segment is invented by
  construction; and the retired schema-1 citation leaves are a pure schema fact.
  Those two are solid. `hardware-procedure-uses-interlock` decides that the
  documented command sequence is present and correctly ordered.
  **HONOUR SYSTEM - the rest, which is most of it.**
  *Invented hardware:* there is no lexical test separating a real part number
  from an invented one - `MCXA256` exists, `AX100` does not, and they are the
  same shape - so the citation-subject half is only as good as a small
  **hand-maintained allowlist** of citable families, and an invented part
  resembling one passes. Worse for the item's actual purpose: a fabricated
  register offset, bit position, reset value or field encoding in prose matches
  **nothing here at all**. The check finds invented *targets* and retired
  *leaves*; it does not find invented *facts*, which is what Rule 1 is about.
  *Interlock usage:* the check reads procedure text. Nothing proves an agent
  ran `acquire-board`, and a procedure naming every command in the right order
  while describing the wrong actions between them passes - its own PASS line
  says exactly that. The three safety properties the wiring states - holder
  death is not operation death, device state declared unknown before
  reconnecting, and the safe-state ordering before human contact with the
  fixture - are **prose an agent may ignore**. Carried as H17.)*


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
  fencing and cross-clone crash markers are still required. M4 makes this
  worse, not better: `write-driver` is dispatched once per peripheral, so
  N concurrent drivers now contend for the same shared clock files.
  Per-driver candidate path locking reduces cooperative overlap but converts
  what was a crash window into an **active writer race** on
  `embassy-*/src/clocks/**`. Still open. Owner: M6.*
  *M6 disposition: **PARTIALLY ENFORCED, still open.** `.opencode/schema/runtime.py`
  is a real worktree-local, single-operator interlock with exact `path:` and
  `board:` resources, and `runtime-protocol-tests` drives it through eight
  injected faults. What M6 refused to build is the part this item actually
  needs: a hardware-operation broker (F15), cross-clone and concurrent-operator
  exclusion (F16), a durable cross-clone marker (F17) and a durable integration
  journal (F18). "A half-built broker is worse than none." The corpus now says
  `runtime.py` arbitrates cooperating worktree-local callers, and that direct
  writers and other clones are outside it. Owner: post-M7.*

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
  *M6 disposition: **PARTIALLY ENFORCED, still open.** `.opencode/schema/runtime.py`
  is a real worktree-local, single-operator interlock with exact `path:` and
  `board:` resources, and `runtime-protocol-tests` drives it through eight
  injected faults. What M6 refused to build is the part this item actually
  needs: a hardware-operation broker (F15), cross-clone and concurrent-operator
  exclusion (F16), a durable cross-clone marker (F17) and a durable integration
  journal (F18). "A half-built broker is worse than none." The corpus now says
  `runtime.py` arbitrates cooperating worktree-local callers, and that direct
  writers and other clones are outside it. Owner: post-M7.*

- [ ] **F3** No lease on the single physical board.
  `hardware-execution.md` is singular throughout; two concurrently
  dispatched testers would each hold genuine device authorization and
  interleave resets, loads and runs on the same MCU. The failure mode is
  physical, not a merge conflict. *Progress: `.opencode/schema/layout.md`
  reserves a `board:<board_id>` lease keyed by physical device rather than
  by stage, but M1 implements no reader, so no exclusion is enforced yet.
  Owner: M6.* *M6 disposition: **PARTIALLY ENFORCED, still open.** A reader now
  exists. `runtime.py` acquires, prechecks and releases a `board:<board_id>`
  resource with an unpredictable `lease_epoch` and a revalidated `check_token`,
  any post-create rescan conflict makes the new claimant remove only its own
  candidate and fail `BOARD_INTERLOCK_CONFLICT`, and `07-tests` must carry the
  matching `tests.board_interlock`. It is deliberately **not** called a lease:
  it is worktree-local and single-operator. Another clone or another operator
  has no visible `.run` lock at all, and the check-use window between
  `before-board-op` and the actual probe command cannot be closed without the
  broker. Carried as F15, F16 and F17. Owner: post-M7.*
  *M6 review correction: the paragraph above was written while **no procedure
  called the helper at all**. Until E16 the hardware-execution reference
  performed attach, load, run and teardown without naming a single interlock
  command, so "a reader now exists" described a reader nothing invoked. The
  wiring is now in place and asserted; the honest reading of this item is
  therefore unchanged - still open - but for the right reason.*
  *M6 recheck correction: "partially enforced" above overstated **operability**.
  What is mechanically enforced is narrow and real: the helper refuses a recovery
  attempt or a safe-state observation whose FileRef does not exist, never records
  `board_state="safe"` on absent evidence, and refuses to release against it.
  What is **documented only** is the operator-facing path - the procedure text,
  its ordering, and the three safety properties it states. Two defects found in
  this recheck bear directly on whether that path is walkable at all: a recovery
  deadlock, in which every recovery-scoped operation was refused across every
  advertised entry point while `recovery-pending`, and an evidence-closure hole
  in which an unpinned nested FileRef passed verification and release. Both are
  being repaired in the runtime helper. Until a recovery is demonstrated
  end-to-end, treat this path as specified, not as shown to work.*

- [ ] **F4** No interrupted-HIL recovery. If the host or agent dies
  mid-run, no record can confirm teardown, and no next-session procedure
  declares device state unknown
  (`hardware-execution.md:104-115`). *M6 disposition: **PARTIALLY ENFORCED,
  still open.** Recovery is now typed and tested: `recovery-pending` needs no
  produced evidence (breaking the circularity), only a latest `verified`
  attempt with a matching `SafeStateObservation` reaches `recovery-verified`,
  attempts are append-only and cannot be reordered or replaced, and the helper
  refuses release before that. Holder death is explicitly not operation death -
  state is declared unknown before any reconnect, and attaching a debugger is
  itself a target-affecting operation. What remains open is exactly what a
  record cannot establish: whether the operator's confirmation of child
  termination or physical isolation is true, and whether a *different clone*
  died with the board active, which a fresh clone still cannot know. Carried as
  F17. Owner: post-M7.* *M6 review correction: this disposition credited typed
  recovery transitions while the tester-facing procedure named no recovery
  command, so an operator following the documented steps had no route into
  recovery at all. E16 wires `begin-board-recovery`, `append-recovery-attempt`
  and `verify-board-recovery` into both tester-emitted skill trees and states
  that device state is declared unknown **before** reconnecting. The record
  layer was real; the path to it was not.*
  *M6 recheck correction: "partially enforced" above overstated **operability**.
  What is mechanically enforced is narrow and real: the helper refuses a recovery
  attempt or a safe-state observation whose FileRef does not exist, never records
  `board_state="safe"` on absent evidence, and refuses to release against it.
  What is **documented only** is the operator-facing path - the procedure text,
  its ordering, and the three safety properties it states. Two defects found in
  this recheck bear directly on whether that path is walkable at all: a recovery
  deadlock, in which every recovery-scoped operation was refused across every
  advertised entry point while `recovery-pending`, and an evidence-closure hole
  in which an unpinned nested FileRef passed verification and release. Both are
  being repaired in the runtime helper. Until a recovery is demonstrated
  end-to-end, treat this path as specified, not as shown to work.*

- [ ] **F5** No universal between-test safe state — outputs
  high-impedance, DMA/interrupts quiesced, loads de-energized, reset
  asserted before fixture changes. *M6 disposition: **PARTIALLY ENFORCED, still
  open.** `SafeStateObservation` is a typed standalone record requiring exactly
  six hazard observations - outputs, DMA, interrupts, external loads,
  reset/halt, probe - each with a disposition, an observation method and
  evidence, an `operator_confirmation` FileRef wherever observation depends on
  physical action, and an `outstanding_human_actions` list that prevents a safe
  classification when nonempty, and the ordered sequence before human contact
  with the fixture is written down. `SafeStateProcedureRef` binds the record to
  one board identity and to assertion IDs in a ready `02-facts` handoff.
  **That binding is structural, and it is weaker than it sounds.** What is
  enforced is that the named IDs *resolve* in a handoff that *passed* the
  citation gate. The gate proves an excerpt occurs at a cited location - it does
  not prove the excerpt supports the claim, and a procedure can therefore cite
  verified assertions that do not establish what the procedure needs them to.
  "Founded on verified facts" means "references IDs that resolve", nothing more.
  **Whether the procedure is physically sufficient, and whether the
  observations are true, is reviewed, not proved.** A complete set of FileRefs
  is not electrical safety, and no such record has yet been produced by a real
  run on real hardware. Owner: post-M7 for the physical
  residual.* *M6 review correction: the ordered safe-state sequence existed only
  in the schema prose, not in the procedure a tester actually follows; the
  hardware-execution reference still said "follow the documented safe teardown"
  and nothing more. E16 writes the ordered sequence - quiesce, establish cited
  non-driving and reset/halt state, de-energize external loads, collect all six
  hazard observations, classify safe, authorize the fixture change - into that
  procedure, keeping **never join driven outputs** and **configure input before
  output** additive. Still **DOCUMENTED** at the procedure layer: prose an agent
  may ignore is not a mechanism.*
  *M6 recheck correction: "partially enforced" above overstated **operability**.
  What is mechanically enforced is narrow and real: the helper refuses a recovery
  attempt or a safe-state observation whose FileRef does not exist, never records
  `board_state="safe"` on absent evidence, and refuses to release against it.
  What is **documented only** is the operator-facing path - the procedure text,
  its ordering, and the three safety properties it states. Two defects found in
  this recheck bear directly on whether that path is walkable at all: a recovery
  deadlock, in which every recovery-scoped operation was refused across every
  advertised entry point while `recovery-pending`, and an evidence-closure hole
  in which an unpinned nested FileRef passed verification and release. Both are
  being repaired in the runtime helper. Until a recovery is demonstrated
  end-to-end, treat this path as specified, not as shown to work.*

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
  required. M4 makes this worse for the same reason as F1: one `write-driver`
  dispatch per peripheral means N concurrent drivers, and per-driver candidate
  path locking turns the shared clock-file crash window into an active writer
  race rather than removing it. Still open. Owner: M6.*
  *M6 disposition: **PARTIALLY ENFORCED, still open.** `.opencode/schema/runtime.py`
  is a real worktree-local, single-operator interlock with exact `path:` and
  `board:` resources, and `runtime-protocol-tests` drives it through eight
  injected faults. What M6 refused to build is the part this item actually
  needs: a hardware-operation broker (F15), cross-clone and concurrent-operator
  exclusion (F16), a durable cross-clone marker (F17) and a durable integration
  journal (F18). "A half-built broker is worse than none." The corpus now says
  `runtime.py` arbitrates cooperating worktree-local callers, and that direct
  writers and other clones are outside it. Owner: post-M7.*

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
  `.opencode/schema/handoff-common.md`. *Owner: M6.* *M6 correction: the
  "reserve identities only" sentence above is **obsolete**. The `schema = 2`
  transition landed the structural fields it asks for - `operation_phase`,
  `operation_attempt`, `operation_id`, `last_operation`, `child_session`,
  `safe_state`, `recovery_attempts` and `override_record` on the lock, plus the
  typed `SafeStateObservation` with its six hazards and the append-only recovery
  attempt records. **MECHANICALLY ENFORCED:** the structural portion - required
  and exclusive fields, phase/state agreement, and lock-era identity equality
  across lock, safe-state record and run. **The two gaps that remain are
  precise, and neither is structural.** First, no independent physical
  re-derivation or attestation. The helper does parse these records - it opens
  every referenced FileRef and refuses to transition or release against evidence
  it cannot read - but parsing a record is not observing a device. Nothing
  re-derives an observation from the hardware, so a complete, internally
  consistent, fully parsed record can still be false, and no external attester
  exists to say otherwise. Second, no physical authority: `check_token` is not a
  fencing token, the helper is worktree-local and single-operator, and it has no
  standing over another clone, another operator, or a probe command issued
  outside it. Carried as F15, F16 and F17. Owner: post-M7.*
- [~] **F13** No durable integration journal. `hal-integrator` is now the
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
  *M6 disposition: **deliberately deferred, documented only.** M6 added no
  journal fields and no journal diagnostics. The scaffold record now says that
  canonical copy is serialized by the worktree interlock and an immediate
  baseline check, and that the crash phase remains unknown without this item.
  Carried forward as F18. Owner: post-M7.*
- [~] **F14** No durable coordinator dispatch ledger. `hal-coordinator`
  writes its intent, owner, inputs, expected output and exit criteria to
  `halucinator/docs/<target-id>/notes/ROADMAP.md` before dispatching, but
  `state.stages[]` requires a *returned* handoff FileRef, so
  dispatched-but-never-returned work has no typed representation at all. A
  fresh session sees a stage lock with no handoff and can only guess. The
  ROADMAP is prose and is not a transaction ledger. Recording in-progress
  dispatch typedly needs `schema = 2` and belongs with F10/F11's recovery
  work. M4 mitigates identity but increases frequency: the ROADMAP now
  enumerates every expected `write-driver:<name>` dispatch, so a returned
  handoff can be tied to the dispatch that asked for it — but more
  concurrent named drivers make a missing durable dispatch record **more
  frequent**, not less. Still open. *Owner: M6, with F10/F11.*
  *M6 disposition: **deliberately deferred, documented only.** ROADMAP and locks
  remain procedural evidence; no typed pre-dispatch publication exists. Carried
  forward as F19. Owner: post-M7.*
- [ ] **F12** `state.toml` compare-and-swap protects cooperating writers
  only. An uncooperative writer can overwrite it with valid TOML and a
  plausible generation, and the validator cannot reconstruct the prior
  value. Recorded in `.opencode/schema/validate.md` limits. *Unchanged by
  M4. Owner: M6.*
- [~] **F15** A hardware-operation broker process is deferred to post-M7; closing the check-use race requires one long-lived broker to own the probe/runner handle and execute every target-affecting operation after epoch validation. Owner: post-M7.
- [~] **F16** Cross-clone and concurrent-operator board exclusion is deferred to post-M7; closing it requires an external shared lease authority with atomic acquisition, renewable ownership and fencing honored by the hardware broker. Owner: post-M7.
- [~] **F17** A durable cross-clone board-active marker is deferred to post-M7; closing it requires a shared durable authority updated before hardware operations and recoverable independently of one worktree. A fresh clone currently cannot know that a previous run died with the board active. Owner: post-M7.
- [~] **F18** The durable canonical-integration journal is deferred to post-M7; closing it requires committed baseline/candidate/result manifests, durable phase transitions and recovery tied to an owner fencing authority. Owner: post-M7.
- [~] **F19** The durable coordinator dispatch ledger is deferred to post-M7; closing it requires typed pre-dispatch publication and CAS-checked dispatched/returned/abandoned transitions bound to locks and handoffs. Owner: post-M7.
- [~] **F20** Windows durability is a **weaker guarantee** than the POSIX
  directory-`fsync` barrier, and M6 declines to define the weaker protocol it
  would need. `os.fsync` on a directory handle fails unconditionally on win32,
  so `.opencode/schema/runtime.py` relies on exclusive-create, a file `fsync`,
  and a same-volume `os.replace`, and documents NTFS metadata ordering rather
  than an explicit barrier. Where the directory-flush probe reports the
  capability unavailable the helper blocks target-affecting operations instead
  of claiming persistence, which is fail-closed but not equivalent. Closing it
  requires defining that explicitly scoped weaker protocol. Escalated by M6's
  schema coder. Owner: post-M7.


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
  blocked, never silently accepted. M4 closed the residual capability gap
  too: `write-driver` covers every peripheral — see H1 and D13.)*
- [x] **G5** Terminology drift: stage / phase / step / milestone used
  interchangeably; target / chip / part / exact-MCU for overlapping
  identities; `type-state` (`README.md:146`) vs `Typestate`
  (`AGENTS.md:93-98`); British `behaviour` / `normalise` /
  `initialisation` in agents vs American in skills. *(Closed by the canon
  in `.opencode/schema/terminology.md`; mechanical enforcement covers only
  the five unambiguous tokens `type-state`, `Typestate`, `behaviour`,
  `normalise`, and `initialisation` - each quoted here inside backticks,
  because `terminology` blanks inline code spans, so a citation of a rejected
  token is representable and a bare use is not; migration of legacy occurrences is
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

- [x] **H1** General peripheral-driver generation
  (`README.md`'s pipeline) — *(Closed by M4: `write-driver` is the generic
  per-peripheral procedure. It applies the universal driver obligations to
  every peripheral and selects a GPIO, Embassy-time-service or bus profile,
  so a bus shape is never presented as universal. README now says so
  directly under the pipeline's peripheral-drivers row. The claim is now
  true of the toolkit; A21 and A22 record that the peripheral inventory and
  the profile discriminator are still untyped.)*
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
- [x] **H5** RAM-first loading (`hardware-execution.md:50-83`) is policy
  with no linker-generation procedure or ELF inspection command set.
  Blocked on C1. *(Closed by M5 in
  `.opencode/skills/integrate-runtime-linker/`: RAM-first candidate linker
  and runtime configuration plus ELF load/run-address inspection are now a
  procedure rather than a policy sentence. C1 named the owner; this names
  the steps.)*
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
  scans dependency URLs and revisions. *M6 disposition: **PARTIALLY ENFORCED,
  still open.** `reference-url-pins` now rejects any evidentiary URL across the
  governed Markdown naming `main`, `master` or `HEAD` without an exact 40-hex
  commit; the one remaining moving reference, the MCXA manifest link inside an
  otherwise SHA-pinned table in
  `generate-pac/references/generation-and-checks.md`, is pinned to the exact
  inspected commit `f8506dc5f0022ccb62c75bd2707da913c6979375`, whose manifest
  was read and does carry the `nxp-pac` revision the surrounding prose claims.
  Detection of hand-edited generated output remains procedural: the generation
  tooling writes a path/hash manifest for candidate and independent replay and
  the reviewer compares them. Pin immutability is enforced; pin *legitimacy* and
  fork legitimacy are still review. Owner: post-M7.*
- [~] **H8** Skill acceptance testing. The SVD and PAC references list
  acceptance scenarios (`preparation-and-checks.md:262-287`,
  `generation-and-checks.md:372-404`) with no fixtures, runner or
  recorded results. *Deferred.*
- [ ] **H9** The `.gitattributes` byte policy specified in
  `.opencode/schema/validate.md` is not installed anywhere. Raw-byte
  SHA-256 hashes are stable only where `core.autocrlf=false`; a clone
  configured otherwise breaks every hash. *Owner: M3.*
- [x] **H10** The 944-file fixture tree was generated by a script that
  lives outside the repository. The fixtures are committed and
  self-sufficient, but nothing in-tree can regenerate them and no owner is
  named. *Owner: M3 or M7.* *(Closed by M6.
  **MECHANICALLY ENFORCED:** `tools/generate_schema_fixtures.py` and its
  declarative input `tools/schema-fixtures.toml` are committed, stdlib-only and
  deterministic; `--write` regenerates both valid roots and every invalid root
  including referenced evidence, `.gitattributes` and README declarations, and
  `--check` regenerates into a temporary directory and byte-compares. The
  `fixture-regeneration` self-check runs `--check` and requires exit 0 with no
  output, so no committed fixture byte can be undeclared or divergent. The
  fixture count is derived from the TOML, not a duplicated literal.
  **DOCUMENTED ONLY:** this proves REGENERATION, not that the declared
  mutations are the right ones. That judgement stays with review.)*
- [ ] **H11** Validator invocation is an honour system. The retrofitted
  skills wire the validator at every required point and self-check proves
  those instructions are present, but nothing proves an agent ran them and
  the validator cannot attest to its own prior execution. This limitation is
  recorded in `.opencode/schema/selfcheck.md` and `docs/skill-template.md`;
  no M3 text describes the wiring as runtime enforcement. *Unchanged by M4:
  `write-driver` and the validation profiles wire the validator at the same
  required points and disclose the same limit, and retiring the allowlist
  changed coverage, not enforcement. Owner: M6.*
  *M6 disposition: **DOCUMENTED, not closed, and structurally unclosable here.**
  `skill-validator-wiring` now binds every publication step and requires each of
  the 13 skills to state the honor-system limit and that `validate.py` cannot
  attest to an earlier invocation, so the **disclosure** and the **wiring** are
  enforced. Invocation itself is not, and no text in this repository may
  describe it as enforcement. A validator gate is an honour system; instructions
  being present is not proof an agent ran them. Closing this needs an external
  attester, which M6 explicitly did not build. Permanent residual until then.
  Owner: post-M7.*
- [x] **H12** Validator wiring does not bind every publication.
  `skill-validator-wiring` derives every handoff-publication step in a skill
  — it is not hard-coded — but it requires a validator invocation only
  before and at the **first** publication, plus the `--kind all` gate at or
  after the last. A middle or later publication in a multi-publication skill
  can therefore lose its immediate validation while the check stays green.
  Binding every publishing step is not a check-only fix: it needs 7 of the
  13 skills to name the command stem at their final gate rather than only
  `--kind all`, which is a change to skill text. *Owner: M6.* *(Closed by M6.
  **MECHANICALLY ENFORCED:** `skill-validator-wiring` now derives every
  handoff-publishing step and requires a `validate.py` invocation at **each** of
  them, in addition to one before the first and the `--kind all` gate at or
  after the last; the seven skills that named only `--kind all` at their final
  gate were changed to name the command. **DOCUMENTED ONLY:** a publishing step
  whose bold title does not name a publish verb, or that does not bind that verb
  to a "handoff", is not a subject of the derivation at all - and the check
  proves the instruction is present, never that an agent executed it, which is
  H11.)*
- [ ] **H13** Subject-derivation guard has known AST blind spots.
  `skill-subject-derivation` was added by M5 after two milestones in a row
  shipped a check whose subject set was hard-coded and silently incomplete
  (M4's review-gated tuple, M5's verb-prefix scanner). It catches the eight
  literal forms it tests, including the one-element collection that reads as
  general and is not. It cannot see filtering hidden in a called helper,
  component-wise or aliased names, `.keys()` membership, or
  `startswith`/`endswith`/regex predicates. Its own PASS text describes it
  correctly as a regression guard over those forms, not as proof that every
  check derives its subjects — the honest framing is the point, and it does
  not make the blind spots smaller. *Owner: M6.*
- [ ] **H14** The composite-evidence marker rule is a bounded structural
  tripwire. Three rounds of lexical patching were each defeated by a
  reviewer-constructed bypass, so `skill-platform-slices` was rebuilt
  structurally: a non-final slice may not state the marker anywhere in
  `## Procedure` or `## Validation`, and where it appears elsewhere it must
  name the consolidator or the consolidating role. All four known bypasses
  are now caught. **Three residuals are known and accepted.** Attribution
  outside the operative sections is co-occurrence rather than role
  assignment, so a sentence that names the consolidator while still claiming
  the work passes. Detection reads one literal phrase, so any synonym is
  invisible. And the rule is placement-based, not semantic. Exclusivity
  itself is carried by the unreachable-`ready` assertion, the review gate,
  the consolidator-count assertion and human review — the tripwire raises
  the cost of the cheap mechanical violation and nothing more. Same posture,
  and the same limits, as the `DRIVER_API_LEAK` and
  `validation-guidance-isolation` tripwires. *Owner: M6 if it is to be
  strengthened.*
- [ ] **H15** Self-check mutation coverage is incomplete and non-durable.
  M5 ran a mutation proof that bound 14 of 36 checks to the new skills and
  confirmed that all five new review-gated skills trip
  `SKILL_VERDICT_SENTENCE_MISSING` when their accepting sentence is removed.
  Two problems. The harness lives **outside the tree**, so the proof is not
  reproducible from a clone — the same defect as H10's fixture generator.
  And nothing durable records which checks have been exercised against real
  content versus merely shown to fail closed: `debug-lineage` and
  `skill-note-paths` are in the second category, never bound to M5 content.
  A check that has only been shown to fail closed has been shown to reject
  garbage, not to accept the corpus for the right reason. Add an in-tree
  mutation matrix, or a committed record of exercised versus unexercised
  checks. *Owner: M6, with H10.*
- [~] **H16** Two self-check subject lists remain hand-maintained, and whether
  they should exist at all is an open specification question. The M6 recheck
  eliminated the third one: `mcxa-example-boundary` no longer reads a file list,
  it derives its subjects corpus-wide, which is why it began catching this very
  backlog file. `LIFECYCLE_ENUMERATING_FILES` and `CITATION_FILES` were not
  eliminated; they were **closed**, which is a smaller but real improvement. A
  file that carries the matching marker and appears in neither its declared
  subject list nor its declared out-of-scope list now fails loudly
  (`LIFECYCLE_SUBJECT_UNDECLARED`, `CITATION_SUBJECT_UNDECLARED`) instead of
  being silently unasserted, so an omission announces itself rather than
  quietly narrowing coverage. What is still hand-maintained is the *membership
  decision*: someone must place each new marker-matching file in one list or the
  other, and nothing checks that the placement is right. Closing this properly
  is not a refactor - it is deciding whether the minimum lifecycle-contract
  obligation and the v2 CitationRef field obligation bind **every** file that
  discusses them, which would immediately put roughly seven further files in
  scope and change what those files must say. The owner declined that for M6 as
  scope creep rather than repair, which is the right call for a safety
  milestone, and it is recorded here so the decision is not lost. Owner:
  post-M7.

- [ ] **H17** Seven M6 obligations are enforced only as **corpus text**, and
  narrowing the wording is all M6 could honestly do about it. The M6 compliance
  review found them presented as "mechanically enforced" when what a program
  decides is the presence, absence or ordering of literal strings in named
  Markdown files. They are now relabelled - `E3` lifecycle universality, `E4`
  error-clearing semantics, `E5` target-first reading order, `E8` agent checkout
  behavior, the invented-hardware rule outside its two decidable halves, the
  interlock-usage rule, and `E9` install guarding, which is per code **block**
  and not per destination. Each is real as far as it goes and none of them
  reaches the property the item was raised about: a corpus can satisfy every
  string test while a driver clears the wrong flags, an agent reads another
  vendor's implementation first, a `hal-*` agent loops in a toolkit checkout, a
  fabricated register offset ships, nobody calls `acquire-board`, or three of
  four destinations are overwritten. Closing this needs an observer of agent
  and driver BEHAVIOR - a runtime that records what an agent read and in what
  order, a compiled driver exercised against cited register semantics, or an
  external attester - none of which exists and none of which is a wording fix.
  Recorded so the gap has an ID rather than only a softer sentence. Owner:
  post-M7.


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
