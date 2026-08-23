# LangGraph II: Checkpointers, interrupt()/HITL, Durable Resume

> Sprint weekend 2 · source: `curriculum/07-agentic-ai/07-langgraph-durable.md`

```
WHY AT ALL — reliability is MULTIPLICATIVE
  0.95^10 ≈ 60%   0.85^10 ≈ 20%   0.95^50 ≈ 8%   0.85^20 ≈ 4%
  0.85^10 ≈ 20% → 4 of 5 runs fail somewhere; un-checkpointed retry pays for
  the WHOLE trajectory again (~5x expected cost per success)
  retry raises p · checkpointing makes failure CHEAP · they are complements

INTERFACE  BaseCheckpointSaver: .put .put_writes .get_tuple .list
                        async:  .aput .aput_writes .aget_tuple .alist
  put_writes = per-TASK writes inside a super-step → PENDING WRITES:
    sibling node that succeeded in a failed tick does NOT re-run

IMPLEMENTATIONS
  InMemorySaver     bundled       dict on the heap. dies on deploy/evict/OOM/2nd replica
  SqliteSaver       -sqlite pkg   file; single writer; dev + single-node only
  PostgresSaver     -postgres pkg PRODUCTION (+ AsyncPostgresSaver for ainvoke)
  ShallowPostgres   -postgres pkg latest checkpoint only → NO time travel / fork
  CosmosDBSaver     langchain-azure-cosmosdb

KEYS  config={"configurable":{"thread_id": ..., ["checkpoint_id": ...]}}   REQUIRED
  thread_id = durable cursor. business id, not per-request UUID. PII + tenancy surface.
  checkpoint_ns: "" root · "node:uuid" subgraph · nested joined by "|"
  renaming a node changes the ns → breaks INTERRUPTED threads

StateSnapshot  values · next (()=done) · config · created_at · parent_config
  metadata{source: input|loop|update, writes, step} · tasks[PregelTask: id,name,error,interrupts]
  START→A→B→END produces FOUR checkpoints (steps -1, 0, 1, 2)

TIME TRAVEL
  get_state / get_state_history (REVERSE chronological)
  REPLAY  invoke(None, snap.config)   → nodes after re-EXECUTE (LLM+API+interrupts fire again)
  FORK    update_state(snap.config, values) → NEW checkpoint, original history intact
          values pass through REDUCERS (add accumulates!) → use Overwrite to replace
          as_node= when parallel writes / no history / to skip a node

interrupt()  raises GraphBubbleUp · needs checkpointer + thread_id · JSON-serialisable
  read: v1 result["__interrupt__"] · v2 result.interrupts · v3 stream.interrupts/.interrupted
  resume: Command(resume=v) — the ONLY Command valid as INPUT
  parallel interrupts → Command(resume={interrupt.id: answer, ...})
  ★ NODE RE-RUNS FROM ITS FIRST LINE ON EVERY RESUME ★
  1 no bare try/except (swallows the pause)   2 never skip/reorder (INDEX-matched)
  3 JSON-serialisable only                    4 pre-interrupt side effects IDEMPOTENT
  static interrupt_before/after = DEBUG breakpoints, resume with invoke(None, cfg)

SIDE EFFECTS ON RESUME
  sibling completed in failed tick → safe (pending writes)
  node failed mid-way / interrupt  → everything before it RE-RUNS
  fix order: (1) side effect AFTER interrupt or in its OWN node
             (2) naturally idempotent (upsert > insert)
             (3) idempotency key = f"{thread_id}:{checkpoint_id}:{op}", TTL > approval window
             (4) @task (retrieved on replay) — still NOT exactly-once
  LangGraph = AT-LEAST-ONCE. Exactly-once is the downstream system's property.

DURABILITY  exit (on exit only; no crash recovery) · async (default choice) · sync (safest)
GRACEFUL SHUTDOWN (>=1.2 alpha)  RunControl().request_drain(); catch GraphDrained;
  resume invoke(None, cfg). Cooperative: BETWEEN supersteps; does NOT cancel tasks.

POSTGRES  ConnectionPool(kwargs={"autocommit": True, "row_factory": dict_row})
  autocommit → .setup() persists DDL · dict_row → else TypeError: tuple indices...
  .setup() ONCE in a migration job → checkpoints, checkpoint_blobs, checkpoint_writes,
                                     checkpoint_migrations
  serde=EncryptedSerializer.from_pycryptodome_aes()  (LANGGRAPH_AES_KEY) — plaintext otherwise
  LANGGRAPH_STRICT_MSGPACK=true — restrict deserialisation
  NOTHING prunes checkpoints. Own a retention job.

MIGRATIONS  completed threads: any topology change · interrupted threads: NOT rename/remove
  state keys: add/remove safe · RENAME LOSES SAVED STATE · type change may break

WHEN NOT TO USE  stateless single-shot call · synchronous confirmation (no durable pause needed)
  exactly-once / cross-service compensation → Temporal / Restate (LLM calls as activities)
```
