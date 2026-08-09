# Rollups (Optimistic vs ZK), Data Availability, Bridges and Their Failures

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 2.5h · **Prereqs:** `T22-consensus`, `T22-bitcoin-ethereum`
> **Updated:** 2026-08-08
> **Module id:** `T22-scaling` · **Tags:** scaling
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A rollup executes transactions off Ethereum's base layer (L1) but posts enough data back to L1 that anyone can independently reconstruct and verify the resulting state — this is the entire trick behind "layer 2 scaling": push computation off-chain, keep just enough on-chain that L1's decentralization and security still constrain what the rollup operator can get away with. Optimistic rollups assume every batch is valid by default and rely on a **fraud proof**: anyone can challenge a bad batch within a window (historically seven days on the major optimistic rollups), and if the challenge succeeds the bad state is rolled back and the challenger is rewarded — which means withdrawals to L1 are slow (bounded by that challenge window) unless a liquidity provider fronts you the funds for a fee. ZK-rollups instead attach a **validity proof** (a zero-knowledge or, more precisely for most current implementations, a succinct cryptographic proof) to every batch, mathematically proving the new state follows correctly from the old one and the submitted transactions — this lets withdrawals finalize in minutes once the proof verifies on L1, no challenge window needed, at the cost of the proof-generation infrastructure being more complex and, historically, more expensive to run. **Data availability (DA)** is the deceptively simple but load-bearing requirement underneath both: even a perfectly valid rollup is worthless if nobody can get the underlying transaction data to actually reconstruct state or contest a fraudulent claim, which is precisely the problem EIP-4844's "blobs" (March 2024) and Fusaka's PeerDAS (December 2025) target, dramatically cheapening how much data L2s can post to L1. None of this touches the single largest, most consistently exploited category of loss in this entire space: **bridges** — the contracts that move value between chains — have lost billions of dollars across a small number of catastrophic incidents specifically because a bridge concentrates trust (a locked pool of funds on one side, a minting authority on the other) into an unusually attractive, unusually fragile single point of failure, and that pattern hasn't meaningfully changed even as the rollup technology around it has matured substantially.

## Why this gets asked

Because "Ethereum scales via rollups" is the correct 2026 answer but an incomplete one — the interviewer wants to know whether you understand the actual mechanism distinguishing optimistic from ZK (fraud proof vs. validity proof, not just "one uses zero-knowledge and one doesn't"), whether you understand data availability as the real bottleneck rollups are fighting rather than raw compute, and critically, whether you can explain *why* bridges specifically are where the money disappears — a pattern repeated so consistently across the industry's worst losses that failing to name it as a distinct, structural risk category (rather than "hacks happen") is a real gap for anyone claiming production blockchain fluency.

---

## Lineage: past → present → future

**What came before.** Ethereum's base layer alone tops out at roughly 15-30 transactions per second in ordinary operation — a hard constraint directly following from the scalability trilemma (module 3): raising L1 throughput directly by increasing block size or reducing block time increases the resource burden on every full node, trading away decentralization to get it. Early scaling attempts (state channels, plasma) tried to move computation off-chain while keeping *some* on-chain anchor, but each had real, specific limitations — state channels required all participants to be known and online, and generalize poorly beyond simple bilateral interactions; Plasma (Buterin & Poon, 2017) moved execution off-chain with periodic commitments back to L1, but its data-availability problem was never fully solved (if the Plasma operator withholds transaction data, users can't prove what actually happened, undermining the exit mechanism the whole design depended on) — and this specific, named failure is precisely what rollups were designed to fix by making a stronger, explicit guarantee: **post the data, not just a commitment to it.**

**Where it stands now.** Rollups — both optimistic and ZK — are the dominant, currently-deployed scaling answer, and this is settled, not contested: the majority of Ethereum-ecosystem transaction volume now happens on L2s rather than L1 directly, and this shift is a measured fact of 2026 usage patterns, not an aspiration. Arbitrum and Optimism (OP Stack, powering Base and others) still settle the majority of L2 value as optimistic rollups; the notable live technical convergence is those chains' addition of shorter "fast withdrawal" paths via third-party liquidity providers, closing much of the practical UX gap against ZK-rollups' faster native finality. On the ZK side, EVM-compatibility — running unmodified or near-unmodified Ethereum smart contracts inside a system that can generate validity proofs for that execution — has substantially matured; by 2026 every major zkEVM implementation is in production, not merely announced, and proof-generation costs have dropped sharply since 2024 through specialized proving hardware and more efficient proof systems. The live, still-unresolved question isn't "does ZK work" (it demonstrably does), it's economic and architectural: which specific proving system, hardware approach, and level of EVM-equivalence wins for which workload — a genuinely open, actively-competitive space, not a settled ranking.

