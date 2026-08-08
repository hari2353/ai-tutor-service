# How to DRAW a System: C4, Sequence, Dataflow, Deployment

> **Track:** T10 System Design · **Time:** 2.5h · **Prereqs:** `T10-design-method` · **Updated:** 2026-07-26
> **Module id:** `T10-diagramming` · **Tags:** sprint, craft, critical

## The 30-second version

There are four diagram types you need and they answer four different questions: **C4** answers "what are the pieces and where do they live" (and an interview almost always wants exactly the container level, C4's level 2), **sequence** answers "what happens in order for one request", **dataflow** answers "how does data move and get transformed through a pipeline", and **deployment** answers "what physical or cloud infrastructure runs it". The single most common failure is drawing one diagram that tries to be all four at once, which produces a picture where a box might be a service, a library, a process, or a machine, and an arrow might mean a call, a dependency, or a data movement. On a whiteboard the discipline is: pick a type, announce it, keep to 12 to 15 boxes, label every edge with protocol plus sync-or-async, and draw the happy-path read end to end before you draw anything else. Everything you leave out (auth, logging, CI/CD, DNS, individual replicas) you mention once out loud and then do not draw, because whiteboard real estate is the scarcest resource in the round.

## Why this gets asked

It is not asked directly. It is scored continuously, because the diagram is the medium through which every other part of your answer is transmitted. The interviewer has sat through a design review where a diagram had thirty boxes, unlabelled arrows, and no indication of which calls were on the critical path, and the review spent forty minutes on "wait, is that a service or a database?" instead of on the actual risk. So the thing they are watching for is whether your picture makes your reasoning *checkable*. Concretely: they want to be able to point at an arrow and ask "what's the p99 on that hop, and what happens if it fails", and if the arrow is unlabelled they cannot, so the conversation degrades into clarification. Guidance across interview-prep sources converges on the same handful of behaviours: label the arrows, use consistent shapes, distinguish sync from async visually, start simple and elaborate, and never switch the meaning of a symbol midstream ([Exponent, whiteboarding for system design](https://www.tryexponent.com/blog/how-to-whiteboard-for-system-design-interviews), [DesignGurus, mastering the whiteboard](https://designgurus.substack.com/p/mastering-the-whiteboard-a-step-by) — both accessed 2026-07-26).

---

## Lineage: past → present → future

**What came before.** The 1990s answer was UML, and specifically the full thirteen-diagram UML 2.x taxonomy plus tooling (Rational Rose, later Enterprise Architect) that promised model-driven development. Kruchten's 4+1 view model (1995) was the serious attempt at organising architectural views: logical, process, development, physical, plus scenarios. The pain that killed it was twofold. First, **cost of maintenance**: the diagrams were generated once for a design review, then diverged from the code within weeks, so nobody trusted them, so nobody updated them, so they were useless. Second, **notational overhead**: UML has strict semantics for aggregation versus composition, for stereotypes, for lifelines, and almost no working engineer knew them, so a diagram drawn correctly was read incorrectly. The industry's practical reaction was to abandon notation entirely and draw "boxes and lines", which solved the learning cost by reintroducing the original problem: a box could mean anything.

**Where it stands now.** Simon Brown's C4 model (introduced around 2011, stabilised through the 2010s) is the current de facto standard and it succeeded precisely because it is minimal: four nested levels of abstraction, one notion of "container" meaning a separately-deployable-and-runnable thing, and no prescribed notation beyond "label everything and include a legend" ([c4model.com](https://c4model.com/) — accessed 2026-07-26). The consensus in practice is that levels 1 and 2 (context and container) carry most of the value and that level 4 (code) is essentially dead, because IDEs generate class diagrams on demand and nobody hand-maintains them ([Baeldung, C4 abstraction levels](https://www.baeldung.com/cs/c4-model-abstraction-levels) — accessed 2026-07-26). Alongside C4, the other major shift is **diagrams-as-code**: Mermaid (now rendered natively by GitHub, GitLab, and Notion), Structurizr DSL (Brown's own, which generates all C4 levels from a single model so they cannot diverge from each other), PlantUML, and D2. This addresses the maintenance failure that killed UML by putting the diagram in the repo and in code review.

The live disagreement is about **how much rigour a diagram should carry**. One camp (C4 purists, Structurizr users) argues that a diagram without a defined abstraction level and a legend is not a diagram; the other argues that any formalism above "labelled boxes and labelled arrows" costs more than it returns and that the real artefact is the prose in the ADR, with the diagram as an index into it. For interview purposes both camps agree on the operative rule: **say which level you are drawing at, and keep the meaning of a symbol stable within a diagram.** A second, smaller disagreement is whether to draw a sequence diagram at all in a 45-minute round; the honest answer is that it is the highest-value second diagram when the interviewer asks "walk me through what happens when a user does X", and a waste of five minutes otherwise.

**Where it's heading.** High confidence: **diagrams-as-code wins for durable documentation** and the boundary between "the model" and "the diagram" continues to harden, with Structurizr-style single-model-many-views becoming the norm for anything that must stay accurate. Medium confidence: **drift detection** becomes standard, where a tool compares the declared container graph against observed traffic from distributed tracing and flags containers or edges that exist in one and not the other; OpenTelemetry service graphs already do a crude version of this and the gap to a maintained C4 model is small. Speculative, and relevant to interviews: as rounds move onto shared collaborative canvases and plain text editors, ASCII and Mermaid become the interview medium rather than a marker, which advantages candidates who can type a clean box diagram quickly and disadvantages nobody, since a text diagram forces you to be explicit about labels in a way a scribble does not. Ask at the start of the round which medium is being used.

---

## Mental model

A diagram is a **map at a chosen zoom level**, and mixing zoom levels is the entire failure mode. You would not draw a world map with one country's street layout inside it, and the reason is not aesthetic: it is that the reader cannot tell which distances are comparable.

```
      C4 = ZOOM. Same system, four magnifications.
   ┌──────────────────────────────────────────────────────────────────┐
   │ L1 CONTEXT     "what is this system and who/what touches it"     │
   │                1 box for YOUR system + users + external systems  │
   │                audience: non-technical. 5-8 boxes total.         │
   │   ┌──────────────────────────────────────────────────────────┐   │
   │   │ L2 CONTAINER  "what separately-deployable things exist,   │   │
   │   │                what tech, how do they talk"               │   │
   │   │  ← THIS IS THE INTERVIEW DIAGRAM. 8-15 boxes.             │   │
   │   │   ┌──────────────────────────────────────────────────┐    │   │
   │   │   │ L3 COMPONENT  "inside ONE container, what are the │    │   │
   │   │   │   major modules"  ← only for the deep-dive box    │    │   │
   │   │   │   ┌──────────────────────────────────────────┐    │    │   │
   │   │   │   │ L4 CODE   classes. Effectively dead.     │    │    │   │
   │   │   │   │ Never draw this in an interview.         │    │    │   │
   │   │   │   └──────────────────────────────────────────┘    │    │   │
   │   │   └──────────────────────────────────────────────────┘    │   │
   │   └──────────────────────────────────────────────────────────┘   │
   └──────────────────────────────────────────────────────────────────┘

      THE OTHER THREE ARE NOT ZOOM LEVELS. They are different QUESTIONS
      about the same L2 diagram:

        C4 container   →  WHAT exists and WHERE          (structure, static)
        Sequence       →  WHEN, in what order, one req   (time, dynamic)
        Dataflow       →  HOW data is transformed        (transformation)
        Deployment     →  WHAT IT RUNS ON                (infrastructure)
```

**The test for whether your diagram has a consistent zoom level:** every box at the same level should be the same *kind* of thing. If one box is "Postgres" and the next is "the retry decorator", you have mixed levels and the reader has lost the ability to compare them.

---

## How it actually works

### C4: the four levels, and the one the interview wants

**Level 1, Context.** One box for your system, surrounded by the people and external systems that touch it. No internals. Its job is to establish scope, which makes it the right thing to draw at minute 3 if the prompt is ambiguous, and a waste of time if it is not.

```
   ┌──────────┐                        ┌────────────────────┐
   │ Employee │───asks questions──────▶│                    │
   │ (person) │◀──answers + citations──│  DocuChat          │
   └──────────┘                        │  [Software System] │
   ┌──────────┐                        │                    │
   │  Admin   │───manages corpora─────▶│  answers questions │
   │ (person) │                        │  over internal docs│
   └──────────┘                        └───┬────┬───────┬───┘
                                           │    │       │
                    ┌──────────────────────┘    │       └──────────────┐
                    ▼                           ▼                      ▼
          ┌──────────────────┐        ┌──────────────────┐   ┌──────────────────┐
          │ SharePoint /     │        │  Okta            │   │ LLM Provider     │
          │ Confluence       │        │  [ext. system]   │   │ [ext. system]    │
          │ [ext. system]    │        │  SSO / OIDC      │   │ Anthropic/Bedrock│
          │ source documents │        └──────────────────┘   └──────────────────┘
          └──────────────────┘
```

In an interview, draw this **only if scope is genuinely contested**, and spend 60 seconds on it. Its real value is that it makes your out-of-scope declarations visual: everything not in the picture is not being built.

**Level 2, Container.** This is the diagram the interview wants. A container is a separately deployable and runnable thing: a service, an SPA, a mobile app, a database, a queue, an object store, a Lambda. Each box gets a **name, a type, and a one-line responsibility**, and each edge gets a label. The technology annotation is what makes it a design rather than a wish.

The size discipline matters: **8 to 15 boxes**. Below 8 you have hand-waved; above 15 the reader cannot hold it and the interviewer starts asking clarifying questions instead of design questions. Human working memory tops out around 7±2 chunks, which is why grouping boxes into 3 to 5 labelled regions (edge, read path, write path, async, storage) recovers legibility past about 10 boxes.

**Level 3, Component.** Inside a single container. This is exactly the right diagram for the deep dive, when the interviewer says "tell me more about the retriever". Draw it in *fresh space*, not on top of the container diagram, and keep it to 5 to 8 boxes.

```
   Inside the [Query Service] container:
   ┌───────────────────────────────────────────────────────────────┐
   │  ┌────────────┐   ┌──────────────┐   ┌───────────────────┐    │
   │  │ HTTP       │──▶│ AuthZ +      │──▶│ Query Planner     │    │
   │  │ Handler    │   │ Tenant Scope │   │ (rewrite, expand) │    │
   │  └────────────┘   └──────────────┘   └─────────┬─────────┘    │
   │                                                 │              │
   │        ┌────────────────────────────────────────┤              │
   │        ▼                        ▼               ▼              │
   │  ┌──────────┐          ┌─────────────┐   ┌───────────┐        │
   │  │ Vector   │          │ BM25/       │   │ Filter    │        │
   │  │ Retriever│          │ Keyword     │   │ Builder   │        │
   │  └────┬─────┘          └──────┬──────┘   └───────────┘        │
   │       └────────┬──────────────┘                                │
   │                ▼                                               │
   │        ┌───────────────┐    ┌─────────────┐   ┌────────────┐  │
   │        │ RRF Fusion    │───▶│ Cross-enc.  │──▶│ Context    │  │
   │        │               │    │ Reranker    │   │ Assembler  │  │
   │        └───────────────┘    └─────────────┘   └────────────┘  │
   └───────────────────────────────────────────────────────────────┘
```

**Level 4, Code.** Do not. If asked to go deeper than components, write code instead of drawing classes; that is what the interviewer wants anyway.

### Sequence diagrams: for one request, in order

A container diagram cannot express order, concurrency, or a timeout. A sequence diagram does all three, and it is what you draw when the question is "walk me through what happens when the user does X" or "where does the latency go".

ASCII conventions that read cleanly:

```
  ──▶   synchronous call (caller blocks)
  ╌╌▶   asynchronous / fire-and-forget (caller does not wait)
  ◀╌╌   response / callback
  ══▶   the critical path (thicken what dominates latency)
  [ ]   a note or a timing annotation
  ▓▓▓   time spent (shade the expensive spans)
```

```
 Client      API GW     Query Svc    Vector DB    Reranker      LLM
   │            │           │            │            │           │
   │ POST /ask  │           │            │            │           │
   ├───────────▶│           │            │            │           │
   │            │ authz     │            │            │           │
   │            │ (JWT, local verify, 0.2ms)          │           │
   │            ├──────────▶│            │            │           │
   │            │           │ embed query│            │           │
   │            │           ├─ 8ms ─────▶│(local ONNX)│           │
   │            │           │ ANN search ef=100       │           │
   │            │           ├───────────▶│            │           │
   │            │           │◀── 12ms ───┤ top-50     │           │
   │            │           │ rerank top-50           │           │
   │            │           ├────────────────────────▶│           │
   │            │           │◀────── 35ms ────────────┤ top-5     │
   │            │           │ generate (streaming)                │
   │            │           ├────────────────────────────────────▶│
   │            │           │◀═══ first token 420ms ══════════════┤
   │            │◀══════════┤ SSE stream begins                   │
   │◀═══════════┤           │                                     │
   │            │           │ log query + citations               │
   │            │           ╌╌╌╌╌╌╌╌╌╌╌╌▶ Kafka (async, off path) │
   │            │           │                                     │
   [ p99 to first token = 0.2 + 8 + 12 + 35 + 420 ≈ 475ms         ]
   [ 88% of it is the LLM. Optimising retrieval is pointless here. ]
```

That final bracket is why the sequence diagram earns its five minutes: **it makes the latency budget visible and immediately tells you which optimisation is worthless.** No container diagram can do that.

Three things to get right:
- **Put the latency on the arrow.** A sequence diagram without timings is a call graph with extra steps.
- **Show the async escape explicitly.** The dashed line to Kafka is the difference between "we log the query" and "logging is not on the user's critical path".
- **Show one failure variant if you have time.** A second, shorter sequence for "Vector DB times out at 50 ms → serve keyword-only results with a degraded-quality flag" is worth more than any additional box on the container diagram.

### Dataflow diagrams: for pipelines

When the system is a pipeline rather than a request-response service (ETL, ingestion, indexing, feature computation, training), the interesting content is transformation and volume, not call order. Draw stages left to right, and **annotate every edge with volume and every stage with what it changes**.

```
 SOURCES              INGEST            TRANSFORM              SINKS
 ┌──────────┐                                                              
 │SharePoint│─┐   ┌─────────────┐   ┌──────────────┐   ┌──────────────┐
 └──────────┘ │   │ Crawler     │   │ Parse +      │   │ Chunker      │
 ┌──────────┐ ├──▶│ (incremental│──▶│ Extract      │──▶│ 512 tok,     │──┐
 │Confluence│ │   │  by mtime)  │   │ (PDF/DOCX/   │   │ 64 overlap   │  │
 └──────────┘ │   └─────────────┘   │  HTML→text)  │   └──────────────┘  │
 ┌──────────┐ │    2M docs total    └──────────────┘    100M chunks      │
 │  S3 dump │─┘    ~50k new/day      ~30 GB/day raw     ~2.5M new/day    │
 └──────────┘                                                             │
                                                                          │
      ┌───────────────────────────────────────────────────────────────────┘
      ▼
 ┌──────────────┐        ┌──────────────┐        ┌────────────────────┐
 │ Embed        │        │ Upsert       │        │ Weaviate           │
 │ BGE-large    │───────▶│ (idempotent  │───────▶│ HNSW M=32          │
 │ 1024-dim     │        │  on doc_id + │        │ int8 quantised     │
 │ batch=256    │        │  chunk_hash) │        │ 132 GB resident    │
 │ 2.5M/day     │        └──────┬───────┘        └────────────────────┘
 │ ≈ 4 GPU-hr/d │               │
 └──────────────┘               ╰──────────────▶ ┌────────────────────┐
                                                  │ Postgres          │
      ┌──────────────┐                            │ chunk metadata,   │
      │ DLQ          │◀─── parse/embed failures ──│ acl, doc lineage  │
      │ (S3 + alert) │     ~0.5% of docs          └────────────────────┘
      └──────────────┘

  [ back-pressure: chunker → embedder is the narrow stage.
    embed throughput 2.5M chunks/day = 29/s; a 10x doc burst queues, not drops. ]
  [ idempotency key = (doc_id, chunk_index, content_hash) so re-crawl is free ]
```

The rules that separate a good dataflow diagram from a box chain:
- **Volume on every edge.** Documents in, chunks out, bytes per day. The narrow stage is then visible rather than argued about.
- **Name the transformation, not the technology.** "Chunker, 512 tokens, 64 overlap" beats "LangChain".
- **Draw the DLQ.** Every pipeline has failures; a pipeline diagram without an error path is a diagram of the happy day.
- **Mark the idempotency key.** Pipelines get replayed. Where dedup happens is the most important detail in the picture.
- **Mark the narrow stage and say what happens on burst** (queue, shed, or drop). That one annotation is the difference between a diagram and a design.

### Deployment diagrams: for infrastructure

The question is "what does this actually run on, and what is the failure domain". Draw the physical or cloud nesting: region contains AZ contains cluster/subnet contains node contains process. **Replica counts go on the box; failure domains are the boundaries.**

```
 ┌── Route 53 (latency routing) ──────────────────────────────────────────┐
 │                                                                         │
 │  ┌═══ REGION us-east-1 (primary) ══════════════════════════════════╕   │
 │  ║  ┌── ALB (cross-AZ) ─────────────────────────────────────────┐   ║   │
 │  ║  │  ┌─ AZ-a ────────┐ ┌─ AZ-b ────────┐ ┌─ AZ-c ────────┐   │   ║   │
 │  ║  │  │ EKS nodegroup │ │ EKS nodegroup │ │ EKS nodegroup │   │   ║   │
 │  ║  │  │ query-svc ×4  │ │ query-svc ×4  │ │ query-svc ×4  │   │   ║   │
 │  ║  │  │ c7g.2xlarge   │ │ c7g.2xlarge   │ │ c7g.2xlarge   │   │   ║   │
 │  ║  │  └───────────────┘ └───────────────┘ └───────────────┘   │   ║   │
 │  ║  └───────────────────────────────────────────────────────────┘   ║   │
 │  ║                                                                   ║   │
 │  ║  ┌─ Weaviate StatefulSet ──────────┐  ┌─ RDS Postgres ────────┐  ║   │
 │  ║  │ 4 shards × 2 replicas            │  │ primary   (AZ-a)      │  ║   │
 │  ║  │ r7g.8xlarge, 256 GB, spread      │  │ sync standby (AZ-b)   │  ║   │
 │  ║  │ across AZ a/b/c (anti-affinity)  │  │ read replica ×2       │  ║   │
 │  ║  │ EBS gp3 snapshot daily           │  │ PITR 7d               │  ║   │
 │  ║  └──────────────────────────────────┘  └───────────────────────┘  ║   │
 │  ║  ┌─ MSK Kafka 3 brokers (1/AZ) ─┐  ┌─ S3 (raw docs, versioned) ┐ ║   │
 │  ║  └──────────────────────────────┘  └───────────────────────────┘ ║   │
 │  ╘═══════════════════════════════╤═════════════════════════════════╛   │
 │            async replication ────┤  RPO ≈ 30s · RTO ≈ 15 min           │
 │  ┌═══ REGION eu-west-1 (warm standby, EU-resident tenants) ════════╕   │
 │  ║  scaled to 25%; Weaviate rebuilt from S3 + Postgres on failover ║   │
 │  ╘═════════════════════════════════════════════════════════════════╛   │
 └─────────────────────────────────────────────────────────────────────────┘
```

What earns points here: **replica counts, instance types, the AZ spread, and explicit RPO/RTO numbers.** "Multi-region" is a word; "async replication, RPO about 30 seconds, RTO about 15 minutes because Weaviate has to be rebuilt from S3" is a design. Also note the anti-affinity annotation: a StatefulSet with 4 shards × 2 replicas that lands both replicas of a shard in the same AZ is not multi-AZ, and saying that out loud shows you have operated one.

### The practical craft

#### What to draw FIRST on a blank whiteboard

Not a box. **Divide the space.** This is the single most valuable 20 seconds in the round, because running out of room at minute 30 forces you to erase the thing the interviewer wants to point at.

```
 ┌──────────────┬────────────────────────────────────────┬─────────────┐
 │ REQUIREMENTS │                                        │  SCRATCH /  │
 │              │        MAIN ARCHITECTURE               │  DEEP DIVE  │
 │ FR:          │        (C4 container level)             │             │
 │  1. ...      │                                        │  (keep this │
 │  2. ...      │   client ──▶ [ ] ──▶ [ ] ──▶ [ ]       │   EMPTY     │
 │  3. ...      │                       │                │   until     │
 │              │                       ▼                │   minute 30)│
 │ NFR:         │                      [ ]               │             │
 │  p99 200ms   │                                        │             │
 │  99.95%      │                                        │             │
 │  100:1 R:W   │                                        │             │
 │              │                                        │             │
 │ NUMBERS:     │                                        │             │
 │  15k rps pk  │                                        │             │
 │  250k ins/s  │                                        │             │
 │  1.6 TB      │                                        │             │
 └──────────────┴────────────────────────────────────────┴─────────────┘
    ~20% width            ~55% width                        ~25% width
    NEVER ERASE           evolves                           deep dives
```

The left column never gets erased, and you point at it when you justify a decision ("this is the durability requirement, so I can't ack before the fsync"). Interviewers consistently rate "referred back to stated requirements" as a strong signal, and a persistent visible list is what makes that possible under time pressure.

#### Drawing order that keeps the narrative coherent

```
 1. TWO ANCHORS FIRST.   client on the far left, primary datastore on the far right.
                         Everything else grows between them. This prevents the
                         classic "ran out of room on the right" failure.
 2. HAPPY-PATH READ, end to end, in one unbroken line. Complete it before adding
                         anything. A complete narrow path beats a broad half-path.
 3. WRITE PATH, branching off the same entry point, drawn BELOW the read path.
 4. ASYNC PATH, below a visible horizontal line. Everything under that line is
                         off the user's critical path, and the line itself is the
                         claim. Say: "below this line, nothing blocks the user."
 5. NUMBERS ON EDGES, second pass. Do not do this while drawing boxes; you will
                         slow to a crawl. Draw, then annotate.
 6. DEEP DIVE in the right-hand column, in FRESH space. Never draw component
                         detail on top of the container diagram.
```

Say the transition out loud each time: "read path is complete, now the write path", "everything below this line is asynchronous". The narration is what makes an evolving picture followable, and it is why interviewers can tell the difference between a diagram that was designed and one that was recalled.

#### Labelling edges: the grammar

Every edge gets up to four fields. Two are mandatory.

```
        protocol/format  ·  sync|async  ·  payload/size  ·  rate or latency
        ───────────────     ───────────    ─────────────    ────────────────
          MANDATORY          MANDATORY       if it matters    second pass

  client ──HTTPS/JSON · sync · 6 KB · 15k rps──▶ API GW
  API GW ──gRPC · sync · p99 12 ms────────────▶ Query Svc
  Query  ╌╌Kafka · async · ~200 B · 15k msg/s╌▶ Analytics
  Fanout ──Redis pipeline · sync · 100/batch──▶ Redis (250k ZADD/s)
  Region ╌╌async replication · RPO 30 s╌╌╌╌╌╌▶ Standby region
```

Two hard rules:
- **Direction means "initiates", not "data flows".** A read is an arrow from the caller to the datastore even though bytes come back. Pick this convention and state it, because the alternative convention (data direction) is also common and mixing them is unreadable.
- **Solid is synchronous, dashed is asynchronous, and this never changes within a diagram.** Sync edges sum into the latency budget; async edges do not, but they need a durability and retry story. Stating that distinction explicitly is worth a point on its own: "the dashed edges don't count toward my 200 ms, but each one needs at-least-once delivery and an idempotent consumer."

#### How to annotate for scale

Scale annotations are a second pass over a finished diagram, in this order:

```
  1. RATE on the hot edges only.       "15k rps peak" · "250k ins/s"
  2. SIZE on the stateful boxes.       "1.6 TB" · "100M vectors, 132 GB"
  3. REPLICA COUNT as a multiplier.    "×12 (3 AZ)" · "4 shards × 2 replicas"
     NEVER draw 12 identical boxes. Draw one and write ×12.
  4. THE BOTTLENECK, circled or double-boxed, with the number that binds:
         ╔════════════════════╗
         ║ Redis timelines    ║  ← 1.6 TB · MEMORY-BOUND · breaks first at 10x
         ║ ×12 shards         ║
         ╚════════════════════╝
  5. PARTITION KEY on every sharded box.   "part: user_id" · "part: hash(doc_id)"
  6. THE CUT LINE for what you did not draw, written as text, not boxes:
         "not drawn: authn (Okta/OIDC at the gateway), o11y (OTel → Datadog),
          CI/CD, DNS, secrets, per-hop LBs, service mesh sidecars"
```

Point 6 is disproportionately valuable and costs one line. It converts every omission from a gap into a deliberate scoping decision, and it pre-empts "you didn't mention monitoring".

#### What to leave out

| Leave out | Say it once instead | Why |
|---|---|---|
| Auth service box on every edge | "Authn at the gateway via OIDC, authz per-request in the service using tenant claims" | It is on every edge; drawing it 8 times destroys legibility |
| Logging/metrics/tracing boxes | "OTel sidecar, traces to Datadog, RED metrics per service" | It touches everything and is never the design question |
| CI/CD, artifact registry | "Blue-green with a 5% canary and automated rollback on error-rate" | It is a rollout answer, not an architecture answer |
| DNS, TLS termination | Assume it | Nobody scores this |
| Load balancer between every pair of internal services | Draw one at the edge; say "service discovery + client-side LB internally" | Otherwise half your boxes are LBs |
| Individual replicas | "×12" on one box | 12 boxes carry no more information than one and a multiplier |
| Service mesh sidecars | "Envoy sidecars handle mTLS, retries, and outlier detection" | Doubles the box count for zero design content |
| Config/secrets/feature flags | Mention when relevant to a rollout question | |
| Every cache layer at once | Draw the one that carries the hit rate you quoted | A diagram with four caches and no hit rates is a wish list |

The governing principle: **draw what you will be asked a follow-up about, and name everything else.** Anything on the board is an invitation to a question, so drawing infrastructure you cannot discuss in depth is actively harmful.

#### Bad versus good, concretely

```
 BAD                                    GOOD
 ┌───┐   ┌───┐   ┌───┐                  ┌────────────┐ HTTPS/JSON  ┌──────────────┐
 │   │──▶│   │──▶│   │                  │ Web client │ sync 6KB    │ API Gateway  │
 └───┘   └───┘   └───┘                  │ [React SPA]│──15k rps───▶│ [Envoy]      │
   │       │       │                    └────────────┘             │ TLS, JWT,    │
   ▼       ▼       ▼                                               │ 429 limit    │
 ┌───┐   ┌───┐   ┌───┐                                             └──────┬───────┘
 │DB │   │ ? │   │ ? │                                       gRPC sync    │ p99 12ms
 └───┘   └───┘   └───┘                                                    ▼
                                                              ┌────────────────────┐
 - unlabelled boxes                                           │ Feed Read Svc      │
 - unlabelled arrows                                          │ [Go] ×12 (3 AZ)    │
 - no technology                                              │ stateless          │
 - no direction semantics                                     └──────┬─────────────┘
 - can't tell service from store                                     │ Redis proto
 - can't tell sync from async                                        │ sync p99 1ms
 - nothing to ask a question about                                   ▼
                                                             ╔════════════════════╗
                                                             ║ Timeline cache     ║
                                                             ║ [Redis] ×12 shards ║
                                                             ║ part: user_id      ║
                                                             ║ 1.6 TB · 95% hit   ║
                                                             ║ ← BOTTLENECK       ║
                                                             ╚════════════════════╝
```

Every difference on the right is cheap: a name, a bracketed technology, an edge label, a replica count, a partition key, a hit rate, and a marked bottleneck. None of it takes longer than 15 seconds per box, and collectively it is the difference between a diagram the interviewer can interrogate and one they have to decode.

---

## Build it from scratch

### Same system, four diagram types: DocuChat (enterprise document Q&A)

One system, four questions, four pictures. The point of this exercise is that **no single diagram answers more than one of the four questions**, and knowing which to reach for when the interviewer asks is the actual skill.

**The system, in one line:** employees ask natural-language questions over 2M internal documents; the service retrieves relevant chunks, reranks them, and streams an LLM answer with citations. Multi-tenant, ACL-aware, EU data residency for EU tenants.

---

#### Diagram 1 of 4 — C4 Container: "what exists and how do the pieces talk"

Draw this first, always. Answers "what are the pieces". Roughly 8 minutes including labels.

```
 ┌── EDGE ─────────────────────────────────────────────────────────────────┐
 │  ┌────────────┐  HTTPS/SSE · sync · 15k rps pk  ┌──────────────────┐    │
 │  │ Web client │─────────────────────────────────▶│ API Gateway      │   │
 │  │ [React SPA]│◀───── token stream ─────────────│ [Envoy]          │   │
 │  └────────────┘                                  │ TLS · OIDC verify│   │
 │                                                  │ 429 per-tenant   │   │
 │                                                  └────┬────────┬────┘   │
 └───────────────────────────────────────────────────────│────────│────────┘
   ── READ / QUERY PATH ────────────────────────────────│────────│─────────
        gRPC · sync · p99 60ms (excl. LLM)               │        │
                    ┌────────────────────────────────────┘        │
                    ▼                                             │
      ┌──────────────────────────────┐                            │
      │ Query Service                │  Redis · sync · 0.4ms      │
      │ [Python/FastAPI] ×12 (3 AZ)  │───────────────────────┐    │
      │ plan → retrieve → rerank →   │                       ▼    │
      │ assemble → stream            │            ┌──────────────────────┐
      └──┬────────────┬──────────┬───┘            │ Answer cache [Redis] │
         │            │          │                │ key: h(q)+tenant+acl │
  gRPC   │      HTTP  │    HTTPS │                │ TTL 1h · 22% hit     │
  sync   │      sync  │    sync  │                └──────────────────────┘
  12ms   │      35ms  │    420ms │ first token
         ▼            ▼          ▼
 ┌───────────────┐ ┌──────────┐ ┌──────────────────┐
 │ Weaviate      │ │ Reranker │ │ LLM Provider     │
 │ [vector DB]   │ │ [BGE     │ │ [Bedrock/        │
 │ 4 shards ×2   │ │  cross-  │ │  Anthropic]      │
 │ 100M chunks   │ │  encoder]│ │ EXTERNAL         │
 │ int8, 132 GB  │ │ ×6 GPU   │ │ 420ms TTFT       │
 │ part: tenant  │ │ T4       │ │ ← 88% of latency │
 └───────────────┘ └──────────┘ └──────────────────┘
         ▲
   ══════╪════════════ ASYNC — NOTHING BELOW BLOCKS THE USER ══════════════
         │
         │ upsert · async · 29 chunks/s
 ┌───────┴────────┐  ┌──────────────┐  ┌──────────────────┐
 │ Index Worker   │◀─│ Kafka        │◀─│ Crawler          │
 │ [Python] ×8    │  │ [MSK] 3 brk  │  │ [Python] cron 15m│
 │ parse→chunk→   │  │ doc.changed  │  │ incremental by   │
 │ embed (GPU)    │  │ 12 partitions│  │ mtime · 50k/day  │
 └───────┬────────┘  └──────────────┘  └────────┬─────────┘
         │                                       │ HTTPS · sync
         ▼                                       ▼
 ┌────────────────────┐                ┌────────────────────────┐
 │ Postgres [RDS]     │                │ SharePoint/Confluence  │
 │ chunk meta, ACL,   │                │ EXTERNAL               │
 │ doc lineage, audit │                └────────────────────────┘
 │ primary + sync std │
 │ + 2 read replicas  │
 └────────────────────┘

 NOT DRAWN: Okta (OIDC at gateway), OTel→Datadog, CI/CD, DNS, secrets,
            Envoy sidecars, per-tenant config service, S3 raw-doc archive.
```

What this diagram answers: what the pieces are, what technology each is, which edges are sync (they sum to the latency budget) and which are async (they do not), where state lives, what the partition keys are, and what the bottleneck is. What it **cannot** answer: the order things happen in, what the data looks like as it moves, and what it runs on. Hence the next three.

---

#### Diagram 2 of 4 — Sequence: "what happens, in order, for one question"

Draw this when asked to walk through a request, or when the conversation turns to latency. About 4 minutes.

```
 User    Gateway   QuerySvc   AnswerCache  Weaviate  Reranker   LLM    Kafka
  │         │          │            │          │        │        │       │
  │ POST /ask (q, tenant, jwt)      │          │        │        │       │
  ├────────▶│          │            │          │        │        │       │
  │         │ verify JWT locally (JWKS cached 10m) — 0.2ms      │       │
  │         ├─────────▶│            │          │        │        │       │
  │         │          │ GET h(q)+tenant+acl_hash             │       │
  │         │          ├───────────▶│          │        │        │       │
  │         │          │◀─ MISS ────┤ 0.4ms    │        │        │       │
  │         │          │            │          │        │        │       │
  │         │          │ embed(q) local ONNX — 8ms      │        │       │
  │         │          │ ANN top-50, filter: tenant+acl │        │       │
  │         │          ├──────────────────────▶│        │        │       │
  │         │          │◀───── 12ms ───────────┤        │        │       │
  │         │          │ rerank(q, 50 chunks)  │        │        │       │
  │         │          ├───────────────────────────────▶│        │       │
  │         │          │◀────────── 35ms ───────────────┤ top-5  │       │
  │         │          │ assemble prompt (1.5k tok)     │        │       │
  │         │          ├───────────────────────────────────────▶│       │
  │         │          │◀══════ first token 420ms ══════════════┤       │
  │         │◀═════════┤ SSE: begin streaming                   │       │
  │◀════════┤          │                                        │       │
  │         │          │ ... 180 more tokens @ ~40 tok/s ...    │       │
  │◀════════┼══════════┤                                        │       │
  │         │          │ SET answer cache (TTL 1h)              │       │
  │         │          ├───────────▶│                           │       │
  │         │          │ emit query_answered (q, cites, latency)│       │
  │         │          ╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌▶│
  │         │          │                                        │       │
 [ TTFT p99 = 0.2 + 0.4 + 8 + 12 + 35 + 420 ≈ 476 ms                   ]
 [ LLM = 88% of it. Cutting reranker to 10ms saves 5% of perceived time. ]
 [ CACHE HIT PATH = 0.6 ms total. 22% hit rate → 22% of traffic is ~free.]

 FAILURE VARIANT (draw this if there is time — it is worth more than a box):
 User    Gateway   QuerySvc            Weaviate
  │         │          │ ANN search, 50ms timeout    │
  │         │          ├────────────── X timeout ────┤ (breaker opens after
  │         │          │                              │  50% failures / 20 calls)
  │         │          │ fall back: Postgres FTS keyword-only, top-20
  │         │          │ ── answer streams with degraded=true flag ──▶
  │◀════════┼══════════┤ user gets a worse answer, not an error
```

What this answers that the container diagram cannot: the latency budget and its decomposition, which optimisations are pointless, what the cache-hit path costs, where the async boundary actually sits in time, and what degradation looks like.

---

#### Diagram 3 of 4 — Dataflow: "how does a document become a searchable chunk"

Draw this when the conversation moves to ingestion, freshness, or reindexing. About 4 minutes.

```
 SOURCE            EXTRACT              TRANSFORM              LOAD
 ┌───────────┐   ┌──────────────┐   ┌────────────────┐   ┌──────────────────┐
 │SharePoint │   │ Crawler      │   │ Parse          │   │ Chunk            │
 │Confluence │──▶│ incremental  │──▶│ PDF/DOCX/HTML  │──▶│ 512 tok · 64 ovl │──┐
 │2M docs    │   │ by mtime     │   │ →text + struct │   │ heading-aware    │  │
 │           │   │ + ACL fetch  │   │ ~0.5% fail     │   │                  │  │
 └───────────┘   └──────────────┘   └───────┬────────┘   └──────────────────┘  │
   50k new/day    50k docs/day       30 GB/day raw text          │             │
                                            │                    │             │
                                            ▼                2.5M chunks/day   │
                                     ┌─────────────┐               │           │
                                     │ DLQ [S3]    │               │           │
                                     │ + PagerDuty │               │           │
                                     │ if >2%/hr   │               │           │
                                     └─────────────┘               │           │
     ┌──────────────────────────────────────────────────────────────┘           │
     ▼                                                                          │
 ┌────────────────┐        ┌──────────────────────┐                             │
 │ Embed          │        │ Upsert               │                             │
 │ BGE-large 1024d│───────▶│ idempotency key =    │──────┐                      │
 │ batch 256, GPU │        │ (doc_id, chunk_idx,  │      │                      │
 │ 29 chunks/s    │        │  content_hash)       │      │                      │
 │ ← NARROW STAGE │        │ → re-crawl is FREE   │      │                      │
 │ 4 GPU-hr/day   │        └──────────────────────┘      │                      │
 └────────────────┘                                       │                      │
                                                          ├──────────────────────┤
                                                          ▼                      ▼
                                              ┌────────────────────┐  ┌──────────────────┐
                                              │ Weaviate           │  │ Postgres         │
                                              │ vectors + tenant + │  │ chunk text, ACL, │
                                              │ acl_hash filter    │  │ doc lineage,     │
                                              │ 100M chunks        │  │ audit trail      │
                                              └────────────────────┘  └──────────────────┘

 ┌── ACL CHANGE PATH (the one people forget) ────────────────────────────────┐
 │ SharePoint permission change ─▶ Kafka acl.changed ─▶ ACL Sync Worker      │
 │   ─▶ UPDATE acl_hash on affected chunks (no re-embed needed)              │
 │   p99 propagation target: 60s. Until then, a user may see a stale-allowed  │
 │   citation → so the FINAL ACL check happens at read time against Postgres, │
 │   not only via the vector filter. Filter is an optimisation, not the       │
 │   security boundary.                                                       │
 └───────────────────────────────────────────────────────────────────────────┘

 [ back-pressure: 29 chunks/s embed capacity. A 10x doc dump (500k docs)
   = 25M chunks = 10 days of embedding. So bulk onboarding needs a SEPARATE
   burst-capacity path on spot GPUs, not the steady-state pipeline. ]
 [ freshness SLO: doc edited → searchable in p99 < 15 min (crawler interval
   dominates, not the pipeline). Say which stage owns the SLO. ]
```

What this answers that neither of the previous two can: where the throughput ceiling is, what happens on a bulk load, where replay-safety lives, how ACL changes propagate without re-embedding, and what freshness actually means. The ACL box is the highest-value part of this diagram, because it distinguishes an optimisation from a security boundary, and that is a distinction interviewers probe hard on multi-tenant systems.

---

#### Diagram 4 of 4 — Deployment: "what does it run on, and what is the failure domain"

Draw this when the conversation moves to availability, regions, or residency. About 3 minutes.

```
                       ┌── Route 53 · geo + latency routing ──┐
                       │ EU tenants pinned to eu-west-1 (residency)
                       └──────┬──────────────────────┬────────┘
                              │                      │
 ╔══ us-east-1 (primary, US tenants) ══════════╗  ╔══ eu-west-1 (EU tenants, ══╗
 ║ ┌── ALB (cross-AZ, TLS) ─────────────────┐  ║  ║   ALSO US warm standby) ══ ║
 ║ │ ┌─AZ-a───────┐┌─AZ-b───────┐┌─AZ-c───┐│  ║  ║  same topology at 40% size ║
 ║ │ │query-svc ×4││query-svc ×4││qs ×4   ││  ║  ║  SEPARATE Weaviate +       ║
 ║ │ │c7g.2xlarge ││            ││        ││  ║  ║  Postgres — EU data never  ║
 ║ │ │reranker ×2 ││reranker ×2 ││rr ×2   ││  ║  ║  leaves. NOT a replica of  ║
 ║ │ │g5.xlarge   ││            ││        ││  ║  ║  us-east-1 for EU tenants. ║
 ║ │ └────────────┘└────────────┘└────────┘│  ║  ╚════════════════════════════╝
 ║ └────────────────────────────────────────┘  ║       ▲
 ║ ┌── Weaviate StatefulSet ────────────────┐  ║       │ async repl of US data
 ║ │ 4 shards × 2 replicas = 8 pods         │  ║       │ (standby only)
 ║ │ r7g.8xlarge · 256 GB · EBS gp3 1TB     │  ║       │ RPO ≈ 30s
 ║ │ podAntiAffinity: shard replicas MUST   │  ║       │ RTO ≈ 15 min
 ║ │ be in different AZs  ← check this       │  ║       │ (Weaviate rebuilt
 ║ │ snapshot → S3 daily, restore ~40 min   │  ║       │  from S3+PG, not
 ║ └────────────────────────────────────────┘  ║       │  streamed)
 ║ ┌── RDS Postgres ──┐ ┌── MSK ───────────┐   ║       │
 ║ │ primary AZ-a     │ │ 3 brokers, 1/AZ  │   ║───────┘
 ║ │ sync standby AZ-b│ │ RF=3, min.isr=2  │   ║
 ║ │ 2 read replicas  │ └──────────────────┘   ║
 ║ │ PITR 7d          │ ┌── S3 (raw docs) ──┐  ║
 ║ └──────────────────┘ │ versioned, CRR off│  ║
 ║ ┌── ElastiCache Redis ─┐ (per-region!)   │  ║
 ║ │ cluster mode, 3 shd  │ └───────────────┘  ║
 ║ │ 1 replica/shard      │                    ║
 ║ └──────────────────────┘                    ║
 ╚═════════════════════════════════════════════╝

 FAILURE DOMAINS, stated explicitly:
   pod       → k8s reschedules, ~30s, no user impact (12 replicas)
   AZ        → lose 1/3 of query capacity + possibly 1 Weaviate replica/shard.
               Survivable IF anti-affinity is correct. This is the check people miss.
   region    → 15 min RTO, 30 s RPO for US. EU tenants CANNOT fail over to
               us-east-1 (residency), so EU availability is capped by eu-west-1.
               That is a stated business tradeoff, not an oversight.
   LLM provider → circuit breaker + secondary provider; degrade to
               extractive (retrieval-only) answers if both are down.
   Weaviate total loss → rebuild from S3 + Postgres, ~4 hours for 100M chunks.
               So Postgres is the source of truth and Weaviate is a derived index.
               Say that sentence; it is the most important line on this diagram.
```

What this answers that nothing else can: the blast radius of each failure, whether the multi-AZ claim is real (anti-affinity), the residency constraint and its cost in availability, and which store is the source of truth versus a rebuildable derived index.

---

### The choosing rule

| Interviewer says | Draw |
|---|---|
| "Design X" | **C4 container.** Always. This is the default. |
| "Walk me through what happens when a user does X" | **Sequence** |
| "Where does the latency go?" | **Sequence** with per-hop timings |
| "How does data get in / how do you reindex / what about freshness?" | **Dataflow** |
| "What breaks if an AZ goes down / how do you go multi-region?" | **Deployment** |
| "Tell me more about the retriever/matcher/scheduler" | **C4 component** (level 3), in fresh space |
| "Show me the schema" | Not a diagram. Write `CREATE TABLE` and the partition key. |
| "How would you implement the queue?" | Not a diagram. Write code. |

---

## How it's done in production

**Diagrams-as-code is the production answer**, and naming the tools is a cheap signal that you maintain architecture documentation rather than producing it once:

| Tool | What it is | When it is right |
|---|---|---|
| **Mermaid** | Text-to-diagram, rendered natively by GitHub/GitLab/Notion | Default for anything in a repo or a PR. Sequence and flowchart support are good; C4 support is workable but weak. |
| **Structurizr DSL** | Simon Brown's own; one model, many views | The right answer when C4 accuracy matters, because all four levels derive from one model and cannot diverge from each other |
| **D2** | Modern text-to-diagram with good auto-layout | Best-looking output; good for docs sites |
| **PlantUML** | The old workhorse, full UML plus C4 macros | Fine, but heavier toolchain and dated output |
| **Excalidraw / tldraw** | Hand-drawn-feel canvas | Whiteboarding and interviews on a shared canvas |
| **AWS/GCP architecture icons in draw.io** | Icon-heavy deployment diagrams | Deployment diagrams for stakeholders who want to see the logos. Actively bad for interviews: icons carry no semantics. |

**The artefact that actually matters is the ADR**, not the diagram. An architecture decision record states the context, the decision, the alternatives considered, and the consequences, and the diagram is an index into it. Mentioning that you write ADRs and that the diagram lives beside one is a staff-level signal, because it says you know a picture cannot record *why*.

**Drift is the permanent problem.** The C4 model in your wiki describes the system as of the last person who cared. The mitigations, in increasing order of effort: put the diagram in the repo next to the code so it appears in code review; generate the container level from service manifests or Terraform; compare the declared graph against the OpenTelemetry service graph and alert on edges that exist in traffic but not in the model. That last one is where the tooling is heading and is worth naming as a direction.

### What breaks at scale (diagram pathologies)

| Symptom | Cause | Fix |
|---|---|---|
| Interviewer keeps asking "is that a service or a database?" | Uniform boxes, no technology annotation | `[Postgres]`, `[Go svc]`, `[Redis]` in every box; distinct shapes for stores |
| "Which of these calls are on the critical path?" | Sync and async drawn identically | Solid = sync, dashed = async, and an explicit async line |
| Diagram becomes unreadable by minute 30 | No space plan; deep dive drawn on top of the main diagram | Divide the board at minute 0; deep dives go in the right column |
| You run out of room on the right | Started drawing at the left and grew rightward | Place client (far left) and primary datastore (far right) first |
| 30 boxes, no narrative | Drew every component you could think of | 12-15 box cap; group into 3-5 labelled regions; name what you left out |
| Erased the requirements to make room | No reserved region | Left 20% is permanent and never erased |
| "How does this scale?" and the diagram has no numbers | Annotation never happened | Second pass: rate on hot edges, size on stateful boxes, ×N replicas |
| Twelve identical service boxes | Drew replicas instead of annotating | One box, `×12 (3 AZ)` |
| Multi-AZ claim collapses under questioning | Drew AZ boundaries but no anti-affinity or quorum placement | State replica placement per failure domain |
| Sequence diagram with no timings | Drew the call graph, not the budget | Latency on every arrow; sum it; state which hop dominates |
| Pipeline diagram with no failure path | Drew the happy day | DLQ box, failure rate, and the idempotency key |
| Interviewer asks about something you drew and you cannot go deep | Drew infrastructure you do not understand | Only draw what you can defend; name the rest |

---

## Tradeoffs & when NOT to use it

- **Do not draw a C4 context diagram when scope is obvious.** "Design a URL shortener" has no interesting external systems, and 90 seconds on a context diagram is 90 seconds not spent on the key-generation scheme. Draw it only when the prompt is genuinely ambiguous about boundaries, which is roughly one prompt in four.
- **Do not draw a sequence diagram unprompted in a 45-minute round.** It costs 4 to 5 minutes and answers a question that may never be asked. Draw it when the interviewer asks for a walkthrough or when latency becomes the topic, and otherwise narrate the sequence verbally over the container diagram.
- **Never draw C4 level 4.** Class diagrams in an interview are a waste of the medium; if they want that depth they want code.
- **Deployment diagrams are wrong for a logic question.** If the question is about consistency or a data model, drawing AZs and instance types is displacement activity. Match the diagram to the question.
- **Icon-heavy cloud diagrams are worse than boxes in an interview.** An AWS icon looks authoritative and conveys nothing about responsibility, protocol, or scale. Draw a box, name the technology in brackets, and label the edge.
- **The C4 "container" abstraction leaks for some architectures.** Serverless designs where every function is a container produce 40-box diagrams; the practical fix is to group functions by bounded responsibility and treat the group as the container, which is a deviation from strict C4 that you should name if you do it. Similarly, a monolith with internal modules is one container, which makes the container diagram nearly empty and pushes all the value to level 3.
- **Diagrams cannot express "why", and the interviewer is scoring "why".** A beautiful diagram with no narration scores worse than a rough one with a running justification. The picture is a prop for the argument, not the argument.
- **Do not over-invest in neatness.** Straight lines and even spacing are not scored. Legible labels, consistent symbol meaning, and reserved space are. Candidates who redraw boxes to align them are burning their most expensive resource.

---

## Interview questions

### Q1 — What are the four C4 levels, and which one do you draw in an interview?
**Testing:** baseline. Fast points.
**Answer:** Context (the system plus its users and external systems, no internals), Container (separately deployable and runnable things with their technology choices and how they communicate), Component (the major modules inside one container), and Code (classes, effectively dead). The interview wants the **container** level, and selectively the component level for whichever box the interviewer wants to deep-dive. Context is worth 60 seconds only when scope is genuinely contested; level 4 never.
**Follow-up trap:** *"What exactly is a container in C4? Is a Docker container a container?"* Not necessarily, and the naming collision is unfortunate. A C4 container is anything separately deployable and runnable: a service, a single-page app, a mobile app, a database, a queue, an object-store bucket, a Lambda. A Docker container usually maps to one, but a sidecar is not a separate C4 container because it is not separately meaningful, and a database schema running on a shared cluster is one even though it is not containerised at all.

### Q2 — You have a blank whiteboard and 45 minutes. What is the very first mark you make?
**Testing:** whether you have done this under time pressure.
**Answer:** Not a box. I divide the board: roughly 20% on the left for the requirements list, NFR table, and computed numbers, which never gets erased; 55% in the middle for the container diagram; 25% on the right kept empty for deep dives. Then I place two anchors, client at the far left of the middle region and the primary datastore at the far right, so the architecture grows between them and I cannot run out of room. Then the happy-path read.
**Follow-up trap:** *"Why does the requirements column matter enough to give up 20% of the board?"* Because referring back to a stated requirement by name is one of the highest-signal behaviours in the round, and you cannot do it reliably from memory at minute 35 under pressure. It also makes contradictions visible: if I am about to add a synchronous cross-region call and the p99 target is on the board at 200 ms, I catch it myself instead of the interviewer catching it.

### Q3 — How do you label an edge?
**Testing:** whether your diagram is interrogable.
**Answer:** Up to four fields, two mandatory: protocol and format, sync or async, payload size, and rate or latency. So `HTTPS/JSON · sync · 6 KB · 15k rps` or `Kafka · async · 200 B · 15k msg/s`. Solid line for sync, dashed for async, and that convention never changes within a diagram. Direction means "initiates the call", not "data flows", and I state which convention I am using because both are common.
**Follow-up trap:** *"Why does sync versus async on the arrow matter so much?"* Because it determines whether the edge is in the latency budget. Sync edges sum: if my p99 target is 200 ms and I have five sync hops, each has a ~40 ms budget before processing. Async edges contribute nothing to that budget but each one incurs a durability and ordering obligation instead: at-least-once delivery, an idempotent consumer, and a lag metric to alert on. Drawing them identically means the diagram cannot answer either question.

### Q4 — In what order do you draw, and why that order?
**Testing:** narrative coherence, which is what makes an evolving diagram followable.
**Answer:** Two anchors, then the happy-path read end to end without adding anything else, then the write path below it branching from the same entry point, then the async path below a visible horizontal line, then a second pass to annotate with numbers, then deep dives in the reserved right column. The read path goes first because it is usually the latency-critical path and because a complete narrow path is more convincing than a broad incomplete one. The horizontal async line is itself a claim: "nothing below this line blocks the user."
**Follow-up trap:** *"What if the write path is the interesting one, like for an ingestion system?"* Then the order inverts, and the rule generalises to "draw the path that the hard requirement lives on first". For an ingestion or analytics system the write path is the design and the read path may be a single box labelled "BI tool". The invariant is completing one path end to end before starting another, not literally starting with reads.

### Q5 — When do you draw a sequence diagram instead of a box diagram?
**Testing:** whether you match the diagram to the question.
**Answer:** When the question involves order, concurrency, or time. Specifically: "walk me through what happens when a user does X", "where does the latency go", "what happens if that call fails halfway", or anything about a multi-step protocol like a two-phase commit, a saga, or an OAuth exchange. A container diagram physically cannot express order, so if the question is temporal, a box diagram is the wrong tool no matter how good it is.
**Follow-up trap:** *"Give me the case where a sequence diagram is uniquely necessary."* A distributed transaction or saga, because the whole design is the ordering and the compensating actions. "Reserve inventory, charge card, create shipment, and if the shipment fails, refund and release" is unintelligible as boxes and obvious as a sequence with compensations drawn as return arrows. Same for anything with a timeout interacting with a retry, since the interesting part is what state exists at each instant.

### Q6 — Your diagram has 30 boxes. What is wrong and what do you do?
**Testing:** legibility discipline.
**Answer:** It has exceeded what anyone can hold, and the interviewer will start spending questions on comprehension rather than design. Three fixes, in order: delete the infrastructure that touches everything (auth, logging, tracing, CI/CD, DNS, per-hop load balancers, sidecars) and name it in a text line instead; collapse replicas into a multiplier so 12 boxes become one box and `×12`; and group the survivors into 3 to 5 labelled regions (edge, read path, write path, async, storage) so the reader chunks the diagram instead of scanning it. Target 12 to 15 boxes.
**Follow-up trap:** *"Doesn't removing the auth service make your design look incomplete?"* Only if I remove it silently. I write a "not drawn" line listing every omission, which converts each from a gap into a scoping decision and pre-empts "you didn't mention monitoring". Everything I draw is an invitation to a follow-up, so drawing a component I cannot discuss in depth is worse than naming it.

### Q7 — How do you show scale on a diagram?
**Testing:** whether numbers reach the picture or stay in your head.
**Answer:** As a second pass, in a fixed order: rate on the hot edges only, size on the stateful boxes, replica count as a multiplier with the failure-domain spread (`×12 (3 AZ)`), the partition key on every sharded store, and the bottleneck double-boxed with the number that binds it. Then a text line for what is not drawn. Doing it as a second pass matters, because annotating while drawing slows you to a crawl and you will not finish the path.
**Follow-up trap:** *"Which single annotation would you keep if you could only have one?"* The bottleneck marker with its binding constraint, for example "Redis timelines, 1.6 TB, memory-bound, breaks first at 10×". It answers the scaling question before it is asked, it demonstrates you ranked the components rather than listing them, and it sets up the whole scale discussion. Second choice is the partition key on each sharded store, because it is what makes the access pattern checkable.

### Q8 — What do you deliberately leave out, and how do you avoid looking like you forgot?
**Testing:** scope control.
**Answer:** Authn/authz as boxes (it touches every edge, so I say "OIDC at the gateway, per-request tenant authz in the service" once), observability, CI/CD, DNS and TLS, secrets and config, internal load balancers, service mesh sidecars, and individual replicas. I avoid looking forgetful by writing an explicit "not drawn" line in a corner listing them. That line costs one line of board space and converts every omission into a deliberate decision. If the interviewer wants any of them they will pull on it, and then I have the full 3 minutes for that thread instead of a box I drew in passing.
**Follow-up trap:** *"So you'd never draw the auth service?"* I would if authentication *is* the design: a question about SSO, token exchange, delegated authorisation, or a multi-tenant permission model makes auth the subject rather than the plumbing, and then it gets a container diagram of its own plus a sequence diagram for the token flow. The rule is that infrastructure touching every edge gets named, and whatever the question is actually about gets drawn.

### Q9 — Same system, four diagram types. What does each answer that the others cannot?
**Testing:** whether the four types are distinct tools or interchangeable pictures.
**Answer:** C4 container answers what the pieces are, what technology each uses, where state lives, and which edges are sync versus async. Sequence answers ordering, the decomposition of the latency budget, and what the failure and degradation paths look like in time. Dataflow answers where the throughput ceiling is, what happens on a burst, how data is transformed, and where replay-safety and idempotency live. Deployment answers the blast radius of each failure domain, whether the multi-AZ claim is real, residency constraints, and which store is the source of truth versus a rebuildable derived index. None of the four can answer another's question, which is why "one big diagram" always fails.
**Follow-up trap:** *"If you only get one, which?"* Container, because it is the only one that establishes shared vocabulary, and every other conversation refers to its boxes. But I would rather have container plus a *verbal* sequence walkthrough than container plus a drawn sequence diagram, because the narration gets the same information across in a third of the time and leaves the board clear.

### Q10 — What is wrong with a diagram full of AWS service icons?
**Testing:** whether you know that notation should carry meaning.
**Answer:** Icons encode the vendor's product name and nothing else. They do not say what the component is responsible for, what protocol the edge uses, whether the call is synchronous, what the throughput is, or what the partition key is, and they create a false impression of rigour because they look official. They also bias the design toward whatever has an icon: candidates draw an SQS icon and a Lambda icon because those exist, rather than deriving that they need a queue. A labelled box with a bracketed technology and a labelled edge carries strictly more information in the same space.
**Follow-up trap:** *"When are icon diagrams the right choice?"* Deployment diagrams for a non-engineering audience, or a cloud architecture review where the point is procurement and the specific managed services are the content. In those contexts the icon *is* the semantic. In an interview it is decoration that competes with your labels for space.

### Q11 — Your dataflow diagram has five stages and arrows between them. What is missing?
**Testing:** whether a pipeline diagram is a design or a box chain.
**Answer:** Five things. Volume on every edge, so the narrow stage becomes visible rather than argued about. The narrow stage explicitly marked, with what happens on a burst (queue, shed, or drop). The dead-letter path and its expected failure rate, because a pipeline without an error path is a diagram of the happy day. The idempotency key, because pipelines get replayed and where dedup happens is the most important detail in the picture. And the freshness SLO with the stage that owns it, which is usually the crawler interval rather than anything in the pipeline.
**Follow-up trap:** *"Where does back-pressure actually come from in your diagram?"* From the narrowest stage propagating upstream, which only works if every stage between it and the source is pull-based or bounded. If the crawler pushes into an unbounded queue, there is no back-pressure at all, just an unbounded lag that eventually becomes an out-of-disk incident. So the honest annotation is either a bounded queue with a shed policy, or a lag metric with an alert and a documented decision to let it grow, and saying which is a real design statement.

### Q12 — You drew AZ boundaries. How do I know your multi-AZ claim is real?
**Testing:** whether deployment diagrams are decorative.
**Answer:** By the replica placement, not the boundary lines. Stateless services are easy: 12 replicas spread across 3 AZs by topology spread constraints, and losing one AZ costs a third of capacity. Stateful is where the claim usually fails: a StatefulSet with 4 shards and 2 replicas each needs pod anti-affinity guaranteeing that a shard's two replicas land in different AZs, otherwise you have 8 pods across 3 AZs with some shard having both replicas in the same one, and losing that AZ loses the shard. For quorum systems I would also state the quorum arithmetic per AZ, because 3 replicas across 2 AZs cannot survive losing the AZ holding two of them.
**Follow-up trap:** *"You lose an AZ and you're at two-thirds capacity. Is that fine?"* Only if I provisioned for it, and most people do not. If I sized 12 replicas for peak at 60% utilisation, then 8 replicas is 90% utilisation, which is past the knee of the latency curve, so p99 roughly triples during the exact incident when I least want that. The honest design provisions 1.5× so that N-1 AZ capacity still sits at the target utilisation, and that cost should be stated rather than discovered.

### Q13 — The interviewer says "tell me more about the reranker". What do you draw and where?
**Testing:** deep-dive hygiene.
**Answer:** A C4 component diagram, 5 to 8 boxes, in the reserved right-hand column, in fresh space. Never on top of or inside the container box, because the container diagram is the shared reference for the rest of the conversation and destroying it costs more than the deep dive gains. I would also draw an arrow or write the container name so it is unambiguous which box I zoomed into, and I would keep the container diagram's own annotations intact so we can come back to it.
**Follow-up trap:** *"You've run out of space in the right column."* Then erase the deep dive, not the main diagram or the requirements, and say so: "I'm clearing this to zoom into the next component; the container diagram and requirements stay." Deep dives are transient by design, which is exactly why they get their own region. If I have genuinely filled the board, the requirements column is the last thing to go, and by that point I should have said the numbers out loud enough times that they are in the interviewer's notes anyway.

### Q14 — The round is on a shared text editor, not a whiteboard. What changes?
**Testing:** 2026 medium awareness.
**Answer:** The structure gets easier and the excuses get fewer. I would ask at the start which medium we are using, then in a text editor I write the requirements and NFR table as a literal list, the API as actual signatures, the schema as `CREATE TABLE` statements, and the architecture as an ASCII box diagram or a Mermaid graph. Text raises the bar in a way that favours prepared candidates: nobody can hand-wave a schema when the medium wants exact column names. The one thing that gets harder is spatial layout, so I compensate with explicit section headers and a reserved block at the top for the requirements rather than a left column.
**Follow-up trap:** *"Isn't ASCII slower than drawing?"* For boxes, marginally. For everything else it is much faster, and it is a net win because the artefacts that score highest (API signatures, schema, edge labels, numbers) are text anyway. The practical trick is a small fixed vocabulary of ASCII forms you can type without thinking: a box, an arrow with a label, a dashed arrow, and a sequence-diagram skeleton. Practising those four is worth more than practising neat rectangles.

### Q15 — Two candidates draw the same boxes. One diagram scores well and one does not. Why?
**Testing:** whether you have internalised what the diagram is for.
**Answer:** Labels and annotation, which together determine whether the interviewer can interrogate the design. The scoring diagram has a technology in every box, a protocol and sync/async on every edge, a rate on the hot edges, a size and partition key on the stateful boxes, replica counts as multipliers, a marked bottleneck, and a "not drawn" line. The other has boxes and arrows. Given the second, the interviewer must spend their questions on comprehension; given the first, they can point at an edge and ask "what's the p99 there and what happens if it fails", which is the conversation that produces a hire signal.
**Follow-up trap:** *"So it's just labelling?"* No, and this is the important part: the labels are a forcing function, not decoration. You cannot write `sync · p99 12 ms` on an edge without having decided the consistency and latency properties of that hop, and you cannot write a partition key without having decided the access pattern. Candidates who label discover their own gaps while drawing, at minute 25, instead of having the interviewer discover them at minute 40. The labelling is where the thinking happens.

### Q16 — How do you keep a diagram accurate over two years in production?
**Testing:** whether you have maintained architecture documentation or only produced it.
**Answer:** You do not, by hand. Three mechanisms, in increasing effort: put the diagram in the repo as Mermaid or Structurizr DSL so it appears in code review and a reviewer can notice it is stale; generate the container level from the actual deployment descriptors or Terraform so it derives from truth rather than memory; and compare the declared container graph against the OpenTelemetry service graph, alerting on edges present in traffic but absent from the model. And the diagram is never the primary artefact anyway; the ADR is, because a picture cannot record why an alternative was rejected.
**Follow-up trap:** *"Which of those would you actually do?"* Diagrams-as-code in the repo, always, because it is nearly free and it puts staleness in front of a reviewer. Generation from Terraform I would do only for the deployment view, where the mapping is mechanical. Drift detection against traces I would not build myself; I would wait for the tooling, because a homegrown version produces false positives on every health check and background job and the alert gets muted within a month. Naming what you would *not* build is part of the answer.

---

## Red flags that fail you

- Unlabelled boxes, or unlabelled arrows.
- Solid and dashed lines used inconsistently, or sync and async drawn identically.
- Mixing abstraction levels: a database box next to a "retry decorator" box.
- Drawing before dividing the board, then running out of room on the right.
- Erasing the requirements list to make space.
- Drawing the component-level deep dive on top of the container diagram.
- Thirty boxes, or twelve identical replica boxes instead of `×12`.
- No numbers anywhere on a diagram after you computed them five minutes earlier.
- No partition key on a sharded datastore.
- AZ boundaries drawn with no statement about replica placement or anti-affinity.
- A pipeline diagram with no dead-letter path and no idempotency key.
- A sequence diagram with no latencies on the arrows.
- Cloud vendor icons in place of labels and responsibilities.
- Drawing infrastructure you cannot discuss in depth when asked.
- Redrawing boxes to make them align.
- Silence while drawing. The picture is a prop for the argument, not the argument.

## Cheat card

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

## Sources

- [C4 model — home](https://c4model.com/) — accessed 2026-07-26
- [C4 model — Container diagram](https://c4model.com/diagrams/container) — accessed 2026-07-26
- [What Is the C4 Model for Visualizing Software Architecture? — Baeldung](https://www.baeldung.com/cs/c4-model-abstraction-levels) — accessed 2026-07-26
- [The C4 Model for Software Architecture — InfoQ](https://www.infoq.com/articles/C4-architecture-model/) — accessed 2026-07-26
- [How to Whiteboard for System Design Interviews — Exponent](https://www.tryexponent.com/blog/how-to-whiteboard-for-system-design-interviews) — accessed 2026-07-26
- [Mastering the Whiteboard: A Step-by-Step Guide to System Design Diagrams — DesignGurus](https://designgurus.substack.com/p/mastering-the-whiteboard-a-step-by) — accessed 2026-07-26
- [The One Diagram You Should Always Draw in a System Design Interview — DesignGurus](https://designgurus.substack.com/p/the-one-diagram-you-should-always) — accessed 2026-07-26
- [How to Draw System Design Diagrams in Interviews — System Design Handbook](https://www.systemdesignhandbook.com/blog/system-design-diagrams/) — accessed 2026-07-26
- [How to Whiteboard for System Design Interviews — GeeksforGeeks](https://www.geeksforgeeks.org/system-design/how-to-whiteboard-for-system-design-interviews/) — accessed 2026-07-26
- [Doing proper C4 diagrams is easy — Eugene Pavliy, Medium](https://medium.com/@epavliy/doing-proper-c4-diagrams-is-easy-8cca06fdaea6) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
