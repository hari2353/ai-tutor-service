"""Phase 6: enrich. Classify every record (study vs noise, reusing
mine_saved.py's weighted term lists), run gap_audit against the curriculum,
and write:

  mining/graph.json    nodes (you -> creators -> posts) + edges
  mining/posts/<code>/notes.md   per-post extracted content (caption,
                       links, media inventory, OCR text, verdict)
  mining/worklist.md   only the posts worth reading deeply

Run:  python scripts/ig_crawler/run_enrich.py
"""
from __future__ import annotations

import html
import json
import pathlib
import re
import sys

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import common

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
NOISE = ["giveaway", "follow for", "link in bio", "dm me", "course fee",
         "enroll now", "limited seats", "discount", "comment ", "in your dm",
         "send you", "i'll send", "will send", "premium prompts", "free pdf",
         "repositories are replacing", "apps you", "tools you need"]
NOISE_WEIGHT = 6

try:
    import gap_audit
    GAP_INDEX = gap_audit.load_index()
except Exception as e:
    print(f"(gap audit unavailable: {e})")
    GAP_INDEX = None


def classify(caption: str, creator: str):
    text = html.unescape(f"{caption} {creator}").lower()
    first = text[:200]
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
        score -= 4
    return score, sorted(set(hits))


def gap_check(topic: str):
    if not GAP_INDEX:
        return None
    tt = gap_audit.tokens(topic)
    ranked = sorted(((gap_audit.score(tt, e), e) for e in GAP_INDEX), key=lambda r: -r[0])
    best, entry = ranked[0] if ranked else (0.0, None)
    return {"verdict": "covered" if best >= 0.6 else "partial" if best >= 0.3 else "GAP",
            "nearest": entry[1] if entry else "", "nearest_title": entry[2][:80] if entry else "",
            "score": round(best, 2)}


def topic_line(caption: str, hits: list) -> str:
    cap = html.unescape(caption or "")
    cap = re.sub(r"#\w+", "", cap)
    cap = re.sub(r"\s+", " ", cap).strip()
    first = re.split(r"[.!?\n]", cap)[0].strip()
    return (first or " ".join(hits[:4]) or "")[:120]


def main() -> None:
    st = common.load_state()
    records = st["records"]
    username = st.get("username") or "me"

    nodes, edges = [], []
    nodes.append({"id": f"user:{username}", "kind": "user", "label": username})
    creators_seen = {}
    gaps, partials, covered_n = [], [], 0

    for code, rec in records.items():
        cu = rec.get("creator_username") or "unknown"
        if cu not in creators_seen:
            creators_seen[cu] = True
            nodes.append({"id": f"creator:{cu}", "kind": "creator", "label": cu,
                          "full_name": rec.get("creator_full_name", ""),
                          "verified": rec.get("creator_verified", False)})
            edges.append({"from": f"user:{username}", "to": f"creator:{cu}",
                          "rel": "saved_from" if rec.get("source") == "saved" else "expanded"})
        score, hits = classify(rec.get("caption", ""), cu)
        useful = score >= 2
        topic = topic_line(rec.get("caption", ""), hits)
        gap = gap_check(topic) if (useful and topic) else None
        verdict = (gap or {}).get("verdict", "n/a")
        if useful and gap:
            if verdict == "GAP":
                gaps.append((code, topic, cu))
            elif verdict == "partial":
                partials.append((code, topic, cu))
            else:
                covered_n += 1
        pdir = common.POSTS / code
        if not pdir.exists() and useful:
            pdir.mkdir(parents=True, exist_ok=True)
        media_files = sorted(p.name for p in pdir.glob("*")) if pdir.exists() else []
        nodes.append({
            "id": f"post:{code}", "kind": "post", "shortcode": code,
            "creator": cu, "source": rec.get("source", ""),
            "useful": useful, "score": score, "hits": hits, "topic": topic,
            "gap": gap, "caption": rec.get("caption", ""),
            "caption_links": rec.get("caption_links", []),
            "media_count": len(rec.get("items", [])),
            "media_files": media_files,
        })
        edges.append({"from": f"creator:{cu}", "to": f"post:{code}", "rel": "posted"})
        # per-post note
        if pdir.exists():
            lines = [f"# @{cu} — {topic or code}", "",
                     f"- shortcode: `{code}`  ·  source: {rec.get('source','')}",
                     f"- verdict: useful={useful} score={score} hits={hits}",
                     f"- curriculum: {verdict}"
                     + (f" (nearest {gap['nearest']}, {gap['score']:.0%})" if gap else ""),
                     f"- media: {len(rec.get('items', []))} items -> {media_files}",
                     "", "## Caption", "", rec.get("caption", "") or "_none_", ""]
            if rec.get("caption_links"):
                lines += ["## Links in caption", ""]
                lines += [f"- {u}" for u in rec["caption_links"]] + [""]
            (pdir / "notes.md").write_text("\n".join(lines), encoding="utf-8")

    graph = {
        "root": f"user:{username}",
        "node_count": len(nodes),
        "edge_count": len(edges),
        "nodes": nodes,
        "edges": edges,
    }
    (common.MINE / "graph.json").write_text(
        json.dumps(graph, indent=2, ensure_ascii=False), encoding="utf-8")

    wl = ["# Mining worklist (crawl)", "",
          f"{len(records)} posts · {len(gaps)} gaps · {len(partials)} partial · {covered_n} covered",
          "", "## Gaps", ""]
    wl += [f"- [ ] {t} — @{c} — mining/posts/{code}/notes.md" for code, t, c in gaps]
    wl += ["", "## Partial", ""]
    wl += [f"- [ ] {t} — @{c} — mining/posts/{code}/notes.md" for code, t, c in partials]
    (common.MINE / "worklist.md").write_text("\n".join(wl) + "\n", encoding="utf-8")

    print(f"graph: {len(nodes)} nodes / {len(edges)} edges -> mining/graph.json")
    print(f"classified: {len(gaps)} gaps · {len(partials)} partial · {covered_n} covered")
    print(f"worklist -> mining/worklist.md")


if __name__ == "__main__":
    main()
