# Lab 09: The Injection Lab — Why Parameterization Wins

**Track:** T30 Auth & Application Security · **Time:** 2h · **XP:** 50
**Module:** `T30-injection`

**You will build:** a tiny in-memory "database" with a `query_unsafe(sql)` that string-concatenates user input and naively evaluates the WHERE clause — exploitable by `' OR '1'='1` tautologies, second-order payloads, and LIKE wildcards — next to a `query_parameterized(col, val)` that cannot be escaped by any of them, plus the honest exception: ORDER BY can't be parameterized, so it gets an allowlist.

**You will be able to answer:** *"Show me an SQL injection end-to-end — and why do parameterized queries make it structurally impossible rather than just harder?"*

## Setup

```bash
cd labs/py/09-injection-lab
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest
```

## The spec

1. **`query_unsafe(sql)`** — parse `SELECT * FROM users WHERE <expr>`; evaluate the expr with a deliberately literal mini-parser: `col='value'` equality, `OR` splits disjuncts, quoted-literal comparisons (`'1'='1`) evaluate as plain string equality — the tautology. A trailing dangling quote-remainder and `--` comments (outside quotes) are consumed like a real engine would. **It must be exploitable — that is the demonstration.**
2. **`query_parameterized(where_col, where_val)`** — exact string equality against an allowlisted column; the value is data forever, never syntax. Unknown column → `ValueError`.
3. **`query_like_unsafe(pattern)` / `query_like_parameterized(pattern)`** — SQL LIKE semantics (`%` = any run, `_` = any single char). Unsafe: the user's `%` is a live wildcard — input `%` dumps the table. Parameterized: `%`, `_`, `\` are escaped to literals *first*.
4. **`order_by(column, descending)`** — column names are syntax, not values, so they can't be bound — the fix is an allowlist; injected column names raise `ValueError`.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Blind boolean injection** — build `exists(username, password)` and extract bob's password one character at a time using only `query_unsafe` and response-size differences.
2. **NoSQL operator injection** — a dict-based filter where `{"$ne": None}` in a JSON body becomes an operator; fix with explicit type validation.
3. **ORDER BY in the real world** — allowlist + direction validation + a test proving `id DESC--` is refused.
