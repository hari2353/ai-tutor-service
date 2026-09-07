"""Lab 02 — reference solution: WAL + ARIES-style recovery."""
from __future__ import annotations

import json
import os


class WAL:
    def __init__(self, path: str) -> None:
        self.path = path
        self.next_lsn = 1

    def append(self, txn: int, type: str, page: str | None = None,
               before: object = None, after: object = None) -> int:
        lsn = self.next_lsn
        self.next_lsn += 1
        rec = {"lsn": lsn, "txn": txn, "type": type,
               "page": page, "before": before, "after": after}
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec) + "\n")
            f.flush()
            os.fsync(f.fileno())
        return lsn

    def read_all(self) -> list[dict]:
        if not os.path.exists(self.path):
            return []
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    out.append(json.loads(line))
        return out


class BufferManager:
    def __init__(self) -> None:
        self.pages: dict[str, dict] = {}
        self.disk: dict[str, dict] = {}
        self.flushed_lsn = 0

    def set_flushed_lsn(self, lsn: int) -> None:
        self.flushed_lsn = max(self.flushed_lsn, lsn)

    def write(self, page: str, value: object, lsn: int) -> None:
        self.pages[page] = {"value": value, "page_lsn": lsn}

    def flush_page(self, page: str) -> None:
        if self.wal_violation(page):
            raise RuntimeError(
                f"WAL rule violation: page {page!r} page_lsn "
                f"{self.pages[page]['page_lsn']} > flushed_lsn {self.flushed_lsn} "
                f"— log record must be durable before the page")
        self.disk[page] = dict(self.pages[page])

    def wal_violation(self, page: str) -> bool:
        buf = self.pages.get(page)
        return bool(buf and buf["page_lsn"] > self.flushed_lsn)

    def snapshot_disk(self) -> dict[str, dict]:
        return {p: dict(d) for p, d in self.disk.items()}


def _copy(state: dict[str, dict]) -> dict[str, dict]:
    return {p: dict(d) for p, d in state.items()}


class Database:
    def __init__(self, wal_path: str) -> None:
        self.wal = WAL(wal_path)
        self.buffers = BufferManager()
        self._active: set[int] = set()
        self._next_txn = 1

    def begin(self) -> int:
        txn = self._next_txn
        self._next_txn += 1
        lsn = self.wal.append(txn, "BEGIN")
        self.buffers.set_flushed_lsn(lsn)
        self._active.add(txn)
        return txn

    def _current(self, page: str):
        if page in self.buffers.pages:
            return self.buffers.pages[page]["value"]
        if page in self.buffers.disk:
            return self.buffers.disk[page]["value"]
        return None

    def update(self, txn: int, page: str, after: object) -> int:
        before = self._current(page)
        lsn = self.wal.append(txn, "UPDATE", page=page, before=before, after=after)
        self.buffers.set_flushed_lsn(lsn)
        self.buffers.write(page, after, lsn)
        return lsn

    def commit(self, txn: int) -> None:
        lsn = self.wal.append(txn, "COMMIT")
        self.buffers.set_flushed_lsn(lsn)
        self._active.discard(txn)

    def abort(self, txn: int) -> None:
        """Active rollback, ARIES-style: the txn's updates are undone NOW
        (each undo logged as a CLR, before-images restored to the buffers),
        then the ABORT record marks the transaction finished."""
        recs = [r for r in self.wal.read_all()
                if r["type"] == "UPDATE" and r["txn"] == txn]
        for r in sorted(recs, key=lambda x: -x["lsn"]):
            clr_lsn = self.wal.append(txn, "CLR", page=r["page"],
                                      before=r["after"], after=r["before"])
            self.buffers.set_flushed_lsn(clr_lsn)
            self.buffers.write(r["page"], r["before"], clr_lsn)
        lsn = self.wal.append(txn, "ABORT")
        self.buffers.set_flushed_lsn(lsn)
        self._active.discard(txn)

    def read(self, page: str):
        return self._current(page)

    def crash(self) -> dict[str, dict]:
        disk = self.buffers.snapshot_disk()
        self.buffers.pages = {}              # volatile memory is gone
        self._active = set()
        return disk

    def pages(self) -> dict[str, dict]:
        state = _copy(self.buffers.disk)
        state.update(_copy(self.buffers.pages))
        return state


def recover(wal: WAL, disk: dict[str, dict]) -> dict[str, dict]:
    records = wal.read_all()
    state: dict[str, dict] = {p: dict(d) for p, d in disk.items()}

    # ---- analysis: find losers (BEGIN with no COMMIT/ABORT after it)
    finished: set[int] = set()
    started: set[int] = set()
    for r in records:
        if r["type"] in ("BEGIN",):
            started.add(r["txn"])
        elif r["type"] in ("COMMIT", "ABORT"):
            finished.add(r["txn"])
    losers = started - finished

    # ---- redo: repeat history — every UPDATE and CLR in LSN order,
    # skip lsn <= page_lsn (idempotency). CLRs must replay too: a crash
    # mid-undo leaves partial rollback in the log, and redo reapplies it.
    for r in sorted(records, key=lambda x: x["lsn"]):
        if r["type"] not in ("UPDATE", "CLR"):
            continue
        page = r["page"]
        cur = state.get(page, {"value": None, "page_lsn": 0})
        if r["lsn"] <= cur["page_lsn"]:
            continue                              # already reflected — idempotent
        state[page] = {"value": r["after"], "page_lsn": r["lsn"]}

    # ---- undo: losers in reverse LSN order, before-images, logged as CLRs.
    # Each CLR stamps the page with its OWN lsn so a re-run of undo can see
    # what's already been undone (idempotent undo), and the before-image is
    # only restored if this record's change is still the newest on the page.
    to_undo = sorted(
        (r for r in records
         if r["type"] == "UPDATE" and r["txn"] in losers),
        key=lambda x: -x["lsn"])
    for r in to_undo:
        page = r["page"]
        cur = state.get(page, {"value": None, "page_lsn": 0})
        if r["lsn"] >= cur["page_lsn"]:
            # this record's change is still reflected — restore before-image
            state[page] = {"value": r["before"], "page_lsn": cur["page_lsn"]}
        clr_lsn = wal.append(r["txn"], "CLR", page=page,
                             before=r["after"], after=r["before"])
        state[page]["page_lsn"] = clr_lsn
    # mark losers aborted so a second recovery's analysis finds no losers
    for txn in losers:
        wal.append(txn, "ABORT")
    return state
