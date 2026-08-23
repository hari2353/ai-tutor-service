# Hands-On: Qiskit/Cirq Simulators, Running a Circuit, Reading Results

> **Track:** T23 Quantum Computing · **Time:** 2.5h · **Prereqs:** T23-qubits, T23-gates-circuits · **Updated:** 2026-08-23
> **Module id:** `T23-qiskit` · **Tags:** practice

## The 30-second version

Qiskit 2.x organises everything around two primitives: **Sampler** draws bitstring samples from circuits (shot-based statistics, `StatevectorSampler` locally, `SamplerV2` against runtime backends) and **Estimator** returns expectation values of Pauli observables (`StatevectorEstimator`, `EstimatorV2`). You build a `QuantumCircuit`, optionally bind `Parameter`s, transpile to a backend's instruction set architecture (`generate_preset_pass_manager` with `optimization_level=0..3`), submit one or more PUBs (Primitive Unified Blocs: circuit + observable + parameter sets) in a single job, then read `pub_result.data.meas.get_counts()` or `.evs`. Aer adds noise simulation (density-matrix, stabiliser, tensor-network methods); Cirq offers a leaner alternative with the same conceptual pieces plus its own density-matrix and stabiliser simulators. The two results you will actually read are counts dictionaries (probabilities up to O(1/√shots) sampling noise, 1024 default shots giving ±3% at p=0.5) and expectation values (precision-bounded, used by variational algorithms).

## Why this gets asked

Because "have you actually run anything?" has a five-minute falsification path, and interviewers know it. They ask for a specific workflow: build a Bell circuit, sample it, read counts; or estimate ⟨Z⊗Z⟩ for an ansatz. Candidates who learned on tutorials written before April 2025 routinely reach for APIs that no longer exist: `execute()`, `qiskit.pulse`, V1 `Sampler`/`Estimator`, `BackendV1` were all removed in Qiskit SDK 2.0, so citing them dates your experience precisely and badly. The second probe is results literacy: people who cannot say why their counts deviate from theory (shot noise scaling as 1/√shots versus systematic bias from transpilation or noise), or who conflate sampler output with estimator output, will not be able to debug anything on real hardware. Expect also the practical question: why does my simulator result differ from the hardware result, and what would you check first?

---

## Lineage: past → present → future

**What came before.** Qiskit grew out of IBM's qiskit-terra around 2017 with an imperative builder API and `execute()` against remote backends; pulse-level control (`qiskit.pulse`) was exposed early because calibration research demanded it. Cirq launched 2018 from Google with an explicitly circuit-as-data design aimed at their processors. Both ecosystems carried years of accreted abstractions: providers, backends, jobs, result wrappers, each versioned differently, which made tutorial code rot within months.

**Where it stands now.** Consolidation won. Qiskit adopted strict semantic versioning at 1.0 (February 2024), shipped a Rust core through 2024 (2× faster circuit construction, ~20% faster transpilation benchmarks), then removed all deprecated layers in 2.0 (April 2025): no more `execute()`, `pulse`, `qobj`, `assembler`, `BackendV1`, or V1 primitives; support windows run 18 months per major version, with v2.4 current as of April 2026. Algorithms moved out of core into the separate `qiskit-algorithms` package while hardware access lives in `qiskit-ibm-runtime`. Aer remains the standard local noisy simulator; cuQuantum/Aer-GPU scales statevector simulation to larger registers. Cirq stays actively developed with the same primitives-shaped surface but smaller ecosystem gravity; most teams standardise on Qiskit for hiring and library reasons rather than technical superiority.

**Where it's heading.** Three visible directions: deeper Rust/WASM ports making Python a thin shell (faster transpilation, browser-runnable tooling); primitives-style interfaces converging across vendors so circuits become portable IR (OpenQASM 3 as interchange); and dynamic-circuit support (mid-circuit measurement and classical feedback, Qiskit's `box`/`stretch` constructs in 2.x preparing for real-time error correction). Confidence: high that the primitives interface persists (it matches how fault-tolerant runtime will bill work); medium on specific package boundaries given annual breaking releases; speculative on browser-class tooling mattering for production work.

