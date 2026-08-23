package breaker

import (
	"errors"
	"fmt"
	"math/rand"
	"sync"
	"testing"
	"time"
)

// No sleeps, no wall clock — everything runs on FakeClock.
// Run:            go test ./...              (starter → FAILS. Make them pass.)
// Reference:      go test -tags solution ./...

func mustFail(t *testing.T, cb *CircuitBreaker, n int) {
	t.Helper()
	for i := 0; i < n; i++ {
		if err := cb.Call(func() error { return errors.New("boom") }); err == nil {
			t.Fatalf("call %d should have failed", i+1)
		}
	}
}

// ------------------------------------------------------------------ clock

func TestFakeClockAdvances(t *testing.T) {
	c := NewFakeClock()
	c.Advance(100 * time.Second)
	if got := c.Now().Sub(time.Unix(0, 0)); got != 100*time.Second {
		t.Fatalf("now = %v, want 100s", got)
	}
	c.Advance(5 * time.Second)
	if got := c.Now().Sub(time.Unix(0, 0)); got != 105*time.Second {
		t.Fatalf("now = %v, want 105s", got)
	}
}

func TestFakeClockSleepRecordsNotBlocks(t *testing.T) {
	c := NewFakeClock()
	c.Sleep(3 * time.Second)
	if c.Now().Sub(time.Unix(0, 0)) != 3*time.Second {
		t.Fatal("Sleep must fast-forward the fake clock")
	}
	if len(c.Sleeps) != 1 || c.Sleeps[0] != 3*time.Second {
		t.Fatalf("Sleeps = %v, want [3s]", c.Sleeps)
	}
}

// ------------------------------------------------------------------ deadline

func TestDeadlineRemainingAndExpiry(t *testing.T) {
	c := NewFakeClock()
	d := After(10*time.Second, c)
	if d.Remaining() != 10*time.Second {
		t.Fatalf("remaining = %v", d.Remaining())
	}
	c.Advance(4 * time.Second)
	if d.Remaining() != 6*time.Second || d.Expired() {
		t.Fatal("deadline should have 6s left")
	}
	c.Advance(6 * time.Second)
	if !d.Expired() || d.Remaining() != 0 {
		t.Fatal("deadline should be expired with remaining clamped to 0")
	}
}

func TestDeadlineBudgetShrinksWithDepth(t *testing.T) {
	c := NewFakeClock()
	d := After(3*time.Second, c)
	if b, err := d.BudgetFor(5 * time.Second); err != nil || b != 3*time.Second {
		t.Fatalf("budget = %v, err = %v; want capped at 3s", b, err)
	}
	c.Advance(2500 * time.Millisecond)
	if b, _ := d.BudgetFor(5 * time.Second); b != 500*time.Millisecond {
		t.Fatalf("budget = %v, want 500ms", b)
	}
	c.Advance(time.Second)
	if _, err := d.BudgetFor(5 * time.Second); !errors.Is(err, ErrTimeout) {
		t.Fatalf("expired deadline must return ErrTimeout, got %v", err)
	}
}

// ------------------------------------------------------------------ backoff

func TestFullJitterBoundedAndGrows(t *testing.T) {
	rng := rand.New(rand.NewSource(0))
	for attempt := 0; attempt < 6; attempt++ {
		bound := min(10*time.Second, 100*time.Millisecond<<attempt)
		for i := 0; i < 50; i++ {
			s := FullJitter(attempt, 100*time.Millisecond, 10*time.Second, rng)
			if s < 0 || s >= bound {
				t.Fatalf("attempt %d: jitter %v outside [0,%v)", attempt, s, bound)
			}
		}
	}
}

func TestFullJitterRespectsCap(t *testing.T) {
	rng := rand.New(rand.NewSource(1))
	for i := 0; i < 100; i++ {
		if s := FullJitter(20, 100*time.Millisecond, 2*time.Second, rng); s > 2*time.Second {
			t.Fatalf("jitter %v exceeds cap", s)
		}
	}
}

