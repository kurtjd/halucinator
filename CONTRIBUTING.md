# Contributing to halucinator

This guide is for contributors changing the halucinator toolkit itself. The
repository contains OpenCode agent definitions, executable skill procedures,
typed handoff contracts, and repository-only verification tools. It does not
contain a HAL implementation, and none of its checks demonstrate operation in
an Embassy checkout or on hardware.

Start with the [README](README.md) for the toolkit overview, [AGENTS.md](AGENTS.md)
for pipeline policy and hard rules, and the [glossary](GLOSSARY.md) for shared
terms. Use this guide when adding or changing a skill, an agent, a schema fixture,
or a self-check.

## Repository orientation

The moving parts are deliberately coupled:

| Path | Purpose |
|---|---|
| `.opencode/agents/*.md` | The eight OpenCode agent definitions, their permissions, ownership declarations, dispatch boundaries, and emitted handoff kinds. |
| `.opencode/skills/*/SKILL.md` | The thirteen executable stage procedures. |
| [`docs/skill-template.md`](docs/skill-template.md) | The authoritative skill structure and acceptance conditions. Link to it; do not copy it into another document. |
| [`.opencode/ownership.toml`](.opencode/ownership.toml) | The registry of 46 file classes and their single owners, plus the sole commit owner. |
| [`.opencode/schema/`](.opencode/schema/README.md) | The typed handoff documentation, validator, runtime helper, tests, and generated fixtures. |
| [`.opencode/schema/selfcheck.md`](.opencode/schema/selfcheck.md) | The documentation-parity contract for every check invoked by the self-check harness. |
| [`tools/selfcheck.py`](tools/selfcheck.py) | The repository-only corpus harness. Its PASS text states both each assertion and its limit. |
| [`tools/schema-fixtures.toml`](tools/schema-fixtures.toml) | The declarative source for the schema fixture corpus. |
| [`tools/generate_schema_fixtures.py`](tools/generate_schema_fixtures.py) | The deterministic fixture generator and byte-for-byte verifier. |

Agent frontmatter and contract fences describe who may act. Skill frontmatter
routes work; the skill body describes how to perform it. The Python validator
defines the accepted handoff structure. The ownership registry defines who may
write each file class. A contribution that changes one of these contracts often
has to update the others in the same change.

## Run the verification loop

Run these commands from the repository root with Python 3.11 or newer:

```powershell
python tools/selfcheck.py
python tools/generate_schema_fixtures.py --root . --check
python -m unittest discover -s .opencode/schema -p "test_*.py"
```

The commands answer different questions:

1. `python tools/selfcheck.py` checks corpus invariants across agents, skills,
   ownership, schema documentation, links, terminology, fixtures, and runtime
   interlocks. A green run is a necessary structural and procedural condition.
   It does not prove that an agent followed a procedure, that evidence is true,
   that a review was sound, or that the toolkit works in an Embassy checkout or
   on hardware. Several checks are lexical, use hand-maintained mappings, or
   derive coverage from test names and docstrings; read each PASS line before
   relying on it.
2. `python tools/generate_schema_fixtures.py --root . --check` regenerates the
   declared fixture roots in a temporary directory and compares their path sets
   and bytes with the working tree and Git's committed set. Success proves
   deterministic regeneration from `tools/schema-fixtures.toml`; it does not
   prove that a declared mutation is semantically correct. Check mode does not
   rewrite fixtures.
3. `python -m unittest discover -s .opencode/schema -p "test_*.py"` discovers
   the schema test modules and runs the citation and runtime suites. These tests
   exercise production helpers, including subprocess boundaries and fault
   injection. A passing suite does not close the documented broker,
   cross-clone, physical-truth, or test-intent limits. Read
   [`test_citation.py`](.opencode/schema/test_citation.py) and
   [`test_runtime.py`](.opencode/schema/test_runtime.py) when changing the
   covered behavior.

The self-check also invokes fixture regeneration and both schema suites, but run
all three commands directly. Direct runs make failures attributable and confirm
that the commands documented here still work.

## How to add a skill

Use the [canonical skill template](docs/skill-template.md) as a specification,
not as optional style guidance.

1. Create exactly `.opencode/skills/<name>/SKILL.md`. Add bundled references
   only when the procedure needs them.
2. Add the skill to the canonical skill mapping used by `tools/selfcheck.py`.
   Discovery and the mapping must agree in both directions.
3. Derive the emitted and consumed leaves and canonical check IDs from
   `validate.py`; do not summarize or abbreviate a leaf set.
