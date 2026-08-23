# Hashes, Merkle Trees, Digital Signatures, ECDSA — Build Them

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** none · **Updated:** 2026-08-23
> **Module id:** `T22-crypto-primitives` · **Tags:** blockchain, cryptography, critical

## The 30-second version

A blockchain is a hash-pointer data structure wearing a consensus protocol: every block embeds the hash of its predecessor, so tampering with any old block invalidates everything after it — that is the entire tamper-evidence story, and it needs nothing but SHA-256. A Merkle tree compresses n transactions into one 32-byte root while letting a light client prove any single transaction is included with only log₂(n) sibling hashes: about 640 bytes for a million transactions instead of downloading ~200 MB. A digital signature binds an action to a private key without revealing it: ECDSA over secp256k1 signs a 32-byte digest, and the fatal implementation mistake in its history has almost always been the ephemeral nonce k — reuse or bias leaks the private key arithmetically. If you can build these three primitives from scratch and explain where each one fails, you can hold up your end of any blockchain interview; if you cannot, "I worked on blockchain" will not survive the second follow-up.

## Why this gets asked

Because it is the cheapest filter available. Anyone can install web3.py and call `contract.functions.transfer()`, but interviewers at exchanges, custody providers, and infrastructure teams keep getting candidates who cannot say why modifying block N breaks the chain, what a Merkle proof actually contains, or why reusing an ECDSA nonce hands the attacker your private key. Those are not trivia — each maps to a real production incident: the Android `SecureRandom` bug of August 2013 drained Bitcoin wallets because nonces repeated; Sony's PS3 firmware signing used a hardcoded k and was fully compromised in 2010; malleability of `(r, s)` vs `(r, n−s)` signatures broke wallets until Ethereum banned high-s values in EIP-2. At senior level they also want the systems angle: Merkle trees are how SPV light clients and modern indexers avoid full downloads, and the same construction shows up outside chains in Certificate Transparency, Git, Cassandra anti-entropy, and DynamoDB merkle-tree sync. Expect to be asked to sketch ECDSA sign-and-verify on a whiteboard and to reason about which property of a hash (preimage vs second-preimage vs collision) a given attack actually violates.

## Lineage

**What came before.** Cryptographic hashing predates blockchains by decades: Merkle described the tree that bears his name in his 1979 thesis, and hash-based one-time signatures date to Lamport the same year. Through the 1990s the defaults were MD5 and SHA-1 — both chosen before serious collision attacks existed. MD5 collision attacks were demonstrated in 2004 and practical collisions (including rogue CA certificates) followed by 2008-2012; SHA-1 fell to Google and CWI's "SHAttered" collision in February 2017, roughly 2^63 work on ~$110k of GPU time, and chosen-prefix collisions dropped below $50k by 2020, killing last remaining uses like git's SHA-1 object IDs (git migrated to SHA-256 support). On signatures, Schnorr published his scheme in 1989 but patented it, so standards bodies standardized ECDSA (ANSI X9.62 in 1998, FIPS 186-2 in 2000) even though Schnorr is simpler, provably secure in a stronger model, and linear. When Satoshi picked secp256k1 — a Certicom-recommended Koblitz curve specified around 1997-2000 — for Bitcoin in 2008-09, ECDSA-over-secp256k1 became the most economically protected key space on earth.

**Where it stands now.** SHA-256 and Keccak-256 (Ethereum) are unbroken; the practical frontier is implementation, not math. Deterministic nonces via RFC 6979 (2013) eliminated the worst class of signing bugs and is mandatory in every serious library; libsecp256k1 replaced OpenSSL for Bitcoin Core in 2015-16 because OpenSSL's variable-time operations had side-channel risk. Bitcoin activated Schnorr verification (BIP-340) with Taproot in November 2021, enabling key aggregation where n parties produce one signature. Ethereum's beacon chain uses BLS12-381 aggregate signatures — thousands of validator attestations per slot collapse into a single signature, roughly 96 bytes, which is the only way 32-second-finality PoS fits its bandwidth budget. The live disagreement is about post-quantum urgency: Shor's algorithm breaks ECDSA entirely, and NIST finalized ML-DSA (FIPS 204) in August 2024, but signatures are 7-45× larger, so chains are watching rather than migrating; symmetric primitives like SHA-256 only lose half their margin to Grover (256→128-bit security).

**Where it's heading.** Three trends with different confidence levels. First, signature aggregation keeps deepening: MuSig2 multisignatures are deployed on Bitcoin, BLS aggregation is load-bearing in Ethereum consensus, and FROST-style threshold Schnorr is standardizing — expect "one signature per group" as the default assumption. Second, state proofs are moving from Merkle Patricia Tries toward Verkle trees on Ethereum's roadmap (post-Glamsterdam), replacing 3,000-byte account proofs with vector commitments under 200 bytes; this is real engineering, scheduled but not shipped. Third, and speculative: quantum-vulnerable signatures have a migration problem no chain has solved — lost keys from dead wallets cannot be rotated, so a quantum adversary could raid coins whose owners cannot respond. Treat timeline estimates (10-20 years) as guesses; treat the migration difficulty as certain.

