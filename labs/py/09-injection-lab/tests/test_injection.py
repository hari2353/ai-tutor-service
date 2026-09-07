"""Lab 09 tests: the auth bypass, second-order, LIKE wildcards, ORDER BY allowlist."""
import pytest

BYPASS = "' OR '1'='1"


# ------------------------------------------------------------------ honest baseline
def test_unsafe_ordinary_query_works(R, db):
    """The trap: the vulnerable path works FINE for honest input. That's why
    it ships."""
    rows = db.query_unsafe("SELECT * FROM users WHERE username = 'alice'")
    assert len(rows) == 1 and rows[0]["username"] == "alice"


def test_parameterized_ordinary_query_works(R, db):
    rows = db.query_parameterized("username", "alice")
    assert len(rows) == 1 and rows[0]["username"] == "alice"


# ------------------------------------------------------------------ auth bypass
def test_unsafe_auth_bypass_via_tautology(R, db):
    """THE classic: ' OR '1'='1 appended to the password turns the WHERE clause
    into 'x'='x' OR '1'='1' — always true — and the query returns everything."""
    sql = "SELECT * FROM users WHERE username = 'admin' AND password = '" + BYPASS
    rows = db.query_unsafe(sql)
    assert len(rows) >= 3, "tautology did not match all rows — bypass failed"


def test_parameterized_blocks_the_tautology(R, db):
    """Same payload, parameterized: it's just a (nonexistent) password string."""
    rows = db.query_parameterized("password", BYPASS)
    assert rows == [], "payload matched rows — parameterization is broken"
    # and every row remains findable only by its exact value
    assert db.query_parameterized("username", BYPASS) == []


def test_parameterized_returns_exact_matches_only(R, db):
    for user in ("admin", "alice", "bob"):
        rows = db.query_parameterized("username", user)
        assert [r["username"] for r in rows] == [user]


# ------------------------------------------------------------------ second-order
def test_second_order_injection_via_stored_value(R, db):
    """Step 1 (correctly parameterized): a hostile username is stored VERBATIM.
    Step 2 (later, elsewhere): a DIFFERENT query concatenates the stored value
    into its WHERE clause — and the payload detonates there."""
    hostile = "admin'--"
    db2 = R.MiniDB()
    db2.users.append({"id": 4, "username": hostile, "password": "x",
                      "bio": "", "is_admin": False})   # stored safely...
    sql = "SELECT * FROM users WHERE username = '" + db2.users[3]["username"] + "'"
    rows = db2.query_unsafe(sql)                       # ...detonates here
    # 'admin'--' comments out the closing quote; 'admin' matches the real admin
    assert any(r["username"] == "admin" and r["is_admin"] for r in rows), \
        "second-order payload did not reach the admin row"
    # the parameterized path treats the stored value as inert data
    assert [r["username"] for r in db2.query_parameterized("username", hostile)] \
        == [hostile]


# ------------------------------------------------------------------ LIKE wildcards
def test_like_wildcard_injection_matches_all(R, db):
    """LIKE '%<input>%': % and _ are wildcards. Input '%' matches EVERYTHING —
    an enumeration primitive (and a performance footgun)."""
    rows = db.query_like_unsafe("%")
    assert len(rows) == 3, "wildcard did not leak the whole table"


def test_like_underscore_wildcard(R, db):
    """Underscore = exactly one char, wrapped in %...% — 'a_' matches any name
    CONTAINING 'a' followed by one char: admin, alice both qualify; bob doesn't."""
    names = {r["username"] for r in db.query_like_unsafe("a_")}
    assert "admin" in names and "alice" in names
    assert "bob" not in names
    # escaped path: a literal underscore only
    db.users.append({"id": 4, "username": "a_b", "password": "x",
                     "bio": "", "is_admin": False})
    assert [r["username"] for r in db.query_like_parameterized("a_")] == ["a_b"]


def test_parameterized_like_escapes_wildcards(R, db):
    """Same '%', but bound: escaped to a LITERAL percent sign — matches nothing."""
    assert db.query_like_parameterized("%") == []
    assert db.query_like_parameterized("_") == []
    # literal content still matches
    assert [r["username"] for r in db.query_like_parameterized("li")] == ["alice"]


def test_parameterized_like_with_real_percent_content(R, db):
    """A user whose name genuinely contains % must still be findable —
    add one, then match with the escaped path."""
    db.users.append({"id": 4, "username": "50%off", "password": "x",
                     "bio": "", "is_admin": False})
    assert [r["username"] for r in db.query_like_parameterized("%o")] == ["50%off"]


# ------------------------------------------------------------------ ORDER BY
def test_order_by_allowlist_sorts(R, db):
    asc = db.order_by("username")
    assert [r["username"] for r in asc] == ["admin", "alice", "bob"]
    desc = db.order_by("username", descending=True)
    assert [r["username"] for r in desc] == ["bob", "alice", "admin"]
    ids = db.order_by("id", descending=True)
    assert [r["id"] for r in ids] == [3, 2, 1]


def test_order_by_injected_column_rejected(R, db):
    """ORDER BY can't be parameterized (it's syntax, not a value) — the fix is
    an allowlist. Injected column names are refused."""
    with pytest.raises(ValueError):
        db.order_by("id; DROP TABLE users")
    with pytest.raises(ValueError):
        db.order_by("(SELECT password FROM users)")
    with pytest.raises(ValueError):
        db.order_by("id DESC--")


# ------------------------------------------------------------------ misc
def test_unsafe_rejects_unknown_shapes(R, db):
    with pytest.raises(ValueError):
        db.query_unsafe("DROP TABLE users")


def test_fake_clock(R):
    c = R.FakeClock(t=10.0)
    assert c.now() == 10.0
    c.advance(5.0)
    assert c.now() == 15.0
