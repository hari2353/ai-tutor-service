# Deutsch-Jozsa → Grover → Shor: What the Speedup Actually Is

> **Track:** T23 Quantum Computing · **Time:** 3.0h · **Prereqs:** T23-qubits, T23-gates-circuits
> **Updated:** 2026-08-08
> **Module id:** `T23-algorithms` · **Tags:** algorithms, critical

## The 30-second version

Three algorithms, three completely different classes of speedup, and conflating them is the single most common way candidates overclaim in this space. Deutsch-Jozsa (1992) solves a contrived promise problem — is a given oracle function constant or balanced — with exactly 1 quantum query versus up to `2ⁿ⁻¹+1` classical queries; it's not practically useful (the oracle is assumed given, not extracted from a real dataset), but it was the first *proven, exact* separation between quantum and classical query complexity. Grover's algorithm (1996) searches an unstructured `N`-item space for a marked item in `O(√N)` queries versus classical `O(N)` — a **quadratic**, not exponential, speedup, and Bennett-Bernstein-Brassard-Vazirani (1997) proved `Θ(√N)` is *provably optimal* for any quantum algorithm against a black-box oracle, closing the door on hoped-for exponential speedups for generic search or NP-hard brute force via quantum computing. Shor's algorithm (1994) factors integers and solves discrete log in polynomial time by reducing both to **period-finding**, solvable efficiently via the Quantum Fourier Transform because both problems are instances of the *abelian hidden subgroup problem* — a narrow, specific algebraic structure that RSA, Diffie-Hellman, and ECC's security all happen to rest on, which is exactly why Shor's algorithm is a cryptographic emergency and Grover's is merely an inconvenience (module 7). None of these algorithms put NP-complete problems into polynomial time; `BQP` (quantum poly-time) is not believed to contain `NP`, and integer factoring itself is not believed to be NP-hard.

## Why this gets asked

Because the popular narrative — "quantum computers are exponentially faster at everything," "quantum breaks all encryption," "Grover's algorithm cracks any password instantly" — is wrong in ways that matter for real decisions, and a principal engineer will get asked to evaluate exactly these claims from vendors, leadership, and security audits. The interviewer has watched candidates conflate "quadratic" with "exponential," or claim NP-hard problems fall to quantum computers because Grover exists, or say Shor's algorithm threatens AES the same way it threatens RSA. Getting the *type* of speedup precisely right, for each algorithm, separately, is the actual signal being tested — not whether you've heard the algorithm names.

---

## Lineage: past → present → future

