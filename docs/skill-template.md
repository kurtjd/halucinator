# The halucinator skill template

This document is the canonical shape of a halucinator skill. It is
toolkit-authoring material: it is not copied into a destination repository and
no agent loads it at run time. Every file under `.opencode/skills/*/SKILL.md`
must conform to it, and `tools/selfcheck.py` asserts that conformance
mechanically.

Read it as a specification with decidable acceptance conditions, not as style
advice. Almost every rule below is checked; where a rule is not checkable, this
document says so rather than implying enforcement that does not exist.

## Why this shape

A skill is a procedure an agent executes, so its failure mode is not "badly
written" but "not executable". Three defects recur:

- A capability summary in the description invites an agent to act from the
  description alone, without loading the body.
- Prose steps with no ordering, no verbs and no named checks cannot be
  discharged, only paraphrased.
- Completion wording that is not the typed status vocabulary makes a handoff
  unpublishable, because the emitted artifact must carry `ready`, `partial` or
  `blocked` and nothing else.

The template's example / quick-reference / common-mistakes tail is taken from
`scaffold-hal`, which already had the most usable ending of any skill in the
corpus. The rest of the shape exists to make the body as decidable as that tail
was readable.

## Frontmatter

Exactly these keys are permitted, and only `name`, `description` and
`compatibility` are required:

```yaml
---
name: <directory name>
description: >-
  Use when <observable dispatch trigger>. <Named dispatch and search terms.>
  Wrong for <adjacent work this skill must not do>.
compatibility: opencode
---
```

`license` and `allowed-tools` are tolerated and currently unused. Any other
top-level key is rejected.

Rules:

1. `name` equals the containing directory name exactly.
2. `compatibility` is `opencode`.
3. After whitespace normalization, `description` **starts with `Use when`**
   followed by an observable trigger — something a dispatcher can recognize in
   a request, not a restatement of what the skill can do.
4. `description` **contains `Wrong for`** and names the adjacent work the skill
   must decline. A description that only claims capability cannot disambiguate
   dispatch between two neighboring skills, so a dispatcher picks by vibe.
5. `description` names the dispatch and search terms a caller would actually
   use. Name a surface the skill *assigns* to another owner as readily as one
   it performs; a skill the dispatcher cannot find is a skill that gets
   reimplemented inline.

Rules 3 and 4 are why a skill must never be executable from its description:
the description exists to route, the body exists to execute.

## The skill contract fence

Immediately after the H1, before any prose, place exactly one raw fence with
the info string `halucinator-skill-contract`:

```halucinator-skill-contract
stage: <canonical handoff stage>
participants: <sorted comma-separated agent IDs>
emitter: <one agent ID>
emits: <kind>|<deterministic filename>|<sorted comma-separated complete leaf paths>
checks: <sorted comma-separated canonical check IDs>
consumes: <kind>|<sorted comma-separated leaf paths>
writes: <agent>|<ownership class>
supplies-delta: <semantic-author agent>|<ownership class materialized by another agent>
```

**This fence is an authoring device introduced for the skill corpus. It is not
part of the handoff wire format.** It adds no field to any handoff TOML, no
diagnostic code, no schema version. `checks:` and `supplies-delta:` in
particular exist only here. Nothing reads this fence except
`tools/selfcheck.py`.

Grammar:

- `stage`, `participants`, `emitter`, `emits` and `checks` appear exactly once.
- `consumes`, `writes` and `supplies-delta` repeat, one entry per line. An empty
  `supplies-delta` is represented by **no line at all**, never by an empty
  value.
- A skill with no predecessor handoff writes exactly `consumes: none|none`.
- Values carry no whitespace around commas or pipes.
- `participants` contains every agent named by `emitter`, `writes` or
  `supplies-delta`, sorted, with no one else.
- `emits` leaf paths and the `checks` set are **equalities**, not subsets, and
  they are compared against the registry derived from
  [`validate.py`](../.opencode/schema/validate.py) by its AST — never against
  schema Markdown scraped as prose. Shorthand is not permitted: write every
  leaf.

Ownership semantics, which the checker enforces against
[`ownership.toml`](../.opencode/ownership.toml):

- `writes: <agent>|<class>` asserts that the named participant **itself
  materializes** a class it owns. The registry owner of that class must equal
  the named agent.
- `supplies-delta: <agent>|<class>` asserts that the named agent **authors
  semantic content** for a class owned and materialized by somebody else. The
  registry owner must differ from the named author, and the procedure body must
  name the registry owner and route materialization through `hal-coordinator`.

