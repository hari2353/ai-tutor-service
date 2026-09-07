# Production notes — injection

## What you'd actually use

| Layer | Production answer |
|---|---|
| Queries | **prepared statements / parameterized queries** — `cursor.execute(sql, params)` (psycopg, SQLAlchemy `text(...).bindparams()`), JPA/Hibernate `setParameter`, `db.Query` + placeholders |
| ORMs | default-safe; the injection re-enters via `text()` fragments and `order_by(request.args['sort'])` |
| Escaping (last resort) | `psycopg2.extensions.escape_string` etc. — only where binding genuinely can't work (IDENTIFIERS) |
| Identifiers | allowlist, like your `order_by` — or a mapping from safe external names to internal ones |

## What the real engine adds over your mini-parser

- **A real parser with a hard boundary.** Your `query_unsafe` simulates what a real engine does when the *query string* arrives already-merged: the parser cannot tell your data from your syntax — they're the same bytes. A prepared statement sends the SQL *with placeholders* first (parsed once, plan cached), values separately over the protocol — there is no concatenation step to attack. That's why parameterization is a *structural* fix, not an escaping arms race.
- **Second-order injection is a real engine's blind spot too** — data stored safely (bound) is still hostile when a *later* query concatenates it. Your Lab 09 test is the canonical demo; production fix = audit every f-string/`%` SQL in the codebase (`bandit` S608, `sqlfluff`, semgrep `python.sqlalchemy.concurrent` rules).
- **LIKE wildcards** — binding alone is not enough for LIKE: the bound `%` is still a *pattern* wildcard. Real code must escape `%`/`_` in the value AND add `ESCAPE '\'` to the clause. Databases differ (MySQL default-escapes, Postgres doesn't) — a classic cross-db portability bug.
- **`information_schema` and UNION attacks** — real injection escalates past tautologies to `UNION SELECT table_name FROM information_schema.tables`. Your mini-DB stops at the WHERE clause; the defense lesson is identical.

## Failure table

| Symptom | Cause | Fix |
|---|---|---|
| Auth bypass works in prod | one concatenated WHERE in a legacy endpoint | parameterize; if truly impossible, escape + code-sign-off; add a CI rule |
| '%' search returns everything | bound LIKE value, unescaped wildcards | escape `%`/`_` server-side, `ESCAPE` clause |
| ORDER BY injection | identifier concatenated | allowlist columns + direction enum |
| Second-order detonation | stored value later concatenated | never concatenate, even "trusted" DB data |
| ORM "safe" but still injected | `text()` fragment with f-string, or `filter(**request.args)` | bindparams, explicit field allowlists (this is also Lab 10's mass-assignment fix) |
| Error messages leak schema | verbose 500s with SQL fragments | generic errors server-side; log details internally |

## Cost & latency

Prepared statements are *faster*, not slower: parse once, execute N (plan caching). The only real cost is developer discipline — every framework on earth supports binding; every injection finding is a place someone typed faster than they thought.

## The 3 questions an interviewer asks after you describe this

1. *"Why can't a bound parameter ever become syntax?"* — because the wire protocol separates them: SQL text arrives parsed, values arrive as typed data. There is no merge step, so there is no quote to break out of. Your `query_parameterized` is that separation in miniature.
2. *"When can't you parameterize, and what do you do?"* — identifiers: table/column names in ORDER BY / dynamic pivots. Allowlist (your `order_by`) or an indirection map. Never escape-and-hope.
3. *"Parameterized everywhere — are you safe?"* — no: LIKE wildcards still enumerate, second-order stored payloads wait for a concatenation elsewhere, and the ORM's `text()` is a loaded footgun. Parameterization is the floor, not the ceiling.
