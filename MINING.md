# Mining external sources without burning tokens

Saved posts, course syllabi, job ads and "top 50 X" lists are useful for one thing:
**telling you what you have not covered.** They are almost never better than the modules
you already have — 452 modules with cited sources beat a carousel — but they surface
topics you never thought to scope.

Transcribing them is the expensive way to find that out. Here is the cheap way.

## The rule

**Read titles, not contents. Diff, then deep-read only the gaps.**

A 12-slide carousel costs ~12 screenshots to transcribe. Its *first* slide plus its caption
costs one, and that is enough to know the topic. Multiply by dozens of saved posts and the
difference is the whole budget.

## The loop

1. **Collect topics cheaply.** One line per source. From a post: the hook slide and caption.
   From a syllabus: the section headings. From a job ad: the requirements list.

   ```
   Arrays and Hashing
   Pandas for data roles
   SQL window functions
   A/B test sample ratio mismatch
   ```

2. **Diff against the curriculum.**

   ```bash
   python scripts/gap_audit.py topics.txt
   ```

   Output is three buckets: **COVERED** (with the module id), **PARTIAL** (related module
   exists, may not cover this angle), and **GAPS** (nothing close). It exits non-zero if
   there are gaps, so it works in a script.

3. **Only deep-read the gaps.** If a topic is covered, you are done — do not read the
   source. If it is partial, open the named module and check whether the angle is really
   there. If it is a gap, *then* spend the screenshots.

4. **Add what is genuinely missing** via `build_data.py`'s spec and the module format.

## Why this exists

The first real test of it: a saved post titled *"Top 50 Python LeetCode questions for data
jobs"* listed six sections. Five were already covered by the 250-problem set. One —
**LeetCode's Pandas track** — was not, and neither was SQL, despite both having full
modules written. The Problems tab had 250 problems and zero for either.

That gap was worth finding. The other five sections were not worth reading. One screenshot
found it; transcribing twelve slides would have found the same thing for twelve times the
cost.

Result: `app/data/problemsets/pandas.json` and `sql.json`, 60 problems, 250 → 310.

## How the matcher works, and where it lies to you

`gap_audit.py` scores token overlap between your topic and each module's title, tags and
track, plus a **discounted** pass over the module's headings and bold runs.

The discount matters. An earlier version indexed module bodies at full weight and reported
everything as covered — "pandas for data roles" resolved to a *normalization* module,
because a 5,000-word module mentions enough terms to match almost any topic. Body evidence
is now weighted 0.55, so a passing mention cannot outrank a real title match.

It also stems plurals and gerunds, because "searching" never matched "Modified Binary
Search" and that produced a false gap.

**It will still lie to you occasionally**, in both directions:

- *False covered* — a module whose body mentions your topic once. Check the named module
  before you trust it. That is why the module id is always printed.
- *False gap* — a topic the curriculum calls something else entirely. Skim the nearest
  matches it prints before writing anything new.

Treat it as triage, not as truth. It is there to stop you re-writing something you already
have, and to stop you reading a source you do not need.

## Instagram specifically

The carousel slide is in the URL as `?img_index=N`, so slides can be stepped without
clicking. In this setup the browser is granted read-only (visible, no clicks), but File
Explorer is not — typing a URL into Explorer's address bar launches it in the default
browser, and the resulting page can then be screenshotted.

It works, and it is still one screenshot per slide. Use it for the gaps, not the survey.

If you want this to be genuinely cheap and automatic, install the **Claude in Chrome**
extension: it reads page *text* rather than pixels, which is far cheaper than images, and
it can navigate on its own.