4. Match every `writes` and `supplies-delta` declaration to the ownership
   registry. Use `supplies-delta` when one agent authors content that another
   owner materializes.
5. Write the procedure and worked handoff example to the current schema, then
   run the full verification loop.

Use the failing check name to locate the obligation:

| Check | What the contributor must do |
|---|---|
| `frontmatter` | Provide only the permitted skill keys; make `name` equal the directory and `compatibility` equal `opencode`. There is no separate `skill-frontmatter` check: skill frontmatter is covered here. |
| `skill-trigger-frontmatter` | Begin the normalized description with `Use when`, give an observable dispatch trigger, include search terms, and state `Wrong for` adjacent work. |
| `skill-contracts` | Put one raw `halucinator-skill-contract` fence immediately after the H1 and satisfy its required, repeatable, sorted, and no-whitespace grammar. |
| `skill-structure` | Supply the ten exact nonempty H2 sections in order, an assertable numbered procedure and validation table, three exclusive exit predicates, and a schema-current TOML handoff example. |
| `skill-discovery-closure` | Give every immediate skill directory exactly one regular `SKILL.md` and add a matching canonical mapping; neither side may contain an unpaired entry. |
| `skill-emissions` | Make `emits` leaves and `checks` exactly equal the registry derived from `validate.py`, not a selected subset. |
| `skill-consumption` | Declare exactly the canonical predecessor leaves and keep any hand-maintained exclusion list intentional and current. |
| `skill-ownership` | Declare only writes owned by that agent; for cross-owner semantic content, declare a delta, name the registry owner, and route materialization through the coordinator. |
| `skill-references` | Ensure every skill name cited by agent prose resolves to a discovered, canonical skill. This check does not inspect arbitrary prose references outside that relation. |
| `skill-note-paths` | If the emitted kind has a deterministic first-note path, state that exact path without a soft alternative in the same paragraph; applicability comes from the emitted kind. |
| `skill-status-vocabulary` | Use only `ready`, `partial`, and `blocked` for stage exits, and omit optional TOML keys instead of writing a legacy null sentinel. |
| `skill-validator-wiring` | Put the validator command at every derived handoff-publication point, include a final `--kind all` gate, and state that this wiring is an honor system. The lexical check proves instructions exist, not execution. |
| `skill-verdict` | If the contract declares `independent-review`, state the exact accepting sentence from the template and use only the typed verdict tokens. |
| `skill-subject-derivation` | When extending the harness for the skill, discover subjects from `skill_paths(root)` rather than selecting literal skill names; see [Adding a check](#how-to-add-a-check). |
| `skill-platform-slices` | For a non-final platform slice, keep `ready` unreachable, publish `partial`, consume the required predecessor snapshot, and leave composite evidence and canonical placement to the final consolidator. This is a bounded wording and structure check, not observed exclusivity. |
| `links` | Make every relative Markdown link resolve to an existing regular file. The check strips queries and fragments but does not validate anchors. |
| `terminology` | Use the canonical American-English and lowercase forms in [the terminology canon](.opencode/schema/terminology.md); only five exact rejected tokens are mechanically blocked. |

Other checks may apply according to what the skill does. Tester-emitted skills,
debugging lineage, review emission, and hardware-operation procedures have
additional derived subject checks. Do not copy a neighboring skill and assume
that its applicability set is yours; inspect the complete self-check output.

## How to add or change an agent

An agent is not an isolated prompt. Change its frontmatter, raw agent contract,
ownership claims, prose permission statement, dispatch relation, and emitted
handoff declaration as one contract.

| Check | What the contributor must do |
|---|---|
| `topology` | Keep the declared topology coherent. The current contract is exactly eight agents with exactly one primary agent, so adding a ninth requires an intentional topology-contract change rather than dropping in a file. |
| `contracts` | Provide one parseable raw agent contract fence with valid ownership, emission, state-write, and dispatch declarations. |
| `permissions` | Make the prose permission statement exactly describe the frontmatter serialization. Permission key sets legitimately differ between agents. |
| `precedence` | Carry the required ownership-precedence sentence and the exact conflict ID set applicable to the agent. |
| `emissions` | Make every emitted kind and complete leaf set match the registry derived from `validate.py`. |
| `ownership` | Claim each of the 46 registry classes exactly once and only by its recorded owner; preserve valid overlap overrides and sorted registry structure. |
| `commit-owner` | Keep `hal-integrator` as the sole commit owner. Every other agent must deny `git commit*`. |
| `dispatch` | Keep the coordinator as the HAL-workflow dispatcher and make every specialist deny `task`; specialists return cross-owner work rather than dispatching peers. |
| `checkout-context-guard` | Carry the complete checkout guard in all eight agents, including all classifications, toolkit precedence, the exact refusal, and the no-retry, no-write, no-lock, no-state-publication, and no-subdispatch consequences. This check verifies corpus text, not runtime classification. |

The ownership registry is authoritative. Do not grant a permission merely
because adjacent prose says an agent needs it. First decide whether the file
class and its single owner must change, then update every affected declaration
and rerun the checks.

## How to change the handoff schema or fixtures

Read the [schema index](.opencode/schema/README.md), the common contract, the
relevant per-kind document, and `validate.py` before changing a handoff. The
validator is executable authority for accepted fields and canonical check sets;
the Markdown records the contract and its limits.

Never hand-edit a file under `.opencode/schema/fixtures/`. Change
`tools/schema-fixtures.toml`, regenerate with:

```powershell
python tools/generate_schema_fixtures.py --root . --write
```

Then inspect the generated diff and run the verification loop. Regeneration
recomputes FileRef hashes and expected fixture bytes. The check can prove that
the declaration reproduces the committed corpus; review must decide whether the
declaration and expected diagnostics are correct.

## How to add a check

1. Express the invariant as a check function in `tools/selfcheck.py`, include
   discriminating positive and near-miss cases where practical, and invoke it
   from `main()` with a stable check name.
2. Document that name in
   [`.opencode/schema/selfcheck.md`](.opencode/schema/selfcheck.md). The
   `selfcheck-doc-parity` check derives invoked names from the harness AST and
   fails if the documentation omits one. State what the check asserts, how its
   subjects are selected, and what it explicitly does not assert.
3. For every skill-scoped check, begin with discovered paths from
   `skill_paths(root)` and narrow by parsed properties such as emitted kind,
   emitter, stage, checks, or procedure role. Do not select applicability with
   a literal skill name, literal name collection, literal skill-directory path,
   or membership in a name-keyed mapping.
4. Run the complete verification loop and read the new PASS line as a skeptical
   contributor would.

`skill-subject-derivation` is a regression guard over eight AST forms, not a
semantic proof. It catches direct literal comparisons, collections, paths, and
mapping-key selection represented in those forms. Indirection through a helper,
aliases, component-wise construction, and some other predicates can evade it.
The requirement is therefore to derive the subject set, not merely to write code
whose syntax escapes the analyzer. A name-keyed expectation mapping is allowed
only after discovery and property-based applicability have already selected the
subject.

Do not weaken, delete, rename, or stop invoking an existing check merely to make
a contribution pass. If an invariant is obsolete, explain the contract change
and update its implementation, parity documentation, tests, and dependent
corpus together.

## House rules

### Commit messages

Use a short, plain imperative subject line. Recent history uses forms such as
“Generate”, “Add”, “Make”, “Correct”, and “Record”. Do not add Conventional
Commit prefixes such as `feat:` or `fix:`, and do not add attribution trailers.
The integrator is the only product agent allowed to commit; ordinary toolkit
contributors should still follow the repository's subject style.

### Terminology

Follow [`.opencode/schema/terminology.md`](.opencode/schema/terminology.md).
Prefer the precise terms `workflow stage`, `target identity`, `MCU part number`,
`Cargo chip feature`, and `Rust compilation target`. Use `typestate`, `behavior`,
`normalize`, and `initialization`. The terminology check blocks only its five
exact rejected spellings in governed prose; broader vocabulary consistency
still depends on review.

### Evidence and hardware claims

Apply [AGENTS.md](AGENTS.md)'s hard rules to toolkit prose as well as generated
workflows:

- Under `HAL-RULE-01`, never invent a hardware fact. A plausible register
  offset, field encoding, reset value, clock relation, or erratum is worse than
  an explicit unknown. Mechanical corpus scanning cannot identify every
  fabrication.
- Under `HAL-RULE-11`, never claim behavior that was not observed. State what
  command ran, what it established, what it did not establish, and what remains
  untested.

The toolkit has not been validated against a real Embassy checkout or real
hardware. Do not turn a green corpus check, fixture run, build, or schema test
into such a claim.

## What not to do

- Do not hand-edit a generated schema fixture.
- Do not weaken or delete a check to make a change land.
- Do not invent a hardware fact or citation.
- Do not report unobserved behavior as a result.
- Do not describe lexical corpus checks as runtime enforcement.
- Do not add a skill directory without its canonical mapping, or a mapping
  without its directory.
- Do not assign the same file class to two agents.
- Do not let an agent other than `hal-integrator` commit.
