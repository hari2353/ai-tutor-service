# GoF Creational Patterns in Python/Java/Go

> **Track:** T21 Architecture & Design Principles · **Time:** 1.5h · **Prereqs:** T21-solid, T21-grasp-dry-kiss · **Updated:** 2026-07-26
> **Module id:** `T21-gof-creational` · **Tags:** patterns

## The 30-second version

The five creational patterns — Singleton, Factory Method, Abstract Factory, Builder, Prototype — all solve one problem: decoupling *what gets constructed* from *the code that uses it*, so construction logic can change without rippling through callers. Three of them have mostly dissolved into language features: Singleton is a module-level object or a DI container's scope, not a class with a private constructor; Prototype is `copy.deepcopy` or a clone constructor, rarely a named pattern; Factory Method survives mostly as "a function that returns different subtypes based on input." The two that are still genuinely load-bearing in 2026 are Abstract Factory (families of related objects that must stay consistent — client SDKs, cross-cloud provisioning, cross-database drivers) and Builder (objects with many optional parameters, especially where you want immutability and validation at the end, which is why the pattern reappears as fluent config objects, Pydantic models with `model_construct`, and Go's functional-options idiom). The honest interview answer is not "here are the five patterns" — it's "here's which of these a modern codebase should still name explicitly, and which are now just how the language works."

## Why this gets asked

Because pattern-name recitation is the easiest thing to fake and the easiest thing to catch. An interviewer who has shipped for a decade has watched a `SingletonManager` class cause a flaky test suite (shared mutable state across test runs) and a 200-line `AbstractWidgetFactoryFactory` hierarchy that existed to support a second implementation that never shipped. They ask this to find out whether you reach for a pattern because it fits, or because you read a book. The senior signal is naming the modern replacement before you're asked, and being willing to say "you don't need a pattern for this, just a dict of constructors."

---

## Lineage: past → present → future

**What came before.** The *Design Patterns* book (Gamma, Helm, Johnson, Vlissides — "the Gang of Four" — 1994) codified idioms that C++ and Smalltalk programmers were already hand-rolling because those languages had no first-class functions, no default arguments, no keyword arguments, and weak module systems. Every creational pattern is, in large part, a workaround for a class-based language with none of those features. Factory Method exists because C++ has no way to return "a function that builds a Dog or a Cat depending on a flag" without wrapping it in an object with a virtual method. Builder exists because C++/Java have no keyword arguments, so a constructor with nine optional parameters becomes an unreadable positional call, and the pattern gives you named, staged construction instead. Singleton exists because those languages have no first-class module-level state — a Python module is already a singleton by construction, C++ has no equivalent without a static local or a global.

**Where it stands now.** The live consensus, confirmed by two decades of "patterns are missing language features" commentary (most influentially Peter Norvig's 1996 "Design Patterns in Dynamic Programming" talk, which showed 16 of the 23 GoF patterns become invisible or trivial in Lisp/Dylan), is that in Python, Go, and modern Java (records, sealed interfaces, `var`, lambdas) several of these patterns are either a code smell if implemented as a named class hierarchy, or so lightweight they don't deserve the ceremony. The disagreement that is still live: whether Abstract Factory is a real pattern or just "dependency injection with extra steps" — practitioners building genuinely multi-backend systems (cloud-provider abstraction layers, multi-database ORMs) argue it earns its keep; practitioners who've only ever targeted one backend see it as premature abstraction, and they are usually right about their own codebase. Singleton in particular has had its reputation reversed: it was taught in 1994 as *the* pattern to know, and by the 2010s it was widely taught as *the* pattern to avoid, because global mutable state is exactly what makes unit tests flaky and concurrent code prone to lock contention.

**Where it's heading.** High confidence: creational-pattern *names* will keep fading from vocabulary in dynamic and functional-leaning codebases while the *problems* they solved (controlling instance lifetime, validating multi-field construction, swapping implementation families) remain permanently real and get solved with language-native tools — dataclasses/Pydantic validators, DI container scopes (`@lru_cache` in FastAPI, Spring `@Scope`, Go's `sync.Once` wrapped in an explicit constructor), and functional options. Lower confidence, more speculative: as LLM-generated code becomes a larger fraction of what gets written and reviewed, GoF names may persist longer than they otherwise would simply because they're a compact, widely-trained vocabulary for an LLM to describe intent in a code review comment — "this reads like it wants to be a Builder" is a fast way to communicate a refactor, even if nobody writes a class called `Builder`.

