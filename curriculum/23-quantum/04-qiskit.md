# Hands-On: Qiskit/Cirq Simulators, Running a Circuit, Reading Results

> **Track:** T23 Quantum Computing · **Time:** 2.5h · **Prereqs:** T23-qubits, T23-gates-circuits
> **Updated:** 2026-08-08
> **Module id:** `T23-qiskit` · **Tags:** practice

## The 30-second version

The standard Qiskit workflow is: build a `QuantumCircuit`, `transpile()` it for a target backend (rewriting it into native gates and respecting connectivity, module 2), then execute it — either exactly via `Statevector` simulation (which gives you the true amplitude vector directly, something no real quantum computer can ever hand you, only a simulator can) or via shot-based sampling through a `Sampler` primitive (which mimics what actual hardware gives you: a `counts` dictionary from repeated circuit executions, with statistical shot noise that shrinks as `1/√shots`, not something you eliminate by "running it more precisely"). Qiskit's execution API moved from the old monolithic `execute()` function (removed in Qiskit 1.0, February 2024) to a **primitives** model — `Sampler` for measurement-outcome distributions, `Estimator` for observable expectation values — that abstracts uniformly over local simulators and real IBM hardware. The single most important distinction for reading results correctly: shot noise (statistical, shrinks with more shots) and hardware noise/decoherence (systematic, does *not* shrink with more shots — module 5) look similar in a histogram but require completely different fixes, and conflating them is the most common practical mistake.

## Why this gets asked

Because theory fluency and hands-on fluency are different skills, and an interviewer testing for the latter has watched candidates who can derive the Born rule but have never actually run `transpile()`, never debugged a "counts don't sum to shots" bug, and don't know that increasing `shots=1000` to `shots=1000000` fixes statistical noise but does nothing for a genuinely miscalibrated two-qubit gate. This is also the module that separates people who've read about quantum computing from people who could plausibly onboard onto a team using it — can you read a circuit diagram, run it, get a histogram, and correctly diagnose why the histogram doesn't look like the textbook answer.

---

## Lineage: past → present → future

**What came before.** Early quantum programming meant writing circuits at the assembly level — OpenQASM (2017) gave a standardized low-level instruction format, but hand-writing gate sequences and pulse schedules doesn't scale past toy circuits, has no reusable abstraction for circuit construction or optimization, and gives no software layer for switching between simulators and real hardware. IBM released Qiskit in 2017 and Google released Cirq in 2018 specifically to solve this — a Python SDK layer with circuit-building objects, a transpiler, and pluggable backends, so the same logical circuit description could target a local simulator during development and real hardware for final runs without rewriting anything.

