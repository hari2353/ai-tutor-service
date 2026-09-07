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
    path = ROOT / which / "webatt.py"
    spec = importlib.util.spec_from_file_location("webatt", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["webatt"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def R():
    return sys.modules["webatt"]


@pytest.fixture
def internet(R):
    """A fake internet: resolver map + fetch map, no network."""
    hosts = {
        "example.com": "93.184.216.34",
        "cdn.example.com": "93.184.216.35",
        "redirect.example.com": "93.184.216.36",
        "internal.corp": "10.1.2.3",
        "localhost": "127.0.0.1",
        "127.0.0.1": "127.0.0.1",                 # raw-IP URLs resolve to themselves
        "169.254.169.254": "169.254.169.254",
        "93.184.216.34": "93.184.216.34",
        "metadata.google.internal": "169.254.169.254",
        "rebind.example.com": "127.0.0.1",
    }
    pages = {
        "https://example.com/": (200, "<h1>hello</h1>"),
        "https://example.com/redirect": (302, "http://internal.corp/admin"),
        "http://internal.corp/admin": (200, "INTERNAL SECRET"),
        "https://redirect.example.com/": (302, "https://example.com/"),
        "http://169.254.169.254/latest/meta-data/": (200, "AWS-SECRET"),
        "http://127.0.0.1:8080/": (200, "LOCAL SERVICE"),
    }
    resolver = lambda h: hosts[h]
    fetch = lambda u: pages.get(u, (404, "not found"))
    return R.UrlFetcher(resolver=resolver, fetch=fetch), hosts, pages
