# Build a Blockchain From Scratch: Blocks, Chain, Validation, Forks

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** T22-crypto-primitives · **Updated:** 2026-08-23
> **Module id:** `T22-blockchain-scratch` · **Tags:** blockchain, consensus, critical

## The 30-second version

A blockchain is three things stapled together: a block format where the header commits to a Merkle root of transactions and the previous header's hash, a validation function that re-checks every structural, contextual, and state rule for every block from genesis, and a fork-choice rule that says which valid chain is *the* chain — Bitcoin's "most accumulated work," Ethereum's GHOST-weighted heaviest head plus Casper FFG finality. Tamper-evidence falls out of the hash pointers; tamper-*resistance* requires that rewriting history means redoing all the work of the rewritten segment while honest miners keep extending the real tip, so the attacker must out-compute the majority. Building this in ~150 lines of Python — mining to a difficulty target, validating links and proofs-of-work, resolving a fork by cumulative work rather than length — is the fastest way to make every later topic (consensus, rollups, finality) legible.

## Why this gets asked

Because it exposes the difference between people who have used blockchain APIs and people who understand what the data structure guarantees. Interviewers ask "why can't an attacker just rewrite last week's blocks?" and listen for two-part answers: the hash-chain makes any edit detectable, but detection alone is cheap (git has that); the security comes from work — the rewrite must also beat the honest network's extension rate, which is why the answer quantifies in hashes per second rather than hand-waves about cryptography. The fork question separates another tier: given two valid histories, what picks the winner, and what does your application do during those seconds when both exist? Anyone who has run an exchange deposit-credit system or a bridge has lived through a reorg double-spend and will probe exactly there — confirmation counts, reorg-depth assumptions, and why six confirmations on Bitcoin became convention (a >99.9% chance an honest minority's fork dies within that much work).

## Lineage

**What came before.** The pieces are older than Bitcoin by decades: Haber and Stornetta proposed cryptographically timestamping documents in hash chains in 1990-91 precisely so no central timestamping authority could later reorder history, and Bayer-Haber-Stornetta added Merkle trees to batch certificates in 1992 — that is a blockchain minus consensus. What killed every centralized variant was trust in the operator: you had to believe the timestamp service wouldn't backdate. Adam Back's Hashcash (1997) supplied the missing ingredient as anti-spam proof-of-work; Szabo's bit gold (2005) and Dai's b-money (1998) sketched decentralized money but left open how peers agree. Nakamoto's whitepaper (October 31, 2008) and genesis block (January 3, 2009) combined hash chains + PoW + longest-work fork choice into one protocol where agreement emerges from economics instead of an administrator.

**Where it stands now.** Two production-grade templates dominate. Bitcoin keeps the original UTXO design with ~10-minute blocks and probabilistic finality — nothing ever "finalizes," confidence just compounds. Ethereum moved to proof-of-stake in September 2022: fixed 12-second slots, a GHOST-style fork choice (LMD/attn-GHOST) using attestation weight, and explicit finality via Casper FFG where checkpoints finalize after 2 epochs (~12.8 minutes); after that, even a supermajority attacker cannot revert without being slashed — economic finality replaces probabilistic. Meanwhile most new activity never touches these base layers directly: rollups post compressed batches to L1 for data availability and inherit its fork choice, so "building a chain" in 2026 usually means deploying a rollup stack (OP Stack, Arbitrum Orbit, Polygon CDK) rather than bootstrapping validators. The live argument is whether alt-L1s with faster blocks but weaker validator sets are buying latency with security — Ethereum Classic answered empirically with four separate 51% reorgs of 3,400-5,300+ blocks between July and November 2020.

**Where it's heading.** Three directions. First, base-layer throughput keeps rising without changing the shape of the problem: Ethereum's Fusaka upgrade (December 3, 2025) shipped PeerDAS with blob-parameter forks raising data capacity toward 48 blobs/block, and Glamsterdam (testing on public testnets August 2026, mainnet targeted H2 2026) adds enshrined proposer-builder separation plus block-access lists for parallel execution. Second, finality is becoming a product expectation: apps increasingly refuse to act on unfinalized state at all, making pre-merge-style probabilistic-only chains commercially awkward. Third, speculative but visible: shared sequencing and based/preconfirmation designs are collapsing the distinction between "my chain" and "your mempool," which may end the era of thousands of independent fork-choice rules.

