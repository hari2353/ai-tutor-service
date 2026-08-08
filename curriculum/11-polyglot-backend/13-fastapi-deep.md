# FastAPI Deep: Pydantic Validation, DI, Exception Handlers, BackgroundTasks

> **Track:** T11 Polyglot Backend · **Time:** 2.5h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T11-fastapi-deep` · **Tags:** python, critical

## Why this gets asked

Everyone who has shipped a FastAPI service can draw `@app.get` and a Pydantic model. The interviewer already assumes that. What they're actually checking is whether you've hit the three walls that only show up under load or under attack: a blocking call inside an `async def` handler that quietly collapses your throughput while every dashboard says CPU is idle, a stack trace leaking through an unhandled exception into a client response, and a "background task" that someone believed was a job queue until a deploy rolled mid-request and silently dropped work. They've debugged at least one of these in production. If you can narrate the failure and not just the feature, you're being read as someone who has actually operated the framework, not tutorialed through it.

---

## Lineage: past → present → future

**What came before.** Pre-2018 Python web APIs meant Flask or Django REST Framework: mature, synchronous-by-default (Flask), or batteries-included but heavyweight (DRF), and in both cases request validation was bolted on — marshmallow schemas, DRF serializers, or hand-rolled `if not isinstance` checks duplicated between validation and API documentation. You wrote the OpenAPI spec by hand or generated it from decorators that drifted from the actual code within a sprint. Async support existed (aiohttp, Sanic) but without integrated validation or docs. The pain was concrete: every endpoint had a validation layer, a serialization layer, and a documentation layer, maintained separately, and they went out of sync constantly — DRF serializers silently accepting fields the model didn't have, hand-written OpenAPI YAML describing an endpoint that had since changed shape.

**Where it stands now.** Sebastián Ramírez released FastAPI in December 2018, betting on three things that had just become viable together: Python 3.6+ type hints, Starlette as a genuinely fast ASGI toolkit, and Pydantic for validation. The bet paid off — type hints became the single source of truth for validation, serialization, and OpenAPI generation simultaneously, collapsing three previously-separate layers into one. It is now the dominant async Python API framework, sitting on Starlette (routing, middleware, ASGI, WebSockets — Starlette itself wraps Uvicorn/Hypercorn as the actual server) and Pydantic (parsing, validation, serialization) and contributing essentially none of the low-level machinery itself. FastAPI's real product is the dependency injection system and the way it wires type hints to all three of the layers above. The live disagreement is less about FastAPI itself and more about the ecosystem around it: whether Django's newer async views close the gap for teams already invested in Django's ORM and admin, and whether Litestar (a more opinionated, DI-container-first alternative also built on Starlette-adjacent ASGI foundations) is a better fit for larger services — both are real production choices in 2026, not FastAPI-or-nothing.

**Where it's heading.** Pydantic v2's Rust core (`pydantic-core`) is the settled direction: validation stopped being a Python-level cost, and every future FastAPI release assumes it. Typed, async-first background processing is consolidating around lightweight asyncio-native queues (ARQ) rather than Celery for new services, because most FastAPI-shaped workloads don't need Celery's multi-broker, multi-language flexibility. Moderate confidence. More speculatively, structured output validation is increasingly shared infrastructure between web APIs and LLM tool-calling — Pydantic models already double as both FastAPI request schemas and LLM structured-output schemas in a lot of 2026 codebases, and that convergence looks likely to deepen rather than reverse.

---

## Mental model

```
                    HTTP request
                          │
                 ┌────────▼─────────┐
                 │     Starlette     │  routing, ASGI, middleware,
                 │  (the web layer)  │  WebSockets, background task API
                 └────────┬─────────┘
                          │  path params, query params, body (raw)
                 ┌────────▼─────────┐
                 │     Pydantic      │  parse → validate → coerce
                 │ (the data layer)  │  request model in, response model out
                 └────────┬─────────┘
                          │  typed Python objects
                 ┌────────▼─────────┐
                 │   Type hints +    │  FastAPI's actual contribution:
                 │   Depends graph   │  wire hints to validation, DI, docs
                 └────────┬─────────┘
                          │
                    your endpoint
```

FastAPI itself is thin. It does not parse HTTP, does not validate data, does not run the event loop. Its job is reading your function signature and turning type hints into three things simultaneously: a Pydantic validator for the request, a Pydantic serializer for the response, and an OpenAPI schema — plus resolving a `Depends()` graph before your function ever runs. That's the whole value proposition: one declaration, three consumers.

---

## How it actually works

### Pydantic's role, precisely

Four separate jobs, often conflated into "validation":

1. **Request parsing/validation** — raw JSON/query/path/form data → typed Python objects, or a `422` if it doesn't fit.
2. **Response serialization** — your return value → JSON, filtered and shaped by `response_model`.
3. **Settings management** — `pydantic-settings`' `BaseSettings` reads env vars, `.env` files, and secrets into a typed, validated config object at startup instead of scattering `os.environ.get(...)` with silent `None` defaults across the codebase.
4. **Schema generation** — the same model produces the OpenAPI schema shown in `/docs`, so contract and implementation cannot drift.

**`response_model` as a data-leak control, not just a formatting nicety.** This is the part people miss: `response_model` filters the *output*, independent of what your function returns.

```python
from pydantic import BaseModel

