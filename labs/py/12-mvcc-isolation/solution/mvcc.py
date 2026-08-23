"""Lab 12 — MVCC isolation simulator. Reference solution.

Rules:
  * Pure stdlib. No threads, no sleeps — the interleaving driver makes
    concurrency deterministic by executing an explicit step script.
  * There are NO LOCKS anywhere in this module. Readers never block writers,
    writers never block readers. Conflicts are detected, not prevented.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable

# --------------------------------------------------------------------------- errors
class SerializationFailure(Exception):
    """Raised on the LOSING side of a write-write conflict (first-committer-wins)
    or when SSI's dangerous structure (an rw-antidependency cycle) is detected.
    `.reason` is 'ww-conflict' or 'ssi-cycle'; the transaction must retry."""

    def __init__(self, reason: str, detail: str = "") -> None:
        super().__init__(detail or reason)
        self.reason = reason


class AbortedTransaction(Exception):
    """Operating on a transaction that already aborted."""


# --------------------------------------------------------------------------- levels
READ_UNCOMMITTED = "READ_UNCOMMITTED"
READ_COMMITTED = "READ_COMMITTED"
REPEATABLE_READ = "REPEATABLE_READ"
SERIALIZABLE = "SERIALIZABLE"

LEVELS = (READ_UNCOMMITTED, READ_COMMITTED, REPEATABLE_READ, SERIALIZABLE)

# Levels that pin ONE snapshot for the whole transaction (the others take a
# fresh snapshot at the start of every statement).
_SNAPSHOT_PER_TXN = (REPEATABLE_READ, SERIALIZABLE)


# --------------------------------------------------------------------------- model
@dataclass
class Version:
    """One row version. A key's chain is ordered by append (write) time."""

    key: str
    value: Any
    begin_ts: int                    # ts at which the write EXECUTED (write-start)
    xid: int                         # owning transaction id
    end_ts: int | None = None        # commit ts of the superseding tx; None = open
    commit_ts: int | None = None     # set when the owning tx commits
    committed: bool = False          # flips True at commit


@dataclass
class Transaction:
    xid: int
    name: str
    level: str
    snapshot_ts: int                 # pinned for RR/SER, refreshed per statement RU/RC
    status: str = "active"           # active | committed | aborted
    abort_reason: str = ""
    pending_writes: dict[str, Any] = field(default_factory=dict)  # read-your-writes overlay
    wrote_keys: set[str] = field(default_factory=set)
    my_versions: list[Version] = field(default_factory=list)
    sireads: set[str] = field(default_factory=set)                # SSI-lite read set
    range_sireads: list[tuple[str, str]] = field(default_factory=list)  # predicate reads


