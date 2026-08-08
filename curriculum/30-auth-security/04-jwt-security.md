# JWT Attacks: alg=none, Key Confusion, Weak Secrets, Replay, and the Revocation Problem

> **Track:** T30 Auth & Application Security · **Time:** 3h · **Prereqs:** `T30-jwt-deep`
> **Updated:** 2026-07-26
> **Module id:** `T30-jwt-security` · **Tags:** jwt, critical
> **Lab:** `labs/py/04-jwt-attack-lab/`

## The 30-second version

Every JWT attack in this catalogue traces back to one root cause: a verifier that trusts something in the token before the signature has been fully and correctly checked — trusting the `alg` header to pick the verification method (`alg=none`, algorithm confusion), trusting the `kid` header to be a safe file path or URL (path traversal, SSRF), trusting a signature that was forgeable because the secret was weak (offline cracking), or trusting a token indefinitely because nothing was ever checked for uniqueness or freshness (replay, the revocation problem). The fix pattern is identical across all of them: pin everything explicitly server-side — the expected algorithm, the expected key by a trusted lookup (never an attacker-supplied path), a strong high-entropy secret or asymmetric keypair, and an explicit claim/nonce check for anything that must not be replayed — rather than trusting a single field to answer a question that should never have been delegated to attacker-controlled input in the first place.

## Why this gets asked

Because JWT vulnerabilities are almost entirely implementation bugs, not cryptographic breaks — the underlying signature schemes (HMAC-SHA256, RSA, ECDSA) are sound; every attack here works because a library or a developer trusted the token to describe its own verification method. The interviewer has either found one of these in a pentest, fixed one after a bug bounty report, or watched a real incident unfold from one, and wants to know whether you reason about "verify the signature" as a specific, precise procedure with several distinct ways to get subtly wrong, rather than a single checkbox you tick by calling `jwt.decode()`.

---

## Lineage: past → present → future

**What came before.** Early JWT library implementations, in the years immediately following RFC 7519 (2015), largely followed the spec's own suggestion that `alg` be read from the token header to determine how to verify it — a design choice that made sense for interoperability (a single verify function could handle any algorithm a client might use) but created an attacker-controlled decision point at the exact place a security check needed to happen. The `alg=none` vulnerability (RFC 7515 §6 defines "none" as valid for *unsecured* JWS, never intended for authentication contexts) and the RS256→HS256 algorithm-confusion attack (first broadly publicized by Tim McLean's 2015 write-up, "Critical vulnerabilities in JSON Web Token libraries") both exploit this same design flaw: if the verifier asks the token "how should I check you," an attacker gets to answer. The pain this caused was concrete and repeated — dozens of library CVEs across Node's `jsonwebtoken`, Java's various JWT libraries, and PHP implementations through the mid-2010s, each a variation on "the verifier trusted attacker-controlled metadata to select its own verification procedure."

**Where it stands now.** The current consensus, hardened by that CVE history, is unambiguous: verifiers must specify an explicit algorithm allowlist as a parameter to the verification call, never derive it from the token. Every major current library (`PyJWT`, `python-jose`, `jsonwebtoken` post-patches, `jjwt`, `golang-jwt`) requires or strongly encourages this. The live disagreement isn't about whether this is correct — it's settled — but about how much residual risk exists from *legacy* code and *third-party* integrations that predate the fix, and from newer attack surface around JWKS-based key lookup (`kid` path traversal and SSRF) that the "pin the algorithm" fix doesn't address at all, since it's a distinct trust failure (trusting `kid` as a fetch target rather than an index). Security researchers and bug-bounty writeups through 2026 continue to report `kid`-based SSRF and path-traversal findings, indicating the algorithm-confusion lesson has been broadly learned while the `kid`-trust lesson is still being relearned per-codebase. The revocation problem (a valid, unexpired JWT cannot be un-issued) remains architecturally unresolved by JWT itself — every mitigation (short TTL, refresh-token hybrid, deny-lists) is a workaround bolted on from outside the token format, not a fix within it.

**Where it's heading.** DPoP (RFC 9449) and mTLS-bound tokens address a different, related problem — a stolen bearer token being usable by whoever holds it — by cryptographically binding a token to a client-held key, so replay from a different client fails even with a stolen token; this is real, standardized, and slowly gaining adoption in high-sensitivity APIs, but is not yet a default. More speculatively, some researchers argue the `alg`-in-header design itself is a mistake that should have been fixed at the spec level (a token format where the algorithm is bound to the key/issuer out-of-band, not self-declared) rather than left to be a discipline problem for every implementer; this is a design critique, not a near-term spec change, so treat it as informed opinion rather than a direction the ecosystem is actually moving.

---

## Mental model

