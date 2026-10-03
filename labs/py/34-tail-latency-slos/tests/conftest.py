"""Import starter by default and solution when --solution is supplied."""
import importlib.util
import pathlib
import sys

import pytest


ROOT = pathlib.Path(__file__).resolve().parent.parent


def pytest_addoption(parser):
    parser.addoption("--solution", action="store_true")


def pytest_configure(config):
    which = "solution" if config.getoption("--solution") else "starter"
    path = ROOT / which / "latency_slos.py"
    spec = importlib.util.spec_from_file_location("latency_slos", path)
    module = importlib.util.module_from_spec(spec)
    sys.modules["latency_slos"] = module
    spec.loader.exec_module(module)


@pytest.fixture
def R():
    return sys.modules["latency_slos"]
