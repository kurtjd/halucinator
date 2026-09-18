# Fixture requirements

Tester authors fixtures; M1 does not. Use fictional Unobtainium Circuits / UC-NOT-A-REAL-MCU-0001 only. Every note says `FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE`; no real-looking hardware numbers.

## Valid

`fixtures/valid/` contains exactly ten TOML documents: one state file, one scope decision, and eight handoffs, matching the ten fenced TOML blocks in `worked-examples.md`. Unlike documentation placeholders, replace every 64-`a` digest with the actual raw-byte SHA-256. Materialize all referenced notes/evidence/inventory/source files under the shown roots. To keep CI portable, the valid fixture binds `generation:fictional-pac` to a fixture-local directory supplied through the validator's explicit test-root binding mechanism; it must not depend on `C:/authorized/...`. The fixture proves all artifact kinds can be written coherently, including a ready PAC and honest downstream partial states.

## Invalid

Each `fixtures/invalid/<NN>-<slug>/` is independently complete or differs from valid only in the intended defect. README names exactly one expected diagnostic code. Required, one per rule:

1. `01-unknown-field`; 2 `02-missing-required`; 3 `03-illegal-enum`; 4 `04-ready-dependency-not-ready`; 5 `05-input-hash-mismatch`; 6 `06-stale-review`; 7 `07-in-progress-handoff`; 8 `08-lock-complete-conflict`; 9 `09-narrowed-ready-scope`; 10 `10-path-escape`; 11 `11-noncanonical-digest`; 12 `12-malformed-lock`; 13 `13-review-nonaccepting`; 14 `14-driver-api-private-leak-key`; 15 `15-omitted-mandatory-check`; 16 `16-not-applicable-without-reason`; 17 `17-incomplete-status-partition`; 18 `18-stale-non-review-evidence`; 19 `19-route-incompatibility`; 20 `20-missing-dependency-identity`; 21 `21-windows-unsafe-lock-id`; 22 `22-unknown-schema-version`; 23 `23-first-peripheral-without-modes`; 24 `24-foundation-partition-missing`; 25 `25-scope-deleted-predecessor`; 26 `26-scope-second-initial`; 27 `27-scope-fork`; 28 `28-scope-orphan`; 29 `29-scope-cycle`.

`fixtures/valid/` contains no lock, so committed stale heartbeats cannot affect its required exit 0. Structural/filename-positive lock samples live in sibling `fixtures/valid-locks/`; committed locks cannot exercise liveness because their heartbeat inevitably ages. Fixture 21 statically covers only the representable percent-encoded-colon bypass; raw-colon NTFS rejection is operational, not a static fixture. State-generation races and live-lock PID/clock behavior are operational tests specified in `validate.md`, not static fixtures. Every invalid fixture must exit 1 and contain its expected code; unrelated failures invalidate the fixture.

If these cannot be authored directly from the worked examples, revise schema before validator implementation.
## Hash materialization order

The worked-example placeholder is exactly 64 lowercase `a` characters. Materialize files in this order: (1) source, note, check-evidence, authorization, and inventory files; (2) scope decision; (3) handoffs in numeric order, with review created before the reviewed stage's final ready rewrite; (4) state last. Hash each completed file's raw bytes before writing its referrer. Evidence notes and inventories must not embed hashes of handoffs/state that refer back to them; this prohibition prevents hash cycles. After materialization, replace no file without following re-attestation. Run the validator only after state is hashed last.