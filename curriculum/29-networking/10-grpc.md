# gRPC Deep: Protobuf, HTTP/2 Framing, 4 RPC Types, Deadlines, Interceptors, Streaming

> **Track:** T29 Networking & Protocols · **Time:** 3h · **Prereqs:** T29-http-versions, T29-http-semantics · **Updated:** 2026-07-26
> **Module id:** `T29-grpc` · **Tags:** rpc, critical

## The 30-second version

gRPC is protobuf-encoded messages carried as HTTP/2 streams: each RPC gets its own stream, a HEADERS frame carries metadata, one or more DATA frames carry the binary-encoded request/response, and a trailers frame carries the final status — which is exactly why gRPC requires HTTP/2 and cannot run on HTTP/1.1. Protobuf's tag-length-value wire format is smaller and faster to parse than JSON because it skips key names and text-number parsing entirely, and its field-number-based schema evolution lets services add fields without breaking old clients as long as you never reuse or renumber a field. The four RPC shapes (unary, server-streaming, client-streaming, bidirectional) map directly onto what a single HTTP/2 stream can already do — one, many, or interleaved DATA frames in either direction. Deadlines are absolute and propagate automatically through a call chain, unlike a plain per-hop timeout, which is why gRPC is the stronger choice for internal service-to-service calls with strict schemas and streaming, and REST/JSON remains the stronger choice for public APIs where curl-ability, browser support without a proxy, and standard HTTP caching matter more than raw efficiency.

## Why this gets asked

Because "gRPC uses protobuf and is faster" is the answer of someone who's read a comparison blog post, and "here's the actual wire format, here's why deadlines aren't the same as timeouts, here's the honest tradeoff against REST" is the answer of someone who's debugged a gRPC deadline propagation bug in production or migrated a service off REST and found out the hard way that curl doesn't work anymore. The interviewer is checking whether you understand gRPC as HTTP/2 plus a schema, not as a magic faster-REST replacement, and whether you can name the real cost (loss of human debuggability, browser incompatibility) rather than only the benefits.

---

## Lineage: past → present → future

**What came before.** Google's internal RPC framework, Stubby, had run since roughly 2001 on top of a proprietary transport and an early version of what became Protocol Buffers, but it was internal-only and undocumented externally. Meanwhile the industry standardized on SOAP/XML (verbose, self-describing, heavyweight parsing) and then REST/JSON (human-readable, cacheable via standard HTTP semantics, universally supported, but with no enforced schema, no native streaming, and text-based encoding that's slow to parse at scale and wasteful on the wire — repeated field names in every JSON object, no compact binary types). The pain that pushed Google to open-source gRPC (2015, alongside protobuf which had been open-sourced earlier in 2008) was internal: thousands of services calling each other needed strict, versioned schemas, low serialization overhead at Google's request volume, and native support for streaming RPCs, none of which JSON/REST gave for free.

**Where it stands now.** gRPC is the default choice for internal service-to-service RPC at most companies running polyglot microservices at scale (its codegen produces idiomatic clients/servers in a dozen-plus languages from one `.proto` file), and it underpins large swaths of Kubernetes' own control plane and CNCF projects. The genuine, current disagreement is scope: some teams push gRPC all the way to browser clients via gRPC-Web (a JS-compatible subset requiring a translating proxy like Envoy, since browsers can't do true HTTP/2 trailers-based framing directly), while others draw a hard line — gRPC for internal, REST/JSON (or GraphQL) for anything a browser or third-party developer touches directly. The REST-for-public-APIs camp argues curl-ability and standard HTTP caching are non-negotiable for external developer experience; the gRPC-everywhere camp argues maintaining two API styles is real ongoing cost. Both positions are actually deployed at scale, and the honest answer is "it depends whether your public consumers need to read what came back with their own eyes."

