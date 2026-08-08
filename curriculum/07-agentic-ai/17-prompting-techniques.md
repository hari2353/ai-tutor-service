# Zero-Shot, Few-Shot, CoT, Self-Consistency: What Actually Moves Accuracy

> **Track:** T07 Agentic AI · **Time:** 2.0h · **Prereqs:** none · **Updated:** 2026-08-01
> **Module id:** `T07-prompting-techniques` · **Tags:** prompting,critical

## The 30-second version

Zero-shot asks the model to do a task cold; few-shot shows it 2-5 worked examples, and what those examples actually teach is the output format and label space far more than the underlying task itself — a model that already "knows" sentiment analysis mostly needs few-shot examples to learn you want `positive/negative/neutral` as exact strings, not a paragraph. Chain-of-thought prompting (Wei et al., 2022) improves accuracy on multi-step reasoning tasks, but the original finding included a load-bearing caveat everyone forgets to mention: the benefit only appears above a model-scale threshold — small models get no lift or get worse, because CoT requires the underlying capability to reason step-by-step, not just the instruction to try. The current, sharper caveat: reasoning-trained models (o-series, Claude's extended thinking, DeepSeek-R1, Gemini's deep-think modes) already do internal step-by-step reasoning before answering, so bolting an explicit "think step by step" instruction on top is redundant at best and can measurably hurt at worst by fighting the model's own trained reasoning process. Self-consistency (sample N reasoning paths, take the majority answer) buys real accuracy on hard problems but costs N times the tokens, and the honest, unglamorous finding after three years of production use is that a good eval set, solid retrieval, and structured output constraints move accuracy more reliably than any prompt-wording trick — most prompt-engineering folklore does not survive being measured against a real benchmark.

## Why this gets asked

The interviewer has watched a team spend two weeks iterating on prompt wording — reordering examples, trying five different phrasings of "think carefully" — while the actual bottleneck was that their retrieval was returning irrelevant context or their eval set had ten examples and no statistical power to tell a real improvement from noise. They want to know if you'll default to that trap, or if you know which of these techniques have real, measured effect sizes and which are folklore that stopped mattering once reasoning models shipped. They're also checking whether you know that "add more chain-of-thought" is now sometimes the wrong answer, which is a distinctly 2025-2026 piece of knowledge that separates people with current experience from people reciting a 2023 blog post.

---

## Lineage: past → present → future

**What came before.** Pre-2020, getting a language model to do a new task meant fine-tuning it on labeled examples for that specific task — there was no notion of "just ask it in the prompt." GPT-3 (Brown et al., 2020) demonstrated in-context learning: a sufficiently large model could perform a new task from a handful of examples placed directly in the prompt, with no gradient update at all. This was the pain point it solved — task-specific fine-tuning required labeled data and a training pipeline per task; in-context learning needed neither, just a well-constructed prompt. Zero-shot and few-shot prompting are the direct descendants of that discovery: zero-shot relies purely on the pretrained model's ability to follow an instruction, few-shot adds demonstrations to disambiguate exactly what "doing the task" should look like in output form.

