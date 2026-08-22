# HTTP Semantics: Why GET vs POST vs PUT vs PATCH, Idempotency, Safety, Caching, Status Codes

> **Track:** T29 Networking & Protocols · **Time:** 2.5h · **Prereqs:** T29-tcp-deep · **Updated:** 2026-07-26
> **Module id:** `T29-http-semantics` · **Tags:** http, critical

## The 30-second version

Safety means no server-side side effects (GET, HEAD, OPTIONS); idempotency means N identical requests leave the server in the same state as 1 (GET, PUT, DELETE, HEAD, OPTIONS qualify, POST and PATCH don't by default). These aren't arbitrary labels — PUT is idempotent because it's defined as a full replace ("this resource now equals exactly this representation"), so repeating it changes nothing; POST is not idempotent because it's defined as "create a new subordinate resource," so repeating it creates a duplicate; PATCH is a partial update, and a partial update applied twice can compound (`increment_counter` twice ≠ once) even though it often happens to be idempotent in practice (`set field X to value Y` twice is fine). This matters mechanically because idempotent methods are safe to retry blindly at the network layer, while POST needs a client-generated idempotency key to be retried safely. Status codes encode who's at fault and whether retrying helps: 4xx means don't retry as-is (client error), 5xx/429 mean maybe retry with backoff (server or rate-limit issue), 401 means "who are you" while 403 means "I know who you are and no," and 307/308 exist specifically to preserve the method and body across a redirect where 301/302 historically got rewritten to GET by browsers. Conditional requests (`If-Match`/`If-None-Match` against an ETag) give you both caching (a 304 skips re-sending the body) and optimistic concurrency (a `PUT` with `If-Match` fails with 412 if someone else wrote first, preventing lost updates).

## Why this gets asked

Because this is the layer every backend engineer touches daily and almost nobody has actually reasoned through. The interviewer has personally shipped or reviewed a "retry-safe" client that blindly retried a POST and double-charged a customer, or watched a mobile client follow a 302 and silently turn a form submission into a GET, dropping the body. They're checking whether you reason from the actual RFC definitions (what does "idempotent" *mean*, not just which verbs get the label) or from a memorized table, because the memorized table breaks the instant someone asks "why is PATCH not idempotent but this specific PATCH endpoint is" — which happens constantly in real API design reviews.

---

## Lineage: past → present → future

**What came before.** HTTP/0.9 (1991) had exactly one method — GET — and no headers, no status codes, no concept of a request/response beyond "ask for a document, get a document." HTTP/1.0 (1996, RFC 1945) added POST and HEAD, status codes, and headers, but left semantics thin and inconsistently implemented across servers — there was no rigorous definition of what a repeated request was allowed to do. The pain: as HTTP grew from serving static documents into a general application protocol (forms, then APIs), engineers needed the protocol itself to specify retry and caching semantics precisely, because the network layer (proxies, browsers, load balancers) needed to know which requests were safe to retry, cache, or replay without understanding the application. HTTP/1.1 (1997, RFC 2068, revised RFC 2616 in 1999) formalized safety and idempotency as first-class properties of each method, plus the conditional-request machinery (`If-Modified-Since`, later ETags), specifically so intermediaries could make retry/caching decisions without knowing what the application did.

**Where it stands now.** The current normative reference is RFC 9110 (HTTP Semantics, 2022), which consolidated and clarified RFC 7231's older method/status/caching definitions into one document shared across HTTP/1.1, /2, and /3. The verb-safety-idempotency model is settled and universally implemented; the live disagreement is almost entirely at the API-design layer, not the protocol layer: whether PATCH should be JSON Patch (RFC 6902, a sequence of explicit operations, arguably more idempotent in practice since each op is well-defined) versus JSON Merge Patch (RFC 7396, simpler but semantically fuzzier about arrays and deletions) versus a bespoke partial-update body — and whether POST-based "create" endpoints should mandate a client-supplied idempotency key as a first-class API contract (Stripe popularized this pattern; it's now close to expected for any payment-adjacent POST endpoint) versus leaving retry safety to the client's judgment. What's actually deployed: idempotency keys are now standard practice at any serious payments or order-creation API; conditional requests for caching are ubiquitous (every CDN relies on them); conditional requests for optimistic concurrency (ETags on PUT/PATCH) are correctly understood and used far less often than they should be, and this exact gap is a frequent code-review finding.

