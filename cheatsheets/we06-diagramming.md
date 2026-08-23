# How to DRAW a System: C4 Model, Sequence, Dataflow, Deployment — Live on a Whiteboard

> Sprint weekend 6 · source: `curriculum/10-system-design/12-diagramming.md`

```
FOUR TYPES, FOUR QUESTIONS
  C4 container   WHAT exists + tech + where state lives   ← DEFAULT, always draw
  Sequence       WHEN / order / latency budget / failure   ← "walk me through X"
  Dataflow       HOW data transforms + volume + replay     ← pipelines, freshness
  Deployment     WHAT IT RUNS ON + blast radius + RPO/RTO  ← AZ/region questions

C4 LEVELS   L1 context (5-8 boxes, only if scope contested, 60s)
            L2 container (8-15 boxes) ← THE interview diagram
            L3 component (5-8 boxes) ← deep dive only, in FRESH space
            L4 code ← never

FIRST 20 SECONDS  divide the board:
   20% left = requirements + NFRs + numbers (NEVER erase)
   55% mid  = container diagram
   25% right= deep dives (keep empty until ~min 30)
   then place TWO ANCHORS: client far left, primary datastore far right

DRAWING ORDER  anchors → happy-path READ end-to-end → WRITE path below →
               ASYNC below a visible line → annotate numbers (2nd pass) →
               deep dives in right column.  Narrate every transition.

EDGE GRAMMAR   protocol/format · sync|async · payload · rate-or-latency
               HTTPS/JSON · sync · 6 KB · 15k rps
               ── solid = sync (SUMS into latency budget)
               ╌╌ dashed = async (needs at-least-once + idempotent consumer)
               arrow direction = INITIATES, not data flow. State the convention.

SCALE PASS  1 rate on hot edges · 2 size on stateful boxes · 3 "×12 (3 AZ)"
            4 BOTTLENECK double-boxed with its binding constraint
            5 partition key on every sharded store
            6 "not drawn:" line ← converts omissions into scoping decisions

LEAVE OUT (say once, don't draw)  authn/authz · o11y · CI/CD · DNS/TLS ·
            secrets/config · internal LBs · mesh sidecars · individual replicas
            RULE: only draw what you can defend in depth. Boxes invite questions.

CAPS   12-15 boxes · group into 3-5 labelled regions (7±2 working memory)
       container diagram ~8 min · sequence ~4 min · dataflow ~4 min · deploy ~3 min

PIPELINE MUST-HAVES  volume on every edge · narrow stage marked + burst policy ·
                     DLQ + failure rate · idempotency key · freshness SLO owner

DEPLOYMENT MUST-HAVES  replica counts · instance types · anti-affinity per shard ·
                       RPO + RTO as numbers · which store is source of truth vs
                       rebuildable derived index

TOOLS  Mermaid (repo default) · Structurizr DSL (one model → all C4 levels) ·
       D2 · Excalidraw (canvas) · ADR is the real artefact; diagram indexes it
```
