# Reentrancy, Overflow, Oracle Manipulation, Front-Running, Audits

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 4h · **Prereqs:** T22-smart-contracts · **Updated:** 2026-08-23
> **Module id:** `T22-contract-security` · **Tags:** blockchain, security, critical

## The 30-second version

Four bug classes account for most smart-contract losses, each with a mechanical fix. Reentrancy: any external call hands control to unknown code, so finalize state *before* interacting — the DAO lost 3.6M ETH in June 2016 to exactly this ordering error. Integer overflow stopped being a default hazard when Solidity 0.8 made arithmetic revert (December 2020), leaving narrowing casts and `unchecked` blocks as the residual risk. Oracle manipulation exploits the difference between a price you can shift and a price you can trust: flash-loan an AMM's spot price 10× in one transaction and borrow against the fake number — Mango Markets lost $110M in October 2022 this way, which is why production reads multi-source feeds (Chainlink deviation checks, Uniswap TWAPs) with staleness bounds. Front-running exists because the mempool is public by default; sandwiches extract from every naive swap, and the fixes are structural: slippage caps, private order flow, batch auctions, commit-reveal. Audits reduce risk measurably but historically don't prevent it — Euler passed multiple audits weeks before losing $197M — so layered defense (invariant fuzzing, monitoring, pausability, bounties) is the only honest answer.

## Why this gets asked

Because security questions double as code-review questions, and they're cheap to make concrete: hand the candidate ten lines of Solidity containing an external call before a subtraction and watch whether they see the reentrancy, whether they know two distinct fixes, and whether they can explain why the mutex version still loses to the effects-first version stylistically. Interviewers who shipped DeFi have personally triaged oracle incidents — a stablecoin peg drifting because someone read a thin pool — so follow-ups go straight to "how would you manipulate this price feed and how would you stop yourself." The audit question tests judgment rather than ritual: candidates who say "get an audit" as the whole answer reveal they've never been responsible for one; those who discuss what audits miss (economic bugs, composability, upgrade paths) and what caught things audits didn't (fuzzing found Euler-class issues elsewhere; monitoring limited Curve 2023 losses) demonstrate operating maturity.

## Lineage

**What came before.** Security thinking was forged in three early disasters. The DAO (June 2016): 3.6M ETH (~$50-60M then) siphoned through reentrant withdrawal loops; the community forked the chain to reverse it, birthing ETH/ETC and establishing that exploit response is political, not just technical. Parity (July 2017): a default-visibility function let anyone become owner of multisig wallets, draining ~150,000 ETH; its November sequel froze 513,000 ETH forever via an uninitialized library — teaching the industry initialization hygiene. BatchOverflow (April 2018): integer overflow minted absurd supplies in ERC-20s (BEC, SMT), prompting mass pauses and eventually Solidity 0.8's checked arithmetic. Each era added a permanent defense: reentrancy → CEI ordering plus mutexes; overflow → language-level checks; access control → role frameworks like OpenZeppelin AccessControl.

