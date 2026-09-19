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
# here: they are derived from validate.py's AST by derive_registry(). Only the
# consumed predecessor leaf sets (specification section 12) are literal,
# because they are a deliberate subset of a kind rather than the whole kind.
CONSUMED_01 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,sources.catalog,sources.route,sources.source_ids,sources.available,sources.cited_notes"
CONSUMED_02 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,facts.notes,facts.citations.source_id,facts.citations.document,facts.citations.revision,facts.citations.locator,facts.citations.note,facts.categories,facts.contradictions"
CONSUMED_03 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,checks.id,checks.status,checks.evidence,checks.reason,svd.route,svd.source,svd.transforms,svd.includes,svd.prepared_manifest,svd.extraction_mode,svd.namespace_mode,svd.representation_limits,svd.unresolved_facts"
CONSUMED_04 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,pac.crate_manifest,pac.package,pac.revision.kind,pac.revision.value,pac.cargo_chip_feature,pac.runtime_features,pac.metadata_features,pac.rust_compilation_target,pac.source_ids,pac.cited_notes,pac.temporary_fork,pac.foundation.id,pac.foundation.kind,pac.foundation.location,pac.foundation.status,pac.foundation.evidence"
CONSUMED_05 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,platform.crate_manifest,platform.roadmap,platform.startup_clock_contract,platform.supporting_subsystems,platform.foundation_api,platform.pac_manifest,platform.source_ids,platform.cited_notes,platform.dependencies.crate,platform.dependencies.identity,platform.dependencies.features,platform.first_driver,platform.first_driver_modes"
CONSUMED_06 = "handoff.status,handoff.inputs,handoff.notes,handoff.blockers,scope.revision,scope.decision,coverage.complete,coverage.incomplete,driver.name,driver.scope_kind,driver.capabilities,driver.public_api,driver.dependencies.crate,driver.dependencies.identity,driver.dependencies.features,driver.trait_obligations.dependency_crate,driver.trait_obligations.trait,driver.trait_obligations.obligations,driver.test_hardware_facts.source_id,driver.test_hardware_facts.document,driver.test_hardware_facts.revision,driver.test_hardware_facts.locator,driver.test_hardware_facts.note,driver.build_contract.cargo_chip_feature,driver.build_contract.rust_compilation_target,driver.build_contract.init_calls,driver.build_contract.memory_runtime,driver.build_contract.observation,driver.requirement_ids,driver.public_test_record"