class UserInDB(BaseModel):
    id: int
    email: str
    hashed_password: str      # never meant to leave the process
    is_admin: bool

class UserOut(BaseModel):
    id: int
    email: str

@app.get("/users/{user_id}", response_model=UserOut)
async def get_user(user_id: int) -> UserInDB:
    return await db.fetch_user(user_id)   # full row, hashed_password included
```

FastAPI validates the return value against `UserOut`, drops `hashed_password` and `is_admin`, and serializes only what's left. A future engineer who adds a `stripe_customer_id` field to `UserInDB` and forgets to update `UserOut` gets a safe failure mode (the field silently doesn't leave), not a silent leak — the opposite direction of the usual "forgot to filter" bug class. This is a real, load-bearing security control, not decoration. `response_model_exclude_unset=True` additionally drops fields the object never set (useful for `PATCH` responses that should only echo what changed); `response_model_exclude_none=True` drops `None`s. [Response Model - Return Type — FastAPI docs](https://fastapi.tiangolo.com/tutorial/response-model/) — accessed 2026-08-01.

**v1 vs v2, with numbers.** Pydantic v2 (2023) moved the validation core to Rust (`pydantic-core`), keeping the Python-facing API mostly compatible but not identical (see the migration guide — `Config` class becomes `model_config = ConfigDict(...)`, `.dict()` becomes `.model_dump()`, `@validator` becomes `@field_validator`). Reported benchmarks put v2 at roughly **4x-50x faster than v1.9** depending on the model shape, with the commonly cited headline number around **17x faster on a model with a representative mix of common field types**, and Pydantic's own benchmarks showing complex nested models validating **~20x faster**. Point releases keep incrementally improving on top of that base (Pydantic 2.5.2 reported a further ~12% gain over the first v2 release, on top of the already-large jump from v1). [Pydantic V2: Supercharge Your Data Validation with Rust](https://medium.com/@akaashhazarika/pydantic-v2-supercharge-your-data-validation-with-rust-95ae490b5e46) — accessed 2026-08-01; [Obtain a 5x speedup for free by upgrading to Pydantic v2 — The Data Quarry](https://thedataquarry.com/blog/why-pydantic-v2-matters/) — accessed 2026-08-01. Treat the exact multiplier as model-shape-dependent — it is not a single fixed number — but the direction and order of magnitude are solid and worth quoting cold.

**Validators and config in v2:**

```python
from pydantic import BaseModel, field_validator, model_validator, ConfigDict

class SignupRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True, extra="forbid")

    email: str
    password: str
    password_confirm: str

    @field_validator("email")
    @classmethod
    def lowercase_email(cls, v: str) -> str:
        return v.lower()

    @model_validator(mode="after")
    def passwords_match(self) -> "SignupRequest":
        if self.password != self.password_confirm:
            raise ValueError("passwords do not match")
        return self
```

`extra="forbid"` rejects unknown fields outright — a real defense against clients silently sending fields you never validated (mass-assignment-style bugs). Default is `"ignore"`, which is usually the wrong default for anything touching auth or billing.

For full Pydantic v2 typing mechanics (generics, discriminated unions, `TypeAdapter`), see **T01-typing**; this module only covers the FastAPI-specific usage.

### Dependency injection — the thing that makes it testable

`Depends()` is a plain function (or callable) FastAPI calls before your endpoint, injecting the result as an argument. Three properties matter beyond the basic case:

**Sub-dependencies compose into a graph**, resolved once per request even when referenced multiple times:

```python
def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    return decode_and_load_user(token, db)

def get_current_admin(user: User = Depends(get_current_user)) -> User:
    if not user.is_admin:
        raise HTTPException(403, "admin only")
    return user

@app.delete("/users/{user_id}")
def delete_user(user_id: int, admin: User = Depends(get_current_admin), db: Session = Depends(get_db)):
    ...  # get_db() is called ONCE for this request, shared between get_current_user and here
```

**Caching within a request.** FastAPI caches a dependency's result per request by default (keyed on the callable), so `get_db` above returns the same session to both `get_current_user` and `delete_user` rather than opening two connections. Set `Depends(get_db, use_cache=False)` to force a fresh call. This is the mechanism, not an incidental detail — without it every dependency referenced twice would run twice, which for a DB session means two connections and, worse, two separate transactions.

**`yield` dependencies and teardown ordering.** Code after `yield` runs as cleanup, *after the response has been sent*, wrapped in `AsyncExitStack`, which means teardown is **LIFO**: if the resolved dependency graph is A → B → C (C depends on B depends on A), teardown order is C, then B, then A — the reverse of setup order, and the correct order, because B's cleanup might still need A to be alive. [Dependencies with Yield — FastAPI docs](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/) — accessed 2026-08-01.

```python
def get_db():
    db = SessionLocal()
    try:
        yield db
        db.commit()          # only reached if the endpoint didn't raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()           # always runs, teardown, after response is sent
