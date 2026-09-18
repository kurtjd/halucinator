# `valid-multi-driver`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

A **second complete, coherent, accepted** artifact set. It exists to prove that
correct `write-tests` binding is independent of how many `06-driver` handoffs a
repository contains, and to pin the rule that must *not* be written.

Differences from `fixtures/valid/`:

- Two drivers, both `ready`: `06-driver-alpha.toml` and `06-driver-beta.toml`.
- A `ready` `07-tests-beta-loopback.toml` whose `tests.api_handoff` binds
  `halucinator/handoff/06-driver-beta.toml` — the **second** driver by filename
  sort order.
- `tests.name = "beta-loopback"` deliberately **differs** from
  `driver.name = "beta"`. There is no `tests.name == driver.name` equality rule
  and there must never be one: the toolkit's own canonical example binds
  `tests.name = "uart-loopback"` to `06-driver-uart.toml`
  (`.opencode/skills/write-examples/SKILL.md`). A validator that asserted name
  equality would reject the documented workflow, so this fixture is the
  regression guard against it.
- Scope is `["foundation:init-api", "foundation:interrupt-metadata",
  "peripheral:alpha", "peripheral:beta"]`, and `05-platform.toml` is `ready`
  (a ready driver requires a ready `scaffold-hal`), which in turn requires the
  additional review handoffs `08-review-platform.toml`,
  `08-review-driver-alpha.toml`, `08-review-driver-beta.toml` and
  `08-review-tests-beta-loopback.toml`.
- `state.toml` records `write-driver:alpha`, `write-driver:beta` and
  `write-tests:beta-loopback` as separate stage entries.

Honest status: this fixture is **regression coverage, not new RED**. It exits 0
with no diagnostics both before and after the A19 repair. Its value is that it
fails loudly if the repair over-reaches — for example by keying drivers on
`handoff.stage` alone, by demanding `tests.name == driver.name`, or by rejecting
a second handoff for a repeatable kind.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/valid-multi-driver/generation-roots/fictional-pac
```

Expected exit code: 0, with no diagnostics on stdout or stderr.
