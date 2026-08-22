# Applied Crypto: Hashing vs Encryption vs Encoding, bcrypt/argon2, AES-GCM, Key Rotation

> **Track:** T30 Auth & Application Security · **Time:** 2.5h · **Prereqs:** `T30-jwt-deep`
> **Updated:** 2026-07-26
> **Module id:** `T30-crypto-practice` · **Tags:** crypto, critical

## The 30-second version

Encoding (base64, URL-encoding) is reversible by anyone with no key at all and provides zero confidentiality — it's a format transformation, not a security control. Hashing is one-way by design (you cannot recover the input from the output) and is for verifying integrity or storing passwords, never for anything you need to get back. Encryption is reversible only with the correct key and is for confidentiality — data you need to retrieve later in its original form. Password hashing specifically needs a *deliberately slow*, memory-hard algorithm (Argon2id is the current OWASP-recommended default, bcrypt remains acceptable for existing systems) rather than a fast general-purpose hash (SHA-256 alone is wrong for passwords precisely because it's fast — fast is what you want for integrity checks and exactly what you don't want for something an attacker will try to brute-force offline). AES-GCM is the standard authenticated-encryption default, but it has exactly one catastrophic failure mode: reusing a nonce with the same key doesn't just weaken the encryption, it's a complete cryptographic collapse that recovers the authentication key and lets an attacker forge arbitrary ciphertexts — nonce uniqueness is the single fact about AES-GCM worth never forgetting. And the meta-rule underneath all of it: don't roll your own crypto, not because you're not smart enough to implement AES, but because implementations fail in ways that are invisible until someone with the right expertise and years of hindsight finds them, and the entire field's hard-won knowledge already lives in vetted libraries you should be using instead.

## Why this gets asked

Because "hashing" and "encryption" get used interchangeably by engineers who've never had to reason precisely about which one a given use case actually needs, and the interviewer wants to know whether you'd catch a genuinely dangerous mistake before it ships — storing passwords with a fast hash, reusing an AES-GCM nonce, comparing secrets with `==` instead of a constant-time function — because each of these is a real, documented category of production incident, not a theoretical concern.

---

## Lineage: past → present → future

**What came before.** Early password storage, well into the 2000s, routinely used fast general-purpose hashes (MD5, SHA-1, plain SHA-256) with no additional work factor, and often no per-user salt at all — a scheme that seemed reasonable when the threat model was "read the database directly," but broke down catastrophically once GPU-accelerated cracking made brute-forcing fast hashes trivial at scale: SHA-256 without a deliberate slowdown can be attempted many billions of times per second on modern GPU clusters, meaning even a database breach limited to hashed passwords (not plaintext) resulted in the overwhelming majority of common and moderate-strength passwords being recovered within hours. Unsalted hashes compounded this by making precomputed rainbow tables effective across every user in the database simultaneously — crack one common hash value once, and every user who happened to choose that same password is compromised at no additional cost. bcrypt (1999, based on the Blowfish cipher) was an early, deliberate response — a hash function with a tunable work factor specifically designed to be slow, so that the cost of a brute-force attempt scales directly with the defender's chosen difficulty, not just the attacker's hardware. On the symmetric-encryption side, block cipher modes like ECB (Electronic Codebook) were an early, dangerously naive default — ECB encrypts each block independently with no chaining, meaning identical plaintext blocks produce identical ciphertext blocks, visibly leaking structural patterns in the underlying data (the famous "ECB penguin" image, where an encrypted bitmap remains visually recognizable, is the canonical illustration) — a real, repeatedly-rediscovered mistake that authenticated encryption modes were built specifically to prevent.

**Where it stands now.** For password hashing, OWASP's current guidance is unambiguous: Argon2id (winner of the 2015 Password Hashing Competition) is the recommended default for new systems, with bcrypt remaining an acceptable choice for existing systems not worth migrating off immediately, and scrypt as a viable alternative where Argon2 isn't available — all three share the deliberate-slowness-plus-salting design bcrypt pioneered, differing mainly in memory-hardness characteristics (Argon2 and scrypt are explicitly memory-hard, meaning they resist the GPU/ASIC parallelization advantage that made fast hashes and even bcrypt itself somewhat more crackable at scale than a memory-bound function). For symmetric encryption, AES-GCM (Galois/Counter Mode, an authenticated encryption mode combining encryption and integrity verification in one construction) is the dominant current default, replacing older unauthenticated modes (CBC without a separate MAC, and ECB) that require bolting on integrity verification separately and are easy to get subtly wrong when done manually. The live, well-documented, and unambiguous danger specific to AES-GCM is nonce reuse: the "Forbidden Attack," described by Antoine Joux during NIST's own GCM standardization process in 2006, shows that reusing a nonce with the same key allows full recovery of the authentication key via polynomial algebra over the ciphertexts, at which point an attacker can forge arbitrary authenticated messages that pass integrity checks — this is not a theoretical weakness, it's a documented, complete break requiring only two ciphertexts sharing a nonce and key.

**Where it's heading.** Envelope encryption and centralized key-management services (AWS KMS, Google Cloud KMS, HashiCorp Vault) are now the default architecture for any system handling encryption at meaningful scale, specifically because they solve key rotation and access-auditing problems that hand-rolled key management handles poorly — this is settled practice, not an emerging trend. Post-quantum cryptography is the genuinely open frontier: NIST finalized its first post-quantum cryptographic standards in 2024 (ML-KEM/CRYSTALS-Kyber for key encapsulation, ML-DSA/CRYSTALS-Dilithium for signatures), and migration planning for systems with long confidentiality requirements (data that must remain secret for decades, where a future quantum computer breaking today's encryption retroactively is a real "harvest now, decrypt later" threat model) is an active, ongoing effort industry-wide as of 2026 — but for the vast majority of systems without multi-decade confidentiality requirements, current AES/RSA/ECC primitives remain the correct, non-urgent choice, and treating post-quantum migration as an immediate universal requirement rather than a risk-profile-dependent one is itself a common overcorrection worth naming explicitly.

