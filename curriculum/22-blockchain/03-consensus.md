# PoW → PoS → BFT: Nakamoto, Finality, Slashing, the Trilemma

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** T22-blockchain-scratch · **Updated:** 2026-08-23
> **Module id:** `T22-consensus` · **Tags:** blockchain, consensus, critical

## The 30-second version

There are exactly two ways open networks agree, and everything else is a blend. Nakamoto consensus lets anyone propose via a cost-weighted lottery (hashes under PoW, stake under PoS) and picks a winner with a fork-choice rule; agreement is probabilistic, converging as history deepens, which is the price of permissionless membership. Classical BFT (the PBFT lineage: Tendermint, HotStuff) uses a fixed validator set exchanging votes where 2f+1 of 3f+1 replicas commit a block deterministically — instant finality, O(n²) messages in its original form, closed membership. Ethereum runs both at once: stake-weighted lotteries propose blocks, GHOST-style attestation counting picks the head, and a Casper FFG gadget finalizes checkpoints every 2 epochs (~12.8 minutes), while slashing converts attacks into self-destruction: reverting finalized history requires burning at least a third of all staked ETH. The "trilemma" says you pick two of decentralization, security, scalability; treat it as a budget statement about where you hid the tradeoff, not physics.

## Why this gets asked

Because consensus choice is the highest-leverage decision in any chain or rollup stack, and interviewers have watched teams cargo-cult it. The probing questions are predictable: why did Ethereum spend six years moving off PoW if pure BFT gives instant finality (answer: open membership and weak-subjectivity constraints BFT cannot satisfy)? What actually triggers slashing and how much do you lose (most engineers guess "everything immediately"; reality is a minimum ~1 ETH penalty scaling to your full 32 ETH only when misbehavior is correlated across many validators)? What happens when finality stalls, which happened twice on mainnet in May 2023 through client bugs while transactions kept confirming? At principal level they want the honest trilemma: it names a tension, not a theorem, and real systems buy their way around it by relocating execution (rollups) or concentrating validators (fast L1s) rather than by breaking arithmetic.

## Lineage

**What came before.** The bedrock is Lamport, Shostak, and Pease's Byzantine Generals Problem (1982): with oral messages among generals, tolerating f traitors requires 3f+1 participants. DLS (1988) established what partial synchrony permits, the model every practical protocol inhabits. Castro and Liskov's PBFT (1999) made Byzantine agreement practical: pre-prepare/prepare/commit voting, view changes on timeout, thousands of ops per second, deployed in replication middleware but never in open networks because message complexity is O(n²) and membership is static. Nakamoto's whitepaper (2008) attacked the orthogonal constraint, who may validate: proof-of-work made identity unforgeable by making it costly, collapsing Sybil resistance and leader election into hash racing, paying with probabilistic finality and terawatt-hours.

**Where it stands now.** Since the Merge (September 15, 2022), Ethereum is the flagship hybrid: roughly 1M active validator entries and ~34M ETH staked (~28% of supply) during 2025, 12-second slots, finalized checkpoints about every 12.8 minutes. The BFT family industrialized separately: Tendermint has powered Cosmos chains since 2019 with ~6-second finality; HotStuff (2018-19) replaced PBFT's quadratic view changes with aggregated quorum certificates and linear communication, spawning DiemBFT/Jolteon at Aptos and the Narwhal-Bullshark-Mysticeti line at Sui, which reports sub-second (~400 ms class) finality. Avalanche took a third route, repeated sub-sampled voting with probabilistic safety, landing ~1-2 second finality without global quorums. Live disagreements: whether fast-finality chains simply rent speed by concentrating validators (their committee sizes suggest yes), and whether Ethereum's ~13-minute finality matters when most activity settles on L2s posting to L1 data anyway.

