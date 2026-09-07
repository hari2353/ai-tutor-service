"""Lab 22 — crypto primitives: hashes, Merkle trees, RSA/ECDSA signatures.

Implement every function below. starter/ must fail the suite;
the identical suite against solution/ must pass.
"""
import hashlib
import hmac


# --------------------------------------------------------------------- hashes
def sha256_file(path):
    """SHA-256 of a file, streamed in chunks — never load the whole blob.

    Args:
        path: str or pathlib.Path to an existing file.
    Returns:
        bytes: the 32-byte digest.
    """
    raise NotImplementedError


def sha256_str(s):
    """SHA-256 of a string or bytes.

    Args:
        s: str (encoded UTF-8) or bytes.
    Returns:
        bytes: the 32-byte digest.
    """
    raise NotImplementedError


def hmac_sha256(key: bytes, msg: bytes) -> bytes:
    """Keyed-hash MAC: same key + msg -> same tag; any other key -> different.

    Returns:
        bytes: the 32-byte tag.
    """
    raise NotImplementedError


# ----------------------------------------------------------------- merkle tree
class MerkleTree:
    """Binary Merkle tree over hashed leaves (Bitcoin's duplication rule)."""

    def __init__(self, leaves: list):
        """leaves: list[bytes] (or strs, UTF-8 encoded). Empty -> root None."""
        raise NotImplementedError

    @property
    def root(self):
        """bytes — the Merkle root (None for an empty tree)."""
        raise NotImplementedError

    @property
    def n_leaves(self):
        """int — number of leaves the tree was built from."""
        raise NotImplementedError

    def proof(self, index: int) -> list:
        """Inclusion proof for leaf `index`.

        Returns:
            list of (sibling_hash: bytes, is_left: bool) per level, bottom-up.
            is_left=True means the sibling is on the LEFT of the current node.
        Raises:
            IndexError: index out of range.
        """
        raise NotImplementedError

    @staticmethod
    def verify(root, leaf, index: int, proof: list, n_leaves: int) -> bool:
        """Recompute the root from (leaf, index, proof, n_leaves) and compare.

        Must return False — never raise — for a tampered leaf, a tampered
        proof, a wrong index, or a wrong n_leaves.
        """
        raise NotImplementedError


# ------------------------------------------------------------------ RSA (PSS)
def rsa_keypair():
    """Generate a 2048-bit RSA keypair.

    Returns:
        (private_pem: bytes, public_pem: bytes) — PEM-encoded.
    """
    raise NotImplementedError


def rsa_sign(private_pem, data: bytes) -> bytes:
    """Sign `data` with RSA-PSS + SHA-256.

    Returns:
        bytes: the signature.
    """
    raise NotImplementedError


def rsa_verify(public_pem, data: bytes, sig: bytes) -> bool:
    """Verify an RSA-PSS + SHA-256 signature. Must return False on any
    bad input — malformed key, wrong data, corrupt signature — never raise."""
    raise NotImplementedError


# ---------------------------------------------------------------------- ECDSA
def ecdsa_keypair():
    """Generate an ECDSA keypair on secp256k1 (Bitcoin's curve).

    Returns:
        (private_pem: bytes, public_pem: bytes) — PEM-encoded.
    """
    raise NotImplementedError


def ecdsa_sign(private_pem, data: bytes) -> bytes:
    """Sign `data` with ECDSA + SHA-256 on secp256k1.

    Returns:
        bytes: the DER-encoded signature.
    """
    raise NotImplementedError


def ecdsa_verify(public_pem, data: bytes, sig: bytes) -> bool:
    """Verify an ECDSA + SHA-256 signature. Must return False on any
    bad input — never raise."""
    raise NotImplementedError