# Sentinel for "the complete AST-derived leaf set of that kind". M5's snapshot
# and review consumers re-read an entire predecessor rather than a curated
# subset, so writing the subset out by hand would be a second hand-maintained
# copy of the registry. Resolved against derive_registry() at check time.
CONSUME_ALL = "*"


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
        # The consolidator starts the chain's evidence from the PAC and, as the
        # FINAL platform slice, also consumes the 05-platform snapshot the
        # preceding slices published. Without that second edge a `ready`
        # platform needs no typed evidence that the slices ran at all. Same
        # whole-predecessor sentinel the other slices declare, so the two sides
        # cannot drift into disagreeing literal copies.
        "consumes": {"04-pac": _leaves(CONSUMED_04), "05-platform": CONSUME_ALL},
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
    # --- M5 -----------------------------------------------------------------
    "extract-hardware-facts": {
        "stage": "extract-facts",
        "emitter": "hal-datasheet",
        "kind": "02-facts",
        "filename": "halucinator/handoff/02-facts.toml",
        "consumes": {"01-sources": _leaves(CONSUMED_01)},
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
        "consumes": {"04-pac": _leaves(CONSUMED_04)},
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
        "consumes": {"05-platform": _leaves(CONSUMED_05)},
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
        "consumes": {"06-driver": _leaves(CONSUMED_06), "07-tests": CONSUME_ALL},
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


def analyze_typed_example(text: str, stage: str | None, kind: str | None,
                          known: frozenset[str],
                          arrays: frozenset[str] = frozenset()) -> list[tuple[str, str]]:
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
    ("schema not 1", _EXAMPLE_GOOD.replace("schema = 1", "schema = 2"), "SKILL_STRUCTURE_EXAMPLE_NOT_HANDOFF"),
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
    clean = analyze_typed_example(_EXAMPLE_GOOD, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS)
    if clean:
        problems.append(f"the conforming typed example was rejected with {[c for c, _ in clean]}")
    for name, text in _EXAMPLE_CLEAN_CASES:
        codes = [c for c, _ in analyze_typed_example(text, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS)]
        if codes:
            problems.append(f"conforming typed example {name!r} was rejected with {codes}")
    for name, text, expected in _EXAMPLE_CASES:
        codes = [c for c, _ in analyze_typed_example(text, "generate-pac", "04-pac", _EXAMPLE_KNOWN, _EXAMPLE_ARRAYS)]
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
            # CONSUME_ALL resolves against the AST registry, never a literal copy.
            want: dict[str, set[str]] = {}
            for kind, raw in spec["consumes"].items():
                if raw == CONSUME_ALL:
                    if kind not in registry:
                        report.bad(r, "consumes", "SKILL_CONSUMPTION_UNKNOWN_KIND",
                                   f"canonical mapping names predecessor kind {kind!r}, which the validator does not define")
                        continue
                    want[kind] = set(registry[kind]["paths"] | registry[kind]["common"])
                else:
                    want[kind] = set(raw)
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
            arrays = frozenset(registry[kind]["arrays"] | registry[kind]["common_arrays"]) if kind else frozenset()
            for code, message in analyze_typed_example(text, stage, kind, known, arrays):
                report.bad(r, "Application example", code, message)
            ok += 1
        report.ok("skill-structure", f"{ok} skills carry the ten template sections, assertable procedural form, and a typed TOML worked example matching their emitted kind (analyzer self-tested against {len(_FIXTURE_CASES) + len(_EXAMPLE_CASES)} near-misses)", mark)


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
                    if first_pub not in validating:
                        report.bad(r, "Procedure", "SKILL_VALIDATOR_PUBLICATION_MISSING",
                                   f"the first handoff-publishing step (step {steps[first_pub][0]}) does not invoke "
                                   "validate.py; a handoff published without validation is unchecked at exactly the "
                                   "moment it becomes a predecessor for the next stage")
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
                  f"{ok} skills place a validate.py invocation before their first handoff-publishing step, at that "
                  f"publishing step, and the {VALIDATOR_ALL!r} gate at or after their last one, and disclose the "
                  "honor-system limit", mark)


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
    r"\benable_and_reset\b",
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
# Cues by which a unit declines the composite-evidence responsibility rather
# than claiming it. These are NOT scanned as bare substrings anywhere in the
# unit - that was the demonstrated bypass, where "... does not alter the
# status" laundered an outright claim. A negation counts only when
# `_disclaims_composite` finds it BOUND to the act of creating composite
# evidence.
NEGATION_TOKENS = frozenset({"no", "not", "never", "without", "nor", "neither", "cannot"})
# Cues that defer the responsibility to a later stage rather than negating it.
DEFERRAL_TOKENS = frozenset({"pending", "reserved", "awaits", "awaiting", "deferred", "belongs"})
# Verbs that carry the responsibility itself. A negation must govern one of
# these, or the marker directly, to be a disclaimer.
RESPONSIBILITY_VERBS = frozenset({
    "create", "creates", "created", "creating",
    "produce", "produces", "produced", "producing",
    "assemble", "assembles", "assembled", "assembling",
    "author", "authors", "authored", "authoring",
    "generate", "generates", "generated", "generating",
    "compose", "composes", "composed", "composing",
    "publish", "publishes", "published", "publishing",
    "perform", "performs", "performed", "performing",
    "hold", "holds", "held", "holding",
    "own", "owns", "owned", "owning",
    "make", "makes", "made", "making",
    "do", "does", "did", "done",
})
# Binding windows, in intervening tokens. Tight by intent: the cue has to sit
# next to what it governs, not merely somewhere in the same sentence.
NEG_TO_VERB_WINDOW = 3
VERB_TO_MARKER_WINDOW = 2
NEG_TO_MARKER_WINDOW = 2
DEFERRAL_TO_MARKER_WINDOW = 4

NEGATED_PLACEMENT = (
    "no canonical placement",
    "without canonical placement",
    "not perform canonical placement",
    "never perform canonical placement",
)