**Where it's heading.** Three tracks. First, shrinking Ethereum's finality window: single-slot-finality research and the 3-slot proposal target cutting ~13 minutes toward one slot, bandwidth-permitting; unscheduled as of Glamsterdam (in public testing August 2026). Second, proposer-builder separation hardens into protocol: ePBS (EIP-7732) enshrines the builder auction in Glamsterdam, formalizing a world where over 85% of blocks already arrive via external builders through MEV-Boost relays. Third, more speculative: distributed validator technology (Obol, SSV) splits each validator key across machines to make accidental slashing nearly impossible, and shared sequencers sell preconfirmations, tiered "soft finality" priced in hundreds of milliseconds. Expect finality to become a product ladder rather than a binary property.

---

## Mental model

Two families, then the hybrid:

```
LOTTERY (Nakamoto)                     QUORUM (BFT)
-------------------                    -------------------
anyone may play                        fixed roster, 3f+1 members
win chance proportional to cost        leader proposes per view
fork-choice rule resolves races        2f+1 votes commit instantly
finality: probabilistic                finality: deterministic
open membership: YES                   open membership: NO (Sybil!)
cost: burned energy / bonded capital   cost: O(n^2)->O(n) messaging

ETHEREUM = LOTTERY(proposal) + GHOST(head selection) + QUORUM(finality gadget)
           + SLASHING (betrayal burns your own bond)
```

The deepest idea here is that **finality and membership are orthogonal**. PoW bought open membership and paid in energy plus slow confirmation. BFT buys determinism and pays in permissioning. Ethereum layered them: keep the open lottery for proposing, bolt a quorum finality gadget on top, enforce honesty economically (slashing) instead of physically (electricity).

Second anchor: **slashing is enforced game theory, not magic.** Each validator posts a 32 ETH bond. Exactly three provable crimes exist: signing two different blocks for one slot (double proposal), two conflicting attestations for one target epoch (double vote), or surround votes whose checkpoint ranges nest illegally. All leave cryptographic receipts anyone can submit. Penalty starts near 1 ETH and scales with how many others misbehave in the same window: solo accidents cost the minimum; a coordinated third-plus of the network burns everything it staked.

---

## How it actually works

### Nakamoto PoW mechanics

Block discovery is memoryless racing: expected interval 10 minutes, high variance. Security budget per day equals subsidy (3.125 BTC/block after the April 2024 halving, ~450 BTC/day) plus fees; attackers weighing double-spends compare theft against this flow. Fork choice: most cumulative work. The underrated property: **objective validity**, a node syncing years later with no social context independently identifies the canonical chain. Proof-of-stake systems cannot fully replicate this; they require recent trusted checkpoints, called weak subjectivity, and that single phrase answers "why not just PoS everything."

### PBFT and its descendants

PBFT normal case: primary assigns sequence numbers (pre-prepare), replicas echo (prepare), then echo the echoes (commit); execute at 2f+1 matching commits among 3f+1 replicas; timeouts trigger view change with proof-carrying leader replacement. Costs: O(n²) authenticators per view change, workable at tens of nodes, dead at thousands.

Tendermint: same skeleton with stake-weighted validators, round-robin proposer priority, and lock rules preventing conflicting prevotes across rounds; one-block finality around 6 seconds. HotStuff's contribution: the leader aggregates votes into threshold-signed quorum certificates, so each phase costs one message to the leader, O(n) communication, pipelined across blocks. That linearization is why Aptos and Sui sustain hundreds of validators with sub-second-class finality.

### Gasper: Ethereum's actual machine

Each slot (12 s): one proposer, selected from RANDAO-derived randomness weighted by 32-ETH validator units, publishes a block on the parent head. Committees attest: LMD-GHOST votes weight the fork choice tree; checkpoint votes (source,target pairs) create supermajority links. An epoch is 32 slots (~6.4 min); a target justified by 2/3 of staked weight becomes justified, and a link from a justified source finalizes it. Two epochs to finality: ~12.8 minutes.

Slashing penalties precisely: initial slash takes 1/32 of effective balance (≤1 ETH) plus leakage while the offender stays in the exit queue; then the correlation penalty scales as roughly min(3 × fraction_slashed_within_4096_epochs, 1) × balance. One buggy VM clone costs ~1 ETH; a mass client-bug event costs multiples; a coordinated >1/3 attack annihilates the attackers' entire stake.

