#!/usr/bin/env python3
"""Regenerate every committed schema fixture from one declarative source.

H10 closure. Before this existed the fixture corpus was ~1000 committed files
that nothing in the tree could reproduce: a reviewer could not tell an
intentional mutation from a typo, and a schema change meant hand-editing a
hash closure across 37 roots. Source, generator and byte-identical
regeneration are now all in-tree.

    python tools/generate_schema_fixtures.py --root . --write
    python tools/generate_schema_fixtures.py --root . --check

`--write` regenerates `.opencode/schema/fixtures/<root>/` for every declared
root. `--check` generates into a temporary directory, compares the relative
path set and every raw byte against the committed roots, and exits 0 only on
exact equality. Check mode never rewrites.

The declaration is `tools/schema-fixtures.toml`. It carries the fictional
payload strings, the base-root topology, each mutation operation and each
expected diagnostic triple. It carries **no computed hashes**: every FileRef
digest is derived from the bytes this generator actually emits, which is what
makes the hash closure a consequence of the declaration rather than a parallel
artifact that can drift.

Output is UTF-8 with LF endings, stable ordering, stable timestamps, and no
environment paths. Standard library only. Python 3.11+.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import tomllib

DECLARATION = "tools/schema-fixtures.toml"
FIXTURE_ROOT = ".opencode/schema/fixtures"
AUTO = "@auto"
MAX_FILES_PER_ROOT = 512


class DeclarationError(Exception):
    """The declaration is unusable. Always fatal; never silently tolerated."""


# --------------------------------------------------------------------------
# Fictional-content guard
#
# The whole point of this milestone is that hardware facts are never invented.
# Inventing one in a fixture would be a spectacular way to fail, so the only
# permitted example material is the transparently fictional target and manual.
# --------------------------------------------------------------------------

REQUIRED_FICTIONAL_MARKERS = ("FICTIONAL", "not-a-real")


def guard_fictional(meta: dict) -> None:
    target = str(meta.get("target_id", ""))
    title = str(meta.get("document_title", ""))
    part = str(meta.get("mcu_part_number", ""))
    if "not-a-real" not in target.lower():
        raise DeclarationError(
            "meta.target_id %r is not transparently fictional; the generator refuses "
            "any target string that could be mistaken for real silicon" % target)
    if "not-a-real" not in part.lower():
        raise DeclarationError(
            "meta.mcu_part_number %r is not transparently fictional" % part)
    if "FICTIONAL" not in title.upper():
        raise DeclarationError(
            "meta.document_title %r does not announce itself as fictional; a citation "
            "gate demonstrated against a plausible-looking manual title teaches exactly "
            "the wrong lesson" % title)


# --------------------------------------------------------------------------
# Deterministic TOML emission
# --------------------------------------------------------------------------


def toml_value(value) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, float):
        raise DeclarationError("floats are not representable in a fixture document")
    if isinstance(value, str):
        return '"%s"' % value.replace("\\", "\\\\").replace('"', '\\"')
    if isinstance(value, list):
        return "[" + ",".join(toml_value(item) for item in value) + "]"
    if isinstance(value, dict):
        return "{" + ",".join("%s=%s" % (quote_key(k), toml_value(v))
                              for k, v in value.items()) + "}"
    raise DeclarationError("unserializable value %r" % (value,))


def quote_key(key: str) -> str:
    if key and all(ch.isalnum() or ch in "_-" for ch in key):
        return key
    return '"%s"' % key.replace("\\", "\\\\").replace('"', '\\"')


def emit_document(document: dict) -> bytes:
    """Bare top-level keys first, then one `[table]` section per nested table.

    An array of tables is emitted as an ordinary top-level key whose value is
    an array of inline tables. TOML parses that identically to repeated
    `[[name]]` headers, and it keeps the emitter to one code path.
    """
    lines: list[str] = []
    for key, value in document.items():
        if isinstance(value, dict):
            continue
        lines.append("%s=%s" % (quote_key(key), toml_value(value)))
    for key, value in document.items():
        if not isinstance(value, dict):
            continue
        lines.append("[%s]" % quote_key(key))
        for inner_key, inner_value in value.items():
            lines.append("%s=%s" % (quote_key(inner_key), toml_value(inner_value)))
    return ("\n".join(lines) + "\n").encode("utf-8")


# --------------------------------------------------------------------------
# FileRef digest resolution
# --------------------------------------------------------------------------


def ref_relpath(ref: dict) -> str | None:
    """Where inside the fixture root a FileRef's bytes live, if anywhere."""
    path = ref.get("path")
    if not isinstance(path, str) or not path:
        return None
    root = ref.get("root")
    if root is None:
        return "root/" + path
    if isinstance(root, str) and root.startswith("generation:"):
        return "generation-roots/" + root.split(":", 1)[1] + "/" + path
    return None


