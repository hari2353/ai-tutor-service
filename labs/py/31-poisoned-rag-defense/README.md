# Lab 31: Poisoned RAG Defense

**Track:** T06 RAG (Retrieval-Augmented Generation) · **Time:** 2h · **XP:** 50
**Module:** `T06-poisoned-rag-defense`

**You will build:** a deterministic claim resolver that deduplicates equivalent values, ignores unapproved evidence, and chooses by source authority rather than attacker-controlled vote count.

**You will be able to answer:** *"How do you keep three poisoned documents from outvoting one authoritative policy?"*

## Setup

```bash
cd labs/py/31-poisoned-rag-defense
python -m venv .venv && . .venv/bin/activate
pip install pytest
```

## The spec

Implement `resolver.py` with these behaviors:

1. `Claim(value, source_id, tier, approved=True)` is immutable data. `tier` is an integer; higher means more authoritative.
2. `normalize_value(value)` compares numbers independent of commas, currency symbols, and surrounding whitespace, while preserving ordinary text values.
3. `resolve_claims(claims)` returns a `Decision` with `status` in `answered`, `hedged`, or `abstained`, the normalized value or `None`, and source IDs used.
4. Ignore claims with `approved=False` and claims whose value is empty. If no usable claims remain, abstain.
5. Equivalent values form one group. One agreement among approved claims answers directly.
6. For conflicting values, a strictly higher tier wins only if it is unique at the highest tier. Equal-tier conflicts abstain.
7. Never use claim count as authority. Three tier-0 copies must not defeat one tier-3 policy.
8. Preserve deterministic source ordering in the decision so the result is reproducible.

## Run the tests

```bash
pytest tests/ -q                 # starter: MUST FAIL
pytest tests/ -q --solution      # reference: MUST PASS
```

## Stretch goals

1. Add a policy version to `Decision` and reject mixed policy versions. *(Interview: "How do you audit which rule selected the answer?")*
2. Add an `attack_landed` flag and refuse to score a poisoning experiment when the injected claim never reached top-k. *(Interview: "Why is zero attack success not enough?")*
3. Add provenance hashes and quarantine states. *(Interview: "How do you roll back a poisoned document version?")*
