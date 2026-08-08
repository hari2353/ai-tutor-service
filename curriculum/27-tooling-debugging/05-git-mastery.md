# Git Deep: Objects, Refs, Rebase, Bisect, Reflog, Worktrees, Recovering Anything

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.5h · **Prereqs:** none
> **Module id:** `T27-git-mastery` · **Tags:** git, critical

## The 30-second version

Git is a content-addressed object store with four object types — blob, tree, commit, and a mutable pointer layer of refs on top — and everything else (branches, rebase, bisect, reflog, worktrees) is a convenience built on that store. A commit is never really "on a branch"; a branch is just a 41-byte file holding a commit SHA, and moving it is all `git branch -f` or a rebase ever does. Because objects are content-addressed and immutable, nothing in git is ever truly destroyed by a `reset --hard` or a bad rebase — the old commit objects stay in the object database until garbage collection actually runs (default: unreferenced objects older than 2 weeks), and the reflog gives you the commit SHA to point a branch back at in the meantime. The one operation that is genuinely destructive to someone else's work is a force-push that overwrites a ref on a shared remote before they've fetched — `git push --force-with-lease` exists specifically to make that class of accident detectable before it happens, not after. Everything past this — rebase, bisect, cherry-pick — is graph surgery on commit parent pointers; understanding that turns "git is magic incantations" into "git is four object types and a pointer I can inspect with `cat-file`."

## Why this gets asked

Because most engineers operate git entirely through a dozen memorized command incantations and have never once run `git cat-file -p HEAD` to see what a commit object actually contains. Interviewers who've had to walk a panicked teammate through recovering a `git reset --hard` on the wrong branch, or untangle a force-push that silently discarded three people's commits, want to know whether you reach for the object model and reflog as evidence, or start guessing and re-committing from memory (which is how "recoverable" data-loss incidents become permanent ones).

---

## Lineage: past → present → future

**What came before.** Centralized version control (CVS, then Subversion) modeled history as a sequence of per-file deltas against a single central repository — every commit required round-tripping to the server, branching was expensive enough that teams avoided it, and merging two long-lived branches was a dreaded manual reconciliation because the tools tracked line-level diffs, not the actual ancestry graph of changes. The specific pain that killed this model was the 2005 BitKeeper licensing dispute that forced the Linux kernel project off proprietary DVCS tooling overnight — Linus Torvalds wrote git in roughly ten days as a content-addressed snapshot store explicitly designed to make branching and merging cheap (a branch is a pointer, not a copy) and to make history verifiable (every object is hashed, so corruption or tampering is detectable, not just "diffed").

**Where it stands now.** Git has won outright as the version control layer — Mercurial and Perforce persist in specific enterprise/game-industry niches for large binary assets, but git plus a hosting layer (GitHub, GitLab, Bitbucket) is the default everywhere else. The live disagreement isn't about git itself, it's about workflow on top of it: rebase-and-fast-forward versus merge-commit-preserving history is a genuine, unresolved culture split — Linus himself has publicly argued against rebasing published history while GitHub's own default UI nudges toward squash-merge, and both camps have legitimate reasoning (linear bisectable history versus preserving the true chronological record of what actually happened). What's universally agreed and actually deployed at scale: trunk-based development with short-lived feature branches, protected `main`, and CI gating merges — the "GitFlow" long-lived branch model from the early 2010s has fallen out of favor at most fast-moving shops because the merge conflicts it produces scale worse than the release-management problem it solved.

**Where it's heading.** Partial clone and sparse checkout (`git clone --filter=blob:none`, `sparse-checkout`) are real, shipping, and increasingly the default at large-monorepo shops (Microsoft's Windows and Office repos, Google's internal tooling ancestry) because cloning tens of gigabytes of history nobody touches daily doesn't scale linearly with engineering headcount — this is deployed, not speculative. More speculative: AI-assisted conflict resolution and commit-message/PR-description generation are shipping as IDE features (GitHub Copilot, JetBrains AI) but git's underlying object model and merge algorithm (three-way merge via a common ancestor) haven't changed and show no sign of needing to — the innovation is happening at the tooling layer above the object store, not inside it.

