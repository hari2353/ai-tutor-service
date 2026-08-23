# Noise, Decoherence, NISQ, Surface Codes, Logical vs Physical Qubits

> **Track:** T23 Quantum Computing · **Time:** 2h · **Prereqs:** T23-qubits, T23-gates-circuits · **Updated:** 2026-08-23
> **Module id:** `T23-error-correction` · **Tags:** hardware, critical

## The 30-second version

Physical qubits are fragile: two-qubit gate error rates sit around 10⁻³ today, superconducting coherence times run 100-300 microseconds against ~20-50 nanosecond gates, so uncorrected circuits die past roughly a thousand entangling gates, which is the entire NISQ regime. Quantum error correction fights this by encoding one logical qubit non-locally across many physical qubits and repeatedly measuring stabiliser operators that reveal errors without touching the data; the surface code is the workhorse, needing roughly 2d² physical qubits per logical qubit at code distance d, with logical error falling as (p/p_th)^((d+1)/2) provided physical error stays below the ~1% threshold. That overhead is brutal: at p = 10⁻³ you need distance ~25, about 1,000-plus physical qubits per logical one, which is the honest meaning of "millions of physical qubits" for breaking RSA. Google's Willow chip crossed the historic line in December 2024: adding code distance made logical errors *fall* instead of rise (suppression factor Λ = 2.14 per distance step), and IBM is betting on quantum LDPC codes claiming roughly 10× lower overhead than surface codes for its 2029 Starling machine.

## Why this gets asked

Because every serious quantum conversation bottoms out here: qubit counts quoted in press releases are physical, algorithms need logical, and the ratio between them decides whether any claimed application happens in your career. Interviewers probe whether a candidate can move between the three layers: noise physics (what T1/T2 and gate fidelities actually limit), coding theory (why the threshold theorem matters and what overhead costs), and engineering reality (decoders must run in real time; magic states cost factories). A second motivation is cryptographic planning: estimates like "RSA-2048 needs 20 million noisy qubits in 8 hours" are meaningless unless you understand how the surface-code arithmetic produced them. Candidates who repeat "quantum computers are error-prone" without numbers, or who cannot say what Willow did and did not prove, read as consumers of headlines rather than engineers who could price a roadmap claim.

---

## Lineage: past → present → future

**What came before.** The consensus until the mid-1990s was pessimistic: continuous amplitudes plus no-cloning seemed to forbid error correction, since classical redundancy copies bits and quantum mechanics forbids copying unknown states and correcting continuous errors requires infinite precision. Shor's nine-qubit code (1995) broke the deadlock by digitising errors onto a discrete Pauli basis and spreading information non-locally; Steane's seven-qubit code (1996) followed, and the threshold theorem (Aharonov-Ben-Or, Knill-Laflamme-Zurek, Kitaev, ~1996-98) proved that if physical error sits under some constant threshold, arbitrary-length computation is possible with polylogarithmic overhead. Kitaev's toric code (1997) introduced the topological/surface-code family, and Fowler's 2012 engineering analysis turned it into the default architectural assumption with concrete overhead curves.

**Where it stands now.** The experimental era began in earnest recently: Google's 2023 distance-5 surface-code memory showed logical error beating physical pairs, and Willow (December 2024) demonstrated genuine below-threshold scaling from distance 3→5→7 with Λ = 2.14, logical qubit lifetime exceeding the best physical qubit by ~5×. Quantinuum ships 50 error-corrected logical qubits at 2:1 encoding on trapped ions (November 2025) using high-rate codes, exploiting all-to-all connectivity unavailable to superconducting chips. IBM pivoted architecturally: its bivariate-bicycle quantum LDPC codes (Nature, 2024) encode 12 logical qubits in 144 physical (12:1 gross ratio versus surface code's ~145:1 at comparable protection) but demand six-way qubit connectivity, hence the coupler-heavy Nighthawk/Loon processors and the L-coupler modular fridges announced August 2026. Live disagreement: surface-code conservatism versus LDPC ambition, and whether neutral atoms' reconfigurable connectivity makes them the dark horse for both.