**Where it's heading.** High confidence: Ethereum's own base-layer roadmap continues optimizing specifically *for* rollups rather than for direct L1 execution scaling — EIP-4844 (Dencun, March 2024) introduced "blobs," a dramatically cheaper, temporary data-availability lane specifically for L2s to post their data into; Pectra (May 2025) doubled blob capacity; Fusaka (December 2025) introduced PeerDAS, distributing blob data across the network so individual nodes only store a fraction of it, delivering roughly an order-of-magnitude increase in data-availability capacity. **Full danksharding** — the long-stated endgame, targeting around 128 blobs per slot — remains the direction of travel, with BPO (Blob-Parameter-Only) forks incrementally raising blob targets through 2026 rather than waiting for one large jump. Medium confidence: the optimistic/ZK gap continues narrowing specifically because ZK's EVM-compatibility gap has substantially closed while its finality-speed advantage remains real and increasingly relevant to capital-efficiency decisions — whether optimistic rollups retain a meaningful long-term niche or ZK becomes the default for new L2 deployments generally is a live, reasonable question to hold uncertainty about rather than assert confidently either way. Bridge security specifically shows no comparably clear positive trajectory: losses continued at a substantial rate through 2026 (hundreds of millions across multiple incidents in just the first half of the year), and this module's position — that bridges remain the field's most persistent, least-solved risk category — should be stated as a current, ongoing problem, not a historical one being steadily fixed.

---

## Mental model

```
  ROLLUP: execute off-chain, prove/dispute on-chain, DATA still goes to L1

  L2 (off-chain)                          L1 (Ethereum)
  ┌─────────────────────┐                ┌──────────────────────────┐
  │ execute many txs     │   batch +      │ store the DATA (cheaply, │
  │ compute new state    │──────────────▶ │  via blobs) + a claim    │
  │ root                 │   proof/claim  │  about the new state     │
  └─────────────────────┘                └──────────────────────────┘
                                                       │
                          OPTIMISTIC:                 │      ZK:
                    "assume valid, 7-day               "prove valid
                    CHALLENGE WINDOW —                  with a VALIDITY
                    anyone can submit a                 PROOF attached —
                    FRAUD PROOF if wrong"                math, not a wait"
                          │                             │
                    slow finality                  fast finality (mins,
                    (or pay a liquidity              once proof verifies)
                    provider for a fast exit)

  WHY DATA AVAILABILITY MATTERS EVEN IF EVERYONE TRUSTS THE OPERATOR:
  a bad-faith or simply OFFLINE operator withholding the underlying
  transaction data means NOBODY — not challengers, not users trying to
  exit, not even honest operators reconstructing state — can prove
  ANYTHING about what happened. Posting a state ROOT alone (like Plasma
  did) is not enough; the actual DATA behind it must be retrievable.

  BRIDGES: the actual danger concentrates here, not in the rollup logic
  ┌──────────────┐                              ┌──────────────┐
  │  CHAIN A      │   lock/burn A-side tokens    │  CHAIN B      │
  │  (funds       │─────────────────────────────▶│  (mint/release│
  │  LOCKED here, │   ◀─── a SINGLE contract,     │  wrapped      │
  │  a huge pool) │        or a small validator   │  tokens)      │
  └──────────────┘        SET, decides this is    └──────────────┘
                           valid — a concentrated
                           trust chokepoint EVERY
                           cross-chain bridge has
                           some version of.
```

---

## How it actually works

### Optimistic rollups: fraud proofs

An optimistic rollup's sequencer batches many L2 transactions, computes the resulting state root, and posts both the underlying transaction data and the claimed new state root to L1 — **without** proving the computation was correct at submission time. The system's security comes entirely from what happens *after*: a **challenge window** (historically seven days on Arbitrum and Optimism, the two dominant optimistic rollups) during which anyone watching the chain can submit a **fraud proof** — a demonstration, verified by an L1 smart contract, that the claimed state transition doesn't actually follow from the posted transaction data. If a fraud proof succeeds, the bad state is reverted and the party who posted it is penalized (typically losing a posted bond), and the successful challenger is rewarded from that bond.

**Why this makes withdrawals slow, and how that's actually mitigated in production.** A user withdrawing funds from L2 back to L1 needs the L1 contract to be confident the L2 state showing their withdrawal is actually final — but "final" for an optimistic rollup means "the challenge window has passed with no successful fraud proof," which is where the seven-day figure comes from. In production, this UX problem is solved not by shortening the actual security window (which would weaken the fraud-proof mechanism's real protection) but by third-party **liquidity providers** who front the user their funds immediately on L1, for a fee, and then collect the "real" withdrawal themselves once the challenge window genuinely elapses — by 2026 this makes the seven-day wait largely invisible to ordinary retail users on the major optimistic rollups, at the cost of that liquidity-provider fee.

### ZK-rollups: validity proofs

A ZK-rollup's sequencer similarly batches transactions and computes a new state root, but instead of merely *claiming* correctness and waiting out a challenge period, it generates a **validity proof** — a cryptographic proof (in most current production zkEVMs, a SNARK — a succinct non-interactive argument of knowledge) that the new state root is the correct result of applying the batched transactions to the prior state, according to the EVM's actual execution rules. This proof is verified by an L1 smart contract in a single, relatively cheap operation, and once verified, **there is nothing left to challenge** — the mathematics itself is the guarantee, not a time-bounded absence of objection. This is why ZK-rollup withdrawals can finalize in minutes rather than days: finality doesn't depend on waiting to see if anyone objects, because the proof already establishes correctness before it's ever posted.

