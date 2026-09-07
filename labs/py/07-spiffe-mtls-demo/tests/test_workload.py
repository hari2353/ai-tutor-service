"""Lab 07 tests. Pure logic — no network, no TLS, no sleeps."""
import pytest


# ------------------------------------------------------------------ parse
def test_parse_valid_id(W):
    sid = W.SpiffeID.parse("spiffe://example.org/backend/payments")
    assert sid.trust_domain == "example.org"
    assert sid.path == "/backend/payments"


def test_parse_root_id_has_empty_path(W):
    sid = W.SpiffeID.parse("spiffe://example.org")
    assert sid.trust_domain == "example.org"
    assert sid.path == ""


@pytest.mark.parametrize("bad", [
    "https://example.org/backend",        # wrong scheme
    "example.org/backend",                # no scheme at all
    "spiffe:///backend/payments",         # empty trust domain
    "spiffe://",                          # nothing after the scheme
])
def test_parse_rejects_malformed_ids(W, bad):
    with pytest.raises(ValueError):
        W.SpiffeID.parse(bad)


def test_id_equality_is_on_full_string(W):
    a = W.SpiffeID.parse("spiffe://example.org/backend/payments")
    b = W.SpiffeID.parse("spiffe://example.org/backend/payments")
    c = W.SpiffeID.parse("spiffe://example.org/backend/payments-retry")
    d = W.SpiffeID.parse("spiffe://other.org/backend/payments")
    assert a == b
    assert not (a != b)
    assert a != c
    assert a != d


# ------------------------------------------------------------------ trust bundles
def test_validate_is_local_only_federation_never_leaks(W):
    """A federated domain is trusted for handshakes (trusts) but validate()
    still says False — it answers 'is this id OURS', not 'do we trust it'."""
    bundle = W.TrustBundle("example.org", federates_with={"partner.io"})
    mine = W.SpiffeID.parse("spiffe://example.org/backend/payments")
    foreign = W.SpiffeID.parse("spiffe://partner.io/svc/reporting")
    stranger = W.SpiffeID.parse("spiffe://evil.dev/svc/steal")

    assert bundle.validate(mine) is True
    assert bundle.validate(foreign) is False          # local check, not trust
    assert bundle.trusts(mine) is True
    assert bundle.trusts(foreign) is True             # federation counts here
    assert bundle.trusts(stranger) is False           # unlisted -> denied


def test_foreign_domain_denied_by_default(W):
    """The default bundle federates with NOTHING. Zero-trust until listed."""
    bundle = W.TrustBundle("example.org")
    foreign = W.SpiffeID.parse("spiffe://partner.io/svc/reporting")
    assert bundle.trusts(foreign) is False


# ------------------------------------------------------------------ authorization
def test_authorize_same_domain_matching_prefixes(W):
    policy = W.AuthorizationPolicy("example.org", "/backend/",
                                  ["/api/payments", "/api/invoices"])
    wl = W.Workload(W.SpiffeID.parse("spiffe://example.org/backend/payments"),
                    "payments")
    assert policy.authorize(wl, "/api/payments/charge") is True


def test_authorize_denies_wrong_trust_domain(W):
    """A perfectly-shaped id from another domain is still nobody here."""
    policy = W.AuthorizationPolicy("example.org", "/backend/",
                                  ["/api/payments"])
    wl = W.Workload(W.SpiffeID.parse("spiffe://other.org/backend/payments"),
                    "imposter")
    assert policy.authorize(wl, "/api/payments/charge") is False


def test_authorize_enforces_both_prefix_rules(W):
    policy = W.AuthorizationPolicy("example.org", "/backend/",
                                  ["/api/payments", "/api/invoices"])
    payments = W.Workload(
        W.SpiffeID.parse("spiffe://example.org/backend/payments"), "payments")
    frontend = W.Workload(
        W.SpiffeID.parse("spiffe://example.org/frontend/web"), "web")

    assert policy.authorize(payments, "/api/catalog/browse") is False  # resource
    assert policy.authorize(frontend, "/api/payments/charge") is False  # source
    assert policy.authorize(frontend, "/api/catalog/browse") is False  # both