**Where it's heading.** Two threads worth flagging with different confidence. First, **gRPC's error/status model (`google.rpc.Status`, structured error details) is increasingly the reference design even non-gRPC APIs borrow from** — REST APIs adopting `application/problem+json` (RFC 9457) are converging toward the same idea of structured, typed error payloads gRPC had from day one; this is a real, observable trend, not speculation. Second, **gRPC over HTTP/3/QUIC** is an active area of work (per-stream loss isolation would help gRPC exactly the way it helps any multiplexed HTTP/2 workload), but as of mid-2026 it isn't the mainstream deployed transport for gRPC in production internal traffic — treat HTTP/3-backed gRPC as a direction of travel, not something to claim is already standard.

---

## Mental model

```
one gRPC call  =  one HTTP/2 stream

  client                                              server
    │  HEADERS  (:method POST, :path /pkg.Svc/Method,      │
    │           grpc-timeout, content-type: application/    │
    │           grpc+proto, custom metadata)                │
    ├───────────────────────────────────────────────────►   │
    │  DATA  (length-prefixed protobuf-encoded request)      │
    ├───────────────────────────────────────────────────►   │
    │                                                        │
    │  DATA  (length-prefixed protobuf-encoded response(s))  │
    │  ◄───────────────────────────────────────────────────┤ │
    │  TRAILERS  (grpc-status, grpc-message)                 │
    │  ◄───────────────────────────────────────────────────┤ │

  unary:              1 request DATA frame,  1 response DATA frame
  server-streaming:   1 request DATA frame,  N response DATA frames over time
  client-streaming:   N request DATA frames, 1 response DATA frame at the end
  bidi-streaming:     N and M DATA frames interleaved, either side, independently
```

The one fact that answers half the follow-ups: **the final status is a trailer, not a leading header**, because gRPC doesn't know the outcome until the handler finishes — this is only possible because HTTP/2 supports trailing headers after the body, which HTTP/1.1 does not support in any widely-implemented way. That's the mechanical reason gRPC requires HTTP/2.

---

## How it actually works

### Protobuf wire format

Every field is encoded as a **tag** followed by a **value**. The tag is a single varint combining the field number and wire type: `tag = (field_number << 3) | wire_type`. Wire types: `0` = varint (int32/int64/bool/enum), `1` = 64-bit fixed, `2` = length-delimited (string/bytes/embedded message/repeated packed), `5` = 32-bit fixed.

Worked example — encoding `{ field 1 (int32) = 150 }`:
- Tag byte: field 1, wire type 0 (varint) → `(1 << 3) | 0 = 0x08`.
- Value 150 as varint: 150 in binary is `1001 0110`. Varints are little-endian, 7 payload bits per byte, MSB=1 means "more bytes follow." 150 fits in 8 bits, which needs 2 varint bytes: low 7 bits `001 0110` with continuation bit set → `0x96`; remaining bits `1` → `0x01`.
- Full encoding: `08 96 01` — 3 bytes total, versus `{"field1":150}` at 14+ bytes in JSON, and no runtime string parsing of the number.

This is *why* protobuf is smaller and faster to parse: no field names on the wire (just small integer tags), no text-to-number parsing, and length-delimited fields let the parser skip unknown/unrecognized bytes entirely without understanding them — which is also the mechanism that makes forward-compatible schema evolution possible.

**Schema evolution rules** (know these cold, this is the most commonly tested part):
- **Safe:** adding a new field with a new field number (old clients simply don't see it; new clients see a default if an old server doesn't send it). Removing a field, as long as its number is reserved (`reserved 4;`) so it's never reused. Renaming a field (the wire format only cares about the number, not the name).
- **Breaking:** reusing a field number for a different field (an old message serialized with the old meaning gets deserialized with the new meaning — silent data corruption, not a crash, which is what makes it dangerous). Changing a field's number. Changing a field's wire-incompatible type (e.g., `int32` to `string` — wire type 0 vs wire type 2, the receiver misparses bytes). Changing `optional` to `required` in proto2 (proto3 removed `required` entirely for exactly this reason).

### Mapping onto HTTP/2 framing

