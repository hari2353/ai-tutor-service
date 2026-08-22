# Explainability & Attribution: Citations, Traces, SHAP/LIME, Model Cards

> **Track:** T07 Agentic AI · **Time:** 2h · **Prereqs:** `T07-agent-loop-from-scratch`, `T07-tool-engineering` · **Updated:** 2026-07-26
> **Module id:** `T07-explainability` · **Tags:** trust, critical

## The 30-second version

**Interpretability** is a claim about the model's internals ("this circuit computes the capital-of relation"); **explainability** is a claim about one output ("this answer came from these two retrieved passages and this tool result"). For LLM systems, almost everything valuable is on the explainability side, and it is delivered by *provenance* — the trace and the citations — not by feature attribution. SHAP, LIME, and integrated gradients still earn their keep on the classical models in your pipeline (the reranker, the fraud scorer, the churn model) and are essentially useless on the generator: KernelSHAP over a 50k-token prompt would need thousands of forward passes to explain one token, and text features are not independent anyway. The one thing you must not do is ship chain-of-thought as the explanation: Anthropic measured CoT faithfulness at **25% for Claude 3.7 Sonnet and 39% for DeepSeek R1** on hint-verbalisation tests, dropping to **20% and 29%** on harmful prompts, so the visible reasoning is a *sample from the same policy that produced the answer*, not a log of the computation that produced it. Treating it as a log is a category error, and it is the specific error that gets people cut in trust-and-safety interviews.

## Why this gets asked

Because someone senior has already been in the room where a regulator, an auditor, or an enterprise customer's security team asked "why did it say that?" and the team's answer was a screenshot of the model's reasoning block. That answer collapses under one question: *"Would the model have said the same thing if it had reached the answer a different way?"* The interviewer wants to know whether you can distinguish **what the system did** (recoverable from a trace, cheap, auditable, contractually useful) from **why the weights produced these tokens** (not recoverable in production, expensive, an active research area). At staff and principal level the probe sharpens: they will ask what your explanation is *for*. If it is for a user, plausibility matters and faithfulness is a safety constraint. If it is for an incident review, faithfulness is everything and plausibility is a distraction. If it is for a regulator, the artefact is a document, not a UI. Candidates who cannot name the audience produce explanations that satisfy nobody.

---

## Lineage: past → present → future

**What came before.** Pre-2016, the accepted answer to "explain this model" was "don't use an unexplainable model" — logistic regression with monotonic constraints, decision lists, GA2M/GAM. Then two papers made post-hoc explanation of arbitrary models respectable: **LIME** (Ribeiro et al., KDD 2016) fitted a sparse local linear surrogate around one prediction, and **SHAP** (Lundberg & Lee, NeurIPS 2017) unified the field on Shapley values from cooperative game theory, giving the only attribution satisfying local accuracy, missingness, and consistency. **Integrated Gradients** (Sundararajan et al., ICML 2017) added a path-integral method for differentiable models with a completeness axiom. For a few years attention weights were treated as free explanation, and that specific idea died in public: **"Attention is not Explanation"** (Jain & Wallace, NAACL 2019) showed you can find adversarial attention distributions that produce the same prediction with completely different weights, and **"Attention is not not Explanation"** (Wiegreffe & Pinter, EMNLP 2019) pushed back without restoring it. Cynthia Rudin's *"Stop explaining black box machine learning models for high-stakes decisions"* (Nature MI, 2019) named the underlying pain: post-hoc explanations were being used to *license* deployment of models nobody understood, and a plausible-but-wrong explanation is worse than no explanation because it manufactures unearned confidence. That is the exact pain that recurs with CoT.

**Where it stands now.** The consensus has split cleanly along the line this module is about. For **system-level explanation**, the industry standardised on provenance: retrieval traces, tool-call records, inline citations, prompt and model version pinning, and OpenTelemetry GenAI semantic conventions as the wire format. This is boring, cheap, and it is what actually ships. For **model-level understanding**, the centre of gravity moved from feature attribution to mechanistic interpretability: Anthropic's circuit-tracing work using cross-layer transcoders to build **attribution graphs** was open-sourced in May 2025 as `circuit-tracer`, and MIT Technology Review named mechanistic interpretability a 2026 Breakthrough Technology. Classical attribution did not die, it got correctly scoped — it remains the right tool for the tabular and feature-based models inside an AI system, and the wrong tool for the generator. The live disagreements are worth knowing. (1) **Is CoT monitorable?** The July 2025 multi-lab position paper *"Chain of Thought Monitorability: A New and Fragile Opportunity for AI Safety"* (arXiv:2507.11473, co-authored across Anthropic, OpenAI, and Google DeepMind, endorsed by Sutskever, Schulman, and Hinton) argues CoT monitoring is worth preserving as a safety agenda *while explicitly conceding it is not faithful and may not survive further optimisation*. Some researchers think building on an unfaithful signal is a mistake; a 2026 counter-line (arXiv:2512.23032) argues CoT can be faithful in the causal sense even when it fails hint-verbalisation tests, i.e. that the standard benchmark measures the wrong thing. Both positions are defensible and you should be able to state both. (2) **Whether sparse features are the right unit** of explanation at all, versus attention heads or geometric directions. (3) **Whether explanations should be shown to end users at all**, given the evidence that plausible explanations increase reliance regardless of correctness.

**Where it's heading.** High confidence: **regulatory pressure turns explanation into a documentation deliverable**. EU AI Act Article 13 (transparency to deployers) and Article 14 (human oversight) apply to high-risk systems from 2 August 2026, Article 50 transparency provisions apply the same day, and the GPAI documentation stack (internal technical docs, public model card, downstream deployer package, published training-data summary) is due then too, with penalties up to €35M or 6-7% of global turnover depending on the provision. Model cards stop being a nice-to-have README and become a compliance artefact generated from CI. High confidence: **traces become the audit substrate** and the interesting engineering problem becomes retention, redaction, and cost, not capture. Medium confidence: **verified rather than explained** outputs grow — AWS shipped Automated Reasoning checks in Bedrock Guardrails GA in August 2025, claiming up to 99% verification accuracy on formally-encoded policy domains, which sidesteps explanation by proving the claim instead. Speculative, and flag it as such: attribution graphs running at inference time on production traffic. Circuit tracing today costs orders of magnitude more than the forward pass it explains and requires a transcoder trained per model; treat "we'll just show the customer the circuit" as research, not roadmap.

