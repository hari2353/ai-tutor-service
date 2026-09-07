"""Lab 02 tests: WAL appends, WAL rule, crash, ARIES recovery, idempotency.

Real-file I/O only under pytest's tmp_path; no sleeps, no network."""
import json
import os

import pytest


# ---------------------------------------------------------------- WAL basics
def test_append_assigns_increasing_lsns(tmp_path, R):
    wal = R.WAL(str(tmp_path / "wal.log"))
    assert wal.append(1, "BEGIN") == 1
    assert wal.append(1, "UPDATE", page="p1", before=None, after=5) == 2
    assert wal.append(1, "COMMIT") == 3
    assert wal.next_lsn == 4


def test_append_actually_fsyncs_a_file(tmp_path, R):
    wal = R.WAL(str(tmp_path / "wal.log"))
    wal.append(1, "BEGIN")
    wal.append(2, "BEGIN")
    recs = wal.read_all()
    assert len(recs) == 2
    assert recs[0]["type"] == "BEGIN" and recs[0]["txn"] == 1
    assert recs[1]["txn"] == 2
    # and the file is real, parseable JSON lines
    with open(str(tmp_path / "wal.log")) as f:
        assert len(json.loads(f.readline())) >= 3   # lsn, txn, type


def test_read_all_returns_lsn_order(tmp_path, R):
    wal = R.WAL(str(tmp_path / "wal.log"))
    for i in range(5):
        wal.append(1, "UPDATE", page=f"p{i}", before=i, after=i + 1)
    recs = wal.read_all()
    assert [r["lsn"] for r in recs] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------- WAL rule
def test_wal_rule_page_flush_blocked_before_log_flush(tmp_path, R):
    """A page whose newest change (page_lsn) is not yet in the fsynced log
    must be reported as a violation BEFORE flushing it."""
    bm = R.BufferManager()
    bm.write("p1", value="new", lsn=42)
    bm.set_flushed_lsn(41)                 # log NOT yet durable for lsn 42
    assert bm.wal_violation("p1") is True


def test_wal_rule_satisfied_after_log_flush(tmp_path, R):
    bm = R.BufferManager()
    bm.write("p1", value="new", lsn=42)
    bm.set_flushed_lsn(42)                 # log IS durable for lsn 42
    assert bm.wal_violation("p1") is False
    bm.flush_page("p1")                   # must not raise
    assert bm.disk["p1"]["value"] == "new"


def test_flush_page_refuses_to_break_the_rule(tmp_path, R):
    bm = R.BufferManager()
    bm.write("p1", value="new", lsn=42)
    bm.set_flushed_lsn(41)
    with pytest.raises(RuntimeError):
        bm.flush_page("p1")
    assert "p1" not in bm.disk, "page must NOT reach disk ahead of its log record"


# ----------------------------------------------------------- txn API basics
def test_update_appends_then_buffers(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "acct", 100)
    assert db.read("acct") == 100
    recs = db.wal.read_all()
    upd = [r for r in recs if r["type"] == "UPDATE"][0]
    assert upd["before"] is None and upd["after"] == 100
    assert upd["page"] == "acct"
    assert db.buffers.pages["acct"]["page_lsn"] == upd["lsn"]


def test_update_captures_before_image(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "acct", 100)
    db.update(t, "acct", 50)
    recs = db.wal.read_all()
    ups = [r for r in recs if r["type"] == "UPDATE"]
    assert ups[1]["before"] == 100 and ups[1]["after"] == 50


