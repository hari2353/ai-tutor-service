"""Lab 28 tests. No sleeps, no network, pure stdlib fixtures.

Sixteen tests, one behaviour each: every check must pass good code and
flag bad code, and the report gate must weigh blockers over warns.
"""

CLEAN_CODE = '''\
def add(a, b):
    """Add two numbers."""
    return a + b


def shout(text):
    """Uppercase and exclaim."""
    return text.upper() + "!"
'''

PEM_KEY = "-----BEGIN RSA PRIVATE KEY-----\nMIIEow...\n-----END RSA PRIVATE KEY-----"

STDLIST_APIS = {"append", "pop", "insert", "remove", "upper", "lower"}


def _ctx(known=("append", "get", "items", "upper", "close", "split", "strip", "join")):
    return {"known_apis": set(known)}


# ------------------------------------------------------------- no_secrets
def test_no_secrets_blocks_real_secrets(G):
    """AKIA id, password literal, PEM key — all blockers."""
    for code in ("KEY = 'AKIAIOSFODNN7EXAMPLE'\n",
                 'password = "hunter2"\n',
                 'CONFIG = {"password": "hunter2"}\n',
                 'password: "hunter2"\n',
                 PEM_KEY):
        r = G.no_secrets("x.py", code, _ctx())
        assert not r.passed, code
        assert r.severity == "blocker"


def test_no_secrets_passes_clean_code(G):
    """Variable passwords and the word inside a function name are fine."""
    for code in ("import os\npassword = os.environ['DB_PASSWORD']\n",
                 "def change_password(user, new):\n    pass\n"):
        r = G.no_secrets("x.py", code, _ctx())
        assert r.passed, code


# -------------------------------------------------------- error_handling
def test_bare_risky_calls_flagged(G):
    code = "def load(p):\n    f = open(p)\n    return f.read()\n"
    r = G.error_handling("load.py", code, _ctx())
    assert not r.passed and r.severity == "warn"
    r = G.error_handling("fetch.py", "def get(u):\n    r = requests.get(u)\n    return r\n", _ctx())
    assert not r.passed


def test_guarded_risky_calls_pass(G):
    with_code = 'def load(p):\n    with open(p) as f:\n        return f.read()\n'
    assert G.error_handling("load.py", with_code, _ctx()).passed
    try_code = ('import requests\n\ndef get(u):\n    try:\n        return requests.get(u)\n'
                '    except Exception:\n        return None\n')
    assert G.error_handling("fetch.py", try_code, _ctx()).passed


# ------------------------------------------------------ no_magic_numbers
def test_magic_number_flagged(G):
    r = G.no_magic_numbers("api.py", "def wait():\n    if retries > 1000:\n        return None\n", _ctx())
    assert not r.passed and r.severity == "warn"


def test_named_constants_pass(G):
    r = G.no_magic_numbers("api.py", "MAX_RETRIES = 1000\nTIMEOUT = 2.5\n", _ctx())
    assert r.passed
    r = G.no_magic_numbers("api.py", "def f(x):\n    return x + 999\n", _ctx())
    assert r.passed


# ---------------------------------------------------------------- naming
def test_naming(G):
    r = G.naming("util.py", "def doSomething(x):\n    return x\n", _ctx())
    assert not r.passed and r.severity == "warn"
    r = G.naming("util.py", "class my_class:\n    pass\n", _ctx())
    assert not r.passed
    r = G.naming("util.py", "class GoodThing:\n    def do_it(self):\n        return 1\n", _ctx())
    assert r.passed


# ----------------------------------------------------------- has_docstrings
def test_docstring_rules(G):
    r = G.has_docstrings("util.py", "def compute(x):\n    return x * 2\n", _ctx())
    assert not r.passed and r.severity == "warn"
    r = G.has_docstrings("tests/test_x.py", "def test_add():\n    assert 1 + 1 == 2\n", _ctx())
    assert r.passed                        # test_ functions exempt
    r = G.has_docstrings("util.py", 'def compute(x):\n    """Double."""\n    return x * 2\n', _ctx())
    assert r.passed


# --------------------------------------------------------- complexity_gate
def test_long_function_flagged(G):
    body = "\n".join("    x = %d" % i for i in range(40))
    r = G.complexity_gate("big.py", "def long_one():\n" + body + "\n    return x\n", _ctx())
    assert not r.passed and r.severity == "warn"


def test_too_many_returns_flagged(G):
    code = ("def many(x):\n"
            + "".join("    if x == %d:\n        return %d\n" % (i, i) for i in range(6))
            + "    return None\n")
    assert not G.complexity_gate("big.py", code, _ctx()).passed
    short = "def one(x):\n    if x:\n        return 1\n    return 0\n"
    assert G.complexity_gate("big.py", short, _ctx()).passed


# ------------------------------------------------------- hallucinated_api
def test_fabricated_api_blocked(G):
    """THE agent failure mode: list.push_back() against a stdlib allowlist."""
    code = "def f(xs):\n    xs.push_back(1)\n    return xs\n"
    r = G.hallucinated_api("x.py", code, {"known_apis": STDLIST_APIS})
    assert not r.passed and r.severity == "blocker"


def test_known_apis_pass(G):
    code = "def f(xs):\n    xs.append(1)\n    return xs.pop()\n"
    r = G.hallucinated_api("x.py", code, {"known_apis": {"append", "pop"}})
    assert r.passed and r.severity == "ok"


# ------------------------------------------------------------- has_tests
def test_has_tests_enforces_diff_rule(G):
    """Source-only changes fail; tests shipped (or docs-only) pass."""
    only_source = {"service.py": CLEAN_CODE, "helpers.py": CLEAN_CODE}
    r = G.has_tests("changeset", "", {"files": only_source})
    assert not r.passed and r.severity == "blocker"

    with_tests = {"service.py": CLEAN_CODE,
                  "tests/test_service.py": "def test_add():\n    assert 1 + 1 == 2\n"}
    assert G.has_tests("changeset", "", {"files": with_tests}).passed

    docs_only = {"README.md": "hi", "docs/arch.md": "words"}
    assert G.has_tests("changeset", "", {"files": docs_only}).passed

    fake_test_file = {"service.py": CLEAN_CODE, "tests/helpers.py": CLEAN_CODE}
    assert not G.has_tests("changeset", "", {"files": fake_test_file}).passed


# ----------------------------------------------------------- run_gauntlet
def test_blockers_fail_the_gauntlet(G):
    files = {"deploy.py": "KEY = 'AKIAIOSFODNN7EXAMPLE'\n"}
    report = G.run_gauntlet(files, _ctx())
    assert report["passed"] is False
    kinds = {(f["file"], f["check"]) for f in report["findings"]}
    assert ("deploy.py", "no_secrets") in kinds
    assert all(set(f) == {"file", "check", "severity", "note"} for f in report["findings"])


def test_warns_collect_but_do_not_fail(G):
    code = "def compute(x):\n    return x + 5000\n"          # no docstring + magic number
    files = {"util.py": code,
             "tests/test_util.py": "def test_compute():\n    assert True\n"}
    report = G.run_gauntlet(files, _ctx())
    assert report["passed"] is True
    names = [f["check"] for f in report["findings"]]
    assert "no_magic_numbers" in names and "has_docstrings" in names
    assert all(f["severity"] != "blocker" for f in report["findings"])


def test_clean_file_set_passes(G):
    files = {"service.py": CLEAN_CODE,
             "tests/test_service.py": "def test_add():\n    assert add(1, 2) == 3\n"}
    report = G.run_gauntlet(files, _ctx())
    assert report["passed"] is True
    assert report["findings"] == []
