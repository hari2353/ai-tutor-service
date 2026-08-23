# Quantum ML, VQE, QAOA — Genuine Promise vs Hype

> **Track:** T23 Quantum Computing · **Time:** 2h · **Prereqs:** T23-qubits, T23-algorithms · **Updated:** 2026-08-23
> **Module id:** `T23-quantum-ml` · **Tags:** ml

## The 30-second version

Three distinct things get called "quantum ML", and their credibility differs by orders of magnitude. **VQE** (variational quantum eigensolver) uses a parameterised circuit plus classical optimiser to approximate molecular ground-state energies; it is the most defensible near-term application because simulating quantum systems is exactly what quantum hardware is natively good at, though no advantage has been shown yet beyond toy molecules. **QAOA** applies the same hybrid loop to combinatorial optimisation (MaxCut, scheduling); it has provable approximation guarantees only asymptotically, loses empirically to good classical heuristics on every non-toy instance tested, and its promise rests on unproven structure discovery. **QML proper**, training circuits as classifiers on classical data, carries the heaviest burden of proof: gradients vanish exponentially ("barren plateaus") for deep random circuits, loading classical data into amplitudes requires hardware that does not exist, and dequantisation results plus the Fourier-series analysis of Schuld et al. explain why tested models reduce to limited classical function classes. The honest position for interviews: genuine scientific promise in quantum simulation, unproven bet in optimisation, and marketing-first evidence base in classical-data QML as of 2026.

## Why this gets asked

Because "quantum machine learning" appears on resumes and vendor decks at a rate wildly disproportionate to any demonstrated capability, and senior interviewers know the vocabulary but need to find out whether you can audit it. The probes are calibrated: ask how VQE handles a Hamiltonian and you learn whether someone can actually run the loop; ask what a barren plateau is and you learn whether they have read past abstracts; ask "compared to what baseline?" about a claimed speedup and you learn whether they will push back on hype, which is the actual job skill here. There is also a defensive motive: teams building classical ML infrastructure keep getting asked by executives whether to budget for quantum ML, and the useful answer requires separating the three families above, knowing that chemical accuracy means ~1.6 milli-Hartree (~4 kJ/mol), and being able to say plainly that no quantum model has beaten strong classical baselines on any practical dataset as of 2026.

---

## Lineage: past → present → future

**What came before.** Feynman's 1982 framing (quantum machines simulate quantum physics) implied the simulation family; variational methods entered with Peruzzo et al.'s VQE (2014), which ran on a photonic processor for HeH⁺, and Farhi et al.'s QAOA (2014) for optimisation, both designed explicitly for near-term noisy devices rather than fault-tolerant ones. The QML-on-data wave followed around 2018-2020: quantum kernels (Havlíček et al., Nature 2019), variational classifiers, and sweeping claims about exponential advantages. Then came the correction cycle: McClean et al. identified barren plateaus (Nature Communications 2018), Ewin Tang's 2019 dequantisation results reproduced headline quantum algorithms (recommendation systems, PCA-style tasks) classically in comparable time, gutting several claimed applications, and Schuld, Sweke, Meyer (2021) showed circuit models encode functions expressible as Fourier series in their input encoding, bounding what they can represent on classical data.

**Where it stands now.** The field has bifurcated. Simulation (VQE and descendants like VQE-with-error-mitigation, sample-based quantum diagonalisation) runs on real hardware for systems up to tens of qubits: FeMoco-style strongly correlated molecules remain the aspirational target where classical methods strain (DMRG/CCSD(T) scaling walls), while everything lighter falls to classical computational chemistry. Optimisation via QAOA shows mixed empirical results: at depth p≤3 on hardware, approximation ratios trail classical Goemans-Williamson-style algorithms and specialised heuristics on standard benchmarks; proponents pin hopes on deeper circuits plus problem-inspired ansätze. Classical-data QML has retreated to theory: careful papers now claim provable separations only for contrived datasets, and the influential groups themselves (Schuld, Killoran) publish increasingly sceptical analyses. Live disagreement: whether problem-informed ansatz design escapes barren plateaus at scale, and whether quantum feature maps offer anything kernel methods cannot dequantise.

