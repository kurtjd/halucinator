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

import os
import posixpath
import re
import subprocess
import sys
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

# M4: 29 (M1) + 30-tests-bound-to-blocked-driver + 31-tests-api-handoff-wrong-kind
# + 32-noncanonical-singleton-filename.
MANDATED_FIXTURES = 32

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
    if len(cases) < MANDATED_FIXTURES:
        report.bad(rel(root, invalid_dir), "0", "FIXTURE_SET_INCOMPLETE", f"expected at least {MANDATED_FIXTURES} invalid fixtures, found {len(cases)}")

    passed = 0
    for case in cases:
        r = rel(root, case)
        readme = case / "README.md"
        if not readme.is_file():
            report.bad(r, "0", "FIXTURE_README_MISSING", "invalid fixture has no README.md naming its expected diagnostic code")
            continue
        m = CODE_RE.search(read_text(readme))
        if not m:
            report.bad(rel(root, readme), "0", "FIXTURE_CODE_UNDECLARED", "README.md does not state 'Expected diagnostic code: `CODE`'")
            continue
        expected = m.group(1)
        readme_text = read_text(readme)
        rc, out = run_validator(root, validator, case)
        if rc is None:
            report.bad(r, "0", "FIXTURE_TIMEOUT", f"validator {out}; a hang is a failure")
            continue
        if rc != 1:
            report.bad(r, "0", "FIXTURE_WRONG_EXIT", f"expected exit 1, got {rc}; output: {_one_line(out)}")
            continue
        if expected not in out:
            report.bad(r, "0", "FIXTURE_WRONG_CODE", f"expected diagnostic code {expected} not emitted; output: {_one_line(out)}")
            continue
        # Opt-in exact mode. The legacy "the code appears somewhere" assertion
        # lets a fixture pass for the wrong reason - a different file, a
        # different field, or a pile of unrelated diagnostics. Fixtures 01-29
        # keep it because EXPECTATIONS.md documents genuinely multi-code cases;
        # a fixture that declares "Expected diagnostics: exact" is held to the
        # single diagnostic it names and nothing else.
        if FIXTURE_EXACT_RE.search(readme_text):
            fm = FIXTURE_FILE_RE.search(readme_text)
            fld = FIXTURE_FIELD_RE.search(readme_text)
            if not fm or not fld:
                report.bad(rel(root, readme), "0", "FIXTURE_EXACT_UNDECLARED",
                           "README declares 'Expected diagnostics: exact' but omits 'Expected file:' or 'Expected field:'")
                continue
            want = (fm.group(1), fld.group(1), expected)
            got = parse_diagnostics(out)
            if got != [want]:
                report.bad(r, "0", "FIXTURE_EXACT_MISMATCH",
                           f"exact mode: expected exactly one diagnostic {want}, got {got or 'none parsed'}")
                continue
        passed += 1

    report.ok("fixtures", f"{len(valid_roots)} accepted fixture roots exit 0 silently and {passed} of {len(cases)} invalid fixtures rejected with exit 1 and their declared code", mark)


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

import ast
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
SKILL_TOKEN_RE = re.compile(r"`((?:write|review|generate|gather|scaffold|extract)-[a-z][a-z0-9-]*)`")


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


