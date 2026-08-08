# REST vs gRPC vs GraphQL vs WebSocket vs SSE vs Webhooks — the Decision Matrix

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-http-semantics, T29-grpc, T29-tcp-vs-udp-vs-ip · **Updated:** 2026-07-26
> **Module id:** `T29-protocol-selection` · **Tags:** tradeoffs, critical

## The 30-second version

There is no best protocol, only a best fit for a specific boundary. REST wins when you need cacheable, human-debuggable, loosely-coupled contracts across organizational boundaries. gRPC wins on internal service-to-service hops where both ends are yours, latency and strict typing matter, and you can afford HTTP/2-only infrastructure. GraphQL wins when one client (or a family of them) needs many different shapes of the same underlying data and you're willing to trade away HTTP caching for a single flexible endpoint — and to own N+1 and query-cost problems that REST never had. WebSocket is for genuine bidirectional, low-latency, high-frequency exchange; SSE is for server-to-client push over plain HTTP when the client never needs to talk back mid-stream. Webhooks invert control to the provider and buy you efficiency at the cost of building retry, ordering, and idempotency yourself. And a message queue is frequently the right answer when nobody asked "which protocol" was even the right question — decoupling producer and consumer lifetimes beats any request/response choice.

## Why this gets asked

Because picking REST by default, or GraphQL because it's trendy, or WebSocket because "real-time" sounds good, is how systems end up with an API layer nobody can operate. The interviewer has watched a team put GraphQL in front of a public API and lose CDN caching for a mostly-static catalog, or add WebSockets for a feature that only ever needed one-way server push and now owns a stateful connection-affinity problem it didn't need. They want to hear the deciding questions, not the marketing pitch for any one technology.

---

## Lineage: past → present → future

**What came before.** SOAP/XML-RPC (late 1990s) tried to make remote calls look like local method calls, with a heavyweight envelope, WSDL contracts, and WS-* extensions for security and transactions. It worked, but the tooling was heavy and the wire format was verbose — a typical SOAP envelope for a trivial call ran several KB of XML boilerplate around a payload of tens of bytes. REST (Fielding's 2000 dissertation, popularized through the mid-2000s) killed it by dropping the ceremony: use HTTP's own verbs and status codes, model state as resources, and let HTTP's existing cache/proxy infrastructure do the work SOAP reinvented badly. The pain SOAP died from was tooling complexity and the impossibility of caching an RPC call that always looks like a POST.

**Where it stands now.** REST is the default for anything public or cross-team, but "REST" in practice means "JSON over HTTP with roughly resource-shaped URLs," rarely full HATEOAS. gRPC (2015, Google, built on HTTP/2 and Protobuf) owns internal service mesh traffic at companies operating at scale — it is the actual default for service-to-service calls at Google, and widely adopted elsewhere for the same reason: binary framing, native streaming, generated strongly-typed clients. GraphQL (2015, Facebook) solved a real and specific pain — mobile clients making 6 round trips to assemble one screen, or over-fetching full objects to use two fields — but the live disagreement is whether its backend complexity (resolver N+1, cost-based rate limiting, cache invalidation) is worth it versus a well-designed REST BFF (backend-for-frontend) that does the same aggregation server-side with ordinary HTTP semantics intact. Both are deployed at scale; neither has won. WebSocket (RFC 6455, 2011) and SSE (part of HTML5, also ~2011) both solved "server needs to push," and the field has mostly converged on "use SSE unless you provably need bidirectional," because SSE reuses ordinary HTTP infrastructure and WebSocket does not.

**Where it's heading.** gRPC-Web and Connect (buf.build's protocol, 2022) are closing the gap that let browsers not speak native gRPC, which removes gRPC's biggest historical limitation — high confidence this continues. GraphQL federation (Apollo Federation, 2019 onward) is the consensus answer for "GraphQL at multi-team scale," splitting one graph across many services; moderate confidence this stays dominant since it's the only mature answer to that problem. HTTP/3 (QUIC) removing head-of-line blocking may reduce the latency argument for gRPC's HTTP/2 framing over time, but this is speculative — QUIC support in gRPC implementations is not yet uniform as of 2026. Expect the request/response-vs-queue line to keep blurring as tools like Kafka add HTTP-native produce APIs and gateways add durable delivery in front of plain REST endpoints.

---

## Mental model

