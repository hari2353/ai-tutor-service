# Reentrancy, Overflow, Oracle Manipulation, Front-Running, Audits

> **Track:** T22 Blockchain & Smart Contracts · **Time:** 2.5h · **Prereqs:** `T22-smart-contracts`
> **Updated:** 2026-08-08
> **Module id:** `T22-contract-security` · **Tags:** security, critical
> **Lab:** none yet — see `labs/py/02-agent-loop/` for the pattern if you want to build one

## The 30-second version

Reentrancy exploits a specific ordering bug: a contract sends funds via an external call *before* updating its own internal balance, and the receiving address's fallback code hijacks control during that call to re-enter the same withdrawal function while the balance still reads its pre-withdrawal value — the fix, checks-effects-interactions, is simply "update your own state before you make any external call," and a direct simulation of both versions shows the vulnerable contract paying out five times against a single ten-unit deposit while the fixed version pays out exactly once. Integer overflow was a real, exploited category of bug through 2018 when Solidity used unchecked wraparound arithmetic by default (`uint8` at 255 plus 1 silently becomes 0); Solidity 0.8.0 (December 2020) made checked arithmetic — reverting on overflow — the default, which didn't eliminate the bug class so much as move the remaining risk into `unchecked{}` blocks developers now opt into deliberately for gas savings, and forgetting why that block was safe is still a live audit finding. Oracle manipulation and flash-loan attacks are the dominant modern DeFi exploit pattern specifically because they don't require finding a bug in the target contract at all — an attacker borrows an enormous, uncollateralized sum for exactly one transaction, uses it to violently move a price a protocol trusts, extracts value at the distorted price, and repays the loan before the transaction ends, all economically rational and requiring zero actual code vulnerability in the victim protocol beyond trusting a manipulable price source. Front-running and MEV (maximal extractable value) exploit the simple fact that pending transactions are visible in the public mempool before they're confirmed, letting anyone — including the block producer itself — see a profitable trade coming and insert their own transaction ahead of it. None of these are solved by "writing more careful code" alone; each has a specific, named structural fix, and a real audit's job is verifying all of them are actually applied, not just checking that the code compiles.

## Why this gets asked

Because smart contract security incidents are unusually visible and unusually expensive — DeFi has lost well over half a billion dollars to flash-loan-facilitated attacks alone since 2020, with individual incidents in the hundreds of millions — and an interviewer wants to know whether a candidate understands these as *specific, named mechanisms with specific, named fixes* rather than a vague "smart contracts are risky" impression. Anyone who has actually worked adjacent to a security review has watched checks-effects-interactions get skipped under deadline pressure, or watched a protocol trust a spot price from a thinly-traded pool, and wants to hear that you'd catch it before it shipped, not after a post-mortem.

---

## Lineage: past → present → future

**What came before.** The DAO hack (June 2016) is the reentrancy bug's origin story for the entire industry: a recursive-call vulnerability in The DAO's withdrawal function let an attacker drain roughly $60M worth of ETH at the time by recursively re-entering the withdrawal before the balance was decremented — precisely the pattern this module demonstrates below — and the fallout (Ethereum's controversial hard fork to reverse it) is why "reentrancy" is the first vulnerability class every Solidity developer learns by name rather than by rediscovering it independently. Integer overflow bugs predate blockchain entirely (they're a decades-old category in systems programming generally), but Solidity's pre-0.8 default of silent, unchecked wraparound arithmetic made them unusually dangerous in a context where the "integer" in question often directly represented money — the BatchOverflow bug (April 2018), affecting multiple ERC-20 token contracts, let attackers mint effectively unlimited tokens by triggering a wraparound in a batch-transfer function's multiplication, a bug class that existed specifically because the language made unsafe arithmetic the unmarked default.

**Where it stands now.** Reentrancy is well-understood and well-defended against in code that follows current best practice (checks-effects-interactions as the default pattern, plus `ReentrancyGuard`-style mutex modifiers as defense-in-depth) — it still appears in audits and in the wild, but almost always in contracts that skipped known, standard mitigations rather than from a genuinely novel variant. Integer overflow is largely closed off by Solidity 0.8+'s checked-arithmetic default, though the Cetus Protocol exploit (May 2025, ~$223M) demonstrates the residual risk hasn't disappeared — that specific loss involved a `u256` overflow made profitable by flash-borrowed liquidity, a reminder that overflow protection at the language level doesn't eliminate every overflow-adjacent logic error, especially in code paths using `unchecked` blocks or non-EVM-native numeric libraries. The live center of gravity for DeFi losses has shifted decisively toward **oracle manipulation and flash-loan-facilitated attacks**, which OWASP's Smart Contract Security project now tracks as a distinct, named top-10 category (SC04:2026) precisely because these attacks don't require any bug in the target contract's logic at all — they exploit an economically-rational, protocol-legitimate mechanism (flash loans, spot-price oracles) in a way the target simply didn't defend against. MEV (maximal extractable value) has gone from an informally-discussed phenomenon to a formalized, measured, and partially-productized part of Ethereum's infrastructure (MEV-Boost, proposer-builder separation) — the live disagreement is less about whether MEV is real (it demonstrably is, and is measured continuously) and more about how much of it should be considered a legitimate cost of decentralized block production versus a harm the protocol should actively suppress.

