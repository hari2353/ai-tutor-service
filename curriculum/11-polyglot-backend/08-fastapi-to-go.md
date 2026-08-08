# Porting FastAPI → Go: The Rewrite, Benchmarked, and When It's Wrong

> **Track:** T11 Polyglot Backend · **Time:** 3h · **Prereqs:** T11-fastapi-deep, T11-go-core · **Updated:** 2026-08-03
> **Module id:** `T11-fastapi-to-go` · **Tags:** go, critical

## The 30-second version

Controlled 2026 benchmarks on comparable hardware put a Go framework (Fiber/Gin-class) at roughly **142,000 RPS** for a JSON CRUD workload against FastAPI's roughly **38,000 RPS** — a real, reproducible ~3.7x gap that widens further under sustained load, where Go can deliver up to **7x better tail latency** than FastAPI at high stress, because Go's goroutines get genuine multi-core parallelism from a single process while a Python process is capped by the GIL to one core of actual compute at a time (`T16-io-models`/`T11-go-core` cover the mechanics). That gap is real, and it is also almost never the reason a specific service is slow: the overwhelming majority of "FastAPI is too slow" complaints trace back to a synchronous ORM call inside an `async def` handler stalling the event loop, missing database indexes, N+1 queries, or missing caching (`T11-fastapi-deep` covers exactly this failure class) — fixable in Python, in hours, for free, versus a multi-week rewrite. The honest rule, cited directly by practitioners who've done this: **rewrite a specific hot endpoint in Go only after profiling proves the framework itself — not the database, not the ORM, not a missing cache — is the actual bottleneck**, which in practice means the workload has already been tuned in Python and is still hitting a wall somewhere around 50,000+ RPS per instance or a genuinely CPU-bound (not I/O-bound) hot path Python's GIL structurally can't parallelize within one process. A backend peaking at 8,000 RPS runs equally well on FastAPI or Go; one peaking at 80,000 RPS does not, and that threshold — not "Go is a faster language" — is the actual decision criterion. When a rewrite is justified, it's a **strangler-fig migration of one endpoint or service at a time** behind a stable API contract, with real production traffic shadowed and compared before cutover, not a big-bang full-service rewrite — and Reddit's real Python-to-Go migration (halving critical write-path latency) and comparable case studies (Docker image size dropping from 1GB+ to under 200MB, memory cost falling) are cited specifically as targeted, measured, one-service-at-a-time efforts, not wholesale rewrites done for prestige.

## Why this gets asked

Because "should we rewrite this in Go" is a real, recurring, expensive decision that Python-primary teams face constantly as they scale, and it's one of the clearest places to distinguish an engineer chasing a resume line from one making a defensible engineering call — the interviewer has almost certainly either greenlit a rewrite that didn't pay back (six months of engineering time for a service that turned out to be database-bound the whole time) or, less often, greenlit one that genuinely saved the company real infrastructure cost and wants to hear you reason about the difference. Given that the target candidate's actual resume includes a documented Java→Python migration and production LLM-serving experience, this question is specifically testing whether the migration reasoning generalizes — do you know how to *prove* a rewrite is warranted before committing to it, and do you know the actual mechanical reason (GIL-bound single-core compute, not "Python is slow") behind the performance gap, versus reciting a vague "Go is faster" without being able to say faster at what, under what load, and why.

---

## Lineage: past → present → future

**What came before.** Python web services in the pre-async era (Django, Flask, pre-2019 stacks) ran WSGI-based, synchronous, thread-or-process-per-request, and the performance conversation was almost entirely about horizontal scaling (more workers, more processes) rather than per-process efficiency, because a single Python process was never going to serve high concurrency efficiently regardless of framework — the GIL made that a structural ceiling, not a tuning problem. FastAPI (2018) and ASGI changed the *I/O-bound* half of this story dramatically (covered in `T11-fastapi-deep`): async handlers let a single process handle far more concurrent I/O-bound requests than a thread-per-request WSGI process could, closing much of the gap that used to motivate an automatic "just rewrite it in a compiled language" reflex. What async *didn't* change is the GIL's cap on genuine CPU-bound parallelism within one process — a CPU-heavy request handler in FastAPI still runs on one core at a time regardless of how many async workers or `await` points surround it, because the GIL serializes actual bytecode execution across threads in a single interpreter process.

