# Production notes — crypto primitives

## Where these actually run

| Primitive | Bitcoin | Ethereum | The boring world |
|---|---|---|---|
| SHA-256 | block headers, PoW, txids | (Keccak-256 instead) | git, TLS, package integrity, password KDFs |
| Merkle tree | tx root per block, ~12-hash SPV proofs | trie variants (Merkle-Patricia), Merkleized receipts | Certificate Transparency logs, git's object model, IPFS, DynamoDB-like anti-entropy, Zilliqa/Casper light clients |
| ECDSA secp256k1 | every legacy tx signature, every taproot key-path spend | every EOA tx (EIP-2 bounds what a "valid" key is) | TLS 1.3 (P-256), SSH, Signal's X3DH |

## Merkle trees at real scale

Bitcoin never materializes the whole tree. It stores leaves plus a 64-bit node-count trick (BIP 37 / the `CTxMerkleTree` logic in `merkleblock`): for any height, the index of the leftmost internal node at that level is `(width + 1) >> 1 << 1` (pre-2010) or just duplicating (`width >> 1` post-fix) — because of CVE-2017-12842, the earlier "duplicate only if next level is odd" rule let a 64-leaf tree be spun up where one leaf was two places at once, an attacker could forge a proof for a tx that wasn't there. **The naive rule and the Bitcoin rule differ**; yours is the Bitcoin rule.

Certificate Transparency does the same for TLS certs, but append-only and publicly auditable: each log is a Merkle tree of leaves over time, a signed tree head (root + size + timestamp) is published each MMD (`maximum merge delay`, currently ~1 day), and any two auditors comparing STHs detect when a log has served two different histories for the same size — which is what catching a mis-issuing CA reduces to: two contradictory roots is the only signal you need. Your `.proof(0)` on the first leaf is what an inclusion proof in a CT log is structurally.

eth2's beacon chain uses `hash_tree_root` with **zero-bit padding** (SSZ), not duplicate-last, so every tree is depth 4096-padded — same idea, different padding rule, and the difference is exactly what made the Bitcoin CVE. Proof: zero-hash constants are precomputed to depth 64 (`ZERO_HASHES` in the spec repo).

## RSA-PSS vs ECDSA — what production picks

- RSA-2048 is ~256 bytes per signature; a secp256k1 signature is 64 bytes raw, ~70-72 DER. When every node stores every tx forever and relays them to peers, 3.7x is not cosmetic — it's the reason no blockchain uses RSA for tx signing.
- secp256k1 is a **Koblitz curve** chosen so `a=0`, making `j=invariant 0` and enabling the `endomorphism` trick (GLV) for a ~1.5x speedup on the scalar mult in libsecp256k1.
- RSA keys are not where the pain is. ECDSA's is.

## The thing production adds over this lab

**Hardware wallets / secure elements.** The private key never exists in process memory. A Ledger or YubiHSM holds the key inside a chip and exposes only `sign(msg) → sig` over a narrow channel; the host can request signatures but never read the key. The Bitcoin Core `wallet` ships with `-signer` support that hands raw signing to an external process or HSM for the same isolation on servers.

**Deterministic ECDSA (RFC 6979).** Your `ecdsa.sign(...)` picks a random nonce `k` from the process PRNG. If `k` ever repeats with the same key across two messages — or even leaks a few bits per signature over hundreds of signatures (Biryukov-Polakov-Saxena, lattice attacks on partial nonce leakage, as in the 2013 Android `SecureRandom` bug or the 2010 Sony PS3 EC-key blunder) — the private key falls out with two lines of modular arithmetic:
```
k = (s1 - s2) / (h(m1) - h(m2)) mod n
d  = (s1 * k - h(m1)) / r      mod n
```
RFC 6979 kills this by deriving `k` as HMAC-SHA256(private_key, message_hash) iterated until it lands in `[1, n-1]` — no RNG anywhere in the signing path. The `python-ecdsa` library does this by default (`sign_deterministic`), libsecp256k1 always does, `cryptography` uses OpenSSL's ECDSA_do_sign which is also deterministic-RFC-6979 for P-256 curves since OpenSSL 1.1. For this lab you used the hazmat API, which routes through OpenSSL — so your signatures are already deterministic; a fun exercise is to verify that signing the same message twice yields the same bytes, which RSA-PSS with random salt length does NOT.

**What the `cryptography` library adds that your `verify` doesn't:**

- PSS `salt_length` is randomized per-signature by default (a "randomized signature" — same msg signed twice, different sigs, both verify). Your implementation uses `PSS.DIGEST_LENGTH` (deterministic salt length) for reproducibility, which is fine for tests but isn't a meaningful security tradeoff — the salt is a hedge against chosen-prefix factoring, not a secret.
- It validates public keys on load (point-on-curve, subgroup, order checks). ECDSA has no `verify` failures from malformed public keys in practice, but libsecp256k1 explicitly checks that `Q` is on-curve and not the point at infinity — exactly what CVE-2020-28272 style bugs are made of when skipped.
- DER parsing rejects non-canonical encodings (a `0x00` sign-extension byte appearing or missing) — a common source of malleability exploits when exchanges accepted a malleable txid as final (Mt. Gox blamed this in 2014, though they were also insolvent independently).

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Wallet drained, no phishing | RNG-generated `k` repeated across two signatures | RFC 6979, or a hardware wallet |
| ECDSA sig verifies on one node, fails on another | Non-canonical DER (high-S) accepted on one side, rejected on the other | BIP 62 / BIP 66: low-S canonical encoding enforced protocol-wide |
| Proof verifies locally but node rejects it | Duplicate-the-last-leaf rule mismatch (your tree vs Bitcoin pre-2010 vs SSZ padding) | Match the chain's rule exactly; test odd leaf counts specifically |
| Slow verification at scale | 1 sig/tx, millions of txs | BLS aggregation (eth2), libsecp256k1 batch verify (~2-4x), or Schnorr batch verification (BIP 340 note: ~1.6x) |
| Signing service latency spikes | RSA-2048 sign is ~1-2 ms, ECDSA sign ~0.1 ms, but rate-limiting/FIPS crypto (AES-GCM on the HSM channel) adds overhead | Pre-generate keys, or batch attestations |

## The 3 questions an interviewer asks

1. *"Why did Bitcoin choose ECDSA over RSA?"* — compact signatures (64 bytes raw vs 256), compact keys (33 vs ~300 bytes), verification speed on 2009 hardware. Everything that matters when every full node stores and relays every transaction.
2. *"What happens if an ECDSA nonce is reused?"* — full private key recovery from two signatures, deterministic algebra, no brute force: `k = (s1-s2)/(h1-h2) mod n`. Sony PS3 (fixed `k` hardcoded), Android Bitcoin wallets 2013 (`SecureRandom` bug), multiple hardware wallets. RFC 6979 exists specifically to make this impossible by construction.
3. *"Why does a Merkle proof cost O(log N)?"* — halving levels: N leaves, N/2 nodes at level 1, N/4 at level 2, so depth is `ceil(log2 N)` and the proof reveals one sibling per level. 3,000 txs → depth 12 → 12 sibling hashes (384 bytes), vs 3,000 tx hashes (96 KB) to re-download the block. This is exactly what SPV wallets (BIP 37 / BIP 157 neutrino) rely on.

One last thing about that first table: the reason Certificate Transparency exists is that the browser vendors got tired of 600+ trusted CAs each able to mint a cert for any domain. Merkle trees + signed tree heads + public audits turned "trust every CA forever" into "catch any CA that mis-issues twice" — same primitives, different composition, no blockchain required.
