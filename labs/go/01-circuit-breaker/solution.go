//go:build solution

package breaker

import (
	"math/rand"
	"sync"
	"time"
)

// SOLUTION — reference implementation. Read it AFTER your own version passes.

// ---------------------------------------------------------------- deadline

type Deadline struct {
	deadline time.Time
	clock    Clock
}

// After returns a Deadline expiring d from the clock's current instant.
func After(d time.Duration, c Clock) *Deadline {
	return &Deadline{deadline: c.Now().Add(d), clock: c}
}

func (d *Deadline) Remaining() time.Duration {
	r := d.deadline.Sub(d.clock.Now())
	if r < 0 {
		return 0
	}
	return r
}

func (d *Deadline) Expired() bool { return d.Remaining() <= 0 }

// BudgetFor propagates the deadline: a nested step gets
// min(its own max, what is actually left). An expired deadline errors.
func (d *Deadline) BudgetFor(max time.Duration) (time.Duration, error) {
	r := d.Remaining()
	if r <= 0 {
		return 0, ErrTimeout
	}
	if max < r {
		return max, nil
	}
	return r, nil
}

// ---------------------------------------------------------------- backoff

func FullJitter(attempt int, base, cap time.Duration, rng *rand.Rand) time.Duration {
	b := base << attempt // exponential growth: base*2^attempt
	if b > cap || b <= 0 {
		b = cap
	}
	return time.Duration(rng.Int63n(int64(b)))
}

func DecorrelatedJitter(prev, base, cap time.Duration, rng *rand.Rand) time.Duration {
	hi := prev * 3
	if hi > cap {
		hi = cap
	}
	if hi < base {
		hi = base
	}
	return base + time.Duration(rng.Int63n(int64(hi-base+1)))
}

// ---------------------------------------------------------------- retry

type Retry struct {
	Config   Config
	Attempts int
	RetryOn  func(error) bool
	Clock    Clock
	RNG      *rand.Rand
	Stats    Stats
}

func NewRetry(attempts int, clock Clock, rng *rand.Rand) *Retry {
	return &Retry{Attempts: attempts, Clock: clock, RNG: rng}
}

func (r *Retry) Call(fn func() error) error {
	var last error
	for attempt := 0; attempt < r.Attempts; attempt++ {
		last = fn()
		r.Stats.Calls++
		if last == nil {
			return nil
		}
		retryable := r.RetryOn == nil || r.RetryOn(last)
		if !retryable {
			return last // e.g. a 400 — retrying is pure waste
		}
		if attempt == r.Attempts-1 {
			break
		}
		fc, ok := r.Clock.(*FakeClock)
		base := 100 * time.Millisecond
		if ok {
			fc.Sleep(FullJitter(attempt, base, 30*time.Second, r.RNG))
		} else {
			time.Sleep(FullJitter(attempt, base, 30*time.Second, r.RNG))
		}
	}
	r.Stats.Exhausted++
	return last
}

// ---------------------------------------------------------------- breaker

type record struct {
	ok   bool
	slow bool
}

type CircuitBreaker struct {
	cfg   Config
	clock Clock

	mu          sync.Mutex
	state       State
	window      []record
	openedAt    time.Time
	probeOKs    int
	probesInFly int
	Stats       Stats
}

func NewCircuitBreaker(cfg Config, clock Clock) *CircuitBreaker {
	if cfg.FailureRateThreshold <= 0 {
		cfg.FailureRateThreshold = 0.5
	}
	if cfg.SlidingWindow <= 0 {
		cfg.SlidingWindow = 100
	}
	if cfg.MinCalls <= 0 {
		cfg.MinCalls = 20
	}
	if cfg.OpenDuration <= 0 {
		cfg.OpenDuration = 30 * time.Second
	}
	if cfg.HalfOpenProbes <= 0 {
		cfg.HalfOpenProbes = 5
	}
	if cfg.SlowCallRateThreshold <= 0 {
		cfg.SlowCallRateThreshold = 1.1 // >1 never trips: slow-call detection off
	}
	return &CircuitBreaker{cfg: cfg, clock: clock, state: StateClosed}
}

func (cb *CircuitBreaker) State() State {
	cb.mu.Lock()
	defer cb.mu.Unlock()
	cb.refreshStateLocked()
	return cb.state
}

// refreshStateLocked moves OPEN → HALF_OPEN once OpenDuration has passed.
// Time-based transitions are checked lazily on every observation point.
func (cb *CircuitBreaker) refreshStateLocked() {
	if cb.state == StateOpen && cb.clock.Now().Sub(cb.openedAt) >= cb.cfg.OpenDuration {
		cb.transitionLocked(StateHalfOpen)
	}
}

func (cb *CircuitBreaker) transitionLocked(to State) {
	if cb.state == to {
		return
	}
	cb.Stats.record(cb.state, to)
	cb.state = to
	switch to {
	case StateClosed:
		cb.window = nil
		cb.probeOKs = 0
	case StateHalfOpen:
		cb.probeOKs = 0
		cb.probesInFly = 0
	}
}