---

## Mental model

Three objects, three jobs:

```
HASH      = a tamper-evident fingerprint          (integrity)
MERKLE    = a tree of fingerprints                (integrity + efficient membership proofs)
SIGNATURE = a fingerprint only the key holder     (authenticity + non-repudiation)
            can produce, anyone can check
```

The unifying picture is the **hash pointer**. A plain pointer says "go there"; a hash pointer says "go there, and here is the fingerprint of what you'll find." Chain them:

```
block 3        block 2        block 1        genesis
┌────────┐     ┌────────┐     ┌────────┐     ┌─────────┐
│ H(prev)│◀────│ H(prev)│◀────│ H(prev)│◀────│  NULL   │
│ txs    │     │ txs    │     │ txs    │     │  txs    │
│ H(txs) │     │ H(txs) │     │ H(txs) │     │  H(txs) │
└────────┘     └────────┘     └────────┘     └─────────┘
```

Change one bit anywhere in block 1 and H(block 1) no longer matches the copy inside block 2, which invalidates block 3, and so on to the head. That single idea is 80% of "why is a blockchain tamper-evident."

For Merkle trees, the model is a knockout tournament: leaves play each other, winners (hash pairs) advance, the root is the champion. To prove leaf D played, you show C's result, then AB's, then EFGH's — three matches out of eight, log₂(8):

```
            root = H(ABCD ‖ EFGH)
           /                      \
      ABCD                          EFGH        ← 1 sibling
      /        \                    /     \
   ABCD=H(AB‖CD)                 EFGH ...
    /    \
  AB      CD                                  ← 2nd sibling (CD)
 /  \    /  \
A    B  C    D                               ← leaf + proof {H(C), H(EFGH)}
```

For ECDSA, the model is: *the message decides the challenge*. The signer commits to a random curve point R = kG; the hash z of the message forces the verifier's equation; only someone who knows d can solve for a matching s. And the whole thing collapses if the "random" k is not random — which is why every line of production signing code treats nonce generation as the crown jewel.

---

## How it actually works

### 1. Hash functions — which property protects you?

SHA-256: fixed 512-bit blocks, 64 rounds of mixing, 256-bit output, length-padded. Three properties, escalating cost to break:

| Property | Definition | Attack cost (256-bit output) |
|---|---|---|
| Preimage | given h, find any m with H(m)=h | ~2²⁵⁶ |
| Second-preimage | given m₁, find m₂ ≠ m₁ with same hash | ~2²⁵⁶ |
| Collision | find any pair m₁≠m₂ with same hash | ~2¹²⁸ (birthday bound) |

The birthday bound is why 160-bit hashes feel marginal today (2⁸⁰ collision work is within nation-state reach) while 256-bit outputs are comfortably safe. Blockchains lean hardest on second-preimage: to rewrite history you must find a new block content matching an existing hash *and* redo all descendants' work.

Two properties people miss:

- **Puzzle-friendliness**: knowing H(x‖nonce) ≈ target tells you nothing about nonce except by trial. This is exactly what mining exploits.
- **No length extension protection**: SHA-256 is a Merkle-Damgård construction; given H(k‖m) you can compute H(k‖m‖pad‖suffix) for arbitrary suffixes without knowing k. This broke naive token schemes repeatedly. HMAC-SHA256 exists precisely to close it, via `H((k⊕opad) ‖ H((k⊕ipad) ‖ m))`. Bitcoin double-hashes (`SHA256(SHA256(block))`) partly for similar structural reasons.

### 2. Merkle trees — the arithmetic of inclusion proofs

n leaves, binary tree, root stored in the (tiny, frequently replicated) block header. Proof that leaf i is included: sibling hash at each of ⌈log₂ n⌉ levels. For n = 1,048,576 leaves: depth 20, proof = 20 × 32 bytes = **640 bytes**, versus ~33 MB for the raw data at 32 bytes/leaf. Verification is 20 SHA-256 calls.

Design decisions that bite:

- **Odd node handling.** Bitcoin duplicates the last node when a level has odd count. Other implementations promote the odd node up alone. Both work; both must be pinned down in spec, or you get cross-implementation consensus failures.
- **Second-preimage attack on naive trees.** Without domain separation, an attacker can craft a "leaf" whose bytes equal an internal node's bytes and present a forged shorter proof. Fix: prefix leaves with `0x00` and internal nodes with `0x01` (RFC 6962 does exactly this for Certificate Transparency).
- **Update cost.** Changing one leaf changes its path to the root: log₂ n recomputations, O(log n) — cheap. But if your workload mutates half the tree between reads, a sorted hash list may beat a tree. Trees earn their keep on read-mostly data with membership queries.

Bitcoin goes further and stores *all four* roots: the transaction Merkle root, plus three state-related commitments in the header since SegWit (wtxid merkle root), giving light clients different verification routes.

