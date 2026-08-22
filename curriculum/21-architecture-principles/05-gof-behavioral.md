# GoF Behavioral Patterns in Python/Java/Go

> **Track:** T21 Architecture & Design Principles · **Time:** 2.0h · **Prereqs:** T21-gof-creational, T21-gof-structural · **Updated:** 2026-07-26
> **Module id:** `T21-gof-behavioral` · **Tags:** patterns

## The 30-second version

The eleven behavioral patterns — Chain of Responsibility, Command, Interpreter, Iterator, Mediator, Memento, Observer, State, Strategy, Template Method, Visitor — govern how objects communicate and hand off responsibility, and this is the category where "absorbed into the language" is most dramatic. Strategy in Python is a function passed as an argument, full stop — building a class hierarchy for it is a tell that someone learned patterns from Java. Iterator is a language keyword (`for`, generators, `yield`) in Python and Go's `range`, not a class you implement unless you're building a custom container. Visitor is what `match`/pattern matching (Python 3.10+, Go's type switches, Java's sealed interfaces + pattern matching since Java 21) does natively — the double-dispatch dance Visitor performs exists only because older languages lacked pattern matching. What survives with real, undiminished weight: Observer (every pub/sub system, every event bus, every reactive framework), State (any object whose behavior legitimately changes by lifecycle stage — orders, workflow engines, connection state machines), Command (every undo stack, every job queue, every CLI framework), Chain of Responsibility (every middleware pipeline, every validation chain), and Template Method (every framework hook method you override). Mediator, Memento, and Interpreter are the genuine rarities — real but narrow.

## Why this gets asked

Behavioral patterns are where interviewers separate "read the book" from "reads code for a living." Everyone can define Observer; the interviewer wants to know if you've hit its actual production failure — a listener that throws mid-notification and silently drops every subscriber after it, or a memory leak from a subscriber that never unsubscribed. They also use this category to test whether you over-apply patterns: proposing a full Visitor double-dispatch hierarchy in Python when a `match` statement does the same job in four lines is a real, common overengineering tell, and staff-level interviewers watch for exactly that instinct.

---

## Lineage: past → present → future

**What came before.** Behavioral patterns encode communication idioms that predate object orientation entirely — Observer traces to the Model-View-Controller architecture from Smalltalk-80 (Krasner & Pope, 1988), where "dependents" (views) needed to react to model changes without the model knowing about them. State and Strategy both formalize what procedural code did with a big `switch` or function pointer table; the pattern's contribution was making the swap-in-and-out structure explicit and open for extension without touching the switch statement (violating Open/Closed otherwise). Visitor is the most language-constrained of all of them: it exists specifically because C++/Java/Smalltalk-era languages had single dispatch (a method call resolves based on the *receiver's* type only) and no pattern matching, so operating differently based on *both* the node type in a tree/AST *and* the operation required a double-dispatch trick — `element.accept(visitor)` calls back `visitor.visitConcreteElement(element)` — purely to simulate multiple dispatch the language didn't support.

**Where it stands now.** The consensus, backed by two decades of dynamic-language practice, is that at least half of these patterns are now "just how you write the code" rather than named architectural decisions: Strategy is a function parameter, Iterator is a generator, Template Method is method overriding in any OOP language (barely a "pattern" so much as inheritance's basic mechanism). The live disagreement is around Visitor specifically: `match`/pattern matching genuinely replaces the *mechanics* of Visitor in languages that have it, but Visitor's other benefit — adding a new *operation* over a fixed set of types without touching any of those types' source files — still has real value in exactly the situation Visitor was designed for (a stable AST, many operations added over time: a compiler's parse tree visited by a type-checker, an optimizer, a code generator, each without modifying the node classes). Where the AST/type set is stable and the operations grow, Visitor (or its pattern-matching equivalent) still earns its keep; where the type set grows and operations are fixed, pattern matching without the visitor apparatus is strictly simpler.

**Where it's heading.** High confidence: pattern-matching language features (Python 3.10 `match`, Rust's `match`, Java's sealed interfaces + switch pattern matching finalized in Java 21) will keep displacing hand-written Visitor and State-machine boilerplate, because exhaustiveness checking (the compiler telling you "you forgot to handle this case") is strictly better than a missing visit method silently doing nothing. Observer is trending toward becoming infrastructure rather than in-process code — Kafka, EventBridge, and durable pub/sub systems are Observer's production-scale descendants, and the interesting engineering decisions have moved from "how do I implement Observer" to "at-least-once vs exactly-once delivery, ordering guarantees, and replay." Speculative: as agentic systems formalize multi-step workflows, Command (encapsulating an action as a first-class, serializable object) is quietly becoming the backbone of how agent tool-calls get logged, retried, and replayed — a tool call *is* a Command object (receiver, action, parameters, undo/compensating-action), and durable execution engines (Temporal, LangGraph checkpointers) are Command plus Memento at scale.

---

## Mental model