**Where it's heading.** Near term: real-time decoders as shipping components (IBM prototyped theirs ahead of schedule in 2025, targeting deployment through 2026), logical operations beyond memory (lattice surgery, magic-state injection demonstrated on small instances), and code-distance scaling on 100-to-1000-qubit machines. IBM's committed targets: 200 logical qubits running 100 million gates (Starling, 2029), 2,000 logical (Blue Jay, ~2033); Google targets useful error-corrected machines toward a million physical qubits around 2029+. Confidence: high that below-threshold operation generalises; medium on 2029 dates; speculative on overhead constants improving fast enough to pull RSA-scale factoring before ~2035.

---

## Mental model

Classical majority vote fails twice over: you cannot copy an unknown qubit (no-cloning) and errors are continuous (any rotation angle, not just 0/1 flips). QEC solves both with one move: **encode non-locally, then measure only parity checks**.

```
CLASSICAL REPETITION          QUANTUM STEANE-STYLE
|0> -> |0>|0>|0>              alpha|0>+beta|1>  ->  spread across 7 qubits
flip? take majority           measure STABILISERS: e.g. Z1Z2, Z2Z3
3 copies, 1 error fixed       outcomes (+1/-1) reveal WHICH error occurred
                              WITHOUT revealing alpha or beta
                              correct by applying the named Pauli again
```

The stabiliser is a question like "do qubits 1 and 2 agree?" Its answer exposes the error's location while staying totally blind to the encoded amplitudes; that blindness is what makes measurement legal mid-computation. Continuous physical noise gets digitised because measurements project onto the discrete Pauli basis: any small rotation collapses to either "nothing happened" or "a clean X/Y/Z happened", and codes handle the discrete cases.

The economics picture to carry:

```
logical error per round ~ 0.1 · (p/p_th)^((d+1)/2),   p_th ~ 1% (surface code)

p = 1e-3:   d=3 -> ~1e-2   d=11 -> ~1e-6    d=25 -> ~1e-14
qubit cost: 2d^2 physical per logical:
            d=25 -> 1250 physical/logical  (~1000:1 overhead regime)
```

Every headline number ("millions of qubits for RSA") is this curve times algorithm width and depth. Nothing else in the field moves budgets as directly as the position of p below p_th.

## How it actually works

### The noise model, quantitatively

Errors decompose into four channels worth knowing numerically:

- **T1 relaxation** (|1⟩ decays toward |0⟩): superconducting transmons today ~100-300 μs; trapped ions ~seconds to minutes.
- **T2 dephasing** (phase randomisation): comparable scale, bounded by T1/... practically T2 ≤ 2·T1.
- **Gate error**: single-qubit ~10⁻⁴, two-qubit ~10⁻³ on best current hardware (IonQ reported 99.9923% two-qubit fidelity October 2025; IBM Heron-class devices run ~99.9% median).
- **Measurement/readout error**: ~10⁻² on superconducting, lower on ions; matters because QEC measures constantly.

NISQ depth budget from these numbers alone: total circuit success ≈ exp(−p₂ · d₂Q); at p₂ = 10⁻³, surviving 1000 two-qubit gates gives ~37% success, so useful uncorrected circuits top out near hundreds-to-a-thousand entangling gates. Error *mitigation* (zero-noise extrapolation, probabilistic error cancellation) reduces bias at exponential shot cost, buying back maybe one order of magnitude; it does not change the scaling. Only correction changes scaling, via the threshold theorem: below threshold, overhead grows polylogarithmically with target reliability; above it, adding qubits makes things worse, which is precisely what Willow disproved for its device family.

### Stabiliser codes: the [[n,k,d]] machinery

A code is written [[n,k,d]]: n physical qubits, k logical, distance d (smallest Pauli weight that maps any codeword to another; corrects up to t = ⌊(d−1)/2⌋ arbitrary single-qubit errors). Stabilisers are commuting Pauli operators fixing the code space; measuring them yields syndromes pointing to errors. Shor's [[9,1,3]] concatenated a bit-flip and phase-flip repetition code; Steane's [[7,1,3]] uses the classical Hamming code structure; the surface code is [[d², 1, d]] on a 2D lattice with only nearest-neighbour check qubits, which is why hardware likes it: planar layout, local stabilisers of weight ≤4.

