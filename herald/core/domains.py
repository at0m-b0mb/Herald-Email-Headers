"""
Domain reasoning — the registrable part, and the tells a lookalike leaves.

People read the wrong part of a hostname. They see ``secure-paypal`` and stop,
when the only part that is guaranteed theirs is the registrable domain at the
end. So the first job here is to pull the registrable domain out of any host,
and the second is to notice the structural tricks a spoofed domain uses to look
like one it is not.

Herald never matches against a list of "real" brands — a blocklist is a losing
game and it teaches nothing. It looks for *structure* instead: a domain written
in punycode, a label built from digit-for-letter swaps, an address buried under
a pile of subdomains. Those are properties of the string, true regardless of
who is being impersonated.
"""

from __future__ import annotations

# A compact public-suffix subset. Not the full Mozilla PSL — just the
# multi-label suffixes common enough that treating them as a single TLD matters
# for "same registrable domain?" questions. Everything else falls back to the
# last two labels, which is correct for the ordinary ``example.com`` case.
_MULTI_SUFFIXES = {
    "co.uk", "org.uk", "me.uk", "gov.uk", "ac.uk", "net.uk", "sch.uk",
    "com.au", "net.au", "org.au", "edu.au", "gov.au", "id.au",
    "co.nz", "org.nz", "net.nz", "govt.nz",
    "co.in", "net.in", "org.in", "gov.in", "ac.in", "edu.in",
    "co.jp", "or.jp", "ne.jp", "go.jp", "ac.jp",
    "com.br", "net.br", "org.br", "gov.br",
    "com.cn", "net.cn", "org.cn", "gov.cn", "edu.cn",
    "co.za", "org.za", "net.za", "gov.za",
    "com.sg", "edu.sg", "gov.sg",
    "com.hk", "org.hk", "gov.hk",
    "com.mx", "gob.mx",
    "com.tr", "gov.tr", "edu.tr",
    "co.kr", "or.kr", "go.kr",
    "com.tw", "org.tw", "gov.tw",
    "co.il", "org.il", "gov.il",
}

# Letters that a nearby digit or symbol can stand in for in a cheap lookalike.
_HOMOGLYPH_DIGITS = {
    "0": "o", "1": "l", "3": "e", "4": "a", "5": "s", "7": "t", "8": "b",
}


def normalise_host(host: str) -> str:
    """Strip brackets, trailing dots and case so hosts compare cleanly."""
    h = (host or "").strip().strip(".").lower()
    if h.startswith("[") and h.endswith("]"):
        h = h[1:-1]
    return h


def registrable_domain(host: str) -> str:
    """The part a person actually owns: the label plus its public suffix.

    ``mx.corp.example.co.uk`` -> ``example.co.uk``;
    ``mail.example.com``      -> ``example.com``.
    Hosts that are bare IPs or have no dot are returned unchanged.
    """
    h = normalise_host(host)
    if not h or _looks_like_ip(h):
        return h
    labels = h.split(".")
    if len(labels) < 2:
        return h
    last_two = ".".join(labels[-2:])
    if last_two in _MULTI_SUFFIXES and len(labels) >= 3:
        return ".".join(labels[-3:])
    return last_two


def same_registrable(a: str, b: str) -> bool:
    """Do two hosts share an owner — i.e. the same registrable domain?"""
    ra, rb = registrable_domain(a), registrable_domain(b)
    return bool(ra) and ra == rb


def _looks_like_ip(h: str) -> bool:
    parts = h.split(".")
    if len(parts) == 4 and all(p.isdigit() and 0 <= int(p) <= 255 for p in parts):
        return True
    return ":" in h  # a bare IPv6 literal


def subdomain_depth(host: str) -> int:
    """How many labels sit in front of the registrable domain."""
    h = normalise_host(host)
    reg = registrable_domain(h)
    if not reg or h == reg:
        return 0
    prefix = h[: -(len(reg) + 1)] if h.endswith(reg) else ""
    return prefix.count(".") + 1 if prefix else 0


def is_punycode(host: str) -> bool:
    """Any label encoded as punycode (``xn--``) — a non-ASCII domain in disguise."""
    return any(label.startswith("xn--") for label in normalise_host(host).split("."))


def homoglyph_hits(host: str) -> list[tuple[str, str]]:
    """Registrable-domain labels that mix letters with look-alike digits.

    ``paypa1.com`` or ``g00gle.net`` — a label that would be a plain word if you
    read each digit as the letter it imitates. Pure-numeric labels (an IP octet,
    a year) are ignored; the tell is letters *and* stand-in digits together.

    Returns ``(label, reads_as)`` pairs so the caller can phrase the warning.
    """
    reg = registrable_domain(host)
    if not reg or _looks_like_ip(reg):
        return []
    hits: list[tuple[str, str]] = []
    for label in reg.split("."):
        if label in _MULTI_SUFFIXES or (len(label) <= 3 and label.isalpha()):
            continue
        has_alpha = any(c.isalpha() for c in label)
        swap_digits = [c for c in label if c in _HOMOGLYPH_DIGITS]
        if has_alpha and swap_digits:
            reads_as = "".join(_HOMOGLYPH_DIGITS.get(c, c) for c in label)
            # A tell only if swapping leaves a word — no stray digits remain, so
            # a year or a model number ("web2025", "route66") never trips it,
            # while hyphenated labels ("paypa1-billing") still do.
            no_digits_left = not any(c.isdigit() for c in reads_as)
            if reads_as != label and no_digits_left and any(c.isalpha() for c in reads_as):
                hits.append((label, reads_as))
    return hits


def is_private_ip(ip: str) -> bool:
    """True for RFC1918 / loopback / link-local / reserved space.

    A hop from one of these is an *internal* handoff inside an organisation, not
    a jump across the public internet — worth showing differently, and never a
    spoofing tell by itself.
    """
    ip = normalise_host(ip)
    if ":" in ip:  # IPv6
        return (
            ip.startswith("::1")
            or ip.startswith("fc")
            or ip.startswith("fd")
            or ip.startswith("fe80")
        )
    parts = ip.split(".")
    if len(parts) != 4 or not all(p.isdigit() for p in parts):
        return False
    a, b = int(parts[0]), int(parts[1])
    if a == 10 or a == 127:
        return True
    if a == 192 and b == 168:
        return True
    if a == 172 and 16 <= b <= 31:
        return True
    if a == 169 and b == 254:  # link-local
        return True
    if a == 100 and 64 <= b <= 127:  # carrier-grade NAT
        return True
    return False
