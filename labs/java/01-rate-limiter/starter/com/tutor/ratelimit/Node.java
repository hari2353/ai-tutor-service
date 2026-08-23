package com.tutor.ratelimit;

import java.util.Map;

/** STARTER — wraps a bucket shared by several "app servers". Exists to prove
 *  that per-node buckets multiply your real limit by nodeCount. */
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
        return false;
    }
}

class FairQueueSupport {
    private FairQueueSupport() {}

    static Map<String, Integer> empty() {
        return new java.util.TreeMap<>();
    }
}
