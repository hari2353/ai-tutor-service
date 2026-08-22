# Go: Worker Pools, gRPC, and a Fast Vector-Search Microservice

> **Track:** T11 Polyglot Backend · **Time:** 2.5h · **Prereqs:** T11-go-core · **Updated:** 2026-08-03
> **Module id:** `T11-go-services` · **Tags:** go

## The 30-second version

A production worker pool in Go is a bounded-concurrency pipeline, not just "spawn N goroutines" — the pattern that actually survives load has a fixed-size worker set reading from a channel (bounding memory and downstream pressure), explicit backpressure (a bounded input channel that blocks the producer rather than an unbounded one that just grows until OOM), and every worker exiting cleanly on `context` cancellation, per the discipline in `T11-go-core`. gRPC is Go's (and most polyglot backends') default choice for internal service-to-service calls specifically because it multiplexes many concurrent RPCs over a **single HTTP/2 TCP connection** with binary Protobuf framing — avoiding REST/JSON's per-request connection or header overhead — and because `context.Context` deadlines propagate automatically as wire metadata to the server, so a client's 2-second budget is visible and enforceable on the far side of the call, not just locally. The real gRPC gotcha at scale: a single HTTP/2 connection means a client-side load balancer that only balances *connections* (not RPCs) can pin all traffic to one backend pod even with many concurrent streams, because HTTP/2 multiplexes streams over the same TCP connection rather than opening a new one per call — the fix is either client-side, request-level load balancing (gRPC's own `grpc.WithDefaultServiceConfig` round-robin policy resolving multiple backend addresses) or an L7-aware proxy (Envoy) in front, not a plain L4 load balancer that only sees one long-lived TCP stream. A fast vector-search microservice in Go is fundamentally an HNSW (Hierarchical Navigable Small World) approximate-nearest-neighbor index wrapped in a thin gRPC or HTTP layer — the three parameters that actually determine its recall/latency/memory tradeoff are `M` (graph connectivity per node, typically 12-48, higher for high-dimensional embeddings), `efConstruction` (build-time search breadth, higher means slower index build but better graph quality), and `efSearch` (query-time search breadth, the only one of the three you can tune live, trading recall for latency per query) — and the honest reason to build this in Go rather than reach for a managed vector database is when the recall/latency budget and memory footprint need tuning below what a general-purpose vector DB's abstraction allows, or when it needs to be embedded directly in a low-latency serving path rather than a network hop away.

## Why this gets asked

Because "Go for backend services" interviews specifically probe whether a candidate has built something under real concurrent load, not just written idiomatic single-request handlers — worker pools and gRPC are where Go's concurrency model actually earns its keep in a way Python or Java rarely make as visible. The interviewer has likely debugged a gRPC service that looked horizontally scaled on paper (multiple pods behind a load balancer) but was actually funneling all traffic through one pod because nobody accounted for HTTP/2 connection-level load balancing, or watched an "unbounded worker pool" (spawn a goroutine per incoming item with no cap) take down a service under a traffic spike because nothing bounded concurrent downstream calls. The vector-search microservice angle specifically tests whether resume claims about RAG/embeddings translate to knowing the actual index structure underneath — a lot of engineers can call a vector DB's API and very few can explain why `efSearch` is the one knob you'd actually expose as a per-query tuning parameter in production.

---

## Lineage: past → present → future

**What came before.** Pre-gRPC internal service communication meant either REST/JSON over HTTP/1.1 (human-readable, ubiquitous tooling, but a new TCP connection — or connection-pool checkout — per logical request under HTTP/1.1's head-of-line-blocking-prone model, plus JSON's text-based parsing and larger payload size versus a binary format) or older RPC frameworks (Thrift, CORBA, Java RMI) that solved the binary-efficiency problem but were largely single-language or required heavyweight IDL tooling with poor cross-language ergonomics. Google's internal Stubby RPC system (used at massive internal scale for years before being open-sourced) directly motivated gRPC's 2015 public release: Protobuf as the wire format (already Google-internal-standard), HTTP/2 as the transport (multiplexing, header compression, built-in flow control — a genuine transport-layer upgrade over HTTP/1.1, not just a payload format change), and generated client/server stubs across languages from one `.proto` schema.

**Where it stands now.** gRPC is the dominant choice for internal, service-to-service, polyglot backend communication at companies operating more than a handful of services — genuinely production-standard for that specific use case, not a niche choice. It is *not* generally the choice for public-facing/browser-facing APIs (browsers can't easily speak raw HTTP/2 trailers-based gRPC without a proxy layer like grpc-web, and REST/JSON's tooling ubiquity and human-debuggability still win for external, partner-facing, or webhook-style APIs — see `T11-api-design` for the fuller REST/gRPC/GraphQL comparison). For Go specifically, worker pools remain the idiomatic pattern for any bounded-concurrency fan-out (batch processing, rate-limited downstream calls, CPU-bound parallel work capped near `GOMAXPROCS`), and the `golang.org/x/sync/errgroup` package has become the de facto standard library-adjacent tool for coordinating a worker group's errors and shared cancellation rather than hand-rolling the channel plumbing every time. On vector search specifically: HNSW remains the dominant algorithm underlying most production approximate-nearest-neighbor systems (it's what Weaviate, Qdrant, and pgvector's HNSW index type all implement internally), with the live disagreement being less about the algorithm and more about build-vs-buy — a managed vector database (Weaviate, pgvector, ClickHouse's vector search, all covered elsewhere in this curriculum's RAG-focused tracks) handles persistence, replication, and filtering for you at the cost of an abstraction layer and a network hop; a hand-rolled Go microservice wrapping a native HNSW library trades that convenience for lower latency and tighter control when the serving path is latency-critical enough to matter.

**Where it's heading.** gRPC's ecosystem keeps maturing around observability and resilience specifically (interceptor-based tracing/metrics is now table-stakes, and xDS-based service-mesh integration for dynamic service discovery and load balancing is increasingly standard in Kubernetes-native shops rather than hand-configured static backend lists) — this is incremental hardening, not architectural change. For vector search, the more active direction is hybrid approaches combining HNSW-style graph search with newer structures aimed at better handling filtered search (finding nearest neighbors *within* a metadata-filtered subset, historically a weak point for pure HNSW, which was designed for unfiltered search) — real, active research and production engineering (see the DEG/Dynamic Edge Navigation Graph line of work), not yet a settled replacement for HNSW as the default. Go's own concurrency primitives are stable; the direction of travel here is less "new language features" and more "which library patterns (errgroup, singleflight, structured worker-pool packages) have become de facto standard enough that hand-rolling them is now a code-review flag rather than a neutral choice."

---

## Mental model

```
WORKER POOL: bounded concurrency, explicit backpressure, clean shutdown

  Producer ──▶ [bounded input chan, cap N] ──▶ Worker 1 ─┐
                    (BLOCKS producer when full             Worker 2 ─┤──▶ [results chan]
                     = the actual backpressure signal,      Worker 3 ─┘
                     not an unbounded queue that just        (fixed pool size,
                     grows until OOM)                          not 1-per-item)

  UNBOUNDED (the anti-pattern): go func() per incoming item, no cap —
  under a traffic spike, goroutine count and downstream connection count
  grow without limit, taking down the downstream AND this service's memory.

GRPC OVER HTTP/2: ONE TCP connection, MANY concurrent multiplexed streams

  Client ══════[single TCP/HTTP2 connection]══════▶ Server
         stream1 (RPC A) ───┐
         stream2 (RPC B) ───┼─── all multiplexed over the SAME connection,
         stream3 (RPC C) ───┘    no per-request connection overhead

  THE TRAP: an L4 (connection-level) load balancer sees ONE long-lived
  connection and routes it to ONE backend — ALL streams on it go to that
  SAME pod, regardless of how many concurrent RPCs are multiplexed inside.
  Fix: client-side RPC-level load balancing (round_robin service config
  resolving MULTIPLE addresses) or an L7-aware proxy (Envoy) that balances
  individual STREAMS, not connections.

HNSW: layered graph, greedy search narrows top-down

  Layer 2:    A -------- D                    (few nodes, long-range links)
  Layer 1:    A -- B --- D --- E               (more nodes, medium links)
  Layer 0:    A-B-C-D-E-F-G-H-I  (ALL nodes)   (every node, short-range links)

  Search: start at top layer's entry point, greedily walk toward the query
  vector, DROP DOWN a layer once no closer neighbor exists at the current
  layer, repeat until layer 0 — then return the ef-best candidates found.
  M = max neighbors per node (graph connectivity, build-time AND memory).
  efConstruction = search breadth DURING BUILD (higher = better graph, slower build).
  efSearch = search breadth AT QUERY TIME (higher = better recall, slower query,
  the ONE knob you tune live per-query for a recall/latency tradeoff).
```

---

## How it actually works

### Worker pools: the pattern that survives production load

```go
func processInBatches(ctx context.Context, items []Item, workers int, downstream DownstreamClient) error {
    g, ctx := errgroup.WithContext(ctx)         // shared cancellation: first error cancels ALL
    itemCh := make(chan Item)                    // UNBUFFERED — backpressure is immediate

    // producer
    g.Go(func() error {
        defer close(itemCh)
        for _, item := range items {
            select {
            case itemCh <- item:
            case <-ctx.Done():
                return ctx.Err()
            }
        }
        return nil
    })

    // fixed-size worker pool — NOT one goroutine per item
    for i := 0; i < workers; i++ {
        g.Go(func() error {
            for item := range itemCh {           // exits cleanly when itemCh closes
                if err := downstream.Process(ctx, item); err != nil {
                    return err                     // errgroup cancels ctx for siblings
                }
            }
            return nil
        })
    }

    return g.Wait()   // returns the FIRST error, all goroutines guaranteed done
}
```

`errgroup.WithContext` is the standard library-adjacent (`golang.org/x/sync/errgroup`) answer to the hand-rolled `sync.WaitGroup` + error channel + shared cancellation context plumbing shown in `T11-go-core`'s build-from-scratch example — it's worth knowing both the manual version (so you can explain the mechanics if asked) and that `errgroup` is what production code actually reaches for, because reimplementing this coordination by hand in a real codebase is a code-review flag, not a sign of understanding.

**Sizing the pool**: the same Little's Law reasoning from `T21-resilience-catalogue`'s bulkhead sizing applies — `concurrency ≈ downstream throughput × downstream latency`, with headroom for burst, verified under load rather than picked by intuition. For CPU-bound work (not I/O-bound), the pool size should cap near `GOMAXPROCS` — more workers than logical CPUs for CPU-bound work just adds scheduling overhead with no throughput gain, a distinct sizing rule from the I/O-bound case where the downstream's actual capacity (not core count) is the limiting factor.

**Backpressure, specifically**: an unbuffered (or small, bounded) input channel is the mechanism — the producer's `itemCh <- item` blocks once no worker is ready to receive, which propagates pressure back to whatever is feeding the producer (an HTTP handler, a queue consumer) rather than letting work pile up in an ever-growing unbounded channel or slice. This is the concrete, checkable difference between "a worker pool" and "an unbounded fan-out that happens to use channels" — the bound is what makes it a pool.

### gRPC: streaming types, deadlines, and interceptors

```protobuf
service Pricing {
  rpc GetPrice(PriceRequest) returns (PriceResponse);                    // unary
  rpc StreamPrices(stream PriceRequest) returns (stream PriceResponse);  // bidi streaming
}
```

Four RPC shapes: **unary** (one request, one response — the REST-equivalent default), **server streaming** (one request, a stream of responses — a natural fit for "subscribe to price updates"), **client streaming** (a stream of requests, one response — batch upload), and **bidirectional streaming** (both sides stream independently over the same call — a natural fit for a live chat-style or agent-tool-call-style protocol). All four share the same underlying HTTP/2 stream-multiplexing mechanism; the difference is purely how many messages flow in each direction before the call completes.

```go
func (s *server) GetPrice(ctx context.Context, req *pb.PriceRequest) (*pb.PriceResponse, error) {
    deadline, ok := ctx.Deadline()
    if ok && time.Until(deadline) < 50*time.Millisecond {
        return nil, status.Error(codes.DeadlineExceeded, "insufficient budget remaining")
    }
    price, err := s.lookup(ctx, req.Sku)
    if err != nil {
        return nil, status.Errorf(codes.Internal, "lookup failed: %v", err)
    }
    return &pb.PriceResponse{Price: price}, nil
}
```

**Deadline propagation is automatic and free**, and it's one of gRPC's most concretely useful properties versus plain REST: a client's `context.WithTimeout(ctx, 2*time.Second)` is serialized into the call's HTTP/2 metadata (`grpc-timeout` header) and reconstructed as a real, enforceable deadline on the server's `ctx` — the server doesn't need to trust an application-level "X-Timeout" header convention someone might forget to check; it's a first-class part of the protocol, and libraries in every language honor it identically. This is directly the deadline-budget-shrinks-with-depth pattern from `T21-resilience-catalogue`, made structurally easy rather than something every team reinvents.

**Interceptors** are gRPC's middleware mechanism — unary and streaming variants, client-side and server-side — for cross-cutting concerns that shouldn't live in every handler: logging, metrics, auth token validation, retry policy, and distributed tracing span propagation.

```go
func loggingInterceptor(ctx context.Context, req interface{}, info *grpc.UnaryServerInfo, handler grpc.UnaryHandler) (interface{}, error) {
    start := time.Now()
    resp, err := handler(ctx, req)
    log.Printf("method=%s duration=%s err=%v", info.FullMethod, time.Since(start), err)
    return resp, err
}
// registered once at server construction: grpc.NewServer(grpc.UnaryInterceptor(loggingInterceptor))
```

### The HTTP/2 connection-vs-stream load balancing trap

Because gRPC multiplexes many concurrent RPCs over a **single, long-lived TCP connection**, a load balancer operating at L4 (TCP connection level — a plain network load balancer, or a naive DNS-round-robin setup) makes its balancing decision **once, when the connection is established**, and every subsequent RPC on that connection goes to the same backend regardless of how many concurrent streams are multiplexed inside it. In a Kubernetes deployment with multiple backend pods behind a `ClusterIP` Service using plain L4 iptables/IPVS load balancing, this can mean **one client pod's entire gRPC traffic pins to a single backend pod** for the connection's lifetime, defeating horizontal scaling in a way that's invisible until someone actually checks per-pod traffic distribution and finds it wildly uneven. The two real fixes: **client-side load balancing** (gRPC's built-in `round_robin` load-balancing policy, configured via `grpc.WithDefaultServiceConfig`, which resolves multiple backend addresses — typically via DNS or a service-discovery mechanism — and round-robins *new RPCs*, or with connection-level balancing across several connections rather than one), or an **L7-aware proxy** (Envoy, Linkerd) in front that understands HTTP/2 streams and can balance individual streams across backends rather than treating the whole connection as one unit. This is a specific, checkable, real production gotcha — "just put it behind a load balancer" is not sufficient for gRPC the way it is for HTTP/1.1 REST.

