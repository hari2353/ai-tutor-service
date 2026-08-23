#!/usr/bin/env python3
"""Diff a list of topics against the curriculum. Answers one question cheaply:
"is this already covered, and where?"

The expensive way to mine a source (a saved post, a course syllabus, a job ad)
is to transcribe all of it. The cheap way is to extract the TOPIC LIST, run it
through here, and only read deeply where this reports a gap.

Usage:
    python scripts/gap_audit.py topics.txt        # one topic per line
    python scripts/gap_audit.py --stdin           # pipe them in
    echo "pandas groupby" | python scripts/gap_audit.py --stdin

Matching is deliberately loose (token overlap against module titles, slugs and
tags) because a source will say "sliding window" where the curriculum says
"Sliding Window pattern". False positives are cheap to dismiss by eye; false
negatives cost you a rewritten module you already had.
"""
from __future__ import annotations

import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
STOP = {
    "the", "a", "an", "and", "or", "of", "to", "in", "for", "with", "on", "at",
    "how", "what", "why", "when", "is", "are", "it", "its", "your", "you",
    "top", "best", "guide", "tips", "questions", "interview", "using", "from",
}


def _stem(t: str) -> str:
    for suf in ("ing", "ers", "es", "s"):
        if len(t) > 4 and t.endswith(suf):
            return t[: -len(suf)]
    return t


def tokens(s: str) -> set[str]:
    raw = [t for t in re.split(r"[^a-z0-9+#]+", s.lower())
           if t and t not in STOP and len(t) > 2]
    return {_stem(t) for t in raw}


def load_index(deep: bool = True):
    """Every searchable unit: modules, plus problems (so 'pandas' finds the
    problem set even though no module title says it).

    Titles alone give false negatives: "sample ratio mismatch" is covered inside
    T32-experiment-design but appears in no title, and "searching" never matches
    "Modified Binary Search". So when deep=True we also index each module's
    body text, which is what the reader actually gets."""
    import glob
    idx = []
    cur = json.loads((ROOT / "app/data/curriculum.json").read_text(encoding="utf-8"))
    for t in cur["tracks"]:
        files = {pathlib.Path(f).stem: f for f in glob.glob(str(ROOT / t["dir"] / "*.md"))}
        for m in t["modules"]:
            blob = f"{m['title']} {m['slug']} {' '.join(m['tags'])} {t['title']}"
            tok_title = tokens(blob)
            tok_body: set[str] = set()
            if deep:
                hit = next((f for stem, f in files.items() if stem.endswith(m["slug"])), None)
                if hit:
                    body = pathlib.Path(hit).read_text(encoding="utf-8", errors="ignore")
                    # headings and bold runs carry the concepts; full body is too noisy
                    concepts = " ".join(re.findall(r"^#{2,3} (.+)$", body, re.M)
                                        + re.findall(r"\*\*([^*]{3,60})\*\*", body))
                    tok_body = tokens(concepts)
            idx.append(("module", m["id"], m["title"], t["title"], tok_title, tok_body))

    pfile = ROOT / "app/data/problems.json"
    if pfile.exists():
        seen = set()
        for p in json.loads(pfile.read_text(encoding="utf-8")).get("problems", []):
            pat = p.get("pattern", "")
            if pat and pat not in seen:
                seen.add(pat)
                idx.append(("problems", pat, f"{pat} problem set", "Problems tab", tokens(pat), set()))
    return idx


BODY_WEIGHT = 0.55   # mentioning a term in passing is not the same as teaching it


def score(topic_tokens: set[str], entry) -> float:
    """Title/tag overlap counts at full weight; body-only overlap is discounted.
    Without the discount, indexing whole module bodies made every module match
    every topic -- 'pandas for data roles' resolved to a normalization module."""
    if not topic_tokens:
        return 0.0
    title_tok, body_tok = entry[4], entry[5]
    hit_title = topic_tokens & title_tok
    hit_body = (topic_tokens & body_tok) - hit_title
    return (len(hit_title) + BODY_WEIGHT * len(hit_body)) / len(topic_tokens)


def main() -> None:
    args = sys.argv[1:]
    if "--stdin" in args:
        lines = sys.stdin.read().splitlines()
    elif args:
        lines = pathlib.Path(args[0]).read_text(encoding="utf-8").splitlines()
    else:
        print(__doc__)
        sys.exit(2)

    topics = [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]
    idx = load_index()

    covered, partial, gaps = [], [], []
    for topic in topics:
        tt = tokens(topic)
        ranked = sorted(((score(tt, e), e) for e in idx), key=lambda r: -r[0])
        best, entry = ranked[0] if ranked else (0.0, None)
        if best >= 0.6:
            covered.append((topic, entry))
        elif best >= 0.3:
            partial.append((topic, entry, best))
        else:
            gaps.append((topic, ranked[:2]))

    print(f"{len(topics)} topics · {len(covered)} covered · {len(partial)} partial · {len(gaps)} GAPS\n")

    if gaps:
        print("── GAPS — nothing close in the curriculum ──")
        for topic, near in gaps:
            print(f"  ✗ {topic}")
            for s, e in near:
                if e and s > 0:
                    print(f"      nearest {s:.0%}: {e[1]} — {e[2][:60]}")
        print()

    if partial:
        print("── PARTIAL — related module exists, may not cover this angle ──")
        for topic, e, s in partial:
            print(f"  ~ {topic}\n      {s:.0%} {e[1]} — {e[2][:60]}")
        print()

    if covered:
        print("── COVERED ──")
        for topic, e in covered:
            print(f"  ✓ {topic}  →  {e[1]}")

    sys.exit(1 if gaps else 0)


if __name__ == "__main__":
    main()
