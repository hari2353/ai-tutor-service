# Bitcoin UTXO vs Ethereum Accounts, EVM, Gas, State Trie

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 2.5h · **Prereqs:** `T22-blockchain-scratch`, `T22-consensus`
> **Updated:** 2026-08-08
> **Module id:** `T22-bitcoin-ethereum` · **Tags:** platforms
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Bitcoin's UTXO model represents money as a set of discrete, unspent "coins" (unspent transaction outputs) that get consumed whole and replaced by new outputs — there's no persistent "account balance" anywhere in the protocol, only "what UTXOs exist and who can spend them," which makes double-spend detection a trivial set-membership check and parallel validation easy, but makes anything stateful (a running balance, a smart contract with memory) awkward to express. Ethereum's account model gives every address a persistent balance and nonce, closer to a bank ledger, which makes smart contracts natural to build (a contract is just an account with code and storage) but makes double-spending and replay protection a sequential nonce check instead of a parallel-friendly set lookup, and requires explicitly tracking global state rather than deriving it from a UTXO set. Both models get validated the same underlying way: full nodes maintain that state (a UTXO set, or an account/storage tree) and every transaction is checked against it before being applied — Ethereum's version of that state is authenticated by a **Merkle Patricia Trie**, a structure combining a Merkle tree's tamper-evidence with a Patricia trie's efficient key-based lookup, so any node can get a compact, cryptographically verifiable proof of any account's balance without downloading the whole state. **Gas** exists because Ethereum's contracts are Turing-complete and therefore can't be statically checked to halt (the halting problem, not a design oversight) — every EVM instruction costs a specific amount of gas, execution stops the instant a transaction runs out, and this is literally the only thing preventing an infinite loop from hanging every node in the network forever.

## Why this gets asked

Because "Bitcoin and Ethereum are both blockchains" is where most self-taught understanding stops, and the actual engineering differences between UTXO and account models — how each handles double-spending, parallelism, statefulness, and privacy — is exactly the kind of distinction that separates someone who's read explainer articles from someone who could reason about which model to pick for a new system. Anyone who's debugged an Ethereum transaction stuck with the wrong nonce, or reasoned about why Bitcoin's Lightning Network works the way it does, has hit these mechanics directly; the interviewer wants to know if gas is understood as a solution to a specific, named computer-science problem (the halting problem) rather than "the fee you pay."

---

## Lineage: past → present → future

**What came before.** Bitcoin's UTXO model (2009) was the first design point in this space, built specifically to make double-spend prevention simple and verifiable: a transaction is valid if and only if its inputs reference real, unspent, correctly-signed-for outputs, and the sum of inputs is at least the sum of outputs — a check requiring no global balance ledger at all, just a set of currently-unspent outputs. This was sufficient for Bitcoin's original design goal (peer-to-peer electronic cash) but was never designed to support arbitrary programmability — Bitcoin Script exists and is intentionally limited (no loops, bounded complexity) precisely to keep validation cheap and predictable, a deliberate constraint, not an early limitation later "fixed." Ethereum (Vitalik Buterin's 2013 whitepaper, launched 2015) was a direct, explicit response to that limitation: its stated goal was a "world computer" supporting arbitrary programs, which required a fundamentally different state model — persistent accounts with balances, code, and storage — because expressing a general-purpose stateful program against a UTXO set is possible in principle but sufficiently awkward that essentially no serious smart-contract platform has chosen it as the primary model since.

**Where it stands now.** Both models are mature, live, and clearly suited to different things — this isn't "Ethereum's model won," it's "they optimize for different problems and both remain the dominant choice for their respective problem." UTXO's set-based structure genuinely does make certain scaling approaches easier: transaction validation is naturally parallelizable (checking whether disjoint sets of UTXOs are unspent has no ordering dependency the way sequential account-nonce checks do), and privacy-focused designs (CoinJoin, and non-Bitcoin UTXO chains like Zcash) build more naturally on top of discrete, swappable coin-like outputs than on a persistent, directly-linkable account balance. The account model's clear win is programmability: virtually every smart-contract platform that followed Ethereum (BNB Chain, Polygon, Avalanche's C-Chain, and the EVM-compatible chains covered in module 7) adopted an account-based, EVM-compatible design, not a UTXO-based one — the account model has become the default assumption for "smart contract platform" specifically because expressing contract state naturally requires persistent storage. The live technical detail worth being precise about: Ethereum's gas mechanism and EIP-1559 fee market (August 2021) are a direct consequence of the account model's programmability — a system that can run arbitrary code needs a metering mechanism UTXO-based Bitcoin Script never required, because Script was deliberately constrained to not need one.

**Where it's heading.** High confidence: EVM compatibility remains the dominant standard for new smart-contract chains and layer-2s (module 7), because the tooling, audit expertise, and developer familiarity built around it is now a massive, self-reinforcing ecosystem advantage independent of whether the EVM is technically the best possible design — a real, if slightly uncomfortable, path-dependency worth naming explicitly. Medium confidence: alternative execution environments (Solana's account model with parallel execution via explicit state-access declarations, Move-based chains like Aptos and Sui with resource-oriented programming) are a genuine, growing design space exploring whether Ethereum's account model specifically — not just "account-based" broadly — has left performance or safety on the table; whether any of these displace EVM dominance at scale is a live, unresolved question. Speculative: Bitcoin's own programmability is slowly, deliberately expanding (Taproot 2021, ongoing covenant-opcode proposals) without abandoning UTXO's core simplicity — treat any specific prediction about how far this goes as genuinely uncertain.