---

## Mental model

Four layers, and only two of them are yours to ship.

```
                        THE EXPLANATION STACK
  ┌────────────────────────────────────────────────────────────────────────┐
  │ L4  USER-FACING RATIONALE      "Based on your Aug invoice (§3) and the  │
  │     what the human reads        refund policy v2.1, you're eligible."   │
  │     ── PLAUSIBILITY matters, faithfulness is a SAFETY CONSTRAINT ──     │
  ├────────────────────────────────────────────────────────────────────────┤
  │ L3  SYSTEM TRACE               spans: retrieval(q, doc_ids, scores) →   │
  │     what the system DID         rerank → tool_call(args, result_hash) → │
  │     ✅ YOU SHIP THIS            generate(model@ver, prompt@ver, cost)   │
  │     ── fully faithful by construction: it's a log, not a story ──       │
  ├────────────────────────────────────────────────────────────────────────┤
  │ L2  MODEL-BEHAVIOURAL          SHAP / LIME / IG / leave-one-out         │
  │     which INPUTS mattered       ✅ works on the reranker, fraud model    │
  │                                 ❌ ~useless on the 50k-token generator   │
  ├────────────────────────────────────────────────────────────────────────┤
  │ L1  MECHANISTIC                circuits · SAE features · attribution    │
  │     what the WEIGHTS compute    graphs · cross-layer transcoders        │
  │     🔬 research; not in your request path in 2026                        │
  └────────────────────────────────────────────────────────────────────────┘

  CHAIN-OF-THOUGHT sits at L4, NOT L3. It is generated text about the
  computation, produced by the same sampling process as the answer.
  Faithfulness measured 25% (Claude 3.7 Sonnet) / 39% (DeepSeek R1).
```

The single sentence that makes it click: **a trace is a log, a chain of thought is a story.** Logs are faithful because writing them is not the same act as doing the work. CoT is unfaithful because generating it *is* the same act, sampled from the same distribution, subject to the same pressures toward fluency and plausibility.

Second picture, the honesty ladder — what you can truthfully claim, cheapest first:

```
 CLAIM STRENGTH                                          COST
 "these tokens were in context"        provenance         ~0        ✅ always
 "this passage entails this sentence"  NLI verification   1 small model call
 "removing this chunk changes it"      leave-one-out      k+1 LLM calls
 "these features drove the score"      SHAP (tabular)     100s-1000s of evals
 "this circuit performs this step"     attribution graph  research-grade
 "the model reasoned as follows"       CoT                ~0        ❌ unfaithful
```

Note the last row is the cheapest and the most tempting, and it is the only one that is a lie.

---

## How it actually works

### Definitions you will be graded on

| Term | Definition | Scope |
|---|---|---|
| **Interpretability** | The degree to which a human can understand the model's *mechanism* | Global, model-level |
| **Explainability** | An account of why *this input* produced *this output* | Local, output-level |
| **Faithfulness** | The explanation accurately reflects the process that produced the output | Property of an explanation |
| **Plausibility** | The explanation is convincing to a human | Property of an explanation |
| **Attribution** | A mapping from output content back to specific source content | Provenance claim |
| **Provenance** | The recorded chain of artefacts and versions that produced the output | Property of the system |

The trap in that table: **faithfulness and plausibility are independent axes**, and optimising for the one users can see (plausibility) with human feedback actively degrades the one that matters (faithfulness). Turpin et al. (NeurIPS 2023, arXiv:2305.04388) demonstrated it: insert a biasing feature into the prompt (e.g. always mark option (A) in the few-shot examples), and models produce fluent CoT justifying the biased answer without mentioning the bias, with accuracy dropping **up to 36% across 13 BIG-Bench Hard tasks** on GPT-3.5 and Claude 1.0. The explanations got *more* plausible as they got less faithful.

### SHAP: what it is, and the arithmetic that rules it out for LLMs

Shapley value for feature *i* is the average marginal contribution across all orderings:

```
φᵢ = Σ_{S ⊆ F\{i}}  [ |S|!(|F|-|S|-1)! / |F|! ] · [ f(S ∪ {i}) - f(S) ]
```

Exact computation is over `2^|F|` coalitions. That is the whole story for why it does not transfer:

- **TreeSHAP** makes it tractable for tree ensembles: `O(T · L · D²)` for *T* trees, *L* leaves, *D* depth. Exact, fast, and the reason SHAP is ubiquitous on tabular work. Your BGE reranker's *feature-based* variants, a LightGBM CTR model, a fraud scorer: use it.
- **KernelSHAP** is the model-agnostic fallback: sample coalitions, fit a weighted linear regression. Practically you need on the order of `2·|F| + 2048` samples for a stable estimate. With `|F| = 512` tokens that is ~3k forward passes **per explained output**. At 50k tokens of context it is not a cost problem, it is a category problem.
- **Independence assumption.** Shapley values with a marginal (interventional) reference distribution place mass on off-manifold inputs. Masking token 400 of a sentence produces text no model ever saw. With correlated features, SHAP attributes to unrealistic instances; with text, *every* feature is correlated.
- **Wrong output type.** SHAP explains a scalar. An LLM emits a sequence. You would need one explanation per generated token, or a scalar reduction (perplexity of the answer, a judge score) that throws away what you wanted to explain.

The senior framing: **SHAP answers "which features moved this score"; nobody asks that about a generated paragraph. They ask "where did this claim come from", which is a retrieval question, not an attribution question.**

### LIME and its instability

LIME perturbs the input, gets predictions, fits a sparse linear model weighted by proximity kernel `exp(-D(x,z)²/σ²)`. Two known failure modes you should be able to name:

1. **Seed instability.** Different random perturbation samples give different top-k features for the same instance. Reported rank correlations between repeated runs on the same input are frequently well below 0.8; the practical mitigation is to run it n≥10 times and only report features stable across runs, which multiplies cost.
2. **Kernel width `σ` is a free parameter with no principled default.** Change it and you change which features look important. There is no cross-validation objective, because there is no ground truth.

For text, LIME's perturbation is word deletion, which produces ungrammatical inputs and explains the model's behaviour on garbage rather than on the real input.

### Integrated gradients and the baseline problem

