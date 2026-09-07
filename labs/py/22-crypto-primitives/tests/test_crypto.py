"""Lab 22 tests — hashes, Merkle proofs, RSA-PSS, ECDSA. No sleeps, no network."""
import pathlib

import pytest


# ------------------------------------------------------------------- hashes
def test_sha256_str_deterministic_known_vector(R):
    # canonical SHA-256 test vectors (NIST / RFC 6234)
    assert R.sha256_str(b"").hex() == \
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    assert R.sha256_str("abc").hex() == \
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
    assert R.sha256_str(b"abc") == R.sha256_str("abc")     # str and bytes agree



def test_sha256_avalanche_one_bit_change(R):
    # 1-bit input difference must produce a completely different digest
    a = R.sha256_str(b"attack at dawn")
    b = R.sha256_str(b"attack at dusk")       # 'n'(0x6e) vs 'k'(0x6b): 2 bits
    c = R.sha256_str(b"btack at dawn")        # 'a'->'b': 1 bit (0x61 vs 0x62)
    assert a != b
    assert a != c
    assert b != c
    # hamming distance between a and c should be substantial (~128 of 256)
    diff = [x ^ y for x, y in zip(a, c)]
    assert sum(bin(v).count("1") for v in diff) > 32


def test_sha256_file_streams_from_disk(R, tmp_path):
    p: pathlib.Path = tmp_path / "blob.bin"
    p.write_bytes(b"file content here")
    assert R.sha256_file(p) == R.sha256_str(b"file content here")
    big = tmp_path / "big.bin"
    big.write_bytes(b"x" * 300_000)           # multiple 64 KiB chunks
    assert R.sha256_file(big) == R.sha256_str(b"x" * 300_000)


# ---------------------------------------------------------------------- hmac
def test_hmac_deterministic_and_keyed(R):
    tag = R.hmac_sha256(b"k" * 32, b"msg")
    assert len(tag) == 32
    assert tag == R.hmac_sha256(b"k" * 32, b"msg")            # deterministic
    assert tag != R.hmac_sha256(b"j" * 32, b"msg")           # exact key required
    assert tag != R.hmac_sha256(b"k" * 32, b"msh")           # exact msg required
    # RFC 4231 test case 2:
    assert R.hmac_sha256(b"Jefe", b"what do ya want for nothing?").hex() == \
        "5bdcc146bf60754e6a042426089575c75a003f089d2739839dec58b964ec3843"


# ---------------------------------------------------------------- merkle tree
def _tx(i: int) -> bytes:
    return f"tx-{i}: send 5 BTC to {i}".encode()


def test_merkle_empty_root_none(R):
    assert R.MerkleTree([]).root is None


def test_merkle_single_leaf_root_is_leaf_hash(R):
    t = R.MerkleTree([b"solo"])
    assert t.root == R.sha256_str(b"solo")
    assert t.n_leaves == 1
    assert R.MerkleTree.verify(t.root, b"solo", 0, t.proof(0), 1)


def test_merkle_four_leaf_proof_verifies(R):
    leaves = [_tx(i) for i in range(4)]
    t = R.MerkleTree(leaves)
    assert t.n_leaves == 4
    for i in range(4):
        proof = t.proof(i)
        assert len(proof) == 2                       # log2(4) siblings
        assert R.MerkleTree.verify(t.root, leaves[i], i, proof, 4)
        # a proof that does not reach the root depth must fail
        assert not R.MerkleTree.verify(t.root, leaves[i], i, proof[:-1], 4)


def test_merkle_five_leaves_odd_duplication_verifies(R):
    leaves = [_tx(i) for i in range(5)]
    t = R.MerkleTree(leaves)
    assert t.n_leaves == 5
    for i in range(5):
        assert R.MerkleTree.verify(t.root, leaves[i], i, t.proof(i), 5)


def test_merkle_tampered_leaf_fails(R):
    leaves = [_tx(i) for i in range(4)]
    t = R.MerkleTree(leaves)
    proof = t.proof(2)
    evil = _tx(2)[:-1] + b"X"                        # one byte changed
    assert not R.MerkleTree.verify(t.root, evil, 2, proof, 4)
    # and the honest leaf against someone else's proof fails too
    assert not R.MerkleTree.verify(t.root, _tx(1), 2, proof, 4)


