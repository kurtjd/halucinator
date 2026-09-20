#!/usr/bin/env python3
"""Executable tests for the citation verifier - the gate this milestone exists for.

Discovered by `python -m unittest discover -s .opencode/schema -p "test_*.py"`.

`verify_citation` is exercised directly with an **injected runner**, so the
failure modes of the external `pdftotext` boundary - absent, timeout, bad page -
are provoked without depending on whether poppler happens to be installed on the
machine running the suite. Every case below actually injects its fault: the
runner raises the real `CitationFailure` the production `run_pdftotext` raises,
or the source bytes on disk are genuinely malformed for that case. A test that
merely carried the right name would assert nothing, and the self-check that
counts these names cannot tell the difference - so the assertions are the
evidence.

All example material is the transparently fictional
`unobtainium-circuits-uc-not-a-real-mcu-0001` and its FICTIONAL FIXTURE
REFERENCE MANUAL. Nothing here describes real silicon.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
import unittest

import validate


FICTIONAL_MANUAL = (
    "FICTIONAL FIXTURE REFERENCE MANUAL\n"
    "Unobtainium Circuits UC-NOT-A-REAL-MCU-0001\n"
    "FICTIONAL SCHEMA FIXTURE - NOT HARDWARE EVIDENCE\n"
    "\n"
    "Section 2.1 Schema-demo reset state\n"
    "\n"
    "The SCHEMA_DEMO block is an invented fixture peripheral that exists only to\n"
    "exercise this schema. After a fixture reset the block reports the invented\n"
    "value zero in every invented field. No sentence in this file describes real\n"
    "silicon, and nothing here may be copied into a driver.\n"
)

EXCERPT = ("After a fixture reset the block reports the invented value zero in "
           "every invented field.")


class Recorder:
    """Collects diagnostics instead of printing them."""

    def __init__(self) -> None:
        self.found: list[tuple[str, str, str, str]] = []

    def emit(self, where, field, code, expectation, found, remedy):
        self.found.append((field, code, str(found), str(remedy)))

    def codes(self) -> list[str]:
        return [code for _f, code, _v, _r in self.found]

    def payload(self) -> str:
        return " ".join(value for _f, _c, value, _r in self.found)

    def remedies(self) -> str:
        return " ".join(remedy for _f, _c, _v, remedy in self.found)


class Ctx:
    """The minimal context `verify_citation` needs: a root binding and an emitter."""

    def __init__(self, root: str) -> None:
        self.roots = validate.Roots(root, {})
        self.rep = Recorder()
        self.where = "halucinator/handoff/02-facts.toml"

    def err(self, field, code, expectation, found, remedy):
        self.rep.emit(self.where, field, code, expectation, found, remedy)


class CitationCase(unittest.TestCase):
    """Shared fixture: one fictional manual on disk and a citation that fits it."""

    def setUp(self) -> None:
        self.root = tempfile.mkdtemp(prefix="halucinator-citation-")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.ctx = Ctx(self.root)

    def write_source(self, relpath: str, data: bytes) -> dict:
        target = os.path.join(self.root, *relpath.split("/"))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        with open(target, "wb") as handle:
            handle.write(data)
        return {"path": relpath, "sha256": hashlib.sha256(data).hexdigest()}

    def text_source(self, text: str = FICTIONAL_MANUAL) -> dict:
        return self.write_source("halucinator/docs/fictional/sources/MANUAL.txt",
                                 text.encode("utf-8"))

    def pdf_source(self) -> dict:
        # Opaque bytes: the injected runner decides what this "page" contains,
        # so no real PDF writer is needed and no real PDF is implied.
        return self.write_source("halucinator/docs/fictional/sources/MANUAL.pdf",
                                 b"%PDF-1.4 fictional fixture placeholder\n")

    def document(self, ref: dict, fmt: str = "utf8-text") -> dict:
        return {"doc-001": {
            "source_id": "doc-001",
            "document": "FICTIONAL FIXTURE REFERENCE MANUAL",
            "revision": "fixture-1", "format": fmt, "source": ref}}

    def citation(self, ref: dict, excerpt: str = EXCERPT,
                 location: dict | None = None) -> dict:
        return {
            "assertion_id": "fact.schema-demo.reset-state",
            "scope_item": "peripheral:schema-demo",
            "claim": "The fictional block reports zero after a fixture reset.",
            "source_id": "doc-001", "source": ref,
            "location": location or {"kind": "text-lines",
                                     "line_start": 7, "line_end": 10},
            "locator": {"kind": "section", "value": "Section 2.1"},
            "excerpt": excerpt,
            "note": {"path": "halucinator/docs/fictional/notes/FACTS.md",
                     "sha256": "0" * 64},
        }

    def verify(self, citation: dict, documents: dict, runner=None) -> Recorder:
        validate.verify_citation(self.ctx, 0, citation, documents,
                                 runner=runner or validate.run_pdftotext)
        return self.ctx.rep


class TestHonestExcerptIsAccepted(CitationCase):
    def test_honest_excerpt_at_the_cited_lines_verifies(self):
        """A quotation that really is at the cited lines produces no diagnostic."""
        ref = self.text_source()
        rep = self.verify(self.citation(ref), self.document(ref))
        self.assertEqual(rep.codes(), [], rep.payload())

    def test_absent_excerpt_is_refused(self):
        """A plausible sentence that is not there is refused, with a candidate."""
        ref = self.text_source()
        fabricated = ("The invented block latches an invented sentinel that appears "
                      "nowhere in this fixture manual.")
        rep = self.verify(self.citation(ref, excerpt=fabricated), self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("closest candidate", rep.payload())


class FakeCompleted:
    """What `subprocess.run` returns, as `run_pdftotext` actually consumes it."""

    def __init__(self, returncode: int = 0, stdout: bytes = b"", stderr: bytes = b""):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


class SubprocessBoundary(unittest.TestCase):
    """`run_pdftotext` itself - the only function permitted to start a process.

    These reach the PRODUCTION wrapper and replace `subprocess.run` underneath
    it, so the argv it builds, the timeout it passes and its translation of
    every exception are all executed. Injecting an already-constructed
    `CitationFailure` at the `verify_citation` seam would leave all of that
    unrun, and a regression in command construction would pass unnoticed.
    """

    def setUp(self) -> None:
        self.real = validate.subprocess.run
        self.addCleanup(setattr, validate.subprocess, "run", self.real)
        self.calls: list[dict] = []

    def install(self, behaviour):
        def fake_run(cmd, **kwargs):
            self.calls.append({"cmd": cmd, "kwargs": kwargs})
            return behaviour(cmd, kwargs)
        validate.subprocess.run = fake_run

    def test_subprocess_argument_array_and_timeout_are_exact(self):
        """The argv array, the no-shell invocation and the timeout are asserted.

        `run_pdftotext` must pass a LIST - never a joined string through a
        shell - so a source path containing a space or a quote cannot become
        additional arguments.
        """
        self.install(lambda cmd, kwargs: FakeCompleted(stdout=b"page text\n"))
        out = validate.run_pdftotext(r"C:\a path\fictional manual.pdf", 7)
        self.assertEqual(out, "page text\n")
        self.assertEqual(len(self.calls), 1)
        argv = self.calls[0]["cmd"]
        self.assertIsInstance(argv, list, "argv must be a list, never a shell string")
        self.assertEqual(argv, ["pdftotext", "-layout", "-f", "7", "-l", "7",
                                r"C:\a path\fictional manual.pdf", "-"])
        kwargs = self.calls[0]["kwargs"]
        self.assertEqual(kwargs.get("timeout"), validate.PDFTOTEXT_TIMEOUT)
        self.assertTrue(kwargs.get("capture_output"))
        self.assertNotIn("shell", kwargs, "the verifier must never use a shell")
        self.assertIsNot(kwargs.get("text"), True, "stdout must be handled as bytes")

    def test_subprocess_output_bound_rejects_an_oversized_page(self):
        """The 16 MiB output cap is enforced on what the tool actually returns.

        An overflowing page must fail closed rather than being decoded and
        matched against: an unbounded read is how a verifier becomes a memory
        exhaustion vector on a hostile or simply broken PDF.
        """
        oversized = b"x" * (validate.PDFTOTEXT_MAX_BYTES + 1)
        self.install(lambda cmd, kwargs: FakeCompleted(stdout=oversized))
        with self.assertRaises(validate.CitationFailure) as caught:
            validate.run_pdftotext("manual.pdf", 1)
        self.assertIn("cap", str(caught.exception))
        self.assertIn(str(validate.PDFTOTEXT_MAX_BYTES), str(caught.exception))
        # Exactly at the cap is accepted, so the bound is not off by one.
        self.install(lambda cmd, kwargs: FakeCompleted(
            stdout=b"y" * validate.PDFTOTEXT_MAX_BYTES))
        self.assertEqual(len(validate.run_pdftotext("manual.pdf", 1)),
                         validate.PDFTOTEXT_MAX_BYTES)

    def test_missing_binary_is_translated_to_the_install_remedy(self):
        """FileNotFoundError from the real call site becomes the poppler remedy."""
        def absent(cmd, kwargs):
            raise FileNotFoundError(2, "The system cannot find the file specified")
        self.install(absent)
        with self.assertRaises(validate.CitationFailure) as caught:
            validate.run_pdftotext("manual.pdf", 1)
        self.assertIn("poppler-utils", caught.exception.remedy)
        self.assertIn("pdftotext -layout", caught.exception.remedy)

    def test_timeout_expiry_is_translated_not_propagated(self):
        """A TimeoutExpired escaping the verifier would abort the whole run."""
        def slow(cmd, kwargs):
            raise validate.subprocess.TimeoutExpired(cmd, validate.PDFTOTEXT_TIMEOUT)
        self.install(slow)
        with self.assertRaises(validate.CitationFailure) as caught:
            validate.run_pdftotext("manual.pdf", 1)
        self.assertIn(str(validate.PDFTOTEXT_TIMEOUT), str(caught.exception))

    def test_nonzero_exit_reports_the_code_and_bounded_stderr(self):
        """A rejected page surfaces the exit status and a truncated stderr."""
        self.install(lambda cmd, kwargs: FakeCompleted(
            returncode=99, stderr=b"Error: Wrong page range given\n" + b"z" * 4000))
        with self.assertRaises(validate.CitationFailure) as caught:
            validate.run_pdftotext("manual.pdf", 9999)
        message = str(caught.exception)
        self.assertIn("exited 99", message)
        self.assertIn("Wrong page range", message)
        self.assertLess(len(message.encode("utf-8")), 2048,
                        "stderr must be truncated, not echoed whole")

    def test_undecodable_output_is_refused(self):
        """Output that is not UTF-8 cannot be matched, so it fails closed."""
        self.install(lambda cmd, kwargs: FakeCompleted(stdout=b"\xff\xfe\x00bad"))
        with self.assertRaises(validate.CitationFailure) as caught:
            validate.run_pdftotext("manual.pdf", 1)
        self.assertIn("UTF-8", str(caught.exception))

    def test_os_error_is_translated_to_the_install_remedy(self):
        """Any other OSError at the boundary is a refusal, never a crash."""
        def broken(cmd, kwargs):
            raise OSError(13, "Permission denied")
        self.install(broken)
        with self.assertRaises(validate.CitationFailure) as caught:
            validate.run_pdftotext("manual.pdf", 1)
        self.assertIn("could not be executed", str(caught.exception))

    def test_the_production_wrapper_is_what_verify_citation_calls(self):
        """`verify_citation`'s default runner is the real wrapper, not a stub.

        Without this, every other case here could be exercising a boundary the
        validator never reaches.
        """
        import inspect
        signature = inspect.signature(validate.verify_citation)
        self.assertIs(signature.parameters["runner"].default, validate.run_pdftotext)


class TestExternalToolBoundary(CitationCase):
    def test_missing_pdftotext_fails_closed_with_the_install_remedy(self):
        """An absent pdftotext binary FAILS the gate and names how to fix it.

        Injects exactly what production `run_pdftotext` raises on
        FileNotFoundError. A gate that can be bypassed by uninstalling a binary
        is not a gate, so this must never skip or become not-applicable.
        """
        ref = self.pdf_source()

        def absent(_source, _page):
            raise validate.CitationFailure(
                "", "pdftotext is not installed or not on PATH",
                validate.PDFTOTEXT_REMEDY)

        rep = self.verify(
            self.citation(ref, location={"kind": "pdf-page", "page": 3}),
            self.document(ref, fmt="pdf"), runner=absent)
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("poppler-utils", rep.remedies())
        self.assertIn("pdftotext -layout", rep.remedies())

    def test_verifier_timeout_is_unverified_not_skipped(self):
        """A runner that times out yields CITATION_UNVERIFIED, never a pass."""
        ref = self.pdf_source()

        def slow(_source, page):
            raise validate.CitationFailure(
                "", "pdftotext did not finish in %ds" % validate.PDFTOTEXT_TIMEOUT,
                "shrink or replace the source PDF, then rerun page %d" % page)

        rep = self.verify(
            self.citation(ref, location={"kind": "pdf-page", "page": 2}),
            self.document(ref, fmt="pdf"), runner=slow)
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("did not finish", rep.payload())

    def test_invalid_pdf_page_ordinal_is_rejected_before_the_runner(self):
        """A PDF page error: ordinal 0 is refused and the runner is never called."""
        ref = self.pdf_source()
        called = []

        def runner(_source, page):
            called.append(page)
            return ""

        rep = self.verify(
            self.citation(ref, location={"kind": "pdf-page", "page": 0}),
            self.document(ref, fmt="pdf"), runner=runner)
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertEqual(called, [], "the runner must not be invoked for a bad page")
        self.assertIn("not >= 1", rep.payload())

    def test_page_rejected_by_the_tool_reports_the_exact_command(self):
        """A nonzero exit from the tool is surfaced with its remedy, not swallowed."""
        ref = self.pdf_source()

        def rejects(_source, page):
            raise validate.CitationFailure(
                "", "pdftotext exited 99 for page %d" % page,
                "correct the physical page ordinal")

        rep = self.verify(
            self.citation(ref, location={"kind": "pdf-page", "page": 9999}),
            self.document(ref, fmt="pdf"), runner=rejects)
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("exited 99", rep.payload())

    def test_source_format_and_location_variant_must_agree(self):
        """A pdf source cited with text-lines is refused: the variant selects the path."""
        ref = self.pdf_source()
        rep = self.verify(self.citation(ref), self.document(ref, fmt="pdf"))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("location kind", rep.payload())

    def test_source_id_bound_to_no_document_is_refused(self):
        """An unbound source ID names no bytes, so nothing can be derived from it."""
        ref = self.text_source()
        citation = self.citation(ref)
        citation["source_id"] = "doc-404"
        rep = self.verify(citation, self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("doc-404", rep.payload())

    def test_non_utf8_source_bytes_are_refused(self):
        """A utf8-text source that is not valid UTF-8 fails closed."""
        ref = self.write_source("halucinator/docs/fictional/sources/MANUAL.txt",
                                b"\xff\xfe not utf-8 at all\n" * 8)
        rep = self.verify(self.citation(ref), self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])


class TestNormalization(unittest.TestCase):
    """Unicode / NFKC normalization and casefolding, exercised as pure functions."""

    def test_nfkc_casefold_and_soft_hyphen_removal(self):
        """Compatibility forms, case and soft hyphens normalize to one form."""
        # U+FB01 LATIN SMALL LIGATURE FI decomposes to "fi" under NFKC;
        # U+00AD SOFT HYPHEN is deleted; case folds away.
        decorated = "FI\u00adXTURE \uff32\uff25\uff33\uff45\uff54"
        self.assertEqual(validate.normalize_citation_text(decorated), "fixture reset")
        self.assertEqual(validate.normalize_citation_text("Stra\u00dfe"), "strasse")

    def test_line_separators_and_whitespace_runs_collapse(self):
        """CRLF, CR, NEL and paragraph separators all collapse to single spaces."""
        raw = "reset\r\nvalue\rzero\u0085in\u2028every\u2029field   here"
        self.assertEqual(validate.normalize_citation_text(raw),
                         "reset value zero in every field here")

    def test_digit_safe_hyphen_joining_never_mangles_ranges(self):
        """Line-break hyphen joining is digit-safe: FIFO-\\n0 and 0x1-0x3 survive.

        A join between letters is real typesetting. A join touching a digit
        would silently invent a register value, which is precisely the class of
        fabrication this milestone exists to prevent.
        """
        # Letter-letter: joined.
        self.assertEqual(validate.normalize_citation_text("periph-\neral"), "peripheral")
        # Digit on the right: NOT joined, so the tokens stay separate.
        self.assertEqual(validate.normalize_citation_text("fifo-\n0"), "fifo- 0")
        self.assertEqual(validate.citation_tokens(
            validate.normalize_citation_text("fifo-\n0")), ["fifo", "-", "0"])
        # Digit on the left: NOT joined.
        self.assertEqual(validate.normalize_citation_text("3-\nbit"), "3- bit")
        # An inline range is never touched at all.
        self.assertEqual(validate.normalize_citation_text("0x1-0x3"), "0x1-0x3")
        self.assertEqual(validate.citation_tokens("0x1-0x3"), ["0x1", "-", "0x3"])


class TestInterleavingGapBound(unittest.TestCase):
    """The attempt-2 ordered-token match and its declared gap budget."""

    def test_interleaving_within_the_gap_bound_matches(self):
        """Column interleaving up to eight intervening tokens still matches."""
        excerpt = ["reset", "value", "zero"]
        source = ["reset", "unrelated", "value", "unrelated", "zero"]
        self.assertIs(validate.ordered_token_match(excerpt, source), True)

    def test_interleaving_beyond_the_gap_bound_does_not_match(self):
        """Nine intervening tokens exceeds the per-gap bound of eight.

        The excerpt is deliberately long enough that the TOTAL budget
        (min(256, 2 x token count) = 12 here) does not bind first; otherwise
        this would be testing the wrong bound. For a two-token excerpt the
        total budget is 4, which is tighter than the per-gap 8 - the two rules
        are separate and both apply.
        """
        excerpt = ["reset", "value", "zero", "in", "every", "field"]
        self.assertEqual(min(validate.EXCERPT_MAX_TOKENS, 2 * len(excerpt)), 12)
        near = ["reset"] + ["filler"] * 8 + ["value", "zero", "in", "every", "field"]
        self.assertIs(validate.ordered_token_match(excerpt, near), True)
        far = ["reset"] + ["filler"] * 9 + ["value", "zero", "in", "every", "field"]
        self.assertIs(validate.ordered_token_match(excerpt, far), False)

    def test_short_excerpt_is_bound_by_the_total_budget_not_the_per_gap_bound(self):
        """For a two-token excerpt the total budget of 4 binds before the gap of 8."""
        excerpt = ["reset", "value"]
        self.assertEqual(min(validate.EXCERPT_MAX_TOKENS, 2 * len(excerpt)), 4)
        self.assertIs(validate.ordered_token_match(
            excerpt, ["reset"] + ["filler"] * 4 + ["value"]), True)
        self.assertIs(validate.ordered_token_match(
            excerpt, ["reset"] + ["filler"] * 5 + ["value"]), False)

    def test_total_skipped_token_budget_is_enforced(self):
        """Each gap may be legal while the cumulative skip budget is not."""
        excerpt = ["a", "b", "c"]
        budget = min(validate.EXCERPT_MAX_TOKENS, 2 * len(excerpt))
        self.assertEqual(budget, 6)
        # Two gaps of four: every gap legal, total eight, over the budget of six.
        source = ["a"] + ["x"] * 4 + ["b"] + ["x"] * 4 + ["c"]
        self.assertIs(validate.ordered_token_match(excerpt, source), False)
        # Two gaps of three: total six, exactly the budget.
        source = ["a"] + ["x"] * 3 + ["b"] + ["x"] * 3 + ["c"]
        self.assertIs(validate.ordered_token_match(excerpt, source), True)

    def test_order_is_required(self):
        """Out-of-order tokens are not an occurrence, however close together."""
        self.assertIs(validate.ordered_token_match(["b", "a"], ["a", "b"]), False)

    def test_every_viable_start_is_inspected(self):
        """A match after many occurrences of the leading token is still found.

        This is the regression guard for the retired 4096-start cap: an honest
        excerpt beginning with a common token used to be false-rejected once
        that token had occurred often enough, and a gate that false-rejects
        honest evidence is a gate people route around.
        """
        excerpt = ["the", "invented", "value"]
        source = ["the", "other"] * 6000 + ["the", "invented", "value"]
        self.assertGreater(source.count("the"), 4096)
        self.assertIs(validate.ordered_token_match(excerpt, source), True)


class TestBoundedDiagnosticPayload(CitationCase):
    """The failure payload: bounded, truncated, and carrying a nearest candidate."""

    def test_bounded_payload_truncates_and_names_the_closest_candidate(self):
        """The diagnostic stays within its byte bound and marks its truncation.

        The excerpt is long but still inside the 32-4096 code-point constraint,
        so the payload path is actually reached rather than short-circuiting on
        the length check. Each reported slice is clipped independently, and the
        whole payload is bounded before it is emitted.
        """
        ref = self.text_source()
        fabricated = ("The invented SCHEMA_DEMO block asserts an invented sentinel "
                      "value that does not occur at these lines. " + "padding " * 150)
        self.assertLess(len(validate.normalize_citation_text(fabricated)),
                        validate.EXCERPT_MAX_CODEPOINTS)
        rep = self.verify(self.citation(ref, excerpt=fabricated), self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        payload = rep.payload()
        self.assertLessEqual(len(payload.encode("utf-8")),
                             validate.MAX_PAYLOAD_BYTES + 64)
        self.assertIn("\u2026", payload, "truncation must be marked")
        self.assertIn("closest candidate", payload)

    def test_closest_candidate_prefers_highest_score_then_shortest_span(self):
        """Nearest-candidate ordering: score, then shortest span, then earliest."""
        excerpt = ["reset", "value", "zero"]
        source = ["noise", "reset", "value", "zero", "trailing", "trailing"]
        score, window, complete = validate.nearest_candidate(excerpt, source)
        self.assertEqual(score, 1.0)
        self.assertEqual(window, "reset value zero")
        self.assertTrue(complete, "a small region must be scanned exhaustively")

    def test_clip_marks_truncation_without_splitting_utf8(self):
        """The payload clipper never emits a partial code point."""
        clipped = validate._clip("\u00e9" * 100, 9)
        self.assertTrue(clipped.endswith("\u2026"))
        clipped.encode("utf-8")


class TestExcerptConstraints(CitationCase):
    def test_excerpt_shorter_than_the_minimum_is_refused(self):
        """A two-word excerpt could match almost anything, so it is refused."""
        ref = self.text_source()
        rep = self.verify(self.citation(ref, excerpt="reset state"),
                          self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("outside", rep.payload())

    def test_excerpt_without_enough_letters_or_digits_is_refused(self):
        """Punctuation padded to length carries no evidentiary content."""
        ref = self.text_source()
        rep = self.verify(self.citation(ref, excerpt="-" * 40), self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])

    def test_line_range_past_the_end_of_the_source_is_refused(self):
        """A cited range the source does not have is a location error, not a miss."""
        ref = self.text_source()
        rep = self.verify(
            self.citation(ref, location={"kind": "text-lines",
                                         "line_start": 900, "line_end": 901}),
            self.document(ref))
        self.assertEqual(rep.codes(), ["CITATION_UNVERIFIED"])
        self.assertIn("past the", rep.payload())


if __name__ == "__main__":
    unittest.main()