def resolve_auto_digests(value, emitted: dict[str, bytes], where: str):
    """Replace every `sha256 = "@auto"` with the digest of the emitted bytes.

    A digest that cannot be resolved is a declaration error, not a silent
    placeholder: a fixture whose closure quietly went stale would fail for a
    reason nobody declared.
    """
    if isinstance(value, list):
        return [resolve_auto_digests(item, emitted, where) for item in value]
    if not isinstance(value, dict):
        return value
    out = {}
    for key, inner in value.items():
        out[key] = resolve_auto_digests(inner, emitted, where)
    if out.get("sha256") == AUTO:
        relpath = ref_relpath(out)
        if relpath is None or relpath not in emitted:
            raise DeclarationError(
                "%s: cannot resolve @auto digest for %r; the referenced file is not "
                "emitted before its referrer. Fix the document order." % (where, out))
        out["sha256"] = hashlib.sha256(emitted[relpath]).hexdigest()
    return out


# --------------------------------------------------------------------------
# Mutation operations
# --------------------------------------------------------------------------


def split_path(dotted: str) -> list[str]:
    return [part for part in dotted.split(".") if part != ""]


def descend(container, parts: list[str], create: bool):
    for part in parts:
        if isinstance(container, list):
            index = int(part)
            if index >= len(container):
                raise DeclarationError("index %d past end of array" % index)
            container = container[index]
            continue
        if not isinstance(container, dict):
            raise DeclarationError("cannot descend into %r at %r" % (type(container), part))
        if part not in container:
            if not create:
                raise DeclarationError("missing key %r" % part)
            container[part] = {}
        container = container[part]
    return container


def apply_set(document: dict, dotted: str, value) -> None:
    parts = split_path(dotted)
    parent = descend(document, parts[:-1], create=True)
    leaf = parts[-1]
    if isinstance(parent, list):
        parent[int(leaf)] = value
    else:
        parent[leaf] = value


def apply_unset(document: dict, dotted: str) -> None:
    parts = split_path(dotted)
    parent = descend(document, parts[:-1], create=False)
    leaf = parts[-1]
    if isinstance(parent, list):
        del parent[int(leaf)]
    elif leaf in parent:
        del parent[leaf]
    else:
        raise DeclarationError("unset of absent key %r" % dotted)


