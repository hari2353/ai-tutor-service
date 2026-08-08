# Access vs Refresh Tokens, Rotation, Revocation Lists, TTL Caching, Where to Store Them

> **Track:** T30 Auth & Application Security · **Time:** 2.5h · **Prereqs:** `T30-jwt-security`
> **Updated:** 2026-07-26
> **Module id:** `T30-token-lifecycle` · **Tags:** jwt, critical
> **Lab:** `labs/py/05-refresh-rotation/`

## The 30-second version

Access tokens are short-lived (5-15 minutes), stateless, and do the actual authorization work on every request; refresh tokens are long-lived (days to weeks), server-tracked, and exist for exactly one purpose — minting new access tokens without forcing the user to re-authenticate. Refresh token **rotation** means every refresh invalidates the token just used and issues a new one, and **reuse detection** is what makes rotation actually valuable: if a supposedly-already-used refresh token shows up again, that's a signal the token was stolen and duplicated, so the server revokes the entire token family rather than quietly issuing another access token to whoever presented it. Where you store these client-side is a real, contested tradeoff — `httpOnly` cookies block JavaScript-based exfiltration (XSS) but reopen CSRF; `localStorage` is simple and CSRF-immune but fully exposed to any successful XSS — and OWASP's actual guidance is to avoid `localStorage` for anything sensitive precisely because of that exposure, not because of some vague "cookies are safer" folklore.

## Why this gets asked

Because "we use refresh tokens" is a sentence engineers say without necessarily having reasoned about what happens when one gets stolen — and refresh tokens, being long-lived, are a higher-value theft target than access tokens by design. The interviewer wants to know whether you understand rotation as a detection mechanism, not just a hygiene practice, and whether you've actually weighed the storage tradeoff rather than picked `localStorage` because it's the first Stack Overflow answer.

---

## Lineage: past → present → future

**What came before.** Early OAuth 2.0 deployments (RFC 6749, 2012) issued long-lived access tokens directly — sometimes with no expiry at all, or expiries measured in days — because refresh flows added implementation complexity that many teams skipped. The pain this caused was structural: a stolen access token from this era was often valid for as long as the token itself existed, with no natural expiry forcing re-authentication and no server-side lever to cut it off short of a blunt, system-wide key rotation that invalidated every token for every user simultaneously. The refresh-token pattern existed in the spec from the start but was frequently treated as optional convenience (avoid re-prompting for a password) rather than as a security control, and *rotation* of refresh tokens — issuing a new one on every use — was rarer still, meaning a single leaked refresh token, valid for its full multi-week or multi-month lifetime, was a standing risk with no way to detect it had been copied rather than just used by its legitimate owner.

**Where it stands now.** Refresh token rotation with reuse detection is now the documented, expected pattern (OAuth 2.0 Security Best Current Practice, and effectively mandatory under the emerging OAuth 2.1 consolidation) rather than an advanced technique: every refresh both issues a new token and invalidates the one presented, and the server remembers enough about the token family (a chain of rotations back to the original grant) to detect when an already-invalidated token is presented again — the unambiguous signal of a copy in an attacker's hands racing the legitimate client. The live disagreement is over storage location on the client, specifically for browser-based apps: the security community is not unanimous, and OWASP's own guidance has shifted over time, but the current mainstream position is that `httpOnly`, `Secure`, `SameSite` cookies are the safer default for anything sensitive because they remove the token from JavaScript's reach entirely, closing the XSS-exfiltration path that `localStorage` leaves wide open — while acknowledging cookies reopen CSRF, which is a well-understood, well-mitigated problem (`SameSite` plus a synchronizer token) compared to XSS, which is much harder to fully close once it exists in an application.

**Where it's heading.** Sender-constrained tokens (DPoP, mTLS-bound refresh tokens) are the direction of travel for closing the residual gap that rotation-with-reuse-detection doesn't fully solve: reuse detection catches theft *after the fact*, once both the legitimate client and the attacker have raced to use the same token, but it doesn't prevent the theft itself or guarantee the attacker's request doesn't win that race and get served first. Binding the refresh token to a client-held key means a stolen token, lacking the key, simply can't be used at all — this is real, standardized (RFC 9449), and slowly moving from "advanced" to "recommended for high-sensitivity flows," but is not yet a universal default because of the client-side key-management complexity it demands. More speculative: some platforms are experimenting with continuous risk-based re-authentication (step-up triggered by anomaly signals rather than a fixed TTL) as a complement to fixed-TTL rotation, but this remains bespoke per-platform rather than a settled pattern.