**Where it's heading.** Confidence-weighted forecast: high confidence that quantum simulation reaches genuinely useful chemistry first, contingent on error correction (logical-qubit machines, post-2028 per roadmaps); medium confidence QAOA finds niche value on problems with native cost-Hamiltonian structure (Ising-type hardware constraints); low confidence in general-purpose QML beating deep learning, whose own scaling curve keeps moving. What would change my mind: a peer-reviewed result beating tuned classical baselines on a natural dataset with data-loading costs included. Nobody has produced one through mid-2026.

---

## Mental model

All three families share one loop; the difference is what the cost function measures and whether structure exists:

```
        ┌────────────────────────────────────────────┐
        │  θ  ──>  U(θ)|0>  ──>  measure ⟨C⟩ ± shot  │
        │   ▲                                        │
        │   │            classical optimiser         │
        │   └────── update θ ◄── gradient/COBYLA ◄───┘

VQE:    C = molecular Hamiltonian H     (physics structure exists)
QAOA:   C = problem cost (MaxCut edges) (structure hoped for)
QML:    C = classification loss         (usually no quantum structure)
```

The second picture is why training is hard: random deep parameterised circuits have gradients that concentrate exponentially around zero.

```
Var[∂⟨C⟩/∂θ] ~ O(1/2^n)          ← barren plateau (McClean et al. 2018)

cost landscape for n=20 qubits:
⟨C⟩ ┤_______________________~ flat to 2^-20 precision everywhere ~
    │      ╱╲                    except exponentially narrow ravines
    └────────────────────────────▶ θ     classical optimisers starve here
```

Third picture, the data bottleneck that audits most QML claims: encoding a 1000-dimensional classical vector into amplitudes needs log₂(1000) ≈ 10 qubits but a state-preparation circuit of depth ~2¹⁰ without QRAM; angle-encoding instead uses one gate per feature (depth scales with data), which caps expressivity. Either way the loading step eats the claimed speedup unless your data was born quantum, which is exactly true in chemistry and almost nowhere else.

## How it actually works

### VQE: variational eigensolver, mechanically

Goal: ground-state energy E₀ of Hamiltonian H. The Rayleigh-Ritz variational principle says every trial state gives E(θ) = ⟨ψ(θ)|H|ψ(θ)⟩ ≥ E₀, so minimising over θ squeezes toward the truth from above. The hybrid loop:

1. **Ansatz**: U(θ)|0⟩ with hardware-efficient gates (Ry/Rz layers + entanglers) or chemistry-inspired UCCSD-style circuits (physically motivated, deeper).
2. **Measurement**: decompose H into Pauli strings (chemistry Hamiltonians arrive as Σ c_i · P_i, typically O(n⁴) terms before grouping); measure each group's expectation from shots; statistical error per term scales 1/√shots.
3. **Optimise**: gradient-based (parameter-shift rule gives exact gradients from two circuit evaluations per parameter: ∂⟨C⟩/∂θ = [C(θ+π/2) − C(θ−π/2)]/2) or gradient-free (COBYLA/Nelder-Mead) under noise.

Concrete anchor numbers: chemical accuracy is 1.6 mHa (~4 kJ/mol); H₂'s ground energy is −1.137 Ha at equilibrium bond length 0.735 Å; VQE demonstrated chemical accuracy for H₂ on hardware back in 2016-17, and systems beyond ~50 electrons remain out of reach because ansatz depth and measurement counts blow up: naive shot budget for 1 mHa precision on an n-electron molecule runs to 10⁸-10⁹ shots per optimiser step before grouping tricks.

### QAOA: alternating cost and mixer layers

For MaxCut on graph G with cost Hamiltonian C = Σ_{(i,j)∈E} (1−ZᵢZⱼ)/2: prepare uniform superposition via Hadamards, then p repetitions of exp(−iγC) (diagonal phase separation) and exp(−iβB) with mixer B = Σ Xᵢ (uniform recombination). Measure; expectation of C approximates optimum as p grows, converging to the adiabatic result as p→∞. Known results to quote: worst-case approximation ratio tends to the classical guarantee asymptotically; at finite small p on real graphs, tuned classical heuristics win consistently; parameter landscapes concentrate for large regular graphs (transfer to good initial γ,β exists). The honest framing: QAOA is a research bet that depth-p circuits find problem structure classical algorithms miss, not a demonstrated method.

