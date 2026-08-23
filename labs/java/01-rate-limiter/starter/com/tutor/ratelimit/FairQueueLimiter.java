package com.tutor.ratelimit;

import java.util.Map;

/** STARTER — allocates a shared token budget round-robin across clients with
 *  pending work, so one noisy client cannot starve everyone else. */
public class FairQueueLimiter {
    protected final double capacity;
    protected final double refillPerSecond;
    protected final RateLimitClock clock;
    protected double tokens;
    protected double lastRefillAt;

    public FairQueueLimiter(double capacity, double refillPerSecond, RateLimitClock clock) {
        this.capacity = capacity;
        this.refillPerSecond = refillPerSecond;
        this.clock = clock;
        this.tokens = capacity;
        this.lastRefillAt = clock.nowSeconds();
    }

    /** Distribute tokens round-robin over DISTINCT client ids (sorted order
     *  for determinism). Returns admitted count per client id. */
    public Map<String, Integer> processBatch(Map<String, Integer> pendingByClient) {
        return FairQueueSupport.empty();
    }
}
