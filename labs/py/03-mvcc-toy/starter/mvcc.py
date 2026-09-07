"""Lab 03 — a toy MVCC engine with isolation levels. Fill in every TODO.

The core idea, in Postgres terms:

    every key's history is a version chain:
        [Version(txn_id, value, committed, begin_ts, end_ts), ...]

    a snapshot is a point in commit-timestamp space. A version is VISIBLE
        iff  its txn committed with begin_ts <= snapshot
             AND (end_ts is unset OR end_ts > snapshot)

    isolation level  =  WHEN you take snapshots + WHAT conflicts abort you:

        READ_UNCOMMITTED   reads may see uncommitted versions (dirty read)
        READ_COMMITTED     fresh snapshot PER STATEMENT
        REPEATABLE_READ    one snapshot PER TRANSACTION; first-committer-wins
        SERIALIZABLE       RR + read-set vs concurrent-commit check (SSI-ish)
"""
from __future__ import annotations

from dataclasses import dataclass, field


class SerializationFailure(Exception):
    """The txn lost a conflict. Real DBs map this to SQLSTATE 40001 — retry."""


ISOLATION_LEVELS = ("READ_UNCOMMITTED", "READ_COMMITTED",
                    "REPEATABLE_READ", "SERIALIZABLE")


@dataclass
class Version:
    txn_id: int
    value: object
    committed: bool = False
    begin_ts: int = 0          # set at commit time
    end_ts: int | None = None  # set when a later txn supersedes it


@dataclass
class Txn:
    txn_id: int
    snapshot: int | None = None       # None until first use / begin
    writes: dict = field(default_factory=dict)   # key -> pending value
    reads: set = field(default_factory=set)      # keys read (for SER)
    level: str = "READ_COMMITTED"


class MVCCStore:
    """Keys -> version chains, plus the txn/commit machinery."""

    def __init__(self) -> None:
        self.chains: dict[str, list[Version]] = {}
        self.committed_txns: dict[int, int] = {}    # txn_id -> commit_ts
        self.next_txn_id = 1
        self.commit_ts = 0                          # global commit clock

    # ------------------------------------------------------------- txn state
    def begin_txn(self, level: str) -> Txn:
        """Assign id. RR/SER take the snapshot NOW; RC/RU take it lazily."""
        # TODO(step 1)
        raise NotImplementedError

    def current_snapshot(self, txn: Txn) -> int:
        """The snapshot this txn reads at right now: RC/RU re-take it per
        statement (max commit_ts), RR/SER use txn.snapshot."""
        # TODO(step 2)
        raise NotImplementedError

    # ------------------------------------------------------------- visibility
    def visible_version(self, key: str, snapshot: int,
                        reader: Txn | None = None,
                        allow_uncommitted: bool = False):
        """Newest version of `key` visible at `snapshot`.

        Rules:
          * uncommitted versions: visible only to their own writer
            (reader.txn_id == version.txn_id) or when allow_uncommitted.
          * committed version visible iff begin_ts <= snapshot
            AND (end_ts is None or end_ts > snapshot).
        Return the Version or None."""
        # TODO(step 3): walk newest-first; first hit wins.
        raise NotImplementedError

    # ----------------------------------------------------------------- commit
    def commit_txn(self, txn: Txn) -> int:
        """Atomic commit: check conflicts (level-dependent), stamp every
        pending version with one new commit_ts, close the superseded
        versions, record commit_ts. Returns the commit ts.
        Raises SerializationFailure.

        Conflict rules at commit:
          * RR and SER: first-committer-wins — for each key in writes, if a
            version was committed by ANOTHER txn with begin_ts > txn.snapshot,
            abort.
          * SER additionally: for each key in reads (minus own writes), if a
            version was committed by another txn with begin_ts > txn.snapshot,
            abort (write-skew / phantom guard).
          * RC/RU: no conflict checks (anomalies are the point)."""
        # TODO(step 4): implement in this order —
        #   1. conflict checks, 2. ts = ++commit clock, 3. supersede old
        #   versions (end_ts = new ts), 4. mark MY uncommitted versions
        #   committed with begin_ts = ts, 5. record in committed_txns.
        raise NotImplementedError

    def abort_txn(self, txn: Txn) -> None:
        """Discard pending writes. Remove this txn's uncommitted versions from
        their chains — they must never become visible to anyone."""
        # TODO(step 5)
        raise NotImplementedError


class Session:
    """The API tests drive. One session = one transaction at a time."""

    def __init__(self, store: MVCCStore, level: str = "READ_COMMITTED") -> None:
        if level not in ISOLATION_LEVELS:
            raise ValueError(f"unknown isolation level: {level}")
        self.store = store
        self.level = level
        self.txn: Txn | None = None

    def begin(self) -> None:
        # TODO(step 6a)
        raise NotImplementedError

    def read(self, key: str):
        """Take/read under this level's snapshot discipline."""
        # TODO(step 6b): RU passes allow_uncommitted=True.
        raise NotImplementedError

    def write(self, key: str, value) -> None:
        """Like Postgres: the new version enters the chain immediately as
        UNCOMMITTED (xmin = me); commit stamps it, abort removes it.
        Buffered in txn.writes too (for conflict checks and abort cleanup)."""
        # TODO(step 6c): append Version(txn_id=..., value=..., committed=False)
        # to the key's chain AND record it in txn.writes. Own uncommitted
        # versions are visible to this txn's own reads.
        raise NotImplementedError

    def commit(self) -> int:
        # TODO(step 6d)
        raise NotImplementedError

    def abort(self) -> None:
        # TODO(step 6e)
        raise NotImplementedError
