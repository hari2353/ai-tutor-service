#!/usr/bin/env python3
"""Mechanical review gate. Checks every written module against the parts of the
MODULE-SPEC checklist that can be verified without judgement. Items needing
judgement (is the tradeoff claim actually TRUE) still require a human/Opus pass."""
import json, pathlib, re, sys, glob

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent
d = json.loads((ROOT / "app/data/curriculum.json").read_text(encoding="utf-8"))

# Two profiles. Pattern modules (DSA) legitimately swap the generic
# mechanics sections for recognition heuristics + templates + variants,
# which is what the brief asked them to do. Playbook modules swap
# "build it from scratch" for a practical exercise.
COMMON = [
    ("30-second version", r"##\s*The 30-second version"),
    ("why asked",         r"##\s*Why this gets asked"),
    ("lineage",           r"##\s*Lineage"),
    ("mental model",      r"##\s*Mental model"),
    ("questions",         r"##\s*Interview questions"),
    ("red flags",         r"##\s*Red flags"),
    ("cheat card",        r"##\s*Cheat card"),
    ("sources",           r"##\s*Sources"),
    ("changelog",         r"##\s*Changelog"),
]
STANDARD = COMMON + [
    ("how it works",  r"##\s*How it actually works"),
    ("from scratch",  r"##\s*(?:Build it from scratch|Practical exercise|Rehearsal|Exercise)"),
    ("production",    r"##\s*How it's done in production"),
    ("tradeoffs/NOT", r"##\s*Tradeoffs"),
]
PATTERN = COMMON + [
    ("recognition", r"##\s*Recognition heuristics"),
    ("templates",   r"##\s*Template code"),
    ("complexity",  r"##\s*Complexity"),
    ("variants",    r"##\s*The 5 variants"),
    ("common bugs", r"##\s*Common bugs"),
]
# T15 boss rounds are runnable interview rounds, not deep dives: a format spec,
# a calibrated question bank and a rubric. They have no lineage and no
# "build it from scratch" because neither means anything for a round, so the
# standard profile fails all of them for the wrong reason.
BOSS = [
    ("round summary",  r"##\s*The round in 30 seconds"),
    ("format",         r"##\s*Format"),
    ("what's tested",  r"##\s*What is actually being tested"),
    ("question bank",  r"##\s*Question bank"),
    ("rubric",         r"##\s*Rubric"),
    ("score bands",    r"##\s*Score bands"),
    ("red flags",      r"##\s*Red flags"),
    ("time failures",  r"##\s*Time-management failures"),
    ("cheat card",     r"##\s*Cheat card"),
    ("sources",        r"##\s*Sources"),
    ("changelog",      r"##\s*Changelog"),
]

rows, hard_fails = [], 0
for t in d["tracks"]:
    for m in t["modules"]:
        hits = [p for p in glob.glob(str(ROOT / t["dir"] / "*.md"))
                if pathlib.Path(p).stem.endswith(m["slug"])]
        if not hits:
            continue
        txt = pathlib.Path(hits[0]).read_text(encoding="utf-8")
        boss = t["id"] == "T15"
        req = PATTERN if t["id"] == "T02" else BOSS if boss else STANDARD
        # the full-loop round orchestrates the other five rather than holding its
        # own bank, so requiring one (and questions) would fail it for doing its job
        orchestration = boss and m["slug"].endswith("full-loop")
        if orchestration:
            req = [r for r in req if r[0] != "question bank"]
        missing = [name for name, pat in req if not re.search(pat, txt, re.I)]

        # questions appear as `### Qn` headings or, inside a long question bank
        # where headings would blow out the TOC, as bold `**Qn — ...**`. Count
        # both: a 40-question SQL bank formatted the second way is not 3 questions.
        traps  = len(re.findall(r"\*\*Follow-up trap|\*\*Trap", txt))
        qs     = (len(re.findall(r"^###\s*Q\d+", txt, re.M))
                  + len(re.findall(r"^\*\*Q\d+", txt, re.M)))
        # boss rounds may group questions under topic headings instead of
        # numbering them; every question carries a trap, so traps are the floor
        if boss:
            qs = max(qs, traps)
        # count standalone numeric facts (digits with units/percent/complexity)
        # count real numeric facts: strip the sources/changelog boilerplate and the
        # access-date stamps, then count digit groups. Requiring a unit suffix
        # wrongly failed modules whose numbers are versions, RFCs, ports and
        # status codes (OAuth 2.0, RFC 6749, 401, 3NF) - all legitimate facts.
        body   = re.split(r"##\s*Sources", txt)[0]
        body   = re.sub(r"20\d\d-\d\d-\d\d", "", body)
        nums   = len(re.findall(r"(?<![\w-])\d[\d,.]*", body))
        lin3   = len(re.findall(r"\*\*(?:What came before|Where it stands now|Where it.s heading)\.?\*\*", txt))
        srcs   = len(re.findall(r"accessed 20\d\d-\d\d-\d\d", txt))
        words  = len(txt.split())

        fails = []
        if missing:            fails.append("missing:" + ",".join(missing))
        if qs < 10 and not orchestration: fails.append(f"only {qs} questions")
        if traps < qs:         fails.append(f"{traps} traps < {qs} qs")
        # Threshold is a smell test for hand-waving, not a quota. Principles and
# behavioural modules legitimately carry fewer figures than a networking or
# serving module; 20 catches genuinely vague prose without punishing them.
        if nums < 20:          fails.append(f"only {nums} numeric facts")
        if lin3 < 3 and not boss: fails.append(f"lineage has {lin3}/3 parts")
        if srcs < 1:           fails.append("no dated sources")
        if words < 2500:       fails.append(f"thin ({words} words)")

        rows.append((m["id"], words, qs, traps, nums, srcs, fails))
        if fails: hard_fails += 1

print(f"{'module':44} {'words':>6} {'Q':>3} {'trap':>4} {'num':>4} {'src':>4}  status")
print("-" * 96)
for mid, w, q, tr, n, s, f in sorted(rows):
    print(f"{mid:44} {w:6} {q:3} {tr:4} {n:4} {s:4}  {'FAIL: ' + '; '.join(f) if f else 'pass'}")
print("-" * 96)
print(f"{len(rows)} modules reviewed · {len(rows)-hard_fails} pass · {hard_fails} fail")
sys.exit(1 if hard_fails else 0)