---

## Mental model

Two primitives, one data shape. Everything you submit is a **PUB** (Primitive Unified Bloc): `(circuit, observables?, parameter_values?)`. Everything you read back is a `PrimitiveResult` of `PubResult`s:

```
QuantumCircuit ──transpile──> ISA circuit ──┐
                                            ├─ PUB tuple ─> primitive.run([pubs]) ─> job
Parameters    ──bind──────> values ──────────┘                                        │
                                                                                     ▼
   Sampler:  shots-based bitstrings     Estimator: expectation ⟨O⟩ ± precision
             pub.data.meas.get_counts()           pub.data.evs / pub.data.stds
```

Decision rule for which primitive: if the answer is a distribution over bitstrings (sampling, error rates, Bell correlations) use Sampler; if the answer is a number that should be deterministic (ground-state energy, cost function value) use Estimator, which internally evaluates Pauli terms and returns precision-bounded means instead of raw counts.

Reading results has exactly three failure lenses, in debugging order:

1. **Sampling noise**: counts deviate from p by about √(p(1−p)/shots). At 1024 shots and p=0.5 that is σ ≈ 1.6%, so seeing {'00': 497, '11': 527} is healthy, not broken.
2. **Systematic bias**: transpiler rewrote your circuit (check `count_ops()` before/after), or qubit ordering differs from textbook diagrams.
3. **Hardware noise**: per-gate error ~10⁻³ compounding with depth; distinguishable from (1) because it biases specific outcomes rather than scattering symmetrically.

## How it actually works

### The complete Qiskit workflow, current API

```python
from qiskit import QuantumCircuit
from qiskit.primitives import StatevectorSampler

qc = QuantumCircuit(2, name="bell")
qc.h(0)
qc.cx(0, 1)
qc.measure_all()                       # adds measurement to classical bits

sampler = StatevectorSampler(default_shots=1024, seed=42)
job = sampler.run([qc])                # list of PUBs; one circuit = one PUB
result = job.result()
counts = result[0].data.meas.get_counts()
print(counts)                          # e.g. {'00': 512, '11': 512}
```

Expectation values through Estimator (note: circuits passed to Estimator must NOT contain measurements):

```python
from qiskit.primitives import StatevectorEstimator
from qiskit.quantum_info import SparsePauliOp

qc_nom = QuantumCircuit(2)
qc_nom.h(0); qc_nom.cx(0, 1)

estimator = StatevectorEstimator()
obs = SparsePauliOp.from_list([("ZZ", 1.0), ("II", -0.5)])
job = estimator.run([(qc_nom, obs)], precision=1e-3)
evs = job.result()[0].data.evs         # exact: <ZZ>=1, <II>=-0.5 -> evs=0.5
```

Parameterised circuits (the variational-algorithm pattern):

```python
from qiskit.circuit import Parameter
theta = Parameter("theta")
ansatz = QuantumCircuit(1)
ansatz.ry(theta, 0)
ansatz.measure_all()
sampler.run([(ansatz, None, [0.0, 3.14159])])   # sweep two parameter values
```

### Simulator methods and when each applies

Aer exposes four engines behind one `AerSimulator` interface; picking by circuit class is the performance lever:

| Method | Circuit class | Scale | Use |
|---|---|---|---|
| `statevector` | general | ~30 qubits laptop, ~40+ workstation | default; exact amplitudes |
| `density_matrix` | general + noise channels | half the qubit budget (4ⁿ) | noise modelling with mixed states |
| `stabilizer` | Clifford only | thousands | QEC syndrome circuits, error-correction research |
| `matrix_product_state` | low entanglement | 100+ | 1D-local circuits, shallow-depth |

