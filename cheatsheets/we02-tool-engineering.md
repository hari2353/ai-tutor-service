# Tool Engineering: Schemas, Errors, Idempotency, Sandboxing

> Sprint weekend 2 · source: `curriculum/07-agentic-ai/03-tool-engineering.md`

```
CORE ASYMMETRY  traditional client: cheap memory, perfect recall
                model: PAID context, no memory, re-reads your description every turn
  ⇒ your REST API is NOT your tool surface. 1:1 wrapping is THE default mistake.

CONSOLIDATE (task, not endpoint)
  list_users+list_events+create_event → schedule_event
  read_logs                          → search_logs (matches + context)
  get_customer_by_id+txns+notes      → get_customer_context
  test: can you name the HUMAN task? list_contacts fails. search_contacts passes.

NAME  verb_noun · namespace by service THEN resource (asana_projects_search)
  prefix vs suffix namespacing has NON-TRIVIAL eval effects — measure, don't guess
  top failures = WRONG TOOL + WRONG PARAMS (notification-send-user vs -channel)

DESCRIPTION = PROMPT (not docs)
  what it's for · WHEN NOT TO USE IT · query grammar · vocabulary · return shape
  "prefer several narrow searches" · "empty result is NOT an error"
  evidence: description-only refinements → SOTA on SWE-bench Verified
            web search tool was appending "2025" until the description was fixed

PARAMS  user_id > user · Literal[...] > str · flat > nested · document formats + example
  max_results with a default · response_format: concise|detailed (206 → 72 tokens ≈ 1/3)
  SEMANTIC ids > UUIDs (measurably fewer hallucinations); expose ids only in "detailed"
  input_examples 1-5, realistic, full/partial/minimal → 72% → 90% on complex params

TRUNCATE AT THE TOOL (highest-leverage single fix)
  pagination + range + filter + truncate, all with sensible defaults
  Claude Code default cap: 25,000 tokens per tool response
  truncation message MUST STEER: counts + WHICH PARAM TO NARROW
  drop low-signal fields (uuid, mime_type, etag, _links, 256px_image_url)
  response shape (XML/JSON/MD) measurably matters — choose by eval

ERRORS = OBSERVATIONS, never exceptions into the loop
  unknown tool → did-you-mean + list · validation → compact msg + schema + example
  429 → retry_after + "do something else first" · 404 → "verify id via search_x"
  403 → "do NOT retry; tell the user what approval is needed"
  dependency failed → return to model.  YOUR bug (KeyError) → log + fail loudly.
  "no results" is SUCCESS, not an error (else infinite identical retries)

IDEMPOTENCY  HARNESS supplies the key, never the model (model regenerates on retry)
  f"{thread_id}:{checkpoint_id}:{tool}"  /  f"{run_id}:{step}:{tool}:{hash(args)}"
  server: INSERT ... ON CONFLICT DO NOTHING + check rowcount (read-then-write RACES)
  TTL > max retry window (days, if a human approval gate)
  prefer naturally idempotent: upsert > insert, set_status > close, PUT > POST

RISK TIERS (enforce in the DISPATCHER, not the prompt)
  read_only · write_reversible · write_external · financial · destructive
  RISK.get(name, "destructive")  ← unknown = MOST DANGEROUS. fail closed.
  MCP annotations (spec rev 2025-03-26), defaults are PESSIMISTIC:
    readOnlyHint=false · destructiveHint=TRUE · idempotentHint=false · openWorldHint=TRUE
  they are SELF-ASSERTED HINTS. NOT enforcement. never your security boundary.
  auth as the USER, not the service (confused deputy + prompt injection)

SANDBOX untrusted code
  in-process exec  → never       container (shared kernel) → INSUFFICIENT
  gVisor (Modal)   → acceptable  microVM Firecracker/Kata  → PRODUCTION ANSWER
  Firecracker ~125ms boot · <5 MiB/VM · up to 150 VMs/sec/host
  E2B ~150ms · Daytona ~90ms → the latency excuse is gone
  + NO creds/metadata inside · EGRESS DENIED by default · cpu/mem/wall/disk/proc caps
  + read-only root + tmpfs · non-root + seccomp · LOG THE CODE
  isolation without egress control = exfiltration channel

SCALING WALL  degradation starts ~10-15 tools; 20+ clearly worse than 5-8
  BFCL: 43% → 2% as tools went 4 → 51
  RAG-MCP (arXiv 2505.03275): 13.62% → 43.13% selection, >50% fewer prompt tokens
  context cost: 58 tools / 5 MCP servers ≈ 55K tokens BEFORE turn 1 (Jira alone ≈17K)
                Anthropic measured 134K tokens of tool defs pre-optimisation
  FIXES, cheapest first:
    1 DELETE (instrument selection frequency)   2 consolidate   3 fix names+descriptions
    4 namespace   5 gate by state/permission    6 tool search / RAG over tools
    7 subagents with scoped tool sets  ← SECOND resort, not first
  Tool Search: defer_loading:true + search tool · ~500 tok upfront vs ~72K
    total ~8.7K vs ~77K = 85% cut · Opus 4 49%→74% · Opus 4.5 79.5%→88.1%
    does NOT break prompt caching · use when >10K tok defs / 10+ tools / selection issues
  Programmatic Tool Calling: 43,588 → 27,297 tok (37%) · 200KB → 1KB in-example
    knowledge retrieval 25.6%→28.5% · GAIA 46.5%→51.2% · code-as-MCP 150K → 2K (~98.7%)
    COST: arbitrary code execution is now in your control flow → see SANDBOX

TESTING  L1 unit (no LLM): happy/empty/404/429/403 + truncation msg is ACTIONABLE
             + property test: same idem key ⇒ 1 side effect, identical response
         L2 contract in CI (no LLM): desc length, per-param descs, enums, examples
             validate, names unique + not confusable, every mutating tool has tier + key
         L3 evals (LLM): realistic MULTI-STEP tasks that don't name the tool
             metrics: accuracy + #calls + tokens + latency + error rate + WHICH tools
             HELD-OUT set or you're overfitting descriptions to fixtures
             read raw transcripts — what agents OMIT beats what they say
```
