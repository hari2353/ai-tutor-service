# EXPECTED-FINDINGS.md — PY-01 answer key

**Score yourself only after writing your own report.** Each finding below lists the planted defect, its severity, the production failure mode, the minimal fix, and the curriculum module that teaches it.

Severities: **P0** ship-blocker (security / outage / data exposure) · **P1** must fix before merge (availability or correctness under realistic load) · **P2** should fix (latent bug, debt).

---

## Finding 1 — SQL built by string interpolation

- **Where:** `app/events.py`, `rows = client.query(f"SELECT ... WHERE tenant_id = '{tenant}' ORDER BY ts DESC LIMIT {limit}")`
- **Severity:** P0
- **Why it bites in prod:** `tenant` comes straight from the URL path. A tenant id like `x' OR 1=1 --` returns every tenant's event stream; `' ; DROP TABLE events; --`-class payloads or second-order payloads embedded in *previously stored* tenant names turn the metrics API into a full database shell. The old code used ClickHouse's `{param:String}` binding; this diff deleted it.
- **Fix:** restore parameterised binding (`{tenant:String}`, `{limit:Int32}` with `parameters={...}`), and add an allowlist regex on `tenant` at the route layer as defence in depth.
- **Module:** `T30-injection`

## Finding 2 — Blocking call inside `async def`

- **Where:** `app/events.py`, `rows = client.query(...)` (direct call; the diff removed `await run_in_threadpool(...)`)
- **Severity:** P0
- **Why it bites in prod:** `client.query` is a synchronous HTTP round trip to ClickHouse. Inside a coroutine it freezes the entire event loop: while one query runs for 800 ms, that worker serves *zero* requests — no health checks, no other tenants, keepalive timers pile up. With 4 workers, one slow ClickHouse query takes the whole fleet offline; load balancers mark instances dead and the "slow query" becomes a total outage.
- **Fix:** keep the offload (`run_in_threadpool` / executor) or move to a genuinely async ClickHouse client; bound it with the timeout from Finding 6's sibling pattern.
- **Module:** `T14-asyncio-fundamentals`

## Finding 3 — Hardcoded credential default

- **Where:** `app/settings.py`, `admin_password: str = "changeme"`
- **Severity:** P0
- **Why it bites in prod:** defaults win. The empty-string default at least failed closed-ish; `"changeme"` silently *succeeds*, so staging "works" without env setup, the value ships to prod baked into images, and now the ClickHouse admin password is in git history forever. Anyone with repo read access (or the leaked `.env`-less container) owns the database. Rotation can't help until you also scrub history.
- **Fix:** keep secrets env-only, fail fast when unset (`admin_password: SecretStr` + validator raising if missing); rotate the current password since it has been committed.
- **Module:** `T31-secrets-and-config`

## Finding 4 — No timeout on outbound HTTP call

- **Where:** `app/events.py`, `httpx.AsyncClient()` in `_fetch_profile` (the diff dropped `timeout=5.0`)
- **Severity:** P1
- **Why it bites in prod:** httpx default is to wait indefinitely. When `enricher.internal` hangs (deploy, GC pause, network partition), every request needing enrichment holds a connection open forever. FastAPI's task queue grows, memory climbs, upstream nginx starts returning 504s for *unrelated* routes sharing the worker pool. One dead dependency becomes your outage.
- **Fix:** always pass a timeout (`httpx.AsyncClient(timeout=httpx.Timeout(5.0))`), plus a retry budget/circuit breaker around the call.
- **Module:** `T21-resilience-catalogue`

## Finding 5 — Bare `except:` swallowing everything

- **Where:** `app/events.py`, `_fetch_profile`: `try: return resp.json() except: return {}`
- **Severity:** P1
- **Why it bites in prod:** bare except catches `KeyboardInterrupt`, `SystemExit`, and in async code `CancelledError` — so cancelled requests get "handled" instead of aborted, and shutdown hangs. It also silently converts every malformed-response bug into "profile is empty", which downstream code treats as legitimate data: dashboards show zeros for weeks before anyone notices. You debug with nothing — no logs, no tracebacks, ever.
- **Fix:** catch the narrowest exception you can actually handle (`except json.JSONDecodeError:` → log + return `{}`), let everything else propagate.
- **Module:** `T09-error-handling`

## Finding 6 — Unbounded pagination limit

- **Where:** `app/events.py`, `list_events`: `MAX_PAGE_SIZE = 200` clamp deleted
- **Severity:** P1
- **Why it bites in prod:** `?limit=` is user input. `limit=100000000` makes ClickHouse materialise a hundred-million-row result set per request: worker RAM spikes, ClickHouse gets hammered with scans, one curl becomes an OOM kill. Attackers do this for fun; well-meaning frontends do it by accident ("export all"). Cost per unauthenticated request should be bounded — that's the whole point of pagination.
- **Fix:** clamp server-side (`limit = min(max(limit, 1), MAX_PAGE_SIZE)`), return a cursor/next-page token instead of trusting client-supplied offsets.
- **Module:** `T20-backpressure-and-limits`

## Finding 7 — Shared dict cache with no synchronisation

- **Where:** `app/events.py`, module-level `_page_cache: dict[tuple[str, int], dict]`
- **Severity:** P2
- **Why it bites in prod:** check-then-act (`if cached is not None: return cached` … `_page_cache[key] = payload`) races across concurrent requests: duplicate expensive queries under contention (thundering herd) and, worse, the cached payload is a *mutable* dict handed to every caller — any handler or middleware mutating the response corrupts it for all future responses of that tenant. There is no TTL/eviction, so with unbounded `(tenant, limit)` keys the cache also grows forever (memory leak), and stale data lives until restart. With 4 uvicorn workers you get four divergent caches answering differently for the same key.
- **Fix:** `cachetools.TLRUCache` with maxsize+TTL behind a lock (or per-key single-flight); return deep copies or make payloads immutable; accept cross-worker divergence explicitly if you go Redis-less.
- **Module:** `T15-shared-state-concurrency`

## Finding 8 — Mutable default argument

- **Where:** `app/events.py`, `def merge_tags(new_tags: list[str], acc: list[str] = []) -> list[str]`
- **Severity:** P2
- **Why it bites in prod:** the default list is created once at function definition and shared across every call that omits `acc`. In this diff each page view calls `merge_tags(profile.get("tags", []))`, so tags *accumulate across requests and leak between tenants*: tenant B's dashboard shows tenant A's tags after a few hits. Classic Python footgun; in a multi-tenant endpoint it's quietly a data-isolation bug, which is why it's worth more than a style nit even though the mechanism is textbook.
- **Fix:** `acc=None` → create inside; or make the function pure (`return acc + [t for t in new_tags if t not in acc]`).
- **Module:** `T01-scoping-closures`

---

## Grading guide

| Outcome | Signal |
|---|---|
| Fewer than 3 P0s found (of 3 planted) | **NO HIRE signal** — cannot triage severity; injection/blocking-loop/secrets are table stakes |
| All 3 P0s + ≥ 5 total, severities within ±1 | HIRE signal |
| 8/8 found, correct severity, concrete prod scenarios | STRONG HIRE signal |
| 8/8 found but everything labelled P2, or report padded with style nits | LEAN HIRE at best — finding ≠ judging |
| Long list of nits (unused `logger`, missing type hints, naming), < 3 real defects | NO HIRE signal |

**Not defects — do not credit (padding traps):**
- Unused `logger.warning` import after the error-handling rewrite (style).
- `f"https://enricher.internal/tenants/{tenant}/profile"` URL building (path segment interpolation into an HTTPS URL is not SQL/command injection; encoding hardening is a nice-to-have, not a planted defect).
- Returning `dict(r)`-shaped payloads / response model absence (design taste).
- `merge_tags` O(n²) dedupe (performance trivia, not a defect).

**Close calls we do credit partially:**
- Noting the cache never invalidates (part of Finding 7) — fine as long as the race/mutation issue is named.
- Flagging `int` overflow-style DoS via `limit` together with missing upper bound (Finding 6) — counts once.
