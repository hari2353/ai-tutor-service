#!/usr/bin/env python3
"""Turn an Instagram "Download Your Information" export into a gap worklist.

WHY THIS SHAPE, and not a scraper:

  * There is no official API for saved posts. The Instagram Graph API exposes
    GET /me/media -- your OWN posts, and only for Business/Creator accounts.
    Saved collections are not in any published endpoint. The Basic Display API,
    which some guides still reference, was deprecated in December 2024.
  * Getting them any other way means driving your authenticated session with an
    automation tool. That is against Instagram's Terms of Use, and the account
    it puts at risk is yours -- rate-limiting, checkpoints, or a ban. Mass-
    pulling a third party's whole feed is the same problem, louder.
  * The official export is user-initiated, complete, free, and gives you the
    thing that actually matters: URLs and captions.

So: you request the export once, this script does the triage, and you only ever
open the handful of posts that turn out to be genuinely new.

HOW TO GET THE EXPORT
  Instagram -> Settings -> Accounts Centre -> Your information and permissions
  -> Download your information -> select "Saved" (JSON format).
  Delivery is usually minutes to a few hours.

USAGE
  python scripts/mine_saved.py path/to/export_dir_or_file
  python scripts/mine_saved.py export/ --min-score 2

OUTPUT (all under mining/)
  saved_index.json   every saved post: url, creator, caption, class, score
  topics.txt         one topic line per study post -- feed to gap_audit.py
  worklist.md        ONLY the posts whose topics are gaps. Read these, ignore the rest.
"""
from __future__ import annotations

import argparse
import html
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
OUT = ROOT / "mining"

# Signals that a saved post is technical. Weighted: a term in the first line of
# a caption is usually the topic; a term buried in hashtags is weaker evidence.
STUDY_TERMS = {
    3: ["leetcode", "system design", "machine learning", "kubernetes", "terraform",
        "transformer", "embedding", "rag", "langgraph", "pytorch", "spark",
        "airflow", "snowflake", "databricks", "bigquery", "kafka", "postgres",
        "algorithm", "data structure", "microservice", "distributed"],
    2: ["python", "sql", "pandas", "numpy", "docker", "aws", "azure", "gcp",
        "api", "database", "backend", "devops", "mlops", "llm", "agent",
        "interview question", "coding", "架构", "statistics", "bayesian"],
    1: ["interview", "engineer", "developer", "tech", "career", "resume",
        "job", "hiring", "salary", "data", "cloud", "ai"],
}
# Engagement-bait and listicles. "Comment X and I'll DM you the PDF" is the
# dominant format on tech Instagram and carries no content -- the post IS the
# ask. Weighted -6 so a single hit sinks a post even if it name-drops Python.
NOISE = ["giveaway", "follow for", "link in bio", "dm me", "course fee",
         "enroll now", "limited seats", "discount", "comment ", "in your dm",
         "send you", "i'll send", "will send", "premium prompts", "free pdf",
         "repositories are replacing", "apps you", "tools you need"]
NOISE_WEIGHT = 6


def load_export(path: pathlib.Path) -> list[dict]:
    """Tolerant of the JSON export and the HTML one, and of Instagram renaming
    things between export versions -- which it does."""
    files = []
    if path.is_dir():
        files = [p for p in path.rglob("*") if p.suffix.lower() in (".json", ".html")
                 and "saved" in p.name.lower()]
        if not files:  # fall back: any json under a saved_* directory
            files = [p for p in path.rglob("*.json") if "saved" in str(p).lower()]
    else:
        files = [path]

    if not files:
        sys.exit(f"no saved-posts export found under {path}\n"
                 f"expected something like saved_posts.json or saved_collections.html")

    posts: list[dict] = []
    for f in files:
        raw = f.read_text(encoding="utf-8", errors="ignore")
        if f.suffix.lower() == ".json":
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                continue
            posts += _walk_json(data)
        else:
            # HTML export: anchors to /p/<shortcode>/ with the caption nearby
            for m in re.finditer(r'href="(https://www\.instagram\.com/p/[^"/]+/?)"', raw):
                posts.append({"url": m.group(1), "caption": "", "creator": ""})
    # dedupe by shortcode
    seen, out = set(), []
    for p in posts:
        code = re.search(r"/p/([^/?]+)", p.get("url", ""))
        key = code.group(1) if code else p.get("url")
        if key and key not in seen:
            seen.add(key)
            p["shortcode"] = key
            out.append(p)
    return out


def _walk_json(node, acc=None) -> list[dict]:
    """Instagram nests saved posts differently across export versions, so walk
    rather than assume a path."""
    acc = acc if acc is not None else []
    if isinstance(node, dict):
        smd = node.get("string_map_data")
        # The export nests the permalink INSIDE string_map_data (usually under
        # "Saved on"), not on the post node itself -- so look there first, or
        # captions never attach to their URL and everything scores zero.
        href, caption = "", ""
        if isinstance(smd, dict):
            for key, val in smd.items():
                if not isinstance(val, dict):
                    continue
                h = val.get("href", "")
                if isinstance(h, str) and "/p/" in h:
                    href = h
                if key.lower().startswith("caption"):
                    caption = val.get("value", "") or ""
        href = href or node.get("href") or node.get("url") or ""
        if isinstance(href, str) and "/p/" in href:
            acc.append({
                "url": href,
                "creator": node.get("title") or node.get("value") or "",
                "caption": caption,
            })
        for v in node.values():
            _walk_json(v, acc)
    elif isinstance(node, list):
        for v in node:
            _walk_json(v, acc)
    return acc


