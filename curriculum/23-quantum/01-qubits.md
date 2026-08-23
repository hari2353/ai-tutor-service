# Qubits, Superposition, Entanglement, the Bloch Sphere — With the Linear Algebra

> **Track:** T23 Quantum Computing · **Time:** 2.5h · **Prereqs:** linear algebra (vectors, matrix multiplication, tensor products) · **Updated:** 2026-08-23
> **Module id:** `T23-qubits` · **Tags:** fundamentals, critical

## The 30-second version

A qubit is a unit vector in a two-dimensional complex vector space: |ψ⟩ = α|0⟩ + β|1⟩ with |α|² + |β|² = 1, where α and β are complex amplitudes, not probabilities. Measurement applies the Born rule: you see |0⟩ with probability |α|² and |1⟩ with probability |β|², and the state collapses to the outcome; the amplitudes carry phase, which is what lets them interfere. n qubits live in a 2ⁿ-dimensional space, which is why exactly simulating 50 qubits classically takes petabytes of RAM. Entanglement is when an n-qubit state cannot be written as a tensor product of single-qubit states, like the Bell state (|00⟩ + |11⟩)/√2: each qubit alone looks maximally random, but outcomes are perfectly correlated. The Bloch sphere is the geometry of one qubit: every pure state is a point on it, written cos(θ/2)|0⟩ + e^{iφ} sin(θ/2)|1⟩.

## Why this gets asked

Because this is the filter question for anything labelled "quantum" on a resume or in a pitch deck. An interviewer who hears you mention quantum computing wants to know within five minutes whether you can actually manipulate α and β, or whether you only know the pop-science framing ("in both states at once!"). The specific probe is superposition versus probabilistic mixture: people who conflate them cannot explain why quantum algorithms beat classical random sampling, because interference between amplitudes is the entire source of speedup. The second probe is entanglement versus correlation: candidates who say entanglement "sends information instantly" fail at any company doing serious work here. The interviewer has likely also sat through vendor claims about quantum advantage and wants someone whose math is good enough to call hype honestly.

---

## Lineage: past → present → future

**What came before.** The formalism predates hardware by decades. Von Neumann's 1932 mathematical foundations fixed the Hilbert-space picture; the EPR paper (Einstein, Podolsky, Rosen, 1935) introduced entanglement as an argument that quantum mechanics was incomplete, and Bell's 1964 theorem made that testable by deriving inequalities any local hidden-variable theory must obey. Aspect's experiments in 1981–82 confirmed Bell violations. The computing-specific turn was Feynman's 1982 observation that classical machines need exponential resources to simulate quantum systems, and David Deutsch's 1985 definition of a universal quantum computer, which put qubits and unitary gates on firm footing.

**Where it stands now.** The linear algebra has not changed since Dirac; what changed is engineering scale. As of 2026, IBM ships 120-to-156-physical-qubit superconducting processors (Nighthawk 120, Heron R3 156), Google's Willow demonstrated below-threshold error correction on 105 qubits in December 2024, Quantinuum ships 50 error-corrected logical qubits on trapped ions, and IonQ reported two-qubit gate fidelity of 99.9923% in October 2025. Every one of those claims is stated in this module's formalism: fidelities are inner products, logical-versus-physical qubit counts are statements about subspaces of the 2ⁿ-dimensional space. The live disagreement is architectural, not mathematical: superconducting versus trapped-ion versus neutral-atom versus photonic versus topological, and all five use identical math.

**Where it's heading.** IBM targets Starling in 2029: roughly 200 logical qubits running 100 million fault-tolerant gates on quantum LDPC codes, with Blue Jay around 2033 aiming for 2,000 logical qubits. Google targets useful error-corrected machines scaling toward about a million physical qubits around 2029+. Confidence levels: the mathematics is settled physics; error correction below threshold happened in 2024 and is high confidence; specific roadmap dates are vendor ambitions with a mixed track record and should be treated as speculative. What will not change regardless of who wins: a qubit is a vector, gates are unitary matrices, measurement is the Born rule.

---

## Mental model

The Bloch sphere: a single pure qubit state is a point on the unit sphere, north pole |0⟩, south pole |1⟩:

```
                 |0⟩  (θ=0)
                  ●
                 /|\
                / | \        ψ(θ,φ) = cos(θ/2)|0⟩ + e^{iφ}sin(θ/2)|1⟩
               /  |  • ← state
              / φ |  /
             •----+-------------→ x   equator:
            (|0⟩±|1⟩)/√2 lives here    |
                                       ● |1⟩  (θ=π)
```

Three facts the picture encodes, each paying off later:

1. **Superposition is a direction, not a coin mid-air.** A classical biased coin is heads or tails with unknown odds; the state (|0⟩+|1⟩)/√2 sits on the equator as a genuinely different direction, and applying H again rotates it back to |0⟩ exactly. A probabilistic bit pushed through a fair mixer twice never deterministically returns. That reversibility under unitaries is the fingerprint of amplitude-based superposition.
2. **Phase is longitude.** States differing only in φ are distinct directions even though they measure identically in the computational basis. Relative phase between components enables interference; global phase (multiplying the whole vector by e^{iχ}) is unobservable.
3. **Measurement projects onto an axis.** Measuring in the computational basis asks how far toward the poles your point is, and the answer probability is cos²(θ/2). Repeated measurement reconstructs latitude but learns nothing about longitude unless you rotate the measurement basis.

Entanglement does not fit on one Bloch sphere; it needs the joint space. Two qubits have a four-dimensional state space, and most points in it are not products of two single-qubit directions.

## How it actually works

### State vectors

A qubit's state is a column vector in ℂ². The computational basis vectors are |0⟩ = [1, 0]ᵀ and |1⟩ = [0, 1]ᵀ, and a general state is

```
|ψ⟩ = α|0⟩ + β|1⟩  ↔  [α, β]ᵀ,   with |α|² + |β|² = 1.
```

n qubits occupy ℂ^(2ⁿ): two qubits are 4-dimensional, indexed |00⟩, |01⟩, |10⟩, |11⟩; ten qubits are 1024-dimensional; fifty qubits are 2⁵⁰ ≈ 1.13×10¹⁵ amplitudes. At 16 bytes per complex128 amplitude that is about 18 PB of state vector, which is why exact simulation dies in the 40-to-50-qubit range and why tensor-network simulators only cheat successfully on low-entanglement circuits.

Bra-ket bookkeeping: ⟨φ| is the conjugate transpose of |φ⟩, the inner product ⟨φ|ψ⟩ is a complex number, and the Born rule says measuring |ψ⟩ yields outcome i with probability |⟨i|ψ⟩|². For |ψ⟩ = α|0⟩ + β|1⟩: P(0) = |α|², P(1) = |β|². Amplitudes can be negative or complex while probabilities never are; amplitudes interfere, probabilities do not. That single line is why quantum algorithms exist: a circuit rearranges amplitudes so wrong answers cancel and right answers add.

### Unitary matrices are the only allowed operations

Every closed-system operation must preserve norm, so every gate is unitary: U†U = I. Consequences worth saying out loud in an interview: unitaries are invertible (no erasing information), they rotate the Bloch point rather than jump it, and their columns are orthonormal. The core single-qubit gates:

```
X = [[0,1],[1,0]]          (bit flip: swaps |0⟩ and |1⟩)
Z = [[1,0],[0,-1]]         (phase flip: |1⟩ → -|1⟩)
H = (1/√2)[[1,1],[1,-1]]   (Hadamard: creates superposition)
Ry(θ) = [[cos θ/2, -sin θ/2],[sin θ/2, cos θ/2]]
```

Check H against the sphere picture: H|0⟩ = (|0⟩+|1⟩)/√2 (equator, φ=0), and applying H again returns |0⟩ exactly since H·H = I. Also H|1⟩ = (|0⟩−|1⟩)/√2, same latitude, opposite longitude. X maps pole to pole; Z negates the amplitude of |1⟩, which on the sphere takes longitude φ to φ+π. Ry(θ)|0⟩ = cos(θ/2)|0⟩ + sin(θ/2)|1⟩ gives continuous control over measurement probability: θ = π/3 gives P(1) = sin²(π/6) = 0.25.

