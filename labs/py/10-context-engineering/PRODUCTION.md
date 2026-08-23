# Production notes — context budget management

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| Server-side compaction | Anthropic `compact_20260112` | recommended default; correct token accounting |
| Context editing (clear stale tool results) | `clear_tool_uses_20250919` + `clear_thinking_20251015` | free (no LLM call), but invalidates the prompt cache at the clear point |
| Client-side trimming | LangGraph `trim_messages`, custom pre-model hook | you own orphaned tool pairs and trigger policy |
| Prompt compression | LLMLingua / LLMLingua-2 | 2-20x squeeze; quality is task-dependent — eval before trusting |
| Framework compaction | Google ADK (Python v1.16.0+) | framework-native, less control |
| Cross-session memory | Anthropic memory tool (`memory_20250818`) | files survive compaction because they were never in the window |

**Do not run client-side compaction next to server-side tools** until token accounting is fixed: `cache_read_input_tokens` accumulates across a web-search tool's internal calls, so naive clients compact a 63k conversation every other turn.

## What the real ones add over yours

- **Real tokenizers or the counting endpoint**, not `len/4`. Your estimate is fine for budgets, wrong for bills.
- **Mechanical verification of recaps**: regex every identifier-shaped token out of the evicted region and assert each appears in the summary; retry once naming the omissions; refuse to compact if it fails twice.
- **Boundary snapping**: never cut between a `tool_use` and its `tool_result` — an orphan half is a 400.
- **Trigger at ~60% of the window**, not 95%: the summarisation call itself needs headroom.
- **Compaction counters with alerts**: more than ~4 per run means per-turn growth is the real bug.

## What breaks in practice

| Symptom | Cause | Fix |
|---|---|---|
| Agent forgets the task around turn 20 | Naive truncation dropped message 0 | Task/constraints live in a protected block, regenerated each turn |
| Agent retries a failed approach | Recap had no "failed approaches" section | Schema it |
| Wrong order id after turn 40 | Summariser dropped identifiers | Verbatim-values section + mechanical verification |
| Constraint silently gone at turn 70 | Governance decay via recursive summaries | Protected block + assertion test in CI |
| Cost went UP after context editing | Every clear invalidates the cache prefix | `clear_at_least`; do the break-even arithmetic |
| Compaction fires constantly on short chats | Counting accumulated cache reads as input | Token-counting endpoint or exclude cache reads |

## The survival test that catches the whole class

Golden run with an identifier at turn 3, a hard constraint at turn 1, and an open item at turn 10; force three compactions; assert all three are present and exact at turn 90. Deterministic against a scripted summariser, and it is a complete interview answer on its own.

## The 3 questions an interviewer asks after this lab

1. *"Why keep the last N turns verbatim instead of summarising everything?"* — position matters (lost-in-the-middle) and recent corrections/tool state are exactly what the next turn needs verbatim.
2. *"Your summariser is lossy by definition. How do you ship anyway?"* — protected regions never enter the prompt to the summariser, plus mechanical verification with a refuse-to-compact fallback.
3. *"Subagent or compaction?"* — read-heavy/write-light subtasks with big intermediate volume and small output → isolate; continuous back-and-forth → compact. Writes stay single-threaded either way.
