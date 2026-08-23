# The 45-Minute System Design Communication Framework

> Sprint weekend 8 · source: `curriculum/14-behavioral-principal/03-design-communication.md`

```
CLOCK      0-2   restate + declare the plan + ask agreement
           2-5   requirements: scale → 2-3 features → dominant NFR → non-goals
           5-8   estimation, out loud, ending in "so the design problem is ___"
           8-22  high-level BREADTH, ≤9 boxes, end to end, no depth
           22    CHECKPOINT: "two interesting problems; I'd start with X. Your call."
           22-40 DEEP DIVES. 2 done properly > 5 touched. THE SCORE LIVES HERE.
           40-45 close: built / key decision / unfinished / what's next

DEEP DIVE  name problem → constraint → 2-3 options → choose + why →
  SHAPE    cost accepted → one level below → VOLUNTEER the failure mode
           (that last step, unprompted, is the staff signal)

TRADEOFF   "A or B. I'd take A because <property of THIS problem>.
  TEMPLATE  What I'm giving up is C."   ← 8 seconds, use constantly
           Once per deep dive: "the argument for the other side is ___,
           and it wins if ___."

SCALE Q    1 ask what's scaling (users/data/req-per-user)
           2 name the component that breaks FIRST and why
           3 name the SYMPTOM (p99 up, errors flat, queue time up)
           4 fix, then what breaks next.  100x ≠ 10x with bigger numbers

RECOVER    stop · "let me back up, that doesn't work" · SAY WHY IN YOUR
           OWN WORDS · give the fix · name the new cost · move on
           new information → update.  pressure only → hold once, state
           what would change your mind.  second push → take it seriously.

SENIOR     "the cost I'm accepting is ___"
  PHRASES  "the failure mode of what I just described is ___"
           "what breaks first at 10x is ___ and the symptom is ___"
           "you know how X works, so let me go to the interesting part"
           "I don't know. Here's how I'd find out and what I'd assume"
           "I've changed my mind. Here's why."
           "I'd want to measure ___ before committing"

JUNIOR     tech names in the first 30s · "it depends" (full stop)
  TELLS    "we'd just add a cache" · "best practice" · "obviously"
           "what are the requirements?" · "microservices" as an answer
           "X is scalable" · CAP as pick-two-of-three · silence
           orphan nouns (any technology with no "because" attached)

NO         number the components · state direction explicitly ("fans out
WHITEBOARD in parallel to 2 and 3") · name them once, reuse the names
           practise one flagship system verbally, hands behind back

RULE       Every technology you name gets a "because <this problem>"
           in the SAME sentence. No orphan nouns.
```