```
                    EVERY JWT ATTACK HERE = THE VERIFIER TRUSTED
                    ATTACKER-CONTROLLED INPUT TO DECIDE HOW TO VERIFY

  ┌─────────────────────────────────────────────────────────────────────┐
  │  TOKEN (fully attacker-controlled before signature is checked)      │
  │  header: { "alg": "???", "kid": "???" }     <- attacker writes this │
  │  payload: { "sub": "???", "aud": "???" }    <- attacker writes this │
  │  signature: ???                             <- attacker CANNOT      │
  │                                                 forge this IF the   │
  │                                                 verifier is strict  │
  └─────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
          ┌───────────────────────────────────────┐
          │  VERIFIER — every decision below must  │
          │  come from THE VERIFIER'S OWN config,  │
          │  never from reading the token itself   │
          ├───────────────────────────────────────┤
          │ "which alg do I use to check this?"    │  <- alg=none, algorithm
          │   MUST be verifier-pinned, not read     │     confusion attacks
          │   from header.alg                       │     live exactly here
          │ "which key do I check the sig against?" │  <- kid path traversal,
          │   MUST be a lookup in a fixed trusted    │     kid SSRF attacks
          │   set by kid-as-INDEX, never kid-as-PATH │     live exactly here
          │ "is this signature even strong?"        │  <- weak secret /
          │   secret must be high-entropy; asym key  │     offline cracking
          │   must be properly generated              │    lives exactly here
          │ "have I seen this exact token before,    │  <- replay attacks
          │   and should I still trust it?"          │     live exactly here
          │   needs jti + a store, which is exactly  │  <- the revocation
          │   the state JWTs were meant to avoid     │     problem lives here
          └───────────────────────────────────────┘
```

---

## How it actually works — the attack catalogue

### 1. `alg=none`

**Mechanism.** RFC 7515 defines `"alg": "none"` as valid syntax for an *unsecured* JWS — a token with no signature at all, the signature segment simply empty. This exists for legitimate non-authentication use cases (e.g., a JWT used purely as a structured claims carrier where the transport itself, like TLS with mTLS, already provides integrity). If a verifier reads `alg` from the token header and dispatches to a "no signature needed" code path whenever it sees `"none"`, an attacker can set that field themselves.

**Exploit.**

```python
import json, base64

def b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

# Attacker crafts a token claiming to be an admin, with alg=none and empty signature
header = {"alg": "none", "typ": "JWT"}
payload = {"sub": "admin", "role": "admin", "exp": 9999999999}
forged_token = (
    b64url_encode(json.dumps(header).encode()) + "." +
    b64url_encode(json.dumps(payload).encode()) + "."
    # signature segment left empty
)
# If the verifier's decode logic branches on header['alg'] == 'none' and
# skips signature verification for that branch, this token is accepted.
```

Real-world variants have bypassed naive string checks by capitalizing differently (`"None"`, `"NONE"`, `"nOnE"`) when a verifier's guard was a case-sensitive string comparison rather than a proper enum check.

**Fix.** Never accept `"none"` as a valid algorithm for authentication tokens. Modern libraries reject it by default when you pass an explicit `algorithms=["RS256"]` (or similar) allowlist to the verify call, since `"none"` simply isn't in that list — the fix is the same pin-the-algorithm discipline that fixes every attack in this section.

### 2. Algorithm confusion (RS256 → HS256 key confusion)

**Mechanism.** A service issues tokens signed with RS256 (private key signs, public key verifies) and publishes its public key via JWKS — by design, this key is meant to be public. If the verifier's code accepts *either* RS256 or HS256 (e.g., calls `jwt.decode(token, key, algorithms=["RS256", "HS256"])` with the same `key` variable for both, or worse, derives which algorithm to use from the token's own `alg` header), an attacker can construct an HS256 token and use the *public* RSA key — fetched from the same JWKS the legitimate system publishes — as the HMAC secret.

**Exploit.**

```python
import jwt   # PyJWT — untested sketch, illustrates the vulnerable pattern

# Legitimate setup: service verifies with the RSA public key, expecting RS256
public_key_pem = open("public.pem").read()   # fetched from JWKS, meant to be public

# VULNERABLE verifier: accepts multiple algorithms with one key argument
def vulnerable_verify(token):
    return jwt.decode(token, public_key_pem, algorithms=["RS256", "HS256"])  # BUG

# Attacker, knowing only the public key (public by design), forges:
forged = jwt.encode({"sub": "admin", "role": "admin"}, public_key_pem, algorithm="HS256")
# vulnerable_verify(forged) succeeds: the verifier treats public_key_pem's PEM
# bytes as an HMAC secret because the token's own header said alg=HS256,
# and HS256 was in the accepted algorithms list.
```

This is the single most cited real-world JWT vulnerability class, publicized broadly since 2015 and still found in pentests and bug bounties years later whenever a codebase's verification call accepts multiple algorithm families against the same key variable. Several JWT library CVEs across ecosystems have been attributed to variations of this pattern where a library's default behavior made the mistake easy to fall into rather than requiring it be opted into.