Inactivity leak: if finality stalls beyond 4 epochs because over a third of validators are offline (partition scenario), offline balances drain quadratically until the online remainder controls 2/3 again and finality resumes. Deliberate preference for availability over frozen consistency, funded by the inactive minority's treasury.

Proposer-builder separation: ~85-90% of slots are filled via MEV-Boost where competing builders bid complete blocks and relays mediate. ePBS moves that handshake into consensus itself (Glamsterdam). Consequence worth saying aloud: block contents are market-priced, and naive claims of inclusion neutrality are already historical.

### The trilemma, honestly

| Axis | PoW (BTC) | PoS hybrid (ETH) | BFT (Tendermint-class) |
|---|---|---|---|
| Finality | none (probabilistic) | ~12.8 min | ~0.4-6 s |
| Membership | open | open, stake-gated | bounded/elected |
| Validators at scale | ~10⁴-10⁵ mining nodes | ~10⁶ units, ~14k nodes | 100-1000 |
| Attack cost basis | hardware + ~$15-20B/yr energy | ~$120B bonded capital | legal/reputational + bonds |
| Client complexity | moderate | high (two layers) | moderate |

Rollups "break" scalability by renting decentralization and security from an L1 while executing elsewhere; fast L1s rent speed by concentrating committees. When a pitch claims to break the trilemma, ask which leg quietly got weaker; that question is usually the interview's real payload.

## Build it from scratch

A runnable synchronous PBFT simulation, stdlib-only: shows the 2f+1 quorum rule, equivocating Byzantine votes being outvoted, and the 3f+1 membership bound failing liveness when violated. Verified below.

```python
import hashlib

def H(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()[:10]

class PBFTSim:
    """Synchronous normal-case PBFT. Broadcasts are reliable; Byzantine nodes
    may vote arbitrarily (equivocate) in either phase. f faults need N=3f+1."""

    def __init__(self, n, f, byz_ids):
        self.N, self.f = n, f
        self.quorum = 2 * f + 1
        self.byz = set(byz_ids)
        assert len(self.byz) <= f
        self.logs = [[] for _ in range(n)]

    def round(self, seq, tx, leader):
        """Returns the committed digest or None (liveness lost this round)."""
        good   = H(f'{seq}:{tx}')
        poison = H('poison')

        # ---- PRE-PREPARE + PREPARE: everyone hears everyone's vote ----
        tally = [dict() for _ in range(self.N)]       # per-replica digest->voters
        for v in range(self.N):
            d = poison if (v in self.byz and v != leader) else good
            for r in range(self.N):
                tally[r].setdefault(d, set()).add(v)

        # ---- COMMIT: replicas that saw a prepare-quorum vote; byz still poison ----
        ballots = []
        for r in range(self.N):
            if any(len(vs) >= self.quorum for vs in tally[r].values()):
                ballots.append((r, poison if r in self.byz else good))
        ctally = [dict() for _ in range(self.N)]
        for s, d in ballots:
            for r in range(self.N):
                ctally[r].setdefault(d, set()).add(s)

        # ---- decide: any digest reaching commit-quorum wins ----
        committed = None
        for d, vs in ctally[0].items():
            if len(vs) >= self.quorum:
                committed = d
                break
        if committed == good:
            for r in range(self.N):
                self.logs[r].append((seq, committed))
        return committed

if __name__ == '__main__':
    txs = ['pay-alice', 'pay-bob', 'pay-carol']

    sim = PBFTSim(n=4, f=1, byz_ids=[3])          # 3f+1=4 tolerates 1 traitor
    for seq, tx in enumerate(txs):
        assert sim.round(seq, tx, leader=seq % 4) is not None
    assert all(sim.logs[i] == sim.logs[0] for i in range(4))
    print('N=4,f=1 -> consensus held with an equivocating node')

    dead = PBFTSim(n=3, f=1, byz_ids=[2])         # violates 3f+1: 2 honest < quorum 3
    outs = [dead.round(s, t, leader=s % 3) for s, t in enumerate(txs)]
    assert all(o is None for o in outs)
    print('N=3,f=1 -> no commits ever: the 3f+1 boundary demonstrated')
```

