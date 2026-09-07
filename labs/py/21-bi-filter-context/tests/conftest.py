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
    path = ROOT / which / "bi_model.py"
    spec = importlib.util.spec_from_file_location("bi_model", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["bi_model"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def B():
    return sys.modules["bi_model"]


@pytest.fixture
def model(B):
    """The canonical star: 1 fact (Sales) x 3 dimensions.

    Sales (fact): product, store, date keys + amount
      row0: P1 S1 D1 100
      row1: P1 S2 D1  50
      row2: P2 S1 D1  70
      row3: P1 S1 D2  30
      row4: P2 S2 D2  60
    Product: P1=Laptop P2=Mouse ; Store: S1=Hyd S2=Del ; Date: D1=D1
    """
    m = B.Model(relations=[
        ("Product", "pid", "Sales", "product"),
        ("Store", "sid", "Sales", "store"),
        ("Date", "did", "Sales", "date"),
    ])
    m.add_table("Sales", [
        {"product": "P1", "store": "S1", "date": "D1", "amount": 100},
        {"product": "P1", "store": "S2", "date": "D1", "amount": 50},
        {"product": "P2", "store": "S1", "date": "D1", "amount": 70},
        {"product": "P1", "store": "S1", "date": "D2", "amount": 30},
        {"product": "P2", "store": "S2", "date": "D2", "amount": 60},
    ])
    m.add_table("Product", [
        {"pid": "P1", "name": "Laptop"},
        {"pid": "P2", "name": "Mouse"},
    ])
    m.add_table("Store", [
        {"sid": "S1", "city": "Hyderabad"},
        {"sid": "S2", "city": "Delhi"},
    ])
    m.add_table("Date", [
        {"did": "D1", "label": "Q1"},
        {"did": "D2", "label": "Q2"},
    ])
    return m


TOTAL = lambda rows: sum(r["amount"] for r in rows)
