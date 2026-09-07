"""Lab 01 — a toy LSM-tree storage engine. Fill in every TODO. Tests define done.

Shape of the engine:

    put/delete ──▶ MemTable (sorted, in-memory)
                       │  size >= memtable_limit
                       ▼
                   flush: write SSTable file (immutable, sorted, JSON lines)
                       │  recorded in
                       ▼
                   Manifest (list of live SSTables, newest first)

    get ──▶ MemTable first; miss ──▶ SSTables newest-first; first hit wins
            (a tombstone hit means deleted — stop searching)
"""
from __future__ import annotations

import bisect
import json
import os


class _Missing:
    """Sentinel so 'absent' is distinguishable from a stored None."""

    def __repr__(self) -> str:  # pragma: no cover
        return "MISSING"


MISSING = _Missing()


class Tombstone:
    """Delete marker. Shadows every older version of the key."""

    def __eq__(self, other) -> bool:
        return isinstance(other, Tombstone)

    def __repr__(self) -> str:  # pragma: no cover
        return "<TOMBSTONE>"


TOMBSTONE = Tombstone()


def is_tombstone(value) -> bool:
    # TODO(step 1)
    raise NotImplementedError


class MemTable:
    """Sorted in-memory write path (stand-in for RocksDB's skiplist memtable)."""

    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    def put(self, key: str, value: object) -> None:
        """value=None means delete this key."""
        # TODO(step 2a)
        raise NotImplementedError

    def get(self, key: str):
        """Return the stored value, or MISSING if the key is absent."""
        # TODO(step 2b)
        raise NotImplementedError

    def size(self) -> int:
        """Number of live entries."""
        # TODO(step 2c)
        raise NotImplementedError

    def items(self) -> list[tuple[str, object]]:
        """(key, value) pairs in sorted key order."""
        # TODO(step 2d)
        raise NotImplementedError


class SSTable:
    """Immutable sorted file of (key, value) pairs, JSON-lines format."""

    def __init__(self, path: str) -> None:
        self.path = path
        self.keys: list[str] = []
        # TODO(step 3a): load only the key index here; read the payload
        # lazily in get() — real SSTables cache a sparse index, not the data.
        raise NotImplementedError

    @staticmethod
    def create(path: str, items: list[tuple[str, object]]) -> "SSTable":
        """Write `items` (sorted) to `path`, one JSON line per pair."""
        # TODO(step 3b): serialise tombstones as ["T"] so they round-trip.
        raise NotImplementedError

    def get(self, key: str):
        """Binary search the key index; return the value or MISSING."""
        # TODO(step 3c)
        raise NotImplementedError

    def items(self) -> list[tuple[str, object]]:
        """All pairs, sorted by key."""
        # TODO(step 3d)
        raise NotImplementedError


class Manifest:
    """The list of live SSTable paths, newest first, persisted as manifest.json."""

    def __init__(self, dir: str) -> None:
        self.dir = dir
        self._paths: list[str] = []          # newest first
        # TODO(step 4a): load existing manifest.json if present.
        raise NotImplementedError

    def add(self, path: str) -> None:
        """New SSTable becomes the newest."""
        # TODO(step 4b)
        raise NotImplementedError

    def all(self) -> list[str]:
        """Live SSTable paths, newest first."""
        # TODO(step 4c)
        raise NotImplementedError

    def replace(self, old_paths: list[str], new_path: str) -> None:
        """Compaction swap: drop old_paths, push new_path as newest, persist."""
        # TODO(step 4d)
        raise NotImplementedError

    def _save(self) -> None:
        # TODO(step 4e): atomically (temp file + rename) write manifest.json.
        raise NotImplementedError


class LSMTree:
    """put/get/delete with memtable-first, newest-SSTable-first reads."""

    def __init__(self, dir: str, memtable_limit: int = 4) -> None:
        self.dir = dir
        os.makedirs(self.dir, exist_ok=True)
        self.memtable_limit = memtable_limit
        self.memtable = MemTable()
        self.manifest = Manifest(self.dir)
        self._file_seq = 0

    # ---------------------------------------------------------------- writes
    def put(self, key: str, value: object) -> None:
        # TODO(step 5a): memtable insert; flush when size >= limit.
        raise NotImplementedError

    def delete(self, key: str) -> None:
        """A delete is a write of a tombstone."""
        # TODO(step 5b)
        raise NotImplementedError

    def _flush(self) -> None:
        """Write the memtable as a new SSTable, register it, clear the memtable."""
        # TODO(step 5c)
        raise NotImplementedError

    # ----------------------------------------------------------------- reads
    def get(self, key: str):
        """memtable first, then SSTables newest-first. First hit wins:
        a value is returned; a tombstone means deleted; nothing → KeyError."""
        # TODO(step 5d)
        raise NotImplementedError

    def file_count(self) -> int:
        """Number of live SSTable files on disk."""
        # TODO(step 5e)
        raise NotImplementedError

    # ------------------------------------------------------------ compaction
    def compact(self) -> None:
        """Merge every SSTable into one: newest version per key wins,
        tombstones with nothing older left beneath them are dropped."""
        # TODO(step 6): merge oldest→newest so newer overwrites older in a
        # dict, write the result as one SSTable, manifest.replace() the
        # inputs, then delete the input files from disk.
        raise NotImplementedError
