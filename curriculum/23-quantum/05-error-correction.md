# Noise, Decoherence, NISQ, Surface Codes, Logical vs Physical Qubits

> **Track:** T23 Quantum Computing · **Time:** 2.0h · **Prereqs:** T23-qubits, T23-gates-circuits
> **Updated:** 2026-08-08
> **Module id:** `T23-error-correction` · **Tags:** hardware, critical

## The 30-second version

Every real qubit decays: `T1` characterizes energy relaxation (`|1⟩→|0⟩` decay, probability `1−e^{-t/T1}` by time `t`) and `T2` characterizes dephasing (loss of the relative-phase information that makes superposition meaningful, `T2 ≤ 2T1` always), and any circuit whose runtime approaches these timescales accumulates errors faster than it accomplishes useful computation — this is precisely the constraint that defines the "NISQ" era (Noisy Intermediate-Scale Quantum, John Preskill's 2018 term): tens to low-thousands of physical qubits, no error correction, circuit depth bounded by coherence time, no fault tolerance. Quantum error correction fixes this not by copying the state (blocked by no-cloning, module 2) but by **entangling** one logical qubit across several physical qubits and measuring **stabilizers** — parity-check operators that reveal *which* error occurred without revealing *anything about the encoded state itself*, the 1995-96 Shor/Steane insight that made quantum error correction possible at all. The **surface code** is the leading practical scheme today because it needs only 2D nearest-neighbor connectivity and has a comparatively forgiving error threshold (~1% physical two-qubit gate error); below that threshold, adding more physical qubits per logical qubit *exponentially reduces* the logical error rate — a real result experimentally confirmed for the first time in 2026 (Google's Willow chip demonstrating below-threshold scaling), not just theoretical. The number that actually matters for "when does this become useful": the physical-to-logical qubit ratio is commonly estimated in the hundreds to low thousands today, which is why a chip with several thousand physical qubits (IBM's Kookaburra, ~4,158 physical qubits) still yields only a handful to tens of true fault-tolerant logical qubits, and why Microsoft/Quantinuum's 12-logical-qubit milestone (March 2026) is genuinely newsworthy despite the number looking small.

## Why this gets asked

Because this is the module that turns "quantum computing" from an interesting theory conversation into an actual timeline and investment judgment, and it's exactly the question a principal engineer gets asked by leadership: "should we be doing anything about quantum right now, and if so, what, and by when." Anyone who has watched a vendor pitch conflate "we have 1,000 physical qubits" with "we have 1,000 usable logical qubits" — a category error that inflates apparent progress by roughly two to three orders of magnitude — needs a candidate who can name the actual ratio and explain why it exists, not just gesture at "the hardware isn't ready yet."

---

## Lineage: past → present → future

**What came before.** Classical error correction (Hamming codes, 1950; the broader theory formalized by Shannon) relies on redundancy — store the same bit multiple times, take a majority vote to correct a flip. This approach is directly blocked for quantum information by the no-cloning theorem (module 2): you cannot make independent copies of an unknown quantum state to vote among. Worse, the obvious naive fix — "measure the qubit to check if it's still correct" — destroys the very superposition you're trying to protect (module 1's collapse postulate). For years after quantum computing was proposed, a real and reasonable pessimism existed among physicists that quantum error correction might be *fundamentally* impossible for exactly these two reasons. Peter Shor (1995) and Andrew Steane (1996), independently, broke this pessimism with the key insight that makes the entire field possible: you can measure **syndromes** — specific multi-qubit parity operators — that reveal *which* error occurred without revealing *what the encoded logical state is*, because the syndrome measurement commutes with (doesn't distinguish between) the logical `|0⟩` and `|1⟩` basis states. This is the load-bearing idea the rest of this module builds on, and it was quickly followed by the **fault-tolerance threshold theorem** (Aharonov & Ben-Or, 1996; Knill & Laflamme, 1996): if the physical error rate per gate is below some threshold, arbitrarily long and reliable quantum computation is achievable with only polylogarithmic overhead — proving, in principle, that scaling quantum computers wasn't hopeless.

**Where it stands now.** The **surface code** (Kitaev's foundational work through the 1990s-2000s, practically popularized by Fowler et al. 2012) is the dominant scheme in active use because it requires only nearest-neighbor 2D qubit connectivity — a natural match for how superconducting chips are physically laid out — and has a comparatively high fault-tolerance threshold, commonly cited around 1% physical two-qubit gate error rate, well within reach of current hardware generations. The live, genuinely unresolved architecture debate is overhead: surface codes are believed to need on the order of hundreds to a few thousand physical qubits per logical qubit at useful logical error rates with today's physical error rates, while newer quantum LDPC (low-density parity-check) codes promise dramatically better overhead ratios in theory but are significantly harder to implement given current hardware connectivity constraints — this is an active competition between architectures, not a settled question. What's actually deployed and demonstrated, as opposed to merely published: 2026 marks a genuine inflection point, not incremental progress — Google's Willow chip demonstrated **below-threshold** error correction on real hardware for the first time, meaning scaling up the code (more physical qubits per logical qubit) measurably *reduced* the logical error rate exactly as threshold theory predicts, rather than the reverse (which is what happens above threshold, and what happened on earlier, smaller error-correction demonstrations); Microsoft and Quantinuum's H2 trapped-ion system separately demonstrated 12 logical qubits at a logical error rate around 2-in-1,000 in March 2026 ([Quantum Computing Milestones 2026](https://www.technerdo.com/blog/quantum-computing-milestones-2026) — accessed 2026-08-08). Both are real engineering proofs that the theory works at small scale — neither is remotely close to the thousands of long-lived, low-error logical qubits Shor's algorithm at cryptographically relevant scale would require (module 3).

**Where it's heading.** High confidence: continued scaling of logical qubit count and improving logical error rates is the industry's explicit, publicly stated near-term roadmap — IBM has stated a goal of demonstrating quantum advantage on a *useful* workload by end of 2026 with its Nighthawk and Kookaburra-generation hardware. This is a narrower, more achievable claim than "cryptographically relevant fault-tolerant computer," and conflating the two — treating "useful quantum advantage on some workload" as equivalent to "can now break RSA" — is a common and consequential overclaiming trap; module 3 and module 7 depend on keeping this distinction sharp. Lower confidence, genuinely open: whether the surface-code-on-superconducting-qubits combination remains the dominant path, or whether alternative codes (LDPC-style) or alternative hardware modalities (neutral atoms and trapped ions have some structural advantages for certain code geometries) displace it — this is an active, unresolved bet across the industry, not a direction with consensus.

---

## Mental model

```
  T1 / T2 DECAY                                    PHYSICAL vs LOGICAL QUBITS
  ─────────────                                     ─────────────────────────
  P(relaxed by time t) = 1 - e^(-t/T1)              ONE logical qubit
  coherence remaining  = e^(-t/T2),  T2 ≤ 2·T1           ▲
                                                          │  encoded across
  T1=100us, T2=80us (typical superconducting order):      │  ~hundreds to low
    t=10us:  P(relax)=0.095, coherence=0.883              │  thousands of
    t=50us:  P(relax)=0.393, coherence=0.535              │  PHYSICAL qubits
    t=100us: P(relax)=0.632, coherence=0.286               │  (surface code,
  -> circuit must finish well within this budget           │   below threshold)
                                                     ●●●●●●●●●●●●●●●●●●●●●●●●
                                                     one "patch" of physical qubits

  3-QUBIT BIT-FLIP CODE: syndrome reveals ERROR LOCATION without revealing the STATE
  ────────────────────────────────────────────────────────────────────────────────
  encode:  a|0⟩+b|1⟩  --CNOTs-->  a|000⟩+b|111⟩
  error:   X on qubit 1 (middle)  -->  a|010⟩+b|101⟩
  syndrome (parity checks, don't touch a,b):
    Z0Z1 parity = 1,  Z1Z2 parity = 1   -->  UNIQUELY identifies "qubit 1 flipped"
  correct: apply X to qubit 1  -->  back to a|000⟩+b|111⟩, a and b NEVER measured
```

---

## How it actually works

### T1, T2, and the coherence budget

**`T1` (energy relaxation time):** the characteristic timescale over which an excited `|1⟩` state decays to the ground `|0⟩` state by losing energy to its environment. The probability of relaxation having occurred by time `t` is `1 − e^{-t/T1}`.

**`T2` (dephasing time):** the characteristic timescale over which the *relative phase* between `|0⟩` and `|1⟩` components randomizes — the coherence a superposition needs to remain meaningful decays as `e^{-t/T2}`. `T2` is always `≤ 2T1` — dephasing can never be slower than what energy relaxation alone would already impose, a fundamental bound, not an engineering choice.

Verified directly, for representative superconducting-qubit-scale values (`T1=100µs, T2=80µs`, realistic order of magnitude for current hardware generations):

```
t=1µs:   P(relaxation)=0.0100, coherence remaining=0.9876
t=10µs:  P(relaxation)=0.0952, coherence remaining=0.8825
t=50µs:  P(relaxation)=0.3935, coherence remaining=0.5353
t=100µs: P(relaxation)=0.6321, coherence remaining=0.2865
```

This is the entire reason NISQ-era circuit depth is bounded: if a two-qubit gate takes ~300ns and `T2≈80µs`, a circuit longer than roughly 100-200 sequential two-qubit gates is already operating with substantial accumulated decoherence before it finishes — real algorithms (Shor's for cryptographically relevant `N`, deep VQE ansätze, module 6) require circuit depths far beyond this budget on uncorrected hardware, which is precisely why they're not runnable today regardless of qubit *count*.

### NISQ: the term, and what it actually bounds

**NISQ** — Noisy Intermediate-Scale Quantum — was coined by John Preskill in his 2018 paper of the same name, describing devices with tens to low-thousands of qubits, no error correction, and performance bounded jointly by gate error accumulation and the coherence budget above. "Quantum advantage" claims on NISQ hardware (Google's original 2019 random-circuit-sampling claim being the best-known example) are narrower and more contested than headlines suggest — they typically demonstrate a specific sampling task is hard to *classically simulate exactly*, not that the task is *useful*, and several such claims have subsequently been challenged or matched by improved classical simulation techniques. The honest framing: NISQ-era hardware can run *some* interesting small experiments, but it cannot run any of module 3's algorithms at a scale that threatens real cryptography or delivers proven, sustained advantage on a useful workload — that requires the error correction covered in the rest of this module.

### Why quantum error correction is possible at all: syndrome extraction without state collapse

The Shor/Steane insight, made concrete: a **stabilizer** is a multi-qubit operator (built from tensor products of Pauli matrices, module 2) chosen so that it commutes with every operation used to encode the logical state, and — critically — gives the *same* measurement outcome regardless of whether the logical qubit is in state `|0⟩_L`, `|1⟩_L`, or any superposition of them. Measuring a stabilizer therefore reveals whether an error has disturbed the encoded state (and which one) **without collapsing or revealing anything about the logical superposition itself** — this is what "error information without state information" means mechanically, not just as a slogan.

### The 3-qubit repetition code, verified end to end

The simplest concrete example, protecting against **bit-flip (`X`) errors only**: encode `a|0⟩+b|1⟩ → a|000⟩+b|111⟩` via two `CNOT`s (module 2's exact GHZ-state-building circuit, structurally). Verified directly with `a=0.6, b=0.8` (a valid normalized state, `0.6²+0.8²=1`):

```
encoded state: a|000⟩ + b|111⟩ = [0.6, 0, 0, 0, 0, 0, 0, 0.8]

X error injected on the MIDDLE qubit: a|010⟩ + b|101⟩ = [0, 0, 0.6, 0, 0, 0.8, 0, 0]

syndrome via parity checks Z0Z1 and Z1Z2 on the errored basis states:
  |010⟩: Z0Z1 parity = 1, Z1Z2 parity = 1
  |101⟩: Z0Z1 parity = 1, Z1Z2 parity = 1
syndrome (1,1) UNIQUELY identifies "qubit 1 flipped" (each of the 3 possible single-qubit
  flip locations gives a different, distinguishable syndrome pattern)

correction: apply X to qubit 1  ->  recovers a|000⟩+b|111⟩ exactly, confirmed:
  corrected == original encoded: True
```

At no point in this process was `a` or `b` measured or revealed — the syndrome measurement (`Z0Z1`, `Z1Z2`) only ever returns information about *which qubit flipped*, consistent with the Shor/Steane insight above.

**The critical limitation, stated precisely:** this code protects against `X` (bit-flip) errors only. A `Z` (phase-flip) error on any qubit is completely invisible to this syndrome and goes uncorrected. A separate phase-flip code (the same construction, conjugated by Hadamards so it operates in the `X`-eigenbasis instead) is needed for `Z` errors, and Shor's original 9-qubit code nests the bit-flip code inside the phase-flip code to protect against both simultaneously. A deeper, genuinely surprising fact worth knowing cold: protecting against just the discrete Pauli errors `X`, `Y=iXZ`, and `Z` turns out to be *sufficient* to protect against **arbitrary, continuous single-qubit errors** — any error operator can be decomposed into a linear combination of `I, X, Y, Z`, and the discreteness of quantum measurement means correcting the three discrete Pauli error types actually corrects the continuum of possible small perturbations too. This "discretization of errors" result is part of why quantum error correction is tractable at all, not merely a convenient simplification.

### Surface codes: the practical, scalable answer

The surface code arranges physical qubits on a 2D lattice, alternating **data qubits** (carrying the encoded information) with **ancilla qubits** (used only for syndrome measurement), with stabilizers defined locally over small plaquettes of nearest-neighbor qubits — matching real chip connectivity far better than codes requiring long-range interactions. One logical qubit is encoded per surface-code "patch," and the patch's **code distance `d`** (roughly, the minimum number of physical errors needed to cause an undetected logical error) determines the tradeoff: larger `d` means more physical qubits per logical qubit, but — **only if the physical error rate is below the code's threshold** — exponentially lower logical error rate. This "below threshold" condition is exactly what Google's Willow chip demonstrated experimentally for the first time in 2026: increasing `d` measurably *reduced* the observed logical error rate, confirming the theory holds in practice on real, noisy hardware rather than only in simulation or in principle.

---

## Build it from scratch

The T1/T2 decay model and the full bit-flip repetition code — encode, inject error, extract syndrome, correct — verified above with real numbers:

```python
import numpy as np

# T1/T2 decay
T1, T2 = 100e-6, 80e-6
for t in [1e-6, 10e-6, 50e-6, 100e-6]:
    p_decay = 1 - np.exp(-t / T1)
    coherence = np.exp(-t / T2)
    # matches the table above exactly

# 3-qubit bit-flip repetition code
zero, one = np.array([1, 0]), np.array([0, 1])
a, b = 0.6, 0.8
encoded = np.zeros(8)
encoded[0] = a   # |000>
encoded[7] = b   # |111>

X = np.array([[0, 1], [1, 0]])
I = np.eye(2)
X_on_q1 = np.kron(np.kron(I, X), I)   # bit-flip error injected on the middle qubit
errored = X_on_q1 @ encoded            # -> nonzero at |010> (idx 2) and |101> (idx 5)

def bits(idx, n=3):
    return [(idx >> k) & 1 for k in reversed(range(n))]

for idx in np.nonzero(errored)[0]:
    b_ = bits(idx)
    z0z1 = b_[0] ^ b_[1]
    z1z2 = b_[1] ^ b_[2]
    # both errored basis states give syndrome (1,1) -> "qubit 1 flipped"

corrected = X_on_q1 @ errored   # apply the same X again to correct (X is self-inverse)
assert np.allclose(corrected, encoded)   # True -- exact recovery, a,b never touched
```

Every number in "How it actually works" is this exact code's output.

---

## How it's done in production

Today's hardware runs **error mitigation**, not full error correction — a critical distinction that gets blurred constantly and shouldn't be:

| Technique | What it does | Limitation |
|---|---|---|
| Zero-noise extrapolation | Runs the same circuit at artificially amplified noise levels, extrapolates back to the zero-noise limit | Overhead (multiple circuit runs) grows with circuit size; doesn't scale to arbitrarily long computations |
| Readout-error mitigation | Characterizes and classically corrects for measurement-error bias in the final counts | Only fixes measurement error, not gate/decoherence error accumulated during the circuit |
| Dynamical decoupling | Inserts carefully-timed pulse sequences during idle qubit periods to average out slow environmental noise | Helps with idle-qubit dephasing specifically, not gate errors |
| Probabilistic error cancellation | Statistically cancels known error channels by sampling from a quasi-probability distribution | Sampling overhead grows exponentially with circuit depth/error rate — a hard scaling wall |

**Error mitigation is a NISQ-era stopgap, not a substitute for error correction.** Every mitigation technique above trades increased *classical* post-processing or repeated-run overhead for improved apparent fidelity, and every one of them has overhead that grows (often badly) with circuit size — none of them provide the *structural*, scalable guarantee the threshold theorem gives real error correction. This is the practical version of the theory distinction covered above, and it's the one that actually determines what's deployable today versus what remains a research target.

| Symptom | Cause | Fix |
|---|---|---|
| A circuit that works at small scale degrades sharply as qubit count or depth increases | Accumulated gate error and decoherence exceeding the coherence budget — a NISQ-era hardware limit, not a bug | Reduce circuit depth, apply error mitigation, or accept the result is only valid at small scale until fault-tolerant hardware exists |
| A vendor claims "N physical qubits" as evidence of near-term useful computation | Conflating physical qubit count with logical (error-corrected) qubit count — routinely off by 2-3 orders of magnitude | Ask specifically: how many *logical* qubits, at what logical error rate, sustained for how long — physical qubit count alone answers nothing about useful computation |
| Error mitigation "stops working" past a certain circuit size on a mitigation-based workflow | Sampling/repetition overhead for techniques like probabilistic error cancellation grows exponentially with circuit depth or error rate | Recognize this as mitigation's fundamental scaling ceiling, not a configuration problem — true error correction, not more aggressive mitigation, is the only path past it |
| A surface-code demonstration reports a specific logical error rate without stating code distance or physical error rate | Incomplete reporting — logical error rate alone is meaningless without knowing the `d` and physical error rate it was measured at | Always ask for physical error rate, code distance, and confirmation of below- vs above-threshold behavior when evaluating an error-correction claim |

---

## Tradeoffs & when NOT to use it

- **Don't plan production deployment of module 3's algorithms on current hardware.** Nothing in this module changes that conclusion — 2026's genuine below-threshold and 12-logical-qubit milestones are real engineering progress, not evidence that Shor's algorithm at cryptographically relevant scale, or deep VQE/QAOA circuits at useful problem sizes, are runnable today.
- **Don't treat physical qubit count as a meaningful progress metric on its own.** The physical-to-logical ratio (hundreds to low thousands per logical qubit, at current error rates) is the number that actually matters, and it's the number vendor announcements most often omit.
- **Don't confuse error mitigation with error correction when evaluating a near-term roadmap.** Mitigation is real, useful, and deployed today, but its overhead scaling means it cannot substitute for structural error correction at the circuit sizes real algorithms need — a roadmap that relies on "better mitigation" indefinitely, rather than a transition to fault tolerance, is not a credible path to the algorithms in module 3.
- **Do invest now in understanding this material for evaluating claims and planning migrations that don't depend on quantum hardware timelines.** Module 7's post-quantum cryptography migration is the concrete example: the *right* action today doesn't wait for a fault-tolerant machine to exist, because the threat model (harvest-now-decrypt-later) and the migration timeline are both driven by considerations independent of exactly when hardware crosses the required threshold.

---

## Interview questions

### Q1 — Define T1 and T2, and state the relationship between them.
**Testing:** the two basic noise timescales, correctly distinguished.
**Answer:** `T1` is the energy relaxation time (`|1⟩→|0⟩` decay, `P(relaxed by t)=1−e^{-t/T1}`). `T2` is the dephasing time (loss of relative-phase coherence, `e^{-t/T2}` remaining). `T2 ≤ 2T1` always — a fundamental bound, not an engineering limitation.
**Follow-up trap:** *"If a vendor reports T1=200µs but doesn't mention T2, what should you assume?"* — nothing favorable; `T2` could be as low as a small fraction of `2T1` depending on the dominant noise sources (charge noise, flux noise, etc.), and since `T2` often bounds circuit fidelity for phase-sensitive algorithms just as much as `T1` does, an incomplete report should be treated as a red flag, not benignly ignored.

### Q2 — What does "NISQ" stand for, and what does it actually bound?
**Testing:** whether the term is understood as a specific technical constraint, not a vague "early days" label.
**Answer:** Noisy Intermediate-Scale Quantum (Preskill, 2018) — tens to low-thousands of physical qubits, no error correction, and performance jointly bounded by gate error accumulation and the coherence-time budget (`T1`/`T2`) covered above. It specifically does *not* mean "not many qubits yet" — a device can have thousands of physical qubits and still be firmly NISQ if none of them are error-corrected.
**Follow-up trap:** *"Does having more physical qubits automatically move a device out of the NISQ regime?"* — no; moving out of NISQ requires *error correction* (logical qubits below threshold), which is a qualitatively different achievement than simply adding more noisy physical qubits — a 10,000-physical-qubit NISQ device is still NISQ if it has zero logical, error-corrected qubits.

### Q3 — Why was quantum error correction believed by some to be fundamentally impossible before 1995?
**Testing:** the historical pain point, connected to the no-cloning theorem from module 2.
**Answer:** Classical error correction relies on redundant copies and majority voting, but the no-cloning theorem forbids copying an unknown quantum state, and the obvious alternative — directly measuring a qubit to check for errors — collapses any superposition it was in, destroying the information you're trying to protect.
**Follow-up trap:** *"So how did Shor and Steane actually get around this?"* — they showed you can measure **syndromes** (specific stabilizer operators) that reveal which error occurred without revealing the encoded logical state itself, because the syndrome measurement gives the same outcome regardless of whether the logical qubit is in `|0⟩_L`, `|1⟩_L`, or any superposition — this is the exact mechanism verified directly in this module's repetition-code example, where the syndrome uniquely identified the error location without ever touching `a` or `b`.

### Q4 — Encode `0.6|0⟩+0.8|1⟩` in the 3-qubit bit-flip code, inject an X error on the middle qubit, and show how the syndrome identifies it.
**Testing:** the mechanical, numerical core of this module.
**Answer:** Encoded: `0.6|000⟩+0.8|111⟩`. After `X` on qubit 1: `0.6|010⟩+0.8|101⟩`. Measuring the parity checks `Z0Z1` and `Z1Z2` on both nonzero basis states gives `(1,1)` in both cases — a syndrome pattern unique to "qubit 1 flipped" among the three possible single-qubit-flip locations. Applying `X` to qubit 1 again exactly restores `0.6|000⟩+0.8|111⟩`, with `0.6` and `0.8` never measured or revealed at any point.
**Follow-up trap:** *"Does this code protect against a Z error on any qubit?"* — no, and this is the critical limitation: this code's syndrome is entirely insensitive to phase-flip (`Z`) errors, which pass through completely undetected. Full protection requires a separate phase-flip code (the same construction in the Hadamard-rotated basis) combined with the bit-flip code — Shor's original 9-qubit code nests both.

### Q5 — What is a "code distance," and why does increasing it only help below a certain physical error rate?
**Testing:** the threshold concept, the single most consequential idea in this module.
**Answer:** Code distance `d` roughly measures the minimum number of physical errors needed to cause an undetected logical error — larger `d` uses more physical qubits per logical qubit. Below the code's error threshold (surface codes: roughly ~1% physical two-qubit gate error), increasing `d` *exponentially decreases* the logical error rate. Above threshold, the opposite happens: adding more physical qubits (more opportunities for error) makes the logical error rate *worse*, not better — more qubits only help once you're already below the crossover point.
**Follow-up trap:** *"How would you know, from experimental data, whether a given device is below or above threshold?"* — measure logical error rate as a function of code distance `d`; a device below threshold shows logical error rate *decreasing* as `d` increases, while a device above threshold shows it *increasing*. This is exactly what Google's Willow chip demonstrated in 2026 — the first real-hardware confirmation of decreasing logical error rate with increasing `d`, which is the operational definition of "below threshold" being satisfied in practice, not just claimed.

### Q6 — A vendor announces a "4,000-qubit quantum computer." What's the single most important follow-up question?
**Testing:** the physical-vs-logical distinction, applied directly to a realistic claim.
**Answer:** "How many of those are logical, error-corrected qubits, and at what logical error rate?" Physical qubit count and logical qubit count commonly differ by two to three orders of magnitude given current physical-to-logical ratios (hundreds to low thousands of physical qubits per logical qubit) — a 4,000-physical-qubit NISQ device could plausibly have zero fault-tolerant logical qubits, and the announcement alone doesn't distinguish "4,000 noisy qubits" from "a handful of fault-tolerant logical qubits," which are wildly different engineering achievements.
**Follow-up trap:** *"Isn't a large physical qubit count still meaningful progress even without error correction?"* — yes, genuinely — physical qubit count, connectivity, and gate fidelity are all real prerequisites for eventually building error-corrected logical qubits, and NISQ-scale experiments do produce real research value (calibration data, algorithm prototyping, near-term applications with tolerance for noise). The point isn't that physical qubit count is meaningless, only that it's not a substitute for the logical-qubit metric when the question is "can this run module 3's algorithms at meaningful scale."

### Q7 — What's the practical difference between error mitigation and error correction, and why can't mitigation substitute for correction indefinitely?
**Testing:** a distinction routinely blurred in casual conversation about "fixing quantum noise."
**Answer:** Error mitigation (zero-noise extrapolation, readout-error correction, dynamical decoupling, probabilistic error cancellation) statistically or classically compensates for noise on today's uncorrected NISQ hardware, without any structural encoding of the quantum information across redundant physical qubits. Error correction (the stabilizer/syndrome approach in this module) structurally protects the encoded state and, per the threshold theorem, scales to arbitrarily long computations given a physical error rate below threshold. Mitigation techniques' overhead (extra circuit runs, sampling cost) generally grows — sometimes exponentially — with circuit size or error rate, so they hit a hard scaling wall that structural error correction, by design, does not.
**Follow-up trap:** *"If mitigation has a scaling wall, why is it used at all instead of just building error-corrected hardware now?"* — because full fault-tolerant hardware isn't available yet at any useful scale (this entire module's conclusion), so mitigation is the only tool available today for extracting any useful signal from noisy hardware in the interim — it's a genuinely useful stopgap for near-term, small-scale work, just not a long-term substitute for the transition to error correction that module 3's algorithms actually require.

### Q8 — Explain, precisely, why correcting only the discrete errors X, Y, and Z is sufficient to correct arbitrary continuous single-qubit errors.
**Testing:** staff-level depth on a genuinely subtle and important result, not just pattern-matching "quantum error correction handles noise."
**Answer:** Any single-qubit error operator can be written as a linear combination of the identity and the three Pauli matrices, `I, X, Y, Z` (they form a basis for `2×2` Hermitian, and more generally all, matrices). Combined with the discreteness quantum measurement imposes — a syndrome measurement projects any error (even one that was a continuous, arbitrary perturbation) onto one of a discrete set of outcomes corresponding to which Pauli-type error occurred — correcting the finite set `{I,X,Y,Z}` on each physical qubit turns out to correct the entire continuum of possible small perturbations, not just those four specific operators.
**Follow-up trap:** *"Does this mean quantum error correction handles ANY error, including correlated multi-qubit errors or non-Markovian noise?"* — no, and this is an important boundary: the discretization argument covers arbitrary *single-qubit* errors on qubits treated independently; codes and thresholds are typically analyzed under specific noise-model assumptions (often local, independent errors), and correlated errors across multiple physical qubits, or noise with memory (non-Markovian), can violate those assumptions and degrade real performance below what an idealized independent-error threshold calculation predicts — real hardware noise characterization has to check which regime actually applies.

### Q9 — Why do surface codes dominate current practical implementations over codes with theoretically better overhead, like quantum LDPC codes?
**Testing:** current, nuanced awareness of the real architecture tradeoff, not a stale "surface codes are simply the best" answer.
**Answer:** Surface codes need only 2D nearest-neighbor connectivity, matching how superconducting chips are physically fabricated and laid out, and have a comparatively high, well-characterized fault-tolerance threshold. Quantum LDPC codes can theoretically achieve much better physical-to-logical qubit ratios, but typically require longer-range or higher-connectivity interactions that current hardware architectures don't natively support well — the overhead advantage on paper doesn't automatically translate into a practical advantage given real hardware constraints.
**Follow-up trap:** *"Is this settled in favor of surface codes long-term, or still an open competition?"* — genuinely open; this module's lineage section flags it explicitly as an active, unresolved architecture bet, not a settled outcome. Whether hardware connectivity evolves to better support LDPC-style codes, or surface codes' overhead disadvantage is mitigated by other advances, remains a live research and engineering question as of 2026.

### Q10 — Design check: a team wants to plan a 5-year roadmap assuming fault-tolerant quantum computers capable of breaking RSA-2048 will exist by year 3, based on "below-threshold error correction was demonstrated in 2026." Evaluate this planning assumption.
**Testing:** synthesizing the whole module into a real risk/planning judgment — exactly the staff-level question this material exists to answer.
**Answer:** The premise (below-threshold error correction demonstrated in 2026) is accurate, but the inference is not supported: below-threshold demonstrations to date involve small numbers of logical qubits (Microsoft/Quantinuum's 12, at a modest logical error rate) sustained for short computations, while breaking RSA-2048 requires an estimated hundreds of thousands to roughly a million physical qubits' worth of resources (module 3) sustained through a long, deep circuit — a gap of several more orders of magnitude in scale and reliability beyond what's been demonstrated. A defensible planning assumption uses the *falling resource-estimate trend* (module 3's point about algorithmic improvements) and *industry-stated roadmaps* (IBM's "useful advantage by end of 2026" for narrower workloads) as inputs, while treating "cryptographically relevant fault tolerance by year 3" as one plausible but far from certain scenario among a wide range of expert estimates (module 3 cited a range from roughly 5 to 30 years).
**Follow-up trap:** *"Given that uncertainty, does that mean post-quantum migration planning should wait for more clarity on hardware timelines?"* — no, and this is precisely the pivot to module 7: migration timelines for cryptographic infrastructure are driven by data sensitivity duration and how long real-world migrations actually take (often years, for large organizations), not by pinning down the exact year a quantum computer becomes capable — the "harvest now, decrypt later" threat model means data encrypted today with vulnerable algorithms is already at risk regardless of when decryption capability arrives, which argues for migration planning now, independent of resolving this module's hardware-timeline uncertainty.

---

## Red flags that fail you

- Treating physical qubit count as equivalent to, or a good proxy for, logical/error-corrected qubit count.
- Confusing error mitigation (statistical, NISQ-era, doesn't scale to arbitrary circuit size) with error correction (structural, scalable per the threshold theorem).
- Not knowing the 3-qubit repetition code protects only against bit-flip errors, or being unable to explain the syndrome-without-state-collapse mechanism.
- Claiming "more qubits always means less error" without the below-threshold qualifier.
- Treating any current hardware milestone (12 logical qubits, below-threshold demonstrations) as evidence that module 3's algorithms are runnable at meaningful scale today.
- Not knowing what NISQ stands for or conflating it with "any early-stage quantum hardware" rather than the specific no-error-correction constraint.

---

## Cheat card

```
T1 (relaxation): P(decayed by t) = 1 - e^(-t/T1). T2 (dephasing): coherence = e^(-t/T2).
  ALWAYS T2 ≤ 2·T1. Typical superconducting order: T1~100µs, T2~80µs.
  Circuit runtime must stay well under this budget -- NISQ circuit depth is bounded by it.
NISQ (Preskill, 2018) = Noisy Intermediate-Scale Quantum: tens-to-low-thousands qubits, NO error
  correction, bounded by gate error + coherence budget. More physical qubits != leaving NISQ.
NO-CLONING blocks classical-style redundancy-based error correction (module 2).
SHOR/STEANE (1995-96) INSIGHT: measure STABILIZERS (syndrome) -- reveals WHICH error occurred
  WITHOUT revealing the encoded state (syndrome outcome same for |0>_L, |1>_L, any superposition).
3-QUBIT BIT-FLIP CODE: a|0>+b|1> -> a|000>+b|111>. Syndrome = Z0Z1, Z1Z2 parities, uniquely
  locates a single X error. PROTECTS X ERRORS ONLY -- Z (phase-flip) errors pass through undetected.
  Verified: 0.6|000>+0.8|111>, X-error on qubit1, syndrome(1,1), corrected exactly, a,b never measured.
DISCRETIZATION OF ERRORS: correcting {I,X,Y,Z} suffices to correct ARBITRARY continuous single-qubit
  errors (any error = linear combo of Paulis; measurement discretizes which one occurred).
SURFACE CODE: 2D nearest-neighbor lattice, threshold ~1% physical 2-qubit gate error. BELOW
  threshold: larger code distance d -> EXPONENTIALLY lower logical error rate (verified on real
  hardware for the first time: Google Willow, 2026). ABOVE threshold: more qubits makes it WORSE.
PHYSICAL:LOGICAL QUBIT RATIO ~ hundreds to low thousands per logical qubit at current error rates.
  IBM Kookaburra ~4,158 physical qubits != anywhere near 4,158 usable logical qubits.
  MS/Quantinuum H2: 12 logical qubits, ~2-in-1000 logical error rate (March 2026) -- genuine milestone.
ERROR MITIGATION (ZNE, readout correction, dynamical decoupling, prob. error cancellation) = NISQ-era
  STOPGAP, overhead grows (sometimes exponentially) with circuit size -- NOT a substitute for
  structural error CORRECTION, which scales per the fault-tolerance THRESHOLD THEOREM (1996).
```

## Sources

- [Preskill, J. — Quantum Computing in the NISQ era and beyond (2018)](https://arxiv.org/abs/1801.00862) — accessed 2026-08-08
- [Shor, P. — Scheme for reducing decoherence in quantum computer memory (1995)](https://journals.aps.org/pra/abstract/10.1103/PhysRevA.52.R2493) — accessed 2026-08-08
- [Fowler, A. et al. — Surface codes: Towards practical large-scale quantum computation (2012)](https://arxiv.org/abs/1208.0928) — accessed 2026-08-08
- [Quantum Computing Milestones 2026 — Technerdo (Google Willow below-threshold, Microsoft/Quantinuum 12 logical qubits, IBM Kookaburra/Nighthawk)](https://www.technerdo.com/blog/quantum-computing-milestones-2026) — accessed 2026-08-08
- [5 Key Quantum Computing Breakthroughs in 2026 — bqpsim.com](https://www.bqpsim.com/blogs/quantum-computing-breakthroughs) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