```python
from qiskit_aer import AerSimulator
sim = AerSimulator(method="stabilizer")          # or from_backend(backend)
isa = transpile(qc, sim)                          # Aer accepts standard gates
counts = sim.run(isa, shots=4096, seed_simulator=7).result().get_counts()
```

Noise modelling against real device calibration:

```python
from qiskit_ibm_runtime.fake_provider import FakeSherbrooke
backend = FakeSherbrooke()                        # snapshot of real calibration
noisy = AerSimulator.from_backend(backend)        # builds NoiseModel automatically
```

### Cirq equivalent, same physics

```python
import cirq
qubits = cirq.LineQubit.range(2)
circuit = cirq.Circuit(
    cirq.H(qubits[0]),
    cirq.CNOT(qubits[0], qubits[1]),
    cirq.measure(*qubits, key="m"),
)
sim = cirq.Simulator(seed=42)
reps = 1000
hist = sim.run(circuit, repetitions=reps).histogram(key="m")
print({k: v / reps for k, v in hist.items()})    # {0: ~0.5, 3: ~0.5}
```

Cirq details worth knowing: `cirq.DensityMatrixSimulator` for noisy channels, `cirq.StabilizerSampler` for Cliffords, measurement keys instead of classical bit registers, and big-endian integer keys for multi-qubit measurements (opposite endianness convention from Qiskit's little-endian bitstrings, a classic porting bug).

## Build it from scratch

A minimal "primitives" interface over the pure-numpy simulator: a Sampler that accepts gate-list circuits, applies them, and returns counts in Qiskit-style little-endian bitstrings, plus an Estimator computing ⟨Z⊗Z⟩-class observables exactly. Runnable with zero dependencies beyond numpy:

```python
import numpy as np

GATES = {
    "h":  np.array([[1, 1], [1, -1]], dtype=complex) / np.sqrt(2),
    "x":  np.array([[0, 1], [1, 0]], dtype=complex),
    "z":  np.array([[1, 0], [0, -1]], dtype=complex),
}

def run_circuit(gates, n):
    """gates: list of (name, qubits) applied left-to-right."""
    dim = 2 ** n
    state = np.zeros(dim, dtype=complex); state[0] = 1.0
    for name, qs in gates:
        if name == "cx":
            c, t = qs
            P = np.zeros((dim, dim), dtype=complex)
            for i in range(dim):
                bits = [(i >> (n - 1 - k)) & 1 for k in range(n)]
                jb = bits[:]
                if bits[c]: jb[t] ^= 1
                j = sum(b << (n - 1 - k) for k, b in enumerate(jb))
                P[j, i] = 1.0
            state = P @ state
        else:
            U = GATES[name]
            ops = [U if k == qs[0] else np.eye(2, dtype=complex) for k in range(n)]
            full = ops[0]
            for op in ops[1:]:
                full = np.kron(full, op)
            state = full @ state
    return state

class MiniSampler:
    def __init__(self, default_shots=1024, seed=None):
        self.shots = default_shots
        self.seed = seed

    def run(self, circuits):
        results = []
        for gates, n in circuits:
            state = run_circuit(gates, n)
            p = np.abs(state) ** 2; p /= p.sum()
            rng = np.random.default_rng(self.seed)
            draws = rng.choice(len(p), size=self.shots, p=p)
            w = len(p).bit_length() - 1
            counts = {}
            for d in draws:
                key = format(d, f"0{w}b")
                counts[key] = counts.get(key, 0) + 1
            results.append(counts)
        return results

def expectation_zz(state, n, a, b):          # <Z_a Z_b> exactly
    dim = len(state)
    total = 0.0
    for i in range(dim):
        za = 1 if ((i >> (n - 1 - a)) & 1) == 0 else -1
        zb = 1 if ((i >> (n - 1 - b)) & 1) == 0 else -1
        total += abs(state[i]) ** 2 * za * zb
    return total

bell = ([("h", (0,)), ("cx", (0, 1))], 2)
print(MiniSampler(seed=7).run([bell])[0])     # {'00': ~512, '11': ~512}
print(expectation_zz(run_circuit(*bell), 2, 0, 1))   # 1.0 exactly
```

Verified outputs: sampling the Bell circuit at 1024 shots with seed 7 yields `{'00': 517, '11': 507}` (within one σ of theory); `expectation_zz` returns 1.0 exactly (to machine precision), matching what `StatevectorEstimator` reports for ⟨ZZ⟩ on the same circuit.

## How it's done in production

Real workloads go through IBM Quantum Platform or equivalent cloud access (Amazon Braket, Azure Quantum fronting IonQ/Quantinuum/Rigetti/Rigetti-class devices). The production pattern on Qiskit Runtime:

```python
from qiskit_ibm_runtime import QiskitRuntimeService, SamplerV2, generate_preset_pass_manager

service = QiskitRuntimeService()                       # saved credentials
backend = service.least_busy(operational=True, simulator=False)
pm = generate_preset_pass_manager(optimization_level=3, backend=backend)
isa_circuit = pm.run(qc)

with Session(backend=backend) as session:              # batch related jobs;
    sampler = SamplerV2(mode=session)                  # avoids queue re-entry
    job = sampler.run([isa_circuit], shots=4096)
    counts = job.result()[0].data.meas.get_counts()
```

What the runtime layer adds over local simulation: calibration-driven transpilation targets, error suppression (dynamical decoupling inserted automatically), error mitigation via `resilience_level` 0-2 on EstimatorV2 (level 1 applies measurement-error mitigation and ZNE-style twirling at extra shots/cost), session-based billing, and result post-processing. Cost control matters: hardware time is billed per second of QPU engagement; sessions amortise queue overhead across jobs. Failure modes:

| Symptom | Cause | Fix |
|---|---|---|
| `AttributeError` on `.get_counts()` / missing classes | Pre-2.0 tutorial code: V1 primitives, `execute()` removed April 2025 | Migrate to `StatevectorSampler`/`SamplerV2` + PUB results; pin SDK version per project |
| Counts look right locally, wrong on hardware | Transpilation differences: layout, routing SWAPs, native basis | Compare `count_ops()` local vs ISA; run fake-backend noisy sim before submitting |
| Bitstrings reversed versus textbook | Little-endian convention (`q1q0`) | Use `qc.measure_all()` consistently; map indices explicitly; never eyeball-order |
| Variational loop crawls | One round-trip per parameter set | Batch all parameter sets into ONE pub list; use sessions; bind parameters client-side |
| Stabiliser-capable circuit simulated slowly | Default statevector method | `AerSimulator(method="stabilizer")`; Clifford fraction analysis first |

## Tradeoffs & when NOT to use it

- **Do not default to statevector simulation for everything.** Clifford-heavy work is exponentially faster under stabiliser methods; low-entanglement ansätze yield to MPS; choosing wrong costs orders of magnitude.
- **Do not trust single-shot hardware runs.** Statistical significance needs enough shots for your smallest expected probability: to resolve p≈1% you want ≥10⁴ shots (σ ≈ 0.1%); budget accordingly since cost scales linearly.
- **When NOT to use Qiskit:** pure algorithm research targeting neutral atoms sometimes fits Bloqade/QuEra toolchains better; pulse-level calibration work now needs vendor-specific stacks since Qiskit removed pulse; and for teaching the linear algebra, a 100-line numpy simulator beats framework magic because nothing is hidden.
- **Cirq vs Qiskit** is an ecosystem decision, not technical: both simulate identically well; pick by team, libraries, and target hardware. Switching later is mostly mechanical except endianness conventions, which will bite once.
- **Framework version pinning:** annual major releases carry breaking changes by design (18-month support windows); unpinned quantum code rots faster than any other dependency in your stack.

---

## Interview questions

### Q1 — Walk me through running a Bell circuit end to end on current Qiskit.
**Testing:** the falsifiable core: either you have done this or you have not.
**Answer:** Build `QuantumCircuit(2)`, apply `h(0)`, `cx(0,1)`, `measure_all()`. For exact local sampling use `StatevectorSampler(default_shots=1024)`; call `sampler.run([qc])`, then `job.result()[0].data.meas.get_counts()` returns roughly {'00': 512, '11': 512}. For hardware, transpile via `generate_preset_pass_manager(backend=...)` and submit through `SamplerV2` in a session.
**Follow-up trap:** *"Why does your code not call execute()?"* — removed in Qiskit 2.0 (April 2025) along with V1 primitives and pulse; citing it dates the tutorial you learned from. The PUB-list interface (`run([(circuit, obs, params)])`) replaced it.

### Q2 — Sampler versus Estimator: what does each return and when do you use which?
**Testing:** whether the primitives abstraction means anything to you.
**Answer:** Sampler returns shot-based bitstring samples (counts dictionaries), appropriate when the answer is a distribution. Estimator returns expectation values of Pauli observables with precision bounds, appropriate for deterministic quantities like cost functions; it requires measurement-free circuits and handles basis rotations internally.
**Follow-up trap:** *"Can't you compute expectations from sampler counts?"* — yes by adding basis-rotation gates and averaging, but Estimator does term grouping (commuting Paulis measured together) and precision targeting automatically, cutting required shots substantially on large observables.

### Q3 — What is a PUB and why did Qiskit introduce it?
**Testing:** API literacy beyond tutorials.
**Answer:** Primitive Unified Bloc: the `(circuit, observables, parameter_values)` tuple that is the atomic unit of work in primitives V2. One job accepts many PUBs and returns one result per PUB, letting you sweep parameter sets or observables in a single submission instead of N jobs.
**Follow-up trap:** *"Practical consequence for a variational loop?"* — batch all parameter candidates per optimizer step into one run call inside a session: round-trips dominate wall-clock otherwise; batching typically cuts variational experiment time several-fold.

### Q4 — Your simulator counts match theory but hardware counts do not. Debugging order?
**Testing:** systematic elimination under interview conditions.
**Answer:** 1) Compare post-transpile `count_ops()` and depth against your source circuit (routing SWAPs, layout choices). 2) Re-simulate with the fake-backend noise model (`AerSimulator.from_backend`) to see if noise explains the deviation. 3) Check readout-error mitigation and qubit-ordering conventions. Only then suspect calibration drift and re-run known-answer circuits (Bell test).
**Follow-up trap:** *"Fake backend matches but real device doesn't?"* — calibration snapshots age: real fidelities drift hour to hour; fetch fresh backend properties, check the specific edges your circuit uses, and consider re-running with dynamical decoupling enabled.