**Where it's heading.** Nothing structural is changing in HTTP semantics itself — RFC 9110 is stable and the model is mature. The more interesting direction is at the client/framework layer: HTTP client libraries and API gateways are increasingly building idempotency-key handling and retry-classification (which status codes are retryable) into their defaults rather than leaving it to each application team, because getting it wrong is a well-understood, recurring class of production incident. Treat "the framework should just handle retry safety for me" as directional, not yet universal — plenty of widely-used HTTP clients still retry blindly by default on connection errors regardless of method.

---

## Mental model

```
                    SAFE (no side effects)
                    ┌─────────────────────┐
                    │  GET  HEAD  OPTIONS  │
                    └──────────┬──────────┘
                               │
              IDEMPOTENT (N times state = 1 time)
    ┌──────────────────────────┴──────────────────────────┐
    │  GET  HEAD  OPTIONS  │  PUT   DELETE                 │
    └──────────────────────┴───────────────────────────────┘
                                          │
                            NOT IDEMPOTENT (retry needs a key)
                            ┌─────────────┴──────────────┐
                            │   POST   │   PATCH*         │
                            └──────────┴──────────────────┘
    * PATCH is not idempotent BY DEFAULT, but a specific PATCH endpoint can be
      idempotent by design (e.g. "set status to X") — it depends on the operation,
      not the verb. That's the trap question.

RETRY RULE:  safe+idempotent → retry blindly.  POST/unsafe-PATCH → need an
             idempotency key, or don't auto-retry.
```

The one thing to internalize: **safety and idempotency are about the definition of the operation, not an accident of implementation.** PUT is idempotent because the spec defines it as "the target resource now has this exact representation" — a statement about desired end state, not a delta — so applying that statement twice is identical to applying it once by construction. POST is defined as "process this according to the resource's own semantics, typically creating something new" — the spec never says what happens on repeat, and "create a new subordinate resource" repeated twice naturally creates two.

---

## How it actually works

### Safety vs idempotency vs cacheability — three different axes

| Property | Definition | Verbs that qualify |
|---|---|---|
| **Safe** | The request is defined to have no intended side effects on server state; it's read-only from the spec's point of view | GET, HEAD, OPTIONS, TRACE |
| **Idempotent** | N identical requests produce the same server state as 1 (the *response* can legitimately differ — a repeat DELETE might return 404 instead of 204, that's fine, the resource *state* is still "gone" either way) | GET, HEAD, OPTIONS, PUT, DELETE, TRACE |
| **Cacheable** | A response to this method may be stored and reused for a later request without re-contacting the origin, subject to cache-control directives | GET (default cacheable), HEAD, POST (cacheable only with explicit freshness info, rarely used in practice) |

Note the asymmetry: safety implies idempotency (nothing changes, so repeating changes nothing), but idempotency doesn't imply safety (PUT and DELETE both change state, just to the same end state regardless of repeat count).

### Why each verb has the property it does — the reasoning, not the table

- **GET is safe** because it's specified purely as "retrieve a representation of the target resource" — no request body is meant to change server state, and any server that mutates state on a GET is violating the spec's contract, which is exactly why "GET requests that log you out" or "GET that deletes a record" are a well-known anti-pattern that breaks prefetching, crawlers, and browser back/forward behavior.
- **PUT is idempotent** because it's defined as "store this representation *as* the target resource," a full replacement, not a delta. Sending the identical PUT body twice means "the resource is exactly this" stated twice — the second statement is a no-op relative to the first, by definition, regardless of what the previous state was.
- **DELETE is idempotent** because its defined effect is "the target resource no longer exists," and "no longer exists" is a state, not a transition — deleting an already-deleted resource is still "it doesn't exist," even if the HTTP status code differs between the first call (200/204) and the repeat (404). This is the subtlety that trips people up: idempotency is about *server state*, not about identical HTTP responses.
- **POST is not idempotent** because it's defined as "perform resource-specific processing," canonically "create a new subordinate resource" — the spec never claims repetition is a no-op, and the common case (create) is definitionally the opposite: each call is a *new* creation.
- **PATCH is not idempotent by default** because it's defined as applying a *partial modification* described by the request body, and a partial modification's effect on repeat depends entirely on what the modification says. `{"op": "increment", "field": "counter"}` applied twice increments twice — not idempotent. `{"op": "set", "field": "status", "value": "shipped"}` applied twice sets it to "shipped" twice — happens to be idempotent, but that's a property of *this specific patch document*, not of PATCH as a verb. This is why the spec (RFC 5789) explicitly declines to claim idempotency for PATCH in general.

### The practical retry consequence

At the network/client layer, a request that times out or gets a connection reset is ambiguous — did the server process it and the response got lost, or did it never arrive? For safe/idempotent methods, the answer doesn't matter: retry blindly, worst case you repeat a no-op. For POST (and any PATCH you can't prove is idempotent for that specific operation), blind retry risks a duplicate side effect — a second order, a second charge, a second email sent.

