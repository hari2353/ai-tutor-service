# Repo, sharing, and the day-to-day loop

**Live at `https://github.com/hari2353/ai-tutor-service` (private).**
Pushed 2026-08-09: 1,507 objects, 12.92 MiB, `main` tracking `origin/main`.

Note that `gh` (GitHub CLI) is **not installed** on this machine. Everything below uses
plain git plus the GitHub web UI. If you want the CLI: `winget install --id GitHub.cli`,
then restart PowerShell so `gh` lands on `PATH`.

## Add your friend

Repo → **Settings → Collaborators → Add people** → their username, **Write** permission.

Then they clone and set up:

```powershell
git clone https://github.com/hari2353/ai-tutor-service.git
cd ai-tutor-service
pwsh scripts/setup-collab.ps1     # REQUIRED, once per clone -- see CONTRIBUTING.md §3
python app/build_data.py
```

Skipping `setup-collab` is the one mistake that will hurt: without it, every merge dumps
conflict markers into a 2.7 MB generated JSON file. Git does not ship hooks or merge
drivers over the wire (they execute code), so each clone must opt in locally.

Read `CONTRIBUTING.md` before writing modules — it has the parallel workflow, the
fragment-vs-aggregate rule, and the five module-writing rules.

## Day-to-day

```powershell
cd F:\v1\ai-tutor-service
git pull                          # post-merge hook regenerates indexes automatically

# ... work ...

python app/build_data.py          # regenerate; merges card and drill fragments
python app/tests/review_gate.py   # house format -- expect 452 pass, 0 fail
bash app/tests/run.sh             # DOM and SM-2 tests
python app/learning_path.py       # refresh LEARNING-PATH.md

git add -A
git commit -m "..."
git push
```

`git add -A` takes roughly 45 seconds here. That is normal for ~1,900 files over a Windows
filesystem, not a hang.

## Keep it private

The repo contains, deliberately:

- `curriculum/14-behavioral-principal/01-star-bank.md` — 30 STAR stories from your real CV:
  employer, systems, metrics, and what went wrong in each
- `curriculum/10-system-design/09-resume-systems.md` — your flagship systems as formal
  design docs, with architecture and scale numbers
- `curriculum/14-behavioral-principal/04-company-specific.md` — which stories to lead with
  at which employer
- `progress/` — your study state

No credentials, but all of it is specific about your employer's internals and your own
interview strategy. A public repo hands a future interviewer your prep notes.

If you ever want the curriculum public, move those three files plus `progress/` into a
separate private repo **before** the first public push. Rewriting history afterwards is far
harder than not committing it.

## Secrets: scanned, clean

Checked for AWS keys, OpenAI/Anthropic keys, GitHub tokens, Slack tokens, Google API keys,
private key blocks and real JWTs. One hit, a false positive: the literal string
`-----BEGIN PRIVATE KEY-----` inside a SPIFFE teaching example in
`curriculum/30-auth-security/07-sso-federation.md`, where the value is
`(never leaves this workload)`.

`.gitignore` covers `interview_prep_queue.json` (live job listings), `__pycache__/`,
`.venv/`, `node_modules/` and OS droppings.

## Repository size

~39 MB working tree. The four largest tracked files are generated aggregates:

```
2.7M  app/data/flashcards.json
2.7M  app/data/drills.json
2.6M  app/data/drills.js
2.5M  app/data/flashcards.js
```

Tracked **on purpose**: the app loads them from `file://` with no build step, so a fresh
clone opens by double-clicking `app/index.html` without anyone running Python first. The
cost is that every regeneration rewrites ~10 MB, so history grows faster than a normal
repo. `.gitattributes` marks them `linguist-generated` to keep them out of diffs.

If that ever becomes a problem the fix is to untrack the `.js` files and add a build step
to the README — but do it deliberately, because it breaks the zero-setup property that
makes the app pleasant to use.