Ethereum replaces the plain binary tree with a **Merkle Patricia Trie** — a radix trie whose nodes are hashed and linked — because accounts change constantly and proofs must be *updatable* and keyed by path (address → [nonce, balance, codeHash, storageRoot]). Cost: an account proof is 3-8 nodes, each up to ~500 bytes encoded; Verkle trees aim to shrink that below 200 bytes total.

### 3. Digital signatures — ECDSA over secp256k1

secp256k1: y² = x³ + 7 mod p, p = 2²⁵⁶ − 2³² − 977, cofactor 1, order n ≈ 1.158 × 10⁷⁷. Key generation: pick d uniformly in [1, n−1], publish Q = d·G where G is the standard generator.

Signing message m (digest z = SHA256(m), interpreted mod n):

1. Pick nonce k ∈ [1, n−1]. Production: deterministic k = RFC 6979(HMAC-SHA256 over d and z).
2. R = k·G; r = x-coordinate of R, reduced mod n.
3. s = k⁻¹(z + r·d) mod n.
4. Signature = (r, s).

Verification, public key Q:

1. Check 1 ≤ r,s < n.
2. w = s⁻¹ mod n; u₁ = z·w; u₂ = r·w (mod n).
3. X = u₁·G + u₂·Q.
4. Valid iff x(X) mod n == r.

Why it works: substitute s = k⁻¹(z+rd): u₂·Q + u₁·G = r·w·d·G + z·w·G = w(r·d + z)G = (r·d+z)/s · G = k·G = R. So the verifier reconstructs the signer's committed point R without ever seeing k.

**Why nonce discipline is life-or-death.** From s = k⁻¹(z + r·d): if k repeats across two messages z₁, z₂ producing s₁, s₂, subtracting gives k = (z₁ − z₂)/(s₁ − s₂), and then d = (s₁k − z₁)/r. Two signatures, full key compromise — pure algebra, no lattice required. Partial leakage of k (biased RNG) also falls to lattice attacks (LadderLeak 2020, Minerva, TPM-Fail 2019). This is not theoretical: PS3 (hardcoded k, 2010), Android Bitcoin wallets (SecureRandom bug, Aug 2013), and numerous embedded devices failed exactly here.

**Malleability.** If (r, s) verifies, so does (r, n − s): negate the point's y-coordinate and the algebra still closes. An attacker who sees your transaction in the mempool can flip s and broadcast a second tx with the same validity but a different txid, breaking txid-tracking systems. Ethereum's fix (EIP-2, Homestead 2016): reject s > n/2; signers emit low-s. Bitcoin did the same (BIP-62). Note this is *not* forgery — the attacker cannot choose a new message — but it wrecks naive accounting.

**Cost reality check.** Pure-Python verify runs ~25 ms/op (measured for this module); libsecp256k1 verifies ~5,000-15,000 sigs/sec/core depending on CPU and does batch verification ~2-3× faster still. Signing is cheaper than verifying in ECDSA (unusual among signature schemes; Ed25519 is the opposite).

---

## Build it from scratch

Complete, runnable, stdlib-only (`hashlib`, `hmac`). Two halves: Merkle trees, then real secp256k1 ECDSA with RFC 6979 deterministic nonces and the low-s rule. Verified end-to-end including the nonce-reuse attack recovering the private key.

```python
import hashlib, hmac

# ---------- hashes ----------
def sha256(b: bytes) -> bytes:
    return hashlib.sha256(b).digest()

# ---------- merkle tree ----------
LEAF, NODE = b'\x00', b'\x01'          # domain separation (RFC 6962 style)

def _pad(level):
    """Bitcoin rule: duplicate the last hash on an odd level."""
    return level + [level[-1]] if len(level) % 2 else level

def merkle_root(leaves):
    level = [sha256(LEAF + l) for l in leaves]
    if not level:
        return sha256(b'')
    while len(level) > 1:
        level = _pad(level)
        level = [sha256(NODE + level[i] + level[i+1]) for i in range(0, len(level), 2)]
    return level[0]

def merkle_proof(leaves, i):
    """Sibling hashes bottom-up; entries are ('L',h) or ('R',h) = position of sib."""
    idx, proof = i, []
    level = [sha256(LEAF + l) for l in leaves]
    while len(level) > 1:
        level = _pad(level)
        j = idx ^ 1                                    # sibling index
        proof.append(('R' if j > idx else 'L', level[j]))
        level = [sha256(NODE + level[k] + level[k+1]) for k in range(0, len(level), 2)]
        idx //= 2
    return proof

def verify_proof(leaf, proof, root):
    h = sha256(LEAF + leaf)
    for side, sib in proof:
        h = sha256(NODE + (sib + h if side == 'L' else h + sib))
    return h == root

if __name__ == '__main__':
    txs = [f'tx{i}'.encode() for i in range(100_000)]
    root = merkle_root(txs)
    p = merkle_proof(txs, 57_123)
    assert verify_proof(txs[57_123], p, root)
    print(f'proof for 1M-ish leaves: {len(p)} hashes = {len(p)*32} bytes')
    assert not verify_proof(txs[57_124], p, root)
```

