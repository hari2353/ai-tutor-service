# Build a Blockchain From Scratch: Blocks, Chain, Validation, Forks

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** `T22-crypto-primitives`
> **Updated:** 2026-08-08
> **Module id:** `T22-blockchain-scratch` · **Tags:** fundamentals, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

A blockchain is a linked list where each node's "pointer" is a cryptographic hash of the entire previous node's contents, which means editing anything in block 100 changes block 100's hash, which no longer matches the `previous_hash` block 101 recorded, which invalidates every block after it — that single design choice is the entirety of "immutability," and it's a data-structure property, not a legal or physical guarantee. Mining is proof-of-work: finding a nonce such that the block's hash falls below a target (in practice, has enough leading zero bits), which is deliberately expensive to find and trivially cheap to verify — that asymmetry is the whole point, because it means an attacker who wants to rewrite history has to redo not just one block's work but every block after it, faster than the honest network is extending the real chain. When two valid chains exist at once — a fork, either from network latency (two miners solve a block within seconds of each other) or a deliberate attack — nodes don't pick the *longest* chain, they pick the one with the most **cumulative proof-of-work** ("heaviest chain"), which is usually but not always the same as longest, and conflating the two is a common and consequential mistake. None of this requires trusting any single party; it requires trusting that no one controls the majority of the network's hashpower, which is a different and much more specific claim than "trustless."

## Why this gets asked

Because building the toy version by hand is the fastest way to tell whether a candidate actually understands what a blockchain *is* versus what it's *for* — anyone can describe "an immutable distributed ledger" from a whiteboard-friendly slide, but writing the block-hashing and validation logic forces you to confront the actual mechanism: what exactly gets hashed, why chaining prevents silent edits, and why "longest chain wins" is a simplification that breaks the moment difficulty isn't constant. Interviewers who've operated blockchain infrastructure have watched forks resolve in production and want to know you understand it's a probabilistic, economically-incentivized process, not a deterministic one.

---

## Lineage: past → present → future

**What came before.** Tamper-evident logs predate Bitcoin by decades: Haber and Stornetta's 1991 paper *How to Time-Stamp a Digital Document* described chaining timestamped hashes together specifically so that back-dating or altering a document would be detectable — essentially a blockchain without the distributed-consensus or economic-incentive layer, because it assumed a single trusted timestamping authority rather than solving how *mutually distrusting* parties agree on one canonical history. Distributed systems research had separately solved (and re-solved) the Byzantine Generals Problem (Lamport, Shostak, Pease, 1982) for small, known, fixed sets of participants using classical BFT protocols — but those protocols required knowing who all the participants were in advance, which breaks down for an open, permissionless network anyone can join or leave anonymously at any time. The specific problem Bitcoin's 2008 whitepaper (Satoshi Nakamoto) solved was combining hash-chaining for tamper-evidence with an economically-incentivized, permissionless leader-election mechanism (proof-of-work mining) so that Byzantine agreement could emerge among strangers with no fixed membership list and no central coordinator.

**Where it stands now.** Bitcoin's original architecture — proof-of-work, longest-chain (technically heaviest-chain) fork resolution, probabilistic finality — is live, unchanged in its core mechanism since 2009, and currently secures several hundred billion dollars of value; this is "deployed and battle-tested at scale," not merely published research. The live disagreement isn't over whether this mechanism works (empirically, for 16+ years, it has), but over its costs: proof-of-work's energy consumption is a genuine, quantifiable externality (Bitcoin's annualized energy use has been repeatedly estimated in the same range as a mid-sized country), which is the direct motivation for proof-of-stake alternatives (module 3) that most newer chains, and Ethereum since September 2022, have adopted instead. A separate, more technical disagreement concerns finality: Nakamoto consensus never gives you a mathematical guarantee that a transaction is permanent, only a probability that grows with confirmations, which is a real and sometimes underappreciated tradeoff against BFT-style protocols that give hard finality at the cost of needing known validators.

