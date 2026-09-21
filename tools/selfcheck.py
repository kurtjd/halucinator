#!/usr/bin/env python3
"""Repository self-check harness for the halucinator OpenCode toolkit.

Repository-only (not shipped). Python 3.11+, standard library only.

Usage:
    python tools/selfcheck.py [REPO_ROOT]

Exits 0 only when every check passes. Prints sorted lines of the form:
    PASS <check>: <detail>
    FAIL <path>:<location> [<CODE>] <actionable-message>

Checks:
  1. frontmatter  - agent and skill YAML frontmatter conforms to the peer
                    schema inspected at commit 2d073c1.
  2. links        - relative Markdown links resolve to regular files.
  3. fixtures     - .opencode/schema/validate.py accepts the valid fixture and
                    rejects each invalid fixture with its README's code.
  4. terminology  - no *newly introduced* occurrences of the mechanically
                    enforced rejected tokens.

------------------------------------------------------------------------------
Terminology baseline format (tools/terminology-baseline.tsv)
------------------------------------------------------------------------------
The legacy agent and skill prose deliberately contains British spellings that
milestone 1 is not permitted to rewrite. A naive grep would therefore fail on
files this harness may not touch. The baseline is a checked-in record of the
known legacy occurrences; the check fails only on occurrences in excess of it.

Format: UTF-8, LF, one record per line, three TAB-separated fields:

    <repo-relative-posix-path>\t<token>\t<count>

Lines beginning with '#' and blank lines are ignored. Records are sorted by
(path, token). The granularity is *per file, per token, counted* rather than a
whole-file allowlist, so introducing an additional `behaviour` into a file that
already has two is still caught (3 > 2). Counts are of occurrences remaining
after code fences, inline code and URLs are stripped.

Regenerate (only when a rewrite milestone legitimately changes the counts):

    python tools/selfcheck.py --write-terminology-baseline

If the baseline file is absent, check 4 fails with TERMINOLOGY_BASELINE_MISSING.
"""

from __future__ import annotations

import ast
import datetime
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
import tomllib
import urllib.parse
from pathlib import Path, PurePosixPath

SUBPROCESS_TIMEOUT = 30

BASELINE_RELPATH = "tools/terminology-baseline.tsv"

# M3: canonical skill template. Named explicitly by governed_markdown() so that
# the link and terminology checks cover it, and by nothing else.
SKILL_TEMPLATE_RELPATH = "docs/skill-template.md"

# Mechanically enforced rejected tokens (terminology.md). Case sensitive.
REJECTED_TOKENS = ("type-state", "Typestate", "behaviour", "normalise", "initialisation")

# Terminology governance covers *tracked* toolkit prose. This is the closed
# list of untracked coordinator working-state files that are therefore not
# governed: they are scratch notes owned by whoever is running the pipeline,
# not shipped toolkit prose, so the harness must not fail because of an edit
# in progress. The exclusion is deliberately narrow and self-policing: it is
# honoured only while Git confirms the file is genuinely untracked (see
# untracked_working_state), so committing such a file re-governs it
# automatically. Widening this list requires a terminology.md revision.
UNTRACKED_WORKING_STATE = ("TODO.md",)

# Directory names never descended into.
SKIP_DIRS = {
    "node_modules",
    ".git",
    "target",
    "__pycache__",
    ".venv",
    "venv",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "dist",
    "build",
}

# M6 (spec S2.6): the mandated invalid-fixture count is DERIVED from the
# committed declarative generator input, never duplicated here as a literal.
# A literal would have to be hand-raised for every new fixture, which is
# exactly how a declared coverage floor comes to assert nothing. The floor
# below is only a non-vacuity backstop: it is the M4 count, so a declaration
# file that declares fewer fixtures than the corpus already has is itself a
# failure rather than a silently lowered bar.
FIXTURE_DECL_RELPATH = "tools/schema-fixtures.toml"
FIXTURE_FLOOR = 32

# M6 (spec S2.2): the three new diagnostic codes, plus the existing code the
# A18 destination constraint reuses. Every one of these must be exercised by at
# least one declared invalid fixture, or the gate it names is unproven.
REQUIRED_FIXTURE_CODES = (
    "CITATION_UNVERIFIED",
    "BOARD_INTERLOCK_CONFLICT",
    "BOARD_RECOVERY_REQUIRED",
    "ILLEGAL_ENUM",
)

LINK_RE = re.compile(r"(?<!!)\[(?:[^\]\[]|\[[^\]]*\])*\]\(\s*<?([^)<>\s]+)>?(?:\s+\"[^\"]*\")?\s*\)")

# ---------------------------------------------------------------------------
# emitter
# ---------------------------------------------------------------------------


class Report:
    def __init__(self) -> None:
        self.lines: list[str] = []
        self.failures = 0

    @property
    def failed(self) -> bool:
        return self.failures > 0

    def mark(self) -> int:
        """Return the current failure count, for scoping a PASS line to one check."""
        return self.failures

    def ok(self, check: str, detail: str, since: int | None = None) -> None:
        """Emit a PASS line only if no failure was recorded since `since`."""
        if since is not None and self.failures != since:
            return
        self.lines.append(f"PASS {check}: {detail}")

    def bad(self, path: str, location: str, code: str, message: str) -> None:
        self.failures += 1
        self.lines.append(f"FAIL {path}:{location} [{code}] {message}")

    def emit(self) -> int:
        for line in sorted(self.lines):
            print(line)
        return 1 if self.failed else 0


def rel(root: Path, p: Path) -> str:
    try:
        return PurePosixPath(p.relative_to(root).as_posix()).as_posix()
    except ValueError:
        return p.as_posix()


# ---------------------------------------------------------------------------
# markdown discovery
# ---------------------------------------------------------------------------


def governed_markdown(root: Path) -> list[Path]:
    """Root *.md plus .opencode/**/*.md, skipping node_modules and caches.

    M3 extends discovery by exactly one additional path, SKILL_TEMPLATE_RELPATH.
    It is authoring material outside .opencode/, so it is named explicitly
    rather than by widening the walk to all of docs/. Only the link and
    terminology checks consume this list, which is precisely the extension the
    M3 specification mandates. The file is appended only when it exists: the
    link check must resolve only existing files, and the template is authored
    after this harness lands.
    """
    out: list[Path] = []
    for entry in sorted(root.glob("*.md")):
        if entry.is_file():
            out.append(entry)
    template = root / SKILL_TEMPLATE_RELPATH
    if template.is_file():
        out.append(template)
    opencode = root / ".opencode"
    if opencode.is_dir():
        for dirpath, dirnames, filenames in os.walk(opencode):
            dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
            for fn in sorted(filenames):
                if fn.endswith(".md"):
                    out.append(Path(dirpath) / fn)
    return out


def is_fixture_payload(root: Path, p: Path) -> bool:
    return "/.opencode/schema/fixtures/" in "/" + rel(root, p)


def read_text(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


FENCE_RE = re.compile(r"^(\s*)(`{3,}|~{3,})", re.MULTILINE)


def strip_code(text: str) -> str:
    """Blank out fenced code blocks and inline code spans, preserving line count."""
    lines = text.split("\n")
    out: list[str] = []
    fence: str | None = None
    for line in lines:
        stripped = line.lstrip()
        if fence is None:
            m = re.match(r"(`{3,}|~{3,})", stripped)
            if m:
                fence = m.group(1)[0] * 3
                out.append("")
                continue
        else:
            m = re.match(r"(`{3,}|~{3,})", stripped)
            if m and m.group(1)[0] * 3 == fence:
                fence = None
                out.append("")
                continue
            out.append("")
            continue
        # inline code
        out.append(re.sub(r"`[^`]*`", lambda mm: " " * len(mm.group(0)), line))
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Check 1 - frontmatter
# ---------------------------------------------------------------------------


class FMError(Exception):
    def __init__(self, line: int, code: str, message: str) -> None:
        super().__init__(message)
        self.line = line
        self.code = code
        self.message = message


def parse_frontmatter(text: str) -> dict:
    """Parse the constrained YAML subset: nested mappings, block scalars, scalars."""
    lines = text.split("\n")
    if not lines or lines[0].rstrip("\r") != "---":
        raise FMError(1, "FRONTMATTER_DELIMITER", "file does not begin with a '---' frontmatter delimiter")
    end = None
    for i in range(1, len(lines)):
        if lines[i].rstrip("\r") == "---":
            end = i
            break
    if end is None:
        raise FMError(1, "FRONTMATTER_DELIMITER", "no closing '---' frontmatter delimiter found")
    body = [ln.rstrip("\r") for ln in lines[1:end]]
    offsets = list(range(2, end + 1))
    return _parse_block(body, offsets, 0, 0, len(body))[0]


def _indent_of(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _parse_block(lines: list[str], offsets: list[int], indent: int, start: int, stop: int) -> tuple[dict, int]:
    result: dict = {}
    i = start
    while i < stop:
        raw = lines[i]
        lineno = offsets[i]
        if "\t" in raw:
            raise FMError(lineno, "FRONTMATTER_TAB", "tab character is not permitted in frontmatter")
        if not raw.strip():
            i += 1
            continue
        if raw.strip().startswith("#"):
            i += 1
            continue
        cur = _indent_of(raw)
        if cur < indent:
            break
        if cur > indent:
            raise FMError(lineno, "FRONTMATTER_INDENT", f"unexpected indentation (expected {indent} spaces, got {cur})")
        content = raw[cur:]
        if content.startswith("- "):
            raise FMError(lineno, "FRONTMATTER_UNSUPPORTED", "block sequences are not part of the supported subset")
        m = re.match(r'^("(?:[^"\\]|\\.)*"|\'[^\']*\'|[^:]+?)\s*:(?:\s+(.*))?$', content)
        if not m:
            raise FMError(lineno, "FRONTMATTER_SYNTAX", f"line is not a supported 'key: value' mapping entry: {content!r}")
        key_raw, value_raw = m.group(1), m.group(2)
        key = _unquote(key_raw)
        if key in result:
            raise FMError(lineno, "FRONTMATTER_DUPLICATE_KEY", f"duplicate key {key!r}")
        value_raw = "" if value_raw is None else value_raw.strip()
        if value_raw.startswith("#"):
            value_raw = ""
        if value_raw in ("|", "|-", "|+", ">", ">-", ">+"):
            folded = value_raw[0] == ">"
            chunk, i = _collect_scalar_block(lines, offsets, indent, i + 1, stop)
            result[key] = _join_block(chunk, folded, value_raw)
            continue
        if value_raw == "":
            # nested mapping (or empty)
            j = i + 1
            while j < stop and (not lines[j].strip() or lines[j].strip().startswith("#")):
                j += 1
            if j < stop and _indent_of(lines[j]) > indent:
                sub_indent = _indent_of(lines[j])
                k = j
                while k < stop:
                    if not lines[k].strip() or lines[k].strip().startswith("#"):
                        k += 1
                        continue
                    if _indent_of(lines[k]) < sub_indent:
                        break
                    k += 1
                sub, _ = _parse_block(lines, offsets, sub_indent, j, k)
                result[key] = sub
                i = k
                continue
            result[key] = {}
            i = j
            continue
        if value_raw.startswith(("[", "{", "&", "*", "!")):
            raise FMError(lineno, "FRONTMATTER_UNSUPPORTED", f"unsupported YAML construct in value for {key!r}")
        result[key] = _unquote(value_raw)
        i += 1
    return result, i


def _collect_scalar_block(lines: list[str], offsets: list[int], indent: int, start: int, stop: int) -> tuple[list[str], int]:
    chunk: list[str] = []
    i = start
    while i < stop:
        raw = lines[i]
        if "\t" in raw:
            raise FMError(offsets[i], "FRONTMATTER_TAB", "tab character is not permitted in frontmatter")
        if not raw.strip():
            chunk.append("")
            i += 1
            continue
        if _indent_of(raw) <= indent:
            break
        chunk.append(raw)
        i += 1
    return chunk, i


def _join_block(chunk: list[str], folded: bool, marker: str) -> str:
    if not chunk:
        return ""
    widths = [_indent_of(c) for c in chunk if c.strip()]
    base = min(widths) if widths else 0
    body = [c[base:] if c.strip() else "" for c in chunk]
    if folded:
        paras: list[str] = []
        cur: list[str] = []
        for line in body:
            if line.strip():
                cur.append(line.strip())
            else:
                paras.append(" ".join(cur))
                cur = []
        paras.append(" ".join(cur))
        text = "\n".join(paras)
    else:
        text = "\n".join(body)
    if marker.endswith("-"):
        text = text.rstrip("\n")
    elif not marker.endswith("+"):
        text = text.rstrip("\n") + "\n"
    return text


def _unquote(s: str) -> str:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        inner = s[1:-1]
        if s[0] == '"':
            return inner.replace('\\"', '"').replace("\\\\", "\\")
        return inner.replace("''", "'")
    return s


SKILL_REQUIRED = ("name", "description", "compatibility")
AGENT_REQUIRED = ("description", "mode", "permission")
AGENT_ALLOWED_TOP = {"description", "mode", "permission", "model", "temperature", "tools", "name"}
SKILL_ALLOWED_TOP = {"name", "description", "compatibility", "license", "allowed-tools"}


def check_frontmatter(root: Path, report: Report) -> None:
    mark = report.mark()
    targets: list[tuple[Path, str]] = []
    agents_dir = root / ".opencode" / "agents"
    if agents_dir.is_dir():
        for p in sorted(agents_dir.glob("*.md")):
            targets.append((p, "agent"))
    skills_dir = root / ".opencode" / "skills"
    if skills_dir.is_dir():
        for p in sorted(skills_dir.glob("*/SKILL.md")):
            targets.append((p, "skill"))

    if not targets:
        report.bad(".opencode", "0", "FRONTMATTER_NO_TARGETS", "no agent or skill files found; expected .opencode/agents/*.md and .opencode/skills/*/SKILL.md")
        return

    checked = 0
    for path, kind in targets:
        r = rel(root, path)
        try:
            data = parse_frontmatter(read_text(path))
        except FMError as exc:
            report.bad(r, str(exc.line), exc.code, exc.message)
            continue
        except OSError as exc:
            report.bad(r, "0", "FRONTMATTER_UNREADABLE", f"cannot read file: {exc}")
            continue

        required = SKILL_REQUIRED if kind == "skill" else AGENT_REQUIRED
        allowed = SKILL_ALLOWED_TOP if kind == "skill" else AGENT_ALLOWED_TOP
        missing = [k for k in required if k not in data]
        if missing:
            report.bad(r, "frontmatter", "FRONTMATTER_MISSING_FIELD", f"missing required top-level field(s): {', '.join(missing)}; add them to the frontmatter")
        extra = sorted(set(data) - allowed)
        if extra:
            report.bad(r, "frontmatter", "FRONTMATTER_UNKNOWN_FIELD", f"unknown top-level field(s): {', '.join(extra)}; adding a field requires revising the peer schema in tools/selfcheck.py")

        desc = data.get("description")
        if desc is not None:
            if not isinstance(desc, str):
                report.bad(r, "description", "FRONTMATTER_TYPE", "description must be a scalar string, not a mapping")
            elif not desc.strip():
                report.bad(r, "description", "FRONTMATTER_EMPTY", "description must not be empty")

        if kind == "skill":
            name = data.get("name")
            if name is not None and (not isinstance(name, str) or not name.strip()):
                report.bad(r, "name", "FRONTMATTER_TYPE", "name must be a nonempty scalar string")
            elif isinstance(name, str) and name.strip() != path.parent.name:
                report.bad(r, "name", "FRONTMATTER_NAME_MISMATCH", f"name {name.strip()!r} does not match directory name {path.parent.name!r}")
            compat = data.get("compatibility")
            if compat is not None and compat != "opencode":
                report.bad(r, "compatibility", "FRONTMATTER_ILLEGAL_VALUE", f"compatibility must be 'opencode', got {compat!r}")
        else:
            mode = data.get("mode")
            if mode is not None and mode not in ("primary", "subagent"):
                report.bad(r, "mode", "FRONTMATTER_ILLEGAL_ENUM", f"mode must be 'primary' or 'subagent', got {mode!r}")
            perm = data.get("permission")
            if perm is not None:
                if not isinstance(perm, dict):
                    report.bad(r, "permission", "FRONTMATTER_TYPE", "permission must be a mapping")
                elif not perm:
                    report.bad(r, "permission", "FRONTMATTER_EMPTY", "permission mapping must not be empty")
        checked += 1

    report.ok("frontmatter", f"{checked} of {len(targets)} agent/skill frontmatter blocks parsed and conform to the peer schema", mark)


# ---------------------------------------------------------------------------
# Check 2 - links
# ---------------------------------------------------------------------------

IGNORED_SCHEMES = ("http:", "https:", "mailto:", "ftp:", "tel:", "data:")


def check_links(root: Path, report: Report) -> None:
    mark = report.mark()
    files = [p for p in governed_markdown(root) if not is_fixture_payload(root, p)]
    skip_names = {"package.json", "package-lock.json"}
    checked = 0
    total_links = 0
    for path in files:
        if path.name in skip_names:
            continue
        r = rel(root, path)
        try:
            text = read_text(path)
        except OSError as exc:
            report.bad(r, "0", "LINK_UNREADABLE", f"cannot read file: {exc}")
            continue
        scrubbed = strip_code(text)
        checked += 1
        for lineno, line in enumerate(scrubbed.split("\n"), start=1):
            for m in LINK_RE.finditer(line):
                target = m.group(1).strip()
                if not target:
                    continue
                low = target.lower()
                if low.startswith(IGNORED_SCHEMES) or low.startswith("//"):
                    continue
                if target.startswith("#"):
                    continue
                if re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target) and not target.startswith("./") and not target.startswith("../"):
                    continue
                total_links += 1
                bare = target.split("#", 1)[0].split("?", 1)[0]
                if not bare:
                    continue
                bare = urllib.parse.unquote(bare)
                if bare.startswith("/"):
                    resolved = (root / bare.lstrip("/")).resolve()
                else:
                    resolved = (path.parent / bare).resolve()
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    report.bad(r, str(lineno), "LINK_ESCAPES_REPO", f"relative link {target!r} resolves outside the repository; use a repository-relative target")
                    continue
                if not resolved.is_file():
                    report.bad(r, str(lineno), "LINK_BROKEN", f"relative link {target!r} does not resolve to a regular file (looked for {rel(root, resolved)})")
    report.ok("links", f"{total_links} relative Markdown links in {checked} files resolve to regular files", mark)


# ---------------------------------------------------------------------------
# Check 3 - validator against fixtures
# ---------------------------------------------------------------------------

CODE_RE = re.compile(r"Expected diagnostic code:\s*`?([A-Z][A-Z0-9_]+)`?")
FIXTURE_FILE_RE = re.compile(r"Expected file:\s*`([^`]+)`")
FIXTURE_FIELD_RE = re.compile(r"Expected field:\s*`([^`]+)`")
FIXTURE_EXACT_RE = re.compile(r"Expected diagnostics:\s*exact\b")
# Retired by M6/E13 and kept only as near-miss data for the declaration-parser
# self-test: the new pipe-delimited form must NOT match either legacy shape.
LEGACY_FIXTURE_DECL_RES = (CODE_RE, FIXTURE_FILE_RE, FIXTURE_FIELD_RE, FIXTURE_EXACT_RE)
# M6/E13: one declaration per expected diagnostic, pipe-delimited.
EXPECTED_DIAG_RE = re.compile(
    r"Expected diagnostic:\s*`?([^`|\n]+)\|([^`|\n]*)\|([A-Z][A-Z0-9_]*)`?")


# `ERROR <where>:<field> [<CODE>] expected ...` (validate.py Reporter.emit).
# `where` is a repository-relative path or '-', neither of which contains a
# colon, so the FIRST colon separates path from field. The field may itself
# contain colons (canonical stage IDs do), hence the non-greedy path group.
DIAG_RE = re.compile(r"^ERROR ([^:\s]+):(\S*) \[([A-Z][A-Z0-9_]*)\] ")


def parse_diagnostics(out: str) -> list[tuple[str, str, str]]:
    """(file, field, code) for every diagnostic line the validator printed."""
    found = []
    for line in out.splitlines():
        m = DIAG_RE.match(line.strip())
        if m:
            found.append((m.group(1), m.group(2), m.group(3)))
    return found


def declared_diagnostics(readme_text: str) -> list[tuple[str, str, str]]:
    """Every 'Expected diagnostic: <file>|<field>|<code>' declaration, in file order.

    M6/E13. The legacy forms - a single 'Expected diagnostic code:' line, and
    the opt-in 'Expected diagnostics: exact' trio - let a fixture pass while
    the validator emitted a pile of OTHER diagnostics it never declared. The
    pipe-delimited form is one declaration per expected diagnostic, so a fixture
    with genuinely several is still held to its exact set.
    """
    out: list[tuple[str, str, str]] = []
    for m in EXPECTED_DIAG_RE.finditer(readme_text):
        out.append((m.group(1).strip(), m.group(2).strip(), m.group(3).strip()))
    return out


def declaration_parser_failures() -> list[str]:
    """Self-test declared_diagnostics. An unproven parser turns exact mode vacuous."""
    sample = (
        "# 33-citation-excerpt-absent\n"
        "Expected diagnostic: `02-facts.toml|facts.citations.0.excerpt|CITATION_UNVERIFIED`\n"
        "Expected diagnostic: `state.toml|stages.write-driver:beta.status|DEPENDENCY_NOT_READY`\n"
        "Expected diagnostic code: `LEGACY_FORM_MUST_NOT_MATCH`\n"
    )
    want = [
        ("02-facts.toml", "facts.citations.0.excerpt", "CITATION_UNVERIFIED"),
        ("state.toml", "stages.write-driver:beta.status", "DEPENDENCY_NOT_READY"),
    ]
    got = declared_diagnostics(sample)
    if got != want:
        return [f"declared_diagnostics returned {got}, expected {want}"]
    if declared_diagnostics("Expected diagnostic code: `ONLY_LEGACY`\n"):
        return ["declared_diagnostics accepted the retired 'Expected diagnostic code:' form"]
    return []


def mandated_fixture_names(root: Path) -> tuple[list[str], str | None]:
    """Invalid-fixture names DECLARED by the committed generator input.

    Returns (names, error). The declaration file is the single source of both
    the fixture set and the expected diagnostics; this harness derives the
    mandated count from it rather than restating a number that would drift.
    """
    path = root / FIXTURE_DECL_RELPATH
    if not path.is_file():
        return [], (f"{FIXTURE_DECL_RELPATH} is absent; the mandated invalid-fixture set cannot be "
                    "derived and the coverage floor would be a literal this harness invented")
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError, UnicodeDecodeError) as exc:
        return [], f"{FIXTURE_DECL_RELPATH} does not parse as TOML: {_one_line(str(exc), 200)}"
    entries = data.get("invalid")
    if not isinstance(entries, list) or not entries:
        return [], (f"{FIXTURE_DECL_RELPATH} declares no nonempty 'invalid' array of tables; "
                    "each entry must carry a 'name' naming one invalid fixture root")
    names: list[str] = []
    for i, entry in enumerate(entries):
        if not isinstance(entry, dict) or not isinstance(entry.get("name"), str) or not entry["name"]:
            return [], f"{FIXTURE_DECL_RELPATH} entry invalid[{i}] has no nonempty string 'name'"
        names.append(entry["name"])
    return names, None


def run_validator(root: Path, validator: Path, fixture: Path) -> tuple[int | None, str]:

    gen = (fixture / "generation-roots" / "fictional-pac").resolve()
    cmd = [
        sys.executable,
        str(validator),
        str((fixture / "root").resolve()),
        "--root",
        f"generation:fictional-pac={gen}",
    ]
    try:
        proc = subprocess.run(
            cmd,
            cwd=str(root),
            capture_output=True,
            text=True,
            timeout=SUBPROCESS_TIMEOUT,
            encoding="utf-8",
            errors="replace",
        )
    except subprocess.TimeoutExpired:
        return None, f"timed out after {SUBPROCESS_TIMEOUT}s"
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def diagnostic_parser_failures() -> list[str]:
    """Self-test parse_diagnostics against the validator's exact line shape.

    Exact mode is only as good as this parser: a parser that silently matched
    nothing would turn every exact assertion into 'got none parsed'. These
    cases pin the shapes that actually occur, including a field that itself
    contains a colon (canonical stage IDs do).
    """
    sample = (
        "ERROR halucinator/handoff/04-pac.toml:handoff.inputs [DEPENDENCY_NOT_READY] expected x; found y; action: z\n"
        "ERROR halucinator/state.toml:stages.write-driver:beta.status [DEPENDENCY_NOT_READY] expected x; found y; action: z\n"
        "ERROR halucinator/handoff/05-platform-extra.toml:- [UNKNOWN_FIELD] expected x; found y; action: z\n"
        "ERROR -:- [PATH_ESCAPE] expected x; found y; action: z\n"
        "this is not a diagnostic line\n"
    )
    want = [
        ("halucinator/handoff/04-pac.toml", "handoff.inputs", "DEPENDENCY_NOT_READY"),
        ("halucinator/state.toml", "stages.write-driver:beta.status", "DEPENDENCY_NOT_READY"),
        ("halucinator/handoff/05-platform-extra.toml", "-", "UNKNOWN_FIELD"),
        ("-", "-", "PATH_ESCAPE"),
    ]
    got = parse_diagnostics(sample)
    return [] if got == want else [f"parse_diagnostics returned {got}, expected {want}"]


def check_fixtures(root: Path, report: Report) -> None:
    mark = report.mark()
    for problem in diagnostic_parser_failures():
        report.bad("tools/selfcheck.py", "parse_diagnostics", "FIXTURE_PARSER",
                   f"the exact-mode diagnostic parser failed its self-test: {problem}")
    for problem in declaration_parser_failures():
        report.bad("tools/selfcheck.py", "declared_diagnostics", "FIXTURE_PARSER",
                   f"the README declaration parser failed its self-test: {problem}")
    validator = root / ".opencode" / "schema" / "validate.py"
    fixtures = root / ".opencode" / "schema" / "fixtures"
    if not validator.is_file():
        report.bad(rel(root, validator), "0", "VALIDATOR_MISSING", "validator script not found; check 3 cannot run")
        return
    # Every accepted root, not just `valid/`. A second coherent root is how a
    # binding rule is proved to be independent of driver count; hardcoding one
    # directory here is what let that gap exist.
    valid_roots = sorted(
        p for p in fixtures.iterdir()
        if p.is_dir() and (p.name == "valid" or p.name.startswith("valid-"))
        and (p / "root").is_dir()
    ) if fixtures.is_dir() else []
    valid = fixtures / "valid"
    if not valid.is_dir():
        report.bad(rel(root, valid), "0", "FIXTURE_MISSING", "valid fixture directory not found")
        return
    if len(valid_roots) < 2:
        report.bad(rel(root, fixtures), "0", "FIXTURE_VALID_ROOTS",
                   f"expected at least 2 accepted fixture roots (valid/ plus a multi-driver root), found {len(valid_roots)}: "
                   f"{[p.name for p in valid_roots]}")

    for vr in valid_roots:
        rc, out = run_validator(root, validator, vr)
        if rc != 0:
            report.bad(rel(root, vr), "0", "FIXTURE_VALID_REJECTED", f"valid fixture must exit 0, got {rc}: {_one_line(out)}")
        elif out.strip():
            report.bad(rel(root, vr), "0", "FIXTURE_VALID_NOISY", f"valid fixture must emit no diagnostics: {_one_line(out)}")

    invalid_dir = fixtures / "invalid"
    cases = sorted(p for p in invalid_dir.glob("[0-9][0-9]-*") if p.is_dir()) if invalid_dir.is_dir() else []
    declared_names, decl_err = mandated_fixture_names(root)
    if decl_err:
        report.bad(FIXTURE_DECL_RELPATH, "0", "FIXTURE_DECL_UNDERIVABLE", decl_err)
        mandated = FIXTURE_FLOOR
    else:
        mandated = len(declared_names)
        if mandated < FIXTURE_FLOOR:
            report.bad(FIXTURE_DECL_RELPATH, "invalid", "FIXTURE_DECL_SHRANK",
                       f"declares {mandated} invalid fixtures, fewer than the {FIXTURE_FLOOR} the corpus already "
                       "carried; deriving the count must not become a way to lower the bar")
        missing_on_disk = sorted(set(declared_names) - {p.name for p in cases})
        extra_on_disk = sorted({p.name for p in cases} - set(declared_names))
        if missing_on_disk:
            report.bad(rel(root, invalid_dir), "0", "FIXTURE_DECL_MISSING",
                       f"{len(missing_on_disk)} declared invalid fixture root(s) are absent from the corpus, "
                       f"first: {', '.join(missing_on_disk[:6])}")
        if extra_on_disk:
            report.bad(FIXTURE_DECL_RELPATH, "invalid", "FIXTURE_DECL_UNDECLARED",
                       f"{len(extra_on_disk)} committed invalid fixture root(s) are not declared, "
                       f"first: {', '.join(extra_on_disk[:6])}")
    if len(cases) < mandated:
        report.bad(rel(root, invalid_dir), "0", "FIXTURE_SET_INCOMPLETE",
                   f"expected at least {mandated} invalid fixtures, found {len(cases)}")

    passed = 0
    covered_codes: set[str] = set()
    for case in cases:
        r = rel(root, case)
        readme = case / "README.md"
        if not readme.is_file():
            report.bad(r, "0", "FIXTURE_README_MISSING", "invalid fixture has no README.md declaring its expected diagnostics")
            continue
        readme_text = read_text(readme)
        declared = declared_diagnostics(readme_text)
        if not declared:
            report.bad(rel(root, readme), "0", "FIXTURE_CODE_UNDECLARED",
                       "README.md declares no 'Expected diagnostic: `<file>|<field>|<CODE>`' line; the retired "
                       "'Expected diagnostic code:' and opt-in 'Expected diagnostics: exact' forms no longer satisfy "
                       "E13, because neither pins the diagnostics the validator must NOT also emit")
            continue
        covered_codes.update(c for _, _, c in declared)
        rc, out = run_validator(root, validator, case)
        if rc is None:
            report.bad(r, "0", "FIXTURE_TIMEOUT", f"validator {out}; a hang is a failure")
            continue
        if rc != 1:
            report.bad(r, "0", "FIXTURE_WRONG_EXIT", f"expected exit 1, got {rc}; output: {_one_line(out)}")
            continue
        # Exact SET, not multiset: validate.py's Reporter stores its lines in a
        # set, so a repeated diagnostic is unobservable here and a multiset
        # assertion would be unimplementable rather than merely strict.
        want = sorted(set(declared))
        got = sorted(set(parse_diagnostics(out)))
        if got != want:
            missing = [d for d in want if d not in got]
            extra = [d for d in got if d not in want]
            report.bad(r, "0", "FIXTURE_EXACT_MISMATCH",
                       f"exact diagnostic set mismatch; undelivered: {missing or 'none'}; undeclared: {extra or 'none'}")
            continue
        passed += 1

    uncovered = [c for c in REQUIRED_FIXTURE_CODES if c not in covered_codes]
    if uncovered:
        report.bad(rel(root, invalid_dir), "0", "FIXTURE_CODE_UNCOVERED",
                   f"no invalid fixture declares {', '.join(uncovered)}; a diagnostic with no rejecting fixture "
                   "has never been shown to fire, so the gate it names is unproven")

    report.ok("fixtures",
              f"{len(valid_roots)} accepted fixture roots exit 0 silently and {passed} of {len(cases)} invalid "
              f"fixtures ({mandated} declared in {FIXTURE_DECL_RELPATH}) are rejected with exit 1 and an exact "
              f"diagnostic SET equal to their README declarations, covering {len(REQUIRED_FIXTURE_CODES)} required "
              "codes. Set, not multiset: Reporter deduplicates, so a duplicated diagnostic is unobservable", mark)



def _one_line(s: str, limit: int = 300) -> str:
    s = " ".join(s.split())
    return s[:limit] + ("..." if len(s) > limit else "")


# ---------------------------------------------------------------------------
# Check 4 - terminology
# ---------------------------------------------------------------------------

URL_RE = re.compile(r"<?https?://\S+>?")


def untracked_working_state(root: Path) -> set[str]:
    """Members of UNTRACKED_WORKING_STATE that are not tracked by Git.

    Asking Git keeps the exclusion honest: a file that gets committed becomes
    governed prose again without anyone editing this list. When Git is
    unavailable the closed list is applied as written, which cannot widen it.
    """
    candidates: set[str] = set(UNTRACKED_WORKING_STATE)
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z", "--", *UNTRACKED_WORKING_STATE],
            capture_output=True, timeout=SUBPROCESS_TIMEOUT,
        )
    except (OSError, subprocess.SubprocessError):
        return candidates
    if proc.returncode != 0:
        return candidates
    tracked = {p for p in proc.stdout.decode("utf-8", "replace").split("\0") if p}
    return candidates - tracked


def terminology_targets(root: Path) -> list[Path]:
    out = []
    excluded = untracked_working_state(root)
    for p in governed_markdown(root):
        if is_fixture_payload(root, p):
            continue
        r = rel(root, p)
        if r == ".opencode/schema/terminology.md":
            continue
        if r in excluded:
            continue
        out.append(p)
    return out


def count_tokens(text: str) -> dict[str, int]:
    scrubbed = URL_RE.sub(" ", strip_code(text))
    counts: dict[str, int] = {}
    for token in REJECTED_TOKENS:
        pat = re.compile(r"(?<![A-Za-z0-9_-])" + re.escape(token) + r"(?![A-Za-z0-9_-])")
        n = len(pat.findall(scrubbed))
        if n:
            counts[token] = n
    return counts


def scan_terminology(root: Path) -> dict[tuple[str, str], int]:
    found: dict[tuple[str, str], int] = {}
    for p in terminology_targets(root):
        try:
            text = read_text(p)
        except OSError:
            continue
        for token, n in count_tokens(text).items():
            found[(rel(root, p), token)] = n
    return found


def load_baseline(path: Path) -> dict[tuple[str, str], int]:
    base: dict[tuple[str, str], int] = {}
    for line in path.read_text(encoding="utf-8").split("\n"):
        line = line.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) != 3:
            continue
        p, token, count = parts
        try:
            base[(p, token)] = int(count)
        except ValueError:
            continue
    return base


def write_baseline(root: Path) -> Path:
    path = root / BASELINE_RELPATH
    found = scan_terminology(root)
    lines = [
        "# terminology baseline for tools/selfcheck.py check 4",
        "# format: <repo-relative-posix-path>\\t<token>\\t<count>",
        "# regenerate: python tools/selfcheck.py --write-terminology-baseline",
    ]
    for (p, token) in sorted(found):
        lines.append(f"{p}\t{token}\t{found[(p, token)]}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return path


def check_terminology(root: Path, report: Report) -> None:
    mark = report.mark()
    baseline_path = root / BASELINE_RELPATH
    if not baseline_path.is_file():
        report.bad(BASELINE_RELPATH, "0", "TERMINOLOGY_BASELINE_MISSING", "checked-in terminology baseline is absent; regenerate with 'python tools/selfcheck.py --write-terminology-baseline'")
        return
    baseline = load_baseline(baseline_path)
    found = scan_terminology(root)
    new = 0
    for key in sorted(found):
        path, token = key
        allowed = baseline.get(key, 0)
        actual = found[key]
        if actual > allowed:
            new += 1
            report.bad(path, "prose", "TERMINOLOGY_REJECTED_TOKEN", f"{actual - allowed} new occurrence(s) of rejected token {token!r} (baseline allows {allowed}); use the accepted spelling from .opencode/schema/terminology.md")
    if new == 0:
        total = sum(found.values())
        report.ok("terminology", f"no new occurrences of {len(REJECTED_TOKENS)} rejected tokens across {len(terminology_targets(root))} governed files ({total} baselined legacy occurrences)", mark)


# ---------------------------------------------------------------------------
# Milestone M2 - eight-agent topology, ownership registry, config
#
# Every check below parses *raw* Markdown. strip_code() blanks every fenced
# block regardless of its info string (see :162-188), and the M2 agent contract
# lives inside a fence, so these checks must never consume stripped text.
# ---------------------------------------------------------------------------

import json
import tomllib

AGENT_NAMES = (
    "hal-architect",
    "hal-coordinator",
    "hal-datasheet",
    "hal-driver",
    "hal-integrator",
    "hal-reviewer",
    "hal-svd",
    "hal-tester",
)
PRIMARY_AGENT = "hal-coordinator"
SPECIALISTS = tuple(n for n in AGENT_NAMES if n != PRIMARY_AGENT)

CONTRACT_INFO = "halucinator-agent-contract"
CONTRACT_KEYS = ("owner", "owns", "emits", "state-writes", "dispatched-by", "may-dispatch")
CONTRACT_SINGLE = ("owner", "state-writes", "dispatched-by", "may-dispatch")

EXPECTED_EMITS = {
    "hal-coordinator": ("none",),
    "hal-architect": ("none",),
    "hal-datasheet": ("01-sources", "02-facts"),
    "hal-svd": ("03-svd", "04-pac"),
    "hal-integrator": ("05-platform",),
    "hal-driver": ("06-driver",),
    "hal-tester": ("07-tests",),
    "hal-reviewer": ("08-review",),
}

CONFLICT_IDS = {
    "hal-coordinator": "2,4,5,6,7,8,9",
    "hal-architect": "1,2,6,8,9",
    "hal-datasheet": "5",
    "hal-svd": "4",
    "hal-driver": "1,6,9",
    "hal-tester": "2,3,7,9",
    "hal-integrator": "1,2,3,4,5,6,7,8",
    "hal-reviewer": "9",
}

PRECEDENCE_SENTENCE = (
    "The agent contract and .opencode/ownership.toml override any skill or bundled reference "
    "instruction that assigns this task's file class, dispatch route, gate authority, or commit "
    "authority to another agent. Follow the skill's domain procedure only inside this agent's "
    "declared ownership boundary; return conflicting work to hal-coordinator."
)

DISPATCH_BLOCK = (
    "All Embassy HAL work enters through hal-coordinator. Specialist HAL agents are dispatched only "
    "by hal-coordinator with the typed payload their agent contract requires. Generic agents"
    "\u2014including build, plan, general, explore, coder, integrator, architect, reviewer, and "
    "tester\u2014may be used only for a bounded support task that hal-coordinator explicitly "
    "delegates. A generic agent may not own a workflow stage, mutate canonical HAL/PAC/test "
    "artifacts, change scope or decisions, accept a gate, or substitute for a HAL specialist. "
    "If routing is ambiguous, return to hal-coordinator rather than falling back."
)

VERDICT_SENTENCE = "Only review.verdict=ready accepts; ready-with-fixes and not-ready do not."
LEGACY_VERDICT_TOKENS = ("ready with fixes", "not ready")

ROADMAP_PATH = "halucinator/docs/<target-id>/notes/ROADMAP.md"
TEST_CANDIDATE_ROOT = "halucinator/test-candidates/"
REJECTED_SCRATCH = "halucinator/.run/"

INTEGRATOR_MARKERS = ("Preflight", "Integration lock", "Stage recovery", "Frozen candidate order")
TESTER_MARKERS = ("Three-attempt loop",)
SANITIZED_KEYS = ("category", "error_code", "test_location", "public_signature_mismatch", "message")

COMMIT_OWNER = "hal-integrator"
COMMIT_DENY_PATTERN = "git commit*"

MAX_CONTRACT_LINES = 400
MAX_REGISTRY_ENTRIES = 500
MAX_AST_DEPTH = 40
# Any backticked lowercase hyphenated token. This is deliberately NOT a verb
# prefix list: M5 adds `integrate-interrupts`, `integrate-runtime-linker` and
# `debug-hardware`, none of which begin with a verb the old
# (write|review|generate|gather|scaffold|extract) alternation matched, so all
# three would have been silently skipped by the reference scanner. Tokens are
# resolved against the DISCOVERED and CANONICAL skill-name sets instead, so a
# token that merely looks skill-shaped is not treated as a skill reference.
SKILL_TOKEN_RE = re.compile(r"\x00([a-z][a-z0-9]*(?:-[a-z0-9]+)+)\x00")


def norm_ws(text: str) -> str:
    """Whitespace-normalized, backtick-stripped prose for exact-sentence matching."""
    return " ".join(text.replace("`", "").replace("\u2019", "'").split())


def agent_paths(root: Path) -> dict[str, Path]:
    d = root / ".opencode" / "agents"
    if not d.is_dir():
        return {}
    return {p.stem: p for p in sorted(d.glob("*.md"))}


def guard(report: Report, path: str, code: str):
    """Context manager-free guard: convert any unexpected exception into a FAIL."""
    class _G:
        def __enter__(self_inner):
            return None

        def __exit__(self_inner, exc_type, exc, tb):
            if exc is None:
                return False
            report.bad(path, "0", code, f"check aborted on unexpected {exc_type.__name__}: {_one_line(str(exc), 200)}")
            return True

    return _G()


# --- raw contract parsing ---------------------------------------------------


def parse_contract(text: str, info: str = CONTRACT_INFO) -> tuple[list[tuple[str, str, int]], str | None, int]:
    """Parse the single raw ```<info> fence after the H1.

    Returns (entries, error, lineno). Entries are (key, value, lineno).
    Operates on RAW markdown: strip_code() would erase this block entirely.

    `info` is the fence info string. It defaults to the M2 agent contract so
    that every existing caller is unchanged; the M3 skill checks pass
    SKILL_CONTRACT_INFO to reuse this parser rather than reimplement it.
    """
    lines = text.split("\n")
    h1 = None
    for i, line in enumerate(lines):
        if line.startswith("# "):
            h1 = i
            break
    if h1 is None:
        return [], "file has no '# ' H1 heading; the contract must follow it", 1

    blocks: list[tuple[int, list[str]]] = []
    i = h1 + 1
    scanned = 0
    while i < len(lines) and scanned < MAX_CONTRACT_LINES * 8:
        scanned += 1
        stripped = lines[i].strip()
        if stripped.startswith("```") and stripped[3:].strip() == info:
            body: list[str] = []
            j = i + 1
            while j < len(lines) and len(body) < MAX_CONTRACT_LINES:
                if lines[j].strip().startswith("```"):
                    break
                body.append(lines[j])
                j += 1
            else:
                return [], f"unterminated '{info}' fence", i + 1
            if j >= len(lines):
                return [], f"unterminated '{info}' fence", i + 1
            blocks.append((i + 1, body))
            i = j + 1
            continue
        i += 1

    if not blocks:
        return [], f"no raw '```{info}' fence found after the H1; add the contract block", h1 + 1
    if len(blocks) > 1:
        return [], f"expected exactly one '{info}' fence, found {len(blocks)}", blocks[1][0]

    start, body = blocks[0]
    entries: list[tuple[str, str, int]] = []
    for off, raw in enumerate(body):
        if not raw.strip():
            continue
        if ":" not in raw:
            return [], f"contract line is not 'key: value': {raw.strip()!r}", start + 1 + off
        key, _, value = raw.partition(":")
        entries.append((key.strip(), value.strip(), start + 1 + off))
    return entries, None, start


def contract_map(entries: list[tuple[str, str, int]]) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for key, value, _ in entries:
        out.setdefault(key, []).append(value)
    return out


def check_topology(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "TOPOLOGY_ABORT"):
        found = agent_paths(root)
        missing = [n for n in AGENT_NAMES if n not in found]
        extra = sorted(set(found) - set(AGENT_NAMES))
        if missing:
            report.bad(".opencode/agents", "0", "TOPOLOGY_AGENT_MISSING",
                       f"missing agent definition(s): {', '.join(missing)}; M2 requires exactly the eight agents {', '.join(AGENT_NAMES)}")
        if extra:
            report.bad(".opencode/agents", "0", "TOPOLOGY_AGENT_UNEXPECTED",
                       f"unexpected agent definition(s): {', '.join(extra)}; remove or fold them into the eight-agent topology")
        for name in sorted(found):
            path = found[name]
            r = rel(root, path)
            try:
                data = parse_frontmatter(read_text(path))
            except (FMError, OSError) as exc:
                report.bad(r, "0", "TOPOLOGY_UNPARSEABLE", f"cannot read frontmatter for mode check: {exc}")
                continue
            mode = data.get("mode")
            want = "primary" if name == PRIMARY_AGENT else "subagent"
            if mode != want:
                report.bad(r, "mode", "TOPOLOGY_MODE",
                           f"mode is {mode!r} but {name} must be {want!r}; only {PRIMARY_AGENT} is primary")
        report.ok("topology", f"{len(AGENT_NAMES)} agents present and only {PRIMARY_AGENT} is primary", mark)


def check_contracts(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "CONTRACT_ABORT"):
        # Self-test: the raw-value terminology scanner must reject a known-bad value.
        if not count_token_values(["owns: initialisation-notes"]):
            report.bad("tools/selfcheck.py", "count_token_values", "CONTRACT_SCANNER_BROKEN",
                       "the raw contract terminology scanner failed its in-memory rejection case")
        found = agent_paths(root)
        ok = 0
        for name in AGENT_NAMES:
            path = found.get(name)
            if path is None:
                continue
            r = rel(root, path)
            text = read_text(path)
            entries, err, lineno = parse_contract(text)
            if err:
                report.bad(r, str(lineno), "CONTRACT_BLOCK", err)
                continue
            cmap = contract_map(entries)
            bad_keys = sorted(set(cmap) - set(CONTRACT_KEYS))
            if bad_keys:
                report.bad(r, str(lineno), "CONTRACT_UNKNOWN_KEY",
                           f"unknown contract key(s): {', '.join(bad_keys)}; allowed keys are {', '.join(CONTRACT_KEYS)}")
                continue
            missing = [k for k in CONTRACT_KEYS if k not in cmap]
            if missing:
                report.bad(r, str(lineno), "CONTRACT_MISSING_KEY",
                           f"contract is missing required key(s): {', '.join(missing)}")
                continue
            dup = [k for k in CONTRACT_SINGLE if len(cmap[k]) != 1]
            if dup:
                report.bad(r, str(lineno), "CONTRACT_REPEATED_KEY",
                           f"key(s) {', '.join(dup)} must appear exactly once")
                continue
            for value in cmap["owns"]:
                if "," in value:
                    report.bad(r, str(lineno), "CONTRACT_OWNS_LIST",
                               f"'owns: {value}' must name one ownership ID; repeat the key instead of comma-listing")
            hits = count_token_values([f"{k}: {v}" for k, v, _ in entries])
            if hits:
                report.bad(r, str(lineno), "CONTRACT_REJECTED_TOKEN",
                           f"contract values contain rejected terminology token(s) {', '.join(sorted(hits))}; "
                           "fenced contract text is invisible to the terminology check and must be clean")
            owner = cmap["owner"][0]
            if norm_ws(owner) not in norm_ws(text):
                report.bad(r, str(lineno), "CONTRACT_OWNER_PROSE",
                           "the 'owner:' ownership sentence does not appear verbatim in the agent prose")
            if cmap["dispatched-by"][0] not in (PRIMARY_AGENT, "user-via-default-agent"):
                report.bad(r, str(lineno), "CONTRACT_DISPATCHED_BY",
                           f"dispatched-by is {cmap['dispatched-by'][0]!r}; subagents must declare {PRIMARY_AGENT}")
            if name != PRIMARY_AGENT and cmap["may-dispatch"][0] != "none":
                report.bad(r, str(lineno), "CONTRACT_MAY_DISPATCH",
                           f"{name} declares may-dispatch {cmap['may-dispatch'][0]!r}; specialists must declare 'none'")
            ok += 1
        report.ok("contracts", f"{ok} of {len(AGENT_NAMES)} agent contract blocks parsed from raw Markdown and conform", mark)


def count_token_values(values: list[str]) -> set[str]:
    hits: set[str] = set()
    joined = "\n".join(values)
    for token in REJECTED_TOKENS:
        pat = re.compile(r"(?<![A-Za-z0-9_])" + re.escape(token) + r"(?![A-Za-z0-9_])")
        if pat.search(joined):
            hits.add(token)
    return hits


# --- ownership registry -----------------------------------------------------

ENTRY_REQUIRED = ("id", "owner", "patterns")
ENTRY_OPTIONAL = ("overrides",)
ID_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def glob_to_re(pattern: str) -> re.Pattern[str]:
    out = []
    i = 0
    while i < len(pattern):
        c = pattern[i]
        if pattern.startswith("**", i):
            out.append(".*")
            i += 2
            continue
        if c == "*":
            out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        else:
            out.append(re.escape(c))
        i += 1
    return re.compile("^" + "".join(out) + "$")


def load_registry(root: Path, report: Report) -> dict | None:
    path = root / ".opencode" / "ownership.toml"
    r = ".opencode/ownership.toml"
    if not path.is_file():
        report.bad(r, "0", "OWNERSHIP_REGISTRY_MISSING",
                   "the ownership registry does not exist; create .opencode/ownership.toml with schema = 1, sorted [[file_classes]], and [operations].commit_owner")
        return None
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        report.bad(r, "0", "OWNERSHIP_REGISTRY_MALFORMED", f"cannot parse registry TOML: {_one_line(str(exc), 200)}")
        return None
    return data


def check_ownership(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/ownership.toml", "OWNERSHIP_ABORT"):
        r = ".opencode/ownership.toml"
        data = load_registry(root, report)
        if data is None:
            return
        if data.get("schema") != 1:
            report.bad(r, "schema", "OWNERSHIP_SCHEMA", f"schema must be the integer 1, got {data.get('schema')!r}")
        classes = data.get("file_classes")
        if not isinstance(classes, list) or not classes:
            report.bad(r, "file_classes", "OWNERSHIP_NO_CLASSES", "registry must contain a nonempty [[file_classes]] array")
            return
        if len(classes) > MAX_REGISTRY_ENTRIES:
            report.bad(r, "file_classes", "OWNERSHIP_TOO_LARGE", f"registry has {len(classes)} entries, above the {MAX_REGISTRY_ENTRIES} bound")
            return
        ops = data.get("operations")
        if not isinstance(ops, dict) or sorted(ops) != ["commit_owner"]:
            report.bad(r, "operations", "OWNERSHIP_OPERATIONS", "[operations] must contain exactly commit_owner")
        elif ops.get("commit_owner") != COMMIT_OWNER:
            report.bad(r, "operations.commit_owner", "OWNERSHIP_COMMIT_OWNER",
                       f"commit_owner is {ops.get('commit_owner')!r}; the sole committer is {COMMIT_OWNER}")
        top_extra = sorted(set(data) - {"schema", "file_classes", "operations"})
        if top_extra:
            report.bad(r, "0", "OWNERSHIP_UNKNOWN_KEY", f"unknown top-level key(s): {', '.join(top_extra)}")

        ids: list[str] = []
        owners: dict[str, str] = {}
        pats: dict[str, list[str]] = {}
        overrides: dict[str, list[str]] = {}
        for idx, entry in enumerate(classes):
            loc = f"file_classes[{idx}]"
            if not isinstance(entry, dict):
                report.bad(r, loc, "OWNERSHIP_ENTRY_TYPE", "each file class must be a table")
                continue
            extra = sorted(set(entry) - set(ENTRY_REQUIRED) - set(ENTRY_OPTIONAL))
            if extra:
                report.bad(r, loc, "OWNERSHIP_UNKNOWN_KEY", f"unknown key(s) {', '.join(extra)}; allowed are id, owner, patterns, overrides")
            miss = [k for k in ENTRY_REQUIRED if k not in entry]
            if miss:
                report.bad(r, loc, "OWNERSHIP_MISSING_KEY", f"missing key(s): {', '.join(miss)}")
                continue
            cid, owner, patterns = entry["id"], entry["owner"], entry["patterns"]
            if not isinstance(cid, str) or not ID_RE.match(cid):
                report.bad(r, loc, "OWNERSHIP_ID_FORMAT", f"id {cid!r} must be lowercase hyphenated")
                continue
            if cid in owners:
                report.bad(r, loc, "OWNERSHIP_DUPLICATE_ID", f"duplicate file class id {cid!r}")
                continue
            if owner not in AGENT_NAMES:
                report.bad(r, loc, "OWNERSHIP_UNKNOWN_OWNER", f"owner {owner!r} is not one of the eight agents")
            if not isinstance(patterns, list) or not patterns or not all(isinstance(p, str) for p in patterns):
                report.bad(r, loc, "OWNERSHIP_PATTERNS", "patterns must be a nonempty array of strings")
                continue
            if list(patterns) != sorted(set(patterns)):
                report.bad(r, loc, "OWNERSHIP_PATTERNS_ORDER", f"patterns for {cid!r} must be sorted and unique")
            ov = entry.get("overrides", [])
            if not isinstance(ov, list) or not all(isinstance(p, str) for p in ov) or list(ov) != sorted(set(ov)):
                report.bad(r, loc, "OWNERSHIP_OVERRIDES", f"overrides for {cid!r} must be a sorted unique string array")
                ov = []
            ids.append(cid)
            owners[cid] = owner
            pats[cid] = list(patterns)
            overrides[cid] = list(ov)

        if ids != sorted(ids):
            report.bad(r, "file_classes", "OWNERSHIP_ORDER", "file classes must appear in ascending id order")
        for cid in ids:
            for other in overrides[cid]:
                if other not in owners:
                    report.bad(r, cid, "OWNERSHIP_OVERRIDES_UNKNOWN", f"{cid!r} overrides unknown class {other!r}")

        # Overlap: a narrower class covered by a broader one with a different
        # owner must declare an explicit override of that broader class.
        for a in ids:
            for b in ids:
                if a == b or owners.get(a) == owners.get(b):
                    continue
                covered = any(glob_to_re(pb).match(pa) for pa in pats[a] for pb in pats[b])
                if covered and b not in overrides[a] and a not in overrides[b]:
                    report.bad(r, a, "OWNERSHIP_OVERLAP",
                               f"class {a!r} ({owners[a]}) overlaps {b!r} ({owners[b]}) with a different owner and no overrides entry")

        # Agent claims must exactly partition the registry.
        found = agent_paths(root)
        claimed: dict[str, list[str]] = {}
        for name in AGENT_NAMES:
            path = found.get(name)
            if path is None:
                continue
            entries, err, _ = parse_contract(read_text(path))
            if err:
                continue
            for value in contract_map(entries).get("owns", []):
                claimed.setdefault(value.strip(), []).append(name)
        for cid, names in sorted(claimed.items()):
            if cid not in owners:
                report.bad(rel(root, found[names[0]]), "owns", "OWNERSHIP_UNKNOWN_CLAIM",
                           f"{names[0]} claims ownership ID {cid!r}, which is absent from the registry")
            elif len(names) > 1:
                report.bad(r, cid, "OWNERSHIP_DOUBLE_CLAIM", f"{cid!r} is claimed by {', '.join(sorted(names))}; exactly one agent may claim it")
            elif owners[cid] != names[0]:
                report.bad(r, cid, "OWNERSHIP_CLAIM_MISMATCH", f"{cid!r} is claimed by {names[0]} but the registry assigns it to {owners[cid]}")
        for cid in ids:
            if cid not in claimed:
                report.bad(r, cid, "OWNERSHIP_UNCLAIMED", f"registry class {cid!r} is claimed by no agent contract")
        report.ok("ownership", f"{len(ids)} registry classes well-formed and claimed exactly once", mark)


# --- structural field registry derived from validate.py AST -----------------


class RegistryError(Exception):
    pass


OPAQUE = object()


def _ast_eval(node: ast.AST, symbols: dict[str, ast.AST], depth: int = 0):
    if depth > MAX_AST_DEPTH:
        raise RegistryError("schema declaration nests deeper than the evaluator bound")
    if isinstance(node, ast.Constant):
        return node.value
    if isinstance(node, (ast.List, ast.Tuple)):
        return [_ast_eval(e, symbols, depth + 1) for e in node.elts]
    if isinstance(node, ast.Dict):
        out = {}
        for k, v in zip(node.keys, node.values):
            if k is None:
                raise RegistryError("dict unpacking is not evaluable")
            out[_ast_eval(k, symbols, depth + 1)] = _ast_eval(v, symbols, depth + 1)
        return out
    if isinstance(node, ast.Name):
        if node.id in symbols:
            return _ast_eval(symbols[node.id], symbols, depth + 1)
        return OPAQUE
    if isinstance(node, ast.Call):
        if isinstance(node.func, ast.Name) and node.func.id == "S":
            if not node.args:
                raise RegistryError("S() called without a kind argument")
            spec = {"type": _ast_eval(node.args[0], symbols, depth + 1)}
            for kw in node.keywords:
                if kw.arg is None:
                    raise RegistryError("S(**kwargs) is not evaluable")
                spec[kw.arg] = _ast_eval(kw.value, symbols, depth + 1)
            return spec
        return OPAQUE
    if isinstance(node, ast.Lambda):
        return OPAQUE
    raise RegistryError(f"unsupported AST node {type(node).__name__} in schema declaration")


def _enumerate(spec, prefix: str, out: set[str], depth: int = 0,
               arrays: set[str] | None = None) -> None:
    """Flatten a validator field declaration into dotted leaf paths.

    `arrays`, when supplied, additionally collects every prefix the schema
    declares with `type == "array"`. That type information is what lets the
    typed-example analyzer tell an empty ARRAY (a legal "known-empty
    collection") from an empty array standing where the schema requires a
    struct or a tagged union - `driver.build_contract` and `review.lineage`
    are both composite parents, and both reject `[]`.
    """
    if depth > MAX_AST_DEPTH:
        raise RegistryError("field tree nests deeper than the evaluator bound")
    if not isinstance(spec, dict) or "type" not in spec:
        out.add(prefix)
        return
    kind = spec["type"]
    if kind == "struct":
        fields = spec.get("fields") or {}
        if not isinstance(fields, dict):
            raise RegistryError(f"struct at {prefix} has non-mapping fields")
        for name, decl in fields.items():
            _enumerate(_decl_spec(decl), f"{prefix}.{name}", out, depth + 1, arrays)
        return
    if kind == "array":
        if arrays is not None:
            arrays.add(prefix)
        _enumerate(spec.get("items"), prefix, out, depth + 1, arrays)
        return
    if kind == "tagged":
        out.add(f"{prefix}.kind")
        variants = spec.get("variants") or {}
        if not isinstance(variants, dict):
            raise RegistryError(f"tagged at {prefix} has non-mapping variants")
        for vfields in variants.values():
            if not isinstance(vfields, dict):
                continue
            for name, decl in vfields.items():
                _enumerate(_decl_spec(decl), f"{prefix}.{name}", out, depth + 1, arrays)
        return
    out.add(prefix)


def _decl_spec(decl):
    if isinstance(decl, list) and decl:
        return decl[0]
    return decl


def derive_registry(validator: Path) -> dict[str, dict]:
    """Derive kind -> {stage, paths, checks} from validate.py without executing it."""
    try:
        tree = ast.parse(validator.read_text(encoding="utf-8"), filename=str(validator))
    except (OSError, SyntaxError, UnicodeDecodeError) as exc:
        raise RegistryError(f"cannot parse validator: {exc}") from exc
    symbols: dict[str, ast.AST] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for tgt in node.targets:
                if isinstance(tgt, ast.Name):
                    symbols[tgt.id] = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.value is not None:
            symbols[node.target.id] = node.value
    for required in ("HANDOFF_TABLE", "SCOPE_TABLE", "COVERAGE_TABLE", "KINDS"):
        if required not in symbols:
            raise RegistryError(f"validator declares no {required}; the structural registry cannot be derived")

    common: set[str] = set()
    common_arrays: set[str] = set()
    for name, table in (("handoff", "HANDOFF_TABLE"), ("scope", "SCOPE_TABLE"), ("coverage", "COVERAGE_TABLE")):
        value = _ast_eval(symbols[table], symbols)
        if not isinstance(value, dict):
            raise RegistryError(f"{table} did not evaluate to a mapping")
        for field, decl in value.items():
            _enumerate(_decl_spec(decl), f"{name}.{field}", common, arrays=common_arrays)
    for leaf in ("id", "status", "evidence", "reason"):
        common.add(f"checks.{leaf}")
    common_arrays.add("checks")

    kinds_value = _ast_eval(symbols["KINDS"], symbols)
    if not isinstance(kinds_value, dict) or not kinds_value:
        raise RegistryError("KINDS did not evaluate to a nonempty mapping")
    registry: dict[str, dict] = {}
    for kind, spec in kinds_value.items():
        if not isinstance(spec, dict):
            raise RegistryError(f"KINDS[{kind!r}] did not evaluate to a mapping")
        table = spec.get("table")
        fields = spec.get("fields")
        if not isinstance(table, str) or not isinstance(fields, dict):
            raise RegistryError(f"KINDS[{kind!r}] has no evaluable table/fields")
        paths: set[str] = set()
        kind_arrays: set[str] = set()
        for field, decl in fields.items():
            _enumerate(_decl_spec(decl), f"{table}.{field}", paths, arrays=kind_arrays)
        checks = spec.get("checks")
        registry[kind] = {
            "stage": spec.get("stage"),
            "table": table,
            "paths": paths,
            "arrays": kind_arrays,
            "common": common,
            "common_arrays": common_arrays,
            "checks": sorted(checks) if isinstance(checks, dict) else [],
        }
    return registry


def check_emissions(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/schema/validate.py", "EMISSION_ABORT"):
        validator = root / ".opencode" / "schema" / "validate.py"
        if not validator.is_file():
            report.bad(".opencode/schema/validate.py", "0", "EMISSION_NO_VALIDATOR", "validator absent; the structural field registry cannot be derived")
            return
        try:
            registry = derive_registry(validator)
        except RegistryError as exc:
            report.bad(".opencode/schema/validate.py", "0", "EMISSION_REGISTRY_UNDERIVABLE",
                       f"structural field registry could not be derived: {exc}")
            return
        found = agent_paths(root)
        checked = 0
        for name in AGENT_NAMES:
            path = found.get(name)
            if path is None:
                report.bad(f".opencode/agents/{name}.md", "0", "EMISSION_MISSING",
                           f"agent absent, so it declares no 'emits:' line; M2 assigns it {list(EXPECTED_EMITS.get(name, ()))}")
                continue
            r = rel(root, path)
            entries, err, lineno = parse_contract(read_text(path))
            if err:
                report.bad(r, str(lineno), "EMISSION_MISSING",
                           f"no parseable agent contract, so no 'emits:' declaration exists ({err})")
                continue
            values = contract_map(entries).get("emits", [])
            if not values:
                report.bad(r, str(lineno), "EMISSION_MISSING", "contract declares no 'emits:' line")
                continue
            declared_kinds = []
            for value in values:
                if "|" not in value:
                    report.bad(r, str(lineno), "EMISSION_FORMAT", f"emits value {value!r} must be '<kind>|<comma-separated paths>'")
                    continue
                kind, _, paths_raw = value.partition("|")
                kind, paths_raw = kind.strip(), paths_raw.strip()
                declared_kinds.append(kind)
                if kind == "none":
                    if paths_raw != "none":
                        report.bad(r, str(lineno), "EMISSION_FORMAT", "'emits: none|...' must be exactly 'none|none'")
                    continue
                if kind not in registry:
                    report.bad(r, str(lineno), "EMISSION_UNKNOWN_KIND",
                               f"emits kind {kind!r} is not a validator handoff kind ({', '.join(sorted(registry))})")
                    continue
                declared = {p.strip() for p in paths_raw.split(",") if p.strip()}
                expected = registry[kind]["paths"] | registry[kind]["common"]
                unknown = sorted(declared - expected)
                if unknown:
                    report.bad(r, str(lineno), "EMISSION_UNKNOWN_PATH",
                               f"{kind}: path(s) {', '.join(unknown[:8])} are not structurally valid schema paths for table {registry[kind]['table']!r}")
                missing = sorted(expected - declared)
                if missing:
                    report.bad(r, str(lineno), "EMISSION_INCOMPLETE",
                               f"{kind}: contract omits {len(missing)} required structural leaf path(s), first: {', '.join(missing[:8])}")
            want = list(EXPECTED_EMITS.get(name, ()))
            if sorted(declared_kinds) != sorted(want):
                report.bad(r, str(lineno), "EMISSION_WRONG_KINDS",
                           f"{name} declares emits kinds {sorted(declared_kinds)}; M2 assigns it {want}")
            checked += 1
        report.ok("emissions", f"{checked} agent emits declarations match the AST-derived registry of {len(registry)} kinds", mark)


# --- permissions ------------------------------------------------------------


def serialize_permission(perm: dict) -> dict[str, str]:
    def one(value) -> str:
        if isinstance(value, dict):
            return "; ".join(f"{k}={v}" for k, v in value.items())
        return f"*={value}"

    out = {}
    out["Edit"] = one(perm["edit"]) if "edit" in perm else "*=deny"
    out["Read"] = one(perm["read"]) if "read" in perm else "*=allow"
    out["Bash"] = one(perm["bash"]) if "bash" in perm else "*=ask"
    out["Dispatch"] = f"task={perm.get('task', 'deny')}" if not isinstance(perm.get("task"), dict) else one(perm["task"])
    return out


def section_of(text: str, heading: str) -> str | None:
    lines = text.split("\n")
    start = None
    for i, line in enumerate(lines):
        if line.strip().lstrip("#").strip() == heading and line.strip().startswith("#"):
            start = i + 1
            break
    if start is None:
        return None
    body = []
    for line in lines[start:]:
        if line.startswith("## "):
            break
        body.append(line)
    return "\n".join(body)


def check_permissions(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "PERMISSION_ABORT"):
        found = agent_paths(root)
        registry = load_registry(root, Report())  # silent: check_ownership reports absence
        pats: dict[str, list[str]] = {}
        if isinstance(registry, dict) and isinstance(registry.get("file_classes"), list):
            for entry in registry["file_classes"][:MAX_REGISTRY_ENTRIES]:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("patterns"), list):
                    pats[entry["id"]] = [p for p in entry["patterns"] if isinstance(p, str)]
        checked = 0
        for name in AGENT_NAMES:
            path = found.get(name)
            if path is None:
                continue
            r = rel(root, path)
            text = read_text(path)
            try:
                data = parse_frontmatter(text)
            except (FMError, OSError) as exc:
                report.bad(r, "0", "PERMISSION_UNPARSEABLE", f"cannot read frontmatter: {exc}")
                continue
            perm = data.get("permission")
            if not isinstance(perm, dict):
                report.bad(r, "permission", "PERMISSION_TYPE", "permission must be a mapping to serialize")
                continue
            expected = serialize_permission(perm)
            section = section_of(text, "Permission statement")
            if section is None:
                report.bad(r, "0", "PERMISSION_STATEMENT_MISSING",
                           "agent has no '## Permission statement' section; add the canonical Edit/Read/Bash/Dispatch serialization")
                continue
            for label in ("Edit", "Read", "Bash", "Dispatch"):
                want = f"{label}: {expected[label]}"
                if norm_ws(want) not in norm_ws(section):
                    report.bad(r, "Permission statement", "PERMISSION_PARITY",
                               f"statement does not contain the frontmatter serialization {want!r}")
            # Ownership parity: every owned writable class must be allowed here.
            edit = perm.get("edit")
            if isinstance(edit, dict):
                entries, err, _ = parse_contract(text)
                claims = [] if err else contract_map(entries).get("owns", [])
                for cid in claims:
                    for pattern in pats.get(cid.strip(), []):
                        if pattern.startswith("halucinator/handoff/") or "/" in pattern:
                            allowed = [p for p, a in edit.items() if a == "allow" and glob_to_re(p).match(pattern)]
                            if not allowed and pattern not in edit:
                                report.bad(r, "permission.edit", "PERMISSION_OWNED_NOT_WRITABLE",
                                           f"{name} owns class {cid.strip()!r} pattern {pattern!r} but no edit rule allows it")
            checked += 1
        report.ok("permissions", f"{checked} agent permission statements match their frontmatter serialization", mark)


# --- config / dispatch / strings --------------------------------------------


def check_config(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "docs/opencode.json", "CONFIG_ABORT"):
        # Shipped as an example under docs/, never live at the toolkit root.
        # A root opencode.json is auto-loaded by OpenCode and would make the
        # HAL-building agents the active set for toolkit maintenance, where
        # hal-architect can write only halucinator/docs/*/notes/ARCHITECTURE.md
        # - a path that does not exist here. See TODO E8.
        path = root / "docs" / "opencode.json"
        if (root / "opencode.json").is_file():
            report.bad("opencode.json", "0", "CONFIG_MISPLACED",
                       "opencode.json must not be live at the toolkit root; it is an example for the "
                       "destination checkout and belongs at docs/opencode.json")
        if not path.is_file():
            report.bad("docs/opencode.json", "0", "CONFIG_MISSING",
                       'docs/opencode.json is absent; create it with {"$schema": "https://opencode.ai/config.json", "default_agent": "hal-coordinator"}')
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            report.bad("docs/opencode.json", "0", "CONFIG_MALFORMED", f"not strict JSON: {_one_line(str(exc), 200)}")
            return
        if not isinstance(data, dict):
            report.bad("docs/opencode.json", "0", "CONFIG_TYPE", "config must be a JSON object")
            return
        if data.get("$schema") != "https://opencode.ai/config.json":
            report.bad("docs/opencode.json", "$schema", "CONFIG_SCHEMA", f"$schema must be 'https://opencode.ai/config.json', got {data.get('$schema')!r}")
        default = data.get("default_agent")
        if default != PRIMARY_AGENT:
            report.bad("docs/opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT", f"default_agent must be {PRIMARY_AGENT!r}, got {default!r}")
            return
        target = root / ".opencode" / "agents" / f"{default}.md"
        if not target.is_file():
            report.bad("docs/opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT_MISSING", f"default_agent {default!r} has no agent definition at .opencode/agents/{default}.md")
            return
        try:
            fm = parse_frontmatter(read_text(target))
        except (FMError, OSError) as exc:
            report.bad("docs/opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT_MISSING", f"default agent definition is unparseable: {exc}")
            return
        if fm.get("mode") != "primary":
            report.bad("docs/opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT_MODE", f"default_agent {default!r} must be mode primary, got {fm.get('mode')!r}")
        report.ok("config", "docs/opencode.json parses and its default agent resolves to a primary agent", mark)


def check_dispatch(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "README.md", "DISPATCH_ABORT"):
        found = agent_paths(root)
        targets = [("README.md", root / "README.md")]
        if PRIMARY_AGENT in found:
            targets.append((rel(root, found[PRIMARY_AGENT]), found[PRIMARY_AGENT]))
        else:
            report.bad(".opencode/agents", "0", "DISPATCH_NO_COORDINATOR", f"{PRIMARY_AGENT} does not exist, so the dispatch policy has no owner")
        want = norm_ws(DISPATCH_BLOCK)
        for r, path in targets:
            if not path.is_file():
                report.bad(r, "0", "DISPATCH_FILE_MISSING", "file required to carry the dispatch policy block is absent")
                continue
            text = norm_ws(read_text(path))
            if want not in text:
                report.bad(r, "0", "DISPATCH_BLOCK_MISSING", "the exact dispatch policy block is absent; copy it verbatim from the M2 specification")
            if r == "README.md":
                for claim in ("entry point is hal-architect", "hal-architect is the entry point", "enters through hal-architect"):
                    if claim in text:
                        report.bad(r, "0", "DISPATCH_WRONG_ENTRY", f"README names the architect as entry point ({claim!r}); the entry point is {PRIMARY_AGENT}")
        for name in SPECIALISTS:
            path = found.get(name)
            if path is None:
                continue
            try:
                fm = parse_frontmatter(read_text(path))
            except (FMError, OSError):
                continue
            perm = fm.get("permission") or {}
            if isinstance(perm, dict) and perm.get("task") != "deny":
                report.bad(rel(root, path), "permission.task", "DISPATCH_SPECIALIST_TASK", f"{name} must declare task: deny; specialists never dispatch peers")
        report.ok("dispatch", f"dispatch policy present in README and {PRIMARY_AGENT}, and {len(SPECIALISTS)} specialists deny task", mark)


def _require_text(root: Path, report: Report, relpath: str, needle: str, code: str, message: str) -> None:
    path = root / relpath
    if not path.is_file():
        report.bad(relpath, "0", code, f"file absent; {message}")
        return
    if norm_ws(needle) not in norm_ws(read_text(path)):
        report.bad(relpath, "0", code, message)


def check_roadmap_path(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "ROADMAP_ABORT"):
        found = agent_paths(root)
        msg = f"the exact ROADMAP path {ROADMAP_PATH!r} is absent; an unnamed 'notes location' is not a path"
        if PRIMARY_AGENT in found:
            _require_text(root, report, rel(root, found[PRIMARY_AGENT]), ROADMAP_PATH, "ROADMAP_PATH_UNSPECIFIED", msg)
        else:
            report.bad(".opencode/agents", "0", "ROADMAP_PATH_UNSPECIFIED", f"{PRIMARY_AGENT} absent; {msg}")
        _require_text(root, report, "README.md", ROADMAP_PATH, "ROADMAP_PATH_UNSPECIFIED", msg)
        for name in ("hal-architect",):
            path = found.get(name)
            if path is None:
                continue
            text = norm_ws(read_text(path))
            if "ROADMAP" in text and ROADMAP_PATH not in text:
                report.bad(rel(root, path), "0", "ROADMAP_PATH_UNSPECIFIED",
                           f"{name} refers to a roadmap without naming {ROADMAP_PATH!r}")
        report.ok("roadmap-path", f"exact ROADMAP path {ROADMAP_PATH} named wherever a roadmap is referenced", mark)


def check_verdict(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "VERDICT_ABORT"):
        found = agent_paths(root)
        for name in (PRIMARY_AGENT, "hal-reviewer"):
            path = found.get(name)
            if path is None:
                report.bad(f".opencode/agents/{name}.md", "0", "VERDICT_SENTENCE_MISSING",
                           f"{name} absent; it must state {VERDICT_SENTENCE!r}")
                continue
            r = rel(root, path)
            text = norm_ws(read_text(path))
            if norm_ws(VERDICT_SENTENCE) not in text:
                report.bad(r, "0", "VERDICT_SENTENCE_MISSING", f"agent does not state the exact accepting sentence {VERDICT_SENTENCE!r}")
            for legacy in LEGACY_VERDICT_TOKENS:
                if legacy in text:
                    report.bad(r, "0", "VERDICT_LEGACY_TOKEN",
                               f"legacy spaced verdict wording {legacy!r} is present; use the typed tokens ready / ready-with-fixes / not-ready")
        report.ok("verdict", "coordinator and reviewer state the exact accepting verdict sentence with typed tokens", mark)


def check_commit_owner(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "COMMIT_ABORT"):
        data = load_registry(root, Report())
        ops = data.get("operations") if isinstance(data, dict) else None
        if not isinstance(ops, dict) or ops.get("commit_owner") != COMMIT_OWNER:
            report.bad(".opencode/ownership.toml", "operations.commit_owner", "COMMIT_OWNER_UNDECLARED",
                       f"the registry does not name {COMMIT_OWNER} as the sole commit_owner")
        found = agent_paths(root)
        for name in AGENT_NAMES:
            path = found.get(name)
            if path is None:
                continue
            r = rel(root, path)
            text = read_text(path)
            try:
                fm = parse_frontmatter(text)
            except (FMError, OSError):
                continue
            perm = fm.get("permission")
            bash = perm.get("bash") if isinstance(perm, dict) else None
            if name == COMMIT_OWNER:
                if norm_ws("sole committer") not in norm_ws(text):
                    report.bad(r, "0", "COMMIT_OWNER_PROSE", f"{name} prose does not state that it is the sole committer")
                continue
            if not isinstance(bash, dict):
                report.bad(r, "permission.bash", "COMMIT_DENY_MISSING",
                           f"{name} bash permission is not an ordered map, so it cannot end with '{COMMIT_DENY_PATTERN}: deny'")
                continue
            items = list(bash.items())
            if not items or items[-1] != (COMMIT_DENY_PATTERN, "deny"):
                report.bad(r, "permission.bash", "COMMIT_DENY_MISSING",
                           f"{name} bash map must end with '{COMMIT_DENY_PATTERN}: deny'; OpenCode applies the last matching rule")
        report.ok("commit-owner", f"{COMMIT_OWNER} is the sole commit owner and every other agent denies '{COMMIT_DENY_PATTERN}'", mark)


def check_precedence(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "PRECEDENCE_ABORT"):
        found = agent_paths(root)
        for name in AGENT_NAMES:
            path = found.get(name)
            if path is None:
                continue
            r = rel(root, path)
            text = read_text(path)
            if norm_ws(PRECEDENCE_SENTENCE) not in norm_ws(text):
                report.bad(r, "0", "PRECEDENCE_SENTENCE_MISSING",
                           "agent does not contain the exact contract-over-skill precedence sentence required by M2")
            section = section_of(text, "Temporary M2 precedence")
            if section is None:
                report.bad(r, "0", "PRECEDENCE_SECTION_MISSING", "agent has no '## Temporary M2 precedence' section listing its conflict IDs")
                continue
            want = CONFLICT_IDS[name]
            ids = sorted(set(re.findall(r"(?<![0-9])([1-9])(?![0-9])", section)), key=int)
            if ",".join(ids) != want:
                report.bad(r, "Temporary M2 precedence", "PRECEDENCE_CONFLICT_IDS",
                           f"{name} lists conflict IDs {','.join(ids) or '(none)'}; M2 assigns it {want}")
        report.ok("precedence", f"{len(AGENT_NAMES)} agents state the precedence sentence and their exact conflict ID set", mark)


def check_candidate_convention(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "CANDIDATE_ABORT"):
        found = agent_paths(root)
        required = [("README.md", root / "README.md"), ("TODO.md", root / "TODO.md"),
                    (".opencode/ownership.toml", root / ".opencode" / "ownership.toml")]
        if "hal-tester" in found:
            required.append((rel(root, found["hal-tester"]), found["hal-tester"]))
        else:
            report.bad(".opencode/agents/hal-tester.md", "0", "CANDIDATE_CONVENTION_MISSING",
                       f"hal-tester absent; it must use {TEST_CANDIDATE_ROOT}")
        for r, path in required:
            if not path.is_file():
                report.bad(r, "0", "CANDIDATE_CONVENTION_MISSING", f"file absent; it must declare the {TEST_CANDIDATE_ROOT} convention")
                continue
            text = read_text(path)
            if TEST_CANDIDATE_ROOT not in text:
                report.bad(r, "0", "CANDIDATE_CONVENTION_MISSING", f"does not use the committed test-candidate convention {TEST_CANDIDATE_ROOT!r}")
            if REJECTED_SCRATCH in text:
                report.bad(r, "0", "CANDIDATE_SCRATCH_REJECTED", f"uses the rejected hidden scratch convention {REJECTED_SCRATCH!r}; it is gitignored and clone-local")
        report.ok("candidate-convention", f"{TEST_CANDIDATE_ROOT} used consistently and the hidden scratch convention is absent", mark)


def check_workflow_markers(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "MARKER_ABORT"):
        found = agent_paths(root)
        for name, markers in (("hal-integrator", INTEGRATOR_MARKERS), ("hal-tester", TESTER_MARKERS)):
            path = found.get(name)
            if path is None:
                report.bad(f".opencode/agents/{name}.md", "0", "MARKER_MISSING",
                           f"{name} absent; it must carry the headings {', '.join(markers)}")
                continue
            r = rel(root, path)
            text = read_text(path)
            for marker in markers:
                if section_of(text, marker) is None:
                    report.bad(r, "0", "MARKER_MISSING", f"required workflow heading {marker!r} is absent")
        tester = found.get("hal-tester")
        if tester is not None:
            text = read_text(tester)
            absent = [k for k in SANITIZED_KEYS if k not in text]
            if absent:
                report.bad(rel(root, tester), "0", "MARKER_DIAGNOSTIC_KEYS",
                           f"sanitized diagnostic key(s) {', '.join(absent)} are not named; the tester must state the exact returned keys")
        report.ok("workflow-markers", "integrator and tester carry their required workflow headings and diagnostic keys", mark)


def check_skill_references(root: Path, report: Report) -> None:
    """Agent prose must not name a skill that does not exist.

    Subject derivation: the resolvable name set is
    `set(skill_paths(root)) | set(SKILL_SPEC)` - what discovery actually finds,
    unioned with the canonical mapping so that a *deleted* canonical skill is
    still recognised as a skill reference and reported UNRESOLVED rather than
    silently reclassified as ordinary prose. No verb prefix, no literal name.
    """
    mark = report.mark()
    with guard(report, ".opencode/agents", "SKILLREF_ABORT"):
        existing = set(skill_paths(root))
        resolvable = known_skill_names(root)
        if not resolvable:
            report.bad(".opencode/skills", "0", "SKILL_REFERENCE_NO_NAMES",
                       "no skill names could be derived from discovery or the canonical mapping; "
                       "every backticked token would be unclassifiable and the scanner would assert nothing")
            return
        found = agent_paths(root)
        refs = 0
        for name in sorted(found):
            path = found[name]
            r = rel(root, path)
            text = read_text(path)
            for sentence in norm_ws(text.replace("`", "\u0000")).split(". "):
                for m in SKILL_TOKEN_RE.finditer(sentence):
                    token = m.group(1)
                    # A token is a skill reference only when it names a skill we
                    # know about. `ready-with-fixes`, `06-driver` and an invented
                    # `integrate-nothing` are prose, not unresolved skills.
                    if token not in resolvable:
                        continue
                    refs += 1
                    if token in existing:
                        continue
                    if re.search(r"awaits M[0-9]+ TODO ", sentence):
                        continue
                    report.bad(r, "0", "SKILL_REFERENCE_UNRESOLVED",
                               f"references skill {token!r}, which does not exist under .opencode/skills/; a future skill may appear only as unlinked prose marked 'awaits M<n> TODO <ID>'")
        report.ok("skill-references", f"{refs} skill references in agent prose resolve to existing skills, matched against {len(resolvable)} discovered/canonical names", mark)


# ---------------------------------------------------------------------------
# Typed procedural skills
#
# Thirteen checks validating every discovered skill against the canonical
# template. Like the M2 checks above they parse *raw* Markdown, because the
# machine-readable skill contract lives inside a fence that strip_code() erases.
#
# M4 retired the two-generation exemption file and its parser together. There
# is no exclusion set and no registry indirection: each check is invoked
# directly from main() and scans every discovered skill. A check that covered
# nothing because its input file had vanished was the failure mode that
# retirement removes.
# ---------------------------------------------------------------------------

SKILL_CONTRACT_INFO = "halucinator-skill-contract"
SKILL_CONTRACT_KEYS = ("stage", "participants", "emitter", "emits", "checks", "consumes", "writes", "supplies-delta")
# `supplies-delta` is optional: "Empty supplies-delta is represented by no line."
SKILL_CONTRACT_REQUIRED = ("stage", "participants", "emitter", "emits", "checks", "consumes", "writes")
SKILL_CONTRACT_SINGLE = ("stage", "participants", "emitter", "emits", "checks")
SKILL_CONTRACT_REPEATABLE = ("consumes", "writes", "supplies-delta")

SKILL_TEMPLATE_H2 = (
    "When to use",
    "Ownership and boundaries",
    "Inputs",
    "Outputs",
    "Procedure",
    "Validation",
    "Exit criteria",
    "Application example",
    "Quick reference",
    "Common mistakes",
)

# Closed template verb list (specification section 2, "Assertable procedural form").
PROCEDURE_VERBS = (
    "Inspect", "Validate", "Load", "Classify", "Select", "Record", "Preserve",
    "Compare", "Author", "Generate", "Build", "Run", "Publish", "Request",
    "Re-attest", "Return",
)

EXIT_STATUSES = ("ready", "partial", "blocked")
VALIDATION_COLUMNS = ("Check ID", "Discharging action", "Evidence artifact")

# Nine legacy null sentinels, rejected ONLY as TOML scalar field values inside
# fenced TOML example blocks. Ordinary prose such as "unknown fact" is legal.
NULL_SENTINELS = (
    "unknown", "not provided", "none", "not checked", "none recorded",
    "not selected", "none yet", "unverified", "in progress",
)

# Soft-alternative wording that must not share a paragraph with a deterministic
# note path: a default is not a determinism.
SOFT_NOTE_TOKENS = ("default to", "or default", "when unused", "if unused", "optional")

# Deterministic first-note path, keyed by EMITTED HANDOFF KIND rather than by
# skill name. Subjects for the note-path check are selected by parsing each
# discovered skill's `emits:` kind, so a new skill that emits 03-svd or 04-pac
# is covered the moment it declares that kind. Keying by skill name made the
# mapping's own key set the subject filter - the M4 defect shape.
NOTE_PATH_BY_KIND = {
    "03-svd": "<documentation>/notes/SVD.md",
    "04-pac": "<documentation>/notes/PAC.md",
}

# Skills whose exit gate is an accepting independent review. This set is NOT
# hard-coded: a skill is review-gated exactly when its own contract fence
# declares the 'independent-review' check, so a new review-gated skill is
# covered the moment it declares the check. See review_gated_skills().
REVIEW_GATED_CHECK = "independent-review"

# Per-skill canonical contract expectations. Leaf/check sets are NOT stored
# here: they are derived from validate.py's AST by derive_registry().
#
# M6 defect fix. The consumed predecessor sets used to be literal comma-joined
# leaf strings (CONSUMED_01..CONSUMED_06). That made check_skill_consumption
# UNSATISFIABLE the moment schema 2 retired a leaf: SKILL_CONSUMPTION_SET
# compared the declaration against the stale literal while
# SKILL_CONSUMPTION_UNKNOWN_PATH compared the same declaration against the
# AST-derived registry, so `want` was not a subset of `valid` and no skill text
# could satisfy both. The two assertions could disagree with nobody noticing;
# that, not the stale names, was the bug.
#
# The fix is to express each consumed set the way CONSUME_ALL already did -
# as a predicate over the derived registry - so `want` is a subset of `valid`
# BY CONSTRUCTION and cannot drift again. A consumer that reads a deliberate
# SUBSET of a kind now states only what it deliberately does NOT read, which
# is the small editorial part; the rest follows the validator. A newly added
# leaf is consumed automatically, and a retired leaf disappears from `want`
# without any edit here.
#
# The exclusions themselves are still literal, so they are checked: every
# excluded path must be a live member of the derived kind, or the mapping
# fails loudly with SKILL_CONSUMPTION_SPEC_STALE at the constant rather than
# silently making the check unsatisfiable at the skill.


class ConsumeAllExcept:
    """The whole AST-derived leaf set of a kind, minus named exclusions."""

    __slots__ = ("exclude",)

    def __init__(self, *exclude: str) -> None:
        self.exclude: tuple[str, ...] = tuple(sorted(exclude))

    def __repr__(self) -> str:  # pragma: no cover - diagnostics only
        return f"ConsumeAllExcept{self.exclude}"


# Sentinel for "the complete AST-derived leaf set of that kind". M5's snapshot
# and review consumers re-read an entire predecessor rather than a curated
# subset, so writing the subset out by hand would be a second hand-maintained
# copy of the registry. Resolved against derive_registry() at check time.
CONSUME_ALL = "*"

# The typed envelope a downstream skill does not re-read: `handoff.schema` and
# `handoff.stage` identify the record it already selected by kind, and
# `handoff.can_progress` is the producer's own gate, not an input.
ENVELOPE_EXCLUDED = ("handoff.can_progress", "handoff.schema", "handoff.stage")

# Most consumers take the predecessor's payload and status but not its check
# ledger; they re-derive their own. `generate-pac` is the documented exception
# - it must read the SVD preparation's recorded check results - so 03-svd
# below deliberately omits this group from its exclusions.
CHECKS_EXCLUDED = ("checks.evidence", "checks.id", "checks.reason", "checks.status")

CONSUMED_01 = ConsumeAllExcept(*ENVELOPE_EXCLUDED, *CHECKS_EXCLUDED)
CONSUMED_02 = ConsumeAllExcept(*ENVELOPE_EXCLUDED, *CHECKS_EXCLUDED)
CONSUMED_03 = ConsumeAllExcept(*ENVELOPE_EXCLUDED)
CONSUMED_04 = ConsumeAllExcept(*ENVELOPE_EXCLUDED, *CHECKS_EXCLUDED)
CONSUMED_05 = ConsumeAllExcept(*ENVELOPE_EXCLUDED, *CHECKS_EXCLUDED)
# `driver.owned_files` is integrator bookkeeping about the driver's canonical
# placement. A tester that read it would be reading a file list for a crate it
# is not permitted to open.
CONSUMED_06 = ConsumeAllExcept(*ENVELOPE_EXCLUDED, *CHECKS_EXCLUDED, "driver.owned_files")


def resolve_consumed(valid: set[str], raw) -> tuple[set[str], list[str]]:
    """Resolve one canonical consumes entry against a kind's derived leaf set.

    Returns (want, stale). `stale` is nonempty exactly when the mapping names a
    path the validator no longer defines - the condition that used to make the
    check unsatisfiable. Pure, so the self-test below can drive it.
    """
    if raw == CONSUME_ALL:
        return set(valid), []
    if isinstance(raw, ConsumeAllExcept):
        stale = sorted(set(raw.exclude) - valid)
        return (set(valid) - set(raw.exclude)), stale
    named = set(raw)
    return named, sorted(named - valid)


def consumed_resolution_failures() -> list[str]:
    """Self-test resolve_consumed. A resolver that never reports staleness is
    exactly the failure mode being fixed, so prove it discriminates."""
    valid = {"a.one", "a.two", "b.keep", "checks.id"}
    problems: list[str] = []
    want, stale = resolve_consumed(valid, CONSUME_ALL)
    if want != valid or stale:
        problems.append(f"CONSUME_ALL resolved to {sorted(want)} / stale {stale}")
    want, stale = resolve_consumed(valid, ConsumeAllExcept("checks.id"))
    if want != {"a.one", "a.two", "b.keep"} or stale:
        problems.append(f"ConsumeAllExcept resolved to {sorted(want)} / stale {stale}")
    _, stale = resolve_consumed(valid, ConsumeAllExcept("a.retired"))
    if stale != ["a.retired"]:
        problems.append(f"a retired EXCLUSION was not reported stale (got {stale}); the mapping could name a "
                        "path the validator dropped and nobody would be told")
    _, stale = resolve_consumed(valid, {"a.one", "a.retired"})
    if stale != ["a.retired"]:
        problems.append(f"a retired ENUMERATED leaf was not reported stale (got {stale}); that is precisely the "
                        "condition that made want a non-subset of valid and the check unsatisfiable")
    want, _ = resolve_consumed(valid, ConsumeAllExcept())
    if want != valid:
        problems.append("ConsumeAllExcept() with no exclusions did not resolve to the whole kind")
    return problems



def _leaves(raw: str) -> set[str]:
    return {p for p in raw.split(",") if p}


SKILL_SPEC: dict[str, dict] = {
    "gather-documentation": {
        "stage": "gather-documentation",
        "emitter": "hal-datasheet",
        "kind": "01-sources",
        "filename": "halucinator/handoff/01-sources.toml",
        "consumes": {},
        "writes": {"hal-datasheet|vendor-source-bytes", "hal-datasheet|sources-handoff"},
        "supplies-delta": {"hal-datasheet|sources-catalog"},
    },
    "generate-svd": {
        "stage": "generate-svd",
        "emitter": "hal-svd",
        "kind": "03-svd",
        "filename": "halucinator/handoff/03-svd.toml",
        "consumes": {"01-sources": CONSUMED_01, "02-facts": CONSUMED_02},
        "writes": {"hal-svd|pac-project", "hal-svd|svd-handoff", "hal-svd|svd-pac-notes"},
        "supplies-delta": {"hal-svd|sources-catalog"},
    },
    "generate-pac": {
        "stage": "generate-pac",
        "emitter": "hal-svd",
        "kind": "04-pac",
        "filename": "halucinator/handoff/04-pac.toml",
        "consumes": {"03-svd": CONSUMED_03},
        "writes": {"hal-svd|pac-handoff", "hal-svd|pac-project", "hal-svd|svd-pac-notes"},
        "supplies-delta": {"hal-svd|sources-catalog"},
    },
    "scaffold-hal": {
        "stage": "scaffold-hal",
        "emitter": "hal-integrator",
        "kind": "05-platform",
        "filename": "halucinator/handoff/05-platform.toml",
        # The consolidator starts the chain's evidence from the PAC and, as the
        # FINAL platform slice, also consumes the 05-platform snapshot the
        # preceding slices published. Without that second edge a `ready`
        # platform needs no typed evidence that the slices ran at all. Same
        # whole-predecessor sentinel the other slices declare, so the two sides
        # cannot drift into disagreeing literal copies.
        "consumes": {"04-pac": CONSUMED_04, "05-platform": CONSUME_ALL},
        "writes": {
            "hal-architect|architecture-spec", "hal-coordinator|roadmap", "hal-driver|clock-modules",
            "hal-integrator|build-generation", "hal-integrator|chip-modules", "hal-integrator|ci",
            "hal-integrator|crate-manifest", "hal-integrator|example-binaries", "hal-integrator|example-manifest",
            "hal-integrator|example-support", "hal-integrator|integration-candidates", "hal-integrator|linker",
            "hal-integrator|platform-handoff", "hal-integrator|platform-lib", "hal-integrator|platform-notes",
            "hal-integrator|runtime-wiring",
        },
        "supplies-delta": {
            "hal-architect|platform-notes", "hal-driver|platform-notes", "hal-tester|example-binaries",
            "hal-tester|example-manifest", "hal-tester|example-support",
        },
    },
    "write-driver": {
        "stage": "write-driver",
        "emitter": "hal-driver",
        "kind": "06-driver",
        # 06 is per-peripheral; <name> equals driver.name.
        "filename": "halucinator/handoff/06-driver-<name>.toml",
        "consumes": {"05-platform": CONSUMED_05},
        "writes": {
            "hal-driver|clock-modules", "hal-driver|driver-candidates",
            "hal-driver|driver-evidence", "hal-driver|driver-handoff",
            "hal-driver|peripheral-modules",
        },
        "supplies-delta": {
            "hal-driver|driver-records", "hal-driver|platform-notes",
            "hal-driver|roadmap", "hal-driver|sources-catalog",
        },
    },
    "write-examples": {
        "stage": "write-tests",
        "emitter": "hal-tester",
        "kind": "07-tests",
        # 07 is the one per-item deterministic filename; <name> equals tests.name.
        "filename": "halucinator/handoff/07-tests-<name>.toml",
        "consumes": {"06-driver": CONSUMED_06},
        "writes": {
            "hal-tester|test-candidate-evidence", "hal-tester|test-candidate-manifests",
            "hal-tester|test-candidate-source", "hal-tester|tests-handoff",
        },
        "supplies-delta": {
            "hal-tester|ci", "hal-tester|example-binaries", "hal-tester|example-manifest",
            "hal-tester|example-support", "hal-tester|hil-tests", "hal-tester|runtime-wiring",
            "hal-tester|test-records",
        },
    },
    # --- M5 -----------------------------------------------------------------
    "extract-hardware-facts": {
        "stage": "extract-facts",
        "emitter": "hal-datasheet",
        "kind": "02-facts",
        "filename": "halucinator/handoff/02-facts.toml",
        "consumes": {"01-sources": CONSUMED_01},
        "writes": {
            "hal-datasheet|fact-notes", "hal-datasheet|facts-handoff",
            "hal-datasheet|vendor-extractions",
        },
        "supplies-delta": {"hal-datasheet|sources-catalog"},
    },
    "write-clocks": {
        "stage": "scaffold-hal",
        "emitter": "hal-integrator",
        "kind": "05-platform",
        "filename": "halucinator/handoff/05-platform.toml",
        "consumes": {"04-pac": CONSUMED_04},
        "writes": {
            "hal-driver|clock-modules", "hal-driver|driver-evidence",
            "hal-integrator|integration-candidates", "hal-integrator|platform-handoff",
        },
        "supplies-delta": {"hal-driver|platform-notes"},
    },
    "integrate-interrupts": {
        "stage": "scaffold-hal",
        "emitter": "hal-integrator",
        "kind": "05-platform",
        "filename": "halucinator/handoff/05-platform.toml",
        # A non-first platform slice consumes an immutable byte-identical
        # snapshot of the validated live 05-platform, so it re-reads the whole
        # predecessor rather than a curated subset.
        "consumes": {"05-platform": CONSUME_ALL},
        "writes": {
            "hal-integrator|build-generation", "hal-integrator|chip-modules",
            "hal-integrator|integration-candidates", "hal-integrator|platform-handoff",
            "hal-integrator|platform-lib",
        },
        "supplies-delta": set(),
    },
    "integrate-runtime-linker": {
        "stage": "scaffold-hal",
        "emitter": "hal-integrator",
        "kind": "05-platform",
        "filename": "halucinator/handoff/05-platform.toml",
        "consumes": {"05-platform": CONSUME_ALL},
        "writes": {
            "hal-integrator|crate-manifest", "hal-integrator|example-support",
            "hal-integrator|integration-candidates", "hal-integrator|linker",
            "hal-integrator|platform-handoff", "hal-integrator|platform-lib",
            "hal-integrator|runtime-wiring",
        },
        "supplies-delta": set(),
    },
    "write-dma": {
        "stage": "write-driver",
        "emitter": "hal-driver",
        "kind": "06-driver",
        "filename": "halucinator/handoff/06-driver-dma.toml",
        "consumes": {"05-platform": CONSUMED_05},
        "writes": {
            "hal-driver|driver-candidates", "hal-driver|driver-evidence",
            "hal-driver|driver-handoff", "hal-driver|peripheral-modules",
        },
        "supplies-delta": {
            "hal-driver|driver-records", "hal-driver|platform-notes",
            "hal-driver|roadmap", "hal-driver|sources-catalog",
        },
    },
    "review-artifact": {
        "stage": "review",
        "emitter": "hal-reviewer",
        "kind": "08-review",
        "filename": "halucinator/handoff/08-review-<artifact>.toml",
        # One invocation selects exactly one predecessor kind, but the skill
        # must declare every kind it may be dispatched against.
        "consumes": {
            "01-sources": CONSUME_ALL, "02-facts": CONSUME_ALL, "03-svd": CONSUME_ALL,
            "04-pac": CONSUME_ALL, "05-platform": CONSUME_ALL, "06-driver": CONSUME_ALL,
            "07-tests": CONSUME_ALL,
        },
        "writes": {"hal-reviewer|review-handoff"},
        "supplies-delta": {"hal-reviewer|review-notes"},
    },
    "debug-hardware": {
        "stage": "write-tests",
        "emitter": "hal-tester",
        "kind": "07-tests",
        # Distinct from the consumed 07 name: the debug run never replaces the
        # failure it is investigating.
        "filename": "halucinator/handoff/07-tests-<source-name>-debug-<run-id>.toml",
        "consumes": {"06-driver": CONSUMED_06, "07-tests": CONSUME_ALL},
        "writes": {
            "hal-tester|test-candidate-evidence", "hal-tester|test-candidate-manifests",
            "hal-tester|test-candidate-source", "hal-tester|tests-handoff",
        },
        "supplies-delta": {"hal-tester|test-records"},
    },
}

# Stale attribution that A16 removes, and the wording that must replace it.
STALE_ATTRIBUTION = {
    ".opencode/schema/state.md": (
        "architect-selected immutable decision",
        "architect-owned PAC/scaffold decisions",
        "architect-selected next driver",
        "architect-owned PAC consumer requirements",
        "the architect derives them",
        "Architect owns this decision",
    ),
    ".opencode/schema/04-pac.md": (
        "architect-owned foundation requirement",
        "core/architect decisions",
    ),
    ".opencode/schema/traceability.md": (
        "Architect alone writes",
        "Tester writes only 07 and public records",
    ),
}
REQUIRED_ATTRIBUTION = {
    ".opencode/schema/state.md": (
        "coordinator-selected immutable decision",
        "coordinator-owned PAC/scaffold decisions",
        "coordinator-selected next driver",
        "hal-coordinator owns this decision",
    ),
    ".opencode/schema/04-pac.md": ("coordinator-owned foundation requirement",),
}

TEST_CANDIDATE_ATTRIBUTES = (
    "halucinator/test-candidates/*/src/** text eol=lf",
    "halucinator/test-candidates/*/*.toml text eol=lf",
    "halucinator/test-candidates/*/INVENTORY.md text eol=lf",
    "halucinator/test-candidates/*/evidence/** -text",
)
TEST_CANDIDATE_CLASSES = ("test-candidate-source", "test-candidate-manifests", "test-candidate-evidence")
README_DEFERRED_CLAIM = "Ratifying this layout in the schema is deferred"

# --- skill discovery --------------------------------------------------------


def skill_paths(root: Path) -> dict[str, Path]:
    d = root / ".opencode" / "skills"
    if not d.is_dir():
        return {}
    return {p.parent.name: p for p in sorted(d.glob("*/SKILL.md"))}


def in_scope_skills(root: Path) -> dict[str, Path]:
    """Every discovered skill. M4 removed the exemption mechanism entirely."""
    return dict(skill_paths(root))


def skill_reference_paths(root: Path, skill: Path) -> list[Path]:
    refs = skill.parent / "references"
    if not refs.is_dir():
        return []
    return sorted(p for p in refs.glob("*.md") if p.is_file())


# --- derived subject selectors ----------------------------------------------
#
# Every M5 subject set begins at skill_paths()/in_scope_skills() and is
# narrowed by a PARSED contract field. None of these functions may mention a
# skill name; check_skill_subject_derivation enforces that against this file's
# own AST.


def skill_contracts(root: Path) -> dict[str, dict[str, list[str]]]:
    """Discovered skill -> parsed contract map, for every parseable fence.

    An unparseable fence is omitted here but is independently reported by
    check_skill_contracts, so it can never quietly narrow a derived subject
    set without failing the suite.
    """
    out: dict[str, dict[str, list[str]]] = {}
    for name, path in sorted(skill_paths(root).items()):
        entries, err, _ = parse_contract(read_text(path), SKILL_CONTRACT_INFO)
        if err:
            continue
        out[name] = contract_map(entries)
    return out


def _single(cmap: dict[str, list[str]], key: str) -> str | None:
    values = cmap.get(key, [])
    return values[0] if len(values) == 1 else None


def emitted_kind(cmap: dict[str, list[str]]) -> str | None:
    value = _single(cmap, "emits")
    if value is None or "|" not in value:
        return None
    return value.split("|")[0]


def emitted_filename(cmap: dict[str, list[str]]) -> str | None:
    value = _single(cmap, "emits")
    if value is None or value.count("|") != 2:
        return None
    return value.split("|")[1]


def consumed_kinds(cmap: dict[str, list[str]]) -> set[str]:
    out: set[str] = set()
    for value in cmap.get("consumes", []):
        if value.count("|") == 1:
            out.add(value.split("|")[0])
    return out


def skills_emitting_kind(contracts: dict[str, dict[str, list[str]]], kind: str) -> list[str]:
    return sorted(n for n, c in contracts.items() if emitted_kind(c) == kind)


def skills_with_emitter(contracts: dict[str, dict[str, list[str]]], agent: str) -> list[str]:
    return sorted(n for n, c in contracts.items() if _single(c, "emitter") == agent)


def skills_at_stage(contracts: dict[str, dict[str, list[str]]], stage: str) -> list[str]:
    return sorted(n for n, c in contracts.items() if _single(c, "stage") == stage)


# A non-final platform slice declares its ready exit as unreachable; the final
# consolidator does not. This is the parsed procedural role that separates the
# two, and it is why the slice set is never a literal list.
SLICE_UNREACHABLE_TOKEN = "unreachable"


def exit_predicate(text: str, label: str) -> str | None:
    """Raw body of one '### <label>' block inside '## Exit criteria'."""
    for heading, body, _ in h2_sections(text):
        if heading != "Exit criteria":
            continue
        for h, b in h3_blocks(body):
            if h == label:
                return b
    return None


def h2_body(text: str, heading: str) -> str | None:
    for h, body, _ in h2_sections(text):
        if h == heading:
            return body
    return None


# --- raw markdown section helpers -------------------------------------------


def h2_sections(text: str) -> list[tuple[str, str, int]]:
    """Ordered (heading, body, lineno) for every top-level '## ' heading.

    Fence-aware: a '## ' inside a fenced block is content, not a heading.
    """
    out: list[tuple[str, str, int]] = []
    fence: str | None = None
    cur: list[str] | None = None
    heading = ""
    lineno = 0
    for i, line in enumerate(text.split("\n"), start=1):
        stripped = line.strip()
        m = re.match(r"(`{3,}|~{3,})", stripped)
        if m:
            tok = m.group(1)[0] * 3
            if fence is None:
                fence = tok
            elif fence == tok:
                fence = None
        if fence is None and line.startswith("## "):
            if cur is not None:
                out.append((heading, "\n".join(cur), lineno))
            heading = line[3:].strip()
            lineno = i
            cur = []
            continue
        if cur is not None:
            cur.append(line)
    if cur is not None:
        out.append((heading, "\n".join(cur), lineno))
    return out


def h3_blocks(body: str) -> list[tuple[str, str]]:
    """Ordered (heading, body) for every '### ' heading inside a section body."""
    out: list[tuple[str, str]] = []
    fence: str | None = None
    cur: list[str] | None = None
    heading = ""
    for line in body.split("\n"):
        stripped = line.strip()
        m = re.match(r"(`{3,}|~{3,})", stripped)
        if m:
            tok = m.group(1)[0] * 3
            if fence is None:
                fence = tok
            elif fence == tok:
                fence = None
        if fence is None and line.startswith("### "):
            if cur is not None:
                out.append((heading, "\n".join(cur)))
            heading = line[4:].strip()
            cur = []
            continue
        if cur is not None:
            cur.append(line)
    if cur is not None:
        out.append((heading, "\n".join(cur)))
    return out


def fenced_blocks(text: str, info: str) -> list[str]:
    """Bodies of every fenced block whose info string equals `info`."""
    out: list[str] = []
    lines = text.split("\n")
    i = 0
    while i < len(lines):
        stripped = lines[i].strip()
        if stripped.startswith("```") and stripped[3:].strip() == info:
            body: list[str] = []
            j = i + 1
            while j < len(lines) and not lines[j].strip().startswith("```"):
                body.append(lines[j])
                j += 1
            out.append("\n".join(body))
            i = j + 1
            continue
        i += 1
    return out


def paragraphs(text: str) -> list[str]:
    out: list[str] = []
    cur: list[str] = []
    for line in text.split("\n"):
        if line.strip():
            cur.append(line)
        elif cur:
            out.append("\n".join(cur))
            cur = []
    if cur:
        out.append("\n".join(cur))
    return out


def first_verb(item: str) -> str:
    """First word of a procedure item, ignoring a leading bold label marker."""
    s = item.strip().lstrip("*").strip()
    m = re.match(r"([A-Za-z][A-Za-z-]*)", s)
    return m.group(1) if m else ""


# --- structure analyzer (pure, so malformed fixtures can drive it) ----------


def analyze_structure(text: str, checks: list[str]) -> list[tuple[str, str]]:
    """Return [(code, message)] for every template-form defect in a skill body.

    Pure function of (raw markdown, canonical check IDs). Driven both by real
    skill files and by the in-memory malformed near-miss fixtures below, which
    is what proves it discriminates rather than rejecting everything.
    """
    out: list[tuple[str, str]] = []
    sections = h2_sections(text)
    headings = [h for h, _, _ in sections]
    if headings != list(SKILL_TEMPLATE_H2):
        out.append((
            "SKILL_STRUCTURE_H2",
            f"H2 headings are {headings or '(none)'}; the template requires exactly {list(SKILL_TEMPLATE_H2)} once each, in order, with no interleaved H2",
        ))
    bodies = {h: b for h, b, _ in sections}
    for name in SKILL_TEMPLATE_H2:
        if name in bodies and not bodies[name].strip():
            out.append(("SKILL_STRUCTURE_EMPTY_SECTION", f"section '## {name}' is empty; every template section must carry content"))

    # --- Procedure: contiguous imperative numbered steps -------------------
    proc = bodies.get("Procedure")
    if proc is None:
        out.append(("SKILL_STRUCTURE_NO_PROCEDURE", "no '## Procedure' section; the template requires an ordered numbered procedure"))
    else:
        items: list[tuple[int, str]] = []
        fence: str | None = None
        for line in proc.split("\n"):
            stripped = line.strip()
            m = re.match(r"(`{3,}|~{3,})", stripped)
            if m:
                tok = m.group(1)[0] * 3
                if fence is None:
                    fence = tok
                elif fence == tok:
                    fence = None
                continue
            if fence is not None:
                continue
            m = re.match(r"^(\d+)\.\s+(\S.*)$", line)  # top level only: no indent
            if m:
                items.append((int(m.group(1)), m.group(2)))
        if not items:
            out.append(("SKILL_STRUCTURE_PROCEDURE_FORM", "'## Procedure' contains no top-level numbered steps; H3 prose or bullets are not an assertable procedure"))
        else:
            numbers = [n for n, _ in items]
            if numbers != list(range(1, len(numbers) + 1)):
                out.append(("SKILL_STRUCTURE_PROCEDURE_NUMBERING", f"top-level procedure markers are {numbers}; they must be contiguous 1..{len(numbers)} with no gap or restart"))
            for n, body in items:
                verb = first_verb(body)
                if verb not in PROCEDURE_VERBS:
                    out.append(("SKILL_STRUCTURE_PROCEDURE_VERB", f"procedure step {n} begins with {verb or '(nothing)'!r}, not a template verb; use one of {', '.join(PROCEDURE_VERBS)}"))
            head = items[0][1]
            if first_verb(head) != "Inspect" or "entry state" not in head.lower():
                out.append(("SKILL_STRUCTURE_PROCEDURE_RECOVERY", "procedure step 1 is not the universal entry-recovery step ('Inspect and classify entry state')"))
            if len(items) < len(checks):
                out.append(("SKILL_STRUCTURE_PROCEDURE_COUNT", f"procedure has {len(items)} top-level steps but the contract declares {len(checks)} canonical checks; there must be at least as many steps as checks"))
            unnamed = [c for c in checks if c not in proc]
            if unnamed:
                out.append(("SKILL_STRUCTURE_PROCEDURE_CHECK_UNNAMED", f"procedure never names canonical check(s) {', '.join(unnamed[:8])}; every declared check must be discharged by a named step"))

    # --- Validation: exactly one row per canonical check --------------------
    val = bodies.get("Validation")
    if val is None:
        out.append(("SKILL_STRUCTURE_NO_VALIDATION", "no '## Validation' section; the template requires the check/action/evidence table"))
    else:
        rows = [ln for ln in val.split("\n") if ln.strip().startswith("|")]
        body_rows = [r for r in rows if not re.match(r"^\s*\|[\s:|-]+\|\s*$", r)]
        if len(body_rows) < 2:
            out.append(("SKILL_STRUCTURE_VALIDATION_TABLE", "'## Validation' has no table with a header and at least one row; a bullet list or 'see procedure' is not a validation table"))
        else:
            def cells(r: str) -> list[str]:
                parts = [c.strip() for c in r.strip().strip("|").split("|")]
                return parts
            header = [c.replace("`", "") for c in cells(body_rows[0])]
            if header != list(VALIDATION_COLUMNS):
                out.append(("SKILL_STRUCTURE_VALIDATION_COLUMNS", f"validation table header is {header}; it must be exactly {list(VALIDATION_COLUMNS)}"))
            seen: list[str] = []
            for r in body_rows[1:]:
                c = cells(r)
                if len(c) != 3:
                    out.append(("SKILL_STRUCTURE_VALIDATION_ROW", f"validation row {r.strip()!r} does not have exactly three cells"))
                    continue
                cid, action, evidence = c[0].replace("`", "").strip(), c[1].strip(), c[2].strip()
                seen.append(cid)
                if not action:
                    out.append(("SKILL_STRUCTURE_VALIDATION_ACTION", f"validation row {cid!r} has an empty discharging action"))
                elif first_verb(action) not in PROCEDURE_VERBS:
                    out.append(("SKILL_STRUCTURE_VALIDATION_ACTION", f"validation action for {cid!r} begins with {first_verb(action)!r}, not an imperative template verb"))
                if not evidence:
                    out.append(("SKILL_STRUCTURE_VALIDATION_EVIDENCE", f"validation row {cid!r} has an empty evidence cell; name a concrete artifact or 'reason (no evidence FileRef)'"))
            dupes = sorted({c for c in seen if seen.count(c) > 1})
            if dupes:
                out.append(("SKILL_STRUCTURE_VALIDATION_DUPLICATE", f"validation table repeats check ID(s) {', '.join(dupes)}"))
            extra = sorted(set(seen) - set(checks))
            missing = sorted(set(checks) - set(seen))
            if extra:
                out.append(("SKILL_STRUCTURE_VALIDATION_EXTRA", f"validation table names check(s) {', '.join(extra)} that the contract does not declare"))
            if missing:
                out.append(("SKILL_STRUCTURE_VALIDATION_MISSING", f"validation table has no row for declared check(s) {', '.join(missing)}"))

    # --- Exit criteria: exactly three predicate blocks ----------------------
    exit_body = bodies.get("Exit criteria")
    if exit_body is None:
        out.append(("SKILL_STRUCTURE_NO_EXIT", "no '## Exit criteria' section; the template requires ready/partial/blocked predicates"))
    else:
        blocks = h3_blocks(exit_body)
        labels = [h for h, _ in blocks]
        if labels != list(EXIT_STATUSES):
            out.append(("SKILL_STRUCTURE_EXIT_LABELS", f"exit criteria H3 labels are {labels or '(none)'}; they must be exactly {list(EXIT_STATUSES)} in order"))
        texts = {h: b for h, b in blocks}
        for label in EXIT_STATUSES:
            b = texts.get(label)
            if b is None:
                continue
            if "Predicate:" not in b:
                out.append(("SKILL_STRUCTURE_EXIT_PREDICATE", f"exit block '{label}' has no 'Predicate:' paragraph stating decidable field/check conditions"))
                continue
            low = norm_ws(b).lower()
            has_true = "can_progress=true" in low
            has_false = "can_progress=false" in low
            if label == "ready":
                if has_true or has_false:
                    out.append(("SKILL_STRUCTURE_EXIT_OVERLAP", "the 'ready' predicate constrains can_progress; ready requires can_progress to be ABSENT, so naming true or false overlaps partial/blocked"))
                for need in ("incomplete", "blockers", "passed"):
                    if need not in low:
                        out.append(("SKILL_STRUCTURE_EXIT_PREDICATE", f"the 'ready' predicate does not mention {need!r}; restate the handoff-common.md rules"))
            elif label == "partial":
                if not has_true or has_false:
                    out.append(("SKILL_STRUCTURE_EXIT_OVERLAP", "the 'partial' predicate must state can_progress=true and must not state can_progress=false"))
            elif label == "blocked":
                if not has_false or has_true:
                    out.append(("SKILL_STRUCTURE_EXIT_OVERLAP", "the 'blocked' predicate must state can_progress=false and must not state can_progress=true"))
    return out


# --- in-memory malformed near-miss fixtures ---------------------------------

_FIXTURE_CHECKS = ["alpha-check", "beta-check"]

_FIXTURE_GOOD = """# Fixture Skill

## When to use
Use when the fixture runs.

## Ownership and boundaries
Owner prose.

## Inputs
Input prose.

## Outputs
Output prose.

## Procedure
1. **Inspect and classify entry state.** Inspect locks and classify them.
2. **Validate before consumption.** Validate the predecessor for alpha-check.
3. **Publish in one order.** Publish evidence discharging beta-check.

## Validation
| Check ID | Discharging action | Evidence artifact |
|---|---|---|
| `alpha-check` | Run the alpha tool | `evidence/alpha.log` |
| `beta-check` | Build the beta crate | `evidence/beta.log` |

## Exit criteria
### ready
Predicate: empty incomplete, complete equals included scope, can_progress absent, empty blockers, all applicable checks passed.

### partial
Predicate: can_progress=true, empty blockers, and incomplete or applicable unrun checks remain.

### blocked
Predicate: can_progress=false, nonempty blockers, and incomplete or applicable failed checks remain.

## Application example
Example prose.

## Quick reference
Reference prose.

## Common mistakes
Mistake prose.
"""

# (name, mutated text, expected diagnostic code)
_FIXTURE_CASES: tuple[tuple[str, str, str], ...] = (
    (
        "skipped numbering",
        _FIXTURE_GOOD.replace("3. **Publish in one order.**", "4. **Publish in one order.**"),
        "SKILL_STRUCTURE_PROCEDURE_NUMBERING",
    ),
    (
        "noun-led step",
        _FIXTURE_GOOD.replace("2. **Validate before consumption.**", "2. **Input validation.**"),
        "SKILL_STRUCTURE_PROCEDURE_VERB",
    ),
    (
        "missing check row",
        _FIXTURE_GOOD.replace("| `beta-check` | Build the beta crate | `evidence/beta.log` |\n", ""),
        "SKILL_STRUCTURE_VALIDATION_MISSING",
    ),
    (
        "extra check row",
        _FIXTURE_GOOD.replace(
            "| `beta-check` | Build the beta crate | `evidence/beta.log` |",
            "| `beta-check` | Build the beta crate | `evidence/beta.log` |\n| `gamma-check` | Run the gamma tool | `evidence/gamma.log` |",
        ),
        "SKILL_STRUCTURE_VALIDATION_EXTRA",
    ),
    (
        "empty evidence cell",
        _FIXTURE_GOOD.replace("| Build the beta crate | `evidence/beta.log` |", "| Build the beta crate |  |"),
        "SKILL_STRUCTURE_VALIDATION_EVIDENCE",
    ),
    (
        "fourth status",
        _FIXTURE_GOOD.replace(
            "## Application example",
            "### software verified\nPredicate: every software gate passed.\n\n## Application example",
        ),
        "SKILL_STRUCTURE_EXIT_LABELS",
    ),
    (
        "overlapping predicates",
        _FIXTURE_GOOD.replace(
            "Predicate: empty incomplete, complete equals included scope, can_progress absent, empty blockers, all applicable checks passed.",
            "Predicate: empty incomplete, complete equals included scope, can_progress=true, empty blockers, all applicable checks passed.",
        ),
        "SKILL_STRUCTURE_EXIT_OVERLAP",
    ),
)


# --- typed worked example (an arm of skill-structure, not a 15th check) -----

MAX_TOML_EXAMPLE_BYTES = 64 * 1024


def _toml_leaf_paths(value, prefix: str, known: frozenset[str], depth: int = 0) -> set[tuple[str, str]]:
    """Flatten a parsed TOML example into (path, emptiness shape) pairs.

    Descent STOPS at any prefix already known to be a leaf, so opaque schema
    scalars that happen to be TOML tables or arrays of tables - FileRef,
    ArtifactRef, and the like - are not mistaken for structs and reported as
    invented fields.

    The second element is "" for an ordinary value, "array" when the value AT
    that path is an empty list, and "table" when it is an empty table. An empty
    composite collection has no sub-keys to flatten, so it can only ever
    surface as its own bare parent path, which is never itself a schema leaf;
    recording WHICH empty shape it was is what lets the caller tell the
    prescribed known-empty form from a wrong container type.
    """
    if depth > MAX_AST_DEPTH:
        return {(prefix, "")}
    if prefix and prefix in known:
        return {(prefix, "")}
    if isinstance(value, dict):
        out: set[tuple[str, str]] = set()
        for key, sub in value.items():
            out |= _toml_leaf_paths(sub, f"{prefix}.{key}" if prefix else str(key), known, depth + 1)
        return out or {(prefix, "table")}
    if isinstance(value, list):
        out = set()
        for item in value:
            out |= _toml_leaf_paths(item, prefix, known, depth + 1)
        return out or {(prefix, "array")}
    return {(prefix, "")}


def _is_composite_parent(path: str, known: frozenset[str]) -> bool:
    """True when `path` is a PROPER prefix of at least one known schema leaf."""
    return any(leaf.startswith(path + ".") for leaf in known)


def _permits_empty(path: str, shape: str, known: frozenset[str], arrays: frozenset[str]) -> bool:
    """True only for an empty ARRAY standing where the schema declares an array.

    `docs/skill-template.md` - "Optional means key absence; known-empty means
    an empty collection" - makes `x = []` the spelling for a known-empty
    collection, and for a COMPOSITE collection the bare parent path is the only
    path it can produce. The allowance is bounded by the schema's own type:

      * the path must be a proper prefix of a known leaf (not a typo), AND
      * the schema must declare that path `type == "array"`.

    So an empty array is accepted at an array-of-struct path and rejected at a
    struct or tagged path. `driver.build_contract` is a struct and
    `review.lineage` is a tagged union; `[]` at either is a wrong container
    type that `.opencode/schema/validate.py` rejects, so the worked example
    must not show it. An empty TABLE is never a known-empty collection.
    """
    if shape != "array":
        return False
    return path in arrays and _is_composite_parent(path, known)


# A `schema = N` statement in prose or inline code, used to hold the canonical
# skill template to the derived version.
SCHEMA_ASSIGN_RE = re.compile(r"\bschema\s*=\s*(\d+)")


def derive_schema_version(validator: Path) -> tuple[int | None, str]:
    """The current handoff schema version, AST-derived from validate.py.

    M6 recheck / B1. This check used to REQUIRE `schema = 1` in every skill's
    worked example. When the approved schema-2 migration landed everywhere
    else, the corpus could not follow: correcting a skill to schema 2 made
    this harness fail, so the wrong version was pinned by the very check meant
    to keep examples valid. That is the fourth instance in M6 of hand-
    maintained data standing where a derivation belongs, so the number is no
    longer written here at all.

    Derivation: the single module-level INT constant in validate.py whose name
    contains SCHEMA_VERSION. The diagnostic code of the same name is a string
    and is filtered out by the int requirement. Zero or several such constants
    is reported rather than guessed - an ambiguous derivation must not silently
    pick one.
    """
    try:
        tree = ast.parse(validator.read_text(encoding="utf-8"))
    except (OSError, SyntaxError) as exc:
        return None, f"cannot parse {rel(validator.parent.parent.parent, validator)}: {exc}"
    found: dict[str, int] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if value is None or not isinstance(value, ast.Constant) or not isinstance(value.value, int):
            continue
        if isinstance(value.value, bool):
            continue
        for t in targets:
            if isinstance(t, ast.Name) and "SCHEMA_VERSION" in t.id:
                found[t.id] = value.value
    if not found:
        return None, ("validate.py declares no module-level integer constant whose name contains "
                      "SCHEMA_VERSION, so the version the corpus must use cannot be derived")
    if len(found) > 1:
        return None, (f"validate.py declares {len(found)} SCHEMA_VERSION-ish integer constants "
                      f"({', '.join(sorted(found))}); the derivation is ambiguous and must not guess")
    return next(iter(found.values())), ""


def analyze_typed_example(text: str, stage: str | None, kind: str | None,
                          known: frozenset[str],
                          arrays: frozenset[str] = frozenset(),
                          schema_version: int = 2) -> list[tuple[str, str]]:
    """Assert the '## Application example' shows the skill's emitted handoff as TOML.

    M3 makes these five skills emit typed TOML handoffs, so the worked example
    must be that handoff in TOML rather than prose. This also gives the
    null-sentinel arm of skill-status-vocabulary a guaranteed subject: before
    this, no skill contained a ```toml fence at all, so that arm had nothing to
    scan.
    """
    out: list[tuple[str, str]] = []
    body = None
    for heading, section, _ in h2_sections(text):
        if heading == "Application example":
            body = section
            break
    if body is None:
        out.append(("SKILL_STRUCTURE_EXAMPLE_MISSING",
                    "no '## Application example' section, so the skill shows no typed worked example of the handoff it emits"))
        return out
    blocks = fenced_blocks(body, "toml")
    if not blocks:
        out.append(("SKILL_STRUCTURE_EXAMPLE_NO_TOML",
                    "'## Application example' contains no ```toml fenced block; M3 skills emit typed TOML handoffs, so the worked example must show one"))
        return out
    if stage is None or kind is None:
        out.append(("SKILL_STRUCTURE_EXAMPLE_NO_CONTRACT",
                    "the contract declares no parseable stage/emits kind, so the typed example cannot be matched to the handoff it claims to show"))
        return out
    parsed: list[dict] = []
    for index, block in enumerate(blocks, start=1):
        if len(block.encode("utf-8", "replace")) > MAX_TOML_EXAMPLE_BYTES:
            out.append(("SKILL_STRUCTURE_EXAMPLE_TOML_INVALID", f"toml example block {index} exceeds the {MAX_TOML_EXAMPLE_BYTES}-byte bound"))
            continue
        try:
            parsed.append(tomllib.loads(block))
        except (tomllib.TOMLDecodeError, ValueError) as exc:
            out.append(("SKILL_STRUCTURE_EXAMPLE_TOML_INVALID",
                        f"toml example block {index} does not parse as TOML: {_one_line(str(exc), 160)}"))
    handoffs = []
    for doc in parsed:
        h = doc.get("handoff")
        if isinstance(h, dict) and h.get("stage") == stage and h.get("schema") == schema_version:
            handoffs.append(doc)
    if not handoffs:
        stale = sorted({d["handoff"]["schema"] for d in parsed
                        if isinstance(d.get("handoff"), dict)
                        and d["handoff"].get("stage") == stage
                        and d["handoff"].get("schema") != schema_version
                        and isinstance(d["handoff"].get("schema"), int)})
        extra = (f" A block for this stage declares schema {stale} instead; the validator's current version "
                 f"is {schema_version}, so a reader copying this example would be rejected with "
                 "SCHEMA_VERSION." if stale else "")
        out.append(("SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF",
                    f"no toml example block is the emitted handoff: one must contain a [handoff] table with "
                    f"schema = {schema_version} (DERIVED from validate.py, not written here) and "
                    f"stage = {stage!r}.{extra}"))
        return out
    for doc in handoffs:
        # A path that is not itself a schema leaf is accepted ONLY in the one
        # form the template prescribes for "this collection is known to be
        # empty", and only where the SCHEMA'S OWN TYPE says a collection
        # belongs. `_permits_empty` carries that type through, so every other
        # shape stays rejected: an unknown scalar, a misspelled field, a
        # non-empty composite carrying an unknown sub-key, an empty collection
        # at a path that prefixes no known leaf, and - the type-blind hole -
        # an empty array standing at a struct or tagged path.
        unknown = sorted(
            p for p, shape in _toml_leaf_paths(doc, "", known)
            if p not in known and not _permits_empty(p, shape, known, arrays)
        )
        if unknown:
            out.append(("SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD",
                        f"{kind}: the typed example names field(s) {', '.join(unknown[:8])} that are not schema leaves of that kind; the worked example must not drift from the contract"))
    return out


_EXAMPLE_KNOWN = frozenset({
    "handoff.schema", "handoff.stage", "handoff.status", "handoff.notes", "alpha.name",
    # a COMPOSITE collection: its schema leaves are sub-keys, so the collection
    # itself ('alpha.items') is a proper prefix and never a leaf.
    "alpha.items.id", "alpha.items.value",
    # Two composite parents that are NOT arrays, mirroring the real schema:
    # `driver.build_contract` is a struct and `review.lineage` is a tagged
    # union (.opencode/schema/validate.py). Both are proper prefixes of a known
    # leaf, so only the schema's type distinguishes them from `alpha.items`.
    "driver.build_contract.cargo_chip_feature", "driver.build_contract.init_calls",
    "review.lineage.kind", "review.lineage.previous",
})
# The subset of the above composite parents the schema declares `type ==
# "array"`. `driver.build_contract` and `review.lineage` are deliberately
# absent: they are a struct and a tagged union.
_EXAMPLE_ARRAYS = frozenset({"alpha.items"})
_EXAMPLE_GOOD = """# Fixture

## Application example

```toml
[handoff]
schema = 1
stage = "generate-pac"
status = "ready"
notes = [{ path = "notes/PAC.md", sha256 = "ab" }]

[alpha]
name = "x"
items = []
```
"""

_EXAMPLE_NONEMPTY_COMPOSITE = _EXAMPLE_GOOD.replace(
    "items = []",
    '\n[[alpha.items]]\nid = "a"\nvalue = "b"',
)

_EXAMPLE_CASES: tuple[tuple[str, str, str], ...] = (
    ("no Application example section", "# Fixture\n\n## Procedure\n1. Inspect it.\n", "SKILL_STRUCTURE_EXAMPLE_MISSING"),
    ("section present but no toml fence", "# Fixture\n\n## Application example\n\nProse only, no fence.\n", "SKILL_STRUCTURE_EXAMPLE_NO_TOML"),
    ("unparseable toml", _EXAMPLE_GOOD.replace("schema = 1", "schema = = 1"), "SKILL_STRUCTURE_EXAMPLE_TOML_INVALID"),
    ("wrong stage", _EXAMPLE_GOOD.replace('stage = "generate-pac"', 'stage = "scaffold-hal"'), "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF"),
    ("schema is not the derived version", _EXAMPLE_GOOD.replace("schema = 1", "schema = 2"), "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF"),
    ("field absent from the kind's leaf set", _EXAMPLE_GOOD.replace('name = "x"', 'name = "x"\nbogus = "y"'), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    # --- known-empty composite acceptance must not open a hole ---------------
    ("misspelled composite collection, empty",
     _EXAMPLE_GOOD.replace("items = []", "itemz = []"), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    ("empty collection at a path prefixing no known leaf",
     _EXAMPLE_GOOD.replace("items = []", "items = []\nzeta = []"), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    ("empty TABLE at a path prefixing no known leaf",
     _EXAMPLE_GOOD.replace("items = []", "items = []\n\n[alpha.zeta]"), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    ("non-empty composite carrying an unknown sub-key",
     _EXAMPLE_NONEMPTY_COMPOSITE.replace('value = "b"', 'value = "b"\nnope = "c"'), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    ("non-empty composite whose sub-keys are all unknown",
     _EXAMPLE_NONEMPTY_COMPOSITE.replace('id = "a"\nvalue = "b"', 'wrong = "a"'), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    # --- the known-empty allowance must be TYPE-aware, not merely name-aware -
    ("empty array at a STRUCT composite path",
     _EXAMPLE_GOOD.replace("items = []", "items = []\n\n[driver]\nbuild_contract = []"),
     "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    ("empty array at a TAGGED composite path",
     _EXAMPLE_GOOD.replace("items = []", "items = []\n\n[review]\nlineage = []"),
     "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
    ("empty table at an ARRAY composite path",
     _EXAMPLE_GOOD.replace("items = []", "\n[alpha.items]"),
     "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
)

# Shapes that must be ACCEPTED: the conforming fixture itself carries the
# known-empty composite collection ('items = []'), and the populated form of
# the same collection must stay legal.
_EXAMPLE_CLEAN_CASES: tuple[tuple[str, str], ...] = (
    ("known-empty composite collection", _EXAMPLE_GOOD),
    ("non-empty composite collection", _EXAMPLE_NONEMPTY_COMPOSITE),
)


def structure_fixture_failures() -> list[str]:
    """Self-test both analyzers. Returns human-readable problems, empty when sound."""
    problems: list[str] = []
    clean = analyze_structure(_FIXTURE_GOOD, _FIXTURE_CHECKS)
    if clean:
        problems.append(f"the conforming fixture was rejected with {[c for c, _ in clean]}; the analyzer rejects everything and proves nothing")
    for name, text, expected in _FIXTURE_CASES:
        codes = [c for c, _ in analyze_structure(text, _FIXTURE_CHECKS)]
        if expected not in codes:
            problems.append(f"malformed near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    # The fixture corpus is written at schema 1 and the analyzer is driven at
    # schema 1 here ON PURPOSE: the live corpus is at a different version, so a
    # green self-test proves the version is a PARAMETER and not a constant.
    clean = analyze_typed_example(_EXAMPLE_GOOD, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS, 1)
    if clean:
        problems.append(f"the conforming typed example was rejected with {[c for c, _ in clean]}")
    for name, text in _EXAMPLE_CLEAN_CASES:
        codes = [c for c, _ in analyze_typed_example(text, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS, 1)]
        if codes:
            problems.append(f"conforming typed example {name!r} was rejected with {codes}")
    for name, text, expected in _EXAMPLE_CASES:
        codes = [c for c, _ in analyze_typed_example(text, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS, 1)]
        if expected not in codes:
            problems.append(f"typed-example near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    # The version must be LOAD-BEARING: the conforming fixture analyzed at a
    # different schema version must be rejected. Without this the parameter
    # could be ignored and nobody would notice.
    codes = [c for c, _ in analyze_typed_example(
        _EXAMPLE_GOOD, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS, 2)]
    if "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF" not in codes:
        problems.append("the conforming schema-1 fixture was ACCEPTED when analyzed at schema 2; the derived "
                        "version is not actually being applied")
    return problems



# --- check 19: skill-contracts ----------------------------------------------


def parse_skill_contract(root: Path, path: Path, report: Report) -> dict[str, list[str]] | None:
    """Shared front end: raw fence -> key -> values, or None after reporting."""
    r = rel(root, path)
    entries, err, lineno = parse_contract(read_text(path), SKILL_CONTRACT_INFO)
    if err:
        report.bad(r, str(lineno), "SKILL_CONTRACT_BLOCK", f"{err}; the skill template requires one '{SKILL_CONTRACT_INFO}' fence immediately after the H1")
        return None
    return contract_map(entries)


def check_skill_contracts(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_CONTRACT_ABORT"):
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_CONTRACT_NO_TARGETS",
                       "no skills were discovered; the skill contract checks would assert nothing")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            cmap = parse_skill_contract(root, path, report)
            if cmap is None:
                continue
            bad_keys = sorted(set(cmap) - set(SKILL_CONTRACT_KEYS))
            if bad_keys:
                report.bad(r, "contract", "SKILL_CONTRACT_UNKNOWN_KEY",
                           f"unknown contract key(s): {', '.join(bad_keys)}; allowed keys are {', '.join(SKILL_CONTRACT_KEYS)}")
                continue
            missing = [k for k in SKILL_CONTRACT_REQUIRED if k not in cmap]
            if missing:
                report.bad(r, "contract", "SKILL_CONTRACT_MISSING_KEY", f"contract is missing required key(s): {', '.join(missing)}")
                continue
            dup = [k for k in SKILL_CONTRACT_SINGLE if len(cmap[k]) != 1]
            if dup:
                report.bad(r, "contract", "SKILL_CONTRACT_REPEATED_KEY", f"key(s) {', '.join(dup)} must appear exactly once")
                continue
            for key in SKILL_CONTRACT_KEYS:
                for value in cmap.get(key, []):
                    if re.search(r"\s*,\s+|\s+,|\s+\||\|\s+", value):
                        report.bad(r, key, "SKILL_CONTRACT_WHITESPACE",
                                   f"{key} value {value!r} has whitespace around a comma or pipe; values are whitespace-free around separators")
            spec = SKILL_SPEC.get(name)
            if spec is None:
                report.bad(r, "contract", "SKILL_CONTRACT_UNMAPPED",
                           f"skill {name!r} has no canonical contract mapping; add it to SKILL_SPEC")
                continue
            if cmap["stage"][0] != spec["stage"]:
                report.bad(r, "stage", "SKILL_CONTRACT_STAGE", f"stage is {cmap['stage'][0]!r}; the canonical stage for {name} is {spec['stage']!r}")
            if cmap["emitter"][0] != spec["emitter"]:
                report.bad(r, "emitter", "SKILL_CONTRACT_EMITTER", f"emitter is {cmap['emitter'][0]!r}; {name} is emitted by {spec['emitter']!r}")
            emits = cmap["emits"][0]
            parts = emits.split("|")
            if len(parts) != 3:
                report.bad(r, "emits", "SKILL_CONTRACT_EMITS_FORMAT",
                           f"emits value {emits!r} must be '<kind>|<deterministic filename>|<sorted comma-separated leaf paths>'")
            else:
                if parts[0] != spec["kind"]:
                    report.bad(r, "emits", "SKILL_CONTRACT_EMITS_KIND", f"emits kind is {parts[0]!r}; {name} emits {spec['kind']!r}")
                if parts[1] != spec["filename"]:
                    report.bad(r, "emits", "SKILL_CONTRACT_EMITS_FILENAME", f"emits filename is {parts[1]!r}; the deterministic path is {spec['filename']!r}")
            for key in ("checks",):
                value = cmap[key][0]
                items = [v for v in value.split(",") if v]
                if items != sorted(set(items)):
                    report.bad(r, key, "SKILL_CONTRACT_UNSORTED", f"{key} value must be a sorted, duplicate-free comma-separated list")
            for value in cmap.get("consumes", []):
                if value.count("|") != 1:
                    report.bad(r, "consumes", "SKILL_CONTRACT_CONSUMES_FORMAT", f"consumes value {value!r} must be '<kind>|<sorted comma-separated leaf paths>'")
            for key in ("writes", "supplies-delta"):
                for value in cmap.get(key, []):
                    if value.count("|") != 1:
                        report.bad(r, key, "SKILL_CONTRACT_OWNERSHIP_FORMAT", f"{key} value {value!r} must be '<agent>|<ownership class>'")
            named = {cmap["emitter"][0]}
            for key in ("writes", "supplies-delta"):
                for value in cmap.get(key, []):
                    named.add(value.split("|")[0])
            declared = [v for v in cmap["participants"][0].split(",") if v]
            if declared != sorted(named):
                report.bad(r, "participants", "SKILL_CONTRACT_PARTICIPANTS",
                           f"participants is {declared}; it must be the sorted set of every agent named by emitter/writes/supplies-delta, {sorted(named)}")
            ok += 1
        report.ok("skill-contracts", f"{ok} of {len(skills)} skill contract fences parsed from raw Markdown and conform", mark)


# --- check 20: skill-emissions ----------------------------------------------


def skill_registry(root: Path, report: Report, code: str) -> dict[str, dict] | None:
    validator = root / ".opencode" / "schema" / "validate.py"
    if not validator.is_file():
        report.bad(".opencode/schema/validate.py", "0", code, "validator absent; the structural field registry cannot be derived")
        return None
    try:
        return derive_registry(validator)
    except RegistryError as exc:
        report.bad(".opencode/schema/validate.py", "0", code, f"structural field registry could not be derived: {exc}")
        return None


def check_skill_emissions(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_EMISSION_ABORT"):
        registry = skill_registry(root, report, "SKILL_EMISSION_NO_REGISTRY")
        if registry is None:
            return
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_EMISSION_NO_TARGETS", "no skills discovered; nothing to compare against the AST registry")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            cmap = parse_skill_contract(root, path, report)
            if cmap is None:
                continue
            values = cmap.get("emits", [])
            if not values:
                report.bad(r, "emits", "SKILL_EMISSION_MISSING", "contract declares no 'emits:' line")
                continue
            parts = values[0].split("|")
            if len(parts) != 3:
                report.bad(r, "emits", "SKILL_EMISSION_FORMAT", f"emits value {values[0]!r} is not '<kind>|<filename>|<leaves>'")
                continue
            kind = parts[0]
            if kind not in registry:
                report.bad(r, "emits", "SKILL_EMISSION_UNKNOWN_KIND", f"emits kind {kind!r} is not a validator handoff kind ({', '.join(sorted(registry))})")
                continue
            declared = _leaves(parts[2])
            expected = registry[kind]["paths"] | registry[kind]["common"]
            unknown = sorted(declared - expected)
            missing = sorted(expected - declared)
            if unknown:
                report.bad(r, "emits", "SKILL_EMISSION_UNKNOWN_PATH",
                           f"{kind}: path(s) {', '.join(unknown[:8])} are not structurally valid leaves of table {registry[kind]['table']!r}")
            if missing:
                report.bad(r, "emits", "SKILL_EMISSION_INCOMPLETE",
                           f"{kind}: contract omits {len(missing)} required structural leaf path(s), first: {', '.join(missing[:8])}")
            if not cmap.get("checks"):
                report.bad(r, "checks", "SKILL_EMISSION_CHECKS_MISSING", "contract declares no 'checks:' line")
                continue
            declared_checks = [c for c in cmap["checks"][0].split(",") if c]
            want_checks = list(registry[kind]["checks"])
            if declared_checks != want_checks:
                report.bad(r, "checks", "SKILL_EMISSION_CHECKS",
                           f"{kind}: checks are {declared_checks}; the AST-derived canonical set is exactly {want_checks}")
            ok += 1
        report.ok("skill-emissions", f"{ok} skill emits/checks declarations equal the AST-derived registry of {len(registry)} kinds", mark)


# --- check 21: skill-consumption --------------------------------------------


def check_skill_consumption(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_CONSUMPTION_ABORT"):
        for problem in consumed_resolution_failures():
            report.bad("tools/selfcheck.py", "resolve_consumed", "SKILL_CONSUMPTION_RESOLVER",
                       f"the canonical consumed-set resolver failed its self-test: {problem}")
        registry = skill_registry(root, report, "SKILL_CONSUMPTION_NO_REGISTRY")
        if registry is None:
            return
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_CONSUMPTION_NO_TARGETS", "no skills discovered; no consumption declaration is asserted")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            cmap = parse_skill_contract(root, path, report)
            if cmap is None:
                continue
            spec = SKILL_SPEC.get(name)
            if spec is None:
                # Fail CLOSED. Skipping silently would let an unmapped skill
                # escape the consumption check entirely - the M4 defect shape,
                # where a missing entry degraded to "asserts nothing" instead
                # of "fails".
                report.bad(r, "consumes", "SKILL_CONSUMPTION_UNMAPPED",
                           f"skill {name!r} has no canonical contract mapping, so its consumption declaration is compared against nothing; add it to SKILL_SPEC")
                continue
            values = cmap.get("consumes", [])
            if not values:
                report.bad(r, "consumes", "SKILL_CONSUMPTION_MISSING", "contract declares no 'consumes:' line; intake declares 'consumes: none|none'")
                continue
            # Every canonical consumed set - whole-kind, whole-kind-minus, or
            # enumerated - resolves against the AST registry, never a literal
            # copy of it. That makes `want` a subset of `valid` by
            # construction, so SKILL_CONSUMPTION_SET and
            # SKILL_CONSUMPTION_UNKNOWN_PATH can no longer contradict each
            # other and leave the check unsatisfiable.
            want: dict[str, set[str]] = {}
            spec_stale = False
            for kind, raw in spec["consumes"].items():
                if kind not in registry:
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_UNKNOWN_KIND",
                               f"canonical mapping names predecessor kind {kind!r}, which the validator does not define")
                    spec_stale = True
                    continue
                valid = registry[kind]["paths"] | registry[kind]["common"]
                resolved, stale = resolve_consumed(valid, raw)
                if stale:
                    report.bad("tools/selfcheck.py", f"SKILL_SPEC[{name}].consumes[{kind}]",
                               "SKILL_CONSUMPTION_SPEC_STALE",
                               f"the canonical mapping names {', '.join(stale[:8])}, which {kind} no longer "
                               "defines. Refresh the mapping against validate.py; leaving it stale would make "
                               "this check unsatisfiable, because no declaration can be both equal to the "
                               "mapping and a subset of the validator's paths")
                    spec_stale = True
                    continue
                want[kind] = resolved
            if spec_stale:
                continue
            if not want:
                if values != ["none|none"]:
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_NOT_INTAKE",
                               f"{name} is intake and must declare exactly one 'consumes: none|none', got {values}")
                else:
                    ok += 1
                continue
            got: dict[str, set[str]] = {}
            malformed = False
            for value in values:
                if value.count("|") != 1:
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_FORMAT", f"consumes value {value!r} must be '<kind>|<leaves>'")
                    malformed = True
                    continue
                kind, _, raw = value.partition("|")
                if kind == "none":
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_NOT_INTAKE", f"{name} consumes a predecessor handoff and must not declare 'none'")
                    malformed = True
                    continue
                if kind not in registry:
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_UNKNOWN_KIND", f"consumes kind {kind!r} is not a validator handoff kind")
                    malformed = True
                    continue
                got[kind] = _leaves(raw)
            if malformed:
                continue
            if sorted(got) != sorted(want):
                report.bad(r, "consumes", "SKILL_CONSUMPTION_WRONG_PREDECESSOR",
                           f"{name} declares predecessor kind(s) {sorted(got)}; M3 assigns it exactly {sorted(want)}")
                continue
            for kind in sorted(want):
                valid = registry[kind]["paths"] | registry[kind]["common"]
                unknown = sorted(got[kind] - valid)
                if unknown:
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_UNKNOWN_PATH",
                               f"{kind}: consumed leaf/leaves {', '.join(unknown[:8])} are not structurally valid paths of that kind")
                if got[kind] != want[kind]:
                    absent = sorted(want[kind] - got[kind])
                    surplus = sorted(got[kind] - want[kind])
                    report.bad(r, "consumes", "SKILL_CONSUMPTION_SET",
                               f"{kind}: consumed leaf set differs from the M3 predecessor set; missing {absent[:6] or 'none'}, unexpected {surplus[:6] or 'none'}")
            ok += 1
        report.ok("skill-consumption",
                  f"{ok} skill consumption declarations equal their canonical predecessor set EXACTLY, where that "
                  "set is resolved against the AST-derived registry in every case - whole kind, whole kind minus "
                  "named exclusions, or an enumerated subset - so the equality assertion and the "
                  "structurally-valid-path assertion cannot disagree. A mapping naming a path the validator has "
                  "retired now fails at the mapping (SKILL_CONSUMPTION_SPEC_STALE), not by making the check "
                  "unsatisfiable. What is still hand-maintained is the EXCLUSION list, not the inclusion list: an "
                  "exclusion that should have been dropped keeps a live leaf out of the expected set, and no check "
                  "here can tell that from a deliberate one", mark)


# --- check 22: skill-structure ----------------------------------------------


def check_skill_structure(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_STRUCTURE_ABORT"):
        for problem in structure_fixture_failures():
            report.bad("tools/selfcheck.py", "analyze_structure", "SKILL_STRUCTURE_FIXTURE",
                       f"the template-form analyzer failed its in-memory near-miss fixtures: {problem}")
        registry = skill_registry(root, report, "SKILL_STRUCTURE_NO_REGISTRY")
        if registry is None:
            return
        version, verr = derive_schema_version(root / ".opencode" / "schema" / "validate.py")
        if version is None:
            report.bad(".opencode/schema/validate.py", "SCHEMA_VERSION", "SKILL_STRUCTURE_VERSION_UNDERIVABLE",
                       f"the current handoff schema version could not be derived: {verr}. This check must not "
                       "fall back to a literal - a pinned literal is exactly what stranded the corpus on the "
                       "rejected version")
            return
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_STRUCTURE_NO_TARGETS", "no skills discovered; template form is asserted against nothing")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            text = read_text(path)
            entries, err, _ = parse_contract(text, SKILL_CONTRACT_INFO)
            checks: list[str] = []
            stage: str | None = None
            kind: str | None = None
            if not err:
                cmap = contract_map(entries)
                values = cmap.get("checks", [])
                if values:
                    checks = [c for c in values[0].split(",") if c]
                if cmap.get("stage"):
                    stage = cmap["stage"][0]
                emits = cmap.get("emits", [])
                if emits and "|" in emits[0]:
                    candidate = emits[0].split("|")[0]
                    if candidate in registry:
                        kind = candidate
            if not checks:
                report.bad(r, "contract", "SKILL_STRUCTURE_NO_CHECKS",
                           "no parseable 'checks:' declaration, so the Procedure step count and Validation row set cannot be asserted; add the skill contract fence")
            for code, message in analyze_structure(text, checks):
                report.bad(r, "structure", code, message)
            known = frozenset(registry[kind]["paths"] | registry[kind]["common"]) if kind else frozenset()
            arrays = frozenset(registry[kind]["arrays"] | registry[kind]["common_arrays"]) if kind else frozenset()
            for code, message in analyze_typed_example(text, stage, kind, known, arrays, version):
                report.bad(r, "Application example", code, message)
            ok += 1
        # The canonical template is the 14th file carrying the worked handoff
        # version. It is not a discovered skill, and it states the version in
        # PROSE rather than in a TOML fence, so it would otherwise keep
        # shipping the rejected version to every skill authored from it.
        template = root / SKILL_TEMPLATE_RELPATH
        if template.is_file():
            ttext = read_text(template)
            stale = sorted({int(n) for n in SCHEMA_ASSIGN_RE.findall(ttext) if int(n) != version})
            if stale:
                report.bad(SKILL_TEMPLATE_RELPATH, "Application example",
                           "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF",
                           f"the canonical template tells authors to write schema = {stale} in the worked "
                           f"handoff; the current version derived from validate.py is {version}. Every skill "
                           "authored from this template inherits the rejected version")
        report.ok("skill-structure",
                  f"{ok} skills carry the ten template sections, assertable procedural form, and a typed TOML "
                  f"worked example matching their emitted kind at schema version {version}, DERIVED by AST from "
                  f"validate.py rather than written here (analyzer self-tested against "
                  f"{len(_FIXTURE_CASES) + len(_EXAMPLE_CASES)} near-misses plus a version-is-load-bearing case). "
                  "At the next schema transition the expected version follows the validator automatically; a "
                  "renamed or ambiguous version constant fails loudly rather than defaulting", mark)


# --- check 23: skill-trigger-frontmatter ------------------------------------

SCAFFOLD_REQUIRED_TERMS = ("clocks", "init", "interrupt_mod!", "generated mappings", "memory.x", "linker")
PLATFORM_STAGE = "scaffold-hal"


def platform_roles(root: Path, contracts: dict[str, dict[str, list[str]]]) -> tuple[list[str], list[str]]:
    """Split the platform stage into (non-final slices, final consolidators).

    Derivation: subjects are the discovered skills whose PARSED contract stage
    is the platform stage. A subject is a non-final slice exactly when its own
    '### ready' exit predicate declares ready unreachable. Nothing here names a
    skill; the role is read out of the skill's own text.
    """
    slices: list[str] = []
    final: list[str] = []
    paths = skill_paths(root)
    for name in skills_at_stage(contracts, PLATFORM_STAGE):
        body = exit_predicate(read_text(paths[name]), "ready") or ""
        (slices if SLICE_UNREACHABLE_TOKEN in body.lower() else final).append(name)
    return sorted(slices), sorted(final)


def check_skill_trigger_frontmatter(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_TRIGGER_ABORT"):
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_TRIGGER_NO_TARGETS", "no skills discovered; no dispatch description is asserted")
            return
        # The whole-platform dispatch terms belong to the FINAL consolidator,
        # derived from parsed stage + parsed ready-predicate role. A non-final
        # slice describes one slice and must not be required to advertise the
        # complete platform vocabulary.
        contracts = skill_contracts(root)
        _slices, consolidators = platform_roles(root, contracts)
        if not consolidators:
            report.bad(".opencode/skills", "0", "SKILL_TRIGGER_NO_CONSOLIDATOR",
                       f"no discovered skill at stage {PLATFORM_STAGE!r} declares a reachable ready exit, so the "
                       f"whole-platform dispatch terms {', '.join(SCAFFOLD_REQUIRED_TERMS)} are asserted against nothing")
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            try:
                data = parse_frontmatter(read_text(path))
            except (FMError, OSError) as exc:
                report.bad(r, "0", "SKILL_TRIGGER_UNPARSEABLE", f"cannot read frontmatter: {exc}")
                continue
            desc = data.get("description")
            if not isinstance(desc, str) or not desc.strip():
                report.bad(r, "description", "SKILL_TRIGGER_MISSING", "description is absent or empty; it must open with an observable 'Use when' dispatch trigger")
                continue
            flat = norm_ws(desc)
            if not flat.startswith("Use when"):
                report.bad(r, "description", "SKILL_TRIGGER_OPENING",
                           f"description starts {flat[:40]!r}; after whitespace normalization it must start with 'Use when' and an observable dispatch trigger")
            if "Wrong for" not in flat:
                report.bad(r, "description", "SKILL_TRIGGER_WRONG_FOR",
                           "description does not contain 'Wrong for' naming adjacent excluded work; a description that only claims capability cannot disambiguate dispatch")
            if name in consolidators:
                absent = [t for t in SCAFFOLD_REQUIRED_TERMS if t.lower() not in flat.lower()]
                if absent:
                    report.bad(r, "description", "SKILL_TRIGGER_SCAFFOLD_TERMS",
                               f"the final platform consolidator's description does not name dispatch/search term(s): {', '.join(absent)}")
            ok += 1
        report.ok("skill-trigger-frontmatter", f"{ok} skill descriptions open with an observable 'Use when' trigger and name excluded adjacent work ({len(consolidators)} final platform consolidator)", mark)


# --- check 24: skill-ownership ----------------------------------------------


def check_skill_ownership(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_OWNERSHIP_ABORT"):
        data = load_registry(root, Report())  # silent: check_ownership reports absence
        owners: dict[str, str] = {}
        if isinstance(data, dict) and isinstance(data.get("file_classes"), list):
            for entry in data["file_classes"][:MAX_REGISTRY_ENTRIES]:
                if isinstance(entry, dict) and isinstance(entry.get("id"), str) and isinstance(entry.get("owner"), str):
                    owners[entry["id"]] = entry["owner"]
        if not owners:
            report.bad(".opencode/ownership.toml", "0", "SKILL_OWNERSHIP_NO_REGISTRY",
                       "no ownership registry classes could be loaded; skill writes/supplies-delta cannot be validated against an owner")
            return
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_OWNERSHIP_NO_TARGETS", "no skills discovered; no ownership declaration is asserted")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            text = read_text(path)
            cmap = parse_skill_contract(root, path, report)
            if cmap is None:
                continue
            spec = SKILL_SPEC.get(name)
            if spec is None:
                # Fail CLOSED, as in check_skill_consumption.
                report.bad(r, "writes", "SKILL_OWNERSHIP_UNMAPPED",
                           f"skill {name!r} has no canonical contract mapping, so its writes/supplies-delta sets are compared against nothing; add it to SKILL_SPEC")
                continue
            got_writes = set(cmap.get("writes", []))
            got_delta = set(cmap.get("supplies-delta", []))
            if got_writes != spec["writes"]:
                report.bad(r, "writes", "SKILL_OWNERSHIP_WRITES_SET",
                           f"writes set differs from the M3 assignment; missing {sorted(spec['writes'] - got_writes)[:6] or 'none'}, unexpected {sorted(got_writes - spec['writes'])[:6] or 'none'}")
            if got_delta != spec["supplies-delta"]:
                report.bad(r, "supplies-delta", "SKILL_OWNERSHIP_DELTA_SET",
                           f"supplies-delta set differs from the M3 assignment; missing {sorted(spec['supplies-delta'] - got_delta)[:6] or 'none'}, unexpected {sorted(got_delta - spec['supplies-delta'])[:6] or 'none'}")
            proc = None
            for heading, body, _ in h2_sections(text):
                if heading == "Procedure":
                    proc = body
                    break
            for value in sorted(got_writes):
                if value.count("|") != 1:
                    continue
                agent, _, cid = value.partition("|")
                if cid not in owners:
                    report.bad(r, "writes", "SKILL_OWNERSHIP_UNKNOWN_CLASS", f"writes names ownership class {cid!r}, which is absent from the registry")
                elif owners[cid] != agent:
                    report.bad(r, "writes", "SKILL_OWNERSHIP_WRITES_OWNER",
                               f"'writes: {value}' claims {agent} materializes {cid!r}, but the registry assigns it to {owners[cid]}; cross-owner authorship must be declared as supplies-delta, never disguised as a write")
            for value in sorted(got_delta):
                if value.count("|") != 1:
                    continue
                agent, _, cid = value.partition("|")
                if cid not in owners:
                    report.bad(r, "supplies-delta", "SKILL_OWNERSHIP_UNKNOWN_CLASS", f"supplies-delta names ownership class {cid!r}, which is absent from the registry")
                    continue
                if owners[cid] == agent:
                    report.bad(r, "supplies-delta", "SKILL_OWNERSHIP_DELTA_SAME_OWNER",
                               f"'supplies-delta: {value}' names the registry owner of {cid!r}; a delta is cross-owner semantic content, so declare it as a write instead")
                    continue
                if proc is None or owners[cid] not in proc:
                    report.bad(r, "supplies-delta", "SKILL_OWNERSHIP_MATERIALIZER_UNNAMED",
                               f"the procedure never names {owners[cid]}, the registry owner that must materialize {cid!r} and return its FileRef")
            ok += 1
        report.ok("skill-ownership", f"{ok} skills declare writes/supplies-delta consistent with the {len(owners)}-class ownership registry", mark)


# --- check 25: skill-status-vocabulary --------------------------------------

TOML_SCALAR_RE = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_.-]*\s*=\s*"([^"]*)"\s*(?:#.*)?$')
TOML_ARRAY_RE = re.compile(r'^\s*[A-Za-z_][A-Za-z0-9_.-]*\s*=\s*\[(.*)\]\s*(?:#.*)?$')


def check_skill_status_vocabulary(root: Path, report: Report) -> None:
    """Syntactically scoped. A global token search is unsatisfiable, because the
    schema's own Check (passed/failed/unrun/not-applicable), coverage and
    hardware-run vocabularies legitimately use the same words. Ordinary prose
    such as "unknown fact" is legal and must not fail here.
    """
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_STATUS_ABORT"):
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_STATUS_NO_TARGETS", "no skills discovered; stage vocabulary is asserted against nothing")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            text = read_text(path)

            # Scope 1: the raw contract fence's stage declaration.
            entries, err, _ = parse_contract(text, SKILL_CONTRACT_INFO)
            if err:
                report.bad(r, "contract", "SKILL_STATUS_NO_STAGE",
                           "no parseable skill contract, so the emitted-stage declaration cannot be scoped for the status vocabulary")
            else:
                spec = SKILL_SPEC.get(name)
                values = contract_map(entries).get("stage", [])
                if spec is not None and values and values[0] != spec["stage"]:
                    report.bad(r, "stage", "SKILL_STATUS_STAGE", f"contract stage is {values[0]!r}; the canonical emitted stage is {spec['stage']!r}")

            # Scope 2: the '## Exit criteria' section only.
            exit_body = None
            for heading, body, _ in h2_sections(text):
                if heading == "Exit criteria":
                    exit_body = body
                    break
            if exit_body is None:
                report.bad(r, "Exit criteria", "SKILL_STATUS_NO_EXIT",
                           "no '## Exit criteria' section, so the skill states no ready/partial/blocked stage vocabulary; legacy status tables are not the stage vocabulary")
            else:
                labels = [h for h, _ in h3_blocks(exit_body)]
                extra = [l for l in labels if l not in EXIT_STATUSES]
                if extra:
                    report.bad(r, "Exit criteria", "SKILL_STATUS_VOCABULARY",
                               f"exit criteria declare predicate label(s) {', '.join(extra)}; the stage vocabulary is exactly ready, partial, blocked")
                if sorted(set(labels)) != sorted(EXIT_STATUSES):
                    report.bad(r, "Exit criteria", "SKILL_STATUS_VOCABULARY",
                               f"exit criteria declare labels {labels or '(none)'}; all three of ready, partial, blocked are required")

            # Scope 3: TOML scalar values inside fenced TOML example blocks only.
            for target in [path] + skill_reference_paths(root, path):
                tr = rel(root, target)
                for block in fenced_blocks(read_text(target), "toml"):
                    for lineno, line in enumerate(block.split("\n"), start=1):
                        values2: list[str] = []
                        m = TOML_SCALAR_RE.match(line)
                        if m:
                            values2.append(m.group(1))
                        else:
                            m = TOML_ARRAY_RE.match(line)
                            if m:
                                values2.extend(re.findall(r'"([^"]*)"', m.group(1)))
                        for v in values2:
                            if v.strip().lower() in NULL_SENTINELS:
                                report.bad(tr, f"toml-example:{lineno}", "SKILL_STATUS_NULL_SENTINEL",
                                           f"typed TOML example uses the legacy null sentinel {v!r} as a field value; optional is absence and known-empty is an empty collection")
            ok += 1
        report.ok("skill-status-vocabulary", f"{ok} skills scope the stage vocabulary to their contract and exit criteria, with no null sentinels in typed TOML examples", mark)


# --- check 26: skill-verdict ------------------------------------------------


def review_gated_skills(root: Path, skills: dict[str, Path]) -> list[str]:
    """Skills whose own contract fence declares the independent-review check.

    Derived rather than listed: hard-coding the set let write-driver declare a
    review gate that the harness never asserted. A skill that cannot be parsed
    here is not silently dropped -- check_skill_contracts reports the same fence
    and fails the suite, so an unparseable fence can never quietly narrow this
    set to nothing.
    """
    gated: list[str] = []
    for name in sorted(skills):
        entries, err, _ = parse_contract(read_text(skills[name]), SKILL_CONTRACT_INFO)
        if err:
            continue
        for value in contract_map(entries).get("checks", []):
            if REVIEW_GATED_CHECK in [v for v in value.split(",") if v]:
                gated.append(name)
                break
    return gated


REVIEW_KIND = "08-review"


def verdict_subject_skills(root: Path, skills: dict[str, Path],
                           contracts: dict[str, dict[str, list[str]]]) -> tuple[list[str], list[str]]:
    """(review-gated consumers, verdict producers) - both parsed, never listed.

    Two disjoint reasons a skill must state the accepting-verdict sentence:

      * it CONSUMES a review gate, declared by the `independent-review` check
        in its own contract fence -> `review_gated_skills`; and
      * it PRODUCES the verdict, declared by its own `emits:` kind being
        08-review -> `skills_emitting_kind`.

    The producer is not in the gated set and should not be: it obtains no
    review of itself. That derivation is sound, but it left the corpus with a
    hole - the one skill that DEFINES which verdict accepts could delete the
    sentence, and its `| Review gate |` row with it, while the suite stayed
    green. That is the M4 defect's shape, so the emitter is asserted too.
    """
    gated = review_gated_skills(root, skills)
    producers = [n for n in skills_emitting_kind(contracts, REVIEW_KIND) if n in skills]
    return gated, sorted(producers)


def check_skill_verdict(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_VERDICT_ABORT"):
        skills = in_scope_skills(root)
        contracts = skill_contracts(root)
        gated, producers = verdict_subject_skills(root, skills, contracts)
        if not gated:
            report.bad(".opencode/skills", "0", "SKILL_VERDICT_NO_TARGETS",
                       f"no discovered skill declares the {REVIEW_GATED_CHECK!r} check in its contract fence; the accepting verdict sentence is asserted against nothing")
            return
        if not producers:
            report.bad(".opencode/skills", "0", "SKILL_VERDICT_NO_PRODUCER",
                       f"no discovered skill declares an 'emits:' kind of {REVIEW_KIND!r}; the skill that defines "
                       "which verdict accepts is asserted against nothing, so that sentence could be deleted with "
                       "the suite green")
            return
        subjects = sorted(set(gated) | set(producers))
        for name in subjects:
            path = skills[name]
            for target in [path] + skill_reference_paths(root, path):
                tr = rel(root, target)
                flat = norm_ws(read_text(target))
                if target == path and norm_ws(VERDICT_SENTENCE) not in flat:
                    role = "the skill emitting " + REVIEW_KIND if name in producers else "review-gated skill"
                    report.bad(tr, "0", "SKILL_VERDICT_SENTENCE_MISSING",
                               f"{role} does not state the exact accepting sentence {VERDICT_SENTENCE!r}")
                for legacy in LEGACY_VERDICT_TOKENS:
                    if legacy in flat:
                        report.bad(tr, "0", "SKILL_VERDICT_LEGACY_TOKEN",
                                   f"legacy spaced verdict wording {legacy!r} is present in gate prose; use the typed tokens ready / ready-with-fixes / not-ready")
        report.ok("skill-verdict",
                  f"{len(gated)} review-gated skill(s) and {len(producers)} {REVIEW_KIND} emitter(s) state the exact "
                  "accepting verdict sentence with no spaced legacy tokens", mark)


# --- check 27: skill-validator-wiring ---------------------------------------

VALIDATOR_STEM = "python .opencode/schema/validate.py"
VALIDATOR_ALL = "--kind all"

PROCEDURE_STEP_RE = re.compile(r"^\s*(\d+)[.)]\s")
STEP_TITLE_RE = re.compile(r"\*\*(.+?)\*\*")
PUBLISH_VERB_RE = re.compile(r"\b(?:re)?publish(?:es|ed|ing)?\b")


def procedure_steps(proc: str) -> list[tuple[int, str]]:
    """Split a '## Procedure' body into (step number, whole step text).

    Continuation lines belong to the step that opened them, so a multi-line
    step is judged whole.
    """
    steps: list[list] = []
    for line in proc.split("\n"):
        if PROCEDURE_STEP_RE.match(line):
            steps.append([line])
        elif steps:
            steps[-1].append(line)
    out: list[tuple[int, str]] = []
    for lines in steps:
        m = PROCEDURE_STEP_RE.match(lines[0])
        if m:
            out.append((int(m.group(1)), norm_ws(" ".join(lines))))
    return out


def handoff_publication_steps(steps: list[tuple[int, str]]) -> list[int]:
    """Indices of steps that PUBLISH A HANDOFF, derived from the step's own form.

    Two conjuncts, because either alone misclassifies real procedure text:

      * the step's bold TITLE must name a publish verb. Nearly every skill's
        step 1 mentions publishing somewhere in its body ("do not publish
        ..."), so body-level keyword matching selects step 1 everywhere and is
        useless; the title is the step's own statement of what it does.
      * some sentence of the step must bind that publish verb to a `handoff`.
        This drops publication of things that are not the typed handoff - e.g.
        a step titled "Publish the verified crate and rebuild at the final
        path" publishes a crate, and validating the handoff there would assert
        nothing.

    Returns list indices into `steps` (not step numbers), ascending.
    """
    out: list[int] = []
    for i, (_, text) in enumerate(steps):
        low = text.lower()
        title = STEP_TITLE_RE.search(low)
        if not title or not PUBLISH_VERB_RE.search(title.group(1)):
            continue
        if any(PUBLISH_VERB_RE.search(s) and "handoff" in s
               for s in re.split(r"(?<=[.!?])\s+", low)):
            out.append(i)
    return out


def check_skill_validator_wiring(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_VALIDATOR_ABORT"):
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_VALIDATOR_NO_TARGETS", "no skills discovered; validator wiring is asserted against nothing")
            return
        ok = 0
        for name in sorted(skills):
            path = skills[name]
            r = rel(root, path)
            text = read_text(path)
            flat = norm_ws(text)
            if VALIDATOR_STEM not in flat:
                report.bad(r, "0", "SKILL_VALIDATOR_STEM_MISSING",
                           f"skill never names the validator command stem {VALIDATOR_STEM!r}; a procedure that does not invoke the validator cannot gate on it")
            if VALIDATOR_ALL not in flat:
                report.bad(r, "0", "SKILL_VALIDATOR_ALL_GATE_MISSING",
                           f"skill never names the {VALIDATOR_ALL!r} final gate required before and after publication")
            proc = None
            for heading, body, _ in h2_sections(text):
                if heading == "Procedure":
                    proc = body
                    break
            if proc is None:
                report.bad(r, "Procedure", "SKILL_VALIDATOR_NO_PROCEDURE",
                           "no '## Procedure' section, so validation cannot be placed before consumption and at publication")
            else:
                # The old assertion was a bare cardinality - `sites >= 2` -
                # while the PASS message reported a TOPOLOGY of three named
                # positions. They disagreed, and the gap was demonstrable:
                # deleting a skill's publication-time invocation left three
                # other sites standing and the suite green. The assertion now
                # binds each invocation to the position the message names,
                # derived from the procedure's own step structure rather than
                # from any step-number literal.
                steps = procedure_steps(proc)
                pubs = handoff_publication_steps(steps)
                validating = [i for i, (_, t) in enumerate(steps) if "validate.py" in t]
                all_gates = [i for i, (_, t) in enumerate(steps) if VALIDATOR_ALL in t]
                if not steps:
                    report.bad(r, "Procedure", "SKILL_VALIDATOR_NO_STEPS",
                               "the '## Procedure' section contains no numbered steps, so no validation position "
                               "can be derived; the placement assertion must not pass vacuously")
                elif not pubs:
                    report.bad(r, "Procedure", "SKILL_VALIDATOR_NO_PUBLICATION_STEP",
                               "no procedure step publishes a handoff (a step whose bold title names a publish verb "
                               "and whose prose binds that verb to a 'handoff'); publication-time and final-gate "
                               "validation cannot be located, so the placement assertion would pass vacuously")
                else:
                    first_pub, last_pub = pubs[0], pubs[-1]
                    if not any(i < first_pub for i in validating):
                        report.bad(r, "Procedure", "SKILL_VALIDATOR_PRE_CONSUMPTION_MISSING",
                                   f"no validate.py invocation precedes the first handoff-publishing step "
                                   f"(step {steps[first_pub][0]}); the predecessor must be validated before it is "
                                   "consumed, not only after this skill has written its own handoff")
                    unbound = [steps[i][0] for i in pubs if i not in validating]
                    if unbound:
                        report.bad(r, "Procedure", "SKILL_VALIDATOR_PUBLICATION_MISSING",
                                   f"{len(unbound)} handoff-publishing step(s) do not invoke validate.py "
                                   f"(step(s) {', '.join(str(n) for n in unbound)}); M6/H11 binds EVERY publication "
                                   "step, not only the first. A handoff published without validation is unchecked at "
                                   "exactly the moment it becomes a predecessor for the next stage")
                    if not any(i >= last_pub for i in all_gates):
                        report.bad(r, "Procedure", "SKILL_VALIDATOR_FINAL_GATE_POSITION",
                                   f"no step at or after the last handoff-publishing step (step {steps[last_pub][0]}) "
                                   f"names the {VALIDATOR_ALL!r} gate; the all-gate must run on the final state, not "
                                   "before the final handoff exists")
            low = flat.lower()
            if "honor system" not in low and "honor-system" not in low:
                report.bad(r, "0", "SKILL_VALIDATOR_HONOR_SYSTEM",
                           "skill does not state the honor-system limitation; self-check proves the instruction is present, not that the agent ran it")
            if "cannot attest" not in low:
                report.bad(r, "0", "SKILL_VALIDATOR_HONOR_SYSTEM",
                           "skill does not state that validate.py cannot attest to an earlier invocation")
            ok += 1
        report.ok("skill-validator-wiring",
                  f"{ok} skills invoke validate.py at every DERIVED position - somewhere before their FIRST "
                  f"handoff-publishing step, at EVERY handoff-publishing step, and the {VALIDATOR_ALL!r} gate at or "
                  "after their LAST one - and disclose the honor-system limit. M6/H11 closed the former gap where "
                  "only the first and last publishing steps were bound and a middle one could drop validate.py "
                  "unnoticed. What remains unbound is what the derivation cannot see: a publishing step whose bold "
                  "title does not name a publish verb, or that does not bind that verb to a 'handoff', is not a "
                  "subject at all. And the whole check proves the INSTRUCTION is present, never that any agent "
                  "executed it", mark)


# --- check 28: skill-note-paths ---------------------------------------------


def check_skill_note_paths(root: Path, report: Report) -> None:
    """Skills emitting a note-bearing kind must state their exact first-note path.

    Subject derivation: `skills_emitting_kind(contracts, kind)` for each kind in
    NOTE_PATH_BY_KIND. The mapping is keyed by HANDOFF KIND, and the parsed
    `emits:` kind - not the mapping's key set - selects the subject.
    """
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_NOTE_ABORT"):
        skills = in_scope_skills(root)
        contracts = skill_contracts(root)
        targets: list[tuple[str, Path, str]] = []
        for kind in sorted(NOTE_PATH_BY_KIND):
            for name in skills_emitting_kind(contracts, kind):
                if name in skills:
                    targets.append((name, skills[name], NOTE_PATH_BY_KIND[kind]))
        if not targets:
            report.bad(".opencode/skills", "0", "SKILL_NOTE_NO_TARGETS",
                       f"no discovered skill declares an 'emits:' kind in {sorted(NOTE_PATH_BY_KIND)}; the deterministic note paths are asserted against nothing")
            return
        for name, path, want in sorted(targets):
            bare = want.split("/")[-1]
            files = [path] + skill_reference_paths(root, path)
            seen_exact = False
            for target in files:
                tr = rel(root, target)
                text = read_text(target)
                if want in text:
                    seen_exact = True
                for para in paragraphs(text):
                    if bare not in para:
                        continue
                    low = para.lower()
                    for soft in SOFT_NOTE_TOKENS:
                        if soft in low:
                            report.bad(tr, "note-record", "SKILL_NOTE_SOFT_DEFAULT",
                                       f"the paragraph naming {bare} offers the soft alternative {soft!r}; the first handoff note is the deterministic path {want!r}, not a default")
            if not seen_exact:
                report.bad(rel(root, path), "0", "SKILL_NOTE_PATH_MISSING",
                           f"{name} never states the exact deterministic first-note path {want!r}")
        report.ok("skill-note-paths", f"{len(targets)} skills state their exact deterministic first-note path with no soft alternative", mark)


# --- check 30: schema-attribution -------------------------------------------


def check_schema_attribution(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/schema", "SCHEMA_ATTRIBUTION_ABORT"):
        checked = 0
        for relpath in sorted(STALE_ATTRIBUTION):
            path = root / relpath
            if not path.is_file():
                report.bad(relpath, "0", "SCHEMA_ATTRIBUTION_FILE_MISSING", "schema file carrying decision attribution is absent")
                continue
            flat = norm_ws(read_text(path))
            for phrase in STALE_ATTRIBUTION[relpath]:
                if norm_ws(phrase) in flat:
                    report.bad(relpath, "attribution", "SCHEMA_ATTRIBUTION_STALE",
                               f"stale architect attribution {phrase!r} is present; hal-coordinator owns target, scope, decisions and foundation requirements (.opencode/ownership.toml scope-decisions/roadmap)")
            for phrase in REQUIRED_ATTRIBUTION.get(relpath, ()):
                if norm_ws(phrase) not in flat:
                    report.bad(relpath, "attribution", "SCHEMA_ATTRIBUTION_MISSING",
                               f"corrected coordinator attribution {phrase!r} is absent; removing the stale phrase is not enough, the owner must be named")
            checked += 1
        trace = root / ".opencode" / "schema" / "traceability.md"
        if trace.is_file():
            flat = norm_ws(read_text(trace))
            if "integrator materializes durable records" not in flat.lower():
                report.bad(".opencode/schema/traceability.md", "Field writer audit", "SCHEMA_ATTRIBUTION_TESTER_RECORD",
                           "the tester-record attribution is uncorrected; the tester authors test content/evidence and 07, while hal-integrator materializes durable records (.opencode/ownership.toml test-records)")
        report.ok("schema-attribution", f"{checked} schema files attribute decisions to hal-coordinator with no stale architect phrasing", mark)


# --- check 31: test-candidate-layout ----------------------------------------


def check_test_candidate_layout(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/schema/layout.md", "TEST_CANDIDATE_LAYOUT_ABORT"):
        relpath = ".opencode/schema/layout.md"
        path = root / relpath
        if not path.is_file():
            report.bad(relpath, "0", "TEST_CANDIDATE_LAYOUT_MISSING", "layout.md is absent, so the committed test-candidate root is ratified nowhere")
            return
        text = read_text(path)
        flat = norm_ws(text)
        if TEST_CANDIDATE_ROOT not in text:
            report.bad(relpath, "0", "TEST_CANDIDATE_LAYOUT_ROOT",
                       f"layout.md does not ratify the committed root {TEST_CANDIDATE_ROOT!r}; A15 requires it alongside halucinator/docs/ and halucinator/pac/")
        for part in ("src/**", "INVENTORY.md", "evidence/**"):
            if part not in text:
                report.bad(relpath, "0", "TEST_CANDIDATE_LAYOUT_PARTS",
                           f"layout.md does not ratify the test-candidate member {part!r}")
        for cid in TEST_CANDIDATE_CLASSES:
            if cid not in text:
                report.bad(relpath, "0", "TEST_CANDIDATE_LAYOUT_CLASSES",
                           f"layout.md does not cite the ownership class {cid!r} covering the committed test-candidate tree")
        for attr in TEST_CANDIDATE_ATTRIBUTES:
            if norm_ws(attr) not in flat:
                report.bad(relpath, "gitattributes", "TEST_CANDIDATE_LAYOUT_ATTRIBUTES",
                           f"layout.md does not document the exact attribute line {attr!r}")
        if REJECTED_SCRATCH not in text:
            report.bad(relpath, "gitignore", "TEST_CANDIDATE_LAYOUT_IGNORE",
                       f"layout.md does not state that the destination .gitignore adds only {REJECTED_SCRATCH!r}")
        low = flat.lower()
        if "never" not in low or "ignored" not in low:
            report.bad(relpath, "0", "TEST_CANDIDATE_LAYOUT_NONIGNORE",
                       "layout.md does not state that the test-candidate tree is never .run and never ignored; a gitignored tree is neither reviewable nor durable across clones")
        readme = root / "README.md"
        if readme.is_file() and norm_ws(README_DEFERRED_CLAIM) in norm_ws(read_text(readme)):
            report.bad("README.md", "0", "TEST_CANDIDATE_LAYOUT_DEFERRED",
                       f"README still claims {README_DEFERRED_CLAIM!r}; A15 ratifies the layout in the schema, so the deferral must be removed")
        report.ok("test-candidate-layout", "layout.md ratifies the committed test-candidate root, its classes, four attributes and .run-only ignore", mark)


# --- check 32: selfcheck-doc-parity -----------------------------------------


def invoked_check_names(source: str) -> list[str]:
    """Display names of every check main() invokes, derived from this file's AST.

    Maps each check_* function to the literal it passes to report.ok(), so the
    documentation is compared against what the harness actually runs rather
    than against a hand-maintained list.
    """
    tree = ast.parse(source)
    display: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("check_"):
            for sub in ast.walk(node):
                if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute) and sub.func.attr == "ok"
                        and sub.args and isinstance(sub.args[0], ast.Constant) and isinstance(sub.args[0].value, str)):
                    display.setdefault(node.name, sub.args[0].value)
                    break
    invoked: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name == "main":
            for sub in ast.walk(node):
                if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name) and sub.func.id.startswith("check_"):
                    if sub.func.id in display and display[sub.func.id] not in invoked:
                        invoked.append(display[sub.func.id])
    return invoked


def check_selfcheck_doc_parity(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/schema/selfcheck.md", "SELFCHECK_DOC_ABORT"):
        relpath = ".opencode/schema/selfcheck.md"
        path = root / relpath
        if not path.is_file():
            report.bad(relpath, "0", "SELFCHECK_DOC_MISSING", "the self-check contract document is absent; A17 requires it to list every invoked check")
            return
        try:
            source = Path(__file__).read_text(encoding="utf-8")
        except OSError as exc:
            report.bad("tools/selfcheck.py", "0", "SELFCHECK_DOC_UNREADABLE", f"cannot read this harness to derive its invoked checks: {exc}")
            return
        names = invoked_check_names(source)
        if not names:
            report.bad("tools/selfcheck.py", "main", "SELFCHECK_DOC_UNDERIVABLE",
                       "no invoked check display names could be derived from main()'s AST; the documentation cannot be compared against what runs")
            return
        text = read_text(path)
        flat = norm_ws(text)
        absent = [n for n in names if n not in text]
        if absent:
            report.bad(relpath, "Checks", "SELFCHECK_DOC_CHECK_ABSENT",
                       f"{len(absent)} of {len(names)} invoked check display name(s) are undocumented, first: {', '.join(absent[:8])}")
        low = flat.lower()
        if "five agents" in low:
            report.bad(relpath, "0", "SELFCHECK_DOC_AGENT_COUNT",
                       "the document still says 'five agents'; permissions are heterogeneous across exactly eight agents with one primary")
        if "eight agents" not in low:
            report.bad(relpath, "0", "SELFCHECK_DOC_AGENT_COUNT",
                       "the document does not state that there are exactly eight agents with one primary")
        if "honor system" not in low and "honor-system" not in low:
            report.bad(relpath, "0", "SELFCHECK_DOC_HONOR_SYSTEM",
                       "the document does not state the honor-system limitation: a green self-check proves structural and procedural necessity, not that agents invoked the validator, locks, CAS or review")
        report.ok("selfcheck-doc-parity", f"all {len(names)} AST-derived invoked check names are documented with the eight-agent and honor-system wording", mark)


# --- M4 check: validation-guidance-isolation --------------------------------
#
# B8. After M4 the tester loads `write-examples` and nothing else: the
# implementation procedure lives in `write-driver`, which hal-tester must never
# read. This check proves the tree the tester actually loads carries no
# implementation guidance - neither inline (register-poking prose) nor by
# reference (a relative link into write-driver/).
#
# Scope is the WHOLE write-examples Markdown tree, SKILL.md and every
# reference including references/profiles/, because the tester loads all of it.

# The tester-facing tree and the implementation tree are both DERIVED from
# parsed `emitter:` declarations, not from literal directory names. M5 gives
# hal-tester a second skill (debug-hardware) and hal-driver two more
# (write-clocks, write-dma); a literal write-examples/write-driver pair would
# have left all three unscanned.
TESTER_AGENT = "hal-tester"
IMPLEMENTATION_AGENT = "hal-driver"
PROFILE_SUBDIR = "references/profiles"

# Retained ONLY as fixture data for the analyzer self-test below, which is not
# a subject selector: the live scan derives its forbidden roots from
# IMPLEMENTATION_AGENT.
IMPLEMENTATION_SKILL_DIR = ".opencode/skills/write-driver"

# Deliberately NOT included: any `(private|internal)\s+(field|state|...)` rule.
# It matches the legitimate, load-bearing sentence "not the target HAL's
# implementation or private state" in the real validation references, so it
# would forbid the very disclaimer that makes a profile tester-safe.
IMPLEMENTATION_TOKENS: tuple[str, ...] = (
    r"pac::",
    r"unsafe\s*\{",
    r"embassy-[A-Za-z0-9_-]+/src/",
    r"(?:^|[\s`(])src/[A-Za-z0-9_./-]+\.rs\b",
    r"\bread_volatile\b",
    r"\bwrite_volatile\b",
    r"\.read\s*\(\s*\|",
    r"\.write\s*\(\s*\|",
    r"\.modify\s*\(\s*\|",
    r"\bOnDrop\b",
    r"\bWaitCell\b",
    # M6/E3 item 21 removed `enable_and_reset` from this set. It is one MCXA
    # helper NAME, not evidence of implementation leakage: a public target
    # lifecycle contract may legitimately use it, and a leaking one may use any
    # other name. The identical removal is required in selfcheck.md, which is
    # coder-owned.
    r"\bwaker\.register\b",
    r"\bregister_waker\b",
)

_IMPL_RE = tuple((p, re.compile(p, re.MULTILINE)) for p in IMPLEMENTATION_TOKENS)


def analyze_validation_guidance(relpath: str, text: str,
                                forbidden: tuple[str, ...] = (IMPLEMENTATION_SKILL_DIR,)) -> list[tuple[str, str]]:
    """Pure analyzer: [(code, message)] for implementation guidance in one file.

    Pure function of (repository-relative path, raw markdown, forbidden link
    roots) so the in-memory non-vacuity fixtures below can drive it without
    touching the filesystem. The live caller passes DERIVED forbidden roots.

    Two independent failure modes:
      (a) a relative Markdown link that RESOLVES beneath an implementation
          skill directory, and
      (b) prose matching the implementation token set.
    """
    out: list[tuple[str, str]] = []
    base = posixpath.dirname(relpath)
    for m in LINK_RE.finditer(text):
        target = m.group(1).split("#", 1)[0].strip()
        if not target or "://" in target or target.startswith("#"):
            continue
        if target.startswith("/"):
            resolved = posixpath.normpath(target.lstrip("/"))
        else:
            resolved = posixpath.normpath(posixpath.join(base, target))
        for root_dir in forbidden:
            if resolved == root_dir or resolved.startswith(root_dir + "/"):
                out.append((
                    "VALIDATION_GUIDANCE_LEAK",
                    f"link {target!r} resolves to {resolved!r}, beneath the implementation skill "
                    f"{root_dir!r}; hal-tester must never be routed into implementation guidance",
                ))
                break
    for lineno, line in enumerate(text.split("\n"), start=1):
        for pattern, rx in _IMPL_RE:
            if rx.search(line):
                out.append((
                    "VALIDATION_GUIDANCE_LEAK",
                    f"line {lineno} matches implementation token /{pattern}/: {line.strip()[:120]!r}; "
                    "tester-facing guidance describes observable behavior, not register access",
                ))
                break
    return out


_VALIDATION_NEAR_MISSES: tuple[tuple[str, str, str], ...] = (
    ("inline PAC path",
     ".opencode/skills/write-examples/references/profiles/x.md",
     "Use `pac::uart0::RegisterBlock` to derive the expected result.\n"),
    ("link into the implementation skill",
     ".opencode/skills/write-examples/references/x.md",
     "See the [implementation checklist](../../write-driver/references/driver-checklist.md).\n"),
    ("link into the implementation skill from a profile",
     ".opencode/skills/write-examples/references/profiles/x.md",
     "See the [implementation checklist](../../../write-driver/references/driver-checklist.md).\n"),
    ("unsafe block",
     ".opencode/skills/write-examples/SKILL.md",
     "Wrap the access in `unsafe { ... }` first.\n"),
    ("crate source path",
     ".opencode/skills/write-examples/SKILL.md",
     "Edit embassy-unobtainium/src/uart/mod.rs before running.\n"),
    ("waker registration",
     ".opencode/skills/write-examples/SKILL.md",
     "Call register_waker before checking the condition.\n"),
    ("drop guard",
     ".opencode/skills/write-examples/SKILL.md",
     "Guard the armed region with OnDrop and defuse on success.\n"),
)

_VALIDATION_SAFE = (
    "Observe the pin level through the public API and record the result.\n"
    "This describes observable behavior, not the target HAL's implementation or private state.\n"
    "See the [test record](test-record.md) for the evidence layout.\n"
)


def validation_analyzer_failures(root: Path) -> list[str]:
    """Self-test the analyzer. Empty when it discriminates; problems otherwise."""
    problems: list[str] = []
    clean = analyze_validation_guidance(
        ".opencode/skills/write-examples/references/profiles/x.md", _VALIDATION_SAFE)
    if clean:
        problems.append(
            f"the conforming in-memory profile was rejected with {[c for c, _ in clean]}; "
            "the analyzer rejects everything and proves nothing")
    for name, relpath, text in _VALIDATION_NEAR_MISSES:
        codes = [c for c, _ in analyze_validation_guidance(relpath, text)]
        if "VALIDATION_GUIDANCE_LEAK" not in codes:
            problems.append(f"near-miss {name!r} was not caught (got {codes or 'no findings'})")
    # The REAL tester-facing validation references must survive the token set.
    # These are the files whose content migrates into the scan target; if one
    # of them trips a token the check is unimplementable as specified and the
    # token set - not the prose - is what must change.
    for probe in (".opencode/skills/write-gpio/references/gpio-validation.md",
                  ".opencode/skills/write-time-driver/references/time-validation.md",
                  ".opencode/skills/write-examples/references/profiles/gpio-validation.md",
                  ".opencode/skills/write-examples/references/profiles/time-validation.md"):
        p = root / probe
        if not p.is_file():
            continue
        findings = analyze_validation_guidance(probe, read_text(p))
        if findings:
            problems.append(
                f"the real tester-facing reference {probe!r} trips the token set "
                f"({findings[0][1]}); the token set must be corrected, not the prose")
    return problems


def check_validation_guidance_isolation(root: Path, report: Report) -> None:
    """Every tester-loaded Markdown tree must be free of implementation guidance.

    Subject derivation: `skills_with_emitter(contracts, TESTER_AGENT)` - every
    discovered skill whose PARSED contract emitter is hal-tester. Forbidden
    link roots are `skills_with_emitter(contracts, IMPLEMENTATION_AGENT)`.
    Neither is a literal directory path, so M5's debug-hardware, write-clocks
    and write-dma are covered the moment they declare their emitter.
    """
    mark = report.mark()
    with guard(report, ".opencode/skills", "VALIDATION_GUIDANCE_ABORT"):
        for problem in validation_analyzer_failures(root):
            report.bad("tools/selfcheck.py", "analyze_validation_guidance",
                       "VALIDATION_GUIDANCE_FIXTURE",
                       f"the validation-guidance analyzer failed its in-memory fixtures: {problem}")
        paths = skill_paths(root)
        contracts = skill_contracts(root)
        tester_skills = [n for n in skills_with_emitter(contracts, TESTER_AGENT) if n in paths]
        impl_skills = [n for n in skills_with_emitter(contracts, IMPLEMENTATION_AGENT) if n in paths]
        if not tester_skills:
            report.bad(".opencode/skills", "0", "VALIDATION_GUIDANCE_NO_SCAN_ROOT",
                       f"no discovered skill declares 'emitter: {TESTER_AGENT}'; the isolation check has nothing to scan")
            return
        forbidden = tuple(rel(root, paths[n].parent) for n in impl_skills)
        if not forbidden:
            report.bad(".opencode/skills", "0", "VALIDATION_GUIDANCE_NO_FORBIDDEN_ROOT",
                       f"no discovered skill declares 'emitter: {IMPLEMENTATION_AGENT}'; the link arm of the "
                       "isolation check would forbid nothing and pass vacuously")
            return
        files: list[Path] = []
        profiles: list[Path] = []
        for name in tester_skills:
            scan_dir = paths[name].parent
            files.extend(sorted(p for p in scan_dir.rglob("*.md") if p.is_file()))
            pdir = scan_dir / PROFILE_SUBDIR
            if pdir.is_dir():
                profiles.extend(sorted(p for p in pdir.rglob("*.md") if p.is_file()))
        if not files:
            report.bad(".opencode/skills", "0", "VALIDATION_GUIDANCE_NO_TARGETS",
                       "no Markdown found under any tester-facing skill tree; a scanner with no targets must not pass vacuously")
            return
        # A tester-safe validation profile must actually exist somewhere in the
        # tester-loaded trees. Without one the scan is technically green and
        # substantively meaningless: it would be asserting that guidance that
        # does not exist contains no leak.
        if not profiles:
            report.bad(".opencode/skills", "0", "VALIDATION_GUIDANCE_NO_PROFILE",
                       f"no tester-safe validation profile exists under any <tester-skill>/{PROFILE_SUBDIR}; "
                       "hal-tester has nothing to load in place of the implementation skill, so the "
                       "isolation guarantee is vacuous")
        for p in files:
            r = rel(root, p)
            for code, message in analyze_validation_guidance(r, read_text(p), forbidden):
                report.bad(r, "0", code, message)
        report.ok("validation-guidance-isolation",
                  f"{len(files)} tester-facing Markdown files across {len(tester_skills)} hal-tester-emitted skill(s) "
                  f"({len(profiles)} validation profiles) carry no implementation guidance under "
                  f"{len(IMPLEMENTATION_TOKENS)} tokens and no link into {len(forbidden)} hal-driver-emitted skill tree(s) "
                  f"(analyzer self-tested against {len(_VALIDATION_NEAR_MISSES)} near-misses)",
                  mark)


# --- M5 check: skill-platform-slices ----------------------------------------
#
# G5. The platform stage becomes an ORDERED chain of partial slices followed by
# one final consolidator. Four independent writers of the singleton
# 05-platform.toml could otherwise each erase the previous slice, so the
# discipline has to be asserted: a non-final slice publishes only `partial`,
# performs no canonical placement, obtains no review, and consumes the
# immutable snapshot of its predecessor rather than restarting from the PAC.

PAC_KIND = "04-pac"
PLATFORM_KIND = "05-platform"
LINKER_CLASS = "linker"

COMPOSITE_EVIDENCE_MARKER = "composite evidence"
CANONICAL_PLACEMENT_MARKER = "canonical placement"
CANDIDATE_ONLY_MARKER = "candidate-only"
# Generic role noun for the final consolidator. Not a skill name: it is the
# English word for the parsed role that `platform_roles()` computes, so it
# stays correct when the consolidating skill is renamed or replaced.
CONSOLIDATOR_ROLE_TOKEN = "consolidator"
# OPERATIVE SURFACES. Sections in which a statement is an instruction to act:
# a '## Procedure' step tells the agent what to do, a '## Validation' row tells
# it how a check is discharged. The composite-evidence marker is banned here
# outright, whatever words surround it.
#
# WHY STRUCTURAL, AND WHY THE NEGATION ANALYSIS IS GONE. Three review rounds
# were spent trying to tell "claims X" from "disclaims X" in free prose, and
# each round a reviewer found another wording that got through:
#
#   1. "creates composite evidence and does not alter the status"
#      - bare substring "not " read as a disclaimer.
#   2. "creates composite evidence; no unrelated file is touched"
#      - bare substring "no " read as a disclaimer.
#   3. "creates composite evidence, which it does not publish."
#      - clause-final negated verb read as governing the marker, though the
#        sentence positively claims CREATION.
#   4. "| This slice creates | composite evidence | no unrelated file is touched |"
#      - any negation in any other table cell accepted, whatever it governed.
#
# Every one of those is fail-OPEN in an exclusivity guard. English negation
# scope is not decidable by a token-window heuristic, so the heuristic is
# deleted rather than tuned a fourth time. What replaces it cannot be reworded
# around: on an operative surface the marker is forbidden, full stop, and
# elsewhere it must carry attribution.
OPERATIVE_SECTIONS = ("Procedure", "Validation")

NEGATED_PLACEMENT = (
    "no canonical placement",
    "without canonical placement",
    "not perform canonical placement",
    "never perform canonical placement",
)


def prose_units(text: str) -> list[str]:
    """Split Markdown into sentence-sized attribution units.

    A unit is the span a reader would judge a claim in. Markdown table rows are
    kept whole (a row's cells are one assertion and carry no sentence
    terminator), headings and list-item markers start a new unit so a
    neighbouring bullet's attribution cannot leak into this one, and ordinary
    paragraph text is joined across soft line breaks then split on sentence
    terminators.
    """
    segments: list[str] = []
    buf: list[str] = []

    def flush() -> None:
        if buf:
            segments.append(" ".join(buf))
            buf.clear()

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            flush()
            continue
        if line.startswith("|") or line.startswith("#"):
            flush()
            segments.append(line)
            continue
        if re.match(r"^(?:[-*+]\s|\d+[.)]\s)", line):
            flush()
        buf.append(line)
    flush()

    units: list[str] = []
    for segment in segments:
        if segment.startswith("|"):
            units.append(segment)
            continue
        units.extend(part for part in re.split(r"(?<=[.!?])\s+", segment) if part.strip())
    return units


def _writes_class(cmap: dict[str, list[str]], cid: str) -> bool:
    return any(v.count("|") == 1 and v.split("|")[1] == cid for v in cmap.get("writes", []))


def _composite_flat(unit: str) -> str:
    """Lowercased unit with Markdown emphasis removed as well as backticks.

    `norm_ws` strips backticks but not `*` / `_`, so "composite *evidence*"
    slipped past the marker match while reading identically to a human. The
    emphasis characters are dropped here rather than in `norm_ws`, which is
    shared by exact-sentence assertions that must keep seeing the raw text.
    """
    return norm_ws(unit).replace("*", "").replace("_", "").lower()


def operative_composite_statements(text: str) -> list[tuple[str, str]]:
    """(section, unit) for every marker statement on an OPERATIVE surface.

    The whole body of each `OPERATIVE_SECTIONS` heading counts, not only its
    numbered steps or table rows: a lead-in paragraph to a procedure is as much
    an instruction as the steps it introduces, and restricting the ban to the
    numbered lines would leave that paragraph as a one-line bypass.

    No attribution and no disclaimer is accepted here. That is the point: a
    non-final slice's procedure has no legitimate reason to put the phrase in
    an instruction, because the instruction it can legitimately give is
    "return to the consolidator", which needs no mention of what the
    consolidator then builds. Boundary prose belongs in the sections that
    describe boundaries.
    """
    out: list[tuple[str, str]] = []
    for heading, body, _ in h2_sections(text):
        if heading not in OPERATIVE_SECTIONS:
            continue
        for unit in prose_units(body):
            if COMPOSITE_EVIDENCE_MARKER in _composite_flat(unit):
                out.append((heading, _one_line(unit, 160)))
    return out


def unattributed_composite_claims(text: str, consolidators: list[str]) -> list[str]:
    """Units OUTSIDE the operative sections that state the marker unattributed.

    Absence of the phrase was the original rule, and it was the wrong one: it
    pushed a slice author into vaguer prose that no longer names what the slice
    is declining to do. So outside the operative surfaces the phrase stays
    legal, on one condition - the unit must say whose work it is:

      * the final consolidator BY NAME. The names come from
        `platform_roles(...)[1]`, i.e. the platform-stage skill whose own ready
        predicate is reachable, never from a literal written here; or
      * the consolidating ROLE noun.

    There is no longer a disclaimer arm. A free negation was what four separate
    bypasses exploited, and "no composite evidence is created here" carries no
    information that "composite evidence belongs to the final consolidator"
    does not carry better - the second says where it went.

    Operative-section units are excluded because they are reported, more
    severely and unconditionally, by `operative_composite_statements`.
    """
    tokens = [n.lower() for n in consolidators] + [CONSOLIDATOR_ROLE_TOKEN]
    operative = {u for _, u in operative_composite_statements(text)}
    offenders: list[str] = []
    for unit in prose_units(text):
        flat = _composite_flat(unit)
        if COMPOSITE_EVIDENCE_MARKER not in flat:
            continue
        if any(t in flat for t in tokens):
            continue
        if _one_line(unit, 160) in operative:
            continue
        offenders.append(_one_line(unit, 160))
    return offenders


_COMPOSITE_CONSOLIDATORS = ["omega-consolidate"]


def _doc(section: str, body: str) -> str:
    """A minimal skill document with `body` under one '## <section>' heading."""
    return f"# s\n\n## When to use\n\nIrrelevant preamble.\n\n## {section}\n\n{body}\n"


# Documents whose marker sits on an OPERATIVE surface. Every one must yield an
# operative finding, whatever the surrounding words claim or disclaim.
_COMPOSITE_OPERATIVE: tuple[tuple[str, str], ...] = (
    ("bare claim in a procedure step",
     _doc("Procedure", "12. **Publish.** Create the composite evidence, then publish the handoff.")),
    ("bare claim in a procedure lead-in paragraph",
     _doc("Procedure", "This slice creates composite evidence for all ten canonical checks.")),
    ("claim in a validation table row",
     _doc("Validation", "| Done here | composite evidence, independent review |")),
    ("attribution stranded in a neighbouring procedure bullet",
     _doc("Procedure",
          "- The final consolidator owns the whole platform.\n"
          "- This step assembles composite evidence over every slice-local log.")),
    # --- BYPASS 1 (round one): unrelated negated verb ------------------------
    ("BYPASS claim laundered by an unrelated negated verb",
     _doc("Procedure", "9. **Log.** This slice creates composite evidence and does not alter the status.")),
    # --- BYPASS 2 (round one): negation of a different noun phrase -----------
    ("BYPASS claim laundered by a negation of a different noun phrase",
     _doc("Procedure", "9. **Log.** This slice creates composite evidence; no unrelated file is touched.")),
    # --- BYPASS 3 (round two): clause-final negated verb --------------------
    ("BYPASS claim laundered by a clause-final negated verb",
     _doc("Procedure", "9. **Log.** This slice creates composite evidence, which it does not publish.")),
    # --- BYPASS 4 (round two): negation in an unrelated table cell ----------
    ("BYPASS claim laundered by a negation in a sibling table cell",
     _doc("Validation", "| This slice creates | composite evidence | no unrelated file is touched |")),
    # --- my own bypass attempt against the structural rule ------------------
    # Markdown emphasis inside the marker reads identically to a human and
    # broke the substring match, until `_composite_flat` dropped `*` and `_`.
    ("marker split by Markdown emphasis",
     _doc("Procedure", "9. **Do.** This slice creates composite *evidence* for all ten checks.")),
    ("marker inside a fenced block in a procedure step",
     _doc("Procedure", "9. **Do.**\n\n```\nthis slice creates composite evidence\n```")),
    # The ban is UNCONDITIONAL on these surfaces. Attribution and disclaimer
    # are both still findings here - that is what makes the rule immune to
    # rewording, and it is the load-bearing case of the whole design.
    ("correctly attributed sentence, but placed in a procedure step",
     _doc("Procedure",
          "13. **Return.** Return the logs to `omega-consolidate`, which alone creates the composite evidence.")),
    ("explicit disclaimer, but placed in a procedure step",
     _doc("Procedure", "13. **Return.** Do not create composite evidence and do not request review.")),
    ("explicit disclaimer, but placed in a validation row",
     _doc("Validation", "| Never done here | composite evidence, canonical placement |")),
)

# Documents whose marker sits in a PERMITTED section with no attribution. Each
# must yield an unattributed-claim finding and NO operative finding.
_COMPOSITE_UNATTRIBUTED: tuple[tuple[str, str], ...] = (
    ("unattributed claim in Ownership and boundaries",
     _doc("Ownership and boundaries", "This slice creates composite evidence for all ten checks.")),
    ("free negation is no longer a disclaimer",
     _doc("Common mistakes",
          "- The `ready` platform asserts composite evidence that this slice never held.")),
    ("negated list item with no owner named",
     _doc("Exit criteria", "No canonical placement and no composite evidence was performed.")),
    ("table label cell with no owner named",
     _doc("Quick reference", "| Never done here | composite evidence, independent review |")),
)

# Documents that must PASS: the phrase is named in a permitted section AND the
# unit says whose work it is. One per permitted section named in the design.
_COMPOSITE_PERMITTED: tuple[tuple[str, str], ...] = (
    ("attributed by consolidator name in Ownership and boundaries",
     _doc("Ownership and boundaries",
          "Only the final skill, `omega-consolidate`, creates composite evidence for all ten checks.")),
    ("attributed by role in Exit criteria",
     _doc("Exit criteria",
          "Unreachable here: only the final consolidator creates the composite evidence.")),
    ("attributed by role in Common mistakes",
     _doc("Common mistakes",
          "- **Creating it early.** Composite evidence over all ten checks is the consolidator's job.")),
    ("attributed by role in a Quick reference table row",
     _doc("Quick reference", "| Reserved to the consolidator | composite evidence, `ready` |")),
    ("attributed by role in When to use",
     _doc("When to use", "Only that consolidator creates composite evidence and obtains the review.")),
    ("no marker at all is trivially clean",
     _doc("Procedure", "13. **Return.** Return the logs and publish the partial handoff.")),
)


def composite_analyzer_failures() -> list[str]:
    """Self-test the structural pair. Empty when it discriminates."""
    problems: list[str] = []
    for name, text in _COMPOSITE_OPERATIVE:
        if not operative_composite_statements(text):
            problems.append(
                f"composite OPERATIVE case {name!r} was not caught; the marker is stated in an instruction "
                "to act, which is a claim regardless of the surrounding words")
    for name, text in _COMPOSITE_UNATTRIBUTED:
        if operative_composite_statements(text):
            problems.append(f"composite case {name!r} was reported as operative, but its section is not operative")
        if not unattributed_composite_claims(text, _COMPOSITE_CONSOLIDATORS):
            problems.append(
                f"composite UNATTRIBUTED case {name!r} was not caught; outside the operative sections the "
                "mention must still name the consolidator or the consolidating role")
    for name, text in _COMPOSITE_PERMITTED:
        operative = operative_composite_statements(text)
        offenders = unattributed_composite_claims(text, _COMPOSITE_CONSOLIDATORS)
        if operative or offenders:
            detail = operative[0] if operative else offenders[0]
            problems.append(
                f"composite PERMITTED case {name!r} was rejected ({detail!r}); a permitted section may name "
                "the phrase when it says whose work it is")
    return problems


def check_skill_platform_slices(root: Path, report: Report) -> None:
    """Subject derivation: parsed stage + parsed ready-predicate role.

    `platform_roles()` returns (non-final slices, final consolidators) from
    `skills_at_stage(contracts, PLATFORM_STAGE)` narrowed by whether the
    skill's own '### ready' predicate declares ready unreachable. The
    runtime/linker slice is identified by its declared `writes: <agent>|linker`
    ownership class. No literal skill name appears anywhere in this check.
    """
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_PLATFORM_ABORT"):
        paths = skill_paths(root)
        contracts = skill_contracts(root)
        for problem in composite_analyzer_failures():
            report.bad(".opencode/skills", "0", "SKILL_PLATFORM_ANALYZER_UNSOUND", problem)
        slices, final = platform_roles(root, contracts)
        if not slices:
            report.bad(".opencode/skills", "0", "SKILL_PLATFORM_NO_SLICES",
                       f"no discovered skill at stage {PLATFORM_STAGE!r} declares an unreachable ready exit; "
                       "the ordered partial platform-slice chain is asserted against nothing")
            return
        if len(final) != 1:
            report.bad(".opencode/skills", "0", "SKILL_PLATFORM_CONSOLIDATOR_COUNT",
                       f"{len(final)} platform skill(s) declare a reachable ready exit ({', '.join(final) or 'none'}); "
                       "exactly one final consolidator may publish a ready platform")

        # The consolidator, and only the consolidator, carries the final
        # composite-evidence / review / canonical-placement responsibilities.
        for name in final:
            r = rel(root, paths[name])
            flat = norm_ws(read_text(paths[name])).lower()
            if COMPOSITE_EVIDENCE_MARKER not in flat:
                report.bad(r, "Procedure", "SKILL_PLATFORM_NO_COMPOSITE",
                           f"the final platform consolidator never states {COMPOSITE_EVIDENCE_MARKER!r}; "
                           "slice-local evidence does not attest the complete platform, so fresh composite "
                           "evidence for every canonical check is what the ready handoff rests on")
            if CANONICAL_PLACEMENT_MARKER not in flat:
                report.bad(r, "Procedure", "SKILL_PLATFORM_NO_PLACEMENT",
                           f"the final platform consolidator never states {CANONICAL_PLACEMENT_MARKER!r}; "
                           "it is the sole skill that may move a canonical byte")
            if norm_ws(VERDICT_SENTENCE) not in norm_ws(read_text(paths[name])):
                report.bad(r, "0", "SKILL_PLATFORM_NO_REVIEW_GATE",
                           f"the final platform consolidator does not state the exact accepting sentence {VERDICT_SENTENCE!r}")

        first: list[str] = []
        for name in slices:
            r = rel(root, paths[name])
            text = read_text(paths[name])
            flat = norm_ws(text).lower()
            cmap = contracts.get(name, {})
            kinds = consumed_kinds(cmap)

            ready = exit_predicate(text, "ready") or ""
            if SLICE_UNREACHABLE_TOKEN not in ready.lower():
                # Unreachable by construction of platform_roles(); kept so the
                # assertion is stated where a reader looks for it.
                report.bad(r, "Exit criteria", "SKILL_PLATFORM_READY_REACHABLE",
                           "a non-final platform slice must declare its ready exit unreachable")
            proc = h2_body(text, "Procedure")
            if proc is None or "partial" not in proc.lower():
                report.bad(r, "Procedure", "SKILL_PLATFORM_NO_PARTIAL",
                           "the procedure never names the 'partial' status it must publish; a non-final slice "
                           "publishes only a partial 05-platform and returns to the consolidator")
            for section, unit in operative_composite_statements(text):
                report.bad(r, section, "SKILL_PLATFORM_OPERATIVE_COMPOSITE",
                           f"a non-final platform slice states {COMPOSITE_EVIDENCE_MARKER!r} in its "
                           f"'## {section}' section, where a statement is an instruction to act: {unit!r}. "
                           "On that surface the phrase is a claim whatever surrounds it - attribution and "
                           "disclaimer alike - because four separate rewordings have already defeated the "
                           "attempt to read English negation scope. Move the sentence to a section that "
                           "describes boundaries ('Ownership and boundaries', 'Exit criteria', 'Common "
                           "mistakes', 'Quick reference') and attribute it there")
            offenders = unattributed_composite_claims(text, final)
            if offenders:
                report.bad(r, "0", "SKILL_PLATFORM_SLICE_COMPOSITE",
                           f"a non-final platform slice states {COMPOSITE_EVIDENCE_MARKER!r} outside its "
                           f"operative sections without naming whose work it is: {offenders[0]!r}; name the "
                           "final platform consolidator or the consolidating role. A negation is no longer "
                           "accepted as a disclaimer")

            if PAC_KIND in kinds and PLATFORM_KIND in kinds:
                report.bad(r, "consumes", "SKILL_PLATFORM_CHAIN",
                           f"slice consumes both {PAC_KIND!r} and {PLATFORM_KIND!r}; the first slice starts from the "
                           "PAC and every later slice consumes the immutable predecessor snapshot, never both")
            elif PAC_KIND in kinds:
                first.append(name)
            elif PLATFORM_KIND not in kinds:
                report.bad(r, "consumes", "SKILL_PLATFORM_CHAIN",
                           f"slice consumes {sorted(kinds) or 'nothing'}; a platform slice consumes either "
                           f"{PAC_KIND!r} (first slice) or {PLATFORM_KIND!r} (every later slice)")

            if _writes_class(cmap, LINKER_CLASS):
                if CANDIDATE_ONLY_MARKER not in flat:
                    report.bad(r, "Procedure", "SKILL_PLATFORM_NOT_CANDIDATE_ONLY",
                               f"the runtime/linker slice (declared by 'writes: <agent>|{LINKER_CLASS}') never states "
                               f"{CANDIDATE_ONLY_MARKER!r}; its linker and runtime wiring stays inside the "
                               "integration candidate until the consolidator places it")
                if not any(p in flat for p in NEGATED_PLACEMENT):
                    report.bad(r, "Procedure", "SKILL_PLATFORM_SLICE_PLACEMENT",
                               f"the runtime/linker slice does not state any of {list(NEGATED_PLACEMENT)}; it must "
                               "explicitly disclaim independent canonical placement")

        if len(first) != 1:
            report.bad(".opencode/skills", "0", "SKILL_PLATFORM_FIRST_SLICE",
                       f"{len(first)} platform slice(s) consume {PAC_KIND!r} ({', '.join(first) or 'none'}); exactly "
                       "one first slice starts the chain from the PAC")
        report.ok("skill-platform-slices",
                  f"{len(slices)} non-final platform slice(s) publish only partial, start once from {PAC_KIND} and "
                  f"otherwise consume the {PLATFORM_KIND} snapshot, state {COMPOSITE_EVIDENCE_MARKER!r} nowhere in "
                  f"their {' / '.join(OPERATIVE_SECTIONS)} sections and nowhere else without naming the "
                  f"consolidator or the consolidating role, and {len(final)} final consolidator carries "
                  "composite evidence, review and canonical placement. The marker rule is a BOUNDED STRUCTURAL "
                  "TRIPWIRE over section placement and attribution, not a proof of exclusivity. Two residual "
                  "bypasses are known and accepted: it reads ONE literal phrase, so a slice describing the same "
                  "work in other words is invisible to it; and outside the operative sections the attribution "
                  "test is co-occurrence, so a unit that names the role while still claiming the work passes. "
                  "Exclusivity itself is carried by the unreachable-ready, review-gate and consolidator-count "
                  "assertions above, and by human review "
                  f"(analyzer self-tested against {len(_COMPOSITE_OPERATIVE)} operative cases, "
                  f"{len(_COMPOSITE_UNATTRIBUTED)} unattributed cases and {len(_COMPOSITE_PERMITTED)} permitted cases)", mark)


# --- M5 check: debug-lineage ------------------------------------------------
#
# G6. A debugging test run must never overwrite the failure it is
# investigating. 07 filenames are name-derived and repeatable
# (validate.py SINGLETON_KINDS), so nothing in the schema stops a debug run
# from reusing the original name; the discipline is procedural and is asserted
# here.

TESTS_KIND = "07-tests"
DRIVER_KIND = "06-driver"
DRIVER_FILE_PREFIX = "06-driver-"
TESTS_FILE_RE = re.compile(r"halucinator/handoff/07-tests-(.+)\.toml$")


def check_debug_lineage(root: Path, report: Report) -> None:
    """Subject derivation: skills that both EMIT and CONSUME the tests kind.

    `[n for n in skills_emitting_kind(contracts, TESTS_KIND)
        if TESTS_KIND in consumed_kinds(contracts[n])]` - parsed `emits:` and
    parsed `consumes:` only. The ordinary example producer emits 07 without
    consuming one and is therefore not a subject.
    """
    mark = report.mark()
    with guard(report, ".opencode/skills", "DEBUG_LINEAGE_ABORT"):
        paths = skill_paths(root)
        contracts = skill_contracts(root)
        emitters = [n for n in skills_emitting_kind(contracts, TESTS_KIND) if n in paths]
        subjects = [n for n in emitters if TESTS_KIND in consumed_kinds(contracts[n])]
        if not subjects:
            report.bad(".opencode/skills", "0", "DEBUG_LINEAGE_NO_TARGETS",
                       f"no discovered skill both emits and consumes {TESTS_KIND!r}; the distinct-output debugging "
                       "lineage is asserted against nothing")
            return
        for name in subjects:
            r = rel(root, paths[name])
            text = read_text(paths[name])
            mine = emitted_filename(contracts[name])
            if not mine:
                report.bad(r, "emits", "DEBUG_LINEAGE_NO_FILENAME",
                           "no parseable deterministic filename in the 'emits:' declaration")
                continue
            for other in emitters:
                if other == name:
                    continue
                theirs = emitted_filename(contracts[other])
                if theirs is not None and theirs == mine:
                    report.bad(r, "emits", "DEBUG_LINEAGE_SELF_REPLACEMENT",
                               f"the debug output filename template {mine!r} equals the template emitted by "
                               f"{other!r}; a debug run must publish a distinct name and never replace the "
                               "failing original it pins")
            proc = (h2_body(text, "Procedure") or "").lower()
            if "distinct" not in proc:
                report.bad(r, "Procedure", "DEBUG_LINEAGE_NO_DISTINCT_STEP",
                           "the procedure never requires a distinct debug name; selecting a fresh name is the "
                           "step that preserves the original failing handoff")
            if "differ" not in proc and "no matching file" not in proc:
                report.bad(r, "Procedure", "DEBUG_LINEAGE_NO_DISTINCT_STEP",
                           "the procedure never requires the chosen name to differ from the consumed one, so "
                           "in-place replacement is not actually forbidden")
            # The worked example must show a real, non-self-replacing lineage.
            docs: list[dict] = []
            for block in fenced_blocks(h2_body(text, "Application example") or "", "toml"):
                if len(block.encode("utf-8", "replace")) > MAX_TOML_EXAMPLE_BYTES:
                    continue
                try:
                    docs.append(tomllib.loads(block))
                except (tomllib.TOMLDecodeError, ValueError):
                    continue
            shown = [d for d in docs if isinstance(d.get("tests"), dict)]
            if not shown:
                report.bad(r, "Application example", "DEBUG_LINEAGE_NO_EXAMPLE",
                           "no parseable typed example showing a [tests] table, so the distinct lineage is "
                           "demonstrated nowhere")
                continue
            for doc in shown:
                tests = doc["tests"]
                own = tests.get("name")
                inputs = doc.get("handoff", {}).get("inputs", []) if isinstance(doc.get("handoff"), dict) else []
                sources = []
                for ref in inputs if isinstance(inputs, list) else []:
                    if not isinstance(ref, dict):
                        continue
                    m = TESTS_FILE_RE.search(str(ref.get("path", "")))
                    if m:
                        sources.append(m.group(1))
                if not sources:
                    report.bad(r, "Application example", "DEBUG_LINEAGE_NO_SOURCE_PIN",
                               f"the example's handoff.inputs pins no {TESTS_KIND} handoff; the failing original "
                               "must remain pinned, not merely referenced in prose")
                for src in sources:
                    if src == own:
                        report.bad(r, "Application example", "DEBUG_LINEAGE_SELF_REPLACEMENT",
                                   f"the example emits tests.name {own!r} while pinning the identically named "
                                   f"{TESTS_KIND} input; the debug run would overwrite the failure it consumed")
                api = tests.get("api_handoff")
                api_path = str(api.get("path", "")) if isinstance(api, dict) else ""
                if not api_path.rsplit("/", 1)[-1].startswith(DRIVER_FILE_PREFIX):
                    report.bad(r, "Application example", "DEBUG_LINEAGE_API_HANDOFF",
                               f"tests.api_handoff names {api_path or '(nothing)'!r}; it binds by path to the exact "
                               f"{DRIVER_KIND} handoff whose public API the debug run exercises")
        report.ok("debug-lineage",
                  f"{len(subjects)} of {len(emitters)} {TESTS_KIND} emitter(s) consume a {TESTS_KIND} handoff and "
                  "publish a distinct debug name that pins, never replaces, the failing original", mark)



# --- M5 check: skill-subject-derivation -------------------------------------
#
# G3. M4 shipped a defect its own review caught: SKILL_REVIEW_GATED was a
# hard-coded tuple that omitted write-driver, so that skill's declared review
# gate asserted nothing. M5 adds seven skills - seven more chances to repeat
# it. This check reads THIS FILE's AST and rejects the four shapes by which a
# check can quietly narrow its own subject set to a literal:
#
#   1. literal skill-name comparison      name == "scaffold-hal"
#   2. literal skill-name collection      M4_SKILLS = (...) used for equality
#   3. literal skill-directory scan root  root / ".opencode/skills/write-examples"
#   4. mapping-key membership             if n in SKILL_NOTE_PATHS
#
# SCOPE, stated honestly because an overclaimed guard is worse than a narrow
# one: this catches the four AST forms above and nothing else. It is a
# regression guard over the shapes that have actually occurred, NOT a proof
# that every check derives its subjects. It does not see, and will not flag:
#
#   * selection hidden inside a helper the check calls, since only `check_*`
#     bodies are walked;
#   * a name assembled component-wise ("write-" + "driver") or reached through
#     an alias bound to a name collection;
#   * `.keys()` / `.values()` membership, `startswith`/`endswith` predicates,
#     regex matches, or any other comparison that is not `==`/`in` against a
#     recognised literal;
#   * a literal that is not a KNOWN skill name at audit time.
#
# An expectation mapping keyed by skill name stays legal when the lookup
# happens AFTER the discovered subject is selected and the mapping does not
# filter applicability - i.e. subscript and .get() are fine, membership tests,
# iteration and set/sorted() coercion are not.

SKILL_DIR_PREFIX = ".opencode/skills/"
COLLECTION_COERCIONS = ("sorted", "set", "frozenset", "list", "tuple", "any", "all")
# One literal skill name in a collection is enough. A single-name tuple used
# for filtering is the most plausible regression - it is what a hurried
# "just this one skill" exception looks like - and it is exactly the M4 defect
# with one element instead of six.
_MIN_LITERAL_NAMES = 1


def known_skill_names(root: Path) -> set[str]:
    """Discovered plus canonically mapped skill names.

    Deliberately not a `check_*` function: it is the guard's own input, and the
    guard only scans `check_*` bodies.
    """
    return set(skill_paths(root)) | set(SKILL_SPEC)


def _str_const(node: ast.AST) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_strings(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.Tuple, ast.List, ast.Set)):
        return [s for s in (_str_const(e) for e in node.elts) if s is not None]
    if isinstance(node, ast.Dict):
        return [s for s in (_str_const(k) for k in node.keys if k is not None) if s is not None]
    return []


def analyze_subject_derivation(source: str, names: set[str],
                               exempt: tuple[str, ...] = ()) -> list[tuple[str, str, str]]:
    """Pure analyzer: [(function, code, message)] for literal subject selection.

    Pure function of (python source, known skill names, exempt functions) so
    the in-memory near-miss fixtures below drive it without touching the
    filesystem.
    """
    out: list[tuple[str, str, str]] = []
    tree = ast.parse(source)

    # Module-level constants whose literal content is skill names, and
    # constants that are literal skill-directory paths.
    name_collections: dict[str, str] = {}   # const -> "collection" | "mapping"
    dir_consts: dict[str, str] = {}
    for node in tree.body:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        value = node.value
        if value is None:
            continue
        for t in targets:
            if not isinstance(t, ast.Name):
                continue
            literal = _literal_strings(value)
            if len([s for s in literal if s in names]) >= _MIN_LITERAL_NAMES:
                name_collections[t.id] = "mapping" if isinstance(value, ast.Dict) else "collection"
            s = _str_const(value)
            if s is not None and s.startswith(SKILL_DIR_PREFIX):
                tail = s[len(SKILL_DIR_PREFIX):].split("/")[0]
                if tail in names:
                    dir_consts[t.id] = s

    def flag(fn: str, code: str, message: str) -> None:
        out.append((fn, code, message))

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.name.startswith("check_") or node.name in exempt:
            continue
        fn = node.name
        for sub in ast.walk(node):
            # 1. literal skill-name comparison
            if isinstance(sub, ast.Compare):
                operands = [sub.left] + list(sub.comparators)
                for operand in operands:
                    s = _str_const(operand)
                    if s is not None and s in names:
                        flag(fn, "SKILL_SUBJECT_LITERAL_NAME",
                             f"compares against the literal skill name {s!r}; subjects must be derived from "
                             "skill_paths()/parsed contract fields, never from a name written into the harness")
                # 4. mapping-key / collection membership used for selection
                for op, comparator in zip(sub.ops, sub.comparators):
                    if not isinstance(op, (ast.In, ast.NotIn)):
                        continue
                    if isinstance(comparator, ast.Name) and comparator.id in name_collections:
                        kind = name_collections[comparator.id]
                        code = ("SKILL_SUBJECT_MAPPING_KEYS" if kind == "mapping"
                                else "SKILL_SUBJECT_LITERAL_COLLECTION")
                        flag(fn, code,
                             f"tests membership in {comparator.id!r}, whose {'keys' if kind == 'mapping' else 'elements'} "
                             "are literal skill names; that makes the literal the subject filter. Select the subject "
                             "from discovery first, then look the expectation up")
                    elif len([s for s in _literal_strings(comparator) if s in names]) >= _MIN_LITERAL_NAMES:
                        flag(fn, "SKILL_SUBJECT_LITERAL_COLLECTION",
                             "tests membership in an inline literal collection of skill names")
                # 2. literal-collection equality
                for operand in operands:
                    if isinstance(operand, ast.Name) and name_collections.get(operand.id) == "collection":
                        flag(fn, "SKILL_SUBJECT_LITERAL_COLLECTION",
                             f"compares against {operand.id!r}, a literal collection of skill names; a new skill "
                             "would have to be hand-added to it, which is exactly how a declared gate comes to "
                             "assert nothing")
            # 2. literal collection iterated or coerced
            if isinstance(sub, (ast.For, ast.comprehension)):
                it = sub.iter
                if isinstance(it, ast.Name) and it.id in name_collections:
                    flag(fn, "SKILL_SUBJECT_LITERAL_COLLECTION",
                         f"iterates {it.id!r}, a literal collection of skill names, to produce subjects")
                elif len([s for s in _literal_strings(it) if s in names]) >= _MIN_LITERAL_NAMES:
                    flag(fn, "SKILL_SUBJECT_LITERAL_COLLECTION",
                         "iterates an inline literal collection of skill names to produce subjects")
            if isinstance(sub, ast.Call):
                if isinstance(sub.func, ast.Name) and sub.func.id in COLLECTION_COERCIONS:
                    for arg in sub.args:
                        if isinstance(arg, ast.Name) and arg.id in name_collections:
                            flag(fn, "SKILL_SUBJECT_LITERAL_COLLECTION",
                                 f"coerces {arg.id!r} with {sub.func.id}(); a literal skill-name collection must "
                                 "not become a subject set")
                # 3. literal skill-directory scan root
                if isinstance(sub.func, ast.Attribute) and sub.func.attr in ("glob", "rglob"):
                    base = sub.func.value
                    if isinstance(base, ast.Name) and base.id in dir_consts:
                        flag(fn, "SKILL_SUBJECT_LITERAL_PATH",
                             f"scans {dir_consts[base.id]!r}, a literal skill directory")
            # 3. literal skill-directory joined onto a root path
            if isinstance(sub, ast.BinOp) and isinstance(sub.op, ast.Div):
                for operand in (sub.left, sub.right):
                    if isinstance(operand, ast.Name) and operand.id in dir_consts:
                        flag(fn, "SKILL_SUBJECT_LITERAL_PATH",
                             f"joins the literal skill directory {dir_consts[operand.id]!r} onto a path; the tree to "
                             "scan must be derived from a parsed contract field, not from a directory name")
                    s = _str_const(operand)
                    if s is not None and s.startswith(SKILL_DIR_PREFIX) \
                            and s[len(SKILL_DIR_PREFIX):].split("/")[0] in names:
                        flag(fn, "SKILL_SUBJECT_LITERAL_PATH",
                             f"joins the literal skill directory {s!r} onto a path")
    # Deduplicate: one finding per (function, code, message).
    seen: set[tuple[str, str, str]] = set()
    unique: list[tuple[str, str, str]] = []
    for item in out:
        if item not in seen:
            seen.add(item)
            unique.append(item)
    return unique


_SUBJECT_NAMES = {"alpha-skill", "beta-skill"}

_SUBJECT_GOOD = '''
EXPECT = {"alpha-skill": "a", "beta-skill": "b"}

def check_good(root, report):
    for name in sorted(skill_paths(root)):
        want = EXPECT.get(name)
        if want is not None:
            report.ok(name, want)
'''

_SUBJECT_CASES: tuple[tuple[str, str, str], ...] = (
    ("literal name comparison",
     'def check_x(root, report):\n'
     '    for name in sorted(skill_paths(root)):\n'
     '        if name == "alpha-skill":\n'
     '            report.ok(name, "x")\n',
     "SKILL_SUBJECT_LITERAL_NAME"),
    ("literal name collection compared for equality",
     'M_SKILLS = ("alpha-skill", "beta-skill")\n'
     'def check_x(root, report):\n'
     '    if sorted(skill_paths(root)) != sorted(M_SKILLS):\n'
     '        report.bad("x", "0", "C", "m")\n',
     "SKILL_SUBJECT_LITERAL_COLLECTION"),
    ("literal name collection iterated",
     'M_SKILLS = ["alpha-skill", "beta-skill"]\n'
     'def check_x(root, report):\n'
     '    for name in M_SKILLS:\n'
     '        report.ok(name, "x")\n',
     "SKILL_SUBJECT_LITERAL_COLLECTION"),
    ("literal skill-directory scan root",
     'SCAN = ".opencode/skills/alpha-skill"\n'
     'def check_x(root, report):\n'
     '    for p in (root / SCAN).rglob("*.md"):\n'
     '        report.ok(str(p), "x")\n',
     "SKILL_SUBJECT_LITERAL_PATH"),
    ("inline literal skill-directory scan root",
     'def check_x(root, report):\n'
     '    d = root / ".opencode/skills/beta-skill"\n'
     '    report.ok(str(d), "x")\n',
     "SKILL_SUBJECT_LITERAL_PATH"),
    ("mapping-key membership as subject selection",
     'NOTES = {"alpha-skill": "a", "beta-skill": "b"}\n'
     'def check_x(root, report):\n'
     '    targets = [n for n in skill_paths(root) if n in NOTES]\n'
     '    report.ok("x", str(targets))\n',
     "SKILL_SUBJECT_MAPPING_KEYS"),
    ("ONE-element literal name collection iterated",
     'ONLY = ("alpha-skill",)\n'
     'def check_x(root, report):\n'
     '    for name in ONLY:\n'
     '        report.ok(name, "x")\n',
     "SKILL_SUBJECT_LITERAL_COLLECTION"),
    ("ONE-element inline literal collection used for membership",
     'def check_x(root, report):\n'
     '    targets = [n for n in skill_paths(root) if n in ("beta-skill",)]\n'
     '    report.ok("x", str(targets))\n',
     "SKILL_SUBJECT_LITERAL_COLLECTION"),
)


def subject_analyzer_failures() -> list[str]:
    """Self-test: empty when the analyzer discriminates, problems otherwise."""
    problems: list[str] = []
    clean = analyze_subject_derivation(_SUBJECT_GOOD, _SUBJECT_NAMES)
    if clean:
        problems.append(
            f"the conforming in-memory check was rejected with {[c for _, c, _ in clean]}; a name-keyed "
            "expectation map read AFTER discovery is legal, so the analyzer rejects everything and proves nothing")
    for label, src, want in _SUBJECT_CASES:
        codes = [c for _, c, _ in analyze_subject_derivation(src, _SUBJECT_NAMES)]
        if want not in codes:
            problems.append(f"near-miss {label!r} did not yield {want} (got {codes or 'no findings'})")
    return problems


def check_skill_subject_derivation(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "tools/selfcheck.py", "SKILL_SUBJECT_ABORT"):
        for problem in subject_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_subject_derivation", "SKILL_SUBJECT_FIXTURE",
                       f"the subject-derivation analyzer failed its in-memory fixtures: {problem}")
        names = known_skill_names(root)
        if not names:
            report.bad(".opencode/skills", "0", "SKILL_SUBJECT_NO_NAMES",
                       "no discovered or canonical skill names; the guard would recognise no literal and "
                       "pass vacuously")
            return
        try:
            source = Path(__file__).read_text(encoding="utf-8")
        except OSError as exc:
            report.bad("tools/selfcheck.py", "0", "SKILL_SUBJECT_UNREADABLE",
                       f"cannot read this harness to audit its own subject selection: {exc}")
            return
        if len(SUBJECT_DERIVATION_EXEMPT) != 1:
            report.bad("tools/selfcheck.py", "SUBJECT_DERIVATION_EXEMPT", "SKILL_SUBJECT_EXEMPTION",
                       f"{len(SUBJECT_DERIVATION_EXEMPT)} functions are exempt from the guard; exactly one - the "
                       "discovery-closure comparison, whose entire job is comparing discovery against the "
                       "canonical mapping - may be")
        findings = analyze_subject_derivation(source, names, SUBJECT_DERIVATION_EXEMPT)
        for fn, code, message in findings:
            report.bad("tools/selfcheck.py", fn, code, message)
        audited = sum(1 for n in ast.walk(ast.parse(source))
                      if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and n.name.startswith("check_") and n.name not in SUBJECT_DERIVATION_EXEMPT)
        report.ok("skill-subject-derivation",
                  f"{audited} check functions carry none of the {len(_SUBJECT_CASES)} literal subject-selection AST "
                  f"forms this guard tests for - literal name comparison, literal name collection (down to one "
                  f"element), literal skill directory, mapping-key membership - across {len(names)} known skill "
                  "names. This is a regression guard over those forms, not a proof that every check derives its "
                  "subjects: selection inside a called helper, a component-wise or aliased name, and "
                  "startswith/.keys() predicates are outside what it can see", mark)


# --- M4 check: skill-discovery-closure --------------------------------------
#
# Part 8. The template checks bind on whatever skill_paths() discovers, and
# discovery globs `*/SKILL.md` - so a skill directory with no SKILL.md is
# simply invisible and silently exempt. That is a fail-OPEN discovery, and it
# is exactly the hole the retired two-generation exemption file used to make
# visible. This check is what keeps discovery honest now that the file and its
# parser are gone.

# M4_SKILLS is gone. A literal six-name tuple compared for equality is a
# subject-selection literal (G3 shape 2), and it would also have had to be
# hand-edited for every new milestone. Discovery is now compared BOTH ways
# against the canonical mapping SKILL_SPEC, which the contract checks already
# treat as authoritative.
#
# This is the one function permitted to read SKILL_SPEC as a collection: its
# entire job IS that comparison. check_skill_subject_derivation enforces the
# exemption is exactly this one function.
SUBJECT_DERIVATION_EXEMPT: tuple[str, ...] = ("check_skill_discovery_closure",)


def check_skill_discovery_closure(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_DISCOVERY_ABORT"):
        d = root / ".opencode" / "skills"
        if not d.is_dir():
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_NO_DIR", "the skills directory is absent")
            return
        dirs = sorted(p for p in d.iterdir() if p.is_dir())
        for p in dirs:
            r = f".opencode/skills/{p.name}"
            entry = p / "SKILL.md"
            matches = sorted(x for x in p.glob("SKILL.md") if x.is_file())
            if not matches:
                report.bad(r, "0", "SKILL_DISCOVERY_NO_ENTRY",
                           "skill directory contains no regular SKILL.md; discovery globs */SKILL.md, so this "
                           "directory is invisible to every template check - a silent, undeclared exemption")
            elif not entry.is_file():
                report.bad(r, "0", "SKILL_DISCOVERY_NOT_REGULAR",
                           "SKILL.md is not a regular file")
        discovered = sorted(skill_paths(root))
        if not discovered:
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_EMPTY",
                       "no skill was discovered at all; every skill-scoped check would assert nothing")
            return
        canonical = sorted(SKILL_SPEC)
        undiscovered = sorted(set(canonical) - set(discovered))
        unmapped = sorted(set(discovered) - set(canonical))
        if undiscovered:
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_MISSING",
                       f"canonical skill(s) {', '.join(undiscovered)} are mapped but not discovered under "
                       ".opencode/skills/*/SKILL.md; a mapped skill that does not exist is a stage with no procedure")
        if unmapped:
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_UNMAPPED",
                       f"discovered skill(s) {', '.join(unmapped)} have no canonical contract mapping; "
                       "every discovered skill must be mapped or the contract checks compare it against nothing")
        # Every discovered skill must be in scope for the template checks with
        # no exclusion set applied at all.
        unbound = sorted(set(discovered) - set(in_scope_skills(root)))
        if unbound:
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_UNBOUND",
                       f"skills {unbound} are discovered but not in scope for the template checks")
        report.ok("skill-discovery-closure",
                  f"{len(discovered)} skill directories each carry exactly one regular SKILL.md and directory "
                  f"discovery equals the {len(canonical)}-entry canonical mapping in both directions", mark)


# ---------------------------------------------------------------------------


# ===========================================================================
# M6 checks
# ===========================================================================
#
# Every analyzer below is a PURE function of (relpath, text) so it can be
# self-tested against deliberate near-misses before the live corpus is
# trusted. An analyzer that has never been shown to reject anything is not
# evidence, and several of these are pure corpus-wording gates whose only
# protection against vacuity is that self-test.
#
# Subject selection: the file groups are module-level tuples of repository-
# relative paths, resolved by helpers that are NOT named check_*. That keeps
# them outside check_skill_subject_derivation's AST guard while still being
# literal data, which is correct here: these are the exact files the M6
# specification enumerates, not a discovered population.


def m6_text(root: Path, relpath: str) -> str | None:
    p = root / PurePosixPath(relpath)
    return read_text(p) if p.is_file() else None


def flat_low(text: str) -> str:
    return norm_ws(text).lower()


def sentences(text: str) -> list[str]:
    """Split normalized prose into sentence-ish units for co-occurrence rules."""
    return [s for s in re.split(r"(?<=[.!?;:])\s+|\n", norm_ws(text)) if s.strip()]


# --- M6/E3: mcxa-example-boundary -------------------------------------------

# The seven minimum lifecycle-contract elements (spec S3 E3). Both replacement
# texts that enumerate the whole contract contain all seven literally, so this
# term set is exactly satisfiable rather than aspirational.
LIFECYCLE_TERMS: tuple[str, ...] = (
    "policy owner",
    "acquisition",
    "reset arbitration",
    "lifetime accounting",
    "teardown",
    "quiescence",
    "frequency source",
    "cancellation",
)

# --- closure guards for the subject lists that cannot be derived -----------
#
# M6 recheck. Three subject lists in this file were hand-maintained and could
# omit a newly relevant file WITHOUT FAILING ANYTHING. One of them
# (MCXA_SUBJECT_FILES) turned out to be derivable and is gone. The two below
# are not: they encode which files the E1/E3 specification assigns specific
# obligations to, and nothing in the corpus carries that assignment in
# machine-readable form. Deriving them by keyword threshold was measured and
# rejected - it sweeps in TODO.md, selfcheck.md and driver-checklist.md, which
# would be me expanding the specification's scope on my own authority.
#
# So instead of leaving a silent allowlist, each list is CLOSED: every file
# matching the subject's defining marker must appear in either the subject
# list or an explicit, reasoned out-of-scope list. A new marker-matching file
# is in neither and fails loudly. The allowlist is still hand-maintained; it is
# no longer silent.


def subject_closure_failures(root: Path, marker: re.Pattern[str], subjects: tuple[str, ...],
                             out_of_scope: dict[str, str], label: str) -> list[tuple[str, str]]:
    """[(relpath, message)] for marker-matching files declared in neither list."""
    out: list[tuple[str, str]] = []
    untracked = untracked_working_state(root)
    for p in governed_markdown(root):
        if is_fixture_payload(root, p):
            continue
        relpath = rel(root, p)
        if relpath in untracked:
            continue
        if not marker.search(norm_ws(read_text(p))):
            continue
        if relpath in subjects or relpath in out_of_scope:
            continue
        out.append((relpath,
                    f"carries the {label} marker but appears in neither the subject list nor the recorded "
                    f"out-of-scope list in tools/selfcheck.py. A hand-maintained subject list that can silently "
                    f"omit a relevant file asserts nothing about it; add it to one list or the other"))
    return out


# Files whose replacement text enumerates the COMPLETE lifecycle contract.
LIFECYCLE_ENUMERATING_FILES: tuple[str, ...] = (
    "AGENTS.md",
    ".opencode/agents/hal-architect.md",
)
# Everything else that states the obligation, with why it is not held to the
# complete enumeration. Measured against the live corpus, not guessed.
LIFECYCLE_OUT_OF_SCOPE: dict[str, str] = {
    "TODO.md": "deferral register; it records requirements rather than stating the contract",
    ".opencode/agents/hal-driver.md": "applies the contract; E3 assigns the enumeration to the architect",
    ".opencode/schema/selfcheck.md": "documents this harness, and quotes the terms to describe the check",
    ".opencode/skills/scaffold-hal/SKILL.md": "dispatches the slice that authors the contract",
    ".opencode/skills/scaffold-hal/references/scaffold-record.md": "records that a contract exists",
    ".opencode/skills/write-clocks/SKILL.md": "authors the contract for one target; E3 item 8 governs its wording",
    ".opencode/skills/write-dma/SKILL.md": "consumes the contract; E3 item 13 governs its wording",
    ".opencode/skills/write-driver/references/driver-checklist.md": "E3 item 16 governs its wording",
    ".opencode/skills/write-driver/references/profiles/gpio.md": "E3 item 18 governs its wording",
    ".opencode/skills/write-driver/references/profiles/time-driver.md": "E3 item 19 governs its wording",
}
LIFECYCLE_MARKER_RE = re.compile(r"per resource|owning layer|lifecycle contract", re.IGNORECASE)

# Files whose replacement text explicitly frames MCXA names as examples.
MCXA_FRAMING_FILES: tuple[str, ...] = (
    "AGENTS.md",
    ".opencode/agents/hal-architect.md",
    ".opencode/agents/hal-driver.md",
    ".opencode/agents/hal-reviewer.md",
    ".opencode/skills/write-clocks/SKILL.md",
    ".opencode/skills/scaffold-hal/references/scaffold-record.md",
)
# Other files that name an MCXA helper, with why they need no framing sentence.
MCXA_FRAMING_OUT_OF_SCOPE: dict[str, str] = {
    "TODO.md": "deferral register; it quotes retired names to record what was removed",
    ".opencode/skills/write-dma/SKILL.md": "E3 item 13 replaces its wording; framing lives with the clock owner",
    ".opencode/skills/scaffold-hal/SKILL.md": "E3 item 14 replaces one worked string only",
    ".opencode/skills/write-driver/references/driver-checklist.md": "E3 item 16 replaces its wording",
    ".opencode/skills/write-driver/references/profiles/bus.md": "E3 item 17 replaces its wording",
    ".opencode/skills/write-driver/references/profiles/gpio.md": "E3 item 18 replaces its wording",
    ".opencode/skills/write-driver/references/profiles/time-driver.md": "E3 item 19 replaces its wording",
}

# M6 recheck: the subject set is DERIVED. There is no MCXA_SUBJECT_FILES list
# any more - every governed non-fixture Markdown file is scanned, so a new file
# that mandates an MCXA helper is covered the moment it is written. That became
# possible by narrowing the name pattern to IDENTIFIER-SHAPED occurrences: the
# old `\bthe gate\b` alternative matched the ordinary English word in "the
# citation gate" and "the review gate", which is why the scan had to be
# confined to a hand-listed set of clock-context files. Measured corpus-wide,
# the narrowed pattern produces no such false positive.
MCXA_NAME_RE = re.compile(
    r"enable_and_reset|`Gate`|\bGate trait\b|pub trait Gate|\bGate\b(?=\s*(?:trait|implementations|impl))")

MCXA_FRAMING_RE = re.compile(
    r"\bexamples?\b|\boptional\b|\bnot required\b|\bonly when\b|\bwhen selected\b|\bif selected\b"
    r"|\brequired only if\b|\bsearch example\b|\bmay extend\b",
    re.IGNORECASE)
MCXA_FRAMED_MENTION_RE = re.compile(r"mcxa[^.]{0,80}?\b(example|examples|names|helpers)\b", re.IGNORECASE)


def analyze_mcxa_boundary(relpath: str, text: str) -> list[tuple[str, str]]:
    """Pure analyzer: unframed MCXA-helper mandates and missing contract terms."""
    out: list[tuple[str, str]] = []
    for unit in sentences(text):
        if MCXA_NAME_RE.search(unit) and not MCXA_FRAMING_RE.search(unit):
            out.append((
                "MCXA_NAME_MANDATED",
                f"{relpath}: names an MCXA clock helper without framing it as an example or an optional "
                f"selection: {unit[:160]!r}. E3 makes Gate/enable_and_reset examples, not required names",
            ))
    if relpath in LIFECYCLE_ENUMERATING_FILES:
        low = flat_low(text)
        missing = [t for t in LIFECYCLE_TERMS if t not in low]
        if missing:
            out.append((
                "LIFECYCLE_CONTRACT_INCOMPLETE",
                f"{relpath}: the minimum lifecycle contract omits {', '.join(missing)}; E3 requires all "
                f"{len(LIFECYCLE_TERMS)} elements to be stated per resource",
            ))
    if relpath in MCXA_FRAMING_FILES and not MCXA_FRAMED_MENTION_RE.search(norm_ws(text)):
        out.append((
            "MCXA_FRAMING_ABSENT",
            f"{relpath}: never says that the MCXA names/helpers are examples; without that sentence a reader "
            "cannot tell an illustration from a requirement",
        ))
    return out


_MCXA_GOOD = (
    "Never duplicate clock, reset, or power policy in a peripheral driver. One architected owning layer "
    "records, per resource, policy owners, acquisition/initialization, reset arbitration, lifetime accounting "
    "or its explicit absence, teardown/quiescence, frequency source or irrelevance, and cancellation behavior. "
    "Gate and enable_and_reset are MCXA examples, not required names or shapes.\n"
)

_MCXA_CASES: tuple[tuple[str, str, str, str], ...] = (
    ("unframed mandate", "AGENTS.md",
     _MCXA_GOOD + "Reach gating through the Gate trait and enable_and_reset.\n",
     "MCXA_NAME_MANDATED"),
    ("dropped lifetime accounting", "AGENTS.md",
     _MCXA_GOOD.replace("lifetime accounting or its explicit absence, ", ""),
     "LIFECYCLE_CONTRACT_INCOMPLETE"),
    ("no example framing", ".opencode/agents/hal-reviewer.md",
     "Audit every minimum lifecycle-contract element and shared-domain behavior.\n",
     "MCXA_FRAMING_ABSENT"),
)


def mcxa_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_mcxa_boundary("AGENTS.md", _MCXA_GOOD)
    if clean:
        problems.append(f"the conforming replacement text was rejected with {[c for c, _ in clean]}; "
                        "the analyzer rejects everything and proves nothing")
    for name, relpath, text, expected in _MCXA_CASES:
        codes = [c for c, _ in analyze_mcxa_boundary(relpath, text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_mcxa_example_boundary(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "AGENTS.md", "MCXA_BOUNDARY_ABORT"):
        for problem in mcxa_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_mcxa_boundary", "MCXA_BOUNDARY_FIXTURE",
                       f"the MCXA-example analyzer failed its in-memory near-misses: {problem}")
        # DERIVED subject set: every governed non-fixture Markdown file, minus
        # untracked working state. No hand-maintained list of clock-context
        # files, so a new file that mandates an MCXA helper is covered.
        untracked = untracked_working_state(root)
        targets = [p for p in governed_markdown(root)
                   if not is_fixture_payload(root, p) and rel(root, p) not in untracked]
        scanned = 0
        for p in targets:
            relpath = rel(root, p)
            scanned += 1
            for code, message in analyze_mcxa_boundary(relpath, read_text(p)):
                report.bad(relpath, "prose", code, message)
        if scanned == 0:
            report.bad("AGENTS.md", "0", "MCXA_BOUNDARY_NO_TARGETS",
                       "no governed Markdown was readable; the boundary is asserted against nothing")
        for relpath in LIFECYCLE_ENUMERATING_FILES + MCXA_FRAMING_FILES:
            if m6_text(root, relpath) is None:
                report.bad(relpath, "0", "MCXA_BOUNDARY_TARGET_MISSING",
                           "file named by E3 is absent; its obligation cannot be verified")
        for relpath, message in subject_closure_failures(
                root, LIFECYCLE_MARKER_RE, LIFECYCLE_ENUMERATING_FILES, LIFECYCLE_OUT_OF_SCOPE,
                "lifecycle-contract obligation"):
            report.bad(relpath, "subject-closure", "MCXA_SUBJECT_UNDECLARED", message)
        for relpath, message in subject_closure_failures(
                root, MCXA_NAME_RE, MCXA_FRAMING_FILES, MCXA_FRAMING_OUT_OF_SCOPE, "MCXA helper name"):
            report.bad(relpath, "subject-closure", "MCXA_SUBJECT_UNDECLARED", message)
        report.ok("mcxa-example-boundary",
                  f"{scanned} governed non-fixture files - a DERIVED subject set, not a list - name no MCXA "
                  f"clock helper outside example framing; {len(LIFECYCLE_ENUMERATING_FILES)} state all "
                  f"{len(LIFECYCLE_TERMS)} minimum lifecycle-contract elements and "
                  f"{len(MCXA_FRAMING_FILES)} say so explicitly (analyzer self-tested against "
                  f"{len(_MCXA_CASES)} near-misses). Those last two ARE hand-maintained, and are CLOSED: every "
                  f"file carrying their marker must appear in the subject list or in a reasoned out-of-scope "
                  f"list, so an omission fails rather than passing silently. This matches the NAMED MCXA "
                  "HELPERS and nothing else. The same topology under other names - mandating a UniversalGate, a "
                  "UniversalWakeGuard, a required instance trio - matches no token and passes, so this is not a "
                  "guard against copied MCXA structure. Corpus wording only: no generated HAL is inspected", mark)


# --- M6/E4: error-clear-semantics -------------------------------------------

ERROR_SEMANTICS_FILES: tuple[str, ...] = (
    "AGENTS.md",
    ".opencode/agents/hal-driver.md",
    ".opencode/agents/hal-reviewer.md",
    ".opencode/skills/write-dma/SKILL.md",
    ".opencode/skills/write-driver/references/driver-checklist.md",
    ".opencode/skills/write-driver/references/profiles/bus.md",
)

# Rejected: the universal single-write clear, and the universal snapshot it
# implies. Both are false on read-to-clear registers.
ERROR_FORBIDDEN_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("single-write clear", re.compile(r"in one write", re.IGNORECASE)),
    ("clear-all mandate", re.compile(r"clear all (?:of them|error flags)", re.IGNORECASE)),
    ("universal snapshot", re.compile(r"read all error flags", re.IGNORECASE)),
)

# Required per file (the canonical replacement wording contains all of these).
ERROR_REQUIRED_TERMS: tuple[str, ...] = (
    "read-to-clear",
    "preserve",
    "recoverable",
    "latched",
)

# Required somewhere in the group, not per file: the canonical sentence does
# not name the write-one-to-clear and write-zero-to-clear conventions, so
# demanding them in every file would be unsatisfiable as specified.
ERROR_CORPUS_TERMS: tuple[str, ...] = ("w1c", "w0c")


def analyze_error_semantics(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    flat = norm_ws(text)
    low = flat.lower()
    for label, rx in ERROR_FORBIDDEN_RES:
        m = rx.search(flat)
        if m:
            out.append((
                "ERROR_CLEAR_OVERGENERAL",
                f"{relpath}: retains the {label} wording {m.group(0)!r}; E4 requires cited per-register read/clear "
                "semantics, because read-to-clear state cannot be snapshotted first and a blanket write destroys "
                "unrelated control bits",
            ))
    missing = [t for t in ERROR_REQUIRED_TERMS if t not in low]
    if missing:
        out.append((
            "ERROR_CLEAR_TERMS_MISSING",
            f"{relpath}: error-handling obligation omits {', '.join(missing)}; the canonical E4 wording states all "
            "of them",
        ))
    return out


_ERROR_GOOD = (
    "Observe and account for every relevant error condition according to cited read and clear semantics before "
    "returning. Preserve unrelated/control bits and leave no recoverable condition latched. Read-to-clear state "
    "need not and sometimes cannot be snapshotted first.\n"
)

_ERROR_CASES: tuple[tuple[str, str, str], ...] = (
    ("single write survives", _ERROR_GOOD + "Read every flag, clear all of them in one write.\n",
     "ERROR_CLEAR_OVERGENERAL"),
    ("universal snapshot survives", _ERROR_GOOD + "Read all error flags, then decide.\n",
     "ERROR_CLEAR_OVERGENERAL"),
    ("no preserve term", _ERROR_GOOD.replace("Preserve unrelated/control bits and ", ""),
     "ERROR_CLEAR_TERMS_MISSING"),
)


def error_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_error_semantics("AGENTS.md", _ERROR_GOOD)
    if clean:
        problems.append(f"the canonical E4 wording was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _ERROR_CASES:
        codes = [c for c, _ in analyze_error_semantics("AGENTS.md", text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_error_clear_semantics(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "AGENTS.md", "ERROR_CLEAR_ABORT"):
        for problem in error_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_error_semantics", "ERROR_CLEAR_FIXTURE",
                       f"the error-semantics analyzer failed its in-memory near-misses: {problem}")
        scanned = 0
        corpus_low = ""
        for relpath in ERROR_SEMANTICS_FILES:
            text = m6_text(root, relpath)
            if text is None:
                report.bad(relpath, "0", "ERROR_CLEAR_TARGET_MISSING",
                           "file named by E4 is absent; its replacement cannot be verified")
                continue
            scanned += 1
            corpus_low += flat_low(text) + " "
            for code, message in analyze_error_semantics(relpath, text):
                report.bad(relpath, "prose", code, message)
        if scanned == 0:
            report.bad("AGENTS.md", "0", "ERROR_CLEAR_NO_TARGETS",
                       "no E4 target file was readable; the wording is asserted against nothing")
        else:
            absent = [t for t in ERROR_CORPUS_TERMS if t not in corpus_low]
            if absent:
                report.bad("AGENTS.md", "prose", "ERROR_CLEAR_CONVENTIONS_MISSING",
                           f"no E4 file names the {', '.join(t.upper() for t in absent)} clear convention(s); "
                           "'cited read and clear semantics' is not actionable if the conventions are never named")
        report.ok("error-clear-semantics",
                  f"{scanned} E4 files reject the universal single-write clear and the universal snapshot and "
                  f"state all {len(ERROR_REQUIRED_TERMS)} obligation terms, with the W1C/W0C conventions named "
                  f"somewhere in the group (analyzer self-tested against {len(_ERROR_CASES)} near-misses). "
                  "CORPUS WORDING ONLY: no driver is compiled or executed here", mark)


# --- M6/E5: target-first-driver-order ---------------------------------------

DRIVER_AGENT_RELPATH = ".opencode/agents/hal-driver.md"
OBLIGATIONS_HEADING = "Conditional implementation obligations"
MCXA_PATH_RE = re.compile(r"embassy-mcxa/", re.IGNORECASE)


def bullet_items(body: str) -> list[str]:
    """Top-level '- ' bullets of a section, continuation lines folded in."""
    items: list[list[str]] = []
    for line in body.split("\n"):
        if re.match(r"^-\s+\S", line):
            items.append([line])
        elif items and line.strip():
            items[-1].append(line)
        elif items and not line.strip():
            items.append([])
            items.pop()
    return [norm_ws(" ".join(chunk)) for chunk in items if chunk]


def analyze_driver_order(relpath: str, text: str) -> list[tuple[str, str]]:
    """Pure analyzer for the E5 reading order inside the driver agent."""
    out: list[tuple[str, str]] = []
    heads = [(h, b, i) for h, b, i in h2_sections(text)]
    names = [h for h, _, _ in heads]
    if "What you do" in names:
        out.append(("DRIVER_ORDER_SECTION_NOT_RENAMED",
                    f"{relpath}: '## What you do' still exists; E5 renames it to "
                    f"'## {OBLIGATIONS_HEADING}' so its items read as conditional on target compatibility"))
    if OBLIGATIONS_HEADING not in names:
        out.append(("DRIVER_ORDER_SECTION_MISSING",
                    f"{relpath}: no '## {OBLIGATIONS_HEADING}' section"))
    elif "How you work" in names:
        if names.index(OBLIGATIONS_HEADING) < names.index("How you work"):
            out.append(("DRIVER_ORDER_SECTION_MISPLACED",
                        f"{relpath}: '## {OBLIGATIONS_HEADING}' precedes '## How you work'; E5 moves it after the "
                        "four reading-order bullets so the obligations are read second"))
    if "How you work" not in names:
        out.append(("DRIVER_ORDER_NO_WORKFLOW",
                    f"{relpath}: no '## How you work' section, so the reading order cannot be derived"))
        return out
    body = heads[names.index("How you work")][1]
    items = bullet_items(body)
    if len(items) < 4:
        out.append(("DRIVER_ORDER_ANCHORS_MISSING",
                    f"{relpath}: '## How you work' has {len(items)} top-level bullets; E5 requires at least four, "
                    "the first being the target-inventory anchor"))
        return out
    low = [b.lower() for b in items]
    if "inventory" not in low[0]:
        out.append(("DRIVER_ORDER_INVENTORY_NOT_FIRST",
                    f"{relpath}: the first '## How you work' bullet does not require writing the target capability/"
                    f"invariant inventory: {items[0][:160]!r}"))
    if not re.search(r"write-clocks|write-dma|write-driver", low[1]):
        out.append(("DRIVER_ORDER_DISPATCH_NOT_SECOND",
                    f"{relpath}: the second bullet is not the skill-selection anchor: {items[1][:160]!r}"))
    if not re.search(r"\b(profile|skill)\b", low[2]) or "applicable" not in low[2]:
        out.append(("DRIVER_ORDER_PROFILE_NOT_THIRD",
                    f"{relpath}: the third bullet does not load the selected skill/profile and separate applicable "
                    f"from inapplicable generic patterns: {items[2][:160]!r}"))
    if "only now" not in low[3] or "mcxa" not in low[3]:
        out.append(("DRIVER_ORDER_REFERENCE_NOT_FOURTH",
                    f"{relpath}: the fourth bullet does not defer reading the live embassy-mcxa references until "
                    f"after the inventory: {items[3][:160]!r}"))
    # No MCXA implementation PATH may appear before the end of the inventory
    # bullet. Computed on RAW LINES: a character offset derived from the
    # normalized bullet silently fails to locate a wrapped bullet, and a
    # located-nothing comparison would make this assertion vacuous.
    lines = text.split("\n")
    head_at = next((i for i, ln in enumerate(lines) if ln.strip() == "## How you work"), -1)
    if head_at < 0:
        out.append(("DRIVER_ORDER_INVENTORY_UNLOCATABLE",
                    f"{relpath}: cannot locate the '## How you work' heading on a raw line, so the "
                    "MCXA-path-before-inventory rule would pass vacuously"))
    else:
        bullet_lines = [i for i in range(head_at + 1, len(lines)) if re.match(r"^-\s+\S", lines[i])]
        if len(bullet_lines) < 2:
            out.append(("DRIVER_ORDER_INVENTORY_UNLOCATABLE",
                        f"{relpath}: fewer than two raw bullets follow '## How you work'; the end of the inventory "
                        "bullet cannot be located"))
        else:
            inv_end = bullet_lines[1]
            early = [i for i in range(inv_end) if MCXA_PATH_RE.search(lines[i])]
            if early:
                out.append(("DRIVER_ORDER_MCXA_PATH_EARLY",
                            f"{relpath}: an embassy-mcxa implementation path appears on line {early[0] + 1}, before "
                            f"the target-inventory bullet ends on line {inv_end}; E5 forbids opening another "
                            "target's implementation before the inventory exists"))
    return out


_DRIVER_GOOD = """# x

## Stance

- Accepted target facts, PAC, architecture and selected profile define capability.

## How you work

- Validate the payload, then read target facts, PAC, architecture, startup/lifecycle
  contract, scope/modes, dependencies and requirements; write the target capability/
  invariant inventory before opening another target's implementation.
- Use `write-clocks` for the first platform clock slice, `write-dma` for the shared DMA
  subsystem, and `write-driver` for ordinary peripheral subsystems.
- Load the selected skill/profile and identify applicable and inapplicable generic patterns.
- Only now read the live `embassy-mcxa` references named by the skill; compare them with
  the inventory and record accepted and rejected analogies.

## Conditional implementation obligations

Apply each item only after target/profile compatibility is established.

- **Type erasure.** One lifetime and one Mode.
"""

_DRIVER_CASES: tuple[tuple[str, str, str], ...] = (
    ("section not renamed",
     _DRIVER_GOOD.replace("## Conditional implementation obligations", "## What you do"),
     "DRIVER_ORDER_SECTION_NOT_RENAMED"),
    ("obligations before workflow",
     _DRIVER_GOOD.replace("## How you work", "## ZZZ").replace(
         "## Conditional implementation obligations", "## How you work").replace(
         "## ZZZ", "## Conditional implementation obligations"),
     "DRIVER_ORDER_SECTION_MISPLACED"),
    ("reference read promoted above inventory",
     _DRIVER_GOOD.replace(
         "- Validate the payload, then read target facts, PAC, architecture, startup/lifecycle\n"
         "  contract, scope/modes, dependencies and requirements; write the target capability/\n"
         "  invariant inventory before opening another target's implementation.\n",
         "- Read the live `embassy-mcxa` references named by the skill before anything else.\n"),
     "DRIVER_ORDER_INVENTORY_NOT_FIRST"),
    ("profile bullet swapped out",
     _DRIVER_GOOD.replace(
         "- Load the selected skill/profile and identify applicable and inapplicable generic patterns.",
         "- Write the code."),
     "DRIVER_ORDER_PROFILE_NOT_THIRD"),
    ("deferral removed",
     _DRIVER_GOOD.replace("- Only now read the live `embassy-mcxa` references named by the skill; compare them with",
                          "- Read whatever you like; compare them with"),
     "DRIVER_ORDER_REFERENCE_NOT_FOURTH"),
    ("mcxa path promoted into the stance",
     _DRIVER_GOOD.replace("- Accepted target facts, PAC, architecture and selected profile define capability.",
                          "- Read embassy-mcxa/src/i2c/ first; it is the spec."),
     "DRIVER_ORDER_MCXA_PATH_EARLY"),
)


def driver_order_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_driver_order(DRIVER_AGENT_RELPATH, _DRIVER_GOOD)
    if clean:
        problems.append(f"the conforming E5 ordering was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _DRIVER_CASES:
        codes = [c for c, _ in analyze_driver_order(DRIVER_AGENT_RELPATH, text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_target_first_driver_order(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, DRIVER_AGENT_RELPATH, "DRIVER_ORDER_ABORT"):
        for problem in driver_order_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_driver_order", "DRIVER_ORDER_FIXTURE",
                       f"the reading-order analyzer failed its in-memory near-misses: {problem}")
        text = m6_text(root, DRIVER_AGENT_RELPATH)
        if text is None:
            report.bad(DRIVER_AGENT_RELPATH, "0", "DRIVER_ORDER_TARGET_MISSING",
                       "the driver agent is absent; the E5 reading order is asserted against nothing")
            return
        if "is the spec" in flat_low(text):
            report.bad(DRIVER_AGENT_RELPATH, "Stance", "DRIVER_ORDER_DEVGUIDE_IS_SPEC",
                       "the stance still calls another target's DEVGUIDE 'the spec'; E5 makes accepted target facts, "
                       "PAC, architecture and the selected profile the capability source")
        for code, message in analyze_driver_order(DRIVER_AGENT_RELPATH, text):
            report.bad(DRIVER_AGENT_RELPATH, "order", code, message)
        report.ok("target-first-driver-order",
                  f"the driver agent states the four E5 reading-order anchors in order, renames its obligations "
                  f"section and places it after them, and names no embassy-mcxa implementation path before the "
                  f"target inventory (analyzer self-tested against {len(_DRIVER_CASES)} near-misses). This asserts "
                  "DOCUMENT ORDER only; it cannot observe what an agent actually reads first", mark)


# --- M6/E8: checkout-context-guard ------------------------------------------

CONTEXT_NO_ACTION_SENTENCE = ("HAL workflow not started: run toolkit maintenance with a non-HAL agent, "
                              "or install halucinator into an Embassy checkout.")
CONTEXT_MARKERS: tuple[str, ...] = (
    "README.md", "docs/opencode.json", ".opencode/ownership.toml", "tools/selfcheck.py",
)
CONTEXT_CLASSES: tuple[str, ...] = ("TOOLKIT", "EMBASSY", "AMBIGUOUS")

# M6 follow-up. The E8 guard as first written binds EVERY agent that reads
# AGENTS.md, not the hal-* HAL-workflow agents it was specified for. That is a
# demonstrated false positive: a generic reviewer dispatched to do toolkit
# maintenance on THIS repository refused twice with the guard's own no-action
# sentence, and was right to - "before anything else ... no write, no
# subdispatch" outranks a dispatch instruction. The original E8 defect was a
# prerequisite that halted toolkit maintenance; an unscoped guard reproduces it
# in mirror image and makes it mandatory rather than merely implied.
#
# So the guard must now declare BOTH halves of its scope. These are matched as
# CO-OCCURRENCE within one sentence over two open families of wording, not as
# one literal sentence: the coder writes prose, and several reasonable
# phrasings satisfy each half. The refusal behaviour required of hal-* agents
# is unchanged and every assertion above still applies to them.

# Who the guard binds: the HAL-workflow agent family.
CONTEXT_FAMILY_RE = re.compile(
    r"hal-\*|hal-workflow agents?|HAL-workflow agents?|\bHAL agents?\b|hal-<[a-z]+>|the eight hal-",
    re.IGNORECASE)
# ... stated as an obligation, so merely naming the family does not count.
CONTEXT_OBLIGATION_RE = re.compile(r"classif|guard|refus|no-action|not started|halt|bound by",
                                   re.IGNORECASE)
# Who it does not bind: a non-HAL agent doing toolkit maintenance here.
CONTEXT_NONHAL_RE = re.compile(
    r"non-HAL|not a HAL|toolkit maintenance|maintenance agents?|outside the HAL workflow",
    re.IGNORECASE)
# ... and that such an agent carries on. Deliberately excludes "run", which the
# existing remedy sentence already contains: the remedy tells the OPERATOR what
# to do next, it does not tell the reading agent it may proceed.
CONTEXT_PROCEED_RE = re.compile(
    r"\bproceeds?\b|does not apply|not bound|never bound|exempt|continue normally|as normal"
    r"|\bnormally\b|unaffected|no obligation",
    re.IGNORECASE)



def contract_fence_end(text: str) -> int:
    """Character offset just past the agent contract fence, or -1."""
    m = re.search(r"^```" + re.escape(CONTRACT_INFO) + r"\s*$", text, re.MULTILINE)
    if not m:
        return -1
    close = re.search(r"^```\s*$", text[m.end():], re.MULTILINE)
    return m.end() + close.end() if close else -1


def analyze_context_guard(relpath: str, text: str, require_fence: bool) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    flat = norm_ws(text)
    idx = flat.find(CONTEXT_NO_ACTION_SENTENCE)
    if idx < 0:
        out.append(("CONTEXT_GUARD_ABSENT",
                    f"{relpath}: does not carry the exact no-action sentence {CONTEXT_NO_ACTION_SENTENCE!r}; "
                    "without it an agent in the toolkit checkout has no scripted refusal"))
    missing_class = [c for c in CONTEXT_CLASSES if c not in text]
    if missing_class:
        out.append(("CONTEXT_GUARD_CLASSES_MISSING",
                    f"{relpath}: names no {', '.join(missing_class)} classification; E8 requires all three, with "
                    "TOOLKIT winning even when Embassy markers also appear"))
    if "precede" not in flat.lower() and "wins" not in flat.lower() and "even if" not in flat.lower():
        out.append(("CONTEXT_GUARD_PRECEDENCE_MISSING",
                    f"{relpath}: never states that TOOLKIT takes precedence over EMBASSY; a predicate without a "
                    "precedence rule is ambiguous exactly where it matters"))
    low = flat.lower()
    for forbidden, why in (("retry", "retry"), ("subdispatch", "subdispatch")):
        if forbidden not in low:
            out.append(("CONTEXT_GUARD_NO_ACTION_INCOMPLETE",
                        f"{relpath}: does not forbid {why} on a TOOLKIT/AMBIGUOUS classification; E8 requires an "
                        "immediate return with no retry, lock, state publication, write or subdispatch"))
    if require_fence:
        end = contract_fence_end(text)
        if end < 0:
            out.append(("CONTEXT_GUARD_NO_CONTRACT",
                        f"{relpath}: no parseable agent contract fence, so the guard's position cannot be asserted"))
        elif idx >= 0:
            raw_at = text.find(CONTEXT_NO_ACTION_SENTENCE.split(":")[0])
            if 0 <= raw_at < end:
                out.append(("CONTEXT_GUARD_MISPLACED",
                            f"{relpath}: the context guard appears inside or before the contract fence; E8 places it "
                            "immediately after"))
    # Scope. Both halves are required: an unscoped guard binds every reader,
    # and a guard that only names an exclusion leaves the binding set to
    # inference.
    units = sentences(text)
    # A sentence about who is NOT bound is not a statement of who IS bound.
    # Without this the exclusion half satisfies the binding half by accident:
    # "non-HAL agent" contains a word-boundary match for "HAL agent", and
    # "is not bound by it" matches the obligation family.
    if not any(CONTEXT_FAMILY_RE.search(s) and CONTEXT_OBLIGATION_RE.search(s)
               and not CONTEXT_NONHAL_RE.search(s) for s in units):
        out.append(("CONTEXT_GUARD_SCOPE_UNBOUND",
                    f"{relpath}: no sentence states that the classification obligation binds the hal-* "
                    "HAL-workflow agents specifically. An unscoped guard binds every agent that reads this file, "
                    "including one dispatched to maintain this toolkit, which is a demonstrated false refusal"))
    if not any(CONTEXT_NONHAL_RE.search(s) and CONTEXT_PROCEED_RE.search(s) for s in units):
        out.append(("CONTEXT_GUARD_EXCLUSION_ABSENT",
                    f"{relpath}: no sentence states that a non-HAL agent performing toolkit maintenance on this "
                    "repository is not bound and proceeds normally. Without it a good-faith reader refuses, because "
                    "the guard's own 'before anything else' wording outranks its dispatch"))
    return out


_CONTEXT_SCOPE_BINDS = (
    "This guard binds the hal-* HAL-workflow agents and nobody else. "
)
_CONTEXT_SCOPE_EXCLUDES = (
    "A non-HAL agent performing toolkit maintenance on this repository is not bound by it and proceeds "
    "normally.\n"
)

_CONTEXT_GOOD_BODY = (
    _CONTEXT_SCOPE_BINDS +
    "Classify the checkout read-only before anything else. TOOLKIT when README.md, docs/opencode.json, "
    ".opencode/ownership.toml and tools/selfcheck.py exist; TOOLKIT wins even if Embassy markers also appear. "
    "Otherwise EMBASSY, otherwise AMBIGUOUS. On TOOLKIT or AMBIGUOUS respond exactly: "
    + CONTEXT_NO_ACTION_SENTENCE +
    " Return immediately and list the observed markers: no retry, no lock, no state publication, no write, "
    "no subdispatch. " + _CONTEXT_SCOPE_EXCLUDES
)

_CONTEXT_GOOD_AGENT = (
    "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n" + _CONTEXT_GOOD_BODY
)

_CONTEXT_CASES: tuple[tuple[str, str, bool, str], ...] = (
    ("sentence removed", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(CONTEXT_NO_ACTION_SENTENCE, "Stop."), True, "CONTEXT_GUARD_ABSENT"),
    ("ambiguous class dropped", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace("otherwise AMBIGUOUS", "otherwise proceed").replace(
         "On TOOLKIT or AMBIGUOUS respond", "On TOOLKIT respond"), True,
     "CONTEXT_GUARD_CLASSES_MISSING"),
    ("precedence dropped", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace("; TOOLKIT wins even if Embassy markers also appear", ""), True,
     "CONTEXT_GUARD_PRECEDENCE_MISSING"),
    ("subdispatch still permitted", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(", no subdispatch", ""), True, "CONTEXT_GUARD_NO_ACTION_INCOMPLETE"),
    ("guard before the contract", _CONTEXT_GOOD_BODY + "\n```" + CONTRACT_INFO + "\nid: a\n```\n", True,
     "CONTEXT_GUARD_MISPLACED"),
    # --- scope near-misses -------------------------------------------------
    # 1. Today's shipped state: a guard with neither half of its scope. It must
    #    fail on BOTH codes, which is what makes the live corpus RED.
    ("unscoped guard binds every reader", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(_CONTEXT_SCOPE_BINDS, "").replace(_CONTEXT_SCOPE_EXCLUDES, ""), True,
     "CONTEXT_GUARD_SCOPE_UNBOUND"),
    ("unscoped guard omits the exclusion too", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(_CONTEXT_SCOPE_BINDS, "").replace(_CONTEXT_SCOPE_EXCLUDES, ""), True,
     "CONTEXT_GUARD_EXCLUSION_ABSENT"),
    # 2. Names who is excluded but never who is bound.
    ("exclusion without a binding set", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(_CONTEXT_SCOPE_BINDS, ""), True, "CONTEXT_GUARD_SCOPE_UNBOUND"),
    # 3. Binds hal-* agents but never releases toolkit maintenance - the
    #    demonstrated false refusal survives.
    ("binding without an exclusion", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(_CONTEXT_SCOPE_EXCLUDES, ""), True, "CONTEXT_GUARD_EXCLUSION_ABSENT"),
    # 4. The remedy sentence alone must NOT satisfy the exclusion: it tells the
    #    operator what to run next, it does not release the reading agent.
    ("remedy sentence mistaken for an exclusion", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(
         _CONTEXT_SCOPE_EXCLUDES,
         "Run toolkit maintenance with a non-HAL agent instead.\n"), True,
     "CONTEXT_GUARD_EXCLUSION_ABSENT"),
    # 5. Naming the family without an obligation is not a binding statement.
    ("family named but not bound", "# a\n\n```" + CONTRACT_INFO + "\nid: a\n```\n\n"
     + _CONTEXT_GOOD_BODY.replace(
         _CONTEXT_SCOPE_BINDS, "The hal-* agents are listed in the pipeline table below. "), True,
     "CONTEXT_GUARD_SCOPE_UNBOUND"),
)



def context_guard_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_context_guard(".opencode/agents/x.md", _CONTEXT_GOOD_AGENT, True)
    if clean:
        problems.append(f"the conforming guard was rejected with {[c for c, _ in clean]}")
    for name, text, fence, expected in _CONTEXT_CASES:
        codes = [c for c, _ in analyze_context_guard(".opencode/agents/x.md", text, fence)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_checkout_context_guard(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents", "CONTEXT_GUARD_ABORT"):
        for problem in context_guard_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_context_guard", "CONTEXT_GUARD_FIXTURE",
                       f"the checkout-context analyzer failed its in-memory near-misses: {problem}")
        agents = agent_paths(root)
        if len(agents) != 8:
            report.bad(".opencode/agents", "0", "CONTEXT_GUARD_AGENT_COUNT",
                       f"discovered {len(agents)} agents; E8 requires the guard in all eight copies")
        for name in sorted(agents):
            relpath = rel(root, agents[name])
            for code, message in analyze_context_guard(relpath, read_text(agents[name]), True):
                report.bad(relpath, "context-guard", code, message)
        agents_md = m6_text(root, "AGENTS.md")
        if agents_md is None:
            report.bad("AGENTS.md", "0", "CONTEXT_GUARD_TARGET_MISSING", "AGENTS.md is absent")
        else:
            for code, message in analyze_context_guard("AGENTS.md", agents_md, False):
                report.bad("AGENTS.md", "context-guard", code, message)
            missing = [m for m in CONTEXT_MARKERS if m not in agents_md]
            if missing:
                report.bad("AGENTS.md", "Scope", "CONTEXT_GUARD_MARKERS_MISSING",
                           f"the classification predicate omits marker(s) {', '.join(missing)}; E8 names an exact "
                           "conservative marker set so classification is reproducible")
            if "No HAL source lives here" not in agents_md:
                report.bad("AGENTS.md", "Scope", "CONTEXT_GUARD_README_PROBE_MISSING",
                           "the predicate never names the README sentence 'No HAL source lives here' it tests for")
        readme = m6_text(root, "README.md")
        if readme is None:
            report.bad("README.md", "0", "CONTEXT_GUARD_TARGET_MISSING", "README.md is absent")
        elif not re.search(r"opencode\.json[^.]{0,200}\binert\b", norm_ws(readme)):
            report.bad("README.md", "0", "CONTEXT_GUARD_INERT_NOTE_MISSING",
                       "README does not note that docs/opencode.json is inert product material; a config that looks "
                       "live in the toolkit checkout is exactly the E8 confusion")
        report.ok("checkout-context-guard",
                  f"{len(agents)} agents plus AGENTS.md carry the exact no-action sentence, all three "
                  f"classifications, the TOOLKIT precedence rule and the no-retry/no-subdispatch restriction, "
                  f"AND scope the guard in both directions - one sentence binding the hal-* HAL-workflow agents "
                  f"to the obligation, another releasing a non-HAL agent doing toolkit maintenance on this "
                  f"repository - and README notes the inert config (analyzer self-tested against "
                  f"{len(_CONTEXT_CASES)} near-misses, including an unscoped guard and the remedy sentence "
                  "mistaken for an exclusion). Scope is matched as sentence-level CO-OCCURRENCE over two open "
                  "wording families, not one literal sentence, so several phrasings satisfy it. CORPUS/CONFIG "
                  "ONLY: no classification is executed here, the refusal strictness required of hal-* agents is "
                  "asserted as text and not as behaviour, and nothing here can tell a correctly scoped exclusion "
                  "from one worded so broadly that a hal-* agent reads itself out of the guard", mark)


# --- M6/E9: install-no-overwrite --------------------------------------------

COPY_VERB_RE = re.compile(r"^\s*(?:cp\s|Copy-Item\b|robocopy\b|xcopy\b)", re.MULTILINE)
POSIX_GUARD_RE = re.compile(r"\[\s*!\s*-e\s")
PWSH_GUARD_RE = re.compile(r"Test-Path\s+-LiteralPath")
PWSH_THROW_RE = re.compile(r"\bthrow\b")
FORCE_RE = re.compile(r"(?:^|\s)-Force\b|(?:^|\s)-f\b|--force\b")


def fenced_blocks_with_info(text: str) -> list[tuple[str, str]]:
    """[(info-string, body)] for every fenced block, in document order."""
    out: list[tuple[str, str]] = []
    info: str | None = None
    body: list[str] = []
    for line in text.split("\n"):
        m = re.match(r"^\s*```(\S*)\s*$", line)
        if m and info is None:
            info = m.group(1).lower()
            body = []
            continue
        if re.match(r"^\s*```\s*$", line) and info is not None:
            out.append((info, "\n".join(body)))
            info = None
            continue
        if info is not None:
            body.append(line)
    return out


def analyze_install_blocks(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    if "overwrite matching files" in norm_ws(text):
        out.append(("INSTALL_OVERWRITE_DECLARED",
                    f"{relpath}: still announces that the commands overwrite matching files; E9 makes install a "
                    "fresh-install operation and sends existing destinations to a manual diff/merge path"))
    copying = 0
    for info, body in fenced_blocks_with_info(text):
        if not COPY_VERB_RE.search(body):
            continue
        copying += 1
        if FORCE_RE.search(body):
            out.append(("INSTALL_FORCE_USED",
                        f"{relpath}: a {info or 'plain'} install block passes a force flag: "
                        f"{_one_line(body, 160)!r}; E9 forbids Force so an existing destination cannot be "
                        "silently replaced"))
        pwsh = info in ("powershell", "pwsh", "ps1") or "Copy-Item" in body
        if pwsh:
            if not (PWSH_GUARD_RE.search(body) and PWSH_THROW_RE.search(body)):
                out.append(("INSTALL_GUARD_MISSING",
                            f"{relpath}: a PowerShell install block copies without a "
                            "'Test-Path -LiteralPath' ... throw guard on every destination: "
                            f"{_one_line(body, 160)!r}"))
        else:
            if not POSIX_GUARD_RE.search(body):
                out.append(("INSTALL_GUARD_MISSING",
                            f"{relpath}: a POSIX install block copies without a '[ ! -e ... ] || exit 1' guard on "
                            f"every destination: {_one_line(body, 160)!r}"))
    if copying == 0:
        out.append(("INSTALL_NO_COPY_BLOCKS",
                    f"{relpath}: no fenced block contains a copy command, so the guard assertion would pass "
                    "vacuously"))
    return out


_INSTALL_GOOD = """# x

Fresh install only. For an existing destination, diff and merge manually.

```sh
[ ! -e /dst/AGENTS.md ] || exit 1
cp halucinator/AGENTS.md /dst/AGENTS.md
```

```powershell
if (Test-Path -LiteralPath D:\\dst\\AGENTS.md) { throw "exists" }
Copy-Item halucinator\\AGENTS.md D:\\dst\\AGENTS.md
```
"""

_INSTALL_CASES: tuple[tuple[str, str, str], ...] = (
    ("overwrite announcement", _INSTALL_GOOD.replace(
        "Fresh install only.", "The commands below overwrite matching files."),
     "INSTALL_OVERWRITE_DECLARED"),
    ("posix guard removed", _INSTALL_GOOD.replace("[ ! -e /dst/AGENTS.md ] || exit 1\n", ""),
     "INSTALL_GUARD_MISSING"),
    ("powershell guard removed", _INSTALL_GOOD.replace(
        'if (Test-Path -LiteralPath D:\\dst\\AGENTS.md) { throw "exists" }\n', ""),
     "INSTALL_GUARD_MISSING"),
    ("force flag", _INSTALL_GOOD.replace(
        "Copy-Item halucinator\\AGENTS.md", "Copy-Item -Force halucinator\\AGENTS.md"),
     "INSTALL_FORCE_USED"),
    ("no copy blocks at all", "# x\n\nNothing here.\n", "INSTALL_NO_COPY_BLOCKS"),
)


def install_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_install_blocks("README.md", _INSTALL_GOOD)
    if clean:
        problems.append(f"the conforming fresh-install text was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _INSTALL_CASES:
        codes = [c for c, _ in analyze_install_blocks("README.md", text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_install_no_overwrite(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "README.md", "INSTALL_ABORT"):
        for problem in install_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_install_blocks", "INSTALL_FIXTURE",
                       f"the install-command analyzer failed its in-memory near-misses: {problem}")
        text = m6_text(root, "README.md")
        if text is None:
            report.bad("README.md", "0", "INSTALL_TARGET_MISSING", "README.md is absent")
            return
        for code, message in analyze_install_blocks("README.md", text):
            report.bad("README.md", "install", code, message)
        report.ok("install-no-overwrite",
                  f"every README install block that copies contains at least one absence guard and passes no "
                  f"force flag (analyzer self-tested against {len(_INSTALL_CASES)} near-misses). The guard test "
                  "is PER BLOCK, not per destination: a block that guards its first copy and then copies three "
                  "more destinations unguarded passes. Establishing one-to-one guard-before-copy correspondence "
                  "needs a shell parser, which this harness does not have. Shipped command text only", mark)


# --- M6/H7: reference-url-pins ----------------------------------------------

MOVING_REF_RE = re.compile(
    r"https?://[^\s)<>\"']*?/(?:raw|blob|tree|archive)?/?(?:refs/heads/)?(?:main|master|HEAD)(?:/|\b)",
    re.IGNORECASE)
EXACT_SHA_RE = re.compile(r"\b[0-9a-f]{40}\b")


def analyze_reference_pins(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for m in MOVING_REF_RE.finditer(text):
        url = m.group(0)
        if EXACT_SHA_RE.search(url):
            continue
        out.append(("REFERENCE_URL_MOVING",
                    f"{relpath}: evidentiary URL {url!r} names a moving ref; H7 requires the exact inspected commit "
                    "URL, or removal of the claim. Never substitute an invented SHA"))
    return out


_PINS_GOOD = (
    "See [Cargo.toml](https://raw.githubusercontent.com/embassy-rs/embassy/"
    "0123456789abcdef0123456789abcdef01234567/embassy-mcxa/Cargo.toml) as inspected.\n"
    "The project home is https://github.com/embassy-rs/embassy for orientation only.\n"
)

_PINS_CASES: tuple[tuple[str, str, str], ...] = (
    ("raw main", "https://raw.githubusercontent.com/embassy-rs/embassy/main/embassy-mcxa/Cargo.toml\n",
     "REFERENCE_URL_MOVING"),
    ("blob master", "https://github.com/embassy-rs/embassy/blob/master/ci.sh\n", "REFERENCE_URL_MOVING"),
    ("tree HEAD", "https://github.com/embassy-rs/embassy/tree/HEAD/embassy-stm32\n", "REFERENCE_URL_MOVING"),
    ("refs/heads/main", "https://github.com/x/y/raw/refs/heads/main/a.toml\n", "REFERENCE_URL_MOVING"),
)


def reference_pin_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_reference_pins("README.md", _PINS_GOOD)
    if clean:
        problems.append(f"the pinned-and-orientation sample was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _PINS_CASES:
        codes = [c for c, _ in analyze_reference_pins("README.md", text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_reference_url_pins(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "README.md", "REFERENCE_PIN_ABORT"):
        for problem in reference_pin_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_reference_pins", "REFERENCE_PIN_FIXTURE",
                       f"the moving-ref analyzer failed its in-memory near-misses: {problem}")
        files = governed_markdown(root)
        if not files:
            report.bad(".opencode", "0", "REFERENCE_PIN_NO_TARGETS",
                       "no governed Markdown discovered; the pin rule is asserted against nothing")
            return
        for p in files:
            relpath = rel(root, p)
            for code, message in analyze_reference_pins(relpath, read_text(p)):
                report.bad(relpath, "url", code, message)
        report.ok("reference-url-pins",
                  f"no evidentiary URL across {len(files)} governed Markdown files names main/master/HEAD without an "
                  f"exact 40-hex commit (analyzer self-tested against {len(_PINS_CASES)} near-misses). This proves "
                  "PIN IMMUTABILITY only: it cannot tell whether the pinned commit says what the prose claims, and "
                  "a non-GitHub moving reference is outside the pattern", mark)


# --- M6/A18: tester-destination-coverage ------------------------------------

DESTINATION_FILES: tuple[str, ...] = (
    ".opencode/agents/hal-tester.md",
    ".opencode/skills/write-examples/SKILL.md",
    "README.md",
)

DESTINATION_CLOSURE = "closes configured-path coverage"
DESTINATION_REOPEN = "remain leak paths"
DESTINATION_FORBIDDEN_RE = re.compile(r"destination[_ ]crate[^.]{0,120}\barbitrary\b|\barbitrary path\b",
                                      re.IGNORECASE)


def analyze_destination_coverage(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    flat = norm_ws(text)
    low = flat.lower()
    m = DESTINATION_FORBIDDEN_RE.search(flat)
    if m:
        out.append(("DESTINATION_STILL_ARBITRARY",
                    f"{relpath}: still describes the destination crate path as arbitrary: {m.group(0)!r}; schema 2 "
                    "constrains it to a repository-root one-segment embassy-<vendor_id>"))
    if "embassy-<vendor_id>" not in flat:
        out.append(("DESTINATION_CONSTRAINT_ABSENT",
                    f"{relpath}: never states the root embassy-<vendor_id> constraint"))
    if "embassy-*/**" not in flat:
        out.append(("DESTINATION_COVERAGE_ABSENT",
                    f"{relpath}: never states that embassy-*/** is what covers the constrained destination"))
    ci = low.find(DESTINATION_CLOSURE)
    ri = low.find(DESTINATION_REOPEN)
    if ci < 0:
        out.append(("DESTINATION_CLOSURE_ABSENT",
                    f"{relpath}: does not say what the constraint closes ({DESTINATION_CLOSURE!r})"))
    if ri < 0:
        out.append(("DESTINATION_REOPEN_ABSENT",
                    f"{relpath}: does not reopen the residual: bash, grep, filenames, diagnostics, history and "
                    "tools remain leak paths. A closure claim without it overstates blindness"))
    if ci >= 0 and ri >= 0 and ri < ci:
        out.append(("DESTINATION_ORDER_WRONG",
                    f"{relpath}: the residual-leak sentence precedes the closure claim; A18 requires deny then "
                    "reopen so the limitation qualifies the claim it follows"))
    if "invalidates the run" not in low:
        out.append(("DESTINATION_INVALIDATION_ABSENT",
                    f"{relpath}: does not state that observed body text invalidates the run"))
    return out


_DEST_GOOD = (
    "Schema 2 constrains destination_crate to root embassy-<vendor_id>, covered by embassy-*/**. This closes "
    "configured-path coverage, not perfect blindness: bash, grep, filenames, diagnostics, history and tools "
    "remain leak paths; observed body text invalidates the run.\n"
)

_DEST_CASES: tuple[tuple[str, str, str], ...] = (
    ("arbitrary retained", _DEST_GOOD + "The destination crate path can be arbitrary.\n",
     "DESTINATION_STILL_ARBITRARY"),
    ("reopen removed", _DEST_GOOD.replace(
        ": bash, grep, filenames, diagnostics, history and tools remain leak paths;", ":"),
     "DESTINATION_REOPEN_ABSENT"),
    ("order inverted",
     "Bash, grep, filenames, diagnostics, history and tools remain leak paths. Schema 2 constrains "
     "destination_crate to root embassy-<vendor_id>, covered by embassy-*/**, which closes configured-path "
     "coverage; observed body text invalidates the run.\n",
     "DESTINATION_ORDER_WRONG"),
    ("invalidation removed", _DEST_GOOD.replace("; observed body text invalidates the run", ""),
     "DESTINATION_INVALIDATION_ABSENT"),
)


def destination_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_destination_coverage(".opencode/agents/hal-tester.md", _DEST_GOOD)
    if clean:
        problems.append(f"the conforming A18 wording was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _DEST_CASES:
        codes = [c for c, _ in analyze_destination_coverage(".opencode/agents/hal-tester.md", text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_tester_destination_coverage(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/agents/hal-tester.md", "DESTINATION_ABORT"):
        for problem in destination_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_destination_coverage", "DESTINATION_FIXTURE",
                       f"the destination-coverage analyzer failed its in-memory near-misses: {problem}")
        scanned = 0
        for relpath in DESTINATION_FILES:
            text = m6_text(root, relpath)
            if text is None:
                report.bad(relpath, "0", "DESTINATION_TARGET_MISSING",
                           "file named by A18 is absent; the destination constraint cannot be verified")
                continue
            scanned += 1
            for code, message in analyze_destination_coverage(relpath, text):
                report.bad(relpath, "destination", code, message)
        if scanned == 0:
            report.bad(".opencode/agents/hal-tester.md", "0", "DESTINATION_NO_TARGETS",
                       "no A18 target file readable; the constraint is asserted against nothing")
        report.ok("tester-destination-coverage",
                  f"{scanned} A18 files constrain destination_crate to root embassy-<vendor_id>, name embassy-*/** "
                  f"as its coverage, and state the closure BEFORE the residual leak paths and the run-invalidation "
                  f"rule (analyzer self-tested against {len(_DEST_CASES)} near-misses). The CONFIGURED PATH is what "
                  "is closed; bash, grep, filenames, diagnostics, history and tools remain open and unasserted", mark)


# --- M6/E6+E7: claim-truth-limit --------------------------------------------

VALIDATE_DOC_RELPATH = ".opencode/schema/validate.md"
CLAIM_DISCLOSURE_FILES: tuple[str, ...] = (
    ".opencode/schema/validate.md",
    ".opencode/agents/hal-coordinator.md",
    ".opencode/agents/hal-integrator.md",
    ".opencode/agents/hal-reviewer.md",
    ".opencode/agents/hal-tester.md",
    "docs/skill-template.md",
)
CLAIM_TERMS: tuple[tuple[str, str], ...] = (
    ("fabricated", "that a claimant may have fabricated execution evidence"),
    ("no external attester", "that no external attester exists"),
)
E6_DISCLOSURE = ("M6 does not propagate beyond declared current one-hop bindings; cycles/missing graph nodes "
                 "are not represented.")


def analyze_claim_truth(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    low = flat_low(text)
    for token, why in CLAIM_TERMS:
        if token not in low:
            out.append(("CLAIM_LIMIT_UNDISCLOSED",
                        f"{relpath}: does not disclose {why}; E7 requires the limitation to be stated wherever "
                        "typed evidence is described, because it is not mechanically detectable"))
    return out


_CLAIM_GOOD = ("Hash/occurrence checks prove bytes and the bounded relation stated; the claimant may still have "
               "fabricated execution evidence. No external attester exists.\n")

_CLAIM_CASES: tuple[tuple[str, str, str], ...] = (
    ("fabrication not disclosed",
     _CLAIM_GOOD.replace("the claimant may still have fabricated execution evidence. ", ""),
     "CLAIM_LIMIT_UNDISCLOSED"),
    ("attester claim removed", _CLAIM_GOOD.replace(" No external attester exists.", ""),
     "CLAIM_LIMIT_UNDISCLOSED"),
)


def claim_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_claim_truth(VALIDATE_DOC_RELPATH, _CLAIM_GOOD)
    if clean:
        problems.append(f"the conforming E7 disclosure was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _CLAIM_CASES:
        codes = [c for c, _ in analyze_claim_truth(VALIDATE_DOC_RELPATH, text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_claim_truth_limit(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, VALIDATE_DOC_RELPATH, "CLAIM_LIMIT_ABORT"):
        for problem in claim_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_claim_truth", "CLAIM_LIMIT_FIXTURE",
                       f"the claim-limit analyzer failed its in-memory near-misses: {problem}")
        scanned = 0
        for relpath in CLAIM_DISCLOSURE_FILES:
            text = m6_text(root, relpath)
            if text is None:
                report.bad(relpath, "0", "CLAIM_LIMIT_TARGET_MISSING",
                           "file named by E7 is absent; the disclosure cannot be verified")
                continue
            scanned += 1
            for code, message in analyze_claim_truth(relpath, text):
                report.bad(relpath, "disclosure", code, message)
        doc = m6_text(root, VALIDATE_DOC_RELPATH)
        if doc is not None and E6_DISCLOSURE not in norm_ws(doc):
            report.bad(VALIDATE_DOC_RELPATH, "limits", "CLAIM_LIMIT_E6_UNDISCLOSED",
                       "validate.md does not state the exact E6 deferral sentence; transitive invalidation is "
                       "deferred to post-M7 and a reader must not infer it is handled")
        if scanned == 0:
            report.bad(VALIDATE_DOC_RELPATH, "0", "CLAIM_LIMIT_NO_TARGETS",
                       "no E7 target readable; disclosure is asserted against nothing")
        report.ok("claim-truth-limit",
                  f"{scanned} files disclose that typed evidence may be fabricated and that no external attester "
                  f"exists, and validate.md states the E6 one-hop deferral "
                  f"(analyzer self-tested against {len(_CLAIM_CASES)} near-misses). This ENSURES THE LIMITATION IS "
                  "DISCLOSED; it does not detect a false claim and cannot", mark)


# --- M6/E1: citation-verification-corpus ------------------------------------

CITATION_FILES: tuple[str, ...] = (
    ".opencode/schema/handoff-common.md",
    ".opencode/schema/01-sources.md",
    ".opencode/schema/02-facts.md",
    ".opencode/schema/06-driver.md",
    ".opencode/agents/hal-datasheet.md",
    ".opencode/skills/extract-hardware-facts/SKILL.md",
)
# Files that declare citation fields but carry no E1 required-leaf obligation,
# with the reason. Closes CITATION_FILES so an omission cannot be silent.
CITATION_OUT_OF_SCOPE: dict[str, str] = {
    "TODO.md": "deferral register; it names leaves to record deferred work",
    ".opencode/agents/hal-tester.md": "consumes resolved assertion IDs; originates no CitationRef",
    ".opencode/schema/07-tests.md": "references assertion IDs through the driver handoff",
    ".opencode/schema/worked-examples.md": "worked examples, governed by the fixture generator",
    ".opencode/skills/debug-hardware/SKILL.md": "consumes resolved assertion IDs only",
    ".opencode/skills/generate-svd/SKILL.md": "consumes verified citations; declares no field table",
    ".opencode/skills/review-artifact/SKILL.md": "re-verifies the same IDs; declares no field table",
    ".opencode/skills/write-examples/SKILL.md": "consumes resolved assertion IDs only",
}
CITATION_MARKER_DECL_RE = re.compile(r"assertion_id|\[\[facts\.citations\]\]")

# (relpath, required substring, why) - each is drawn from the exact S2.2/S2.3
# field table or the exact E1 replacement prose.
CITATION_REQUIRED: tuple[tuple[str, str, str], ...] = (
    (".opencode/schema/handoff-common.md", "assertion_id",
     "the v2 CitationRef is keyed by a stable assertion ID"),
    (".opencode/schema/handoff-common.md", "excerpt",
     "the excerpt is what the verifier matches"),
    (".opencode/schema/handoff-common.md", "pdf-page",
     "the tagged location variant the verifier derives from"),
    (".opencode/schema/handoff-common.md", "text-lines",
     "the tagged location variant for UTF-8 sources"),
    (".opencode/schema/01-sources.md", "sources.documents",
     "source IDs bind to hash-pinned bytes through one array"),
    (".opencode/schema/02-facts.md", "citations-verified",
     "the mandatory gate check on 02-facts"),
    (".opencode/schema/06-driver.md", "facts_handoff",
     "drivers reference a verified facts handoff rather than originating citations"),
    (".opencode/schema/06-driver.md", "test_hardware_facts",
     "the assertion-ID reference list the tester is given"),
    (".opencode/agents/hal-datasheet.md", "assertion ID",
     "the producer states what every fact now carries"),
    (".opencode/skills/extract-hardware-facts/SKILL.md", "poppler-utils",
     "the fail-closed remedy names the package that supplies pdftotext"),
    (".opencode/skills/extract-hardware-facts/SKILL.md", "pdftotext -layout",
     "the remedy names the exact rerun command"),
)

# Agent-authored extraction is the R1 attack: it must not reappear as a field
# or as prose telling an agent to copy from its own extraction.
CITATION_EXTRACTION_RES: tuple[re.Pattern[str], ...] = (
    re.compile(r"extraction_first_page|extraction_last_page|CitationRef\.extraction"),
    re.compile(r"copied from the layout-preserving extraction", re.IGNORECASE),
    re.compile(r"\bnot mechanically verified here\b", re.IGNORECASE),
)

# Retired v1 leaves that must not survive anywhere in the citation surface.
CITATION_RETIRED_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("sources.source_ids", re.compile(r"\bsources\.source_ids\b")),
    ("sources.available", re.compile(r"\bsources\.available\b")),
    ("facts.citations.document", re.compile(r"facts\.citations\.document\b")),
    ("facts.citations.revision", re.compile(r"facts\.citations\.revision\b")),
)


def analyze_citation_corpus(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    flat = norm_ws(text)
    low = flat.lower()
    for rx in CITATION_EXTRACTION_RES:
        m = rx.search(flat)
        if m:
            out.append(("CITATION_TRUSTED_EXTRACTION",
                        f"{relpath}: still routes citation evidence through an agent-authored extraction "
                        f"({m.group(0)!r}); E1 regenerates the selected location from hash-pinned source bytes"))
    for label, rx in CITATION_RETIRED_RES:
        if rx.search(flat):
            out.append(("CITATION_RETIRED_LEAF",
                        f"{relpath}: retains the retired v1 leaf {label}; schema 2 replaces it with the "
                        "sources.documents binding, and an independently-membered source list is exactly the "
                        "flaw that removal closes"))
    for want_path, needle, why in CITATION_REQUIRED:
        if want_path == relpath and needle not in flat:
            out.append(("CITATION_FIELD_ABSENT",
                        f"{relpath}: does not name {needle!r} - {why}"))
    # Overclaim: anything describing the gate must also state what it cannot
    # prove. An occurrence proof read as a truth proof is the E1 failure mode.
    if "citation_unverified" in low or "citations-verified" in low or "verify_citation" in low:
        if "cannot prove" not in low and "does not prove" not in low:
            out.append(("CITATION_OVERCLAIM",
                        f"{relpath}: describes the citation gate without stating what it cannot prove; "
                        "occurrence is not entailment, OCR correctness, or vendor truth"))
        elif "entailment" not in low and "semantic" not in low:
            out.append(("CITATION_OVERCLAIM",
                        f"{relpath}: states a limit but never that semantic entailment is outside it"))
    return out


_CITATION_GOOD = (
    "Record each assertion in the v2 CitationRef: assertion_id, scope_item, claim, source_id, source, "
    "location.kind (pdf-page or text-lines), locator, excerpt and note. Do not provide or trust an extraction "
    "path: validate.py regenerates the selected location from the bound source bytes. Run the citation gate; a "
    "missing pdftotext fails with CITATION_UNVERIFIED and the remedy: install poppler-utils, then rerun "
    "pdftotext -layout -f <page> -l <page> <source> -. The gate proves normalized occurrence at the cited "
    "location; it cannot prove semantic entailment, OCR correctness or vendor truth.\n"
)

_CITATION_CASES: tuple[tuple[str, str, str, str], ...] = (
    ("trusted extraction", ".opencode/skills/extract-hardware-facts/SKILL.md",
     _CITATION_GOOD + "Use the excerpt copied from the layout-preserving extraction.\n",
     "CITATION_TRUSTED_EXTRACTION"),
    ("remedy absent", ".opencode/skills/extract-hardware-facts/SKILL.md",
     _CITATION_GOOD.replace("install poppler-utils, then rerun ", "reinstall it, then rerun "),
     "CITATION_FIELD_ABSENT"),
    ("driver linkage absent", ".opencode/schema/06-driver.md",
     "Drivers record the hardware facts their tests depend on.\n",
     "CITATION_FIELD_ABSENT"),
    ("overclaim", ".opencode/schema/02-facts.md",
     "The citations-verified check passes when the validator has confirmed every cited hardware fact.\n",
     "CITATION_OVERCLAIM"),
    ("retired leaf", ".opencode/schema/01-sources.md",
     "Fields: sources.source_ids required; sources.documents required.\n",
     "CITATION_RETIRED_LEAF"),
)


def citation_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_citation_corpus(".opencode/skills/extract-hardware-facts/SKILL.md", _CITATION_GOOD)
    if clean:
        problems.append(f"the conforming E1 producer text was rejected with {[c for c, _ in clean]}")
    for name, relpath, text, expected in _CITATION_CASES:
        codes = [c for c, _ in analyze_citation_corpus(relpath, text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_citation_verification_corpus(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/schema/02-facts.md", "CITATION_CORPUS_ABORT"):
        for problem in citation_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_citation_corpus", "CITATION_CORPUS_FIXTURE",
                       f"the citation-corpus analyzer failed its in-memory near-misses: {problem}")
        scanned = 0
        for relpath in CITATION_FILES:
            text = m6_text(root, relpath)
            if text is None:
                report.bad(relpath, "0", "CITATION_CORPUS_TARGET_MISSING",
                           "file named by E1 is absent; the citation contract cannot be verified")
                continue
            scanned += 1
            for code, message in analyze_citation_corpus(relpath, text):
                report.bad(relpath, "citation", code, message)
        if scanned == 0:
            report.bad(".opencode/schema/02-facts.md", "0", "CITATION_CORPUS_NO_TARGETS",
                       "no E1 target readable; the citation contract is asserted against nothing")
        # The FORBIDDEN halves need no mapping and are scanned corpus-wide, so
        # a retired leaf or a trusted extraction path anywhere is caught.
        untracked = untracked_working_state(root)
        wide = 0
        for p in governed_markdown(root):
            relpath = rel(root, p)
            if is_fixture_payload(root, p) or relpath in CITATION_FILES or relpath in untracked:
                continue
            wide += 1
            for code, message in analyze_citation_corpus(relpath, read_text(p)):
                if code in ("CITATION_TRUSTED_EXTRACTION", "CITATION_RETIRED_LEAF"):
                    report.bad(relpath, "citation", code, message)
        for relpath, message in subject_closure_failures(
                root, CITATION_MARKER_DECL_RE, CITATION_FILES, CITATION_OUT_OF_SCOPE,
                "CitationRef field declaration"):
            report.bad(relpath, "subject-closure", "CITATION_SUBJECT_UNDECLARED", message)
        report.ok("citation-verification-corpus",
                  f"{scanned} E1 files declare the v2 CitationRef leaves and the sources.documents binding, and "
                  f"across a further {wide} governed files no retired v1 leaf or agent-authored extraction path "
                  f"survives anywhere; the poppler-utils remedy carries its exact rerun command and entailment is "
                  f"disclaimed wherever the gate is described (analyzer self-tested against "
                  f"{len(_CITATION_CASES)} near-misses). The REQUIRED-leaf mapping is per file and hand-"
                  f"maintained - the specification assigns specific leaves to specific files and nothing carries "
                  f"that assignment mechanically - so it is CLOSED: any file declaring CitationRef fields must "
                  f"appear in the subject list or a reasoned out-of-scope list. CORPUS WORDING ONLY: whether "
                  "validate.py actually derives text from the pinned bytes is proved by the fixtures, not here", mark)


# --- M6/H10: fixture-regeneration -------------------------------------------

FIXTURE_GENERATOR_RELPATH = "tools/generate_schema_fixtures.py"


def check_fixture_regeneration(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, FIXTURE_GENERATOR_RELPATH, "FIXTURE_REGEN_ABORT"):
        gen = root / PurePosixPath(FIXTURE_GENERATOR_RELPATH)
        if not gen.is_file():
            report.bad(FIXTURE_GENERATOR_RELPATH, "0", "FIXTURE_REGEN_MISSING",
                       "the committed fixture generator is absent; without it the fixture corpus has no in-tree "
                       "source and byte-identical regeneration cannot be demonstrated (H10)")
            return
        decl = root / PurePosixPath(FIXTURE_DECL_RELPATH)
        if not decl.is_file():
            report.bad(FIXTURE_DECL_RELPATH, "0", "FIXTURE_REGEN_NO_INPUT",
                       "the declarative generator input is absent; the generator would have no source of truth")
        cmd = [sys.executable, str(gen), "--root", ".", "--check"]
        try:
            proc = subprocess.run(
                cmd, cwd=str(root), capture_output=True, text=True,
                timeout=SUBPROCESS_TIMEOUT, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            report.bad(FIXTURE_GENERATOR_RELPATH, "0", "FIXTURE_REGEN_TIMEOUT",
                       f"'--check' did not finish in {SUBPROCESS_TIMEOUT}s; a hang is a failure, never a pass")
            return
        out = (proc.stdout or "") + (proc.stderr or "")
        if proc.returncode != 0:
            report.bad(FIXTURE_GENERATOR_RELPATH, "0", "FIXTURE_REGEN_DIVERGED",
                       f"'--check' exited {proc.returncode}; a committed fixture is undeclared, missing, or differs "
                       f"byte for byte: {_one_line(out, 500)}")
            return
        if out.strip():
            report.bad(FIXTURE_GENERATOR_RELPATH, "0", "FIXTURE_REGEN_NOISY",
                       f"'--check' exited 0 but printed output; exact equality must be silent: {_one_line(out, 300)}")
            return
        report.ok("fixture-regeneration",
                  f"'{FIXTURE_GENERATOR_RELPATH} --root . --check' exits 0 silently, so every committed fixture byte "
                  f"is declared by {FIXTURE_DECL_RELPATH} and regenerates identically. This proves REGENERATION, not "
                  "that the declared mutations are the right ones; that judgement stays with review", mark)


# --- M6/D17: runtime-protocol-tests -----------------------------------------

RUNTIME_RELPATH = ".opencode/schema/runtime.py"
RUNTIME_TEST_RELPATH = ".opencode/schema/test_runtime.py"
RUNTIME_TEST_TIMEOUT = 300

# Each required D17 fault, with the alternative spellings that identify it in a
# test's function name or docstring. Written as regexes over the lowered,
# underscore-and-hyphen-flattened test surface so a reasonable naming choice
# satisfies them without this harness dictating one.
RUNTIME_FAULT_CASES: tuple[tuple[str, str], ...] = (
    ("simultaneous post-create acquisition conflict",
     r"(simultaneous|concurrent|post.?create|race).{0,40}(conflict|acquir)|conflict.{0,40}(post.?create|simultaneous)"),
    ("PID reuse / process-birth mismatch", r"pid.?reuse|birth.?(mismatch|identity)|process.?birth"),
    ("orphaned probe/runner child", r"orphan|surviving.?child|child.?(survive|outliv)"),
    ("recovery interrupted repeatedly", r"interrupt.{0,30}(twice|repeat|again)|repeat.{0,30}interrupt"),
    ("check-token check-use pause", r"check.?use|token.?pause|pause.{0,30}token"),
    ("Windows os.replace delete-sharing failure", r"sharing.?violation|delete.?shar|replace.?(fail|retry)"),
    ("unsupported directory fsync", r"(dir|directory).?fsync|fsync.?unsupported|durability.?unavailable"),
    ("fresh-clone absence", r"fresh.?clone|no.?prior.?lock|absence.?(is|not).?evidence"),
)


def runtime_test_surface(source: str) -> str:
    """Lowered, flattened test names plus docstrings: the searchable surface."""
    parts: list[str] = []
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            parts.append(node.name)
            doc = ast.get_docstring(node)
            if doc:
                parts.append(doc)
    return re.sub(r"[_\-\s]+", " ", " ".join(parts).lower())


def _runtime_surface_failures() -> list[str]:
    """Self-test the fault-coverage patterns against a naming-plausible sample."""
    sample = '''
def test_simultaneous_acquisition_conflict():
    """Second claimant removes only its own candidate."""

def test_pid_reuse_birth_mismatch():
    pass

def test_orphaned_probe_child_forces_unknown():
    pass

def test_recovery_interrupted_twice_stays_pending():
    pass

def test_check_use_window_pause():
    pass

def test_windows_replace_sharing_violation_retries_then_fails():
    pass

def test_directory_fsync_unsupported_blocks_operations():
    pass

def test_fresh_clone_starts_recovery_pending():
    pass
'''
    surface = runtime_test_surface(sample)
    problems = [label for label, pat in RUNTIME_FAULT_CASES if not re.search(pat, surface)]
    if problems:
        return [f"the fault-coverage patterns did not recognise a plausibly named suite: {problems}"]
    empty = runtime_test_surface("def helper():\n    pass\n")
    matched = [label for label, pat in RUNTIME_FAULT_CASES if re.search(pat, empty)]
    if matched:
        return [f"the fault-coverage patterns matched an EMPTY suite for {matched}; they would pass vacuously"]
    return []


def check_runtime_protocol_tests(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, RUNTIME_TEST_RELPATH, "RUNTIME_TESTS_ABORT"):
        for problem in _runtime_surface_failures():
            report.bad("tools/selfcheck.py", "RUNTIME_FAULT_CASES", "RUNTIME_TESTS_FIXTURE",
                       f"the D17 fault-coverage patterns failed their self-test: {problem}")
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        suite = root / PurePosixPath(RUNTIME_TEST_RELPATH)
        if not helper.is_file():
            report.bad(RUNTIME_RELPATH, "0", "RUNTIME_HELPER_MISSING",
                       "the worktree-local interlock helper is absent; there is no single-operator board exclusion "
                       "to test and no CLI for a caller to reach")
        if not suite.is_file():
            report.bad(RUNTIME_TEST_RELPATH, "0", "RUNTIME_TESTS_MISSING",
                       "the D17 fault-injection suite is absent; every interlock claim would be unexercised")
            return
        source = read_text(suite)
        try:
            surface = runtime_test_surface(source)
        except SyntaxError as exc:
            report.bad(RUNTIME_TEST_RELPATH, "0", "RUNTIME_TESTS_UNPARSEABLE",
                       f"the suite does not parse, so its fault coverage cannot be derived: {exc}")
            return
        if "subprocess" not in source:
            report.bad(RUNTIME_TEST_RELPATH, "0", "RUNTIME_TESTS_NOT_BLACKBOX",
                       "the suite never imports or names subprocess; D17 requires the production helper to be driven "
                       "as a subprocess with file and exit-code inspection, so the test does not re-implement the "
                       "algorithm it is meant to check")
        uncovered = [label for label, pat in RUNTIME_FAULT_CASES if not re.search(pat, surface)]
        if uncovered:
            report.bad(RUNTIME_TEST_RELPATH, "0", "RUNTIME_TESTS_FAULT_UNCOVERED",
                       f"{len(uncovered)} required D17 fault(s) are named by no test: {'; '.join(uncovered)}")
        if not helper.is_file():
            return
        cmd = [sys.executable, str(suite)]
        try:
            proc = subprocess.run(
                cmd, cwd=str(root), capture_output=True, text=True,
                timeout=RUNTIME_TEST_TIMEOUT, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            report.bad(RUNTIME_TEST_RELPATH, "0", "RUNTIME_TESTS_TIMEOUT",
                       f"the suite did not finish in {RUNTIME_TEST_TIMEOUT}s; a hang in an interlock test is a "
                       "failure, never a pass - a helper that blocks forever is a board that never releases")
            return
        if proc.returncode != 0:
            out = (proc.stdout or "") + (proc.stderr or "")
            report.bad(RUNTIME_TEST_RELPATH, "0", "RUNTIME_TESTS_FAILED",
                       f"the suite exited {proc.returncode}: {_one_line(out, 600)}")
            return
        report.ok("runtime-protocol-tests",
                  f"the D17 fault-injection suite runs green and names all {len(RUNTIME_FAULT_CASES)} required "
                  "faults - post-create acquisition conflict, PID reuse against process birth identity, orphaned "
                  "probe child, repeatedly interrupted recovery, the check-use pause, Windows delete-sharing "
                  "replacement failure, unsupported directory fsync, and fresh-clone absence. COVERAGE IS DERIVED "
                  "FROM TEST NAMES AND DOCSTRINGS: a test named for a fault it does not actually inject is "
                  "invisible here, and the broker, cross-clone and physical-truth residuals are closed by nothing "
                  "in M6", mark)



# ===========================================================================
# M6 review follow-up: behaviour, not wording
# ===========================================================================
#
# The M6 compliance review found the hardware-safety mechanism was largely
# theatre while this harness was green: every existing M6 check asserts corpus
# WORDING or fixture SHAPE, and none drives the helper that is supposed to keep
# a board from being driven on unreadable evidence. The checks below execute
# the production helper as a subprocess in a throwaway directory and assert
# OBSERVABLE OUTCOMES - exit status and file state - never the helper's own
# report of itself. A command that reports success while writing nothing is
# exactly the defect being closed.

RUNTIME_CLI_TIMEOUT = 60
BOARD_FIXTURE_ID = "BOARD-FIXTURE-1"
BOARD_FIXTURE_STAGE = "write-tests:demo"
BOARD_FIXTURE_AUTH = "halucinator/auth.md"
# Evidence paths that deliberately do not exist. Naming them explicitly keeps
# the intent readable in a failure message.
ABSENT_ATTEMPT = "evidence/recovery/does-not-exist-attempt.toml"
ABSENT_SAFE_STATE = "evidence/safe-state/does-not-exist-observation.toml"
ABSENT_OVERRIDE = "evidence/recovery/does-not-exist-override.toml"


def run_runtime(root: Path, workdir: Path, args: list[str]) -> tuple[int | None, str, dict | None]:
    """Invoke the production interlock helper as a subprocess. Never imported.

    Returns (returncode, combined output, parsed JSON or None). A timeout
    returns rc=None, which every caller must treat as a failure: a helper that
    blocks forever is a board that never releases.
    """
    helper = root / PurePosixPath(RUNTIME_RELPATH)
    cmd = [sys.executable, str(helper), "--root", str(workdir)] + args
    try:
        proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                              timeout=RUNTIME_CLI_TIMEOUT, encoding="utf-8", errors="replace")
    except subprocess.TimeoutExpired:
        return None, f"timed out after {RUNTIME_CLI_TIMEOUT}s", None
    out = (proc.stdout or "") + (proc.stderr or "")
    try:
        parsed = json.loads(proc.stdout or "")
    except (ValueError, TypeError):
        parsed = None
    return proc.returncode, out, parsed


def acquire_fixture_board(root: Path, workdir: Path) -> tuple[dict | None, str]:
    """Create one interlock in a fresh directory. Returns (payload, problem)."""
    rc, out, payload = run_runtime(root, workdir, [
        "acquire-board", "--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
        "--authorization", BOARD_FIXTURE_AUTH])
    if rc != 0 or not payload:
        return None, f"acquire-board did not establish a fixture interlock (rc={rc}): {_one_line(out, 240)}"
    if not payload.get("lease_epoch") or not payload.get("check_token"):
        return None, f"acquire-board returned no epoch/token: {_one_line(out, 240)}"
    return payload, ""


def live_lock_files(workdir: Path) -> list[Path]:
    d = workdir / "halucinator" / ".run"
    return sorted(p for p in d.glob("*.lock")) if d.is_dir() else []


def lock_says(workdir: Path, key: str) -> str | None:
    """The raw value text of one lock key.

    Captures the WHOLE line after `key =`. The earlier pattern stopped at the
    first quote, which silently truncated inline tables such as
    `child_session={kind="process-group",identity="child-one",...}` to
    `{kind=` - so a test asking whether a child identity survived was reading
    a value that never contained one. Surrounding quotes are stripped so plain
    scalars compare as before.
    """
    for p in live_lock_files(workdir):
        m = re.search(rf"^{re.escape(key)}\s*=\s*(.+?)\s*$", read_text(p), re.MULTILINE)
        if m:
            value = m.group(1)
            if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
                return value[1:-1]
            return value
    return None


# --- A: interlock-refuses-fabricated-evidence -------------------------------


def write_lf(p: Path, text: str) -> None:
    """Write UTF-8 with LF endings. newline='' keeps Windows from rewriting."""
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8", newline="") as handle:
        handle.write(text)


def run_closure_scenario(root: Path, report: Report, degrade: str | None) -> tuple[str, str, str]:
    """Drive acquire -> recovery -> verify -> release over a real evidence closure.

    Returns (outcome, step, detail) with THREE distinguishable outcomes:

      "released" - the sequence completed and the lock is gone.
      "refused"  - the helper rejected the sequence at `step` with a non-zero
                   exit. For a DEGRADED variant this is the desired result, and
                   it is desired WHEREVER it happens: refusing an unpinned
                   FileRef at append is strictly better than admitting it to
                   the append-only lineage, letting verify call the board safe,
                   and only catching it at release.
      "unposed"  - the scenario could not be constructed or ran ambiguously
                   (acquire failed, a command timed out, or release reported
                   success while the lock survived). This is never evidence
                   about the helper's integrity handling; it means this
                   harness could not ask the question.

    The earlier two-way bool conflated "refused" with "could not construct",
    which made the only passing shape for a degraded variant "admitted at
    append, admitted at verify, caught at release" - i.e. it demanded the
    weaker helper. That was a defect in this check, not in the helper.

    `degrade` is None for the positive control, "no-digest" to strip a nested
    FileRef's sha256, or "mutate-nested" to alter a nested record after
    recovery is verified.
    """
    workdir = Path(tempfile.mkdtemp(prefix="halucinator-closure-"))
    try:
        payload, problem = acquire_fixture_board(root, workdir)
        if payload is None:
            return ("unposed", "acquire-board", problem)
        # Derived, not written twice. The records below are schema-versioned,
        # and B1 was caused by exactly this literal being pinned in one place
        # while the schema moved in another. One derivation feeds all three.
        version, verr = derive_schema_version(root / ".opencode" / "schema" / "validate.py")
        if version is None:
            return ("unposed", "derive-schema-version", verr)
        epoch, token = payload["lease_epoch"], payload["check_token"]
        common = ["--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                  "--epoch", epoch, "--token", token]
        nested_rel = "halucinator/test-candidates/demo/evidence/recovery/prior-lock.txt"
        nested = workdir / PurePosixPath(nested_rel)
        write_lf(nested, "archived prior lock bytes for the fictional fixture board\n")
        sha = __import__("hashlib").sha256
        digest = sha(nested.read_bytes()).hexdigest()
        pinned = f'{{path = "{nested_rel}", sha256 = "{digest}"}}'
        if degrade == "no-digest":
            pinned = f'{{path = "{nested_rel}"}}'
        # A REAL facts handoff. The helper now binds procedure.facts_handoff
        # properly - it parses the reference, requires the extract-facts kind,
        # ready status, a passed `citations-verified` check, and every
        # assertion ID to resolve against the citations the handoff carries.
        # The previous builder pointed this at a plain-text file, which
        # binding necessarily refuses; accepting that back would undo the
        # repair, so the CONTROL moves to meet the helper, not the reverse.
        #
        # `checks` is a bare top-level key and must be emitted BEFORE any
        # table header: once `[facts]` opens it would land at `facts.checks`
        # and the helper would correctly report no verified check.
        facts_rel = "halucinator/test-candidates/demo/evidence/02-facts.toml"
        facts = workdir / PurePosixPath(facts_rel)
        assertion_id = "fixture.safe-state.procedure"
        write_lf(facts,
                 'checks = [{id = "citations-verified", status = "passed"}]\n'
                 "[handoff]\n"
                 f"schema = {version}\n"
                 'stage = "extract-facts"\n'
                 'status = "ready"\n'
                 "[facts]\n"
                 f'citations = [{{assertion_id = "{assertion_id}", '
                 'claim = "The invented fixture board reports zero in every invented field '
                 'after a fixture reset."}]\n')
        facts_pin = f'{{path = "{facts_rel}", sha256 = "{sha(facts.read_bytes()).hexdigest()}"}}'
        safe_rel = "halucinator/test-candidates/demo/evidence/safe-state/" + f"{epoch}-0.toml"
        safe = workdir / PurePosixPath(safe_rel)
        hazards = "".join(
            '[[hazards]]\n'
            f'kind = "{k}"\n'
            'disposition = "safe"\n'
            'observation_method = "operator observation of the fictional fixture board"\n'
            f'evidence = {{path = "{nested_rel}", sha256 = "{digest}"}}\n'
            f'operator_confirmation = {{path = "{nested_rel}", sha256 = "{digest}"}}\n'
            for k in ("outputs", "dma", "interrupts", "external-loads", "reset-halt", "probe"))
        write_lf(safe,
                 f"schema = {version}\n"
                 f'board_id = "{BOARD_FIXTURE_ID}"\n'
                 f'lease_epoch = "{epoch}"\n'
                 "operation_attempt = 0\n"
                 'observed_at = "2026-01-01T00:05:00Z"\n'
                 "outstanding_human_actions = []\n"
                 "[procedure]\n"
                 f'board_id = "{BOARD_FIXTURE_ID}"\n'
                 f"facts_handoff = {facts_pin}\n"
                 f'assertion_ids = ["{assertion_id}"]\n'
                 f'procedure = {{path = "{nested_rel}", sha256 = "{digest}"}}\n'
                 + hazards)
        safe_pin = f'{{path = "{safe_rel}", sha256 = "{sha(safe.read_bytes()).hexdigest()}"}}'
        attempt_rel = "halucinator/test-candidates/demo/evidence/recovery/" + f"{epoch}-1.toml"
        attempt = workdir / PurePosixPath(attempt_rel)
        write_lf(attempt,
                 f"schema = {version}\n"
                 f'board_id = "{BOARD_FIXTURE_ID}"\n'
                 f'lease_epoch = "{epoch}"\n'
                 "attempt_number = 1\n"
                 'started_at = "2026-01-01T00:00:00Z"\n'
                 'completed_at = "2026-01-01T00:05:00Z"\n'
                 'last_operation = "none"\n'
                 f"prior_lock = {pinned}\n"
                 'actions = ["confirmed the fictional fixture board is de-energized"]\n'
                 f"evidence = [{pinned}]\n"
                 'outcome = "verified"\n'
                 f"safe_state = {safe_pin}\n")
        for step, args in (
            ("append-recovery-attempt", ["append-recovery-attempt", *common, "--attempt-file", attempt_rel,
                                         "--attempt-number", "1", "--outcome", "verified"]),
            ("verify-board-recovery", ["verify-board-recovery", *common, "--safe-state", safe_rel]),
        ):
            rc, out, _ = run_runtime(root, workdir, args)
            if rc is None:
                return ("unposed", step, f"timed out: {_one_line(out, 160)}")
            if rc != 0:
                # A REFUSAL, not a construction failure. An earlier refusal is
                # a better refusal: the helper is entitled to reject degraded
                # evidence before it ever enters the append-only lineage.
                return ("refused", step, _one_line(out, 220))
        if degrade == "mutate-nested":
            write_lf(nested, "these bytes were altered after the attempt attested them\n")
        rc, out, _ = run_runtime(root, workdir, ["release-board", *common])
        if rc is None:
            return ("unposed", "release-board", f"timed out: {_one_line(out, 160)}")
        if rc != 0:
            return ("refused", "release-board", _one_line(out, 220))
        if live_lock_files(workdir):
            return ("unposed", "release-board",
                    "release reported success but the lock survived; the outcome is neither a clean "
                    "release nor a refusal")
        return ("released", "release-board", _one_line(out, 160))
    finally:
        shutil.rmtree(workdir, ignore_errors=True)


def check_interlock_refuses_fabricated_evidence(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, RUNTIME_RELPATH, "INTERLOCK_EVIDENCE_ABORT"):
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        if not helper.is_file():
            report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_HELPER_MISSING",
                       "the interlock helper is absent; nothing arbitrates board access")
            return
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-interlock-"))
        try:
            payload, problem = acquire_fixture_board(root, workdir)
            if payload is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_SETUP_FAILED", problem)
                return
            epoch, token = payload["lease_epoch"], payload["check_token"]
            common = ["--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                      "--epoch", epoch, "--token", token]

            # 1. A recovery attempt whose evidence file does not exist.
            rc, out, _ = run_runtime(root, workdir, [
                "append-recovery-attempt", *common, "--attempt-file", ABSENT_ATTEMPT,
                "--attempt-number", "1", "--outcome", "verified"])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "append-recovery-attempt", "INTERLOCK_TIMEOUT", out)
                return
            if rc == 0:
                report.bad(RUNTIME_RELPATH, "append-recovery-attempt", "INTERLOCK_ACCEPTS_ABSENT_EVIDENCE",
                           f"a recovery attempt naming {ABSENT_ATTEMPT!r} - a file that does not exist - was "
                           f"accepted with outcome 'verified' and exit 0. Append-only recovery lineage is the "
                           f"record a human later relies on to believe the board was made safe; an unreadable "
                           f"FileRef must be refused, not recorded. Output: {_one_line(out, 200)}")

            # 2. A safe-state observation whose record does not exist.
            rc, out, _ = run_runtime(root, workdir, [
                "verify-board-recovery", *common, "--safe-state", ABSENT_SAFE_STATE])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "verify-board-recovery", "INTERLOCK_TIMEOUT", out)
                return
            if rc == 0:
                report.bad(RUNTIME_RELPATH, "verify-board-recovery", "INTERLOCK_ACCEPTS_ABSENT_EVIDENCE",
                           f"recovery was verified against SafeStateObservation {ABSENT_SAFE_STATE!r}, which does "
                           f"not exist, and exited 0. Output: {_one_line(out, 200)}")

            # 3. The board must not be classified safe on either.
            state = lock_says(workdir, "board_state")
            phase = lock_says(workdir, "operation_phase")
            if state == "safe":
                report.bad(RUNTIME_RELPATH, "board_state", "INTERLOCK_UNSAFE_SAFE_CLAIM",
                           f"the live lock records board_state=\"safe\" (phase {phase!r}) after evidence that "
                           "cannot be read. 'Safe' is a claim about a physical device; it must never rest on a "
                           "FileRef the helper never opened")

            # 4. The decisive one: release must be refused.
            rc, out, _ = run_runtime(root, workdir, ["release-board", *common])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "release-board", "INTERLOCK_TIMEOUT", out)
                return
            if rc == 0:
                report.bad(RUNTIME_RELPATH, "release-board", "INTERLOCK_RELEASES_ON_ABSENT_EVIDENCE",
                           "the interlock released on the back of unreadable recovery and safe-state evidence. "
                           "Release hands the board to the next claimant; releasing here means the next operator "
                           f"attaches to a device whose state nobody established. Output: {_one_line(out, 200)}")
            elif live_lock_files(workdir) == []:
                report.bad(RUNTIME_RELPATH, "release-board", "INTERLOCK_RELEASES_ON_ABSENT_EVIDENCE",
                           "release-board reported failure but the lock file is gone; the interlock was released "
                           "anyway. Assert file state, not the command's report of itself")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        # 5. An unreadable lock is not an absent lock. A corrupted live lock
        #    that acquisition skips makes a claimed board look free, which is
        #    two operators on one MCU - the hazard the interlock exists for.
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-malformed-"))
        try:
            run_dir = workdir / "halucinator" / ".run"
            run_dir.mkdir(parents=True, exist_ok=True)
            (run_dir / "other.lock").write_text(
                "this is not = valid toml [[[\n", encoding="utf-8", newline="\n")
            rc, out, _ = run_runtime(root, workdir, [
                "acquire-board", "--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                "--authorization", BOARD_FIXTURE_AUTH])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_TIMEOUT", out)
            elif rc == 0:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_MALFORMED_LOCK_FAILS_OPEN",
                           "acquisition succeeded with an unparseable .lock present in .run/. A lock the helper "
                           "cannot read or structurally validate must be treated as possibly LIVE and block "
                           "acquisition; skipping it makes a corrupted claim indistinguishable from no claim, "
                           f"which permits two operators on one board. Output: {_one_line(out, 200)}")
            extra = [p for p in live_lock_files(workdir) if p.name != "other.lock"]
            if extra:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_MALFORMED_LOCK_FAILS_OPEN",
                           f"a second lock {extra[0].name!r} was created beside an unreadable one; assert file "
                           "state, not the command's report")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        # 6. Nested-reference integrity, posed as a DIFFERENTIAL so it cannot
        #    fail for the wrong reason. The baseline is the positive control:
        #    if it does not itself reach release, the question was never asked
        #    and that stays loud, because it means the record shape this
        #    harness builds has drifted from the helper's schema.
        outcome, step, detail = run_closure_scenario(root, report, degrade=None)
        where = "positive control did not reach release"
        if outcome != "released":
            report.bad(RUNTIME_RELPATH, "closure", "INTERLOCK_CLOSURE_UNPOSED",
                       f"the positive-control recovery closure ended {outcome!r} at {step!r} instead of reaching "
                       f"release, so the nested-reference assertions prove nothing. The record shape this harness "
                       f"builds is in run_closure_scenario(); align it or tell the tester what the helper now "
                       f"requires. Detail: {detail}")
        else:
            refusal_points: list[str] = []
            for degrade, code, why in (
                ("no-digest", "INTERLOCK_ACCEPTS_UNPINNED_REF",
                 "a nested FileRef carrying no sha256 was accepted all the way through a successful release. An "
                 "unpinned reference is a name, not evidence: the bytes behind it can change freely"),
                ("mutate-nested", "INTERLOCK_ACCEPTS_MUTATED_CLOSURE",
                 "a nested record was altered AFTER recovery was verified and release still succeeded. Release "
                 "must revalidate the whole closure, not only the outer attempt files"),
            ):
                outcome, step, detail = run_closure_scenario(root, report, degrade=degrade)
                if outcome == "released":
                    report.bad(RUNTIME_RELPATH, "release-board", code, why)
                elif outcome == "refused":
                    refusal_points.append(f"{degrade} at {step}")
                else:
                    report.bad(RUNTIME_RELPATH, "closure", "INTERLOCK_CLOSURE_UNPOSED",
                               f"the {degrade!r} variant ended {outcome!r} at {step!r}, which is neither a "
                               f"release nor a refusal, so it is not evidence about the helper. Detail: {detail}")
            if refusal_points:
                where = "; ".join(refusal_points)
            else:
                where = "no degraded variant was posed"
        report.ok("interlock-refuses-fabricated-evidence",
                  "the interlock helper, driven black-box through its CLI in a throwaway directory, refuses a "
                  "recovery attempt and a safe-state observation whose FileRefs do not exist, never records "
                  "board_state=safe on them, refuses to release, and refuses acquisition while an unreadable "
                  "lock is present. A positive-control closure reaches release cleanly, and each DEGRADED "
                  f"closure is refused SOMEWHERE in append -> verify -> release ({where}). The assertion is "
                  "that a degraded closure is refused, NOT where: the helper is free to refuse earlier, and "
                  "earlier is better - rejecting an unpinned FileRef at append keeps it out of the append-only "
                  "lineage entirely, rather than admitting it, calling the board safe, and catching it at "
                  "release. This proves the helper OPENS and PINS the evidence it is handed; it cannot prove "
                  "the evidence is true, that the procedure it describes is physically sufficient, or that any "
                  "operator followed it", mark)


# --- B: interlock-override-requires-ambiguity -------------------------------


def make_lock_remote_and_fresh(workdir: Path) -> bool:
    """Rewrite the fixture lock as a remote owner with a current heartbeat.

    Per the approved liveness rules a remote owner whose heartbeat is within
    120s classifies LIVE. This is the only way to construct a live lock from a
    one-shot CLI, whose own process exits immediately after writing.
    """
    locks = live_lock_files(workdir)
    if not locks:
        return False
    # Must be a CURRENT timestamp: a remote heartbeat older than 120s is
    # ambiguous, not live, and would pose the wrong question.
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    for p in locks:
        text = read_text(p)
        text = re.sub(r"^host\s*=.*$", 'host="OTHER-HOST-FIXTURE"', text, flags=re.MULTILINE)
        text = re.sub(r"^heartbeat_at\s*=.*$", f'heartbeat_at="{now}"', text, flags=re.MULTILINE)
        p.write_text(text, encoding="utf-8", newline="")
    return True


def check_interlock_override_requires_ambiguity(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, RUNTIME_RELPATH, "INTERLOCK_OVERRIDE_ABORT"):
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        if not helper.is_file():
            report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_HELPER_MISSING",
                       "the interlock helper is absent; the override path cannot be exercised")
            return
        # B1. Override must refuse when its operator record does not exist.
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-override-"))
        try:
            payload, problem = acquire_fixture_board(root, workdir)
            if payload is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_SETUP_FAILED", problem)
                return
            rc, out, _ = run_runtime(root, workdir, [
                "override-ambiguous-owner", "--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                "--override-record", ABSENT_OVERRIDE])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "override-ambiguous-owner", "INTERLOCK_TIMEOUT", out)
            elif rc == 0:
                report.bad(RUNTIME_RELPATH, "override-ambiguous-owner", "OVERRIDE_ACCEPTS_ABSENT_RECORD",
                           f"the ambiguity override succeeded while naming operator record {ABSENT_OVERRIDE!r}, "
                           "which does not exist. That record is the ONLY thing standing between a jammed "
                           "interlock and an operator's signed statement that the prior owner and its children "
                           f"are stopped or the board is physically isolated. Output: {_one_line(out, 200)}")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)

        # B2. Override must refuse a lock the helper itself classifies live.
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-override-live-"))
        try:
            payload, problem = acquire_fixture_board(root, workdir)
            if payload is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_SETUP_FAILED", problem)
                return
            if not make_lock_remote_and_fresh(workdir):
                report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_SETUP_FAILED",
                           "no lock file was written, so a live owner cannot be constructed")
                return
            rc, out, parsed = run_runtime(root, workdir, ["inspect", "--board", BOARD_FIXTURE_ID])
            classification = None
            if parsed and parsed.get("locks"):
                classification = parsed["locks"][0].get("classification")
            if classification != "live":
                report.bad(RUNTIME_RELPATH, "inspect", "INTERLOCK_SETUP_FAILED",
                           f"the constructed remote owner with a current heartbeat classified {classification!r}, "
                           "not 'live'; the override-against-a-healthy-owner case cannot be posed and must not "
                           "be reported as passing")
                return
            rc, out, _ = run_runtime(root, workdir, [
                "override-ambiguous-owner", "--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                "--override-record", ABSENT_OVERRIDE])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "override-ambiguous-owner", "INTERLOCK_TIMEOUT", out)
            elif rc == 0:
                report.bad(RUNTIME_RELPATH, "override-ambiguous-owner", "OVERRIDE_SEIZES_LIVE_OWNER",
                           "the ambiguity override seized a lock the helper had just classified LIVE. The escape "
                           "hatch exists for one situation - a recycled PID pinning an interlock live forever - "
                           "and an override that also takes a healthy owner's board is not an escape hatch, it is "
                           f"a way for two operators to drive one device. Output: {_one_line(out, 200)}")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        report.ok("interlock-override-requires-ambiguity",
                  "override-ambiguous-owner refuses an operator record that does not exist, and refuses a lock "
                  "the helper itself classifies live. This asserts the two constructible refusals; it does not "
                  "prove the override correctly ACCEPTS a genuinely ambiguous owner, and it cannot check that the "
                  "operator's confirmation is true", mark)


# --- B: interlock-recovery-can-reconnect ------------------------------------
#
# The counterpart to the refusal checks. Recovery must be REACHABLE: the
# operator has to be able to attach, reset or otherwise observe the board in
# order to establish that it is safe. If every target operation is refused
# until recovery is already verified, the only ways out are physically
# isolating every fixture or bypassing the helper - and a safety mechanism
# whose documented path can only be completed by going around it is worse than
# none, because it teaches operators to go around it.
#
# This asserts the PROPERTY, not one command spelling. The candidate entry
# points are read from the helper's own --help output, so an explicitly
# authorised recovery-operation command the coder adds later is picked up
# without editing this harness.

RECOVERY_SCOPED_OPERATIONS: tuple[str, ...] = ("attach", "reset", "halt")
NORMAL_TEST_OPERATIONS: tuple[str, ...] = ("run", "load-ram", "program-flash")
RECOVERY_ENTRY_RE = re.compile(r"\b([a-z][a-z-]*(?:board-op|board-operation|recovery-operation))\b")


def helper_commands(root: Path, workdir: Path) -> list[str]:
    """Command names the helper itself advertises, parsed from --help."""
    rc, out, _ = run_runtime(root, workdir, ["--help"])
    if rc is None:
        return []
    return sorted(set(RECOVERY_ENTRY_RE.findall(out)))


def check_interlock_recovery_can_reconnect(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, RUNTIME_RELPATH, "RECOVERY_REACHABLE_ABORT"):
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        if not helper.is_file():
            report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_HELPER_MISSING",
                       "the interlock helper is absent; the recovery path cannot be exercised")
            return
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-recovery-"))
        try:
            payload, problem = acquire_fixture_board(root, workdir)
            if payload is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_SETUP_FAILED", problem)
                return
            epoch, token = payload["lease_epoch"], payload["check_token"]
            common = ["--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                      "--epoch", epoch, "--token", token]
            rc, out, _ = run_runtime(root, workdir, ["begin-board-recovery", *common])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "begin-board-recovery", "INTERLOCK_TIMEOUT", out)
                return
            if rc != 0:
                report.bad(RUNTIME_RELPATH, "begin-board-recovery", "RECOVERY_ENTRY_REFUSED",
                           f"entering recovery was itself refused (rc={rc}). Entry must need no evidence: "
                           f"requiring evidence to start recovery is the circularity already ruled out. "
                           f"Output: {_one_line(out, 200)}")
                return
            entries = helper_commands(root, workdir) or ["before-board-op", "begin-board-operation"]
            permitted: list[str] = []
            for cmd in entries:
                for op in RECOVERY_SCOPED_OPERATIONS:
                    rc, _out, _ = run_runtime(root, workdir, [cmd, *common, "--operation", op])
                    if rc == 0:
                        permitted.append(f"{cmd} {op}")
            if not permitted:
                report.bad(RUNTIME_RELPATH, "recovery", "RECOVERY_DEADLOCKED",
                           f"while recovery-pending, every recovery-scoped operation "
                           f"({', '.join(RECOVERY_SCOPED_OPERATIONS)}) was refused across every advertised entry "
                           f"point ({', '.join(entries)}). The operator cannot observe the board to establish "
                           "that it is safe, so the documented recovery path can only be completed by physically "
                           "isolating every fixture or by bypassing the helper - which is the unsafe behaviour "
                           "the workflow forbids")
            # The rest must stay closed. Recovery is not a general unlock.
            for op in NORMAL_TEST_OPERATIONS:
                rc, _out, _ = run_runtime(root, workdir, [
                    "begin-board-operation", *common, "--operation", op])
                if rc == 0:
                    report.bad(RUNTIME_RELPATH, "begin-board-operation", "RECOVERY_OVER_PERMITS",
                               f"operation {op!r} was permitted while the board is unknown and recovery is "
                               "pending. Recovery may authorise observation, never ordinary test work")
            rc, _out, _ = run_runtime(root, workdir, ["release-board", *common])
            if rc == 0:
                report.bad(RUNTIME_RELPATH, "release-board", "RECOVERY_OVER_PERMITS",
                           "release succeeded while recovery was still pending; release must wait for "
                           "recovery-verified")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        report.ok("interlock-recovery-can-reconnect",
                  f"after begin-board-recovery the helper permits at least one recovery-scoped operation "
                  f"({', '.join(RECOVERY_SCOPED_OPERATIONS)}) through an entry point read from its own --help, "
                  f"while still refusing ordinary test operations "
                  f"({', '.join(NORMAL_TEST_OPERATIONS)}) and still refusing release until verified. This proves "
                  "the documented recovery path is REACHABLE without bypassing the interlock. It does not prove "
                  "the operations offered are sufficient to establish physical safety, and it cannot tell a "
                  "correctly scoped recovery authorisation from one so broad that recovery becomes a general "
                  "unlock beyond the three operations named here", mark)


# --- B2: recovery child sessions --------------------------------------------

RECOVERY_OPERATION_RE = re.compile(r"\b([a-z][a-z-]*recovery-operation)\b")


def recovery_operation_commands(root: Path, workdir: Path) -> list[str]:
    """Commands the helper advertises for starting a RECOVERY-scoped operation.

    Derived from the helper's own --help so a rename follows automatically.
    """
    rc, out, _ = run_runtime(root, workdir, ["--help"])
    return [] if rc is None else sorted(set(RECOVERY_OPERATION_RE.findall(out)))


def check_interlock_recovery_child_sessions(root: Path, report: Report) -> None:
    """A second recovery operation must not silently orphan the first child.

    B2. Reproduced: start recovery `attach` for one child, then - before it
    completes - start recovery `reset` for another. Both returned 0 and the
    lock retained only the second. The first probe is still running and is now
    untracked, so its completion can never be recorded or checked. That is the
    holder-death-is-not-operation-death hazard arriving by a different door.

    The assertion is a PROPERTY: the helper may refuse the second start, or it
    may legitimately track both children. What it must not do is accept the
    second and lose the first.
    """
    mark = report.mark()
    with guard(report, RUNTIME_RELPATH, "RECOVERY_CHILD_ABORT"):
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        if not helper.is_file():
            report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_HELPER_MISSING",
                       "the interlock helper is absent; concurrent recovery operations cannot be exercised")
            return
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-child-"))
        try:
            payload, problem = acquire_fixture_board(root, workdir)
            if payload is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "INTERLOCK_SETUP_FAILED", problem)
                return
            epoch, token = payload["lease_epoch"], payload["check_token"]
            common = ["--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                      "--epoch", epoch, "--token", token]
            rc, out, _ = run_runtime(root, workdir, ["begin-board-recovery", *common])
            if rc != 0:
                report.bad(RUNTIME_RELPATH, "begin-board-recovery", "INTERLOCK_SETUP_FAILED",
                           f"entering recovery failed (rc={rc}); the concurrency question cannot be posed: "
                           f"{_one_line(out, 200)}")
                return
            starts = recovery_operation_commands(root, workdir)
            if not starts:
                report.bad(RUNTIME_RELPATH, "--help", "RECOVERY_CHILD_NO_ENTRY",
                           "the helper advertises no recovery-operation command, so a recovery-scoped operation "
                           "cannot be started and this hazard cannot be posed")
                return
            start = starts[0]
            rc, out, _ = run_runtime(root, workdir, [
                start, *common, "--operation", "attach",
                "--child-kind", "process-group", "--child-identity", "child-one"])
            if rc != 0:
                report.bad(RUNTIME_RELPATH, start, "INTERLOCK_SETUP_FAILED",
                           f"the FIRST recovery operation was refused (rc={rc}), so there is no active child to "
                           f"be overwritten and the question is unposed: {_one_line(out, 200)}")
                return
            before = lock_says(workdir, "child_session") or ""
            rc, out, _ = run_runtime(root, workdir, [
                start, *common, "--operation", "reset",
                "--child-kind", "process-group", "--child-identity", "child-two"])
            after = lock_says(workdir, "child_session") or ""
            if rc is None:
                report.bad(RUNTIME_RELPATH, start, "INTERLOCK_TIMEOUT", out)
                return
            if "child-one" not in before:
                report.bad(RUNTIME_RELPATH, start, "RECOVERY_CHILD_UNRECORDED",
                           "the first recovery operation reported success but the lock records no child session "
                           f"for it: {_one_line(before, 160)}. An operation whose child is never written down "
                           "cannot be reaped or confirmed quiescent")
            elif "child-one" not in after:
                verdict = ("was ACCEPTED" if rc == 0 else "was refused, yet")
                report.bad(RUNTIME_RELPATH, start, "RECOVERY_CHILD_ORPHANED",
                           f"a second recovery operation {verdict} the lock no longer records the first child. "
                           "That probe may still be driving pins or transferring; its completion can now never "
                           "be recorded or checked, and the system believes nothing is in flight. Either refuse "
                           "the second start or track both children - never replace one silently. Lock now: "
                           f"{_one_line(after, 160)}")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        report.ok("interlock-recovery-child-sessions",
                  "a second recovery-scoped operation begun while the first is still active either is refused "
                  "or leaves the first child session still recorded - it never silently replaces it. The entry "
                  "command is read from the helper's own --help, so a rename follows automatically. This asserts "
                  "the RECORD, not the processes: nothing here observes whether a probe child is genuinely still "
                  "running, and a helper that tracked both children without being able to reap them would pass",
                  mark)


# --- B3: runtime-written locks must satisfy the static validator ------------


def check_interlock_lock_validates(root: Path, report: Report) -> None:
    """A lock the runtime helper writes must be accepted by validate.py.

    B3. The helper writes phase `recovery-active` and field `operation_scope`;
    LOCK_SCHEMA in validate.py allows neither, so a LEGITIMATE recovery makes
    the worktree invalid with MALFORMED_LOCK. Two sides of a comparison
    disagree and neither is authoritative - the same root pattern as B1.
    Asserting round-trip acceptance is the durable fix for the whole class:
    any future runtime field the static schema does not know about fails here
    immediately, whichever side turns out to be wrong.
    """
    mark = report.mark()
    with guard(report, RUNTIME_RELPATH, "LOCK_ROUNDTRIP_ABORT"):
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        validator = root / ".opencode" / "schema" / "validate.py"
        if not helper.is_file() or not validator.is_file():
            report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_HELPER_MISSING",
                       "helper or validator absent; runtime/static lock agreement cannot be checked")
            return
        source = root / ".opencode" / "schema" / "fixtures" / "valid" / "root"
        gen = (root / ".opencode" / "schema" / "fixtures" / "valid"
               / "generation-roots" / "fictional-pac")
        if not source.is_dir():
            report.bad(".opencode/schema/fixtures/valid/root", "0", "LOCK_ROUNDTRIP_SETUP_FAILED",
                       "the accepted fixture root is absent; there is no valid worktree to add a lock to")
            return
        stage_dir = Path(tempfile.mkdtemp(prefix="halucinator-lockrt-"))
        workdir = stage_dir / "root"
        try:
            shutil.copytree(source, workdir)

            def validate_now() -> tuple[int | None, str]:
                cmd = [sys.executable, str(validator), str(workdir.resolve()),
                       "--root", f"generation:fictional-pac={gen.resolve()}"]
                try:
                    proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                                          timeout=SUBPROCESS_TIMEOUT, encoding="utf-8", errors="replace")
                except subprocess.TimeoutExpired:
                    return None, f"validator timed out after {SUBPROCESS_TIMEOUT}s"
                return proc.returncode, (proc.stdout or "") + (proc.stderr or "")

            # Positive control: the untouched copy must validate, otherwise a
            # later rejection would say nothing about the lock.
            rc, out = validate_now()
            if rc != 0:
                report.bad(".opencode/schema/fixtures/valid/root", "0", "LOCK_ROUNDTRIP_SETUP_FAILED",
                           f"the copied fixture root does not validate before any lock is written (rc={rc}); "
                           f"the round-trip question cannot be posed: {_one_line(out, 240)}")
                return
            payload, problem = acquire_fixture_board(root, workdir)
            if payload is None:
                report.bad(RUNTIME_RELPATH, "acquire-board", "LOCK_ROUNDTRIP_SETUP_FAILED", problem)
                return
            epoch, token = payload["lease_epoch"], payload["check_token"]
            common = ["--stage", BOARD_FIXTURE_STAGE, "--board", BOARD_FIXTURE_ID,
                      "--epoch", epoch, "--token", token]
            rc, out = validate_now()
            if rc != 0:
                report.bad(RUNTIME_RELPATH, "acquire-board", "LOCK_NOT_VALIDATOR_CLEAN",
                           f"a worktree carrying a freshly acquired runtime lock is REJECTED by validate.py "
                           f"(rc={rc}). The helper and the static lock schema disagree about a record the helper "
                           f"itself wrote: {_one_line(out, 300)}")
            run_runtime(root, workdir, ["begin-board-recovery", *common])
            starts = recovery_operation_commands(root, workdir)
            if not starts:
                report.bad(RUNTIME_RELPATH, "--help", "LOCK_ROUNDTRIP_SETUP_FAILED",
                           "no recovery-operation command is advertised, so the recovery-phase lock shape cannot "
                           "be produced and this agreement is unproven")
                return
            rcs, outs, _ = run_runtime(root, workdir, [
                starts[0], *common, "--operation", "attach",
                "--child-kind", "process-group", "--child-identity", "recovery-child"])
            if rcs != 0:
                report.bad(RUNTIME_RELPATH, starts[0], "LOCK_ROUNDTRIP_SETUP_FAILED",
                           f"the recovery operation was refused (rc={rcs}), so the recovery-phase lock shape was "
                           f"never written and is unchecked: {_one_line(outs, 200)}")
                return
            rc, out = validate_now()
            if rc != 0:
                report.bad(RUNTIME_RELPATH, starts[0], "LOCK_NOT_VALIDATOR_CLEAN",
                           f"after a legitimate recovery operation the worktree is REJECTED by validate.py "
                           f"(rc={rc}). A recovery that makes the repository invalid forces the operator to "
                           f"choose between a clean tree and a safe board: {_one_line(out, 300)}")
        finally:
            shutil.rmtree(stage_dir, ignore_errors=True)
        report.ok("interlock-lock-validates",
                  "a worktree carrying locks the runtime helper actually wrote - after acquisition and after a "
                  "recovery-scoped operation - is still accepted by validate.py, with the untouched fixture root "
                  "as a positive control. This binds two sides that had drifted: any runtime phase or field the "
                  "static LOCK_SCHEMA does not know about now fails immediately. It does not decide WHICH side "
                  "is right when they disagree; that is a design judgement for review", mark)




STATE_RELPATH = "halucinator/state.toml"
GENERATION_RE = re.compile(r"^generation\s*=\s*(\d+)\s*$", re.MULTILINE)


def seed_state(root: Path, workdir: Path) -> int | None:
    """Copy the accepted fixture state into workdir. Returns its generation."""
    src = root / ".opencode" / "schema" / "fixtures" / "valid" / "root" / "halucinator" / "state.toml"
    if not src.is_file():
        return None
    dst = workdir / "halucinator" / "state.toml"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, dst)
    m = GENERATION_RE.search(read_text(dst))
    return int(m.group(1)) if m else None


def check_state_publish_is_atomic(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, RUNTIME_RELPATH, "STATE_PUBLISH_ABORT"):
        helper = root / PurePosixPath(RUNTIME_RELPATH)
        if not helper.is_file():
            report.bad(RUNTIME_RELPATH, "0", "INTERLOCK_HELPER_MISSING",
                       "the interlock helper is absent; publish-state cannot be exercised")
            return
        workdir = Path(tempfile.mkdtemp(prefix="halucinator-publish-"))
        try:
            gen = seed_state(root, workdir)
            if gen is None:
                report.bad(RUNTIME_RELPATH, "publish-state", "STATE_PUBLISH_SETUP_FAILED",
                           "could not seed an accepted state.toml carrying a 'generation' key")
                return
            target = workdir / "halucinator" / "state.toml"
            before = target.read_bytes()

            # A stale generation must be refused and must write nothing.
            rc, out, _ = run_runtime(root, workdir, [
                "publish-state", "--stage", BOARD_FIXTURE_STAGE, "--expect-generation", str(gen - 1)])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "publish-state", "INTERLOCK_TIMEOUT", out)
                return
            if rc == 0:
                report.bad(RUNTIME_RELPATH, "publish-state", "STATE_PUBLISH_STALE_ACCEPTED",
                           f"publish-state accepted expect-generation {gen - 1} against live generation {gen}; "
                           "compare-and-swap that does not compare is not a guard")
            if target.read_bytes() != before:
                report.bad(RUNTIME_RELPATH, "publish-state", "STATE_PUBLISH_WROTE_ON_REFUSAL",
                           "a refused publish-state modified state.toml; a refusal must leave the file untouched")
                return

            # A matching generation must actually publish.
            rc, out, _ = run_runtime(root, workdir, [
                "publish-state", "--stage", BOARD_FIXTURE_STAGE, "--expect-generation", str(gen)])
            if rc is None:
                report.bad(RUNTIME_RELPATH, "publish-state", "INTERLOCK_TIMEOUT", out)
                return
            after = target.read_bytes()
            if rc != 0:
                report.bad(RUNTIME_RELPATH, "publish-state", "STATE_PUBLISH_REFUSED_MATCH",
                           f"publish-state refused a matching generation {gen} (rc={rc}): {_one_line(out, 200)}")
                return
            if after == before:
                report.bad(RUNTIME_RELPATH, "publish-state", "STATE_PUBLISH_IS_NOOP",
                           f"publish-state reported success on a matching generation but state.toml is byte "
                           f"identical. A publish that writes nothing while reporting a matched CAS is worse "
                           f"than no publish: every caller believes its state is durable. Output: "
                           f"{_one_line(out, 200)}")
                return
            m = GENERATION_RE.search(after.decode("utf-8", "replace"))
            got = int(m.group(1)) if m else None
            if got != gen + 1:
                report.bad(RUNTIME_RELPATH, "publish-state", "STATE_PUBLISH_GENERATION_NOT_ADVANCED",
                           f"after a successful publish the generation is {got!r}, not {gen + 1}; a CAS token "
                           "that does not advance lets the next writer's stale expectation match forever")
        finally:
            shutil.rmtree(workdir, ignore_errors=True)
        report.ok("state-publish-is-atomic",
                  "publish-state refuses a stale generation without touching the file, and on a matching "
                  "generation changes the bytes and advances the generation by exactly one - asserted by reading "
                  "state.toml, never from the command's own 'cas: matched' report. This proves the WRITE "
                  "happened; it does not prove the write is crash-atomic, and durable cross-clone ordering "
                  "remains deferred", mark)


# --- D: hardware-procedure-uses-interlock -----------------------------------

# The ordered interlock protocol a target-affecting procedure must name. Order
# is asserted by first-occurrence position in the skill's own normative text.
INTERLOCK_SEQUENCE: tuple[str, ...] = (
    "acquire-board",
    "before-board-op",
    "begin-board-operation",
    "complete-board-operation",
    "release-board",
)
# At least one recovery command must appear: holder death is not operation
# death, and a procedure with no recovery leg has nowhere to go when it does.
INTERLOCK_RECOVERY: tuple[str, ...] = (
    "begin-board-recovery", "append-recovery-attempt", "verify-board-recovery",
)

# B4. Naming *a* recovery command is not enough. The reviewer found that the
# operator-facing procedure omits the recovery-scoped OPERATION start entirely
# while ordinary begin-board-operation is deliberately refused during
# recovery - so the documented route from interrupted, through recovery, to
# verified release is not executable, and the circularity that was fixed in
# the schema survives in the prose an operator actually follows.
#
# The recovery leg is therefore required to be COMPLETE and ORDERED: enter,
# perform a recovery-scoped operation, record attempts, verify. The
# operation-start command is supplied by the caller from the helper's own
# --help, so a rename follows automatically and no spelling is pinned here.
INTERLOCK_RECOVERY_SEQUENCE: tuple[str, ...] = (
    "begin-board-recovery",
    "",                      # placeholder: the advertised recovery-operation start
    "append-recovery-attempt",
    "verify-board-recovery",
)


def analyze_interlock_procedure(relpath: str, text: str,
                                recovery_start: str | None = None) -> list[tuple[str, str]]:
    """Pure analyzer: the interlock protocol is named, and named in order."""
    out: list[tuple[str, str]] = []
    flat = norm_ws(text)
    positions: dict[str, int] = {}
    for cmd in INTERLOCK_SEQUENCE:
        at = flat.find(cmd)
        if at < 0:
            out.append((
                "HARDWARE_INTERLOCK_UNUSED",
                f"{relpath}: the target-affecting procedure never invokes {cmd!r}. An interlock that the "
                "procedure needing it does not call is decoration: nothing stops a second operator, and no "
                "epoch, attempt or child session is ever recorded",
            ))
        else:
            positions[cmd] = at
    named = [c for c in INTERLOCK_SEQUENCE if c in positions]
    for earlier, later in zip(named, named[1:]):
        if positions[earlier] > positions[later]:
            out.append((
                "HARDWARE_INTERLOCK_ORDER",
                f"{relpath}: {later!r} is described before {earlier!r}. Acquisition must precede any "
                "target-affecting operation and release must follow teardown; a procedure written in the "
                "other order tells the operator to drive the board before claiming it",
            ))
    if not any(c in flat for c in INTERLOCK_RECOVERY):
        out.append((
            "HARDWARE_INTERLOCK_NO_RECOVERY",
            f"{relpath}: names no recovery command ({', '.join(INTERLOCK_RECOVERY)}). Holder death is not "
            "operation death; a procedure with no recovery leg leaves the board in an unknown state with no "
            "documented way out",
        ))
        return out
    # The recovery leg must be EXECUTABLE end to end, in order. A procedure
    # that enters recovery and then tells the operator to run the ordinary
    # operation command - which is refused during recovery - is a dead end.
    sequence = [c if c else recovery_start for c in INTERLOCK_RECOVERY_SEQUENCE]
    if recovery_start is None:
        sequence = [c for c in sequence if c]
    positions = {}
    for cmd in sequence:
        if cmd is None:
            continue
        at = flat.find(cmd)
        if at < 0:
            out.append((
                "HARDWARE_INTERLOCK_RECOVERY_INCOMPLETE",
                f"{relpath}: the recovery leg never names {cmd!r}, so an operator cannot get from interrupted, "
                "through recovery, to verified release by following this procedure. The ordinary operation "
                "command is refused while the board is unknown, so omitting the recovery-scoped one leaves "
                "physical isolation or bypassing the interlock as the only routes",
            ))
        else:
            positions[cmd] = at
    ordered = [c for c in sequence if c in positions]
    for earlier, later in zip(ordered, ordered[1:]):
        if positions[earlier] > positions[later]:
            out.append((
                "HARDWARE_INTERLOCK_RECOVERY_ORDER",
                f"{relpath}: the recovery leg describes {later!r} before {earlier!r}; recovery must be entered, "
                "then performed, then recorded, then verified",
            ))
    return out


_HW_GOOD = (
    "8. **Acquire the interlock.** Run acquire-board for this board before touching the target.\n"
    "9. **Precheck.** Run before-board-op, then begin-board-operation to record the attempt and child session.\n"
    "10. **Run.** Load and run, then complete-board-operation once the child and its descendants have exited.\n"
    "11. **Teardown.** Collect the safe-state observation, then release-board.\n"
    "If the holder died, declare the board unknown and use begin-board-recovery, then "
    "begin-recovery-operation to attach under recovery scope, then append-recovery-attempt for each action, "
    "then verify-board-recovery before any release.\n"
)

_HW_CASES: tuple[tuple[str, str, str], ...] = (
    ("no interlock at all",
     "8. Attach the probe, load the image, run it, then follow the documented safe teardown.\n",
     "HARDWARE_INTERLOCK_UNUSED"),
    ("acquisition after the operation",
     _HW_GOOD.replace("Run acquire-board for this board before touching the target.",
                      "Drive the board first.").replace(
         "then release-board.", "then acquire-board and release-board."),
     "HARDWARE_INTERLOCK_ORDER"),
    ("no recovery leg",
     _HW_GOOD.replace(
         "If the holder died, declare the board unknown and use begin-board-recovery, then "
         "begin-recovery-operation to attach under recovery scope, then append-recovery-attempt for each "
         "action, then verify-board-recovery before any release.\n", ""),
     "HARDWARE_INTERLOCK_NO_RECOVERY"),
    ("release dropped",
     _HW_GOOD.replace("then release-board.", "then stop."), "HARDWARE_INTERLOCK_UNUSED"),
    # B4: the exact shape the reviewer found in the live procedure.
    ("recovery leg omits the recovery-scoped operation",
     _HW_GOOD.replace("then begin-recovery-operation to attach under recovery scope, ", ""),
     "HARDWARE_INTERLOCK_RECOVERY_INCOMPLETE"),
    ("recovery leg verifies before it acts",
     _HW_GOOD.replace(
         "use begin-board-recovery, then begin-recovery-operation to attach under recovery scope, then "
         "append-recovery-attempt for each action, then verify-board-recovery before any release.",
         "use verify-board-recovery, then begin-board-recovery, then begin-recovery-operation to attach, then "
         "append-recovery-attempt."),
     "HARDWARE_INTERLOCK_RECOVERY_ORDER"),
)


def interlock_procedure_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_interlock_procedure("x.md", _HW_GOOD, "begin-recovery-operation")
    if clean:
        problems.append(f"the conforming interlocked procedure was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _HW_CASES:
        codes = [c for c, _ in analyze_interlock_procedure("x.md", text, "begin-recovery-operation")]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_hardware_procedure_uses_interlock(root: Path, report: Report) -> None:
    """Every skill that performs target operations must drive the interlock.

    Subject derivation: skills whose PARSED contract emitter is the tester
    agent - the same derivation validation-guidance-isolation uses - scanned
    across SKILL.md and every reference file, because the normative
    hardware-execution procedure lives in a reference.
    """
    mark = report.mark()
    with guard(report, ".opencode/skills", "HARDWARE_INTERLOCK_ABORT"):
        for problem in interlock_procedure_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_interlock_procedure", "HARDWARE_INTERLOCK_FIXTURE",
                       f"the interlock-procedure analyzer failed its in-memory near-misses: {problem}")
        paths = skill_paths(root)
        contracts = skill_contracts(root)
        subjects = [n for n in skills_with_emitter(contracts, TESTER_AGENT) if n in paths]
        if not subjects:
            report.bad(".opencode/skills", "0", "HARDWARE_INTERLOCK_NO_TARGETS",
                       f"no skill declares {TESTER_AGENT!r} as its emitter, so the hardware procedure is "
                       "asserted against nothing")
            return
        scanned = 0
        probe = Path(tempfile.mkdtemp(prefix="halucinator-hwhelp-"))
        try:
            starts = recovery_operation_commands(root, probe)
        finally:
            shutil.rmtree(probe, ignore_errors=True)
        recovery_start = starts[0] if starts else None
        if recovery_start is None:
            report.bad(RUNTIME_RELPATH, "--help", "HARDWARE_INTERLOCK_NO_RECOVERY_ENTRY",
                       "the helper advertises no recovery-operation command, so the procedure cannot name one "
                       "and the recovery leg cannot be executable")
        for name in sorted(subjects):
            skill = paths[name]
            tree = [skill] + skill_reference_paths(root, skill)
            blob = "\n".join(read_text(p) for p in tree if p.is_file())
            relpath = rel(root, skill)
            scanned += 1
            for code, message in analyze_interlock_procedure(relpath, blob, recovery_start):
                report.bad(relpath, "hardware-execution", code, message)
        report.ok("hardware-procedure-uses-interlock",
                  f"{scanned} tester-emitted skill tree(s) name the whole interlock protocol - acquire, "
                  f"precheck, operation start, operation completion, release - in that order, AND carry a "
                  f"recovery leg that is executable end to end: enter recovery, perform a recovery-scoped "
                  f"operation ({recovery_start!r}, read from the helper's own --help so a rename follows), "
                  f"record attempts, verify - in that order (analyzer self-tested against {len(_HW_CASES)} "
                  "near-misses). This asserts the PROCEDURE TEXT and its order only. It cannot prove an agent "
                  "ran the commands, and a procedure that names them in the right order while describing the "
                  "wrong actions between them passes", mark)


# --- E: no-invented-hardware-in-corpus --------------------------------------
#
# Discriminator. There is NO lexical test that separates a real part number
# from an invented one: MCXA256 exists and AX100 does not, and they are the
# same shape. So this check never tries. It asserts three things that are
# decidable from the corpus's own rules instead:
#
#   (a) the spec permits exactly ONE example target, the fictional fixture, so
#       any other target-id or vendor occupying a halucinator/docs/<id>/ or
#       halucinator/pac/<vendor>/ path in shipped prose is invented by
#       construction - no hardware knowledge needed;
#   (b) a part-number-shaped token standing in a CITATION - beside a manual,
#       datasheet, section, table or revision - is a hardware claim, and the
#       only hardware this toolkit legitimately cites is the north-star family
#       it is built from. This half rests on a small allowlist and is the only
#       part that could ever need hand-maintenance; and
#   (c) retired schema-1 citation leaves, which is a pure schema fact and is
#       where the invented manual and section number are actually carried.

# The one permitted example target, its vendor slug, and the literal
# placeholders that stand for a real one.
PERMITTED_TARGET_SEGMENTS: frozenset[str] = frozenset({
    "unobtainium-circuits-uc-not-a-real-mcu-0001",
    "unobtainium",
    "<target-id>",
    "<vendor>",
})
TARGET_SEGMENT_RE = re.compile(r"halucinator/(?:docs|pac)/([A-Za-z0-9<>_.-]+)/")

# Hardware this toolkit genuinely references, per AGENTS.md's two references.
# Hand-maintained, and declared as such in the PASS line.
CITABLE_HARDWARE_RE = re.compile(r"^(?:MCXA[0-9A-Z]*|STM32[0-9A-Z]*|CORTEX-?M[0-9]*)$", re.IGNORECASE)
# Shapes that are acronyms, standards or units rather than part numbers.
PART_SHAPE_RE = re.compile(
    r"\b(?!SHA|UTF|RFC|ISO|IEC|ASCII|TOML|JSON|HTML|XML|SVD|PAC|HAL|DMA|GPIO|SPI|I2C|USB|NVIC|RAM|ROM|CPU"
    r"|MHZ|KHZ|GHZ|CRC|FIFO|UART|LPUART|ARM|AHB|APB|SRAM|MMIO|CMSIS)"
    r"[A-Z][A-Z0-9]{1,7}[0-9]{2,5}[A-Z0-9-]*\b")
CITATION_MARKER_RE = re.compile(
    r"reference manual|datasheet|data sheet|user guide|errata|\bsection \d|\btable \d|\bfigure \d"
    r"|\brev\.? ?\d|\bdocument [A-Z]", re.IGNORECASE)
# How close a part-number-shaped token must stand to a citation marker before
# it counts as the subject of that citation.
CITATION_WINDOW = 160

RETIRED_CITATION_RES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("[[driver.test_hardware_facts]] as a table array",
     re.compile(r"\[\[\s*driver\.test_hardware_facts\s*\]\]")),
    ("driver.test_hardware_facts.document",
     re.compile(r"driver\.test_hardware_facts\.document\b")),
    ("driver.test_hardware_facts.revision",
     re.compile(r"driver\.test_hardware_facts\.revision\b")),
    ("driver.test_hardware_facts.locator",
     re.compile(r"driver\.test_hardware_facts\.locator\b")),
)


def analyze_invented_hardware(relpath: str, text: str) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for seg in sorted(set(TARGET_SEGMENT_RE.findall(text))):
        if seg not in PERMITTED_TARGET_SEGMENTS:
            out.append((
                "INVENTED_TARGET_EXAMPLE",
                f"{relpath}: worked example uses target/vendor segment {seg!r}. The milestone permits exactly "
                "one example target, the transparently fictional fixture, precisely so that no reader can "
                "mistake example material for a hardware fact",
            ))
    # Proximity, not sentence co-occurrence. A TOML worked example is one
    # enormous "sentence" to any punctuation splitter, so co-occurrence there
    # would pair a token with a citation marker two thousand characters away
    # and the finding would not support its own message.
    flat = norm_ws(text)
    seen: set[tuple[str, int]] = set()
    for m in CITATION_MARKER_RE.finditer(flat):
        lo = max(0, m.start() - CITATION_WINDOW)
        hi = min(len(flat), m.end() + CITATION_WINDOW)
        window = flat[lo:hi]
        for tok in sorted(set(PART_SHAPE_RE.findall(window))):
            if CITABLE_HARDWARE_RE.match(tok) or (tok, lo) in seen:
                continue
            seen.add((tok, lo))
            out.append((
                "INVENTED_CITATION_SUBJECT",
                f"{relpath}: {tok!r} stands within {CITATION_WINDOW} characters of the citation marker "
                f"{m.group(0)!r}: ...{window[max(0, m.start() - lo - 60):m.start() - lo + 90]!r}... Register "
                "offsets, revisions and section numbers come from a real manual or they do not exist; a "
                "plausible-looking citation is worse than none, because it reads as evidence",
            ))
    for label, rx in RETIRED_CITATION_RES:
        if rx.search(text):
            out.append((
                "RETIRED_CITATION_LEAF",
                f"{relpath}: carries the retired schema-1 form {label}. Schema 2 makes "
                "driver.test_hardware_facts a list of verified assertion IDs precisely so a driver cannot "
                "originate a citation; the old block is where invented manuals and section numbers live",
            ))
    return out


_INVENT_GOOD = (
    "For exact MCU `unobtainium-circuits-uc-not-a-real-mcu-0001` the coordinator dispatches `uart`.\n"
    "notes = { path = \"halucinator/docs/unobtainium-circuits-uc-not-a-real-mcu-0001/notes/FACTS.md\" }\n"
    "pac = \"halucinator/pac/unobtainium/unobtainium-pac\"\n"
    "The roadmap lives at halucinator/docs/<target-id>/notes/ROADMAP.md.\n"
    "Read `embassy-mcxa/DEVGUIDE.md` and the MCXA256 clock tree; section 3 of that guide is the model.\n"
    "Install poppler-utils so that pdftotext -layout is available.\n"
    "driver.facts_handoff and driver.test_hardware_facts carry verified assertion IDs.\n"
)

_INVENT_CASES: tuple[tuple[str, str, str], ...] = (
    ("invented target directory",
     "notes = { path = \"halucinator/docs/acme-ax100/notes/FACTS.md\" }\n", "INVENTED_TARGET_EXAMPLE"),
    ("invented vendor directory",
     "source = \"halucinator/pac/acme/data/svd/x/sources/x.svd\"\n", "INVENTED_TARGET_EXAMPLE"),
    ("invented manual citation",
     "document = \"AX100 Reference Manual, document AX100RM\"\nlocator = \"Section 42.5.3, Table 42-18\"\n",
     "INVENTED_CITATION_SUBJECT"),
    ("retired citation table array",
     "[[driver.test_hardware_facts]]\nsource_id = \"doc-001\"\n", "RETIRED_CITATION_LEAF"),
    ("retired citation leaf reference",
     "| Cited hardware facts | `driver.test_hardware_facts.document`, `.revision` |\n",
     "RETIRED_CITATION_LEAF"),
)

# Real, legitimate corpus material that must NOT trip the analyzer. A rule that
# forbids citing the north-star HAL or naming a real tool is unusable.
_INVENT_CLEAN_CASES: tuple[tuple[str, str], ...] = (
    ("north-star reference", "See `embassy-mcxa/DEVGUIDE.md` section 4 for the MCXA577 clock tree.\n"),
    ("pinned upstream URL",
     "https://raw.githubusercontent.com/embassy-rs/nxp-pac/0c2b68a1c1badce2cf09ba8bb3aae25e72776b2b/"
     "nxp-pac/Cargo.toml documents the feature set.\n"),
    ("real tool names", "Install poppler-utils or xpdf-utils, then rerun pdftotext -layout.\n"),
    ("standards and units in a citation",
     "Timestamps are RFC3339 UTC; see section 2 of the datasheet template for the SHA256 field.\n"),
    ("fictional fixture manual",
     "document = \"FICTIONAL FIXTURE REFERENCE MANUAL\"\nrevision = \"Rev 0\"\n"),
    ("schema-2 driver leaves",
     "driver.facts_handoff and driver.test_hardware_facts reference verified assertion IDs.\n"),
)


def invented_hardware_analyzer_failures() -> list[str]:
    problems: list[str] = []
    clean = analyze_invented_hardware("x.md", _INVENT_GOOD)
    if clean:
        problems.append(f"the conforming fictional-target sample was rejected with {[c for c, _ in clean]}; "
                        "an over-broad rule here is unusable")
    for name, text in _INVENT_CLEAN_CASES:
        codes = [c for c, _ in analyze_invented_hardware("x.md", text)]
        if codes:
            problems.append(f"legitimate corpus material {name!r} was rejected with {codes}")
    for name, text, expected in _INVENT_CASES:
        codes = [c for c, _ in analyze_invented_hardware("x.md", text)]
        if expected not in codes:
            problems.append(f"near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
    return problems


def check_no_invented_hardware_in_corpus(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "INVENTED_HARDWARE_ABORT"):
        for problem in invented_hardware_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_invented_hardware", "INVENTED_HARDWARE_FIXTURE",
                       f"the invented-hardware analyzer failed its in-memory fixtures: {problem}")
        files = [p for p in governed_markdown(root) if not is_fixture_payload(root, p)]
        if not files:
            report.bad(".opencode", "0", "INVENTED_HARDWARE_NO_TARGETS",
                       "no governed non-fixture Markdown discovered; the rule is asserted against nothing")
            return
        for p in files:
            relpath = rel(root, p)
            for code, message in analyze_invented_hardware(relpath, read_text(p)):
                report.bad(relpath, "hardware-fact", code, message)
        report.ok("no-invented-hardware-in-corpus",
                  f"across {len(files)} governed non-fixture Markdown files: every worked example uses the one "
                  f"permitted fictional target, no part-number-shaped token stands as the subject of a manual / "
                  f"datasheet / section citation outside the north-star families this toolkit is built from, and "
                  f"no retired schema-1 citation block survives (analyzer self-tested against "
                  f"{len(_INVENT_CASES)} near-misses and {len(_INVENT_CLEAN_CASES)} legitimate samples that must "
                  "NOT trip). LIMITS: no lexical test can tell a real part number from an invented one - MCXA256 "
                  "and AX100 are the same shape - so the citation half rests on a HAND-MAINTAINED allowlist of "
                  "citable families and will not notice an invented part that resembles one. A fabricated "
                  "register offset, bit position or reset value in prose matches nothing here at all", mark)


# --- F: citation-path-tested ------------------------------------------------

SCHEMA_TEST_DIR = ".opencode/schema"
SCHEMA_TEST_PATTERN = "test_*.py"
SCHEMA_TEST_TIMEOUT = 300

CITATION_TEST_CASES: tuple[tuple[str, str], ...] = (
    ("missing pdftotext fails closed", r"missing.?(pdftotext|tool|binary)|(pdftotext|tool|binary).?(absent|missing)"),
    ("verifier timeout", r"timeout|timed.?out"),
    ("PDF page error", r"page.?(error|invalid|out.?of.?range|rejected)|bad.?page|invalid.?page"),
    ("Unicode / NFKC normalization", r"unicode|nfkc|casefold|soft.?hyphen"),
    ("digit-safe hyphen joining", r"hyphen|digit.?safe|line.?break.?join"),
    ("interleaving gap bound", r"interleav|gap.?bound|token.?gap|skipped.?token"),
    ("bounded diagnostic payload", r"bounded|truncat|payload.?limit|closest.?candidate|nearest.?candidate"),
    # M6 recheck: the external-process boundary must actually be crossed.
    # Injecting an already-constructed CitationFailure never executes
    # run_pdftotext, so a regression in command construction or in the
    # subprocess exception translation passes every test.
    ("production run_pdftotext wrapper reached", r"run.?pdftotext"),
    ("subprocess argument array asserted", r"arg(?:ument)?.?(?:array|list|v)|cmd.?(?:array|list)|argv"),
    ("subprocess output bound asserted", r"output.?(?:bound|cap|limit)|mib|max.?output|overflow"),
)


def _citation_case_failures() -> list[str]:
    """Self-test the coverage patterns: recognise a plausible suite, reject an empty one."""
    sample = '''
def test_missing_pdftotext_fails_closed(): pass
def test_runner_timeout_is_unverified(): pass
def test_invalid_page_rejected_with_remedy(): pass
def test_nfkc_casefold_unicode_excerpt(): pass
def test_digit_safe_hyphen_join_fifo_zero(): pass
def test_interleaving_gap_bound_enforced(): pass
def test_bounded_diagnostic_payload_closest_candidate(): pass
def test_run_pdftotext_builds_argv_and_timeout(): pass
def test_run_pdftotext_output_bound_mib_overflow(): pass
'''
    surface = runtime_test_surface(sample)
    missed = [label for label, pat in CITATION_TEST_CASES if not re.search(pat, surface)]
    if missed:
        return [f"the coverage patterns did not recognise a plausibly named citation suite: {missed}"]
    empty = runtime_test_surface("def helper(): pass\n")
    matched = [label for label, pat in CITATION_TEST_CASES if re.search(pat, empty)]
    if matched:
        return [f"the coverage patterns matched an EMPTY suite for {matched}; they would pass vacuously"]
    return []


def check_citation_path_tested(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, SCHEMA_TEST_DIR, "CITATION_TESTS_ABORT"):
        for problem in _citation_case_failures():
            report.bad("tools/selfcheck.py", "CITATION_TEST_CASES", "CITATION_TESTS_FIXTURE",
                       f"the citation coverage patterns failed their self-test: {problem}")
        d = root / PurePosixPath(SCHEMA_TEST_DIR)
        modules = sorted(d.glob(SCHEMA_TEST_PATTERN)) if d.is_dir() else []
        if not modules:
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_MISSING",
                       f"no {SCHEMA_TEST_PATTERN} module under {SCHEMA_TEST_DIR}; the citation verifier - the "
                       "gate this milestone exists for - has no executable test at all")
            return
        surface = ""
        joined_source = ""
        for p in modules:
            try:
                text = read_text(p)
                surface += runtime_test_surface(text) + " "
                joined_source += text + "\n"
            except SyntaxError as exc:
                report.bad(rel(root, p), "0", "CITATION_TESTS_UNPARSEABLE",
                           f"test module does not parse, so its coverage cannot be derived: {exc}")
                return
        # The boundary must be crossed, not simulated. A suite that only
        # constructs a CitationFailure never executes the wrapper it claims to
        # test, so require both the production symbol and an injected
        # subprocess seam in the same corpus of tests.
        if "run_pdftotext" not in joined_source:
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_SKIP_BOUNDARY",
                       "no test module names run_pdftotext. Injecting an already-built CitationFailure exercises "
                       "the caller's error path and never the external-process wrapper, so a regression in the "
                       "argument array, the timeout, or the translation of a subprocess exception passes")
        elif not re.search(r"subprocess\.run|\bsubprocess\b.*\brun\b|monkeypatch|fake_run|stub_run|patch\(",
                           joined_source):
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_SKIP_BOUNDARY",
                       "run_pdftotext is named but no subprocess seam is injected beneath it; the wrapper must be "
                       "driven with a substituted runner so the argument array, timeout and output bound can be "
                       "asserted without depending on a real pdftotext being installed")
        uncovered = [label for label, pat in CITATION_TEST_CASES if not re.search(pat, surface)]
        if uncovered:
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_UNCOVERED",
                       f"{len(uncovered)} required citation case(s) are named by no test: {'; '.join(uncovered)}")
        cmd = [sys.executable, "-m", "unittest", "discover", "-s", SCHEMA_TEST_DIR,
               "-t", SCHEMA_TEST_DIR, "-p", SCHEMA_TEST_PATTERN]
        try:
            proc = subprocess.run(cmd, cwd=str(root), capture_output=True, text=True,
                                  timeout=SCHEMA_TEST_TIMEOUT, encoding="utf-8", errors="replace")
        except subprocess.TimeoutExpired:
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_TIMEOUT",
                       f"unittest discovery did not finish in {SCHEMA_TEST_TIMEOUT}s; a hang is a failure")
            return
        out = (proc.stdout or "") + (proc.stderr or "")
        # Check emptiness FIRST: unittest exits non-zero on "NO TESTS RAN", and
        # reporting that as a test failure hides what is actually wrong.
        if re.search(r"^Ran 0 tests", out, re.MULTILINE) or "NO TESTS RAN" in out:
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_EMPTY",
                       f"unittest discovery under {SCHEMA_TEST_DIR} ran 0 tests. The citation gate is the "
                       "milestone's headline claim and has no executable test: nothing exercises missing "
                       "pdftotext, timeout, page errors, normalization or the gap bound")
            return
        if proc.returncode != 0:
            report.bad(SCHEMA_TEST_DIR, "0", "CITATION_TESTS_FAILED",
                       f"unittest discovery exited {proc.returncode}: {_one_line(out, 500)}")
            return
        report.ok("citation-path-tested",
                  f"{len(modules)} discovered test module(s) under {SCHEMA_TEST_DIR} run green under unittest "
                  f"discovery and name all {len(CITATION_TEST_CASES)} required citation cases - missing "
                  "pdftotext, timeout, PDF page error, Unicode/NFKC, digit-safe hyphen joining, the "
                  "interleaving gap bound, and the bounded diagnostic payload. AS WITH runtime-protocol-tests, "
                  "COVERAGE IS DERIVED FROM TEST NAMES AND DOCSTRINGS: a test named for a case it does not "
                  "actually exercise is invisible here, and nothing checks that the assertions inside are the "
                  "right ones", mark)


# ===========================================================================
# M7 checks - the user-facing documentation set
# ===========================================================================
#
# M7 added four root-level user documents. They were placed at the repository
# ROOT rather than under docs/ for a specific reason: governed_markdown()
# discovers root *.md, so `links` and `no-invented-hardware-in-corpus` govern
# them the moment they land, with no new code and no new discovery path. That
# is regression-only coverage inherited by placement, and it is deliberate.
#
# Three invariants were NOT inherited and are implemented below.


# --- M7-A: markdown-anchor-targets ------------------------------------------
#
# `links` resolves the FILE half of a relative Markdown link and stops there:
# its own contract says "Anchor existence is out of scope". So
# `AGENTS.md#artifact-storage-and-handoff` is checked only as far as AGENTS.md
# existing, and renaming the heading breaks the link silently. M7 made that
# live risk rather than theoretical - AGENTS.md grew a "Start here" navigation
# table and is now the target of nine distinct anchors from three documents.
#
# Every analyzer here is a pure function of text so it can be self-tested
# against near-misses before the live corpus is trusted.

ATX_HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*(?:#+[ \t]*)?$")
FENCE_LINE_RE = re.compile(r"^\s*(`{3,}|~{3,})")


def blank_fenced_blocks(text: str) -> str:
    """Blank fenced code blocks, preserving line count and INLINE code spans.

    Deliberately not strip_code(). strip_code also blanks inline code spans,
    which destroys exactly the heading text the anchors are computed from:
    `### 1. \x60embassy-mcxa\x60 - the north star` would slug to a row of
    hyphens and every correct link into it would be reported broken. Headings
    inside a fenced block are still not headings, so the fences must go.
    """
    out: list[str] = []
    fence: str | None = None
    for line in text.split("\n"):
        m = FENCE_LINE_RE.match(line)
        if fence is None:
            if m:
                fence = m.group(1)[0] * 3
                out.append("")
                continue
        else:
            if m and m.group(1)[0] * 3 == fence:
                fence = None
            out.append("")
            continue
        out.append(line)
    return "\n".join(out)


def github_slug(heading: str) -> str:
    """GitHub's heading-anchor slug, as understood here.

    Lowercase; inline HTML dropped; a Markdown link reduced to its text;
    backticks, emphasis and strikethrough markers stripped; every remaining
    character outside [0-9a-z _-] DELETED; spaces then become hyphens.

    The deletion-before-substitution order is what produces a DOUBLE hyphen
    from a spaced em dash: the dash itself vanishes and each flanking space
    survives to become a hyphen. That is why `#1-embassy-mcxa--the-north-star`
    is the correct anchor for `1. \x60embassy-mcxa\x60 - the north star` and
    not a typo.
    """
    s = heading.strip().lower()
    s = re.sub(r"<[^>]*>", "", s)
    s = re.sub(r"\[([^\]\[]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"[`*_~]", "", s)
    s = re.sub(r"[^0-9a-z \-_]", "", s)
    return s.replace(" ", "-")


def heading_anchors(text: str) -> list[str]:
    """Every anchor a Markdown document offers, in document order.

    Repeated slugs are disambiguated the way GitHub does it: the first
    occurrence keeps the bare slug and the nth gets a `-<n-1>` suffix.
    """
    seen: dict[str, int] = {}
    out: list[str] = []
    for line in blank_fenced_blocks(text).split("\n"):
        m = ATX_HEADING_RE.match(line)
        if not m:
            continue
        base = github_slug(m.group(2))
        n = seen.get(base, 0)
        seen[base] = n + 1
        out.append(base if n == 0 else f"{base}-{n}")
    return out


# (heading line, expected anchor). Each row is a shape the live corpus
# actually contains; a slugger that gets any of them wrong would report
# correct links as broken, which is the expensive failure for this check.
_ANCHOR_SLUG_CASES: tuple[tuple[str, str], ...] = (
    ("## Artifact storage and handoff", "artifact-storage-and-handoff"),
    ("### 1. `embassy-mcxa` \u2014 the north star", "1-embassy-mcxa--the-north-star"),
    ("### 2. \"Making Smaller Things\" \u2014 the design discipline",
     "2-making-smaller-things--the-design-discipline"),
    ("### Why `hal-tester` is blindfolded", "why-hal-tester-is-blindfolded"),
    ("## Known skill/agent ownership conflicts", "known-skillagent-ownership-conflicts"),
    ("# target-id", "target-id"),
    ("###### Deep  spacing", "deep--spacing"),
    ("## Trailing hashes ##", "trailing-hashes"),
)

# Text samples whose anchor SET is asserted, for the rules a single heading
# cannot express: duplicate disambiguation, and fenced content that only looks
# like a heading.
_ANCHOR_DOC_CASES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("duplicate headings are disambiguated", "## Notes\n\n## Notes\n\n## Notes\n",
     ("notes", "notes-1", "notes-2")),
    ("a fenced shell comment is not a heading", "```sh\n# not a heading\n```\n\n## Real\n",
     ("real",)),
    ("inline code survives into the slug", "## The `Gate` contract\n", ("the-gate-contract",)),
    ("a link in a heading keeps only its text", "## See [the pipeline](AGENTS.md#the-pipeline)\n",
     ("see-the-pipeline",)),
)


def anchor_analyzer_failures() -> list[str]:
    problems: list[str] = []
    for heading, expected in _ANCHOR_SLUG_CASES:
        got = heading_anchors(heading + "\n")
        if got != [expected]:
            problems.append(f"heading {heading!r} slugged to {got} rather than [{expected!r}]")
    for name, text, expected in _ANCHOR_DOC_CASES:
        got = tuple(heading_anchors(text))
        if got != expected:
            problems.append(f"sample {name!r} produced anchors {got} rather than {expected}")
    # Non-vacuity: the slugger must actually discriminate. A function that
    # returned its input, or the empty string, would satisfy nothing above by
    # accident, but assert it anyway - a self-test that cannot fail is decor.
    if github_slug("## A") == github_slug("## B"):
        problems.append("the slugger maps distinct headings to one anchor; it discriminates nothing")
    return problems


def fragment_links(text: str) -> list[tuple[int, str, str, str]]:
    """(line, raw target, path part, fragment) for every relative link with a fragment.

    Link extraction runs over strip_code() output, exactly as `links` does, so
    a link inside a fenced example is not a link. External schemes and
    protocol-relative targets are skipped for the same reason `links` skips
    them: nothing here can resolve them.
    """
    out: list[tuple[int, str, str, str]] = []
    for lineno, line in enumerate(strip_code(text).split("\n"), start=1):
        for m in LINK_RE.finditer(line):
            target = m.group(1).strip()
            if "#" not in target:
                continue
            low = target.lower()
            if low.startswith(IGNORED_SCHEMES) or low.startswith("//"):
                continue
            if (re.match(r"^[A-Za-z][A-Za-z0-9+.-]*:", target)
                    and not target.startswith("./") and not target.startswith("../")):
                continue
            bare, fragment = target.split("#", 1)
            if not fragment:
                continue
            out.append((lineno, target, bare.split("?", 1)[0], fragment))
    return out


MAX_ANCHOR_SUGGESTIONS = 6


def check_markdown_anchor_targets(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, "tools/selfcheck.py", "ANCHOR_ABORT"):
        for problem in anchor_analyzer_failures():
            report.bad("tools/selfcheck.py", "github_slug", "ANCHOR_SLUG_FIXTURE",
                       f"the anchor slugger failed its in-memory fixtures: {problem}")
        files = [p for p in governed_markdown(root) if not is_fixture_payload(root, p)]
        if not files:
            report.bad(".opencode", "0", "ANCHOR_NO_TARGETS",
                       "no governed non-fixture Markdown discovered; anchor resolution is asserted against nothing")
            return
        anchors: dict[Path, list[str] | None] = {}

        def anchors_of(p: Path) -> list[str] | None:
            if p not in anchors:
                try:
                    anchors[p] = heading_anchors(read_text(p)) if p.is_file() else None
                except OSError:
                    anchors[p] = None
            return anchors[p]

        total = 0
        same_file = 0
        checked = 0
        for path in files:
            r = rel(root, path)
            try:
                text = read_text(path)
            except OSError as exc:
                report.bad(r, "0", "ANCHOR_UNREADABLE", f"cannot read file: {exc}")
                continue
            checked += 1
            for lineno, target, bare, fragment in fragment_links(text):
                if not bare:
                    resolved = path
                    same_file += 1
                elif bare.startswith("/"):
                    resolved = (root / urllib.parse.unquote(bare).lstrip("/")).resolve()
                else:
                    resolved = (path.parent / urllib.parse.unquote(bare)).resolve()
                try:
                    resolved.relative_to(root.resolve())
                except ValueError:
                    # `links` owns this diagnostic; reporting it twice would
                    # only make one defect look like two.
                    continue
                available = anchors_of(resolved)
                if available is None:
                    # Missing or unreadable target file. `links` already fails
                    # on it with LINK_BROKEN; do not double-report.
                    continue
                total += 1
                if urllib.parse.unquote(fragment) in available:
                    continue
                near = [a for a in available
                        if a.startswith(fragment[:8]) or fragment.startswith(a[:8])][:MAX_ANCHOR_SUGGESTIONS]
                hint = f"; closest existing anchor(s): {', '.join(near)}" if near else (
                    f"; that file offers {len(available)} anchor(s)")
                report.bad(r, str(lineno), "ANCHOR_BROKEN",
                           f"link {target!r} names no heading in {rel(root, resolved)}. The file resolves, so "
                           f"`links` passes it; the fragment does not{hint}")
        # Fail CLOSED on an empty subject set, in the idiom the rest of this
        # harness uses. Having discovered Markdown is not the same as having
        # discovered something to assert about: if every fragment link were
        # deleted, or fragment_links() silently stopped matching, `total`
        # would be zero and a PASS line claiming that all such links resolve
        # would be asserting over the empty set. That is the exact shape of
        # vacuity the M4 discovery-closure work exists to prevent.
        if total == 0:
            report.bad(".opencode", "0", "ANCHOR_NO_LINKS",
                       f"no relative Markdown link carrying a fragment was discovered across {checked} governed "
                       "non-fixture file(s); anchor resolution is asserted against nothing. Either the corpus "
                       "genuinely stopped cross-referencing headings, or link extraction has stopped matching")
            return
        report.ok("markdown-anchor-targets",
                  f"{total} relative Markdown links carrying a fragment across {checked} governed non-fixture "
                  f"files ({same_file} of them same-file `#anchor` links, which `links` skips entirely) name a "
                  f"heading that exists in the file they resolve to, with duplicate headings disambiguated the "
                  f"way GitHub disambiguates them (slugger self-tested against {len(_ANCHOR_SLUG_CASES)} heading "
                  f"shapes and {len(_ANCHOR_DOC_CASES)} document samples; the check fails closed rather than "
                  f"passing when the fragment-link set is empty). LIMITS: this implements GITHUB'S slug "
                  "algorithm AS UNDERSTOOD HERE and nothing standardizes it - another renderer may slug the same "
                  "heading differently, so a green run here is not a promise the anchor works everywhere. Only ATX "
                  "(`#`) headings are anchors to it: a setext heading, an explicit HTML `id=`, or a renderer that "
                  "emits anchors for non-heading elements is invisible. And an anchor that resolves is not an "
                  "anchor that says what the citing sentence claims it says - that stays with review", mark)


# --- M7-B: readme-live-counts (backlog G13) ---------------------------------
#
# README.md's Status table hard-codes counts of things the tree already knows.
# Before M7 it claimed 6 skills and 45 ownership classes against a live 13 and
# 46 - drift in the one table a reader checks first. Each displayed count is
# compared against a value DERIVED from the tree, never against a literal in
# this harness: the self-check count in particular comes from the same
# AST-derived invoked-check registry `selfcheck-doc-parity` uses, so adding a
# check to main() moves the expectation automatically. A literal here would be
# precisely the drift the check exists to prevent.

README_RELPATH = "README.md"
README_STATUS_HEADING = "Status"

# (derived-count key, row-label pattern, human name). The label patterns
# select TABLE ROWS, not skills or agents, so nothing here is a subject
# selector in the sense skill-subject-derivation guards.
README_COUNT_ROWS: tuple[tuple[str, str, str], ...] = (
    ("agents", r"^agents$", "agent definitions under .opencode/agents/*.md"),
    ("skills", r"^skills$", "skills discovered as .opencode/skills/*/SKILL.md"),
    ("ownership file classes", r"^ownership registry$", "[[file_classes]] in .opencode/ownership.toml"),
    ("self-checks", r"^repository self-?checks$", "checks main() invokes"),
)


def status_section(text: str) -> str | None:
    """The body of README's `## Status` section, up to the next H2."""
    lines = blank_fenced_blocks(text).split("\n")
    start = None
    for i, line in enumerate(lines):
        m = ATX_HEADING_RE.match(line)
        if m and len(m.group(1)) == 2 and m.group(2).strip() == README_STATUS_HEADING:
            start = i + 1
            break
    if start is None:
        return None
    for j in range(start, len(lines)):
        m = ATX_HEADING_RE.match(lines[j])
        if m and len(m.group(1)) <= 2:
            return "\n".join(lines[start:j])
    return "\n".join(lines[start:])


def table_rows(section: str) -> list[tuple[str, str]]:
    """(normalized label, raw value) for every two-column row, header/rule dropped."""
    out: list[tuple[str, str]] = []
    for line in section.split("\n"):
        s = line.strip()
        if not s.startswith("|"):
            continue
        cells = [c.strip() for c in s.strip("|").split("|")]
        if len(cells) != 2:
            continue
        label = norm_ws(cells[0]).lower()
        if not label or set(label) <= set("-: "):
            continue
        if label == "component":
            continue
        out.append((label, cells[1]))
    return out


def analyze_readme_counts(section: str, derived: dict[str, int]) -> list[tuple[str, str]]:
    """Pure comparison of a Status table against counts derived from the tree."""
    findings: list[tuple[str, str]] = []
    rows = table_rows(section)
    for key, pattern, what in README_COUNT_ROWS:
        matched = [value for label, value in rows if re.match(pattern, label)]
        if not matched:
            findings.append(("README_COUNT_ROW_MISSING",
                             f"the Status table has no row for {key!r}; the live tree has "
                             f"{derived[key]} {what} and the table claims nothing"))
            continue
        if len(matched) > 1:
            findings.append(("README_COUNT_ROW_DUPLICATE",
                             f"the Status table has {len(matched)} rows matching {key!r}; one of them can drift "
                             "while the other stays right, and a reader cannot tell which is authoritative"))
            continue
        digits = re.findall(r"\d+", matched[0])
        if len(digits) != 1:
            findings.append(("README_COUNT_ROW_MALFORMED",
                             f"the Status row for {key!r} carries {len(digits)} integers ({matched[0]!r}); "
                             "exactly one is required or there is nothing unambiguous to compare"))
            continue
        shown = int(digits[0])
        if shown != derived[key]:
            findings.append(("README_COUNT_MISMATCH",
                             f"the Status table says {shown} for {key!r}; the live tree has {derived[key]} "
                             f"({what}). Update the table - this harness derives the count and will not be "
                             "taught a literal"))
    return findings


_README_SAMPLE_ROWS: tuple[tuple[str, str, str], ...] = (
    ("agents", "Agents", "{n} written"),
    ("skills", "Skills", "{n} written"),
    ("ownership file classes", "Ownership registry", "`.opencode/ownership.toml`, {n} file classes"),
    ("self-checks", "Repository self-checks", "{n} PASS"),
)
_README_SAMPLE_DERIVED = {"agents": 8, "skills": 13, "ownership file classes": 46, "self-checks": 59}


def _render_status_sample(counts: dict[str, int], drop: tuple[str, ...] = (),
                          duplicate: tuple[str, ...] = (), blank: tuple[str, ...] = ()) -> str:
    lines = ["| Component | State |", "|---|---|", "| `AGENTS.md` | written |"]
    for key, label, template in _README_SAMPLE_ROWS:
        if key in drop:
            continue
        value = "several written" if key in blank else template.format(n=counts[key])
        lines.append(f"| {label} | {value} |")
        if key in duplicate:
            lines.append(f"| {label} | {value} |")
    lines.append("| Example root config | `docs/opencode.json` |")
    return "\n".join(lines) + "\n"


def readme_count_analyzer_failures() -> list[str]:
    problems: list[str] = []
    derived = dict(_README_SAMPLE_DERIVED)
    clean = analyze_readme_counts(_render_status_sample(derived), derived)
    if clean:
        problems.append(f"a conforming Status table was rejected with {[c for c, _ in clean]}")
    # Mutate each displayed count INDIVIDUALLY. A comparison that accidentally
    # keys every row off one value would pass three of these four.
    for key, _label, _template in _README_SAMPLE_ROWS:
        drifted_table = _render_status_sample({**derived, key: derived[key] + 1})
        codes = [c for c, _ in analyze_readme_counts(drifted_table, derived)]
        if "README_COUNT_MISMATCH" not in codes:
            problems.append(f"a table whose {key!r} count was off by one was accepted (got {codes or 'no findings'})")
        elif len(codes) != 1:
            problems.append(f"a table whose only defect was the {key!r} count produced {len(codes)} findings; "
                            "one mutated row must implicate one row")
    for key, _label, _template in _README_SAMPLE_ROWS:
        for mutation, expected in (("drop", "README_COUNT_ROW_MISSING"),
                                   ("duplicate", "README_COUNT_ROW_DUPLICATE"),
                                   ("blank", "README_COUNT_ROW_MALFORMED")):
            table = _render_status_sample(derived, **{mutation: (key,)})
            codes = [c for c, _ in analyze_readme_counts(table, derived)]
            if expected not in codes:
                problems.append(f"near-miss {mutation!r} on row {key!r} was not caught by {expected} "
                                f"(got {codes or 'no findings'})")
    return problems


def check_readme_live_counts(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, README_RELPATH, "README_COUNT_ABORT"):
        for problem in readme_count_analyzer_failures():
            report.bad("tools/selfcheck.py", "analyze_readme_counts", "README_COUNT_FIXTURE",
                       f"the Status-table analyzer failed its in-memory near-misses: {problem}")
        path = root / README_RELPATH
        if not path.is_file():
            report.bad(README_RELPATH, "0", "README_COUNT_MISSING", "README.md is absent; its Status table is the "
                       "first thing a reader checks and there is nothing to compare")
            return
        registry = load_registry(root, report)
        if registry is None:
            return
        classes = registry.get("file_classes")
        if not isinstance(classes, list):
            report.bad(".opencode/ownership.toml", "file_classes", "README_COUNT_UNDERIVABLE",
                       "the registry has no [[file_classes]] array, so the displayed class count is comparable "
                       "with nothing")
            return
        try:
            source = Path(__file__).read_text(encoding="utf-8")
        except OSError as exc:
            report.bad("tools/selfcheck.py", "0", "README_COUNT_UNDERIVABLE",
                       f"cannot read this harness to derive its own invoked-check count: {exc}")
            return
        invoked = invoked_check_names(source)
        if not invoked:
            report.bad("tools/selfcheck.py", "main", "README_COUNT_UNDERIVABLE",
                       "no invoked check names could be derived from main()'s AST; the displayed self-check count "
                       "would be compared against zero")
            return
        derived = {
            "agents": len(agent_paths(root)),
            "skills": len(skill_paths(root)),
            "ownership file classes": len(classes),
            "self-checks": len(invoked),
        }
        empty = sorted(k for k, v in derived.items() if v == 0)
        if empty:
            report.bad(README_RELPATH, README_STATUS_HEADING, "README_COUNT_UNDERIVABLE",
                       f"derived {', '.join(empty)} count(s) are zero; discovery found nothing and the comparison "
                       "would be vacuous")
            return
        section = status_section(read_text(path))
        if section is None:
            report.bad(README_RELPATH, README_STATUS_HEADING, "README_COUNT_NO_SECTION",
                       f"README.md has no '## {README_STATUS_HEADING}' section; the counted table cannot be located")
            return
        for code, message in analyze_readme_counts(section, derived):
            report.bad(README_RELPATH, README_STATUS_HEADING, code, message)
        report.ok("readme-live-counts",
                  f"README.md's Status table shows exactly one row each for agents, skills, ownership file classes "
                  f"and repository self-checks, and every displayed integer equals a count DERIVED from the live "
                  f"tree - {derived['agents']} agents, {derived['skills']} skills, "
                  f"{derived['ownership file classes']} file classes, {derived['self-checks']} checks, the last "
                  f"from the same AST-derived invoked-check registry selfcheck-doc-parity reads, so adding a check "
                  f"moves the expectation and no literal count lives in this harness (analyzer self-tested against "
                  f"{len(_README_SAMPLE_ROWS) * 4} near-misses: each count off by one, and each row dropped, "
                  "duplicated and made non-numeric). LIMITS: this proves the NUMBERS agree, not that the things "
                  "counted are the right things - eight agent files that are all empty count as eight - and it "
                  "says nothing about any other prose in the table or the document", mark)


# --- M7-C: glossary-terms-grounded ------------------------------------------
#
# GLOSSARY.md defines the toolkit's vocabulary. A glossary that drifts into
# defining words the corpus no longer uses is worse than no glossary, because
# a reader trusts it. The term list is parsed from the glossary's own entry
# structure - one H2 per term - so adding an entry enrolls it automatically.

GLOSSARY_RELPATH = "GLOSSARY.md"
MAX_GLOSSARY_TERMS = 500


def glossary_terms(text: str) -> list[str]:
    """Every defined term, read from the glossary's own H2 entry structure."""
    out: list[str] = []
    for line in blank_fenced_blocks(text).split("\n"):
        m = ATX_HEADING_RE.match(line)
        if m and len(m.group(1)) == 2:
            term = m.group(2).strip()
            if term:
                out.append(term)
    return out


def ground_key(s: str) -> str:
    """Fold a term or a document to a space-delimited token stream, padded.

    Case, inline markup, dashes and punctuation are all legitimate variation
    between a glossary heading and the prose that uses the term: the corpus
    writes `north-star`, `North star` and `north star` for one concept. Folding
    all three to one key is what keeps this check from producing false alarms
    it would then have to be weakened to silence.

    The leading and trailing space are load-bearing, not cosmetic. Because
    every token in both the term and the corpus is surrounded by spaces, a
    plain `in` test between two padded keys is a TOKEN/PHRASE match rather
    than a substring match: ` pac ` does not occur inside ` the package `.
    Padding both sides is also what makes a term at the very start or end of
    the corpus match.
    """
    s = s.replace("\u2014", " ").replace("\u2013", " ").replace("\u2019", "'")
    s = re.sub(r"[`*_~]", "", s.lower())
    s = re.sub(r"[^a-z0-9]+", " ", s)
    return " " + " ".join(s.split()) + " "


def ungrounded_terms(terms: list[str], corpus_key: str) -> list[str]:
    """Terms whose every slash-separated part is absent from the folded corpus.

    Matching is on whole folded tokens, not raw substrings. The earlier
    revision compared `ground_key(part).strip()` against the corpus, which
    grounded `PAC` on the word "package" and `Handoff` on anything containing
    those letters - the PASS line said the term *occurs* and containment is
    not occurrence. Comparing the PADDED keys makes the claim true as written.

    A compound heading such as `Functional core / imperative shell` names one
    concept written two ways; both halves must occur, because half a compound
    occurring is not evidence the compound is in use.
    """
    out: list[str] = []
    for term in terms:
        parts = [p for p in (part.strip() for part in term.split("/")) if p]
        if not parts:
            continue
        missing = [p for p in parts if ground_key(p) not in corpus_key]
        if missing:
            out.append(term)
    return out


_GLOSSARY_SAMPLE_CORPUS = (
    "The north-star crate is `embassy-mcxa`. A handoff carries `target-id` and a typed verdict.\n"
    "Functional core, imperative shell: the functional core is host-testable and the imperative "
    "shell pokes registers. Typed verdicts gate acceptance.\n"
    "A package of recorded transforms is an input; unhandoffed drafts are not.\n"
)

_GLOSSARY_GROUNDED_CASES: tuple[str, ...] = (
    "North star",
    "`target-id`",
    "Typed verdict",
    "Functional core / imperative shell",
    "HANDOFF",
    # A term that IS a whole token must still match when neighbouring words
    # merely contain it: the tightening must not overshoot into rejecting
    # legitimate occurrences.
    "gate",
)

_GLOSSARY_UNGROUNDED_CASES: tuple[tuple[str, str], ...] = (
    ("a term nothing uses", "Quiescent flange"),
    ("only half a compound occurs", "Functional core / orbital mechanics"),
    ("a plausible near-word", "north stars and stripes"),
    # The two cases that motivated the tightening. Under the earlier substring
    # comparison both of these were reported GROUNDED, which is precisely the
    # gap between "occurs" and "is contained in".
    ("a short term buried inside a longer word", "PAC"),
    ("a term that is only ever a prefix of another", "Handoffed"),
)


def glossary_analyzer_failures() -> list[str]:
    problems: list[str] = []
    corpus = ground_key(_GLOSSARY_SAMPLE_CORPUS)
    grounded = list(_GLOSSARY_GROUNDED_CASES)
    rejected = ungrounded_terms(grounded, corpus)
    if rejected:
        problems.append(f"terms the sample corpus plainly uses were reported ungrounded: {rejected}; "
                        "a check that cries wolf on case, backticks or a hyphen is a check that gets deleted")
    for name, term in _GLOSSARY_UNGROUNDED_CASES:
        if not ungrounded_terms([term], corpus):
            problems.append(f"near-miss {name!r} ({term!r}) was accepted as grounded")
    if not ungrounded_terms(grounded, ground_key("")):
        problems.append("every term was accepted against an EMPTY corpus; the match would pass vacuously")
    return problems


def check_glossary_terms_grounded(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, GLOSSARY_RELPATH, "GLOSSARY_ABORT"):
        for problem in glossary_analyzer_failures():
            report.bad("tools/selfcheck.py", "ungrounded_terms", "GLOSSARY_FIXTURE",
                       f"the grounding analyzer failed its in-memory fixtures: {problem}")
        path = root / GLOSSARY_RELPATH
        if not path.is_file():
            report.bad(GLOSSARY_RELPATH, "0", "GLOSSARY_MISSING",
                       "the glossary is absent; the documents that link to it define the toolkit's vocabulary "
                       "nowhere")
            return
        terms = glossary_terms(read_text(path))
        if not terms:
            report.bad(GLOSSARY_RELPATH, "0", "GLOSSARY_NO_TERMS",
                       "no '## <term>' entries were parsed from the glossary; the grounding rule is asserted "
                       "against nothing")
            return
        if len(terms) > MAX_GLOSSARY_TERMS:
            report.bad(GLOSSARY_RELPATH, "0", "GLOSSARY_TOO_LARGE",
                       f"the glossary defines {len(terms)} terms, above the {MAX_GLOSSARY_TERMS} bound")
            return
        others = [p for p in governed_markdown(root)
                  if not is_fixture_payload(root, p) and p.resolve() != path.resolve()]
        if not others:
            report.bad(GLOSSARY_RELPATH, "0", "GLOSSARY_NO_CORPUS",
                       "no governed Markdown outside the glossary itself; every term would be reported ungrounded")
            return
        corpus_key = ground_key(" \n ".join(read_text(p) for p in others))
        for term in ungrounded_terms(terms, corpus_key):
            report.bad(GLOSSARY_RELPATH, term, "GLOSSARY_TERM_UNGROUNDED",
                       f"the glossary defines {term!r} but the token occurs nowhere in the {len(others)} other "
                       "governed Markdown files. Either the corpus stopped using the term and the entry is stale, "
                       "or the entry is spelled differently from the prose it is meant to explain")
        report.ok("glossary-terms-grounded",
                  f"all {len(terms)} terms parsed from the glossary's own H2 entry structure occur as whole "
                  f"folded tokens somewhere in the {len(others)} governed non-fixture Markdown files outside it, "
                  f"matched after folding away case, backticks and emphasis, dashes and punctuation, with a "
                  f"compound `a / b` heading requiring BOTH halves (analyzer self-tested against "
                  f"{len(_GLOSSARY_UNGROUNDED_CASES)} near-misses, {len(_GLOSSARY_GROUNDED_CASES)} legitimate "
                  "spellings that must not trip, and an empty corpus that must reject everything). The match is "
                  "on token and phrase boundaries, not raw substrings: `PAC` is grounded by `PAC` and NOT by "
                  "\"package\". LIMITS: OCCURRENCE IS STILL NOT USAGE-CONSISTENCY. A term that appears somewhere "
                  "is not thereby a term used as the glossary defines it, and this check will never notice a "
                  "definition that has quietly become wrong - a sentence using `Canonical` in its ordinary "
                  "English sense grounds the entry just as well as one using it in this toolkit's sense. Folding "
                  "punctuation away also means a term is grounded by any spelling that folds to the same tokens, "
                  "and inflections are NOT matched: a corpus that only ever wrote \"handoffs\" would leave "
                  "`Handoff` ungrounded. The converse is not checked at all: a term the corpus uses heavily and "
                  "the glossary omits is invisible here", mark)


def main(argv: list[str]) -> int:
    args = [a for a in argv[1:]]
    write_base = False
    if "--write-terminology-baseline" in args:
        write_base = True
        args.remove("--write-terminology-baseline")
    if len(args) > 1:
        print("usage: selfcheck.py [REPO_ROOT] [--write-terminology-baseline]", file=sys.stderr)
        return 2
    root = Path(args[0]).resolve() if args else Path(__file__).resolve().parent.parent
    if not root.is_dir():
        print(f"FAIL {root}:0 [REPO_ROOT_MISSING] repository root is not a directory", file=sys.stderr)
        return 2

    if write_base:
        p = write_baseline(root)
        print(f"wrote {rel(root, p)}")
        return 0

    report = Report()
    check_frontmatter(root, report)
    check_links(root, report)
    check_fixtures(root, report)
    check_terminology(root, report)
    check_topology(root, report)
    check_contracts(root, report)
    check_ownership(root, report)
    check_emissions(root, report)
    check_permissions(root, report)
    check_config(root, report)
    check_dispatch(root, report)
    check_roadmap_path(root, report)
    check_verdict(root, report)
    check_commit_owner(root, report)
    check_precedence(root, report)
    check_candidate_convention(root, report)
    check_workflow_markers(root, report)
    check_skill_references(root, report)
    check_validation_guidance_isolation(root, report)
    check_skill_discovery_closure(root, report)
    check_skill_subject_derivation(root, report)

    # Skill template checks. M4 retired the two-generation exemption file and
    # its parser together, so these are ordinary invocations with no exclusion
    # set: each scans every discovered skill.
    check_skill_contracts(root, report)
    check_skill_emissions(root, report)
    check_skill_consumption(root, report)
    check_skill_structure(root, report)
    check_skill_trigger_frontmatter(root, report)
    check_skill_ownership(root, report)
    check_skill_status_vocabulary(root, report)
    check_skill_verdict(root, report)
    check_skill_validator_wiring(root, report)
    check_skill_note_paths(root, report)
    check_skill_platform_slices(root, report)
    check_debug_lineage(root, report)
    check_schema_attribution(root, report)
    check_test_candidate_layout(root, report)

    # M6. Corpus-wording and record gates first (cheap, pure), then the two
    # subprocess-bound checks. Deliberately serial: at most one build/test
    # process runs at a time.
    check_mcxa_example_boundary(root, report)
    check_error_clear_semantics(root, report)
    check_target_first_driver_order(root, report)
    check_checkout_context_guard(root, report)
    check_install_no_overwrite(root, report)
    check_reference_url_pins(root, report)
    check_tester_destination_coverage(root, report)
    check_claim_truth_limit(root, report)
    check_citation_verification_corpus(root, report)
    check_fixture_regeneration(root, report)
    check_runtime_protocol_tests(root, report)

    # M6 review follow-up. Behavioural checks: these execute the production
    # helper and the committed test suites. Deliberately serial and last - at
    # most one build/test process at a time.
    check_no_invented_hardware_in_corpus(root, report)
    check_hardware_procedure_uses_interlock(root, report)
    check_interlock_refuses_fabricated_evidence(root, report)
    check_interlock_recovery_can_reconnect(root, report)
    check_interlock_recovery_child_sessions(root, report)
    check_interlock_lock_validates(root, report)
    check_interlock_override_requires_ambiguity(root, report)
    check_state_publish_is_atomic(root, report)
    check_citation_path_tested(root, report)

    # M7. The user-documentation set. Pure corpus/tree analyzers, no
    # subprocess, so they cost nothing and are invoked last before parity.
    check_markdown_anchor_targets(root, report)
    check_readme_live_counts(root, report)
    check_glossary_terms_grounded(root, report)

    check_selfcheck_doc_parity(root, report)
    return report.emit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
