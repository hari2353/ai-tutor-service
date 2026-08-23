# Solidity From Scratch: Storage, Calls, Events, Upgradeability

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** T22-bitcoin-ethereum · **Updated:** 2026-08-23
> **Module id:** `T22-smart-contracts` · **Tags:** blockchain, solidity, critical

## The 30-second version

A smart contract is an account holding two things: immutable bytecode (the program) and a flat array of 32-byte storage slots (its memory), where the compiler packs small variables together sequentially and hashes mappings into slot-space. Four opcodes govern how contracts interact: `CALL` enters another contract's context entirely, `STATICCALL` forbids state changes, and `DELEGATECALL` executes foreign code *in your own storage context* — which is simultaneously the mechanism behind every upgradeable proxy and the single most dangerous opcode in the EVM. Events are append-only log entries costing roughly 375 gas plus 375 per topic versus 20,000 for a fresh storage write, visible only to off-chain indexers, and are the correct medium for anything you query rather than execute against. Upgradeability (transparent proxy, UUPS, beacon, diamond) all reduce to delegatecall plus a carefully-guarded implementation pointer, and each variant trades one hazard for another: storage collisions, uninitialized initializers, or admin-key compromise.

## Why this gets asked

Because these four subtopics are where senior Solidity engineers separate from tutorial graduates. Anyone can deploy an ERC-20; interviewers probe the layer below: why does adding a variable in the middle of your contract brick the proxy behind it (storage layout shifts), why did Parity lose 513,000 ETH to an uninitialized library (initializer defaults), when do you choose events over storage (cost and access-patterns math), and what exactly does `msg.sender` become through two hops of delegatecall (context propagation — the answer decides whether your auth check means anything). At principal level they add judgment questions: should this system be upgradeable at all, who holds the upgrade key, what does the timelock look like, and can you defend shipping immutable instead? Having lived through an upgrade gone wrong is practically a prerequisite for being asked about upgrades.

## Lineage

**What came before.** Ethereum's contract model arrived whole with the 2014-15 design: accounts carrying code, gas-metered execution, logs for events. Solidity (Christian Reitwiessner, Gavin Wood et al., first release 2014, production 2015-16) won the language war early despite rough edges its history still carries: the 2016 DAO exploit (3.6M ETH, ~$50-60M then) came from call-forwarded-gas reentrancy and split the community into the fork that became today's Ethereum; Parity's multisig freeze (July 2017, then November 2017 killing 513,000 ETH permanently) came from default-visible initializers and a suicide function on a shared library. Vyper emerged (2017) as the deliberate anti-Solidity: Pythonic syntax, fewer features, audit-friendly. Proxy engineering matured through pain: ad-hoc storage layouts collided until EIP-1967 standardized implementation slots (finalized 2019), UUPS (EIP-1822, 2019) moved upgrade logic into implementations, and the Diamond standard (EIP-2535, 2020) generalized to facet routing.

**Where it stands now.** Solidity ≥0.8 (December 2020) made arithmetic overflow revert by default, deleting a whole vulnerability class that once demanded SafeMath everywhere; custom errors (0.8.4) replaced reason-string `require`s at a fraction of the gas. The upgradeability consensus settled around UUPS-with-namespaced-storage: ERC-7201 (adopted 2023) derives storage namespaces from formula-hashed IDs so implementations never collide with proxy slots, and OpenZeppelin's tooling enforces layout compatibility checks in CI. Diamonds remain a niche power tool — flexible, complex, and implicated in several exploits through facet misconfiguration. Meanwhile the frontier moved past Solidity-as-usual: formal verification tooling (Certora, Halmos, Kontrol) runs against top TVL protocols, account abstraction (ERC-4337/EIP-7702) is relocating custody logic into contracts, and Move-derived languages sell resource-safety semantics as their headline difference.