---

## Mental model

```
  LOGIN
    │
    ▼
  ┌───────────────────────────────────────────────────────────┐
  │  Auth server issues:                                        │
  │    access_token  (JWT, 5-15 min TTL)  ── used on every API   │
  │    refresh_token (opaque, R1, DB row) ── used ONLY to refresh │
  └───────────────────────────────────────────────────────────┘
    │
    ▼  access_token expires after 10 min
  ┌───────────────────────────────────────────────────────────┐
  │  Client presents R1 to /token/refresh                        │
  │  Server: is R1 valid & un-rotated? YES                        │
  │    -> issue new access_token                                 │
  │    -> issue new refresh_token R2                              │
  │    -> mark R1 INVALID (rotated), remember R1->R2 lineage      │
  └───────────────────────────────────────────────────────────┘
    │
    ▼  ... time passes, client refreshes normally with R2, R3, R4 ...
  ┌───────────────────────────────────────────────────────────┐
  │  ATTACK: attacker stole R1 (logs, XSS, MITM) BEFORE it       │
  │  rotated, and now tries to use it — but it's already used     │
  │                                                                │
  │  Server: is R1 valid & un-rotated?  NO — R1 was already used  │
  │    to mint R2. This is REUSE of an invalidated token.          │
  │    -> THEFT SIGNAL. Revoke the ENTIRE family (R1..R4, all      │
  │       descendants), force full re-authentication.              │
  └───────────────────────────────────────────────────────────┘

  Rotation alone = hygiene (limits a leaked token's remaining life).
  Rotation + REUSE DETECTION = an actual theft alarm, not just hygiene.
```

---

## How it actually works

### Access vs refresh: two tokens, two jobs, two lifetimes

| Property | Access token | Refresh token |
|---|---|---|
| Format | Usually a JWT (self-contained, stateless verification) | Usually opaque (a random string, meaningless without a server-side lookup) |
| Lifetime | Minutes (5-15 typical; can be as short as 60s for high-sensitivity flows) | Days to weeks (30 days is a commonly cited OAuth guidance ceiling) |
| Where verified | Any resource server, locally, no lookup | Only the authorization server, via a DB lookup — by design, since it must be revocable |
| Sent on | Every API request | Only to the token endpoint, to get a new access token |
| Theft impact | Bounded by its own short TTL | Bounded by rotation + reuse detection, not by TTL alone |

The design logic: you want the *frequent*, *hot-path* operation (checking "is this request authorized") to be cheap and lookup-free, and you want the *infrequent* operation (getting a new access token) to be the one place you pay for a database round-trip — because that's also the one place you actually need server-side state to make revocation possible at all.

### Rotation, precisely

On every refresh request: validate the presented refresh token, issue a brand-new access token **and** a brand-new refresh token, and mark the presented refresh token as consumed/invalid in the same atomic operation. The client discards the old refresh token and stores only the new one. This means any single refresh token is usable exactly once for its intended purpose — using it a second time is, by construction, either a client bug (a race condition, a retry that fired twice) or theft.