def test_authorize_cross_allows_federated_only_when_listed_and_owned(W):
    local_bundle = W.TrustBundle("example.org")
    partner_bundle = W.TrustBundle("partner.io")
    policy = W.AuthorizationPolicy("example.org", "/backend/", ["/api/payments"])

    foreign = W.Workload(
        W.SpiffeID.parse("spiffe://partner.io/backend/reporting"), "reporting")

    # not listed yet -> denied
    assert policy.authorize_cross(foreign, "/api/payments/summary",
                                  local_bundle, partner_bundle) is False

    # listed AND the partner bundle actually owns the id -> allowed
    local_bundle.federates_with.add("partner.io")
    assert policy.authorize_cross(foreign, "/api/payments/summary",
                                  local_bundle, partner_bundle) is True

    # federation grants trust, not blanket access: prefix still applies
    assert policy.authorize_cross(foreign, "/api/admin/purge",
                                  local_bundle, partner_bundle) is False


def test_authorize_cross_local_workload_uses_local_bundle(W):
    local_bundle = W.TrustBundle("example.org")
    policy = W.AuthorizationPolicy("example.org", "/backend/", ["/api/payments"])
    local = W.Workload(
        W.SpiffeID.parse("spiffe://example.org/backend/payments"), "payments")
    assert policy.authorize_cross(local, "/api/payments/charge",
                                  local_bundle, W.TrustBundle("partner.io"))


# ------------------------------------------------------------------ mTLS handshake
def test_handshake_succeeds_within_one_domain(W):
    bundle = W.TrustBundle("example.org")
    client = W.Workload(W.SpiffeID.parse("spiffe://example.org/frontend/web"),
                        "web")
    server = W.Workload(
        W.SpiffeID.parse("spiffe://example.org/backend/payments"), "payments")
    r = W.handshake(client, server, bundle, bundle)
    assert r["established"] is True
    assert r["client_saw"] == "spiffe://example.org/backend/payments"
    assert r["server_saw"] == "spiffe://example.org/frontend/web"


def test_handshake_server_rejects_unknown_domain_client(W):
    """The client trusts the server, but the server has never heard of the
    client's domain — one failed direction kills the whole handshake."""
    corp = W.TrustBundle("corp.internal")
    outsider = W.Workload(
        W.SpiffeID.parse("spiffe://random.net/scraper/crawler"), "crawler")
    server = W.Workload(
        W.SpiffeID.parse("spiffe://corp.internal/backend/payments"), "payments")
    r = W.handshake(outsider, server, corp, corp)
    assert r["established"] is False
    assert "server" in r["reason"]


def test_handshake_accepts_federated_client(W):
    local = W.TrustBundle("corp.internal", federates_with={"partner.io"})
    partner = W.TrustBundle("partner.io", federates_with={"corp.internal"})
    client = W.Workload(
        W.SpiffeID.parse("spiffe://partner.io/backend/reporting"), "reporting")
    server = W.Workload(
        W.SpiffeID.parse("spiffe://corp.internal/api/payments"), "payments")
    r = W.handshake(client, server, partner, local)
    assert r["established"] is True
    assert r["client_saw"] == "spiffe://corp.internal/api/payments"
    assert r["server_saw"] == "spiffe://partner.io/backend/reporting"


def test_handshake_fails_when_only_client_direction_trusts(W):
    """Asymmetric trust: the client federates with the server's domain, but
    the server does not reciprocate. Established must be False."""
    client_bundle = W.TrustBundle("example.org", federates_with={"partner.io"})
    server_bundle = W.TrustBundle("partner.io")           # no reciprocation
    client = W.Workload(
        W.SpiffeID.parse("spiffe://example.org/frontend/web"), "web")
    server = W.Workload(
        W.SpiffeID.parse("spiffe://partner.io/backend/reporting"), "reporting")
    r = W.handshake(client, server, client_bundle, server_bundle)
    assert r["established"] is False
    assert "client" in r["reason"]
    # SANs are recorded even on failure — useful for the audit log
    assert r["client_saw"] == "spiffe://partner.io/backend/reporting"
    assert r["server_saw"] == "spiffe://example.org/frontend/web"