### Building a fast vector-search microservice: HNSW mechanics

The three parameters that determine the recall/latency/memory tradeoff, concretely:

- **`M`** — the maximum number of neighbor connections each node maintains per layer (graph connectivity). Commonly cited range is **M=12-48**; low-dimensional data can work well with lower M (around 6 for very low dimensions), while high-dimensional embeddings (word/sentence embeddings, the kind used in RAG pipelines) typically need higher M (48-64) to maintain good recall — M directly drives both index memory footprint (more neighbors per node = more stored edges) and build time.
- **`efConstruction`** — the candidate-list breadth used *while building* the graph: a higher value means the build process considers more candidate neighbors before committing to the best `M` per node, producing a higher-quality graph (better recall at query time for the same `efSearch`) at the direct cost of significantly longer index-build time, since every insertion does more distance computations.
- **`efSearch`** (sometimes called just `ef` at query time) — the candidate-list breadth used *during a query*, dynamically adjustable per-request, unlike the other two which are baked in at index-build time. This is **the one knob you actually expose as a live, per-query tuning parameter in production** — trading recall for latency on a per-request basis (a background batch job might want high `efSearch` for maximum recall; a p99-latency-sensitive live user-facing query might deliberately accept lower recall for a tighter latency bound).

```go
// untested sketch — a Go vector-search microservice wrapping a native HNSW library
type SearchServer struct {
    pb.UnimplementedVectorSearchServer
    index *hnsw.Index   // e.g. a cgo binding to usearch, or a pure-Go HNSW implementation
}

func (s *SearchServer) Search(ctx context.Context, req *pb.SearchRequest) (*pb.SearchResponse, error) {
    efSearch := int(req.GetEfSearch())
    if efSearch == 0 {
        efSearch = 64   // sane default if the caller doesn't specify
    }
    results, err := s.index.SearchWithEf(req.GetVector(), int(req.GetK()), efSearch)
    if err != nil {
        return nil, status.Errorf(codes.Internal, "search failed: %v", err)
    }
    return &pb.SearchResponse{Matches: toProto(results)}, nil
}
```