The fix is a **client-generated idempotency key**: the client creates a UUID once per logical operation attempt and sends it as a header (`Idempotency-Key: <uuid>`); the server stores `(key → response)` — typically in Redis with a TTL, or via a unique constraint in the database — and on a repeat with the same key, returns the *stored* response instead of re-executing the operation. This must be implemented atomically (`INSERT ... ON CONFLICT DO NOTHING`, checking the affected-row count) rather than read-then-write, or two near-simultaneous retries both pass the check and both execute.

### Status codes: who's at fault, and does retrying help

| Range | Meaning | Retry? |
|---|---|---|
| 2xx | Success | N/A |
| 3xx | Further action needed (redirect, or "not modified") | Follow the redirect (see method-preservation below), or treat 304 as "use your cache" |
| 4xx | Client error — the request as sent is wrong | **Don't retry as-is.** Fix the request first (except 408 Request Timeout and 429, see below) |
| 5xx | Server error, or the server can't currently fulfil a valid request | **May retry with backoff** — the request itself might be fine, the server just failed this attempt |

- **401 Unauthorized vs 403 Forbidden.** 401 means "I don't know who you are" (missing or invalid credentials — the correct client response is to authenticate, e.g. prompt for login or refresh a token). 403 means "I know exactly who you are, and you don't have permission" — re-authenticating won't help; this is an authorization decision, not an authentication one. Conflating these is a very common interview miss and a real API-design smell (returning 403 for "not logged in" is technically wrong and misleads client retry logic).
- **429 Too Many Requests** is a 4xx that *is* worth retrying, specifically because it comes with a `Retry-After` header (or should) telling you exactly when to retry — treat it as a scheduling instruction, not a fatal error.
- **301 vs 302 vs 307 vs 308.** 301 (Moved Permanently) and 302 (Found) predate a rigorous method-preservation rule, and in practice browsers have historically rewritten a POST to a GET when following either of them — technically against a strict reading of the spec for 302, but it's what shipped and became the de facto behavior everyone had to work around. 307 (Temporary Redirect) and 308 (Permanent Redirect) exist specifically to remove that ambiguity: both are explicitly defined to preserve the original method *and* body across the redirect. If you're redirecting a POST/PUT to an API client and need the payload to survive the hop, use 307/308, not 301/302.

### Conditional requests: caching and optimistic concurrency from the same mechanism

**ETags** are an opaque validator (RFC 9110 §8.8.3) representing a specific version of a resource — commonly a hash of the content, but the spec doesn't mandate the algorithm, only that identical content should (ideally) produce identical ETags and different content different ones.

- **Strong validators** guarantee byte-for-byte identical representations if the ETag matches — required for range requests to be safely resumed/combined.
- **Weak validators** (prefixed `W/"..."`) only guarantee semantic equivalence — the server is saying "this is equivalent enough for cache-freshness purposes" even if bytes differ (e.g. whitespace or metadata changes). Weak validators are not safe for range requests or for optimistic-concurrency `If-Match`, since "equivalent" isn't "identical."

**Caching flow:** client sends `If-None-Match: "<etag>"` on a GET; if the server's current ETag matches, it returns `304 Not Modified` with no body — the client reuses its cached copy. A `200` means the representation changed and a full body follows. The equivalent time-based mechanism is `If-Modified-Since` against `Last-Modified`, coarser (second-level precision) and generally treated as a fallback when ETags aren't available.

**Optimistic concurrency:** client sends `If-Match: "<etag>"` on a `PUT` or `PATCH`, meaning "only apply this write if the resource still has exactly this ETag." If another writer already changed it, the ETag no longer matches and the server returns `412 Precondition Failed` instead of silently overwriting the other write — this is compare-and-swap semantics implemented entirely through standard HTTP headers, and it directly prevents the classic **lost update** problem (two clients read the same version, both write, second write silently clobbers the first). `If-Unmodified-Since` is the time-based equivalent, again coarser.

### Cache-Control directives that matter

