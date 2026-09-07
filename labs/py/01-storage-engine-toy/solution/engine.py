"""Lab 01 — reference solution: a toy LSM-tree storage engine."""
from __future__ import annotations

import bisect
import json
import os


class _Missing:
    def __repr__(self) -> str:  # pragma: no cover
        return "MISSING"


MISSING = _Missing()


class Tombstone:
    def __eq__(self, other) -> bool:
        return isinstance(other, Tombstone)

    def __repr__(self) -> str:  # pragma: no cover
        return "<TOMBSTONE>"


TOMBSTONE = Tombstone()


def is_tombstone(value) -> bool:
    return isinstance(value, Tombstone)


def _encode(value):
    return ["T"] if isinstance(value, Tombstone) else ["V", value]


def _decode(raw):
    if raw == ["T"]:
        return TOMBSTONE
    return raw[1]


class MemTable:
    def __init__(self) -> None:
        self.data: dict[str, object] = {}

    def put(self, key: str, value: object) -> None:
        self.data[key] = value

    def get(self, key: str):
        return self.data.get(key, MISSING)

    def size(self) -> int:
        return len(self.data)

    def items(self) -> list[tuple[str, object]]:
        return sorted(self.data.items())


class SSTable:
    def __init__(self, path: str) -> None:
        self.path = path
        self.keys: list[str] = []
        if not os.path.exists(path):
            raise FileNotFoundError(path)
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                self.keys.append(rec[0])
        self._lines: list[str] | None = None

    @staticmethod
    def create(path: str, items: list[tuple[str, object]]) -> "SSTable":
        with open(path, "w", encoding="utf-8") as f:
            for k, v in sorted(items, key=lambda kv: kv[0]):
                f.write(json.dumps([k, _encode(v)]) + "\n")
                f.flush()
                os.fsync(f.fileno())
        return SSTable(path)

    def _records(self) -> list[tuple[str, object]]:
        out = []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                rec = json.loads(line)
                out.append((rec[0], _decode(rec[1])))
        return out

    def get(self, key: str):
        i = bisect.bisect_left(self.keys, key)
        if i < len(self.keys) and self.keys[i] == key:
            return self._records()[i][1]
        return MISSING

    def items(self) -> list[tuple[str, object]]:
        return self._records()


class Manifest:
    def __init__(self, dir: str) -> None:
        self.dir = dir
        self._paths: list[str] = []
        path = self._manifest_path()
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                self._paths = json.load(f)

    def _manifest_path(self) -> str:
        return os.path.join(self.dir, "manifest.json")

    def add(self, path: str) -> None:
        self._paths.insert(0, os.path.basename(path))
        self._save()

    def all(self) -> list[str]:
        return [os.path.join(self.dir, name) for name in self._paths]

    def replace(self, old_paths: list[str], new_path: str) -> None:
        old_names = {os.path.basename(p) for p in old_paths}
        self._paths = [n for n in self._paths if n not in old_names]
        self._paths.insert(0, os.path.basename(new_path))
        self._save()

    def _save(self) -> None:
        final = self._manifest_path()
        tmp = final + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(self._paths, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, final)


class LSMTree:
    def __init__(self, dir: str, memtable_limit: int = 4) -> None:
        self.dir = dir
        os.makedirs(self.dir, exist_ok=True)
        self.memtable_limit = memtable_limit
        self.memtable = MemTable()
        self.manifest = Manifest(self.dir)
        self._file_seq = len(self.manifest.all())

    def put(self, key: str, value: object) -> None:
        self.memtable.put(key, value)
        if self.memtable.size() >= self.memtable_limit:
            self._flush()

    def delete(self, key: str) -> None:
        self.put(key, TOMBSTONE)

    def _flush(self) -> None:
        if self.memtable.size() == 0:
            return
        name = f"sst_{self._file_seq:06d}.json"
        self._file_seq += 1
        path = os.path.join(self.dir, name)
        SSTable.create(path, self.memtable.items())
        self.manifest.add(path)
        self.memtable = MemTable()

    def get(self, key: str):
        v = self.memtable.get(key)
        if v is not MISSING:
            if isinstance(v, Tombstone):
                raise KeyError(key)
            return v
        for path in self.manifest.all():
            sst = SSTable(path)
            v = sst.get(key)
            if v is not MISSING:
                if isinstance(v, Tombstone):
                    raise KeyError(key)
                return v
        raise KeyError(key)

    def file_count(self) -> int:
        return len(self.manifest.all())

    def compact(self) -> None:
        paths = self.manifest.all()
        if not paths:
            return
        merged: dict[str, object] = {}
        for path in reversed(paths):            # oldest first → newer overwrites
            for k, v in SSTable(path).items():
                merged[k] = v
        live = {k: v for k, v in merged.items() if not isinstance(v, Tombstone)}
        name = f"sst_{self._file_seq:06d}.json"
        self._file_seq += 1
        new_path = os.path.join(self.dir, name)
        SSTable.create(new_path, sorted(live.items()))
        self.manifest.replace(paths, new_path)
        for path in paths:
            if os.path.exists(path):
                os.remove(path)
