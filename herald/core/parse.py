"""
From raw text to a :class:`Message`.

This is the front door. Hand it the full source of an e-mail — the thing your
client shows under "View source" / "Show original", or a saved ``.eml`` file —
and it hands back a structured picture: who it claims to be from, the itinerary
it took, and what the receiver said about its authentication. It does not grade
anything; that is :mod:`herald.core.grade`'s job, kept separate so the facts and
the judgement never get tangled.
"""

from __future__ import annotations

from email import message_from_string
from email.header import decode_header, make_header
from email.utils import getaddresses, parseaddr

from .auth import collect_auth
from .domains import is_private_ip, registrable_domain
from .model import Address, Message, utc
from .received import parse_received_stack


def _decode(value: str) -> str:
    """Render an RFC 2047 encoded-word header as plain Unicode."""
    if not value:
        return ""
    try:
        return str(make_header(decode_header(value)))
    except Exception:
        return value


def _address(raw: str) -> Address | None:
    """Parse ``Display Name <local@domain>`` into an :class:`Address`."""
    if not raw:
        return None
    display, email_addr = parseaddr(_decode(raw))
    if not email_addr and not display:
        return None
    local, _, domain = email_addr.partition("@")
    return Address(
        display=display.strip(),
        local=local.strip().lower(),
        domain=domain.strip().strip(">").lower(),
    )


def _addresses(raw_values: list[str]) -> list[Address]:
    out: list[Address] = []
    pairs = getaddresses([_decode(v) for v in raw_values])
    for display, email_addr in pairs:
        if not email_addr:
            continue
        local, _, domain = email_addr.partition("@")
        out.append(
            Address(
                display=display.strip(),
                local=local.strip().lower(),
                domain=domain.strip().strip(">").lower(),
            )
        )
    return out


def parse_email(source: str) -> Message:
    """Parse the full source of one e-mail into a :class:`Message`."""
    msg = message_from_string(source or "")
    out = Message()

    out.header_count = len(msg.items())
    out.subject = _decode(msg.get("Subject", ""))
    out.from_addr = _address(msg.get("From", ""))
    out.reply_to = _address(msg.get("Reply-To", ""))
    out.return_path = _address(msg.get("Return-Path", ""))
    out.to_addrs = _addresses(msg.get_all("To", []))

    out.message_id = (msg.get("Message-ID", "") or "").strip()
    if "@" in out.message_id:
        dom = out.message_id.rsplit("@", 1)[1]
        out.message_id_domain = dom.strip().strip("<>").strip().lower()

    date_raw = msg.get("Date", "")
    if date_raw:
        from email.utils import parsedate_to_datetime

        try:
            out.date_header = parsedate_to_datetime(date_raw)
        except (TypeError, ValueError, IndexError):
            out.parse_notes.append("The Date header could not be parsed.")

    # --- itinerary -----------------------------------------------------------
    received_values = msg.get_all("Received", [])
    stack = parse_received_stack(received_values)
    # Reverse to travel order: origin first, recipient last.
    hops = list(reversed(stack))
    for hop in hops:
        if hop.from_ip:
            hop.is_internal = is_private_ip(hop.from_ip)
    _fill_delays(hops)
    out.hops = hops

    # --- authentication ------------------------------------------------------
    out.auth = collect_auth(
        msg.get_all("Authentication-Results", []),
        msg.get_all("Received-SPF", []),
        msg.get_all("DKIM-Signature", []),
    )
    # When the receiver named no domains, borrow the obvious one from the headers.
    if not out.auth.spf_domain and out.return_path and out.return_path.domain:
        out.auth.spf_domain = registrable_domain(out.return_path.domain)
    if not out.auth.dmarc_domain and out.from_addr and out.from_addr.domain:
        out.auth.dmarc_domain = registrable_domain(out.from_addr.domain)

    if not out.hops:
        out.parse_notes.append(
            "No Received headers were found — this may be a draft, a saved copy, "
            "or a message with its itinerary stripped."
        )
    return out


def _fill_delays(hops: list) -> None:
    """Set each hop's delay relative to the previous hop, in travel order."""
    prev = None
    for hop in hops:
        if hop.timestamp and prev and prev.timestamp:
            delta = (utc(hop.timestamp) - utc(prev.timestamp)).total_seconds()
            hop.delay_seconds = delta
        if hop.timestamp:
            prev = hop
