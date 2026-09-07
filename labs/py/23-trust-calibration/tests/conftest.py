"""conftest — load starter/calibration.py by default, solution/ with --solution."""
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
    path = ROOT / which / "calibration.py"
    spec = importlib.util.spec_from_file_location("calibration", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["calibration"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def C():
    return sys.modules["calibration"]