**Where it stands now.** The center of gravity moved from code-level bugs to economic-design exploits once flash loans arrived (2020): bZx's two February 2020 attacks (~$950k combined) demonstrated price-oracle manipulation without owned capital, and the genre scaled through 2021-22 — Cream, Badger, and culminating in Mango Markets' $110M (October 2022, perpetrator later convicted in the US in 2024) and Beanstalk's $182M flash-loan governance capture (April 2022, 67% of votes bought within one block). Curve's Vyper reentrancy incident (July 30, 2023, ~$70M) proved old classes never die when tooling fails — the compiler silently disabled `@nonreentrant` guards in versions 0.2.15/0.3.0. Euler Finance (March 2023, $197M) passed four documented audits weeks earlier; nearly all funds came back through negotiated whitehat disclosure, making it the case study for both audit insufficiency and response quality. Current stack: static analysis (Slither), invariant fuzzing (Foundry/Echidna/Medusa), symbolic execution (Certora, Halmos), real-time monitoring (Forta, Tenderly alerts), and bug bounties reaching $10M-class payouts (Wormhole's whitehat reward, 2023).

**Where it's heading.** Three directions. First, prevention shifts left into types and proofs: Move's resource semantics, increasingly standard formal verification on high-TVL cores, and compiler-guaranteed reentrancy patterns — high confidence for blue-chip protocols. Second, MEV defense industrializes: private order flow (Flashbots Protect, MEV Blocker), order-flow auctions paying users for their flow, batch auctions neutralizing sandwiches structurally (CoW Protocol), and application-level MEV taxes on chains like Arbitrum — the cat-and-mouse is converging toward users capturing their own extraction value. Third, response speed becomes a security control itself: sub-minute pause automation, on-chain circuit breakers with anomaly detectors, and standing whitehat relationships now determine loss sizes as much as prevention does; expect "time-to-pause" metrics in protocol risk dashboards.

---

## Mental model

```
INVARIANT THINKING: name what must ALWAYS be true, then ask which
line of code lets a hostile caller observe a moment when it isn't.

  solvency:   sum(balances) <= address(this).balance      <- DAO violated
  price:      collateral_value uses TRUSTED price          <- Mango violated
  fairness:   execution cannot depend on tx ORDER secrets <- sandwich violates

REENTRANCY     = state finalized after handing control away
ORACLE HACK    = trusting a price someone else can set
SANDWICH       = your trade visible before it executes
AUDIT GAP      = code verified, economics assumed
```

The unifying lens: blockchains execute adversarial code in shared state with perfect observability. Every vulnerability is a place where you handed one of three powers to an adversary — control flow (reentrancy), input values (oracles), or timing (MEV) — and every defense is taking that power back mechanically: effects-before-interactions takes back control flow; multi-source time-weighted prices take back inputs; privacy and batching take back timing.

---

## How it actually works

### Reentrancy — the canonical pair

```solidity
// ---------- VULNERABLE: the exact shape of the 2016 DAO ----------
contract VulnerableVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw(uint256 amount) external {
        require(balances[msg.sender] >= amount, "insufficient"); // CHECK
        (bool ok, ) = msg.sender.call{value: amount}("");        // INTERACTION
        require(ok, "failed");                                   //   <- control leaves;
        balances[msg.sender] -= amount;                          // EFFECT runs last:
    }                                                            // attacker reenters here
}

// ---------- ATTACKER ----------
contract Drainer {
    VulnerableVault immutable vault;
    constructor(Vault v) payable { vault = v; }

    function pwn() external {
        vault.deposit{value: 1 ether}();
        vault.withdraw(1 ether);                 // recursion happens in receive()
    }
    receive() external payable {
        if (address(vault).balance >= 1 ether)   // loop until vault is dry;
            vault.withdraw(1 ether);             // check stops infinite gas blowup
    }
}

// ---------- FIX A: checks-effects-interactions (preferred) ----------
contract CeVault {
    mapping(address => uint256) public balances;
    function withdraw(uint256 amount) external {
        uint256 bal = balances[msg.sender];
        require(bal >= amount, "insufficient");  // CHECK
        balances[msg.sender] = bal;              // EFFECT first: re-entry now sees 0
        (bool ok, ) = msg.sender.call{value: amount}("");
        require(ok, "failed");                   // INTERACTION last
    }
}

// ---------- FIX B: mutex belt-and-suspenders ----------
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";
contract GuardedVault is ReentrancyGuard {
    mapping(address => uint256) public balances;
    function withdraw(uint256 amount) external nonReentrant {   // lock during call
        // ... same body as Fix A ...
    }
}
```

Why the attacker's `receive` reverts under Fix A: by the time control returns, `balances[attacker]` is already zero, so the recursive `withdraw` fails its own check. Note the 2,300 wei gas stipend on plain transfers historically masked this class (CALL with empty data gives callees limited gas), which is why pre-Byzantium code got lucky; modern `call{value:}` forwards all remaining gas, making discipline mandatory.

Variant families interviewers probe: **cross-function** reentrancy (attacker reenters a *different* function sharing unfinalized state — mutex-per-function misses it), **cross-contract** reentrancy (token hooks: ERC-777 `tokensReceived`, ERC-721 `_safeMint` callbacks fire attacker code mid-flow), and **read-only reentrancy** (view functions report inconsistent state during a callback — Curve pools 2021-23: a lender reading virtual-price mid-transaction gets stale pricing). Defenses generalize: finalize ALL related state before ANY external call; treat every token transfer as potential code execution; never trust view outputs during callbacks without a reentrancy-lock on the source pool.

### Overflow — mostly solved, residually sharp

Pre-0.8 arithmetic wrapped mod 2²⁵⁶ silently: BatchOverflow (April 2018) multiplied three uint256s whose product exceeded the word size, minting 2⁵⁷-bit balances and destroying the tokens' markets within hours. Solidity ≥0.8 reverts on overflow automatically; `unchecked { }` opts out deliberately. What remains: narrowing casts (`uint256 → uint128` truncates high bits silently — always range-check before casting), assembly math, and *downstream* overflow where your safe value breaks an unaudited integration. Rule: treat every cast as an assertion site.

### Oracle manipulation — prices you can move vs prices you can trust

Spot prices from AMMs are attacker-settable: with reserves (x, y), swapping Δy moves price along x·y=k; a flash loan makes Δy free. bZx February 2020, first attack: borrow 10k ETH worth of sUSD → swap to WBTC → pump sUSD's Uniswap price → open a 5x-long sUSD position priced against the inflated pool → close at honest prices. Profit ~$230k on zero capital at risk; second attack days later brought the total near $950k. Mango Markets scaled it: October 11, 2022 — pump thin MNGO perpetual-spot books ~10× in minutes, post inflated MNGO as collateral, borrow $110M USDC. Convicted April 2024.

Defenses, in production order:

| Defense | Mechanism | Residual weakness |
|---|---|---|
| External feeds (Chainlink) | aggregated off-chain reports, deviation threshold (e.g., 0.5%) + heartbeat staleness checks | feed compromise/halt; l2 sequencer uptime flags |
| TWAP (Uniswap V3) | arithmetic-mean time-weighted average over ≥30 min windows | multi-block manipulation cost rises but isn't infinite on L2s with cheap blocks |
| Value bounds | per-block/per-user caps, global exposure caps | caps tuned wrong either strangle growth or leak |
| Circuit breakers | halt borrowing when price moves >X% in <Y minutes | governance of breaker parameters |

The interview-grade sentence: **never read a price from the same pool you settle against, never accept a spot price, always bound staleness and deviation.**

### Front-running and sandwiches — timing is the vulnerability

Public mempools let observers simulate pending transactions. Sandwich: place a buy before the victim's swap and a sell immediately after, capturing the victim's slippage minus fees — pure tax on naive routing. Historical scale: MEV extraction ran to hundreds of millions annually post-2020 (Flashbots quantified >$600M extracted on Ethereum by early 2022 era estimates). Defenses layered: user-side slippage tolerance and deadlines (weak alone — tight slippage fails trades), private submission (Flashbots Protect, MEV Blocker: pay builders directly, skip public mempool), batch auctions matching at uniform clearing prices (CoW Protocol: sandwiches need price *continuity* to work), and application-level MEV taxes (penalize same-block adjacency on chains like Arbitrum where ordering is deterministic). For admin/governance flows: commit-reveal schemes hide intent between commitment and revelation phases.

## Build it from scratch

Two runnable simulations, stdlib-only: a reentrancy drain with its fix, and spot-vs-TWAP manipulation economics. Both verified.

```python
"""Reentrancy drain + fix, and spot-vs-TWAP manipulation economics."""

class Revert(Exception): pass

class VulnerableVault:
    """The DAO shape: external call BEFORE the state update."""
    def __init__(self):
        self.balances, self.pool = {}, 0            # pool = physical ETH here

    def deposit(self, sender, amount):
        self.balances[sender] = self.balances.get(sender, 0) + amount
        self.pool += amount

    def withdraw(self, sender, amount, send=lambda to, amt: None):
        if self.balances[sender] < amount:
            raise Revert('insufficient')
        send(sender, amount)                        # ETH leaves HERE...
        self.balances[sender] -= amount             # ...ledger AFTER: bug

class Drainer:
    def __init__(self, vault):
        self.vault, self.loot, self.depth = vault, 0, 0

    def _send(self, to, amt):
        self.loot += amt
        self.vault.pool -= amt                      # vault REALLY empties now
        if self.vault.pool >= 1 and self.depth < 300:
            self.depth += 1
            self.vault.withdraw(to, 1, send=self._send)   # REENTER

    def pwn(self):
        self.vault.deposit('attacker', 1)
        try:
            self.vault.withdraw('attacker', 1, send=self._send)
        except Revert:
            pass                                    # ends when vault is dry

v = VulnerableVault()
v.deposit('alice', 10); v.deposit('bob', 90)
d = Drainer(v); d.pwn()
assert v.pool == 0 and d.loot == 101               # every wei gone
assert v.balances['alice'] == 10                   # ledger still claims she's paid!

class FixedVault(VulnerableVault):                 # effects-before-interactions
    def withdraw(self, sender, amount, send=lambda to, amt: None):
        if self.balances[sender] < amount:
            raise Revert('insufficient')
        self.balances[sender] -= amount            # EFFECT FIRST
        self.pool -= amount
        send(sender, amount)                       # INTERACTION LAST

v2 = FixedVault(); v2.deposit('alice', 10); v2.deposit('bob', 90)
d2 = Drainer(v2); d2.pwn()
assert d2.loot == 1 and v2.pool == 99              # only their own deposit back
```

```python
# ---------- oracle: free instant spot attack vs costly TWAP attack ----------
class Pool:
    """Constant-product pool; price quoted as token-a price in token-b units."""
    def __init__(self, x, y): self.x, self.y = x, y
    @property
    def price(self): return self.y / self.x          # b per one a
    def swap_b_for_a(self, dy):
        dx = self.x - self.x * self.y / (self.y + dy)
        self.y += dy; self.x -= dx

def twap_after_spike(spike, dur_s, window_s=1800, base=1.0):
    return ((window_s - dur_s) * base + dur_s * spike) / window_s

p = Pool(1_000_000, 1_000_000)                     # fair price 1.0
p.swap_b_for_a(9_000_000)                          # one flash-funded swap...
spot = p.price                                     # -> exactly 100x, instantly
t12 = twap_after_spike(spike=spot, dur_s=12)       # one block inside 30-min window
t60 = twap_after_spike(spike=spot, dur_s=60)
assert round(t12, 2) == 1.66 and round(t60, 2) == 4.3
```

Output teaches both lessons mechanically: the vulnerable vault ends at zero ETH while its ledger still claims alice holds her 10 — accounting fiction is precisely what reentrancy exploits — and the fixed version returns only the attacker's own deposit. The oracle numbers kill two myths: spot prices move 100× for the cost of one transaction, but TWAPs are not magic either — twelve seconds of manipulation inside a 30-minute window still shifts the average +66%, which is why production pairs windows with deviation caps, multi-source feeds, and circuit breakers instead of trusting any single mechanism.

## How it's done in production

Defense-in-depth stack, roughly in deployment order:

| Layer | Tools | What it catches |
|---|---|---|
| Static analysis | Slither, Semgrep rules | reentrancy shapes, uninitialized storage, tx.origin auth |
| Unit + property tests | Foundry/Hardhat | logic errors; invariants asserted per-test |
| Invariant fuzzing | Foundry invariants, Echidna, Medusa | sequences breaking solvency/conservation invariants |
| Symbolic/formal | Certora, Halmos, Kontrol | exhaustive proofs on core paths (standard for high-TVL) |
| Economic review | manual, adversarial modeling | oracle design, liquidation cascades, governance capture |
| Audit | 1-4 firms, ~$50k-500k+ each, 2-6 weeks | known patterns; report quality varies widely |
| Monitoring | Forta bots, Tenderly alerts, balance-diff watchers | live anomalies within seconds-to-minutes |
| Response | pausable guards, circuit breakers, whitehat channels, bounties ($10M-class via Immunefi) | loss containment once prevention failed |

Post-incident table of what people actually saw:

| Symptom in logs | Incident | Root cause class |
|---|---|---|
| Balance drained via repeated fallback invocations | The DAO 2016 (3.6M ETH) | reentrancy ordering |
| Tokens minted to astronomic supply | BatchOverflow 2018 (BEC/SMT) | integer overflow pre-0.8 |
| Borrowed max against collateral pumped minutes earlier | Mango Markets 2022 ($110M) | manipulable oracle |
| Governance proposal passed with borrowed votes in one block | Beanstalk 2022 ($182M) | flash-loan governance capture |
| Pool drained days after "clean" audits | Euler 2023 ($197M, mostly returned) | economic bug audits missed |
| Pools drained despite battle-tested math | Curve/Vyper 2023 (~$70M) | compiler disabled reentrancy guards |

The uncomfortable pattern for interviews: audits catch code bugs imperfectly and economic designs worse. Curve's pools had been audited repeatedly before a *compiler* regression silently undid their `@nonreentrant` guards (Vyper 0.2.15/0.3.0), and Euler's exploit came through a donation/convertible sub-account interaction no reviewer modeled despite four documented audit reports. Modern risk committees therefore weight invariant-fuzzing coverage, monitoring latency, and time-to-pause alongside audit reports.

## Tradeoffs & when NOT to use it

- **Audits are necessary, never sufficient.** An audit covers a code snapshot under time pressure; upgrades, integrations, and market conditions change daily afterward. Continuous programs beat point-in-time certificates.
- **Pausability is centralized power.** A guardian key that freezes transfers can be captured or coerced; some protocols deliberately ship pause-less cores for neutrality. Decide explicitly, don't default.
- **Over-tight oracles strangle products.** Aggressive staleness/deviation thresholds halt markets during exactly the volatility users need them for; tune breakers against measured volatility percentiles.
- **Private mempools reorder trust**: Flashbots-class submission adds availability and censorship-adjacent dependencies; batch auctions change price semantics to uniform clearing. Each MEV defense relocates the problem rather than deleting it.
- **Mutexes hide rather than fix**: sprinkling `nonReentrant` can mask shared-state reasoning errors and blocks legitimate flows like flash-loan callbacks. Effects-first ordering stays primary; the mutex is belt-and-suspenders.
- **Formal verification pays only on small, stable cores.** Proving an AMM's swap math is tractable and worth it; proving a composable lending market is a research project. Scope proofs to invariants that matter (solvency, conservation), not whole systems.

## Interview questions

### Q1 — Find the bug in this contract and fix it two ways.
**Testing:** live code reading; the core screening exercise.
**Answer:** The `withdraw` makes an external call before deducting balances: reentrancy. Fix A — checks-effects-interactions: zero the balance before `call`, so re-entry fails its own check. Fix B — OpenZeppelin's `nonReentrant` mutex. Prefer A as primary (works for cross-function variants a per-function mutex misses) with B layered on critical paths.
**Follow-up trap:** *"Why not just use transfer() instead of call?"* — transfer forwards only 2,300 gas, historically breaking fallbacks; it also breaks multisig wallets that need more gas to receive. It was deprecated in practice for good reason; the fix is ordering, not gas starvation.

### Q2 — Explain cross-contract reentrancy with an ERC-777 or ERC-721 example.
**Testing:** beyond the textbook same-function loop.
**Answer:** Tokens with hooks execute attacker code during transfers: ERC-777 fires `tokensReceived` inside `transfer`, ERC-721 `_safeMint` calls `onERC721Received`. A protocol mid-invariant (e.g., updating collateral accounting after initiating a token move) gets interrupted at its most inconsistent moment. Curve-class pools and lending markets guard by finalizing all accounting before ANY token movement, or holding a reentrancy lock across the whole flow.
**Follow-up trap:** *"Does Solidity 0.8 or a mutex save you?"* — No: this isn't arithmetic and often crosses contracts where one mutex doesn't reach. The defense is architectural: no external calls while invariants are temporarily violated.

### Q3 — What is read-only reentrancy? Give the Curve scenario.
**Testing:** current-generation depth.
**Answer:** View functions can report inconsistent state during an ongoing callback: attacker triggers a state-changing operation on pool X; during X's callback, calls into victim V which reads X's view (get_virtual_price); V prices against a stale/intermediate value. Curve pools patched by adding nonReentrant locks to view functions themselves. General rule: views consumed by OTHER protocols are attack surface too.
**Follow-up trap:** *"How do you find these systematically?"* — Model view functions as untrusted inputs during threat modeling; fuzz harnesses that interleave callbacks against views; Slither has detectors for modifiers missing on views used cross-contract.

### Q4 — Walk me through manipulating an AMM spot oracle end-to-end, then defend it.
**Testing:** adversarial thinking plus engineering maturity.
**Answer:** Attack: flash-borrow massive token B; swap into the target pool shifting reserves (constant product: price moves quadratically with reserve ratio); protocol reads `reserves`-derived price and lends/mints against inflated collateral; unwind swap; repay loan; keep profit. Cost ≈ fees on two large swaps. Defense: never settle against your own pool's spot; Chainlink-style feeds with deviation thresholds (~0.5%) and heartbeat staleness checks; Uniswap V3 TWAP over ≥30 minutes; per-block exposure caps; circuit breakers on fast moves.
**Follow-up trap:** *"Is TWAP enough?"* — No: our simulation shows one manipulated block shifts a 30-minute average ~66%. TWAP raises attack cost (capital must stay deployed across blocks) rather than eliminating manipulation; combine windows with caps and breakers.

### Q5 — Mango Markets lost $110M. Reconstruct the mechanics and what design would have prevented it.
**Testing:** real-incident analysis with numbers.
**Answer:** October 11, 2022: attacker built a large long position on MNGO perpetuals, then pumped MNGO's thin FTT-listed spot books roughly 10× within minutes; the inflated mark price made their perp position show huge unrealized profit usable as collateral; they borrowed ~$110M USDC against it and walked. Design failures: thin-market mark pricing, no deviation circuit breaker, unlimited borrow against manipulated collateral. Preventers: multi-venue median marks, price-band limits rejecting >X% deviations, borrow caps per asset, and treating illiquid tokens' collateral factors as near-zero.
**Follow-up trap:** *"Wasn't that 'legal alpha' though?"* — Courts disagreed: the perpetrator was convicted of fraud/manipulation in April 2024. But smart-contract design must assume the hostile version regardless of legal outcomes; code cannot subpoena.

### Q6 — How exactly does a sandwich attack work, and what actually stops it?
**Testing:** MEV literacy with practical fixes.
**Answer:** Observer sees victim's swap in the public mempool; front-runs with a buy, victim executes at worse price, back-run sells into the moved pool — extracting victim slippage minus fees, risk-free-ish. Real stops: private order flow (Flashbots Protect / MEV Blocker bypass the public mempool entirely), batch auctions with uniform clearing prices (CoW-style: no intermediate price to sandwich), tight-but-not-fatal slippage bounds, and application-level MEV taxes penalizing adjacency. Education point: slippage settings alone trade user experience against extraction.
**Follow-up trap:** *"Isn't back-running benign arbitrage?"* — Price-alignment back-runs are arguably healthy; the harm concentrates in insertion BEFORE user flow (frontrunning/sandwiching). Order-flow auctions that PAY users for their flow are the current market answer to that distinction.

### Q7 — Why did Euler happen despite four audits?
**Testing:** audit-model realism.
**Answer:** March 13, 2023: $197M drained via the donation/convertible sub-account mechanism — self-liquidation interactions whose economic composition wasn't modeled as dangerous; audits verify specified behavior against known patterns, not novel compositional economics. Notably the attacker was later identified and negotiated: nearly all funds returned (whitehat settlement), making Euler simultaneously an audit-failure and response-success case.
**Follow-up trap:** *"So why pay for audits at all?"* — They reliably catch whole classes (access control, reentrancy, overflow remnants) and their absence is negligence; the failure mode is treating coverage as proof. Layer: fuzz invariants + formal specs on cores + monitoring, with audits as one input among five.

### Q8 — Beanstalk lost $182M through governance. Mechanics?
**Testing:** recognizing governance as attack surface.
**Answer:** April 17, 2022: attacker flash-loaned ~$1B in assets to acquire 67% of Beanstalk's governance weight within ONE block, voted an emergency proposal transferring the treasury to themselves, executed, repaid the flash loan — netting $182M in seconds. Root cause: token-weighted voting with instant finality and no delay between voting power acquisition and execution.
**Follow-up trap:** *"Fix?"* — Time-locks between vote acquisition and execution (snapshots, multi-block voting), proposal thresholds decoupled from transferable tokens, and emergency-action multisigs with independent legitimacy. Flash loans make 'temporary majority' cheap, so governance must be temporally expensive.

### Q9 — Solidity 0.8 made overflow revert. What integer bugs remain reachable?
**Testing:** updated mental model, not 2018 flashcards.
**Answer:** Narrowing casts truncate silently (uint256→uint128 drops high bits — always range-check), `unchecked` blocks wrap deliberately, assembly arithmetic is raw, and downstream integrations may overflow on values safe in yours. BatchOverflow-class ERC-20 disasters (BEC/SMT, April 2018) are extinct in modern compilers but live forever in deployed legacy code you compose with.
**Follow-up trap:** *"Show me a real truncation exploit."* — Depositing amounts near 2¹²⁸ boundaries into systems storing balances as uint128: deposit twice such that the first sets high bits the second's cast clears, netting accounting drift. Fuzzing with boundary values catches it; typical unit tests don't.

### Q10 — Design the monitoring and response stack for a lending protocol post-launch.
**Testing:** operations maturity beyond prevention.
**Answer:** Detection: Forta/Tenderly anomaly alerts (TVL drop %, utilization spikes, oracle deviation events, unusual large borrows), balance-diff watchers on treasury and key pools, simulation of every pending governance proposal. Response: pausable guards with clear authority matrix, automated circuit breakers on oracle deviation, pre-authorized whitehat relationships and bounty terms ($10M-class via Immunefi now standard for top TVL), and rehearsed runbooks — Euler's negotiated return succeeded partly because response channels existed. Measure time-to-pause as a first-class SLO.
**Follow-up trap:** *"Who holds pause keys?"* — Multisig of responsive signers with documented quorum SLAs; too few signers = single point, too many = too slow. Rehearse: an untested pauser path fails exactly when needed.

### Q11 — Compare audit, fuzzing, and formal verification: cost, coverage, failure modes.
**Testing:** tooling judgment at staff level.
**Answer:** Audit: ~$50k-500k+ per firm, 2-6 weeks, human-pattern coverage, misses novel economics (Euler). Invariant fuzzing: cheap to run continuously, finds state-machine violations (solvency, conservation) humans skip, but only explores what harnesses allow. Formal verification: exhaustive over specified properties (Certora/Halmos on AMM math, vault accounting), high per-property cost, guarantees nothing about specs being wrong or code outside scope. Stack all three on cores; audits alone nowhere.
**Follow-up trap:** *"What did fuzzing catch that audits didn't?"* — Order-dependent liquidation insolvencies and donation-edge cases across DeFi repeatedly surfaced via Foundry/Echidna invariant runs after clean audit reports; conversely fuzzing can't see missing-feature design flaws at all.

### Q12 — What makes flash loans an attack amplifier rather than a vulnerability?
**Testing:** precise causal reasoning.
**Answer:** Flash loans add unbounded temporary capital within one transaction: any capital-gated attack (price manipulation, governance capture, self-liquidation arbitrage) drops its barrier from millions to transaction fees. They're atomic — either repay or whole tx reverts — so they introduce no NEW bug class, they weaponize existing ones: manipulable oracles, temporally-naive governance, mispriced collateral. Fix the underlying flaw; banning flash loans is whack-a-mole (they also power legitimate refinancing).
**Follow-up trap:** *"Should protocols block flash-loan callbacks?"* — Some do (reentrancy locks incidentally block them) as defense-in-depth, but sophisticated attackers route through composability anyway. Economic design must assume free temporary capital; say that sentence.

### Q13 — A stablecoin protocol reads Chainlink. Which checks make it safe? What remains?
**Testing:** production oracle integration specifics.
**Answer:** Required checks: `latestRoundData` staleness vs heartbeat (e.g., 1h for majors), answered-in-round sanity, price >0, sequencer uptime feed on L2s (else stale prices during sequencer downtime), and deviation-from-last-value bounds. Remaining risks: feed-wide compromise/halt, asset-specific feed absence forcing synthetic pricing, L2 data-latency windows. Defense: median across independent providers, emergency manual feeds behind timelock, and circuit breakers treating oracle silence as halt condition.
**Follow-up trap:** *"Why not just multiple Chainlink feeds?"* — Correlated infrastructure: same node operators, same aggregation logic. Independence requires heterogeneous sources (different provider classes, TWAP cross-checks); correlation analysis belongs in the risk doc.

### Q14 — You find a critical exploit in a live protocol. Walk through responsible disclosure on-chain.
**Testing:** ethics plus practical whitehat mechanics.
**Answer:** Options ladder: (1) if a bug bounty exists, follow its process immediately — Immunefi handles identity/escrow; (2) exploit-and-return whitehat style: drain funds to safety to prevent attacker theft, then negotiate return + reward publicly (Euler 2023 precedent, mostly-clean recovery); (3) contact team via security@/keybase with PoC, no exploitation. Never: partial theft, extortion timelines, or disclosure without fix window. Legal exposure varies by jurisdiction; document intent to return contemporaneously.
**Follow-up trap:** *"Team ignores your report?"* — Escalate via bounty platform arbitration; public disclosure deadlines (90-day norms) after fix window lapses; on-chain whitehat rescue becomes defensible when user funds face imminent third-party theft and no response arrives — each step needs timestamped evidence.

### Q15 — Rank reentrancy, overflow, oracle manipulation, front-running by current loss frequency and explain the shift.
**Testing:** calibrated view of where losses actually come from in 2025-26.
**Answer:** Current ranking by realized damage: 1) oracle/economic manipulation, 2) access-control/key compromise, 3) front-running/MEV extraction (chronic tax more than episodic loss), 4) reentrancy (rare solo, appears when tooling fails — Curve/Vyper 2023), 5) overflow (near-extinct in new code). The shift: language-level fixes deleted old classes while composable economics created bigger targets; 2022-25 mega-losses skew overwhelmingly toward economic design and operational security, not opcode-level bugs.
**Follow-up trap:** *"So stop teaching reentrancy?"* — No: it's the pedagogical gateway to state-machine thinking, and compiler/tooling regressions resurrect 'dead' classes (Vyper 2023). Teach the class as the pattern; allocate defensive budget by current threat data.