Surface-code operation: rounds of (1) ancilla-mediated stabiliser measurement via CNOT schedules taking ~1 microsecond per round on superconducting hardware, (2) syndrome stream into a decoder, (3) decoder outputs corrections. Logical failure accumulates when error chains outgrow distance: per-round logical error ε_L ≈ 0.1(100p)^((d+1)/2) (Fowler's fit). Two consequences worth internalising: halving p buys you ~4× smaller d for fixed target, and every extra unit of d costs 4d+... roughly 4 new physical qubits (d² data + d²−1 ancilla ≈ 2d² total).

**Decoders are the hidden systems problem**: minimum-weight perfect matching (PyMatching-class) runs in microseconds for small d but real-time constraint at scale demands FPGA/ASIC decoding; a backlog of undecoded syndromes stalls the computation (the "data backlog problem"). This is a streaming-systems engineering problem wearing physics clothing, which is why IBM prototyped a dedicated real-time decoder in 2025.

### Beyond surface codes: LDPC and the overhead war

Quantum LDPC (low-density parity-check) codes relax geometry: each data qubit participates in few checks but checks can be long-range and encode k>1 logical qubits per block. IBM's bivariate bicycle codes ([[144,12,12]] gross code) achieve distance-12 protection at 144 physical for 12 logical, versus needing thousands under surface code, at the price of six-way connectivity between arbitrarily placed qubits, driving their coupler architecture. Trapped-ion machines exploit all-to-all gates for high-rate codes instead (Quantinuum's 2:1 encoding claim trades deep circuits for tiny blocks). Magic-state distillation remains the universal-gate tax: Toffoli/T operations consume distilled states produced in dedicated factories whose footprint historically exceeds the data qubits themselves; improving factory ratios is as valuable as better codes.

## Build it from scratch

A full classical-side QEC demonstration in numpy: the 3-qubit bit-flip repetition code with syndrome extraction and majority correction, plus a Monte Carlo showing the logical error curve crossing below physical. Runnable:

```python
import numpy as np
from itertools import product

def encode(psi):                       # |psi> -> alpha|000> + beta|111>
    a, b = psi
    enc = np.zeros(8, dtype=complex)
    enc[0b000] = a                     # basis index = three data bits
    enc[0b111] = b
    return enc / np.linalg.norm(enc)

def apply_x_errors(state, error_bits): # inject Pauli X on chosen qubits
    s = state.copy()
    for q in error_bits:
        flipped = np.zeros_like(s)
        for i in range(8):
            j = i ^ (1 << (2 - q))     # flip bit q (leftmost = qubit 0)
            flipped[j] = s[i]
        s = flipped
    return s

def syndromes(state):                  # Z0Z1 and Z1Z2 parity checks
    def zqzr(i, q, r):
        return (1 if ((i >> (2 - q)) & 1) == 0 else -1) * \
               (1 if ((i >> (2 - r)) & 1) == 0 else -1)
    s1 = sum(abs(state[i]) ** 2 * zqzr(i, 0, 1) for i in range(8))
    s2 = sum(abs(state[i]) ** 2 * zqzr(i, 1, 2) for i in range(8))
    return s1 < 0, s2 < 0              # True = odd parity = error present

def correct(state, syn):
    e = []
    if syn[0] and not syn[1]: e = [0]
    elif syn[1] and not syn[0]: e = [2]
    elif syn[0] and syn[1]: e = [1]
    return apply_x_errors(state, e), e

rng = np.random.default_rng(11)
psi = encode([np.sqrt(0.7), np.sqrt(0.3)])
for p in [0.05, 0.10, 0.15, 0.25]:
    trials = 20000
    good = 0
    for _ in range(trials):
        errs = [q for q in range(3) if rng.random() < p]
        noisy = apply_x_errors(psi, errs)
        fixed, _ = correct(noisy, syndromes(noisy))
        overlap = abs(np.vdot(psi, fixed))   # success iff state restored
        if overlap > 0.999:
            good += 1
    print(p, round(good / trials, 4))
```

Theory to verify against: distance-3 repetition fixes any single X error; failure needs ≥2 errors mis-corrected into a third, so logical failure ≈ 3p² − 2p³ (the XXX term maps |000⟩↔|111⟩, detectable by amplitude overlap, not by staying-in-code-space). Verified outputs at 20k trials: p=0.05 → 0.9928 (theory 0.99275), p=0.10 → 0.9733 (theory 0.972), p=0.15 → 0.9379 (theory 0.9365), p=0.25 → 0.8435 (theory 0.84375). The crossing behaviour, protection while p < 50% and degradation beyond it, is the threshold phenomenon in miniature; note the subtlety that the naive "still in code space" check cannot catch triple errors because XXX permutes codewords among themselves.