```
BEHAVIORAL PATTERNS = how do objects communicate and hand off responsibility?

  Chain of Responsibility   pass a request along a chain until someone handles it
  Command                   turn an action into an object (do/undo/queue/log it)
  Interpreter                represent a grammar as a class hierarchy, walk it to evaluate
  Iterator                   traverse a collection without exposing its internals
  Mediator                   centralize how a set of objects talk to each other
  Memento                    capture/restore an object's internal state (undo, snapshots)
  Observer                    one-to-many: notify dependents when subject changes
  State                       object's behavior changes based on its internal state
  Strategy                    swap an algorithm/behavior at runtime
  Template Method             skeleton algorithm in a base class, subclasses fill in steps
  Visitor                     add a new operation over a fixed set of types without touching them
```

The fast filter for "do I need the class-based version, or does my language already give me this":

| Pattern | Modern replacement |
|---|---|
| Strategy | a function/lambda parameter |
| Iterator | generator / `yield` / language `for` |
| Template Method | plain method overriding |
| Visitor | `match` / pattern matching / type switch |
| State | still a real pattern — the state machine explicitness has value |
| Observer | still a real pattern — often becomes a message bus at scale |
| Command | still a real pattern — the object-ness is the whole point (queue it, log it, undo it) |
| Chain of Responsibility | still a real pattern — often becomes middleware |
| Mediator, Memento, Interpreter | real but rare; situational |

---

## How it actually works

### Strategy — a function, not a hierarchy

Classic GoF form: an abstract `SortStrategy` with `BubbleSort`/`QuickSort` subclasses, injected into a `Sorter` context class.

```python
# Don't do this in Python:
class SortStrategy(ABC):
    @abstractmethod
    def sort(self, data: list) -> list: ...

class QuickSort(SortStrategy):
    def sort(self, data): return sorted(data)   # ... etc, pure ceremony

# Do this:
def sort_data(data: list, strategy: Callable[[list], list] = sorted) -> list:
    return strategy(data)

sort_data(prices, strategy=lambda xs: sorted(xs, reverse=True))
```

```go
// Go: a function type IS the strategy interface. No class hierarchy needed.
type PricingStrategy func(base float64, qty int) float64

func BulkDiscount(base float64, qty int) float64 {
    if qty > 100 { return base * 0.9 }
    return base
}

func CalculateTotal(base float64, qty int, strategy PricingStrategy) float64 {
    return strategy(base, qty) * float64(qty)
}
```

```java
// Java: since lambdas (Java 8, 2014), Strategy no longer needs a class hierarchy either --
// a functional interface is enough.
@FunctionalInterface
interface PricingStrategy { double price(double base, int qty); }

double total = calculateTotal(basePrice, qty, (base, qty2) -> qty2 > 100 ? base * 0.9 : base);
```

**Verdict: absorbed almost everywhere first-class functions exist — which by 2026 is every mainstream language.** Building a class hierarchy for Strategy today, in any of Python/Java/Go, is a smell unless you need to carry non-trivial state or configuration alongside the algorithm (in which case a small callable class, not an ABC hierarchy, is enough).

### State — the one that keeps its structure

Unlike Strategy, State genuinely benefits from the explicit class/enum-driven structure, because the point isn't just swapping behavior — it's making illegal transitions impossible or at least loud.

```python
from enum import Enum, auto

class OrderState(Enum):
    PENDING = auto(); PAID = auto(); SHIPPED = auto(); DELIVERED = auto(); CANCELLED = auto()

_VALID_TRANSITIONS = {
    OrderState.PENDING:   {OrderState.PAID, OrderState.CANCELLED},
    OrderState.PAID:      {OrderState.SHIPPED, OrderState.CANCELLED},
    OrderState.SHIPPED:   {OrderState.DELIVERED},
    OrderState.DELIVERED: set(),
    OrderState.CANCELLED: set(),
}

class Order:
    def __init__(self):
        self.state = OrderState.PENDING

    def transition(self, new_state: OrderState) -> None:
        if new_state not in _VALID_TRANSITIONS[self.state]:
            raise InvalidTransition(f"{self.state} -> {new_state} not allowed")
        self.state = new_state
```

This differs from Strategy in a way worth being precise about in an interview: Strategy is chosen by the *caller* per invocation; State is owned by the *object itself* and changes as a side effect of events over the object's lifetime. A well-implemented State pattern makes the valid-transition graph a first-class, checkable artifact (the dict above), which is exactly what workflow engines, order-management systems, and TCP's own state machine (`CLOSED → SYN_SENT → ESTABLISHED → ...`) all rely on.

```go
// Go: state machines are commonly explicit constants + a transition map,
// same idea, no inheritance needed.
type OrderState int
const (
    Pending OrderState = iota
    Paid
    Shipped
    Delivered
    Cancelled
)

var validTransitions = map[OrderState]map[OrderState]bool{
    Pending: {Paid: true, Cancelled: true},
    Paid:    {Shipped: true, Cancelled: true},
    Shipped: {Delivered: true},
}

func (o *Order) Transition(to OrderState) error {
    if !validTransitions[o.state][to] {
        return fmt.Errorf("invalid transition %v -> %v", o.state, to)
    }
    o.state = to
    return nil
}
```

**Verdict: still a real, valuable pattern. The value isn't the class hierarchy (GoF's per-state subclass with polymorphic `handle()` methods) — that part is often overkill — it's the explicit, checkable transition graph. A dict/map of valid transitions usually beats a full State subclass hierarchy in dynamic languages.**