**Where it's heading.** Three currents with different confidence. First, compilers are being rebuilt: the Slang effort targets a formally-specifiable Solidity front end, and via-IR compilation is now default-recommended for upgradeable systems because it stabilizes storage and codegen across versions — high confidence this becomes table stakes. Second, upgradeability itself is losing fashion among blue chips: the largest protocols increasingly ship immutable cores with parameterized admin surfaces, reserving full upgrade paths for fast-moving products — expect "immutable unless proven otherwise" to keep spreading. Third, speculative: cross-language standards (Solidity interfaces consumed by MoveVM chains, ZK-proof-verifying precompiles like the secp256r1 support landing in recent forks) hint at contracts whose guarantees come from cryptography and type systems rather than audit labor alone; direction real, timeline fuzzy.

---

## Mental model

```
        CONTRACT = RECORD PLAYER
        ┌───────────────────────────────────────────────┐
        │  BYTECODE  = the record (immutable program)   │
        │  STORAGE   = your vinyl shelf (mutable slots) │
        │                                               │
        │  CALL          borrow another room + their    │
        │                shelf; you're a visitor        │
        │  DELEGATECALL  play THEIR record on YOUR      │
        │                player, touching YOUR shelf    │  ← proxy magic
        │                (msg.sender/value unchanged!)  │  ← proxy danger
        └───────────────────────────────────────────────┘

EVENTS = the shop window: cheap public notes passersby
         (indexers, dashboards) read; contracts cannot.
```

Two anchors carry everything else. First, **storage is a giant array of 32-byte cells** addressed by slot number; the compiler assigns them deterministically from declaration order (packing adjacent small vars), and mappings/dynamic arrays derive their element addresses from `keccak(slot_index . key)` — so "where does my variable live" always has a computable answer, and "what happens if two contracts disagree about the answer" is precisely the proxy-collision bug class. Second, **delegatecall preserves caller context**: `msg.sender`, `msg.value`, and the storage pointer stay the caller's while the code is the callee's. Every upgrade pattern is a disciplined way of exploiting that; every delegatecall disaster is a failure of that discipline.

---

## How it actually works

### Storage layout, concretely

Slot assignment rules (Solidity default layout): state variables occupy slots in declaration order; values under 32 bytes pack right-to-left into the current slot when they fit; a new variable that would straddle a slot boundary starts a fresh slot. Mappings and dynamic arrays reserve one slot for bookkeeping (empty for mappings, length for arrays) with element k living at `keccak(abi.encode(key, slot))` / `keccak(slot . k)` respectively. Strings/bytes over 31 bytes store length×2+1 in the head slot and data at hashed offsets. Practical consequences with numbers:

```solidity
contract Packed {
    uint128 a;      // slot 0, bytes 0..15
    uint64  b;      // slot 0, bytes 16..23
    uint64  c;      // slot 0, bytes 24..31   <- three vars, ONE slot
    uint256 d;      // slot 1                  <- full word
    mapping(address => uint256) balances;  // slot 2 (reserved)
}
```

Writing `a` costs one SSTORE touching slot 0; writing `b` likewise — but reading `d` after `a` costs two cold SLOADs (2,100 each) versus one if both were warm. Packing five uint16 flags separately into five slots turns five 20k-gas writes into five 2.9k updates on one slot — the single highest-leverage optimization most audits flag first.

### ABI and selectors

Calling a contract means sending calldata whose first four bytes are the function selector: `bytes4(keccak256("transfer(address,uint256)"))`. Arguments follow in 32-byte words; dynamic types (arrays, bytes, strings) append their data and place offsets in-line. Two consequences interviewers love: selectors collide occasionally across functions with argument-count tricks (the historical ERC-20 short-address and proxy selector-clash incidents), and interface ID derivation (ERC-165) is just XOR of selectors — know the mechanics, not just the name.

### The four call families

| Opcode | Context | Storage touched | msg.sender/msg.value | Reverts on state change |
|---|---|---|---|---|
| CALL | callee's | callee's | rewritten (current contract becomes sender) | no |
| STATICCALL | callee's | none writable | n/a (read-only frame) | yes |
| DELEGATECALL | caller's | **caller's** | **preserved** | no |
| CALLCODE (legacy) | caller's | caller's | preserved | no |

Delegatecall is the entire upgrade story: a proxy contract holds state (balances, config) in ITS slots and forwards calls to an implementation whose code executes against those slots. It is also the entire disaster story: forward to an address you don't control and that code reads/writes YOUR storage with YOUR authority — the mechanism behind multiple wallet-drainer exploits where users delegatecall into malicious "permit2-style" helpers.

