# Trajectory Eval, Tool-Call Accuracy, Task Completion, Cost/Step

> Sprint weekend 7 · source: `curriculum/08-eval-observability/04-agent-eval.md`

```
WHY OUTCOME-ONLY FAILS   right destination/wrong path · lucky one-off success ·
                         agent self-reports success that didn't actually happen

LAYERS                   1. tool-call accuracy    (binary, per call, deterministic
                            where possible; verifier fn for open-ended args)
                         2. trajectory eval        (golden fuzzy-match: required/
                            forbidden/optional calls; OR llm-judge, 6 dims scored
                            independently: tool selection, arg extraction, result
                            use, error recovery, plan coherence, task completion)
                         3. task completion        vs ACTUAL STATE, never agent's
                            own summary text
                         4. cost/steps per task     $ + tokens + steps, p50 AND p95,
                            first-class metric alongside accuracy every run

GOLDEN TRAJECTORIES      build from real/expert runs, human-edited to canonical ·
                         annotate required / forbidden / order-independent calls ·
                         cover POLICY EDGE CASES + induced-failure recovery, not
                         just happy path · version alongside tool schemas

NONDETERMINISM           pass@1 = success in >=1 of k tries (optimistic)
                         pass^k = ALL k tries succeed (honest reliability number)
                         reported gap: pass^1 ~70-80% -> pass^8 <25% (tau-bench,
                         realistic multi-turn retail tasks)
                         run N>=3-5 repeats before calling ANYTHING a regression

CI GATES                 hard-gate deterministic checks (tool-call acc, state)
                         statistical-gate judge-based checks (drop across a run-
                         set, not one trace) · pin agent AND judge model versions
                         · quarantine known-flaky tasks, don't let them block

BENCHMARK SHAPE          tau-bench / tau2-bench: real mutable backend + policy
                         doc + simulated user, pass^k built in — imitate this
                         shape for your own domain, don't just cite the score

TOOLS                    LangSmith (LangGraph-native, node diffs, replay) ·
                         Braintrust (dataset+score+monitor+CI in one) ·
                         Arize Phoenix (OTel-native tracing, drift detection)
```