### Barren plateaus and the training wall

McClean et al.'s result: for random parameterised circuits of sufficient depth, gradient variance across parameters scales like 1/2ⁿ (more precisely O(1/poly(2ⁿ)) depending on architecture and cost locality). Consequences: for n=20 qubits, gradients live below 10⁻⁶ relative scale, so shot noise (1/√shots) drowns signal until shots reach astronomical values; for n≥50, training is effectively impossible for unstructured ansätze. Mitigations researched since: shallow/block-wise initialisation, layerwise training, problem-inspired ansätze preserving symmetry (number-preserving for chemistry), local cost functions. Each helps partially; none removes the fundamental tension between expressivity and trainability.

### The dequantisation lesson

Tang's 2019 results are the field's control group: several "exponential quantum speedups" for data analysis (recommendation, supervised clustering, PCA-flavoured tasks) assumed QRAM-style data access, and Tang showed classical algorithms with sampling-based access achieve polynomially similar runtime. Audit rule derived from this: any QML claim must specify how classical data enters the quantum state, count that circuit's cost, and compare against the best classical method given the same access assumptions. Applied rigorously, nearly all published advantages evaporate; Schuld's Fourier-series result adds the structural reason: data re-uploading circuits compute exactly multivariate trigonometric polynomials whose frequency spectrum is fixed by the encoding, a limited classical function class.

## Build it from scratch

VQE on a two-qubit molecular-hydrogen-style Hamiltonian, pure numpy: H = g₀·I + g₁·Z₀ + g₂·Z₁ + g₃·Z₀Z₁ + g₄·X₀X₁ (the standard reduced H₂ form), ansatz of Ry rotations plus an entangler, parameter-shift gradients, exact diagonalisation as ground truth. Runnable:

```python
import numpy as np

I2 = np.eye(2, dtype=complex)
Z  = np.diag([1, -1]).astype(complex)
X  = np.array([[0, 1], [1, 0]], dtype=complex)

def kron_all(*ops):
    out = np.array([[1.0]], dtype=complex)
    for op in ops:
        out = np.kron(out, op)
    return out

# Reduced H2 coefficients at equilibrium bond length (0.735 Angstrom)
g = [0.2252, 0.3435, -0.4347, 0.5716, 0.0910]
H = (g[0] * kron_all(I2, I2) + g[1] * kron_all(Z, I2)
     + g[2] * kron_all(I2, Z) + g[3] * kron_all(Z, Z)
     + g[4] * kron_all(X, X))

def ansatz_state(theta):
    """|psi(theta)> = CX(Ry(t1) (x) Ry(t0)) |00>, then XX-mixer absorbed in H."""
    def ry(t): return np.array([[np.cos(t/2), -np.sin(t/2)],
                                [np.sin(t/2),  np.cos(t/2)]], dtype=complex)
    U = kron_all(ry(theta[0]), ry(theta[1]))          # qubit order: (q1,q0)
    cx = np.eye(4, dtype=complex)                     # CNOT q0->q1
    perm = {(b1, b0): ((b1 ^ b0) & 1, b0) for b1 in (0, 1) for b0 in (0, 1)}
    P = np.zeros((4, 4))
    for (a1, a0), (c1, c0) in perm.items():
        P[c1 * 2 + c0, a1 * 2 + a0] = 1.0
    state = P @ U @ np.ones(4, dtype=complex) / 2.0   # |00> = uniform index 0
    return state

def energy(theta):
    s = ansatz_state(theta)
    return float(np.real(s.conj() @ H @ s))

def grad(theta, h=np.pi / 2):                          # parameter-shift rule
    gvec = np.zeros_like(theta)
    for i in range(len(theta)):
        tp, tm = theta.copy(), theta.copy()
        tp[i] += h; tm[i] -= h
        gvec[i] = (energy(tp) - energy(tm)) / 2
    return gvec

theta = np.zeros(2)
for step in range(200):
    theta -= 0.1 * grad(theta)
print("VQE ground energy :", round(energy(theta), 4))
print("Exact (numpy eigh):", round(float(np.linalg.eigvalsh(H)[0]), 4))
```