def apply_operations(documents: dict, payloads: dict, order: list[str],
                     operations: list[dict], name: str) -> None:
    """Mutate the model BEFORE emission, so the hash closure recomputes itself."""
    for index, operation in enumerate(operations):
        kind = operation.get("op")
        where = "%s op[%d] (%s)" % (name, index, kind)
        try:
            if kind == "set":
                apply_set(documents[operation["doc"]], operation["path"], operation["value"])
            elif kind == "unset":
                apply_unset(documents[operation["doc"]], operation["path"])
            elif kind == "append":
                target = descend(documents[operation["doc"]],
                                 split_path(operation["path"]), create=False)
                if not isinstance(target, list):
                    raise DeclarationError("append target is not an array")
                target.append(operation["value"])
            elif kind == "add-doc":
                documents[operation["doc"]] = copy.deepcopy(operation["value"])
                position = operation.get("after")
                if position and position in order:
                    order.insert(order.index(position) + 1, operation["doc"])
                else:
                    order.append(operation["doc"])
            elif kind == "copy-doc":
                documents[operation["doc"]] = copy.deepcopy(documents[operation["from"]])
                position = operation.get("after", operation["from"])
                order.insert(order.index(position) + 1, operation["doc"])
            elif kind == "drop-doc":
                documents.pop(operation["doc"], None)
                if operation["doc"] in order:
                    order.remove(operation["doc"])
            elif kind == "set-payload":
                payloads[operation["path"]] = operation["value"]
            elif kind == "drop-payload":
                payloads.pop(operation["path"], None)
            else:
                raise DeclarationError("unknown op %r" % kind)
        except DeclarationError:
            raise
        except (KeyError, IndexError, ValueError, TypeError) as exc:
            raise DeclarationError("%s failed: %s" % (where, exc))


# --------------------------------------------------------------------------
# Root generation
# --------------------------------------------------------------------------


def collect_auto_refs(value, acc: set) -> None:
    if isinstance(value, list):
        for item in value:
            collect_auto_refs(item, acc)
        return
    if not isinstance(value, dict):
        return
    if value.get("sha256") == AUTO:
        relpath = ref_relpath(value)
        if relpath:
            acc.add(relpath)
    for item in value.values():
        collect_auto_refs(item, acc)


def emission_order(documents: dict, declared: list[str]) -> list[str]:
    """Topological order over `@auto` references, tie-broken by the declared order.

    Deriving the order rather than trusting a static list means a mutation that
    adds a document cannot silently produce an unresolvable hash closure, and
    the result is still deterministic.
    """
    rank = {name: index for index, name in enumerate(declared)}
    pending = sorted(documents, key=lambda name: (rank.get(name, len(rank)), name))
    dependencies: dict[str, set] = {}
    for name in pending:
        acc: set = set()
        collect_auto_refs(documents[name], acc)
        dependencies[name] = {dep for dep in acc if dep in documents and dep != name}
    order: list[str] = []
    placed: set = set()
    for _ in range(len(pending) + 1):
        progressed = False
        for name in pending:
            if name in placed or not dependencies[name] <= placed:
                continue
            order.append(name)
            placed.add(name)
            progressed = True
        if len(placed) == len(pending):
            return order
        if not progressed:
            break
    raise DeclarationError(
        "documents form a hash cycle and cannot be ordered: %s"
        % sorted(set(pending) - placed))


def generate_root(spec: dict, bases: dict, name: str) -> dict[str, bytes]:
    base_name = spec.get("base")
    if base_name is not None:
        base = bases.get(base_name)
        if base is None:
            raise DeclarationError("%s: unknown base %r" % (name, base_name))
        documents = copy.deepcopy(base["documents"])
        payloads = copy.deepcopy(base["payloads"])
        order = list(base["order"])
    else:
        documents = copy.deepcopy(spec.get("documents", {}))
        payloads = copy.deepcopy(spec.get("payloads", {}))
        order = list(spec.get("order", []))

    apply_operations(documents, payloads, order, list(spec.get("ops", [])), name)

    emitted: dict[str, bytes] = {}
    for relpath in sorted(payloads):
        emitted[relpath] = normalize_text(payloads[relpath])
    for relpath in emission_order(documents, order):
        resolved = resolve_auto_digests(documents[relpath], emitted,
                                        "%s/%s" % (name, relpath))
        emitted[relpath] = emit_document(resolved)
    if len(emitted) > MAX_FILES_PER_ROOT:
        raise DeclarationError("%s: %d files exceeds the bound" % (name, len(emitted)))
    return emitted


def normalize_text(text: str) -> bytes:
    """UTF-8, LF endings, exactly one trailing newline."""
    body = text.replace("\r\n", "\n").replace("\r", "\n")
    if not body.endswith("\n"):
        body += "\n"
    return body.encode("utf-8")