Never use `writes` to imply cross-owner authorship. That is the one contract
error that reads as correct and silently grants an agent a file class it does
not own.

## Required sections

Exactly these ten H2 headings, once each, in this order, with no interleaved H2
and none empty:

1. `## When to use`
2. `## Ownership and boundaries`
3. `## Inputs`
4. `## Outputs`
5. `## Procedure`
6. `## Validation`
7. `## Exit criteria`
8. `## Application example`
9. `## Quick reference`
10. `## Common mistakes`

H3 subheadings are free inside a section except in `## Exit criteria`, which has
its own exact form.

### `## Procedure`

A Markdown ordered list whose **top-level** markers are contiguous `1.` through
`N.`, with no gap, no restart and no indentation. Each item begins, after its
marker and an optional bold label, with a verb from this closed list:

`Inspect`, `Validate`, `Load`, `Classify`, `Select`, `Record`, `Preserve`,
`Compare`, `Author`, `Generate`, `Build`, `Run`, `Publish`, `Request`,
`Re-attest`, `Return`.

Additional requirements:

- Step 1 is always the universal entry-recovery step below, and begins
  `Inspect` with the words `entry state`.
- There are at least as many top-level steps as the contract declares checks.
- Every canonical check ID in `checks:` is named literally somewhere in the
  section.

Malformed near-misses that are rejected: H3 prose with no ordered list; a
noun-led item such as `**Input validation.**`; a skipped or restarted number;
fewer steps than checks; a check that no step names.

### `## Validation`

Exactly one table, with this header and no other:

| Check ID | Discharging action | Evidence artifact |
|---|---|---|

One nonempty row per declared check, no duplicate and no invented ID: the row
set **equals** the contract's `checks:` set.

- The discharging action begins with one of the closed template verbs above.
- The evidence cell names a concrete artifact or path category that yields a
  FileRef. For a check the skill records as not-applicable, write
  `reason (no evidence FileRef)`, matching the `Check` variant in
  [`handoff-common.md`](../.opencode/schema/handoff-common.md) that carries a
  reason instead of evidence.

A bullet list, an evidence cell reading "see procedure", or an empty cell is
rejected.

### `## Exit criteria`

Exactly three H3 blocks, in this order: `### ready`, `### partial`,
`### blocked`. No fourth status may appear — not `software verified`, not
`in progress`, not a legacy status table. Each block contains one paragraph
beginning `Predicate:` and stating decidable field and check conditions, and
the three must be **mutually exclusive**, restating the rules in
[`handoff-common.md`](../.opencode/schema/handoff-common.md):

- **ready** — `incomplete` is empty, `complete` equals the included scope,
  `can_progress` is **absent**, `blockers` is empty, and every applicable check
  is `passed`. Naming `can_progress` true or false here is an overlap error,
  not a harmless extra clause.
- **partial** — `can_progress=true`, `blockers` is empty, and either
  `incomplete` is nonempty or at least one applicable check is `unrun` or
  `failed`.
- **blocked** — `can_progress=false`, `blockers` is nonempty, and either
  `incomplete` is nonempty or at least one applicable check is `unrun` or
  `failed`.

### `## Application example`

At least one ` ```toml ` fence, one of which is **the handoff this skill
emits**: a `[handoff]` table with `schema = 2` - the validator's current
version, `SCHEMA_VERSION_CURRENT` - and `stage` equal to the
contract's `stage`. Every field path in that block must be a real schema leaf of
the emitted kind. Invented or abbreviated field names are rejected, because an
example that drifts from the contract is the first place a future author copies
from.

Legacy null sentinels are forbidden as TOML scalar values in these blocks:
`unknown`, `not provided`, `none`, `not checked`, `none recorded`,
`not selected`, `none yet`, `unverified`, `in progress`. Optional means key
absence; known-empty means an empty collection. Ordinary prose elsewhere in the
skill may of course use those words normally.

### `## Quick reference` and `## Common mistakes`

Both are required and nonempty. The quick reference is the compressed form a
returning reader needs: filenames, checks, the exit predicates, the routing
rule. Common mistakes names the specific wrong things authors and agents have
actually done in this stage — not generic caution.

## The universal entry-recovery step

Step 1 of every procedure, specialized only by stage ID and owned artifacts.
It implements "Acquire, liveness, release" and "Stage recovery" in
[`layout.md`](../.opencode/schema/layout.md).

