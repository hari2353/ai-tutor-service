# API Design: REST Maturity, gRPC, GraphQL, Versioning, OpenAPI-First, SSE/WebSocket, Pagination, Error Contracts

> **Track:** T11 Polyglot Backend · **Time:** 2.5h · **Prereqs:** T11-go-services, T21-resilience-catalogue · **Updated:** 2026-08-03
> **Module id:** `T11-api-design` · **Tags:** api

## The 30-second version

The 2026 consensus on protocol choice has settled into a genuine, workload-driven split rather than a single winner: **REST remains the right default for public-facing APIs** because it caches cleanly at every layer (CDN, browser, intermediate proxies) and is debuggable with nothing more than `curl`, **GraphQL has won the aggregation layer** in front of complex backends serving diverse clients (mobile needing a thin payload, web needing a rich one, from the same underlying data), **gRPC is the default for internal service-to-service calls** (covered mechanically in `T11-go-services`), and **tRPC has carved out a real niche eliminating the API boundary entirely** for TypeScript full-stack applications where the same team owns both ends. Richardson's four-level REST maturity model (Level 0: one endpoint, everything's a POST — "the swamp of POX"; Level 1: resources get their own URLs; Level 2: HTTP verbs and status codes are used correctly, which is what "RESTful" means in practice for the overwhelming majority of real APIs; Level 3: HATEOAS, hypermedia links driving client navigation, rare in practice) is a real, checkable framework — most production APIs stop at Level 2 deliberately, not out of ignorance, because Level 3's promised benefit (clients that don't hardcode URLs) rarely justifies its real complexity cost. Cursor-based pagination has become the mandatory default over offset-based pagination for any dataset that's large or frequently updated, for a concrete, measurable reason: an offset query at `offset=999,950` forces the database to scan and discard nearly a million rows before returning results, with visibly degrading latency as the offset grows, while a cursor query (`WHERE id > last_seen_id ORDER BY id LIMIT N`) hits an index and returns in near-constant time regardless of how deep into the dataset you are — this is the pattern Stripe, Slack, and GitHub all use, and it's not a stylistic preference. Error contracts should follow **RFC 9457** (Problem Details for HTTP APIs, published August 2023, superseding RFC 7807 from 2016) — a structured JSON shape (`type`, `title`, `status`, `detail`, `instance`, plus extension fields) that gives every client a predictable, machine-parseable error shape instead of each endpoint inventing its own. SSE (Server-Sent Events) should be the default choice for **95% of real-time/streaming use cases** — unidirectional server-to-client delivery with built-in reconnection (`Last-Event-ID` header) and transparent support from every major CDN — reaching for WebSocket specifically for the remaining 5% that genuinely need bidirectional, low-latency, binary-capable communication (voice/video signaling, collaborative multi-cursor editing, gaming). API versioning has no single universally-correct answer — URL-path versioning (`/v1/users`) is the safest default because it caches cleanly with zero extra CDN configuration, header-based versioning keeps URLs stable but breaks standard HTTP caching unless `Vary` is set correctly, and date-based versioning (GitHub's, Stripe's actual production pattern) suits platforms shipping frequent, fine-grained breaking changes — the right choice depends on your consumers, your caching layer, and your actual breaking-change cadence, not a rule to apply uniformly.

## Why this gets asked

Because API design is the single most consequential, hardest-to-reverse decision a backend team makes — a bad database index gets fixed with a migration, a bad API contract gets fixed by breaking every consumer who ever integrated against it — and it's a topic where the actual, current 2026 landscape (REST/GraphQL/gRPC/tRPC each winning a specific, non-overlapping niche rather than one protocol dominating) has genuinely shifted from the more binary "REST vs GraphQL" framing common a few years earlier. The interviewer has almost certainly debugged an offset-pagination performance cliff in production (a report that got slower every week as the underlying table grew, traced to `OFFSET 50000` scanning fifty thousand rows every single page load), or reviewed a PR introducing yet another bespoke error response shape that broke a client's error-handling code expecting the shape from three other endpoints. Given this candidate's production RAG/agentic-AI and 8-service recommendation-platform background, this module is also implicitly testing whether the same API-design discipline that applies to a conventional CRUD service transfers correctly to streaming, tool-calling, and multi-service API surfaces — which is exactly where sloppy API design shows up first and hurts most.

---

## Lineage: past → present → future

**What came before.** Pre-REST web APIs (SOAP, XML-RPC, CORBA) were verbose, heavily tooling-dependent (WSDL-driven code generation, XML envelopes with significant per-request overhead), and tightly coupled to specific transport/framework assumptions that made cross-language, cross-team integration genuinely painful — a real, well-documented pain point that motivated Roy Fielding's 2000 dissertation formalizing REST as an architectural style built on HTTP's existing, universal semantics (verbs, status codes, caching headers) rather than inventing a new protocol on top of HTTP. REST's adoption through the 2000s-2010s was overwhelmingly at Richardson Maturity Level 1-2 in practice — resources with real URLs, correct verb usage — with Level 3's HATEOAS remaining largely theoretical outside a small number of purist implementations, because the promised benefit (a client that discovers available actions dynamically via response links, needing no hardcoded knowledge of the API surface) rarely justified the real engineering cost of building and maintaining that hypermedia layer for typical CRUD-shaped APIs.