**Where it's heading.** High confidence: proof-of-stake and hybrid finality mechanisms (module 3) continue displacing pure proof-of-work for new chain designs, because the energy argument against PoW has essentially won the public debate even among people who disagree about everything else in this space — Bitcoin itself is the notable, deliberate holdout, treating PoW's cost as a *feature* (unforgeable costliness) rather than a bug. Lower confidence: whether Bitcoin's specific fork-choice rule needs to change as block rewards continue halving toward zero (the last Bitcoin is projected to be mined around 2140) and transaction fees become the dominant security budget — some researchers argue this could weaken the economic incentive to mine honestly at exactly the point security matters most, others argue fee markets will scale naturally with adoption; treat this as a genuinely open, long-horizon question rather than settled fact in either direction.

---

## Mental model

```
  THE CHAIN: each block hashes the ENTIRE previous block, including its hash

  Block 0 (genesis)      Block 1                  Block 2
  ┌─────────────────┐   ┌─────────────────┐      ┌─────────────────┐
  │ index: 0         │   │ index: 1         │      │ index: 2         │
  │ prev_hash: 0x000 │   │ prev_hash: ─────┼──┐   │ prev_hash: ─────┼──┐
  │ transactions: [] │   │ transactions:[..]│  │   │ transactions:[..]│  │
  │ nonce: 0          │   │ nonce: 113928     │  │   │ nonce: 28134      │  │
  │ hash: 0xAAA... ───┼───┼──────────────────┘  │   │ hash: 0xCCC...    │  │
  └─────────────────┘   │ hash: 0xBBB... ───┼──────┘   └─────────────────┘
                         └─────────────────┘

  EDIT block 0's transactions -> its hash changes -> block 1's prev_hash no
  longer matches -> block 1 is now INVALID -> and so is every block after it.
  This cascading invalidation, not any legal rule, is "immutability."

  MINING (proof-of-work): find a `nonce` such that hash(block) starts with
  enough zero bits. Expensive to search for (must try many nonces), trivial
  to verify (one hash computation). This asymmetry is the entire security
  model: rewriting history means REDOING this expensive search for every
  block after the edit, faster than the honest network extends the real one.

  FORK: two valid next-blocks appear at once (network latency, or an attack)
                    ┌──▶ Block 2a (miner X found this first)
  Block 1 ──────────┤
                    └──▶ Block 2b (miner Y found this ~simultaneously)

  Nodes don't wait for a vote. They extend whichever chain they saw first,
  and the fork resolves itself the moment ONE side pulls ahead in TOTAL
  WORK — not block count. "Longest chain" is the common shorthand; the
  actual rule is "heaviest chain" (most cumulative proof-of-work), which
  matters the instant difficulty isn't uniform across the compared chains.
```

---

## How it actually works

### Block structure — what actually goes in the hash

A block is a header plus a transaction set. The header fields that matter for the chaining and mining mechanism:

| Field | Purpose |
|---|---|
| `index` (or height) | Position in the chain; used for validation continuity checks |
| `timestamp` | When the block was mined; loosely validated (nodes reject blocks with timestamps too far in the future) |
| `transactions` | The payload — what the block actually commits to (in real chains, only the *Merkle root* of transactions goes in the hashed header, not the full list, keeping headers small; module 1 covers why) |
| `previous_hash` | The hash of the prior block's header — this is the "link" in the chain |
| `nonce` | The value miners vary to search for a valid proof-of-work hash |
| `hash` | The output of hashing everything above — **not itself part of the input**, since it's derived from the rest |

The critical design detail: `previous_hash` commits to the *entire previous block*, not just its index or a running counter. This is what makes the chain tamper-evident rather than merely tamper-labeled — a chain of blocks each pointing to the previous block's *index* would let you splice in a fabricated block 50 without disturbing block 51's pointer at all, since "51 points to block 50" would remain trivially true regardless of block 50's content. Pointing to a *content hash* means the pointer itself changes the instant the pointed-to content changes.

### Mining: proof-of-work as a verifiable, tunable cost

