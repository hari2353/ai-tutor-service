package com.tutor.ratelimit;

/** STARTER — the naive fixed window: resets to zero at every aligned
 *  boundary, which is exactly why it allows a 2x burst across one.
 *  Included on purpose: the sliding-window test proves the difference. */
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

    public boolean tryAcquire() {
        return true;
    }

    public long currentCount() {
        return count;
    }
}
