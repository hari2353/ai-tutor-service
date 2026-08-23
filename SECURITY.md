# Security & Privacy

## What this repo is

A personal interview-preparation system containing **resume-derived content** — real
project numbers, employer names, incident narratives, and a live job-application queue.
There are no production credentials anywhere (enforced by `scripts/security_check.py`,
wired into the test suite), but the *content itself* is private-personal.

## Privacy classification

| Class | Paths | Rule |
|---|---|---|
| NEVER COMMIT | `interview_prep_queue.json` | gitignored; verified absent from all history by the security check |
| PERSONAL — private remote only | `progress/`, `mocks/`, `curriculum/10-system-design/09-resume-systems.md`, `curriculum/14-behavioral-principal/01-star-bank.md` (real numbers behind `[CONFIRM]`), personal email in `COMMIT.md` | Fine in a **private** repo; scrub before ever making public |
| PUBLIC-SAFE | everything else (`app/`, `curriculum/` technical content, `labs/`, `skills/`, `docs/`) | Generic teaching material |

## Secret scanning

`python scripts/security_check.py`

- **Hard-fail patterns:** AWS keys, GitHub/Slack/OpenAI/Anthropic token shapes,
  Google API keys, PEM private-key blocks, credentials-in-URLs.
- **Teaching-artifact allowlist:** placeholder PEM annotations ("never leaves this
  workload") and dotless-docker-hostname dev URLs (`postgres:devpass@db`) are the
  documented exceptions — the auth curriculum must be allowed to show what
  credential shapes look like without tripping the gate.
- **Warnings:** generic `secret="..."`-style assignments that self-identify as demos.
  Reviewed, not silenced.

The scan runs as part of `app/tests/run.ps1`, so ALL GREEN includes a secure tree.

## Pre-upload checklist

1. [ ] Remote is **private**: `gh repo create hari2353/ai-tutor-service --private`
   (or Settings → Change visibility → Private).
2. [ ] `python scripts/security_check.py` exits 0 (part of run.ps1).
3. [ ] `git log --all --name-only | Select-String interview_prep_queue` → empty
       (the script asserts this too).
4. [ ] If ever making public later: purge or genericize `progress/`, `mocks/`,
       the two resume-derived modules, and the email line in `COMMIT.md`;
       rewrite history (`git filter-repo`) since old commits keep content.

## Dependency posture

Runtime deps of the product: **zero** (vanilla JS app loaded from `file://`,
stdlib-only Python tooling). Dev-only: `pytest` (labs/tests) and `node` (DOM/SM-2
suites). No npm/pip supply chain ships to users.

## Incident playbook

If a secret ever lands: rotate/revoke the credential first, then remove from
history with `git filter-repo`, force-push, and re-run the scanner. Content
leaks (resume data) in a private-repo accident: make repo private immediately,
then decide on history rewrite per item above.
