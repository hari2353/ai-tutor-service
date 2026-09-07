"""conftest — load starter/nanogpt.py by default, solution/ with --solution."""
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
    path = ROOT / which / "nanogpt.py"
    spec = importlib.util.spec_from_file_location("nanogpt", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["nanogpt"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def G():
    return sys.modules["nanogpt"]


@pytest.fixture(scope="session")
def tiny_seed():
    import torch
    torch.manual_seed(0)
    return 0
