---
name: tutor-update
description: Pull only what changed since the last run from AWS/Azure/GCP release feeds and the AI stack (LangGraph, MCP, vLLM, model releases), append dated changelog entries, patch affected curriculum pages, and advance the watermark. Use when the user says /tutor-update, "update the curriculum", "what changed since last time", "refresh the cloud atlas", or asks whether the tutor content is current.
---

# tutor-update

**Delta only.** Nothing is re-fetched and nothing already written is rewritten wholesale. The watermark is what makes this cheap enough to run weekly.

**Repo root** (`$ROOT`): the directory containing `CONTENT-STATUS.md`. Find it by walking up from your current working directory until that file appears; if you never find it, ask the user where the repo lives — do not guess a path.

## 1. Read the watermarks

```
$ROOT/clouds/aws/changelog/LAST_UPDATED.json
$ROOT/clouds/azure/changelog/LAST_UPDATED.json
$ROOT/clouds/gcp/changelog/LAST_UPDATED.json
$ROOT/curriculum/.LAST_UPDATED.json      (scope: ai-stack)
```

Shape: `{"provider":"aws","last_updated":"2026-07-26","last_item_guid":"","runs":0}`

Everything before `last_updated` is already accounted for. If `runs` is 0 the watermark is a seed, not a real run — say so, and treat the seed date as the start.

## 2. Fetch the delta

Only items dated after the watermark.

| Scope | Sources |
|---|---|
| AWS | AWS What's New feed, service release notes for the atlas services |
| Azure | Azure Updates feed |
| GCP | Google Cloud release notes |
| AI stack | LangGraph/LangChain releases, MCP spec + SDK releases, vLLM/SGLang releases, model launches and deprecations from Anthropic/OpenAI/Google/Meta, notable papers that changed a default |

Use `WebSearch` and `WebFetch`. Prefer official release notes over roundup blogs.

## 3. Filter hard — this is the whole skill

Most cloud announcements are irrelevant to a Principal AI Engineer interview. Keep an item only if at least one is true:

- it changes a **default, limit, or price** that a written module states
- it **deprecates or GAs** something a module calls current
- it changes the **right answer to an interview question** in the curriculum
- it is a model or serving change that moves the **latency/accuracy/cost triangle**

Drop everything else. A changelog nobody reads is the failure mode here; ten filtered items beat two hundred logged ones. Report how many you dropped so the filtering stays visible.

## 4. Write

**Changelog entries** → `$ROOT/clouds/<provider>/changelog/<YYYY-MM>.md`, appended, newest last:

```markdown
## 2026-08-01
- **<Service> — <what changed>.** <Why it matters for the curriculum, one line.>
  Affects: `T06-vector-index-internals`. [source](url) — accessed 2026-08-01
```

**Patch affected modules.** For each module named in `Affects:`, edit only the specific claim, and add a line to that module's `## Changelog` section:

```markdown
- 2026-08-01 — updated <section>: <old claim> → <new claim>
```

Never rewrite a module wholesale from an update. If a change is big enough to need a rewrite, say so and hand off to `/tutor-deepdive`.

**Flashcards.** If a patched number appears on a card, correct the card in `$ROOT/app/data/cards/<module-id>.json` — the fragment, never the aggregate. The merge is by id, so an edited card replaces the stale one on the next build.

## 5. Advance the watermark and reindex

```json
{"provider":"aws","last_updated":"2026-08-01","last_item_guid":"<newest guid>","runs":<n+1>}
```

Only after the writes succeed — a bumped watermark with no content silently skips that window forever.

```bash
python app/build_data.py
```

## 6. Report

```
UPDATE  <last watermark> → <today>

AWS     <n> kept / <n> seen
AZURE   <n> kept / <n> seen
GCP     <n> kept / <n> seen
AI      <n> kept / <n> seen

PATCHED
  <module-id> — <what changed>

NEEDS A REWRITE, NOT A PATCH
  <module-id> — <why>

NOTHING CHANGED FOR
  <tracks with no relevant delta>
```

## Rules

- Cite every claim with a URL and access date.
- If a source is unreachable, say so and do **not** advance that provider's watermark.
- Never fabricate a release. An empty delta is a good result; report it as one.
- Weekly on Saturday morning pairs with the weekend cadence — offer to schedule it if `runs` is still low.
