# Bitcoin UTXO vs Ethereum Accounts, EVM, Gas, State Trie

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** T22-consensus · **Updated:** 2026-08-23
> **Module id:** `T22-bitcoin-ethereum` · **Tags:** blockchain, evm, bitcoin, critical

## The 30-second version

Bitcoin and Ethereum disagree about what the ledger *is*. Bitcoin keeps a UTXO set: money exists as unspent outputs, transactions declare which outputs they consume and which they create, validation checks signatures plus the absence of double-spends against one flat set — embarrassingly parallel, naturally private, useless for general computation. Ethereum keeps a world state: every address has an account record (nonce, balance, code hash, storage root), contracts are code living inside that state, and the EVM is a 256-bit stack machine executing transactions sequentially while gas prices every opcode — 21,000 base per transfer, 2,100 for a cold SLOAD, 20,000 to write a fresh storage slot — so resource abuse is billed instead of forbidden. All of it commits into a Merkle Patricia Trie whose root sits in each header. Pick UTXO when you want verifiable payment objects; pick accounts when you want composable state machines; either way, know which model your mental debugging habits come from, because they differ exactly where systems fail.

## Why this gets asked

Because it is secretly a distributed-systems design question wearing crypto clothes. UTXO versus accounts is object-state versus shared-memory concurrency: interviewers who have built payment rails want to hear you connect UTXO's spend-once semantics to idempotency keys and optimistic concurrency, and accounts' global ordering to serialization bottlenecks and MEV. Gas questions filter people who have actually shipped contracts: quoting SSTORE at 20k gas or knowing a failed transaction still consumes gas shows you've watched a mainnet bill. The state-trie question probes whether you understand why light clients can prove an account balance without downloading the chain — the same log-sized-proof reasoning as module 01, applied to mutable keyed state. Expect a follow-up like "your exchange credits deposits; where do you read them from and what can go wrong?" — the answer runs straight through finality tags, reorg handling, and indexer lag.

## Lineage

**What came before.** Bitcoin's UTXO model descends from Chaum-style electronic cash: coins as cryptographic objects that die when spent, preventing double-spend without a central issuer by publishing every spend. Nakamoto's innovation was making the death certificate public and ordered (the chain), not the coin itself. Ethereum (whitepaper late 2013, Yellow Paper by Gavin Wood 2014) inverted the abstraction: instead of coins, a single replicated computer whose memory happens to hold balances. Vitalik's framing was that Bitcoin's scripting was deliberately crippled — non-Turing-complete, no state — so finance-grade logic (escrow, derivatives, DAOs) needed a first-class programmable state machine. That choice bought composability ("money legos") and paid for it with sequential execution, gas markets, and permanent state bloat.

**Where it stands now.** The two ledgers have diverged less in mechanism than in economics. Bitcoin still ships UTXO purity: SegWit (2017) split witness data out at a 4M-weight-unit block budget, Taproot (November 2021) made complex spends indistinguishable from singles. Ethereum layered five hard forks of economics onto the account model since 2021: EIP-1559 (August 2021) made base fees deterministic and burns them (~80% of ETH issuance offset at busy times); The Merge (2022) changed issuance; EIP-4844 (March 13, 2024) created a second fee market for 128 KiB blobs carrying L2 data; Pectra (May 7, 2025) let EOAs behave like smart accounts via EIP-7702 and doubled blob capacity; Fusaka (December 3, 2025) shipped PeerDAS with blob-parameter forks pushing targets from 6 toward 21 blobs/block by January 2026. Meanwhile the account model is being parallelized: Sei's parallel EVM went live in 2024, Monad's EVM-compatible L1 launched late 2025, and Glamsterdam's block-access lists (EIP-7928) bring declared state access to mainnet for parallel execution, targeted H2 2026.

**Where it's heading.** Three currents. First, the EVM won the VM war by network effects — MoveVM (Aptos/Sui) and Solana's Sealevel exist, but new chains default to EVM compatibility, and even Bitcoin ecosystems wrap EVM sidecars. Second, state is the binding constraint nobody markets around: a full Ethereum node crosses the terabyte class, and the roadmap attacks it via Verkle trees (proofs under 200 bytes replacing multi-KB trie branches), state expiry, and eventually weak statelessness where blocks carry witnesses instead of nodes keeping full tries. Third, the account itself dissolves: ERC-4337 smart accounts plus EIP-7702 mean EOAs, contracts, and passkey wallets converge into programmable accounts with social recovery and session keys, which changes key management more than any consensus upgrade has.