**Where it stands now.** The 2026 benchmark reality, cited across multiple current sources, is a real and consistent gap for high-throughput JSON-CRUD-style workloads — roughly 3.7x in raw RPS (Go ~142K vs FastAPI ~38K in one controlled comparison) and up to 7x in tail latency under sustained stress — but the community consensus, from teams that have actually done these migrations, has hardened around measurement-first discipline specifically *because* enough teams got burned rewriting services that turned out to be bottlenecked elsewhere. The repeated, specific finding across multiple 2025-2026 postmortems: most "FastAPI is slow" complaints are actually a synchronous call blocking the event loop, an N+1 query, a missing index, or no caching layer — all fixable for a fraction of a rewrite's cost, and all things that would make the *Go* rewrite disappointingly unimpressive too, since none of them are Python-specific problems. The live, genuinely debated line is where the RPS/latency threshold sits that justifies a rewrite — cited guidance clusters around roughly 50,000+ RPS on a single, already-tuned endpoint as the point where Python's per-core ceiling becomes the actual constraint rather than a symptom of something else being wrong.

**Where it's heading.** The gap is likely to narrow somewhat but not close: Python's free-threaded build (PEP 703, removing the GIL as an experimental/opt-in mode, under active development across recent CPython releases) is a genuine, multi-year effort to remove exactly the structural ceiling described here, but it remains experimental and not yet the default in mainstream production Python as of 2026 — treat "the GIL problem will just go away" as a real but not-yet-arrived direction, not current reality. Separately, the *decision framework* itself (measure first, rewrite the specific bottlenecked component via strangler-fig migration, not the whole service) is a stable, hardening consensus unlikely to reverse — expect continued emphasis on this discipline as more teams publish rewrite postmortems, both successful and wasted, and as tooling for endpoint-level production profiling (distinguishing "the framework" from "the database" from "the ORM" as the actual bottleneck) keeps maturing on both sides.

---

## Mental model

```
THE ACTUAL DECISION TREE (not "is Go faster" — it always is, for CPU work):

  "This service feels slow" ──▶ PROFILE FIRST, before any rewrite conversation
         │
         ▼
  Is it a synchronous call blocking      YES ──▶ FIX IN PYTHON (async client,
  the event loop? (T11-fastapi-deep)              run_in_threadpool) — hours,
         │ NO                                      not weeks, done.
         ▼
  Is it N+1 queries / missing indexes /  YES ──▶ FIX IN PYTHON (query opt,
  missing caching?                                caching layer) — hours to
         │ NO                                      days, done.
         ▼
  Is it genuinely CPU-bound compute      YES ──▶ Consider: multiprocessing
  (not I/O) hitting the GIL ceiling               in Python first (cheaper),
  WITHIN one process?                             THEN Go if still insufficient
         │ NO
         ▼
  Is the ALREADY-TUNED endpoint still    YES ──▶ Go rewrite is DEFENSIBLE —
  hitting ~50K+ RPS or a hard latency             for THIS endpoint/service,
  wall Python can't clear per-process?            not the whole backend.
         │ NO
         ▼
  Don't rewrite. Most services never reach this threshold.

WHY THE GAP EXISTS MECHANICALLY (not "Python is slow" — it's GIL + interpreter):

  PYTHON PROCESS                          GO PROCESS
  ┌─────────────────────────┐            ┌─────────────────────────┐
  │ GIL: only ONE thread     │            │ M:N goroutines across   │
  │ executing Python         │            │ ALL logical CPUs         │
  │ bytecode at a time,      │            │ simultaneously — genuine │
  │ regardless of thread     │            │ parallel compute, no     │
  │ count. Async helps I/O   │            │ global interpreter lock  │
  │ CONCURRENCY, not CPU     │            │ at all.                  │
  │ PARALLELISM.             │            │                           │
  │ Need N worker PROCESSES  │            │ ONE process saturates    │
  │ (uvicorn --workers N)    │            │ all cores natively.      │
  │ to use N cores — each    │            │                           │
  │ with its OWN memory      │            │                           │
  │ overhead, no shared      │            │                           │
  │ in-process cache.        │            │                           │
  └─────────────────────────┘            └─────────────────────────┘

STRANGLER-FIG MIGRATION (the actual mechanism for a justified rewrite):

  [Python monolith] ──▶ [Proxy/Gateway] ──▶ routes ONE endpoint to [Go service]
                                          ──▶ everything else still Python
  Shadow traffic first (compare responses, don't cut over blind) → gradually
  shift real traffic → decommission the Python path for THAT endpoint only
  → repeat for the NEXT proven-bottlenecked endpoint, if any.
```

---

## How it actually works

### The GIL, mechanically, and why async doesn't fix CPU-bound work

Python's Global Interpreter Lock ensures only one thread executes Python bytecode at any instant within a single interpreter process — a design choice from CPython's early history that made single-threaded performance and C-extension integration simpler at the direct cost of true multi-core parallelism for pure-Python code. `asyncio`/FastAPI's async model works *around* this for I/O-bound work by having one thread cooperatively switch between many pending I/O-bound coroutines while waiting on the OS — it does not add parallelism, it adds concurrency: you can have thousands of requests "in flight" but the CPU work in any given request still executes serially with every other request's CPU work on that one process, because the GIL is held during actual bytecode execution regardless of whether that execution happens inside an `async def` or not. This is the precise, checkable reason why a genuinely CPU-heavy handler (image processing, a hot serialization loop, a hand-rolled parsing routine) gets **zero** benefit from being `async def` — the GIL still serializes it against every other request on that process, and the fix within Python is horizontal (`uvicorn --workers N`, spinning up N separate OS processes, each with its own GIL and its own full copy of loaded memory) rather than a language-level fix.