---

## Mental model

```
  THREE OPERATIONS, THREE DIFFERENT QUESTIONS THEY ANSWER

  ENCODING    "can I represent this data in a different, more
              transportable FORMAT?"        e.g. base64, URL-encoding
              REVERSIBLE BY ANYONE, NO KEY NEEDED. Zero confidentiality.
              base64("secret") -> "c2VjcmV0" -> anyone can decode this instantly

  HASHING     "can I verify this data hasn't changed, or verify a
              guess, WITHOUT ever needing the original back?"
              ONE-WAY BY DESIGN. Given the output, you cannot recover the input.
              SHA256("password123") -> a fixed-size fingerprint, not reversible
              (but a FAST hash IS bruteforceable — try many inputs, compare outputs)

  ENCRYPTION  "can I make this UNREADABLE to everyone except whoever
              holds the KEY, and get the ORIGINAL back later?"
              REVERSIBLE ONLY WITH THE CORRECT KEY.
              AES_encrypt(data, key) -> ciphertext -> AES_decrypt(ciphertext, key) = data

  THE CLASSIC MISTAKE: using a FAST hash (SHA-256 alone) for PASSWORDS.
  Fast = good for integrity checks (verify a file wasn't corrupted, quickly).
  Fast = catastrophic for passwords (attacker tries billions of guesses/sec on GPU).
  PASSWORD HASHING NEEDS DELIBERATE SLOWNESS + MEMORY-HARDNESS: bcrypt/scrypt/Argon2id.

  AES-GCM'S ONE CATASTROPHIC RULE:
  ┌─────────────────────────────────────────────────────────────┐
  │  encrypt(plaintext_1, key=K, nonce=N)  -> ciphertext_1        │
  │  encrypt(plaintext_2, key=K, nonce=N)  -> ciphertext_2        │
  │                        ▲                                      │
  │                 SAME NONCE, SAME KEY = TOTAL COLLAPSE          │
  │  attacker with ciphertext_1 XOR ciphertext_2 recovers          │
  │  plaintext_1 XOR plaintext_2 directly, AND can recover the     │
  │  authentication key via polynomial math, enabling FORGERY      │
  │  of arbitrary future messages that pass integrity checks.      │
  │  NEVER let a (key, nonce) pair repeat. Ever.                    │
  └─────────────────────────────────────────────────────────────┘
```

---

## How it actually works

### Encoding, hashing, encryption — precisely, with the failure each one is wrong for

| | Encoding | Hashing | Encryption |
|---|---|---|---|
| Reversible? | Yes, by anyone, no key | No (by design) | Yes, only with the correct key |
| Needs a key? | No | No (though a keyed variant, HMAC, exists) | Yes |
| Use case | Transport-safe representation (binary → text) | Integrity verification, password storage, content addressing | Confidentiality — need the original back later |
| Wrong use | Assuming it hides anything (`base64("secret")` is NOT a security control) | Trying to "decrypt" a hash (structurally impossible) or using a fast hash for passwords | Using it where a hash would do (unnecessarily reversible = unnecessary risk if the key ever leaks) |

The single most common real mistake across all three: treating encoding as if it provided confidentiality. `base64`-encoded credentials in a config file, an `Authorization: Basic <base64>` header, a base64 blob in a URL — none of these are protected in any way; decoding requires nothing but the decode function itself, which is why base64-encoded secrets found in logs, git history, or client-side JavaScript are exactly as exposed as if they'd been written in plaintext.

### Password hashing — bcrypt, scrypt, Argon2id, and why work factor matters numerically

**Why a fast hash is wrong for passwords, quantified.** A modern GPU can compute billions of SHA-256 hashes per second; against a database of unsalted or weakly-salted fast hashes, an attacker with a dictionary of the top 10 million common passwords can test the entire list against every hash in a stolen database in a matter of seconds to minutes. Password hashing functions exist specifically to break this asymmetry: they're deliberately, tunably slow, so that the *defender* controls how expensive each guess is, independent of what a fast hash's raw throughput would otherwise allow.

**bcrypt.** Based on the Blowfish cipher, tunable via a **work factor** (commonly called "cost" or "rounds," expressed as `2^cost` iterations) — OWASP recommends a minimum work factor of 10, with many production systems using 12-14; the cost should be reassessed every 2-3 years and increased as hardware gets faster, since a work factor appropriate in 2015 is meaningfully weaker in relative terms by 2026 even though the number itself hasn't changed.

```python
import bcrypt

hashed = bcrypt.hashpw(b"correct horse battery staple", bcrypt.gensalt(rounds=12))
# gensalt() generates a random salt automatically — never reuse a salt across users;
# this is baked into bcrypt's design, not a separate step you can forget

bcrypt.checkpw(b"correct horse battery staple", hashed)   # True
bcrypt.checkpw(b"wrong guess", hashed)                      # False
```

**Argon2id — the current OWASP-recommended default.** Winner of the 2015 Password Hashing Competition, explicitly designed to be **memory-hard** (requiring a configurable amount of RAM per hash computation, not just CPU cycles), which specifically defeats the GPU/ASIC parallelization advantage that makes bcrypt somewhat more crackable at extreme scale than a memory-bound function — an attacker with thousands of parallel GPU cores gains far less advantage against Argon2id than against a purely CPU-time-bound function, because memory bandwidth doesn't parallelize the same way raw compute does.

