# Schema fixtures

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Hand-authored acceptance fixtures for `.opencode/schema/validate.py`. Authored
from the specification **before** the validator existed, so that the fixtures
test the contract rather than the implementation.

Everything here describes the transparently fictional
**Unobtainium Circuits UC-NOT-A-REAL-MCU-0001**
(`target-id` `unobtainium-circuits-uc-not-a-real-mcu-0001`). No file in this
tree contains a register offset, bit position, reset value, clock topology or
manual section number. There is nothing here to mistake for hardware evidence.

## Layout

Every fixture is a self-contained pair of directories:

```text
<fixture>/
  root/                              <- the validator's positional ROOT argument
    .gitattributes                   <- the byte policy validate.md requires
    halucinator/{state,scope,handoff,docs,candidates,.run}/...
    embassy-unobtainium/, examples/  <- referenced non-halucinator artifacts
  generation-roots/fictional-pac/    <- bound with --root generation:fictional-pac=<abs>
```

`fixtures.md` leaves this layout open; the `root/` + `generation-roots/` split
is chosen here and applied uniformly so that the named-root binding stays
fixture-local and CI-portable, never `C:/authorized/...`.

Trees:

- `valid/` — the one complete coherent artifact set: `state.toml`, one scope
  decision, and eight handoffs, matching the ten fenced TOML blocks in
  `worked-examples.md`. Exits 0.
- `valid-multi-driver/` — a second complete coherent artifact set (M4): two
  ready `06-driver` handoffs (`alpha`, `beta`) and one ready `07-tests`
  (`beta-loopback`) bound through `tests.api_handoff` to the second of them,
  with `tests.name` deliberately unequal to `driver.name`. Exits 0. Regression
  coverage for the `tests.api_handoff` binding rule, not a rejection case.
- `invalid/NN-slug/` — 32 fixtures, one per rejection rule. Each is a **full
  re-materialization** of a coherent set with exactly one defect injected at the
  right point in the hash order, so every unrelated digest stays correct. Each
  carries its own `README.md` naming exactly one expected diagnostic code;
  30-32 additionally declare `Expected diagnostics: exact` and are held to
  exactly one diagnostic with a matching file and field.
- `valid-locks/` — valid lock files for canonical stage IDs containing `:`,
  demonstrating the computed filename-safe lock ID. Held **outside** `valid/root`
  deliberately: see "Known limitations".

## Hashes

Every `sha256` is the real raw-byte SHA-256 of the referenced file. The
worked-example 64-`a` placeholders appear nowhere. Files were materialized in
the order mandated by `fixtures.md#hash-materialization-order`: evidence, then
the scope decision, then handoffs `01`, `02`, `03`, then `08-review-pac`
(created before the reviewed `04-pac` is written, per "review created before the
reviewed stage's final ready rewrite"), then `04`, `05`, `06`, `07`, then
`state.toml` last.

## Expectations

See `EXPECTATIONS.md` for the per-fixture expected diagnostic code, file and
field, and for the list of codes this fixture set had to mint because
`validate.md` does not enumerate them.

## Known limitations

- **Raw-colon lock filenames cannot be materialized.** `fixtures.md` asks for
  "invalid raw-colon filename coverage", but Windows (NTFS) cannot create a file
  named `write-tests:schema-demo.lock`. `21-windows-unsafe-lock-id` covers the
  representable half of that rule with a percent-encoded colon instead. Raw-colon
  rejection needs an operational test, not a committed fixture.
- **Lock liveness is not exercised.** A committed lock's heartbeat is always
  stale, so static lock fixtures are permanently "interrupted or ambiguous".
  `fixtures.md` already classifies live-lock PID/clock behavior as operational.
  `valid-locks/` therefore sits outside `valid/root/` so that a liveness
  classification cannot break the exit-0 guarantee.
- **`ATTRIBUTES_UNVERIFIED`.** `validate.md` blocks ready handoffs when the Git
  byte policy is unverifiable. Each `root/` ships a `.gitattributes` with the
  mandated patterns plus explicit policy for the paths the worked example itself
  uses (`halucinator/candidates/**`, `halucinator/.run/*.lock`, `examples/**`,
  `embassy-unobtainium/**`) which the mandated list does not cover.
- **No fixture 30.** "Consuming a partial input to mutate canonical artifacts"
  is not statically representable; `validate.md` records it as an operational
  limitation. (The number `30` was later reused by
  `30-tests-bound-to-blocked-driver`; the unrepresentable case remains
  operational.)
- **Fixtures 30-32 were authored RED.** They are accepted (exit 0) by the
  validator as it stands and describe the contract the validator must grow to
  meet. Their `README.md` files cite the exact `validate.py` lines that admit
  them today.