```

A subtlety worth naming out loud: an exception raised *inside the endpoint* propagates back through the `yield` point of every dependency in the chain, so a `try/except` around `yield` is how you catch it and roll back — omit it and you leak an open transaction on error paths.

**Dependency overrides — the actual test story.** `app.dependency_overrides[get_db] = get_test_db` swaps the real dependency for a fake one, keyed by the original callable, for the lifetime of the override:

```python
app.dependency_overrides[get_db] = lambda: TestSessionLocal()
client = TestClient(app)
# ... run tests ...
app.dependency_overrides.clear()
```

This is *why* people say FastAPI is testable: you never need to monkeypatch a module-level import or mock an ORM call, because every external dependency your endpoint touches was already expressed as an injectable seam. Compare to a typical Flask/Django handler that imports the DB session directly at module scope, where testing means patching `sys.modules` or reaching for `unittest.mock.patch` on an import path that breaks the moment someone refactors the module layout.

### Errors and exceptions

Three distinct mechanisms, frequently confused:

| Mechanism | Raised by | Status | When |
|---|---|---|---|
| `HTTPException` | your code, deliberately | whatever you pass (`404`, `403`, ...) | expected business-logic failures |
| `RequestValidationError` | FastAPI/Pydantic, automatically | **422**, not 400 | request body/query/path fails Pydantic validation |
| unhandled `Exception` | anything | 500, generic body, unless you add a handler | bugs, unexpected downstream failures |

**The 422 surprise.** People coming from REST conventions expect `400 Bad Request` for malformed input. FastAPI's default is `422 Unprocessable Entity` for validation failures specifically, because it's distinguishing "the request is syntactically fine but the *content* fails semantic/schema validation" (422, HTTP's own definition, RFC 4918 via WebDAV) from "the request itself is malformed" (400, reserved for cases like invalid JSON that can't even be parsed). Interviewers ask this because it's a genuine, cited, non-obvious framework decision, and the follow-up is whether you know you can override it:

```python
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(status_code=400, content={"detail": exc.errors()})
```

**Never leak internal exception text.** The default 500 handler in debug mode (or a naively written custom one) can put a raw traceback or `str(exc)` into the response body — which routinely leaks table names, ORM query fragments, internal hostnames, or stack frames revealing library versions, directly useful for an attacker fingerprinting your stack. The fix is a global handler that logs the real exception server-side and returns a generic, non-identifying body to the client:

```python
import logging, uuid
logger = logging.getLogger("app")

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    error_id = uuid.uuid4().hex
    logger.exception("unhandled exception, error_id=%s", error_id)
    return JSONResponse(
        status_code=500,
        content={"detail": "internal server error", "error_id": error_id},
    )
```

The `error_id` correlates the opaque client-facing message back to the full server-side log without exposing anything — this pattern shows up in every mature API and is worth having memorized.

**Custom domain exceptions** get their own handler rather than being converted to `HTTPException` at every call site:

```python
class InsufficientBalanceError(Exception):
    def __init__(self, account_id: str, needed: float):
        self.account_id, self.needed = account_id, needed

@app.exception_handler(InsufficientBalanceError)
async def balance_handler(request: Request, exc: InsufficientBalanceError):
    return JSONResponse(status_code=402, content={"detail": f"insufficient balance on {exc.account_id}"})
```

This keeps business logic free of HTTP concerns — a service class can `raise InsufficientBalanceError` without importing `fastapi` at all, which also matters if that logic is ever reused outside a web context (a CLI, a worker).

### `BackgroundTasks` versus a real queue

`BackgroundTasks` runs the function *after the response is sent*, in the same process, on the same event loop (for async functions) or the threadpool (for sync functions):

```python
from fastapi import BackgroundTasks

def send_confirmation_email(email: str):
    smtp_client.send(email, "Order confirmed")

@app.post("/orders")
async def create_order(order: OrderIn, background_tasks: BackgroundTasks):
    order_id = await save_order(order)
    background_tasks.add_task(send_confirmation_email, order.email)
    return {"order_id": order_id}
```

**The trap: it is not durable.** There is no broker, no persistence, no retry, no visibility. If the process receives `SIGTERM` mid-task (a routine rolling deploy, an autoscaler scale-down, an OOM kill), the in-flight task is dropped with no record it ever existed. [FastAPI Background Tasks: Celery vs ARQ vs RQ — 2026 Benchmarks & Decision Guide](https://medium.com/@rameshkannanyt0078/fastapi-background-tasks-celery-vs-arq-vs-rq-2026-benchmarks-decision-guide-f99598aa21eb) — accessed 2026-08-01. Fine for "send a non-critical email, best-effort" — wrong for "charge the card," "issue the refund," or anything the business would notice missing. The observable symptom in production is a support ticket: "I placed the order but never got the confirmation," with nothing in any log, because the task never got far enough to log its own failure — the process was already gone.

Use a real queue (ARQ backed by Redis for asyncio-native FastAPI stacks, Celery when you need multi-language workers or a heavier feature set, SQS/RabbitMQ-backed workers on AWS) whenever the work needs: durability across a crash, retries with backoff, visibility (task status, dead-letter queue), or independent scaling of the worker fleet.

### Async vs sync path operations, and the threadpool trap

`async def` handlers run directly on the single event loop. `def` (sync) handlers are automatically dispatched to Starlette's threadpool and awaited — this is a deliberate design choice so blocking libraries (`requests`, `psycopg2`, `pandas` calls) don't need to be rewritten to use FastAPI at all. That threadpool has a real, finite default size; a commonly cited default cap is **40 worker threads**. [Understanding Concurrency in FastAPI](https://bhaveshparvatkar.medium.com/understanding-concurrency-in-fastapi-fbbe09dc4979) — accessed 2026-08-01.

**The failure mode with the specific observable symptom.** Put a blocking call — a synchronous `requests.get()`, `time.sleep()`, a non-async DB driver call, `pandas.read_sql` — inside an `async def` endpoint, and it blocks the *entire event loop*, not just that request's thread. Every other coroutine scheduled on that loop, including totally unrelated endpoints, stalls until the blocking call returns. The symptom is distinctive and worth being able to name cold: **p99 latency and error rate climb sharply as concurrency increases, throughput plateaus and then collapses, while CPU utilization stays low or idle** — because the process isn't computing, it's blocked on I/O with nothing else able to run. Teams that haven't seen this before typically misdiagnose it as "we need more CPU" or "the database is slow," add replicas, and the problem doesn't move, because the bottleneck is one blocked event loop per process, not compute.

```python
# WRONG — blocks the event loop; every concurrent request on this worker stalls
@app.get("/report")
async def get_report():
    resp = requests.get("https://slow-upstream.example.com/data")   # sync call in async def
    return resp.json()

