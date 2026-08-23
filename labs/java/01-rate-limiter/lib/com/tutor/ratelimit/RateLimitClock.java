package com.tutor.ratelimit;

/** Injectable time source. NOTHING in this lab may call System.nanoTime()
 *  directly — tests that sleep are broken tests. */
public interface RateLimitClock {
    double nowSeconds();
}
