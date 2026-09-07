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
    path = ROOT / which / "oracle_sql.py"
    spec = importlib.util.spec_from_file_location("oracle_sql", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["oracle_sql"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def O():
    return sys.modules["oracle_sql"]


EMP = [
    {"name": "Anna", "salary": 90000, "email": "anna@x.com"},
    {"name": "Bob", "salary": 80000, "email": ""},
    {"name": "Chen", "salary": 95000, "email": "chen@x.com"},
    {"name": "Dora", "salary": None, "email": "dora@x.com"},
    {"name": "Eli", "salary": 80000, "email": None},
    {"name": "Faye", "salary": 70000, "email": ""},
]