# RIGHT — either use an async client...
@app.get("/report")
async def get_report():
    async with httpx.AsyncClient() as client:
        resp = await client.get("https://slow-upstream.example.com/data")
    return resp.json()

# ...or, if the library has no async version, push it to the threadpool explicitly
from starlette.concurrency import run_in_threadpool

@app.get("/report")
async def get_report():
    resp = await run_in_threadpool(requests.get, "https://slow-upstream.example.com/data")
    return resp.json()
```

One reported real-world case: a team fixed this class of bug (removing blocking calls from async paths, tuning threadpool size, avoiding needless threadpool round-trips) and moved a service from **~40 RPS to a sustained ~200 RPS** with no hardware change. [Shippo: why is my FastAPI throughput so low](https://goshippo.com/blog/why-is-my-fastapi-throughput-so-low) — accessed 2026-08-01. This is the single most common FastAPI production incident and the highest-signal interview question in this module — see Q6 below.

### Middleware, lifespan, streaming

**Middleware** wraps every request/response (CORS, request-ID injection, GZip, auth pre-checks that don't need the DI graph):

```python
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request.state.request_id = str(uuid.uuid4())
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    return response
```

**Lifespan** replaces the deprecated `@app.on_event("startup"/"shutdown")` pair with a single async context manager — the natural place to open a DB connection pool, warm a model, or start a background scheduler, and to close them cleanly on shutdown:

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.db_pool = await create_pool()
    yield
    await app.state.db_pool.close()

app = FastAPI(lifespan=lifespan)
```

**Streaming responses** — `StreamingResponse` for chunked output (log tails, CSV export, token-by-token LLM output) and Starlette's native SSE support for server-sent events; for the fuller comparison of SSE vs WebSocket vs polling for streaming APIs, see **T11-api-design**.

### When FastAPI is the wrong choice

- **CPU-bound, compute-heavy workloads** (image processing, heavy PySpark-style transforms) get nothing from the async model — you need process-based parallelism (multiprocessing, a job queue with worker processes) regardless of the web framework in front of it. FastAPI is fine as the thin API layer, but the async event loop buys you nothing for the actual work.
- **Teams already deep in Django** with its ORM, admin panel, and migrations tooling: rewriting for FastAPI to get async support is often a worse trade than adopting Django's async views, unless the service is genuinely new.
- **Very large, many-team monoliths** where FastAPI's lack of an opinionated app structure (no enforced layering, no built-in ORM) becomes a liability — Litestar's more structured DI container or a heavier framework can pay off once you have dozens of engineers touching one service.
- **gRPC-first internal service meshes** — FastAPI's real strength (OpenAPI-first REST, docs, validation) is largely wasted if every caller is another internal service that would rather have protobuf and HTTP/2 streaming natively; see **T11-api-design** for the REST vs gRPC tradeoff.
- **Anywhere you need true multi-language worker interop** for background jobs (Python producers, Go/Java consumers) — reach for Celery, SQS, or a message broker rather than pretending `BackgroundTasks` will grow into that role.

---

## Build it from scratch

A minimal but complete slice showing the DI + validation + error-handling + background-task pattern together:

```python
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from contextlib import asynccontextmanager
import logging, uuid

logger = logging.getLogger("orders")
FAKE_DB: dict[int, dict] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("starting up")
    yield
    logger.info("shutting down")


app = FastAPI(lifespan=lifespan)


class OrderIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item: str
    quantity: int
    email: str


class OrderOut(BaseModel):
    order_id: int
    item: str
    quantity: int
    # NOTE: email deliberately excluded — response_model as data-leak control


def get_db():
    yield FAKE_DB   # stand-in for a real session; teardown would go after yield


def notify_customer(email: str, order_id: int):
    logger.info("would email %s about order %s", email, order_id)


class OutOfStockError(Exception):
    def __init__(self, item: str):
        self.item = item


@app.exception_handler(OutOfStockError)
async def out_of_stock_handler(request: Request, exc: OutOfStockError):
    return JSONResponse(status_code=409, content={"detail": f"'{exc.item}' is out of stock"})


@app.exception_handler(Exception)
async def unhandled_handler(request: Request, exc: Exception):
    error_id = uuid.uuid4().hex
    logger.exception("unhandled, error_id=%s", error_id)
    return JSONResponse(status_code=500, content={"detail": "internal error", "error_id": error_id})


@app.post("/orders", response_model=OrderOut, status_code=201)
async def create_order(order: OrderIn, background_tasks: BackgroundTasks, db: dict = Depends(get_db)):
    if order.item == "widget" and order.quantity > 100:
        raise OutOfStockError(order.item)
    order_id = len(db) + 1
    db[order_id] = order.model_dump()
    background_tasks.add_task(notify_customer, order.email, order_id)
    return {"order_id": order_id, "item": order.item, "quantity": order.quantity}
```

