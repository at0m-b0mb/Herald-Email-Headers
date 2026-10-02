"""Reading authentication verdicts out of the headers."""

from herald.core.auth import collect_auth
from herald.core.model import AuthState


def test_full_authentication_results():
    ar = [("mx.recipient.com; spf=pass smtp.mailfrom=example.com; "
           "dkim=pass header.d=example.com header.s=s1; "
           "dmarc=pass header.from=example.com")]
    rep = collect_auth(ar, [], [])
    assert rep.spf is AuthState.PASS
    assert rep.dkim is AuthState.PASS
    assert rep.dmarc is AuthState.PASS
    assert rep.spf_domain == "example.com"
    assert rep.dkim_domain == "example.com"
    assert rep.dmarc_domain == "example.com"
    assert rep.authserv == "mx.recipient.com"


def test_failures_recorded():
    ar = ["mx; spf=fail smtp.mailfrom=bad.ru; dkim=none; dmarc=fail header.from=x.com"]
    rep = collect_auth(ar, [], [])
    assert rep.spf is AuthState.FAIL
    assert rep.dkim is AuthState.NONE
    assert rep.dmarc is AuthState.FAIL


def test_received_spf_fallback():
    rep = collect_auth([], ["pass (example.com: domain of x) smtp.mailfrom=x@example.com"], [])
    assert rep.spf is AuthState.PASS
    assert rep.spf_domain == "example.com"


def test_dkim_signature_presence_without_verdict():
    rep = collect_auth([], [], ["v=1; a=rsa-sha256; d=signer.com; s=k1; b=abc"])
    # Present but no receiver verdict -> neutral, not a claimed pass.
    assert rep.dkim is AuthState.NEUTRAL
    assert "signer.com" in rep.dkim_signatures
    assert rep.dkim_domain == "signer.com"


def test_softfail_mapping():
    rep = collect_auth(["mx; spf=softfail smtp.mailfrom=x.com"], [], [])
    assert rep.spf is AuthState.SOFTFAIL


def test_absent_when_nothing_present():
    rep = collect_auth([], [], [])
    assert rep.spf is AuthState.ABSENT
    assert rep.dkim is AuthState.ABSENT
    assert rep.dmarc is AuthState.ABSENT


def test_strongest_dkim_kept_across_lines():
    ar = [
        "mx; dkim=fail header.d=a.com",
        "mx; dkim=pass header.d=b.com",
    ]
    rep = collect_auth(ar, [], [])
    assert rep.dkim is AuthState.PASS