**Where it stands now.** GraphQL (Facebook, 2015 public release) solved a real, specific REST pain point — over-fetching and under-fetching, where a mobile client needing three fields from a resource either receives the whole resource (over-fetch, wasted bandwidth) or needs multiple round trips to assemble what it actually needs (under-fetch, latency) — by letting the client specify exactly the shape of data it wants in a single request. gRPC (2015, built on Google's internal Stubby, covered mechanically in `T11-go-services`) solved a different, adjacent problem: efficient, strongly-typed, binary internal service-to-service communication where REST/JSON's text-based overhead and lack of native streaming semantics were the actual bottleneck. The 2026 landscape is genuinely settled into complementary niches rather than one protocol "winning": REST for public APIs (caching, debuggability, tooling ubiquity), GraphQL specifically at the aggregation layer serving multiple diverse client shapes from one backend, gRPC for internal service-to-service calls, and tRPC (a genuinely newer entrant, now cited around 15% of TypeScript job postings and climbing) for the specific case of a TypeScript full-stack team wanting to eliminate the API boundary's type-safety gap entirely by sharing types directly between frontend and backend code. On error contracts specifically, RFC 9457 (August 2023) superseded RFC 7807 (2016) with tightened semantics (clarifying that a `type` URI must not be dereferenced to fetch machine-readable information, and formalizing "problem type extensions") — both RFCs describe compatible shapes in practice, and current tooling generally targets either interchangeably.

**Where it's heading.** OpenAPI 3.1's alignment with JSON Schema (rather than OpenAPI's earlier, subtly different schema dialect) has brought OpenAPI-first tooling — client generation, mock servers, contract testing — to rough parity with GraphQL's SDL-driven tooling ecosystem, closing a gap that used to be a real GraphQL advantage; expect OpenAPI-first workflows (writing the contract before the implementation, generating both client and server scaffolding from it) to keep gaining ground as the default discipline for REST APIs specifically because of this tooling maturity, not just as an aspirational best practice. Contract testing (verifying a service's actual behavior against its published OpenAPI/GraphQL schema automatically, in CI) is trending from "nice to have" toward "the primary defense against integration breaks" in distributed systems specifically — a natural, current extension of the general resilience discipline covered in `T21-resilience-catalogue` applied to API contracts rather than runtime failures. tRPC's continued growth is worth watching as a genuinely new pattern (not a REST or GraphQL variant) rather than dismissing it as a TypeScript-ecosystem curiosity — its specific bet (shared types eliminate an entire class of contract-drift bugs, at the cost of requiring both ends to be TypeScript) is a real, if narrower, tradeoff gaining real adoption.

---

## Mental model

```
PROTOCOL CHOICE, 2026 (non-overlapping niches, not one winner):

  PUBLIC API, external/partner consumers  ──▶  REST
    (caches at CDN, debuggable w/ curl, universal tooling)

  AGGREGATION layer, diverse client shapes ──▶ GraphQL
    (mobile needs 3 fields, web needs 20, ONE query shape adapts per client)

  INTERNAL service-to-service, polyglot    ──▶ gRPC
    (binary, HTTP/2 multiplexed, auto deadline propagation — T11-go-services)

  TypeScript full-stack, SAME team owns both ends ──▶ tRPC
    (eliminates the API boundary's type gap entirely — no schema, no
     codegen, the function signature IS the contract, shared directly)

RICHARDSON MATURITY MODEL (checkable, not a vibe):
  L0: one endpoint, everything's a POST         "swamp of POX"
  L1: resources get real URLs                   /orders/123, not ?action=getOrder
  L2: HTTP VERBS + STATUS CODES used correctly   <- most production APIs
      GET=read, POST=create, PUT=replace,           stop HERE, deliberately
      PATCH=partial update, DELETE=delete
      200/201/204 success, 4xx client error, 5xx server error
  L3: HATEOAS — response includes LINKS to next available actions
      rare in practice — cost rarely justifies the dynamic-discovery benefit

PAGINATION: OFFSET degrades, CURSOR doesn't
  OFFSET: "SELECT * OFFSET 999950 LIMIT 20"
    -> DB must scan+discard 999,950 rows EVERY TIME, latency grows with depth
  CURSOR: "SELECT * WHERE id > :last_seen_id ORDER BY id LIMIT 20"
    -> hits an INDEX, near-constant time REGARDLESS of depth into dataset
    -> Stripe/Slack/GitHub pattern. MANDATORY for large/frequently-updated data.

SSE vs WEBSOCKET: SSE = 95% of real-time use cases (default)
  SSE:  unidirectional (server->client), TEXT only, BUILT-IN reconnect
        (Last-Event-ID header), CDN-transparent (Cloudflare/Fastly/CloudFront)
  WS:   bidirectional, BINARY-capable, NO built-in reconnect, CDN support
        is special-cased/inconsistent — the 5%: voice/video signaling,
        collaborative multi-cursor, gaming — genuine bidirectional need

ERROR CONTRACT: RFC 9457 (supersedes RFC 7807, Aug 2023)
  { "type": "...", "title": "...", "status": 422,
    "detail": "...", "instance": "...", + extension fields }
  ONE shape, every endpoint, every client parses it the same way.

VERSIONING: no single right answer — depends on consumers/caching/cadence
  URL PATH (/v1/users):  safest default, CDN-caches with ZERO extra config
  HEADER (Accept-Version): stable URLs, BREAKS caching unless Vary is set
  DATE-BASED (Stripe/GitHub): fast-evolving platform APIs, fine-grained
```

---

## How it actually works

### Richardson Maturity Model: why most production APIs stop at Level 2 deliberately

```http
GET /orders/123 HTTP/1.1                    ← Level 1: real resource URL

HTTP/1.1 200 OK                              ← Level 2: correct status code
Content-Type: application/json

{ "id": 123, "status": "shipped", "total": 49.99 }

# Level 3 (HATEOAS) would add:
{ "id": 123, "status": "shipped", "total": 49.99,
  "_links": {
    "self": { "href": "/orders/123" },
    "cancel": { "href": "/orders/123/cancel", "method": "POST" },
    "track": { "href": "/orders/123/tracking" }
  }
}
```

Level 2 — correct HTTP verb semantics (`GET` is safe and idempotent, `PUT` is idempotent, `POST` is neither by default, `DELETE` is idempotent) and correct status codes (`201 Created` with a `Location` header for a successful creation, `204 No Content` for a successful action with no body, `409 Conflict` for a state conflict, `422 Unprocessable Entity` for semantic validation failure — the same 422-vs-400 distinction covered mechanically in `T11-fastapi-deep`) — is what "RESTful" means for the overwhelming majority of real, production APIs, and stopping here is a deliberate, defensible engineering choice, not an unfinished implementation. Level 3's HATEOAS promises clients that don't hardcode URLs and can discover available next-actions dynamically from response links, which is a genuinely valuable property for a small number of use cases (a generic API browser, a workflow engine navigating dynamically) but adds real complexity (every response needs correctly-computed link relations reflecting the current resource state and the caller's permissions) that most APIs' actual client population — engineers writing code against documented endpoints — never benefits from, since they're going to hardcode the URL pattern in their client code regardless of whether the server offers a link to discover it dynamically.

### Cursor vs offset pagination: the mechanism, with real numbers

```sql
-- OFFSET: cost grows with depth, REGARDLESS of index presence on the sort column
SELECT * FROM orders ORDER BY created_at DESC OFFSET 999950 LIMIT 20;
-- the database must count through and discard 999,950 rows before returning
-- the 20 you actually want, EVERY TIME this exact query runs — the deeper
-- the page, the slower the query, with no way to index around it because
-- OFFSET itself has no index-friendly representation

-- CURSOR: cost is roughly constant, REGARDLESS of depth into the dataset
SELECT * FROM orders WHERE created_at < :last_seen_created_at
ORDER BY created_at DESC LIMIT 20;
-- an index on created_at lets the database seek DIRECTLY to the right
-- starting point and read forward 20 rows — page 1 and page 50,000 cost
-- roughly the same, because the WHERE clause is a real, indexable predicate
```

```json
// The response shape a cursor-paginated API should return, consistently
{
  "data": [ /* 20 items */ ],
  "pagination": {
    "next_cursor": "eyJjcmVhdGVkX2F0IjoiMjAyNi0wOC0wM1QxMDo...",
    "has_more": true
  }
}
```

The `next_cursor` value is typically an opaque, encoded token (frequently base64-encoded JSON, though the exact encoding is an implementation detail clients should never parse or construct themselves) representing the position to resume from — treating it as opaque is deliberate, since it lets the server change its internal pagination implementation (switching the underlying sort key, adding a tiebreaker column for uniqueness) without breaking clients who only ever pass the cursor back verbatim. **The real, checkable tradeoff cursor pagination gives up**: you lose the ability to jump to an arbitrary page number (`?page=500`) or show a total page count cheaply, since cursor pagination is inherently sequential — for a UI that genuinely needs "jump to page 50 of 200" (rare, but real for some admin/reporting interfaces), offset pagination (accepting its performance ceiling, or bounding how deep users can actually page) or a hybrid approach (cursor for the primary feed, a separate, less-frequently-hit "search/jump" endpoint using offset with an enforced maximum depth) is the honest answer, not pretending cursor pagination is a strict, costless upgrade in every case.

### Error contracts: RFC 9457's Problem Details shape

```json
HTTP/1.1 422 Unprocessable Entity
Content-Type: application/problem+json

{
  "type": "https://api.example.com/errors/insufficient-inventory",
  "title": "Insufficient inventory",
  "status": 422,
  "detail": "Only 3 units of SKU WIDGET-42 are available, but 5 were requested.",
  "instance": "/orders/789",
  "sku": "WIDGET-42",
  "available": 3,
  "requested": 5
}
```

The five standard members — `type` (a URI identifying the error category, not necessarily dereferenceable, RFC 9457 explicitly clarifies it must not be treated as a live lookup), `title` (a short, human-readable summary, generally static per `type`), `status` (the HTTP status code, duplicated here for convenience since some clients don't have easy access to the transport-level status), `detail` (a specific, human-readable explanation of *this particular* occurrence), and `instance` (a URI identifying the specific occurrence, useful for correlating with server-side logs, similar in spirit to the `error_id` correlation pattern covered in `T11-fastapi-deep`) — plus arbitrary extension members (`sku`, `available`, `requested` above) for machine-consumable, error-type-specific detail. The concrete production benefit over each endpoint inventing its own error shape: a client's error-handling code can be written once, generically, against the `type`/`title`/`status`/`detail` shape, with extension fields parsed only when the client specifically cares about that error `type` — rather than every new endpoint requiring new client-side error-parsing code because the shape is different every time.

### SSE vs WebSocket: choosing correctly, and the reconnection mechanism

```javascript
// SSE — the 95% case, built-in reconnection via Last-Event-ID
const events = new EventSource('/api/orders/789/stream');
events.onmessage = (e) => console.log(JSON.parse(e.data));
// on a dropped connection, the BROWSER automatically reconnects and sends
// a Last-Event-ID header with the last event id it received — the SERVER
// is responsible for resuming the stream from after that id, not the client
```

```
Server response format enabling this:
id: 12345
data: {"status": "shipped"}

id: 12346
data: {"status": "delivered"}
```

SSE's built-in reconnection (the browser's native `EventSource` retries automatically on disconnect, sending `Last-Event-ID` so the server can resume rather than replay from the start) and universal CDN transparency (Cloudflare, Fastly, CloudFront all handle SSE's plain-HTTP-with-a-long-lived-response-stream model without special configuration) make it the correct default for the large majority of "real-time" product requirements — live order status, notification feeds, and (per `T33-streaming-ai-ui`'s deeper coverage) LLM token streaming are all fundamentally unidirectional server-to-client delivery problems that don't need WebSocket's bidirectional capability. WebSocket's genuine, narrower niche is the remaining cases needing the client to push data mid-stream with low latency (a voice agent's barge-in interruption, collaborative real-time cursors, a multiplayer game's input stream) — reaching for WebSocket by default for a unidirectional streaming need is reaching for more complexity (no built-in reconnection, CDN configuration friction, connection-state management on the server) than the actual requirement justifies.

### API versioning: matching the strategy to the actual constraint

```
URL PATH:    GET /v1/orders/789          — safest default. CDN caches this
             GET /v2/orders/789            URL cleanly with zero extra config,
                                            since each version is a genuinely
                                            distinct, cacheable URL.

HEADER:      GET /orders/789               — keeps URLs stable (nice for
             Accept: application/vnd.example.v2+json    bookmarking, linking),
                                            BUT breaks standard HTTP caching
                                            unless the server correctly sets
                                            `Vary: Accept` so a CDN/cache
                                            doesn't serve v1's cached response
                                            to a v2 request hitting the same URL.

DATE-BASED:  GET /orders/789               — Stripe's and GitHub's real
             Stripe-Version: 2026-06-15     production pattern: each client
                                            pins to a specific API date/
                                            snapshot, the server maintains
                                            behavior compatibility per pinned
                                            date, suited to platforms shipping
                                            frequent, fine-grained changes
                                            rather than infrequent big-bang
                                            major versions.
```

The honest, senior framing: there is no universally-correct choice, and the decision genuinely depends on three concrete factors — how much your consumers value stable, cacheable URLs versus stable version-pinning semantics; whether your caching layer (a CDN, a reverse proxy) is easy or hard to configure correctly for header-based `Vary` behavior; and how frequently you actually ship breaking changes (infrequent major versions fit URL-path versioning naturally; frequent, small, fine-grained changes fit date-based versioning better, since forcing every small change through a new major URL-path version is heavier than the change warrants).

---

## Build it from scratch

A minimal, correctly-shaped cursor-paginated endpoint with an RFC 9457 error contract, worth being able to sketch cold:

```python
# untested sketch — FastAPI, cursor pagination + RFC 9457 error shape
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
import base64, json

app = FastAPI()

def encode_cursor(created_at: str) -> str:
    return base64.urlsafe_b64encode(json.dumps({"created_at": created_at}).encode()).decode()

def decode_cursor(cursor: str) -> dict:
    return json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())

@app.get("/orders")
async def list_orders(cursor: str | None = Query(None), limit: int = Query(20, le=100)):
    last_created_at = decode_cursor(cursor)["created_at"] if cursor else None
    orders = await db.orders.find_page(after=last_created_at, limit=limit)  # indexed query
    next_cursor = encode_cursor(orders[-1].created_at) if len(orders) == limit else None
    return {
        "data": orders,
        "pagination": {"next_cursor": next_cursor, "has_more": next_cursor is not None},
    }

class ProblemDetail(Exception):
    def __init__(self, type_: str, title: str, status: int, detail: str, **extensions):
        self.type, self.title, self.status, self.detail = type_, title, status, detail
        self.extensions = extensions

@app.exception_handler(ProblemDetail)
async def problem_detail_handler(request, exc: ProblemDetail):
    return JSONResponse(
        status_code=exc.status,
        media_type="application/problem+json",
        content={"type": exc.type, "title": exc.title, "status": exc.status,
                 "detail": exc.detail, "instance": str(request.url), **exc.extensions},
    )
```

A fuller lab building this endpoint against a real, indexed table with 1M+ rows, measuring offset-vs-cursor query latency at increasing depth directly, plus an SSE endpoint with correct `Last-Event-ID` resumption, belongs in `(lab pending)`.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| A "list orders" endpoint's p99 latency climbs steadily as a customer's order history grows, or as time passes and more historical data accumulates | Offset-based pagination — the database scans and discards an ever-growing number of rows for deep pages | Migrate to cursor-based pagination on an indexed sort key; if arbitrary page-jump is a genuine product requirement, bound the maximum offset depth explicitly rather than allowing unbounded degradation |
| Every endpoint's error response has a different JSON shape, and client-side error handling is a maze of endpoint-specific special cases | No shared error contract — each endpoint (or each engineer) invented its own error shape independently | Adopt RFC 9457's Problem Details shape uniformly, with a shared exception-handling layer producing it consistently across the whole API surface |
| A WebSocket-based notification feature has frequent, hard-to-debug connection drops in production that don't reproduce locally | CDN/proxy infrastructure not configured for (or not supporting) WebSocket's long-lived, bidirectional connection model, unlike SSE's transparent plain-HTTP compatibility | Reassess whether the feature genuinely needs bidirectional communication; if it's actually unidirectional (notifications, status updates), migrate to SSE and let CDN infrastructure handle it transparently |
| A v2 API rollout breaks existing v1 clients despite both versions supposedly being served from the same infrastructure | Header-based versioning without a correctly configured `Vary: Accept` (or equivalent) header, causing a CDN/cache to serve a cached v1 response to a v2 request hitting the identical URL | Either fix the `Vary` header configuration, or migrate to URL-path versioning, which sidesteps this entire class of caching bug by construction |
| A GraphQL aggregation layer's single query fans out to a dozen inefficient N+1-shaped calls against backend services | No dataloader/batching layer between the GraphQL resolvers and the backend services — the same N+1 problem covered in `T11-spring-boot`, manifesting at the API-aggregation layer instead of the ORM layer | Add a batching/dataloader layer between resolvers and backend calls, deduplicating and batching what would otherwise be N individual calls per field resolved |
| A public API's OpenAPI spec and its actual runtime behavior have drifted — documented request/response shapes don't match what the server actually does | No contract testing verifying the implementation against the published spec in CI | Add automated contract tests (verifying request/response schemas, status codes, header policies against the OpenAPI spec) as a CI gate, not a manual, periodically-forgotten documentation task |

---

## Tradeoffs & when NOT to use it

- **Don't default to offset pagination for any dataset that's large or frequently updated.** The performance cliff is real, measurable, and gets worse the longer the table grows — cursor pagination should be the default, with offset reserved for genuinely small, rarely-changing datasets or explicit arbitrary-page-jump requirements.
- **Don't invent a new error response shape per endpoint.** A shared, RFC 9457-shaped error contract is close to free to implement uniformly and saves every client integrator real, ongoing pain.
- **Don't reach for WebSocket by default for a unidirectional streaming requirement.** SSE covers the 95% case with less complexity, built-in reconnection, and transparent CDN support — reserve WebSocket for genuinely bidirectional, low-latency needs.
- **Don't pursue HATEOAS/Level 3 REST maturity reflexively "because it's more RESTful."** Most production APIs' actual client population (engineers writing code against documented endpoints) never benefits from dynamic link discovery enough to justify the real implementation and maintenance cost — Level 2 is a legitimate, deliberate stopping point.
- **Don't apply one versioning strategy uniformly without considering your actual consumers, caching layer, and change cadence.** URL-path, header-based, and date-based versioning each have a real, different cost profile — the "best" one is workload-dependent, not universal.
- **Don't use GraphQL as a wholesale REST replacement for a simple, single-client-shape API.** Its real value is specifically the aggregation/multi-client-shape use case; a straightforward CRUD API with one client consuming it gains complexity from GraphQL's resolver/schema machinery without a corresponding benefit.

---

## Interview questions

### Q1 — Why does offset pagination degrade at scale while cursor pagination doesn't, mechanically?
**Testing:** the actual database mechanism, not just "cursor is better."
**Answer:** `OFFSET N` requires the database to count through and discard the first N rows before returning the requested page — there's no index-friendly way to represent "skip to row N" directly, so the scan cost grows linearly with the offset regardless of whether the sort column is indexed. A cursor query (`WHERE sort_column < :last_seen_value ORDER BY sort_column LIMIT N`) is a genuine, indexable predicate — the database can seek directly to the right starting point via the index and read forward, so cost stays roughly constant whether you're on page 1 or page 50,000.
**Follow-up trap:** *"What does cursor pagination give up that offset pagination has?"* — the ability to jump to an arbitrary page number or cheaply show a total page count, since cursor pagination is inherently sequential (you can only move forward/backward from a known position, not teleport to page 500 directly) — a real, honest tradeoff to name, not something cursor pagination solves for free.

### Q2 — When would GraphQL be the right choice over REST, and when would introducing it be adding complexity with no real payoff?
**Testing:** whether GraphQL is understood as solving a specific problem, not adopted as a general "more modern" upgrade.
**Answer:** Right choice: an aggregation layer serving genuinely diverse client shapes from the same underlying data — a mobile client needing 3 fields and a web client needing 20 from the same resource, where REST would otherwise mean either over-fetching (mobile gets the full resource) or maintaining multiple bespoke endpoints per client shape. Wrong choice: a straightforward API with one client shape, or a public API prioritizing caching and debuggability — GraphQL's typical single-endpoint, POST-based query model is inherently harder to cache at a CDN layer than REST's per-resource URLs, and its resolver/schema machinery is real, ongoing complexity that a simple CRUD API gains nothing from.
**Follow-up trap:** *"Doesn't GraphQL solve over-fetching for REST too, so isn't it strictly better for any API?"* — the caching cost is the real counter-argument: REST's GET-based, per-URL model caches transparently at every layer (browser, CDN, intermediate proxy) using standard HTTP semantics, while GraphQL's typical single-endpoint POST model requires bespoke, harder-to-configure caching strategies — for a public API where CDN caching matters a great deal, that's a real cost GraphQL's flexibility doesn't offset for every use case.

### Q3 — Explain RFC 9457's Problem Details shape and why a shared error contract matters more than any specific field choice.
**Testing:** whether the actual production value (predictability, not the RFC number) is understood.
**Answer:** Five standard members — `type` (a URI identifying the error category, not meant to be dereferenced as a live lookup per RFC 9457's clarification), `title`, `status`, `detail`, `instance` — plus arbitrary extension fields for error-type-specific machine-readable detail. The real value isn't any specific field, it's that every endpoint in an API returns errors in the *same* shape, so client-side error-handling code can be written once, generically, against `type`/`title`/`status`/`detail`, rather than every new endpoint requiring bespoke client-side parsing because its error shape is different from the last one.
**Follow-up trap:** *"What's the difference between RFC 7807 and RFC 9457, and does it matter which you target?"* — RFC 9457 (August 2023) superseded RFC 7807 (2016), tightening semantics (clarifying `type` mustn't be treated as a live lookup, formalizing "problem type extensions") — both describe compatible shapes in practice and current tooling generally targets either interchangeably, so knowing the newer RFC number is a currency signal more than a practically different implementation choice.

### Q4 — A team building a live order-tracking feature is deciding between SSE and WebSocket. Walk through the decision.
**Testing:** applying the 95%/5% framing to a concrete, realistic scenario.
**Answer:** Order status updates are fundamentally unidirectional — the server pushes state changes (processing → shipped → delivered) to the client; the client never needs to push data back through this specific channel. That's squarely SSE's use case: built-in reconnection (the browser automatically retries and sends `Last-Event-ID` so the server can resume rather than replay from scratch), transparent support from every major CDN, and meaningfully less implementation complexity than WebSocket for a need that doesn't require bidirectionality.
**Follow-up trap:** *"What if the feature later needs the client to send a 'cancel this order' action through the same real-time channel?"* — that additional need doesn't retroactively require WebSocket for the whole feature; the cancel action is a distinct, ordinary request (a regular POST/Server Action) separate from the read-only status stream — conflating "I need to send data to the server at some point in this feature" with "I need a bidirectional streaming channel" is a common overreach; most features that feel like they need WebSocket actually need SSE plus an ordinary request/response action alongside it.

### Q5 — Compare the three main API versioning strategies and explain the specific caching failure mode header-based versioning is prone to.
**Testing:** the concrete, checkable caching bug, not just "there are three strategies."
**Answer:** URL-path versioning (`/v1/orders`) creates genuinely distinct, cacheable URLs per version, so CDN caching works correctly with zero extra configuration. Header-based versioning (`Accept: application/vnd.example.v2+json`) keeps the URL identical across versions, which means a CDN or intermediate cache that keys purely on URL will serve a cached v1 response to a v2 request hitting the same URL, unless the server correctly sets `Vary: Accept` (or equivalent) to tell the cache to key on that header too. Date-based versioning (Stripe's, GitHub's actual pattern) pins each client to a specific date/snapshot via a header, suited to platforms shipping frequent, fine-grained breaking changes rather than infrequent major-version bumps.
**Follow-up trap:** *"If Vary fixes the caching bug, why would anyone choose URL-path versioning over header-based versioning at all?"* — `Vary` correctness is a real, ongoing operational burden (every layer in the caching chain — CDN, reverse proxy, browser — needs to respect it correctly, and a misconfiguration anywhere in that chain silently reintroduces the bug), whereas URL-path versioning sidesteps the entire class of failure by construction, at the cost of URLs that change per version — for most public APIs, the simplicity and reliability of URL-path versioning outweighs the aesthetic preference for stable URLs that header-based versioning offers.

### Q6 — What does Richardson Maturity Level 3 (HATEOAS) actually provide, and why do most production APIs deliberately stop at Level 2?
**Testing:** whether stopping at Level 2 is understood as a deliberate engineering tradeoff rather than an unfinished implementation.
**Answer:** HATEOAS embeds links to available next-actions directly in API responses (a "cancel" link on an order response, present only if cancellation is currently valid for that order's state and the caller's permissions), letting a client discover available actions dynamically rather than hardcoding URL patterns and business rules about when actions are valid. Most production APIs stop at Level 2 (correct verbs, correct status codes, real resource URLs) because their actual client population — engineers writing code against documented endpoints — is going to hardcode the URL pattern regardless of whether a link is offered, and correctly computing state-and-permission-aware links for every response is real, ongoing implementation cost with limited payoff for that client population.
**Follow-up trap:** *"Is there a real use case where HATEOAS's cost is clearly worth it?"* — a generic API browser/explorer tool, or a workflow/orchestration engine that genuinely needs to navigate a resource graph without prior knowledge of its specific shape — cases where the *client itself* is generic and can't be hardcoded against a specific API's documented URL patterns, which is a narrower population than most production APIs actually serve.

### Q7 — Design the pagination and error-contract approach for a GraphQL aggregation layer sitting in front of three internal gRPC services, serving both a mobile app and a web app.
**Testing:** synthesizing multiple protocols and this module's patterns into one coherent, multi-layer design.
**Answer:** The GraphQL layer exposes cursor-based pagination via the Relay-style connection pattern (`edges`/`node`/`cursor`/`pageInfo` with `hasNextPage`) as the GraphQL-ecosystem-idiomatic equivalent of this module's cursor pagination principle, translating to the underlying gRPC services' own pagination (which should also be cursor-based internally, for the same database-performance reasons). For errors, GraphQL's own error extensions mechanism (the `errors` array's `extensions` field) can carry the same structured detail RFC 9457 provides for REST — mapping gRPC status codes and messages from the underlying services into a consistent shape at the aggregation layer so both mobile and web clients get one predictable error format regardless of which internal service actually failed. Resolvers calling the three gRPC services should use a dataloader/batching layer to avoid N+1-shaped fan-out, per the general pattern covered in this module's production table.
**Follow-up trap:** *"What happens if one of the three internal gRPC services is degraded — how does that surface through the GraphQL layer?"* — partial GraphQL response: return the fields that resolved successfully from the healthy services alongside a properly-shaped error entry (in the standard `errors` array, associated with the specific failed field's path) for the degraded service's fields, rather than failing the entire query — this is one of GraphQL's genuine advantages over a REST aggregation endpoint, which more commonly either succeeds or fails as one unit.

### Q8 — A public API currently uses offset pagination and header-based versioning. A partner integration reports intermittent stale-data issues and slow "load more" performance on large accounts. Diagnose both and propose fixes.
**Testing:** applying both the pagination and versioning failure modes from this module to one combined, realistic incident.
**Answer:** The slow "load more" is very likely the offset-pagination performance cliff — as the partner's account data grows, deeper pages scan and discard more rows every time, degrading latency measurably as their dataset grows; migrate to cursor-based pagination on an indexed sort key. The intermittent stale-data issue is very likely the header-based-versioning caching bug — if `Vary` isn't configured correctly somewhere in the caching chain (the partner's own HTTP client cache, an intermediate proxy, or the API's own CDN), a cached response from one version can be served for a request expecting another, or a cached response can simply outlive its correct freshness window without the version header being respected as a cache key.
**Follow-up trap:** *"The partner says they can't easily change their integration code right now — what can you fix on your side alone?"* — cursor pagination can be introduced as an additive, backward-compatible change (new pagination parameters alongside the old offset-based ones, with the old ones deprecated on a timeline) without breaking the partner immediately; the caching issue can potentially be fixed entirely server-side by correcting the `Vary` header configuration, with no client-side change required at all — distinguishing which fixes need consumer coordination and which don't is itself a real, senior-level part of the diagnosis.

### Q9 — When would you reach for tRPC over REST or GraphQL, and what's the real limitation that keeps it from being a universal choice?
**Testing:** whether tRPC is understood as a genuinely different, narrower-niche pattern rather than "just another API style."
**Answer:** tRPC eliminates the API contract boundary entirely for a TypeScript full-stack application where the same team (or even the same codebase/monorepo) owns both the frontend and backend — instead of a schema (OpenAPI, GraphQL SDL) that both sides must independently implement and keep in sync, the backend's actual function signatures ARE the contract, imported directly by the frontend with full type inference and no codegen step, eliminating an entire class of contract-drift bugs. The real limitation: it requires both ends to be TypeScript in the same monorepo (or at least sharing a type-generation pipeline) — a mobile app in Swift/Kotlin, a partner's external integration, or any consumer that isn't TypeScript-and-co-located gets no benefit and can't consume a tRPC API the way it would consume REST or GraphQL.
**Follow-up trap:** *"So would you use tRPC for a public API with external partner consumers?"* — no, that's exactly the wrong fit — tRPC's entire value proposition depends on shared TypeScript types across a boundary you don't control for an external partner; REST (or GraphQL for diverse-shape needs) remains the right choice for any API surface with consumers outside your own TypeScript codebase.

### Q10 — A team debates whether idempotency keys belong in the API design layer or the resilience/retry layer. Where do they actually belong, and why does that matter for how you'd design the endpoint?
**Testing:** cross-referencing this module with `T21-resilience-catalogue`'s idempotency coverage, applied to concrete endpoint design.
**Answer:** Idempotency keys are fundamentally an API *contract* concern implemented to serve a resilience *need* — the endpoint's design (accepting an `Idempotency-Key` header, documenting the dedup/replay behavior, defining the response for a repeated key) is squarely part of API design, because it's a client-visible, documented part of the interface; the actual mechanism preventing double-processing (a dedup store, an atomic `INSERT ... ON CONFLICT`) is resilience-layer implementation, covered in `T21-resilience-catalogue`. Designing the endpoint without documenting idempotency-key behavior explicitly (whether it's required, optional, or unsupported for a given mutation) leaves clients unable to safely retry a `POST /charge`-style endpoint without risking duplicate side effects — an API design gap, not just a missing retry policy.
**Follow-up trap:** *"Should every POST endpoint accept an idempotency key?"* — no; only endpoints with real side effects where a duplicate execution is costly (payments, provisioning, sending a notification) need it — a purely read-adjacent or naturally-idempotent-by-construction endpoint (an upsert keyed on a client-provided ID, for instance) doesn't need the extra header/mechanism, and adding it everywhere reflexively is unnecessary API surface for endpoints where retry safety is already structural.

---

## Red flags that fail you

- Using offset pagination for a large or frequently-updated dataset without acknowledging the performance cliff.
- Inventing a new, bespoke error response shape per endpoint instead of a shared contract.
- Recommending WebSocket reflexively for a unidirectional streaming requirement.
- Claiming HATEOAS/Level 3 REST maturity is a strict improvement everyone should pursue, with no cost-benefit framing.
- Treating GraphQL as a universal REST replacement rather than understanding its specific aggregation-layer value proposition.
- Not knowing header-based API versioning breaks caching without a correctly configured `Vary` header.
- Not knowing cursor pagination gives up arbitrary page-jump capability as a real, honest tradeoff.
- Confusing RFC 7807 and RFC 9457 as unrelated standards rather than superseding versions of the same Problem Details shape.

---

## Cheat card

```
PROTOCOL CHOICE (2026, non-overlapping niches):
  Public API -> REST (CDN caching, curl-debuggable, universal tooling)
  Aggregation/diverse clients -> GraphQL (mobile vs web shape from 1 backend)
  Internal service-to-service -> gRPC (T11-go-services: binary, HTTP/2, auto
    deadline propagation)
  TS full-stack, same team both ends -> tRPC (eliminates API boundary
    entirely, ~15% of TS job postings and climbing)

RICHARDSON MATURITY: L0 swamp of POX (everything's POST) -> L1 real
  resource URLs -> L2 correct verbs+status codes (MOST production APIs
  stop HERE, deliberately) -> L3 HATEOAS (rare — cost rarely justifies
  dynamic-discovery benefit for a typical hardcoded-client population)

PAGINATION: OFFSET degrades — DB scans+discards N rows every time, cost
  grows with depth, NOT indexable. CURSOR (WHERE col > :last ORDER BY col
  LIMIT N) hits an INDEX, near-constant time at ANY depth. MANDATORY for
  large/frequently-updated data (Stripe/Slack/GitHub pattern). Tradeoff
  given up: no arbitrary page-jump, no cheap total-page-count.

ERROR CONTRACT: RFC 9457 (supersedes RFC 7807, Aug 2023) Problem Details:
  type, title, status, detail, instance + extension fields. ONE shape,
  every endpoint — client error-handling written ONCE, generically.

SSE vs WEBSOCKET: SSE = 95% default (unidirectional, TEXT, BUILT-IN
  reconnect via Last-Event-ID header, CDN-transparent — Cloudflare/Fastly/
  CloudFront handle it natively). WebSocket = 5% (genuine bidirectional +
  low-latency + binary need: voice/video signaling, collab cursors,
  gaming) — no built-in reconnect, CDN support special-cased/inconsistent.

VERSIONING: no universal answer, depends on consumers/caching/cadence.
  URL PATH (/v1/x): safest default, CDN-caches with ZERO extra config.
  HEADER (Accept-Version): stable URLs, BREAKS caching unless Vary set
    correctly at EVERY layer in the chain (CDN, proxy, browser).
  DATE-BASED (Stripe/GitHub real pattern): fast-evolving platforms,
    fine-grained changes, client pins to a specific date/snapshot.

422 vs 400 (T11-fastapi-deep): 422 = parses fine, fails semantic
  validation. 400 = structurally malformed. Same Problem Details shape
  applies to both.
```

## Sources

- [REST vs GraphQL vs gRPC vs tRPC: API Architecture 2026 — APIScout](https://apiscout.dev/guides/rest-vs-graphql-vs-grpc-vs-trpc-2026) — accessed 2026-08-03
- [Richardson Maturity Model — REST API Tutorial](https://restfulapi.net/richardson-maturity-model/) — accessed 2026-08-03
- [API Pagination Best Practices: Cursor, Offset & Keyset Explained (2026) — getknit.dev](https://www.getknit.dev/blog/api-pagination-best-practices) — accessed 2026-08-03
- [The Offset Massacre — Why Cursor Pagination is Mandatory (2026) — DEV Community](https://dev.to/kaushikcoderpy/the-offset-massacre-why-cursor-pagination-is-mandatory-2026-p4i) — accessed 2026-08-03
- [An introduction to RFC 7807 | Representing Problem Details in HTTP APIs — Axway](https://blog.axway.com/learning-center/apis/api-design/introduction-to-rfc-7807) — accessed 2026-08-03
- [Charge your APIs Volume 19: RFC 7807 and RFC 9457 — codecentric](https://www.codecentric.de/en/knowledge-hub/blog/charge-your-apis-volume-19-understanding-problem-details-for-http-apis-a-deep-dive-into-rfc-7807-and-rfc-9457) — accessed 2026-08-03
- [WebSockets vs Server-Sent Events: Key differences and which to use in 2026 — Ably](https://ably.com/blog/websockets-vs-sse) — accessed 2026-08-03
- [Server-Sent Events Beat WebSockets for 95% of Real-Time Apps — DEV Community](https://dev.to/polliog/server-sent-events-beat-websockets-for-95-of-real-time-apps-heres-why-a4l) — accessed 2026-08-03
- [API Versioning Strategies and Their Hidden Long-Term Costs — Java Code Geeks](https://www.javacodegeeks.com/2026/07/api-versioning-strategies-and-their-hidden-long-term-costs.html) — accessed 2026-08-03

## Changelog
- 2026-08-03 — created
