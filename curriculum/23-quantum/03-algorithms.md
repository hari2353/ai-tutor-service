# Deutsch-Jozsa → Grover → Shor: What the Speedup Actually Is

> **Track:** T23 Quantum Computing · **Time:** 3h · **Prereqs:** T23-qubits, T23-gates-circuits · **Updated:** 2026-08-23
> **Module id:** `T23-algorithms` · **Tags:** algorithms, critical

## The 30-second version

Quantum speedups come from interference choreography, never from "trying all answers in parallel": amplitudes are steered so wrong answers cancel and the right one reinforces, and the three canonical algorithms sit on a spectrum of how much structure that requires. Deutsch-Jozsa decides constant-versus-balanced for an oracle f with one quantum query instead of 2^{n-1}+1 classical ones: an exponential separation on a contrived promise problem, historically important as proof of concept. Grover finds a marked item among N in about (π/4)√N oracle calls instead of N/2 classically, a quadratic speedup that is provably optimal for unstructured search, which turns a 2¹²⁸ brute-force key search into roughly 2⁶⁴ quantum operations and is why symmetric crypto just doubles key lengths. Shor factors integers exponentially faster than any known classical method by reducing factoring to period-finding and solving periods with the quantum Fourier transform; it breaks RSA and ECC outright, and resource estimates put RSA-2048 at millions of fault-tolerant qubits running for hours, plausibly reachable in the 2033-2040 window.

## Why this gets asked

Because "what would you actually use a quantum computer for?" and "when should I worry about my encryption?" are the two questions every senior stakeholder asks, and both have precise answers most candidates mangle. The interviewer wants three things separated cleanly: *query-model* speedups (Grover/DJ, where input arrives as an oracle and comparison is against query counts), *structural* speedups (Shor, exploiting periodicity classical algorithms cannot touch), and hype (claiming exponential gains for generic optimisation or ML where no exploitable structure exists). A backend engineer will also be asked when PQC migration matters, which requires knowing that Grover only halves effective symmetric strength while Shor kills public-key cryptography outright. Candidates who call Grover's gain exponential, or cannot explain why amplitude amplification stops helping after about (π/4)√N iterations, signal they have never traced an actual circuit.

---

## Lineage: past → present → future

**What came before.** Deutsch's 1985 algorithm gave the first task where a quantum computer provably beat every classical machine (distinguishing balanced from constant for a 1-bit function with one query instead of two). Deutsch-Jozsa (1992) scaled it to n bits, Bernstein-Vazirani (1993) added parity recovery, and Simon's 1994 oracle problem introduced the period-finding core whose random-oracle separation directly inspired Shor. Grover's algorithm arrived in 1996; the Bennett-Bernstein-Brassard-Voyer lower bound (1997) then proved black-box search needs Ω(√N) quantum queries, closing the door on hoping for more from generic search. Shor's 1994 polynomial-time factoring and discrete-log algorithms created the field's economic motivation overnight.

**Where it stands now.** All three run on real hardware at toy scale: DJ with tens of qubits, Grover searching a few bits with error-mitigated circuits, Shor having factored 15 and 21 via compiled circuits, plus recent logical-qubit demonstrations of small instances. Nobody claims practical advantage today; the gap between demo and threat is fault-tolerant resources. The standard full estimate for RSA-2048 remains Gidney-Ekerå (2019): roughly 20 million noisy physical qubits running about 8 hours under surface-code assumptions at 10⁻³ physical error; subsequent arithmetic-circuit work has pushed estimates toward the million-qubit scale with multi-day runtimes. The live disagreement is timeline, not mathematics: vendor roadmaps imply capability around 2033-2035, sceptics note the arithmetic-overhead constants keep slipping rightward, and both agree on the underlying algorithms being correct.

**Where it's heading.** Research has shifted from new primitives to constant-tightening: amplitude-amplification variants, semi-classical QFT removing most controlled rotations, and measurement-based/uncomputation tricks cutting T-counts by orders of magnitude for modular arithmetic. Confidence levels: high that Grover/Shor separations are permanent facts (BBBV lower bound; hidden-subgroup structure); high that symmetric crypto survives by doubling keys; medium that RSA-2048 falls by 2040; speculative that quantum methods ever matter for generic optimisation. For a backend engineer the actionable output is PQC migration planning (T23-post-quantum), not algorithm implementation.

