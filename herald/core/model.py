"""
The shapes the analysis produces.

Everything the parser learns about a message is poured into these dataclasses,
and everything the interface draws reads from them. Nothing here does any
parsing or scoring — these are the nouns, defined once, so the engine and the
window never disagree about what a "hop" or a "finding" is.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional


class AuthState(Enum):
    """What a mail-authentication check reported.

    This is the *receiving server's* verdict as written into the headers, not
    something Herald re-computed. The names mirror the words that actually
    appear in an ``Authentication-Results`` header.
    """

    PASS = "pass"
    FAIL = "fail"
    SOFTFAIL = "softfail"
    NEUTRAL = "neutral"
    NONE = "none"
    TEMPERROR = "temperror"
    PERMERROR = "permerror"
    ABSENT = "absent"  # the header never mentioned this mechanism at all

    @property
    def is_good(self) -> bool:
        return self is AuthState.PASS

    @property
    def is_bad(self) -> bool:
        return self in (AuthState.FAIL, AuthState.SOFTFAIL, AuthState.PERMERROR)


class Severity(Enum):
    """How much a single finding should worry the reader."""

    GOOD = "good"        # a reassuring signal, not a problem
    INFO = "info"        # worth knowing, not alarming
    NOTICE = "notice"    # a soft tell
    WARNING = "warning"  # a real spoofing tell
    ALERT = "alert"      # a strong spoofing tell

    @property
    def rank(self) -> int:
        return {
            Severity.GOOD: 0,
            Severity.INFO: 1,
            Severity.NOTICE: 2,
            Severity.WARNING: 3,
            Severity.ALERT: 4,
        }[self]


@dataclass(frozen=True)
class Address:
    """One parsed e-mail address and the display name attached to it."""

    display: str
    local: str
    domain: str

    @property
    def full(self) -> str:
        at = f"{self.local}@{self.domain}" if self.domain else self.local
        return at

    @property
    def rendered(self) -> str:
        return f"{self.display} <{self.full}>" if self.display else self.full


@dataclass
class Hop:
    """One ``Received:`` header, read into its parts.

    Mail logs these newest-first, so index 0 is the server that handled the
    message *last* (closest to the recipient). Herald reverses them for display
    so the story reads origin-first, the way the message actually travelled.
    """

    index: int                      # position in the raw header list (0 = topmost)
    from_host: str = ""             # the name the sending side announced
    from_ip: str = ""               # the IP the receiving side actually saw
    by_host: str = ""               # the server that accepted this hop
    protocol: str = ""              # ESMTP, ESMTPS, SMTP, local, ...
    with_tls: bool = False          # did this hop say it used TLS?
    queue_id: str = ""
    for_addr: str = ""
    timestamp: Optional[datetime] = None
    raw: str = ""

    # filled in by the analyser, relative to the previous hop in travel order
    delay_seconds: Optional[float] = None
    is_internal: bool = False       # the IP sits in private/reserved space
    notes: list[str] = field(default_factory=list)


@dataclass
class AuthReport:
    """The authentication picture, as claimed by the receiver."""

    spf: AuthState = AuthState.ABSENT
    dkim: AuthState = AuthState.ABSENT
    dmarc: AuthState = AuthState.ABSENT

    spf_domain: str = ""            # the domain SPF was checked against
    dkim_domain: str = ""           # the d= of the DKIM signature
    dmarc_domain: str = ""
    dkim_signatures: list[str] = field(default_factory=list)  # every d= seen
    authserv: str = ""              # the mail host that performed the checks
    raw_results: list[str] = field(default_factory=list)


@dataclass
class Finding:
    """One observation the grader made, in words a person can act on."""

    severity: Severity
    title: str
    detail: str
    points: int = 0                 # subtracted from the score (0 for GOOD/INFO)
    category: str = "general"


@dataclass
class Grade:
    """The final letter, the number behind it, and why."""

    letter: str
    score: int
    headline: str
    ceiling_note: str               # the honesty caveat — always present


@dataclass
class Message:
    """Everything Herald learned about one e-mail."""

    subject: str = ""
    date_header: Optional[datetime] = None
    message_id: str = ""
    message_id_domain: str = ""

    from_addr: Optional[Address] = None
    reply_to: Optional[Address] = None
    return_path: Optional[Address] = None
    to_addrs: list[Address] = field(default_factory=list)

    hops: list[Hop] = field(default_factory=list)   # travel order (origin first)
    auth: AuthReport = field(default_factory=AuthReport)

    findings: list[Finding] = field(default_factory=list)
    grade: Optional[Grade] = None

    header_count: int = 0
    parse_notes: list[str] = field(default_factory=list)

    @property
    def travel_time_seconds(self) -> Optional[float]:
        stamped = [h.timestamp for h in self.hops if h.timestamp]
        if len(stamped) < 2:
            return None
        return (max(stamped) - min(stamped)).total_seconds()


def utc(dt: datetime) -> datetime:
    """Normalise any datetime to UTC so deltas are honest across zones."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)