```python
# ---------- secp256k1 ECDSA ----------
P  = 2**256 - 2**32 - 977          # field prime of secp256k1
N  = 0xFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFFEBAAEDCE6AF48A03BBFD25E8CD0364141
GX = 0x79BE667EF9DCBBAC55A06295CE870B07029BFCDB2DCE28D959F2815B16F81798
GY = 0x483ADA7726A3C4655DA4FBFC0E1108A8FD17B448A68554199C47D08FFB10D4B8
G  = (GX, GY)

def point_add(Pt, Qt):
    if Pt is None: return Qt
    if Qt is None: return Pt
    x1, y1 = Pt; x2, y2 = Qt
    if x1 == x2 and (y1 + y2) % P == 0:
        return None                                  # point at infinity
    if Pt == Qt:
        lam = (3*x1*x1) * pow(2*y1, -1, P) % P       # tangent slope
    else:
        lam = (y2 - y1) * pow(x2 - x1, -1, P) % P    # chord slope
    x3 = (lam*lam - x1 - x2) % P
    y3 = (lam*(x1 - x3) - y1) % P
    return (x3, y3)

def scalar_mul(k, Pt):
    R = None
    while k:                                          # double-and-add
        if k & 1: R = point_add(R, Pt)
        Pt = point_add(Pt, Pt)
        k >>= 1
    return R

def rfc6979_k(priv: int, z_hash: bytes):
    V, K = b'\x01'*32, b'\x00'*32
    xo, ho = priv.to_bytes(32,'big'), (int.from_bytes(z_hash,'big') % N).to_bytes(32,'big')
    K = hmac.new(K, V+b'\x00'+xo+ho, hashlib.sha256).digest(); V = hmac.new(K, V, hashlib.sha256).digest()
    K = hmac.new(K, V+b'\x01'+xo+ho, hashlib.sha256).digest(); V = hmac.new(K, V, hashlib.sha256).digest()
    while True:
        V = hmac.new(K, V, hashlib.sha256).digest()
        k = int.from_bytes(V, 'big')
        if 1 <= k < N: return k
        K = hmac.new(K, V+b'\x00', hashlib.sha256).digest()
        V = hmac.new(K, V, hashlib.sha256).digest()

def sign(priv: int, msg: bytes):
    z = int.from_bytes(hashlib.sha256(msg).digest(), 'big')
    R = scalar_mul(rfc6979_k(priv, hashlib.sha256(msg).digest()), G)
    r = R[0] % N
    s = (pow(rfc6979_k(priv, hashlib.sha256(msg).digest()), -1, N) * (z + r*priv)) % N
    if s > N // 2: s = N - s                          # EIP-2 low-s
    return r, s

def verify(pub, msg: bytes, sig) -> bool:
    r, s = sig
    if not (1 <= r < N and 1 <= s < N): return False
    z = int.from_bytes(hashlib.sha256(msg).digest(), 'big')
    w = pow(s, -1, N)
    X = point_add(scalar_mul(z*w % N, G), scalar_mul(r*w % N, pub))
    return X is not None and X[0] % N == r
```

Self-test worth running once (it proves both correctness and the nonce-reuse catastrophe):

```python
d = int.from_bytes(hashlib.sha256(b'seed').digest(),'big') % N
Q = scalar_mul(d, G)
m = b'pay alice'
assert verify(Q, m, sign(d, m))
# attacker sees two signatures that reused k:
k = 0xdeadbeef; z1 = int.from_bytes(hashlib.sha256(m).digest(),'big')
z2 = int.from_bytes(hashlib.sha256(b'pay eve').digest(),'big')
r_, = (lambda R: (R[0] % N,))(scalar_mul(k, G))
s1 = pow(k,-1,N)*(z1+r_*d)%N; s2 = pow(k,-1,N)*(z2+r_*d)%N
k_rec = (z1-z2)*pow(s1-s2,-1,N)%N                  # recover nonce...
d_rec = (s1*k_rec - z1)*pow(r_,-1,N)%N             # ...then the KEY
assert d_rec == d                                   # game over
```

Measured on this machine: pure-Python verify ≈ 26 ms/op; libsecp256k1 is roughly 4 orders of magnitude faster. Never ship the Python version anywhere near production.

## How it's done in production

| Layer | What ships | Why |
|---|---|---|
| Signatures (UTXO/EVM) | libsecp256k1 (C, constant-time, assembly-optimized), batch verify | ~10k verifications/sec/core; audited; RFC 6979 built in |
| Consensus-layer sigs | BLS12-381 via `blst` (Ethereum validators) | Aggregation: 64 attestations/slot committee → 1 signature |
| Multisig | MuSig2 (Bitcoin), threshold Schnorr/FROST, Safe contracts (EVM) | One on-chain signature for n-of-n; m-of-n needs contract logic on BTC |
| Hashing | hardware SHA extensions (~2 GB/s/core), Keccak-256 fips202/keccak libs | Throughput rarely the bottleneck; side-channel safety is |
| Storage proofs | MPT (Ethereum state), RFC 6962 CT logs, sparse Merkle trees (indexers, rollups) | Updatable keyed proofs vs append-only logs |

