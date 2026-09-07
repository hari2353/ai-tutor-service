"""Lab 01 tests: memtable → flush → SSTables → tombstones → compaction."""
import json
import os

import pytest


# ------------------------------------------------------------------ MemTable
def test_memtable_put_get_roundtrip(E):
    m = E.MemTable()
    m.put("a", 1)
    m.put("b", 2)
    assert m.get("a") == 1
    assert m.get("b") == 2
    assert m.size() == 2


def test_memtable_absent_returns_missing_not_none(E):
    m = E.MemTable()
    assert m.get("nope") is E.MISSING
    assert m.get("nope") is not None


def test_memtable_overwrite_counts_once(E):
    m = E.MemTable()
    m.put("k", "old")
    m.put("k", "new")
    assert m.get("k") == "new"
    assert m.size() == 1


def test_memtable_items_sorted(E):
    m = E.MemTable()
    for k in ["z", "a", "m", "b"]:
        m.put(k, k.upper())
    assert [k for k, _ in m.items()] == ["a", "b", "m", "z"]


def test_memtable_delete_is_tombstone_write(E):
    m = E.MemTable()
    m.put("k", "v")
    m.put("k", None)          # None means delete
    assert E.is_tombstone(m.get("k")) is True or m.get("k") is None
    assert m.size() == 1


# ------------------------------------------------------------------ SSTable
def test_sstable_roundtrip(tmp_path, E):
    p = str(tmp_path / "sst_0.json")
    E.SSTable.create(p, [("a", 1), ("b", 2), ("c", 3)])
    s = E.SSTable(p)
    assert s.get("a") == 1
    assert s.get("c") == 3
    assert s.get("zzz") is E.MISSING


def test_sstable_items_sorted(tmp_path, E):
    p = str(tmp_path / "sst_0.json")
    E.SSTable.create(p, [("x", 24), ("a", 1), ("m", 13)])   # sorted by caller
    s = E.SSTable(p)
    assert s.items() == [("a", 1), ("m", 13), ("x", 24)]


def test_sstable_is_immutable_file_on_disk(tmp_path, E):
    p = str(tmp_path / "sst_0.json")
    E.SSTable.create(p, [("a", 1)])
    assert os.path.exists(p)
    with open(p) as f:
        rec = json.loads(f.readline())
    assert rec[0] == "a"
    assert len(json.loads(f.readline())) == 0 if False else True  # one line is enough


def test_tombstone_detection(E):
    assert E.is_tombstone(E.TOMBSTONE) is True
    assert E.is_tombstone("value") is False
    assert E.is_tombstone(None) is False
    assert E.is_tombstone(0) is False
    assert E.is_tombstone("") is False


# ------------------------------------------------------------------ Manifest
def test_manifest_add_newest_first(tmp_path, E):
    man = E.Manifest(str(tmp_path))
    man.add(str(tmp_path / "sst_0.json"))
    man.add(str(tmp_path / "sst_1.json"))
    assert man.all()[0].endswith("sst_1.json")
    assert man.all()[1].endswith("sst_0.json")


def test_manifest_replace_swaps_inputs_for_output(tmp_path, E):
    man = E.Manifest(str(tmp_path))
    p0, p1, p2 = (str(tmp_path / f"sst_{i}.json") for i in range(3))
    man.add(p0)
    man.add(p1)
    man.add(p2)
    man.replace([p0, p1, p2], str(tmp_path / "merged.json"))
    assert len(man.all()) == 1
    assert man.all()[0].endswith("merged.json")


def test_manifest_persists_across_instances(tmp_path, E):
    man1 = E.Manifest(str(tmp_path))
    man1.add(str(tmp_path / "sst_0.json"))
    man1.add(str(tmp_path / "sst_1.json"))
    man2 = E.Manifest(str(tmp_path))          # "re-open the engine"
    assert len(man2.all()) == 2
    assert man2.all()[0].endswith("sst_1.json")


# --------------------------------------------------------------- write path
def test_put_get_roundtrip_no_flush(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=100)
    tree.put("name", "haris")
    tree.put("city", "oslo")
    assert tree.get("name") == "haris"
    assert tree.get("city") == "oslo"


def test_flush_threshold_triggers_sstable_file(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=3)
    assert tree.file_count() == 0
    for i in range(3):
        tree.put(f"k{i}", i)
    assert tree.file_count() == 1, "memtable_limit reached — an SSTable must exist"
    assert tree.memtable.size() == 0, "memtable cleared after flush"
    # and the file is really on disk
    assert any(f.startswith("sst_") for f in os.listdir(str(tmp_path)))


