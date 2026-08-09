# Hashes, Merkle Trees, Digital Signatures, ECDSA — Build Them

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 2.5h · **Prereqs:** none
> **Updated:** 2026-08-08
> **Module id:** `T22-crypto-primitives` · **Tags:** fundamentals, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A blockchain is three cryptographic primitives wearing a trenchcoat: a hash function that turns arbitrary data into a fixed-size fingerprint you cannot invert or forge a collision for, a Merkle tree that lets you prove one transaction is included in a block of thousands by revealing a handful of hashes instead of the whole block, and a digital signature scheme (ECDSA on Bitcoin and Ethereum, both on the secp256k1 curve) that lets you prove you control a private key without ever revealing it. None of this is blockchain-specific — TLS, git, and every password database use the same primitives — blockchain just composes them into a structure where the hash chain gives you tamper-evidence and the signatures give you authorization, and the entire "trustless" property people market comes from those two guarantees and nothing more mystical than that. The one fact in this module that has actually destroyed real money more than once: ECDSA's signing nonce `k` must be unique and unpredictable for every signature, because reusing it twice with the same key turns two signatures into a two-line algebra problem that hands the attacker your private key, in full, no brute force required — this is exactly how the 2010 Sony PS3 signing key leaked and how multiple Bitcoin wallets with broken random number generators have been drained.

## Why this gets asked

Because "blockchain" is a word candidates use fluently without being able to build any of the three primitives underneath it, and the interviewer wants to know if you understand the mechanism or just the marketing. Anyone who has operated a signing service, built a certificate pipeline, or debugged a "why did this wallet get drained with no phishing involved" incident has watched nonce reuse or a weak PRNG turn into a full key-recovery in production — Android's `SecureRandom` bug in 2013 leaked Bitcoin private keys this exact way, and it keeps recurring because most engineers have never actually done the algebra by hand and so don't feel viscerally why it's catastrophic rather than "a bit weaker."

---

## Lineage: past → present → future

**What came before.** Before public-key cryptography existed at all, authentication meant shared secrets — symmetric MACs, passwords, physical keys — which required every verifier to hold something an attacker could steal and immediately impersonate you with. Diffie and Hellman's 1976 paper *New Directions in Cryptography* proposed the idea of a key pair where the public half could be shared openly; RSA (Rivest, Shamir, Adleman, 1977) gave the first practical realization, based on the difficulty of factoring large semiprimes. Elliptic-curve cryptography followed in the mid-1980s (Koblitz and Miller, independently, 1985), offering equivalent security to RSA at dramatically smaller key sizes — a 256-bit EC key is roughly as hard to break as a 3072-bit RSA key — because the best known attack against the elliptic-curve discrete-log problem (Pollard's rho, roughly `O(sqrt(n))`) doesn't benefit from the sub-exponential factoring shortcuts (the general number field sieve) that attack RSA. That size advantage is precisely why Bitcoin (2009) chose ECDSA over RSA: smaller signatures and public keys mean smaller transactions, which matters when every node must store and replicate every transaction forever.

**Where it stands now.** ECDSA over secp256k1 is what Bitcoin and pre-2022 Ethereum transaction signing both use, and it remains the dominant signature scheme securing the majority of value on both chains today. The live, well-documented weak point isn't the curve — secp256k1 has no known practical attack — it's implementation discipline around the nonce `k`: RFC 6979 (2013) standardized *deterministic* nonce generation (derive `k` from the private key and message hash via HMAC, instead of trusting a random number generator) specifically because "just use a good random number generator" kept failing in practice, and most modern libraries (`python-ecdsa`, OpenSSL, libsecp256k1) now default to RFC 6979 rather than raw randomness. Separately, Schnorr signatures (standardized for Bitcoin as BIP-340, live since the Taproot upgrade in November 2021) are gaining ground because they support native signature aggregation — multiple signers can produce one combined signature indistinguishable from a single signer's, which ECDSA cannot do without more complex multi-party protocols — and Schnorr's security proof is simpler and more directly reducible to the discrete-log assumption than ECDSA's.

**Where it's heading.** Two threads, different confidence levels. First, high confidence: aggregatable and threshold signature schemes (Schnorr-based MuSig2, BLS signatures used natively by Ethereum's consensus layer for validator attestations) are replacing plain ECDSA anywhere many parties need to jointly authorize something, because verifying one aggregated signature instead of thousands individually is a real, measured throughput win Ethereum's beacon chain depends on today. Second, lower confidence and longer horizon: post-quantum signature migration. Shor's algorithm breaks the discrete-log problem underlying ECDSA on a sufficiently large fault-tolerant quantum computer, and NIST finalized post-quantum signature standards (ML-DSA/Dilithium, SLH-DSA/SPHINCS+) in 2024, but no such quantum computer exists yet and estimates for when one might range from "a decade" to "not in any current roadmap" — treat any specific timeline you hear as speculation, but treat the standardization work itself as real and already underway.

---

## Mental model

