# Federated Learning & On-Device AI: Training Without Centralizing Data

> **Track:** T09 MLOps / LLMOps · **Time:** 2h · **Prereqs:** `T03-classical-ml`, `T04-deep-learning` · **Updated:** 2026-10-31
> **Module id:** `T09-federated-learning` · **Tags:** privacy, training, advanced

## The 30-second version

Federated learning (FL) trains a model across decentralized devices (phones, hospitals, edge servers) without moving raw data to a central server. Each device trains locally on its data, sends model updates (gradients or weights) to a central aggregator (typically FedAvg), which averages them and sends the updated model back. The appeal: data stays local (privacy, regulatory compliance). The reality: FL is hard — heterogeneous data (non-IID), communication costs (model updates are large), stragglers (slow devices), and the fundamental tension between privacy and utility. On-device AI (running models on phones/edge) is the deployment side: quantized models (INT4/INT8), efficient architectures (MobileNet, EfficientNet, Phi-3-mini), and hardware acceleration (CoreML, NNAPI, Qualcomm AI Engine). The 2026 reality: FL is used in production by Apple (keyboard prediction, Siri), Google (Gboard), and healthcare (multi-hospital models). On-device LLMs (Phi-3-mini, Gemma 2B, Llama 3.2 1B/3B) run on phones. The key insight: FL trains without centralizing data; on-device AI runs without a server. Both are about keeping data local.

## Why this gets asked

Because privacy regulations (GDPR, HIPAA) make centralizing data expensive or illegal, and on-device AI is the fastest-growing deployment pattern. Interviewers probe: "how would you train a model across 10 hospitals without sharing patient data?" (answer: federated learning with FedAvg, differential privacy for gradient protection, secure aggregation). Also probed: "how do you run an LLM on a phone?" (answer: quantization to INT4, efficient architecture, hardware acceleration, KV cache optimization). The principal-level probe: "your healthcare app needs a personalized model per hospital but hospitals can't share data — design the system" (answer: federated learning with per-hospital fine-tuning on a shared base model, differential privacy for gradient protection, secure multi-party computation for aggregation).

## Lineage: past → present → future

**What came before.** Centralized training (2010s): collect all data in one place, train one model. The pain: data privacy (GDPR, HIPAA), data silos (hospitals, banks, devices), and the cost of moving large datasets. Federated learning was proposed by Google (McMahan et al., 2017) to solve the privacy problem: train locally, share updates, not data.

**Where it stands now.** FL is used in production: Apple (keyboard prediction, Siri personalization), Google (Gboard next-word prediction), healthcare (multi-hospital diagnostic models). On-device AI: quantized models (INT4/INT8) run on phones (Phi-3-mini, Gemma 2B, Llama 3.2 1B/3B). The 2026 landscape: FL is mature for simple models (linear, small NNs) but still hard for LLMs (communication cost of gradient updates is enormous). On-device LLMs are practical for 1-3B parameter models with 4-bit quantization. The live disagreement: whether FL + differential privacy can achieve sufficient utility for complex models, or whether the privacy-utility tradeoff is too steep.

**Where it's heading.** High confidence: on-device AI (quantized small models) becomes standard for mobile/edge. Medium confidence: FL becomes practical for LLMs as communication-efficient methods (gradient compression, sparse updates) improve. Speculative: fully private ML (FL + differential privacy + secure aggregation + TEEs) becomes the default for regulated industries, but the utility cost remains the limiting factor.

## Mental model

```
FEDERATED LEARNING (FedAvg):
  ┌─────────┐  ┌─────────┐  ┌─────────┐
  │ Device 1│  │ Device 2│  │ Device 3│  (local data stays here)
  │ train   │  │ train   │  │ train   │
  │ locally │  │ locally │  │ locally │
  └────┬────┘  └────┬────┘  └────┬────┘
       │ Δw₁        │ Δw₂        │ Δw₃
       └────────────┼────────────┘
                    ▼
              ┌───────────┐
              │ Aggregator│  w_new = (w₁ + w₂ + w₃) / 3
              │ (FedAvg)  │
              └─────┬─────┘
                    │ w_new
                    ▼
              ┌───────────┐
              │ All devices│  receive updated model
              │            │
              └───────────┘

ON-DEVICE AI (deployment):
  Cloud model (32-bit, 70B params) ──► Quantize to INT4 ──► 8B params ──► Phone (NPU/GPU)
  Optimizations: KV cache compression, speculative decoding, flash attention, operator fusion
```

