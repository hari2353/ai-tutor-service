package com.tutor.ratelimit;

/** SOLUTION — reference implementation. Read it AFTER your own version passes. */

/** The naive fixed window, kept as the honest buggy baseline: count resets to
 *  zero at every calendar-aligned boundary, so a client that saves up requests
 *  can push `limit` through at the end of one window and `limit` more right
 *  at the start of the next — 2x the limit in a near-instant span. */
public class FixedWindowCounter {
    protected final long limit;
    protected final double windowSeconds;
    protected final RateLimitClock clock;
    protected long count;
    protected double windowStart = -1;

    public FixedWindowCounter(long limit, double windowSeconds, RateLimitClock clock) {
        this.limit = limit;
        this.windowSeconds = windowSeconds;
        this.clock = clock;
    }

    private void roll() {
        double now = clock.nowSeconds();
        if (windowStart < 0) {
            windowStart = Math.floor(now / windowSeconds) * windowSeconds; // aligned
        }
        if (now >= windowStart + windowSeconds) {
            windowStart += Math.floor((now - windowStart) / windowSeconds) * windowSeconds;
            count = 0;
        }
    }

    public boolean tryAcquire() {
        roll();
        if (count < limit) {
            count++;
            return true;
        }
        return false;
    }

    public long currentCount() {
        roll();
        return count;
    }
}