```bash
# Python's standard answer to CPU-bound scaling: more PROCESSES, not more async
uvicorn app:app --workers 8   # 8 separate processes, 8x memory footprint of
                               # loaded modules/models, NO shared in-process cache
                               # between them (Redis or similar needed for that)
```

Go has no equivalent lock — goroutines scheduled M:N onto `GOMAXPROCS` OS threads (`T11-go-core`) genuinely run in parallel across cores within a single process, with a single shared memory space and no per-process duplication cost. This is the actual mechanism behind the benchmark gap, not a vague "compiled languages are faster" claim — it is specifically about parallel compute capacity per process, which is why the gap is largest for CPU-bound or high-fan-out workloads and comparatively much smaller for I/O-bound workloads where FastAPI's async model already extracts most of the achievable concurrency.

### The benchmark numbers, and what they actually measure

Cited 2026 controlled benchmarks for a JSON CRUD workload on comparable hardware: Go (Fiber/Gin-class framework) at roughly **142,000 RPS**, FastAPI at roughly **38,000 RPS**, Express 5 (Node.js) at roughly **19,000 RPS** — Go leading by a wide margin, FastAPI notably ahead of Express in this specific comparison. Under sustained high-stress load specifically, Go delivers up to **7x better tail latency** than FastAPI, while under *moderate* load the two perform comparably — the gap is load-dependent, not a fixed multiplier that applies identically at every traffic level, which is precisely why "our load test shows Go is 3.7x faster" doesn't automatically mean your specific production traffic pattern experiences that same multiplier if your actual peak load never approaches the point where the gap opens up.

**What these numbers don't tell you**: they measure raw framework/runtime throughput for a synthetic CRUD workload with no real database, no real network calls to other services, and no real business logic — in other words, exactly the conditions under which framework overhead is the *entire* cost, which is essentially never true for a real production service where a database round trip, a downstream API call, or serialization of a non-trivial payload dominates total latency regardless of which language issues the query. This is the single most important caveat to state unprompted when discussing these numbers in an interview: a benchmark measuring pure framework overhead systematically overstates the real-world impact of a language/framework choice for any service where I/O, not framework dispatch overhead, is the dominant cost — which is most services.

### Diagnosing the actual bottleneck before considering a rewrite

The repeated, cited finding across multiple postmortems: teams that skip this step and rewrite anyway frequently discover the Go rewrite is *also* unimpressive, because the bottleneck (a slow query, a missing index, a synchronous call) was never framework-dependent in the first place.

```python
# untested sketch — the profiling checklist BEFORE proposing a Go rewrite
# 1. Is a blocking call stalling the event loop? (T11-fastapi-deep Q6)
#    Symptom: throughput plateaus/collapses under load, CPU stays LOW/idle.
#    grep for sync HTTP clients, blocking DB drivers, time.sleep-equivalent
#    calls inside async def handlers.

# 2. N+1 queries / missing indexes / missing caching?
#    Turn on SQL query logging under realistic load; count queries per
#    request. A "list orders" endpoint issuing 500+ near-identical queries
#    is a database problem, not a language problem — Go with the same
#    query pattern against the same schema is EQUALLY slow.

# 3. Is CPU time (not wall-clock time, which includes I/O wait) actually
#    the dominant cost? py-spy / cProfile under realistic load — if CPU
#    utilization per request is low and wall-clock latency is high, the
#    bottleneck is I/O WAIT, not compute, and Go's parallelism advantage
#    is largely irrelevant (Go's async I/O model doesn't wait faster,
#    it just uses cheaper threads to wait — see T16-io-models).

# 4. ONLY after 1-3 are ruled out: is this endpoint's CPU-bound hot path
#    genuinely saturating one core, and would horizontal scaling
#    (more uvicorn workers, more pods) already solve it more cheaply
#    than a rewrite, given Python's per-process memory cost?
```

