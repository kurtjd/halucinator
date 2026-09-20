#!/usr/bin/env python3
"""Validator for halucinator pipeline handoff artifacts.

Implements the contract in `.opencode/schema/validate.md`.

Structure
---------
* ``Diag`` / ``Reporter``      -- diagnostic vocabulary and sorted stderr emission.
* ``Limits`` / ``Loader``      -- resource bounds, bounded raw-byte reads, TOML parsing.
* path helpers                 -- component-safe PathRef validation and root resolution.
* ``SPEC``-style declarations  -- per-kind table/field schemas and canonical check sets.
* ``validate_*`` functions     -- structural, coverage, evidence, dependency, review,
                                 scope-chain, state and lock rules.
* ``main``                     -- CLI, root bindings, exit codes (0 ok, 1 invalid, 2 env).

Standard library only.
"""

from __future__ import annotations

import difflib
import hashlib
import os
import pathlib
import re
import shlex
import subprocess
import sys
import tomllib
import unicodedata

# --------------------------------------------------------------------------
# Diagnostics
# --------------------------------------------------------------------------

SCHEMA_VERSION_CURRENT = 2

CODES = {
    "UNKNOWN_FIELD", "MISSING_FIELD", "ILLEGAL_ENUM", "DEPENDENCY_NOT_READY",
    "INPUT_HASH_MISMATCH", "STALE_EVIDENCE", "STALE_REVIEW", "HANDOFF_IN_PROGRESS",
    "LOCK_COMPLETE_CONFLICT", "NARROWED_READY_SCOPE", "PATH_ESCAPE",
    "NONCANONICAL_DIGEST", "MALFORMED_LOCK", "REVIEW_NONACCEPTING",
    "DRIVER_API_LEAK", "CHECK_MISSING", "NOT_APPLICABLE_NO_REASON",
    "COVERAGE_PARTITION", "ROUTE_INCOMPATIBILITY", "DEPENDENCY_IDENTITY",
    "LOCK_ID_UNSAFE", "SCHEMA_VERSION", "FIRST_PERIPHERAL_MODES",
    "FOUNDATION_PARTITION", "SCOPE_DELETED_PREDECESSOR", "SCOPE_SECOND_INITIAL",
    "SCOPE_FORK", "SCOPE_ORPHAN", "SCOPE_CYCLE", "RESOURCE_LIMIT",
    "PATH_INSPECTION", "ATTRIBUTES_UNVERIFIED",
    # M6 (schema 2), approved subset only.
    "CITATION_UNVERIFIED", "BOARD_INTERLOCK_CONFLICT", "BOARD_RECOVERY_REQUIRED",
}



def _repr160(value) -> str:
    text = repr(value)
    return text if len(text) <= 160 else text[:157] + "..."


class Reporter:
    def __init__(self) -> None:
        self.lines: set[str] = set()

    def emit(self, where: str, field: str, code: str, expectation: str,
             found, remedy: str) -> None:
        assert code in CODES, code
        self.lines.add(
            "ERROR %s:%s [%s] expected %s; found %s; action: %s"
            % (where, field or "-", code, expectation, _repr160(found), remedy)
        )

    def flush(self) -> int:
        for line in sorted(self.lines):
            print(line, file=sys.stderr)
        return 1 if self.lines else 0


class Fatal(Exception):
    """Invocation / environment failure -> exit 2."""


# --------------------------------------------------------------------------
# Resource bounds
# --------------------------------------------------------------------------

class Limits:
    MAX_SCHEMA_TOML = 256
    MAX_REFERENCED = 4096
    MAX_TEXT_BYTES = 8 * 1024 * 1024
    MAX_OPAQUE_BYTES = 64 * 1024 * 1024
    MAX_DEPTH = 12
    MAX_ARRAY = 4096
    MAX_STRING = 64 * 1024
    MAX_COMPONENTS = 64


TEXT_SUFFIXES = {".toml", ".md", ".lock"}