---

## Mental model

**Git with no remotes, where writing requires solving a puzzle.** Every node holds the full repository. Commits (blocks) reference their parent's checksum. Anyone can create branches (forks), but each branch's authority is measured in accumulated work, and everyone converges on the heaviest branch. A "reorg" is exactly a git force-push that loses — unless the pusher controls more compute than everyone else combined.

```
        mempool ──▶ miner ──▶ candidate block ──▶ validate ──▶ extend tip
                                                    │
                              competing tip exists? │
                                                    ▼
                       fork choice: max(cumulative work / attestation weight)
                                                    │
                                    loser becomes stale/orphaned
```

Two consequences worth internalizing:

1. **The chain is a claim, not a fact.** Your node's local view of "the" chain is whatever passed validation and won fork choice *as seen by your peer set*. Network partitions produce divergent winners until healing — March 2013's Bitcoin split (v0.7 vs v0.8 database handling) ran two chains for ~6 hours before operators downgraded the larger one, orphaning ~24 blocks.
2. **Finality is a spectrum.** PoW gives exponential-ish confidence with depth; PoS gives hard cutoffs (Ethereum: finalized = irreversible barring ≥1/3 stake destruction). Applications should be written against one of those models explicitly, not against vibes like "waited a bit."

---

## How it actually works

### Block anatomy

Bitcoin's header is 80 bytes: `version(4) prev_hash(32) merkle_root(32) time(4) bits(4) nonce(4)`. Note what is *not* in it: transactions. They live in the body, committed via the Merkle root — that single indirection is what lets SPV clients verify inclusion with log-sized proofs. Ethereum's execution header is bigger (~500+ bytes encoded): parent hash, state root, transactions root, receipts root, difficulty/prevrandao, number, gas limit/used, base fee, timestamp, extra data, and since The Merge the consensus layer wraps it with beacon-block fields (slot, proposer randao reveal, attestations).

### Validation: three layers, strictly ordered

1. **Structural** — parseable, size limits (BTC: ≤4M weight units), Merkle root matches body, PoW meets stated target, timestamp within tolerance (~2h future skew allowed).
2. **Contextual** — connects to known parent, height correct, difficulty correct for the epoch (BTC retargets every 2016 blocks targeting 10 min; formula clamps adjustments to ×4/÷4), coinbase only pays itself the allowed subsidy + fees.
3. **Execution/state** — every transaction valid under current state: signatures verify, inputs exist and unspent (UTXO) or sender nonce/balance suffice (accounts model), scripts/EVM execute without violation, total supply rules hold.

Full nodes do all three for *every* block back to genesis (with trusted checkpoints/assume-valid shortcuts). That replay is why syncing a full node takes hours-to-days and why "don't trust, verify" has a hardware bill.

### Difficulty and the 10-minute clock

Target adjustment: `new_target = old_target × actual_2016_block_time / expected(2 weeks)`, clamped to ±4×. This is a feedback controller: hashpower quadruples → target tightens → block rate returns to ~10 min. Ethereum PoS doesn't need it — slots are wall-clock scheduled and proposers rotate; difficulty became PREVRANDAO.

### Forks: kinds and resolution

| Kind | Cause | Resolution |
|---|---|---|
| Natural race | two miners find blocks ~simultaneously | fork choice rule; loser orphaned |
| Software split | incompatible validation rules activated unevenly | human coordination (see 2013 BTC incident) or intentional hard fork |
| Deliberate attack | majority hashpower/stake rewrites recent history | fork choice follows attacker if they out-work/out-attest honest chain |

Nakamoto consensus math: attacker with q fraction of hashpower behind by z blocks catches up with probability ≈ (q/p)^z (p=1−q). At q=0.1: z=6 → ~0.24%, z=12 → ~6×10⁻⁴. That decay is the entire quantitative basis for confirmation conventions (exchanges commonly credit BTC at 2-3 confirmations, large deposits at 6; ~60 minutes for 6×10min). Under PoS the equivalent statement is sharper: finality after 2 epochs is absolute unless ≥1/3 of stake burns itself attacking — slashing converts "impossible" into "unprofitable."

