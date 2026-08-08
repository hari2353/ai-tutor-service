# Committing and sharing this repo

Git operations run far too slowly through the agent's sandbox mount to complete
inside its command timeout (707 files over a mounted Windows filesystem). On your
own machine they take seconds. Run these yourself.

## One-time: commit and push

```powershell
cd F:\v1\ai-tutor-service

git config user.name  "Hari Siva Rami Dwarampudi"
git config user.email "haribhamireddy@gmail.com"

git add -A
git commit -m "AI tutor service: 36 tracks, 452 modules, 313 written"

# authenticate (agent will never run this for you)
gh auth login

# create the repo and push. Use --private unless you intend it public:
# the STAR bank and resume-systems modules contain your real work history.
gh repo create ai-tutor-service --private --source=. --remote=origin --push
```

If you prefer the web UI: create an empty repo on GitHub, then

```powershell
git remote add origin https://github.com/<you>/ai-tutor-service.git
git branch -M main
git push -u origin main
```

## Sharing with your friend

```powershell
gh repo add-collaborator <their-github-username> --permission push
```

## Before you push — check this

`.gitignore` already excludes `interview_prep_queue.json` (live job listings).

But the repository **does** contain, by design:

- `curriculum/14-behavioral-principal/01-star-bank.md` — 30 STAR stories built
  from your real resume, including employer, metrics and project detail
- `curriculum/10-system-design/09-resume-systems.md` — your flagship systems
  written up as formal design docs
- `progress/` — your study state

None of that is secret, but it is personal and it is specific about your
employer's systems. **Private repo unless you have decided otherwise.**

If you want the curriculum public and the personal material out, move those two
files plus `progress/` into a second private repo before the first push —
rewriting history afterwards is much harder than not committing it.

## Routine, after every work session

```powershell
python app/build_data.py        # regenerate index + merge fragments
python app/tests/review_gate.py # house-format check
bash app/tests/run.sh           # app + lab tests
python app/learning_path.py     # refresh LEARNING-PATH.md
git add -A && git commit -m "..." && git push
```