func TestDecorrelatedJitterBounded(t *testing.T) {
	rng := rand.New(rand.NewSource(3))
	prev := 100 * time.Millisecond
	for i := 0; i < 50; i++ {
		prev = DecorrelatedJitter(prev, 100*time.Millisecond, 5*time.Second, rng)
		if prev < 100*time.Millisecond || prev > 5*time.Second {
			t.Fatalf("decorrelated jitter %v outside bounds", prev)
		}
	}
}

// ------------------------------------------------------------------ retry

func TestRetrySucceedsAfterTransientFailures(t *testing.T) {
	c := NewFakeClock()
	r := NewRetry(3, c, rand.New(rand.NewSource(0)))
	n := 0
	err := r.Call(func() error {
		n++
		if n < 3 {
			return errors.New("transient")
		}
		return nil
	})
	if err != nil || n != 3 {
		t.Fatalf("err=%v calls=%d, want success on call 3", err, n)
	}
	if len(c.Sleeps) != 2 {
		t.Fatalf("sleeps = %d, want 2 (between attempts, not after the last)", len(c.Sleeps))
	}
}

func TestRetryReraisesWhenExhausted(t *testing.T) {
	c := NewFakeClock()
	r := NewRetry(3, c, rand.New(rand.NewSource(0)))
	err := r.Call(func() error { return errors.New("down") })
	if err == nil || err.Error() != "down" {
		t.Fatalf("want last error surfaced, got %v", err)
	}
	if r.Stats.Calls != 3 || r.Stats.Exhausted != 1 {
		t.Fatalf("stats = %+v, want 3 calls / 1 exhausted", r.Stats)
	}
}

func TestRetryDoesNotRetryNonRetryable(t *testing.T) {
	c := NewFakeClock()
	r := NewRetry(3, c, rand.New(rand.NewSource(0)))
	r.RetryOn = func(err error) bool { return errors.Is(err, ErrTimeout) }
	n := 0
	_ = r.Call(func() error { n++; return fmt.Errorf("400 bad request") })
	if n != 1 {
		t.Fatalf("non-retryable retried %d times", n-1)
	}
	if len(c.Sleeps) != 0 {
		t.Fatal("no sleeping for a non-retryable error")
	}
}

// ------------------------------------------------------------------ breaker

func TestBreakerStartsClosed(t *testing.T) {
	cb := NewCircuitBreaker(DefaultConfig(), NewFakeClock())
	if cb.State() != StateClosed {
		t.Fatalf("state = %v, want closed", cb.State())
	}
}

func TestBreakerDoesNotTripBelowMinCalls(t *testing.T) {
	// 5 failures out of 5 is a 100% failure rate — but under min_calls the
	// evidence is too thin and the breaker must stay closed.
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, SlidingWindow: 100,
		MinCalls: 20}, NewFakeClock())
	mustFail(t, cb, 5)
	if cb.State() != StateClosed {
		t.Fatalf("tripped below min_calls: state = %v", cb.State())
	}
}

func TestBreakerTripsAtThreshold(t *testing.T) {
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 10,
		SlidingWindow: 100}, NewFakeClock())
	for i := 0; i < 5; i++ {
		if err := cb.Call(func() error { return nil }); err != nil {
			t.Fatal(err)
		}
	}
	mustFail(t, cb, 5)
	if cb.State() != StateOpen {
		t.Fatalf("50%% failures over 10 calls must open, state = %v", cb.State())
	}
}

func TestOpenBreakerFailsFastWithoutCalling(t *testing.T) {
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10}, c)
	mustFail(t, cb, 2)
	called := 0
	err := cb.Call(func() error { called++; return nil })
	if !errors.Is(err, ErrBreakerOpen) {
		t.Fatalf("want ErrBreakerOpen, got %v", err)
	}
	if called != 0 {
		t.Fatal("open breaker invoked the protected call")
	}
	if cb.Stats.Rejections != 1 {
		t.Fatalf("rejections = %d, want 1", cb.Stats.Rejections)
	}
}