class Loader:
    """Bounded raw-byte reads, hashing and TOML parsing with a shared budget."""

    def __init__(self, rep: Reporter) -> None:
        self.rep = rep
        self.schema_toml = 0
        self.referenced = 0
        self._hash_cache: dict[str, str | None] = {}

    # -- budget ----------------------------------------------------------
    def count_schema_toml(self, where: str) -> bool:
        self.schema_toml += 1
        if self.schema_toml > Limits.MAX_SCHEMA_TOML:
            self.rep.emit(where, "-", "RESOURCE_LIMIT",
                          "at most %d schema TOML files" % Limits.MAX_SCHEMA_TOML,
                          self.schema_toml, "reduce the number of schema artifacts")
            return False
        return True

    def count_referenced(self, where: str) -> bool:
        self.referenced += 1
        if self.referenced > Limits.MAX_REFERENCED:
            self.rep.emit(where, "-", "RESOURCE_LIMIT",
                          "at most %d referenced files" % Limits.MAX_REFERENCED,
                          self.referenced, "reduce the number of referenced files")
            return False
        return True

    # -- io --------------------------------------------------------------
    def read_bytes(self, abspath: str, where: str, field: str) -> bytes | None:
        try:
            st = os.lstat(abspath)
        except OSError as exc:
            self.rep.emit(where, field, "PATH_INSPECTION",
                          "an inspectable existing file", str(exc),
                          "restore the referenced file or fix the path")
            return None
        if hasattr(st, "st_file_attributes") and (
            st.st_file_attributes & getattr(os.stat_result, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
        ):
            self.rep.emit(where, field, "PATH_INSPECTION",
                          "a regular file, not a reparse point", abspath,
                          "replace the reparse point with a regular file")
            return None
        if not os.path.isfile(abspath):
            self.rep.emit(where, field, "PATH_INSPECTION",
                          "a regular file (directories cannot be hashed)", abspath,
                          "reference a file rather than a directory")
            return None
        suffix = os.path.splitext(abspath)[1].lower()
        cap = Limits.MAX_TEXT_BYTES if suffix in TEXT_SUFFIXES else Limits.MAX_OPAQUE_BYTES
        if st.st_size > cap:
            self.rep.emit(where, field, "RESOURCE_LIMIT",
                          "file at most %d bytes" % cap, st.st_size,
                          "shrink or split the referenced file")
            return None
        try:
            with open(abspath, "rb") as handle:
                return handle.read()
        except OSError as exc:
            raise Fatal("cannot read %s: %s" % (abspath, exc))

    def sha256(self, abspath: str, where: str, field: str) -> str | None:
        if abspath in self._hash_cache:
            return self._hash_cache[abspath]
        data = self.read_bytes(abspath, where, field)
        digest = hashlib.sha256(data).hexdigest() if data is not None else None
        self._hash_cache[abspath] = digest
        return digest

    def load_toml(self, abspath: str, where: str) -> dict | None:
        data = self.read_bytes(abspath, where, "-")
        if data is None:
            return None
        try:
            return tomllib.loads(data.decode("utf-8"))
        except (tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
            self.rep.emit(where, "-", "MALFORMED_LOCK" if where.endswith(".lock")
                          else "UNKNOWN_FIELD",
                          "a well-formed UTF-8 TOML document", str(exc),
                          "repair the TOML syntax")
            return None


# --------------------------------------------------------------------------
# Path handling
# --------------------------------------------------------------------------

WIN_RESERVED = {"CON", "PRN", "AUX", "NUL", "CLOCK$"} | \
    {"COM%d" % i for i in range(1, 10)} | {"LPT%d" % i for i in range(1, 10)}

ROOT_NAME_RE = re.compile(r"^generation:[a-z][a-z0-9-]{0,31}$")
SHA_RE = re.compile(r"^[0-9a-f]{64}$")
SCOPE_REV_RE = re.compile(r"^scope-[0-9a-f]{8}$")
SCOPE_ITEM_RE = re.compile(r"^[a-z][a-z0-9]*(?:[.-][a-z0-9]+)*:[a-z0-9][a-z0-9._-]*$")
ASSERTION_ID_RE = re.compile(r"^[a-z][a-z0-9._-]{2,79}$")


def path_problem(rel: str) -> str | None:
    """Return a reason string when `rel` violates layout.md, else None."""
    if not isinstance(rel, str) or rel == "":
        return "a nonempty relative path"
    if rel == ".":
        return None
    if "\\" in rel or ":" in rel or "\0" in rel:
        return "no backslash, colon or NUL"
    if "%2f" in rel.lower() or "%5c" in rel.lower():
        return "no percent-encoded separator"
    parts = rel.split("/")
    if len(parts) > Limits.MAX_COMPONENTS:
        return "at most %d path components" % Limits.MAX_COMPONENTS
    for part in parts:
        if part in ("", ".", ".."):
            return "no empty, '.' or '..' segment"
        if part.endswith(" ") or part.endswith("."):
            return "no segment ending in space or dot"
        if part.split(".")[0].upper() in WIN_RESERVED:
            return "no Windows reserved device name"
    return None


def contained(root_abs: str, target_abs: str) -> bool:
    """Component-safe containment: never a string-prefix test."""
    rdrive, rtail = os.path.splitdrive(os.path.abspath(root_abs))
    tdrive, ttail = os.path.splitdrive(os.path.abspath(target_abs))
    if os.path.normcase(rdrive) != os.path.normcase(tdrive):
        return False
    rparts = [p for p in pathlib.PurePath(rtail).parts]
    tparts = [p for p in pathlib.PurePath(ttail).parts]
    if len(tparts) < len(rparts):
        return False
    for a, b in zip(rparts, tparts):
        if os.path.normcase(a) != os.path.normcase(b):
            return False
    try:
        common = os.path.commonpath([os.path.abspath(root_abs), os.path.abspath(target_abs)])
    except ValueError:
        return False
    return os.path.normcase(common) == os.path.normcase(os.path.abspath(root_abs))


class Roots:
    def __init__(self, repo_root: str, bindings: dict[str, str]) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self.bindings = bindings
        self.used: set[str] = set()

    def base(self, root_name: str | None) -> str | None:
        if root_name is None:
            return self.repo_root
        self.used.add(root_name)
        return self.bindings.get(root_name)


# --------------------------------------------------------------------------
# Schema declarations
# --------------------------------------------------------------------------

def S(kind, **kw):
    spec = {"type": kind}
    spec.update(kw)
    return spec


FILEREF = S("fileref")
PATHREF = S("pathref")
STR = S("str")
STRS = S("array", items=STR)
SORTED_STRS = S("array", items=STR, sorted_unique=True)
SCOPE_ITEMS = S("array", items=S("scopeitem"), sorted_unique=True)

DEPENDENCY = S("struct", fields={
    "crate": (STR, True), "identity": (S("str", allow_empty=True), True),
    "features": (SORTED_STRS, True)})

CITATION = S("struct", fields={
    "assertion_id": (S("assertionid"), True),
    "scope_item": (S("scopeitem"), True),
    "claim": (STR, True),
    "source_id": (STR, True),
    "source": (FILEREF, True),
    "location": (S("tagged", variants={
        "pdf-page": {"page": (S("int"), True)},
        "text-lines": {"line_start": (S("int"), True),
                       "line_end": (S("int"), True)}}), True),
    "locator": (S("struct", fields={
        "kind": (S("enum", values=["page", "section", "table", "figure"]), True),
        "value": (STR, True)}), True),
    "excerpt": (STR, True),
    "note": (FILEREF, True)})

SOURCE_DOCUMENT = S("struct", fields={
    "source_id": (STR, True), "document": (STR, True), "revision": (STR, True),
    "format": (S("enum", values=["pdf", "utf8-text"]), True),
    "source": (FILEREF, True)})

SAFE_STATE_PROCEDURE = S("struct", fields={
    "board_id": (STR, True),
    "facts_handoff": (FILEREF, True),
    "assertion_ids": (S("array", items=S("assertionid"), sorted_unique=True,
                        nonempty=True), True),
    "procedure": (FILEREF, True)})

BOARD_INTERLOCK = S("struct", fields={
    "board_id": (STR, True),
    "lease_epoch": (S("hex", width=32), True),
    "check_token": (S("hex", width=64), True),
    "authorization": (FILEREF, True)})


HANDOFF_TABLE = {
    "schema": (S("int"), True),
    "stage": (S("enum", values=["gather-documentation", "extract-facts", "generate-svd",
                                "generate-pac", "scaffold-hal", "write-driver",
                                "write-tests", "review"]), True),
    "status": (S("enum", values=["ready", "partial", "blocked"]), True),
    "can_progress": (S("bool"), False),
    "inputs": (S("array", items=FILEREF), True),
    "notes": (S("array", items=FILEREF), True),
    "blockers": (STRS, True),
}
SCOPE_TABLE = {"revision": (S("scoperev"), True), "decision": (FILEREF, True)}
COVERAGE_TABLE = {"complete": (SCOPE_ITEMS, True), "incomplete": (SCOPE_ITEMS, True)}


def check_applicable_always(_h):
    return True


KINDS: dict[str, dict] = {
    "01-sources": {
        "stage": "gather-documentation", "table": "sources",
        "fields": {
            "catalog": (FILEREF, True),
            "route": (S("enum", values=["review-supplied", "author-from-docs", "unresolved"]), True),
            "documents": (S("array", items=SOURCE_DOCUMENT, nonempty=True), True),
            "cited_notes": (S("array", items=FILEREF), True),
        },
        "checks": {
            "requested-inputs-accounted": check_applicable_always,
            "available-content-resolves": check_applicable_always,
            "local-source-hashes": lambda h: bool(h.get("sources", {}).get("documents")),
            "svd-search-complete": lambda h: h.get("sources", {}).get("route") == "author-from-docs",
        },
    },
    "02-facts": {
        "stage": "extract-facts", "table": "facts",
        "fields": {
            "notes": (S("array", items=FILEREF, nonempty=True), True),
            "citations": (S("array", items=CITATION), True),
            "categories": (S("array", items=S("enum", values=[
                "register-layout", "field-encodings", "dependencies", "interrupts",
                "errata", "pin-mux", "memory-runtime"]), sorted_unique=True), True),
            "contradictions": (STRS, True),
        },
        "checks": {
            "citations-complete": check_applicable_always,
            "citations-verified":
                lambda h: bool(h.get("facts", {}).get("citations")),
            "summary-field-cross-check":
                lambda h: "register-layout" in h.get("facts", {}).get("categories", []),
            "field-encodings-exhaustive":
                lambda h: "field-encodings" in h.get("facts", {}).get("categories", []),
            "pdf-layout-extraction": lambda h: any(
                str(r.get("path", "")).lower().endswith(".pdf")
                for r in h.get("handoff", {}).get("inputs", []) if isinstance(r, dict)),
        },
    },
    "03-svd": {
        "stage": "generate-svd", "table": "svd",
        "fields": {
            "route": (S("enum", values=["review-supplied", "author-from-docs"]), True),
            "source": (FILEREF, True),
            "transforms": (S("array", items=FILEREF), True),
            "includes": (S("array", items=FILEREF), True),
            "prepared_manifest": (FILEREF, False),
            "extraction_mode": (S("enum", values=["peripheral", "block"]), True),
            "namespace_mode": (S("enum", values=["none", "block", "block-with-regs-vals"]), True),
            "representation_limits": (STRS, True),
            "unresolved_facts": (STRS, True),
        },
        "checks": {
            "input-identity": check_applicable_always,
            "xml-well-formed": check_applicable_always,
            "schema-validation": check_applicable_always,
            "source-fact-comparison": check_applicable_always,
            "correction-effects": lambda h: bool(h.get("svd", {}).get("transforms")),
            "structural-inventory": check_applicable_always,
            "information-limits": check_applicable_always,
            "preparation-replay": check_applicable_always,
        },
    },
    "04-pac": {
        "stage": "generate-pac", "table": "pac",
        "fields": {
            "crate_manifest": (FILEREF, True),
            "package": (STR, True),
            "revision": (S("tagged", variants={
                "revision": {"value": (STR, True)}, "workspace": {}}), True),
            "cargo_chip_feature": (STR, True),
            "runtime_features": (SORTED_STRS, True),
            "metadata_features": (SORTED_STRS, True),
            "rust_compilation_target": (STR, True),
            "source_ids": (SORTED_STRS, True),
            "cited_notes": (S("array", items=FILEREF), True),
            "temporary_fork": (S("bool"), True),
            "foundation": (S("array", items=S("struct", fields={
                "id": (S("scopeitem"), True), "kind": (S("enum", values=[
                    "api", "metadata", "runtime", "link", "fact"]), True),
                "location": (STR, True),
                "status": (S("enum", values=["covered", "missing"]), True),
                "evidence": (FILEREF, False)})), True),
        },
        "checks": {
            "input-identity": check_applicable_always,
            "expected-inventory": check_applicable_always,
            "representation-limits": check_applicable_always,
            "target-build-api": check_applicable_always,
            "host-metadata-api": lambda h: bool(h.get("pac", {}).get("metadata_features")),
            "negative-chip-selection": lambda h: bool(h.get("pac", {}).get("cargo_chip_feature")),
            "pure-host-tests": None,
            "format-lint": check_applicable_always,
            "generation-replay": check_applicable_always,
            "final-path-build": check_applicable_always,
            "independent-review": check_applicable_always,
        },
        "review_artifact": ("pac", "crate_manifest"),
    },
    "05-platform": {
        "stage": "scaffold-hal", "table": "platform",
        "fields": {
            "crate_manifest": (FILEREF, True),
            "roadmap": (FILEREF, True),
            "startup_clock_contract": (FILEREF, True),
            "supporting_subsystems": (S("array", items=S("scopeitem")), True),
            "foundation_api": (STRS, True),
            "pac_manifest": (FILEREF, True),
            "source_ids": (SORTED_STRS, True),
            "cited_notes": (S("array", items=FILEREF), True),
            "dependencies": (S("array", items=DEPENDENCY), True),
            "first_driver": (STR, True),
            "first_driver_modes": (S("array", items=STR, nonempty=True), True),
        },
        "checks": {
            "live-reference-read": check_applicable_always,
            "foundation-coverage": check_applicable_always,
            "format-lint": check_applicable_always,
            "advertised-builds": check_applicable_always,
            "negative-chip-selection": None,
            "pure-host-tests": None,
            "generated-mappings": check_applicable_always,
            "target-link": check_applicable_always,
            "build-only-ci": check_applicable_always,
            "independent-review": check_applicable_always,
        },
        "review_artifact": ("platform", "crate_manifest"),
    },
    "06-driver": {
        "stage": "write-driver", "table": "driver",
        "fields": {
            "name": (STR, True),
            "scope_kind": (S("enum", values=["full", "scaffold-support"]), True),
            "owned_files": (S("array", items=FILEREF), True),
            "capabilities": (STRS, True),
            "public_api": (STRS, True),
            "dependencies": (S("array", items=DEPENDENCY), True),
            "trait_obligations": (S("array", items=S("struct", fields={
                "dependency_crate": (STR, True), "trait": (STR, True),
                "obligations": (STRS, True)})), True),
            "facts_handoff": (FILEREF, True),
            "test_hardware_facts": (S("array", items=S("assertionid"),
                                      sorted_unique=True), True),
            "build_contract": (S("struct", fields={
                "cargo_chip_feature": (STR, True),
                "rust_compilation_target": (STR, True),
                "init_calls": (STRS, True),
                "memory_runtime": (FILEREF, True),
                "observation": (STR, True)}), True),
            "requirement_ids": (STRS, True),
            "public_test_record": (FILEREF, False),
        },
        "checks": {
            "live-reference-read": check_applicable_always,
            "format-lint-build": check_applicable_always,
            "pure-host-tests": None,
            "trait-conformance": lambda h: bool(h.get("driver", {}).get("trait_obligations")),
            "generated-mappings": None,
            "target-link-ci": check_applicable_always,
            "independent-review": check_applicable_always,
        },
        "review_artifact": None,
    },
    "07-tests": {
        "stage": "write-tests", "table": "tests",
        "fields": {
            "name": (STR, True),
            "output_kind": (S("enum", values=["example", "validation", "both"]), True),
            "execution_scope": (S("enum", values=["build-only", "hardware-validation"]), True),
            "api_handoff": (FILEREF, True),
            "owned_files": (S("array", items=FILEREF), True),
            "dependencies": (S("array", items=DEPENDENCY), True),
            "setup_record": (FILEREF, False),
            "review_input_manifest": (FILEREF, True),
            "board_interlock": (BOARD_INTERLOCK, False),
            "safe_state_procedure": (SAFE_STATE_PROCEDURE, False),
            "recovery_attempts": (S("array", items=FILEREF), False),
            "coverage": (S("array", items=S("struct", fields={
                "id": (STR, True),
                "status": (S("enum", values=[
                    "passed", "failed", "blocked", "not-applicable"]), True),
                "test_case": (STR, True),
                "evidence": (FILEREF, False),
                "reason": (STR, False)})), True),
            "hardware_runs": (S("array", items=S("struct", fields={
                "test_case": (STR, True),
                "status": (S("enum", values=[
                    "passed", "failed", "blocked", "not-run"]), True),
                "evidence": (FILEREF, False),
                "teardown": (STR, True),
                "lease_epoch": (S("hex", width=32), False),
                "operation_attempt": (S("int"), False),
                "operation_id": (S("hex", width=32), False),
                "pre_safe_state": (FILEREF, False),
                "post_safe_state": (FILEREF, False)})), True),
        },
        "checks": {
            "workflow-references-read": check_applicable_always,
            "live-conventions-read": check_applicable_always,
            "format-lint": check_applicable_always,
            "target-build-link": check_applicable_always,
            "build-only-ci": check_applicable_always,
            "hardware-admission":
                lambda h: h.get("tests", {}).get("execution_scope") == "hardware-validation",
            "hardware-execution":
                lambda h: h.get("tests", {}).get("execution_scope") == "hardware-validation",
            "independent-review": check_applicable_always,
        },
        "review_artifact": ("tests", "review_input_manifest"),
    },
    "08-review": {
        "stage": "review", "table": "review",
        "fields": {
            "artifact_id": (STR, True),
            "artifact": (FILEREF, True),
            "scope": (S("array", items=S("scopeitem")), True),
            "unreviewed": (S("array", items=S("scopeitem")), True),
            "dependencies": (S("array", items=FILEREF), True),
            "findings": (S("array", items=S("struct", fields={
                "severity": (S("enum", values=[
                    "blocking", "convention", "api", "contract", "unverified"]), True),
                "location": (STR, True), "summary": (STR, True), "owner": (STR, True),
                "status": (S("enum", values=["open", "resolved", "not-applicable"]), True)})), True),
            "verdict": (S("enum", values=["ready", "ready-with-fixes", "not-ready"]), True),
            "lineage": (S("tagged", variants={
                "initial": {}, "recheck": {"previous": (FILEREF, True)}}), True),
        },
        "checks": {
            "applicable-references-read": check_applicable_always,
            "artifact-identity": check_applicable_always,
            "hardware-claims-cited": lambda h: any(
                str(i).startswith("hardware:") or str(i).startswith("foundation:fact-")
                for i in h.get("review", {}).get("scope", [])),
            "upstream-contracts-reviewed": None,
        },
        "review_artifact": None,
    },
}

STATE_SCHEMA = {
    "schema": (S("int"), True),
    "generation": (S("int"), True),
    "target": (S("struct", fields={
        "vendor": (STR, True), "mcu_part_number": (STR, True),
        "target_id": (STR, True), "vendor_id": (STR, True),
        "package": (S("tagged", variants={
            "known": {"value": (STR, True)}, "unknown": {}, "not-applicable": {}}), True),
        "silicon_revision": (STR, False), "core": (STR, False),
        "board": (STR, False), "board_revision": (STR, False)}), True),
    "scope": (S("struct", fields={
        "current_revision": (S("scoperev"), True),
        "current_decision": (FILEREF, True)}), True),
    "decisions": (S("struct", fields={
        "cargo_chip_feature": (STR, False),
        "rust_compilation_target": (STR, False),
        "destination_crate": (PATHREF, False),
        "first_peripheral": (STR, False),
        "first_peripheral_modes": (STRS, False),
        "foundation_requirements": (S("array", items=S("struct", fields={
            "id": (S("scopeitem"), True),
            "kind": (S("enum", values=["api", "metadata", "runtime", "link", "fact"]), True),
            "location": (STR, True)})), True)}), True),
    "roots": (S("struct", fields={
        "documentation": (PATHREF, False), "sources": (PATHREF, False),
        "pac_project": (PATHREF, False), "svd_inputs": (PATHREF, False),
        "generator": (PATHREF, False), "pac_crate": (PATHREF, False),
        "roadmap": (PATHREF, False),
        "generation": (S("array", items=S("struct", fields={
            "name": (STR, True), "authorization": (FILEREF, True)})), True)}), True),
    "stages": (S("array", items=S("struct", fields={
        "id": (STR, True),
        "status": (S("enum", values=["ready", "partial", "blocked"]), True),
        "handoff": (FILEREF, True)})), True),
}

SCOPE_SCHEMA = {
    "schema": (S("int"), True),
    "revision": (S("scoperev"), True),
    "previous": (S("tagged", variants={
        "initial": {},
        "revision": {"revision": (S("scoperev"), True), "decision": (FILEREF, True)}}), True),
    "included": (SCOPE_ITEMS, True),
    "excluded": (SCOPE_ITEMS, True),
    "reason": (STR, True),
}

LOCK_SCHEMA = {
    "schema": (S("int"), True),
    "stage": (STR, True),
    "status": (S("enum", values=["in-progress"]), True),
    "kind": (S("enum", values=[
        "stage", "board-test", "pac-integration", "state-update"]), True),
    "owner": (STR, True),
    "host": (STR, True),
    "pid": (S("int"), True),
    "acquired_at": (STR, True),
    "heartbeat_at": (STR, True),
    "resources": (SORTED_STRS, True),
    "state_generation": (S("int"), False),
    "state_sha256": (S("str"), False),
    "board_id": (STR, False),
    "authorization": (FILEREF, False),
    "board_state": (S("enum", values=["unknown", "safe", "active"]), False),
    "canonical": (PATHREF, False),
    "candidate": (PATHREF, False),
    # Schema 2 worktree-local interlock members. The word "lease" survives only
    # in these field names for compact identity; the mechanism is a
    # worktree-local, single-operator interlock, never a lease or a broker.
    "lease_epoch": (S("hex", width=32), False),
    "check_token": (S("hex", width=64), False),
    "owner_process_identity": (S("struct", fields={
        "scheme": (S("enum", values=[
            "windows-filetime", "linux-startticks", "unavailable"]), True),
        "value": (S("str", allow_empty=True), False)}), False),
    "operation_phase": (S("enum", values=[
        "acquired", "preparing", "active", "teardown",
        "recovery-pending", "recovery-verified"]), False),
    "operation_attempt": (S("int"), False),
    "operation_id": (S("hex", width=32), False),
    "last_operation": (S("enum", values=[
        "none", "attach", "reset", "load-ram", "program-flash", "run",
        "halt", "detach", "power-change", "fixture-change"]), False),
    "child_session": (S("struct", fields={
        "kind": (S("enum", values=["windows-job", "process-group", "external"]), True),
        "identity": (STR, True),
        "started_at": (STR, True),
        "completed_at": (STR, False)}), False),
    "safe_state": (FILEREF, False),
    "recovery_attempts": (S("array", items=FILEREF), False),
    "override_record": (FILEREF, False),
}

# A repository-root destination crate is exactly one path segment named
# `embassy-<vendor_id>`. Nesting, aliases and named roots are refused with the
# existing ILLEGAL_ENUM; no extra diagnostic was approved for A18.
DESTINATION_CRATE_RE = re.compile(r"^embassy-[a-z0-9]+(?:-[a-z0-9]+)*$")


FORBIDDEN_API_TOKENS = ("pac::", "unsafe {")

REQUIRED_ATTRS = [
    "halucinator/state.toml text eol=lf",
    "halucinator/scope/*.toml text eol=lf",
    "halucinator/handoff/*.toml text eol=lf",
    "halucinator/docs/**/*.md text eol=lf",
    "halucinator/docs/**/sources/** -text",
    "halucinator/pac/** -text",
    "halucinator/candidates/** text eol=lf",
    "halucinator/.run/*.lock text eol=lf",
    "examples/** text eol=lf",
    "embassy-unobtainium/** text eol=lf",
]


# --------------------------------------------------------------------------
# Citation verification (schema 2)
#
# `run_pdftotext` is the ONLY function in this file permitted to invoke an
# external program. Everything else is Python 3.11 standard library and starts
# no process. The gate fails closed: a missing binary makes the citation check
# FAIL, never skip, because a gate bypassable by uninstalling a binary is not a
# gate. The diagnostic therefore always names the remedy.
# --------------------------------------------------------------------------

PDFTOTEXT_TIMEOUT = 30
PDFTOTEXT_MAX_BYTES = 16 * 1024 * 1024
EXCERPT_MIN_CODEPOINTS = 32
EXCERPT_MAX_CODEPOINTS = 4096
EXCERPT_MIN_ALNUM = 8
EXCERPT_MAX_TOKENS = 256
SOURCE_MAX_TOKENS = 100_000
MAX_TOKEN_GAP = 8
MAX_PAYLOAD_BYTES = 2048
# Declared work bounds. Reaching one emits RESOURCE_LIMIT - a loud, nameable
# outcome - and NEVER a silent "not found": reporting absence about a region we
# did not finish searching is exactly the false rejection these replaced.
MATCH_WORK_BUDGET = 20_000_000
CANDIDATE_WORK_BUDGET = 2_000_000
CANDIDATE_PREFILTER_KEEP = 32

PDFTOTEXT_REMEDY = (
    "Install poppler-utils (or xpdf-utils where that package supplies "
    "pdftotext), then rerun: pdftotext -layout -f <page> -l <page> <source> -")


class CitationFailure(Exception):
    """A citation could not be verified. Carries the bounded operator payload."""

    def __init__(self, field: str, reason: str, remedy: str) -> None:
        super().__init__(reason)
        self.field = field
        self.reason = reason
        self.remedy = remedy


def run_pdftotext(source_abs: str, page: int) -> str:
    """Derive one physical PDF page as text. The single external-program call."""
    cmd = ["pdftotext", "-layout", "-f", str(page), "-l", str(page), source_abs, "-"]
    display = " ".join(shlex.quote(part) for part in cmd)
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=PDFTOTEXT_TIMEOUT)
    except FileNotFoundError:
        raise CitationFailure(
            "", "pdftotext is not installed or not on PATH (attempted %s)" % display,
            PDFTOTEXT_REMEDY)
    except subprocess.TimeoutExpired:
        raise CitationFailure(
            "", "pdftotext did not finish in %ds (attempted %s)"
                % (PDFTOTEXT_TIMEOUT, display),
            "shrink or replace the source PDF, then rerun: " + display)
    except OSError as exc:
        raise CitationFailure(
            "", "pdftotext could not be executed: %s (attempted %s)" % (exc, display),
            PDFTOTEXT_REMEDY)
    if proc.returncode != 0:
        tail = _clip(proc.stderr.decode("utf-8", "replace"), 512)
        raise CitationFailure(
            "", "pdftotext exited %d (attempted %s); stderr: %s"
                % (proc.returncode, display, tail),
            "correct the physical page ordinal or the source, then rerun: " + display)
    if len(proc.stdout) > PDFTOTEXT_MAX_BYTES:
        raise CitationFailure(
            "", "pdftotext produced %d bytes, over the %d-byte cap (attempted %s)"
                % (len(proc.stdout), PDFTOTEXT_MAX_BYTES, display),
            "cite a narrower page, then rerun: " + display)
    try:
        return proc.stdout.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise CitationFailure(
            "", "pdftotext output is not valid UTF-8: %s (attempted %s)" % (exc, display),
            "supply a text-capable authoritative source, then rerun: " + display)


def _clip(text: str, limit: int) -> str:
    raw = text.encode("utf-8", "replace")
    if len(raw) <= limit:
        return text
    return raw[:limit].decode("utf-8", "ignore") + "\u2026"


def _is_hspace(ch: str) -> bool:
    return ch == "\t" or unicodedata.category(ch) == "Zs"


def _is_letter_or_mark(ch: str) -> bool:
    return unicodedata.category(ch)[0] in ("L", "M")


def _rejoin_line_end_hyphens(text: str) -> str:
    """Rejoin a line-end ASCII hyphen only between letters/marks.

    Never between digits: `FIFO-\\n0` must stay two tokens, and a digit-bearing
    range such as `0x1-0x3` must never be altered.
    """
    out: list[str] = []
    index = 0
    length = len(text)
    while index < length:
        ch = text[index]
        if ch == "-":
            after_hyphen = index + 1
            while after_hyphen < length and _is_hspace(text[after_hyphen]):
                after_hyphen += 1
            if after_hyphen < length and text[after_hyphen] == "\n":
                resume = after_hyphen + 1
                while resume < length and _is_hspace(text[resume]):
                    resume += 1
                before = index - 1
                while before >= 0 and _is_hspace(text[before]):
                    before -= 1
                left = text[before] if before >= 0 else ""
                right = text[resume] if resume < length else ""
                if left and right and _is_letter_or_mark(left) and _is_letter_or_mark(right):
                    index = resume
                    continue
        out.append(ch)
        index += 1
    return "".join(out)


def normalize_citation_text(text: str) -> str:
    """NFKC, casefold, soft-hyphen removal, line joining, whitespace collapse."""
    text = unicodedata.normalize("NFKC", text).casefold()
    text = text.replace("\u00ad", "")
    for separator in ("\r\n", "\r", "\u0085", "\u2028", "\u2029"):
        text = text.replace(separator, "\n")
    text = _rejoin_line_end_hyphens(text)
    return " ".join(text.split())


def citation_tokens(text: str) -> list[str]:
    """Maximal word-token runs; every other non-space code point is its own token."""
    out: list[str] = []
    run: list[str] = []
    for ch in text:
        category = unicodedata.category(ch)
        if category[0] in ("L", "M", "N") or category == "Pc":
            run.append(ch)
            continue
        if run:
            out.append("".join(run))
            run = []
        if not ch.isspace():
            out.append(ch)
    if run:
        out.append("".join(run))
    return out


def ordered_token_match(excerpt: list[str], source: list[str]) -> bool | None:
    """Exact ordered occurrence with bounded gaps, tolerating column interleaving.

    EVERY viable start is inspected. An earlier build capped the search at the
    first 4096 occurrences of the excerpt's leading token, which false-rejected
    an honest excerpt beginning with a common word after occurrence 4096 - and
    a gate that false-rejects honest evidence is a gate people route around,
    which is worse than a gate that is slightly wide.

    Returns True (matched), False (searched exhaustively, no match), or None
    (the declared work bound was reached). None is NOT "no match": the caller
    emits RESOURCE_LIMIT, because saying "absent" about a region we did not
    finish searching is the false rejection this exists to prevent.

    Greedy-earliest from a fixed start is optimal here: taking the nearest
    admissible next token minimizes both the cursor position and the cumulative
    skip, so it can never lose a match a later choice would have found.

    This DELIBERATELY broadens what a fabricated excerpt could match. It proves
    ordered normalized token occurrence under the stated gap bound, not visual
    contiguity and not semantic support. Excerpt tokens `reset value zero` do
    match source tokens `reset unrelated value unrelated zero`; that is the
    accepted, disclosed consequence of aggressive normalization, and comparing
    the claim against the rendered page remains a human obligation.
    """
    if not excerpt:
        return False
    budget = min(EXCERPT_MAX_TOKENS, 2 * len(excerpt))
    first = excerpt[0]
    work = 0
    for start, token in enumerate(source):
        if token != first:
            continue
        cursor = start + 1
        skipped = 0
        matched = 1
        for want in excerpt[1:]:
            step = 0
            # `step < MAX_TOKEN_GAP`, not `<=`: the bound is at most eight
            # NONMATCHING tokens between adjacent excerpt tokens, and `<=`
            # admitted nine, making the gate one token wider than the approved
            # algorithm.
            while cursor < len(source) and step < MAX_TOKEN_GAP and source[cursor] != want:
                cursor += 1
                step += 1
                work += 1
                if work > MATCH_WORK_BUDGET:
                    return None
            if cursor >= len(source) or source[cursor] != want:
                break
            skipped += step
            if skipped > budget:
                break
            cursor += 1
            matched += 1
        work += len(excerpt)
        if work > MATCH_WORK_BUDGET:
            return None
        if matched == len(excerpt) and skipped <= budget:
            return True
    return False


def nearest_candidate(excerpt: list[str], source: list[str]) -> tuple[float, str, bool]:
    """Highest-scoring source window, then shortest span, then earliest offset.

    Returns (score, window text, complete). `complete` is False when the full
    span-by-span scan would have exceeded the declared work bound and a
    cheaper multiset-overlap prefilter over EVERY start was used to choose the
    windows actually scored. The diagnostic says which it was, so a reader is
    never told "closest candidate" about a search that silently skipped most of
    the region.
    """
    if not excerpt or not source:
        return (0.0, "", True)
    budget = min(EXCERPT_MAX_TOKENS, 2 * len(excerpt))
    spans = list(range(len(excerpt), len(excerpt) + budget + 1))
    starts = range(len(source))
    complete = True
    if len(source) * len(spans) > CANDIDATE_WORK_BUDGET:
        complete = False
        starts = _overlap_prefilter(excerpt, source)
    best = (-1.0, 0, 0)
    for start in starts:
        for span in spans:
            window = source[start:start + span]
            if not window:
                break
            score = difflib.SequenceMatcher(None, excerpt, window, autojunk=False).ratio()
            if score > best[0] or (score == best[0] and span < best[1]):
                best = (score, span, start)
            if start + span >= len(source):
                break
    if best[0] < 0:
        return (0.0, "", complete)
    window = source[best[2]:best[2] + best[1]]
    return (best[0], _clip(" ".join(window), 768), complete)


def _overlap_prefilter(excerpt: list[str], source: list[str]) -> list[int]:
    """Every start scored by sliding multiset overlap; the best few survive.

    No position is excluded a priori - the window slides across the whole
    selected region - but only the highest-overlap starts are handed to the
    exact scorer. This is a diagnostic aid, never the gate.
    """
    width = len(excerpt)
    wanted: dict[str, int] = {}
    for token in excerpt:
        wanted[token] = wanted.get(token, 0) + 1
    have: dict[str, int] = {}
    overlap = 0
    scored: list[tuple[int, int]] = []
    for index, token in enumerate(source):
        if wanted.get(token, 0) > have.get(token, 0):
            overlap += 1
        have[token] = have.get(token, 0) + 1
        if index >= width:
            gone = source[index - width]
            have[gone] -= 1
            if wanted.get(gone, 0) > have.get(gone, 0):
                overlap -= 1
        if index >= width - 1:
            scored.append((overlap, index - width + 1))
    scored.sort(key=lambda pair: (-pair[0], pair[1]))
    return [start for _score, start in scored[:CANDIDATE_PREFILTER_KEEP]]


def verify_citation(ctx, index: int, citation: dict, documents: dict,
                    runner=run_pdftotext) -> None:
    """Verify one CitationRef. Emits at most one CITATION_UNVERIFIED."""
    base = "facts.citations.%d" % index
    try:
        _verify_citation_inner(ctx, base, citation, documents, runner)
    except CitationFailure as failure:
        field = failure.field or base
        ctx.err(field, "CITATION_UNVERIFIED",
                "a citation whose excerpt is derivable from the bound source bytes",
                _clip(failure.reason, MAX_PAYLOAD_BYTES), failure.remedy)


def _verify_citation_inner(ctx, base: str, citation: dict, documents: dict,
                           runner) -> None:
    if not isinstance(citation, dict):
        raise CitationFailure(base, "a CitationRef table", "use a table literal")
    source_id = citation.get("source_id")
    document = documents.get(source_id)
    if document is None:
        raise CitationFailure(
            base + ".source_id",
            "source ID %r selects no sources.documents entry" % (source_id,),
            "bind the citation to a declared source document")
    if citation.get("source") != document.get("source"):
        raise CitationFailure(
            base + ".source_id",
            "citation source %r differs from the bound document source %r"
            % (citation.get("source"), document.get("source")),
            "record the exact FileRef of the bound source document")

    fmt = document.get("format")
    location = citation.get("location")
    if not isinstance(location, dict):
        raise CitationFailure(base + ".location", "a tagged location table",
                              "declare a pdf-page or text-lines location")
    variant = location.get("kind")
    expected = "pdf-page" if fmt == "pdf" else "text-lines"
    if variant != expected:
        raise CitationFailure(
            base + ".location",
            "format %r requires location kind %r; found %r" % (fmt, expected, variant),
            "use the location variant the source format supports")

    excerpt = citation.get("excerpt")
    if not isinstance(excerpt, str):
        raise CitationFailure(base + ".excerpt", "a string excerpt",
                              "quote the source text")
    normalized_excerpt = normalize_citation_text(excerpt)
    if not EXCERPT_MIN_CODEPOINTS <= len(normalized_excerpt) <= EXCERPT_MAX_CODEPOINTS:
        raise CitationFailure(
            base + ".excerpt",
            "normalized excerpt length %d outside %d-%d code points"
            % (len(normalized_excerpt), EXCERPT_MIN_CODEPOINTS, EXCERPT_MAX_CODEPOINTS),
            "quote a longer or shorter passage")
    alnum = sum(1 for ch in normalized_excerpt
                if unicodedata.category(ch)[0] in ("L", "M", "N"))
    if alnum < EXCERPT_MIN_ALNUM:
        raise CitationFailure(
            base + ".excerpt",
            "normalized excerpt carries %d letters/digits, fewer than %d"
            % (alnum, EXCERPT_MIN_ALNUM),
            "quote a passage with substantive text")

    source_ref = document.get("source")
    abs_source = _resolve_ref(ctx, source_ref)
    if abs_source is None:
        raise CitationFailure(
            base + ".source_id", "the bound source path does not resolve inside its root",
            "restore the authoritative source bytes")

    if variant == "pdf-page":
        page = location.get("page")
        if not isinstance(page, int) or isinstance(page, bool) or page < 1:
            raise CitationFailure(base + ".location",
                                  "physical PDF page ordinal %r is not >= 1" % (page,),
                                  "record the one-based physical page ordinal")
        derived = runner(abs_source, page)
        where = "physical PDF page %d" % page
        command = "pdftotext -layout -f %d -l %d %s -" % (
            page, page, shlex.quote(abs_source))
    else:
        line_start = location.get("line_start")
        line_end = location.get("line_end")
        for name, value in (("line_start", line_start), ("line_end", line_end)):
            if not isinstance(value, int) or isinstance(value, bool) or value < 1:
                raise CitationFailure(base + ".location",
                                      "%s %r is not >= 1" % (name, value),
                                      "record one-based inclusive line numbers")
        line_start = int(line_start)
        line_end = int(line_end)
        if line_end < line_start:
            raise CitationFailure(base + ".location",
                                  "line_end %d precedes line_start %d" % (line_end, line_start),
                                  "record an ordered inclusive line range")
        try:
            with open(abs_source, "rb") as handle:
                raw = handle.read(Limits.MAX_TEXT_BYTES + 1)
        except OSError as exc:
            raise CitationFailure(base + ".source_id",
                                  "the bound source cannot be read: %s" % exc,
                                  "restore the authoritative source bytes")
        if len(raw) > Limits.MAX_TEXT_BYTES:
            raise CitationFailure(base + ".source_id",
                                  "the bound source exceeds the text read bound",
                                  "split the source or cite a smaller document")
        try:
            text = raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise CitationFailure(base + ".source_id",
                                  "the bound source is not strict UTF-8: %s" % exc,
                                  "record format='pdf' or supply valid UTF-8 bytes")
        lines = text.splitlines()
        if line_end > len(lines):
            raise CitationFailure(
                base + ".location",
                "line_end %d is past the %d-line source" % (line_end, len(lines)),
                "correct the cited line range")
        derived = "\n".join(lines[line_start - 1:line_end])
        where = "text lines %d-%d" % (line_start, line_end)
        command = "sed -n '%d,%dp' %s" % (line_start, line_end, shlex.quote(abs_source))

    normalized_source = normalize_citation_text(derived)
    if normalized_excerpt in normalized_source:
        return

    excerpt_tokens = citation_tokens(normalized_excerpt)
    source_tokens = citation_tokens(normalized_source)
    if len(excerpt_tokens) > EXCERPT_MAX_TOKENS:
        ctx.err(base + ".excerpt", "RESOURCE_LIMIT",
                "an excerpt of at most %d tokens" % EXCERPT_MAX_TOKENS,
                len(excerpt_tokens), "quote a shorter passage")
        return
    if len(source_tokens) > SOURCE_MAX_TOKENS:
        ctx.err(base + ".location", "RESOURCE_LIMIT",
                "a selected region of at most %d tokens" % SOURCE_MAX_TOKENS,
                len(source_tokens), "cite a narrower location")
        return
    outcome = ordered_token_match(excerpt_tokens, source_tokens)
    if outcome is True:
        return
    if outcome is None:
        ctx.err(base + ".location", "RESOURCE_LIMIT",
                "an ordered-token search completable within %d steps" % MATCH_WORK_BUDGET,
                {"excerpt_tokens": len(excerpt_tokens),
                 "source_tokens": len(source_tokens)},
                "cite a narrower location or a more distinctive excerpt; the search was "
                "NOT completed, so this is not a finding that the excerpt is absent")
        return

    score, window, complete = nearest_candidate(excerpt_tokens, source_tokens)
    payload = (
        "assertion %r; source %r sha256 %s; %s; attempted: %s; "
        "attempt-1 normalized excerpt: %s; attempt-2 tokens: %s; "
        "closest candidate (%s scan) score %.4f: %s"
        % (citation.get("assertion_id"), citation.get("source_id"),
           (source_ref or {}).get("sha256"), where, command,
           _clip(normalized_excerpt, 512),
           _clip(" ".join(excerpt_tokens), 512),
           "exhaustive" if complete else "overlap-prefiltered", score, window))
    raise CitationFailure(
        base + ".excerpt", payload,
        "quote text that actually occurs at the cited location, or correct the "
        "location; rerun the displayed command to see what the verifier reads")


def _resolve_ref(ctx, ref) -> str | None:
    """Absolute path of an already structurally validated FileRef, or None."""
    if not isinstance(ref, dict) or not isinstance(ref.get("path"), str):
        return None
    base = ctx.roots.base(ref.get("root"))
    if base is None:
        return None
    target = os.path.abspath(os.path.join(base, ref["path"].replace("/", os.sep)))
    return target if contained(base, target) else None


# --------------------------------------------------------------------------
# Structural validation
# --------------------------------------------------------------------------

class Ctx:
    def __init__(self, rep: Reporter, loader: Loader, roots: Roots, where: str) -> None:
        self.rep = rep
        self.loader = loader
        self.roots = roots
        self.where = where
        self.refs: list[tuple[str, dict]] = []   # (dotted field, FileRef)

    def err(self, field, code, expectation, found, remedy):
        self.rep.emit(self.where, field, code, expectation, found, remedy)


def validate_value(ctx: Ctx, field: str, spec: dict, value, depth: int = 0) -> None:
    if depth > Limits.MAX_DEPTH:
        ctx.err(field, "RESOURCE_LIMIT", "nesting depth at most %d" % Limits.MAX_DEPTH,
                depth, "flatten the structure")
        return
    kind = spec["type"]

    if kind == "int":
        if isinstance(value, bool) or not isinstance(value, int):
            ctx.err(field, "ILLEGAL_ENUM", "an integer (boolean is not an integer)",
                    value, "use an integer literal")
        return
    if kind == "bool":
        if not isinstance(value, bool):
            ctx.err(field, "ILLEGAL_ENUM", "a boolean", value, "use true or false")
        return
    if kind == "str":
        if not isinstance(value, str):
            ctx.err(field, "ILLEGAL_ENUM", "a string", value, "use a string literal")
            return
        if len(value) > Limits.MAX_STRING:
            ctx.err(field, "RESOURCE_LIMIT", "string at most %d bytes" % Limits.MAX_STRING,
                    len(value), "shorten the string")
        if not value and not spec.get("allow_empty"):
            ctx.err(field, "MISSING_FIELD", "a nonempty string", value,
                    "supply a nonempty value")
        return
    if kind == "enum":
        if value not in spec["values"]:
            ctx.err(field, "ILLEGAL_ENUM", "one of %s" % sorted(spec["values"]),
                    value, "use a declared enum value")
        return
    if kind == "scopeitem":
        if not isinstance(value, str) or not SCOPE_ITEM_RE.match(value) or not 3 <= len(value) <= 80:
            ctx.err(field, "ILLEGAL_ENUM", "a scope-item ID matching the declared grammar",
                    value, "use a well-formed scope-item ID")
        return
    if kind == "scoperev":
        if not isinstance(value, str) or not SCOPE_REV_RE.match(value):
            ctx.err(field, "ILLEGAL_ENUM", "a scope revision ID 'scope-<8 lowercase hex>'",
                    value, "use a well-formed revision ID")
        return
    if kind == "assertionid":
        if not isinstance(value, str) or not ASSERTION_ID_RE.match(value):
            ctx.err(field, "ILLEGAL_ENUM",
                    "an assertion ID matching [a-z][a-z0-9._-]{2,79}", value,
                    "use a well-formed assertion ID")
        return
    if kind == "hex":
        width = spec["width"]
        if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{%d}" % width, value):
            ctx.err(field, "ILLEGAL_ENUM",
                    "exactly %d lowercase hexadecimal characters" % width, value,
                    "record the canonical lowercase hexadecimal value")
        return
    if kind == "array":
        if not isinstance(value, list):
            ctx.err(field, "ILLEGAL_ENUM", "an array", value, "use an array literal")
            return
        if len(value) > Limits.MAX_ARRAY:
            ctx.err(field, "RESOURCE_LIMIT", "array length at most %d" % Limits.MAX_ARRAY,
                    len(value), "shorten the array")
            return
        if spec.get("nonempty") and not value:
            ctx.err(field, "MISSING_FIELD", "a nonempty array", value,
                    "supply at least one entry")
        if spec.get("sorted_unique"):
            if len(set(map(str, value))) != len(value):
                ctx.err(field, "ILLEGAL_ENUM", "a duplicate-free set", value,
                        "remove duplicate entries")
            elif list(value) != sorted(value, key=str):
                ctx.err(field, "ILLEGAL_ENUM", "a sorted set", value, "sort the entries")
        for index, item in enumerate(value):
            validate_value(ctx, "%s.%d" % (field, index), spec["items"], item, depth + 1)
        return
    if kind in ("fileref", "pathref"):
        validate_ref(ctx, field, spec, value)
        return
    if kind == "struct":
        if not isinstance(value, dict):
            ctx.err(field, "ILLEGAL_ENUM", "a table", value, "use a table literal")
            return
        validate_table(ctx, field, spec["fields"], value, depth + 1)
        return
    if kind == "tagged":
        if not isinstance(value, dict):
            ctx.err(field, "ILLEGAL_ENUM", "a tagged table", value, "use a table literal")
            return
        tag = value.get("kind")
        if tag not in spec["variants"]:
            ctx.err(field + ".kind", "ILLEGAL_ENUM",
                    "one of %s" % sorted(spec["variants"]), tag, "use a declared variant")
            return
        fields = dict(spec["variants"][tag])
        fields["kind"] = (STR, True)
        validate_table(ctx, field, fields, value, depth + 1)
        return
    raise Fatal("unknown spec kind %r" % kind)


def validate_table(ctx: Ctx, prefix: str, fields: dict, table: dict, depth: int = 0) -> None:
    if not isinstance(table, dict):
        ctx.err(prefix or "-", "ILLEGAL_ENUM", "a table", table, "use a table")
        return
    for name in sorted(table):
        dotted = "%s.%s" % (prefix, name) if prefix else name
        if name not in fields:
            ctx.err(dotted, "UNKNOWN_FIELD", "only fields defined by the schema",
                    name, "remove the field or fix the schema")
            continue
        validate_value(ctx, dotted, fields[name][0], table[name], depth)
    for name, (_spec, required) in sorted(fields.items()):
        if required and name not in table:
            dotted = "%s.%s" % (prefix, name) if prefix else name
            ctx.err(dotted, "MISSING_FIELD", "the required field to be present",
                    None, "add the required field")


_INDEX_TAIL = re.compile(r"(?:\.\d+)+$")


def base_field(field: str) -> str:
    """Name the declared collection, not a positional element within it."""
    return _INDEX_TAIL.sub("", field)


def validate_ref(ctx: Ctx, dotted: str, spec: dict, value) -> None:
    field = base_field(dotted)
    if not isinstance(value, dict):
        ctx.err(field, "ILLEGAL_ENUM", "a PathRef table", value, "use a table literal")
        return
    allowed = {"root", "path"} | ({"sha256"} if spec["type"] == "fileref" else set())
    for name in sorted(value):
        if name not in allowed:
            ctx.err("%s.%s" % (field, name), "UNKNOWN_FIELD",
                    "only %s" % sorted(allowed), name, "remove the field")
    if "path" not in value:
        ctx.err(field + ".path", "MISSING_FIELD", "a path", None, "add the path")
        return
    root = value.get("root")
    if root is not None:
        if not isinstance(root, str) or not ROOT_NAME_RE.match(root):
            ctx.err(field + ".root", "PATH_ESCAPE",
                    "a root name matching generation:[a-z][a-z0-9-]{0,31}", root,
                    "use a declared named root")
            return
    problem = path_problem(value.get("path"))
    if problem is not None:
        ctx.err(field, "PATH_ESCAPE", problem, value.get("path"),
                "use a normalized relative path inside the selected root")
        return
    base = ctx.roots.base(root)
    if base is None:
        ctx.err(field, "PATH_ESCAPE", "a CLI binding for named root %r" % root, value,
                "supply --root %s=<absolute-path>" % root)
        return
    target = os.path.abspath(os.path.join(base, value["path"].replace("/", os.sep)))
    if not contained(base, target):
        ctx.err(field, "PATH_ESCAPE", "a target inside the selected root", value["path"],
                "keep the path within its root")
        return
    if spec["type"] == "fileref":
        digest = value.get("sha256")
        if not isinstance(digest, str) or not SHA_RE.match(digest):
            ctx.err(field, "NONCANONICAL_DIGEST",
                    "exactly 64 lowercase hexadecimal characters", digest,
                    "record the canonical lowercase SHA-256 digest")
            return
        ctx.refs.append((field, {"abs": target, "sha256": digest, "ref": value}))


# --------------------------------------------------------------------------
# Handoff validation
# --------------------------------------------------------------------------

class Handoff:
    def __init__(self, kind, rel, abspath, data):
        self.kind = kind
        self.rel = rel
        self.abs = abspath
        self.data = data


# Kinds whose filename is not name-derived and occurs at most once. Their
# canonical filename is exactly "<kind>.toml"; a prefix match such as
# "05-platform-extra.toml" is a non-canonical name, not a second handoff.
# "06-driver-<name>", "07-tests-<name>" and "08-review-<artifact>" stay
# name-derived and repeatable.
SINGLETON_KINDS = ("01-sources", "02-facts", "03-svd", "04-pac", "05-platform")


def kind_of(filename: str) -> str | None:
    for key in KINDS:
        if filename.startswith(key):
            return key
    return None


def canonical_filename(kind: str, filename: str) -> bool:
    """Whether `filename` is a canonical filename for `kind`."""
    if kind in SINGLETON_KINDS:
        return filename == kind + ".toml"
    return True


def evidence_code(field: str, kind: str) -> str:
    if field.startswith("handoff.inputs"):
        return "INPUT_HASH_MISMATCH"
    return "STALE_EVIDENCE"


def validate_handoff(rep, loader, roots, h: Handoff, world) -> None:
    ctx = Ctx(rep, loader, roots, h.rel)
    spec = KINDS[h.kind]
    data = h.data
    table_name = spec["table"]

    top = {"handoff": HANDOFF_TABLE, "scope": SCOPE_TABLE, "coverage": COVERAGE_TABLE}
    for name in sorted(data):
        if name not in top and name != table_name and name != "checks":
            ctx.err(name, "UNKNOWN_FIELD", "only tables defined by the schema", name,
                    "remove the table")
    for name, fields in top.items():
        if name not in data:
            ctx.err(name, "MISSING_FIELD", "the required table", None, "add the table")
        else:
            validate_table(ctx, name, fields, data[name])

    hd = data.get("handoff", {}) if isinstance(data.get("handoff"), dict) else {}

    # schema version
    if hd.get("schema") != SCHEMA_VERSION_CURRENT:
        ctx.err("handoff.schema", "SCHEMA_VERSION",
                "schema version %d" % SCHEMA_VERSION_CURRENT, hd.get("schema"),
                "rewrite the artifact for a supported schema version")
        return
    if hd.get("stage") != spec["stage"]:
        ctx.err("handoff.stage", "ILLEGAL_ENUM", "stage %r for this filename" % spec["stage"],
                hd.get("stage"), "fix the stage or the filename")

    # lock-only status leaking into a committed handoff
    if hd.get("status") == "in-progress":
        ctx.err("handoff.status", "HANDOFF_IN_PROGRESS",
                "one of ['blocked', 'partial', 'ready']", "in-progress",
                "publish a durable status; 'in-progress' is lock-only")

    status = hd.get("status")
    if status in ("partial", "blocked") and "can_progress" not in hd:
        ctx.err("handoff.can_progress", "MISSING_FIELD",
                "can_progress present for a non-ready status", None, "add can_progress")
    if status == "ready" and "can_progress" in hd:
        ctx.err("handoff.can_progress", "UNKNOWN_FIELD",
                "can_progress absent for a ready status", hd.get("can_progress"),
                "remove can_progress")
    if status == "blocked" and not hd.get("blockers"):
        ctx.err("handoff.blockers", "MISSING_FIELD", "a nonempty blocker list", [],
                "name the external blocking action")
    if status != "blocked" and hd.get("blockers"):
        ctx.err("handoff.blockers", "ILLEGAL_ENUM", "empty blockers unless blocked",
                hd.get("blockers"), "clear the blockers")

    # kind-specific table
    if table_name not in data:
        ctx.err(table_name, "MISSING_FIELD", "the required table", None, "add the table")
    else:
        validate_table(ctx, table_name, spec["fields"], data[table_name])

    validate_checks(ctx, h, spec)
    validate_coverage(ctx, h, world)
    validate_refs(ctx, h)

    kind_rules(ctx, h, world)


def validate_checks(ctx: Ctx, h: Handoff, spec: dict) -> None:
    raw = h.data.get("checks")
    if not isinstance(raw, list):
        ctx.err("checks", "MISSING_FIELD", "a checks array", raw, "add [[checks]] entries")
        return
    seen: dict[str, dict] = {}
    canonical = spec["checks"]
    for index, entry in enumerate(raw):
        if not isinstance(entry, dict):
            ctx.err("checks.%d" % index, "ILLEGAL_ENUM", "a check table", entry, "use a table")
            continue
        cid = entry.get("id")
        if cid not in canonical:
            ctx.err("checks.%s" % cid, "UNKNOWN_FIELD",
                    "a canonical check ID from %s" % sorted(canonical), cid,
                    "remove the invented check")
            continue
        if cid in seen:
            ctx.err("checks.%s" % cid, "ILLEGAL_ENUM", "exactly one entry per check ID",
                    cid, "remove the duplicate entry")
            continue
        seen[cid] = entry
        field = "checks.%s" % cid
        status = entry.get("status")
        if status not in ("passed", "failed", "unrun", "not-applicable"):
            ctx.err(field, "ILLEGAL_ENUM",
                    "one of ['failed', 'not-applicable', 'passed', 'unrun']", status,
                    "use a declared check status")
            continue
        allowed = {"id", "status", "reason"} if status == "not-applicable" \
            else {"id", "status", "evidence"}
        for name in sorted(entry):
            if name not in allowed:
                ctx.err("%s.%s" % (field, name), "UNKNOWN_FIELD",
                        "only %s for status %r" % (sorted(allowed), status), name,
                        "remove the field")
        if status == "not-applicable":
            reason = entry.get("reason")
            if not isinstance(reason, str) or not reason.strip():
                ctx.err(field, "NOT_APPLICABLE_NO_REASON",
                        "a nonempty reason for a not-applicable check", reason,
                        "state why the check does not apply")
        else:
            if "evidence" not in entry:
                ctx.err(field, "MISSING_FIELD", "evidence for a run check", None,
                        "attach hashed evidence")
            else:
                validate_ref(ctx, field + ".evidence", FILEREF, entry["evidence"])

    for cid in sorted(canonical):
        if cid not in seen:
            ctx.err("checks", "CHECK_MISSING",
                    "exactly one entry for canonical check %r" % cid, sorted(seen),
                    "add the missing check entry")

    # applicability
    for cid, predicate in sorted(canonical.items()):
        entry = seen.get(cid)
        if entry is None:
            continue
        if predicate is None:          # flexible: passed or not-applicable+reason
            continue
        applicable = bool(predicate(h.data))
        status = entry.get("status")
        field = "checks.%s" % cid
        if applicable and status == "not-applicable":
            ctx.err(field, "ILLEGAL_ENUM", "an applicable check to be run", status,
                    "run the check and record its outcome")
        if not applicable and status != "not-applicable":
            ctx.err(field, "ILLEGAL_ENUM", "not-applicable for an inapplicable check",
                    status, "record not-applicable with a reason")

    if h.data.get("handoff", {}).get("status") == "ready":
        for cid, predicate in sorted(canonical.items()):
            entry = seen.get(cid)
            if entry is None:
                continue
            status = entry.get("status")
            if status == "not-applicable":
                continue
            if status != "passed":
                ctx.err("checks.%s" % cid, "ILLEGAL_ENUM",
                        "a passed applicable check in a ready handoff", status,
                        "pass the check or lower the status")


def validate_coverage(ctx: Ctx, h: Handoff, world) -> None:
    cov = h.data.get("coverage")
    if not isinstance(cov, dict):
        return
    complete = cov.get("complete")
    incomplete = cov.get("incomplete")
    if not isinstance(complete, list) or not isinstance(incomplete, list):
        return
    revision = h.data.get("scope", {}).get("revision")
    decision = world.scope_nodes.get(revision)
    status = h.data.get("handoff", {}).get("status")

    if set(complete) & set(incomplete):
        ctx.err("coverage.complete", "COVERAGE_PARTITION",
                "complete and incomplete to be disjoint",
                sorted(set(complete) & set(incomplete)), "remove the overlap")
    if decision is not None:
        included = decision.get("included")
        if isinstance(included, list):
            union = set(complete) | set(incomplete)
            if union != set(included):
                ctx.err("coverage.complete", "COVERAGE_PARTITION",
                        "complete and incomplete to exactly partition included scope %s"
                        % sorted(included), sorted(union),
                        "cover every included scope item exactly once")
    if status == "ready" and incomplete:
        ctx.err("coverage.incomplete", "NARROWED_READY_SCOPE",
                "an empty incomplete list in a ready handoff", incomplete,
                "complete the scope or publish partial")


def validate_refs(ctx: Ctx, h: Handoff) -> None:
    review_fields = ("review.artifact", "review.dependencies")
    for field, info in ctx.refs:
        if not ctx.loader.count_referenced(ctx.where):
            return
        actual = ctx.loader.sha256(info["abs"], ctx.where, field)
        if actual is None:
            continue
        if actual != info["sha256"]:
            ctx.err(field, evidence_code(field, h.kind),
                    "the recorded digest to equal the raw bytes (%s)" % actual,
                    info["sha256"], "re-hash the evidence and update the reference")
            if h.kind == "08-review" and field.startswith(review_fields):
                ctx.err(field, "STALE_REVIEW",
                        "reviewed bytes to still match the review record (%s)" % actual,
                        info["sha256"], "obtain a fresh review of the changed bytes")


def _dep_check(ctx: Ctx, field: str, deps) -> None:
    if not isinstance(deps, list):
        return
    for entry in deps:
        if isinstance(entry, dict):
            identity = entry.get("identity")
            if not isinstance(identity, str) or not identity.strip():
                ctx.err(field, "DEPENDENCY_IDENTITY",
                        "a nonempty exact version requirement or source revision",
                        entry, "record the exact dependency identity")


def kind_rules(ctx: Ctx, h: Handoff, world) -> None:
    data = h.data
    status = data.get("handoff", {}).get("status")
    table = data.get(KINDS[h.kind]["table"])
    if not isinstance(table, dict):
        return

    if h.kind in ("05-platform", "06-driver", "07-tests"):
        _dep_check(ctx, KINDS[h.kind]["table"] + ".dependencies", table.get("dependencies"))

    if h.kind == "01-sources":
        docs = table.get("documents")
        if isinstance(docs, list):
            ids = [d.get("source_id") for d in docs if isinstance(d, dict)]
            if len(set(map(str, ids))) != len(ids):
                ctx.err("sources.documents", "ILLEGAL_ENUM",
                        "source IDs unique across sources.documents", ids,
                        "remove the duplicate source document")
            elif list(map(str, ids)) != sorted(map(str, ids)):
                ctx.err("sources.documents", "ILLEGAL_ENUM",
                        "sources.documents sorted by source_id", ids,
                        "sort the source documents by source_id")

    if h.kind == "02-facts":
        citations = table.get("citations")
        if isinstance(citations, list) and citations:
            documents = world.source_documents
            for index, citation in enumerate(citations):
                verify_citation(ctx, index, citation, documents)
            seen_ids: list[str] = []
            for citation in citations:
                if isinstance(citation, dict) and isinstance(citation.get("assertion_id"), str):
                    seen_ids.append(citation["assertion_id"])
            if len(set(seen_ids)) != len(seen_ids):
                ctx.err("facts.citations", "ILLEGAL_ENUM",
                        "assertion IDs unique within facts.citations", seen_ids,
                        "give every assertion a distinct ID")

    if h.kind == "06-driver":
        api = table.get("public_api")
        if isinstance(api, list):
            for item in api:
                if isinstance(item, str):
                    for token in FORBIDDEN_API_TOKENS:
                        if token in item:
                            ctx.err("driver.public_api", "DRIVER_API_LEAK",
                                    "no occurrence of forbidden token %r" % token, item,
                                    "remove implementation detail from the tester-facing API")
        validate_driver_fact_linkage(ctx, h, table, world)

    if h.kind == "03-svd":
        sources = world.by_stage.get("gather-documentation")
        if sources is not None:
            sroute = sources.data.get("sources", {}).get("route")
            if sroute is not None and table.get("route") != sroute:
                ctx.err("svd.route", "ROUTE_INCOMPATIBILITY",
                        "the SVD route to equal the sources route %r" % sroute,
                        table.get("route"), "align the SVD route with the sources route")

    if h.kind == "04-pac":
        requirements = world.state_requirements
        if requirements is not None:
            entries = table.get("foundation")
            got = set()
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, dict):
                        got.add((entry.get("id"), entry.get("kind"), entry.get("location")))
            if got != requirements:
                ctx.err("pac.foundation", "FOUNDATION_PARTITION",
                        "entries exactly partitioning the coordinator requirements %s"
                        % sorted(requirements), sorted(got),
                        "cover every foundation requirement exactly once")
        # PAC/state continuity: a PAC handoff may not contradict the current
        # coordinator-owned decisions it is built against. Compared only when the
        # coordinator has actually recorded the decision; both fields are
        # optional in state.toml.
        for name in ("cargo_chip_feature", "rust_compilation_target"):
            decided = world.state_decisions.get(name)
            if not isinstance(decided, str) or not decided:
                continue
            if table.get(name) != decided:
                ctx.err("pac." + name, "DEPENDENCY_NOT_READY",
                        "%s to equal the current coordinator decision %r"
                        % (name.replace("_", " "), decided),
                        table.get(name),
                        "rebuild the PAC against the recorded decision, or "
                        "record a new coordinator decision first")

    if h.kind == "07-tests":
        # `tests.api_handoff` is a binding to one specific driver handoff, so
        # it is resolved by path, never through `world.by_stage` (which keeps
        # only the first handoff per stage and so cannot tell two drivers
        # apart). A binding that does not name a `06-driver` is corrupt
        # lineage at any status, hence this is not gated on `status`.
        # Hash freshness of the reference is already proved by validate_refs.
        # Suite and driver names need not match: one driver may carry several
        # suites.
        ref = table.get("api_handoff")
        target = world.by_path.get(ref.get("path")) if isinstance(ref, dict) else None
        if target is None or target.kind != "06-driver":
            ctx.err("tests.api_handoff", "ILLEGAL_ENUM",
                    "a path naming a present 06-driver handoff",
                    ref.get("path") if isinstance(ref, dict) else ref,
                    "bind the suite to the driver handoff whose API it exercises")
        elif status == "ready":
            tstatus = target.data.get("handoff", {}).get("status") \
                if isinstance(target.data.get("handoff"), dict) else None
            if tstatus != "ready":
                ctx.err("tests.api_handoff", "DEPENDENCY_NOT_READY",
                        "the bound driver handoff %r to be ready" % target.rel,
                        tstatus,
                        "complete the bound driver before declaring tests ready")
        validate_board_records(ctx, h, table, world)

    # dependency graph for ready
    if status == "ready":
        required = {
            "extract-facts": ["gather-documentation"],
            "generate-svd": ["gather-documentation"],
            "generate-pac": ["generate-svd"],
            "scaffold-hal": ["generate-pac"],
            "write-driver": ["scaffold-hal"],
            # "write-tests" is deliberately absent: its upstream is the one
            # driver named by `tests.api_handoff`, checked above by path.
        }.get(KINDS[h.kind]["stage"], [])
        if KINDS[h.kind]["stage"] == "generate-svd" and table.get("route") == "author-from-docs":
            required = required + ["extract-facts"]
        for stage in required:
            upstream = world.by_stage.get(stage)
            if upstream is None:
                ctx.err("handoff.inputs", "DEPENDENCY_NOT_READY",
                        "a ready %r handoff" % stage, None,
                        "produce the required upstream handoff")
                continue
            ustatus = upstream.data.get("handoff", {}).get("status")
            if ustatus != "ready":
                ctx.err("handoff.inputs", "DEPENDENCY_NOT_READY",
                        "a ready %r dependency" % stage, ustatus,
                        "complete the upstream stage before declaring ready")

    validate_independent_review(ctx, h, world)