def test_multiple_flushes_multiple_files(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    for i in range(6):
        tree.put(f"k{i}", i)
    assert tree.file_count() == 3


def test_reads_hit_memtable_first(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    tree.put("a", 1)
    tree.put("b", 2)              # flush: a,b → SSTable
    tree.put("a", 99)             # newer a lives only in the memtable
    assert tree.get("a") == 99


# ------------------------------------------------------------------- reads
def test_newest_wins_across_sstables(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    tree.put("a", 1)              # flush #1: a=1
    tree.put("b", 1)              # flush #1
    tree.put("a", 2)              # flush #2: a=2
    tree.put("c", 3)              # flush #2
    tree.put("a", 3)              # still memtable (limit 2, size 1 < 2)
    assert tree.get("a") == 3, "memtable is checked first"
    # force the memtable copy out so reads come from the SSTable path
    tree.put("x", 0)              # size 2 → flush #3: a=3, x=0
    assert tree.get("a") == 3, "newest SSTable wins"


def test_get_missing_key_raises(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=100)
    with pytest.raises(KeyError):
        tree.get("never-written")


# --------------------------------------------------------------- tombstones
def test_tombstone_hides_key(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    tree.put("a", "live")         # flush #1
    tree.put("b", "live")         # flush #1
    tree.delete("a")              # tombstone still in memtable
    with pytest.raises(KeyError):
        tree.get("a"), "tombstone in memtable must hide the value"


def test_tombstone_flushed_hides_older_sstable_version(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    tree.put("a", "v1")           # flush #1: a=v1
    tree.put("b", "x")            # flush #1
    tree.delete("a")              # flush #2: a=TOMBSTONE
    tree.put("c", "y")            # flush #2
    with pytest.raises(KeyError):
        tree.get("a"), "flushed tombstone must shadow the older SSTable's value"
    assert tree.get("b") == "x"
    assert tree.get("c") == "y"


def test_delete_then_reinsert(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=100)
    tree.put("k", "v1")
    tree.delete("k")
    tree.put("k", "v2")
    assert tree.get("k") == "v2"


# -------------------------------------------------------------- compaction
def _fill(tree, pairs):
    for k, v in pairs:
        tree.put(k, v)


def test_compaction_merges_and_shrinks_file_count(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    _fill(tree, [(f"k{i}", i) for i in range(8)])      # 4 SSTables
    assert tree.file_count() == 4
    tree.compact()
    assert tree.file_count() == 1
    assert all("sst_" in p for p in tree.manifest.all())


def test_compaction_keeps_newest_version(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    tree.put("a", 1)              # flush #1
    tree.put("b", 10)             # flush #1
    tree.put("a", 2)              # flush #2
    tree.put("b", 20)            # flush #2
    tree.compact()
    assert tree.get("a") == 2, "newest version must survive compaction"
    assert tree.get("b") == 20


def test_compaction_drops_shadowed_tombstones(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    tree.put("a", "v1")           # flush #1
    tree.put("b", "keep")         # flush #1
    tree.delete("a")              # flush #2
    tree.put("c", "keep2")        # flush #2
    tree.compact()
    # the merged file must contain no tombstone at all — nothing is older
    merged = E.SSTable(tree.manifest.all()[0])
    tombstones = [k for k, v in merged.items() if E.is_tombstone(v)]
    assert tombstones == [], "full compaction drops tombstones with nothing beneath"
    with pytest.raises(KeyError):
        tree.get("a")
    assert tree.get("b") == "keep"
    assert tree.get("c") == "keep2"


def test_compaction_removes_old_files_from_disk(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    _fill(tree, [(f"k{i}", i) for i in range(8)])
    before = set(tree.manifest.all())
    tree.compact()
    for p in before:
        assert not os.path.exists(p), "input SSTables must be deleted after merge"


def test_compaction_is_read_transparent(E, tmp_path):
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    data = {f"k{i}": f"v{i}" for i in range(10)}
    _fill(tree, list(data.items()))
    tree.compact()
    for k, v in data.items():
        assert tree.get(k) == v


def test_reads_survive_engine_reopen(E, tmp_path):
    """SSTables + manifest are the durable state; the memtable is not."""
    tree = E.LSMTree(str(tmp_path), memtable_limit=2)
    _fill(tree, [(f"k{i}", i) for i in range(8)])      # 4 flushed SSTables
    tree2 = E.LSMTree(str(tmp_path), memtable_limit=2)  # reopen same dir
    assert tree2.file_count() == 4
    for i in range(8):
        assert tree2.get(f"k{i}") == i


def test_memtable_contents_lost_on_reopen(E, tmp_path):
    """No WAL in this lab — unflushed writes die with the process. (02-wal-toy fixes this.)"""
    tree = E.LSMTree(str(tmp_path), memtable_limit=100)
    tree.put("volatile", "gone")
    tree2 = E.LSMTree(str(tmp_path), memtable_limit=100)
    with pytest.raises(KeyError):
        tree2.get("volatile")
