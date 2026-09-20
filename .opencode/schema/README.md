# Handoff schema index

These documents specify schema version 2. They are contracts, not executable schemas. Version 1 is superseded: existing version-1 records remain historical evidence and are not current consumable roots.

- [Terminology](terminology.md)
- [Runtime layout and locks](layout.md)
- [`state.toml`](state.md)
- [Common handoff](handoff-common.md)
- [01 sources](01-sources.md)
- [02 facts](02-facts.md)
- [03 SVD](03-svd.md)
- [04 PAC](04-pac.md)
- [05 platform](05-platform.md)
- [06 driver](06-driver.md)
- [07 tests](07-tests.md)
- [08 review](08-review.md)
- [Complete worked examples](worked-examples.md)
- [Traceability](traceability.md)
- [Validator](validate.md)
- [Fixtures](fixtures.md)
- [Self-check](selfcheck.md)
- [Superseded revision 2 record](revision-2.md)
- [Revision 3 final audit](revision-3.md)

Normative precedence is: per-kind document over common handoff over layout. A contradiction is a schema defect; implementations must fail rather than guess.
