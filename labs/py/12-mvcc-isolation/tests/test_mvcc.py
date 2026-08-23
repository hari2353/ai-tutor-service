"""Lab 12 tests — every anomaly from T17-mvcc-isolation, reproduced and
prevented by name. Deterministic: the driver executes explicit interleavings,
no threads, no sleeps, no wall clock.

Each anomaly test asserts BOTH the isolation level where the anomaly appears
AND the level(s) where it is prevented.
"""
import pytest


# ------------------------------------------------------------------ helpers
def run(R, steps, levels=None, seed=None):
    store, res = R.simulate(steps, levels, seed)
    return store, res


DOCTORS = [
    ("t1", "r", "alice"), ("t1", "r", "bob"),
    ("t2", "r", "alice"), ("t2", "r", "bob"),
    ("t1", "w", "alice", False),          # Alice goes off call
    ("t2", "w", "bob", False),            # Bob goes off call
    ("t1", "commit"), ("t2", "commit"),
]


# ------------------------------------------------------------------ mechanics
def test_version_chain_windows_are_half_open(R):
    """xmin/xmax-style chains: commit stamps begin, supersession closes end,
    and a reader pinned between two commits sees exactly the old version."""
    s = R.MVCCStore()
    w1 = s.begin(R.READ_COMMITTED, name="w1")
    s.write(w1, "k", 1)
    c1 = s.commit(w1)
    reader = s.begin(R.REPEATABLE_READ, name="reader")   # pinned BETWEEN commits
    w2 = s.begin(R.READ_COMMITTED, name="w2")
    s.write(w2, "k", 2)
    c2 = s.commit(w2)

    chain = s.data["k"]
    assert len(chain) == 2
    assert chain[0].commit_ts == c1 and chain[1].commit_ts == c2
    assert chain[0].end_ts == c2                          # superseded at w2's commit
    assert chain[1].end_ts is None                        # still live
    assert chain[0].begin_ts < c1                         # write-start precedes commit
    assert chain[0].commit_ts <= reader.snapshot_ts < chain[1].commit_ts
    assert s.read(reader, "k") == 1                       # snapshot sees only v1
    probe = s.begin(R.READ_COMMITTED, name="probe")
    assert s.read(probe, "k") == 2                        # fresh snapshot sees v2


def test_snapshot_policy_per_level(R):
    """RU/RC take a fresh snapshot per statement; RR/SER pin one at begin.
    This single policy IS the isolation ladder."""
    s = R.MVCCStore()
    R.seed_store(s, {"k": "v"})
    for level in (R.READ_UNCOMMITTED, R.READ_COMMITTED):
        tx = s.begin(level, name=level)
        before = tx.snapshot_ts
        s.read(tx, "k")
        assert tx.snapshot_ts > before, f"{level} must refresh per statement"
    for level in (R.REPEATABLE_READ, R.SERIALIZABLE):
        tx = s.begin(level, name=level)
        before = tx.snapshot_ts
        s.read(tx, "k")
        assert tx.snapshot_ts == before, f"{level} must pin one snapshot"


def test_read_uncommitted_tracks_write_start_not_commit(R):
    """RU visibility begins at WRITE-START (that's what makes dirty reads
    possible); RC must not see any of it until the commit lands."""
    steps = [
        ("t2", "w", "n", 1),
        ("ru", "r", "n"),
        ("t2", "w", "n", 2),
        ("ru", "r", "n"),
        ("rc", "r", "n"),
        ("t2", "commit"),
        ("rc", "r", "n"),
    ]
    _, res = run(R, steps, {"t2": R.READ_COMMITTED, "ru": R.READ_UNCOMMITTED,
                            "rc": R.READ_COMMITTED})
    assert res.reads("ru", "n") == [1, 2], "RU watches writes as they happen"
    assert res.reads("rc", "n") == [None, 2], "RC waits for the commit"


def test_keys_between_range_helper(R):
    """Predicate reads respect bounds AND isolation (uncommitted insert is
    invisible to RC, visible to RU)."""
    s = R.MVCCStore()
    R.seed_store(s, {"b": 1, "d": 1})
    writer = s.begin(R.READ_COMMITTED, name="writer")
    s.write(writer, "c", 1)                                # uncommitted
    rc = s.begin(R.READ_COMMITTED, name="rc")
    ru = s.begin(R.READ_UNCOMMITTED, name="ru")
    assert s.keys_between(rc, "a", "e") == ["b", "d"]
    assert s.keys_between(ru, "a", "e") == ["b", "c", "d"]  # sees the phantom row
    assert s.keys_between(rc, "b", "c") == ["b"]            # 'c' invisible, bounds hold