`IG_i(x) = (x_i - x'_i) · ∫₀¹ ∂f(x' + α(x - x'))/∂x_i dα`, approximated with 20-300 Riemann steps (300 for tight completeness error; check that `Σφᵢ ≈ f(x) - f(x')` to within ~5%).

For images the all-black baseline `x'` is defensible. For text there is no neutral token: the zero embedding is off-manifold, `[PAD]` and `[MASK]` carry learned meaning, and the choice of baseline changes the sign of attributions. IG also requires white-box gradient access, which you do not have for API models. It is usable on your own fine-tuned encoder; it is not usable on the frontier model in your pipeline.

### What actually works for LLM-output attribution

Three techniques that survive contact with production, in increasing cost:

**1. Provenance (free).** You already know exactly which chunks, tool results, and memories were in the context, because you put them there. Record chunk ids, scores, and byte offsets. This is not an inference about the model; it is a fact about the system. It supports the claim "the model could only have got this from one of these five passages" which, combined with a closed-book baseline, is genuinely strong.

**2. Entailment verification (one small-model call per sentence).** Take each generated sentence and its cited chunk, run an NLI model, keep only sentences where the chunk entails the sentence. This upgrades "this chunk was present" to "this chunk supports this claim". Covered mechanically in `T07-attribution`.

**3. Leave-one-out over retrieved chunks (k+1 generation calls).** Occlusion at the *chunk* level rather than the token level. Regenerate with chunk *j* removed; if the answer's key claim changes or its logprob drops materially, chunk *j* was load-bearing. This is exactly what ALCE-style citation *precision* computes, and it is the honest version of "feature attribution" for a RAG system: coarse granularity, semantically meaningful units, tractable cost at k=5-10.

```python
# untested sketch — chunk-level occlusion attribution for a RAG answer
import itertools, hashlib

def chunk_attribution(question, chunks, answer, generate, score_fn):
    """Which retrieved chunks were load-bearing for `answer`?
    Cost: len(chunks) + 1 generation calls. k=8 -> 9 calls, ~2-4s each.
    score_fn(a, b) -> [0,1] semantic agreement (NLI-entailment or embedding cos).
    """
    base = score_fn(answer, generate(question, chunks))     # sanity: should be ~1.0
    out = []
    for j in range(len(chunks)):
        ablated = chunks[:j] + chunks[j+1:]
        alt = generate(question, ablated)
        out.append({
            "chunk_id": chunks[j]["id"],
            "delta": base - score_fn(answer, alt),          # >0.2 == load-bearing
            "answer_without": alt,
        })
    return sorted(out, key=lambda r: -r["delta"])
```

Interpret the output honestly: a `delta` near zero means either the chunk was irrelevant **or** the information was redundantly available elsewhere (including in the weights). Occlusion cannot distinguish those, and saying so out loud is a senior signal.

### Chain-of-thought is not an explanation

This is the section that decides the interview. Three pieces of evidence, all citable:

- **Turpin et al. 2023** (arXiv:2305.04388): biasing features change the answer, CoT rationalises the changed answer without mentioning the bias, accuracy drops up to 36% on 13 BBH tasks.
- **Chen et al., Anthropic, May 2025** (arXiv:2505.05410, *Reasoning Models Don't Always Say What They Think*): overall hint-verbalisation faithfulness **25% for Claude 3.7 Sonnet, 39% for DeepSeek R1**; on harmful-hint settings, **20% and 29%**. Faithfulness *decreases* as questions get harder. Reasoning models were more faithful than their non-reasoning counterparts, which is the honest caveat — the trend is favourable and the absolute level is still unusable as evidence.
- **Arcuschin et al. 2025** (arXiv:2503.08679, *Chain-of-Thought Reasoning In The Wild Is Not Always Faithful*): unfaithfulness occurs on naturally-worded prompts with **no injected bias at all**, including models producing coherent arguments for both "yes" and "no" on logically inverted pairs of the same question.

The mechanism is not mysterious and you should state it mechanically: the CoT tokens are sampled autoregressively from the same distribution as the answer tokens. Nothing in training ties them to the forward-pass computation that determined the answer; RLHF rewards them for being *convincing and correct-looking*. A model can attend to a feature that never appears in its verbalisation, and the verbalisation can assert a step the model did not use. There are two distinct claims here, keep them separate:

- **CoT is causally load-bearing** — often true. Erase it and accuracy drops. That is why CoT works.
- **CoT is a faithful description of the computation** — measured at 25-39% on the standard test. That is why it is not an explanation.

The interview-grade version: *"CoT is useful as a monitoring signal and as an artefact for a human reviewer to attack, because when it reveals bad reasoning that is real evidence. It is not usable as certification that the reasoning was good. Absence of a red flag in CoT is not evidence of safety."* That is also, almost verbatim, the position the 2025 monitorability paper takes.

### Trace-based explanation for agents

For an agent, the explanation *is* the trace, and this is good news because a trace is faithful by construction. Minimum record per run, using OpenTelemetry GenAI semantic-convention span names:

| Span | Attributes you must capture | Why |
|---|---|---|
| `gen_ai.client.inference` | model id + version, prompt template id + version, temperature, seed if available, input/output token counts, cost | Reproducibility. "Which prompt version" is the first incident question |
| `retrieval` | query (post-rewrite), index + snapshot id, top-k doc ids, scores, latency | Lets you replay retrieval independently of generation |
| `rerank` | model, input order, output order, scores | Where "the right doc was retrieved but ranked 9th" shows up |
| `tool.execute` | tool name + schema version, arguments, result hash + size, error class, retries | Arguments are the agent's actual decisions |
| `decision` | branch taken, condition value, budget remaining, step index | Explains loop control, not just content |
| `guardrail` | check name, verdict, score, threshold | Explains refusals and redactions |

Two rules people get wrong. **Store the result hash and a bounded prefix, not the full payload** — a 2MB tool result per span will bankrupt your trace backend and your redaction review. And **version everything that is not data**: model, prompt, tool schema, index snapshot, guardrail config. An explanation that cannot be replayed is an anecdote.

### Model cards and system cards

**Model card** (Mitchell et al., FAT* 2019) documents the trained artefact: intended use, out-of-scope use, training data summary, evaluation results *disaggregated by relevant group*, metrics with confidence intervals, ethical considerations, caveats. **System card** documents the deployed system: the model plus retrieval, tools, guardrails, human oversight, and the failure modes of the composition. The distinction matters because for most of what you build, the model card is somebody else's document (the provider's) and the system card is yours.

