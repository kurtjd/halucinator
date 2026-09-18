# `30-tests-bound-to-blocked-driver`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `DEPENDENCY_NOT_READY`

- Expected file: `halucinator/handoff/07-tests-beta-loopback.toml`
- Expected field: `tests.api_handoff`
- Expected diagnostics: exact

Defect: two `06-driver` handoffs exist. `06-driver-alpha.toml` is `ready`;
`06-driver-beta.toml` is honestly `partial` (`format-lint-build` and
`target-link-ci` unrun) and `state.stages` agrees. `07-tests-beta-loopback.toml`
is nevertheless `ready` and its `tests.api_handoff` binds **beta**.

A ready `07-tests` must be gated on the `06-driver` it actually names, not on
whichever `write-driver` handoff happens to be discovered first.

`alpha` sorts lexically before `beta` on purpose: today
`validate.py:1507-1527` stores only the first handoff per `handoff.stage`, so
`world.by_stage["write-driver"]` is the ready alpha, and the generic ready
dependency gate at `validate.py:1068-1091` consults that entry. The fixture is
therefore accepted today (exit 0) and must be rejected once `tests.api_handoff`
is resolved through a per-path index.

Every digest in the tree is internally current, so no `STALE_EVIDENCE` or
`INPUT_HASH_MISMATCH` noise can mask the defect.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/30-tests-bound-to-blocked-driver/generation-roots/fictional-pac
```

Expected exit code: 1.