func (cb *CircuitBreaker) Call(fn func() error) error {
	cb.mu.Lock()
	cb.refreshStateLocked()

	switch cb.state {
	case StateOpen:
		cb.Stats.Rejections++
		cb.mu.Unlock()
		return ErrBreakerOpen
	case StateHalfOpen:
		if cb.probesInFly >= cb.cfg.HalfOpenProbes {
			cb.Stats.Rejections++
			cb.mu.Unlock()
			return ErrBreakerOpen
		}
		cb.probesInFly++
		cb.mu.Unlock()
		err := cb.runAndRecord(fn)
		cb.mu.Lock()
		cb.probesInFly--
		cb.mu.Unlock()
		return err
	}
	cb.mu.Unlock()
	return cb.runAndRecord(fn)
}

func (cb *CircuitBreaker) runAndRecord(fn func() error) error {
	start := cb.clock.Now()
	err := fn()
	dur := cb.clock.Now().Sub(start)

	cb.mu.Lock()
	defer cb.mu.Unlock()

	ignored := err != nil && cb.cfg.Ignore != nil && cb.cfg.Ignore(err)
	slow := cb.cfg.SlowCallDuration > 0 && dur >= cb.cfg.SlowCallDuration &&
		cb.cfg.SlowCallRateThreshold <= 1.0
	failed := err != nil && !ignored

	cb.window = append(cb.window, record{ok: !failed, slow: slow})
	if len(cb.window) > cb.cfg.SlidingWindow {
		cb.window = cb.window[len(cb.window)-cb.cfg.SlidingWindow:]
	}
	cb.Stats.Calls++
	if failed {
		cb.Stats.Failures++
	}
	if cb.state == StateHalfOpen {
		// Any probe failure reopens; enough clean probes close.
		if failed {
			cb.openedAt = cb.clock.Now()
			cb.transitionLocked(StateOpen)
			return err
		}
		if ignored {
			return err // neither counts against nor for the probe
		}
		cb.probeOKs++
		if cb.probeOKs >= cb.cfg.HalfOpenProbes {
			cb.transitionLocked(StateClosed)
		}
		return err
	}

	n := len(cb.window)
	if n < cb.cfg.MinCalls {
		return err // not enough evidence yet — stay closed
	}
	failRate := float64(countFail(cb.window)) / float64(n)
	if failRate >= cb.cfg.FailureRateThreshold {
		cb.openedAt = cb.clock.Now()
		cb.transitionLocked(StateOpen)
		return err
	}
	slowRate := float64(countSlow(cb.window)) / float64(n)
	if slowRate >= cb.cfg.SlowCallRateThreshold {
		cb.openedAt = cb.clock.Now()
		cb.transitionLocked(StateOpen)
	}
	return err
}

func countFail(rs []record) int {
	n := 0
	for _, r := range rs {
		if !r.ok {
			n++
		}
	}
	return n
}

func countSlow(rs []record) int {
	n := 0
	for _, r := range rs {
		if r.slow {
			n++
		}
	}
	return n
}

// ---------------------------------------------------------------- bulkhead

type Bulkhead struct {
	limit int
	sem   chan struct{}
	mu    sync.Mutex
	inFly int
	Stats Stats
}

func NewBulkhead(limit int) *Bulkhead {
	return &Bulkhead{limit: limit, sem: make(chan struct{}, limit)}
}

// Call rejects IMMEDIATELY with ErrBulkheadFull when saturated — it never
// queues. The slot is released even when fn panics or errors.
func (b *Bulkhead) Call(fn func() error) (err error) {
	select {
	case b.sem <- struct{}{}:
	default:
		b.mu.Lock()
		b.Stats.Rejections++
		b.mu.Unlock()
		return ErrBulkheadFull
	}
	defer func() {
		<-b.sem
		if p := recover(); p != nil {
			panic(p) // release first, then re-panic
		}
	}()
	b.mu.Lock()
	b.inFly++
	if b.inFly > b.Stats.MaxConcurrent {
		b.Stats.MaxConcurrent = b.inFly
	}
	b.mu.Unlock()
	defer func() {
		b.mu.Lock()
		b.inFly--
		b.mu.Unlock()
	}()
	return fn()
}

// ---------------------------------------------------------------- compose

type Opts struct {
	Retry    *Retry
	Breaker  *CircuitBreaker
	Bulkhead *Bulkhead
	Clock    Clock
	Fallback func(error) error
}

// Resilient composes bulkhead → breaker → retry → fallback, OUTSIDE-IN.
//
// The nesting order is the whole point:
//   - bulkhead outermost: a full bulkhead rejects without spending a single
//     downstream call (and without tripping the breaker).
//   - breaker around retry: one logical call records ONE breaker outcome no
//     matter how many attempts happened inside — otherwise the breaker trips
//     N-times faster than reality.
//   - fallback catches whatever escapes (exhausted retries, open breaker).
func Resilient(fn func() error, o Opts) func() error {
	return func() error {
		core := fn
		if o.Retry != nil {
			r := o.Retry
			core = func() error { return r.Call(fn) }
		}
		if o.Breaker != nil {
			cb := o.Breaker
			inner := core
			core = func() error { return cb.Call(inner) }
		}
		if o.Bulkhead != nil {
			bh := o.Bulkhead
			inner := core
			core = func() error { return bh.Call(inner) }
		}
		err := core()
		if err == nil || o.Fallback == nil {
			return err
		}
		return o.Fallback(err)
	}
}
