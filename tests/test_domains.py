"""Domain reasoning: registrable part, look-alike tells, private space."""

from herald.core.domains import (
    homoglyph_hits,
    is_private_ip,
    is_punycode,
    registrable_domain,
    same_registrable,
    subdomain_depth,
)


def test_registrable_simple():
    assert registrable_domain("mail.example.com") == "example.com"
    assert registrable_domain("example.com") == "example.com"
    assert registrable_domain("a.b.c.example.com") == "example.com"


def test_registrable_multi_suffix():
    assert registrable_domain("mx.corp.example.co.uk") == "example.co.uk"
    assert registrable_domain("example.co.uk") == "example.co.uk"
    assert registrable_domain("shop.example.com.au") == "example.com.au"


def test_registrable_edge_cases():
    assert registrable_domain("localhost") == "localhost"
    assert registrable_domain("203.0.113.5") == "203.0.113.5"
    assert registrable_domain("") == ""


def test_same_registrable():
    assert same_registrable("mail.example.com", "bounce.example.com")
    assert same_registrable("a.example.co.uk", "b.example.co.uk")
    assert not same_registrable("example.com", "example.net")
    assert not same_registrable("example.com", "")


def test_punycode():
    assert is_punycode("xn--80ak6aa92e.com")
    assert is_punycode("secure.xn--pple-43d.com")
    assert not is_punycode("apple.com")


def test_homoglyph_digits():
    assert homoglyph_hits("paypa1.com")  # 1 -> l
    assert homoglyph_hits("g00gle.net")  # 0 -> o
    assert homoglyph_hits("paypa1-billing.com")  # hyphenated still a tell


def test_homoglyph_false_positives():
    # Pure words, pure numbers, and mixed year/model labels must not trip it.
    assert not homoglyph_hits("example.com")
    assert not homoglyph_hits("web2025.com")   # a digit survives the swap
    assert not homoglyph_hits("route66.net")   # 6 has no letter it imitates
    assert not homoglyph_hits("203.0.113.5")   # an IP, not a name


def test_private_ip():
    for ip in ("10.0.0.1", "192.168.1.1", "172.16.5.9", "127.0.0.1",
               "169.254.1.1", "100.64.0.1"):
        assert is_private_ip(ip), ip
    for ip in ("203.0.113.5", "8.8.8.8", "198.51.100.24"):
        assert not is_private_ip(ip), ip


def test_private_ipv6():
    assert is_private_ip("::1")
    assert is_private_ip("fd00::1")
    assert not is_private_ip("2001:db8::1")


def test_subdomain_depth():
    assert subdomain_depth("example.com") == 0
    assert subdomain_depth("mail.example.com") == 1
    assert subdomain_depth("a.b.example.com") == 2
    assert subdomain_depth("a.b.example.co.uk") == 2
