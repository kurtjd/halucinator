# `32-noncanonical-singleton-filename`

FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE

Expected diagnostic code: `UNKNOWN_FIELD`

- Expected file: `halucinator/handoff/05-platform-extra.toml`
- Expected field: `-`
- Expected diagnostics: exact

Defect: `halucinator/handoff/` carries a stray `05-platform-extra.toml`
alongside the canonical `05-platform.toml`. `05-platform` is a **singleton**
kind: unlike `06-driver-<name>`, `07-tests-<name>` and `08-review-<artifact>`,
its filename is not name-derived and is not repeatable.

`kind_of()` (`validate.py:786-790`) matches a handoff filename by **prefix**:
`"05-platform-extra.toml".startswith("05-platform")` is true, so the stray file
is admitted as a second `scaffold-hal` handoff and the fixture is accepted today
(exit 0). Worse, `"05-platform-extra.toml"` sorts *before* `"05-platform.toml"`
(`-` is 0x2D, `.` is 0x2E), so it is the entry that wins `world.by_stage`
(`validate.py:1526-1527`).

Discovery must enforce exact filenames for the five singleton kinds
(`01-sources`, `02-facts`, `03-svd`, `04-pac`, `05-platform`) and emit the
existing `UNKNOWN_FIELD` at field `-` for anything else, exactly as it already
does for a filename matching no kind at all (`validate.py:1512-1516`).

Derived from `fixtures/valid-multi-driver/` by adding one byte-identical copy of
`05-platform.toml` under the non-canonical name, so no digest anywhere else in
the tree changes.

Invoke as:

```text
python .opencode/schema/validate.py <this-dir>/root \
  --root generation:fictional-pac=<abs-path-to>/32-noncanonical-singleton-filename/generation-roots/fictional-pac
```

Expected exit code: 1.
