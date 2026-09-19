# Toolkit self-check contract

`tools/selfcheck.py` is repository-only (not shipped), Python 3.11+ standard library only. It accepts an optional repository root, defaults to its parent root, returns zero only when all checks pass, and prints sorted lines `PASS <check>: <detail>` or `FAIL <path>:<location> [<CODE>] <actionable-message>`. No expected failure emits a traceback.

## What a green self-check does and does not prove

A green run proves **structural and procedural necessity**: that the declared agents, skills, ownership registry and schema documents are present, internally consistent, and mutually parseable, and that every skill procedure *contains* the instructions the pipeline depends on.

It does **not** prove runtime conduct. The self-check cannot show that an agent invoked `.opencode/schema/validate.py`, acquired or classified a lock, updated `state.toml` through the compare-and-swap sequence, or obtained an independent review before closing a gate. `validate.py` itself cannot attest to any earlier invocation of itself: it inspects artifacts, not history. Validator wiring in a skill is therefore an **honor system** backed by evidence discipline, not runtime enforcement. Read the self-check as a necessary condition on the corpus, never as a sufficient condition on a run.

## Agents and permissions

The toolkit defines exactly **eight agents**, of which exactly one - `hal-coordinator` - is `mode: primary`; the other seven are subagents. Permission mappings are **heterogeneous** across those eight: there is no fixed permission key set. The frontmatter parser therefore accepts any nonempty permission mapping and compares it generically against the agent's own serialization, rather than asserting a per-agent key list. Earlier revisions of this document described only the original six-agent topology and a tester-only `read,grep,glob,list` extension; that is obsolete and must not be reintroduced.

## Frontmatter, links, fixtures and terminology

1. **`frontmatter`.** Parse the YAML frontmatter delimited by the first two `---` lines without third-party YAML. The supported subset is mappings, indentation, block scalars, and scalar strings. Skills (`*/SKILL.md`) require `name`, `description`, and `compatibility`; `compatibility` is `opencode`. Their tolerated top-level allowlist is exactly `name`, `description`, `compatibility`, `license`, `allowed-tools`. A skill's `name` must equal its containing directory name. Agents require `description`, `mode`, and `permission`; `mode` is `primary|subagent`, and `permission` is a nonempty mapping whose subkeys legitimately vary between agents. Their tolerated top-level allowlist is exactly `description`, `mode`, `permission`, `model`, `temperature`, `tools`, `name`. Reject malformed delimiters, duplicate keys, tabs, unsupported YAML constructs, wrong scalar/container type, missing common fields, empty descriptions, name/directory mismatch, and top-level fields outside the applicable allowlist.
2. **`links`.** Inspect relative Markdown links in the governed Markdown set. Strip fragments/query for filesystem resolution, URL-decode paths, ignore `http:`, `https:`, `mailto:`, and pure `#fragment`; require the target to be an existing regular file. Anchor existence is out of scope. Skip `.opencode/node_modules/`, `.opencode/package.json`, `.opencode/package-lock.json`, fixture payload Markdown, and generated/cache directories.
3. **`fixtures`.** Run the validator as a subprocess using the current interpreter. The valid fixture must exit 0. Discover bounded `fixtures/invalid/[0-9][0-9]-*/`, require at least the mandated cases, run each with a 30-second timeout, require exit 1 and its README expected diagnostic code. Exit 2 or timeout fails.
4. **`terminology`.** Use the baseline/scoping rules in `terminology.md` and reject only the exact tokens `type-state`, `Typestate`, `behaviour`, `normalise`, and `initialisation` in newly governed prose. Stage/identity shorthand is review-only, not mechanically asserted. A missing baseline fails with `[TERMINOLOGY_BASELINE_MISSING]`. Root `TODO.md` is exempt only while Git reports it untracked, because it is coordinator working state under active revision; once committed it is governed automatically, without editing an exemption list. When Git is unavailable, use a closed, non-wideable fallback containing only `TODO.md`.

### Governed Markdown discovery

The governed set is root `*.md` plus `.opencode/**/*.md`, extended by **exactly one** additional path, `docs/skill-template.md`, appended only when it exists. That file is toolkit-authoring material outside `.opencode/`, so it is named explicitly rather than by widening the walk to all of `docs/`. Only `links` and `terminology` consume this set; no new check was introduced for it, and no link to a nonexistent skill is permitted.

## Topology, ownership and contract checks