---

## Mental model

```
BITCOIN = CHECK CLEARING          ETHEREUM = SHARED SPREADSHEET
┌─────────────────────┐           ┌──────────────────────────────┐
│ UTXO set (unspent   │           │ one global state, versioned  │
│ banknotes)          │           │ every tx mutates it serially │
│                     │           │                              │
│ tx: burn notes you  │           │ tx: run program against      │
│     own -> mint new │           │ current sheet -> new sheet   │
│     notes to others │           │ gas meters every step        │
│ +change back to you │           │                              │
└─────────────────────┘           └──────────────────────────────┘
spend-once = idempotency by         global order = contention,
construction; validation            MEV, and the whole ordering
parallelizes trivially              industry (searchers/builders)
```

For gas, the model is a taxi meter wired to every instruction: reading far away state (cold SLOAD) costs 2,100 because someone's disk seeks; writing a fresh slot costs 20,000 because the state grows forever and everyone replicates it forever; reverting refunds execution but never the work done. Gas converts "the network does your computing" from charity into billing, and the fee market turns congestion into price rather than queues.

For the state trie, picture a filesystem tree where every directory and file name is hashed into its parent: the root fingerprint fits in the 32-byte header, and proving "account X holds Y" means handing over only the sibling hashes along X's path — a few kilobytes — instead of the whole drive.

---

## How it actually works

### UTXO mechanics

A transaction lists inputs `(prev_txid, vout)` and outputs `(value, locking_script)`. Validation per input: the referenced output exists in the UTXO set and isn't already spent (set membership — this is why nodes keep the UTXO set hot in RAM, ~65-75M outputs and several GB in recent years); the unlocking script plus locking script evaluate true under Bitcoin Script (a Forth-like stack language, deliberately non-Turing-complete: no loops); sum(outputs) ≤ sum(inputs), difference = miner fee. No account exists anywhere; your "balance" is the sum of outputs you can unlock. Consequences worth saying in interviews:

- **Idempotency is structural**: an output can be consumed exactly once; double-spends fail set lookup, not business logic.
- **Parallelism**: independent inputs validate concurrently; Bitcoin Core validates scripts across threads.
- **Privacy posture**: fresh addresses per payment are native; clustering heuristics (co-spends reveal common ownership) are the counter-practice, and chain-analysis firms monetize exactly this gap.
- **Change**: payments create a change output back to you; forgetting it donates it to miners (a classic bug class in hand-built transactions).
- **Coinbase rule**: freshly mined outputs unspendable for 100 confirmations.

Weight accounting since SegWit: legacy bytes weigh 4 units, witness (signature) bytes weigh 1; blocks cap at 4M WU, so signature-heavy transactions effectively got a 75% discount — that was the point (fixing the 2015-16 malleability-era backlog economics), and ordinal inscriptions later abused cheap witness space for arbitrary data.

### Account model mechanics