**The real historical cost, and why it's shrinking.** Generating a validity proof for a batch of general-purpose EVM execution is computationally expensive — proving arbitrary computation in zero-knowledge is a much harder engineering problem than optimistically assuming correctness, which is exactly why optimistic rollups were technically simpler to build and reached production maturity first. Specialized proving hardware and substantially more efficient proof systems have driven proof-generation costs down sharply since 2024, and by 2026 every major zkEVM implementation is in production rather than merely announced — the historical "ZK is theoretically better but not practically ready" gap has substantially closed, though proving infrastructure remains a genuinely more complex operational dependency than an optimistic rollup's simpler challenge-based design.

### Data availability: the requirement underneath both

Neither fraud proofs nor validity proofs mean anything if the underlying transaction data isn't actually retrievable. A fraud proof requires reconstructing what the correct state transition *should* have been, which requires the actual transaction data, not just a claimed state root. A validity proof, while it doesn't need to be *challenged*, still requires the underlying data be available for anyone (a new user, an indexer, a would-be verifier of the L2's actual current state) to reconstruct that state independently — a chain where you must trust the operator's own node to tell you your balance, with no way to verify it yourself from public data, has quietly reintroduced the exact trust assumption rollups exist to remove.

This is the specific problem **EIP-4844 ("blobs," part of the March 2024 Dencun upgrade)** targets: a new, much cheaper data-storage lane on Ethereum specifically for this kind of large, temporary rollup data — blobs are pruned by L1 nodes after roughly 18 days (long enough for anyone who needs to challenge a fraudulent optimistic-rollup claim, or independently reconstruct state, to retrieve them, but not persisted forever, keeping the ongoing storage burden on L1 full nodes bounded). Ethereum's blob capacity has scaled substantially since: **Pectra (May 2025)** doubled blob capacity, and **Fusaka (December 2025)** introduced **PeerDAS** (Peer Data Availability Sampling), which distributes blob data across the network so that each individual node needs to store only a fraction (roughly one-eighth) of the total, letting the network support roughly an order of magnitude more blob capacity without proportionally increasing what any single node must handle — a direct, mechanical answer to the scalability trilemma's core tension (module 3): more data capacity without concentrating the storage burden onto fewer, better-resourced nodes.

### Bridges: where the value actually concentrates and disappears

A **bridge** moves value (or, more precisely, the *representation* of value) between chains that otherwise have no native way to communicate — Chain A doesn't know anything happened on Chain B, and vice versa. The overwhelmingly common architecture: lock (or burn) tokens on the source chain, and have some mechanism — a smart contract, a validator set, a multi-signature committee — attest that this locking happened, authorizing the mint (or release) of an equivalent representation on the destination chain.

**This architecture concentrates trust into an unusually attractive single point of failure**, for a structural reason worth stating precisely: the locked funds on the source chain sit in one place, controlled by one mechanism, and if an attacker can forge or bypass the attestation that's supposed to require a real, valid lock — without needing to compromise either underlying blockchain's own consensus — they can mint or release funds against nothing. This is categorically different from attacking a chain's own consensus (module 3's 51%-attack economics, genuinely expensive at scale for a major chain); attacking a bridge's attestation mechanism specifically is often attacking a much smaller, much less battle-tested piece of custom infrastructure.

