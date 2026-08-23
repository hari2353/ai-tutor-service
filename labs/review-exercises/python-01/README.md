# Review Exercise PY-01: Triage This Diff

**Track:** T00 Code Review & Judgment · **Time:** 45min · **XP:** 50
**Modules:** cross-track — see the rubric

This lab has **no tests directory and no starter/solution split** — the lab runner skips it. Your deliverable is a written review, not code.

## The brief

`DIFF.md` contains a proposed change to `metrics-api`, a small FastAPI + ClickHouse service that exposes product metrics. It was written by a well-meaning teammate under deadline pressure. It merges tomorrow unless you block it.

Run `/tutor-review` on `DIFF.md`:

```bash
/tutor-review DIFF.md
```

and produce a findings report. For **each** finding give:

1. **Location** — file + line reference from the diff
2. **Severity** — `P0` (ship-blocker: data loss, security, outage), `P1` (must fix before merge: correctness/availability risk under realistic load), `P2` (should fix: latent bug or debt)
3. **Why it bites in prod** — the concrete failure scenario, not the textbook definition
4. **The fix** — one or two sentences, as you'd leave it on the PR
5. **Curriculum module ref** — which module teaches this

## Rules of engagement

- Exactly **8 planted defects** are in the diff. Find as many as you can.
- Style nits are not defects. Don't pad the report.
- If you claim a defect, point at the line. No vibes-based findings.
- 8/8 with severity right is a strong senior signal; 8 found but all mislabelled P2 is not.

## Grading guide

| Outcome | Signal |
|---|---|
| Found < 3 of the P0s | **NO HIRE signal** — cannot triage severity |
| All P0s found + ≥ 6 total, severities sane | HIRE signal |
| All 8 found, correct severity, crisp prod scenarios | STRONG HIRE signal |
| Long list, no severities, style nits padded in | LEAN NO HIRE — activity ≠ judgment |

Check yourself against `EXPECTED-FINDINGS.md` **after** writing your own report first.