**Why build this in Go rather than reach for a managed vector database**: latency and control. A managed vector DB (Weaviate, pgvector, ClickHouse) is a network hop away and carries its own query-planning/abstraction overhead — usually the right default, and covered in depth elsewhere in this curriculum's RAG-focused tracks. A hand-rolled Go service embedding the HNSW index directly in-process is the right call specifically when the serving path is latency-critical enough that the network hop and abstraction cost matter (a sub-10ms p99 requirement on top of an already-tight end-to-end budget), or when you need direct control over memory layout and `efSearch` tuning per traffic class that a general-purpose vector DB's API doesn't expose. **This is a genuine build-vs-buy tradeoff, not a default recommendation** — most teams should reach for the managed option first and only build this when profiling proves the network hop is the actual bottleneck.

---

## Build it from scratch

A minimal end-to-end slice: a bounded worker pool feeding a gRPC unary call with a propagated deadline, demonstrating the pieces composed together:

```go
// untested sketch — client side: deadline set once, propagated automatically
func fetchPrices(ctx context.Context, skus []string, client pb.PricingClient) ([]*pb.PriceResponse, error) {
    ctx, cancel := context.WithTimeout(ctx, 2*time.Second)
    defer cancel()

    g, ctx := errgroup.WithContext(ctx)
    results := make([]*pb.PriceResponse, len(skus))

    sem := make(chan struct{}, 10)   // bound concurrent outbound RPCs
    for i, sku := range skus {
        i, sku := i, sku
        g.Go(func() error {
            sem <- struct{}{}
            defer func() { <-sem }()
            resp, err := client.GetPrice(ctx, &pb.PriceRequest{Sku: sku})   // deadline auto-propagated
            if err != nil {
                return err
            }
            results[i] = resp
            return nil
        })
    }
    if err := g.Wait(); err != nil {
        return nil, err
    }
    return results, nil
}
```