Verified behaviour: the loop converges from θ=(0,0) to E ≈ −1.1299, matching `eigvalsh`'s minimum exactly to 4 decimal places for these truncated coefficients (full-precision H₂ coefficients give the textbook −1.137 Ha at equilibrium). Swap the ansatz for `ry`-only (drop the entangler) and it plateaus above the true ground state, a one-line demonstration that entanglement is necessary, not decorative.

## How it's done in production

Nobody runs these on laptops; the toolchains are PennyLane (device-agnostic autodiff over circuits), Qiskit primitives + `qiskit-algorithms` (VQE/QAOA classes against Estimator/Sampler V2 interfaces), and cloud quantum lab services. A realistic production-shaped workflow today is simulation-first with hardware spot-checks:

```python
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp
from scipy.optimize import minimize

hamiltonian = SparsePauliOp.from_list(
    [("II", g[0]), ("ZI", g[1]), ("IZ", g[2]), ("ZZ", g[3]), ("XX", g[4])])
estimator = StatevectorEstimator()

def objective(params):
    job = estimator.run([(ansatz_circuit(params), hamiltonian)])
    return float(job.result()[0].data.evs)

res = minimize(objective, x0=[0.0, 0.0], method="COBYLA")
```

What production adds beyond the toy: measurement grouping (commuting Pauli terms share basis rotations, cutting shots several-fold), error mitigation layers (resilience levels), optimizer choice under noise (SPSA beats analytic gradient methods when shot noise dominates because it needs only 2 evaluations per step regardless of parameter count), and chemistry preprocessing (Hartree-Fock reference states, active-space reduction via classical packages like PySCF before anything touches a QPU). Failure modes seen repeatedly:

| Symptom | Cause | Fix |
|---|---|---|
| Optimiser returns initial point unchanged | Barren plateau: gradient signal below shot noise | Problem-inspired ansatz, layerwise training, symmetry-preserving circuits |
| Energy jitters between iterations worse than convergence step | Shot noise dominating small gradients | Increase shots adaptively near convergence; SPSA/COBYLA instead of Adam |
| Hardware energy far above simulator optimum | Noise biasing expectation upward (depolarisation inflates ⟨H⟩) | Error mitigation (ZNE), shorter-depth ansatz, verify on fake-backend sim first |
| Claimed speedup evaporates under review | Data-loading cost or weak classical baseline omitted | Count encoding circuit depth; benchmark against tuned classical (not sklearn defaults) |
| QAOA approximation ratio stuck ~0.9 at p≤2 | Depth too low for structure discovery; parameters generic | Warm-start from classical relaxation, concentrate parameters, accept it may not beat heuristics |

## Tradeoffs & when NOT to use it

- **Do not budget for QML on classical data today.** No published result beats strong classical baselines with honest data-loading accounting through mid-2026. If a vendor pitch cites a paper, run the three audits: baseline quality, data-entry cost, scaling beyond toy sizes.
- **Do use quantum simulation seriously if your business owns hard chemistry/materials problems**, but plan around post-error-correction timelines and keep classical computational chemistry (DFT, coupled-cluster, DMRG) as the workhorse; hybrid pipelines where quantum handles only strongly correlated active spaces are the credible shape.
- **QAOA deserves research curiosity, not production bets.** Where its cost Hamiltonian matches native hardware structure (annealers, Ising machines) there may be niches; against modern MILP/CP-SAT solvers on general instances, evidence says no.
- **When NOT to publish/train variational circuits at width:** beyond roughly 20-30 unstructured qubits, barren plateau mathematics makes training cost exceed any plausible benefit; if your experiment cannot train classically simulable widths, the hardware claim being tested is usually moot anyway.
- **The senior tell is asymmetry:** enthusiasm for simulation, scepticism toward optimisation/QML claims, willingness to say "this is a science project" about most of it. Interviews reward calibrated positions over cheerleading in both directions.

---

## Interview questions