```python
# untested sketch — illustrates the shape of rotation + reuse detection
import secrets, time

REFRESH_STORE = {}   # token -> {family_id, user_id, status, created_at}

def issue_initial_tokens(user_id: str) -> tuple[str, str]:
    family_id = secrets.token_urlsafe(16)
    refresh = secrets.token_urlsafe(32)
    REFRESH_STORE[refresh] = {
        "family_id": family_id, "user_id": user_id,
        "status": "active", "created_at": time.time(),
    }
    return create_access_token(user_id), refresh

def refresh_tokens(presented_refresh: str) -> tuple[str, str] | None:
    record = REFRESH_STORE.get(presented_refresh)
    if record is None:
        return None   # unknown token — reject, no family to revoke

    if record["status"] == "rotated":
        # REUSE of an already-rotated token: theft signal.
        # Revoke every token in this family, not just this one.
        revoke_family(record["family_id"])
        alert_security_team(record["user_id"], record["family_id"])
        return None

    # Legitimate, first-time use of this refresh token: rotate it.
    record["status"] = "rotated"
    new_refresh = secrets.token_urlsafe(32)
    REFRESH_STORE[new_refresh] = {
        "family_id": record["family_id"], "user_id": record["user_id"],
        "status": "active", "created_at": time.time(),
    }
    return create_access_token(record["user_id"]), new_refresh

def revoke_family(family_id: str) -> None:
    for token, record in REFRESH_STORE.items():
        if record["family_id"] == family_id:
            record["status"] = "revoked"   # nothing in this family works again
```

**Why revoke the whole family, not just the reused token?** Because reuse of an already-rotated token proves *someone else* has a copy of a token that should no longer exist — and since rotation means each token in the chain descends from the last, an attacker who captured an early token in the chain and is racing the legitimate client could be one or several rotations "behind" or "ahead." Revoking only the specific reused token leaves the rest of the family — potentially already compromised too — still valid. The family-wide revocation is the actual security payoff; without it, reuse detection just tells you theft happened after the fact with no containment action taken.

### The race condition rotation introduces, and how to handle it

A legitimate but imperfect client (a mobile app that retries a failed network request, a browser tab that fires two refresh calls in quick succession due to a race in its own token-refresh logic) can present the *same still-valid* refresh token twice in rapid succession, both before either response returns — this looks identical to theft at the server unless you build in a grace window. Production implementations commonly allow a short grace period (a few seconds) during which a just-rotated token is still accepted (returning the *same* new tokens already issued, rather than treating it as reuse), specifically to absorb this legitimate race without triggering a false-positive family revocation that would log a real, non-malicious user out unexpectedly. Tune this grace window narrowly — wide enough to survive one legitimate retry, narrow enough that it doesn't meaningfully weaken reuse detection's actual security value.

### Revocation lists vs short TTLs — when each is the right lever

- **Short access-token TTL** bounds exposure automatically, with zero additional infrastructure, but only after the fact — it doesn't stop misuse *during* the TTL window, it just limits how long that window is.
- **Revocation list** (a `jti` deny-list, or the refresh-token-family revocation above) gives you an immediate, deliberate stop button, at the cost of a lookup somewhere in the flow — the design question is *where* that lookup happens, and the answer that keeps most of JWT's latency benefit is "at refresh time only," not "on every access-token verification."

The number to hold in your head for the interview: **worst-case exposure after any revocation action equals the access-token TTL**, because that's the one artifact that can't itself be revoked mid-flight without paying the per-request lookup cost. If your access-token TTL is 10 minutes, that's your real number for "how long after we decide to cut someone off are they actually cut off," full stop, regardless of how fast your refresh-token revocation itself executes.

### TTL caching

JWKS caching (module 3) is the token-*verification* side of caching; the token-*lifecycle* side has its own caching concern: authorization servers issuing access tokens frequently cache the underlying authorization decision (the user's current roles/permissions) for the duration of the access-token TTL rather than re-querying a permissions database on every single token mint. This is a deliberate consistency/latency tradeoff — a permission change takes effect at the *next* token mint (bounded by the previous access token's remaining TTL plus however long the permission cache itself is held), not instantaneously. Teams sometimes get bitten by stacking these two staleness windows (a cached permission lookup *plus* a long access-token TTL) without realizing the two compound.

### Where to store tokens in a browser