def _enumerate(spec, prefix: str, out: set[str], depth: int = 0) -> None:
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
            _enumerate(_decl_spec(decl), f"{prefix}.{name}", out, depth + 1)
        return
    if kind == "array":
        _enumerate(spec.get("items"), prefix, out, depth + 1)
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
                _enumerate(_decl_spec(decl), f"{prefix}.{name}", out, depth + 1)
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
    for name, table in (("handoff", "HANDOFF_TABLE"), ("scope", "SCOPE_TABLE"), ("coverage", "COVERAGE_TABLE")):
        value = _ast_eval(symbols[table], symbols)
        if not isinstance(value, dict):
            raise RegistryError(f"{table} did not evaluate to a mapping")
        for field, decl in value.items():
            _enumerate(_decl_spec(decl), f"{name}.{field}", common)
    for leaf in ("id", "status", "evidence", "reason"):
        common.add(f"checks.{leaf}")

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
        for field, decl in fields.items():
            _enumerate(_decl_spec(decl), f"{table}.{field}", paths)
        checks = spec.get("checks")
        registry[kind] = {
            "stage": spec.get("stage"),
            "table": table,
            "paths": paths,
            "common": common,
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
    with guard(report, "opencode.json", "CONFIG_ABORT"):
        path = root / "opencode.json"
        if not path.is_file():
            report.bad("opencode.json", "0", "CONFIG_MISSING",
                       'root opencode.json is absent; create it with {"$schema": "https://opencode.ai/config.json", "default_agent": "hal-coordinator"}')
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            report.bad("opencode.json", "0", "CONFIG_MALFORMED", f"not strict JSON: {_one_line(str(exc), 200)}")
            return
        if not isinstance(data, dict):
            report.bad("opencode.json", "0", "CONFIG_TYPE", "config must be a JSON object")
            return
        if data.get("$schema") != "https://opencode.ai/config.json":
            report.bad("opencode.json", "$schema", "CONFIG_SCHEMA", f"$schema must be 'https://opencode.ai/config.json', got {data.get('$schema')!r}")
        default = data.get("default_agent")
        if default != PRIMARY_AGENT:
            report.bad("opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT", f"default_agent must be {PRIMARY_AGENT!r}, got {default!r}")
            return
        target = root / ".opencode" / "agents" / f"{default}.md"
        if not target.is_file():
            report.bad("opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT_MISSING", f"default_agent {default!r} has no agent definition at .opencode/agents/{default}.md")
            return
        try:
            fm = parse_frontmatter(read_text(target))
        except (FMError, OSError) as exc:
            report.bad("opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT_MISSING", f"default agent definition is unparseable: {exc}")
            return
        if fm.get("mode") != "primary":
            report.bad("opencode.json", "default_agent", "CONFIG_DEFAULT_AGENT_MODE", f"default_agent {default!r} must be mode primary, got {fm.get('mode')!r}")
        report.ok("config", "root opencode.json parses and its default agent resolves to a primary agent", mark)


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
    mark = report.mark()
    with guard(report, ".opencode/agents", "SKILLREF_ABORT"):
        skills_dir = root / ".opencode" / "skills"
        existing = {p.parent.name for p in skills_dir.glob("*/SKILL.md")} if skills_dir.is_dir() else set()
        found = agent_paths(root)
        refs = 0
        for name in sorted(found):
            path = found[name]
            r = rel(root, path)
            text = read_text(path)
            for sentence in norm_ws(text.replace("`", "\u0000")).split(". "):
                for m in re.finditer(r"\x00((?:write|review|generate|gather|scaffold|extract)-[a-z][a-z0-9-]*)\x00", sentence):
                    token = m.group(1)
                    refs += 1
                    if token in existing:
                        continue
                    if re.search(r"awaits M[0-9]+ TODO ", sentence):
                        continue
                    report.bad(r, "0", "SKILL_REFERENCE_UNRESOLVED",
                               f"references skill {token!r}, which does not exist under .opencode/skills/; a future skill may appear only as unlinked prose marked 'awaits M<n> TODO <ID>'")
        report.ok("skill-references", f"{refs} skill references in agent prose resolve to existing skills", mark)


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

SKILL_NOTE_PATHS = {
    "generate-svd": "<documentation>/notes/SVD.md",
    "generate-pac": "<documentation>/notes/PAC.md",
}

# Skills whose exit gate is an accepting independent review. This set is NOT
# hard-coded: a skill is review-gated exactly when its own contract fence
# declares the 'independent-review' check, so a new review-gated skill is
# covered the moment it declares the check. See review_gated_skills().
REVIEW_GATED_CHECK = "independent-review"

# Per-skill canonical contract expectations. Leaf/check sets are NOT stored
# here: they are derived from validate.py's AST by derive_registry(). Only the
# consumed predecessor leaf sets (specification section 12) are literal,
# because they are a deliberate subset of a kind rather than the whole kind.
CONSUMED_01 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,sources.catalog,sources.route,sources.source_ids,sources.available,sources.cited_notes"
CONSUMED_02 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,facts.notes,facts.citations.source_id,facts.citations.document,facts.citations.revision,facts.citations.locator,facts.citations.note,facts.categories,facts.contradictions"
CONSUMED_03 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,checks.id,checks.status,checks.evidence,checks.reason,svd.route,svd.source,svd.transforms,svd.includes,svd.prepared_manifest,svd.extraction_mode,svd.namespace_mode,svd.representation_limits,svd.unresolved_facts"
CONSUMED_04 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,pac.crate_manifest,pac.package,pac.revision.kind,pac.revision.value,pac.cargo_chip_feature,pac.runtime_features,pac.metadata_features,pac.rust_compilation_target,pac.source_ids,pac.cited_notes,pac.temporary_fork,pac.foundation.id,pac.foundation.kind,pac.foundation.location,pac.foundation.status,pac.foundation.evidence"
CONSUMED_05 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,platform.crate_manifest,platform.roadmap,platform.startup_clock_contract,platform.supporting_subsystems,platform.foundation_api,platform.pac_manifest,platform.source_ids,platform.cited_notes,platform.dependencies.crate,platform.dependencies.identity,platform.dependencies.features,platform.first_driver,platform.first_driver_modes"
CONSUMED_06 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,driver.name,driver.scope_kind,driver.capabilities,driver.public_api,driver.dependencies.crate,driver.dependencies.identity,driver.dependencies.features,driver.trait_obligations.dependency_crate,driver.trait_obligations.trait,driver.trait_obligations.obligations,driver.test_hardware_facts.source_id,driver.test_hardware_facts.document,driver.test_hardware_facts.revision,driver.test_hardware_facts.locator,driver.test_hardware_facts.note,driver.build_contract.cargo_chip_feature,driver.build_contract.rust_compilation_target,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.requirement_ids,driver.public_test_record"


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
        "consumes": {"01-sources": _leaves(CONSUMED_01), "02-facts": _leaves(CONSUMED_02)},
        "writes": {"hal-svd|pac-project", "hal-svd|svd-handoff", "hal-svd|svd-pac-notes"},
        "supplies-delta": {"hal-svd|sources-catalog"},
    },
    "generate-pac": {
        "stage": "generate-pac",
        "emitter": "hal-svd",
        "kind": "04-pac",
        "filename": "halucinator/handoff/04-pac.toml",
        "consumes": {"03-svd": _leaves(CONSUMED_03)},
        "writes": {"hal-svd|pac-handoff", "hal-svd|pac-project", "hal-svd|svd-pac-notes"},
        "supplies-delta": {"hal-svd|sources-catalog"},
    },
    "scaffold-hal": {
        "stage": "scaffold-hal",
        "emitter": "hal-integrator",
        "kind": "05-platform",
        "filename": "halucinator/handoff/05-platform.toml",
        "consumes": {"04-pac": _leaves(CONSUMED_04)},
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
        "consumes": {"05-platform": _leaves(CONSUMED_05)},
        "writes": {
            "hal-driver|clock-modules", "hal-driver|driver-candidates",
            "hal-driver|driver-handoff", "hal-driver|peripheral-modules",
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
        "consumes": {"06-driver": _leaves(CONSUMED_06)},
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


def _toml_leaf_paths(value, prefix: str, known: frozenset[str], depth: int = 0) -> set[str]:
    """Flatten a parsed TOML example into schema leaf paths.

    Descent STOPS at any prefix already known to be a leaf, so opaque schema
    scalars that happen to be TOML tables or arrays of tables - FileRef,
    ArtifactRef, and the like - are not mistaken for structs and reported as
    invented fields.
    """
    if depth > MAX_AST_DEPTH:
        return {prefix}
    if prefix and prefix in known:
        return {prefix}
    if isinstance(value, dict):
        out: set[str] = set()
        for key, sub in value.items():
            out |= _toml_leaf_paths(sub, f"{prefix}.{key}" if prefix else str(key), known, depth + 1)
        return out
    if isinstance(value, list):
        out = set()
        for item in value:
            out |= _toml_leaf_paths(item, prefix, known, depth + 1)
        return out or {prefix}
    return {prefix}


def analyze_typed_example(text: str, stage: str | None, kind: str | None, known: frozenset[str]) -> list[tuple[str, str]]:
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
        if isinstance(h, dict) and h.get("stage") == stage and h.get("schema") == 1:
            handoffs.append(doc)
    if not handoffs:
        out.append(("SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF",
                    f"no toml example block is the emitted handoff: one must contain a [handoff] table with schema = 1 and stage = {stage!r}"))
        return out
    for doc in handoffs:
        unknown = sorted(p for p in _toml_leaf_paths(doc, "", known) if p not in known)
        if unknown:
            out.append(("SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD",
                        f"{kind}: the typed example names field(s) {', '.join(unknown[:8])} that are not schema leaves of that kind; the worked example must not drift from the contract"))
    return out


_EXAMPLE_KNOWN = frozenset({"handoff.schema", "handoff.stage", "handoff.status", "handoff.notes", "alpha.name"})
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
```
"""

_EXAMPLE_CASES: tuple[tuple[str, str, str], ...] = (
    ("no Application example section", "# Fixture\n\n## Procedure\n1. Inspect it.\n", "SKILL_STRUCTURE_EXAMPLE_MISSING"),
    ("section present but no toml fence", "# Fixture\n\n## Application example\n\nProse only, no fence.\n", "SKILL_STRUCTURE_EXAMPLE_NO_TOML"),
    ("unparseable toml", _EXAMPLE_GOOD.replace("schema = 1", "schema = = 1"), "SKILL_STRUCTURE_EXAMPLE_TOML_INVALID"),
    ("wrong stage", _EXAMPLE_GOOD.replace('stage = "generate-pac"', 'stage = "scaffold-hal"'), "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF"),
    ("schema not 1", _EXAMPLE_GOOD.replace("schema = 1", "schema = 2"), "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF"),
    ("field absent from the kind's leaf set", _EXAMPLE_GOOD.replace('name = "x"', 'name = "x"\nbogus = "y"'), "SKILL_STRUCTURE_EXAMPLE_UNKNOWN_FIELD"),
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
    clean = analyze_typed_example(_EXAMPLE_GOOD, "generate-pac", "04-pac", _EXAMPLE_KNOWN)
    if clean:
        problems.append(f"the conforming typed example was rejected with {[c for c, _ in clean]}")
    for name, text, expected in _EXAMPLE_CASES:
        codes = [c for c, _ in analyze_typed_example(text, "generate-pac", "04-pac", _EXAMPLE_KNOWN)]
        if expected not in codes:
            problems.append(f"typed-example near-miss {name!r} was not caught by {expected} (got {codes or 'no findings'})")
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
                continue
            values = cmap.get("consumes", [])
            if not values:
                report.bad(r, "consumes", "SKILL_CONSUMPTION_MISSING", "contract declares no 'consumes:' line; intake declares 'consumes: none|none'")
                continue
            want: dict[str, set[str]] = spec["consumes"]
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
        report.ok("skill-consumption", f"{ok} skill consumption declarations name AST-valid leaves of their exact predecessor kinds", mark)


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
            for code, message in analyze_typed_example(text, stage, kind, known):
                report.bad(r, "Application example", code, message)
            ok += 1
        report.ok("skill-structure", f"{ok} skills carry the ten template sections, assertable procedural form, and a typed TOML worked example matching their emitted kind (analyzer self-tested against {len(_FIXTURE_CASES) + len(_EXAMPLE_CASES)} near-misses)", mark)


# --- check 23: skill-trigger-frontmatter ------------------------------------

SCAFFOLD_REQUIRED_TERMS = ("clocks", "init", "interrupt_mod!", "generated mappings", "memory.x", "linker")


def check_skill_trigger_frontmatter(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_TRIGGER_ABORT"):
        skills = in_scope_skills(root)
        if not skills:
            report.bad(".opencode/skills", "0", "SKILL_TRIGGER_NO_TARGETS", "no skills discovered; no dispatch description is asserted")
            return
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
            if name == "scaffold-hal":
                absent = [t for t in SCAFFOLD_REQUIRED_TERMS if t.lower() not in flat.lower()]
                if absent:
                    report.bad(r, "description", "SKILL_TRIGGER_SCAFFOLD_TERMS",
                               f"scaffold-hal description does not name dispatch/search term(s): {', '.join(absent)}")
            ok += 1
        report.ok("skill-trigger-frontmatter", f"{ok} skill descriptions open with an observable 'Use when' trigger and name excluded adjacent work", mark)


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


def check_skill_verdict(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_VERDICT_ABORT"):
        skills = in_scope_skills(root)
        gated = review_gated_skills(root, skills)
        if not gated:
            report.bad(".opencode/skills", "0", "SKILL_VERDICT_NO_TARGETS",
                       f"no discovered skill declares the {REVIEW_GATED_CHECK!r} check in its contract fence; the accepting verdict sentence is asserted against nothing")
            return
        for name in gated:
            path = skills[name]
            for target in [path] + skill_reference_paths(root, path):
                tr = rel(root, target)
                flat = norm_ws(read_text(target))
                if target == path and norm_ws(VERDICT_SENTENCE) not in flat:
                    report.bad(tr, "0", "SKILL_VERDICT_SENTENCE_MISSING",
                               f"review-gated skill does not state the exact accepting sentence {VERDICT_SENTENCE!r}")
                for legacy in LEGACY_VERDICT_TOKENS:
                    if legacy in flat:
                        report.bad(tr, "0", "SKILL_VERDICT_LEGACY_TOKEN",
                                   f"legacy spaced verdict wording {legacy!r} is present in gate prose; use the typed tokens ready / ready-with-fixes / not-ready")
        report.ok("skill-verdict", f"{len(gated)} review-gated skills state the exact accepting verdict sentence with no spaced legacy tokens", mark)


# --- check 27: skill-validator-wiring ---------------------------------------

VALIDATOR_STEM = "python .opencode/schema/validate.py"
VALIDATOR_ALL = "--kind all"


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
                sites = sum(1 for line in proc.split("\n") if "validate.py" in line)
                if sites < 2:
                    report.bad(r, "Procedure", "SKILL_VALIDATOR_PLACEMENT",
                               f"the procedure names validate.py at {sites} step(s); it must validate before consuming predecessors AND after writing the preliminary and final handoff")
            low = flat.lower()
            if "honor system" not in low and "honor-system" not in low:
                report.bad(r, "0", "SKILL_VALIDATOR_HONOR_SYSTEM",
                           "skill does not state the honor-system limitation; self-check proves the instruction is present, not that the agent ran it")
            if "cannot attest" not in low:
                report.bad(r, "0", "SKILL_VALIDATOR_HONOR_SYSTEM",
                           "skill does not state that validate.py cannot attest to an earlier invocation")
            ok += 1
        report.ok("skill-validator-wiring", f"{ok} skills wire the validator before consumption, at publication, and at the final all-gate, and disclose the honor-system limit", mark)


# --- check 28: skill-note-paths ---------------------------------------------


def check_skill_note_paths(root: Path, report: Report) -> None:
    mark = report.mark()
    with guard(report, ".opencode/skills", "SKILL_NOTE_ABORT"):
        skills = in_scope_skills(root)
        targets = [(n, p) for n, p in skills.items() if n in SKILL_NOTE_PATHS]
        if not targets:
            report.bad(".opencode/skills", "0", "SKILL_NOTE_NO_TARGETS",
                       f"neither {' nor '.join(sorted(SKILL_NOTE_PATHS))} was discovered; the deterministic note paths are asserted against nothing")
            return
        for name, path in sorted(targets):
            want = SKILL_NOTE_PATHS[name]
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

VALIDATION_SCAN_ROOT = ".opencode/skills/write-examples"
IMPLEMENTATION_SKILL_DIR = ".opencode/skills/write-driver"
VALIDATION_PROFILE_DIR = ".opencode/skills/write-examples/references/profiles"

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
    r"\benable_and_reset\b",
    r"\bwaker\.register\b",
    r"\bregister_waker\b",
)

_IMPL_RE = tuple((p, re.compile(p, re.MULTILINE)) for p in IMPLEMENTATION_TOKENS)


def analyze_validation_guidance(relpath: str, text: str) -> list[tuple[str, str]]:
    """Pure analyzer: [(code, message)] for implementation guidance in one file.

    Pure function of (repository-relative path, raw markdown) so the in-memory
    non-vacuity fixtures below can drive it without touching the filesystem.

    Two independent failure modes:
      (a) a relative Markdown link that RESOLVES beneath write-driver/, and
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
        if resolved == IMPLEMENTATION_SKILL_DIR or resolved.startswith(IMPLEMENTATION_SKILL_DIR + "/"):
            out.append((
                "VALIDATION_GUIDANCE_LEAK",
                f"link {target!r} resolves to {resolved!r}, beneath the implementation skill "
                f"{IMPLEMENTATION_SKILL_DIR!r}; hal-tester must never be routed into implementation guidance",
            ))
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
    mark = report.mark()
    with guard(report, VALIDATION_SCAN_ROOT, "VALIDATION_GUIDANCE_ABORT"):
        for problem in validation_analyzer_failures(root):
            report.bad("tools/selfcheck.py", "analyze_validation_guidance",
                       "VALIDATION_GUIDANCE_FIXTURE",
                       f"the validation-guidance analyzer failed its in-memory fixtures: {problem}")
        scan_dir = root / VALIDATION_SCAN_ROOT
        if not scan_dir.is_dir():
            report.bad(VALIDATION_SCAN_ROOT, "0", "VALIDATION_GUIDANCE_NO_SCAN_ROOT",
                       "the tester-facing skill tree is absent; the isolation check has nothing to scan")
            return
        files = sorted(p for p in scan_dir.rglob("*.md") if p.is_file())
        if not files:
            report.bad(VALIDATION_SCAN_ROOT, "0", "VALIDATION_GUIDANCE_NO_TARGETS",
                       "no Markdown found under the tester-facing skill tree; a scanner with no targets must not pass vacuously")
            return
        # A tester-safe validation profile must actually exist. Without one the
        # scan is technically green and substantively meaningless: it would be
        # asserting that guidance that does not exist contains no leak.
        profiles = sorted(p for p in (root / VALIDATION_PROFILE_DIR).rglob("*.md")
                          if p.is_file()) if (root / VALIDATION_PROFILE_DIR).is_dir() else []
        if not profiles:
            report.bad(VALIDATION_PROFILE_DIR, "0", "VALIDATION_GUIDANCE_NO_PROFILE",
                       "no tester-safe validation profile exists under "
                       f"{VALIDATION_PROFILE_DIR}; hal-tester has nothing to load in place of the "
                       "implementation skill, so the isolation guarantee is vacuous")
        for p in files:
            r = rel(root, p)
            for code, message in analyze_validation_guidance(r, read_text(p)):
                report.bad(r, "0", code, message)
        report.ok("validation-guidance-isolation",
                  f"{len(files)} tester-facing Markdown files ({len(profiles)} validation profiles) carry no "
                  f"implementation guidance under {len(IMPLEMENTATION_TOKENS)} tokens and no link into "
                  f"{IMPLEMENTATION_SKILL_DIR} (analyzer self-tested against {len(_VALIDATION_NEAR_MISSES)} near-misses)",
                  mark)


# --- M4 check: skill-discovery-closure --------------------------------------
#
# Part 8. The template checks bind on whatever skill_paths() discovers, and
# discovery globs `*/SKILL.md` - so a skill directory with no SKILL.md is
# simply invisible and silently exempt. That is a fail-OPEN discovery, and it
# is exactly the hole the retired two-generation exemption file used to make
# visible. This check is what keeps discovery honest now that the file and its
# parser are gone.

M4_SKILLS: tuple[str, ...] = (
    "gather-documentation",
    "generate-pac",
    "generate-svd",
    "scaffold-hal",
    "write-driver",
    "write-examples",
)


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
        if discovered != sorted(M4_SKILLS):
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_SET",
                       f"discovered skills are {discovered}; after M4 there must be exactly "
                       f"{len(M4_SKILLS)}: {sorted(M4_SKILLS)}. Implementation guidance is consolidated "
                       "into write-driver and tester-safe validation profiles live under "
                       f"{VALIDATION_PROFILE_DIR}")
        # Every discovered skill must be in scope for the template checks with
        # no exclusion set applied at all.
        unbound = sorted(set(discovered) - set(in_scope_skills(root)))
        if unbound:
            report.bad(".opencode/skills", "0", "SKILL_DISCOVERY_UNBOUND",
                       f"skills {unbound} are discovered but not in scope for the template checks")
        report.ok("skill-discovery-closure",
                  f"{len(discovered)} skill directories each carry exactly one regular SKILL.md and the "
                  f"discovered set is the exact M4 set of {len(M4_SKILLS)}", mark)


# ---------------------------------------------------------------------------


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
    check_schema_attribution(root, report)
    check_test_candidate_layout(root, report)
    check_selfcheck_doc_parity(root, report)
    return report.emit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