Run it and you see both fundamental results live: with N=4, f=1 the Byzantine node's poison votes never reach quorum and all honest logs converge block-for-block; with N=3, f=1 nothing ever commits because two honest replicas cannot reach the required three. Flip to N=7, f=2 and it works again. Deliberate omissions to name when presenting this: no signatures on votes (real protocols sign everything, which is what makes slashing proofs possible), no timeouts/view-change (the genuinely hard 20% of any BFT spec), synchronous broadcast instead of partial synchrony, and no stake weighting. The safety argument itself lives in quorum intersection: any two quorums of 2f+1 among 3f+1 share at least one honest replica, so two conflicting commits cannot both form.

## How it's done in production

| Network | Protocol family | Finality (typical) | Notes |
|---|---|---|---|
| Bitcoin | Nakamoto PoW | none; depth-based | objective history; ~$15-20B/yr security flow |
| Ethereum | Gasper (PoS + FFG) | ~12.8 min | ~34M ETH staked; slashing live since Dec 2020 |
| Cosmos hubs | Tendermint BFT | ~6 s | bounded active set (Hub: 180 validators) |
| Aptos | Jolteon / DiemBFT v4 | ~0.6-1 s | HotStuff lineage, pipelined |
| Sui | Mysticeti (DAG + BFT) | ~0.4 s | uncertified DAG commit in 3 rounds |
| Avalanche | Snowman (subsampled voting) | ~1-2 s | probabilistic safety, no global quorum |

Operational failure modes:

| Symptom | Cause | Fix |
|---|---|---|
| Validator slashed ~1 ETH | Accidental double-sign: cloned VM, shared disk, failover race | Slashing-protection DB per key; never run duplicate instances of one key |
| Checkpoints freeze but blocks keep coming | Client bug cluster (May 2023 mainnet pattern) | Client diversity targets (no >1/3 per client); alert on justification gap |
| Chain halts entirely | BFT: fewer than 2f+1 online (Cosmos outage pattern, e.g., June 2021 hub halt) | Uptime overprovisioning; missed-block counters paging |
| Proposer misses outsized share of slots | MEV-Boost relay outage or bad builder bids | Multi-relay config; monitor relay latency and fallback local building |
| Reorg past "safe" tag | Non-finalizing minority partition | Apps consume `safe`/`finalized` tags, not raw depth, on PoS |

Production hygiene that separates professionals: persistent slashing-protection records (high-water marks over slots/epochs signed), dual-client operation with automated failover, epoch-boundary participation dashboards, DVT (threshold BLS via Obol/SSV) so no single machine can double-sign, and application integrations that gate irreversible actions exclusively on `finalized`. Anything earlier is a risk-policy decision, priced as such.

## Tradeoffs & when NOT to use it

- **Don't use BFT where membership cannot be bounded.** Permissionless growth requires Sybil-resistant admission (work or stake); pure BFT assumes a known roster. Consortium chains that ignore this relearn it every time a member joins or gets hacked.
- **Don't use PoW for anything non-monetary.** Its security flow (~$15-20B/yr on Bitcoin) buys open membership you probably don't need; hash-based anchoring into an existing chain gives tamper-evidence at zero marginal energy.
- **PoS shifts risk from physics to key management.** No electricity arms race, but slashing turns operational mistakes into capital loss, and long-range attacks mean every node needs a recent trusted checkpoint. Weak subjectivity is a real philosophical cost; say it out loud rather than hand-waving.
- **Fast finality concentrates power.** Sub-second BFT finality at scale implies committees small enough that a few operators colluding reach quorum. If decentralization is the product requirement, accept slower finality or rent L1 security.
- **The trilemma is a heuristic, not a theorem.** It names tensions; it does not forbid engineering around them (rollups, DVT, data-availability sampling). Presenting it as physics fails interviews at exactly the places this module trains.
- **When consensus choice barely matters:** single-writer audit logs, internal ledgers with one trusted operator — skip distributed trust entirely and ship a database with append-only storage plus external anchoring.

