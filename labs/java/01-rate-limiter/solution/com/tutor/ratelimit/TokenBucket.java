package com.tutor.ratelimit;

/** SOLUTION — reference implementation. Read it AFTER your own version passes. */

/** Token bucket: a fresh bucket permits an immediate burst of up to
 *  `capacity`; after that, sustained throughput is exactly `refillPerSecond`
 *  requests/second. Refill is continuous, not windowed. Only successful
 *  acquires spend tokens. */
public class TokenBucket {
    protected final double capacity;
    protected final double refillPerSecond;
    protected final RateLimitClock clock;
    protected double tokens;
    protected double lastRefillAt;

    public TokenBucket(double capacity, double refillPerSecond, RateLimitClock clock) {
        this(capacity, refillPerSecond, clock, capacity);
    }

    public TokenBucket(double capacity, double refillPerSecond, RateLimitClock clock,
                       double initialTokens) {
        if (capacity <= 0 || refillPerSecond < 0) {
            throw new IllegalArgumentException("capacity must be > 0 and refill >= 0");
        }
        if (initialTokens < 0 || initialTokens > capacity) {
            throw new IllegalArgumentException("initialTokens must be within [0, capacity]");
        }
        this.capacity = capacity;
        this.refillPerSecond = refillPerSecond;
        this.clock = clock;
        this.tokens = initialTokens;
        this.lastRefillAt = clock.nowSeconds();
    }

    private void refill() {
        double now = clock.nowSeconds();
        tokens = Math.min(capacity, tokens + (now - lastRefillAt) * refillPerSecond);
        lastRefillAt = now;
    }

    public boolean tryAcquire(double cost) {
        if (cost <= 0 || cost > capacity) {
            throw new IllegalArgumentException("cost must be in (0, capacity]");
        }
        refill();
        if (tokens + 1e-9 >= cost) {
            tokens -= cost; // spend ONLY on success
            return true;
        }
        return false;
    }

    public boolean tryAcquire() {
        return tryAcquire(1.0);
    }

    public double available() {
        refill();
        return tokens;
    }
}