def _disclaims_composite(unit: str) -> bool:
    """True when the unit binds a negation or deferral TO composite evidence.

    The old rule accepted any of `"no "` / `"not "` anywhere in the unit, and a
    reviewer duly bypassed it: "This slice creates composite evidence and does
    not alter the status." negates ALTERING THE STATUS while claiming the
    consolidator's exclusive work outright. The cue therefore has to be tied to
    the verb-plus-object relationship. Four bindings count:

      A. negation governing a responsibility verb that governs the marker
         - "do not create composite evidence"
      B. negation directly determining the marker
         - "no composite evidence"
      C. the marker as the antecedent of a TRAILING negated responsibility verb
         - "... composite evidence ... that this slice never held."
         Bounded to the end of the unit, so a negated verb that takes its own
         explicit object ("does not create the report") does not qualify.
      D. a table row whose OTHER cell negates the cell carrying the marker
         - "| Never done here | composite evidence, ... |"
         A row's cells are one assertion (see `prose_units`), so a label cell
         is a genuine verb-object binding and not a stray neighbouring clause.

    Neither reviewer bypass matches any of the four: in both the negation
    governs a different noun phrase ("the status", "unrelated file") and the
    trailing token is not a responsibility verb.
    """
    flat = norm_ws(unit).lower()

    # D. table row: a negation or deferral in a cell that does not itself
    # carry the marker binds to the cell that does.
    if flat.startswith("|"):
        cells = [c.strip() for c in flat.strip("|").split("|")]
        marker_cells = [i for i, c in enumerate(cells) if COMPOSITE_EVIDENCE_MARKER in c]
        if marker_cells:
            for i, cell in enumerate(cells):
                if i in marker_cells:
                    continue
                words = re.findall(r"[a-z]+", cell)
                if any(w in NEGATION_TOKENS or w in DEFERRAL_TOKENS for w in words):
                    return True

    tokens: list[str] = []
    spans: list[tuple[int, int]] = []
    for mt in re.finditer(r"[a-z]+", flat):
        tokens.append(mt.group(0))
        spans.append(mt.span())
    markers = [i for i in range(len(tokens) - 1)
               if tokens[i] == "composite" and tokens[i + 1] == "evidence"]
    if not markers:
        return False

    def clause_final(i: int) -> bool:
        """True when token i ends its clause - nothing but punctuation follows.

        This is what separates "...that this slice never held, so a `ready`
        here is a claim about work nobody did." (the verb governs the marker
        through the relative clause) from "...does not create the report."
        (the verb has taken its own explicit object).
        """
        tail = flat[spans[i][1]:].lstrip()
        return not tail or tail[0] in ",;.!?:)"

    for m in markers:
        # B. negation immediately determining the marker.
        lo = max(0, m - 1 - NEG_TO_MARKER_WINDOW)
        if any(t in NEGATION_TOKENS for t in tokens[lo:m]):
            return True
        # deferral determining the marker ("pending consolidation of the ...").
        lo = max(0, m - 1 - DEFERRAL_TO_MARKER_WINDOW)
        if any(t in DEFERRAL_TOKENS for t in tokens[lo:m]):
            return True
        # A. negation -> responsibility verb -> marker, each within its window.
        vlo = max(0, m - 1 - VERB_TO_MARKER_WINDOW)
        for k in range(vlo, m):
            if tokens[k] not in RESPONSIBILITY_VERBS:
                continue
            nlo = max(0, k - 1 - NEG_TO_VERB_WINDOW)
            if any(t in NEGATION_TOKENS for t in tokens[nlo:k]):
                return True
        # C. the marker as antecedent of a clause-final negated responsibility
        # verb somewhere after it.
        for k in range(m + 2, len(tokens)):
            if tokens[k] not in RESPONSIBILITY_VERBS or not clause_final(k):
                continue
            nlo = max(m + 2, k - NEG_TO_VERB_WINDOW)
            if any(t in NEGATION_TOKENS for t in tokens[nlo:k]):
                return True
    return False


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


def unattributed_composite_claims(text: str, consolidators: list[str]) -> list[str]:
    """Units that state the composite-evidence marker while claiming it.

    Absence of the phrase was the old rule, and it was the wrong one: it pushed
    a slice author into vaguer prose that no longer names what the slice is
    declining to do. The assertion is about the CLAIM, not the phrase. A unit
    is legal when it does one of:

      * attributes the work to the final consolidator BY NAME - the names come
        from `platform_roles(...)[1]`, i.e. the platform-stage skill whose own
        ready predicate is reachable, never from a literal written here; or
      * names the consolidating ROLE; or
      * disclaims the work with a negation BOUND to the act of creating
        composite evidence - see `_disclaims_composite`. A negation bound to
        anything else ("... and does not alter the status") is not a
        disclaimer, and was a demonstrated bypass of the earlier rule.

    Anything else - a unit that states composite evidence in its own voice with
    no attribution and no disclaimer - is the violation.
    """
    tokens = [n.lower() for n in consolidators] + [CONSOLIDATOR_ROLE_TOKEN]
    offenders: list[str] = []
    for unit in prose_units(text):
        flat = norm_ws(unit).lower()
        if COMPOSITE_EVIDENCE_MARKER not in flat:
            continue
        if any(t in flat for t in tokens):
            continue
        if _disclaims_composite(unit):
            continue
        offenders.append(_one_line(unit, 160))
    return offenders


_COMPOSITE_CONSOLIDATORS = ["omega-consolidate"]