```python
from argon2 import PasswordHasher

# OWASP-recommended baseline parameters (2026): memory=19 MiB min, iterations=2, parallelism=1
# (many production deployments use higher memory, e.g. ~64-128 MiB, for stronger margins)
ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)   # memory_cost in KiB

hashed = ph.hash("correct horse battery staple")
ph.verify(hashed, "correct horse battery staple")   # raises on mismatch, returns True on match
```

**scrypt** — the alternative when Argon2 isn't available in a given ecosystem: also memory-hard, tunable via CPU/memory cost `N` (OWASP recommends a minimum of `2^17`), block size `r` (minimum 8), and parallelization `p` (minimum 1).

**The number to hold in your head:** password hashing functions should take somewhere in the range of 100ms-500ms per hash on your actual production hardware — slow enough to make large-scale offline brute-forcing expensive, fast enough that legitimate login doesn't feel sluggish. Tune the specific parameters (bcrypt's cost factor, Argon2's memory/time/parallelism) against your real infrastructure to land in that range, rather than copying a fixed number from a blog post written for different hardware.

### Constant-time comparison — the subtle bug that undermines everything above

**Mechanism.** A naive string comparison (`==` in most languages, or a byte-by-byte comparison that returns early on the first mismatch) leaks timing information: it takes measurably longer to compare two strings that match for their first 5 characters than two strings that differ at the very first character, because the comparison exits early on mismatch. An attacker measuring response times precisely enough (a timing side-channel attack) can exploit this to recover a secret — a password, an HMAC signature, an API key — one character at a time, by observing which guessed prefix produces a marginally slower response.

**Exploit sketch.**

```python
# VULNERABLE: exits early on the first mismatched byte — timing leaks
# how many LEADING characters of the guess were correct
def naive_compare(a: str, b: str) -> bool:
    if len(a) != len(b):
        return False
    for x, y in zip(a, b):
        if x != y:
            return False   # returns FASTER the earlier the mismatch occurs
    return True

# FIX: always compare every byte, taking the SAME time regardless of
# where (or whether) a mismatch occurs
import hmac
hmac.compare_digest(guess, actual_secret)   # constant-time, from the stdlib
```

**Why this matters even when it seems like an edge case.** This exact class of bug is why module 3's JWT signature verification code explicitly used `hmac.compare_digest` rather than `==` — comparing a computed HMAC signature against the token's claimed signature using a naive `==` reintroduces a timing side channel into signature verification specifically, defeating the cryptographic strength of the signature scheme itself through an implementation detail entirely orthogonal to the algorithm's math. **Never compare secrets, signatures, or tokens with a naive equality operator — always use the language's constant-time comparison primitive** (`hmac.compare_digest` in Python, `crypto.timingSafeEqual` in Node, `subtle.ConstantTimeCompare` in Go).

### AES-GCM and the nonce reuse catastrophe

**Mechanism, precisely.** AES-GCM is an authenticated encryption mode: it produces both a ciphertext and an authentication tag in one construction, verifying both confidentiality and integrity together. It requires a nonce (a number used once) — typically 96 bits — for every encryption operation, and the security proof underlying GCM depends entirely on that nonce never repeating for a given key.

**Why reuse is catastrophic, not just weakened.** If two different plaintexts are encrypted under the same key and the same nonce, the keystream generated for both encryptions is identical (GCM, like other counter-mode ciphers, generates a keystream from the key+nonce and XORs it with the plaintext). This means:

1. **Direct plaintext recovery**: `ciphertext_1 XOR ciphertext_2 = plaintext_1 XOR plaintext_2` — if an attacker knows or can guess either plaintext, they immediately recover the other, with no cryptanalysis required beyond an XOR.
2. **Authentication key recovery**: GCM's authentication tag is computed using a polynomial evaluated over a hash subkey derived from the encryption key; the "Forbidden Attack" (Joux, 2006) shows that having two ciphertext/tag pairs under the same nonce provides enough algebraic information to solve for that hash subkey directly via polynomial root-finding, after which the attacker can compute valid authentication tags for **arbitrary messages of their own choosing** — a complete forgery capability, not merely a confidentiality leak.

**The numbers that matter.** With a 96-bit random nonce generated freshly per message, the birthday-bound collision risk becomes non-negligible only after roughly `2^48` messages under the same key (the square root of the nonce space, per the birthday paradox) — a real constraint at very high message volumes, which is exactly why production systems either use a counter-based nonce (guaranteed unique, never random, as long as the counter itself is never reset or reused) or rotate keys well before approaching that volume, rather than relying purely on random nonce generation at extreme scale.

```python
# untested sketch — illustrates the catastrophe, not a functional demo to run for real secrets
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os

key = AESGCM.generate_key(bit_length=256)
aesgcm = AESGCM(key)

nonce = os.urandom(12)   # 96 bits — MUST be unique per (key, message), NEVER reused

# CORRECT: fresh nonce for every encryption
ciphertext_1 = aesgcm.encrypt(os.urandom(12), b"message one", associated_data=None)
ciphertext_2 = aesgcm.encrypt(os.urandom(12), b"message two", associated_data=None)

# CATASTROPHIC BUG: reusing the same nonce for two different messages
same_nonce = os.urandom(12)
bad_1 = aesgcm.encrypt(same_nonce, b"message one", associated_data=None)
bad_2 = aesgcm.encrypt(same_nonce, b"message two", associated_data=None)
# An attacker with bad_1 and bad_2 can now XOR the ciphertexts to leak
# plaintext relationships AND recover the authentication subkey via the
# Forbidden Attack — this is not a "slightly weaker" outcome, it's total.
```