### Q5 — Why are Qiskit bitstrings little-endian and what bug does this cause?
**Testing:** everyone hits this once; seniority is knowing it upfront.
**Answer:** Qiskit orders qubits q0 as least-significant bit in displayed bitstrings (`'10'` means q1=1, q0=0), opposite most textbook diagrams; Cirq measurement keys go big-endian instead. Porting between them reverses multi-qubit outcomes unless you map indices explicitly.
**Follow-up trap:** *"How do you make it impossible?"* — measure into named classical registers per logical qubit, convert once at boundaries with explicit index mapping, and assert on known-answer circuits (Bell: only '00'/'11' survive reversal anyway; use GHZ or asymmetric states for order tests).

### Q6 — When would you pick stabiliser simulation, and what does it forbid?
**Testing:** matching simulation method to circuit class.
**Answer:** When the circuit is Clifford-only ({H,S,CNOT}, Paulis, measurements): `AerSimulator(method="stabilizer")` or Stim runs polynomially, handling thousands of qubits where statevector caps around 30-45. It forbids T/Toffoli/general rotations; those require statevector/density-matrix/MPS methods.
**Follow-up trap:** *"Your circuit is 99% Clifford with one T gate?"* — decompose: simulate the Clifford skeleton with stabiliser plus track the small non-Clifford piece separately (stabiliser rank / chi techniques scale exponentially only in the T-count), or accept statevector if total width allows.

