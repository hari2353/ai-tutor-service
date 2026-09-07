"""Lab 03 tests: visibility, snapshot discipline, and THE anomalies.

Each anomaly test reproduces the anomaly at the weak level and proves
prevention at the stronger level — the whole point of the lab."""
import pytest


def doctors_fixture(M):
    """Two doctors on call. The invariant: >= 1 stays on call."""
    store = M.MVCCStore()
    s_seed = M.Session(store)
    s_seed.begin()
    s_seed.write("alice:on_call", True)
    s_seed.write("bob:on_call", True)
    s_seed.commit()
    return store


def on_call_count(store, session, keys=("alice:on_call", "bob:on_call")):
    return sum(1 for k in keys if session.read(k) is True)


# ------------------------------------------------------------------ basics
def test_write_read_commit_roundtrip(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin()
    s.write("k", "v")
    assert s.read("k") == "v"          # read-your-own-writes
    s.commit()
    s2 = M.Session(store, "READ_COMMITTED")
    s2.begin()
    assert s2.read("k") == "v"


def test_version_chain_records_history(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin(); s.write("k", 1); s.commit()
    s.begin(); s.write("k", 2); s.commit()
    chain = store.chains["k"]
    assert [v.value for v in chain] == [1, 2]
    assert all(v.committed for v in chain)
    assert chain[0].end_ts is not None, "old version closed when superseded"
    assert chain[1].end_ts is None, "current version still live"


def test_commit_assigns_monotonic_commit_ts(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    ts1 = (s.begin(), s.write("a", 1), s.commit())[-1]
    s.begin(); s.write("b", 2); ts2 = s.commit()
    assert ts2 > ts1


def test_uncommitted_write_invisible_to_others_at_rc(M):
    store = M.MVCCStore()
    w = M.Session(store, "READ_COMMITTED")
    w.begin(); w.write("k", "dirty")
    r = M.Session(store, "READ_COMMITTED")
    r.begin()
    assert r.read("k") is None, "no dirty reads at READ_COMMITTED"


# ------------------------------------------------- DIRTY READ (RU vs RC)
def test_dirty_read_visible_at_read_uncommitted(M):
    store = M.MVCCStore()
    w = M.Session(store, "READ_COMMITTED")
    w.begin(); w.write("k", "uncommitted-value")
    r = M.Session(store, "READ_UNCOMMITTED")
    r.begin()
    assert r.read("k") == "uncommitted-value", "RU sees the uncommitted write"
    w.abort()
    # and the value never existed — T1 acted on data that was never real
    r2 = M.Session(store, "READ_UNCOMMITTED")
    r2.begin()
    assert r2.read("k") is None


def test_dirty_read_blocked_at_read_committed(M):
    store = M.MVCCStore()
    w = M.Session(store, "READ_COMMITTED")
    w.begin(); w.write("k", "uncommitted-value")
    r = M.Session(store, "READ_COMMITTED")
    r.begin()
    assert r.read("k") is None, "RC must not see uncommitted writes"
    w.commit()
    # RC takes a fresh snapshot per statement — NOW the read sees it
    assert r.read("k") == "uncommitted-value"


# -------------------------------------- NON-REPEATABLE READ (RC vs RR)
def test_non_repeatable_read_happens_at_rc(M):
    """THE anomaly repro: same row, same txn, two statements, two answers."""
    store = M.MVCCStore()
    s1 = M.Session(store, "READ_COMMITTED")
    s1.begin(); s1.write("balance", 500); s1.commit()

    reader = M.Session(store, "READ_COMMITTED")
    reader.begin()
    first = reader.read("balance")

    writer = M.Session(store, "READ_COMMITTED")
    writer.begin(); writer.write("balance", 400); writer.commit()

    second = reader.read("balance")
    assert first == 500 and second == 400, \
        "RC: fresh snapshot per statement → non-repeatable read"


def test_non_repeatable_read_blocked_at_rr(M):
    store = M.MVCCStore()
    s1 = M.Session(store, "READ_COMMITTED")
    s1.begin(); s1.write("balance", 500); s1.commit()

    reader = M.Session(store, "REPEATABLE_READ")
    reader.begin()
    first = reader.read("balance")

    writer = M.Session(store, "READ_COMMITTED")
    writer.begin(); writer.write("balance", 400); writer.commit()

    second = reader.read("balance")
    assert first == 500 and second == 500, \
        "RR: one snapshot for the whole txn → repeatable reads"


# ------------------------------------------- LOST UPDATE (RC vs RR/FCW)
def test_lost_update_at_read_committed(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin(); s.write("n", 100); s.commit()

    t1 = M.Session(store, "READ_COMMITTED")
    t2 = M.Session(store, "READ_COMMITTED")
    t1.begin(); t2.begin()
    v1 = t1.read("n"); v2 = t2.read("n")           # both see 100
    t1.write("n", v1 + 50)                          # 150
    t2.write("n", v2 + 30)                          # 130 — clobbers +50
    t1.commit(); t2.commit()

    after = M.Session(store, "READ_COMMITTED")
    after.begin()
    assert after.read("n") == 130, "RC: last writer wins — T1's +50 is LOST"
    assert after.read("n") != 180


def test_first_committer_wins_prevents_lost_update_at_rr(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin(); s.write("n", 100); s.commit()

    t1 = M.Session(store, "REPEATABLE_READ")
    t2 = M.Session(store, "REPEATABLE_READ")
    t1.begin(); t2.begin()
    t1.write("n", 150)
    t2.write("n", 130)
    t1.commit()                                     # first committer wins
    with pytest.raises(M.SerializationFailure):
        t2.commit()                                # second committer aborts

    after = M.Session(store, "READ_COMMITTED")
    after.begin()
    assert after.read("n") == 150, "only T1's write survived"


# -------------------------------------------- WRITE SKEW (RR vs SER)
def test_write_skew_happens_at_repeatable_read(M):
    """THE doctors-on-call example. Both check the count, both see 2>1,
    both take themselves off — final count 0 at RR. Nobody's write conflicted."""
    store = doctors_fixture(M)

    alice = M.Session(store, "REPEATABLE_READ")
    bob = M.Session(store, "REPEATABLE_READ")
    alice.begin(); bob.begin()

    a_count = on_call_count(store, alice)
    b_count = on_call_count(store, bob)
    assert a_count == 2 and b_count == 2, "precondition: both see 2 on call"

    if a_count > 1:                                 # "safe" to go off call
        alice.write("alice:on_call", False)
    if b_count > 1:
        bob.write("bob:on_call", False)

    alice.commit()
    bob.commit()                                    # both commit — no conflict!

    check = M.Session(store, "READ_COMMITTED")
    check.begin()
    assert on_call_count(store, check) == 0, \
        "WRITE SKEW at RR: disjoint writes, invariant dead, no error raised"


def test_serializable_aborts_write_skew(M):
    """Same scenario at SERIALIZABLE: one of the two must lose."""
    store = doctors_fixture(M)

    alice = M.Session(store, "SERIALIZABLE")
    bob = M.Session(store, "SERIALIZABLE")
    alice.begin(); bob.begin()

    a_count = on_call_count(store, alice)
    b_count = on_call_count(store, bob)
    assert a_count == 2 and b_count == 2

    alice.write("alice:on_call", False)
    bob.write("bob:on_call", False)

    alice.commit()                                  # first committer wins
    with pytest.raises(M.SerializationFailure):
        bob.commit()                                # read bob's row → conflict

    check = M.Session(store, "READ_COMMITTED")
    check.begin()
    assert on_call_count(store, check) == 1, \
        "SERIALIZABLE: invariant survives — exactly one doctor still on call"


# --------------------------------------------------------- snapshot rules
def test_rr_ignores_concurrent_inserts_to_new_keys(M):
    """RR also gives a stable predicate view (phantom-free reads)."""
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin(); s.write("x:1", True); s.commit()

    reader = M.Session(store, "REPEATABLE_READ")
    reader.begin()
    assert reader.read("x:1") is True

    writer = M.Session(store, "READ_COMMITTED")
    writer.begin(); writer.write("x:2", True); writer.commit()

    assert reader.read("x:2") is None, "RR snapshot predates x:2 — phantom blocked"
    fresh = M.Session(store, "READ_COMMITTED")
    fresh.begin()
    assert fresh.read("x:2") is True


def test_abort_discards_writes(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin(); s.write("k", "doomed"); s.abort()
    r = M.Session(store, "READ_COMMITTED")
    r.begin()
    assert r.read("k") is None


def test_concurrent_update_closes_old_version(M):
    store = M.MVCCStore()
    s = M.Session(store, "READ_COMMITTED")
    s.begin(); s.write("k", "v1"); s.commit()
    old = store.chains["k"][0]
    t = M.Session(store, "READ_COMMITTED")
    t.begin(); t.write("k", "v2"); t.commit()
    assert old.value == "v1" and old.end_ts is not None
    assert store.chains["k"][-1].value == "v2"
