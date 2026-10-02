"""
The judgement — findings first, then a letter.

The grader reads the facts :mod:`herald.core.parse` gathered and turns them into
plain-English findings a person can act on, then a single A+..F letter. Two
principles shape it, both carried over from the rest of this catalogue:

* **Honesty ceiling.** Herald reads the receiver's authentication *claims*; it
  cannot re-verify a DKIM signature without fetching a DNS key, and it never
  sees the recipient's own filtering. So the top of the scale is reserved and
  annotated, a message whose authentication is simply *unknown* is capped well
  below "looks fine", and the word "safe" never appears. A high grade means
  "every signal Herald can read is consistent", not "this message is genuine".

* **Tells, not brands.** Every penalty is a property of the message itself — a
  mismatch, a failed check, a domain written to deceive — never a comparison
  against a list of who is "really" who.
"""

from __future__ import annotations

from .domains import (
    homoglyph_hits,
    is_punycode,
    registrable_domain,
    same_registrable,
)
from .model import AuthState, Finding, Grade, Message, Severity, utc

# Letters, best to worst, so ceilings can be compared as positions.
_LETTERS = [
    "A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D+", "D", "D-", "F",
]


def _letter_for_score(score: int) -> str:
    bands = [
        (97, "A+"), (93, "A"), (90, "A-"),
        (87, "B+"), (83, "B"), (80, "B-"),
        (77, "C+"), (73, "C"), (70, "C-"),
        (67, "D+"), (63, "D"), (60, "D-"),
    ]
    for floor, letter in bands:
        if score >= floor:
            return letter
    return "F"


def _cap(letter: str, ceiling: str) -> str:
    """Return the worse (lower) of two letters."""
    return letter if _LETTERS.index(letter) >= _LETTERS.index(ceiling) else ceiling


