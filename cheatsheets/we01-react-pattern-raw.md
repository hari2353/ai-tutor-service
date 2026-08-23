# ReAct Implemented Raw + Plan-Execute + Reflexion

> Sprint weekend 1 · source: `curriculum/07-agentic-ai/02-react-pattern-raw.md`

```
THE AXIS: where is the decision point vs the observations?
  ReAct        decide AFTER each obs   · adaptive · quadratic ctx · n round trips
  Plan-Execute decide BEFORE any obs   · 0.4-0.7x tokens · parallel · plan lock-in
  Reflexion    decide AGAIN after fail · needs a REAL verdict · cap 2-3 attempts
  ToT/self-cons decide ACROSS branches · 10-100x tokens · needs a node scorer

REACT 2026 = thinking block + tool_use block + tool_result block
  NOT regex on "Thought:/Action:". parse-failure rate 2-8% -> 0.
  KEEP the reasoning block in history, else you re-implement act-only (the ablation).
  cost of the trace: thought_len x n(n+1)/2 input tokens. 120 tok x 10 steps = 6,600.

PAPER NUMBERS (know cold)
  ReAct (Yao 2022/ICLR23): +34% abs ALFWorld, +10% WebShop, 1-2 shot
  Reflexion (Shinn 2023):  91% pass@1 HumanEval (GPT-4: 80%) <- verdict = unit tests
                           130/134 ALFWorld ~97% in 12 trials (ReAct 75%)
                           HotpotQA 61% -> 75% EM
  ToT (Yao 2023):          Game of 24: 74% vs CoT 4%. cheap verifier + tiny branching.
  Huang ICLR24:            INTRINSIC self-correct doesn't reliably improve, sometimes
                           degrades. many reported gains = weak initial prompt.
  Self-consistency 2026:   Gemini-2.5-Flash-Lite HotpotQA +0.4% @ 20 samples (20x cost)
                           Gemini-2.5-Pro MATH-500 98 -> 99.6% @ 15x
                           DECLINES past 15 samples. negative, not just diminishing.
  Adaptive-consistency:    7.9x fewer samples, <0.1% accuracy loss
  ReWOO:                   30-50% fewer tokens than ReAct
  arXiv 2509.03581:        ALWAYS planning degrades long-horizon; never planning limits

DECISION RULE
  later steps depend on earlier RESULTS?  yes -> ReAct
    no + decomposition stable up front?   yes -> Plan-Execute/ReWOO + a GATE
  cheap external verdict exists?          yes -> retry-with-critique, cap 2-3
                                          no  -> DO NOT add self-critique
  single-pass acc well below ceiling AND nodes cheaply scoreable? -> self-cons k=3-5
  default: plain ReAct loop. add one pattern at a time, eval each.

VERDICT SOURCES, best to worst
  compiler/tests/typecheck/schema/EXPLAIN > invariants+row-count bounds
  > a DIFFERENT model as judge > same model "are you sure?" (~worthless, harmful)

MEASURE THE LOOP: help rate (wrong->right) · harm rate (right->wrong)
  · cost per NET-CORRECT.  harm >= help = random-answer-perturber.

FAILURE SYMPTOMS
  plan lock-in:  plan_hash constant, replan_count==0, answer cites a missing entity
  degeneration:  cos(reflect_k, reflect_k-1) > 0.9, flat pass rate, linear tokens
  act-only drift: reasoning block dropped from history; repeats prior action
  fabricated obs: Observation: line with no matching tool log (2022 impl, no stop seq)

REASONING MODELS: absorbed the THOUGHT half. not the ACT/OBSERVE half.
  gone:  external ToT, self-consistency (math/code), introspection-only critique
  yours: side effects, real verifiers, durable state, budgets, stop conditions
```
