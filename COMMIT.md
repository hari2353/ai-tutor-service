# Committing and sharing this repo

The repo is versioned locally on `main`. Pushing to GitHub is a user action — it needs
`gh auth login` (or any remote you create); the agent never runs authentication.

## Status

First commit landed as the baseline (36 tracks · 452 modules · content + app + skills).
Commit after each work session so history tracks progress, not just snapshots.

## One-time: push to GitHub

```powershell
# from the repo root (the directory containing CONTENT-STATUS.md)
git add -A
git commit -m "progress: <what changed>"

# create the private remote and push — keep this repo PRIVATE:
# curriculum contains resume-derived material, real numbers, and a live job queue.
gh repo create ai-tutor-service --private --source . --push

# gh not installed? winget install GitHub.cli   then   gh auth login
```

## After every session

```powershell
git add -A
git commit -m "<concise message>"
```

The generated data files (`app/data/*.json`, `*.js`, `CONTENT-STATUS.md`,
`LEARNING-PATH.md`) are tracked on purpose: the app loads them from `file://`
so a fresh clone must open by double-click with no build step. Commit them together
with whatever regenerated them so the tree stays consistent.

## Never in this repo's public history

- `interview_prep_queue.json` is gitignored (live job pipeline, stays local).
- Real offer details / compensation numbers belong only in `mocks/` or `progress/`
  if the remote is private; scrub before ever making this public.
