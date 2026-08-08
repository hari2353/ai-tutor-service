"""Import the implementation under test.

Default: starter/  (should FAIL -- that's the point)
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
    path = ROOT / which / "hnsw.py"
    spec = importlib.util.spec_from_file_location("hnsw", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["hnsw"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def H():
    return sys.modules["hnsw"]
