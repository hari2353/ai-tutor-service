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
    path = ROOT / which / "oauth.py"
    spec = importlib.util.spec_from_file_location("oauth", path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["oauth"] = mod
    spec.loader.exec_module(mod)
    config._impl = which


@pytest.fixture
def R():
    return sys.modules["oauth"]


@pytest.fixture
def as_server(R):
    server = R.AuthorizationServer(clock=R.FakeClock(t=0.0))
    server.register_client("web-app", ["https://app.example/callback"],
                           ["openid", "profile", "email"])
    return server


@pytest.fixture
def client(R):
    return R.ClientApp("web-app", "https://app.example/callback")


def run_happy(R, server, client, scope="openid profile"):
    params = client.begin()
    redirect = server.authorize(scope=scope, code_challenge=params["code_challenge"],
                               code_challenge_method=params["code_challenge_method"],
                               state=params["state"], client_id=params["client_id"],
                               redirect_uri=params["redirect_uri"])
    qs = dict(pair.split("=") for pair in redirect.lstrip("?").split("&"))
    return client.complete(server, qs)