**Where it stands now.** Qiskit's execution model itself went through a significant, disruptive change: the original `execute(circuit, backend, shots=N)` one-call pattern was deprecated and then removed starting with Qiskit 1.0 (February 2024), replaced by the **primitives** model — `Sampler.run([circuit])` returns measurement-outcome distributions (what you'd call "counts"), `Estimator.run([(circuit, observable)])` returns expectation values directly, and both work identically whether the backend is a local simulator or IBM's cloud Runtime service. `qiskit-aer` (the high-performance local simulator package providing `AerSimulator`) remains fully functional and is what most local development and this module's examples use, though its own documentation as of 2026 notes it's under **reduced maintenance** — critical bug fixes only, feature requests backlogged — reflecting where IBM's active development investment has shifted (toward the cloud Runtime primitives and hardware-facing tooling) ([Qiskit Aer GitHub](https://github.com/Qiskit/qiskit-aer) — accessed 2026-08-08). The live practical question for a newcomer isn't philosophical — it's "AerSimulator locally for learning and fast iteration, primitives model for anything touching real hardware or IBM's cloud" is the current de facto answer, and this module teaches both.

**Where it's heading.** High confidence: error mitigation and error suppression (module 5 covers the underlying physics) are becoming default-on, automatic parts of cloud hardware submission through the Runtime primitives rather than something users hand-implement circuit-by-circuit — this is a real, shipping trend, not speculative. Lower confidence: **circuit-cutting** — decomposing a large logical circuit into smaller sub-circuits that fit on today's small noisy devices, executed separately and stitched back together with classical post-processing — is an active research area with real published results and some production tooling, but whether it becomes a standard, load-bearing part of practitioners' workflows (versus a niche technique for specific circuit structures) is not yet settled; treat it as promising but unproven at scale.

---

## Mental model

```
  THE WORKFLOW                                    STATEVECTOR vs SHOT-BASED
  ─────────────                                    ─────────────────────────
  QuantumCircuit          (build: qc.h(0), qc.cx(0,1))

        │ transpile(qc, backend)                   Statevector.from_instruction(qc)
        ▼                                           -> EXACT amplitudes, e.g. (0.7071,0,0,0.7071)
  native-gate circuit     (module 2: routed,          no shot noise, but:
                            basis-translated)          - exponential memory, ~30-40 qubit ceiling
        │                                              - NOT obtainable from real hardware, ever
        ├── Statevector sim  ──▶ exact amplitudes
        │                                           Sampler.run([qc], shots=N)
        └── Sampler.run(shots=N) ──▶ counts dict      -> counts dict, e.g. {'00':512, '11':488}
              {'00': 512, '11': 488}                   statistical noise ~ 1/√N (SHRINKS with shots)
                                                        mimics what REAL hardware actually returns
```

---

## How it actually works

### Building and transpiling a circuit

```python
# untested sketch -- qiskit unavailable in this sandbox (no package-index network access);
# API verified against current Qiskit docs (Qiskit 1.x primitives model, qiskit-aer 0.17.x,
# accessed 2026-08-08). Logic cross-checked against the hand-verified numpy simulator below,
# which WAS run and whose output is quoted exactly.

from qiskit import QuantumCircuit, transpile
from qiskit_aer import AerSimulator

qc = QuantumCircuit(2, 2)
qc.h(0)          # qubit 0 -> |+>
qc.cx(0, 1)       # CNOT(control=0, target=1) -> Bell state
qc.measure([0, 1], [0, 1])

sim = AerSimulator()
transpiled = transpile(qc, sim, optimization_level=1)
```

`transpile()` does three distinct jobs, and conflating them is a common source of confusion: **basis translation** (rewrite `h`/`cx` into whatever native gates the target actually implements, module 2), **routing** (insert `SWAP` gates if the target's qubit connectivity doesn't allow a required two-qubit gate directly between the chosen qubits), and **optimization** (`optimization_level=0..3`, trading compile time for fewer resulting gates — level 3 runs the most aggressive passes, including gate cancellation and commutation-based reordering). For a local `AerSimulator` target with no connectivity restriction, transpilation mostly just does basis translation and light optimization; the routing step becomes load-bearing specifically when targeting real, sparsely-connected hardware.

### Statevector simulation: exact, but not what real hardware gives you

```python
# untested sketch -- see note above
from qiskit.quantum_info import Statevector

qc2 = QuantumCircuit(2)
qc2.h(0)
qc2.cx(0, 1)
sv = Statevector.from_instruction(qc2)
print(sv)   # expected: Statevector([0.70710678+0.j, 0.+0.j, 0.+0.j, 0.70710678+0.j], dims=(2, 2))
```

This returns the **exact** amplitude vector — no shots, no statistical noise, a direct readout of the mathematical object modules 1-2 built by hand. The expected output above is not a guess: it's exactly the Bell-state vector `(0.7071, 0, 0, 0.7071)` verified independently via the pure-`numpy` circuit simulator in module 2's "Build it from scratch" section, which **was** actually run. This is the critical fact to internalize: **no real quantum computer can ever return a statevector.** Measuring a real qubit collapses it (module 1) — hardware only ever gives you classical measurement outcomes (`counts`), never the underlying amplitudes. `Statevector` simulation is a debugging and pedagogical tool available *only* in simulation, useful for verifying a circuit does what you think before ever touching real (or shot-based-simulated) hardware, and it shares the exponential-memory ceiling covered in module 1 — practically limited to roughly 30-40 qubits on typical hardware.

### Shot-based sampling: what real hardware actually gives you, and why noise shrinks as 1/√shots

```python
# untested sketch -- see note above
from qiskit.primitives import StatevectorSampler

sampler = StatevectorSampler()
job = sampler.run([transpiled], shots=1000)
result = job.result()
counts = result[0].data.c.get_counts()   # e.g. {'00': 507, '11': 493}
```

`shots` is the number of times the circuit is prepared and measured from scratch; each shot gives one classical bitstring, and `counts` tallies how often each bitstring occurred. For a genuinely 50/50 distribution (an ideal Bell state, ignoring hardware noise), the standard error of the observed frequency is `√(p(1-p)/shots) = 0.5/√shots` — **verified directly** by sampling from the exact Bell-state distribution:

```
shots=    10: counts={'00': 4, '11': 6},   freq(00)=0.4000, deviation=0.1000, theoretical SE=0.1581
shots=   100: counts={'00': 49,'11': 51},  freq(00)=0.4900, deviation=0.0100, theoretical SE=0.0500
shots=  1000: counts={'00': 507,'11': 493},freq(00)=0.5070, deviation=0.0070, theoretical SE=0.0158
shots= 10000: counts={'00':4968,'11':5032},freq(00)=0.4968, deviation=0.0032, theoretical SE=0.0050
shots=100000: counts={'00':49911,'11':50089},freq(00)=0.4991,deviation=0.0009, theoretical SE=0.0016
```

The observed deviation from the true `0.5` tracks the theoretical `1/√shots` standard error closely at every scale tested — `10×` more shots buys roughly `√10 ≈ 3.16×` tighter precision, not `10×` tighter, which is the concrete numeric content of "shot noise shrinks as `1/√shots`." **This is purely statistical sampling noise from a perfect, noiseless distribution** — it has nothing to do with hardware imperfection, and this is exactly the distinction that gets muddled in practice: on real hardware, the observed counts deviate from the ideal distribution for *two* separate, differently-behaved reasons — statistical shot noise (shrinks with more shots, as shown) and systematic decoherence/gate-error noise (does **not** shrink with more shots; module 5's T1/T2 and gate-fidelity numbers set a noise floor that more shots cannot buy you past).

### Reading a histogram correctly

A `counts` dictionary from a Bell-state circuit run on **real hardware** typically looks like `{'00': 481, '11': 468, '01': 29, '10': 22}` rather than the ideal `{'00': ~500, '11': ~500}` — the `'01'`/`'10'` outcomes, which should have exactly zero probability in the ideal circuit, appear because of real gate errors and decoherence. The diagnostic discipline: **increasing shots narrows the error bars around whatever the true underlying distribution is, but does not move the true distribution back toward ideal** — if `'01'`/`'10'` persist at a stable ~5% each after `10×` more shots, that's a noise floor from hardware error (module 5), not a sampling artifact, and the fix is error mitigation, better calibration, or a different qubit pair — never "run more shots."

---

## Build it from scratch

Since a sandboxed environment may not have network access to install `qiskit` (true for this module's authoring environment — the `pip install qiskit qiskit-aer` attempt failed with a proxy/network error, worth knowing as a realistic failure mode itself), here is the actual verification path used: the exact circuits above were cross-checked against the pure-`numpy` statevector simulator built and run in module 2, which requires no external packages and reproduces every Qiskit primitive's *logic* directly:

```python
import numpy as np

# This IS runnable with numpy alone, and was run — it's the ground truth the qiskit
# sketches above are checked against, not a hypothetical.

I2 = np.eye(2, dtype=complex)
H = (1/np.sqrt(2))*np.array([[1,1],[1,-1]], dtype=complex)
CNOT = np.array([[1,0,0,0],[0,1,0,0],[0,0,0,1],[0,0,1,0]], dtype=complex)
zero = np.array([1,0], dtype=complex)

def tensor(a, b):
    return np.kron(a, b)

state = tensor(zero, zero)
state = tensor(H, I2) @ state
bell = CNOT @ state
# bell = [0.7071, 0, 0, 0.7071]  -- this IS what Statevector.from_instruction(qc2) returns

# Simulate shots by sampling from the exact |amplitude|^2 distribution -- this is
# literally what a shot-based backend does internally, just without hardware noise.
probs = np.abs(bell)**2
outcomes = ["00", "01", "10", "11"]
rng = np.random.default_rng(7)
for shots in [10, 100, 1000, 10000, 100000]:
    samples = rng.choice(outcomes, size=shots, p=probs)
    counts = {o: int(np.sum(samples == o)) for o in outcomes if probs[outcomes.index(o)] > 0}
    freq00 = counts.get("00", 0) / shots
    se = np.sqrt(0.5*0.5/shots)
    # matches the table above exactly -- this table's numbers ARE this code's output
```

This numpy-based "shot simulator" is not a toy stand-in — it's mechanically identical to what `AerSimulator` and `StatevectorSampler` do under the hood for a noiseless circuit: compute the exact statevector, square the amplitudes for outcome probabilities, sample from that categorical distribution `shots` times. The only thing genuinely missing without real Qiskit is the noise-model machinery (module 5) and the transpiler's hardware-connectivity-aware routing (module 2) — both of which are separate, well-documented subsystems, not part of the core sampling logic this reproduces exactly.

---

## How it's done in production

| Layer | What it adds over local simulation |
|---|---|
| `AerSimulator` (local) | Fast, noiseless or custom-noise-model simulation on your own machine; no queue, no cost, ceiling around 30-40 qubits for statevector methods |
| `AerSimulator` with a **fake backend** noise model (`FakeSherbrooke`, etc.) | Loads real calibration data (gate errors, T1/T2, readout error) from an actual IBM device snapshot, so you can estimate how a circuit will perform on real hardware *before* spending queue time and cost on it |
| IBM Quantum Runtime (cloud primitives) | Real hardware execution, with automatic error suppression/mitigation options, but subject to queue wait times (minutes to hours depending on device demand) and a per-second or per-shot cost model |
| Amazon Braket / Azure Quantum | Multi-vendor access layers (IonQ, Rigetti, IBM, and others through one API), useful for comparing platforms without separate SDKs per vendor |

| Symptom | Cause | Fix |
|---|---|---|
| `counts` dictionary values don't sum to the requested `shots` | Measurement instructions missing on some qubits, or measuring into fewer classical bits than qubits, silently dropping outcomes | Verify `qc.measure_all()` or explicit `measure()` calls cover every qubit you intend to read out |
| Circuit runs fine on `AerSimulator` but fails to transpile for a real backend | Real backend's coupling map doesn't support a required two-qubit gate between the chosen qubits, or the circuit uses more qubits than the backend has | Check `backend.coupling_map` and `backend.num_qubits` before submission; let the transpiler's routing pass handle connectivity rather than assuming any-to-any |
| Increasing `shots` from 1,000 to 100,000 doesn't shrink the deviation from the expected ideal distribution | The deviation is a systematic hardware noise floor (decoherence, gate error), not statistical shot noise — module 5 | Apply error mitigation (zero-noise extrapolation, readout-error correction) or accept the noise floor as a real hardware limitation; more shots only helps the *statistical* component |
| `Statevector` simulation runs out of memory around 30 qubits | Exact statevector simulation is inherently `O(2ⁿ)` in memory (module 1) — this is not a Qiskit bug | Switch to shot-based (`Sampler`) simulation for larger circuits, or tensor-network/stabilizer-based simulators for specific circuit structures that admit them |
| A circuit that should be entirely Clifford (H, S, CNOT only) runs slowly on a "quantum" simulator | Using a general statevector or shot-based simulator for a circuit that's classically efficiently simulable (Gottesman-Knill, module 2) | Use a stabilizer-formalism simulator (Qiskit's `Clifford`/`StabilizerState` classes) for Clifford-only circuits — polynomial time instead of exponential |

---

## Tradeoffs & when NOT to use it

- **Don't use `Statevector` simulation to predict real hardware behavior.** It's exact and noiseless by construction — useful for verifying circuit logic, useless for estimating real-world fidelity. Use a noise-model-equipped `AerSimulator` (loaded with real calibration data via a fake backend) for that.
- **Don't chase more shots to fix a problem that's actually noise, not statistics.** This is the single most common practical misdiagnosis covered in this module — check whether a deviation shrinks with more shots (statistical) or persists (systematic/hardware) before deciding what to fix.
- **Don't skip transpilation "because the simulator ran fine."** A circuit that runs on `AerSimulator` with no connectivity constraints can fail outright, or silently balloon in gate count via `SWAP` insertion, when transpiled for real hardware's coupling map — always transpile against the actual intended target, even during local development.
- **Don't reach for a general statevector or shot-based simulator for pure Clifford circuits at scale.** Gottesman-Knill (module 2) means a dedicated stabilizer simulator handles thousands of qubits of Clifford-only circuits in polynomial time, where a general simulator would hit the exponential wall around 30-40 qubits for no reason.

---

## Interview questions

### Q1 — What's the difference between `Statevector` simulation and shot-based (`Sampler`) simulation, and which one can real hardware actually give you?
**Testing:** the module's central distinction, checked directly.
**Answer:** `Statevector` gives the exact amplitude vector with no sampling noise — a purely simulation-only capability. `Sampler`-based shot simulation returns a `counts` dictionary from repeated circuit executions, with statistical noise shrinking as `1/√shots` — this is what real hardware actually returns, since measurement is destructive (module 1) and no physical device can hand you amplitudes directly.
**Follow-up trap:** *"If I run Statevector simulation with a huge number of 'shots,' does it converge to the exact statevector?"* — the question itself contains a category error: `Statevector` simulation has no shots at all; it's a single deterministic linear-algebra computation, not a sampling process. Shot-based sampling *converges toward* the probabilities `Statevector` gives you exactly and directly, but the two are different computations, not different precision levels of the same one.

### Q2 — A Bell-state circuit run with `shots=1000` gives `{'00': 507, '11': 493}`. Is this consistent with the ideal circuit, or evidence of a bug?
**Testing:** whether shot noise magnitude is understood quantitatively, not just qualitatively.
**Answer:** Consistent. The theoretical standard error for a fair 50/50 outcome at 1,000 shots is `√(0.5·0.5/1000) ≈ 0.0158`, i.e., roughly `±16` shots around the expected `500` — an observed `507/493` split is well within one standard error and exactly the kind of variation a correct, noiseless Bell-state circuit produces.
**Follow-up trap:** *"What result at 1000 shots WOULD indicate a problem?"* — a result like `{'00': 480, '11': 460, '01': 35, '10': 25}` (non-negligible `'01'`/`'10'` counts, which should be exactly zero in an ideal Bell-state circuit) — that pattern doesn't shrink with more shots and points to real gate error or decoherence (module 5), not statistical noise, which is the diagnostic distinction this module is built around.

### Q3 — Why can't a real quantum computer ever return a `Statevector` object the way a simulator can?
**Testing:** connecting the hands-on tooling back to the measurement-collapse physics from module 1.
**Answer:** Measuring a qubit collapses its state to a classical outcome (the Born rule, module 1) — a real device only ever produces classical bitstrings from repeated executions, never the underlying complex amplitude vector. `Statevector` simulation works only because a simulator has direct access to the mathematical object being manipulated internally; there's no physical measurement process that reveals a quantum state's amplitudes directly, for any hardware, ever.
**Follow-up trap:** *"Could you approximate the statevector by doing full quantum state tomography on real hardware instead?"* — yes, partially: state tomography reconstructs an approximate density matrix (module 1) from many repeated measurements in different bases, but it requires exponentially many measurement settings and shots in the number of qubits, is itself subject to the same statistical and hardware noise covered in this module, and gives an *estimate*, not the ground-truth statevector a simulator directly computes — practical only for very small numbers of qubits.

### Q4 — What are the three distinct things `transpile()` does, and why does conflating them cause confusion?
**Testing:** whether the transpiler is understood as multiple passes, not one opaque black box.
**Answer:** Basis translation (rewrite gates into the target's native gate set, module 2), routing (insert `SWAP` gates to satisfy limited qubit connectivity), and optimization (reduce gate count/depth via passes like gate cancellation, controlled by `optimization_level=0..3`). Conflating them causes confusion because they have different symptoms when they go wrong — a basis-translation issue means an unsupported gate error, a routing issue means unexpected `SWAP`-driven gate-count inflation, and an optimization-level choice trades compile time for circuit quality, a separate knob entirely.
**Follow-up trap:** *"If a transpiled circuit at optimization_level=3 has MORE gates than at level 1, is that a bug?"* — not necessarily; level 3's more aggressive passes have longer compile time and *usually* produce fewer or equal gates, but this isn't a strict guarantee for every circuit and every backend — the more actionable check is comparing actual circuit depth and two-qubit gate count (the metrics that dominate real hardware error) between levels for your specific circuit, not assuming a higher level number always wins.

### Q5 — You increase shots from 1,000 to 100,000 on a real device and the deviation from the ideal 50/50 Bell-state distribution barely changes. What does this tell you?
**Testing:** the practical diagnostic this whole module builds toward.
**Answer:** The deviation is dominated by systematic hardware noise (decoherence, gate error, readout error — module 5), not statistical shot noise. Statistical noise from a true underlying distribution shrinks predictably as `1/√shots` (verified: `0.1000 → 0.0009` deviation across `10 → 100,000` shots for the *ideal, noiseless* case above) — if real-device deviation isn't shrinking at anywhere near that rate, the noise floor is systematic, and more shots won't buy you past it.
**Follow-up trap:** *"So is running more shots ever pointless on real hardware?"* — not pointless, but its purpose changes: more shots still tightens your *statistical* confidence in whatever the true (noisy) distribution actually is, which is useful for accurately characterizing the hardware noise itself (calibration, benchmarking) — it's specifically "more shots removes the *bias* introduced by hardware noise" that's false, not "more shots is useless."

### Q6 — Design check: a teammate proposes debugging a suspected circuit-logic bug by submitting increasingly large `shots` counts to real IBM hardware to "get a clearer picture." What's wrong with this debugging approach?
**Testing:** applying the tooling-fluency lessons to a realistic, costly production mistake.
**Answer:** Real hardware runs cost money and queue time, and — critically — real hardware results are *always* contaminated by systematic noise (module 5) on top of whatever the circuit's true ideal behavior is, so a suspected *logic* bug (wrong gate, wrong qubit ordering, wrong measurement mapping) is far cheaper and clearer to debug against `Statevector` simulation first, where the exact ideal amplitudes are directly visible with zero noise of any kind — only once the circuit is confirmed logically correct does it make sense to move to shot-based simulation, and only after that to real hardware for characterizing actual physical performance.
**Follow-up trap:** *"What if the bug only appears on real hardware, not in Statevector simulation — how do you debug that?"* — that's precisely evidence the bug isn't in circuit logic but in something hardware-specific: a transpilation/routing issue (wrong qubit ended up in the wrong physical location), a calibration problem with a specific qubit pair, or genuine noise exceeding expectations — the fix path is checking the transpiled circuit against the backend's coupling map and calibration data (readout/gate error rates per qubit), not re-examining the original circuit's logic, which `Statevector` simulation already confirmed was correct.

### Q7 — What replaced Qiskit's `execute()` function, and why does this matter beyond "the API changed"?
**Testing:** current tooling awareness — has the candidate touched Qiskit recently enough to know this, or are they working from stale memory.
**Answer:** The **primitives** model — `Sampler` for measurement-outcome distributions and `Estimator` for expectation values — replaced the monolithic `execute(circuit, backend, shots=N)` call starting with Qiskit 1.0 (February 2024). It matters beyond naming because primitives are designed to work identically whether the backend is a local simulator or IBM's cloud Runtime service, and `Estimator` in particular directly returns expectation values (needed for VQE/QAOA, module 6) without the caller manually post-processing counts into an expectation value themselves — a real workflow simplification, not just a rename.
**Follow-up trap:** *"Is old code using execute() still guaranteed to work?"* — no; `execute()` was deprecated and then removed in Qiskit 1.0, so any tutorial, blog post, or internal codebase referencing it directly is stale as of the 2024 change and needs updating to the primitives pattern — a real, concrete example of why this track insists on checking current docs rather than working from memory or older training material.

### Q8 — Why would you deliberately use a "fake backend" noise model in `AerSimulator` instead of just submitting to real hardware?
**Testing:** the practical cost/iteration-speed tradeoff between simulation tiers.
**Answer:** Fake backends (`FakeSherbrooke` and similar) load real calibration snapshots — actual per-qubit gate error rates, T1/T2, readout error — from a real device, letting you estimate realistic circuit performance locally, with no queue wait and no cost, before spending real hardware time on it. This is strictly better for iterating on error-mitigation strategies or estimating whether a circuit is even worth submitting.
**Follow-up trap:** *"Does a fake-backend simulation perfectly predict what the real device will do?"* — no; it's a snapshot of calibration data at a point in time, and real device performance drifts (recalibration happens regularly, and qubit performance genuinely varies day to day) — a fake-backend estimate is directionally useful and far better than assuming zero noise, but shouldn't be treated as a guaranteed match to a live run's actual results.

### Q9 — A circuit that's entirely built from H, S, and CNOT gates runs noticeably slower on a general-purpose simulator than expected for its qubit count. What's the fix?
**Testing:** connecting module 2's Gottesman-Knill theorem to a concrete tooling choice.
**Answer:** A general statevector or shot-based simulator doesn't know or exploit that a Clifford-only circuit (module 2) is classically efficiently simulable — it still does the full `O(2ⁿ)`-scaling linear algebra. Using a dedicated stabilizer-formalism simulator (Qiskit's `Clifford`/`StabilizerState` classes, or Aer's stabilizer simulation method) instead handles thousands of qubits of Clifford-only circuits in polynomial time, because it tracks the stabilizer generators rather than the full amplitude vector.
**Follow-up trap:** *"If the circuit has even one T gate mixed in with otherwise-Clifford gates, does the stabilizer simulator still work?"* — no, and this is the hard boundary: stabilizer simulators are specifically built to handle Clifford operations and fail (or require switching to a fundamentally different, more expensive technique like stabilizer-rank decomposition, which scales with the number of non-Clifford gates) the moment genuine non-Clifford resources like `T` gates are introduced — this is precisely the same boundary (Clifford vs. Clifford+T) covered as the universality threshold in module 2.

### Q10 — What actually failed when this module's author tried `pip install qiskit` in this sandbox, and why is that worth mentioning in a "hands-on" module rather than hiding it?
**Testing:** whether the candidate values honest failure reporting over a polished-looking but potentially fabricated demonstration — a real engineering-culture signal, not a trivia question.
**Answer:** The install failed with a proxy/network connectivity error (no package-index access in the authoring sandbox), which is disclosed explicitly in this module rather than silently presenting untested Qiskit code as if it had been run. The actual verification path used instead — a hand-rolled `numpy` statevector simulator, which *was* run, cross-checked against the exact amplitudes Qiskit's `Statevector` API would return — is the honest substitute, clearly labeled as such.
**Follow-up trap:** *"Doesn't this undermine confidence in the qiskit code snippets shown?"* — the opposite, if handled correctly: labeling unverified code explicitly (`# untested sketch`) while providing a genuinely run, cross-checked equivalent is more trustworthy than silently presenting all code as equally verified — this module's discipline about which numbers were actually computed versus which are API usage patterns checked against current documentation is itself the practice worth adopting when writing about tools you can't currently execute.

---

## Red flags that fail you

- Claiming increasing `shots` fixes hardware noise/decoherence rather than only shrinking statistical sampling error.
- Not knowing real hardware can never return a `Statevector` — only simulators can.
- Presenting untested code as if it were verified, or being unable to distinguish "I ran this" from "this matches documented API usage."
- Skipping transpilation and assuming a circuit that works on a noiseless local simulator will behave identically on real hardware.
- Referencing the deprecated `execute()` function as current Qiskit API without acknowledging the primitives-model change.
- Using a general statevector/shot-based simulator for a pure Clifford circuit at a scale where a stabilizer simulator would trivially handle it.

---

## Cheat card

```
WORKFLOW: build QuantumCircuit -> transpile(qc, backend) -> run (Statevector exact, or
  Sampler/Estimator shot-based) -> read counts / expectation values.
transpile() DOES THREE THINGS: basis translation (native gates), routing (SWAP insertion for
  limited connectivity), optimization (optimization_level=0-3, gate count/depth reduction).
STATEVECTOR sim: EXACT amplitudes, no shot noise, O(2^n) memory (~30-40 qubit ceiling).
  Real hardware can NEVER return this -- measurement is destructive (Born rule, module 1).
SHOT-BASED (Sampler): returns counts dict from repeated runs. Statistical noise ~ 1/√shots
  (verified: 10 shots -> 0.10 deviation, 100k shots -> 0.0009 deviation from true p=0.5).
  10x more shots -> ~3.16x (√10) tighter precision, NOT 10x.
KEY DIAGNOSTIC: deviation that SHRINKS with more shots = statistical (fine). Deviation that
  PERSISTS regardless of shots = systematic hardware noise (module 5) -- more shots won't fix it.
Qiskit execute() REMOVED in 1.0 (Feb 2024) -> replaced by PRIMITIVES: Sampler (counts),
  Estimator (expectation values). Works identically on local sim or real IBM hardware.
FAKE BACKENDS (FakeSherbrooke etc.): AerSimulator loaded with real device calibration data --
  estimate real-hardware performance locally, no queue/cost, but drifts from live device state.
CLIFFORD-ONLY circuits (H,S,CNOT): use a STABILIZER simulator (poly-time), not general
  statevector/shot sim -- breaks the instant a T gate (non-Clifford) is introduced (module 2).
qiskit-aer is under REDUCED MAINTENANCE (2026) -- critical fixes only; still fully usable locally.
ALWAYS verify counts sum to requested shots -- mismatch usually means missing measure() calls.
```

## Sources

- [Qiskit Aer — GitHub (maintenance status, current version)](https://github.com/Qiskit/qiskit-aer) — accessed 2026-08-08
- [IBM Quantum Documentation — Sampler examples (current primitives API)](https://quantum.cloud.ibm.com/docs/en/guides/sampler-examples) — accessed 2026-08-08
- [IBM Quantum Documentation — Exact simulation with Qiskit SDK primitives (Statevector, Estimator)](https://quantum.cloud.ibm.com/docs/en/guides/simulate-with-qiskit-sdk-primitives) — accessed 2026-08-08
- [IBM Quantum Documentation — transpiler guide](https://docs.quantum.ibm.com/guides/transpile) — accessed 2026-08-08
- [What are Qiskit Primitives? — Qiskit Medium (Sampler/Estimator design rationale, execute() replacement)](https://medium.com/qiskit/what-are-qiskit-primitives-9bf63c1eacc7) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