| Directive | Meaning |
|---|---|
| `no-store` | Never cache this response at all, anywhere — for genuinely sensitive data |
| `no-cache` | Can be cached, but **must revalidate with the origin before reuse** — misleadingly named; it does not mean "don't cache" |
| `private` | Cacheable only in the end-user's own client, not in a shared/intermediate cache (CDN, proxy) |
| `public` | Cacheable by shared caches even for responses that would otherwise be restricted (e.g. ones with auth headers) |
| `max-age=N` | Fresh for N seconds from response generation; no revalidation needed until then |
| `must-revalidate` | Once stale (past max-age), the cache must revalidate with the origin before serving — cannot serve stale on origin failure |
| `stale-while-revalidate=N` | Serve the stale copy immediately while asynchronously revalidating in the background for up to N seconds — trades a small staleness window for zero added latency |

A **200** response to a conditional GET means the server sent a fresh, full body (either the validator didn't match, or the client didn't send one). A **304** means the client's cached copy is still valid — same semantic content, but the server sent no body at all, saving bandwidth and server render/serialization cost; the client keeps serving what it already had.

---

## Build it from scratch

An idempotency-key middleware, the piece that actually shows up in interviews and in real payment/order APIs:

```python
# untested sketch
import hashlib, json, time
from dataclasses import dataclass

@dataclass
class StoredResponse:
    status: int
    body: dict
    created_at: float

class IdempotencyStore:
    """Backed by Redis in production; dict here for clarity."""
    def __init__(self, ttl_seconds: int = 24 * 3600):
        self._store: dict[str, StoredResponse] = {}
        self.ttl = ttl_seconds

    def get(self, key: str) -> StoredResponse | None:
        entry = self._store.get(key)
        if entry and time.time() - entry.created_at < self.ttl:
            return entry
        return None

    def put_if_absent(self, key: str, status: int, body: dict) -> bool:
        """Atomic in Redis via SETNX; here, a single-threaded dict stands in."""
        if key in self._store:
            return False
        self._store[key] = StoredResponse(status, body, time.time())
        return True

def handle_post(request, store: IdempotencyStore, handler):
    key = request.headers.get("Idempotency-Key")
    if not key:
        # Policy choice: reject, or execute without dedup protection.
        return handler(request)

    cached = store.get(key)
    if cached is not None:
        return cached.status, cached.body          # replay, do NOT re-execute

    # Reserve the key BEFORE doing the work, so a concurrent retry sees it
    # reserved rather than racing past this check (naive read-then-write races).
    reserved = store.put_if_absent(key, 202, {"status": "processing"})
    if not reserved:
        return 409, {"error": "request with this key already in flight"}

    status, body = handler(request)                 # do the actual work once
    store._store[key] = StoredResponse(status, body, time.time())  # finalize
    return status, body
```

The two things naive versions miss: the key is reserved atomically *before* the work runs, closing the race where two retries both pass a "does it exist" check, and a repeat returns the *original* stored response rather than re-deriving one.

---

## How it's done in production

| Layer | What it adds |
|---|---|
| **API gateway / framework middleware** (Stripe-style `Idempotency-Key`, AWS API Gateway idempotency, Django/FastAPI middleware) | Standardizes key extraction, storage, and replay so every mutating endpoint doesn't hand-roll it inconsistently |
| **CDN / reverse proxy caching** (CloudFront, Fastly, nginx) | Honors `Cache-Control`/`ETag` automatically for GET, serves `304`s without hitting origin, implements `stale-while-revalidate` |
| **HTTP client retry policies** (`tenacity`, `urllib3`'s `Retry`, gRPC's retry config) | Classifies status codes/exceptions as retryable vs not, applies backoff — but most still need you to explicitly gate retry on method safety |
| **Database-level idempotency enforcement** (unique constraint on an idempotency-key column) | Makes the dedup atomic at the storage layer instead of relying on an application-level check-then-write, which is the difference between "usually correct" and "correct under concurrency" |

### Failure modes

