#!/usr/bin/env python3
"""Worktree-local, single-operator board interlock for halucinator.

What this is
------------
A **worktree-local, single-operator interlock**. It is a strong default and a
statement of intent, **not a sandbox**. It does not exclude another clone,
another worktree, or another operator, and a direct probe or programmer command
bypasses it entirely. It is not a lease, not a broker, and `check_token` is not
physical fencing.

What it cannot close
--------------------
* **The check-use window.** `before-board-op` narrows the window between an
  epoch check and the operation that relies on it; it cannot close it. A holder
  can pass the check, pause, lose or override its epoch, and then resume a
  direct command. Only the deferred broker (TODO F15) closes this.
* **Cross-clone and concurrent-operator exclusion** (TODO F16/F17). A fresh
  clone cannot know that a previous run died with the board active, which is
  why acquisition in an empty worktree starts in `recovery-pending`, never
  `acquired`: absence of a lock is not evidence of safe teardown.
* **Physical truth.** Every record here can be complete and still false.

**Holder death is not operation death.** A probe or runner child may still be
transferring or driving pins after its parent has gone. Recovery therefore
declares device state unknown *before* reconnecting - attaching a debugger is
itself a target-affecting operation - and refuses to proceed until the operator
confirms child termination and quiescence, or physically isolates board and
probe.

Standard library only. Python 3.11+.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import re
import secrets
import sys
import time
import tomllib
from datetime import datetime, timezone

EXIT_OK = 0
EXIT_USAGE = 2
EXIT_DURABILITY = 3
EXIT_CONFLICT = 4
EXIT_RECOVERY = 5
EXIT_CAS = 6

SCHEMA = 2
HEARTBEAT_AMBIGUOUS_SECONDS = 120
REPLACE_RETRY_DELAYS_MS = (50, 100, 200, 400)
MAX_SCAN_FILES = 4096

# The lock vocabulary is DEFINED in validate.py's LOCK_SCHEMA and imported
# here. Restating it was how this helper came to write `recovery-active` and
# `operation_scope` into a lock that its own static validator then rejected
# with MALFORMED_LOCK: two spellings of one enum, neither authoritative. The
# schema is authoritative; this file reads it.
_SCHEMA_MODULE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                   "validate.py")


def _load_lock_schema_module():
    spec = importlib.util.spec_from_file_location("halucinator_lock_schema",
                                                  _SCHEMA_MODULE_PATH)
    if spec is None or spec.loader is None:
        raise Refusal(EXIT_USAGE,
                      "cannot load the lock schema from %r; the helper refuses to "
                      "write a lock whose vocabulary it cannot check against the "
                      "validator" % _SCHEMA_MODULE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_SCHEMA = _load_lock_schema_module()

PHASES = _SCHEMA.LOCK_OPERATION_PHASES
OPERATIONS = _SCHEMA.LOCK_OPERATIONS
OPERATION_SCOPES = _SCHEMA.LOCK_OPERATION_SCOPES

# Operations an OPERATOR NEEDS in order to find out whether a board is safe.
# Recovery has to be completable without bypassing the helper: if every target
# operation is refused until recovery is already verified, the only ways out
# are physically isolating every fixture or going around the interlock - and a
# safety mechanism whose documented path can only be completed by going around
# it is worse than none, because it teaches operators to go around it.
#
# This list is deliberately short and deliberately NOT the operation set. It
# carries no way to put code on the target or start it running.
RECOVERY_SCOPED_OPERATIONS = ("attach", "reset", "halt", "detach",
                              "power-change", "fixture-change")

FAULT_ENV = "HALUCINATOR_RUNTIME_FAULTS"


class Refusal(Exception):
    """A refusal with an exit code. Every refusal is fail-closed."""

    def __init__(self, code: int, message: str) -> None:
        super().__init__(message)
        self.code = code


# --------------------------------------------------------------------------
# Adapters
#
# Clock, process-inspection and filesystem behaviour are reached only through
# these seams so the D17 fault suite can drive the PRODUCTION code paths. The
# seam is an environment-named JSON file, never a CLI option: a fault must not
# be reachable from an ordinary invocation.
# --------------------------------------------------------------------------


class Adapters:
    def __init__(self, spec: dict | None = None) -> None:
        self.spec = spec or {}

    @classmethod
    def from_environment(cls) -> "Adapters":
        path = os.environ.get(FAULT_ENV)
        if not path:
            return cls({})
        try:
            with open(path, "rb") as handle:
                return cls(json.loads(handle.read().decode("utf-8")))
        except (OSError, ValueError) as exc:
            raise Refusal(EXIT_USAGE, "fault adapter file %r is unusable: %s" % (path, exc))

    # -- clock ----------------------------------------------------------
    def now(self) -> datetime:
        override = self.spec.get("now")
        if isinstance(override, str):
            return parse_rfc3339(override)
        return datetime.now(timezone.utc)

    # -- identity -------------------------------------------------------
    def host(self) -> str:
        override = self.spec.get("host")
        return override if isinstance(override, str) else os.environ.get("COMPUTERNAME") or "localhost"

    def process_birth(self, pid: int) -> tuple[str, str | None]:
        """(scheme, value). value None means the process is absent.

        `scheme="unavailable"` means identity could not be inspected at all,
        which makes same-host ownership AMBIGUOUS rather than dead.
        """
        if "process_inspectable" in self.spec and not self.spec["process_inspectable"]:
            return ("unavailable", "")
        if "process_present" in self.spec:
            if not self.spec["process_present"]:
                return (self.spec.get("process_scheme", "windows-filetime"), None)
            return (self.spec.get("process_scheme", "windows-filetime"),
                    str(self.spec.get("process_birth", "")))
        return native_process_birth(pid)

    def child_alive(self) -> bool:
        """Whether a recorded probe/runner child may still be running."""
        return bool(self.spec.get("child_alive", False))

    # -- filesystem -----------------------------------------------------
    def directory_fsync_supported(self, directory: str) -> bool:
        if "dir_fsync_unsupported" in self.spec:
            return not self.spec["dir_fsync_unsupported"]
        return native_directory_fsync(directory)

    def replace_failures(self) -> int:
        """How many transient sharing violations os.replace should raise."""
        value = self.spec.get("replace_sharing_failures", 0)
        return int(value) if isinstance(value, (int, float)) else 0

    def replace_always_fails(self) -> bool:
        return bool(self.spec.get("replace_always_fails", False))

    def sleep(self, seconds: float) -> None:
        if self.spec.get("no_sleep"):
            return
        time.sleep(seconds)


def native_process_birth(pid: int) -> tuple[str, str | None]:
    """Process-birth identity, so a reused PID cannot pass as the same owner."""
    if sys.platform == "win32":
        try:
            import ctypes
            from ctypes import wintypes
        except Exception:
            return ("unavailable", "")
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
        if not handle:
            return ("windows-filetime", None)
        try:
            creation = wintypes.FILETIME()
            exit_time = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            ok = kernel32.GetProcessTimes(
                handle, ctypes.byref(creation), ctypes.byref(exit_time),
                ctypes.byref(kernel_time), ctypes.byref(user_time))
            if not ok:
                return ("unavailable", "")
            return ("windows-filetime",
                    "%d" % ((creation.dwHighDateTime << 32) | creation.dwLowDateTime))
        finally:
            kernel32.CloseHandle(handle)
    if sys.platform.startswith("linux"):
        try:
            with open("/proc/%d/stat" % pid, "rb") as handle:
                raw = handle.read().decode("utf-8", "replace")
        except FileNotFoundError:
            return ("linux-startticks", None)
        except OSError:
            return ("unavailable", "")
        tail = raw.rpartition(")")[2].split()
        # Field 22 of /proc/pid/stat overall; index 19 after comm.
        if len(tail) < 20:
            return ("unavailable", "")
        return ("linux-startticks", tail[19])
    return ("unavailable", "")


def native_directory_fsync(directory: str) -> bool:
    """Probe whether this directory can give us durable metadata ordering.

    **Platform asymmetry, stated rather than hidden.** On POSIX the probe is
    the literal `fsync` of a directory file descriptor the specification names.
    Windows exposes no directory-flush primitive through the standard library
    at all, so the literal probe would fail on *every* Windows path and block
    *every* Windows operator - a universal denial of service that is a property
    of the platform, not of the filesystem, and is not the fail-closed behavior
    intended. The specification's remedy, "select a supported local
    filesystem", is a filesystem-level instruction.

    On Windows the probe is therefore the operation actually relied upon: an
    exclusive create, a `FlushFileBuffers` via `os.fsync` on the file handle,
    and a same-volume `os.replace` in this exact directory. That is a
    **weaker** guarantee than a POSIX directory flush - NTFS metadata ordering
    rather than an explicit barrier - and it is recorded here as such. A
    directory that cannot complete the probe (read-only, denied, exotic mount)
    still fails closed, which is the case the gate exists for.
    """
    if sys.platform == "win32":
        probe = os.path.join(directory, ".durability-probe-%s" % secrets.token_hex(4))
        target = probe + ".final"
        try:
            flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
            fd = os.open(probe, flags, 0o644)
            with os.fdopen(fd, "wb") as handle:
                handle.write(b"probe\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(probe, target)
            os.unlink(target)
            return True
        except OSError:
            for leftover in (probe, target):
                try:
                    os.unlink(leftover)
                except OSError:
                    pass
            return False
    try:
        fd = os.open(directory, getattr(os, "O_DIRECTORY", os.O_RDONLY))
    except OSError:
        return False
    try:
        os.fsync(fd)
        return True
    except OSError:
        return False
    finally:
        os.close(fd)


# --------------------------------------------------------------------------
# Time helpers
# --------------------------------------------------------------------------


def parse_rfc3339(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def format_rfc3339(moment: datetime) -> str:
    return moment.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# --------------------------------------------------------------------------
# Lock identity and serialization
# --------------------------------------------------------------------------


def lock_id(stage: str) -> str:
    """Windows-safe slug plus digest. A raw colon is never materialized."""
    slug = re.sub(r"[^a-z0-9]+", "-", stage.lower()).strip("-")[:40].strip("-")
    return "%s-%s" % (slug, hashlib.sha256(stage.encode("utf-8")).hexdigest()[:8])


def lock_filename(stage: str) -> str:
    name = lock_id(stage) + ".lock"
    # Defence in depth: the slug cannot produce these, and if it ever did the
    # helper refuses rather than writing an unopenable NTFS name.
    if ":" in name or "%3a" in name.lower() or "\\" in name or "/" in name:
        raise Refusal(EXIT_USAGE,
                      "computed lock filename %r is not Windows-safe; the canonical "
                      "slug-plus-digest algorithm must not be bypassed" % name)
    return name


# The members every lock must carry for this helper to reason about it at all.
# Anything missing or of the wrong type means the lock cannot be classified,
# and an unclassifiable lock blocks rather than being ignored.
LOCK_REQUIRED: tuple[tuple[str, type | tuple[type, ...]], ...] = (
    ("schema", int), ("stage", str), ("status", str), ("kind", str),
    ("owner", str), ("host", str), ("pid", int),
    ("acquired_at", str), ("heartbeat_at", str), ("resources", list),
)


def lock_structure_problem(data: dict) -> str | None:
    """Why this parsed lock cannot be trusted to describe its own claim, or None."""
    for key, kind in LOCK_REQUIRED:
        if key not in data:
            return "omits the required lock field %r" % key
        value = data[key]
        if kind is int and isinstance(value, bool):
            return "has a boolean where field %r must be an integer" % key
        if not isinstance(value, kind):
            return "has field %r of the wrong type (%s)" % (key, type(value).__name__)
    if data.get("kind") == "board-test" and not isinstance(data.get("board_id"), str):
        return "is a board-test lock with no board_id, so the board it claims is unknown"
    if not all(isinstance(r, str) for r in data["resources"]):
        return "has a non-string entry in resources"
    return None


def toml_scalar(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(value, list):
        return "[" + ",".join(toml_scalar(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join("%s=%s" % (k, toml_scalar(v)) for k, v in value.items()) + "}"
    raise Refusal(EXIT_USAGE, "unserializable lock value %r" % (value,))


def serialize_lock(lock: dict) -> bytes:
    lines = ["%s=%s" % (key, toml_scalar(lock[key])) for key in lock]
    return ("\n".join(lines) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# Durable writes
# --------------------------------------------------------------------------


class Store:
    def __init__(self, run_dir: str, adapters: Adapters) -> None:
        self.run_dir = run_dir
        self.adapters = adapters
        self._durability: bool | None = None

    def require_durability(self) -> None:
        """Probe directory-flush capability once; block operations if absent."""
        if self._durability is None:
            os.makedirs(self.run_dir, exist_ok=True)
            self._durability = self.adapters.directory_fsync_supported(self.run_dir)
        if not self._durability:
            raise Refusal(
                EXIT_DURABILITY,
                "directory flush is unsupported or denied on %r, so required "
                "durability cannot be established; target-affecting operations are "
                "blocked. Select a supported local filesystem. M6 defines no weaker "
                "protocol." % self.run_dir)

    def create_new(self, name: str, data: bytes) -> None:
        """Exclusive create, write, flush, fsync. Never overwrites."""
        path = os.path.join(self.run_dir, name)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        try:
            fd = os.open(path, flags, 0o644)
        except FileExistsError:
            raise Refusal(EXIT_CONFLICT,
                          "a lock already exists at %r; a lock is never stolen" % name)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())

    def replace(self, name: str, data: bytes) -> None:
        """Sibling temp plus os.replace, retrying only transient sharing violations.

        Source and destination are siblings, so the replacement is same-volume.
        Exhaustion fails closed and leaves the temp file for recovery; a lock is
        never deleted to work around a sharing failure.
        """
        path = os.path.join(self.run_dir, name)
        temp = path + ".tmp-%s" % secrets.token_hex(4)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        fd = os.open(temp, flags, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        remaining = self.adapters.replace_failures()
        always = self.adapters.replace_always_fails()
        last: Exception = OSError("no attempt was made")
        for delay_ms in (0,) + REPLACE_RETRY_DELAYS_MS:
            if delay_ms:
                self.adapters.sleep(delay_ms / 1000.0)
            try:
                if always or remaining > 0:
                    remaining -= 1
                    raise PermissionError(
                        32, "The process cannot access the file because it is being "
                            "used by another process")
                os.replace(temp, path)
                return
            except PermissionError as exc:
                last = exc
        raise Refusal(
            EXIT_DURABILITY,
            "replacing %r failed after %d bounded retries on a sharing violation "
            "(%s); failing closed and preserving %r for recovery. Nothing was "
            "deleted and no lock was stolen."
            % (name, len(REPLACE_RETRY_DELAYS_MS), last, os.path.basename(temp)))

    def scan(self) -> list[tuple[str, dict | None, str]]:
        """Every `.lock` in the run directory: (name, parsed-or-None, reason).

        Unreadable locks are RETURNED, not skipped. A lock the helper cannot
        read, decode, parse or structurally validate is not an absent lock: it
        is a claim of unknown extent, and skipping it makes a corrupted live
        claim indistinguishable from no claim at all - which is two operators
        on one board, the hazard this whole mechanism exists to prevent.
        """
        if not os.path.isdir(self.run_dir):
            return []
        out: list[tuple[str, dict | None, str]] = []
        for index, name in enumerate(sorted(os.listdir(self.run_dir))):
            if index >= MAX_SCAN_FILES:
                raise Refusal(EXIT_USAGE, "more than %d files in %r" % (MAX_SCAN_FILES, self.run_dir))
            if not name.endswith(".lock"):
                continue
            try:
                with open(os.path.join(self.run_dir, name), "rb") as handle:
                    raw = handle.read(MAX_RECORD_BYTES + 1)
            except OSError as exc:
                out.append((name, None, "cannot be read: %s" % exc))
                continue
            if len(raw) > MAX_RECORD_BYTES:
                out.append((name, None, "exceeds the %d-byte lock bound" % MAX_RECORD_BYTES))
                continue
            try:
                data = tomllib.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
                out.append((name, None, "is not well-formed UTF-8 TOML: %s" % exc))
                continue
            if not isinstance(data, dict):
                out.append((name, None, "is not a table"))
                continue
            problem = lock_structure_problem(data)
            if problem is not None:
                out.append((name, None, problem))
                continue
            out.append((name, data, ""))
        return out

    def read_all(self) -> list[tuple[str, dict]]:
        """Only the locks that parsed and validated. Callers that make safety
        decisions must use `scan()` instead, so an unreadable lock cannot be
        silently read as an absent one."""
        return [(name, data) for name, data, _why in self.scan() if data is not None]

    def read_one(self, name: str) -> dict | None:
        for found, data in self.read_all():
            if found == name:
                return data
        return None

    def remove_own_candidate(self, name: str) -> None:
        try:
            os.unlink(os.path.join(self.run_dir, name))
        except OSError:
            pass


# --------------------------------------------------------------------------
# Liveness classification - the ONLY admissible observations
# --------------------------------------------------------------------------


def classify_lock(lock: dict, now: datetime, local_host: str,
                  birth: tuple[str, str | None]) -> str:
    """live | interrupted | ambiguous. No other inference is permitted.

    A timeout never proves death, so a stale remote heartbeat is ambiguous, not
    interrupted. A same-host PID that exists but whose birth identity differs is
    a REUSED PID, therefore interrupted, not live.
    """
    heartbeat = lock.get("heartbeat_at")
    try:
        age = (now - parse_rfc3339(str(heartbeat))).total_seconds()
    except (ValueError, TypeError):
        return "ambiguous"
    if lock.get("host") != local_host:
        if age < 0 or age > HEARTBEAT_AMBIGUOUS_SECONDS:
            return "ambiguous"
        return "live"
    if age < -HEARTBEAT_AMBIGUOUS_SECONDS:
        return "ambiguous"
    scheme, value = birth
    if scheme == "unavailable":
        return "ambiguous"
    if value is None:
        return "interrupted"
    recorded = lock.get("owner_process_identity")
    if not isinstance(recorded, dict) or recorded.get("scheme") == "unavailable":
        return "ambiguous"
    if recorded.get("scheme") != scheme:
        return "ambiguous"
    if str(recorded.get("value")) != str(value):
        return "interrupted"
    return "live"


# --------------------------------------------------------------------------
# Evidence resolution
#
# Every FileRef this helper records or acts on is OPENED, HASHED and PARSED
# before the transition it justifies. A path the helper never read is not
# evidence, it is a string: the earlier build accepted a nonexistent
# SafeStateObservation, declared a board "safe" on it, and released the
# interlock, which handed the next operator a device whose state nobody had
# established. "Safe" is a claim about a physical device and must never rest on
# an unread FileRef.
#
# What this still cannot do: it proves the record EXISTS, PARSES and BINDS to
# this board, epoch and attempt. It cannot prove the observation is true, that
# the procedure it describes is physically sufficient, or that any operator
# actually performed it. Those remain human obligations.
# --------------------------------------------------------------------------

MAX_RECORD_BYTES = 1024 * 1024
HAZARD_KINDS = ("outputs", "dma", "interrupts", "external-loads", "reset-halt", "probe")
# Hazards whose observation depends on physical actions no tooling can see.
PHYSICAL_HAZARDS = ("external-loads", "probe")
TERMINATION_DISPOSITIONS = ("confirmed-terminated", "physically-isolated")
RECOVERY_OUTCOMES = _SCHEMA.LOCK_RECOVERY_OUTCOMES


def resolve_evidence(root: str, relpath: str, what: str) -> tuple[str, bytes, str]:
    """Open and hash one referenced file. (abspath, raw bytes, sha256 hex)."""
    if not isinstance(relpath, str) or not relpath.strip():
        raise Refusal(EXIT_RECOVERY, "%s: a nonempty relative path is required" % what)
    if relpath.startswith("/") or relpath.startswith("\\") or ":" in relpath:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r must be a repository-relative path" % (what, relpath))
    target = os.path.abspath(os.path.join(root, relpath.replace("/", os.sep)))
    base = os.path.abspath(root)
    if os.path.commonpath([base, target]) != base:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r escapes the repository root" % (what, relpath))
    if not os.path.isfile(target):
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r does not exist or is not a regular file. The helper refuses to "
            "record, transition on, or release against evidence it cannot open; an "
            "unreadable FileRef is not a weaker claim, it is no claim at all."
            % (what, relpath))
    try:
        size = os.path.getsize(target)
        if size > MAX_RECORD_BYTES:
            raise Refusal(EXIT_RECOVERY,
                          "%s: %r is %d bytes, over the %d-byte record bound"
                          % (what, relpath, size, MAX_RECORD_BYTES))
        with open(target, "rb") as handle:
            raw = handle.read(MAX_RECORD_BYTES + 1)
    except OSError as exc:
        raise Refusal(EXIT_RECOVERY, "%s: %r could not be read: %s" % (what, relpath, exc))
    return target, raw, hashlib.sha256(raw).hexdigest()


def file_ref(relpath: str, digest: str) -> dict:
    return {"path": relpath, "sha256": digest}


SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def resolve_ref(root: str, ref, what: str) -> tuple[str, str]:
    """Resolve a recorded FileRef and require a PINNED digest that still matches.

    The digest is mandatory. An earlier build accepted `{path = "..."}` with no
    `sha256` and only compared when one happened to be present, so an unpinned
    reference passed verification and release unchallenged - and an unpinned
    reference is a name, not evidence: the bytes behind it can change freely
    after they were attested, which is exactly what the closure is supposed to
    prevent.
    """
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        raise Refusal(EXIT_RECOVERY, "%s: a {path,sha256} FileRef is required" % what)
    recorded = ref.get("sha256")
    if not isinstance(recorded, str) or not SHA256_RE.match(recorded):
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r carries no canonical sha256 (64 lowercase hex); found %r. An "
            "unpinned reference is a name, not evidence - the bytes behind it can "
            "change freely after they were attested."
            % (what, ref["path"], recorded))
    _abs, _raw, digest = resolve_evidence(root, ref["path"], what)
    if recorded != digest:
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r now hashes to %s but the record pins %s. The bytes changed after "
            "they were attested; re-observe rather than trusting the old claim."
            % (what, ref["path"], digest, recorded))
    return ref["path"], digest


def parse_record(root: str, relpath: str, what: str) -> tuple[dict, str]:
    """Resolve, hash and TOML-parse one typed record. (data, sha256)."""
    _abs, raw, digest = resolve_evidence(root, relpath, what)
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r is not a well-formed UTF-8 TOML record: %s"
                      % (what, relpath, exc))
    if not isinstance(data, dict):
        raise Refusal(EXIT_RECOVERY, "%s: %r is not a table" % (what, relpath))
    if data.get("schema") != SCHEMA:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r declares schema %r, not %d"
                      % (what, relpath, data.get("schema"), SCHEMA))
    return data, digest


def require(condition: bool, message: str) -> None:
    if not condition:
        raise Refusal(EXIT_RECOVERY, message)


def bind_to_lock(record: dict, lock: dict, relpath: str, what: str,
                 attempt: int | None = None) -> None:
    """Board, epoch and attempt must match the interlock this record justifies."""
    require(record.get("board_id") == lock.get("board_id"),
            "%s: %r names board %r but the interlock holds %r"
            % (what, relpath, record.get("board_id"), lock.get("board_id")))
    require(record.get("lease_epoch") == lock.get("lease_epoch"),
            "%s: %r names epoch %r but the current epoch is %r. A record from another "
            "epoch describes another claim on the board."
            % (what, relpath, record.get("lease_epoch"), lock.get("lease_epoch")))
    if attempt is not None:
        require(record.get("operation_attempt") == attempt,
                "%s: %r names operation attempt %r, not the current %r"
                % (what, relpath, record.get("operation_attempt"), attempt))


def load_facts_handoff(root: str, relpath: str, what: str) -> set:
    """Parse a bound `02-facts` handoff and return its verified assertion IDs.

    A hash pin proves only that some bytes did not change. It does not make the
    file a handoff, let alone a READY one whose citations were verified - and
    `07-tests.md` claims the procedure is bound "to verified assertions in a
    ready 02-facts handoff", which is exactly what makes a SafeStateObservation
    mean anything. So the handoff is parsed here: right stage, ready status, a
    passed `citations-verified` check, and real assertion IDs.

    What this still cannot do: it proves the cited assertions were VERIFIED as
    occurrences at their cited locations. It cannot prove they entail that the
    procedure makes this board safe. That stays with review.
    """
    _abs, raw, _digest = resolve_evidence(root, relpath, what)
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r is not a well-formed UTF-8 TOML handoff: %s"
                      % (what, relpath, exc))
    handoff = data.get("handoff")
    if not isinstance(handoff, dict):
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r has no [handoff] table, so it is not a handoff at all. A "
            "hash-pinned file is not evidence of its own kind." % (what, relpath))
    if handoff.get("schema") != SCHEMA:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r declares handoff schema %r, not %d"
                      % (what, relpath, handoff.get("schema"), SCHEMA))
    if handoff.get("stage") != "extract-facts":
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r is a %r handoff, not the 02-facts handoff the procedure must bind "
            "to" % (what, relpath, handoff.get("stage")))
    if handoff.get("status") != "ready":
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r is %r, not ready. A procedure may not rest on facts their own "
            "producer has not finished." % (what, relpath, handoff.get("status")))
    verified = None
    for entry in data.get("checks", []) or []:
        if isinstance(entry, dict) and entry.get("id") == "citations-verified":
            verified = entry.get("status")
    if verified != "passed":
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r records citations-verified as %r, not 'passed'. Unverified "
            "citations are quotations nobody derived from the source bytes."
            % (what, relpath, verified))
    available = set()
    for citation in data.get("facts", {}).get("citations", []) or []:
        if isinstance(citation, dict) and isinstance(citation.get("assertion_id"), str):
            available.add(citation["assertion_id"])
    if not available:
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r carries no verified citations" % (what, relpath))
    return available


def load_safe_state_observation(root: str, relpath: str, lock: dict) -> tuple[dict, str]:
    """A SafeStateObservation covering all six hazards, bound to this epoch."""
    what = "safe-state observation"
    data, digest = parse_record(root, relpath, what)
    bind_to_lock(data, lock, relpath, what,
                 attempt=lock.get("operation_attempt"))
    for field in ("observed_at", "procedure", "hazards", "outstanding_human_actions"):
        require(field in data, "%s: %r omits required field %r" % (what, relpath, field))
    try:
        parse_rfc3339(str(data["observed_at"]))
    except (ValueError, TypeError):
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r has a malformed observed_at %r"
                      % (what, relpath, data.get("observed_at")))

    procedure = data.get("procedure")
    if not isinstance(procedure, dict):
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r omits the bound SafeStateProcedureRef" % (what, relpath))
    require(procedure.get("board_id") == lock.get("board_id"),
            "%s: %r binds a procedure for board %r, not %r"
            % (what, relpath, procedure.get("board_id"), lock.get("board_id")))
    assertion_ids = procedure.get("assertion_ids")
    if not (isinstance(assertion_ids, list) and assertion_ids
            and all(isinstance(a, str) and a for a in assertion_ids)):
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r binds no verified fact assertion IDs; the procedure must "
                      "rest on cited facts, not on prose" % (what, relpath))
    handoff_path, _d = resolve_ref(root, procedure.get("facts_handoff"),
                                   what + " facts handoff")
    available = load_facts_handoff(root, handoff_path, what + " facts handoff")
    missing = sorted(set(assertion_ids) - available)
    if missing:
        raise Refusal(
            EXIT_RECOVERY,
            "%s: %r names assertion ID(s) %s that do not resolve in the bound facts "
            "handoff %r. An assertion ID nobody can look up is a string, not a cited "
            "fact." % (what, relpath, ", ".join(missing), handoff_path))
    resolve_ref(root, procedure.get("procedure"), what + " procedure record")

    hazards = data.get("hazards")
    if not isinstance(hazards, list):
        raise Refusal(EXIT_RECOVERY, "%s: %r has no hazards array" % (what, relpath))
    seen: dict[str, dict] = {}
    for entry in hazards:
        require(isinstance(entry, dict), "%s: %r has a non-table hazard" % (what, relpath))
        kind = entry.get("kind")
        require(kind in HAZARD_KINDS,
                "%s: %r observes unknown hazard %r" % (what, relpath, kind))
        require(kind not in seen,
                "%s: %r observes hazard %r twice" % (what, relpath, kind))
        seen[str(kind)] = entry
    missing = [k for k in HAZARD_KINDS if k not in seen]
    require(not missing,
            "%s: %r observes %d of 6 hazards; %s is unobserved. A hazard nobody looked "
            "at is not a hazard nobody has."
            % (what, relpath, len(seen), ", ".join(missing)))

    for kind in HAZARD_KINDS:
        entry = seen[kind]
        disposition = entry.get("disposition")
        require(disposition in ("safe", "not-applicable", "unknown"),
                "%s: %r hazard %r has illegal disposition %r"
                % (what, relpath, kind, disposition))
        require(disposition != "unknown",
                "%s: %r records hazard %r as UNKNOWN. Any unknown hazard means the "
                "board is not safe; there is no partial safety."
                % (what, relpath, kind))
        require(isinstance(entry.get("observation_method"), str)
                and entry["observation_method"].strip(),
                "%s: %r hazard %r states no observation method"
                % (what, relpath, kind))
        resolve_ref(root, entry.get("evidence"),
                    "%s hazard %r evidence" % (what, kind))
        if disposition == "not-applicable":
            require(isinstance(entry.get("reason"), str) and entry["reason"].strip(),
                    "%s: %r hazard %r is not-applicable without a reason"
                    % (what, relpath, kind))
        if kind in PHYSICAL_HAZARDS:
            require("operator_confirmation" in entry,
                    "%s: %r hazard %r depends on a physical action no tooling can "
                    "observe and carries no operator confirmation"
                    % (what, relpath, kind))
        if "operator_confirmation" in entry:
            resolve_ref(root, entry.get("operator_confirmation"),
                        "%s hazard %r operator confirmation" % (what, kind))

    outstanding = data.get("outstanding_human_actions")
    if not isinstance(outstanding, list) or not all(isinstance(a, str) for a in outstanding):
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r has a malformed outstanding_human_actions list"
                      % (what, relpath))
    require(not outstanding,
            "%s: %r lists %d outstanding human action(s): %s. Outstanding work means "
            "the board is not yet safe."
            % (what, relpath, len(outstanding), "; ".join(str(a) for a in outstanding)))
    return data, digest


def load_recovery_attempt(root: str, relpath: str, lock: dict,
                          attempt_number: int, outcome: str) -> tuple[dict, str]:
    """One append-only recovery-attempt record, bound to this epoch."""
    what = "recovery attempt"
    data, digest = parse_record(root, relpath, what)
    bind_to_lock(data, lock, relpath, what)
    require(data.get("attempt_number") == attempt_number,
            "%s: %r records attempt_number %r but this is attempt %d"
            % (what, relpath, data.get("attempt_number"), attempt_number))
    require(data.get("outcome") == outcome,
            "%s: %r records outcome %r but the command declares %r"
            % (what, relpath, data.get("outcome"), outcome))
    require(outcome in RECOVERY_OUTCOMES,
            "%s: illegal outcome %r" % (what, outcome))
    require(data.get("last_operation") in OPERATIONS,
            "%s: %r records unknown last_operation %r"
            % (what, relpath, data.get("last_operation")))
    try:
        parse_rfc3339(str(data.get("started_at")))
    except (ValueError, TypeError):
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r has a malformed started_at %r"
                      % (what, relpath, data.get("started_at")))
    if outcome in ("failed", "verified"):
        require("completed_at" in data,
                "%s: %r is %r but records no completed_at" % (what, relpath, outcome))
    actions = data.get("actions")
    if not (isinstance(actions, list) and actions
            and all(isinstance(a, str) and a.strip() for a in actions)):
        raise Refusal(EXIT_RECOVERY,
                      "%s: %r records no actions; an attempt that did nothing is not "
                      "an attempt" % (what, relpath))
    evidence = data.get("evidence")
    if not (isinstance(evidence, list) and evidence):
        raise Refusal(EXIT_RECOVERY, "%s: %r carries no evidence" % (what, relpath))
    for index, ref in enumerate(evidence):
        resolve_ref(root, ref, "%s evidence[%d]" % (what, index))
    resolve_ref(root, data.get("prior_lock"), what + " prior_lock")
    if "operator_confirmation" in data:
        resolve_ref(root, data.get("operator_confirmation"),
                    what + " operator confirmation")
    if outcome == "verified":
        safe_state = data.get("safe_state")
        if not (isinstance(safe_state, dict) and isinstance(safe_state.get("path"), str)):
            raise Refusal(EXIT_RECOVERY,
                          "%s: %r claims outcome 'verified' with no "
                          "SafeStateObservation. Verified means a human observed the "
                          "board safe and wrote it down." % (what, relpath))
        load_safe_state_observation(root, str(safe_state["path"]), lock)
        resolve_ref(root, safe_state, what + " safe_state")
    return data, digest


def load_override_record(root: str, relpath: str, lock: dict,
                         lock_digest: str) -> tuple[dict, str]:
    """The operator-authored ambiguity override. The only escape from a jam."""
    what = "override record"
    data, digest = parse_record(root, relpath, what)
    bind_to_lock(data, lock, relpath, what)
    for field in ("observed_host", "observed_pid", "reason",
                  "termination_disposition", "confirmation", "confirmed_at",
                  "confirmer", "acknowledges_board_unknown"):
        require(field in data, "%s: %r omits required field %r" % (what, relpath, field))
    require(data.get("termination_disposition") in TERMINATION_DISPOSITIONS,
            "%s: %r records termination_disposition %r, not one of %s"
            % (what, relpath, data.get("termination_disposition"),
               " or ".join(TERMINATION_DISPOSITIONS)))
    require(data.get("acknowledges_board_unknown") is True,
            "%s: %r does not explicitly acknowledge that board state remains unknown. "
            "An override is permission to RECOVER, never a claim that the board is safe."
            % (what, relpath))
    require(isinstance(data.get("confirmer"), str) and data["confirmer"].strip(),
            "%s: %r names no confirmer" % (what, relpath))
    require(isinstance(data.get("reason"), str) and data["reason"].strip(),
            "%s: %r gives no reason why inspection is inconclusive" % (what, relpath))
    pid = data.get("observed_pid")
    require(isinstance(pid, int) and not isinstance(pid, bool) and pid > 0,
            "%s: %r records a non-positive observed_pid %r" % (what, relpath, pid))
    resolve_ref(root, data.get("confirmation"), what + " confirmation")
    # The operator must have inspected THIS lock, not a description of it.
    prior = data.get("prior_lock")
    require(isinstance(prior, dict) and prior.get("sha256") == lock_digest,
            "%s: %r pins prior_lock %r but the live lock hashes to %s. The record must "
            "attest the lock actually present, or it attests nothing."
            % (what, relpath,
               prior.get("sha256") if isinstance(prior, dict) else prior, lock_digest))
    return data, digest


# --------------------------------------------------------------------------
# Lock construction and transitions
# --------------------------------------------------------------------------


def new_lock(stage: str, board_id: str, authorization: dict | None, adapters: Adapters,
             phase: str, board_state: str) -> dict:
    now = adapters.now()
    pid = os.getpid()
    scheme, value = adapters.process_birth(pid)
    identity = {"scheme": scheme if value is not None else "unavailable"}
    if value:
        identity["value"] = str(value)
    elif identity["scheme"] != "unavailable":
        identity["value"] = ""
    lock = {
        "schema": SCHEMA,
        "stage": stage,
        "status": "in-progress",
        "kind": "board-test",
        "owner": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
        "host": adapters.host(),
        "pid": pid,
        "acquired_at": format_rfc3339(now),
        "heartbeat_at": format_rfc3339(now),
        "resources": sorted(["board:%s" % board_id, "stage:%s" % stage]),
        "board_id": board_id,
        "board_state": board_state,
        "lease_epoch": secrets.token_hex(16),
        "check_token": secrets.token_hex(32),
        "owner_process_identity": identity,
        "operation_phase": phase,
        "operation_attempt": 0,
        "last_operation": "none",
        "recovery_attempts": [],
    }
    # Acquisition is not a safety claim: the lock is born recovery-pending with
    # the board unknown, so nothing target-affecting is legal yet. The
    # authorization is therefore recorded as a bare path when it cannot be
    # resolved, and `begin-board-operation` - the first command that actually
    # touches the target - refuses until it resolves and hashes.
    if authorization is not None:
        lock["authorization"] = authorization
    return lock


def child_in_flight(lock: dict) -> dict | None:
    """The recorded child session that has not been confirmed finished, if any.

    A child is "in flight" from the moment an operation starts it until
    `complete-board-operation` records that it and its descendants terminated
    and the observation channel went quiet. Until then it may still be driving
    pins or transferring, which is why it must never be overwritten.
    """
    session = lock.get("child_session")
    if isinstance(session, dict) and not session.get("completed_at"):
        return session
    return None


def refuse_if_child_in_flight(lock: dict, what: str) -> None:
    session = child_in_flight(lock)
    if session is None:
        return
    raise Refusal(
        EXIT_RECOVERY,
        "%s: operation %r is still in flight with child session %r (%s, started %s) "
        "and its completion has not been recorded. Starting another would REPLACE "
        "that record, leaving a probe that may still be driving pins or transferring "
        "with no way to reap it or confirm it quiescent - the system would believe "
        "nothing is in flight. Run complete-board-operation --operation-id %s first, "
        "or enter recovery for it."
        % (what, lock.get("last_operation"), session.get("identity"),
           session.get("kind"), session.get("started_at"), lock.get("operation_id")))


def require_epoch(lock: dict, epoch: str, token: str) -> None:
    if lock.get("lease_epoch") != epoch or lock.get("check_token") != token:
        raise Refusal(
            EXIT_CONFLICT,
            "epoch or check token does not equal the current lock; another claimant "
            "or a recovery has taken the board. Treat any overlap as unknown and stop "
            "operations.")


def board_resource_conflict(store: Store, own_name: str, board_id: str,
                            adapters: Adapters) -> tuple[str, str] | None:
    """Any OTHER lock that might hold this board. Fails CLOSED.

    Three ways a lock blocks:

    * it is unreadable - cannot be read, decoded, parsed or structurally
      validated. Its resources are unknown, so it may well hold this board.
      **An unreadable lock is not an absent lock**; treating it as absent makes
      a corrupted live claim look like a free board.
    * it holds `board:<id>` and classifies live;
    * it holds `board:<id>` and classifies ambiguous - a timeout never proves
      death.

    No creation-order inference: whatever the timestamps say, the NEW claimant
    is the one that backs off.
    """
    now = adapters.now()
    local_host = adapters.host()
    for name, lock, why in store.scan():
        if name == own_name:
            continue
        if lock is None:
            return (name, "unreadable (%s)" % why)
        resources = lock.get("resources")
        if not isinstance(resources, list) or "board:%s" % board_id not in resources:
            continue
        pid = lock.get("pid")
        birth = adapters.process_birth(int(pid)) if isinstance(pid, int) else ("unavailable", "")
        state = classify_lock(lock, now, local_host, birth)
        if state in ("live", "ambiguous"):
            return (name, state)
    return None


# --------------------------------------------------------------------------
# Commands
# --------------------------------------------------------------------------


def cmd_inspect(args, store: Store, adapters: Adapters) -> dict:
    now = adapters.now()
    local_host = adapters.host()
    locks = []
    unreadable = []
    for name, lock, why in store.scan():
        if lock is None:
            # Acquisition fails closed on these, so an operator who cannot see
            # them here is told the board is busy with no way to find out why.
            unreadable.append({"name": name, "reason": why,
                               "effect": "blocks acquisition of every board until it "
                                         "is repaired or deliberately removed"})
            continue
        pid = lock.get("pid")
        birth = adapters.process_birth(int(pid)) if isinstance(pid, int) else ("unavailable", "")
        locks.append({
            "name": name,
            "stage": lock.get("stage"),
            "board_id": lock.get("board_id"),
            "operation_phase": lock.get("operation_phase"),
            "board_state": lock.get("board_state"),
            "operation_attempt": lock.get("operation_attempt"),
            "lease_epoch": lock.get("lease_epoch"),
            "classification": classify_lock(lock, now, local_host, birth),
            "recovery_attempts": lock.get("recovery_attempts", []),
        })
    return {"command": "inspect", "locks": locks,
            "unreadable_locks": unreadable,
            "note": "worktree-local and single-operator; another clone or operator is "
                    "invisible here. An unreadable lock is listed separately and still "
                    "blocks acquisition: its resources cannot be read, so it may hold "
                    "any board."}


def cmd_acquire_board(args, store: Store, adapters: Adapters) -> dict:
    store.require_durability()
    name = lock_filename(args.stage)
    existing = board_resource_conflict(store, name, args.board, adapters)
    if existing is not None:
        raise Refusal(EXIT_CONFLICT,
                      "board %r is held by %r classified %s; this claimant creates "
                      "nothing and fails" % (args.board, existing[0], existing[1]))
    prior = store.read_all()
    # The authorization is hashed if it can be resolved now. If it cannot, the
    # bare path is recorded and `begin-board-operation` refuses until it does:
    # acquisition itself is not a target-affecting operation, and the lock is
    # born recovery-pending with the board unknown either way.
    # A lock never carries a reference the helper did not verify. If the
    # authorization cannot be resolved now it is simply absent, and
    # `begin-board-operation` refuses on that absence; recording an unpinned
    # FileRef would both overstate what was checked and write a lock the static
    # schema rejects.
    authorization: dict | None = None
    authorization_state = "absent-until-resolved"
    try:
        _abs, _raw, digest = resolve_evidence(args.root, args.authorization,
                                              "board authorization")
        authorization = file_ref(args.authorization, digest)
        authorization_state = "resolved"
    except Refusal:
        pass
    # Absence is NOT evidence of prior safe teardown, so a first acquisition in a
    # fresh clone starts in recovery-pending with the board unknown.
    lock = new_lock(args.stage, args.board, authorization, adapters,
                    "recovery-pending", "unknown")
    store.create_new(name, serialize_lock(lock))
    # Post-create rescan. Any other intersecting valid lock makes THIS claimant
    # remove only its own candidate and fail; the existing lock is untouched.
    conflict = board_resource_conflict(store, name, args.board, adapters)
    if conflict is not None:
        store.remove_own_candidate(name)
        raise Refusal(EXIT_CONFLICT,
                      "post-create rescan found %r classified %s holding board %r; "
                      "removed only this claimant's own candidate and failed"
                      % (conflict[0], conflict[1], args.board))
    return {"command": "acquire-board", "lock": name,
            "lease_epoch": lock["lease_epoch"], "check_token": lock["check_token"],
            "operation_phase": lock["operation_phase"],
            "board_state": lock["board_state"],
            "authorization": authorization_state,
            "prior_locks_seen": len(prior),
            "note": "board state is UNKNOWN: no prior lock proves a previous run tore "
                    "down safely. Confirm no other operator is active and confirm prior "
                    "debug children terminated or physically isolate board and probe, "
                    "then establish recovery-verified before any attach."}


def load_own(store: Store, args) -> tuple[str, dict]:
    name = lock_filename(args.stage)
    lock = store.read_one(name)
    if lock is None:
        raise Refusal(EXIT_RECOVERY,
                      "no interlock at %r; the board state is unknown and a fresh "
                      "acquisition starts in recovery-pending" % name)
    require_epoch(lock, args.epoch, args.token)
    board = getattr(args, "board", None)
    if board is not None and lock.get("board_id") != board:
        raise Refusal(EXIT_CONFLICT,
                      "the interlock holds board %r, not the %r this command names"
                      % (lock.get("board_id"), board))
    return name, lock


def cmd_heartbeat_board(args, store: Store, adapters: Adapters) -> dict:
    name, lock = load_own(store, args)
    lock["heartbeat_at"] = format_rfc3339(adapters.now())
    store.replace(name, serialize_lock(lock))
    return {"command": "heartbeat-board", "lock": name,
            "heartbeat_at": lock["heartbeat_at"]}


def cmd_before_board_op(args, store: Store, adapters: Adapters) -> dict:
    store.require_durability()
    name, lock = load_own(store, args)
    scope = "test"
    if lock.get("operation_phase") in ("recovery-pending", "recovery-active"):
        # Recovery is reachable: the operator may precheck the observation
        # operations recovery needs. Everything else stays shut until the board
        # has actually been shown safe.
        if args.operation is None or args.operation not in RECOVERY_SCOPED_OPERATIONS:
            raise Refusal(
                EXIT_RECOVERY,
                "the interlock is recovery-pending and the board is UNKNOWN. Only a "
                "recovery-scoped operation (%s) may be precheck-approved, and only "
                "through begin-recovery-operation; %r is ordinary test work and waits "
                "for recovery-verified."
                % (", ".join(RECOVERY_SCOPED_OPERATIONS), args.operation))
        scope = "recovery"
    return {"command": "before-board-op", "lock": name, "approved": True,
            "operation_scope": scope,
            "residual": "this check narrows but CANNOT CLOSE the check-use window. "
                        "A holder may pass this check, pause, lose or override its "
                        "epoch, and then resume a direct command. Only the deferred "
                        "broker closes it; treat any overlap as unknown."}


def cmd_begin_board_operation(args, store: Store, adapters: Adapters) -> dict:
    store.require_durability()
    name, lock = load_own(store, args)
    if args.operation not in OPERATIONS:
        raise Refusal(EXIT_USAGE, "unknown operation %r" % args.operation)
    if lock.get("operation_phase") not in ("acquired", "preparing", "recovery-verified", "teardown"):
        raise Refusal(EXIT_RECOVERY,
                      "phase %r does not permit ordinary test work; the board must be "
                      "recovery-verified and safe first. Recovery authorizes only "
                      "observation, through begin-recovery-operation (%s)."
                      % (lock.get("operation_phase"),
                         ", ".join(RECOVERY_SCOPED_OPERATIONS)))
    if lock.get("board_state") == "unknown":
        raise Refusal(EXIT_RECOVERY,
                      "board state is unknown; attaching a debugger is itself a "
                      "target-affecting operation and is refused")
    # The first command that actually touches the target is the first that
    # needs a readable authorization. Acquisition records the path; this
    # resolves and hashes it, and refuses if it is not there.
    authorization = lock.get("authorization")
    if not isinstance(authorization, dict) or not isinstance(authorization.get("path"), str):
        raise Refusal(EXIT_RECOVERY,
                      "the interlock records no board authorization; a target-affecting "
                      "operation requires the authorizing record this claim was made "
                      "under")
    _path, auth_digest = resolve_ref(args.root, authorization, "board authorization")
    lock["authorization"] = file_ref(str(authorization["path"]), auth_digest)
    refuse_if_child_in_flight(lock, "begin-board-operation")
    lock["operation_attempt"] = int(lock.get("operation_attempt", 0)) + 1
    lock["operation_id"] = secrets.token_hex(16)
    lock["last_operation"] = args.operation
    lock["operation_phase"] = "active"
    lock["board_state"] = "active"
    lock["child_session"] = {
        "kind": args.child_kind,
        "identity": args.child_identity,
        "started_at": format_rfc3339(adapters.now()),
    }
    store.replace(name, serialize_lock(lock))
    return {"command": "begin-board-operation", "lock": name,
            "operation_attempt": lock["operation_attempt"],
            "operation_id": lock["operation_id"]}


def cmd_begin_recovery_operation(args, store: Store, adapters: Adapters) -> dict:
    """Authorize ONE recovery-scoped operation on a board whose state is unknown.

    This is the narrow, explicitly authorized transition that makes recovery
    completable. It is not a general unlock:

    * it is reachable only from `recovery-pending` or from a recovery-scoped
      operation already in flight - never from a fresh claim;
    * it permits only the observation operations in
      `RECOVERY_SCOPED_OPERATIONS`; it cannot load, program or run;
    * it marks the lock `operation_scope = "recovery"`, so
      `begin-board-operation` and `release-board` both keep refusing;
    * completing it returns the interlock to `recovery-pending` with the board
      still UNKNOWN. A recovery operation never advances toward release.

    **Device state stays unknown while this runs.** Attaching a debugger drives
    pins, so it is a target-affecting operation and cannot itself be the step
    that establishes safety; it is how the operator gathers the observations a
    SafeStateObservation then records.

    It does not require the board authorization. That record gates authorized
    TEST work; making a board safe after an interruption is not test work, and
    requiring it here would re-close the door this opens.
    """
    store.require_durability()
    name, lock = load_own(store, args)
    if args.operation not in RECOVERY_SCOPED_OPERATIONS:
        raise Refusal(
            EXIT_RECOVERY,
            "%r is not a recovery-scoped operation. Recovery may authorize only %s - "
            "observation and isolation, never loading, programming or running code on "
            "a board whose state nobody has established."
            % (args.operation, ", ".join(RECOVERY_SCOPED_OPERATIONS)))
    phase = lock.get("operation_phase")
    if phase not in ("recovery-pending", "recovery-active"):
        raise Refusal(
            EXIT_RECOVERY,
            "phase %r does not permit a recovery operation; run begin-board-recovery "
            "first so the board is explicitly declared unknown before anything "
            "reconnects to it" % phase)
    refuse_if_child_in_flight(lock, "begin-recovery-operation")
    lock["operation_attempt"] = int(lock.get("operation_attempt", 0)) + 1
    lock["operation_id"] = secrets.token_hex(16)
    lock["last_operation"] = args.operation
    lock["operation_phase"] = "recovery-active"
    lock["operation_scope"] = "recovery"
    lock["board_state"] = "unknown"
    lock["child_session"] = {
        "kind": args.child_kind,
        "identity": args.child_identity,
        "started_at": format_rfc3339(adapters.now()),
    }
    store.replace(name, serialize_lock(lock))
    return {"command": "begin-recovery-operation", "lock": name,
            "operation": args.operation,
            "operation_scope": "recovery",
            "operation_attempt": lock["operation_attempt"],
            "operation_id": lock["operation_id"],
            "operation_phase": "recovery-active",
            "board_state": "unknown",
            "note": "the board remains UNKNOWN while this runs. Attaching a debugger "
                    "drives pins and is itself target-affecting, so it cannot be the "
                    "step that establishes safety - record what you observe in a "
                    "recovery attempt and a SafeStateObservation."}


def cmd_complete_board_operation(args, store: Store, adapters: Adapters) -> dict:
    name, lock = load_own(store, args)
    if lock.get("operation_id") != args.operation_id:
        raise Refusal(EXIT_CONFLICT, "operation ID does not equal the current lock")
    if adapters.child_alive():
        raise Refusal(
            EXIT_RECOVERY,
            "the recorded child session is still running or the observation channel "
            "is not quiescent: holder death is not operation death, and a surviving "
            "probe or runner child may still be transferring or driving pins. "
            "Completion is not recorded; enter recovery.")
    session = lock.get("child_session")
    if isinstance(session, dict):
        session["completed_at"] = format_rfc3339(adapters.now())
    # A recovery-scoped operation returns to recovery-pending, never to
    # teardown: recovery work gathers observations, it does not advance the
    # interlock toward release.
    recovery_scoped = lock.get("operation_scope") == "recovery"
    lock["operation_phase"] = "recovery-pending" if recovery_scoped else "teardown"
    lock["board_state"] = "unknown"
    if recovery_scoped:
        del lock["operation_scope"]
    store.replace(name, serialize_lock(lock))
    return {"command": "complete-board-operation", "lock": name,
            "board_state": "unknown",
            "operation_phase": lock["operation_phase"],
            "note": "state stays unknown until a SafeStateObservation is recorded"}


def cmd_set_board_state(args, store: Store, adapters: Adapters) -> dict:
    name, lock = load_own(store, args)
    if args.state == "safe":
        if not args.safe_state:
            raise Refusal(EXIT_RECOVERY,
                          "a safe board state requires a SafeStateObservation FileRef")
        _record, digest = load_safe_state_observation(args.root, args.safe_state, lock)
        lock["safe_state"] = file_ref(args.safe_state, digest)
    elif "safe_state" in lock:
        del lock["safe_state"]
    lock["board_state"] = args.state
    store.replace(name, serialize_lock(lock))
    return {"command": "set-board-state", "lock": name, "board_state": args.state}


def cmd_begin_board_recovery(args, store: Store, adapters: Adapters) -> dict:
    name, lock = load_own(store, args)
    # Entry needs no produced evidence. Requiring evidence to enter recovery
    # would be circular: evidence can only be produced from inside recovery.
    # Entry is always permitted and needs no produced evidence. What it must
    # NOT do is claim nothing is in flight while still holding an operation ID
    # and an unreaped child record: that contradiction is what let a second
    # operation quietly overwrite the first child. The record is preserved and
    # reported, and the next operation start refuses until it is completed.
    pending = child_in_flight(lock)
    lock["operation_phase"] = "recovery-pending"
    lock["board_state"] = "unknown"
    if "safe_state" in lock:
        del lock["safe_state"]
    if "operation_scope" in lock:
        del lock["operation_scope"]
    store.replace(name, serialize_lock(lock))
    return {"command": "begin-board-recovery", "lock": name,
            "recovery_scoped_operations": list(RECOVERY_SCOPED_OPERATIONS),
            "unreaped_child": None if pending is None else {
                "identity": pending.get("identity"), "kind": pending.get("kind"),
                "started_at": pending.get("started_at"),
                "operation_id": lock.get("operation_id"),
                "note": "this child was never confirmed finished. No further operation "
                        "may start until complete-board-operation records that it and "
                        "its descendants terminated, or it is physically isolated."},
            "operation_phase": "recovery-pending", "board_state": "unknown",
            "note": "declare the board unknown BEFORE reconnecting; identify and "
                    "terminate the recorded child session and confirm quiescence, or "
                    "physically isolate board and probe"}


def cmd_append_recovery_attempt(args, store: Store, adapters: Adapters) -> dict:
    name, lock = load_own(store, args)
    if lock.get("operation_phase") != "recovery-pending":
        raise Refusal(EXIT_RECOVERY,
                      "recovery attempts may be appended only while recovery-pending; "
                      "found %r. Complete any recovery operation in flight first."
                      % lock.get("operation_phase"))
    attempts = lock.get("recovery_attempts")
    if not isinstance(attempts, list):
        attempts = []
    expected = len(attempts) + 1
    if args.attempt_number != expected:
        raise Refusal(EXIT_RECOVERY,
                      "attempt number %d is not the next consecutive number %d; the "
                      "lineage is append-only and is never reordered or replaced"
                      % (args.attempt_number, expected))
    # Resolve, parse and bind the attempt record BEFORE appending it. The
    # append-only lineage is what a human later reads to believe the board was
    # made safe; a FileRef nobody opened would make that belief unfounded.
    record, digest = load_recovery_attempt(
        args.root, args.attempt_file, lock, args.attempt_number, args.outcome)
    attempts.append(file_ref(args.attempt_file, digest))
    lock["recovery_attempts"] = attempts
    lock["last_recovery_outcome"] = args.outcome
    if args.outcome == "verified":
        lock["last_verified_safe_state"] = str(record["safe_state"]["path"])
    elif "last_verified_safe_state" in lock:
        del lock["last_verified_safe_state"]
    store.replace(name, serialize_lock(lock))
    return {"command": "append-recovery-attempt", "lock": name,
            "attempt_number": args.attempt_number, "outcome": args.outcome,
            "attempts": len(attempts), "attempt_sha256": digest,
            "operation_phase": lock["operation_phase"]}


def cmd_verify_board_recovery(args, store: Store, adapters: Adapters) -> dict:
    name, lock = load_own(store, args)
    if lock.get("operation_phase") != "recovery-pending":
        raise Refusal(EXIT_RECOVERY,
                      "only a recovery-pending interlock can be verified; found %r. A "
                      "recovery operation still in flight must be completed first."
                      % lock.get("operation_phase"))
    if lock.get("last_recovery_outcome") != "verified":
        raise Refusal(EXIT_RECOVERY,
                      "the latest recovery attempt outcome is %r; only a verified "
                      "attempt with a matching SafeStateObservation reaches "
                      "recovery-verified" % lock.get("last_recovery_outcome"))
    pinned = lock.get("last_verified_safe_state")
    if pinned != args.safe_state:
        raise Refusal(
            EXIT_RECOVERY,
            "the verified recovery attempt names SafeStateObservation %r but this "
            "command names %r. Verification must rest on the observation the attempt "
            "itself recorded, not on a different record produced afterwards."
            % (pinned, args.safe_state))
    # Open, parse and bind the observation: six hazards, none unknown, no
    # outstanding human action, evidence that resolves, and the same board,
    # epoch and attempt. Only then may the board be called safe.
    _record, digest = load_safe_state_observation(args.root, args.safe_state, lock)
    lock["operation_phase"] = "recovery-verified"
    lock["board_state"] = "safe"
    lock["safe_state"] = file_ref(args.safe_state, digest)
    store.replace(name, serialize_lock(lock))
    return {"command": "verify-board-recovery", "lock": name,
            "operation_phase": "recovery-verified", "board_state": "safe",
            "safe_state_sha256": digest,
            "note": "this records that six typed hazard observations were READ and "
                    "bound to this epoch; it does not prove any of them is true, nor "
                    "that the procedure they describe is physically sufficient"}


def cmd_override_ambiguous_owner(args, store: Store, adapters: Adapters) -> dict:
    """The one escape from a jammed interlock. Narrow on purpose.

    It exists for exactly one situation: an owner whose liveness cannot be
    disproved - a recycled PID, an uninspectable process, an unreachable remote
    host - pinning a board forever. That is a real denial of service on real
    equipment. An override that also takes a HEALTHY owner's board is not an
    escape hatch; it is a way for two operators to drive one device, which is
    the accident this whole mechanism exists to prevent.

    So it requires all three: the helper's own classification is `ambiguous`,
    the ambiguity is persistent rather than a single unlucky reading, and a
    parsed operator record carries the confirmations. It authorizes RECOVERY
    only, and never claims the board is safe.
    """
    store.require_durability()
    name = lock_filename(args.stage)
    lock = store.read_one(name)
    if lock is None:
        raise Refusal(EXIT_RECOVERY, "no interlock at %r to override" % name)
    if args.board is not None and lock.get("board_id") != args.board:
        raise Refusal(EXIT_CONFLICT,
                      "the interlock holds board %r, not the %r this command names"
                      % (lock.get("board_id"), args.board))

    lock_path = os.path.join(store.run_dir, name)
    with open(lock_path, "rb") as handle:
        lock_bytes = handle.read()
    lock_digest = hashlib.sha256(lock_bytes).hexdigest()

    now = adapters.now()
    pid = lock.get("pid")
    birth = adapters.process_birth(int(pid)) if isinstance(pid, int) else ("unavailable", "")
    classification = classify_lock(lock, now, adapters.host(), birth)
    if classification == "live":
        raise Refusal(
            EXIT_CONFLICT,
            "the interlock classifies LIVE; the override refuses. A healthy owner is "
            "using this board. The escape hatch is for an owner whose death cannot be "
            "proved, never for one whose life can.")
    if classification == "interrupted":
        raise Refusal(
            EXIT_RECOVERY,
            "the interlock classifies INTERRUPTED, not ambiguous; the owner is "
            "positively gone, so no override is needed. Use begin-board-recovery and "
            "record recovery attempts under the existing epoch.")

    # Persistence. A living owner refreshes its heartbeat at least every 30
    # seconds, so an ambiguity that survives the full window is the real thing
    # rather than one unlucky reading.
    try:
        age = (now - parse_rfc3339(str(lock.get("heartbeat_at")))).total_seconds()
    except (ValueError, TypeError):
        age = None
    if age is None or age < HEARTBEAT_AMBIGUOUS_SECONDS:
        raise Refusal(
            EXIT_CONFLICT,
            "the interlock is ambiguous but its heartbeat is %s old; the override "
            "requires ambiguity that PERSISTS for at least %ds. A living owner "
            "refreshes within 30s, so wait, re-read, and override only if the "
            "ambiguity is still there."
            % ("%.0fs" % age if age is not None else "un-parseable",
               HEARTBEAT_AMBIGUOUS_SECONDS))

    record, digest = load_override_record(args.root, args.override_record,
                                          lock, lock_digest)
    try:
        confirmed = parse_rfc3339(str(record.get("confirmed_at")))
    except (ValueError, TypeError):
        raise Refusal(EXIT_RECOVERY,
                      "override record: malformed confirmed_at %r"
                      % record.get("confirmed_at"))
    heartbeat = parse_rfc3339(str(lock.get("heartbeat_at")))
    if heartbeat > confirmed:
        raise Refusal(
            EXIT_CONFLICT,
            "the owner refreshed its heartbeat at %s, after the operator confirmed at "
            "%s. Something is alive on the other side of this lock; re-inspect rather "
            "than override."
            % (format_rfc3339(heartbeat), format_rfc3339(confirmed)))

    archive = name + ".archived-%s" % lock.get("lease_epoch")
    store.create_new(archive, lock_bytes)
    fresh = new_lock(args.stage, str(lock.get("board_id")),
                     file_ref(args.override_record, digest), adapters,
                     "recovery-pending", "unknown")
    fresh["override_record"] = file_ref(args.override_record, digest)
    store.replace(name, serialize_lock(fresh))
    return {"command": "override-ambiguous-owner", "lock": name,
            "archived": archive,
            "prior_classification": classification,
            "prior_heartbeat_age_seconds": int(age),
            "termination_disposition": record.get("termination_disposition"),
            "confirmer": record.get("confirmer"),
            "lease_epoch": fresh["lease_epoch"], "check_token": fresh["check_token"],
            "operation_phase": "recovery-pending", "board_state": "unknown",
            "note": "this authorizes RECOVERY ONLY, never tests. It does not claim the "
                    "board is safe; state remains unknown until recovery-verified. The "
                    "operator's confirmation that the prior owner and its children are "
                    "stopped, or that board and probe are isolated, is not checkable "
                    "here and may be false."}


def cmd_release_board(args, store: Store, adapters: Adapters) -> dict:
    name_of_lock, lock = load_own(store, args)
    if lock.get("operation_phase") != "recovery-verified" or lock.get("board_state") != "safe":
        raise Refusal(
            EXIT_RECOVERY,
            "release requires operation_phase='recovery-verified' and "
            "board_state='safe'; found %r/%r. A lock is never released on the "
            "strength of a handoff published later."
            % (lock.get("operation_phase"), lock.get("board_state")))
    # Release hands the board to the next claimant, so re-read and re-verify the
    # safe-state record and the whole recovery lineage first. Nothing is removed
    # until every referenced record has been opened again and still hashes the
    # same: a record that changed or vanished since it was recorded is not a
    # weaker claim, it is no claim.
    safe_state = lock.get("safe_state")
    if not isinstance(safe_state, dict):
        raise Refusal(EXIT_RECOVERY,
                      "the interlock is marked safe but records no SafeStateObservation")
    resolve_ref(args.root, safe_state, "release safe-state observation")
    load_safe_state_observation(args.root, str(safe_state.get("path")), lock)
    lineage = lock.get("recovery_attempts")
    if not isinstance(lineage, list):
        raise Refusal(EXIT_RECOVERY, "the recovery lineage is malformed")
    walked = 0
    for index, ref in enumerate(lineage):
        path, _digest = resolve_ref(args.root, ref, "release recovery attempt[%d]" % index)
        # Walk INTO each attempt as well, not only its outer FileRef. An
        # attempt file can be byte-identical while the records it points at
        # have moved underneath it, and release is the moment the board passes
        # to the next claimant, so the whole closure is re-read here.
        record, _d = parse_record(args.root, path, "release recovery attempt[%d]" % index)
        for name in ("prior_lock", "operator_confirmation", "safe_state"):
            if name in record:
                resolve_ref(args.root, record[name],
                            "release recovery attempt[%d] %s" % (index, name))
                walked += 1
        nested = record.get("evidence")
        if isinstance(nested, list):
            for position, item in enumerate(nested):
                resolve_ref(args.root, item,
                            "release recovery attempt[%d] evidence[%d]" % (index, position))
                walked += 1
    os.unlink(os.path.join(store.run_dir, name_of_lock))
    return {"command": "release-board", "lock": name_of_lock, "released": True,
            "reverified_records": 1 + len(lineage) + walked}


GENERATION_LINE = re.compile(r"^(generation\s*=\s*)(\d+)(\s*)$", re.MULTILINE)


def cmd_publish_state(args, store: Store, adapters: Adapters) -> dict:
    """Compare-and-swap the state generation. Cooperating writers only.

    The earlier build compared, reported `cas: matched`, and wrote nothing.
    That is worse than no publish at all: every caller believed its state was
    durable. The sequence below is the one `layout.md` specifies - serialize on
    `global:state`, read, compare, write a sibling temp, flush and fsync it,
    re-read and re-verify that nothing moved underneath, then atomically
    replace and flush the directory where that can be established.
    """
    store.require_durability()
    state_dir = os.path.join(args.root, "halucinator")
    path = os.path.join(state_dir, "state.toml")
    try:
        with open(path, "rb") as handle:
            raw = handle.read()
    except OSError as exc:
        raise Refusal(EXIT_USAGE, "cannot read state: %s" % exc)
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise Refusal(EXIT_USAGE, "state is not well-formed TOML: %s" % exc)

    current = data.get("generation")
    if current != args.expect_generation:
        raise Refusal(EXIT_CAS,
                      "state generation is %r, not the expected %r; another writer "
                      "published first. Re-read and retry; nothing was written."
                      % (current, args.expect_generation))
    if not isinstance(current, int) or isinstance(current, bool) or current < 0:
        raise Refusal(EXIT_USAGE,
                      "state generation %r is not a nonnegative integer" % current)

    text = raw.decode("utf-8")
    match = GENERATION_LINE.search(text)
    if match is None or int(match.group(2)) != current:
        raise Refusal(EXIT_USAGE,
                      "state.toml carries no single 'generation = <n>' line this helper "
                      "can advance without rewriting the document")
    updated = (text[:match.start()] + match.group(1) + str(current + 1)
               + match.group(3) + text[match.end():]).encode("utf-8")

    # Serialize on the global state resource for the duration of the swap.
    guard_name = lock_filename("global:state")
    guard_lock = {
        "schema": SCHEMA, "stage": "global:state", "status": "in-progress",
        "kind": "state-update",
        "owner": os.environ.get("USERNAME") or os.environ.get("USER") or "unknown",
        "host": adapters.host(), "pid": os.getpid(),
        "acquired_at": format_rfc3339(adapters.now()),
        "heartbeat_at": format_rfc3339(adapters.now()),
        "resources": sorted(["global:state", "stage:global:state"]),
        "state_generation": current,
        "state_sha256": hashlib.sha256(raw).hexdigest(),
    }
    store.create_new(guard_name, serialize_lock(guard_lock))
    try:
        temp = path + ".tmp-%s" % secrets.token_hex(4)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY | getattr(os, "O_BINARY", 0)
        fd = os.open(temp, flags, 0o644)
        with os.fdopen(fd, "wb") as handle:
            handle.write(updated)
            handle.flush()
            os.fsync(handle.fileno())
        # Re-read and re-verify before replacing: never merge from a stale
        # snapshot, and never overwrite a document that moved underneath us.
        with open(path, "rb") as handle:
            recheck = handle.read()
        if recheck != raw:
            os.unlink(temp)
            raise Refusal(EXIT_CAS,
                          "state.toml changed between the compare and the swap; "
                          "aborting and writing nothing. Re-read and retry.")
        os.replace(temp, path)
        if adapters.directory_fsync_supported(state_dir):
            durability = "directory-flush established"
        else:
            durability = "file flushed; directory flush unavailable on this path"
    finally:
        try:
            os.unlink(os.path.join(store.run_dir, guard_name))
        except OSError:
            pass
    return {"command": "publish-state", "generation": current + 1,
            "previous_generation": current, "cas": "swapped",
            "bytes_written": len(updated), "durability": durability,
            "note": "CAS protects cooperating writers only; it cannot detect tampering "
                    "or reconstruct overwritten history, and crash-atomicity across "
                    "clones remains deferred"}


COMMANDS = {
    "inspect": cmd_inspect,
    "acquire-board": cmd_acquire_board,
    "heartbeat-board": cmd_heartbeat_board,
    "before-board-op": cmd_before_board_op,
    "begin-board-operation": cmd_begin_board_operation,
    "complete-board-operation": cmd_complete_board_operation,
    "set-board-state": cmd_set_board_state,
    "begin-board-recovery": cmd_begin_board_recovery,
    "begin-recovery-operation": cmd_begin_recovery_operation,
    "append-recovery-attempt": cmd_append_recovery_attempt,
    "verify-board-recovery": cmd_verify_board_recovery,
    "override-ambiguous-owner": cmd_override_ambiguous_owner,
    "release-board": cmd_release_board,
    "publish-state": cmd_publish_state,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="runtime.py",
        description="Worktree-local, single-operator board interlock. A strong "
                    "default and a statement of intent, not a sandbox.")
    parser.add_argument("command", choices=sorted(COMMANDS))
    parser.add_argument("--root", required=True)
    parser.add_argument("--stage")
    parser.add_argument("--board")
    parser.add_argument("--authorization")
    parser.add_argument("--epoch")
    parser.add_argument("--token")
    parser.add_argument("--operation")
    parser.add_argument("--operation-id", dest="operation_id")
    parser.add_argument("--child-kind", dest="child_kind", default="process-group",
                        choices=["windows-job", "process-group", "external"])
    parser.add_argument("--child-identity", dest="child_identity", default="")
    parser.add_argument("--state", choices=["unknown", "safe", "active"])
    parser.add_argument("--safe-state", dest="safe_state")
    parser.add_argument("--attempt-file", dest="attempt_file")
    parser.add_argument("--attempt-number", dest="attempt_number", type=int)
    parser.add_argument("--outcome", choices=["interrupted", "failed", "verified"])
    parser.add_argument("--override-record", dest="override_record")
    parser.add_argument("--expect-generation", dest="expect_generation", type=int)
    return parser


REQUIRED_ARGS = {
    "acquire-board": ("stage", "board", "authorization"),
    "heartbeat-board": ("stage", "epoch", "token"),
    "before-board-op": ("stage", "epoch", "token"),
    "begin-board-operation": ("stage", "epoch", "token", "operation"),
    "begin-recovery-operation": ("stage", "epoch", "token", "operation"),
    "complete-board-operation": ("stage", "epoch", "token", "operation_id"),
    "set-board-state": ("stage", "epoch", "token", "state"),
    "begin-board-recovery": ("stage", "epoch", "token"),
    "append-recovery-attempt": ("stage", "epoch", "token", "attempt_file",
                                "attempt_number", "outcome"),
    "verify-board-recovery": ("stage", "epoch", "token", "safe_state"),
    "override-ambiguous-owner": ("stage", "override_record"),
    "release-board": ("stage", "epoch", "token"),
    "publish-state": ("expect_generation",),
}


def main(argv: list[str]) -> int:
    args = build_parser().parse_args(argv)
    try:
        for name in REQUIRED_ARGS.get(args.command, ()):
            if getattr(args, name, None) is None:
                raise Refusal(EXIT_USAGE,
                              "%s requires --%s" % (args.command, name.replace("_", "-")))
        if not os.path.isdir(args.root):
            raise Refusal(EXIT_USAGE, "root %r is not a directory" % args.root)
        adapters = Adapters.from_environment()
        store = Store(os.path.join(args.root, "halucinator", ".run"), adapters)
        result = COMMANDS[args.command](args, store, adapters)
        print(json.dumps(result, sort_keys=True))
        return EXIT_OK
    except Refusal as refusal:
        print(json.dumps({"command": args.command, "refused": str(refusal),
                          "exit": refusal.code}, sort_keys=True), file=sys.stderr)
        return refusal.code


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
