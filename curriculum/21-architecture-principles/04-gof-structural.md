# GoF Structural Patterns in Python/Java/Go

> **Track:** T21 Architecture & Design Principles · **Time:** 1.5h · **Prereqs:** T21-gof-creational · **Updated:** 2026-07-26
> **Module id:** `T21-gof-structural` · **Tags:** patterns

## The 30-second version

The seven structural patterns — Adapter, Bridge, Composite, Decorator, Facade, Flyweight, Proxy — all answer "how do I compose objects into larger structures without the composition itself becoming a maintenance liability?" Unlike creational patterns, most of these did **not** dissolve into language features, because the problem they solve — impedance mismatch between interfaces, tree-shaped data, wrapping behavior around an object, hiding subsystem complexity — is structural, not syntactic. Adapter is everywhere it's needed (every SDK wrapping a third-party API), Facade is every well-designed service boundary, Decorator is every HTTP middleware chain and Python `@decorator`, Proxy is every ORM lazy-load and every service-mesh sidecar, and Composite is every tree UI and every nested validation rule. The two that are genuinely rare in modern backend work are Bridge (real uses exist but are uncommon outside GUI toolkits and driver abstraction layers) and Flyweight (largely superseded by string interning, integer caching, and just letting the garbage collector do its job — you reach for it only under measured, real memory pressure). The honest interview answer: five of the seven are load-bearing and you should be able to point at one in your own codebase; two are niche and citing them as your daily-driver pattern is a minor red flag.

## Why this gets asked

Structural patterns are where "have you actually built something with layers" gets tested. Anyone can define Adapter; fewer can explain why wrapping a third-party payment SDK behind your own interface (an Adapter) is the single highest-leverage thing you can do to survive that vendor's next breaking API change. The interviewer has lived through a codebase where a vendor SDK was called directly from 200 call sites, and the vendor deprecated a method — that's a week of mechanical, dangerous find-and-replace that an Adapter layer would have made a one-file change. They're checking whether you've internalized *why* you isolate external dependencies, not whether you can recite the UML diagram.

---

## Lineage: past → present → future

**What came before.** Before *Design Patterns* (1994), the discipline for managing structural complexity was ad hoc — inheritance-heavy C++ codebases solved "I need object A to behave like B" by multiple inheritance (fragile, the "diamond problem") or by hand-rolled wrapper classes with no shared vocabulary. The structural patterns chapter of GoF is largely a codification of composition-over-inheritance techniques that senior C++/Smalltalk engineers were already using informally; the book's contribution was naming them consistently enough that "wrap it in an Adapter" became a portable instruction across teams and languages.

**Where it stands now.** The live consensus is that structural patterns aged far better than creational ones because composition problems are language-agnostic — Python, Java, and Go all still need to reconcile mismatched interfaces (Adapter), hide subsystem complexity (Facade), add cross-cutting behavior without subclass explosion (Decorator), and represent recursive tree structures uniformly (Composite). Where the live disagreement sits: whether Proxy and Decorator are actually distinguishable in practice, since both wrap an object behind the same interface — the GoF answer (Proxy controls *access*, Decorator adds *behavior*) is a real distinction but the two frequently overlap in real code (a caching proxy is also adding behavior), and pattern purists spend more energy on this boundary than it's worth. Flyweight is the one pattern in this category whose relevance genuinely declined, because modern runtimes (JVM string pool, Python small-int caching, arena allocators) do automatically what Flyweight used to require you to hand-build.

**Where it's heading.** High confidence: Adapter, Facade, Decorator, Proxy, and Composite will remain permanently relevant because they map directly onto real architectural seams — the boundary between your code and a vendor's, the boundary between a subsystem and its callers, cross-cutting concerns (auth, caching, logging, retries) layered around a call, tree-shaped domain data (org charts, file systems, UI trees, nested permission rules). Moderate confidence: service meshes (Envoy sidecars) and API gateways are effectively industrial-scale, infrastructure-level instances of Proxy and Facade respectively, and that trend of moving these patterns *out* of application code and *into* infrastructure will continue — meaning the pattern's value persists but its implementation increasingly lives in YAML/mesh config rather than a hand-written wrapper class. Speculative: as more services are composed from LLM agents calling tools, the Adapter pattern is quietly reappearing as the "tool wrapper" layer that normalizes heterogeneous external APIs into a single tool-calling interface — same problem, new domain.

---

## Mental model

