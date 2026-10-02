"""End-to-end: parse plus grade, and the honesty ceiling that governs it."""

import os
import re

from herald.core.grade import analyze
from herald.core.model import Severity

SAMPLES = os.path.join(os.path.dirname(__file__), "..", "samples")


def _sample(name: str) -> str:
    with open(os.path.join(SAMPLES, name), encoding="utf-8") as fh:
        return fh.read()


def _titles(msg):
    return {f.title for f in msg.findings}


def test_clean_newsletter_grades_top():
    m = analyze(_sample("clean-newsletter.eml"))
    assert m.grade.letter == "A+"
    assert m.grade.score == 100
    # A+ still carries the honesty caveat.
    assert "never that a message is safe" in m.grade.ceiling_note


def test_mailing_list_is_consistent_with_one_note():
    m = analyze(_sample("mailing-list.eml"))
    assert m.grade.letter in ("A-", "B+", "A")
    assert "Replies would go elsewhere" in _titles(m)


def test_spoofed_invoice_fails_hard():
    m = analyze(_sample("spoofed-invoice.eml"))
    assert m.grade.letter == "F"
    titles = _titles(m)
    assert "SPF failed" in titles
    assert "DMARC failed" in titles
    assert "The display name hides another address" in titles
    assert "From and Return-Path disagree" in titles


def test_spoofed_invoice_catches_homoglyph():
    m = analyze(_sample("spoofed-invoice.eml"))
    assert any("look-alike" in f.title.lower() for f in m.findings)


def test_no_verdict_ever_reads_as_a_clearance():
    """The word itself, not a list of phrases.

    A phrase ban ("this message is safe") only forbids the sentence someone
    thought of. Assert the words outright, across every verdict-bearing string
    -- the headline and every finding title -- on every sample. The ceiling note
    is excluded on purpose: it is the one place the word belongs, because that
    is the sentence refusing it.
    """
    for name in ("clean-newsletter.eml", "mailing-list.eml", "spoofed-invoice.eml"):
        m = analyze(_sample(name))
        for text in [m.grade.headline] + [f.title for f in m.findings]:
            assert not re.search(r"\b(safe|secure|trusted|clean)\b", text, re.I), (
                f"{name}: a verdict reads as a clearance -- {text!r}")


def test_the_ceiling_note_still_refuses_the_word():
    """The claim above is only worth making while the refusal is actually there."""
    m = analyze(_sample("clean-newsletter.eml"))
    assert "never that a message is safe" in m.grade.ceiling_note


def test_unknown_authentication_is_capped():
    # A message with no SPF/DKIM/DMARC anywhere cannot earn a high grade.
    raw = (
        "From: Someone <a@example.com>\n"
        "To: you@example.com\n"
        "Subject: hello\n"
        "Date: Tue, 30 Sep 2026 10:00:00 +0000\n"
        "Message-ID: <1@example.com>\n"
        "\n"
        "body\n"
    )
    m = analyze(raw)
    # C or worse — "authentication unknown".
    assert m.grade.letter in ("C", "C-", "D+", "D", "D-", "F")
    assert "unknown" in m.grade.headline.lower()


def test_findings_sorted_most_severe_first():
    m = analyze(_sample("spoofed-invoice.eml"))
    ranks = [f.severity.rank for f in m.findings]
    assert ranks == sorted(ranks, reverse=True)
    assert m.findings[0].severity in (Severity.ALERT, Severity.WARNING)


def test_internal_hop_flagged():
    m = analyze(_sample("clean-newsletter.eml"))
    assert any(h.is_internal for h in m.hops)
    assert any(not h.is_internal for h in m.hops)


def test_travel_time_computed():
    m = analyze(_sample("clean-newsletter.eml"))
    assert m.travel_time_seconds == 5.0


def test_empty_input_does_not_crash():
    m = analyze("")
    assert m.grade is not None
    assert not m.hops