def validate_driver_fact_linkage(ctx: Ctx, h: Handoff, table: dict, world) -> None:
    """A driver references verified assertions; it never originates a citation.

    This is what makes the citation gate protect the tester transitively: the
    tester receives assertion IDs resolved through a handoff the validator has
    already checked, not an agent-authored duplicate of the quotation.
    """
    wanted = table.get("test_hardware_facts")
    ref = table.get("facts_handoff")
    if not isinstance(ref, dict):
        return
    target = world.by_path.get(ref.get("path"))
    field = "driver.facts_handoff"
    if target is None or target.kind != "02-facts":
        ctx.err(field, "ILLEGAL_ENUM",
                "a path naming a present 02-facts handoff", ref.get("path"),
                "bind the driver to the facts handoff carrying its cited assertions")
        return
    if target.data.get("scope", {}).get("revision") != h.data.get("scope", {}).get("revision"):
        ctx.err(field, "ILLEGAL_ENUM",
                "a facts handoff pinned to scope revision %r"
                % h.data.get("scope", {}).get("revision"),
                target.data.get("scope", {}).get("revision"),
                "bind to the facts handoff for the current scope revision")
    if not isinstance(wanted, list) or not wanted:
        return
    tstatus = target.data.get("handoff", {}).get("status")
    if tstatus != "ready":
        ctx.err(field, "DEPENDENCY_NOT_READY",
                "the bound facts handoff %r to be ready" % target.rel, tstatus,
                "complete the facts stage before naming its assertions")
    verified = None
    for entry in target.data.get("checks", []) or []:
        if isinstance(entry, dict) and entry.get("id") == "citations-verified":
            verified = entry.get("status")
    if verified != "passed":
        ctx.err(field, "DEPENDENCY_NOT_READY",
                "a passed citations-verified check in %r" % target.rel, verified,
                "verify the citations before a driver may reference them")
    available = set()
    for citation in target.data.get("facts", {}).get("citations", []) or []:
        if isinstance(citation, dict) and isinstance(citation.get("assertion_id"), str):
            available.add(citation["assertion_id"])
    missing = sorted(set(str(a) for a in wanted) - available)
    if missing:
        ctx.err("driver.test_hardware_facts", "ILLEGAL_ENUM",
                "every assertion ID to resolve in %r" % target.rel, missing,
                "reference only assertions present in the bound facts handoff")