## Recognition heuristics

- **"Train a model across hospitals without sharing patient data"** → federated learning (FedAvg) + differential privacy (gradient noise) + secure aggregation (encrypted updates).
- **"Run an LLM on a phone"** → quantize to INT4 (GPTQ/AWQ), efficient architecture (1-3B params), hardware acceleration (CoreML/NNAPI), KV cache compression.
- **"Non-IID data in FL"** → FedProx (proximal term), SCAFFOLD (control variates), or personalized FL (per-client fine-tuning on shared base).
- **"Communication cost in FL"** → gradient compression (top-k sparsification, quantization), fewer rounds (more local epochs), or split learning (send activations, not gradients).

## Common bugs and how these get shipped wrong

- **Ignoring non-IID data.** FedAvg assumes IID data across clients. Real data is non-IID (hospital A has more diabetes cases, hospital B has more heart disease). Fix: FedProx (proximal term to prevent client drift), SCAFFOLD (control variates), or personalized FL.
- **Not accounting for communication cost.** Sending a 7B model's gradients (28GB at FP32) per round is impractical. Fix: gradient compression (top-k, quantization), fewer rounds with more local epochs.
- **Forgetting stragglers.** Slow devices (old phones, weak networks) delay aggregation. Fix: asynchronous FL (FedAsync), timeout-based aggregation, or client selection.
- **Assuming FL = privacy.** FL prevents raw data sharing but model updates can leak information (membership inference, gradient inversion). Fix: differential privacy on gradients, secure aggregation (encrypted updates).

## Interview questions

1. **"How would you train a model across 10 hospitals without sharing patient data?"** Answer: federated learning (FedAvg) — each hospital trains locally, sends model updates (not data) to aggregator. Add differential privacy (gradient noise) for privacy guarantee. Add secure aggregation (encrypted updates) so aggregator can't see individual updates. Handle non-IID data with FedProx or personalized FL.
2. **"How do you run an LLM on a phone?"** Answer: (1) Quantize to INT4 (GPTQ/AWQ, ~4x smaller). (2) Use efficient architecture (1-3B params, Phi-3-mini/Gemma 2B). (3) Hardware acceleration (CoreML/NNAPI/Qualcomm AI Engine). (4) KV cache compression (reduce memory). (5) Speculative decoding with a tiny draft model. Target: 10-20 tok/s on modern phones.
3. **"What's the privacy-utility tradeoff in FL?"** Answer: differential privacy adds noise to gradients, which reduces model quality. More noise = more privacy but worse model. The tradeoff is quantified by epsilon (privacy budget): smaller epsilon = more privacy = more noise = worse utility. In practice, epsilon=1-10 is common, with measurable utility loss.

## Red flags that fail you

- "FL is fully private" — model updates can leak information. Need differential privacy + secure aggregation.
- "FL works the same as centralized training" — non-IID data, communication cost, and stragglers make FL fundamentally harder.
- "Any model runs on a phone" — need quantization + efficient architecture + hardware acceleration.
- Not knowing the privacy-utility tradeoff (epsilon, noise, utility loss).

## Cheat card

- FL = train locally, share updates (not data). FedAvg = average model weights.
- Privacy: differential privacy (gradient noise) + secure aggregation (encrypted updates).
- Non-IID: FedProx (proximal term), SCAFFOLD (control variates), personalized FL.
- On-device: quantize to INT4 (GPTQ/AWQ), efficient arch (1-3B), hardware accel (CoreML/NNAPI).
- KV cache compression + speculative decoding for on-device LLM speed.
- Epsilon = privacy budget. Smaller = more privacy = more noise = worse utility.

## Sources

- [Communication-Efficient Learning of Deep Networks from Decentralized Data (FedAvg, McMahan et al., 2017)](https://arxiv.org/abs/1602.05629) — accessed 2026-10-31
- [Federated Learning: Challenges, Methods, and Future Directions (Kairouz et al., 2021)](https://arxiv.org/abs/1912.04977) — accessed 2026-10-31
- [Phi-3 Technical Report (Microsoft)](https://arxiv.org/abs/2404.14219) — accessed 2026-10-31
- [Gemma 2 Technical Report (Google)](https://arxiv.org/abs/2408.00118) — accessed 2026-10-31

## Changelog

- 2026-10-31: Created — Federated Learning / On-Device AI identified as a gap (no dedicated module).
