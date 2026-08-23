#!/usr/bin/env python3
"""Integration tests — the whole pipeline, end to end, as subprocesses.

These are the "does the MACHINE work" layer: build_data regenerates every
aggregate from fragments; the review gate passes over all written modules;
the node DOM/SM-2 suites pass against freshly built data; the security gate
exits clean. Skips (never silent passes) when a tool is missing."""
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
PY = sys.executable


def _run(cmd, timeout=300):
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def test_build_data_rebuilds_all_aggregates():
    r = _run([PY, str(ROOT / "app" / "build_data.py")])
    assert r.returncode == 0, r.stdout + r.stderr
    assert "OK" in r.stdout
    # aggregates actually rewritten and parseable
    for name in ("curriculum", "flashcards", "drills", "problems"):
        data = json.loads((ROOT / "app" / "data" / f"{name}.json").read_text(encoding="utf-8"))
        assert data, name
    curriculum = json.loads((ROOT / "app" / "data" / "curriculum.json").read_text(encoding="utf-8"))
    assert curriculum["totals"]["modules"] >= 450
    # CONTENT-STATUS regenerated and consistent with build output
    status = (ROOT / "CONTENT-STATUS.md").read_text(encoding="utf-8")
    assert "modules written" in status


def test_review_gate_zero_failures():
    r = _run([PY, str(ROOT / "app" / "tests" / "review_gate.py")], timeout=600)
    assert r.returncode == 0, r.stdout[-2000:]
    assert "0 fail" in r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_dom_suite_against_built_data():
    r = _run(["node", str(ROOT / "app" / "tests" / "dom.test.js"), str(ROOT)])
    assert r.returncode == 0, r.stdout[-2000:]
    assert "passed" in r.stdout


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_sm2_scheduler_suite():
    r = _run(["node", str(ROOT / "app" / "tests" / "sm2.test.js"), str(ROOT)])
    assert r.returncode == 0, r.stdout[-2000:]


def test_security_gate_clean():
    r = _run([PY, str(ROOT / "scripts" / "security_check.py")])
    assert r.returncode == 0, r.stdout[-2000:]
    assert "hard failures: 0" in r.stdout