### Q1 — Explain VQE to a classical ML engineer using their vocabulary.
**Testing:** translation ability; also checks you actually understand the loop.
**Answer:** It is empirical risk minimisation where the model is a parameterised quantum circuit, the "loss" is the expectation value of a molecular Hamiltonian (always an upper bound on the true ground energy by Rayleigh-Ritz), gradients come from the parameter-shift rule (two circuit evaluations per parameter, exact in theory), and the optimiser is classical (COBYLA/SPSA under shot noise). The data being exploited is naturally quantum: the Hamiltonian's eigenvalues.
**Follow-up trap:** *"Where does it beat gradient descent on GPUs?"* — nowhere yet: for H₂-class problems classical chemistry wins outright. The bet is systems where the Hamiltonian's Hilbert space grows so fast (strongly correlated transition-metal complexes, FeMoco) that classical exact methods hit combinatorial walls while a quantum processor represents the state natively.

### Q2 — What is a barren plateau and what causes it?
**Testing:** the central training obstacle; separates readers from practitioners.
**Answer:** For sufficiently deep random parameterised circuits, cost-function gradients concentrate exponentially near zero: Var[∂⟨C⟩/∂θ] ~ O(1/2ⁿ). Cause: high expressivity makes almost all directions indistinguishable at any fixed precision; with shot noise 1/√shots, signal vanishes below noise floor for n≥~20 unstructured qubits. Mitigations: symmetry-preserving/problem-inspired ansätze, shallow circuits, layerwise training.
**Follow-up trap:** *"Why doesn't this kill VQE for chemistry?"* — physically motivated ansatzes (UCCSD-style) stay near low-excitation manifolds where gradients survive; barren plateaus bite hardware-efficient random circuits hardest. The tradeoff is ansatz depth versus trainability, and it is quantitative, not binary.

### Q3 — Audit this claim: "Our quantum kernel gives 99% accuracy versus 97% classical SVM."
**Testing:** the hype-audit skill the module exists for.
**Answer:** Three questions before believing anything: What was the classical baseline (tuned kernel methods, gradient boosting, or defaults?), what did data encoding cost (angle encoding depth scales with features; amplitude encoding needs state-preparation circuits that erase the advantage), and does the separation survive on standard benchmarks or only curated splits? Published quantum-kernel advantages at scale do not exist as of 2026; Schuld's Fourier analysis bounds what these models express classically.
**Follow-up trap:** *"Could kernels still win somewhere?"* — conceivably on data with genuine quantum provenance (measuring quantum systems), where feature maps are natural rather than forced; that is a real research niche and completely different from claiming wins on tabular/image data.

### Q4 — State QAOA's actual guarantees and its honest empirical record.
**Answer:** Guarantee: asymptotically, p→∞ recovers adiabatic evolution's solution quality; worst-case approximation ratio matches best classical asymptotically. Empirics: at p≤3 on real hardware, approximation ratios trail Goemans-Williamson and tuned heuristics on MaxCut benchmarks; parameters concentrate helpfully for regular graphs but nothing beats classical solvers on practical instances through mid-2026.
**Follow-up trap:** *"Why do people keep working on it?"* — two live bets: native cost-Hamiltonian structure may suit quantum hardware the way MILP structure suits CP-SAT, and fault-tolerant depths might unlock behaviour invisible at NISQ depths. Both are unproven; funding reflects option value, not demonstrated advantage.

### Q5 — Why is quantum simulation considered the credible family when QML isn't?
**Answer:** Asymmetry of representation: molecules ARE quantum states, so a quantum register represents them with polynomial resources while classical simulation needs exponential ones (n spin-orbitals → 2ⁿ amplitudes). Classical-data QML lacks this: data enters via expensive encoding, and the target function classes are classically representable. The advantage argument is representational necessity versus contrived mapping.
**Follow-up trap:** *"Then why hasn't simulation won already?"* — error rates: useful chemistry needs logical qubits and deep fault-tolerant circuits; today's devices run toy active spaces that classical methods handle trivially. Timeline is gated on T23-error-correction progress, not algorithm discovery.

### Q6 — Derive the parameter-shift rule.
**Testing:** mechanical depth beyond buzzword recall.
**Answer:** For gates generated by Pauli operators with eigenvalues ±1 (Ry(θ)=e^{−iθY/2} etc.), expectation values are trigonometric polynomials of period 2π in θ: f(θ) = a·cos θ + b·sin θ + c. Two samples determine the derivative exactly: ∂f/∂θ = [f(θ+π/2) − f(θ−π/2)]/2. Cost: two circuit executions per parameter per step, hardware-compatible by construction.
**Follow-up trap:** *"What breaks under hardware noise?"* — shifts remain unbiased estimators of the noisy expectation, so gradients track the noisy landscape faithfully; the pathology is variance from shots, which is why SPSA's two-evaluation-per-step stochastic approximation often outperforms exact shifts when parameters number in the hundreds.