def readme_bytes(spec: dict, name: str) -> bytes:
    lines = [
        "# `%s`" % name,
        "",
        "FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE",
        "",
        spec["summary"].strip(),
        "",
        "The validator must emit exactly this diagnostic set - no more, no fewer.",
        "`Reporter` stores its lines in a set, so a repeated diagnostic is",
        "unobservable and the assertion is over the sorted SET, not a multiset.",
        "",
    ]
    for entry in spec.get("expect", []):
        lines.append("Expected diagnostic: `%s|%s|%s`"
                     % (entry["file"], entry.get("field", ""), entry["code"]))
    lines += [
        "",
        "Regenerate with `python tools/generate_schema_fixtures.py --root . --write`;",
        "every byte here is derived from `tools/schema-fixtures.toml`.",
        "",
        "Invoke as:",
        "",
        "```text",
        "python .opencode/schema/validate.py <this-dir>/root \\",
        "  --root generation:fictional-pac=<abs-path-to>/%s/generation-roots/fictional-pac"
        % name,
        "```",
        "",
        "Expected exit code: 1.",
    ]
    return normalize_text("\n".join(lines))


def build_all(declaration: dict) -> dict[str, dict[str, bytes]]:
    guard_fictional(declaration.get("meta", {}))
    shared_payloads = declaration.get("payloads", {})
    bases: dict[str, dict] = {}
    roots: dict[str, dict[str, bytes]] = {}

    for entry in declaration.get("base", []):
        name = entry["name"]
        payloads = dict(shared_payloads)
        payloads.update(entry.get("payloads", {}))
        spec = {"documents": entry.get("documents", {}),
                "payloads": payloads,
                "order": entry.get("order", []),
                "ops": entry.get("ops", [])}
        if entry.get("base"):
            spec["base"] = entry["base"]
        bases[name] = {
            "documents": copy.deepcopy(spec.get("documents") or bases[entry["base"]]["documents"]),
            "payloads": payloads if not entry.get("base") else
                        {**bases[entry["base"]]["payloads"], **entry.get("payloads", {})},
            "order": list(spec.get("order") or bases[entry["base"]]["order"]),
        }
        if entry.get("base"):
            apply_operations(bases[name]["documents"], bases[name]["payloads"],
                             bases[name]["order"], list(entry.get("ops", [])), name)
        if entry.get("emit", True):
            roots[name] = generate_root({"base": name}, bases, name)
            readme = entry.get("readme")
            if isinstance(readme, str) and readme.strip():
                roots[name]["README.md"] = normalize_text(readme)

    for entry in declaration.get("extra", []):
        name = entry["name"]
        roots[name] = {relpath: normalize_text(text)
                       for relpath, text in entry.get("payloads", {}).items()}

    for entry in declaration.get("invalid", []):
        name = entry["name"]
        if not isinstance(name, str) or not name:
            raise DeclarationError("every invalid entry needs a nonempty name")
        emitted = generate_root(entry, bases, name)
        emitted["README.md"] = readme_bytes(entry, name)
        roots["invalid/" + name] = emitted
    return roots


# --------------------------------------------------------------------------
# Write and check
# --------------------------------------------------------------------------


def write_roots(destination: str, roots: dict[str, dict[str, bytes]]) -> None:
    for name, files in roots.items():
        root_dir = os.path.join(destination, *name.split("/"))
        if os.path.isdir(root_dir):
            shutil.rmtree(root_dir)
        for relpath, data in sorted(files.items()):
            target = os.path.join(root_dir, *relpath.split("/"))
            os.makedirs(os.path.dirname(target), exist_ok=True)
            with open(target, "wb") as handle:
                handle.write(data)


