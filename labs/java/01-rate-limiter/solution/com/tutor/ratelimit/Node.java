package com.tutor.ratelimit;

/** SOLUTION — reference implementation. Read it AFTER your own version passes. */

/** Wraps ONE bucket shared by several "app servers" — the correct distributed
 *  pattern (one counter, e.g. a Redis key, read/written by every node).
 *  Give each node its own bucket instead and the effective limit becomes
 *  capacity × nodeCount; the tests demonstrate exactly that bug. */
public class Node {
    private final String nodeId;
    private final TokenBucket sharedBucket;

    public Node(String nodeId, TokenBucket sharedBucket) {
        this.nodeId = nodeId;
        this.sharedBucket = sharedBucket;
    }

    public String nodeId() {
        return nodeId;
    }

    public boolean tryAcquire() {
        return sharedBucket.tryAcquire();
    }

    public double available() {
        return sharedBucket.available();
    }
}
