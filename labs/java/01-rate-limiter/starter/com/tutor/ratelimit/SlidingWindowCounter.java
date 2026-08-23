package com.tutor.ratelimit;

/** STARTER — placeholder for the sliding-window counter that fixes the fixed
 *  window's 2x-boundary bug by blending the previous window's count into the
 *  estimate, weighted by how much of it is still inside the look-back. */
public class SlidingWindowCounter {
    protected final long limit;
    protected final double windowSeconds;
    protected final RateLimitClock clock;
    protected long currentCount;
    protected long previousCount;
    protected double windowStart = -1;

    public SlidingWindowCounter(long limit, double windowSeconds, RateLimitClock clock) {
        this.limit = limit;
        this.windowSeconds = windowSeconds;
        this.clock = clock;
    }

    public boolean tryAcquire() {
        return false;
    }

    /** The blended estimate: current + previous * fraction of previous still
     *  inside the trailing window. */
    public double estimate() {
        return 0;
    }
}