A gRPC call is one HTTP/2 stream: the request path is `POST /package.Service/Method`, `content-type: application/grpc+proto` (or `+json` for the JSON codec, rarely used), and gRPC-specific metadata (`grpc-timeout`, custom key-value pairs) rides in HTTP/2 HEADERS alongside standard HTTP headers. The protobuf-encoded message body is sent as DATA frames, each individual gRPC message prefixed with a 5-byte header (1 byte compression flag + 4 byte big-endian length) so the receiver knows where one message ends and the next begins within a stream that may carry many messages (streaming RPCs). The final outcome — `grpc-status` (an integer status code) and `grpc-message` (human-readable detail) — is sent as HTTP/2 **trailers**, frames that arrive after the body and are only possible because HTTP/2 supports trailing headers as a first-class frame type. HTTP/1.1 has no standardized, universally-supported trailers mechanism, which is the concrete, mechanical reason gRPC cannot run on HTTP/1.1.

### The four RPC types

- **Unary** — one request, one response. The default; used for anything that's naturally a single call-and-return (fetch a record, execute a command).
- **Server-streaming** — one request, a stream of responses. Used for a query that returns a large or unbounded result set the client wants to consume incrementally (log tailing, a large paginated result streamed rather than paged, live price updates for one subscribed instrument).
- **Client-streaming** — a stream of requests, one final response. Used when the client is uploading a sequence of chunks and only cares about a final acknowledgment (chunked file upload, streaming telemetry batches that get one aggregated ack).
- **Bidirectional streaming** — both sides stream independently and concurrently, not necessarily in lockstep. Used for genuinely interactive protocols (a chat-like exchange, a live translation service consuming audio and emitting text concurrently, coordinating agent tool-call turns over a persistent channel).

### Deadlines and cancellation propagation

A gRPC client sets an **absolute deadline** — a timestamp, not a duration — and it's propagated automatically as metadata to every downstream call made *within* that RPC's context, so if service A calls B calls C, C inherits A's original deadline (minus whatever time has already elapsed), not a fresh independent timeout. This is structurally different from a plain per-call timeout: if A sets a 3s timeout on its call to B, and B independently sets its own fresh 3s timeout calling C, a chain of slow-but-under-timeout hops can blow well past the deadline the *original caller* actually cared about, because none of the timeouts know about each other. gRPC deadlines fix this by threading the same deadline through the whole call tree via context propagation.

```go
// untested sketch — Go, illustrating deadline propagation
func handlerA(ctx context.Context, req *pb.Request) (*pb.Response, error) {
    // ctx already carries the deadline the original client set
    ctx, cancel := context.WithTimeout(ctx, 5*time.Second) // can only shrink, not extend
    defer cancel()
    resp, err := clientB.CallB(ctx, req)  // deadline auto-propagated as grpc-timeout metadata
    if err != nil {
        if status.Code(err) == codes.DeadlineExceeded {
            return nil, status.Error(codes.DeadlineExceeded, "downstream B exceeded deadline")
        }
        return nil, err
    }
    return resp, nil
}
```

```python
# untested sketch — Python, cancellation propagation
async def handler_a(request, context):
    # context.cancel() propagates to any downstream async calls made using
    # this same context/deadline; cancelling the parent cancels all children
    deadline = context.time_remaining()  # seconds left on the inherited deadline
    if deadline is not None and deadline < 0.5:
        context.abort(grpc.StatusCode.DEADLINE_EXCEEDED, "insufficient budget to call B")
    resp = await stub_b.CallB(request, timeout=deadline)
    return resp
```

Cancelling the parent context cancels every child call derived from it — if the original client hangs up or times out, every in-flight downstream RPC gets cancelled rather than continuing to do work nobody's waiting for anymore, which is exactly the server-side-work-after-client-gave-up problem that plain HTTP timeouts don't solve for free (see T21-resilience-catalogue).

### Interceptors

Interceptors are gRPC's middleware: client-side interceptors wrap every outgoing call (inject auth tokens, add tracing spans, log request/response); server-side interceptors wrap every incoming call (validate auth, rate-limit, record metrics). They compose in a chain, analogous to HTTP middleware/decorators, and are the standard place to put cross-cutting concerns rather than duplicating them in every service method.