def validate_board_records(ctx: Ctx, h: Handoff, table: dict, world) -> None:
    """Interlock, safe-state and recovery record rules for a tests handoff.

    The interlock is worktree-local and single-operator: a strong default and a
    statement of intent, not a sandbox. These rules enforce RECORD consistency
    only. They cannot establish physical ownership of a board, and a direct
    probe command bypasses the mechanism entirely.
    """
    scope = table.get("execution_scope")
    hardware = scope == "hardware-validation"
    for name in ("board_interlock", "safe_state_procedure", "recovery_attempts"):
        present = name in table
        if hardware and not present:
            ctx.err("tests." + name, "MISSING_FIELD",
                    "the field to be present for hardware-validation", None,
                    "record the worktree-local interlock evidence")
        if not hardware and present:
            ctx.err("tests." + name, "UNKNOWN_FIELD",
                    "the field to be absent for build-only execution", name,
                    "remove the hardware-only field")

    epoch_of_interlock = None
    interlock = table.get("board_interlock")
    if hardware and isinstance(interlock, dict):
        epoch_of_interlock = interlock.get("lease_epoch")

    runs = table.get("hardware_runs")
    required = ("lease_epoch", "operation_attempt", "operation_id", "pre_safe_state")
    if isinstance(runs, list):
        for index, run in enumerate(runs):
            if not isinstance(run, dict):
                continue
            base = "tests.hardware_runs.%d" % index
            status = run.get("status")
            if status == "not-run":
                for name in required + ("post_safe_state", "evidence"):
                    if name in run:
                        ctx.err(base + "." + name, "UNKNOWN_FIELD",
                                "no operation members on a not-run entry", name,
                                "remove the member; nothing was attempted")
                continue
            for name in required:
                if name not in run:
                    ctx.err(base + "." + name, "MISSING_FIELD",
                            "the member to be present for an attempted run", None,
                            "record the epoch, attempt, operation and pre-run safe state")
            attempt = run.get("operation_attempt")
            if isinstance(attempt, int) and not isinstance(attempt, bool) and attempt < 0:
                ctx.err(base + ".operation_attempt", "ILLEGAL_ENUM",
                        "a nonnegative operation attempt", attempt,
                        "record a monotonically increasing attempt number")
            if status in ("passed", "failed") and "post_safe_state" not in run:
                ctx.err(base + ".post_safe_state", "MISSING_FIELD",
                        "a post-run safe-state observation for a completed run", None,
                        "observe and record the safe state before releasing")
            if epoch_of_interlock is not None and run.get("lease_epoch") != epoch_of_interlock:
                ctx.err(base + ".lease_epoch", "ILLEGAL_ENUM",
                        "the run epoch to equal the interlock epoch %r" % epoch_of_interlock,
                        run.get("lease_epoch"),
                        "record runs under the epoch that owned the board")

    if not hardware or not isinstance(interlock, dict):
        return
    board_id = interlock.get("board_id")
    for lock in world.board_locks.get(board_id, []):
        phase = lock.get("operation_phase")
        state = lock.get("board_state")
        if phase == "recovery-verified" and state == "safe":
            continue
        ctx.err("tests.board_interlock.lease_epoch", "BOARD_RECOVERY_REQUIRED",
                "the interlock for board %r to have reached recovery-verified with a "
                "safe board state before release and publication" % board_id,
                {"operation_phase": phase, "board_state": state},
                "declare the board state unknown, confirm the recorded child session "
                "terminated or physically isolate board and probe, then append recovery "
                "attempts until recovery-verified; never infer teardown from exit or age")
        break