# ------------------------------------------------------------------ dirty read
def test_dirty_read_visible_at_ru_blocked_at_rc_rr_ser(R):
    """T2 writes an uncommitted value; T1 reads it. RU acts on a value that
    never existed; every level above RU refuses to see it."""
    steps = [
        ("t2", "w", "bal", 350),      # uncommitted debit
        ("t1", "r", "bal"),
        ("t2", "rollback"),           # the value never existed
        ("t1", "r", "bal"),
    ]
    # appears: READ UNCOMMITTED — including after the rollback erased it
    _, res = run(R, steps, {"t1": R.READ_UNCOMMITTED, "t2": R.READ_COMMITTED})
    assert res.reads("t1", "bal") == [350, None]
    # prevented: RC / RR / SER see only committed data at every statement
    for level in (R.READ_COMMITTED, R.REPEATABLE_READ, R.SERIALIZABLE):
        _, res = run(R, steps, {"t1": level, "t2": R.READ_COMMITTED})
        assert res.reads("t1", "bal") == [None, None], \
            f"dirty read must be blocked at {level}"


# ------------------------------------------------------------------ non-repeatable read
def test_non_repeatable_read_occurs_at_rc_prevented_at_rr_and_ser(R):
    """Same transaction reads 'bal' twice; T2 commits 400 in between. RC's
    per-statement snapshots answer 500 then 400 (read skew). RR/SER answer
    500 twice — one snapshot, one truth."""
    seed = {"bal": 500}
    steps = [
        ("t1", "r", "bal"),
        ("t2", "w", "bal", 400),
        ("t2", "commit"),
        ("t1", "r", "bal"),
    ]
    # appears: RC (and even RU, which also re-snapshots per statement)
    _, res = run(R, steps, {"t1": R.READ_COMMITTED, "t2": R.READ_COMMITTED}, seed)
    assert res.reads("t1", "bal") == [500, 400]
    _, res = run(R, steps, {"t1": R.READ_UNCOMMITTED, "t2": R.READ_COMMITTED}, seed)
    assert res.reads("t1", "bal") == [500, 400]
    # prevented: RR / SER — fixed transaction-wide snapshot
    for level in (R.REPEATABLE_READ, R.SERIALIZABLE):
        _, res = run(R, steps, {"t1": level, "t2": R.READ_COMMITTED}, seed)
        assert res.reads("t1", "bal") == [500, 500], f"must be stable at {level}"


# ------------------------------------------------------------------ phantom read
def test_phantom_occurs_at_rc_prevented_by_snapshot_at_rr_and_ser(R):
    """T1 counts pending orders twice; T2 inserts one in between. The predicate
    result set changes under RC. A pinned snapshot freezes the set."""
    seed = {"ord:1": "pending"}
    steps = [
        ("t1", "range", "ord:", "ord:~"),
        ("t2", "w", "ord:2", "pending"),
        ("t2", "commit"),
        ("t1", "range", "ord:", "ord:~"),
    ]
    # appears: RC (and RU) — the count grows mid-transaction
    _, res = run(R, steps, {"t1": R.READ_COMMITTED, "t2": R.READ_COMMITTED}, seed)
    assert res.ranges("t1") == [("ord:1",), ("ord:1", "ord:2")]
    _, res = run(R, steps, {"t1": R.READ_UNCOMMITTED, "t2": R.READ_COMMITTED}, seed)
    assert res.ranges("t1")[1] == ("ord:1", "ord:2")
    # prevented: RR / SER — same answer twice, new commit or not
    for level in (R.REPEATABLE_READ, R.SERIALIZABLE):
        _, res = run(R, steps, {"t1": level, "t2": R.READ_COMMITTED}, seed)
        assert res.ranges("t1") == [("ord:1",), ("ord:1",)], f"phantom at {level}"