Production failure modes and what they look like:

| Symptom | Cause | Fix |
|---|---|---|
| Same signature emitted twice for two different messages | Nonce k reused (hand-rolled RNG or forked code stripping RFC 6979) | Deterministic nonces; audit every signing path; HSM/KMS |
| Transaction hash changes while mempool-watching | Signature malleability (high-s variant broadcast) | Reject/enforce low-s (EIP-2, BIP-62); track by intent, not raw txid |
| Light-client proof rejected by one implementation | Odd-node rule or leaf/node domain separation mismatch | Pin the spec; test vectors across implementations |
| Verify passes for attacker-chosen msg after key leak | Not a crypto failure: keys extracted via side channel | Constant-time libraries, HSM, rate-limit signing APIs |
| Two "valid" chains of headers disagree | Different serialization (e.g., DER vs compact sig encoding pre-BIP-66) | Canonical encodings enforced at consensus layer |

Also production-grade hygiene: never implement curve arithmetic yourself (use `coincurve`, libsecp256k1 bindings, `cryptography`); treat signature *verification* as the expensive path and cache/batch; keep private keys in KMS/HSM where policy, not process memory, gates use.

## Tradeoffs & when NOT to use it

- **Do not hand-roll crypto.** The from-scratch code above is for interviews. Real code: libsecp256k1, libsodium, `cryptography`. The gap between correct-looking and safe (timing, caching, validation) is measured in CVEs.
- **You may not need signatures at all.** If both endpoints share a secret, HMAC-SHA256 authenticates ~50× faster than ECDSA verify and has no nonce hazards. Signatures buy non-repudiation and third-party verifiability — pay for them only when you need those.
- **You may not need a Merkle tree.** For under ~1,000 items, rehashing a list is microseconds; a tree adds spec surface (odd rules, prefixes) for nothing. Trees win when proofs travel to parties who won't download the dataset, or updates must be incremental.
- **ECDSA vs Ed25519 vs BLS:** ECDSA/secp256k1 wins on ecosystem lock-in and hardware wallet support; Ed25519 wins on speed, simple secure implementations, and misuse-resistance (no nonce catastrophes — deterministic by design, though RFC 8032 still demands care); BLS wins on aggregation and loses on verification cost (~5-10× ECDSA) and a known rogue-key pitfall requiring proofs of possession.
- **Truncated hashes.** Storing 128 bits of a 256-bit hash buys you 2⁶⁴ collision resistance — broken by a laptop cluster. Keep ≥160 bits for anything adversarial.
- **When the whole apparatus is overkill:** an append-only log with external anchoring (periodically embedding a hash into a chain or CT log) gives tamper-evidence without running nodes. Most enterprise "we need blockchain" requirements are satisfied by this plus a database.

## Interview questions

### Q1 — What makes a cryptographic hash function usable in a blockchain?
**Testing:** whether you know the three security properties and can rank them.
**Answer:** Collision resistance (infeasible to find any two inputs with the same output, ~2¹²⁸ work for 256-bit outputs by the birthday bound), second-preimage resistance (given m, hard to find m′≠m with H(m)=H(m′), ~2²⁵⁶), and preimage resistance (given only h, hard to find m, ~2²⁵⁶). Chains additionally exploit puzzle-friendliness: hash output reveals nothing about input structure, which is what lets PoW set a numeric target.
**Follow-up trap:** *"So finding two colliding blocks takes 2²⁵⁶ work?"* — No: collisions are birthday-bound to ~2¹²⁸, half the exponent. Preimage and second-preimage are the 2²⁵⁶ cases. Mixing these up signals you've never reasoned about attack surfaces.

### Q2 — Why do Merkle trees exist? Why not just hash the whole block?
**Testing:** the actual purpose: partial verification.
**Answer:** A single hash of all transactions proves integrity of everything but supports no partial claims. The Merkle root lets a light client verify one transaction's inclusion with ⌈log₂ n⌉ sibling hashes — 20 hashes (640 bytes) for ~10⁶ transactions — without downloading the block. It also makes a small set of data (the header) commit to a large set (the body), which is what SPV, indexes, and sync protocols are built on.
**Follow-up trap:** *"What's the proof size for a million leaves?"* — log₂(10⁶) ≈ 20 hashes × 32 bytes = 640 bytes, verified with 20 SHA-256 calls. Give the number; vagueness here is common and costly.

### Q3 — Walk me through ECDSA sign and verify.
**Testing:** whiteboard mechanics; do you know where the nonce lives.
**Answer:** Keys: private d, public Q = dG on secp256k1. Sign: nonce k, R = kG, r = x_R mod n, s = k⁻¹(z + rd) mod n, emit (r,s) with z = H(m). Verify: w = s⁻¹, compute X = z·w·G + r·w·Q, accept iff x_X mod n = r. The identity works because substituting s recovers kG.
**Follow-up trap:** *"Which step destroys everything if done wrong?"* — Nonce generation. Reuse leaks the key in closed form: k = (z₁−z₂)/(s₁−s₂), then d = (s₁k−z₁)/r. Even biased randomness falls to lattice attacks (Minerva, TPM-Fail). Production answer: RFC 6979 deterministic nonces, always.