5. **`topology`.** Exactly eight agents exist and exactly one is primary.
6. **`contracts`.** Every agent's raw contract fence parses and conforms.
7. **`ownership`.** Every registry class in `.opencode/ownership.toml` is well-formed and claimed exactly once.
8. **`emissions`.** Each agent's `emits` declaration matches the AST-derived handoff-kind registry.
9. **`permissions`.** Each agent's permission statement matches its frontmatter serialization.
10. **`config`.** Root `opencode.json` parses and its default agent resolves to a primary agent.
11. **`dispatch`.** The dispatch policy is stated in `README.md` and `hal-coordinator`, and every specialist denies `task`.
12. **`roadmap-path`.** The exact roadmap path is named wherever a roadmap is referenced.
13. **`verdict`.** Coordinator and reviewer state the exact accepting verdict sentence with typed tokens.
14. **`commit-owner`.** `hal-integrator` is the sole commit owner and every other agent denies `git commit*`.
15. **`precedence`.** Every agent states the precedence sentence and its exact conflict ID set.
16. **`candidate-convention`.** `halucinator/test-candidates/` is used consistently and the hidden scratch convention is absent.
17. **`workflow-markers`.** Integrator and tester carry their required workflow headings and diagnostic keys.
18. **`skill-references`.** Every skill referenced in agent prose resolves to an existing skill.

## Skill-contract checks

These thirteen checks encode the authoring template in `docs/skill-template.md`. Each is invoked directly from `main()` and scans **every applicable discovered skill**: M4 deleted the two-generation exemption file `tools/skill-template-allowlist.tsv`, its parser, and the registry indirection that threaded a shared exclusion set into them, so there is no exemption mechanism and no file whose absence could silently narrow coverage.

Eleven of the thirteen are universal — their applicability class is every discovered skill, with no predicate. Two are not, and their applicability rule is a property of the skill, never a list of names:

| Check | Applies to | Why not universal |
|---|---|---|
| `skill-note-paths` | `generate-svd` and `generate-pac` only, by the literal `SKILL_NOTE_PATHS` mapping | Only these two stages write a first handoff note at a single deterministic path (`<documentation>/notes/SVD.md`, `<documentation>/notes/PAC.md`). The other four stages have no such fixed first-note path, so there is no exact string to assert. |
| `skill-verdict` | every skill whose own contract fence declares the `independent-review` check — currently `generate-pac`, `scaffold-hal`, `write-driver`, `write-examples` | Only a skill gated on an accepting independent review has an accepting verdict to state. The set is **derived** from each skill's parsed `checks:` declaration, not listed: M4 shipped a hard-coded tuple that omitted `write-driver`, so the review gate it declares was never asserted and both accepting sentences could be deleted with the suite still green. Deriving the set closes that class of omission. A skill declaring the check is covered the moment it declares it; if the derived set is ever empty the check fails with `SKILL_VERDICT_NO_TARGETS` rather than passing vacuously. |

Where a check is not universal it is narrowed by an explicit, documented predicate — never by an exemption file, and never silently. A non-universal check still fails rather than passes when its applicability class turns out to be empty.

19. **`skill-contracts`.** Each discovered skill has exactly one raw ` ```halucinator-skill-contract ` fence immediately after its H1, with the required keys, the `checks` and `supplies-delta` grammar, and the single/repeatable key rules. A skill with no canonical contract mapping in `SKILL_SPEC` fails.
20. **`skill-emissions`.** The declared `emits` leaf set and `checks` set equal the sets derived from `validate.py` by `derive_registry()`.
21. **`skill-consumption`.** Every consumed leaf belongs to its declared predecessor kind, and the predecessor sets match the canonical mapping.
22. **`skill-structure`.** Ten exact nonempty H2 sections in order; a contiguous numbered `## Procedure` of imperative template verbs whose step 1 is the entry-recovery step, with at least as many steps as declared checks and every check named; an exact `## Validation` table; exactly three `## Exit criteria` predicate blocks; and an `## Application example` whose ` ```toml ` block is the emitted handoff using only that kind's schema leaves.
23. **`skill-trigger-frontmatter`.** Each description starts with `Use when`, contains `Wrong for`, and, for `scaffold-hal`, names its required dispatch terms.
24. **`skill-ownership`.** Each `writes` entry names the registry owner of that class; each `supplies-delta` entry names a semantic author who is *not* the registry owner.
25. **`skill-status-vocabulary`.** Parsed only from the raw contract's stage declaration and `## Exit criteria`, whose labels are only `ready`, `partial`, `blocked`; the nine legacy null sentinels are rejected only as TOML scalar values inside fenced TOML examples, never in ordinary prose.
26. **`skill-verdict`.** Every skill whose contract fence declares `independent-review` states the exact accepting verdict sentence and uses no spaced legacy verdict tokens. The gated set is derived from the parsed contracts, so declaring the check is what enrolls a skill.
27. **`skill-validator-wiring`.** Each skill names the validator command stem, the `--kind all` final gate, at least two validator placements inside `## Procedure`, and the honor-system limitation including that `validate.py` cannot attest to an earlier invocation.
28. **`skill-note-paths`.** For the two stages that have one — `generate-svd` and `generate-pac` — the deterministic note path appears exactly, with no soft alternative or default in the same paragraph.
29. **`schema-attribution`.** The schema documents attribute scope, decisions and foundation requirements to `hal-coordinator`, carry no stale architect phrasing, and state the corrected tester/integrator record attribution.
30. **`test-candidate-layout`.** `layout.md` ratifies the committed test-candidate root, its members, its ownership classes, the four `.gitattributes` lines and the `.run`-only ignore, and `README.md` no longer claims the ratification is deferred.
31. **`selfcheck-doc-parity`.** This document names every check the harness actually invokes, and carries the eight-agent and honor-system wording.