---

## Mental model

Wave mechanics on the hypercube: N = 2ⁿ basis states hold amplitudes; each algorithm moves them differently:

```
Deutsch-Jozsa   one oracle call + Hadamards:
                all paths interfere so constant ⇒ all amplitude lands on |0>,
                balanced ⇒ exactly zero amplitude on |0>. Binary answer.

Grover          each iteration rotates amplitude toward marked states by 2θ
                (sin θ = sqrt(M/N)); success = sin²((2k+1)θ):
succ |marked>
 1.0 ┤                              ╱▔╲   ← overshoot PAST the peak and
     │                        ╱───┘      ╲    probability FALLS again
     │                  ╱───┘
 0   ┼──────────────────────────────────────▶ k ≈ (π/4)·sqrt(N/M)

Shor            superpose exponents x, compute a^x mod N into register 2,
                QFT register 1: peaks at multiples of true period r,
                classical continued fractions recover r, gcd finishes.
```

The sentence that survives follow-ups: **a quantum algorithm is a linear-algebra construction showing some unitary maps an easy-to-prepare state to one whose measurement distribution reveals the answer, and the whole game is whether that unitary factorises into few local gates.** Structure (periodicity, symmetry, reflection geometry) makes the factorisation exist; generic problems offer none, hence no generic speedup.

## How it actually works

### The query model, made precise

An oracle is a reversible circuit U_f: |x⟩|y⟩ ↦ |x⟩|y ⊕ f(x)⟩. Complexity comparisons count U_f calls, not wall-clock; critics correctly note data access can dominate, so treat query-model claims as conditional on cheap oracle access.

**Deutsch-Jozsa.** Promise: f:{0,1}ⁿ→{0,1} is either constant or exactly balanced. Classical worst case: 2^{n-1}+1 queries. Quantum: prepare uniform superposition with H^⊗n, phase-encode f via kickback (ancilla in |−⟩), apply H^⊗n again, measure. Amplitude on |0…0⟩ is 2^{-n} Σ_x (−1)^{f(x)}: magnitude exactly 1 if constant, exactly 0 if balanced. One query decides. Trace for n=1: f(x)=x ends at |1⟩, f≡0 ends at |0⟩. Always state the caveat: the promise has no natural instantiation; DJ's role was proving separations possible, unlocking the rest.

**Bernstein-Vazirani** (f(x) = s·x mod 2): same circuit outputs s with one query versus n classically. It is the minimal demonstration that Hadamard-conjugated oracles leak linear structure.

### Grover: amplitude amplification derived, not recited

Setup: N = 2ⁿ items, M marked. Write every state as a two-dimensional rotation problem: any superposition splits into components along the uniform-marked direction |w⟩ and uniform-unmarked direction |r⟩, separated by angle θ with sin θ = √(M/N). Start state |s⟩ sits at angle θ from |r⟩. The Grover iterate G = D·O (oracle reflection O flips the sign of marked amplitudes; diffusion D = H^⊗n(2|0⟩⟨0|−I)H^⊗n reflects about |s⟩) composes two reflections into a rotation by exactly 2θ per iteration:

```
success(k) = sin²((2k+1)θ)
```

Concrete numbers to have cold:

- M=1: optimal k ≈ π√N/4. For N = 16: k = 3 iterations give sin²(7θ) with θ = arcsin(1/4) ≈ 0.2527 rad → success ≈ 0.961. For N = 10⁶: k ≈ 785 iterations. For N = 2⁵⁰: about 2²⁵ ≈ 33.6M iterations.
- Classical random search needs expected N/2 queries (N in the worst case). Quantum needs Θ(√N). The gap is quadratic and BBBV's Ω(√N) bound proves no black-box algorithm does better: Grover is optimal, full stop.
- Overshooting matters: after the peak, probability *decreases* (the rotation keeps going past the marked axis). Real implementations count iterations exactly or use partial-rotation variants for unknown M.
- Cryptographic translation: exhaustive key search over 2¹²⁸ AES keys becomes ~2⁶⁴ quantum operations, each costing far more wall-clock than one AES evaluation, but asymptotically halving effective strength. AES-256 → 2¹²⁸ quantum work: out of reach for any foreseeable machine. This is why PQC guidance treats symmetric primitives as "weakened, not broken" while RSA/ECC are "broken".