def collect_committed(root_dir: str) -> dict[str, bytes]:
    out: dict[str, bytes] = {}
    if not os.path.isdir(root_dir):
        return out
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dirnames.sort()
        for filename in sorted(filenames):
            full = os.path.join(dirpath, filename)
            relpath = os.path.relpath(full, root_dir).replace(os.sep, "/")
            with open(full, "rb") as handle:
                out[relpath] = handle.read()
    return out


def check_roots(fixtures_dir: str, roots: dict[str, dict[str, bytes]]) -> list[str]:
    problems: list[str] = []
    committed_names = set()
    for entry in sorted(os.listdir(fixtures_dir)) if os.path.isdir(fixtures_dir) else []:
        full = os.path.join(fixtures_dir, entry)
        if not os.path.isdir(full):
            continue
        if entry == "invalid":
            for inner in sorted(os.listdir(full)):
                if os.path.isdir(os.path.join(full, inner)):
                    committed_names.add("invalid/" + inner)
        else:
            committed_names.add(entry)

    for name in sorted(committed_names - set(roots)):
        problems.append("undeclared committed fixture root: %s" % name)
    for name in sorted(set(roots) - committed_names):
        problems.append("declared fixture root is not committed: %s" % name)

    for name in sorted(set(roots) & committed_names):
        generated = roots[name]
        committed = collect_committed(os.path.join(fixtures_dir, *name.split("/")))
        for relpath in sorted(set(committed) - set(generated)):
            problems.append("%s: extra committed file %s" % (name, relpath))
        for relpath in sorted(set(generated) - set(committed)):
            problems.append("%s: missing committed file %s" % (name, relpath))
        for relpath in sorted(set(generated) & set(committed)):
            if generated[relpath] != committed[relpath]:
                problems.append("%s: %s differs from the generated bytes" % (name, relpath))
    return problems


# --------------------------------------------------------------------------
# Committed-set guard
#
# Comparing the generator against the WORKING TREE is not enough, and the hole
# is not theoretical: a regeneration that stopped emitting a previously
# committed file deleted it from the worktree, after which both sides agreed it
# was absent and `--check` passed. A verification whose two sides can be wrong
# in the same direction certifies nothing.
#
# The committed set is therefore read from Git, which is the only record of
# what was there before this run. Git is already a dependency of the
# repository-only tooling (`tools/selfcheck.py` reads it for the terminology
# baseline), and this file is repository-only tooling, not shipped runtime.
# --------------------------------------------------------------------------

GIT_TIMEOUT = 60

# Hand-authored documents that live at the fixtures root and belong to no
# generated root. Closed and short on purpose: anything else committed outside
# a declared root is reported rather than quietly tolerated.
FIXTURE_ROOT_DOCS = ("README.md", "EXPECTATIONS.md")


def _git_paths(repo: str, argv: list[str]) -> tuple[set[str] | None, str | None]:
    """Run one bounded `git` path-listing command. (paths, error)."""
    try:
        proc = subprocess.run(argv, cwd=repo, capture_output=True, timeout=GIT_TIMEOUT)
    except FileNotFoundError:
        return None, ("git is not installed or not on PATH, so the committed fixture "
                      "set cannot be established. Install Git and rerun, or run "
                      "--check from a Git working tree.")
    except subprocess.TimeoutExpired:
        return None, "%s did not finish in %ds" % (" ".join(argv[:3]), GIT_TIMEOUT)
    except OSError as exc:
        return None, "%s could not be executed: %s" % (" ".join(argv[:3]), exc)
    if proc.returncode != 0:
        detail = proc.stderr.decode("utf-8", "replace").strip()[:300]
        return None, ("%s exited %d: %s" % (" ".join(argv[:3]), proc.returncode, detail))
    prefix = FIXTURE_ROOT + "/"
    out: set[str] = set()
    for raw in proc.stdout.decode("utf-8", "replace").split("\0"):
        path = raw.strip()
        if path.startswith(prefix):
            out.add(path[len(prefix):])
    return out, None


