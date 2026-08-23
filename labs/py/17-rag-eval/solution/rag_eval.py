"""Lab 17 — mini-RAGAS: decomposed RAG eval with an injected stub judge.

Reference solution. Implements the RAGAS four-metric decomposition from
`T06-rag-eval` — context precision, context recall, faithfulness, answer
relevancy — plus an `eval_suite` runner. Every judgment goes through an
INJECTED judge object; the default `JudgeStub` is deterministic keyword
overlap (no LLM, no randomness, no network), so scores are reproducible and
the tests can pin exact values. A real LLM judge plugs into the same seam
and none of the metric code changes.

Case shape: EvalCase(question, answer, contexts, ground_truth).

Retrieval axis:
  context_precision(k) — of the top-k contexts retrieved, how many does the
                         judge rate relevant? (weighted keyword overlap with
                         question + ground truth; configurable weights)
  context_recall       — of the ground-truth sentences, how many are covered
                         by some context (>= min_shared_words shared content
                         words)? Low recall = retrieval failure, unfixable by
                         prompt tuning.
Generation axis:
  faithfulness         — decompose the answer into claim sentences; a claim is
                         supported if its best-context content-word overlap
                         clears support_threshold. High recall + low
                         faithfulness = the clearest hallucination signal.
  answer_relevancy     — the reversed judge: how much of the QUESTION do the
                         answer's terms touch, penalized by the answer's
                         generic-filler ratio (fluent waffle scores down).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- stopwords
# Provided lists — the lab's shared notion of "not a content word".
STOPWORDS = frozenset("""
a about above after again against all am an and any are as at be because been
before being below between both but by can could did do does doing down during
each few for from further had has have having he her here hers herself him
himself his how i if in into is it its itself just me more most my myself no
nor not now of off on once only or other our ours ourselves out over own same
she should so some such than that the their theirs them themselves then there
these they this those through to too under until up very was we were what when
where which while who whom why will with would you your yours yourself
yourselves
""".split())

# Vague grammatical filler — used ONLY by the answer-relevancy penalty.
GENERIC_FILLERS = frozenset("""
a an the and or but so because is are was were be been being am it its this
that these those there here to of in on at by for with from as just very
really quite rather some many much several various generally basically
essentially however therefore moreover furthermore etc
""".split())

_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_TOKEN_RE = re.compile(r"[a-z0-9]+")


# --------------------------------------------------------------------------- text ops
def tokenize(text: str) -> list[str]:
    """Lowercase word tokens: letters/digits only, punctuation is a boundary."""
    return _TOKEN_RE.findall(text.lower())


def content_words(text: str) -> list[str]:
    """Tokens that carry meaning: tokenize minus STOPWORDS."""
    return [t for t in tokenize(text) if t not in STOPWORDS]


def split_sentences(text: str) -> list[str]:
    """Split on . ! ? followed by whitespace (or end). Keeps punctuation."""
    text = text.strip()
    if not text:
        return []
    return [p.strip() for p in _SENTENCE_SPLIT.split(text) if p.strip()]


# --------------------------------------------------------------------------- case
@dataclass
class EvalCase:
    """One golden-set example: {question, answer, contexts[], ground_truth}."""
    question: str
    answer: str
    contexts: list[str] = field(default_factory=list)
    ground_truth: str = ""


# --------------------------------------------------------------------------- judge
class JudgeStub:
    """Deterministic stand-in for the LLM-as-judge.

    Every "judgment" in RAGAS is really a structured prompt to a model that
    rates relevance/support. Here that judgment is keyword overlap with
    configurable weights and thresholds — same shape of decision, zero noise.
    Swap this class for a real LLM judge and the metrics don't change.
    """

    def __init__(self,
                 question_weight: float = 1.0,
                 ground_truth_weight: float = 2.0,
                 relevance_threshold: float = 0.35,
                 support_threshold: float = 0.5,
                 min_shared_words: int = 2,
                 filler_penalty: float = 0.5) -> None:
        self.question_weight = question_weight
        self.ground_truth_weight = ground_truth_weight
        self.relevance_threshold = relevance_threshold
        self.support_threshold = support_threshold
        self.min_shared_words = min_shared_words
        self.filler_penalty = filler_penalty

    def context_relevance(self, question: str, ground_truth: str, context: str) -> float:
        """Weighted coverage of question-terms and ground-truth-terms by the
        context. Returns [0, 1]; weights are configurable knobs."""
        ctx = set(content_words(context))
        if not ctx:
            return 0.0
        q = set(content_words(question))
        g = set(content_words(ground_truth))
        q_cov = len(ctx & q) / len(q) if q else 0.0
        g_cov = len(ctx & g) / len(g) if g else 0.0
        total = self.question_weight + self.ground_truth_weight
        return (self.question_weight * q_cov + self.ground_truth_weight * g_cov) / total

    def is_context_relevant(self, question: str, ground_truth: str, context: str) -> bool:
        return self.context_relevance(question, ground_truth, context) >= self.relevance_threshold

    def sentence_covered(self, sentence: str, contexts: list[str]) -> bool:
        """A ground-truth sentence is covered if SOME context shares at least
        min_shared_words content words with it."""
        s = set(content_words(sentence))
        for ctx in contexts:
            if len(s & set(content_words(ctx))) >= self.min_shared_words:
                return True
        return False

    def claim_support(self, claim: str, contexts: list[str]) -> float:
        """Best single-context overlap for a claim: |claim ∩ ctx| / |claim|."""
        c = set(content_words(claim))
        if not c:
            return 0.0
        best = 0.0
        for ctx in contexts:
            ov = len(c & set(content_words(ctx))) / len(c)
            best = max(best, ov)
        return best

    def is_claim_supported(self, claim: str, contexts: list[str]) -> bool:
        return self.claim_support(claim, contexts) >= self.support_threshold

    def answer_relevancy_score(self, question: str, answer: str) -> float:
        """The reversed judge: fraction of the question's terms the answer
        touches, penalized by the answer's generic-filler ratio."""
        q = set(content_words(question))
        a = set(content_words(answer))
        if not q or not a:
            return 0.0
        overlap = len(a & q) / len(q)
        tokens = tokenize(answer)
        filler_ratio = sum(1 for t in tokens if t in GENERIC_FILLERS) / len(tokens)
        return max(0.0, min(1.0, overlap * (1.0 - self.filler_penalty * filler_ratio)))


