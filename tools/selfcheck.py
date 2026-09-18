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
    return report.emit()


if __name__ == "__main__":
    sys.exit(main(sys.argv))