```python
# untested sketch — server-side auth interceptor
class AuthInterceptor(grpc.ServerInterceptor):
    def intercept_service(self, continuation, handler_call_details):
        metadata = dict(handler_call_details.invocation_metadata)
        token = metadata.get("authorization")
        if not token or not verify(token):
            def deny(request, context):
                context.abort(grpc.StatusCode.UNAUTHENTICATED, "invalid or missing token")
            return grpc.unary_unary_rpc_method_handler(deny)
        return continuation(handler_call_details)
```

### Status codes and rich errors

gRPC has a fixed, small set of status codes (`OK`, `CANCELLED`, `UNKNOWN`, `INVALID_ARGUMENT`, `DEADLINE_EXCEEDED`, `NOT_FOUND`, `ALREADY_EXISTS`, `PERMISSION_DENIED`, `RESOURCE_EXHAUSTED`, `FAILED_PRECONDITION`, `ABORTED`, `OUT_OF_RANGE`, `UNIMPLEMENTED`, `INTERNAL`, `UNAVAILABLE`, `DATA_LOSS`, `UNAUTHENTICATED` — 17 total including OK) versus HTTP's ~60 status codes, most of which are rarely used and none of which are semantically constrained the way gRPC's are. This is deliberately richer and more structured than a bare HTTP status for programmatic handling: `UNAVAILABLE` unambiguously means "retry might help, the server or a dependency was unreachable," `FAILED_PRECONDITION` unambiguously means "don't retry until the client fixes state," in a way that HTTP's overloaded 400s/500s don't consistently distinguish across different APIs. For anything beyond the code and a message string, `google.rpc.Status` carries structured `details` (a list of typed protobuf messages — e.g., `BadRequest` with per-field violations, `RetryInfo` with a suggested backoff) so a client can programmatically branch on rich error content instead of parsing a human-readable string.

---

## Build it from scratch

Minimal unary gRPC service — the shape you should be able to sketch cold:

```protobuf
// untested sketch
syntax = "proto3";
package demo;

service Greeter {
  rpc SayHello (HelloRequest) returns (HelloReply);
  rpc SayHelloStream (HelloRequest) returns (stream HelloReply);
}

message HelloRequest {
  string name = 1;
}

message HelloReply {
  string message = 1;
}
```

```python
# untested sketch — server
class Greeter(demo_pb2_grpc.GreeterServicer):
    def SayHello(self, request, context):
        if not request.name:
            context.abort(grpc.StatusCode.INVALID_ARGUMENT, "name is required")
        return demo_pb2.HelloReply(message=f"Hello, {request.name}")

    def SayHelloStream(self, request, context):
        for i in range(3):
            yield demo_pb2.HelloReply(message=f"Hello #{i}, {request.name}")

server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
demo_pb2_grpc.add_GreeterServicer_to_server(Greeter(), server)
server.add_insecure_port("[::]:50051")
server.start()
```

```python
# untested sketch — client, with a deadline
with grpc.insecure_channel("localhost:50051") as channel:
    stub = demo_pb2_grpc.GreeterStub(channel)
    try:
        resp = stub.SayHello(demo_pb2.HelloRequest(name="Hari"), timeout=2.0)
    except grpc.RpcError as e:
        print(e.code(), e.details())  # e.g. DEADLINE_EXCEEDED, "Deadline Exceeded"
```

The codegen step (`protoc` with the gRPC plugin, or `buf generate`) is what turns the `.proto` into typed client stubs and server base classes in whatever target language — this is the "polyglot codegen" advantage cited for gRPC: one schema, idiomatic generated code in a dozen-plus languages, versus hand-maintaining OpenAPI-generated clients that vary in quality per language.

---

## How it's done in production