| Storage | XSS exposure | CSRF exposure | Notes |
|---|---|---|---|
| `localStorage` | **Full** — any successful XSS can read and exfiltrate the token via `localStorage.getItem(...)` | None — not auto-sent by the browser | Simple to implement, which is exactly why it's over-recommended; OWASP explicitly advises against it for session-identifying tokens |
| Non-`httpOnly` cookie | Full — JS can read it just like `localStorage` | Yes — auto-sent on matching-origin requests | Gets the worst of both worlds; rarely the right choice |
| `httpOnly` + `Secure` + `SameSite` cookie | **None from JS directly** — but an XSS attacker can still ride the cookie to make authenticated requests *as the victim's browser*, just can't read/exfiltrate the raw token value | Yes, mitigated by `SameSite=Lax/Strict` and/or anti-CSRF tokens | The mainstream-recommended default for browser-based session/refresh tokens as of 2026 |
| In-memory (JS variable, not persisted) | Reduced — nothing to read from storage after page reload, but still readable if XSS executes while the variable is live in memory | None | Strong against exfiltration-after-the-fact, but tokens don't survive a page refresh, forcing a re-auth or silent-refresh-via-cookie flow anyway |

**The nuance interviewers want you to state precisely:** `httpOnly` cookies don't prevent an XSS attacker from *acting as the user* (they can still trigger authenticated requests through the victim's browser while the XSS payload runs), they prevent the attacker from **exfiltrating the raw token value** for later, offline, unlimited reuse. That's a real, meaningful reduction in blast radius (the attack is limited to the window the XSS payload is live and interacting, rather than a stolen token usable indefinitely from the attacker's own infrastructure), not a complete fix for XSS — XSS remains the more fundamental problem to close (module 8).

---

## Build it from scratch

Full rotation-with-reuse-detection and grace-window handling, combined with the access/refresh split from earlier in this module:

```python
# untested sketch, extends the pattern above with a grace window
import secrets, time

GRACE_SECONDS = 5

def refresh_tokens_with_grace(presented_refresh: str) -> tuple[str, str] | None:
    record = REFRESH_STORE.get(presented_refresh)
    if record is None:
        return None

    if record["status"] == "rotated":
        rotated_at = record.get("rotated_at", 0)
        if time.time() - rotated_at <= GRACE_SECONDS and "reissued_pair" in record:
            # Legitimate race: return the SAME pair already issued, don't
            # treat this as theft and don't mint yet another new pair.
            return record["reissued_pair"]
        # Outside the grace window: this is stale reuse. Theft signal.
        revoke_family(record["family_id"])
        alert_security_team(record["user_id"], record["family_id"])
        return None

    record["status"] = "rotated"
    record["rotated_at"] = time.time()
    new_access = create_access_token(record["user_id"])
    new_refresh = secrets.token_urlsafe(32)
    REFRESH_STORE[new_refresh] = {
        "family_id": record["family_id"], "user_id": record["user_id"],
        "status": "active", "created_at": time.time(),
    }
    record["reissued_pair"] = (new_access, new_refresh)
    return new_access, new_refresh
```

Full lab with Redis-backed refresh-token families, a working grace window, and a simulated theft scenario that triggers family revocation: **`labs/py/05-refresh-rotation/`**.

---

## How it's done in production

**Auth0 / Okta / Cognito** implement refresh-token rotation and reuse detection out of the box, with configurable grace periods and automatic family revocation on detected reuse — this is precisely the kind of security-critical, easy-to-get-subtly-wrong logic (race conditions, family lineage tracking) worth not reimplementing unless you have a specific reason to.

**Mobile-specific handling** — native mobile apps typically store refresh tokens in the OS-provided secure storage (iOS Keychain, Android Keystore), which is a materially different threat model than a browser: no XSS-equivalent JS-injection vector exists for a native app's own storage, so the browser storage debate above is largely moot for mobile, though the theft vectors shift to device compromise, malicious accessibility-service abuse on Android, or jailbreak/root-level access.