### Q7 — Your QAOA experiment's approximation ratio improves with depth until p=5 then degrades. Diagnose.
**Answer:** Most likely compounding gate noise swamping the signal: deeper circuits accumulate more error than the added optimisation power gains, so measured ⟨C⟩ diverges from the ideal circuit's value. Verify by simulating noiselessly at same depths (if improvement continues, hardware is the limit) and checking whether transpiled two-qubit counts grew superlinearly. Mitigate: error mitigation, better layouts, or accept the depth ceiling.
**Follow-up trap:** *"Could it be the optimiser instead?"* — yes: parameter landscapes develop local minima at higher p; distinguish by multi-start optimisation in simulation. Hardware-noise degradation shows as systematic bias toward worse costs even from good parameters.

### Q8 — Where do measurement costs explode in VQE, and how do practitioners fight back?
**Answer:** Chemistry Hamiltonians have O(n⁴) Pauli terms (two-electron integrals); each needs shots scaling as cᵢ²/ε² for precision ε, so naive budgets hit 10⁸-10⁹ shots per energy evaluation. Fights: grouping commuting terms into shared basis rotations (classical shadows and clique-cover methods cut measurements substantially), adaptive shot allocation weighted by coefficient magnitude, and classical preprocessing shrinking active spaces before anything reaches a QPU.
**Follow-up trap:** *"Is there a fundamental floor?"* — information-theoretically you must estimate enough observables to pin the energy to ε, giving Ω(poly(n)/ε²)-ish sampling lower bounds for general Hamiltonians; structure helps constants, not scaling. This is why chemical accuracy claims should always cite shot counts.

### Q9 — A startup pitches "quantum-enhanced feature maps" for your fraud model with exponential speedup. Your response memo?
**Answer:** Decline pending evidence: request the baseline comparison table with tuned classical competitors, the end-to-end latency including encoding circuits (each inference would need circuit execution at ~ms-to-s latencies plus queueing), and the theoretical separation result distinguishing their map from classical random features. Current literature supports neither the exponent nor the deployment story; if they cite Havlíček-style kernels, note those demonstrate separations on contrived distributions only.
**Follow-up trap:** *"Any circumstances you'd pilot?"* — as structured due-diligence: small paid benchmark against our strongest classical pipeline with pre-registered metrics, full data-cost accounting, and a kill criterion. Option value has a price; make it explicit and small.

### Q10 — What did Tang's dequantisation results actually prove, and why do they matter beyond specific papers?
**Answer:** That several claimed exponential quantum speedups for linear-algebra-on-data tasks (recommendation systems 2016-era, some PCA/regression variants) assumed quantum-accessible data structures (QRAM) and could be matched by classical sampling algorithms under equivalent access assumptions, in polylogarithmic-in-dimension time. Beyond killing those papers, they established the audit standard: access-model assumptions and data-loading costs are part of the complexity claim.
**Follow-up trap:** *"Do they touch Shor or Grover?"* — no: Shor needs no data loading (input is an integer) and Grover's oracle model already counts queries honestly. Dequantisation bites precisely where classical data masquerades as quantum-native, which is the QML pattern.

### Q11 — Contrast how you'd evaluate a VQE chemistry claim versus a QML classification claim.
**Answer:** VQE claim: check the molecule size and active space against classical state-of-the-art results for the same system (FCI/DMRG references exist), verify chemical accuracy definition (1.6 mHa), ask whether error mitigation was included and whether the ansatz can plausibly scale (systematic, size-consistent). QML claim: additionally demand the data-loading accounting and strong-baseline comparison; the prior here is scepticism because no scaled-up win exists. Same rigour, different priors grounded in representation arguments.
**Follow-up trap:** *"What single number most validates a VQE paper?"* — agreement with an independent classical high-precision method (FCI or experiment) within chemical accuracy for a system non-trivially sized, since self-reported convergence without external reference is how errors hide.