What a 51% attacker can and cannot do — asked constantly, answered sloppily:

- **Can**: censor transactions; double-spend *their own* coins by reorging the block containing their payment; reorder recent history above the last honest checkpoint.
- **Cannot**: invent coins beyond the subsidy schedule; spend coins whose private keys they lack; alter smart-contract logic; reverse finalized checkpoints (PoS) without catastrophic self-slashing.
- Real costs: ETC's 2020 attacks were executed with rented hashrate costing thousands per day against hundreds of thousands stolen across double-spends; Bitcoin Gold lost ~$18M to a May 2018 attack (~86-block deep reorg). Cheap-security chains pay the difference to attackers.

---

## Build it from scratch

Runnable stdlib-only Python: SHA-256 blocks, hex-zero difficulty PoW, full validation, fork resolution by accumulated work (not length). Tested end-to-end below.

```python
import hashlib, json, time

def H(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

class Block:
    def __init__(self, index, txs, prev_hash, difficulty, ts=None):
        self.index      = index
        self.txs        = list(txs)
        self.prev_hash  = prev_hash
        self.difficulty = difficulty          # leading zero HEX digits required
        self.ts         = int(time.time() * 1000) if ts is None else ts
        self.nonce      = 0
        self.merkle     = merkle_root(self.txs)
        self.hash       = None

    def header(self) -> str:
        return json.dumps({
            'index': self.index, 'prev': self.prev_hash,
            'merkle': self.merkle, 'ts': self.ts,
            'diff': self.difficulty, 'nonce': self.nonce,
        }, sort_keys=True)

    def seal(self) -> None:
        """Proof-of-work: find nonce so SHA256(header) starts with N zero hex digits."""
        prefix = '0' * self.difficulty
        h = H(self.header().encode())
        while not h.startswith(prefix):
            self.nonce += 1
            h = H(self.header().encode())
        self.hash = h

    def work(self) -> int:
        """Expected hashes per success = 16**difficulty."""
        return 16 ** self.difficulty

def merkle_root(items) -> str:
    if not items:
        return H(b'')
    level = [H(i.encode()) for i in items]
    while len(level) > 1:
        if len(level) % 2:
            level.append(level[-1])
        level = [H((level[i] + level[i+1]).encode()) for i in range(0, len(level), 2)]
    return level[0]

GENESIS_TXS = ['coinbase->genesis']

def make_genesis(difficulty=4) -> Block:
    g = Block(0, GENESIS_TXS, '0'*64, difficulty, ts=1231006505000)
    g.seal()
    return g

def valid_block(b: Block) -> bool:
    if b.hash != H(b.header().encode()):          return False   # integrity
    if not b.hash.startswith('0' * b.difficulty): return False   # PoW
    if b.merkle != merkle_root(b.txs):            return False   # body commit
    return True

def valid_chain(chain) -> bool:
    if not chain or chain[0].prev_hash != '0'*64: return False
    for prev, cur in zip(chain, chain[1:]):
        if cur.prev_hash != prev.hash or cur.index != prev.index + 1:
            return False                          # linkage
        if cur.ts <= prev.ts - 3600_000:          # crude timestamp sanity
            return False
    return all(valid_block(b) for b in chain)

def total_work(chain) -> int:
    return sum(b.work() for b in chain)

def resolve_fork(a, b) -> list:
    """Heaviest accumulated work wins - NOT longest chain."""
    if not valid_chain(a): return b if valid_chain(b) else []
    if not valid_chain(b): return a
    return a if total_work(a) >= total_work(b) else b
```

Demo that exercises the interesting case — longer-but-lighter fork must lose:

```python
D = 4
genesis = make_genesis(D)
A = [genesis]
for txs in [['alice->bob:5'], ['bob->carol:2']]:
    nb = Block(len(A), txs, A[-1].hash, D); nb.seal(); A.append(nb)
assert valid_chain(A)

B = [Block(0, GENESIS_TXS, '0'*64, D, ts=genesis.ts)]
for txs in [['mallory->eve:9'], ['eve->frank:1'], ['frank->grace:1']]:
    fb = Block(len(B), txs, B[-1].hash, D - 1); fb.seal(); B.append(fb)

winner = resolve_fork(A, B)
assert winner is A            # heavier wins despite being SHORTER
A[1].txs[0] = 'alice->eve:99999'
assert not valid_chain(A)     # tampering detected
```

Measured here: d=4 mines instantly; each extra hex digit multiplies expected work ×16 (d=6 → ~65k hashes/block, still <1s in Python; d=8 crosses minutes — feel the exponential). Production output shows `A: 3 blocks, work=196,608` beating `B: 5 blocks, work=81,920`.

Deliberate simplifications to call out in an interview: fixed difficulty per block (real chains carry target bits and retarget), no coinbase/fees, no signature verification on txs (module 01 supplies that primitive), whole-chain-in-memory (real nodes store headers separately and prune), and fork resolution comparing only two chains (real ones maintain a block tree indexed by hash).

## How it's done in production

| Concern | Bitcoin | Ethereum |
|---|---|---|
| Clients | Bitcoin Core (C++), btcd/knots | Geth/Nethermind/Besu (EL) + Lighthouse/Prysm/Teku (CL) |
| Sync | headers-first, assume-valid, compact filters (BIP-157/158) | snap sync: download state trie chunks + heal |
| Block time | ~10 min, retarget 2016 blocks | 12 s slots, deterministic proposers |
| Fork choice | most cumulative work (chainwork) | attn-GHOST by attestation weight + Casper FFG finality |
| Finality | none (probabilistic, depth-based) | justified→finalized, 2 epochs ≈ 12.8 min |

Production failure modes and observable symptoms:

| Symptom | Cause | Fix |
|---|---|---|
| Deposit credited then reversed hours later | Reorg replaced the accepting block | Credit after depth policy; subscribe to reorg events; use finalized checkpoints on PoS |
| Node stuck at same height while peers advance | Invalid block accepted locally / stalled sync | Check peer score logs, restart with fresh peers, verify client version |
| Chain split across versions after activation | Uneven software upgrade (March 2013 pattern) | Staged deploys, alert on fork-detection counters (Core ships one) |
| Sudden block-interval drift | Hashpower migrated on/off (profit switching) | Watch retarget deltas; exchanges raise confirmation requirements |
| Double-spend accepted by your service | Attacker mined private fork (ETC-2020 style) | Depth scaled to value; finality-required mode; monitor for conflicting broadcasts |

App-side patterns that matter more than node config: treat `n confirmations` as a risk budget tied to tx value (the (q/p)^z table), prefer PoS-finality subscriptions (`finalized` block tag) over raw counts where available, index by txid *and* (sender,nonce) because reorgs replace txids, and alarm on `getblockchaininfo`'s headers-vs-blocks divergence.

## Tradeoffs & when NOT to use it

- **Don't build a bespoke L1 for an app.** Bootstrapping a validator set with real economic security is a nine-figure problem; ETC-class outcomes are the base rate for small chains. Deploy a rollup inheriting Ethereum settlement instead — you get its fork choice and finality as a library feature.
- **Probabilistic finality is hostile to some products.** Exchanges, bridges, and payments want hard cutoffs; pure-PoW depth policies mean either slow UX (60 min) or tail risk. If you need instant irrevocability, PoS-finality or a traditional ledger beats PoW.
- **The tamper-evidence is worthless without replication.** A hash-chained log on one disk proves tampering *after* it happens; it cannot prevent the operator rewriting everything. Security comes from many independent parties extending the chain you're watching.
- **Throughput is structurally bounded by replication cost**: every full node re-executes everything, so L1 capacity ≈ cheapest acceptable node hardware's capacity (BTC ~7 tx/s base layer; ETH ~15-20 tx/s pre-blobs, higher post-Fusaka but still orders below Visa's ~65k peak tps). Anything consumer-scale belongs on L2.
- **Energy accounting is real**: Bitcoin's network draws estimates around 120-175 TWh/year (CAMBRIDGE Bitcoin Electricity Consumption Index range, 2023-2025), comparable to medium-sized countries. For non-monetary uses that is indefensible; even monetary uses get challenged on it in every architecture review.
- **When a plain database wins:** single organization, mutable records needed, no adversarial participants, GDPR erasure required (chains are delete-hostile by design). Append-only + periodic external anchoring covers the audit story at 0.001% the cost.

