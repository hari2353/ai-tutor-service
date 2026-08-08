# Solidity From Scratch: Storage, Calls, Events, Upgradeability

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 3h · **Prereqs:** `T22-bitcoin-ethereum`
> **Updated:** 2026-08-08
> **Module id:** `T22-smart-contracts` · **Tags:** contracts, critical
> **Lab:** `labs/sol/22-smart-contracts/`

## The 30-second version

A Solidity contract's storage is a flat array of 2^256 32-byte slots, and the compiler packs consecutively-declared state variables smaller than 32 bytes into the same slot to save gas — get the declaration order wrong and you pay for extra `SSTORE`s that correct ordering would have avoided for free, which is why storage layout is a real, measurable cost decision, not a style preference. `call` and `delegatecall` are both ways to invoke another contract's code, but they differ in exactly one load-bearing way: `call` executes in the *callee's* storage context (the callee's state changes, the callee's `msg.sender` becomes the caller), while `delegatecall` executes the callee's code *in the caller's own storage context* — the callee's logic runs as if it were the caller's own code, reading and writing the caller's storage slots directly. That single distinction is simultaneously how every upgradeable-proxy pattern in production works and the root cause of some of the most expensive smart contract exploits ever recorded, because a proxy and its implementation contract must agree on storage layout with zero tolerance for drift, and a `delegatecall` to an untrusted or mismatched contract hands that contract the ability to overwrite your storage as if it were its own. Upgradeability patterns (Transparent Proxy, UUPS, Diamond) exist because deployed bytecode is immutable by design — the proxy pattern's entire trick is that the proxy's *address* stays fixed and its `delegatecall` target (the implementation) can be swapped, which is upgradeability achieved through indirection, not through actually mutating deployed code.

## Why this gets asked

Because Solidity looks like a mainstream object-oriented language on the surface and behaves nothing like one underneath — an interviewer asking about storage slots or `delegatecall` wants to know if you understand the EVM's actual execution and storage model, since surface-level Solidity fluency without that understanding is exactly how the Parity multisig wallet lost $150M+ in 2017 (a `delegatecall` to a library whose storage layout assumption turned out to be attacker-controllable) and how numerous smaller proxy-storage-collision bugs have shipped since. This is the module where "I've written Solidity" and "I understand what Solidity compiles to and why the compiler makes the choices it does" visibly diverge.

---

## Lineage: past → present → future

**What came before.** Ethereum's earliest contracts, in the 2015-2016 era, were deployed as immutable bytecode with no upgrade mechanism at all — a bug meant redeploying an entirely new contract at a new address and migrating users and funds manually, which is exactly what happened repeatedly in that period and is a large part of why "smart contracts are immutable" became an early, load-bearing selling point that later needed walking back in practice. The DAO hack (June 2016, a reentrancy exploit draining roughly $60M in ETH at the time) forced the ecosystem to confront that immutability without an upgrade path is not an unambiguous virtue — it also means bugs are permanent — and the response split into two schools: Ethereum itself hard-forked to reverse the DAO hack's effects (a protocol-level, deeply controversial intervention that produced the Ethereum/Ethereum Classic split), while application-level developers began building proxy patterns so that *individual contracts* could be upgraded without requiring anything as drastic as a chain fork.

**Where it stands now.** Proxy-based upgradeability is mainstream and widely deployed — the majority of significant DeFi protocols and most production dApps holding meaningful value use some form of upgradeable proxy rather than a genuinely immutable, one-shot deployment, and OpenZeppelin's audited proxy implementations (Transparent, UUPS, Beacon) are the de facto standard most teams build on rather than hand-rolling. The live, substantive disagreement is about which proxy pattern to default to: **UUPS (EIP-1822/ERC-1822)** has become OpenZeppelin's own recommended default over the older Transparent Proxy pattern specifically because it moves the upgrade-authorization logic into the *implementation* contract rather than the proxy, which is both cheaper per-call (no need to check "is this an admin call" on every single invocation, since that check lives in the rarely-called upgrade function instead) and, notably, means an implementation that forgets to include upgrade logic becomes **permanently non-upgradeable** — a real, sharp failure mode UUPS trades in for its efficiency gain, and teams disagree in good faith about whether that tradeoff is worth it versus Transparent Proxy's built-in safety net. The **Diamond pattern (EIP-2535)**, which splits a contract's logic across many independently-upgradeable "facets" behind one proxy, remains a minority choice reserved for genuinely large, modular systems that exceed the 24KB contract size limit — its tooling is real but markedly less mature than Transparent/UUPS, and most teams that don't specifically need to exceed the size limit are better served by simpler patterns.