```
STRUCTURAL PATTERNS = how do I compose objects without the composition breaking?

  Adapter     translate one interface to another          → your VendorClient wrapping their SDK
  Bridge      decouple abstraction from implementation      → interface + swappable impl, 2 hierarchies
              so BOTH can vary independently
  Composite   treat a tree of objects uniformly,            → every node (leaf or branch) implements
              recursively                                       the same interface
  Decorator   add behavior around an object without          → middleware chain / Python @decorator
              subclassing, stackable
  Facade      one simple interface hiding a complicated       → your PaymentService hiding 6 vendor calls
              subsystem
  Flyweight   share immutable state across many logical       → string interning, cached small integers
              objects to cut memory
  Proxy       stand-in that controls access to the real       → lazy load, cache, rate limit, auth check
              object, same interface
```

The fast way to tell Adapter, Facade, Decorator, and Proxy apart, since all four "wrap another object behind an interface":

| Pattern | Changes the interface? | Adds behavior? | Purpose |
|---|---|---|---|
| Adapter | Yes — translates A's interface to B's | No | Compatibility |
| Facade | Yes — simplifies many interfaces to one | No (usually) | Simplicity |
| Decorator | No — same interface as wrapped object | Yes, stackable | Extension |
| Proxy | No — same interface as real object | Sometimes (access control) | Control |

---

## How it actually works

### Adapter — the vendor-isolation pattern

Problem: your code expects interface `Notifier.send(msg)`, but the SDK you're integrating exposes `TwilioClient.messages.create(body=..., to=..., from_=...)`. Calling the SDK directly from 50 call sites means the vendor's next breaking change is a 50-site refactor.

```python
from typing import Protocol

class Notifier(Protocol):
    def send(self, to: str, message: str) -> None: ...

class TwilioNotifier:
    """Adapter: translates our domain interface to Twilio's SDK shape."""
    def __init__(self, client: "TwilioClient", from_number: str):
        self._client = client
        self._from = from_number

    def send(self, to: str, message: str) -> None:
        self._client.messages.create(body=message, to=to, from_=self._from)
```

```java
// Java: same idea, adapting a legacy XML-based API to a modern JSON-shaped interface.
public interface PaymentGateway {
    PaymentResult charge(String cardToken, BigDecimal amount);
}

public class LegacyXmlGatewayAdapter implements PaymentGateway {
    private final LegacyXmlClient legacy;
    public PaymentResult charge(String cardToken, BigDecimal amount) {
        String xmlRequest = buildXml(cardToken, amount);
        String xmlResponse = legacy.submit(xmlRequest);
        return parseResult(xmlResponse);       // translation happens here, once
    }
}
```

```go
// Go: interfaces are structural, so "adapting" is often just implementing
// the interface your code expects, wrapping the vendor SDK's client.
type Notifier interface {
    Send(to, message string) error
}

type twilioAdapter struct { client *twilio.Client; from string }

func (a *twilioAdapter) Send(to, message string) error {
    _, err := a.client.Messages.Create(&twilio.MessageParams{
        To: to, From: a.from, Body: message,
    })
    return err
}
```

**The measurable payoff:** when the vendor changes their SDK (renames a field, changes auth), the blast radius is the adapter file, not every call site. This is the single highest-value structural pattern for anyone integrating third-party APIs, which in an AI/agent-heavy resume (tool integrations, multiple LLM providers, multiple vector DB clients) is most of the job.

### Facade — hiding subsystem complexity behind one seam

Problem: placing an order touches inventory, pricing, tax, payment, and notification services. Every caller that needs to place an order souldn't need to know all five.

```python
class OrderFacade:
    def __init__(self, inventory, pricing, tax, payment, notifier):
        self._inventory, self._pricing = inventory, pricing
        self._tax, self._payment, self._notifier = tax, payment, notifier

    def place_order(self, cart: Cart, customer: Customer) -> OrderResult:
        self._inventory.reserve(cart.items)
        subtotal = self._pricing.calculate(cart)
        total = subtotal + self._tax.calculate(subtotal, customer.region)
        charge = self._payment.charge(customer.payment_method, total)
        self._notifier.send(customer.email, f"Order confirmed: ${total}")
        return OrderResult(charge_id=charge.id, total=total)
```

The Facade doesn't add capability — every one of these calls could be made directly by the caller. What it buys is a single seam to test, mock, version, and reason about, and it's exactly what a well-designed microservice's public API *is*: a facade over its internal modules.