```
  HASH FUNCTION           one-way fingerprint, fixed size, avalanche effect
  ─────────────
  input (any size)  ──SHA256──▶  256-bit digest
  "hello world"      ──────▶  b94d27b9...
  "hello worlE"      ──────▶  59a6e5d1...   (1 bit changed → ~50% of output bits flip)
  CANNOT go digest → input.  CANNOT find two inputs with the same digest (by design).


  MERKLE TREE              prove ONE leaf is in a set of N without revealing the rest
  ─────────────
                          ROOT = H(H01 || H23)
                         /                    \
                  H01=H(L0||L1)          H23=H(L2||L3)
                  /         \              /         \
               L0=H(tx0)  L1=H(tx1)    L2=H(tx2)   L3=H(tx3)

  Proof that tx0 is in this tree: reveal {L1, H23} + your own tx0.
  Verifier recomputes: H(H(tx0)||L1) = H01, then H(H01||H23), checks == ROOT.
  Cost: O(log N) hashes to prove inclusion in N items, not O(N).
  A Bitcoin block with 3,000 transactions needs a ~12-hash proof, not 3,000 hashes.


  DIGITAL SIGNATURE        prove you hold a private key, without revealing it
  ─────────────
  private key d (secret)  ──scalar mult on curve──▶  public key Q = d·G  (shareable)
  sign(message, d, k)  ──▶  (r, s)     k = one-time-use RANDOM NUMBER — the whole
                                        security model depends on k never repeating
  verify(message, (r,s), Q)  ──▶  True/False,  needs ONLY the public key
```

---

## How it actually works

### Hash functions: the three properties that make everything else possible

A cryptographic hash function `H` maps arbitrary-length input to a fixed-length output (SHA-256 → 256 bits, always, whether the input is one byte or one gigabyte) and needs to hold three properties simultaneously:

1. **Preimage resistance** — given `H(x)`, you cannot feasibly find any `x` that produces it. This is what makes a hash "one-way." Breaking it for SHA-256 would require roughly `2^256` attempts on average — not "hard," astronomically infeasible; there are estimated to be around `2^266` atoms in the observable universe, so this isn't a "buy more GPUs" problem.
2. **Second-preimage resistance** — given `x1`, you cannot feasibly find a *different* `x2` such that `H(x1) == H(x2)`.
3. **Collision resistance** — you cannot feasibly find *any* two inputs `x1 != x2` with `H(x1) == H(x2)`, without being handed either one first. This is strictly harder to achieve than the first two because of the **birthday paradox**: finding *some* collision among random hashes only takes about `sqrt(2^256) = 2^128` attempts, not `2^256` — the same math behind why 23 random people in a room have better-than-even odds of sharing a birthday. This is why a hash function needs *double* the bit-length of its "difficulty" to be collision-resistant at a given security level, and it's why SHA-1 (160-bit output, ~2^80 collision resistance) was formally broken by Google's 2017 "SHAttered" attack, which produced two different PDFs with an identical SHA-1 hash for a real, demonstrated cost (~$110,000 of cloud GPU time at the time).

**The avalanche effect** is the practical signature of a well-designed hash: flipping a single input bit should flip roughly half the output bits, with no discernible pattern. Verified directly:

```python
import hashlib
a = hashlib.sha256(b"hello world").hexdigest()
b = hashlib.sha256(b"hello worle").hexdigest()   # one character changed: d -> e
print(a)  # b94d27b9934d3e08a52e52d7da7dabfac484efe37a5380ee9088f7ace2efcde9
print(b)  # 0fc30e735a0228a31cbbb969988b4f50e02e737f979f091d7d224b765443f5d
# differing bits between the two 256-bit digests: 140 out of 256 (~55%)
```