# ------------------------------------------------------------------ lost update
def test_lost_update_at_ru_rc_prevented_by_first_committer_wins_at_si(R):
    """Two RMW on the same balance: both read 500, t1 writes 600, t2 writes 550.
    At RU/RC both commit and t1's +100 silently vanishes (final 550). At
    RR/SI the second committer hits the ww-conflict abort (final 600)."""
    seed = {"bal": 500}
    steps = [
        ("t1", "r", "bal"),
        ("t2", "r", "bal"),
        ("t1", "w", "bal", 600),       # 500 + 100
        ("t2", "w", "bal", 550),       # 500 + 50
        ("t1", "commit"),
        ("t2", "commit"),
    ]
    # appears: RU and RC — last writer wins, one deposit evaporates
    for level in (R.READ_UNCOMMITTED, R.READ_COMMITTED):
        _, res = run(R, steps, {"t1": level, "t2": level}, seed)
        assert res.committed == {"t1", "t2"}, f"no conflict detected at {level}"
        assert res.final_value("bal") == 550, f"update lost at {level}"
    # prevented: REPEATABLE READ (= SI) via first-committer-wins
    _, res = run(R, steps, {"t1": R.REPEATABLE_READ, "t2": R.REPEATABLE_READ}, seed)
    assert res.aborted.get("t2") == "ww-conflict"
    assert res.committed == {"t1"}
    assert res.final_value("bal") == 600
    # prevented: SERIALIZABLE too (SSI subsumes SI)
    _, res = run(R, steps, {"t1": R.SERIALIZABLE, "t2": R.SERIALIZABLE}, seed)
    assert "t2" in res.aborted
    assert res.committed == {"t1"}
    assert res.final_value("bal") == 600


def test_first_committer_wins_aborts_second_committer_at_commit(R):
    """Direct store-level view of FCW: both may BUFFER a write to k while
    concurrent; the first commit lands, the second raises ww-conflict. A later
    transaction that began AFTER the winner committed never conflicts."""
    s = R.MVCCStore()
    R.seed_store(s, {"k": 0})
    a = s.begin(R.REPEATABLE_READ, name="a")
    b = s.begin(R.REPEATABLE_READ, name="b")
    s.read(a, "k")
    s.read(b, "k")
    s.write(a, "k", 1)
    s.write(b, "k", 2)
    s.commit(a)
    with pytest.raises(R.SerializationFailure) as ei:
        s.commit(b)
    assert ei.value.reason == "ww-conflict"

    late = s.begin(R.REPEATABLE_READ, name="late")     # built ON TOP of a's commit
    s.write(late, "k", 3)
    s.commit(late)                                     # no conflict: snapshot is fresh


def test_first_committer_wins_requires_key_overlap(R):
    """FCW fires on OVERLAPPING keys only. Disjoint writes at RR both land."""
    steps = [
        ("t1", "w", "a", 1),
        ("t2", "w", "b", 2),
        ("t1", "commit"),
        ("t2", "commit"),
    ]
    _, res = run(R, steps, {"t1": R.REPEATABLE_READ, "t2": R.REPEATABLE_READ})
    assert res.committed == {"t1", "t2"}
    assert res.final_state() == {"a": 1, "b": 2}


# ------------------------------------------------------------------ write skew
def test_write_skew_allowed_under_plain_snapshot_isolation(R):
    """Doctors on call, invariant x != y (at least one on call). Both RR
    transactions read a consistent snapshot, neither write touches the other's
    key, BOTH COMMIT — final state violates the invariant. SI detects nothing:
    there is no row written by both."""
    for level in (R.READ_UNCOMMITTED, R.READ_COMMITTED, R.REPEATABLE_READ):
        _, res = run(R, DOCTORS, {"t1": level, "t2": level},
                     seed={"alice": True, "bob": True})
        assert res.committed == {"t1", "t2"}, f"skew must slip through at {level}"
        assert res.final_state() == {"alice": False, "bob": False}
        assert not (res.final_state()["alice"] or res.final_state()["bob"]), \
            "zero doctors on call — the invariant died quietly"


