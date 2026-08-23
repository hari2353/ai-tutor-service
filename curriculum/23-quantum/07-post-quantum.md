# Post-Quantum Cryptography: What Breaks, When, and Migration Plans

> **Track:** T23 Quantum Computing · **Time:** 2h · **Prereqs:** T23-algorithms · **Updated:** 2026-08-23
> **Module id:** `T23-post-quantum` · **Tags:** security, critical

## The 30-second version

Shor's algorithm factors integers and solves discrete logs in polynomial time, which kills RSA, Diffie-Hellman, ECDSA, and ECDH outright once fault-tolerant machines exist; estimates for RSA-2048 cluster at millions of physical qubits running hours, credibly mid-2030s. Grover only halves symmetric strength, so AES-256 and SHA-384 survive; you do not replace symmetric crypto, you size it up. NIST finalised the replacements on August 13, 2024: FIPS 203 (ML-KEM, from CRYSTALS-Kyber) for key exchange, FIPS 204 (ML-DSA, from CRYSTALS-Dilithium) for signatures, FIPS 205 (SLH-DSA, hash-based SPHINCS+) as conservative backup, with FN-DSA (Falcon) and HQC (selected March 2025) following. The operational driver is harvest-now-decrypt-later: traffic recorded today falls to a future quantum computer, so externally-facing key exchange migrates first, via hybrid X25519+ML-KEM-768, which already covers over half of human web traffic through Cloudflare as of late October 2025. Signatures carry no retroactive risk but are operationally harder (PKI, firmware, code signing), and the planning dates are NIST IR 8547's proposed 2030 deprecation / 2035 removal plus NSA CNSA 2.0's 2027 acquisition mandate.

## Why this gets asked

Because every backend engineer owns pieces of this migration whether or not they know it: TLS termination configs, JWT signing keys, certificate lifecycles, HSM inventories, and third-party dependency lists all contain quantum-vulnerable cryptography today. Interviewers at any company handling long-lived confidential data ask this to find out three things: whether you can state precisely what breaks and what doesn't (candidates who say "quantum computers break all encryption" fail immediately), whether you understand why key exchange and signatures have different urgencies despite both dying to Shor, and whether you can run an actual migration program rather than recite algorithm names. There is also a live compliance angle: US federal contractors face CNSA 2.0 requirements starting January 2027, FIPS 140-2 certificates moved to historical status in September 2026, and enterprises that sell into regulated markets are already receiving customer questionnaires about PQC readiness. The senior signal is a concrete sequencing answer, not enthusiasm.

---

## Lineage: past → present → future

**What came before.** Shor's 1994 algorithm created the threat; the response took two decades to organise. NIST announced the formal competition in 2016 (following its 2015 report calling for quantum-resistant standards), received 82 candidates in 2017, and ran four elimination rounds. The process itself demonstrated why standardisation is hard: SIKE, an isogeny-based favourite, fell to a classical attack (Castryck-Decru, July 2022) weeks after being flagged as alternate; Rainbow, a multivariate signature finalist, was broken by Ward Beullens in February 2022 with a weekend-computable attack after surviving three rounds. Both breaks used classical mathematics, proving the point that "not RSA" is not a security proof.

**Where it stands now.** Standards exist and deployment is measurable: FIPS 203/204/205 published August 13, 2024; HQC added as a code-based KEM backup March 11, 2025 (NIST IR 8545); FN-DSA (Falcon) in development as FIPS 206. Browser support for hybrid X25519MLKEM768 shipped in Chrome and Firefox during 2024; Cloudflare reported crossing 50% of human-sourced web traffic using it in late October 2025; Signal deployed PQXDH (September 2023) and Apple iMessage PQ3 (February 2024). OpenSSL gained native ML-KEM in 3.5 (April 2025). On the mandate side: NSA CNSA 2.0 requires PQC in new National Security System acquisitions from 2027 with exclusive-use windows through 2033; NIST IR 8547 proposes deprecating RSA-2048/ECC-P256 around 2030 and disallowing them entirely by 2035 (still Initial Public Draft as of August 2026, so treat dates as strong signals, not law); Google committed to completing internal migration by 2029 (announced March 2026). Live disagreement: how much hybrid overhead is worth, and whether ML-DSA alone suffices or hash-based backups need wider deployment.