As of the 2 August 2026 EU AI Act milestones this stops being voluntary for anything in scope. The practical engineering move is to **generate the card from CI**: eval results, dataset hashes, model and prompt versions, and known limitations pulled from the same registry your traces reference, so the document cannot drift from the system. A hand-maintained markdown card is stale within two sprints, and a stale card is a documented compliance failure rather than a missing one.

---

## Build it from scratch

A decision record: the minimum artefact that makes a single agent output explainable, and the renderer that turns it into something a user can read without lying to them.

```python
# runnable with python 3.11+, stdlib only
from dataclasses import dataclass, field, asdict
from typing import Any
import hashlib, json, time, uuid


def _h(x: Any) -> str:
    return hashlib.sha256(json.dumps(x, sort_keys=True, default=str).encode()).hexdigest()[:12]


@dataclass
class Evidence:
    source_id: str            # stable doc id, not a URL
    locator: str              # "p3:§2" or "chars 1204-1388" — must point INTO the doc
    quote: str                # verbatim span, <= 300 chars
    score: float              # retrieval or rerank score
    entailed: bool | None = None   # filled in by the NLI verifier, None = unchecked


@dataclass
class DecisionRecord:
    run_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    ts: float = field(default_factory=time.time)
    question: str = ""
    answer: str = ""
    # provenance: what the system DID
    model: str = ""                    # "claude-sonnet-4-6@20260410"
    prompt_version: str = ""           # "answer_with_citations@v7"
    index_snapshot: str = ""           # "kb-2026-07-19T04:00Z"
    retrieved: list[Evidence] = field(default_factory=list)
    tool_calls: list[dict] = field(default_factory=list)
    guardrails: list[dict] = field(default_factory=list)
    # honest uncertainty
    abstained: bool = False
    unsupported_sentences: list[str] = field(default_factory=list)

    def integrity(self) -> str:
        return _h({"q": self.question, "a": self.answer,
                   "ev": [e.source_id + e.locator for e in self.retrieved],
                   "m": self.model, "p": self.prompt_version})

    def user_explanation(self) -> str:
        """L4 rendering. Claims ONLY what the record supports."""
        lines = []
        verified = [e for e in self.retrieved if e.entailed is True]
        if verified:
            lines.append("This answer is supported by:")
            for e in verified:
                lines.append(f'  • {e.source_id} ({e.locator}): "{e.quote[:160]}"')
        unverified = [e for e in self.retrieved if e.entailed is None]
        if unverified:
            lines.append(f"Consulted but not verified as supporting: "
                         f"{', '.join(e.source_id for e in unverified)}")
        if self.unsupported_sentences:
            lines.append("Not supported by any source (treat as unverified):")
            lines += [f"  ! {s}" for s in self.unsupported_sentences]
        for t in self.tool_calls:
            lines.append(f"  ⚙ ran {t['name']}({json.dumps(t['args'])[:120]}) "
                         f"→ {t.get('status', 'ok')}")
        if not verified and not self.tool_calls:
            lines.append("No source was verified for this answer. "
                         "It reflects the model's parametric knowledge only.")
        return "\n".join(lines)

    def audit_json(self) -> str:
        d = asdict(self)
        d["integrity"] = self.integrity()
        return json.dumps(d, indent=2, default=str)


if __name__ == "__main__":
    r = DecisionRecord(
        question="Is the August invoice eligible for refund?",
        answer="Yes. Invoice INV-8841 is within the 30-day window and the plan is monthly.",
        model="claude-sonnet-4-6@20260410",
        prompt_version="answer_with_citations@v7",
        index_snapshot="kb-2026-07-19T04:00Z",
        retrieved=[
            Evidence("policy/refunds-v2.1", "§3.2", "Refunds are available within 30 days...",
                     0.81, entailed=True),
            Evidence("billing/INV-8841", "chars 400-460", "Issued 2026-07-11, monthly plan",
                     0.77, entailed=True),
            Evidence("policy/refunds-v1.4", "§3.1", "Refunds within 14 days...", 0.52),
        ],
        tool_calls=[{"name": "get_invoice", "args": {"id": "INV-8841"}, "status": "ok"}],
    )
    print(r.user_explanation())
    print("\nintegrity:", r.integrity())
```

Three properties worth defending in an interview: the record contains **no model-authored narrative** (so it cannot rationalise), every `Evidence` carries a **locator into the document** (so a human can check it in one click, which is the difference between a citation and a decoration), and `entailed` is a **tri-state** — verified, contradicted, unchecked — so an unverified citation is never rendered as a supported one.

Lab: **`labs/py/19-explainability/`** adds the NLI verifier, the occlusion attributor, an OTel exporter, and a golden-trace regression test.

---

## How it's done in production

**Tracing.** LangSmith, Langfuse, and Arize Phoenix all consume OpenTelemetry GenAI semantic conventions; the conventions are still marked development-stage, so pin your attribute names and normalise at the exporter rather than scattering vendor keys through the code. What the managed layer adds over rolling your own: trace-linked eval runs, dataset construction from production traces (the single highest-value feature — your regression set should be real failures), prompt-version diffing, and cost attribution per run. What it does not add: any faithfulness guarantee. A trace viewer that renders the model's `thinking` block next to the retrieved docs invites your own engineers to read CoT as ground truth.

**Classical attribution, correctly scoped.** `shap.TreeExplainer` on the reranker's feature-based variant or the CTR model; `captum` for integrated gradients on your fine-tuned encoder; per-feature drift monitoring on those same features. This is where the interviewer expects you to say "SHAP, yes, on *that* model" and not "SHAP, no, we use LLMs now".

**Verification instead of explanation.** Bedrock Guardrails contextual grounding filters over 75% of hallucinated responses on RAG and summarisation workloads by checking the output against the source; Automated Reasoning checks (GA August 2025) encode a policy document into formal logic and validate outputs against it with claimed up to 99% accuracy. Note precisely what that buys: it is a *soundness* claim over a formalised policy, not an explanation, and it only exists where someone did the formalisation work.