def test_write_skew_aborted_under_serializable_ssi_lite(R):
    """Same script at SERIALIZABLE: each tx SIREADs the key the other writes,
    the rw-antidependency edges close a cycle, and exactly ONE doctor loses.
    Invariant survives."""
    store, res = run(R, DOCTORS,
                     {"t1": R.SERIALIZABLE, "t2": R.SERIALIZABLE},
                     seed={"alice": True, "bob": True})
    aborted = res.aborted
    assert sum(name in aborted for name in ("t1", "t2")) == 1, \
        "exactly one side of the cycle aborts"
    loser = next(name for name in ("t1", "t2") if name in aborted)
    assert aborted[loser] == "ssi-cycle"
    survivor = "t2" if loser == "t1" else "t1"
    assert res.committed == {survivor}
    final = res.final_state()
    assert final["alice"] != final["bob"], "invariant restored by the abort"
    # the aborted tx's commit step was skipped, never executed
    assert ("skip", loser, "commit") in [e[:3] for e in res.log]
    # the dangerous structure was real bookkeeping, not locking
    assert store.lock_count() == 0


def test_ssi_single_rw_antidependency_is_not_dangerous(R):
    """One rw edge is fine — the danger is a CYCLE. t1 reads k; t2 writes a
    disjoint key; no edges form, both commit. SIREAD bookkeeping must not
    abort unrelated serializable traffic."""
    steps = [
        ("t1", "r", "k"),
        ("t2", "w", "j", "new"),
        ("t2", "commit"),
        ("t1", "commit"),
    ]
    store, res = run(R, steps,
                     {"t1": R.SERIALIZABLE, "t2": R.SERIALIZABLE},
                     seed={"k": "v"})
    assert res.committed == {"t1", "t2"}
    assert res.aborted == {}
    assert store.rw_edges == set()


# ------------------------------------------------------------------ MVCC basics
def test_read_your_writes_inside_transaction_at_every_level(R):
    """A transaction always reads its own uncommitted writes — at every level.
    Nobody else can (that's the dirty-read test)."""
    steps = [
        ("t1", "r", "k"),
        ("t1", "w", "k", 99),
        ("t1", "r", "k"),
        ("t1", "commit"),
    ]
    for level in R.LEVELS:
        _, res = run(R, steps, {"t1": level})
        assert res.reads("t1", "k") == [None, 99], f"read-your-writes at {level}"
        assert res.committed == {"t1"}


def test_uncommitted_reader_blocks_nothing_no_locks(R):
    """THE MVCC pitch: t1 holds an open RR snapshot while t2 writes and commits
    underneath it. No lock is taken, nothing blocks, and t1 keeps seeing its
    snapshot — its own later commit doesn't even conflict (it wrote nothing)."""
    steps = [
        ("t1", "r", "k"),             # t1 now holds a long-lived snapshot
        ("t2", "w", "k", "v1"),       # writer proceeds instantly — no block
        ("t2", "commit"),             # ...and finishes while t1 is still open
        ("t1", "r", "k"),             # t1 unaffected
        ("t1", "commit"),
    ]
    store, res = run(R, steps, {"t1": R.REPEATABLE_READ, "t2": R.READ_COMMITTED},
                     seed={"k": "v0"})
    assert res.last_read("t1", "k") == "v0", "reader's snapshot is untouched"
    assert res.committed == {"t1", "t2"}
    assert store.lock_count() == 0 and store.locks == {}, "MVCC takes no locks"


def test_commit_visibility_is_atomic_and_ordered(R):
    """Nothing of t1's work is visible until its commit; between commits a
    probe sees exactly v1; an RR probe pinned before t2's commit NEVER sees
    v2; commit order decides the winner."""
    steps = [
        ("t1", "w", "k", "v1"),
        ("t2", "w", "k", "v2"),
        ("t1", "commit"),
        ("p1", "r", "k"),             # between the two commits
        ("p0", "r", "k"),             # RR probe, pins its snapshot here
        ("t2", "commit"),
        ("p0", "r", "k"),
        ("p2", "r", "k"),             # after everything
    ]
    levels = {"t1": R.READ_COMMITTED, "t2": R.READ_COMMITTED,
              "p0": R.REPEATABLE_READ, "p1": R.READ_COMMITTED,
              "p2": R.READ_COMMITTED}
    store, res = run(R, steps, levels, seed={"k": "seed"})
    assert res.last_read("p1", "k") == "v1", "t1 visible atomically at its commit"
    assert res.reads("p0", "k") == ["v1", "v1"], "RR probe never sees v2"
    assert res.last_read("p2", "k") == "v2", "later commit wins"
    chain = store.data["k"]
    assert chain[-2].end_ts == chain[-1].commit_ts, "superseded at commit time"