## How it's done in production

QEC today runs as co-designed hardware-plus-software pipelines rather than library calls: Google's Willow stack streams syndromes from 105 qubits through trained decoders (their July 2026 reinforcement-learning calibration improved logical stability 3.5× and pushed surface-code memory errors below one per 1,000 cycles); IBM's decoder prototype targets real-time operation for LDPC codes on Nighthawk-class processors; Quantinuum's Helios applies high-rate codes across 98 trapped-ion qubits for 50 logical at 2:1. Open-source tooling exists for the software side: Stim (fast stabiliser circuit generation + sampling, billions of rounds/second), PyMatching/MWPM decoders, Riverlane's Deltaflow decode hardware. Failure modes seen in real experiments and sims:

| Symptom | Cause | Fix |
|---|---|---|
| Logical error worsens as you add ancilla checks | Physical error above threshold, or correlated errors between neighbouring qubits | Reduce p (recalibrate), increase check-qubit spacing, model cross-talk explicitly |
| Decoder falls behind the syndrome stream | MWPM latency grows with d; backlog stalls rounds | FPGA/GPU decoding, union-find or neural decoders with bounded latency |
| Logical error rate plateaus despite larger d | Leakage out of the computational space accumulating per cycle | Leakage-reduction units, reset policies, leakage-aware decoders |
| "Logical qubits" claim doesn't survive scrutiny | Marketing: encoded memory without logical gates or fault-tolerant preparation | Ask for: code distance, Λ factor, logical gate set demonstrated, and whether prep/meas are fault-tolerant |
| Simulated overheads look fine, real budgets explode | Magic-state factory footprint ignored; routing between logical cells omitted | Price T-factories and lattice-surgery space-time volume explicitly (Gidney-Ekerå style accounting) |

The honest scoreboard as of mid-2026: memory demonstrations are genuinely below threshold on two platforms; two-logical-qubit gates exist at small scale; nothing yet runs a logical algorithm of useful depth. Roadmaps promise Starling-scale machines by 2029; treat those as engineering commitments with real evidence behind them, not certainties.

## Tradeoffs & when NOT to use it

- **Do not apply QEC thinking to NISQ demos.** Below ~100 logical operations, error mitigation beats correction because even one distance-3 surface-code patch costs ~50+ physical qubits per logical qubit plus constant measurement traffic; mitigation is free by comparison. Correction wins only when circuits grow past what mitigation's exponential shot cost can reach.
- **Do not compare qubit counts across platforms naively.** 1,000 superconducting physical ≠ 1,000 ion physical: connectivity, gate speed (~50 ns vs ~300 μs), and code family change effective capacity by orders of magnitude. The only portable currency is logical operations per dollar-hour at a target error.
- **Surface vs LDPC is a real tradeoff, not progress.** LDPC cuts overhead roughly an order of magnitude but demands long-range couplers and more complex decoding; surface codes waste qubits but map onto planar chips trivially. IBM betting on both (LDPC codes, planar-friendly modules) tells you neither side is settled.
- **When NOT to believe a roadmap date:** when it lacks a published Λ (error-suppression factor), a decoder latency budget, and a magic-state accounting. Those three numbers separate engineering from aspiration; their absence is the tell.

---

## Interview questions

### Q1 — Why can't you just copy a qubit three times and take a majority vote?
**Testing:** whether the no-cloning constraint is load-bearing in your reasoning.
**Answer:** Two blockers: no-cloning forbids copying unknown states (linearity), and quantum errors are continuous, not discrete flips, so "majority" is ill-defined over arbitrary rotations. QEC's fix: spread information non-locally via entanglement, then measure stabiliser parity checks that digitise errors onto Paulis without revealing amplitudes.
**Follow-up trap:** *"How does measuring syndromes avoid collapsing the computation?"* — stabilisers act as identity on the code space, so all codewords are +1 eigenvectors; measurement projects noise-induced subspaces apart while leaving encoded data untouched. Information about the error exists; information about α,β does not.

