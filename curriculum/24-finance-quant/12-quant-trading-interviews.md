# Quant Trading Interviews: Math, Probability, and Mental Math for Jane Street / Citadel / HRT

> **Track:** T24 Financial Engineering, Time Series & Banking · **Time:** 2.5h · **Prereqs:** `T24-derivatives`, `T03-classical-ml` · **Updated:** 2026-11-04
> **Module id:** `T24-quant-trading-interviews` · **Tags:** quant, interview, critical

## The 30-second version

Quant trading interviews (Jane Street, Citadel, HRT, Two Sigma, D.E. Shaw) test a specific skill stack that overlaps with but is distinct from ML engineering: **mental math** (arithmetic speed, probability puzzles), **probability and statistics** (Bayes, conditional probability, expected value, variance), **brainteasers** (game theory, optimal stopping, betting), and **coding** (often in OCaml, C++, or Python with a focus on correctness over cleverness). The math prerequisites: linear algebra (eigenvalues, SVD, matrix calculus), probability (distributions, conditional probability, Bayes), stochastic calculus (Itô, Brownian motion, Black-Scholes derivation), and statistics (hypothesis testing, regression, time series). The 2026 reality: Jane Street's interview process is 3-4 rounds (phone screen with mental math + probability, onsite with brainteasers + coding + market making). Citadel/HRT focus more on systems and low-latency. The key insight: quant interviews test *speed of reasoning*, not depth of knowledge — you need to compute expected values in your head in under 30 seconds.

## Why this gets asked

Because quant trading firms pay 2-5x more than tech companies and have a completely different interview bar. The interviewer's lived failure is a candidate who aces LeetCode but can't compute the expected value of a dice game in 20 seconds. What they probe: (1) mental math speed (can you multiply 17×23 in 3 seconds?), (2) probability intuition (Bayes, conditional probability, expected value), (3) game theory (optimal strategies, Nash equilibrium, betting), (4) coding under pressure (correctness, not cleverness). The principal-level probe: "design a market-making strategy for a new ETF" (answer: estimate fair value, set bid/ask spread, manage inventory risk, handle adverse selection).

## Lineage: past → present → future

**What came before.** Pre-2010s: quant interviews were mostly math olympiad-style (putnam, IMO problems). The pain: these tested mathematical talent, not trading intuition. The shift (2010s-2020s): interviews became more practical — probability puzzles, mental math, game theory, and coding. Jane Street popularized the "brainteaser" format (probability puzzles, optimal stopping, betting games). Citadel/HRT added systems and low-latency components.