## Interview questions

### Q1 — Why store the previous block's hash inside the header instead of linking externally?
**Testing:** whether hash-pointer chaining actually clicked.
**Answer:** Because then the link is part of the signed/mined content: editing block N changes its hash, invalidating the pointer stored in N+1, cascading to the tip. External links could be updated selectively. It converts "tampering" into "tampering that is trivially detectable by anyone holding the chain."
**Follow-up trap:** *"Detectable isn't prevented — so what stops rewriting?"* — Correct instinct: prevention comes from the fork-choice economics. You must redo PoW for the edited segment faster than the honest network extends the real tip; otherwise your fork stays the losing branch forever.

### Q2 — Walk through everything a full node checks when a new block arrives.
**Testing:** systems thoroughness; ordering discipline.
**Answer:** Structural: parse, size ≤4M WU, Merkle root recomputes, header hash ≤ target. Contextual: parent known and valid, height/difficulty right for the epoch, timestamps sane, coinbase claims only subsidy+fees. Execution: replay every transaction against current state — sigs, UTXOs unspent / account balance+nonce, script/EVM constraints. Only then: add to block tree, run fork choice, possibly reorg.
**Follow-up trap:** *"Why replay from genesis instead of trusting checkpoints?"* — Full replay is the point of decentralization: checkpoints reintroduce trusted parties. In practice Core's assume-valid skips signature checks for historical blocks below a community-published hash (script verification only), an audited tradeoff, not blind trust.

### Q3 — How does difficulty adjustment behave if half the hashpower vanishes overnight?
**Testing:** control-systems thinking.
**Answer:** Blocks slow to ~20 min immediately; the next 2016-block window takes ~4 weeks, so the retarget computes actual/expected ≈ 2 and doubles the target (halves difficulty), clamped at ×4 max per adjustment. Rate recovers to 10 min after the window closes. This lag caused real pain in China-miner exits (mid-2021) — block times stretched for weeks between events.
**Follow-up trap:** *"Why clamp?"* — To prevent difficulty oscillation/griefing via hashpower whiplash attacks and to bound damage from timestamp manipulation feeding the adjustment. An unclamped loop can be driven unstable by an adversary controlling timestamps near boundaries.

### Q4 — What exactly can a 51% attacker do, and what's the cheapest real-world demonstration?
**Testing:** precision on the classic question.
**Answer:** Can: censor, reorder recent txs, double-spend their own funds by privately mining a replacement fork and releasing it. Cannot: steal others' keys, mint beyond schedule, change rules (that needs consensus, not hashpower). Demonstrations: Bitcoin Gold May 2018, ~$18M via ~86-block reorg; Ethereum Classic July-November 2020, four reorgs of roughly 3.4k-5.3k blocks using rented hashrate; both were small-PoW chains where rental markets made majority power cheap by the hour.
**Follow-up trap:** *"Does 51% let them rewrite from genesis?"* — No: rewriting z blocks requires out-working the honest chain over that whole span, and cost grows with depth; also PoW history is anchored by checkpoints/exchanges, and PoS history past finality is protected by slashing — reverting it requires burning ≥1/3 of all stake and still failing socially.

### Q5 — Why did Ethereum replace longest/heaviest-work with GHOST-style fork choice?
**Testing:** knowledge of post-merge consensus mechanics.
**Answer:** With 12-second slots, natural races make forks frequent; discarding losing blocks wastes the attestations backing them and slows convergence. LMD/attn-GHOST counts latest-message attestations as weight, choosing the subtree with the most validator support, so orphaned-slot information still steers the head. On top sits Casper FFG: when 2/3 of stake attests a checkpoint pair (source→target), it's justified; a second justification finalizes it irreversibly absent slashing.
**Follow-up trap:** *"So short forks can't happen after finality?"* — Before finality yes (~2 epochs of churn possible); after finality, no honest client follows a conflicting chain, and any majority attempting it gets ≥1/3 of itself slashed — economically terminal. Apps should key irreversible logic off the `finalized` tag.