### Observer — still load-bearing, still where people get bitten

```python
class EventBus:
    def __init__(self):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)

    def subscribe(self, event: str, handler: Callable) -> None:
        self._subscribers[event].append(handler)

    def publish(self, event: str, payload: dict) -> None:
        for handler in list(self._subscribers[event]):   # copy: safe if a handler unsubscribes
            try:
                handler(payload)
            except Exception:
                logger.exception(f"handler {handler} failed for event {event}")
                # deliberately continue — one bad subscriber must not block the rest
```

The two production bugs this code specifically guards against, both real and common: (1) iterating the live list while a handler mutates it (unsubscribing itself mid-notification) — fixed by iterating a copy; (2) one subscriber's exception aborting notification to every subsequent subscriber — fixed by catching per-handler and logging rather than propagating.

```java
// Java: java.util.Observer/Observable were deprecated in Java 9 specifically because
// they were badly designed (Observable is a class not an interface, not thread-safe).
// Modern Java uses PropertyChangeListener, or more commonly, a message bus / Spring
// ApplicationEventPublisher.
@Component
public class OrderEventPublisher {
    private final ApplicationEventPublisher publisher;
    public void orderPlaced(Order order) {
        publisher.publishEvent(new OrderPlacedEvent(order));
    }
}
```

```go
// Go: channels are frequently used for Observer-like fan-out,
// though a simple slice-of-callbacks is just as common for in-process pub/sub.
type EventBus struct {
    mu          sync.RWMutex
    subscribers map[string][]chan Event
}

func (b *EventBus) Publish(topic string, evt Event) {
    b.mu.RLock()
    defer b.mu.RUnlock()
    for _, ch := range b.subscribers[topic] {
        select {
        case ch <- evt:
        default: // don't block the publisher on a slow/full subscriber
        }
    }
}
```

**Verdict: fully alive, and at scale it becomes Kafka/EventBridge/Pub/Sub rather than an in-process class.** The in-process version is worth knowing precisely because its two classic bugs (live-list mutation, one-handler-poisons-all) are exactly the kind of thing interviewers probe.

### Command — the object-ness is the entire point

```python
from dataclasses import dataclass
from abc import ABC, abstractmethod

class Command(ABC):
    @abstractmethod
    def execute(self) -> None: ...
    @abstractmethod
    def undo(self) -> None: ...

@dataclass
class MoveItemCommand(Command):
    item: "InventoryItem"
    from_bin: str
    to_bin: str

    def execute(self) -> None:
        self.item.move(self.to_bin)

    def undo(self) -> None:
        self.item.move(self.from_bin)

class CommandStack:
    def __init__(self): self._history: list[Command] = []

    def run(self, cmd: Command) -> None:
        cmd.execute()
        self._history.append(cmd)

    def undo_last(self) -> None:
        if self._history:
            self._history.pop().undo()
```

The reason Command doesn't collapse to a plain function like Strategy: a function can't be queued, serialized, logged with a timestamp and actor, retried, or undone without extra machinery bolted on. Making the action itself an object with `execute()`/`undo()` is what makes all of those free. This is precisely the shape of a job queue (`Celery` tasks, `Sidekiq` jobs), a CLI framework's subcommands (`Click`, `Cobra`), and — increasingly — an agent's tool-call log, where each call needs to be replayable and sometimes compensatable.

```go
// Go: Command as an interface, used identically for a job-queue task.
type Command interface {
    Execute() error
    Undo() error
}

type MoveItemCommand struct {
    Item             *InventoryItem
    FromBin, ToBin   string
}

func (c *MoveItemCommand) Execute() error { return c.Item.Move(c.ToBin) }
func (c *MoveItemCommand) Undo() error    { return c.Item.Move(c.FromBin) }
```

**Verdict: fully alive. Reach for it whenever an action needs to be queued, logged, retried, or undone — not for simple synchronous calls with no such requirement.**

### Chain of Responsibility — every middleware pipeline you've ever written

```python
class Handler(ABC):
    def __init__(self): self._next: "Handler | None" = None

    def set_next(self, handler: "Handler") -> "Handler":
        self._next = handler
        return handler

    def handle(self, request: "Request") -> "Response | None":
        if self._next:
            return self._next.handle(request)
        return None

class AuthHandler(Handler):
    def handle(self, request):
        if not request.token:
            return Response(401, "unauthorized")
        return super().handle(request)

class RateLimitHandler(Handler):
    def handle(self, request):
        if is_rate_limited(request.client_ip):
            return Response(429, "too many requests")
        return super().handle(request)

auth, rate_limit = AuthHandler(), RateLimitHandler()
auth.set_next(rate_limit)
response = auth.handle(incoming_request)
```

This is exactly what WSGI/ASGI middleware, Express/Koa middleware, and gRPC interceptors already are — a chain where each link can short-circuit or pass along. It's rarely built by hand in a mature web framework (the framework provides the chaining mechanism), but validation pipelines, permission-check chains, and approval workflows (each approver can approve, reject, or escalate) still get built this way explicitly.

**Verdict: fully alive, mostly as framework middleware rather than a hand-rolled class chain, but the hand-rolled version is still the right tool for business-level approval/validation chains.**

### Template Method — barely a "pattern," it's just overriding

