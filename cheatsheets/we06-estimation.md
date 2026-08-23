# Back-of-Envelope: Guesstimates, Latency/Throughput/Storage Math, Sanity Checks

> Sprint weekend 6 · source: `curriculum/10-system-design/11-estimation.md`

```
PROCEDURE   declare what it DECIDES → assume out loud → round to 1e → compute
            → AMPLIFY by fanout → sanity-check vs a known system → use it

CONVERSIONS 1M/day ≈ 10/s      1B/day ≈ 10,000/s      86,400 s/day → 1e5
            2^10 KB · 2^20 MB · 2^30 GB · 2^40 TB · 2^50 PB
            1 hour of 1080p @5 Mbps ≈ 2.25 GB   ·   1 token ≈ 4 chars

LATENCY     L1 1ns · L2 4ns · L3 12ns · RAM 60ns · NVMe rand 20-100us
            same-DC RTT 0.5ms · cross-AZ 1-2ms · US-EU 80ms · US-APAC 200ms
            LLM first token 300-800ms
            RAM ~1000x SSD · same-DC RTT ~1000x RAM · cross-continent ~200x same-DC
            fibre: 5 us/km → ~1 ms per 100 km one-way after routing

THROUGHPUT  NVMe 3-7 GB/s, 500k IOPS · gp3 125 MB/s / 3k IOPS baseline (40x slower!)
            100 GbE = 12.5 GB/s · Postgres 5-20k write TPS · Redis 100k ops/s
            JSON service ~2k rps/core · Cassandra partition ~1-3k writes/s

BYTES       UUID 16B bin / 36B text · int64 8B · narrow row 40-60B
            entity row ~500B · Redis per-key overhead 50-100B  ← the cache trap
            zset >128 members flips listpack→skiplist: ~40B becomes ~100B/member
            1024-dim fp32 vector 4KB (int8 1KB, binary 128B)

PEAK/AVG    global consumer 2-3x · single region 3-5x · B2B 4-8x
            cron 10-100x · launch/event 10-1000x
            SIZE AT 60% UTIL: M/M/1 wait = service x rho/(1-rho); rho=.9 → 9x
            Little's Law: concurrency = throughput x latency

SPLITS      feed 100:1 R:W · messaging 1:1 · commerce 20:1 · ASK, don't assume
            80/20 keys, but Zipf: 80%→95% hit rate costs far more than 1.2x memory
            hottest single key can be 1-5% of ALL traffic (hash won't fix it)
            AMPLIFIED WRITE = logical writes x fanout   ← the number that breaks

NINES       99% 3.65d/yr · 99.9% 8.8h · 99.99% 53min · 99.999% 5min
            serial deps MULTIPLY: 5 x 99.9% = 99.5% = 43h/yr

STORAGE     records x bytes x retention x replication x (1 + index) + WAL/backups

COST 2026   egress $0.05/GB list, $0.005-0.01 negotiated  ← often the top line item
            LLM ~$2/$10 per M in/out (Sonnet-class); cache reads ~10% of input
            Flash-class ~$0.10/$0.40 (≈20x cheaper) · Batch API -50%
            r7g.8xlarge (256 GB) ~$1.7/hr ≈ $1,240/mo

RECOVERY    name it precisely → don't restart → identify the ONE decision it feeds
            → walk the branch you pre-named → say what you'd measure
            PRE-EMPT: state every assumption WITH its sensitivity ("if 10x off, I'd...")
```