A fuller lab building the vector-search server end to end — HNSW index construction with configurable `M`/`efConstruction`, a gRPC unary `Search` endpoint exposing `efSearch` as a request parameter, and a benchmark script measuring recall@k versus p99 latency across a sweep of `efSearch` values — belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Traffic wildly uneven across backend pods despite a Kubernetes Service and multiple replicas | L4 (connection-level) load balancing pinning each client's single HTTP/2 connection, and all its multiplexed RPCs, to one backend pod for the connection's lifetime | Client-side `round_robin` gRPC load-balancing policy resolving multiple addresses, or an L7-aware proxy (Envoy) balancing individual streams |
| Service falls over under a traffic spike; goroutine count and downstream connection count both spike unboundedly | An "unbounded worker pool" — a goroutine spawned per incoming item with no cap, rather than a fixed-size pool reading from a bounded channel | Fixed-size worker pool with a bounded input channel providing real backpressure; size via Little's Law against the downstream's actual capacity |
| A downstream service reports receiving requests well past the client's stated timeout | Deadline not actually propagated — a hand-rolled internal call didn't thread `ctx` through, or REST-over-JSON's timeout convention wasn't honored by every hop | Use gRPC where internal, since deadline propagation is automatic via `grpc-timeout` metadata; for REST, explicitly propagate and enforce a deadline header at every hop |
| Vector search recall drops noticeably after a re-index, though the same code and data | `efConstruction` reduced (intentionally or accidentally) to speed up index builds, producing a lower-quality graph that hurts recall at any given `efSearch` | `efConstruction` is a build-time-only quality knob — raising `efSearch` at query time cannot fully compensate for a poorly-built graph; re-check both parameters together |
| A worker pool with `workers = 500` shows no throughput improvement over `workers = 50` for a CPU-bound task | Pool sized well past `GOMAXPROCS` for CPU-bound work, adding scheduling overhead with no additional compute capacity | Cap CPU-bound worker pools near `GOMAXPROCS`; only I/O-bound pools benefit from sizing past core count |
| gRPC client blocked/hanging with no error for an unexpectedly long time | Missing or nonexistent context deadline on the client call (a plain `context.Background()` passed straight through with no `WithTimeout`) | Always wrap outbound gRPC calls in an explicit, budget-derived deadline — never issue a call on an undeadlined context in production code |