# --------------------------------------------------------------------------- store
class MVCCStore:
    """Version-chained KV store with snapshot visibility and four isolation
    levels. Nothing here ever blocks: there is no lock manager at all."""

    def __init__(self) -> None:
        self.data: dict[str, list[Version]] = {}   # key -> version chain (append order)
        self.now: int = 0                          # logical clock
        self.locks: dict = {}                      # ALWAYS empty — kept so tests can prove it
        self.rw_edges: set[tuple[int, int]] = set()  # SSI-lite (reader_xid, writer_xid)
        self._next_xid = 1
        self._status: dict[int, str] = {}          # xid -> status (survives tx gc)
        self.by_name: dict[str, Transaction] = {}

    # ---------------------------------------------------------------- clock
    def tick(self) -> int:
        self.now += 1
        return self.now

    def lock_count(self) -> int:
        return len(self.locks)                     # invariantly 0

    # ------------------------------------------------------------ lifecycle
    def begin(self, level: str = READ_COMMITTED, name: str | None = None) -> Transaction:
        xid = self._next_xid
        self._next_xid += 1
        tx = Transaction(xid=xid, name=name or f"x{xid}", level=level,
                         snapshot_ts=self.tick())
        self._status[xid] = "active"
        if name:
            self.by_name[name] = tx
        return tx

    def _require_active(self, tx: Transaction) -> None:
        if tx.status == "aborted":
            raise AbortedTransaction(f"{tx.name} aborted ({tx.abort_reason})")
        if tx.status == "committed":
            raise AbortedTransaction(f"{tx.name} already committed")

    def _mark(self, tx: Transaction, status: str, reason: str = "") -> None:
        tx.status = status
        tx.abort_reason = reason
        self._status[tx.xid] = status

    def abort(self, tx: Transaction, reason: str) -> None:
        """Lose. Pending writes are discarded; appended versions stay behind in
        the chains as garbage (commit_ts never set) — vacuum's problem, and
        invisible to every reader because the creator is aborted."""
        self._mark(tx, "aborted", reason)
        tx.pending_writes.clear()

    def rollback(self, tx: Transaction) -> None:
        self._require_active(tx)
        self.abort(tx, "rolled-back")

    # ----------------------------------------------------------- visibility
    def _visible(self, v: Version, tx: Transaction, snap: int) -> bool:
        if v.xid == tx.xid:
            return True                            # own versions (read-your-writes path)
        if self._status.get(v.xid) == "aborted":
            return False                           # aborted writes vanish for everyone
        if tx.level == READ_UNCOMMITTED:
            # dirty reads allowed: visible from the moment the write STARTED
            return v.begin_ts <= snap and (v.end_ts is None or snap < v.end_ts)
        # RC / RR / SER: committed data only, and only if committed by snap time
        if not v.committed or v.commit_ts > snap:
            return False
        return v.end_ts is None or snap < v.end_ts

    def _scan(self, key: str, tx: Transaction, snap: int):
        for v in reversed(self.data.get(key, [])):     # newest first
            if self._visible(v, tx, snap):
                return v.value
        return None

    def _refresh_snapshot(self, tx: Transaction) -> None:
        if tx.level not in _SNAPSHOT_PER_TXN:          # RU / RC: fresh per statement
            tx.snapshot_ts = self.tick()

    # ----------------------------------------------------------------- read
    def read(self, tx: Transaction, key: str):
        self._require_active(tx)
        self._refresh_snapshot(tx)
        if key in tx.pending_writes:                   # read-your-writes, all levels
            self._note_read(tx, key)
            return tx.pending_writes[key]
        value = self._scan(key, tx, tx.snapshot_ts)
        self._note_read(tx, key)
        return value

    def keys_between(self, tx: Transaction, lo: str, hi: str) -> list[str]:
        """Range (predicate) read: keys in [lo, hi] with a visible value."""
        self._require_active(tx)
        self._refresh_snapshot(tx)
        out: list[str] = []
        for key in sorted(self.data):
            if lo <= key <= hi:
                value = tx.pending_writes.get(key) if key in tx.pending_writes \
                    else self._scan(key, tx, tx.snapshot_ts)
                self._note_read(tx, key)
                if value is not None:
                    out.append(key)
        if tx.level == SERIALIZABLE:
            tx.range_sireads.append((lo, hi))
        return out

    def _note_read(self, tx: Transaction, key: str) -> None:
        if tx.level != SERIALIZABLE:
            return
        tx.sireads.add(key)
        # reverse-direction edge: I just read what another live SER tx already wrote
        for other in self.by_name.values():
            if (other.xid != tx.xid and other.level == SERIALIZABLE
                    and other.status == "active" and key in other.wrote_keys):
                self.rw_edges.add((tx.xid, other.xid))

    def _covers_siread(self, tx: Transaction, key: str) -> bool:
        if key in tx.sireads:
            return True
        return any(lo <= key <= hi for lo, hi in tx.range_sireads)

    # ---------------------------------------------------------------- write
    def write(self, tx: Transaction, key: str, value: Any) -> int:
        self._require_active(tx)
        ts = self.tick()
        v = Version(key=key, value=value, begin_ts=ts, xid=tx.xid)
        self.data.setdefault(key, []).append(v)
        tx.my_versions.append(v)
        tx.wrote_keys.add(key)
        tx.pending_writes[key] = value                 # visible to myself immediately
        if tx.level == SERIALIZABLE:
            self._record_write_edges(tx, key)
            self.check_dangerous(tx)                   # SSI-lite: may abort ME now
        return ts

    def _record_write_edges(self, wtx: Transaction, key: str) -> None:
        """rw-antidependency: an active SER tx has read (the version this write
        supersedes). Bookkeeping only — nobody blocks, nobody waits."""
        for other in self.by_name.values():
            if (other.xid != wtx.xid and other.level == SERIALIZABLE
                    and other.status == "active" and self._covers_siread(other, key)):
                self.rw_edges.add((other.xid, wtx.xid))

    def check_dangerous(self, tx: Transaction) -> None:
        """Dangerous structure, lite: two CONCURRENT transactions that each read
        what the other wrote (an rw-antidependency cycle). The detector loses."""
        for a, b in self.rw_edges:
            if b != tx.xid or a == b:
                continue
            if (tx.xid, a) in self.rw_edges \
                    and self._status.get(a) == "active" \
                    and self._status.get(b) == "active":
                raise SerializationFailure(
                    "ssi-cycle",
                    f"rw-antidependency cycle between xid {a} and xid {b}")

    # --------------------------------------------------------------- commit
    def _fcw_check(self, tx: Transaction, key: str) -> None:
        """First-committer-wins: lose if anyone else COMMITTED a write to this
        key after my snapshot was taken. Uncommitted writers don't count — they
        lose later, at their own commit, against MY commit timestamp."""
        for v in self.data.get(key, []):
            if v.xid == tx.xid:
                continue
            if (self._status.get(v.xid) == "committed"
                    and v.commit_ts is not None
                    and v.commit_ts > tx.snapshot_ts):
                raise SerializationFailure(
                    "ww-conflict",
                    f"key '{key}' committed by xid {v.xid} after my snapshot")

    def commit(self, tx: Transaction) -> int:
        self._require_active(tx)
        if tx.level == SERIALIZABLE:
            self.check_dangerous(tx)
        if tx.level in (REPEATABLE_READ, SERIALIZABLE):
            for key in sorted(tx.wrote_keys):
                self._fcw_check(tx, key)
        cts = self.tick()
        for v in tx.my_versions:
            v.commit_ts = cts
            v.committed = True
            chain = self.data[v.key]
            i = chain.index(v)
            for prev in reversed(chain[:i]):           # supersede: close the window
                if prev.xid != tx.xid and prev.end_ts is None:
                    prev.end_ts = cts
                    break
        self._mark(tx, "committed")
        return cts