### Decorator — stackable behavior without subclass explosion

Problem: you want retry, then caching, then logging, around a base HTTP call — and you want to add/remove/reorder any of them without a combinatorial subclass hierarchy (`CachedRetryingLoggingClient`, `RetryingLoggingClient`, `LoggingClient`...).

```python
from functools import wraps
import time

def with_retry(max_attempts=3):
    def decorator(fn):
        @wraps(fn)
        def wrapper(*a, **kw):
            for attempt in range(max_attempts):
                try:
                    return fn(*a, **kw)
                except TransientError:
                    if attempt == max_attempts - 1:
                        raise
                    time.sleep(0.1 * 2 ** attempt)
        return wrapper
    return decorator

def with_timing(fn):
    @wraps(fn)
    def wrapper(*a, **kw):
        start = time.monotonic()
        try:
            return fn(*a, **kw)
        finally:
            print(f"{fn.__name__} took {time.monotonic() - start:.3f}s")
    return wrapper

@with_timing
@with_retry(max_attempts=3)
def fetch_price(sku: str) -> float:
    return http_client.get(f"/price/{sku}").json()["price"]
```

Python's `@decorator` syntax is a first-class language feature *because* the Decorator pattern is common enough to deserve syntax — this is one of the clearest examples of a GoF pattern being absorbed into a language, but unlike the creational patterns, the underlying composition (stacking independent behaviors around a call) is exactly as valuable as it was in 1994, just with less ceremony.

```java
// Java: the object-wrapping form, since Java lacks Python's function-decorator syntax
// (annotations are declarative metadata, not the same mechanism).
public interface DataSource { String read(); }

public class CompressingDataSource implements DataSource {
    private final DataSource wrapped;
    public CompressingDataSource(DataSource wrapped) { this.wrapped = wrapped; }
    public String read() { return decompress(wrapped.read()); }
}

public class EncryptingDataSource implements DataSource {
    private final DataSource wrapped;
    public String read() { return decrypt(wrapped.read()); }
}

DataSource source = new EncryptingDataSource(new CompressingDataSource(new FileDataSource(path)));
```

```go
// Go: functional decorators around http.Handler are the idiomatic form —
// middleware chains in every Go web framework are literally this pattern.
func WithLogging(next http.Handler) http.Handler {
    return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
        start := time.Now()
        next.ServeHTTP(w, r)
        log.Printf("%s %s %v", r.Method, r.URL.Path, time.Since(start))
    })
}

handler := WithLogging(WithAuth(baseHandler))
```

### Proxy — same interface, controlled access

Problem: you want lazy loading, caching, rate limiting, or access control around an object, without callers knowing the difference.

```python
class LazyImageProxy:
    """Virtual proxy: defers expensive load until first real use."""
    def __init__(self, path: str):
        self._path = path
        self._real: "Image | None" = None

    def render(self) -> bytes:
        if self._real is None:
            self._real = Image.load(self._path)   # expensive I/O, deferred
        return self._real.render()
```

```java
// Java: a protection proxy, controlling access based on caller permissions.
public class SecureDocumentProxy implements Document {
    private final Document real;
    private final User caller;
    public String read() {
        if (!caller.hasPermission(Permission.READ)) {
            throw new AccessDeniedException();
        }
        return real.read();
    }
}
```

```go
// Go: a caching proxy, the most common real-world proxy shape in backend services.
type cachingRepo struct {
    inner Repository
    cache *lru.Cache
}

func (r *cachingRepo) Get(id string) (*Record, error) {
    if v, ok := r.cache.Get(id); ok {
        return v.(*Record), nil
    }
    rec, err := r.inner.Get(id)
    if err == nil {
        r.cache.Add(id, rec)
    }
    return rec, err
}
```