func TestBreakerHalfOpensAfterWait(t *testing.T) {
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10, OpenDuration: 30 * time.Second, HalfOpenProbes: 2}, c)
	mustFail(t, cb, 2)
	c.Advance(29 * time.Second)
	if err := cb.Call(func() error { return nil }); !errors.Is(err, ErrBreakerOpen) {
		t.Fatal("breaker must stay open before OpenDuration elapses")
	}
	c.Advance(2 * time.Second)
	if err := cb.Call(func() error { return nil }); err != nil {
		t.Fatalf("probe should be admitted after open_duration: %v", err)
	}
	if cb.State() != StateHalfOpen {
		t.Fatalf("state = %v, want half_open after first probe", cb.State())
	}
}

func TestHalfOpenClosesAfterEnoughProbes(t *testing.T) {
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10, OpenDuration: time.Second, HalfOpenProbes: 2}, c)
	mustFail(t, cb, 2)
	c.Advance(2 * time.Second)
	_ = cb.Call(func() error { return nil })
	_ = cb.Call(func() error { return nil })
	if cb.State() != StateClosed {
		t.Fatalf("%d clean probes must close the breaker, state = %v",
			cb.cfg.HalfOpenProbes, cb.State())
	}
}

func TestHalfOpenReopensOnAnyProbeFailure(t *testing.T) {
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10, OpenDuration: time.Second, HalfOpenProbes: 3}, c)
	mustFail(t, cb, 2)
	c.Advance(2 * time.Second)
	_ = cb.Call(func() error { return nil }) // one good probe
	_ = cb.Call(func() error { return errors.New("boom") })
	if cb.State() != StateOpen {
		t.Fatalf("a failed probe must reopen, state = %v", cb.State())
	}
}

func TestBreakerIgnoresBusinessExceptions(t *testing.T) {
	notFound := errors.New("404 not found")
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10, Ignore: func(err error) bool {
			return errors.Is(err, notFound)
		}}, NewFakeClock())
	for i := 0; i < 10; i++ {
		_ = cb.Call(func() error { return notFound })
	}
	if cb.State() != StateClosed {
		t.Fatal("404s are business outcomes — they must not trip the breaker")
	}
}

func TestBreakerTripsOnSlowCallsThatSucceed(t *testing.T) {
	// The dependency returns 200s in 5s. Failure rate is 0%. It still kills you.
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.99, MinCalls: 4,
		SlidingWindow: 10, SlowCallRateThreshold: 0.5,
		SlowCallDuration: 2 * time.Second}, c)
	for i := 0; i < 4; i++ {
		_ = cb.Call(func() error {
			c.Advance(5 * time.Second)
			return nil
		})
	}
	if cb.State() != StateOpen {
		t.Fatal("slow-call rate must trip the breaker even with zero failures")
	}
}

func TestBreakerRecordsTransitions(t *testing.T) {
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10, OpenDuration: time.Second, HalfOpenProbes: 1}, c)
	mustFail(t, cb, 2)
	c.Advance(2 * time.Second)
	_ = cb.Call(func() error { return nil })

	want := map[string]bool{"closed>open": false, "open>half_open": false}
	for _, tr := range cb.Stats.Transitions {
		key := tr[0] + ">" + tr[1]
		want[key] = true
	}
	for k, seen := range want {
		if !seen {
			t.Fatalf("missing transition %s in %v", k, cb.Stats.Transitions)
		}
	}
}

// ------------------------------------------------------------------ bulkhead

func TestBulkheadAllowsUpToLimitSequentially(t *testing.T) {
	bh := NewBulkhead(3)
	for i := 0; i < 10; i++ {
		if err := bh.Call(func() error { return nil }); err != nil {
			t.Fatalf("sequential calls never saturate: %v", err)
		}
	}
	if bh.Stats.Rejections != 0 {
		t.Fatalf("rejections = %d", bh.Stats.Rejections)
	}
}