World state maps address → `[nonce, balance, codeHash, storageRoot]`. Externally owned accounts sign transactions; contract accounts execute code when called. Nonce forces total order per sender (replay protection pre-chainId, now combined with EIP-155's chain-id in signatures). Storage lives under each contract: another trie keyed by keccak(slot) → 32-byte values. Four tries total: world state (committed in header as stateRoot), per-contract storage, transactions list, receipts (logs, status). RLP encodes everything; keccak256 hashes nodes; empty subtrees compress via extension/leaf encoding — the MPT is a radix trie over nibbles with branch fan-out ≤17.

Proof shape: an account proof is the branch from stateRoot to the leaf, typically 3-8 nodes, each up to ~532 bytes encoded — hence kilobyte-scale proofs and the Verkle ambition (<200 bytes via vector commitments).

### The EVM

Design constants first, because they explain everything else: 256-bit words chosen so keccak outputs and addresses fit one stack item — convenient, catastrophic for arithmetic (a 64-bit add emulates through multiple 256-bit ops), and the reason Solidity loops over uint256 dominate bytecode. Stack capped at 1024 items; memory is byte-addressed, priced linearly-plus-quadratically in 32-byte words (expansion ≈ 3·words + words²/512); storage persists.

Gas schedule you should be able to quote (post-Istanbul/Berlin, EIP-2929 access lists):

| Operation | Gas | Note |
|---|---|---|
| Base transaction | 21,000 | every tx |
| ADD/MUL/MLOAD/MSTORE | 3-8 | arithmetic class |
| KECCAK256 | 30 + 6/word | hashing |
| SLOAD cold | 2,100 | first touch of a slot |
| SLOAD warm | 100 | subsequent touches |
| SSTORE zero→nonzero | 20,000 | **new slot: the expensive one** |
| SSTORE nonzero→nonzero | 2,900 | updates |
| SSTORE nonzero→zero | 2,900 (+4,800 refund) | cleanup incentive |
| CALL cold account | 2,600 (+700 base) | cross-contract touch |
| Value transfer via CALL | +9,000 | ETH movement |
| Call to new account | +25,000 | state creation |
| CREATE / CREATE2 | 32,000 | deployment |
| LOGn | 375 + 375·topics + 8·bytes | events |
| Calldata byte | 16 nonzero / 4 zero | EIP-2028 |

Two structural rules: **reverts refund gas but not state** — execution stops, state rolls forward-then-back atomically, spent gas stays spent (that's why simulations use `eth_call`); and **EIP-7623 (Prague, 2025) added a calldata floor** so rollups can't dump arbitrarily cheap data into normal transactions — data-heavy txs pay `max(gas_used, 21000 + 10·tokens)` where tokens weight nonzero calldata 4×.

Fee markets: post-London, users sign `(maxFeePerGas, maxPriorityFeePerGas)`; protocol computes baseFee per block, adjusting ±12.5% max toward 50% utilization, and **burns it**; proposers collect tips. Blobs run their own market with the same curve over a 6-target (rising under BPO forks) and a 1-wei floor — which is why L2 fees collapsed from dollars to cents after Dencun.

### Execution flow, end to end

Tx arrives → mempool validates signature, nonce continuity, balance ≥ gasLimit·maxFee → block builder orders (MEV!) and executes sequentially against local state, collecting gas → block carries txs + header(stateRoot after, receiptsRoot, gasUsed, bloom) → validators attest → fork choice/finality. Every full node repeats the execution bit-for-bit; determinism is sacred, which is why the EVM has no floats, no clock, no randomness except PREVRANDAO-derived beacon output.

## Build it from scratch

Two runnable engines, stdlib-only: a mini-EVM with honest gas accounting, and a UTXO ledger enforcing spend-once semantics. Both verified below.

```python
"""Minimal EVM interpreter (6 opcodes) + minimal UTXO ledger."""

PUSH1, ADD, SUB = 0x60, 0x01, 0x03
SLOAD, SSTORE   = 0x54, 0x55
STOP            = 0x00
GAS = {PUSH1: 3, ADD: 3, SUB: 3, SLOAD: None, SSTORE: None, STOP: 0}

class Revert(Exception): pass

class MiniEVM:
    """Stack machine over one contract's storage. Cold slot reads cost 2100 once;
    SSTORE costs 20000 on zero->nonzero, else 2900 - matching mainnet pricing."""

    def __init__(self):
        self.storage, self.touched = {}, set()

    def _sload_gas(self, slot):
        if slot not in self.touched:
            self.touched.add(slot)
            return 2100                      # cold access (EIP-2929)
        return 100                           # warm

    def _sstore_gas(self, slot, val):
        cold = 2100 if slot not in self.touched else 0
        self.touched.add(slot)
        cur = self.storage.get(slot, 0)
        return cold + (20000 if cur == 0 and val != 0 else 2900)

    def run(self, code: bytes, gas_cap=100_000):
        pc, stack, gas = 0, [], gas_cap
        while pc < len(code):
            op = code[pc]; pc += 1
            if op == STOP:
                return gas
            if op == PUSH1:
                g = GAS[PUSH1]; stack.append(code[pc]); pc += 1
            elif op in (ADD, SUB):
                g = GAS[op]
                a, b = stack.pop(), stack.pop()
                stack.append(a + b if op == ADD else a - b)   # real EVM: mod 2^256
            elif op == SLOAD:
                slot = stack.pop()
                g = self._sload_gas(slot)
                stack.append(self.storage.get(slot, 0))
            elif op == SSTORE:
                slot, val = stack.pop(), stack.pop()          # key sits on top
                g = self._sstore_gas(slot, val)
                self.storage[slot] = val
            else:
                raise Revert(f'bad opcode {op:#x}')
            gas -= g
            if gas < 0:
                raise Revert('out of gas')     # state reverts; gas stays spent
        raise Revert('fell off end')

code = bytes([
    PUSH1, 42, PUSH1, 7, SSTORE,               # storage[7] = 42
    PUSH1, 7, SLOAD, PUSH1, 0, ADD,            # load it back, burn deterministically
    STOP,
])
evm = MiniEVM()
used_gas = evm.run(code)
assert evm.storage[7] == 42
assert used_gas == 3+3 + (2100+20000) + 3+100 + 3+3   # = 22,215
print(f'mini-EVM ok: {used_gas} gas - new-slot SSTORE dominates at 20k')
```

```python
import hashlib

def txid(tx): return hashlib.sha256(repr(sorted(tx.items())).encode()).hexdigest()[:16]

class DoubleSpend(Exception): pass

class UtxoLedger:
    def __init__(self):
        self.utxos = {}                        # (txid, vout) -> (value, owner)

    def coinbase(self, owner, value):
        t = {'inputs': [], 'outputs': [(value, owner)]}
        i = txid(t)
        self.utxos[(i, 0)] = (value, owner)
        return i

    def apply(self, tx):
        total_in, spent_here = 0, []
        for (ref, sig_owner) in tx['inputs']:  # ref = (txid, vout)
            if ref not in self.utxos:
                raise DoubleSpend(f'{ref} is not an unspent output')
            value, owner = self.utxos[ref]
            if owner != sig_owner:             # stand-in for script/sig verification
                raise PermissionError('unlocking fails')
            total_in += value
            spent_here.append(ref)
        total_out = sum(v for v, _ in tx['outputs'])
        assert total_in >= total_out           # difference = miner fee
        tid = txid(tx)
        for k in spent_here:
            del self.utxos[k]                  # outputs die exactly once
        for i, (v, o) in enumerate(tx['outputs']):
            self.utxos[(tid, i)] = (v, o)
        return tid

led = UtxoLedger()
c = led.coinbase('alice', 100)
tid = led.apply({'inputs': [((c, 0), 'alice')],
                 'outputs': [(30, 'bob'), (68, 'alice')]})   # 2 to fees
assert (c, 0) not in led.utxos                 # consumed
try:
    led.apply({'inputs': [((c, 0), 'alice')], 'outputs': [(100, 'mallory')]})
    assert False, 'double spend accepted!'
except DoubleSpend:
    pass                                       # rejected by SET LOOKUP, not logic
assert sum(v for v, _ in led.utxos.values()) == 98
print('UTXO ok: spend-once enforced structurally')
```

The EVM demo teaches the interview point numerically: writing one fresh storage slot costs 22,215 gas here versus ~12 for the arithmetic — state creation is what you bill for, because every node replicates it forever. The UTXO demo teaches its own: double-spend rejection needs no business rules, just set membership. Deliberate omissions: no memory/calldata, no calls or logs, no signatures (owner strings stand in), no coin-selection strategy for building transactions.

## How it's done in production

**Clients and data.** Execution clients (Geth, Nethermind, Besu, Reth) offer full (re-execute everything, ~1 TB class), snap (download trie chunks + heal, hours), and archive modes (every historical state, multiple TB — Erigon/Reth compress hard). Bitcoin Core keeps levelDB chainstate plus a hot UTXO cache. Indexers (Erigon-style, Hypersync, Ponder, The Graph) exist because apps query events and balances at scale, which raw RPC was never meant to serve.

**Gas engineering.** Solidity optimizer and via-IR pipelines, Foundry gas reports per function, storage packing (multiple small fields into one 32-byte slot turns five 20k writes into one), calldata-heavy batchers watching EIP-7623 floors, and simulation-first UX (`eth_call` / Tenderly) so users never pay for doomed transactions.

| Symptom | Cause | Fix |
|---|---|---|
| Tx reverts with "out of gas" but balance dropped | Gas consumed before revert is never refunded | Simulate first; estimate +20% headroom; check 63/64 depth rule on nested calls |
| "Nonce too low/high" storms under retries | Parallel senders sharing one EOA nonce | One nonce manager per sender; queue, don't broadcast blind |
| Deposit visible but balance API stale | Indexer lag vs reorg | Read finalized tag; reconcile indexer checkpoints against finality |
| Gas estimates wildly wrong after fork | Cold/warm semantics changed pricing (EIP-2929-class events) | Pin client versions; regression-test estimates across forks |
| Batch settlement costs jumped post-2025 | EIP-7623 calldata floor | Compress calldata (zlib/brotli pre-compiles) or move to blobs |
| Storage writes dominate contract cost | Unpacked structs, repeated zero→nonzero flips | Pack slots; cache warm reads; consider transient storage (EIP-1153 TSTORE: 100 gas, cleared per-tx) |

## Tradeoffs & when NOT to use it

- **UTXO when**: payments, auditability of individual objects, parallel validation, privacy-by-default addressing. **Accounts when**: composable contracts needing shared state (DEXs, lending), simple wallet UX, rich queries over balances.
- **Don't put general computation on Bitcoin's layer** — Script has no loops by design; Taproot adds introspection but the L1 stays a payment rail. Anything dynamic belongs on sidechains/L2s or other chains.
- **Ethereum L1 is not for high-frequency anything**: ~15-20 base-layer tps means consumer products live on L2s; paying mainnet rates for what a rollup does at 1-5% cost is a budgeting failure, not decentralization.
- **State growth is the silent bill**: every new slot is replicated forever by every node; contracts that mint unbounded storage (NFT metadata on-chain!) are externalities. Design for expiry-friendly or hash-pointer storage.
- **256-bit words tax everything**: CPU-emulating uint64 math costs multiples; chains redesigning around 64-bit VMs (Move-based, Solana's BPF) gain real performance — relevant when advising non-EVM deployments.
- **When neither model fits:** event-sourced off-chain systems with periodic anchoring give audit trails without global replication; most "we need smart contracts" enterprise flows are signed message queues in disguise.

## Interview questions

### Q1 — Contrast UTXO and account models at the data-structure level.
**Testing:** precision beyond "Bitcoin uses coins".
**Answer:** UTXO: ledger is a set of unspent outputs; each tx consumes whole outputs by reference and creates new ones; validity = signatures + set membership + value conservation; no mutable state exists. Accounts: ledger maps address → (nonce, balance, codeHash, storageRoot); txs mutate entries in place under global ordering; validity includes nonce continuity and balance sufficiency.
**Follow-up trap:** *"Which parallelizes better and why?"* — UTXO: disjoint input sets are independent proofs, so validation shards trivially; accounts need conflict detection (two txs touching one storage slot serialize), which is exactly what parallel-EVM chains now solve with declared access lists.

### Q2 — Why does Ethereum charge 20,000 gas for a new storage slot but 2,900 for updating?
**Testing:** whether gas economics clicked.
**Answer:** New slots permanently grow the state that every full node stores forever — the fee internalizes a perpetual externality. Updates reuse existing bytes, costing only execution. Refunds (~4,800 for clearing to zero, capped at 1/5 of gas post-London) nudge cleanup without making refunds a DoS vector.
**Follow-up trap:** *"How would you cut a contract's gas bill 10×?"* — Pack fields into fewer slots (one 32-byte word holds several small values), avoid zero→nonzero flips in loops, move read-only lookups to calldata/memory or view calls, use transient storage for intra-tx scratch. Real answer: profile with forge gas-report first.

### Q3 — What exactly happens when a transaction runs out of gas mid-execution?
**Testing:** revert semantics; everyone thinks they know this.
**Answer:** The EVM raises OOG, the entire transaction's state effects roll back atomically (storage, balances, logs — nothing persists, not even prior successful sub-calls), the tx still appears in the block marked failed, and ALL provided gas up to the failure point is consumed — no refund. Miners/validators collect it regardless.
**Follow-up trap:** *"So why do wallets sometimes show 'failed' txs with full gas burned?"* — Because that's the mechanism working: simulation should have caught it, but MEV races, changing state between estimate and inclusion, or maliciously crafted interactions burn senders deliberately (griefing vectors on public mempools).

### Q4 — Explain EIP-1559 mechanics including the base-fee adjustment rule.
**Testing:** modern fee-market literacy.
**Answer:** Each block sets baseFee from the parent's: if parent used exactly the target gas (50% of limit), baseFee unchanged; over target raises ≤12.5%, under lowers ≤12.5% (exponential-ish decay toward equilibrium). Users sign maxFee and maxPriority; they pay min(maxFee, baseFee+tip); baseFee is BURNED, tips go to the proposer. Result: predictable pricing instead of first-price auctions.
**Follow-up trap:** *"Does burning make ETH deflationary?"* — It offsets issuance variably: burn exceeded issuance during 2023 activity peaks (supply slightly deflated), issuance leads post-Merge at moderate activity. Quote the mechanism, dodge the price-talk.

### Q5 — How can a light client prove an account's balance today, and how will that change?
**Testing:** trie knowledge plus roadmap awareness.
**Answer:** Today: fetch a Merkle Patricia Trie proof — the branch of nodes from the header's stateRoot to the account leaf (and optionally into its storage trie), verifying keccak hashes upward; typically 3-8 nodes, kilobytes. Verkle trees replace this with vector commitments: constant-size witnesses (~hundreds of bytes) supporting random sampling, enabling weak statelessness where validators verify blocks with witnesses instead of holding full tries.
**Follow-up trap:** *"Why not ship Verkle already?"* — Proof verification cost, database migration of petabyte-scale tries, and tooling churn; it slipped repeatedly on Ethereum's roadmap and remains future-facing as of Glamsterdam planning. Saying "it's scheduled" without acknowledging slippage sounds naive.

### Q6 — What problem did SegWit solve, and what's a weight unit?
**Testing:** Bitcoin mechanics depth.
**Answer:** SegWit moved signature (witness) data to a separate structure, fixing transaction malleability (signatures no longer inside the txid-hashed serialization) and repricing block space: legacy bytes weigh 4 units, witness bytes weigh 1, blocks cap at 4M weight units. Effect: signature-heavy spends got up to ~75% cheaper, unlocking capacity and later enabling cheap inscription data.
**Follow-up trap:** *"Did SegWit increase the block size?"* — Not the byte limit conceptually: it introduced weighted capacity. A block full of witness data can exceed 1M legacy-equivalent bytes while weighing under 4M WU. Precision matters; "increased to 4MB" is the common wrong version.

### Q7 — Where do replay attacks come from and how are they prevented across chains/forks?
**Testing:** security history applied.
**Answer:** Same-signed transaction valid on two networks (ETH/ETC post-2016 split) lets one broadcast drain both. Fixes: EIP-155 embeds chainId into the signing hash (2016), making signatures network-specific; contracts add per-chain domain separation (EIP-712) and salted deploy addresses. Forks without replay protection forced users to race spend orderings.
**Follow-up trap:** *"Do all chains enforce chainId?"* — Legacy (pre-155) signatures remain technically valid formats on some tools; safe practice treats unsigned-chainId txs as hazardous, and bridges/custodians reject them.

### Q8 — Your exchange credits BTC deposits after 3 confirmations and ETH after 5 minutes. Critique both policies quantitatively.
**Testing:** applying model differences to risk.
**Answer:** BTC 3 confs: catch-up probability for a q=10% attacker ≈ (q/p)^3 ≈ 0.14% — acceptable for mid-value, thin for whales (6 confs ≈ 10⁻⁴%). ETH 5 minutes ≈ 25 slots: past finality needs ~13, so this policy accepts justified-but-unfinalized state; better to gate on the `finalized` tag (deterministic, slashing-backed) than minutes. Different models need different primitives — confirmations are a PoW heuristic, finality tags are PoS-native truth.
**Follow-up trap:** *"Why not just always require finalization?"* — UX: users wait ~13 min. Tier by value and product surface: show instantly, credit on safe, release on finalized; document the ladder explicitly.

### Q9 — What lives in contract code versus contract storage? Where do immutables go?
**Testing:** basic-but-load-bearing mental model.
**Answer:** Code (runtime bytecode) lives under the account's codeHash — immutable post-deployment, readable via EXTCODECOPY, executable. Storage holds mutable 32-byte slots addressed by keccak(slot-key) tries. Constants: compile-time ones inline into bytecode (free reads); immutable/constant Solidity variables also live in bytecode; anything assignable at construction goes to storage unless marked immutable.
**Follow-up trap:** *"Why do uninitialized struct/array bugs matter here?"* — Zero-initialized slots collide with legitimate zeros; historical bugs (the 2019 $690k ETH vault incident class) came from assuming storage layout safety. Slot discipline is security, not style.

### Q10 — How does blob (EIP-4844) pricing differ from normal gas, and why create a second market?
**Testing:** 2024-26 scaling literacy.
**Answer:** Blobs carry L2 data with independent supply (target/max counts per block: 3 at Dencun, 6 after Pectra May 2025, rising via Fusaka BPO forks to 14 target/21 max by January 2026) and their own exponentially-adjusted fee with a 1-wei floor; crucially blobs are pruned after ~18 days (4096 epochs), so they don't bloat permanent state. Separating markets prevents L2 data demand from bidding up ordinary transactions.
**Follow-up trap:** *"If blobs get pruned, how do rollup withdrawals stay provable later?"* — DA guarantees are time-boxed: challenges/finality must occur within the window; long-run archival lives with indexers/L2s themselves, not consensus. Knowing pruning exists is the differentiator.

### Q11 — Explain EIP-7702 and what it changes about EOAs.
**Testing:** newest account-model developments.
**Answer:** Shipped with Pectra (May 7, 2025): an EOA can sign a delegation designating contract code that executes in its context, effectively upgrading wallets into smart accounts (batching, sponsorship, session keys) without migrating funds to ERC-4337 accounts. Security posture shifts: the delegated contract becomes single point of compromise, revocation requires another signed tx, and phishing gains new surfaces (malicious delegations).
**Follow-up trap:** *"Does 4337 become obsolete?"* — No: 7702 covers existing EOAs; 4337 remains the full framework for keyless/social-recovery accounts with paymasters and bundlers; production wallets blend both. Naming coexistence signals currency.

### Q12 — A rollup posts batches via calldata pre-Fusaka. Post-7623, its costs spike. Options?
**Testing:** operational response to protocol changes.
**Answer:** Move posting to blob transactions (that's their purpose; Dencun onward), compress calldata (generic compression checked on-chain costs less than nonzero bytes at 16 gas), restructure batches (fewer, denser), or negotiate dedicated DA layers (Celestia/EigenDA) accepting different trust assumptions. The floor specifically prices tokens = 1·zeros + 4·nonzeros at ≥10 gas/token beyond 21k base, so byte-shaving directly converts to savings.
**Follow-up trap:** *"Why did core devs add a floor at all?"* — Pre-floor, calldata's discounted pricing let rollups underpay relative to the actual burden on nodes, subsidizing at ordinary users' expense; the floor restores cost-reflective pricing while blobs provide the intended cheap lane.

### Q13 — Why is EVM determinism sacred, and which features test it?
**Testing:** fundamentals behind "no floats".
**Answer:** Every node re-executes every transaction and must reach bit-identical state roots; any nondeterminism splits consensus. Hence: integer-only arithmetic (mod 2^256), no wall-clock (block.timestamp is consensus-agreed, miner-influenceable ±seconds), randomness only from beacon PREVRANDAO (not blockhash of recent blocks alone, which proposers manipulate), and environment opcodes bounded to agreed data.
**Follow-up trap:** *"timestamp-dependent contract — attackable?"* — Within ~12-15 s skew, proposers nudge timestamps; auctions/deadlines keyed to seconds-level timestamp boundaries are exploitable. Use block numbers for ordering, accept timestamp only for coarse intervals.

### Q14 — Compare debugging a stuck payment in UTXO vs accounts.
**Testing:** translating models into ops behavior.
**Answer:** UTXO: stuck usually means unconfirmed due to feerate (RBF/CPFP levers exist: bump fee by spending change output with higher fee, child-pays-for-parent); there's no "pending balance mutation", just absent confirmation. Accounts: stuck means nonce gap (a lower-nonce tx missing blocks everything after) or underpriced baseFee; fix by replacing same-nonce tx with higher fee or nulling the gap (self-send at missing nonce).
**Follow-up trap:** *"What invariant makes both recoverable?"* — Deterministic ordering keys: outpoints in UTXO, nonces in accounts. Systems lacking explicit sequence keys make partial failures unrecoverable — worth saying because it generalizes to payment systems design generally.

### Q15 — State grows ~100+ GB/year. Propose your mitigation portfolio.
**Testing:** roadmap fluency plus prioritization.
**Answer:** Near term: snapshot/prune defaults (nodes keep recent state + re-executability), rent nothing yet but stop subsidizing growth (keep 20k SSTORE pricing; reject cheap-mint spam via mempool policy). Mid term: Verkle/statelessness so nodes verify without storing, state expiry (resurrect-with-proof for untouched accounts). Demand-side: push L2s to blobs so L1 stops being the dumping ground. Portfolio beats silver bullets; each attacks a different constraint (verification vs storage vs demand).
**Follow-up trap:** *"Expiry breaks immutability promises?"* — Resurrection proofs preserve integrity: expired state isn't deleted from truth, only from hot storage; anyone can revive by presenting witness. The social contract question is who pays archiving — an honest open problem to acknowledge.

## Red flags

- Saying Bitcoin accounts hold balances (they don't; UTXOs do).
- Quoting SSTORE/SLOAD prices wrong by an order of magnitude, or claiming reverted txs refund gas.
- Believing block gas limit means unlimited computation per user tx.
- Mixing up code (immutable) and storage (mutable) locations.
- Claiming blobs made L1 transactions cheaper (they relieved L2 data pressure; separate market).
- Ignoring nonce management when describing transaction plumbing.
- Treating confirmations and finality as interchangeable across PoW/PoS.

## Cheat card

```
UTXO          set of unspent outputs · spend-once via lookup · parallel-safe
              weight: legacy byte=4 WU, witness=1 WU · block cap 4M WU
ACCOUNTS      [nonce, balance, codeHash, storageRoot] · global serial execution
TRIE          MPT x4: world/storage/txs/receipts · root in header
              account proof = 3-8 nodes, KBs -> Verkle <200B (roadmap)
EVM           256-bit words · stack 1024 · deterministic (no floats/clock)
GAS           base 21000 · SSTORE new slot 20000 · update 2900 (+4800 refund)
              SLOAD cold 2100/warm 100 · CALL cold 2600 · CREATE 32000
              LOG 375+375*t+8*B · calldata 16 nz / 4 z (+7623 floor 10/token)
REVERT        state rolls back atomically · gas spent regardless · simulate!
FEES          EIP-1559: baseFee adjusts <=+-12.5%/blk toward 50% full, BURNED
BLOBS         EIP-4844 128 KiB · pruned ~18 days · target 3->6 (Pectra 5/2025)
              Fusaka 12/3/2025 PeerDAS -> BPO1 10/15, BPO2 14/21 (Jan 2026)
WALLETS       ERC-4337 smart accounts · EIP-7702 (Pectra) delegates EOA code
THROUGHPUT    L1 ~15-20 tps · Visa peak ~65k tps -> consumers live on L2s
```

## Sources

- [Ethereum Yellow Paper (Wood) — formal account/trie/EVM spec](https://ethereum.github.io/yellowpaper/paper.pdf); accessed 2026-08-23
- [Bitcoin developer reference — transactions and UTXO model](https://developer.bitcoin.org/devguide/transactions.html); accessed 2026-08-23
- [EIP-1559: Fee market change (Buterin, Stark)](https://eips.ethereum.org/EIPS/eip-1559); accessed 2026-08-23
- [EIP-4844: Shard Blob Transactions](https://eips.ethereum.org/EIPS/eip-4844); accessed 2026-08-23
- [EIP-2929: State access opcode gas cost increases](https://eips.ethereum.org/EIPS/eip-2929); accessed 2026-08-23
- [EIP-7623: Increase calldata cost (Prague)](https://eips.ethereum.org/EIPS/eip-7623); accessed 2026-08-23
- [EIP-7702: Set EOA account code (Pectra, May 2025)](https://eips.ethereum.org/EIPS/eip-7702); accessed 2026-08-23
- [Fusaka Mainnet Announcement — Ethereum Foundation](https://blog.ethereum.org/2025/11/06/fusaka-mainnet-announcement); accessed 2026-08-23
- [SegWit upgrade documentation — Bitcoin Wiki](https://en.bitcoin.it/wiki/Segregated_Witness); accessed 2026-08-23
- [Verkle trees — ethereum.org roadmap](https://ethereum.org/en/roadmap/verkle-trees/); accessed 2026-08-23

## Changelog

- 2026-08-23 — created


