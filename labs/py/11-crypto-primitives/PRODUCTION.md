# Production notes — applied crypto

## Password hashing: bcrypt vs scrypt vs Argon2id

The post-2015 consensus, and OWASP's current cheat-sheet guidance:

- **Argon2id** (winner of the 2015 Password Hashing Competition) is the recommended default for new systems. Memory-hard: it forces the attacker to spend RAM per guess, which is what kills the GPU/ASIC advantage that makes fast hashes crackable at billions per second. OWASP baseline: **m=19 MiB (19456 KiB), t=2, p=1** — then tune to hit **~100–500 ms per hash on your actual production hardware**, not a blog post's number.
- **bcrypt** (1999) remains acceptable for existing systems; work factor **min 10, prod commonly 12–14**, reassess every 2–3 years as hardware speeds up. Its 72-byte input truncation is the known footgun.
- **scrypt** (what this lab uses, because `cryptography` ships it) is the solid alternative where Argon2 isn't available. OWASP: **N ≥ 2¹⁷, r ≥ 8, p ≥ 1** — this lab pins `n=2¹⁴` purely so tests run in seconds; production goes higher.

This lab's `verify_password` is also the place where the **constant-time comparison** rule lives (`hmac.compare_digest`): `==` exits early on the first mismatching byte, leaking timing information that a patient attacker turns into byte-by-byte secret recovery. Any secret comparison — password hash, token, signature — goes through a constant-time compare, in every language (`hmac.compare_digest` / `crypto.subtle.timingSafeEqual` / `ConstantTimeCompare`).

## AES-GCM and the nonce-reuse catastrophe

The single fact about AES-GCM worth never forgetting: **reusing a (key, nonce) pair is not a weakening, it is a total collapse**:

1. `ct1 XOR ct2 = pt1 XOR pt2` — the keystream cancels and the plaintext relationship leaks instantly.
2. Worse: the **Forbidden Attack** (Joux, 2006, during NIST's own GCM standardization) recovers the authentication key from just two such ciphertexts via polynomial algebra over GF(2¹²⁸) — after which an attacker **forges arbitrary authenticated messages that pass integrity checks**.

This is the "cryptographic doom principle" in its concrete form — and why the lab's `encrypt` generates a fresh `secrets.token_bytes(12)` nonce per call and the tests assert two encryptions of the same plaintext never share one. Production options: a durable restart-surviving **counter nonce** (an in-memory counter that resets on reboot is a bug, not a design), the random 96-bit nonce accepting the 2⁴⁸-message birthday bound, or **AES-GCM-SIV** for misuse-resistance where uniqueness genuinely cannot be guaranteed.

The AAD you passed is the other half of the contract: it binds a ciphertext to its *context* (a row id, a tenant id) so ciphertexts cannot be transplanted between contexts even under a shared key.

## Envelope encryption + KMS: what production actually does

A single application-held AES key does not survive contact with real operational requirements. Production systems layer it:

- **Envelope encryption** — a fresh **DEK** (data encryption key) encrypts each object or batch; the **KEK** (key encryption key), which lives in the KMS and never leaves it, encrypts only the small DEK. **Rotating the KEK means re-encrypting kilobytes of DEKs, not terabytes of data** — this is what makes rotation cheap, and it is exactly what the lab's `rotate()` is a toy of.
- **Key management services** — AWS KMS, GCP KMS, Azure Key Vault, HashiCorp Vault: keys generated and held in **HSMs**, every use audited, IAM-scoped.
- **Per-tenant DEKs** — one tenant's key exposure must not touch another's; the blast radius ends at the DEK boundary.
- **Automated rotation** — scheduled KEK rotation (e.g. AWS KMS annual) plus immediate rotation on any suspicion of compromise, with old versions kept for decrypt-until-rewrapped.
- **Fail-closed rewrap jobs** — the lab's `rotate` aborts on the first undecryptable item precisely because a half-rotated batch that the caller believes succeeded is the worst outcome; production rewrap pipelines carry the same rule with idempotency keys, retries, and a re-encryption ledger so a crashed job resumes cleanly instead of silently skipping rows.

## The 3 questions an interviewer asks after you describe this

1. *"Why not SHA-256 for passwords? It's a secure hash."* — Secure ≠ suitable. Fast is what you want for integrity and precisely what you don't want against an offline brute-forcer; password hashing needs *deliberate* slowness + memory-hardness + per-user salt.
2. *"What happens if the same AES-GCM nonce is used twice?"* — Total break: XOR leak of the plaintexts, then Forbidden-Attack recovery of the auth key and arbitrary forgery. Not "weaker" — collapsed.
3. *"How do you rotate keys on terabytes of encrypted data?"* — You don't re-encrypt the data; envelope encryption means you re-encrypt the DEKs under a new KEK in the KMS, which is small, auditable, and cheap.