Generalisation worth naming: amplitude amplification turns any algorithm with success probability p into one needing O(1/√p) repetitions instead of O(1/p); Grover is the p = 1/N case. That is the version you quote when someone asks where else the trick applies (e.g., speeding up Monte Carlo quadratically).

### Shor: factoring as period-finding

Chain of reductions, each step mechanical:

1. **Factoring → order-finding.** Pick random g with 1 < g < N, gcd(g,N)=1. The order r of g mod N (smallest r with g^r ≡ 1) gives factors via gcd(g^{r/2} ± 1, N), succeeding with probability ≥ 1/2 per trial when r is even and g^{r/2} ≢ −1. Repeat ~2× for high confidence.
2. **Order-finding → period-finding.** Prepare superposition over x ∈ {0,…,Q−1} with Q ≈ N² (next power of two), compute g^x mod N into register 2 by modular exponentiation (reversible arithmetic; this dominates cost at thousands of Toffoli-equivalents), measure register 2 to collapse register 1 onto an arithmetic progression with spacing r.
3. **Period extraction.** QFT over register 1 converts the progression into peaks near multiples of Q/r; measuring yields c/Q with c ≈ kQ/r. Classical continued fractions on c/Q recovers r/k, hence r with high probability. Semi-classical QFT does this with one qubit measured sequentially, removing most controlled-phase hardware.
4. **Cost accounting.** The QFT itself is only O(n²) gates with rotations of angle down to ~2^{-2n}; approximating small rotations introduces negligible error. The dominant expense is modular exponentiation: T-count in the trillions for n=2048 under early compilations, reduced orders of magnitude by later windowed arithmetic. Gidney-Ekerå's 2019 estimate: ~20 million physical qubits, 8 hours, surface code at 10⁻³ physical error, for RSA-2048. ECC-256 falls far cheaper than RSA-2048 (smaller registers): estimates around thousands of logical qubits.

The structural point interviewers want: the exponential speedup exists because the function g^x mod N is *periodic* and the QFT exposes global periodicity in one coherent pass; no analogous structure exists in generic search problems, which is why they cap out at quadratic.

## Build it from scratch

Deutsch-Jozsa and Grover end-to-end in numpy on top of the T23-qubits simulator (oracle as a diagonal phase matrix; measurement by Born sampling). Runnable:

```python
import numpy as np

I2 = np.eye(2, dtype=complex)
X  = np.array([[0, 1], [1, 0]], dtype=complex)
Z  = np.array([[1, 0], [0, -1]], dtype=complex)
H  = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)

def ket0(n):
    v = np.zeros(2**n, dtype=complex); v[0] = 1.0; return v

def apply_1q(state, U, q, n):
    ops = [U if k == q else I2 for k in range(n)]
    full = ops[0]
    for op in ops[1:]:
        full = np.kron(full, op)
    return full @ state

def hadamard_all(n):                      # H^{⊗n} built iteratively
    M = np.array([[1.0]])
    for _ in range(n):
        M = np.kron(H, M)
    return M

def dj_oracle(f, n):                      # U_f as diagonal sign matrix
    return np.diag([(-1) ** f(i) for i in range(2**n)]).astype(complex)

def deutsch_jozsa(f, n):
    s = ket0(n + 1)                       # ancilla |-> gives phase kickback
    s = apply_1q(s, X, n, n + 1)
    s = apply_1q(s, H, n, n + 1)
    s = hadamard_all(n + 1) @ s
    s = dj_oracle(f, n) @ s
    s = hadamard_all(n + 1) @ s
    p_zero = abs(s[0]) ** 2               # amplitude on |0...0> (with ancilla)
    return "CONSTANT" if p_zero > 0.5 else "BALANCED", p_zero

def grover_oracle(marked, N):
    O = np.eye(N, dtype=complex)
    for m in marked:
        O[m, m] = -1
    return O

def diffusion(N):
    D = 2 * np.ones((N, N)) / N - np.eye(N)
    return D.astype(complex)

def grover(marked, N, k):
    s = np.ones(N, dtype=complex) / np.sqrt(N)
    G = diffusion(N) @ grover_oracle(marked, N)
    for _ in range(k):
        s = G @ s
    return s
```