| Symptom | Cause | Fix |
|---|---|---|
| Customer charged twice after a network blip | Client retried a POST to `/charge` with no idempotency key | Require and store `Idempotency-Key`; reserve the key atomically before executing |
| A form submission becomes a GET after following a redirect, losing all submitted data | Server used 301/302 for a POST-target redirect; client (browser or library) rewrote method to GET per historical convention | Use 307/308 to preserve method and body across the redirect |
| Two concurrent edits silently overwrite each other, one user's change vanishes | `PUT`/`PATCH` with no conditional header — classic lost update | Require `If-Match: <etag>`; return 412 on mismatch, force client to re-fetch and reapply |
| Client keeps re-authenticating in a loop after a permission change | Server returns 401 for an authorization failure instead of 403, client treats it as "credentials expired" and refreshes forever | Return 403 for "authenticated but not permitted", reserve 401 strictly for missing/invalid credentials |
| API consumers hammer a rate-limited endpoint immediately after a 429 | Server omits `Retry-After`, client has no signal for backoff duration | Always send `Retry-After` on 429 (and ideally 503) |
| Stale content served indefinitely after an update | `Cache-Control: no-cache` misunderstood as "don't cache," configured as `max-age` with no revalidation path instead | Use `must-revalidate` or a short `max-age` plus proper ETag support so updates propagate promptly |
| Bulk retry of a batch job doubles half the records | Batch handler implemented as repeated POSTs with no per-item idempotency key, only a job-level one | Key idempotency at the granularity that can actually be retried independently — per item, not just per batch |

---

## Tradeoffs & when NOT to use it

- **Don't make GET have side effects**, even "harmless" ones like incrementing a view counter synchronously in the request path if you also want that endpoint to be cacheable or prefetchable — either accept the counter is approximate/best-effort, or move it to an async event, not the GET handler itself.
- **Don't assume PATCH is safe to retry just because it's "not POST."** Verify idempotency per endpoint; a PATCH that increments or appends is exactly as dangerous to retry blindly as a POST.
- **Don't skip idempotency keys because "our retries are rare."** The cost of getting this wrong (duplicate charges, duplicate orders) is asymmetric — rare-but-catastrophic beats common-but-cheap in the cost-benefit here, which is why it's now closer to a baseline expectation than an optional hardening step for anything payment- or order-adjacent.
- **Don't use ETags/conditional requests as your only concurrency-control mechanism for high-contention writes.** Optimistic concurrency (412 on mismatch, client retries) works well when conflicts are rare; if the same resource is being written dozens of times a second by different clients, you'll thrash on 412s and a pessimistic lock or a different data model (CRDT, single-writer partition) is the better fit.
- **`no-cache` is not a performance optimization — don't reach for it by default.** It still allows caching, just forces revalidation every time, so it doesn't save the round trip, only the bandwidth of the body when unchanged. If you actually want to avoid the round trip, you want `max-age`, and if you actually want to avoid *any* storage, you want `no-store`.

---

## Interview questions

### Q1 — Define safe and idempotent, precisely, and name which verbs qualify for each.
**Testing:** baseline, but the follow-ups separate people who understand the definitions from people who memorized the table.
**Answer:** Safe: no intended server-side side effects (GET, HEAD, OPTIONS, TRACE). Idempotent: N identical requests produce the same server *state* as 1 request (GET, HEAD, OPTIONS, TRACE, PUT, DELETE). Safety implies idempotency; idempotency doesn't imply safety — PUT and DELETE both change state, just to the same end state regardless of repeat count.
**Follow-up trap:** *"Is a repeat DELETE guaranteed to return the same status code as the first?"* — No. The first DELETE might return 200/204, a repeat 404 (already gone) — the *response* can differ, but the *resource state* ("it doesn't exist") is identical either way. Idempotency is a state property, not a response-identity property.

### Q2 — Why is PUT idempotent but POST is not? Reason from the definitions, not the table.
**Answer:** PUT is defined as "store this representation as the entire target resource" — a statement of desired end state. Applying that statement twice is a no-op the second time by definition; there's no notion of "relative to what was there before." POST is defined as resource-specific processing, canonically "create a new subordinate resource" — the spec never claims repetition is a no-op, and creation specifically means each call produces something new.
**Follow-up trap:** *"So could you design a POST endpoint that IS idempotent?"* — Yes, and it's common in practice — e.g. `POST /orders` with a client-supplied idempotency key that dedupes server-side is *made* idempotent by an added mechanism, not by the verb itself. The verb's default isn't idempotent; a specific endpoint's contract can add that guarantee on top.

### Q3 — Is PATCH idempotent?
**Testing:** whether you'll give a flat wrong answer or reason about the specific operation.
**Answer:** Not by default, and the spec (RFC 5789) deliberately doesn't claim it is. Whether a specific PATCH is idempotent depends on what the patch document says: `set field to value` applied twice yields the same result (idempotent in practice); `increment field` applied twice does not (not idempotent). It's a property of the operation encoded in the request, not of the PATCH verb itself.
**Follow-up trap:** *"Your API only ever does field-set PATCHes today. Can you safely treat it as idempotent for retry purposes?"* — Only if that's an enforced, documented contract for every current *and future* PATCH endpoint — otherwise the first engineer who adds an `increment` or `append` operation silently breaks a retry policy that assumed idempotency. Safer to make idempotency explicit via a key rather than an implicit assumption about payload shape.

