# Recursive Language Models: External Context, Programmatic Inspection, Recursive Calls

> **Track:** T07 Agentic AI · **Time:** 2.5h · **Prereqs:** 11-context-engineering, 12-multi-agent-topologies, 26-loop-engineering · **Updated:** 2026-09-20
> **Module id:** `T07-recursive-language-models` · **Tags:** agents, context, critical
> **Lab:** `labs/py/32-recursive-language-models/`

## The 30-second version

Recursive Language Models (RLMs) treat a long prompt as data in an external environment rather than placing the entire prompt in the model's context window. The model can inspect slices, search or grep, partition the data, and recursively call itself on selected snippets before aggregating structured results. This attacks context rot by replacing one flat attention problem with selective computation, but it adds orchestration cost, partial-failure modes, and a potentially explosive call tree. Use it when programmatic exploration and context dilution are the bottleneck, not as a blanket replacement for retrieval, compaction, or ordinary long-context inference.

## Why this gets asked

Most candidates answer long-context questions with a larger window, more compaction, or a vector database. The interviewer is testing whether you see a fourth option: keep the data outside the model and let code decide what enters each call. They also want the production answer, not the paper diagram: how do you bound recursive fan-out, preserve evidence, handle child failure, prevent untrusted documents from acquiring tools, and prove that extra calls improved the system rather than merely increasing the bill?

---

## Lineage: past → present → future

**What came before.** The first response to long inputs was to increase the context window and send the whole document or conversation in one request. That removed hard truncation, but not the quality problem: attention is not equally effective over every position, distractors accumulate, and the model can lose recall or synthesis ability while the input remains technically within the limit. Retrieval and summarization reduced tokens, but retrieval can miss the needed slice and compaction can destroy details before the question is known. Code-execution scaffolds improved exact filtering, yet typically treated child calls as ad hoc tools rather than a general recursive inference model.

**Where it stands now.** The RLM paper (submitted December 2025, revised May 2026) formalizes the pattern: long prompts live in an external environment, and the model programmatically examines, decomposes, and recursively calls itself over snippets. The paper reports processing inputs up to two orders of magnitude beyond model context windows and, across four long-context tasks, median gains of 26% over compaction, 130% over CodeAct with subcalls, and 13% over Claude Code in its evaluated setup, with comparable cost. Those are research results, not a production SLA. The live engineering question is where RLM belongs relative to RAG, agent loops, and model-native long context: RLM offers exact programmatic exploration, while RAG offers reusable indexing and caching, and a large window offers the simplest global view.

**Where it's heading.** High confidence: external context managers with bounded inspection, structured subcalls, and traceable evidence will appear as a reusable pattern in long-document and codebase agents. Medium confidence: models will be post-trained to plan exploration and choose decomposition strategies, reducing wasted child calls. Speculative: RLM-style environments become a universal replacement for large context windows; global reasoning, simple short prompts, and highly cached corpora can still favor direct inference or retrieval.

## Mental model

An ordinary call carries the whole library into the reader's head. An RLM gives the reader a catalog, search, and a desk where it can open only the books needed for the question.

```text
ordinary:
  question + [entire 200-page document] -> one model call -> answer

RLM:
  question -> model controller
                  |
                  +-- peek / schema inspect
                  +-- grep / exact filter
                  +-- partition into slices
                  +-- child call(slice 1) --+
                  +-- child call(slice 2) --+--> typed reducer -> answer
                  +-- child call(slice N) --+
```

The controller never needs to hold every byte in its context. It holds the search plan, selected evidence, child results, and the budget state.

## How it actually works

### 1. Externalize the prompt

Store the long input in a read-only environment with stable IDs and offsets. The environment can be a Python object, a database, object storage with range reads, a code repository, or a ticket collection. It is not automatically a vector database; exact search and structure-aware traversal are first-class operations.

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class Slice:
    source_id: str
    start: int
    end: int
    text: str