### Q12 — Design the decision memo: should your pharma employer fund a quantum chemistry program in 2026?
**Testing:** executive-level synthesis with calibrated uncertainty.
**Answer:** Recommend a bounded watch-and-pilot posture: core simulation work stays classical (DFT/coupled-cluster/DMRG pipelines); fund (a) one internal expert tracking hardware/error-correction milestones against published thresholds, (b) a small partnership pilot on one genuinely hard strongly-correlated active space where classical methods demonstrably strain, with pre-agreed success metrics versus DMRG baselines, and (c) explicit re-evaluation triggers keyed to logical-qubit roadmaps (IBM 2029 Starling-class). Budget as option purchase, not capability build; the science case is real, the timeline risk is large, and competitive intelligence alone justifies the modest spend.
**Follow-up trap:** *"What would falsify the program?"* — error-correction scaling stalling below threshold at distance ~7-9 through 2028, or classical methods (ML force fields, better DMRG variants) absorbing the target problem class first; either outcome means redeploying spend to compute infrastructure that compounds regardless.

## Red flags that fail you

- Presenting QML on classical data as a near-term advantage area with no caveats about barren plateaus or data loading.
- Unable to define chemical accuracy (~1.6 mHa) or explain why VQE is variational.
- No mention of classical baselines when discussing any quantum ML result.
- Treating QAOA's existence as evidence of optimisation advantage.
- Never having heard of dequantisation/Tang results or the Fourier-series limitation.
- The opposite failure too: dismissing quantum simulation wholesale because QML hype soured you; the representation argument for chemistry stands on its own.

## Cheat card

```
THREE FAMILIES   VQE (simulation: credible) · QAOA (optimisation:
                 unproven) · QML on data (hype-heavy as of 2026)
VQE              min_theta <psi(theta)|H|psi(theta)> >= E0 (Rayleigh-Ritz)
                 ansatz U(theta)|0> + classical optimiser
                 param-shift: dC/dtheta = [C(th+pi/2)-C(th-pi/2)]/2
                 chem accuracy = 1.6 mHa ~ 4 kJ/mol · H2 g.s. -1.137 Ha
                 O(n^4) Pauli terms -> 1e8+ shots/step w/o grouping
QAOA             |+>^n then p x [exp(-i gamma C), exp(-i beta B)]
                 C=cost diag(ZZ...), B=sum X · p->inf => adiabatic
                 empirics: loses to GW/heuristics at p<=3 on real HW
BARREN PLATEAUS  Var[d<C>/dtheta] ~ O(1/2^n) deep random circuits
                 fixes: problem-inspired ansatz, layerwise, symmetries
DEQUANTISATION   Tang 2019: QRAM-assumed speedups matched classically
                 Schuld 2021: circuit models = Fourier series of encoding
AUDIT CHECKLIST  tuned classical baseline? · data-loading counted?
                 scales past toy? · access assumptions stated?
TOOLING          PennyLane (autodiff circuits) · qiskit-algorithms +
                 Estimator/Sampler V2 · PySCF classical preprocessing
                 SPSA under noise (2 evals/step, param-count-free)
HONEST STATE     no quantum model beats strong classical baselines on
                 natural datasets as of 2026 · simulation is the
                 credible path, gated on error correction (2028+)
```

## Sources

- [McClean et al., Barren plateaus in quantum neural network training landscapes](https://www.nature.com/articles/s41467-018-07090-4) — accessed 2026-08-23
- [Schuld, Sweke, Meyer, Effect of data encoding on the expressive power of variational quantum machine learning models](https://journals.aps.org/pra/abstract/10.1103/PhysRevA.103.032430) — accessed 2026-08-23
- [Peruzzo et al., A variational eigenvalue solver on a photonic quantum processor (VQE)](https://www.nature.com/articles/ncomms5213) — accessed 2026-08-23
- [Farhi, Goldstone, Gutmann, A Quantum Approximate Optimization Algorithm](https://arxiv.org/abs/1411.4028) — accessed 2026-08-23
- [PennyLane documentation: variational quantum algorithms](https://docs.pennylane.ai/) — accessed 2026-08-23
- [QubitLogic: Qiskit 2.x migration and qiskit-algorithms patterns](https://qubitlogic.dev/quantum-coding/qiskit-2-migration-guide) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