Send a body missing `email` and observe the `422` with a Pydantic-shaped error list, not a `400`. Send `{"item": "widget", "quantity": 500, "email": "a@b.com"}` and observe the `409` from the custom handler rather than a generic 500. Neither `email` nor internal error text appears in any successful response body.

For a fuller runnable version with tests exercising dependency overrides and the threadpool-blocking failure mode directly, pair this module with a lab — none exists yet for this module; a reasonable ask is `labs/py/13-fastapi-deep/` covering the DI-override test pattern and a load-test script demonstrating the blocking-call throughput collapse.

---

## How it's done in production

| Concern | What's actually used | What it adds over the toy version |
|---|---|---|
| Settings | `pydantic-settings.BaseSettings` | typed env vars, `.env` loading, secret validation at boot, not at first use |
| Background jobs | ARQ (asyncio-native, Redis) or Celery (multi-broker, multi-language) | durability, retries, visibility, independent worker scaling |
| Sync DB drivers in async app | `run_in_threadpool`, or switch to `asyncpg`/`SQLAlchemy 2.0 async` | keeps blocking I/O off the event loop |
| Observability | OpenTelemetry ASGI middleware, structured logging with request-ID | traces span service boundaries; `X-Request-ID` correlates logs to a single request |
| Rate limiting / auth | `slowapi`, API gateway, or ambassador pattern in front | FastAPI has no built-in rate limiting |
| Testing | `TestClient`/`httpx.AsyncClient` + `dependency_overrides` | full request/response cycle without a running server |

### What breaks in production

| Symptom | Cause | Fix |
|---|---|---|
| Throughput plateaus then collapses under load; CPU stays low | Blocking call (`requests`, sync DB driver, `time.sleep`) inside `async def` | Use an async client, or `run_in_threadpool` for the unavoidable sync call |
| "I never got my confirmation email," nothing in any log | `BackgroundTasks` task in flight during a `SIGTERM`/deploy/OOM kill | Move to ARQ/Celery for anything the business needs to actually happen |
| 500 response body contains a table name or stack frame | No global exception handler, or a naive one that returns `str(exc)` | Global `Exception` handler: log full detail server-side, return generic body + correlation id |
| Client expected `400`, got `422`, confused their own error-handling logic | Default `RequestValidationError` behavior | Either document the 422 convention, or override with a custom `exception_handler(RequestValidationError)` mapping to 400 |
| DB session opened twice for one request | Two different dependencies calling `get_db()` without relying on FastAPI's per-request cache | Confirm you're not passing `use_cache=False` unintentionally; verify with a counter in `get_db` during a test |
| Test suite hits the real database | Forgot `app.dependency_overrides[get_db] = get_test_db`, or forgot to `.clear()` it after a previous test | Use a pytest fixture that sets and tears down the override per test, not module-global mutation |
| Field added to an internal model leaks to clients | `response_model` omitted, or endpoint returns a dict/ORM object directly instead of through the model | Always declare `response_model` on anything returning data derived from an internal model |
| New field silently missing from every response after adding it | Added to `response_model`, but the source object/dict never populates it and Pydantic drops it as unset with `exclude_unset=True` on | Check `response_model_exclude_unset` isn't hiding the newly-default-valued field; test with a non-default value |

---

## Tradeoffs & when NOT to use it

- **Don't use `BackgroundTasks` for anything the business would notice missing.** Payments, refunds, provisioning, anything with a durability requirement — that's a queue's job, not this API's convenience feature.
- **Don't reach for `async def` reflexively.** If your handler only calls synchronous, CPU-light code with no I/O, a plain `def` handler dispatched to the threadpool is simpler and just as fast; the async model only pays off when you're actually waiting on I/O (DB, HTTP, disk) and can use an async-native client for it. Mixing a blocking call into `async def` is strictly worse than just declaring the function `def` and letting FastAPI thread-pool it for you.
- **Don't treat `HTTPException` and unhandled exceptions as interchangeable.** Deliberately raised business errors should be `HTTPException` or a custom exception with its own handler; anything else falling through to the generic 500 handler should be treated as a bug to fix, not a normal code path.
- **Don't skip `extra="forbid"` on anything security- or billing-adjacent.** The default `"ignore"` silently drops unexpected fields rather than rejecting the request, which can hide a client bug or a probing attacker.
- **For CPU-bound work, FastAPI's async model adds complexity without benefit** — use worker processes and treat FastAPI purely as the thin, synchronous-feeling API shell in front of them.
- **For a small internal tool with one team and no plans to scale**, the DI ceremony (separate dependency functions, override wiring) can be more structure than the problem needs — a simpler synchronous Flask app is a legitimate choice, and pretending otherwise for resume-driven-development reasons is a real anti-pattern worth naming if asked "would you always choose FastAPI."

---

## Interview questions

