# Lab 08: The Web Attack Lab — XSS, CSRF, SSRF

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-web-attacks`

**You will build:** the three web attacks as working miniature systems — a `TemplateEngine` with autoescape ON (payload renders inert) vs raw interpolation (live `<script>`), a `CsrfProtectingFormHandler` with per-session, clock-expiring tokens that rejects cross-site POSTs *and* tokens leaked from other sessions, and a `UrlFetcher` with a hand-rolled CIDR check that blocks metadata endpoints, localhost, private ranges, DNS-rebinding aliases, and — the trap — public URLs that redirect to private targets.

**You will be able to answer:** *"Explain XSS vs CSRF vs SSRF — mechanism, one real exploit each, and the fix that actually works."*

## Setup

```bash
cd labs/py/08-web-attack-lab
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest
```

## The spec

1. **`TemplateEngine.render`** — `{key}` substitution from a context dict. `autoescape=True`: every value through `html.escape(quote=True)` (covers attribute injection too). `autoescape=False`: raw — the vulnerability, kept deliberately so the tests can *show* it. Missing key raises `KeyError`.
2. **`CsrfProtectingFormHandler`** — `issue_token(session_id)` mints `secrets.token_urlsafe` bound to that session with a clock TTL. `submit` accepts only the *current* session's *unexpired* token. Session-bound means a token harvested from any other session is rejected.
3. **`ip_in_cidr(ip, cidr)`** — the IPv4 CIDR math yourself: `(ip & mask) == (net & mask)`.
4. **`UrlFetcher._check_url`** — scheme must be http/https (`file:`, `gopher:` refused); blocked metadata hostnames; resolved IP must miss every private range (10/8, 127/8, 169.254/16, 172.16/12, 192.168/16, 0/8) plus IPv6 loopback/link-local text. Resolver is injectable — fake DNS, no network.
5. **`UrlFetcher.get`** — follow redirects but **re-run every check on every hop**; refuse the whole chain if any hop fails.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **CSP as a second layer** — add a `ContentSecurityPolicy` object that blocks inline `<script>` and assert the live payload from the vulnerable mode is neutralized even though the HTML is intact.
2. **Double-submit cookie** — the stateless CSRF variant (`Cookie: csrf=x` header must match `csrf=x` field); write the test showing why SameSite=Lax covers most of what it did.
3. **TOCTOU rebinding** — make the resolver return public on first call, private on second (that *is* real DNS rebinding); your fetcher should resolve *once per hop* and pin the IP for that fetch.
