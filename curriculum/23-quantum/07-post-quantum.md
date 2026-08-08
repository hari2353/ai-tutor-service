# Post-Quantum Cryptography: What Breaks, When, and Migration Plans

> **Track:** T23 Quantum Computing · **Time:** 2.0h · **Prereqs:** T23-qubits, T23-algorithms
> **Updated:** 2026-08-08
> **Module id:** `T23-post-quantum` · **Tags:** security, critical

## The 30-second version

Shor's algorithm (module 3) completely breaks RSA, Diffie-Hellman, and ECC/ECDSA — every public-key scheme in production today rests on factoring or discrete log being classically hard, and a sufficiently large fault-tolerant quantum computer defeats all of them, not weakens them. Grover's algorithm only quadratically weakens symmetric crypto and hashes — AES-256 drops to an effective 128-bit security level (still adequate; AES-128 does not survive and should not be used for new long-lived data), and SHA-256's preimage resistance drops from `2^256` to `2^128` (still adequate; its birthday-bound collision resistance was already `2^128` classically and is essentially unaffected). NIST finalized the first three post-quantum standards in August 2024 — **ML-KEM** (FIPS 203, lattice-based key encapsulation, the Kyber algorithm standardized), **ML-DSA** (FIPS 204, lattice-based signatures, ex-Dilithium), and **SLH-DSA** (FIPS 205, hash-based signatures, ex-SPHINCS+, the conservative fallback whose security rests only on hash-function collision resistance) — with **HQC** (a code-based KEM, a mathematically different hardness assumption) added in 2025 specifically as a hedge against any future lattice-cryptanalysis breakthrough. **Harvest-now-decrypt-later** is a present-day threat, not a future one: data encrypted today with RSA/ECC and captured by an adversary can be decrypted retroactively the moment a cryptographically relevant quantum computer exists, so the migration clock started when that data was first transmitted, not when the hardware arrives. Hybrid key exchange (classical `X25519` combined with `ML-KEM-768`) is already live in production TLS — Chrome and Cloudflare have deployed it since 2024, reaching roughly 30% of TLS 1.3 handshakes globally by early 2026 — and hybrid, not PQC-only, is the correct near-term posture precisely because newer PQC algorithms have had far less real-world cryptanalytic scrutiny than decades-old RSA/ECC.

## Why this gets asked