def classify(caption: str, creator: str) -> tuple[int, list[str]]:
    text = html.unescape(f"{caption} {creator}").lower()
    first = text[:200]           # the hook usually states the topic
    score, hits = 0, []
    for weight, terms in STUDY_TERMS.items():
        for t in terms:
            if t in text:
                score += weight * (2 if t in first else 1)
                hits.append(t)
    for n in NOISE:
        if n in text:
            score -= NOISE_WEIGHT
    if not hits:
        score -= 4      # no technical term anywhere -- e.g. a bare location string
    return score, sorted(set(hits))


def topic_line(post: dict) -> str:
    """One line that names the topic. The caption's first sentence is almost
    always it; hashtags are noise."""
    cap = html.unescape(post.get("caption") or "")
    cap = re.sub(r"#\w+", "", cap)
    cap = re.sub(r"\s+", " ", cap).strip()
    first = re.split(r"[.!?\n]", cap)[0].strip()
    return (first or " ".join(post.get("hits", [])[:4]) or post["shortcode"])[:120]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("export", type=pathlib.Path)
    ap.add_argument("--min-score", type=int, default=2,
                    help="classify as study at or above this score (default 2)")
    a = ap.parse_args()

    posts = load_export(a.export)
    for p in posts:
        p["score"], p["hits"] = classify(p.get("caption", ""), p.get("creator", ""))
        p["class"] = "study" if p["score"] >= a.min_score else "skip"
        p["topic"] = topic_line(p)

    study = [p for p in posts if p["class"] == "study"]
    OUT.mkdir(exist_ok=True)
    (OUT / "saved_index.json").write_text(
        json.dumps({"total": len(posts), "study": len(study), "posts": posts}, indent=2),
        encoding="utf-8")
    (OUT / "topics.txt").write_text(
        "\n".join(f"{p['topic']}" for p in study) + "\n", encoding="utf-8")

    by_creator: dict[str, int] = {}
    for p in study:
        by_creator[p.get("creator") or "unknown"] = by_creator.get(p.get("creator") or "unknown", 0) + 1

    print(f"  {len(posts)} saved posts · {len(study)} classified study · "
          f"{len(posts)-len(study)} skipped")
    print(f"  wrote {OUT/'saved_index.json'} and {OUT/'topics.txt'}")
    if by_creator:
        print("  top creators among study posts:")
        for c, n in sorted(by_creator.items(), key=lambda x: -x[1])[:5]:
            print(f"    {n:3}  {c}")
    # Run the gap audit inline and emit a worklist of ONLY the posts worth
    # opening. The whole point is that you never read the covered ones.
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import gap_audit
        idx = gap_audit.load_index()
        rows = []
        for post in study:
            tt = gap_audit.tokens(post["topic"])
            ranked = sorted(((gap_audit.score(tt, e), e) for e in idx), key=lambda r: -r[0])
            best, entry = ranked[0] if ranked else (0.0, None)
            verdict = "covered" if best >= 0.6 else "partial" if best >= 0.3 else "GAP"
            post["verdict"] = verdict
            post["nearest"] = entry[1] if entry else ""
            post["nearest_score"] = round(best, 2)
            rows.append(post)

        gaps = [r for r in rows if r["verdict"] == "GAP"]
        partial = [r for r in rows if r["verdict"] == "partial"]
        lines = ["# Mining worklist", "",
                 f"{len(rows)} study posts · **{len(gaps)} gaps** · {len(partial)} partial · "
                 f"{len(rows)-len(gaps)-len(partial)} already covered", "",
                 "Open the gaps. Skim the partials to check the angle. Ignore the rest —",
                 "that is the entire saving.", "", "## Gaps — nothing close in the curriculum", ""]
        for r in gaps or [None]:
            if r is None:
                lines.append("_none — your saved posts are fully covered._")
                break
            lines.append(f"- [ ] [{r['topic']}]({r['url']}) — @{r.get('creator','?')}")
        lines += ["", "## Partial — related module exists, check the angle", ""]
        for r in partial:
            lines.append(f"- [ ] [{r['topic']}]({r['url']}) — nearest `{r['nearest']}` "
                         f"({r['nearest_score']:.0%})")
        (OUT / "worklist.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
        (OUT / "saved_index.json").write_text(
            json.dumps({"total": len(posts), "study": len(study), "posts": posts}, indent=2),
            encoding="utf-8")
        print(f"  gap audit: {len(gaps)} gaps · {len(partial)} partial · "
              f"{len(rows)-len(gaps)-len(partial)} covered")
        print(f"  wrote {OUT/'worklist.md'} — open only what is listed there")
    except Exception as e:
        print(f"  (gap audit skipped: {e})")
        print("  run manually:  python scripts/gap_audit.py mining/topics.txt")


if __name__ == "__main__":
    main()