def _ref_key(ref) -> tuple:
    """Hashable identity of a FileRef/ArtifactRef for set comparison."""
    if not isinstance(ref, dict):
        return ("", "", "")
    return (str(ref.get("root") or ""), str(ref.get("path") or ""),
            str(ref.get("sha256") or ""))


def validate_independent_review(ctx: Ctx, h: Handoff, world) -> None:
    spec = KINDS[h.kind]
    if "independent-review" not in spec["checks"]:
        return
    entry = None
    for item in h.data.get("checks", []) or []:
        if isinstance(item, dict) and item.get("id") == "independent-review":
            entry = item
    if entry is None or entry.get("status") != "passed":
        return
    field = "checks.independent-review"
    ref = entry.get("evidence")
    if not isinstance(ref, dict):
        ctx.err(field, "REVIEW_NONACCEPTING", "an 08-review FileRef as evidence", ref,
                "cite the accepting review handoff")
        return
    review = world.reviews_by_path.get(ref.get("path"))
    if review is None:
        ctx.err(field, "REVIEW_NONACCEPTING",
                "evidence naming a parseable 08-review handoff", ref.get("path"),
                "cite an existing accepting review handoff")
        return
    rtable = review.data.get("review", {})
    if rtable.get("verdict") != "ready":
        ctx.err(field, "REVIEW_NONACCEPTING", "a review verdict of 'ready'",
                rtable.get("verdict"), "obtain an accepting review")
    if review.data.get("scope", {}).get("revision") != h.data.get("scope", {}).get("revision"):
        ctx.err(field, "REVIEW_NONACCEPTING",
                "a review pinned to scope revision %r"
                % h.data.get("scope", {}).get("revision"),
                review.data.get("scope", {}).get("revision"),
                "obtain a review of the current scope revision")
    target = spec.get("review_artifact")
    if target:
        table = h.data.get(target[0], {})
        expected = table.get(target[1]) if isinstance(table, dict) else None
        if isinstance(expected, dict) and rtable.get("artifact") != expected:
            ctx.err(field, "REVIEW_NONACCEPTING",
                    "a review of the kind-defined artifact %s" % (expected,),
                    rtable.get("artifact"), "review the declared artifact")
    elif h.kind == "06-driver":
        # The driver kind has no single designated inventory ref. The reviewed
        # artifact is the complete set of driver.owned_files, compared
        # order-independently with the review handoff's handoff.inputs:
        # duplicates rejected on either side, exact FileRef equality with no
        # missing or extra path/hash pair (validate.md "Structural validation").
        owned = h.data.get("driver", {}).get("owned_files")
        rinputs = review.data.get("handoff", {}).get("inputs") \
            if isinstance(review.data.get("handoff"), dict) else None
        owned_keys = [_ref_key(r) for r in owned if isinstance(r, dict)] \
            if isinstance(owned, list) else []
        input_keys = [_ref_key(r) for r in rinputs if isinstance(r, dict)] \
            if isinstance(rinputs, list) else []
        for label, keys in (("driver.owned_files", owned_keys),
                            ("the review's handoff.inputs", input_keys)):
            if len(set(keys)) != len(keys):
                ctx.err(field, "STALE_REVIEW",
                        "a duplicate-free reviewed set in %s" % label, sorted(keys),
                        "remove the duplicate entries")
        if set(owned_keys) != set(input_keys):
            ctx.err(field, "STALE_REVIEW",
                    "the review inputs to equal the owned-files inventory %s"
                    % sorted(set(owned_keys)), sorted(set(input_keys)),
                    "review exactly the declared owned files")
        # review.artifact names the primary artifact only; it must be one
        # member of the driver input set and does not replace the set check.
        primary = rtable.get("artifact")
        if isinstance(primary, dict) and _ref_key(primary) not in set(input_keys):
            ctx.err(field, "STALE_REVIEW",
                    "review.artifact to be one member of the reviewed input set %s"
                    % sorted(set(input_keys)), _ref_key(primary),
                    "name a reviewed owned file as the primary artifact")