### Q1 — What is FastAPI actually built on, and what does each piece contribute?
**Testing:** whether you understand FastAPI as thin glue rather than a monolith.
**Answer:** Starlette provides the ASGI web layer — routing, middleware, WebSockets, the background-task primitive, request/response objects. Pydantic provides parsing, validation, serialization, and (via `pydantic-settings`) config management. FastAPI's own contribution is reading type hints off your function signature and wiring them simultaneously to Pydantic validation, Pydantic serialization, OpenAPI schema generation, and its dependency-injection graph. Remove FastAPI and you still have a working ASGI app with Starlette; remove Starlette and FastAPI has no transport layer at all.
**Follow-up trap:** *"So what would you lose moving to raw Starlette?"* — automatic request validation, automatic OpenAPI docs, and the `Depends()` DI system. You'd hand-write everything FastAPI currently derives from type hints. People who haven't actually used Starlette directly tend to underestimate how much smaller its surface area is.

### Q2 — Why does `response_model` matter for security, not just formatting?
**Testing:** whether "validation" is understood as bidirectional.
**Answer:** `response_model` filters the *return value* against a Pydantic schema before serialization, independent of what the function actually returns. If your endpoint returns a full DB row (including a password hash or internal flag) but `response_model` only declares public fields, those extra fields are dropped, not leaked. It's the most common accidental way sensitive fields get exposed — someone adds a column, forgets it's returned via `.dict()` or an ORM object directly, and a schema-less endpoint ships it straight to the client.
**Follow-up trap:** *"What if I return a dict, not the ORM object?"* — same protection applies; FastAPI validates and filters whatever you return against `response_model` regardless of its origin type, as long as it can be coerced. The trap is thinking `response_model` is just a docs annotation — it's an active runtime filter.