```python
class DataImporter(ABC):
    def run(self) -> ImportResult:                 # the template — fixed skeleton
        raw = self.fetch()
        parsed = self.parse(raw)
        validated = self.validate(parsed)
        return self.persist(validated)

    @abstractmethod
    def fetch(self) -> bytes: ...
    @abstractmethod
    def parse(self, raw: bytes) -> list[dict]: ...

    def validate(self, records: list[dict]) -> list[dict]:   # default, overridable hook
        return [r for r in records if r.get("id")]

    @abstractmethod
    def persist(self, records: list[dict]) -> ImportResult: ...

class CsvImporter(DataImporter):
    def fetch(self) -> bytes: return self._client.download()
    def parse(self, raw: bytes) -> list[dict]: return list(csv.DictReader(io.StringIO(raw.decode())))
    def persist(self, records): return self._db.bulk_insert(records)
```

**Verdict: this is just inheritance with hook methods — it's "a pattern" only in the sense that naming it helps communicate intent (a fixed skeleton, overridable steps). Every framework's base class with `on_start()`/`on_finish()` hooks (Django `CBV`, JUnit's `setUp()`/`tearDown()`, pytest fixtures) is this pattern, unnamed.**

### Visitor — what `match` replaces, and what it doesn't

Classic form: double dispatch to add an operation over a fixed set of AST node types without modifying them.

```python
# GoF-style Visitor, needed pre-3.10 or in languages without pattern matching:
class Visitor(ABC):
    @abstractmethod
    def visit_number(self, node: "Number"): ...
    @abstractmethod
    def visit_add(self, node: "Add"): ...

class Number:
    def __init__(self, value): self.value = value
    def accept(self, visitor: Visitor): return visitor.visit_number(self)

class Add:
    def __init__(self, left, right): self.left, self.right = left, right
    def accept(self, visitor: Visitor): return visitor.visit_add(self)

class Evaluator(Visitor):
    def visit_number(self, node): return node.value
    def visit_add(self, node): return node.left.accept(self) + node.right.accept(self)

# Python 3.10+: match replaces the double-dispatch machinery entirely
def evaluate(node) -> float:
    match node:
        case Number(value=v):        return v
        case Add(left=l, right=r):   return evaluate(l) + evaluate(r)
        case _:                       raise TypeError(f"unknown node {node!r}")
```

```go
// Go: type switches have always been Go's Visitor-equivalent — Go never had the
// problem Visitor was solving, since it has no class hierarchy to double-dispatch over.
func Evaluate(node Expr) float64 {
    switch n := node.(type) {
    case Number: return n.Value
    case Add:    return Evaluate(n.Left) + Evaluate(n.Right)
    default:     panic("unknown node type")
    }
}
```

```java
// Java 21+: sealed interfaces + pattern matching for switch finally give Java
// the same capability, with exhaustiveness checking at compile time.
sealed interface Expr permits Number, Add {}
record Number(double value) implements Expr {}
record Add(Expr left, Expr right) implements Expr {}

double evaluate(Expr e) {
    return switch (e) {
        case Number n -> n.value();
        case Add a    -> evaluate(a.left()) + evaluate(a.right());
    };   // compiler ERRORS if a permitted subtype is left unhandled — Visitor never gave you this
}
```

The nuance that keeps Visitor from being *fully* dead: `match`/switch-based dispatch requires the dispatching function to know about every node type, which is fine when the type set is fixed and you're adding operations (a compiler adding a new optimization pass) — but if you need to add a *new node type* without touching every existing `match` block scattered across the codebase, GoF Visitor's `accept()`-based double dispatch is actually the more Open/Closed-compliant design, because each new visitor implementation is a self-contained class, not a new `case` bolted onto N existing functions. This is a genuine, rarely-articulated tradeoff: **Visitor optimizes for "types fixed, operations grow"; pattern matching optimizes for "operations fixed (or few), types grow less often than you add new ways to process them."** Most real compilers, having a fairly fixed AST and a constantly growing set of passes, are why Visitor originated there and is one of the only places it's still hand-written today.

**Verdict: mechanically absorbed into `match`/switch/pattern matching wherever the language has it. Still the right choice specifically for stable type hierarchies (compilers, stable AST-like structures) with a frequently growing set of operations, because it keeps each new operation self-contained instead of touching N existing dispatch sites.**

### Iterator — a language keyword, not a class to write

```python
# You almost never implement __iter__/__next__ by hand; a generator does it.
def paginated_records(client, page_size=100):
    offset = 0
    while True:
        page = client.fetch(offset, page_size)
        if not page:
            return
        yield from page
        offset += page_size

for record in paginated_records(client):   # Iterator protocol, invisible
    process(record)
```

```go
// Go 1.23+ range-over-func iterators are Go's native Iterator pattern.
func Paginated(client *Client, pageSize int) iter.Seq[Record] {
    return func(yield func(Record) bool) {
        offset := 0
        for {
            page := client.Fetch(offset, pageSize)
            if len(page) == 0 { return }
            for _, r := range page {
                if !yield(r) { return }
            }
            offset += pageSize
        }
    }
}

for record := range Paginated(client, 100) { process(record) }
```

**Verdict: fully absorbed. You implement the Iterator pattern by hand only when building a custom container type from scratch (`__iter__`/`__next__`, Java's `Iterable<T>`); for everyday sequential traversal, generators and native range-over-func are the pattern, invisibly.**

### Mediator, Memento, Interpreter — the genuine rarities

**Mediator** centralizes communication between a set of objects so they don't reference each other directly (an air-traffic-control tower coordinating planes that never talk to each other). Real modern instances: a chat room server relaying messages between clients, a UI form controller coordinating validation across many fields, an orchestrator service in a saga. It's genuinely useful when you have N objects that would otherwise need N² direct references to coordinate; below a handful of participants, it's usually overkill.

**Memento** captures and restores an object's internal state without violating encapsulation (undo/redo, snapshotting). Real modern instances: a text editor's undo stack, a workflow engine's checkpoint (which is Memento plus Command together), and — very directly — durable agent execution: LangGraph's checkpointer serializing full graph state so a run can resume after a crash *is* Memento at the framework level.

```python
@dataclass(frozen=True)
class EditorMemento:
    content: str
    cursor: int

class TextEditor:
    def __init__(self): self.content, self.cursor = "", 0
    def save(self) -> EditorMemento: return EditorMemento(self.content, self.cursor)
    def restore(self, m: EditorMemento) -> None: self.content, self.cursor = m.content, m.cursor
```

**Interpreter** represents a grammar as a class hierarchy and walks it to evaluate expressions — genuinely rare in application code today because if you need a real grammar, you reach for a parser generator (ANTLR, Lark, `pyparsing`) or an existing embedded language rather than hand-rolling a class per grammar rule. The pattern survives conceptually in rule engines (business rule DSLs), regex engines, and — again — SQL query builders that construct an AST of clauses and walk it to render SQL, which is Interpreter's structure without anyone calling it that.

---

## Build it from scratch

A minimal Command + Memento combination, since together they're the backbone of any real undo system and of durable execution checkpointing:

```python
from dataclasses import dataclass, field
from typing import Callable

@dataclass
class Snapshot:
    state: dict

class Document:
    def __init__(self):
        self._state: dict = {"text": "", "version": 0}

    def snapshot(self) -> Snapshot:
        return Snapshot(state=dict(self._state))   # shallow copy is enough here

    def restore(self, snap: Snapshot) -> None:
        self._state = dict(snap.state)

    def apply(self, text: str) -> None:
        self._state["text"] += text
        self._state["version"] += 1


class UndoableEditor:
    """Command objects carry their own pre-execute snapshot for undo -- Command + Memento."""
    def __init__(self, doc: Document):
        self._doc = doc
        self._undo_stack: list[Snapshot] = []

    def type_text(self, text: str) -> None:
        self._undo_stack.append(self._doc.snapshot())   # Memento captured before mutation
        self._doc.apply(text)                            # Command executed

    def undo(self) -> None:
        if self._undo_stack:
            self._doc.restore(self._undo_stack.pop())
```

This is the exact shape (command execution + pre-state snapshot on a stack) that every text editor's undo, every database transaction's rollback log, and every durable agent framework's checkpoint-before-step pattern reduces to.

---

## How it's done in production

| Pattern | Where it shows up in real frameworks |
|---|---|
| Strategy | Any `key=` callable parameter (`sorted(data, key=...)`), scikit-learn's swappable estimators, comparator functions |
| State | Workflow engines (Temporal, AWS Step Functions), TCP's own connection state machine, order-management systems |
| Observer | Kafka/EventBridge/Pub-Sub at scale; React's re-render-on-state-change; RxJS/Reactor reactive streams |
| Command | Celery/Sidekiq job queues, Click/Cobra CLI subcommands, Redux actions, undo stacks, agent tool-call logs |
| Chain of Responsibility | WSGI/ASGI/Express middleware, gRPC interceptors, approval-workflow chains |
| Template Method | Django class-based views, JUnit/pytest setup/teardown hooks, `torch.nn.Module.forward` overriding |
| Visitor | Compiler passes (type-checkers, optimizers) over a fixed AST, `ast.NodeVisitor` in Python's own stdlib |
| Iterator | Python generators, Go range-over-func (1.23+), Java `Iterable`/streams |
| Mediator | Chat server relaying clients, saga orchestrators, UI form controllers |
| Memento | Undo stacks, LangGraph/Temporal checkpointers, database savepoints |
| Interpreter | SQL query builders (SQLAlchemy `select()` building an AST), rule engines, regex engines |

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| One event subscriber's exception silently stops all later subscribers from being notified | Observer implementation propagates exceptions instead of isolating per-handler | Catch and log per-handler; never let one bad subscriber block the rest |
| `RuntimeError: dictionary changed size during iteration` in an event bus | Iterating the live subscriber list while a handler subscribes/unsubscribes | Iterate a shallow copy of the subscriber list per publish call |
| Order can transition PENDING → DELIVERED directly, skipping payment | No explicit valid-transition graph; state changes are ad hoc `if` statements scattered around the codebase | Centralize the transition table (State pattern) and reject invalid transitions loudly |
| Undo button restores the wrong state after a batch of ops | Memento captured after the mutation instead of before, or captured by reference instead of by value | Snapshot immutable, deep-copied state *before* the mutating command executes |
| Adding a new AST node type requires touching 12 existing `match` blocks | Chose pattern matching for a domain where types grow more often than operations (should have used Visitor/`accept()`) | Refactor to Visitor so each new node type's handling for every existing operation lives in one new visitor method set, not 12 edits |
| A 6-line Strategy became a 40-line `AbstractStrategy`/`ConcreteStrategyA`/`ConcreteStrategyB` hierarchy | Cargo-culted the GoF class shape into a language with first-class functions | Collapse to a plain function parameter or lambda |
| Middleware chain silently drops a request with no response | A handler in Chain of Responsibility returns `None` without calling the next handler and without explicitly rejecting | Make "did not handle" and "explicitly rejected" distinguishable; always either delegate or return a real response |

---

## Tradeoffs & when NOT to use it

- **Do not build a Strategy class hierarchy in Python or Go.** A function parameter does everything `AbstractStrategy`/`ConcreteStrategy` did, with less code and no virtual dispatch overhead. Reach for a class only when the "strategy" needs to carry meaningful state or configuration of its own.
- **Do not build a Visitor hierarchy where pattern matching is available and your type set is stable but small.** The double-dispatch ceremony (`accept()`/`visitX()` pairs) buys you nothing over a `match` statement unless you specifically need new *operations* added without touching the node classes, repeatedly, over the life of the project (this is real for compilers; rare for typical CRUD domains).
- **Do not hand-roll Iterator (`__iter__`/`__next__`) for a linear traversal.** A generator function does the same job in a third of the code and without manual state-tracking bugs.
- **State earns its complexity only when illegal transitions are a real risk.** If an object only ever has two states and one transition, a boolean flag is honest; building the full transition-table machinery for that is overkill.
- **Chain of Responsibility can silently swallow a request if no handler in the chain matches and none explicitly rejects it.** Always distinguish "no handler applies, this is fine" from "no handler applied, and that's a bug" — an unhandled fall-through should be loud, not silent.
- **Mediator centralizes coupling rather than eliminating it — the mediator itself can become a God Object** if it accumulates all cross-object logic. Use it when N objects would otherwise need N² references, not reflexively.
- **Memento's naive form (deep-copying the entire object state on every command) doesn't scale to large documents/graphs.** Real editors use incremental diffs or command-based undo (reverse the last command rather than restoring a full snapshot) once state gets large — know both approaches and when each applies.
- **Observer's biggest real-world risk is the silent memory leak**: a subscriber that's added but never removed keeps its referenced object alive for the lifetime of the publisher, which is a classic long-running-process leak (particularly nasty in long-lived servers and desktop apps).

---

## Interview questions

### Q1 — Implement Strategy for a payment-processing system. Would you use a class hierarchy in Python?
**Testing:** the most common "translate this GoF pattern to Python idiomatically" question.
**Answer:** No — a dict mapping payment method to a processing function, or a `Callable` parameter passed into the checkout function, replaces the `AbstractPaymentStrategy`/`CreditCardStrategy`/`PayPalStrategy` hierarchy entirely. Build a class only if a given strategy needs to carry non-trivial configuration state (API credentials, retry policy) alongside its behavior — and even then, a small dataclass with a `__call__` method is enough, not an ABC hierarchy.
**Follow-up trap:** *"What about Java, which has no first-class function types before Java 8?"* — Java 8+ has functional interfaces and lambdas, so the same collapse applies there too; pre-Java-8 code is the one place the full class hierarchy is genuinely idiomatic, and it's worth knowing that history rather than assuming Java always needs the ceremony.

### Q2 — Explain how Visitor achieves "adding a new operation" without modifying existing classes, and when pattern matching is NOT a full replacement.
**Testing:** the subtlest and most-tested tradeoff in this category.
**Answer:** `element.accept(visitor)` calls back into `visitor.visitConcreteType(element)`, so a new operation (a new Visitor implementation) is a single new class touching zero existing element classes. Pattern matching (`match`/switch) replaces this *mechanically* when the type set is fixed, but it inverts the extension axis: adding a new node *type* with pattern matching requires editing every existing `match` block across the codebase, whereas Visitor requires editing every existing *visitor* to handle the new type — but a NEW visitor for an existing type set costs zero edits either way. Visitor specifically wins when types are stable and operations grow (compilers); pattern matching wins when operations are stable/few and types grow less often.
**Follow-up trap:** *"So which is 'better'?"* — neither, it's Open/Closed applied along two different axes, and the correct answer names which axis your domain actually grows along, rather than picking a side.

### Q3 — Your event bus has one subscriber that throws an exception. What happens, and how do you prevent it from breaking the rest?
**Testing:** the classic Observer production bug.
**Answer:** In a naive implementation, an uncaught exception in one handler propagates up through the publish loop and aborts notification to every subscriber registered after it — silently, since the caller of `publish()` often doesn't even know how many subscribers exist. Fix: wrap each handler invocation in its own try/except, log the failure, and continue to the next handler; the publisher's job is fan-out, not all-or-nothing execution.
**Follow-up trap:** *"What if a handler unsubscribes itself during notification?"* — mutating the subscriber list while iterating it live raises a runtime error (Python) or produces undefined iteration behavior; iterate over a shallow copy of the subscriber list taken at the start of the publish call.

### Q4 — Design a state machine for an order lifecycle (pending → paid → shipped → delivered, plus cancellation). What does the State pattern buy you over a bunch of `if` statements?
**Testing:** whether you understand the pattern's value is the transition graph, not the class ceremony.
**Answer:** The value is making the set of valid transitions an explicit, checkable artifact — a dict/map from current state to allowed next states — so an attempt to jump PENDING → DELIVERED directly is a loud, caught error rather than a silent bug produced by a missing `if` branch somewhere. Whether you implement each state as a subclass with polymorphic `handle()` (GoF's literal form) or as an enum plus a transition table (more idiomatic in Python/Go) is a secondary decision; the transition table is the part that actually prevents production bugs.
**Follow-up trap:** *"Would you ever need the full subclass-per-state version?"* — when each state has meaningfully different *behavior*, not just different *allowed transitions* — e.g., a TCP connection's `ESTABLISHED` state processes incoming data differently than `CLOSING` does. If states only differ in what they can transition to, the table alone is enough.

### Q5 — What's the difference between Command and Strategy? They both wrap behavior in an object.
**Testing:** a commonly confused pair.
**Answer:** Strategy wraps an *algorithm choice* that's invoked immediately and doesn't need identity or history — a plain function suffices. Command wraps an *action* as a first-class object specifically because you need to do something *with* that object beyond immediate invocation: queue it, log it, serialize it, undo it, retry it. If you never need any of those, Command collapses to a function call same as Strategy; the object-ness is only worth its cost when at least one of those needs is real.
**Follow-up trap:** *"Is a Redux action a Command or something else?"* — it's Command: a plain serializable object describing an action, dispatched to a reducer, which is exactly why Redux actions can be logged, replayed, and time-travel-debugged — none of which would be possible if the action were just a function call.

### Q6 — Why were `java.util.Observer`/`Observable` deprecated, and what replaced them?
**Testing:** specific, checkable knowledge of a well-known deprecation.
**Answer:** Deprecated in Java 9 because `Observable` is a concrete class (forcing single inheritance, so you couldn't also extend anything else), not thread-safe, and its API (using `Object` for the argument) predates generics — a design that looked reasonable in 1996 and aged badly. Modern Java uses `PropertyChangeListener`/`PropertyChangeSupport` for simple cases, or an application event bus (Spring's `ApplicationEventPublisher`, Guava's `EventBus`) for anything more serious.
**Follow-up trap:** *"Does this history matter for a Python/Go engineer?"* — yes as a cautionary tale: baking pub/sub into a base class you must extend (rather than composing it in) is a design mistake independent of language, and it's the same reason Python's own Observer implementations favor a standalone `EventBus` object over a mixin base class.

### Q7 — When would you reach for Mediator, and what's the risk of overusing it?
**Testing:** recognizing a rare pattern's real trigger and its failure mode.
**Answer:** When N objects would otherwise need direct references to each other to coordinate (N² relationships) — a chat server relaying messages between clients who never see each other directly, or a saga orchestrator coordinating services. The risk: the mediator itself absorbs all the coordination logic and can become an unmaintainable God Object if it isn't kept to pure coordination (routing messages, sequencing calls) rather than embedding business rules.
**Follow-up trap:** *"How is this different from choreography in a saga?"* — Mediator is exactly the orchestration side of the orchestration-vs-choreography distinction; choreography (each service reacting to events with no central coordinator) is closer to pure Observer/pub-sub with no Mediator at all. Being able to map "orchestration = Mediator, choreography = Observer" onto the saga vocabulary is a strong cross-topic signal.

### Q8 — What is Memento actually protecting, and where does its naive implementation break down at scale?
**Testing:** depth beyond "it's undo."
**Answer:** It protects encapsulation during snapshot/restore — the originator (the object being snapshotted) controls what state gets captured and how it's restored, without the caretaker (whatever's holding the undo stack) needing to know or touch the object's internals. The naive form — deep-copying full state on every command — doesn't scale to large documents or graphs (a 10MB document snapshotted per keystroke is a real memory and latency problem); production undo systems typically store the *inverse command* (Command-based undo) or an incremental diff rather than a full state copy, falling back to full snapshots only at coarser checkpoints.
**Follow-up trap:** *"How does this relate to LangGraph/Temporal checkpointing?"* — those systems are Memento at the framework level (serializing enough state to resume a run after a crash), and they face the identical scaling tension: checkpointing full state after every step is simple but expensive; checkpointing deltas or only at meaningful boundaries is more efficient but more complex to implement correctly.

### Q9 — A colleague proposes hand-writing a custom Iterator class with `__iter__`/`__next__` for paginated API traversal. What would you suggest instead, and when would the class-based version still be correct?
**Testing:** recognizing where the pattern is genuinely absorbed versus where it isn't.
**Answer:** A generator function (`yield`-based, as shown in this module) does the identical job with automatic state management and no manual `StopIteration` handling — strictly less code, same protocol compliance. The class-based `__iter__`/`__next__` version is still correct when you're building a reusable, stateful *container type* (not just a one-off traversal function) that needs to support being iterated multiple times independently, or when the iteration needs additional methods beyond `__next__` (e.g., `reset()`, `peek()``) that a plain generator can't expose.
**Follow-up trap:** *"Can a generator be iterated twice?"* — no, a generator is exhausted after one full traversal; if you need re-iterable behavior, you need either a class implementing `__iter__` that returns a fresh generator each time, or to re-call the generator function itself. This is a genuine, commonly-missed gotcha.

### Q10 — Rank these 11 behavioral patterns by how much of their original GoF ceremony survives in a modern Python/Go codebase, and justify the two extremes.
**Testing:** synthesis across the whole category.
**Answer:** Most ceremony survives: Observer, State, Command, Chain of Responsibility — all still commonly implemented as explicit classes/structures because their value (fan-out, transition safety, do/undo/queue, chained handling) doesn't depend on missing language features. Least ceremony survives: Strategy (a function), Iterator (a generator), Template Method (plain overriding) — all fully absorbed because first-class functions and native iteration protocols directly replace what the class hierarchy used to provide. Visitor sits in between: its mechanics are replaced by pattern matching, but its Open/Closed benefit for stable-types/growing-operations domains (compilers) is real and not fully replaceable.
**Follow-up trap:** *"Where do Mediator, Memento, Interpreter fall?"* — real but rare; they solve genuine, narrower problems (N² coordination, undo/snapshot, embedded grammars) that most CRUD-shaped backend services simply don't encounter often, so their ceremony neither collapsed into a language feature nor stayed common — it just stayed niche.

---

## Red flags that fail you

- Building a class hierarchy for Strategy in Python or modern Java when a function/lambda would do.
- Not knowing that `java.util.Observer`/`Observable` were deprecated, or presenting them as the modern answer.
- Proposing full Visitor double-dispatch in a codebase with `match`/pattern matching available and no operations-growth requirement.
- An Observer implementation with no per-handler exception isolation.
- Confusing Strategy (caller picks per call) with State (object's own behavior changes over its lifecycle).
- Hand-writing `__iter__`/`__next__` for a simple linear traversal instead of a generator.
- Presenting Mediator, Memento, or Interpreter as everyday tools rather than situational ones.

---

## Cheat card

```
11 BEHAVIORAL PATTERNS — MODERN VERDICT
  Strategy            ABSORBED → function/lambda parameter. Class only if state is carried.
  Iterator             ABSORBED → generator / yield / range-over-func. Class only for custom containers.
  Template Method       ABSORBED → plain method overriding / framework hooks (setUp/forward/CBV).
  Visitor               MECHANICS absorbed by match/switch/sealed+pattern-matching.
                        STILL earns its keep: types FIXED, operations GROW (compilers).
                        match wins: operations FIXED/few, types grow (adding a new case per site instead).
  State                 SURVIVES. Value = explicit, checkable transition table, not the subclass hierarchy.
  Observer               SURVIVES. At scale = Kafka/EventBridge/PubSub.
                        2 classic bugs: (1) live-list mutation during iteration
                                        (2) one handler's exception blocks all later handlers
  Command                SURVIVES. Object-ness earns its cost only if you queue/log/serialize/undo it.
                        = job queue task, CLI subcommand, agent tool-call log entry.
  Chain of Responsibility SURVIVES, usually as framework middleware (WSGI/ASGI/gRPC interceptors).
  Mediator               RARE. Use when N objects need N^2 refs to coordinate. Risk: becomes God Object.
                        = orchestration side of saga orchestration-vs-choreography.
  Memento                RARE but real. = undo stacks, DB savepoints, LangGraph/Temporal checkpoints.
                        Naive full-deepcopy-per-command doesn't scale; use inverse-command or diffs.
  Interpreter            RARE. Real grammars → use a parser generator (ANTLR/Lark), not hand-rolled classes.
                        Survives unnamed in query builders (SQLAlchemy select() builds+walks an AST).

java.util.Observer/Observable: DEPRECATED Java 9 (not thread-safe, concrete class, pre-generics).

RULE OF THUMB: if it's a caller-side choice with no state → Strategy → just pass a function.
               if it's the object's own lifecycle → State → keep the explicit transition table.
```

## Sources

- [Design Patterns: Elements of Reusable Object-Oriented Software — Gamma, Helm, Johnson, Vlissides (1994)](https://en.wikipedia.org/wiki/Design_Patterns) — accessed 2026-07-26
- [Design Patterns in Dynamic Programming — Peter Norvig, 1996](https://norvig.com/design-patterns/) — accessed 2026-07-26
- [Design Patterns | Hello Interview Low Level Design](https://www.hellointerview.com/learn/low-level-design/in-a-hurry/patterns) — accessed 2026-07-26
- [Top Design Patterns Interview Questions for 2026 — Guvi](https://www.guvi.in/blog/top-design-patterns-interview-questions/) — accessed 2026-07-26
- [27 Advanced Design Patterns Interview Questions For Senior Developers — FullStack.Cafe](https://www.fullstack.cafe/blog/design-patterns-interview-questions) — accessed 2026-07-26
- [Java Language Updates: Pattern Matching for switch (JEP 441, Java 21) — Oracle](https://docs.oracle.com/en/java/javase/21/language/pattern-matching-switch-statements-and-expressions.html) — accessed 2026-07-26

## Changelog
- 2026-07-28 — created