**Where it stands now.** The 2026 landscape: (1) Jane Street: 3-4 rounds, phone screen (mental math + probability, 30 min), onsite (brainteasers + coding + market making, 4-5 hours). (2) Citadel: more systems-focused (low-latency, distributed systems, C++). (3) HRT: similar to Citadel, heavy on systems. (4) Two Sigma/D.E. Shaw: more ML-focused. The live disagreement: whether mental math is a good predictor of trading performance (critics say it's hazing; firms say it filters for speed of reasoning under pressure).

**Where it's heading.** High confidence: mental math + probability remain core. Medium confidence: coding rounds become more practical (build a small system, not just LeetCode). Speculative: AI-assisted trading interviews (where candidates use AI tools) become standard, testing judgment over syntax.

## Mental model

```
QUANT TRADING INTERVIEW STACK:

Layer 1: MENTAL MATH (speed)
  ├─ Multiplication/division of 2-digit numbers (< 3 seconds)
  ├─ Fractions/decimals/percentages
  ├─ Expected value of simple games
  └─ Practice: mental math apps, Jane Street's "Probability and Markets" book

Layer 2: PROBABILITY & STATISTICS (intuition)
  ├─ Bayes' theorem (conditional probability)
  ├─ Expected value and variance
  ├─ Common distributions (normal, Poisson, binomial, geometric)
  ├─ Law of total probability
  └─ Central limit theorem (when does it apply?)

Layer 3: BRAINTEASERS (reasoning)
  ├─ Optimal stopping (secretary problem, optimal card drawing)
  ├─ Game theory (Nash equilibrium, zero-sum games, betting)
  ├─ Expected value games (dice, cards, coins)
  └─ Information theory (entropy, mutual information)

Layer 4: CODING (correctness)
  ├─ Implement an algorithm from scratch (no libraries)
  ├─ Handle edge cases (empty input, single element, all same)
  ├─ Time/space complexity analysis
  └─ Often: implement a data structure (heap, trie, union-find)

Layer 5: MARKET MAKING (domain)
  ├─ Estimate fair value of an asset
  ├─ Set bid/ask spread (inventory risk vs. adverse selection)
  ├─ Manage position limits
  └─ Handle information asymmetry
```

## Recognition heuristics

- **"Compute the expected value of rolling two dice"** → E[X] = sum of (value × probability). For two dice: E = 7 (average of 2-12). Variance = 35/12 ≈ 2.92.
- **"What's the probability of at least one heads in 3 coin flips?"** → 1 - P(all tails) = 1 - (1/2)³ = 7/8.
- **"A stock goes up 10% then down 10%. What's the net change?"** → 1.10 × 0.90 = 0.99 → down 1%. (Common trap: not 0%.)
- **"Optimal stopping: when do you stop drawing cards?"** → Secretary problem: optimal stop at n/e ≈ 37% of the way through, then pick the next best. For 100 cards, stop after 37, then pick the next card better than all seen.

## Common bugs and how these get shipped wrong

- **Slow mental math.** Practice until 2-digit multiplication takes < 3 seconds. Use the "break apart" method: 17×23 = 17×20 + 17×3 = 340 + 51 = 391.
- **Confusing conditional probability.** P(A|B) ≠ P(B|A). Bayes' theorem: P(A|B) = P(B|A)·P(A)/P(B). The "base rate fallacy" is the #1 trap.
- **Ignoring variance.** Expected value alone doesn't tell you the risk. A game with E=$10 and variance=$1000 is very different from E=$10 and variance=$1.
- **Overcomplicating brainteasers.** Most have a simple insight. State the obvious first, then build. Don't jump to complex formulas.
- **Not asking clarifying questions.** "What's the expected value?" → "Of what? Over how many trials? With replacement or without?" Clarify before computing.

## Interview questions

1. **"A fair coin is flipped until the first heads. What's the expected number of flips?"** Answer: geometric distribution with p=1/2. E = 1/p = 2.
2. **"You have 3 boxes: one has 2 gold coins, one has 2 silver, one has 1 gold + 1 silver. You pick a box at random and draw a gold coin. What's the probability the other coin in that box is gold?"** Answer: Bayes. P(gold box | drew gold) = P(drew gold | gold box)·P(gold box) / P(drew gold) = (1 × 1/3) / (1/3 × 1 + 1/3 × 0 + 1/3 × 1/2) = (1/3)/(1/2) = 2/3.
3. **"Design a market-making strategy for a new ETF."** Answer: (1) Estimate fair value (NAV, underlying basket). (2) Set bid/ask spread (wider for illiquid, narrower for liquid). (3) Manage inventory risk (skew quotes based on position). (4) Handle adverse selection (widen spread when informed flow detected). (5) Monitor P&L, hit rate, inventory turnover.

## Red flags that fail you

- "I'm not good at mental math" — practice until you are. It's a learnable skill.
- Confusing P(A|B) with P(B|A) — the base rate fallacy.
- Not asking clarifying questions before computing.
- Overcomplicating simple problems (most brainteasers have a simple insight).
- Not knowing basic distributions (normal, Poisson, binomial, geometric, exponential).

## Cheat card

- Mental math: break apart (17×23 = 17×20 + 17×3 = 391). Practice daily.
- Bayes: P(A|B) = P(B|A)·P(A)/P(B). Always check the base rate.
- Expected value: E[X] = Σ x·P(x). Variance: Var(X) = E[X²] - E[X]².
- Common distributions: Normal (bell curve), Poisson (rare events), Binomial (n trials), Geometric (first success), Exponential (waiting time).
- Optimal stopping: secretary problem → stop at n/e ≈ 37%, then pick next best.
- Game theory: zero-sum (minimax), Nash equilibrium (no player can improve unilaterally).
- Market making: fair value ± spread, inventory skew, adverse selection.

## Sources

- [Jane Street — Probability and Markets (book)](https://www.janestreet.com/) — accessed 2026-11-04
- [Heard on the Street: Quantitative Questions from Wall Street Job Interviews (Crack)](https://www.crack.com/) — accessed 2026-11-04
- [Quantitative Finance (Yves Hilpisch)](https://www.oreilly.com/library/view/python-for-finance/9781492024323/) — accessed 2026-11-04

## Changelog

- 2026-11-04: Created — Quant trading interviews identified as a gap (no dedicated module for Jane Street/Citadel/HRT interview prep).