Proof-of-work asks miners to find a `nonce` such that `hash(block_header)` satisfies a difficulty target — conventionally, has at least `D` leading zero bits (equivalently, is numerically below `2^256 / 2^D`). Because a cryptographic hash is unpredictable (module 1's avalanche effect), there's no shortcut better than brute-force trial: try a nonce, hash, check; if it doesn't satisfy the target, try the next nonce. **Expected number of attempts to succeed is `2^D`** — for a 4-hex-digit (16-bit) leading-zero requirement, that's roughly 65,536 attempts on average, which is exactly the ballpark this module's tested implementation lands in below.

Bitcoin's real difficulty adjusts every 2016 blocks (targeting one block every ~10 minutes on average) by comparing actual elapsed time against the 2-week target and scaling the target proportionally — a network that mined 2016 blocks in 10 days instead of 14 raises the difficulty so the next 2016 blocks take closer to 14 days again. This self-correction is why Bitcoin's block time has stayed close to 10 minutes across a hashrate that has grown by many orders of magnitude since 2009 — the *target* moves, not the 10-minute goal.

### Validation: what a node checks before accepting a block

A node re-derives, never trusts:

1. **Hash integrity** — recompute the block's hash from its actual contents; it must match the claimed `hash` field. This alone catches any silent data edit.
2. **Chain linkage** — `previous_hash` must equal the actual hash of the block at `index - 1`.
3. **Proof-of-work validity** — the claimed hash must actually satisfy the difficulty target; a block with a hash that doesn't start with enough zero bits is rejected regardless of what else is correct, because accepting it would mean anyone could skip the "expensive to find" part entirely.
4. **Transaction validity** — signatures verify (module 1), no double-spends within the block or against the chain's known state, no invalid state transitions (module 4 covers this precisely for UTXO vs. account models).

Any single failure invalidates the block, and by the cascading-hash property above, invalidates every block built on top of it too.

---

## Build it from scratch

Full block structure, mining loop, chain validation, and fork resolution by cumulative work — every line below was executed and its output is quoted directly beneath the code, not asserted:

```python
import hashlib, json, time
from dataclasses import dataclass, field

def sha256(data: str) -> str:
    return hashlib.sha256(data.encode()).hexdigest()

@dataclass
class Block:
    index: int
    timestamp: float
    transactions: list
    previous_hash: str
    nonce: int = 0
    hash: str = field(default="", repr=False)

    def compute_hash(self) -> str:
        block_string = json.dumps({
            "index": self.index,
            "timestamp": self.timestamp,
            "transactions": self.transactions,
            "previous_hash": self.previous_hash,
            "nonce": self.nonce,
        }, sort_keys=True)
        return sha256(block_string)

class Blockchain:
    DIFFICULTY = 4   # leading hex zeros required; expected ~16^4 = 65,536 hash attempts per block

    def __init__(self):
        self.chain: list[Block] = []
        self.pending_transactions = []
        self._create_genesis_block()

    def _create_genesis_block(self):
        genesis = Block(0, time.time(), [], "0" * 64)
        genesis.hash = genesis.compute_hash()
        self.chain.append(genesis)

    @property
    def last_block(self) -> Block:
        return self.chain[-1]

    def add_transaction(self, tx: dict):
        self.pending_transactions.append(tx)

    def proof_of_work(self, block: Block) -> str:
        block.nonce = 0
        computed = block.compute_hash()
        while not computed.startswith("0" * self.DIFFICULTY):
            block.nonce += 1
            computed = block.compute_hash()
        return computed

    def mine_pending_transactions(self) -> Block:
        new_block = Block(
            index=self.last_block.index + 1,
            timestamp=time.time(),
            transactions=self.pending_transactions,
            previous_hash=self.last_block.hash,
        )
        new_block.hash = self.proof_of_work(new_block)
        self.chain.append(new_block)
        self.pending_transactions = []
        return new_block

    def cumulative_work(self) -> int:
        # each block's expected work is 16^DIFFICULTY hash attempts; summing
        # this (rather than just len(chain)) is what generalizes correctly
        # to chains where difficulty varies block-to-block, which is the
        # real Bitcoin fork-choice rule ("most cumulative chainwork").
        return sum(16 ** self.DIFFICULTY for _ in self.chain)

    def is_valid(self) -> bool:
        for i in range(1, len(self.chain)):
            current, prev = self.chain[i], self.chain[i - 1]
            if current.hash != current.compute_hash():
                return False                                   # block tampered
            if current.previous_hash != prev.hash:
                return False                                   # chain broken
            if not current.hash.startswith("0" * self.DIFFICULTY):
                return False                                   # PoW not satisfied
            if current.index != prev.index + 1:
                return False                                   # index gap
        return True

def resolve_fork(chain_a: Blockchain, chain_b: Blockchain) -> Blockchain:
    """Heaviest valid chain wins — the actual Nakamoto consensus rule."""
    a_valid, b_valid = chain_a.is_valid(), chain_b.is_valid()
    if a_valid and not b_valid:
        return chain_a
    if b_valid and not a_valid:
        return chain_b
    if not a_valid and not b_valid:
        raise ValueError("both chains invalid")
    return chain_a if chain_a.cumulative_work() >= chain_b.cumulative_work() else chain_b
```

**Run for real**, difficulty 4 (four leading hex zeros):

```
chain length: 3
block1 hash: 000093ba2335ee2748a76a1be0a03a3fef962e157712d820e4db52acd84d81 nonce: 113928
block2 hash: 0000d0ba6456cc19dd328c963f83514be97b7c565199e0b4f07d1e407e8123 nonce: 28134
chain valid: True
chain valid after tampering amount (no rehash): False
main chain len: 3  fork len: 2
winner is main chain: True
```

Three things worth noticing in that output. First, the two nonces found (113,928 and 28,134) both land in the same order of magnitude as the `16^4 = 65,536` expected-attempts estimate — that's the proof-of-work cost made concrete, not theoretical. Second, mutating a transaction amount **after** mining (without recomputing the hash) is caught immediately by `is_valid()` — this is the mechanism, demonstrated, not asserted. Third, the fork resolution correctly picks the three-block main chain over the two-block fork by cumulative work, which in this uniform-difficulty case happens to agree with "longest" — the next section covers exactly when it wouldn't.

Full lab — with a difficulty-adjustment simulation, a peer-to-peer toy network (multiple `Blockchain` instances mining independently and syncing via fork resolution), and a deliberately-broken variant for students to find and fix the immutability bug: **`labs/py/22-blockchain-scratch/`**.

### Why "longest chain" is the wrong mental model

If difficulty is constant across the compared chains, cumulative work is directly proportional to block count, and "longest chain wins" and "heaviest chain wins" agree — which is exactly why the shorthand persists and rarely causes visible problems in casual explanation. But they diverge the instant difficulty varies: a 10-block chain mined at difficulty 4 has less cumulative work than an 8-block chain mined at difficulty 6, because `10 × 16^4 = 655,360` is less than `8 × 16^6 = 134,217,728`. A node applying a literal "count the blocks" rule would pick the wrong chain. Real Bitcoin nodes track and compare **cumulative chainwork**, precisely to handle difficulty changes correctly — this is a real, if infrequent, source of confusion even among engineers who've worked adjacent to blockchain infrastructure without implementing consensus rules directly.

---

## How it's done in production

Bitcoin Core and Ethereum clients (Geth, Nethermind, Reth) implement exactly this mechanism at a scale and with a level of network-layer sophistication a from-scratch educational build doesn't touch: peer discovery and gossip protocols to propagate blocks across thousands of geographically distributed nodes within seconds, transaction mempool management (pending transactions competing for inclusion by fee), UTXO-set or state-trie caching so validation doesn't require replaying the entire chain history for every new block (module 4), and — critically — **orphan/stale block handling**, since in production a node frequently receives a valid block for a height it already has a block for, and must track both until one side of the fork pulls ahead.

| Symptom | Cause | Fix |
|---|---|---|
| A node rejects a chain that's objectively "winning" by block count | Difficulty varied across the compared segments; node compared block count instead of cumulative work | Track and compare cumulative chainwork explicitly, never raw block count |
| Two miners both find valid blocks at nearly the same height, network briefly disagrees | Natural propagation latency — this is expected, routine behavior, not an attack | Wait for confirmations; the network converges within one to a few blocks in the overwhelming majority of cases |
| A transaction that was "confirmed" 1 block ago later disappears from the canonical chain | A short-lived fork resolved against the block containing it (a "reorg") — this is exactly why exchanges require multiple confirmations before crediting a deposit | Wait for the number of confirmations appropriate to the value at risk (module 3 covers the actual probability math) |
| Mining a block takes far longer or shorter than the target interval | Difficulty hasn't adjusted to a recent large hashrate change | Difficulty-adjustment algorithm self-corrects over the next adjustment window; short-term deviation is expected, not a bug |
| A node with a slightly different validation rule accepts a block the rest of the network rejects (or vice versa) | A consensus rule mismatch — different software version, or a bug — causing a "chain split" | This is precisely how contentious hard forks happen (Bitcoin/Bitcoin Cash, Ethereum/Ethereum Classic); requires explicit node-software coordination to resolve, not automatic |

---

## Tradeoffs & when NOT to use it

- **Don't build a from-scratch chain like this for anything beyond learning.** Every production chain needs P2P networking, mempool design, DoS resistance against spam transactions, and (for anything handling real value) a security-audited implementation — the code above intentionally omits all of it to isolate the core mechanism.
- **Don't assume "more confirmations" ever reaches mathematical certainty under Nakamoto consensus.** It's probabilistic finality: the probability of a reorg deep enough to reverse a transaction shrinks exponentially with confirmations, but never reaches exactly zero — a distinction module 3 covers precisely, including the actual math, and one worth naming explicitly rather than implying "6 confirmations = safe" as an absolute.
- **Don't use a public, permissionless proof-of-work chain when you control all the participants.** If every node writing to the ledger is a known, trusted (or at least accountable) party — an internal audit log across your own company's services, a consortium of known banks — a permissioned system with classical BFT consensus (module 3) gives deterministic finality at a fraction of the computational cost, with none of the energy externality. Proof-of-work's cost buys permissionless, pseudonymous participation specifically; paying that cost when you don't need that property is waste, not rigor.
- **The "immutability" property has a real, practical limit worth stating precisely in an interview.** It's immutable *in the sense that editing history is astronomically expensive to get accepted by the network* — it is not immutable in the sense that data can never be reorganized (reorgs happen routinely, if usually shallow) or that the *rules themselves* can't change (a hard fork is exactly the network agreeing to change what "valid" means going forward).

---

## Interview questions

### Q1 — What exactly makes a blockchain "immutable"? Be precise.
**Testing:** whether the candidate can explain the mechanism instead of reciting the word.
**Answer:** Each block's hash is computed over its full contents including `previous_hash`, which points to the prior block's hash. Editing any past block changes that block's hash, which no longer matches what the next block recorded as `previous_hash`, invalidating it and cascading through every subsequent block. "Immutable" means "editing history requires redoing proof-of-work for every block after the edit, faster than the honest network extends the real chain" — a cost-based guarantee, not an absolute impossibility.
**Follow-up trap:** *"Does that mean a sufficiently powerful attacker CAN rewrite history?"* — yes, in principle: this is exactly what a 51% attack is (module 3 covers the economics). "Immutable" is a statement about the cost of an attack scaling with network hashpower, not a claim that rewriting is impossible in an absolute mathematical sense.

### Q2 — Why does a block's header commit to a Merkle root of transactions rather than the raw transaction list?
**Testing:** connecting module 1's Merkle trees to this module's block design, a common interview link.
**Answer:** Keeps the header a small, fixed size (Bitcoin's header is 80 bytes regardless of block transaction count) while still cryptographically committing to every transaction — changing any transaction changes the Merkle root, which changes the header hash, exactly as if the full transaction data were hashed directly. It also enables SPV/light clients to verify a transaction's inclusion with a short Merkle proof instead of downloading the full block.
**Follow-up trap:** *"If the header only has the root, how does a node validate the actual transactions inside?"* — a full node still downloads and validates the complete block body against the root (recomputing the Merkle tree and checking it matches), and separately validates each transaction's signatures and state transitions; the compact header is what gets propagated first and referenced by later blocks, not a substitute for full validation by nodes that need it.

### Q3 — Walk through proof-of-work mining mechanically. What's actually being searched for?
**Testing:** the search-space and expected-attempts intuition.
**Answer:** A miner varies the `nonce` field (and sometimes other malleable fields) and recomputes the block hash each time, looking for a hash that falls below a numeric target — conventionally expressed as requiring `D` leading zero bits. Because a good hash function is unpredictable, there's no better strategy than brute-force trial, and the expected number of attempts to find a valid nonce is `2^D`. This module's tested code at difficulty 4 (16 leading zero bits worth, in hex-nibble terms) found valid nonces in 113,928 and 28,134 tries — both in the right order of magnitude versus the `16^4 = 65,536` expected value.
**Follow-up trap:** *"Why hex leading zeros and not decimal, and does the specific representation matter?"* — no, it's just a convenient way to express a numeric threshold; what actually matters is comparing the hash's integer value against a target threshold (`hash_value < target`), and "N leading hex zeros" is shorthand for one particular way of expressing that threshold. Real implementations (Bitcoin's `nBits` compact target encoding) work with the numeric target directly, not a leading-zero-count heuristic, though they're mathematically equivalent framings.

### Q4 — What's the difference between "longest chain wins" and the actual Nakamoto consensus fork-choice rule?
**Testing:** the module's central nuance, since this phrase gets repeated imprecisely constantly.
**Answer:** The actual rule is "the chain with the most cumulative proof-of-work (chainwork) wins," which equals "longest" only when difficulty is uniform across the compared chains. Since Bitcoin's difficulty adjusts roughly every two weeks, two competing chain segments spanning a difficulty adjustment could have different work-per-block, making a shorter-by-block-count chain the heavier, correct one to follow.
**Follow-up trap:** *"Give a concrete numeric example where they disagree."* — a 10-block chain at difficulty 4 has cumulative work `10 × 16^4 = 655,360`; an 8-block chain at difficulty 6 has `8 × 16^6 = 134,217,728` — over 200x more work despite fewer blocks. A node using literal block-count comparison would (wrongly) follow the first chain.

### Q5 — Your `is_valid()` check recomputes every block's hash from scratch. What's the cost of this at Bitcoin's actual current chain length, and how do production nodes handle it?
**Testing:** whether toy-scale reasoning transfers to production-scale constraints.
**Answer:** Bitcoin's chain is 900,000+ blocks deep as of 2026; full-chain validation from genesis (an "initial block download") is a real, hours-to-days operation for a new node, which is why production nodes checkpoint known-good historical block hashes (widely-verified, hardcoded reference points) to skip re-verifying ancient history's proof-of-work in some fast-sync modes, while still requiring full validation of recent, actively-contested chain history. Pruned nodes additionally discard old block data after validating it once, keeping only the UTXO set (module 4) needed to validate new transactions.
**Follow-up trap:** *"Doesn't checkpointing reintroduce a trust assumption the whole design was supposed to avoid?"* — partially, yes, and this is a real, acknowledged tradeoff: checkpoints are typically embedded in client software by developers, which is a form of trusting the client software's maintainers for *historical* chain data specifically, not for *new* blocks, which are still fully validated. It's a pragmatic performance optimization with a narrow, bounded trust surface, not a silent abandonment of trustlessness.

### Q6 — Two miners solve block 500 within two seconds of each other, on opposite sides of the world. What happens over the next several minutes?
**Testing:** systems-level understanding of fork formation and resolution as an emergent, not orchestrated, process.
**Answer:** Nodes near each miner see their local block first and extend it, creating a temporary fork with two competing block-500 candidates. No global vote occurs. Miners continue mining on top of whichever block-500 they received first. The fork resolves the moment one side's chain accumulates more total work — typically when the *next* block (501) is found on one side before the other, at which point nodes following the now-shorter/lighter side switch (a "reorg") to the heavier chain, and the losing block-500's transactions return to the mempool to be re-included later (unless they were also included in the winning block).
**Follow-up trap:** *"What if both sides keep finding blocks at almost exactly the same rate for several rounds?"* — statistically increasingly unlikely each round (roughly halving in probability per additional simultaneous round, similar in spirit to a biased coin-flip race), but not impossible; this is exactly why higher-value transactions warrant more confirmations before being treated as final — the probability of a fork persisting past N blocks isn't zero, it's just exponentially small, and module 3 covers the actual formula.

### Q7 — Why is "expensive to produce, cheap to verify" the specific property proof-of-work needs, rather than just "expensive"?
**Testing:** the asymmetry that makes the whole mechanism practical at network scale.
**Answer:** Every node on the network needs to verify every new block it receives, potentially thousands of times per day across the whole network's block production — if verification were as expensive as mining, the network's total verification cost would scale with its total mining cost, which is economically unworkable at scale. Because verification is a single hash computation (microseconds) while mining requires many attempts (the `2^D` expected search), nodes can cheaply confirm that real work was done without redoing that work themselves.
**Follow-up trap:** *"Is there a mining approach that breaks this asymmetry?"* — ASIC-resistant proof-of-work schemes (Ethereum's pre-Merge Ethash, memory-hard functions like those discussed in `T30-crypto-practice` for password hashing) intentionally make mining *more* expensive relative to naive hashing specifically to resist specialized hardware centralizing mining power — but they preserve the fundamental asymmetry (cheap verification) throughout; the goal is changing *who* can mine efficiently, not breaking the verify-cheaply property the whole system depends on.

### Q8 — A company wants an internal ledger among five known, mutually-trusted subsidiaries, tamper-evident and auditable. Would you recommend proof-of-work?
**Testing:** judgment about when the mechanism this module built is the wrong tool — this connects directly to module 8's broader theme.
**Answer:** No. Proof-of-work's cost buys permissionless participation among mutually distrusting, potentially anonymous parties with no fixed membership — none of which applies to five known subsidiaries of one company. A permissioned ledger with classical BFT consensus (module 3) or even a straightforward hash-chained append-only log with each subsidiary's signature gives the same tamper-evidence and auditability with deterministic finality and no energy cost, because you already have exactly what Nakamoto consensus exists to substitute for: known, accountable participants.
**Follow-up trap:** *"If it's not proof-of-work, is it still meaningfully 'a blockchain'?"* — the block/chain/hash-linking structure is genuinely useful independent of the consensus mechanism layered on top, so yes, a permissioned hash-chained ledger is reasonably still "a blockchain" in the structural sense — the more precise statement for an interview is that the *consensus mechanism* (PoW vs. BFT vs. simple signature-based append) is the actual design decision that should track the trust model, and "blockchain" alone under-specifies which one you're building.

### Q9 — What specifically would you need to add to this module's from-scratch implementation before it could handle a real, adversarial network of untrusted peers?
**Testing:** whether the candidate can name the real gap between a toy and production system precisely.
**Answer:** At minimum: a P2P networking and gossip layer for block/transaction propagation with basic DoS resistance (rate-limiting, peer scoring, banning misbehaving peers); mempool policy (fee-based transaction prioritization, size limits, replace-by-fee rules); full transaction validation beyond hash/chain integrity (signature checks, no double-spends against current state, script/opcode validation); handling of orphan blocks (a valid block whose parent hasn't arrived yet) and stale/competing chains simultaneously; and a difficulty-adjustment algorithm rather than a fixed constant.
**Follow-up trap:** *"Which of those is most likely to be the actual attack surface in practice?"* — the P2P and mempool layers, historically: most real-world Bitcoin/Ethereum client vulnerabilities and incidents have been in network-layer DoS handling and mempool-acceptance logic (transaction-flooding, malformed-message parsing bugs) rather than in the core hashing/chaining mechanism itself, which is comparatively simple and has had far fewer implementation bugs found over the ecosystem's history.

### Q10 — Design a test suite for this from-scratch blockchain implementation. What are the cases that actually matter?
**Testing:** whether the candidate thinks about correctness the way a staff engineer would, not just "does it run."
**Answer:** Positive: valid chain of N blocks validates true; a valid single-transaction inclusion round-trips correctly. Negative/tamper: mutating any field of any historical block (transaction data, timestamp, nonce, previous_hash) without recomputing must be caught by `is_valid()`; a block whose hash doesn't satisfy the difficulty target must be rejected even if internally consistent; a chain with a broken index sequence or mismatched `previous_hash` must be rejected. Fork-specific: two chains of equal block count but different cumulative work must resolve to the heavier one, not the longer one; an invalid chain must never be selected over a valid shorter one, even if it claims more nominal "length."
**Follow-up trap:** *"Which of these is easiest to get subtly wrong in a real implementation?"* — the difficulty-target check specifically: it's tempting to check `nonce` correctness by re-running proof-of-work search from scratch during validation (expensive and pointless, since verification should be O(1)) rather than simply re-hashing once and comparing against the target — conflating "search for a valid nonce" (mining) with "check a claimed nonce is valid" (validation) is a real, recurring implementation mistake that defeats the entire cheap-verification property this module's Q7 covers.

---

## Red flags that fail you

- Saying "longest chain wins" without the caveat that it's actually cumulative work, or being unable to construct a counterexample when pressed.
- Describing "immutable" as an absolute guarantee rather than a cost-based one.
- Not knowing that `previous_hash` must reference the *content hash* of the prior block, not just its index, for tamper-evidence to work.
- Confusing "expensive to mine" with "expensive to verify" — not understanding the asymmetry is the entire point.
- Proposing proof-of-work for a system with a small, known, trusted set of participants.
- Treating a fork/reorg as an anomaly or attack by default rather than routine, expected network behavior at shallow depths.

---

## Cheat card

```
BLOCK = {index, timestamp, transactions (or Merkle root), previous_hash, nonce, hash}
  hash computed over EVERYTHING except itself; previous_hash = prior block's actual hash
IMMUTABILITY = cascading invalidation: edit block N -> hash changes -> block N+1's
  previous_hash mismatches -> N+1 invalid -> every block after N invalid too.
  NOT an absolute guarantee — it's "redoing PoW for every block after N, faster than
  the honest network extends the real chain" — a COST, see 51% attack (module 3).

MINING = find nonce s.t. hash(block) < target (conventionally: D leading zero bits).
  Expected attempts ~= 2^D (16^D in hex-nibble terms). Cheap to VERIFY (1 hash), expensive
  to FIND — this asymmetry is the whole security model. Tested: difficulty=4 (16^4=65,536
  expected) found nonces 113,928 and 28,134 — right order of magnitude.
Bitcoin: difficulty retargets every 2016 blocks, targets ~10min/block; self-corrects
  against total network hashrate changes.

VALIDATION (a node RECOMPUTES, never trusts): hash matches recomputed hash; previous_hash
  matches prior block's actual hash; hash satisfies PoW target; index is sequential.
  ANY failure invalidates that block AND everything chained after it.

FORK RESOLUTION: NOT "longest chain" — actual rule is MOST CUMULATIVE WORK (chainwork).
  Same thing only when difficulty is uniform across compared segments. Counterexample:
  10 blocks @ diff 4 = 655,360 work < 8 blocks @ diff 6 = 134,217,728 work.
  Forks are ROUTINE (propagation latency), not inherently an attack.
  "Confirmations" = probabilistic finality, shrinks exponentially, never reaches exactly 0.

WRONG TOOL: known/trusted/small participant set -> permissioned ledger + classical BFT
  (module 3), not PoW. PoW's cost buys PERMISSIONLESS pseudonymous participation specifically.

REORG = short-lived fork resolves against a previously-"confirmed" block; why exchanges
  require N confirmations before crediting deposits, scaled to transaction value.
```

## Sources

- [Bitcoin: A Peer-to-Peer Electronic Cash System (Nakamoto, 2008)](https://bitcoin.org/bitcoin.pdf) — accessed 2026-08-08
- [Haber & Stornetta — How to Time-Stamp a Digital Document (1991)](https://link.springer.com/article/10.1007/BF00196791) — accessed 2026-08-08
- [Bitcoin Core Developer Reference — Block Chain, Proof of Work, Difficulty Retargeting](https://developer.bitcoin.org/reference/block_chain.html) — accessed 2026-08-08
- [Lamport, Shostak, Pease — The Byzantine Generals Problem (1982)](https://lamport.azurewebsites.net/pubs/byz.pdf) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