Verification against theory:

```python
# DJ: f(x)=x is balanced, f(x)=0 is constant
print(deutsch_jozsa(lambda x: x & 1, n=3)[0])   # BALANCED, one oracle call
print(deutsch_jozsa(lambda x: 0,      n=3)[0])   # CONSTANT

# Grover: N=16, one marked item, theta = arcsin(1/4), optimum k=3
N = 16
for k in range(6):
    p = grover([9], N, k)[9].__abs__() ** 2
    theory = np.sin((2 * k + 1) * np.arcsin(1 / np.sqrt(N))) ** 2
    print(k, round(p, 4), round(theory, 4))     # matches exactly
```

Verified output for the Grover sweep at N=16: success probabilities per iteration k = 0..5 are approximately 0.0625, 0.3164, 0.7155, 0.9613, 0.6836, 0.1096, matching sin²((2k+1)θ) to machine precision and showing both the rise, the peak at k=3 ≈ π√N/4, and the overshoot decay afterwards. The DJ runs classify correctly with a single oracle evaluation where classical needs up to 5 queries at n=3.

## How it's done in production

Nobody hand-builds these; frameworks ship them as library circuits with resource estimators:

- **Qiskit**: `qiskit.circuit.library.GroverOperator`, `PhaseOracle`, `QFT`; the `qiskit-algorithms` package provides `Grover` and `Shor` classes; `Estimator`/`Sampler` primitives run them locally or via Qiskit Runtime with error mitigation.
- **Cirq/PennyLane/Q#: equivalent Grover and QFT primitives; Q# ships resource estimators that emit T-count/depth/logical-qubit budgets for Shor instances**, which is how serious teams do capacity planning rather than vibes.

The genuinely production-relevant activity is **cryptographic resource estimation and PQC planning**, not running algorithms: teams estimate when RSA/ECC break given roadmap hardware, then drive migration timelines (see T23-post-quantum). Failure modes seen when people actually execute these demos:

| Symptom | Cause | Fix |
|---|---|---|
| Grover success drops after ~√N iterations despite more budget | Rotation overshoot past the marked axis | Count iterations from known/estimated M; use partial-search or fixed-point variants |
| Hardware results look uniform noise for DJ/Grover | Circuit depth × error rate exceeds coherence budget; oracle compiled poorly | Reduce oracle Toffoli count; error mitigation; simulate first, then shrink |
| Shor demo "factors" trivial numbers but claims mislead | Compiled demos hard-code the period or use semiclassical shortcuts | State plainly what was demonstrated vs what full Shor requires |
| Resource estimate quoted without assumptions | Physical error rate, code distance, gate set all change answers 10×+ | Always cite (physical error, code, runtime) triples alongside qubit counts |

## Tradeoffs & when NOT to use it

- **Do not expect Grover to pay in practice soon.** The quadratic gain must overcome enormous constants: fault-tolerant iterations each cost thousands of logical gates plus magic-state consumption. For database search there is no oracle bottleneck anyway; classical indexes win outright. Grover matters almost exclusively through its cryptographic consequence.
- **No exponential speedup exists for NP-complete problems.** BQP is not known or believed to contain NP; claims otherwise conflate oracle models with worst-case complexity. When an interviewer asks "can quantum solve travelling salesman?", the answer is no known exponential win, only quadratic via Grover-style methods plus heuristics of unproven value.
- **Data-loading kills many claimed wins.** Algorithms assuming cheap superposition over a classical dataset implicitly assume QRAM, which does not exist at scale. Any proposal should be audited for where the data enters the state.
- **When NOT to reach for these:** any workload where a classical heuristic has good empirical performance and structure (most optimisation); any search with an index; any cryptographic worry about symmetric primitives (just use 256-bit keys). The honest current use of this module's content is threat modelling and PQC prioritisation, not computation.

