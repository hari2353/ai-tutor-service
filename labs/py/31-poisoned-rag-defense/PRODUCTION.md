# Production notes - poisoned RAG defense

The lab's resolver is deliberately small. In production, it sits after retrieval and isolated claim extraction, not instead of ACL-aware retrieval, provenance capture, quarantine, or attack-landing evaluation.

| Lab | Production addition |
|---|---|
| `Claim` | immutable source/version/hash/tier/ACL/review metadata |
| `normalize_value` | domain-specific units, locale-aware money/date parsing, audited equivalence rules |
| tier comparison | versioned policy engine with explicit conflict and freshness rules |
| `Decision` | citation spans, policy version, trace ID, confidence/abstention reason |
| list input | streaming claims with bounded memory and deterministic ordering |

Common failure modes are attacker-controlled duplicate documents, unapproved uploads entering the live index, cache entries surviving quarantine, and a false `abstained` result caused by an upstream timeout. Store candidate IDs, claim extraction status, resolver policy, and source versions so an incident can identify affected answers.

The resolver must never be the only defense. Enforce tenant and ACL filters during retrieval, retain immutable originals and content hashes, quarantine untrusted sources, invalidate cache entries by source dependency, and run a poisoning suite with an attack-landing gate. A zero attack-success number is meaningless if the attack never reached the reader.