---

## Tradeoffs & when NOT to use it

- **Don't assume a Kubernetes Service's default load balancing is sufficient for gRPC.** Verify whether it's L4 (connection-pinning risk) or genuinely stream-aware, and configure client-side load balancing or an L7 proxy explicitly rather than discovering uneven pod traffic in production.
- **Don't spawn an unbounded goroutine per item as a "worker pool."** That's fan-out with no backpressure, not a pool — the bound (fixed worker count, bounded input channel) is the entire point, and its absence is exactly what turns a traffic spike into an outage.
- **Don't use gRPC for public/browser-facing APIs without accounting for the extra proxy layer (grpc-web) browsers need.** REST/JSON (or GraphQL) remains the more defensible default for external, partner-facing APIs where tooling ubiquity and human debuggability matter more than binary efficiency — see `T11-api-design`.
- **Don't build a custom vector-search microservice before confirming a managed vector database's latency/recall doesn't already meet your budget.** The build-vs-buy tradeoff favors buying by default; build only after profiling proves the network hop or abstraction overhead is the actual bottleneck.
- **Don't tune `efSearch` globally to a single value across all traffic.** It's specifically valuable as a per-request or per-traffic-class knob — a background batch job and a p99-sensitive live query have genuinely different recall/latency needs, and a single global value wastes that flexibility.
- **Don't skip explicit deadlines on outbound gRPC calls.** An undeadlined `context.Background()` call can hang indefinitely with no visible symptom until it cascades into a resource exhaustion incident elsewhere.

---

## Interview questions

### Q1 — What's the actual difference between "a worker pool" and "spawning a goroutine per item," and why does it matter under load?
**Testing:** whether bounded concurrency is understood as the defining property, not incidental detail.
**Answer:** A worker pool has a fixed, bounded number of goroutines reading from a bounded (often unbuffered) input channel — the channel provides real backpressure, blocking the producer once workers are saturated, which propagates pressure back up the call chain rather than letting work accumulate unboundedly. Spawning a goroutine per incoming item has no such bound: under a traffic spike, both goroutine count and any downstream connections/resources those goroutines hold grow without limit, which can take down the downstream dependency and exhaust this service's own memory simultaneously.
**Follow-up trap:** *"How would you size the worker count for a downstream call with a known throughput and latency?"* — Little's Law: `concurrency ≈ throughput × latency`, with burst headroom, verified under real load rather than picked by intuition — the same reasoning as bulkhead sizing in `T21-resilience-catalogue`.

### Q2 — Why does gRPC propagate deadlines automatically, and what's the mechanism?
**Testing:** whether this is understood as a protocol-level guarantee, not an application convention.
**Answer:** A client's `context.WithTimeout`/`WithDeadline` is serialized into the RPC's HTTP/2 metadata as a `grpc-timeout` header when the call is made; the server-side gRPC library deserializes it back into a real `context.Context` deadline on receipt. Every language's gRPC implementation honors this identically, so deadline propagation across a polyglot service chain works without any team having to invent or remember an application-level timeout-header convention.
**Follow-up trap:** *"Does the server automatically cancel the work when the deadline is exceeded?"* — the *context* is marked done, and idiomatic Go code checks `ctx.Err()`/selects on `ctx.Done()` to stop working, but this is cooperative, not automatic termination of arbitrary in-flight work — the same server-continues-after-client-gives-up caveat as `T21-resilience-catalogue` Q13 applies unless the handler code actually respects the context.