## Interview questions

### Q1 — Why does Byzantine agreement need 3f+1 nodes, not 2f+1?
**Testing:** fundamentals under the buzzwords.
**Answer:** With 3f+1, any two quorums of size 2f+1 intersect in at least f+1 nodes, so they share at least one honest replica: two conflicting commits cannot both form. With only 2f+1 total and f faults, quorums of ~f+1 can be disjoint or consist entirely of liars, breaking safety. The extra f nodes buy quorum intersection through honesty.
**Follow-up trap:** *"So more replicas always help?"* — Beyond the bound it helps nothing and costs O(n²) messages in PBFT; HotStuff reduces per-view traffic but committee growth still slows consensus latency. The bound is about fault tolerance, not throughput.

### Q2 — What is "weak subjectivity" and why does PoS accept it?
**Testing:** whether you know PoS's philosophical cost.
**Answer:** A node joining after long offline periods cannot distinguish the true chain from an attacker's fabricated history built from old stakes (long-range attack), because there's no cumulative work to measure. Mitigation: sync against a recent state root published by the live network or a trusted source. Accepted because attacks require majority stake colluding publicly, destroying their own deposits, and social coordination can reject them anyway.
**Follow-up trap:** *"Isn't that trusting developers?"* — It's trusting recentness, not code: any current honest participant suffices as checkpoint source, and multiple independent sources defeat single-point deception. Compare honestly with PoW's objective history; don't pretend the cost away.

### Q3 — Enumerate Ethereum's slashing conditions and the actual penalty curve.
**Testing:** precision; this separates operators from tourists.
**Answer:** Three conditions: double proposal (two headers for one slot), double vote (conflicting attestations, same target epoch), surround vote (attestations nesting illegally across epochs). Penalty: initial slash takes 1/32 of effective balance (≤1 ETH); then correlation penalty ≈ min(3 × fraction slashed within 4096 epochs, 1) × balance. Solo accident ≈ 1 ETH; correlated mass events scale toward total loss.
**Follow-up trap:** *"Can you get slashed for being offline?"* — No: downtime costs only missed rewards (~1:4 ratio versus rewards earned at full participation). The inactivity leak drains offline validators only when finality stalls over 4 epochs network-wide.

### Q4 — Why did Ethereum keep probabilistic-style fork choice instead of adopting pure BFT end-to-end?
**Testing:** design reasoning across families.
**Answer:** Pure BFT needs bounded membership and pays quadratic messaging plus halts below quorum. Ethereum wanted open membership at ~10⁶ validator units, so it kept lottery-based proposals and GHOST-weighted head selection for liveness/fork choice, then layered deterministic finality via Casper FFG checkpoints where aggregate BLS signatures make 2/3 votes cheap. Hybrid gets open membership plus eventual hard finality.
**Follow-up trap:** *"What did that cost them?"* — 13-minute finality, two-layer client complexity (the May 2023 non-finality incidents were exactly this complexity biting), and slashing-key operational risk. Name all three to show the tradeoff was priced, not ignored.

### Q5 — Explain inactivity leak and what problem it solves.
**Testing:** liveness-under-partition reasoning.
**Answer:** If >1/3 of stake goes offline (partition, outage), checkpoints can't reach 2/3 and finality stalls forever without intervention. After 4 epochs, offline validators' balances leak quadratically until the online remainder exceeds 2/3, letting the surviving partition finalize. Availability is prioritized; consistency restored by economically punishing the absent side.
**Follow-up trap:** *"Which side is 'right' afterward?"* — Whichever is online finalizes; the rejoining side syncs to it. There's no automatic reconciliation with the minority's history beyond protocol rules; that's deliberate, mirroring CAP's partition choice, made explicit.

