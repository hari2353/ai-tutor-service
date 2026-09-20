import importlib.util
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent.parent


def pytest_addoption(parser):
    parser.addoption("--solution", action="store_true")


def pytest_configure(config):
    which = "solution" if config.getoption("--solution") else "starter"
    path = ROOT / which / "controller.py"
    spec = importlib.util.spec_from_file_location("controller", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["controller"] = mod
    spec.loader.exec_module(mod)


@pytest.fixture
def R():
    return sys.modules["controller"]