Production gRPC deployments layer on top of the raw framework: **load balancing** (client-side, via a resolver + pick-first/round-robin policy, since a single long-lived HTTP/2 connection to one backend defeats simple L4 load balancing — this is a real operational gotcha, see the failure-mode table), **health checking** (the standard `grpc.health.v1.Health` service every backend should implement so infra can distinguish "process is up" from "ready to serve"), **reflection** (`grpc.reflection.v1.ServerReflection`, letting tools like `grpcurl` introspect a running service's schema without needing the `.proto` file locally — the closest thing gRPC has to curl-ability), and **service mesh integration** (Envoy/Istio natively understand gRPC framing for routing, retries, and observability at the proxy layer).

| Symptom | Cause | Fix |
|---|---|---|
| One backend pod gets all the traffic, others sit idle | gRPC keeps a single long-lived HTTP/2 connection per client-server pair; a plain L4/TCP load balancer only balances *new connections*, not requests within one | Client-side load balancing (resolver + LB policy) or an L7-aware proxy (Envoy) that balances individual streams, not connections |
| Deadline set on the outer call, but an inner downstream call still runs long after the client gave up | Deadline wasn't propagated — a library or manual code path created a fresh, unrelated context instead of deriving from the inbound one | Always derive downstream call contexts from the inbound request's context; never create an unrelated fresh deadline for a downstream hop |
| Old client suddenly fails deserializing a message from an updated server | A field number was reused or its type was changed incompatibly | Never reuse/renumber field numbers; use `reserved` for removed fields; wire-incompatible type changes require a new field number, not an in-place change |
| Client gets `UNAVAILABLE` in a burst right after a rolling deploy | Server closed connections during pod termination without a grace period; client's connection pool hadn't detected the backend was gone yet | Graceful server shutdown (drain in-flight RPCs, reject new ones cleanly) plus client-side retry with backoff on `UNAVAILABLE` |
| Browser JS client can't call the gRPC service at all | Browsers can't do real HTTP/2 trailers-based framing the way gRPC needs | Use gRPC-Web with a translating proxy (Envoy), or don't put gRPC directly in front of a browser client at all |
| A public third-party integration partner can't easily test your API | No curl-ability, no self-describing human-readable payloads, no standard HTTP caching | This is the sign gRPC was the wrong choice for this surface; expose a REST/JSON facade for external consumers instead |

---

## Tradeoffs & when NOT to use it

- **Public APIs consumed by third parties or browsers directly** are the clearest "don't." No native browser support (gRPC-Web needs a proxy), no `curl <url>` debuggability for an external developer, no benefit from standard HTTP caching semantics (`Cache-Control`, ETags) that REST gets for free. If your consumers just want to read a JSON response in a browser dev tools tab, REST wins on developer experience, full stop.
- **Internal service-to-service calls with strict schemas, streaming needs, and polyglot teams** are where gRPC clearly wins: compact binary encoding at scale, native bidirectional streaming, enforced contracts via `.proto` instead of a loosely-versioned JSON shape, and generated clients in every language your services are written in.
- **Don't adopt gRPC just for "it's faster."** For most internal APIs at moderate request volume, the serialization difference is not the bottleneck — network and downstream processing dominate. The stronger, more honest justification is schema enforcement and streaming, not raw throughput, unless you've actually measured serialization cost as your bottleneck.
- **Debuggability is a real, ongoing cost.** Without `grpcurl` and reflection enabled, a gRPC service is opaque to ad-hoc inspection in a way a REST endpoint never is; budget for reflection support and observability tooling as part of the adoption cost, not an afterthought.
- **Load balancing is not free with gRPC.** Because connections are long-lived and multiplexed, naive L4 load balancing silently concentrates traffic on whichever backend happened to get the connection first — this is a recurring, underappreciated operational surprise for teams migrating from REST's connection-per-request-ish behavior.

---

## Interview questions

### Q1 — Why does gRPC require HTTP/2 and can't run on HTTP/1.1?
**Testing:** whether you understand the framing dependency, not just "it's a rule."
**Answer:** gRPC needs trailing headers to carry the final `grpc-status` after the body, and it needs true multiplexed independent streams for concurrent RPCs on one connection plus native bidirectional streaming — both are HTTP/2-native (trailers frame, independent stream IDs) and neither is reliably available on HTTP/1.1.
**Follow-up trap:** *"Could you fake trailers on HTTP/1.1 by putting status in the JSON body instead?"* — you could, and some early RPC-over-HTTP/1.1 systems did exactly that, but you lose true concurrent multiplexing on one connection and native streaming; you'd be reinventing a worse version of what HTTP/2 already gives you for free.

### Q2 — Walk me through the protobuf wire format for a single int32 field.
**Answer:** Tag byte = `(field_number << 3) | wire_type`; for field 1, wire type 0 (varint), that's `0x08`. The value is varint-encoded: 7 bits of payload per byte, MSB set means more bytes follow, little-endian ordering of the 7-bit groups. Value 150 encodes as two bytes, `0x96 0x01`, giving a 3-byte total encoding `08 96 01`.
**Follow-up trap:** *"Why does length-delimited (wire type 2) encoding matter for schema evolution?"* — it lets a parser skip over a field it doesn't recognize (unknown field number) by reading the length prefix and jumping past the bytes, without needing to understand the field's meaning — this is exactly what lets an old client safely ignore new fields a newer server added.

### Q3 — Give me a change to a `.proto` file that's safe, and one that silently corrupts data.
**Answer:** Safe: adding `string email = 5;` to a message that previously only had fields 1-4 — old clients ignore it, new clients see empty string as default if talking to an old server. Silently corrupting: reusing field number 3 for a completely different field after it was previously used for something else and removed — an old serialized message (or a client still on the old schema) gets deserialized with the new field's meaning applied to old bytes, producing wrong data with no error thrown.
**Follow-up trap:** *"Why no error thrown — wouldn't that show up in tests?"* — protobuf deserialization doesn't validate that a field number "means" what you currently think it means; it just reads bytes at that tag. Nothing crashes; you get a subtly wrong value that behaves like valid data, which is exactly why this is more dangerous than a type mismatch that would at least throw a parse error.

### Q4 — What's the difference between a gRPC deadline and a plain per-call timeout?
**Answer:** A deadline is an absolute point in time, set once by the originating client and propagated automatically as metadata through every downstream call derived from that request's context. A per-call timeout is independently set at each hop with no knowledge of what came before — so A→B→C with each hop setting its own fresh 3s timeout can blow past the 3s the *original* caller actually wanted, because none of the timeouts share information.
**Follow-up trap:** *"Does propagation happen automatically, or do you have to wire it yourself?"* — it's automatic *if* you correctly derive the downstream call's context from the inbound request's context; if a code path constructs a brand-new context for the downstream call (common when people aren't careful about context threading), propagation silently breaks and you're back to independent, uncoordinated timeouts.