**Monitoring** — reuse-detection events (a family revoked due to detected reuse) should page or alert, not just log silently, since each one is a strong signal of active token theft in progress, not routine noise; teams that log-but-don't-alert on this specific event class are effectively collecting forensic evidence of a compromise after the fact rather than stopping it while it's happening.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Users randomly logged out on flaky mobile networks | No grace window; retried refresh requests treated as reuse/theft | Add a short (few-second) grace window returning the same reissued pair for a same-token retry |
| A stolen refresh token was used for days before detection | Rotation implemented without reuse detection — a copy simply worked indefinitely until its own long TTL | Add reuse detection: any presentation of an already-rotated token revokes the whole family and alerts |
| Security team disabled a compromised account but the attacker stayed active for several more minutes | Correct behavior, not a bug — this is the bounded exposure window equal to the access-token TTL | Shorten access-token TTL for high-sensitivity scopes if that residual window is unacceptable |
| Permission change took 20+ minutes to take effect despite a 5-minute access-token TTL | Stacked staleness: a cached permission lookup at token-mint time plus the access-token TTL itself compound | Reduce permission-cache TTL, or invalidate the cache explicitly on permission changes rather than relying purely on time-based expiry |
| XSS payload successfully performed authenticated actions despite tokens being in httpOnly cookies | Correct, expected limitation — httpOnly blocks exfiltration, not in-session abuse by a live XSS payload | Close the XSS vulnerability itself (module 8, CSP) — token storage choice was never going to fully mitigate this |
| localStorage-stored token appeared in an attacker's exfiltration dump from an unrelated XSS finding | Sensitive token stored somewhere fully JS-readable | Migrate to httpOnly cookie storage for the refresh token at minimum |

---

## Tradeoffs & when NOT to use it

- **Don't implement rotation without reuse detection** — rotation alone (issue a new token, invalidate the old one) provides essentially no security benefit against a copied token if nothing ever checks whether an invalidated token gets presented again; it's rotation's *detection* half that does the actual work.
- **Don't set the reuse-detection grace window too wide.** A multi-minute grace window to be "safe" against retries defeats much of the point — an attacker racing a legitimate client within that window is indistinguishable from a legitimate retry, and you've effectively disabled detection for that entire window.
- **Don't use `localStorage` for anything you'd call a security token** if your application has any user-generated content, third-party scripts, or a non-trivial JS dependency tree — which describes almost every modern web app — since that's exactly the surface XSS uses, and `localStorage` gives a successful XSS payload trivial, silent, exfiltratable access.
- **Don't assume `httpOnly` cookies fully solve XSS** — they solve *exfiltration*, not *abuse-during-execution*. If your threat model includes "an XSS payload could perform actions as the user while it's running," cookie storage doesn't fix that; only closing the XSS vulnerability does.
- **For native mobile apps, the browser storage debate mostly doesn't apply** — use the platform's secure storage (Keychain/Keystore) and worry instead about device-compromise-specific threats, which are a different problem with different mitigations (biometric-gated key access, attestation).
- **Aggressive family-wide revocation on reuse detection has a real user-experience cost** — a legitimate but buggy client (a bug causing a genuine double-refresh outside your grace window) gets logged out entirely, not just the one request rejected. This is usually the correct tradeoff for a security control, but it's worth stating explicitly rather than treating it as free.

---

## Interview questions

### Q1 — Why do refresh tokens exist at all, given that a system could just issue long-lived access tokens directly?
**Testing:** whether they understand the split as intentional, not incidental.
**Answer:** Splitting the tokens lets the frequent, hot-path operation (access-token verification, happening on every request) stay stateless and lookup-free, while concentrating the one place you actually need server-side state — and therefore the one place revocation is possible — into the infrequent refresh operation. A single long-lived access token would need either no revocation lever at all, or a per-request lookup that defeats the point of using a stateless token in the first place.
**Follow-up trap:** *"So why not just make access tokens short and skip refresh tokens, forcing re-login every 10 minutes?"* — that pushes the UX cost onto the user (re-entering credentials constantly) instead of onto the system; refresh tokens let re-authentication happen silently in the background as long as the refresh token itself remains valid and un-revoked, which is the actual point.

### Q2 — What does refresh token "rotation" mean precisely, and why isn't rotation alone sufficient security?
**Testing:** the rotation/detection distinction, the heart of this module.
**Answer:** Rotation means every refresh both mints a new refresh token and invalidates the one just presented, limiting how many times a given token string can ever be used to exactly one. But rotation alone doesn't detect theft — if an attacker has a copy and uses it *before* the legitimate client does, the attacker simply gets the next valid token in the chain, and the legitimate client's subsequent attempt is what fails (looking to the system exactly like the attacker was the real client). Rotation without reuse detection just relocates the theft window, it doesn't close it.
**Follow-up trap:** *"So who actually gets locked out in that race — the attacker or the legitimate user?"* — whichever party's refresh request the server processes second gets rejected, since the first one to arrive "legitimately" rotates the token and invalidates it for the other; this is exactly why reuse detection (revoking the whole family when an already-rotated token reappears) matters — without it, the *legitimate user* could be the one who ends up locked out while the attacker keeps the valid chain.