class ContextStore:
    def __init__(self, documents: dict[str, str]):
        self._documents = documents

    def peek(self, source_id: str, start: int = 0, end: int = 2_000) -> Slice:
        text = self._documents[source_id][start:end]
        return Slice(source_id, start, start + len(text), text)

    def grep(self, term: str, limit: int = 100) -> list[Slice]:
        hits = []
        for source_id, text in self._documents.items():
            offset = 0
            while len(hits) < limit:
                pos = text.lower().find(term.lower(), offset)
                if pos < 0:
                    break
                hits.append(self.peek(source_id, max(0, pos - 500), pos + 1_500))
                offset = pos + len(term)
        return hits
```

The important design choice is that `peek` and `grep` return bounded, provenance-carrying slices. An unbounded `read_all()` method simply recreates the original failure mode.

### 2. Explore before invoking the model repeatedly

The controller should inspect structure and filter cheaply before spending child-call tokens. For 5,000 support tickets, it might identify the schema, grep target user IDs, partition by ticket, and invoke classification only on matching rows. This is different from sending all 5,000 tickets to a model and asking it to count.

The useful split is:

```text
cheap deterministic work: parse, grep, filter, count candidates, partition
model work: interpret ambiguous slices, classify, summarize, reconcile
```

If the question is exact and structured, code may solve it entirely. If the question needs semantic judgment, child calls operate on the smallest slice that contains enough evidence.

### 3. Recursive calls are a tree, not free parallelism

Let `b` be average child fan-out and `d` be recursion depth. A naive tree can create approximately:

```text
calls = 1 + b + b^2 + ... + b^d = (b^(d+1) - 1) / (b - 1)
```

With `b=10` and `d=3`, that is 1,111 calls before retries. A production controller therefore enforces multiple budgets:

- maximum depth, often 2-4 for an interactive task;
- maximum child calls and concurrent children;
- maximum input, output, and total model tokens;
- wall-clock deadline and per-child timeout;
- maximum result bytes retained in the parent;
- cost ceiling and cancellation propagation.

The depth number is not a universal default. It is a starting constraint to load-test against the task distribution. The invariant is more important than the value: a child cannot create unbounded work merely because the model keeps asking for another split.

### 4. Aggregate typed evidence

Child calls should return a schema, not arbitrary essays:

```python
# untested sketch
from dataclasses import dataclass

@dataclass(frozen=True)
class ChildResult:
    slice_id: str
    claims: list[str]
    evidence_offsets: list[tuple[int, int]]
    status: str              # ok | no_answer | timeout | error
    input_tokens: int
    output_tokens: int

def reduce_results(results: list[ChildResult]) -> dict:
    failures = [r for r in results if r.status not in {"ok", "no_answer"}]
    claims = [claim for r in results if r.status == "ok" for claim in r.claims]
    return {
        "claims": deduplicate_equivalent_claims(claims),
        "evidence": [r.evidence_offsets for r in results if r.status == "ok"],
        "partial": bool(failures),
        "failed_slices": [r.slice_id for r in failures],
    }
```

The parent must not treat a timeout as a negative answer. A missing child result is missing evidence. The final answer should expose partial status or retry according to policy.

### 5. Context, code, and security boundaries

The external environment is a capability surface. If it can execute Python, access the network, or read arbitrary files, the RLM is an agent with a new name. Keep document content marked as untrusted data. Expose read-only context operations by default, validate arguments outside the model, sandbox code where execution is required, deny arbitrary egress, and audit every slice and child call. The RLM pattern reduces context pressure; it does not solve prompt injection, data exfiltration, or authorization.

## Build it from scratch

Build a small controller over a list of support tickets. The lab should provide a fake model adapter and injectable clock, then test:

1. exact grep narrows 5,000 tickets to the target IDs;
2. only matching slices reach child calls;
3. child results carry slice IDs and evidence offsets;
4. one child timeout produces a partial result, not a false negative;
5. depth, call, token, wall-time, and cost budgets stop recursion;
6. a malicious ticket cannot call filesystem or network tools;
7. the reducer deduplicates claims and preserves conflicting evidence.

```python
# untested sketch
def answer(question, store, model, budget):
    root = model.plan(question, tools=["peek", "grep", "partition"])
    candidates = store.grep(root.search_term, limit=budget.max_slices)
    results = []
    for chunk in candidates:
        if budget.calls_remaining <= 0:
            break
        budget.charge_call()
        results.append(model.solve_slice(question, chunk))
    reduced = reduce_results(results)
    if reduced["partial"] and budget.can_retry():
        reduced["retry"] = True
    return model.synthesize(question, reduced)