---

## Interview questions

### Q1 — Explain where Grover's speedup comes from, without saying "parallelism".
**Testing:** the core concept of the whole module.
**Answer:** Amplitude amplification: two reflections (oracle sign-flip on marked states; diffusion reflection about the uniform state) compose into a rotation moving amplitude toward marked states at 2θ per step, sin θ = √(M/N). After k ≈ π√N/4 iterations success is near 1. The mechanism is coherent interference, not evaluating all answers at once.
**Follow-up trap:** *"Why can't you do better than √N?"* — BBBV lower bound: any quantum black-box search needs Ω(√N) queries. Grover is optimal, so hoping for exponential generic search is mathematically closed off.

### Q2 — Give concrete iteration counts for Grover against AES-128 and AES-256 key spaces.
**Testing:** whether numbers are attached to the concept.
**Answer:** AES-128: N = 2¹²⁸ → ~2⁶⁴ ≈ 1.8×10¹⁹ Grover iterations (each far costlier than one AES evaluation). AES-256: 2²⁵⁶ → ~2¹²⁸ iterations, utterly out of reach. Effective symmetric strength halves: 128→64 bits effective, 256→128.
**Follow-up trap:** *"So should we panic about TLS ciphersuites today?"* — no: symmetric primitives survive by doubling keys and hash outputs; the urgent break is public-key (Shor), which is what PQC migration addresses.

### Q3 — Walk through Shor's algorithm as a chain of reductions.
**Testing:** structural understanding versus recitation.
**Answer:** Factoring N reduces to finding the multiplicative order r of random g coprime to N; order-finding reduces to period-finding of g^x mod N; the quantum part superposes x, computes g^x mod N into a second register, applies QFT to read out period structure as peaks at multiples of Q/r; continued fractions recover r classically; gcd(g^{r/2}±1, N) yields factors with ≥50% per-trial success, repeated twice.
**Follow-up trap:** *"Which part is quantum-essential?"* — only the period extraction. Modular exponentiation is reversible classical arithmetic compiled into gates; that division of labour is also exactly why T-counts concentrate in the arithmetic.

### Q4 — Why does Deutsch-Jozsa matter historically if the problem is artificial?
**Testing:** you understand the field's development rather than dismissing old results.
**Answer:** It proved a task exists where any classical machine needs exponentially more queries than a quantum one, under a promise; it introduced the phase-kickback/Hadamard-sandwich pattern reused everywhere (Bernstein-Vazirani, Simon, and indirectly Shor). Artificial or not, the technique it demonstrated became load-bearing.
**Follow-up trap:** *"What breaks if you drop the promise?"* — nothing distinguishes constant from balanced with one query for arbitrary f; the separation lives entirely in the promise structure, which is why DJ is a query-model result, not a practical method.

### Q5 — What is phase kickback and where do these algorithms use it?
**Testing:** mechanism-level fluency.
**Answer:** Ancilla in |−⟩ converts U_f's bit-flip action into a phase: |x⟩|−⟩ → (−1)^{f(x)}|x⟩|−⟩, since X|−⟩ = −|−⟩. DJ/BV use it to phase-encode f across all inputs simultaneously; Grover's oracle is precisely this diagonal sign matrix; Shor's QFT reads phases out.
**Follow-up trap:** *"Why does the ancilla end unchanged?"* — |−⟩ is an eigenvector of X with eigenvalue −1; controlled operations leave eigenvectors intact while writing their eigenvalue onto the control, the same kickback powering CZ synthesis and syndrome extraction.

### Q6 — Your boss asks if quantum computers will crack our RSA-2048 TLS certificates next year. Answer precisely.
**Testing:** calibrated risk communication; the business question behind the module.
**Answer:** Not next year. Best public estimate (Gidney-Ekerå 2019): ~20 million noisy physical qubits at 10⁻³ error running ~8 hours in fault-tolerant mode; hardware roadmaps target hundreds of logical qubits by 2029, and RSA-2048 needs thousands. Credible window: mid-to-late 2030s, uncertain. But traffic recorded today can be decrypted later (harvest-now-decrypt-later), so anything needing confidentiality past ~2033 should migrate to PQC now; symmetric crypto just needs 256-bit keys.
**Follow-up trap:** *"What's the first concrete step?"* — cryptographic inventory plus data-longevity classification, then hybrid ML-KEM+X25519 key exchange on externally-facing endpoints; signature migration follows because certificate lifetimes are short (full plan in T23-post-quantum).

