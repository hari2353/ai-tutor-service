# Lab 17: Mini-RAGAS — Decomposed RAG Eval With a Stub Judge From Scratch

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **XP:** 50
**Module:** `T06-rag-eval`

**You will build:** the RAGAS four-metric decomposition — context precision@k, context recall, faithfulness, answer relevancy — plus an `eval_suite` runner with aggregate means and a worst-cases ranking, all scored through an **injected stub judge**: deterministic keyword overlap standing in for the LLM, so every score is exactly reproducible and test-pinnable.

**You will be able to answer:** *"Walk me through RAGAS's four metrics — and why is a high faithfulness with low context recall (or the reverse) the interesting signal?"*

## Setup

```bash
cd labs/py/17-rag-eval
python -m venv .venv && . .venv/bin/activate     # or: uv venv && . .venv/bin/activate
pip install pytest                                # only dependency
```

## The spec

One `EvalCase(question, answer, contexts[], ground_truth)` per golden-set example. All judgment flows through an injected judge; `JudgeStub` is the deterministic default. `STOPWORDS` and `GENERIC_FILLERS` are provided.

1. **Text ops** — `tokenize` (lowercase `[a-z0-9]+`, punctuation is a boundary), `content_words` (minus stopwords), `split_sentences` (`.`/`!`/`?` + whitespace, punctuation kept).
2. **`JudgeStub.context_relevance(q, gt, ctx)`** — weighted coverage of question terms and ground-truth terms by the context: `(qw·q_cov + gw·g_cov) / (qw + gw)`. Weights are knobs (`question_weight=1.0`, `ground_truth_weight=2.0`); `is_context_relevant` cuts at `relevance_threshold=0.35`.
3. **`context_precision(case, k)`** — fraction of the top-k contexts rated relevant; denominator `min(k, len(contexts))`; no contexts → `0.0`.
4. **`context_recall_detail(case)`** — split ground truth into sentences; a sentence is covered if SOME context shares ≥ `min_shared_words=2` content words. Returns score + the exact uncovered sentences.
5. **`faithfulness_detail(case)`** — decompose the answer into claim sentences; a claim is supported if its best single-context overlap `|claim∩ctx| / |claim|` clears `support_threshold=0.5`. Returns supported/total + the verbatim unsupported claims. Empty contexts or empty answer guard to `0.0`.
6. **`answer_relevancy(case)`** — the reversed judge direction: `|answer_terms ∩ question_terms| / |question_terms|`, penalized by the answer's generic-filler ratio via `filler_penalty=0.5`; empty question/answer → `0.0`.
7. **`eval_suite(cases, k)`** — per-case rows (all four scores + flagged claims/sentences), aggregate mean per metric, and `worst_cases` sorted ascending by faithfulness (stable).

## Run the tests

```bash
pytest tests/ -v          # against starter/ → FAILS. Make them pass.
```

To check the reference: `pytest tests/ -v --solution`

The perfect-RAG fixture prints its exact scores under `-s`: all four metrics land on `1.0`.

## Stretch goals

1. **Rank-weighted precision** — replace precision@k with RAGAS's average-precision formula (`Σ precision@i · rel_i / Σ rel_i`) and show relevant-at-rank-1 beats relevant-at-rank-3. *(Interview: "why reward early rank?")*
2. **Judge calibration harness** — score a labeled subset under two judge configs and report agreement per metric; that's the human-calibration workflow from the curriculum with the LLM swapped out.
3. **Synthetic-question trap demo** — paraphrase questions away from source-chunk vocabulary and watch stub relevance (and a real retriever's) fall; quantify how much lexical overlap was carrying the score.
4. **CI regression gate** — persist `eval_suite` output as JSON and fail the build when any aggregate drops more than a threshold vs a checked-in baseline (per curriculum Q14).
