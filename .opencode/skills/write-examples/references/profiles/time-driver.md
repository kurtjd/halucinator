# Time Driver Validation Profile

This is the **public, tester-safe validation profile** for an Embassy time
driver. **hal-tester** loads it in addition to [`universal.md`](./universal.md)
when the coordinator-supplied public contract positively establishes that the
driver under test is a time driver. **hal-driver** uses its requirements and
**hal-reviewer** audits coverage.

It describes observable time-service behavior, not the target HAL's
implementation or private state.

## Intake and composition

Use `write-examples`' public intake and record fields for target, API and source
versions, build and runtime facts, and existing evidence. **hal-coordinator**'s
handoff also supplies the time-specific contracts: initialization, reserved
resources, tick rate and resolution, supported idle and clock behavior,
observation facilities, and accuracy and latency expectations with their cited
basis. Unknowns block dependent checks, not unrelated software preparation.

Read `AGENTS.md` at the actual working repository root for shared boundaries and
artifact policy, not relative to the skill installation. **hal-tester** combines
this profile with `write-examples` and its required
[test-record](../test-record.md) and
[hardware-execution](../hardware-execution.md) references for test creation,
setup, execution, repair and retest, and public records. This is not a second
execution workflow. Do not load HAL bodies, private implementation checklists, or
the full time-driver record. Implementation and review readers consume these
contracts without taking the tester's writing or hardware-execution role. Report
API ambiguity or missing observability to **hal-coordinator**.

## Contract sources

Read the actual dependency versions in the executing checkout. These official
entry points identify the contracts, not a version to impose on every HAL:

- [embassy-time-driver](https://docs.rs/embassy-time-driver/latest/embassy_time_driver/index.html):
  one global driver, driver registration, tick-rate configuration, and linkage.
- [Driver](https://docs.rs/embassy-time-driver/latest/embassy_time_driver/trait.Driver.html):
  timestamp and wake-scheduling obligations, including monotonic, non-failing
  reads before initialization. The current API uses `now` and `schedule_wake`;
  confirm the checkout's interface rather than assuming an older alarm API.
- [Timer](https://docs.rs/embassy-time/latest/embassy_time/struct.Timer.html):
  the public future's completion semantics and the distinction between an
  absolute deadline and a relative duration. Inspect other claimed consumer
  APIs, such as periodic timers, only when included in the task.
- [Queue](https://docs.rs/embassy-time-queue-utils/latest/embassy_time_queue_utils/struct.Queue.html):
  the selected backend's public scheduling/capacity contract where relevant.
  Do not derive test expectations from the target driver's queue internals.

In the matrix, **D** means the versioned driver contract, **T** the public time
consumer contract, and **H** the handed-over HAL/MCU/board contract and cited
facts. Add precise dependency or document title/number, revision, and
section/table/page references to each case. Wake notifications are not timer
completion: do not assume exactly one wake, no early/spurious wakes, immediate
first-poll readiness, or removal of every queue entry on cancellation unless
the actual upstream contract promises it.

## Verification matrix

Map every applicable row to a concrete case, expected result, evidence category,
and owner. **Host** tests exercise actual pure production logic and belong to
**hal-driver**. **Build** includes compilation and actual target linking;
**HIL** means an observed agent-run hardware case, both owned by **hal-tester**.
**Review** is independent implementation review by **hal-reviewer**.

| ID | Requirement and scenario | Expected result | Basis | Evidence and owner |
|---|---|---|---|---|
| TIME-01 | Link a public time consumer with the selected driver and tick features; check the supported enabled/disabled resource policy and applicable incompatible selections. | Exactly one active driver and an agreed tick rate; no duplicate registration or simultaneous user claim of reserved timer resources. | D, H | Build: tester; Review: reviewer |
| TIME-02 | Read public time before initialization and across the documented public initialization sequence. | Reads do not fault or fail; time does not go backwards across initialization. A documented initial value is not permanently frozen time after init. | D, H | HIL: tester; Review: reviewer |
| TIME-03 | Read repeatedly from supported execution contexts, with concurrent reads where the platform supports them. | Ordered observations are nondecreasing, consistent, and continue to advance; no torn timestamp or invalid epoch. | D, H | HIL: tester; Review: reviewer |
| TIME-04 | Exercise production timestamp/deadline arithmetic at counter and epoch boundaries; observe a real wrap when reachable in the agreed runtime configuration. | Time and scheduled completions remain correct across boundaries, within the documented service assumptions. Modeled arithmetic is not an observed hardware wrap. | D, T, H | Host: driver; Review: reviewer; reachable required HIL cases: tester |
| TIME-05 | Measure elapsed public time over an independently measured interval, including short and long intervals relevant to the claimed resolution. | Tick rate, units, conversion, and drift meet a justified tolerance after accounting for quantization and measurement uncertainty. | D, T, H | Host arithmetic: driver; HIL: tester |
| TIME-06 | Schedule deadlines in the past or at the current timestamp, and zero-duration timers through the selected public APIs. | Futures make progress according to the versioned contracts without waiting for a full hardware wrap or hanging. | D, T | HIL: tester; Review: reviewer |
| TIME-07 | Exercise the shortest supported delays and deadlines near the programming boundary; vary when futures are first polled. | No requested completion is lost when a deadline passes during scheduling; readiness respects the public deadline and rounding semantics. | D, T, H | Host arithmetic: driver; HIL: tester; Review: reviewer |
| TIME-08 | Schedule distant deadlines, including beyond the hardware's direct compare window where applicable. | No truncated deadline, premature future completion, or stranded timer; eventual completion meets the recorded timing bound. | D, T, H | Host arithmetic: driver; HIL: tester; Review: reviewer |
| TIME-09 | Start a later timer, then add an earlier one while it is pending; repeat with equal and differing deadlines. | The earlier deadline is serviced without losing the later one; equal deadlines need no invented task execution order. | D, T | HIL: tester; Review: reviewer |
| TIME-10 | Use several tasks and several timer futures within one task, with repeated polls and deadline updates permitted by the public API. | Every required timer completes; shared wakers or coalesced scheduling do not strand peers or complete a future before its contract allows. | D, T, H | HIL: tester; Review: reviewer |
| TIME-11 | Drop before first poll and after scheduling, immediately create another timer, and keep an independent timer pending throughout. | Dropping one future does not reset the timebase or break another timer; subsequent scheduling works despite permitted stale wakes. | T, H | HIL: tester; Review: reviewer |
| TIME-12 | Repeat bounded batches of timers and cancellation/reuse within the selected queue's supported usage; exercise documented capacity behavior where applicable. | No progressive loss of scheduling or undocumented failure; evaluate future outcomes rather than raw wake counts. | D, T, H | HIL: tester; Review: reviewer |
| TIME-13 | Let the executor become idle with a pending timer; test only declared supported sleep or clock-transition modes. | The timebase and wakeups meet the stated contract in those modes; unsupported power behavior is not silently claimed. | T, H | HIL: tester; Review: reviewer |
| TIME-14 | Measure public completion timing under the agreed task/interrupt load and any claimed periodic use. | Completion latency and periodic behavior satisfy their documented bounds; distinguish timer events from delayed task execution and transport timestamps. | T, H | HIL: tester; Review: reviewer |

At intake, identify which runtime cases/configurations are required and how
their events can be observed. Missing evidence, equipment, or PAC coverage is
not unsupported silicon. A cited capability limit or explicitly agreed scope
can make a case inapplicable; do not quietly drop a failing or blocked case.
Bounded scaffold support covers only its assigned software checks, not full
time-service validation. Record unobserved behavior separately from passes.

## Independent timing evidence

**Do not use the time driver under test as the sole clock for its own acceptance
or test timeout.** `now()` and `Timer` agreeing with each other can conceal the
same frequency error. **A second counter on the same unverified clock is not an
independent frequency reference.**

**Use a documented external reference or suitable instrument for quantitative
accuracy and latency claims**, with a public observation path such as a known
GPIO marker only when the handed-over fixture supports it. Provide the required
connections and instrument setup through `write-examples`; do not invent pin,
voltage, oscillator, or calibration facts. **Record reference frequency and
accuracy, sample window, event definition, quantization, and transport and
scheduling uncertainty before choosing tolerances. Never derive a passing limit
from the failing driver's observed rate.**

A host-side watchdog establishes bounded liveness. Host timestamps can support
coarse interval checks only with a justified uncertainty bound; debugger, USB or
RTT latency is not a precise timer measurement. Separate a hardware event, task
resumption, and host receipt of a log. **Missing independent observation leaves
the corresponding accuracy claim unverified or its required HIL case `blocked`.**

## Boundary and concurrency cases

Use public `embassy-time` consumer APIs and the documented initialization
surface. Account for lazy futures: creating a timer is not proof it has been
polled or scheduled. Arrange polling and stimuli deliberately for earlier and
later insertion, cancellation, and pending-peer cases. Repoll on wakes and judge
completion against the actual contract, not an invented one-wake-per-alarm rule.

Use genuine production arithmetic for host boundary tests, not a disconnected
timer simulator. Reduced-width exploration or a test-only accelerated timer
can inform review but is not production rollover HIL evidence. Observe a real
boundary in an advertised configuration when feasible, with a cited counter
period and run budget. If impractical or inaccessible through the public API,
record the limitation and planned host and review evidence; required runtime
coverage stays blocked until satisfied or the scope is explicitly revised.
**Do not add private counter-write hooks or have the tester poke registers to
force a pass.**

## Results and handoff

Use `write-examples`' public test record and repair/retest workflow. Include
the TIME requirement mapping, selected API/tick configuration, timing reference
and tolerances, actual observations, wrap/idle cases exercised, and remaining
measurement gaps. Reuse existing public records and link them through
**hal-coordinator**, which links them from the private time-driver record. The
tester never reads that record's implementation sections and never changes the
driver to match a test expectation.
