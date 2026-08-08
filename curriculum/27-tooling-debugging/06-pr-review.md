# PR Review at Speed: What to Look For, In What Order, and What to Ignore

> **Track:** T27 Tooling, Docker & Debugging Mastery · **Time:** 2.0h · **Prereqs:** T27-git-mastery
> **Module id:** `T27-pr-review` · **Tags:** review, critical

## The 30-second version

Review in a fixed order — correctness, security, design, tests, style — because each layer invalidates cheaper checks below it: a function with a wrong algorithm doesn't need a style pass, and a SQL-injection hole doesn't need a design opinion yet. Correctness and security get full attention regardless of PR size; design gets attention proportional to blast radius; tests get checked for whether they'd actually catch a regression, not whether they exist; style gets a linter, not a human, and if it's consuming review time the CI pipeline is missing a gate. For a 2000-line PR, the actual skill isn't reading 2000 lines carefully — nobody sustains that — it's finding the 200 lines that matter (the entry point, the diff's riskiest hunk, the parts with no tests) and reading those at full depth while skimming the rest for shape. Feedback that gets acted on is specific, scoped to what blocks merge versus what's a suggestion, and never phrased as a rewrite of someone's approach when the existing approach already works.

## Why this gets asked

Because "did you review the PR" is a proxy for "can we trust you to be the last line of defense before production," and every interviewer asking this has shipped a bug that a careless review let through — usually because the reviewer skimmed for style (formatting, naming) while an actual null-pointer path or an auth bypass sailed past unexamined. They want to see that the candidate has an internalized order of operations, not a vibe-based "looks good to me."

---

## Lineage: past → present → future

**What came before.** Pre-2005, code review at most companies meant either nothing (trunk commits, no gate) or formal Fagan inspections — scheduled meetings, printed listings, a moderator, a recorder, defect logs — descended from Michael Fagan's 1976 IBM process. Fagan inspections caught real defects (studies at the time claimed 60-90% detection rates for inspected code) but cost hours of synchronous meeting time per few hundred lines, which made them economically viable only for safety-critical or extremely expensive-to-patch software (embedded firmware, aerospace). The pain that killed them for mainstream software: the meeting overhead didn't scale to weekly or daily release cadence, and most defects inspections caught were also catchable by much cheaper means (static analysis, tests) once those tools matured.

**Where it stands now.** Lightweight, tool-mediated, asynchronous review (GitHub/GitLab pull requests, Gerrit changesets) is the near-universal default; the live disagreement is about PR size and review depth, not process. The widely cited Cisco/SmartBear peer-review research (from the "Best Kept Secrets of Peer Code Review" studies) found defect-detection effectiveness falls off sharply above roughly 200-400 lines of diff reviewed per hour, and that review sessions past 60-90 minutes continuous find fewer new defects per minute regardless of remaining diff size — both numbers still get cited in 2026-era review-process guides essentially unchanged, because nobody has published contradicting data, only tooling that tries to route around the problem (AI pre-review passes, mandatory small-PR policies). What's actually deployed at most engineering orgs: automated gates (lint, type-check, security scanners, test coverage diff) run before a human ever opens the PR, and the human's job is explicitly scoped to what automation can't do — correctness of business logic, whether the design fits the codebase, whether tests actually assert behavior. What's merely aspirational: PR-size limits are recommended almost everywhere (200-400 lines) and enforced almost nowhere, because feature work and refactors routinely don't decompose that small without real engineering effort most teams don't invest.

**Where it's heading.** LLM-assisted first-pass review (flagging hallucinated APIs, inconsistent patterns, missing null checks, full-repo-context dependency changes) is real and shipping now in 2026 — GitHub Copilot review, Graphite's reviewer, and standalone tools built specifically for this are in daily use at many companies, and the consensus split is which checks are safe to fully delegate (import resolution, style, obvious null-deref patterns) versus which still need a human regardless of tooling quality (does this design actually fit where the codebase is going, is this the right tradeoff for this specific system). The more speculative direction — an AI reviewer with enough repo and product context to make the design-fit call unsupervised — is not there yet and treated skeptically by senior engineers, precisely because that judgment depends on context (team roadmap, on-call history, org priorities) that isn't fully captured in the repo itself.

---

## Mental model

```
REVIEW ORDER (top gate blocks; each layer is cheaper only because the one above already passed)

1. CORRECTNESS   -- does it do what it claims, on the actual inputs it will see in prod?
2. SECURITY      -- can an adversarial or malformed input turn this into a vulnerability?
3. DESIGN        -- does this fit the codebase's shape, or does it fight it?
4. TESTS         -- do the tests assert BEHAVIOR, and would they actually fail if this broke?
5. STYLE         -- naming, formatting, comments -- linter's job, not yours, unless the linter is missing

Why this order and not another:
  A correctness bug makes security/design/test discussion moot -- you're reviewing code that
  will be rewritten anyway once the bug is found.
  A security hole in correct-looking code is the single most expensive thing to miss --
  it ships, works fine in every demo, and fails in production against an adversary, not a user.
  Design critique on code with a correctness or security bug is wasted breath twice over.
  Style comments before correctness is the single most common failure mode in real reviews --
  it's the cheapest thing to comment on, so it's what under-time reviewers gravitate to first.

FOR A 2000-LINE PR, don't read linearly. Triage first:
  a) find the entry point / the thing that actually changes behavior (usually 10-20% of the diff)
  b) find what has zero test coverage in the diff -- read THAT at full depth
  c) find the file with the most churn (git diff --stat) -- usually where the real logic lives
  d) skim generated/vendored/config-only files for shape, don't read them line by line
  e) budget: ~60-90 min of continuous focus before defect-finding rate drops -- split into
     two sessions rather than pushing through, if the PR genuinely needs that much time
```

## How it actually works

**Correctness, mechanically.** Don't read code and ask "does this look right" — trace at least one real input through it by hand, specifically an edge input: empty collection, zero, negative, max-int, unicode, concurrent caller, the timeout path. Most correctness bugs that survive to review are exactly the inputs the author didn't mentally simulate while writing the happy path — that's why simulating them at review time (not just "reading" the code) catches what a same-author self-review already missed. For a function that transforms a list, walk it with `[]`, `[x]`, and a list with a duplicate — three inputs, thirty seconds, catches most off-by-one and null-handling bugs before you've read a single test.

**Security, mechanically, ordered by frequency in real reviews.** (1) Untrusted input reaching a query, shell command, or template without parameterization/escaping — grep the diff for string concatenation feeding `execute(`, `subprocess`, `os.system`, template rendering. (2) Authorization checked at the wrong layer — an endpoint that checks "is this user logged in" but not "does this user own this specific resource ID," the classic IDOR (insecure direct object reference) pattern, caught by asking "what happens if I pass someone else's ID here." (3) Secrets or credentials in the diff itself — a hardcoded key, a `.env` file accidentally added, a log line that prints a full request body including an `Authorization` header. (4) Deserialization of untrusted data with a format that supports arbitrary code execution (Python `pickle`, Java native serialization, YAML's `!!python/object` tag with unsafe loaders) — anywhere this appears on a path an external caller can influence is an immediate block, not a nitpick.

**Design, mechanically.** The question isn't "would I have built it this way" — that's taste, not review — it's "does this fit the shape of what's already here, and if not, is the divergence justified." Concretely: does this introduce a second way to do something the codebase already does one way (a new HTTP client wrapper next to an existing one, a second retry-with-backoff implementation), and if so is there a stated reason. Does this couple two modules that were previously independent, and if the PR needed that coupling, is it going through the existing seam (an interface, an event) or reaching directly into internals. Design pushback should identify the actual cost (this will need to change in two places next time, this makes module A untestable without module B running) — "I'd have done it differently" without a stated cost is a preference, and preferences don't block merges.

**Tests, mechanically — the check most reviewers do wrong.** Reading test code to confirm tests exist and pass is nearly worthless; the actual check is whether a test would fail if the implementation had a specific plausible bug. Read the test's assertions and ask: if someone flipped this conditional, deleted this null check, or changed this off-by-one, would this test go red? A test that mocks the exact behavior under test and then asserts the mock was called (`assert mock_transform.called_with(x)` for a test of `transform`) asserts nothing about correctness — it asserts that the code called a function, which the code obviously does, since that's what's being tested. This pattern is common enough in AI-generated test suites specifically that it gets its own module (see `reviewing-ai-code`).

**Style — deliberately last and deliberately brief.** If a formatter (Black, Prettier, gofmt, rustfmt) and a linter (Ruff, ESLint, golangci-lint, Clippy) aren't already gating the PR before a human opens it, that's the actual finding — "we need a pre-merge lint gate," not twenty inline comments about brace placement. A human commenting on style repeatedly across PRs is a signal the CI pipeline has a gap, not that the author needs more feedback.

## Build it from scratch

A minimal "triage a large diff before reading it" pass, runnable against any PR branch:

```bash
# Shape of the diff before reading a single line
git diff --stat main...feature-branch | tail -30
# -> which files changed the most; that's usually where the real logic is,
#    not the file with the most lines added (a generated lockfile can dwarf real changes)

# Which changed files have NO corresponding test file touched in this diff
git diff --name-only main...feature-branch | grep -v test | while read f; do
  base=$(basename "$f" | sed 's/\.[a-z]*$//')
  git diff --name-only main...feature-branch | grep -qi "test.*$base\|${base}.*test" \
    || echo "NO TEST TOUCHED: $f"
done

# Security-relevant grep pass across just the diff, not the whole repo
git diff main...feature-branch -- '*.py' '*.js' '*.ts' '*.java' \
  | grep -nE '^\+.*(subprocess|os\.system|eval\(|exec\(|pickle\.loads|yaml\.load\(|f".*SELECT|f".*INSERT|\.format\(.*SELECT)'

# Actual entry-point trace: what does main.go / app.py / index.ts touch in this diff
git diff main...feature-branch -- '**/main.*' '**/app.*' '**/index.*' '**/routes/*' '**/handlers/*'

# Review time budget: 60-90 min continuous, then break -- literally set a timer
# for anything over ~400 lines of real (non-generated) diff
```

Reading the output of the first three commands before opening the diff viewer changes what you look at first — you go in knowing which file is untested and which lines touch a shell/SQL/deserialization sink, instead of discovering it forty files in.

## How it's done in production — failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| Reviewer approves a 2000-line PR in 8 minutes | No triage pass — reviewer either skimmed everything shallowly or read only the first few files and assumed the rest matched | Triage first (diff --stat, untested files, entry-point trace); budget review time proportional to diff size, and say so explicitly ("this needs a real session, not a between-meetings glance") rather than approving under time pressure |
| PR sits for days with zero review | No owner assigned, or the PR is too large for anyone to want to start | CODEOWNERS-style routing to a specific reviewer, and author-side PR splitting for anything over ~400 real lines before requesting review, not after |
| Review comments are all style/naming, correctness bug ships anyway | Reviewer defaulted to the cheapest, most visible layer under time pressure instead of the order that actually catches expensive bugs | Enforce the order explicitly in review culture (or a checklist template in the PR description) — correctness and security first, every time, regardless of remaining time budget |
| Author pushes back on every comment, nothing gets resolved | Feedback phrased as a rewrite of approach ("I'd have used X instead") rather than a specific defect or cost | Scope every comment to blocking-defect vs. non-blocking-suggestion explicitly; reserve "must fix" language for correctness/security, use "consider" for design preferences |
| A security hole ships that "passed review" | Reviewer checked business logic correctness but never traced untrusted input to a sink (SQL, shell, deserialization, authorization boundary) | Make the security pass a named, separate step in the review checklist, not folded silently into "correctness" where it's easy to skip under time pressure |
| Tests pass, coverage tool shows green, regression ships next sprint anyway | Tests assert mock-call structure or implementation details, not observable behavior — they can't fail even when the real behavior is wrong | Read test assertions for whether flipping a real conditional in the implementation would flip the test's result; if not, the test isn't testing what it claims to |
| Reviewer requests changes, author addresses them, reviewer re-reviews the entire diff again from scratch | No use of "changes since last review" diff view; wastes the second pass re-litigating already-approved sections | Use the platform's incremental-diff view (GitHub's "changes since your last review," Gerrit's patch-set diff) — re-review only what changed |

## Tradeoffs & when NOT to use it

- **Don't apply full Fagan-style rigor to low-blast-radius changes.** A config value bump, a copy change, a well-tested internal refactor with no behavior change doesn't need the same correctness/security depth as a new payment-processing endpoint — calibrate depth to blast radius, not to a fixed process for every PR regardless of what it touches.
- **Don't block a PR on style when there's no lint gate to point to yet.** If the team genuinely has no automated formatter/linter, that's a one-time infrastructure fix, not a standing manual-review burden — spend the time setting up the gate instead of re-litigating brace placement on every PR indefinitely.
- **Don't insist on a design rewrite for something that already works and isn't on a critical path.** The senior signal is knowing when "not how I'd have built it, but it's correct, tested, and not blocking anything downstream" is the right call to approve as-is, versus when the divergence genuinely creates future cost.
- **Don't treat "tests exist and pass" as sufficient without reading what they actually assert** — this is the single most common way reviews rubber-stamp a regression, because the checkbox (green CI) is satisfied while the actual guarantee (this behavior is locked in) is not.
- **For genuinely huge PRs (a vendored dependency bump, a generated-code regeneration, a mechanical rename across the repo) don't read it like organic code at all** — confirm the tool that generated it is trustworthy and the diff matches what the tool claims to do, and spend the human-review budget on the 5% of the PR that's actually hand-written.

---

## Interview questions

### Q1 — You're handed a 2000-line PR with a two-hour meeting in twenty minutes. Walk through exactly what you do.
**Testing:** whether the candidate has a triage strategy or just starts reading top to bottom.
**Answer:** `git diff --stat` first to find the highest-churn files (usually where real logic lives, not the highest-line-count file, which might be a lockfile or generated code). Identify which changed files have no corresponding test touched. Trace the entry point — what does the route handler / main function actually call into. Read those at full depth; skim config/generated/vendored files for shape only. State explicitly to the team that a proper review of the remainder needs a dedicated session, rather than rubber-stamping the rest under time pressure.
**Follow-up trap:** *"The author says it can't be split, it's one atomic migration. Now what?"* — atomic migrations are exactly the case where splitting the review session (not the PR) is correct: review the schema/data-migration logic in one focused pass, review the application-code changes that depend on it in a second, and explicitly flag that you reviewed it in parts rather than claiming full single-pass coverage you didn't actually do.

### Q2 — Why review correctness before security, when a security hole is arguably more dangerous?
**Testing:** understanding that the order is about what invalidates downstream review, not about ranking severity.
**Answer:** It's not that correctness is more important — it's that a correctness bug (wrong algorithm, wrong edge-case handling) usually means the code will be substantially rewritten, making a security review of the current shape wasted effort. In practice both get full attention on any PR that reaches review; the ordering principle matters most for triage under time pressure, where you stop at the first layer that already blocks merge rather than continuing to comment on layers below it.
**Follow-up trap:** *"You find both a correctness bug and a SQL injection in the same function. Which do you report first, and does it change how you write the comment?"* — report both, but lead with the security issue in the written feedback regardless of code-reading order, because severity for triage/prioritization purposes is about production risk, not about which layer you happened to notice first; the reading order and the reporting priority are two different orderings serving two different purposes.

### Q3 — What's actually wrong with a code review that consists entirely of style and naming comments?
**Answer:** It signals either that the reviewer defaulted to the cheapest, most visible layer under time pressure, or that there's no automated lint/format gate, which means a human is doing a linter's job at a linter's cost-effectiveness (much worse) while presumably not budgeting time for what a human is actually needed for — correctness and security judgment a linter can't make.
**Follow-up trap:** *"The team has full lint/format automation already. Is a purely style-focused review comment ever legitimate?"* — rarely, but yes for things automation can't catch: a misleading variable name that doesn't violate any style rule but actively obscures what a value represents, or a comment that's now factually wrong after a nearby change — these aren't "style" in the linter sense, they're correctness-of-communication, which is a real (if minor) review responsibility.

### Q4 — A test suite has 100% line coverage on a new module. Is that sufficient signal that the tests are good?
**Answer:** No — line coverage measures whether a line executed during the test run, not whether the test's assertions would catch a bug on that line. A test can execute every line and assert nothing meaningful (or assert against a mock instead of real behavior) while still showing 100% coverage. The actual check: for each test, would flipping a real conditional or deleting a null check in the implementation cause that specific test to fail.
**Follow-up trap:** *"How would you demonstrate this gap concretely to a teammate who trusts coverage numbers?"* — introduce a deliberate, obviously wrong change to the implementation (mutation testing, informally or via a tool like `mutmut`/PIT/Stryker) and show the suite still passes; this is literally what mutation-testing tools automate, and citing that this exists as a real category of tooling (not just a manual argument) strengthens the answer.

### Q5 — What specifically do you grep for, or look for, to catch an authorization bug (as opposed to an authentication bug) in a PR?
**Answer:** Authentication ("is this a valid logged-in user") is usually handled by shared middleware and rarely wrong in an individual PR. Authorization ("does this specific user have rights to this specific resource") is checked per-endpoint and is exactly where individual PRs introduce bugs — the IDOR pattern, where an endpoint fetches a resource by an ID taken from the request without confirming the caller owns or has rights to that ID. Concretely: for any endpoint taking a resource identifier as a path/query/body parameter, confirm there's a check tying that identifier back to the authenticated caller, not just a check that the caller is logged in at all.
**Follow-up trap:** *"The endpoint does check ownership, but only in the GET handler, not the newly-added PATCH handler in this same PR. How did you find that, mechanically?"* — by reading every handler for the resource, not just the one the PR description focuses on, and specifically comparing the authorization check present in sibling handlers (GET) against the one being added (PATCH) — a common and specifically dangerous pattern is copy-pasting a handler and forgetting to carry over a check that lived in the original.

### Q6 — How do you give feedback on a PR where you fundamentally disagree with the technical approach, but it works and is tested?
**Answer:** Distinguish stated cost from preference. If the divergence creates a concrete future cost (duplicated logic that will drift, an interface violation that makes another module untestable in isolation, a pattern the team explicitly moved away from for a documented reason), say so specifically and treat it as blocking. If it's genuinely "I'd have structured this differently" with no identifiable future cost, phrase it as a non-blocking suggestion and approve — repeatedly blocking correct, tested, low-risk code on stylistic architecture preference is what erodes trust in review as a gate.
**Follow-up trap:** *"The author says your suggested approach would take another two days and this needs to ship today. Do you hold the block?"* — re-evaluate against actual cost: if the identified cost is real but bounded and doesn't compound (a one-time cleanup later), approve now and file a tracked follow-up; if the cost compounds (every future feature in this area now has to work around the wrong abstraction), the two-day cost is cheaper than paying it repeatedly, and that tradeoff — stated in those terms — is the actual argument to make, not a flat refusal.

### Q7 — Someone submits a PR with a new dependency. What do you check beyond "does the code that uses it work"?
**Answer:** License compatibility with the project's own license and any commercial constraints. Whether the dependency is actively maintained (last commit/release date, open critical issues) versus effectively abandoned. Its transitive dependency footprint — a single new import can pull in dozens of transitive packages, each an expansion of supply-chain surface. Whether it duplicates a capability an existing dependency already provides.
**Follow-up trap:** *"The new dependency is from a well-known org, but this specific package has 40 stars and was published three weeks ago. Does the org's reputation cover for that?"* — no; org reputation applies to packages the org has actually invested in maintaining, not to every package published under an org's namespace — a three-week-old, low-adoption package needs the same scrutiny as one from an unknown author, since "who published it" and "how battle-tested is this specific artifact" are separate questions.

### Q8 — What's the actual argument for reviewing tests before implementation code, versus after?
**Answer:** Reading the tests first tells you what behavior the author believes they built, before you've formed your own opinion from reading the implementation — this surfaces gaps between intended and actual behavior faster, and it also tells you where to look hardest in the implementation (whatever the tests don't cover is exactly where an untested edge case is most likely to be wrong).
**Follow-up trap:** *"Doesn't reading tests first bias you toward the author's mental model instead of an independent read of the implementation?"* — partially, yes, which is why the practical approach is: skim tests first to build a map of intended behavior and coverage gaps, then read the implementation independently against actual requirements (not just against what the tests check), specifically hunting in the gaps the test skim revealed.

### Q9 — A PR modifies a shared utility function used in twelve other places. How does your review change compared to reviewing a change isolated to one new feature?
**Answer:** The review has to include impact analysis on the callers, not just the function itself — grep every call site, check whether the change to behavior (not just signature) is compatible with every existing caller's assumptions, and specifically look for callers relying on an edge-case behavior the PR might be "fixing" without realizing something depended on the old behavior.
**Follow-up trap:** *"All twelve call sites' existing tests still pass. Is that sufficient confidence?"* — only if those tests actually exercise the specific behavior that changed; a shared utility with weak test coverage at some call sites can pass all existing tests while still breaking that call site's real production behavior, because the test suite never asserted the behavior that changed in the first place — this loops back to the "do tests assert behavior" check from Q4, applied at every call site, not just the PR's own new tests.

### Q10 — How do you review a PR in a language or subsystem you're not deeply expert in?
**Answer:** Shift more weight toward what transfers regardless of language — does the diff handle the edge inputs (empty, null, boundary, concurrent) that matter in any language, does untrusted input reach a sink unsafely, are tests asserting real behavior. For language-specific idioms and pitfalls you're less sure about, say so explicitly and either loop in someone who is expert, or spend extra time confirming via documentation/testing locally rather than approving on faith.
**Follow-up trap:** *"The PR uses a language feature you don't recognize. Do you block on that alone?"* — no; unfamiliarity isn't itself a defect. Look it up, understand what it does, and evaluate it on the same correctness/security/design criteria as anything else — blocking purely because a construct is unfamiliar to the reviewer, without evaluating whether it's actually wrong, is exactly the kind of feedback that doesn't get acted on and damages review credibility.

### Q11 — What does "feedback that gets acted on" actually look like, mechanically, versus feedback that gets argued with or ignored?
**Answer:** It names the specific defect or cost (not a vague "this feels off"), it's scoped clearly as blocking versus suggestion, it proposes or at least gestures at a fix rather than only pointing at a problem, and it doesn't relitigate a decision the author already made for a stated reason unless there's new information. Comments that read as a personal-style preference dressed up as a requirement get argued with, correctly, because they are arguable.
**Follow-up trap:** *"An author repeatedly dismisses your blocking security comments as 'edge cases that won't happen in practice.' How do you handle it?"* — demonstrate the input concretely (a crafted request, a repro script) rather than continuing to assert it in the abstract; "here's the curl command that returns another user's data" ends the argument in a way "this could be an IDOR" doesn't, and if it still gets dismissed, escalate to whoever owns the security bar for the team rather than approving under repeated pressure.

---

## Red flags that fail you

- Approving a large PR in a few minutes with no stated triage strategy.
- Leading review comments with style/naming when correctness or security issues are present in the same diff.
- Treating "tests pass" or "coverage is 100%" as sufficient without reading what the assertions actually check.
- Blocking a correct, tested, low-risk PR purely on architectural taste with no stated future cost.
- Not distinguishing authentication (is this a valid user) from authorization (does this user have rights to this specific resource) when looking for access-control bugs.
- Reviewing a modified shared utility without checking its other call sites.
- Re-reading an entire diff from scratch after requested changes instead of using an incremental "changes since last review" view.

## Cheat card

```
ORDER: correctness -> security -> design -> tests -> style (each layer invalidates the ones below)

TRIAGE A LARGE PR (don't read linearly):
  git diff --stat main...branch          -- highest-churn files, not highest-line-count
  find changed files with no test touched -- read those at full depth
  trace the entry point (route/handler/main) -- what actually changes behavior
  skim generated/vendored/config files for shape only
  ~60-90 min continuous focus before defect-detection rate drops (Cisco/SmartBear peer-review data)

CORRECTNESS: hand-trace edge inputs -- empty, zero, negative, max, unicode, concurrent, timeout
SECURITY, in frequency order:
  1. untrusted input -> SQL/shell/template without escaping (grep: subprocess, os.system, eval, f"...SELECT)
  2. authz checked at wrong layer -- IDOR: "is logged in" != "owns this resource ID"
  3. secrets/creds in the diff itself
  4. unsafe deserialization of untrusted data (pickle.loads, yaml.load without SafeLoader, Java native serde)
DESIGN: does this fit the codebase's existing shape? name the actual future COST, not just preference
TESTS: would flipping a real conditional / deleting a null check make this test go RED? if not, it tests nothing
  red flag: assert mock.called_with(x) -- asserts a call happened, not that behavior is correct
STYLE: linter's job. repeated human style comments = missing CI gate, not a review finding

FEEDBACK THAT GETS ACTED ON: specific defect/cost, scoped blocking-vs-suggestion, not a rewrite of a
  working approach, backed by a concrete repro when disputed ("here's the curl command"), not an abstract claim
```

## Sources

- [Proof your thousand-line pull requests result in more bugs](https://tekin.co.uk/2020/05/proof-your-thousand-line-pull-requests-create-more-bugs) — accessed 2026-07-28
- [Code Review Checklist: The Complete 2026 Guide](https://refacto.ai/blog/code-review-checklist-the-complete-2026-guide-for-engineering-teams/) — accessed 2026-07-28
- [How to Make Reviewers Love Your Big Pull Requests](https://ieftimov.com/posts/how-to-make-reviewers-love-your-big-pull-requests/) — accessed 2026-07-28
- [Code Review Best Practices for Developers in 2026](https://www.codeant.ai/blogs/code-review-best-practices) — accessed 2026-07-28

## Changelog
- 2026-07-28 — created