**The historical record is blunt and worth stating plainly, not softened.** Some of the largest crypto losses in history are bridge hacks specifically: the **Ronin Bridge** (March 2022, ~$625M) — attackers compromised 5 of 9 validator keys securing the bridge (later attributed to North Korea's Lazarus Group), a validator-set-compromise attack requiring no blockchain-level exploit at all. **Poly Network** (August 2021, ~$612M) — a smart-contract vulnerability let an attacker redirect the bridge's own "keeper" authorization to their own address, then withdraw at will. **Wormhole** (February 2022, ~$320M) — a signature-verification bug let an attacker mint 120,000 wrapped ETH on Solana without ever depositing real ETH. **Nomad** (August 2022, ~$190M) — a faulty upgrade set a trusted-root value to the zero address, letting essentially anyone spoof a valid-looking withdrawal message. This pattern has not stopped: 2026 alone saw well over $340M in bridge-specific losses across dozens of separate incidents in just the first half of the year, with Q2 2026 recording 83 total DeFi hacks and roughly $755M in combined losses, cross-chain bridge vulnerabilities accounting for close to half of that quarter's total. **This is not a solved problem the industry is steadily closing out — it is an ongoing, actively-recurring category, and treating it as a historical footnote from "the early days" is a real, checkable factual error.**

---

## Build it from scratch

The core mental model worth internalizing precisely — since a full zkEVM or fraud-proof system is well beyond a from-scratch educational build — is the fraud-proof *challenge economics* and why optimistic rollups can rely on a single honest challenger rather than needing every participant to watch constantly:

```python
# untested sketch — illustrates the economic logic of optimistic rollup fraud proofs,
# not a functional dispute-resolution implementation
class OptimisticRollupBatch:
    def __init__(self, claimed_state_root, bond_amount, challenge_window_seconds):
        self.claimed_state_root = claimed_state_root
        self.bond_amount = bond_amount            # sequencer's posted bond, at risk
        self.challenge_window_seconds = challenge_window_seconds
        self.submitted_at = None
        self.challenged = False
        self.finalized = False

    def submit(self, at_time):
        self.submitted_at = at_time

    def challenge(self, fraud_proof_valid: bool, challenger_reward_from_bond):
        """A SINGLE honest, watching challenger is sufficient — this is the
        key economic property: you don't need a majority or even many
        watchers, because the bond makes fraud economically irrational
        against even a small probability of being caught by anyone."""
        if fraud_proof_valid:
            self.challenged = True
            # bad state reverted; sequencer's bond slashed, challenger rewarded
            return {"outcome": "fraud proven", "reward": challenger_reward_from_bond}
        return {"outcome": "challenge failed", "challenger_loses_own_stake": True}

    def try_finalize(self, current_time):
        if self.challenged:
            raise ValueError("cannot finalize a successfully challenged batch")
        if current_time - self.submitted_at >= self.challenge_window_seconds:
            self.finalized = True
        return self.finalized
```

The property worth being able to state precisely in an interview: fraud-proof security doesn't require *most* participants to actively watch every batch — it requires only that **at least one** honest, economically-motivated party is watching and willing to challenge, because the bond-slashing mechanism makes submitting fraudulent data a strictly losing bet against even a small probability of being caught by any single challenger, at any point during the entire window. This "single honest watcher" security model is a real, load-bearing assumption worth naming explicitly rather than glossing over — it's weaker than "everyone verifies everything" but importantly, dramatically cheaper to achieve at scale.

Full lab — including a simulated bridge with a configurable validator-signature threshold demonstrating exactly how few compromised signers are needed under different (m-of-n) configurations, and a walkthrough reconstruction of the Nomad bridge's zero-address trusted-root bug against a toy contract: **`labs/py/22-scaling/`**.

---

## How it's done in production

**Arbitrum and Optimism (OP Stack)** are the dominant optimistic rollups; Optimism's OP Stack additionally powers a growing ecosystem of OP Stack-based chains (Base, among others) sharing core rollup infrastructure design — a real, deliberate move toward standardized, audited rollup tooling rather than every chain reimplementing fraud-proof logic independently. **zkSync, Starknet, Polygon zkEVM, and Scroll** are among the production zkEVM implementations live by 2026, each with different tradeoffs in EVM-equivalence level (how close to *literally identical* Ethereum bytecode execution versus a functionally-equivalent-but-different VM) and proving-system architecture.

| Symptom | Cause | Fix |
|---|---|---|
| A user's L2-to-L1 withdrawal takes days and they're confused why | Optimistic rollup's challenge window (still commonly ~7 days) being confused with instant finality | Explain the fast-withdrawal liquidity-provider option (fee-for-speed) versus the slower, free, fully-trustless native path; this is expected behavior, not a bug |
| A rollup's state becomes unverifiable/unreconstructable even though the operator claims everything is fine | Data availability failure — the underlying transaction data was never actually retrievable, only a state root was posted (a Plasma-era failure mode) | Verify the specific rollup posts full transaction data (via blobs or another DA solution), not merely a commitment/root, before trusting its security model |
| A cross-chain bridge is drained with no apparent blockchain-level exploit on either connected chain | The bridge's own attestation/validator mechanism was compromised or bypassed directly (Ronin-style key compromise, Wormhole-style signature bug, Nomad-style access-control bug) — the underlying chains' own security was never touched | Treat every bridge as its own, independent, often less battle-tested trust boundary — minimize funds held in any single bridge, prefer bridges with higher validator/signer thresholds and longer audit history, and understand that a chain's own security says nothing about a bridge connected to it |
| ZK-rollup proof generation becomes a throughput bottleneck under high transaction volume | Proving infrastructure not scaled to match sequencer throughput, or an inefficient proving system for the specific workload | Specialized proving hardware, proof aggregation/batching, and continued proof-system efficiency improvements — an active, fast-moving area as of 2026, not a solved, static cost |
| Blob-posting costs spike during periods of high L2 activity | Blob demand exceeding available blob capacity in a given period, driving up the blob base fee via the same EIP-1559-style mechanism module 4 covered for regular gas | Fusaka/PeerDAS-driven blob capacity increases are the direct, ongoing protocol-level answer; individual L2s can also batch more efficiently to reduce per-transaction blob footprint |

---

## Tradeoffs & when NOT to use it

- **Don't treat "it's a rollup" as automatically meaning "as secure as L1."** A rollup's security is bounded by both its own fraud-proof/validity-proof correctness *and* its data-availability guarantees — a rollup posting data availability to something other than Ethereum L1 itself (a separate, less battle-tested DA layer) has a meaningfully different, generally weaker security model than one anchored fully to L1, and this distinction (sometimes marketed loosely as "L2" regardless) is worth interrogating specifically rather than assuming uniformly.
- **Don't recommend an optimistic rollup for a use case that genuinely needs fast, native (not liquidity-provider-fronted) finality**, and don't recommend a ZK-rollup reflexively where the operational complexity of proving infrastructure isn't actually justified by the specific application's finality-speed requirements — this remains a real, workload-dependent choice, not a settled "ZK wins" conclusion.
- **Don't hold significant value in any single bridge longer than necessary, regardless of that bridge's reputation or audit history.** The historical record (Ronin, Poly Network, Wormhole, Nomad, and the continuing 2026 pattern) spans bridges that were each considered reputable, audited infrastructure at the time they were exploited — "this bridge is well-established" has not historically been a reliable predictor of safety, and treating bridge risk as a solved, historical problem rather than an ongoing, structural one is a specific, checkable mistake.
- **Don't assume a higher validator/signer threshold on a bridge fully eliminates the concentrated-trust risk** — it raises the cost of compromise (Ronin's 5-of-9 threshold, in hindsight, was not high enough against a sufficiently resourced, patient attacker), but any m-of-n attestation scheme is still a meaningfully smaller, more concentrated trust surface than either connected chain's own full consensus mechanism, and framing a higher threshold as "solved" rather than "improved" understates the residual risk.
- **Don't design a system requiring cross-chain value transfer without treating the bridge itself as the primary security review focus**, disproportionate to the attention given the rollup or application logic on either side — the historical loss data makes an unambiguous, quantitative case that this is where the actual risk concentrates, not evenly distributed across the system.