### Q4 — A client's HTTP call to your API times out. What's the safe retry policy?
**Answer:** If the method is safe/idempotent (GET, HEAD, PUT, DELETE), retry with backoff — worst case you repeat a no-op or re-fetch the same state. If it's POST or a not-provably-idempotent PATCH, don't blindly retry; either require a client-generated idempotency key so a retry is provably safe, or surface the ambiguity to the caller rather than silently risking a duplicate.
**Follow-up trap:** *"The timeout happened on the client side — how do you even know if the server processed it?"* — You don't, and that's exactly the point: a timeout is genuinely ambiguous (request lost vs. response lost), which is precisely why idempotency (of the method, or of an explicit key) is what makes retry decisions safe rather than a guess.

### Q5 — Design an idempotency-key mechanism for a payment-creation endpoint.
**Answer:** Client generates a UUID per logical payment attempt, sends it as `Idempotency-Key`. Server, on first sight of a key, atomically reserves it (unique constraint or `SETNX`-equivalent) before doing any work, executes the charge, and stores `(key → final response)`. Any repeat with that key returns the stored response without re-executing. TTL on the stored key must exceed the client's maximum retry window, including manual/support-driven replays, not just automatic retries.
**Follow-up trap:** *"Two retries arrive within milliseconds of each other, before the first has finished processing. What happens?"* — This is the hard case: naive read-then-write races and both pass a "does it exist" check, executing twice. The reservation step must be atomic and happen *before* the work starts, so the second request sees the key already reserved (return 409 "in flight," or block briefly on it) rather than racing past an unenforced check.

### Q6 — Explain 401 vs 403, and why conflating them is a real bug, not just a style nitpick.
**Answer:** 401 means the request lacks valid authentication — the correct client behavior is to (re-)authenticate. 403 means the client is authenticated but not authorized for this action — re-authenticating won't help, since the problem isn't who they are, it's what they're allowed to do. Conflating them breaks client retry/refresh logic: a client that treats every 403 as "token expired" will loop refreshing a token that was never the problem, and a client that treats every 401 as "permanently forbidden" will fail to prompt for re-login when it should.
**Follow-up trap:** *"Your security team wants to return 404 instead of 403 for resources the user isn't authorized to even know exist. Is that reasonable?"* — Yes, and it's a legitimate, common pattern (avoiding confirming a resource's existence to an unauthorized party) — but it should be a deliberate, documented choice for specifically sensitive resources, not a blanket replacement, because it also removes the diagnostic signal 403 gives to legitimate callers debugging their own permissions.

### Q7 — Why do 307 and 308 exist when 301 and 302 already redirect?
**Answer:** 301/302 predate a strict method-preservation guarantee, and in practice browsers historically rewrote a POST into a GET when following either of them — dropping the body entirely. 307 (temporary) and 308 (permanent) are explicitly specified to preserve both the original method and the request body across the redirect, so an API client following a 307/308 for a POST/PUT keeps its payload intact.
**Follow-up trap:** *"You redirect a webhook POST with a 302 and the receiving system reports the payload vanished. Whose bug is it?"* — Arguably neither system is "wrong" by a strict spec reading for 307/308, but it's a real, foreseeable interoperability trap given known browser/client behavior around 301/302 — the fix is using 307/308 for any redirect that must carry a non-GET method and body, not relitigating spec compliance after the fact.

### Q8 — Explain how ETags enable both caching and optimistic concurrency, using the same mechanism.
**Answer:** An ETag is an opaque version identifier for a resource. For caching: client sends `If-None-Match` on a GET; matching ETag → server returns 304 with no body, client reuses its cache. For concurrency: client sends `If-Match` on a PUT/PATCH; matching ETag → the write proceeds because the client's view was current; mismatch → 412 Precondition Failed, because someone else wrote in between, preventing a silent lost update. Same validator, same compare-on-the-server mechanism, applied to a read-freshness question in one case and a write-safety question in the other.
**Follow-up trap:** *"Would a weak ETag work for the concurrency use case?"* — No — weak validators only promise semantic equivalence, not byte-identical state, which isn't a strong enough guarantee for compare-and-swap write safety. Optimistic concurrency needs a strong validator; caching freshness can tolerate a weak one.