# Units that must FAIL: the slice states composite evidence in its own voice.
_COMPOSITE_CLAIMS: tuple[tuple[str, str], ...] = (
    ("bare claim", "This slice creates composite evidence for all ten canonical checks.\n"),
    ("claim in a numbered step",
     "12. **Publish.** Create the composite evidence, then publish the handoff.\n"),
    ("claim in a table row", "| Done here | composite evidence, independent review |\n"),
    ("attribution stranded in a neighbouring bullet",
     "- The final consolidator owns the whole platform.\n"
     "- This step assembles composite evidence over every slice-local log.\n"),
    # --- the two bypasses a reviewer demonstrated against the substring rule --
    # Both state the claim outright and then negate something else entirely.
    # Under the old DISCLAIMER_CUES the bare tokens "not " / "no " matched and
    # the whole suite stayed green.
    ("claim laundered by an unrelated negated verb",
     "This slice creates composite evidence and does not alter the status.\n"),
    ("claim laundered by a negation of a different noun phrase",
     "This slice creates composite evidence; no unrelated file is touched.\n"),
    # Near-misses of the new binding: a negated responsibility verb that takes
    # its own explicit object is not a disclaimer of the marker.
    ("negated responsibility verb governing a different object",
     "This slice creates composite evidence and does not publish the roadmap.\n"),
)

# Units that must PASS: the phrase is named but attributed or disclaimed.
_COMPOSITE_ATTRIBUTIONS: tuple[tuple[str, str], ...] = (
    ("attributed by consolidator name",
     "Return the logs to `omega-consolidate`, which alone creates the composite evidence.\n"),
    ("attributed by role", "Only the final consolidator creates the composite evidence.\n"),
    ("disclaimed in a step",
     "13. **Return.** Do not publish `ready`, do not create composite evidence, do not request review.\n"),
    ("disclaimed in a table row", "| Never done here | composite evidence, canonical placement |\n"),
    ("disclaimed by a trailing negation",
     "The `ready` platform asserts composite evidence and an accepting review that this slice never held.\n"),
    ("disclaimed by a mid-sentence negated clause that the sentence continues past",
     "The `ready` platform asserts composite evidence and an accepting review that this slice never "
     "held, so a `ready` here is a claim about work nobody did.\n"),
    ("deferred as pending consolidation",
     "Complete-platform checks stay unrun here, pending consolidation of the composite evidence.\n"),
    # Shapes taken from the shipped slices, so a reword of the binding rule
    # cannot silently start rejecting conforming prose.
    ("disclaimed as one item in a negated list",
     "State explicitly that no canonical placement, no composite evidence and no independent review was performed.\n"),
    ("disclaimed by a table label cell",
     "| Never done here | composite evidence, independent review, canonical placement, `ready` |\n"),
    ("deferred by a table label cell",
     "| Reserved to the final skill | composite evidence, independent review |\n"),
)


def composite_analyzer_failures() -> list[str]:
    """Self-test `unattributed_composite_claims`. Empty when it discriminates."""
    problems: list[str] = []
    for name, text in _COMPOSITE_CLAIMS:
        if not unattributed_composite_claims(text, _COMPOSITE_CONSOLIDATORS):
            problems.append(f"composite CLAIM near-miss {name!r} was not caught; the rule permits an unattributed claim")
    for name, text in _COMPOSITE_ATTRIBUTIONS:
        offenders = unattributed_composite_claims(text, _COMPOSITE_CONSOLIDATORS)
        if offenders:
            problems.append(f"composite ATTRIBUTION {name!r} was rejected ({offenders[0]!r}); the rule forbids naming what the slice declines to do")
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
            offenders = unattributed_composite_claims(text, final)
            if offenders:
                report.bad(r, "Procedure", "SKILL_PLATFORM_SLICE_COMPOSITE",
                           f"a non-final platform slice states {COMPOSITE_EVIDENCE_MARKER!r} in its own voice, with "
                           f"neither attribution to the final platform consolidator nor a disclaimer: "
                           f"{offenders[0]!r}; composite evidence across all slices belongs only to the consolidator")

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
                  f"otherwise consume the {PLATFORM_KIND} snapshot, attribute or disclaim every mention of "
                  f"{COMPOSITE_EVIDENCE_MARKER!r}, and {len(final)} final consolidator carries "
                  "composite evidence, review and canonical placement "
                  f"(analyzer self-tested against {len(_COMPOSITE_CLAIMS)} claims and {len(_COMPOSITE_ATTRIBUTIONS)} attributions)", mark)


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
    check_selfcheck_doc_parity(root, report)
    return report.emit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
