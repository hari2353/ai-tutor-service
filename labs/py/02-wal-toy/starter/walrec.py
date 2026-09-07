"""Lab 02 — WAL + ARIES-style recovery. Fill in every TODO. Tests define done.

The durability pipeline:

    update ──▶ 1. append UPDATE record to WAL (write + fsync)   ← durable point
           ──▶ 2. apply to buffer pool (volatile! dies on crash)
           ──▶ 3. commit: append COMMIT, fsync, THEN ack client
           ──▶ 4. page flushes to "disk" lazily, much later

    THE WAL RULE: the log record describing a change must be durable
    BEFORE the page carrying that change reaches disk. wal_violation()
    exists so a test can catch you breaking it.
"""
from __future__ import annotations

import json
import os


# ------------------------------------------------------------------------ WAL
class WAL:
    """Append-only log. One JSON line per record, fsync per append."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.next_lsn = 1
        # TODO: nothing here needs init beyond fields.

    def append(self, txn: int, type: str, page: str | None = None,
               before: object = None, after: object = None) -> int:
        """Assign LSN, write {"lsn":..,"txn":..,"type":..,"page":..,
        "before":..,"after":..} as one line, flush AND fsync. Return the LSN."""
        # TODO(step 1): lsn = self.next_lsn; ...; os.fsync before returning.
        raise NotImplementedError

    def read_all(self) -> list[dict]:
        """Parse the log file into a list of record dicts, LSN order."""
        # TODO(step 1b)
        raise NotImplementedError


# ---------------------------------------------------------------- buffer pool
class BufferManager:
    """Dirty pages with per-page LSNs. 'Disk' is the dict we flush into."""

    def __init__(self) -> None:
        self.pages: dict[str, dict] = {}          # page -> {"value":..,"page_lsn":..}
        self.disk: dict[str, dict] = {}           # page -> {"value":..,"page_lsn":..}
        self.flushed_lsn = 0                      # highest LSN fsynced to the WAL
        # TODO(step 2a): nothing more needed.

    def set_flushed_lsn(self, lsn: int) -> None:
        """Called by the WAL/engine after each append+fsync."""
        # TODO(step 2b)
        raise NotImplementedError

    def write(self, page: str, value: object, lsn: int) -> None:
        """Apply a change to the (volatile) buffer; stamp page_lsn."""
        # TODO(step 2c)
        raise NotImplementedError

    def flush_page(self, page: str) -> None:
        """Write the buffer page to 'disk'. Enforce the WAL rule here:
        a page whose page_lsn > flushed_lsn must NOT be flushed —
        call wal_violation() first (tests rely on it)."""
        # TODO(step 2d)
        raise NotImplementedError

    def wal_violation(self, page: str) -> bool:
        """True iff flushing this page now would break the WAL rule:
        its page_lsn is newer than anything fsynced to the log."""
        # TODO(step 2e)
        raise NotImplementedError

    def snapshot_disk(self) -> dict[str, dict]:
        """The pages that actually reached 'disk' before the crash."""
        # TODO(step 2f): return a deep-enough copy for assertions.
        raise NotImplementedError


# ------------------------------------------------------------------ the DB toy
class Database:
    """Transactions write WAL records + dirty buffers; crash() drops buffers."""

    def __init__(self, wal_path: str) -> None:
        self.wal = WAL(wal_path)
        self.buffers = BufferManager()
        self._active: set[int] = set()
        self._next_txn = 1

    def begin(self) -> int:
        """Allocate a txn id; append BEGIN."""
        # TODO(step 3a)
        raise NotImplementedError

    def update(self, txn: int, page: str, after: object) -> int:
        """Append UPDATE with before-image (current buffer/disk value),
        fsync the log, THEN apply to the buffer. Returns the record's LSN."""
        # TODO(step 3b): before = value currently visible in buffers (or disk).
        raise NotImplementedError

    def commit(self, txn: int) -> None:
        # TODO(step 3c): append COMMIT, fsync (durability point), update sets.
        raise NotImplementedError

    def abort(self, txn: int) -> None:
        # TODO(step 3d): append ABORT, fsync, update sets.
        raise NotImplementedError

    def read(self, page: str):
        """Current visible value (buffer if dirty, else disk)."""
        # TODO(step 3e)
        raise NotImplementedError

    def crash(self) -> dict[str, dict]:
        """Power loss: dirty buffers vanish; the fsynced WAL survives.
        Returns the disk pages snapshot that recovery starts from."""
        # TODO(step 4)
        raise NotImplementedError

    def pages(self) -> dict[str, dict]:
        """Visible page state (buffer overlaid on disk) for assertions."""
        # TODO(step 4b)
        raise NotImplementedError


# ------------------------------------------------------------------- recovery
def recover(wal: WAL, disk: dict[str, dict]) -> dict[str, dict]:
    """ARIES-style three-pass recovery over the surviving WAL + disk pages.

    Returns the recovered page state: {page: {"value":..,"page_lsn":..}}.

    Analysis: forward scan — txn has BEGIN but no COMMIT/ABORT => loser.
    Redo:    replay after-images of ALL UPDATEs in LSN order (committed and
             not — "repeat history"), skipping lsn <= page's current page_lsn.
    Undo:    losers in reverse LSN order, restore before-images, and append
             a CLR per undone record ({"type":"CLR", "undo_of": lsn}) so a
             crash mid-undo can resume rather than restart.
    """
    # TODO(step 5): implement analysis / redo / undo as described.
    raise NotImplementedError
