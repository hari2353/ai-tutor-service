# Lab 10: Context Engineering — Budgets, Truncation, Compaction

**Track:** T07 Agentic AI · **Time:** 2h · **XP:** 50
**Module:** `T07-context-engineering`

**You will build:** a context budget manager in pure Python — token arithmetic, tool-result truncation at the boundary, and a compactor that folds old turns into one recap while never touching the task, the constraints, or anything flagged `protect`.

**You will be able to answer:** *"Implement compaction. What must never be compacted, and what mechanism guarantees it?"*

## Setup

```bash
cd labs/py/10-context-engineering
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The model

A context is a list of items, each:

```python
{"role": "user", "text": "...", "kind": "task" | "constraint" | "tool_result" | "turn" | "recap"}
```

Tokens are arithmetic, not vibes: `est_tokens(text) = ceil(len(text) / 4)`.

## The spec

1. **`ContextBudget(limit)`** — `.total(items)` and `.fits(items)`; an item costs `est_tokens` of its text. Empty lists always fit.
2. **`truncate_tool_results(items, max_per=500)`** — every `tool_result` over `max_per` tokens becomes a stub that keeps its head and gains `\n[truncated N tokens]`, where N is the exact number of dropped tokens. The stubbed item stays within cap. Non-tool kinds, under-cap results, and `protect`-flagged items pass through untouched. Already-stubbed results are skipped (idempotent).
3. **`compact(items, keep_recent=4, summarizer=None)`** — older `turn`/`tool_result` items fold into exactly ONE recap item (`kind: "recap"`), placed at the position of the first evicted item. NEVER touches `task`/`constraint` kinds, `protect: true` items, or the last `keep_recent` compactable items — those survive verbatim with identity preserved. The default summarizer keeps the first line per evicted text; a custom summarizer is called ONCE with the evicted texts joined by `\n`.
4. **`enforce(items, limit)`** — the pipeline: truncate → compact → repeat until `.fits`, or raise `Unfittable`. Raises up front when protected items alone exceed the limit; returns the input object unchanged when it already fits.

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

## Stretch goals

1. **Structured recap schema** — summarise into Task / State / Discoveries / Failed approaches / Open items / Verbatim values, and mechanically verify identifier survival before committing.
2. **Cache-aware clearing** — add `clear_at_least` semantics to truncation and compute the cache break-even point.
3. **Pending tool pairs** — refuse to compact while a `tool_use` awaits its `tool_result`; snap the boundary.
4. **Progress-file seeding** — seed the recap from an append-only progress file so summaries are never summaries-of-summaries.