**Where it stands now.** Chain-of-thought (Wei et al., 2022) was the next major finding: prompting a model to produce intermediate reasoning steps before its final answer substantially improves accuracy on arithmetic, commonsense, and symbolic reasoning tasks — but the paper's own results showed this benefit is an **emergent capability that only appears above a certain model scale**; smaller models see flat or negative results from CoT prompting, because generating a plausible-looking reasoning chain that doesn't actually help requires the underlying step-by-step reasoning capacity CoT prompting merely elicits, not creates. Self-consistency (Wang et al., 2022) extended CoT by sampling multiple independent reasoning paths and taking the majority-vote answer, buying meaningful accuracy — +17.9 points on GSM8K, +11.0 on SVAMP, +12.2 on AQuA with PaLM-540B [Self-Consistency Improves Chain of Thought Reasoning](https://www.researchgate.net/publication/359390115_Self-Consistency_Improves_Chain_of_Thought_Reasoning_in_Language_Models) — accessed 2026-08-01 — at the direct cost of N times the inference tokens. The live, current disagreement is what CoT even means once models are trained to reason internally: OpenAI's o-series, Anthropic's extended-thinking Claude models, DeepSeek-R1, and Gemini's deep-think modes are trained via reinforcement learning to produce their own internal reasoning trace before answering, which is architecturally a trained behavior, not a prompted one — CoT prompting on top of these models is frequently unnecessary, and multiple practitioner reports and a growing set of benchmarks show it can measurably *reduce* accuracy by disrupting a reasoning process the model already runs more effectively on its own [Chain of Thought Prompting in 2026](https://futureagi.com/blog/chain-of-thought-prompting-ai-2025/) — accessed 2026-08-01. Self-consistency itself is showing diminishing returns as base models get better at reasoning without needing the ensemble crutch — a late-2025 analysis found self-consistency's accuracy gains plateauing and its cost-effectiveness declining sharply as per-query resource constraints tighten, arguing it should be reserved for genuinely hard problems rather than applied as a default scaling knob [Self-Consistency Is Losing Its Edge](https://arxiv.org/html/2511.00751v2) — accessed 2026-08-01.

**Where it's heading.** High confidence: the field keeps moving reasoning capability from the prompt into the model's trained behavior — explicit prompt-engineering for reasoning becomes less relevant over time as more deployed models are reasoning-native by default, mirroring how native tool calling made ReAct's original text-parsing scaffold obsolete (`T07-agent-loop-from-scratch`). Moderate confidence: prompt engineering as a discipline is narrowing to a smaller, more durable core — task framing, output-format constraints, and example curation for format/label-space teaching — while the more speculative, folklore-heavy techniques (specific magic phrases, elaborate persona prompts, threats or incentives to the model) continue failing to show reproducible effects under rigorous measurement, and get abandoned as eval culture matures across the industry. Speculative but worth flagging: whether self-consistency and similar test-time-compute-scaling techniques remain useful at all as reasoning models' single-pass accuracy keeps improving, or whether they collapse into a niche for the hardest remaining problems only — the 2025 evidence already points this direction but it isn't settled.

---

## Mental model

```
ZERO-SHOT           "Classify this review: <text>"
                     relies entirely on pretrained instruction-following

FEW-SHOT             "Review: X -> positive
                       Review: Y -> negative
                       Review: <text> -> ?"
                     teaches FORMAT and LABEL SPACE more than the task itself
                     (the model likely already 'knows' sentiment; it needed to learn
                      you want the literal string "positive", not a paragraph)

CHAIN-OF-THOUGHT     "<text>. Let's think step by step."
                     elicits an intermediate reasoning trace before the final answer
                     ONLY HELPS if the model has the underlying reasoning capacity —
                     below a scale/capability threshold, it adds tokens, not accuracy

SELF-CONSISTENCY     sample N independent CoT traces -> majority vote on final answer
                     buys accuracy on genuinely hard problems, costs N x the tokens
                     gains plateau (sometimes decline) at high N — not a free scaling knob

REASONING MODELS     the model ALREADY does step-by-step reasoning internally,
(o-series, Claude    trained via RL, before you ever add "think step by step"
 extended thinking,  -> explicit CoT prompting is often redundant
 DeepSeek-R1,         -> can measurably HURT by fighting the model's own trained process
 Gemini deep-think)

WHAT ACTUALLY MOVES ACCURACY IN PRODUCTION (the honest ranking)
  1. eval set quality           (can you even tell if a change helped?)
  2. retrieval / context quality (garbage in, garbage out — no prompt fixes bad context)
  3. structured output constraints (schema-enforced generation beats hoping for format)
  4. prompt wording              (real, but smaller and more fragile than folklore claims)
```

---

## How it actually works

### Zero-shot vs few-shot: what few-shot actually teaches

Zero-shot prompting gives the model a task description alone and relies on the pretrained model's instruction-following and world knowledge to produce a correct answer with no worked examples. Few-shot prompting adds 1-N demonstrations of (input, correct output) pairs before the actual query. The common misconception is that few-shot examples primarily teach the model *how to solve* the task; in practice, for tasks a model already has strong pretrained competence at (sentiment, basic classification, common extraction patterns), few-shot examples are doing far more work teaching:

1. **Output format** — exact label strings, JSON key names, whether to include explanation or just the answer.
2. **Label space** — which categories exist and their exact spelling/casing, disambiguating a task description that might otherwise admit multiple reasonable label sets.
3. **Granularity and length** — how detailed an answer should be, calibrated by the examples' own length.

This matters practically: if your task's ambiguity is really about *output shape*, a small number of format-clarifying examples fixes it cheaply; if the ambiguity is genuinely about task difficulty (the model doesn't actually know how to do the task), no number of examples fixes that, and you need a better model, retrieval augmentation, or fine-tuning instead.

### How many shots before returns flatten