**Where it's heading.** Expect hybrid-only KEM deployment through roughly 2027-2028, then gradual pure-PQC once implementation confidence accumulates; signature migration lags because certificate ecosystems, HSM firmware, and embedded devices move slowest, which is why CNSA 2.0 gives custom applications until 2033. Confidence levels: high that the FIPS algorithms hold (lattice problems have thirty years of scrutiny and survived the competition's cryptanalysis wars); medium on timeline precision, since IR 8547 remains draft; near-certain that harvest-now-decrypt-later makes waiting the expensive option regardless of when Q-day lands.

---

## Mental model

Two clocks ticking at different speeds on two different assets:

```
CONFIDENTIALITY (KEM/key exchange)        AUTHENTICATION (signatures)
TLS, VPNs, E2E messaging                  JWTs, certs, code signing
                                          firmware, root CAs
THREAT: harvest-now-decrypt-later         THREAT: none until Q-day
recorded today, broken later              (forgery needs the QC present)
URGENCY: migrate NOW (hybrid)             URGENCY: inventory now,
                                          rotate 2027-2033
WHY: data already left your perimeter     WHY: nothing retroactive to steal,
                                          but rotation is slowest here
```

The asymmetry drives all sequencing decisions: key-exchange migration is urgent because the attack is retroactive, signature migration is slow because the dependency graph (root CAs, HSMs, embedded verifiers) is huge, and neither urgency comes from a quantum computer existing yet. The third model to carry: **crypto agility**. The SIKE/Rainbow breaks during standardisation proved algorithms can die classically; systems that hardcode one primitive repeat this migration forever. Treat "swap algorithm via config" as an architectural requirement, not a nice-to-have.

## How it actually works

### What Shor actually breaks, precisely

