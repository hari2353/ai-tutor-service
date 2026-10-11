# Production notes - resume evidence matching

The lab is intentionally conservative: it matches reviewed phrase terms and returns source-line evidence, but it never infers personal experience from similarity. Production adds PDF/DOCX parsing, section detection, a controlled skills taxonomy, synonym review, provenance spans, versioned evidence ledgers, redaction, and human approval.

| Lab concept | Production addition |
|---|---|
| `Requirement` | JD taxonomy with required/preferred priority and reviewed synonyms |
| Phrase matching | Parser plus phrase/entity matching with source offsets and confidence |
| `MatchResult` | Evidence graph linking role capability to canonical resume claim and ownership |
| Missing explanation | Learning queue or confirmation task, never an invented claim |
| Resume text | Versioned canonical ledger and generated role-specific variants |

An ATS-like score is a triage signal, not a hiring probability. Keep the original sentence for every match so a human can distinguish personal implementation from team context.