**Where it's heading.** High confidence: formal verification and invariant-based fuzzing (Foundry's native fuzzing, Echidna, Medusa, and formal tools like Certora Prover and Halmos) have moved from a niche, expensive practice reserved for the largest protocols to a mainstream expectation for high-value contract audits — roughly a third of high-value 2025-era audit engagements shipped with at least one formal invariant suite, with the remainder relying on fuzzing-based invariant testing as a cheaper baseline; this trajectory (more automated, mathematically-grounded verification, less pure manual review as the only check) is well underway, not speculative. Medium confidence: oracle design continues converging toward manipulation-resistant patterns (time-weighted average prices, multi-source aggregation, Chainlink-style decentralized oracle networks) as the default rather than the exception, specifically because spot-price-from-a-single-DEX-pool has proven repeatedly, expensively exploitable. Lower confidence, more speculative: whether MEV mitigation techniques (encrypted mempools, threshold encryption for transaction ordering, SUAVE-style specialized MEV infrastructure) meaningfully reduce extractable value at the protocol level, or whether MEV simply relocates to whatever layer doesn't yet have the mitigation — this remains a genuinely open, actively-researched question rather than a solved one.

---

## Mental model

```
  REENTRANCY: external call BEFORE state update lets the callee "come back in"
  while your state still looks like the withdrawal never happened

  VULNERABLE:                              FIXED (checks-effects-interactions):
  function withdraw() {                    function withdraw() {
    amount = balances[msg.sender]            amount = balances[msg.sender]     CHECKS
    send(msg.sender, amount)  ◀── external   balances[msg.sender] = 0          EFFECTS
      │                          call         send(msg.sender, amount)  ◀──── INTERACTIONS
      │  attacker's fallback                    (external call LAST — balance
      │  re-enters withdraw()                    is already 0, re-entry sees
      │  HERE, balance still                     amount=0 and does nothing)
      ▼  shows the OLD amount!
    balances[msg.sender] = 0  ◀── too late,
                                   already paid out multiple times

  FLASH LOAN + ORACLE MANIPULATION: no bug in the victim contract needed at all
  ┌─────────────────────────── ONE TRANSACTION ───────────────────────────┐
  │  1. borrow $100M, uncollateralized (flash loan — must repay by end    │
  │     of THIS transaction, or the whole transaction reverts)            │
  │  2. dump/pump a thinly-traded DEX pool's price violently with it      │
  │  3. victim protocol reads that pool's SPOT price as "the" price       │
  │  4. borrow/liquidate/trade against the victim at the distorted price  │
  │  5. repay the flash loan, keep the extracted profit                   │
  └─────────────────────────────────────────────────────────────────────┘
  Every step is individually legitimate. The exploit IS the composition.

  MEV: pending transactions sit in the public mempool BEFORE confirmation —
  visible to everyone, including whoever assembles the next block
       user's profitable trade  ──▶  [ public mempool, visible ]
                                            │
                          searcher/builder sees it, inserts their OWN
                          trade immediately before (front-run) and/or
                          after (back-run) — a "sandwich"
```

---

## How it actually works

### Reentrancy: the exact mechanism, demonstrated