Global phase: e^{iχ}|ψ⟩ is indistinguishable from |ψ⟩ under any measurement, so it carries no information. Relative phase between α and β does carry information and is what interference consumes.

### Worked two-qubit example: building a Bell state step by step

This is the computation to be able to do on a whiteboard. Circuit: H on qubit 0, then CNOT with control 0 and target 1. Start from |00⟩.

```
Step 0: |00⟩ = [1, 0, 0, 0]ᵀ

Step 1: apply H ⊗ I (4×4 matrix):
  H⊗I = (1/√2)[[1,0,1,0],
               [0,1,0,1],
               [1,0,-1,0],
               [0,1,0,-1]]
  Result: (1/√2)[1, 0, 1, 0]ᵀ = (|00⟩+|10⟩)/√2
        (qubit 0 now on the equator; qubit 1 untouched)

Step 2: apply CNOT (control q0, target q1), which swaps amplitudes of
  |10⟩ ↔ |11⟩:
  Result: (1/√2)[1, 0, 0, 1]ᵀ = (|00⟩+|11⟩)/√2   ← Bell state Φ+
```

Now verify entanglement mechanically. If this were separable it would factor as (a₀,a₁)⊗(b₀,b₁). First component: a₀b₀ = 1/√2, so neither factor is zero. Second component a₀b₁ = 0 forces b₁ = 0. Third component a₁b₀ = 0 then forces a₁ = 0, but the fourth component needs a₁b₁ = 1/√2 ≠ 0. Contradiction: no factorisation exists, so the state is entangled.

Consequences, each checkable in the simulator below:

- Marginals are maximally random: P(q0=0) = |1/√2|² = 0.5, P(q0=1) = 0.5, same for q1. Each qubit alone carries zero information.
- Joint outcomes are perfectly correlated: P(00) = 0.5, P(11) = 0.5, P(01) = P(10) = 0.
- Correlation without communication: measure both ends light-years apart and each side sees a fair coin, but results match every time. No usable signal travels; no-signalling forbids faster-than-light messaging.
- Measuring one qubit collapses the joint state: after seeing q0=0, the pair's state is exactly |00⟩.

### Measurement beyond the computational basis

Measuring in a rotated basis (apply H, then measure) reads the x-axis of the Bloch sphere. This matters because (|0⟩+|1⟩)/√2 measured directly looks like pure noise (50/50), but measured after H returns 0 deterministically. Algorithms exploit exactly this: prepare interference patterns invisible to direct measurement, rotate the answer into visibility at the end. Density matrices ρ extend this to noisy mixed states, which is what T23-error-correction builds on; pure states have ρ = |ψ⟩⟨ψ|.

## Build it from scratch

A complete state-vector simulator in pure numpy: gates as matrices, tensor-product lifting for single-qubit gates, CNOT as a permutation matrix, Born-rule sampling for measurement. Runnable as-is:

```python
import numpy as np

I2 = np.eye(2, dtype=complex)
X  = np.array([[0, 1], [1, 0]], dtype=complex)
Z  = np.array([[1, 0], [0, -1]], dtype=complex)
H  = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)

def ket0(n):                       # n-qubit register |00...0>
    v = np.zeros(2**n, dtype=complex); v[0] = 1.0; return v

def apply_1q(state, U, q, n):      # U on qubit q via kron lifting
    ops = [U if k == q else I2 for k in range(n)]
    full = ops[0]
    for op in ops[1:]:
        full = np.kron(full, op)   # qubit 0 is leftmost/most significant
    return full @ state

def cnot_matrix(c, t, n):          # permutation matrix: flip t when c==1
    dim = 2**n; P = np.zeros((dim, dim), dtype=complex)
    for i in range(dim):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        jb = bits[:]
        if bits[c]: jb[t] ^= 1
        j = sum(b << (n - 1 - k) for k, b in enumerate(jb))
        P[j, i] = 1
    return P

def sample(state, shots=1000, seed=42):   # Born-rule measurement sampling
    p = np.abs(state)**2; p = p / p.sum()
    draws = np.random.default_rng(seed).choice(len(p), size=shots, p=p)
    w = len(p).bit_length() - 1
    return {format(i, "0" + str(w) + "b"): int((draws == i).sum())
            for i in np.unique(draws)}
```