### Q6 — Compare Tendermint, HotStuff, and Gasper on view-change and message complexity.
**Testing:** literature fluency beyond marketing.
**Answer:** Tendermint: rounds with lock rules; view change via proof-of-failure round robin; O(n²) votes per round, acceptable at ~100-180 validators. HotStuff: leader aggregates threshold-signed votes into QCs each phase; linear O(n) per view; pipelined 3-phase commit; enables hundreds of validators at sub-second class. Gasper: not a BFT replication protocol per block; attestation aggregation every slot with FFG checkpoint justification every epoch, relying on BLS aggregation (thousands of sigs into one).
**Follow-up trap:** *"Why didn't everyone just adopt HotStuff?"* — They largely did: DiemBFT, Jolteon, Bullshark are HotStuff derivatives. But HotStuff still needs bounded membership, so permissionless chains bolt stake-weighting and rotation on top; the protocol core alone doesn't solve admission.

### Q7 — A bridge credits transfers after 20 confirmations on a BFT chain with 1-second blocks. Critique.
**Testing:** transferring finality concepts across chains.
**Answer:** Confirmations count blocks, but BFT security comes from commit certificates, not depth: one finalized block beats twenty uncommitted ones. If the chain commits instantly (Tendermint-class), 20 confs ≈ 20 seconds of pure latency with no added safety; if finality can stall under partition, the right primitive is waiting for the commit certificate or explicit finalization event, plus monitoring quorum health.
**Follow-up trap:** *"So confirmations are meaningless?"* — On PoW they're the entire risk model ((q/p)^z decay); on instant-finality BFT they're vestigial UX. Saying which model the chain uses before quoting numbers is the senior tell.

### Q8 — Walk through what happens, protocol-level, when two clients disagree on validity post-Merge.
**Testing:** real-incident mechanics (client diversity).
**Answer:** Each client follows its own validation: the buggy one accepts/attests a block the correct one rejects, splitting attestation weight. If the buggy chain keeps >half of attestations, heads fork; Casper FFG cannot justify either checkpoint until weights resolve, freezing finality while blocks continue (May 2023 pattern, twice, from Prysm and Teku bugs under specific conditions). Recovery: fix deployed, minority-weighted correct chain regains 2/3, finality resumes; no rollback of finalized state occurred.
**Follow-up trap:** *"How do you prevent it operationally?"* — Client diversity targets (no client >1/3 of stake), staged releases, and monitoring justification-gap alarms rather than block-height alarms, since height kept advancing during both incidents.

### Q9 — What actually secures Bitcoin daily, quantitatively?
**Testing:** economic security literacy with numbers.
**Answer:** Subsidy + fees flow to miners as revenue that must be recouped through hardware and energy: post-April-2024 subsidy is 3.125 BTC/block → ~450 BTC/day baseline (~$45-60B/yr at $110-140k BTC ranges seen 2025-26; quote order-of-magnitude, flag volatility). Attacking means out-racing that flow or acquiring majority ASIC capacity unavailable on rental markets. Security budget scales with price, which is also its fragility: fee-only sustainability post-subsidy remains genuinely unresolved.
**Follow-up trap:** *"Is that efficient?"* — As insurance proportional to protected value (~$2T+ asset), 2-3% annual flow is comparable to custody/gold-storage costs; as energy policy it's contested. Give both framings; pick neither dogmatically.

### Q10 — Design consensus for a consortium of 12 banks settling tokenized deposits. Choose family and justify.
**Testing:** applied architecture judgment, not ideology.
**Answer:** BFT (HotStuff/Tendermint lineage or a permissioned stack like Besu with QBFT): membership is known and bounded, 12 members tolerate f=3 Byzantine at N=13, sub-second-to-second finality fits settlement, no token needed since reputational and legal bonds substitute for economic ones. Add: key ceremonies, HSM-backed signers, on-chain identity for admission, and off-chain governance for member changes since protocol can't arbitrate politics.
**Follow-up trap:** *"Why not just use a database?"* — Valid challenge: if settlement finality is internal, a replicated DB with signed logs wins on cost. Blockchain earns its seat when counterparties need shared, independently verifiable settlement truth without a designated operator — say that condition explicitly.

