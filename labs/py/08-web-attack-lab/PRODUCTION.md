# Production notes — XSS, CSRF, SSRF

## What you'd actually use

| Concern | Production answer |
|---|---|
| XSS | Template-engine autoescape ON by default (Jinja2, React's JSX), **CSP** (no `unsafe-inline`), `HttpOnly` cookies so XSS can't steal sessions |
| CSRF | **SameSite=Lax** cookies (the 2026 default and the main defense), plus synchronizer tokens where cross-site POSTs must work |
| SSRF | Allowlist egress proxies, `requests` + `url-normalize` + a resolver-pinning library (e.g. `requests-ssrf-protect`), network-level egress deny by default |

## What the real systems add over yours

- **Contextual autoescaping** — real engines escape differently in HTML body vs attribute vs URL vs `<script>` contexts. One `html.escape` everywhere is *mostly* right; the failure mode is auto-unwrapped `|safe` / `dangerouslySetInnerHTML` — the code-review line to hunt.
- **SameSite cookie taxonomy** — `Strict` (no cookie on top-level navigations from elsewhere — breaks SSO links), `Lax` (cookie on safe top-level navigation, NOT on cross-site POST — the sweet spot), `None` (requires `Secure`; only for genuine cross-site iframe needs). CSRF token + SameSite is defense in depth, not either/or.
- **SSRF: the real killer is redirect-following + DNS rebinding** — your `_check_url`-per-hop is exactly the production rule (both CVE classes: validate-after-fetch and resolve-twice). Real fetchers additionally *pin* the resolved IP for the connection (rebinding defeats naive resolve-then-connect) and block **IPv6-mapped IPv4** (`::ffff:10.0.0.1`), decimal/octal IP encodings (`2130706433`), and `0.0.0.0` — your `0.0.0.0/8` entry is that rule.
- **Metadata service v2** — AWS IMDSv2 requires a session token acquired via a hop-count-limited PUT: SSRF that can't do the two-step dance gets nothing. GCP/Azure wrap it in mandatory headers. Defense in depth for exactly the 169.254.169.254 endpoint you just blocked.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| XSS found despite escaping | one `|safe` in a template, or Markdown/HTML rendered raw | sanitize with allowlist (DOMPurify/bleach), CSP as backstop |
| CSRF reports despite tokens | token not bound to session, or SameSite=None for no reason | bind token to session (you did), audit every `SameSite=None` |
| Fetcher bypassed via 302 | validated once, followed N times | re-validate every hop (you did) |
| Fetcher bypassed via rebinding | resolve-then-connect with a second DNS lookup | pin the IP after the first resolve; or use a resolver proxy |
| SSRF via IPv6/decimal encodings | checks only dotted-quad IPv4 text | normalize first (`ipaddress.ip_address` after parsing), then check |
| Egress scanner blind to cloud metadata | private-CIDR list missing 169.254/16 | your list has it; test it in CI |

## Cost & latency

All three fixes are ~free at runtime (escaping is string ops; SameSite is a cookie attribute; SSRF checks are two syscalls' worth of parsing). What they actually cost is **correctness discipline**: one raw template, one `SameSite=None`, one un-validated redirect — and the control is gone while the test suite stays green if you didn't test the behavior (which is why this lab asserts on output strings and refusals, not on internals).

## The 3 questions an interviewer asks after you describe this

1. *"Why is CSP a backstop and not the fix for XSS?"* — CSP limits what executed script can *do* (no inline, exfil rules); it doesn't fix the injection. Fix escaping at the sink; CSP catches what you miss.
2. *"If SameSite=Lax kills CSRF, why keep tokens?"* — Lax still sends cookies on top-level GET navigations, older browsers ignore it, and subdomain-owned POSTs slip by. Tokens are cheap; the pair is the standard.
3. *"Your fetcher blocks private IPs. How does the cloud metadata endpoint still get hit in real incidents?"* — redirects, DNS rebinding, and IP-encoding tricks — the three things this lab makes you build against.