### Events, priced honestly

The LOG opcodes emit entries into transaction receipts: base 375 gas, +375 per topic (up to 3 indexed params + the event signature as topic 0), +8 per data byte, recorded into a 2,048-bit Bloom filter in the block header so light scans can reject non-matches. Compare mediums:

| Need | Mechanism | Cost | Readable by contracts? |
|---|---|---|---|
| Mutate logic decisions | storage | 2,900-20,000/write | yes |
| Off-chain history/analytics | event | ~375-1,500 typical | no |
| Config flags read often | storage (or immutable) | varies | yes |

Rule of thumb: if a smart contract must branch on it, pay for storage; if humans/indexers consume it, emit an event. Emitting instead of storing where possible is why modern protocols keep on-chain footprints small and rebuild history from logs.

### Upgradeability patterns, compared

All share the skeleton: user-facing proxy (holds state) → implementation contract (holds code) via delegatecall, with the implementation address stored at the EIP-1967 slot `keccak256("eip1967.proxy.implementation") − 1` (hex begins `360894a13ba1a…`) so it never collides with declared variables.

| Pattern | Where upgrade logic lives | Strength | Distinctive hazard |
|---|---|---|---|
| Transparent proxy | proxy checks caller (admin vs user routes differently) | simple mental model | gas overhead per call; admin functions callable only by admin |
| UUPS (EIP-1822) | inside implementation (`upgradeToAndCall`) | cheaper proxy; upgrade+init atomic | buggy/burned implementation bricks proxy permanently |
| Beacon | proxy reads beacon's impl | upgrade N proxies in one tx | beacon is central choke point |
| Diamond (EIP-2535) | selector→facet map in proxy | modular size-limit busting | selector clashes; loudest audit surface |

Initialization is its own minefield: constructors don't run through proxies (only runtime code does), so logic moves to `initialize()` guarded by an `initialized` flag — and forgetting the guard or leaving the implementation uninitialized is exactly how Parity's library lost 513,000 ETH in November 2017 (anyone could call the unowned init, take ownership, then trigger its self-destruct). Modern defenses: initializer modifiers, deploying implementations already-initialized (via `ERC1967Utils` helpers), and disabling initializers on logic contracts.

## Build it from scratch

EVM call-context and proxy semantics simulated in plain Python — no compiler needed to internalize the two ideas that matter: context preservation and storage-layout coupling. Verified below.

