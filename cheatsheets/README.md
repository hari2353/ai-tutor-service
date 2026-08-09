# Cheat Sheets

Ten one-page revision sheets, one per weekend of the interview sprint (see `curriculum.json`, `sprint_week` 1–10). Each sheet compresses every module scheduled for that weekend down to what actually needs to be recalled cold under interview pressure.

## What these are

Every module in this curriculum ends with a `## Cheat card` section — 8–15 atomic lines of bare facts, numbers, thresholds, and syntax, with no explanation attached. These sheets take the cheat cards (plus each module's `## The 30-second version`) for every module in a given sprint weekend and reorganise them into one printable page: related facts pulled together across modules, a ruthless "if you remember nothing else" list of the 5–8 highest-stakes facts for the whole weekend, and a single numbers table consolidating every threshold, default, and complexity bound so it can be scanned in one pass.

They are not summaries and not a replacement for the modules. They are compression artifacts — the modules are long enough to teach you the material once; these sheets are short enough to reread the morning it matters.

## When to use them

**Morning of an interview, not while learning.** If a fact on one of these sheets doesn't make sense, that's the sheet doing its job — go back to the module it came from (named in the file) and read the full explanation, the worked example, and the "why this gets asked" section. These sheets assume you've already done that once. Their only job is fast recall of things you've already understood, the morning you need them back.

A reasonable way to use the sprint: study weekend N's modules in full during week N, drill and mock-interview against them, then on the morning of an actual interview reread whichever weekend-N sheet(s) cover material likely to come up. Print one, or read it on a phone on the train — that's the whole design constraint.

## Source of truth

These sheets are generated from the modules' cheat cards, not the other way around. If a fact here looks wrong, stale, or contradicts the module, **the module is correct and this sheet needs regenerating** — file paths are noted inline under each weekend so you can go straight to the source. Nothing on these sheets was invented; where a module's cheat card was too thin to say something useful about a topic, the corresponding weekend sheet says so explicitly under a `## Gaps` heading rather than padding with material that isn't in the curriculum.

## Coverage

| File | Weekend | Modules |
|---|---|---|
| `weekend-1-agent-loops-and-resilience.md` | 1 | Agent loop from scratch, ReAct/Plan-Execute/Reflexion, resilience catalogue |
| `weekend-2-tools-and-langgraph.md` | 2 | Tool engineering, LangGraph I (core), LangGraph II (durability/HITL) |
| `weekend-3-rag-retrieval.md` | 3 | Chunking, vector index internals, hybrid search, latency/accuracy/cost triangle |
| `weekend-4-memory-context-multiagent.md` | 4 | Agent memory, context engineering, multi-agent topologies |
| `weekend-5-distributed-and-llm-internals.md` | 5 | Distributed fundamentals (CAP/PACELC), attention internals, inference serving |
| `weekend-6-system-design-craft.md` | 6 | Estimation, diagramming, design-from-scratch method |
| `weekend-7-databases-and-eval.md` | 7 | MVCC/isolation, query planner, LLM-as-judge, agent eval |
| `weekend-8-resume-and-behavioral.md` | 8 | Flagship systems as design docs, STAR bank, design communication, company-specific prep |
| `weekend-9-production-agents-and-genai-design.md` | 9 | Agent zero-to-production, 20 GenAI/agent system designs |
| `weekend-10-harness-and-architect.md` | 10 | Harness engineering, loop engineering, the Claude Architect model |

Each sheet's own header line states which weekend it covers and why that weekend's material tends to decide interview outcomes.