The specific, cited rule of thumb for when the fourth branch actually applies: an endpoint that's already been tuned (blocking calls fixed, N+1 fixed, caching added) and is *still* hitting roughly **50,000+ RPS** or a hard tail-latency wall that additional Python worker processes can't clear cost-effectively (each additional process duplicating memory, with no free win from more cores past what the workload's I/O-vs-CPU mix can actually use) is where a targeted Go rewrite becomes defensible — not a blanket threshold, but the order of magnitude cited by teams who've actually made this call correctly.

### The strangler-fig migration: how a justified rewrite is actually executed

```
Client ──▶ [API Gateway / reverse proxy] ──┬──▶ /orders/*     → Python (unchanged)
                                             ├──▶ /search       → Go (NEW, migrated)
                                             └──▶ /everything-else → Python (unchanged)
```

A justified rewrite is never "rewrite the whole backend in Go" — it's migrating **one proven-bottlenecked endpoint or service at a time**, behind a stable contract the gateway/proxy routes on, with three concrete phases: **shadow** (the new Go service receives a copy of real production traffic and its responses are compared against the existing Python service's responses for correctness, with zero user-facing risk, since the Python response is still what's actually returned), **gradual cutover** (a small percentage of real traffic routes to the Go service, monitored for correctness and the actual measured latency/throughput improvement, ramped up incrementally), and **decommission** (once the Go service has proven itself at full traffic for a meaningful period, the Python code path for that specific endpoint is removed — not the whole Python service, just that endpoint). This is the concrete mechanism behind the cited real case studies: Reddit's Comments/Accounts/Posts/Subreddits migration from a Python monolith to Go happened as discrete, individually-justified service extractions, not one atomic rewrite, and the Docker-image-size and memory-cost improvements cited in comparable case studies were measured per migrated service, not projected across an entire backend that was never fully rewritten.

### What actually changes about the API contract during a port

Porting a FastAPI service's *behavior* faithfully to Go is where most of the real engineering risk lives, not the raw language translation — Pydantic's validation error shape (422 with a specific error-list JSON structure, `T11-fastapi-deep`), FastAPI's automatic OpenAPI generation, and dependency-injection-based test overrides all need Go equivalents that preserve the exact wire contract existing clients depend on:

```go
// Go equivalent needs to preserve FastAPI's exact validation error SHAPE
// if any existing client parses it, not just "return a 4xx somehow"
type ValidationError struct {
    Detail []FieldError `json:"detail"`
}
type FieldError struct {
    Loc  []string `json:"loc"`
    Msg  string   `json:"msg"`
    Type string   `json:"type"`
}
```

A rewrite that changes the wire contract (different error shape, different field naming convention — Go's idiomatic `CamelCase` JSON tags versus Python's conventional `snake_case`) breaks every existing client silently unless the contract is explicitly preserved or every consumer is coordinated through a breaking-change process — this is frequently the actual source of a rewrite's real cost and risk, underestimated relative to the "just rewrite the handlers" framing a rewrite proposal often uses.

---

## Build it from scratch

A minimal side-by-side comparison worth being able to describe and, ideally, run: the same CRUD endpoint in FastAPI and Go, load-tested identically, to make the "measure, don't assume" discipline concrete rather than theoretical.

```python
# FastAPI version — untested sketch
@app.get("/items/{item_id}")
async def get_item(item_id: int, db: AsyncSession = Depends(get_db)):
    item = await db.get(Item, item_id)
    if item is None:
        raise HTTPException(404, "not found")
    return item
```

```go
// Go equivalent — untested sketch
func getItem(w http.ResponseWriter, r *http.Request) {
    id := chi.URLParam(r, "itemID")
    item, err := db.GetItem(r.Context(), id)
    if errors.Is(err, sql.ErrNoRows) {
        http.Error(w, `{"detail":"not found"}`, http.StatusNotFound)
        return
    }
    json.NewEncoder(w).Encode(item)
}
```

```bash
# Load test BOTH against the SAME database, same hardware, same realistic
# data volume — not a synthetic in-memory benchmark — before drawing any
# conclusion about whether the gap matters for THIS specific workload
wrk -t8 -c200 -d30s http://fastapi-host:8000/items/42
wrk -t8 -c200 -d30s http://go-host:8080/items/42
```

A fuller lab building both versions against a real Postgres instance with realistic data volume, profiling each under `py-spy`/`pprof` respectively to attribute time to database vs framework vs serialization, and measuring the actual gap for a *representative* (not synthetic) workload belongs in `labs/go/08-fastapi-to-go/`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| "FastAPI is too slow" cited as the reason for a proposed rewrite, with no profiling data attached | The bottleneck hasn't actually been identified — proposing a rewrite based on a feeling, not a measurement | Require a profiling result (py-spy/cProfile, SQL query counts, blocking-call audit) before any rewrite conversation proceeds |
| A Go rewrite of a "slow" endpoint shows disappointing improvement | The original bottleneck was database/N+1/missing-cache, not the framework — the same problem exists in the Go version against the same schema | Profile again in Go; if the same query pattern is still the dominant cost, the fix was always database-side, in either language |
| Rewritten Go service breaks existing API clients after cutover | The wire contract (error response shape, field naming convention, status code semantics) wasn't preserved faithfully during the port | Explicitly define and test the contract compatibility before shadow traffic begins, not after |
| Load test shows a large Go-vs-Python gap that doesn't materialize in production | The load test used a synthetic workload (no real DB, no real downstream calls) that isolates pure framework overhead — unrepresentative of real traffic dominated by I/O | Load test against a realistic replica of production data volume and dependency latency, not an in-memory synthetic benchmark |
| CPU-bound Python endpoint stays slow despite adding more `async def` and `await` points | Async concurrency doesn't add CPU parallelism — the GIL still serializes actual bytecode execution across the process regardless of async structure | Either add worker processes (`uvicorn --workers N`, if the memory cost is acceptable) or this is a genuine candidate for the Go/CPU-bound branch of the decision tree |
| A migrated Go service handles the target endpoint well, but the team then proposes rewriting "the rest of the backend too" | Momentum/enthusiasm from one successful, measured migration generalized into an unmeasured blanket decision | Apply the same profile-first discipline to each additional candidate service independently — one success doesn't validate the next migration without its own evidence |

---

## Tradeoffs & when NOT to use it

- **Don't propose a Go rewrite without a profiling result showing the framework itself, not the database or a blocking call, is the bottleneck.** This is the single most common, most expensive mistake in this space, and it's exactly the mistake multiple 2025-2026 postmortems cite explicitly.
- **Don't extrapolate a synthetic CRUD-benchmark gap (Go ~142K RPS vs FastAPI ~38K RPS) onto a real service with database calls, downstream dependencies, and non-trivial serialization.** That benchmark measures pure framework overhead, which is rarely the dominant cost in a real production request.
- **Don't rewrite the whole backend at once.** A justified rewrite is a strangler-fig migration of one proven-bottlenecked endpoint or service, shadowed and gradually cut over — a big-bang full rewrite multiplies risk (contract breakage, feature parity gaps, lost institutional knowledge in the Python codebase) for no additional benefit over doing it incrementally.
- **Don't underestimate the wire-contract-preservation work.** Faithfully reproducing FastAPI's validation error shape, status code conventions, and field naming is real engineering effort easy to miss when a rewrite proposal focuses only on "rewriting the handlers."
- **Don't treat "we could add more Python worker processes" as automatically inferior to a rewrite.** Horizontal scaling within Python is cheaper and faster to ship than a rewrite and may clear the actual bottleneck — evaluate it explicitly as an alternative before defaulting to Go.
- **Don't ignore Python's free-threaded build direction as if it's irrelevant.** It's not production-default yet, but it's a real, funded, multi-year effort specifically targeting the GIL limitation described in this module — worth naming as a "where it's heading" caveat if the conversation turns to whether this tradeoff is permanent.

---

## Interview questions

### Q1 — A team proposes rewriting a FastAPI service in Go because "Python is slow." What's your first question?
**Testing:** whether measurement-first discipline is a reflex, not an afterthought.
**Answer:** "What profiling data shows the framework itself is the bottleneck, as opposed to the database, a blocking call inside an async handler, or missing caching?" The cited, repeated finding across real 2025-2026 rewrite postmortems is that most "FastAPI is slow" complaints trace back to exactly those non-framework causes, all fixable in Python for a fraction of a rewrite's cost — proposing a rewrite without that evidence is proposing to spend weeks of engineering time on a guess.
**Follow-up trap:** *"The team says they already profiled it and it's genuinely CPU-bound Python code taking too long."* — then the next question is whether horizontal scaling (`uvicorn --workers N`) already clears the bottleneck at acceptable memory cost, since that's cheaper and faster to ship than a rewrite — only once that's also ruled out (or the memory cost of enough workers is itself prohibitive) does a targeted Go rewrite for that specific hot path become the reasonable next step.

### Q2 — Explain, mechanically, why Python's GIL limits CPU-bound performance but doesn't limit FastAPI's I/O-bound concurrency the same way.
**Testing:** whether the actual mechanism, not a vague "Python is slow," is understood.
**Answer:** The GIL ensures only one thread executes Python bytecode at any instant within a process. `asyncio`/FastAPI's async model achieves I/O concurrency by having a single thread cooperatively switch between many pending coroutines *while they're waiting on I/O* — no bytecode is executing during that wait, so the GIL isn't the constraint there. But when a request's handler is doing genuine CPU work — computing, parsing, serializing a large payload — that work executes real bytecode and the GIL serializes it against every other request on that process, regardless of whether the handler is `async def` or not; being async changes nothing about CPU-bound execution time.
**Follow-up trap:** *"So would making a CPU-bound handler synchronous instead of async fix anything?"* — no, that's an orthogonal axis entirely; sync vs async determines how the process waits on I/O, not whether CPU work is parallelized. Fixing CPU-bound throughput within Python requires more OS processes (each with their own GIL and own memory), not a different single-process concurrency model.

### Q3 — Cite the actual 2026 benchmark numbers for FastAPI vs Go, and immediately name the biggest caveat about them.
**Testing:** whether specific numbers are known cold, and whether their limits are understood unprompted.
**Answer:** A cited controlled comparison for JSON CRUD workloads: Go (Fiber/Gin-class) at roughly 142,000 RPS versus FastAPI at roughly 38,000 RPS, with Go delivering up to 7x better tail latency under high sustained stress specifically (the gap narrows under moderate load). The caveat: this measures pure framework/runtime overhead with no real database, no downstream calls, and minimal business logic — exactly the condition under which framework choice is the *entire* cost, which almost never describes a real production service where I/O (database round trips, downstream API calls) dominates total latency regardless of language.
**Follow-up trap:** *"So the numbers are meaningless?"* — no, they're real and directionally correct for genuinely framework-bound, high-fan-out, or CPU-bound workloads — the caveat isn't that they're wrong, it's that extrapolating them onto a typical I/O-dominated production service systematically overstates the expected real-world improvement from a rewrite.

### Q4 — What's a strangler-fig migration, and why is it the right execution model for a justified Go rewrite rather than a full rewrite?
**Testing:** whether the *how* of a justified rewrite is understood, not just the *whether*.
**Answer:** Migrating one proven-bottlenecked endpoint or service at a time behind a stable API gateway/proxy contract: shadow real traffic to the new Go service first (compare responses for correctness with zero user-facing risk, since the old path still serves real responses), gradually cut over a growing percentage of real traffic while monitoring correctness and actual measured improvement, then decommission only that specific Python code path once proven at full traffic — repeating per-service rather than attempting a single atomic full-backend rewrite. This bounds risk (a bad migration affects one endpoint, not the whole backend), preserves the ability to roll back cheaply at any stage, and matches how the cited real case studies (Reddit's Comments/Accounts/Posts/Subreddits migration) actually happened — as discrete, individually justified extractions.
**Follow-up trap:** *"What's the biggest risk this process is specifically designed to avoid?"* — a big-bang rewrite committing to a full contract/behavior port before any real traffic has validated correctness, discovering a subtle behavioral divergence (a validation edge case, an error-shape mismatch) only after full cutover, with no partial-traffic safety net to catch it cheaply.

### Q5 — A load test comparing your FastAPI and Go prototypes shows Go 3.7x faster, matching the cited benchmark. Should you trust that number for your production decision?
**Testing:** whether synthetic-benchmark skepticism is applied to a self-generated result, not just a cited one.
**Answer:** Only if the load test used realistic conditions — a real (or realistically-sized and realistically-latent) database, real downstream dependency calls at their actual latency, and payload shapes matching production, not an in-memory synthetic CRUD benchmark. If the test isolates pure framework overhead the way the cited industry benchmarks do, the 3.7x gap is real for *that specific measurement* but likely overstates the improvement a real, I/O-dominated production service would see, since the database/downstream-call latency that dominates real requests is identical in both languages.
**Follow-up trap:** *"How would you redesign the load test to be trustworthy for the actual production decision?"* — replay real (or realistically synthesized) production traffic patterns against both implementations connected to a production-representative database with production-representative data volume and index state, ideally via the shadow-traffic mechanism itself rather than a separate synthetic benchmark — the actual migration's shadow phase is a better decision input than any pre-migration synthetic load test.

### Q6 — At what point does "add more Python worker processes" stop being a viable alternative to a Go rewrite for a CPU-bound bottleneck?
**Testing:** staff-level judgment on the actual tradeoff between horizontal Python scaling and a rewrite.
**Answer:** When the memory cost of enough worker processes to hit the required throughput becomes prohibitive — each `uvicorn` worker is a full separate OS process duplicating loaded modules, models, and any in-process (non-shared) state, so scaling to dozens of workers to match Go's single-process multi-core throughput can mean dramatically higher memory footprint and infrastructure cost than a single Go process using the same cores natively. The crossover point is workload-specific: a lightweight handler with small memory footprint per worker might scale acceptably to many processes; a worker loading a large model or big in-memory cache hits the memory ceiling much sooner, making the Go rewrite's single-process multi-core efficiency the more cost-effective answer.
**Follow-up trap:** *"Could you use a shared cache (Redis) to avoid the per-worker memory duplication instead of rewriting?"* — yes, and that's a legitimate intermediate step worth trying before a rewrite — externalizing shared, expensive-to-duplicate state to Redis/Memcached lets more Python worker processes scale without each carrying a full private copy, which can meaningfully raise the threshold at which a rewrite becomes the better answer, or eliminate the need for one entirely.

### Q7 — What specifically breaks for existing clients if a Go rewrite doesn't preserve FastAPI's exact validation error response shape?
**Testing:** whether the wire-contract risk, not just the code-translation risk, is understood as real engineering cost.
**Answer:** Any client that parses the structured validation error body — FastAPI's `{"detail": [{"loc": [...], "msg": "...", "type": "..."}]}` shape from a `RequestValidationError` — to extract which field failed and why (a form-validation UI mapping errors back to specific input fields, for instance) breaks silently if the Go rewrite returns a differently-shaped error body, even if the *behavior* (rejecting invalid input with an appropriate status code) is functionally equivalent. This is a specific, concrete instance of a much broader risk: a rewrite proposal that frames the work as "reimplement the handlers" often doesn't account for every consumer's dependency on the exact wire format, not just the endpoint's logical behavior.
**Follow-up trap:** *"How would you catch this before it reaches production?"* — contract tests comparing the Go service's actual response bodies against the Python service's for the same set of both valid and deliberately invalid inputs, run as part of the shadow-traffic phase specifically, not just functional/integration tests that check status codes alone.

### Q8 — Your CPU-bound Python service's async handlers show no throughput improvement no matter how many `await` points you add. Why, and what's the actual fix path?
**Testing:** applying the GIL mechanism to a realistic misdiagnosis scenario.
**Answer:** Adding `await` points restructures *how* the process waits on I/O; it does nothing for CPU-bound work, since the GIL still serializes actual bytecode execution regardless of how many coroutines are notionally concurrent. If the handler is genuinely CPU-bound (not accidentally CPU-bound because of an inefficient algorithm or unnecessary work that could simply be optimized first), the fix path is: first, algorithmic/implementation optimization if any is available (often overlooked in the rush toward "we need a different language"); second, horizontal scaling via more Python worker processes if memory cost is acceptable; third, offloading the specific CPU-bound computation to a Go (or Rust, or C extension) component called from Python, keeping the rest of the service in Python; fourth, and only if the whole service's profile justifies it, a full rewrite of that service.
**Follow-up trap:** *"Why would you offload just the CPU-bound piece rather than rewriting the whole service, if you're already introducing Go?"* — it captures the actual performance win (the genuinely CPU-bound hot path) while minimizing the surface area of contract-preservation risk, migration effort, and ongoing polyglot maintenance cost — rewriting only what's proven to need it is the same discipline as the endpoint-level strangler-fig approach, applied at a finer grain (a computational component rather than a whole service).

### Q9 — Your team successfully migrates one hot endpoint to Go and sees the promised throughput improvement. Leadership now wants to rewrite the entire backend. What do you say?
**Testing:** whether the profile-first discipline survives success, or gets abandoned once momentum builds.
**Answer:** One measured, successful migration validates that migration for that specific, profiled bottleneck — it doesn't validate rewriting services that were never shown to be framework-bound in the first place. The right response is applying the identical discipline to each additional candidate independently: profile it, confirm the bottleneck is genuinely the framework/GIL rather than database/caching/blocking-call issues, and only then scope a migration — otherwise the team risks spending months rewriting services that turn out, like the majority of cases cited in real postmortems, to have been database-bound or cache-missing all along, with the Go version equally disappointing.
**Follow-up trap:** *"Isn't that overly cautious given the team just proved Go's advantage works?"* — the team proved Go's advantage works for *one specific, measured, CPU/framework-bound bottleneck* — generalizing that to "Go is just better, rewrite everything" is exactly the reasoning error this module exists to correct, regardless of how good the first result felt. Momentum is not evidence.

### Q10 — How would you design the shadow-traffic comparison phase of a strangler-fig migration to catch a subtle behavioral divergence before full cutover?
**Testing:** the practical mechanics of de-risking a justified rewrite, not just naming the pattern.
**Answer:** Route a copy of real production traffic to the new Go service in parallel with the existing Python service actually serving the response, then diff the two responses programmatically — status codes, response bodies (including error shapes), and ideally latency — logging any divergence for review without ever letting the shadow service's response reach the real user. Run this across a long enough window and high enough traffic volume to surface edge cases (unusual input combinations, rare error paths, timezone/locale-dependent formatting differences) that a pre-migration test suite is unlikely to have anticipated, since real traffic reliably finds cases synthetic tests miss.
**Follow-up trap:** *"What do you do when the shadow comparison finds a divergence — pause the whole migration?"* — depends on the divergence's severity and scope: a cosmetic difference (float formatting, key ordering in JSON) might be fixed and the migration continued; a semantic difference (wrong data returned, a validation rule not faithfully ported) should pause cutover for that specific path until fixed and re-verified — the point of the shadow phase is precisely to make this a controlled, low-stakes decision rather than a production incident discovered after real cutover.

---

## Red flags that fail you

- Proposing or endorsing a rewrite based on "Go is faster" with no profiling evidence identifying the actual bottleneck.
- Not knowing that async/await in Python addresses I/O concurrency, not CPU parallelism, and conflating the two.
- Citing the FastAPI-vs-Go benchmark numbers without the caveat that they measure pure framework overhead, not a representative production workload.
- Recommending a full big-bang backend rewrite instead of a strangler-fig, endpoint-by-endpoint migration.
- Ignoring the wire-contract-preservation cost (error shapes, field naming, status semantics) when scoping a rewrite.
- Not considering horizontal Python scaling (more worker processes, shared caching) as an alternative before defaulting to a rewrite.
- Treating the Go/Python performance gap as a fixed, load-independent multiplier rather than something that widens under stress and narrows under moderate load.
- Assuming Python's GIL limitation is permanent and unworth mentioning the free-threaded build effort as a "where it's heading" caveat.

---

## Cheat card

```
BENCHMARK (2026, JSON CRUD, controlled): Go ~142K RPS vs FastAPI ~38K RPS vs
  Express5 ~19K RPS. Up to 7x better Go tail latency under HIGH stress;
  gap narrows under MODERATE load. CAVEAT: measures pure framework overhead,
  no real DB/downstream calls — rarely the dominant cost in production.

WHY THE GAP EXISTS: Python GIL = only ONE thread executes bytecode/process,
  regardless of thread/async count. asyncio/FastAPI async = I/O CONCURRENCY
  (cooperative waiting), NOT CPU parallelism — a CPU-bound handler gets ZERO
  benefit from being async def. Go goroutines = genuine M:N parallel compute
  across all GOMAXPROCS cores, single process, no GIL equivalent.
  Python's CPU-bound fix = MORE PROCESSES (uvicorn --workers N), each with
  own memory/GIL, no shared in-process cache (need Redis for that).

DECISION RULE: profile FIRST. Order of checks before considering Go:
  1. blocking call stalling the event loop? (T11-fastapi-deep)
  2. N+1 queries / missing indexes / missing caching?
  3. is it ACTUALLY CPU-bound (not I/O-wait)? py-spy/cProfile under load.
  4. ONLY THEN: already-tuned endpoint still hitting ~50K+ RPS or a hard
     latency wall more Python workers can't clear cost-effectively?
  ~8K RPS peak: fine on either. ~80K RPS peak: language choice matters.

MIGRATION MODEL: strangler-fig, ONE endpoint/service at a time, never a
  big-bang full rewrite. Phases: SHADOW (compare responses, zero risk) ->
  GRADUAL CUTOVER (ramp real traffic, monitor) -> DECOMMISSION (that path
  only). Real case studies (Reddit Comments/Accounts/Posts/Subreddits) =
  discrete, individually justified extractions, not one atomic rewrite.

WIRE CONTRACT RISK (often underestimated): FastAPI's 422 validation error
  SHAPE ({"detail":[{"loc","msg","type"}]}), field naming (snake_case vs
  Go's idiomatic CamelCase JSON), status code conventions — must be
  preserved explicitly or existing clients break silently on cutover.

ALTERNATIVES TO RECONSIDER BEFORE REWRITING: more uvicorn workers (memory
  cost tradeoff), shared caching (Redis) to reduce per-worker duplication,
  algorithmic optimization of the actual hot path, offloading JUST the
  CPU-bound component to Go/Rust rather than rewriting the whole service.

WHERE IT'S HEADING: Python free-threaded build (PEP 703) removes the GIL
  as an opt-in experimental mode — real, funded, multi-year effort, NOT
  yet production-default in mainstream Python as of 2026.
```

## Sources

- [FastAPI vs Node.js vs Go: 2026 Benchmark Reality Check — Acquaintsoft](https://acquaintsoft.com/blog/fastapi-vs-nodejs-vs-go-performance-benchmarks) — accessed 2026-08-03
- [Go vs Node.js vs FastAPI: Backend Technology Comparison 2026 — Index.dev](https://www.index.dev/skill-vs-skill/backend-go-vs-nodejs-vs-python-fastapi) — accessed 2026-08-03
- [FastAPI vs Fiber: A Benchmark, not Opinion — Medium](https://ravishtiwari.medium.com/fastapi-vs-fiber-a-benchmark-not-opinion-da1848c6caae) — accessed 2026-08-03
- [Benchmarking Gin, Elysia, BlackSheep, and FastAPI — Cemrehan Çavdar](https://cemrehancavdar.com/2026/02/10/framework-benchmark/) — accessed 2026-08-03
- [Rewriting Python Microservice in Golang — Medium](https://medium.com/@shubham320/rewriting-python-microservice-in-golang-2aba65f903cc) — accessed 2026-08-03
- [I Rewrote My Python Microservice In Go — The Performance Results — Medium](https://medium.com/@ArkProtocol1/i-rewrote-my-python-microservice-in-go-the-performance-results-were-disgusting-in-a-good-way-2f31f112b55c) — accessed 2026-08-03
- [How Khan Academy rewrote their backend — Quastor](https://quastor.substack.com/p/how-khan-academy-rewrote-their-backend) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