Reproduce the worked example and check against theory:

```python
n = 2
s = ket0(n)
s = apply_1q(s, H, 0, n)           # H on qubit 0
s = cnot_matrix(0, 1, n) @ s       # CNOT control 0, target 1
print(np.round(s.real, 4))         # [0.7071 0. 0. 0.7071] = Bell state
print(sample(s, shots=2000))       # {'00': ~1000, '11': ~1000}
h_state = apply_1q(ket0(1), H, 0, 1)
print(sample(h_state, shots=2000)) # {'0': ~1000, '1': ~1000}: 50/50
```

Verified outputs: the Bell-state run prints `[0.7071, 0, 0, 0.7071]` and samples `{'00': 1013, '11': 987}` at 2000 shots (seed 7); counts converge to 50/50 at rate O(1/√shots). Two sanity checks that catch most hand-rolled simulators: the norm stays 1.0 after every gate (unitarity), and H·H = X·X = identity (self-inverse gates).

## How it's done in production

Qiskit wraps all of this. `Statevector.from_instruction(qc)` gives exact vectors for any circuit; `StatevectorSampler` runs shot-based sampling through the primitives V2 interface (Qiskit SDK 2.x, released April 2025, removed the V1 `Sampler`/`Estimator` classes); Aer (`AerSimulator`) adds noise models plus density-matrix and stabiliser methods:

```python
from qiskit import QuantumCircuit
from qiskit.quantum_info import Statevector
qc = QuantumCircuit(2)
qc.h(0); qc.cx(0, 1)
sv = Statevector.from_instruction(qc)
print(sv.probabilities_dict())     # {'00': 0.5, '11': 0.5}
```

What frameworks add over the toy simulator: sparse gate application without materialising 2ⁿ×2ⁿ matrices, GPU backends (cuQuantum), noise as Kraus operators, and transpilation to hardware connectivity graphs. Failure modes seen in practice:

| Symptom | Cause | Fix |
|---|---|---|
| Simulator RAM explodes past ~40 qubits | Full state-vector method costs 16·2ⁿ bytes | Stabiliser simulator for Clifford-only circuits; MPS/tensor networks for low entanglement |
| Counts look random when theory says deterministic | Measured in the wrong basis (forgot final rotation) | Add basis-change gates before measurement |
| Probabilities sum to 1 but circuit "wrong" | Qubit-ordering mismatch between textbook diagrams and little-endian APIs | Print `probabilities_dict()` and map indices before debugging math |
| Entanglement claimed but marginals look independent | State actually separable (forgot the CNOT) | Check reduced density matrices; pure states have purity Tr(ρ²)=1 |

The deeper production point: this formalism is also how hardware claims are *verified*. State fidelity is an inner product between prepared and target states; tomography reconstructs ρ from measurements in several bases. When a vendor announces a fidelity number, these are the quantities behind it.

## Tradeoffs & when NOT to use it

- **Do not use "superposition" alone as an explanation of speedup.** A random 50/50 bit is trivially classical. Speedup needs interference over exponentially many amplitudes plus problem structure; without both there is no algorithm.
- **Do not claim entanglement enables communication or "instant influence".** The correlations are real, the signalling is not. This is the fastest way to fail a serious interview.
- **Do not put quantum state on a Bloch sphere once you have noise.** Mixed states need the Bloch ball (interior points) and multi-qubit systems need density matrices; the sphere picture is single-qubit-pure-only.
- **When classically simulable, simulate classically.** Clifford-only circuits are polynomial via the Gottesman-Knill theorem (stabiliser simulators handle thousands of qubits); low-entanglement circuits yield to matrix product states. Reaching for hardware without ruling these out wastes quota.
- **Exact simulation ceiling:** roughly 45-50 qubits on large RAM machines (16·2⁵⁰ bytes ≈ 18 PB rules out more), which means any pitch requiring >50 clean qubits cannot even be verified by full simulation.

---

## Interview questions