# --------------------------------------------------------------------------
# Scope chain
# --------------------------------------------------------------------------

def validate_scope_chain(rep, loader, roots, nodes, state, state_rel) -> None:
    """nodes: revision -> (rel, data). Validate a single append-only chain."""
    if not nodes:
        return
    prev_of: dict[str, str | None] = {}
    for rev, (_rel, data) in nodes.items():
        previous = data.get("previous")
        if isinstance(previous, dict) and previous.get("kind") == "revision":
            prev_of[rev] = previous.get("revision")
        else:
            prev_of[rev] = None

    tip = None
    if isinstance(state, dict):
        tip = state.get("scope", {}).get("current_revision")

    # walk from the tip
    chain: list[str] = []
    seen: set[str] = set()
    cursor = tip
    bound = 0
    while cursor is not None and cursor in nodes and cursor not in seen and bound < Limits.MAX_SCHEMA_TOML:
        seen.add(cursor)
        chain.append(cursor)
        cursor = prev_of.get(cursor)
        bound += 1
    chain_set = set(chain)

    if tip is not None and tip not in nodes:
        rep.emit(state_rel, "scope.current_revision", "SCOPE_DELETED_PREDECESSOR",
                 "state to point at a present scope decision", tip,
                 "restore the referenced scope decision")

    # tip-chain node with an absent predecessor
    for rev in chain:
        rel, _data = nodes[rev]
        parent = prev_of.get(rev)
        if parent is not None and parent not in nodes:
            rep.emit(rel, "previous", "SCOPE_DELETED_PREDECESSOR",
                     "a present hash-matching predecessor decision", parent,
                     "restore the deleted predecessor; scope decisions are append-only")

    # successors
    successors: dict[str, list[str]] = {}
    for rev, parent in prev_of.items():
        if parent is not None:
            successors.setdefault(parent, []).append(rev)

    # cycle detection over every node
    for rev in sorted(nodes):
        walk: list[str] = []
        cursor = rev
        bound = 0
        while cursor is not None and cursor in nodes and bound <= len(nodes) + 1:
            if cursor in walk:
                cycle = sorted(walk[walk.index(cursor):])
                head = cycle[0]
                rep.emit(nodes[head][0], "previous", "SCOPE_CYCLE",
                         "an acyclic append-only lineage", cycle,
                         "break the scope lineage cycle")
                break
            walk.append(cursor)
            cursor = prev_of.get(cursor)
            bound += 1

    cyclic: set[str] = set()
    for rev in nodes:
        walk: list[str] = []
        cursor = rev
        while cursor is not None and cursor in nodes and cursor not in walk:
            walk.append(cursor)
            cursor = prev_of.get(cursor)
        if cursor is not None and cursor in walk:
            cyclic.update(walk[walk.index(cursor):])

    for rev in sorted(nodes):
        if rev in chain_set or rev in cyclic:
            continue
        rel, data = nodes[rev]
        parent = prev_of.get(rev)
        if parent is None:
            rep.emit(rel, "previous", "SCOPE_SECOND_INITIAL",
                     "exactly one initial scope decision in the lineage", data.get("previous"),
                     "re-root this decision on the existing chain")
        elif parent in nodes and len(successors.get(parent, [])) > 1:
            rep.emit(rel, "previous", "SCOPE_FORK",
                     "each scope decision to have at most one successor", parent,
                     "linearize the scope lineage")
        else:
            rep.emit(rel, "previous", "SCOPE_ORPHAN",
                     "a decision connected to the current scope chain", data.get("previous"),
                     "connect or remove the disconnected scope node")