Shor solves two mathematical problems in polynomial time: integer factorisation (period of f(x) = aˣ mod N) and discrete logarithm in any abelian group (hidden subgroup over ℤ), which covers finite-field DH and all elliptic-curve groups used in TLS. Everything built solely on those falls together: RSA encryption/signatures, DH/ECDH key agreement, ECDSA/EdDSA signatures, BLS-style aggregate schemes. What survives: symmetric primitives (Grover gives quadratic search speedup only: AES-128's 2¹²⁸ keyspace drops to ~2⁶⁴ quantum operations, so AES-256 → effective 2¹²⁸ remains safe; SHA-2 preimages likewise halve, with collision resistance degrading more via BHT-style attacks to ~2^(n/3), hence guidance to prefer SHA-384 for long-lived structures). HMAC and KMAC constructions remain sound with adequate output lengths. This clean split, public-key dies, symmetric weakens-and-survives, is the answer interviewers want word-for-word.

### Why lattice problems resist: the one-paragraph theory

ML-KEM/ML-DSA rest on Module Learning-With-Errors (M-LWE) and Short-Integer-Solution problems: solve noisy linear systems mod q where each equation carries small random error. No known quantum reduction turns them into hidden-subgroup problems; their abelian structure that powers Shor is absent, and worst-case-to-average-case reductions (Regev 2005, for LWE) mean breaking random instances implies breaking worst-case instances of related lattice problems. Thirty years of cryptanalysis have produced only polynomial-factor improvements, and the competition process actively tried to kill candidates (Rainbow and SIKE died to classical math). Caveat worth stating honestly: confidence is empirical depth of scrutiny, not proof, which is exactly why hybrid deployment exists.

### The concrete numbers of ML-KEM (Kyber)

Parameter sets and wire sizes you will actually quote:

| Scheme | Role | Public key | Ciphertext/Sig | Shared secret |
|---|---|---|---|---|
| ML-KEM-512 | conservative minimum | 800 B | 768 B | 32 B |
| ML-KEM-768 | default target | 1,184 B | 1,088 B | 32 B |
| ML-KEM-1024 | high security | 1,568 B | 1,568 B | 32 B |
| ML-DSA-44/65/87 | signatures | 1,312/1,952/2,592 B | 2,420/3,309/4,627 B | — |
| SLH-DSA-128s/256s | hash-based backup | 32/64 B | ~7,856/17,064 B | — |

Operational consequences: hybrid X25519+ML-KEM-768 adds roughly 2 KB per TLS handshake (negligible versus typical payloads, visible on embedded MTU-constrained links); ML-DSA signatures are 4-10× larger than EdDSA's 64 bytes, which matters for JWT headers, certificate chains (a full chain of ML-DSA certs adds tens of KB), and DNSSEC-style constrained records; ML-KEM keygen+encaps runs in tens of microseconds on commodity CPUs (faster than RSA-2048 private operations by an order of magnitude); SLH-DSA signs slowly (hash-tree traversals) and suits firmware/root-of-trust signing cadence, not per-request workloads.

### Migration plan, sequenced like a real program

1. **Inventory (CBOM)**: enumerate every cryptographic asset: TLS libs and configs, JWT/JWS signers, cert chains, HSMs, SSH configs, VPNs, embedded firmware, vendor dependencies. Automate discovery (tools: CBOMkit-class scanners, sigstore provenance checks); manual lists rot.
2. **Data longevity classification**: for each data flow, how long must confidentiality hold? Anything beyond ~2033 is at HNDL risk today; classify and prioritise by (sensitivity × exposure window).
3. **Key exchange first, hybrid**: enable X25519MLKEM768 (or P384_MLKEM768 for CNSA contexts) on external TLS endpoints; OpenSSL ≥3.5, BoringSSL, AWS-LC all ship it; watch middlebox handshake-failure telemetry and keep classical fallback enabled during rollout.
4. **Vendor/supply-chain pressure**: questionnaires to SaaS vendors, HSM vendors (FIPS 140-3 validation status mandatory for US federal from September 2026 when 140-2 certificates went historical), CA/browser forum tracking for PQC cert profiles.
5. **Signatures second**: rotate code signing and firmware to ML-DSA (or SLH-DSA/LMS for long-lived artifacts); PKI migration last because root rotation cascades; short-lived certificates ease eventual cutover.
6. **Agility engineering**: abstract algorithm choice behind configuration; test dual-stack operation; rehearse algorithm rollback so the next transition is config, not archaeology.

## Build it from scratch

A working toy of the math inside ML-KEM: Regev-style LWE public-key encryption over a small modulus, pure numpy. It encrypts/decrypts correctly and demonstrates why breaking it means solving noisy linear systems rather than factoring. Runnable:

```python
import numpy as np

rng = np.random.default_rng(3)
n, q, m = 8, 97, 24            # dimension, modulus, #samples (TOY sizes!)

def keygen():
    s = rng.integers(0, q, size=n)              # secret
    A = rng.integers(0, q, size=(m, n))         # random matrix
    e = rng.integers(-2, 3, size=m)             # small noise
    b = (A @ s + e) % q                         # noisy samples
    return s, (A, b)                            # secret, public key

def encrypt(pk, bit):
    A, b = pk
    r = rng.integers(0, 2, size=m)              # random subset selector
    u = r @ A % q                               # n-dim vector
    v = (r @ b + bit * (q // 4)) % q            # offset by ~q/4 if 1
    return u, int(v)

def decrypt(s, ct):
    u, v = ct
    diff = (v - u @ s) % q                      # ≈ 0 or ≈ q/4 mod q
    return 1 if min(diff, q - diff) > q // 8 else 0

s, pk = keygen()
msgs = [0, 1, 1, 0, 1]
ok = all(decrypt(s, encrypt(pk, x)) == x for _ in range(100) for x in msgs)
print("LWE toy decrypts correctly:", ok)
```

Verified output: `True` across all trials. The decryption identity works because (v − u·s) mod q collapses the noise to |Σrᵢeᵢ| ≤ m·max|e|, far below q/4 at these parameters; real ML-KEM uses n=768-1568 with error distributions and a Fujisaki-Okamoto transform converting this CPA primitive into an IND-CCA KEM. Note what an attacker faces: recovering s from (A, b) means solving a system whose equations are individually wrong by a few units, which no known classical or quantum algorithm does in subexponential time for proper parameters; that structural difference from factoring is the entire bet.

## How it's done in production

Deployed stacks as of mid-2026: OpenSSL 3.5+ ships ML-KEM and TLS 1.3 hybrid groups natively (`Groups = X25519MLKEM768`); BoringSSL/AWS-LC power Chrome and AWS endpoints; liboqs + oqs-provider expose the full NIST set plus experimental schemes for non-OpenSSL consumers; Bouncy Castle ≥1.79 brings ML-KEM/ML-DSA to Java; Apple CryptoKit and Android Keystore are rolling out ML-DSA support through platform releases. Cloud posture: Cloudflare terminates hybrid handshakes for >50% of human traffic (Oct 2025); Signal's PQXDH and Apple's PQ3 wrap messaging key agreement in post-quantum KEM chains; AWS KMS and Secrets Manager support hybrid post-quantum TLS on endpoints.

```nginx
# nginx 1.25+/OpenSSL 3.5+: enable hybrid group
ssl_ecdh_curve X25519MLKEM768:X25519;
```

What production adds beyond flipping configs: telemetry on handshake failures during rollout (middleboxes choking on larger ClientHellos), FIPS-validated module requirements (140-2 certificates historical since September 2026), HSM firmware support matrices for key generation inside hardware, certificate-profile work (X.509 PQC composite/hybrid drafts), and dual-signing strategies where verifiers cannot yet parse ML-DSA. Failure modes:

| Symptom | Cause | Fix |
|---|---|---|
| Handshake failures spike after enabling hybrid group | Middleboxes/load balancers rejecting >1.7 KB ClientHello | Update LB firmware; segment rollout; keep X25519 fallback ordered last |
| JWTs double in size after ML-DSA signing | Signature is 3,309 B vs EdDSA 64 B; embedded in every request header | Move auth to opaque tokens + introspection; sign only at issuance |
| HSM cannot generate ML-KEM keys | Firmware predates standard; vendor roadmap lag | Sequence vendor upgrades now; interim: software keys for low-value flows only |
| Cert chain bloat breaks legacy clients | Full ML-DSA chain adds tens of KB | Shorten chains, use delegated credentials, split classical/PQC serving planes |
| "We'll migrate when quantum computers arrive" | Misunderstanding HNDL: data is stolen today, decrypted later | Classify by confidentiality lifetime; anything past ~2033 migrates now |

## Tradeoffs & when NOT to use it

- **Do not deploy pure (non-hybrid) PQC key exchange prematurely.** Hybrids cost ~2 KB per handshake and remove single-algorithm risk; pure ML-KEM makes sense only where bandwidth-constrained devices force the tradeoff, and even then behind analysis.
- **Do not touch symmetric cryptography in this migration** beyond key-size policy: AES-256, SHA-384, HMAC-SHA-384 need no replacement; swapping them for unproven primitives adds risk while solving nothing.
- **Do not use SLH-DSA for high-volume signing.** Its signatures run 7-49 KB and hashing throughput limits sign rates to hundreds per second class; it exists for roots-of-trust and long-lived artifacts. High-volume request signing wants ML-DSA.
- **Do not treat IR 8547 dates as law.** They remain draft (as of August 2026); cite them as planning signals alongside the firmer CNSA 2.0/FIPS 140-3 milestones if you sell into US government supply chains.
- **When NOT to prioritise signatures first:** nothing retroactive can be stolen against them, so a program that spends its first year on signature PKI while external TLS stays classical has its priorities exactly backwards; confidentiality exposure is the clock that is already running.

---

## Interview questions

### Q1 — What exactly does a cryptographically relevant quantum computer break, and what survives?
**Testing:** the foundational split; wrong here and nothing else matters.
**Answer:** Shor breaks everything resting on factoring or abelian discrete log: RSA, DH, ECDH, ECDSA/EdDSA. Grover only halves symmetric strength: AES-256 retains ~2¹²⁸ effective security, SHA-384 stays sound (SHA-256 collisions degrade to ~2⁸⁵ via quantum collision algorithms). So: replace public-key primitives, size up symmetric ones.
**Follow-up trap:** *"Does TLS die then?"* — no: TLS 1.3's ciphersuites are already symmetric (AEAD); only its key-exchange group dies. Swapping X25519 for X25519MLKEM768 re-secures it; this is why KEM migration is a config-level change today.

### Q2 — Why migrate key exchange before signatures when both fall to Shor?
**Testing:** the sequencing insight that separates planners from reciters.
**Answer:** Asymmetric threat models: recorded key-exchange traffic is decryptable retroactively once a CRQC exists (harvest-now-decrypt-later), so confidentiality already leaking today must be fixed now with hybrid ML-KEM. Signatures have no retroactive attack: forgery requires the quantum computer to exist at forgery time, but signature ecosystems (root CAs, HSM firmware, embedded verifiers) rotate slowest, so they need inventory and lead-time work immediately, deployment later.
**Follow-up trap:** *"Any exception where signatures come first?"* — yes: long-lived signed artifacts whose verification devices cannot update easily (firmware, automotive/industrial roots): those need early migration because their rotation clock is measured in device lifetimes, not cert renewals.

### Q3 — State the NIST standards precisely.
**Answer:** FIPS 203: ML-KEM (from CRYSTALS-Kyber), lattice KEM, published August 13, 2024. FIPS 204: ML-DSA (from CRYSTALS-Dilithium), lattice signatures, same date. FIPS 205: SLH-DSA (SPHINCS+), stateless hash-based signatures, conservative backup. In development: FN-DSA (Falcon, FIPS 206) and HQC selected March 11, 2025 as a code-based KEM backup per NIST IR 8545.
**Follow-up trap:** *"Why keep HQC if ML-KEM exists?"* — algorithm diversity: both rest on different hardness assumptions (lattices vs codes); a future break of one should not strand every deployment, which is also the argument behind hybrids during transition.

### Q4 — What is harvest-now-decrypt-later and what does it actually imply for my systems?
**Testing:** whether urgency has a mechanism behind it.
**Answer:** Adversaries record encrypted traffic today at near-zero cost and decrypt after a CRQC arrives; any data whose confidentiality horizon extends past credible Q-day (~mid-2030s, uncertain) is effectively already compromised. Implication: classify data flows by secrecy lifetime; external TLS, backups, inter-service mTLS carrying data sensitive past ~2033 get hybrid PQC now, regardless of hardware news.
**Follow-up trap:** *"What about data that expires in weeks?"* — genuinely low HNDL risk: short-lived session traffic with no long-term sensitivity can follow the normal refresh cycle. The classification step exists precisely so you spend migration budget where exposure windows are real.

### Q5 — Walk through the CNSA 2.0 and NIST IR 8547 timelines.
**Answer:** CNSA 2.0 (NSA): new National Security System acquisitions require CNSA 2.0 compliance from January 2027; software/firmware signing exclusive by 2030; web/cloud/OS/custom applications by 2033. NIST IR 8547 (draft): deprecate RSA-2048/ECC-P256-class around 2030, disallow entirely by 2035. FIPS 140-2 certificates became historical September 2026, forcing 140-3 validation for US federal procurement. Google announced internal completion by 2029.
**Follow-up trap:** *"IR 8547 is a draft; why plan against it?"* — because enterprise migrations run 3-7 years: waiting for finalisation consumes your runway. Treat draft dates as planning baselines and track revisions; the cost asymmetry favours early movers either way.

### Q6 — What is hybrid key exchange and why insist on it?
**Testing:** operational maturity on rollout risk.
**Answer:** Combine classical and PQC in one exchange: X25519MLKEM768 computes both shared secrets and mixes them (TLS 1.3 concatenates into the key schedule), so traffic stays secure unless BOTH algorithms break. Rationale: new schemes carry implementation and analysis risk (the competition itself killed SIKE and Rainbow classically), while classical algorithms remain secure today against classical adversaries.
**Follow-up trap:** *"When do you drop the classical half?"* — when ML-KEM accumulates enough deployment confidence and the residual classical-vulnerability risk profile changes (e.g., store-now-decrypt-later adversaries using non-quantum breaks of ECC would be caught by hybrids too); guidance converges on hybrid through ~2028, pure PQC thereafter for most contexts.

### Q7 — Give the wire-size numbers for ML-KEM-768 and their system consequences.
**Testing:** whether you have shipped anything or only read blogs.
**Answer:** Public key 1,184 B, ciphertext 1,088 B, shared secret 32 B. Hybrid X25519MLKEM768 adds ~2 KB per handshake: negligible for web payloads, material on constrained MTU links and embedded devices. ML-DSA-65 signatures are 3,309 B versus EdDSA's 64 B: JWTs balloon, certificate chains add tens of KB, DNSSEC-style records overflow limits. ML-KEM operations run tens of microseconds on modern CPUs, faster than RSA private-key ops.
**Follow-up trap:** *"Where did big keys actually break production?"* — middleboxes and older load balancers rejecting larger ClientHello messages during browser rollouts; the fix was LB firmware upgrades and ordered fallback groups, which is why rollout telemetry matters more than benchmarks.

### Q8 — Your company sells SaaS to the US government. What dates bind you?
**Answer:** FIPS 140-3 validated crypto modules from September 2026 (140-2 historical); CNSA 2.0 compliance in new NSS deliveries from January 2027; software/firmware signing under CNSA 2.0 exclusively by January 2030; web/cloud services and custom applications by 2033; full federal migration posture by 2035 per NSM-10. Practically: contract language already demands PQC roadmaps, so procurement readiness precedes technical deadlines.
**Follow-up trap:** *"We're commercial-only. Zero obligations?"* — legal obligations aside, customers in finance/healthcare inherit federal supply-chain pressure via questionnaires, and EU coordinated roadmaps target critical-infrastructure transition starts by end-2026; market pressure reaches you one contract cycle late but reliably.

### Q9 — How do you build the cryptographic inventory (CBOM)?
**Testing:** program leadership, not just awareness.
**Answer:** Automated discovery first: scan repositories for crypto library imports and hardcoded primitives, inspect TLS configs across environments, enumerate certificates and their algorithms/expiry, inventory HSM/KMS key specs, map third-party/vendor dependencies to their crypto claims. Then enrich: data classification per flow, confidentiality lifetimes, owner assignment. Store as queryable SBOM-extension (CBOM format), wire into CI so new vulnerable primitives fail builds. Manual spreadsheets rot within a quarter.
**Follow-up trap:** *"Hardest category to find?"* — embedded and vendored code: static binaries shipping their own OpenSSL forks, firmware with baked-in keys, and shadow IT SaaS terminating TLS on your behalf; discovery tooling sees none of it without procurement and asset-management integration.

### Q10 — JWT signing: what changes under PQC?
**Testing:** concrete backend-engineer territory.
**Answer:** EdDSA/RS256 signatures give way to ML-DSA (JOSE/COSE algorithm drafts exist): ML-DSA-65 signatures are ~3.3 KB versus 64 B, so bearer tokens in headers inflate accordingly; options are accepting larger headers (HTTP/2 mitigates somewhat), moving to opaque session tokens with server-side introspection and signing only at issuance, or composite JOSE during transition. Refresh-token and JWKS distribution sizes grow similarly.
**Follow-up trap:** *"Better architectural answer?"* — treat PQC as forcing function for token hygiene: short-lived access tokens plus opaque references shrink what needs signing and make future algorithm rotations config-level; teams that hardcode RS256 everywhere feel every transition twice.

### Q11 — Why do hash-based signatures inspire special trust, and what are their costs?
**Answer:** Security reduces to hash-function preimage/collision resistance alone, the most conservative assumption in cryptography; SLH-DSA (stateless SPHINCS+) survived standardisation untouched and needs no algebraic structure a quantum computer could exploit. Costs: large signatures (7-49 KB depending on parameters) and slow signing (hash-tree traversals), making them fit root CAs, firmware, and code-signing cadence rather than request-path workloads. Stateful variants (LMS/XMSS, SP 800-208) are smaller/faster but catastrophic if state reuse occurs, hence restricted to controlled signing pipelines.
**Follow-up trap:** *"If hashes are safest, why isn't SLH-DSA the default?"* — operational economics: 40× signature bloat and slower signing across billions of daily verifications buys robustness insurance beyond current evidence needs; ML-DSA's lattice assumptions carry thirty years of scrutiny and the standardisation gauntlet. Defense-in-depth says deploy both where roles allow.

### Q12 — Design the three-year PQC migration roadmap for a mid-size SaaS platform.
**Testing:** synthesis under constraints; the actual job.
**Answer:** Year 1: CBOM inventory with CI enforcement, data-longevity classification, enable X25519MLKEM768 on edge/proxies behind telemetry, vendor questionnaire wave, HSM/CA upgrade contracts signed. Year 2: complete external+internal mTLS hybrid coverage, pilot ML-DSA code signing alongside classical (dual-sign), upgrade HSM fleet to 140-3/PQC-capable firmware, token architecture refactor toward opaque short-lived tokens. Year 3: PKI root migration plan executed in staging, firmware/embedded signers moved per device-replacement cycles, drop-to-pure-PQC decision point per endpoint, rollback drills completed. Success metric each year: percentage of data flows whose confidentiality survives a hypothetical instant-Q-day, trending to ~100% for flows classified long-lived.
**Follow-up trap:** *"Cut to six months and one engineer?"* — edge TLS hybrid (config change) plus the inventory script plus vendor questionnaire template: those three capture most of the HNDL risk reduction available at that scale, and honestly document the rest as accepted risk with dates attached.

## Red flags that fail you

- Claiming quantum computers will break AES/symmetric encryption (they halve effective strength).
- No harvest-now-decrypt-later reasoning anywhere in a "when should we migrate" answer.
- Naming algorithms without FIPS numbers or standardisation status (FIPS 203/204/205, Aug 13 2024).
- Treating signature migration and KEM migration as equally urgent, or both as deferrable.
- Proposing pure-PQC rollout with no hybrid phase and no rollback story.
- Quoting IR 8547's 2030/2035 dates as finalized law (still Initial Public Draft as of August 2026).
- No mention of crypto agility or inventories: implies the next migration will hurt just as much.

## Cheat card

```
WHAT BREAKS   Shor => RSA, DH, ECDH, ECDSA/EdDSA dead (poly time)
              Grover halves symmetric: AES-128 -> 2^64 eff, USE AES-256
              SHA-384 fine · HMAC fine · TLS cipher suites survive
WHEN          RSA-2048 CRQC: millions of phys qubits / hours,
              credible mid-2030s · HNDL means data stolen TODAY
STANDARDS     FIPS 203 ML-KEM (Kyber) · 204 ML-DSA (Dilithium)
              205 SLH-DSA (SPHINCS+)  -- all Aug 13 2024
              FN-DSA Falcon = FIPS 206 (dev) · HQC backup Mar 2025
SIZES         ML-KEM-768: pk 1184B ct 1088B ss 32B (~us ops)
              ML-DSA-65: pk 1952B sig 3309B (vs EdDSA 64B!)
              SLH-DSA sigs 7-49KB: roots/firmware only
HYBRID        X25519MLKEM768: +~2KB/handshake · >50% human web
              traffic via Cloudflare Oct 2025 · keep fallback last
TIMELINES     CNSA 2.0: new NSS Jan 2027 · sign-only 2030 ·
              cloud/apps 2033 · NIST IR 8547 DRAFT: dep 2030/dis 2035
              FIPS 140-2 -> historical Sep 2026 (need 140-3)
MIGRATION     1) CBOM inventory (automated, CI-enforced)
              2) data longevity classification (HNDL lens)
              3) external KEM hybrid NOW · 4) vendor pressure
              5) signatures second (code/firmware first) · 6) agility
STACK         OpenSSL >=3.5 native ML-KEM · liboqs/oqs-provider
              Bouncy Castle >=1.79 (Java) · Signal PQXDH · iMessage PQ3
NEVER         don't replace symmetric crypto · don't go pure-PQC
              without hybrid phase · SLH-DSA not for high-volume paths
```

## Sources

- [NIST releases first three finalized post-quantum encryption standards (Aug 13, 2024)](https://www.nist.gov/news-events/news/2024/08/nist-releases-first-3-finalized-post-quantum-encryption-standards) — accessed 2026-08-23
- [NIST CSRC Post-Quantum Cryptography Standardization project page (FIPS 203/204/205, HQC selection)](https://csrc.nist.gov/Projects/post-quantum-cryptography/post-quantum-cryptography-standardization) — accessed 2026-08-23
- [NIST IR 8547: Transition to Post-Quantum Cryptography Standards (Initial Public Draft)](https://csrc.nist.gov/pubs/ir/8547/ipd) — accessed 2026-08-23
- [Cloudflare: PQC milestones, 50% X25519MLKEM768 traffic (Oct 2025)](https://blog.cloudflare.com/pq-2025/) — accessed 2026-08-23
- [CNSA 2.0 timeline and mandates summary](https://axelspire.com/business/pqc-timeline-mandates/) — accessed 2026-08-23
- [Quantum roadmaps tracker: RSA-2048 estimates and Q-day outlook](https://quantummarketcap.com/roadmap) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

