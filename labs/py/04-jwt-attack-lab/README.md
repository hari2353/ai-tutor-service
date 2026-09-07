# Lab 04: The JWT Attack Lab — Break It, Then Fix It

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-jwt-security`

**You will build:** the five real-world JWT breaks as working code — `alg=none`, RSA/HMAC key confusion, weak-secret cracking, the replay window, and the revocation gap — each demonstrated against a deliberately insecure `make_insecure()` verifier and then killed by a `make_secure()` one. The final piece is the mitigation: short access TTL + refresh rotation with reuse detection.

**You will be able to answer:** *"What JWT vulnerabilities have actually shipped, and which one would I write myself if I weren't careful?"*

## Setup

```bash
cd labs/py/04-jwt-attack-lab
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest cryptography
```

## The spec

1. **Codec** — `b64url_encode/decode`, `hs256_sign`, `encode_jwt(claims, alg, key)`. `alg="none"` must produce an *empty* signature segment — you need it to forge the attack tokens.
2. **(a) `alg=none`** — `InsecureAlgNoneVerifier` branches on the token's own header (`none`/`None`/empty → skip verification) and accepts an unsigned admin token. `SecurePinnedVerifier` pins `algorithms=["HS256"]` — anything the header claims otherwise is rejected before any key is touched.
3. **(b) Key confusion** — `InsecureConfusionVerifier` accepts both HS256 and RS256 against one key argument, so the RSA *public* PEM gets used as an HMAC secret — and the attacker, knowing the public key, forges tokens. `SecureConfusionVerifier` is RS256-only; an HS256 header is rejected outright.
4. **(c) Weak secret** — `crack_hs256_secret(token, dictionary)` brute-forces the signature offline. The test proves a dictionary secret is recoverable in microseconds and that a 32-byte random secret survives.
5. **(d) Replay window** — `StatelessGateway` validates the same stolen token N times: stateless means no replay memory. 
6. **(e) Revocation gap + the fix** — a stolen stateless token outlives "logout" until `exp`. `HybridRotatingGateway` shrinks the window (300s access TTL) and adds rotation: replaying an already-rotated refresh token revokes the whole family — the theft signal.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **`kid` injection** — a verifier building a filesystem path from the `kid` header (`kid: "../../../dev/null"`); fix with a strict allowlist of kid formats.
2. **Async exploitation** — crack a 10k-word dictionary with `asyncio` + a process pool; note that HS256's weakness is *offline* — no server, no rate limit.
3. **Acceptance tests in CI** — port these tests to your real auth service's token verifier unchanged: every deploy should re-prove it rejects `alg=none` and key confusion.
