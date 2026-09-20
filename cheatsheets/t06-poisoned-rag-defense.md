# RAG Poisoning Defense - cheat sheet
> Sources: `T06-poisoned-rag-defense` · generated 2026-09-20

## Say this first
RAG poisoning is an integrity attack: attacker-controlled text is engineered to retrieve for a target question and steer the answer. Relevance and reranking do not establish truth, so the defense needs provenance, source authority, isolated claim extraction, deterministic conflict resolution, quarantine, and rollback. When trusted evidence conflicts or the attack has not been validated, abstain rather than return an untraceable confident answer.

## Numbers
| What | Value | Why it matters |
|---|---:|---|
| PoisonedRAG reported attack success | 90% | 5 injected texts per target question in its evaluated setting |
| Resolver outcomes | 5 | correct, attacked, hedged, abstained, failed |
| Required gate | attack landing | zero success is meaningless if poison never retrieved |
| Required evidence | source/version/range | answer must be auditable |
| Trust decision | authority != similarity | embeddings measure relevance, not truth |

## Decision rules
- **Use authority resolution** when sources disagree. **Use majority only** when votes are independent and authenticated. **Neither** when provenance is missing.
- **Isolate claims** before resolving. **Never let** passages debate or authorize one another in one prompt.
- **Quarantine** unapproved or suspicious versions. **Invalidate** cache entries by source dependency.

## The mechanism, in one diagram
```text
retrieve -> verify landing -> isolate claims -> authority resolver
                                      |             |
                                  provenance   answer / abstain
```

## Failure modes
| Symptom | Cause | Fix |
|---|---|---|
| Three poisons outvote policy | vote count is attacker-controlled | rank by tier, not copies |
| 0% attack success | poison never reached reader | add landing gate |
| faithful wrong answer | retrieved text was malicious | evaluate source integrity, not only faithfulness |
| unknown blast radius | missing provenance/trace | store source/version/claim/citation joins |

## Traps
- Citation means truth → citation proves support by text, not source authority.
- Lower the classifier threshold → overlapping distributions need structural controls, not threshold tuning.

## Do not say
- “We tell the model to ignore document instructions.” Say: “The model is not the security boundary; provenance, permissions, quarantine, and the resolver are.”
