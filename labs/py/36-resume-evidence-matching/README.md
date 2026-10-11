# Lab 36: Resume Evidence Matching

**Track:** T15 Interview Simulator · **Time:** 2h · **XP:** 50
**Module:** `T15-resume-ats-evidence`

**You will build:** a pure-stdlib matcher that extracts technical evidence terms from a resume and explains which JD requirements lack proof.

**You will be able to answer:** *"How did you tailor the resume without claiming work you did not personally do?"*

## Setup

```bash
cd labs/py/36-resume-evidence-matching
python -m venv .venv && .venv/Scripts/activate
pip install pytest
```

The implementation uses only the standard library. No network, files, sleeping, randomness, or third-party parser is allowed.

## The spec

Implement `resume_match.py`:

1. `normalize_term(term)` case-folds, collapses whitespace, and removes punctuation at phrase boundaries without destroying internal `+`, `#`, or `-` technical characters.
2. `extract_terms(resume_text, terms)` returns the requested terms that occur as normalized phrases in the resume, without treating a substring inside a larger word as a match.
3. `match_requirements(resume_text, requirements)` returns `MatchResult` rows with matched terms, evidence snippets, and missing requirements. A requirement may include `synonyms` but must retain its canonical name.
4. `explain_missing(result)` returns a deterministic explanation that names each missing canonical requirement and says that a truthful evidence sentence or learning task is needed; it must not claim the candidate has the skill.
5. Use dataclasses and deterministic ordering. Empty requirements and invalid values should raise `ValueError`.

## Run the tests

```bash
pytest tests/ -q                 # starter: MUST FAIL
pytest tests/ -q --solution      # reference: MUST PASS
```

## Stretch goals

1. Add proof dimensions for mechanism, result, ownership, and tradeoff. *(Interview: "What makes a match defensible?")*
2. Add a role-specific variant generator from a canonical evidence ledger. *(Interview: "How do you keep tailored resumes consistent?")*
3. Add a redaction pass for company and customer names before sharing a match report. *(Interview: "How do you protect confidential interview material?")*