### Q2 — What exactly did Google's Willow demonstrate, and what did it not?
**Testing:** separating milestone from marketing.
**Answer:** Demonstrated: below-threshold surface-code memory scaling, distance 3→5→7 with logical error per round falling by factor Λ = 2.14 per distance step; logical qubit lifetime exceeding the best physical qubit (~5×); 105 qubits, December 2024. Not demonstrated: logical gates at scale, magic-state injection economics, algorithmic workloads.
**Follow-up trap:** *"Why was below-threshold the historic line?"* — above threshold, adding qubits amplifies noise and scaling fails; below it, the threshold theorem guarantees overhead buys reliability. Every qubit-count estimate for breaking RSA assumes being below threshold; Willow provided the first direct superconducting evidence.

### Q3 — Derive the physical-qubit cost of one logical qubit at target error 10⁻¹² with p = 10⁻³ under the surface code.
**Testing:** can you run the field's central arithmetic cold.
**Answer:** ε_L ≈ 0.1·(100p)^((d+1)/2) with 100p = 0.1: need 0.1^((d+1)/2) ≤ 10⁻¹¹, i.e., (d+1)/2 ≥ 11 → d ≥ 21, round up to odd d=21-25 for margin. Qubits: ≈ 2d² → 882 to 1,250 physical per logical. That ~1000:1 regime is where RSA-2048's millions-of-qubits estimates come from.
**Follow-up trap:** *"What levers shrink this fastest?"* — halving p moves you two steps down the exponent chain (~4× fewer qubits); switching to LDPC codes cuts the constant (~10× claimed by IBM's [[144,12,12]]); better T-factories cut total footprint further. Code distance alone is the blunt instrument.

### Q4 — NISQ: given p₂ = 10⁻³, what circuit depth is actually usable?
**Testing:** the numbers behind "NISQ" as more than a buzzword.
**Answer:** Success ≈ exp(−p₂·d₂Q): depth 100 → ~90%, depth 1000 → ~37%, depth 3000 → ~5%. Practical useful range: hundreds to ~1000 entangling gates before mitigation; error mitigation buys roughly an order of magnitude back at exponential shot cost, not more.
**Follow-up trap:** *"So what were IBM's 2023 'utility' 127-qubit Ising experiments?"* — depth-limited circuits (~60 layers × 2Q gates ≈ few hundred total) plus zero-noise extrapolation, demonstrating state quality beyond brute-force classical simulation for specific observables, not general-purpose advantage; the distinction matters when quoting them.

### Q5 — Explain the threshold theorem and its one commercial implication.
**Answer:** If each component's error rate stays below a code-dependent constant threshold (~1% for surface codes), then increasing code distance suppresses logical error exponentially, so arbitrary-length quantum computation costs only polylogarithmic overhead. Commercial implication: hardware progress is a race below a fixed bar, after which scale converts directly into capability, which is why fidelity milestones move markets more than qubit counts.
**Follow-up trap:** *"Thresholds assume what failure model?"* — local Markovian noise on gates/measurement/memory, no correlated bursts, leakage, or cosmic-ray events that hit many qubits coherently; real devices need mitigation for those, which is why measured Λ < theoretical predictions.

### Q6 — Surface code vs quantum LDPC: give the tradeoff like an architect.
**Answer:** Surface: planar nearest-neighbour checks (weight ≤4), simple decoders, proven scaling, but k=1 per patch and ~2d² qubits per logical, brutal overhead. LDPC ([[144,12,12]] bicycle codes): ~10× lower qubit-per-logical ratio, encodes many logicals per block, but needs six-way long-range connectivity (hence IBM's coupler roadmap) and harder real-time decoding. Choice reduces to your fabrication constraints: planar chips default surface; connectivity-rich platforms (ions, neutral atoms, coupled modules) can afford LDPC.
**Follow-up trap:** *"Which wins for RSA-scale machines?"* — unknown; LDPC's savings compound enormously at width thousands, but its decoder latency and connectivity yield are unproven at scale, which is precisely why IBM runs both tracks and dates Starling conservatively.

### Q7 — What is a magic state and why does everyone count it?
**Testing:** knowledge of the fault-tolerant gate tax.
**Answer:** Cliffords run transversally cheap on most codes, but universality needs non-Clifford T/Toffoli gates, which fault-tolerantly consume specially distilled "magic states" prepared via noisy injection plus distillation circuits. Factories producing these dominate space-time volume historically (>50%), so resource estimates price T-gates like expensive consumables.
**Follow-up trap:** *"Could better codes eliminate factories?"* — some LDPC/holographic proposals make non-Cliffords cheaper transversally, and magic-state cultivation (Gidney 2023+) cuts factory size several-fold, but nothing eliminates the tax; every credible estimate still carries explicit magic-state lines.

### Q8 — Your team sees logical error plateau at 10⁻³ despite raising distance from 5 to 7. Diagnose.
**Answer:** Plateau means an error source uncorrelated-with-distance dominates: likely leakage out of the computational subspace accumulating per cycle, correlated errors (crosstalk/cosmic-ray events hitting neighbours simultaneously), or decoder mis-modelling of measurement-error correlations. Fixes: leakage-reduction units each cycle, spacetime-aware decoding that treats correlated events, spacing checks away from burst-prone regions.
**Follow-up trap:** *"Why doesn't the threshold theorem cover this?"* — it assumes independent local noise; correlated events violate locality, effectively acting like errors of weight >t that distance cannot fix. Real machines add engineering mitigations rather than pure code distance.

### Q9 — Quantinuum claims 50 logical qubits at 2:1 encoding; IBM implies ~12:1 minimum. Reconcile.
**Testing:** reading vendor claims critically against code theory.
**Answer:** Different codes for different hardware: Quantinuum uses high-rate small blocks exploiting all-to-all ion connectivity (2 physical per logical for memory-level protection, shallow logical operations), trading circuit depth; IBM's [[144,12,12]] gives distance-12 protection at 12:1 gross for superconducting plans. Neither number means "logical qubit ready for algorithms": ask what logical gate set runs fault-tolerantly and at what additional ancilla cost.
**Follow-up trap:** *"Which claim would you trust more for 2030 planning?"* — neither as stated; demand the triple: demonstrated Λ, decoder latency at their distance, and magic-state accounting. Quantinuum's numbers suit near-term small logical demos; IBM's suit algorithm-scale budgeting.

### Q10 — What do error mitigation and error correction each buy, and when do they cross over?
**Answer:** Mitigation (ZNE, PEC) reduces *bias* post-hoc at exponential shot-cost growth: practical to ~10⁻²-10⁻³ bias on depth ≤~100 circuits, useless beyond because shots explode. Correction changes scaling: exponential reliability growth with distance at linear qubit overhead, viable only once per-qubit p < threshold and you can afford ≥50-100 physical/logical. Crossover sits around circuits needing >~10⁴ reliable logical ops, i.e., exactly where interesting algorithms begin.
**Follow-up trap:** *"Why not always correct then?"* — one distance-3 patch costs dozens of qubits plus continuous syndrome traffic and decoding infrastructure; for sampling-class experiments mitigation returns answers at a fraction of the hardware. Economics decides, not ideology.

### Q11 — How does QEC change the RSA threat timeline specifically?
**Testing:** connecting this module to T23-algorithms' estimates.
**Answer:** Shor's logical-qubit requirement (thousands for RSA-2048 arithmetic width) multiplies by per-logical overhead (~1000+ at current p) and adds T-factory footprint: Gidney-Ekerå's 20M physical qubits / 8 hours. Faster-than-projected fidelity improvements or LDPC adoption shrink the multiplier; slower decoherence progress pushes dates right. The timeline is therefore an error-correction-engineering forecast, which is why PQC deadlines (2030 deprecation / 2035 disallowance drafts) hedge with margin.
**Follow-up trap:** *"Single biggest lever?"* — two-qubit fidelity below ~10⁻⁴ would collapse distances needed (each halving of p saves ~4× qubits), compounding across the whole machine; it is worth more than any single architectural cleverness.

### Q12 — Design the syndrome-decoding subsystem like a systems engineer.
**Testing:** whether you treat QEC as streaming systems design.
**Answer:** Input: syndrome stream at one bit-pair per check per microsecond round (a distance-25 patch emits ~1200 bits/round). Requirements: decode latency < round time sustained, bounded memory (no backlog), throughput matching multiple patches concurrently. Architecture: FPGA/ASIC front-end running union-find or lookup-heavy MWPM approximations for O(1)-ish latency, host-side retraining loops for neural decoders, telemetry on marginal cases. SLOs: p99 latency under round time, drop rate zero (drops corrupt logic silently).
**Follow-up trap:** *"What happens on backlog overflow?"* — computation must stall (hold rounds) or discard data; stalls extend exposure to memory error quadratically... concretely, idle cycles still accumulate logical error, so backlogs convert directly into logical failure probability, making the decoder a hard-real-time component, not batch analytics.

## Red flags that fail you

- Quoting physical qubit counts as if they were computational capacity.
- No numbers attached to "quantum computers are noisy": missing 10⁻³ gate error, ~1% threshold, 1000:1 overhead.
- Claiming Willow means useful quantum computing arrived, or dismissing it as irrelevant; both miss the actual milestone (below-threshold scaling).
- Believing repetition-code intuition transfers unchanged (no-cloning and phase flips break it).
- Ignoring decoders, magic states, or routing when discussing feasibility ("just add more qubits").
- Treating error mitigation and error correction as substitutes rather than different regimes.

## Cheat card

```
NOISE       T1/T2 ~100-300us (SC), s-min (ions) · 1Q err ~1e-4
            2Q err ~1e-3 · readout ~1e-2 · success ~ exp(-p2*d_2Q)
NISQ BUDGET p2=1e-3: d=100 -> 90%, d=1000 -> 37% · mitigation
            (ZNE/PEC) buys ~10x at exp shot cost, no scaling change
QEC CORE    encode non-local · measure stabilisers (parity only)
            errors digitise to Paulis · data never measured
            [[n,k,d]] corrects t=(d-1)/2 · Shor[[9,1,3]] Steane[[7,1,3]]
SURFACE     [[d^2,1,d]], weight<=4 checks, ~2d^2 phys/logical
            eps_L ~ 0.1(100p)^((d+1)/2) · threshold p_th ~ 1%
            p=1e-3, target 1e-12 => d~25 => ~1250 phys/logical
MILESTONES  Willow Dec 2024: below-threshold, Lambda=2.14, d=7,
            logical beats best physical ~5x · Jul 2026: RL calib
            3.5x stability, mem err <1e-3/cycle
            Quantinuum Helios: 50 logical @ 2:1 (ions)
LDPC        IBM [[144,12,12]]: 12 logical/144 phys (~10x saving)
            needs 6-way connectivity -> Nighthawk/L-coupler modules
DECODER     real-time hard requirement: latency < 1us round;
            MWPM/union-find/neural on FPGA; backlog = silent failure
FT GATES    Clifford cheap/transversal · T/Toffoli = magic states
            factories dominate volume (>50%) · lattice surgery
TIMELINE    IBM Starling 2029: 200 logical/100M gates (LDPC-based);
            Blue Jay 2033: 2000 logical · Google: ~1M phys ~2029+
```

## Sources

- [Google Willow: quantum error correction below the threshold (Nature, Dec 2024)](https://www.nature.com/articles/s41586-024-08449-y) — accessed 2026-08-23
- [IBM Quantum roadmap: large-scale fault tolerance, LDPC codes, decoder prototype](https://www.ibm.com/quantum/blog/large-scale-ftqc) — accessed 2026-08-23
- [IBM press release: modular cryogenic systems connected (Aug 2026)](https://newsroom.ibm.com/2026-08-19-ibm-connects-its-first-modular-cryogenic-systems-in-milestone-toward-fault-tolerant-quantum-computing) — accessed 2026-08-23
- [Quantum roadmaps tracker: logical qubit records, fidelities, 2026 state](https://quantummarketcap.com/roadmap) — accessed 2026-08-23
- [Fowler et al., Surface codes: Towards practical large-scale quantum computation](https://arxiv.org/abs/1208.0928) — accessed 2026-08-23
- [Bravyi et al., High-threshold and low-overhead fault-tolerant quantum memory (bivariate bicycle LDPC)](https://www.nature.com/articles/s41586-024-08170-8) — accessed 2026-08-23

## Changelog
- 2026-08-23 — created