---

## Interview questions

### Q1 — What's the mechanical difference between a fraud proof and a validity proof? Not the marketing description — the actual guarantee each provides.
**Testing:** whether the distinction is understood as a mechanism, not a slogan.
**Answer:** A fraud proof is a *reactive* mechanism: the system assumes a claimed state transition is correct by default, and relies on someone actively detecting and proving it wrong within a bounded challenge window — the guarantee is conditional on at least one honest party watching and successfully challenging in time. A validity proof is *proactive*: a cryptographic proof accompanying the claimed state transition mathematically demonstrates correctness before it's ever accepted, requiring no challenge period and no assumption that anyone is watching, because the proof itself is the guarantee.
**Follow-up trap:** *"Does a validity proof mean a ZK-rollup needs zero trust assumptions at all?"* — no: it removes the "someone must actively watch and challenge" trust assumption specifically, but data availability (can anyone actually get the underlying data to reconstruct state independently) and the correctness of the proving system itself (is the cryptographic construction actually sound, is the trusted setup, if any, legitimate) remain real, separate trust and correctness assumptions the validity proof alone doesn't eliminate.

### Q2 — Why do optimistic rollup withdrawals to L1 take roughly a week, and how do production systems make this invisible to most users?
**Testing:** the mechanism plus the practical mitigation, both required for a complete answer.
**Answer:** The L1 contract can't treat an L2 state as final until the challenge window (historically ~7 days on the major optimistic rollups) has passed without a successful fraud proof — shortening this window for UX would directly weaken the actual security margin the fraud-proof mechanism depends on. Production systems solve the UX problem without weakening the security window: third-party liquidity providers front users their withdrawal immediately (for a fee), then collect the genuine, fully-finalized withdrawal themselves once the real challenge window elapses — making the wait invisible to the end user while leaving the underlying trust-minimized security period unchanged.
**Follow-up trap:** *"Does using a fast-withdrawal liquidity provider change the security model for the withdrawing user?"* — yes, meaningfully: the user is now trusting the liquidity provider's solvency and honesty for the immediate funds, rather than relying purely on the trust-minimized native bridge mechanism — it's a real, if usually small and well-collateralized, additional trust dependency traded for speed, not a free UX improvement with no tradeoff at all.

