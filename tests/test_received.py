"""Parsing the Received itinerary."""

from herald.core.received import parse_received, parse_received_stack


def test_full_header():
    v = ("from mail.example.com (mail.example.com [203.0.113.5]) "
         "by mx.recipient.com (Postfix) with ESMTPS id 4abc123 "
         "for <you@recipient.com>; Tue, 30 Sep 2026 10:15:23 -0400 (EDT)")
    hop = parse_received(v, 0)
    assert hop.from_host == "mail.example.com"
    assert hop.from_ip == "203.0.113.5"
    assert hop.by_host == "mx.recipient.com"
    assert hop.protocol == "ESMTPS"
    assert hop.queue_id == "4abc123"
    assert hop.for_addr == "you@recipient.com"
    assert hop.with_tls is True
    assert hop.timestamp is not None
    assert hop.timestamp.year == 2026


def test_minimal_header():
    hop = parse_received("by internal.host with local id 9", 0)
    assert hop.by_host == "internal.host"
    assert hop.from_host == ""
    assert hop.from_ip == ""
    assert hop.timestamp is None


def test_ipv6_literal():
    v = ("from x (x [IPv6:2001:db8::5]) by y with ESMTP id 1; "
         "Tue, 30 Sep 2026 10:00:00 +0000")
    hop = parse_received(v, 0)
    assert hop.from_ip == "2001:db8::5"


def test_semicolon_inside_comment_not_mistaken_for_date():
    v = ("from a (a [1.2.3.4]) by b with ESMTP id 1 (note; still a note); "
         "Tue, 30 Sep 2026 10:00:00 +0000")
    hop = parse_received(v, 0)
    assert hop.timestamp is not None
    assert hop.timestamp.hour == 10


def test_folded_whitespace_collapsed():
    v = "from   a\n\t(a [1.2.3.4])\n  by b with ESMTP id 1"
    hop = parse_received(v, 0)
    assert hop.from_host == "a"
    assert hop.from_ip == "1.2.3.4"


def test_stack_preserves_order():
    hops = parse_received_stack(["by last", "by middle", "by first"])
    assert [h.index for h in hops] == [0, 1, 2]
    assert hops[0].by_host == "last"


def test_unparseable_date_is_none_not_crash():
    hop = parse_received("from a by b; not a real date at all", 0)
    assert hop.timestamp is None