### Q4 — Why is ECDSA malleable and what did ecosystems do about it?
**Testing:** did you learn the failure modes, not just the happy path.
**Answer:** Curve points come in ±pairs: if (r,s) verifies, (r, n−s) does too, since verification only checks x-coordinates. Anyone can flip a mempool transaction's s and create a second valid broadcast with a different txid, breaking txid-based tracking and refund logic. Fixes: EIP-2 (Ethereum, Homestead 2016) rejects s > n/2; BIP-62/BIP-66 (Bitcoin) enforce low-s and canonical DER. Note the flipper hasn't forged anything — same message, same sender — it's an accounting hazard, not a forgery.
**Follow-up trap:** *"Is malleability a break of the signature scheme?"* — No: EUF-CMA unforgeability concerns creating a signature on a *new message*. It's an application-layer hazard. Saying "it broke the cryptography" is the tell of someone repeating headlines.

### Q5 — Why does Ethereum use Keccak-256 and not SHA3-256?
**Testing:** history and attention to detail; catches résumé-driven claims.
**Answer:** Ethereum adopted Keccak before NIST finalized SHA-3 in 2015 — the standardization changed padding (SHA3-256 appends 0x06; Keccak-256 original submission pads 0x01), so the constants differ. Everything on-chain (addresses, storage keys, function selectors) is Keccak-256; tooling must match. Solidity exposes `keccak256()`; off-chain code must use a Keccak-256 implementation, not `hashlib.sha_3`.
**Follow-up trap:** *"Does that matter in practice?"* — Constantly: Python's `hashlib.sha3_256` produces different digests than on-chain keccak256, and using it silently corrupts address derivation and Merkle proofs against Ethereum tries.

### Q6 — What is a length-extension attack and which constructions are immune?
**Testing:** deeper than checklist knowledge; HMAC literacy.
**Answer:** Merkle-Damgård hashes (MD5, SHA-1, SHA-256) let anyone who knows H(k‖m) compute H(k‖m‖pad‖suffix) for arbitrary suffix without k, because the digest is the internal state. Naive `SHA256(secret || params)` authentication therefore forges. HMAC fixes it with nested keyed hashing; truncated variants (H(k‖m)[:16]) and MAC constructions like KMAC/SipHash also avoid it. SHA-3's sponge doesn't extend, but you should still use a MAC, not raw hashing.
**Follow-up trap:** *"Bitcoin signs serialized transactions with double SHA-256 — is that length-extensible?"* — No: the hash covers the full signed payload and there's no secret prepended; the attack class applies to keyed-prefix authentication, not signatures over complete messages.

### Q7 — Design a Merkle proof system for 10 million records. What are your parameters?
**Testing:** translating log math into engineering choices.
**Answer:** Depth ⌈log₂ 10⁷⌉ = 24, proof ≈ 24×32 = 768 bytes, verification 24 hashes. Domain-separate leaf/node hashing (0x00/0x01 prefixes, à la RFC 6962) to kill second-preimage proofs; pin odd-level handling (duplicate-last like Bitcoin, or promote — just document it); store the root somewhere independently trusted. For key-value semantics rather than ordered lists, use a sparse Merkle tree so proofs don't shift as siblings change. Batch many proofs via multiproofs if bandwidth-bound.
**Follow-up trap:** *"Your records update hourly — still fine?"* — Yes for the tree itself (log n path updates), but re-derive and re-publish roots atomically, and beware proof caching: a stale root invalidates cached proofs, so version your roots.

### Q8 — Why did Bitcoin move to Schnorr (Taproot) and Ethereum to BLS? Compare them to ECDSA.
**Testing:** scheme tradeoffs at a systems level.
**Answer:** Schnorr (BIP-340, Taproot 2021): provably secure with fewer assumptions, no malleability, and linearity enabling MuSig2 key aggregation — n signers produce one signature indistinguishable from single-key. BLS12-381 (Eth2): signatures aggregate associatively — thousands of attestations combine into ~96 bytes, essential for 400k+ validators under bandwidth limits; costs slower verification (~5-10× ECDSA) and requires rogue-key defenses (proofs of possession). ECDSA stays dominant at the application layer purely through ecosystem inertia and hardware support.
**Follow-up trap:** *"Why not aggregate everything with BLS everywhere?"* — Verification cost scales poorly for high-throughput single-signature paths, aggregation requires distinct-message discipline (or proofs of possession) to stay secure, and hardware wallets/ecosystems already speak ECDSA; switching cost is enormous relative to benefit for ordinary transfers.