### Q9 — What's the difference between `no-cache` and `no-store`, and why does the naming trip people up?
**Answer:** `no-store` means never persist this response anywhere, full stop — for genuinely sensitive data. `no-cache` is misleadingly named — it *does* allow storage, but requires revalidating with the origin (typically via a conditional request) before ever reusing the stored copy, meaning you save bandwidth on unchanged content but not the round trip itself.
**Follow-up trap:** *"Which one would you use for a page showing another user's private data momentarily rendered client-side?"* — `no-store`, unambiguously — `no-cache` still permits a shared or local cache to retain the bytes on disk, which is exactly the exposure you're trying to avoid for genuinely sensitive content.

### Q10 — A cache serves stale data for 30 seconds after every deploy. Diagnose and fix.
**Answer:** Likely `max-age` set too high relative to how often the underlying data changes, with no `must-revalidate` and no cache-busting on deploy (e.g. no versioned URL or ETag change tied to the new deployment). Fix: shorten `max-age` to match actual data freshness needs, add `must-revalidate` so a stale cache is forced to check rather than silently continuing to serve, and ensure the ETag/Last-Modified actually changes when the underlying content does — a common bug is an ETag computed from something that doesn't reflect the real content change (e.g. a build hash that's stable across a config-only deploy).
**Follow-up trap:** *"What if you can't tolerate even the revalidation round trip's latency?"* — `stale-while-revalidate=N` — serve the (slightly) stale copy immediately with zero added latency, kick off a background revalidation, and the *next* request gets the fresh copy. This trades a bounded staleness window for consistently low latency, which is the right tradeoff for content where a few seconds of staleness is harmless but latency variance isn't.

### Q11 — Explain why 429 is retryable but most 4xx codes aren't, and what a well-behaved client does differently for it.
**Answer:** Most 4xx codes mean the request itself is malformed or invalid for this resource — retrying identically will fail identically, so retrying is pure waste until the client fixes the request. 429 is different: the request was valid, the client is just being rate-limited temporarily. A well-behaved client reads `Retry-After` (seconds or an HTTP-date) and waits exactly that long rather than retrying immediately or applying a generic exponential backoff that might be shorter or needlessly longer than what the server actually needs.
**Follow-up trap:** *"The server doesn't send `Retry-After`. What now?"* — Fall back to exponential backoff with jitter, but flag this as an API gap — a rate-limiting endpoint that doesn't tell callers when to come back is forcing every client to guess, which produces exactly the synchronized-retry-storm behavior rate limiting was supposed to prevent in the first place.

### Q12 — Design the conditional-request strategy for a multi-user document-editing API where two users can open the same document.
**Answer:** GET returns the document plus a strong ETag. Both users' clients cache it. On save, each client sends `PUT`/`PATCH` with `If-Match: <etag-they-last-saw>`. Whoever saves first succeeds and gets a new ETag; the second save's `If-Match` no longer matches the server's current ETag, so it fails with 412 rather than silently overwriting the first user's change. The client handling the 412 should re-fetch the current version, ideally showing the user what changed (or offering a merge), rather than blindly resubmitting — resubmitting on a 412 without re-fetching just moves the same lost-update risk one layer up.
**Follow-up trap:** *"What if the two users are editing different fields of the same document — should the second save really fail?"* — This is exactly where whole-document ETags are too coarse; a field-level or operational-transform/CRDT-based merge strategy is the better fit for genuinely concurrent, non-conflicting edits, and reaching for that instead of a single document-wide ETag is the senior distinction — ETag-based optimistic concurrency is right for "rare conflicting writes," wrong for "expected frequent concurrent editing of disjoint parts."

### Q13 — Rank GET, PUT, POST, PATCH, DELETE by how often getting their semantics wrong causes a real production incident.
**Answer:** 1) POST retried without an idempotency key — duplicate charges/orders, the most expensive and most common mistake because the fix is nontrivial to retrofit. 2) PATCH assumed idempotent by verb alone — often safe until someone adds a non-idempotent op to the schema. 3) PUT/PATCH with no `If-Match` — silent lost updates, no error, just quietly overwritten data. 4) 401/403 conflation — broken client retry/refresh loops, rarely catastrophic. 5) 301/302 vs 307/308 confusion — narrower blast radius, usually caught once a payload visibly goes missing.
**Follow-up trap:** *"Why rank a silent bug (lost updates) below a loud one (duplicate charges)?"* — Frequency times blast radius, not blast radius alone: every payment retry path is exposed to the duplicate-charge failure mode, and it's directly financial, which is how incident cost usually gets prioritized.

