# Lab 22: Loop Engineering — Budgets, Compaction Triggers, Stop Conditions

**Track:** T07 Agentic AI · **Time:** 3h · **XP:** 50
**Module:** `T07-loop-engineering`

**You will build:** the control levers of the canonical agent loop — budget objects, compaction strategy engine with stuck-detection, snapshot/resume, and metrics.

**You will be able to answer:** *"Your agent is looping — same tool, same args, turn after turn. What detects it, what stops it, and what's the difference between a stop condition and a budget?"*

## Setup

```bash
cd labs/py/22-loop-engineering
pip install pytest
```

## The spec

1. **`LoopBudget(turns, tokens_in, tokens_out, wallclock)`** — all caps; `consume_*` methods; `exhausted()` reports which budget tripped (first match wins).
2. **`CompactionEngine(strategy, tokenizer)`** — strategies: `truncate_oldest` (drop oldest non-pinned, keep pinned + first N), `sliding_window` (keep first `n_head` + last `n_tail`), `summarize` (call `summarizer` hook on dropped). `compact(messages, target_tokens)` returns the new message list. Trigger policy: compact when `tokens > threshold` (threshold = 0.8 × cap).
3. **`StopConditions`** — `evaluate(state)` returns the first tripped: `goal_met` (detector fn over messages), `stuck_loop` (same tool+args seen `k` consecutive times), `budget_exhausted` (from LoopBudget).
4. **`snapshot(state) / restore(blob)`** — serialize loop state (messages, counters, rng-free) to a dict and back; a resumed run with the same scripted LLM produces the same subsequent trace as an uninterrupted run.
5. **`MetricsRecorder`** — turns used, tokens by step, tool-call histogram; `report()` returns the dict.

## Run the tests

```bash
pytest tests/ -q          # against starter/ — FAILS. Make them pass.
```

Reference: `pytest tests/ -q --solution`

## Stretch goals

1. **Token-budget-aware compaction** — trigger compaction from *remaining* budget, not absolute cap; why does that change behavior on long tasks?
2. **Stuck-detector variants** — same-tool-same-args vs same-tool-different-args vs alternating pair; which catches real bugs vs which just annoys?
3. **Exponential backoff stop** — a soft-stop that inserts a nudge message before declaring stuck.