def test_lsns_advance_across_records(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t1 = db.begin()
    t2 = db.begin()
    db.update(t1, "a", 1)
    db.update(t2, "b", 2)
    db.commit(t1)
    recs = db.wal.read_all()
    assert [r["lsn"] for r in recs] == [1, 2, 3, 4, 5]


# ---------------------------------------------------------------- crash sim
def test_crash_discards_dirty_buffers_keeps_disk(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "p", "dirty-value")
    db.buffers.flush_page("p")            # p reaches disk
    db.update(t, "q", "only-in-buffer")    # q never flushed
    disk = db.crash()
    assert "p" in disk and disk["p"]["value"] == "dirty-value"
    assert "q" not in disk, "crash must lose unflushed buffers"
    assert db.buffers.pages == {}


# ------------------------------------------------------------- ARIES: redo
def test_committed_txn_survives_crash_and_recovery(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "acct", 500)
    db.commit(t)                            # ack only after COMMIT is fsynced
    disk = db.crash()                       # buffers die; log + disk survive
    state = R.recover(db.wal, disk)
    assert state["acct"]["value"] == 500, "committed work must never be lost"


def test_redo_replays_page_that_never_flushed(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "hot", "v2")
    db.commit(t)
    # page never flushed — crash loses the buffer
    disk = db.crash()
    assert "hot" not in disk
    state = R.recover(db.wal, disk)
    assert state["hot"]["value"] == "v2"


def test_redo_replays_newest_of_multiple_updates(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "x", 1)
    db.update(t, "x", 2)
    db.update(t, "x", 3)
    db.commit(t)
    disk = db.crash()
    state = R.recover(db.wal, disk)
    assert state["x"]["value"] == 3


# ------------------------------------------------------------- ARIES: undo
def test_uncommitted_txn_rolled_back_by_recovery(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "acct", -999)              # never committed
    disk = db.crash()                       # "acct" never hit disk anyway
    state = R.recover(db.wal, disk)
    assert "acct" not in state or state["acct"]["value"] is None, \
        "loser's partial writes must be rolled back/absent"


def test_uncommitted_txn_over_disk_page_restores_before_image(tmp_path, R):
    """The interesting undo case: the loser's change DID reach disk
    (page flushed after commit of an older value, then overwritten by a
    loser that also got flushed) — undo must restore the before-image."""
    db = R.Database(str(tmp_path / "wal.log"))
    t1 = db.begin()
    db.update(t1, "acct", 100)              # committed value on disk
    db.commit(t1)
    db.buffers.flush_page("acct")
    t2 = db.begin()
    db.update(t2, "acct", -999)            # loser writes...
    db.buffers.set_flushed_lsn(db.buffers.pages["acct"]["page_lsn"])
    db.buffers.flush_page("acct")          # ...and the page reaches disk
    disk = db.crash()
    assert disk["acct"]["value"] == -999   # precondition: disk has the bad value
    state = R.recover(db.wal, disk)
    assert state["acct"]["value"] == 100, "undo must restore the before-image"


def test_aborted_txn_not_treated_as_loser(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t1 = db.begin()
    db.update(t1, "a", 1)
    db.commit(t1)                           # t1 committed — value must survive
    t2 = db.begin()
    db.update(t2, "b", 2)
    db.abort(t2)                            # explicit abort: finished, not loser
    disk = db.crash()
    state = R.recover(db.wal, disk)
    assert state["a"]["value"] == 1, "committed value must survive"
    assert "b" not in state or state["b"]["value"] is None, \
        "aborted txn's writes must be rolled back"


def test_undo_writes_clr_records(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    lsn = db.update(t, "p", "oops")
    disk = db.crash()
    R.recover(db.wal, disk)
    recs = db.wal.read_all()
    clrs = [r for r in recs if r["type"] == "CLR"]
    assert len(clrs) >= 1, "undo must be logged via compensation records"
    assert clrs[0]["page"] == "p"
    assert clrs[0]["before"] == "oops" and clrs[0]["after"] is None


# --------------------------------------------------------- recovery is idempotent
def test_recovery_idempotent_same_state_twice(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    t1 = db.begin()
    db.update(t1, "a", 10)
    db.commit(t1)
    t2 = db.begin()
    db.update(t2, "b", 20)                  # loser
    disk = db.crash()
    first = R.recover(db.wal, disk)
    second = R.recover(db.wal, disk)
    assert first == second, "running recovery twice must not change the outcome"


def test_second_recovery_finds_no_losers(tmp_path, R):
    """First recovery's CLRs + ABORTs must complete the loser transactions,
    so a crash during recovery resumes instead of restarting undo."""
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "x", "loser-write")
    disk = db.crash()
    R.recover(db.wal, disk)
    recs = db.wal.read_all()
    types = [r["type"] for r in recs]
    assert "CLR" in types and "ABORT" in types
    # second recovery should find nothing new to undo — same result again
    again = R.recover(db.wal, disk)
    assert "x" not in again or again["x"]["value"] is None


# --------------------------------------------------- mixed committed/loser
def test_recovery_mixed_workload_correct_split(tmp_path, R):
    db = R.Database(str(tmp_path / "wal.log"))
    tc = db.begin()
    db.update(tc, "committed_page", "keep-me")
    db.commit(tc)
    tl = db.begin()
    db.update(tl, "loser_page", "roll-me-back")
    db.update(tl, "committed_page", "clobber")   # loser also touched committed page
    disk = db.crash()
    state = R.recover(db.wal, disk)
    assert state["committed_page"]["value"] == "keep-me", \
        "undo must reverse the loser's clobber of a committed page"
    assert "loser_page" not in state or state["loser_page"]["value"] is None


def test_durability_point_only_after_commit_fsync(tmp_path, R):
    """The client-visible rule: before COMMIT is fsynced, nothing is promised;
    after it, recovery must reproduce the value no matter what hit disk."""
    db = R.Database(str(tmp_path / "wal.log"))
    t = db.begin()
    db.update(t, "ledger", "debit 500")
    db.commit(t)
    # verify the COMMIT record is durable in the file BEFORE we simulate crash
    recs = db.wal.read_all()
    assert any(r["type"] == "COMMIT" for r in recs)
    state = R.recover(db.wal, db.crash())
    assert state["ledger"]["value"] == "debit 500"