---

## Mental model

```
CREATIONAL PATTERNS = answers to "who decides what gets built, and how?"

  Singleton         one instance, globally reachable       → module / DI scope
  Factory Method     subclass decides which concrete type   → a function with a match/switch
  Abstract Factory   a FAMILY of related objects, consistent → one function returning a bundle
                     with each other (don't mix Windows          of related constructors
                     button with Mac scrollbar)
  Builder            staged construction, many optional      → fluent API / kwargs / functional
                     params, validate only once complete          options
  Prototype          clone an existing configured object      → copy.deepcopy / clone()
                     instead of rebuilding from scratch
```

The one-line test for "do I need the named pattern, or just the language feature": **can I solve this with a function, a dict, and a dataclass?** If yes — which is true for the large majority of real cases in Python and Go — you don't need the GoF ceremony. Reach for the named pattern only when you have (a) a genuine family of implementations that must be swapped as a unit, or (b) construction with enough optional state and invariants that a plain constructor call becomes unreadable or unsafe.

---

## How it actually works

### Singleton — usually a mistake, here's why and the one legitimate use

The classic textbook form:

```python
class Config:
    _instance = None
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance
```

This is almost always the wrong tool in 2026. It hides a global in a design that *looks* like ordinary object construction, which means every caller of `Config()` believes they're creating something when they're actually reaching into shared mutable state. Consequences that show up in real codebases: unit tests that pass individually and fail in a suite (state leaks between tests because nobody reset it), a threading bug where two requests read/write the same in-memory cache without synchronization because "it's just a class," and an inability to have two configurations in the same process (multi-tenant workers, blue/green feature testing).

The legitimate need — "I want exactly one of this expensive resource" — is real (a DB connection pool, a model loaded into GPU memory). The fix is not the GoF pattern, it's **making the single-instance decision visible and owned by the composition layer**, not implicit in the class:

```python
# Python: module-level singleton, or an explicit provider with caching
from functools import lru_cache

@lru_cache(maxsize=1)
def get_db_pool() -> ConnectionPool:
    return ConnectionPool(dsn=settings.DATABASE_URL)
```

```java
// Java/Spring: scope is a config decision, not baked into the class
@Bean
@Scope("singleton")   // the default scope, made explicit
public DataSource dataSource() { return new HikariDataSource(config); }
```

```go
// Go: sync.Once for genuine one-time init, but still constructed and injected explicitly
var (
    poolOnce sync.Once
    pool     *sql.DB
)

func GetPool() *sql.DB {
    poolOnce.Do(func() { pool, _ = sql.Open("postgres", dsn) })
    return pool
}
```

The difference that matters: in all three, the "singleton-ness" is a property of *how the object is wired into the application* (a DI scope, a cached provider, a package-level var), not a property baked into the type itself via a private constructor. That means tests can construct a fresh instance trivially, and nothing prevents a second instance existing if you genuinely need one later (e.g., per-tenant pools).

**Verdict: usually a mistake as a named class pattern. The underlying need (single shared instance) is real and common; solve it with DI scope or a cached provider, never with a private constructor and a static `getInstance()`.**

### Factory Method — mostly just a function now

Classic form: an abstract creator class with a `createProduct()` method that subclasses override.

```python
# GoF-style class hierarchy — unnecessary ceremony in Python
class DocumentCreator(ABC):
    @abstractmethod
    def create(self) -> Document: ...

class PDFCreator(DocumentCreator):
    def create(self) -> Document: return PDFDocument()

# Idiomatic Python — a function and a dict
def create_document(kind: str) -> Document:
    return {"pdf": PDFDocument, "docx": DocxDocument, "html": HtmlDocument}[kind]()
```

Java, lacking first-class functions until relatively late (lambdas arrived in Java 8, 2014) and still lacking Python-style default/keyword arguments, is the one language of the three where the class-based version still shows up idiomatically, but even there it's usually collapsed to a `Map<String, Supplier<Document>>` registry rather than a subclass hierarchy.