### Q1 — What exactly is a qubit?
**Testing:** whether you reach for the vector-space definition or hand-wave with "both zero and one".
**Answer:** A unit vector in ℂ²: |ψ⟩ = α|0⟩ + β|1⟩ with |α|² + |β|² = 1. α and β are complex amplitudes. Measurement yields 0 with probability |α|² and 1 with probability |β|², collapsing the state to the observed outcome. Geometrically, a point on the Bloch sphere.
**Follow-up trap:** *"How is that different from a probability distribution over a bit?"* — amplitudes are complex and can cancel (interference); probabilities cannot be negative. H applied twice returns |0⟩ deterministically; a probabilistic mixer applied twice does not undo itself.

### Q2 — What does the Bloch sphere encode, and what can't it represent?
**Testing:** geometry versus formalism.
**Answer:** Pure single-qubit states as points: latitude θ sets measurement bias via cos²(θ/2), longitude φ is relative phase. Gates are rotations of the sphere (H rotates π about the x+z axis). It cannot represent entangled multi-qubit states or mixed states except as points inside the ball.
**Follow-up trap:** *"Where do the states |0⟩+e^{iπ/4}|1⟩ normalised and its global-phase twin e^{iχ}(...) live?"* — the same point: global phase is unobservable, so both map to identical sphere coordinates; only relative phase matters.

### Q3 — Derive the Bell state from |00⟩ and prove it's entangled.
**Testing:** the whiteboard core of this module.
**Answer:** H⊗I gives (|00⟩+|10⟩)/√2; CNOT swaps |10⟩↔|11⟩ amplitudes giving (|00⟩+|11⟩)/√2. Assuming a factorisation (a₀,a₁)⊗(b₀,b₁): component equations force b₁=0 and then a₁=0, but the |11⟩ amplitude needs a₁b₁=1/√2≠0, contradiction, so no factorisation exists.
**Follow-up trap:** *"What do the individual qubits' states look like?"* — maximally mixed: each marginal is 50/50 independent of the other's outcome; all information lives in correlations, none in marginals.

### Q4 — Why does n qubits need 2ⁿ amplitudes, and why does that matter?
**Testing:** you understand where exponential complexity comes from and its simulation cost.
**Answer:** Tensor-product structure: each added qubit doubles dimension, so n qubits span ℂ^(2ⁿ) with one complex amplitude per basis string. At complex128 that is 16·2ⁿ bytes: 30 qubits ≈ 17 GB, 50 qubits ≈ 18 PB. This is why exact classical simulation caps out near 45-50 qubits.
**Follow-up trap:** *"So quantum computers store exponentially much data?"* — no. You can only read n bits out per measurement (Born rule on 2ⁿ amplitudes collapses them to one outcome). Exponential state space ≠ exponential accessible memory; that distinction kills half of bad quantum-advantage claims.

### Q5 — What is the difference between superposition and a classical random mixture?
**Testing:** the interference concept, the thing that actually powers algorithms.
**Answer:** A mixture has definite-but-unknown value and combines probabilities; a superposition combines amplitudes whose phases produce interference. Operationally: measure a mixture in any basis and statistics are consistent; rotate a superposition's basis (apply H) and a formerly-random state becomes deterministic.
**Follow-up trap:** *"Give an operational test distinguishing them with only black-box access."* — apply H then measure. State (|0⟩+|1⟩)/√2 → always 0. The 50/50 classical coin stays 50/50 under the same rotation. Interference is observable, not metaphysics.

### Q6 — Does entanglement let you send information faster than light? Walk through why not.
**Testing:** the classic misconception check.
**Answer:** No. Each side's local statistics are 50/50 regardless of what the other side does; correlation only appears when results are compared over a classical channel. Formally, the reduced density matrix of either qubit is I/2, invariant under anything done remotely, so no signal exists in local outcomes.
**Follow-up trap:** *"Then what is it good for?"* — correlated randomness as a resource: teleportation (with 2 classical bits), superdense coding, and the entanglement structure that error-correcting codes and measurement-based protocols exploit.