**Fix.** Never accept both symmetric and asymmetric algorithms in the same verification call or the same key variable. Pin exactly one algorithm (or a tightly-scoped family that shares a trust model, e.g., only `["RS256"]` or only `["ES256"]`, never mixing symmetric and asymmetric). If you must support multiple algorithms during a migration, route by an independently-verified discriminator (module 3's `iss`-based routing pattern) to entirely separate verification paths with entirely separate key material, never a shared call.

### 3. Weak secrets and offline cracking

**Mechanism.** HS256's security depends entirely on the secret's entropy. A short, guessable, or default secret (`"secret"`, `"changeme"`, a short dictionary word, or a value copy-pasted from a tutorial and never rotated) can be brute-forced offline once an attacker has even one valid token: they don't need the server, they just need to try candidate secrets against the known signing algorithm and compare against the token's actual signature, entirely offline, at whatever speed their hardware allows (GPU-accelerated HMAC-SHA256 cracking can attempt many millions of candidates per second on consumer hardware).

**Exploit sketch.**

```python
import hmac, hashlib, itertools

def try_crack(token: str, wordlist: list[str]) -> str | None:
    header_b64, payload_b64, sig_b64 = token.split(".")
    signing_input = f"{header_b64}.{payload_b64}".encode()
    target_sig = base64_url_decode(sig_b64)   # helper omitted
    for candidate in wordlist:
        guess = hmac.new(candidate.encode(), signing_input, hashlib.sha256).digest()
        if hmac.compare_digest(guess, target_sig):
            return candidate   # secret cracked entirely offline, no server interaction
    return None
```

Tools like `hashcat` (mode 16500 for JWT-HS256) and `jwt_tool` automate exactly this against common wordlists (rockyou.txt and variants) and are standard pentest tooling — this is not an exotic attack, it's a checklist item.

**Fix.** Use a high-entropy secret (256+ bits of real randomness, generated with a CSPRNG, never a human-chosen phrase) if you must use HS256 at all, and prefer RS256/ES256 for anything beyond a single trusted verifier specifically because asymmetric keys sidestep the "brute-forceable shared secret" problem entirely — an RSA-2048 or EC P-256 private key isn't crackable via the same offline dictionary approach.

### 4. `kid` path traversal and SSRF

**Mechanism.** If a verifier's key-lookup logic treats the `kid` header value as (or derives) a file path (`open(f"/keys/{kid}.pem")`) or a URL (`fetch(kid)` or constructs a URL using `kid` as a parameter) rather than an opaque lookup key into a fixed, trusted set, an attacker who controls `kid` controls what the verifier reads or requests.

**Exploit sketch — path traversal:**

```python
# VULNERABLE: kid used directly to build a filesystem path
def vulnerable_load_key(kid: str):
    with open(f"/app/keys/{kid}.pem") as f:   # BUG: no validation of kid's contents
        return f.read()

# Attacker sets kid = "../../../../dev/null" or a path to a file whose
# CONTENT the attacker also controls or can predict (e.g., an uploaded
# file, an access log with attacker-controlled content, /dev/null which
# reads as empty — and an empty "key" plus alg=HS256 signs trivially).
```

**Exploit sketch — SSRF via `jku`/`x5u` (related header fields that explicitly point to a URL):**

```json
{"alg": "RS256", "jku": "https://attacker.example.com/jwks.json", "kid": "attacker-key-1"}
```

If the verifier fetches whatever URL `jku` (JWK Set URL) or `x5u` (X.509 URL) specifies to retrieve the verification key, rather than restricting fetches to a pre-configured, trusted JWKS endpoint, the attacker hosts their own JWKS containing a keypair they control, points `jku` at it, signs the token with their own private key, and the verifier obligingly fetches the attacker's public key and "successfully" verifies a token the attacker fully controls. This is a direct SSRF vector as well — even if the fetch ultimately fails signature validation for some reason, the verifier has still made an outbound request to an attacker-chosen URL, which can be pointed at internal infrastructure (module 8 covers the cloud-metadata-endpoint variant of SSRF in depth).

**Fix.** Treat `kid` strictly as an opaque string used to index into your own pre-loaded, trusted key set (a dictionary literal, a cached JWKS from a hardcoded, pinned issuer URL) — never interpolate it into a file path or URL. Never honor `jku` or `x5u` headers from untrusted tokens at all; if you must support them, restrict fetches to an explicit allowlist of trusted hosts, never the value the token itself supplies.

### 5. Missing `aud`/`iss` validation

**Mechanism.** Covered mechanically in module 3; restated here as an attack: if a verifier checks only the signature and `exp`, a token that is completely legitimately issued — correctly signed, unexpired, by a trusted issuer — but intended for a *different* audience (a different service, a different tenant in a multi-tenant IdP, a lower-privilege internal tool) will verify successfully against a service it was never meant to authenticate to.

**Exploit.** No forgery is even required — this is a legitimate token used out of its intended context. A user with valid low-privilege access to Service A, if Service B trusts the same issuer and doesn't check `aud`, can present their Service-A token to Service B and be treated as authenticated there too, potentially with different (higher) privileges depending on how Service B interprets the token's claims.

**Fix.** Always validate `aud` against the exact expected value for the verifying service, and `iss` against the exact expected issuer — both are a single equality check, and skipping either is one of the most common real findings in JWT security reviews precisely because it requires no attacker sophistication at all, just an existing legitimate token used somewhere it shouldn't work.

### 6. Replay attacks

**Mechanism.** A JWT, once issued, is a bearer credential — whoever presents it is treated as authenticated, with no built-in mechanism distinguishing "the legitimate holder presenting it the first time" from "an attacker who intercepted or stole it presenting it again." Unlike a nonce-based challenge-response scheme, nothing in the base JWT spec prevents the *same* token from being replayed by a different party from a different location, as many times as its `exp` allows.

**Exploit.** An attacker who intercepts a token in transit (a misconfigured logging pipeline that logs full `Authorization` headers, a compromised proxy, a browser extension with overly broad permissions, an XSS payload that exfiltrates a token from `localStorage`) can replay it from anywhere, indistinguishable from the legitimate client, until it expires.

**Fix.** Short TTLs bound the replay window (this is one more reason to keep access tokens short-lived, beyond the revocation argument in module 2). `jti` plus a "seen tokens" store lets you detect or reject exact replays, at the cost of reintroducing a per-request lookup. DPoP/mTLS-bound tokens (module 3, module 7) solve this more fundamentally by requiring proof of possession of a client-held private key alongside the bearer token, so a stolen token alone is insufficient to replay successfully from a different client.

### 7. The fundamental revocation problem

**Mechanism.** This is architectural, not a bug — it's covered in depth in module 2 and restated here as the seventh entry in the catalogue because it's the attack surface that *isn't fixable by better validation code*, only by design choices made before the token is ever issued. A signed, unexpired JWT is valid by construction; there is no "ask the server if this is still good" step unless you deliberately build one back in (deny-list, short TTL plus refresh-token hybrid).

**Exploit — really, a limitation exploited by circumstance rather than crafted.** An attacker who steals a valid token (via any of the above vectors, or an entirely unrelated one like a compromised CI/CD secret store) retains full access for the token's remaining lifetime, and no incident-response action taken against the account (password reset, account disable, permission revocation) touches that already-issued token's validity at all.

**Fix.** Not a code fix — an architectural one, made in module 2: short access-token TTLs, a server-tracked revocable refresh token, and for the highest-sensitivity tokens, a `jti` deny-list checked at the cost of a lookup. There is no way to make a pure, long-lived, stateless JWT both instantly revocable and lookup-free — that combination doesn't exist, and claiming otherwise in an interview is a red flag.

---

## Build it from scratch

A minimal attack-and-defense harness demonstrating the algorithm-confusion vulnerability concretely, since it's the highest-value one to be able to demonstrate live:

```python
import jwt  # PyJWT — untested sketch; run inside the lab's sandboxed environment only

# --- Setup: legitimate RS256 issuer ---
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
public_key = private_key.public_key()

private_pem = private_key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.PKCS8,
    encryption_algorithm=serialization.NoEncryption(),
)
public_pem = public_key.public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)   # this is what gets published via JWKS — meant to be public

legit_token = jwt.encode({"sub": "user_1", "role": "user"}, private_pem, algorithm="RS256")

# --- Vulnerable verifier: accepts both algorithm families against one key ---
def vulnerable_verify(token: str):
    return jwt.decode(token, public_pem, algorithms=["RS256", "HS256"])  # THE BUG

# --- Attack: forge an admin token using the PUBLIC key as an HMAC secret ---
forged_token = jwt.encode({"sub": "attacker", "role": "admin"}, public_pem, algorithm="HS256")
print(vulnerable_verify(forged_token))   # succeeds — role: admin, no private key needed

# --- Fixed verifier: pin exactly one algorithm family ---
def safe_verify(token: str):
    return jwt.decode(token, public_pem, algorithms=["RS256"])  # HS256 not in list — rejected

try:
    safe_verify(forged_token)
except jwt.InvalidAlgorithmError:
    print("forged token correctly rejected")
```

Full lab including `alg=none`, `kid` path traversal against a sandboxed filesystem, weak-secret cracking with a wordlist, and a working `jti` deny-list: **`labs/py/04-jwt-attack-lab/`**.

---

## How it's done in production

**Defensive tooling** — `jwt_tool` and Burp Suite's JWT extensions are the standard tools *attackers and pentesters* use to probe for every vulnerability in this catalogue; running them against your own services pre-launch is a legitimate and common practice. On the defense side, current-generation libraries (PyJWT ≥2.x, `jsonwebtoken` post-2022 patches, `jjwt`) require an explicit `algorithms` parameter and reject `none` by default, closing the two most common historical CVE classes at the library level rather than relying on every developer getting it right independently.

**Secret/key management** — HS256 secrets, when used at all, should come from a secrets manager (AWS Secrets Manager, HashiCorp Vault) generating high-entropy values, never hardcoded or copy-pasted; RSA/EC private keys should be generated with standard tooling (`openssl genrsa`, `cryptography` library) and never checked into source control — a surprisingly common finding is a private key committed to a public repository, at which point the "asymmetric algorithms can't be brute-forced" advantage is moot because the key simply leaked outright.

**JWKS hardening** — restrict `jku`/`x5u` header trust entirely for externally-facing verifiers (most implementations should ignore these headers and use only a hardcoded, pinned JWKS endpoint); rate-limit and monitor JWKS fetch requests if you do support dynamic key URLs, since an attacker probing for SSRF will generate a distinctive pattern of fetch attempts against varied hosts.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Pentest reports "admin token forged with no credentials" | Verifier accepts both HS256 and RS256 against the same key variable | Pin a single algorithm family per verification path; never mix symmetric/asymmetric in one `algorithms=[...]` call |
| A crafted token with empty signature is accepted | Verifier branches on `header.alg == "none"` and skips verification | Never accept `"none"`; use a library that rejects it by default when given an explicit allowlist |
| Outbound requests from your verifier to unexpected external hosts, visible in egress logs | `jku`/`x5u` header trusted and fetched without an allowlist | Ignore `jku`/`x5u` entirely for untrusted tokens, or restrict to a hardcoded allowlist |
| Cracked JWT secret found in a public wordlist match during a security review | HS256 secret was short, a dictionary word, or a tutorial default never rotated | Rotate to a CSPRNG-generated 256+ bit secret, or migrate to RS256/ES256 |
| Same token accepted from two different IPs/user-agents simultaneously, flagged by anomaly detection | No replay protection; pure bearer token, no proof-of-possession | Add `jti` + short TTL; consider DPoP for high-sensitivity endpoints |
| Account disabled in admin panel, attacker still active for several more minutes | The fundamental revocation problem — no architectural fix retrofitted | Implement the module-2 hybrid (short access-token TTL + revocable refresh token) before an incident forces it |
| `kid` value in logs contains `../` sequences or full URLs | Verifier treats `kid` as a path/URL rather than an index | Validate `kid` against a strict allowlist pattern (e.g., alphanumeric only) and use it purely as a dictionary key |

---

## Tradeoffs & when NOT to use it

- **Don't accept multiple algorithm families in one verification call, ever, under any migration pressure.** If you must support two algorithms during a transition, route to fully separate verification functions with fully separate key material, keyed by a pre-signature-verified discriminator handled with extreme care (module 3, Q10).
- **Don't implement your own JWT library "for control."** The attack catalogue here is precisely the set of mistakes well-maintained libraries have already been hardened against through years of CVE fixes; a hand-rolled verifier is far more likely to reintroduce one of these than to avoid a real bug the library doesn't have.
- **Don't rely on `jti` deny-lists as your primary revocation mechanism at scale** unless you've accepted the per-request lookup cost — it's the right tool for high-sensitivity tokens or active-incident response, not a blanket default that quietly turns your "stateless" system stateful everywhere.
- **Don't assume asymmetric algorithms make secret management a non-issue.** A leaked private key (checked into a repo, embedded in a mobile app binary, exposed via a misconfigured secrets manager) is just as catastrophic as a weak HS256 secret — asymmetric keys solve the *shared-secret-across-verifiers* problem, not the *keeping-any-secret-secret* problem.
- **DPoP and mTLS-bound tokens add real client-side complexity** (key generation and storage on the client, additional handshake overhead) — appropriate for high-sensitivity APIs (banking, admin control planes) where replay of a stolen bearer token is an unacceptable residual risk, overkill for a low-sensitivity internal read-only dashboard.

---

## Interview questions

### Q1 — Explain the RS256-to-HS256 algorithm confusion attack end to end.
**Testing:** the single most important JWT vulnerability; almost guaranteed to be asked in some form.
**Answer:** The service signs tokens with RS256 (private key signs, public key verifies) and publishes the public key via JWKS, since it's meant to be public. If the verifier's code accepts both RS256 and HS256 using the same key variable, an attacker fetches the public key (public by design), constructs a token, and signs it with HS256 using the RSA public key's bytes as the HMAC secret. The verifier, told by the token's own header to use HS256, checks the signature against the same key variable — which now succeeds, because the attacker signed with exactly that value as an HMAC key.
**Follow-up trap:** *"How do you fix it without breaking existing RS256 clients?"* — pin the algorithm allowlist to `["RS256"]` only; this requires zero change for legitimate RS256-issued tokens and simply rejects any token claiming HS256, since HS256 was never a legitimate algorithm for this service in the first place.

### Q2 — What is `alg=none` and why does the JWT spec even allow it?
**Testing:** whether they understand this as a spec feature misapplied, not a spec bug.
**Answer:** RFC 7515 defines `"none"` as valid syntax for an unsecured JWS — a legitimate use case exists (structured claims where the transport already guarantees integrity), but it should never be accepted in an authentication context. The vulnerability is entirely in verifiers that read `alg` from the token and skip signature checking whenever they see `"none"`, letting an attacker simply declare their own forged token unsigned-by-design.
**Follow-up trap:** *"A verifier does a case-sensitive check for the literal string 'none' and rejects it. Is that sufficient?"* — not necessarily; some historical library bugs were bypassed with case variants (`"None"`, `"NONE"`) if the check wasn't a proper case-insensitive comparison or, better, an explicit allowlist that simply never contains any spelling of "none" rather than a blocklist trying to catch every variant.

### Q3 — How does `kid`-based SSRF work, and why is it distinct from the algorithm-confusion vulnerability?
**Testing:** whether they see this as a separate trust failure, not a variant of the same bug.
**Answer:** If a verifier trusts a `jku` (or `x5u`) header to specify a URL to fetch the verification key from, an attacker hosts their own JWKS at a URL they control, points the header at it, signs the token with their own key, and the verifier dutifully fetches the attacker's key and "successfully" verifies a token the attacker fully controls. It's distinct from algorithm confusion because the root trust failure is different: algorithm confusion trusts the token to choose its own verification *method*; this trusts the token to choose its own verification *key source* — pinning the algorithm allowlist does nothing to prevent this.
**Follow-up trap:** *"If the forged token fails signature verification anyway, is there still a security issue?"* — yes: the verifier already made an outbound HTTP request to an attacker-chosen URL before verification failed, which is SSRF regardless of whether the subsequent signature check succeeds — the network request itself can be pointed at internal infrastructure, including a cloud metadata endpoint (module 8).

### Q4 — Your service uses HS256 with a secret that's a 12-character English word. Walk through how an attacker exploits this, and quantify the risk.
**Testing:** numbers over adjectives on offline cracking feasibility.
**Answer:** Given even one valid, intercepted token, the attacker needs no server interaction at all — they recompute the HMAC-SHA256 signature over the token's header and payload for each candidate secret from a wordlist (or a brute-force keyspace) and compare against the real signature. GPU-accelerated cracking (tools like `hashcat` mode 16500) can attempt many millions of candidates per second on consumer hardware, so a dictionary word or a short low-entropy secret typically falls within minutes to hours, not a computationally infeasible timeframe.
**Follow-up trap:** *"What secret length/entropy would make this infeasible?"* — a CSPRNG-generated secret of 256+ bits (32+ random bytes, not 32 characters of a memorable phrase) puts brute-force outside feasible reach; the practical fix most teams should make regardless is migrating to RS256/ES256 for anything beyond a single trusted verifier, sidestepping the brute-forceable-shared-secret problem entirely.

### Q5 — A token is legitimately issued, correctly signed, unexpired, and used exactly as designed — yet it's still a security incident. How?
**Testing:** whether missing `aud`/`iss` validation is understood as an attack, not just a config gap.
**Answer:** If Service B trusts the same issuer as Service A but never validates `aud`, a token legitimately issued for Service A (perhaps with lower privileges, or scoped to a different tenant) authenticates successfully against Service B too — no forgery, no cracking, just a completely valid credential used somewhere it was never intended to work.
**Follow-up trap:** *"Is this the attacker's fault or the verifier's?"* — squarely the verifier's; the token holder may not even be malicious, they might simply have a legitimate token and an application that happens to accept it elsewhere due to a missing check. This distinguishes it from every other attack in this module, which requires deliberate attacker action — missing `aud` validation is a vulnerability that doesn't even need an attacker to demonstrate.

### Q6 — Design a replay-resistant token scheme for an API that processes financial transactions, where a stolen bearer token being replayed even once is unacceptable.
**Testing:** whether they reach for proof-of-possession rather than just "shorten the TTL."
**Answer:** Short TTL alone bounds the *window* but doesn't prevent replay *within* that window — if an attacker steals the token during its valid lifetime, they can still use it. The correct answer here is DPoP (RFC 9449) or mTLS-bound tokens: the client proves possession of a private key at request time (a DPoP proof JWT signed per-request, or the TLS client certificate itself), and the access token is bound to that specific key, so a stolen bearer token alone — without the corresponding private key — cannot be replayed by a different client even within the token's valid window.
**Follow-up trap:** *"What's the operational cost of adopting DPoP?"* — client-side key generation and secure storage, an additional signed proof object per request (verified server-side, adding compute and a small latency cost), and the fact that not every client platform/SDK has mature DPoP support yet — a real adoption friction that has kept it from being a default outside high-sensitivity APIs.

### Q7 — Explain why the revocation problem cannot be fixed by "just checking a database on every request" without losing what JWTs were for.
**Testing:** whether they see the tension precisely, not just recite "sessions vs tokens."
**Answer:** Checking a revocation store (a `jti` deny-list, a "logged out" flag) on every single verification reintroduces exactly the per-request network lookup that stateless JWTs were adopted specifically to eliminate — you end up with a system that has JWT's complexity (signature schemes, claim validation, key rotation tooling) plus a session system's operational dependency (a shared, available lookup store), without JWT's actual latency benefit. This is why the pragmatic answer (module 2) is a hybrid: check the store only at refresh time (infrequent), not at every access-token verification (frequent).
**Follow-up trap:** *"Isn't checking a deny-list for a small number of specifically-flagged high-risk tokens a reasonable middle ground?"* — yes, and this is exactly how it's used in practice: a `jti` deny-list checked only for tokens above a certain sensitivity threshold, or only during an active incident, rather than universally — a targeted exception to statelessness, not an abandonment of it.

### Q8 — A colleague says "we use RS256, so we're immune to JWT attacks." What's wrong with that statement?
**Testing:** whether algorithm choice is understood as necessary but not remotely sufficient.
**Answer:** RS256 alone prevents shared-secret cracking and shared-secret forgery (the HS256-specific risks), but does nothing about `alg=none` if the verifier's code still branches on the header naively, nothing about `kid`/`jku` SSRF if key lookup trusts attacker-supplied paths/URLs, nothing about missing `aud`/`iss` validation, and nothing about replay or the revocation problem — all of which apply regardless of algorithm family. Algorithm choice closes exactly one category of the catalogue.
**Follow-up trap:** *"Which of these remaining risks is hardest to fully close?"* — the revocation problem, because it's architectural rather than a validation-logic bug; every other item in the catalogue has a clean code-level fix (pin the algorithm, validate `kid` as an index, validate `aud`/`iss`, add `jti`+TTL), while revocation requires a design decision made before tokens are ever issued.

### Q9 — You find a private RSA signing key committed to a public GitHub repository from eighteen months ago. What's your actual exposure, and what's the remediation?
**Testing:** incident-response judgment beyond "rotate the key."
**Answer:** Exposure is total for the entire eighteen-month window and potentially beyond — anyone who found the key (via automated secret-scanning bots that actively monitor public commits, which is a real and fast-moving threat, not a hypothetical one) could have forged arbitrary valid tokens for that entire period, and you have no way to distinguish legitimate historical tokens from forged ones after the fact, since a forged token signed with the real private key is cryptographically indistinguishable from a genuine one. Remediation: rotate immediately (new keypair, update JWKS, retire the old key once outstanding legitimate tokens expire per module 3's rotation procedure), audit logs for the exposure window for suspicious activity patterns even though you can't cryptographically prove which tokens were forged, and treat every action taken by any account during that window as needing independent corroboration if it was sensitive.
**Follow-up trap:** *"Can you retroactively invalidate tokens signed during the exposure window specifically?"* — not via the signature itself (a forged token using the real key is indistinguishable from genuine), but if tokens carry `jti` and you have a complete issuance log, you could deny-list every `jti` NOT in your legitimate issuance log — assuming your issuance log is itself complete and trustworthy, which is exactly the kind of assumption an incident like this should force you to verify rather than assume.

### Q10 — Rank these five JWT mistakes by how often you'd expect to find them in a real security review of a mid-sized company's API, and justify the ranking.
**Testing:** staff-level pattern recognition across a real population of codebases, not just theoretical severity.
**Answer:** In rough order of what shows up most often: (1) missing `aud`/`iss` validation — the easiest to miss because it requires no attacker sophistication and "it worked in testing" never surfaces the gap; (2) weak/short HS256 secrets, especially in older or smaller services that predate a security review; (3) algorithm confusion, from a permissive `algorithms=[...]` list, often introduced during a "let's support both while we migrate" period that never got cleaned up; (4) `kid`/`jku` SSRF, less common because fewer codebases implement custom JWKS-fetching logic at all (most use a library's built-in, already-hardened JWKS client); (5) `alg=none`, the rarest now, because current-generation libraries reject it by default when given an explicit allowlist, and most codebases post-2018 were built on already-patched libraries.
**Follow-up trap:** *"Does that ranking match public CVE frequency, or your own field experience — and does it matter which?"* — public CVE data skews toward library-level bugs (algorithm confusion, `alg=none`) because those are the ones that get a CVE number attached; missing `aud`/`iss` validation is an application-level misconfiguration, not a library bug, so it never shows up in CVE databases despite being, by most practitioners' field experience, the most commonly found issue in real reviews — a useful reminder that CVE counts measure library defects, not the full population of real-world misconfigurations.

---

## Red flags that fail you

- Describing algorithm confusion vaguely ("something about mixing up algorithms") without being able to explain that the public key becomes the HMAC secret.
- Proposing `algorithms=["RS256", "HS256"]` in a verification call as a reasonable way to "support both during migration."
- Not knowing that `kid` should never be used as a raw file path or URL.
- Claiming RS256/ES256 alone makes a system immune to JWT attacks.
- Suggesting `alg=none` should be handled by string-matching against `"none"` case-insensitively as a sufficient fix, rather than using an explicit allowlist.
- Treating the revocation problem as fixable purely by shortening the TTL, without naming replay-within-the-window as a distinct, unaddressed risk.

---

## Cheat card

```
ROOT CAUSE OF EVERY ATTACK HERE: verifier trusts attacker-controlled token
  content to decide HOW to verify, instead of using its OWN pinned config.

alg=none          verifier skips sig check when header.alg == "none"
                  FIX: never accept "none"; use explicit algorithms=[...] allowlist

ALG CONFUSION      RS256 issuer + verifier accepts RS256 AND HS256 vs same key var
(RS256->HS256)     attacker HMAC-signs using the PUBLIC RSA key as HMAC secret
                  FIX: pin ONE algorithm family per verify call, never mix sym+asym

WEAK SECRET       HS256 w/ short/dictionary secret -> offline crack (hashcat -m 16500)
                  millions of guesses/sec on consumer GPU -> minutes-hours for weak secrets
                  FIX: 256+ bit CSPRNG secret, or migrate to RS256/ES256 entirely

kid PATH TRAVERSAL / SSRF   kid used as file path (../../etc) or jku/x5u fetched blindly
                  FIX: kid = opaque INDEX into fixed trusted set only.
                       NEVER honor jku/x5u from untrusted tokens; hardcode JWKS URL.

MISSING aud/iss   valid signed unexpired token from Service A works on Service B too
                  (same issuer, no aud check) -- NO forgery needed, just missing checks
                  FIX: always validate aud AND iss against exact expected values

REPLAY            bearer token = usable by whoever holds it, no possession proof
                  FIX: short TTL bounds window; jti+store detects; DPoP/mTLS binds to client key

REVOCATION PROBLEM   architectural, not a bug. valid+unexpired JWT = always accepted.
                  FIX: NOT a code fix -- short access-TTL + server-tracked refresh token (mod 2)

TOOLS: jwt_tool, Burp JWT extensions (attacker/pentest side)
       PyJWT/jsonwebtoken/jjwt current versions reject none + require explicit algorithms=[...]
```

## Sources

- [JWT Algorithm Confusion Attack (RS256 vs HS256) — Sourcery Vulnerability Database](https://www.sourcery.ai/vulnerabilities/jwt-algorithm-confusion) — accessed 2026-07-26
- [JWT Algorithm Confusion: How alg:none and RS256→HS256 Downgrade Break Authentication — AquilaX](https://aquilax.ai/blog/jwt-algorithm-confusion-auth-bypass) — accessed 2026-07-26
- [The alg=none JWT vulnerability, with code that exploits it and a 5-line fix — JWTShield](https://jwtshield.com/blog/alg-none-jwt-vulnerability) — accessed 2026-07-26
- [JWT algorithm confusion attacks: How they work and how to prevent them — WorkOS](https://workos.com/blog/jwt-algorithm-confusion-attacks) — accessed 2026-07-26
- [RFC 7515 — JSON Web Signature (JWS), §6 Unsecured JWS](https://www.rfc-editor.org/rfc/rfc7515#section-6) — accessed 2026-07-26
- [RFC 9449 — OAuth 2.0 Demonstrating Proof of Possession (DPoP)](https://www.rfc-editor.org/rfc/rfc9449) — accessed 2026-07-26

**Unverified claim flagged:** search results surfaced references to specific 2026 CVE identifiers (e.g., "CVE-2026-22817," "CVE-2026-27804," "CVE-2026-23552") attributed to JWT algorithm-confusion clusters in secondary blog sources; these could not be cross-verified against a primary CVE/NVD record during research for this module and are deliberately omitted from the body text above. Treat any specific CVE number for 2026 JWT vulnerabilities as unconfirmed until checked directly against nvd.nist.gov.

## Changelog
- 2026-07-26 — created