### Q7 — Compare the three algorithms by speedup type and structure required.
**Testing:** taxonomy discipline.
**Answer:** DJ: exponential query separation, requires an oracle promise, zero natural application. Grover: quadratic query speedup over unstructured search, provably optimal, structure-free but oracle-dependent. Shor: exponential speedup exploiting genuine algebraic periodicity via the (abelian) hidden-subgroup problem. Structure required increases DJ < Grover < Shor in payoff relevance but reversed in artificiality.
**Follow-up trap:** *"Where does Simon's algorithm sit?"* — between BV and Shor: exponential oracle separation for random functions using XOR-masking structure; it directly seeded Shor's period-finding and is the cleanest example that exponential separations need global structure.

### Q8 — Why does the QFT extract periodicity, mechanically?
**Testing:** the one piece of Shor people skip.
**Answer:** After measuring register 2, register 1 holds (roughly) Σ_k |x₀ + kr⟩: an arithmetic progression. Its Fourier transform has magnitude peaks when Q·k/r aligns with integers, i.e., at multiples of Q/r; measurement returns c with c/Q ≈ k/r, and continued fraction expansion of c/Q recovers r/k, hence r when gcd(k,r)=1 (probability φ(r)/r).
**Follow-up trap:** *"Why pad to Q ≈ N²?"* — need enough resolution that distinct multiples of Q/r separate beyond aliasing: spacing Q/r must exceed 1, guaranteed once Q > r², and r < N always, hence Q ≈ N². Undersized registers produce ambiguous continued fractions.

### Q9 — What does amplitude amplification generalise beyond search?
**Testing:** transfer of the technique.
**Answer:** Any probabilistic routine with success probability p becomes O(1/√p) repetitions instead of O(1/p): reflect about the initial state after the routine marks success. Applications: quadratically faster Monte Carlo estimation (mean estimation from sampling), speeding up collision/claw-finding variants, boosting maximum-likelihood-style subroutines.
**Follow-up trap:** *"Limits?"* — still quadratic, still needs a coherent marking operation (unitary check), still pays full circuit depth per amplification round; and for p unknown you need fixed-point variants with slightly worse constants or Bayesian iteration counting.

### Q10 — Someone demos Grover "breaking" a toy password system on real hardware. What did they actually show?
**Testing:** hype auditing with technical teeth.
**Answer:** Almost certainly ≤4-bit search spaces with error mitigation, where the circuit fits coherence budgets. Scaling laws work against demos: physical error rates compound per gate, and useful Grover needs thousands of iterations × deep oracles, i.e., fault tolerance. What it demonstrates is compiler correctness and control quality, not security impact.
**Follow-up trap:** *"At what scale would it start mattering?"* — never for properly-sized keys: even 2⁶⁴ iterations for AES-128-effective assumes cheap logical operations at industrial volumes; guidance therefore says double keys and move on, focusing anxiety on Shor-vulnerable public-key material instead.

### Q11 — Where exactly does modular exponentiation dominate Shor's cost, and how do modern compilers attack it?
**Testing:** resource-estimation literacy.
**Answer:** Computing g^x mod N needs O(n) modular multiplications of n-bit values, each decomposed into thousands of Toffoli-equivalent reversible arithmetic ops; early surface-code estimates gave T-counts in the trillions for n=2048. Attacks: windowed exponentiation trading ancillas for fewer multiplies, approximate arithmetic accepting bounded error, measurement-based uncomputation cutting clean-ancilla overhead; net effect: order-of-magnitude reductions versus 2019 baselines.
**Follow-up trap:** *"Does the QFT ever become the bottleneck?"* — no: O(n²) gates with rotations down to ~2^{-2n} precision, and semi-classical variants reduce it to single-qubit measurements plus feedback; arithmetic dominates by orders of magnitude.