**Where it's heading.** High confidence: storage-layout safety tooling continues improving — namespaced storage patterns (**EIP-7201**, formalizing a technique storage-collision-conscious teams were already using informally) are becoming a standard recommendation specifically to make storage-layout mistakes structurally harder to make by deriving each contract's storage location from a unique, collision-resistant namespace rather than relying on manual slot-ordering discipline alone. Medium confidence: account abstraction (**ERC-4337**, and native account abstraction proposals for future Ethereum upgrades) changes what "a user's account" even is at the protocol level, which has second-order implications for upgrade and access-control patterns this module doesn't cover in depth but is worth knowing is an active, evolving area. Lower confidence, more speculative: whether the Diamond pattern's tooling and adoption reach parity with Transparent/UUPS, or whether it remains a specialized tool for large protocols specifically — treat this as genuinely open rather than assuming convergence in either direction.

---

## Mental model

```
  STORAGE LAYOUT: state variables pack into 32-byte slots, DECLARATION ORDER matters

  contract Bad {                          contract Good {
    uint128 a;   // slot 0 (16 bytes)       uint128 a;   // slot 0, byte 0-15
    uint256 b;   // slot 1 (needs full      uint128 c;   // slot 0, byte 16-31 <- PACKED
                 //   32 bytes, a's other                                        with a!
                 //   16 bytes in slot 0                uint256 b;   // slot 1
                 //   are WASTED)
    uint128 c;   // slot 2 (16 bytes,       // Good: 2 slots used. Bad: 3 slots used.
                 //   16 bytes wasted)      // Every avoided slot = ~20,000 gas saved
  }                                        //   on first write (module 4's SSTORE cost)


  CALL vs DELEGATECALL: same syntax, opposite storage context

  Contract A calls Contract B:

  A.foo() --call--> B.bar()          A.foo() --delegatecall--> B.bar()
    B's code runs                      B's CODE runs
    IN B's storage                     IN A's STORAGE  <── the whole point
    msg.sender = A                     msg.sender = (unchanged, still whoever called A)
    msg.value context = B's            msg.value context = A's

  This is EXACTLY how a proxy works:
  ┌──────────┐  delegatecall   ┌────────────────────┐
  │  PROXY   │ ──────────────▶ │  IMPLEMENTATION      │
  │ (fixed   │                 │  (the actual logic,  │
  │  address,│                 │   swappable —        │
  │  holds   │ ◀── logic runs ─│   THIS address is    │
  │  ALL the │     against     │   what "upgrading"   │
  │  storage)│     PROXY's     │   changes)            │
  │          │     storage!    │                       │
  └──────────┘                 └────────────────────┘
  Users always call the PROXY's fixed address. "Upgrading" = the proxy
  starts delegatecall-ing to a NEW implementation address. Storage layout
  between proxy and EVERY implementation version must match EXACTLY, or
  the new implementation's variables silently read/write the WRONG slots.
```

---

## How it actually works

### Storage slot packing, precisely

Ethereum contract storage is conceptually a mapping from a 256-bit slot number to a 256-bit value. The Solidity compiler assigns state variables to slots **in declaration order**, and — this is the packing optimization — consecutive variables that together fit within 32 bytes are packed into the *same* slot rather than each getting its own. A `uint128` (16 bytes) followed by another `uint128` shares one slot; a `uint128` followed by a `uint256` does not, because the `uint256` needs the full 32 bytes and can't share.

**The mechanical rule:** the compiler processes state variables in order, and starts a new slot only when the current variable wouldn't fit in the remaining space of the current slot. `bool`, `address` (20 bytes), and small `uint`s are the common candidates for packing; dynamic types (`mapping`, dynamically-sized `array`, `string`, `bytes`) never pack with anything — each always occupies its own conceptual slot as a base pointer, with actual data stored at a `keccak256`-derived location computed from that base slot (this is what lets a mapping have unbounded size without needing contiguous storage).

```solidity
// BAD ORDER — 3 slots used
contract Bad {
    uint128 a;   // slot 0, bytes 0-15 (bytes 16-31 of slot 0 wasted — b needs a fresh slot)
    uint256 b;   // slot 1, full slot
    uint128 c;   // slot 2, bytes 0-15 (bytes 16-31 wasted)
}

// GOOD ORDER — 2 slots used, functionally identical contract
contract Good {
    uint128 a;   // slot 0, bytes 0-15
    uint128 c;   // slot 0, bytes 16-31 — PACKED with a, same slot
    uint256 b;   // slot 1, full slot (uint256 never packs with anything)
}
```
`// untested sketch — illustrates slot-packing rules; compile with solc --storage-layout to confirm exact slot assignment for any specific contract`

Every slot saved isn't cosmetic: module 4 covered that writing a previously-zero storage slot costs 20,000 gas — packing two variables that would otherwise occupy separate slots into one, and writing both together, can turn two expensive `SSTORE`s into effectively one, a real and often significant deployment- and runtime-gas saving at scale, which is exactly why gas-conscious Solidity style guides consistently recommend grouping same-or-smaller-than-32-byte state variables together by declaration order rather than declaring them in whatever order reads most naturally.

### `call` vs `delegatecall`, and why the distinction is the entire upgradeability mechanism