**Mechanistic tooling.** `circuit-tracer` (Anthropic, open-sourced May 2025) builds attribution graphs from cross-layer transcoders. Legitimate uses today: post-incident investigation on an open-weights model you control, and safety research. Not a production explanation path — you need a transcoder trained for that model, and graph construction costs vastly more than the generation it explains.

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Support cites the model's `thinking` block in a customer RCA; the claimed reason is absent from the trace | CoT treated as L3 log rather than L4 story | Remove reasoning blocks from the explanation surface; render only trace-derived facts |
| Citation links resolve but the cited page does not contain the claim | Post-hoc citation, no entailment check | NLI verification gate; see `T07-attribution` |
| Trace storage bill exceeds inference bill | Full tool payloads stored per span | Store `hash + 2KB prefix`, offload payloads to object storage with TTL |
| Explanations disagree between two identical requests | Unpinned model alias (`-latest`) or missing prompt version in the record | Pin model@version and prompt@version in the record; alias resolution logged |
| "Explain this decision" for a 3-week-old run returns nothing | Index snapshot rotated; chunk ids reused after reindex | Immutable chunk ids + snapshot id in the record; retain snapshot manifests |
| SHAP job on the reranker takes 40 min per batch and blocks the dashboard | KernelSHAP used where TreeSHAP applies, or explaining every row instead of sampling | TreeSHAP for tree models; explain a stratified sample, not the full table |
| Users accept wrong answers *more* after you shipped explanations | Plausibility increased without faithfulness; classic automation bias | Show verified evidence only; mark unverified claims explicitly; see `T07-human-oversight` |
| Audit asks "what data trained this" and nobody knows | No model card / training-data summary for a fine-tune you own | CI-generated model card keyed to dataset hash |

---

## Tradeoffs & when NOT to use it

- **Do not ship chain-of-thought as an explanation, in any product surface, ever.** Faithfulness 25-39%. It is legally worse than silence: you have asserted a causal account you cannot support. There is one narrow exception — showing a reasoning summary as *content the user can attack* ("here is my working, check step 3") in a tool aimed at experts. State that framing explicitly if you use it.
- **Do not run SHAP or LIME on a generative model.** ~3k forward passes per explained output at 512 features, off-manifold masks, correlated tokens, wrong output type. If asked to, propose chunk-level occlusion instead and give the cost: `k+1` generations.
- **Do not add an explanation surface to a low-stakes, high-volume feature.** Explanation UI has a real cost: it slows the interaction, invites disputes, and increases reliance. For autocomplete or a search ranking, a citation link is enough and a rationale is noise.
- **Explanations are an attack surface.** They leak system-prompt structure, retrieval corpus composition, and threshold behaviour. If your system makes adversarial decisions (fraud, abuse, pricing, moderation), a faithful explanation is a specification for evading it. The correct pattern is a two-tier explanation: full trace to the internal reviewer, minimal reason code to the subject. Say this before the interviewer does.
- **More explanation can reduce net safety.** MIT SMR's rubber-stamping work and the automation-bias literature both point the same way: plausible rationale raises acceptance rates of *wrong* outputs. If you ship an explanation, you owe an eval measuring whether reviewers catch injected errors *more* often with it than without. Almost nobody runs that eval.
- **Mechanistic interpretability is not a deliverable on a product timeline.** It is the right answer to "how would you investigate why this open-weights model does X in a red-team finding", and the wrong answer to "how will you explain decisions to customers next quarter".
- **When the real requirement is a guarantee, explanation is the wrong tool.** If the ask is "this must never contradict the policy", the answer is constrained generation plus formal or NLI verification, not a better explanation of a free-form answer.

---

## Interview questions

### Q1 — What is the difference between interpretability and explainability?
**Testing:** whether you use the words precisely or interchangeably.
**Answer:** Interpretability is a property of the *model* — the extent to which its mechanism is human-understandable, which is global and intrinsic (a depth-3 tree, a monotonic GAM). Explainability is a property of an *account of one output* — why this input produced this output, which is local and usually post-hoc. A random forest is not interpretable but SHAP makes individual predictions explainable. For LLM systems, interpretability is a research programme (circuits, SAE features) and explainability is an engineering deliverable (traces, citations, provenance).
**Follow-up trap:** *"Which one do regulators require?"* — neither, by that name. EU AI Act Article 13 requires transparency sufficient for deployers to interpret output and use it appropriately, and Article 14 requires oversight persons be able to correctly interpret outputs. That is satisfied by documented limitations, provenance, and reason codes, not by mechanistic understanding. Anyone who answers "the AI Act requires explainable models" has not read it.

### Q2 — Would you use SHAP to explain an LLM's answer?
**Testing:** whether you can say "no" with arithmetic instead of vibes.
**Answer:** No, and the reasons are structural, not practical. Exact Shapley is `2^|F|` coalitions; KernelSHAP needs roughly `2|F| + 2048` samples, so ~3k forward passes per explained output at 512 tokens, and a real prompt is 10-50k tokens. Tokens are not independent features, so the marginal reference distribution puts mass on off-manifold text no model has seen. And SHAP explains a scalar while an LLM emits a sequence, so you would have to explain each token or collapse the output to a score and lose the thing you wanted explained. What I would do instead: chunk-level occlusion over the k retrieved passages, which is `k+1` generation calls, uses semantically meaningful units, and answers the question people actually ask.
**Follow-up trap:** *"So where does SHAP still belong in your stack?"* — on the non-generative models: the reranker's feature-based scorer, the CTR or fraud model, the router that decides which model to call. TreeSHAP is exact and `O(T·L·D²)`, so it is cheap there. Saying "SHAP is obsolete" fails this; the point is scoping, not dismissal.

### Q3 — Your PM wants to show the model's reasoning to users as the explanation. What do you say?
**Testing:** the core honest point of this module, plus whether you can push back constructively.
**Answer:** That CoT is not an explanation of the computation and shipping it as one creates liability. Anthropic's own measurement puts hint-verbalisation faithfulness at 25% for Claude 3.7 Sonnet and 39% for DeepSeek R1, dropping to 20% and 29% on harmful prompts, and Turpin et al. showed models produce fluent rationales for biased answers without ever mentioning the bias, with up to a 36% accuracy drop on 13 BBH tasks. So the reasoning block is a plausible story generated by the same sampling process as the answer, and its plausibility is exactly what makes it dangerous. What I would ship instead: verified citations with locators into the source, the tool calls that were made with their arguments, and an explicit statement when a claim has no supporting source. That is derived from the trace, so it is faithful by construction, and it is more useful to the user because they can check it.
**Follow-up trap:** *"But OpenAI and Anthropic both show reasoning summaries in their products. Are they wrong?"* — they show it as *content*, not as certification, and both publish that it is unfaithful. The distinction is what claim the UI makes. "Here is my working" invites scrutiny; "here is why this is correct" asserts something unsupported. And the July 2025 multi-lab monitorability paper takes precisely this position: CoT is worth monitoring because visible bad reasoning is real evidence, while its absence is not evidence of safety.