```java
Map<String, Supplier<Document>> creators = Map.of(
    "pdf", PdfDocument::new,
    "docx", DocxDocument::new
);
Document doc = creators.get(kind).get();
```

```go
// Go: no inheritance at all, so this was always a function-and-switch,
// never a class hierarchy — Go never had the problem GoF was solving here.
func NewDocument(kind string) Document {
    switch kind {
    case "pdf":  return &PDFDocument{}
    case "docx": return &DocxDocument{}
    default:     panic("unknown kind")
    }
}
```

**Verdict: absorbed into the language everywhere. First-class functions and maps make the class hierarchy pure overhead.** Keep the *name* for communication ("this needs a factory method here") without building the class ceremony.

### Abstract Factory — one of the two survivors

The one creational pattern that still earns its keep: producing a **family** of related objects that must be mutually consistent, where mixing members from different families is a bug. Classic UI toolkit example (Windows vs Mac widgets); modern real example: a multi-cloud provisioning layer where you must never construct an AWS `Bucket` alongside a GCP `Topic` inside the same deployment target.

```python
from abc import ABC, abstractmethod

class CloudFactory(ABC):
    @abstractmethod
    def storage(self) -> "ObjectStore": ...
    @abstractmethod
    def queue(self) -> "MessageQueue": ...

class AWSFactory(CloudFactory):
    def storage(self) -> "ObjectStore": return S3Store()
    def queue(self) -> "MessageQueue": return SQSQueue()

class GCPFactory(CloudFactory):
    def storage(self) -> "ObjectStore": return GCSStore()
    def queue(self) -> "MessageQueue": return PubSubQueue()

def get_cloud_factory(provider: str) -> CloudFactory:
    return {"aws": AWSFactory(), "gcp": GCPFactory()}[provider]
```

```go
// Go: interfaces make this natural without an explicit "factory" class name at all —
// a constructor function returning a struct of interfaces IS the abstract factory.
type CloudFactory interface {
    Storage() ObjectStore
    Queue() MessageQueue
}

func NewCloudFactory(provider string) CloudFactory {
    switch provider {
    case "aws": return awsFactory{}
    case "gcp": return gcpFactory{}
    default:    panic("unknown provider")
    }
}
```

The reason this survives where Factory Method doesn't: the *coherence constraint across multiple products* is the actual value, not the dispatch mechanism. A dict-of-constructors gives you dispatch; it doesn't give you the compile-time (Go, Java) or structural (Python duck typing) guarantee that all the pieces you get back belong to the same family.

**Verdict: still legitimate, but only when there are genuinely 2+ backend families each producing multiple coupled objects. For a single product type, this collapses back to Factory Method — don't reach for Abstract Factory just because you have "a factory."**

### Builder — the other survivor, now usually invisible

Classic Java form (fluent builder, because Java has no keyword arguments):

```java
Pizza pizza = new Pizza.Builder()
    .size(Size.LARGE)
    .addTopping(Topping.MUSHROOM)
    .addTopping(Topping.OLIVE)
    .crust(Crust.THIN)
    .build();  // validation happens here, once, on a fully-specified object
```

This exists specifically because Java has no keyword arguments — the alternative is a telescoping constructor (`Pizza(size, crust, cheese, topping1, topping2, ...)`) that is unreadable and error-prone at a call site (which boolean was `extraCheese` again?). In Python and modern Go, the same problem barely needs the named pattern:

```python
# Python: keyword arguments + a validating dataclass IS the builder,
# the ceremony of a separate .build() step is rarely needed
from dataclasses import dataclass

@dataclass(frozen=True)
class Pizza:
    size: Size
    crust: Crust = Crust.THIN
    toppings: tuple[Topping, ...] = ()

    def __post_init__(self):
        if len(self.toppings) > 5:
            raise ValueError("max 5 toppings")

pizza = Pizza(size=Size.LARGE, toppings=(Topping.MUSHROOM, Topping.OLIVE))
```