Both are low-level ways to invoke another contract's bytecode, and both accept arbitrary calldata and forward a specifiable amount of gas — the difference is entirely about *execution context*:

| | `call` | `delegatecall` |
|---|---|---|
| Whose storage is read/written | The **callee's** storage | The **caller's** storage |
| `msg.sender` inside the invoked code | The calling contract | Unchanged — still the original caller of the *outer* call |
| `msg.value` inside the invoked code | The value sent with this call | Unchanged — the outer call's value context |
| Typical use | Normal inter-contract calls, sending ETH | Proxy patterns, and (historically) shared library logic |

`delegatecall`'s defining property — executing foreign code against your own storage — is precisely what makes upgradeable proxies possible: the proxy contract holds all the actual state (balances, owner, whatever the application needs), and every call to the proxy `delegatecall`s into an implementation contract that contains only *logic*, no meaningful persistent state of its own. "Upgrading" a proxy means changing which implementation address it `delegatecall`s to — the proxy's own address, and everything pointing at it, never changes.

**The exact same mechanism is the root cause of one of Ethereum's largest-ever losses.** The July 2017 Parity multisig wallet hack exploited a wallet contract that `delegatecall`d into a shared library contract for its core logic; an attacker found that the library contract itself was callable *directly* (not just via delegatecall from a wallet) and had an unprotected function that let them become the library's "owner" and then `selfdestruct` it — because every wallet's `delegatecall` pointed at that now-destroyed library address, every wallet depending on it was permanently, unrecoverably bricked, freezing roughly $150M+ in ETH. The lesson generalizes precisely: `delegatecall` gives the target contract's code full read/write access to your storage exactly as if it were your own code, so `delegatecall`ing to any contract whose access control, storage layout, or destructibility isn't fully understood and trusted is handing over your entire contract's state.

### Events

Events are how contracts emit structured, indexed log data that's cheap to write (far cheaper than an equivalent `SSTORE`, since event data isn't part of contract storage or the state trie — it's stored in transaction receipts, part of a separate, block-header-referenced receipts trie, module 4) and queryable off-chain by anything watching the chain, without being readable *by other contracts* on-chain at all.

```solidity
// untested sketch — standard event pattern, illustrates the `indexed` mechanic
contract Token {
    event Transfer(address indexed from, address indexed to, uint256 value);

    function transfer(address to, uint256 amount) external {
        // ... balance updates ...
        emit Transfer(msg.sender, to, amount);
    }
}
```

`indexed` parameters (up to three per event) are stored as searchable "topics" in the log, letting off-chain indexers (The Graph, custom event listeners, block explorers) efficiently query "every Transfer event where `to == 0x...`" without scanning every transaction's full data — non-indexed parameters are stored in the log's data payload, cheaper to include but not directly filterable this way. This indexed/non-indexed split is precisely why almost every production ERC-20's `Transfer` and `Approval` events index both address parameters but leave the numeric `value`/`amount` non-indexed: addresses are what you filter by, amounts are what you read after finding the relevant events.

### Upgradeability patterns

**Transparent Proxy** (the older, still-widely-deployed pattern): the proxy itself contains the logic to distinguish "is this call from the admin, trying to upgrade?" versus "is this a normal user call, to be delegatecalled through?" — routing admin calls to the proxy's own upgrade function and everything else through to the implementation. This costs a small amount of gas on *every single call* (the admin-check branch), but its safety property is strong and simple: the implementation contract itself needs zero awareness that it's sitting behind a proxy.

**UUPS (EIP-1822/ERC-1822)**, OpenZeppelin's current recommended default: moves the upgrade-authorization logic *into the implementation contract itself*, via an `upgradeTo` function the implementation must include (typically inherited from OpenZeppelin's `UUPSUpgradeable`). The proxy becomes almost trivially thin — it does nothing but `delegatecall` everything through — which saves the per-call admin-check gas cost Transparent Proxy pays, but creates a sharp, real failure mode: **if a given implementation version is deployed without correctly including the upgrade function (or with a bug in its access control), that version is permanently non-upgradeable**, since the upgrade logic that would fix it lives in the very contract that needs fixing.

**Diamond (EIP-2535)**: splits contract logic across many independently-deployed "facets," with one proxy routing each function selector to the facet that implements it, managed via a `diamondCut` function that adds/replaces/removes facets. This solves a problem neither Transparent nor UUPS solves at all: Ethereum's 24KB contract bytecode size limit, which a sufficiently large, feature-rich protocol can genuinely hit — Diamond lets you keep adding logic indefinitely across new facets without that ceiling. The cost is real, additional complexity: storage layout discipline now has to hold across *every* facet simultaneously (a single shared storage space, commonly managed via the namespaced-storage / "Diamond Storage" pattern to avoid collisions), and Diamond's tooling, audit familiarity, and community battle-testing remain markedly less mature than Transparent or UUPS as of 2026.

