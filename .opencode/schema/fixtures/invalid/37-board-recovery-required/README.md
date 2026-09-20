# `37-board-recovery-required`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Defect: a hardware-validation `07-tests` handoff is published while the
interlock for its board is still `active` with the board state `unknown`.
The lock never reached `recovery-verified`, so the board was never shown
safe; holder death is not operation death, and a surviving probe child may
still be driving pins.

The validator must emit exactly this diagnostic set - no more, no fewer.
`Reporter` stores its lines in a set, so a repeated diagnostic is
unobservable and the assertion is over the sorted SET, not a multiset.

Expected diagnostic: `halucinator/handoff/07-tests-schema-demo.toml|tests.board_interlock.lease_epoch|BOARD_RECOVERY_REQUIRED`

Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;
every byte here is derived from `tools/schema-fixtures.toml`.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/37-board-recovery-required/generation-roots/fictional-pac
```

Expected exit code: 1.