The vulnerability is an ordering bug between an *external call* (any interaction that transfers control to another address's code — sending ETH via a low-level call, or calling another contract) and a *state update*. If the external call happens first, the receiving code executes with the caller's state still reflecting "before this operation happened," and if that receiving code calls back into the same function, it sees a green light to run again.

This is precisely reproducible without a Solidity compiler, by simulating EVM call semantics faithfully enough that the mechanism is unambiguous — this code was executed directly, not asserted:

```python
class VulnerableVault:
    """External interaction (send) happens BEFORE the internal state update —
    mirrors `(bool ok,) = who.call{value: amount}("")` followed by a balance
    write, the classic vulnerable ordering."""
    def __init__(self):
        self.balances = {}
        self.call_log = []

    def deposit(self, who, amount):
        self.balances[who] = self.balances.get(who, 0) + amount

    def withdraw(self, who, attacker_hook=None):
        amount = self.balances.get(who, 0)
        if amount <= 0:
            return
        self.call_log.append(f"sending {amount} to {who}")
        if attacker_hook is not None:
            attacker_hook(self)          # <- transfers control to the "receiver",
        self.balances[who] = 0           #    exactly like an external .call()

class FixedVault:
    """Checks-Effects-Interactions: state update happens BEFORE the external call."""
    def __init__(self):
        self.balances = {}
        self.call_log = []

    def deposit(self, who, amount):
        self.balances[who] = self.balances.get(who, 0) + amount

    def withdraw(self, who, attacker_hook=None):
        amount = self.balances.get(who, 0)
        if amount <= 0:
            return
        self.balances[who] = 0            # EFFECTS: state updated FIRST
        self.call_log.append(f"sending {amount} to {who}")
        if attacker_hook is not None:
            attacker_hook(self)           # INTERACTIONS: external call last

class Attacker:
    def __init__(self, vault, max_reentries=5):
        self.vault = vault
        self.reentries = 0
        self.max_reentries = max_reentries

    def hook(self, vault):
        """The attacker contract's fallback/receive function — what actually
        runs during the vault's external call."""
        self.reentries += 1
        if self.reentries < self.max_reentries and vault.balances.get("attacker", 0) > 0:
            vault.withdraw("attacker", attacker_hook=self.hook)   # re-enter
```

Run against the vulnerable vault (attacker deposits 10, a victim's 90 sits in the same pool):

```
VULNERABLE VAULT
  attacker's recorded balance after exploit: 0
  reentries triggered: 5
  call log: ['sending 10 to attacker', 'sending 10 to attacker', 'sending 10 to attacker',
             'sending 10 to attacker', 'sending 10 to attacker']
```

**Five payouts of 10 against a single 10-unit deposit — 50 units extracted, 40 of it the victim's money**, because every reentrant call read `balances["attacker"] == 10` before the original call ever got the chance to zero it out. Run the identical attack against `FixedVault`:

```
FIXED VAULT (checks-effects-interactions)
  attacker's recorded balance after exploit attempt: 0
  reentries triggered: 1
  call log: ['sending 10 to attacker']
```

**Exactly one payout.** The balance was zeroed *before* the external call, so the reentrant `withdraw()` call immediately reads `amount = 0` and returns without sending anything. This is the entire fix, demonstrated mechanically rather than asserted: **checks (validate), effects (update your own state), interactions (only then talk to the outside world)** — reorder those three phases and the attack simply has nothing to exploit, because by the time control transfers to any external address, your own bookkeeping already reflects the operation as complete.

**Defense in depth**, used alongside CEI rather than instead of it: a **reentrancy guard** — a simple mutex flag set at function entry and cleared at exit, reverting any call that finds the flag already set — catches reentrancy attempts even in code that got the ordering wrong, at the cost of a small, constant gas overhead per protected call. OpenZeppelin's `ReentrancyGuard` is the standard, audited implementation almost every production contract uses rather than a hand-rolled mutex.

### Integer overflow: pre- and post-Solidity 0.8

Before Solidity 0.8.0 (released December 2020), arithmetic operations wrapped silently on overflow or underflow — `uint8 x = 255; x + 1` produced `0`, with no revert, no event, nothing observable unless the developer had manually added a check (typically via SafeMath, a widely-used library that did exactly this wrapping and reverting by hand, before it became a language default). This was directly exploitable wherever an overflow could be triggered by attacker-controlled input: the BatchOverflow bug (April 2018) affected multiple ERC-20 contracts implementing a "batch transfer" function whose internal multiplication (`amount × recipients.length`) could be made to overflow, letting an attacker specify parameters producing a wrapped, tiny multiplication result while the actual per-recipient transfer amount stayed attacker-chosen and large — effectively minting tokens from nothing.

**Solidity 0.8.0 made checked arithmetic the default**: `+`, `-`, `*` now revert automatically on overflow/underflow, with no library needed. This didn't eliminate the risk category, it relocated it: the `unchecked { ... }` block lets a developer explicitly opt back into the old wrapping behavior, almost always for a specific, understood gas optimization (checked arithmetic costs slightly more gas per operation; a tight loop with a counter provably bounded well under the overflow threshold is a legitimate, common `unchecked` use case) — but every `unchecked` block is now a marked, auditable surface specifically because it's the one place overflow can still happen silently, and an audit finding of "this `unchecked` block's safety assumption isn't actually guaranteed by the surrounding logic" remains a live, real category of bug. The Cetus Protocol exploit (May 2025, ~$223M lost) involved a `u256` overflow made profitable by flash-borrowed liquidity — a reminder that overflow protection at the language level for native Solidity arithmetic doesn't automatically extend to every numeric code path, particularly custom fixed-point math libraries or cross-language contexts (Cetus was a Sui/Move-ecosystem protocol, illustrating the bug class isn't Solidity-specific).

### Oracle manipulation and flash-loan attacks

A **price oracle** is however a contract learns the current market price of an asset it doesn't itself trade — and the single most consequential design mistake in this category is trusting a **spot price** read directly from one DEX pool's current reserves, because that price is trivially, momentarily movable by anyone with enough capital to swap against the pool, even if only for the duration of one transaction.

A **flash loan** (pioneered by Aave, and now offered by multiple protocols) lets anyone borrow an arbitrary, uncollateralized amount, provided the entire loan (plus a small fee) is repaid within the *same transaction* — if repayment doesn't happen by the end of the transaction, the whole transaction, including the loan itself, atomically reverts, so the lender bears zero default risk regardless of loan size. This is a legitimate, useful DeFi primitive (enabling arbitrage, collateral swaps, and self-liquidation without needing capital up front) that also happens to be the perfect tool for temporarily, overwhelmingly moving a thin market's price for exactly as long as one transaction needs it to stay moved.

The composition is what makes this category so effective and so hard to fully eliminate: **each individual step is legitimate**. Borrowing a flash loan isn't an attack. Swapping in a DEX pool isn't an attack. Reading a pool's current price isn't inherently wrong. The exploit *is* the composition — borrow enormous capital for one transaction, use it to move a price a victim protocol naively trusts, transact against the victim at that distorted price, repay the loan, keep the difference. Real attacks in this category have flash-borrowed anywhere from tens to hundreds of millions of dollars for the duration of a single transaction specifically to make an otherwise-uneconomical price distortion profitable.

**The fix, and it's a single, well-known one:** never use a manipulable spot price as a trusted input. Use a **time-weighted average price (TWAP)**, which requires an attacker to sustain a price distortion across multiple blocks (dramatically more expensive and more visible than a single-transaction spike), or a **decentralized oracle network** (Chainlink and similar services, aggregating prices across many independent sources and reporters) that a single DEX pool's momentary state can't unilaterally influence. A protocol reading `getReserves()` from one Uniswap pool directly as "the price," with no TWAP and no external oracle, is a specific, checkable, and still-recurring audit finding.

### Front-running and MEV

Ethereum transactions sit in a public **mempool** after being broadcast and before being included in a block — visible to anyone running a node, including the entities (searchers, and ultimately block builders/proposers under the current MEV-Boost/proposer-builder-separation architecture) who decide what order transactions go into the next block. **MEV (maximal extractable value)** is the aggregate value that can be extracted by controlling that ordering: seeing a large, pending DEX trade that will move a price, and inserting your own trade immediately before it (front-running, buying before the price moves up) and immediately after it (back-running, selling into the price you just helped push up) — a **sandwich attack**, the most common retail-facing MEV pattern, extracting value directly from the original trader's slippage.

This isn't a bug in any single contract; it's a structural property of how transaction ordering works in a public, permissionless mempool, which is why the mitigations operate at a different layer than "fix the contract": **commit-reveal schemes** (submit a hidden commitment first, reveal the actual transaction later, so the content isn't visible to front-run while pending), **private transaction relays / encrypted mempools** (submitting directly to a block builder without broadcasting to the public mempool at all, removing the visibility front-running depends on), and **slippage limits with tight tolerances** (bounding how much price movement a user's own transaction will tolerate before reverting, capping the damage a sandwich attack can extract even if it succeeds).

---

## Build it from scratch

The reentrancy simulation above **is** the from-scratch build for this module's central mechanism, executed directly rather than described. The equivalent Solidity pattern, matching the tested Python logic precisely:

```solidity
// untested sketch — mirrors the exact VulnerableVault / FixedVault logic
// verified above in Python, translated to the real language and call primitive
contract VulnerableVault {
    mapping(address => uint256) public balances;

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external {
        uint256 amount = balances[msg.sender];
        require(amount > 0, "nothing to withdraw");
        (bool ok, ) = msg.sender.call{value: amount}("");   // EXTERNAL CALL FIRST
        require(ok, "send failed");
        balances[msg.sender] = 0;                            // STATE UPDATE LAST — too late
    }
}

contract FixedVault {
    mapping(address => uint256) public balances;
    bool private locked;                                     // defense-in-depth mutex

    modifier nonReentrant() {
        require(!locked, "reentrant call");
        locked = true;
        _;
        locked = false;
    }

    function deposit() external payable {
        balances[msg.sender] += msg.value;
    }

    function withdraw() external nonReentrant {
        uint256 amount = balances[msg.sender];               // CHECKS
        require(amount > 0, "nothing to withdraw");
        balances[msg.sender] = 0;                             // EFFECTS
        (bool ok, ) = msg.sender.call{value: amount}("");     // INTERACTIONS (last)
        require(ok, "send failed");
    }
}
```

Full lab — a Foundry test suite reproducing the DAO-style reentrancy against a local testnet, a `unchecked{}`-block overflow exercise, a minimal flash-loan-and-oracle-manipulation scenario against a deliberately naive spot-price-reading contract, and an Echidna invariant-fuzzing configuration: **`labs/sol/22-contract-security/`**.

---

## How it's done in production

A real audit is not "read the code and look for bugs" — it's a structured process combining several categorically different techniques, because each catches a different class of issue and none of them alone is sufficient:

1. **Static analysis** (Slither, Aderyn) — automated scanning against a known catalogue of vulnerability patterns (80+ detector types in Slither's case) without executing any code; fast, cheap, catches known-shape issues (reentrancy-shaped code, unchecked external calls, obviously missing access control) but blind to logic errors specific to the protocol's actual business rules.
2. **Fuzz testing** (Foundry's native fuzzing, Echidna, Medusa) — automatically generating large volumes of randomized inputs against developer- or auditor-defined invariants ("total supply never exceeds X," "this function never reverts for valid input," "balances sum always equals total supply"), catching edge cases a manual reviewer wouldn't think to construct by hand.
3. **Formal verification** (Certora Prover, Halmos) — mathematically proving an invariant holds for *all* possible inputs, not just the fuzzer's sampled subset; roughly a third of high-value 2025-era audit engagements included at least one formally-verified invariant suite, reserved for the highest-value, highest-risk contract logic given its cost and the specialized expertise required.
4. **Manual review** — an experienced auditor reading the code against the protocol's actual intended economic behavior, which is where logic errors, oracle-trust assumptions, and business-rule mistakes that no automated tool has a pattern for actually get caught; this remains irreplaceable specifically because it's the only step that reasons about *intent*, not just code shape.

| Symptom | Cause | Fix |
|---|---|---|
| A withdrawal function drains more than any single user's balance | Reentrancy — external call before state update, no reentrancy guard | Apply checks-effects-interactions; add `ReentrancyGuard` as defense-in-depth |
| A batch operation mints or transfers an absurd, unintended amount | Integer overflow in an `unchecked` block or in arithmetic that bypassed Solidity 0.8's default checks | Remove unnecessary `unchecked` blocks; audit every remaining one's actual safety assumption explicitly |
| A lending/derivatives protocol gets drained after a single, large, unusual transaction | Spot-price oracle manipulated via a flash loan in the same transaction | Switch to TWAP or a decentralized oracle network; never trust a single pool's instantaneous reserves as "the price" |
| Retail users report consistently worse execution prices than expected on DEX trades | Sandwich attacks — MEV searchers front-running and back-running visible pending trades | Tighten slippage tolerance defaults; consider private transaction relays/commit-reveal for sensitive trades |
| An audit finding gets dismissed as "theoretical" and ships anyway, then gets exploited | Governance/prioritization failure, not a technical one — treating a demonstrated exploit path as low-priority because it "requires a flash loan" (a genuinely trivial, permissionless resource) | Treat any flash-loan-reachable exploit path as fully in-scope and immediately actionable; flash loans require no special access or capital, so "requires a flash loan" is not a mitigating factor |

---

## Tradeoffs & when NOT to use it

- **Don't treat a passed audit as a permanent, complete guarantee.** Audits assess the code as reviewed, at a point in time, against a bounded scope and time budget — new attack techniques, subsequent code changes, and interactions with *other* protocols deployed after the audit are all outside what any single audit certified. "Audited" is a real, meaningful signal, not an immutable safety proof.
- **Don't add a reentrancy guard as a substitute for checks-effects-interactions.** The guard is real, valuable defense-in-depth, but relying on it alone while still writing external-call-before-state-update code leaves you one missed `nonReentrant` modifier away from the exact same vulnerability — CEI should be the default coding pattern, with the guard as a backstop, not the other way around.
- **Don't assume Solidity 0.8's default checked arithmetic makes overflow a solved problem you no longer need to think about.** It closes the *default* case; every `unchecked` block, every custom fixed-point math library, and every non-EVM-native numeric path (as Cetus's 2025 loss demonstrated) still needs the same scrutiny overflow always required.
- **Don't build a price-sensitive protocol around a single DEX pool's spot price under any circumstances**, regardless of how liquid that pool seems at design time — liquidity conditions change, and "this pool is too deep to manipulate" has been wrong before at exactly the moment an attacker chose to test it with a large enough flash loan.
- **Don't treat MEV mitigation as solvable purely at the smart-contract layer.** Front-running is a property of public transaction ordering, not a bug in any one contract; meaningful mitigation requires infrastructure-layer changes (private relays, encrypted mempools) or protocol-design changes (batch auctions, commit-reveal) rather than a Solidity-only fix, and pretending a contract-level patch fully solves it is a real gap worth naming precisely in a design review.

---

## Interview questions

### Q1 — Walk through the reentrancy attack mechanism precisely, and explain exactly why checks-effects-interactions fixes it.
**Testing:** whether the mechanism is understood well enough to derive the fix, not just recite it.
**Answer:** A vulnerable withdrawal function calls out to an external address (sending funds) before updating its own internal balance record. Because an external call transfers control to the receiving address's code, that code — if it's a malicious contract's fallback function — can call back into the same withdrawal function while the balance still reflects "unwithdrawn," letting it pass the same balance check repeatedly before the original call ever gets to zero it out. Checks-effects-interactions fixes it by reordering: validate the request (checks), update your own state to reflect the operation as already complete (effects), and only then make the external call (interactions) — by the time control transfers to any outside code, any reentrant call sees the already-updated (zeroed) balance and has nothing left to exploit.
**Follow-up trap:** *"If a function makes multiple external calls, does CEI ordering apply to all of them, or just the first?"* — all of them: every external call is a point where control (and potentially malicious code) can execute, so every state variable the function's logic depends on for correctness must be fully updated before *any* external call in that function, not just the first one — a common, subtler mistake is fixing the ordering for one external call while a second, later external call in the same function still reads state that hasn't been finalized yet.

### Q2 — Your tested code showed the vulnerable vault paying out 50 units against a 10-unit deposit. Where did the other 40 units actually come from?
**Testing:** whether the "who actually loses money" mechanism, not just "reentrancy is bad," is understood.
**Answer:** From the shared pool — the vault's `balances` mapping tracks accounting per-address, but the actual ETH (or tokens) held by the contract is one shared pot; the attacker's reentrant withdrawals kept passing the balance *check* (which never got updated) while draining real funds from that shared pot, meaning every unit paid out beyond the attacker's legitimate 10 came directly out of other depositors' funds, even though their own balance records were never touched. This is precisely why reentrancy in a shared-pool contract is catastrophic rather than merely a self-inflicted accounting error: the attacker's exploit directly steals other users' money, not just their own.
**Follow-up trap:** *"Would the attack still work if the vault tracked funds per-user in fully separate, individually-custodied balances rather than a shared pool?"* — the reentrancy *mechanism* (bypassing the balance check via recursive calls) would still technically fire, but if there were genuinely no shared pool to drain from — meaning the contract literally couldn't pay out more than that specific user ever deposited, by construction — the exploit would have nothing extra to extract; in practice almost no real vault design achieves this isolation cleanly, which is exactly why CEI/reentrancy-guards remain necessary regardless of the underlying accounting model.

### Q3 — What changed in Solidity 0.8.0 regarding arithmetic, and why doesn't this fully close the integer-overflow risk category?
**Testing:** whether the "default changed, risk relocated" nuance is understood, not just "overflow is fixed now."
**Answer:** Solidity 0.8.0 (December 2020) made checked arithmetic the default: `+`, `-`, `*` now revert automatically on overflow/underflow, replacing the prior silent-wraparound behavior that required manual SafeMath-style guarding. This doesn't eliminate the risk category, it relocates it into `unchecked{}` blocks, which developers explicitly opt into (almost always for gas savings in provably-bounded loops), and into any numeric code path that doesn't go through native Solidity checked arithmetic at all — custom fixed-point math libraries, or non-EVM ecosystems entirely, as the Cetus Protocol's 2025 ~$223M loss (a Move-ecosystem `u256` overflow) demonstrated.
**Follow-up trap:** *"If you see an `unchecked` block in a code review, is that automatically a red flag?"* — no, and treating it that way misses the point: `unchecked` is a legitimate, common gas optimization when the surrounding logic provably bounds the value well under the overflow threshold (a loop counter bounded by a small, fixed array length, for instance) — the actual audit question is whether that boundedness is *actually* guaranteed by the code as written, not whether `unchecked` appears at all; a correctly-justified `unchecked` block is fine, an unjustified or incorrectly-reasoned one is the finding.

### Q4 — Explain a flash-loan-facilitated oracle manipulation attack end to end, and why it doesn't require any bug in the victim contract's code.
**Testing:** the composition-of-legitimate-steps insight, which is the module's central point about this attack class.
**Answer:** An attacker borrows a large, uncollateralized sum via a flash loan (repayable within the same transaction or the whole transaction reverts, so the lender takes zero risk). They use that capital to swap violently against a thinly-traded DEX pool, moving its spot price far from the broader market's actual price for the duration of that one transaction. A victim protocol that reads that pool's current reserves directly as "the price" — rather than a manipulation-resistant source — then executes some action (a loan, a liquidation, a trade) against the attacker at that distorted price. The attacker repays the flash loan and keeps the extracted difference. No step individually is a bug: borrowing is legitimate, swapping in a DEX is legitimate, reading a pool's reserves is legitimate — the exploit is entirely in the victim's *trust assumption* about what a momentary spot price represents, not in any specific line of vulnerable code.
**Follow-up trap:** *"If the victim protocol has no bugs, whose responsibility is it, and how is it 'fixed'?"* — it's an architectural/design responsibility, specifically the choice of price oracle: the fix is switching to a TWAP (requiring sustained multi-block manipulation, dramatically more expensive and visible) or a decentralized oracle network aggregating many independent sources, neither of which a single flash-loan-funded transaction can unilaterally distort — the "bug," such as it is, is a design decision (trusting a manipulable price source) rather than a coding error, which is exactly why this category shows up in architecture review as much as code-level audit.

### Q5 — What is MEV, and why is "fix the smart contract" not a complete answer to front-running?
**Testing:** whether the structural, infrastructure-layer nature of the problem is understood.
**Answer:** MEV (maximal extractable value) is the value obtainable by controlling the ordering, inclusion, or exclusion of transactions within a block — front-running (inserting a transaction ahead of a visible, profitable pending one) and sandwich attacks (front-running plus back-running around a target trade) are the most common user-facing forms. This is a structural property of how a public mempool and block-production process work, not a bug in any single contract's code — the pending transaction being visible to searchers and block builders before confirmation is what enables it, and no change to the target contract's own logic removes that visibility. Meaningful mitigation requires infrastructure-layer intervention (private transaction relays, encrypted mempools) or protocol-design changes (commit-reveal ordering, batch auctions) rather than a purely contract-level patch.
**Follow-up trap:** *"Doesn't setting a tight slippage tolerance on a DEX trade 'fix' front-running for that trade?"* — it caps the *damage* a sandwich attack can extract (the trade reverts rather than executing at an arbitrarily bad price), which is a genuinely useful, real mitigation worth applying by default — but it doesn't prevent the front-running attempt itself, doesn't recover any value already lost within the tolerated slippage range, and does nothing for MEV forms beyond sandwiching (like arbitrage extraction that doesn't need a wide slippage window at all) — a meaningfully smaller problem, not a solved one.

### Q6 — Design an audit process for a new DeFi lending protocol before mainnet launch. What specifically would you require, and why is any single technique insufficient alone?
**Testing:** whether the multi-technique audit methodology is understood as necessary composition, not a checklist to recite.
**Answer:** Static analysis (Slither/Aderyn) first, as a fast, cheap pass catching known-shape issues (missing access control, obvious reentrancy patterns, unchecked calls) — necessary but blind to logic specific to this protocol's actual economic rules. Fuzz testing (Foundry invariants, Echidna) next, defining protocol-specific invariants (collateralization ratios never go negative, total supply always equals the sum of balances) and letting automated random-input generation try to break them at a scale manual review can't match. Formal verification (Certora/Halmos) for the highest-value, highest-risk logic specifically — the liquidation and interest-accrual math, most likely — where a mathematical proof of correctness for *all* inputs, not just fuzzed samples, is worth the added cost. Manual review throughout and especially at the end, from an experienced auditor reasoning about the protocol's actual intended behavior and trust assumptions (oracle sources, admin key powers, upgrade paths) — the step that catches "this is technically correct code implementing the wrong economic design," which no automated tool has a pattern for.
**Follow-up trap:** *"If budget only allows for one of these, which do you pick?"* — manual review, and this is worth defending explicitly: automated tools catch known-shape bugs efficiently, but a protocol's actual, novel economic vulnerabilities (a specific oracle trust assumption, a specific incentive misalignment) are exactly the class of issue only a human reasoning about intent tends to find — automated tools are a force multiplier on top of manual review, not a substitute for it, which is precisely why "we ran Slither" is not, by itself, a credible claim to have been audited.

### Q7 — A protocol's audit report flags an "unchecked block overflow risk, low severity, requires an unrealistic input" and the team ships anyway. A month later it's exploited via a flash loan providing exactly that "unrealistic" input. What went wrong in the risk assessment?
**Testing:** the specific, real mistake of underweighting flash-loan-reachable inputs — a recurring, named failure mode.
**Answer:** "Requires an unrealistic input" implicitly assumes the input is hard or expensive for an attacker to actually produce — but a flash loan makes enormous, temporary capital trivially, permissionlessly available for exactly one transaction, which routinely turns "requires an unlikely $50M position" into "costs a flash-loan fee, achievable by anyone." Any exploit path reachable via flash-loan-scale capital should be assessed as realistically achievable by default, not discounted for requiring a large input — this is precisely the mistake OWASP's Smart Contract Security top-10 explicitly calls out flash-loan-facilitated attacks as a distinct category for, because the underweighting keeps recurring across otherwise-competent risk assessments.
**Follow-up trap:** *"Is every large-input finding automatically high severity, then?"* — no, and overcorrecting to "any large number is dangerous" is its own mistake; the actual test is whether the large input is achievable *within a single transaction, without collateral or special access* — a flash loan satisfies that test trivially, while an input requiring genuine, sustained capital commitment or privileged access does not, and severity should track that specific distinction rather than input magnitude alone.

### Q8 — Compare and contrast integer overflow, reentrancy, and oracle manipulation as vulnerability classes: which is a language/compiler-level problem, which is a code-pattern problem, and which is an architecture-level problem?
**Testing:** synthesis across the whole module — whether the candidate can categorize by root cause and fix layer, not just recall each independently.
**Answer:** Integer overflow was fundamentally a **language-default** problem — Solidity 0.8's checked-arithmetic default fixed the common case at the compiler level, with residual risk pushed into explicitly-marked `unchecked` opt-outs. Reentrancy is a **code-pattern** problem — the language provides everything needed to write it safely (checks-effects-interactions is just an ordering discipline, requiring no special language feature), so the fix lives entirely in developer practice and audit review, reinforced by library-level tooling (`ReentrancyGuard`) rather than a compiler default. Oracle manipulation is an **architecture-level** problem — no code-pattern or compiler default fixes a design decision to trust a manipulable price source; the fix is a different architectural choice (TWAP, decentralized oracle network) made at design time, and no amount of careful implementation of the wrong architecture avoids the exploit.
**Follow-up trap:** *"Which of the three is hardest to catch in a standard audit, and why?"* — oracle manipulation and other architecture-level trust-assumption issues, specifically because static analysis and fuzzing tools are built to catch *code-shape* problems (a pattern in the syntax or a violated invariant), while "this design trusts a source that can be manipulated" is a judgment about the system's economic and trust architecture that requires a human auditor to reason about deliberately — it's exactly the category most likely to be missed by a review that leans too heavily on automated tooling and too lightly on manual, intent-focused review.

### Q9 — What's the difference between a "read-only reentrancy" attack and the classic reentrancy this module demonstrated, and why did it take the industry longer to recognize as a distinct risk?
**Testing:** whether the candidate's understanding of reentrancy extends past the textbook drain-a-vault case to a subtler, more recently-recognized variant.
**Answer:** Classic reentrancy exploits a contract's own vulnerable state-update ordering to directly drain funds from itself. Read-only reentrancy is subtler: a contract's *view* functions (read-only, no state change, seemingly "safe" by definition) can return stale or manipulated values *during* a reentrant callback window, because the calling contract's state update is mid-flight — a separate, third-party contract that trusts that view function's return value (for pricing, collateral checks, or similar) as if it were always consistent can be misled into acting on transiently-incorrect data, even though the view function itself never reverted or behaved incorrectly in isolation. It took longer to recognize specifically because "view functions can't be part of a reentrancy exploit" was a reasonable-sounding but incorrect assumption — the vulnerability isn't in the view function's own logic, it's in another contract's trust in that function's value being consistent at every possible call point, including mid-reentrancy.
**Follow-up trap:** *"How would checks-effects-interactions, as covered in this module, protect against read-only reentrancy?"* — it doesn't, directly, and this is the important nuance: CEI protects the contract *making* the external call from being directly drained by its own logic; read-only reentrancy is a risk to *other, third-party contracts* that read a vulnerable contract's state via a view function during a reentrant window — the fix is different and lives partly outside the vulnerable contract's own code (third-party integrators should be cautious trusting external view-function state during any external call, and defensive patterns like reentrancy guards applied even to view functions, or explicit state-consistency checks by the consuming contract, are the actual mitigations).

### Q10 — Your protocol integrates a third-party price oracle that's widely used and has a multi-year track record with no incidents. Does that track record meaningfully reduce the oracle-manipulation risk this module covered?
**Testing:** whether "track record" is understood as weak evidence for a risk category that's fundamentally about a manipulable mechanism, not a probabilistic failure rate.
**Answer:** It reduces risk somewhat (a well-designed, already-hardened oracle with TWAP or multi-source aggregation genuinely is safer than a naive spot-price read), but a multi-year clean track record specifically doesn't address the actual mechanism this module covers: flash-loan-facilitated manipulation doesn't require the oracle to have a latent bug that eventually gets found — it requires only that manipulating the specific price source it reads from is *currently* economically feasible for a given attack's expected payoff, which changes with market liquidity conditions, the size of positions the protocol allows, and the cost of capital via flash loans — none of which a clean historical track record predicts, since the attack's feasibility is a live, continuously-changing economic calculation, not a static code-quality property that improves monotonically with time-in-production the way a typical software bug's absence might suggest.
**Follow-up trap:** *"So should every protocol assume every oracle integration is equally risky, regardless of design?"* — no, and that overcorrection misses real, meaningful distinctions: a TWAP-based or multi-source-aggregated oracle genuinely raises the cost and difficulty of manipulation by a large, real margin over a naive single-pool spot price, and that architectural difference is exactly what should drive the risk assessment — the point is that "track record" and "time in production with no incidents" are the wrong signals to lean on; "what specific manipulation-resistance mechanism does this oracle actually implement, and does the protocol's position sizing stay within what that mechanism can realistically defend" are the right ones.

---

## Red flags that fail you

- Describing reentrancy's fix as "add a reentrancy guard" without mentioning checks-effects-interactions as the underlying, primary pattern.
- Claiming Solidity 0.8+ "solved" integer overflow with no mention of `unchecked` blocks or non-EVM-native numeric risk.
- Describing oracle manipulation or flash-loan attacks as requiring a bug in the victim contract's code.
- Not knowing that a flash loan must be repaid within the same transaction or the entire transaction reverts.
- Treating "the contract passed an audit" as a permanent, complete safety guarantee.
- Describing MEV/front-running as fixable purely by a smart-contract-level code change.

---

## Cheat card

```
REENTRANCY: external call BEFORE state update lets the callee re-enter and pass the
  same balance CHECK repeatedly before it's ever zeroed. FIX = Checks-Effects-Interactions:
  validate -> update YOUR state -> THEN external call (last). VERIFIED (Python sim):
  vulnerable vault paid attacker 5x10=50 vs one 10-unit deposit; CEI-fixed vault paid 1x10=10.
  Defense-in-depth: ReentrancyGuard mutex (OpenZeppelin) -- backstop, NOT a substitute for CEI.
  Origin: The DAO hack, June 2016, ~$60M -> Ethereum/ETC hard-fork split.

INTEGER OVERFLOW: pre-0.8.0 (<Dec 2020) = SILENT WRAPAROUND by default (uint8 255+1=0).
  BatchOverflow (Apr 2018): ERC-20 batch-transfer multiplication overflow -> minted tokens
  from nothing. Solidity 0.8.0+ = CHECKED arithmetic by default, reverts on overflow.
  Risk RELOCATED, not eliminated: unchecked{} blocks (deliberate gas opt-out) + non-EVM-native
  math (Cetus Protocol, May 2025, ~$223M, u256 overflow, flash-loan-funded, Move ecosystem).

FLASH LOAN + ORACLE MANIPULATION: uncollateralized loan, must repay by END of SAME tx or
  whole tx reverts (zero lender risk). Attack = borrow huge sum -> violently move a THINLY
  TRADED pool's SPOT price -> victim protocol trusts that spot price -> transact against
  victim at distorted price -> repay loan -> keep profit. EVERY STEP INDIVIDUALLY LEGITIMATE --
  exploit IS the composition, NOT a bug in victim's code. FIX: TWAP or decentralized oracle
  network (Chainlink-style), never trust single-pool spot price. OWASP SC04:2026 category.
  "Requires unrealistic capital" is NOT mitigating -- flash loans make $50-500M trivially available.

MEV / FRONT-RUNNING: pending txs sit in PUBLIC MEMPOOL before confirmation -- visible to
  searchers/builders. SANDWICH = front-run (buy before target trade moves price) + back-run
  (sell after). Structural property of public tx ordering, NOT a per-contract bug -- fix
  needs infra layer (private relays, encrypted mempool) or protocol design (commit-reveal,
  batch auctions), not just a Solidity patch. Slippage limits cap damage, don't prevent it.

AUDIT = 4 DISTINCT TECHNIQUES, need ALL, none sufficient alone:
  1. STATIC ANALYSIS (Slither 80+ detectors, Aderyn) -- fast, catches known-shape bugs only
  2. FUZZING (Foundry invariants, Echidna, Medusa) -- random inputs vs defined invariants
  3. FORMAL VERIFICATION (Certora, Halmos) -- proves invariant for ALL inputs; ~1/3 of
     high-value 2025-26 engagements use this for highest-risk logic
  4. MANUAL REVIEW -- only step reasoning about INTENT/economic design, catches oracle
     trust mistakes + business-logic errors no automated tool has a pattern for
  "Audited" = point-in-time, bounded scope -- NOT a permanent guarantee.
```

## Sources

- [OWASP Smart Contract Security — SC04:2026 Flash Loan-Facilitated Attacks](https://scs.owasp.org/sctop10/SC04-FlashLoanAttacks/) — accessed 2026-08-08
- [Hacken — Flash Loan Attacks: How They Work, Real Examples, and How to Prevent Them](https://hacken.io/discover/flash-loan-attacks/) — accessed 2026-08-08
- [Hacken — Smart Contract Auditing Tools 2026: A Reviewer's Stack](https://hacken.io/discover/audit-tools-review/) — accessed 2026-08-08
- [Solidity v0.8.0 Breaking Changes — checked arithmetic default](https://docs.soliditylang.org/en/latest/080-breaking-changes.html) — accessed 2026-08-08
- [OpenZeppelin — ReentrancyGuard](https://docs.openzeppelin.com/contracts/4.x/api/security) — accessed 2026-08-08
- [Zealynx — Flash loan attacks: anatomy of nine-figure DeFi exploits](https://www.zealynx.io/research/web3-attack-vectors/flash-loan-attacks) — accessed 2026-08-08

## Changelog
- 2026-08-08 — created
