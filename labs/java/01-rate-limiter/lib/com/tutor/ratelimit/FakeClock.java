package com.tutor.ratelimit;

/** Deterministic clock for tests: advance() moves time without blocking. */
public final class FakeClock implements RateLimitClock {
    private double seconds;

    @Override
    public double nowSeconds() {
        return seconds;
    }

    public void advance(double deltaSeconds) {
        if (deltaSeconds < 0) {
            throw new IllegalArgumentException("time cannot go backwards");
        }
        seconds += deltaSeconds;
    }

    public void set(double seconds) {
        this.seconds = seconds;
    }
}