# --------------------------------------------------------------------------
# Locks
# --------------------------------------------------------------------------

def lock_id(stage: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", stage.lower()).strip("-")[:40].strip("-")
    digest8 = hashlib.sha256(stage.encode("utf-8")).hexdigest()[:8]
    return "%s-%s" % (slug, digest8)


def index_board_locks(loader, run_dir, world) -> None:
    """Index board-test locks by board ID without emitting diagnostics.

    Read-only and side-effect free on purpose: classification and conflict
    reporting belong to `validate_locks`, and nothing here may remove a lock.
    A lock is never stolen.
    """
    if not os.path.isdir(run_dir):
        return
    try:
        names = sorted(os.listdir(run_dir))
    except OSError:
        return
    quiet = Reporter()
    quiet_loader = Loader(quiet)
    for name in names:
        if not name.endswith(".lock"):
            continue
        data = quiet_loader.load_toml(os.path.join(run_dir, name),
                                      "halucinator/.run/" + name)
        if not isinstance(data, dict) or data.get("kind") != "board-test":
            continue
        board = data.get("board_id")
        if isinstance(board, str) and board:
            world.board_locks.setdefault(board, []).append(data)


def validate_locks(rep, loader, run_dir, state, state_stage_status) -> None:
    if not os.path.isdir(run_dir):
        return
    try:
        names = sorted(os.listdir(run_dir))
    except OSError as exc:
        raise Fatal("cannot list %s: %s" % (run_dir, exc))
    claimed: dict[str, str] = {}
    for name in names:
        if not name.endswith(".lock"):
            continue
        rel = "halucinator/.run/" + name
        abspath = os.path.join(run_dir, name)
        data = loader.load_toml(abspath, rel)
        if data is None:
            continue
        ctx = Ctx(rep, loader, Roots(os.path.dirname(os.path.dirname(os.path.dirname(abspath))), {}), rel)
        before = len(rep.lines)
        validate_table(ctx, "", LOCK_SCHEMA, data)
        if len(rep.lines) != before:
            rep.emit(rel, "-", "MALFORMED_LOCK", "a lock satisfying its structural schema",
                     sorted(data), "repair the lock file")
            continue
        stage = data.get("stage")
        expected = lock_id(stage) + ".lock"
        if name != expected:
            rep.emit(rel, "-", "LOCK_ID_UNSAFE",
                     "filename %r computed from the canonical stage ID" % expected, name,
                     "rename the lock to its computed safe slug-plus-digest")
        resources = data.get("resources") or []
        if "stage:%s" % stage not in resources:
            rep.emit(rel, "-", "MALFORMED_LOCK",
                     "resources including 'stage:%s'" % stage, resources,
                     "declare the stage resource")
        for resource in resources:
            if resource in claimed and claimed[resource] != name:
                if str(resource).startswith("board:"):
                    rep.emit(rel, "resources", "BOARD_INTERLOCK_CONFLICT",
                             "no other structurally valid lock holding %r" % resource,
                             claimed[resource],
                             "the new claimant removes only its own candidate lock and "
                             "fails; never touch or steal the existing lock, and treat "
                             "the board as unknown until recovery is verified")
                else:
                    rep.emit(rel, "-", "MALFORMED_LOCK",
                             "non-intersecting lock resources", resource,
                             "release the conflicting lock")
            claimed[resource] = name
        if state_stage_status.get(stage) == "ready":
            rep.emit(rel, "-", "LOCK_COMPLETE_CONFLICT",
                     "no lock for a state-ready stage", stage,
                     "remove the stale lock for the completed stage")


# --------------------------------------------------------------------------
# World assembly / entry point
# --------------------------------------------------------------------------

class World:
    def __init__(self):
        self.by_stage: dict[str, Handoff] = {}
        self.by_path: dict[str, Handoff] = {}
        self.reviews_by_path: dict[str, Handoff] = {}
        self.scope_nodes: dict[str, dict] = {}
        self.state_requirements: set | None = None
        # Current coordinator-owned decisions from state.toml, used to prove a
        # ready PAC handoff does not contradict them.
        self.state_decisions: dict = {}
        # source_id -> SourceDocument, from the 01-sources handoff. One binding
        # array, so an ID cannot name bytes the catalog never admitted.
        self.source_documents: dict = {}
        # board_id -> structurally parseable board-test locks still present.
        self.board_locks: dict[str, list[dict]] = {}


def parse_args(argv):
    if not argv:
        raise Fatal("usage: validate.py ROOT [--root generation:<name>=<abs>]... [--kind K]")
    root = None
    bindings: dict[str, str] = {}
    kind = "all"
    index = 0
    while index < len(argv):
        arg = argv[index]
        if arg == "--root":
            index += 1
            if index >= len(argv):
                raise Fatal("--root requires generation:<name>=<absolute-path>")
            binding = argv[index]
            if "=" not in binding:
                raise Fatal("malformed --root binding: %r" % binding)
            name, _, value = binding.partition("=")
            if not ROOT_NAME_RE.match(name):
                raise Fatal("invalid root name: %r" % name)
            if name in bindings:
                raise Fatal("duplicate --root binding for %r" % name)
            drive, tail = os.path.splitdrive(value)
            if drive and not tail.startswith(("\\", "/")):
                raise Fatal("drive-relative root binding is forbidden: %r" % value)
            if not os.path.isabs(value):
                raise Fatal("root binding must be absolute: %r" % value)
            if value.startswith("\\\\") or value.startswith("//"):
                raise Fatal("UNC/device-namespace root binding is not authorized: %r" % value)
            if not os.path.isdir(value):
                raise Fatal("root binding is not an existing directory: %r" % value)
            bindings[name] = os.path.abspath(value)
        elif arg == "--kind":
            index += 1
            if index >= len(argv):
                raise Fatal("--kind requires a value")
            kind = argv[index]
        elif arg.startswith("--kind="):
            kind = arg.split("=", 1)[1]
        elif arg.startswith("--"):
            raise Fatal("unknown option %r" % arg)
        elif root is None:
            root = arg
        else:
            raise Fatal("unexpected positional argument %r" % arg)
        index += 1
    if root is None:
        raise Fatal("ROOT is required")
    if not os.path.isdir(root):
        raise Fatal("ROOT is not a directory: %r" % root)
    valid_kinds = {"all", "state"} | set(KINDS)
    if kind not in valid_kinds:
        raise Fatal("unknown --kind %r" % kind)
    return os.path.abspath(root), bindings, kind


def run(root_dir, bindings, kind) -> int:
    rep = Reporter()
    loader = Loader(rep)
    roots = Roots(root_dir, bindings)
    world = World()
    hal = os.path.join(root_dir, "halucinator")

    # -- Git byte policy -------------------------------------------------
    attrs_path = os.path.join(root_dir, ".gitattributes")
    if not os.path.isfile(attrs_path):
        rep.emit(".gitattributes", "-", "ATTRIBUTES_UNVERIFIED",
                 "a destination-root .gitattributes declaring the raw-byte policy", None,
                 "add the mandated .gitattributes policy")
    else:
        text = loader.read_bytes(attrs_path, ".gitattributes", "-")
        lines = set()
        if text is not None:
            lines = {ln.strip() for ln in text.decode("utf-8", "replace").splitlines()}
        for required in REQUIRED_ATTRS:
            if required not in lines:
                rep.emit(".gitattributes", "-", "ATTRIBUTES_UNVERIFIED",
                         "the mandated policy line %r" % required, None,
                         "declare an explicit Git byte policy for these paths")

    # -- state -----------------------------------------------------------
    state = None
    state_rel = "halucinator/state.toml"
    state_abs = os.path.join(hal, "state.toml")
    state_stage_status: dict[str, str] = {}
    if os.path.isfile(state_abs):
        loader.count_schema_toml(state_rel)
        state = loader.load_toml(state_abs, state_rel)
    if state is not None:
        ctx = Ctx(rep, loader, roots, state_rel)
        if state.get("schema") != SCHEMA_VERSION_CURRENT:
            ctx.err("schema", "SCHEMA_VERSION",
                    "schema version %d" % SCHEMA_VERSION_CURRENT, state.get("schema"),
                    "rewrite state for a supported schema version")
            state = None
        else:
            validate_table(ctx, "", STATE_SCHEMA, state)
            generation = state.get("generation")
            if isinstance(generation, int) and not isinstance(generation, bool) and generation < 0:
                ctx.err("generation", "ILLEGAL_ENUM", "a nonnegative CAS generation",
                        generation, "use a nonnegative generation")
            decisions = state.get("decisions", {})
            if isinstance(decisions, dict):
                world.state_decisions = decisions
                destination = decisions.get("destination_crate")
                if isinstance(destination, dict):
                    # A18. Constraining the configured destination to a
                    # repository-root `embassy-<vendor_id>` is what makes the
                    # tester's `embassy-*/**` deny rule actually cover it. It
                    # closes CONFIGURED-PATH coverage only: bash, grep,
                    # filenames, diagnostics, history and tools remain leak
                    # paths, and observed body text still invalidates a run.
                    vendor_id = state.get("target", {}).get("vendor_id") \
                        if isinstance(state.get("target"), dict) else None
                    expected = "embassy-%s" % vendor_id if isinstance(vendor_id, str) else None
                    path = destination.get("path")
                    ok = (isinstance(path, str) and "/" not in path
                          and destination.get("root") is None
                          and DESTINATION_CRATE_RE.match(path)
                          and (expected is None or path == expected))
                    if not ok:
                        ctx.err("decisions.destination_crate", "ILLEGAL_ENUM",
                                "a repository-root single-segment crate directory %r"
                                % (expected or "embassy-<vendor_id>"), destination,
                                "place the destination crate at the repository root so "
                                "the tester's embassy-*/** denial covers it")
                peripheral = decisions.get("first_peripheral")
                modes = decisions.get("first_peripheral_modes")
                if bool(peripheral) != bool(modes):
                    ctx.err("decisions.first_peripheral_modes", "FIRST_PERIPHERAL_MODES",
                            "a first peripheral and nonempty modes to be co-present",
                            {"first_peripheral": peripheral, "first_peripheral_modes": modes},
                            "record both or neither")
                reqs = decisions.get("foundation_requirements")
                if isinstance(reqs, list):
                    world.state_requirements = {
                        (r.get("id"), r.get("kind"), r.get("location"))
                        for r in reqs if isinstance(r, dict)}
            for entry in state.get("stages", []) or []:
                if isinstance(entry, dict):
                    state_stage_status[entry.get("id")] = entry.get("status")
            validate_refs(ctx, Handoff("state", state_rel, state_abs, state))

    # -- scope decisions -------------------------------------------------
    scope_dir = os.path.join(hal, "scope")
    nodes: dict[str, tuple[str, dict]] = {}
    if os.path.isdir(scope_dir):
        for name in sorted(os.listdir(scope_dir)):
            if not (name.startswith("scope-") and name.endswith(".toml")):
                continue
            rel = "halucinator/scope/" + name
            if not loader.count_schema_toml(rel):
                break
            abspath = os.path.join(scope_dir, name)
            data = loader.load_toml(abspath, rel)
            if data is None:
                continue
            ctx = Ctx(rep, loader, roots, rel)
            if data.get("schema") != SCHEMA_VERSION_CURRENT:
                ctx.err("schema", "SCHEMA_VERSION",
                        "schema version %d" % SCHEMA_VERSION_CURRENT, data.get("schema"),
                        "rewrite the decision for a supported schema version")
                continue
            validate_table(ctx, "", SCOPE_SCHEMA, data)
            if data.get("revision") != name[:-5]:
                ctx.err("revision", "ILLEGAL_ENUM",
                        "revision %r matching the filename" % name[:-5], data.get("revision"),
                        "align the revision with the filename")
            included = data.get("included") or []
            excluded = data.get("excluded") or []
            if not included:
                ctx.err("included", "MISSING_FIELD", "a nonempty included set", included,
                        "include at least one scope item")
            if set(included) & set(excluded):
                ctx.err("included", "ILLEGAL_ENUM", "included and excluded to be disjoint",
                        sorted(set(included) & set(excluded)), "remove the overlap")
            validate_refs(ctx, Handoff("scope", rel, abspath, data))
            nodes[data.get("revision")] = (rel, data)
            world.scope_nodes[data.get("revision")] = data
    validate_scope_chain(rep, loader, roots, nodes, state, state_rel)

    # -- handoffs --------------------------------------------------------
    handoff_dir = os.path.join(hal, "handoff")
    handoffs: list[Handoff] = []
    if os.path.isdir(handoff_dir):
        for name in sorted(os.listdir(handoff_dir)):
            if not name.endswith(".toml"):
                continue
            khint = kind_of(name)
            rel = "halucinator/handoff/" + name
            if khint is None or not canonical_filename(khint, name):
                rep.emit(rel, "-", "UNKNOWN_FIELD",
                         "a filename matching a declared handoff kind", name,
                         "rename to a canonical handoff filename")
                continue
            if not loader.count_schema_toml(rel):
                break
            abspath = os.path.join(handoff_dir, name)
            data = loader.load_toml(abspath, rel)
            if data is None:
                continue
            handoff = Handoff(khint, rel, abspath, data)
            handoffs.append(handoff)
            # Per-path index. `by_stage` collapses the repeatable kinds onto a
            # single entry per stage, which is correct for the singleton
            # generic dependencies but cannot express "this tests handoff is
            # bound to that driver handoff". Cross-artifact bindings resolve
            # through `by_path` instead.
            if rel in world.by_path:
                # Defensive: `os.listdir` cannot yield a duplicate name, so
                # this is unreachable under filesystem discovery.
                rep.emit(rel, "-", "ILLEGAL_ENUM",
                         "at most one handoff per repository path", rel,
                         "remove the duplicate handoff")
            else:
                world.by_path[rel] = handoff
            stage = data.get("handoff", {}).get("stage") if isinstance(data.get("handoff"), dict) else None
            if stage and stage not in world.by_stage:
                world.by_stage[stage] = handoff
            if khint == "08-review":
                # Reviews are resolved by path only (see
                # validate_independent_review); an 08-review is never a
                # `by_stage` consumer.
                world.reviews_by_path["halucinator/handoff/" + name] = handoff
            if khint == "01-sources":
                docs = data.get("sources", {}).get("documents") \
                    if isinstance(data.get("sources"), dict) else None
                if isinstance(docs, list):
                    for entry in docs:
                        if isinstance(entry, dict) and isinstance(entry.get("source_id"), str):
                            world.source_documents.setdefault(entry["source_id"], entry)

    # Board locks are indexed before handoff validation so a published tests
    # handoff can be compared with an interlock that never reached
    # recovery-verified. Absence of a lock is NOT evidence of safe teardown.
    index_board_locks(loader, os.path.join(hal, ".run"), world)

    for handoff in handoffs:
        if kind not in ("all", handoff.kind):
            continue
        validate_handoff(rep, loader, roots, handoff, world)
        # filename <-> body name agreement
        table = handoff.data.get(KINDS[handoff.kind]["table"])
        if handoff.kind in ("06-driver", "07-tests") and isinstance(table, dict):
            prefix = "06-driver-" if handoff.kind == "06-driver" else "07-tests-"
            expected = prefix + str(table.get("name")) + ".toml"
            if os.path.basename(handoff.rel) != expected:
                rep.emit(handoff.rel, KINDS[handoff.kind]["table"] + ".name",
                         "ILLEGAL_ENUM", "filename %r matching the declared name" % expected,
                         os.path.basename(handoff.rel), "align the filename and the name")

    # -- state backlinks -------------------------------------------------
    if state is not None and kind in ("all", "state"):
        by_path = {h.rel: h for h in handoffs}
        for entry in state.get("stages", []) or []:
            if not isinstance(entry, dict):
                continue
            ref = entry.get("handoff")
            if not isinstance(ref, dict):
                continue
            target = by_path.get(ref.get("path"))
            if target is None:
                rep.emit(state_rel, "stages", "STALE_EVIDENCE",
                         "a present handoff at %r" % ref.get("path"), ref.get("path"),
                         "restore the referenced handoff")
                continue
            # State/handoff status agreement. Both vocabularies are
            # ready|partial|blocked, so the recorded snapshot must equal the
            # status the referenced handoff declares; otherwise state can claim
            # a stage is ready over a handoff that says otherwise.
            recorded = entry.get("status")
            declared = target.data.get("handoff", {}).get("status") \
                if isinstance(target.data.get("handoff"), dict) else None
            if isinstance(recorded, str) and isinstance(declared, str) \
                    and recorded != declared:
                rep.emit(state_rel, "stages.%s.status" % entry.get("id"),
                         "DEPENDENCY_NOT_READY",
                         "the recorded status to equal the %r status declared by %s"
                         % (declared, ref.get("path")), recorded,
                         "re-publish state from the referenced handoff status")

    # -- named roots -----------------------------------------------------
    for name in sorted(set(bindings) - roots.used):
        rep.emit("-", "-", "PATH_ESCAPE",
                 "every CLI root binding to be used by a selected artifact", name,
                 "remove the unused --root binding")

    # -- locks -----------------------------------------------------------
    validate_locks(rep, loader, os.path.join(hal, ".run"), state, state_stage_status)

    return rep.flush()


def main(argv) -> int:
    try:
        root_dir, bindings, kind = parse_args(argv)
        return run(root_dir, bindings, kind)
    except Fatal as exc:
        print("ERROR -:- [PATH_INSPECTION] expected a valid invocation; found %s; "
              "action: correct the command line or environment" % _repr160(str(exc)),
              file=sys.stderr)
        return 2
    except RecursionError:
        print("ERROR -:- [RESOURCE_LIMIT] expected bounded recursion; found 'recursion "
              "limit exceeded'; action: reduce artifact nesting", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
