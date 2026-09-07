"""Lab 03 — reference solution: a toy MVCC engine with isolation levels."""
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
    begin_ts: int = 0
    end_ts: int | None = None


@dataclass
class Txn:
    txn_id: int
    snapshot: int | None = None
    writes: dict = field(default_factory=dict)
    reads: set = field(default_factory=set)
    level: str = "READ_COMMITTED"


class MVCCStore:
    def __init__(self) -> None:
        self.chains: dict[str, list[Version]] = {}
        self.committed_txns: dict[int, int] = {}
        self.next_txn_id = 1
        self.commit_ts = 0

    # ------------------------------------------------------------- txn state
    def begin_txn(self, level: str) -> Txn:
        txn = Txn(txn_id=self.next_txn_id, level=level)
        self.next_txn_id += 1
        if level in ("REPEATABLE_READ", "SERIALIZABLE"):
            txn.snapshot = self.commit_ts
        return txn

    def current_snapshot(self, txn: Txn) -> int:
        if txn.level in ("REPEATABLE_READ", "SERIALIZABLE") \
                and txn.snapshot is not None:
            return txn.snapshot
        txn.snapshot = self.commit_ts          # RC/RU: per statement
        return txn.snapshot

    # ------------------------------------------------------------- visibility
    def visible_version(self, key: str, snapshot: int,
                        reader: Txn | None = None,
                        allow_uncommitted: bool = False):
        for v in reversed(self.chains.get(key, [])):     # newest first
            if not v.committed:
                own = reader is not None and v.txn_id == reader.txn_id
                if own or allow_uncommitted:
                    return v
                continue
            if v.begin_ts <= snapshot and (v.end_ts is None or v.end_ts > snapshot):
                return v
        return None

    # ----------------------------------------------------------------- commit
    def commit_txn(self, txn: Txn) -> int:
        snap = txn.snapshot if txn.snapshot is not None else 0
        if txn.level in ("REPEATABLE_READ", "SERIALIZABLE"):
            keys_to_check = set(txn.writes)
            if txn.level == "SERIALIZABLE":
                keys_to_check |= (txn.reads - set(txn.writes))
            for key in keys_to_check:
                for v in self.chains.get(key, []):
                    if (v.committed and v.txn_id != txn.txn_id
                            and v.begin_ts > snap):
                        raise SerializationFailure(
                            f"conflict on {key!r}: txn {v.txn_id} committed "
                            f"after my snapshot {snap}")
        ts = self.commit_ts + 1
        self.commit_ts = ts
        for key in txn.writes:
            chain = self.chains.setdefault(key, [])
            for v in chain:
                if v.committed and v.end_ts is None:
                    v.end_ts = ts               # close superseded live versions
            for v in chain:
                if v.txn_id == txn.txn_id and not v.committed:
                    v.committed = True          # my own uncommitted versions
                    v.begin_ts = ts
        self.committed_txns[txn.txn_id] = ts
        return ts

    def abort_txn(self, txn: Txn) -> None:
        """Pending versions never become visible; drop them from the chains."""
        for key in txn.writes:
            chain = self.chains.get(key, [])
            self.chains[key] = [v for v in chain
                                if not (v.txn_id == txn.txn_id and not v.committed)]
        txn.writes = {}
        txn.reads = set()


class Session:
    def __init__(self, store: MVCCStore, level: str = "READ_COMMITTED") -> None:
        if level not in ISOLATION_LEVELS:
            raise ValueError(f"unknown isolation level: {level}")
        self.store = store
        self.level = level
        self.txn: Txn | None = None

    def begin(self) -> None:
        self.txn = self.store.begin_txn(self.level)

    def read(self, key: str):
        assert self.txn is not None, "begin() first"
        self.txn.reads.add(key)
        snap = self.store.current_snapshot(self.txn)
        v = self.store.visible_version(
            key, snap, reader=self.txn,
            allow_uncommitted=(self.level == "READ_UNCOMMITTED"))
        return v.value if v is not None else None

    def write(self, key: str, value) -> None:
        """Like Postgres: the new version enters the chain immediately as
        uncommitted (xmin = me); commit stamps it, abort removes it."""
        assert self.txn is not None, "begin() first"
        self.txn.writes[key] = value
        self.store.chains.setdefault(key, []).append(
            Version(txn_id=self.txn.txn_id, value=value, committed=False))

    def commit(self) -> int:
        assert self.txn is not None, "begin() first"
        ts = self.store.commit_txn(self.txn)
        self.txn = None
        return ts

    def abort(self) -> None:
        assert self.txn is not None, "begin() first"
        self.store.abort_txn(self.txn)
        self.txn = None