### Q4 — What makes a trace a faithful explanation when CoT is not?
**Testing:** whether you understand *why*, not just *that*.
**Answer:** Because emitting a trace is a different act from doing the work. The span that records `retrieval(query, doc_ids, scores)` is written by the retrieval code as a side effect of retrieving; it cannot rationalise, because it is not generated by a policy optimised for plausibility. CoT is sampled autoregressively from the same distribution as the answer, with nothing in training tying it to the forward-pass computation and RLHF rewarding it for looking convincing. A log is a record; a chain of thought is a story about a record.
**Follow-up trap:** *"Is a trace a complete explanation then?"* — no. It faithfully explains everything the *system* did and says nothing about why the weights emitted these tokens given that context. If the answer is wrong despite correct retrieval and correct tools, the trace localises the failure to the generation step and then stops. That boundary is the honest claim.

### Q5 — Design the explainability layer for a RAG assistant used by insurance claims adjusters.
**Testing:** whether you can produce a concrete, layered design with an audience per layer.
**Answer:** Three audiences, three artefacts. (1) **Adjuster, in-line:** sentence-level citations with a locator (`policy-v2.1 §3.2, chars 1204-1388`) that deep-links and highlights, each gated by an NLI entailment check, plus explicit "unsupported" marking on any sentence that fails the check, plus abstention when nothing entails. (2) **Reviewer / QA, on demand:** the full trace — retrieval query after rewrite, index snapshot id, top-k with scores, rerank reordering, tool calls with arguments, guardrail verdicts, model@version, prompt@version, cost — replayable so retrieval can be rerun independently of generation. (3) **Regulator / enterprise buyer, as a document:** a system card covering intended use, out-of-scope use, eval results with the abstention rate and citation-precision numbers, known failure modes, human-oversight design, and retention policy, generated from CI so it cannot drift. And a deliberate exclusion: no model-authored reasoning narrative anywhere in the product surface.
**Follow-up trap:** *"How do you keep an explanation for a decision made three weeks ago when the index has been rebuilt twice?"* — immutable chunk ids and retained snapshot manifests, with the snapshot id in the decision record; store the quoted span verbatim in the record rather than only a pointer, so the explanation survives even if the source is deleted, and record the source's own content hash so you can detect that it changed rather than silently showing new text as old evidence.

### Q6 — A regulator asks why your model denied a claim. Walk me through your answer.
**Testing:** whether you know that the answer is a document plus a record, not a saliency map.
**Answer:** I would not lead with the model. I would produce: the decision record (inputs, retrieved policy sections with quoted spans, the tool results that established the facts, the rule or threshold that produced the outcome, versions of all of it), the human-oversight record if the decision was gated (who reviewed, what they saw, how long they had, what they changed), the system card with the eval results and documented limitations, and the aggregate outcome monitoring including disaggregated performance. If the actual eligibility determination is deterministic, I would also point out that the LLM extracted and summarised while a rules engine decided, because that is a much stronger position than "the model decided and here is our explanation".
**Follow-up trap:** *"What if the LLM did make the decision?"* — then say so and show the abstention and escalation policy, the review rate, and the measured error rate with confidence intervals. Do not invent a mechanistic account. The single worst answer is a post-hoc rationalisation generated by asking the model why it decided, which is unfalsifiable and, if it ever contradicts the trace, is evidence against you.

### Q7 — Attention weights: are they an explanation?
**Testing:** whether you know the 2019 literature.
**Answer:** No. Jain & Wallace (NAACL 2019) showed you can construct adversarial attention distributions that produce essentially the same prediction while attending to completely different tokens, so attention is not identifiable as the explanation. Wiegreffe & Pinter (EMNLP 2019) pushed back on the strongest reading — attention is not *nothing* — but nobody restored it as a faithful attribution. In multi-head, multi-layer transformers with residual streams it is worse: attention in layer 7 is over representations that already mixed information from everywhere, so a head attending to token 40 tells you little about token 40's causal role.
**Follow-up trap:** *"What about attention rollout or attention-flow methods?"* — they aggregate across layers to address exactly that objection and they help for coarse localisation, but they inherit the identifiability problem and are not causal. If you want causality, do ablation: remove the span and measure the change in output. Expensive, coarse, and actually a causal claim.

### Q8 — Explain the difference between faithfulness and plausibility, and why it is a product risk.
**Testing:** senior framing of the central tension.
**Answer:** Faithfulness is whether the explanation matches the process that produced the output; plausibility is whether a human finds it convincing. They are independent, and only plausibility is visible to the user, to the PM, and to human raters. So any optimisation loop with a human in it — RLHF, A/B tests on explanation satisfaction, design review — pushes on plausibility and can degrade faithfulness. The product risk is specific and measured: plausible explanations raise acceptance of wrong outputs. The automation-bias literature and MIT SMR's rubber-stamping work both show that a rationale attached to a recommendation increases reliance without increasing accuracy, so shipping explanations without an accompanying eval on error-detection can *reduce* system-level correctness while every visible metric improves.
**Follow-up trap:** *"How would you measure that?"* — an error-injection study on the humans, not the model: take N real outputs, corrupt a specific claim in a random half, show explanation and no-explanation arms to reviewers, and measure detection rate and time-to-decision. If detection does not improve, the explanation is decoration. Nobody runs this and it is the answer that separates staff from senior.

### Q9 — Chunk-level occlusion says a chunk has zero influence. What do you conclude?
**Testing:** whether you over-read ablation results.
**Answer:** Only that the chunk was not *necessary* given everything else present. Two very different worlds produce the same zero: the chunk was irrelevant, or the same fact was redundantly available in another chunk or in the model's parameters. Occlusion measures necessity, not sufficiency, and with correlated evidence necessity goes to zero. To distinguish, run the complementary test: generate with *only* that chunk (sufficiency), and run a closed-book baseline with no chunks at all to see whether the model knew it anyway. Three numbers — necessity, sufficiency, closed-book — are interpretable; one is not.
**Follow-up trap:** *"What is the cost of doing all three at k=10?"* — `k` necessity runs plus `k` sufficiency runs plus 1 closed-book plus the base run = 22 generation calls. At ~2s and ~$0.01 each that is ~45s and ~$0.22 per explained answer, which is fine for an audit path and not fine per request. So it belongs in offline eval and incident review, not the hot path. Being explicit about which path a technique lives in is the point.