**Fix.** Never construct nonces manually from a mutable, resettable, or restart-prone source (a counter that resets to zero on process restart is a real, documented way this bug reappears in practice). Use a counter that's durably persisted across restarts, or a cryptographically random 96-bit nonce generated fresh per message and accept the birthday-bound message-volume ceiling, or use a construction like AES-GCM-SIV specifically designed to be nonce-misuse-resistant (degrading gracefully rather than catastrophically if a nonce is ever accidentally reused) for systems where guaranteeing nonce uniqueness is operationally hard to fully assure.

### Key rotation and envelope encryption

**The problem envelope encryption solves.** Encrypting large volumes of data directly with a single master key means that key is used enormously often (higher exposure surface) and rotating it requires re-encrypting every single piece of data it ever touched — often infeasible at scale. Envelope encryption solves this with two layers: a **data encryption key (DEK)**, generated fresh (or per-object/per-batch) and used to encrypt the actual data, and a **key encryption key (KEK)**, held in a hardened key management service (AWS KMS, Google Cloud KMS, HashiCorp Vault) and used only to encrypt/decrypt the DEK itself, never the bulk data directly.

```
  DATA          ──encrypt with──▶  DEK (fresh per object/batch)
                                        │
                                        ▼
  DEK           ──encrypt with──▶  KEK (held in KMS, rarely touched directly)
                                        │
                                        ▼
  STORED: {ciphertext_of_data, encrypted_DEK}   <- both stored together
  KEK NEVER LEAVES THE KMS. Only the encrypted DEK is exposed to the app.

  ROTATE THE KEK: re-encrypt only the (small) DEKs under the new KEK.
  The bulk DATA never needs re-encryption at all, since it was never
  encrypted directly by the KEK in the first place.
```

**Why this matters for rotation specifically.** Rotating the KEK requires re-encrypting only the (small, numerous but individually tiny) DEKs — a fast, cheap operation — rather than re-encrypting potentially petabytes of underlying data, which would be the case if the KEK had encrypted the bulk data directly. This is the mechanism that makes routine key rotation operationally feasible at all for large-scale systems, and it's why every major cloud KMS offering (AWS KMS, GCP KMS) implements envelope encryption as the default pattern rather than direct bulk-data encryption under a single master key.

### HMAC — integrity and authenticity, keyed

HMAC (Hash-based Message Authentication Code) combines a hash function with a secret key to produce a tag that proves both that a message hasn't been tampered with *and* that whoever produced the tag possessed the shared secret — a plain hash alone (`SHA256(message)`) proves nothing about who computed it, since anyone can compute a hash of anything; `HMAC(key, message)` proves the tag's producer held `key`, which is precisely why JWT's HS256 (module 3) and countless webhook-signature-verification schemes use HMAC rather than a bare hash.

```python
import hmac, hashlib

def sign(message: bytes, key: bytes) -> bytes:
    return hmac.new(key, message, hashlib.sha256).digest()

def verify(message: bytes, key: bytes, tag: bytes) -> bool:
    expected = sign(message, key)
    return hmac.compare_digest(expected, tag)   # constant-time — see above
```

### "Don't roll your own crypto" — precisely why, not just as a rule to recite