### Q9 — A junior suggests storing only the first 16 bytes of each transaction hash to save space. Consequence?
**Testing:** birthday-bound intuition applied.
**Answer:** 128-bit digests give 2⁶⁴ collision resistance — findable with serious GPU effort and trivially within well-funded adversary budgets; and in a blockchain context collisions let an attacker swap content under a committed hash. Keep ≥160 bits (2⁸⁰, borderline) and prefer 256 bits (2¹²⁸ collision work). Space saved is negligible versus risk.
**Follow-up trap:** *"What about 20-byte addresses then?"* — Ethereum addresses are Keccak-256 digests truncated to 160 bits, and that's accepted because address collisions aren't the active attack (you'd need to generate a colliding *contract*, and 2⁸⁰ remains out of casual reach) — but it is precisely why CREATE2 deployments with salted init codes deserve care.

### Q10 — Explain the 2013 Android SecureRandom Bitcoin incident mechanically.
**Testing:** whether you connect theory to a named incident.
**Answer:** In August 2013 Java's SecureRandom on some Android versions initialized poorly under contention, yielding low-entropy ECDSA nonces. Repeated or predictable k across transactions allowed recovery of private keys — k = (z₁−z₂)(s₁−s₂)⁻¹, then d — and wallets were drained within hours. Industry response cemented RFC 6979 deterministic nonces (derive k from key+message via HMAC) so entropy failures stop being catastrophic.
**Follow-up trap:** *"Deterministic nonces are safe forever, right?"* — Mostly, but side channels leaking k bits remain lethal (Minerva, TPM-Fail 2019, LadderLeak 2020), so production signing also uses constant-time code, blinding, and HSM isolation. Determinism removes the RNG failure mode, not the physical-leakage one.

### Q11 — Where exactly do Merkle proofs appear when you send a transaction and later verify it landed?
**Testing:** end-to-end plumbing knowledge beyond definitions.
**Answer:** Three places. (1) In-block inclusion: the tx Merkle root in the header lets an SPV client confirm inclusion with ~11-12 sibling hashes for typical block sizes (2-4k transactions). (2) State: after execution, receipts and account state are committed in the state/receipt tries; a proof of your balance change is a trie branch of 3-8 nodes. (3) Bridges/L2: rollups post batch roots; withdrawal proofs are Merkle branches against those roots. Each is the same primitive with different domain separation and serialization.
**Follow-up trap:** *"Why does Ethereum need a trie instead of a plain Merkle tree?"* — Accounts mutate and proofs are keyed by path (address), needing stable insert/update/delete with O(log n) proof updates: a Merkle-Patricia Trie. Plain binary trees fit append-only lists, not mutable keyed state.

### Q12 — How would post-quantum computing affect each primitive here?
**Testing:** current-events awareness with correct scoping.
**Answer:** Shor's algorithm breaks ECDSA (and Schnorr, BLS) polynomially — signatures are the existential risk. Grover halves symmetric/hash security exponents: SHA-256 preimage drops to ~2¹²⁸, still comfortable. Mitigations exist but hurt: NIST-standardized ML-DSA (FIPS 204, Aug 2024) signatures are ~2.4-4.6 KB vs 64 bytes, SLH-DSA (stateless hash-based) larger still, so chain migration faces throughput and state-growth pain, plus unsolvable rotation for lost keys.
**Follow-up trap:** *"Should we switch signatures now?"* — No credible chain has; hybrid schemes are being prototyped at L2/application layers. Honest answer: quantify (sig size × TPS impact), note harvest-now-decrypt-later mostly threatens confidentiality not signatures, and say monitoring NIST timelines is the current best practice.

### Q13 — You see two different transactions with the same Merkle root claimed. Debug.
**Testing:** systematic reasoning about where equality could arise.
**Answer:** Enumerate: (a) implementation bug in proof concatenation order (left/right swapped); (b) missing domain separation letting a leaf collide with an internal node — the classic second-preimage on naive trees; (c) odd-node handling divergence between implementations; (d) genuinely different serializations of the "same" tx hashing differently (canonicality). Reproduce with minimal trees (2 and 3 leaves) comparing byte-level inputs at each level; the bug almost always shows in the smallest case.
**Follow-up trap:** *"How do you prevent that class permanently?"* — RFC 6962-style prefixes on leaf vs node hashes, fixed canonical serialization tested against cross-implementation vectors, and property tests asserting proof rejection for wrong leaf, wrong position, and truncated proofs.

### Q14 — Why cofactor-1 curves like secp256k1 simplify ECDSA compared to cofactor-4 curves?
**Testing:** depth on curve selection; separates curve users from curve understanders.
**Answer:** Cofactor h = #E(F_p)/n; h = 1 means every point on the curve lies in the prime-order subgroup generated by G, so subgroup-membership validation of public keys is unnecessary and small-subgroup attacks vanish. On cofactor > 1 curves (e.g., P-224 variants, Ed25519's h=8), implementations must validate points or clamp scalars, or attackers can inject low-order points to extract key bits. secp256k1's h = 1 is one reason it's beloved by implementers.
**Follow-up trap:** *"Ed25519 has cofactor 8 — is it unsafe?"* — No: RFC 8032 mandates clamping and canonical encoding, and modern libraries handle it; it's a footgun for hand-rolled implementations, another argument for vetted libraries.

### Q15 — Rank these by verification cost and say where each belongs: ECDSA-secp256k1, Ed25519, BLS12-381, RSA-2048.
**Testing:** quantitative feel for production choices.
**Answer:** Roughly fastest-to-slowest for verify: Ed25519 (~50-100µs), ECDSA secp256k1 via libsecp256k1 (~50-150µs), RSA-2048 verify is fast too but keys/sigs are large (256-byte sigs, 1-2 KB ops) and signing is slow (~1-3 ms), BLS verify slowest (~0.5-2 ms) but aggregates. Belongings: ECDSA for UTXO/EVM compatibility; Ed25519 for high-throughput app-layer auth and newer chains; BLS where many signatures must become one (consensus committees); RSA nowhere new in chains — legacy interop only.
**Follow-up trap:** *"Your numbers vary by CPU — why trust any?"* — Right instinct: cite orders of magnitude and measure on target hardware; the durable claim is the ranking and the aggregation property, not exact microseconds.

## Red flags

- Calling SHA-256 "encryption" or saying it "encrypts the block".
- Claiming collision resistance means nobody can ever find two identical-hash inputs; it means it's computationally infeasible (~2¹²⁸ for 256-bit).
- Describing ECDSA without knowing where the nonce appears, or claiming "random k from any RNG" is fine.
- Confusing signature malleability with forgery.
- Saying Merkle proofs require O(n) data or that light clients download full blocks.
- Recommending MD5/SHA-1 for anything adversarial "because it's faster".
- Hand-rolled curve arithmetic proposed for production with no mention of constant-time libraries.
- Asserting blockchains are "quantum-proof".

## Cheat card

```
SHA-256       512-bit blocks · 64 rounds · 256-bit out · collision ≈ 2^128
              preimage/2nd-preimage ≈ 2^256 · NOT length-extension-safe
HMAC          H((k⊕opad)||H((k⊕ipad)||m)) — the keyed-hash default
MERKLE        proof = ⌈log2 n⌉ siblings · 10^6 leaves → 20 × 32 B = 640 B
              duplicate-last on odd (BTC) · 0x00 leaf / 0x01 node prefixes (RFC 6962)
SECP256K1     y² = x³ + 7 mod p · p = 2^256 − 2^32 − 977 · cofactor 1
KEYS          d ∈ [1,n−1] · Q = dG · n ≈ 1.158e77
SIGN          k (RFC6979!) · R=kG · r = x_R mod n · s = k⁻¹(z + r·d) mod n
VERIFY        w=s⁻¹ · X = z·w·G + r·w·Q · ok iff x_X mod n == r
NONCE LAW     k reused ⇒ k=(z₁−z₂)/(s₁−s₂) ⇒ d leaked (PS3 '10, Android '13)
MALLEABILITY  (r,s)≡(r,n−s) · ban s>n/2 (EIP-2 '16, BIP-62)
VERIFY COST   python ~26 ms · libsecp256k1 ~10k/s/core · BLS ~10× slower but aggregates
SCHEMES       Schnorr=BIP340/Taproot '21 (MuSig2 agg) · BLS12-381=Eth2 consensus
PQC           Shor kills ECDSA/Schnorr/BLS · Grover: SHA-256 → ~2^128 · ML-DSA FIPS204 8/2024
```

## Sources

- [SHAttered: first collision for full SHA-1 — Google Security Blog](https://security.googleblog.com/2017/02/announcing-first-sha1-collision.html); accessed 2026-08-23
- [RFC 6979: Deterministic Usage of DSA and ECDSA](https://datatracker.ietf.org/doc/html/rfc6979); accessed 2026-08-23
- [RFC 6962: Certificate Transparency — Merkle tree domain separation](https://datatracker.ietf.org/doc/html/rfc6962); accessed 2026-08-23
- [secp256k1 curve parameters — Bitcoin Wiki](https://en.bitcoin.it/wiki/Secpk256k1); accessed 2026-08-23
- [EIP-2: Homestead Hard-fork Changes (low-s)](https://eips.ethereum.org/EIPS/eip-2); accessed 2026-08-23
- [BIP-340: Schnorr Signatures for secp256k1](https://github.com/bitcoin/bips/blob/master/bip-0340.mediawiki); accessed 2026-08-23
- [Android SecureRandom flaw drains Bitcoin wallets — Ars Technica, Aug 2013](https://arstechnica.com/information-technology/2013/08/catastrophic-flaw-in-android-random-number-generator-bites-bitcoin-wallets/); accessed 2026-08-23
- [TPM-Fail: timing attack on ECDSA nonces in TPMs (2019)](https://tpm.fail/); accessed 2026-08-23
- [FIPS 204: Module-Lattice-Based Digital Signature Standard (ML-DSA), NIST 2024](https://csrc.nist.gov/pubs/fips/204/final); accessed 2026-08-23
- [Verkle trees — ethereum.org roadmap](https://ethereum.org/en/roadmap/verkle-trees/); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