## Closure checks

These two checks guard the boundary of the skill set itself rather than the contents of one skill.

32. **`validation-guidance-isolation`.** Every Markdown file under `.opencode/skills/write-examples/` — `SKILL.md`, all references, and the tester-safe profiles under `references/profiles/` — is scanned by a **bounded lexical tripwire**, in the same spirit as the two-token `DRIVER_API_LEAK` tripwire described in `.opencode/schema/06-driver.md`. A file fails with `VALIDATION_GUIDANCE_LEAK` when a relative Markdown link **resolves** beneath `.opencode/skills/write-driver/`, or when prose matches the fourteen-token implementation set (`pac::`, `unsafe {`, an `embassy-*/src/` or bare `*.rs` path, `read_volatile`/`write_volatile`, a `.read(|`/`.write(|`/`.modify(|` register closure, `OnDrop`, `WaitCell`, `enable_and_reset`, `waker.register`, `register_waker`). A scan that finds zero target files fails rather than passing vacuously, and at least one validation profile must exist or the guarantee is vacuous. The analyzer is a pure function of `(path, markdown)` self-tested against a conforming sample and seven near-misses, and against the real tester-facing validation references, which must survive the token set unchanged. The token set deliberately contains **no** `private|internal` word rule: that would match the legitimate disclaimer "not the target HAL's implementation or private state". **The check catches the named links and tokens and nothing else.** Semantic implementation guidance in plain prose — "write the control register, then enable its interrupt" — matches no token and passes. This is a tripwire against the cheap, mechanical leak, not a proof of isolation; human review remains the real boundary.
33. **`skill-discovery-closure`.** Every immediate child directory of `.opencode/skills/` contains exactly one regular `SKILL.md` — discovery globs `*/SKILL.md`, so a directory without one is invisible to every template check and is therefore a silent, undeclared exemption. The discovered set must be exactly the six skill directories: `gather-documentation`, `generate-pac`, `generate-svd`, `scaffold-hal`, `write-driver`, `write-examples`. That directory set and the discovered set must be equal, and every discovered skill must be in scope for the template checks.

## No exemption mechanism

There is no allowlist. M3 carried one time-boxed, two-row exemption file so that two legacy driver skills could lag the template; M4 consolidated those two skills into `write-driver` and deleted the file, its parser, and the registry that distributed its parsed set. Deleting the data alone would have been unsafe — the parser failed **open to the empty set**, so a check pointed at a vanished file would have kept reporting `PASS` while asserting nothing. Data and parser therefore retired together, and the thirteen skill-contract checks above now take no exclusion set at all. `skill-discovery-closure` covers the one remaining way a skill could become silently exempt: never being discovered.

## Derivation and bounds

Registries are derived from source, not scraped from prose: `derive_registry()` walks `validate.py`'s AST to obtain the handoff kinds, their schema leaf paths and their canonical check IDs, and `invoked_check_names()` walks this harness's own AST to obtain the display name of every check `main()` invokes. Skill and agent contracts are parsed from raw Markdown fences so that a fenced example is never mistaken for a declaration. The structure and typed-example analyzers are pure functions driven by in-memory conforming and malformed near-miss fixtures, which is what proves they discriminate rather than rejecting everything.

The script skips `.opencode/node_modules/` completely and does not parse package JSON. Every filesystem walk is bounded to the repository, every subprocess to 30 seconds, and AST recursion, contract length and registry size to their declared maxima.