### Q5 — Explain cancellation propagation with a concrete failure you'd watch for.
**Answer:** Cancelling the parent context (client hangs up, or the deadline is exceeded) cancels every child call derived from that context, so downstream services stop doing work nobody's waiting on. The failure to watch for: a downstream call made using a fresh/unrelated context instead of a derived one keeps running to completion even after the parent is long gone — silently wasting resources and, for a write, potentially completing a side effect the caller thinks never happened.
**Follow-up trap:** *"How would you actually detect this in a running system?"* — trace the request end-to-end and check whether a downstream span's lifetime outlives the parent span's cancellation timestamp; if it does, that's a context-propagation bug, and it's exactly the kind of thing that's invisible without distributed tracing.

### Q6 — Name the four RPC types and a real use case for each.
**Answer:** Unary — fetch-a-record style calls. Server-streaming — a client subscribing to live updates or consuming a large result incrementally (log tail, price feed). Client-streaming — uploading a sequence of chunks with one final ack (chunked upload, batched telemetry). Bidirectional streaming — genuinely interactive, independently-paced exchange in both directions (chat-like protocols, live audio-to-text, coordinated multi-turn tool calls).
**Follow-up trap:** *"Could you build client-streaming behavior with plain unary calls plus a session ID?"* — yes, and people do, but you lose the single-connection efficiency and in-order guarantees within the stream, and you now own session/state management yourself instead of getting it from the RPC shape.

