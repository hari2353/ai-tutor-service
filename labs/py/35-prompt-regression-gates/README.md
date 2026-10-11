# Lab 35: Prompt Regression Gates

**Track:** T08 Eval & Observability · **Time:** 2.5h · **XP:** 50
**Module:** `T08-prompt-regression-gates`

**You will build:** a deterministic golden-case scorer with slice thresholds and baseline regression detection.

**You will be able to answer:** *"How do you stop a prompt change from improving the aggregate while breaking a critical slice?"*

## Setup

```bash
cd labs/py/35-prompt-regression-gates
python -m venv .venv && .venv/Scripts/activate
pip install pytest
```

The implementation uses only the Python standard library. Tests do not call a model, sleep, use randomness, read files, or access a network.

## The spec

Implement `prompt_gates.py`:

1. `GoldenCase` stores a stable `id`, `prompt`, `slice_name`, required evidence terms, and an optional `critical` flag.
2. `score_case(case, output)` passes only when every required term occurs in the output using case-insensitive phrase matching. Return a `CaseResult` containing matched and missing terms.
3. `aggregate(results)` returns overall pass rate and per-slice pass rates. Reject an empty result set.
4. `evaluate_gate(results, baseline_slices, overall_threshold, slice_thresholds, max_slice_drop=0.0, min_slice_cases=1)` passes only when the overall threshold, each configured slice threshold, minimum sample counts, and baseline drop limits pass.
5. The gate must report failing slices and regression slices, not only a boolean.

## Run the tests

```bash
pytest tests/ -q                 # starter: MUST FAIL
pytest tests/ -q --solution      # reference: MUST PASS
```

## Stretch goals

1. Add confidence intervals without changing the deterministic gate result. *(Interview: "How do you set a threshold above noise?")*
2. Add a held-out flag and prevent active-set cases from being used as a baseline. *(Interview: "How do you detect prompt overfitting?")*
3. Add a JSON report serializer with dataset, prompt, and model version fields. *(Interview: "What makes an eval result reproducible?")*