```

The sketch intentionally leaves scheduling and model calls abstract. The lab's value is the tests around the controller: bounded work, evidence preservation, and failure semantics.

## How it's done in production

For long documents, use a store that supports range reads and stable versioned identifiers. For code, preserve file paths and line ranges. For structured data, push filtering and aggregation into the database before invoking the model. Run child calls with a bounded worker pool, propagate a deadline, and persist a trace tree. Cache deterministic search results and safe child outputs, but key caches by source version, query, model, and policy version so a new corpus does not reuse stale evidence.

| Symptom | Cause | Fix |
|---|---|---|
| Cost grows exponentially with document size | Recursive fan-out is unconstrained or every chunk is sent to a child | Filter/grep before model calls; cap depth, fan-out, tokens, concurrency, and cost |
| Answer says "no tickets match" after a child timeout | Timeout was treated as a negative result | Return typed partial failure; retry or mark the answer incomplete |
| RLM returns a plausible answer with no supporting location | Child schema omitted provenance or reducer dropped offsets | Require source/version/range evidence in every successful child result |
| Latency p99 equals the outer deadline | One slow child blocks aggregation or cancellation does not propagate | Parallelize bounded children, use per-child deadlines, and cancel outstanding work |
| A document tells the RLM to run a shell command | External environment exposed authority-bearing tools to untrusted content | Read-only capability surface, sandbox, egress deny, and policy checks below the model |
| RLM is worse than baseline on simple questions | Orchestration overhead exceeds context-rot benefit | Route short/simple inputs to direct or cached paths; gate RLM by task and length |
| Repeated runs disagree after corpus updates | Cache key ignores source version or child sampling is uncontrolled | Version the context, prompt, model, policy, and cache entries; use deterministic settings where possible |

## Tradeoffs & when NOT to use it

- **Do not use RLM for every prompt.** A short request over a small context does not justify a controller, extra calls, and a trace tree. Route by input size, task type, and measured context-rot risk.
- **Do not replace a reusable retrieval index with recursive scanning by default.** If the corpus is stable and queries repeat, ANN/lexical retrieval and caching can be cheaper and faster. RLM earns complexity when exploration is dynamic or exact programmatic inspection matters.
- **Do not expose arbitrary code execution merely because the paper uses a REPL.** A read-only structured environment is enough for many tasks. If code is necessary, sandbox it with no credentials and restricted egress.
- **Do not hide partial failure behind a fluent synthesis.** A parent that receives only 80% of children must know that 20% is missing. Surface uncertainty or retry; never convert timeout into "nothing found."
- **Do not compare RLM with a baseline using different token accounting.** Include controller prompts, child calls, retries, cached tokens, wall time, and human review in total cost.
- **Do not use it when global relational reasoning is the task and the context is modest.** A direct long-context call may be simpler and better when the model genuinely needs to compare every item simultaneously.

## Interview questions

### Q1 — What is an RLM, and how is it different from RAG?
**Testing:** whether you can place the new pattern in the existing architecture.
**Answer:** RLM keeps the long input outside the model and gives the model programmable operations to inspect, partition, and recursively process slices. RAG retrieves from a pre-indexed corpus using a relevance mechanism. RLM can use exact search and task-specific exploration without a vector index; RAG is usually cheaper for stable, reusable retrieval.
**Follow-up trap:** *"Does RLM make RAG obsolete?"* — No. They solve different bottlenecks and can compose. Use retrieval for reusable candidate selection and RLM-style recursive inspection when the selected context still needs exploration or decomposition.

### Q2 — Why does a larger context window not solve context rot?
**Testing:** context engineering depth.
**Answer:** Fitting tokens is a capacity property, not a guarantee of uniform attention or reasoning. More distractors, long-range dependencies, and synthesis burden can reduce quality before the hard window limit; a 1M-token model can still perform worse on a huge prompt than on selected slices.
**Follow-up trap:** *"Wouldn't a stronger model solve that?"* — It can move the curve, not eliminate the tradeoff. RLM changes the computation by selecting and decomposing evidence rather than asking one attention pass to handle everything.

### Q3 — Walk through an RLM over 5,000 customer tickets.
**Testing:** mechanical design.
**Answer:** Keep tickets in a versioned external store; inspect schema; grep or filter target user IDs and date ranges; partition matches; run bounded child classification on each selected ticket; aggregate typed labels and evidence offsets; synthesize with a partial-result indicator. Never send all 5,000 tickets by default.
**Follow-up trap:** *"What if the tickets have no stable schema?"* — Spend one bounded inspection call to infer structure, then validate the inferred fields and fall back to chunked semantic inspection with explicit evidence rather than trusting the inferred schema blindly.

### Q4 — Quantify recursive fan-out risk.
**Testing:** systems math.
**Answer:** With average branching factor `b` and depth `d`, a full tree creates roughly `(b^(d+1)-1)/(b-1)` calls. `b=10,d=3` is 1,111 calls before retries. Therefore cap depth, child count, concurrency, tokens, cost, and wall time, and filter before spawning children.
**Follow-up trap:** *"If calls are parallel, is the cost problem gone?"* — No. Parallelism can reduce wall time while increasing provider cost, rate-limit pressure, memory, and downstream load. Budget both total work and concurrency.

### Q5 — What must a child result contain?
**Testing:** evidence and failure semantics.
**Answer:** Slice/source ID, version, evidence offsets or citations, typed claims, status, model/version metadata, input/output tokens, and error information. The reducer needs to distinguish `ok`, `no_answer`, `timeout`, and `error`.
**Follow-up trap:** *"Can a timeout count as no answer?"* — No. Timeout means missing evidence, not evidence that the slice contains no answer. Retry or mark the final answer partial.

### Q6 — How would you bound an RLM in production?
**Testing:** operational maturity.
**Answer:** Set maximum recursion depth, child calls, concurrent children, per-child and total wall deadlines, token and dollar budgets, output bytes, retry count, and cancellation propagation. Enforce checks before dispatch, charge retries and parallel calls individually, and kill work that continues after cancellation.
**Follow-up trap:** *"Which single budget matters most?"* — It depends on the SLO, but no single budget is sufficient. A step cap misses one expensive call; a dollar cap misses latency; a wall clock cap misses runaway detached work. Use layered budgets.

### Q7 — What security risks does the external environment create?
**Testing:** whether you understand that RLM is still an agent.
**Answer:** If the model can execute arbitrary code, read secrets, or make network calls, an untrusted document can prompt it into acting. Keep the environment read-only and capability-scoped, validate arguments outside the model, sandbox execution, deny egress, and audit every operation.
**Follow-up trap:** *"Does putting the document in a variable make it trusted?"* — No. It changes where data is stored, not its trust level. Treat document contents as untrusted data throughout the controller.

### Q8 — When would ordinary RAG beat RLM?
**Testing:** technology selection.
**Answer:** Stable corpus, repeated query distribution, high cache reuse, and a mature ANN/lexical index favor RAG. Precomputed indexes amortize work, while RLM may rescan and invoke children repeatedly. RLM wins when exploration is dynamic, exact filters matter, or context rot dominates.
**Follow-up trap:** *"Could you combine them?"* — Yes: RAG narrows candidates, then an RLM controller searches, partitions, or recursively analyzes the retrieved evidence with provenance.

### Q9 — Design a fair RLM benchmark.
**Testing:** evaluation discipline.
**Answer:** Hold model/provider, task set, output schema, corpus version, and correctness rubric constant. Compare direct long-context, compaction, retrieval, code-execution scaffold, and RLM. Report quality and evidence coverage with total tokens, child calls, cache hits, wall time, cost, failures, and partial answers.
**Follow-up trap:** *"The paper reports comparable cost. Is that enough?"* — No. Cost depends on provider pricing, caching, concurrency, retries, and task distribution. Reproduce accounting on your workload and report p50/p95/p99 latency, not just average cost.

### Q10 — A child result is correct but its citation range is wrong. What do you do?
**Testing:** evidence integrity.
**Answer:** Treat the result as invalid or degraded, because the answer cannot be audited. Validate offsets against the versioned source before aggregation; retry with a smaller slice or return a cited partial result rather than silently accepting an uncitable claim.
**Follow-up trap:** *"Would you still use the claim internally?"* — Only under an explicitly lower-confidence path that cannot drive consequential actions. For user-visible or high-stakes answers, unsupported evidence is not an acceptable success.

### Q11 — How do you route between direct, RAG, and RLM paths?
**Testing:** principal-level architecture.
**Answer:** Use measured gates: direct for short/modest contexts and global reasoning; RAG for stable corpora and reusable semantic retrieval; RLM for long or semi-structured inputs where exact programmatic exploration and context rot are demonstrated. Include estimated cost, latency budget, corpus version, security tier, and task type in the router decision.
**Follow-up trap:** *"What if the router itself is an LLM?"* — Keep hard constraints and budget policy deterministic. An LLM can propose a route, but the harness must reject a route that violates latency, cost, data, or tool permissions.

### Q12 — What is the migration path from a vanilla long-context system?
**Testing:** delivery judgment.
**Answer:** Instrument quality against context length; identify tasks with context rot; add a read-only external store and deterministic peek/search tools; introduce typed child calls behind a feature flag; compare against the old path on fixed evals; then expand only if measured quality, cost, and latency justify the extra operational surface.
**Follow-up trap:** *"Would you delete the old path after launch?"* — No, retain it as a fallback until the RLM path has enough production evidence and a rollback trigger; the new controller adds failure modes that offline tests may miss.

## Red flags that fail you

- Treating RLM as merely a bigger context window.
- Calling every chunk recursively without a cost or depth bound.
- Counting timeouts as negative evidence.
- Dropping source offsets and citations during reduction.
- Exposing shell, filesystem, secrets, or arbitrary network access to document-directed code.
- Comparing only answer quality while ignoring child-call cost and latency.
- Claiming RLM replaces RAG, compaction, or long-context models in every workload.

## Cheat card

```text
RLM = long prompt in EXTERNAL ENVIRONMENT, not all in model context.
MODEL can peek, grep, partition, recurse over slices, then reduce typed results.
Target: context rot, distractors, long-range recall/synthesis failures.
RAG selects from an index; RLM PROGRAMMATICALLY EXPLORES external context.
Cheap first: schema inspect -> exact filter/grep -> partition -> child model calls.
Calls tree: (b^(d+1)-1)/(b-1); b=10,d=3 => 1,111 calls before retries.
BUDGET: depth, child calls, concurrency, tokens, cost, wall time, output bytes, retries.
Child result: source/version/range evidence + claims + status + token/cost metadata.
TIMEOUT != no_answer; missing child evidence must remain visible or be retried.
Security: untrusted data stays data; read-only tools, sandbox, egress deny, audit.
Evaluate against direct, compaction, RAG, CodeAct: quality + evidence + cost + p95/p99.
Use RLM when measured context rot/exploration benefit exceeds orchestration complexity.
```

## Sources

- [Recursive Language Models](https://arxiv.org/abs/2512.24601) — accessed 2026-09-20
- [Context Engineering](../07-agentic-ai/11-context-engineering.md) — accessed 2026-09-20
- [Harness Engineering](../07-agentic-ai/25-harness-engineering.md) — accessed 2026-09-20
- [Agent Safety](../07-agentic-ai/14-agent-safety.md) — accessed 2026-09-20

## Changelog

- 2026-09-20 — created from the second saved-post refresh; adds external-context recursive inference rather than duplicating context-rot coverage.
