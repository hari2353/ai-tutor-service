# Lab 32: Bounded Recursive Context Controller

**Track:** T07 Agentic AI · **Time:** 2h · **XP:** 50
**Module:** `T07-recursive-language-models`

**You will build:** a deterministic recursive-context controller that searches external documents, calls a fake child solver only on selected slices, preserves evidence, and stops at depth/call/token budgets.

**You will be able to answer:** *"How do you keep a recursive context system from becoming an unbounded and unauditable agent?"*

## Setup

```bash
cd labs/py/32-recursive-language-models
python -m venv .venv && . .venv/bin/activate
pip install pytest
```

## The spec

Implement `controller.py`:

1. `ContextStore` stores versioned documents and returns bounded `Slice` objects from `peek` and case-insensitive `grep`.
2. `Budget` tracks maximum calls, depth, and tokens. Charging beyond any limit raises `BudgetExceeded` before the child runs.
3. `ChildResult` preserves slice ID, claims, evidence offsets, status, and token counts.
4. `run_children(question, slices, child, budget, depth=0)` invokes the injected child only while budget permits and returns results in deterministic slice order.
5. A child timeout/error becomes a typed result and does not become a false negative claim.
6. `reduce_results(results)` deduplicates claims, preserves evidence, and reports partial failure plus failed slice IDs.
7. No function may sleep, use wall-clock time, read arbitrary files, or access a network.

## Run the tests

```bash
pytest tests/ -q                 # starter: MUST FAIL
pytest tests/ -q --solution      # reference: MUST PASS
```

## Stretch goals

1. Add a concurrency limit with a fake executor. *(Interview: "How do you reduce p95 without allowing fan-out to explode?")*
2. Add a versioned result cache keyed by source version, slice range, question, and policy version. *(Interview: "How do you avoid stale evidence?")*
3. Add an attack test where document text contains a fake tool instruction. *(Interview: "Why is RLM still an agent security surface?")*