**Storage-collision-resistant slot placement — EIP-1967.** Proxies need to store their own bookkeeping data (which implementation address to `delegatecall` to, who the admin is) *somewhere* in storage — but that somewhere must never collide with any slot the implementation's own state variables might use, or the implementation's normal storage writes would silently corrupt the proxy's own critical pointers. EIP-1967's fix: use slots computed as `keccak256("eip1967.proxy.implementation") - 1` (and similarly for admin, beacon) rather than slot 0, 1, 2 — a location so deep in the 2^256 slot space that no realistic implementation contract's ordinary sequential state-variable declarations would ever land there by accident. Computed directly (Keccak-256, verified against the actual value the ecosystem uses):

```python
implementation_slot = 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
admin_slot          = 0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
beacon_slot         = 0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50
# each computed as keccak256(label) - 1, confirmed by direct computation against
# a from-scratch pure-Python Keccak-256 implementation, matching the values every
# EIP-1967-compliant proxy (OpenZeppelin's included) actually uses on mainnet.
```

---

## Build it from scratch

The storage-slot arithmetic and the EIP-1967 slot derivation above **are** the from-scratch build worth internalizing precisely, because they're the exact mechanism, not a simplification — a from-scratch Keccak-256 implementation (built and verified against the known `keccak256("") = c5d2460186f7233c927e7db2dcc703c0e500b653ca82273b7bfad8045d85a470` test vector) was used to independently derive the canonical EIP-1967 slot constants above, rather than quoting them from a spec without verification.

A minimal, illustrative proxy — the mechanism, not a production-ready contract:

```solidity
// untested sketch — illustrates the EIP-1967 proxy mechanism minimally;
// use OpenZeppelin's audited ERC1967Proxy in any real deployment, never this
contract MinimalProxy {
    // EIP-1967 implementation slot: keccak256("eip1967.proxy.implementation") - 1
    bytes32 private constant _IMPL_SLOT =
        0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc;

    constructor(address implementation) {
        assembly { sstore(_IMPL_SLOT, implementation) }
    }

    fallback() external payable {
        address impl;
        assembly { impl := sload(_IMPL_SLOT) }
        assembly {
            calldatacopy(0, 0, calldatasize())
            let result := delegatecall(gas(), impl, 0, calldatasize(), 0, 0)
            returndatacopy(0, 0, returndatasize())
            switch result
            case 0 { revert(0, returndatasize()) }
            default { return(0, returndatasize()) }
        }
    }
}
```

Full lab — including a working Hardhat/Foundry project with a real Transparent Proxy and UUPS deployment, a `solc --storage-layout` exercise confirming actual slot assignment against hand-computed predictions, and a reproduction (on a local testnet, harmlessly) of the Parity-style delegatecall-to-untrusted-library failure mode: **`labs/sol/22-smart-contracts/`**.

---

## How it's done in production

**OpenZeppelin Contracts** is the de facto standard library almost every serious Solidity project builds on for proxies (`ERC1967Proxy`, `UUPSUpgradeable`, `TransparentUpgradeableProxy`), access control (`Ownable`, `AccessControl`), and token standards — hand-rolling any of this, especially proxy logic, against audited alternatives that exist specifically because the naive version has repeatedly failed in the field, is a real red flag in a code review, not a demonstration of skill. Deployment and upgrade orchestration commonly runs through Hardhat or Foundry's deployment scripting, with `storage-layout` compiler output diffed automatically in CI between the current and proposed implementation to catch storage-layout drift *before* deployment rather than discovering it on mainnet.

| Symptom | Cause | Fix |
|---|---|---|
| After an upgrade, a contract's state appears corrupted or reads garbage values | New implementation's storage layout doesn't match the old one — a variable was inserted, removed, or reordered rather than only appended | Only ever *append* new state variables after existing ones across upgrades; never reorder, resize, or remove; diff storage layouts in CI before every upgrade |
| Every user interaction with a proxy costs slightly more gas than an equivalent non-proxied contract | Transparent Proxy's per-call admin-check branch | Expected and usually acceptable overhead; switch to UUPS if this specific cost matters and the team accepts UUPS's non-recoverable-if-misconfigured tradeoff |
| An "upgraded" implementation can never be upgraded again | UUPS implementation deployed without correctly including (or with broken access control on) the upgrade function | Extensively test the upgrade path itself before every UUPS deployment, specifically including a dry-run upgrade-of-the-upgrade to confirm the mechanism still works |
| A proxy's calls silently do nothing or behave unexpectedly after a library or dependency change | `delegatecall` target's function selectors changed (a function signature changed, shifting the selector) without the proxy's expectations being updated | Treat implementation function signatures as a public interface contract as strict as any other API — changing them is a breaking change requiring coordinated updates |
| A contract is unexpectedly, permanently destroyed/frozen, and everything depending on it breaks | `delegatecall` (or a direct call) reached an untrusted or under-access-controlled contract containing `selfdestruct` (the Parity failure mode) | Never `delegatecall` to a contract you don't fully control and audit; as of Solidity 0.8.x-era EVM changes, `SELFDESTRUCT`'s behavior itself has also been substantially restricted at the protocol level (post-Dencun/EIP-6780) specifically in response to this class of risk |

