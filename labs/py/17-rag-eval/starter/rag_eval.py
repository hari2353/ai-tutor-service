"""Lab 17 — mini-RAGAS: decomposed RAG eval with an injected stub judge.

Fill in every TODO. Tests define done.

Rules:
  * Every judgment goes through the injected JudgeStub — metrics never inspect
    strings directly. A real LLM judge plugs into the same seam.
  * The judge is deterministic: no random, no time, no network. Scores must be
    exactly reproducible so the tests can pin values.

Case shape: EvalCase(question, answer, contexts[], ground_truth).

Retrieval axis:
  context_precision(k) — of top-k contexts, how many does the judge rate
                         relevant? (weighted overlap vs question + ground truth)
  context_recall       — ground-truth sentences covered by some context
                         (>= min_shared_words shared content words).
Generation axis:
  faithfulness         — answer claim-sentences supported by best context;
                         score = supported / total; list unsupported claims.
  answer_relevancy     — reversed judge: answer/question term overlap,
                         penalized by generic-filler ratio.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# --------------------------------------------------------------------------- stopwords
# PROVIDED — the lab's shared notion of "not a content word".
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

# PROVIDED — vague grammatical filler, used ONLY by the relevancy penalty.
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
    # TODO(step 1): _TOKEN_RE.findall(text.lower())
    raise NotImplementedError


def content_words(text: str) -> list[str]:
    """Tokens that carry meaning: tokenize minus STOPWORDS."""
    # TODO(step 1)
    raise NotImplementedError


def split_sentences(text: str) -> list[str]:
    """Split on . ! ? followed by whitespace (or end). Keeps punctuation.
    Empty/whitespace-only input -> []."""
    # TODO(step 1)
    raise NotImplementedError


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
    """Deterministic stand-in for the LLM-as-judge: keyword overlap with
    configurable weights and thresholds. Same decision shape as a real judge,
    zero noise."""

    def __init__(self,
                 question_weight: float = 1.0,
                 ground_truth_weight: float = 2.0,
                 relevance_threshold: float = 0.35,
                 support_threshold: float = 0.5,
                 min_shared_words: int = 2,
                 filler_penalty: float = 0.5) -> None:
        # TODO(step 2): store all six knobs on self
        raise NotImplementedError

    def context_relevance(self, question: str, ground_truth: str, context: str) -> float:
        """Weighted coverage of question-terms and ground-truth-terms by the
        context: (qw * q_cov + gw * g_cov) / (qw + gw). [0, 1]. Empty context
        scores 0.0."""
        # TODO(step 2): sets of content words; coverage = |ctx & side| / |side|
        raise NotImplementedError

    def is_context_relevant(self, question: str, ground_truth: str, context: str) -> bool:
        # TODO(step 3): context_relevance >= relevance_threshold
        raise NotImplementedError

    def sentence_covered(self, sentence: str, contexts: list[str]) -> bool:
        """True if SOME context shares >= min_shared_words content words."""
        # TODO(step 4)
        raise NotImplementedError

    def claim_support(self, claim: str, contexts: list[str]) -> float:
        """Best single-context overlap |claim & ctx| / |claim|. Empty claim -> 0.0."""
        # TODO(step 5)
        raise NotImplementedError

    def is_claim_supported(self, claim: str, contexts: list[str]) -> bool:
        # TODO(step 5): claim_support >= support_threshold
        raise NotImplementedError

    def answer_relevancy_score(self, question: str, answer: str) -> float:
        """Reversed direction: overlap = |ans_terms & q_terms| / |q_terms|,
        then score = clamp(overlap * (1 - filler_penalty * filler_ratio)).
        filler_ratio = share of RAW tokens in GENERIC_FILLERS.
        Empty question or empty answer -> 0.0."""
        # TODO(step 6)
        raise NotImplementedError


# --------------------------------------------------------------------------- metrics
def context_precision(case: EvalCase, judge: JudgeStub | None = None, k: int = 2) -> float:
    """Fraction of the top-k contexts rated relevant. Denominator is
    min(k, len(contexts)). No contexts -> 0.0."""
    # TODO(step 3)
    raise NotImplementedError


def context_recall_detail(case: EvalCase, judge: JudgeStub | None = None) -> dict:
    """{"score": covered/total, "uncovered_sentences": [...]}. No ground-truth
    sentences -> score 0.0 with nothing listed. Sentences but no contexts ->
    score 0.0 with EVERY sentence listed."""
    # TODO(step 4)
    raise NotImplementedError


def context_recall(case: EvalCase, judge: JudgeStub | None = None) -> float:
    """Fraction of ground-truth sentences covered by some context."""
    # TODO(step 4): delegate to context_recall_detail
    raise NotImplementedError


def faithfulness_detail(case: EvalCase, judge: JudgeStub | None = None) -> dict:
    """{"score": supported/total claims, "unsupported_claims": [...]}. No
    claims -> score 0.0, nothing listed. Claims but no contexts -> score 0.0,
    every claim listed."""
    # TODO(step 5)
    raise NotImplementedError


def faithfulness(case: EvalCase, judge: JudgeStub | None = None) -> float:
    """Fraction of answer claim-sentences supported by retrieved context."""
    # TODO(step 5): delegate to faithfulness_detail
    raise NotImplementedError


def answer_relevancy(case: EvalCase, judge: JudgeStub | None = None) -> float:
    """Does the answer address the question asked? (Reversed judge direction.)"""
    # TODO(step 6): judge.answer_relevancy_score(case.question, case.answer)
    raise NotImplementedError


# --------------------------------------------------------------------------- suite
_METRICS = ("context_precision", "context_recall", "faithfulness", "answer_relevancy")


def eval_suite(cases: list[EvalCase], judge: JudgeStub | None = None,
               k: int = 2) -> dict:
    """Run all four metrics per case, aggregate means, rank worst cases
    ascending by faithfulness (stable sort). Returns
    {n_cases, cases[...], aggregate{...}, worst_cases[...]} where each case row
    carries index, question, all four scores, unsupported_claims and
    uncovered_sentences."""
    # TODO(step 7)
    raise NotImplementedError