## Red flags

- Hand-waving "we'll get an audit" as the security plan.
- Not spotting external-call-before-state-update in provided code.
- Claiming Solidity 0.8 eliminated integer-related exploits entirely.
- Reading spot prices from AMM pools without mentioning manipulation.
- Confusing front-running prevention with slippage settings alone.
- No answer for who can pause, upgrade, or change oracle feeds in their own designs.
- Treating flash loans as the root cause of Mango/Beanstalk rather than the amplifier.
- Suggesting transfer()/send() gas-stipend tricks as reentrancy protection today.

## Cheat card

```
REENTRANCY     external call -> control leaves -> finalize state BEFORE
               checks-effects-interactions (primary) + nonReentrant mutex
               variants: cross-function, cross-contract (ERC-777/721 hooks),
               read-only (Curve views) - mutex-per-fn misses them all
OVERFLOW       0.8+ reverts by default · residual: narrowing casts, unchecked,
               assembly, legacy deployed tokens (BatchOverflow BEC/SMT 4/2018)
ORACLE         spot price = attacker-settable via flash loan (bZx 2/2020 ~$950k)
               Mango 10/2022: $110M vs 10x-pumped thin books
               DEFEND: Chainlink deviation ~0.5% + heartbeat staleness,
               Uniswap V3 TWAP >=30min, caps, breakers - TWAP alone: +66%
               shift from ONE manipulated block in a 30-min window
MEV            public mempool => sandwich = front-run + victim + back-run
               DEFEND: private orderflow (Flashbots Protect/MEV Blocker),
               batch auctions (CoW), commit-reveal, MEV taxes
FLASH LOANS    amplifier not vuln: capital barrier -> tx fees (Beanstalk $182M
               governance capture, 67% votes in one block, 4/2022)
AUDITS         $50k-500k+/firm · 2-6 weeks · snapshot only
               Euler 3/2023 $197M after FOUR audits (economic composition)
               Curve/Vyper 7/2023 ~$70M: compiler killed @nonreentrant
STACK          Slither -> Foundry/Echidna invariants -> Certora/Halmos proofs
               -> Forta/Tenderly monitoring -> pause + bounty ($10M Immunefi)
METRIC         time-to-pause is the SLO that bounds loss once prevention fails
```

