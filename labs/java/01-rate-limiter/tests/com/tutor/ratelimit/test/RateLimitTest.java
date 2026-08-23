package com.tutor.ratelimit.test;

import java.util.HashMap;
import java.util.Map;

import com.tutor.ratelimit.FakeClock;
import com.tutor.ratelimit.FairQueueLimiter;
import com.tutor.ratelimit.FixedWindowCounter;
import com.tutor.ratelimit.Node;
import com.tutor.ratelimit.RateLimitClock;
import com.tutor.ratelimit.SlidingWindowCounter;
import com.tutor.ratelimit.TokenBucket;

/**
 * Zero-dependency test harness (no JUnit download needed).
 * Run:            java ... RateLimitTest           → starter, MUST FAIL
 * Reference:      LAB_IMPL=solution gate script    → MUST PASS
 */
public final class RateLimitTest {
    private static int passed = 0;
    private static int failed = 0;

    private static void check(String name, boolean cond) {
        if (cond) {
            passed++;
            System.out.println("  ok  " + name);
        } else {
            failed++;
            System.out.println("  FAIL " + name);
        }
    }

    private static int admitted(TokenBucket b, int n) {
        int k = 0;
        for (int i = 0; i < n; i++) {
            if (b.tryAcquire()) k++;
        }
        return k;
    }

    /** Bounded admission probes — a broken implementation under test may
     *  never say "yes" forever, so no loop here can spin without end. */
    private static int probe(TokenBucket b, int tries) {
        int k = 0;
        for (int i = 0; i < tries; i++) {
            if (b.tryAcquire()) k++;
        }
        return k;
    }

    private static int probe(FixedWindowCounter w, int tries) {
        int k = 0;
        for (int i = 0; i < tries; i++) {
            if (w.tryAcquire()) k++;
        }
        return k;
    }

    private static int probe(SlidingWindowCounter w, int tries) {
        int k = 0;
        for (int i = 0; i < tries; i++) {
            if (w.tryAcquire()) k++;
        }
        return k;
    }

    // ------------------------------------------------------------ token bucket

    private static void burstThenThrottle() {
        FakeClock c = new FakeClock();
        TokenBucket b = new TokenBucket(5, 1.0, c);
        check("fresh bucket permits an immediate burst of capacity", admitted(b, 10) == 5);
        c.advance(1.0);
        check("after one second exactly refill_rate tokens exist", b.tryAcquire() && !b.tryAcquire());
    }

    private static void fractionalRefillAccumulates() {
        FakeClock c = new FakeClock();
        TokenBucket b = new TokenBucket(5, 1.0, c);
        admitted(b, 5); // drain
        c.advance(0.5);
        check("half a second is not enough yet", !b.tryAcquire());
        c.advance(0.5);
        check("two halves accumulate into one token", b.tryAcquire());
    }

    private static void costsAndNoSpendOnFailure() {
        FakeClock c = new FakeClock();
        TokenBucket b = new TokenBucket(10, 1.0, c, 4);
        check("multi-token cost succeeds when funded", b.tryAcquire(4));
        check("bucket is now empty", b.available() == 0.0);
        double before = b.available();
        check("failed acquire spends nothing", !b.tryAcquire(1) && b.available() == before);
        c.advance(60);
        check("refill caps at capacity", b.available() <= 10.000001);
    }

    // -------------------------------------------------------- fixed vs sliding

    private static void fixedWindowAllows2xBurstAcrossBoundary() {
        FakeClock c = new FakeClock();
        FixedWindowCounter w = new FixedWindowCounter(10, 1.0, c);
        c.set(0.9);
        int first = probe(w, 50);
        c.set(1.1);
        int second = probe(w, 50);
        check("fixed window: 10 admitted late in window one", first == 10);
        check("fixed window BUG: another 10 immediately across the boundary",
                second == 10 && first + second == 20);
    }

    private static void slidingWindowDoesNotAllow2xBurstAcrossBoundary() {
        FakeClock c = new FakeClock();
        SlidingWindowCounter w = new SlidingWindowCounter(10, 1.0, c);
        c.set(0.9);
        int first = probe(w, 50);
        c.set(1.1);
        int second = probe(w, 50);
        check("sliding window: full budget before the boundary", first == 10);
        // est at 1.1s = prev(10) * (1-0.1) = 9 → exactly ONE more fits.
        check("sliding window FIX: only 1 more across the boundary", second == 1);
    }

    private static void slidingWindowRecoversAsBoundaryRecedes() {
        FakeClock c = new FakeClock();
        SlidingWindowCounter w = new SlidingWindowCounter(5, 1.0, c);
        c.set(0.05);
        int drained = probe(w, 50);
        c.set(2.1);
        int recovered = probe(w, 50);
        check("old windows age out: budget substantially restored",
                drained == 5 && recovered >= 4);
    }

    // ------------------------------------------------------------------ nodes

    private static void sharedBucketNotPerNodeBuckets() {
        FakeClock c = new FakeClock();
        TokenBucket shared = new TokenBucket(6, 0.0, c);
        Node[] nodes = { new Node("a", shared), new Node("b", shared), new Node("c", shared) };
        int totalShared = 0;
        for (Node n : nodes) {
            for (int i = 0; i < 10; i++) {
                if (n.tryAcquire()) totalShared++;
            }
        }
        check("shared counter: cluster-wide total is the real limit", totalShared == 6);

        // The bug this avoids: independent buckets multiply the limit.
        FakeClock c2 = new FakeClock();
        int totalNaive = 0;
        for (int i = 0; i < 3; i++) {
            TokenBucket own = new TokenBucket(6, 0.0, c2);
            for (int k = 0; k < 10; k++) {
                if (own.tryAcquire()) totalNaive++;
            }
        }
        check("per-node buckets silently become capacity x nodeCount", totalNaive == 18);
    }

    // -------------------------------------------------------------- fair queue

    private static void fairQueueIsRoundRobinNotGreedy() {
        FakeClock c = new FakeClock();
        FairQueueLimiter fq = new FairQueueLimiter(4, 0.0, c);
        Map<String, Integer> batch = new HashMap<>();
        batch.put("noisy-client", 100);
        batch.put("quiet-client", 2);
        Map<String, Integer> got = fq.processBatch(batch);
        int a = got.getOrDefault("noisy-client", 0);
        int b = got.getOrDefault("quiet-client", 0);
        check("fair queue: quiet client is not starved", b == 2);
        check("fair queue: noisy client gets its equal share", Math.abs(a - b) <= 1);
    }

    public static void main(String[] args) {
        RateLimitClock ignored = new FakeClock(); // keep import honest
        burstThenThrottle();
        fractionalRefillAccumulates();
        costsAndNoSpendOnFailure();
        fixedWindowAllows2xBurstAcrossBoundary();
        slidingWindowDoesNotAllow2xBurstAcrossBoundary();
        slidingWindowRecoversAsBoundaryRecedes();
        sharedBucketNotPerNodeBuckets();
        fairQueueIsRoundRobinNotGreedy();

        System.out.println();
        System.out.println("passed=" + passed + " failed=" + failed);
        System.exit(failed > 0 ? 1 : 0);
    }
}
