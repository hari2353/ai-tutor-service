# Production notes — ReAct / Plan-and-Execute / Reflexion

## What you'd actually use

| Need | Tool | Note |
|---|---|---|
| Graph runtime | LangGraph | StateGraph with explicit replan edges; checkpointed by default |
| Hosted ReAct | Agent frameworks' built-in | Same trace shape; you own the budget knobs |
| Reflection memory | LangGraph `Store` / custom | Reflections persist across attempts — and across sessions |

## What production adds over yours

- **Structured intermediates**: production ReAct emits tool calls as data, not parsed `Action:` lines — the trace you assert on is JSON, and the parse step is gone (with its failure class).
- **Replan is a graph edge, not a flag**: the at-most-once constraint in your lab becomes a cycle guard in the graph with the transition tested as a unit.
- **Reflection needs a sink**: reflections accumulate; without a store they bloat context and the third reflection is the model arguing with itself.
- **Cost asymmetry is real**: Plan-and-Execute saves tokens until the first surprise; ReAct burns them linearly. Production picks per task volatility, not per taste.

## What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Reflexion loops 5x on a hard task | No reflection cap or diminishing-returns check | Cap attempts; score each; keep best-of-N |
| ReAct trace unparseable in prod | Free-text Thought/Action against a real model | Use tool-calling APIs — structured output, not parsing |
| Plan drifts silently | Planner never re-sees observations | Plan-and-Execute with a replan trigger threshold |
| Works on FakeLLM, fails live | Model variation on edge cases | Golden-trajectory tests over a corpus, plus the fake for logic |

## The one-liner to remember

ReAct interleaves thinking and acting, Plan-and-Execute amortises the
thinking, and Reflexion turns failure into context — pick the loop shape
that matches how often reality interrupts the plan.