The pattern replicated across multiple studies: the first few examples improve accuracy sharply, additional examples yield smaller boosts, and returns typically plateau by 4-5 examples for most classification-style tasks — one measured case found five few-shot examples lifting a GPT-4o classification task from 84.5% to 91.5%, a 7-point jump over zero-shot [Few Shot Prompting guide, 2026](https://phrasly.ai/blog/few-shot-prompting/) — accessed 2026-08-01. Beyond roughly 5 examples for typical tasks, added examples can introduce noise or conflicting patterns rather than continued lift, and the marginal example is competing for context budget against other useful content (retrieved documents, system instructions) rather than reliably buying more accuracy. Some many-shot regimes (dozens to hundreds of examples, feasible only with very long context windows) show plateaus much later, around 50-70 shots per class for certain tasks — but this is a different, more specialized regime than the standard few-shot pattern, and the marginal cost in tokens at that scale is substantial [Test-Time Adaptation via Many-Shot Prompting](https://arxiv.org/html/2603.05829) — accessed 2026-08-01.

### Example selection and ordering effects

Which examples you pick and what order you put them in changes accuracy on the same task with the same model — this is a real, measured, and under-appreciated effect. **Selection**: examples that are semantically similar to the actual query (retrieved dynamically per-query, rather than a fixed static set) generally outperform a fixed few-shot set, because they demonstrate the specific decision boundary relevant to this input rather than a generic one. **Ordering**: models show measurable **recency bias** — examples placed closer to the actual query (typically the last few in the prompt) have disproportionate influence on the output relative to examples placed earlier, which means a single unusual or mislabeled example placed last can skew results more than the same example placed first. The practical mitigation: if using a fixed few-shot set, put your most representative, highest-quality example last, and if selection is dynamic, retrieve and re-rank the K nearest examples per query rather than reusing a static prompt across all inputs.

### Chain-of-thought: the original finding, and the threshold

Wei et al. (2022) showed that prompting a model to produce reasoning steps ("A chain of thought is a series of intermediate reasoning steps...") before its final answer substantially improved performance on arithmetic, symbolic, and commonsense reasoning benchmarks. The finding that gets dropped in casual retellings: **this benefit is an emergent property of model scale**. In the original experiments, small models saw flat or even negative effects from CoT prompting — they'd produce reasoning-shaped text that didn't actually track toward a correct answer, sometimes worse than a direct answer would have been, because generating a genuinely useful reasoning chain requires the underlying multi-step reasoning capacity that CoT prompting elicits and structures, but does not itself create. This is the correct, precise answer to "does CoT always help": no, and the scale threshold is the reason why, not a vague "it depends."

**Zero-shot CoT.** Kojima et al. (2022) showed you don't need worked examples at all — simply appending "Let's think step by step" to a zero-shot prompt recovers much of few-shot CoT's benefit, because the instruction alone is often sufficient to elicit the reasoning-trace behavior in models that have the underlying capacity, without the token cost of curating and including full worked examples.

### The current, sharper caveat: reasoning models and explicit CoT

This is the part of the topic that dates a candidate's knowledge. Reasoning-trained models — OpenAI's o-series, Anthropic's extended-thinking Claude models, DeepSeek-R1, Gemini's deep-think modes — are trained via reinforcement learning specifically to produce an internal, extended reasoning trace before emitting a final answer. This is a **trained model behavior**, architecturally baked in via the RL objective, not a prompted behavior you elicit with clever wording. The consequence: telling one of these models "think step by step" is frequently redundant, since it's already doing that by default, and in a growing number of measured cases it actively **hurts** — forcing an externally-specified reasoning format can interrupt or constrain a reasoning process the model has learned to run more effectively on its own terms [Chain of Thought Prompting in 2026: GPT-5 + Claude 4.7](https://futureagi.com/blog/chain-of-thought-prompting-ai-2025/) — accessed 2026-08-01. The honest, current framing: CoT prompting is still genuinely useful for non-reasoning models, or for reasoning models where you specifically want to *steer* or *constrain the shape of* the visible reasoning (e.g., forcing it to check a specific list of edge cases), but "always append 'think step by step'" is 2023-era advice that can now cost you accuracy on a 2026 reasoning model. There's also a separate, unresolved concern worth naming if asked: CoT faithfulness — a reasoning-native model's visible chain of thought does not always reflect its actual internal decision process, so treating a visible CoT trace as a reliable explanation (rather than merely a helpful scaffold) is its own trap.

### Self-consistency: the mechanism and its cost multiplier

Instead of taking a single CoT completion, sample N independent completions (typically at nonzero temperature to get genuine diversity, not N copies of the same greedy output), extract the final answer from each, and take the majority vote. This works because independent reasoning errors are less likely to be correlated than the reasoning process itself is likely to converge on the correct answer when it's actually right — wrong answers tend to be idiosyncratic to a specific flawed path, while correct answers tend to be reached by multiple different valid paths converging on the same result.

**The numbers.** On GSM8K with PaLM-540B, standard CoT reached 56.5% accuracy; self-consistency with N=40 samples reached 74.4%, an 18-point gain [Self-Consistency Prompting: Get 17.9% Better Reasoning Accuracy](https://www.adaline.ai/blog/what-is-self-consistency-prompting) — accessed 2026-08-01. That gain is real and large — but it comes at **N times the token cost and N times the latency** (or N times the parallel compute, if you fan the requests out concurrently), and more recent analysis finds these gains plateauing and sometimes declining at very high sample counts on problems the model was already solving correctly, since additional samples on an easy problem just add sampling noise rather than correcting genuine errors [Self-Consistency Is Losing Its Edge](https://arxiv.org/html/2511.00751v2) — accessed 2026-08-01. The practical rule: reserve self-consistency for genuinely hard problems where single-pass accuracy is measurably poor, not as a default multiplier applied to every request — applying it uniformly multiplies your inference bill for accuracy gains concentrated on a small subset of your traffic.

### ReAct, least-to-most, step-back — briefly, with pointers

- **ReAct** (Yao et al., 2022) interleaves reasoning traces with tool-executed actions so the model can think, act, observe the result, and think again — this is agent-harness territory, fully covered in `T07-agent-loop-from-scratch` and `T07-react-pattern-raw`; don't re-derive it here.
- **Least-to-most prompting** (Zhou et al., 2022) decomposes a hard problem into an explicit sequence of simpler subproblems, solving each in order and feeding prior answers forward — useful when a problem has genuine compositional structure (e.g., a multi-hop question) that a single CoT pass tends to skip steps on.
- **Step-back prompting** (Zheng et al., 2023) has the model first answer a more general, abstracted version of the question ("what physical principle governs this?") before answering the specific question, which can surface relevant background knowledge the model would otherwise fail to retrieve when jumping straight to the specific case.

Both are real, measured techniques for specific problem shapes (compositional and knowledge-grounding gaps respectively) rather than general-purpose accuracy boosters — know they exist and what shape of failure each addresses, rather than treating them as always-apply tricks.

### The honest part: what actually moves accuracy in production

This is the senior signal for the whole module, and it is the least glamorous section. Across production LLM systems, the interventions that reliably move measured accuracy, ranked by how consistently teams report real gains:

1. **A good eval set.** Without a representative eval set with enough examples to distinguish real improvement from noise, you cannot tell whether a prompt change helped, hurt, or did nothing — teams routinely ship a "prompt improvement" that was actually noise from a 10-example manual spot-check.
2. **Retrieval quality**, for any RAG-backed system. No prompt wording compensates for the model reasoning correctly over the wrong or missing context — see `T06-rag-eval` and `T06-hybrid-search` for the actual levers here, which are almost entirely outside the prompt.
3. **Structured output constraints** (JSON schema enforcement, constrained decoding, grammar-based generation). Guaranteeing the model can only emit valid, parseable output eliminates an entire category of "prompt engineering to get it to format correctly" failure that used to consume real effort — see `T07-structured-output` for the mechanisms (function calling, JSON mode, grammar-constrained decoding) rather than duplicating them here.
4. **Prompt wording and technique** — real, but smaller in effect size than most practitioners assume, and the most over-invested-in lever relative to its actual impact. Most specific "magic phrase" folklore (threatening the model, promising a tip, elaborate roleplay framing for non-creative tasks) does not survive being measured against a real benchmark with statistical power; it survives in blog posts because a single anecdote with no control group is easy to publish and easy to believe.

Say this plainly to an interviewer if asked what you'd do first to improve a system's accuracy: build or fix the eval set before touching the prompt, because without it you're optimizing blind.

---

## Build it from scratch

```python
# untested sketch — self-consistency via sampled majority vote
from collections import Counter

def self_consistency(client, model, prompt, n=10, temperature=0.7):
    answers = []
    for _ in range(n):
        resp = client.messages.create(
            model=model, max_tokens=1024, temperature=temperature,
            messages=[{"role": "user", "content": prompt + "\n\nThink step by step, then give your final answer after 'Answer:'."}],
        )
        text = resp.content[0].text
        final = text.split("Answer:")[-1].strip()
        answers.append(final)
    counts = Counter(answers)
    majority, votes = counts.most_common(1)[0]
    return majority, votes / n, counts     # answer, confidence, full distribution
```

```python
# untested sketch — dynamic few-shot selection with recency-biased ordering
def build_few_shot_prompt(query, example_pool, embed_fn, k=4):
    query_vec = embed_fn(query)
    scored = sorted(example_pool, key=lambda ex: -cosine_sim(embed_fn(ex["input"]), query_vec))
    top_k = scored[:k]
    top_k.sort(key=lambda ex: ex["quality_score"])   # lowest-quality first, BEST example LAST
                                                       # exploits recency bias deliberately
    shots = "\n\n".join(f"Input: {ex['input']}\nOutput: {ex['output']}" for ex in top_k)
    return f"{shots}\n\nInput: {query}\nOutput:"
```

---

## How it's done in production

| Approach | What it adds |
|---|---|
| Dynamic few-shot retrieval (embed the query, retrieve K nearest labeled examples) | Adapts examples per-input rather than reusing a static set, which measurably beats fixed few-shot on tasks with heterogeneous inputs |
| Structured output / function calling / JSON mode | Removes format-following as a prompt-engineering problem entirely — see `T07-structured-output` |
| Reasoning-mode API parameters (extended thinking budgets, reasoning effort levels) | Lets you control how much internal reasoning a reasoning-native model does, without needing to prompt-engineer a CoT trace yourself |
| Self-consistency as a selective escalation path | Applied only when a cheaper single-pass attempt scores low-confidence (e.g., low agreement across a small initial sample), not applied uniformly to all traffic |
| Eval harnesses (golden sets, LLM-as-judge, human-rated samples) | The actual infrastructure that tells you whether any of the above helped — see `T08` eval modules |

**Failure modes**

| Symptom | Cause | Fix |
|---|---|---|
| "Improved" prompt shows gains in a 10-example manual check but production metrics don't move | Eval set too small to have statistical power; result was noise | Build a golden set large enough to detect the effect size you actually care about; track a distribution across runs, not a single pass/fail |
| Reasoning model given explicit "think step by step" performs worse than the same prompt without it | Explicit CoT prompting conflicting with the model's own trained internal reasoning process | Remove explicit step-by-step instructions for reasoning-native models; let the model's trained reasoning run, only add explicit structure if you need to steer *which* things it reasons about |
| Few-shot examples added but accuracy didn't improve | Task ambiguity was never about format — the model genuinely lacks the capability, so examples don't teach anything new | Diagnose whether the gap is format/label-space (few-shot fixes this) or genuine task difficulty (needs a better model, RAG, or fine-tuning instead) |
| Self-consistency deployed on all traffic, inference cost spikes with modest accuracy gain | Applying an N-times-cost technique uniformly instead of selectively on hard cases | Gate self-consistency behind a confidence check or route only genuinely hard problem classes through it |
| CoT prompting shows no benefit on a small or distilled model | Below the capability threshold where CoT's benefit is emergent | Don't force CoT on small models by default; measure whether it helps for your specific model size before assuming it will |
| Prompt engineering effort plateaus with no further accuracy gains despite continued iteration | Bottleneck has moved to retrieval or eval quality, not prompt wording | Re-diagnose upstream: check retrieval precision/recall and eval set validity before iterating further on the prompt |

---

## Tradeoffs & when NOT to use it

- **Don't apply explicit CoT prompting to reasoning-native models as a default.** It's frequently redundant and, per current measurement, sometimes actively harmful — verify on your specific model and task rather than carrying over 2023-era "always add step by step" advice.
- **Don't use self-consistency uniformly across all traffic.** N-times token and latency cost is real money and real p99 latency; reserve it for problems with measurably poor single-pass accuracy.
- **Don't keep adding few-shot examples past the point of diminishing returns** (typically ~5 for standard classification-style tasks) — beyond that, examples compete for context budget against retrieved content or instructions with no reliable further accuracy gain, and can introduce noise.
- **Don't reach for prompt engineering as your first lever when accuracy is bad.** If you haven't verified your eval set has statistical power and your retrieval is returning relevant context, prompt changes are optimizing blind and any observed "improvement" may not replicate.
- **When prompting technique genuinely is the right lever**: format/label-space ambiguity (few-shot fixes this cheaply), non-reasoning-model deployments where explicit CoT still measurably helps, and genuinely hard problems where self-consistency's cost is justified by the accuracy gain on that specific problem class.

---

## Interview questions

### Q1 — What does a few-shot example actually teach the model?
**Answer:** Primarily output format and label space, not the underlying task — for tasks the model already has strong pretrained competence at, few-shot examples mostly disambiguate exact label strings, JSON structure, and expected answer length/granularity, rather than teaching a capability the model lacked.
**Follow-up trap:** *"So few-shot never helps with actual task difficulty?"* — it can, for genuinely novel or unusual tasks where the model's pretraining gave it little relevant signal, but for common tasks (sentiment, standard classification, common extraction patterns) the format/label-space explanation accounts for most of the observed lift, and conflating the two leads teams to keep adding examples when the real gap is model capability, not format ambiguity.

### Q2 — How many few-shot examples before returns flatten, and what happens if you keep adding more?
**Answer:** Typically by around 4-5 examples for standard classification-style tasks — one measured case showed 5 examples lifting GPT-4o classification accuracy from 84.5% to 91.5%. Beyond that, additional examples yield diminishing and sometimes negative returns, introducing conflicting patterns or noise, and compete for context budget against other useful content.
**Follow-up trap:** *"What about many-shot regimes with dozens or hundreds of examples?"* — those exist as a separate, more specialized technique enabled by very long context windows, with plateaus reported much later (50-70 shots per class in some studies), but it's a different cost/benefit regime than standard few-shot and shouldn't be conflated with "just add more examples" advice for typical production prompts.

### Q3 — What's recency bias in few-shot prompting, and how do you exploit or mitigate it?
**Answer:** Examples placed closer to the actual query (typically last in the prompt) have disproportionate influence on the model's output relative to earlier examples. To exploit it deliberately: place your highest-quality, most representative example last. To mitigate an unwanted version of it: avoid ending a fixed example set on an unusual or edge-case example that could skew typical-case outputs.
**Follow-up trap:** *"Does this interact with dynamic example retrieval?"* — yes, and it's easy to miss: if you retrieve K nearest examples and sort them by similarity score, the least-similar of the K (last after ascending sort, or first after descending sort depending on implementation) could end up in the highest-influence position purely by an arbitrary sort order rather than a deliberate quality choice — the ordering decision needs to be explicit, not incidental.

### Q4 — State chain-of-thought's original finding and its most important caveat.
**Answer:** Prompting a model to produce intermediate reasoning steps before its final answer substantially improves accuracy on multi-step reasoning tasks (Wei et al., 2022). The caveat: this is an emergent capability tied to model scale — below a certain scale/capability threshold, CoT prompting shows flat or negative effects, because the model can produce reasoning-shaped text without the underlying capacity to make that reasoning actually track toward correctness.
**Follow-up trap:** *"Does that mean bigger is always better for CoT?"* — model scale was the original 2022 proxy for reasoning capability, but the more precise modern framing is capability threshold, not raw parameter count — a well-trained reasoning-native model at a given size can exhibit strong CoT-benefit behavior that a same-size non-reasoning model doesn't, which is exactly why reasoning-training (RL-based, not just scale) has become the dominant lever since.

### Q5 — Should you tell a reasoning model like o-series or DeepSeek-R1 to "think step by step"?
**Testing:** whether the candidate's knowledge is current past 2023.
**Answer:** Usually no. These models are trained via reinforcement learning to produce an internal extended reasoning trace before answering — that's a trained architectural behavior, not something you need to prompt into existence. Explicit CoT instructions are frequently redundant, and measured cases show they can actively reduce accuracy by imposing an external reasoning structure that fights the model's own trained process.
**Follow-up trap:** *"So chain-of-thought prompting is dead?"* — no, it's still genuinely useful for non-reasoning models and for steering *which* things a reasoning model considers (e.g., "make sure to check for off-by-one errors" as a targeted nudge, rather than a generic "think step by step"). The dead part is the blanket "always add think-step-by-step" advice as a universal default.

### Q6 — Derive why self-consistency improves accuracy and give real numbers.
**Answer:** Sample N independent reasoning traces at nonzero temperature and take the majority-vote final answer. This works because wrong answers tend to arise from idiosyncratic, uncorrelated reasoning errors, while correct answers tend to be reachable via multiple different valid reasoning paths that converge on the same result — so majority vote statistically favors the correct answer as N grows, given each individual path has better-than-chance accuracy. On GSM8K with PaLM-540B, single-pass CoT scored 56.5%; self-consistency with N=40 reached 74.4%, an 18-point gain.
**Follow-up trap:** *"Does increasing N always keep improving accuracy?"* — no, gains plateau and can decline at very high N on problems the model was already solving correctly, since additional sampling on an easy problem adds noise rather than correcting genuine errors — recent analysis frames self-consistency as best reserved for genuinely hard problems, not applied as a default scaling knob.

### Q7 — What's the actual cost of self-consistency, and how would you deploy it responsibly in production?
**Answer:** N times the token cost and either N times the latency (sequential) or N times the parallel compute (concurrent requests). Deploy it selectively: gate it behind a confidence signal (e.g., low agreement across a small initial sample of 3-5, or a task-difficulty classifier), applying the full N-sample self-consistency pass only to the subset of requests that need it, rather than uniformly across all traffic.
**Follow-up trap:** *"How would you set the confidence threshold for escalation?"* — measure it empirically against your eval set: run a cheap initial pass, correlate its internal agreement/confidence signal against whether the full self-consistency pass actually changed the answer, and set the threshold where escalation meaningfully changes outcomes rather than just adding cost with the same answer.

### Q8 — What's the honest answer to "what should I do first to improve my LLM system's accuracy"?
**Testing:** the central senior signal of this module.
**Answer:** Verify the eval set first — without a representative set large enough to distinguish real improvement from noise, you cannot tell whether any subsequent change helped. Then check retrieval/context quality if the system is RAG-backed, since no prompt wording fixes a model reasoning correctly over wrong or missing context. Then consider structured output constraints if format-following failures are a source of errors. Prompt wording iteration comes after those, not first — it's real but has a smaller effect size than most practitioners assume, and iterating on it without a valid eval set is optimizing blind.
**Follow-up trap:** *"Isn't that just avoiding the actual prompting question?"* — no, it's the correct diagnostic order; naming it plainly (rather than jumping straight to a clever prompt trick) is exactly the signal the question is probing for, and an interviewer who's shipped production LLM systems will recognize it as the answer that reflects real experience rather than folklore.

### Q9 — When would you reach for least-to-most prompting instead of standard CoT?
**Answer:** When the problem has genuine compositional structure — a multi-hop question or a task naturally decomposable into an ordered sequence of simpler subproblems where each step's answer feeds the next. Standard CoT on such problems can skip or conflate steps within a single continuous reasoning trace; least-to-most explicitly decomposes and solves in stages, carrying forward intermediate answers.
**Follow-up trap:** *"How is this different from just writing a more detailed CoT prompt?"* — least-to-most is a structural decomposition (separate solve steps, explicit intermediate answers fed forward), not just more verbose instructions within one pass; the distinction matters because it changes the actual inference pattern (potentially multiple calls or explicit staged sections) rather than just prompt wording within a single generation.

### Q10 — A teammate wants to add a persona ("You are a world-class expert...") and a promised tip to a production prompt because a blog post claimed it improves accuracy. How do you respond?
**Testing:** whether the candidate defaults to measurement over folklore.
**Answer:** Ask for the eval evidence, and if there isn't any, run it against your own eval set before shipping — most "magic phrase" folklore (personas, threats, incentives, elaborate roleplay for non-creative tasks) does not survive controlled measurement against a real benchmark; it tends to circulate because a single uncontrolled anecdote is easy to publish. If it's cheap to test and doesn't risk anything, testing it is fine; shipping it on faith is not.
**Follow-up trap:** *"What if the eval shows a small positive effect?"* — check whether it's within noise given your eval set's size before treating it as real; a small measured lift on a small eval set is often not distinguishable from sampling variance, and this is exactly the failure mode named in Q8 as the most common route to "improvements" that don't replicate in production.

### Q11 — Your RAG system's structured JSON output occasionally comes back malformed despite careful prompt wording asking for valid JSON. What's the better fix?
**Answer:** Structured output enforcement — function calling, JSON mode, or grammar-constrained decoding — rather than continuing to iterate on prompt wording asking nicely for valid JSON. This class of failure is a solved infrastructure problem (see `T07-structured-output`), and prompt-only enforcement of a hard format constraint is inherently probabilistic where a constrained decoding approach is deterministic.
**Follow-up trap:** *"Does structured output enforcement ever hurt accuracy on the actual content, separate from formatting?"* — it can, if the schema is over-constrained in a way that forces the model into an unnatural response shape before it's had room to reason; a common mitigation is letting the model reason freely first, then constraining only the final structured extraction step, rather than constraining the entire generation from the first token.

### Q12 — How would you A/B test whether chain-of-thought prompting actually helps your specific production task on your specific model?
**Answer:** Run both variants (with and without explicit CoT instruction) against the same eval set sized to detect the effect you care about, holding everything else constant (temperature, examples, model version), and compare accuracy with a statistical test appropriate for the sample size rather than eyeballing a handful of examples. Given current evidence that reasoning-native models can regress under explicit CoT, this test is now necessary rather than optional — you can no longer assume the answer is "yes, CoT helps" by default.
**Follow-up trap:** *"What if your eval set is too small to detect the effect?"* — that's the actual failure mode from Q8: you'd conclude "no significant difference" without being able to distinguish that from "not enough statistical power to see a real difference," so the fix is sizing the eval set to the minimum detectable effect you care about before running the comparison, not after.

---

## Red flags that fail you

- Recommending "think step by step" as a universal default without qualifying it for reasoning-native models.
- Believing few-shot examples primarily teach task capability rather than format/label-space, across the board.
- Applying self-consistency uniformly to all production traffic without a cost/accuracy justification.
- Treating a 10-example manual prompt comparison as sufficient evidence of improvement.
- Not knowing CoT's benefit is scale/capability-threshold-dependent, not universal.
- Reaching for prompt wording changes before checking eval validity or retrieval quality.
- Citing specific "magic phrase" folklore as reliable technique without measurement.

---

## Cheat card

```
ZERO-SHOT vs FEW-SHOT
  few-shot teaches FORMAT + LABEL SPACE more than task capability
  returns plateau ~4-5 examples (measured: +7pts GPT-4o at 5 shots, 84.5%->91.5%)
  many-shot (50-70/class) is a separate, long-context-only regime

EXAMPLE SELECTION/ORDERING
  dynamic retrieval (K-nearest per query) > static fixed set
  RECENCY BIAS: last example has outsized influence -> put best example LAST

CHAIN-OF-THOUGHT (Wei et al. 2022)
  helps multi-step reasoning — BUT emergent w/ model scale/capability
  below threshold: flat or NEGATIVE effect
  zero-shot CoT (Kojima 2022): "let's think step by step" alone, no examples needed

REASONING MODELS (o-series, Claude extended thinking, DeepSeek-R1, Gemini deep-think)
  ALREADY reason internally via RL training — architectural, not prompted
  explicit "think step by step" = often REDUNDANT, sometimes ACTIVELY HURTS
  CoT faithfulness caveat: visible trace != actual internal reasoning, don't trust as explanation

SELF-CONSISTENCY (Wang et al. 2022)
  sample N traces, majority vote
  GSM8K PaLM-540B: CoT 56.5% -> self-consistency N=40: 74.4% (+17.9pts)
  COST: N x tokens, N x latency/compute — gains plateau/decline at high N on easy problems
  -> gate behind confidence check, don't apply uniformly

OTHER TECHNIQUES (know the shape, not just the name)
  ReAct: reason+act+observe loop -> see T07-agent-loop-from-scratch
  least-to-most: decompose into ordered subproblems, feed answers forward
  step-back: answer the general principle first, then the specific question

WHAT ACTUALLY MOVES PRODUCTION ACCURACY (ranked, the honest answer)
  1. eval set quality (can you even detect a real change?)
  2. retrieval/context quality (RAG-backed systems)
  3. structured output constraints (see T07-structured-output)
  4. prompt wording — real but smaller than folklore claims; most magic-phrase
     advice does not survive measurement
```

## Sources
- [Self-Consistency Improves Chain of Thought Reasoning in Language Models — Wang et al., 2022](https://www.researchgate.net/publication/359390115_Self-Consistency_Improves_Chain_of_Thought_Reasoning_in_Language_Models) — accessed 2026-08-01
- [Self-Consistency Prompting: Get 17.9% Better Reasoning Accuracy](https://www.adaline.ai/blog/what-is-self-consistency-prompting) — accessed 2026-08-01
- [Self-Consistency Is Losing Its Edge: Diminishing Returns and Rising Costs](https://arxiv.org/html/2511.00751v2) — accessed 2026-08-01
- [Chain of Thought Prompting in 2026: Guide for GPT-5 + Claude 4.7](https://futureagi.com/blog/chain-of-thought-prompting-ai-2025/) — accessed 2026-08-01
- [Few Shot Prompting: What It Is + How to Use It (2026)](https://phrasly.ai/blog/few-shot-prompting/) — accessed 2026-08-01
- [Test-Time Adaptation via Many-Shot Prompting: Benefits, Limits, and Pitfalls](https://arxiv.org/html/2603.05829) — accessed 2026-08-01
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629) — accessed 2026-08-01

## Changelog
- 2026-08-01 — created
