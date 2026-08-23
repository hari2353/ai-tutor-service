package com.tutor.ratelimit;

/** SOLUTION — reference implementation. Read it AFTER your own version passes. */

/** The fix for the fixed window's 2x-boundary bug. Estimate the trailing
 *  window's load by blending the PREVIOUS aligned window's count into the
 *  current one, weighted by how much of the previous window is still inside
 *  the look-back: est = current + previous * (window - posInCurrent)/window.
 *  Right at a boundary a maxed-out previous window keeps throttling the new
 *  one; the estimate decays smoothly as the boundary recedes. */
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

    private void roll() {
        double now = clock.nowSeconds();
        if (windowStart < 0) {
            windowStart = Math.floor(now / windowSeconds) * windowSeconds; // aligned
            return;
        }
        if (now >= windowStart + windowSeconds) {
            // A jump of more than one full window means NO part of the old
            // previous window is still relevant.
            boolean adjacent = now - windowStart < 2 * windowSeconds;
            previousCount = adjacent ? currentCount : 0;
            currentCount = 0;
            windowStart += Math.floor((now - windowStart) / windowSeconds) * windowSeconds;
        }
    }

    public boolean tryAcquire() {
        roll();
        if (estimate() + 1e-9 < limit) {
            currentCount++;
            return true;
        }
        return false;
    }

    public double estimate() {
        roll();
        double pos = clock.nowSeconds() - windowStart;
        double fraction = Math.max(0.0, Math.min(1.0, (windowSeconds - pos) / windowSeconds));
        return currentCount + previousCount * fraction;
    }
}
