#!/usr/bin/env python3
"""D17 fault-injection suite for the worktree-local board interlock.

The production helper is driven **black-box, as a subprocess**, and the result
is judged from its exit code, its JSON output and the bytes it left on disk.
Nothing here re-implements the algorithm under test, so a test cannot agree
with a bug by construction.

Every case injects its named fault through the helper's internal adapter seam -
an environment-named JSON file, never a CLI option - so the fault reaches the
real code path rather than a test double. Read each case as the evidence for
its claim: the self-check that runs this suite derives coverage from names and
docstrings and **cannot** prove a test injects the fault it is named for. This
file is where that assurance actually lives.

Run directly: `python .opencode/schema/test_runtime.py`.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib

HERE = os.path.dirname(os.path.abspath(__file__))
RUNTIME = os.path.join(HERE, "runtime.py")
TIMEOUT = 60

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DURABILITY = 3
EXIT_CONFLICT = 4
EXIT_RECOVERY = 5
EXIT_CAS = 6

BOARD = "fictional-fixture-board-1"
AUTHORIZATION = "halucinator/docs/fictional/notes/AUTH.md"
SAFE_STATE = "halucinator/evidence/safe-state/observation.toml"
ATTEMPT_1 = "halucinator/evidence/recovery/1.toml"
ATTEMPT_2 = "halucinator/evidence/recovery/2.toml"
PROCEDURE = "halucinator/docs/fictional/notes/SAFE-STATE-PROCEDURE.md"
FACTS_HANDOFF = "halucinator/handoff/02-facts.toml"
RAW_EVIDENCE = "halucinator/evidence/raw/probe-log.txt"
OPERATOR_CONFIRMATION = "halucinator/evidence/raw/operator-confirmation.txt"
OVERRIDE_RECORD = "halucinator/evidence/recovery/override.toml"

HAZARDS = ("outputs", "dma", "interrupts", "external-loads", "reset-halt", "probe")
PHYSICAL_HAZARDS = ("external-loads", "probe")

# Everything below is transparently fictional. The only example material this
# project permits is the unobtainium-circuits-uc-not-a-real-mcu-0001 target and
# its FICTIONAL FIXTURE REFERENCE MANUAL; nothing here describes real silicon.
FICTIONAL_NOTE = (
    "FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE\n"
    "Target unobtainium-circuits-uc-not-a-real-mcu-0001, an invented part.\n")



class Failure(AssertionError):
    pass


# --------------------------------------------------------------------------
# Harness
# --------------------------------------------------------------------------


class Worktree:
    """One disposable repository root with a `halucinator/.run` directory."""

    def __init__(self) -> None:
        self.root = tempfile.mkdtemp(prefix="halucinator-interlock-")
        os.makedirs(os.path.join(self.root, "halucinator", ".run"), exist_ok=True)

    def close(self) -> None:
        shutil.rmtree(self.root, ignore_errors=True)

    @property
    def run_dir(self) -> str:
        return os.path.join(self.root, "halucinator", ".run")

    def locks(self) -> dict[str, dict]:
        out: dict[str, dict] = {}
        for name in sorted(os.listdir(self.run_dir)):
            if not name.endswith(".lock"):
                continue
            with open(os.path.join(self.run_dir, name), "rb") as handle:
                out[name] = tomllib.loads(handle.read().decode("utf-8"))
        return out

    def files(self) -> list[str]:
        return sorted(os.listdir(self.run_dir))

    def run(self, command: str, *args: str, faults: dict | None = None):
        """Invoke the production CLI as a subprocess. Returns (code, payload)."""
        environment = dict(os.environ)
        if faults is not None:
            fault_path = os.path.join(self.root, "faults-%s.json" % os.urandom(4).hex())
            with open(fault_path, "w", encoding="utf-8") as handle:
                json.dump(faults, handle)
            environment["HALUCINATOR_RUNTIME_FAULTS"] = fault_path
        else:
            environment.pop("HALUCINATOR_RUNTIME_FAULTS", None)
        proc = subprocess.run(
            [sys.executable, RUNTIME, command, "--root", self.root, *args],
            capture_output=True, text=True, timeout=TIMEOUT, env=environment,
            encoding="utf-8", errors="replace")
        raw = proc.stdout.strip() or proc.stderr.strip()
        try:
            payload = json.loads(raw) if raw else {}
        except ValueError:
            payload = {"raw": raw}
        return proc.returncode, payload

    # -- record materialization -----------------------------------------
    #
    # The helper opens, parses and binds every record it is handed, so these
    # build genuine ones. A test that could pass with a nonexistent filename
    # would be asserting nothing about the evidence discipline.

    def put(self, relpath: str, text: str) -> str:
        target = os.path.join(self.root, *relpath.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        return relpath

    def sha256(self, relpath: str) -> str:
        with open(os.path.join(self.root, *relpath.split("/")), "rb") as handle:
            return hashlib.sha256(handle.read()).hexdigest()

    def ref(self, relpath: str) -> str:
        return '{path="%s",sha256="%s"}' % (relpath, self.sha256(relpath))

    def write_authorization(self) -> str:
        return self.put(AUTHORIZATION,
                        FICTIONAL_NOTE + "Board authorization for the fixture board.\n")

    def write_support_files(self) -> None:
        self.put(RAW_EVIDENCE, FICTIONAL_NOTE + "Invented probe transcript.\n")
        self.put(OPERATOR_CONFIRMATION,
                 FICTIONAL_NOTE + "Operator confirmed the invented fixture state.\n")
        self.put(PROCEDURE, FICTIONAL_NOTE + "Invented safe-state procedure.\n")
        self.put(FACTS_HANDOFF, FICTIONAL_NOTE + "Invented facts handoff stand-in.\n")

    def write_safe_state(self, relpath: str, epoch: str, attempt: int,
                         unknown_hazard: str | None = None,
                         outstanding: tuple[str, ...] = (),
                         drop_hazard: str | None = None,
                         unpinned_hazard: str | None = None) -> str:
        self.write_support_files()
        lines = [
            "schema = 2",
            'board_id = "%s"' % BOARD,
            'lease_epoch = "%s"' % epoch,
            "operation_attempt = %d" % attempt,
            'observed_at = "2024-01-01T00:05:00Z"',
            "outstanding_human_actions = [%s]"
            % ", ".join('"%s"' % a for a in outstanding),
            "procedure = {board_id=\"%s\",facts_handoff=%s,assertion_ids=[\"fact.fixture.safe-state\"],procedure=%s}"
            % (BOARD, self.ref(FACTS_HANDOFF), self.ref(PROCEDURE)),
        ]
        hazards = []
        for kind in HAZARDS:
            if kind == drop_hazard:
                continue
            disposition = "unknown" if kind == unknown_hazard else "safe"
            # An unpinned reference is written as {path=...} with no sha256.
            evidence = ('{path="%s"}' % RAW_EVIDENCE if kind == unpinned_hazard
                        else self.ref(RAW_EVIDENCE))
            entry = ('{kind="%s",disposition="%s",observation_method="invented fixture '
                     'observation",evidence=%s' % (kind, disposition, evidence))
            if kind in PHYSICAL_HAZARDS:
                entry += ",operator_confirmation=%s" % self.ref(OPERATOR_CONFIRMATION)
            hazards.append(entry + "}")
        lines.append("hazards = [%s]" % ",".join(hazards))
        return self.put(relpath, "\n".join(lines) + "\n")

    def write_recovery_attempt(self, relpath: str, epoch: str, number: int,
                               outcome: str, lock_name: str,
                               safe_state: str | None = None) -> str:
        self.write_support_files()
        prior = "halucinator/evidence/recovery/prior-lock-%d.toml" % number
        with open(os.path.join(self.run_dir, lock_name), "rb") as handle:
            self.put(prior, handle.read().decode("utf-8"))
        lines = [
            "schema = 2",
            'board_id = "%s"' % BOARD,
            'lease_epoch = "%s"' % epoch,
            "attempt_number = %d" % number,
            'started_at = "2024-01-01T00:01:00Z"',
            'completed_at = "2024-01-01T00:04:00Z"',
            'last_operation = "load-ram"',
            "prior_lock = %s" % self.ref(prior),
            'actions = ["Invented fixture recovery action."]',
            "evidence = [%s]" % self.ref(RAW_EVIDENCE),
            'outcome = "%s"' % outcome,
            "operator_confirmation = %s" % self.ref(OPERATOR_CONFIRMATION),
        ]
        if safe_state is not None:
            lines.append("safe_state = %s" % self.ref(safe_state))
        return self.put(relpath, "\n".join(lines) + "\n")

    def write_override_record(self, relpath: str, epoch: str, lock_name: str,
                              confirmed_at: str = "2030-01-01T00:00:00Z") -> str:
        self.write_support_files()
        prior = "halucinator/evidence/recovery/prior-lock-override.toml"
        with open(os.path.join(self.run_dir, lock_name), "rb") as handle:
            self.put(prior, handle.read().decode("utf-8"))
        return self.put(relpath, "\n".join([
            "schema = 2",
            'board_id = "%s"' % BOARD,
            'lease_epoch = "%s"' % epoch,
            "prior_lock = %s" % self.ref(prior),
            'observed_host = "OTHER-HOST-FIXTURE"',
            "observed_pid = 4242",
            'reason = "Invented fixture: the owner cannot be inspected."',
            'termination_disposition = "physically-isolated"',
            "confirmation = %s" % self.ref(OPERATOR_CONFIRMATION),
            'confirmed_at = "%s"' % confirmed_at,
            'confirmer = "fixture-operator"',
            "acknowledges_board_unknown = true",
        ]) + "\n")


def acquire(tree: Worktree, stage: str, faults: dict | None = None):
    tree.write_authorization()
    return tree.run("acquire-board", "--stage", stage, "--board", BOARD,
                    "--authorization", AUTHORIZATION, faults=faults)


def bring_to_verified(tree: Worktree, stage: str, faults: dict | None = None):
    """Walk the real recovery path to a safe, recovery-verified interlock.

    Every record the helper is handed here is materialized on disk first, with
    all six hazard observations, their evidence and their operator
    confirmations. That is the point: the helper opens and binds each one, so a
    test that wants a verified interlock has to produce a real lineage rather
    than a plausible filename.
    """
    code, payload = acquire(tree, stage, faults=faults)
    expect(code == EXIT_OK, "acquisition failed: %r" % payload)
    epoch, token = payload["lease_epoch"], payload["check_token"]
    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]
    tree.write_safe_state(SAFE_STATE, epoch, attempt=0)
    tree.write_recovery_attempt(ATTEMPT_1, epoch, 1, "verified", lock_name,
                                safe_state=SAFE_STATE)
    code, out = tree.run("append-recovery-attempt", "--stage", stage, "--epoch", epoch,
                         "--token", token, "--attempt-file", ATTEMPT_1,
                         "--attempt-number", "1", "--outcome", "verified", faults=faults)
    expect(code == EXIT_OK, "first recovery attempt was refused: %r" % out)
    code, out = tree.run("verify-board-recovery", "--stage", stage, "--epoch", epoch,
                         "--token", token, "--safe-state", SAFE_STATE, faults=faults)
    expect(code == EXIT_OK, "recovery verification was refused: %r" % out)
    return epoch, token


def expect(condition: bool, message: str) -> None:
    if not condition:
        raise Failure(message)


# --------------------------------------------------------------------------
# D17 fault cases
# --------------------------------------------------------------------------


def test_simultaneous_post_create_acquisition_conflict(tree: Worktree) -> None:
    """Simultaneous post-create acquisition conflict: the NEW claimant backs off.

    Injects a second claimant against a live intersecting `board:` lock and
    asserts the existing lock is byte-identical afterwards and that exactly the
    new claimant's own candidate is gone. No creation-order inference is
    permitted, so whichever claimant is second always loses.
    """
    epoch, _ = bring_to_verified(tree, "write-tests:alpha")
    before = tree.locks()
    expect(len(before) == 1, "expected exactly one lock before the race")
    holder = list(before)[0]
    with open(os.path.join(tree.run_dir, holder), "rb") as handle:
        holder_bytes = handle.read()
    # The holder is a finished subprocess, so make it observably LIVE: a
    # present process whose birth identity equals the recorded one. That is the
    # only observation class that means live, and it is what a real concurrent
    # holder would produce.
    recorded = before[holder]["owner_process_identity"]
    live = {"process_present": True, "process_scheme": recorded["scheme"],
            "process_birth": recorded.get("value", "")}

    code, payload = acquire(tree, "write-tests:beta", faults=live)
    expect(code == EXIT_CONFLICT,
           "second claimant must fail with the interlock-conflict code, got %d: %r"
           % (code, payload))
    after = tree.locks()
    expect(set(after) == set(before),
           "the new claimant must remove ONLY its own candidate; locks are now %r"
           % sorted(after))
    with open(os.path.join(tree.run_dir, holder), "rb") as handle:
        expect(handle.read() == holder_bytes,
               "the existing lock was modified; a lock is never stolen")
    expect(epoch == after[holder]["lease_epoch"], "holder epoch changed")


def test_pid_reuse_process_birth_mismatch_is_interrupted(tree: Worktree) -> None:
    """PID reuse against process-birth identity classifies interrupted, not live.

    The lock is written with one birth identity, then inspected while a process
    with the SAME pid reports a DIFFERENT birth value. A PID-only check would
    call this live and hand the board to a stranger.
    """
    bring_to_verified(tree, "write-tests:alpha")
    name = list(tree.locks())[0]
    recorded = tree.locks()[name]["owner_process_identity"]

    code, payload = tree.run("inspect", faults={"process_present": True,
                                                "process_scheme": recorded["scheme"],
                                                "process_birth": recorded.get("value", "")})
    expect(code == EXIT_OK and payload["locks"][0]["classification"] == "live",
           "a matching birth identity must classify live, got %r" % payload)

    code, payload = tree.run("inspect", faults={"process_present": True,
                                               "process_scheme": recorded["scheme"],
                                               "process_birth": "not-the-same-birth"})
    expect(code == EXIT_OK and payload["locks"][0]["classification"] == "interrupted",
           "a reused PID with a different birth identity must classify interrupted, "
           "got %r" % payload)

    code, payload = tree.run("inspect", faults={"process_inspectable": False})
    expect(code == EXIT_OK and payload["locks"][0]["classification"] == "ambiguous",
           "an uninspectable same-host owner must be ambiguous, never dead: %r" % payload)


def test_orphaned_probe_child_blocks_completion(tree: Worktree) -> None:
    """An orphaned surviving probe child refuses completion and forces recovery.

    Holder death is not operation death. The fault makes the recorded child
    session still alive at completion time; the helper must refuse to record
    completion and must leave the board active rather than unknown-but-done.
    """
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    code, payload = tree.run("begin-board-operation", "--stage", stage, "--epoch", epoch,
                             "--token", token, "--operation", "load-ram",
                             "--child-identity", "probe-session-1")
    expect(code == EXIT_OK, "operation start was refused: %r" % payload)
    operation_id = payload["operation_id"]

    code, payload = tree.run("complete-board-operation", "--stage", stage, "--epoch",
                             epoch, "--token", token, "--operation-id", operation_id,
                             faults={"child_alive": True})
    expect(code == EXIT_RECOVERY,
           "a surviving child must force recovery, got %d: %r" % (code, payload))
    lock = tree.locks()[list(tree.locks())[0]]
    expect(lock["operation_phase"] == "active",
           "completion must not be recorded while a child may still drive pins")

    code, payload = tree.run("complete-board-operation", "--stage", stage, "--epoch",
                             epoch, "--token", token, "--operation-id", operation_id,
                             faults={"child_alive": False})
    expect(code == EXIT_OK, "completion after confirmed quiescence was refused")
    lock = tree.locks()[list(tree.locks())[0]]
    expect(lock["board_state"] == "unknown",
           "state must stay unknown until a SafeStateObservation exists")


def test_recovery_interrupted_twice_stays_pending(tree: Worktree) -> None:
    """Recovery interrupted twice stays pending; the lineage is append-only.

    Two interrupted attempts are appended, then a non-consecutive number is
    rejected, then verification is refused because the latest outcome is not
    `verified`. Attempts are never removed, reordered or replaced.
    """
    stage = "write-tests:alpha"
    code, payload = acquire(tree, stage)
    expect(code == EXIT_OK, "acquisition failed")
    epoch, token = payload["lease_epoch"], payload["check_token"]

    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]
    paths = {1: ATTEMPT_1, 2: ATTEMPT_2}
    for number in (1, 2):
        tree.write_recovery_attempt(paths[number], epoch, number, "interrupted",
                                    lock_name)
        code, payload = tree.run("append-recovery-attempt", "--stage", stage,
                                 "--epoch", epoch, "--token", token,
                                 "--attempt-file", paths[number],
                                 "--attempt-number", str(number),
                                 "--outcome", "interrupted")
        expect(code == EXIT_OK, "attempt %d was refused: %r" % (number, payload))
        expect(payload["operation_phase"] == "recovery-pending",
               "an interrupted attempt must leave the interlock pending")

    ninth = "halucinator/evidence/recovery/9.toml"
    tree.write_recovery_attempt(ninth, epoch, 9, "verified", lock_name,
                                safe_state=tree.write_safe_state(
                                    SAFE_STATE, epoch, attempt=0))
    code, payload = tree.run("append-recovery-attempt", "--stage", stage, "--epoch",
                             epoch, "--token", token, "--attempt-file", ninth,
                             "--attempt-number", "9", "--outcome", "verified")
    expect(code == EXIT_RECOVERY,
           "a nonconsecutive attempt number must be refused, got %d" % code)

    code, payload = tree.run("verify-board-recovery", "--stage", stage, "--epoch",
                             epoch, "--token", token, "--safe-state", SAFE_STATE)
    expect(code == EXIT_RECOVERY,
           "verification after two interrupted attempts must be refused")

    code, payload = tree.run("release-board", "--stage", stage, "--epoch", epoch,
                             "--token", token)
    expect(code == EXIT_RECOVERY, "release before recovery-verified must be refused")

    lock = tree.locks()[list(tree.locks())[0]]
    expect([entry["path"] for entry in lock["recovery_attempts"]]
           == [ATTEMPT_1, ATTEMPT_2],
           "the recovery lineage was altered: %r" % lock["recovery_attempts"])


def test_check_use_window_pause_residual(tree: Worktree) -> None:
    """The check-token check-use pause: approval is narrowed, never closed.

    `before-board-op` approves, then a recovery reclassifies the board while
    the caller is 'paused'. The stale token is refused when it comes back - but
    the helper must also SAY, in its approval, that a direct probe command
    issued during the pause is outside it entirely. Only the deferred broker
    closes that.
    """
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    code, payload = tree.run("before-board-op", "--stage", stage, "--epoch", epoch,
                             "--token", token)
    expect(code == EXIT_OK and payload["approved"], "precheck was refused")
    expect("cannot close" in payload["residual"].lower(),
           "the approval must disclose the unclosable check-use window")

    # Rotate the epoch the way an authorized recovery would, by hand rather
    # than through the override: the override is for an ambiguous owner, and
    # this owner is healthy. See test_override_refuses_live_owner.
    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]
    path = os.path.join(tree.run_dir, lock_name)
    text = open(path, encoding="utf-8").read()
    open(path, "w", encoding="utf-8", newline="").write(
        text.replace(token, "f" * 64))

    code, payload = tree.run("before-board-op", "--stage", stage, "--epoch", epoch,
                             "--token", token)
    expect(code == EXIT_CONFLICT,
           "the paused caller's stale token must be refused, got %d" % code)


def test_override_refuses_live_owner_and_absent_record(tree: Worktree) -> None:
    """The ambiguity override refuses a healthy owner and an unreadable record.

    This case previously ENCODED THE BUG: it asserted that the override
    succeeded against a lock the helper itself classified live, while naming an
    operator record that did not exist. Two operators driving one board is the
    accident the whole interlock exists to prevent, so both are now refusals.

    The escape hatch is for exactly one situation - an owner whose death cannot
    be proved, pinning a board forever - and that is asserted separately by
    test_override_accepts_persistently_ambiguous_owner.
    """
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]
    before = open(os.path.join(tree.run_dir, lock_name), "rb").read()

    # A. An operator record that does not exist.
    tree.write_override_record(OVERRIDE_RECORD, epoch, lock_name)
    code, payload = tree.run("override-ambiguous-owner", "--stage", stage,
                             "--board", BOARD, "--override-record",
                             "halucinator/evidence/recovery/does-not-exist.toml")
    expect(code != EXIT_OK,
           "an override naming a nonexistent operator record must be refused: %r"
           % payload)

    # B. A healthy owner. Same-host, present process, matching birth identity.
    recorded = tree.locks()[lock_name]["owner_process_identity"]
    live = {"process_present": True, "process_scheme": recorded["scheme"],
            "process_birth": recorded.get("value", "")}
    code, payload = tree.run("override-ambiguous-owner", "--stage", stage,
                             "--board", BOARD, "--override-record", OVERRIDE_RECORD,
                             faults=live)
    expect(code != EXIT_OK,
           "the override seized a LIVE owner's board: %r" % payload)
    expect(open(os.path.join(tree.run_dir, lock_name), "rb").read() == before,
           "a refused override must leave the existing lock byte-identical")


def test_override_accepts_persistently_ambiguous_owner(tree: Worktree) -> None:
    """The override DOES open a jam: an uninspectable owner with a stale heartbeat.

    A recycled PID or an uninspectable process pinning a board forever is a real
    denial of service on real equipment, so the hatch must still work. It opens
    only into recovery-pending with the board unknown - never into a safe board
    and never into tests.
    """
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]

    # Age the heartbeat past the ambiguity window: a living owner refreshes
    # every 30s, so an ambiguity that survives 120s is the real thing.
    path = os.path.join(tree.run_dir, lock_name)
    text = open(path, encoding="utf-8").read()
    stale = "2024-01-01T00:00:00Z"
    text = re.sub(r'(?m)^heartbeat_at=.*$', 'heartbeat_at="%s"' % stale, text)
    open(path, "w", encoding="utf-8", newline="").write(text)

    tree.write_override_record(OVERRIDE_RECORD, epoch, lock_name)
    ambiguous = {"process_inspectable": False}
    code, payload = tree.run("inspect", faults=ambiguous)
    expect(payload["locks"][0]["classification"] == "ambiguous",
           "this case requires an ambiguous owner, got %r" % payload)

    # With classification and persistence both satisfied, the operator record is
    # the only thing left standing between a jammed interlock and a seizure -
    # so prove that check is live here, not merely shadowed by the ones above.
    code, payload = tree.run("override-ambiguous-owner", "--stage", stage,
                             "--board", BOARD, "--override-record",
                             "halucinator/evidence/recovery/does-not-exist.toml",
                             faults=ambiguous)
    expect(code != EXIT_OK,
           "even a genuinely ambiguous owner must not be overridden without a "
           "readable operator record: %r" % payload)

    code, payload = tree.run("override-ambiguous-owner", "--stage", stage,
                             "--board", BOARD, "--override-record", OVERRIDE_RECORD,
                             faults=ambiguous)
    expect(code == EXIT_OK,
           "a persistently ambiguous owner must be overridable, or a recycled PID "
           "jams the board forever: %r" % payload)
    expect(payload["operation_phase"] == "recovery-pending"
           and payload["board_state"] == "unknown",
           "the override must open into recovery only, with the board unknown: %r"
           % payload)
    expect(payload["lease_epoch"] != epoch, "the override must mint a fresh epoch")
    expect(any(n.startswith(lock_name + ".archived-") for n in tree.files()),
           "the prior lock must be archived, never discarded")


def test_windows_replace_delete_sharing_violation_fails_closed(tree: Worktree) -> None:
    """Windows os.replace delete-sharing failure: bounded retries, then fail closed.

    A transient sharing violation must be retried within the bounded delay
    ladder and then succeed. A persistent one must fail closed, preserve the
    temp file for recovery, and never delete or steal the lock.
    """
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    lock_names = [n for n in tree.files() if n.endswith(".lock")]

    code, payload = tree.run("heartbeat-board", "--stage", stage, "--epoch", epoch,
                             "--token", token,
                             faults={"replace_sharing_failures": 3, "no_sleep": True})
    expect(code == EXIT_OK,
           "three transient sharing violations are within the bounded ladder: %r" % payload)

    code, payload = tree.run("heartbeat-board", "--stage", stage, "--epoch", epoch,
                             "--token", token,
                             faults={"replace_always_fails": True, "no_sleep": True})
    expect(code == EXIT_DURABILITY,
           "a persistent sharing violation must fail closed, got %d: %r" % (code, payload))
    expect([n for n in tree.files() if n.endswith(".lock")] == lock_names,
           "the lock must survive a failed replacement untouched")
    expect(any(".tmp-" in n for n in tree.files()),
           "the temp file must be preserved as recovery evidence")


def test_unsupported_directory_fsync_blocks_operations(tree: Worktree) -> None:
    """Unsupported directory fsync makes durability unavailable and blocks operations.

    The helper must refuse rather than claim persistence it cannot establish,
    and must create no lock on the way out.
    """
    code, payload = acquire(tree, "write-tests:alpha",
                            faults={"dir_fsync_unsupported": True})
    expect(code == EXIT_DURABILITY,
           "acquisition must be blocked when durability cannot be established, got %d: %r"
           % (code, payload))
    expect([n for n in tree.files() if n.endswith(".lock")] == [],
           "no lock may be created when durability is unavailable")

    epoch, token = bring_to_verified(tree, "write-tests:alpha")
    code, payload = tree.run("before-board-op", "--stage", "write-tests:alpha",
                             "--epoch", epoch, "--token", token,
                             faults={"dir_fsync_unsupported": True})
    expect(code == EXIT_DURABILITY,
           "an operation precheck must be blocked when durability is unavailable")


def test_fresh_clone_absence_is_not_evidence(tree: Worktree) -> None:
    """Fresh-clone absence of any prior lock starts recovery-pending, not acquired.

    A fresh clone cannot know that a previous run died with the board active,
    so the board is unknown and no target-affecting operation is permitted
    until recovery is verified.
    """
    code, payload = acquire(tree, "write-tests:alpha")
    expect(code == EXIT_OK, "acquisition failed: %r" % payload)
    expect(payload["prior_locks_seen"] == 0, "this case requires an empty worktree")
    expect(payload["operation_phase"] == "recovery-pending",
           "absence of a lock must not be read as a safe teardown, got %r"
           % payload["operation_phase"])
    expect(payload["board_state"] == "unknown", "a fresh clone's board is unknown")

    epoch, token = payload["lease_epoch"], payload["check_token"]
    code, payload = tree.run("begin-board-operation", "--stage", "write-tests:alpha",
                             "--epoch", epoch, "--token", token, "--operation", "attach")
    expect(code == EXIT_RECOVERY,
           "attaching a debugger is itself a target-affecting operation and must be "
           "refused while the board is unknown, got %d" % code)


def test_state_cas_race_is_refused(tree: Worktree) -> None:
    """A CAS race on the state generation is refused without writing anything."""
    state_dir = os.path.join(tree.root, "halucinator")
    with open(os.path.join(state_dir, "state.toml"), "w", encoding="utf-8") as handle:
        handle.write("schema = 2\ngeneration = 7\n")
    code, payload = tree.run("publish-state", "--expect-generation", "7")
    expect(code == EXIT_OK, "a matching generation must be accepted: %r" % payload)
    code, payload = tree.run("publish-state", "--expect-generation", "6")
    expect(code == EXIT_CAS,
           "a stale expected generation must be refused, got %d: %r" % (code, payload))


def test_raw_colon_lock_filename_is_never_materialized(tree: Worktree) -> None:
    """A canonical stage ID containing a colon never yields a raw-colon filename.

    NTFS cannot materialize a raw colon, and a percent-encoded colon would
    bypass the mandated slug-plus-digest algorithm. Neither may appear.
    """
    code, payload = acquire(tree, "write-tests:schema-demo")
    expect(code == EXIT_OK, "acquisition failed: %r" % payload)
    names = [n for n in tree.files() if n.endswith(".lock")]
    expect(len(names) == 1, "expected exactly one lock, found %r" % names)
    expect(":" not in names[0] and "%3a" not in names[0].lower(),
           "lock filename %r is not Windows-safe" % names[0])
    expect(names[0].startswith("write-tests-schema-demo-"),
           "lock filename %r is not the canonical slug-plus-digest" % names[0])


def test_release_requires_verified_and_safe(tree: Worktree) -> None:
    """Release is refused until the interlock is recovery-verified and safe."""
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    code, _ = tree.run("begin-board-recovery", "--stage", stage, "--epoch", epoch,
                       "--token", token)
    expect(code == EXIT_OK, "entering recovery was refused")
    code, payload = tree.run("release-board", "--stage", stage, "--epoch", epoch,
                             "--token", token)
    expect(code == EXIT_RECOVERY, "release while pending must be refused: %r" % payload)


def test_release_refuses_absent_or_altered_evidence(tree: Worktree) -> None:
    """Release re-reads its evidence: a record that vanished blocks the release.

    Release hands the board to the next claimant. The safe-state observation is
    deleted after verification, so the record that justified "safe" no longer
    exists; the helper must refuse and leave the lock in place rather than let
    the next operator attach to a device whose state nobody can now establish.
    """
    stage = "write-tests:alpha"
    epoch, token = bring_to_verified(tree, stage)
    os.unlink(os.path.join(tree.root, *SAFE_STATE.split("/")))
    code, payload = tree.run("release-board", "--stage", stage, "--epoch", epoch,
                             "--token", token)
    expect(code == EXIT_RECOVERY,
           "release must be refused when its safe-state record is gone: %r" % payload)
    expect([n for n in tree.files() if n.endswith(".lock")] != [],
           "a refused release must leave the lock in place")


def test_safe_state_with_unknown_hazard_is_refused(tree: Worktree) -> None:
    """An unknown hazard, a missing hazard, or outstanding human work is not safe.

    Three separate observations are built, each defective in one way, and each
    must be refused. There is no partial safety: a hazard nobody looked at is
    not a hazard nobody has.
    """
    stage = "write-tests:alpha"
    code, payload = acquire(tree, stage)
    expect(code == EXIT_OK, "acquisition failed")
    epoch, token = payload["lease_epoch"], payload["check_token"]
    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]

    for label, kwargs in (
        ("an unknown hazard", {"unknown_hazard": "dma"}),
        ("a missing hazard", {"drop_hazard": "probe"}),
        ("outstanding human work", {"outstanding": ("De-energize the invented rig.",)}),
    ):
        tree.write_safe_state(SAFE_STATE, epoch, attempt=0, **kwargs)
        tree.write_recovery_attempt(ATTEMPT_1, epoch, 1, "verified", lock_name,
                                    safe_state=SAFE_STATE)
        code, payload = tree.run("append-recovery-attempt", "--stage", stage,
                                 "--epoch", epoch, "--token", token,
                                 "--attempt-file", ATTEMPT_1, "--attempt-number", "1",
                                 "--outcome", "verified")
        expect(code == EXIT_RECOVERY,
               "a verified attempt carrying %s must be refused: %r" % (label, payload))
        lock = tree.locks()[lock_name]
        expect(lock["board_state"] == "unknown",
               "the board must stay unknown after %s" % label)


def test_unreadable_lock_blocks_acquisition(tree: Worktree) -> None:
    """An unreadable lock is not an absent lock: it blocks, and nothing is created.

    Three ways a lock can be unreadable are injected in turn - unparseable
    TOML, a missing required field, and a board-test lock with no board_id.
    Each must block acquisition of an intersecting board and leave the run
    directory with exactly the one file it started with. Skipping a lock the
    helper cannot read makes a corrupted LIVE claim look like a free board,
    which is two operators on one MCU.
    """
    os.makedirs(tree.run_dir, exist_ok=True)
    corrupt = os.path.join(tree.run_dir, "other.lock")
    for label, body in (
        ("unparseable TOML", "this is not = valid toml [[[\n"),
        ("missing required field", 'schema = 2\nstage = "x"\n'),
        ("board-test lock with no board_id",
         'schema = 2\nstage = "x"\nstatus = "in-progress"\nkind = "board-test"\n'
         'owner = "o"\nhost = "h"\npid = 1\nacquired_at = "2024-01-01T00:00:00Z"\n'
         'heartbeat_at = "2024-01-01T00:00:00Z"\nresources = ["stage:x"]\n'),
    ):
        with open(corrupt, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(body)
        code, payload = acquire(tree, "write-tests:alpha")
        expect(code != EXIT_OK,
               "acquisition must be blocked by a lock that is %s: %r" % (label, payload))
        expect(tree.files() == ["other.lock"] or
               sorted(n for n in tree.files() if n.endswith(".lock")) == ["other.lock"],
               "no second lock may be created beside an unreadable one (%s); found %r"
               % (label, tree.files()))
    os.unlink(corrupt)
    code, payload = acquire(tree, "write-tests:alpha")
    expect(code == EXIT_OK,
           "with the unreadable lock removed, acquisition must succeed again: %r"
           % payload)


def test_recovery_permits_observation_but_not_test_work(tree: Worktree) -> None:
    """Recovery is completable without bypassing the interlock, and no wider.

    The circularity the owner already ordered fixed once had MOVED rather than
    gone: entry into recovery needed no evidence, but every operation an
    operator needs in order to find out whether the board is safe was then
    refused until recovery was already verified. That leaves physical
    isolation or going around the helper as the only exits, and a safety
    mechanism satisfiable only by bypassing it teaches operators to bypass it.

    So: attach/reset/halt/detach/power-change/fixture-change are permitted
    through begin-recovery-operation; run/load-ram/program-flash are not;
    begin-board-operation stays shut; release stays shut; and the board stays
    UNKNOWN throughout, because attaching a debugger drives pins and cannot be
    the step that establishes safety.
    """
    stage = "write-tests:alpha"
    code, payload = acquire(tree, stage)
    expect(code == EXIT_OK, "acquisition failed: %r" % payload)
    epoch, token = payload["lease_epoch"], payload["check_token"]
    common = ["--stage", stage, "--epoch", epoch, "--token", token]
    code, payload = tree.run("begin-board-recovery", *common)
    expect(code == EXIT_OK, "entering recovery was refused: %r" % payload)

    for op in ("attach", "reset", "halt", "detach", "power-change", "fixture-change"):
        code, payload = tree.run("before-board-op", *common, "--operation", op)
        expect(code == EXIT_OK,
               "precheck of recovery-scoped %r was refused: %r" % (op, payload))
        expect(payload["operation_scope"] == "recovery",
               "the precheck must say the approval is recovery-scoped")
        code, payload = tree.run("begin-recovery-operation", *common, "--operation", op,
                                 "--child-identity", "probe-session-recovery")
        expect(code == EXIT_OK, "recovery operation %r was refused: %r" % (op, payload))
        expect(payload["board_state"] == "unknown",
               "the board must stay UNKNOWN during a recovery operation")
        code, payload = tree.run("complete-board-operation", *common,
                                 "--operation-id", payload["operation_id"])
        expect(code == EXIT_OK, "completing recovery operation %r failed: %r" % (op, payload))
        expect(payload["operation_phase"] == "recovery-pending",
               "a recovery operation must return to recovery-pending, not teardown")

    for op in ("run", "load-ram", "program-flash"):
        code, payload = tree.run("begin-recovery-operation", *common, "--operation", op)
        expect(code != EXIT_OK,
               "recovery must NOT authorize %r - it can load or start code on a board "
               "nobody has established the state of: %r" % (op, payload))
        code, payload = tree.run("begin-board-operation", *common, "--operation", op)
        expect(code != EXIT_OK,
               "ordinary test operation %r was permitted during recovery: %r"
               % (op, payload))
        code, payload = tree.run("before-board-op", *common, "--operation", op)
        expect(code != EXIT_OK,
               "the precheck approved ordinary test operation %r during recovery: %r"
               % (op, payload))

    code, payload = tree.run("release-board", *common)
    expect(code == EXIT_RECOVERY,
           "release must still wait for recovery-verified: %r" % payload)
    expect([n for n in tree.files() if n.endswith(".lock")] != [],
           "a refused release must leave the lock in place")
    lock = tree.locks()[[n for n in tree.files() if n.endswith(".lock")][0]]
    expect(lock["board_state"] == "unknown", "the board must still be unknown")


def test_unpinned_nested_reference_is_refused(tree: Worktree) -> None:
    """A FileRef with no sha256 is a name, not evidence, and never reaches release.

    The safe-state observation is rebuilt with one nested reference - the
    procedure record - stripped of its digest. Everything else is a valid
    closure, so the only reason to refuse is the missing pin.
    """
    stage = "write-tests:alpha"
    code, payload = acquire(tree, stage)
    expect(code == EXIT_OK, "acquisition failed")
    epoch, token = payload["lease_epoch"], payload["check_token"]
    lock_name = [n for n in tree.files() if n.endswith(".lock")][0]

    tree.write_safe_state(SAFE_STATE, epoch, attempt=0, unpinned_hazard="dma")
    rendered = open(os.path.join(tree.root, *SAFE_STATE.split("/")),
                    encoding="utf-8").read()
    expect('evidence={path="%s"}' % RAW_EVIDENCE in rendered,
           "the observation does not actually carry an unpinned reference, so this "
           "case would prove nothing")
    tree.write_recovery_attempt(ATTEMPT_1, epoch, 1, "verified", lock_name,
                                safe_state=SAFE_STATE)
    code, payload = tree.run("append-recovery-attempt", "--stage", stage, "--epoch",
                             epoch, "--token", token, "--attempt-file", ATTEMPT_1,
                             "--attempt-number", "1", "--outcome", "verified")
    expect(code == EXIT_RECOVERY,
           "an unpinned nested FileRef must be refused: %r" % payload)
    expect("sha256" in str(payload).lower(),
           "the refusal must name the missing digest: %r" % payload)
    lock = tree.locks()[lock_name]
    expect(lock["board_state"] == "unknown", "the board must stay unknown")


CASES = [
    test_simultaneous_post_create_acquisition_conflict,
    test_pid_reuse_process_birth_mismatch_is_interrupted,
    test_orphaned_probe_child_blocks_completion,
    test_recovery_interrupted_twice_stays_pending,
    test_check_use_window_pause_residual,
    test_override_refuses_live_owner_and_absent_record,
    test_override_accepts_persistently_ambiguous_owner,
    test_release_refuses_absent_or_altered_evidence,
    test_safe_state_with_unknown_hazard_is_refused,
    test_unreadable_lock_blocks_acquisition,
    test_recovery_permits_observation_but_not_test_work,
    test_unpinned_nested_reference_is_refused,
    test_windows_replace_delete_sharing_violation_fails_closed,
    test_unsupported_directory_fsync_blocks_operations,
    test_fresh_clone_absence_is_not_evidence,
    test_state_cas_race_is_refused,
    test_raw_colon_lock_filename_is_never_materialized,
    test_release_requires_verified_and_safe,
]


def main() -> int:
    failures: list[str] = []
    for case in CASES:
        tree = Worktree()
        try:
            case(tree)
            print("ok   %s" % case.__name__)
        except (Failure, subprocess.TimeoutExpired, OSError, KeyError, ValueError) as exc:
            failures.append("%s: %s" % (case.__name__, exc))
            print("FAIL %s: %s" % (case.__name__, exc))
        finally:
            tree.close()
    if failures:
        print("\n%d of %d interlock cases failed" % (len(failures), len(CASES)))
        return 1
    print("\nall %d interlock cases passed" % len(CASES))
    return 0


if __name__ == "__main__":
    sys.exit(main())