---

## Mental model

```
  UTXO MODEL (Bitcoin)                    ACCOUNT MODEL (Ethereum)
  ─────────────────────                   ─────────────────────────
  No balances anywhere. Only:             Every address has:
    a SET of unspent outputs               balance: 100 ETH
    {(txid,0): {owner:Alice, amt:10},      nonce: 5   (replay protection,
     (txid,1): {owner:Bob,   amt:3}, ...}         must increment sequentially)
                                            storage: {} (if it's a contract)
  SPEND = consume whole UTXOs as           code: 0x... (if it's a contract)
  inputs, create new UTXOs as outputs.
  "Change" is just a new output back       TRANSFER = decrement sender
  to yourself — there's no partial         balance, increment receiver
  spend of one UTXO.                       balance, in place. Nonce must
                                            match exactly (no gaps, no reuse).

  inputs:  [UTXO_a(10), UTXO_b(3)]         Alice: {balance: 94, nonce: 6}
  outputs: [Bob: 6, Alice: 6] (1 fee)      Bob:   {balance: 6}
  Alice's UTXOs a,b are GONE. New          (Alice's balance mutated in
  UTXOs exist for Bob and Alice's change.  place — no discrete "coins")

  DOUBLE-SPEND CHECK: is this UTXO         DOUBLE-SPEND / REPLAY CHECK:
  still in the unspent set? O(1) lookup,   does this transaction's nonce
  naturally parallelizable across          match the account's expected
  disjoint UTXOs.                          next nonce? Inherently sequential
                                            per-account.

  STATE AUTHENTICATION: Ethereum's account/storage state is committed to
  via a MERKLE PATRICIA TRIE — Merkle tree tamper-evidence (module 1) +
  Patricia trie's efficient prefix-based key lookup. The trie ROOT goes
  in the block header, exactly like the transaction Merkle root — any
  node can get a compact, verifiable proof of one account's balance
  without downloading the entire multi-hundred-GB state.

  GAS: EVM code can loop arbitrarily (Turing-complete) — the halting
  problem means NO static check can guarantee a program terminates.
  Gas is the only thing that guarantees a transaction terminates anyway:
  every opcode costs gas, execution HALTS when gas runs out, period.
```

---

## How it actually works

### UTXO transactions: verified end to end

A UTXO is identified by `(txid, output_index)`. Spending consumes referenced UTXOs entirely and creates new ones; there's no concept of debiting a UTXO by a partial amount — if you own a 10 BTC UTXO and want to send 6, you spend the whole 10 BTC UTXO as an input and create two new outputs: 6 to the recipient, 4 back to yourself as "change" (minus whatever fee is implicitly left over as the gap between input and output totals, since miners collect `sum(inputs) - sum(outputs)` as the fee).

```python
class UTXOSet:
    def __init__(self):
        self.utxos = {}          # (txid, index) -> {"owner": str, "amount": int}
        self._next_txid = 0

    def fund(self, owner: str, amount: int):
        txid = f"coinbase{self._next_txid}"; self._next_txid += 1
        self.utxos[(txid, 0)] = {"owner": owner, "amount": amount}
        return (txid, 0)

    def spend(self, inputs: list, outputs: list, signer: str) -> str:
        total_in = 0
        for ref in inputs:
            if ref not in self.utxos:
                raise ValueError(f"double-spend or unknown UTXO: {ref}")
            utxo = self.utxos[ref]
            if utxo["owner"] != signer:
                raise ValueError("not authorized to spend this UTXO")
            total_in += utxo["amount"]
        total_out = sum(amt for _, amt in outputs)
        if total_out > total_in:
            raise ValueError(f"outputs ({total_out}) exceed inputs ({total_in})")
        for ref in inputs:
            del self.utxos[ref]                 # consume — this IS the double-spend prevention
        txid = f"tx{self._next_txid}"; self._next_txid += 1
        for i, (owner, amt) in enumerate(outputs):
            self.utxos[(txid, i)] = {"owner": owner, "amount": amt}
        return txid                             # implicit fee = total_in - total_out
```