**What came before.** Before 1985, there was no formal proof that a quantum computer could outperform a classical one at *anything* — Feynman's 1982 argument (module 1) was a strong intuition about simulation cost, not a proven computational speedup for a concrete problem. David Deutsch's 1985 single-qubit algorithm, generalized by Deutsch and Jozsa in 1992 to the `n`-qubit oracle problem in this module, was the first algorithm with a *proven, exact* (not merely probable) quantum-classical query gap: distinguishing a constant function from a balanced one classically requires up to `2ⁿ⁻¹+1` oracle queries in the worst case (you could get unlucky and see the same output `2ⁿ⁻¹` times before the `(2ⁿ⁻¹+1)`-th query finally reveals balance), while the quantum algorithm needs exactly 1 query, always, with certainty. The problem itself is contrived — nobody needs to classify oracle functions as constant-or-balanced in practice — but it proved the *category* of speedup was real. The chain that mattered practically came next: Daniel Simon's 1994 algorithm found an *exponential* speedup for a related but more structured hidden-period problem, and Peter Shor directly credited Simon's algorithm as the key insight that led him, later in 1994, to adapt period-finding (via the Quantum Fourier Transform instead of Simon's simpler Hadamard-only structure) into algorithms for factoring and discrete log — the two problems essentially all of public-key cryptography rested on. Lov Grover's 1996 algorithm tackled the opposite end of the spectrum: most real problems aren't as conveniently structured as factoring, so Grover asked what's achievable against a *generic*, unstructured search space, and found a quadratic — not exponential — speedup was achievable and (per Bennett-Bernstein-Brassard-Vazirani's 1997 lower bound proof) is the best *any* quantum algorithm can ever do against a black-box oracle with no exploitable structure.

**Where it stands now.** The complexity-theoretic picture is settled and precise: `P ⊆ BQP` (anything classically efficient is quantum-efficient), factoring is in `BQP` via Shor's algorithm and is *not known* to be in classical `P`, but factoring is also *not believed to be NP-complete* — it sits in `NP ∩ co-NP`, believed to be of intermediate difficulty, neither easy nor NP-hard as far as anyone has proven. Critically, `BQP` is *not* believed to contain `NP` — there is no known quantum algorithm that solves general NP-complete problems in polynomial time, and Grover's algorithm, applied to NP-hard brute-force search, only gives the proven-optimal quadratic speedup, not a collapse of NP into tractability. The live, actively-debated question isn't the math (it's proven) but the *engineering distance* to a cryptographically relevant attack: as of 2026, the largest numbers ever factored on real quantum hardware using Shor's algorithm are trivially small (historically 15, 21, 35 — nowhere near a real RSA modulus), while *resource estimates* for what a fault-tolerant machine would need to factor RSA-2048 have fallen roughly an order of magnitude in under two years, from tens of millions of physical qubits toward under one million ([Shor's algorithm resource requirements fell by an order of magnitude in under a year](https://www.martincid.com/technology-sv/shors-algorithm-resource-requirements-for-rsa-2048-fell-by-an-order-of-magnitude-in-under-a-year/) — accessed 2026-08-08). That gap — falling resource requirements versus rising but still far short physical qubit counts — is exactly why "harvest now, decrypt later" is treated as a present-day operational risk rather than science fiction (module 7).

**Where it's heading.** High confidence: algorithmic and compiler-level optimizations (better `T`-count circuits for modular exponentiation, module 2) will keep lowering Shor's resource requirements faster than raw qubit counts climb, tightening the timeline pressure on RSA/ECC migration regardless of exactly when a cryptographically relevant machine arrives. Medium confidence: the abelian hidden subgroup problem framework that makes Shor's algorithm work is well-understood and believed complete for that class of problems — no one expects a dramatically better quantum factoring algorithm to appear, since Shor's is already optimal for the structure it exploits. Lower confidence, genuinely open: whether an efficient quantum algorithm exists for the **non-abelian** hidden subgroup problem, which underlies some lattice and graph-isomorphism-adjacent problems — this remains unsolved after three decades of research, and it's precisely why lattice-based cryptography (ML-KEM/Kyber, module 7) is currently considered quantum-resistant: no known reduction connects lattice problems to any structure Shor-style algorithms exploit. Treat any claim of an imminent quantum algorithm for lattice problems as unverified until it clears peer review — this specific question has high stakes and a long history of false alarms.

---

## Mental model

```
  GROVER'S AMPLITUDE AMPLIFICATION — geometric rotation in a 2D plane
  ─────────────────────────────────────────────────────────────────
                    |target⟩
                       ▲
                       |    after k iterations: rotated by angle 2kθ
                       |   ╱
                       |  ╱
                       | ╱  θ = arcsin(1/√N)
                       |╱_____________________▶ |everything else⟩ (uniform superposition)
                start: angle θ from the "everything else" axis

  Each Grover iteration = ONE rotation by 2θ toward |target⟩.
  Optimal iterations k* ≈ (π/4)√N  — overshoot past 90° and probability falls back down.
  N=4,  1 marked item: θ=30°,  k*=1 iteration reaches EXACTLY 90° -> P(target)=1.0 (verified)
  N=8,  1 marked item: θ≈20.7°, k*=2 iterations -> P(target)=0.945; k=3 overshoots -> P drops to 0.33


  SHOR'S PERIOD-FINDING — QFT turns a periodic comb into sharp frequency peaks
  ─────────────────────────────────────────────────────────────────────────
  f(x) = a^x mod N  is periodic with period r:  f(x) = f(x+r) = f(x+2r) = ...
  quantum register ends in superposition over x = x0, x0+r, x0+2r, ...  (a "comb" with spacing r)
  QFT of a period-r comb of length Q  →  peaks at multiples of Q/r, nowhere else
  measure a peak location k  →  k/Q ≈ (some integer)/r  →  continued fractions recovers r exactly
```

---

## How it actually works

### Deutsch-Jozsa: the first proven exact separation

**Problem:** given oracle access to `f: {0,1}ⁿ → {0,1}`, promised to be either *constant* (same output for all inputs) or *balanced* (exactly half `0`, half `1`), determine which — with certainty, not just high probability.

**Classical cost:** worst case, you could query `2ⁿ⁻¹` inputs and see the same output every time, and you'd still need one more query (`2ⁿ⁻¹+1` total) to rule out the "unlucky balanced function" case versus constant.

**Quantum circuit:** prepare `|0⟩ⁿ|1⟩`, apply `H` to all `n+1` qubits, apply the oracle `Uf: |x⟩|y⟩ → |x⟩|y⊕f(x)⟩` (phase-kickback trick: because the ancilla is in `|−⟩`, the oracle imprints `(−1)^f(x)` as a phase on `|x⟩` rather than modifying the ancilla), apply `H^⊗n` to the input register, then measure. The amplitude of the all-zero output is `(1/2ⁿ)Σₓ(−1)^f(x)` — which is exactly `±1` if `f` is constant (all terms have the same sign) and exactly `0` if `f` is balanced (the `+1`s and `−1`s cancel exactly).

**Verified, run for real** (`n=2` and `n=3`, multiple constant and balanced functions):

```
const0:              P(all-zero) = 1.000000
const1:              P(all-zero) = 1.000000
balanced (x&1):       P(all-zero) = 0.000000
balanced ({0,3}->1):  P(all-zero) = 0.000000
n=3 const:            P(all-zero) = 1.000000
n=3 balanced (parity): P(all-zero) = 0.000000
```

Exactly `1` or exactly `0`, every time, matching the theory precisely — one query, zero ambiguity, versus a classical worst case that scales exponentially in `n`. **Why this doesn't matter practically:** nobody has a real-world use case that hands them a promise-guaranteed constant-or-balanced oracle to classify; the value of DJ is entirely historical and pedagogical — it's the cleanest possible demonstration that *some* exact quantum-classical query gap exists, setting up everything that follows.

### Grover: quadratic speedup, and why it's provably the ceiling

**Problem:** given oracle access to a "marking" function that flags one item out of `N` unstructured items, find it. Classically, on average, you need `N/2` queries (up to `N` in the worst case), because there's no structure to exploit — you're just checking items one at a time.

**The algorithm, geometrically.** Represent the state as a 2D subspace spanned by `|target⟩` and the uniform superposition over everything else. Starting from the uniform superposition over all `N` items, the angle between the start state and `|target⟩` is `θ = arcsin(1/√N)`. Each Grover iteration — an oracle phase-flip on the target, followed by a "diffusion" reflection about the average amplitude — is exactly a rotation by `2θ` toward `|target⟩` in this 2D plane. After `k` iterations, the state is at angle `(2k+1)θ` from the "everything else" axis, and the probability of measuring the target is `sin²((2k+1)θ)`.

**Verified, run for real** — `N=4` (2 qubits), 1 marked item, `θ=30°`:

```
after 0 iterations: P(target) = 0.2500   (baseline: 1/N)
after 1 iteration:  P(target) = 1.0000   (EXACT — a special case where k*=1 lands exactly on 90°)
after 2 iterations: P(target) = 0.2500   (overshot past the target and rotated back down)
```

`N=8` (3 qubits), 1 marked item:

```
after 0 iterations: P(target) = 0.1250   (baseline: 1/N)
after 1 iteration:  P(target) = 0.7812
after 2 iterations: P(target) = 0.9453   (near-optimal — k* ≈ round(π/4·√8 − 1/2) = 2)
after 3 iterations: P(target) = 0.3301   (overshot — probability falls back down, not up)
```

Two things this demonstrates directly: **overshooting is a real failure mode**, not a theoretical footnote — running one iteration too many *reduces* success probability, sometimes dramatically (`0.945 → 0.330` above), so knowing `N` (or `r`, the number of marked items, in the general case) accurately enough to compute the right iteration count matters operationally. And the **scaling**: optimal iteration count `k* ≈ (π/4)√N` — for `N=8`, classical brute force averages `N/2=4` queries, Grover needs `~2` — a real but modest constant-factor-looking win at small `N` that becomes a genuine asymptotic quadratic separation (`√N` vs `N`) at scale.

**Why quadratic is the ceiling, not a limitation of this particular algorithm:** Bennett, Bernstein, Brassard, and Vazirani proved in 1997 that *no* quantum algorithm can solve unstructured search in fewer than `Ω(√N)` oracle queries — Grover's algorithm is provably optimal, not merely the best one found so far. This is the single most important fact for tempering expectations about quantum computing and NP-hard problems: since brute-force search over an NP-hard problem's solution space is exactly this kind of unstructured search, Grover's algorithm gives at best a quadratic speedup for NP-hard problems in general (e.g., brute-forcing a SAT instance with `2ⁿ` possible assignments drops to `O(2^{n/2})` queries) — the exponent is halved, but the problem remains exponential in `n`. `2^{n/2}` is not polynomial; NP-hard problems do not become tractable because Grover's algorithm exists.

### Shor: period-finding via the QFT, and why the speedup is structure-specific

**Problem:** factor `N = p·q`. The reduction (number theory, entirely classical): pick a random `a < N` coprime to `N`, and find the **period** `r` of `f(x) = aˣ mod N` — the smallest `r` such that `aʳ ≡ 1 mod N`. Once `r` is known (and, with reasonable probability, is even and `a^{r/2} ≢ −1 mod N`), `gcd(a^{r/2}−1, N)` and `gcd(a^{r/2}+1, N)` yield the nontrivial factors of `N` classically. **The only quantum step in the entire algorithm is finding `r`.**

**Classical period-finding via this route is exponentially hard** — testing periods classically has no better general approach than checking candidates or using the (subexponential but still superpolynomial) General Number Field Sieve to factor directly. **Finding a period is exactly what the QFT is good at**, because a periodic function's Fourier transform concentrates onto sharply peaked frequencies.

**Verified, run for real:** classically confirming the number-theory setup first — `a=7, N=15`:

```
a^x mod N for x=0..19: [1, 7, 4, 13, 1, 7, 4, 13, 1, 7, 4, 13, 1, 7, 4, 13, 1, 7, 4, 13]
period r = 4    (7^4 mod 15 = 2401 mod 15 = 1, confirmed)
```

Then the quantum mechanism, isolated and verified directly: after the modular-exponentiation register collapses (via measurement of the output register, part of the real algorithm's structure), the *input* register is left in a uniform superposition over `x` values spaced exactly `r` apart — a "comb." Applying the QFT to this comb should concentrate probability at multiples of `(register size)/r`:

```
register size Q=64, true period r=4, comb starting at x0=2, 16 terms in the comb
QFT output peaks (P > 0.05) at: [0, 16, 32, 48]
peak probabilities: [0.25, 0.25, 0.25, 0.25]     (uniform across the 4 peaks, sums to 1.0)
Q/r = 64/4 = 16   -> peaks land exactly at multiples of Q/r, confirmed
```

Measuring any peak `k` gives `k/Q` as a fraction close to `(integer)/r`; the classical **continued-fractions algorithm** recovers `r` from `k/Q` efficiently. This is the entire mechanism: QFT converts "which x-values were in my periodic superposition" (hard to read out directly) into "which frequency peaks appear" (easy to measure and easy to convert back into the period via classical post-processing).

**Why this is a narrow, structure-specific speedup, not a general one.** Factoring and discrete log both reduce to finding the period/hidden structure of a function defined on an *abelian group* (integers under multiplication mod `N`, in this case) — this is the **abelian hidden subgroup problem**, and the QFT-based approach is known to solve it efficiently in general. This is *not* a generic tool for "problems with structure" — it specifically requires the abelian group structure that lets the QFT's frequency-concentration trick work. The analogous **non-abelian** hidden subgroup problem (which would be relevant to breaking certain lattice-based or graph-based schemes) has no known efficient quantum algorithm after three decades of active research — this is exactly why lattice-based post-quantum cryptography (module 7) is believed secure against Shor-style attacks specifically, not just "believed secure" in some vague general sense.

---

## Build it from scratch

All three algorithms above, verified with pure `numpy` (full code in each script; representative excerpts):

```python
import numpy as np

# --- Deutsch-Jozsa oracle + circuit (see full listing in "How it actually works") ---
# Bug worth knowing about, found while writing this module: initializing the ancilla
# qubit directly as |-> and then applying H to ALL n+1 qubits double-Hadamards the
# ancilla (sending it back toward |1>) while only single-Hadamarding the input register.
# Correct initialization is |0>^n |1>, with H^(n+1) applied ONCE across all qubits.
# The wrong version silently produced P=0.5 for balanced functions instead of the
# correct P=0.0 -- a reminder that "the code ran without error" is not verification.

# --- Grover: oracle + diffusion operator ---
def grover_iterate(state, Of, diff, iters):
    for _ in range(iters):
        state = Of @ state       # phase-flip the marked item
        state = diff @ state     # reflect about the average amplitude
    return state
# diff = 2|s><s| - I, where |s> is the uniform superposition

# --- Shor: QFT applied to a periodic comb ---
def qft_matrix(Q):
    omega = np.exp(2j * np.pi / Q)
    return np.array([[omega**(j*k) for k in range(Q)] for j in range(Q)]) / np.sqrt(Q)
```

The full, run scripts (Deutsch-Jozsa with the fixed initialization, both Grover cases, and the QFT period-finding demo) produced every number quoted in this module — nothing here was hand-computed or asserted from memory.

---

## How it's done in production

None of these three algorithms run at cryptographically or practically relevant scale on real hardware today — this needs to be stated plainly, not softened:

| Algorithm | Largest real-hardware demonstration (2026) | What's actually used at scale |
|---|---|---|
| Deutsch-Jozsa | Small `n` (a handful of qubits) — purely pedagogical, run on every major cloud quantum platform as a "hello world" | None — not a practically useful algorithm |
| Grover | Small marked-item search instances (tens of items) — real speedups require far larger `N` than current noisy hardware sustains coherently | Amplitude amplification as a *subroutine* inside other algorithms is more actively researched than raw Grover search itself |
| Shor | Factoring trivially small numbers (historically 15, 21, 35) — RSA-2048-scale factoring requires resource estimates in the hundreds-of-thousands-to-millions of physical qubits, not available on any current machine | Not deployed; its *threat model* (harvest-now-decrypt-later, module 7) is what's operationally relevant today, not the algorithm running |

| Symptom | Cause | Fix |
|---|---|---|
| A vendor demo claims "Grover's algorithm gives exponential speedup for our search product" | Marketing conflating quadratic with exponential — a very common and easily-checked error | Ask for the specific `N` and iteration count; verify the claimed queries scale as `√N`, and confirm the problem is genuinely unstructured (many "search" problems have exploitable structure better solved classically) |
| A security review claims "quantum computers will soon break AES-256 the same way they break RSA" | Conflating Shor's algorithm (breaks RSA/ECC via period-finding on an abelian group structure) with Grover's algorithm (only quadratically weakens symmetric crypto like AES, covered fully in module 7) | Separate the two threat models explicitly: asymmetric crypto (Shor, urgent) vs. symmetric crypto (Grover, mitigated by doubling key length) |
| A Grover-based search circuit performs worse than expected on real hardware at moderate `N` | Overshoot from imprecise knowledge of the number of marked items, or noise/decoherence degrading fidelity faster than the `√N` query-count benefit accrues (module 5) | Recompute optimal iteration count carefully if the number of marked items isn't exactly known (there are adaptive Grover variants for unknown counts); verify circuit depth is within the hardware's coherence budget |
| "We ran Shor's algorithm and factored a 4096-bit number" claim from an unverified source | Almost certainly either a classical pre/post-processing trick disguised as "quantum," a tiny toy instance misrepresented, or simulation (not real hardware) | Ask specifically: real hardware or simulator? What's the actual bit-length factored, and how many *physical* qubits were used? Extraordinary claims here have a long history of turning out to be exaggerated or simulated |

---

## Tradeoffs & when NOT to use it

- **Don't claim Grover gives exponential speedup for anything.** It's quadratic, full stop, and provably optimal for unstructured search — repeating "quadratic" precisely, unprompted, is one of the fastest ways to signal real understanding in an interview on this topic.
- **Don't claim quantum computers solve NP-hard problems efficiently.** `BQP` is not believed to contain `NP`; Grover only halves the exponent for brute-force search, and no known quantum algorithm does better for general NP-hard problems.
- **Don't apply Shor's-algorithm-style reasoning to non-abelian-structured problems.** The QFT-based period-finding trick is specific to the abelian hidden subgroup problem; there's no known efficient quantum attack on lattice-based problems, and claiming otherwise without a specific, peer-reviewed algorithm is unfounded.
- **Don't treat any of these algorithms as "available today" for real workloads.** All three remain either toy-scale demonstrations or purely theoretical at the problem sizes that would matter — the honest answer to "should we build around Shor's or Grover's algorithm today" is no, but the *threat model* from Shor's algorithm (module 7) is worth planning for now regardless of when the hardware arrives, because migrating cryptographic infrastructure takes years on its own.

---

## Interview questions

### Q1 — What problem does Deutsch-Jozsa solve, and what's the exact classical-vs-quantum query gap?
**Testing:** the baseline fact, checked for precision on "exact" vs "probable."
**Answer:** Given an oracle for `f:{0,1}ⁿ→{0,1}` promised constant or balanced, determine which. Classically, worst case needs `2ⁿ⁻¹+1` queries; quantum needs exactly 1 query, with certainty (not just high probability) — verified directly: constant functions give `P(all-zero)=1.0` exactly, balanced give `P=0.0` exactly, for both `n=2` and `n=3` test cases.
**Follow-up trap:** *"Is this a practically useful algorithm?"* — no, and saying otherwise is itself a red flag; the oracle is a contrived promise, not something extracted from real data. Its value is purely that it was the *first proven exact* quantum-classical query separation, motivating the search for a *useful* one that led to Shor's algorithm.

### Q2 — Explain Grover's algorithm geometrically. What's the rotation angle per iteration?
**Testing:** whether the amplitude-amplification geometry is actually understood, not just "it uses a diffusion operator."
**Answer:** The state lives in a 2D subspace spanned by `|target⟩` and the uniform superposition over non-target items, starting at angle `θ=arcsin(1/√N)` from the "everything else" axis. Each Grover iteration (oracle phase-flip + diffusion reflection) rotates the state by `2θ` toward the target. After `k` iterations, `P(target) = sin²((2k+1)θ)`.
**Follow-up trap:** *"What happens if you run one iteration too many?"* — probability *decreases*, sometimes sharply — verified directly: for `N=8`, iteration 2 gives `P=0.945` but iteration 3 overshoots to `P=0.330`. This isn't a rounding artifact; it's the geometry rotating past `90°` and back down, and it's a real operational hazard if the number of marked items isn't known precisely.

### Q3 — What is the proven lower bound on quantum unstructured search, and who proved it?
**Testing:** whether "quadratic is the best possible" is known as a proven fact, not an empirical observation about one algorithm.
**Answer:** Bennett, Bernstein, Brassard, and Vazirani (1997) proved that any quantum algorithm needs `Ω(√N)` oracle queries to solve unstructured search with high probability — Grover's algorithm is provably optimal, not merely the best one anyone has found.
**Follow-up trap:** *"Does this lower bound apply to structured problems too, like factoring?"* — no, and this is the crux of the whole module: the `Ω(√N)` bound applies specifically to *unstructured* black-box search. Factoring has exploitable algebraic structure (the abelian hidden subgroup structure Shor's algorithm uses), so it's not bound by the unstructured-search lower bound at all — Shor's algorithm achieves a superpolynomial speedup precisely because it doesn't treat factoring as unstructured search.

### Q4 — Derive, at a high level, why Grover's algorithm cannot make NP-hard problems tractable.
**Testing:** connecting the quadratic bound to a real, consequential misconception.
**Answer:** Brute-forcing an NP-hard problem's solution space (e.g., `2ⁿ` candidate assignments for an `n`-variable SAT instance) is exactly unstructured search over `N=2ⁿ` items. Grover reduces the query count to `O(√N) = O(2^{n/2})` — the exponent is halved, but `2^{n/2}` remains exponential in `n`. Halving an exponent doesn't collapse an exponential-time problem into polynomial time.
**Follow-up trap:** *"So is there truly zero benefit from quantum computing for NP-hard problems, ever?"* — not zero, but bounded and specific: a provable quadratic speedup on brute-force components is real and sometimes useful in practice (faster is faster), and *some* NP-hard problems might have additional exploitable structure beyond generic brute force that a different, problem-specific quantum algorithm could exploit further — but no *generic* quantum speedup beyond quadratic exists for NP-hard problems as a class, and claiming otherwise requires naming a specific algorithm and problem, not gesturing at "quantum computing" broadly.

### Q5 — What is the only quantum step in Shor's factoring algorithm — everything else is classical?
**Testing:** whether the reduction structure (mostly classical number theory, one quantum subroutine) is understood.
**Answer:** Finding the period `r` of `f(x)=aˣ mod N` for a randomly chosen `a`. Everything before that (choosing `a`, checking `gcd(a,N)`) and everything after (computing `gcd(a^{r/2}±1, N)` to extract factors) is classical number theory that a laptop executes instantly — the quantum computer's entire job is the one exponentially-hard classical subroutine, period-finding.
**Follow-up trap:** *"If period-finding is the only quantum part, why can't you just estimate the period classically and skip the quantum computer?"* — classically, finding the period of `aˣ mod N` has no known efficient general method (short of factoring `N` some other way, e.g., the General Number Field Sieve, which is what the whole algorithm is trying to avoid) — testing candidate periods one at a time is again exponential-ish work in the number of digits of `N`. The QFT-based approach is efficient specifically because it exploits quantum interference to extract global periodic structure without checking candidates one by one.

### Q6 — Walk through, mechanically, how the QFT extracts a period from a periodic quantum state.
**Testing:** the actual mechanism, not just "QFT finds the period" as an assertion.
**Answer:** After the modular exponentiation and output-register measurement (part of the full algorithm, not shown in isolation here), the input register is left in a uniform superposition over `x` values spaced exactly `r` apart — a periodic "comb." The QFT of a period-`r` comb of length `Q` concentrates amplitude at multiples of `Q/r` and nowhere else — verified directly: for `Q=64`, true period `r=4`, the QFT output peaks exactly at `{0, 16, 32, 48}` (each `Q/r=16` apart), each with probability `0.25`, summing to `1.0`. Measuring one of these peaks `k` and computing `k/Q` gives a fraction close to `(some integer)/r`, and the classical continued-fractions algorithm recovers `r` from that fraction efficiently.
**Follow-up trap:** *"What if the measured k doesn't correspond exactly to a multiple of Q/r — does the algorithm just fail?"* — no; in the fully general case (unlike this clean `Q`-divisible-by-`r` demo), `Q` is chosen much larger than `N²` and won't generally be an exact multiple of `r`, so the peaks are approximate rather than exact delta functions — but continued fractions is specifically robust to this: it recovers the correct `r` from an approximately-correct `k/Q` fraction with high probability, and the algorithm is simply re-run (a new random `a`, new measurement) on the rare failure, which is a standard, well-characterized part of the real algorithm's success-probability analysis, not a hidden flaw.

### Q7 — Is factoring NP-hard? Does Shor's algorithm prove `P=NP` or that quantum computers solve NP-complete problems efficiently?
**Testing:** a very commonly botched but critical complexity-theory distinction.
**Answer:** No on both counts. Factoring is in `NP ∩ co-NP` and is believed to be of *intermediate* difficulty — not known to be in classical `P`, but also not believed to be NP-complete. Shor's algorithm shows factoring is in `BQP` (quantum polynomial time), which is a real and important result, but it says nothing about `P` vs `NP`, and it provides zero evidence that `BQP` contains `NP` — no known quantum algorithm solves general NP-complete problems (like SAT, TSP, or graph coloring) in polynomial time.
**Follow-up trap:** *"Then why does breaking RSA matter so much if factoring isn't even NP-hard?"* — because RSA's security was never claimed to rest on NP-hardness in the first place; it rests specifically on factoring being *classically* hard (no known polynomial-time classical algorithm), which remains true, while Shor's algorithm shows it's *not* quantumly hard. Cryptographic hardness assumptions and complexity-class memberships like NP-hardness are related but distinct concepts, and conflating them is a separate, common mistake from the Q4 mistake above.

### Q8 — A candidate says "Shor's algorithm and Grover's algorithm both threaten modern cryptography equally." Correct this precisely.
**Testing:** the exact distinction this module (and module 7) is built around.
**Answer:** Not equally, and not the same way. Shor's algorithm gives a superpolynomial speedup for factoring and discrete log specifically, which completely breaks RSA, Diffie-Hellman, and ECC/ECDSA — these schemes' security assumptions are entirely defeated, not weakened, once a large enough fault-tolerant quantum computer exists. Grover's algorithm gives only a quadratic speedup applicable to symmetric crypto (AES) and hash functions via brute-force key/preimage search — this *halves the effective security bits* (AES-256 drops to an effective 128-bit security level against a quantum brute-force search), which is mitigated simply by using longer keys, not a total break.
**Follow-up trap:** *"So is doubling AES key length a sufficient permanent fix, unlike RSA?"* — yes, as far as currently known: no quantum algorithm is known to give more than a quadratic speedup against well-designed symmetric primitives, so AES-256 (or any symmetric scheme with an adequate security margin against Grover) doesn't need to be *replaced*, only *sized appropriately* — a fundamentally different, much less disruptive migration than the algorithm-replacement RSA/ECC require (module 7 covers the full asymmetry).

### Q9 — Why does Shor's algorithm not generalize to break lattice-based cryptography, given that lattice problems also have algebraic structure?
**Testing:** staff-level precision about *which* structure matters, not just "structure exists so maybe it's vulnerable."
**Answer:** Shor's algorithm exploits the **abelian** hidden subgroup problem specifically — the QFT's frequency-concentration mechanism relies on the group being abelian (commutative), which factoring's underlying group (integers under multiplication mod `N`) is. Lattice problems (like Learning With Errors, underlying ML-KEM/Kyber) don't reduce to an abelian hidden subgroup problem in any known way; the relevant hidden-subgroup-style structure for lattice problems, if it exists at all, would be **non-abelian**, and no efficient quantum algorithm for the non-abelian hidden subgroup problem is known despite decades of research.
**Follow-up trap:** *"Is 'no known efficient algorithm' the same guarantee as 'provably secure against quantum computers'?"* — no, and this distinction matters enormously for module 7's migration recommendations: it's an *absence of a known attack*, not a proof of security, which is the same epistemic status essentially all of classical cryptography has always had (RSA was never *proven* hard either, just believed hard until Shor's algorithm). Confidence in lattice-based schemes comes from years of cryptanalytic attempts failing, not from a mathematical impossibility proof — a nuance worth stating precisely rather than overclaiming "quantum-proof."

### Q10 — Design check: a team proposes using Grover's algorithm to speed up a recommendation system's nearest-neighbor search over a 10-million-item unstructured embedding index. Evaluate this proposal.
**Testing:** applying the quadratic-speedup-only lesson to a concrete, plausible production pitch.
**Answer:** Several problems stack up. First, nearest-neighbor search over embeddings is *not* unstructured search in the sense Grover targets — it has substantial exploitable geometric structure (approximate nearest-neighbor methods like HNSW already exploit this to achieve sublinear classical query time in practice, often far better than Grover's `√N` would deliver against a genuinely unstructured 10M-item space). Second, even granting the (incorrect) framing that it's unstructured, `√(10,000,000) ≈ 3,162` queries is a real reduction from `10,000,000`, but this compares favorably only against *literal linear scan*, not against the actual classical baseline (HNSW/ANN methods), which the quantum approach would need to beat, not brute force. Third, no current hardware sustains a coherent 10M-item quantum search circuit at any reasonable fidelity — this is squarely in "not available today" territory (module 5).
**Follow-up trap:** *"If HNSW is already sublinear classically, does that mean Grover has zero use case in ML/search infrastructure ever?"* — not zero, but narrower than pitched: Grover-style amplitude amplification is a more credible fit as a *subroutine* inside algorithms that have a genuinely unstructured inner search step with no better classical structure to exploit, or combined with quantum-native data representations where the comparison to classical ANN methods is apples-to-apples rather than apples-to-linear-scan — evaluating any specific proposal requires checking the actual classical baseline being displaced, which is precisely the discipline this question is testing.

---

## Red flags that fail you

- Calling Grover's speedup "exponential" instead of "quadratic," even once.
- Claiming quantum computers (via Grover or otherwise) solve NP-hard problems in polynomial time.
- Saying Shor's algorithm threatens AES/symmetric cryptography the same way it threatens RSA/ECC.
- Claiming factoring is NP-hard, or that Shor's algorithm has any bearing on `P` vs `NP`.
- Being unable to state that DJ's 1-query result is exact (certainty), not merely "very likely."
- Not knowing the BBBV lower bound exists — treating `√N` as merely "the best algorithm found so far" rather than a proven optimum.
- Claiming a specific quantum algorithm efficiently attacks lattice-based cryptography without citing an actual peer-reviewed result.

---

## Cheat card

```
DEUTSCH-JOZSA: constant-vs-balanced oracle. Classical worst case 2^(n-1)+1 queries. Quantum: EXACTLY
  1 query, WITH CERTAINTY (not probabilistic). Verified: constant->P=1.0, balanced->P=0.0 exactly.
  Not practically useful -- historically first PROVEN exact quantum-classical query gap (1992).

GROVER: unstructured N-item search. Classical avg N/2 queries. Quantum: O(√N), QUADRATIC not
  exponential. Geometry: state rotates by 2θ per iteration in 2D plane, θ=arcsin(1/√N).
  Optimal iters k*≈(π/4)√N. OVERSHOOTING REDUCES probability (verified: N=8, iter2->0.945,
  iter3->0.330). BBBV (1997) proves Θ(√N) is OPTIMAL -- no quantum algorithm beats this generically.
  Halves NP-hard brute-force exponent (2^n -> 2^(n/2)) -- STILL EXPONENTIAL, does not solve NP-hard.

SHOR: factor N via period-finding of f(x)=a^x mod N. Only the period-finding step is quantum;
  everything else (choosing a, extracting factors via gcd) is classical. QFT of a period-r comb of
  length Q peaks at multiples of Q/r (verified: Q=64,r=4 -> peaks at 0,16,32,48). Continued fractions
  recovers r from measured k/Q. Superpolynomial speedup -- breaks RSA, Diffie-Hellman, ECC/ECDSA.
  Works because factoring/discrete-log = ABELIAN hidden subgroup problem. Does NOT generalize to
  non-abelian HSP -- no known efficient quantum attack on lattice-based crypto (module 7).

COMPLEXITY: P ⊆ BQP. Factoring ∈ BQP, NOT known ∈ P, NOT believed NP-complete (∈ NP∩co-NP).
  BQP NOT believed to contain NP -- quantum computers don't solve NP-hard problems efficiently.

2026 REALITY CHECK: largest real Shor factorizations still trivial (15,21,35-class numbers).
  RSA-2048 estimated resource requirement fell from ~20M to <1M physical qubits in <2 years
  (algorithmic/compiler improvements, not hardware) -- gap closing faster than qubit counts rise.
```

## Sources

- [Deutsch, D. & Jozsa, R. — Rapid solution of problems by quantum computation (1992), Proc. Royal Society A](https://royalsocietypublishing.org/doi/10.1098/rspa.1992.0167) — accessed 2026-08-08
- [Grover, L. — A fast quantum mechanical algorithm for database search (1996)](https://arxiv.org/abs/quant-ph/9605043) — accessed 2026-08-08
- [Bennett, Bernstein, Brassard, Vazirani — Strengths and Weaknesses of Quantum Computing (1997)](https://arxiv.org/abs/quant-ph/9701001) — accessed 2026-08-08
- [Shor, P. — Algorithms for quantum computation: discrete logarithms and factoring (1994)](https://ieeexplore.ieee.org/document/365700) — accessed 2026-08-08
- [Shor's algorithm resource requirements for RSA-2048 fell by an order of magnitude in under a year — martincid.com](https://www.martincid.com/technology-sv/shors-algorithm-resource-requirements-for-rsa-2048-fell-by-an-order-of-magnitude-in-under-a-year/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