---

## Mental model

```
THE OBJECT MODEL (four types, all content-addressed by SHA-1/SHA-256 hash)

  blob    <- raw file CONTENTS only. No filename, no path, no permissions.
             Two files with identical content are ONE blob, everywhere in history.

  tree    <- a directory listing: (mode, name, type, sha) rows pointing to
             blobs and other trees. This is where filenames/paths actually live.

  commit  <- (tree SHA, parent SHA(s), author, committer, message)
             A commit is a SNAPSHOT pointer + metadata, not a diff.
             Diffs are *computed* on demand by comparing two trees.

  tag     <- (annotated only) a named, signed pointer to any object, usually a commit.

  REFS -- mutable pointers, NOT objects themselves
  .git/refs/heads/main        <- 40/64 hex chars, the tip commit SHA. That's it.
  .git/HEAD                   <- usually "ref: refs/heads/main" (symbolic ref)
  .git/refs/remotes/origin/*  <- where the remote's branches were LAST SEEN
  .git/logs/HEAD              <- the reflog: every SHA HEAD has pointed to, locally, with a reason

  git commit  == write a new tree, write a new commit object pointing at it and
                 at current HEAD as parent, then move the branch ref forward.
                 "Committing to a branch" is really just moving a pointer.

  git branch -f <name> <sha>  == literally overwrite that 41-byte file. That is
                                 100% of what a hard reset or a rebase does to a ref.
```

The fact that resolves the most confusion: **a commit does not know what branch it's "on."** Branches are external pointers into a DAG of commits that only know their own parent(s). `git log --oneline` walking "a branch" is really just walking parent pointers starting from wherever the ref currently points — which is exactly why deleting a branch doesn't delete its commits, and why `git branch -f` can make any branch point anywhere in the DAG instantly.

## How it actually works

**Object hashing and storage.** Every object is stored as `zlib`-deflated content prefixed with a header `"<type> <byte-length>\0"`, and the object's ID is the SHA-1 (SHA-256 in the newer, still-experimental format) hash of that header-plus-content. `git hash-object` computes this without even touching the object store; `git cat-file -p <sha>` decompresses and prints any object by ID. Loose objects live under `.git/objects/<first 2 hex chars>/<remaining 38>`; once a repo accumulates roughly 6700 loose objects (the default `gc.auto` threshold), `git gc` packs them into a single `.pack` file using delta compression against similar objects, which is why a freshly-cloned repo's `.git` is dramatically smaller than the sum of every blob it contains.

**Rebase, mechanically.** `git rebase <upstream>` finds the merge-base (common ancestor) between your branch and `<upstream>`, then replays each of your commits — literally re-running `cherry-pick` for each one — on top of `<upstream>`'s tip, producing brand-new commit objects with new SHAs (same tree diff, different parent, so a different hash) and finally moving your branch ref to the last new commit. `git rebase --onto <newbase> <oldbase> <branch>` generalizes this to "replay only the commits between `<oldbase>` and `<branch>`, onto `<newbase>`" — the tool for surgically moving a feature branch off a bad base without dragging along unrelated commits. Because every replayed commit gets a new SHA, **rebased commits are not the same objects as the originals** — anyone who already pulled the pre-rebase commits now has a diverged, unrelated history, which is the entire reason rebasing already-pushed/shared branches is the operation that burns teams.

