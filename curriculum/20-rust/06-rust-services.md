# Building a Service: axum, sqlx, tracing, Docker, and Deploying It

> **Track:** T20 Rust · **Time:** 2.5h · **Prereqs:** `T20-rust-ownership`, `T20-rust-async` (Tokio, futures, `spawn`/`spawn_blocking`, cancellation-by-drop assumed known), `T21-architecture-principles` · **Updated:** 2026-08-05
> **Module id:** `T20-rust-services` · **Tags:** core, critical, backend, production
> **Lab:** `labs/rust/06-rust-services/`

## The 30-second version

A production Rust HTTP service is four crates and one Dockerfile: axum 0.8.9 for routing and extraction, sqlx 0.9.0 for compile-time-checked SQL against a connection pool, `tracing` 0.1.44 plus `tracing-subscriber` 0.3.23 for structured spans that survive being moved between Tokio worker threads, and a multi-stage build that ends in a distroless base with a 3.4 MiB stripped binary. axum is not a framework in the Spring sense: a `Router` is a `tower::Service<Request, Response = Response, Error = Infallible>`, handlers are plain `async fn`s whose arguments are extractors resolved left-to-right through `FromRequestParts`, and every piece of middleware is a `tower::Layer`, which means the entire ecosystem of tower and tower-http composes but also that ordering bugs are silent rather than loud. The three decisions that actually bite are pool sizing (sqlx defaults to `max_connections = 10` and `acquire_timeout = 30s`, which under load turns a slow query into a 30-second queue rather than a fast 503), middleware ordering (`.layer()` on a `Router` applies inside-out and only to routes declared *before* it, so auth added in the wrong place silently applies to nothing), and the base image (a naive `FROM rust:1.97` single-stage build ships a 700 MB-plus image and a fully static musl build can cost you a multiple of your throughput because musl's allocator serializes multithreaded `malloc`). Measured on 2 vCPU with Rust 1.97.1: the whole service idles at **3.1 MiB RSS** with 3 threads, cold-builds in 117 s and warm-builds in 24 s with `cargo-chef` layer caching, which is roughly a 5x CI win and a 50-100x memory win against the equivalent Spring Boot service.

## Why this gets asked

Nobody asks this to find out whether you can write a route handler. They ask because Rust services fail differently from JVM and Go services, and the person interviewing you has been paged by one of four incidents.

The first is **pool exhaustion presenting as a total outage**. A downstream query goes from 3 ms to 300 ms, every pooled connection is checked out, `acquire()` starts queueing, and because sqlx's default `acquire_timeout` is 30 seconds every request now takes 30 seconds and then fails. The healthcheck endpoint, if it touches the database, also takes 30 seconds, so Kubernetes kills the pod, so the remaining pods take more load, so they exhaust faster. Ten replicas go down in ninety seconds because one query got slow. The interviewer wants to hear you say "cap the acquire timeout below the client timeout, and never put the database in the liveness probe."

The second is **the middleware that ran on nothing**. `Router::layer` only wraps routes that already exist on the router, and `Router::layer` also wraps the fallback, and both facts have burned people. Someone writes `Router::new().layer(RequireAuth).route("/admin", get(admin))` and ships an unauthenticated admin endpoint, with no compile error, no runtime warning, and a green test suite if the tests exercise the handler directly. This is a security incident that produces zero symptoms until an audit.

The third is **the 700 MB image and the 25-minute build**. Rust's compile times are the standard objection to Rust in a service org, and the honest answer is that a naive Dockerfile makes them dramatically worse than they need to be, because `COPY . .` invalidates the layer cache on every source change and Cargo then rebuilds all 179 crates in the dependency tree. Someone who has actually shipped Rust knows `cargo-chef` or a BuildKit cache mount, knows what each buys and what it costs, and knows the numbers.

The fourth is **the musl trap**. Someone reads "static binary, tiny image" and switches to `x86_64-unknown-linux-musl` plus `FROM alpine`. The image drops from 90 MB to 12 MB and throughput drops by a factor that has been measured as high as 7x on allocation-heavy workloads, because musl's `malloc` serializes far harder than glibc's under multithreaded contention. The symptom is a service that benchmarks fine on one core and falls apart at 8, with `perf` showing time in `__lock`/`malloc`. Knowing this distinguishes someone who has deployed Rust from someone who has read a blog post about it.

Underneath all four is the real question: you already ship Spring Boot and FastAPI and Go services. Can you articulate what Rust changes about operating a service, in numbers, and where it is the wrong choice?

---

## Lineage: past → present → future

**What came before.** Rust's first serious web frameworks were built on `futures 0.1` and `hyper 0.11`/`0.12`, and they were miserable in specific, documented ways. Iron (2014) and Nickel were synchronous, thread-per-request, and died when async arrived. Rocket (2016) chose ergonomics and paid for it by requiring nightly Rust for five years, until Rocket 0.5.0 shipped on stable in November 2023, by which time the market had moved. Actix-web (2017) was the fast one, held the TechEmpower top slot for years, and took two reputational hits: the actor model it was built on turned out to be the wrong abstraction for HTTP and was largely removed in 1.0 (2019), and the maintainer's response to the 2020 `unsafe` audit controversy (a documented soundness hole where a `&mut` was handed out from an `&`) led to him archiving the project in January 2020 before the community took it over. Warp (2019, by hyper's author Sean McArthur) got the composition story right by building routes out of `Filter` combinators, and the pain that killed it as a default choice was exactly the pain that killed `futures 0.1` combinators: the type of a route was a deeply nested generic like `And<And<Or<...>, ...>, ...>`, so a compile error in one filter produced hundreds of lines naming types no human had written, and `warp::Rejection` made "did this route not match, or did it match and fail auth?" genuinely hard to answer. On the database side the sequence was `rust-postgres` (raw, synchronous, 2015), Diesel (2016, a full compile-time-checked query DSL with a schema-derived type per table), and then sqlx (2019-2020), whose bet was that people wanted SQL, not a DSL, and would accept a compile-time database connection to get type checking on it. Before all of this, the thing an engineer at this level actually did was Spring Boot or Django or Express, and the pain that motivates any of this is 300 MB of RSS per replica, 4-second cold starts, and GC pauses in the tail.

**Where it stands now.** axum (first released July 2021, by the Tokio team) won by refusing to invent anything: a handler is an `async fn`, a route tree is a `Router`, and everything else is `tower`. It is `Service`-based rather than combinator-based, so error messages name your types instead of generated ones, and the `#[debug_handler]` macro exists precisely because the one remaining bad error message (a handler that fails the `Handler` trait bound) needed a dedicated tool. Current stable is **axum 0.8.9**, published **14 April 2026**, with an MSRV of **1.80**; the 0.8.0 release on **1 January 2025** made the breaking change everyone remembers, moving path parameters from `/:id` and `/*rest` to `/{id}` and `/{*rest}` to match the OpenAPI and `matchit` conventions. axum sits on **hyper 1.11.0** (20 July 2026) and **tower 0.5.3**; **tower-http 0.7.0** landed **15 June 2026** and added a CSRF middleware ported from Go 1.25's cross-origin protection scheme plus body *deadline* (as opposed to idle-timeout) layers. sqlx reached **0.9.0** on **6 May 2026** (crates.io publish 21 May 2026) with an MSRV of **1.94.0**, and that release both added per-crate `sqlx.toml` configuration and made a batch of breaking changes, the loudest being that every `query*()` function now takes `impl SqlSafeStr`, implemented only for `&'static str` and the explicit `AssertSqlSafe` wrapper, which is a deliberate speed bump against `format!`-built SQL. sqlx also announced the repository's move from `launchbadge/sqlx` to the `transact-rs` organisation. The live disagreements are real. First, sqlx versus Diesel is not settled: sqlx's compile-time checking needs a live database (or a checked-in `.sqlx/` directory) at build time, which people either accept as a small CI cost or reject as a hard dependency in the build graph; Diesel needs no database at compile time but makes you express queries in a DSL and generate a `schema.rs`, and Diesel's async story (`diesel-async`) is a separate crate rather than the default. Second, whether ORMs belong in Rust at all: SeaORM exists, is built on sqlx, and is the closest thing to Hibernate/SQLAlchemy in the ecosystem, and the majority position among people running Rust in production is that Rust's type system already gives you most of what an ORM's mapping layer buys, so the ORM's costs (an extra abstraction, worse generated SQL, a slower compile) are not paid back. Third, `tracing` versus `log`: `log` is still the interoperability floor and `tracing` still emits into it via `tracing-log`, but for anything async `tracing` won on the merits and the argument is over. Fourth, OpenTelemetry Rust is genuinely half-mature: as of the **0.32** release line (opentelemetry 0.32.0, May 2026; tracing-opentelemetry 0.33.0, May 2026), the **Logs and Metrics API/SDK are marked Stable while Traces are still Beta**, which is the reverse of the maturity order in every other language, and it means the crate you most want for a service is the least stable one.

**Where it's heading.** High confidence: axum 0.9 is in progress on `main` and the breaking changes are already visible in the changelog, so plan for them. `axum::serve` will apply hyper's default `header_read_timeout` (closing a slowloris hole that you currently have to close yourself), router fallbacks will be properly merged for nested routers, `#[from_request(via(Extractor))]` will propagate the inner extractor's rejection type instead of erasing it to `Response`, and a `serve::Executor` trait will let you control how connection tasks are spawned, which is what you need to attach a span or a per-connection budget. `ListenerExt::limit_connections` is added, which means the concurrency cap moves below the `Service` layer where it belongs. Medium confidence: sqlx's `sqlx.toml` will become the normal way to configure multi-database and multi-tenant workspaces within a year, because the alternative (environment-variable gymnastics around `DATABASE_URL`) is bad enough that the feature will pull people forward; expect the `sqlx-toml` feature to stop being opt-in eventually. Medium confidence: OpenTelemetry Rust traces reach Stable in the 0.34-0.36 window, at which point the `tracing` → OTel bridge stops being the thing you pin nervously. Lower confidence and explicitly speculative: the "one true" Rust service framework question stays open, because Pavex (compile-time-generated, no runtime reflection) and Loco (a Rails-shaped batteries-included framework) are both credible and both making the argument that axum's minimalism pushes too much wiring onto the application; I would not bet on either displacing axum inside three years, and I would bet against a Rust equivalent of Spring's ecosystem gravity existing at all, because the language's compile-time story makes dependency-injection containers largely pointless. Also speculative: `io_uring`-backed HTTP serving (via `tokio-uring`/`compio`) is real but not the default path, and the honest statement for an interview is "opt-in, Linux-only, and it fights the poll-based `Future` interface at the buffer-ownership boundary."

---

## Mental model

```
THE WHOLE SERVICE, AS ONE tower::Service

  TcpListener  --accept-->  hyper conn task (one tokio task per connection)
                                    |
                                    v
   +--------------------------------------------------------------+
   |  Router  ==  tower::Service<Request<Body>,                    |
   |                             Response = Response<Body>,        |
   |                             Error = Infallible>               |
   +--------------------------------------------------------------+
        ^  Error = Infallible is the load-bearing detail.
        |  axum has NO error channel. Every failure is a Response.
        |  A tower middleware whose Error is NOT Infallible does not
        |  compose without HandleErrorLayer (or tower-http's version).


REQUEST PATH, ONE HANDLER

  Request<Body>
      |
      | [layers, outermost first]
      v
  TraceLayer -> RequestIdLayer -> ConcurrencyLimit -> Timeout -> Auth
      |
      | routing (matchit radix tree on the path)
      v
  MethodRouter (GET/POST/...) -> Handler
      |
      | extractor resolution, LEFT TO RIGHT
      v
  async fn h(                                  Parts = head only
      State(st): State<AppState>,   <- FromRequestParts  (&mut Parts)
      Path(id): Path<Uuid>,         <- FromRequestParts
      headers: HeaderMap,           <- FromRequestParts
      Json(body): Json<Create>,     <- FromRequest  (CONSUMES the body)
  ) -> Result<Json<Out>, ApiError>
      |                                   ^^^^^^^^ LAST ARGUMENT ONLY.
      |                                   The body can only be taken once,
      |                                   so only the tail position may take it.
      v
  Ok(Json(..))  --IntoResponse-->  Response
  Err(ApiError) --IntoResponse-->  Response   <- your error enum, your status


THE ORDERING SURPRISE, DRAWN OUT

  ServiceBuilder::new()          Router::new()
      .layer(A)                      .route(...)
      .layer(B)                      .layer(A)
      .service(router)               .layer(B)

  A(B(router))                   B(A(router))
  A sees request FIRST           B sees request FIRST
  "top-down"                     "inside-out"

  Same two lines of code, opposite meaning. This is why the axum docs
  say to use ONE ServiceBuilder and pass it to ONE .layer() call.


THE SHIP

  cargo new  ->  cargo build --release  ->  3.4 MiB stripped binary
                                                 |
   +---------------------------------------------+
   |
   v  multi-stage Dockerfile
  stage 1  FROM rust:1.97-slim   (308 MiB compressed base)
           cargo chef cook       <-- deps only, CACHED layer
           cargo build --release <-- your code, ~24 s
   stage 2 FROM gcr.io/distroless/cc-debian12  (8.75 MiB compressed)
           COPY --from=builder /app/target/release/svc /
   -----------------------------------------------------
   final image ~= 12 MiB compressed, ~26 MB on disk
   runtime RSS = 3.1 MiB idle, 3.5 MiB after 3,000 requests, 3 threads
```

---

## How it actually works

### axum is a thin veneer over `tower::Service`

There is no dependency-injection container, no reflection, no annotation processor, no classpath scan. `tower::Service` is the whole abstraction:

```rust
// tower_service::Service, the entire interface
pub trait Service<Request> {
    type Response;
    type Error;
    type Future: Future<Output = Result<Self::Response, Self::Error>>;

    fn poll_ready(&mut self, cx: &mut Context<'_>) -> Poll<Result<(), Self::Error>>;
    fn call(&mut self, req: Request) -> Self::Future;
}
```

An axum `Router` implements `Service<Request<Body>>` with `Response = Response<Body>` and, critically, **`Error = Infallible`**. That single choice explains most of axum's ergonomics and most of its friction with raw tower middleware.

Because the error type is uninhabited, axum has no error channel at all: everything that can go wrong must already be a `Response` by the time it reaches the router boundary. Handlers return `impl IntoResponse`, extractor failures return a `Rejection` that is `IntoResponse`, and 404 is a fallback route rather than an error. This is why you never write an exception mapper the way you would in Spring (`@ControllerAdvice`) or FastAPI (`app.exception_handler`): the `IntoResponse` impl on your own error enum *is* the exception mapper, and it is checked at compile time.

The friction is that plenty of tower middleware *does* have a real error type. `tower::timeout::TimeoutLayer` produces `Box<dyn Error + Send + Sync>`; `tower::load_shed::LoadShedLayer` produces `Overloaded`. Stacking one of those directly onto a `Router` fails to compile with a bound error about `Error = Infallible`, and there are exactly two fixes. Either wrap the fallible part in `HandleErrorLayer` (which converts the error to a response and restores `Infallible`), or use the tower-http equivalent, which is already infallible by construction. `tower_http::timeout::TimeoutLayer` returns a `408 Request Timeout` response instead of an error, and is the one you want 95% of the time.

`poll_ready` is the half of `Service` that people from Spring and FastAPI have no analogue for, and it is where tower's backpressure lives. A middleware may return `Poll::Pending` from `poll_ready` to say "do not hand me a request yet." `ConcurrencyLimit` uses it to hold a semaphore permit; `Buffer` uses it to bound a queue. The contract is that you must call `poll_ready` until it returns `Ready(Ok(()))` before calling `call`, and a `Service` may panic if you violate it. axum's `Router` is always ready, so this only matters when you write or stack middleware, but "how do you apply backpressure in axum?" is a real interview question and `poll_ready` is the real answer, layered under a `ConcurrencyLimitLayer` plus a `LoadShedLayer` to convert the wait into a fast 503.

### Handlers and the `Handler` trait

```rust
// axum's Handler is implemented for async fns by a macro over arities 1..=16.
// Sketch of the shape (the real impl also carries a marker type M):
impl<F, Fut, S, Res, T1, ..., T16> Handler<(T1, ..., T16), S> for F
where
    F: FnOnce(T1, ..., T16) -> Fut + Clone + Send + 'static,
    Fut: Future<Output = Res> + Send,
    Res: IntoResponse,
    T1..T15: FromRequestParts<S> + Send,
    T16:     FromRequest<S>      + Send,   // <-- only the LAST one
{ ... }
```

Three mechanical consequences, all of which show up as compiler errors people find confusing:

**Step 1. Sixteen extractors, hard cap.** The `all_the_tuples!` macro in `axum-core` generates impls for arities 1 through 16 exactly. A seventeenth argument does not produce "too many arguments"; it produces `the trait bound ...: Handler<_, _> is not satisfied`, which is the same error you get from *any* handler bound failure. If you hit it, group arguments into one custom extractor.

**Step 2. `FromRequestParts` versus `FromRequest`.** These are two traits, not one.

```rust
pub trait FromRequestParts<S>: Sized {
    type Rejection: IntoResponse;
    fn from_request_parts(
        parts: &mut Parts,           // method, uri, version, headers, extensions
        state: &S,
    ) -> impl Future<Output = Result<Self, Self::Rejection>> + Send;
}

pub trait FromRequest<S, M = private::ViaRequest>: Sized {
    type Rejection: IntoResponse;
    fn from_request(
        req: Request,                // parts + BODY
        state: &S,
    ) -> impl Future<Output = Result<Self, Self::Rejection>> + Send;
}
```

`Parts` is the request head with no body. An extractor that only needs the head (`Path`, `Query`, `HeaderMap`, `State`, `Extension`, `Method`, `Uri`, `ConnectInfo`, your own `AuthUser`) implements `FromRequestParts` and takes `&mut Parts`, so any number of them can run in sequence. An extractor that needs the body (`Json`, `Form`, `Bytes`, `String`, `Multipart`, `Request`) implements `FromRequest`, which takes the whole `Request` **by value**, because a body is a stream that can only be consumed once. Only one argument can consume it, and by construction that must be the last one. `Json<T>` in a non-final position produces the same opaque `Handler` bound error, and this is the single most common axum papercut. `#[debug_handler]` exists to turn it into an error that names the offending argument.

**Step 3. Extractors run left to right, and short-circuit.** `from_request_parts` is awaited in argument order. If your `AuthUser` extractor rejects with 401, the extractors to its right never run, and neither does the handler. That is a design tool: put the cheap authorization extractor first and the expensive `Path`-plus-database-lookup extractor second, and you never pay for the lookup on an unauthenticated request. It is also a trap: if you put `Json<T>` before an auth extractor, you have already buffered up to the body limit before deciding the caller is not allowed.

Writing your own extractor is about fifteen lines and is the idiomatic place to put cross-cutting request logic that needs to fail with a specific status:

```rust
// # untested sketch — axum 0.8, checked against the FromRequestParts signature
use axum::{extract::FromRequestParts, http::{request::Parts, StatusCode}};

pub struct AuthUser { pub id: uuid::Uuid, pub scopes: Vec<String> }

pub enum AuthRejection { Missing, Malformed, Expired }

impl axum::response::IntoResponse for AuthRejection {
    fn into_response(self) -> axum::response::Response {
        let (code, msg) = match self {
            AuthRejection::Missing   => (StatusCode::UNAUTHORIZED, "missing bearer token"),
            AuthRejection::Malformed => (StatusCode::UNAUTHORIZED, "malformed bearer token"),
            AuthRejection::Expired   => (StatusCode::UNAUTHORIZED, "token expired"),
        };
        (code, msg).into_response()
    }
}

impl<S> FromRequestParts<S> for AuthUser
where
    S: Send + Sync,
    JwtKeys: axum::extract::FromRef<S>,   // pull just the piece of state we need
{
    type Rejection = AuthRejection;

    async fn from_request_parts(parts: &mut Parts, state: &S) -> Result<Self, Self::Rejection> {
        let keys = JwtKeys::from_ref(state);
        let raw = parts.headers
            .get(axum::http::header::AUTHORIZATION)
            .ok_or(AuthRejection::Missing)?
            .to_str().map_err(|_| AuthRejection::Malformed)?
            .strip_prefix("Bearer ").ok_or(AuthRejection::Malformed)?;
        keys.verify(raw).map_err(|_| AuthRejection::Expired)
    }
}
```

Now `async fn admin(user: AuthUser, ...)` is authenticated, the 401 body is yours, and the type system will not let an unauthenticated handler read `AuthUser`. Contrast Spring's `@PreAuthorize`, which is an annotation checked by an AOP proxy at runtime and silently does nothing if the proxy is bypassed by a self-invocation.

### `State` versus `Extension`: compile-time versus runtime

Both put shared data in reach of every handler. They fail differently, and the difference is the whole argument.

```rust
// # untested sketch
#[derive(Clone)]
struct AppState {
    db: sqlx::PgPool,          // PgPool is already an Arc internally: cheap to clone
    http: reqwest::Client,     // also internally Arc'd
    cfg: Arc<Config>,          // wrap your own types
}

let app = Router::new()
    .route("/users/{id}", get(get_user))
    .with_state(AppState { db, http, cfg });
//   ^ changes the type from Router<AppState> to Router<()>.
//     A Router<S> with S != () cannot be passed to axum::serve.
```

`State<AppState>` is checked at compile time. The `Router<S>` type parameter tracks which state the router still needs; `with_state` is what discharges it. Forget it and `axum::serve(listener, app)` does not compile, because `serve` requires `Router<()>`. Ask for `State<Wrong>` in a handler and it does not compile. This is the equivalent of Spring failing at *compile* time instead of throwing `NoSuchBeanDefinitionException` on startup.

`Extension<T>` is a typed slot in `http::Extensions`, a `HashMap<TypeId, Box<dyn Any>>` carried on the request. Nothing checks that it was inserted. `Extension<Foo>`'s rejection when the value is missing is a **500 Internal Server Error** with the message `Missing request extension: Extension of type 'Foo' was not found. Perhaps you forgot to add it? See axum::Extension.` That is a runtime failure discovered in production, and it is why `State` is the default and `Extension` is for the case `State` cannot express: data inserted *per request by middleware*, such as a request id, a trace id, or the result of an auth layer that runs as a `Layer` rather than an extractor.

Substates use `FromRef`, which is what lets one handler ask for `State<PgPool>` while another asks for `State<Arc<Config>>` off the same `AppState`:

```rust
// # untested sketch
use axum::extract::FromRef;

#[derive(Clone, FromRef)]      // derive generates FromRef<AppState> for each field
struct AppState { db: PgPool, cfg: Arc<Config> }

async fn h(State(db): State<PgPool>) { /* ... */ }
```

The cost model matters: `with_state` clones the state **once per request**, so every field must be cheap to clone. `PgPool` and `reqwest::Client` are already `Arc` inside and clone in a few nanoseconds; a `Vec<String>` of 10,000 entries clones 10,000 allocations per request. The rule is: everything in `AppState` is `Arc`-shaped or a handle.

### Middleware, `ServiceBuilder`, and why the order surprises people

There are three ways to add middleware and they compose in two different directions.

```rust
// # untested sketch
// (a) Router::layer, chained. INSIDE-OUT.
let app = Router::new()
    .route("/x", get(h))
    .layer(A)     // wraps the router:      A(router)
    .layer(B);    // wraps THAT:            B(A(router))
// Request order: B, then A, then handler.

// (b) ServiceBuilder, one .layer() call. TOP-DOWN.
let app = Router::new()
    .route("/x", get(h))
    .layer(
        ServiceBuilder::new()
            .layer(A)     // A(B(router))
            .layer(B),
    );
// Request order: A, then B, then handler.
```

Both snippets are three lines and look identical in review. tower's own docs state the `ServiceBuilder` rule plainly: "Layers that are added first will be called with the request first. The argument to `service` will be last to see the request." `Router::layer` wraps whatever the router currently is, so chained calls nest the other way. **The convention that avoids the whole problem is: build exactly one `ServiceBuilder` and pass it to exactly one `.layer()` call.** axum's own middleware docs recommend this.

The genuinely dangerous ordering rules are the two that produce no error at all:

**Test 1 — middleware applies only to routes declared before it.** From axum's `Router::layer` docs: "Note that the middleware is only applied to existing routes. So you have to first add your routes (and / or fallback) and then call `layer` afterwards. Additional routes added after `layer` is called will not have the middleware added." So this ships an unauthenticated endpoint:

```rust
// # untested sketch — THIS IS THE BUG
let app = Router::new()
    .layer(RequireAuthLayer::new())      // wraps an EMPTY router
    .route("/admin/keys", get(dump_keys));   // added after; NOT wrapped
```

It compiles, it runs, `GET /admin/keys` returns 200 with no token, and the only way to catch it is an integration test that hits the route over HTTP without credentials. Write that test. `Router::route_layer` panics if no routes have been declared yet, precisely because this bug was common enough to warrant a guard, but `Router::layer` does not panic because wrapping an empty router is legitimate when you later `merge` into it.

**Test 2 — `layer` versus `route_layer` for anything that rejects.** `Router::layer` also wraps the fallback (look at the implementation: it maps `catch_all_fallback` through the layer too). So an auth layer added with `.layer()` turns every 404 into a 401, which leaks the existence of your route table in reverse: an attacker probing paths gets 401 for everything and learns nothing, which sounds good until your monitoring shows a 401 spike from a typo and you spend an hour on a phantom auth outage. `Router::route_layer` runs the layer **only if the request matched a route**, which is exactly what you want for authorization. The axum docs say this in one sentence: "This is useful for middleware that returns early (such as authorization) which might otherwise convert a `404 Not Found` into a `401 Unauthorized`."

**Test 3 — middleware runs after routing.** axum's docs are explicit: middleware added with `Router::layer` "will run _after_ routing and thus cannot be used to rewrite the request URI." If you need URI rewriting (a legacy path alias, a tenant prefix strip), it has to go outside the router, applied to the service you hand to `axum::serve`, not to the `Router`.

The stack I would actually ship, in the order that is correct:

```rust
// # untested sketch — axum 0.8.9 / tower 0.5.3 / tower-http 0.6-0.7
use std::time::Duration;
use tower::ServiceBuilder;
use tower_http::{
    catch_panic::CatchPanicLayer, compression::CompressionLayer,
    request_id::{MakeRequestUuid, PropagateRequestIdLayer, SetRequestIdLayer},
    timeout::TimeoutLayer, trace::TraceLayer,
};

let middleware = ServiceBuilder::new()
    // 1. outermost: set an id BEFORE anything can log
    .layer(SetRequestIdLayer::x_request_id(MakeRequestUuid))
    // 2. tracing span opens here, so it captures everything below
    .layer(TraceLayer::new_for_http())
    // 3. a panic below this becomes 500, not a dropped connection
    .layer(CatchPanicLayer::new())
    // 4. shed before you queue: fail fast at the edge
    .layer(tower::load_shed::LoadShedLayer::new())
    .layer(tower::limit::ConcurrencyLimitLayer::new(512))
    // 5. server-side deadline, shorter than the client's
    .layer(TimeoutLayer::new(Duration::from_secs(10)))
    .layer(CompressionLayer::new())
    .layer(PropagateRequestIdLayer::x_request_id());

let app = Router::new()
    .route("/healthz", get(live))          // no auth, no db
    .route("/readyz", get(ready))          // no auth, touches db
    .nest("/v1", api_routes())             // auth applied inside via route_layer
    .fallback(not_found)
    .layer(middleware)                     // ONE call, ONE builder
    .with_state(state);
```

Two details in that stack that are load-bearing. `SetRequestIdLayer` must be outermost so the id exists before `TraceLayer` opens its span. `CatchPanicLayer` must be *inside* the trace layer, or a panic escapes without the span being closed and you get a trace with a missing end. And `ConcurrencyLimitLayer` without `LoadShedLayer` above it converts overload into an unbounded wait rather than a fast 503, which is the classic way a rate limit makes an incident worse.

`middleware::from_fn` is the ergonomic escape hatch when a full `Layer` impl is overkill:

```rust
// # untested sketch
use axum::{extract::Request, middleware::Next, response::Response};

async fn add_server_timing(req: Request, next: Next) -> Response {
    let start = std::time::Instant::now();
    let mut res = next.run(req).await;
    let ms = start.elapsed().as_secs_f64() * 1000.0;
    res.headers_mut().insert(
        "server-timing",
        format!("app;dur={ms:.1}").parse().unwrap(),
    );
    res
}
// .layer(axum::middleware::from_fn(add_server_timing))
// .layer(axum::middleware::from_fn_with_state(state.clone(), f))  // needs state
```

`from_fn` costs one boxed future per request relative to a hand-written `Layer`. At the scale where that matters (100k+ rps per core), write the `Layer`; below it, do not.

### Errors: `IntoResponse` is your exception mapper

```rust
// # untested sketch — the shape I would ship
use axum::{http::StatusCode, response::{IntoResponse, Response}, Json};
use serde_json::json;

#[derive(Debug, thiserror::Error)]
pub enum ApiError {
    #[error("not found")]                 NotFound,
    #[error("conflict: {0}")]             Conflict(String),
    #[error("validation failed")]         Validation(Vec<FieldError>),
    #[error("upstream unavailable")]      Upstream(#[source] reqwest::Error),
    #[error(transparent)]                 Db(#[from] sqlx::Error),
}

impl IntoResponse for ApiError {
    fn into_response(self) -> Response {
        // Map to (status, machine-readable code, safe message).
        let (status, code) = match &self {
            ApiError::NotFound       => (StatusCode::NOT_FOUND, "not_found"),
            ApiError::Conflict(_)    => (StatusCode::CONFLICT, "conflict"),
            ApiError::Validation(_)  => (StatusCode::UNPROCESSABLE_ENTITY, "validation"),
            ApiError::Upstream(_)    => (StatusCode::BAD_GATEWAY, "upstream"),
            ApiError::Db(sqlx::Error::RowNotFound) => (StatusCode::NOT_FOUND, "not_found"),
            ApiError::Db(_)          => (StatusCode::INTERNAL_SERVER_ERROR, "internal"),
        };

        // Log the full chain ONCE, here. Never in the handler.
        if status.is_server_error() {
            tracing::error!(error = ?self, error.code = code, "request failed");
        } else {
            tracing::warn!(error.code = code, "request rejected");
        }

        // NEVER serialize the Debug/Display of a db error to the client.
        (status, Json(json!({ "error": code, "message": self.to_string() }))).into_response()
    }
}
```

Four things this gets right that people get wrong. First, `From<sqlx::Error>` via `#[from]` means handlers can use `?` on any query, which is the entire ergonomic payoff. Second, the log happens exactly once, at the boundary, so you do not get five stack levels each logging the same failure. Third, `sqlx::Error::RowNotFound` maps to 404 rather than 500, because `fetch_one` on an empty result is a client error 90% of the time. Fourth, the client sees a stable machine-readable `code`, not `error: relation "user" does not exist`, which is an information disclosure finding in any pen test.

The one thing to be careful about: `self.to_string()` on a `thiserror` enum renders the `#[error("...")]` string, not the source chain, so `ApiError::Db(_)` renders whatever sqlx's `Display` says, which can include table names. Either use `#[error("internal error")]` on that variant or hardcode the client-visible message per status. Add `RFC 9457` (`application/problem+json`) if you want the standard shape.

### Graceful shutdown, and what it does not cover

```rust
// # untested sketch — axum 0.8 shape
let listener = tokio::net::TcpListener::bind("0.0.0.0:8080").await?;
axum::serve(listener, app.into_make_service())
    .with_graceful_shutdown(shutdown_signal())
    .await?;

async fn shutdown_signal() {
    use tokio::signal::unix::{signal, SignalKind};
    let mut term = signal(SignalKind::terminate()).unwrap();
    let ctrl_c = tokio::signal::ctrl_c();
    tokio::select! {
        _ = ctrl_c => {}
        _ = term.recv() => {}
    }
    tracing::info!("shutdown signal received, draining");
}
```

`with_graceful_shutdown` does three things: stops accepting new connections, lets in-flight requests finish, and then returns. What it does **not** do, and what people discover in production:

- It does not bound the drain. A long-polling or SSE connection holds shutdown open forever. Wrap it: `tokio::time::timeout(Duration::from_secs(25), server).await`, sized under Kubernetes' `terminationGracePeriodSeconds`, which defaults to **30 seconds** before SIGKILL.
- It does not wait for tasks you `tokio::spawn`ed from a handler. A fire-and-forget "write the audit log" task is killed when the runtime drops. If you need those, hold a `tokio_util::sync::CancellationToken` plus a `TaskTracker`, or a `tokio::sync::mpsc` whose receiver you drain before returning.
- It does not fix the endpoint-propagation race. When Kubernetes deletes a pod it sends SIGTERM and removes the pod from Endpoints **concurrently**, and kube-proxy/ingress convergence is typically 1-5 seconds. If you exit immediately on SIGTERM you will 502 requests that were routed to you after you stopped accepting. The fix is a `preStop` hook of `sleep 5` (or a readiness flag flipped to false, followed by a sleep of `readinessProbe.periodSeconds × failureThreshold`, default 10 s × 3 = 30 s, which is usually too slow, so lower the period to 2 s).

The full shape, and the one detail everyone forgets: **close the database pool after the server drains**, not before, and not never. `pool.close().await` waits for checked-out connections to return and issues a clean terminate rather than leaving Postgres to reap `idle in transaction` backends.

### sqlx: compile-time checked SQL and what it actually costs

`sqlx::query!` is a proc macro that **connects to your database at compile time**. For each invocation it sends a `Parse`/`Describe` over the extended query protocol, gets back the parameter types, the result column types, and Postgres's nullability inference, and generates an anonymous struct with exactly those Rust types.

```rust
// # untested sketch — sqlx 0.8/0.9, Postgres
let row = sqlx::query!(
    r#"
    select u.id, u.email, count(o.id) as "order_count!: i64"
    from users u left join orders o on o.user_id = u.id
    where u.id = $1
    group by u.id
    "#,
    user_id                       // typed: must be Uuid, checked at compile time
)
.fetch_optional(&pool)
.await?;
// row: Option<{ id: Uuid, email: String, order_count: i64 }>
```

The `as "order_count!: i64"` syntax is the escape hatch you will use constantly, and knowing it cold is a strong signal:

| Suffix | Meaning |
|---|---|
| `as "x!"` | force **non-null** (`T` instead of `Option<T>`) |
| `as "x?"` | force **nullable** (`Option<T>` instead of `T`) |
| `as "x: MyType"` | override the Rust type (newtypes, enums) |
| `as "x!: MyType"` | both |

You need it because Postgres's nullability inference is conservative: any expression, aggregate, or column on the null-able side of a `LEFT JOIN` comes back as possibly-null even when a `count(*)` provably cannot be. sqlx 0.9.0 changed this behaviour ("Postgres: force generic plan for better nullability inference," listed as a **breaking** change that "may alter the output of the `query!()` macros for certain queries"), so a 0.8 → 0.9 upgrade can produce a wave of type errors in previously-compiling code. That is the migration cost, and it is the honest answer to "what breaks when you upgrade sqlx."

**Offline mode and the CI bill.** `cargo sqlx prepare` runs every macro against a live database and writes one JSON file per unique query into `.sqlx/`, named `query-<sha256-of-the-sql>.json`. Commit that directory. Then `SQLX_OFFLINE=true cargo build` needs no database. The costs, all real:

1. **You must regenerate on every SQL change.** Add a query, forget to run `cargo sqlx prepare`, and CI fails with `set DATABASE_URL to use query macros online, or run cargo sqlx prepare to update the query cache`. The mitigation is a CI step running `cargo sqlx prepare --check --workspace`, which fails the build if `.sqlx/` is stale. Budget one CI job with a Postgres service container.
2. **`.sqlx/` is a merge-conflict surface.** Two branches each adding queries produce two sets of new files; that part merges cleanly. Two branches *modifying the same query* produce a delete-plus-add, which merges badly. Not fatal, but it is noise.
3. **It invalidates your Docker cache layer.** `.sqlx/` must be `COPY`ed before `cargo build`, so any SQL change busts the application build layer. It does not bust the dependency layer, which is why `cargo-chef` still works.
4. **Compile time.** The macros are proc macros doing file IO (offline) or network IO (online). Online mode on a 200-query service means 200 round trips on a cold build. Offline mode is file reads and is much faster, but the macros still re-run whenever the crate is recompiled, so putting all your SQL in one small `db` crate keeps them out of the hot iteration loop.

If you do not want any of this: `sqlx::query_as::<_, MyRow>("select ...")` (the *function*, not the macro) does zero compile-time checking, needs no database, and is what you fall back to for dynamic SQL. In sqlx 0.9.0 the function forms take `impl SqlSafeStr`, implemented only for `&'static str` and the explicit `AssertSqlSafe(_)` wrapper. That is a deliberate speed bump: `sqlx::query(&format!("select * from {table}"))` no longer compiles without you writing `AssertSqlSafe`, which makes SQL string-building visible in code review. Do not read that as sanitisation; it is a marker, not an escaper. Bound parameters (`$1`) remain the only safe way to interpolate values, and identifiers still need an allowlist.

### Pool sizing, with the arithmetic

sqlx's `PoolOptions::new()` defaults, read straight from `sqlx-core/src/pool/options.rs`:

| Option | Default | Why it matters |
|---|---|---|
| `max_connections` | **10** | The docs literally say "A production application will likely want to set a higher limit than this." |
| `min_connections` | **0** | No warm connections; the first request after idle pays a full TCP + TLS + auth handshake |
| `acquire_timeout` | **30 s** | The single worst default for an overloaded service |
| `idle_timeout` | **600 s** (10 min) | Closes idle connections; must be below any proxy/firewall idle reaper |
| `max_lifetime` | **1800 s** (30 min) | Forces recycling; essential behind a load balancer that rebalances on new connections |
| `test_before_acquire` | **true** | One extra round trip per acquire |
| `acquire_slow_threshold` | **2 s** | Logs a `WARN` when an acquire takes longer |
| `fair` | **true** | FIFO waiters, so no starvation under contention |

Now the sizing. Little's Law: the mean number of connections in use is `L = λ × W`, where λ is queries-per-second the pool serves and W is the mean time a connection is held.

**Worked example.** A service handling **2,000 rps**, where each request runs 2 queries averaging **1.5 ms** each, holds a connection for `W = 3 ms` per request. So `L = 2000 × 0.003 = 6` connections on average. That is the *mean*; you size for the tail. Utilisation `ρ = L / max_connections`, and queueing delay grows roughly as `1/(1-ρ)`, so at ρ = 0.9 the wait is 10x the service time and at ρ = 0.95 it is 20x. Target `ρ ≤ 0.7`, which gives `max_connections ≈ 6 / 0.7 ≈ 9`, and then add headroom for the p99 query rather than the mean: if p99 query time is 15 ms rather than 1.5 ms, the tail-driven number is `2000 × 0.030 × (1/0.7) ≈ 86`, which is nonsense for a single replica and tells you the real answer is **fix the p99 query**, not grow the pool.

The counter-pressure is the database. Postgres is process-per-connection, `max_connections` defaults to **100** with **3** reserved for superusers, and each backend costs roughly **5-10 MB** RSS plus `work_mem` per sort/hash node. Throughput does not increase past roughly 2-4x the core count in *active* connections; past that you are paying `ProcArray` and lock-manager contention for nothing. On RDS the default is the formula `LEAST({DBInstanceClassMemory/9531392}, 5000)`, which on a 16 GiB `db.r6g.large` works out to about **1,802**, and that number is a trap: it is what the instance *permits*, not what it performs well at.

So the binding constraint is usually the multiplication:

```
replicas × max_connections_per_pod  ≤  postgres max_connections − reserve

10 replicas × 20 = 200  >  100 default        -> outage on deploy
10 replicas × 8  =  80  <  97                 -> fits, ρ per pod ≈ 0.75 at 200 rps/pod
```

A rolling deploy briefly runs `maxSurge` extra pods, so use `(replicas + maxSurge) × max_connections`. This is the number-one way a Rust service takes down a shared Postgres: the service itself is so cheap that you run 40 replicas, and 40 × 10 = 400 connections against a 100-connection database.

When the arithmetic does not fit, the answer is **PgBouncer in transaction mode** (or RDS Proxy / pgcat), which multiplexes many client connections onto few server connections. Its own defaults: `default_pool_size = 20` server connections per user/database pair, `max_client_conn = 100`. The Rust-specific trap: **sqlx uses named prepared statements by default** and caches them per connection (`statement_cache_capacity`, default **100**), and named prepared statements do not survive transaction-level pooling unless PgBouncer 1.21+ is configured with `max_prepared_statements > 0`. The symptom is intermittent `prepared statement "sqlx_s_3" does not exist` errors under load and never in staging. The fix is either that PgBouncer setting or `PgConnectOptions::statement_cache_capacity(0)` on the client, and the second one costs you a parse on every query.

The two settings I change on day one, every time:

```rust
// # untested sketch
let pool = PgPoolOptions::new()
    .max_connections(16)
    .min_connections(4)                                  // warm; avoids handshake on cold path
    .acquire_timeout(Duration::from_secs(3))             // NOT 30. Fail fast, shed load.
    .max_lifetime(Duration::from_secs(30 * 60))
    .idle_timeout(Duration::from_secs(5 * 60))
    .test_before_acquire(false)                          // see below
    .connect(&database_url).await?;
```

`acquire_timeout(3s)` turns pool exhaustion into a fast, visible 503 instead of a 30-second stall that the client has already timed out on. Pick it strictly below your client's timeout, so *you* generate the error and it appears in your metrics rather than as an opaque gateway timeout.

`test_before_acquire(false)` is the one that needs justification. With it on, every `acquire()` costs one extra round trip to the database. At 10,000 acquires/sec and a 0.3 ms RTT, that is 3 seconds of connection-time consumed per wall-clock second, which is about 3 connections' worth of your pool spent purely on liveness checks, plus 0.3 ms added to every request's latency floor. Turn it off and rely on `max_lifetime` plus retry-once-on-`io error` for stale connections. Turn it back on if you sit behind a NAT gateway or firewall that silently drops idle flows, where a dead connection is common rather than rare. Also set `acquire_time_level` (default `Off`) to `Debug` while you are tuning, and keep `acquire_slow_level` at `Warn` so you get the 2-second warning in production.

### Migrations and transactions

```bash
sqlx migrate add -r create_users          # writes 20260805120000_create_users.{up,down}.sql
sqlx migrate run                          # applies, records in _sqlx_migrations
sqlx migrate info                         # shows applied/pending
```

```rust
// # untested sketch — embeds the SQL in the binary at compile time
sqlx::migrate!("./migrations").run(&pool).await?;
```

Mechanics worth knowing:

- `_sqlx_migrations` stores `version`, `description`, `installed_on`, `success`, **`checksum`**, `execution_time`. Editing an already-applied migration file changes its checksum and produces `VersionMismatch`, which is the correct behaviour and the reason you never edit an applied migration. sqlx 0.9's `sqlx.toml` adds an option to ignore specified characters when hashing, which exists so whitespace-only reformatting does not break your deploy.
- sqlx takes a **Postgres advisory lock** for the duration of the migration, so N pods starting simultaneously do not race. `Migrator::set_locking(false)` disables it, which you need on CockroachDB and behind PgBouncer in transaction mode (advisory locks are session-scoped and a transaction-pooled connection is not a stable session).
- Running migrations at **startup** is fine for small, fast, additive migrations and is a real operational hazard for anything else, because a `ALTER TABLE ... ADD COLUMN ... DEFAULT` that rewrites a 200M-row table blocks every pod's startup and blows the readiness deadline, and because a failed migration crash-loops the whole deployment. For anything non-trivial, run migrations as a Kubernetes `Job` or an init container gated on a single replica, and use expand/contract so old and new code both work against the intermediate schema.

Transactions:

```rust
// # untested sketch
let mut tx = pool.begin().await?;                       // Transaction<'_, Postgres>

sqlx::query!("update accounts set cents = cents - $1 where id = $2", amt, from)
    .execute(&mut *tx).await?;                          // note: &mut *tx, not &pool
sqlx::query!("update accounts set cents = cents + $1 where id = $2", amt, to)
    .execute(&mut *tx).await?;

tx.commit().await?;                                     // explicit. Drop = ROLLBACK.
```

Three mechanics:

- `Transaction` implements `Deref`/`DerefMut` to the connection, so the executor argument is `&mut *tx`. Passing `&pool` inside a transaction is a silent bug: it checks out a *different* connection, so those statements run outside the transaction and commit independently. That is a data-integrity bug that a code review catches and no compiler does. Grep for `&pool` inside any function that also calls `begin()`.
- **`Drop` rolls back.** Returning `Err` early via `?` aborts the transaction correctly with no `catch` block, which is the single nicest thing about transactions in Rust. The caveat: `Drop` cannot be `async`, so sqlx queues the `ROLLBACK` to run when the connection is next used or returned to the pool. It is correct, but it means the rollback is not synchronous with the drop, and under a hard `abort()` of the task the connection is closed rather than cleanly rolled back (Postgres then rolls back on disconnect, which is also correct, just noisier in the logs).
- `tx.begin()` on an existing transaction issues a **`SAVEPOINT`**, so nesting works and behaves like a nested transaction.
- Retry on serialization conflicts yourself. Postgres SQLSTATE **`40001`** (`serialization_failure`) and **`40P01`** (`deadlock_detected`) are retryable; match on `sqlx::Error::Database(e) if e.code().as_deref() == Some("40001")` and retry the whole closure with jittered backoff, capped at 3 attempts. Nothing does this for you, unlike Spring's `@Retryable`.

### sqlx vs Diesel vs SeaORM, honestly

| | **sqlx 0.9** | **Diesel 2.x** | **SeaORM 1.x** |
|---|---|---|---|
| You write | SQL | a Rust DSL | an ORM API (entities, `find_by_id`, relations) |
| Compile-time checking | yes, needs a **live DB** or `.sqlx/` | yes, needs a generated `schema.rs`, **no DB** | no; it is checked at runtime |
| Async | native (Tokio or async-std) | via the separate `diesel-async` crate | native (built **on sqlx**) |
| Migrations | built in (`sqlx migrate`) | built in (`diesel migration`) | built in, plus a schema-from-entities generator |
| Dynamic queries | string building, `QueryBuilder` | `into_boxed()`, well typed | first-class |
| Compile time | macros do IO; slow-ish | heavy generics; the slowest of the three on wide tables | inherits sqlx plus its own generics |
| Learning cost for a polyglot | ~zero if you know SQL | real; the DSL is its own language | familiar if you know Hibernate/SQLAlchemy |
| When it is wrong | you need dynamic SQL everywhere, or cannot have a DB in the build | you want to write actual SQL, or need async as a first-class concern | you would not add an ORM to a new Rust service without a specific reason |

My recommendation, stated as a lean rather than a fact: **default to sqlx**. You already write SQL every day; the DSL tax on Diesel buys you compile-time checking you get from sqlx anyway, and the async story is cleaner. Choose **Diesel** when a live database in the build pipeline is genuinely unacceptable (air-gapped builds, a monorepo where the build cannot reach infrastructure) or when you have complex composable query builders where a typed DSL is genuinely safer than string concatenation. Choose **SeaORM** when you are porting a Rails/Django-shaped application with heavy entity relationships and the team's productivity depends on the ORM idiom, and accept that you have added a layer over sqlx that generates SQL you did not write. The position that is wrong in both directions is "ORMs are always bad" and "you need an ORM"; the real question is whether you have enough entity-graph traversal that mapping code would dominate, and in a typical HTTP service with 20 tables the answer is no.

One live disagreement worth naming: sqlx's compile-time DB requirement is the most-argued design decision in the Rust database ecosystem. The defenders say `.sqlx/` plus `cargo sqlx prepare --check` makes it a one-time CI cost. The critics point out that it makes `cargo build` non-hermetic in principle, breaks `cargo install`-style workflows, and adds a class of "works on my machine" failure where a developer's local schema drifts from the checked-in cache. Both are true. If your organisation has strong hermetic-build norms (Bazel, Nix), the critics' side is heavier.

### `tracing`: spans are the point, events are the consolation prize

The distinction, precisely:

- An **event** is a moment. `tracing::info!(user_id = %id, "created")`. This is what `log::info!` gives you.
- A **span** is a period with an entry and an exit, and spans **nest** into a tree. `let span = info_span!("handle_request", route = "/v1/users"); let _g = span.enter();`
- Every event emitted while a span is entered is **attributed to that span and all its ancestors**, so a single `error!` at depth 5 carries the request id, route, tenant, and query name without you passing any of them down.

`log` cannot do this in async code, and the reason is mechanical rather than aesthetic. `log` correlates by (timestamp, thread id, module path). On a Tokio multi-thread runtime, one worker thread interleaves polls from thousands of tasks, so the thread id partitions nothing: two consecutive lines from the same thread routinely belong to different requests. Meanwhile a single request's lines are spread across every worker, because work-stealing migrates the task. So the log for one request is neither contiguous nor thread-local. The MDC/ThreadLocal trick that works in Spring (`MDC.put("requestId", ...)`, because Servlet containers really are thread-per-request) is exactly wrong here.

`tracing` fixes it by attaching the span to the **future**, not the thread:

```rust
// # untested sketch
use tracing::Instrument;

// The right way: the span is entered on every poll and exited on every
// return-Pending, so it follows the task across worker threads.
tokio::spawn(
    handle(req).instrument(tracing::info_span!("request", %request_id))
);

// The macro version, which is what you actually write:
#[tracing::instrument(
    skip_all,                                  // do NOT log the whole struct
    fields(user_id = %user.id, route = "/v1/orders"),
    err(Debug),                                // auto-emit an ERROR event on Err
    level = "info",
)]
async fn create_order(user: AuthUser, State(st): State<AppState>) -> Result<Json<Order>, ApiError> {
    // ...
}
```

**The single biggest `tracing` footgun in async Rust:**

```rust
// # untested sketch — THIS IS THE BUG
async fn handler() {
    let span = tracing::info_span!("handler");
    let _guard = span.enter();          // <-- Entered guard...
    do_io().await;                       // <-- ...held ACROSS an await.
    tracing::info!("done");
}
```

`Span::enter()` sets a **thread-local** current-span. When this task hits the `.await` and returns `Pending`, the worker thread immediately polls a different task, and that task's events are now attributed to *your* span. You get a trace where unrelated requests appear nested under each other, and it is maddening to debug because it only happens under concurrency. `tracing` documents this and the fix is absolute: **never hold an `Entered` guard across an `.await`**; use `.instrument(span)` or `#[instrument]`, which enter and exit around each individual `poll`. Clippy has a lint for a subset of this (`await_holding_span_guard` in older versions), but the discipline is the real defence.

**Subscriber composition.** `tracing` itself only defines the `Subscriber` trait and the macros; `tracing-subscriber` 0.3.23 supplies `Registry` (which stores span data) and the `Layer` trait for composing behaviour on top of it.

```rust
// # untested sketch — the initialisation I would ship
use tracing_subscriber::{layer::SubscriberExt, util::SubscriberInitExt, EnvFilter, fmt};

let filter = EnvFilter::try_from_default_env()
    .unwrap_or_else(|_| EnvFilter::new("info,sqlx::query=warn,tower_http=debug,hyper=info"));

let fmt_layer = if cfg!(debug_assertions) {
    fmt::layer().pretty().boxed()
} else {
    fmt::layer().json().flatten_event(true).with_current_span(true).boxed()
};

tracing_subscriber::registry()
    .with(filter)                                  // global filter
    .with(fmt_layer)
    .with(tracing_opentelemetry::layer().with_tracer(tracer))   // OTel export
    .with(tracing_error::ErrorLayer::default())    // span traces on errors
    .init();
```

Details that matter:

- **`RUST_LOG` directives are per-target with an optional span filter.** `RUST_LOG=info,my_app::db=trace,sqlx::query=warn` is the ordinary form; `RUST_LOG="[request{route=/v1/orders}]=debug"` turns on debug only inside spans named `request` with that field value, which is how you get per-endpoint verbosity in production without a redeploy.
- **`.with(filter)` filters globally; `.with_filter(filter)` filters one layer.** Getting this backwards is why people end up shipping `TRACE` to their OTel collector while their console looks fine. Use per-layer filters when the console and the exporter should differ, which they usually should: `INFO` to stdout, everything sampled to OTel.
- **Cost of a disabled callsite is a few nanoseconds.** `tracing` caches per-callsite `Interest` in an atomic and checks `STATIC_MAX_LEVEL` first, so `trace!` in a hot loop compiled with the `release_max_level_info` feature is compiled out entirely (zero instructions). Enabled span creation with fields is more like hundreds of nanoseconds to low microseconds, dominated by field formatting. At 50,000 rps, one span per request at 1 µs is 5% of one core; one span per *query* per request at 4 queries is 20%. Set span levels deliberately.
- **Quiet sqlx.** sqlx logs every statement at the `sqlx::query` target, at `INFO` for slow queries and `DEBUG` otherwise, with fields including `summary`, `db.statement`, `rows_affected`, `elapsed`. Left at `debug` this is your highest-volume log source by an order of magnitude, and it contains your SQL text. `sqlx::query=warn` in production, with `PoolOptions::acquire_slow_threshold` kept on so pool problems still surface.
- **tokio-console** is a `tracing` layer too (`console-subscriber`), needing `RUSTFLAGS="--cfg tokio_unstable"`. Not for production, invaluable for "why is my p99 250 ms."

**OpenTelemetry export.** The current line is `opentelemetry` **0.32.0**, `opentelemetry-otlp` **0.32.0**, `tracing-opentelemetry` **0.33.0** (May 2026). The uncomfortable status: in opentelemetry-rust the **Logs and Metrics** API/SDK are marked **Stable** while **Traces are still Beta**, which is the inverse of every other language's maturity order, and it means the piece you most need for a request-tracing story is the one whose API still churns. Practical consequences:

- Version pinning is not optional. `opentelemetry`, `opentelemetry_sdk`, `opentelemetry-otlp`, and `tracing-opentelemetry` must be upgraded together; mismatched minors produce trait-resolution errors that read like nonsense because the `Tracer` trait is defined in one crate and implemented in another.
- OTLP defaults: gRPC on port **4317**, HTTP/protobuf on **4318**, configured by `OTEL_EXPORTER_OTLP_ENDPOINT`. The batch span processor's spec defaults are `max_queue_size = 2048`, `scheduled_delay = 5000 ms`, `max_export_batch_size = 512`, `export_timeout = 30000 ms`. At 5,000 rps with one span per request, a 2,048-span queue drains in 0.4 s, so you will silently drop spans unless you either raise the queue or sample. Dropped spans are reported by the SDK's own metrics, not by an error.
- **Sample at the head, ratio-based, parent-respecting.** `TraceIdRatioBased(0.05)` wrapped in `ParentBased` keeps whole traces intact across services rather than sampling each hop independently, which is the difference between a usable trace and a set of disconnected fragments. 1-10% is the normal production range; sample errors at 100% with a tail sampler in the collector if you can afford one.
- Context propagation is the W3C `traceparent`/`tracestate` headers via `TraceContextPropagator`; you must explicitly extract on ingress and inject on egress, because nothing is automatic. `tower-http`'s `TraceLayer` does not do OTel propagation for you.
- Call `opentelemetry::global::shutdown_tracer_provider()` (or the provider's `shutdown()`) before `main` returns, or the last batch is lost. This is the "my last 5 seconds of traces before the crash are always missing" bug.

### Configuration and secrets

Load once, validate at startup, and make a missing value a **process exit**, not a 500 at 03:00.

```rust
// # untested sketch — `config` 0.15, `secrecy` 0.10
use secrecy::{ExposeSecret, SecretString};

#[derive(Debug, serde::Deserialize)]
pub struct Settings {
    pub port: u16,
    pub database_url: SecretString,      // Debug prints "SecretBox<str>([REDACTED])"
    pub pool_max_connections: u32,
    pub otlp_endpoint: Option<String>,
    pub log_level: String,
}

pub fn load() -> Result<Settings, config::ConfigError> {
    let env = std::env::var("APP_ENV").unwrap_or_else(|_| "local".into());
    config::Config::builder()
        .add_source(config::File::with_name("config/base"))
        .add_source(config::File::with_name(&format!("config/{env}")).required(false))
        // APP__DATABASE_URL, APP__POOL_MAX_CONNECTIONS, ...
        .add_source(config::Environment::with_prefix("APP").separator("__"))
        .build()?
        .try_deserialize()
}
```

The rules that are actually contested and worth having an opinion about:

1. **Prefer file-mounted secrets over environment variables.** Env vars appear in `/proc/<pid>/environ`, in `docker inspect`, in crash handlers that dump the environment, and in any child process you spawn. Kubernetes projects secrets to `/var/run/secrets/...`; read the file. If you must use env, read it once at startup into a `SecretString` and `std::env::remove_var` it.
2. **`secrecy` 0.10's `SecretString`/`SecretBox<T>` gives you two things**: a `Debug`/`Display` impl that prints `[REDACTED]`, so a `#[derive(Debug)]` on your config struct or a `tracing::info!(?settings)` cannot leak it, and `Zeroize` on drop so the plaintext does not linger in freed heap. Note 0.10 removed the old `Secret<T>` type in favour of `SecretBox<T>`; code written against 0.8 does not compile.
3. **Do not put secrets in the binary or the image.** `strings` on a 3.4 MiB binary takes milliseconds.
4. **One validated struct, constructed once, stored in `Arc<Settings>` inside `AppState`.** No `std::env::var` calls scattered through handlers; those are how a config typo becomes a partial outage that only affects one endpoint.

---

## Build it from scratch

The point of building it once by hand is to see that there is no framework underneath. `labs/rust/06-rust-services/` has the full version; this is the spine.

```bash
cargo new svc && cd svc
cargo add axum tokio --features tokio/full
cargo add tower --features util,limit,load-shed
cargo add tower-http --features trace,timeout,request-id,compression-gzip
cargo add serde --features derive
cargo add serde_json thiserror uuid --features uuid/v4,uuid/serde
cargo add tracing tracing-subscriber --features tracing-subscriber/env-filter,tracing-subscriber/json
cargo add sqlx --no-default-features \
    --features runtime-tokio,tls-rustls,postgres,macros,migrate,uuid,chrono
cargo install sqlx-cli --no-default-features --features rustls,postgres
```

That dependency set resolves to **179 unique crates** and, measured on 2 vCPU with Rust **1.97.1** (`8bab26f4f`, 14 July 2026), takes **117 seconds** for a cold `cargo build --release` with `lto = "thin"` and `codegen-units = 1`. Dropping sqlx and uuid takes it to **100 crates**, **58 seconds**, and a **1.13 MiB** binary. Those numbers are the honest answer when someone says "Rust compile times are terrible": for a service of this size they are minutes, not the twenty minutes people quote from `rustc` bootstrap or from a workspace with 800 dependencies.

```rust
// # untested sketch (compiles as written against axum 0.8 / sqlx 0.8; the
// version in the lab is the one that was actually built and run)
use axum::{extract::{Path, State}, routing::get, Json, Router};
use sqlx::postgres::PgPoolOptions;
use std::time::Duration;

#[derive(Clone)]
struct AppState { db: sqlx::PgPool }

#[tokio::main]
async fn main() -> anyhow::Result<()> {
    let cfg = config::load()?;
    init_tracing(&cfg);

    let db = PgPoolOptions::new()
        .max_connections(cfg.pool_max_connections)
        .acquire_timeout(Duration::from_secs(3))
        .connect(cfg.database_url.expose_secret()).await?;

    sqlx::migrate!("./migrations").run(&db).await?;

    let app = Router::new()
        .route("/healthz", get(|| async { "ok" }))              // liveness: NO db
        .route("/readyz",  get(readyz))                          // readiness: db ping
        .route("/v1/users/{id}", get(get_user))
        .layer(middleware_stack())
        .with_state(AppState { db: db.clone() });

    let listener = tokio::net::TcpListener::bind(("0.0.0.0", cfg.port)).await?;
    tracing::info!(port = cfg.port, "listening");

    let server = axum::serve(listener, app).with_graceful_shutdown(shutdown_signal());
    let _ = tokio::time::timeout(Duration::from_secs(25), server).await;

    db.close().await;                        // drain AFTER the server stops
    opentelemetry::global::shutdown_tracer_provider();
    Ok(())
}

async fn readyz(State(st): State<AppState>) -> Result<&'static str, ApiError> {
    // Cheap, bounded, and it must fail fast: the readiness probe's own
    // timeoutSeconds defaults to 1.
    tokio::time::timeout(Duration::from_millis(500), sqlx::query("select 1").execute(&st.db))
        .await
        .map_err(|_| ApiError::Upstream)??;
    Ok("ready")
}
```

Four exercises that each teach one production concept:

**Step 1.** Write the `AuthUser` extractor from the earlier section, then deliberately register it with `.layer()` *before* `.route()` and prove with a `reqwest` integration test that the unauthenticated request returns 200. Then move it and watch the test go red-to-green. You will never make that mistake again.

**Step 2.** Set `max_connections(2)` and `acquire_timeout(30)`, add a handler that runs `select pg_sleep(1)`, and fire 20 concurrent requests. Observe: latency climbs linearly with queue position, `acquire_slow_threshold` warnings appear at 2 s, nothing fails for 30 s, and `/readyz` (which shares the pool) starts failing. Then set `acquire_timeout(3)` and observe the same load producing fast 503s instead. That is the whole pool-exhaustion incident in a lab.

**Step 3.** Take a `span.enter()` guard across an `.await` in a handler, run 50 concurrent requests, and read the JSON logs. Count how many events land under the wrong span. Then switch to `#[instrument]` and re-run.

**Step 4.** Build the image four ways (single-stage `rust:1.97`, multi-stage onto `debian:trixie-slim`, multi-stage onto `distroless/cc-debian12`, and static-musl onto `distroless/static-debian12`), record `docker images --format '{{.Size}}'` for each, then run a `wrk`/`oha` benchmark against the glibc and musl builds and record the throughput delta. The numbers in the next section are what you should roughly see.

---

## How it's done in production

### The release profile, and the one setting that will bite you

```toml
[profile.release]
opt-level = 3
lto = "thin"          # "fat" is slower to build, marginally smaller/faster
codegen-units = 1     # better optimisation, worse build parallelism
strip = true          # measured: 8,418,352 B -> 3,539,024 B  (-58%)
panic = "abort"       # READ THE WARNING BELOW
```

Measured on the reference service (axum + tokio + sqlx + tracing-subscriber, 179 crates, Rust 1.97.1, 2 vCPU):

| Artefact | Size |
|---|---|
| Release binary, unstripped | **8,418,352 B** (8.03 MiB) |
| Release binary, `strip = true` | **3,539,024 B** (3.38 MiB) |
| Same without sqlx/uuid | **1,181,680 B** (1.13 MiB), 100 crates |
| `target/release/` directory | **1.4 GB** |
| `target/debug/` directory | **561 MB** |

`codegen-units = 1` costs build time (it serialises the LLVM stage) and typically buys single-digit-percent runtime. `lto = "fat"` costs more still. On a service that spends its time in syscalls and JSON, neither is worth much; on one doing tight compute, both are. Measure rather than cargo-cult.

**`panic = "abort"` is the trap.** It removes unwind tables (smaller binary, marginally faster) and makes any panic terminate the process immediately. That means `tower_http::catch_panic::CatchPanicLayer`, which is built on `std::panic::catch_unwind`, **stops working**, and Tokio's normal behaviour of isolating a panicking task (`JoinError::is_panic()`) stops working too. One malformed request that trips an `unwrap()` in a handler now kills the pod and every other in-flight request with it. On a service, ship `panic = "unwind"` (the default) plus `CatchPanicLayer`, and set `RUST_BACKTRACE=1` so the panic message carries a backtrace into your logs. `panic = "abort"` belongs on CLIs and on binaries where a panic genuinely should be fatal.

### The Dockerfile that people write first, and why it is 700 MB

```dockerfile
# ANTI-PATTERN. Do not ship this.
FROM rust:1.97
WORKDIR /app
COPY . .
RUN cargo build --release
CMD ["./target/release/svc"]
```

Three separate problems, each independently disqualifying:

1. **The base image is enormous.** `rust:latest` is **569.3 MiB compressed** on amd64; `rust:1.97-slim` is **308.1 MiB compressed**, roughly 1.2 GB uncompressed. The final image contains the entire Rust toolchain, which the running service does not use.
2. **`target/` ships too.** 1.4 GB of intermediate objects, unless a `.dockerignore` excludes it, and if `.dockerignore` *doesn't* exclude it, the local `target/` is also part of the build context and gets uploaded to the daemon on every build.
3. **`COPY . .` destroys the layer cache.** Any change to any file, including the README, invalidates that layer, so every subsequent `RUN cargo build` recompiles all 179 dependency crates. Cold build measured at **117 s** on 2 vCPU for this small service; on a real service with 500+ dependencies on a shared CI runner, 15-25 minutes is the number people report.

### `cargo-chef`, and the layer-caching arithmetic

The insight is that Cargo has no "build dependencies only" mode. `cargo build` needs your `src/` to exist, and once `src/` is in the layer, changing `src/` invalidates the dependency build. `cargo-chef` (0.1.77, March 2026) solves it in two steps: `cargo chef prepare` reduces your workspace to a **recipe.json** describing only the dependency graph and the manifest skeleton, and `cargo chef cook` reconstitutes a dummy source tree from it and builds only the dependencies. Since `recipe.json` changes only when `Cargo.toml`/`Cargo.lock` change, the expensive layer is stable across ordinary code changes.

```dockerfile
# syntax=docker/dockerfile:1.7
ARG RUST_VERSION=1.97.1

FROM lukemathwalker/cargo-chef:latest-rust-${RUST_VERSION} AS chef
WORKDIR /app

FROM chef AS planner
COPY . .
RUN cargo chef prepare --recipe-path recipe.json

FROM chef AS builder
COPY --from=planner /app/recipe.json recipe.json
# ---- THE CACHED LAYER. Invalidated only by Cargo.toml / Cargo.lock. ----
RUN cargo chef cook --release --recipe-path recipe.json
# -----------------------------------------------------------------------
COPY . .
ENV SQLX_OFFLINE=true
RUN cargo build --release --bin svc && strip target/release/svc

FROM gcr.io/distroless/cc-debian12:nonroot AS runtime
COPY --from=builder /app/target/release/svc /usr/local/bin/svc
COPY --from=builder /app/migrations /migrations
USER nonroot:nonroot
EXPOSE 8080
ENTRYPOINT ["/usr/local/bin/svc"]
```

The measured payoff, on the reference service, 2 vCPU, Rust 1.97.1:

| Scenario | Wall time |
|---|---|
| Cold build, no cache, 179 crates | **117 s** |
| Warm build, deps cached, only `src/main.rs` changed | **24 s** |
| Speed-up | **4.9x** |

That 4.9x on a small service is consistent with the numbers cargo-chef's author reports on larger ones: ~10 min to ~2 min (5x) on a ~14k-line, ~500-dependency commercial codebase, and ~22.5 min to ~2.5 min (9x) on the ExpressVPN repository. The larger the dependency-to-application ratio, the bigger the win, which is why it matters more for a service (lots of deps, little code) than for a library.

Three caveats that stop this being free:

- **`cargo chef cook` is not always faster.** If your CI has no persistent Docker layer cache, cargo-chef adds a planner stage and gains nothing; there is a well-known issue thread of people whose build time went *up* (5 min to 25 min) because they were on a runner with cold caches every time and cargo-chef's dummy-source build ran in addition to the real one. Confirm your CI persists layers (`docker buildx --cache-from/--cache-to`, a registry cache, or a self-hosted runner) before adopting it.
- **The BuildKit alternative is simpler and sometimes better.** `RUN --mount=type=cache,target=/usr/local/cargo/registry --mount=type=cache,target=/app/target cargo build --release` gives you incremental compilation across builds with no extra stage. It requires BuildKit and a runner that persists the cache mount, and the cache is not portable between machines, whereas cargo-chef's win rides on ordinary registry-pushed layers.
- **Feature unification changes the recipe.** Adding a feature to a dependency changes `recipe.json` and busts the cache, exactly as it should. Adding a whole new dependency does too. Expect one slow build per dependency change and no more.

### Base images: the real numbers

Compressed amd64 sizes, pulled from the registries on 5 August 2026:

| Base | Compressed | Layers | libc | Shell? | Notes |
|---|---|---|---|---|---|
| `rust:latest` | **569.3 MiB** | many | glibc | yes | builder only |
| `rust:1.97-slim` | **308.1 MiB** | many | glibc | yes | builder only |
| `debian:bookworm-slim` | **26.9 MiB** | 1 | glibc | yes | fine, has a shell and a package manager |
| `debian:trixie-slim` | **28.4 MiB** | 1 | glibc | yes | current stable |
| `gcr.io/distroless/cc-debian12` | **8.75 MiB** | 18 | glibc | **no** | glibc + libgcc + libssl; what a normal Rust binary needs |
| `gcr.io/distroless/base-debian12` | **7.78 MiB** | 14 | glibc | **no** | no libstdc++/libgcc; enough for pure-Rust + rustls |
| `gcr.io/distroless/static-debian12` | **0.67 MiB** | 12 | none | **no** | fully static binaries only (musl or `crt-static`) |
| `alpine:3.22` | **3.6 MiB** | 1 | **musl** | yes | see the trap below |

Add the 3.38 MiB stripped binary and the resulting final images are roughly: **distroless/cc ≈ 12 MiB compressed / ~26 MB on disk**, **debian-slim ≈ 30 MiB compressed / ~78 MB on disk**, **distroless/static + musl ≈ 4 MiB compressed / ~9 MB on disk**.

The choice I would defend: **`distroless/cc-debian12:nonroot`**. You get glibc's allocator, no shell (so a remote-code-execution finding cannot pivot to `sh`), no package manager, a non-root UID (65532) baked in, and CVE scanners have far less to complain about because there are ~20 packages instead of ~100. The cost is that debugging is harder: no `sh`, no `curl`, no `ps`. The answer to that is `:debug` variants of the same images, plus `kubectl debug --image=busybox --target=svc` ephemeral containers, not shipping a shell to production.

### The musl trap, stated precisely

Building with `--target x86_64-unknown-linux-musl` gives you a fully static binary, which is genuinely attractive: a 4 MB image, no dynamic linker, no glibc version-skew between build and runtime. The cost is the allocator.

musl's `malloc` uses far more conservative locking than glibc's. glibc's ptmalloc gives each thread an arena (up to `8 × ncores` of them) so concurrent allocations mostly do not contend; musl's allocator serialises much harder. Rust programs allocate constantly (every `String`, `Vec`, `Box<dyn ...>`, every boxed future in `middleware::from_fn`, every `serde_json` document), so the contention is on your hot path. The measured results people report: **up to 7x slowdown** on a real allocation-heavy workload with musl's default allocator versus glibc, worsening as thread count rises, and Andy Grove documented a similar order of magnitude on a Rust workload in 2020. The symptom to recognise: throughput scales fine to 2 threads and then *flattens or regresses* as you add cores, and a `perf record` shows a large fraction of cycles inside musl's `malloc`/`free` lock path.

The fixes, in order:

1. **Do not use musl.** Build with the default `x86_64-unknown-linux-gnu` and run on `distroless/cc-debian12`. This is the right answer for 90% of services. You are trading 8 MiB of image for a multiple of your throughput.
2. **If you need static, replace the allocator.** mimalloc builds and runs cleanly on musl and has been measured pushing musl *past* glibc's default; Microsoft's own benchmarks claim up to 5.3x throughput over glibc malloc under heavy multithreaded load with roughly half the resident memory. One line:

```rust
// # untested sketch
#[global_allocator]
static GLOBAL: mimalloc::MiMalloc = mimalloc::MiMalloc;
```

3. **jemalloc (`tikv-jemallocator`) is the other option** and is the one with the longest Rust production history: Rust shipped jemalloc *in* the standard library until **1.32.0 (2019)**, when it moved to the system allocator. It is excellent on glibc; on musl it has historically been the flakier of the two.

Two more musl gotchas that are not about the allocator and still ruin days. Static musl binaries do their own DNS resolution rather than going through glibc's NSS, so `/etc/nsswitch.conf` is ignored and musl's resolver historically handled the `ndots:5` search-path behaviour and multiple nameservers differently from glibc, which is exactly the configuration Kubernetes injects. The symptom is intermittent `failed to lookup address information` for in-cluster service names that resolve fine from a debug pod. And cross-compiling to musl needs `musl-gcc` or `cargo-zigbuild`/`cross`, which is one more moving part in CI.

### Deployment: probes, drain, and the memory profile

```yaml
# untested sketch — the parts that matter
spec:
  terminationGracePeriodSeconds: 40        # > your 25s drain timeout
  containers:
  - name: svc
    resources:
      requests: { cpu: "250m", memory: "64Mi" }
      limits:   { memory: "256Mi" }         # no CPU limit; throttling ruins p99
    env:
      - name: TOKIO_WORKER_THREADS
        value: "2"                          # Tokio reads nproc, NOT the cgroup quota
      - name: MALLOC_ARENA_MAX
        value: "2"                          # cap glibc arena growth
      - name: RUST_BACKTRACE
        value: "1"
    startupProbe:                            # covers slow migrations / cold pools
      httpGet: { path: /healthz, port: 8080 }
      periodSeconds: 2
      failureThreshold: 30                   # 60s budget to come up
    livenessProbe:                           # process alive. NO database.
      httpGet: { path: /healthz, port: 8080 }
      periodSeconds: 10
      timeoutSeconds: 1
      failureThreshold: 3
    readinessProbe:                          # can I serve? Database ping allowed.
      httpGet: { path: /readyz, port: 8080 }
      periodSeconds: 2
      timeoutSeconds: 1
      failureThreshold: 3
    lifecycle:
      preStop:
        exec: { command: ["sleep", "5"] }   # let Endpoints propagate before draining
```

The rule that saves you: **liveness must not depend on anything external.** If `/healthz` queries the database, a database blip restarts every pod simultaneously, converting a recoverable degradation into a full outage with a thundering-herd reconnect on the other side. Readiness may depend on the database, because failing readiness removes you from the load balancer without killing you, and you rejoin when the dependency recovers. Kubernetes' own probe defaults are `periodSeconds: 10`, `timeoutSeconds: 1`, `failureThreshold: 3`, `successThreshold: 1`, so a default liveness config kills a pod **30 seconds** after the first failed probe. A readiness handler that takes longer than `timeoutSeconds: 1` is counted as a failure, which is why the `readyz` above has an internal 500 ms timeout.

`TOKIO_WORKER_THREADS` matters more than it looks. Tokio sizes its worker pool from `std::thread::available_parallelism()`, which on Linux respects `sched_setaffinity` but **not** the cgroup v2 CPU *quota*. A pod with `limits.cpu: 500m` on a 64-core node gets 64 worker threads competing for half a core: context-switch storms, terrible p99, and 64 × ~2 MiB of stack reservation. Set it explicitly to `ceil(cpu_limit)`.

**The memory profile, measured against the JVM alternative.** On the reference service:

| | This Rust service (measured) | Typical Spring Boot equivalent |
|---|---|---|
| RSS, idle | **3,140 KiB** (3.1 MiB) | 150-300 MB |
| RSS, after 3,000 requests | **3,540 KiB** (3.5 MiB) | 250-450 MB |
| OS threads at idle | **3** (main + 2 workers on 2 vCPU) | 25-60 (Tomcat pool, GC, JIT, JMX) |
| Startup to first served request | single-digit ms | 2-8 s (~50-100 ms with GraalVM native-image) |
| Container memory request you can defend | 64 MiB | 512 MiB - 1 GiB |
| Tail latency driver | allocator + syscalls | GC pauses + JIT deopt |

The Rust numbers are measured in this session; the JVM numbers are the ranges commonly reported and are *not* measured here, so quote them as ranges rather than facts. The structural reasons behind them are what an interviewer wants: no GC means no heap headroom multiplier (the JVM wants 2-5x live-set to keep pause times down), no JIT means no code cache or profiling metadata, no `Object` header means an 8-16 byte per-object saving, and Tokio's task model means concurrency does not cost a thread stack. The practical consequence is bin-packing: at 64 MiB per replica you fit 60+ replicas on a 4 GiB node instead of 6.

Two Rust-specific memory failure modes to be ready for, because "Rust has no GC" invites the follow-up "so how does it use too much memory?":

- **glibc arena growth that looks like a leak.** ptmalloc creates up to `8 × ncores` arenas and each retains freed memory rather than returning it to the OS. On a 32-core node, RSS can climb by hundreds of MB and plateau, which reads as a leak on a graph and is not one. `MALLOC_ARENA_MAX=2`, or switching to jemalloc/mimalloc (both of which return memory more aggressively and expose tuning), both fix it. `malloc_trim` via `MALLOC_TRIM_THRESHOLD_` is the blunter version.
- **There is no `OutOfMemoryError`.** Exceeding the cgroup limit gets you SIGKILL from the OOM killer: **exit code 137**, `Reason: OOMKilled`, no log line, no stack trace, no chance to flush your last spans. The mitigation is monitoring `container_memory_working_set_bytes` against the limit and, if you have unbounded per-request buffers, capping them (`DefaultBodyLimit`, which is **2 MB** by default for `Bytes`-based extractors, and an explicit `tower_http::limit::RequestBodyLimitLayer` for anything that streams).

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| All endpoints go to ~30 s latency then fail; `sqlx` logs `WARN` about slow acquires; DB CPU is low | Pool exhaustion. One slow query holds all `max_connections`; `acquire_timeout` default is 30 s so everything queues instead of failing | `acquire_timeout(3s)`, raise `max_connections` only after checking `replicas × max_conn ≤ pg max_connections − 3`, add `LoadShedLayer` + `ConcurrencyLimitLayer` to shed at the edge |
| All pods restart within 30 s of a database blip; DB then gets a reconnect storm | Liveness probe hits the database; `failureThreshold: 3 × periodSeconds: 10` = 30 s to SIGKILL | Liveness = process-only `/healthz`; move the DB check to readiness; add a `startupProbe` |
| An authenticated endpoint returns 200 with no credentials; tests pass; no error anywhere | `.layer(auth)` called **before** `.route(...)`. axum only wraps routes that already exist | Move `.layer()` after all `.route()` calls; use `route_layer` for auth; add an integration test that hits every route over HTTP with no token |
| Every 404 becomes 401; monitoring shows an auth-failure spike after a typo'd deploy | `Router::layer` also wraps the fallback | Use `Router::route_layer`, which runs only when a route matched |
| Handler compiles nowhere; error is `the trait bound ...: Handler<_, _> is not satisfied` | `Json<T>`/`Bytes`/`Multipart` not in the **last** argument position, or 17+ arguments, or a non-`IntoResponse` return | Move the body extractor last; add `#[axum::debug_handler]` to get an error that names the argument |
| CI image is 700 MB-1.2 GB; every build recompiles all deps | Single-stage `FROM rust:...` (308-569 MiB compressed base) plus `COPY . .` invalidating the cache | Multi-stage with `cargo-chef`; runtime stage `distroless/cc-debian12` (8.75 MiB); `.dockerignore` `target/` |
| Throughput flat or worse from 2 to 8 cores; `perf` shows cycles in `malloc`/`free` lock path; only in the Alpine image | musl's allocator serialises multithreaded allocation; measured up to 7x slowdown vs glibc | Move to `distroless/cc-debian12` on glibc; if static is required, `#[global_allocator]` = mimalloc or jemalloc |
| Intermittent `prepared statement "sqlx_s_7" does not exist`, only in prod, only under load | sqlx caches **named** prepared statements per connection (capacity 100); PgBouncer transaction pooling reuses server connections across clients | PgBouncer ≥ 1.21 with `max_prepared_statements > 0`, or `PgConnectOptions::statement_cache_capacity(0)` |
| Traces show unrelated requests nested under each other; only under concurrency | `span.enter()` guard held across an `.await`; `Span::enter` sets a **thread-local** current span and the worker polls other tasks at the await | `#[tracing::instrument]` or `.instrument(span)`; never hold an `Entered` guard across `.await` |
| One bad request kills the whole pod, taking every in-flight request with it | `panic = "abort"` in `[profile.release]` makes `CatchPanicLayer`'s `catch_unwind` a no-op and removes Tokio's per-task panic isolation | `panic = "unwind"` plus `CatchPanicLayer`; keep `RUST_BACKTRACE=1` |
| Pod dies with exit code 137, `OOMKilled`, no log line, no stack | Rust has no `OutOfMemoryError`; the kernel SIGKILLs. Usually an unbounded request body, an unbounded channel, or glibc arena growth | `DefaultBodyLimit` (2 MB default) and `RequestBodyLimitLayer`; bounded channels; `MALLOC_ARENA_MAX=2`; alert on working-set vs limit |
| 502s from the ingress for ~5 s on every rolling deploy | SIGTERM and Endpoints removal race; the pod stops accepting before the LB stops routing | `preStop: sleep 5`, `terminationGracePeriodSeconds` above your drain timeout, and drain with `with_graceful_shutdown` wrapped in a `timeout` |
| CI fails with `set DATABASE_URL to use query macros online, or run cargo sqlx prepare` | `.sqlx/` offline cache is stale relative to the SQL in the source | Run `cargo sqlx prepare --workspace`, commit `.sqlx/`, and add `cargo sqlx prepare --check` as a CI gate |
| The last few seconds of traces before any crash are always missing | Batch span processor buffers up to `max_queue_size = 2048` with a 5 s `scheduled_delay`, and the process exits without flushing | Call the tracer provider's `shutdown()` before `main` returns; raise the queue or sample if you exceed 2048 spans per 5 s |
| p99 is 250 ms with 4% CPU; timers fire late; healthchecks time out while the service is "up" | A blocking call on a Tokio worker thread (`std::fs`, a sync driver, `bcrypt`); see `T20-rust-async` | `spawn_blocking`, and `tokio-console` (`--cfg tokio_unstable`) to find it |
| Two writes that should be atomic are not; one commits, the other rolls back | Inside a transaction, a query was executed against `&pool` instead of `&mut *tx`, so it checked out a different connection | Grep for `&pool`/`&state.db` in any function that calls `begin()`; pass the transaction explicitly |
| p99 is spiky and CPU sits at exactly the limit on a big node | `TOKIO_WORKER_THREADS` unset; `available_parallelism()` reads host cores, not the cgroup CPU quota | Set `TOKIO_WORKER_THREADS` to `ceil(cpu limit)`; drop the CPU limit and keep a request |

---

## Tradeoffs & when NOT to use it

**Do not choose Rust for a service whose bottleneck is not the service.** If your handler spends 95% of its time waiting on Postgres and a third-party API, and you serve 200 rps, then FastAPI, Spring Boot, and axum all have the same p99 within noise, and you have paid Rust's costs for nothing. The costs are real and specific: a 117-second cold build for a *tiny* service (and 10-25 minutes for a large one), a hiring pool an order of magnitude smaller than Java's or Python's, a two-to-three-month ramp for a competent engineer to stop fighting the borrow checker in async code, and an ecosystem where the AWS SDK, the Kafka client, and the OpenTelemetry tracing SDK are all less mature than their Java equivalents. The honest framing is that Rust buys you memory (3 MiB vs 300 MB), tail latency (no GC), and a class of bug eliminated at compile time, and it costs you iteration speed and staffing flexibility.

**Do not choose it for a service that changes shape weekly.** A product surface still in discovery, where the data model is rewritten twice a month, is where Rust's compile-time guarantees turn into compile-time *friction*: a schema change means a `cargo sqlx prepare` plus a wave of type errors across every touched query. That is a feature in year three and a tax in month two. Ship the prototype in the language your team is fastest in, and port the hot path when you know what it is. This is exactly the FastAPI-to-Rust migration story, and the version of it that works is porting one service, not the platform.

**Do not choose it where the runtime is the product's constraint.** Serverless with per-invocation billing is a genuine Rust win (single-digit-ms cold starts, tiny memory tier). But if your organisation's deployment substrate is a JVM app server, a Databricks cluster, or anything where "a container that runs a static binary" is not a first-class unit, you will spend more on integration than you save on CPU.

**Do not reach for tower's raw middleware when tower-http has an infallible version.** `tower::timeout::Timeout` composes with axum only through `HandleErrorLayer`, and every layer of that boilerplate is a place to get the ordering wrong. If the answer exists in tower-http, use it.

**Do not use sqlx's compile-time macros for genuinely dynamic queries.** A search endpoint with 12 optional filters is not a `query!` problem; it is a `QueryBuilder` problem, and forcing it into the macro produces either 4,096 branches or a `format!` you have to wrap in `AssertSqlSafe`. Use the unchecked function form deliberately, with bound parameters and an identifier allowlist, and write the integration test the macro would have replaced.

**Do not add an ORM by default.** SeaORM is well built and it sits on top of sqlx, so you inherit sqlx's compile times plus its own generics, and you get generated SQL you did not write. The case for it is a large entity graph with heavy relationship traversal where mapping code would otherwise dominate. In a 20-table CRUD service it is a layer you will spend time working around.

**Do not use `panic = "abort"`, musl, or `codegen-units = 1` because a blog post said they were faster.** Each has a measured cost on a service workload: no panic isolation, an allocator that can cost you a multiple of throughput, and serialised codegen that lengthens every build. Two of the three are usually wrong for a service.

**Where the counter-argument is strongest:** the case *for* Rust in a boring CRUD service is not performance, it is that the same team runs 8 replicas instead of 40, that the p99 has no GC saw-tooth so SLO alerting stops being noisy, that null-pointer and data-race classes of incident stop happening, and that the deploy artefact is a 26 MB image with a 12-package CVE surface instead of a 400 MB image with a base OS. Those are operational wins, not benchmark wins, and they are the honest reason to pick it. If your organisation does not feel any of those pains, the answer is genuinely "keep shipping Spring Boot."

---

## Interview questions

### Q1 — Walk me through what happens to an HTTP request from the TCP accept to your handler in axum.

**Testing:** whether you know axum is a `tower::Service` composition rather than a framework with hidden machinery.

**Answer:** `axum::serve` owns a `TcpListener` and loops on `accept()`. Each accepted connection is spawned as its own Tokio task running a hyper 1.x connection driver, which parses HTTP/1.1 or HTTP/2 frames and produces an `http::Request<Body>`. That request is passed to the `Router`, which is a `tower::Service<Request<Body>, Response = Response<Body>, Error = Infallible>`. Middleware layers wrap the router, outermost first, and each is a `Service` that may inspect or short-circuit. The router then routes: axum uses `matchit`, a radix tree, to match the path and pull out `{}`-style parameters, then hands off to the `MethodRouter` for that path, which dispatches on the HTTP method or returns 405 with an `Allow` header. The handler's extractors are then resolved left to right: every argument except the last calls `FromRequestParts::from_request_parts(&mut Parts, &S)`, and the last argument calls `FromRequest::from_request(Request, &S)` because it may consume the body. Any extractor's `Rejection` is `IntoResponse` and short-circuits. Finally the handler's return value goes through `IntoResponse` to become a `Response`. The `Error = Infallible` is the design centre: there is no error channel, every failure is already a response.

**Follow-up trap:** "So where do you put backpressure?" The wrong answer is "a rate limiter in the handler." The right answer is `Service::poll_ready`, which is the half of the `Service` trait that exists for exactly this: a middleware returns `Poll::Pending` from `poll_ready` to refuse work. `ConcurrencyLimitLayer` holds a semaphore permit there. Then the second half of the trap: a concurrency limit *alone* converts overload into an unbounded wait, so you stack `LoadShedLayer` above it to turn "not ready" into a fast 503 rather than a queue.

### Q2 — Why can `Json<T>` only be the last argument of a handler?

**Testing:** whether you understand `FromRequestParts` versus `FromRequest`, or just memorised the rule.

**Answer:** they are two different traits. `FromRequestParts` takes `&mut http::request::Parts`, which is the head only (method, URI, version, headers, extensions), so any number of them can run in sequence, each mutating the parts. `FromRequest` takes the whole `Request` **by value** because it needs the body, and a body is a stream that can only be consumed once. axum's `Handler` impl is generated by a macro over arities 1 through 16 where `T1..T15` are bound by `FromRequestParts` and only `T16` by `FromRequest`. Put `Json<T>` in the middle and the bound fails; because it fails on the whole `Handler` trait, the error message is unhelpful, which is why `#[axum::debug_handler]` exists.

**Follow-up trap:** "What if I need two body extractors?" You cannot have two, and the trap is to say "clone the body." The body is a stream, not a buffer. If you need to both validate and deserialise, write one custom `FromRequest` extractor that buffers with `Bytes` once (subject to the 2 MB `DefaultBodyLimit`) and does both, or buffer into an `Extension` in middleware. And the second half: extractors also run **left to right and short-circuit**, so an auth extractor placed *after* `Json<T>` means you have already buffered up to 2 MB from an unauthenticated caller.

### Q3 — `State` or `Extension`? When would you use each?

**Testing:** compile-time versus runtime failure, and whether you can name the actual error.

**Answer:** `State<S>` is checked at compile time. `Router<S>` carries the required state in its type, `with_state` discharges it, and `axum::serve` requires `Router<()>`, so forgetting the state is a compile error, and asking for the wrong state type in a handler is a compile error. `Extension<T>` is a `TypeId`-keyed slot in `http::Extensions`, checked at runtime, and its rejection when missing is a **500** with `Missing request extension: Extension of type 'T' was not found`. So `State` for anything known at startup (pool, HTTP client, config), `Extension` for per-request data injected by a middleware layer (request id, trace context, an auth principal produced by a `Layer` rather than an extractor), because `State` cannot express "set per request." Use `FromRef` to project a substate so a handler can ask for `State<PgPool>` off a bigger `AppState`.

**Follow-up trap:** "Is `State` free?" No: `with_state` **clones the state on every request**, so every field must be cheap to clone. `PgPool` and `reqwest::Client` are internally `Arc`ed and clone in nanoseconds; a `HashMap` of 50,000 entries in `AppState` is 50,000 allocations per request. The rule is that everything in `AppState` is `Arc`-shaped.

### Q4 — I add `.layer(RequireAuth)` and my endpoint is still unauthenticated. What happened?

**Testing:** the single highest-consequence axum gotcha.

**Answer:** `Router::layer` wraps only the routes that exist on the router **at the moment it is called**. The docs state it: "the middleware is only applied to existing routes... Additional routes added after `layer` is called will not have the middleware added." So `Router::new().layer(auth).route("/admin", get(h))` wraps an empty router and leaves `/admin` open, with no compile error and no warning. Fix: all `.route()` and `.nest()` calls first, `.layer()` last. And use `route_layer` rather than `layer` for anything that rejects early, because `Router::layer` also wraps the fallback and would turn every 404 into a 401. The structural defence is an integration test that enumerates every route and asserts a 401 without credentials.

**Follow-up trap:** "Fine, so I'll chain `.layer(A).layer(B)` in the order I want them to run." That is backwards. Chained `Router::layer` calls nest **inside-out**: `.layer(A).layer(B)` gives `B(A(router))`, so B sees the request first. `ServiceBuilder` is the opposite: `ServiceBuilder::new().layer(A).layer(B)` gives `A(B(...))`, and tower's docs say "layers that are added first will be called with the request first." Build one `ServiceBuilder` and pass it to one `.layer()` call; that is the axum-recommended convention precisely because the two orders read identically.

### Q5 — How do you do error handling in axum, compared to Spring's `@ControllerAdvice`?

**Testing:** whether `IntoResponse` clicked, and whether you log at the right layer.

**Answer:** the `IntoResponse` impl on your own error enum *is* the exception mapper, and it is checked at compile time rather than wired by an AOP proxy. Define `enum ApiError` with `thiserror`, derive `From<sqlx::Error>` so handlers use `?`, and implement `IntoResponse` to map each variant to a status, a stable machine-readable code, and a safe message. Handlers return `Result<Json<T>, ApiError>`, which is `IntoResponse` because both arms are. Log the full error chain exactly once, inside `into_response`, at `error!` for 5xx and `warn!` for 4xx, so you do not get the same failure logged five times up the stack. `sqlx::Error::RowNotFound` maps to 404, not 500.

**Follow-up trap:** "Show me the client-visible body." The trap is `self.to_string()` on a `#[error(transparent)]` database variant, which renders sqlx's `Display` and can leak table names, column names, and constraint names to the caller. That is an information-disclosure finding. Give the 5xx variant a fixed `#[error("internal error")]` or hardcode the client message per status, and keep the real detail in the log with the request id.

### Q6 — Size the sqlx connection pool for a service doing 2,000 rps.

**Testing:** whether you reach for Little's Law and whether you know the constraint is on the database side.

**Answer:** `L = λ × W`. If each request runs 2 queries averaging 1.5 ms, it holds a connection for ~3 ms, so mean concurrent connections = `2000 × 0.003 = 6`. Size for utilisation `ρ ≤ 0.7` because queueing delay scales as `1/(1-ρ)`, giving ~9. Round to 12-16 for tail headroom. Then check the other side: Postgres defaults to `max_connections = 100` with 3 superuser-reserved, each backend costs 5-10 MB plus `work_mem`, and throughput stops improving past roughly 2-4x core count in active connections. So the binding constraint is `(replicas + maxSurge) × max_connections ≤ 97`. At 10 replicas you get 8-9 each, not 16, and if you need more you put PgBouncer in transaction mode in front (`default_pool_size` 20, `max_client_conn` 100 by default) rather than raising Postgres' limit. Also change `acquire_timeout` from its **30 s** default to ~3 s so exhaustion becomes a fast 503 you can see in your own metrics.

**Follow-up trap:** "You put PgBouncer in transaction mode. What breaks?" sqlx uses **named** prepared statements and caches them per connection (`statement_cache_capacity`, default 100). Transaction-level pooling reuses server connections across clients, so a cached statement name can be missing on the connection you get. Symptom: intermittent `prepared statement "sqlx_s_N" does not exist` under load and never in staging. Fix: PgBouncer 1.21+ with `max_prepared_statements > 0`, or `statement_cache_capacity(0)` on the client, which costs a parse per query. Second half of the trap: sqlx's migration advisory lock is session-scoped and does not survive transaction pooling either, so `Migrator::set_locking(false)` and run migrations through a direct connection.

### Q7 — What does `cargo sqlx prepare` actually do, and what does it cost you in CI?

**Testing:** whether you have run this in anger or read the README.

**Answer:** `sqlx::query!` connects to `DATABASE_URL` at **compile time** and issues a describe for each query to get parameter types, result column types, and nullability. `cargo sqlx prepare` does that once and writes one JSON file per unique query into `.sqlx/`, named by the SHA-256 of the SQL; you commit that directory and build with `SQLX_OFFLINE=true`. The costs: you must regenerate on every SQL change or the build fails with `set DATABASE_URL to use query macros online, or run cargo sqlx prepare`; you need a CI gate (`cargo sqlx prepare --check --workspace`) plus a Postgres service container to run it; `.sqlx/` is a small merge-conflict surface; and it sits in your Docker build context so any SQL change invalidates the application build layer, though not the `cargo-chef` dependency layer.

**Follow-up trap:** "Your `count(*)` came back as `Option<i64>`. Why, and how do you fix it?" Because Postgres reports nullability conservatively for any expression or aggregate, and for the nullable side of a `LEFT JOIN`. The fix is the column-annotation syntax: `count(o.id) as "order_count!: i64"` where `!` forces non-null, `?` forces nullable, and `: Type` overrides the Rust type. Then the sting: sqlx **0.9.0** changed Postgres nullability inference ("force generic plan for better nullability inference," listed as breaking), so a 0.8 → 0.9 upgrade can produce a wave of type errors in queries that compiled yesterday.

### Q8 — Why `tracing` instead of `log` for an async service?

**Testing:** whether you can name the mechanism, not just say "structured logging."

**Answer:** `log` correlates by (timestamp, thread id, module path). On a Tokio multi-thread runtime a single worker interleaves polls from thousands of tasks, so consecutive lines from one thread routinely belong to different requests, and one request's lines are scattered across every worker because work-stealing migrates the task. The MDC/ThreadLocal pattern that works in Spring works because Servlet containers are genuinely thread-per-request; here it is actively wrong. `tracing` attaches a **span** to the *future* rather than the thread: `.instrument(span)` or `#[instrument]` enters the span at the start of every `poll` and exits at every return, so context follows the task across workers. Spans nest into a tree, so an `error!` at depth five automatically carries request id, route, and tenant from its ancestors. Cost: a disabled callsite is a cached atomic `Interest` check plus a `STATIC_MAX_LEVEL` comparison, single-digit nanoseconds, and `release_max_level_info` compiles `trace!` out entirely.

**Follow-up trap:** "Can I just do `let _g = span.enter();` at the top of my async handler?" No, and this is the classic bug. `Span::enter()` sets a **thread-local** current span. When the task hits `.await` and yields, the worker polls a different task, whose events are then attributed to your span. You get traces where unrelated requests nest inside each other, only under concurrency, and never in a unit test. Use `#[instrument]` or `.instrument()`, which enter/exit per poll.

### Q9 — Your service returns 503 for 5 seconds on every deploy. Diagnose.

**Testing:** graceful shutdown and the Kubernetes lifecycle, not just `with_graceful_shutdown`.

**Answer:** SIGTERM and Endpoints removal happen **concurrently** in Kubernetes, and kube-proxy/ingress convergence takes 1-5 seconds. If the process stops accepting the moment SIGTERM lands, connections still being routed to it get refused. Three fixes together: a `preStop` hook of `sleep 5` so the pod stays up while Endpoints propagate; `axum::serve(...).with_graceful_shutdown(signal)` to drain in-flight requests; and a `tokio::time::timeout` around the whole server future so a long-poll connection cannot hold shutdown open past `terminationGracePeriodSeconds` (default **30 s** before SIGKILL). Close the pool with `pool.close().await` **after** the server returns, and shut down the tracer provider so the last batch of spans flushes.

**Follow-up trap:** "You called `with_graceful_shutdown` and you still lost data." Because it drains *connections*, not the tasks your handlers spawned. A `tokio::spawn`ed "write the audit record" future is dropped when the runtime shuts down, silently. Use a `CancellationToken` plus `tokio_util::task::TaskTracker`, or an mpsc whose receiver you drain before returning. And remember, from `T20-rust-async`, that cancellation in Rust is `drop`: there is no `finally` and no async destructor, so anything that must complete has to be structurally awaited, not detached.

### Q10 — Design the liveness and readiness probes.

**Testing:** whether you have been paged by a cascading restart.

**Answer:** liveness answers "is this process wedged," so it must check nothing external: a handler returning a constant, registered before any auth layer. Readiness answers "should I get traffic," so it may ping the database, with an internal timeout (300-500 ms) because `readinessProbe.timeoutSeconds` defaults to **1 second** and a slow response counts as a failure. A `startupProbe` covers slow starts (migrations, pool warm-up) so liveness does not kill you during boot. Kubernetes defaults are `periodSeconds: 10`, `timeoutSeconds: 1`, `failureThreshold: 3`, so a default liveness config SIGKILLs the pod 30 seconds after the first failed probe. Putting the database in liveness means one database blip restarts every replica simultaneously and the database then eats a reconnect storm from every pod at once, converting a degradation into an outage.

**Follow-up trap:** "Your readiness probe returns 200 but the pod serves errors." Readiness that only pings the database misses pool exhaustion, because a `select 1` can be served by a connection the probe itself acquired while every application request queues. Make readiness reflect the thing that is actually broken: check `pool.size()` versus `pool.num_idle()`, or export the pool gauge and fail readiness when idle has been zero for N seconds. And never let readiness be *more* expensive than a real request, or the probe becomes the load.

### Q11 — Your image is 1.1 GB and CI takes 22 minutes. Fix it, with numbers.

**Testing:** whether you know the actual mechanics of Docker layer caching against Cargo.

**Answer:** two separate problems. Size: a single-stage `FROM rust:1.97-slim` ships a **308 MiB compressed** toolchain base plus a `target/` directory that measured **1.4 GB** on the reference service. Multi-stage, copying only the binary into `gcr.io/distroless/cc-debian12` (**8.75 MiB compressed**), with `strip = true` taking the binary from 8,418,352 B to **3,539,024 B**, gives roughly a **12 MiB compressed / 26 MB on-disk** final image. Speed: `COPY . .` before `cargo build` invalidates the cache on any file change, so all 179 dependency crates rebuild. `cargo-chef` splits it: `cargo chef prepare` emits a `recipe.json` describing only the dependency graph, `cargo chef cook --release` builds only dependencies into a layer that is invalidated solely by `Cargo.toml`/`Cargo.lock`, and then the application build is the only thing that reruns. Measured on the reference service, 2 vCPU: cold **117 s**, warm **24 s**, a **4.9x** win, matching the ~5x reported on a 500-dependency commercial codebase and ~9x on ExpressVPN's repository.

**Follow-up trap:** "We added cargo-chef and the build got *slower*." That happens and it is documented: if your CI runner has no persistent layer cache, cargo-chef adds a planner stage and a dummy-source dependency build **on top of** the real one, and there is a well-known issue thread of a build going from 5 minutes to 25. cargo-chef only pays off when layers persist: `buildx --cache-from/--cache-to` against a registry, or a self-hosted runner. The alternative on BuildKit is `RUN --mount=type=cache,target=/usr/local/cargo/registry --mount=type=cache,target=/app/target`, which is simpler but produces a cache tied to that machine rather than a portable layer.

### Q12 — Alpine gives a 4 MB image. Why shouldn't I use it?

**Testing:** whether you have actually deployed Rust or read a listicle.

**Answer:** Alpine means musl, and musl's `malloc` serialises multithreaded allocation far harder than glibc's ptmalloc, which spreads threads across up to `8 × ncores` arenas. Rust allocates constantly (every `String`, `Vec`, boxed future, `serde_json` document), so the contention lands on your hot path. Reported measurements go up to a **7x** slowdown on allocation-heavy workloads versus glibc, and it worsens with thread count. The recognisable symptom is throughput that scales to 2 threads and then flattens or regresses as you add cores, with `perf` showing cycles inside musl's `malloc` lock path. The default answer is: build for `x86_64-unknown-linux-gnu` and run on `distroless/cc-debian12` at 8.75 MiB compressed. You are trading 8 MiB of image for a multiple of your throughput. If you genuinely need a static binary (`distroless/static-debian12` is **0.67 MiB compressed**), replace the allocator with `#[global_allocator] static G: MiMalloc = MiMalloc;`, because mimalloc builds cleanly on musl and has been measured pushing musl past glibc's default.

**Follow-up trap:** "Anything else about musl?" Two things that are not the allocator. Static musl binaries do their own DNS resolution instead of going through glibc's NSS, so `/etc/nsswitch.conf` is ignored and musl's handling of multiple nameservers and the `ndots:5` search path differs from glibc, which is precisely what Kubernetes injects; the symptom is intermittent `failed to lookup address information` for in-cluster names that resolve fine from a debug pod. And cross-compiling to musl needs `musl-gcc`, `cross`, or `cargo-zigbuild`, which is another CI moving part. Also worth saying: Rust dropped jemalloc from the standard library in **1.32.0 (2019)** and uses the system allocator, which is exactly why the base image's libc is a performance decision at all.

### Q13 — How does this service's memory profile compare to the Spring Boot version, and where does Rust still use too much memory?

**Testing:** whether you have real numbers and whether you can argue the other side.

**Answer:** measured on the reference service (axum + sqlx + tracing, 2 vCPU, Rust 1.97.1): **3,140 KiB RSS at idle**, **3,540 KiB after 3,000 requests**, **3 OS threads**, single-digit-millisecond startup. The Spring Boot equivalent is commonly 150-400 MB RSS with 25-60 threads and a 2-8 second startup, so roughly two orders of magnitude on memory. The structural reasons: no GC means no live-set headroom multiplier (the JVM wants 2-5x to keep pauses bounded), no JIT means no code cache or profiling metadata, no object header, and Tokio's tasks mean concurrency does not cost a thread stack. The operational consequence is bin-packing: a defensible request is 64 MiB instead of 512 MiB, so you fit 60 replicas per 4 GiB node instead of 6. Where Rust still uses too much: **glibc arena growth**, where ptmalloc creates up to `8 × ncores` arenas that retain freed memory, so RSS climbs by hundreds of MB on a 32-core node and looks exactly like a leak; `MALLOC_ARENA_MAX=2` or switching to jemalloc/mimalloc fixes it.

**Follow-up trap:** "So Rust can't OOM?" It absolutely can, and it is worse than the JVM's version because there is no `OutOfMemoryError` to catch and no heap dump. You get SIGKILL from the kernel: **exit code 137**, `Reason: OOMKilled`, no log line, no stack, no flushed spans. The usual causes are an unbounded request body, an unbounded channel, or arena growth. Cap bodies (`DefaultBodyLimit` is **2 MB** by default for `Bytes`-based extractors), bound every channel, and alert on `container_memory_working_set_bytes` against the limit rather than waiting for the restart.

### Q14 — What would make you tell a team not to build this service in Rust?

**Testing:** senior judgement; whether you can argue against your own tool.

**Answer:** four conditions, any one of which is enough. First, the bottleneck is not the service: if the handler waits 95% of its time on Postgres and a third-party API at 200 rps, axum, FastAPI, and Spring Boot have the same p99 within noise, and you paid for nothing. Second, the shape changes weekly: in discovery, Rust's compile-time guarantees are compile-time friction, and every schema change means `cargo sqlx prepare` plus a wave of type errors, which is a feature in year three and a tax in month two. Third, staffing: the hiring pool is an order of magnitude smaller than Java's, and a competent engineer takes two to three months to stop fighting async lifetimes; if this service needs to be maintained by a rotating on-call team of twelve, that cost is real and recurring. Fourth, ecosystem gaps that matter to *your* service: the Kafka client, the AWS SDK, and the OpenTelemetry **traces** SDK (still Beta at the 0.32 line while Logs and Metrics are Stable) are all less mature than their Java equivalents. The honest positive case is operational, not benchmark: 8 replicas instead of 40, no GC saw-tooth in the p99, a 26 MB image with a dozen packages of CVE surface, and whole classes of incident eliminated at compile time. If a team feels none of those pains, keep shipping Spring Boot.

**Follow-up trap:** "You said the bottleneck is the database, so Rust is pointless. But we're on Lambda." That flips the answer. Per-invocation billing and cold starts are where Rust's profile is decisive: single-digit-millisecond cold start against 2-8 seconds for a JVM, and the smallest memory tier instead of 512 MB-1 GB, and the billing dimension is memory-time. The general lesson is that the language choice follows the *constraint*, not the workload description, and the constraint on serverless is startup and memory, not steady-state throughput.

---

## Red flags that fail you

- "axum is like Spring Boot for Rust." It is not a framework in that sense; there is no DI container, no classpath scan, no annotation processor. Saying this signals you have not looked underneath.
- Not knowing that `Router` is a `tower::Service` with `Error = Infallible`, and then being unable to explain why `tower::timeout::Timeout` does not compose without `HandleErrorLayer`.
- Explaining middleware ordering as "top to bottom" without distinguishing `ServiceBuilder` (top-down) from chained `Router::layer` (inside-out). They read identically and mean the opposite.
- Leaving `acquire_timeout` at its 30-second default and calling that "resilient." It is the opposite: it converts a fast failure into a stall the client has already given up on.
- Sizing the pool without ever mentioning the database's `max_connections`, or forgetting to multiply by replica count plus `maxSurge`.
- Putting the database in the liveness probe. This is the single most reliable way to turn a blip into an outage, and interviewers who have lived it will stop the interview there.
- "Rust has no GC so memory is not a concern." Say that and the follow-up about exit code 137 and glibc arenas will be unpleasant.
- Reaching for Alpine/musl for image size with no awareness of the allocator cost, or claiming musl is "basically the same as glibc."
- Holding `span.enter()` across an `.await`, or not knowing why that is wrong.
- `panic = "abort"` on a service, especially while also claiming `CatchPanicLayer` protects you. It does not; `catch_unwind` is a no-op under abort.
- Logging the same error at three layers, or serialising a `sqlx::Error` into the client-facing response body.
- Claiming Rust is always the right choice. The senior signal is naming the four conditions under which it is not.

## Cheat card

```
axum 0.8.9 (2026-04-14, MSRV 1.80) | tower 0.5.3 | tower-http 0.7.0 | hyper 1.11
sqlx 0.9.0 (2026-05-06, MSRV 1.94) | tracing 0.1.44 | tracing-subscriber 0.3.23
Router = tower::Service<Request, Response=Response, Error=Infallible>  <- no error channel
Handler: args 1..15 = FromRequestParts(&mut Parts); LAST = FromRequest (owns body). Max 16.
Extractors run left->right and short-circuit. #[axum::debug_handler] names the bad arg.
State<S> = compile-time (Router<S> -> with_state -> Router<()>); Extension<T> = runtime 500.
State is CLONED per request -> every field must be Arc-shaped.
Router::layer wraps only routes ALREADY added, AND wraps the fallback (404->401).
  route_layer = only on matched routes; panics if no routes yet. Use it for auth.
ServiceBuilder: first .layer() = OUTERMOST. Chained Router::layer: LAST = outermost. Opposite.
sqlx defaults: max_connections=10 min=0 acquire_timeout=30s idle=600s max_lifetime=1800s
  test_before_acquire=true acquire_slow_threshold=2s stmt_cache=100. Set acquire_timeout=3s.
Pool size = rps x sec_per_request / 0.7. Check (replicas+surge) x pool <= pg max_conn(100)-3.
query! nullability: as "x!" force non-null | "x?" force null | "x: T" retype. cargo sqlx prepare -> .sqlx/
Transaction: &mut *tx (NOT &pool). Drop = rollback. tx.begin() = SAVEPOINT. Retry 40001/40P01.
NEVER hold span.enter() across .await (thread-local). Use #[instrument] / .instrument().
Measured (2 vCPU, rustc 1.97.1): 179 crates | cold 117s | warm 24s (4.9x, cargo-chef)
  binary 8.03 MiB -> 3.38 MiB stripped | RSS 3.1 MiB idle, 3.5 MiB @3k req, 3 threads
Images compressed: rust:1.97-slim 308 MiB | debian-slim 27 MiB | distroless/cc 8.75 MiB
  distroless/static 0.67 MiB | alpine 3.6 MiB (musl: up to 7x slower; use mimalloc if forced)
panic="abort" kills CatchPanicLayer + Tokio task isolation. Use unwind on a service.
Liveness = no deps. Readiness = deps, <500ms. k8s probe defaults 10s/1s/3 -> 30s to SIGKILL.
preStop sleep 5 + graceful shutdown in a timeout < terminationGracePeriodSeconds (30s).
TOKIO_WORKER_THREADS: available_parallelism ignores the cgroup CPU quota. Set it.
DefaultBodyLimit = 2 MB. OOM = exit 137, no stack. OTel batch: queue 2048, delay 5s, batch 512.
```

## Sources

- [axum CHANGELOG (main)](https://github.com/tokio-rs/axum/blob/main/axum/CHANGELOG.md) — accessed 2026-08-05
- [Announcing axum 0.8.0 — tokio.rs blog](https://tokio.rs/blog/2025-01-01-announcing-axum-0-8-0) — accessed 2026-08-05
- [axum `Router::layer` / `route_layer` docs source](https://github.com/tokio-rs/axum/blob/main/axum/src/docs/routing/route_layer.md) — accessed 2026-08-05
- [axum `all_the_tuples!` (16-extractor arity limit)](https://github.com/tokio-rs/axum/blob/main/axum-core/src/macros.rs) — accessed 2026-08-05
- [axum `DefaultBodyLimit` (2 MB default)](https://github.com/tokio-rs/axum/blob/main/axum-core/src/extract/default_body_limit.rs) — accessed 2026-08-05
- [tower `ServiceBuilder` ordering docs](https://github.com/tower-rs/tower/blob/master/tower/src/builder/mod.rs) — accessed 2026-08-05
- [tower-http 0.7.0 CHANGELOG](https://github.com/tower-rs/tower-http/blob/main/tower-http/CHANGELOG.md) — accessed 2026-08-05
- [sqlx 0.9.0 CHANGELOG](https://github.com/launchbadge/sqlx/blob/main/CHANGELOG.md) — accessed 2026-08-05
- [sqlx `PoolOptions` defaults, source](https://github.com/launchbadge/sqlx/blob/main/sqlx-core/src/pool/options.rs) — accessed 2026-08-05
- [sqlx docs.rs — `PoolOptions`](https://docs.rs/sqlx/latest/sqlx/pool/struct.PoolOptions.html) — accessed 2026-08-05
- [tracing docs.rs](https://docs.rs/tracing/latest/tracing/) — accessed 2026-08-05
- [tracing-subscriber docs.rs](https://docs.rs/tracing-subscriber/latest/tracing_subscriber/) — accessed 2026-08-05
- [opentelemetry-rust (component status: Logs/Metrics Stable, Traces Beta)](https://github.com/open-telemetry/opentelemetry-rust) — accessed 2026-08-05
- [OpenTelemetry Rust exporters docs](https://opentelemetry.io/docs/languages/rust/exporters/) — accessed 2026-08-05
- [cargo-chef](https://github.com/LukeMathWalker/cargo-chef) — accessed 2026-08-05
- [5x Faster Rust Docker Builds with cargo-chef — Luca Palmieri](https://lpalmieri.com/posts/fast-rust-docker-builds/) — accessed 2026-08-05
- [cargo-chef issue #273: build time went from 5 to 25 minutes](https://github.com/LukeMathWalker/cargo-chef/issues/273) — accessed 2026-08-05
- [GoogleContainerTools/distroless](https://github.com/GoogleContainerTools/distroless) — accessed 2026-08-05
- [Default musl allocator considered harmful (to performance) — nickb.dev](https://nickb.dev/blog/default-musl-allocator-considered-harmful-to-performance/) — accessed 2026-08-05
- [Why does musl make my Rust code so slow? — Andy Grove](https://andygrove.io/2020/05/why-musl-extremely-slow/) — accessed 2026-08-05
- [Kubernetes: Configure Liveness, Readiness and Startup Probes](https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/) — accessed 2026-08-05
- [PostgreSQL runtime config: connection settings](https://www.postgresql.org/docs/current/runtime-config-connection.html) — accessed 2026-08-05
- [PgBouncer configuration reference](https://www.pgbouncer.org/config.html) — accessed 2026-08-05
- [Rust release notes (1.97.1, 1.32.0 jemalloc removal)](https://doc.rust-lang.org/stable/releases.html) — accessed 2026-08-05
- [crates.io API — version and publish dates for axum, sqlx, tower-http, tokio, hyper](https://crates.io/crates/axum/versions) — accessed 2026-08-05

Measured in this session on a 2 vCPU / 3.9 GiB Linux sandbox with `rustc 1.97.1 (8bab26f4f 2026-07-14)`: crate counts, cold/warm build times, stripped/unstripped binary sizes, `target/` sizes, and idle/loaded RSS and thread counts. Container base-image sizes were read from the Docker Hub and gcr.io registry APIs on 2026-08-05 and are **compressed** amd64 sizes.

## Changelog
- 2026-08-05 — created
