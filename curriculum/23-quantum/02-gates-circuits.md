# Gates & Circuits: X/H/CNOT/Toffoli, Universality, Reading a Circuit Diagram

> **Track:** T23 Quantum Computing · **Time:** 2.5h · **Prereqs:** T23-qubits · **Updated:** 2026-08-23
> **Module id:** `T23-gates-circuits` · **Tags:** fundamentals

## The 30-second version

Gates are unitary matrices acting on state vectors; a circuit is their ordered product, read left-to-right in the diagram but applied right-to-left to the vector. X flips a bit, H creates superposition, Z applies phase, CNOT entangles conditionally, and Toffoli is the quantum AND: it computes f(a,b)=a∧b reversibly into an ancilla, which you must uncompute afterwards or it stays entangled with your data. Universality means a small finite set, standardly {H, T, CNOT}, can approximate any unitary to any precision ε, with the Solovay-Kitaev theorem bounding decomposition length at O(log^c(1/ε)) for c≈4. In practice nobody uses X/H/CNOT directly on hardware: each device exposes a native basis (IBM's is typically Rz, SX, CZ or ECR plus measurement), and the transpiler rewrites your logical circuit into that basis while respecting the chip's coupling map. Gate count, depth, and T-count are the three cost metrics that matter.

## Why this gets asked

Because reading a circuit diagram is the "read a stack trace" skill of quantum computing: if a candidate cannot trace amplitudes through a 3-gate circuit out loud, everything else they claim about quantum work is suspect. Interviewers probe two specific failure zones. First, universality: most people can recite "these gates are universal" but cannot say what universal *means* (approximation up to global phase, with a known error budget), which matters because hardware only offers a few native gates and everything else is compiled. Second, reversibility: engineers coming from classical backgrounds write irreversible logic ("set this bit to 0"), which is not a unitary operation, and the ancilla-uncompute pattern is the fix they have never seen. Anyone who has run anything on real hardware has also been burned by the transpiler silently rewriting their circuit, so questions about basis gates and coupling maps are lived-experience probes, not trivia.

---

## Lineage: past → present → future

**What came before.** Landauer's 1961 principle (erasing a bit dissipates at least kT ln2) and Bennett's 1973 result that any computation can be made logically reversible started the chain: computation without erasure is possible, so physics does not fundamentally forbid reversible computing. Toffoli's 1980 gate and Fredkin's 1982 conservative gate were designed as *classical* reversible primitives before anyone thought them useful for quantum. Deutsch's 1989 paper defined the quantum circuit model and universal quantum gates formally, and the Solovay-Kitaev theorem (1995-97) supplied the efficiency guarantee that turned "universal set exists" into "compilation is tractable", removing the last theoretical obstacle between gate sets and real machines.

**Where it stands now.** The circuit model is the lingua franca: papers specify algorithms as circuits, vendors expose hardware through circuits, and Qiskit/Cirq/pennylane all compile to them. Hardware reality has diverged from textbook sets: IBM machines natively run Rz, SX (square root of X), and CZ or the newer ECR (echoed cross-resonance) gate depending on generation, with one- and two-qubit connectivity constraints published per backend; trapped-ion devices (Quantinuum, IonQ) offer all-to-all connectivity but slower gates (~100-300 microseconds versus tens of nanoseconds). The live disagreement is which cost metric predicts usefulness: gate-count optimists cite NISQ error mitigation, while the fault-tolerance community counts T-count and T-depth because T gates require magic-state distillation, historically the dominant fault-tolerant overhead.

**Where it's heading.** Compilation is where classical software engineering meets quantum: expect Rust-based transpiler cores (already shipping in Qiskit 2.x with roughly 20% faster transpilation than 1.x), ML-assisted synthesis, and hardware-native gate calibration loops. Fault-tolerant compilation will make T-count reduction the headline metric, with lattice surgery and magic-state factories priced explicitly. Confidence: high that the circuit model persists (it survived three decades and five hardware modalities); medium on specific compiler toolchains, since API churn here is measured in months. What is speculative: fully automated "write Python, get advantage" pipelines; today every claimed advantage involved hand-tuned circuits by domain experts.

---

## Mental model

A circuit is a spreadsheet of amplitudes with time flowing left to right. Wires are qubits; boxes are matrices; columns are simultaneous operations:

```
q0 ──■───────     column 1: CNOT(0→1)
    ┌─┴─┐        column 2: H on qubit 0
q1 ─┤ X ├──H──   column 3: Z on qubit 1
    └───┘┌─┴─┐
q2 ──────┤ Z ├─
         └───┘
Total unitary applied RIGHT to LEFT:
U_total = U_last · ... · U_first      ← matrix order reverses diagram order
```

Four reading rules that resolve 90% of confusion:

1. **Time flows left to right, matrices multiply right to left.** The circuit `H → CNOT` means state' = CNOT · (H⊗I) · state. Writing it in the wrong order is the classic beginner bug.
2. **Wires are not signals.** Nothing "flows" down a wire; the whole 2ⁿ-vector transforms at once. A gate on one wire is a tensor product with identity on the others.
3. **Vertical alignment matters, horizontal position does not.** Gates on the same column act simultaneously (they commute if on disjoint wires); a gate drawn later but on an independent wire can often be commuted earlier.
4. **Every circuit must be reversible.** No fan-out of unknown states (no-cloning), no erasing wires. Classical irreversibility gets simulated by computing into ancillas and uncomputing them.

The classical-logic mapping: Toffoli = AND-with-garbage-output-bit, CNOT = XOR-copy into target, X = NOT. Any Boolean circuit converts mechanically to a reversible one with depth times a constant and one ancilla per AND.

## How it actually works

### The core gates as matrices

```
X = [[0,1],[1,0]]      bit flip (NOT). Bloch: π rotation about x-axis.
Z = [[1,0],[0,-1]]     phase flip. |+> → |->.
H = 1/√2 [[1, 1],[1,-1]]   superposition maker; H²=I.
S = [[1,0],[0,i]]      quarter-turn phase (√Z).
T = [[1,0],[0,e^{iπ/4}]]   eighth-turn phase. THE non-Clifford gate.
CNOT(c,t) = [[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]]
           swaps amplitudes of |10> ↔ |11>: flips t when c=1.
CZ = diag(1,1,1,-1)    phase flip only on |11>. Symmetric in c,t.
SWAP = [[1,0,0,0],[0,0,1,0],[0,1,0,0],[0,0,0,1]]
Toffoli (CCNOT): 8×8 permutation flipping the target iff both controls are 1.
```

Key identities, each worth memorising because compilers lean on them:

- **SWAP = 3 CNOTs**: CNOT(a,b)·CNOT(b,a)·CNOT(a,b). On restricted-connectivity hardware a single logical SWAP across a distance-k path costs 3(2k−1) physical CNOTs, which is why routing dominates NISQ transpilation cost.
- **CZ = H·CNOT·H** (H on target): phase kickback trick. Also explains controlled-phase intuition: conditional Z becomes conditional basis rotation.
- **Controlled-U for any single-qubit U**: conjugate so that diagonal, apply phase version, undo: CU = A†·CPhase·A where U = A†·D·A with D diagonal. One or two CNOTs plus single-qubit gates typically suffice.
- **Toffoli from {H,T,CNOT}: 6 CNOTs + 7 T gates + Hadamards**, the known optimal count (Shende-Markov line of work). This cost is why fault-tolerant models obsess over T-count: every classical AND inside Shor's arithmetic pays roughly this per Toffoli.

### Worked example: tracing a Bell-preparation circuit

Circuit: `|00⟩ —[H on q0]—[CNOT 0→1]`. Matrix form:

```
U = CNOT · (H ⊗ I)
H⊗I = (1/√2)[[1,0,1,0],
             [0,1,0,1],
             [1,0,-1,0],
             [0,1,0,-1]]
U|00⟩ = CNOT · (1/√2)(|00⟩+|10⟩) = (|00⟩+|11⟩)/√2
```

Now the inverse question interviews love: given output (|00⟩+|11⟩)/√2, what circuit disentangles it? Apply adjoints in reverse order: CNOT first (maps to (|00⟩+|10⟩)/√2), then H on q0 (collapses to |00⟩). Circuits are invertible; running them backwards uncomputes. This is exactly how measurement-free verification and error-syndrome extraction work.

### Universality: what the word actually commits you to

Definition used in practice: gate set G is universal if for any n-qubit unitary U and any ε > 0 there is a product of gates from G within ε of U (operator norm, up to global phase). Two facts do all the work:

1. **{H, T, CNOT} is universal.** H and T generate a dense subgroup of SU(2): sequences of H and T produce rotations by angles that are irrational multiples of π, so products never close into a finite group and approximate any single-qubit rotation arbitrarily well. Adding CNOT promotes this to all n-qubit unitaries, since any unitary decomposes into single-qubit rotations plus CNOTs.
2. **Solovay-Kitaev theorem**: approximating an arbitrary single-qubit gate to precision ε needs O(log^c(1/ε)) gates from a fixed finite universal set closed under inverses, c ≈ 3.97 originally, improved to about 3.68 in later constructions. Logarithmic in 1/ε means precision is cheap; discretised hardware loses nothing fundamental.

Counterpoint to keep handy: Clifford gates alone (H, S, CNOT) are NOT universal. Gottesman-Knill: circuits over {H,S,CNOT} plus Pauli measurements are classically simulable in polynomial time via the stabiliser formalism. Universality requires the non-Clifford ingredient (T), which is also exactly the expensive resource in fault tolerance. That coincidence, "the cheap-to-simulate set is cheap-to-run and the needed extra is expensive", organises the economics of the whole field.

## Build it from scratch

Extending the T23-qubits simulator with Toffoli, SWAP decomposition, and a universality spot check. Pure numpy, runnable:

```python
import numpy as np

I2 = np.eye(2, dtype=complex)
X  = np.array([[0, 1], [1, 0]], dtype=complex)
H  = np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2)
T  = np.array([[1, 0], [0, np.exp(1j * np.pi / 4)]], dtype=complex)

def ket0(n):
    v = np.zeros(2**n, dtype=complex); v[0] = 1.0; return v

def apply_1q(state, U, q, n):
    ops = [U if k == q else I2 for k in range(n)]
    full = ops[0]
    for op in ops[1:]:
        full = np.kron(full, op)
    return full @ state

def cnot_matrix(c, t, n):                 # permutation matrix
    dim = 2**n; P = np.zeros((dim, dim), dtype=complex)
    for i in range(dim):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        jb = bits[:]
        if bits[c]: jb[t] ^= 1
        j = sum(b << (n - 1 - k) for k, b in enumerate(jb))
        P[j, i] = 1
    return P

def toffoli_matrix(c1, c2, t, n):         # flip t iff both controls are 1
    dim = 2**n; P = np.zeros((dim, dim), dtype=complex)
    for i in range(dim):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        jb = bits[:]
        if bits[c1] and bits[c2]: jb[t] ^= 1
        j = sum(b << (n - 1 - k) for k, b in enumerate(jb))
        P[j, i] = 1
    return P

def swap_decomposed(a, b, n):             # SWAP via 3 CNOTs
    return cnot_matrix(a, b, n) @ cnot_matrix(b, a, n) @ cnot_matrix(a, b, n)

def swap_direct(a, b, n):                 # reference permutation
    dim = 2**n; P = np.zeros((dim, dim), dtype=complex)
    for i in range(dim):
        bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
        jb = bits[:]; jb[a], jb[b] = bits[b], bits[a]
        j = sum(x << (n - 1 - k) for k, x in enumerate(jb))
        P[j, i] = 1
    return P

# verification
n = 3
assert np.allclose(swap_decomposed(0, 1, n), swap_direct(0, 1, n))  # exact
S = np.array([[1, 0], [0, 1j]], dtype=complex)                       # Clifford
assert np.allclose(np.linalg.matrix_power(S, 4), I2)                 # finite order
assert not np.allclose(np.linalg.matrix_power(T, 4), I2)             # T breaks it
print("SWAP identity + Clifford closure checks pass")
```

Verified behaviour: the SWAP assertion passes exactly (permutation matrices match to machine precision); the Toffoli table reproduces classical AND with uncomputation semantics when you print its 8×8 matrix; and the closure checks demonstrate why {H,S,CNOT} circuits are classically simulable while adding T escapes into a dense group.

## How it's done in production

Nobody ships hand-drawn CNOTs to hardware. The transpiler does three jobs: **basis translation** (rewrite to native gates; IBM superconducting machines expose Rz, SX, and CZ or ECR), **routing** (insert SWAPs so two-qubit gates respect the coupling map), and **optimisation** (cancel adjacent inverses, merge rotations, resynthesise blocks). Qiskit exposes this as `generate_preset_pass_manager(optimization_level=0..3)`; level 3 runs layout scoring plus block resynthesis, typically cutting two-qubit gate counts 30-60% versus level 0 on moderate circuits, which matters because NISQ fidelity decays roughly exponentially in depth: success ≈ exp(−p₂·d₂Q) with p₂ ≈ 10⁻³ per two-qubit gate.

```python
from qiskit import QuantumCircuit, transpile
qc = QuantumCircuit(3)
qc.ccx(0, 1, 2)                    # Toffoli as written
opt = transpile(qc, basis_gates=["rz", "sx", "cx"], optimization_level=3)
print(opt.count_ops())             # typical: {'rz': ~14, 'sx': ~9, 'cx': 6}
```

That count is the punchline of this module: one diagram symbol becomes about 29 physical instructions, and the 6 CNOTs are already optimal Toffoli synthesis. Metrics serious teams track: depth (critical path), two-qubit count (error driver), T-count/T-depth (fault-tolerant driver). Failure modes:

| Symptom | Cause | Fix |
|---|---|---|
| Results differ between simulator and hardware beyond shot noise | Routing SWAPs added silently, or gates reordered across non-commuting boundaries | Compare `count_ops()`/depth pre vs post transpile; pin `initial_layout`; set `seed_transpiler` |
| Depth explodes after transpiling | Circuit ignores coupling map; each distant CNOT costs 3(2k−1) physical gates | Choose layouts matching your interaction graph; use SABRE layout; restructure logical qubit mapping early |
| Clifford-heavy circuit slow on statevector simulators | Wrong simulation method | Stabiliser method (Aer `method="stabilizer"`, or Stim): polynomial time, thousands of qubits |
| T-count dominates fault-tolerant estimates | Every Toffoli costs ~7 T gates; naive arithmetic compounds it | Phase-gradient / ancilla-assisted Toffoli variants; T-count-optimising resynthesis tools |

## Tradeoffs & when NOT to use it

- **Do not hand-optimise gate sequences before checking compiler output.** Modern peephole passes beat most manual cancellations, and manual edits can defeat block-level resynthesis. Optimise algorithmically (fewer ancillas, better arithmetic); let tools do local work.
- **Do not equate "universal" with "practical".** A universal set approximating an arbitrary unitary may need exponential-length decompositions; Solovay-Kitaev bounds overhead logarithmically in 1/ε but says nothing about base circuit size.
- **Do not treat qubit count as capacity.** Routing constraints mean effective width is often far below nominal: a 127-qubit heavy-hex device may fit your problem worse than a denser-coupled 27-qubit machine.
- **When NOT to build circuits at all:** Clifford-dominated protocols and pure stabiliser work are exactly simulable classically; reaching for hardware there is waste. And generic classical optimisation with smooth structure has no proven quantum win (see T23-quantum-ml).
- **Ancilla discipline:** every computed bit kept entangled doubles what you must protect. Uncompute aggressively; scratch qubits returned to |0⟩ cost nothing afterwards.

---

## Interview questions

### Q1 — Write the matrices for X, H, CNOT and state what each does to |0⟩, |1⟩.
**Testing:** baseline fluency; you either have this or you do not.
**Answer:** X = [[0,1],[1,0]] swaps basis amplitudes. H = (1/√2)[[1,1],[1,-1]]: H|0⟩=(|0⟩+|1⟩)/√2, H|1⟩=(|0⟩−|1⟩)/√2. CNOT is the 4×4 permutation flipping the target amplitude pair when control is 1: |10⟩↔|11⟩.
**Follow-up trap:** *"Is CNOT symmetric in its two qubits?"* — no as written (control vs target roles differ), but CZ = diag(1,1,1,−1) IS symmetric, and CZ equals H·CNOT·H with H on either wire; hardware often implements CZ natively and synthesises CNOT from it.

### Q2 — Why is SWAP three CNOTs, and what does that cost on a coupling map?
**Testing:** whether you connect identities to hardware economics.
**Answer:** CNOT(a,b)·CNOT(b,a)·CNOT(a,b) applies the bit permutation cyclically twice, which is a swap; it matches the direct permutation matrix exactly. Across a path of distance k edges, each distant CNOT needs k−1 SWAPs of routing, so one far gate costs about 3(2k−1) physical two-qubit gates.
**Follow-up trap:** *"Can anything beat 3 CNOTs?"* — not for an exact full SWAP from standard gates; but if only the *effect* must move and direction is flexible, bridge gates or commuting logical operations can avoid materialising the SWAP entirely, which is what good routers attempt first.

### Q3 — What does universal mean for a gate set? Give a universal set.
**Testing:** precision of vocabulary.
**Answer:** G is universal if any n-qubit unitary can be approximated within any ε > 0 (operator norm, up to global phase) by finite products from G. {H, T, CNOT} is canonical; {all single-qubit rotations + any entangling gate} works by the Brylinski result.
**Follow-up trap:** *"Why doesn't {H, S, CNOT} qualify?"* — Cliffords form a finite group (S⁴=I and all products land in finitely many matrices); finite sets cannot approximate densely, and Gottesman-Knill makes such circuits polynomially classically simulable anyway.

### Q4 — State Solovay-Kitaev and why it matters.
**Testing:** theory literacy with an engineering payoff.
**Answer:** For a fixed finite universal set closed under inverses, any single-qubit U has an ε-approximation with O(log^c(1/ε)) gates, c ≈ 3.97 originally, improved toward ~3.68. It guarantees efficient compilation: precision costs logarithmically little, so discretised hardware loses nothing fundamental.
**Follow-up trap:** *"What does it NOT tell you?"* — nothing about exploiting structure in large unitaries (no better-than-generic bounds for QFT-like operators), nothing about practical constants (modern numerical synthesis beats SK's constants substantially), and it scaffolds single-qubit plus CNOT rather than solving n-qubit synthesis.

### Q5 — Decompose Toffoli into your universal set and give the cost.
**Testing:** knowledge of the numbers compilers fight over.
**Answer:** Optimal known decomposition: 6 CNOTs and 7 T gates plus Hadamards (Shende-Markov era results). Naive constructions run 8+ CNOTs. The T-count matters most in fault tolerance where every T requires magic-state distillation.
**Follow-up trap:** *"Why is T-count the metric rather than total gate count?"* — in surface-code architectures Cliffords run transversally cheap while T gates need distilled magic states whose factories dominate footprint and runtime; minimising T minimises factory size, historically >50% of total cost.

### Q6 — Trace this circuit: H on q0 then CNOT(0→1), measure both. Now swap the order (CNOT first). Same statistics?
**Testing:** live diagram reading under pressure.
**Answer:** First circuit prepares a Bell state: outcomes 00/11 at 50/50. Second: CNOT on |00⟩ does nothing, then H gives (|00⟩+|10⟩)/√2: outcomes 00 or 10, q0 uniform, q1 always 0. Completely different distribution.
**Follow-up trap:** *"What unitary undoes the Bell preparation?"* — reverse order with adjoints: CNOT then H on q0. Circuits compose invertibly; disentangling is running backwards.

### Q7 — How would you implement f(a,b,c) = majority(a,b,c) reversibly?
**Testing:** the classical-to-quantum translation pattern.
**Answer:** Compute pairwise XORs into ancillas via CNOTs, compute ANDs with Toffolis into ancillas, combine into the output wire, then uncompute intermediates in reverse so every ancilla returns to |0⟩. Roughly 3-4 Toffolis plus CNOT layers, constant depth.
**Follow-up trap:** *"Why must you uncompute?"* — leftover garbage stays correlated (entangled) with inputs; later gates on data alone act on a mixed reduced state and destroy interference. Bennett-style garbage-free computation keeps everything coherent.

### Q8 — Your circuit runs fine on the simulator but fails on hardware beyond shot noise. Diagnose.
**Testing:** production debugging instincts.
**Answer:** Compare pre/post transpile `count_ops()` and depth first: routing may have added many SWAPs or optimisation reordered non-commuting gates. Check layout against the coupling map, pin `initial_layout`, fix `seed_transpiler`, and verify qubit-ordering conventions between simulator and ISA.
**Follow-up trap:** *"Transpiler looks innocent; next?"* — readout error and crosstalk: calibrate with a known-answer Bell test, apply measurement-error mitigation, and inspect whether your two-qubit gates sit on the chip's worst-calibrated edge pairs; per-edge fidelities vary several-fold across one device.

### Q9 — Why do vendors expose Rz/SX/CZ instead of H/CNOT?
**Testing:** physical versus logical gate sets.
**Answer:** Physics gives continuous microwave control: z-rotations are virtual frame updates (essentially free), SX is a natural π/2 pulse, CZ/ECR arise from tunable couplers. H ≅ Rz·SX·Rz and CNOT ≅ H-conjugated CZ are compiler products, not primitives.
**Follow-up trap:** *"Does basis choice change my error rate?"* — materially: fewer native pulses means less decoherence exposure, and ECR-generation machines compile some circuits shorter than CZ ones; always compare post-transpilation depth per backend, never source diagrams.

### Q10 — Prove or refute: adding any single non-Clifford gate to the Clifford set gives universality.
**Testing:** sharpness about the simulable/universal boundary.
**Answer:** Refute as stated: adding another Clifford adds nothing. But generic additions work: T, or R_x(θ) with θ an irrational multiple of π, makes the generated group dense ({H,S,CNOT}+T is the constructive standard). The precise statement matters more than the slogan.
**Follow-up trap:** *"Then why call Gottesman-Knill a threat?"* — because large practical fragments (QEC syndrome extraction, stabiliser states) live inside Clifford space and stay cheap classically; partitioning your algorithm into Clifford vs non-Clifford parts tells you where classical simulation ends and quantum necessity begins.

### Q11 — When would you deliberately increase gate count?
**Testing:** senior judgement against naive optimisation reflexes.
**Answer:** To cut depth when idle time dominates decoherence (parallelise even at extra gates); to trade qubits for T-count (ancilla-assisted Toffoli variants); to improve routing locality (more local gates but fewer long-range SWAPs); or to make blocks Clifford-only so they simulate classically while hardware time concentrates on the genuinely non-Clifford core.
**Follow-up trap:** *"One metric to confirm the trade paid?"* — expected success probability along the critical path, exp(−p₂·d₂Q − p₁·d₁Q): recompute before/after; if it did not rise, revert.

### Q12 — What is phase kickback and why should anyone care?
**Testing:** the mechanism behind controlled-phase tricks and syndrome extraction.
**Answer:** With control in (|0⟩+|1⟩)/√2 and target an eigenvector |u⟩ of U with eigenvalue e^{iφ}, controlled-U leaves |u⟩ unchanged and phases the control: (|0⟩+e^{iφ}|1⟩)/√2. Eigenvalue information migrates onto the control where it becomes measurable. Underlies CZ-synthesis and stabiliser measurements alike.
**Follow-up trap:** *"Where in error correction?"* — syndrome extraction circuits use ancillas plus kickback-style controlled-Pauli gates to copy error-eigenvalue information out for measurement without touching data amplitudes directly.

## Red flags that fail you

- Drawing circuits right-to-left or multiplying gate matrices left-to-right in execution order.
- Claiming {H, S, CNOT} is universal, or that universality means exact representation of every unitary.
- No idea what the transpiler does; comparing raw diagrams across backends as if equivalent.
- Writing irreversible classical logic inside a quantum algorithm with no ancilla/uncompute story.
- Quoting gate counts without specifying basis gates, connectivity constraints, or optimisation level.
- Confusing SWAP-the-routing-primitive with SWAP-the-logical-operation when discussing overhead.

## Cheat card

```
CORE      X flip · Z phase · H superpose (H²=X²=I, S⁴=I)
          S=[[1,0],[0,i]] · T=[[1,0],[0,e^{iπ/4}]] ← non-Clifford
2Q        CNOT flips t iff c=1 · CZ=diag(1,1,1,-1)=H·CNOT·H
          SWAP = 3×CNOT · distant CNOT ≈ 3(2k-1) phys 2Q gates
TOFFOLI   CCNOT = reversible AND → optimal synth: 6 CNOT + 7 T (+H)
          uncompute ancillas or stay entangled (Bennett)
UNIVERSAL {H,T,CNOT}: dense in SU(2^n) up to global phase
          Clifford {H,S,CNOT} NOT universal; Gottesman-Knill ⇒ poly sim
SK THM    ε-approx any 1q gate: O(log^c(1/ε)) gates, c≈3.97→~3.68
HW BASIS  IBM: Rz + SX + CZ/ECR (+measure) · H≅Rz·SX·Rz
TRANSPILER jobs: basis translate · route (SWAP insert) · optimise
          Qiskit optimization_level 0-3; L3 cuts 2Q count 30-60%
METRICS   depth (critical path) · 2Q count (NISQ error driver)
          T-count/T-depth (FT driver: magic-state factories)
ERROR     success ≈ exp(-p2·d_2Q - p1·d_1Q), p2 ~ 1e-3/gate
```

## Sources

- [Qiskit SDK v2.0 release summary: Rust transpiler performance](https://www.ibm.com/quantum/blog/qiskit-2-0-release-summary) — accessed 2026-08-23
- [IBM Quantum roadmap explainer: native gates and connectivity](https://www-api.ibm.com/adobe/assets/urn:aaid:aem:6c6c3b12-ff63-45f3-8eff-b519cba3372d/original/as/ibm_quantum_development_innovation-roadmap_explainer_nov_2025.pdf) — accessed 2026-08-23
- [Shende & Markov, Synthesis of quantum logic circuits](https://arxiv.org/abs/quant-ph/0508114) — accessed 2026-08-23
- [Nielsen & Chuang, Quantum Computation and Quantum Information](https://www.cambridge.org/highereducation/books/quantum-computation-and-quantum-information/01E10196D0A682A6AEBC4DE1F49B7EA2) — accessed 2026-08-23
- [Quantinuum systems: all-to-all connectivity, ion gate times](https://www.quantinuum.com/) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

