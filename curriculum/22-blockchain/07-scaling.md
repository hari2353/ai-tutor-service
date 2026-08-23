# Rollups (Optimistic vs ZK), Data Availability, Bridges and Their Failures

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** T22-bitcoin-ethereum · **Updated:** 2026-08-23
> **Module id:** `T22-scaling` · **Tags:** blockchain, scaling, l2, critical

## The 30-second version

Base layers are throughput-capped by replication — every node re-executes everything — so scaling means moving execution off-chain while renting the L1's security for *data* and *settlement*. Two families dominate. Optimistic rollups (Arbitrum, OP Mainnet/Base) post batches and assert state roots that stand unless challenged: anyone has a ~7-day fraud window to submit a proof that re-executes a disputed step on-chain, so safety rests on at least ONE honest verifier existing — cheap execution, slow exits. ZK-rollups (Starknet, zkSync) attach a succinct validity proof per batch that an L1 contract verifies mathematically in one transaction: no window, no honest-party assumption, finality in minutes-to-hours — at the price of prover infrastructure and varying EVM compatibility. Data availability is the actual bottleneck: Ethereum's blob market (128 KiB blobs, target raised from 3 to 6 in May 2025, then 10 and 14 through Fusaka's BPO forks ending January 2026) exists precisely so rollups stop paying for permanent state. Bridges are the graveyard: $2B+ stolen across 13 cross-chain bridge hacks in 2022 alone (Ronin $625M, Wormhole $325M, Nomad $190M) because most verified attestations with small multisigs rather than cryptographic proofs.

## Why this gets asked

Because rollup selection is the highest-frequency architecture decision in production blockchain work, and interviewers want the reasoning, not brand loyalty. The sharp questions are mechanical: why does optimism need seven days (the window equals maximum challenge time, and your withdrawal waits for it unless a liquidity provider fronts you)? What does "1-of-N honest" actually buy you versus ZK's "0-of-N"? Why did blobs make L2 fees collapse ~10× overnight in March 2024, and what does blob *pruning* after ~18 days mean for long-run data guarantees? Bridge questions are trust-distribution questions wearing crypto clothes: given Ronin fell to five phished keys out of nine and Wormhole fell to a signature-check bug, what would you actually deploy — and candidates who rank designs by "who can steal everything and how many of them must collude" answer correctly regardless of marketing. Expect a system-design variant: "design a bridge between two EVM chains" — the answer's skeleton is light clients plus proof verification, never a multisig with a dashboard.

## Lineage

**What came before.** Scaling theory predates working products by years: state channels (2015-17, Lightning-style) bought instant off-chain throughput but only for known participants with locked collateral; Plasma (Poon-Buterin, August 2017) generalized periodic commitments to L1 and briefly consumed the entire ecosystem's imagination, then died against its own geometry — mass-exit games during operator misbehavior required users to watch for fraud personally, and data unavailability meant nobody could even prove which exits were valid. The lesson Plasma taught became rollups' foundation: keep the DATA on the settlement layer, move only computation. Optimistic designs shipped first because fraud proofs are simple: Arbitrum One went live August 31, 2021, OP Mainnet December 2021. ZK took longer because proving general EVM execution is genuinely hard — early zk systems (zkSync 1.0, 2020; StarkEx) proved only bespoke circuits for transfers/swaps.

**Where it stands now.** Rollups carry the majority of Ethereum-ecosystem activity since 2023-24. The Dencun upgrade's proto-danksharding (March 13, 2024) created dedicated blob space and collapsed L2 fees from dollar-scale to cent-scale overnight; Pectra (May 7, 2025) doubled blob targets to 6; Fusaka (December 3, 2025) activated PeerDAS — nodes sample erasure-coded fragments instead of downloading whole blobs — and introduced Blob-Parameter-Only forks that pushed targets/maxes to 10/15 (December 2025) then 14/21 (January 2026) without full hard forks. On the optimistic side, permissionless fault proofs landed: OP Stack's fault-proof system went live mid-2024 and Arbitrum replaced its allowlisted validators with BoLD (permissionless, bisection-based) in February 2025. ZK-side, Starknet and zkSync ship full proving pipelines with costs falling toward cents-per-batch, and the L2BEAT "stages" framework (Stage 0 training wheels → Stage 1 limited → Stage 2 full autonomy) became the industry's honesty metric — most major rollups sat at Stage 1 during 2025, with sequencers still centralized and upgrade keys still warm. Bridges bifurcated into intent-based routing (Across, Stargate) over canonical lock-mint paths, plus Circle's CCTP making native burn-and-mint the default for USDC.

**Where it's heading.** Three tracks. First, interoperability collapses the bridge problem itself: shared sequencing (Espresso), Superchain-style message passing, and intent-based execution aim to make "which chain am I on" a routing detail rather than a trust decision — direction certain, timeline contested. Second, proving keeps getting cheaper: real-time proving (a proof before the next L1 slot) is Starknet/zkSync's stated bar for Stage-2-grade soft-finality, and specialized prover hardware/markets are forming — high confidence this reaches commodity pricing by 2027. Third, DA keeps compounding: PeerDAS unlocks ~8× headroom toward 48 blobs/block, with further sampling research queued behind Glamsterdam; the endgame remains danksharding where blobs become protocol-native sharded data. Speculative flag: whether application-specific rollups (one chain per app, Orbit/CDK-style) fragment liquidity fatally or compose cleanly through shared sequencing is genuinely undecided — reasonable engineers hold opposite positions.

---

## Mental model

```
THE COURTROOM

OPTIMISTIC ROLLUP          = innocent until proven guilty
  operator asserts verdict ─────────────────────────────┐
  7-day appeal window                                   │ anyone can appeal:
  appeal = FRAUD PROOF (re-execute disputed step)       │ 1 honest verifier
  verdict stands if unchallenged ◀──────────────────────┘ suffices (1-of-N)

ZK ROLLUP                  = mathematical notarization up front
  operator attaches VALIDITY PROOF with every batch
  L1 verifies proof in one call (~hundreds of k gas)
  no window, no trust assumption - cryptography (0-of-N)

DATA AVAILABILITY          = the court RECORD
  judges (L1 nodes) must be able to READ the evidence to rule;
  blobs = temporary evidence room (pruned ~18 days);
  validium = trusting the clerk's summary without records (cheaper, weaker)

BRIDGE                     = extradition treaty
  who certifies 'this really happened over there'?
  5 phished humans (Ronin) < buggy signature check (Wormhole/Nomad)
      < light client verifying the other chain's headers (IBC/Rainbow)
```

The single sentence tying it together: **rollups rent L1 security for two things — data availability and dispute resolution — and every design choice is about how much of each you buy.**

## How it actually works

### Rollup anatomy, both flavors

Shared skeleton: a sequencer receives transactions, orders them, executes against local state, compresses batches, posts data to L1 (blobs since Dencun; calldata before), and publishes state roots to an L1 bridge contract holding canonical deposits/withdrawals. Withdrawals reverse the flow: burn on L2, prove inclusion in L1-verified data, mint. The flavors differ entirely at *verification*:

**Optimistic pipeline.** Operator asserts post-batch root → assertion enters pending state with bond → any verifier re-executes the batch from L1-available data; disagreement opens a dispute game that bisects computation until one instruction remains, which an on-chain mini-interpreter adjudicates; loser's bond pays winner; window expires → finalized. Costs: no proving infra, native EVM fidelity. Weaknesses: sequencer ordering power, warm upgrade keys (Stage 1 vs 2 gap).

**ZK pipeline.** Operator runs prover infrastructure generating a succinct proof that the new root follows from old root plus posted data under correct VM rules; L1 contract verifies (~100s of k gas regardless of batch size); finality lands when proofs do — minutes-to-hours currently, with real-time proving (proof within one 12-second slot) as the industry's stated next bar. Prover costs fell from dollars-per-transaction (2020 circuits) toward cents-per-thousand-transactions via recursion and specialized hardware. The zkEVM type taxonomy (1→4) prices compatibility against prover speed.

### Data availability mechanics

A rollup's safety claim reduces to: *anyone can read the data needed to reconstruct state and prove fraud*. That's why data placement IS the trust model. Blob facts: 131,072 bytes each, independent fee market with exponential adjustment around target counts, pruned after ~4096 epochs (~18 days) — consensus guarantees availability only through the challenge window, deliberately not forever. PeerDAS (Fusaka): erasure-code each blob into 128 columns; nodes custody a subset proportional to validator count and randomly sample others — statistically, successful samples imply full-data existence without anyone downloading everything, letting blob targets scale toward 48 while per-node load stays bounded.

External DA layers trade this: Celestia erasure-codes across its own validator set with light-client sampling; EigenDA uses restaked ETH security committees; Avail similar sampling designs. Each replaces "Ethereum validators hold my bytes" with a different economic security pool — legitimate, but your rollup's stage rating drops accordingly (validium-class unless settling disputes on Ethereum with Ethereum-readable data).

### Bridge mechanics and their failure catalog

| Model | Verification | Failure mode | Example |
|---|---|---|---|
| Committee/multisig | n-of-m humans sign attestations | key phishing/collusion | Ronin $624M (5-of-9 phished) |
| Oracle network | independent attesters stake/reputation | code bugs in verification | Wormhole $325M (forged sig path) |
| Light client | verify source-chain headers + Merkle proofs | client bugs, header sync weight | Nomad $190M (zero-proof init) |
| Burn-mint native | issuer burns on A, mints on B | issuer centralization only | Circle CCTP for USDC |
| Intent/filler | fillers deliver instantly, settle later | filler solvency, auction health | Across, Stargate class |

The pattern across 2022's thirteen bridge failures totaling $2B+: nearly all verified attestations with small human committees or single signature checks rather than cryptographic proofs of source-chain consensus. Ronin's five phished keys were validators for Axie Infinity's sidechain economy; Wormhole's bug let anyone forge guardian approval on Solana (Jump Capital recapitalized to restore wrapped-ETH backing); Nomad's initialization made empty proofs validate, producing a chaotic public free-for-all within hours.

## Build it from scratch

A mini optimistic rollup — data posted to L1, assertion with fraud window, challenge slashing a dishonest operator — plus the bridge trust-model contrast (multisig vs light client). Stdlib-only, verified below.

```python
"""Mini optimistic rollup (fraud window) + bridge trust models."""

import hashlib

def H(b): return hashlib.sha256(str(b).encode()).hexdigest()[:16]

class L1:
    """Simulated settlement layer: blobs, assertions, disputes."""
    def __init__(self):
        self.blobs = {}            # id -> tx list (data availability)
        self.assertions = []       # pending -> finalized | slashed
        self.finalized = []
        self.window_blocks = 100   # stand-in for 7 days (~50400 L1 blocks)

    def post_batch(self, bid, txs):
        self.blobs[bid] = txs                      # THE data availability act
        return H(txs)

    def assert_root(self, bid, root):
        self.assertions.append({'bid': bid, 'root': root,
                                'status': 'pending', 'expires': self.window_blocks})

    def tick(self):                                # one block passes
        for a in self.assertions:
            if a['status'] == 'pending':
                a['expires'] -= 1
                if a['expires'] <= 0:
                    a['status'] = 'finalized'
                    self.finalized.append((a['bid'], a['root']))

    def challenge(self, bid, honest_root):
        for a in self.assertions:
            if a['bid'] == bid and a['status'] == 'pending':
                correct = H(self.blobs[bid])       # real chains re-execute the
                if honest_root == correct != a['root']:   # disputed step on-chain
                    a['status'] = 'slashed'        # dishonest operator loses bond
                    return True
        return False

l1 = L1()
txs = ['alice->bob:5', 'bob->carol:2']
l1.post_batch('b1', txs)
honest_root = H(txs)
l1.assert_root('b1', honest_root)
for _ in range(100): l1.tick()
assert ('b1', honest_root) in l1.finalized         # unchallenged => final

l1.post_batch('b2', ['alice->bob:5', 'bob->attacker:99999'])
l1.assert_root('b2', 'FAKE_ROOT_I_WISH')
assert l1.challenge('b2', H(l1.blobs['b2']))       # challenger wins within window
```

```python
# ---------- bridges: committee trust vs cryptographic verification ----------
class MultisigBridge:
    """Ronin-class: k-of-n humans sign attestations. Keys leak -> theft."""
    def __init__(self, keys, threshold):
        self.keys, self.threshold, self.vault = set(keys), threshold, 1_000_000_000

    def withdraw(self, sigs, to, amt):
        if len(set(sigs) & self.keys) >= self.threshold:
            self.vault -= amt                     # NO proof of real deposit needed!
            return f'sent {amt:,} to {to}'
        raise PermissionError('insufficient signatures')

class LightClientBridge:
    """Verifies source-chain headers + Merkle proofs. No committee to phish."""
    def __init__(self):
        self.headers = {H(f'header{i}'): i for i in range(10)}
        self.vault = 1_000_000_000

    def withdraw(self, header_hash, merkle_proof, to, amt):
        if header_hash not in self.headers:
            raise PermissionError('unknown/forged header rejected')
        if not merkle_proof:
            raise PermissionError('invalid inclusion proof')
        self.vault -= amt
        return f'sent {amt:,} to {to} via verified inclusion'

ronin = MultisigBridge(keys=[f'k{i}' for i in range(1, 10)], threshold=5)
print(ronin.withdraw({'k1','k2','k3','k4','k5'}, 'lazarus', 624_000_000))
print(f'  vault now: {ronin.vault:,}  <- went NEGATIVE: unbacked IOUs minted')

lc = LightClientBridge()
try:
    lc.withdraw(H('forged-header'), None, 'attacker', 624_000_000)
except PermissionError as e:
    print('light-client bridge:', e)
```

The rollup half shows optimism's whole bargain in twenty lines: data availability makes challenges *possible*, the window bounds how long challenges may arrive, and an invalid assertion only survives if nobody honest looks. The bridge half reproduces history: five phished keys out of nine let "Lazarus" drain $624M while driving the vault negative — the bridge minted claims against deposits that never existed, which is precisely what happened to Ronin in March 2022; the light-client version rejects the forged attestation at the header check because there are no human keys to phish. Deliberate omissions: no bisection dispute game (real Arbitrum narrows disputes to a single instruction before on-chain arbitration), no erasure coding or sampling for DA, no Merkle proof construction (a boolean stands in).

## How it's done in production

**The rollup stacks.** OP Stack powers OP Mainnet, Base (Coinbase, launched August 2023), Unichain, World Chain — a shared Superchain vision with interoperable messaging. Arbitrum Orbit spins app-chains settling to Arbitrum One. zkSync's ZK Stack, Polygon CDK, and Starknet's appchains cover the ZK side. Choosing means weighing ecosystem liquidity (OP/Arbitrum dominate), decentralization stage (L2BEAT framework: Stage 0 training wheels → Stage 1 limited → Stage 2 no-trust), and proving maturity.

| Dimension | Optimistic (Arbitrum, OP/Base) | ZK (Starknet, zkSync Era) |
|---|---|---|
| Trust assumption | 1-of-N honest verifier | cryptography (0-of-N) |
| Finality for withdrawals | ~7 days (LPs bridge instantly for fee) | minutes-to-hours (proof cadence) |
| Soft confirmation | seconds (sequencer) | seconds + proof-backed within hours |
| EVM compatibility | native equivalence | zkEVM types 2-4 (Vitalik taxonomy) |
| Operating cost | low (no proving) | prover infra; falling toward cents/batch |
| Maturity | years of mainnet, BoLD permissionless proofs (Feb 2025) | full proving live; real-time proving the 2026 bar |

**Data availability economics.** Blobs cost a fraction of calldata for equivalent bytes; L2 fees fell roughly 10× after Dencun (March 13, 2024). Blob supply: target/max 3/6 → 6/9 (Pectra, May 2025) → 10/15 (BPO1, Dec 2025) → 14/21 (BPO2, Jan 2026), with PeerDAS enabling further growth toward 48. Pruning (~4096 epochs ≈ 18 days) means rollups must archive their own history long-term — DA guarantees are time-boxed by design.

**Failure-mode table:**

| Symptom | Cause | Fix |
|---|---|---|
| "Chain is down" but funds intact | Sequencer outage (Base had two in Sept 2023) | Forced-inclusion path via L1; status page honesty; multiple sequencers |
| Withdrawal stuck past 7 days | Challenge period extension or bug | LP fast-exit services; escalation via security council |
| Invalid state accepted briefly | No permissionless challenger online | Permissionless fault proofs (BoLD/OP FP); bounty for challenges |
| Validium loses data | DAC committee offline/colludes | Prefer full rollup mode; insure committee risk |
| Bridge vault drained without deposits existing | Committee keys phished (Ronin $624M, Mar 2022) or sig-check bug (Wormhole $325M, Feb 2022; Nomad zero-proof init bug $190M, Aug 2022) | Light clients/zk bridges; rate limits; monitoring on mint events |
| Bridge paused for weeks post-hack | Centralized kill switch | Decentralized validation trades pause-capability for safety |

## Tradeoffs & when NOT to use it

- **Optimistic vs ZK is latency vs assurance, mostly.** Choose optimistic when exit latency can be financialized away (LPs, exchanges crediting early) and you want maximal EVM fidelity today; choose ZK when trust-minimized fast finality is the product (institutional settlement, high-value bridging). Both converge as proving gets cheap.
- **Validiums sell cost for trust**: keeping data off-chain cuts fees dramatically but reintroduces an availability committee — if they withhold data, assets freeze. Volitions let users pick per-asset. For anything custody-like, full rollup.
- **Don't build a bespoke bridge where a canonical one exists.** Native burn-mint (CCTP for USDC) beats lock-mint wrappers beats committees. Every extra validator set is another Ronin waiting for its five phished keys.
- **Sequencer centralization is the open wound**: ordering power = MEV extraction + censorship ability. Mitigations exist (forced inclusion via L1 every N blocks, fee-switch governance, shared sequencers like Espresso) but none shipped at scale everywhere yet — ask any rollup team for their forced-inclusion path before deploying serious TVL.
- **Stage 1 ≠ Stage 2**: most major rollups still carry upgrade keys that could change rules faster than users can exit. Read the L2BEAT stage page like a prospectus; "rollup" marketing and actual trust assumptions diverge.
- **When rollups are overkill:** single-app internal ledgers don't need shared DA markets; a database with periodic anchoring remains unbeatable value. Rollups solve multi-party neutrality problems, not throughput-for-yourself problems.

## Interview questions

### Q1 — Why do optimistic rollups need a 7-day challenge window, and who enforces it?
**Testing:** core mechanics, not vibes.
**Answer:** The window equals the maximum time an honest verifier needs to detect and prove fraud: detect (sync data, re-execute), then litigate through the dispute game to a one-step on-chain proof. Seven days is engineering headroom for worst-case dispute depth plus L1 congestion, not magic. Enforcement: the L1 bridge contract refuses finalization until the window passes; any challenger can extend/revert via a valid fraud proof; Arbitrum's BoLD (Feb 2025) made challenging permissionless rather than allowlisted.
**Follow-up trap:** *"So users wait a week to exit?"* — No: liquidity providers front withdrawals instantly for a fee (~0.1-1%), and centralized exchanges credit deposits on soft confirmations. The window binds trust-minimized settlement, not UX, if markets exist.

### Q2 — What does "1-of-N honest assumption" mean versus ZK's assumption?
**Testing:** trust-model precision.
**Answer:** Optimistic safety holds if AT LEAST ONE honest party watches every assertion and challenges invalid ones within the window — liveness of challenges is social/economic, safety degrades only if literally everyone is asleep or bribed simultaneously. ZK-rollups need zero honest watchers: validity proofs are verified mechanically by L1 math; an invalid state transition cannot finalize even with universal collusion among operators. Tradeoff: ZK pays prover costs upfront for that property.
**Follow-up trap:** *"Doesn't 1-of-N make optimistic chains insecure?"* — Quantify: watchers include competing teams with staked capital and bounties; attacks require corrupting ALL simultaneously during the window. Real incidents come from upgrade keys and sequencer bugs, not broken challenges. But it IS weaker than cryptographic certainty — say so plainly.

### Q3 — Explain how a fraud proof dispute actually resolves on-chain.
**Testing:** bisection mechanics depth.
**Answer:** Challenger asserts operator's post-state root is wrong for batch B. Dispute game: both parties submit intermediate state roots at successive halves of the computation until they disagree about ONE step (bisection). The L1 contract then re-executes that single instruction/step via a minimal on-chain interpreter and declares the winner; losers forfeit bonds. Arbitrum's BoLD removed multi-round timing games by letting challengers address any assertion in parallel with fixed deadlines.
**Follow-up trap:** *"Why not verify the whole batch on-chain?"* — That's just an L1 again: full re-execution defeats scaling. Bisection amortizes verification to O(log steps) L1 work per dispute, which is the entire trick making optimistic verification cheap.

### Q4 — Lay out Vitalik's zkEVM type taxonomy and its practical tradeoffs.
**Testing:** ZK-side literacy beyond buzzwords.
**Answer:** Type 1: fully Ethereum-equivalent (verifies L1 blocks themselves) — max compatibility, slowest proving. Type 2: EVM-equivalence (Solidity-level; subtle gas/differences) — Scroll, Taiko-class. Type 2.5: EVM-equivalent except gas-cost tweaks that ease proving. Type 3: almost-equivalent, some precompiles/syscalls removed. Type 4: language-level — compile Solidity/Vyper to a zk-friendly IR (zkSync Era): fastest proving but bytecode-level incompatibilities break tooling edge cases. Compatibility decreases as proving cost falls along the spectrum.
**Follow-up trap:** *"Which type wins?"* — Convergence pressure runs both directions: provers improve toward Type 1-2 while apps demand equivalence; but Type 4 chains ship today. Answer with workload fit, not religion.

### Q5 — Why is data availability THE bottleneck, and what did blobs change?
**Testing:** systems reasoning about where bytes live.
**Answer:** Execution scales horizontally (parallelism, better VMs), but consensus requires every validator to hold the data guaranteeing rollup safety — bandwidth/storage bound what the network can promise. Pre-Dencun, rollups posted batches as calldata paying permanent-state prices; Dencun (March 13, 2024) added blobs: separate fee market, ~128 KiB each, pruned after ~18 days, target 3 → 6 (Pectra) → 14 (BPO2, Jan 2026). L2 fees dropped roughly an order of magnitude overnight because supply finally met demand in dedicated space.
**Follow-up trap:** *"If blobs get pruned after 18 days, isn't history lost?"* — Consensus guarantees availability only for the challenge/settlement window; long-term archival shifts to rollups themselves, indexers, and third parties. That's deliberate: permanent storage was pricing out throughput. State the time-boxing explicitly.

### Q6 — Validium vs rollup vs volition — pick for a high-value exchange product.
**Testing:** DA-trust tradeoff judgment.
**Answer:** Rollup: data on Ethereum — trust-minimized, blob costs. Validium: data off-chain behind a committee (StarkEx heritage) — near-zero DA fees, but committee withholding freezes assets; acceptable for exchange-internal custody where the operator already holds keys. Volition: per-account choice. For a high-value EXCHANGE product specifically: the operator's custody risk dominates anyway, so validium's marginal risk is small — but market-facing products should default rollup and price the difference honestly.
**Follow-up trap:** *"Committees never lost funds though?"* — They've frozen them: DAC outages lock exits without stealing. Freezing is theft when positions are leveraged. Frame committee risk as availability, not integrity — different mitigation (SLAs, redundancy, insurance).

### Q7 — Rank Ronin, Wormhole, Nomad by root cause and name the design lesson each teaches.
**Testing:** incident literacy mapped to design principles.
**Answer:** Ronin ($624M, March 2022): five of nine validator multisig keys phished (Lazarus) — lesson: committees are key-management problems; n-of-m humans are phishable. Wormhole ($325M, Feb 2022): deprecated signature-verification path on Solana accepted forged guardian signatures — lesson: signature verification bugs are fatal where signatures ARE trust; Jump recapitalized to save wrapped ETH backing. Nomad ($190M, Aug 2022): initialization made zero-value proofs pass as valid, triggering a copy-paste free-for-all across hundreds of addresses — lesson: initialization and canonical-message checks need adversarial test vectors. Aggregate: $2B+ across 13 bridges in 2022 alone (Chainalysis).
**Follow-up trap:** *"So no trusted bridges ever?"* — Pragmatics: light-client bridges (IBC, Near Rainbow, zk-based like Succinct/Polymer) exist and scale; intents/routers over canonical paths reduce exposure surface. The lesson is minimizing WHO can steal everything, ideally to "nobody, cryptographically."

### Q8 — Design a bridge between two EVM chains you don't control.
**Testing:** system design under trust constraints.
**Answer:** Skeleton: on each side, deploy light-client contracts verifying the other chain's headers (sync committee or ZK-proven execution headers), message passing with Merkle inclusion proofs against posted roots, replay protection via nonces, rate limits per asset with anomaly-based throttling, and a governance timelock for client updates. Add monitoring on mint events and circuit-breaker pausability held by a security multisig distinct from upgraders. Avoid: single attestation committees for anything above insurance-covered value.
**Follow-up trap:** *"Header sync on PoS chains is heavy — realistic?"* — Yes, that's why ZK attestations (prove consensus of source chain once, verify cheaply forever) are replacing naive header sync; cite Polymer/Succinct-class designs. Acknowledge the prover cost as the current tax.

### Q9 — What does Stage 1 vs Stage 2 mean, and why should an integrator care?
**Testing:** operational due-diligence literacy.
**Answer:** L2BEAT stages grade rollup autonomy: Stage 0 = training wheels (operators can override fraud proofs/upgrades unilaterally); Stage 1 = proofs live permissionlessly but security council can intervene under defined conditions (e.g., bug response windows); Stage 2 = no trust — invalid states can't finalize, upgrades bounded by user exit windows even if keys misbehave. Integrator care: your withdrawal guarantees, censorship exposure, and upgrade risk differ categorically; most majors sat at Stage 1 through 2025 with warm sequencer/proving caveats.
**Follow-up trap:** *"Stage numbers are self-reported?"* — Framework criteria are public and L2BEAT audits claims against code; still, read their evidence links yourself. 'Trust but verify' applies doubly to marketing terms like 'secured by Ethereum'.

### Q10 — Sequencers are centralized. Why hasn't this been catastrophic, and what fixes are real?
**Testing:** separating chronic weakness from acute failure.
**Answer:** Not catastrophic because sequencing controls ORDERING and availability, not custody: users retain forced-inclusion escape hatches (submit via L1 inbox) and assets remain recoverable during outages (Base's Sept 2023 outages froze UX, not funds). It IS catastrophic for fairness: MEV extraction, soft-censorship, and latency games. Real fixes: forced-inclusion enforcement hardening, shared/decentralized sequencer sets (Espresso, Superchain interop), based rollups (Ethereum proposers sequence directly), and multiple competing sequencers with rotation.
**Follow-up trap:** *"Based rollups sound strictly better?"* — They inherit L1 proposer decentralization but sacrifice sequencing latency (12s slots) and MEV auction integration; fast apps hate it. Tradeoffs all the way down.

### Q11 — Your CTO asks: rollup vs appchain for our product. Give the decision tree.
**Testing:** architecture judgment synthesis.
**Answer:** Default: general-purpose rollup (Base/Arbitrum) if you need composability with existing liquidity and minimal ops. App-specific rollup (Orbit/CDK/zkStack) if: custom fee tokens/gas economics, dedicated blockspace for performance isolation, sovereignty over upgrades, and you can staff infra. L1 appchain only if consensus-level customization is essential AND token-funded security exists. Always model: liquidity fragmentation cost, bridge exposure to settle anywhere, team ops burden, and stage/decentralization requirements of your compliance posture.
**Follow-up trap:** *"We want OUR gas token."* — Legitimate appchain trigger, but check whether points/loyalty on an existing chain plus an ERC-20 achieves 90% of the goal without splitting security. Most 'we need a token' requirements survive contact with that cheaper option.

### Q12 — Estimate the cost for a rollup posting 50 kB/s continuously. Where does it go?
**Testing:** back-of-envelope fluency with real units.
**Answer:** 50 kB/s ≈ 160 GB/month ≈ ~1,220 blobs/day equivalent at 131,072 bytes each... simpler: at 14-target era, blob space is scarce; historically blob fees ranged 1 wei floor to dollars. Rough order: 160 GB/month × $0.01-0.10/GB-blob-market ≈ low thousands USD/month at quiet markets, spiking 10-100× under contention (March 2024-style bursts hit hundreds-of-thousands daily across all rollups). Plus L1 execution overhead (state root updates ~100-200k gas/batch), prover costs if ZK, and archival. The honest answer: quote the mechanism (per-byte blob auction + fixed overheads), give ranges, flag volatility.
**Follow-up trap:** *"Why not just use calldata if blobs spike?"* — EIP-7623's calldata floor closed that arbitrage; external DA (Celestia/EigenDA) trades cost against Ethereum-settled security. Every path re-prices the same underlying question: whose nodes must hold your bytes?

### Q13 — What breaks in a rollup during an L1 reorg?
**Testing:** layered-systems thinking.
**Answer:** Anything finalized on the rollup referencing L1 state below the reorg depth becomes inconsistent: bridge deposits counted that no longer happened, oracle updates reverted, forced-inclusion txs vanish. Mitigations: rollups derive canonical L1 blocks only past finality (or deep-confirmations pre-Merge-era), treat L1-derived events with finality tags, and pause bridging when L1 reorg alarms fire. Conversely, L1 doesn't care about rollup state — asymmetry is safe.
**Follow-up trap:** *"Post-Merge, can't we use finality tags everywhere?"* — Mostly yes (~13 min lag), which is why serious bridges wait for finalized L1 headers before minting; anything faster is either intent-based with LPs bearing risk, or a bug.

### Q14 — Intent-based bridging vs canonical bridges: compare trust and UX.
**Testing:** current-generation interoperability literacy.
**Answer:** Canonical: user locks asset on A, protocol mints on B — trust in bridge validation, waits on challenge windows, exact asset received. Intents: user signs WHAT they want ("X USDC on B"), fillers compete to deliver instantly using their own inventory, getting repaid on A via the bridge later — UX instant, trust shifts to filler solvency + settlement honesty (Dutch auctions, Across/Unistark-class). Filler model caps user exposure to trade size, not TVL.
**Follow-up trap:** *"What if fillers collude?"* — Competition + settlement proofs bound extraction; systemic risk moves to solver-set health, which regulators will eventually treat like market makers. Name the endgame: intents + shared sequencers make cross-chain feel like one market with routing.

### Q15 — PeerDAS: explain the mechanics and why sampling preserves security as blobs scale.
**Testing:** 2025-26 protocol currency.
**Answer:** Each blob is erasure-coded into 128 column subsets; any 50% reconstructs 100%. Nodes custody a subset (scaled by validator count) and randomly SAMPLE others: k successful random samples imply (with overwhelming probability, ~1-in-10²⁰+ per parameters) that ≥50% of data exists, hence full reconstruction possible. Security scales because verification work stays constant per node while total data grows ~8× toward the 48-blob roadmap; BPO forks tune targets (6→10→14 by Jan 2026) against observed network health.
**Follow-up trap:** *"What's the actual failure mode?"* — Insufficient combined custodial coverage during correlated node churn (network-wide events); the p2p layer heals via reconstruction but sustained partition + churn could stall availability. Monitoring custody rates is now a protocol-health metric — a genuinely new operational surface Fusaka created.

## Red flags

- Describing rollups without mentioning data availability as the security anchor.
- Saying optimistic rollups are "trust-based" while ZK is "trustless" without noting sequencer/upgrade realities on BOTH.
- No answer for why the fraud window is seven days or who can challenge.
- Recommending multisig bridges for production cross-chain value.
- Confusing blob pruning with data loss (it's time-boxed availability, archives persist elsewhere).
- Claiming L2 fees fell "because of batching" instead of the blob fee market.
- Ignoring sequencer centralization entirely, or claiming it means funds are lost during downtime.

## Cheat card

```
WHY ROLLUPS    L1 capped by replication · rent L1 for DATA + SETTLEMENT
               execution moves off-chain, guarantees stay on-chain
OPTIMISTIC     assert roots · 7-day fraud window = max challenge time
               safety: 1-of-N honest watcher · BoLD (2/2025) permissionless
               dispute = bisection to ONE step re-executed on-chain
               exits: 7d trust-minimized OR LPs front instantly (~0.1-1%)
ZK             validity proof per batch · L1 verifies in ~100s of k gas
               0-of-N trust · finality minutes-hours · cost = provers
               zkEVM types: 1 eth-equiv -> 4 language-level (proving cost falls)
DA             blobs 128 KiB · pruned ~4096 epochs (~18 days) - archives elsewhere
               target/max 3/6 -> 6/9 (Pectra 5/2025) -> BPO1 10/15 -> BPO2 14/21
               PeerDAS (Fusaka 12/3/2025): erasure-code 128 cols + sampling ~8x headroom
VALIDIUM       DA off-chain via committee: cheap, freezing risk (availability not theft)
BRIDGES        2022: $2B+ stolen / 13 hacks (Chainalysis)
               Ronin $624M (5/9 keys phished, Lazarus) - committees are key mgmt
               Wormhole $325M (forged sig path) - sig bugs fatal where sigs = trust
               Nomad $190M (zero-proof init bug) - adversarial init vectors
               GOLD: light clients / ZK consensus proofs; CCTP burn-mint for USDC
STAGES         L2BEAT: 0 training wheels -> 1 council can intervene -> 2 no-trust
SEQUENCER      centralized ordering = MEV/censorship risk, NOT custody loss
               fixes: forced inclusion via L1, shared sequencers, based rollups
INTENTS        sign outcome; fillers compete, repaid via bridge later - instant UX
```

## Sources

- [Arbitrum BoLD permissionless validation launch — Offchain Labs, Feb 2025](https://arbitrum.io/blog); accessed 2026-08-23
- [OP Stack fault proofs go permissionless — Optimism docs, June 2024](https://docs.optimism.io/stack/protocol/fault-proofs); accessed 2026-08-23
- [Fusaka Mainnet Announcement (PeerDAS, BPO forks) — Ethereum Foundation](https://blog.ethereum.org/2025/11/06/fusaka-mainnet-announcement); accessed 2026-08-23
- [EIP-4844: Shard Blob Transactions](https://eips.ethereum.org/EIPS/eip-4844); accessed 2026-08-23
- [Different types of zkEVMs — Vitalik Buterin](https://vitalik.eth.limo/general/2022/08/04/zkevm.html); accessed 2026-08-23
- [L2BEAT — rollup stages and risk assessment framework](https://l2beat.com/scaling/summary); accessed 2026-08-23
- [Cross-Chain Bridge Hacks $2B — Chainalysis, August 2022](https://www.chainalysis.com/blog/cross-chain-bridge-hacks-2022/); accessed 2026-08-23
- [Ronin bridge hack post-mortem — Ronin/Sky Mavis, April 2022](https://roninblockchain.substack.com/p/community-alert-ronin-validators-compromised); accessed 2026-08-23
- [Nomad bridge exploit root cause analysis — rekt.news](https://rekt.news/nomad-rekt/); accessed 2026-08-23
- [PeerDAS specification EIP-7594](https://eips.ethereum.org/EIPS/eip-7594); accessed 2026-08-23

## Changelog

- 2026-08-23 — created