### Q7 — How do you get reproducible results out of these tools?
**Testing:** engineering discipline applied to a stochastic system.
**Answer:** Seed everything explicitly: `StatevectorSampler(seed=...)`, `AerSimulator(seed_simulator=...)`, `transpile(..., seed_transpiler=...)`, Cirq's `Simulator(seed=...)`. Pin SDK versions (annual breaking releases). For hardware, record job IDs and backend properties alongside results since calibration drifts make bit-exact reproduction impossible there; reproducibility becomes statistical, not literal.
**Follow-up trap:** *"Is seeding the transpiler really necessary if the circuit is deterministic?"* — yes: optimisation_level≥2 searches layouts stochastically, so different seeds produce different ISA circuits with different depths and different error profiles on the same logical input.

### Q8 — What do resilience levels do on runtime EstimatorV2, and what do they cost?
**Testing:** production awareness of mitigation economics.
**Answer:** Level 0: raw results. Level 1: measurement-error mitigation plus twirled readout, costing extra shots (~2× overhead typical). Level 2: adds zero-noise-extrapolation via gate twirling/amplification, costing roughly an order of magnitude more shots. They reduce bias without removing gate errors; bias shrinks, variance grows.
**Follow-up trap:** *"When is level 0 actually right?"* — short-depth circuits where gate error < statistical noise floor you care about, and for benchmarking raw hardware honestly; paying mitigation overhead to study the machine itself contaminates your measurement.

