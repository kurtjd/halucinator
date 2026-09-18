# `31-tests-api-handoff-wrong-kind`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `ILLEGAL_ENUM`

- Expected file: `halucinator/handoff/07-tests-beta-loopback.toml`
- Expected field: `tests.api_handoff`
- Expected diagnostics: exact

Defect: the coherent multi-driver arrangement of `fixtures/valid-multi-driver/`
with one change — the ready `07-tests-beta-loopback.toml` points
`tests.api_handoff` at `halucinator/handoff/05-platform.toml`, which is not a
`06-driver` handoff at all. `handoff.inputs` names the same platform handoff so
that no split-lineage or stale-evidence noise appears; the digest is current.

`tests.api_handoff` must name a present handoff **of kind `06-driver`**. Today
the field is only shape-validated as a `FileRef` (`validate.py:448-455`) and
re-hashed by `validate_refs` (`validate.py:978-993`); the target's kind is never
checked, so the fixture is accepted today (exit 0).

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/31-tests-api-handoff-wrong-kind/generation-roots/fictional-pac
```

Expected exit code: 1.