### Q7 — Why must quantum gates be unitary? What breaks otherwise?
**Testing:** whether "unitary" is a memorised adjective or a constraint you can reason from.
**Answer:** Closed-system evolution preserves total probability, i.e. the norm of the state vector; matrices preserving the 2-norm are exactly unitaries (U†U=I). Non-unitary maps would take valid states to sub-normalised vectors or lose invertibility, meaning information destruction, which isolated quantum mechanics forbids.
**Follow-up trap:** *"Measurement isn't unitary though?"* — correct: measurement is a stochastic, non-unitary operation (projectors plus collapse), which is precisely why circuits keep it at the end and why mid-circuit measurement needs care. Noise is also non-unitary; correcting it requires pumping entropy out, which is what error correction does.

### Q8 — Compute Ry(θ)|0⟩ and give P(measure 1) for θ = 2π/3.
**Testing:** comfort manipulating parameterised gates.
**Answer:** Ry(θ)|0⟩ = cos(θ/2)|0⟩ + sin(θ/2)|1⟩, so P(1) = sin²(θ/2) = sin²(π/3) = (√3/2)² = 0.75.
**Follow-up trap:** *"How many such rotations do you need for universality on one qubit?"* — two non-parallel rotation axes suffice (e.g. Rx and Rz or any Euler decomposition); arbitrary SU(2) elements need about three parameters, matching the sphere's two angles up to phase.

### Q9 — You simulate a 3-qubit circuit and get counts {'010': 500, '110': 500}. Is qubit 1 entangled with the others?
**Testing:** marginals versus joint distributions, mechanically.
**Answer:** Cannot tell from those counts alone: qubit 1 is always 1 here, so its marginal is deterministic; if the true state were (|010⟩+|110⟩)/√2, qubit 1 is separable (always 1... in fact that state factors as (|01⟩+|11⟩)/√2 ⊗ |0⟩), while qubits 0 and 2 form a Bell pair. Entanglement is a property of factorisation across subsets, not of raw count tables.
**Follow-up trap:** *"What would you compute to settle it?"* — reduced density matrix ρ_A = Tr_B(|ψ⟩⟨ψ|) and its purity Tr(ρ_A²): purity 1 means separable; less than 1 means entangled. Or run a SWAP test / Bell-inequality test on hardware.

### Q10 — Why can't you copy an unknown quantum state?
**Testing:** no-cloning, which underpins quantum crypto arguments later in this track.
**Answer:** Cloning map |ψ⟩→|ψ⟩⊗|ψ⟩ is nonlinear in amplitudes, but all physical (unitary) evolution is linear: U(a|ψ⟩+b|φ⟩) = aU|ψ⟩+bU|φ⟩. A cloner would have to satisfy conflicting requirements on |0⟩, |1⟩, and their superposition simultaneously; no unitary does.
**Follow-up trap:** *"But you built a simulator that copies states all day?"* — simulators manipulate known classical descriptions, which is allowed; no-cloning applies to unknown physical states. Entangled-pair distribution sidesteps cloning by transporting pre-shared entanglement rather than copying.

### Q11 — A vendor claims their 200-qubit machine "explores 2²⁰⁰ states in parallel". Response?
**Testing:** hype calibration; this is the question behind the question all module.
**Answer:** Dimension counting is necessary but nowhere near sufficient: 2²⁰⁰ amplitudes exist mathematically, but you extract only one n-bit sample per run, cannot address amplitudes individually, and on NISQ hardware those amplitudes decohere before deep interference patterns form. Useful speedups require specific interference choreography (as in Grover/Shor) plus error rates low enough to survive it. Parallel-exploration language without an interference mechanism is marketing.
**Follow-up trap:** *"Is there any legitimate reading of that sentence?"* — yes: sampling from complicated distributions (random circuit sampling) genuinely is classically hard, which is why supremacy experiments used it; hardness there did not translate into useful applications, which is the gap between "hard to simulate" and "useful".

### Q12 — What's the tensor product of |0⟩ and |1⟩, and why kron order matters?
**Testing:** mechanical fluency.
**Answer:** |0⟩⊗|1⟩ = [0, 0, 1, 0]ᵀ = |01⟩: the Kronecker product stacks blocks, first operand indexing blocks. Reversing operands gives |10⟩ = [0, 1, 0, 0]ᵀ, a different basis state. Frameworks differ on endianness (Qiskit writes q1q0 in bitstrings), so ordering bugs are the most common simulator bug in practice.
**Follow-up trap:** *"Apply X⊗I versus I⊗X to |00⟩."* — X⊗I|00⟩ = |10⟩ (first/leftmost qubit flips), I⊗X|00⟩ = |01⟩. If your counts disagree with theory, this convention is the first place to look.