### Q10 — What goes in a model card versus a system card, and who generates them?
**Testing:** whether you have actually shipped governance artefacts.
**Answer:** The model card documents the trained artefact — intended and out-of-scope use, training data summary, evaluation disaggregated by relevant subgroup with confidence intervals, caveats. For a frontier API model that document is the provider's and you consume it; for anything you fine-tune it is yours. The system card documents the composition you deployed — model plus retrieval plus tools plus guardrails plus human oversight — and the failure modes that only exist in the composition, which is the part no provider can write for you. Both should be generated from CI against the same registry your traces reference: eval results, dataset hashes, model and prompt versions. Hand-maintained cards drift within two sprints and a stale card is a documented compliance failure rather than a missing one.
**Follow-up trap:** *"What is the deadline pressure here?"* — EU AI Act high-risk obligations including Article 13 transparency and Article 14 oversight, plus Article 50 transparency provisions, apply from 2 August 2026, and the GPAI documentation stack (internal technical documentation, public model card, downstream deployer package, training-data summary) is due the same day. Penalties run to €35M or 6-7% of global turnover depending on provision. If you are not in scope, say why you believe you are not — that is itself an answer they are testing for.

### Q11 — Is mechanistic interpretability going to solve this?
**Testing:** calibration about research timelines.
**Answer:** Partially, and not on a product timeline. The 2025-2026 progress is real: cross-layer transcoders and attribution graphs, open-sourced by Anthropic as `circuit-tracer` in May 2025, named a 2026 MIT Tech Review Breakthrough Technology. What that buys today is post-incident investigation on models whose weights you have, plus safety research. What it does not buy is per-request explanation, because you need a transcoder trained for the specific model and graph construction costs orders of magnitude more than the generation it explains. My confidence that mechanistic methods are in a production request path within three years is low; my confidence that they become standard in incident forensics for open-weights models is moderate.
**Follow-up trap:** *"Then why should we care?"* — because it is the only line of work that could ever produce a faithful account of the generation step, which is exactly the gap traces cannot close. And because interpretability findings already change engineering decisions today, e.g. evidence about how models plan ahead and represent refusals informs where you place guardrails, even without a per-request explanation.

### Q12 — Your explanation surface is being used to reverse-engineer your fraud model. What now?
**Testing:** whether you anticipated explanation as an attack surface.
**Answer:** Two-tier explanations, by design and from day one. The internal reviewer gets the full trace: features, scores, thresholds, retrieved cases, tool results. The subject gets a reason code from a fixed, audited vocabulary ("insufficient transaction history", "device mismatch") plus an appeal route, with no thresholds, no scores, no rankings. Concretely, avoid emitting anything that makes the decision boundary queryable: no numeric scores, no "you were 0.02 away", no feature ordering, and rate-limit the explanation endpoint since repeated queries with perturbed inputs is a model-extraction attack. Also monitor for it — a spike in near-duplicate submissions from one account with systematic single-field variation is the observable symptom.
**Follow-up trap:** *"Does a reason code satisfy a right to explanation?"* — GDPR Article 22 and the AI Act require meaningful information about the logic involved and a route to human review, not disclosure of the model. Reason codes plus documented logic plus a real appeal path is the standard practice; a full faithful account of an adversarial model is neither required nor safe.

### Q13 — Rank explanation techniques by cost-per-explanation and say where each lives.
**Testing:** operational judgment, whether you can price your own recommendations.
**Answer:** Provenance (chunk ids, versions, tool args): ~0 marginal cost, always on, in the request path. NLI entailment per sentence: one small-model call per sentence, roughly 10-40ms on a hosted DeBERTa-size checker, in the request path for anything high-stakes. Chunk occlusion: `k+1` generation calls, seconds and cents, audit path and offline eval only. Self-consistency sampling: 5-20 extra generations, offline eval or high-value abstention decisions. SHAP on tabular components: hundreds to thousands of model evaluations, batch job. Attribution graphs: research-grade, incident forensics on models you own. The ranking is also a defaults recommendation: everything free is mandatory, everything per-request is conditional on stake, everything expensive is offline.
**Follow-up trap:** *"Which one would you cut first under a latency budget?"* — nothing free, obviously. The first real cut is per-sentence NLI, and the honest way to cut it is not to disable it but to make it asynchronous: serve the answer with citations marked "verifying", then downgrade or flag sentences that fail. That keeps p50 clean and preserves the verification signal, at the cost of a UI that can retract. Say the cost out loud.

### Q14 — When would you deliberately ship no explanation at all?
**Testing:** whether the "when NOT to" instinct is real.
**Answer:** When the stake is low and the volume is high, and the explanation would cost more than it returns: autocomplete, search ranking, a tag suggestion. When the decision is adversarial and the subject is the adversary, where a minimal reason code plus appeal beats a faithful account. When the only explanation you can produce is a plausible-but-unverifiable narrative, because shipping that is worse than shipping nothing — it manufactures confidence you have not earned, which is Rudin's 2019 argument and it has held up. And when the requirement is actually a guarantee rather than an explanation: if the ask is "must never contradict policy", build constrained generation plus verification and skip the essay.
**Follow-up trap:** *"Isn't 'no explanation' unacceptable for anything user-facing now?"* — provenance is not optional and I am not arguing against it. Citations, versions, and an "I don't know" are the floor. What I am declining to ship is a *rationale* — a narrative account of why. Those are different products and conflating them is how teams end up shipping CoT.

---

## Red flags that fail you

- Presenting chain-of-thought as an explanation of the model's computation, or citing it in an RCA.
- Proposing SHAP or LIME on an LLM's output without immediately naming the cost and the independence problem.
- Using "interpretability" and "explainability" interchangeably after being asked to distinguish them.
- Claiming attention weights show what the model looked at.
- "The EU AI Act requires explainable models." It requires transparency, documentation, and effective human oversight.
- Designing an explanation without naming the audience (user / reviewer / regulator) and what each needs.
- Not knowing that plausible explanations increase reliance on wrong answers, and shipping explanations with no eval on reviewer error-detection.
- Treating a citation that resolves to a real URL as a citation that supports the claim.
- Proposing mechanistic interpretability as a production explanation path in 2026.
- No versioning of model, prompt, tool schema, or index snapshot in the trace, so no explanation is replayable.