# --------------------------------------------------------------------------- metrics
def context_precision(case: EvalCase, judge: JudgeStub | None = None, k: int = 2) -> float:
    """Fraction of the top-k retrieved contexts the judge rates relevant.
    Denominator is min(k, len(contexts)) — a short list isn't punished for
    slots it never filled. No contexts retrieved → 0.0."""
    judge = judge or JudgeStub()
    if not case.contexts:
        return 0.0
    top = case.contexts[:k]
    hits = sum(1 for c in top
               if judge.is_context_relevant(case.question, case.ground_truth, c))
    return hits / min(k, len(top))


def context_recall_detail(case: EvalCase, judge: JudgeStub | None = None) -> dict:
    """Coverage of ground-truth sentences plus WHICH sentences were missed."""
    judge = judge or JudgeStub()
    sentences = split_sentences(case.ground_truth)
    if not sentences:
        return {"score": 0.0, "uncovered_sentences": []}
    if not case.contexts:
        return {"score": 0.0, "uncovered_sentences": list(sentences)}
    flags = [judge.sentence_covered(s, case.contexts) for s in sentences]
    uncovered = [s for s, ok in zip(sentences, flags) if not ok]
    return {"score": sum(flags) / len(sentences), "uncovered_sentences": uncovered}


def context_recall(case: EvalCase, judge: JudgeStub | None = None) -> float:
    """Fraction of ground-truth sentences covered by some context."""
    return context_recall_detail(case, judge)["score"]


def faithfulness_detail(case: EvalCase, judge: JudgeStub | None = None) -> dict:
    """Supported/total claims plus the unsupported claim sentences."""
    judge = judge or JudgeStub()
    claims = split_sentences(case.answer)
    if not claims:
        return {"score": 0.0, "unsupported_claims": []}
    if not case.contexts:
        return {"score": 0.0, "unsupported_claims": list(claims)}
    flags = [judge.is_claim_supported(c, case.contexts) for c in claims]
    unsupported = [c for c, ok in zip(claims, flags) if not ok]
    return {"score": sum(flags) / len(claims), "unsupported_claims": unsupported}


def faithfulness(case: EvalCase, judge: JudgeStub | None = None) -> float:
    """Fraction of answer claim-sentences supported by the retrieved context."""
    return faithfulness_detail(case, judge)["score"]


def answer_relevancy(case: EvalCase, judge: JudgeStub | None = None) -> float:
    """Does the answer address the question asked? (Reversed judge direction.)
    Empty question or empty answer → 0.0."""
    judge = judge or JudgeStub()
    return judge.answer_relevancy_score(case.question, case.answer)


# --------------------------------------------------------------------------- suite
_METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")


def eval_suite(cases: list[EvalCase], judge: JudgeStub | None = None,
               k: int = 2) -> dict:
    """Run all four metrics per case, aggregate means, and rank worst cases
    ascending by faithfulness (stable sort — ties keep input order).

    Returns {n_cases, cases[...], aggregate{...}, worst_cases[...]}.
    """
    judge = judge or JudgeStub()
    case_reports = []
    for i, case in enumerate(cases):
        rec = context_recall_detail(case, judge)
        fai = faithfulness_detail(case, judge)
        case_reports.append({
            "index": i,
            "question": case.question,
            "context_precision": context_precision(case, judge, k=k),
            "context_recall": rec["score"],
            "faithfulness": fai["score"],
            "answer_relevancy": answer_relevancy(case, judge),
            "unsupported_claims": fai["unsupported_claims"],
            "uncovered_sentences": rec["uncovered_sentences"],
        })
    aggregate: dict = {"n_cases": len(case_reports)}
    for m in _METRICS:
        vals = [r[m] for r in case_reports]
        aggregate[m] = sum(vals) / len(vals) if vals else 0.0
    return {
        "n_cases": len(case_reports),
        "cases": case_reports,
        "aggregate": aggregate,
        "worst_cases": sorted(case_reports, key=lambda r: r["faithfulness"]),
    }