This isn't a statement about individual competence; it's a statement about the specific, well-documented ways cryptographic implementations fail even when written by capable engineers: **side-channel leaks** (the constant-time comparison issue above, or cache-timing attacks against naive implementations of primitives that need to be branch-free and memory-access-pattern-independent to be safe), **subtle mode-of-operation mistakes** (ECB's pattern leakage, nonce reuse in counter-based modes, incorrect padding schemes vulnerable to padding-oracle attacks), and **the absence of the specific expertise needed to reason about a construction's actual security proof**, which is a genuinely specialized skill distinct from general software engineering competence. Vetted libraries (`cryptography` in Python, `libsodium`, platform-native crypto APIs) encode decades of accumulated, hard-won knowledge about exactly these failure modes — using them isn't a concession of inability, it's the correct engineering decision given that the field's actual experts have already done this work and published it as a reusable, audited artifact.

---

## Build it from scratch

A minimal illustration of the full password-hashing-and-verification lifecycle plus the AES-GCM nonce discipline, combined:

```python
# untested sketch — illustrates the shape; use vetted libraries in real systems
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, hmac, hashlib

ph = PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1)

def register_user(password: str) -> str:
    return ph.hash(password)   # Argon2id, salted automatically, deliberately slow

def login(password: str, stored_hash: str) -> bool:
    try:
        ph.verify(stored_hash, password)
        return True
    except VerifyMismatchError:
        return False

class NonceCounter:
    """Durable, monotonic counter — survives restarts by persisting to disk/DB.
    NEVER use a plain in-memory counter that resets to 0 on restart."""
    def __init__(self, persisted_value: int = 0):
        self._counter = persisted_value

    def next_nonce(self) -> bytes:
        self._counter += 1
        # persist self._counter durably HERE in a real system, before returning
        return self._counter.to_bytes(12, byteorder="big")   # 96-bit nonce, GUARANTEED unique

key = AESGCM.generate_key(bit_length=256)
aesgcm = AESGCM(key)
nonce_counter = NonceCounter(persisted_value=load_last_persisted_counter())

def encrypt_record(plaintext: bytes) -> tuple[bytes, bytes]:
    nonce = nonce_counter.next_nonce()   # never random+reused, never restart-reset
    ciphertext = aesgcm.encrypt(nonce, plaintext, associated_data=None)
    return nonce, ciphertext

def sign_webhook_payload(payload: bytes, secret: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()

def verify_webhook_signature(payload: bytes, secret: bytes, provided_sig: str) -> bool:
    expected = sign_webhook_payload(payload, secret)
    return hmac.compare_digest(expected, provided_sig)   # constant-time, always
```

Full lab with envelope encryption against a local KMS emulator, a working nonce-reuse "Forbidden Attack" demonstration in a sandboxed environment, and a timing-attack proof-of-concept against a naive string comparison: **`(lab pending)`**.

---

## How it's done in production

**Password hashing** — Argon2id via well-maintained bindings (`argon2-cffi` in Python, `argon2` npm package, native support in most current frameworks' auth scaffolding); bcrypt via similarly mature libraries for existing systems not migrating immediately. Neither should ever be hand-implemented.

**Key management** — AWS KMS, Google Cloud KMS, Azure Key Vault, or HashiCorp Vault for envelope encryption's KEK layer, providing hardware-security-module-backed key storage, automated rotation scheduling, fine-grained access auditing (every key-use operation logged), and the operational machinery (IAM integration, cross-region replication) that hand-rolled key management reliably gets wrong at scale.

**TLS for transport, application-layer encryption for data-at-rest-beyond-TLS's-reach** — TLS protects data in transit between two directly-connected parties, but data that passes through or is stored by an intermediary that shouldn't see it in plaintext (a message queue, a third-party processor, a backup system) needs its own application-layer encryption independent of whatever TLS is doing at the transport layer — a common gap is assuming "we use HTTPS everywhere" covers confidentiality requirements that actually need end-to-end, not just hop-to-hop, protection.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| A database breach results in most user passwords cracked within hours | Fast hash (SHA-256/MD5) used for password storage, no deliberate slowdown | Migrate to Argon2id (or bcrypt as an interim step), re-hash on next successful login |
| Two users with the same password have identical hash values in the database | Missing per-user salt (or a global/shared salt) | Use a library that generates and stores a unique random salt per hash automatically (bcrypt/Argon2 do this by default) |
| An attacker forges arbitrary "authenticated" ciphertexts after observing two messages | AES-GCM nonce reused across two encryptions under the same key | Use a durable, restart-surviving counter-based nonce, or AES-GCM-SIV for misuse resistance |
| A timing side-channel attack recovers an HMAC secret or API key one character at a time | Naive `==` comparison used for signature/secret verification | Use the language's constant-time comparison primitive (`hmac.compare_digest`, etc.) universally for secret comparisons |
| Rotating an encryption key requires re-encrypting an entire multi-petabyte dataset | Direct bulk-data encryption under one master key, no envelope encryption layer | Introduce a DEK/KEK envelope-encryption layer; rotation then only touches the small DEKs |
| An encrypted image or file is visually or structurally recognizable despite encryption | ECB mode used, encrypting identical plaintext blocks to identical ciphertext blocks | Use an authenticated mode (AES-GCM) with proper chaining/counter construction, never ECB |
| A "confidential" base64-encoded credential is found readable in logs or git history | Encoding mistaken for encryption — no actual confidentiality was ever applied | Encrypt (or better, never log/store the raw secret at all) rather than merely encoding |

---

## Tradeoffs & when NOT to use it

- **Don't use encryption where hashing is the correct tool.** If you never need the original value back (a password, a content-integrity check), encryption is strictly worse: it introduces a key that can leak and, if it does, retroactively exposes every value it ever protected, whereas a correctly-implemented one-way hash has no equivalent single point of catastrophic failure.
- **Don't tune password-hashing work factors from a blog post's fixed numbers without testing against your own hardware.** The right Argon2/bcrypt parameters are the ones that land in the 100-500ms range on *your* actual production servers — a number copied from a five-year-old blog post reflects that post's hardware, not yours, and drifts further wrong every year hardware improves if never revisited.
- **Don't treat post-quantum migration as urgent for systems without multi-decade confidentiality requirements.** Current AES/RSA/ECC primitives remain correct and non-urgent for the overwhelming majority of systems in 2026; over-indexing on post-quantum migration for, say, a session token with a 15-minute lifetime is effort spent on a threat model that genuinely doesn't apply to that specific data's confidentiality window.
- **Don't roll your own AES-GCM nonce management "for efficiency."** A monotonic counter is simple in concept but has a real, recurring failure mode (reset on restart, reused across a data-migration/replay scenario, shared incorrectly across a distributed system's multiple writers without coordination) — use a vetted library's guidance, or AES-GCM-SIV specifically when uniqueness can't be fully guaranteed operationally.
- **Envelope encryption adds real complexity (a KMS dependency, an extra decrypt step on every data access) that's not justified for small-scale systems** with a handful of secrets and no meaningful rotation requirement — a single, well-managed secret in a secrets manager (not envelope-encrypted) can be entirely appropriate at that scale, and introducing a full KMS/DEK/KEK architecture for a five-person startup's single API key is disproportionate engineering overhead.
- **HMAC is not a substitute for asymmetric signatures when the verifier shouldn't also be able to produce valid signatures** — this is exactly module 4's algorithm-confusion lesson restated: HMAC's verification key is also its signing key, so it's wrong wherever a party needs to verify but must never be able to forge.

---

## Interview questions

### Q1 — Explain the difference between encoding, hashing, and encryption, and give a concrete example of each being misused for the wrong purpose.
**Testing:** baseline precision, since this trio is genuinely confused in casual engineering conversation.
**Answer:** Encoding (base64) is a reversible format transformation requiring no key, providing zero confidentiality; hashing is one-way by design, for integrity/password verification, never for anything you need back; encryption is reversible only with the correct key, for confidentiality. Common misuses: treating base64 as if it hides data (a base64-encoded secret in a config file or log is exactly as exposed as plaintext, just less immediately readable to a human glance), and using a fast general-purpose hash like SHA-256 for password storage, where the fast, easily-parallelized nature that makes SHA-256 good for integrity checks makes it dangerous for passwords, since it does nothing to slow down an offline brute-force attempt.
**Follow-up trap:** *"Is HMAC hashing or encryption?"* — neither cleanly; it's a keyed hash, one-way like a hash but requiring a secret key like encryption does, used specifically to prove both integrity and that the producer held the key — a distinct third category (authenticated integrity) that doesn't map onto either of the other two.

### Q2 — Why is SHA-256 the wrong choice for password storage, even though it's a perfectly secure hash function?
**Testing:** whether "secure hash" and "secure password hash" are understood as different requirements.
**Answer:** SHA-256's security properties (collision resistance, preimage resistance) are exactly what you want for integrity verification, but password hashing has an additional, different requirement: resisting offline brute-force at scale, which requires the hash to be *deliberately slow* and ideally memory-hard. A modern GPU computes billions of SHA-256 hashes per second, so an attacker with a stolen database of SHA-256'd passwords and a dictionary of common passwords can test the entire dictionary against every hash in seconds to minutes — SHA-256 being fast and secure as a general-purpose hash is precisely the property that makes it wrong for this specific use case.
**Follow-up trap:** *"What if you add a random salt to the SHA-256 input — does that fix it?"* — salting fixes the *precomputed rainbow table* problem (forcing an attacker to crack each hash individually rather than reusing one table across every user) but does nothing about raw brute-force speed against any *individual* hash — a salted-but-fast hash is still crackable per-user at billions of attempts per second; you need deliberate slowness (Argon2id/bcrypt/scrypt) in addition to salting, not instead of it.

### Q3 — Walk through the AES-GCM nonce reuse attack and explain precisely why it's catastrophic rather than merely weakened security.
**Testing:** the module's central, highest-stakes fact.
**Answer:** GCM generates a keystream from the key and nonce together and XORs it with the plaintext; if the same (key, nonce) pair encrypts two different messages, both ciphertexts were XORed with the *identical* keystream, so `ciphertext_1 XOR ciphertext_2` directly yields `plaintext_1 XOR plaintext_2` — immediate, algorithm-free plaintext-relationship recovery. Separately and more severely, GCM's authentication tag is computed via a polynomial evaluated over a hash subkey derived from the encryption key, and the "Forbidden Attack" (Joux, 2006) shows that two ciphertext/tag pairs under the same nonce provide enough algebraic constraints to solve for that hash subkey directly — after which the attacker can compute valid authentication tags for arbitrary messages of their own choosing, a complete forgery capability, not a partial weakening.
**Follow-up trap:** *"How would you design a system to make this mistake structurally hard to make?"* — use a durable, monotonically-incrementing counter persisted across restarts (never regenerated from a source that could reset or repeat), or adopt AES-GCM-SIV specifically, which is designed to degrade gracefully — remaining merely "somewhat weakened" rather than catastrophically broken — if a nonce is ever accidentally reused, trading a small amount of standard-GCM performance for genuine misuse resistance.

### Q4 — What does "memory-hard" mean in the context of Argon2id, and why does it matter more than pure CPU-time cost?
**Testing:** understanding the specific design goal, not just "Argon2 is the recommended one."
**Answer:** A memory-hard function requires a configurable, substantial amount of RAM per computation, not just CPU cycles — this matters because GPUs and custom ASICs achieve massive parallelization advantages for CPU-bound computation (many cheap cores computing in parallel) but far less advantage for memory-bound computation, since memory bandwidth and capacity don't scale the same way raw compute cores do. A purely CPU-time-hard function (an early, naive password hash design) can be attacked far more effectively at scale on specialized hardware than a memory-hard one, which is why Argon2id's explicit memory-hardness is a meaningful security property beyond simply "it's slow."
**Follow-up trap:** *"Does that mean bcrypt, which isn't explicitly memory-hard in the same way, is now considered insecure?"* — no, bcrypt remains an acceptable choice for existing systems per current OWASP guidance, and it does have some inherent memory usage from its Blowfish-based design, just less tunable and less aggressively memory-hard than Argon2id specifically; the guidance is "prefer Argon2id for new systems," not "bcrypt is broken."

### Q5 — Explain why a naive `==` string comparison for verifying an HMAC signature is a security vulnerability, even though the HMAC algorithm itself is sound.
**Testing:** the constant-time comparison nuance, a subtle but real, recurring class of bug.
**Answer:** A naive comparison typically exits as soon as it finds the first mismatched byte, meaning the total comparison time correlates with how many leading bytes of the guess matched the real value — an attacker capable of measuring response timing precisely can exploit this to recover the secret one byte at a time, submitting many guesses and keeping whichever guess produced a marginally slower response (indicating more leading bytes matched), repeating until the full value is recovered. This is a vulnerability in the *comparison implementation*, entirely separate from and undermining the cryptographic strength of the HMAC construction itself.
**Follow-up trap:** *"Is this a purely theoretical attack, or has it been demonstrated practically?"* — timing side-channel attacks are practically demonstrated and a well-documented, real vulnerability class (not purely academic), though the precision required to reliably exploit small timing differences over a network (versus locally, where it's much easier) does raise the practical bar somewhat — this doesn't make it acceptable to skip constant-time comparison, since the fix (`hmac.compare_digest` or equivalent) costs nothing and closes the gap entirely regardless of how hard the attack is to pull off in a given deployment context.

### Q6 — Design a system for rotating an encryption key across a dataset that would take days to fully re-encrypt if done directly. What's the pattern, and why does it work?
**Testing:** envelope encryption's core value proposition, applied to a concrete operational constraint.
**Answer:** Envelope encryption: introduce a data encryption key (DEK) that actually encrypts the bulk data, and a key encryption key (KEK), held in a KMS, that encrypts only the (small) DEKs. Rotating the KEK then requires re-encrypting only the DEKs — numerous but individually tiny — not the underlying multi-day-to-re-encrypt bulk data at all, since the bulk data was never directly encrypted by the KEK in the first place.
**Follow-up trap:** *"What if you need to fully retire an old DEK itself, not just the KEK — doesn't that bring back the full re-encryption problem?"* — yes, DEK rotation (as opposed to KEK rotation) does require re-encrypting the actual data that DEK protects, which is why DEKs are typically scoped small (per-object, per-batch, or per-time-window) specifically so that any single DEK's "blast radius" for a forced rotation is bounded — this is a real, remaining cost of the pattern, not eliminated by envelope encryption, just made proportional to a much smaller scope than "the entire dataset under one master key."

### Q7 — A startup wants to encrypt customer PII at rest. They propose storing a single AES key in an environment variable and using it to encrypt every record directly. Critique this design.
**Testing:** whether the candidate connects a seemingly-reasonable-sounding design to the specific problems envelope encryption and KMS exist to solve.
**Answer:** Several concrete problems: the key has no hardware-backed protection or access audit trail (anyone with access to the environment/process can read it in plaintext, with no log of who accessed it or when), rotating it requires re-encrypting every record it ever touched (a potentially enormous, disruptive operation), and a single leaked key compromises every record in the system at once, with no compartmentalization. The fix is envelope encryption via a real KMS: the bulk data is encrypted with per-object/per-batch DEKs, the DEKs are encrypted by a KEK that never leaves the KMS's hardware boundary, key use is logged and auditable, and rotation only touches the small DEKs.
**Follow-up trap:** *"Is this design ever acceptable — is there a scale or context where a single env-var key is fine?"* — for a small system with a genuinely low volume of low-sensitivity data and no compliance requirement demanding auditable key access (a hobby project, an internal tool with no PII), a single well-managed secret (ideally still in a secrets manager, not a raw environment variable) can be a reasonable, proportionate choice — the KMS/envelope-encryption overhead is justified by scale and sensitivity, not applied reflexively regardless of context.

### Q8 — Why is "don't roll your own crypto" not simply a statement about competence?
**Testing:** whether the reasoning behind the rule is understood, not just the rule itself.
**Answer:** Cryptographic implementations fail in specific, well-documented, and often subtle ways that are largely orthogonal to general software engineering skill: side-channel leaks (timing, cache-access patterns) that require specialized knowledge to even recognize as a risk, mode-of-operation mistakes (ECB's pattern leakage, nonce reuse) that look correct in a functional test but are catastrophically wrong under attack, and the need to reason about a construction's actual security proof, which is a distinct, specialized field. Vetted libraries encode this accumulated, hard-won expertise as an audited, battle-tested artifact — using them isn't an admission of inability, it's recognizing that this specific expertise already exists and has been published for reuse.
**Follow-up trap:** *"Does this mean engineers should never read or understand cryptographic primitives themselves?"* — no, and this entire module argues the opposite: understanding the mechanisms (why parameterization-equivalent nonce discipline matters for AES-GCM, why memory-hardness matters for password hashing) is exactly what lets you use vetted libraries *correctly* rather than misusing a correct implementation through an incorrect calling pattern (like reusing a nonce, or comparing secrets with `==`) — the rule is "don't implement the primitives yourself," not "don't understand how they work."

### Q9 — Your team stores API keys hashed with bcrypt "for security," the same way passwords are hashed. A colleague flags this as wrong. Are they right?
**Testing:** whether the candidate recognizes that not every secret needs the same treatment as a password, and can reason about why.
**Answer:** Likely wrong, yes — bcrypt/Argon2id are designed for *user-chosen, low-entropy* secrets (passwords humans can remember), where the deliberate slowness specifically defends against a large, guessable keyspace. API keys, when properly generated, are typically high-entropy random values (128+ bits from a CSPRNG) with no meaningful "guessable" structure at all — for these, deliberate slowness adds real latency cost to every API authentication check with no corresponding security benefit, since brute-forcing a properly-generated high-entropy key is already computationally infeasible regardless of hash speed. A fast, keyed hash (HMAC) or, if the key needs to be looked up efficiently, a fast general-purpose hash (SHA-256) with a proper lookup index is usually the more appropriate choice for high-entropy API keys.
**Follow-up trap:** *"So password-hashing algorithms are never appropriate for API keys?"* — if API keys are ever *user-chosen* or otherwise low-entropy (a legacy system allowing custom, short keys, for instance), the same brute-force concern that applies to passwords applies there too, and a slow hash would be appropriate — the deciding factor is the actual entropy/guessability of the secret, not what category of credential it's nominally called.

### Q10 — A security review flags that your organization has no plan for post-quantum cryptography migration. How do you respond, given the systems your team actually operates?
**Testing:** staff-level judgment about calibrating a genuinely open but often-overstated risk against actual context.
**Answer:** The correct first step is assessing which specific data actually has a multi-decade confidentiality requirement that a future quantum computer's ability to retroactively break today's RSA/ECC encryption would threaten under a "harvest now, decrypt later" model — for most operational systems (session tokens with minute-scale lifetimes, API traffic encrypted in transit and not archived long-term), this threat model simply doesn't apply, and treating post-quantum migration as universally urgent for all systems is a mismatch between a genuinely important but narrowly-scoped risk and a blanket response. For any data that genuinely does need multi-decade confidentiality (long-term archived records, certain regulated/classified data categories), begin tracking NIST's finalized standards (ML-KEM, ML-DSA, standardized in 2024) and plan migration on a timeline proportional to that specific data's actual exposure window, rather than applying the same urgency uniformly.
**Follow-up trap:** *"Isn't 'harvest now, decrypt later' a reason to encrypt everything with post-quantum algorithms immediately, just in case?"* — that reasoning proves too much: it would justify infinite present-day cost against a future, uncertain-timeline threat for data that will be worthless or irrelevant by the time a cryptographically-relevant quantum computer exists (most operational data ages out of relevance long before then) — the responsible answer is risk-proportional planning keyed to which specific data categories have genuinely long confidentiality requirements, not uniform maximum caution applied without regard to what's actually at stake for each data type.

---

## Red flags that fail you

- Using "hashing" and "encryption" interchangeably, or describing base64 as providing any confidentiality.
- Recommending SHA-256 (or any fast general-purpose hash) alone for password storage.
- Not knowing that AES-GCM nonce reuse is catastrophic (full key/message compromise) rather than merely "weaker."
- Comparing secrets, tokens, or signatures with a naive `==` rather than a constant-time function.
- Describing envelope encryption's rotation benefit incorrectly (e.g., claiming it avoids re-encrypting data that a DEK itself needs rotated, not just the KEK).
- Treating post-quantum migration as equally urgent for every system regardless of that system's actual confidentiality timeline.

---

## Cheat card

```
ENCODING (base64)  reversible by ANYONE, no key. ZERO confidentiality. Never a security control.
HASHING            one-way BY DESIGN. Can't recover input from output. For integrity/passwords.
ENCRYPTION         reversible ONLY with correct key. For confidentiality, need original back later.
HMAC               keyed hash -- proves integrity AND that producer held the key. Neither hash nor encryption alone.

PASSWORD HASHING (never use a fast general-purpose hash -- SHA256 alone = billions of guesses/sec on GPU):
  Argon2id  OWASP 2026 DEFAULT. memory-hard (defeats GPU/ASIC parallelization). Params: mem>=19MiB, t=2, p=1 (baseline)
  bcrypt    acceptable for EXISTING systems. Work factor: OWASP min 10, prod commonly 12-14. Reassess every 2-3yr.
  scrypt    alternative if Argon2 unavailable. N>=2^17, r>=8, p>=1
  TARGET: 100-500ms per hash on YOUR actual production hardware, not a blog post's number

CONSTANT-TIME COMPARISON: naive == leaks TIMING (exits early on first mismatch) -> side-channel
  recovers secrets byte-by-byte. ALWAYS use hmac.compare_digest / timingSafeEqual / ConstantTimeCompare
  for ANY secret/signature/token comparison.

AES-GCM NONCE REUSE = TOTAL CATASTROPHE, not "weaker":
  same (key,nonce) twice -> ciphertext1 XOR ciphertext2 = plaintext1 XOR plaintext2 (instant leak)
  PLUS: Forbidden Attack (Joux 2006) recovers the AUTH KEY via polynomial algebra -> forge ANY message
  FIX: durable RESTART-SURVIVING counter nonce (never plain in-memory, resets=bug) OR random 96-bit nonce
       accepting 2^48-message birthday-bound ceiling, OR AES-GCM-SIV for misuse-resistance

ENVELOPE ENCRYPTION:  DEK encrypts bulk DATA (fresh per object/batch) -> KEK (in KMS) encrypts only the DEK
  ROTATE KEK = re-encrypt only small DEKs, NOT the bulk data. This is what makes rotation feasible at scale.
  KMS: AWS KMS / GCP KMS / Vault -- HSM-backed, audited, automated rotation

DON'T ROLL YOUR OWN CRYPTO: not about competence -- side-channels, mode-of-operation mistakes (ECB
  pattern leakage, nonce reuse), and security-proof reasoning are specialized, already-solved-and-published
  knowledge in vetted libraries (cryptography, libsodium). Understand the mechanisms; use the library.

POST-QUANTUM (NIST finalized ML-KEM/ML-DSA, 2024): urgent ONLY for data w/ multi-decade confidentiality
  needs ("harvest now decrypt later"). NOT urgent for short-TTL tokens / most operational data.
```

## Sources

- [OWASP Password Storage Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html) — accessed 2026-07-26
- [Password Hashing in 2026 — inkyvoxel](https://www.inkyvoxel.com/password-hashing-in-2026/) — accessed 2026-07-26
- [Nonce-Disrespecting Adversaries: Practical Forgery Attacks on GCM in TLS (Joux Forbidden Attack context)](https://eprint.iacr.org/2016/475.pdf) — accessed 2026-07-26
- [Attacks on GCM with Repeated Nonces — elttam](https://www.elttam.com/blog/key-recovery-attacks-on-gcm) — accessed 2026-07-26
- [AES-GCM nonce reuse attack from scratch — Medium](https://medium.com/@patrickl.publique/aes-gcm-nonce-reuse-attack-515f7acec3f7) — accessed 2026-07-26
- [NIST Post-Quantum Cryptography Standardization](https://csrc.nist.gov/projects/post-quantum-cryptography) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