---

## Red flags that fail you

- Reciting the safe/idempotent table without being able to derive it from the verb definitions.
- Claiming idempotency means "the response is identical," rather than "the server state is identical."
- Saying PATCH is idempotent, full stop, with no caveat about the specific operation.
- Not knowing why 307/308 exist, or confusing them with 301/302.
- Confusing 401 and 403.
- Recommending blind retry of POST with no idempotency-key mechanism.
- Calling `no-cache` "don't cache this."
- Not knowing ETags serve both caching and optimistic-concurrency roles.
- Treating all 4xx and all 5xx as uniformly retryable or uniformly not.

---

## Cheat card

```
SAFE (no side effects):       GET, HEAD, OPTIONS, TRACE
IDEMPOTENT (N reqs = 1 in server STATE, response CAN differ):
                               GET, HEAD, OPTIONS, TRACE, PUT, DELETE
NOT idempotent by default:    POST (create = new each time), PATCH (depends on op)
  safe ⟹ idempotent.  idempotent ⟹̸ safe (PUT/DELETE change state, same end state).

WHY: PUT = "this IS the resource now" (end-state statement, repeat = no-op)
     POST = "create a new subordinate resource" (repeat = new thing, by definition)
     PATCH = partial delta; increment-twice ≠ increment-once, set-twice = set-once

RETRY RULE: safe/idempotent → retry blindly. POST/unsafe-PATCH → need
  Idempotency-Key (client UUID, server stores key→response, atomic reserve
  BEFORE executing, INSERT...ON CONFLICT not read-then-write, TTL > max retry window)

STATUS CODES:
  2xx success | 3xx further action | 4xx client's fault, DON'T retry as-is (except 429)
  5xx server's fault, MAY retry w/ backoff
  401 = who ARE you (auth) | 403 = I know you, NO (authz) — don't conflate
  429 = retryable, honor Retry-After
  301/302 = historically rewritten POST→GET by browsers, body lost
  307/308 = preserve METHOD + BODY across redirect — use these for non-GET redirects

CONDITIONAL REQUESTS (ETag-based):
  caching:      If-None-Match matches → 304, no body, client reuses cache
  concurrency:  If-Match matches → write proceeds; mismatch → 412 (lost-update guard)
  strong ETag = byte-identical guarantee (needed for range reqs + If-Match CAS)
  weak ETag (W/"...") = semantically equivalent only — NOT safe for CAS

CACHE-CONTROL:
  no-store        never persist, anywhere
  no-cache        CAN cache, must revalidate before reuse (misleading name)
  private/public  client-only cache / shared-cache-eligible
  max-age=N       fresh N seconds, no revalidation needed
  must-revalidate stale copy MUST revalidate, can't serve stale on origin failure
  stale-while-revalidate=N  serve stale now, refresh in background
  200 = fresh full body | 304 = cache still valid, NO body, saves render+bandwidth
```

## Sources

- RFC 9110 (HTTP Semantics) — IETF datatracker, accessed 2026-07-26
- RFC 5789 (PATCH Method for HTTP) — IETF datatracker, accessed 2026-07-26
- RFC 7396 (JSON Merge Patch), RFC 6902 (JSON Patch) — IETF datatracker, accessed 2026-07-26
- [307 and 308 Response Codes — Seer Interactive](https://www.seerinteractive.com/insights/307-and-308-response-codes) — accessed 2026-07-26
- [Handling Optimistic Concurrency with ETags — Ed-Fi Alliance](https://docs.ed-fi.org/reference/data-exchange/api-guidelines/design-and-implementation-guidelines/api-implementation-guidelines/handling-optimistic-concurrency-with-etags/) — accessed 2026-07-26
- [ETags and Optimistic Concurrency Control](https://fideloper.com/etags-and-optimistic-concurrency-control) — accessed 2026-07-26
- [Idempotent: PUT versus POST RESTful APIs — Medium](https://medium.com/@sandeep.h.hullatti/idempotent-put-versus-post-restful-apis-2784e6d2ca30) — accessed 2026-07-26
- [Top 40+ REST API Interview Questions and Answers (2026) — InterviewBit](https://www.interviewbit.com/rest-api-interview-questions/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
