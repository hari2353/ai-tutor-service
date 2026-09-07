"""Lab 11 tests. No sleeps, no network — scrypt params stay low (n=2**14)."""
import pytest


# ------------------------------------------------------------------ password hashing
def test_password_roundtrip_true(R):
    stored = R.hash_password("correct horse battery staple")
    assert R.verify_password("correct horse battery staple", stored) is True


def test_password_wrong_password_false(R):
    stored = R.hash_password("correct horse battery staple")
    assert R.verify_password("Tr0ub4dor&3", stored) is False


def test_password_unique_salts(R):
    """Same password, hashed twice -> different records. A shared salt would
    mean cracking one user cracks every user with the same password."""
    a = R.hash_password("hunter2")
    b = R.hash_password("hunter2")
    assert a["salt_hex"] != b["salt_hex"]
    assert a["hash_hex"] != b["hash_hex"]


def test_verify_tolerates_missing_keys(R):
    """A malformed / legacy stored record is a failed verification,
    never a crash (KeyError escaping verify is a 500 in production)."""
    stored = R.hash_password("pw")
    for broken in (
        {},
        {"algo": "scrypt"},
        {"algo": "scrypt", "salt_hex": "ab"},
        {"algo": "md5", "salt_hex": "ab", "hash_hex": "cd", "n": 1, "r": 1, "p": 1},
        {"algo": "scrypt", "salt_hex": "!!not-hex!!", "hash_hex": "cd", "n": 1, "r": 1, "p": 1},
    ):
        assert R.verify_password("pw", broken) is False


def test_verify_param_mismatch_returns_false(R):
    """The record stores its own params. Verify against a record whose
    params do not match must return False, not raise."""
    stored = R.hash_password("pw")
    tampered = dict(stored, n=2 ** 15)   # a 'params were upgraded' record
    assert R.verify_password("pw", tampered) is False


# ------------------------------------------------------------------------ AES-GCM
def test_aes_roundtrip(R, key):
    pt = b"attack at dawn"
    nonce, ct = R.encrypt(key, pt)
    assert R.decrypt(key, nonce, ct) == pt


def test_aes_fresh_nonce_every_time(R, key):
    """THE rule. Two encryptions of the SAME plaintext under the SAME key
    must never share a nonce — and the ciphertexts must differ too."""
    pt = b"attack at dawn"
    nonce1, ct1 = R.encrypt(key, pt)
    nonce2, ct2 = R.encrypt(key, pt)
    assert nonce1 != nonce2
    assert ct1 != ct2


def test_aes_tampered_ciphertext_rejected(R, key):
    nonce, ct = R.encrypt(key, b"attack at dawn")
    bad = bytes([ct[0] ^ 1]) + ct[1:]        # flip one bit of ciphertext
    with pytest.raises(R.DecryptionError):
        R.decrypt(key, nonce, bad)


def test_aes_wrong_key_rejected(R, key):
    nonce, ct = R.encrypt(key, b"attack at dawn")
    with pytest.raises(R.DecryptionError):
        R.decrypt(R.new_key(), nonce, ct)


def test_aes_aad_roundtrip_and_mismatch(R, key):
    nonce, ct = R.encrypt(key, b"payload", aad=b"context:row-42")
    assert R.decrypt(key, nonce, ct, aad=b"context:row-42") == b"payload"
    # decrypting with a DIFFERENT context fails — AAD binds the ciphertext
    # to where it belongs (e.g. a row id: a ct copied from user A to user B
    # will not decrypt)
    with pytest.raises(R.DecryptionError):
        R.decrypt(key, nonce, ct, aad=b"context:row-43")


# ------------------------------------------------------------------- key rotation
def test_rotation_new_key_decrypts_old_fails(R, key):
    plaintexts = [b"item-0", b"item-1", b"item-2"]
    cts = [R.encrypt(key, pt) for pt in plaintexts]
    new_key, rotated = R.rotate(key, cts)

    assert new_key != key
    assert len(rotated) == len(cts)
    for pt, (nonce, ct), (n2, c2) in zip(plaintexts, rotated, cts):
        assert nonce != n2                            # fresh nonces too
        assert ct != c2
        assert R.decrypt(new_key, nonce, ct) == pt    # readable under the new key
    for nonce, ct in rotated:
        with pytest.raises(R.DecryptionError):
            R.decrypt(key, nonce, ct)                 # old key must be dead


def test_rotation_fail_closed_one_bad_item(R, key):
    """One undecryptable item aborts the WHOLE rotation. A partial rotation
    the caller believes succeeded is worse than no rotation at all."""
    good = [R.encrypt(key, b"ok-1"), R.encrypt(key, b"ok-2")]
    nonce_other, ct_other = R.encrypt(R.new_key(), b"encrypted under some other key")
    with pytest.raises(R.DecryptionError):
        R.rotate(key, good + [(nonce_other, ct_other)])


# ------------------------------------------------------------------- file helpers
def test_file_roundtrip_via_tmp_path(R, key, tmp_path):
    blob = b"larger blob of user data " * 100
    nonce, ct = R.encrypt_file(key, blob)
    f = tmp_path / "secret.bin"
    f.write_bytes(nonce + ct)                       # the persistence layer
    on_disk = f.read_bytes()
    restored = R.decrypt_file(key, on_disk[:12], on_disk[12:])
    assert restored == blob

    # a bit flip on disk must be rejected, never silently decrypt to garbage
    f.write_bytes(nonce + bytes([ct[0] ^ 0xFF]) + ct[1:])
    on_disk = f.read_bytes()
    with pytest.raises(R.DecryptionError):
        R.decrypt_file(key, on_disk[:12], on_disk[12:])


# ------------------------------------------------------------------------- digest
def test_digest_tamper_detected(R):
    """Integrity check: any change to the contents changes the digest,
    and identical contents always produce the identical digest."""
    original = b"the report, as authored"
    tampered = b"the report, as authored "
    assert R.digest(original) == R.digest(b"the report, as authored")
    assert R.digest(original) != R.digest(tampered)
