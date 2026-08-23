// Package breaker: resilience primitives from scratch.
//
// Shared infrastructure compiled for BOTH starter and solution builds:
// clocks, states, errors, stats. The primitives themselves live in
// breaker.go (//go:build !solution) and solution.go (//go:build solution).
package breaker

import (
	"errors"
	"fmt"
	"sync"
	"time"
)

// State of the circuit breaker.
type State int

const (
	StateClosed State = iota
	StateOpen
	StateHalfOpen
)

func (s State) String() string {
	switch s {
	case StateClosed:
		return "closed"
	case StateOpen:
		return "open"
	case StateHalfOpen:
		return "half_open"
	}
	return "unknown"
}

// Sentinel errors. Tests match on these with errors.Is.
var (
	ErrBreakerOpen = errors.New("circuit breaker is open")
	ErrBulkheadFull = errors.New("bulkhead is full")
	ErrTimeout     = errors.New("deadline exceeded")
)

// Clock is the injectable time source. NOTHING in this lab may call
// time.Now() directly — tests that sleep are broken tests.
type Clock interface {
	Now() time.Time
}

type systemClock struct{}

func (systemClock) Now() time.Time { return time.Now() }

// SystemClock reads the real wall clock.
func NewSystemClock() Clock { return systemClock{} }

// FakeClock is a deterministic clock for tests. Advance moves time without
// blocking; Sleep records instead of blocking and advances the fake time.
type FakeClock struct {
	mu    sync.Mutex
	t     time.Duration
	Sleeps []time.Duration // every Sleep() call, in order
}

func NewFakeClock() *FakeClock { return &FakeClock{} }

func (c *FakeClock) Now() time.Time { return time.Unix(0, 0).Add(c.snapshot()) }

func (c *FakeClock) snapshot() time.Duration {
	c.mu.Lock()
	defer c.mu.Unlock()
	return c.t
}

// Advance moves fake time forward without blocking.
func (c *FakeClock) Advance(d time.Duration) {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.t += d
}

// Sleep does NOT block — it records the request and fast-forwards.
func (c *FakeClock) Sleep(d time.Duration) {
	c.mu.Lock()
	c.Sleeps = append(c.Sleeps, d)
	c.t += d
	c.mu.Unlock()
}

// Stats are the counters every primitive exposes via .Stats().
type Stats struct {
	Calls       int
	Failures    int
	Rejections  int
	Exhausted   int
	MaxConcurrent int
	Transitions [][2]string // (from, to) pairs, e.g. {"closed","open"}
}

func (s *Stats) record(from, to State) {
	s.Transitions = append(s.Transitions, [2]string{from.String(), to.String()})
}

// Config configures CircuitBreaker. Zero values get sensible defaults;
// use DefaultConfig() as a base when overriding selectively.
type Config struct {
	FailureRateThreshold  float64       // trip when failure rate >= this (0..1]
	SlidingWindow         int           // last N calls evaluated
	MinCalls              int           // don't evaluate until N calls recorded
	OpenDuration          time.Duration // how long OPEN waits before HALF_OPEN
	HalfOpenProbes        int           // successful probes required to CLOSE
	SlowCallRateThreshold float64       // trip on slow-call rate >= this
	SlowCallDuration      time.Duration // a call longer than this is "slow"
	// Ignore reports errors that must NOT count as failures
	// (e.g. 404s from the dependency are business outcomes, not faults).
	Ignore func(error) bool
}

func DefaultConfig() Config {
	return Config{
		FailureRateThreshold:  0.5,
		SlidingWindow:         100,
		MinCalls:              20,
		OpenDuration:          30 * time.Second,
		HalfOpenProbes:        5,
		SlowCallRateThreshold: 1.1, // disabled by default (>1 never trips)
		SlowCallDuration:      5 * time.Second,
	}
}

func (c Config) String() string {
	return fmt.Sprintf("Config{rate:%.2f window:%d min:%d}", c.FailureRateThreshold, c.SlidingWindow, c.MinCalls)
}