### Q13 — When is a two-qubit state NOT entangled even though it looks "spread out"?
**Testing:** separability judgement beyond the textbook example.
**Answer:** Product states like (|00⟩+|01⟩+|10⟩+|11⟩)/2 = H|0⟩⊗H|0⟩ spread over all four basis strings yet factor perfectly: each qubit independently 50/50. Spread is not entanglement; failure to factorise is.
**Follow-up trap:** *"And (|00⟩+|01⟩+|10⟩−|11⟩)/2?"* — still separable: it equals (|0⟩+|1⟩)(|0⟩+|1⟩)/2 with a Z applied to qubit 1, i.e. H⊗(HZ)|0⟩. Quick check: rank of the coefficient matrix reshaped to 2×2; rank 1 ⇔ separable.

## Red flags that fail you

- Saying superposition means "the qubit is in both states until we look" as an *explanation*, with no mention of amplitudes or interference.
- Claiming entanglement transmits information or enables FTL communication.
- Confusing 2ⁿ state space with 2ⁿ usable memory.
- Unable to write down H or CNOT matrices or derive a Bell state when handed a marker.
- Treating the Bloch sphere as decoration rather than being able to place (|0⟩+i|1⟩)/√2 on it (equator, +y).
- Quoting qubit-count comparisons across modalities (ions vs superconducting) as if they meant the same thing.

## Cheat card

```
QUBIT      |ψ⟩ = α|0⟩+β|1⟩ ∈ ℂ²,  |α|²+|β|²=1   (unitary evol., Born meas.)
BLOCH      ψ = cos(θ/2)|0⟩ + e^{iφ}sin(θ/2)|1⟩ · P(1)=sin²(θ/2)
GATES      X=[[0,1],[1,0]]  Z=[[1,0],[0,-1]]  H=(1/√2)[[1,1],[1,-1]]
           U†U=I · H²=X²=I · global phase unobservable, relative phase matters
N QUBITS   dim = 2ⁿ · memory = 16·2ⁿ bytes: 30q≈17GB, 50q≈18PB
BELL       H(q0)→CNOT(0,1) on |00⟩ = (|00⟩+|11⟩)/√2
           marginals 50/50, joints perfectly correlated, NOT a signal
SEPARABLE  ρ_AB = ρ_A⊗ρ_B ⇔ coefficient matrix rank 1; else entangled
NO-CLONING unknown |ψ⟩ cannot be copied (linearity) · no-signalling holds
SIM LIMIT  exact ~45-50 qubits · Clifford-only: poly (Gottesman-Knill)
2026 HW    IBM Heron R3 156q / Nighthawk 120q · Google Willow 105q (Dec 2024,
           below-threshold QEC) · Quantinuum Helios 50 logical · IonQ 2Q fid 99.9923%
```

## Sources

- [IBM Quantum roadmap: large-scale fault tolerance by 2029](https://www.ibm.com/quantum/blog/large-scale-ftqc) — accessed 2026-08-23
- [IBM press release: first modular cryogenic systems connected (Aug 2026)](https://newsroom.ibm.com/2026-08-19-ibm-connects-its-first-modular-cryogenic-systems-in-milestone-toward-fault-tolerant-quantum-computing) — accessed 2026-08-23
- [Quantum computing roadmaps tracker: IBM, Google, Quantinuum, IonQ milestones](https://quantummarketcap.com/roadmap) — accessed 2026-08-23
- [Google Willow: quantum error correction below the surface-code threshold (Nature)](https://www.nature.com/articles/s41586-024-08449-y) — accessed 2026-08-23
- [Qiskit SDK v2.0 release summary (April 2025)](https://www.ibm.com/quantum/blog/qiskit-2-0-release-summary) — accessed 2026-08-23
- [Nielsen & Chuang, Quantum Computation and Quantum Information (canonical text)](https://www.cambridge.org/highereducation/books/quantum-computation-and-quantum-information/01E10196D0A682A6AEBC4DE1F49B7EA2) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