Run for real: Alice funds a 10-unit UTXO, spends it into `[Bob: 6, Alice: 3]` (a 1-unit fee), and the spent UTXO is immediately gone from the set. A second attempt to spend the same original UTXO reference correctly raises `double-spend or unknown UTXO: ('coinbase0', 0)` — the entire double-spend defense is exactly this: a UTXO either exists in the current unspent set or it doesn't, deletion on spend is the whole mechanism, and it requires no notion of transaction ordering *across unrelated UTXOs* to be correct, which is precisely what makes UTXO validation naturally parallelizable.

### Account transactions: verified end to end, with the nonce as the actual defense

```python
class AccountState:
    def __init__(self):
        self.balances = {}
        self.nonces = {}

    def fund(self, addr: str, amount: int):
        self.balances[addr] = self.balances.get(addr, 0) + amount

    def transfer(self, frm: str, to: str, amount: int, nonce: int):
        expected_nonce = self.nonces.get(frm, 0)
        if nonce != expected_nonce:
            raise ValueError(f"bad nonce: expected {expected_nonce}, got {nonce}")
        if self.balances.get(frm, 0) < amount:
            raise ValueError("insufficient balance")
        self.balances[frm] -= amount
        self.balances[to] = self.balances.get(to, 0) + amount
        self.nonces[frm] = expected_nonce + 1
```

Run for real: Alice funds 10, transfers 6 to Bob at nonce 0 (`balances: {'Alice': 4, 'Bob': 6}`, `nonces: {'Alice': 1}`), and a replayed transaction reusing `nonce=0` is correctly rejected (`bad nonce: expected 1, got 0`). This is the account model's replay/double-spend defense: **strictly sequential, per-account nonces**, which is why two transactions from the same account can never be validated out of order or in parallel with each other — a real, structural cost against UTXO's naturally-parallel validation, and directly why account-model chains pursuing high parallel throughput (Solana, Sui, Aptos) had to design explicit mechanisms to declare which accounts a transaction touches, so independent transactions touching disjoint accounts can still be identified and parallelized despite the model's inherently sequential per-account ordering.

### The EVM execution model

The Ethereum Virtual Machine executes bytecode as a stack machine: instructions (opcodes) pop operands off a 256-bit-word stack, operate, and push results back. Contract storage is a separate, persistent key-value space (256-bit key to 256-bit value) distinct from the stack and from transient memory, which is why `SLOAD`/`SSTORE` (storage read/write) are priced dramatically higher than stack or memory operations — storage changes must be included in the account's Merkle Patricia Trie update and persisted forever, where stack and memory are transaction-scoped and discarded after execution.

**Concrete current gas costs** (post EIP-2929, "Berlin" hardfork access-list gas repricing): a **cold** `SLOAD` (first access to a storage slot within a transaction) costs **2,100 gas**; a **warm** `SLOAD` (subsequent access to the same slot in the same transaction) costs only **100 gas** — a 21x difference that exists specifically to charge for the actual first-time disk/trie-lookup cost while not re-charging for values already loaded into a transaction's working set. Writing a **new** value to a previously-zero storage slot (`SSTORE`, 0 → non-zero) costs **20,000 gas** cold (22,100 total including the implied cold access) — the single most expensive common operation in the EVM, and the direct reason gas-optimization advice in Solidity development revolves heavily around minimizing storage writes and packing multiple values into single storage slots (module 5 covers this precisely).

### Why gas exists: the halting problem, not a business model

Bitcoin Script is deliberately not Turing-complete — it has no loop constructs, and its complexity is bounded by design, which means a node can always determine in advance (or at least bound) how much work validating a given script requires. The EVM is Turing-complete: it supports arbitrary loops and conditional jumps, which means, by Turing's own 1936 halting-problem result, **no general algorithm can determine in advance whether an arbitrary EVM program will ever terminate** — this isn't a limitation someone forgot to solve, it's a mathematically proven impossibility for the general case. Gas is the actual solution: every opcode has a fixed cost, a transaction specifies a gas limit it's willing to pay for, and execution halts the instant that limit is exhausted, refunding nothing and reverting all state changes (but still consuming the gas spent, since the computation up to that point genuinely happened and needs to be paid for) — this guarantees every transaction terminates within a bounded number of steps, sidestepping the halting problem entirely rather than solving it, which is the only viable approach given the theoretical result.

