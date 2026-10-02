"""
Reading the authentication verdicts — and being honest about whose they are.

SPF, DKIM and DMARC are the three checks that decide whether a message really
came from where it claims. Crucially, Herald does **not** run them. It reads the
verdict the *receiving* mail server already wrote into the headers
(``Authentication-Results``, ``Received-SPF``, ``DKIM-Signature``). So a "pass"
here means "the server that accepted this message said it passed" — not "Herald
re-validated the cryptography." That distinction is the whole honesty line of
the tool, and the grader never forgets it.
"""

from __future__ import annotations

import re

from .model import AuthReport, AuthState

_STATE_WORDS = {
    "pass": AuthState.PASS,
    "fail": AuthState.FAIL,
    "softfail": AuthState.SOFTFAIL,
    "neutral": AuthState.NEUTRAL,
    "none": AuthState.NONE,
    "temperror": AuthState.TEMPERROR,
    "permerror": AuthState.PERMERROR,
    "hardfail": AuthState.FAIL,
    "error": AuthState.TEMPERROR,
}

_RE_MECH = re.compile(
    r"\b(spf|dkim|dmarc)\s*=\s*([a-zA-Z]+)", re.IGNORECASE
)
_RE_MAILFROM = re.compile(r"smtp\.mailfrom\s*=\s*([^\s;]+)", re.IGNORECASE)
_RE_HEADER_D = re.compile(r"header\.d\s*=\s*([^\s;]+)", re.IGNORECASE)
_RE_HEADER_FROM = re.compile(r"header\.from\s*=\s*([^\s;]+)", re.IGNORECASE)
_RE_DKIM_D = re.compile(r"\bd\s*=\s*([^\s;]+)", re.IGNORECASE)


def _state(word: str) -> AuthState:
    return _STATE_WORDS.get(word.strip().lower(), AuthState.NEUTRAL)


def _domain_of(value: str) -> str:
    value = value.strip().strip(">").strip("<").lower()
    if "@" in value:
        value = value.split("@", 1)[1]
    return value.strip().strip(".")


def collect_auth(
    auth_results: list[str],
    received_spf: list[str],
    dkim_signatures: list[str],
) -> AuthReport:
    """Fold every authentication-related header into one :class:`AuthReport`."""
    report = AuthReport()

    # --- Authentication-Results: the receiver's own summary line(s) ----------
    for line in auth_results:
        flat = " ".join(line.split())
        report.raw_results.append(flat)
        if not report.authserv:
            head = flat.split(";", 1)[0].strip()
            # the first token is the authenticating host, sometimes "host 1"
            report.authserv = head.split()[0] if head else ""

        for mech, word in _RE_MECH.findall(flat):
            mech = mech.lower()
            state = _state(word)
            if mech == "spf" and report.spf is AuthState.ABSENT:
                report.spf = state
            elif mech == "dkim":
                # keep the strongest DKIM result if several are listed
                if report.dkim is AuthState.ABSENT or (
                    state.is_good and not report.dkim.is_good
                ):
                    report.dkim = state
            elif mech == "dmarc" and report.dmarc is AuthState.ABSENT:
                report.dmarc = state

        m_mf = _RE_MAILFROM.search(flat)
        if m_mf and not report.spf_domain:
            report.spf_domain = _domain_of(m_mf.group(1))
        m_hd = _RE_HEADER_D.search(flat)
        if m_hd and not report.dkim_domain:
            report.dkim_domain = _domain_of(m_hd.group(1))
        m_hf = _RE_HEADER_FROM.search(flat)
        if m_hf and not report.dmarc_domain:
            report.dmarc_domain = _domain_of(m_hf.group(1))

    # --- Received-SPF: a fallback when there is no summary line --------------
    for line in received_spf:
        flat = " ".join(line.split())
        first = flat.split()[0] if flat.split() else ""
        state = _state(first)
        if report.spf is AuthState.ABSENT:
            report.spf = state
        if not report.spf_domain:
            m = _RE_MAILFROM.search(flat) or re.search(
                r"envelope-from\s*=?\s*([^\s;]+)", flat, re.IGNORECASE
            )
            if m:
                report.spf_domain = _domain_of(m.group(1))

    # --- DKIM-Signature: the signatures that are actually present ------------
    for sig in dkim_signatures:
        flat = " ".join(sig.split())
        m = _RE_DKIM_D.search(flat)
        if m:
            dom = _domain_of(m.group(1))
            if dom and dom not in report.dkim_signatures:
                report.dkim_signatures.append(dom)
    # A signature exists but no summary mentioned DKIM: record its presence
    # without claiming a verdict we were never given.
    if report.dkim is AuthState.ABSENT and report.dkim_signatures:
        report.dkim = AuthState.NEUTRAL
        if not report.dkim_domain:
            report.dkim_domain = report.dkim_signatures[0]

    return report
