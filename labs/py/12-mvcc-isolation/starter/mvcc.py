"""Lab 12 — MVCC isolation simulator. Fill in every TODO. Tests define done.

Rules:
  * Pure stdlib. No threads, no sleeps — the interleaving driver makes
    concurrency deterministic by executing an explicit step script.
  * There are NO LOCKS anywhere in this module. Readers never block writers,
    writers never block readers. Conflicts are detected, not prevented.

Model:
  * Every write appends a Version(value, begin_ts, end_ts=None) to the key's
    chain; commit stamps commit_ts and closes the superseded version's window
    with end_ts. A read picks the newest version visible to the snapshot:
    begin <= snap < end (end open = live).
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
        # TODO(step 2a): mark aborted + record reason + drop pending writes
        raise NotImplementedError

    def rollback(self, tx: Transaction) -> None:
        # TODO(step 2b): guard via _require_active, then abort as 'rolled-back'
        raise NotImplementedError

    # ----------------------------------------------------------- visibility
    def _visible(self, v: Version, tx: Transaction, snap: int) -> bool:
        """The whole lab in one function.

        own versions            -> always visible to their creator
        creator aborted         -> invisible to EVERYONE (even RU)
        READ_UNCOMMITTED        -> begin_ts <= snap < end_ts   (dirty reads live here)
        RC / RR / SER           -> committed AND commit_ts <= snap < end_ts
        """
        # TODO(step 3): implement the four clauses above
        raise NotImplementedError

    def _scan(self, key: str, tx: Transaction, snap: int):
        """Newest-first walk of the chain; first visible version wins."""
        # TODO(step 4)
        raise NotImplementedError

    def _refresh_snapshot(self, tx: Transaction) -> None:
        """RU / RC take a FRESH snapshot per statement; RR/SER keep the one
        from begin(). This single policy decision IS the isolation ladder."""
        # TODO(step 5)
        raise NotImplementedError

    # ----------------------------------------------------------------- read
    def read(self, tx: Transaction, key: str):
        """Refresh snapshot (per level), serve own pending write first
        (read-your-writes), then scan the chain. Record SIREADs for SER."""
        # TODO(step 6)
        raise NotImplementedError

    def keys_between(self, tx: Transaction, lo: str, hi: str) -> list[str]:
        """Range (predicate) read: sorted keys in [lo, hi] with a visible value."""
        # TODO(step 7)
        raise NotImplementedError

    def _note_read(self, tx: Transaction, key: str) -> None:
        """SER only: add to sireads; if another active SER tx already wrote this
        key, record the reverse-direction rw edge (reader, writer)."""
        # TODO(step 8a)
        raise NotImplementedError

    def _covers_siread(self, tx: Transaction, key: str) -> bool:
        """Has this tx read `key`, or range-scanned a predicate covering it?"""
        # TODO(step 8b)
        raise NotImplementedError

    # ---------------------------------------------------------------- write
    def write(self, tx: Transaction, key: str, value: Any) -> int:
        """Append a Version stamped with the WRITE-START ts (this is what makes
        it visible to RU readers immediately), buffer it for read-your-writes,
        and — SER only — record rw edges and run the cycle check on myself."""
        # TODO(step 9)
        raise NotImplementedError

    def _record_write_edges(self, wtx: Transaction, key: str) -> None:
        """rw-antidependency: an active SER tx has read (the version this write
        supersedes). Bookkeeping only — nobody blocks, nobody waits."""
        # TODO(step 10a)
        raise NotImplementedError

    def check_dangerous(self, tx: Transaction) -> None:
        """Dangerous structure, lite: two CONCURRENT transactions that each read
        what the other wrote (an rw-antidependency cycle). The detector loses:
        raise SerializationFailure('ssi-cycle', ...)."""
        # TODO(step 10b)
        raise NotImplementedError

    # --------------------------------------------------------------- commit
    def _fcw_check(self, tx: Transaction, key: str) -> None:
        """First-committer-wins: lose if anyone else COMMITTED a write to this
        key after my snapshot was taken. Uncommitted writers don't count — they
        lose later, at their own commit, against MY commit timestamp."""
        # TODO(step 11a): raise SerializationFailure('ww-conflict', ...)
        raise NotImplementedError

    def commit(self, tx: Transaction) -> int:
        """SER: cycle check. RR/SER: FCW per written key. Then stamp every own
        version with ONE commit_ts and close each superseded predecessor's
        window (prev.end_ts = cts). Mark committed, return cts."""
        # TODO(step 11b)
        raise NotImplementedError


# --------------------------------------------------------------------------- seeding
def seed_store(store: MVCCStore, initial: dict[str, Any]) -> Transaction:
    """Committed starting state, written through the public API."""
    # TODO: begin a __seed__ tx, write each pair, commit
    raise NotImplementedError


# --------------------------------------------------------------------------- driver
class ScriptResult:
    """What happened when a step script ran. Tests assert against this."""

    def __init__(self, store: MVCCStore) -> None:
        self.store = store
        self.log: list[tuple] = []
        self.txs: dict[str, Transaction] = {}

    @property
    def committed(self) -> set[str]:
        # TODO: names of transactions whose status is committed
        raise NotImplementedError

    @property
    def aborted(self) -> dict[str, str]:
        # TODO: {name: abort_reason} for aborted transactions
        raise NotImplementedError

    def reads(self, name: str, key: str) -> list:
        # TODO: all values ('r', name, key, value) events, in order
        raise NotImplementedError

    def last_read(self, name: str, key: str):
        # TODO: last value read; AssertionError if never read
        raise NotImplementedError

    def ranges(self, name: str) -> list[tuple]:
        # TODO: range results as tuples, in order
        raise NotImplementedError

    def final_state(self) -> dict[str, Any]:
        # TODO: fresh READ_COMMITTED probe over every key
        raise NotImplementedError

    def final_value(self, key: str):
        # TODO: fresh READ_COMMITTED probe of one key
        raise NotImplementedError


Step = tuple


def run_script(store: MVCCStore, steps: Iterable[Step],
               levels: dict[str, str] | None = None) -> ScriptResult:
    """Execute a deterministic two-tx interleaving.

    Steps:  ("t1", "w", key, value) · ("t2", "r", key)
            ("t1", "range", lo, hi) · ("t1", "commit") · ("t2", "rollback")
    Levels: {"t1": REPEATABLE_READ, "t2": SERIALIZABLE}; default READ_COMMITTED.
    Transactions auto-begin at their first step. Steps of a finished or aborted
    transaction are logged as skips, never executed. A SerializationFailure
    aborts the offending transaction in-place (logged as ('abort', name, reason)).
    """
    # TODO(step 12): the driver loop
    raise NotImplementedError


def simulate(steps: Iterable[Step], levels: dict[str, str] | None = None,
             seed: dict[str, Any] | None = None) -> tuple[MVCCStore, ScriptResult]:
    """Fresh store + optional committed seed + run the script."""
    # TODO(step 13)
    raise NotImplementedError
