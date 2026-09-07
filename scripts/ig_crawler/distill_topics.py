"""Distill mining/topics.json into a genuine gap shortlist.

The raw build_topics output has 19,420 clusters, 90% noise (hype posts,
giveaways, memes, non-educational accounts, singletons). This pass:

  1. keeps clusters with real signal (>= 3 member posts, or a saved post)
  2. drops hype/meme/sale posts via a hard phrase blocklist
  3. extracts a TOPIC LINE from OCR text when available (slide 1 is the
     real title), falling back to the caption
  4. re-audits each distilled topic against the 454-module curriculum
  5. writes mining/gap_shortlist.md - the ranked list of what is actually
     missing, with the OCR hook line as evidence

Run:  python scripts/ig_crawler/distill_topics.py
"""
from __future__ import annotations

import json
import pathlib
import re
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("\\", 1)[0])
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import common
import gap_audit

# ── hype / meme / non-educational phrases: kill at the source ──────────
HYPE = [
    "link in bio", "subscribe", "180% hike", "giveaway", "dm me", "comment ",
    "share this", "save this for", "future of work", "freelancing is",
    "is freelancing", "only god can save", "what is your opinion",
    "porsche", "finland is doing", "personal story", "motivat",
    "like and share", "first like", "follow for", "limited seats",
    "enroll now", "discount", "course fee", "i failed interviews",
    "my journey", "day 1 of", "happy to announce", "we are hiring",
    "etiquette", "reels", "explore page", "viral",
]
# accounts that are pure hype/meme/real-estate, seen in the top list
BAD_CREATORS = {
    "kethakiproperties", "entrepreneursonig", "whatshotdelhi",
    "futurewalt.ai", "duodevlogs", "mrk_talkstech",
}

MIN_CLUST = 3          # cluster size: the crowd-vote signal


def looks_hype(text: str) -> str | None:
    low = text.lower()
    for h in HYPE:
        if h in low:
            return h
    return None


def ocr_topic_line(code: str) -> str:
    """Slide-1 text is the real title of a carousel. Take the first
    non-blank chunk of OCR, cleaned; else ''. """
    p = common.POSTS / code / "ocr.txt"
    if not p.exists():
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
    if not text.strip() or text.startswith("["):
        return ""
    first = text.split("-----", 1)[0]  # text before the 2nd slide marker
    first = re.sub(r"\s+", " ", first).strip()
    return first[:200]


def caption_topic_line(caption: str) -> str:
    cap = re.sub(r"#\w+", "", caption or "")
    cap = re.sub(r"\s+", " ", cap).strip()
    first = re.split(r"[.!?\n]", cap)[0].strip()
    return first[:150]


def main() -> None:
    topics = json.loads((common.MINE / "topics.json")
                        .read_text(encoding="utf-8"))["topics"]

    # load state to know which posts the user actually saved (strong signal)
    st = common.load_state()
    saved = {c for c, r in st["records"].items()
             if r.get("source") == "saved"}

    idx = gap_audit.load_index()

    kept, dropped = [], Counter()
    for t in topics:
        rep = t["representative"]
        rep_creator = rep["creator"]
        label = rep.get("caption") or ""
        members = t["members"]

        if t["count"] < MIN_CLUST and not (set(members) & saved):
            dropped["singleton (<3 posts, not saved)"] += 1
            continue
        if rep_creator in BAD_CREATORS:
            dropped["hype/meme creator"] += 1
            continue

        # topic line: OCR slide-1 > caption first sentence
        ocr_line = ocr_topic_line(rep["shortcode"])
        hype_hit = looks_hype(label) or (ocr_line and looks_hype(ocr_line))
        if hype_hit:
            dropped["hype phrase"] += 1
            continue

        topic = ocr_line or caption_topic_line(label)
        if not topic or len(topic.strip()) < 8:
            dropped["no topic text"] += 1
            continue

        tt = gap_audit.tokens(topic)
        if not tt:
            dropped["no tokens"] += 1
            continue
        ranked = sorted(((gap_audit.score(tt, e), e) for e in idx),
                        key=lambda r: -r[0])
        best, entry = ranked[0] if ranked else (0.0, None)
        verdict = ("covered" if best >= 0.6 else
                   "partial" if best >= 0.3 else "GAP")

        kept.append({
            "topic": topic,
            "verdict": verdict,
            "best": round(best, 2),
            "nearest": f"{entry[1]} — {entry[2][:60]}" if entry else "",
            "count": t["count"],
            "creator": rep_creator,
            "rep": rep["shortcode"],
            "key": t["key"],
        })

    gaps = [k for k in kept if k["verdict"] == "GAP"]
    partials = [k for k in kept if k["verdict"] == "partial"]
    covered = [k for k in kept if k["verdict"] == "covered"]

    # rank gaps by cluster size (crowd vote) then by OCR-verified text
    gaps.sort(key=lambda k: (-k["count"], -k["best"], k["topic"]))
    partials.sort(key=lambda k: (-k["count"], -k["best"], k["topic"]))

    lines = ["# Curriculum gap shortlist (distilled)", "",
             f"from 19,420 raw clusters -> {len(kept)} real topics "
             f"({len(gaps)} gaps, {len(partials)} partial, {len(covered)} covered)", "",
             "## GAPS - genuinely missing from the 454 modules", ""]
    for k in gaps:
        lines.append(f"- **{k['topic'][:120]}** ×{k['count']} — @{k['creator']} "
                     f"(rep: mining/posts/{k['rep']}/)")
        if k["nearest"]:
            lines.append(f"    nearest: {k['nearest']}")
    lines += ["", "## PARTIAL - related module exists, angle may differ", ""]
    for k in partials[:80]:
        lines.append(f"- ~{k['topic'][:120]} ×{k['count']} → {k['nearest']} ({k['best']:.0%})")

    lines += ["", "## Dropped by filter", ""]
    for reason, n in dropped.most_common():
        lines.append(f"- {n}: {reason}")

    (common.MINE / "gap_shortlist.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")

    print(f"kept {len(kept)} topics: {len(gaps)} gaps, "
          f"{len(partials)} partial, {len(covered)} covered")
    print(f"dropped: {dict(dropped.most_common())}")
    print("wrote mining/gap_shortlist.md")


if __name__ == "__main__":
    main()