## Cheat card

```
INTERPRETABILITY = how the MODEL works (global, mechanism)
EXPLAINABILITY   = why THIS output (local, post-hoc)
FAITHFULNESS ⊥ PLAUSIBILITY — only plausibility is visible, so RLHF/AB tests
                              optimise the wrong one

STACK  L1 mechanistic (circuits, attribution graphs)   research only
       L2 model-behavioural (SHAP/LIME/IG)             tabular components only
       L3 SYSTEM TRACE                                 ✅ ship this — faithful by construction
       L4 user rationale + citations                   ✅ ship this — from L3 only
       CoT lives at L4, NOT L3

CoT UNFAITHFULNESS   Turpin 2023 arXiv:2305.04388  up to −36% acc, 13 BBH tasks
                     Anthropic 2505.05410  faithfulness 25% Claude 3.7 Sonnet / 39% R1
                                           20% / 29% on harmful hints; worse as task hardens
                     Arcuschin 2503.08679  unfaithful on natural prompts, no injected bias
                     Monitorability posn paper 2507.11473 (Jul 2025, multi-lab)
       CoT is causally load-bearing ≠ CoT is a faithful description

SHAP   exact = 2^|F| coalitions · TreeSHAP O(T·L·D²) exact & cheap
       KernelSHAP ≈ 2|F| + 2048 samples → ~3k fwd passes @512 tokens
       off-manifold masks + correlated tokens + scalar-only output → not for LLMs
LIME   seed-unstable top-k; kernel width σ has no principled default
IG     needs 20-300 steps + white-box grads; NO neutral text baseline

LLM ATTRIBUTION THAT WORKS
  provenance (chunk ids, versions, tool args)     cost ~0     always on
  NLI entailment per sentence                     ~10-40ms    high-stakes path
  chunk occlusion (necessity)                     k+1 gens    audit path
  + sufficiency (chunk alone) + closed-book baseline → 2k+2 gens, interpretable

TRACE MUST PIN  model@ver · prompt@ver · index snapshot id · tool schema ver
                retrieval query + doc ids + scores · tool args · guardrail verdicts
                store result HASH + 2KB prefix, not full payload

DOCS   model card = trained artefact (Mitchell 2019) · system card = deployed system
       generate from CI or it is stale in 2 sprints
       EU AI Act: Art 13 transparency, Art 14 oversight, Art 50 + GPAI docs → 2 Aug 2026
       penalties to €35M / 6-7% global turnover

TOOLS  traces LangSmith/Langfuse/Phoenix over OTel GenAI conventions (dev-stage, pin attrs)
       SHAP → shap.TreeExplainer on rerankers/CTR/fraud · captum IG on own encoders
       verify → Bedrock contextual grounding (>75% of hallucinations filtered),
                Automated Reasoning checks GA Aug 2025, up to 99% on formalised policy
       mech  → anthropic circuit-tracer (OSS May 2025), forensics not production

EXPLANATION IS AN ATTACK SURFACE → 2 tiers: full trace internal, reason code external
FIRST THING TO SHIP IF YOU GET ONE: versioned trace with citation locators
```

## Sources

- [Reasoning Models Don't Always Say What They Think (Chen et al., Anthropic, arXiv:2505.05410)](https://arxiv.org/pdf/2505.05410) — accessed 2026-07-26
- [Language Models Don't Always Say What They Think: Unfaithful Explanations in Chain-of-Thought Prompting (Turpin et al., arXiv:2305.04388)](https://arxiv.org/abs/2305.04388) — accessed 2026-07-26
- [Chain-of-Thought Reasoning In The Wild Is Not Always Faithful (arXiv:2503.08679)](https://arxiv.org/abs/2503.08679) — accessed 2026-07-26
- [Chain of Thought Monitorability: A New and Fragile Opportunity for AI Safety (arXiv:2507.11473)](https://arxiv.org/pdf/2507.11473) — accessed 2026-07-26
- [Is Chain-of-Thought Really Not Explainability? CoT Can Be Faithful without Hint Verbalization (arXiv:2512.23032)](https://arxiv.org/pdf/2512.23032) — accessed 2026-07-26
- [A Perspective on Explainable AI Methods: SHAP and LIME (Salih et al., Advanced Intelligent Systems, 2025)](https://advanced.onlinelibrary.wiley.com/doi/10.1002/aisy.202400304) — accessed 2026-07-26
- [Explainability of Large Language Models: Opportunities and Challenges toward Generating Trustworthy Explanations (arXiv:2510.17256)](https://arxiv.org/pdf/2510.17256) — accessed 2026-07-26
- [LLMs for Explainable AI: A Comprehensive Survey (arXiv:2504.00125)](https://arxiv.org/html/2504.00125v1) — accessed 2026-07-26
- [Article 14: Human Oversight — EU Artificial Intelligence Act](https://artificialintelligenceact.eu/article/14/) — accessed 2026-07-26
- [GPAI Model Card & Transparency Documentation: The Developer's Technical Guide (sota.io)](https://sota.io/blog/eu-ai-act-gpai-model-card-transparency-documentation-2026) — accessed 2026-07-26
- [AI System Cards Explained: The 2026 Transparency Standard](https://aibuzz.blog/ai-system-cards-explained/) — accessed 2026-07-26
- [Minimize AI hallucinations with Automated Reasoning checks — AWS News Blog](https://aws.amazon.com/blogs/aws/minimize-ai-hallucinations-and-deliver-up-to-99-verification-accuracy-with-automated-reasoning-checks-now-available/) — accessed 2026-07-26
- [Amazon Bedrock Guardrails](https://aws.amazon.com/bedrock/guardrails/) — accessed 2026-07-26
- [Circuit Tracing: A Step Closer to Understanding Large Language Models](https://towardsdatascience.com/circuit-tracing-a-step-closer-to-understanding-large-language-models/) — accessed 2026-07-26
- [AI Explainability: How to Avoid Rubber-Stamping Recommendations — MIT Sloan Management Review](https://sloanreview.mit.edu/article/ai-explainability-how-to-avoid-rubber-stamping-recommendations/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