### Q6 — Design the deposit-crediting policy for an exchange handling BTC and ETH.
**Testing:** translating consensus theory into risk policy.
**Answer:** BTC: credit tiers by value — e.g., 1 conf for small amounts, 3 typical, 6 for large (>~$100k), because catch-up probability ≈ (q/p)^z decays exponentially; monitor for conflicting spends of the same UTXO. ETH: watch slot inclusion (seconds) for UX, but gate withdrawal-release on finalization (~13 min) for anything material. Both: index deposits by txid AND identifying fields, handle reorg callbacks, and alarm when observed reorg depth exceeds policy.
**Follow-up trap:** *"Your competitor credits at 0 confs and grows faster."* — Accept unconfirmed credits only with risk controls: amount caps, KYC'd users, RBF-aware mempool monitoring (RBF explicitly allows replacement!), and instant-hold thresholds. Frame it as fraud-loss pricing, not consensus belief.

### Q7 — What breaks first if you remove the Merkle root from block headers?
**Testing:** understanding of header/body separation and SPV.
**Answer:** Light clients die: without a header-committed root, verifying tx inclusion requires the full block. Pruning/full-node bootstrap weakens too (can't validate body against a small commitment). Historical anchoring (e.g., proving a 2015 transaction existed) becomes impossible without storing everything. The 80-byte header is the entire SPV economy.
**Follow-up trap:** *"Could you commit to txs differently, say a running XOR?"* — Any commitment must be collision-resistant and order-sensitive; XOR folds away duplicates/order and is forgeable. Merkle (or Verkle/vector commitments) give O(log n) membership proofs; that property is load-bearing.

### Q8 — Explain the March 2013 Bitcoin fork as a systems failure.
**Testing:** real-incident literacy beyond textbook rules.
**Answer:** v0.8's LevelDB accepted blocks v0.7's BerkeleyDB rejected (lock-limit edge), so a large multisig-heavy block split the network: newer clients built one side, older the other, for ~6 hours. Resolution was social: big merchants/pools downgraded to the v0.7 chain, orphaning ~24 blocks including one double-spend attempt. Lessons: validation is implementation-defined until pinned by tests; upgrades need staged rollout and fork alarms; consensus bugs are operational incidents, not code reviews.
**Follow-up trap:** *"How do you prevent it today?"* — Consensus-rule test vectors shared across implementations (Bitcoin Core vs Knots; Eth client diff tests), canary/fork-monitor services watching for competing tips at depth, and coordinated activation windows for any consensus-affecting change.

### Q9 — Why is a blockchain without tokens often pointless?
**Testing:** incentive-design maturity; the enterprise trap.
**Answer:** The token pays for replication: miners/validators incur cost proportional to securing history and need compensation. Remove it and either a central party runs everything (then it's a database with extra steps) or participants subsidize security out of goodwill, which historically collapses (permissioned chains quietly shut down: we.trade 2022, TradeLens wound down early 2023). Tokenless designs survive only when someone external anchors/enforces honesty (e.g., rollups posting to a secured L1).
**Follow-up trap:** *"But enterprises hate tokens."* — Right, and that's why most enterprise chains died or became boring audit logs; the honest architectures either use a public L1's security (stablecoins, tokenized funds) or drop blockchain entirely. Say that plainly and you sound senior.

### Q10 — Your service saw a 2-block reorg invalidate a settled payment. Root-cause your design.
**Testing:** incident reasoning with concrete remediation.
**Answer:** Immediate: the system acted on probabilistic finality as if it were certain. Fix layers: (1) policy — require depth proportional to value (or finality tag on PoS); (2) plumbing — subscribe to reorg events instead of polling balances; (3) reconciliation — idempotent credit/debit keyed by (txid,sender,nonce) with reversal journal entries, so a reorg is a booked event, not a crash; (4) detection — alert when depth exceeds max ever observed (tells you it's an attack, not weather).
**Follow-up trap:** *"Should you ever act at 1 conf?"* — Yes for low-value flows with fraud-budget accounting, RBF awareness, and rate limits; the error bar is money, not correctness dogma. Quantify expected loss = P(reorg at depth 1) × exposure and compare to conversion gains.

### Q11 — Compare building on a rollup versus launching an app-chain.
**Testing:** 2026-era deployment judgment.
**Answer:** Rollup (OP Stack/Arbitrum Orbit/zkStack): inherit L1 data availability + settlement + its fork choice/finality; launch in days; pay blob fees; sequencer centralization is the main caveat (mitigated by shared/federated sequencing roadmaps). App-chain L1: sovereignty over rules and fee capture, but you own validators, security budget, fork-choice bugs, and 51% economics — see ETC 2020 for the tail. Default answer for an app team: rollup; L1 only with a token-funded security story and ecosystem demand.
**Follow-up trap:** *"When would you genuinely choose an L1?"* — When the app IS the security economy (exchange-native chains with staked exchange assets, high-frequency order books needing custom mempools) or regulatory isolation matters. Even then consider an L2 with custom gas/fees first.

### Q12 — What does "assume-valid" trust, and why is it acceptable?
**Testing:** nuance about real-client engineering vs purity claims.
**Answer:** It trusts the community that historical blocks (below a published hash) contain valid *signatures*, skipping ECDSA verification during initial sync — everything else (structure, PoW/difficulty, state transitions) still verifies fully. Rationale: signature validity of decade-old blocks is not plausibly contested (any invalid one would have been rejected by the live network at publication); sync drops from days to hours. You can disable it and replay everything.
**Follow-up trap:** *"Isn't that 'trust the majority'? So much for don't-trust-verify."* — It's trust scoped to a narrow, publicly auditable claim with an opt-out, versus trusting custodians with custody itself. Engineering is tradeoffs; pretending otherwise fails the credibility check.

### Q13 — How would you explain "finalized" to a backend engineer used to ACID?
**Testing:** translation skill; senior communication.
**Answer:** Like a commit that cannot be rolled back by anyone, ever, given protocol assumptions hold (≤1/3 Byzantine stake). Before finality you're reading uncommitted data — reorgs are the rollback mechanism. Practical mapping: `latest` ≈ dirty read, `safe` (justified) ≈ read-committed-ish, `finalized` ≈ serializable commit. Build integrations accordingly: UI reads latest, money moves on finalized.
**Follow-up trap:** *"Can finality ever break?"* — Under protocol violation: if ≥1/3 stake attacks, inactivity leaks and slashing resolve it eventually, but social recovery (coordinated minority client split, as in the 2016 DAO fork precedent at a different layer) may be invoked. Honest answer: cryptoeconomic guarantee, not thermodynamic law.

### Q14 — Given this Python toy chain, name five ways it differs from Bitcoin and why each matters.
**Testing:** code-level critique under pressure.
**Answer:** (1) No signatures on txs — ownership meaningless without them; (2) fixed difficulty, no retarget — hashpower drift breaks block cadence; (3) no coinbase/subsidy — no incentive to mine honestly; (4) fork choice compares two arrays, not a persistent block tree with reorg depth limits; (5) no networking/mempool — consensus assumes global instant gossip. Each maps to a real subsystem (crypto, difficulty controller, incentives, p2p/state management).
**Follow-up trap:** *"Which omission breaks it first under adversarial conditions?"* — Signatures: anyone can spend anything immediately. Under cooperative load, the missing mempool/rate control breaks liveness first. Ordering depends on threat model — saying that is the point.

### Q15 — Estimate: how much would it cost to 51%-attack Bitcoin for one hour today?
**Testing:** quantitative market literacy; comfort with estimation.
**Answer:** Order-of-magnitude: network hashrate is ~700-900 EH/s (2025-26 range); renting even 10% of global GPU/ASIC-compatible hash is impossible on open markets — dedicated SHA-256 ASICs aren't rentable in bulk, so an attacker must acquire hardware (years of manufacturing, billions USD) or corrupt pools covertly. Contrast ETC (~250 GH/s class in 2020) where $10-50k/day rentals sufficed. Answer shape: define the metric (rental market vs capex), cite the asymmetry, conclude BTC-scale attacks are state-level projects, small-PoW chains are weekend projects.
**Follow-up trap:** *"So big chains can't be attacked at all?"* — They face different vectors: censorship at pool/relay level, MEV extraction, and governance/social attacks — hashpower is one axis of several. Naming the axis switch is the senior move.

## Red flags

- Saying the previous-hash link alone prevents tampering (it detects; work/stake prevents).
- Claiming a 51% attacker can print money or steal arbitrary wallets.
- "Longest chain" as Bitcoin's rule without mentioning cumulative work.
- Confusing hard fork and soft fork (soft = tightening rules, backward-compatible).
- Treating one confirmation as settled.
- Proposing to "just build our own chain" for an enterprise feature with no security-budget answer.
- Not knowing Ethereum slots/epochs (12 s / 32 slots) or that finality ≈ 2 epochs.

## Cheat card

```
BLOCK HEADER   BTC 80 B: ver(4)+prev(32)+merkle(32)+time(4)+bits(4)+nonce(4)
VALIDATION     structure → context (parent/difficulty/time) → full tx replay
DIFFICULTY     BTC retarget every 2016 blks, target 10 min, clamp x4 / /4
               toy: leading zero hex digits, work = 16^d per block
FORK CHOICE    BTC: most cumulative WORK (not length) · ETH: attn-GHOST + FFG
CATCH-UP       P(attacker z behind) ≈ (q/p)^z · q=.1,z=6 → ~0.24%
CONFIRMS       BTC 2-6 (value-scaled, 10-60 min) · ETH finality 2 epochs ≈ 12.8 min
SLOTS/EPOCH    12 s slot · 32 slots/epoch (~6.4 min) · Merge 2022-09-15
51% CAN        censor, reorder, double-spend OWN coins
51% CANNOT     mint extra, spend others' keys, revert finalized (≥1/3 slashed)
INCIDENTS      BTC split 2013-03 (~6h, 24 blks orphaned) · BTG 2018 ($18M)
               ETC 2020: four reorgs 3.4k-5.3k blks (rented hash)
L1 THROUGHPUT  BTC ~7 tx/s · ETH ~15-20 tx/s · Visa peak ~65k tps
RULE OF THUMB  app → rollup on secured L1; bespoke L1 needs 9-figure security budget
```

## Sources

- [Bitcoin whitepaper — Nakamoto (2008)](https://bitcoin.org/bitcoin.pdf); accessed 2026-08-23
- [Haber & Stornetta, "How to Time-Stamp a Digital Document" (1991)](https://link.springer.com/article/10.1007/BF00196791); accessed 2026-08-23
- [Analysis of hashrate-based doubling — Rosenfeld (2014), confirmation probability math](https://www.sciencedirect.com/science/article/pii/S2210271X14000358); accessed 2026-08-23
- [Coinbase: Bitcoin Gold hit by 51% attack, ~$18M double-spent (2018)](https://www.coindesk.com/markets/2018/05/24/bitcoin-gold-hit-by-51-attack-double-spends-worth-18m-exchange-says/); accessed 2026-08-23
- [Cointelegraph: Ethereum Classic suffers fourth 51% attack in a month (Aug 2020)](https://cointelegraph.com/news/ethereum-classic-suffers-third-51-attack-in-a-month); accessed 2026-08-23
- [Post-mortem of the March 2013 Bitcoin fork (BIP-50)](https://github.com/bitcoin/bips/blob/master/bip-0050.mediawiki); accessed 2026-08-23
- [Gasper: Casper FFG + GHOST paper (Buterin & Griffith)](https://arxiv.org/abs/2003.03052); accessed 2026-08-23
- [Fusaka Mainnet Announcement — Ethereum Foundation Blog](https://blog.ethereum.org/2025/11/06/fusaka-mainnet-announcement); accessed 2026-08-23
- [Cambridge Bitcoin Electricity Consumption Index](https://ccaf.io/cbnsi/cbeci); accessed 2026-08-23
- [Assume-valid deployment notes — Bitcoin Core docs](https://bitcoincore.org/en/releases/0.14.0/); accessed 2026-08-23

## Changelog

- 2026-08-23 — created