---

## Tradeoffs & when NOT to use it

- **Don't reach for upgradeability by default.** A genuinely immutable contract has a real, valuable security property Ethereum's original design intended — users and auditors can verify exactly what code they're trusting, permanently, with no possibility of a malicious or buggy future upgrade — and plenty of production systems (many well-audited DeFi primitives, deliberately) ship without any upgrade mechanism specifically to make that guarantee credible. Upgradeability trades a real security property (code immutability as a user-verifiable guarantee) for operational flexibility; that trade needs to be made deliberately, not by reflexively bolting a proxy onto everything.
- **Don't default to UUPS without accepting its specific failure mode.** The gas savings are real but modest per-call; the risk of a misconfigured implementation becoming permanently stuck is a qualitatively different, sharper failure than Transparent Proxy's design, which keeps upgrade logic outside the (potentially buggy) implementation entirely. Teams without strong deployment-testing discipline are often better served by Transparent Proxy's built-in safety margin.
- **Don't use the Diamond pattern unless you're actually hitting the 24KB contract size limit or have a genuine, specific need for many independently-upgradeable modules.** Its complexity cost (shared storage discipline across many facets, less mature tooling and community audit experience) is real overhead most projects don't need — reaching for Diamond because it sounds more sophisticated, without the size or modularity constraint that actually motivates it, is a common overengineering mistake.
- **Don't `delegatecall` to any address that isn't fully known, audited, and access-controlled at deployment time**, and be specifically suspicious of any design where the delegatecall target could be user-influenced or upgraded independently of the calling contract's own governance — this is precisely the Parity failure pattern, and it recurs in smaller forms whenever a library or shared-logic contract's trust boundary isn't as tightly scoped as the calling contract assumes.
- **Storage packing optimization has a real diminishing-returns point.** Aggressively repacking every struct and state variable for maximum byte efficiency is worth doing for hot-path, frequently-written storage; spending significant engineering time hand-optimizing rarely-written configuration state for a few thousand gas is usually not where the effort belongs — profile actual write frequency before optimizing blindly.

---

## Interview questions

### Q1 — Explain exactly how Solidity packs state variables into storage slots, and why declaration order matters.
**Testing:** the mechanical rule, not just "packing exists."
**Answer:** Storage is a mapping from 256-bit slot numbers to 256-bit values. The compiler processes state variables in declaration order and packs consecutive variables into the same slot whenever they collectively fit within 32 bytes; it starts a new slot the moment the next variable wouldn't fit in the current slot's remaining space. Declaring a `uint128` immediately before another `uint128` packs them into one slot; interleaving a `uint256` between them forces both `uint128`s into their own separate slots, since the `uint256` needs the full slot and can't share.
**Follow-up trap:** *"Does reordering functions or reordering non-state-variable declarations (like modifiers) affect storage layout?"* — no, and this is worth stating precisely: only *state variable* declaration order affects storage slot assignment; functions, modifiers, and events have no storage-slot footprint of their own (events are logged to the receipts trie, not storage, as covered above) and reordering them has zero effect on the contract's storage layout.

### Q2 — Walk through exactly what changes and what stays the same between `call` and `delegatecall`.
**Testing:** the core mechanism this entire module hinges on.
**Answer:** Both invoke another contract's bytecode with forwarded calldata and gas. `call` executes that code in the *callee's* own storage and identity context — the callee's state changes, and `msg.sender` inside the callee becomes the calling contract's address. `delegatecall` executes the *same bytecode* but in the *caller's* storage and identity context — the callee's logic runs as if it were the caller's own code, reading and writing the caller's storage slots, and `msg.sender`/`msg.value` remain whatever they were for the outer call, unchanged by the delegatecall itself.
**Follow-up trap:** *"If contract A delegatecalls to contract B, and B's code calls `msg.sender`, what value does it see?"* — the original caller of A, not A's own address — this is a common point of confusion. `msg.sender` is not "who directly invoked this bytecode," it's preserved from the outer call context entirely, which is precisely the property that makes delegatecall-based proxies transparent to end users: a user calling a proxy that delegatecalls into an implementation sees `msg.sender` behave exactly as if they'd called the implementation directly, with no proxy-hop visible in that value.