### Q7 — Why is `UNAVAILABLE` different from `INTERNAL`, and why does that distinction matter operationally?
**Answer:** `UNAVAILABLE` signals the server or a dependency was transiently unreachable — safe and often correct to retry with backoff. `INTERNAL` signals the server hit an unexpected internal error/invariant violation — retrying blindly is far less likely to help and may just repeat whatever triggered the bug. A retry policy that treats every non-OK code the same either retries things it shouldn't (wasting resources on a bug that won't self-resolve) or fails to retry things it safely could.
**Follow-up trap:** *"Would you ever retry on INTERNAL?"* — rarely, and only if you've specifically identified the internal error as a known-transient class (e.g., a specific race condition your team has documented as safe to retry); as a blanket policy, no.

### Q8 — What does `google.rpc.Status` give you that a bare gRPC status code doesn't?
**Answer:** Structured, typed error `details` — e.g., a `BadRequest` message listing exactly which fields violated validation, or a `RetryInfo` message suggesting a specific backoff duration — so a client can programmatically branch on rich, typed error content instead of pattern-matching a human-readable message string.
**Follow-up trap:** *"Isn't a detailed message string enough?"* — no, because parsing a human-readable string for programmatic decisions is brittle across message-text changes/localization; typed `details` messages are a stable, versioned contract the client can rely on the same way it relies on the rest of the schema.

