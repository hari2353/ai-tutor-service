# Lab 22: Crypto Primitives — Hashes, Merkle Trees, Signatures

**Track:** T22 Blockchain & Smart Contracts · **Time:** 2.5h · **XP:** 50
**Module:** `T22-crypto-primitives`

**You will build:** the three primitives underneath every blockchain — a SHA-256 hash layer, a Merkle tree with O(log N) inclusion proofs, and RSA-PSS + ECDSA signature round-trips — in one `crypto.py`.

**You will be able to answer:** *"Walk me through how a Merkle proof works, and why does a 3,000-tx Bitcoin block only need ~12 hashes to prove one transaction was in it?"*

## Setup

```bash
cd labs/py/22-crypto-primitives
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest cryptography                 # cryptography>=42 is fine
```

## The spec

1. **`sha256_file(path)` / `sha256_str(s)`** — convenience wrappers over `hashlib.sha256`. `sha256_str` accepts `str` (UTF-8) or `bytes`; `sha256_file` streams the file in chunks so a 10 GB blob does not become 10 GB of RAM.
2. **`hmac_sha256(key, msg)`** — keyed hash via the `hmac` module. Same key + msg → same tag; any other key → different tag. This is the MAC: symmetric authentication without a key pair.
3. **`MerkleTree(leaves: list[bytes])`** — hash each leaf once, then build pairing levels upwards. If a level has an **odd** number of nodes, **duplicate the last one** (Bitcoin's rule) before pairing. Empty leaf list → root `None`. Expose `.root` and `.n_leaves`.
   - **`proof(index)`** → `list[(sibling_hash, is_left)]`: for each level, the sibling your node will be combined with, and whether that sibling sits on the left (`True`) or right (`False`) of you. Index out of range → `IndexError`.
   - **`verify(root, leaf, index, proof, n_leaves)`** → `bool`, a `@staticmethod`. Recompute the root from the leaf + proof: at each step, if `is_left`, the parent is `H(sibling || me)`, else `H(me || sibling)`. Tampering the leaf, the proof, using the wrong index, or the wrong `n_leaves` must return `False`.
4. **RSA-PSS** — `rsa_keypair()` → `(private_pem, public_pem)` via `cryptography.hazmat` (2048-bit). `rsa_sign(priv_pem, data)` → signature; `rsa_verify(pub_pem, data, sig)` → `bool` using **PSS padding + SHA-256**. `rsa_verify` must **catch every invalid-signature path and return `False`** — never raise — because a malformed signature on the wire is a normal event, not an exception.
5. **ECDSA** — `ecdsa_keypair()` / `ecdsa_sign(priv_pem, data)` / `ecdsa_verify(pub_pem, data, sig)` on **secp256k1** with `ECDSA(SHA256)`. Same contract as RSA. This is what Bitcoin/Ethereum actually sign with.
6. **No sleeps, no network.** Key generation is the slowest thing here and it is honest work.

## Run the tests

```bash
pytest tests/ -q                 # against starter/ → FAILS. Make them pass.
pytest tests/ -q --solution      # the reference — must be green
```

The starter uses fixed hex digests where determinism is testable, so a passing run is a passing run — no flakiness, no seeds.

## Stretch goals

1. **RFC 6979 deterministic ECDSA** — derive the nonce `k` from the private key and message hash instead of the RNG, and explain why nonce reuse hands over the key. *(Interview: "Why did Sony's PS3 key leak?")*
2. **Merkle mountain ranges** — append-only trees where you never rebuild; the structure git and Certificate Transparency actually lean on. *(Interview: "How does CT detect a mis-issuing CA?")*
3. **Key recovery from a reused nonce** — given two secp256k1 signatures with the same `r` and same key, recover the private key in ~5 lines of algebra. Doing it once is the best possible vaccination against ever generating a nonce twice. *(Interview: "What broke the 2013 Android Bitcoin wallets?")*
4. **BLS aggregate signatures** — one signature over a thousand validators; what eth2's attestations actually use. *(Interview: "Why did Ethereum's consensus layer move off ECDSA?")*