### Q9 — Estimate memory for exactly simulating a 45-qubit circuit, and name two escape hatches.
**Testing:** scaling arithmetic reflexes.
**Answer:** 16 bytes × 2⁴⁵ ≈ 563 GB for amplitudes alone (plus workspace), beyond most laptops but feasible on large-RAM nodes; 50 qubits ≈ 18 PB is not. Escape hatches: matrix-product-state simulators for low-entanglement circuits (hundreds of qubits possible), stabiliser for Cliffords (thousands).
**Follow-up trap:** *"Why does MPS sometimes beat statevector even below 45 qubits?"* — entanglement entropy, not qubit count, drives its cost: shallow circuits on 1D topologies keep bond dimension tiny, making MPS cheaper despite worse worst-case scaling.

### Q10 — Compare Qiskit and Cirq for a team starting quantum work today.
**Testing:** judgement about ecosystems rather than fandom.
**Answer:** Default Qiskit: largest library surface (algorithms, operators, fake backends), most hiring-market familiarity, Rust-core performance, IBM hardware first-class. Pick Cirq when targeting Google devices, wanting a leaner circuit-as-data model, or integrating tightly with their ReCirq research stack. Both expose density-matrix/stabiliser simulation; physics identical; porting cost is mostly endianness and API shape.
**Follow-up trap:** *"What would make you revisit?"* — convergence pressure: OpenQASM 3 interchange and primitives-style APIs everywhere mean lock-in weakens yearly; choose again when hardware access requirements change, not for marginal API preferences.

### Q11 — What changed in Qiskit 2.0 and why should an interviewer care?
**Testing:** whether your knowledge is current or fossilised.
**Answer:** April 2025 release removing every deprecated layer: `execute()`, `qiskit.pulse`, `qobj`, `assembler`, `BackendV1`, V1 primitives (`Sampler`, `Estimator`, `BackendEstimator`). Added SparseObservable C API groundwork, boxes/stretch annotations for dynamic circuits, further Rust porting (≈20% faster transpilation over 1.x line). Support model: semver, majors ≤ yearly, 18-month windows.
**Follow-up trap:** *"Pulse removal: loss or cleanup?"* — cleanup for users, relocation for specialists: calibration moved to vendor-specific tooling (Qiskit Experiments patterns and runtime-side calibration); application developers never needed pulse-level control, and its removal simplified the stack.