def test_merkle_wrong_index_fails(R):
    leaves = [_tx(i) for i in range(4)]
    t = R.MerkleTree(leaves)
    proof = t.proof(0)
    # claim leaf 0 is at index 3 — the proof's direction flags say "right
    # side twice" but index 3 says "left side twice": must not verify
    assert not R.MerkleTree.verify(t.root, leaves[0], 3, proof, 4)
    assert not R.MerkleTree.verify(t.root, leaves[0], 1, proof, 4)
    # honest index + honest proof still verifies
    assert R.MerkleTree.verify(t.root, leaves[0], 0, proof, 4)
    # out-of-range index and out-of-range n_leaves
    assert not R.MerkleTree.verify(t.root, leaves[0], 4, proof, 4)
    assert not R.MerkleTree.verify(t.root, leaves[0], 0, proof, 99)


def test_merkle_tampered_proof_fails(R):
    leaves = [_tx(i) for i in range(4)]
    t = R.MerkleTree(leaves)
    proof = t.proof(1)
    (sib, is_left) = proof[0]
    flipped = (sib[:-1] + b"Z", is_left)
    assert not R.MerkleTree.verify(t.root, leaves[1], 1, [flipped, proof[1]], 4)
    # flip the side flag instead of the hash
    flipped_side = (sib, not is_left)
    assert not R.MerkleTree.verify(t.root, leaves[1], 1, [flipped_side, proof[1]], 4)
    # swap sibling for another node's hash
    other = t.proof(0)[0][0]
    assert not R.MerkleTree.verify(t.root, leaves[1], 1, [(other, is_left), proof[1]], 4)


def test_merkle_root_changes_when_any_leaf_changes(R):
    base = R.MerkleTree([_tx(i) for i in range(8)])
    tampered = R.MerkleTree([_tx(0), *[_tx(i) for i in range(1, 7)], b"evil"])
    assert base.root != tampered.root
    # old proofs no longer validate against the new root
    old = base.proof(7)
    assert not R.MerkleTree.verify(tampered.root, _tx(7), 7, old, 8)


def test_merkle_proof_out_of_range_raises(R):
    t = R.MerkleTree([_tx(i) for i in range(3)])
    with pytest.raises(IndexError):
        t.proof(3)
    with pytest.raises(IndexError):
        t.proof(-1)


# ----------------------------------------------------------------- RSA (PSS)
def test_rsa_roundtrip(R):
    priv, pub = R.rsa_keypair()
    sig = R.rsa_sign(priv, b"pay alice 1 BTC")
    assert isinstance(sig, bytes) and len(sig) > 0
    assert R.rsa_verify(pub, b"pay alice 1 BTC", sig)


def test_rsa_tampered_data_fails_without_raising(R):
    priv, pub = R.rsa_keypair()
    sig = R.rsa_sign(priv, b"pay alice 1 BTC")
    assert R.rsa_verify(pub, b"pay alice 2 BTC", sig) is False    # amount changed
    assert R.rsa_verify(pub, b"pay alice 1 BTc", sig) is False    # 1 bit changed


def test_rsa_wrong_key_fails_without_raising(R):
    priv1, pub1 = R.rsa_keypair()
    _, pub2 = R.rsa_keypair()
    sig = R.rsa_sign(priv1, b"message")
    assert R.rsa_verify(pub2, b"message", sig) is False
    # garbage inputs must return False, never raise
    assert R.rsa_verify(pub1, b"message", b"\x00" * 256) is False
    assert R.rsa_verify(b"not a pem", b"message", sig) is False


# --------------------------------------------------------------------- ECDSA
def test_ecdsa_roundtrip(R):
    priv, pub = R.ecdsa_keypair()
    sig = R.ecdsa_sign(priv, b"from: me, to: bob, amount: 7")
    assert isinstance(sig, bytes) and len(sig) > 0
    assert R.ecdsa_verify(pub, b"from: me, to: bob, amount: 7", sig)


def test_ecdsa_tampered_data_fails(R):
    priv, pub = R.ecdsa_keypair()
    sig = R.ecdsa_sign(priv, b"from: me, to: bob, amount: 7")
    assert R.ecdsa_verify(pub, b"from: me, to: bob, amount: 8", sig) is False
    assert R.ecdsa_verify(pub, b"from: me, to: bob, amount: 7", b"\x00" * 70) is False
    _, other_pub = R.ecdsa_keypair()
    assert R.ecdsa_verify(other_pub, b"from: me, to: bob, amount: 7", sig) is False