### Q3 — Why is data availability described as "the real bottleneck" rather than raw computation, for rollup scaling?
**Testing:** whether the DA-as-bottleneck framing (versus a naive "rollups need faster computers" framing) is understood.
**Answer:** A rollup's security — both fraud-proof challengeability and independent state reconstruction — depends entirely on the underlying transaction data being retrievable by anyone who needs it, not merely on a claimed state root being posted. Plasma's specific, named historical failure was exactly this: committing to a state root on L1 while leaving the actual data off-chain meant an operator withholding that data could make the exit/challenge mechanism impossible to actually use, regardless of how computationally correct the underlying execution might have been. Rollups' defining improvement over Plasma is posting the *data itself* (now cheaply, via blobs), not just a commitment to it — which is precisely why Ethereum's roadmap (EIP-4844, Pectra, Fusaka/PeerDAS) has focused so heavily on cheap, scalable data availability specifically, rather than on raw L1 computational throughput.
**Follow-up trap:** *"If blob capacity keeps increasing, does data availability eventually stop being a meaningful constraint at all?"* — the direction of travel (PeerDAS, full danksharding's ~128-blobs-per-slot target) is toward dramatically higher capacity, but "eventually stop constraining" is a stronger claim than the roadmap actually supports — data availability capacity and rollup/application demand are both growing, and whether capacity durably outpaces demand indefinitely (versus periodically becoming a bottleneck again as adoption grows, as blob fee spikes during high-demand periods already demonstrate happening) is a genuinely open, ongoing question rather than a solved one.

### Q4 — Explain precisely why fraud-proof security only requires one honest watcher, not a majority.
**Testing:** the specific economic-incentive mechanism, since this is a commonly-misunderstood detail.
**Answer:** The sequencer posts a bond alongside every batch claim; a successful fraud proof, submitted by *any* single party, slashes that bond and rewards the challenger. This means submitting fraudulent data is a strictly losing bet for the sequencer as long as there's a meaningfully non-zero probability that at least one honest, economically-motivated party is watching at any point during the entire challenge window — the security doesn't require most or even many people watching constantly, just that the expected value of attempting fraud is negative given *some* realistic probability of being caught by anyone.
**Follow-up trap:** *"What happens if literally nobody is watching during a specific batch's challenge window?"* — this is a real, named concern sometimes called the "verifier's dilemma" or a data-availability/liveness assumption: the security model does depend on at least one economically-motivated watcher existing and being sufficiently incentivized (the potential reward needs to exceed the cost of running the infrastructure to watch and verify) — in practice, this is why rollup ecosystems specifically encourage and sometimes directly incentivize independent watchtower/challenger infrastructure, rather than assuming it emerges automatically with zero incentive design.

### Q5 — Name three major bridge hacks, their approximate losses, and the specific mechanism each exploited. What's the common structural thread?
**Testing:** whether specific incidents are known precisely enough to reason from, not just "bridges get hacked."
**Answer:** Ronin Bridge (March 2022, ~$625M) — attackers compromised 5 of 9 validator private keys, a direct key-compromise attack requiring no smart-contract bug at all. Wormhole (February 2022, ~$320M) — a signature-verification bug let an attacker mint 120,000 wrapped ETH on Solana without any real ETH deposit. Nomad (August 2022, ~$190M) — a faulty upgrade set a trusted-root value to the zero address, letting essentially anyone spoof valid-looking withdrawal messages. The common thread: each attack bypassed the bridge's own custom attestation/authorization mechanism specifically — none required compromising either connected blockchain's actual consensus, because the bridge's own, typically smaller and less battle-tested trust mechanism was the weaker link.
**Follow-up trap:** *"Since these are all from 2021-2022, hasn't bridge security improved substantially since then?"* — the specific *named* incidents are older, but the pattern hasn't stopped: 2026 alone recorded well over $340M in bridge-specific losses across dozens of incidents in just the first half of the year, with bridge vulnerabilities accounting for close to half of one quarter's total DeFi losses — the correct, current answer is that bridges remain an actively, currently exploited category, not a historical problem that's been solved.

### Q6 — A team wants to build a new DeFi protocol requiring users to move assets between three different chains. How would you approach the bridge component of this design, given everything covered in this module?
**Testing:** applying the module's central risk lesson to an actual architecture decision.
**Answer:** Treat the bridge as the primary security review focus, disproportionate to the attention given the application logic on any individual chain — this is where the historical loss data says risk concentrates. Prefer existing, higher-threshold, longer-audit-history bridge infrastructure over building a custom bridge, given how consistently even well-resourced, security-conscious teams' custom bridge mechanisms have been the point of failure. Minimize the value held in any single bridge's locked pool at any time where the application design allows it, and design explicit circuit breakers/pausability for the bridge component specifically, given how quickly these losses tend to occur once an attack begins (frequently a single transaction, not a slow drain).
**Follow-up trap:** *"Does using a well-established, audited bridge provider fully outsource this risk?"* — reduces but doesn't eliminate it: every bridge hack discussed in this module involved infrastructure that was considered reputable and, in most cases, audited at the time of the exploit — due diligence on a bridge provider is necessary but the historical record specifically argues against treating "audited and established" as sufficient to stop actively monitoring and limiting exposure; the responsibility doesn't fully transfer just because the bridge is someone else's product.

### Q7 — What specifically did EIP-4844 change, and why was posting rollup data via regular L1 calldata (the pre-2024 approach) a real, quantifiable problem?
**Testing:** the concrete mechanism and cost-numbers understanding of the DA scaling roadmap.
**Answer:** Before EIP-4844 (Dencun, March 2024), rollups posted their transaction data as regular L1 calldata, priced the same as any other transaction data and permanently stored by every L1 full node forever — a real, growing cost both directly (calldata gas pricing) and indirectly (permanent state/history growth for a category of data that only needs to be available temporarily, long enough for fraud-proof challenges and state reconstruction, not forever). EIP-4844 introduced "blobs," a separate, much cheaper data lane specifically for this use case, with blobs automatically pruned after roughly 18 days rather than persisted permanently — directly reducing the ongoing storage burden on L1 nodes while providing more than enough retention window for the fraud-proof and reconstruction use cases that actually need it.
**Follow-up trap:** *"If blobs are pruned after ~18 days, doesn't that mean old rollup transaction data becomes permanently unavailable/unverifiable after that point?"* — this is a real, worth-naming tradeoff: blob data itself isn't meant to be Ethereum's permanent historical archive — L2s and third-party archival services are expected to independently retain and serve older data for anyone needing deep historical reconstruction, while the ~18-day window specifically covers the *live security* use cases (active fraud-proof challenges, near-term state verification) that genuinely need L1-anchored, trustlessly-available data — it's a deliberate scope boundary, not an oversight, but it does mean "L1 blob storage" and "permanent historical record" are not the same guarantee.

### Q8 — What is PeerDAS, and why does distributing blob data across the network rather than requiring every node to store all of it not weaken data-availability guarantees?
**Testing:** whether the specific 2025-era mechanism is understood as a real technical advance rather than just "more capacity."
**Answer:** PeerDAS (Peer Data Availability Sampling, shipped with Fusaka, December 2025) has each node store only a fraction (roughly one-eighth) of total blob data, rather than the full set — which sounds like it should weaken guarantees, but the actual mechanism relies on *sampling*: any party wanting confidence that the full blob is actually available can request small, random samples from many different nodes, and if a large-enough number of independently-sampled pieces are retrievable, this provides strong statistical confidence that the full data is available across the network as a whole, without any single node needing to hold everything. This is the same fundamental tradeoff the scalability trilemma (module 3) describes — spreading the storage burden across more, individually-lighter participants, rather than concentrating full-data storage in fewer, heavier ones — applied specifically to data availability rather than state/execution.
**Follow-up trap:** *"What happens if an attacker specifically wants to withhold data while still passing sampling checks?"* — this is exactly the threat model PeerDAS's specific sampling parameters and erasure-coding techniques (redundantly encoding blob data so a full reconstruction is possible even if some fraction of pieces is withheld or unavailable) are designed to make infeasible: withholding enough of the *actual* data to prevent reconstruction while still successfully answering enough *random* sample requests to appear available requires withholding an implausibly small, specifically-targeted set that erasure coding's redundancy is designed to make statistically very hard to pull off without detection.

### Q9 — Compare the trust model of a rollup posting data availability to Ethereum L1 directly versus a rollup using a separate, non-Ethereum data-availability layer (sometimes marketed as a "validium" or similar). What's the actual difference in guarantee?
**Testing:** whether the candidate can distinguish marketing-level "L2" claims from the specific security anchor being used — a real, current architectural distinction.
**Answer:** A rollup anchoring data availability fully to Ethereum L1 inherits L1's own decentralization and security properties for that data — the same large, permissionless validator/node set securing Ethereum itself is what makes the rollup's underlying data genuinely, trustlessly available. A system posting only a state commitment to L1 while storing the actual transaction data on a separate, smaller, differently-secured DA layer (sometimes called a validium, or more broadly "off-chain DA") has a fundamentally different, generally weaker guarantee — that separate DA layer's own validator/operator set, not Ethereum's, is what determines whether the data is actually retrievable, and if that smaller set colludes or fails, the system inherits Plasma's exact historical failure mode (module content above) despite the smart-contract logic itself being a fully verified, correct rollup.
**Follow-up trap:** *"Does this mean any system using off-chain data availability is automatically insecure or a bad design?"* — no, and this is a real, legitimate architecture choice with an explicit tradeoff, not an automatic disqualifier: off-chain DA is typically meaningfully cheaper than L1 blob posting, and for applications where the value at risk or the specific threat model tolerates a different (not zero, but different and generally weaker) DA security assumption, it's a reasonable, deliberate choice — the failure mode is specifically *marketing* such a system with the same security language as a fully L1-anchored rollup without being explicit about the actual, different DA trust assumption being made, which is exactly the kind of imprecision this module's decision-test-adjacent thinking (module 8) should catch.

### Q10 — A team building a new ZK-rollup asks whether they should prioritize maximal EVM-equivalence (running unmodified Ethereum bytecode) or a custom VM optimized specifically for their proving system's efficiency. How do you frame the tradeoff?
**Testing:** whether the candidate understands the real, current (2026) engineering tension in zkEVM design, not just that ZK-rollups exist.
**Answer:** Maximal EVM-equivalence maximizes compatibility — existing Solidity contracts, tooling, and developer familiarity port over with minimal friction, which matters enormously for adoption given how large the existing Ethereum-tooling ecosystem is. A custom VM designed around what's efficient to generate validity proofs for can achieve meaningfully lower proving costs and faster proof generation, since general-purpose EVM opcodes weren't originally designed with ZK-proving efficiency in mind, and some operations are disproportionately expensive to prove relative to their computational simplicity. This is a real, live tradeoff in the field, not a solved question — by 2026 every major zkEVM implementation has made a specific point on this spectrum (from close-to-literal EVM equivalence to more custom, proving-optimized designs), and which point is "right" depends on whether the project's priority is ecosystem compatibility or proving-cost efficiency for its specific expected workload.
**Follow-up trap:** *"Is this tension likely to resolve as proving hardware and techniques keep improving, making the distinction less important over time?"* — plausible and directionally consistent with the trend (proof-generation costs have already dropped sharply since 2024 through specialized hardware and better proof systems), but asserting this as a settled, inevitable convergence would be overstating current certainty — it's reasonable to expect the compatibility-vs-efficiency tension to matter less as proving costs fall generally, but whether it disappears entirely or simply becomes a smaller, still-relevant factor is genuinely open, and a candidate should flag that distinction rather than presenting a confident prediction as fact.

---

## Red flags that fail you

- Describing the optimistic-vs-ZK distinction as merely "one uses zero-knowledge proofs and one doesn't" without naming the fraud-proof/validity-proof mechanism difference.
- Not knowing that data availability, not raw computation, is the primary scaling bottleneck rollups are built to solve.
- Treating bridge hacks as a solved, historical (2021-2022-only) problem rather than an ongoing, currently-recurring category.
- Claiming a rollup is "as secure as L1" without qualifying that both its proof mechanism and its data-availability anchor need to be evaluated.
- Not knowing that optimistic rollup withdrawal delays are commonly worked around via fee-based liquidity providers, not by shortening the actual security-relevant challenge window.
- Recommending building a custom bridge without acknowledging the historical loss data's clear pattern.

---

## Cheat card

```
ROLLUP CORE IDEA: execute off L1, but post enough DATA to L1 that anyone can
  independently reconstruct/verify state. L1 decentralization+security still constrains
  the L2 operator. This is the trilemma's (module 3) practical current answer.

OPTIMISTIC ROLLUP (Arbitrum, OP Stack/Optimism/Base): assume valid by default.
  FRAUD PROOF = anyone can challenge within a CHALLENGE WINDOW (~7 days historically).
  Successful challenge = bad state reverted, sequencer's bond slashed, challenger rewarded.
  SECURITY NEEDS ONLY 1 HONEST WATCHER, not majority -- bond math makes fraud -EV vs ANY
  nonzero catch probability. Withdrawals slow natively; fee-based liquidity providers
  front funds instantly in production, making the wait invisible to users (real tradeoff:
  now trusting the LP's solvency too).

ZK-ROLLUP (zkSync, Starknet, Polygon zkEVM, Scroll -- all production by 2026):
  VALIDITY PROOF (SNARK) attached to every batch, mathematically proves correctness
  BEFORE acceptance -- no challenge window needed. Withdrawals finalize in MINUTES.
  Historically: expensive proof generation for general EVM execution. 2026: costs
  dropped sharply via specialized proving hardware + better proof systems; every major
  zkEVM in production, EVM-compatibility gap largely closed.

DATA AVAILABILITY = the real bottleneck, not compute. Plasma's fatal flaw (2017-era):
  posted state ROOT only, not the DATA -- operator could withhold data, breaking
  exit/challenge entirely regardless of correctness. Rollups fix this: post the DATA.
  EIP-4844 blobs (Dencun, Mar 2024): cheap temporary DA lane, pruned ~18 days.
  Pectra (May 2025): doubled blob capacity. Fusaka/PeerDAS (Dec 2025): distributes
  blobs so each node stores ~1/8, ~10x DA capacity increase. Danksharding endgame: ~128
  blobs/slot. Blob fees still spike under high demand (EIP-1559-style market).

BRIDGES = the actual danger, structurally concentrated trust (locked pool + a small
  attestation mechanism -- contract/validators/multisig) independent of either chain's
  OWN consensus security. NOT a solved historical problem:
  Ronin (Mar 2022, ~$625M): 5-of-9 validator KEY COMPROMISE (Lazarus Group)
  Poly Network (Aug 2021, ~$612M): keeper-role redirect via contract bug
  Wormhole (Feb 2022, ~$320M): signature-verification bug, minted 120K wETH from nothing
  Nomad (Aug 2022, ~$190M): trusted-root set to zero address, anyone could spoof withdrawals
  2026: $340M+ bridge losses in H1 alone; Q2 2026 bridges = ~half of $755M total DeFi losses.
  Higher m-of-n threshold REDUCES but doesn't ELIMINATE concentrated-trust risk.

WRONG TO SAY: "rollup = as secure as L1" (depends on DA anchor + proof correctness too).
  "ZK strictly beats optimistic" (workload-dependent, EVM-compat gap narrowing not gone).
  "bridge hacks are a 2021-2022 problem" (actively, currently recurring in 2026).
```

## Sources

- [EIP-4844: Shard Blob Transactions](https://eips.ethereum.org/EIPS/eip-4844) — accessed 2026-08-08
- [ethereum.org — PeerDAS](https://ethereum.org/roadmap/fusaka/peerdas/) — accessed 2026-08-08
- [Alchemy — What Is the Ethereum Fusaka Upgrade? Dev Guide to 12 EIPs](https://www.alchemy.com/blog/ethereum-fusaka-upgrade-dev-guide-to-12-eips) — accessed 2026-08-08
- [eco.com — What Is an Optimistic Rollup? A 2026 Layer 2 Guide](https://eco.com/support/en/articles/10080398-what-is-an-optimistic-rollup-a-2026-layer-2-guide) — accessed 2026-08-08
- [eco.com — What Is a ZK Rollup? A 2026 Guide to Zero-Knowledge Scaling](https://eco.com/support/en/articles/10080409-what-is-a-zk-rollup-a-2026-guide-to-zero-knowledge-scaling) — accessed 2026-08-08
- [KuCoin — Top Crypto Hacks of 2026: Bridge Exploits and Sophisticated Operations](https://www.kucoin.com/blog/th-top-crypto-hacks-2026-bridge-exploits) — accessed 2026-08-08
- [blockchain.news — Q2 2026 Breaks Record with 83 Crypto Hacks, $755M Stolen](https://blockchain.news/news/q2-2026-most-hacked-quarter) — accessed 2026-08-08
- [Coingabbar — $340M Lost: 14 Crypto Hacks 2026 Targeting Bridges](https://www.coingabbar.com/en/crypto-currency-news/crypto-hacks-2026-14-bridge-attacks-security-concerns) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
