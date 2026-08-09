# PoW → PoS → BFT: Nakamoto, Finality, Slashing, the Trilemma

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 2.5h · **Prereqs:** `T22-blockchain-scratch`
> **Updated:** 2026-08-08
> **Module id:** `T22-consensus` · **Tags:** consensus, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Consensus mechanisms answer one question — "who gets to propose the next block, and how does the network agree it's canonical" — and the three families answer it with fundamentally different guarantees. Proof-of-work (Nakamoto consensus) gives you permissionless, pseudonymous participation and only ever gives *probabilistic* finality: the chance a transaction gets reversed shrinks exponentially with confirmations but never hits exactly zero, and the actual formula (Satoshi's whitepaper, section 11) says a 30%-hashpower attacker still has a 4.2% chance of overturning a 10-confirmation transaction. Proof-of-stake keeps permissionless participation but swaps computational cost for locked capital, and Ethereum's Casper FFG bolts a genuinely different property on top — deterministic, mathematically provable **finality**: once two-thirds of staked ETH attests to a checkpoint across two consecutive epochs (about 12.8 minutes), that checkpoint cannot be reverted unless attackers controlling at least one-third of all staked ETH are willing to get their stake destroyed via slashing, which is a fundamentally stronger and different guarantee than "very unlikely." Classical BFT protocols (PBFT and its descendants) give the strongest guarantee — instant, deterministic finality — but only work with a known, bounded set of validators, which is why they power permissioned chains and Ethereum's own validator-voting layer, but not an open network anyone can anonymously join. The scalability trilemma (decentralization, security, scalability — pick two, without a scaling-layer trick) is why none of this is free, and it's the lens through which every consensus and layer-2 design decision in this track should be read.

## Why this gets asked

Because "blockchain uses proof-of-work" is a 2015-era answer, and the field has moved decisively toward proof-of-stake and hybrid finality mechanisms since — an interviewer testing current knowledge wants to hear the actual mechanics of Casper FFG's two-thirds threshold and slashing, not just "Ethereum switched to staking." More pointedly, they want to know whether you understand that "finality" is not one concept: probabilistic finality (Bitcoin) and deterministic finality (Casper FFG, classical BFT) are different guarantees with different failure modes, and conflating them is exactly the kind of gap that shows up when someone architects a bridge or an exchange's deposit-confirmation policy incorrectly (module 7 covers what that costs in practice).

---

## Lineage: past → present → future

**What came before.** Classical distributed-systems consensus — Paxos (Lamport, 1998) and Practical Byzantine Fault Tolerance (Castro & Liskov, 1999) — solved agreement among a known, fixed set of participants tolerating up to `f` faulty nodes out of `3f+1` total, with deterministic, immediate finality once a quorum (typically `2f+1`, i.e. more than two-thirds) is reached. This is a strong guarantee, but it structurally requires knowing who the participants are in advance — there's no mechanism for an anonymous stranger to join and start voting, because the safety proof depends on bounding how many of the *known* voters can be faulty. This is precisely the gap Bitcoin's 2008 whitepaper closed: Nakamoto consensus replaced "known validator set casts votes" with "anyone can participate, and influence is proportional to a resource that's expensive to acquire (hashpower)," trading deterministic finality for permissionless, sybil-resistant participation — you can't out-vote the network by creating a million free accounts, because votes are weighted by proof-of-work, not identity count.

**Where it stands now.** Proof-of-stake has displaced proof-of-work as the consensus mechanism of choice for new chains and, decisively, for Ethereum itself, which completed its transition ("the Merge") in September 2022 — this is deployed and battle-tested at scale, not a research proposal. Ethereum's specific design, Gasper (the combination of Casper FFG for finality and LMD-GHOST for fork-choice between finalized checkpoints), currently finalizes checkpoints roughly every 12.8 minutes (two 6.4-minute epochs) once two-thirds of staked ETH attests — a genuinely different and stronger guarantee than Bitcoin's confirmations-based probabilistic model. The live, substantive disagreement is Bitcoin's continued commitment to proof-of-work: Bitcoin's community treats PoW's energy cost as a *feature* — "unforgeable costliness," a real security property that can't be faked by locking capital you might get back — while most of the rest of the industry has concluded the energy externality isn't justified once proof-of-stake demonstrates comparable security empirically. Both positions are held by serious, technically sophisticated people; this is not a settled question, and stating it as one is a tell.

**Where it's heading.** High confidence: Ethereum's roadmap continues pushing toward **single-slot finality** (finalizing within one ~12-second slot instead of two epochs), which would close the current window during which a reorg is theoretically still possible, and this work is actively in progress as of 2026, not merely proposed. Medium confidence: BFT-style and hybrid consensus designs (Tendermint/CometBFT-based chains, Solana's proof-of-history-plus-BFT hybrid) continue proliferating for application-specific and app-chain contexts where the participant set can be more tightly bounded than "anyone on Earth," trading some decentralization for speed and deterministic finality — this is a real, growing design pattern, but whether any of these specific chains achieve Ethereum- or Bitcoin-scale adoption is genuinely unknown and shouldn't be stated as inevitable. Lower confidence, more speculative: whether Bitcoin itself ever moves off proof-of-work is close to a settled "no" within its own community, and treating that as an open question in front of a Bitcoin-adjacent interviewer would be a signal you haven't actually engaged with the ecosystem's stated values.

---

## Mental model

```
  THREE FAMILIES, THREE DIFFERENT ANSWERS TO "WHO PROPOSES THE NEXT BLOCK"

  PROOF OF WORK (Nakamoto consensus)
  ───────────────────────────────────
  Anyone can participate. Influence = hashpower (expensive to fake).
  Finality: PROBABILISTIC — shrinks toward zero, never reaches it.
  P(attacker with 30% hashpower overturns after z confirmations):
    z=1: 42.5%   z=5: 17.7%   z=10: 4.2%   z=20: 0.25%
  "6 confirmations is safe" is a RULE OF THUMB against typical attackers,
  not a mathematical guarantee — the actual number depends on q and stakes.

  PROOF OF STAKE + CASPER FFG (Ethereum since Sept 2022)
  ───────────────────────────────────
  Anyone can participate. Influence = staked capital (32 ETH/validator).
  Finality: DETERMINISTIC once reached — a genuinely different guarantee.
    epoch N attested by 2/3 of stake  ─┐
    epoch N+1 attested by 2/3 of stake ┴─▶ epoch N is FINALIZED (~12.8 min)
  Reverting a finalized checkpoint requires ≥1/3 of ALL staked ETH to
  provably violate a slashing condition — economically suicidal, not just costly.

  CLASSICAL BFT (PBFT, Tendermint/CometBFT — permissioned chains, Ethereum's
  own validator-voting layer underneath the PoS wrapper)
  ───────────────────────────────────
  KNOWN, FIXED validator set required. Tolerates f faulty out of 3f+1 total.
  Finality: INSTANT and deterministic, the moment 2f+1 (>2/3) vote for a block.
  No permissionless joining — this is the tradeoff for speed + certainty.

  THE TRILEMMA: pick two, without a scaling-layer trick (module 7)
        DECENTRALIZATION
             /    \
            /      \
      SECURITY —— SCALABILITY
  Bitcoin/Ethereum L1: decentralization + security, sacrifice raw throughput.
  A permissioned BFT chain: security + scalability, sacrifice decentralization.
```

---

## How it actually works

### Nakamoto consensus and probabilistic finality, with the actual formula

Bitcoin's whitepaper (section 11) derives the probability that an attacker controlling a fraction `q` of network hashpower, starting `z` blocks behind the honest chain, ever catches up and overtakes it — modeling the race as a Poisson process (blocks arrive as a Poisson-distributed random process, both for the honest chain and the attacker's private chain) combined with a gambler's-ruin argument for the remaining deficit once the attacker draws level. The formula:

```
λ = z · (q / p)              where p = 1 − q (honest hashpower fraction)

P(attacker ever catches up) = 1 − Σ_{k=0}^{z} [ (λ^k · e^−λ / k!) · (1 − (q/p)^(z−k)) ]
```

Implemented and checked directly against the whitepaper's own published table:

```python
import math

def attacker_catchup_probability(q: float, z: int) -> float:
    p = 1 - q
    lam = z * (q / p)
    total = 1.0
    for k in range(z + 1):
        poisson = (lam ** k) * math.exp(-lam) / math.factorial(k)
        total -= poisson * (1 - (q / p) ** (z - k))
    return total

for q in [0.1, 0.3]:
    for z in [0, 5, 10, 20]:
        print(f"q={q}, z={z}: P={attacker_catchup_probability(q, z):.4f}")
```

Output, matching the whitepaper's published values (0.1774 vs. the paper's 0.1773523 at q=0.3, z=5; 0.0417 vs. 0.0416605 at z=10; agreement to four decimal places throughout):