Because this is the one module in the entire track where the interviewer isn't testing whether you understand quantum computing — they're testing whether you can make an actual, dated, resourced security decision under genuine uncertainty about hardware timelines, which is precisely the kind of judgment call a principal engineer is paid to make and defend to leadership, auditors, and a board. Anyone who has sat through a security review knows the two failure modes this module exists to prevent: panicking and trying to rip out RSA overnight (wasting resources on the wrong priority, without crypto-agility, likely breaking things), or dismissing the entire topic as science fiction because "quantum computers don't exist yet" (ignoring that harvest-now-decrypt-later makes today's data already exposed, and that large-organization migrations take years regardless of when the hardware threat materializes).

---

## Lineage: past → present → future

**What came before.** RSA (1977), Diffie-Hellman (1976), and elliptic-curve cryptography (mid-1980s) built the entire public-key infrastructure the internet runs on today, all resting on problems (factoring, discrete log) believed classically hard for decades with no serious challenge. That confidence was never a mathematical proof, only an absence of a known attack — the same epistemic status every cryptographic hardness assumption has always had — and Shor's 1994 algorithm (module 3) proved factoring and discrete log both fall to a sufficiently large quantum computer, converting a purely theoretical future risk into a standardization priority the moment the algorithm was published, decades before the hardware would exist to run it at scale. NIST's response, starting a formal public competition in 2016 modeled on the earlier AES competition process, was a deliberate reaction against a real, specific pain: cryptography designed behind closed doors or by a single vendor has a documented history of catastrophic failure (the Dual_EC_DRBG backdoor, confirmed to have been engineered by the NSA and shipped as a default in widely-used products for years before discovery, is the canonical cautionary example) — an open, multi-round, adversarial public cryptanalysis process across nearly eight years and dozens of candidate algorithms spanning different mathematical hardness assumptions (lattice, code-based, hash-based, multivariate, isogeny-based) was specifically designed to earn justified confidence before standardizing anything the world would depend on for decades.

**Where it stands now.** NIST finalized the first three standards in August 2024: **ML-KEM** (FIPS 203, key encapsulation, lattice-based via Module-LWE), **ML-DSA** (FIPS 204, signatures, lattice-based via Module-LWE/Module-SIS), and **SLH-DSA** (FIPS 205, signatures, hash-based, deliberately conservative — its security depends only on hash-function collision resistance, a much older and more thoroughly stress-tested assumption than lattice hardness) ([NIST PQC Standards — QRAMM guide to FIPS 203/204/205](https://qramm.org/learn/nist-pqc-standards.html) — accessed 2026-08-08). NIST added **HQC** (code-based, a mathematically distinct hardness assumption from lattices) as an additional standardized KEM in 2025, explicitly as **cryptographic diversification** — a hedge so that a future breakthrough in lattice cryptanalysis wouldn't simultaneously compromise both the primary KEM and signature standards at once, since ML-KEM and ML-DSA both rest on lattice-family assumptions. The live, consequential reality on the ground: adoption is real but sharply uneven. Hybrid key exchange in TLS 1.3 (classical `X25519` combined with `ML-KEM-768`) has genuine, measured production deployment — Cloudflare's edge has supported hybrid KEMs since 2022, Chrome enabled `X25519MLKEM768` starting with version 124 (April 2024), and by early 2026 this reaches roughly 30% of TLS 1.3 handshakes globally per Cloudflare Radar telemetry ([From X25519 to X25519+MLKEM768 — postquantumsecurity.org](https://www.postquantumsecurity.org/publications/X25519+MLKEM768.html) — accessed 2026-08-08) — while a 2026 internet-wide measurement study found roughly half of analyzed domains remain fully classical with zero PQC readiness ([Measurement Study of Post-Quantum Readiness of Internet: 2026](https://arxiv.org/pdf/2606.16473) — accessed 2026-08-08). Both halves of that statistic matter simultaneously for advising a real organization: PQC in TLS is a proven, deployed, working technology, and most of the internet hasn't touched it yet. A genuinely instructive operational failure is also part of the recent record, not hypothetical: Chrome's initial 2024 hybrid rollout caused real production breakage at organizations running TLS-inspecting middleboxes/enterprise proxies that choked on the larger `ClientHello` messages hybrid key exchange produces, forcing a rollback before a fixed version was redeployed — exactly the kind of operational gotcha a migration plan needs to anticipate, not a one-off curiosity.

**Where it's heading.** High confidence: government timelines are concrete and dated. The NSA's **CNSA 2.0** suite, most recently updated May 2025, specifies a phased mandate directly for national-security systems and indirectly sets the pace regulated industries plan around: new acquisitions must support quantum-resistant algorithms by 2027, legacy networking equipment must complete transition by 2030, CNSA 2.0 becomes mandatory across covered categories by 2031, and operating systems/custom applications/cloud services must reach exclusive use by 2033, with full quantum resistance across national security systems required by 2035 ([CNSA 2.0: NSA's Quantum-Resistant Cryptography — Entrust](https://www.entrust.com/resources/learn/what-is-cnsa-2-0) — accessed 2026-08-08). NSA explicitly recommends **hybrid** (dual classical-and-PQC) deployment through 2030 specifically because newer PQC algorithms have had less real-world cryptanalytic scrutiny than RSA/ECC's decades of attack attempts, despite the NIST competition's rigor — this is a stated, deliberate hedge, not overcaution. Medium confidence: NIST has signaled intent to continue evaluating and potentially standardizing additional signature schemes with different size/performance tradeoffs as real deployment experience surfaces gaps the original competition didn't fully anticipate. Lower confidence, explicitly speculative: exactly when harvest-now-decrypt-later risk converts into actually-realized decryption depends entirely on the hardware timelines covered in modules 3 and 5, which remain genuinely uncertain (expert estimates for a cryptographically relevant quantum computer span roughly 5 to 30 years) — but this uncertainty changes only the *urgency framing* used to justify migration internally, not the recommended action, which is the single most important point this module makes.

---

## Mental model

```
  WHAT BREAKS vs WHAT DOESN'T                         MIGRATION PRIORITY FUNNEL
  ────────────────────────────                         ──────────────────────────
  SHOR (module 3) -- COMPLETE BREAK:                    1. CRYPTOGRAPHIC INVENTORY
    RSA, Diffie-Hellman, ECC/ECDSA                          (usually the hardest, most
    -> algorithm REPLACEMENT required                       underestimated step)
                                                                   │
  GROVER (module 3) -- QUADRATIC WEAKENING ONLY:                  ▼
    AES-256 -> effective 128-bit (fine)                  2. HARVEST-NOW-DECRYPT-LATER RISK
    AES-128 -> effective 64-bit (NOT fine, retire)           rank by: data sensitivity
    SHA-256 preimage -> 2^128 (fine, collision unaffected)    duration x current exposure
    -> algorithm RESIZING, not replacement                       │
                                                                   ▼
  HARVEST-NOW-DECRYPT-LATER                            3. HYBRID DEPLOYMENT
  ─────────────────────────                                (classical + PQC together --
  today: adversary RECORDS encrypted traffic                secure if EITHER holds)
         │                                                        │
         ▼ (years later, timeline uncertain --                   ▼
    CRQC exists, decrypts retroactively            4. CRYPTO-AGILITY (swap algorithms
                                                        without a full rearchitecture --
  clock started at RECORD time, not decrypt time         the actual lesson from SHA-1's
                                                          decade-plus deprecation slog)
```

---

## How it actually works

### What Shor breaks, precisely, and why lattice problems are different

Module 3 established the mechanism: Shor's algorithm solves the abelian hidden subgroup problem efficiently via period-finding and the QFT, which factoring and discrete log both reduce to — this completely breaks RSA (factoring), Diffie-Hellman (discrete log), and ECC/ECDSA (elliptic-curve discrete log). **Lattice-based problems are not known to reduce to the abelian hidden subgroup problem**, and no efficient classical *or* quantum algorithm is known for the specific lattice problems ML-KEM and ML-DSA rely on (Module Learning With Errors, Module-LWE, and the related Module Short Integer Solution, Module-SIS) — this is the actual, specific basis for calling these schemes "post-quantum," not a vague appeal to "lattices are complicated."

**The core hardness intuition, verified directly.** Learning With Errors (Regev, 2005) asks: given many noisy linear equations `bᵢ = ⟨aᵢ, s⟩ + eᵢ mod q` for a secret vector `s`, small random errors `eᵢ`, and known public `aᵢ`, recover `s`. Without the noise `e`, this is trivial linear algebra (Gaussian elimination). With the noise, it becomes believed-hard — verified directly with a toy Regev-style encryption scheme (`n=12`, `q=3329` — the same modulus family real ML-KEM/Kyber uses, not a coincidental choice):

```
secret s: random 12-dimensional vector mod q=3329
public key: (A, b=As+e mod q), A random 40x12 matrix, e small noise in {-2,-1,0,1,2}

encrypt bit 0 -> decrypt bit 0  (raw value mod q = 3317, q/2=1664)  OK
encrypt bit 1 -> decrypt bit 1  (raw value mod q = 1657, q/2=1664)  OK
encrypt bit 0 -> decrypt bit 0  (raw value mod q = 3325, q/2=1664)  OK
encrypt bit 1 -> decrypt bit 1  (raw value mod q = 1660, q/2=1664)  OK
... (8/8 trials correct)

All 8 trials correct: True
```

Decryption works because a correctly-formed ciphertext decrypts to a value close to `0` (bit `0`) or close to `q/2` (bit `1`), with the small noise term not disturbing which side of that boundary the result falls on. **The security argument, demonstrated directly:** attempting to recover the secret `s` via naive linear algebra (solving `As=b` directly, ignoring the noise and the modular structure) produces values wildly different from the true `s` — verified: the true secret's components (values like `2701, 285, 597...`, mod `3329`) bear no resemblance to what a direct linear solve returns (`2.527, -2.293, -0.695...`). The noise term is precisely what defeats the direct linear-algebra attack, and — critically — this obstruction has nothing to do with the classical-versus-quantum distinction the way factoring does: there's no known quantum algorithm (Shor-style or otherwise) that exploits LWE's structure the way period-finding exploits factoring's, because LWE lacks the abelian group structure the QFT-based approach depends on. Real ML-KEM uses **Module-LWE** — the same underlying hardness assumption, but operating over polynomial rings for major efficiency gains — not the plain-vector LWE shown here, but the core noisy-linear-equation hardness intuition is identical.

### What Grover weakens, precisely, with real numbers

Module 3 covered the mechanism (quadratic brute-force speedup, provably optimal, not exponential); here are the numbers that actually drive migration decisions:

| Primitive | Classical security | Grover-adjusted (quantum) security | Action |
|---|---|---|---|
| AES-128 | 128 bits | 64 bits | **Retire for new long-lived-sensitivity use** — 64-bit security is not adequate against a sufficiently resourced quantum adversary, even accounting for the substantial hardware Grover's algorithm itself would still require |
| AES-256 | 256 bits | 128 bits | **Adequate, no replacement needed** — 128-bit effective security remains a comfortable margin |
| SHA-256 (preimage) | 256 bits | 128 bits | Adequate for most purposes; CNSA 2.0 specifies SHA-384/SHA-512 for extra margin in national-security contexts |
| SHA-256 (collision) | ~128 bits (birthday bound, module "crypto-primitives" T22) | ~128 bits (essentially unaffected — collision search was already at the birthday bound classically, and known quantum collision-finding algorithms like BHT don't achieve the same quadratic gain preimage search does, due to memory-query tradeoffs) | Adequate |

The practical upshot, stated precisely because this is the exact distinction most commonly muddled: **symmetric cryptography and hashing need resizing, not algorithm replacement.** This is a fundamentally cheaper, lower-risk migration than the public-key replacement Shor's algorithm forces — AES-256 and SHA-384/512 usage is already largely in place across modern systems, and the remaining work is auditing for any lingering AES-128 or SHA-1/SHA-256-only usage in long-lived-sensitivity contexts, not a wholesale algorithm swap.

### Signature and key sizes: the real, concrete migration cost

This is the number that actually determines protocol and infrastructure impact, and it's dramatic:

| Scheme | Type | Public key size | Signature/ciphertext size |
|---|---|---|---|
| ECDSA (P-256) | Classical signature | ~64 bytes | ~64-72 bytes |
| RSA-2048 | Classical signature/KEM | ~256 bytes | ~256 bytes |
| ML-KEM-768 | PQC KEM | 1,184 bytes | 1,088 bytes |
| ML-DSA-65 | PQC signature | ~1,952 bytes | 2,420-4,595 bytes (varies by parameter set) |
| SLH-DSA | PQC signature (hash-based, conservative) | small | 7,856-49,856 bytes |

`ML-DSA` signatures run roughly **30-70x larger** than `ECDSA`, and `SLH-DSA` signatures run **over 100x larger** in some parameter sets — this is not a minor implementation detail. It directly impacts TLS handshake size (contributing to the middlebox breakage covered above), certificate chain size (multiple signatures compound), bandwidth-constrained protocols, and storage/memory budgets on embedded or IoT devices with hard resource ceilings. `SLH-DSA`'s much larger signatures are the direct cost of its conservative, hash-only security assumption — a real, explicit tradeoff between cryptographic conservatism and practical deployability that a migration plan has to make deliberately, not by default.

### Hybrid key exchange: why combine classical and PQC rather than switch outright

A hybrid TLS key exchange (`X25519MLKEM768`) derives the session key from **both** the classical `X25519` shared secret and the `ML-KEM-768` shared secret, combined through a key-derivation function, such that **the connection remains secure if either algorithm remains unbroken** — an attacker needs to break both simultaneously to compromise the session. This is the concrete, defensible reasoning for recommending hybrid over PQC-only during the transition: `ML-KEM` is new (finalized 2024) and, despite NIST's rigorous multi-year public process, has had a fraction of the real-world cryptanalytic scrutiny `X25519`/`ECC` have accumulated over decades — hybrid deployment hedges against an undiscovered implementation bug or an unexpected weakness in the newer algorithm without giving up any of the quantum-resistance benefit, at the cost of larger handshake messages (the exact tradeoff behind the 2024 middlebox breakage above).

---

## Build it from scratch

The toy LWE encryption scheme verified above — genuinely runnable, no external cryptography libraries needed, and it uses the actual `q=3329` modulus real ML-KEM/Kyber implementations use:

```python
import numpy as np

n, q, m = 12, 3329, 40
rng = np.random.default_rng(3)

s = rng.integers(0, q, size=n)                   # secret key
A = rng.integers(0, q, size=(m, n))               # public matrix
e = rng.integers(-2, 3, size=m)                   # small noise
b = (A @ s + e) % q                                # public key: b = As + e (mod q)

def encrypt_bit(bit):
    subset = rng.choice(m, size=m // 2, replace=False)
    a_sum = A[subset].sum(axis=0) % q
    b_sum = b[subset].sum() % q
    if bit == 1:
        b_sum = (b_sum + q // 2) % q
    return a_sum, b_sum

def decrypt(a_sum, b_sum):
    pred = (b_sum - a_sum @ s) % q
    dist_to_0 = min(pred, q - pred)
    dist_to_half = abs(pred - q // 2)
    return 0 if dist_to_0 < dist_to_half else 1

# encrypting and decrypting 8 random bits: 8/8 correct, verified above
```

This is a deliberately simplified illustration (real ML-KEM adds polynomial-ring structure, proper noise sampling distributions, and IND-CCA2 security hardening well beyond this toy's scope) — but the core mechanism, the thing actually worth being able to derive in an interview, is exactly this: noisy linear equations that resist direct linear-algebra recovery, with no known efficient recovery algorithm, classical or quantum, for appropriately chosen parameters.

---

## How it's done in production

| Component | Current state (2026) |
|---|---|
| TLS 1.3 hybrid key exchange | `X25519MLKEM768` live in Chrome (since v124, April 2024) and Cloudflare's edge (since 2022 in draft form, standardized form since late 2024); ~30% of TLS 1.3 handshakes globally per Cloudflare Radar |
| Code signing / firmware signing | CNSA 2.0 requires exclusive quantum-resistant signing from January 1, 2027 for covered systems — an early, concrete deadline given how long-lived signed firmware/code can remain trusted |
| Certificate Authorities / PKI | Hybrid certificates (classical + PQC signatures in one certificate, or dual-issued certificate chains) are an active transition mechanism; full PQC-only PKI remains early-stage |
| Library/OS support | OpenSSL 3.x, BoringSSL, and AWS-LC all have production ML-KEM/ML-DSA support as of 2026; verify specific version and configuration before assuming availability in any given deployment |

| Symptom | Cause | Fix |
|---|---|---|
| TLS handshakes fail or time out after enabling hybrid key exchange, specifically for users behind corporate networks | TLS-inspecting middleboxes/enterprise proxies choking on larger `ClientHello` messages hybrid KEMs produce — this is exactly what happened during Chrome's 2024 rollout | Test against representative enterprise middlebox configurations before broad rollout; expect this class of compatibility issue and plan a staged rollout with monitoring, not a flag-flip |
| Certificate chain size or TLS handshake bandwidth increases significantly after migrating signatures to ML-DSA | ML-DSA signatures are 30-70x larger than ECDSA — a real, unavoidable protocol overhead, not a misconfiguration | Budget for this explicitly in bandwidth-constrained or high-volume-connection contexts; consider where SLH-DSA's even-larger signatures are and aren't appropriate (long-lived, infrequent signing — e.g., root CA certificates — versus high-frequency signing) |
| An embedded/IoT device can't fit ML-DSA or SLH-DSA keys/signatures in its constrained storage or bandwidth budget | Real, currently unresolved tension between PQC's larger footprint and embedded hardware constraints | Prioritize such devices for hybrid or classical-only short-term with a documented compensating control (network segmentation, shorter cert lifetimes) while monitoring for smaller-footprint PQC schemes or hardware upgrades |
| A migration project stalls trying to inventory every place RSA/ECC is used across the organization | Cryptographic inventory is routinely underestimated — certificates, embedded device firmware, internal service-to-service TLS, VPN configs, code-signing keys, and legacy protocols are easy to miss | Treat inventory as its own dedicated project phase with tooling support (certificate transparency log scanning, network traffic analysis, dependency scanning for crypto library usage), not a checklist item folded into a broader migration timeline |

---

## Tradeoffs & when NOT to use it

- **Don't panic-migrate everything to PQC-only overnight.** No credible timeline requires this today, hybrid gets the quantum-resistance benefit with a hedge against new-algorithm risk, and an uncoordinated rip-and-replace is far more likely to cause outages than a cryptographically relevant quantum computer is to appear in the next few years.
- **Don't treat AES-256/SHA-384 resizing and RSA/ECC replacement as equally urgent.** They are fundamentally different classes of problem — resizing is low-risk and often already substantially complete; algorithm replacement is the genuinely hard, multi-year migration that needs prioritization.
- **Don't deploy PQC-only in place of hybrid during the transition period**, per NSA's own explicit CNSA 2.0 guidance through 2030 — the newer algorithms deserve the same skepticism this track applies to any new, less-battle-tested cryptographic primitive, regardless of how rigorous the standardization process was.
- **Don't skip cryptographic inventory to jump straight to "deploy ML-KEM everywhere."** You cannot migrate what you haven't found, and this step is reliably the most underestimated part of every real migration project, PQC or otherwise (the same lesson from SHA-1's decade-plus-long deprecation).
- **Do prioritize by harvest-now-decrypt-later exposure, not by convenience.** Data with long confidentiality requirements (health records, genomic data, state secrets, long-lived intellectual property, anything under a multi-decade legal retention/confidentiality obligation) that's transmitted or stored with vulnerable algorithms today is already at risk regardless of when the hardware threat materializes — this should rank above lower-sensitivity or short-lived data in any resourced migration plan.

---

## Interview questions

### Q1 — Which cryptographic primitives does Shor's algorithm break, and which does it leave essentially untouched?
**Testing:** the single most load-bearing fact in this module, checked for precision.
**Answer:** Shor's algorithm completely breaks RSA (factoring), Diffie-Hellman (discrete log), and ECC/ECDSA (elliptic-curve discrete log) — all public-key schemes resting on the abelian hidden subgroup structure it exploits. It has no direct bearing on symmetric cryptography (AES) or hash functions (SHA-256) — those are only affected by Grover's algorithm, a completely different, much weaker (quadratic) threat.
**Follow-up trap:** *"So does that mean AES and SHA-256 need no changes at all for the post-quantum era?"* — not quite "no changes," precisely: AES-256 and SHA-384/512 are adequate as-is (their Grover-adjusted security remains a comfortable 128+ bits), but AES-128 and any use case relying on SHA-256's full 256-bit preimage margin should be resized upward — this is resizing, not replacement, and it's a materially cheaper and lower-risk exercise than the RSA/ECC migration.

### Q2 — Walk through why AES-256 is considered adequate against quantum attack but AES-128 is not.
**Testing:** the actual numbers behind the "double your key length" guidance, not just the guidance itself.
**Answer:** Grover's algorithm gives a quadratic brute-force speedup, converting an `n`-bit key's classical security into an effective `n/2`-bit quantum security. AES-256 drops to effective 128-bit security, which remains computationally infeasible to brute-force even accounting for a capable quantum adversary. AES-128 drops to effective 64-bit security, which is within reach of sufficiently resourced brute-force attack (classical or quantum) and should not be relied on for new long-lived-sensitivity data.
**Follow-up trap:** *"Is 64-bit security immediately breakable today by an actual quantum computer?"* — no; current hardware is nowhere near running Grover's algorithm against a real 128-bit key search space at any practical speed (module 5's NISQ limitations apply here too) — the "retire AES-128" guidance is about eliminating unnecessary future risk in long-lived-sensitivity data now, not responding to an imminent capability, exactly parallel to why RSA/ECC migration is prioritized by data lifetime rather than by claimed hardware arrival dates.

### Q3 — What are the three NIST PQC standards finalized in August 2024, and what specific mathematical problem does each rest on?
**Testing:** current, specific knowledge — not "NIST picked some new algorithms."
**Answer:** ML-KEM (FIPS 203, key encapsulation) and ML-DSA (FIPS 204, signatures) both rest on Module Learning With Errors / Module Short Integer Solution — lattice-based problems. SLH-DSA (FIPS 205, signatures) rests only on hash-function collision resistance — deliberately not a lattice assumption, making it a conservative fallback with a different, older, more thoroughly analyzed hardness basis.
**Follow-up trap:** *"Why would you ever use the much-larger SLH-DSA over ML-DSA if ML-DSA is already standardized and smaller?"* — for the highest-assurance, longest-lived signing contexts (root CA certificates, firmware signing) where SLH-DSA's much older, hash-only security assumption is worth its 3-20x larger signature size as insurance against a future lattice-cryptanalysis surprise — this is precisely why NIST also added HQC (a non-lattice KEM) in 2025, as the same diversification logic applied to key encapsulation.

### Q4 — Why was HQC added as an additional standard in 2025, given ML-KEM was already finalized in 2024?
**Testing:** understanding cryptographic diversification as a deliberate risk-management strategy, not a redundant afterthought.
**Answer:** ML-KEM and ML-DSA both rest on lattice-family hardness assumptions; if a future cryptanalytic breakthrough weakened lattice problems generally, both the primary standardized KEM and the primary standardized signature scheme could be compromised simultaneously. HQC rests on a mathematically distinct hardness assumption (code-based, not lattice-based), so standardizing it as an alternative KEM specifically hedges against exactly that correlated-failure scenario.
**Follow-up trap:** *"Should an organization deploy HQC alongside ML-KEM today as a matter of course?"* — not necessarily by default; HQC is newer to standardization than ML-KEM and has had less deployment scrutiny so far, so the practical near-term recommendation for most organizations is hybrid classical+ML-KEM (the combination with the most production deployment experience as of 2026), while treating HQC as a documented contingency/diversification option to have ready, not a mandatory parallel deployment for every system today.

### Q5 — Derive, mechanically, why a noisy linear system (LWE) resists the same Gaussian-elimination attack that would trivially break a noiseless one.
**Testing:** the actual mathematical mechanism behind lattice-based cryptography's hardness, verified not just asserted.
**Answer:** Without noise, `b=As` is a solvable linear system — `s=A⁻¹b` for a square, invertible `A`. With noise, `b=As+e mod q` for small but nonzero `e`, and solving directly for `s` via linear algebra (ignoring the noise) produces a value that, once you're working over the reals rather than exactly modulo `q` with error tolerance, is wildly wrong — verified directly: a true secret with components like `2701, 285, 597...` (mod 3329) bears no resemblance to what naive real-valued linear solving on the same system returns (`2.527, -2.293, -0.695...`). The noise breaks the exactness Gaussian elimination depends on, and recovering `s` given only noisy equations is the LWE problem, believed hard for appropriately chosen parameters (dimension, modulus, noise distribution) against both classical and quantum algorithms.
**Follow-up trap:** *"Is this the same reason quantum computers can't break LWE, or a coincidence that it's also hard classically?"* — not a coincidence, but also not quite "the same reason": LWE's presumed classical hardness comes from the noise defeating linear algebra as shown; its presumed *quantum* hardness specifically comes from LWE not being known to reduce to the abelian hidden subgroup problem the way factoring does, so Shor's QFT-based approach (module 3) has no known foothold — these are two separate (though related) arguments, and conflating "hard classically" with "therefore also hard quantumly" is exactly the mistake RSA's security assumption fell into.

### Q6 — Why does NSA's CNSA 2.0 guidance recommend hybrid deployment through 2030 rather than moving straight to PQC-only, despite PQC algorithms already being standardized?
**Testing:** the actual risk-management reasoning behind hybrid-first, not just "it's the recommended practice."
**Answer:** ML-KEM and ML-DSA, despite NIST's rigorous multi-year public cryptanalysis process, have had a small fraction of the real-world scrutiny RSA and ECC have accumulated over their multi-decade deployment history — hybrid deployment (deriving session security from both a classical and a post-quantum algorithm) means an attacker must break *both* simultaneously to compromise the connection, hedging against an as-yet-undiscovered weakness or implementation flaw in the newer algorithm without sacrificing any of the quantum-resistance benefit.
**Follow-up trap:** *"Doesn't hybrid deployment just mean you're paying the overhead cost of PQC (larger keys/signatures) without fully committing to its benefit?"* — no, this framing is backwards: hybrid gets the *full* quantum-resistance benefit (security holds if ML-KEM remains unbroken) while additionally retaining classical security as a hedge — it's strictly more conservative than PQC-only, not a partial or hesitant version of it, at the real but bounded cost of larger handshake messages (the exact tradeoff behind the 2024 middlebox compatibility issue).

### Q7 — What's the practical significance of ML-DSA signatures being 30-70x larger than ECDSA signatures?
**Testing:** whether size numbers translate into real system-design consequences, not just an abstract fact.
**Answer:** Larger signatures directly inflate TLS handshake size (contributing to the exact middlebox compatibility failures seen in Chrome's 2024 rollout), certificate chain size (compounding across multiple signatures in a chain), bandwidth usage for high-signing-volume protocols, and storage/memory budgets on constrained embedded or IoT devices — this isn't an abstract inconvenience, it's a concrete constraint that determines which systems can adopt PQC signatures easily versus which need dedicated engineering work or a documented interim compensating control.
**Follow-up trap:** *"If size is such a problem, why not just use SLH-DSA's smaller variants or wait for smaller future PQC signature schemes?"* — SLH-DSA's signatures are actually *larger* than ML-DSA's in most parameter sets (7,856-49,856 bytes versus ML-DSA's 2,420-4,595), not smaller — it trades size for a more conservative security assumption, the opposite direction from what this question's premise assumes. Waiting for smaller future schemes is a legitimate long-term research bet (NIST has signaled intent to keep evaluating additional signature schemes) but isn't a substitute for a near-term migration plan for systems that need PQC readiness on CNSA 2.0's actual timeline.

### Q8 — A CISO asks: "Should we replace our RSA-2048 root CA today, given quantum computers don't exist yet that can break it?" What's your answer?
**Testing:** synthesizing the whole module into an actual, defensible executive-facing recommendation.
**Answer:** Not an emergency rip-and-replace today, but start now regardless: root CA rotation is itself a multi-year undertaking under normal circumstances (certificate lifetimes, dependent system updates, trust-store propagation), CNSA 2.0's timeline puts full exclusive-use requirements for OS/application/cloud contexts at 2033 with earlier gates starting 2027, and root CAs specifically are exactly the kind of long-lived, high-consequence-if-compromised asset harvest-now-decrypt-later logic argues for prioritizing early — not because Shor's algorithm is imminent, but because the multi-year migration timeline itself needs to start well before any hard deadline, and hybrid or dual-signed certificate approaches let you begin the transition without disrupting current trust relationships.
**Follow-up trap:** *"What if leadership pushes back that this is premature given the hardware uncertainty covered in module 5?"* — the correct response separates two different questions: hardware timeline uncertainty (genuinely wide, 5-30 years per expert estimates) affects how urgently you frame the *messaging*, but it does not change the *recommended action*, because the migration itself takes years regardless of exactly when the threat materializes, and doing nothing while waiting for certainty guarantees starting later than optimal under any actual hardware timeline that turns out to be true — this is a decision-under-uncertainty argument, not a specific-date prediction, and framing it that way is what survives leadership pushback.

### Q9 — Your team stores health records with a 25-year confidentiality requirement, currently encrypted with RSA-2048-derived keys in transit and AES-256 at rest. Rank the priority of addressing each, and explain why.
**Testing:** applying the harvest-now-decrypt-later prioritization framework to a concrete, realistic data-sensitivity scenario.
**Answer:** The RSA-2048 key exchange in transit is the higher-priority item by a wide margin: if an adversary is recording this traffic today (harvest-now-decrypt-later), the 25-year confidentiality window means the data needs to remain protected well past any plausible hardware timeline estimate, and RSA-2048 offers zero protection once Shor's algorithm becomes practically runnable — this needs hybrid or PQC key exchange, prioritized ahead of lower-sensitivity or shorter-lived data elsewhere in the organization. The AES-256 at-rest encryption, by contrast, is already adequate (Grover-adjusted 128-bit security comfortably covers a 25-year horizon under any credible hardware timeline) and needs no urgent action beyond confirming it's genuinely AES-256 and not a weaker variant.
**Follow-up trap:** *"Does moving to a PQC key exchange for transit fully solve the problem, or is anything else at risk?"* — transit protection going forward doesn't retroactively protect *already-recorded* traffic from before the migration — if an adversary has been harvesting this traffic already, migrating today protects future transmissions but the already-exposed historical data remains at risk once a CRQC exists, which is precisely why "the migration clock started at record time, not decrypt time" (this module's framing) matters: earlier migration directly reduces the total window of exposed historical data, it doesn't erase exposure that already occurred.

### Q10 — Design check: a startup's engineering lead proposes deploying ML-KEM-only (no classical hybrid) for a new product's TLS layer, arguing "why pay the overhead of hybrid when the PQC algorithm is already NIST-standardized and secure?" Evaluate this proposal.
**Testing:** staff-level pushback on a plausible-sounding but risky simplification, synthesizing the hybrid-vs-PQC-only reasoning.
**Answer:** Recommend against PQC-only for a production system today, even for a brand-new product with no legacy constraint forcing hybrid: NIST standardization (a rigorous process) is not the same as "battle-tested at the scale and adversarial scrutiny RSA/ECC have received over decades," and NSA's own CNSA 2.0 guidance explicitly recommends hybrid through 2030 for exactly this reason — a genuinely new algorithm deserves the same skepticism this track applies throughout to any new, less-scrutinized cryptographic primitive. The overhead argument is real (larger handshakes, the middlebox compatibility risk covered above) but modest relative to the downside of an undiscovered flaw in a sole, unhedged PQC dependency, especially for a system with any meaningful lifetime.
**Follow-up trap:** *"Is there ever a legitimate case for PQC-only over hybrid?"* — yes, narrowly: extremely resource-constrained embedded contexts where hybrid's additional overhead genuinely doesn't fit the device's budget might justify PQC-only with a compensating control (shorter key/cert lifetimes, network segmentation, closer monitoring) as a deliberate, documented tradeoff — but this should be an explicit, reviewed exception justified by specific constraints, not a default architectural choice made to avoid a modest and well-understood overhead cost.

---

## Red flags that fail you

- Claiming AES-256 or SHA-256 need to be "replaced" for post-quantum readiness, rather than correctly identifying this as a resizing (not replacement) issue.
- Not knowing the specific NIST PQC standard names (ML-KEM/FIPS 203, ML-DSA/FIPS 204, SLH-DSA/FIPS 205) or conflating them with their pre-standardization names without noting the correspondence.
- Recommending PQC-only deployment over hybrid during the current transition period without acknowledging NSA/NIST's explicit hybrid-first guidance and its rationale.
- Treating "quantum computers don't exist yet" as a reason to defer all post-quantum migration planning, ignoring harvest-now-decrypt-later.
- Being unable to explain, even at a high level, why lattice problems resist Shor's algorithm specifically (not just "they're different math").
- Not knowing PQC signatures/keys are dramatically larger than classical ones, or being unable to name a concrete operational consequence of that size difference.

---

## Cheat card

```
SHOR BREAKS COMPLETELY: RSA (factoring), Diffie-Hellman (discrete log), ECC/ECDSA (EC discrete
  log) -- all rest on the abelian hidden subgroup structure Shor's algorithm exploits (module 3).
GROVER ONLY WEAKENS (quadratic, not exponential): AES-256->effective 128-bit (FINE). AES-128->
  effective 64-bit (RETIRE for long-lived data). SHA-256 preimage 256->128-bit (fine); collision
  resistance ~128-bit already via birthday bound, essentially UNAFFECTED by Grover.
NIST PQC STANDARDS (finalized Aug 2024): ML-KEM/FIPS 203 (KEM, lattice/Module-LWE, ex-Kyber),
  ML-DSA/FIPS 204 (signatures, lattice/Module-LWE+SIS, ex-Dilithium), SLH-DSA/FIPS 205
  (signatures, HASH-ONLY assumption, conservative fallback, ex-SPHINCS+). HQC (code-based KEM,
  non-lattice hedge) added 2025.
WHY LATTICE RESISTS SHOR: LWE = noisy linear equations (b=As+e mod q). Noise defeats Gaussian
  elimination (verified: true secret components ~2701,285,597...; naive real-solve gives
  2.527,-2.293,-0.695... -- unrecoverable). NOT known to reduce to abelian hidden subgroup problem
  -> no known Shor-style quantum attack. Real ML-KEM uses Module-LWE (polynomial rings) for efficiency.
SIZE COST (real migration constraint): ECDSA sig ~64-72B. ML-DSA sig 2,420-4,595B (30-70x larger).
  SLH-DSA sig 7,856-49,856B (even larger -- conservative hash-only assumption's explicit price).
HARVEST-NOW-DECRYPT-LATER: adversary records ciphertext TODAY, decrypts once CRQC exists. Clock
  starts at RECORD time, not decrypt time -- already a present-day risk for long-lived-sensitivity data.
HYBRID KEY EXCHANGE (X25519MLKEM768): secure if EITHER classical OR PQC half holds. NSA CNSA 2.0
  explicitly recommends hybrid THROUGH 2030 -- newer PQC algos have far less real-world scrutiny
  than decades-old RSA/ECC despite rigorous NIST standardization.
DEPLOYED 2026: Chrome (v124+, Apr 2024) + Cloudflare hybrid KEX -- ~30% of TLS 1.3 handshakes
  globally (Cloudflare Radar). ~50% of measured domains still fully classical, zero PQC readiness.
  2024 Chrome rollout ROLLED BACK once (enterprise middlebox ClientHello-size breakage), then fixed.
CNSA 2.0 TIMELINE: 2027 new-acquisition gate -> 2030 legacy/networking transition -> 2031
  mandatory (covered categories) -> 2033 OS/apps/cloud exclusive use -> 2035 full NSS quantum resistance.
MIGRATION ORDER: 1) crypto inventory (hardest, most underestimated step) 2) prioritize by
  harvest-now-decrypt-later exposure (data sensitivity duration x current exposure) 3) hybrid
  deployment 4) build crypto-agility (swap algorithms without full rearchitecture).
```

## Sources

- [NIST Post-Quantum Cryptography Standards: Complete Guide to FIPS 203, 204, 205 — QRAMM](https://qramm.org/learn/nist-pqc-standards.html) — accessed 2026-08-08
- [CNSA 2.0: NSA's Quantum-Resistant Cryptography — Entrust](https://www.entrust.com/resources/learn/what-is-cnsa-2-0) — accessed 2026-08-08
- [From X25519 to X25519+MLKEM768: How Hybrid TLS Is Becoming Real — postquantumsecurity.org](https://www.postquantumsecurity.org/publications/X25519+MLKEM768.html) — accessed 2026-08-08
- [Measurement Study of Post-Quantum Readiness of Internet: 2026 — arXiv](https://arxiv.org/pdf/2606.16473) — accessed 2026-08-08
- [Regev, O. — On Lattices, Learning with Errors, Random Linear Codes, and Cryptography (2005, foundational LWE paper)](https://cims.nyu.edu/~regev/papers/qcrypto.pdf) — accessed 2026-08-08
- [Quantum Security Deadlines are Here — What Happens Next? — The Quantum Insider](https://thequantuminsider.com/2026/05/08/post-quantum-migration-timelines-government-industry-impact/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
