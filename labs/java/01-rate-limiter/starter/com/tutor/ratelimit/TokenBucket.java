package com.tutor.ratelimit;

/** STARTER — compiles but the behavior is wrong. The suite fails against
 *  these classes; that is the point. Make the tests pass without touching
 *  lib/ or tests/. */

/** Token bucket: burst up to capacity, then sustained refillPerSecond. */
public class TokenBucket {
    protected final double capacity;
    protected final double refillPerSecond;
    protected final RateLimitClock clock;
    protected double tokens;
    protected double lastRefillAt;

    public TokenBucket(double capacity, double refillPerSecond, RateLimitClock clock) {
        this(capacity, refillPerSecond, clock, capacity);
    }

    public TokenBucket(double capacity, double refillPerSecond, RateLimitClock clock, double initialTokens) {
        this.capacity = capacity;
        this.refillPerSecond = refillPerSecond;
        this.clock = clock;
        this.tokens = initialTokens;
        this.lastRefillAt = clock.nowSeconds();
    }

    /** Try to spend `cost` tokens; only success spends anything. */
    public boolean tryAcquire(double cost) {
        return false;
    }

    public boolean tryAcquire() {
        return tryAcquire(1.0);
    }

    /** Tokens currently available (after applying elapsed refill). */
    public double available() {
        return 0;
    }
}