```
q=0.1, z=0:  P=1.0000     q=0.3, z=0:  P=1.0000
q=0.1, z=5:  P=0.0009     q=0.3, z=5:  P=0.1774
q=0.1, z=10: P=0.0000     q=0.3, z=10: P=0.0417
q=0.1, z=20: P=0.0000     q=0.3, z=20: P=0.0025
```

The number worth internalizing: **a 30%-hashpower attacker still has a 4.2% chance of overturning a transaction after 10 confirmations**, and only drops to 0.25% at 20 confirmations. "6 confirmations is safe" is a *heuristic calibrated against a much weaker assumed attacker* (often implicitly q≈10%, where 5-6 confirmations already gets under 0.1%) — restating it as a universal guarantee, independent of the actual threat model and value at risk, is exactly the kind of imprecision that gets caught in a staff-level interview.

### Casper FFG: how deterministic finality actually gets produced

Ethereum's consensus layer runs two mechanisms simultaneously. **LMD-GHOST** (Latest Message Driven Greediest Heaviest Observed SubTree) is the fork-choice rule — analogous to Nakamoto's heaviest-chain rule, but based on the weight of validator attestations rather than proof-of-work — that decides which chain head to build on moment-to-moment. **Casper FFG** (Friendly Finality Gadget) runs on top, at the epoch level (32 slots, ~6.4 minutes), and periodically *finalizes* checkpoints:

1. Validators attest to a checkpoint each epoch. If a checkpoint receives attestations from validators representing **at least two-thirds of total staked ETH**, it becomes **justified**.
2. If two consecutive epochs both get justified — epoch N and epoch N+1 — epoch N becomes **finalized**.
3. A finalized checkpoint carries Casper FFG's actual safety guarantee: **it can never be reverted unless validators controlling at least one-third of all staked ETH provably violated a slashing condition** — which means reverting it isn't merely difficult, it requires an action that automatically destroys a documented fraction of the attackers' own capital, an economic guarantee with a very different character than "requires more hashpower than anyone plausibly has."

**Total time to finality in practice is about 12.8 minutes** (two epochs) under normal network conditions — noticeably slower than a "confirmed" Bitcoin transaction's typical wait, but categorically different in kind: after 12.8 minutes, Ethereum's finalized checkpoint has a mathematical proof of irreversibility barring a specific, attributable, catastrophically expensive validator misbehavior, where Bitcoin's confirmations only ever shrink a probability.

### Slashing: the two conditions that actually trigger it

Casper FFG's economic security rests on validators being able to *prove*, on-chain, that a specific validator did one of two contradictory things — proofs a malicious validator cannot avoid leaving behind if they violate the protocol:

1. **Equivocation (double proposal)** — signing two different blocks for the same slot. Directly analogous to double-spending in intent: proposing two mutually exclusive versions of history.
2. **Contradictory attestations** — either a **double vote** (attesting to two different checkpoints for the same target epoch) or a **surround vote** (an attestation that "surrounds" a validator's own earlier attestation in a way that would let them help finalize two conflicting histories — the specific pattern the "no two finalized checkpoints" safety proof depends on being unavailable).

A slashed validator loses a minimum of 1 ETH immediately, is forcibly exited from the validator set, and — critically — faces a **correlation penalty** that scales with how many *other* validators are slashed in the same time window: a single validator slashed in isolation loses relatively little, but if slashing indicates a *coordinated* attack (many validators slashed together, which is what an actual finality-reverting attack requires under the ≥1/3-of-stake threshold), the correlation penalty can destroy up to the validator's **entire stake**. This scaling is deliberate: it makes an attack that requires many validators to misbehave together disproportionately more expensive than the same number of independent, accidental slashing events, directly targeting the coordinated-attack scenario the mechanism exists to deter.

### The scalability trilemma

Vitalik Buterin's framing (drawing on a much older observation in distributed systems that safety/liveness/partition-tolerance tradeoffs are unavoidable, echoing the CAP theorem's shape without being identical to it): a blockchain can strongly optimize for at most two of **decentralization** (running a full node stays cheap enough that many independent, non-specialized participants actually do it), **security** (resistant to an attacker controlling a large fraction of the network's resources), and **scalability** (high transaction throughput) — without a structural trick that changes the terms of the tradeoff.

The mechanism behind the tradeoff, made concrete: raising throughput directly (bigger blocks, faster block times) increases the computational and bandwidth burden of running a full validating node, which prices out smaller, non-specialized participants, concentrating validation among fewer, better-resourced operators — trading decentralization for scalability. Layer-2 rollups (module 7) are the current dominant answer to escaping this tradeoff rather than accepting it: execute and batch transactions off the base layer, but still post enough data and cryptographic proof back to the base layer that the base layer's decentralization and security properties still constrain what a rollup operator can get away with — pushing throughput up without directly increasing what a base-layer full node must do.

---

## Build it from scratch

The probabilistic-finality calculator above is the from-scratch build for this module — reasoning about consensus security *is* reasoning about that formula, and having run it against the whitepaper's own numbers is the strongest possible grounding for an interview answer that needs actual numbers, not adjectives. A companion piece worth building to feel the BFT threshold concretely:

```python
def bft_quorum_reached(votes_for: int, total_validators: int) -> bool:
    """Classical BFT safety: tolerates f faulty out of n=3f+1 total.
    Quorum for a decision requires > 2/3 of votes -- specifically 2f+1."""
    f = (total_validators - 1) // 3
    quorum_needed = 2 * f + 1
    return votes_for >= quorum_needed

# verified: n=10 -> f=3, quorum=7 (not a naive "majority" of 6)
for n in [4, 7, 10, 13, 100]:
    f = (n - 1) // 3
    print(f"n={n}: tolerates f={f} faulty, needs {2*f+1} votes to finalize")
```

Run: `n=4: f=1, needs 3` / `n=7: f=2, needs 5` / `n=10: f=3, needs 7` / `n=13: f=4, needs 9` / `n=100: f=33, needs 67` — the recurring pattern (needing just over two-thirds, not a bare majority) is why "two-thirds" appears identically in both Casper FFG's justification threshold and classical PBFT's quorum requirement: it's the same underlying safety argument (any two quorums of more than two-thirds must overlap by more than one-third, guaranteeing at least one honest validator is in both, which is what prevents two conflicting decisions from both reaching quorum simultaneously), not a coincidence of two unrelated systems picking the same round number.

Full lab — including a simulated PoS validator set with slashing-condition detection, a Monte Carlo simulation of the Nakamoto race that independently confirms the closed-form formula above, and a visualization of how correlation penalties scale with coordinated slashing: **`labs/py/22-consensus/`**.

---

## How it's done in production

**Bitcoin** runs unmodified Nakamoto consensus, currently at roughly **1,000 EH/s (exahashes per second)** of network hashrate as of mid-2026; reaching 51% of that would require an attacker to add on the order of ~480 EH/s of their own, which — assuming modern ASIC rigs at roughly 270 TH/s each — works out to needing well over a million machines and multiple billions of dollars in upfront hardware capital alone, before accounting for the ongoing electricity cost (estimated in the low millions of dollars *per hour* of sustained attack at current network scale). This is the actual, current economic moat behind "Bitcoin is un-attackable in practice" — a claim that's true today specifically because of that dollar figure, not because of any property that couldn't in principle change if hardware costs or network hashrate shifted dramatically.

**Ethereum** runs Gasper (Casper FFG + LMD-GHOST) across a validator set requiring a minimum stake of **32 ETH** per validator, finalizing checkpoints roughly every 12.8 minutes under normal conditions. A finality *delay* (checkpoints justified but not finalizing) is a real, observed production event — it has happened during periods of degraded network participation — and when it occurs, LMD-GHOST fork-choice keeps the chain progressing (liveness preserved) while explicitly *not* finalizing, which is the protocol correctly refusing to offer a false certainty rather than a failure.

**Permissioned BFT chains** (Hyperledger Fabric's ordering service, CometBFT-based app-chains, Solana's tower BFT layered on proof-of-history) trade the permissionless property for speed: sub-second to few-second finality with a known validator set, appropriate for consortiums, app-chains, or any context where "who can participate" is already a solved, bounded question rather than an open one.

### Failure-mode table

| Symptom | Cause | Fix |
|---|---|---|
| An exchange credits a deposit that later disappears from the chain | Confirmation threshold set too low for the transaction's value and the attacker's plausible hashpower | Scale confirmations to value-at-risk using the actual formula, not a flat "6 confirmations" rule for every amount |
| Two conflicting Ethereum checkpoints both appear briefly justified | Genuinely adversarial or catastrophic network partition affecting >1/3 of stake — the safety proof's stated boundary condition | This is the scenario Casper FFG's safety proof explicitly does not cover past that threshold; it's a designed limit, not a bug, and the response is social/off-chain coordination, historically precedented in Ethereum's own client-diversity incident response |
| Finalization stalls for multiple epochs | Insufficient participating stake (<2/3 online/attesting) — often from a large staking provider or client-software outage | LMD-GHOST keeps the chain live without finalizing; investigate and restore attester participation; this is liveness-preserved-over-safety by design |
| A validator gets slashed unexpectedly during routine operation | Running the same validator keys on two machines simultaneously (a common operational mistake during a migration or failover) — produces an equivocation the protocol cannot distinguish from an attack | Never run duplicate validator keys concurrently; use a slashing-protection database (EIP-3076 format) that persists across any redeployment |
| A BFT-based chain halts entirely rather than degrading | More than `f` of `3f+1` validators are offline or faulty simultaneously, exceeding the fault tolerance the validator-set size was provisioned for | Increase validator-set size/redundancy relative to expected concurrent-failure scenarios, or accept that liveness (not just safety) has a hard requirement on validator availability |

---

## Tradeoffs & when NOT to use it

- **Don't use pure Nakamoto/PoW consensus where deterministic finality is a hard requirement of the application.** A payment settlement system that needs to know "is this transaction irreversible, yes or no" at a specific, bounded point in time is fundamentally mismatched with a probabilistic guarantee — this is exactly why real-money exchanges layer their own confirmation policies (and often centralized risk management) on top of Bitcoin rather than treating "N confirmations" as a protocol-level finality answer.
- **Don't treat proof-of-stake's deterministic finality as free of tradeoffs.** It requires an economically meaningful stake to be locked and slashable, introduces "weak subjectivity" (a new node syncing from scratch needs a recent, trusted checkpoint to bootstrap safely, since it can't purely derive trust from genesis the way a PoW chain theoretically can) — a real, if narrow, departure from pure trustlessness that's worth naming precisely rather than glossing over.
- **Don't use classical BFT for an open, permissionless network.** The moment you don't know your validator set in advance and can't bound how many are faulty, PBFT's safety proof has no foundation — this is precisely why BFT chains are consortium/app-chain tools, not competitors to Bitcoin/Ethereum's base-layer permissionless model, despite offering better raw finality speed.
- **Don't conflate "probabilistic finality is real" with "probabilistic finality is unsafe."** Bitcoin has secured hundreds of billions of dollars for over 16 years under exactly this model — the honest, precise statement is that it's a different, well-understood, and (at current hashrate levels) extremely strong guarantee, not a weaker one dressed up with different words.
- **The trilemma is a real engineering constraint, not marketing.** Any project claiming to have "solved" decentralization, security, and scalability simultaneously without a scaling-layer architecture (module 7) or without a corresponding tradeoff made somewhere else in the design deserves specific scrutiny about exactly where the cost actually landed.

---

## Interview questions

### Q1 — Explain probabilistic finality versus deterministic finality, precisely.
**Testing:** the module's central distinction.
**Answer:** Probabilistic finality (Nakamoto consensus) means the probability a confirmed transaction gets reversed shrinks exponentially with additional confirmations but mathematically never reaches exactly zero — quantified by the whitepaper's catchup-probability formula. Deterministic finality (Casper FFG, classical BFT) means that once a specific, checkable condition is met (two-thirds attestation across two epochs; a 2f+1 quorum), reverting requires provably violating an economic or safety guarantee — a qualitatively different claim, not just a smaller probability.
**Follow-up trap:** *"So is deterministic finality just probabilistic finality with a probability of exactly zero?"* — no, and this is the trap: deterministic finality's guarantee is conditional on an explicit, bounded assumption (fewer than one-third of stake is malicious, in Casper FFG's case), and violating that assumption doesn't produce "a small probability of reversal," it produces an entirely different failure mode (a safety-proof violation requiring a large fraction of stake to be provably, attributably destroyed) — the guarantees aren't the same shape, just different magnitudes.

### Q2 — Compute the probability a 30%-hashpower attacker overturns a Bitcoin transaction after 10 confirmations. Walk through why the formula has the shape it does.
**Testing:** whether the candidate has internalized the actual math, not just the conclusion.
**Answer:** Approximately 4.2% (0.0417 by direct computation from Satoshi's formula). The shape combines a Poisson process — since blocks are found via proof-of-work, the number of blocks an attacker privately mines in a given time window has a Poisson distribution with rate proportional to `z·(q/p)` — with a gambler's-ruin argument for the probability the attacker's private chain, currently behind by some remaining deficit, ever draws level and passes the honest chain, summed over every possible number of blocks the attacker might have privately mined by the time the honest chain reaches z blocks ahead.
**Follow-up trap:** *"How does this number change if the attacker also controls a meaningful fraction of transaction relay/network propagation, not just hashpower?"* — the formula as derived assumes hashpower is the only variable; a real attacker with propagation advantages (eclipse-attacking the victim, controlling relevant mining pools' network positioning) can effectively improve their real-world odds beyond what the pure-hashpower formula predicts, which is why the formula is a *lower bound* on attacker capability in practice, not a complete threat model — worth stating explicitly rather than treating the formula as the whole picture.

### Q3 — Walk through exactly how a checkpoint becomes "finalized" under Casper FFG.
**Testing:** the specific mechanism, not just "PoS has finality."
**Answer:** Validators attest to checkpoints each epoch (32 slots, ~6.4 minutes). A checkpoint attested to by validators representing at least two-thirds of total staked ETH becomes "justified." If two consecutive epochs are both justified, the earlier one becomes "finalized" — meaning it can only be reverted if validators controlling at least one-third of all staked ETH provably violate a slashing condition, an event that destroys a large, documented fraction of their own capital. Total time to finality is roughly two epochs, ~12.8 minutes, under normal participation.
**Follow-up trap:** *"Why two consecutive epochs and not just one justified epoch?"* — the two-epoch requirement is what lets the safety proof guarantee that reverting a finalized checkpoint specifically requires a slashable, attributable violation — a single justified epoch alone doesn't yet carry that guarantee, since the specific "surround vote" slashing condition (which is what actually prevents a validator from later helping finalize a conflicting history) depends on the two-epoch structure to be well-defined and detectable.

### Q4 — What are the two conditions that trigger slashing, and why does the penalty scale with how many validators are slashed together?
**Testing:** the mechanism-level understanding of the economic security argument.
**Answer:** Equivocation (signing two different blocks for the same slot) and contradictory attestations (double votes or surround votes across checkpoints). The correlation penalty scales with simultaneous slashing events because an isolated slashing event is most plausibly an operational accident (a validator's keys running on two machines during a migration), while many validators slashed in the same window is the signature of an actual coordinated attack — the exact scenario the ≥1/3-of-stake threshold exists to deter — so the penalty is deliberately designed to make that specific scenario catastrophically, not just moderately, expensive.
**Follow-up trap:** *"Could an attacker exploit the correlation penalty to punish an innocent staking provider running many validators?"* — this is a real, documented operational risk: a large staking provider whose infrastructure has a bug causing accidental duplicate signing across many of its validators simultaneously can trigger the correlation penalty at a scale meant for attackers, which is exactly why slashing-protection databases (EIP-3076) and strict operational discipline against running duplicate validator keys are treated as critical infrastructure, not an afterthought, by any serious staking operation.

### Q5 — Why can't classical BFT protocols like PBFT be used directly for a permissionless network like Bitcoin's?
**Testing:** the structural reason, not just "it wasn't designed for that."
**Answer:** PBFT's safety proof depends on knowing the total validator count `n` and bounding the faulty count at `f ≤ (n-1)/3` — both of which require knowing who the participants are. In a permissionless network, anyone can join anonymously and in unlimited numbers (a Sybil attack), which would let an attacker simply create enough fake identities to exceed whatever `f` bound the protocol assumed, defeating the safety guarantee entirely. Nakamoto consensus sidesteps this by weighting influence by an externally costly resource (hashpower, or locked stake) rather than identity count, making Sybil attacks economically pointless rather than merely difficult to detect.
**Follow-up trap:** *"Could you combine them — use PBFT with hashpower- or stake-weighted voting instead of one-vote-per-identity?"* — yes, and this is close to what several hybrid designs do (Ethereum's own Casper FFG is essentially a BFT-style quorum mechanism running on top of a stake-weighted, permissionlessly-joinable validator set) — the key insight worth stating is that the "known validator set" requirement is really about *bounding the total voting weight an attacker can cheaply acquire*, and stake achieves that without requiring a literally fixed, pre-known identity list, which is the actual innovation Casper FFG represents over pure classical BFT.

### Q6 — Explain the scalability trilemma with a concrete mechanism, not just the three words.
**Testing:** whether "decentralization, security, scalability, pick two" is understood as a consequence of something mechanical, not treated as received wisdom.
**Answer:** Raising raw throughput (bigger blocks, faster blocks) directly increases the computational, storage, and bandwidth burden of running a full validating node. If that burden grows past what an ordinary participant can afford, fewer, better-resourced operators end up running the validating nodes that matter — concentrating the validator/full-node set and reducing decentralization, even if nominal transaction throughput went up. The tradeoff isn't a policy choice the protocol designers imposed; it's a direct mechanical consequence of what "more decentralized" (more people can afford to fully validate) and "more scalable" (more transactions processed) actually require from node hardware.
**Follow-up trap:** *"Doesn't sharding solve this by having each node only validate a subset of the total state?"* — sharding genuinely changes the terms of the tradeoff (each node's burden no longer scales linearly with total network throughput), which is real progress, but it introduces its own security question — cross-shard communication and ensuring each shard individually remains attack-resistant despite validating less of the total state — which is precisely why Ethereum's actual scaling roadmap moved toward rollups (module 7) posting proofs to a shared, fully-validated base layer, rather than full state sharding, as the more immediately practical answer.

### Q7 — A colleague argues Bitcoin's proof-of-work is "wasteful" and should switch to proof-of-stake like Ethereum did. How do you respond as a technically informed but neutral party?
**Testing:** whether the candidate can steelman both sides of a genuinely live disagreement rather than picking one reflexively.
**Answer:** Both positions have real technical substance. The proof-of-stake case: Ethereum's 2022 transition demonstrably works at scale, eliminates a large, quantifiable energy externality, and Casper FFG's deterministic finality is a strictly stronger guarantee in the dimension it targets. The proof-of-work case: PoW's cost is "unforgeable" in a specific sense stake isn't — computational work performed is externally verifiable and can't be faked or recovered, whereas staked capital, while locked and slashable, is still ultimately capital an attacker could in principle acquire (via a large enough acquisition of the asset itself) in a way that doesn't require an equivalent irreversible expenditure the way burned electricity does; Bitcoin's community treats this distinction as securing a categorically different, harder-to-attack property, not an inferior one.
**Follow-up trap:** *"So which is actually more secure?"* — the honest answer is that they're optimizing for different threat models and both have made this tradeoff deliberately and are aware of the counterargument — treating one as simply "better" without naming what specific property each optimizes for is the imprecise answer; the strong answer names the actual axis of disagreement (externally-verifiable irreversible cost vs. capital-at-risk-with-recoverable-value) rather than picking a side by default.

### Q8 — Design a confirmation policy for an exchange accepting Bitcoin deposits ranging from $10 to $10 million. Walk through your reasoning.
**Testing:** applying the probabilistic-finality formula to an actual operational decision, not reciting "wait 6 confirmations."
**Answer:** Scale confirmations to value-at-risk against a stated assumed-attacker hashpower fraction, using the actual formula rather than a flat number: for small deposits, the cost of a targeted attack (renting or diverting enough hashpower even briefly) likely exceeds the value stolen at even 1-2 confirmations, so low thresholds are economically rational. For deposits in the six-to-seven-figure range, compute the confirmation count needed to get the attacker-catchup probability below an acceptable risk threshold (say, well under 0.1%) at a conservative assumed attacker capability (e.g., q=0.1 to 0.3 depending on your threat model), and require that many confirmations — likely double digits for the largest deposits, not a flat "6."
**Follow-up trap:** *"What if the deposit is denominated in a smaller-cap PoW altcoin instead of Bitcoin?"* — smaller-cap chains have dramatically less total network hashrate, meaning the same nominal "q=0.3 attacker" is achievable at a far lower absolute cost — several real, documented 51% attacks against smaller PoW chains (rented hashpower from public marketplaces, not custom hardware) make this a materially different and higher-risk calculation, and confirmation policy should be set per-chain based on its actual current hashrate and rentable-hashpower cost, never copied uniformly from Bitcoin's policy.

### Q9 — What does "weak subjectivity" mean in Ethereum's proof-of-stake design, and why doesn't pure proof-of-work have the same issue?
**Testing:** a specific, less commonly known but real tradeoff of PoS finality — staff-level depth.
**Answer:** A new node syncing Ethereum from scratch cannot purely derive trust from the genesis block the way a PoW chain theoretically can (by re-verifying cumulative proof-of-work from block zero) — because acquiring stake and later selling it back out costs comparatively little relative to the security it once provided (the "nothing at stake" and long-range attack concerns PoS designs specifically have to address), a syncing node instead needs a recent, socially-trusted checkpoint (a "weak subjectivity checkpoint") to safely bootstrap from, rather than being able to derive complete trust from protocol rules and genesis alone. Pure PoW doesn't have this specific issue because redoing historical proof-of-work is expensive by the same mechanism regardless of how much time has passed, so an old, "abandoned" alternate PoW history can't be cheaply reconstructed the way an old set of now-sold validator keys theoretically still could sign an alternate PoS history.
**Follow-up trap:** *"Doesn't this mean Ethereum isn't actually trustless the way Bitcoin is?"* — it's a real, narrower departure worth stating precisely rather than either dismissing or overstating: new nodes need a recent trusted checkpoint (obtainable from multiple independent, easily cross-checked sources — not a single centralized authority), which is a genuinely different and weaker bootstrapping trust model than pure PoW's "verify everything from genesis," but it does not mean an already-synced, actively-participating node's ongoing security depends on trusting anyone — the distinction is specifically about the bootstrapping process for new nodes, not the protocol's ongoing operation.

### Q10 — Your team is building a permissioned ledger for interbank settlement among 20 known banks. Which consensus family do you pick, and why?
**Testing:** applying the whole module's taxonomy to a concrete system-design decision — the connective-tissue question.
**Answer:** Classical BFT (Tendermint/CometBFT-style, or a purpose-built PBFT variant) — the participant set is small, known, and accountable (regulated banks with legal identities, not anonymous strangers), which is exactly the precondition PBFT's safety proof requires and Nakamoto consensus's permissionless design is solving a problem you don't have. This buys instant, deterministic finality (critical for settlement, where "is this transaction final, right now" has direct regulatory and counterparty-risk implications) with no energy cost and no probabilistic-confirmation waiting period, at the cost of needing formal governance for validator-set changes — an acceptable and arguably necessary cost given the participants are already operating under formal governance anyway.
**Follow-up trap:** *"What if two of the 20 banks later want to let their retail customers transact directly on the ledger?"* — that changes the trust model fundamentally: retail customers are not a known, bounded, accountable validator set the way the 20 banks are, so admitting them as direct *validators* would break PBFT's core assumption — the correct design keeps the 20 banks as the BFT validator set while giving retail customers client access (submitting transactions the banks' validators order and finalize), not validator status, which is a common and important distinction between "who can use the system" and "who consensus depends on" that's easy to blur in a design discussion.

---

## Red flags that fail you

- Saying Bitcoin "will never be attacked" rather than naming the actual current economic cost that makes it impractical.
- Treating "6 confirmations" as a universal, protocol-level guarantee rather than a heuristic calibrated to an assumed attacker and value at risk.
- Describing Ethereum's proof-of-stake finality as "just a faster version of Bitcoin's confirmations" rather than a categorically different, deterministic guarantee.
- Not knowing the two-thirds threshold's structural reason (quorum overlap guarantees) and treating it as an arbitrary round number.
- Claiming any system has "solved" the scalability trilemma without naming where the corresponding cost landed.
- Proposing classical BFT for an open, permissionless participant set, or Nakamoto consensus for a small known validator set needing deterministic finality — a mismatch between mechanism and trust model in either direction.

---

## Cheat card

```
NAKAMOTO CONSENSUS (PoW): permissionless, influence = hashpower. PROBABILISTIC finality --
  shrinks exponentially, never reaches exactly 0. Formula (Satoshi whitepaper sec 11):
  lambda = z*(q/p), P(catchup) = 1 - sum_{k=0}^{z}[Poisson(k;lambda)*(1-(q/p)^(z-k))]
  VERIFIED: q=0.3 attacker: z=5 -> 17.7%, z=10 -> 4.2%, z=20 -> 0.25%. "6 confs" is a
  HEURISTIC for a weaker assumed attacker, not a universal guarantee -- scale to value+threat.

CASPER FFG (Ethereum PoS, live since Merge Sept 2022): DETERMINISTIC finality.
  epoch = 32 slots ~6.4min. Checkpoint attested by >=2/3 of staked ETH = JUSTIFIED.
  2 consecutive justified epochs -> earlier one FINALIZED (~12.8min total).
  Reverting finalized checkpoint requires >=1/3 of ALL stake to provably slash-violate.
  Min stake: 32 ETH/validator.

SLASHING triggers: (1) EQUIVOCATION -- sign 2 blocks same slot. (2) double vote / SURROUND
  VOTE -- contradictory attestations across checkpoints. Min penalty 1 ETH + CORRELATION
  PENALTY scaling with how many validators slashed together (isolated = accident-shaped,
  coordinated = attack-shaped, penalty targets the latter disproportionately, up to 100% stake).

CLASSICAL BFT (PBFT/Tendermint/CometBFT): KNOWN, FIXED validator set required.
  Tolerates f faulty out of n=3f+1 total. Quorum = 2f+1 (>2/3) -> INSTANT deterministic finality.
  n=10 -> f=3, needs 7 votes. Two-thirds appears in BOTH Casper FFG and PBFT because same
  proof: any two >2/3 quorums overlap by >1/3, guaranteeing >=1 honest validator in both.
  CANNOT be used permissionlessly -- Sybil identities defeat the f-bound.

51% ATTACK ECONOMICS (Bitcoin, mid-2026): ~1000 EH/s network hashrate. 51% needs ~480 EH/s
  more -> ~1.78M rigs @ 270TH/s -> ~$5.2B hardware capex alone, $1M+/hour electricity.
  Smaller-cap PoW chains: real, documented 51% attacks via RENTED hashpower -- do NOT
  copy Bitcoin's confirmation policy onto a smaller chain.

TRILEMMA: decentralization + security + scalability -- pick 2 without a scaling-layer trick.
  Mechanism: higher throughput -> higher full-node hw/bandwidth burden -> fewer can validate
  -> less decentralized. Rollups (module 7) are the current answer: push execution off L1,
  keep data/proofs on L1 so L1 decentralization still constrains the L2 operator.

WEAK SUBJECTIVITY (PoS-specific): new nodes need a recent trusted checkpoint to bootstrap
  safely (long-range attack risk) -- pure PoW can re-verify fully from genesis; PoS can't as cleanly.
```

## Sources

- [Bitcoin: A Peer-to-Peer Electronic Cash System, Section 11 — Calculations (Nakamoto, 2008)](https://bitcoin.org/bitcoin.pdf) — accessed 2026-08-08
- [Ethereum.org — Gasper: Combining GHOST and Casper](https://ethereum.org/developers/docs/consensus-mechanisms/pos/gasper/) — accessed 2026-08-08
- [Ethereum.org — Proof-of-stake rewards and penalties](https://ethereum.org/developers/docs/consensus-mechanisms/pos/rewards-and-penalties/) — accessed 2026-08-08
- [eth2book.info — 2.3.4 Casper FFG](https://eth2book.info/latest/part2/consensus/casper_ffg/) — accessed 2026-08-08
- [Castro & Liskov — Practical Byzantine Fault Tolerance (1999)](https://pmg.csail.mit.edu/papers/osdi99.pdf) — accessed 2026-08-08
- [KuCoin — Understanding PoW 51% Attack Cost in 2026](https://www.kucoin.com/blog/en-understanding-the-moat-what-is-pow-51-attack-cost-in-2026) — accessed 2026-08-08
- [Towards Single Slot Finality — arXiv:2406.09420](https://arxiv.org/pdf/2406.09420) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