```python
"""EVM call-context + upgradeable-proxy semantics simulated in plain Python."""

class Revert(Exception): pass

class Contract:
    """One contract account: immutable code dict + mutable storage."""

    def __init__(self, code, name):
        self.code = code              # selector(str) -> callable(ctx, **kw)
        self.name = name
        self.storage = {}
        self.balance = 0
        self.events = []

class Frame:
    """Execution context - what msg.sender/msg.value ARE inside the callee."""
    def __init__(self, sender, origin, value=0):
        self.sender = sender          # immediate caller  (msg.sender)
        self.origin = origin          # EOA that started it (tx.origin)

def _call(target, frame, selector, **kw):
    """CALL: callee's storage, rewritten sender."""
    return target.code[selector](target, frame, target.storage, **kw)

def _delegatecall(impl, caller, frame, selector, **kw):
    """DELEGATECALL: CALLER'S storage, PRESERVED sender. The proxy primitive."""
    return impl.code[selector](caller, frame, caller.storage, **kw)

# ---------- implementation v1 ----------
def deposit_v1(self, ctx, storage, amount):
    key = ('balance', ctx.sender)              # balances[msg.sender]
    storage[key] = storage.get(key, 0) + amount
    self.balance += amount
    self.events.append(('Deposited', ctx.sender, amount))
    return True

def getBalance_v1(self, ctx, storage):
    return storage.get(('balance', ctx.sender), 0)

V1 = {'deposit': deposit_v1, 'getBalance': getBalance_v1}

# ---------- v2 appends a feature WITHOUT touching existing slots ----------
def withdraw_v2(self, ctx, storage, amount):
    key = ('balance', ctx.sender)
    if storage.get(key, 0) < amount:
        raise Revert('insufficient')
    storage[key] -= amount
    self.balance -= amount
    self.events.append(('Withdrawn', ctx.sender, amount))
    return True

V2 = dict(V1); V2['withdraw'] = withdraw_v2     # append-only layout: safe upgrade

# ---------- BROKEN v3: author inserts state at the FRONT ----------
def getBalance_broken(self, ctx, storage):
    # identical intent, but the variable now conceptually lives one slot later
    return storage.get(('slot1-balance', ctx.sender), 0)
BROKEN_V3 = {'deposit': deposit_v1, 'getBalance': getBalance_broken}

if __name__ == '__main__':
    alice = 'alice'
    proxy   = Contract({}, name='Proxy')       # holds ALL state; no logic of its own
    impl_v1 = Contract(V1, name='ImplV1')
    impl_v2 = Contract(V2, name='ImplV2')

    frame = Frame(sender=alice, origin=alice)  # through a proxy msg.sender stays alice
    _delegatecall(impl_v1, proxy, frame, 'deposit', amount=100)
    assert _delegatecall(impl_v1, proxy, frame, 'getBalance') == 100

    # UPGRADE: swap the pointer; SAME storage now runs NEW code
    _delegatecall(impl_v2, proxy, frame, 'withdraw', amount=30)
    assert _delegatecall(impl_v2, proxy, frame, 'getBalance') == 70

    broken = Contract(BROKEN_V3, name='BrokenV3')
    seen = _delegatecall(broken, proxy, frame, 'getBalance')
    assert seen == 0, 'collision must hide the real balance'
    print('proxy upgrade ok: balance 100 -> withdraw 30 -> 70 across impls')
    print(f'broken v3 reads shifted layout -> sees {seen}, not 70')
```

Run it and both lessons land mechanically: the balance survives an implementation swap because delegatecall kept writing the *proxy's* storage under unchanged keys (that's why append-only layouts are a rule), and the "v3" that prepends state reads a different location entirely, silently showing zero balances to every user. Deliberate omissions to name: no real keccak-based slot addressing (Python dict keys stand in for `keccak(abi.encode(key, slot))`), no EIP-1967 pointer stored on-chain, no initializer guard demonstrated (the Parity scenario would be one missing flag check here).

## How it's done in production

**Toolchain.** Foundry (Rust, fast, fuzzing + invariant tests built-in) dominates new development; Hardhat persists where JS integration suites exist. Storage-layout safety ships as CI: OpenZeppelin's upgrades plugin diffs declared layouts between versions and refuses incompatible ones; `forge inspect <Contract> storageLayout` gives the raw truth.

**Governance around upgradeability.** Real deployments wrap the admin path: Safe multisig (n-of-m) or on-chain governor holds the UUPS/transparent-proxy admin role, actions pass through a TimelockController giving users 1-7 days to exit before changes execute. The interview-grade answer names all three: who proposes, who approves, how long users have.

| Symptom | Cause | Fix |
|---|---|---|
| Balances read zero after proxy upgrade | Storage layout shifted (variable inserted/removed mid-contract) | Append-only layout discipline; OZ layout diff CI; ERC-7201 namespaces |
| Implementation bricked after upgrade | UUPS upgradeTo called on itself with bad code / initializer consumed | Guarded upgrades, test on fork, keep emergency pause |
| Anyone can reinitialize the system | Missing initializer guard on implementation | `initializer` modifiers; deploy implementations pre-initialized; disable initializers |
| Wallet drained after signing one permit | Delegatecall into attacker-supplied address | Never delegatecall user inputs; audit every delegatecall target |
| Diamond call routes to wrong facet | Selector clash between facets | `diamondCut` validation, loupe checks, selector-uniqueness tests |
| Upgrade executed instantly by compromised key | No timelock between approval and execution | TimelockController 1-7 days; monitoring of queued ops |

**Deployment mechanics worth knowing:** CREATE2 deterministic addressing (`keccak(0xff ++ deployer ++ salt ++ keccak(initCode))`) enables counterfactual wallets and same-address redeployments across chains; minimal proxies (EIP-1167 clones, ~45 bytes) replicate an implementation cheaply for factory patterns; and immutable-data patterns (constants/immutables baked into bytecode) remove entire upgrade classes by removing the need.