### Q3 — Explain the gRPC-over-HTTP/2 load-balancing trap: why can a service with multiple healthy backend pods still see wildly uneven traffic?
**Testing:** the single most-tested gRPC-specific production gotcha.
**Answer:** gRPC multiplexes many concurrent RPCs over one long-lived HTTP/2 TCP connection. A load balancer operating at L4 (connection level) makes its routing decision once, when that connection is established, and every subsequent RPC on it goes to the same backend — so a client that opens one connection and never reconnects sends its entire traffic to one pod regardless of how many concurrent streams it multiplexes inside that connection.
**Follow-up trap:** *"What are the two real fixes, and when would you pick each?"* — client-side RPC-level load balancing (gRPC's `round_robin` policy resolving multiple backend addresses, good when you control the client and can configure its service config directly) or an L7-aware proxy like Envoy in front that understands and balances individual HTTP/2 streams (good when clients are numerous/uncontrolled, or when you want balancing logic centralized rather than duplicated across every client).

### Q4 — What are the three main HNSW parameters, and which one would you expose as a live, per-query tuning knob in production?
**Testing:** whether resume-level RAG/vector-search knowledge extends to the actual index internals.
**Answer:** `M` (max neighbor connections per node, graph connectivity, fixed at build time, drives memory and build cost — commonly 12-48, higher for high-dimensional embeddings), `efConstruction` (build-time search breadth, higher means a better-quality graph at the cost of much longer index builds, also fixed once built), and `efSearch` (query-time search breadth, the only one of the three that's dynamically adjustable per request). `efSearch` is the one to expose live, because it trades recall for latency on a per-query or per-traffic-class basis without requiring a rebuild.
**Follow-up trap:** *"If recall drops after a re-index, is raising efSearch at query time always enough to fix it?"* — no; if the drop is because `efConstruction` was reduced (a lower-quality graph was built), no amount of query-time `efSearch` tuning fully compensates for a structurally worse graph — the fix requires re-checking the build-time parameters, not just the query-time one.

### Q5 — When would you build a custom Go vector-search microservice instead of using a managed vector database?
**Testing:** staff-level build-vs-buy judgment specific to this component.
**Answer:** When profiling shows the managed database's network hop and query-abstraction overhead is the actual bottleneck against a genuinely tight latency budget (a sub-10ms p99 requirement nested inside an already-constrained end-to-end SLA), or when you need direct control over memory layout, sharding strategy, or per-traffic-class `efSearch` tuning that the managed option's API doesn't expose. Most teams should default to the managed option and only build this after proving the specific bottleneck with real measurements, not as a default architectural choice.
**Follow-up trap:** *"What do you give up by building it yourself?"* — persistence/durability, replication, filtered-search support (HNSW's native weak point — filtering within a metadata subset), and operational tooling (backups, monitoring, scaling) that a managed vector database provides out of the box — all of which the custom service now has to build and operate itself, a real ongoing cost beyond the initial build.

### Q6 — What's the difference between REST/JSON and gRPC/Protobuf at the wire level, and why does that matter for internal service-to-service calls specifically?
**Testing:** the mechanical "why" behind "gRPC is faster," not just the claim.
**Answer:** REST/JSON is text-based (larger payloads, slower parsing) typically over HTTP/1.1 (a connection, or a pool-checked-out connection, per logical request in the common case, with head-of-line blocking within a connection). gRPC/Protobuf is binary (smaller payloads, faster serialize/deserialize) over HTTP/2 (multiplexed streams over one connection, header compression via HPACK, built-in flow control). For internal, high-volume, polyglot service-to-service traffic, this compounds — many calls per second between the same service pair benefit disproportionately from connection reuse and binary framing versus a public API's comparatively low, bursty call volume from many different clients.
**Follow-up trap:** *"So why isn't gRPC the default for public APIs too, if it's faster?"* — browsers can't natively speak gRPC's HTTP/2-trailers-based framing without a proxy translation layer (grpc-web), and REST/JSON's universal tooling, human-readability, and caching-friendliness (standard HTTP caching semantics) matter more for external, partner-facing, or debugging-heavy contexts than raw wire efficiency does — see `T11-api-design` for the fuller decision framework.

### Q7 — Walk through what `errgroup.WithContext` gives you over a hand-rolled `sync.WaitGroup` plus a manual error channel.
**Testing:** whether the idiomatic library choice is understood as solving a specific coordination problem, not just "less code."
**Answer:** `errgroup.WithContext` returns a derived context that's automatically canceled the moment any goroutine in the group returns a non-nil error, so every sibling goroutine gets a `ctx.Done()` signal to exit cleanly without needing hand-wired plumbing to notice a peer's failure; `Wait()` returns exactly the first error and blocks until every goroutine has actually finished, guaranteeing no dangling work when the caller proceeds. A hand-rolled version needs to replicate all of this manually — a `WaitGroup` for completion tracking, a separate error channel (sized carefully to avoid blocking on a second error while the first is unread), and its own cancellation context wiring — which is exactly the pattern shown in `T11-go-core`'s worker-pool example, useful to understand mechanically but not what production code should actually hand-roll every time.
**Follow-up trap:** *"Is there a case where you'd still want the manual version over errgroup?"* — when you need behavior errgroup doesn't provide out of the box, like collecting *all* errors rather than just the first, or continuing to run remaining goroutines despite one failure instead of canceling siblings — errgroup's fail-fast, first-error-wins model is a deliberate simplification that doesn't fit every coordination need.

### Q8 — Design the resilience/backpressure strategy for a Go service that fans out to a downstream that occasionally can't keep up.
**Testing:** synthesizing this module with the general resilience catalogue and Resilience4j-adjacent concepts, applied idiomatically in Go.
**Answer:** A bounded worker pool sized via Little's Law against the downstream's real observed throughput and latency (not intuition), an explicit per-call `context` deadline derived from the caller's actual budget (propagated automatically if the downstream is gRPC), a semaphore or bounded channel providing backpressure so a burst blocks the producer rather than spawning unbounded goroutines, and — for the downstream's own protection — a circuit-breaker-equivalent (Go doesn't have Resilience4j's ecosystem natively, but `sony/gobreaker` is the idiomatic equivalent, referenced in `T21-resilience-catalogue`) wrapping the actual call so a genuinely degraded downstream gets failed fast rather than retried into the ground.
**Follow-up trap:** *"What's specifically different about doing this in Go versus the Java/Resilience4j version covered elsewhere in this track?"* — Go has no equivalent of Resilience4j's declarative annotation-based composition; every piece (timeout via context, backpressure via channel/semaphore, circuit breaking via a library like gobreaker) is explicit, hand-composed code rather than a stacked set of annotations — which is more verbose but also makes the actual execution order unambiguous by construction, sidestepping Resilience4j's fixed-and-easily-misunderstood AOP ordering entirely.

### Q9 — Your gRPC server's p99 latency is fine in isolation, but a client reports frequent `DeadlineExceeded` errors. What do you check first?
**Testing:** systematic diagnosis of a deadline-related production complaint rather than guessing at server-side tuning.
**Answer:** First, whether the client's own deadline is even reasonable for the call — a client setting a 200ms timeout for a call whose server-side p99 is 300ms will see `DeadlineExceeded` constantly, correctly, with nothing wrong on the server. Second, whether the deadline budget is being correctly *reduced* at each hop in a multi-service call chain (per `T21-resilience-catalogue`'s budget-shrinks-with-depth rule) — a deadline set for the outermost call without leaving room for inner calls' own processing time manufactures exactly this symptom. Third, only after ruling out both of those, look at actual server-side tail latency (a slow dependency, GC pauses, or the load-balancing pinning issue from Q3 concentrating traffic on one overloaded pod) as the genuine server-side cause.
**Follow-up trap:** *"The client's deadline is generous and budget-aware, and it's still happening intermittently, not constantly."* — that pattern points toward the L4 load-balancing trap (Q3) concentrating traffic unevenly, or a GC-related pause spike (see `T11-jvm-tuning`'s analogous JVM discussion, or Go's own GC pause behavior under memory pressure) on specific backend instances rather than a systemic timeout misconfiguration — intermittent-not-constant is the signal that narrows the search from "always wrong" to "occasionally overloaded."

### Q10 — Why is `efSearch` described as a recall/latency tradeoff specifically, and how would you choose a value for a live user-facing search versus a background batch re-ranking job?
**Testing:** applying the HNSW parameter distinction to a concrete operational decision.
**Answer:** Higher `efSearch` widens the candidate list considered during graph traversal at query time, increasing the chance the true nearest neighbors are found (higher recall) at the direct cost of more distance computations per query (higher latency). A live, user-facing search endpoint with a tight p99 budget should default to a lower `efSearch` tuned to hit its latency SLA with acceptable-but-not-maximal recall; a background batch job re-ranking candidates with no hard latency constraint can afford a much higher `efSearch` to maximize recall, since total throughput/wall-clock time matters more than any single query's latency.
**Follow-up trap:** *"Could you expose efSearch as a client-controllable request parameter instead of hardcoding two profiles?"* — yes, and it's often the better design — exposing it as an optional request field (defaulting to a safe value if unset, as in the code example above) lets different callers make their own recall/latency tradeoff without the service needing to hardcode and maintain separate profiles per known caller type.

---

## Red flags that fail you

- Calling a goroutine-per-item fan-out with no bound "a worker pool."
- Not knowing why a gRPC service with multiple pods can still see uneven traffic distribution.
- Assuming REST timeouts and gRPC deadlines work the same way (REST needs an explicit, hand-maintained convention; gRPC propagates automatically as protocol-level metadata).
- Not knowing the difference between `M`, `efConstruction`, and `efSearch`, or which one is the live per-query tuning knob.
- Reflexively recommending a hand-built vector-search microservice over a managed vector database without a measured bottleneck justifying it.
- Sizing a CPU-bound worker pool far past `GOMAXPROCS` expecting proportional throughput gains.
- Issuing an outbound gRPC call with an undeadlined `context.Background()`.
- Claiming gRPC is a strictly better default than REST for every use case, including public/browser-facing APIs.

---

## Cheat card

```
WORKER POOL: FIXED size, reading from a BOUNDED channel = real backpressure
  (blocks producer, doesn't grow unboundedly). Size via Little's Law:
  concurrency ~ throughput x latency (I/O-bound) or cap near GOMAXPROCS
  (CPU-bound — more workers than cores adds scheduling overhead, no gain).
  errgroup.WithContext = idiomatic prod tool (shared cancellation on first
  error, Wait() blocks til ALL goroutines done) over hand-rolled WaitGroup+chan.

GRPC: binary Protobuf + HTTP/2 (multiplexed streams, ONE TCP connection,
  header compression). 4 RPC shapes: unary, server-streaming, client-
  streaming, bidi-streaming. DEADLINE PROPAGATION IS AUTOMATIC — client's
  context.WithTimeout serializes to grpc-timeout HTTP/2 metadata, server
  reconstructs it as a real ctx deadline. No app-level convention needed.

GRPC LOAD-BALANCING TRAP: one TCP connection = ALL multiplexed RPCs pinned
  to ONE backend if the LB is L4 (connection-level, decides once at
  connect time). Fix: client-side round_robin service config (multiple
  resolved addresses) OR an L7-aware proxy (Envoy) balancing STREAMS not
  connections. "Just put it behind a load balancer" is NOT sufficient.

INTERCEPTORS: gRPC's middleware — unary/streaming x client/server. Used
  for logging, metrics, auth, retry, tracing — registered once, not per handler.

HNSW (vector search): layered graph, greedy top-down search, drop a layer
  when no closer neighbor exists there.
  M = max neighbors/node, 12-48 typical (48-64 for high-dim embeddings),
      FIXED at build, drives memory + build cost.
  efConstruction = build-time search breadth, higher = better graph,
      MUCH slower build, FIXED once built.
  efSearch = QUERY-TIME search breadth, the ONLY one tunable live/per-
      request — trades recall for latency, expose this as an API param.
  Recall drop after reindex + efSearch raised, still bad? Check
  efConstruction — a poor build-time graph can't be fully compensated
  for by a query-time knob.

BUILD vs BUY (vector search): default to a managed vector DB (Weaviate,
  pgvector, ClickHouse). Build a custom Go service ONLY after profiling
  proves the network hop / abstraction overhead is the actual bottleneck
  against a genuinely tight latency budget, or you need per-traffic-class
  efSearch control the managed API doesn't expose.

GRPC vs REST: internal polyglot service-to-service = gRPC default
  (binary, multiplexed, auto deadlines). Public/browser-facing = REST/JSON
  (or GraphQL) still usually right — browsers need grpc-web proxy layer,
  REST wins on tooling/caching/human-debuggability. See T11-api-design.
```

## Sources

- [gRPC vs REST: A Practical Performance Comparison and Tuning Guide — ASOasis](https://asoasis.tech/articles/2026-04-17-0253-grpc-vs-rest-performance-comparison/) — accessed 2026-08-03
- [gRPC in Go: Streaming RPCs, Interceptors, and Metadata — VictoriaMetrics](https://victoriametrics.com/blog/go-grpc-basic-streaming-interceptor/) — accessed 2026-08-03
- [A practical guide to selecting HNSW hyperparameters — OpenSearch](https://opensearch.org/blog/a-practical-guide-to-selecting-hnsw-hyperparameters/) — accessed 2026-08-03
- [ALGO_PARAMS.md — hnswlib/nmslib](https://github.com/nmslib/hnswlib/blob/master/ALGO_PARAMS.md) — accessed 2026-08-03
- [DEG: Efficient Hybrid Vector Search Using the Dynamic Edge Navigation Graph (arXiv 2502.07343)](https://arxiv.org/pdf/2502.07343) — accessed 2026-08-03
- [USearch BENCHMARKS.md — unum-cloud](https://github.com/unum-cloud/usearch/blob/main/BENCHMARKS.md) — accessed 2026-08-03
- [Anthropic Semantic Search Architecture: Production Best Practices — Markaicode](https://markaicode.com/architecture/anthropic-semantic-search-architecture/) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