1. **Inspect and classify entry state.** Inspect every lock applicable to this
   stage and its resources, and classify each as live, interrupted or
   ambiguous.
   - **Live** means concurrency, not interruption: do not interfere, and do not
     recover.
   - **Ambiguous** means wait one 30-second refresh interval, reread, and fail
     closed if it is still ambiguous.
   - **Interrupted**, or ambiguous still unresolved after that reread, means
     recovery: **do not mutate the suspect output.** Inventory and hash it into
     a recovery Markdown FileRef, compare it against the last valid handoff,
     and publish `partial` with empty blockers when unaffected fresh-candidate
     work remains, or `blocked` with an `interrupted:<stage>` blocker when it
     does not. Record the comparison, the chosen disposition, the new candidate
     location and the resource recovery **before** an authorized actor removes
     the lock. Resume only in a fresh candidate or run location; never resume a
     canonical replacement in place.

Time alone never permits deleting a lock, and a successful classification is
not a repair.

## Validator wiring, and its limit

Every skill names the command stem `python .opencode/schema/validate.py` with
`--kind all` and the required named-root bindings, and places it in
`## Procedure` at least twice: once **before** semantically consuming any
predecessor handoff, and once **after** writing the preliminary and again the
final handoff. Exit 0 with silent output is necessary before consumption. A
missing interpreter, a timeout, a nonzero exit, or simply not running it is not
a pass and blocks consumption.

A stale unrelated artifact or an ambiguous unrelated lock surfaced by the
all-kinds gate is reported as a named blocker, never silently ignored.

**This is an honor system.** The self-check can prove that a skill *contains*
these instructions; it cannot prove that an agent *ran* them, and `validate.py`
cannot attest to its own earlier invocation. The wiring is procedural evidence
discipline, not runtime enforcement, and no skill may describe it as
enforcement. Typed evidence hashes freshness, not relevance: a reviewer still
has to judge whether the evidence discharges the check it is attached to.

Hash and occurrence checks prove bytes and the bounded relation they state;
the claimant may still have fabricated execution evidence. No external attester
exists, and nothing here can detect a false claim about work that was never
done.

## The ordered publication sequence

Publish in exactly this order. Its purpose is to close the windows in which
evidence is missing, a handoff is unvalidated, or state points at bytes that do
not validate.

1. Write durable evidence and notes first.
2. Where a cross-owner delta is required, `hal-coordinator` dispatches the
   registry owner to materialize it and returns its FileRef.
3. Preserve a hashed snapshot and recovery record of any deterministic handoff
   that `state.toml` currently pins, **before** replacing it.
4. Write the preliminary handoff.
5. Validate it.
6. Obtain the coordinator-dispatched review where `independent-review` applies.
7. Re-attest, per the sequence below.
8. Rewrite the final deterministic handoff.
9. Validate it.
10. `hal-coordinator` updates `state.toml` through the compare-and-swap
    sequence. **State is never updated before the handoff validates.**
11. Run the final `--kind all` gate.

Two residues remain open and a skill must not claim otherwise: the gap between
a canonical copy and its commit, and the gap between the final handoff rewrite
and the state update. A snapshot makes the second recoverable within one
worktree; it does not make it transactional, and a fresh clone cannot see a
crash marker at all because `.run` is ignored. Durable journal, phase marker
and fencing work is deferred.

## The re-attestation sequence

When referenced bytes legitimately change — on resumption, and on every
transition from a preliminary handoff to a final one — apply
[`handoff-common.md`](../.opencode/schema/handoff-common.md)'s re-attestation
rules as executable steps:

1. Preserve the superseded evidence and the superseded review records.
2. Create replacement evidence at a **new path**. Never overwrite an evidence
   path in place.
3. Rerun only the affected checks.
4. Obtain a new review where the reviewed bytes changed.
5. Replace the deterministic handoff and the state references through the
   compare-and-swap sequence.

**Never delete old evidence or old review records to regain validation.** That
converts a traceable supersession into an untraceable one, and it is the single
most tempting shortcut when a late check fails. `review.lineage` records review
rechecks only; it is not a general supersession mechanism.

## The accepting review verdict

[`08-review.md`](../.opencode/schema/08-review.md) defines the verdict vocabulary
as `ready|ready-with-fixes|not-ready`, and only `ready` accepts. Every
review-gated skill states this in exactly this form:

> Only review.verdict=ready accepts; ready-with-fixes and not-ready do not.

Use the hyphenated typed tokens. The spaced legacy spellings are rejected
wherever they appear in gate prose: they read as English rather than as values,
and prose that quotes only a rejecting verdict leaves the accepting one
unstated, which is how a gate quietly becomes advisory.

## Application example

A minimal conforming skeleton, with the contract and body elided to their
asserted shape:

```markdown
---
name: generate-pac
description: >-
  Use when a checked SVD preparation handoff exists and a Rust peripheral
  access crate must be generated or regenerated. Covers generator setup,
  metapac assembly, Cargo packaging and generation replay. Wrong for preparing
  or correcting SVDs, implementing HAL drivers, or publishing crates.
compatibility: opencode
---

# Generate the peripheral access crate
```

followed immediately by the contract fence, then the ten sections. The
`## Procedure` opening and the `## Validation` table look like this:

```markdown
## Procedure

1. **Inspect and classify entry state.** Inspect the stage and PAC-integration
   locks, classify each as live, interrupted or ambiguous, and recover into a
   fresh candidate run as specified, never in place.
2. **Validate before consumption.** Run
   `python .opencode/schema/validate.py <repository-root> --kind all` with every
   required named-root binding before reading the predecessor handoff, and
   discharge `input-identity` from what it reports.
3. **Generate the candidate crate.** Generate into an unused run directory and
   record `expected-inventory` against an independently derived expectation.

## Validation

| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `input-identity` | Validate the predecessor handoff and compare hashes | `derived/pac/<target-id>/<run-id>/candidate/identity.log` |
| `pure-host-tests` | Run the host test suite | `reason (no evidence FileRef)` |
```

and the emitted handoff appears under `## Application example` as a ` ```toml `
fence whose `[handoff]` table carries `schema = 2` and the contract's `stage`.

## Quick reference

| Element | Exact requirement |
|---|---|
| Frontmatter keys | `name`, `description`, `compatibility`; optional `license`, `allowed-tools` |
| Description | starts `Use when`; contains `Wrong for`; names dispatch terms |
| Contract fence | one raw ` ```halucinator-skill-contract ` fence immediately after the H1 |
| Single-value keys | `stage`, `participants`, `emitter`, `emits`, `checks` |
| Repeatable keys | `consumes`, `writes`, `supplies-delta` (absent when empty) |
| Sections | the ten H2s, once each, in order, none empty |
| Procedure | contiguous `1.`..`N.`, closed verb list, step 1 is entry recovery, steps >= checks, every check named |
| Validation | one table, `Check ID / Discharging action / Evidence artifact`, row set equals `checks:` |
| Exit criteria | exactly `### ready`, `### partial`, `### blocked`, each one `Predicate:` paragraph |
| Application example | a ` ```toml ` fence that is the emitted handoff, real leaves only |
| Validator | command stem plus `--kind all`, at least two placements in `## Procedure` |
| Honor system | stated explicitly, including that `validate.py` cannot attest to an earlier invocation |
| Verdict | the exact accepting sentence, hyphenated tokens only |

## Common mistakes

- **Writing a description that summarizes capability.** It reads fine and it
  makes the body optional. Lead with the trigger and name what the skill is
  wrong for.
- **Declaring `writes` for a class another agent owns.** The contract checker
  catches it, but the deeper problem is that it describes a pipeline in which
  two agents may write one file. Use `supplies-delta` and name the materializer.
- **Abbreviating `emits` leaves.** The leaf set is an equality against the
  derived registry; a partial list is a mismatch, not a summary.
- **Writing the procedure as H3 prose.** It is the most natural way to write and
  the least assertable. Steps must be numbered, contiguous and verb-led.
- **Adding a fourth exit status.** `software verified` and `in progress` are the
  usual ones. They are not in the typed stage vocabulary, so a handoff carrying
  them cannot be published at all.
- **Letting the worked example drift.** An invented field in the ` ```toml `
  block is copied forward by the next author, who assumes it validates.
- **Overwriting evidence to make a rerun pass.** It removes exactly the record
  a reviewer needs. Create replacement evidence at a new path and preserve the
  superseded record.
- **Updating state before the handoff validates.** It leaves state pointing at
  bytes that do not parse, which is the one inconsistency no downstream agent
  can detect from its own inputs.
- **Describing validator wiring as enforcement.** It is an honor system. Saying
  otherwise makes every reader trust an attestation that was never made.
