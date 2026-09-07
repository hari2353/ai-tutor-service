"""Topic clustering: turn thousands of overlapping posts into a compact list
of UNIQUE topics. Groups useful posts by their strong-term signature plus
fuzzy caption key, keeps representative posts per topic, and writes:

  mining/topics.json     topic -> count, creators, sample posts, gap verdict
  mining/topic_worklist.md   deduped, ranked list of what to actually read

The point: 6,712 "gap posts" are maybe 60 real topics once you remove the
recycling (educators repost the same carousel every few weeks).
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter, defaultdict

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import common
import run_enrich as re_mod

STRONG = re_mod.STUDY_TERMS[3] + re_mod.STUDY_TERMS[2]


def norm_key(caption: str) -> str:
    """Fingerprint = the STRONG technical terms present (order-free) plus, if
    none, the caption's top nouns. Posts about the same concept from
    different educators collapse together; that is the entire point."""
    text = caption.lower()
    terms = sorted({t for t in STRONG if t in text})
    if terms:
        return "|".join(terms)
    words = re.findall(r"[a-z][a-z0-9+#]{3,}", text)
    stop = set("this that with your you are for the and from have will what "
              "when how why just like more most best top here they them there "
              "about into some than then only also very much many every need "
              "want know get can now new using make made keep comment share "
              "save follow dm link full start check read learn".split())
    words = [w for w in words if w not in stop][:4]
    return "weak:" + " ".join(sorted(set(words))) if words else "weak:none"


def main() -> None:
    g = json.loads((common.MINE / "graph.json").read_text(encoding="utf-8"))
    posts = [n for n in g["nodes"] if n["kind"] == "post" and n.get("useful")]
    clusters: dict[str, list] = defaultdict(list)
    for p in posts:
        clusters[norm_key(p.get("caption") or "")].append(p)

    # merge tiny clusters into "other" later; keep those with >=1 post
    topics = []
    for key, members in clusters.items():
        verdicts = Counter((m.get("gap") or {}).get("verdict") for m in members)
        creators = Counter(m.get("creator") for m in members)
        rep = max(members, key=lambda m: len(m.get("caption") or ""))
        topics.append({
            "key": key,
            "label": rep.get("topic") or rep["shortcode"],
            "count": len(members),
            "gap_verdict": verdicts.most_common(1)[0][0] or "n/a",
            "top_creators": creators.most_common(3),
            "representative": {
                "shortcode": rep["shortcode"],
                "creator": rep["creator"],
                "caption": (rep.get("caption") or "")[:400],
                "source": rep.get("source"),
            },
            "members": [m["shortcode"] for m in members][:40],
        })
    topics.sort(key=lambda t: (-t["count"], t["label"]))

    (common.MINE / "topics.json").write_text(
        json.dumps({"topics": topics, "total_posts": len(posts),
                    "unique_topics": len(topics)}, indent=2, ensure_ascii=False),
        encoding="utf-8")

    gap_topics = [t for t in topics if t["gap_verdict"] == "GAP"]
    partial_topics = [t for t in topics if t["gap_verdict"] == "partial"]
    lines = ["# Topic worklist (deduped)", "",
             f"{len(posts)} useful posts -> **{len(topics)} unique topics** "
             f"({len(gap_topics)} gaps, {len(partial_topics)} partial)", "",
             "## Gap topics, by frequency", ""]
    for t in gap_topics[:200]:
        lines.append(f"- **{t['label'][:110]}** ×{t['count']} "
                     f"— @{t['top_creators'][0][0]} "
                     f"(rep: mining/posts/{t['representative']['shortcode']}/)")
    lines += ["", "## Partial topics", ""]
    for t in partial_topics[:100]:
        lines.append(f"- ~{t['label'][:110]} ×{t['count']}")
    (common.MINE / "topic_worklist.md").write_text("\n".join(lines) + "\n",
                                                    encoding="utf-8")
    print(f"{len(posts)} useful posts -> {len(topics)} unique topics "
          f"({len(gap_topics)} gaps, {len(partial_topics)} partial)")
    print("wrote mining/topics.json + mining/topic_worklist.md")


if __name__ == "__main__":
    main()