### Q3 — Walk through reuse detection and why the correct response is revoking the entire token family, not just the specific reused token.
**Testing:** the security reasoning behind family-wide revocation specifically.
**Answer:** If an already-rotated (invalidated) refresh token is presented again, that's proof a copy exists somewhere it shouldn't — since the legitimate flow only ever uses each token once. Because every subsequent token in the chain descends from that same original grant, you can't be certain which specific token in the family the attacker currently holds or has already used, so revoking only the one flagged token leaves the rest of a potentially fully-compromised chain still valid. Revoking the whole family and forcing a fresh login is the only response that actually contains the incident rather than just detecting it.
**Follow-up trap:** *"Isn't this overkill if it turns out to be a legitimate client bug, not theft?"* — this is exactly why a grace window exists for legitimate near-simultaneous retries (network flakiness, a race in client-side refresh logic); outside that narrow window, treating reuse as theft and accepting the resulting re-login cost for the legitimate user is the correct, deliberate tradeoff — false positives here are much cheaper than false negatives.

### Q4 — Your mobile app's refresh flow occasionally logs users out on flaky networks, and your security team says it's because of "rotation." Diagnose and fix it.
**Testing:** practical judgment about the race condition rotation introduces.
**Answer:** A retried request (the client resending a refresh call after a timeout, without realizing the first one actually succeeded server-side) presents the same, now-already-rotated token a second time, which without a grace window is indistinguishable from theft and triggers family revocation, logging the legitimate user out. The fix is a short grace window (a few seconds) during which a just-rotated token, if presented again, returns the *same* already-issued new pair rather than treating it as reuse.
**Follow-up trap:** *"What's the security cost of adding that grace window?"* — it creates a real, bounded window (matching the grace period) during which an attacker racing the legitimate client within that same few seconds would also be treated as a legitimate retry rather than flagged as theft — a genuine, quantifiable tradeoff between false-positive user friction and detection sensitivity, not a free fix.

### Q5 — What's the actual worst-case exposure window after your security team decides to cut off a compromised account, in a system using the access/refresh hybrid? Give a number.
**Testing:** whether they can quantify this precisely rather than gesture at "it's fast."
**Answer:** Exactly the access token's TTL — revoking the refresh token stops new access tokens from being minted immediately, but any access token already issued and not yet expired keeps working until its own `exp`, regardless of the revocation action. If the access-token TTL is 10 minutes, that's the real number, full stop; it does not matter how quickly the refresh-token revocation itself executes.
**Follow-up trap:** *"How would you get that number down to zero for one specific, extremely sensitive endpoint?"* — you'd need either a `jti` deny-list checked specifically on that endpoint (reintroducing a lookup, but scoped narrowly rather than universally) or a sender-constrained token (DPoP/mTLS) combined with a way to revoke the client's key itself — there's no way to make a pure bearer JWT's remaining validity zero without one of those two additions.