### Q3 — Explain the Parity multisig wallet hack (2017) precisely, and what specific design mistake it exposes about delegatecall usage.
**Testing:** whether the historical incident is understood as a mechanism lesson, not just a headline.
**Answer:** Parity's multisig wallets `delegatecall`d into a shared library contract for their core logic to save deployment cost (many wallets sharing one library's code). That library contract itself was independently callable, directly, not just via delegatecall — and it had an unprotected initialization-style function letting an attacker claim ownership of the library itself, then trigger `selfdestruct` on it. Because every dependent wallet's delegatecall pointed at that now-empty address, every wallet's core logic became permanently unreachable, freezing roughly $150M+ in ETH with no recovery path, since the wallets' storage was intact but the logic needed to act on it was gone.
**Follow-up trap:** *"Was this a delegatecall-specific bug, or would it have happened with regular calls too?"* — specifically enabled by the shared-library-via-delegatecall pattern: the library needed to be delegatecalled into wallet storage for the pattern to work at all (a regular `call` would have operated on the library's own separate, largely irrelevant storage), and it's exactly this need for the library to be a legitimate delegatecall target that also made it a legitimate, dangerous *direct*-call target with no access control assuming it would only ever be reached via delegatecall from a trusted wallet.

### Q4 — Why does UUPS place the upgrade function in the implementation contract, and what specific new risk does that introduce compared to Transparent Proxy?
**Testing:** the actual tradeoff, not just "UUPS is newer/better."
**Answer:** Moving the upgrade-authorization check into the implementation means the (cheap, thin) proxy doesn't need to branch on "is this an admin call" for every single invocation the way Transparent Proxy does — saving gas on every ordinary call, since the check only needs to run when `upgradeTo` itself is actually invoked. The new risk: if a given implementation version is deployed without correctly including that upgrade function (or with broken access control on it), there is no other path to upgrade it — the very mechanism that would fix the mistake lives inside the broken contract, making that implementation version permanently stuck, a failure mode Transparent Proxy structurally can't have since its upgrade logic lives in the proxy itself, independent of whatever the implementation contains.
**Follow-up trap:** *"How would you mitigate UUPS's stuck-implementation risk in practice?"* — rigorous pre-deployment testing specifically of the upgrade path (not just the business logic), often including a dry-run "upgrade to a trivial new implementation and confirm it works" step before trusting a given implementation version in production, plus building on OpenZeppelin's audited `UUPSUpgradeable` base rather than hand-rolling the upgrade-authorization logic, since a subtle access-control bug in a hand-rolled version is exactly the failure this question is about.

### Q5 — What is EIP-1967 solving, and why can't a proxy just store its implementation address in slot 0?
**Testing:** the storage-collision problem specifically, and why an arbitrary-looking slot constant is actually a deliberate design choice.
**Answer:** If a proxy stored its implementation address in slot 0 (or any low, "ordinary" slot number), it would risk directly colliding with the *implementation* contract's own state variables, which — because delegatecall executes the implementation's code against the proxy's storage — also get assigned to low slot numbers by the compiler in normal declaration order. A collision means the implementation's first state variable and the proxy's implementation-address pointer would silently read and write the *same* storage slot, corrupting one or both. EIP-1967's fix is computing the slot as `keccak256("eip1967.proxy.implementation") - 1` (and similarly for admin/beacon) — a slot number effectively unreachable by any realistic sequential state-variable declaration, sidestepping the collision risk by using a location the implementation would essentially never organically land on.
**Follow-up trap:** *"Is EIP-1967's slot choice a mathematical guarantee against collision, or a probabilistic one?"* — probabilistic in the strict sense (any specific slot number is theoretically reachable by a contract with a sufficiently large, specifically-crafted number of preceding state variables or by direct inline assembly `sstore` to that exact slot), but this is the same practical distinction module 1 covers for hash-based security generally: the slot space is 2^256, an accidental collision via ordinary sequential declaration is astronomically implausible, and a *deliberately* crafted collision would require the implementation contract itself to be malicious in a way that a basic audit should catch regardless of which slot convention is used.

### Q6 — A team wants to deploy an upgradeable contract but is choosing between Transparent Proxy, UUPS, and Diamond. Walk through how you'd advise them.
**Testing:** applying the tradeoffs to an actual decision, not reciting definitions.
**Answer:** Default question first: do they actually need upgradeability at all, given it trades away code-immutability as a user-verifiable guarantee? Assuming yes: if the contract is comfortably under the 24KB size limit and doesn't need many independently-upgradeable modules, it's a Transparent-vs-UUPS choice — UUPS if the team has strong deployment-testing discipline and per-call gas cost genuinely matters at their expected transaction volume, Transparent Proxy if they want the simpler, harder-to-permanently-break safety margin and the marginal per-call gas cost is acceptable. Diamond only enters the conversation if they're actually hitting the size limit or have a genuine, specific need for many independently-upgradeable facets — reaching for it without that concrete constraint adds real complexity for no corresponding benefit.
**Follow-up trap:** *"What if they're not sure yet whether they'll need to exceed the size limit later?"* — starting with Transparent or UUPS and migrating to Diamond later if the size limit is actually hit is a more common and more tractable path than starting with Diamond's added complexity speculatively — the size limit is a hard, checkable constraint (compiler output tells you immediately when you're approaching it), so there's little cost to deferring the Diamond decision until it's an actual, not hypothetical, constraint.