func TestBulkheadRejectsWhenSaturated(t *testing.T) {
	bh := NewBulkhead(2)
	entered := make(chan struct{}, 2)
	release := make(chan struct{})

	var wg sync.WaitGroup
	for i := 0; i < 2; i++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			_ = bh.Call(func() error {
				entered <- struct{}{}
				<-release
				return nil
			})
		}()
	}
	<-entered
	<-entered // both slots held

	if err := bh.Call(func() error { return nil }); !errors.Is(err, ErrBulkheadFull) {
		t.Fatalf("saturated bulkhead must reject immediately, got %v", err)
	}
	close(release)
	wg.Wait()

	if bh.Stats.Rejections != 1 {
		t.Fatalf("rejections = %d, want 1", bh.Stats.Rejections)
	}
	if bh.Stats.MaxConcurrent != 2 {
		t.Fatalf("max_concurrent = %d, want 2", bh.Stats.MaxConcurrent)
	}
}

func TestBulkheadReleasesOnPanic(t *testing.T) {
	bh := NewBulkhead(1)
	for i := 0; i < 5; i++ {
		func() {
			defer func() { _ = recover() }() // panic must not leak the slot
			_ = bh.Call(func() error { panic("boom") })
		}()
	}
	if err := bh.Call(func() error { return nil }); err != nil {
		t.Fatalf("slot leaked on the panic path: %v", err)
	}
}

// ------------------------------------------------------------------ compose

func TestResilientComposesAndFallsBack(t *testing.T) {
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 2,
		SlidingWindow: 10, OpenDuration: 30 * time.Second}, c)
	r := NewRetry(2, c, rand.New(rand.NewSource(0)))

	call := Resilient(func() error { return errors.New("connection refused") },
		Opts{Retry: r, Breaker: cb, Bulkhead: NewBulkhead(5), Clock: c,
			Fallback: func(error) error { return nil }}) // "serve STALE_CACHE" = no error

	for i := 0; i < 4; i++ {
		if err := call(); err != nil {
			t.Fatalf("fallback should absorb the failure: %v", err)
		}
	}
	if cb.State() != StateOpen {
		t.Fatalf("underlying dependency is down — breaker must be open, got %v", cb.State())
	}
}

func TestRetryGroupCountsAsOneBreakerOutcome(t *testing.T) {
	// THE test. Retry lives INSIDE the breaker: 3 attempts of one logical
	// call record ONE failure, not three — otherwise the breaker trips 3x fast.
	c := NewFakeClock()
	cb := NewCircuitBreaker(Config{FailureRateThreshold: 0.5, MinCalls: 4,
		SlidingWindow: 10}, c)
	r := NewRetry(3, c, rand.New(rand.NewSource(0)))

	call := Resilient(func() error { return errors.New("down") },
		Opts{Retry: r, Breaker: cb, Clock: c})

	for i := 0; i < 3; i++ {
		if err := call(); err == nil {
			t.Fatal("expected exhaustion error to escape")
		}
	}
	if r.Stats.Calls != 9 { // 3 logical calls x 3 attempts
		t.Fatalf("retry attempts = %d, want 9", r.Stats.Calls)
	}
	if cb.Stats.Calls != 3 { // but only 3 breaker outcomes
		t.Fatalf("breaker outcomes = %d, want 3 (one per logical call)", cb.Stats.Calls)
	}
	if cb.State() != StateClosed {
		t.Fatalf("min_calls=4 not reached yet, state = %v", cb.State())
	}
}

func TestBulkheadRejectionCostsNoDownstreamCall(t *testing.T) {
	bh := NewBulkhead(1)
	hits := 0
	call := Resilient(func() error { hits++; return nil }, Opts{Bulkhead: bh})

	entered := make(chan struct{}, 1)
	release := make(chan struct{})
	done := make(chan struct{})
	go func() {
		_ = bh.Call(func() error {
			entered <- struct{}{}
			<-release
			return nil
		})
		close(done)
	}()
	<-entered // the holder provably owns the only slot

	if err := call(); !errors.Is(err, ErrBulkheadFull) {
		t.Fatalf("want bulkhead rejection, got %v", err)
	}
	close(release)
	<-done
	if hits != 0 {
		t.Fatalf("rejected call must not touch the downstream, hits = %d", hits)
	}
}
