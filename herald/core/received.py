"""
Reading a ``Received:`` header.

Every server that touches a message stamps one of these on top, so the stack of
them is the message's itinerary written in reverse — the topmost was added last,
by the server nearest the recipient. Each one is a loose, decades-old grammar:

    Received: from HELO (reverse-dns [1.2.3.4])
        by mx.example.com (Postfix) with ESMTPS id 4abc
        for <you@example.com>; Tue, 30 Sep 2026 10:15:23 -0400 (EDT)

The clauses are optional and the whitespace is whatever the sending MTA felt
like, so this parser is deliberately forgiving: it pulls out whatever it
recognises and leaves the rest in ``raw`` rather than refusing a messy header.
Nothing here judges a hop — it only reports what the hop says about itself.
"""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime

from .model import Hop

_RE_FROM = re.compile(r"\bfrom\s+(\S+)", re.IGNORECASE)
_RE_BY = re.compile(r"\bby\s+(\S+)", re.IGNORECASE)
_RE_WITH = re.compile(r"\bwith\s+(\S+)", re.IGNORECASE)
_RE_ID = re.compile(r"\bid\s+(\S+)", re.IGNORECASE)
_RE_FOR = re.compile(r"\bfor\s+<?([^>\s;]+@[^>\s;]+)>?", re.IGNORECASE)
_RE_IP = re.compile(r"\[(?:IPv6:)?([0-9a-fA-F:.]+)\]")
_RE_TLS = re.compile(r"\b(TLS|SSL|cipher|ESMTPS|ESMTPSA)\b", re.IGNORECASE)


def _clean_host(token: str) -> str:
    """Trim the punctuation MTAs leave hanging off a hostname token."""
    return (token or "").strip().strip(".,;()").lower()


def _split_meta(value: str) -> tuple[str, str]:
    """Separate the clauses from the trailing ``; date`` stamp.

    The date is whatever follows the last top-level semicolon. We ignore
    semicolons inside parentheses so a comment like ``(no, really; honest)``
    cannot be mistaken for the date separator.
    """
    depth = 0
    cut = -1
    for i, ch in enumerate(value):
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth = max(0, depth - 1)
        elif ch == ";" and depth == 0:
            cut = i
    if cut == -1:
        return value.strip(), ""
    return value[:cut].strip(), value[cut + 1:].strip()


def _parse_date(text: str) -> datetime | None:
    if not text:
        return None
    # Drop a trailing timezone-name comment such as "(EDT)" that parsedate dislikes.
    text = re.sub(r"\s*\([^)]*\)\s*$", "", text).strip()
    try:
        dt = parsedate_to_datetime(text)
    except (TypeError, ValueError, IndexError):
        return None
    return dt


def parse_received(value: str, index: int) -> Hop:
    """Turn one ``Received`` header body into a :class:`Hop`."""
    value = " ".join(value.split())  # unfold and collapse whitespace
    clauses, date_text = _split_meta(value)

    hop = Hop(index=index, raw=value)

    m_from = _RE_FROM.search(clauses)
    if m_from:
        hop.from_host = _clean_host(m_from.group(1))

    m_by = _RE_BY.search(clauses)
    if m_by:
        hop.by_host = _clean_host(m_by.group(1))

    m_with = _RE_WITH.search(clauses)
    if m_with:
        hop.protocol = m_with.group(1).strip().upper()

    m_id = _RE_ID.search(clauses)
    if m_id:
        hop.queue_id = m_id.group(1).strip()

    m_for = _RE_FOR.search(clauses)
    if m_for:
        hop.for_addr = m_for.group(1).strip().lower()

    # The IP the receiver genuinely observed lives in the first [ ... ] group,
    # which is more trustworthy than the HELO name the sender chose for itself.
    m_ip = _RE_IP.search(clauses)
    if m_ip:
        hop.from_ip = m_ip.group(1).strip().lower()

    hop.with_tls = bool(_RE_TLS.search(clauses))
    hop.timestamp = _parse_date(date_text)
    return hop


def parse_received_stack(values: list[str]) -> list[Hop]:
    """Parse every ``Received`` header, preserving top-of-stack ordering.

    Index 0 is the header that was on top of the message — the last hop. Callers
    that want travel order should reverse the returned list.
    """
    return [parse_received(v, i) for i, v in enumerate(values)]