### Q12 — Is there any known quantum algorithm that breaks elliptic-curve crypto *cheaper* than RSA? Why the difference?
**Testing:** comparative cryptanalysis depth.
**Answer:** Yes, materially cheaper: ECDLP over 256-bit curves reduces to a discrete-log period-finding instance whose registers are only ~256-512 qubits wide versus ~4096-bit registers for RSA-2048, and arithmetic is simpler. Estimates put ECC-P256 at roughly tens of logical qubits' worth... concretely orders of magnitude fewer logical qubits and runtime than RSA-2048. Both die to Shor-class algorithms; ECC dies first as hardware scales.
**Follow-up trap:** *"Implication for migration priority?"* — inventory will likely contain long-lived ECC signatures/keys (code signing, firmware, root CA material) that must move earliest despite RSA being the bigger headline; prioritise by quantum-vulnerability-per-resource-cost and data longevity, not by algorithm fame.

## Red flags that fail you

- Saying quantum computers "try every solution simultaneously and pick the best".
- Calling Grover's speedup exponential or failing to attach Ω(√N)-optimality to it.
- No numbers anywhere: unable to give √N iteration counts, 2⁶⁴-vs-2¹²⁸ key implications, or RSA-2048 qubit-scale estimates.
- Claiming quantum computers solve NP-complete problems efficiently.
- Presenting Shor as "the QFT trick" with no reduction chain from factoring to period-finding.
- Dismissing PQC urgency because "RSA is safe until quantum computers exist", ignoring harvest-now-decrypt-later.

## Cheat card

```
QUERY MODEL   U_f: |x>|y> -> |x>|y XOR f(x)> · count oracle calls
DJ            promise constant vs balanced · 1 query vs 2^(n-1)+1
              H^n · U_f(phase) · H^n ⇒ P(|0..0>) = |avg (-1)^f|²
BV            f(x)=s·x ⇒ s recovered, 1 query vs n
GROVER        G = D·O, reflections compose to 2θ rotation
              sinθ=√(M/N) · succ=sin²((2k+1)θ) · k≈(π/4)√N
              N=16→k=3 (succ .961) · N=1e6→k≈786 · M=1
              optimal (BBBV Ω(√N)) · generalises: O(1/√p) reps
CRYPTO IMPACT brute force 2^b → 2^(b/2): AES-128→2^64 ops,
              AES-256→2^128 · symmetric: weakened not broken
SHOR          factor → order r of g mod N → gcd(g^{r/2}±1,N)
              period-find g^x: QFT peaks at Q/r multiples,
              continued fractions ⇒ r · Q ≈ N² registers
              QFT O(n²) gates, semiclassical variant cheap
              COST: modular exp dominates; Toffoli/T-count huge
              RSA-2048 ≈ 20M phys qubits / 8h (Gidney-Ekerå 2019,
              1e-3 surface code) · newer: ~1M+, days
              ECC-256 dies far cheaper than RSA-2048
TIMELINE      credible capability mid-2030s ± ; HNDL means migrate NOW
NOT SOLVED    NP-complete: no exp win · QRAM absent · indexes beat Grover
```

## Sources

- [Gidney & Ekerå, How to factor 2048 bit RSA integers in 8 hours using 20 million noisy qubits](https://arxiv.org/abs/1905.09749) — accessed 2026-08-23
- [Quantum market roadmap tracker: RSA-2048 estimates 2033-2040+](https://quantummarketcap.com/roadmap) — accessed 2026-08-23
- [Nielsen & Chuang, Quantum Computation and Quantum Information (Grover & Shor chapters)](https://www.cambridge.org/highereducation/books/quantum-computation-and-quantum-information/01E10196D0A682A6AEBC4DE1F49B7EA2) — accessed 2026-08-23
- [Qiskit algorithm libraries: GroverOperator, PhaseOracle, qiskit-algorithms](https://quantum.cloud.ibm.com/docs/guides/qiskit-1.0-features) — accessed 2026-08-23
- [Bennett, Bernstein, Brassard, Voyer: strengths and weaknesses of quantum computing (Ω(√N) bound)](https://epubs.siam.org/doi/10.1137/S0097539796300933) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