### Q3 — Why is a failed request validation a 422 and not a 400?
**Testing:** knowledge of a specific, cited, non-obvious framework decision.
**Answer:** FastAPI reserves 400 for requests that are structurally malformed (can't even be parsed), and uses 422 (`Unprocessable Entity`, defined via WebDAV/RFC 4918) for requests that are syntactically fine but fail semantic/schema validation — wrong type, missing required field, failed a Pydantic validator. It's raised as `RequestValidationError` automatically, before your endpoint code runs.
**Follow-up trap:** *"A client team is annoyed they get 422s where they expected 400s across your whole API surface. What do you do?"* — add a global `@app.exception_handler(RequestValidationError)` that remaps to 400 (or whatever your API contract says), rather than telling every client to special-case 422. Know that this is one line, not a redesign.

### Q4 — Walk through what makes FastAPI actually testable, mechanically.
**Testing:** whether "testable" is understood as a specific mechanism, not a vibe.
**Answer:** Every external dependency an endpoint needs — a DB session, the current user, a settings object, a rate limiter — is expressed as a `Depends()` callable rather than imported at module scope. `app.dependency_overrides` is a dict keyed by the original callable; setting `app.dependency_overrides[get_db] = get_test_db` swaps it for the test's version for as long as the override is set, with no monkeypatching or import-path mocking. Combined with `TestClient`, you get full request/response-cycle tests against fakes.
**Follow-up trap:** *"What happens if you forget to `.clear()` the overrides between test modules?"* — overrides persist on the `app` object, so a later test module can silently run against a leftover fake dependency from an earlier one. Use a fixture that overrides and tears down per test (or per module) rather than mutating the dict at import time.

### Q5 — Explain the teardown order for chained `yield` dependencies.
**Testing:** whether you've actually hit a bug here, not just read the docs once.
**Answer:** Setup runs in dependency order (a dependency's own sub-dependencies resolve first). Teardown, the code after `yield`, runs in the *reverse* order — LIFO — managed by an `AsyncExitStack`. If C depends on B depends on A, setup is A, B, C; teardown is C, B, A. This matters because B's cleanup code might still need A to be alive; tearing down in setup order would break that.
**Follow-up trap:** *"Where does the teardown code run relative to the response being sent?"* — after. The client already has the response by the time `finally`/post-yield code executes, so exceptions raised during teardown don't change the response the client received, but they can still fail to release a lock or a connection if you don't handle them — a common source of connection-pool exhaustion nobody notices until the pool is empty.

### Q6 — A FastAPI service's throughput collapses under load, but CPU utilization stays low. Diagnose it.
**Testing:** the highest-signal question in this module — pattern recognition for the most common real incident.
**Answer:** Classic symptom of a blocking call inside an `async def` handler — a synchronous HTTP client, a non-async DB driver, `time.sleep`, blocking file I/O. It blocks the single event loop entirely, not just the calling request, so every other concurrent request queues behind it. p99 latency and error rate climb as concurrency rises, throughput plateaus and then falls, and CPU stays idle because the process is blocked on I/O, not computing. Teams that misdiagnose this add more replicas or CPU and see no improvement, because the bottleneck is per-process event-loop starvation, not compute capacity.
**Follow-up trap:** *"You audit the code and find no obviously synchronous call. What else could cause it?"* — a synchronous dependency buried several layers deep (a logging handler that does a blocking network call, a metrics client without an async variant, a JSON serializer doing something expensive synchronously on a large payload), or a `def` endpoint accidentally calling `asyncio.run()` internally, which is illegal inside a running loop and can manifest as intermittent stalls rather than a clean crash. Also check whether the threadpool itself (default cap around 40) is saturated by legitimately sync endpoints, starving unrelated sync work even though the async path is clean.

### Q7 — What is `BackgroundTasks` actually good for, and where is it a landmine?
**Testing:** whether "background task" is understood as in-process, not durable.
**Answer:** Good for cheap, best-effort, non-critical work that should happen after the response is returned — logging an analytics event, sending a non-critical notification, warming a cache entry. Landmine: it runs in the same process, with no persistence, broker, or retry. A `SIGTERM` (rolling deploy, autoscale-down, OOM) during execution drops the task silently, with no record it ever ran, and no error surfaces anywhere because the process producing the error is the one that just died.
**Follow-up trap:** *"How would you even detect this is happening in production?"* — you mostly can't from inside the app, because there's no log of the dropped work. You detect it externally: a support ticket rate for "didn't receive X" that correlates with deploy frequency, or a reconciliation job comparing expected side effects (emails sent, webhooks fired) against a source of truth. That mismatch, not an in-app signal, is usually what surfaces the bug.

### Q8 — Design the exception-handling strategy for a public API. What's the shape of a 500 response?
**Testing:** whether "don't leak internals" is a practiced habit, not a slogan.
**Answer:** Three tiers: `HTTPException` for expected business failures with the right status code and a client-safe message; custom domain exceptions with their own `@app.exception_handler` for cases you want mapped to a specific status without polluting business logic with HTTP concerns; a catch-all `@app.exception_handler(Exception)` that logs the full exception server-side with a generated correlation id and returns a generic body — `{"detail": "internal server error", "error_id": "<uuid>"}` — with no stack trace, table name, file path, or library version ever reaching the client.
**Follow-up trap:** *"A user reports a bug and gives you the error_id — walk me through finding it."* — grep your structured logs for that id, which was logged alongside the full exception and traceback server-side at the moment of the 500. This is the entire point of generating and returning it: it's a lookup key, not a leak.

### Q9 — Why does FastAPI dispatch sync `def` endpoints to a threadpool instead of just calling them directly?
**Testing:** understanding of *why* the sync/async split exists, not just that it does.
**Answer:** Calling a blocking synchronous function directly on the event loop would block it exactly like the async-endpoint failure mode — so Starlette runs `def` handlers in a threadpool and awaits the result, isolating blocking work from the loop by construction. This lets libraries with no async story (many ORMs historically, `requests`, most legacy SDKs) work inside FastAPI without a rewrite, at the cost of a finite thread pool (commonly capped around 40 threads) that can itself become the bottleneck under enough concurrent sync load.
**Follow-up trap:** *"So should I just make everything `def` to be safe?"* — no; you lose the concurrency benefit for anything that's actually I/O-bound and could be handled by a single event loop far more cheaply than 40 OS threads. The right rule is: `async def` with async-native clients for I/O-bound work, `def` for CPU-light synchronous work or unavoidable blocking libraries, and never a blocking call inside `async def`.

### Q10 — Compare `HTTPException` and a custom exception with its own handler. When would you use each?
**Answer:** `HTTPException` is the quick path for one-off business failures at the call site — `raise HTTPException(404, "not found")` — and is fine when the error is genuinely tied to that one endpoint. A custom exception (`InsufficientBalanceError`) with a registered `@app.exception_handler` decouples business logic from HTTP entirely, so a service class can raise it without importing FastAPI, is reusable outside a web context (CLI, worker), and centralizes the status-code mapping in one place instead of scattering `raise HTTPException(402, ...)` at every call site that might trigger it.
**Follow-up trap:** *"Your service layer is now used by both the API and a Celery worker. Which pattern survives that refactor?"* — the custom exception, because it has no dependency on `fastapi` at all; `HTTPException` raised from inside a Celery task is meaningless and will crash the worker or require an unnecessary catch-and-translate at the boundary.

### Q11 — What does `model_config = ConfigDict(extra="forbid")` protect against, and why isn't it the default?
**Answer:** By default (`extra="ignore"`), Pydantic silently drops fields not declared on the model, which means a client sending `{"email": "x", "is_admin": true}` to a signup endpoint that never declared `is_admin` just has it quietly discarded rather than rejected — usually fine, but on anything security-adjacent it can mask a mass-assignment attempt or a client-side bug where a field is misspelled and silently vanishes instead of erroring. `extra="forbid"` turns any unexpected field into a `422`. It isn't the default because most APIs want to tolerate forward-compatible extra fields from clients without breaking; forbidding is a deliberate, narrower choice for models that shouldn't accept anything undeclared.
**Follow-up trap:** *"Won't `extra=\"forbid\"` break rolling deploys where a newer client sends a field an older server doesn't know yet?"* — yes, that's the real cost, and it's why you apply it selectively (auth, billing, admin-only mutation endpoints) rather than globally across a versioned public API with independently-deployed clients.

### Q12 — When would you deliberately choose Litestar or Django's async views over FastAPI?
**Testing:** whether FastAPI is a reflex or a considered choice.
**Answer:** Litestar, for a larger service where you want a more opinionated, structured DI container and less freedom to build an inconsistent dependency graph across dozens of contributors. Django's async views, when the team already has significant investment in Django's ORM, admin panel, and migration tooling, and rewriting for FastAPI would mean rebuilding that tooling for marginal async gains. Neither choice is about FastAPI being deficient; both are about matching the framework to existing team investment and service scale.
**Follow-up trap:** *"Isn't that just 'it depends' with extra steps?"* — no, name the concrete axis: team's existing ORM/tooling investment, number of contributors touching one service (structure vs freedom tradeoff), and whether the workload is genuinely I/O-bound enough for async to matter at all. "It depends" without naming the variable is the red flag; naming the variable is the answer.

---

## Red flags that fail you

- Saying `response_model` is "just for the docs" and missing that it actively filters output data.
- Not knowing why validation errors are 422, or not knowing you can remap them.
- Describing `BackgroundTasks` as a job queue, or recommending it for payments/durability-sensitive work.
- Blaming a throughput collapse on "we need more servers" without checking for a blocking call in an async handler.
- Returning `str(exc)` or a raw traceback in a production error response.
- Not knowing dependency results are cached per request, or not knowing how to override them in tests.
- Claiming FastAPI "handles the database" or "handles background jobs" — it does neither; it hands you the primitives to wire your own.
- Treating `async def` as strictly faster than `def` in all cases, with no mention of blocking calls being the actual risk.

---

## Cheat card

```
STACK        Starlette (ASGI, routing, middleware, WebSockets, BackgroundTasks)
             + Pydantic (validate/serialize/settings) + type hints → DI + OpenAPI

PYDANTIC     response_model FILTERS output — real data-leak control, not docs sugar
             v2 Rust core: ~4x-50x faster than v1.9 (model-shape dependent), ~17x cited headline
             extra="forbid" rejects unknown fields; default is "ignore" (silent drop)
             @field_validator (per-field) / @model_validator (cross-field, mode="after")

DI           Depends() results CACHED per request (same callable = one call)
             yield deps: teardown is LIFO via AsyncExitStack, runs AFTER response sent
             app.dependency_overrides[dep] = fake — THIS is why FastAPI is testable

ERRORS       HTTPException = deliberate, any status you choose
             RequestValidationError = automatic, ALWAYS 422 (not 400) — WebDAV/RFC4918
             unhandled Exception → global handler: log full detail, return generic + error_id
             NEVER return str(exc) or a traceback to the client

BACKGROUND   BackgroundTasks = same process, no broker, no retry, no durability
             SIGTERM mid-task = task silently dropped, no log, no trace
             durable work → ARQ (asyncio-native, Redis) or Celery (multi-broker/lang)

ASYNC/SYNC   async def → event loop directly; def → threadpool (default ~40 threads)
             blocking call in async def → ENTIRE loop stalls, not just that request
             symptom: throughput plateaus/collapses under load, CPU stays LOW/idle
             fix: async client (httpx.AsyncClient) or run_in_threadpool(sync_fn, ...)

WRONG TOOL   CPU-bound work (no async benefit) · Django-invested teams · gRPC-internal
             mesh services · multi-language worker interop (needs Celery/broker, not BG tasks)
```

## Sources

- [Response Model - Return Type — FastAPI](https://fastapi.tiangolo.com/tutorial/response-model/) — accessed 2026-08-01
- [Dependencies with yield — FastAPI](https://fastapi.tiangolo.com/tutorial/dependencies/dependencies-with-yield/) — accessed 2026-08-01
- [Pydantic V2: Supercharge Your Data Validation with Rust](https://medium.com/@akaashhazarika/pydantic-v2-supercharge-your-data-validation-with-rust-95ae490b5e46) — accessed 2026-08-01
- [Obtain a 5x speedup for free by upgrading to Pydantic v2 — The Data Quarry](https://thedataquarry.com/blog/why-pydantic-v2-matters/) — accessed 2026-08-01
- [FastAPI Background Tasks: Celery vs ARQ vs RQ (2026 Benchmarks & Decision Guide)](https://medium.com/@rameshkannanyt0078/fastapi-background-tasks-celery-vs-arq-vs-rq-2026-benchmarks-decision-guide-f99598aa21eb) — accessed 2026-08-01
- [Understanding Concurrency in FastAPI](https://bhaveshparvatkar.medium.com/understanding-concurrency-in-fastapi-fbbe09dc4979) — accessed 2026-08-01
- [Shippo: why is my FastAPI throughput so low](https://goshippo.com/blog/why-is-my-fastapi-throughput-so-low) — accessed 2026-08-01
- [Inside FastAPI's Dependency Injection: From Registration to Teardown](https://medium.com/@chootzesien/inside-fastapis-dependency-injection-from-registration-to-teardown-d55ee866d22e) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created

## The 30-second version

FastAPI is thin glue over Starlette (the ASGI/web layer) and Pydantic (validation, serialization, settings) — its own contribution is reading your type hints once and wiring them simultaneously to request validation, response filtering, OpenAPI docs, and a dependency-injection graph. `response_model` is a real security control: it filters whatever your function returns down to the declared schema, which is why a leaked internal field is usually a missing `response_model`, not a missing manual filter. `Depends()` caches per request and its `yield`-based teardown runs LIFO after the response is sent; overriding those callables in `app.dependency_overrides` is the entire reason FastAPI is considered testable. The two production traps that actually bite teams: a blocking call inside `async def` stalls the whole event loop and shows up as throughput collapsing under load while CPU stays idle, and `BackgroundTasks` is in-process and non-durable, so anything the business needs to actually happen belongs in a real queue like ARQ or Celery, not FastAPI's background-task convenience feature.