```
                          PUBLIC / THIRD PARTY? ──yes──▶ REST (or GraphQL if
                               │                          you truly need
                               no                         client-shaped queries)
                               │
                  BOTH ENDS UNDER YOUR CONTROL?
                               │
                       yes ────┴──── no
                        │              │
              LATENCY / TYPING      REST / webhooks
              CRITICAL, INTERNAL     (public contract)
                        │
                  yes ──┴── no
                   │          │
                 gRPC     REST is fine

   NEEDS SERVER → CLIENT PUSH?
        │
   bidirectional required? ──yes──▶ WebSocket
        │
        no ──▶ SSE  (reconnect built in, plain HTTP, one-way)

   PROVIDER PUSHES EVENTS TO YOU, ASYNC, NO OPEN CONNECTION?
        → webhook (you own retry/verify/idempotency)
        or poll/long-poll if you can't expose a public endpoint

   PRODUCER AND CONSUMER HAVE DIFFERENT LIFETIMES,
   OR YOU NEED TO SURVIVE A DOWNSTREAM OUTAGE?
        → message queue (Kafka/SQS/RabbitMQ), not a protocol choice at all
```

---

## How it actually works

### REST — the default, and what it actually buys you

REST's real value is not the verbs, it's that it rides on top of infrastructure built for HTTP: reverse proxies, CDNs, browser caches, load balancers that route on path, and every HTTP client library ever written understands it without a generated stub. A `GET /orders/42` with `Cache-Control: max-age=60, ETag: "abc"` can be served entirely from a CDN edge on a cache hit, at effectively zero origin cost. That caching story disappears the moment you funnel everything through `POST /graphql` or a single gRPC method, because intermediaries can't distinguish one query from another without parsing the body.

Cost: verbose JSON compared to Protobuf (a typical JSON payload runs 2-5x the wire size of the equivalent Protobuf message), no native streaming without extensions (chunked transfer or SSE bolted on), and a client that wants three related resources pays three round trips unless you build a BFF or embed expansion (`?include=customer,items`).

### gRPC — internal, typed, streaming

Protobuf-encoded binary payloads over HTTP/2 frames give you multiplexed streams on one TCP connection (no head-of-line blocking at the HTTP layer, though TCP-level HOL blocking still applies — this is the actual argument for HTTP/3-based transports). Four RPC shapes: unary, server-streaming, client-streaming, bidi-streaming — none of which REST expresses natively. Deadlines propagate as actual wire metadata, not a convention your team has to remember. Contract-first `.proto` files generate clients in every supported language, eliminating an entire class of "the docs say `int` but the field is actually a string" bugs.

Cost: no browser support without a proxy layer (gRPC-Web, Envoy), painful to debug with `curl` (binary frames, not text), and every consumer needs the generated stub or a reflection-based tool (`grpcurl`). Operational maturity requirement is real — teams without HTTP/2-aware load balancers and Protobuf tooling underestimate the ramp.

### GraphQL — honest tradeoffs

What it actually solves: over-fetching (REST returns the whole `User` object when you wanted `name` and `avatarUrl`), under-fetching (REST needs `/users/1`, then `/users/1/posts`, then `/posts/5/comments` — three round trips for one screen), and the N-round-trip mobile problem generally. One POST to `/graphql` with a query shaped exactly like the screen that needs it.

What it costs, precisely:

