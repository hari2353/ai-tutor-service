# How production does it

## sony/gobreaker — the standard Go breaker

The real `gobreaker.CircuitBreaker[T]` is a generic wrapper around
`func() (T, error)` with the same three states you built. What it adds:

- **ReadyToTrip func(counts Counts)** — trip decisions come from a user
  callback over cumulative counters, not just a failure-rate threshold. Teams
  encode things like "trip after 5 consecutive failures OR 60s of >10% errors".
- **onStateChange hooks** — state transitions emit metrics/events. Your
  `Transitions` slice is the seed of that; production wires it to Prometheus.
- **Mutex discipline identical to yours** — a single `sync.Mutex` guards
  state+counters; the protected fn runs OUTSIDE the lock. Same choice you made.

## failsafe-go — the composition layer

Failsafe-go is your `Resilient()`: policies (`Retry`, `CircuitBreaker`,
`Timeout`, `Bulkhead`, `Hedge`) composed with `.Compose()` / `.NewChain()`.
Two production details worth stealing:

- Policies compose outside-in exactly like yours, and the docs warn about the
  same ordering trap: breaker-around-retry or your breaker trips on every attempt.
- Its `TimeoutPolicy` uses `context` cancellation rather than leaking the
  goroutine — your FakeClock version measures, but only context actually stops work.

## Bulkhead in production

Go has no thread pool to exhaust (goroutines are cheap but not free — memory +
scheduler pressure), so bulkheads become bounded worker pools or semaphores:
`golang.org/x/sync/semaphore`, `errgroup.SetLimit`, or a buffered channel like
yours. The rejection-vs-queue decision is identical: load shedding beats
latency death spirals.

## What the interview probe looks for

- "Where does the lock go relative to the protected call?" (Outside. Holding a
  mutex across a network call serialises your whole service.)
- "Why is retry inside the breaker?" (One logical outcome per call.)
- "What trips on slow success?" (Slow-call rate — the silent killer.)
- "How do half-open probes avoid stampede?" (Bounded concurrent probes.)