### Q9 — What's an interceptor, and where would you put auth?
**Answer:** Middleware around every RPC — client-side interceptors wrap outgoing calls (inject auth, tracing, logging), server-side interceptors wrap incoming calls (validate auth, rate-limit, record metrics), composed in a chain. Auth validation belongs in a server-side interceptor, not duplicated in every service method, so a new method automatically gets the same auth check without anyone having to remember to add it.
**Follow-up trap:** *"What happens if two interceptors both try to set the same outgoing metadata key?"* — order-dependent and a real bug source; the last interceptor in the chain to touch it wins (or it errors, depending on the implementation's metadata semantics), which is why interceptor ordering should be explicit and documented, not incidental.

### Q10 — When would you choose REST over gRPC for a new service?
**Testing:** the honest tradeoff, not gRPC boosterism.
**Answer:** When the consumers are browsers or third-party developers who need to `curl` the endpoint, read a human-readable JSON response, and benefit from standard HTTP caching (`ETag`, `Cache-Control`) — none of which gRPC gives you without extra proxying (gRPC-Web) and none of which typed binary framing improves for a consumer who just wants to read the response. Public developer-facing APIs are the clean case for REST.
**Follow-up trap:** *"Your team wants one API style everywhere to reduce maintenance. Do you agree?"* — no, and say so: maintaining two styles (gRPC internal, REST/JSON at the public edge, often via a gateway that translates) is a real, deliberate, and common cost that buys a materially better external developer experience; collapsing to one style for internal simplicity trades away that experience for an engineering convenience, and that's a product decision, not just an engineering one.

### Q11 — A rolling deploy causes a burst of `UNAVAILABLE` errors from clients. Diagnose.
**Answer:** Likely the server closed connections during pod termination without draining in-flight RPCs or rejecting new ones gracefully first, and/or the client's connection pool hadn't yet detected the backend was gone (stale connection in the pool, or client-side load balancer hadn't re-resolved). Fix: graceful server shutdown (stop accepting new streams, finish in-flight ones, then close), health-check-aware client load balancing, and client-side retry with backoff specifically on `UNAVAILABLE`.
**Follow-up trap:** *"Why does one backend pod get flooded with traffic right after this incident?"* — a separate but related gotcha: gRPC's long-lived HTTP/2 connections mean a plain L4 load balancer only balances new *connections*, not individual requests, so if clients reconnected in a burst and picked unevenly, one pod can end up overloaded until connections naturally rebalance or you add L7-aware (stream-level) load balancing.

### Q12 — How would you version a gRPC API without breaking existing clients?
**Answer:** Prefer additive changes within the same message (new fields with new numbers) over introducing a new service version whenever possible, since that's the whole point of protobuf's evolution rules. When a genuinely breaking change is unavoidable (removing a field's meaning entirely, changing RPC semantics), version at the package/service level (`package myapi.v2;`, a new `ServiceV2`) rather than mutating an existing field's contract in place, and run both versions concurrently until old clients migrate.
**Follow-up trap:** *"A field needs to change type from `int32` to `string`. What do you do?"* — you cannot change the existing field's type in place (wire-incompatible, silently corrupts old data as discussed above); add a brand-new field with a new number and the new type, deprecate the old one, and migrate readers/writers before eventually removing (and reserving) the old field number.

---

## Red flags that fail you

- Saying gRPC is "just faster JSON" with no mention of the actual wire format or why it's smaller.
- Not knowing gRPC requires HTTP/2, or not being able to say why (trailers + true multiplexing/streaming).
- Describing a gRPC deadline as "just a timeout."
- Not knowing that reusing a protobuf field number is a silent-corruption bug, not a compile error.
- Recommending gRPC for a public, browser-facing API with no mention of gRPC-Web's proxy requirement or the loss of curl-ability.
- Treating all non-OK gRPC status codes as equally retryable.

---

## Cheat card

```
WIRE FORMAT   tag = (field_number << 3) | wire_type
              wire types: 0=varint 1=64-bit 2=length-delimited(str/bytes/msg) 5=32-bit
              varint: 7 bits/byte, MSB=continuation flag, little-endian groups
              e.g. field1=150 -> tag 0x08, value 0x96 0x01 -> "08 96 01" (3 bytes)

SCHEMA EVOLUTION
  SAFE:     add new field (new number) · remove field + `reserved N` · rename field
  BREAKING: reuse a field number (SILENT corruption, no error) · change number
            · change to a wire-incompatible type

HTTP/2 MAPPING   1 RPC = 1 stream
  HEADERS  -> :path /pkg.Service/Method, grpc-timeout, metadata
  DATA     -> length-prefixed (5-byte header) protobuf message(s)
  TRAILERS -> grpc-status + grpc-message  <- ONLY possible on HTTP/2; why gRPC
                                             can't run on HTTP/1.1

4 RPC TYPES   unary · server-streaming · client-streaming · bidi-streaming
              (1 req/1 resp · 1/N · N/1 · N/M interleaved)

DEADLINES     absolute timestamp, auto-propagated through call chain via context
              != per-hop timeout (which doesn't know about earlier hops)
              cancel parent context -> cancels all derived children

STATUS CODES  17 total: OK, CANCELLED, UNKNOWN, INVALID_ARGUMENT, DEADLINE_EXCEEDED,
              NOT_FOUND, ALREADY_EXISTS, PERMISSION_DENIED, RESOURCE_EXHAUSTED,
              FAILED_PRECONDITION, ABORTED, OUT_OF_RANGE, UNIMPLEMENTED, INTERNAL,
              UNAVAILABLE, DATA_LOSS, UNAUTHENTICATED
              google.rpc.Status -> typed structured error `details`

GRPC WINS     internal service-to-service, strict schemas, streaming, polyglot codegen
REST WINS     public/3rd-party APIs, browser without proxy, curl-ability, HTTP caching

OPERATIONAL GOTCHA   long-lived HTTP/2 conn -> naive L4 LB balances CONNECTIONS
                     not requests -> use client-side LB or L7-aware proxy
```

## Sources

- [Encoding — Protocol Buffers Documentation](https://protobuf.dev/programming-guides/encoding/) — accessed 2026-07-26
- [Status Codes — gRPC](https://grpc.io/docs/guides/status-codes/) — accessed 2026-07-26
- [gRPC Error Codes Explained — Postman Blog](https://blog.postman.com/grpc-error-codes/) — accessed 2026-07-26
- [How to Return Rich Error Details with gRPC Status Codes](https://oneuptime.com/blog/post/2026-01-08-grpc-status-codes-error-details/view) — accessed 2026-07-26
- [How to Fix 'Deadline Exceeded' Errors in gRPC](https://oneuptime.com/blog/post/2026-01-24-grpc-deadline-exceeded-errors/view) — accessed 2026-07-26
- [API Design for System Design Interviews — Hello Interview](https://www.hellointerview.com/learn/system-design/core-concepts/api-design) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