## Tradeoffs & when NOT to use it

- **Default to immutable when you can.** Uniswap's core factories shipped unupgradeable deliberately: no keys to compromise, no governance capture vector, trust from day one. Choose upgradeable only when iteration speed genuinely exceeds the attack surface you're adding.
- **Upgradeability is a key-management product, not a feature.** The honest question is "who can steal all funds?" If the answer is "one EOA," you've centralized regardless of chain decentralization. Multisig + timelock is table stakes, not sophistication.
- **Diamonds are usually overkill.** They solve the 24 KB contract-size limit and team-scale modularity; most systems fit UUPS plus libraries. Every facet boundary adds selector-clash and auth surface.
- **Events are not a database.** Logs aren't queryable from contracts, receipts pruning affects some nodes, and indexed topics are lossy (32-byte hashes of dynamic values). If you need contract-visible state, store it.
- **Packing has a readability price.** Squeezing five fields per slot makes layouts brittle under refactoring; do it where gas dominates (loops, hot paths), not everywhere — measure first.
- **When Solidity is the wrong language entirely:** high-assurance custody math (Move's resource types), heavy crypto loops (precompiles/Cairo), or formal-verification-first designs (K framework) may beat Solidity's defaults; the EVM ecosystem gravity is real but not physics.

## Interview questions

### Q1 — How does Solidity lay out storage slots? Walk through a packing example with gas numbers.
**Testing:** the layer below syntax.
**Answer:** Declaration order, sequential 32-byte slots; sub-32-byte values pack right-aligned into the current slot while they fit. Example: uint128+uint64+uint64 share slot 0; following uint256 takes slot 1. Writing the packed group costs one SSTORE (20k fresh / 2.9k update); unpacked across three slots it's three writes. Mappings reserve their slot; element k lives at keccak(abi.encode(key, reserved_slot)).
**Follow-up trap:** *"Does packing always help?"* — Reads pay per slot touched: interleaving hot and cold fields in one slot forces loading both. Pack cold-together-with-cold; measure with forge snapshots rather than dogma.

### Q2 — Explain CALL vs DELEGATECALL precisely: what changes, what stays?
**Testing:** the single most important EVM semantic.
**Answer:** Both transfer execution to target code. CALL switches everything: callee's storage frame, msg.sender becomes the calling contract, msg.value only if explicitly forwarded. DELEGATECALL keeps the caller's context: caller's storage, original msg.sender and value preserved; only the CODE is foreign. That asymmetry makes proxies possible and makes untrusted delegatecall fatal — foreign code runs with your identity against your state.
**Follow-up trap:** *"Why did they even build delegatecall?"* — Library reuse pre-proxies (stateless libs), then the proxy pattern weaponized it. Also mention STATICCALL (Byzantium, Oct 2017) enforcing read-only frames — the trio defines modern composition.

### Q3 — Where does the proxy implementation pointer live and why that specific place?
**Testing:** EIP-1967 fluency.
**Answer:** At keccak256("eip1967.proxy.implementation") − 1, beginning hex 360894a13ba1a… — chosen pseudo-randomly so no realistically-declared Solidity variable lands on that slot, avoiding the structured-storage collisions of early hand-rolled proxies. Beacon and admin slots follow the same recipe.
**Follow-up trap:** *"Why minus one?"* — Historical: hashing the string could theoretically collide with a valid storage key pattern; subtracting one produces a value outside typical compiler-assigned space and signals intentional non-collision. Know it's convention-plus-safety, not arithmetic necessity today.

### Q4 — Why are events cheaper than storage and when must you still use storage? Give the cost math.
**Testing:** cost-model judgment.
**Answer:** Events: 375 base + 375/topic + 8/byte, written once into prunable-ish receipts, searchable via 2048-bit Bloom in headers; never readable on-chain. Storage: 20k fresh / 2.9k update but branchable by contracts. A typical Transfer event ≈ 375·2 + 8·~64 bytes ≈ ~1.3k gas versus 20k for storing the same fact — but if withdrawal logic needs the number next block, storage (or recomputation) is mandatory.
**Follow-up trap:** *"Can contracts read events at all?"* — Not directly: no opcode reads arbitrary past receipts; workarounds (block-scoped event verification via bloom tricks) are fragile. Design assuming off-chain-only consumption.

### Q5 — Compare transparent proxy vs UUPS. Which would you pick and why?
**Testing:** current default-pattern judgment.
**Answer:** Transparent: proxy distinguishes admin vs user callers, exposing upgrade functions only to admin; simpler reasoning, extra gas on every call for the check. UUPS (EIP-1822): logic lives inside implementation via upgradeToAndCall; proxies stay minimal (~cheaper deploys), upgrades atomic with initialization; hazard is bricking — bad implementation consumes your last chance. Modern default: UUPS + ERC-7201 namespaced storage + timelocked multisig admin.
**Follow-up trap:** *"What kills UUPS deployments in practice?"* — Upgrading to an implementation whose upgrade function lacks authorization, or initializing the implementation standalone so someone else owns it. Fork-test upgrades and pre-initialized deployment mitigate both.

### Q6 — Tell me about Parity's 2017 freeze. What exact mistake, and what exists now because of it?
**Testing:** incident literacy shaping modern patterns.
**Answer:** July 2017: a vulnerability let an actor become owner of Parity's shared multi-sig library and selfdestruct it, freezing dependent wallets; November's follow-on killed access permanently — 513,000 ETH (~$150M then) locked forever. Root causes: public default-initializable functions (anyone could claim ownership) and a suicide() on shared infrastructure. Legacy: initializer modifiers, owned-base contracts, disabling initializers on logic deployments, and general paranoia about shared mutable libraries.
**Follow-up trap:** *"Could that happen through a proxy today?"* — Different shape but same class: uninitialized UUPS implementations remain exploitable (several 2022-23 incidents), which is exactly why tooling auto-initializes/disables them now. The bug class survives; the defaults hardened.

### Q7 — What breaks if two implementations in a diamond define clashing selectors? How is it detected?
**Testing:** diamond depth without fanboyism.
**Answer:** The proxy's selector→facet map resolves one winner; calls meant for the loser route silently to the wrong facet — wrong auth context, wrong storage assumptions, fund-loss shapes. Detection: loupe introspection plus CI asserting global selector uniqueness across facets; diamondCut should reject duplicates.
**Follow-up trap:** *"Are collisions accidental-only?"* — No: crafted collisions were exploited (SushiSwap's router mishandling, 2022-class incidents) where attacker-chosen signatures aliased protected functions. Treat selector space as adversarial input, not compiler trivia.

### Q8 — How would you design initialization for an upgradeable system with multiple modules?
**Testing:** applied constructor-through-proxy reasoning.
**Answer:** Single entry initialize() guarded once (initializer modifier), calling module initializers via reinitializer(1)-style versioning; deploy implementation pre-initialized or with initializers disabled; wire roles (admin/upgrader/pauser) during init from the deployer then transfer to Safe/timelock; verify storage post-init on fork simulation. Sequence matters: grant roles LAST to avoid front-running windows.
**Follow-up trap:** *"Why not several separate initialize txs?"* — Interim states are attackable (partially-configured systems with live proxies); atomic init via upgradeToAndCall closes the window. If forced to split, pause until complete.

### Q9 — When is CREATE2 the right tool? Concrete use cases.
**Testing:** factory-pattern maturity.
**Answer:** Address = keccak(0xff ++ deployer ++ salt ++ keccak(initCode))[:20] — deterministic pre-deployment. Uses: counterfactual wallets (pay for deployment at first use at a known address), cross-chain same-address deployments (multichain infra sanity), token wrappers/vaults recreated after destruction, registry patterns where UIs bind addresses once.
**Follow-up trap:** *"Any footguns?"* — initCode hash includes constructor bytecode: compiler-version drift changes addresses; salt-front-running (deploy first with your salt, griefing counterfactual flows) needs commit-reveal or factory-level guards; and redeploying at a formerly-selfdestructed address inherits cleared-but-history-rich storage semantics post-EIP-6780 nuances.

### Q10 — Your protocol needs a config value changed weekly by governance. Event, storage, or something else?
**Testing:** medium-selection judgment.
**Answer:** Storage: contracts must branch on current value — non-negotiable. Optimize around edges: pack the flag word, use a struct slot updated at 2.9k gas, expose via view for indexers, emit an event alongside purely for history. If the value feeds only off-chain consumers (UI hints), event-only suffices.
**Follow-up trap:** *"Immutable for config?"* — Immutables bake at construction: right for eternal constants, wrong for anything governance adjusts. Middle ground: SSTORE2-style blob writes or minimal-proxy-per-config if churn is extreme — usually overengineering; say so.

### Q11 — Walk through what msg.sender is across: user → proxy → implementation → another token.
**Testing:** context-propagation precision under pressure.
**Answer:** User EOA → proxy: msg.sender = EOA. Proxy → implementation via delegatecall: still EOA (context preserved). If implementation then CALLs a token: token sees msg.sender = proxy address (the executing context), NOT the EOA. That's why approve/transferFrom dances exist, why balance reads inside composited protocols need care, and why tx.origin-based auth breaks here (origin stays EOA but sender doesn't).
**Follow-up trap:** *"Fix for protocols needing true user attribution?"* — msgSender patterns via trusted forwarders (GSN/ERC-2771 meta-transactions appending the real sender in calldata), later standardized thinking flowing into 4337/7702 account abstractions.

### Q12 — Solidity 0.8 changed overflow behavior. What did that delete and what remains dangerous?
**Testing:** language-history awareness tied to security.
**Answer:** Checked arithmetic became default: +/-/* revert on overflow instead of wrapping, deleting SafeMath ceremony and the BEC/SMT-class token bugs. Still dangerous: unchecked blocks (deliberate wraps), casting truncation (uint256→uint128 silently drops bits), array-index underflow pre-0.8 quirks in assembly, and economic overflow (amounts that overflow downstream integrations).
**Follow-up trap:** *"So SafeMath is dead?"* — In source yes; its ghost lives in assembly blocks and older deployed code you integrate with. Audit checklists still grep for unchecked and explicit casts.

### Q13 — You inherit a codebase with transparent proxy + two-year-old implementation. What's your first hour?
**Testing:** practical triage methodology.
**Answer:** Read the proxy: confirm EIP-1967 slots (impl/admin), who holds admin (EOA? Safe? timelock?). Dump storage layout of live implementation (forge inspect) and diff against latest repo tag. Check initializer state and upgrade-function authorization. Pull recent admin ops from the timelock. Then fork-mainnet test both an upgrade and a rollback. Nothing else proceeds until those facts are pinned.
**Follow-up trap:** *"Repo says one thing, chain says another — trust?"* — The chain: storage IS state. Repo drift means migrations ran elsewhere; reconstruct from events (Upgraded logs give impl history) rather than git archaeology alone.

### Q14 — Why did ERC-7201 appear? Explain namespaced storage mechanically.
**Testing:** newest storage-discipline knowledge.
**Answer:** Composable contracts (especially diamonds/facets and modular frameworks) kept colliding when independently-developed modules each claimed low slots. ERC-7201 derives a namespace root: keccak256(abi.encode(uint256(keccak256(id)) − 1)) & ~0xff... placing module state at hashed offsets no declaration collides with — EIP-1967 thinking generalized to app storage. Adopted by OpenZeppelin's modular contracts (2023+).
**Follow-up trap:** *"Costs?"* — Human-readable slot maps vanish; debugging leans on tooling; migration of EXISTING linear-layout contracts into namespaces is a one-time painful rewrite. New projects adopt from day one; retrofits weigh cost honestly.

### Q15 — Should this system be upgradeable at all? Give your decision procedure, not just a preference.
**Testing:** the senior judgment question underneath all proxy trivia.
**Answer:** Procedure: enumerate change classes expected in 12 months (bugfix-only vs parameter vs logic), threat-model the admin path (key compromise → total loss?), regulatory/trust constraints (immutable sells neutrality), and exit options (migration contracts, pausable bridges to new instances). Immutable if changes are parameter-shaped (setters suffice); upgradeable if logic iteration is certain AND governance can be made credible (multisig + timelock + monitoring). State the failure story either way: immutables die with bugs; upgradables die with keys.
**Follow-up trap:** *"Uniswap survived immutable — so everyone should?"* — Survivorship framing: Uniswap accepted permanent-bug risk because AMM cores are tiny and battle-tested; a fast-iterating lending market cannot copy that. Match mechanism maturity to mutability choice, don't cargo-cult winners.

## Red flags

- Describing proxies without delegatecall context-preservation (msg.sender/storage).
- Claiming events are readable by other contracts.
- No answer for where the implementation pointer lives or why.
- Treating initialize() as optional decoration.
- Proposing diamonds as a default architecture.
- Saying Solidity 0.8 "fixed all integer bugs" (casts and unchecked blocks persist).
- Upgrading contracts with no mention of storage-layout diffing.
- Confusing CREATE and CREATE2 determinism guarantees.

## Cheat card

```
STORAGE       32 B slots · declaration order · pack sub-32B neighbors
              mapping elem k: keccak(abi.encode(k, slot)) · arrays: len @slot
              fresh write 20000 · update 2900 · refund 4800 (cap 1/5 gas)
SELECTOR      bytes4(keccak("fn(types)")) · calldata = sel ++ 32B words
CALLS         CALL: callee ctx/storage · sender rewritten
              DELEGATECALL: YOUR storage + KEPT msg.sender/value <- proxy
              STATICCALL: read-only frame (Byzantium 10/2017)
EVENTS        LOG: 375 + 375/topic (max 3+sig topic0) + 8/byte
              bloom 2048-bit in header · OFF-CHAIN ONLY · ~1.3k vs 20k SSTORE
PROXY         impl ptr @ keccak("eip1967.proxy.implementation")-1 = 0x360894a1...
              transparent: admin-aware proxy · UUPS: upgrade lives in impl (brick!)
              beacon: N proxies -> 1 beacon · diamond: selector->facet map
INIT          constructors DON'T run via proxy -> initialize() + guard
              Parity 11/2017: uninit lib + suicide -> 513k ETH frozen forever
SAFETY        append-only storage layout · OZ diff CI · ERC-7201 namespaces
              CREATE2 addr = keccak(0xff++dep++salt++keccak(initCode))
              0.8: checked math default; casts/unchecked still bite
DECISION      immutable unless logic iteration > key-compromise risk
              upgradable needs: multisig + 1-7d timelock + monitoring
```

## Sources

- [Solidity documentation — storage layout and slots](https://docs.soliditylang.org/en/latest/internals/layout_in_storage.html); accessed 2026-08-23
- [EIP-1967: Standard Proxy Storage Slots](https://eips.ethereum.org/EIPS/eip-1967); accessed 2026-08-23
- [EIP-1822: Universal Upgradeable Proxy Standard (UUPS)](https://eips.ethereum.org/EIPS/eip-1822); accessed 2026-08-23
- [EIP-2535: Diamonds, Multi-Facet Proxy](https://eips.ethereum.org/EIPS/eip-2535); accessed 2026-08-23
- [ERC-7201: Namespaced Storage Layout](https://eips.ethereum.org/EIPS/eip-7201); accessed 2026-08-23
- [OpenZeppelin Upgrades Plugins — storage layout checks](https://docs.openzeppelin.com/upgrades-plugins/); accessed 2026-08-23
- [Parity multisig freeze post-mortem coverage — CoinDesk, Nov 2017](https://www.coindesk.com/markets/2017/11/09/a-280-million-cryptocurrency-disaster-parity-wallet-freeze/); accessed 2026-08-23
- [Solidity docs — contracts, ABI, selectors](https://docs.soliditylang.org/en/latest/contracts.html); accessed 2026-08-23
- [Foundry Book — gas snapshots and storage inspection](https://book.getfoundry.sh/); accessed 2026-08-23
- [EIP-1167: Minimal Proxy Contract](https://eips.ethereum.org/EIPS/eip-1167); accessed 2026-08-23

## Changelog

- 2026-08-23 — created