# --------------------------------------------------------------------------- seeding
def seed_store(store: MVCCStore, initial: dict[str, Any]) -> Transaction:
    """Committed starting state, written through the public API."""
    tx = store.begin(READ_COMMITTED, name="__seed__")
    for key, value in initial.items():
        store.write(tx, key, value)
    store.commit(tx)
    return tx


# --------------------------------------------------------------------------- driver
class ScriptResult:
    """What happened when a step script ran. Tests assert against this."""

    def __init__(self, store: MVCCStore) -> None:
        self.store = store
        self.log: list[tuple] = []
        self.txs: dict[str, Transaction] = {}

    @property
    def committed(self) -> set[str]:
        return {t.name for t in self.txs.values() if t.status == "committed"}

    @property
    def aborted(self) -> dict[str, str]:
        return {t.name: t.abort_reason for t in self.txs.values() if t.status == "aborted"}

    def reads(self, name: str, key: str) -> list:
        return [e[3] for e in self.log if e[0] == "r" and e[1] == name and e[2] == key]

    def last_read(self, name: str, key: str):
        values = self.reads(name, key)
        if not values:
            raise AssertionError(f"{name} never read {key!r}")
        return values[-1]

    def ranges(self, name: str) -> list[tuple]:
        return [tuple(e[3]) for e in self.log if e[0] == "range" and e[1] == name]

    def final_state(self) -> dict[str, Any]:
        probe = self.store.begin(READ_COMMITTED, name="?final-probe")
        return {k: self.store.read(probe, k) for k in sorted(self.store.data)}

    def final_value(self, key: str):
        probe = self.store.begin(READ_COMMITTED, name=f"?probe:{key}")
        return self.store.read(probe, key)


Step = tuple


def run_script(store: MVCCStore, steps: Iterable[Step],
               levels: dict[str, str] | None = None) -> ScriptResult:
    """Execute a deterministic two-tx interleaving.

    Steps:  ("t1", "w", key, value) · ("t2", "r", key)
            ("t1", "range", lo, hi) · ("t1", "commit") · ("t2", "rollback")
    Levels: {"t1": REPEATABLE_READ, "t2": SERIALIZABLE}; default READ_COMMITTED.
    Transactions auto-begin at their first step. Steps of a finished or aborted
    transaction are logged as skips, never executed.
    """
    levels = levels or {}
    res = ScriptResult(store)
    done: dict[str, str] = {}

    def tx_for(name: str) -> Transaction:
        if name not in res.txs:
            res.txs[name] = store.begin(levels.get(name, READ_COMMITTED), name=name)
        return res.txs[name]

    for step in steps:
        name, op = step[0], step[1]
        if name in done:
            res.log.append(("skip", name, op, done[name]))
            continue
        tx = tx_for(name)
        try:
            if op == "w":
                _, _, key, value = step
                store.write(tx, key, value)
                res.log.append(("w", name, key))
            elif op == "r":
                key = step[2]
                res.log.append(("r", name, key, store.read(tx, key)))
            elif op == "range":
                _, _, lo, hi = step
                res.log.append(("range", name, (lo, hi),
                                tuple(store.keys_between(tx, lo, hi))))
            elif op == "commit":
                store.commit(tx)
                done[name] = "committed"
                res.log.append(("commit", name))
            elif op == "rollback":
                store.rollback(tx)
                done[name] = "aborted"
                res.log.append(("rollback", name))
            else:
                raise ValueError(f"unknown step op {op!r}")
        except SerializationFailure as failure:
            store.abort(tx, failure.reason)
            done[name] = "aborted"
            res.log.append(("abort", name, failure.reason))
    return res


def simulate(steps: Iterable[Step], levels: dict[str, str] | None = None,
             seed: dict[str, Any] | None = None) -> tuple[MVCCStore, ScriptResult]:
    """Fresh store + optional committed seed + run the script."""
    store = MVCCStore()
    if seed:
        seed_store(store, seed)
    return store, run_script(store, steps, levels)