def test_multi_key_commit_never_shows_partial_state(R):
    """A two-key write becomes visible all-or-nothing: probes before the commit
    see neither value, probes after see both."""
    steps = [
        ("t1", "w", "a", 1),
        ("t1", "w", "b", 2),
        ("p", "r", "a"), ("p", "r", "b"),
        ("t1", "commit"),
        ("p", "r", "a"), ("p", "r", "b"),
    ]
    _, res = run(R, steps, {"t1": R.READ_COMMITTED, "p": R.READ_COMMITTED})
    assert res.reads("p", "a") == [None, 1]
    assert res.reads("p", "b") == [None, 2]


# ------------------------------------------------------------------ abort/rollback
def test_rollback_hides_versions_end_ts_never_set(R):
    """A rolled-back write stays in the chain as unreclaimed garbage — but its
    window never opens: commit_ts is never stamped, end_ts never set, and no
    reader at ANY level ever sees it again."""
    steps = [
        ("t1", "w", "k", "bad"),
        ("t1", "rollback"),
        ("prc", "r", "k"),
        ("pru", "r", "k"),            # even the dirty reader loses it post-abort
        ("prr", "r", "k"),
    ]
    store, res = run(R, steps, {"t1": R.REPEATABLE_READ, "prc": R.READ_COMMITTED,
                                "pru": R.READ_UNCOMMITTED,
                                "prr": R.REPEATABLE_READ}, seed={"k": "safe"})
    assert res.aborted == {"t1": "rolled-back"}
    assert res.last_read("prc", "k") == "safe"
    assert res.last_read("pru", "k") == "safe"
    assert res.last_read("prr", "k") == "safe"
    bad = [v for v in store.data["k"] if v.value == "bad"]
    assert len(bad) == 1
    assert bad[0].commit_ts is None, "aborted version was never committed"
    assert bad[0].end_ts is None, "end_ts never set — discarded, vacuum's job"


def test_aborted_tx_leaves_no_trace_to_later_snapshots(R):
    """t2 loses the first-committer-wins race mid-script. Its buffered value
    never becomes visible to anyone — not to fresh probes, not even to RU —
    and the winner's history stands untouched."""
    steps = [
        ("t1", "r", "bal"),
        ("t2", "r", "bal"),
        ("t1", "w", "bal", "t1-val"),
        ("t2", "w", "bal", "t2-val"),
        ("t1", "commit"),
        ("t2", "commit"),             # -> ww-conflict, aborts right here
        ("prc", "r", "bal"),
        ("pru", "r", "bal"),
    ]
    store, res = run(R, steps, {"t1": R.REPEATABLE_READ, "t2": R.REPEATABLE_READ,
                                "prc": R.READ_COMMITTED, "pru": R.READ_UNCOMMITTED},
                     seed={"bal": "base"})
    assert res.aborted == {"t2": "ww-conflict"}
    assert res.committed == {"t1"}
    assert res.last_read("prc", "bal") == "t1-val"
    assert res.last_read("pru", "bal") == "t1-val", "even RU sees no trace"
    loser = [v for v in store.data["bal"] if v.value == "t2-val"]
    assert loser and loser[0].commit_ts is None
    winner = [v for v in store.data["bal"] if v.value == "t1-val"][0]
    assert winner.end_ts is None, "nobody superseded the winner"
    assert res.final_state() == {"bal": "t1-val"}


# ------------------------------------------------------------------ driver sanity
def test_driver_logs_skips_after_finish_and_records_reads(R):
    """The interleaving driver never executes steps of a finished transaction;
    reads are recorded in order for assertions."""
    steps = [
        ("t1", "r", "k"),
        ("t1", "commit"),
        ("t1", "w", "k", "zombie"),   # must be SKIPPED, not executed
        ("t1", "r", "k"),             # skipped too
        ("t2", "r", "k"),
    ]
    _, res = run(R, steps, {"t1": R.READ_COMMITTED, "t2": R.READ_COMMITTED},
                 seed={"k": "v"})
    skips = [e for e in res.log if e[0] == "skip"]
    assert skips == [("skip", "t1", "w", "committed"), ("skip", "t1", "r", "committed")]
    assert res.reads("t1", "k") == ["v"]
    assert res.reads("t2", "k") == ["v"]
    assert res.final_value("k") == "v", "the zombie write never landed"
