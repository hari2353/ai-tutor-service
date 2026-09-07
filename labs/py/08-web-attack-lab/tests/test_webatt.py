"""Lab 08 tests: XSS escaped/live, CSRF session-bound, SSRF blocked everywhere."""
import pytest

PAYLOAD = "<script>alert(1)</script>"


# ------------------------------------------------------------------ XSS
def test_xss_safe_mode_escapes_the_payload(R):
    eng = R.TemplateEngine(autoescape=True)
    out = eng.render("<p>Hello {name}</p>", {"name": PAYLOAD})
    assert "<script>" not in out
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in out


def test_xss_vulnerable_mode_is_live_script(R):
    """The vulnerability, stated as a fact: raw interpolation emits a live tag."""
    eng = R.TemplateEngine(autoescape=False)
    out = eng.render("<p>Hello {name}</p>", {"name": PAYLOAD})
    assert "<script>alert(1)</script>" in out


def test_xss_attributes_escaped_too(R):
    """quote=True escaping — the attribute-injection variant (onerror=...)."""
    eng = R.TemplateEngine(autoescape=True)
    out = eng.render('<img src="{url}">', {"url": 'x" onerror="alert(1)'})
    assert '" onerror="' not in out


def test_xss_missing_key_fails_closed(R):
    eng = R.TemplateEngine(autoescape=True)
    with pytest.raises(KeyError):
        eng.render("Hi {name}", {})


# ------------------------------------------------------------------ CSRF
def test_csrf_valid_token_accepted(R):
    c = R.FakeClock()
    h = R.CsrfProtectingFormHandler(clock=c)
    tok = h.issue_token("sess-1")
    assert h.submit("sess-1", {"csrf_token": tok, "action": "transfer"}) == "accepted"


def test_csrf_cross_site_post_without_token_rejected(R):
    """THE attack: the victim's browser posts to /transfer while logged in.
    The attacker's form has no token (they can't read the page's DOM)."""
    c = R.FakeClock()
    h = R.CsrfProtectingFormHandler(clock=c)
    h.issue_token("sess-1")
    with pytest.raises(PermissionError):
        h.submit("sess-1", {"action": "transfer", "to": "attacker"})


def test_csrf_token_from_other_session_rejected(R):
    """Session-bound: a leaked token from ANOTHER session must not work —
    otherwise the attacker logs in themselves and harvests a valid token."""
    c = R.FakeClock()
    h = R.CsrfProtectingFormHandler(clock=c)
    attacker_tok = h.issue_token("attacker-sess")
    h.issue_token("victim-sess")
    with pytest.raises(PermissionError):
        h.submit("victim-sess", {"csrf_token": attacker_tok, "action": "transfer"})


def test_csrf_token_expires_via_clock(R):
    c = R.FakeClock()
    h = R.CsrfProtectingFormHandler(clock=c, token_ttl=600.0)
    tok = h.issue_token("sess-1")
    c.advance(599.0)
    assert h.submit("sess-1", {"csrf_token": tok}) == "accepted"
    c.advance(2.0)
    with pytest.raises(PermissionError):
        h.submit("sess-1", {"csrf_token": tok})


def test_csrf_token_is_unguessable_and_rotates(R):
    c = R.FakeClock()
    h = R.CsrfProtectingFormHandler(clock=c)
    t1 = h.issue_token("sess-1")
    t2 = h.issue_token("sess-1")
    assert t1 != t2 and len(t1) >= 32


# ------------------------------------------------------------------ SSRF: cidr math
def test_cidr_membership(R):
    assert R.ip_in_cidr("10.3.4.5", "10.0.0.0/8")
    assert R.ip_in_cidr("10.255.255.255", "10.0.0.0/8")
    assert not R.ip_in_cidr("11.0.0.1", "10.0.0.0/8")
    assert R.ip_in_cidr("127.0.0.1", "127.0.0.0/8")
    assert R.ip_in_cidr("169.254.169.254", "169.254.0.0/16")
    assert not R.ip_in_cidr("169.255.0.1", "169.254.0.0/16")
    assert R.ip_in_cidr("172.31.9.9", "172.16.0.0/12")
    assert not R.ip_in_cidr("172.32.0.1", "172.16.0.0/12")
    assert R.ip_in_cidr("192.168.1.1", "192.168.0.0/16")
    assert R.ip_in_cidr("8.8.8.8", "0.0.0.0/0")


# ------------------------------------------------------------------ SSRF: fetcher
def test_ssrf_metadata_endpoint_blocked(R, internet):
    fetcher, _, _ = internet
    with pytest.raises(R.FetchDenied) as e:
        fetcher.get("https://metadata.google.internal/latest/meta-data/")
    assert "metadata" in e.value.why or "private" in e.value.why


def test_ssrf_aws_raw_ip_blocked(R, internet):
    """The endpoint doesn't even need DNS: raw link-local IP is refused."""
    fetcher, _, _ = internet
    with pytest.raises(R.FetchDenied):
        fetcher.get("http://169.254.169.254/latest/meta-data/")


def test_ssrf_localhost_blocked(R, internet):
    fetcher, _, _ = internet
    with pytest.raises(R.FetchDenied):
        fetcher.get("http://127.0.0.1:8080/")
    with pytest.raises(R.FetchDenied):
        fetcher.get("http://localhost:8080/")


def test_ssrf_dns_name_resolving_to_private_blocked(R, internet):
    """internal.corp is a perfectly public-looking name — the resolver says no."""
    fetcher, _, _ = internet
    with pytest.raises(R.FetchDenied):
        fetcher.get("https://internal.corp/admin")


def test_ssrf_non_http_scheme_blocked(R, internet):
    fetcher, _, _ = internet
    for scheme_url in ("file:///etc/passwd", "gopher://x/y", "ftp://example.com/f"):
        with pytest.raises(R.FetchDenied):
            fetcher.get(scheme_url)


def test_ssrf_public_fetch_allowed(R, internet):
    fetcher, _, _ = internet
    status, body = fetcher.get("https://example.com/")
    assert status == 200 and "hello" in body


def test_ssrf_redirect_to_private_refused(R, internet):
    """THE redirect trap: a public URL 302s to an internal target. Each hop must
    be re-checked — the naive 'validate once, then follow' fetcher is bypassed."""
    fetcher, _, _ = internet
    with pytest.raises(R.FetchDenied):
        fetcher.get("https://example.com/redirect")


def test_ssrf_redirect_to_public_ok(R, internet):
    fetcher, _, _ = internet
    status, body = fetcher.get("https://redirect.example.com/")
    assert status == 200 and "hello" in body


def test_ssrf_dns_rebinding_alias_blocked(R, internet):
    """rebind.example.com resolves to 127.0.0.1 — same rule, nastier name."""
    fetcher, _, _ = internet
    with pytest.raises(R.FetchDenied):
        fetcher.get("https://rebind.example.com/")