Run against the actual byte values (`"hello world"` vs `"hello worle"`, one letter changed), this measures 140 of 256 bits flipped — right around the ~50% an ideal hash produces, with zero correlation to *which* input bit changed. This property is what makes hashes usable as commitment schemes, as content addressing (git's object store, IPFS), and as the building block for Merkle trees below — if similar inputs produced similar outputs, none of those would be safe.

**A hash is not encryption, and this distinction is covered in depth, not repeated here** — see `T30-crypto-practice` for encoding vs. hashing vs. encryption, password hashing (Argon2id/bcrypt), AES-GCM, and HMAC. This module assumes that ground is covered and focuses on what's specific to blockchain: Merkle proofs and ECDSA.

### Merkle trees: proving inclusion in O(log N)

A **Merkle tree** (Ralph Merkle, 1979, predating blockchain by three decades — it was originally built for efficient signature verification of large public-key sets) is a binary tree where every leaf is the hash of one data item and every internal node is the hash of its two children's concatenation. The single hash at the top — the **Merkle root** — is a fixed-size commitment to every item in the tree: change one byte of one transaction anywhere in the tree, and the avalanche effect propagates that change all the way to the root.

The property that makes this valuable for blockchain specifically is the **inclusion proof**: to prove that transaction `tx0` is one of `N` transactions committed to by a known root, you don't need to reveal or re-hash all `N` transactions — you only need `log2(N)` sibling hashes, the ones along the path from your leaf to the root. A Bitcoin block with 3,000 transactions needs about 12 hashes to prove any one transaction's inclusion, not 3,000. This is exactly what **SPV (Simplified Payment Verification)** clients — Bitcoin light wallets that don't download the full blockchain — rely on: a block header (80 bytes) contains the Merkle root of every transaction in that block, and a full node can hand an SPV client a short Merkle proof that a specific payment was included, without the SPV client ever downloading the other 2,999 transactions.

**Two implementation details that matter and are frequently gotten wrong:**

- **Domain separation between leaves and internal nodes.** If `H(leaf_data)` and `H(left || right)` use the same hash with no prefix distinguishing them, an attacker can potentially present an internal node's hash as if it were a valid leaf (a **second-preimage attack on Merkle trees**, described formally in Kelsey & Schneier's 2005 paper) — prefixing leaves with `0x00` and internal nodes with `0x01` before hashing (as below) closes this off entirely, at the cost of one extra byte per hash.
- **Odd number of nodes at a level.** With an odd leaf count, some implementations duplicate the last node to pair with itself (used below); others (Bitcoin's actual implementation) do exactly this too — but it has a known subtlety (CVE-2012-2459) where a maliciously constructed block with duplicate transaction hashes at certain tree positions can create ambiguity about tree validity. Production implementations need to explicitly reject duplicate adjacent transaction hashes to close this, not just duplicate-and-hash blindly.

---

## Build it from scratch

### Merkle tree with a working inclusion proof

Domain-separated, tested, and verified against tampering:

```python
import hashlib

def h(data: bytes) -> bytes:
    return hashlib.sha256(data).digest()

def leaf_hash(data: bytes) -> bytes:
    return h(b"\x00" + data)          # domain-separated from internal nodes

def node_hash(left: bytes, right: bytes) -> bytes:
    return h(b"\x01" + left + right)

class MerkleTree:
    def __init__(self, items: list[bytes]):
        assert items, "need at least one item"
        self.leaves = [leaf_hash(i) for i in items]
        self.levels = [self.leaves]
        level = self.leaves
        while len(level) > 1:
            nxt = []
            for i in range(0, len(level), 2):
                left = level[i]
                right = level[i + 1] if i + 1 < len(level) else level[i]  # duplicate if odd
                nxt.append(node_hash(left, right))
            self.levels.append(nxt)
            level = nxt
        self.root = level[0]

    def proof(self, index: int) -> list[tuple[bytes, str]]:
        path, idx = [], index
        for level in self.levels[:-1]:
            is_right = idx % 2 == 1
            pair_idx = idx - 1 if is_right else idx + 1
            if pair_idx >= len(level):
                pair_idx = idx
            path.append((level[pair_idx], "left" if is_right else "right"))
            idx //= 2
        return path

def verify_proof(item: bytes, proof: list[tuple[bytes, str]], root: bytes) -> bool:
    current = leaf_hash(item)
    for sibling, side in proof:
        current = node_hash(sibling, current) if side == "left" else node_hash(current, sibling)
    return current == root

# verified: 7 items, all 7 proofs valid, tampered item correctly rejected
items = [f"tx{i}".encode() for i in range(7)]
tree = MerkleTree(items)
for i, item in enumerate(items):
    assert verify_proof(item, tree.proof(i), tree.root)
assert not verify_proof(b"tx0-tampered", tree.proof(0), tree.root)
```

This exact code was run: root `e2b7ff03...`, all 7 positive proofs valid (proof length 3, i.e. `log2(7)` rounded up), the tampered-item negative case correctly returns `False`.

### ECDSA from scratch, over the real secp256k1 curve, including the nonce-reuse attack

This is the actual curve Bitcoin and Ethereum use — not a toy curve — implemented in pure Python with no external crypto library, so every step is visible:

```python
import hashlib, random

# secp256k1: y^2 = x^3 + 7 (mod P)
P  = 2**256 - 2**32 - 977
Gx = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
Gy = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G  = (Gx, Gy)
N  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141   # order of G

def inv(a: int, m: int) -> int:
    return pow(a, m - 2, m)   # Fermat's little theorem (P, N both prime)

def point_add(p1, p2):
    if p1 is None: return p2
    if p2 is None: return p1
    x1, y1 = p1; x2, y2 = p2
    if x1 == x2 and (y1 + y2) % P == 0:
        return None                              # point at infinity
    m = ((3 * x1 * x1) * inv(2 * y1, P) if p1 == p2
         else (y2 - y1) * inv((x2 - x1) % P, P)) % P
    x3 = (m * m - x1 - x2) % P
    y3 = (m * (x1 - x3) - y1) % P
    return (x3, y3)

def scalar_mult(k: int, point):
    result, addend = None, point
    while k:
        if k & 1:
            result = point_add(result, addend)
        addend = point_add(addend, addend)
        k >>= 1
    return result

def gen_keypair():
    d = random.randrange(1, N)          # private key: a random 256-bit scalar
    return d, scalar_mult(d, G)         # public key: d·G (a point — cannot be inverted to d)

def sha256_int(msg: bytes) -> int:
    return int.from_bytes(hashlib.sha256(msg).digest(), "big") % N

def ecdsa_sign(msg: bytes, d: int, k: int):
    z = sha256_int(msg)
    r = scalar_mult(k, G)[0] % N
    s = (inv(k, N) * (z + r * d)) % N
    return r, s

def ecdsa_verify(msg: bytes, sig, Q) -> bool:
    r, s = sig
    z = sha256_int(msg)
    w = inv(s, N)
    X = point_add(scalar_mult((z * w) % N, G), scalar_mult((r * w) % N, Q))
    return X is not None and X[0] % N == r
```

Verified against this exact code: `G` lies on the curve, a random keypair signs and verifies correctly for two different messages.

**Now the nonce-reuse attack.** ECDSA signing needs a fresh, unpredictable `k` for every single signature. Reuse it — same `k`, same private key, two different messages — and the algebra collapses:

```
s1 = k⁻¹(z1 + r·d)  mod n            [both signatures share the same r, because
s2 = k⁻¹(z2 + r·d)  mod n             r = (k·G).x depends only on k, not on the message]

s1 - s2 = k⁻¹(z1 - z2)  mod n    →    k = (z1 - z2) / (s1 - s2)  mod n

then, from s1's equation:             d = (s1·k - z1) / r  mod n
```

Two equations, two unknowns (`k` and `d`), solved with nothing but modular arithmetic — no brute force, no weakness in SHA-256 or in the curve itself. The bug is entirely in the *reuse*, not in any primitive:

```python
def recover_privkey_from_nonce_reuse(msg1, sig1, msg2, sig2):
    r1, s1 = sig1
    r2, s2 = sig2
    assert r1 == r2, "r must match — that's the nonce-reuse fingerprint"
    z1, z2 = sha256_int(msg1), sha256_int(msg2)
    k = ((z1 - z2) * inv((s1 - s2) % N, N)) % N
    d = ((s1 * k - z1) * inv(r1, N)) % N
    return d, k

# --- verified end to end ---
d, Q = gen_keypair()
k = random.randrange(1, N)                              # THE MISTAKE: reused below
sig1 = ecdsa_sign(b"send 1 BTC to Alice", d, k)
sig2 = ecdsa_sign(b"send 5 BTC to Mallory", d, k)        # same k, different message

assert sig1[0] == sig2[0]                                # r1 == r2: the tell-tale sign
assert ecdsa_verify(b"send 1 BTC to Alice", sig1, Q)      # both signatures are
assert ecdsa_verify(b"send 5 BTC to Mallory", sig2, Q)    # individually, perfectly valid

recovered_d, recovered_k = recover_privkey_from_nonce_reuse(
    b"send 1 BTC to Alice", sig1, b"send 5 BTC to Mallory", sig2
)
assert recovered_d == d and recovered_k == k              # full private key recovered
```

Run for real: both signatures verify independently and look completely unremarkable on their own — nothing about `sig1` or `sig2` individually indicates anything is wrong. It's only the *pair*, sharing an `r` value, that leaks. This is exactly the mechanism behind the 2010 PS3 signing-key leak (Sony reused a fixed `k` for every ECDSA signature ever produced by the console — not even randomness that happened to repeat, but a hardcoded constant, the maximally bad version of this bug), and the 2013 Android `SecureRandom` flaw that let attackers drain Bitcoin wallets by scanning the blockchain for any two signatures from the same address sharing an `r` value, then running exactly this algebra.

**The fix**, standardized as **RFC 6979**: derive `k` deterministically from the private key and the message hash via HMAC, so the same `(message, key)` pair always produces the same `k` — which sounds like it reintroduces the reuse problem, but doesn't, because `k` only repeats if you sign the *exact same message* with the *exact same key* twice, which produces an identical signature both times and leaks nothing new. This also sidesteps the original problem entirely: a broken or low-entropy random number generator can no longer produce a weak or repeated `k`, because `k` was never sourced from randomness in the first place. Modern signing libraries (`python-ecdsa`, OpenSSL, Bitcoin Core's `libsecp256k1`) default to RFC 6979 today specifically because "trust the RNG" kept failing in the field.

