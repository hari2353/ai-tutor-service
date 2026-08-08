# Frontend Security: XSS Sinks, CSP, CORS, Token Storage, Supply-Chain Risk in npm

> **Track:** T33 Frontend & UI Engineering · **Time:** 2.5h · **Prereqs:** T33-js-deep
> **Module id:** `T33-frontend-security` · **Tags:** security, critical

## The 30-second version

XSS happens when untrusted data reaches a "sink" that the browser interprets as executable — `innerHTML`, `dangerouslySetInnerHTML`, `eval`, `document.write`, and the `href`/`src` attributes with a `javascript:` scheme are the sinks that matter; React's default JSX text interpolation escapes automatically, which is why most React XSS in practice comes specifically from someone reaching for `dangerouslySetInnerHTML` on user content. A strict CSP built on nonces (`script-src 'nonce-<random-per-response>' 'strict-dynamic'`) is the durable defense-in-depth layer against XSS that does land — it blocks inline/injected scripts from executing even if an injection succeeds, and `strict-dynamic` lets a trusted, nonce'd root script load further scripts without needing a fragile host allowlist. CORS is a browser-enforced restriction on which origins JavaScript can read cross-origin responses from — it does not protect the server, it protects the requesting user's browser from a malicious page reading data it shouldn't; a permissive `Access-Control-Allow-Origin: *` combined with `Access-Control-Allow-Credentials: true` is invalid by spec and a real vulnerability if misconfigured. For token storage, the 2026 consensus is a hybrid: short-lived access tokens in JS memory (not persisted, gone on reload, limits exposure window) and refresh tokens in `HttpOnly`+`Secure`+`SameSite` cookies (invisible to JS, so an XSS bug can't exfiltrate them, at the cost of needing CSRF protection since the browser auto-attaches cookies). Clickjacking is defended with the CSP `frame-ancestors` directive (X-Frame-Options is the legacy fallback, and `frame-ancestors` wins when both are present). npm supply-chain risk is not theoretical — the September 2025 compromise of `chalk`/`debug`/16 other packages (2.6 billion combined weekly downloads) and the self-propagating Shai-Hulud worm that followed are the concrete, recent reference incidents, and the practical defenses are lockfiles, minimizing transitive dependency surface, and `npm audit`/Socket-style supply-chain scanning in CI, not vigilance alone.

## Why this gets asked

Because frontend security bugs are disproportionately cheap to introduce and expensive to discover — a single `dangerouslySetInnerHTML` call on unsanitized user content, or a misconfigured CORS header, sits quietly in a codebase until someone actively exploits it, and the interviewer has almost certainly either shipped or caught one of these late. They want to know whether "security" for you means a checklist item at the end of a sprint or a set of specific sinks and mechanisms you actively watch for while writing code. This is also one of the few areas where the interviewer's own production incident is very likely to be one of two specific things: an XSS that got through because CSP wasn't actually blocking inline scripts (a misconfigured `unsafe-inline` left in "temporarily"), or a supply-chain compromise via a transitive dependency nobody was auditing — and they want to hear you reason about defense in depth (multiple independent layers, so one failure doesn't mean full compromise) rather than a single silver-bullet answer.

---

## Lineage: past → present → future

**What came before.** Early web security thinking (1990s-2000s) treated the browser largely as a trusted rendering client and focused security effort almost entirely on the server — input validation, SQL injection defenses, server-side session management. XSS was documented as a category by the late 1990s but treated for years as a secondary concern relative to server-side injection classes, partly because the attack surface (client-side JS doing meaningful work with untrusted data) was smaller before AJAX-heavy, JS-rendered applications became the norm. The pain that forced client-side security into a first-class discipline was the shift to rich client-side rendering: once applications routinely took untrusted data (user bios, comments, search queries, URL parameters) and rendered it directly into the DOM via string concatenation or unescaped HTML insertion, XSS stopped being a niche bug class and became one of the most commonly exploited web vulnerabilities for over a decade (it sat in the OWASP Top 10 consistently), and CSP (first drafted around 2004-2009, CSP Level 1 published as a W3C spec in 2012) emerged specifically as the platform-level answer to "even if an injection succeeds, stop it from executing."

**Where it stands now.** React and similar frameworks' default auto-escaping of JSX text content eliminated the most naive class of XSS by making the safe path the default path — you have to deliberately reach for `dangerouslySetInnerHTML` to reintroduce the vulnerability, which is a genuinely different security posture than hand-written template strings. The live disagreement in CSP construction is host-allowlist policies versus nonce/strict-dynamic policies: allowlisting specific script-source domains was the original CSP model but is fragile in practice (third-party scripts load other third-party scripts unpredictably, breaking the allowlist constantly, and any allowlisted domain hosting an uploadable/writable path becomes a bypass), so the current consensus among practitioners who've actually operated CSP at scale (Google's own CSP guidance is explicit about this) favors nonce-based `strict-dynamic` policies that establish trust cryptographically per script rather than by source domain. Token storage has converged similarly: the localStorage-for-JWT pattern that was common advice in early SPA tutorials (2015-2018 era) is now widely recognized as actively dangerous specifically because it has no XSS-exfiltration protection at all, and the hybrid in-memory-access-token/HttpOnly-cookie-refresh-token pattern is the current practitioner consensus, even though it requires more implementation care (silent refresh flows, CSRF token handling) than the simpler-but-worse localStorage pattern.

**Where it's heading.** npm supply-chain security moved from a theoretical risk to a demonstrated, large-scale, actively exploited one in September-November 2025 — the `chalk`/`debug` compromise and the subsequent self-propagating Shai-Hulud worm (which infected 500+ packages in its first wave and a much larger "Shai-Hulud 2.0" campaign by November 2025) are recent enough and large enough that they've visibly shifted tooling investment: expect continued growth in supply-chain-specific scanning (Socket, Snyk, GitHub's own dependency review) and package-manager-level defenses (npm's provenance attestations, stricter default permissions for install scripts) as a direct, traceable response, though it's genuinely unresolved whether the ecosystem's structural incentive (small packages with many maintainers of wildly varying security practices, deep transitive dependency trees) can be fixed by tooling alone versus requiring a cultural shift toward vendoring/pinning more aggressively — that's a live, unresolved argument, not a settled direction.

---

## Mental model

Think of frontend security as layered defenses, each independently useful, so that one failing doesn't mean full compromise:

```
  Layer 1: Don't let untrusted data reach a sink        <- primary defense
  (escape by default, avoid innerHTML/dangerouslySetInnerHTML/eval)
                          │
                          ▼  (if this fails anyway)
  Layer 2: CSP blocks the injected script from running   <- defense in depth
  (nonce'd script-src, no unsafe-inline, no unsafe-eval)
                          │
                          ▼  (if a script somehow still executes)
  Layer 3: Even with JS execution, sensitive tokens aren't readable
  (HttpOnly cookies invisible to JS; access token has short TTL)
                          │
                          ▼
  Layer 4: Even with a valid token, cross-origin exfiltration is blocked
  (CORS restricts which origins can READ the response;
   frame-ancestors/X-Frame-Options blocks clickjacking overlay attacks)
```

The mental model that matters most for interviews: each layer is independently defeatable, and a mature security posture never relies on exactly one. A team that has "we escape user input" as their only XSS defense, with no CSP, is one missed sink away from full compromise; a team with both has a second chance even when the first defense fails.

---

## How it actually works

### XSS sinks, specifically

A "sink" is any API that takes a string and has the browser interpret part or all of it as code or markup rather than plain text. The ones that actually matter in a modern frontend codebase:

- **`innerHTML` / `outerHTML`** — assigns raw HTML that the browser parses and executes (script tags inserted this way don't run, but event handler attributes like `onerror` on an `<img>` do, and so does anything loaded by the parsed markup).
- **`dangerouslySetInnerHTML`** (React) — the framework's escape hatch that opts out of its default auto-escaping; the name is deliberately alarming for a reason. If the content passed to it contains any user-controlled data that isn't sanitized (e.g., with DOMPurify) first, it's a direct XSS sink.
- **`eval()` / `new Function()`** — executes a string as JavaScript directly; almost never legitimately necessary in application code, and its presence in a dependency is itself a red flag worth auditing.
- **`document.write()`** — parses and executes its argument as HTML into the document, with the added hazard of behaving very differently depending on when it's called (after page load it can wipe the entire document).
- **`javascript:` URLs** in `href`/`src`/`action` — if user-controlled data ends up as a link's `href` without validation, an attacker can supply `javascript:alert(document.cookie)` and get code execution on click.
- **`setTimeout`/`setInterval` with a string argument** (rather than a function) — behaves like `eval` for that string.

```jsx
// VULNERABLE — untested sketch showing the sink, not for use
function Comment({ userBio }) {
  return <div dangerouslySetInnerHTML={{ __html: userBio }} />; // userBio is attacker-controlled
}

// SAFE — sanitize first, and only use this escape hatch when HTML rendering is genuinely required
import DOMPurify from "dompurify";

function Comment({ userBio }) {
  const clean = DOMPurify.sanitize(userBio, { ALLOWED_TAGS: ["b", "i", "a"], ALLOWED_ATTR: ["href"] });
  return <div dangerouslySetInnerHTML={{ __html: clean }} />;
}

// SAFEST — if the content doesn't actually need to render as HTML, don't use the sink at all
function Comment({ userBio }) {
  return <div>{userBio}</div>; // JSX text interpolation auto-escapes
}
```

The critical detail: React's default JSX text interpolation (`{userBio}` as a child) auto-escapes automatically — the vulnerability only exists because someone deliberately reached for the escape hatch, usually because a legitimate feature (rich text, markdown-rendered-to-HTML) requires actual HTML rendering, which is exactly why sanitization (not avoidance) is the real answer for that legitimate case.

### CSP construction: nonces and `strict-dynamic`

A Content-Security-Policy header restricts what a page is allowed to load and execute, sent per response:

```
Content-Security-Policy:
  script-src 'nonce-r4nd0mPerResponseValue' 'strict-dynamic';
  object-src 'none';
  base-uri 'none';
  frame-ancestors 'self';
```

`script-src 'nonce-...'` means only `<script>` tags carrying a matching `nonce` attribute execute — the nonce must be freshly random per HTTP response (reusing a nonce across responses defeats the entire mechanism, since an attacker who can inject markup could then also guess/reuse a static nonce). `'strict-dynamic'` propagates trust from a nonce'd root script to any script that root script itself loads dynamically (e.g., a bundler's dynamically inserted chunk-loading script), which solves the practical problem that a host-allowlist-based CSP (`script-src https://trusted-cdn.com`) breaks constantly in real applications — third-party scripts load other scripts from origins you didn't anticipate and can't practically enumerate, and any allowlisted domain that has an open redirect or user-uploadable content becomes a CSP bypass. `object-src 'none'` blocks Flash/plugin-based injection vectors (largely legacy now but still worth setting), and `base-uri 'none'` prevents an injected `<base>` tag from silently rewriting all relative URLs on the page to an attacker's domain. Two directives that must never appear in a production CSP meant to actually stop XSS: `unsafe-inline` (allows any inline script to execute, which defeats the entire point) and `unsafe-eval` (allows `eval`/`new Function`, reopening that sink specifically).

### CORS: what it actually protects, and what it doesn't

CORS is a browser-side restriction on whether client-side JavaScript running on origin A can read the response body of a cross-origin request to origin B — it does not stop the request from being sent (the request still reaches the server and executes; the browser only blocks the *response* from being readable by the calling script when the server hasn't opted in), and it does not protect the server from anything except this one specific browser-mediated read. This is a genuinely common misconception worth being precise about: CORS is not a server-side authorization mechanism, it's the server telling browsers which origins are allowed to read responses.

```
Access-Control-Allow-Origin: https://app.example.com
Access-Control-Allow-Credentials: true
```

A server that reflects `Access-Control-Allow-Origin` to match whatever `Origin` header the request sent, combined with `Access-Control-Allow-Credentials: true`, is a real vulnerability — it means any origin can make an authenticated (cookie-carrying) cross-origin request and read the response, defeating the entire same-origin protection the browser otherwise provides. The spec itself blocks the naive `Access-Control-Allow-Origin: *` from being combined with credentials (browsers refuse to expose the response in that combination), but a server that dynamically reflects the request's `Origin` header value back verbatim as an "allow all, but not literally `*`" workaround reintroduces the same vulnerability while looking superficially compliant.

Preflight (`OPTIONS`) requests happen automatically before "non-simple" cross-origin requests (custom headers like `Authorization`, methods other than GET/POST/HEAD, or a `Content-Type` other than form-encoded/plain-text/multipart) — the browser asks the server "would you allow this specific method/headers combination from my origin" via `Access-Control-Request-Method`/`Access-Control-Request-Headers`, and only sends the real request if the server's `OPTIONS` response affirms it via `Access-Control-Allow-Methods`/`Access-Control-Allow-Headers`.

### Token storage tradeoffs, concretely

| Storage | Readable by JS (XSS exposure) | Auto-sent by browser (CSRF exposure) | Survives reload | Practical verdict |
|---|---|---|---|---|
| `localStorage` | Yes — any successful XSS reads it trivially | No | Yes | An XSS bug becomes a full, silent account takeover; widely considered a mistake for auth tokens despite being the most common tutorial pattern |
| `sessionStorage` | Yes, same as localStorage | No | Only within the tab session | Same XSS exposure as localStorage, marginally reduced blast radius (tab-scoped) but not a real mitigation against the core problem |
| `HttpOnly` cookie | No — invisible to `document.cookie` and any JS API | Yes — automatically attached to matching-origin requests | Yes, per cookie expiry | Immune to XSS-based token exfiltration, but introduces CSRF surface since the browser attaches it without the page's JS having to do anything |
| In-memory (a JS variable/closure, never persisted) | Yes, technically, if an attacker can execute arbitrary JS at the right moment — but nothing to steal after reload | No | No — lost on refresh, needs a refresh flow | Minimizes exposure window (nothing persisted to steal at rest) at the cost of needing a working silent-refresh mechanism |

The 2026 practitioner consensus, converging from these tradeoffs: short-lived access token in memory only (never localStorage — gone on reload, and a short TTL limits the damage window even if somehow exfiltrated mid-session) plus a longer-lived refresh token in an `HttpOnly`+`Secure`+`SameSite=Lax` (or `Strict`, depending on cross-site navigation needs) cookie, with CSRF protection (a synchronizer token or double-submit cookie pattern) specifically on state-changing endpoints since the refresh cookie is auto-attached by the browser.

### Clickjacking

An attacker embeds the target site in an invisible (opacity: 0, or precisely positioned) `<iframe>` on their own page, overlays a decoy UI, and tricks a logged-in user into clicking what looks like an innocuous button on the decoy but is actually clicking a real button on the embedded, invisible target site (e.g., "Delete Account" or "Authorize Payment" positioned exactly under a "Claim Your Prize" button). Defense is a response header the framed page sends, refusing to be framed at all: `Content-Security-Policy: frame-ancestors 'self'` (or a specific allowlist of origins permitted to frame it) is the current mechanism, taking precedence in all CSP Level 2+ supporting browsers (effectively all current ones) over the older `X-Frame-Options: DENY`/`SAMEORIGIN` header, which is kept only as a fallback for the rare legacy client. Critically, `X-Frame-Options` cannot be set via a `<meta>` tag — it only works as a real HTTP response header, a common implementation mistake.

### npm supply-chain risk, with the real incidents

On September 8, 2025, a phishing attack against a single prolific npm maintainer (a fake "your 2FA needs updating" email from a lookalike domain) led to the compromise of 18 widely-used packages including `chalk`, `debug`, `ansi-styles`, and `strip-ansi` — packages with a combined 2.6 billion weekly downloads, meaning the vast majority of JS projects had at least one of them somewhere in their dependency tree, directly or transitively. The injected payload targeted cryptocurrency wallet interactions specifically (intercepting and rewriting transaction data). This was quickly followed by the "Shai-Hulud" worm, first identified in the following weeks, which self-propagated by using stolen credentials from infected developer machines to publish further malicious packages automatically — over 500 packages in its first wave, and a much larger "Shai-Hulud 2.0" campaign in November 2025 that affected tens of thousands of GitHub repositories. The mechanical lesson: the vulnerability wasn't in application code at all — it was in a transitive dependency several layers removed from anything the affected teams directly chose or reviewed, which is exactly the structural risk of npm's deep dependency graphs. Practical mitigations: commit and enforce lockfiles (`package-lock.json`/`pnpm-lock.yaml`) so installs are deterministic and a compromised new version of a transitive dependency doesn't get pulled in silently on the next `npm install`; run `npm audit` (or a more thorough supply-chain-specific scanner like Socket or Snyk, which analyze actual package behavior — e.g., flagging install scripts making network calls — not just known-CVE matching) in CI; minimize and periodically prune the dependency tree, since every added dependency (and its own transitive dependencies) is added attack surface regardless of how well-maintained it looks at add-time; and be skeptical of automatic dependency-update bots merging without human review for anything touching authentication, crypto, or build tooling specifically.

---

## Build it from scratch

A concrete, checkable exercise: stand up a minimal Express server serving a page with a deliberately vulnerable `dangerouslySetInnerHTML` rendering unsanitized query-string content, confirm the XSS actually fires (an `<img src=x onerror=alert(1)>` payload in the URL), then add a strict nonce-based CSP header and confirm the same payload no longer executes (the injected markup renders but the browser refuses to run the embedded handler since it's not associated with the trusted nonce) — then fix the actual sink with DOMPurify as the primary defense, leaving the CSP in place as defense in depth. This sequence is valuable specifically because it makes visible that CSP and input sanitization are two independent layers, not redundant ones. Reference: `labs/js/11-frontend-security/`.

---

## How it's done in production

Real CSP deployment in production is usually generated per response (not a static file) because the nonce must be fresh per request — most frameworks/edge middleware inject it into both the response header and the rendered `<script nonce="...">` tags at render time. CORS configuration lives in API gateway/backend middleware, with an explicit origin allowlist (never a reflected/dynamic wildcard for anything requiring credentials). Token storage is implemented via an auth SDK or hand-rolled silent-refresh flow (an in-memory access token refreshed via a background call using the HttpOnly refresh cookie before it expires, retried transparently on a 401).

| Symptom | Cause | Fix |
|---|---|---|
| CSP is deployed but inline scripts still execute after an XSS injection | `unsafe-inline` left in the policy (often "temporarily" during initial rollout to avoid breaking things, then forgotten) | Remove `unsafe-inline`; migrate remaining inline scripts to nonce'd `<script nonce="...">` tags or external files |
| CSP nonce is present but doesn't actually block anything | The nonce value is static/hardcoded rather than freshly random per HTTP response, so an attacker who can inject markup can reuse the known nonce | Generate a new cryptographically random nonce per response, server-side, injected into both the header and the markup at render time |
| A cross-origin API call fails silently in the browser console with a CORS error, but works fine in Postman/curl | CORS is a browser-enforced restriction, not a server-side one — the request DID reach the server (visible server-side in logs), the browser just refused to expose the response to the calling script since the server's CORS headers didn't allow it | This usually means CORS is working as intended; fix by adding the correct explicit `Access-Control-Allow-Origin` for legitimate origins, not by weakening it to `*` with credentials |
| An authenticated user gets tricked into an unintended action via an embedded iframe on another site | No `frame-ancestors`/`X-Frame-Options` header, page can be legitimately framed | Add `Content-Security-Policy: frame-ancestors 'self'` (or an explicit allowlist); confirm it's a real header, not a `<meta>` tag, which doesn't work for this directive |
| A dependency several layers deep in the tree starts exfiltrating credentials or manipulating data with no application code change | A transitive dependency was compromised upstream (maintainer account takeover, malicious version publish) — this is exactly the September 2025 chalk/debug/Shai-Hulud pattern | Lockfiles to prevent silent version drift, supply-chain scanning in CI (Socket/Snyk-style behavioral analysis, not just CVE matching), and minimizing dependency surface generally |
| localStorage-stored auth token is exfiltrated via an unrelated XSS bug elsewhere on the page | Any successful XSS anywhere on the page can read localStorage in full, regardless of where the injection point was relative to the auth logic | Move to HttpOnly cookie (refresh token) + in-memory (access token) storage so XSS execution alone isn't sufficient to read the token |

---

## Tradeoffs & when NOT to use it

- **Don't treat CSP as a substitute for fixing the actual XSS sink.** CSP is defense in depth — it reduces the blast radius of an injection that already happened, but relying on it alone while leaving `dangerouslySetInnerHTML` unsanitized is backwards prioritization; fix the sink first, add CSP as a second layer, not the only layer.
- **Don't reach for `HttpOnly` cookies as a silver bullet without accounting for CSRF.** Moving tokens out of JS-readable storage closes the XSS exfiltration path but opens (or reopens) the CSRF path, since the browser auto-attaches cookies to matching requests regardless of which page initiated them — `SameSite` plus an explicit CSRF token on state-changing endpoints is the actual complete answer, not the cookie flag alone.
- **Don't default to `Access-Control-Allow-Origin: *` "to make it work" during development and forget to lock it down.** This is one of the most common real production CORS misconfigurations, and it's especially dangerous combined with credentialed requests.
- **Don't assume `X-Frame-Options` set via a meta tag does anything.** It's a real, common mistake — the directive is only honored as an HTTP response header.
- **Don't add a dependency (or accept an update) without proportional scrutiny to what it touches.** A left-pad-style trivial utility warrants less individual review than a package handling authentication, payments, or crypto — but the September 2025 incident is a reminder that even "boring," widely-trusted, low-risk-seeming packages (`chalk`, a terminal color library) are viable attack vectors precisely because nobody scrutinizes them, which is an argument for lockfiles and automated scanning over manual vigilance alone, since manual vigilance predictably fails exactly where trust is highest.

---

## Interview questions

### Q1 — Name the frontend XSS sinks that actually matter in a modern codebase, and why does React's default rendering avoid the most common one?
**Testing:** whether the candidate can name specific APIs rather than a vague "sanitize your inputs."
**Answer:** `innerHTML`/`outerHTML`, `dangerouslySetInnerHTML`, `eval`/`new Function`, `document.write`, `javascript:` URLs in href/src, and string-argument `setTimeout`/`setInterval`. React's default JSX text interpolation (`{value}` as a child) auto-escapes, so the vulnerability requires someone deliberately opting into `dangerouslySetInnerHTML` — a meaningfully different security posture than hand-written template strings where escaping has to be remembered every time.
**Follow-up trap:** *"If a feature genuinely needs to render user-supplied HTML (rich text), what's the right approach?"* — sanitize with a library like DOMPurify with an explicit allowlist of tags/attributes before passing to `dangerouslySetInnerHTML`, not avoidance of the sink entirely (the feature requirement is real) and not a hand-rolled regex-based sanitizer (regex can't reliably parse HTML and is a well-documented source of sanitizer bypasses).

### Q2 — Why is a nonce-based CSP with `strict-dynamic` preferred over a host-allowlist CSP in current practice?
**Testing:** whether the candidate understands the practical failure mode of allowlisting, not just that nonces exist.
**Answer:** Host allowlists (`script-src https://trusted-cdn.com`) break constantly because third-party scripts load further scripts from origins that weren't anticipated and can't be practically enumerated, and any allowlisted domain with an open redirect or user-uploadable path becomes a CSP bypass. `strict-dynamic` propagates trust cryptographically from a nonce'd root script to whatever it loads, avoiding the need to maintain a fragile, constantly-breaking domain list.
**Follow-up trap:** *"What's the one thing that completely defeats a nonce-based CSP, and how would you catch it in review?"* — a static or predictable nonce value (hardcoded, or generated with a non-cryptographic/reused source) — the nonce must be freshly random per HTTP response. Catch it in review by checking the nonce generation source directly (is it from a CSPRNG, is it actually per-request) rather than just confirming a nonce attribute exists in the markup.

### Q3 — Explain precisely what CORS protects against, and correct the common misconception about what it doesn't do.
**Testing:** the specific, frequently-misunderstood mechanics of CORS.
**Answer:** CORS is a browser-enforced restriction on whether client-side JS on one origin can read the response body of a cross-origin request — it does not stop the request from being sent or executed server-side; the server still receives and processes it. It's not a server-side authorization mechanism; it's the server declaring which origins browsers should allow to read the response.
**Follow-up trap:** *"If a cross-origin fetch fails in the browser console with a CORS error, does that mean the request never reached the server?"* — no, and this trips people up constantly: the request typically did reach the server (visible in server logs, and any side effect it caused — like a database write on a POST — already happened) even though the browser blocked the calling script from reading the response. CORS protects response-reading, not request-sending, which matters a lot for reasoning about what "failed" actually means.

### Q4 — Why is `Access-Control-Allow-Origin: *` combined with `Access-Control-Allow-Credentials: true` dangerous, and why doesn't the spec's block on that exact combination fully solve the problem?
**Testing:** understanding a specific, real production CORS vulnerability pattern.
**Answer:** That literal combination lets any origin make credentialed (cookie-carrying) cross-origin requests and read the response, defeating same-origin protection entirely — which is why browsers refuse to expose the response when both are set together with a literal `*`. But a server that dynamically reflects the request's `Origin` header value back as the allow-origin value (instead of a literal `*`) reintroduces the identical vulnerability while looking superficially compliant, since it's not technically the `*` wildcard the spec blocks.
**Follow-up trap:** *"How would you correctly support multiple legitimate origins with credentials, then?"* — maintain an explicit server-side allowlist of legitimate origins, validate the incoming `Origin` header against that allowlist, and only echo it back as `Access-Control-Allow-Origin` when it matches an entry on that list — not a blanket reflection of whatever `Origin` was sent.

### Q5 — Compare storing an auth token in localStorage versus an HttpOnly cookie versus in-memory. What's the 2026 practitioner consensus and why?
**Testing:** whether the candidate can reason through the actual tradeoff table rather than reciting "cookies are more secure."
**Answer:** localStorage is readable by any successful XSS, making an XSS bug a full silent account takeover — widely considered a mistake for auth tokens despite being the most common tutorial pattern. HttpOnly cookies are invisible to JS (immune to XSS-based exfiltration) but auto-attached by the browser, introducing CSRF exposure that needs its own mitigation. In-memory storage minimizes the exposure window (nothing persisted to steal at rest) but requires a working silent-refresh flow since it's lost on reload. Current consensus: short-lived access token in memory, longer-lived refresh token in an HttpOnly+Secure+SameSite cookie, with CSRF protection on state-changing endpoints.
**Follow-up trap:** *"Does moving to HttpOnly cookies alone fully solve the security problem?"* — no; it closes the XSS-exfiltration path but does nothing about CSRF, since the cookie is auto-sent regardless of which page initiated the request. `SameSite=Lax`/`Strict` plus an explicit CSRF token (double-submit cookie or synchronizer token pattern) on state-changing endpoints is required for a complete answer, not the HttpOnly flag by itself.

### Q6 — What is clickjacking, mechanically, and what's the correct current defense header?
**Testing:** whether the candidate knows the current mechanism (`frame-ancestors`) versus only the legacy one.
**Answer:** An attacker embeds the target site in an invisible or precisely positioned iframe, overlays a decoy UI, and tricks a logged-in user into clicking what looks like harmless decoy content but is actually clicking a real, sensitive control on the hidden embedded site underneath. The current defense is `Content-Security-Policy: frame-ancestors 'self'` (or an explicit origin allowlist), which takes precedence over the legacy `X-Frame-Options` header in all CSP Level 2+ browsers (effectively all current ones); `X-Frame-Options` is kept only as a fallback for rare legacy clients.
**Follow-up trap:** *"A team sets X-Frame-Options via a <meta> tag in their HTML and believes they're protected. What's wrong?"* — `X-Frame-Options` is only honored as a real HTTP response header; setting it via `<meta>` does nothing, and the page remains framable. This is a genuinely common real-world implementation mistake, not a hypothetical.

### Q7 — Describe the September 2025 npm supply-chain incident and what it structurally demonstrates about dependency risk.
**Testing:** whether the candidate tracks real, recent incidents rather than reasoning about supply-chain risk purely in the abstract.
**Answer:** A phishing attack against a single prolific npm maintainer (a fake "update your 2FA" email from a lookalike domain) compromised 18 widely-used packages including `chalk`, `debug`, `ansi-styles`, and `strip-ansi` — a combined 2.6 billion weekly downloads — with a payload targeting cryptocurrency wallet transactions. It was followed by the self-propagating "Shai-Hulud" worm, which used stolen credentials from infected developer machines to automatically publish further malicious packages, infecting 500+ packages in its first wave and expanding to a much larger campaign by November 2025. It demonstrates that the vulnerability wasn't in any affected team's own application code — it was several layers deep in a transitive dependency nobody was individually reviewing, which is the structural risk of deep npm dependency graphs specifically.
**Follow-up trap:** *"If your team's own code never called anything from the compromised packages directly, were you still at risk?"* — yes, if the compromised package was anywhere in the transitive dependency tree (a dependency of a dependency), since it still executes in the same process/build environment with the same permissions — direct usage isn't required for exposure, which is exactly why lockfiles (preventing silent version drift on install) and supply-chain scanning matter even for packages a team never explicitly imports.

### Q8 — Design the CSRF protection needed once auth moves from localStorage to HttpOnly cookies.
**Testing:** staff-level: whether the candidate can specify the actual mechanism, not just name "CSRF token" as a buzzword.
**Answer:** Set `SameSite=Lax` (or `Strict` if no legitimate cross-site navigation needs to carry the cookie) on the auth cookie as a first layer — this blocks most cross-site request forgery by default in modern browsers. For state-changing endpoints specifically, add an explicit CSRF token: either the synchronizer token pattern (server issues a per-session token embedded in the page, client must include it in a header/body on state-changing requests, server validates it matches the session) or the double-submit cookie pattern (a second, non-HttpOnly cookie holding a token the client must also send back as a header — an attacker's cross-site request can trigger the cookie to be sent automatically but can't read its value to also set the matching header, since it can't read a cookie from a different origin).
**Follow-up trap:** *"Why doesn't SameSite alone fully solve CSRF, requiring the additional token layer?"* — `SameSite=Lax` still allows top-level GET navigations (a user clicking a malicious link that top-level-navigates to a state-changing GET endpoint) to carry the cookie, and browser support/enforcement nuances (older browsers, certain subdomain configurations) mean it's a strong mitigation, not a complete guarantee — defense in depth with an explicit CSRF token on genuinely state-changing operations remains the more robust design.

### Q9 — A component uses `window.postMessage` to communicate with an embedded third-party iframe. What's the specific vulnerability this introduces if the message handler doesn't validate `event.origin`, and what's the correct fix?
**Testing:** a genuinely common, real cross-origin messaging vulnerability distinct from the XSS/CSP/CORS material already covered.
**Answer:** `postMessage` by design lets any window with a reference to the target window (including a malicious page that opened it, or an attacker-controlled iframe on the same page) send it a message — if the receiving handler acts on the message content (rendering it, using it to make a decision, passing it to a sink) without first checking `event.origin` against an explicit allowlist of expected senders, any page on the web can forge messages that the handler treats as trusted, effectively bypassing whatever origin isolation the browser's same-origin policy would otherwise provide. The fix: always check `event.origin === expectedOrigin` (or against an explicit allowlist) as the first line of the handler, reject anything that doesn't match, and — symmetrically — always specify the exact target origin (not `"*"`) as the second argument when *sending* a message, so the message itself isn't broadcast to an unintended origin if the target window has navigated elsewhere since the reference was obtained.
**Follow-up trap:** *"The team says they already check `event.source` instead of `event.origin` — is that sufficient?"* — no, and conflating the two is a real, subtle mistake: `event.source` identifies *which window object* sent the message (useful for replying to the right window) but says nothing about that window's *origin*, and a window's origin can also change via navigation after the reference was captured — origin validation and source validation solve different problems, and skipping the origin check specifically leaves the forgery vulnerability open even with a source check in place.

### Q10 — A production app loads a third-party analytics script directly from a CDN URL with a plain `<script src="...">` tag. What's the supply-chain risk, and what's the concrete browser-native mitigation?
**Testing:** Subresource Integrity as a specific, standard defense — connects directly to the npm supply-chain incident already covered in Q7, applied to script-tag loading rather than package installation.
**Answer:** A `<script src>` pointing at a third-party-controlled URL trusts that CDN (and everything upstream of it — the vendor's build pipeline, their own dependencies) to serve exactly the code you reviewed, indefinitely, with no verification — if that CDN is compromised, or the vendor's account is compromised and they push a malicious update to the same URL, the script silently changes and executes with full page privileges on every page load, no code change on your side required to trigger it. Subresource Integrity (`<script src="..." integrity="sha384-..." crossorigin="anonymous">`) mitigates this specifically: the browser computes a cryptographic hash of the fetched script and refuses to execute it if the hash doesn't match the one specified in the `integrity` attribute, so a tampered or swapped script fails closed instead of executing silently.
**Follow-up trap:** *"The third-party script updates weekly with new features. Doesn't SRI break every time they ship a legitimate update, since the hash changes?"* — yes, and that's a genuine, real operational tradeoff worth naming honestly: SRI trades convenience for verification — a vendor that updates frequently without a versioned/pinned URL scheme makes SRI high-maintenance (the hash needs updating on every legitimate change too, indistinguishable at the hash level from a malicious one) — the practical answer is preferring vendors that publish versioned, immutable CDN URLs (a specific version number in the path) so you control exactly when to pull a new version and update the hash deliberately, rather than a "latest" URL that changes underneath you with no signal.

---

## Red flags that fail you

- Using `dangerouslySetInnerHTML` (or `innerHTML`) on user-controlled content with no sanitization, and not recognizing it as a problem.
- Claiming CORS protects the server or stops the request from being sent/processed.
- Recommending `localStorage` for auth tokens without acknowledging the XSS exfiltration risk.
- Believing `<meta http-equiv="X-Frame-Options">` provides real clickjacking protection.
- Including `unsafe-inline` or `unsafe-eval` in a CSP meant to mitigate XSS.
- Treating npm supply-chain risk as purely theoretical or "someone else's problem."
- Reflecting the request's `Origin` header as `Access-Control-Allow-Origin` and calling it equivalent to a proper allowlist.

---

## Cheat card

```
XSS SINKS: innerHTML/outerHTML, dangerouslySetInnerHTML, eval/new Function,
  document.write, javascript: URLs, string-arg setTimeout/setInterval.
  React JSX {value} auto-escapes by default — vuln requires opting into a sink.
  Fix: DOMPurify with explicit allowlist, not avoidance alone if HTML render needed.

CSP: script-src 'nonce-<fresh-per-response>' 'strict-dynamic'; object-src 'none';
  base-uri 'none'; frame-ancestors 'self'.
  NEVER: unsafe-inline (defeats it), unsafe-eval (reopens eval sink).
  Nonce MUST be cryptographically random PER RESPONSE, not static/reused.
  strict-dynamic > host allowlist (allowlists break on 3rd-party script chains,
  any allowlisted domain w/ open redirect = bypass).

CORS: browser-side restriction on JS READING cross-origin responses.
  Request still SENT/PROCESSED server-side regardless — not a server auth mechanism.
  Access-Control-Allow-Origin:* + credentials:true = spec-blocked, but REFLECTING
  Origin header dynamically reintroduces the same hole. Use explicit allowlist.
  Preflight (OPTIONS) fires for non-simple requests (custom headers, non-GET/POST,
  non-form Content-Type).

TOKEN STORAGE 2026 consensus: access token in MEMORY (short TTL, gone on reload,
  minimizes exfil window) + refresh token in HttpOnly+Secure+SameSite cookie
  (invisible to JS, immune to XSS read) + CSRF token on state-changing endpoints
  (cookie auto-sent by browser = CSRF surface HttpOnly alone doesn't close).
  localStorage for tokens = XSS bug becomes full silent account takeover.

CLICKJACKING: invisible/positioned iframe overlay tricks click on hidden real
  button. Fix: CSP frame-ancestors 'self' (wins over X-Frame-Options in CSP2+
  browsers = effectively all). X-Frame-Options via <meta> tag = NO EFFECT,
  header only.

NPM SUPPLY CHAIN: Sept 2025 — phishing compromised maintainer -> chalk/debug/
  16 others (2.6B weekly downloads) hijacked -> crypto-wallet-targeting payload.
  Followed by self-propagating Shai-Hulud worm (500+ pkgs wave 1, tens of
  thousands of repos by "2.0" in Nov 2025). Risk is TRANSITIVE — team never
  imports compromised pkg directly, still exposed via dependency tree.
  Mitigate: commit+enforce lockfiles, npm audit / Socket-Snyk behavioral scan
  in CI, minimize dependency surface, scrutinize auto-merge bots on
  auth/crypto/build-tooling deps specifically.
```

## Sources

- [Content Security Policy — OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Content_Security_Policy_Cheat_Sheet.html) — accessed 2026-08-02
- [Strict CSP — Google](https://csp.withgoogle.com/docs/strict-csp.html) — accessed 2026-08-02
- [npm Supply Chain Attack: Massive Compromise of debug, chalk, and 16 Other Packages — Upwind](https://www.upwind.io/feed/npm-supply-chain-attack-massive-compromise-of-debug-chalk-and-16-other-packages) — accessed 2026-08-02
- ["Shai-Hulud" Worm Compromises npm Ecosystem — Unit 42, Palo Alto Networks](https://unit42.paloaltonetworks.com/npm-supply-chain-attack/) — accessed 2026-08-02
- [Cookie vs LocalStorage: Ultimate Token Security Guide 2026 — Volcanic Minds](https://volcanicminds.com/en/insights/cookie-vs-localstorage-security-guide) — accessed 2026-08-02
- [Clickjacking Defense — OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Clickjacking_Defense_Cheat_Sheet.html) — accessed 2026-08-02
- MDN — Content-Security-Policy, CORS, X-Frame-Options reference — living reference docs

## Changelog
- 2026-08-02 — created