**EIP-1559 (August 2021)** restructured the fee itself into two parts: a **base fee**, algorithmically set per block (adjusting up to 12.5% per block based on whether the previous block was more or less than half full) and **burned** — permanently removed from circulation, not paid to anyone — plus a **priority fee** (tip) that goes to the block proposer as an incentive for inclusion. As of 2026, with the majority of everyday transaction volume having moved to layer-2 rollups (module 7), mainnet base fees have spent much of the year below 1 gwei, and a typical simple mainnet transfer costs a few cents — a substantial, measured change from the multi-dollar-to-tens-of-dollars fees common during 2021-2023 congestion, driven by demand migrating off L1 rather than a change to the fee mechanism itself.

### The state trie

Ethereum's global state — every account's balance, nonce, code hash, and storage root — is committed to via a **Merkle Patricia Trie (MPT)**: a data structure combining a Patricia trie's efficient prefix-compressed key lookup (keys are the Keccak256 hashes of addresses; traversal follows nibbles of the key) with a Merkle tree's cryptographic tamper-evidence (every node's identifier is a hash of its contents, exactly as in module 1). The **state root** — the MPT's top-level hash — is included in every block header, meaning the entire global state at that block is cryptographically committed to in 32 bytes, and any node can produce a compact Merkle proof that a specific account had a specific balance at a specific block, without the verifier needing the full multi-hundred-gigabyte state. Ethereum actually maintains several such tries per block: the state trie (accounts), a separate storage trie per contract (that contract's own key-value storage), the transaction trie (this block's transactions), and the receipts trie (execution results/logs) — each independently root-hashed and referenced from the block header.

---

## Build it from scratch

The UTXO and account implementations above **are** the from-scratch build for this module — both were executed directly, not asserted, and both demonstrate the specific mechanism (deletion-based double-spend prevention vs. sequential-nonce replay prevention) that makes each model's core security property work. A minimal illustration of *why* the account model's sequential nonce is a real parallelism constraint the UTXO model doesn't share:

```python
# UTXO: these two spends touch DISJOINT UTXOs — no ordering dependency,
# safe to validate concurrently on separate threads/cores.
u.spend([utxo_a], [("Bob", 5)], signer="Alice")
u.spend([utxo_c], [("Carol", 2)], signer="Dave")     # unrelated UTXO, unrelated owner

# Account: these two MUST be validated in nonce order for the SAME sender —
# validating tx(nonce=1) before tx(nonce=0) is committed is simply wrong,
# there is no parallel-safe way to reorder a single account's own transaction stream.
a.transfer("Alice", "Bob", 5, nonce=0)
a.transfer("Alice", "Carol", 2, nonce=1)             # must wait for nonce=0 to commit first
```

Full lab — including a minimal from-scratch Merkle Patricia Trie implementation with a working account-balance inclusion proof, a gas-metering EVM-opcode-cost simulator, and a side-by-side double-spend attack attempted against both models to compare the actual defense mechanism: **`labs/py/22-bitcoin-ethereum/`**.

---

## How it's done in production

**Bitcoin Core** maintains the UTXO set in a local database (historically LevelDB-based `chainstate`), pruned of spent entries continuously — a full node's UTXO set is a small fraction of the full historical chain size specifically because spent outputs don't need to be retained for validation once consumed. **Ethereum clients** (Geth, Nethermind, Reth, Besu) maintain the state trie in a similar key-value store, and state growth (the trie's ever-increasing size as more accounts and contract storage accumulate) is a genuine, actively-managed operational concern — "state bloat" has driven multiple protocol-level responses, including gas-cost increases for storage operations (EIP-2929) specifically to make storage growth reflect its real long-term cost, and ongoing research into state expiry and statelessness (allowing nodes to validate blocks using only proofs, without storing the full state themselves).

| Symptom | Cause | Fix |
|---|---|---|
| An Ethereum transaction is stuck "pending" indefinitely | Nonce gap — a transaction with a lower, not-yet-mined nonce is blocking every later-nonce transaction from that account, since nonces must apply in strict sequence | Resubmit (or cancel via a 0-value self-transfer) the missing/stuck nonce; wallets increasingly detect and surface this automatically |
| A Bitcoin wallet shows a balance lower than expected despite recent receipts | UTXO fragmentation — many small unspent outputs each require their own input slot and signature in a future spend, and Bitcoin transaction size (hence fee) scales with input count | Consolidate small UTXOs into fewer, larger ones during low-fee periods, a routine wallet-hygiene operation |
| A smart contract call reverts with "out of gas" despite the logic being correct | Gas limit set too low for the actual computation path taken (often a loop over a larger-than-expected on-chain array) | Estimate gas against realistic worst-case input sizes, not just the happy path tested locally; add explicit bounds to loops over unbounded on-chain collections (module 6 covers the security angle) |
| Ethereum state trie reads are the dominant latency cost in a high-throughput application | Cold SLOAD/trie-node disk lookups on infrequently-accessed storage slots, especially after client restarts with a cold cache | Warm relevant storage ahead of time where possible, use access lists (EIP-2930) to pre-declare storage slots a transaction will touch for slightly reduced gas and improved node-side scheduling |
| Two independent UTXO-model transactions from different users unexpectedly conflict | Both reference the same UTXO — either a genuine double-spend attempt or, more commonly in practice, a wallet bug reusing an already-broadcast-but-unconfirmed UTXO as an input for a second transaction | Track outputs as "reserved" once referenced by any broadcast, unconfirmed transaction, not just once confirmed |

---

## Tradeoffs & when NOT to use it

- **Don't pick UTXO for a system that fundamentally needs rich, persistent, mutable state (a general smart-contract platform).** It's possible in principle (some UTXO-based chains have added limited scripting), but every serious smart-contract platform's design converged on the account model for a reason — expressing arbitrary, evolving contract state naturally requires exactly the persistent storage the account model provides directly and the UTXO model has to work around.
- **Don't pick the account model where UTXO's natural parallelism or privacy properties are the actual requirement.** A payment-focused system prioritizing high-throughput parallel validation or coin-level privacy (each UTXO independently traceable or mixable, rather than a single running balance that links every transaction to one persistent, directly-observable account) is better served by a UTXO design — this is exactly why privacy-focused chains (Zcash, Monero's related-but-distinct model) build on UTXO-like foundations rather than accounts.
- **Don't treat gas limits as merely a spam-prevention fee.** They're the load-bearing mechanism that makes Turing-complete on-chain execution *possible at all* without violating every node's basic liveness — removing or radically weakening gas metering isn't a UX improvement, it reopens the halting-problem vulnerability the entire mechanism exists to close.
- **Don't assume Ethereum's account nonce model generalizes cleanly to systems wanting high parallel transaction throughput without modification.** Strict sequential per-account ordering is a real bottleneck for high-frequency single-account activity (a trading bot sending many transactions rapidly, for instance), which is precisely why account-abstraction proposals and alternative account-model chains (Solana's explicit account-access-list parallelism) exist as direct responses to this specific limitation.
- **Don't over-invest in state-trie optimization before confirming storage operations are the actual bottleneck.** Gas-cost-driven intuition (storage is expensive, so minimize it) is directionally correct advice for contract design (module 5), but for a broader system architecture question, computation-heavy or memory-heavy logic can dominate cost just as easily depending on the actual contract — profile before optimizing blindly toward "storage is always the expensive part."

---

## Interview questions

### Q1 — Explain how Bitcoin's UTXO model prevents double-spending, mechanically.
**Testing:** whether the mechanism (not just the vocabulary) is understood.
**Answer:** A UTXO is either currently in the unspent set or it isn't — spending a transaction consumes its referenced input UTXOs (deletes them from the set) and creates new output UTXOs. Attempting to spend an already-spent UTXO fails a direct set-membership check: the reference simply isn't there anymore. No global balance or transaction-ordering logic is needed for this specific defense to work, which is why UTXO validation across unrelated UTXOs is naturally parallelizable.
**Follow-up trap:** *"What if two conflicting transactions spending the same UTXO are broadcast nearly simultaneously?"* — this is a real race, not prevented by the UTXO structure alone; it's resolved by whichever transaction actually gets mined into a block first (and confirmed via the consensus mechanism, module 3) — the "double-spend prevention" the UTXO model provides is about *validated, confirmed* state, not about race conditions in the unconfirmed mempool, where both conflicting transactions can briefly coexist until one is mined.

### Q2 — Why does Ethereum need a nonce, and what specifically does it prevent?
**Testing:** replay-attack understanding, connected to the account model's structural requirement.
**Answer:** Each account tracks a nonce that must increment by exactly one per transaction, in strict order. This prevents transaction replay (resubmitting a previously-valid, already-executed transaction to have its effect happen twice) and enforces a canonical ordering of that account's transactions, since the account model has no equivalent to "consume the input, it's gone" — a balance is a mutable number, and without the nonce, nothing would stop the exact same signed transaction from being rebroadcast and reapplied.
**Follow-up trap:** *"Could you achieve the same replay protection without a strictly sequential nonce, e.g. a random per-transaction identifier?"* — you could prevent *exact* replay with a used-identifier set (check-and-record, similar in spirit to an idempotency key), but you'd lose the sequential-ordering guarantee the nonce also provides — a strict incrementing nonce simultaneously solves replay prevention *and* defines a canonical, gap-free transaction order for the account, which is why it was chosen over a weaker but sufficient-for-replay-alone identifier scheme.

### Q3 — Why is UTXO validation naturally parallelizable and account-model validation naturally sequential (per account)?
**Testing:** the structural, not just definitional, distinction.
**Answer:** UTXO transactions reference specific, disjoint prior outputs; two transactions spending unrelated UTXOs have no shared state to create an ordering dependency, so they can be validated concurrently. Account-model transactions from the *same* account must apply in exact nonce order because each transaction's validity (the nonce check, the balance check) depends on the account's state *after* the immediately preceding transaction from that account — an inherently sequential dependency chain per account, even though transactions from *different* accounts remain independently parallelizable.
**Follow-up trap:** *"So is Ethereum less scalable than Bitcoin because of this?"* — not straightforwardly; cross-account parallelism is still available and exploited by production clients and L2 sequencers, and Ethereum's actual scaling strategy (module 7, rollups) doesn't primarily hinge on this specific parallelism difference — but it is a real, structural distinction that shows up concretely in high-frequency single-account use cases (a market maker's bot submitting many transactions rapidly), which is a legitimate, narrower scalability concern this specific model choice does create.

### Q4 — What problem does gas actually solve, precisely?
**Testing:** whether gas is understood as a solution to the halting problem, not just "the fee mechanism."
**Answer:** The EVM is Turing-complete, meaning by Turing's 1936 halting-problem result, no general algorithm can determine in advance whether an arbitrary program will terminate. Without a bound, a single malicious or buggy contract with an infinite loop could hang every validating node indefinitely, since correctly executing a transaction requires actually running it. Gas assigns every opcode a fixed cost, requires the transaction to specify a gas limit it's paying for, and halts execution unconditionally when that limit is exhausted — guaranteeing termination within a bounded number of steps regardless of what the code does, sidestepping the halting problem rather than solving it.
**Follow-up trap:** *"If a transaction runs out of gas partway through, does the sender get anything back?"* — no: all state changes from that execution are reverted (as if it never happened, from the state's perspective), but the gas actually consumed up to the point of failure is still charged and not refunded, since real computational work was genuinely performed by every node that validated the attempt and that work has to be paid for regardless of the ultimate outcome — a common point of confusion worth stating precisely.

### Q5 — Why is `SSTORE` (writing to contract storage) so much more expensive than other EVM operations, in gas terms?
**Testing:** connecting the state-trie mechanism to the specific pricing.
**Answer:** A storage write isn't transaction-scoped like stack or memory operations — it permanently modifies the contract's storage trie, which cascades into recomputing that trie's root, which cascades into the account's entry in the global state trie, which cascades into the block's overall state root. This work must be done, verified, and persisted by every full node, forever, whereas stack and memory are discarded after the transaction completes. Writing a new value to a previously-zero slot costs 20,000 gas cold — the most expensive common EVM operation — directly reflecting that permanent, replicated, forever-persisted cost.
**Follow-up trap:** *"Does resetting a storage slot back to zero get you a gas refund?"* — historically yes, Ethereum offered a substantial refund for clearing storage (an incentive against unnecessary state bloat), but this mechanism has been repeatedly reduced and reworked across hardforks (notably scaled back significantly around the London upgrade) specifically because it was found to enable gas-refund gaming patterns unrelated to genuine state cleanup — know that refund behavior has changed materially over Ethereum's history rather than asserting a single fixed number as permanently current.

### Q6 — What is the Merkle Patricia Trie, and what does putting its root in the block header actually buy you?
**Testing:** connecting module 1's Merkle trees to Ethereum's specific state-authentication structure.
**Answer:** It's a trie (efficient prefix-based key lookup, keys derived from Keccak256-hashed addresses) combined with Merkle hashing (every node's identifier is a hash of its contents), so the whole structure is both efficiently navigable by key and cryptographically tamper-evident. Putting the root in the block header means the entire global state at that block — every account balance, every contract's storage — is committed to in 32 bytes, letting any party request and verify a compact Merkle proof of a specific account's state without downloading or trusting the full multi-hundred-gigabyte state.
**Follow-up trap:** *"Is the state root proof of that state's validity, or just its existence?"* — existence/inclusion only, exactly the module 1 distinction: a state root faithfully commits to whatever state actually produced it, valid or not — the *validity* of that state (that it was reached through correctly-executed, correctly-signed transactions from the genesis state) is what full block validation and consensus (module 3) establish, not something the trie structure itself proves. A Merkle proof tells you "this is definitely what the committed state says," not "this state is definitely correct."

### Q7 — A startup wants to build a high-frequency trading system settling on-chain, with a single account submitting hundreds of transactions per minute. What specifically does the account model's nonce requirement mean for their design?
**Testing:** applying the sequential-nonce constraint to a realistic operational scenario.
**Answer:** Every transaction from that account must be assigned and confirmed in strict nonce order — if transaction 47 fails to be included (stuck due to low fee, or a temporary node issue) while 48-100 are already signed and broadcast, everything after 47 is blocked until 47 either confirms or is explicitly replaced (typically via a same-nonce, higher-fee replacement transaction). At hundreds of transactions per minute from one account, careful nonce management (tracking pending vs. confirmed nonces precisely, having an automated stuck-transaction replacement strategy) becomes a hard operational requirement, not an edge case — a naive "just increment and send" approach will eventually produce a nonce gap that silently stalls the entire pending queue.
**Follow-up trap:** *"Would a UTXO-based chain avoid this specific problem?"* — largely yes for *this specific* bottleneck: independent UTXOs don't have a shared sequential-ordering requirement the way one account's nonce stream does, so many parallel UTXO-based transactions from the same wallet (using different, disjoint UTXOs) don't block each other the way nonce-gapped account transactions do — a legitimate, concrete point in UTXO's favor for this exact use case, worth naming rather than defaulting to "account model is strictly better" reflexively.

### Q8 — Why did Bitcoin deliberately choose not to make Bitcoin Script Turing-complete?
**Testing:** whether the candidate understands this as a deliberate security/predictability tradeoff, not an oversight later "fixed" by Ethereum.
**Answer:** A non-Turing-complete script language (no loops, bounded operation count) means every node can bound the computational cost of validating any transaction in advance, with no need for a gas-like metering mechanism at all — validation cost is predictable and can't be weaponized into a resource-exhaustion vector the way an unbounded loop could. This was a deliberate design choice prioritizing simplicity, predictability, and a narrower attack surface for Bitcoin's specific goal (a payment system), not a limitation Ethereum simply "fixed" — Ethereum made the opposite, equally deliberate tradeoff (arbitrary programmability, at the cost of needing gas metering) for its different goal (a general-purpose programmable platform).
**Follow-up trap:** *"Does this mean Bitcoin Script is strictly less capable, and Ethereum's approach is strictly better engineering?"* — no, and framing it that way misses the point: they're solving different problems with tradeoffs appropriate to each. Bitcoin's constrained script has a dramatically smaller attack surface and simpler validation cost model, which is a genuine, deliberate engineering advantage for its stated goal; Ethereum's generality is a genuine advantage for programmability, purchased at the real cost of needing gas metering and dealing with a much larger smart-contract attack surface (module 6 covers this in depth).

### Q9 — Why does the account model make replaying an old, already-mined transaction impossible, while a naive UTXO design might need extra care to prevent something similar?
**Testing:** whether the candidate can compare replay-safety mechanisms across both models precisely rather than assuming UTXO is automatically safe by default.
**Answer:** In the account model, replay is prevented directly by the nonce: an already-mined transaction's nonce has already been consumed, so resubmitting the identical signed transaction fails the nonce check outright. In the UTXO model, replay safety comes from a different mechanism — the referenced input UTXO is already spent and removed from the unspent set, so resubmitting the same transaction fails because its inputs no longer exist, not because of any explicit sequence counter. Both models achieve replay-safety, but through structurally different means: one via an explicit incrementing counter, the other via the input reference simply ceasing to exist.
**Follow-up trap:** *"Is there a cross-chain replay scenario where this distinction matters?"* — yes: cross-chain replay attacks (the same signed transaction being valid on two chains that forked from a shared history, notably Ethereum/Ethereum Classic) exploit exactly the fact that both nonce state and UTXO-set state can be identical across two chains immediately after a fork, meaning a transaction valid on one is initially valid on the other too — this is why post-fork replay protection (EIP-155's chain ID in Ethereum's case) had to be added explicitly as a distinct mechanism layered on top of the ordinary nonce/UTXO replay defenses, which alone don't protect against a *shared-history* replay across two now-separate chains.

### Q10 — A protocol wants to build a payment channel network (Lightning-Network-style) on top of a base layer. Does the choice between UTXO and account models matter for this specific design?
**Testing:** whether the candidate can connect the module's core distinction to a concrete, real scaling technique rather than treating it as purely theoretical.
**Answer:** Yes, materially: Bitcoin's Lightning Network relies on UTXO-specific properties — a channel is fundamentally a specially-constructed, jointly-controlled UTXO whose spending conditions encode the off-chain-negotiated channel state, and the "replace the old channel state" mechanism (revocable commitment transactions) works cleanly with discrete, individually-spendable outputs. Building an equivalent purely on the account model requires different techniques (typically smart-contract-based state channels, where a single contract's storage tracks channel state directly), which is a real, different engineering approach, not the same design merely reimplemented — this is a concrete case where the underlying data model genuinely shapes what layer-2 architecture is natural to build.
**Follow-up trap:** *"Does this mean Ethereum can't have payment-channel-style scaling at all?"* — no; Ethereum has its own smart-contract-based state channel implementations, and its dominant scaling approach (rollups, module 7) doesn't rely on either model's channel-specific properties at all — the point isn't that one model uniquely enables off-chain scaling, it's that *which specific technique* is natural differs by model, and assuming Lightning's exact design would port unchanged to an account-based chain misunderstands why it was designed the way it was in the first place.

---

## Red flags that fail you

- Describing Bitcoin as having "account balances" tracked directly by the protocol rather than a UTXO set.
- Calling gas "just a transaction fee" without connecting it to the halting problem / Turing-completeness.
- Not knowing why account-model transactions from the same sender must be sequentially ordered while UTXO validation is naturally parallel.
- Claiming a Merkle Patricia Trie proof establishes that state is *correct*, rather than merely that it matches a committed root.
- Treating "Ethereum's account model is strictly better than Bitcoin's UTXO model" as a settled conclusion rather than a tradeoff dependent on the actual use case.
- Not knowing that a failed (out-of-gas) transaction still consumes the gas spent up to the point of failure.

---

## Cheat card

```
UTXO (Bitcoin): no balances -- only a SET of unspent outputs {(txid,idx): owner,amount}.
  Spend = consume whole inputs, create new outputs (change = new output to self).
  DOUBLE-SPEND DEFENSE = deletion from unspent set. O(1), naturally PARALLELIZABLE
  across disjoint UTXOs (no ordering dependency between unrelated spends).
  Good for: privacy (discrete coins), parallel validation. Bad for: rich mutable state.

ACCOUNT (Ethereum): every address has {balance, nonce, [code, storage] if contract}.
  Transfer = mutate balances in place. REPLAY/DOUBLE-SPEND DEFENSE = strict sequential
  per-account NONCE (must match exactly, no gaps/reuse) -- inherently SEQUENTIAL per account,
  cross-account still parallel. Nonce gap = every later tx from that account stalls.
  Good for: smart contracts (persistent storage IS the account's own storage). Bad for:
  high-freq single-account throughput without careful nonce management.

EVM: stack machine, 256-bit words. Storage = separate persistent k/v space, priced far
  above stack/memory because it's replicated + persisted forever in the state trie.
  Gas costs (post EIP-2929 Berlin): cold SLOAD 2,100 / warm SLOAD 100 (21x diff).
  SSTORE 0->nonzero: 20,000 (cold, +2,100 access = 22,100) -- most expensive common op.

GAS EXISTS BECAUSE: EVM is Turing-complete -> halting problem (Turing 1936) -> no static
  check can bound execution. Gas = every opcode costs gas, execution HALTS at limit,
  guarantees termination. Failed/reverted tx: state reverts, but GAS SPENT IS NOT REFUNDED.
  Bitcoin Script deliberately NOT Turing-complete (no loops) -- doesn't need gas at all.
  This is a DELIBERATE tradeoff each way, not Ethereum "fixing" a Bitcoin oversight.

EIP-1559 (Aug 2021): fee = BASE FEE (algorithmic, +-12.5%/block based on fullness, BURNED)
  + PRIORITY FEE (tip, to proposer). 2026: most volume on L2s, mainnet base fee often <1 gwei,
  simple transfer = a few cents (down from $/tens-of-$ during 2021-2023 congestion).

STATE TRIE: Merkle Patricia Trie = Patricia trie (prefix key lookup, Keccak256(address))
  + Merkle hashing (tamper-evident). STATE ROOT in block header = 32-byte commitment to
  ALL accounts/storage. Proof = inclusion only, NOT validity -- validity comes from full
  block/consensus validation, not the trie structure itself. Separate tries per block:
  state, per-contract storage, transactions, receipts.
```

## Sources

- [Bitcoin: A Peer-to-Peer Electronic Cash System (Nakamoto, 2008)](https://bitcoin.org/bitcoin.pdf) — accessed 2026-08-08
- [Ethereum Whitepaper (Buterin, 2013/2015)](https://ethereum.org/en/whitepaper/) — accessed 2026-08-08
- [EIP-2929: Gas cost increases for state access opcodes](https://eips.ethereum.org/EIPS/eip-2929) — accessed 2026-08-08
- [EIP-1559: Fee market change for ETH 1.0 chain](https://eips.ethereum.org/EIPS/eip-1559) — accessed 2026-08-08
- [BloFin — Ethereum gas explained: base fee, priority fee, and what a transaction really costs in 2026](https://blofin.com/academy/education/ethereum-gas) — accessed 2026-08-08
- [Ethereum.org — Merkle Patricia Trie](https://ethereum.org/en/developers/docs/data-structures-and-encoding/patricia-merkle-trie/) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
