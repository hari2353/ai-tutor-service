"""Lab 22 — reference implementation: hashes, Merkle trees, signatures."""
import hashlib
import hmac

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec, padding, rsa


# --------------------------------------------------------------------- hashes
def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.digest()


def sha256_str(s):
    if isinstance(s, str):
        s = s.encode("utf-8")
    return hashlib.sha256(s).digest()


def hmac_sha256(key: bytes, msg: bytes) -> bytes:
    return hmac.new(key, msg, hashlib.sha256).digest()


# ----------------------------------------------------------------- merkle tree
class MerkleTree:
    """Binary Merkle tree over hashed leaves (Bitcoin's duplication rule)."""

    def __init__(self, leaves: list):
        self._leaves = [bytes(l) if not isinstance(l, str) else l.encode("utf-8")
                        for l in leaves]
        self._n_leaves = len(self._leaves)
        self._levels = []        # level 0 = leaf hashes, last = [root]
        self._build()

    def _build(self):
        if not self._leaves:
            self._levels = []
            return
        level = [sha256_str(l) for l in self._leaves]
        self._levels = [level]
        while len(level) > 1:
            if len(level) % 2 == 1:
                level = level + [level[-1]]        # Bitcoin rule: duplicate last
            nxt = []
            for i in range(0, len(level), 2):
                nxt.append(sha256_str(level[i] + level[i + 1]))
            self._levels.append(nxt)
            level = nxt

    @property
    def root(self):
        if not self._levels:
            return None
        return self._levels[-1][0]

    @property
    def n_leaves(self):
        return self._n_leaves

    def proof(self, index: int) -> list:
        if not 0 <= index < self._n_leaves:
            raise IndexError("leaf index out of range")
        out = []
        idx = index
        for level in self._levels[:-1]:
            if idx % 2 == 0:
                # even position: sibling (or our own duplicate) sits right
                sib = level[idx + 1] if idx + 1 < len(level) else level[idx]
                is_left = False
            else:
                # odd position: sibling sits left
                sib = level[idx - 1]
                is_left = True
            out.append((sib, is_left))
            idx //= 2
        return out

    @staticmethod
    def verify(root, leaf, index: int, proof: list, n_leaves: int) -> bool:
        try:
            if n_leaves < 1 or not 0 <= index < n_leaves:
                return False
            # depth of an n-leaf tree under the duplication rule: ceil(log2(n))
            if len(proof) != (n_leaves - 1).bit_length():
                return False
            cur = bytes(leaf) if not isinstance(leaf, str) else leaf.encode("utf-8")
            cur = sha256_str(cur)
            for lvl, (sibling, is_left) in enumerate(proof):
                # direction must be consistent with the claimed position:
                # bit `lvl` of the index says which side WE sit on
                if bool(is_left) != bool((index >> lvl) & 1):
                    return False
                sib = bytes(sibling)
                cur = sha256_str(sib + cur) if is_left else sha256_str(cur + sib)
            return cur == root
        except Exception:
            return False


# ------------------------------------------------------------------ RSA (PSS)
_PSS = padding.PSS(mgf=padding.MGF1(hashes.SHA256()),
                   salt_length=padding.PSS.DIGEST_LENGTH)


def rsa_keypair():
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    priv = key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


def rsa_sign(private_pem, data: bytes) -> bytes:
    key = serialization.load_pem_private_key(bytes(private_pem), password=None)
    return key.sign(bytes(data), _PSS, hashes.SHA256())


def rsa_verify(public_pem, data: bytes, sig: bytes) -> bool:
    try:
        key = serialization.load_pem_public_key(bytes(public_pem))
        key.verify(bytes(sig), bytes(data), _PSS, hashes.SHA256())
        return True
    except Exception:
        return False


# ---------------------------------------------------------------------- ECDSA
def ecdsa_keypair():
    key = ec.generate_private_key(ec.SECP256K1())
    priv = key.private_bytes(serialization.Encoding.PEM,
                             serialization.PrivateFormat.PKCS8,
                             serialization.NoEncryption())
    pub = key.public_key().public_bytes(serialization.Encoding.PEM,
                                        serialization.PublicFormat.SubjectPublicKeyInfo)
    return priv, pub


def ecdsa_sign(private_pem, data: bytes) -> bytes:
    key = serialization.load_pem_private_key(bytes(private_pem), password=None)
    return key.sign(bytes(data), ec.ECDSA(hashes.SHA256()))


def ecdsa_verify(public_pem, data: bytes, sig: bytes) -> bool:
    try:
        key = serialization.load_pem_public_key(bytes(public_pem))
        key.verify(bytes(sig), bytes(data), ec.ECDSA(hashes.SHA256()))
        return True
    except Exception:
        return False