## Sources

- [Reentrancy Attack — Solidity documentation security considerations](https://docs.soliditylang.org/en/latest/security-considerations.html); accessed 2026-08-23
- [The DAO post-mortem analysis — vessenes.com and Ethereum Foundation history](https://blog.ethereum.org/2016/07/20/forking-ethereum); accessed 2026-08-23
- [bZx oracle manipulation attacks explained — PeckShield/Chainalysis analyses, Feb 2020](https://www.chainalysis.com/blog/defi-flash-loans/); accessed 2026-08-23
- [Mango Markets exploiter convicted — CoinDesk, April 2024](https://www.coindesk.com/legal/2024/04/11/jury-finds-avi-eisenberg-guilty-of-fraud-in-mango-markets-case); accessed 2026-08-23
- [Euler Finance exploit and negotiated return — Chainalysis, 2023](https://www.chainalysis.com/blog/euler-finances-exploiter-returns-funds/); accessed 2026-08-23
- [Curve/Vyper reentrancy incident July 2023 — Vyper GitHub advisory](https://github.com/vyperlang/vyper/security/advisories/GHSA-3xgq-45jj-v275); accessed 2026-08-23
- [Beanstalk flash-loan governance attack — Rekt news, April 2022](https://rekt.news/beanstalk-rekt/); accessed 2026-08-23
- [Flashbots MEV extraction quantification — Flashbots transparency dashboard](https://explore.flashbots.net/); accessed 2026-08-23
- [Immunefi bug bounty landscape and Wormhole $10M payout](https://immunefi.com/); accessed 2026-08-23
- [OpenZeppelin ReentrancyGuard contract docs](https://docs.openzeppelin.com/contracts/5.x/api/utils#ReentrancyGuard); accessed 2026-08-23

## Changelog

- 2026-08-23 — created