def committed_fixture_paths(repo: str) -> tuple[set[str], str | None]:
    """Fixture paths tracked by Git, relative to the fixtures directory.

    The union of the last commit (`ls-tree HEAD`) and the index (`ls-files`).
    Reading only the index would let a staged `git rm` silently retire a file
    from the guard's view, which is the same "both sides wrong in the same
    direction" failure the guard exists to prevent; reading only HEAD would miss
    a file added and declared in this change.

    Returns (paths, error). An error means the committed set could not be
    established, which is a refusal, never an empty set: treating "cannot ask
    Git" as "nothing was committed" would reopen exactly this hole.
    """
    index, error = _git_paths(repo, ["git", "ls-files", "-z", "--", FIXTURE_ROOT])
    if error is not None or index is None:
        return set(), error or "git ls-files produced no result"
    head, head_error = _git_paths(
        repo, ["git", "ls-tree", "-r", "-z", "--name-only", "HEAD", "--", FIXTURE_ROOT])
    if head is None:
        # A repository with no commit yet has no HEAD. That is the one case
        # where the index alone is the whole history, so it is not a refusal.
        probe = subprocess.run(["git", "rev-parse", "--verify", "-q", "HEAD"],
                               cwd=repo, capture_output=True, timeout=GIT_TIMEOUT)
        if probe.returncode == 0:
            return set(), head_error or "git ls-tree produced no result"
        head = set()
    return index | head, None


def check_committed_coverage(repo: str, roots: dict[str, dict[str, bytes]]) -> list[str]:
    """Every Git-committed fixture path must still be produced by the generator."""
    committed, error = committed_fixture_paths(repo)
    if error is not None:
        return ["cannot verify the committed fixture set: " + error]
    if not committed:
        return ["git reports no tracked files under %s; the committed-set guard would "
                "assert nothing, so this is a failure rather than a pass" % FIXTURE_ROOT]
    # Longest-first so `valid-multi-driver/...` is not attributed to `valid`.
    names = sorted(roots, key=len, reverse=True)
    problems: list[str] = []
    for relpath in sorted(committed):
        if "/" not in relpath:
            if relpath not in FIXTURE_ROOT_DOCS:
                problems.append(
                    "committed fixture document %s belongs to no declared root and is "
                    "not a known fixtures-root document" % relpath)
            continue
        owner = None
        for name in names:
            if relpath.startswith(name + "/"):
                owner = name
                break
        if owner is None:
            problems.append(
                "committed fixture path %s belongs to no declared root; a whole root "
                "was removed from the declaration without being removed from Git"
                % relpath)
            continue
        inner = relpath[len(owner) + 1:]
        if inner not in roots[owner]:
            problems.append(
                "committed fixture file %s is no longer produced by the generator; "
                "regenerating would DELETE it. Declare it or remove it deliberately."
                % relpath)
    return problems


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="generate_schema_fixtures.py",
        description="Regenerate or byte-verify the committed schema fixtures.")
    parser.add_argument("--root", required=True, help="repository root")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)

    repo = os.path.abspath(args.root)
    declaration_path = os.path.join(repo, *DECLARATION.split("/"))
    try:
        with open(declaration_path, "rb") as handle:
            declaration = tomllib.loads(handle.read().decode("utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        print("cannot read %s: %s" % (DECLARATION, exc), file=sys.stderr)
        return 2

    try:
        roots = build_all(declaration)
    except DeclarationError as exc:
        print("declaration error: %s" % exc, file=sys.stderr)
        return 2

    fixtures_dir = os.path.join(repo, *FIXTURE_ROOT.split("/"))
    if args.write:
        write_roots(fixtures_dir, roots)
        return 0

    scratch = tempfile.mkdtemp(prefix="halucinator-fixture-check-")
    try:
        write_roots(scratch, roots)
        problems = check_committed_coverage(repo, roots)
        problems += check_roots(fixtures_dir, roots)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    if problems:
        for problem in problems[:40]:
            print(problem, file=sys.stderr)
        if len(problems) > 40:
            print("... and %d more" % (len(problems) - 40), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