def grade_message(msg: Message) -> Message:
    """Populate ``msg.findings`` and ``msg.grade`` in place, and return it."""
    findings: list[Finding] = []
    score = 100

    def add(sev: Severity, title: str, detail: str, pts: int = 0, cat: str = "general"):
        nonlocal score
        findings.append(Finding(sev, title, detail, pts, cat))
        score -= pts

    from_dom = msg.from_addr.domain if msg.from_addr else ""
    from_reg = registrable_domain(from_dom) if from_dom else ""

    # --- SPF -----------------------------------------------------------------
    spf = msg.auth.spf
    if spf is AuthState.PASS:
        add(Severity.GOOD, "SPF passed",
            f"The receiving server confirmed the sending IP is authorised to "
            f"send for {msg.auth.spf_domain or 'the envelope domain'}.", 0, "spf")
    elif spf is AuthState.FAIL:
        add(Severity.ALERT, "SPF failed",
            "The sending server is not on the envelope domain's list of "
            "authorised senders — a strong forgery tell.", 26, "spf")
    elif spf is AuthState.SOFTFAIL:
        add(Severity.WARNING, "SPF soft-failed",
            "The envelope domain discourages, but does not forbid, this sender. "
            "Often a sign of a spoof the domain owner has not hardened against.",
            15, "spf")
    elif spf in (AuthState.NONE, AuthState.NEUTRAL):
        add(Severity.NOTICE, "SPF gave no verdict",
            "The envelope domain publishes no usable SPF policy, so this check "
            "proves nothing either way.", 8, "spf")
    else:  # ABSENT / error
        add(Severity.NOTICE, "No SPF result recorded",
            "The receiving server did not record an SPF check for this message.",
            8, "spf")

    # --- DKIM ----------------------------------------------------------------
    dkim = msg.auth.dkim
    if dkim is AuthState.PASS:
        add(Severity.GOOD, "DKIM signature verified",
            f"The receiver validated a signature from "
            f"{msg.auth.dkim_domain or 'the signing domain'}. (Herald reads this "
            f"result; it does not re-check the cryptography itself.)", 0, "dkim")
    elif dkim is AuthState.FAIL:
        add(Severity.ALERT, "DKIM signature failed",
            "A DKIM signature was present but did not validate — the message was "
            "altered in transit or forged.", 22, "dkim")
    elif dkim is AuthState.NEUTRAL and msg.auth.dkim_signatures:
        add(Severity.NOTICE, "DKIM present but unverified",
            "The message carries a DKIM signature, but no receiver verdict was "
            "recorded, so Herald cannot say whether it validates.", 8, "dkim")
    else:
        add(Severity.WARNING, "Not DKIM-signed",
            "No DKIM signature was found. Legitimate bulk and transactional mail "
            "is almost always signed; its absence is worth noting.", 10, "dkim")

    # --- DMARC ---------------------------------------------------------------
    dmarc = msg.auth.dmarc
    if dmarc is AuthState.PASS:
        add(Severity.GOOD, "DMARC aligned",
            "SPF or DKIM passed *and* matched the From domain — the alignment "
            "DMARC requires.", 0, "dmarc")
    elif dmarc is AuthState.FAIL:
        add(Severity.ALERT, "DMARC failed",
            "Authentication did not align with the From domain. If that domain "
            "enforces DMARC, a real message would not reach you looking like this.",
            22, "dmarc")
    elif dmarc in (AuthState.NONE, AuthState.NEUTRAL):
        add(Severity.NOTICE, "No DMARC policy",
            "The From domain publishes no DMARC policy, so alignment was not "
            "enforced.", 8, "dmarc")
    else:
        add(Severity.NOTICE, "No DMARC result recorded",
            "The receiving server recorded no DMARC check.", 6, "dmarc")

    # --- address alignment tells --------------------------------------------
    rp = msg.return_path
    if msg.from_addr and rp and rp.domain:
        if not same_registrable(from_dom, rp.domain):
            add(Severity.WARNING, "From and Return-Path disagree",
                f"You see mail from {from_reg or from_dom}, but bounces go to "
                f"{registrable_domain(rp.domain)}. Common for mailing lists and "
                f"some providers — but also the plainest spoofing tell.",
                14, "alignment")
        else:
            add(Severity.GOOD, "Envelope matches the From domain",
                "The bounce address shares the sender's registrable domain.",
                0, "alignment")

    if msg.from_addr and msg.auth.dkim_domain and dkim is AuthState.PASS:
        if not same_registrable(from_dom, msg.auth.dkim_domain):
            add(Severity.NOTICE, "DKIM signs a different domain",
                f"The valid signature belongs to "
                f"{registrable_domain(msg.auth.dkim_domain)}, not "
                f"{from_reg or from_dom}. Legitimate for some senders, but it "
                f"means the From domain itself was not the thing proven.",
                10, "alignment")

    rt = msg.reply_to
    if msg.from_addr and rt and rt.domain and not same_registrable(from_dom, rt.domain):
        add(Severity.NOTICE, "Replies would go elsewhere",
            f"A reply would be sent to {registrable_domain(rt.domain)}, a "
            f"different domain from the sender. A frequent trick for routing "
            f"answers to an attacker.", 8, "alignment")

    # --- display-name deception ---------------------------------------------
    if msg.from_addr and msg.from_addr.display:
        disp = msg.from_addr.display
        if "@" in disp:
            # a whole address hidden in the name, different from the real one
            buried = disp.split()[-1].strip("<>").lower()
            if "@" in buried and buried.split("@")[-1] and not same_registrable(
                buried.split("@")[-1], from_dom
            ):
                add(Severity.ALERT, "The display name hides another address",
                    f"The name shown reads like \"{disp}\", but the message is "
                    f"actually from {msg.from_addr.full}. Your client may show you "
                    f"only the name.", 16, "display")

    # --- lookalike domain structure -----------------------------------------
    if from_dom:
        if is_punycode(from_dom):
            add(Severity.ALERT, "The sender's domain is punycode",
                f"{from_dom} is an internationalised domain shown in ASCII "
                f"disguise — a classic way to mimic a familiar name with "
                f"look-alike letters.", 16, "lookalike")
        for label_hit, reads_as in homoglyph_hits(from_dom):
            add(Severity.WARNING, "Digit-for-letter look-alike in the domain",
                f"The sender's domain contains \"{label_hit}\", which reads as "
                f"\"{reads_as}\" — a word spelled with numbers standing in for "
                f"letters.", 14, "lookalike")

    # --- weak corroborating signals -----------------------------------------
    if msg.message_id_domain and from_reg and not same_registrable(
        msg.message_id_domain, from_dom
    ):
        add(Severity.INFO, "Message-ID from another domain",
            f"The Message-ID was issued by "
            f"{registrable_domain(msg.message_id_domain)}, not the From domain. "
            f"Weak on its own — many legitimate senders relay through a third "
            f"party.", 4, "weak")

    _date_skew(msg, add)

    if not msg.hops:
        add(Severity.INFO, "No itinerary to inspect",
            "Without Received headers Herald cannot show the path or time the "
            "message took; the grade rests only on the headers that remain.",
            0, "path")

    # --- resolve the ceiling -------------------------------------------------
    score = max(0, min(100, score))
    letter = _letter_for_score(score)

    auth_known = any(
        s not in (AuthState.ABSENT,)
        for s in (msg.auth.spf, msg.auth.dkim, msg.auth.dmarc)
    )
    all_pass = (
        msg.auth.spf is AuthState.PASS
        and msg.auth.dkim is AuthState.PASS
        and msg.auth.dmarc is AuthState.PASS
    )

    ceiling_note = (
        "Herald grades the authentication the receiving server reported; it does "
        "not re-verify signatures or see your own spam filtering. A high grade "
        "means every signal it can read is consistent — never that a message is "
        "safe."
    )

    if not auth_known:
        # Nothing to authenticate against: honesty says we simply do not know.
        letter = _cap(letter, "C")
        headline = ("Authentication unknown — treat on its contents, not this "
                    "grade")
    elif all_pass and score >= 97:
        letter = "A+"
        headline = "Every readable signal is consistent"
    else:
        letter = _cap(letter, "A")  # A+ is reserved for a clean full-auth pass
        if score >= 90:
            headline = "Looks consistent, with minor notes"
        elif score >= 75:
            headline = "Some tells worth a second look"
        elif score >= 60:
            headline = "Several spoofing tells present"
        else:
            headline = "Strong signs this message is not what it claims"

    msg.findings = sorted(findings, key=lambda f: -f.severity.rank)
    msg.grade = Grade(letter=letter, score=score, headline=headline,
                      ceiling_note=ceiling_note)
    return msg


def _date_skew(msg: Message, add) -> None:
    """Flag a Date header that sits far from the itinerary's own clock."""
    if not msg.date_header or not msg.hops:
        return
    stamped = [h.timestamp for h in msg.hops if h.timestamp]
    if not stamped:
        return
    origin = min(utc(t) for t in stamped)
    gap = abs((utc(msg.date_header) - origin).total_seconds())
    if gap > 86400:  # more than a day apart
        add(Severity.NOTICE, "The Date header disagrees with the itinerary",
            f"The message is dated roughly {int(gap // 3600)} hours from when the "
            f"first server handled it — a possible sign of a forged or replayed "
            f"header.", 6, "path")


def analyze(source: str) -> Message:
    """Convenience: parse then grade, the whole pipeline in one call."""
    from .parse import parse_email

    return grade_message(parse_email(source))