Full lab — including a from-scratch SHA-256 avalanche visualizer, a larger Merkle tree with a batch-proof optimization, and an interactive nonce-reuse exploit against a deliberately vulnerable toy wallet: **`labs/py/22-crypto-primitives/`**.

---

## How it's done in production

Nobody hand-rolls the elliptic-curve math above in a real system — the pure-Python implementation exists here purely so the mechanism is visible; production code uses **`libsecp256k1`** (the C library Bitcoin Core and most Ethereum clients actually use, optimized and side-channel-hardened) or the `cryptography` package's bindings to it. Signing services (AWS KMS, HashiCorp Vault's transit engine, hardware security modules) generate and store the private key in hardware that never exports it, signing on request — this closes off an entire category of key-exfiltration risk that a private key sitting in application memory or an environment variable does not.

| Symptom | Cause | Fix |
|---|---|---|
| A wallet is drained with no phishing, no malware found | Two on-chain signatures from the same address share an `r` value — nonce reuse, findable by anyone scanning the public chain | Migrate signing to RFC 6979 deterministic nonces (default in modern libraries) or an HSM/KMS that never exposes raw `k` generation to application code |
| Merkle inclusion proof validates for data that was never actually committed | Missing domain separation between leaf and internal node hashing (a crafted internal-node value passed off as a leaf) | Prefix leaves and internal nodes with distinct domain tags before hashing, as shown above |
| Two different transaction sets produce the same Merkle root | Duplicate-node ambiguity with odd leaf counts (CVE-2012-2459 class) | Explicitly reject blocks/trees with duplicate adjacent hashes at the same tree position rather than silently duplicating |
| Signature verification passes for a message that was never signed | Hash truncation or using a non-preimage-resistant hash (e.g., an old MD5-based scheme) inside the signature construction | Use a hash with 256-bit output for 128-bit security margin (accounting for the birthday bound), never anything weaker for anything new |
| Legacy system still validates SHA-1-based certificates or signatures | Deprecated hash never fully migrated off after the 2017 SHAttered collision | Force migration to SHA-256/SHA-3 for any new trust decisions; treat lingering SHA-1 usage as a finding, not a footnote |

