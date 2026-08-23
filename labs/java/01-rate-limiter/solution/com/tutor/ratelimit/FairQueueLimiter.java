package com.tutor.ratelimit;

import java.util.Map;
import java.util.TreeMap;

/** SOLUTION — reference implementation. Read it AFTER your own version passes. */

/** Allocates a shared token budget round-robin across DISTINCT clients with
 *  pending work. Sorted client order makes allocation deterministic. One
 *  client submitting far more than everyone else cannot starve the rest:
 *  each pass gives every pending client at most one token before wrapping. */
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

    public Map<String, Integer> processBatch(Map<String, Integer> pendingByClient) {
        double now = clock.nowSeconds();
        tokens = Math.min(capacity, tokens + (now - lastRefillAt) * refillPerSecond);
        lastRefillAt = now;

        Map<String, Integer> admitted = new TreeMap<>();
        Map<String, Integer> pending = new TreeMap<>(pendingByClient);

        boolean progressed = true;
        while (tokens + 1e-9 >= 1.0 && progressed) {
            progressed = false;
            for (Map.Entry<String, Integer> e : pending.entrySet()) {
                if (e.getValue() > 0 && tokens + 1e-9 >= 1.0) {
                    tokens -= 1.0;
                    admitted.merge(e.getKey(), 1, Integer::sum);
                    e.setValue(e.getValue() - 1);
                    progressed = true;
                }
            }
        }
        return admitted;
    }
}