### Q11 — What breaks if RANDAO bias becomes cheap?
**Testing:** understanding proposer-selection attack surface.
**Answer:** RANDAO is commit-reveal over attestations; the last proposer in an epoch can skip (burning their own slot reward) to shift future proposer selection. Cheap bias lets adversaries grind for consecutive slots, enabling short-range reorg attempts or censorship windows. Mitigations: single-secret-leader-election research hides WHO will propose, removing targeted DoS; MEV-boost already changes incentives around slot value.
**Follow-up trap:** *"Is this theoretical?"* — Bias itself is bounded and expensive today (one bit-ish per slot at full slot-value cost), but targeted-DoS against revealed proposers is real and observed at relay level; SSLE is the acknowledged open problem. Distinguish the two threats cleanly.

### Q12 — Your L2 sequencer offers "soft confirmations" in 200 ms. What are you actually buying?
**Testing:** modern tiered-finality literacy.
**Answer:** A promise from one operator (or federated set), not consensus: the tx entered the sequencer's local order. Real assurance ladder: soft confirmation → batch posted to L1 (data available, still reorderable until finality) → L1 finality ~12.8 min. Preconfirmation markets attempt to price this trust; risks are sequencer equivocation and forced-inclusion delays (L1 inclusion lists) landing later than promised.
**Follow-up trap:** *"Should apps use it?"* — For UX (quotes, carts) yes; for irreversible actions (withdrawals, settlement) no. Codify the ladder in product SLAs; treat soft confirms as optimistic UI, not ledger truth.

### Q13 — Why does BLS aggregation matter more than TPS headlines for Ethereum's design?
**Testing:** systems thinking about bandwidth budgets.
**Answer:** With ~10⁶ validator units, naive per-validator signature broadcast is impossible: committees of 512 attest per slot, and aggregation collapses thousands of signatures into one ~96-byte group signature verifiable once. That's what makes 32-slot epochs, GHOST weighting by millions of votes, and FFG checkpoints feasible within home-node bandwidth. Throughput numbers follow from this plumbing, not vice versa.
**Follow-up trap:** *"Costs?"* — Verification is slower per-signature than ECDSA, aggregation requires distinct-message discipline (rogue-key defenses via deposit proofs-of-possession), and threshold-BLS (DVT) adds complexity. Name the tradeoffs, not just the win.

### Q14 — Where do rollups sit relative to the trilemma? Be precise about what they rent.
**Testing:** current-architecture clarity.
**Answer:** Rollups execute off-chain but post data to L1 (blobs), inheriting L1's data availability and settlement security: decentralization leg rented from Ethereum's validator set; security leg likewise; scalability bought by compressing execution (hundreds of txs per blob, ~128 KB each, target rising past Fusaka's BPO schedule toward 48 blobs/block). Their own consensus (sequencer) is currently centralized, which is the honest weak point until shared/decentralized sequencing matures.
**Follow-up trap:** *"So trilemma solved?"* — Relocated, not solved: L1 data bandwidth is the global bottleneck, and users inherit L1 finality latencies for withdrawals unless liquidity markets front them. Precision here reads as experience.

### Q15 — Rank these properties by how often they decide real deployments: finality time, validator count, slashing risk, ecosystem tooling.
**Testing:** judgment over trivia; defend the ranking.
**Answer:** 1) Ecosystem tooling (SDKs, audits, liquidity) decides most practical choices; 2) finality time, because product UX and bridging economics hinge on it; 3) slashing risk, decisive for staking operators specifically; 4) raw validator count, mostly a narrative metric that rarely changes integration decisions. Then invert: for infrastructure providers, slashing risk jumps to first. Context-dependent rankings, stated with reasons, beat memorized ones.
**Follow-up trap:** *"You'd really put tooling above security?"* — Deployments route around weak tooling constantly (choose the chain with the SDK); security differences between major L1s are abstract to most builders until an incident. Acknowledge the incentive misalignment honestly rather than moralizing.