The line between Proxy and Decorator in practice: a caching proxy is arguably both — same interface (Proxy) *and* adding new behavior (Decorator's territory). Don't lose points over this ambiguity; name what the object actually does (lazy load, cache, gate access) rather than agonizing over the label.

### Composite — uniform tree traversal

Problem: a permission rule can be a single check or a boolean combination of other rules (AND/OR/NOT nested arbitrarily); a UI element can be a button or a container of other elements; an org chart node can be an employee or a manager with reports. In every case, callers want to treat the whole tree the same way regardless of depth.

```python
from abc import ABC, abstractmethod

class PermissionRule(ABC):
    @abstractmethod
    def evaluate(self, ctx: "Context") -> bool: ...

class HasRole(PermissionRule):          # leaf
    def __init__(self, role: str): self.role = role
    def evaluate(self, ctx): return self.role in ctx.user.roles

class AllOf(PermissionRule):            # composite
    def __init__(self, *rules: PermissionRule): self.rules = rules
    def evaluate(self, ctx): return all(r.evaluate(ctx) for r in self.rules)

class AnyOf(PermissionRule):            # composite
    def __init__(self, *rules: PermissionRule): self.rules = rules
    def evaluate(self, ctx): return any(r.evaluate(ctx) for r in self.rules)

can_approve_refund = AllOf(HasRole("finance"), AnyOf(HasRole("manager"), HasRole("director")))
can_approve_refund.evaluate(ctx)   # caller doesn't care this is a 3-node tree
```

The value: `can_approve_refund.evaluate(ctx)` is identical whether the rule is a single `HasRole` leaf or a five-level nested boolean tree — the caller never branches on "is this a leaf or a composite," which is exactly the point.

### Bridge — decoupling abstraction from implementation (the rare one)

Problem: you have a `Shape` abstraction (Circle, Square) that needs to render via different backends (Raster, Vector), and you don't want `CircleRaster`, `CircleVector`, `SquareRaster`, `SquareVector` — an N×M subclass explosion.

```python
class Renderer(ABC):
    @abstractmethod
    def render_circle(self, x, y, r): ...

class RasterRenderer(Renderer):
    def render_circle(self, x, y, r): ...  # pixel-based

class VectorRenderer(Renderer):
    def render_circle(self, x, y, r): ...  # path-based

class Circle:
    def __init__(self, x, y, r, renderer: Renderer):
        self.x, self.y, self.r, self.renderer = x, y, r, renderer
    def draw(self):
        self.renderer.render_circle(self.x, self.y, self.r)
```

Bridge and Strategy (a behavioral pattern) are structurally almost identical — both compose an object with an interchangeable interface — and the distinction is largely about *intent* (Bridge is about avoiding a combinatorial class explosion across two independent hierarchies; Strategy is about swapping one algorithm). Outside GUI toolkits, database driver layers (JDBC's `Driver` abstraction from the `Connection`/`Statement` API), and cross-platform rendering, Bridge is genuinely rare in backend work — most engineers go a whole career without deliberately reaching for it by name.

### Flyweight — the one memory optimization pattern

Problem: you have millions of logical objects (characters in a text editor, tiles in a game map, tokens in a tokenizer) that share most of their state, and instantiating each one fully would exhaust memory.

```python
class GlyphFlyweight:
    """Immutable, shared per character — intrinsic state only."""
    _pool: dict[str, "GlyphFlyweight"] = {}

    def __new__(cls, char: str):
        if char not in cls._pool:
            inst = super().__new__(cls)
            inst.char = char
            inst.font_metrics = load_metrics(char)   # expensive, shared
            cls._pool[char] = inst
        return cls._pool[char]

    def render_at(self, x: int, y: int):   # extrinsic state passed in per call
        draw(self.char, self.font_metrics, x, y)
```

This is precisely what Python's small-integer cache (`-5` to `256` are singletons), string interning, and the JVM's string pool already do automatically for you at the language-runtime level. Reach for a hand-built Flyweight only when profiling shows a genuine, measured memory problem from millions of near-identical objects that the runtime isn't already deduplicating — which is rare outside game engines, text rendering, and some tokenizer/embedding-index internals.

---

## Build it from scratch

A middleware chain that composes Decorator (cross-cutting behavior) with Proxy (caching), the two most common structural patterns in a real backend service:

```python
from functools import wraps
import time
from typing import Callable

_cache: dict[str, tuple[float, object]] = {}

def cached(ttl: float):
    """Decorator that also functions as a caching proxy over the wrapped call."""
    def decorator(fn: Callable):
        @wraps(fn)
        def wrapper(*args, **kwargs):
            key = f"{fn.__name__}:{args}:{kwargs}"
            now = time.monotonic()
            if key in _cache:
                expires_at, value = _cache[key]
                if now < expires_at:
                    return value
            result = fn(*args, **kwargs)
            _cache[key] = (now + ttl, result)
            return result
        return wrapper
    return decorator

def logged(fn: Callable):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        start = time.monotonic()
        result = fn(*args, **kwargs)
        print(f"{fn.__name__}({args}, {kwargs}) -> {result!r} in {time.monotonic()-start:.4f}s")
        return result
    return wrapper

@logged
@cached(ttl=30.0)
def get_exchange_rate(base: str, quote: str) -> float:
    return http_client.get(f"/rates/{base}/{quote}").json()["rate"]
```

Stacking order matters here exactly like the resilience catalogue's nesting order matters: `@logged` outermost means every call (cache hit or miss) is logged; if `@cached` were outermost, cache hits would never reach the logger, which is a real, easy-to-miss bug when composing decorators.

---

## How it's done in production

| Pattern | Where it shows up in real frameworks |
|---|---|
| Adapter | Every cloud SDK wrapper you write around boto3/google-cloud/azure-sdk, `SQLAlchemy` dialects adapting to each DB's SQL dialect, LangChain's `BaseChatModel` adapting each provider's API to one interface |
| Facade | Your service's public API layer, Django's `Manager`/`QuerySet` hiding SQL generation, `requests.Session` hiding connection pooling + retries + cookies |
| Decorator | Every WSGI/ASGI middleware, Python `@app.route`, `@retry`, `@lru_cache`, Go's `http.Handler` chains, Java Spring's `@Transactional`/`@Cacheable` (implemented via dynamic proxies under the hood) |
| Proxy | SQLAlchemy's lazy-loaded relationships, Hibernate's lazy proxies, `gRPC` stub clients, service mesh sidecars (Envoy is an infrastructure-level Proxy) |
| Composite | Every UI framework's component tree, `pathlib.Path` operations recursing over directories, nested validation/permission rule trees, AST nodes in any parser |
| Bridge | JDBC `Driver`/`Connection` abstraction, cross-platform GUI toolkits (Qt), rare in typical backend services |
| Flyweight | JVM string pool, Python small-int/string interning, font glyph caches, BPE tokenizer vocab tables (shared immutable token objects) |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| One vendor API change breaks 50 files | No Adapter; SDK called directly everywhere | Introduce an Adapter/interface layer; confine vendor-specific code to one file |
| A "God Facade" with 40 methods and no cohesion | Facade absorbed unrelated responsibilities over time instead of staying a thin pass-through | Split into multiple facades along actual subsystem boundaries |
| Decorator order bug: cached responses never get logged | Decorators stacked in the wrong order | Reason explicitly about stacking order, outermost = first to see the call and last to see the result |
| Cache Decorator returns stale data after a write | No invalidation path from write path to the read-side cache | Explicit cache invalidation/TTL discipline, not "add caching" as an afterthought |
| Lazy-load Proxy causes N+1 query storm | Proxy triggers a fresh DB round trip per access with no batching | Prefetch/eager-load in bulk before iterating; add batching to the proxy layer |
| Composite tree recursion blows the stack | Unbounded nesting depth with no cycle/depth guard | Add a max-depth check and cycle detection when building the tree |
| Flyweight pool becomes a hidden memory leak | Pool never evicts, intrinsic state grows unbounded (e.g., caching per-request strings instead of per-vocabulary tokens) | Cache only genuinely shared, bounded, immutable state; add eviction if the key space is unbounded |

---

## Tradeoffs & when NOT to use it

- **Adapter is nearly always worth it for any third-party dependency you don't control** — the cost is one extra interface and implementation file; the payoff is confining the vendor's next breaking change to that file. The only case to skip it: a truly stable, in-house-controlled dependency where you'd be adapting your own code to itself.
- **Facade becomes a liability when it absorbs business logic instead of just delegating.** A facade with conditionals and side effects of its own, rather than pure pass-through orchestration, has quietly become a God Object under a friendlier name.
- **Decorator composition is not commutative — order changes behavior.** Stacking retry inside vs. outside a cache decorator gives different (and sometimes wrong) semantics; always be explicit about which decorator sees the call first.
- **Proxy for lazy-loading is a classic N+1 trap.** A proxy that transparently defers a DB fetch is invisible in code review and produces a query storm in production; if you use lazy-loading proxies (ORMs default to this), you need explicit eager-loading escape hatches for hot paths.
- **Flyweight should not be your first memory optimization.** Reach for it only after profiling shows millions of near-duplicate objects consuming real memory; in Python and Java, the runtime already flyweights small integers and interned strings, so a hand-built pool is redundant unless your domain objects are larger than a primitive.
- **Bridge is easy to over-apply.** If you don't actually have two independent hierarchies that both need to vary (an abstraction *and* an implementation, each with multiple variants), you don't need Bridge — a single interface with one implementation swapped via DI is enough, and adding Bridge's extra indirection for a hierarchy that will only ever have one implementation is premature.
- **Composite is wrong for flat, non-recursive data.** If your "tree" never actually nests (a list of independent rules, no AND/OR grouping), Composite adds ceremony a plain list and a loop would do without.

---

## Interview questions

### Q1 — What's the difference between Adapter and Facade? Give an example of each from a system you've built.
**Testing:** whether you can distinguish "translate an interface" from "simplify a subsystem."
**Answer:** Adapter changes an interface to match what the caller expects (one-to-one interface translation, usually wrapping a single external dependency). Facade simplifies access to a *subsystem* of multiple components behind one simpler interface, without necessarily changing any individual interface. In a RAG system: an `EmbeddingAdapter` wrapping OpenAI's/Cohere's differently-shaped embedding APIs behind one `Embedder.embed(texts) -> list[vector]` interface is Adapter; a `RagPipeline.answer(query)` that internally calls retrieval, reranking, and generation is a Facade.
**Follow-up trap:** *"Could the same class be both?"* — yes, and that's fine; a facade over a single vendor SDK that also translates its interface is doing both jobs. The names describe intent, not mutually exclusive categories.

### Q2 — Explain the difference between Proxy and Decorator. Why do they get confused?
**Testing:** the classic ambiguous pair in this category.
**Answer:** Both wrap an object behind the same interface as the thing they wrap. Proxy's intent is controlling *access* (lazy load, permission check, rate limit, remote stub) — the wrapped object may not even be created yet. Decorator's intent is adding *behavior* to an already-accessible object, and decorators are meant to stack arbitrarily. They get confused because a caching wrapper is legitimately both: it controls access (short-circuits the real call) and adds behavior (storing/returning cached values). Don't over-invest in resolving the ambiguity; name the actual function.
**Follow-up trap:** *"So which is Envoy's sidecar proxy — Proxy or Decorator?"* — architecturally it's Proxy (transparent stand-in controlling access to the real service, same "interface" at the network level) but it also adds cross-cutting behavior (retries, mTLS, observability) which is Decorator's job — this is the same ambiguity at infrastructure scale, and naming it "a proxy that also decorates the call with resilience behavior" is the accurate, nuanced answer.

### Q3 — When would you use Composite, and what's the actual payoff versus a flat list with a type tag?
**Testing:** whether you understand *why* uniform interface matters, not just tree structure.
**Answer:** Use Composite when data is genuinely recursive (a rule can contain other rules; a folder can contain files or folders) and callers need to operate on the whole structure without branching on depth or type. The payoff over `if item.type == "leaf"` scattered through calling code: every caller just calls `.evaluate()` or `.render()` uniformly, and adding a new composite type (e.g., a `NoneOf` rule) requires zero changes to existing callers — open/closed in practice.
**Follow-up trap:** *"What if the tree can have cycles?"* — Composite as classically described assumes a DAG/tree; a cycle (rule A contains rule B which contains rule A) causes infinite recursion on evaluate(). Real implementations need a cycle guard or a max-depth check when the structure is built or mutated, not just when traversed.

### Q4 — Why does Python have `@decorator` syntax but no equivalent first-class syntax for Adapter or Facade?
**Testing:** understanding of *why* some structural patterns became language syntax and others didn't.
**Answer:** Decorator wraps a function/callable with the exact same call signature and adds cross-cutting behavior around it — a mechanical, syntax-friendly operation that Python elevated to `@` syntax (and Java elevated to annotations processed by AOP frameworks). Adapter and Facade both involve translating between genuinely *different* interfaces or bundling *multiple* dependencies — that's a design decision requiring a real class with real logic, not a mechanical wrap, so no language has made it a keyword.
**Follow-up trap:** *"Are Python decorators exactly the GoF Decorator pattern?"* — mostly yes for behavior-wrapping decorators (`@retry`, `@cached`), but Python decorators are also used for pure metadata/registration (`@app.route("/users")`, `@dataclass`) with no wrapping of behavior at all — that use is closer to reflection/registration than the GoF pattern, and conflating the two is a common but incorrect simplification.

### Q5 — Your ORM's lazy-loading proxies are causing an N+1 query storm in production. Diagnose and fix.
**Testing:** whether you can connect a named pattern to a real, common production bug.
**Answer:** Lazy-loading is implemented as a Proxy — accessing `order.customer` transparently triggers a fresh query if the customer wasn't eager-loaded. Iterating over 1,000 orders and touching `.customer` on each triggers 1,000 individual queries. Fix: explicit eager loading on the hot path (`joinedload`/`selectinload` in SQLAlchemy, `.Preload()` in GORM, `JOIN FETCH` in JPQL) so the proxy resolves from an already-populated result set instead of triggering N round trips.
**Follow-up trap:** *"Why not just always eager-load everything?"* — over-fetching wastes bandwidth and memory on paths that don't need the related data; lazy-loading is the right default for infrequently-accessed relations, and the discipline is choosing eager-loading deliberately on measured hot paths, not applying either strategy universally.

### Q6 — Design the integration layer for a service that must support 3 different LLM providers (OpenAI, Anthropic, a local vLLM server) behind one internal call.
**Testing:** applying Adapter to the candidate's actual domain (AI/agentic systems).
**Answer:** An `LLMClient` interface/Protocol with `generate(prompt, **kwargs) -> Response`, and one Adapter per provider translating each SDK's request/response shape (different auth, different streaming formats, different token-usage field names) into the common interface. This confines provider-specific breaking changes (a frequent occurrence given how fast these SDKs evolve) to one adapter file each, and lets a router/fallback-chain layer sit above the interface without knowing which provider is underneath — the same reasoning as the resilience catalogue's fallback chains, composed with Adapter for provider-agnosticism.
**Follow-up trap:** *"What if the providers have genuinely different capabilities (one supports function calling, one doesn't)?"* — Adapter can't paper over a capability gap; that's a case for a capability-detection layer (a small registry saying which adapters support which features) rather than pretending the interfaces are identical when they aren't. Silently no-op'ing an unsupported feature in the adapter is a common, dangerous mistake.

### Q7 — What's wrong with a Facade class that has grown to 40 public methods and imports from 15 other modules?
**Testing:** recognizing pattern misuse/God Object drift.
**Answer:** It has stopped being a thin orchestration layer and become a God Object wearing a Facade's name — the tell is that a facade should mostly delegate (call into subsystem components) rather than contain its own business logic, conditionals, and state. The fix is splitting it along actual subsystem boundaries (an `OrderFacade`, a `RefundFacade`, a `ReportingFacade`) rather than one `StoreFacade` that does everything.
**Follow-up trap:** *"Isn't a big Facade just... your service's API?"* — a service's public API can legitimately have many endpoints, but each individual facade method should stay a thin composition of calls to well-scoped internal components; the red flag is business logic and multi-step conditionals living directly inside facade methods rather than in the components they delegate to.

### Q8 — When is Bridge actually justified, versus just being over-engineering?
**Testing:** recognizing the rarest structural pattern and its real trigger condition.
**Answer:** Bridge is justified only when you have two hierarchies that both need to vary independently and would otherwise multiply into an N×M subclass explosion — e.g., N shape types × M rendering backends. If there's only one implementation on one side (only ever raster rendering), you don't need Bridge; a plain interface with a single implementation, swapped later via DI if a second implementation ever appears, is enough.
**Follow-up trap:** *"How is this different from Strategy?"* — structurally almost identical (compose an interface, swap the implementation); the distinction is intent — Bridge exists specifically to prevent a combinatorial explosion across two hierarchies, Strategy exists to make one algorithm swappable. In practice, many engineers correctly implement "Bridge" and call it Strategy or just "dependency injection," and that's fine — the label matters less than recognizing the N×M explosion risk.

### Q9 — Why is Flyweight rarely needed explicitly in Python or the JVM?
**Testing:** knowing what the runtime already does for you.
**Answer:** Both runtimes already flyweight the most common cases automatically: Python caches small integers (-5 to 256) and interns some string literals; the JVM has a string pool (`String.intern()`) and caches boxed `Integer` values in the same range. Building a custom Flyweight pool is worth the code only when your domain objects are larger than these primitives and profiling shows real memory pressure from millions of near-duplicate instances — tokenizer vocabularies, font glyph caches, game-world tile types.
**Follow-up trap:** *"Would you add a Flyweight pool for request-scoped cache keys?"* — no; request-scoped data is, by definition, not shared/immutable across the pool's lifetime, so Flyweight (which requires the cached state to be genuinely shared and immutable — "intrinsic state") is the wrong tool; that's a job for a regular TTL cache instead.

### Q10 — Rank the 7 structural patterns by how often you'd expect to find one, unnamed, in a typical production backend service.
**Testing:** calibration — do you know which patterns are common infrastructure versus rare specialty tools.
**Answer:** Most common: Decorator (every middleware chain, every `@decorator`), Proxy (every ORM lazy-load, every cache wrapper), Adapter (every vendor SDK wrapper), Facade (every service's public API layer). Less common but real: Composite (nested rules/trees, when the domain is genuinely recursive). Rare: Bridge (mostly GUI toolkits, driver abstraction layers), Flyweight (mostly runtime-internal or specialty high-volume-object domains). Interviewers expect you to name the top four unprompted and correctly flag the bottom two as situational.
**Follow-up trap:** *"Why is this ranking the inverse of how often the categories are taught?"* — textbooks give equal airtime to all 7 for completeness; production code doesn't distribute evenly because Decorator/Proxy/Adapter/Facade solve problems (cross-cutting behavior, access control, vendor isolation, subsystem simplification) that occur constantly, while Bridge/Flyweight solve narrower problems (N×M hierarchy explosion, extreme object-count memory pressure) that most services never actually encounter.

---

## Red flags that fail you

- Calling every wrapper class "an Adapter" without distinguishing it from Facade, Decorator, or Proxy.
- Building a hand-rolled Flyweight pool as a first response to a memory problem, before profiling.
- Not recognizing a caching ORM relationship as a Proxy, or an N+1 storm as its classic failure mode.
- Presenting Bridge as a common, everyday pattern rather than a rare one triggered by an N×M hierarchy explosion.
- A Facade with business logic and conditionals living inside it, described as "just an API layer."
- Stacking decorators without being able to explain why the order matters.
- Claiming direct SDK calls scattered through the codebase are fine "because we'll only ever use one vendor."

---

## Cheat card

```
7 STRUCTURAL PATTERNS
  Adapter     translate interface A → B. Isolates vendor SDK churn to ONE file.
  Facade      one simple interface hiding a subsystem. = a well-designed service API.
              FAILS when it absorbs business logic → becomes a God Object.
  Decorator   same interface, ADDS behavior, STACKABLE. Order is NOT commutative.
              Python @decorator IS this pattern (behavior-wrapping use, not registration use).
  Proxy       same interface, CONTROLS access (lazy load / cache / auth / rate limit).
              ORM lazy-load proxy → classic N+1 query storm if not eager-loaded on hot paths.
  Composite   recursive tree, uniform interface for leaf AND branch. Needs cycle/depth guard.
  Bridge      RARE. Only when 2 hierarchies must vary independently (avoids NxM explosion).
              Structurally = Strategy; differs only in INTENT.
  Flyweight   RARE. Share immutable intrinsic state across many objects to cut memory.
              Runtime already does this: Python small-int cache, JVM string pool.
              Reach for it only after profiling shows real pressure.

ADAPTER vs FACADE vs DECORATOR vs PROXY — same-interface? new-behavior?
  Adapter:    interface CHANGES,  no new behavior        → compatibility
  Facade:     interfaces SIMPLIFY (many→one), no new behavior → simplicity
  Decorator:  interface SAME,     ADDS behavior, stacks   → extension
  Proxy:      interface SAME,     CONTROLS access         → control

TOP 4 BY FREQUENCY IN REAL BACKENDS: Decorator, Proxy, Adapter, Facade.
BOTTOM 2, RARE: Bridge, Flyweight.

INFRA-SCALE VERSIONS: Envoy sidecar = industrial Proxy. API gateway = industrial Facade.
```

## Sources

- [Design Patterns: Elements of Reusable Object-Oriented Software — Gamma, Helm, Johnson, Vlissides (1994)](https://en.wikipedia.org/wiki/Design_Patterns) — accessed 2026-07-26
- [Design Patterns in Dynamic Programming — Peter Norvig, 1996](https://norvig.com/design-patterns/) — accessed 2026-07-26
- [Design Patterns | Hello Interview Low Level Design](https://www.hellointerview.com/learn/low-level-design/in-a-hurry/patterns) — accessed 2026-07-26
- [Which Are the 23 GOF Design Patterns & their Uses? — It Interview Guide](https://itinterviewguide.com/gof-design-patterns/) — accessed 2026-07-26
- [Top Design Patterns Interview Questions for 2026 — Guvi](https://www.guvi.in/blog/top-design-patterns-interview-questions/) — accessed 2026-07-26

## Changelog
- 2026-07-28 — created