- **Cacheability.** A GET with a URL is cacheable by any HTTP-aware intermediary. A POST with a query in the body is not, by default. Workarounds exist (persisted queries turn it back into a GET with a query ID, response-level caching with tools like Apollo's cache) but they are additional engineering, not free.
- **N+1 on the backend.** A query for 20 users each resolving their own `posts` field naively issues 1 + 20 database queries. This is not a corner case, it's the default behavior of naive resolvers. The fix is DataLoader-style batching: collect all `posts` lookups requested in one tick of the event loop, issue one `WHERE user_id IN (...)` query, and distribute results back. Skipping this is the single most common GraphQL production incident.
- **Query complexity / DoS.** GraphQL imposes no depth or cost limit by default. A client can send a deeply nested query (`user { friends { friends { friends { ... } } } }`) that is syntactically valid and computationally explosive. Mitigation: depth limiting (reject past N levels, typically 5-10) and cost analysis (assign a numeric cost per field — scalar fields cost ~1, list/connection fields cost more, often scaled by the `first`/`limit` argument — and reject queries over a budget, e.g. 1000 points). Both must be implemented; neither ships by default in most GraphQL servers.
- **Error handling is muddier.** A partially-failed query returns HTTP 200 with an `errors` array alongside partial `data` — this breaks the usual "check the status code" reflex and needs explicit handling in every client.

### WebSocket vs SSE — precisely

WebSocket (`ws://`/`wss://`) upgrades an HTTP/1.1 connection via the `Upgrade: websocket` handshake into a full-duplex framed TCP channel. Either side sends at any time; there's no concept of request/response once upgraded. Needed for: multiplayer state sync, collaborative editing, trading platforms with client-originated cancel messages, chat where the client sends as often as it receives.

SSE (`text/event-stream`) is plain HTTP — a GET request that never closes the response body, streaming `data: ...\n\n` chunks. Server-to-client only; the client cannot send data on the same channel (it would issue a separate normal HTTP request for that). Two properties make SSE the better default when you only need push: automatic reconnection is *part of the spec* (`EventSource` retries and resumes using `Last-Event-ID`, no client code required), and because it's plain HTTP, it passes through ordinary reverse proxies, corporate proxies, and load balancers without special handling — WebSocket upgrades are routinely blocked or mishandled by exactly this kind of infrastructure and need explicit support (sticky sessions or shared state across LB nodes, proxy `Upgrade` header passthrough).

Concrete rule: if the client only *receives* updates (stock ticker, notification feed, progress bar, LLM token streaming), use SSE. If the client also needs to *send* on the same low-latency channel (game state, live cursors, cancel-a-running-operation), use WebSocket.

### Webhooks — inversion of control, and its costs

A webhook flips who initiates: instead of you polling the provider, the provider POSTs to a URL you registered when its event fires. This is efficient (no wasted polling requests) but hands you a list of reliability problems the provider used to own:

- **Retry and backoff are your job to *receive* correctly**, and the provider's job to *send* correctly — you must build an idempotent receiver because the provider will retry on any non-2xx response or timeout, and you cannot assume exactly-once delivery.
- **Ordering is not guaranteed.** Two events for the same entity can arrive out of order (network retries, provider-side queue rebalancing). Include a sequence number or timestamp in the payload and let the receiver decide whether an incoming event is stale.
- **Signature verification is mandatory**, not optional — an HMAC signature (e.g., `X-Hub-Signature-256`) over the raw body, checked before you trust the payload, because the endpoint is public by construction.
- **The receiver must be idempotent** against the same delivery arriving twice: store the event ID, ignore duplicates (`INSERT ... ON CONFLICT DO NOTHING` keyed on provider event ID, not read-then-write).

Polling is simpler but wastes requests and adds latency up to the poll interval; long-polling (hold the request open until data is available or a timeout, typically 20-30s, then reissue) trades some of that latency for holding a connection open, which is a real resource cost at high concurrency. Webhooks beat both when the provider can reach you and you can tolerate building the reliability layer; polling wins when you can't expose an inbound endpoint (behind NAT, air-gapped, no public IP) or need to be the one that decides the pace.

### Message queues — often the actual right answer

A queue (Kafka, SQS, RabbitMQ) isn't a request/response protocol at all, and that's the point: it decouples the producer's lifetime from the consumer's. The producer doesn't need the consumer to be up, doesn't wait for it to finish processing, and doesn't care how many consumers are behind. Three concrete cases where this beats any protocol above:

1. **Downstream is unreliable or slow.** A queue buffers against it; a synchronous call just times out and fails the caller.
2. **You need at-least-once delivery with replay.** Kafka retains messages for a configured window (commonly 7 days) and consumers can replay from any offset; no HTTP-based protocol gives you replay for free.
3. **Fan-out to many consumers with different processing speeds.** One event, many independent consumer groups, each at its own pace — versus N synchronous calls from the producer, each adding to its latency budget and failure surface.

The cost: eventual rather than immediate consistency, an operational system to run (or pay for, managed), and a genuinely different failure mode vocabulary (consumer lag, rebalancing, poison messages) that a REST/gRPC team has to learn.

---

## Build it from scratch

Not applicable as a single lab — this module is a decision framework, not an implementation. The mechanics of each option (HTTP semantics, gRPC framing, WebSocket handshake) are built from scratch in their own modules (`T29-http-semantics`, `T29-grpc`). What belongs here is the deciding-questions checklist an engineer runs before writing any code:

1. Public (third parties, unknown clients) or internal (both ends yours)?
2. Does the client need to *push* to the server mid-exchange, or only *receive*?
3. Is true bidirectional, low-latency streaming required, or is "the server calls me back later" enough?
4. Do you control both ends' tech stack and deployment cadence?
5. What are the caching needs — is this data cacheable by URL, and does that caching matter at your traffic level?
6. What's the team's operational maturity with this stack (HTTP/2-aware infra for gRPC, connection-affinity for WebSocket, DLQ/rebalancing for queues)?
7. Can the downstream tolerate eventual delivery, or does the caller need a synchronous answer to proceed?

---

## How it's done in production

| Pattern | Real deployment | What it adds over a naive choice |
|---|---|---|
| REST + CDN | Public APIs, Stripe, GitHub | ETags, `Cache-Control`, edge caching cut origin load to near zero on read-heavy endpoints |
| gRPC internal mesh | Google, Netflix, most large service meshes | Envoy/Istio handle gRPC-aware load balancing, retries, deadlines uniformly |
| GraphQL + Federation | Netflix, Airbnb (Apollo Federation) | One graph stitched from many services; each team owns a subgraph |
| SSE for LLM token streaming | OpenAI/Anthropic API streaming responses | Plain HTTP, works through existing proxies, `EventSource` auto-reconnect |
| Webhooks + queue behind them | Stripe, GitHub webhooks → customer's SQS | Provider signs and retries; smart receivers immediately enqueue and ack fast to avoid provider-side retry storms |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| GraphQL endpoint p99 spikes under a specific client query | Naive resolver issuing N+1 DB calls | DataLoader batching per request tick |
| Public API suddenly gets a 10x traffic spike, origin CPU pegged | No depth/cost limit; a client (or attacker) sent a pathological nested query | Depth limit (~10) + cost budget (~1000 points) with per-field costs |
| Webhook receiver double-processes an order | Provider retried after a slow 200, receiver wasn't idempotent | Dedup on provider event ID, atomic insert-or-ignore |
| Mobile app shows stale data after a mutation | GraphQL client cache not invalidated / REST cache TTL too long | Cache normalization (Apollo cache IDs) or explicit invalidation; shorter TTL + revalidation |
| WebSocket clients disconnect en masse during a deploy | No reconnect/backoff logic; LB doesn't preserve affinity across pod restarts | Client-side reconnect with jitter; sticky routing or externalize connection state (Redis pub/sub fan-out) |
| SSE stream silently stops updating in a corporate network | Proxy buffers or times out long-lived HTTP connections | Send periodic heartbeat comments (`: ping\n\n`), reduce proxy idle timeout, or fall back to polling |
| Queue consumer falls behind, backlog grows unbounded | Consumer slower than producer, no backpressure | Scale consumer group, apply backpressure, add a DLQ for poison messages |

---

## Tradeoffs & when NOT to use it

- **Don't use GraphQL for a small, stable, mostly-read public API.** You're trading away free HTTP caching for query flexibility nobody asked for. A REST endpoint with `?fields=` query param solves 80% of the over-fetching complaint without any of the N+1/DoS/cache-invalidation cost.
- **Don't use gRPC for a public API.** No browser-native support, painful debugging, and a barrier to third-party integration outweighs the perf gain unless you're serving another backend team, not external developers.
- **Don't use WebSocket when SSE would do.** Every WebSocket connection is stateful infrastructure you now have to load-balance with affinity, monitor for half-open connections, and scale horizontally with a pub/sub backplane. If the client never sends anything mid-stream, that entire cost is unnecessary.
- **Don't use webhooks if you can't build (or don't want to build) a reliable receiver.** A webhook without idempotency and signature verification is a liability, not a feature — polling with a sane interval is often genuinely simpler and safer for a small integration.
- **Don't reach for a message queue to avoid learning why your request/response call is slow.** A queue turns a latency problem into a consistency problem; if the caller genuinely needs the answer now, queueing just adds a poll loop on the other end.

---

## Interview questions

### Q1 — When would you choose gRPC over REST for a new internal service?
**Testing:** whether the answer is reflexive ("gRPC is faster") or reasoned.
**Answer:** When both ends are yours, latency and payload size matter (Protobuf is commonly 2-5x smaller on the wire than the equivalent JSON), you want generated, strongly-typed clients across languages, and you need native streaming (server-streaming logs, bidi-streaming for a live feed). Skip it for anything a browser or third party calls directly.
**Follow-up trap:** *"What does gRPC cost you operationally?"* — HTTP/2-aware load balancers and proxies (older L4-only LBs mishandle multiplexed streams), harder `curl`-style debugging (need `grpcurl` or a Protobuf-aware sniffer), and a build step for every consumer to regenerate stubs when the `.proto` changes.

### Q2 — GraphQL over-fetching/under-fetching — explain both, with a concrete example.
**Answer:** Over-fetching: `GET /users/1` returns the full user object (50 fields) when the mobile screen needed only `name` and `avatarUrl` — wasted bandwidth, worse on mobile networks. Under-fetching: rendering a profile page needs the user, their recent posts, and comment counts — three separate REST calls, three round trips. GraphQL's single query with nested field selection solves both by letting the client specify the exact shape.
**Follow-up trap:** *"What did you give up to get that?"* — cacheability by URL (a POST body isn't cache-key-able by a CDN without persisted queries), and you've moved the over-fetch problem to the backend as N+1 resolver calls if you don't batch.

### Q3 — Explain the GraphQL N+1 problem and how DataLoader fixes it.
**Answer:** A query resolving 20 users' `posts` field naively fires one query per user (20 + 1 for the initial list). DataLoader collects all `posts` requests issued within one tick of the event loop into a single batched `WHERE user_id IN (...)` query, then distributes rows back to each caller, and caches per-request so the same key isn't refetched.
**Follow-up trap:** *"Does DataLoader fix N+1 across separate HTTP requests?"* — no, its cache is scoped to a single request/tick by design; sharing it across requests would leak data between users. Cross-request caching needs a separate layer (Redis, CDN) with its own invalidation story.

### Q4 — How do you stop a GraphQL API being used for a denial-of-service via a pathological query?
**Answer:** Two independent controls: depth limiting (reject queries nested past a fixed level, typically 5-10) and cost/complexity analysis (assign a numeric cost per field, scaled by list-size arguments, sum the AST cost before execution, reject over a budget). Neither is on by default in most servers; both must be added deliberately.
**Follow-up trap:** *"A query is shallow but requests a list with `first: 100000`. Does depth limiting catch it?"* — no, depth limiting only bounds nesting, not breadth. That's exactly why cost analysis (which factors in the `first`/`limit` argument) is the second, separate control — depth alone is insufficient.

### Q5 — WebSocket or SSE for a live stock ticker?
**Answer:** SSE. The client only receives; it never needs to send anything on that channel. SSE gets you automatic reconnection built into `EventSource`, works through existing HTTP infrastructure (proxies, CDNs mostly pass it through if not buffered), and avoids the stateful-connection-affinity problem WebSocket brings at the load balancer.
**Follow-up trap:** *"Now the client needs to place a cancel order on the same low-latency path — does that change your answer?"* — yes, if cancel needs to interrupt in-flight state with sub-100ms round trip on the same connection, that's bidirectional and WebSocket (or a WebSocket alongside SSE) is the right call; if cancel can be a normal separate REST POST, SSE plus REST is still simpler.

### Q6 — Why does SSE reconnect automatically and WebSocket doesn't?
**Answer:** It's specified behavior of the `EventSource` API: on disconnect, the browser reconnects automatically after a provider-suggested `retry:` interval and sends `Last-Event-ID` so the server can resume from where it left off. WebSocket has no equivalent in the spec — reconnect logic (with backoff and resubscription) is something you write yourself in `onclose`.
**Follow-up trap:** *"Does that mean SSE never loses events?"* — no, it only means the *reconnect mechanism* is automatic; the server still has to actually support resuming from `Last-Event-ID` (buffering recent events) or the client silently misses whatever happened during the gap.

### Q7 — Design a webhook receiver that's safe against retries and out-of-order delivery.
**Answer:** Verify the HMAC signature on the raw body before parsing anything. Extract the provider's event ID and do an atomic `INSERT ... ON CONFLICT DO NOTHING` into a processed-events table before acting, so a retried delivery is a no-op. For ordering, include and check a sequence number or timestamp per entity and ignore/queue events that are older than the last-applied one for that entity. Return 2xx fast — ideally after enqueueing to your own internal queue rather than doing the full processing synchronously, since a slow 200 still looks like a timeout to some providers and triggers another retry.
**Follow-up trap:** *"What if two events for the same entity arrive in the same millisecond, out of causal order?"* — a wall-clock timestamp from the provider isn't sufficient on its own if their system has clock skew or the events were queued out of order upstream; use whatever monotonic sequence number the provider supplies (many do: Stripe's events have a strictly increasing internal ordering per object, exposed via the API if not the payload) rather than trusting timestamps alone.

### Q8 — Polling vs long-polling vs webhook — when is each the right call?
**Answer:** Polling: simplest, works when you control the schedule and can tolerate latency up to the poll interval; wasteful at high frequency or low change-rate. Long-polling: server holds the request open (commonly 20-30s) until data is ready or timeout, then the client reissues — better latency than polling, still requires holding connections open at scale. Webhook: lowest latency and lowest wasted traffic, but requires a reachable public endpoint and hands you the reliability burden (retry, ordering, idempotency, signature verification).
**Follow-up trap:** *"Your client is behind a corporate NAT with no inbound access. What now?"* — webhooks are off the table since the provider can't reach you; fall back to polling or long-polling, or have the provider push to an intermediary (a queue or relay) that your client polls or long-polls against instead.

### Q9 — Why is a message queue sometimes the right answer to "which protocol should I use"?
**Answer:** Because the question is often not "which protocol" but "should this even be synchronous." A queue decouples producer and consumer lifetimes — the producer doesn't wait for or depend on the consumer being up, buffers against a downstream outage instead of failing the caller, and gives at-least-once delivery with replay (Kafka retains messages for a configurable window, commonly days, letting you reprocess after a bug fix).
**Follow-up trap:** *"The caller needs a synchronous answer to show the user. Does a queue still work?"* — not directly; you'd need a request/reply pattern on top of the queue (correlation ID + reply topic, or a synchronous gateway that polls/waits), which reintroduces most of what a direct call would have given you for free, plus queue operational overhead. If the caller genuinely needs the answer now, a queue is the wrong tool.

### Q10 — Your team put GraphQL in front of a public, read-heavy, rarely-changing product catalog. What's wrong with that choice, and what would you have done instead?
**Testing:** the senior "when NOT to" signal.
**Answer:** You've given up CDN-level caching for query flexibility a catalog browse page doesn't need — every request is a POST to `/graphql`, uncacheable by any intermediary unless you additionally implement persisted queries. A REST API with `GET /products/{id}?fields=name,price,image` plus normal `Cache-Control`/ETag headers gets you most of the field-selection benefit while keeping the free CDN caching, at a fraction of the backend complexity (no resolver N+1, no query-cost DoS surface to defend).
**Follow-up trap:** *"The mobile team says they need to assemble five different screens from this catalog and REST costs them round trips."* — that's a real problem, but the fix is a BFF (backend-for-frontend) endpoint per screen shape, or persisted GraphQL queries (fixed, allow-listed queries turned back into cacheable GETs) — not full ad-hoc GraphQL exposed publicly with an open query surface.

### Q11 — Compare cache-key composition risk across REST, GraphQL, and CDN edge caching.
**Answer:** REST caches naturally key on the URL (path + query params); a cache that ignores a query param like `?locale=de` will silently serve the wrong locale to everyone — a classic cache-poisoning-adjacent bug. GraphQL, being POST-body-keyed, has no default cache key at all unless you introduce persisted queries (hash the query text + variables into a fixed key) or a response cache keyed on the parsed operation + variables. Either way, the deciding factor is always: does the cache key include every input that changes the response, and nothing that doesn't (varying on an irrelevant header wastes cache entries).
**Follow-up trap:** *"A CDN cache is keyed correctly but a user reports seeing another user's personalized data."* — check whether an auth-dependent field snuck into a response that's cached at a shared (not per-user) cache layer — this is the single most common real CDN misconfiguration, and the fix is either `Cache-Control: private` on personalized responses or stripping personalization out of the cached payload entirely (fetch personalization client-side, separately).

### Q12 — A downstream service occasionally takes 30+ seconds under load. Would you add a queue, retries, or a circuit breaker, and does that change your protocol choice?
**Answer:** This isn't fixed by protocol choice at all — it's a resilience problem layered on top of whichever protocol you picked (see the resilience catalogue: timeout, retry+jitter, circuit breaker, bulkhead). But if the *pattern* is that the caller doesn't need the result synchronously, that's the signal to move the call behind a queue entirely: accept the request fast, enqueue the work, return 202, and let the consumer process at its own pace — converting a latency problem you were fighting with retries into a throughput problem a queue handles natively.
**Follow-up trap:** *"The caller does need the result to render the page."* — then a queue doesn't remove the wait, it just relocates it (poll for completion, or hold a WebSocket/SSE connection open for the eventual result) — often not actually simpler than fixing the synchronous path's resilience directly.

### Q13 — Why did Hystrix-era engineers describe gRPC deadlines as better than HTTP timeouts?
**Answer:** gRPC deadlines propagate as wire metadata through the call chain — if service A calls B with a 3s deadline and B calls C, C sees the *remaining* time, not a fresh timeout. Plain HTTP has no equivalent by default; each hop's timeout is set independently unless your team manually threads a deadline header through every service, which most codebases claim to do and don't.
**Follow-up trap:** *"Does that mean gRPC solves cancellation propagation automatically too?"* — deadlines and cancellation are related but distinct: a deadline expiring does trigger cancellation on the gRPC context, but only if every hop actually checks the context at its await/blocking points — a service that ignores the canceled context and keeps working past the deadline gets none of the benefit despite using gRPC.

---

## Red flags that fail you

- Recommending GraphQL for a public API without mentioning the cache-cost and DoS-control tradeoff.
- Saying "WebSocket is more real-time than SSE" without qualifying that SSE's one-way limitation, not its latency, is the actual difference.
- Describing webhooks as reliable without mentioning retry/idempotency/ordering are the receiver's responsibility.
- Reaching for a message queue or GraphQL as a reflex rather than in response to a specific decoupling or client-shape need.
- Not knowing GraphQL returns HTTP 200 on partial failure.
- Claiming gRPC works natively from a browser.

---

## Cheat card

```
REST      cacheable (URL+verb), universal tooling, no native streaming
          verbose JSON; 3 round trips for related resources w/o BFF

gRPC      HTTP/2 binary, Protobuf ~2-5x smaller than JSON, native deadlines
          4 RPC shapes (unary/server/client/bidi streaming)
          no browser support natively; needs HTTP/2-aware infra

GraphQL   fixes over-/under-fetch, 1 request per screen shape
          COSTS: no URL cache (POST body) unless persisted queries
                 N+1 resolver risk → DataLoader batches per tick
                 no default depth/cost limit → DoS risk
                 partial failure = HTTP 200 + errors[] array

WebSocket full duplex, stateful, needs LB affinity / pub-sub backplane
SSE       server→client only, plain HTTP, EventSource auto-reconnects
          + Last-Event-ID resume; use unless bidi truly required

Webhooks  provider pushes; YOU own: retry receipt idempotency,
          HMAC signature verify, no ordering guarantee
Polling / long-poll: use when no public inbound endpoint possible
          long-poll hold ~20-30s then reissue

Queue     (Kafka/SQS/RabbitMQ) decouples producer/consumer lifetime
          buffers downstream outages, at-least-once + replay (days)
          wrong tool if caller needs a synchronous answer now

DECIDE ON: public vs internal · push direction · bidi needed?
           both ends yours? · cache needs · team's operational maturity
```

## Sources

- [REST vs GraphQL vs gRPC — Hello Interview networking essentials](https://www.hellointerview.com/learn/system-design/core-concepts/networking-essentials) — accessed 2026-07-26
- [Polling vs. Long-Polling vs. SSE vs. WebSockets vs. Webhooks — AlgoMaster](https://blog.algomaster.io/p/polling-vs-long-polling-vs-sse-vs-websockets-webhooks) — accessed 2026-07-26
- [Webhook vs. API Polling in System Design — GeeksforGeeks](https://www.geeksforgeeks.org/system-design/webhook-vs-api-polling-in-system-design/) — accessed 2026-07-26
- [GraphQL N+1 Problem — caisy.io](https://caisy.io/blog/understanding-solving-graphql-n-1) — accessed 2026-07-26
- [GraphQL Security: Query Depth Limiting and Cost Analysis — Medium](https://medium.com/@sohail_saifi/graphql-security-query-depth-limiting-and-cost-analysis-fd8c22867dd5) — accessed 2026-07-26
- [GraphQL Cheat Sheet — OWASP](https://cheatsheetseries.owasp.org/cheatsheets/GraphQL_Cheat_Sheet.html) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
