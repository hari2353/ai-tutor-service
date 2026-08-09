# JWT Deep: Header/Payload/Signature, HS vs RS vs ES, JWKS, kid, Claims, Clock Skew

> **Track:** T30 Auth & Application Security · **Time:** 3h · **Prereqs:** `T30-sessions-vs-tokens`
> **Updated:** 2026-07-26
> **Module id:** `T30-jwt-deep` · **Tags:** jwt, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A JWT is three base64url segments joined by dots — header, payload, signature — where the header and payload are just JSON you can read with `base64 -d`, and the signature is the only part that provides any security guarantee, computed over the first two segments with an algorithm named in the header itself. HS256 uses one shared secret for both signing and verifying (fast, but every verifier must hold the same secret, so a leak anywhere is a total forge); RS256/ES256 use asymmetric keypairs, so verifiers only need the public key and can never forge a token, at the cost of larger tokens (RS256) or more complex tooling (ES256's smaller signatures but less universal library support). JWKS (`/.well-known/jwks.json`) is how verifiers fetch public keys dynamically, keyed by `kid` in the header, which is what makes key rotation possible without redeploying every verifier — and it's also the header field most commonly turned into an attack vector, covered in the next module. None of this matters if you don't validate `exp`, `aud`, and `iss`, with a `leeway` of 30-120 seconds to survive clock skew between servers, because unvalidated claims are the difference between a signed token and a security control.

## Why this gets asked

Because JWT is the technology everyone has used and almost nobody has actually decoded by hand or reasoned about algorithm choice for. The interviewer wants proof you understand JWT as a signed data structure with a specific trust model — not a magic string a library produces — because that understanding is exactly what prevents the algorithm-confusion and `alg=none` vulnerabilities covered in the next module. They've likely fixed a bug caused by someone treating an unverified claim (a `role` field trusted before signature validation, or a missing `aud` check that let a token issued for one service authenticate against another) as gospel.

---

## Lineage: past → present → future

**What came before.** Before JWT, cross-service and cross-domain authentication mostly meant SAML (2002), an XML-based assertion format that is cryptographically sound but verbose, slow to parse, and awkward for anything outside browser-based enterprise SSO — a SAML assertion routinely runs several KB and requires XML canonicalization (a documented CPU cost, and itself a historical source of signature-wrapping vulnerabilities where an attacker adds unsigned XML nodes the parser incorrectly trusts). The pain SAML caused for the emerging mobile/API/microservices world was concrete: XML tooling is heavy on mobile clients, XML canonicalization bugs were a real attack surface, and there was no lightweight, JSON-native equivalent for the growing OAuth ecosystem. JSON Web Signature (JWS, RFC 7515) and JSON Web Token (JWT, RFC 7519) were standardized in 2015 specifically to give OAuth 2.0 a compact, URL-safe, JSON-native token format that a mobile app or a JavaScript client could parse trivially.

**Where it stands now.** JWT is the de facto standard bearer token format across OAuth 2.0/OIDC, but the live disagreement is entirely about algorithm and validation discipline, not the format itself: RS256 remains the most widely deployed asymmetric choice because of universal library support and because it lets you publish a public key via JWKS without exposing anything that can sign, while ES256 (ECDSA over P-256) produces meaningfully smaller signatures (~64 bytes vs RS256's ~256-384 bytes) for the same security margin and is gaining ground in size-sensitive contexts (mobile headers, high-QPS APIs), but has historically had thinner library support and a documented history of implementation bugs (weak or reused nonces in signing, distinct from the algorithm itself, most infamously the 2010 Sony PS3 ECDSA key-recovery incident from nonce reuse — a lesson in library trustworthiness, not ECDSA's math). The near-universal current consensus, hardened by a steady stream of real vulnerabilities, is that verifiers must pin an explicit algorithm allowlist rather than trusting the `alg` field in the token header — this is covered in depth in module 4, but it's worth naming here because it changes how you should read the "structure" of a JWT: the header is attacker-controlled input, not metadata to trust.

**Where it's heading.** JWKS-based key rotation with short-lived signing keys (rotating every few weeks to months, keeping the previous key valid for verification during a transition window) is standard practice now rather than an advanced pattern, and libraries increasingly default to requiring explicit algorithm specification rather than reading it from the token (a direct response to the alg-confusion CVE history). More speculative: some organizations are exploring token binding / DPoP (Demonstrating Proof of Possession, RFC 9449) to cryptographically tie a token to the specific client that requested it, so a stolen bearer token alone isn't sufficient to replay it elsewhere — this closes a real gap (bearer tokens are usable by whoever holds them, full stop) but adds client-side key management complexity that has slowed adoption; treat DPoP as a direction of travel for high-sensitivity APIs, not yet a universal default.

---

## Mental model

```
   eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImFiYzEyMyJ9
   .
   eyJzdWIiOiJ1c2VyXzQyIiwiZXhwIjoxNzUzNTAwMDAwLCJhdWQiOiJhcGkuZXhhbXBsZS5jb20ifQ
   .
   VGhpcyBpc24ndCByZWFsIGJhc2U2NHVybCBidXQgeW91IGdldCB0aGUgaWRlYQ

   └──────────── HEADER ────────────┘ └────────── PAYLOAD ──────────┘ └── SIGNATURE ──┘
   base64url(JSON)                    base64url(JSON)                  base64url(bytes)
   {alg, typ, kid}                     {sub, exp, iss, aud, ...}        HMAC/RSA/ECDSA over
                                                                        "header.payload"

   ATTACKER CAN READ AND EDIT     ATTACKER CAN READ AND EDIT      ONLY THIS SEGMENT PROVIDES
   both of these freely --        both of these freely --        ANY SECURITY GUARANTEE.
   base64url is ENCODING,         base64url is ENCODING,         If you don't verify it, or
   not encryption. Never put      not encryption. Never trust    verify it wrong (module 4),
   secrets in header/payload.     ANY claim before verifying     everything above is just
                                  the signature.                 attacker-supplied JSON.
```

The critical mental shift: **a JWT is not "secure" because it's a JWT.** It's secure only to the extent the signature is (a) actually verified, (b) verified with an algorithm the server chose, not one the attacker's token header suggests, and (c) verified against the *right* key. Everything else — header, payload, the whole visual "this looks like a real token" impression — is just JSON an attacker can produce identically.

---

## How it actually works

### Base64url, precisely

JWT uses base64**url** encoding (RFC 4648 §5), not standard base64: `+` becomes `-`, `/` becomes `_`, and trailing `=` padding is stripped. This matters practically because standard base64 output isn't URL-safe (`+` and `/` have special meaning in URLs and would need percent-encoding), and JWTs are routinely passed as URL query parameters or HTTP headers where that would be awkward. Decoding by hand:

```bash
# Take the header segment, restore padding, decode
echo "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCIsImtpZCI6ImFiYzEyMyJ9" | base64 -d
# {"alg":"RS256","typ":"JWT","kid":"abc123"}

# Real decode of a token produced by python-jose with RS256:
python3 -c "
import jwt, json
token = jwt.encode({'sub':'user_42','exp':1753500000,'aud':'api.example.com','iss':'https://auth.example.com'},
                    open('private.pem').read(), algorithm='RS256', headers={'kid':'abc123'})
print(token)
header, payload, sig = token.split('.')
import base64
def b64d(s):
    s += '=' * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)
print(json.loads(b64d(header)))   # {'alg': 'RS256', 'typ': 'JWT', 'kid': 'abc123'}
print(json.loads(b64d(payload)))  # {'sub': 'user_42', 'exp': 1753500000, 'aud': 'api.example.com', 'iss': 'https://auth.example.com'}
print(len(sig))                   # RS256 signature ~342 base64url chars (~256 raw bytes for RSA-2048)
"
```

Any tool that base64url-decodes text — `jwt.io`, `python -m base64`, a one-liner — reveals header and payload with zero secret knowledge. This is why the signature, not obscurity, is the entire security boundary.

### Algorithm choice: HS256 vs RS256 vs ES256

| Algorithm | Type | Key material | Signature size | When it's right |
|---|---|---|---|---|
| **HS256** (HMAC-SHA256) | Symmetric | One shared secret, used to both sign and verify | ~43 base64url chars (32 raw bytes) | Single service issues and verifies its own tokens — no other party ever needs to verify. Simple, fast (~microseconds). Wrong the moment a second, less-trusted party needs to verify, because verifying requires the same secret that can also forge. |
| **RS256** (RSA-SHA256) | Asymmetric | Private key signs, public key verifies | ~342 base64url chars (256 bytes @ RSA-2048) | Multiple independent verifiers (microservices, third-party APIs) need to check tokens but must never be able to forge one. Publish the public key via JWKS; only the issuer holds the private key. Most widely supported, safe default. |
| **ES256** (ECDSA P-256-SHA256) | Asymmetric | Private key signs, public key verifies | ~86 base64url chars (64 bytes) | Same trust model as RS256, ~4x smaller signature, meaningfully cheaper on mobile/high-QPS/bandwidth-constrained contexts. Requires a correct, constant-time ECDSA implementation — a documented historical source of nonce-reuse key-recovery bugs when implemented carelessly (Sony's 2010 PS3 signing key leak from a static, reused nonce is the canonical cautionary tale, though not a JWT-specific incident). |

**The rule that actually matters:** if more than one party needs to *verify* but should never be able to *forge*, you need asymmetric (RS256/ES256), full stop. Using HS256 across a multi-service architecture where every service holds the same shared secret means any one compromised service (or any developer with read access to its config) can mint tokens claiming to be any user for every other service. This is a real, recurring production mistake, not a theoretical one.

### JWKS and `kid`: rotating keys without redeploying verifiers

A JSON Web Key Set (JWKS, RFC 7517) is a JSON document — conventionally served at `/.well-known/jwks.json` — listing the issuer's current public keys:

```json
{
  "keys": [
    {"kty": "RSA", "kid": "abc123", "use": "sig", "alg": "RS256", "n": "<modulus>", "e": "AQAB"},
    {"kty": "RSA", "kid": "def456", "use": "sig", "alg": "RS256", "n": "<modulus>", "e": "AQAB"}
  ]
}
```

The token header's `kid` field tells the verifier *which* key in the set to use. Rotation workflow: the issuer generates a new keypair, adds the new public key to the JWKS (now serving two keys), starts signing new tokens with the new key's `kid`, and after the old key's maximum token lifetime has elapsed with no outstanding tokens signed by it, removes the old key from the JWKS. Verifiers never need a code change or redeploy — they fetch (and cache, typically for minutes to an hour) the JWKS and look up whichever `kid` the token claims.

**The trap, previewed for module 4:** if the verifier trusts `kid` to mean "fetch whatever URL/file this string points to" rather than "look up this exact key ID in our known, pinned JWKS," an attacker who controls the `kid` value can redirect key lookup to a file they control (path traversal) or a URL they control (SSRF), and the verifier ends up "verifying" the attacker's token against the attacker's own key. `kid` must be treated as an index into a fixed, trusted set — never as a path or URL to fetch.

### Standard claims, and what each actually gates

| Claim | Name | What it gates |
|---|---|---|
| `iss` | Issuer | Which authority minted this token. Must be checked against an expected value — otherwise a token from a *different, legitimately-configured* issuer (e.g., a different tenant in a multi-tenant IdP) verifies successfully but was never meant for you. |
| `sub` | Subject | The identity the token asserts. This is your `user_id` equivalent — the thing the rest of your authorization logic keys off of. |
| `aud` | Audience | Which service(s) this token is valid for. Must be checked — a token minted for `service-a` presented to `service-b` should be rejected even if the signature is perfectly valid, because a valid signature only proves who issued it, not who it's for. |
| `exp` | Expiration | Unix timestamp after which the token is invalid. Non-negotiable to check; several early library defaults did not check this automatically, and CVE history includes libraries that silently accepted expired tokens. |
| `nbf` | Not Before | Token isn't valid until this timestamp — useful for pre-issued, future-activating tokens. |
| `iat` | Issued At | When the token was minted — useful for auditing and for maximum-age policies independent of `exp`. |
| `jti` | JWT ID | Unique token identifier — the hook you need if you ever want a revocation deny-list (module 5) or replay detection, since otherwise there's no stable ID to check against a blocklist. |

### Clock skew and `leeway`

Distributed systems don't share a perfectly synchronized clock — NTP drift of a few seconds is normal, and a few minutes is not unheard of on misconfigured hosts. If server A mints a token with `exp = now + 900` using its clock, and server B (verifying) is 90 seconds ahead due to drift, a token minted 14 minutes ago on A might appear already-expired on B's clock even though it's well within its intended TTL. The fix is a `leeway` (also called clock-skew tolerance) — most JWT libraries accept a parameter (`jwt.decode(..., leeway=60)`) that extends the effective validity window by that many seconds in both directions for `exp` and `nbf` checks. **30-60 seconds is a reasonable default; 120 seconds is generous; anything beyond a few minutes starts meaningfully widening your actual exposure window if a token needs to be treated as expired for a security reason.**

### Size limits

JWTs are sent as HTTP headers (`Authorization: Bearer <token>`) or cookies, both of which have practical size ceilings: most web servers and load balancers cap total header size around 8KB (nginx default `large_client_header_buffers 4 8k`; many CDNs and load balancers cap individual headers around 4-16KB), and browsers cap total cookie size per-domain around 4KB. A JWT with a handful of standard claims plus a `kid` runs a few hundred bytes; a JWT with an embedded permission list, group memberships, or a full user profile can balloon into multiple kilobytes and start colliding with these limits — this is a concrete, observable failure mode (`431 Request Header Fields Too Large`), not a theoretical concern, and it's one more reason (alongside staleness, covered in module 2) to keep claims minimal.

---

## Build it from scratch

A JWT is HMAC (or RSA/ECDSA) over two base64url-encoded JSON blobs — enough that you can build the HS256 path from primitives to demystify it entirely:

```python
import hmac, hashlib, json, base64, time

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

def b64url_decode(s: str) -> bytes:
    s += "=" * (-len(s) % 4)
    return base64.urlsafe_b64decode(s)

def create_jwt_hs256(payload: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = b64url_encode(json.dumps(header, separators=(",", ":")).encode())
    payload_b64 = b64url_encode(json.dumps(payload, separators=(",", ":")).encode())
    signing_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    sig_b64 = b64url_encode(signature)
    return f"{header_b64}.{payload_b64}.{sig_b64}"

def verify_jwt_hs256(token: str, secret: str, *, audience: str, issuer: str, leeway: int = 60) -> dict:
    header_b64, payload_b64, sig_b64 = token.split(".")

    # Recompute signature over exactly what was signed — never trust the token's own claim
    signing_input = f"{header_b64}.{payload_b64}".encode()
    expected_sig = hmac.new(secret.encode(), signing_input, hashlib.sha256).digest()
    actual_sig = b64url_decode(sig_b64)
    if not hmac.compare_digest(expected_sig, actual_sig):   # constant-time compare, module 11
        raise ValueError("bad signature")

    header = json.loads(b64url_decode(header_b64))
    if header.get("alg") != "HS256":                        # pin the algorithm — never read it blindly
        raise ValueError("unexpected alg")

    payload = json.loads(b64url_decode(payload_b64))
    now = time.time()
    if payload.get("exp", 0) < now - leeway:
        raise ValueError("expired")
    if payload.get("aud") != audience:
        raise ValueError("wrong audience")
    if payload.get("iss") != issuer:
        raise ValueError("wrong issuer")
    return payload

# Round trip
secret = "demo-secret-32-bytes-minimum!!!"
token = create_jwt_hs256(
    {"sub": "user_42", "iss": "https://auth.example.com", "aud": "api.example.com",
     "iat": int(time.time()), "exp": int(time.time()) + 900},
    secret,
)
print(token)
print(verify_jwt_hs256(token, secret, audience="api.example.com", issuer="https://auth.example.com"))
```

This demystifies the two most misunderstood things in one pass: header/payload are plain JSON round-tripped through an encoding, not a cipher, and verification is "recompute the signature yourself and compare, then separately check each claim" — never "ask the token what algorithm to use" (that's the vulnerability the next module is entirely about). RS256/ES256 versions using `cryptography`'s RSA/EC primitives, plus a working JWKS endpoint and `kid`-based rotation: **`labs/py/03-jwt-from-scratch/`**.

---

## How it's done in production

**Libraries** — `PyJWT` / `python-jose` (Python), `jsonwebtoken` (Node — note the historical CVEs in early versions around algorithm confusion, fixed by requiring explicit `algorithms` arrays), `jjwt` (Java), `golang-jwt/jwt` (Go). All current-generation libraries require you to pass an explicit allowed-algorithms list to `decode`/`verify` rather than reading `alg` from the token, specifically because of the CVE history.

**JWKS serving and caching** — issuers publish JWKS at a well-known URL; verifiers fetch and cache it (typical TTL: minutes to an hour) rather than fetching on every verification, to avoid a network round-trip on the hot path — this is the same latency argument module 2 makes for JWTs generally, and losing it by re-fetching per-request defeats much of the point. Most OIDC libraries (e.g., Auth0's, Okta's SDKs) handle this caching automatically, including respecting `Cache-Control` headers on the JWKS response and gracefully handling key rotation by re-fetching on a `kid` cache-miss rather than failing immediately.

**Key rotation cadence** — commonly every 90 days to a year for signing keys in mature setups, with a documented overlap window (old key stays in the JWKS, valid for verification, for at least the maximum token lifetime past rotation) so in-flight tokens don't suddenly fail. Rotating without an overlap window is a common outage cause: every token signed with the retired key starts failing verification the instant it's removed from the JWKS, which shows up as a spike in 401s correlated exactly with a key-rotation deploy.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Spike in 401s exactly after a scheduled key rotation | Old key removed from JWKS before all tokens signed with it expired | Keep retired keys in the JWKS for at least one full token-lifetime past rotation |
| Tokens intermittently rejected as "expired" seconds after issuance, only on certain hosts | Clock skew between issuing and verifying hosts, no leeway configured | Add 30-60s `leeway`; also fix NTP sync as the root cause, don't just paper over it |
| `431 Request Header Fields Too Large` under normal traffic | JWT bloated with embedded permission lists / profile data | Trim claims to `sub`, `exp`, a few coarse flags; look up detail server-side |
| Token from tenant B accepted by tenant A's service | Missing or incorrect `iss`/`aud` validation | Explicitly check both against expected values, not just "signature is valid" |
| Verifier throws on a well-formed token from a legitimate but newly-rotated key | JWKS cache not refreshed on `kid` cache-miss | Implement fallback: on unknown `kid`, force a JWKS refetch once before rejecting |
| A stolen bearer token works from any device/location with no additional friction | Bearer tokens are inherently usable by whoever holds them; no possession-binding | Consider DPoP (RFC 9449) for high-sensitivity APIs — binds the token to a client-held key |

---

## Tradeoffs & when NOT to use it

- **Don't use HS256 across a multi-service architecture with different trust levels.** If service B only needs to *verify* tokens issued by service A and should never mint its own, giving B the HS256 shared secret means B (or anything that compromises B) can now forge tokens as any user for the entire system. Use RS256/ES256 so verification and signing require different key material.
- **Don't skip `aud`/`iss` validation "because the signature already proves it's legitimate."** A signature proves who signed it, not who it's for — a token legitimately issued for a low-privilege internal tool, if `aud` isn't checked, can be replayed against a higher-privilege service that shares the same issuer.
- **Don't over-embed claims to avoid a database call.** Beyond the staleness problem (module 2), you risk real header-size failures under normal traffic, not just theoretical bloat.
- **Don't treat JWKS as static.** A verifier that fetches the JWKS once at startup and never refreshes it will fail every verification after the next key rotation; cache with a TTL and a fallback refetch on `kid` miss.
- **ES256 isn't automatically better than RS256** despite the smaller signature — verify your entire toolchain (client libraries, API gateways, any intermediary that parses tokens) actually supports ES256 correctly before switching; some older or embedded tooling only supports RS256, and a partially-supported ES256 rollout is worse than a working RS256 one.
- **For a single-service, single-verifier system with no plans for other consumers, HS256 is genuinely fine** — the asymmetric-key ceremony (JWKS hosting, rotation tooling) is real operational overhead that buys you nothing if there's only ever one party that could misuse a shared secret, because that one party already has full trust.

---

## Interview questions

### Q1 — Decode this JWT header for me without any tooling: `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9`.
**Testing:** whether they understand base64url is encoding, not encryption, and can do it by hand.
**Answer:** Restore padding to a multiple of 4 characters (`==` here), base64-decode: `{"alg":"HS256","typ":"JWT"}`. Anyone can do this with `base64 -d` or jwt.io — no secret required, because header and payload are never encrypted, only the signature is a cryptographic guarantee.
**Follow-up trap:** *"So is a JWT secure?"* — a JWT is secure to the extent its signature is verified correctly, with a pinned algorithm and validated claims; the encoding itself provides zero confidentiality, so anything sensitive (PII, secrets) should never be placed in the payload.

### Q2 — When would you choose HS256 over RS256, and when is that choice a mistake?
**Testing:** understanding the symmetric/asymmetric trust boundary, not just "RS256 is more secure."
**Answer:** HS256 is correct when exactly one party issues and verifies tokens — no other service needs the key. It's a mistake the moment a second, less-trusted verifier needs the key, because HS256's verification key is also its signing key: give that key to a second party and you've given them forgery capability, not just verification capability.
**Follow-up trap:** *"What's the actual attack if you get this wrong?"* — this previews algorithm confusion (module 4): if a verifier also accepts HS256 and an attacker can get the RS256 public key (which is meant to be public, via JWKS), they can HMAC-sign a token using that public key as the HS256 secret, and a misconfigured verifier that doesn't pin the expected algorithm will accept it as a validly-signed token.

### Q3 — Walk through JWKS-based key rotation without any verifier redeploy.
**Testing:** whether they understand `kid` as an index and the overlap-window requirement.
**Answer:** The issuer generates a new keypair, publishes the new public key alongside the old one in the JWKS (now two keys), and starts signing new tokens with the new key's `kid`. Verifiers, which cache the JWKS and refetch on TTL expiry or `kid` cache-miss, transparently pick up the new key without any code change. The old key must remain in the JWKS until every token signed with it has passed its `exp` — remove it early and every outstanding token from before rotation fails verification instantly.
**Follow-up trap:** *"What happens if you remove the old key immediately at rotation time?"* — an observable spike in 401s exactly correlated with the rotation deploy, since every unexpired token signed with the retired key becomes unverifiable; this is a real, recurring self-inflicted outage pattern.

### Q4 — Why does a verifier need `leeway`, and how much is too much?
**Testing:** whether clock skew is understood as a real distributed-systems concern, not an edge case.
**Answer:** Because issuing and verifying servers' clocks aren't perfectly synchronized — a few seconds of NTP drift is normal — a token minted with a valid TTL on one clock can appear prematurely expired (or not-yet-valid, for `nbf`) when checked against a slightly different clock on another host. 30-60 seconds of leeway absorbs normal drift; beyond a couple of minutes you're meaningfully widening the window during which a token you want treated as expired for security reasons is still accepted.
**Follow-up trap:** *"Could an attacker exploit generous leeway?"* — a very generous leeway (minutes) extends how long a token remains valid past its nominal `exp` during, say, an active revocation attempt, which is exactly the kind of small-but-real security margin that should be tuned deliberately rather than defaulted to something large "to avoid support tickets."

### Q5 — Your JWT payload includes the user's full list of 40 group memberships. Two questions: what breaks, and why?
**Testing:** connecting size limits to concrete observable failures.
**Answer:** The token grows into the low kilobytes, and since it's sent as an HTTP header (or cookie) on every request, this risks colliding with header-size limits enforced by load balancers, CDNs, and web servers — commonly a few KB to ~16KB per header depending on the component — producing `431 Request Header Fields Too Large` under otherwise normal traffic, not an edge case. It also means every group-membership change requires re-issuing the token to take effect, compounding the staleness problem from module 2.
**Follow-up trap:** *"How would you fix it without losing the information?"* — store a stable reference (a group-set version ID or just `sub`) in the token and look up current group memberships server-side by that ID when the authorization decision actually needs them, keeping the token itself small and the data source-of-truth server-side.

### Q6 — What's the actual signature-size difference between RS256 and ES256, and when does it matter enough to choose ES256?
**Testing:** numbers over adjectives; judgment about when the difference is decision-relevant.
**Answer:** RS256 at RSA-2048 produces roughly 256 raw bytes (~342 base64url characters); ES256 (P-256) produces 64 raw bytes (~86 base64url characters) — about a 4x reduction. This matters in bandwidth- or header-size-constrained contexts (mobile clients on metered connections, extremely high-QPS APIs where token bytes add up) but is largely irrelevant for typical web/API traffic where a few hundred bytes of difference is noise next to the rest of the request.
**Follow-up trap:** *"Given ES256 is smaller, why isn't it the universal default?"* — thinner historical library support across languages and platforms, and a documented history of ECDSA implementation bugs from incorrect or reused nonces in signing (not a flaw in the algorithm itself, but a real track record of libraries getting the implementation wrong) — verify your full toolchain supports it correctly before switching, rather than assuming smaller is strictly better.

### Q7 — A token has `aud: "internal-admin-tool"` and is presented to your public-facing customer API, which shares the same issuer and the same public key. The signature verifies. Should the request be allowed?
**Testing:** whether `aud` validation is treated as load-bearing, not decorative.
**Answer:** No. A valid signature only proves the issuer minted the token; it says nothing about which service it was minted *for*. Without an explicit `aud` check against the expected value for this specific service, a token scoped for a low-privilege internal tool would authenticate successfully against a completely different, higher-stakes service that happens to trust the same issuer — this is precisely the class of bug missing `aud` validation causes, and it's a real, not hypothetical, failure mode in systems with a shared IdP across multiple services.
**Follow-up trap:** *"What if the issuer only ever issues one kind of token for one purpose?"* — even then, validate `aud` explicitly rather than relying on "we only ever issue tokens for this purpose" as an informal invariant; that invariant breaks the moment a second consumer of the same IdP is added, often without every existing verifier being revisited.

### Q8 — Explain why `jti` matters even though it's not required for basic JWT validity.
**Testing:** connecting a rarely-used claim to a real capability gap.
**Answer:** Without a unique, stable identifier per token, there's no way to reference a *specific* issued token in a deny-list or replay-detection store — you'd have to either deny-list by `sub` (blocking the user's every token, not just the compromised one) or not support fine-grained revocation at all. `jti` gives you the hook to revoke or flag one specific token without collateral impact on the user's other active sessions.
**Follow-up trap:** *"Doesn't checking a `jti` deny-list on every request bring back the per-request-lookup cost JWTs were meant to avoid?"* — yes, precisely; this is the same tension module 2 covers under revocation, and it's why `jti`-based deny-lists are typically reserved for high-sensitivity tokens or active-incident response, not applied universally to every token in the system.

### Q9 — You're asked to add support for a third-party partner's service to verify your tokens. What changes, if anything, about your algorithm choice and key management?
**Testing:** whether the candidate reasons about trust boundaries expanding, not just "add them to the allowlist."
**Answer:** If you're currently on HS256, this is the forcing function to migrate to RS256/ES256 — you cannot safely hand a third party your HMAC secret, since that gives them forging capability over your entire token space; with asymmetric signing, you publish only the public key via JWKS and the partner verifies without ever gaining the ability to mint tokens. You'd also want to consider whether the partner needs a distinct `aud` value so a token scoped for them can't be replayed against your own internal services and vice versa.
**Follow-up trap:** *"What if you're already on RS256 — is there nothing to change?"* — you should still audit whether the partner's verification logic pins your expected algorithm and validates `iss`/`aud` correctly; a third party's sloppy verifier is now part of your token's attack surface even though you don't control its code, which is exactly why the next module's attack catalogue matters even when you did your side correctly.

### Q10 — Design the token validation function for a service that must support both RS256 (from your primary IdP) and HS256 (from a legacy internal system being phased out) during a migration window. What's the risk, and how do you contain it?
**Testing:** staff-level judgment about a genuinely awkward, real-world constraint.
**Answer:** The risk is exactly algorithm confusion (module 4) if both algorithms are accepted by the same verification code path without strict separation — an attacker could attempt to present an HMAC-signed forgery hoping the verifier's "accept either" logic is lenient about which key it checks against which algorithm. The safe design keeps two fully separate verification paths keyed by `iss` (or another unambiguous, pre-checked discriminator) *before* algorithm-specific verification runs, never a single `decode(token, algorithms=["RS256","HS256"], key=??)` call where the same key material could plausibly apply to both — and sets a hard deadline to retire the HS256 path entirely.
**Follow-up trap:** *"Why is checking `iss` before running algorithm-specific verification safer than checking it after?"* — because `iss` in the payload is itself unverified until the signature check passes, so using it to *select* which verification path to run (and which key to use) is safe only if each path's key is scoped so that a forged `iss` value can't trick you into verifying against the wrong (more permissive) key — in practice this means routing on `iss` to select the key, but still fully verifying the signature end-to-end afterward, never trusting `iss` as authorization by itself.

---

## Red flags that fail you

- Saying a JWT is "encrypted" — it's signed, not encrypted; header and payload are plainly readable by anyone.
- Not knowing the difference between `aud` and `iss`, or skipping either in a "what would you validate" answer.
- Proposing HS256 for a multi-service architecture without flagging the shared-secret forgery risk.
- Treating `kid` as safe to use as a file path or URL without qualifying that it must be an index into a fixed, pinned key set.
- Not mentioning clock skew/leeway when asked about `exp` validation.
- Suggesting large, fast-changing data belongs in JWT claims "for convenience."

---

## Cheat card

```
STRUCTURE: base64url(header) . base64url(payload) . base64url(signature)
  header/payload = PLAIN JSON, readable by anyone, zero confidentiality
  signature = ONLY security guarantee; over "header.payload" bytes

ALGORITHMS:
  HS256  symmetric, 1 shared secret signs+verifies. OK only if ONE party ever verifies.
  RS256  asymmetric, RSA. ~342 b64 chars sig (256B @ RSA-2048). Universal support. Safe default.
  ES256  asymmetric, ECDSA P-256. ~86 b64 chars sig (64B) -- ~4x smaller. Thinner lib support historically.
  RULE: >1 verifier that must never forge -> asymmetric (RS256/ES256), never HS256.

JWKS: /.well-known/jwks.json, keyed by `kid` in header
  kid = INDEX into fixed trusted set, NEVER a path/URL to fetch (path traversal / SSRF risk, mod 4)
  rotation: publish new key alongside old -> sign new tokens w/ new kid -> retire old key only
            AFTER max token lifetime has elapsed since rotation (else: 401 spike)

CLAIMS: iss (who minted) · sub (identity) · aud (who it's FOR -- always validate)
        exp (expiry, always validate) · nbf (not before) · iat (issued at) · jti (unique ID, needed for deny-lists)

CLOCK SKEW: leeway 30-60s = reasonable default, 120s generous, >few min = real exposure widening

SIZE LIMITS: headers commonly capped ~4-16KB by LB/CDN/webserver; cookies ~4KB/domain
             keep claims to sub+exp+few coarse flags; NEVER embed large/fast-changing data

NEVER: read `alg` from the token to decide how to verify -- pin an explicit algorithm allowlist
```

## Sources

- [RFC 7519 — JSON Web Token (JWT)](https://www.rfc-editor.org/rfc/rfc7519) — accessed 2026-07-26
- [RFC 7515 — JSON Web Signature (JWS)](https://www.rfc-editor.org/rfc/rfc7515) — accessed 2026-07-26
- [RFC 7517 — JSON Web Key (JWK)](https://www.rfc-editor.org/rfc/rfc7517) — accessed 2026-07-26
- [RFC 9449 — OAuth 2.0 Demonstrating Proof of Possession (DPoP)](https://www.rfc-editor.org/rfc/rfc9449) — accessed 2026-07-26
- [JWT Algorithm Confusion Attack (RS256 vs HS256) — Sourcery](https://www.sourcery.ai/vulnerabilities/jwt-algorithm-confusion) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
