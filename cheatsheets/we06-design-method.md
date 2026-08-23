# Designing From Scratch: Requirements → Constraints → API → Data → Scale → Failure

> Sprint weekend 6 · source: `curriculum/10-system-design/10-design-method.md`

```
TIME BUDGET (45 min):
  0-2   restate + scope contract + "anywhere you want me deep?"
  2-7   requirements: 3-5 FRs (cap it), NFR table, say what's OUT of scope
  7-12  numbers: 3 you will USE, say what each decides, peak = avg x 3
  12-17 API: 3-6 signatures, /v1/, Idempotency-Key, cursor not offset, 202 = async
  17-24 data model: tables + PARTITION KEY + row bytes + "is this query 1-partition?"
  24-32 architecture: read path first, then write, then async. Every box traces up.
  32-38 scale: per-component first-limit + number + fix; RANK the bottlenecks
  38-43 failure: kill each box; user sees / operator sees / recovery
  43-45 wrap: build-first, biggest risk, what you'd cut

NFR CHECKLIST = SCALD-CoM
  Scale · Consistency · Availability · Latency · Durability · Cost · Multi-tenancy

GOOD CLARIFYING QUESTION = names 2 alternatives + says they lead to different designs
  read:write ratio? · fanout distribution (celebrity accounts)? · chronological or ranked?
  retention? · real-time push or pull? · global/residency? · SLO + p99 target?

HARD RULES
  no box before a requirement or number that produced it
  every named component gets ONE number (size / TTL / partitions / key)
  interviewer scores the PROCESS; mutation-resistance is the thing being tested
  blocked question -> state assumption + its consequence + move on
  wrong assumption at min 30 -> walk the branch you already named, do NOT restart
  architecture on the board by minute 32, no exceptions

2026 ADDITIONS
  cost is graded: name the dominant line item + a number
  LLM in the loop: token budget NFR, async + cached, deterministic fallback, eval suite
  half of loops now have an ML-adjacent prompt

HIGHEST-VALUE VOLUNTEERED SENTENCE
  named failure mode + observable symptom + mitigation
  e.g. cold-cache thundering herd -> Cassandra p99 spike -> single-flight + jittered warm-up
```
