"""Import the implementation under test.

Default: starter/  (should FAIL — that's the point)
--solution: solution/ (should PASS)
"""
import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def pytest_addoption(parser):
    parser.addoption("--solution", action="store_true",
                     help="run against solution/ instead of starter/")


def pytest_configure(config):
    which = "solution" if config.getoption("--solution") else "starter"
    path = ROOT / which / "pattern.py"
    spec = importlib.util.spec_from_file_location("pattern", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["pattern"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def P():
    return sys.modules["pattern"]


# ------------------------------------------------------------------ fixtures
SUDOKU_PUZZLE = [
    [5, 3, 0, 0, 7, 0, 0, 0, 0],
    [6, 0, 0, 1, 9, 5, 0, 0, 0],
    [0, 9, 8, 0, 0, 0, 0, 6, 0],
    [8, 0, 0, 0, 6, 0, 0, 0, 3],
    [4, 0, 0, 8, 0, 3, 0, 0, 1],
    [7, 0, 0, 0, 2, 0, 0, 0, 6],
    [0, 6, 0, 0, 0, 0, 2, 8, 0],
    [0, 0, 0, 4, 1, 9, 0, 0, 5],
    [0, 0, 0, 0, 8, 0, 0, 7, 9],
]

SUDOKU_SOLUTION = [
    [5, 3, 4, 6, 7, 8, 9, 1, 2],
    [6, 7, 2, 1, 9, 5, 3, 4, 8],
    [1, 9, 8, 3, 4, 2, 5, 6, 7],
    [8, 5, 9, 7, 6, 1, 4, 2, 3],
    [4, 2, 6, 8, 5, 3, 7, 9, 1],
    [7, 1, 3, 9, 2, 4, 8, 5, 6],
    [9, 6, 1, 5, 3, 7, 2, 8, 4],
    [2, 8, 7, 4, 1, 9, 6, 3, 5],
    [3, 4, 5, 2, 8, 6, 1, 7, 9],
]