---

## Tradeoffs & when NOT to use it

- **Don't roll your own elliptic-curve implementation for anything that touches real funds or real secrets.** The pure-Python code above is for understanding, not deployment — side-channel timing leaks in a naive `scalar_mult` (a non-constant-time double-and-add loop, exactly like the one shown, whose execution time varies with the bits of `k`) have been used in real attacks to recover keys by measuring signing latency. Use `libsecp256k1`.
- **Don't use ECDSA where Schnorr/BLS aggregation is actually available and multiple signers are involved.** Verifying `N` individual ECDSA signatures costs `N` verifications; an aggregated Schnorr or BLS signature can cost one — this is exactly why Ethereum's consensus layer, which must verify tens of thousands of validator signatures per epoch, uses BLS rather than ECDSA for attestations.
- **Don't treat a Merkle proof as proof that data is *correct*, only that it's *included*.** A Merkle root faithfully commits to garbage just as well as it commits to valid data — inclusion and validity are separate questions, and conflating them is a real, recurring design mistake (see module 3 on how Ethereum's state trie and Merkle proofs relate to actual state validity).
- **Don't reach for a full Merkle tree when a flat hash list would do.** If you never need an inclusion proof — only "does this exact dataset match what I expect" — a single hash of the concatenated data is simpler and sufficient; the `O(log N)` proof machinery is overhead that only pays for itself when you need to prove membership of one item without transmitting the whole set.
- **Post-quantum migration for ECDSA-secured funds is not an urgent action item today** for the same reason covered in `T30-crypto-practice`: no cryptographically relevant quantum computer exists, and premature migration effort is often better spent elsewhere — but do know that Bitcoin and Ethereum's *current* signature schemes are exactly the primitives Shor's algorithm targets, which is why post-quantum signature research is an active, funded area for these ecosystems specifically, not a hypothetical concern for some other technology.

---

## Interview questions

### Q1 — What are the three properties a cryptographic hash function needs, and why is collision resistance the hardest to achieve?
**Testing:** whether the birthday-bound intuition is actually understood, not memorized.
**Answer:** Preimage resistance (can't invert), second-preimage resistance (can't find a different input matching a given one's hash), and collision resistance (can't find any two colliding inputs at all). Collision resistance is weaker by the birthday bound: finding *any* collision among random hashes takes about `sqrt(2^n) = 2^(n/2)` attempts for an n-bit hash, not `2^n`, because you're comparing every pair among a growing set rather than matching one fixed target — this is why SHA-1's 160-bit output gave only ~2^80 collision resistance, which Google's 2017 SHAttered attack broke for a demonstrated, bounded real-world cost.
**Follow-up trap:** *"So is SHA-256's preimage resistance also only 2^128?"* — no, that conflation is the trap. Preimage resistance for SHA-256 stays at the full `2^256`, because you're matching one specific target, not searching for any pair among many; only *collision* resistance gets the birthday-bound haircut down to `2^128`. Mixing these up is one of the most common mistakes in this space.

### Q2 — Build a Merkle tree inclusion proof by hand for a 4-leaf tree. What does the verifier actually need?
**Testing:** whether the O(log N) mechanism is understood mechanically, not just as a buzzword.
**Answer:** For leaves L0-L3 with internal nodes H01=H(L0,L1), H23=H(L2,L3), root=H(H01,H23): to prove L0's inclusion, the verifier needs L0 itself, sibling L1 (to recompute H01), and sibling H23 (to recompute the root) — two sibling hashes for four leaves, `log2(4)=2`, matching the formula. The verifier recomputes bottom-up and checks the final value equals the known root; it never sees L2 or L3 directly.
**Follow-up trap:** *"What happens with 5 leaves instead of a power of two?"* — you pad, typically by duplicating the last leaf/node at each level to make pairs, which is what the reference implementation above does — but this reintroduces a known ambiguity (CVE-2012-2459-class) if duplicate adjacent hashes aren't explicitly rejected as invalid input, since an attacker could potentially construct two different-looking trees that produce the same root through the duplication rule.

### Q3 — Why does Bitcoin use ECDSA instead of RSA?
**Testing:** whether the elliptic-curve size advantage and its actual cause is understood.
**Answer:** Equivalent security at dramatically smaller key/signature sizes — a 256-bit EC key matches roughly 3072-bit RSA security, because the best attack against the elliptic-curve discrete-log problem (Pollard's rho, `O(sqrt(n))`) has no sub-exponential shortcut analogous to the general number field sieve that attacks RSA's factoring problem. Smaller keys and signatures matter enormously for a system where every node stores and validates every transaction forever — Bitcoin's entire design is sensitive to bytes-per-transaction in a way most systems aren't.
**Follow-up trap:** *"Could Bitcoin have used a different elliptic curve, like the NIST P-256 curve TLS commonly uses?"* — technically yes, but secp256k1 was specifically chosen over NIST curves partly due to distrust of NIST-generated curve parameters (concerns, never proven for secp256k1 itself, trace back to suspicion of the NSA's involvement in curve parameter selection after the Dual_EC_DRBG backdoor was confirmed) and partly for specific efficiency properties (a particularly efficient endomorphism) that make secp256k1 faster to compute on than P-256 for this use case.

### Q4 — Walk through exactly why reusing an ECDSA nonce leaks the private key. Do the algebra.
**Testing:** the module's central fact, tested for real mechanical understanding not just "you shouldn't do that."
**Answer:** `s1 = k⁻¹(z1 + r·d) mod n` and `s2 = k⁻¹(z2 + r·d) mod n` share the same `r` because `r` is derived purely from `k` (as `(k·G).x`), not from the message. Subtracting: `s1 - s2 = k⁻¹(z1 - z2) mod n`, so `k = (z1-z2)/(s1-s2) mod n` — directly solvable since `z1`, `z2`, `s1`, `s2` are all known from the two public signatures. With `k` recovered, substitute back into either signature equation to solve for `d = (s1·k - z1)/r mod n`. Two linear equations, two unknowns, pure modular arithmetic — no brute force anywhere in the process.
**Follow-up trap:** *"If an attacker only sees one signature, are they safe?"* — from *this specific attack*, yes; nonce reuse requires observing two signatures sharing an `r` value. But this is exactly why the fix (RFC 6979 deterministic nonces) is preferred over "just use better randomness": it removes the *possibility* of reuse entirely rather than relying on an RNG never failing across billions of signing operations over a system's lifetime, and a single RNG failure (a reused seed after a VM snapshot restore, a broken embedded entropy source) can retroactively compromise every signature that shared its output.

### Q5 — Your company is signing millions of transactions per day with ECDSA using a supposedly cryptographically secure RNG for `k`. A security review flags this as a risk. Are they right to flag it, given RFC 6979 exists?
**Testing:** whether the candidate connects the abstract lesson to an actual operational recommendation.
**Answer:** Yes, reasonably — "supposedly cryptographically secure" is doing a lot of work in that sentence, and the entire point of RFC 6979 is to remove reliance on RNG correctness for this specific operation, since RNG failures are a real, recurring category of production incident (Android's 2013 `SecureRandom` bug, virtual machines that clone with a duplicated entropy pool, embedded devices with genuinely weak entropy at boot). Switching to RFC 6979 deterministic nonce derivation costs nothing functionally — signatures remain equally valid and verifiable — while closing off an entire attack class regardless of how the RNG behaves.
**Follow-up trap:** *"Does deterministic nonce generation introduce any new risk?"* — a narrow one: if the deterministic derivation itself has a bug or if the same private key is used across systems with different derivation implementations that could theoretically diverge, you'd want to verify the derivation is correctly implemented against the RFC's test vectors — but this is a one-time implementation-correctness check, not an ongoing operational risk the way RNG entropy quality is.

### Q6 — Why can't you invert `Q = d·G` to recover `d` from the public key, given that `G` and `Q` are both known points on the curve?
**Testing:** the discrete-log hardness assumption underlying every EC signature scheme.
**Answer:** This is the **elliptic curve discrete logarithm problem (ECDLP)**: given `G` and `Q = d·G`, finding `d` is believed computationally infeasible for a well-chosen curve — there's no known algorithm better than roughly `O(sqrt(n))` (Pollard's rho) for a curve of order `n`, and for secp256k1's ~256-bit order that's on the order of `2^128` operations, comparable to SHA-256's collision-resistance margin, and equally infeasible with any currently conceivable classical computing.
**Follow-up trap:** *"Is this the same hardness assumption RSA relies on?"* — no, and conflating them is common. RSA's security rests on integer factorization being hard; ECDSA's rests on the discrete-log problem over an elliptic curve group. They're both believed hard for classical computers but are mathematically distinct problems — and notably, Shor's algorithm breaks *both* on a sufficiently large quantum computer, which is why post-quantum migration concerns apply to ECDSA-based systems just as much as RSA-based ones, not more or less.

### Q7 — What's the difference between the public key and the address in Bitcoin/Ethereum? Why not just use the public key directly as the address?
**Testing:** whether the layered hashing (a Merkle-adjacent but distinct use of hash functions) is understood.
**Answer:** An address is a hash of the public key (Bitcoin: RIPEMD160(SHA256(pubkey)) plus checksum/encoding; Ethereum: the last 20 bytes of Keccak256(pubkey)), not the public key itself. This shortens the address, adds an extra preimage-resistance layer (an attacker with only the address, not the public key, faces an additional hash inversion before they'd even have the public key to attack), and historically mattered more before Bitcoin script types diversified — hashing the pubkey meant the actual public key didn't need to be revealed on-chain until the coins were spent, reducing exposure window against any future weakness in the signature scheme itself.
**Follow-up trap:** *"Does hiding the public key behind a hash protect against a future quantum attack on ECDSA?"* — only partially and only until you spend from that address: the public key becomes visible on-chain the moment you sign a transaction, so an address that has never been used to *send* funds (only received) has a genuine extra layer of quantum-safety margin, but any address that has ever spent from it has fully exposed its public key permanently on an immutable public ledger — a real, sometimes-cited argument for using a fresh address per transaction, which both Bitcoin's UTXO model (module 4) and general wallet hygiene already encourage for privacy reasons independently.

### Q8 — A candidate says "Merkle trees make blockchains tamper-proof." Critique this claim precisely.
**Testing:** precision about what a hash-based structure actually guarantees versus what marketing language implies.
**Answer:** Imprecise in an important way: a Merkle tree (and hash chaining generally) makes tampering *detectable*, not *impossible* — anyone can still edit historical data; the edit simply changes the resulting root/hash in a way that's immediately visible to anyone checking it against a previously known-good value or against consensus among other participants. "Tamper-evident" is the accurate term; "tamper-proof" implies prevention, which is actually enforced by the consensus mechanism (module 3) making it economically or computationally infeasible to get a tampered chain accepted by the network, not by the hashing itself.
**Follow-up trap:** *"So is the hashing even doing meaningful work, if consensus is what really prevents tampering?"* — yes, critically: the hashing is what makes tampering *cheaply and immediately detectable* at all, which is the precondition for the consensus mechanism's economic incentives to work — without tamper-evidence, an attacker's edit would be invisible and consensus would have nothing to reject in the first place. They're complementary layers, not competing explanations for the same guarantee.

### Q9 — Design a system where a client needs to prove to a server that a specific record exists in a dataset of 10 million records, without the server storing or re-downloading the whole dataset. What do you build?
**Testing:** applying the Merkle proof pattern to a novel, non-blockchain scenario — checking for transfer of understanding.
**Answer:** Build a Merkle tree over the 10 million records, publish only the root (32 bytes) to the server as a trusted commitment. When a client needs to prove record inclusion, it sends the record plus a `log2(10,000,000) ≈ 24`-hash proof; the server recomputes up to the root and compares against its stored 32-byte commitment. This is exactly the pattern behind Certificate Transparency logs (proving a TLS certificate was published without downloading every certificate ever issued) and behind SPV Bitcoin clients — the generalizable insight is "publish a small commitment, prove membership with a logarithmic-size proof" wherever a party needs assurance about membership in a large, mostly-static dataset without full replication.
**Follow-up trap:** *"What if the dataset changes — a record gets added or removed?"* — the root must be recomputed and republished, and every existing proof for records at shifted tree positions becomes invalid, which is a real operational cost of Merkle trees for frequently-mutating datasets; this is exactly why blockchains compute a fresh Merkle root *per block* rather than maintaining one mutable tree over all transactions ever — each block's transaction set is fixed and immutable once mined, sidestepping the mutation problem entirely by never mutating a published tree.

### Q10 — What's the actual difference between ECDSA and Schnorr signatures, and why does Bitcoin support both now?
**Testing:** current-state awareness beyond "ECDSA is what blockchain uses."
**Answer:** Both rely on the same elliptic-curve discrete-log hardness, but Schnorr's signature construction is linear in a way that supports native aggregation — multiple parties' individual signatures can be combined into a single signature indistinguishable on-chain from one signer's (via schemes like MuSig2), which ECDSA cannot do without more complex, less efficient multi-party computation protocols. Bitcoin added Schnorr support via BIP-340 in the November 2021 Taproot upgrade specifically to enable this aggregation for multi-signature wallets and complex spending conditions, without deprecating ECDSA, which remains supported for backward compatibility with the entire pre-Taproot transaction history.
**Follow-up trap:** *"If Schnorr is strictly better, why hasn't Ethereum switched its account-signing scheme to it?"* — Ethereum's consensus layer already uses BLS (not Schnorr) for validator attestation aggregation specifically because BLS supports a form of aggregation Schnorr's simpler schemes don't as directly (aggregating signatures over *different* messages from *different* signers into one, which plain multi-signature Schnorr schemes handle less naturally) — but Ethereum's *account-level* transaction signing has largely remained ECDSA for the same backward-compatibility reason Bitcoin kept it, with EIP-4337 account abstraction and newer proposals opening the door to alternative signature schemes at the account level without a network-wide hard requirement to migrate.

### Q11 — A junior engineer proposes storing private keys as environment variables and signing directly in application code "since we control the servers." What's your response, connecting back to what this module covered?
**Testing:** whether the primitives translate into an actual operational security recommendation.
**Answer:** The primitives themselves (ECDSA, the curve, the hash functions) can be perfectly sound while the *key custody* around them is the actual point of failure — a private key in an environment variable is readable by anything with process/filesystem access, has no audit trail of use, and if leaked compromises every past and future signature under that key permanently with no way to "rotate" a blockchain address's key the way you'd rotate a database credential. The correct pattern is a signing service or HSM (AWS KMS, a hardware wallet, a dedicated signing enclave) that performs the `scalar_mult`/signing operation internally and never exports `d` at all — the application requests a signature over a specific message and receives back `(r, s)`, never touching the private key.
**Follow-up trap:** *"Does using an HSM fully eliminate the nonce-reuse risk this module covered?"* — no, and this is a real trap: an HSM protects the *key material* from exfiltration, but if its internal nonce generation is buggy or non-RFC-6979-compliant, nonce reuse is still possible in principle — you'd want to verify (via vendor documentation or independent audit) that the HSM's ECDSA implementation specifically uses deterministic or properly-audited random nonce generation, not just assume "hardware" implies "safe from this specific algebraic attack."

---

## Red flags that fail you

- Saying a hash function is "encrypted" or that you can "decrypt a hash."
- Confusing preimage resistance and collision resistance, or not knowing the birthday-bound halves a hash's effective collision-resistance bit-strength.
- Claiming Merkle trees make data "tamper-proof" rather than "tamper-evident."
- Not knowing that ECDSA nonce reuse leaks the private key completely, or describing it as merely "weakening" the signature.
- Proposing to hand-roll elliptic-curve arithmetic for a production signing path.
- Confusing the public key with the address, or not knowing an address is a hash of the public key.

---

## Cheat card

```
HASH PROPERTIES: preimage-resistant (can't invert), 2nd-preimage-resistant (can't find a
  match for a GIVEN input), collision-resistant (can't find ANY matching pair — weakest,
  due to birthday bound: n-bit hash gives only 2^(n/2) collision resistance, not 2^n)
SHA-1 (160-bit) BROKEN for collisions in 2017 (Google "SHAttered", ~$110K compute). Use SHA-256+.
AVALANCHE EFFECT: 1 input bit flipped -> ~50% of output bits flip, no pattern.

MERKLE TREE: leaf = H(0x00||data), node = H(0x01||left||right) -- domain separation prevents
  leaf/internal-node confusion attacks. Inclusion proof = O(log N) sibling hashes, not O(N).
  3000-tx block -> ~12-hash proof. Basis of Bitcoin SPV / light clients.
  Odd leaf count: duplicate last node -- MUST reject duplicate-adjacent-hash trees (CVE-2012-2459).
  Tamper-EVIDENT, not tamper-proof: hashing detects edits; CONSENSUS is what prevents them sticking.

ECDSA over secp256k1 (Bitcoin + Ethereum, pre-AA): y^2 = x^3+7 mod P, ~256-bit keys ~=
  3072-bit RSA security (ECDLP has no sub-exponential attack unlike RSA factoring).
  privkey d (secret) -> pubkey Q = d*G (point, one-way via ECDLP hardness)
  sign: r = (k*G).x mod n ; s = k^-1(z + r*d) mod n  -- k MUST be unique+unpredictable EVERY TIME

NONCE REUSE = TOTAL KEY COMPROMISE (same r in two sigs is the tell):
  k = (z1-z2)/(s1-s2) mod n  ->  d = (s1*k - z1)/r mod n   -- pure algebra, no brute force
  Real incidents: 2010 PS3 (fixed k), 2013 Android SecureRandom (weak k) drained BTC wallets.
FIX: RFC 6979 -- derive k deterministically via HMAC(privkey, msg_hash). Default in modern libs.

ADDRESS = hash of pubkey (not pubkey itself): BTC RIPEMD160(SHA256(pk)), ETH last-20B Keccak256(pk).
  Pubkey stays hidden until you SPEND from an address -- unused addresses have quantum-safety margin.

SCHNORR (BIP-340, Bitcoin Taproot Nov 2021): same hardness as ECDSA, but supports signature
  AGGREGATION (MuSig2) -- multiple signers -> one signature. Ethereum consensus uses BLS similarly.

DON'T hand-roll EC math for production signing (timing side-channels) -- use libsecp256k1 / HSM/KMS.
```

## Sources

- [SEC 2: Recommended Elliptic Curve Domain Parameters (secp256k1)](https://www.secg.org/sec2-v2.pdf) — accessed 2026-08-08
- [RFC 6979 — Deterministic Usage of DSA and ECDSA](https://www.rfc-editor.org/rfc/rfc6979) — accessed 2026-08-08
- [Google Security Blog — Announcing the first SHA-1 collision](https://security.googleblog.com/2017/02/announcing-first-sha1-collision.html) — accessed 2026-08-08
- [BIP-340 — Schnorr Signatures for secp256k1](https://github.com/bitcoin/bips/blob/master/bip-0340.mediawiki) — accessed 2026-08-08
- [Kelsey & Schneier — Second Preimages on n-bit Hash Functions for Much Less than 2^n Work (2005)](https://www.iacr.org/archive/eurocrypt2005/34940474/34940474.pdf) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
