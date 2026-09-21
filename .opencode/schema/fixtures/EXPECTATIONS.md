# Fixture expectations manifest

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

**This manifest no longer restates expectations.** It used to hold a third copy
of the per-fixture expected diagnostic, alongside each fixture's `README.md` and
the harness's own assertions. Three copies of one fact is the drift this
milestone exists to remove: the table was maintained by hand, nothing compared
it with what the validator actually emitted, and it silently disagreed with the
corpus the moment a fixture changed.

The single source of truth is now `../../../tools/schema-fixtures.toml`. It
declares every fixture root, the exact mutation that creates each defect, and
the exact diagnostic triples the validator must emit. From it:

- `python tools/generate_schema_fixtures.py --root . --write` regenerates every
  fixture byte, including each `README.md` and its
  `Expected diagnostic: <file>|<field>|<CODE>` lines.
- `python tools/generate_schema_fixtures.py --root . --check` regenerates into a
  temporary directory and exits 0 only when every committed byte matches.

`tools/selfcheck.py` then runs the validator over each root and requires the
sorted diagnostic **set** to equal that root's declarations. Set, not multiset:
the validator's `Reporter` stores its lines in a set, so a repeated diagnostic
is unobservable and a multiset assertion would be unimplementable rather than
merely strict.

## What the accepted roots must do

`valid/` and `valid-multi-driver/` must each exit **0** with **no diagnostics**:

```text
python .opencode/schema/validate.py <root>/root \
  --root generation:fictional-pac=<abs>/<root>/generation-roots/fictional-pac
```

The `--root` binding must be an absolute path; `validate.md` forbids
drive-relative and guessed locations, so the caller resolves it.

`valid-multi-driver/` is a second accepted artifact set carrying two `06-driver`
handoffs and one `07-tests` bound to the **second** of them, with `tests.name`
deliberately different from the driver name. It exists so that a binding rule
cannot pass merely because there is only one candidate.

## What these fixtures do not prove

Every root here is the transparently fictional
`unobtainium-circuits-uc-not-a-real-mcu-0001` and its FICTIONAL FIXTURE
REFERENCE MANUAL; the generator refuses any target or document string that could
be mistaken for real silicon. A green fixture run proves the validator emits the
declared diagnostics for the declared mutations. It does not prove the declared
mutations are the right ones to be testing, and it does not prove any of the
gates would fire on a real artifact that is wrong in some way nobody declared.
That judgement stays with review.

`valid-locks/` has no `root/` directory, so the validator is never pointed at
it: committed locks cannot exercise liveness, because their heartbeat inevitably
ages. Live-lock classification, state-generation races and the worktree-local
board interlock are exercised by `../test_runtime.py`, not by static fixtures.
