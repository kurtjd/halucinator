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
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path, PurePosixPath

SUBPROCESS_TIMEOUT = 30

BASELINE_RELPATH = "tools/terminology-baseline.tsv"

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

MANDATED_FIXTURES = 29

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
    """Root *.md plus .opencode/**/*.md, skipping node_modules and caches."""
    out: list[Path] = []
    for entry in sorted(root.glob("*.md")):
        if entry.is_file():
            out.append(entry)
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


def check_fixtures(root: Path, report: Report) -> None:
    mark = report.mark()
    validator = root / ".opencode" / "schema" / "validate.py"
    fixtures = root / ".opencode" / "schema" / "fixtures"
    if not validator.is_file():
        report.bad(rel(root, validator), "0", "VALIDATOR_MISSING", "validator script not found; check 3 cannot run")
        return
    valid = fixtures / "valid"
    if not valid.is_dir():
        report.bad(rel(root, valid), "0", "FIXTURE_MISSING", "valid fixture directory not found")
        return

    rc, out = run_validator(root, validator, valid)
    if rc != 0:
        report.bad(rel(root, valid), "0", "FIXTURE_VALID_REJECTED", f"valid fixture must exit 0, got {rc}: {_one_line(out)}")
    elif out.strip():
        report.bad(rel(root, valid), "0", "FIXTURE_VALID_NOISY", f"valid fixture must emit no diagnostics: {_one_line(out)}")

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
        passed += 1

    report.ok("fixtures", f"valid fixture accepted and {passed} of {len(cases)} invalid fixtures rejected with exit 1 and their declared code", mark)


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


def parse_contract(text: str) -> tuple[list[tuple[str, str, int]], str | None, int]:
    """Parse the single raw ```halucinator-agent-contract fence after the H1.

    Returns (entries, error, lineno). Entries are (key, value, lineno).
    Operates on RAW markdown: strip_code() would erase this block entirely.
    """
    lines = text.split("\n")
    h1 = None
    for i, line in enumerate(lines):
        if line.startswith("# "):
            h1 = i
            break
    if h1 is None:
        return [], "file has no '# ' H1 heading; the agent contract must follow it", 1

    blocks: list[tuple[int, list[str]]] = []
    i = h1 + 1
    scanned = 0
    while i < len(lines) and scanned < MAX_CONTRACT_LINES * 8:
        scanned += 1
        stripped = lines[i].strip()
        if stripped.startswith("```") and stripped[3:].strip() == CONTRACT_INFO:
            body: list[str] = []
            j = i + 1
            while j < len(lines) and len(body) < MAX_CONTRACT_LINES:
                if lines[j].strip().startswith("```"):
                    break
                body.append(lines[j])
                j += 1
            else:
                return [], f"unterminated '{CONTRACT_INFO}' fence", i + 1
            if j >= len(lines):
                return [], f"unterminated '{CONTRACT_INFO}' fence", i + 1
            blocks.append((i + 1, body))
            i = j + 1
            continue
        i += 1

    if not blocks:
        return [], f"no raw '```{CONTRACT_INFO}' fence found after the H1; add the agent contract block", h1 + 1
    if len(blocks) > 1:
        return [], f"expected exactly one '{CONTRACT_INFO}' fence, found {len(blocks)}", blocks[1][0]

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
    return report.emit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