## Red flags

- Reciting "blockchain solves consensus" without naming Nakamoto vs BFT trade spaces.
- Claiming PoS validators "can't be attacked" or ignoring long-range attacks entirely.
- Saying slashing = losing everything immediately (correlation penalty is the actual mechanism).
- Mixing up finality (protocol guarantee) with confirmations (risk heuristic).
- Believing the trilemma is a theorem, or claiming a project "broke" it without identifying the weakened leg.
- Not knowing Ethereum's basic constants: 12 s slots, 32-slot epochs, ~12.8 min finality.
- Proposing BFT for permissionless networks with unbounded participants.
- Ignoring client diversity when explaining the May 2023 finality stalls.

## Cheat card

```
BFT BASICS     f traitors -> N=3f+1 · quorum 2f+1 · quorum intersection => safety
PBFT           pre-prepare/prepare/commit · O(n^2) msgs · view change on timeout
HOTSTUFF       leader aggregates QC (threshold sigs) · O(n)/view · pipelined
               descendants: DiemBFT/Jolteon (Aptos), Narwhal/Mysticeti (Sui)
NAKAMOTO       race + heaviest-work fork choice · probabilistic finality
               objective history (no checkpoint needed) - unique vs PoS
GASPER         12 s slots · 32-slot epochs (6.4 min) · finality 2 epochs ~12.8 min
               LMD-GHOST head + Casper FFG justifies->finalizes checkpoints
SLASHING       double proposal | double vote | surround vote (only 3 crimes)
               initial <=1 ETH · correlation ~min(3*f_frac,1)*balance
               offline != slashed (missed rewards only) · leak after 4 stalled epochs
SECURITY FLOW  BTC ~450 BTC/day subsidy (3.125/blk post 4th halving) + fees
FINALITY TIME  Cosmos ~6 s · Aptos ~0.6-1 s · Sui ~0.4 s · Avalanche 1-2 s
MERGE          2022-09-15 · ~34M ETH staked · MEV-boost >85% of blocks
TRILEMMA       decentralization / security / scalability - name the hidden tradeoff
LADDER         soft confirm (sequencer) -> L1 data posted -> L1 finalized
```

## Sources

- [Lamport, Shostak, Pease — The Byzantine Generals Problem (1982)](https://www.microsoft.com/en-us/research/publication/byzantine-generals-problem/); accessed 2026-08-23
- [Castro & Liskov — Practical Byzantine Fault Tolerance (OSDI 1999)](http://pmg.csail.mit.edu/papers/osdi99.pdf); accessed 2026-08-23
- [Yin, Malkhi et al. — HotStuff: BFT Consensus in the Lens of Blockchain (2019)](https://arxiv.org/abs/1803.05069); accessed 2026-08-23
- [Buterin & Griffith — Casper the Friendly Finality Gadget (arXiv 1710.09437)](https://arxiv.org/abs/1710.09437); accessed 2026-08-23
- [Neu, Tas, Tan — Gasper (FFG + LMD GHOST) specification paper](https://arxiv.org/abs/2003.03052); accessed 2026-08-23
- [Ethereum consensus specs — slashing, inactivity leak](https://github.com/ethereum/consensus-specs); accessed 2026-08-23
- [Finality incident post-mortem coverage, May 2023 — Ethereum Foundation blog](https://blog.ethereum.org/2023/05/11/mainnet-finality); accessed 2026-08-23
- [Glamsterdam / ePBS roadmap — ethereum.org](https://ethereum.org/en/roadmap/); accessed 2026-08-23
- [Cambridge Centre for Alternative Finance — Bitcoin energy and mining data](https://ccaf.io/cbnsi/cbeci); accessed 2026-08-23
- [Cosmos Hub halt June 2021 — Tendermint post-mortem](https://medium.com/cosmos-chain/hub-4-postmortem); accessed 2026-08-23

## Changelog

- 2026-08-23 — created