### Q6 — A colleague proposes storing the refresh token in `localStorage` "because it's simpler than dealing with cookie flags." What's your response?
**Testing:** whether the storage debate is understood precisely, not just "cookies are safer" folklore.
**Answer:** `localStorage` is fully readable by any JavaScript running on the page, so a single successful XSS vulnerability anywhere in the application's dependency tree (a compromised third-party script, a stored-XSS in user content) can exfiltrate the token wholesale for offline, unlimited, indefinite reuse from the attacker's own infrastructure. An `httpOnly` cookie removes that specific exfiltration path — JS simply cannot read the token value — at the cost of reopening CSRF, which is well-understood and cleanly mitigated with `SameSite` plus an anti-CSRF token. The complexity tradeoff favors cookies for anything actually sensitive.
**Follow-up trap:** *"Does httpOnly fully solve the XSS problem then?"* — no; an XSS payload executing live in the page can still ride the `httpOnly` cookie to make authenticated requests *as the user* while it's running, it just can't copy the raw token value for later, separate reuse. This limits blast radius (bounded to the XSS payload's active execution window) but doesn't replace actually closing the XSS vulnerability.

### Q7 — Design the token lifecycle for a system where a compliance requirement states permission changes must take effect within 60 seconds.
**Testing:** connecting TTL caching (the token-lifecycle side, not JWKS) to a concrete constraint.
**Answer:** Access-token TTL must be ≤60 seconds for this to hold purely through natural expiry — likely too aggressive for most systems' refresh-request volume — so the more practical answer is decoupling authorization *state* from the token's TTL: cache the underlying permission lookup with a TTL matched to the 60-second requirement (or invalidate it explicitly on permission-change events via a pub/sub signal) independent of how long the *access token itself* remains valid, and re-check current permissions server-side at the point of the sensitive action rather than trusting a role claim embedded in the token (echoing module 1's authn/authz separation).
**Follow-up trap:** *"Doesn't re-checking permissions server-side on every sensitive action bring back a lookup you were trying to avoid?"* — yes, deliberately, and that's the correct answer for whatever specific actions the compliance requirement actually covers (likely a narrow set of sensitive operations, not every single API call) — this is the same targeted-exception pattern as a `jti` deny-list: pay the lookup cost only where the requirement demands it, not universally.

### Q8 — What does DPoP add to the access/refresh rotation model that reuse detection alone doesn't achieve?
**Testing:** whether they see reuse detection as after-the-fact and DPoP as preventive.
**Answer:** Reuse detection is a detective control — it identifies theft only once both the legitimate client and the attacker have raced to use the same token, and whichever one loses that race gets flagged (potentially the legitimate user, as covered in Q2). DPoP is a preventive control: the token is cryptographically bound to a client-held private key via a signed proof sent with each request, so a stolen token — without the corresponding key, which never leaves the legitimate client — simply cannot be used by an attacker at all, regardless of any race condition.
**Follow-up trap:** *"If DPoP prevents theft-based misuse entirely, why isn't it universal?"* — client-side key generation, secure storage, and per-request proof signing add real implementation complexity and a small latency/compute cost, and not every client platform or SDK has mature, well-tested support yet — a genuine adoption-friction reason, not a security objection, which is why it's currently reserved for high-sensitivity flows rather than deployed as a blanket default.

### Q9 — A security review flags that your system's refresh tokens have a 90-day TTL with no rotation at all. How do you prioritize the fix?
**Testing:** practical remediation sequencing under real constraints.
**Answer:** Add rotation with reuse detection first — this is the highest-value, most self-contained fix, since it converts an indefinitely-reusable 90-day credential (if ever leaked) into one usable at most once per legitimate refresh cycle, with theft actively detected rather than silently persisting for up to 90 days. Shortening the 90-day ceiling itself is a secondary, complementary improvement (reduces the *maximum* blast radius if a currently-active, un-rotated token is stolen right before the fix ships) but rotation-plus-detection is the change that actually closes the "stolen token works indefinitely and undetected" gap.
**Follow-up trap:** *"What do you do about tokens issued before the fix ships, under the old no-rotation regime?"* — they should be treated as a known gap during the transition: either force a re-login for all active sessions at deploy time (a one-time UX cost, deliberately paid to close the gap immediately) or accept that any token issued before the fix retains its full original blast radius until it naturally expires under the old TTL — a tradeoff worth stating explicitly to whoever owns the security decision, not silently absorbed.

### Q10 — Compare the residual risk profile of (a) short access-token TTL with no refresh-token rotation, versus (b) longer access-token TTL with full rotation and reuse detection. Which would you choose and why?
**Testing:** staff-level synthesis across the whole module, not just recall of individual pieces.
**Answer:** (a) bounds each individual access token's blast radius tightly but does nothing about a stolen *refresh* token, which — with no rotation — remains valid and reusable for its entire long lifetime with zero detection; a single refresh-token leak in this design is a standing, silent risk for weeks. (b) accepts a slightly longer access-token exposure window per compromise event but converts refresh-token theft from "silent and long-lived" into "detected on next use, contained via family revocation" — a categorically better outcome for the higher-value target (the refresh token), since access-token exposure is already bounded and refresh-token exposure is the larger, less-bounded risk in design (a). Choose (b): rotation-plus-detection addresses the more consequential and more silent failure mode.
**Follow-up trap:** *"Could you combine both — short access TTL AND full rotation — and is there a reason not to?"* — yes, and this is simply the module's baseline hybrid recommendation, not a novel combination; the only real reason to avoid very short access-token TTLs is refresh-request volume and the resulting load on the authorization server, which is a capacity-planning question, not a security objection, and is usually a solvable, bounded cost.

---

## Red flags that fail you

- Describing "rotation" without mentioning reuse detection, or treating the two as interchangeable.
- Not being able to state the worst-case exposure window after a revocation decision as a concrete number tied to access-token TTL.
- Recommending `localStorage` for refresh/session tokens without acknowledging the XSS-exfiltration tradeoff explicitly.
- Claiming `httpOnly` cookies fully solve XSS rather than specifically closing the exfiltration path.
- Proposing a very wide reuse-detection grace window "to avoid false positives" without recognizing it weakens detection proportionally.
- Treating refresh-token rotation as unnecessary because "access tokens are already short-lived."

---

## Cheat card

```
ACCESS TOKEN   JWT, 5-15 min TTL, stateless verify, used on EVERY request
REFRESH TOKEN  opaque, DB-tracked, days-weeks TTL, used ONLY to mint new access tokens

ROTATION        every refresh: invalidate presented token, issue new one
REUSE DETECTION presenting an ALREADY-rotated token = theft signal
                -> revoke ENTIRE token family, force re-login, alert security team
                ROTATION ALONE (no reuse detection) = hygiene only, doesn't stop theft

RACE CONDITION: legit client retry can present same token twice -> false theft flag
  FIX: short grace window (few sec) returns SAME reissued pair on retry within window
       grace window too wide = weakens detection; too narrow = false logouts on flaky nets

WORST-CASE EXPOSURE after ANY revocation decision = access-token TTL. Always. No exceptions
  (refresh-token revocation stops NEW access tokens, doesn't touch already-issued ones)

TTL CACHING: permission lookups cached at token-mint time for the access-token TTL duration
  STACKED STALENESS = cached-permission-TTL + access-token-TTL can compound silently

BROWSER STORAGE:
  localStorage        -> full XSS exfil risk, zero CSRF risk. OWASP: avoid for sensitive tokens
  httpOnly cookie      -> XSS can still ACT as user live, but CANNOT exfiltrate raw token value
                          reopens CSRF -> mitigate w/ SameSite + anti-CSRF token
                          MAINSTREAM DEFAULT for browser session/refresh tokens in 2026
  native mobile        -> use Keychain (iOS) / Keystore (Android); browser debate doesn't apply

DPoP (RFC 9449): PREVENTIVE (binds token to client key, stolen token unusable w/o key)
  vs reuse detection: DETECTIVE (catches theft only after a race between legit client + attacker)
```

## Sources

- [Refresh Token Security: Best Practices for OAuth Token Protection — Obsidian Security](https://www.obsidiansecurity.com/blog/refresh-token-security-best-practices) — accessed 2026-07-26
- [Refresh Token Rotation — Auth0 Docs](https://auth0.com/docs/secure/tokens/refresh-tokens/refresh-token-rotation) — accessed 2026-07-26
- [If your refresh token gets stolen, rotation alone won't save you](https://dev.to/kiwidevelopment/if-your-refresh-token-gets-stolen-rotation-alone-wont-save-you-heres-what-does-1f7n) — accessed 2026-07-26
- [Token Lifetime Best Practices: Access, Refresh, ID, and Session Tokens in 2026](https://guptadeepak.com/ciam-compass/guides/token-lifetime-best-practices/) — accessed 2026-07-26
- [RFC 9449 — OAuth 2.0 Demonstrating Proof of Possession (DPoP)](https://www.rfc-editor.org/rfc/rfc9449) — accessed 2026-07-26
- [OWASP — HTML5 Security Cheat Sheet (localStorage guidance)](https://cheatsheetseries.owasp.org/cheatsheets/HTML5_Security_Cheat_Sheet.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
