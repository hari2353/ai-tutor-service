//go:build !solution

package breaker

import (
	"math/rand"
	"time"
)

// STARTER — every primitive below compiles but does not work yet.
// The suite fails against this file; that is the point. Make it pass
// without touching the tests or types.go.

// Deadline bounds how long a logical operation may take, and shrinks as it
// propagates down the call tree.
type Deadline struct{}

func After(d time.Duration, c Clock) *Deadline { return &Deadline{} }

func (d *Deadline) Remaining() time.Duration      { return 0 }
func (d *Deadline) Expired() bool                 { return false }
func (d *Deadline) BudgetFor(max time.Duration) (time.Duration, error) {
	return 0, ErrTimeout
}

// FullJitter sleeps-in-seconds picker: uniform in [0, min(cap, base*2^attempt)).
func FullJitter(attempt int, base, cap time.Duration, rng *rand.Rand) time.Duration {
	return 0
}

// DecorrelatedJitter: uniform in [base, min(cap, prev*3)), seeded from prev.
func DecorrelatedJitter(prev, base, cap time.Duration, rng *rand.Rand) time.Duration {
	return 0
}

// Retry retries a flaky call with jittered backoff through the clock.
type Retry struct {
	Config  Config // unused by the starter; kept for signature parity
	Attempts int
	RetryOn func(error) bool
	Clock   Clock
	RNG     *rand.Rand
	Stats   Stats
}

func NewRetry(attempts int, clock Clock, rng *rand.Rand) *Retry {
	return &Retry{Attempts: attempts, Clock: clock, RNG: rng}
}

// Call runs fn up to Attempts times, sleeping (via the clock) between tries.
// Only retryable errors are retried; nil RetryOn means "retry everything".
func (r *Retry) Call(fn func() error) error { return fn() }

// CircuitBreaker is the three-state breaker over a sliding window of calls.
type CircuitBreaker struct {
	cfg   Config
	clock Clock
	Stats Stats
	state State
}

func NewCircuitBreaker(cfg Config, clock Clock) *CircuitBreaker {
	return &CircuitBreaker{cfg: cfg, clock: clock}
}

func (cb *CircuitBreaker) State() State { return cb.state }

// Call runs fn if the breaker admits it. An OPEN breaker rejects with
// ErrBreakerOpen WITHOUT invoking fn.
func (cb *CircuitBreaker) Call(fn func() error) error { return fn() }

// Bulkhead caps concurrent calls, rejecting immediately when full.
type Bulkhead struct {
	limit int
	Stats Stats
}

func NewBulkhead(limit int) *Bulkhead { return &Bulkhead{limit: limit} }

func (b *Bulkhead) Call(fn func() error) error { return fn() }

// Opts wires the composition for Resilient. Nil members are skipped.
type Opts struct {
	Retry    *Retry
	Breaker  *CircuitBreaker
	Bulkhead *Bulkhead
	Clock    Clock
	Fallback func(error) error
}

// Resilient composes bulkhead(breaker(retry(fn))) with an optional fallback.
// THE invariant: one logical call = ONE outcome recorded on the breaker,
// no matter how many retry attempts happened inside.
func Resilient(fn func() error, o Opts) func() error {
	return func() error { return fn() }
}