**Bisect, mechanically.** `git bisect start`, then `git bisect bad <sha>` and `git bisect good <sha>` bracket a range of N commits; git checks out the midpoint and you mark it `good`/`bad`, halving the search space each time — `O(log2 N)` steps to isolate the exact culprit commit out of a linear history, so a 1000-commit range resolves in about 10 checkouts, not 1000. `git bisect run <script>` automates the good/bad judgment entirely by exit code (0 = good, 1-127 excluding 125 = bad, 125 = skip this commit — untestable, e.g. it doesn't build), turning a manual afternoon into an unattended few minutes for anything with a reliable repro script.

**Reflog, mechanically.** Every local ref update — commit, checkout, merge, rebase, reset — appends a line to `.git/logs/<ref>` recording the old SHA, new SHA, and the command that caused it. `git reflog show HEAD` (or just `git reflog`) prints this local history of *where HEAD has pointed*, independent of the commit DAG's own parent pointers — this is why the reflog can rescue you even after a rebase or reset has made the "correct" history graph unreachable from any branch: the reflog still has the SHA. Default retention: 90 days for entries reachable from a ref, 30 days for entries that become unreachable (`gc.reflogExpire` / `gc.reflogExpireUnreachable`) — after that window and an actual `git gc --prune`, the objects become eligible for real deletion. **The reflog is local-only** — it lives in your `.git` directory, was never pushed, and does not exist for anyone else's clone; it cannot recover a commit you never had locally in the first place.

**Worktrees, mechanically.** `git worktree add <path> <branch>` creates a second working directory linked to the *same* `.git` object database and refs, with its own independent `HEAD` and index — this lets you have `main` checked out in one directory and a hotfix branch checked out in a sibling directory simultaneously, without stashing, without a second clone duplicating the entire object store on disk. The constraint: a single branch cannot be checked out in two worktrees at once (git will refuse), because both would be trying to advance the same ref independently, which the tool has no way to reconcile.

## Build it from scratch

```bash
# --- Object model, by hand ---
echo "hello" | git hash-object --stdin              # returns the blob's SHA without storing it
echo "hello" | git hash-object -w --stdin            # -w actually writes it to .git/objects
git cat-file -t <sha>                                 # "blob"
git cat-file -p <sha>                                 # "hello"
git cat-file -p HEAD                                  # tree <sha>, parent <sha>, author, message
git cat-file -p HEAD^{tree}                           # the file listing: mode, type, sha, name per row
git ls-tree -r HEAD                                   # full recursive listing of every blob in HEAD

# --- Recovering a commit "lost" to git reset --hard ---
git reset --hard HEAD~3                               # oops -- three commits look gone
git reflog                                             # find the line: <sha> HEAD@{1}: commit: <msg>
git branch recovered-work <sha>                        # ref restored, pointing at the old tip
# or, if you don't even have the reflog entry (e.g. different clone, expired):
git fsck --lost-found                                  # lists dangling commits/blobs not reachable
                                                         # from any ref -- writes loose ones to
                                                         # .git/lost-found/commit/<sha>

# --- Recovering from someone else's bad force-push (you have an old local ref) ---
git reflog show origin/main                             # your LOCAL record of where origin/main was
                                                          # before your last fetch overwrote it
git branch rescue-main <sha-from-reflog>
git push origin rescue-main:main --force-with-lease      # push the pre-force-push state back,
                                                          # --force-with-lease refuses if the remote
                                                          # moved again since your last fetch (the
                                                          # exact race a plain --force can't detect)

# --- bisect, scripted ---
git bisect start HEAD v1.4.0                             # bad=HEAD, good=v1.4.0
git bisect run ./run_repro_test.sh                       # exit 0=good, 1=bad, 125=skip (untestable)
git bisect reset                                         # done -- return to original HEAD

# --- worktrees: two branches checked out at once, one object store ---
git worktree add ../hotfix-wt hotfix/urgent-cve
cd ../hotfix-wt && git status                            # independent HEAD/index, shared .git/objects
git worktree list
git worktree remove ../hotfix-wt                         # after merging, clean up
```

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| `git reset --hard` "lost" commits that were the only copy of real work | Reset moved the branch ref backward; the old commits are still in the object database, just unreferenced by any ref | `git reflog`, find the pre-reset SHA, `git branch <name> <sha>` to re-point a branch at it — the objects are only truly gone after `gc.reflogExpireUnreachable` (30 days default) passes AND `git gc --prune` actually runs |
| Teammate's push rejected with "stale info" / "fetch first," they force-push anyway, and now history has silently changed underneath everyone | A rebase or `reset --hard` + force-push rewrote already-shared commits; a plain `--force` overwrites the remote ref unconditionally regardless of what changed there since the pusher's last fetch | Everyone should be pushing with `--force-with-lease` (fails loudly if the remote moved since your last fetch, instead of blindly overwriting); recovery is the reflog of `origin/<branch>` from before the last `fetch` on any machine that had it |
| `git bisect` lands on a commit that "shouldn't" be the cause | A non-deterministic test (flaky), or the repro script conflates an unrelated environment change with the actual regression, or a commit in the range doesn't build at all (should have been `git bisect skip`) | Confirm the repro is deterministic before bisecting (run it 5x on the same commit); use `git bisect skip` or exit code 125 in `bisect run` for commits that are untestable rather than letting them be misjudged as good/bad |
| Two people can't both work on `main` locally in separate terminals without constant `git stash` | Trying to use a single working directory/checkout for two divergent lines of work simultaneously | `git worktree add` a second directory sharing the same object database — no second clone, no stash juggling, independent `HEAD` per worktree |
| A rebase interactive session goes wrong mid-flight (bad conflict resolution, wrong commit dropped) | `rebase -i` was still in progress when the mistake was made, or `--continue`d past a broken conflict resolution | `git rebase --abort` restores the original branch tip exactly (it's tracked precisely for this), *if* still mid-rebase; if already completed, the reflog entry immediately before the rebase started still has the pre-rebase tip SHA |
| Large monorepo clone takes 20+ minutes and 8GB on a fresh laptop | Full clone fetches every blob for every path in the entire history, most of which the engineer will never touch | `git clone --filter=blob:none` (blobless partial clone, fetches blobs lazily on checkout) combined with `git sparse-checkout set <paths>` to also limit the working tree to relevant directories |

## Tradeoffs & when NOT to use it

- **Don't rebase a branch other people have already pulled and built on**, even if you personally prefer linear history — every rebased commit gets a new SHA, which means their local history has now diverged from the "true" upstream and their next pull produces a confusing pile of duplicate-looking commits or outright conflicts. Rebase freely on branches only you have; once it's shared, `merge` (or a coordinated force-push everyone re-bases from) is the only non-destructive option.
- **Don't reach for `git filter-branch`/history rewriting as a first response to "we committed a secret."** Rewriting history doesn't retroactively revoke anything already fetched by anyone, anywhere, including any CI cache or fork — the secret must be rotated regardless; history rewriting is cleanup after rotation, not the fix itself. `git filter-repo` (the community-maintained successor) is meaningfully faster and safer than `filter-branch` for the cleanup step, but rotation comes first, always.
- **Don't use worktrees as a substitute for actually branching and merging cleanly.** They solve "I need two checkouts at once," not "my branching strategy is a mess" — a pile of stale worktrees left unregistered (`git worktree prune` needed) is its own maintenance burden.
- **Bisect assumes a monotonic bug** — the regression, once introduced, stays broken all the way to `bad`. A bug that was introduced, incidentally fixed by an unrelated later commit, then reintroduced will make bisect converge on the wrong commit; check that `good` and `bad` are both unambiguous and stable before trusting the result blindly on a long, messy range.

---

## Interview questions

### Q1 — What exactly does `git commit` do to the object database and the ref, step by step?
**Testing:** whether the candidate has an actual mental model versus a memorized command.
**Answer:** It writes a new tree object (or reuses an existing identical one, since objects are content-addressed), writes a new commit object referencing that tree's SHA plus the current `HEAD` commit as parent plus author/committer metadata, then moves the current branch ref (a 41-byte file) forward to point at that new commit SHA. Nothing about "the branch" is stored inside the commit object itself.
**Follow-up trap:** *"If commits don't know what branch they're on, how does `git branch --contains <sha>` work?"* — it's computed on demand by walking every ref's ancestry (parent pointers) and checking whether `<sha>` is reachable from each one; it's a graph reachability query, not a stored field.

### Q2 — Two completely different files in history have identical content. How many blob objects exist for them?
**Testing:** understanding content-addressing.
**Answer:** One. The blob's SHA is a hash of its content only — no filename, path, or permission bits are part of a blob. The filename and mode live in the tree object that references the blob, so the same blob can be referenced by unlimited trees under unlimited different names simultaneously without duplicating storage.
**Follow-up trap:** *"So does renaming a file create a new blob?"* — no, renaming with no content change produces an identical blob SHA referenced by a new tree entry with the new name; `git mv` plus a commit is purely a tree-level change. Git detects "renames" at diff/display time by comparing blob similarity between two trees — there's no stored rename record anywhere.

### Q3 — Explain why `git rebase` produces different commit hashes for commits that supposedly "didn't change."
**Testing:** understanding that a commit hash covers parent + tree + metadata, not just the diff.
**Answer:** A commit's SHA is a hash over its tree SHA, its parent SHA(s), author, committer, and message. Rebase changes the parent (that's the entire point — moving onto a new base), and a changed parent field changes the hash even if the resulting file tree is byte-identical to before. This is why rebased commits are new objects with no identity relationship to the originals as far as git's object store is concerned.
**Follow-up trap:** *"A teammate says 'the commit is exactly the same, just rebased, so it's safe to force-push.'" What's wrong with that reasoning?* — "the same" from a diff-content perspective is not "the same object" from git's perspective; anyone who has the pre-rebase SHA in their own history now has a genuinely divergent commit graph, and their next `git pull` (a fetch + merge) will either silently create a duplicate merge or, with `pull --ff-only`, fail outright — the human claim of sameness doesn't change what the object database considers reachable and identical.

### Q4 — Someone ran `git reset --hard origin/main` on a branch with unpushed local commits. Is the work actually gone?
**Testing:** whether reflog is the first instinct, not panic or "restore from backup."
**Answer:** Not immediately. The commit objects those local commits created still exist in `.git/objects` — reset only moved the branch ref backward, it doesn't delete objects. `git reflog` shows the SHA the branch pointed to immediately before the reset (labeled with the reset operation), and `git branch <newname> <that-sha>` recreates a pointer to the exact prior state. This only stops working once those objects are pruned by `git gc` after the unreachable-object retention window (default 30 days) actually elapses.
**Follow-up trap:** *"The reflog itself has been cleared or you're debugging from a colleague's fresh clone that never had these commits. Now what?"* — the reflog is purely local to whichever `.git` directory produced the commits in the first place; a fresh clone from the remote never had them and has no reflog entries for them. If nobody's local `.git/logs` has the entry and the remote never received the commits, they are genuinely gone — this is the actual boundary of git's recoverability, and it's why "push often, even to a scratch branch" is real risk mitigation, not paranoia.

### Q5 — Walk through `git bisect run` end to end, including what each exit code means.
**Testing:** practical fluency, not just "I've heard of bisect."
**Answer:** `git bisect start`, mark the known-bad commit (`git bisect bad <sha>`, often `HEAD`) and a known-good one (`git bisect good <sha>`), then `git bisect run <script>` where the script exits 0 for good, any of 1-127 except 125 for bad, and specifically 125 to tell bisect "this commit can't be tested" (doesn't build, missing dependency) so it's skipped rather than misjudged. Git checks out the midpoint of the remaining range each iteration and re-runs the script, halving the search space until it converges on the single first-bad commit — roughly log2(N) checkouts for N commits in range.
**Follow-up trap:** *"Your bisect converges cleanly but on a commit that's obviously just a formatting/whitespace change with no logic in it. What's your next hypothesis?"* — either the repro script itself is flaky/non-deterministic (rerun it several times on the same commit to check), or the actual regression was introduced earlier but masked until this later commit changed something adjacent (build config, a file that got picked up differently after reformatting) — re-verify `good` and `bad` boundaries are both stable and consider widening the range rather than trusting a bisect result that doesn't causally make sense.

### Q6 — What's the actual difference between `git merge` and `git rebase` in terms of the resulting object graph, not workflow philosophy?
**Testing:** graph-level understanding versus workflow opinion.
**Answer:** `merge` creates one new commit with *two* parents (the tips of both branches), preserving every original commit object unchanged and the true chronological interleaving of when commits actually happened on each branch. `rebase` creates entirely new commit objects that each have exactly one parent, replaying your branch's diffs on top of a new base — the original commits still exist in the object store (until gc'd) but become unreachable from any ref once the branch pointer moves to the new chain.
**Follow-up trap:** *"Which one makes `git bisect` more reliable on a long-lived branch with lots of merge commits, and why?"* — a linear (rebased) history, because bisect's binary search assumes a single, well-ordered chain; a heavily merged history has ancestry that branches and rejoins, so "the midpoint" is ambiguous across parallel lines of development and bisect can end up testing states that never actually existed as a coherent snapshot anyone ran in that exact order — `git rebase` before bisecting a nasty regression is a legitimate, common tactic specifically to make the search space genuinely linear.

### Q7 — What does `--force-with-lease` actually check that plain `--force` doesn't?
**Testing:** whether the candidate understands the specific race it closes, not just "it's safer."
**Answer:** `--force-with-lease` refuses the push if the remote-tracking ref (`origin/<branch>` as your local git last saw it) doesn't match what the remote server's ref actually currently is — meaning someone else pushed since your last `fetch`. Plain `--force` overwrites the remote ref unconditionally regardless of what's actually there right now, silently discarding any commits pushed by someone else in between your fetch and your force-push.
**Follow-up trap:** *"You ran `--force-with-lease` and it still let you overwrite a colleague's just-pushed commits. How?"* — you didn't `fetch` recently enough before force-pushing; `--force-with-lease` only compares against your locally cached `origin/<branch>` ref, which is only as fresh as your last fetch — if you fetched, then they pushed, then you force-pushed without fetching again, your stale local view of `origin/<branch>` still matches what lease is checking against staleness relative to, and the push goes through and destroys their work anyway. The actual guarantee is "matches my last-known remote state," not "matches the remote's current state at push time."

### Q8 — Explain `git worktree`'s actual constraint: why can't the same branch be checked out in two worktrees simultaneously?
**Testing:** understanding worktrees as sharing one object database and ref set, not independent repos.
**Answer:** All worktrees linked to a repository share the exact same `.git` object database and refs — a branch ref is a single pointer, and if two working directories both had that branch "checked out" they could each independently commit and move that one ref in conflicting directions with no reconciliation mechanism. Git enforces one worktree per branch specifically to prevent that; you can have unlimited worktrees, each on its *own* distinct branch (or the same commit in detached-HEAD state, which has no such conflict since nothing can move a detached HEAD's underlying ref for anyone else).
**Follow-up trap:** *"Can two worktrees be at the exact same commit?"* — yes, as long as at most one of them has an actual branch ref checked out there; the other can check out that same commit in detached HEAD state, since a detached HEAD isn't a movable named ref that could conflict with anything.

### Q9 — A file's `git blame` shows it was "last changed" by a commit that's clearly just a repo-wide reformat, hiding the real author of that logic. How do you get past that?
**Testing:** practical day-to-day git fluency beyond the basic command.
**Answer:** `git blame -w` ignores whitespace-only changes when attributing lines, and `git blame --ignore-rev <reformat-sha>` (or a `.git-blame-ignore-revs` file referenced via `blame.ignoreRevsFile`, which many teams commit to the repo specifically for this) skips a known bulk-reformat commit entirely and attributes those lines to whoever last meaningfully touched them before that.
**Follow-up trap:** *"Your team wants this to work for everyone automatically, not per-engineer flags. What's the actual mechanism?"* — commit a `.git-blame-ignore-revs` file listing reformat/mass-rename commit SHAs, and set `git config blame.ignoreRevsFile .git-blame-ignore-revs` (ideally checked in as a documented convention, since it's a local config setting each clone must still opt into — GitHub's own blame UI also respects this file natively when present in the repo root).

### Q10 — Staff-level: your CI pipeline runs `git bisect` automatically on every regression report, but it recently converged on a commit deep in an already-reverted, since-abandoned experimental branch that was merged and then reverted months ago. What's actually going wrong?
**Testing:** understanding that bisect operates purely on ancestry reachability and doesn't know about "intent" like reverts.
**Answer:** A revert commit undoes the *content* of a change but leaves the original commit fully present in history as an ancestor — bisect's binary search over the linear range can still land squarely inside that reverted branch's commits if the regression symptom happens to reproduce differently at intermediate, transiently-broken states within it, even though the net effect at any commit *after* the revert is "as if it never happened." The tool has no concept of "this was undone later"; it only evaluates whatever state exists at each checked-out commit.
**Follow-up trap:** *"How would you change the bisect range or script to prevent this specific failure mode going forward?"* — narrow `good`/`bad` boundaries to exclude the already-reverted range entirely if it's known to be irrelevant (bisect only searches between the two boundaries you give it), or make the `bisect run` script's pass/fail criteria robust enough to correctly classify every commit in that sub-range on its own merits rather than assuming monotonic badness across the whole span — and treat a bisect result landing inside a known-reverted branch as a signal to re-examine the boundaries, not a final answer to act on.

---

## Red flags that fail you

- Treating a rebase and a merge as "basically the same thing, just different history style" without knowing rebase produces new SHAs for every replayed commit.
- Proposing to re-do lost work from memory before checking `git reflog` or `git fsck --lost-found`.
- Not knowing `--force-with-lease` still relies on a locally cached remote-tracking ref and isn't an atomic server-side check.
- Believing the reflog is shared/pushed, or that it survives indefinitely with no expiration.
- Rebasing a branch you know other people have already pulled, without coordinating.
- Reaching for `git filter-branch`/history rewriting as the fix for a leaked secret instead of rotating it first.

## Cheat card

```
OBJECTS (content-addressed, SHA-1/40-hex or SHA-256/64-hex):
  blob=file content only, no name/path   tree=(mode,name,type,sha) rows -> blobs/trees
  commit=(tree sha, parent sha(s), author, msg)   ref=mutable 41-byte pointer file, NOT an object

git cat-file -t/-p <sha>        inspect any object     git hash-object -w --stdin  write a blob by hand
git ls-tree -r HEAD             full blob listing of HEAD

REBASE: replays commits onto new parent -> NEW SHAs every time (tree may be same, parent isn't)
  never rebase a branch others already pulled -- diverges their history irrecoverably w/o coordination
  git rebase --onto <newbase> <oldbase> <branch>   -- surgical: only commits (oldbase..branch]

BISECT: O(log2 N) checkouts for N commits.
  git bisect start; bisect bad <sha>; bisect good <sha>; bisect run <script>
  script exit: 0=good  1-127(not125)=bad  125=skip(untestable)

REFLOG (LOCAL ONLY, never pushed):
  git reflog                       every SHA a ref pointed to + why, on THIS machine
  retention: 90d reachable / 30d unreachable default (gc.reflogExpire / gc.reflogExpireUnreachable)
  recover: git branch <name> <sha-from-reflog>
  no local reflog entry + never pushed = genuinely unrecoverable

git fsck --lost-found            finds dangling (unreachable, not-yet-gc'd) objects, incl. after gc removed refs
git push --force-with-lease       fails if origin/<branch> moved since YOUR last fetch (vs plain --force: blind overwrite)
git worktree add <path> <branch>  2nd checkout, SAME object db/refs; one branch can't be in 2 worktrees at once
git clone --filter=blob:none      partial clone, lazy blob fetch -- for huge monorepos
git blame -w / --ignore-rev <sha> / blame.ignoreRevsFile   -- skip whitespace/reformat noise in blame
gc.auto threshold ~6700 loose objects before auto-repack into a .pack
```

## Sources

- [Git Reflog: Recover Deleted Branches and Lost Commits — Boot.dev](https://www.boot.dev/blog/devops/git-reflog) — accessed 2026-07-26
- [git reflog: the undo button you didn't know you had — GitFlow](https://www.gitflow.dev/blog/git-reflog-the-undo-button) — accessed 2026-07-26
- [Git User Manual — kernel.org](https://www.kernel.org/pub/software/scm/git/docs/user-manual.html) — accessed 2026-07-26
- [How to Recover from a Corrupted Git Repository — DEV Community](https://dev.to/alanwest/how-to-recover-from-a-corrupted-git-repository-22oc) — accessed 2026-07-26

## Changelog
- 2026-07-27 — created
