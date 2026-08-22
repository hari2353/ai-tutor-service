# Context Engineering: Budgets, Compaction, Context Editing, Subagents

> **Track:** T07 Agentic AI · **Time:** 3h · **Prereqs:** `T07-agent-loop-from-scratch`, `T07-agent-memory` · **Updated:** 2026-07-26
> **Module id:** `T07-context-engineering` · **Tags:** sprint (W4), memory, context

## The 30-second version

Context is a **budget with diminishing marginal returns**, not a buffer you fill to the line. Attention is finite because a transformer computes n² pairwise relationships over n tokens and models were trained mostly on short sequences, so accuracy on retrieval and long-range reasoning degrades on a gradient well before the hard limit — Chroma measured 20-50% accuracy drops between 10k and 100k+ tokens across 18 frontier models, and near-miss distractors hurt worse than length alone. That gives the counterintuitive core claim: **adding tokens usually makes an agent worse**, so the job is finding the smallest set of high-signal tokens that gets the outcome. The four levers, in the order you reach for them, are: truncate at the tool boundary, **clear stale tool results** (Anthropic's context editing alone gave a 29% lift and cut tokens 84% over a 100-turn agentic search, and with the memory tool 39%), **compact** older turns into a structured recap while never touching the task, hard constraints, identifiers, or open obligations, and **isolate** — subagents that burn tens of thousands of tokens privately and return a 1-2k distilled summary, plus progress files that survive compaction entirely because they were never in the window.

## Why this gets asked

Because it is the skill that separates an agent that works in a demo from one that works at turn 60, and because every interviewer running agents in production has been burned by exactly one of two incidents. Either compaction ate something load-bearing — the agent summarised away the customer's account id or the "do not email the customer" constraint and then cheerfully did the wrong thing, which is unfalsifiable without a trace of the pre- and post-compaction context — or somebody "fixed" quality by moving to a bigger window, watched cost rise 4x, and watched accuracy fall. The question behind the question is whether you treat context as a capacity problem (junior) or an attention-allocation problem (senior). At principal level they will push on the thing nobody wants to say: that most context problems are caused by the engineer stuffing "just in case" data into the prompt.

`T07-agent-loop-from-scratch` introduced the three levers in one paragraph. This module is the mechanism, the numbers, and the code.

---

## Lineage: past → present → future

**What came before.** The first era was prompt engineering: one-shot prompts, and the craft was word choice. That worked because a single classification or generation call has a fixed, small context you author entirely. The agent era broke it, because in a loop the context is *generated* — tool results, thinking blocks, prior assistant messages — and nobody authored most of it. The first three responses to a growing context all failed in characteristic ways. **Naive truncation** (drop the oldest messages) broke tool-call pairing and lost the original task, producing an agent that forgot what it was doing at turn 20; symptom in a log is a `tool_result` with no matching `tool_use`, which most providers reject with a 400. **`ConversationSummaryMemory`** (LangChain, 2022-2023) replaced old turns with an LLM summary and lost exactly the specifics — IDs, dates, exact constraint wording — that the next turn needed. And **"just use a bigger window"** was the industry's favourite answer through 2023-2024, moving 4k → 8k → 32k → 128k → 1M. That failed for a reason nobody expected: the quality curve did not follow the capacity curve. The Stanford **"Lost in the Middle"** paper (Liu et al., arXiv:2307.03172, 2023) showed a U-shaped accuracy curve with content in the middle of a long context recalled worst, and it was the first widely-read evidence that the window is not uniformly usable.

**Where it stands now.** The name settled — **context engineering** — and Anthropic's Sept 2025 framing is the one interviewers quote: context is a finite resource with an "attention budget", and the goal is *the smallest set of high-signal tokens that maximises the likelihood of the desired outcome*. The mechanistic story is also settled: transformers let every token attend to every other, giving n² pairwise relationships for n tokens, and models see far more short sequences than long ones in training, so there are fewer specialised parameters for context-wide dependencies; position-encoding interpolation extends the window at some cost to positional precision. The result is a **performance gradient, not a cliff**. Chroma's context-rot study quantified it across 18 frontier models, and produced the finding that most surprises people: **coherently structured input degrades attention more than shuffled input does**, and needle-question semantic similarity plus distractor presence matter more than raw length. The tooling caught up in the same window: Anthropic shipped context editing and a file-based memory tool on 29 Sept 2025 (beta header `context-management-2025-06-27`), with `clear_tool_uses_20250919` and later `clear_thinking_20251015`, and by 2026 server-side compaction (`compact_20260112`) became the recommended default while the client-side SDK `compaction_control` was deprecated. Google's ADK shipped compaction in Python v1.16.0+. **The live disagreements are real.** (1) *Compaction vs isolation:* Cognition's "Don't Build Multi-Agents" (June 2025) argues for a single-threaded linear agent with a dedicated compression model, because subagent handoffs lose context; Anthropic's research system argues for parallel subagents with isolated windows and reported outperforming single-agent Opus 4 by 90.2% on research tasks at roughly 15x the tokens. Both are right about different task shapes. (2) *Bigger windows vs curation:* 1M-token windows went generally available at standard per-token pricing in March 2026, which removes the *cost* argument against long context but not the *quality* one. (3) *Where compaction runs:* server-side (less code, opaque) versus client-side (you own the prompt, you own the bugs).

**Where it's heading.** High confidence: **compaction becomes a platform feature you configure rather than code**, the way retry and caching did; the direction of travel from Anthropic's own docs is explicit — server-side compaction is now the recommended path and the client-side hook is deprecated. High confidence: **incremental, itemised context updates beat wholesale rewrites**. The Agentic Context Engineering (ACE) line of work presented at ICLR 2026 represents context as structured, itemised bullets updated additively, which avoids the "brevity bias" collapse where each successive summary of a summary loses more than the last. Medium confidence: **context management becomes safety-relevant infrastructure**, not just a cost lever — 2026 work on "governance decay" documents safety constraints being silently erased by compaction across long horizons, which means your protected-regions list is a security control. Speculative: **KV-cache-level compaction**, where the eviction happens in attention state rather than in the message list, which would make compaction lossless from the harness's point of view; there are serving-side papers but nothing you should design an application around. Also speculative: the "agents should just have infinite context" position. Treat it as fashion until someone shows an eval where a 1M-token stuffed context beats a curated 40k one on the same task.

---

## Mental model

Two pictures. The first is the budget ledger; the second is why the ceiling is not where you think.

```
CONTEXT AS A LEDGER (every turn, you re-spend all of it)
┌───────────────────────────────────────────────────────────────────────────┐
│ ZONE 1 — STABLE PREFIX            system prompt · tool schemas · rules     │  ← cache it
│                                    NEVER reorder. Cache read ≈ 0.1x input. │     (~90% off)
├───────────────────────────────────────────────────────────────────────────┤
│ ZONE 2 — PROTECTED                task · success criteria · hard limits    │  ← never compact
│                                    IDs · open obligations · last correction│
├───────────────────────────────────────────────────────────────────────────┤
│ ZONE 3 — RETRIEVED / RECAP        memories · docs · <progress_so_far>      │  ← rebuilt each turn
├───────────────────────────────────────────────────────────────────────────┤
│ ZONE 4 — WORKING SET              last N turns verbatim · recent tool out  │  ← the churn
├───────────────────────────────────────────────────────────────────────────┤
│ ZONE 5 — HEADROOM                 max_tokens for the response              │  ← reserve it
└───────────────────────────────────────────────────────────────────────────┘
   compaction operates ONLY on zone 4 → and writes its output into zone 3
   context editing operates ONLY on old tool results inside zone 4
   subagents and progress files move work OUT of zones 3+4 entirely
```

```
WHY THE CEILING ISN'T THE LIMIT

 quality
   ▲
1.0│●●●●●●●●●
   │         ●●●●●
   │              ●●●●●              ← performance GRADIENT (context rot)
   │                   ●●●●●            20-50% accuracy loss 10k → 100k+
   │                        ●●●●●●      (Chroma, 18 frontier models)
   │                              ●●●●●●●●
   │                                      ●●●● │ ← hard limit (400 error)
   └────────────────────────────────────────────┼──▶ tokens
     8k     32k      100k       200k          1M

  the engineering mistake: designing for the RIGHT edge
  the engineering job:      staying on the LEFT plateau
```

The analogy that lands: **context is a working desk, not a filing cabinet.** A bigger desk does not make you find the one page faster; past a point it makes you slower because there is more to scan and more that looks like the thing you want. The filing cabinet (files, stores, subagents) is where volume belongs. What goes on the desk is a decision you make every turn.

---

## How it actually works

### Token accounting: do it as arithmetic, not vibes

You should be able to derive the cost of a run live in an interview. The two facts that generate everything: **the model is stateless, so every turn re-sends the whole prefix**, and **cost is linear per turn but the prefix grows**, so cumulative cost is quadratic in turns.

```python
# Cumulative input tokens over an N-turn run where each turn adds `growth` tokens
# to the prefix. This is the number that surprises people on their first bill.
def cumulative_input_tokens(base: int, growth: int, turns: int) -> int:
    return sum(base + growth * t for t in range(turns))
    # = turns*base + growth * turns*(turns-1)/2      ← the quadratic term

# Worked: 6k stable prefix, each turn adds ~4k (a chatty tool result), 40 turns
cumulative_input_tokens(6_000, 4_000, 40)   # = 240_000 + 3_120_000 = 3_360_000
# At $3/Mtok input that's ~$10.08 of INPUT for one run. Cut per-turn growth to
# 1k (truncate tool results at the tool) and it's 240k + 780k = 1.02M → ~$3.06.
# Cache the 6k prefix (cache read ≈ 0.1x) and you save another ~$0.65.
# Same task. 3x cheaper. The lever was the TOOL, not the model.
```

Two operational consequences:

1. **Per-turn growth is the variable that matters**, not the window size. A 1M window with 40k/turn growth is bankrupt by turn 15; a 200k window with 800/turn growth runs for hours.
2. **Keep the stable prefix stable.** Prompt caching bills cache reads at roughly 0.1x the base input rate, so a 6k system-prompt-plus-schemas block that never changes is nearly free after the first call. Anything that reorders or edits that prefix — including a context-editing pass that clears tool results — invalidates the cache from that point on, which is why `clear_at_least` exists (see below).

Instrument this. The minimum you need per request: `input_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`, `output_tokens`, plus a breakdown by zone. Without the zone breakdown, "context got big" is not actionable; with it you can see that tool results are 78% of the prefix and go fix the tool.

### Attention degradation before the hard limit

Three independent mechanisms, and you should be able to name all three because interviewers use this to separate people who read a blog post from people who understand why.

1. **Quadratic dilution.** Every token can attend to every other, giving n² pairwise relationships. As n grows, the attention mass available to any individual relationship is stretched thin. This is architectural, not a bug, and it does not go away with a longer window.
2. **Training distribution.** Short sequences dominate pretraining corpora, so models have fewer specialised parameters and less experience for context-wide dependencies. Position-encoding interpolation (the standard technique for extending a trained window) buys length at some cost to positional precision.
3. **Positional non-uniformity.** "Lost in the Middle" (Liu et al., 2023) found a U-shaped curve: content at the start and end of a long context is recalled far better than content in the middle. This is why *where* you put the task statement and the constraints matters, and why the standard layout is stable prefix at the top, protected constraints near the top, and the current instruction near the bottom.

What Chroma's 2025 context-rot work added is that **length is not the only variable, and often not the dominant one**:

| Factor | Effect | What you do about it |
|---|---|---|
| Input length | 20-50% accuracy loss from 10k → 100k+ across 18 frontier models | keep the working set small |
| Needle-question similarity | low lexical/semantic overlap between the query and the target degrades fast | restate the target in the query's vocabulary; put the ask last |
| Distractors | semantically near-miss content hurts disproportionately | this is exactly what top-k ANN returns — use a relevance floor and dedupe |
| Haystack structure | **coherent, well-structured input degrades attention *more* than shuffled** | counterintuitive; the practical read is that "just paste the whole doc, it reads nicely" is not a defence |

The operational rule worth stating out loud: **treat your effective window as roughly 40-50% of the nominal one for anything that depends on precise retrieval from the middle of it**, and design so you are nowhere near either number. If you are near the hard limit you have a design bug, not a capacity problem.

### Compaction: the strategies, and what must never be compacted

Five strategies, escalating. Most systems need three of them.

| Strategy | What it does | Cost | Loses |
|---|---|---|---|
| **Tool-result truncation at the tool** | the tool returns 2KB and a pointer instead of 200KB | free, no LLM call | nothing you needed, if the tool is written well |
| **Tool-result clearing** | replace old tool results with a placeholder | free, no LLM call, but invalidates cache | ability to re-read a result the model already processed |
| **Sliding window + rolling summary** | summarise older turns, keep last k verbatim | one cheap LLM call | specifics the summariser judged unimportant |
| **Structured checkpoint recap** | summarise into a *schema* (task / state / decisions / discoveries / open items / preserve) | one LLM call, better prompt | less, because the schema forces recall of each category |
| **Hierarchical / recursive** | summaries of summaries for multi-hour runs | repeated calls | the most, via brevity bias compounding at each level |

The graduation from "rolling summary" to "structured checkpoint recap" is the single highest-value change most teams can make, and it is worth knowing that Anthropic's own default summary prompt is exactly a schema with five sections: **Task Overview** (core request, success criteria, constraints), **Current State** (what is done, files modified, artefacts), **Important Discoveries** (technical constraints, decisions, errors resolved, *failed approaches*), **Next Steps** (actions, blockers, priority), and **Context to Preserve** (user preferences, domain details, commitments). Note "failed approaches" — without it, the post-compaction agent cheerfully retries the thing that already failed, which is the most recognisable compaction failure in a trace.

**The protected list. Never compact:**

1. **The original task and its success criteria.** Message 0, verbatim, always.
2. **Hard constraints and prohibitions.** "Never email the customer directly", "read-only on prod". 2026 work on *governance decay* documents these being silently erased by successive compactions in long-horizon runs, which makes this a security control and not a nicety.
3. **Open obligations.** The explicit TODO list. If it existed before compaction and not after, the agent has silently dropped work and will report success.
4. **Identifiers and exact values.** Order ids, account numbers, file paths, version pins, dollar amounts, dates. Summarisers destroy these first because they read as noise.
5. **The user's most recent correction.** "No, I said staging, not prod." Losing this makes the agent repeat the exact mistake it was just corrected on, which is the fastest way to destroy user trust.
6. **Any pending tool call.** A `tool_use` block whose `tool_result` has not arrived cannot be summarised away; you either complete the pair or drop both. Orphaning either half is a 400 from the API.
7. **Safety/permission state.** Which approvals have been granted, which have been denied, and why.

The mechanism for protecting them is not "tell the summariser to be careful" — it is structural. Protected content is regenerated from state each turn and placed outside the compactable region, so the summariser never sees it and therefore cannot lose it.

### A real compaction implementation

This is the code to be able to write on a whiteboard. It handles token accounting, protected regions, pending tool pairs, cache-awareness, loop prevention, and verification.

```python
"""compaction.py — a real compactor. Provider-shaped for Anthropic Messages;
the structure transfers directly to OpenAI/Gemini message lists.
The tested version, with a scripted fake client, is in
(lab pending). Read this as the reference structure."""
from __future__ import annotations
import json, re
from dataclasses import dataclass, field

RECAP_SCHEMA = """\
Summarise the conversation below into a continuation brief. Use EXACTLY these
sections. Be specific: preserve every identifier, path, version, number, and
quoted constraint verbatim. Do not editorialise. Do not omit failures.

## Task
The original request, success criteria, and hard constraints.
## State
What is done. Files/records changed. Artefacts produced (with paths).
## Discoveries
Facts learned, decisions made WITH reasons, errors resolved.
## Failed approaches
What was tried and did not work, and why. Be complete: omitting these causes
the next agent turn to retry them.
## Open items
Everything still outstanding, as a checklist. Copy from the prior open items
list and add anything new. Never drop an item without saying it was completed.
## Verbatim values
Every identifier, path, URL, version, and amount mentioned anywhere above,
as a flat list. This section exists so nothing numeric is lost.
"""

@dataclass
class Protected:
    """Regenerated from durable state each turn. The summariser never sees it."""
    task: str
    constraints: list[str] = field(default_factory=list)
    open_items: list[str] = field(default_factory=list)
    identifiers: dict[str, str] = field(default_factory=dict)  # name -> exact value
    last_correction: str | None = None
    approvals: dict[str, bool] = field(default_factory=dict)

    def render(self) -> str:
        parts = [f"<task>{self.task}</task>"]
        if self.constraints:
            parts.append("<hard_constraints>\n- " + "\n- ".join(self.constraints) + "\n</hard_constraints>")
        if self.open_items:
            parts.append("<open_items>\n- [ ] " + "\n- [ ] ".join(self.open_items) + "\n</open_items>")
        if self.identifiers:
            parts.append("<identifiers>" + json.dumps(self.identifiers) + "</identifiers>")
        if self.last_correction:
            parts.append(f"<most_recent_user_correction>{self.last_correction}"
                         f"</most_recent_user_correction>")
        if self.approvals:
            parts.append("<approvals>" + json.dumps(self.approvals) + "</approvals>")
        return "\n".join(parts)


class Compactor:
    def __init__(self, client, *, window: int, summary_model: str,
                 trigger_frac: float = 0.60, keep_recent_turns: int = 6,
                 min_reclaim_frac: float = 0.20):
        self.client, self.window = client, window
        self.summary_model = summary_model
        self.trigger = int(window * trigger_frac)        # compact at 60%, not 95%
        self.keep = keep_recent_turns
        self.min_reclaim = int(window * min_reclaim_frac)
        self.compactions = 0

    # ---- 1. decide -------------------------------------------------------
    def should_compact(self, tokens: int, messages: list[dict]) -> bool:
        if tokens < self.trigger:
            return False
        if self._has_pending_tool_use(messages):
            return False           # never compact mid tool-call pair
        if len(messages) <= self.keep + 2:
            return False           # nothing compactable → avoid a no-op loop
        return True

    @classmethod
    def _has_pending_tool_use(cls, messages: list[dict]) -> bool:
        """True if the last assistant message issued tool_use with no result yet."""
        for m in reversed(messages):
            blocks = m["content"] if isinstance(m["content"], list) else []
            types = {_btype(b) for b in blocks}
            if m["role"] == "assistant" and "tool_use" in types:
                return True
            if m["role"] == "user" and "tool_result" in types:
                return False
        return False

    # ---- 2. split --------------------------------------------------------
    def _boundary(self, messages: list[dict]) -> int:
        """Index where the verbatim tail begins. Snap forward so a tool_result
        never becomes an orphan by having its tool_use summarised away."""
        i = max(1, len(messages) - self.keep)
        while i < len(messages) and self._starts_with_tool_result(messages[i]):
            i += 1
        return i

    @staticmethod
    def _starts_with_tool_result(m: dict) -> bool:
        c = m.get("content")
        return isinstance(c, list) and bool(c) and _btype(c[0]) == "tool_result"

    # ---- 3. compact ------------------------------------------------------
    def compact(self, messages: list[dict], protected: Protected,
                token_count: int) -> tuple[list[dict], dict]:
        i = self._boundary(messages)
        system, middle, tail = messages[0], messages[1:i], messages[i:]
        if len(middle) < 2:
            return messages, {"applied": False, "reason": "nothing_compactable"}

        recap = self.client.messages.create(
            model=self.summary_model, max_tokens=3000,
            messages=[{"role": "user",
                       "content": RECAP_SCHEMA + "\n\n<conversation>\n"
                                  + _render(middle) + "\n</conversation>"}],
        )
        recap_text = _text(recap)

        # 3a. VERIFY before committing. This is the step everyone skips.
        missing = self._verify(recap_text, middle, protected)
        if missing:
            # Retry once, naming the omissions. If it fails again, keep more
            # verbatim rather than shipping a lossy recap.
            recap = self.client.messages.create(
                model=self.summary_model, max_tokens=3500,
                messages=[{"role": "user", "content": RECAP_SCHEMA
                           + f"\n\nYou MUST include these exact values: {missing}"
                           + "\n\n<conversation>\n" + _render(middle) + "\n</conversation>"}],
            )
            recap_text = _text(recap)
            if self._verify(recap_text, middle, protected):
                return messages, {"applied": False, "reason": "verification_failed"}

        new_messages = [
            system,
            {"role": "user", "content": protected.render()},        # zone 2, always
            {"role": "user", "content": f"<progress_so_far>\n{recap_text}\n</progress_so_far>"},
            {"role": "assistant", "content": "Understood. Continuing from the brief above."},
            *tail,
        ]
        self.compactions += 1
        return new_messages, {
            "applied": True, "compaction_index": self.compactions,
            "messages_before": len(messages), "messages_after": len(new_messages),
            "tokens_before": token_count, "recap_tokens": len(recap_text) // 4,
        }

    # ---- 4. verify -------------------------------------------------------
    ID_RE = re.compile(r"\b(?:[A-Z]{2,}-\d+|[0-9a-f]{8,}|\d{4,}|v?\d+\.\d+\.\d+"
                       r"|/[\w./-]{4,}|\$[\d,]+(?:\.\d\d)?)\b")

    def _verify(self, recap: str, middle: list[dict], protected: Protected) -> list[str]:
        """Every identifier-looking token in the compacted region must appear in
        the recap, and every open item must still be present. Cheap, mechanical,
        and it catches the failure that actually happens."""
        source = _render(middle)
        ids = {m.group(0) for m in self.ID_RE.finditer(source)}
        missing = sorted(i for i in ids if i not in recap)
        missing += [f"OPEN_ITEM:{it}" for it in protected.open_items if it[:40] not in recap]
        return missing[:20]


def _btype(block) -> str | None:
    """Content blocks arrive as SDK objects or plain dicts. Handle both."""
    if isinstance(block, dict):
        return block.get("type")
    return getattr(block, "type", None)

def _render(messages: list[dict]) -> str:
    out = []
    for m in messages:
        c = m["content"]
        out.append(f"[{m['role']}] " + (c if isinstance(c, str) else json.dumps(c, default=str)))
    return "\n".join(out)

def _text(resp) -> str:
    return "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
```

Seven design decisions in there worth defending out loud:

- **Trigger at 60%, not 95%.** Compaction itself needs headroom: you must fit the region being summarised *plus* the summary output. Triggering late means the compaction call itself fails, which is the worst possible time.
- **Never compact mid tool-call pair.** Orphaning a `tool_use` or `tool_result` is a 400. Anthropic's own SDK compaction handles this by dropping the pending `tool_use` and letting the model reissue it; refusing to compact until the pair completes is cleaner.
- **Boundary snapping.** Cutting between a `tool_use` and its `tool_result` produces the same orphan. Snap forward.
- **Protected block is regenerated, not summarised.** This is the whole thesis. Structure beats instructions.
- **A verbatim-values section in the schema.** Summarisers drop numbers first. Forcing a flat list of every identifier is the cheapest possible mitigation.
- **Mechanical verification with a retry.** A regex over identifiers is crude and catches the real failure. If verification fails twice, *do not compact* — degrade to keeping more verbatim and let the token budget stop the run instead of shipping a recap that lost the account number.
- **A compaction counter.** Two symptoms live here: an infinite compact loop when nothing is compactable, and quality collapse from recursive summarisation. Alert if a single run compacts more than about 4 times; that is a signal that per-turn growth is the real bug.

### Context editing: the cheapest lever, with real config

Context editing is compaction's simpler sibling: instead of summarising, you *delete* content the model has already consumed. Anthropic's version runs **server-side, before the prompt reaches the model**, and your client keeps the full unmodified history — which is a genuinely nice property, because your logs stay complete.

```python
# Real, current API shape. Beta header required.
response = client.beta.messages.create(
    model="claude-opus-5",
    max_tokens=4096,
    messages=messages,
    tools=tools,
    betas=["context-management-2025-06-27"],
    context_management={"edits": [
        # order matters: thinking-clearing must be listed FIRST
        {"type": "clear_thinking_20251015",
         "keep": {"type": "thinking_turns", "value": 2}},
        {"type": "clear_tool_uses_20250919",
         "trigger":        {"type": "input_tokens", "value": 50_000},  # default 100_000
         "keep":           {"type": "tool_uses",    "value": 5},       # default 3
         "clear_at_least": {"type": "input_tokens", "value": 5_000},   # cache-break floor
         "exclude_tools":  ["web_search"],       # never clear these results
         "clear_tool_inputs": False},            # default: keep the CALL, clear the RESULT
    ]},
)
print(response.context_management.applied_edits)
# [{'type': 'clear_tool_uses_20250919', 'cleared_tool_uses': 8,
#   'cleared_input_tokens': 50000}]
```

| Parameter | Default | Why you'd change it |
|---|---|---|
| `trigger` | 100,000 input tokens | lower it for cost-sensitive workloads or smaller effective windows |
| `keep` | 3 tool use/result pairs | raise it when the agent genuinely needs to compare recent results |
| `clear_at_least` | none | **the cache lever**: clearing invalidates the cached prefix from that point, so only clear if you reclaim enough to be worth the re-write |
| `exclude_tools` | none | protect results that are context, not scratch (a retrieved policy document, the plan) |
| `clear_tool_inputs` | `false` | keeping the *call* visible while clearing the *result* preserves the trace of what was tried; set true only if the args are huge |

Three things to say about it in an interview. First, **the numbers**: on an internal agentic-search eval, context editing alone gave a **29%** performance improvement, memory tool plus context editing gave **39%**, and on a 100-turn web-search evaluation context editing cut token consumption **84%** while enabling runs that previously failed on context exhaustion. Second, **the direction of the effect**: 29 of those 39 points came from *removing* content, not adding recall — subtraction beats addition on long tool-heavy runs. Third, **the caveat**: that is an internal eval on a tool-result-heavy workload, which is exactly what the feature targets. A 6-turn chat with two tool calls will see none of it.

And the interaction that bites: **clearing invalidates the prompt cache** at the point of the clear, so you pay a cache write. If you clear 2k tokens on a 150k prefix every few turns you can spend more on cache re-writes than you saved. `clear_at_least` exists for exactly this, and picking it is arithmetic: clear only if `reclaimed_tokens × turns_until_next_clear × input_rate > prefix_tokens × cache_write_rate`.

### Subagents: isolation as a context strategy

The framing that matters here is **not** "multi-agent architecture" (that is `T07-multi-agent-topologies`, and mostly a trap). It is: *a subagent is a way to spend 50,000 tokens without putting 50,000 tokens in the main context.*

```
MAIN AGENT (context: plan + 1-2k summaries)
    │  spawn(task="find every caller of deprecated_fn across the repo",
    │        return_budget_tokens=1500, tools=[grep, read])
    ▼
  ┌────────────────────────────────────────────────────────┐
  │ SUBAGENT — fresh window, own system prompt              │
  │   grep → 400 hits → read 30 files → 47,000 tokens burnt │
  │   returns: 1,400 tokens of structured findings          │
  └────────────────────────────────────────────────────────┘
    │
    ▼  main context grew by 1.4k, not 47k  (~34x compression)
```

Anthropic's published figure is that a subagent "might explore extensively, using tens of thousands of tokens or more, but returns only a condensed, distilled summary of its work (often 1,000-2,000 tokens)". That ratio is the entire argument. The return contract is the part you engineer:

```python
SUBAGENT_RETURN_CONTRACT = """\
Return ONLY this structure. Hard budget: 1500 tokens. If you cannot fit,
return fewer findings with full detail rather than more findings truncated.

## Answer
Direct answer to the question you were given. 1-3 sentences.
## Evidence
Up to 8 items, each: file:line or url, plus the exact quoted span that matters.
## Confidence
high | medium | low, and what would change it.
## Not found / not checked
What you were unable to determine. Do not silently omit this.
"""
```

**When isolation is the right lever:** the subtask is *read-heavy and write-light* (search, exploration, verification), the intermediate volume is large, the useful output is small, and the subtasks are independent enough to run in parallel. Research and codebase exploration are the canonical fits, which is why Anthropic's Research feature is built this way and reported outperforming single-agent Opus 4 by 90.2% on research tasks.

**What it costs:** roughly 15x the tokens of a normal chat in Anthropic's reported system, plus the thing Cognition's "Don't Build Multi-Agents" is right about — **the distillation is lossy in a way you cannot inspect from the main agent.** If the subagent's 1,400-token summary omitted the one detail that mattered, the main agent has no way to know, and no way to ask for it without re-running the whole subtask. Two mitigations: make the subagent return *pointers* (file:line, URLs, stored query ids) alongside its conclusions, so the main agent can re-read on demand; and forbid subagents from making decisions, restricting them to gathering. Cognition's stronger version of this rule is worth memorising: **keep writes single-threaded; let extra agents contribute intelligence, not actions.**

### Progress files: durable memory that survives compaction

The insight is almost too simple: **state written to a file was never in the context window, so compaction cannot lose it.** Anthropic calls this structured note-taking; Claude Code does it with a to-do list; the Pokémon-playing agent maintains maps and tallies across thousands of steps and reads its own notes after context resets to continue multi-hour sequences.

```markdown
<!-- progress.md — the agent owns this file, the harness guarantees it is read -->
# Task
Migrate the billing service from Java 8 to Java 17. Success = tests green, no
behaviour change on the 14 golden invoices. HARD CONSTRAINT: do not touch
`LegacyTaxCalculator` (owned by another team, ticket BILL-4471).

# Done
- [x] 2026-07-26T09:14  Upgraded pom to 17, fixed 31 compile errors (commit a3f19c2)
- [x] 2026-07-26T09:48  Replaced `javax.*` → `jakarta.*` in 22 files (commit 7bd0e41)

# Open
- [ ] 4 tests failing in `InvoiceRoundingTest` — see Failed approaches
- [ ] Verify golden invoice #9 (the one with the credit note)

# Failed approaches
- Bumping jackson to 2.17 to fix rounding: made it WORSE (3 more failures). Reverted.
- `-Djava.locale.providers=COMPAT`: no effect. Do not retry.

# Verbatim values
BILL-4471 · commits a3f19c2, 7bd0e41 · golden invoices 1-14 · pom.xml:47
```

Three engineering requirements, and the third is the one people miss:

1. **Structure it.** The same schema as your compaction recap, so the two are interchangeable and a compaction can be seeded from the file.
2. **Append with timestamps, don't rewrite.** Rewriting reintroduces brevity bias — each rewrite is a summary of a summary. Additive, itemised updates are what the ACE line of work at ICLR 2026 argues for, and it matches what actually works.
3. **Guarantee the read.** An agent that *may* read the file often does not. Have the harness inject the file's contents (or a pointer plus the open-items section) into zone 2 every turn after a compaction, rather than trusting a prompt instruction. "Remember to check progress.md" is not a mechanism.

The bonus property is human observability: a progress file is a diffable, greppable artefact that a person can read during a long run, which is worth as much as the reliability gain.

### The counterintuitive core claim: more tokens makes agents worse

State it plainly, then defend it, because it is the sentence that signals you have actually operated these systems.

**More tokens in context degrades agent quality, monotonically past a fairly early point, on every model tested.** The three mechanisms are the ones above (n² dilution, training distribution, positional non-uniformity), and the empirical shape is Chroma's: 20-50% accuracy loss from 10k to 100k+ across 18 frontier models, with near-miss distractors doing more damage than length, and coherent input degrading attention *more* than shuffled input.

The corollaries you should draw, because this is where it becomes engineering rather than trivia:

- **"Just in case" context is negative-value.** Retrieving 20 documents when 3 are relevant does not hedge, it adds 17 distractors, and distractors are the highest-damage category. A relevance floor that sometimes returns nothing beats a fixed k.
- **A bigger window is not a fix, it is a deferral.** 1M-token windows going GA at standard pricing in March 2026 removed the cost argument and left the quality one untouched.
- **Subtraction is the highest-leverage operation available.** 29 of Anthropic's 39 points came from clearing, not from remembering.
- **The tool is usually the bug.** A tool returning 40k tokens per call is a bigger quality problem than any compaction strategy can fix downstream. Fix it at the boundary.
- **Fewer tools, better described.** A bloated tool set produces ambiguous selection; Anthropic's guidance is blunt about it — if a human engineer cannot say definitively which tool applies in a situation, the agent will not do better.

The falsifiable version, which is what you offer if challenged: run the same golden task set at 8k, 30k, 100k, and 200k of context by padding with plausible-but-irrelevant retrieved content, and plot task success. If success is flat or rising, the claim is wrong for your workload. In practice it falls, and the fall is steepest for tasks requiring precise retrieval from the middle.

---

## Build it from scratch

`(lab pending)` builds the whole stack against a scripted fake client, so it is deterministic and free:

1. **Token ledger.** Instrument a loop to emit per-zone token counts every turn. Reproduce the quadratic curve, then fix the tool and watch it flatten. Assert cumulative input tokens drop >60% with no change to the model or the task.
2. **The compactor above.** Implement `should_compact`, boundary snapping, and the protected block. Test: a 60-turn run where an account id appears once at turn 3 and the task is asked about at turn 58. Naive summarisation loses it; the protected block plus the verbatim-values section does not.
3. **Verification.** Implement `_verify` and deliberately give the fake summariser a lossy prompt. Assert the compaction is *rejected* rather than applied.
4. **Orphan test.** Attempt compaction mid tool-call and assert you get a valid message list, not a 400.
5. **Context editing simulation.** Implement client-side tool-result clearing with `trigger` / `keep` / `clear_at_least`, and compute the cache-cost break-even. Show a configuration where clearing costs more than it saves — that plot is the point of the exercise.
6. **Subagent.** A `spawn(task, tools, return_budget)` that runs a nested loop with a fresh window and enforces the return contract by rejecting over-budget returns. Measure the compression ratio on a search task; you should see 20-40x.
7. **Progress file.** Append-only, structured, injected into zone 2 after every compaction. Then the killer test: compact three times in one run and assert every open item and every identifier from turn 1 is still present and correct at turn 90.

Step 7 is the one to do if you only do one. "I have a test that compacts three times and asserts nothing load-bearing was lost" is a complete answer to the hardest question in this topic.

---

## How it's done in production

| Layer | What ships | What it adds | What it doesn't do |
|---|---|---|---|
| **Anthropic server-side compaction** (`compact_20260112`) | recommended default; runs on their side | no client code, correct token accounting | you don't control the summary prompt as directly |
| **Anthropic context editing** | `clear_tool_uses_20250919`, `clear_thinking_20251015`, beta header `context-management-2025-06-27` | free (no LLM call), server-side, client keeps full history | cache invalidation on clear; within-session only |
| **Anthropic memory tool** (`memory_20250818`) | file-based store you host; pairs with context editing so Claude is warned to save before a clear | cross-session persistence | you design the schema and write policy |
| **Anthropic SDK compaction** | `compaction_control` in `tool_runner`, default threshold 100,000 tokens | client-side control of the summary | **deprecated**; and it mis-counts tokens with server-side tools |
| **Claude Code `/compact`** | structured summary + the five most recently accessed files | a working reference implementation of the pattern | it is a product behaviour, not an API |
| **Google ADK compaction** | Python v1.16.0+, Java v0.2.0+, TS v0.6.0+ | framework-native | — |
| **LangGraph** | checkpointer + `trim_messages` / custom pre-model hook + `Store` | durable state, so compaction is resumable and inspectable | you still write the compaction policy |

**The server-side tool trap, because it is a real and specific bug.** Anthropic's own docs document it: with server-side tools like web search, a response may report `input_tokens: 63,000` and `cache_read_input_tokens: 270,000`, because cache reads accumulate across the tool's internal API calls. A client-side compactor that sums all four usage fields sees 334,400 and compacts prematurely and repeatedly. Symptom in a trace: compaction firing every second turn on a conversation that is obviously short. Fix: use the token-counting endpoint for true context length, or use server-side compaction, or exclude `cache_read_input_tokens` from your threshold when server tools are in play.

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| Agent forgets the task around turn 20 | Naive truncation dropped `messages[0]` | Never truncate the system message or the task; use a protected block |
| Agent reports success with work undone | Open-items list was inside the compacted region | Regenerate open items into zone 2 every turn; verify presence post-compaction |
| Agent retries an approach that already failed | Recap had no "Failed approaches" section | Add it to the schema; it is the highest-value section after Open items |
| Agent uses the wrong order id after turn 40 | Summariser dropped identifiers | Verbatim-values section + mechanical ID verification with retry |
| 400 `tool_result` without matching `tool_use` | Compaction boundary cut a tool pair | Boundary snapping; refuse to compact while a call is pending |
| Compaction fires every other turn on a short conversation | Token accounting counted accumulated `cache_read_input_tokens` from server-side tools | Use the token-counting endpoint; exclude cache reads from the threshold |
| Cost went *up* after enabling context editing | Each clear invalidates the cached prefix | Set `clear_at_least`; do the break-even arithmetic |
| Compaction call itself fails with a context error | Triggered too late (95%) with no headroom for the summary | Trigger at 55-65% of the window |
| Quality collapses in hour 2 of a long run | Recursive summarisation, brevity bias compounding | Additive itemised progress file as the source of truth; cap compactions per run and alert |
| Agent ignored a hard constraint at turn 70 | Governance decay: the constraint was summarised away | Constraints live in zone 2, regenerated; add an assertion test for constraint survival |
| Subagent's answer is subtly wrong and unarguable | Lossy distillation with no pointers | Require file:line / URL evidence and a "not checked" section; let the main agent re-read |
| Retrieval quality dropped after raising k from 5 to 20 | Distractor damage exceeds recall gain | Relevance floor; returning nothing is a valid result |

---

## Tradeoffs & when NOT to use it

- **Do not compact a task that needs precise recall of early detail.** Anthropic's own docs list this as a poor fit. Legal review, reconciliation, forensic analysis of a long transcript — if the answer depends on the exact wording of turn 4, a summary is a lossy channel and you should either keep it verbatim, chunk the task, or externalise to files and re-read.
- **Do not compact short runs.** Under ~30% of the window, compaction adds an LLM call, latency, and a chance of loss for no benefit. The cheapest context strategy is a task that finishes in six turns.
- **Do not run client-side compaction alongside heavy server-side tools** until you have fixed token accounting, or you will compact prematurely and constantly.
- **Do not reach for subagents to fix a context problem you could fix at the tool.** If one tool returns 40k tokens, truncating it is free and lossless-where-it-matters; a subagent is an extra model call, extra latency, and a lossy handoff. Order of operations: fix the tool, then clear, then compact, then isolate.
- **Do not use subagents for anything that writes.** Isolation destroys the shared context that makes conflicting writes detectable. Keep writes single-threaded.
- **Context editing is not memory.** It is within-session deletion. If the requirement is "remember across sessions", that is `T07-agent-memory` and no amount of clearing helps.
- **A bigger window is occasionally the right answer.** If the task genuinely needs 300k tokens of a single coherent document in one pass, and the alternative is a chunking scheme that breaks cross-references, use the long window and accept the degradation. Now that 1M is priced at standard rates, the decision is about quality, not cost. Just do not pretend the degradation isn't there.
- **The honest counter-argument to all of this:** every year, curation that was necessary becomes unnecessary as models improve, and Anthropic's own advice trends toward "do the simplest thing that works" and letting capable models act with less human curation. So build the levers as *policy you can turn down*, not as architecture you cannot remove. A compactor with a configurable trigger ages well; a hand-tuned context pipeline with hardcoded heuristics does not.

---

## Interview questions

### Q1 — What is context engineering and how is it different from prompt engineering?
**Testing:** whether you have the current vocabulary and the reason behind it.
**Answer:** Prompt engineering is authoring a fixed set of instructions once. Context engineering is deciding, on every single turn of a loop, which tokens occupy a finite attention budget — system prompt, tool schemas, tool results, retrieved documents, message history, thinking blocks. The difference is that in an agent most of the context is *generated*, not authored: tool results and prior assistant turns are the bulk, and nobody wrote them. The objective is Anthropic's formulation: the smallest set of high-signal tokens that maximises the likelihood of the desired outcome.
**Follow-up trap:** *"Why is it a budget rather than a buffer?"* — because returns diminish. A transformer computes n² pairwise relationships for n tokens, so attention mass per relationship thins as context grows; models saw mostly short sequences in training so have fewer parameters specialised for context-wide dependencies; and position-encoding interpolation trades positional precision for length. The observable result is a performance gradient: Chroma measured 20-50% accuracy loss between 10k and 100k+ tokens across 18 frontier models. Every added token costs you some accuracy on everything else.

### Q2 — Why not just use a 1M-token window?
**Answer:** Because capacity and quality are different curves. 1M windows went GA at standard per-token pricing in March 2026, so the cost objection is largely gone, but the quality objection isn't: accuracy on retrieval and long-range reasoning degrades on a gradient far below the limit, and the damage is driven at least as much by *distractors* as by length. A 200k prompt with 40 marginally-relevant retrieved documents is worse than a 30k prompt with the 3 that matter — you did not hedge, you added 37 near-misses, and Chroma's data says near-misses are the worst category. Also, cost is quadratic in turns because the prefix re-sends every turn: 6k prefix plus 4k growth per turn over 40 turns is ~3.4M input tokens for one run.
**Follow-up trap:** *"So long context is useless?"* — no. It is the right tool when the task genuinely needs one coherent large artefact in a single pass and chunking would break cross-references. What it is not is a substitute for curation in a *loop*, because in a loop the context grows without bound regardless of how big the ceiling is.

### Q3 — Implement compaction.
**Testing:** whether you have written this or only read about it.
**Answer:** Trigger on token count at ~60% of the window, not 95%, because the compaction call itself needs headroom. Refuse to compact while a tool call is pending. Split into a protected head, a compactable middle, and a verbatim tail of the last ~6 turns, snapping the boundary forward so a `tool_result` never becomes an orphan. Summarise the middle with a *schema*, not a free-text instruction: Task, State, Discoveries, Failed approaches, Open items, Verbatim values. Then verify mechanically — regex every identifier-shaped token out of the source region and assert each appears in the recap, and assert every open item survived; retry once naming the omissions, and if it fails again *do not compact*. Reassemble as system, protected block, `<progress_so_far>`, tail. Count compactions and alert above ~4 in one run.
**Follow-up trap:** *"What must never be compacted?"* — the task and success criteria, hard constraints and prohibitions, open obligations, identifiers and exact values, the user's most recent correction, any pending tool call, and approval/permission state. And the mechanism matters: they are *regenerated from durable state into a protected block* each turn, so the summariser never sees them. Telling the summariser to be careful is not a control.

### Q4 — Anthropic reports 29% from context editing and 84% fewer tokens. What are those numbers and what do they mean?
**Answer:** On an internal agentic-search eval, context editing alone improved performance 29% over baseline; the memory tool plus context editing gave 39%. Separately, on a 100-turn web-search evaluation, context editing cut token consumption by 84% while enabling workflows that previously failed outright on context exhaustion. Two readings. First, it is not a quality-for-cost trade — both moved the right way. Second and more interesting: 29 of the 39 points came from *removing* stale tool results, not from adding recall, which is the strongest published evidence for "subtraction beats addition" on long tool-heavy runs.
**Follow-up trap:** *"Would you expect 29% on your workload?"* — no, and saying so is the point. That is an internal eval on a tool-result-heavy agentic search task, which is precisely what the feature targets. A six-turn support chat with two tool calls has almost no stale tool results to clear and will see nothing. The number tells you the *shape* of the win, not its magnitude for you.

### Q5 — How does context editing interact with prompt caching?
**Testing:** whether you have actually run this and looked at the bill.
**Answer:** Badly, if you are careless. Clearing tool results mutates the prefix, which invalidates the cached prompt from the point of the clear, so you pay a cache write on the next request. Cache reads run at roughly 0.1x the base input rate, so a large stable prefix is nearly free — and repeatedly clearing small amounts destroys that. That is what `clear_at_least` is for: only apply the strategy if it reclaims at least N tokens. The break-even is arithmetic: clear only if `reclaimed × turns_until_next_clear × input_rate > prefix_tokens × cache_write_rate`. Thinking-block clearing behaves differently — keeping thinking blocks preserves the cache, clearing them invalidates from the clear point, which is why the `keep` default varies by model tier and why you should set it explicitly if your code runs across tiers.
**Follow-up trap:** *"Give me a config where enabling context editing makes things worse."* — a 150k stable prefix with a small trigger and no `clear_at_least`, clearing ~2k every couple of turns. You reclaim almost nothing and pay a full cache write repeatedly. Cost goes up, quality is unchanged.

### Q6 — Compaction ate something important and the agent gave a wrong answer. Debug it.
**Answer:** First, this must be reconstructible: I need the pre-compaction message list, the recap, and the post-compaction list in the trace, plus which compaction index this was. Without those three artefacts, the incident is unfalsifiable. With them: diff the identifiers in the source region against the recap — that usually finds it immediately. Then classify. If an identifier vanished, the fix is the verbatim-values section plus mechanical verification. If an open item vanished, the fix is regenerating open items into the protected block rather than trusting the summary. If a constraint vanished, that is governance decay and it is a security bug, not a quality bug — constraints belong in the protected block with an assertion test. If it happened on the third compaction of the run, the real bug is per-turn growth causing recursive summarisation, and the fix is upstream at the tool.
**Follow-up trap:** *"How do you prevent it in CI?"* — a compaction survival test. Golden run with an identifier at turn 3, a hard constraint at turn 1, and an open item created at turn 10; force three compactions; assert all three are present and exact at turn 90. It is a cheap deterministic test against a scripted model and it catches the entire class.

### Q7 — When do you use a subagent instead of compacting?
**Answer:** When the subtask is read-heavy and write-light, its intermediate volume is large, its useful output is small, and it is independent enough to run in parallel. Search, exploration, and verification fit; the pattern is that a subagent burns tens of thousands of tokens in its own fresh window and returns 1,000-2,000 tokens of distilled findings, so the main context grows by 1.4k instead of 47k. Anthropic's Research system is built this way and reported beating single-agent Opus 4 by 90.2% on research tasks, at roughly 15x the tokens. Compaction is the better lever when the task needs continuous back-and-forth and conversational coherence.
**Follow-up trap:** *"What does the isolation cost you?"* — an unauditable lossy handoff. If the subagent's summary omitted the thing that mattered, the main agent cannot tell and cannot ask without re-running the whole subtask. Cognition's "Don't Build Multi-Agents" is right about that. Mitigations: require the return contract to include *pointers* (file:line, URL, stored query id) so the main agent can re-read on demand, require an explicit "not found / not checked" section, and forbid subagents from taking actions — keep writes single-threaded and let extra agents contribute intelligence, not actions.

### Q8 — What is a progress file and why does it beat compaction?
**Answer:** A structured, append-only markdown file the agent writes and re-reads: Task, Done with timestamps and commits, Open items, Failed approaches, Verbatim values. It beats compaction on the one axis that matters — **it was never in the context window, so compaction cannot lose it.** It also gives you human observability during a long run, which is worth as much as the reliability gain. Anthropic calls it structured note-taking; the Pokémon-playing agent uses it to maintain tallies and maps across thousands of steps and resumes multi-hour sequences after context resets by reading its own notes.
**Follow-up trap:** *"The agent stopped reading it. Now what?"* — that is the actual failure mode, and it means your design relied on a prompt instruction where it needed a mechanism. The harness must inject the file's open-items section into the protected block every turn after a compaction, unconditionally. Second-order: append with timestamps rather than rewriting, because each rewrite is a summary of a summary and reintroduces the brevity bias you built the file to escape.

### Q9 — Your agent's cost is 4x the estimate. Walk me through the diagnosis.
**Answer:** Get the per-zone token ledger first; guessing here is how people spend a week on the wrong thing. The usual distribution: tool results dominate the prefix, and the prefix re-sends every turn so cost is quadratic in turns. Concretely, 6k prefix plus 4k of growth per turn over 40 turns is ~3.36M input tokens; cut growth to 1k and it is ~1.02M for the identical task. So: (1) truncate tool results at the tool boundary — free, biggest lever; (2) verify the stable prefix is actually stable and cached, since cache reads are ~0.1x; (3) enable tool-result clearing with a sensible `clear_at_least`; (4) compact at 60%; (5) route the summarisation call to a cheaper model; (6) only then consider subagents or a smaller model for the main loop.
**Follow-up trap:** *"Which of those also improves quality?"* — the first four, and that is the interesting part. Truncating and clearing reduce distractors, and distractor damage is the largest term in context rot. Cost and quality move together here, which is unusual and worth saying, because most optimisation is a trade and this one isn't.

### Q10 — What is "lost in the middle" and what do you do about it?
**Answer:** Liu et al. (2023) found a U-shaped positional accuracy curve: content at the beginning and end of a long context is recalled well, content in the middle is recalled worst. Operationally: put the stable prefix and the hard constraints at the top, put the current instruction and the specific question at the bottom, and never bury a load-bearing constraint in the middle of a long block of retrieved text. The stronger 2025 finding from Chroma is that position is not the only axis — needle-question semantic similarity and the presence of near-miss distractors matter more than length in many cases, and coherent structured input degrades attention *more* than shuffled input, which invalidates the intuition that "it reads nicely, so it's fine."
**Follow-up trap:** *"Doesn't a 1M window with better training fix this?"* — it moves the curve, it does not remove it. Chroma tested 18 frontier models and the degradation appears in all of them, gently in some. The architectural cause (n² relationships, thin attention mass per relationship) does not disappear with scale, and the training-distribution cause only shrinks as long-sequence data becomes proportionally common, which it has not.

### Q11 — Server-side or client-side compaction?
**Answer:** Server-side by default now. Anthropic's docs explicitly recommend server-side compaction (`compact_20260112`) and have deprecated the client-side `compaction_control` in the SDKs, and the reasons are good: less integration code, correct token accounting, and — the underrated property — context editing applies server-side *before* the prompt reaches the model, so your client keeps the full unmodified history and your logs stay complete. Client-side is worth it only when you need domain-specific control over what survives: a schema with a `Verbatim values` section for a financial workflow, or a protected block driven by your own state model. And if you go client-side you own the whole bug surface: orphaned tool pairs, premature triggers, recursive summarisation.
**Follow-up trap:** *"Name the specific bug in client-side compaction with server-side tools."* — token miscounting. With web search, `cache_read_input_tokens` accumulates across the tool's internal calls, so a response can show 63k input and 270k cache reads. A client summing all usage fields sees 334k and compacts a conversation whose real context is 63k. Symptom: compaction firing every other turn on an obviously short conversation. Fix: the token-counting endpoint, or exclude cache reads from the threshold, or move to server-side.

### Q12 — Defend the claim that more tokens makes agents worse.
**Testing:** the thesis of the module, and whether you can be specific rather than aphoristic.
**Answer:** Three mechanisms and one measurement. Mechanisms: n² pairwise attention means per-relationship attention mass thins as n grows; training distributions are dominated by short sequences so there are fewer parameters specialised for context-wide dependencies; position-encoding interpolation buys length at the cost of positional precision. Measurement: 20-50% accuracy loss from 10k to 100k+ tokens across 18 frontier models, with distractor presence and needle-question dissimilarity driving more of the damage than raw length. The engineering corollary is that "just in case" retrieval is negative-value — pulling 20 documents when 3 are relevant adds 17 near-misses, which is the highest-damage category — and that subtraction is the highest-leverage operation available, which is exactly what Anthropic's 29-of-39 points from clearing shows.
**Follow-up trap:** *"How would you falsify it?"* — pad the same golden task set with plausible-but-irrelevant retrieved content to 8k / 30k / 100k / 200k and plot task success. If success is flat or rising, the claim is wrong for that workload and I would change my design. In practice it falls, steepest on tasks needing precise retrieval from the middle. Being able to name the experiment is the difference between holding a belief and repeating a slogan.

### Q13 — Design the context strategy for a 3-hour codebase migration agent.
**Answer:** Layered. Zone 1: stable, cached system prompt plus a deliberately small tool set (glob, grep, read, edit, run_tests) — bloated tool sets cause ambiguous selection. Zone 2: protected block regenerated each turn from a `progress.md` — task, success criteria, the hard "do not touch X" constraint, open items, verbatim values (commits, ticket ids, file paths). Zone 3: `<progress_so_far>` from the last compaction. Zone 4: last ~6 turns verbatim, with every tool truncating output at the boundary (grep returns counts and file:line, not file bodies; test output returns failures only). Levers: just-in-time retrieval rather than pre-loading the repo — keep lightweight identifiers and read on demand; tool-result clearing with `keep: 5` and `exclude_tools` protecting the plan document; compaction at 60% with the six-section schema and mechanical ID verification; subagents for read-only exploration ("find every caller of X") returning 1.5k with file:line pointers. Progress file appended after every meaningful step. Never let a subagent write.
**Follow-up trap:** *"Three hours means many compactions. How do you stop quality collapsing?"* — make the progress file, not the recap chain, the source of truth. Each compaction seeds from the *file*, so summaries are never summaries-of-summaries; that is the brevity-bias collapse and it is what recursive compaction does. Cap compactions per run and alert past ~4, because more than that means per-turn growth is the real bug. And run the survival test in CI: three forced compactions, assert the constraint, the open items, and every identifier from turn 1 are intact.

### Q14 — What do you protect and how, specifically?
**Answer:** Seven things: the task and success criteria; hard constraints and prohibitions; open obligations; identifiers and exact values; the user's most recent correction; any pending tool call; and approval/permission state. The *how* is the answer that matters: they are regenerated from durable state into a protected block outside the compactable region, so the summariser physically cannot see them. Plus a `Verbatim values` section in the recap schema as a second line of defence, plus mechanical verification that every identifier-shaped token from the compacted region survived, with a retry and a refusal-to-compact if it fails twice.
**Follow-up trap:** *"Why is the constraint list a security control?"* — because compaction silently erasing "read-only on prod" or "never contact the customer directly" turns a quality issue into an unauthorised action, and 2026 work on governance decay documents exactly this happening across long-horizon runs. It fails silently: nothing errors, the agent simply stops being constrained. That means it needs an assertion test, not a code review.

### Q15 — You have one week. What is the highest-value context work you can do?
**Testing:** prioritisation, which is what separates staff from senior here.
**Answer:** Day 1: instrument the per-zone token ledger, because everything after is guessing without it. Days 2-3: fix the two worst tools — whichever return the most tokens per call — to return summaries plus pointers. That is free, lossless where it matters, and improves both cost and quality because it removes distractors. Day 4: turn on tool-result clearing with a `clear_at_least` sized from the cache arithmetic. Day 5: the protected block plus a progress file, and the compaction survival test in CI. I would *not* spend the week building a subagent architecture or tuning a summariser prompt; those are lower leverage than the tool boundary and much higher risk.
**Follow-up trap:** *"Your CTO wants the multi-agent version."* — I'd show the ledger: if tool results are 78% of the prefix, decomposition into agents does not remove those tokens, it moves them and adds handoff loss plus latency plus cost. Subagents are the right lever specifically when a read-heavy subtask has large intermediate volume and small output. If that shape exists in our workload, I will build it and measure the compression ratio. If it doesn't, the multi-agent version is a more expensive way to have the same problem.

---

## Red flags that fail you

- Treating context as a capacity problem: "we moved to a bigger window" as a quality fix.
- Not knowing that quality degrades before the hard limit, or thinking it is a cliff rather than a gradient.
- Compacting with a free-text "summarise this" instruction and no schema, no protected region, and no verification.
- No answer for what must never be compacted, or answering "we tell the summariser to keep the important stuff".
- Triggering compaction at 90-95% of the window.
- Not knowing that clearing invalidates the prompt cache.
- Reaching for subagents before fixing the tool that returns 40k tokens per call.
- Letting subagents write, or perform actions, rather than gather.
- Believing retrieving more documents is a safe hedge.
- Quoting 29% or 84% as universal numbers without naming the eval they came from.
- No trace of the pre- and post-compaction context, making every compaction incident unfalsifiable.

## Cheat card

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

## Sources

- [Anthropic — Effective context engineering for AI agents](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) — attention budget, n² framing, compaction/note-taking/subagent trio, the 1,000-2,000 token subagent return figure, Claude Code's five-most-recent-files behaviour; published 2025-09-29, accessed 2026-07-26
- [Anthropic — Managing context on the Claude Developer Platform](https://claude.com/blog/context-management) — the 29% / 39% / 84% figures; published 2025-09-29, accessed 2026-07-26
- [Claude Platform docs — Context editing](https://platform.claude.com/docs/en/build-with-claude/context-editing) — `clear_tool_uses_20250919` and `clear_thinking_20251015` parameters and defaults, beta header, cache interaction, server-side compaction `compact_20260112`, SDK compaction deprecation, the server-side-tool token miscounting trap; accessed 2026-07-26
- [Chroma — Context Rot: How Increasing Input Tokens Impacts LLM Performance](https://www.trychroma.com/research/context-rot) — 18 frontier models, distractor and structure effects; accessed 2026-07-26
- [Lost in the Middle: How Language Models Use Long Contexts](https://arxiv.org/abs/2307.03172) — Liu et al., 2023; the U-shaped positional curve; accessed 2026-07-26
- [Anthropic — How we built our multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) — orchestrator/subagent design, 90.2% improvement, ~15x token usage; accessed 2026-07-26
- [Cognition — Don't Build Multi-Agents](https://cognition.com/blog/dont-build-multi-agents) — single-threaded linear agents, dedicated compression model, handoff loss; June 2025, accessed 2026-07-26
- [Governance Decay: How Context Compaction Silently Erases Safety Constraints in Long-Horizon LLM Agents](https://arxiv.org/abs/2606.22528) — compaction as a safety surface; accessed 2026-07-26
- [Attention Is All You Need](https://arxiv.org/abs/1706.03762) — the n² attention structure being reasoned about; accessed 2026-07-26

## Changelog
- 2026-07-26 — created
