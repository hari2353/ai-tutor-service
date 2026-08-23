#!/usr/bin/env python3
"""Unit tests for app/build_data.py — the merge + spec pipeline.

Runs under pytest like the labs. Patches build_data.DATA at the tmp_path so
fragments never touch the real app/data tree."""
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "app"))
import build_data as bd  # noqa: E402


# ---------------------------------------------------------------- validate_fragment
def test_validate_fragment_rejects_missing_required_field(tmp_path):
    rows = [{"id": "m-c1", "q": "ok question"}]          # missing 'a'
    with pytest.raises(SystemExit) as e:
        bd.validate_fragment("flashcards", rows, "cards/m.json")
    msg = str(e.value)
    assert "missing" in msg and " a " in f" {msg} "


def test_validate_fragment_rejects_non_object_row(tmp_path):
    with pytest.raises(SystemExit) as e:
        bd.validate_fragment("drills", ["not-a-dict"], "drillsets/m.json")
    assert "expected object" in str(e.value)


def test_validate_fragment_problems_needs_pattern(tmp_path):
    with pytest.raises(SystemExit):
        bd.validate_fragment("problems", [{"id": "x", "title": "T"}], "p.json")


def test_validate_fragment_accepts_complete_row():
    bd.validate_fragment("flashcards", [{"id": "i", "q": "q", "a": "a"}], "f.json")


# ---------------------------------------------------------------- merge_fragments
def _mk_frag(bd, name, subdir, module_id, key, rows):
    d = bd.DATA / subdir
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{module_id}.json").write_text(json.dumps({key: rows}), encoding="utf-8")


def test_merge_fragments_adds_and_sets_module_from_stem(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "DATA", tmp_path)
    _mk_frag(bd, "flashcards", "cards", "T99-demo",
             "flashcards", [{"id": "T99-demo-c1", "topic": "t", "q": "Q?", "a": "A."}])
    payload = {"version": "0.2", "flashcards": []}
    added, updated = bd.merge_fragments("flashcards", payload)
    assert added == 1 and updated == 0
    row = payload["flashcards"][0]
    assert row["module"] == "T99-demo"


def test_merge_fragments_is_idempotent_and_updates_edits(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "DATA", tmp_path)
    (tmp_path / "cards").mkdir()
    frag = tmp_path / "cards" / "T99-demo.json"
    payload = {"version": "0.2", "flashcards": []}

    def run():
        return bd.merge_fragments("flashcards", payload)

    frag.write_text(json.dumps({"flashcards": [
        {"id": "c1", "q": "old", "a": "old"}]}), encoding="utf-8")
    assert run() == (1, 0)
    assert run() == (0, 0)                       # second pass: nothing to do

    frag.write_text(json.dumps({"flashcards": [
        {"id": "c1", "q": "edited", "a": "old"}]}), encoding="utf-8")
    added, updated = run()
    assert (added, updated) == (0, 1)            # same id -> update, not duplicate
    assert len(payload["flashcards"]) == 1       # no dup rows ever


def test_merge_fragments_bad_json_fails_loudly(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "DATA", tmp_path)
    d = tmp_path / "drillsets"; d.mkdir(parents=True)
    (d / "broken.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(SystemExit) as e:
        bd.merge_fragments("drills", {"version": "0.2", "drills": []})
    assert "bad JSON" in str(e.value)


def test_merge_fragments_propagates_validation_failure(tmp_path, monkeypatch):
    monkeypatch.setattr(bd, "DATA", tmp_path)
    _mk_frag(bd, "drills", "drillsets", "T98-x", "drills",
             [{"id": "d1", "q": "no answer field"}])
    with pytest.raises(SystemExit):
        bd.merge_fragments("drills", {"version": "0.2", "drills": []})


# ---------------------------------------------------------------- spec integrity
def test_build_resolves_all_sprint_ids():
    data = bd.build()                            # raises SystemExit on typo'd sprint id
    ids = {m["id"] for t in data["tracks"] for m in t["modules"]}
    sprint = [m for t in data["tracks"] for m in t["modules"] if "sprint" in m["tags"]]
    assert all(m["id"] in ids for m in sprint)


def test_build_totals_are_sane():
    data = bd.build()
    assert data["totals"]["tracks"] >= 36
    assert data["totals"]["modules"] >= 450
    assert data["totals"]["hours"] > 1000
    # every weekend within the documented budget ceiling
    over = {w: h for w, h in data["sprint"]["by_week"].items() if h > 10.5}
    assert not over, f"sprint weekend(s) over budget: {over}"


def test_parse_module_shape():
    m = bd.parse_module("slug | Title Here | 2.5 | a,b", "T00", 7)
    assert m["id"] == "T00-slug" and m["hours"] == 2.5
    assert m["tags"] == ["a", "b"] and m["order"] == 7