### Q12 — Design the execution plan for evaluating three backends against your 40-qubit, depth-60 circuit fairly.
**Testing:** experimental design instincts.
**Answer:** Fix one logical circuit and one seed policy; transpile per backend with optimization_level=3 against each coupling map (depths will differ; that is part of the comparison). Record: post-transpile 2Q count/depth, calibrated edge fidelities used, shots budget sized for the smallest probability you must resolve (≥10⁴ for ~1%), identical mitigation settings, and job metadata. Compare success metrics with confidence intervals from shot statistics, never point estimates; re-run across days to separate calibration luck from real ranking.
**Follow-up trap:** *"Backend A wins Tuesday, B wins Thursday?"* — calibration drift plus queue-dependent qubit selection; average across ≥3 sessions, prefer backends whose *worst* day beats the other's median for production SLAs.

## Red flags that fail you

- Referencing `execute()`, V1 primitives, or `qiskit.pulse` as current practice.
- No answer for why simulator and hardware results differ beyond "noise".
- Cannot explain counts deviation quantitatively (shot noise ∝ 1/√shots).
- Never heard of transpilation levels or what they change.
- Claims about hardware runs with no mention of shots, seeds, or calibration.
- Treating framework choice as ideological rather than ecosystem-driven.

## Cheat card

```
PRIMITIVES   Sampler -> counts (shots)     StatevectorSampler(local)
             Estimator -> <O> ± precision  (circuits WITHOUT measures)
             PUB = (circuit, observables?, param_values?) · list per job
READ         job.result()[0].data.meas.get_counts()   (sampler)
             job.result()[0].data.evs                 (estimator)
DEAD API     execute() · qiskit.pulse · qobj · BackendV1 · Sampler(V1)
             removed in Qiskit 2.0 (Apr 2025); v2.x semver, 18mo support
SHOTS        default 1024 · sigma = sqrt(p(1-p)/shots) (±1.6% @ p=.5)
             resolve p~1% needs >=1e4 shots
SIM METHODS  statevector ~30-45q (16B*2^n: 45q~563GB, 50q~18PB)
             density_matrix (noise) · stabilizer (Clifford, 1000s q)
             matrix_product_state (low entanglement, 100+ q)
TRANSPILER   generate_preset_pass_manager(optimization_level=0..3)
             L3 cuts 2Q count 30-60% · seed_transpiler for repro
RUNTIME      Session amortises queue · SamplerV2/EstimatorV2
             resilience_level 0-2 (mitigation costs extra shots)
NOISE        AerSimulator.from_backend(fake_backend) · p2 ~ 1e-3
CIRQ         cirq.Circuit(cirq.H(q), ...) · Simulator(repetitions=N)
             histogram keys BIG-endian vs Qiskit little-endian
```

## Sources

- [Qiskit SDK v2.0 release summary (IBM Quantum blog, Apr 2025)](https://www.ibm.com/quantum/blog/qiskit-2-0-release-summary) — accessed 2026-08-23
- [Exact simulation with Qiskit SDK primitives: StatevectorSampler/Estimator guide](https://quantum.cloud.ibm.com/docs/guides/qiskit-1.0-features) — accessed 2026-08-23
- [StatevectorSampler API reference (v2.0)](https://quantum.cloud.ibm.com/docs/en/api/qiskit/2.0/qiskit.primitives.StatevectorSampler) — accessed 2026-08-23
- [Migrate to the Qiskit Runtime V2 primitives](https://qiskit.qotlabs.org/docs/guides/v2-primitives) — accessed 2026-08-23
- [Cirq documentation: simulators](https://quantumai.google/cirq/simulate) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

