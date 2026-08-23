# Context Engineering: Budgets, Compaction, Context Editing, Subagents

> Sprint weekend 4 · source: `curriculum/07-agentic-ai/11-context-engineering.md`

```
THE THESIS
  context = BUDGET with diminishing returns, not a buffer.
  goal = smallest set of HIGH-SIGNAL tokens for the outcome.
  MORE TOKENS → WORSE AGENT (gradient, not cliff)

WHY (name all three)
  n² pairwise attention → mass per relationship thins
  training skewed short → few params for context-wide deps
  positional non-uniformity → "lost in the middle" U-curve (Liu 2023)
  Chroma 2025: 20-50% acc loss 10k→100k+, 18 frontier models
    distractors > length · coherent input degrades MORE than shuffled
  RULE OF THUMB: effective window ≈ 40-50% of nominal for mid-context recall

COST ARITHMETIC
  cumulative_input = turns·base + growth·turns(turns-1)/2   ← QUADRATIC
  6k base + 4k/turn × 40 turns = 3.36M tok. growth→1k ⇒ 1.02M. same task.
  cache read ≈ 0.1x input → keep the prefix BYTE-STABLE

FOUR LEVERS, IN ORDER
  1. TRUNCATE at the tool          free, lossless-where-it-matters, biggest win
  2. CLEAR stale tool results      free (no LLM call), but breaks cache
  3. COMPACT                       1 LLM call, lossy, needs a schema + verification
  4. ISOLATE (subagent / files)    50k spent privately → 1-2k returned (~30x)

CONTEXT EDITING (real API)
  beta: context-management-2025-06-27
  clear_tool_uses_20250919 · trigger dflt 100k tok · keep dflt 3 pairs
    clear_at_least (cache-break floor) · exclude_tools · clear_tool_inputs=false
  clear_thinking_20251015 · keep {thinking_turns:N}|"all" · MUST be listed first
  server-side compaction compact_20260112 = recommended; SDK compaction_control DEPRECATED
  NUMBERS: ctx editing alone +29% · + memory tool +39% · 100-turn search: -84% tokens

COMPACTION RULES
  trigger 55-65% (NOT 95% — the summary needs headroom)
  never mid tool_use/tool_result pair · snap the boundary (orphan = 400)
  SCHEMA: Task · State · Discoveries · FAILED APPROACHES · Open items · Verbatim values
  VERIFY mechanically (regex IDs must survive) → retry once → else DO NOT COMPACT
  cap compactions/run (~4) and alert; >4 means per-turn growth is the real bug

NEVER COMPACT (7)
  task+success criteria · hard constraints · open obligations · identifiers/exact values
  last user correction · pending tool call · approval/permission state
  MECHANISM: regenerate into a protected block; the summariser never sees it.
  (safety constraints being summarised away = "governance decay" = security bug)

SUBAGENTS
  read-heavy / write-light / large intermediate / small output / parallelisable
  return contract: Answer · Evidence(file:line|url) · Confidence · NOT CHECKED
  Anthropic research: +90.2% vs single-agent Opus 4, ~15x tokens
  cost: unauditable lossy handoff → require POINTERS; WRITES STAY SINGLE-THREADED

PROGRESS FILE
  never in the window → compaction cannot lose it
  append w/ timestamps (rewriting = summary-of-summary = brevity bias)
  harness INJECTS open items every turn; "remember to read it" is not a mechanism

WHEN NOT TO
  short runs (<30% window) · tasks needing exact recall of early detail
  client-side compaction + server-side tools (cache_read inflates the count)
  subagents before fixing the tool · subagents that write
  context editing ≠ memory (within-session deletion only)
```