### Q7 — Why are events cheaper than storage writes, and what's the actual tradeoff for that cheapness?
**Testing:** connecting events to module 4's gas-cost mechanics and the state-trie/receipts-trie distinction.
**Answer:** Event (log) data is written to the transaction's receipt, part of a separate receipts trie referenced from the block header — not part of contract storage or the state trie — so it doesn't carry storage's permanent-replication-and-persistence cost that makes `SSTORE` expensive (module 4). This is significantly cheaper gas-wise. The tradeoff: event data is not readable *on-chain*, by other contracts, at all — only off-chain indexers and clients watching logs can access it — so anything a contract itself needs to read back later must still live in actual storage, and events are purely a "communicate to the outside world" mechanism, never a substitute for state a contract's own logic depends on.
**Follow-up trap:** *"Could you save gas by storing data only in events and never in storage, if a contract needs to reference it later?"* — no, and this is a real, sometimes-attempted mistake: a contract's own functions cannot read event/log data at all, from any block, past or present — if contract logic needs to check or reference a value, it must be in storage (or reconstructible from calldata/parameters at call time), full stop; events are a one-way channel to off-chain observers only.

### Q8 — Design a CI check that would have caught the Parity-style delegatecall vulnerability, or a storage-layout-drift bug, before deployment.
**Testing:** turning the module's lessons into an actual engineering practice — staff-level signal.
**Answer:** Two separate checks. First, storage-layout drift: run `solc --storage-layout` (or the equivalent in the team's toolchain) against both the currently-deployed implementation and the proposed new one, and fail CI if any existing variable's slot, offset, or type changed — only appends should be allowed. Second, delegatecall-target auditing: any contract address a deployed contract might `delegatecall` to (whether hardcoded or configurable) should be enumerated and explicitly reviewed as part of the audit surface, with particular scrutiny on whether that target contract is independently, directly callable by anyone (the exact condition that made Parity's library exploitable) and whether its access control and destructibility have been independently verified — not assumed safe because "it's just a library."
**Follow-up trap:** *"What if the delegatecall target is only knowable at runtime, e.g., a beacon proxy pattern where the implementation address itself is fetched from another contract?"* — the audit surface then explicitly includes that beacon contract's own access control (who can change what it points to) as part of the same trust boundary — a beacon-pattern deployment where the beacon's update function has weak access control is exactly as exploitable as a hardcoded delegatecall to an unaudited contract, just with an extra layer of indirection obscuring that fact, which is precisely why it needs to be named explicitly in the review rather than assumed safe because it's "configurable."

### Q9 — Why does a mapping's actual data live at a `keccak256`-derived storage location instead of a predictable, sequential slot the way simple value types do?
**Testing:** whether the dynamic-storage mechanism (distinct from the packing rules covered earlier) is understood precisely.
**Answer:** A mapping has effectively unbounded size and arbitrary, sparse keys — there's no way to lay out "every possible key's value" contiguously starting from a fixed base slot the way a fixed-size struct's fields can be. Solidity instead computes each entry's actual storage location as `keccak256(key . baseSlot)` (the mapping's declared slot concatenated with the specific key, then hashed) — a location that's effectively unpredictable and collision-resistant across different keys, letting the mapping behave as if it had unlimited, sparsely-populated storage without needing to reserve space for keys that were never used.
**Follow-up trap:** *"Does this mean iterating over 'all entries in a mapping' is possible on-chain?"* — no, and this is a genuinely important, frequently-tripped-over consequence: because keys are hashed into effectively-unpredictable locations, there's no way for a contract to enumerate a mapping's keys from storage alone — any contract needing enumerable membership (e.g., "list every address that has ever staked") must maintain a separate, explicit array or linked structure alongside the mapping, tracked manually in the contract's own logic; the mapping alone never supports iteration, a common design gap in early or naive contract implementations.

### Q10 — A team ships a UUPS-upgradeable contract, and six months later discovers the *first* deployed implementation was missing the `initializer` modifier on its setup function. What's the actual risk, and why does this matter specifically for proxy-based contracts?
**Testing:** a specific, real, recurring proxy-pattern vulnerability class beyond the storage-collision and stuck-upgrade issues already covered.
**Answer:** Without a correctly-guarded initializer (typically OpenZeppelin's `initializer` modifier, which prevents a function from running more than once), anyone can call the unprotected setup function directly against the *implementation contract's own storage* (not the proxy's) if it's ever called outside the proxy's delegatecall context — and separately, if the *proxy's* own initialization was never actually protected against being called twice, an attacker calling it again post-deployment could reset ownership or critical configuration values to attacker-controlled addresses. This is a distinct, real vulnerability class from the storage-collision and stuck-upgrade risks covered earlier — it's specifically about ensuring one-time setup logic can never run twice, given that constructors (which naturally run-once) don't work the normal way for logic meant to execute in the proxy's storage context via delegatecall.
**Follow-up trap:** *"Why can't proxy-based contracts just use a normal Solidity constructor for initialization the way a non-upgradeable contract would?"* — a constructor only ever runs once, at the *implementation* contract's own deployment — but the implementation's constructor executes in the *implementation's* storage, not the proxy's (since delegatecall-based execution against the proxy's storage only happens for calls routed through the proxy after deployment, not during the implementation's own constructor execution) — meaning any state a constructor sets gets stored in the wrong place entirely for a proxy pattern to use. This is exactly why upgradeable contracts use a separate `initialize()` function, explicitly guarded against re-execution, called once through the proxy after deployment, instead of relying on a constructor at all.

---

## Red flags that fail you

- Describing `delegatecall` as "just like `call` but cheaper" rather than naming the storage-context distinction.
- Not knowing that storage variable declaration order affects gas cost via slot packing.
- Recommending a hand-rolled proxy implementation over OpenZeppelin's audited contracts without a specific, stated reason.
- Treating "smart contracts are immutable" as universally true without acknowledging upgradeable proxies are the mainstream production pattern.
- Not knowing that events are unreadable by on-chain contract logic, only by off-chain observers.
- Recommending Diamond pattern without the contract actually needing to exceed the size limit or needing genuine multi-facet modularity.

---

## Cheat card

```
STORAGE PACKING: slots are 32 bytes, DECLARATION ORDER matters. Compiler packs consecutive
  vars into one slot IF they fit together; starts new slot when next var wouldn't fit.
  Dynamic types (mapping/array/string/bytes) NEVER pack -- base slot + keccak256-derived data location.
  Every avoided slot ~= 20,000 gas saved (fresh SSTORE cost, module 4).

CALL vs DELEGATECALL (same calldata/gas forwarding, OPPOSITE context):
  call:         runs in CALLEE's storage, msg.sender = caller contract
  delegatecall: runs in CALLER's storage (!), msg.sender = UNCHANGED from outer call
  delegatecall = the entire proxy-upgradeability mechanism: proxy's storage,
  implementation's CODE. delegatecall to untrusted/mismatched code = handing over your storage.

PARITY HACK (Jul 2017, ~$150M+ frozen): multisig wallets delegatecalled a shared library;
  library was ALSO directly callable, had unprotected ownership-claim function, attacker
  became owner, selfdestructed it -> every dependent wallet's logic permanently gone.
  LESSON: never delegatecall to a contract not fully audited/access-controlled/trusted.

EVENTS: written to receipts trie (NOT storage/state trie) -- far cheaper than SSTORE.
  UNREADABLE by on-chain contract logic, ONLY off-chain indexers/clients. `indexed` params
  (max 3) become filterable "topics"; non-indexed = cheaper, in log data payload only.

EIP-1967 storage slots (VERIFIED via from-scratch Keccak-256, keccak256(label)-1):
  implementation: 0x360894a13ba1a3210667c828492db98dca3e2076cc3735a920a3ca505d382bbc
  admin:          0xb53127684a568b3173ae13b9f8a6016e243e63b6e8ee1178d6a717850b5d6103
  beacon:         0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50
  WHY not slot 0: would collide with implementation's own state vars (same delegatecall
  storage context) -- deep keccak-derived slots avoid realistic collision.

TRANSPARENT PROXY: admin-check logic lives in PROXY, runs EVERY call (small gas cost).
  Safe default: implementation can be arbitrarily buggy, upgrade path still works.
UUPS (OZ's current default): upgrade logic in IMPLEMENTATION (upgradeTo()). Cheaper
  per-call (no per-call admin check). RISK: broken/missing upgrade fn = PERMANENTLY stuck.
DIAMOND (EIP-2535): many independently-upgradeable "facets" behind 1 proxy, diamondCut()
  manages them. Solves 24KB contract SIZE LIMIT + true modularity. Less mature tooling,
  shared storage discipline needed across ALL facets. Minority choice -- only if size-limited.

DON'T default to upgradeable: immutability is a real, user-verifiable security property
  many audited DeFi primitives deliberately keep. Upgradeability trades that away.
```

## Sources

- [OpenZeppelin Docs — UUPS Proxy](https://docs.openzeppelin.com/contracts-stylus/uups-proxy) — accessed 2026-08-08
- [EIP-1967: Standard Proxy Storage Slots](https://eips.ethereum.org/EIPS/eip-1967) — accessed 2026-08-08
- [EIP-2535: Diamonds, Multi-Facet Proxy](https://eips.ethereum.org/EIPS/eip-2535) — accessed 2026-08-08
- [EIP-1822: Universal Upgradeable Proxy Standard (UUPS)](https://eips.ethereum.org/EIPS/eip-1822) — accessed 2026-08-08
- [Parity Technologies — Postmortem on the Parity multi-sig wallet library self-destruct](https://www.parity.io/blog/a-postmortem-on-the-parity-multi-sig-library-self-destruct/) — accessed 2026-08-08
- [Solidity Documentation — Layout of State Variables in Storage](https://docs.soliditylang.org/en/latest/internals/layout_in_storage.html) — accessed 2026-08-08
- [EIP-6780: SELFDESTRUCT only in same transaction](https://eips.ethereum.org/EIPS/eip-6780) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