Where Python *does* still reach for a real builder is when construction is genuinely staged across multiple calls with intermediate mutable state before a final immutable object is produced — `httpx.Client()` config, SQL query builders (SQLAlchemy's `select().where().order_by()`), and Pydantic's `model_construct` for two-phase validation. Go, lacking both keyword arguments and default values, uses the **functional options** idiom, which is Builder wearing a different name:

```go
type ServerOption func(*Server)

func WithTimeout(d time.Duration) ServerOption { return func(s *Server) { s.timeout = d } }
func WithTLS(cfg *tls.Config) ServerOption      { return func(s *Server) { s.tls = cfg } }

func NewServer(addr string, opts ...ServerOption) *Server {
    s := &Server{addr: addr, timeout: 30 * time.Second} // sane defaults
    for _, opt := range opts {
        opt(s)
    }
    return s
}

srv := NewServer(":8080", WithTimeout(5*time.Second), WithTLS(tlsCfg))
```

**Verdict: still genuinely useful, but the implementation has moved. Java: fluent builder class. Python: keyword args + validating dataclass/Pydantic model, occasionally a real staged builder for multi-step construction. Go: functional options. All three are solving the same problem — optional parameters, validated once, without a telescoping constructor — with syntax the language actually gives you.**

### Prototype — clone, don't rebuild

Classic form: a `clone()` method so you copy a configured object instead of re-running expensive setup.

```python
import copy

template_request = HttpRequestConfig(timeout=30, retries=3, headers={"Accept": "json"})
per_call_request = copy.deepcopy(template_request)
per_call_request.headers["X-Request-Id"] = str(uuid4())
```

```java
// Java: Cloneable is famously broken (shallow by default, checked exception,
// no generics support) — most codebases use a copy constructor instead.
public Config(Config other) {
    this.timeout = other.timeout;
    this.headers = new HashMap<>(other.headers);   // explicit deep copy where it matters
}
```

```go
// Go: no built-in clone; either a manual copy constructor
// or, for simple structs with no pointers/slices/maps, a plain value assignment
// already deep-copies because Go structs are value types.
func (c Config) Clone() Config {
    clone := c
    clone.Headers = maps.Clone(c.Headers)   // only needed for reference-like fields
    return clone
}
```

The one place Prototype is still a named, deliberate architectural choice rather than an incidental `copy()` call: object pools and expensive-to-construct templates in game engines, simulation frameworks, and ML feature-pipeline configs, where you build one canonical, fully-validated config once and clone-and-mutate per request instead of paying construction cost N times.

**Verdict: absorbed into `copy.deepcopy` / copy constructors / value semantics almost everywhere. Worth naming explicitly only when cloning a validated template is meaningfully cheaper than reconstructing, and you want that intent visible in the code.**

---

## Build it from scratch

A compact demonstration that ties Builder + Abstract Factory together, the two survivors, in one runnable Python snippet (`# untested sketch` for the surrounding CLI, but the class logic below runs as written):

```python
from dataclasses import dataclass, field
from typing import Protocol

class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> None: ...

class MessageQueue(Protocol):
    def publish(self, topic: str, payload: bytes) -> None: ...

@dataclass(frozen=True)
class PipelineConfig:
    """Builder collapsed into a validating dataclass — the Python idiom."""
    name: str
    batch_size: int = 100
    max_retries: int = 3
    tags: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self):
        if self.batch_size <= 0:
            raise ValueError("batch_size must be positive")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")


class CloudFactory(Protocol):
    def storage(self) -> ObjectStore: ...
    def queue(self) -> MessageQueue: ...


class AWSFactory:
    def storage(self) -> ObjectStore: return _FakeStore("s3")
    def queue(self) -> MessageQueue: return _FakeQueue("sqs")


class GCPFactory:
    def storage(self) -> ObjectStore: return _FakeStore("gcs")
    def queue(self) -> MessageQueue: return _FakeQueue("pubsub")


_FACTORIES: dict[str, CloudFactory] = {"aws": AWSFactory(), "gcp": GCPFactory()}

def build_pipeline(provider: str, cfg: PipelineConfig) -> tuple[ObjectStore, MessageQueue]:
    factory = _FACTORIES[provider]           # abstract factory: guarantees a matched family
    return factory.storage(), factory.queue()
```

This is the shape almost every "we need patterns here" conversation in a real codebase resolves to: a validating config object (Builder's job, done by `dataclass`/Pydantic) plus a small registry that guarantees family coherence (Abstract Factory's job, done by a dict and a Protocol).

---

## How it's done in production

| Pattern | Where it shows up in real frameworks |
|---|---|
| Singleton | Spring `@Scope("singleton")` (the default bean scope), FastAPI `Depends` + `@lru_cache`, Go `sync.Once` |
| Factory Method | `json.loads(object_hook=...)`, SQLAlchemy's `registry.map_imperatively`, Go's `http.NewRequest` |
| Abstract Factory | Boto3's per-service client factories (`boto3.client("s3")` vs `boto3.client("sqs")` sharing a session/credential family), database driver abstraction layers (SQLAlchemy dialects), Kubernetes client-go's scheme/codec factories |
| Builder | `sqlalchemy.select().where().order_by()`, `httpx.Client(timeout=..., limits=...)`, gRPC's `grpc.ServerOptions`, Go's `http.Client` functional options via community libraries |
| Prototype | Kubernetes object templates (`DeepCopy()` generated on every API type), ML config templates cloned per experiment (Hydra, OmegaConf) |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Test suite passes alone, fails in CI batch | Singleton holding mutable state across tests | Replace with a fixture-scoped provider; reset or re-instantiate per test |
| Deadlock or race under load on "the config object" | Singleton mutated concurrently without synchronization | Make it immutable after construction, or add explicit locking, or scope per-request instead of per-process |
| `AbstractWidgetFactory` hierarchy with one real implementation | Abstract Factory built for a family that never materialized (YAGNI violation) | Collapse to a plain constructor; reintroduce the factory when a second family actually ships |
| Telescoping constructor call sites with unlabeled booleans | No Builder / no keyword-argument discipline | Force keyword-only arguments (`*` in Python, named params convention in Go) or add a builder/options type |
| Two "cloned" objects mutate each other unexpectedly | Shallow copy where fields contain mutable containers (dicts, lists) | Use `copy.deepcopy`, or explicit field-by-field deep copy for reference types only |
| `getInstance()` called from 40 files, refactor to per-tenant instance takes 3 days | Singleton-ness baked into the class instead of the wiring layer | Should have been a cached provider from day one; the fix now is a mechanical but wide refactor to inject the instance instead of calling a static getter |

---

## Tradeoffs & when NOT to use it

- **Do not build a Singleton class with a private constructor.** If you need one shared instance, make that a property of dependency wiring (a cached provider, a DI scope), not of the type itself. The class-based Singleton is the single most-flagged anti-pattern in this catalogue precisely because it looks like good OOP while quietly introducing global state.
- **Do not build an Abstract Factory for a family of one.** If you only ever target Postgres, an `AbstractDatabaseFactory` with a single `PostgresFactory` implementation is pure ceremony — YAGNI. Introduce it when the second backend is real, not speculative.
- **Do not build a fluent Builder class in Python or modern Go.** Keyword arguments plus a validating dataclass/Pydantic model or functional options give you everything the Builder pattern gives Java, with less code and no `.build()` ceremony. A fluent builder in Python is usually someone translating Java habits directly rather than using the language.
- **Factory Method as a class hierarchy is almost never justified** outside of frameworks that need users to *override* creation behavior via subclassing (e.g., Django's `get_queryset()`, Django REST Framework's `get_serializer_class()`) — there, the "factory method" is genuinely a template-method-style extension point, not a standalone creational pattern.
- **Prototype is wrong when construction has meaningful side effects** (opening a connection, registering with a service discovery system) — cloning an object that holds a live connection copies the reference, not a fresh connection, and you get two logical objects sharing one socket.
- **The strongest senior signal across all five:** naming which pattern a piece of code is *conceptually* doing (for communication with the team) while not necessarily implementing it as a named class (for the actual code). "This is a builder" is a useful sentence in a design review even when the code is three keyword arguments.

---

## Interview questions

### Q1 — Implement a thread-safe Singleton. What's wrong with the double-checked locking version?
**Testing:** whether you know the classic Java gotcha and whether you'd even reach for this today.
**Answer:** Naive lazy init (`if instance == null: instance = new X()`) races under concurrent first access, potentially constructing two instances. Double-checked locking fixes it but requires the field to be `volatile` in Java (pre-Java 5, without `volatile`, a partially-constructed object could be visible to another thread due to instruction reordering — this was a real, widely-cited bug class). In 2026, prefer static initialization (JVM guarantees class-init is thread-safe) or, better, don't build a Singleton class at all — use a DI container's singleton scope or, in Python, `functools.lru_cache` on a provider function, which sidesteps the whole problem.
**Follow-up trap:** *"So would you ever hand-write this?"* — only in a language/runtime with no DI container and no module-level state (rare), or when asked to demonstrate understanding in an interview. In real code, reach for the framework's scoping mechanism.

### Q2 — Why is Singleton considered an anti-pattern by many senior engineers today?
**Testing:** whether you understand the *reasons*, not just the reputation.
**Answer:** It hides global mutable state behind what looks like ordinary object construction, which breaks test isolation (state leaks between tests), makes concurrent access a shared-mutable-state problem disguised as a class, and makes it structurally hard to have two instances later (multi-tenancy, blue/green configs) without a wide refactor. The functionality it provides — "exactly one shared instance" — is legitimate; the mechanism (baking it into the type via private constructor) is the problem.
**Follow-up trap:** *"What would you use instead?"* — a cached provider (`@lru_cache`, Spring singleton-scoped bean) or an explicitly constructed instance passed via dependency injection. The difference: the single-instance decision lives in the composition root, not in the class.

### Q3 — When is Abstract Factory actually worth the extra layer over a plain factory function?
**Testing:** whether you understand the coherence guarantee, not just the dispatch mechanism.
**Answer:** When you're producing multiple related objects that must belong to the same family and mixing members across families is a bug — e.g., an S3 client paired with an SQS queue must not accidentally get paired with a GCS client. A single factory function gives you dispatch on one product; Abstract Factory additionally guarantees the *set* of products you get back is internally consistent.
**Follow-up trap:** *"Our codebase only targets AWS. Should we build this now?"* — no. Building it for a family of one is speculative YAGNI; introduce it when the second backend is real and you can see the actual coherence constraint, not before.

### Q4 — Write a Builder in Java, then show the Python equivalent, and explain why they differ.
**Testing:** cross-language transfer, the actual point of this module.
**Answer:** Java's fluent builder exists because Java has no keyword arguments — a constructor with 8 optional parameters is unreadable and error-prone positionally, so you stage construction through named setter-like methods and validate once in `.build()`. Python has keyword arguments and default values natively, so the same problem is solved with a dataclass/Pydantic model plus `__post_init__`/validators — no separate builder object needed unless construction is genuinely multi-step with intermediate mutable state (e.g., a query builder).
**Follow-up trap:** *"What does Go do, since it has neither keyword args nor a Builder-friendly OOP model?"* — functional options: variadic `...Option` parameters where each `Option` is a function mutating the struct being built, giving named, optional, defaulted construction without keyword arguments or inheritance.

### Q5 — What does Peter Norvig's "Design Patterns in Dynamic Languages" argument actually claim, and is it right?
**Testing:** whether you've engaged with the strongest counter-argument to memorizing the GoF catalogue.
**Answer:** Norvig's 1996 talk argued that roughly 16 of the 23 GoF patterns become invisible, trivial, or built into the language in Lisp/Dylan because those languages have first-class functions, closures, and multiple dispatch — the patterns exist specifically to work around C++/Smalltalk's lack of those features. It's substantially right for the creational patterns: Factory Method collapses to a function, Builder mostly collapses to keyword arguments, Prototype collapses to a copy function. It's less complete for patterns whose value is structural coordination rather than missing syntax (Abstract Factory, and in the structural/behavioral categories, Observer and Iterator retain real value even in dynamic languages).
**Follow-up trap:** *"So should we stop teaching GoF?"* — no; the *vocabulary* is still useful for communication ("this wants to be a builder") even when the *implementation* doesn't need the class ceremony. The mistake is treating the 1994 implementations as the goal rather than the problem statements.

### Q6 — Your team has a `ConnectionFactory` class with one subclass, `PostgresConnectionFactory`, and a comment saying "add MySQL support here later." Red flag?
**Testing:** YAGN recognition in a creational-pattern context.
**Answer:** Yes — this is speculative generality. The abstraction is being paid for (extra indirection, an interface to maintain, a harder-to-follow call path) before there's a second implementation to justify it. The fix isn't necessarily deleting it immediately, but the interview answer should recognize the smell and propose collapsing it to a plain `PostgresConnection` constructor until MySQL support is a real, scheduled piece of work.
**Follow-up trap:** *"What if the interface makes testing easier via a fake implementation?"* — that's a legitimate reason to keep an interface (a `ConnectionFactory` Protocol/interface with a real Postgres implementation and a test fake), but that's testability-driven abstraction, not Abstract-Factory-family-coherence — a subtly different justification worth naming explicitly.

### Q7 — Explain the difference between Factory Method and Abstract Factory precisely.
**Testing:** whether the two names are actually distinct in your head or memorized together.
**Answer:** Factory Method produces **one** product, and the "pattern" is that a subclass or parameter decides which concrete type. Abstract Factory produces a **family of related products** (two or more) that must be consistent with each other; the factory itself is often implemented using Factory Methods internally, one per product in the family. In short: Factory Method is one factory method; Abstract Factory is an interface bundling several factory methods that must agree.
**Follow-up trap:** *"Give a case where you'd refactor a Factory Method into an Abstract Factory."* — when a second related product that must match the first is added: you start with `create_document(kind)`, and once you also need a matching `create_exporter(kind)` that must use the same file format assumptions as the document, bundling both behind one factory interface prevents a caller from mismatching a PDF document with an HTML exporter.

### Q8 — What's wrong with Java's `Cloneable` interface, and how does that inform how you'd implement Prototype today?
**Testing:** depth on a specific, well-known language wart.
**Answer:** `Cloneable` is a marker interface with no methods; `Object.clone()` is `protected`, does a shallow copy, can throw a checked `CloneNotSupportedException` even though every sane implementation supports it, and doesn't compose with generics or final fields cleanly. Most production Java code uses a copy constructor or a static factory (`Config.copyOf(other)`) instead, giving explicit control over what gets deep-copied.
**Follow-up trap:** *"Does Python's `copy.deepcopy` have the same problems?"* — mostly not, because it recursively copies via a general protocol (`__deepcopy__`/`__reduce__`) rather than a broken shallow default, but it can be slow for large object graphs and can loop infinitely on cyclic references without `memo` handling (which `deepcopy` does provide via its internal memo dict) — know that `deepcopy` handles cycles correctly by default, unlike a naive recursive copy you might hand-write.

### Q9 — A junior engineer proposes a `LoggerFactory` returning `Logger` instances, mirroring `log4j`. Is that a real Factory Method or over-engineering for a Python service?
**Testing:** judgment about when a pattern from another ecosystem doesn't translate.
**Answer:** In Python, `logging.getLogger(name)` already *is* this — the standard library provides a caching factory function keyed by logger name. Wrapping it in a custom `LoggerFactory` class adds a layer with no new behavior. This is a case of importing a Java idiom (`LoggerFactory.getLogger(MyClass.class)`) that exists because Java historically needed a class-based entry point for a static utility; Python's module-level function already does the job.
**Follow-up trap:** *"When would a custom logger factory be justified?"* — if you need to inject cross-cutting behavior at creation time that the stdlib doesn't support directly — e.g., auto-attaching a request-scoped correlation ID to every logger, or routing to a different backend per environment — a thin wrapper function (not a class hierarchy) is reasonable.

### Q10 — Design the object-construction strategy for a multi-tenant SaaS backend that needs a different storage backend (S3, Azure Blob, local disk for on-prem) per tenant, decided at request time.
**Testing:** whether you can compose these patterns into a real architectural decision, not just recite definitions.
**Answer:** Abstract Factory keyed by tenant configuration: a `StorageFactory` interface with `S3Factory`, `AzureFactory`, `LocalFactory` implementations, resolved once per request (or cached per tenant) from tenant config, not a process-wide Singleton — because different tenants need different, coexisting instances, which a Singleton structurally forbids. Construction parameters (bucket name, credentials, region) go through a validating config object (the Builder's job, done via Pydantic) so a malformed tenant config fails fast at construction rather than on first use. No Prototype needed unless per-request storage clients are expensive to construct and a validated template is cloned per request.
**Follow-up trap:** *"Where would a naive Singleton implementation break this design?"* — immediately: a Singleton storage client baked in as `StorageClient.getInstance()` can only ever point at one backend for the whole process, which is incompatible with per-tenant backend choice by definition. This is the clearest real-world argument against the Singleton-as-class-feature approach: the requirement to have *more than one* coexisting instance is common and the classic pattern actively prevents it.

---

## Red flags that fail you

- Implementing Singleton with a private constructor and `getInstance()` and presenting it as the modern answer, with no mention of DI scopes or cached providers.
- Building an Abstract Factory for a single implementation "in case we need another one later."
- Writing a fluent Java-style Builder class in Python instead of using keyword arguments and a validating dataclass.
- Confusing Factory Method and Abstract Factory, or using the names interchangeably.
- Claiming `Cloneable` in Java is a good API without knowing why it's broken (shallow copy, checked exception, no generics).
- Treating all 23 GoF patterns as equally relevant today with no discussion of which have dissolved into language features.
- Not being able to say, unprompted, that Singleton is usually a mistake.

---

## Cheat card

```
5 CREATIONAL PATTERNS — MODERN VERDICT
  Singleton         USUALLY A MISTAKE as a class. Need = real; mechanism wrong.
                    Fix: DI singleton scope / @lru_cache provider / sync.Once wiring, not private ctor.
  Factory Method     Absorbed → a function + dict/match. Java: Map<String,Supplier<T>>.
  Abstract Factory   SURVIVES when 2+ coherent product families exist (multi-cloud, multi-DB).
                    Dies to YAGNI if only one family ships.
  Builder            SURVIVES the PROBLEM, not the class. Py: kwargs + dataclass/Pydantic.
                    Go: functional options (...Option). Java: still a real fluent class (no kwargs).
  Prototype          Absorbed → copy.deepcopy / copy ctor / Go value semantics.
                    Named explicitly only for expensive-template cloning (configs, pooled objects).

KEY HISTORICAL FACT: Norvig 1996 — ~16/23 GoF patterns vanish or trivialize in a language
  with first-class functions + closures + multiple dispatch. Patterns = missing language features.

JAVA Cloneable IS BROKEN: shallow copy, protected clone(), checked exception, no generics.
  → use copy constructors / static copyOf() instead.

SINGLETON FAILURE MODE: flaky test suite (shared state across tests), races under
  concurrent mutation, can't support 2 coexisting instances (multi-tenant) without a rewrite.

RULE OF THUMB: can this be a function + a dict + a validated dataclass? If yes, skip the pattern class.
```

## Sources

- [Design Patterns: Elements of Reusable Object-Oriented Software — Gamma, Helm, Johnson, Vlissides (1994)](https://en.wikipedia.org/wiki/Design_Patterns) — accessed 2026-07-26
- [Design Patterns in Dynamic Programming — Peter Norvig, 1996](https://norvig.com/design-patterns/) — accessed 2026-07-26
- [Top Design Patterns Interview Questions for 2026 — Guvi](https://www.guvi.in/blog/top-design-patterns-interview-questions/) — accessed 2026-07-26
- [Top 50 Design Patterns Interview Questions and Answers for Experienced Developers (2026 Guide) — AssessArc](https://www.assessarc.com/blog/top-50-design-patterns-interview-questions-and-answers-for-experienced-developers-2026-guide) — accessed 2026-07-26
- [27 Advanced Design Patterns Interview Questions For Senior Developers — FullStack.Cafe](https://www.fullstack.cafe/blog/design-patterns-interview-questions) — accessed 2026-07-26
- [Effective Go: functional options pattern — golang.org](https://go.dev/doc/effective_go) — accessed 2026-07-26

## Changelog
- 2026-07-28 — created
