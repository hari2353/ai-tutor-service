# Human Oversight Design: Approval Gates, Escalation, Accountability

> **Track:** T07 Agentic AI · **Time:** 2h · **Prereqs:** `T07-langgraph-durable`, `T07-trust-calibration`, `T07-hallucination` · **Updated:** 2026-07-26
> **Module id:** `T07-human-oversight` · **Tags:** trust, critical

## The 30-second version

Place gates by **irreversibility × blast radius × externality**, not by how scary the tool's name sounds: a `read_only` call needs logging, a `write` to one record needs an undo window, a `financial` or `destructive` action needs a synchronous approval, and some actions should simply not be in the toolset. The failure mode that actually bites is not a missing gate, it is a gate that gets rubber-stamped — automation bias plus alert fatigue means a reviewer facing a queue will approve, and the empirical base rate is grim: security operations receive around **2,992 alerts a day with 63% never addressed**, **46% of alerts are false positives**, and **71% of analysts report burnout**. So a gate is only real if the reviewer sees the **diff rather than the intent**, has the evidence inline, can say no cheaply, faces a bounded queue, and is **measured by an error-injection audit** — corrupt a claim in a random sample of items and see whether reviewers catch it. Everything must land in an immutable audit record that includes the one field everyone forgets: **what the reviewer was actually shown**. And the honest tension is arithmetic, not philosophy: each gate consumes part of the value the automation created, so the goal is *fewer, better* gates with autonomy ratcheting up as measured error rates come in, not a gate on everything.

## Why this gets asked

Because the interviewer has been on both sides of the same mistake. Version one shipped with no gates and an agent did something irreversible — deleted a branch, emailed 4,000 customers, closed the wrong tickets — and nobody could reconstruct who authorised it. Version two shipped with approval on everything, throughput collapsed, the reviewers turned into a click-through queue within three weeks, and the gates were then quietly widened until they protected nothing. They want to know if you can design the version that survives: gates in the right places, sized so a human can actually think, with a decay-detection mechanism. At staff level the probe turns adversarial in a useful way: *"you have added six gates, prove any of them catches anything"*. Candidates who answer with process rather than measurement fail that question. And in 2026 there is a hard external forcing function — EU AI Act Article 14 obligations for high-risk systems apply from **2 August 2026**, with penalties up to **€35M or 6-7% of global turnover** depending on the provision — so "we have a human in the loop" is now a claim someone will audit.

---

## Lineage: past → present → future

**What came before.** The pattern is borrowed, not invented. Finance had **maker-checker / four-eyes** and segregation of duties long before software, formalised by SOX after 2002: the person who initiates a transaction cannot be the person who approves it. Aviation and medicine produced the *research* that matters here, because they automated first and discovered the failure mode. **Parasuraman & Riley (1997), *Humans and Automation: Use, Misuse, Disuse, Abuse*** named the taxonomy, and **Skitka et al. (1999)** demonstrated automation bias directly: humans monitoring an automated aid miss errors they would have caught unaided, because monitoring is a fundamentally different and worse task than doing. The pain that killed naive alarm-everything designs was **alarm flood** — Three Mile Island's control room, clinical alarm fatigue leading to silenced monitors and patient deaths, and the industrial-safety finding that operators disable alarms they cannot act on. Every one of those lessons transfers to agent approval queues, and almost none of the agent tooling built between 2023 and 2025 reflected them.

The ML era's first answer was human-in-the-loop labelling and content-moderation queues, which taught the second lesson: **review capacity is the binding constraint, and a queue that exceeds it silently degrades into sampling** — except unplanned sampling, where you do not know your coverage.

**Where it stands now.** Approval is a framework primitive. LangGraph's `interrupt()` with a durable checkpointer pauses mid-graph and resumes after human input, which is the reference implementation for the shape (`T07-langgraph-durable`); the OpenAI Agents SDK, Temporal signals, and MCP's elicitation flow all expose the same idea; and coding agents ship permission modes with tool allowlists as the consumer-facing version. The **risk-tier taxonomy** has converged across independent 2026 guidance to roughly four bands — auto-approved (low risk, reversible, in scope), notify-and-proceed (logged in real time), human-in-the-loop (high risk or irreversible: the agent pauses), and prohibited (outside scope, agent refuses and logs) — with the consistent hard rule that **permanently destructive actions stay gated at every autonomy level**. Regulation caught up: EU AI Act Article 14 requires high-risk systems be designed so oversight persons can understand the system's capacities and limitations, **remain aware of the tendency to over-rely on it (automation bias is named in the text)**, correctly interpret output, override or disregard it, and halt it via a stop button or comparable procedure; Article 26 puts duties on deployers; NIST AI RMF and ISO/IEC 42001 supply the management-system framing enterprise buyers ask about.

The live disagreements are worth knowing because they show up as interview follow-ups. First, **whether human oversight is meaningful at scale at all**: a 2025 European Commission study found oversight frequently degenerates into "ritual supervision" — clicking approve because the system said so — and the rubber-stamp critique is now mainstream rather than fringe. Second, **what to gate on**: action type (deterministic, auditable, coarse) versus model confidence (adaptive, cheaper, and unauditable when the confidence signal is uncalibrated). The defensible answer is action type as the floor and confidence as an *additional* trigger, never as a replacement. Third, **where the control plane lives**: inside the agent framework (fast, context-rich, bypassable) versus an external runtime control layer with its own identity and policy store (auditable, uniform across agents, adds latency and a dependency).

**Where it's heading.** High confidence: **policy-as-code for agent permissions**, versioned and tested like any other code, because "which policy version approved this action" is an audit question with no good manual answer. High confidence: **agent identity and scoped credentials** become the substrate — agents get their own principals with narrow, short-lived, purpose-scoped tokens instead of borrowing a service account, which converts many approval gates into authorisation failures that never reach a human. Medium confidence: **evidence-based autonomy ratchets**, where an action class graduates from gated to notify-only after N clean executions and demotes automatically on incident, which is the only mechanism that resolves the gates-versus-value tension in a principled way. Medium confidence: liability and insurance products start pricing autonomy levels, which will do more to standardise this than any framework. Speculative, flag it: certified autonomy levels analogous to SAE driving levels, and regulator-recognised attestations of oversight quality. People talk about it; nothing to build against.

---

## Mental model

Gate placement is a function of three properties of the *action*, not of the model.

```
                        WHERE DOES THE GATE GO?

              ┌────────────────────────────────┬────────────────────────────────┐
              │  SMALL BLAST RADIUS            │  LARGE BLAST RADIUS            │
              │  (1 record, 1 user)            │  (many records / tenants /     │
              │                                │   external parties)            │
┌─────────────┼────────────────────────────────┼────────────────────────────────┤
│ REVERSIBLE  │  AUTO + LOG                    │  NOTIFY-AND-PROCEED            │
│ (real undo, │  e.g. read, draft, label,      │  + UNDO WINDOW + rate cap      │
│  cheap)     │  create a private branch       │  e.g. bulk retag 5k records    │
├─────────────┼────────────────────────────────┼────────────────────────────────┤
│ IRREVERSIBLE│  SYNCHRONOUS APPROVAL          │  DUAL APPROVAL or PROHIBITED   │
│ (no undo,   │  with a DIFF                   │  + kill switch + rate cap      │
│  or visible │  e.g. send one email,          │  e.g. delete a table, refund   │
│  externally)│  refund $12, close a ticket    │  10k accounts, force-push main │
└─────────────┴────────────────────────────────┴────────────────────────────────┘

  Third axis, easy to forget: EXTERNALITY. Anything a third party sees
  (email, payment, public post, filed document) is irreversible in practice
  even when the database row can be rolled back. You cannot un-send.

  Fourth: RATE. An action that is fine once and catastrophic 1,000 times needs a
  rate cap, not an approval — the human cannot review 1,000 of anything.
```

And the funnel where rubber-stamping enters, which is the actual subject of the module:

```
  agent proposes 100 actions
        │
        ├── 60 auto-approved (read-only, reversible)          → logged, sampled later
        ├── 30 notify-and-proceed                              → undo window, alert on anomaly
        └── 10 reach a human
                  │
                  ▼
            ┌───────────────────────────────────────────────┐
            │ REVIEW QUALITY DECAYS HERE, PREDICTABLY:      │
            │  • queue > capacity      → click-through      │
            │  • intent shown, not diff→ nothing to check   │
            │  • ~46% false positives  → "it's always fine" │
            │  • no time budget        → 3s per decision    │
            │  • no measurement        → nobody notices     │
            └───────────────────────────────────────────────┘
                  │
                  ▼
        9 approved in <5s each, 1 genuinely reviewed
        → you have ONE gate's worth of protection and TEN gates' worth of latency
```

The one-liner: **a gate is not a place where a human is asked; it is a place where a human can realistically say no.** Everything else is latency with a compliance costume.

---

## How it actually works

### The risk taxonomy, with the dimensions that actually decide

The four-tier vocabulary (`read_only` / `write` / `financial` / `destructive`) is the shared language and it is not sufficient on its own, because "write" spans updating a draft and overwriting a production config. Score each tool on five properties at registration time:

| Dimension | Question | Values |
|---|---|---|
| **Class** | What kind of action? | read_only · write · financial · destructive |
| **Reversibility** | Is there a real, cheap undo, and who can run it? | trivial · compensating-action · none |
| **Blast radius** | How many records/users/tenants at most? | 1 · bounded (≤N) · unbounded |
| **Externality** | Does a third party observe it? | none · internal · external-visible |
| **Rate risk** | Is it safe once and unsafe 1,000 times? | no · yes (needs a cap) |

Then the gate is a function, expressed as policy rather than judgment:

```
gate(action) =
    PROHIBITED       if class == destructive and blast_radius == unbounded
    DUAL_APPROVAL    if reversibility == none and (blast_radius != 1 or amount > T_high)
    APPROVAL         if reversibility == none or externality == external-visible
                        or class == financial
    NOTIFY + UNDO    if reversibility == compensating-action or blast_radius == bounded
    AUTO + LOG       otherwise
  ⨯ RATE CAP         independently, whenever rate_risk == yes
```

Two rules that come up as follow-ups. **Delete stays gated at every autonomy level** — no evidence-based ratchet applies to permanently destructive actions, which is the one place where consistency across 2026 guidance is unanimous. And **prompt-injected instructions never change the tier**: a high-risk action requires approval regardless of what instruction the agent received, because the injection vector's whole purpose is to make the agent believe the action is authorised (`T07-agent-safety`).

### Gate types, in ascending cost

| Gate | Human cost | What it protects | When |
|---|---|---|---|
| Auto + log | 0 | Nothing at execution time; enables post-hoc audit | Reversible, small, internal |
| **Dry run + diff** | ~0 if auto-checked | Catches wrong-target errors deterministically | **Wherever possible — see below** |
| Notify-and-proceed + undo window | ~0 unless triggered | Gives a human a chance to intervene without blocking | Bounded blast radius, compensating undo exists |
| Synchronous approval | 30-180s | Irreversible or externally visible single actions | Financial, external, no undo |
| Dual approval (four-eyes) | 2 × above, plus scheduling | Large irreversible actions; collusion resistance | Destructive with bounded radius, high-value financial |
| Prohibited (not in toolset) | 0 | Everything, absolutely | Unbounded destructive; anything with no legitimate agent use |

**The most under-used pattern is dry run plus diff.** Instead of asking "may I update these records?", the agent computes the exact change, renders it as a diff, and a deterministic validator checks invariants (row count within expected bounds, no rows outside the tenant, no field crossing a threshold, target matches a regex). Most of what a human reviewer would catch is expressible as an assertion, which means it can run in milliseconds on 100% of actions instead of 90 seconds on 10%. Reserve human attention for what genuinely needs judgment. If you take one design pattern from this module, take this one.

The second under-used pattern is **making the action reversible instead of gating it.** A soft delete with a 7-day tombstone, a staged email that sends after 10 minutes unless cancelled, a config change behind a feature flag — each converts an approval into an undo, which costs a human nothing in the normal case. **Prefer reversibility over approval whenever you can buy it**, because approvals scale with volume and undo windows do not.

### Designing for meaningful review

This is the section that separates senior from staff. Automation bias is not a character flaw, it is the predictable result of putting a human in a monitoring role, and Article 14 of the EU AI Act names it explicitly as something the *design* must counteract. Six requirements:

**1. Show the diff, not the intent.** "The agent wants to update the customer's billing address" is unreviewable. `- 12 Oak St, Leeds` / `+ 12 Oak Street, Leeds LS1` with the source of the new value and its citation is reviewable in three seconds. The general rule: the review UI should show *the change and its evidence*, not the agent's stated plan. A plan is a narrative and, per `T07-explainability`, narratives are not faithful.

**2. Put the evidence inline, at the decision point.** If checking requires opening another tab, the reviewer will not check. Retrieved passage, tool result, and the specific field the value came from, adjacent to the approve button.

**3. Make "no" cheap and make it stick.** One click to reject with a reason from a short enumerated list, and the rejection must be *recorded and fed back* — an agent that immediately re-proposes the same action trains the reviewer to stop rejecting. Rejections should decrement a budget and after two rejections on the same objective the run should escalate rather than retry.

**4. Bound the queue.** Compute review capacity honestly: reviewers × minutes per shift ÷ seconds per review. If proposed gated actions exceed it, you do not have an approval process, you have unplanned sampling with unknown coverage. Either narrow the gate criteria, or convert to explicit sampling (auto-approve, audit a random n%) and say so out loud, because explicit sampling with known coverage is strictly better than implicit sampling with unknown coverage.

**5. Budget the time and design for it.** If a review realistically needs 90 seconds, the queue must be sized for 90-second reviews, and the UI should not present ten items on one screen with a select-all. **Never provide a bulk-approve affordance for an irreversible class.** That control is where oversight goes to die.

**6. Measure the gate with error injection.** This is the only real test and almost nobody runs it. Inject a deliberate error into a random small percentage of proposed actions — a wrong target id, an off-by-10x amount, an unsupported claim — and measure the catch rate. A gate with a low catch rate is not oversight; it is a latency tax and, worse, an accountability laundering device, because the human's signature transfers blame without transferring scrutiny. Track catch rate over time: **it decays**, and the decay is the signal to change the design rather than to retrain the humans.

The empirical base rate for why this matters, from adjacent domains that automated first: roughly **2,992 security alerts per day with 63% unaddressed** (Vectra 2026), **46% of alerts false positives** (Microsoft SOC 2026), **73% of security teams naming false positives as their top detection challenge** and **76% citing alert fatigue** (SANS 2025), nearly **90% of SOCs reporting backlog overwhelm**, and **71% of analysts reporting burnout** (Tines). Physician studies of LLM-assisted diagnosis show measurable automation bias, and interventions framed as "20% of the AI's recommendations are wrong" perform differently from "80% are correct" — the framing of the reviewer's prior is part of the design, not a detail.

### Escalation paths

An approval request is a distributed-systems object and needs the same properties as any other. Six decisions to make explicitly:

- **Timeout and default.** What happens if nobody responds in 15 minutes? **Fail-closed** (abandon the action, notify) is correct for irreversible and financial actions. **Fail-open** (proceed) is acceptable only for reversible, bounded actions where blocking is itself a harm, and it must be logged as an auto-approval-by-timeout rather than silently as an approval. Getting this backwards is a classic incident: a queue outage becomes an unreviewed-action outage.
- **Expiry.** A request carries an expiry, because approving a 40-minute-old proposal is approving a stale world state. Re-validate preconditions at execution time and fail if they moved — an approval is for a *specific* diff, not for an intent.
- **Who may approve.** Enforced separation of duties: the requester cannot approve, the agent cannot approve itself, and the approver needs the permission for the underlying action in their own right. The agent must never hold the credential that grants approval.
- **Tiering.** Tier 1 is the operator on shift, tier 2 is the domain owner, tier 3 is the accountable executive for the highest band. Each tier has a target response time and an explicit fallback.
- **Batching versus per-item.** Batch *presentation* is fine for homogeneous reversible actions with a shared diff summary. Per-item decisions are mandatory for anything irreversible. Never a select-all across a heterogeneous batch.
- **Kill switch.** A single, tested control that halts all runs of an agent class immediately and leaves in-flight work in a resumable state. Article 14 requires the ability to halt via a stop button or comparable procedure, and enterprise security questionnaires ask for it by name. Untested kill switches do not count; exercise it in a game day.

### Audit trail and accountability

Record per gated action, immutably and with retention set by the domain's rules:

| Field | Why an auditor asks |
|---|---|
| Agent identity + version, prompt version, model + version | "Which system did this?" and reproducibility |
| Principal on whose behalf it acted, and the credential's scope | Authorisation chain; catches over-broad service accounts |
| Requested action, full parameters, computed diff | The thing that happened |
| Policy id + version that selected the gate | "Why was this gate chosen?" — unanswerable without it |
| **The evidence bundle the reviewer was shown** | **The field everyone forgets.** Without it you cannot distinguish informed approval from a rubber stamp, and this is exactly what an Article 14 audit probes |
| Reviewer identity, decision, reason code, **decision latency** | Latency is your rubber-stamp detector. A p50 of 3 seconds on a 90-second review is the finding |
| Overrides and disagreements with the agent's recommendation | Override rate near 0% means the gate is decorative |
| Execution result, errors, and rollback performed | Closing the loop |

Accountability rules that hold up in a postmortem: **every agent has a named human owner**, actions are attributed to a *person* through the delegation chain rather than to "the agent", and "the AI did it" is never an acceptable resolution. Regulators are explicit here — the deployer holds duties under Article 26 and cannot delegate them to a vendor or a model.

### What regulators and enterprise buyers actually require

**EU AI Act Article 14** (high-risk, applicable 2 August 2026) requires the system be *designed* so that oversight persons can: understand the system's relevant capacities and limitations; remain aware of the tendency to over-rely on output (automation bias, named in the text); correctly interpret the output; decide not to use it, or to disregard, override, or reverse the output; and intervene or halt via a stop button or comparable procedure. Note that this is a **design** obligation on the provider, not merely a staffing obligation on the deployer — a UI that makes override impractical is non-compliant even with a human present. Article 26 adds deployer duties including assigning competent, trained oversight persons. Article 50 transparency provisions and the GPAI documentation stack land the same day. Penalties reach €35M or 6-7% of global turnover depending on the provision.

**NIST AI RMF** and **ISO/IEC 42001** provide the govern/map/measure/manage framing and the management-system certification that enterprise procurement increasingly asks for. What actually appears on enterprise security questionnaires, in rough order of frequency: a tested kill switch; scoped, short-lived credentials per agent rather than a shared service account; an exportable immutable audit log with defined retention; RBAC on who can approve what, with separation of duties; documented risk tiers and which actions require human approval; data residency and retention for prompts, traces, and evidence bundles; and a named accountable owner. Being able to recite that list is a genuine differentiator in a staff-level interview, because it is the list the buyer's security team will send you.

### The honest tension: gates cost you the automation

State it as arithmetic, because that is what makes it a design conversation rather than a values debate. For an action class where the agent saves `S` minutes of human work, review costs `R` minutes, and a fraction `g` of actions are gated:

```
net value per action  =  S − g·R − wait_cost
break-even            :  g = S / R

  S = 10 min, R = 1.5 min  →  gate 100% and you keep 8.5/10 = 85% of the value.  Fine.
  S = 10 min, R = 5 min    →  gate 100% and you keep 50%.  Painful but maybe worth it.
  S = 2 min,  R = 1.5 min  →  gate 100% and you keep 25%, and the reviewer is the
                              bottleneck.  This is where rubber-stamping is CERTAIN,
                              because the economics force speed.
```

`wait_cost` is the one people miss: a synchronous gate mid-run means the agent is blocked, so a 15-minute approval latency turns a 40-second task into a 15-minute task, and if the run holds resources or a lock you have also created a capacity problem. This is why durable checkpointing (`T07-langgraph-durable`) is a prerequisite for approval gates rather than a nice-to-have: the run must suspend to storage and resume, not sit in memory holding a connection.

The resolution is not "fewer gates because velocity", it is **evidence-based ratcheting**: start gated, measure the error rate and the reviewer catch rate per action class, and graduate a class from approval to notify-and-proceed when it has accumulated enough clean executions, with automatic demotion on incident. Deletes and unbounded-blast-radius actions never graduate. That framing turns a political argument into a metric with a threshold, which is exactly what a staff engineer is paid to produce.

---

## Build it from scratch

A policy engine plus approval broker: risk scoring, gate selection, dual approval, separation of duties, expiry with fail-closed default, rate caps, sampling audit, and an audit record that includes what the reviewer saw.

```python
"""Oversight policy engine + approval broker. python 3.11+, stdlib only.
    python oversight.py
"""
from __future__ import annotations
from dataclasses import dataclass, field, asdict
from enum import Enum
from typing import Any
import hashlib, json, random, time, uuid


class Gate(str, Enum):
    AUTO = "auto_log"
    NOTIFY = "notify_and_proceed"
    APPROVAL = "approval"
    DUAL = "dual_approval"
    PROHIBITED = "prohibited"


class Klass(str, Enum):
    READ_ONLY = "read_only"; WRITE = "write"
    FINANCIAL = "financial"; DESTRUCTIVE = "destructive"


@dataclass(frozen=True)
class ToolRisk:
    """Registered ONCE per tool, reviewed like code. Not decided at call time."""
    name: str
    klass: Klass
    reversibility: str          # trivial | compensating | none
    max_blast: str              # one | bounded | unbounded
    externality: str            # none | internal | external_visible
    rate_risk: bool = False
    rate_cap_per_hour: int | None = None
    autonomy_level: int = 0     # ratchets up with evidence; deletes never ratchet


@dataclass
class Action:
    tool: str
    params: dict[str, Any]
    diff: str                   # the COMPUTED change, not the stated intent
    evidence: list[dict] = field(default_factory=list)   # what the reviewer will see
    amount: float | None = None
    affected: int = 1


POLICY_VERSION = "oversight@v4"
T_HIGH = 1000.0                 # currency threshold for dual approval


def select_gate(risk: ToolRisk, a: Action) -> tuple[Gate, str]:
    """Deterministic, versioned, unit-testable. The gate is a function of the ACTION's
    properties, never of what the model asked for or claimed to intend."""
    if risk.klass is Klass.DESTRUCTIVE and risk.max_blast == "unbounded":
        return Gate.PROHIBITED, "unbounded destructive: not in the toolset"
    if risk.klass is Klass.DESTRUCTIVE:
        return Gate.DUAL, "destructive actions stay gated at every autonomy level"
    if risk.reversibility == "none" and (a.affected > 1 or (a.amount or 0) > T_HIGH):
        return Gate.DUAL, "irreversible with multi-record or high-value scope"
    if (risk.reversibility == "none" or risk.externality == "external_visible"
            or risk.klass is Klass.FINANCIAL):
        return Gate.APPROVAL, "irreversible, externally visible, or financial"
    if risk.reversibility == "compensating" or risk.max_blast == "bounded":
        return Gate.NOTIFY, "reversible via compensating action; undo window applies"
    if risk.klass is Klass.READ_ONLY:
        return Gate.AUTO, "read-only"
    return Gate.AUTO, "reversible, small, internal"


@dataclass
class Request:
    id: str
    action: Action
    gate: Gate
    reason: str
    requester: str                      # agent identity@version
    on_behalf_of: str                   # the human principal
    created: float
    expires: float
    approvals: list[dict] = field(default_factory=list)
    rejections: list[dict] = field(default_factory=list)
    evidence_digest: str = ""           # hash of what was SHOWN — the audit anchor

    def needed(self) -> int:
        return 2 if self.gate is Gate.DUAL else 1

    def satisfied(self) -> bool:
        return len(self.approvals) >= self.needed()


class ApprovalBroker:
    def __init__(self, ttl: float = 900.0, fail_closed: bool = True,
                 audit_sample_rate: float = 0.02, seed: int = 0):
        self.ttl, self.fail_closed = ttl, fail_closed
        self.audit_sample_rate = audit_sample_rate
        self.open: dict[str, Request] = {}
        self.audit: list[dict] = []
        self.rate: dict[str, list[float]] = {}
        self._rng = random.Random(seed)

    # --- audit -------------------------------------------------------------
    def _log(self, event: str, **kw):
        self.audit.append({"ts": time.time(), "event": event,
                           "policy_version": POLICY_VERSION, **kw})

    @staticmethod
    def _digest(evidence: list[dict]) -> str:
        return hashlib.sha256(json.dumps(evidence, sort_keys=True,
                                         default=str).encode()).hexdigest()[:16]

    # --- rate cap ----------------------------------------------------------
    def _rate_ok(self, risk: ToolRisk) -> bool:
        if not risk.rate_risk or risk.rate_cap_per_hour is None:
            return True
        now = time.time()
        hist = [t for t in self.rate.get(risk.name, []) if now - t < 3600]
        self.rate[risk.name] = hist
        return len(hist) < risk.rate_cap_per_hour

    # --- main entry --------------------------------------------------------
    def submit(self, risk: ToolRisk, a: Action, requester: str,
               on_behalf_of: str) -> dict:
        gate, reason = select_gate(risk, a)
        if gate is Gate.PROHIBITED:
            self._log("prohibited", tool=a.tool, reason=reason, requester=requester)
            return {"status": "denied", "gate": gate, "reason": reason}
        if not self._rate_ok(risk):
            self._log("rate_capped", tool=a.tool, cap=risk.rate_cap_per_hour)
            return {"status": "denied", "gate": gate, "reason": "rate cap exceeded"}

        if gate in (Gate.AUTO, Gate.NOTIFY):
            self.rate.setdefault(risk.name, []).append(time.time())
            sampled = self._rng.random() < self.audit_sample_rate
            self._log("auto_executed", tool=a.tool, gate=gate, diff=a.diff,
                      requester=requester, on_behalf_of=on_behalf_of,
                      reason=reason, sampled_for_audit=sampled,
                      undo_window_s=600 if gate is Gate.NOTIFY else 0)
            return {"status": "proceed", "gate": gate, "reason": reason,
                    "sampled_for_audit": sampled}

        now = time.time()
        r = Request(id=str(uuid.uuid4()), action=a, gate=gate, reason=reason,
                    requester=requester, on_behalf_of=on_behalf_of,
                    created=now, expires=now + self.ttl,
                    evidence_digest=self._digest(a.evidence))
        self.open[r.id] = r
        self._log("approval_requested", request=r.id, tool=a.tool, gate=gate,
                  diff=a.diff, evidence_digest=r.evidence_digest,
                  requester=requester, on_behalf_of=on_behalf_of, reason=reason)
        return {"status": "pending", "request_id": r.id, "gate": gate,
                "expires_in": self.ttl}

    def decide(self, request_id: str, reviewer: str, approve: bool,
               reason_code: str = "", shown: list[dict] | None = None) -> dict:
        r = self.open.get(request_id)
        if r is None:
            return {"status": "unknown_request"}
        if time.time() > r.expires:
            return self._expire(r)
        # separation of duties: agent cannot approve itself; requester ≠ approver
        if reviewer in (r.requester, r.on_behalf_of) or reviewer.startswith("agent:"):
            self._log("sod_violation", request=r.id, reviewer=reviewer)
            return {"status": "forbidden", "reason": "separation of duties"}
        if any(x["reviewer"] == reviewer for x in r.approvals):
            return {"status": "forbidden", "reason": "one approval per reviewer"}

        latency = time.time() - r.created
        shown_digest = self._digest(shown) if shown is not None else r.evidence_digest
        rec = {"reviewer": reviewer, "reason_code": reason_code,
               "latency_s": round(latency, 2), "shown_digest": shown_digest,
               "shown_matches_request": shown_digest == r.evidence_digest}
        (r.approvals if approve else r.rejections).append(rec)
        self._log("decision", request=r.id, approve=approve, **rec)

        if not approve:
            del self.open[r.id]
            return {"status": "rejected", "reason_code": reason_code}
        if r.satisfied():
            del self.open[r.id]
            self._log("executed_after_approval", request=r.id,
                      approvals=[x["reviewer"] for x in r.approvals])
            return {"status": "approved", "revalidate_preconditions": True}
        return {"status": "pending", "have": len(r.approvals), "need": r.needed()}

    def _expire(self, r: Request) -> dict:
        del self.open[r.id]
        outcome = "abandoned_fail_closed" if self.fail_closed else "auto_approved_by_timeout"
        self._log("expired", request=r.id, outcome=outcome)
        return {"status": outcome}

    def sweep(self) -> list[dict]:
        return [self._expire(r) for r in list(self.open.values()) if time.time() > r.expires]

    # --- the metric that actually matters ----------------------------------
    def rubber_stamp_report(self, review_target_s: float = 45.0) -> dict:
        d = [e for e in self.audit if e["event"] == "decision"]
        if not d:
            return {"decisions": 0}
        lat = sorted(x["latency_s"] for x in d)
        approvals = [x for x in d if x["approve"]]
        return {
            "decisions": len(d),
            "p50_latency_s": lat[len(lat) // 2],
            "fast_approvals_pct": round(
                100 * sum(1 for x in approvals if x["latency_s"] < 5) / max(1, len(approvals)), 1),
            "override_rate_pct": round(100 * (1 - len(approvals) / len(d)), 1),
            "below_review_target_pct": round(
                100 * sum(1 for x in d if x["latency_s"] < review_target_s) / len(d), 1),
            "evidence_mismatch": sum(1 for x in d if not x["shown_matches_request"]),
        }


if __name__ == "__main__":
    tools = {
        "search_kb":   ToolRisk("search_kb", Klass.READ_ONLY, "trivial", "one", "none"),
        "update_note": ToolRisk("update_note", Klass.WRITE, "compensating", "one", "internal"),
        "send_email":  ToolRisk("send_email", Klass.WRITE, "none", "one", "external_visible",
                                rate_risk=True, rate_cap_per_hour=20),
        "issue_refund": ToolRisk("issue_refund", Klass.FINANCIAL, "compensating", "one",
                                 "external_visible"),
        "bulk_close":  ToolRisk("bulk_close", Klass.WRITE, "compensating", "bounded", "internal"),
        "drop_table":  ToolRisk("drop_table", Klass.DESTRUCTIVE, "none", "unbounded", "internal"),
        "delete_user": ToolRisk("delete_user", Klass.DESTRUCTIVE, "none", "one", "internal"),
    }
    b = ApprovalBroker(ttl=900, fail_closed=True)

    for name, act in [
        ("search_kb", Action("search_kb", {"q": "refund policy"}, diff="(no change)")),
        ("update_note", Action("update_note", {"id": 7}, diff="- draft\n+ draft v2")),
        ("send_email", Action("send_email", {"to": "a@b.com"},
                              diff="+ Subject: Your refund\n+ Body: ...",
                              evidence=[{"doc": "policy/refunds-v2.1", "loc": "§3.2"}])),
        ("issue_refund", Action("issue_refund", {"inv": "INV-8841"},
                                diff="- balance 49.00\n+ balance 0.00", amount=49.0,
                                evidence=[{"doc": "billing/INV-8841", "loc": "chars 400-460"}])),
        ("delete_user", Action("delete_user", {"id": 991}, diff="- user 991 (permanent)")),
        ("drop_table", Action("drop_table", {"t": "events"}, diff="- table events")),
    ]:
        out = b.submit(tools[name], act, requester="agent:support@v12",
                       on_behalf_of="user:hari")
        print(f"{name:14} -> {out['gate']:20} {out['status']:8} {out.get('reason','')}")
        if out["status"] == "pending":
            # agent trying to approve itself: must be refused
            print("   self-approve:", b.decide(out["request_id"], "agent:support@v12", True))
            print("   human:", b.decide(out["request_id"], "user:reviewer-1", True,
                                        "verified against invoice"))

    print("\nrubber-stamp report:", b.rubber_stamp_report())
```

Running it: `search_kb` auto-executes, `update_note` gets notify-and-proceed with an undo window, `send_email` and `issue_refund` require one approval, `delete_user` requires two, and `drop_table` is denied outright as unbounded destructive. Every self-approval attempt is refused on separation of duties. And note what `rubber_stamp_report()` prints for the demo: `p50_latency_s: 0.0`, `fast_approvals_pct: 100.0`, `override_rate_pct: 0.0` — the detector correctly flags the script's own instant approvals as rubber-stamping. That is the metric working, and it is the output to show a skeptical interviewer.

Three properties to defend in an interview: gate selection is a **pure function of registered action properties**, so it is unit-testable and diffable in code review rather than being a judgment call at runtime; **separation of duties is enforced in the broker**, so an agent cannot approve itself even if a prompt injection convinces it to try; and the audit record stores a **digest of the evidence bundle plus the decision latency**, which together are the only mechanism that can distinguish informed approval from a rubber stamp after the fact.

Lab **`(lab pending)`** wires this to LangGraph `interrupt()` with a Postgres checkpointer, adds the error-injection harness that measures reviewer catch rate, and implements the autonomy ratchet with automatic demotion on incident.

---

## How it's done in production

**Framework primitives.** LangGraph `interrupt()` plus a durable checkpointer (Postgres in production) is the reference implementation: the graph suspends to storage, the approval lives outside the process, and `Command(resume=...)` continues from the interrupt point. This matters because the alternative — holding a run in memory while a human is at lunch — breaks on any deploy. Temporal signals give the same shape for long-running workflows. The OpenAI Agents SDK exposes tool-approval hooks. MCP's elicitation flow lets a server request user input mid-call. Coding agents ship permission modes with per-tool allowlists and a plan-then-execute mode, which is the consumer version of dry-run-plus-diff.

**Control plane placement.** In-framework gating is fast and context-rich and is bypassable by any code path that calls the tool directly. An external control layer (its own service, its own policy store, its own identity for each agent) gives uniform enforcement across agents and languages and a single audit sink, at the cost of a network hop and a hard dependency in the request path. The pattern that holds up: **authorisation at the credential boundary** (scoped, short-lived tokens per agent, so an unpermitted action fails at the API and never reaches a human), **policy-as-code for gate selection** in a shared library, and **the approval broker as a service** so the audit log is central and tamper-evident.

**Observability that actually detects decay** — this is the part teams skip, and it is what an auditor asks for:

| Metric | Healthy | Alarm |
|---|---|---|
| Approval decision p50 latency | Near your designed review time | **< 5s means click-through** |
| Override / rejection rate | A few percent, non-zero | **~0% means the gate is decorative** |
| Error-injection catch rate | Stable and high | Falling = design decay, not a training problem |
| Gated actions vs review capacity | Below capacity | Above = unplanned sampling with unknown coverage |
| Queue age p95 | Under the expiry TTL | Above = fail-closed abandonments rising |
| Timeout outcomes | Rare | Rising = staffing or routing problem |
| Bulk-approve usage on irreversible classes | **Zero, because the affordance should not exist** | Any usage is a design bug |

### What breaks at scale

| Symptom | Cause | Fix |
|---|---|---|
| Approval p50 is 3 seconds; nothing is ever rejected | Rubber-stamping; queue above capacity, intent shown instead of diff | Narrow gate criteria, show diffs with inline evidence, run error injection, publish catch rate |
| Reviewers approve in batches of 40 | A bulk-approve control exists on an irreversible class | Remove the affordance; per-item decisions for irreversible actions |
| Agent deleted the wrong records and nobody can say who approved | No audit of parameters, or approval recorded without the diff | Immutable record: params, computed diff, policy version, evidence digest, reviewer, latency |
| An outage in the approval service let actions through | Fail-open default on an irreversible class | Fail-closed for irreversible/financial; log timeout outcomes distinctly from approvals |
| Approved action executed against changed state | No precondition re-validation at execution | Approval binds to a specific diff; re-check preconditions and fail if they moved |
| Prompt injection persuaded the agent it had approval | Gate implemented in the prompt, not in the harness | Gate in code at the tool boundary; tier is a property of the action, never of the instruction |
| Agent approved its own request via a tool | No separation of duties in the broker | Enforce requester ≠ approver, reject any `agent:` principal as approver |
| One agent's runaway loop sent 900 emails | No rate cap; approvals were per-action and the reviewer clicked through | Rate caps independent of approvals; a human cannot review 900 of anything |
| Throughput fell 70% after adding gates | Gated an action class where review time is comparable to the work saved | Recompute `S/R`; convert to dry-run validation, undo windows, or explicit sampling |
| Agent runs die during long approvals | Run held in memory rather than checkpointed | Durable checkpointer; suspend to storage and resume |
| Auditor asks what the reviewer saw and you cannot answer | Evidence bundle not persisted | Store the bundle or its digest with the decision |

---

## Tradeoffs & when NOT to use it

- **Do not gate read-only actions.** It trains reviewers to click, consumes the capacity you need for the actions that matter, and protects nothing. Log and sample instead.
- **Prefer reversibility over approval.** Soft delete with a tombstone, a delayed send with a cancel window, a config change behind a flag. Approvals scale linearly with volume; undo windows do not. Buying reversibility is almost always cheaper than buying human attention.
- **Do not put a human where a deterministic check works.** Row-count bounds, tenant scoping, amount thresholds, target regexes, and schema validation run in milliseconds on 100% of actions. A human runs in 90 seconds on 10%. Spend the human on judgment, not on assertions.
- **Do not gate at 100% if you cannot staff the queue.** An over-capacity queue is unplanned sampling with unknown coverage, which is strictly worse than explicit sampling with known coverage. Choose the sampling rate deliberately and document it.
- **Do not gate where the reviewer cannot judge.** If a non-expert is asked to approve a clinical or legal determination, the gate transfers liability without adding scrutiny, which is worse than no gate because it manufactures a record of approval. Either route to someone competent or redesign the action.
- **More gates is not more safety past a point.** Beyond the review capacity limit, each additional gate reduces attention per gate, and total protection can fall. This is the alert-fatigue result, and the adjacent numbers are not ambiguous: 63% of security alerts go unaddressed, 46% are false positives, 71% of analysts are burned out.
- **Human oversight does not substitute for the technical controls.** A confidence gate, a grounding check, and constrained tool schemas are cheaper and more reliable than a human, and a human placed downstream of a bad pipeline will not fix it. Oversight is the last layer, not the first.
- **Do not let the gate become accountability laundering.** If the catch rate is near zero, the human's signature transfers blame without transferring scrutiny — which is the specific pattern regulators are now looking for under the automation-bias language in Article 14, and the specific pattern the 2025 European Commission "ritual supervision" finding described.
- **Where a synchronous gate is genuinely intolerable** — sub-second interactive latency, or an action that must complete inside a transaction — do not fake it with a 200ms timeout. Redesign: make the action reversible, restrict it to a validated subset, or take it out of the agent's hands entirely.

---

## Interview questions

### Q1 — Where do you put approval gates in an agent system?
**Testing:** whether you have a principle or a list.
**Answer:** As a function of the action's properties, evaluated at tool-registration time and enforced in code: irreversibility, blast radius, and externality, with rate risk handled separately. Reversible and small gets auto-plus-log; reversible with bounded radius gets notify-and-proceed with an undo window; irreversible or externally visible or financial gets a synchronous approval with a diff; irreversible with multi-record scope or high value gets dual approval; unbounded destructive is not in the toolset at all. The `read_only / write / financial / destructive` taxonomy is the shared vocabulary but it is not sufficient on its own, because "write" spans a draft edit and a production config overwrite. Two hard rules: destructive actions stay gated at every autonomy level, and the tier is never a function of what the model asked for, because prompt injection's entire purpose is to make the agent believe it is authorised.
**Follow-up trap:** *"An action is reversible in the database but sends an email. Which tier?"* — irreversible. Externality dominates reversibility; you cannot un-send. The general rule is that anything a third party observes — email, payment, public post, filed document — is irreversible in practice regardless of what your data model can roll back.

### Q2 — Your gates are being rubber-stamped. How do you know, and what do you do?
**Testing:** the core of the module.
**Answer:** How I know, from telemetry: approval decision p50 latency, and if it is under about five seconds on a decision designed to take 45-90 seconds, that is click-through; override rate, where near zero means the gate is decorative; queue volume against computed review capacity, since above capacity you have unplanned sampling; and bulk-approve usage, which should be impossible on irreversible classes. Then the definitive test, which is error injection: corrupt a claim, target id, or amount in a small random percentage of proposed actions and measure the catch rate. What I do: reduce the number of gates so attention concentrates where it matters, replace intent with a computed diff plus inline evidence at the decision point, remove any bulk-approve affordance on irreversible classes, make rejection one click with a reason code and make sure a rejection is respected rather than retried, and publish the catch rate as an SLI so decay is visible. What I do not do is retrain the reviewers, because this is a design failure and not an attention failure — the adjacent-domain numbers say the same thing every time: 63% of security alerts unaddressed, 46% false positives, 71% analyst burnout.
**Follow-up trap:** *"Isn't error injection deceiving your own staff?"* — it is testing a control, and it needs to be disclosed as part of the role, agreed with the people managers, never used for individual performance management, and reported only in aggregate. Framed that way it is a standard safety practice, the same as a fire drill or a chaos experiment. Framed as gotcha surveillance it destroys the trust the control depends on. That distinction is the answer.

### Q3 — Design oversight for an agent that processes refunds up to $500.
**Testing:** concrete design with numbers.
**Answer:** Tool registration first: `issue_refund` is `financial`, reversibility compensating (a reverse charge exists but the customer sees the original), externality external-visible, rate risk yes. Gate ladder by amount and evidence: under $50 with an entailed policy citation and a matching invoice, auto-execute with a notify and a 10-minute cancel window; $50-500, synchronous single approval showing the computed diff (balance before and after), the invoice span, and the policy section, with the reviewer able to reject in one click with a reason code; above $500 is out of scope for the agent entirely, escalate to a human workflow. Independent of all of that, a rate cap: at most N refunds per hour and a per-day currency total, because a human cannot review a runaway loop and the cap is what actually bounds the damage. Separation of duties enforced in the broker, so the agent cannot approve itself and the requester cannot be the approver. Approvals expire at 15 minutes and fail closed, with preconditions re-validated at execution so an approval for a specific diff cannot execute against changed state. Audit record includes the params, the diff, the policy version, the evidence digest, the reviewer, the reason code, and the decision latency. SLIs: approval p50 latency, override rate, error-injection catch rate, and the auto-executed fraction, and the auto threshold ratchets up only on evidence.
**Follow-up trap:** *"How would you raise the auto-approve threshold from $50 to $200?"* — with an evidence ratchet, not a decision in a meeting. Require a minimum volume of $50-200 refunds that passed approval with no reviewer override and no downstream dispute, say a few hundred over a defined window, then shadow-run the proposed policy: keep gating but record what the new policy *would* have auto-approved, and compare against reviewer decisions. Promote only if the disagreement rate is under a stated threshold, and wire automatic demotion on incident. Deletes and unbounded actions never participate in the ratchet.

### Q4 — What does the EU AI Act actually require for human oversight?
**Testing:** whether you have read it or absorbed a summary.
**Answer:** Article 14 applies to high-risk systems from 2 August 2026 and puts a **design** obligation on the provider: the system must be built, including its human-machine interface, so that oversight persons can understand its relevant capacities and limitations, remain aware of the tendency to over-rely on the output — automation bias is named in the text — correctly interpret the output, decide not to use it or to disregard, override, or reverse it, and intervene or halt operation via a stop button or comparable procedure. Article 26 adds deployer duties including assigning competent, trained oversight persons. Article 50 transparency provisions and the GPAI documentation stack apply the same day, with penalties reaching €35M or 6-7% of global turnover depending on the provision. The engineering consequence that people miss: because it is a design obligation, a UI that makes override impractical is non-compliant even with a human sitting there, so a rubber-stamped queue is a compliance finding, not just a quality problem.
**Follow-up trap:** *"We're US-only. Does it matter?"* — the Act's scope is about the EU market, so check that first rather than assuming either way. But the requirements have become the de facto template regardless: NIST AI RMF and ISO/IEC 42001 push the same controls, and enterprise procurement questionnaires now ask for a tested kill switch, scoped per-agent credentials, exportable immutable audit logs, RBAC with separation of duties on approvals, and a named accountable owner. Building to Article 14 is cheaper than retrofitting when the first enterprise buyer asks.

### Q5 — Approval service is down. What happens?
**Testing:** whether you have thought about the gate's own failure mode.
**Answer:** It depends on the tier and it must be decided in advance, not by whatever the code happens to do. Irreversible, financial, and destructive actions **fail closed**: the run suspends or abandons the action and notifies, because an unreviewed irreversible action is exactly what the gate exists to prevent. Reversible bounded actions may **fail open** and proceed, but only if blocking is itself a harm, and the outcome must be logged distinctly as auto-approved-by-timeout rather than silently as an approval, so the audit trail does not claim a review that never happened. Then the operational parts: the run must be checkpointed so a suspension is resumable rather than a lost run, requests carry an expiry so nothing executes against stale approvals, and timeout outcomes are a monitored metric because a rising rate is a staffing or routing problem. The classic incident is exactly the inverted version of this: fail-open on everything, so a queue outage becomes an unreviewed-action outage that nobody notices until the postmortem.
**Follow-up trap:** *"Fail-closed means an outage stops the business. Acceptable?"* — for irreversible actions, yes, and it is the same tradeoff as a payment processor rejecting rather than double-charging. The mitigations are on availability and on scope: make the broker highly available and simple, provide a documented break-glass path with elevated logging and mandatory post-hoc review, and shrink the set of actions that need synchronous approval so the outage's blast radius is small. What I would not do is make the default fail-open to protect an availability number.

### Q6 — Give me the audit record fields, and tell me which one people forget.
**Testing:** whether you have been through an audit.
**Answer:** Agent identity and version, prompt version, model and version; the human principal it acted on behalf of and the credential's scope; the requested action with full parameters and the computed diff; the policy id and version that selected the gate; the reviewer identity, decision, reason code, and **decision latency**; overrides and disagreements; the execution result and any rollback. The forgotten field is **the evidence bundle the reviewer was actually shown**, or its hash. Without it you cannot distinguish an informed approval from a rubber stamp after the fact, which is precisely what an Article 14 audit probes, and you cannot detect the bug where the UI showed the reviewer something different from what the request contained. Decision latency is the second most-forgotten and it is your rubber-stamp detector.
**Follow-up trap:** *"Why store the policy version?"* — because "why was this action gated this way?" is unanswerable without it, and gate policy changes over time. If the policy is code and versioned, the audit record plus the policy version reconstructs the decision exactly. Without it your best answer to an auditor is "that's how it works now", which is not an answer about what happened in March.

### Q7 — Explain the tension between gates and the value of automation. Quantify it.
**Testing:** whether you can make this a numbers conversation.
**Answer:** If an action saves `S` minutes of human work and reviewing it costs `R` minutes, gating a fraction `g` of actions leaves `S − g·R − wait_cost`. At `S=10, R=1.5`, gating everything keeps 85% of the value, which is fine. At `S=10, R=5` you keep half, which is painful but may be worth it. At `S=2, R=1.5` you keep a quarter, the reviewer is the bottleneck, and rubber-stamping is not a risk but a certainty because the economics force speed. The term people forget is `wait_cost`: a synchronous mid-run gate blocks the agent, so a 15-minute approval latency turns a 40-second task into a 15-minute one, and if the run holds a lock or a connection you have created a capacity problem too. That is why durable checkpointing is a prerequisite for approval gates rather than a nice-to-have.
**Follow-up trap:** *"So how do you decide the gate set?"* — evidence-based ratcheting. Start gated per action class, measure the error rate and the reviewer catch rate, and graduate a class to notify-and-proceed after a defined volume of clean executions, with automatic demotion on incident. Deletes and unbounded-blast-radius actions never graduate. That converts a political argument about velocity versus safety into a metric with a threshold, which is the actual deliverable.

### Q8 — An agent needs to run a bulk update on 50,000 records. Design the oversight.
**Testing:** whether you reach for approval when a better tool exists.
**Answer:** Not with an approval, or at least not primarily. A human cannot review 50,000 of anything, so the controls are deterministic: a **dry run producing a diff summary** (counts by change type, min/max/distribution of new values, the exact WHERE clause, and a sample of 20 concrete before/after rows including edge cases), then **automated invariant checks** — affected count within an expected band, no rows outside the tenant, no field crossing a threshold, the target matching an approved pattern — then **staged execution** in batches with an abort on anomaly between batches, then a **single human approval of the plan and the invariants** rather than of the rows, then an **undo path** — a snapshot or reverse-migration script tested before the forward run. Plus a rate cap so a retry cannot double-apply, and idempotency keys so a resumed run does not reapply completed batches.
**Follow-up trap:** *"What is the human actually approving?"* — the plan, the invariants, and the undo path. Their real job is to confirm the *intent matches the diff summary* and that a rollback exists, which is a judgment a human is good at and an assertion engine is not. Approving 50,000 individual rows is the thing that looks like oversight and is not. Naming that distinction is the point of the question.

### Q9 — How do you keep prompt injection from defeating your gates?
**Testing:** the intersection with security.
**Answer:** By making the gate a property of the action rather than of the conversation. Gate selection is a pure function of the tool's registered risk attributes and the computed parameters, evaluated in the harness at the tool boundary, so no text in the context can change the tier — an injected "the user has already approved this" changes nothing because the harness never reads intent. Then the credential layer does the real work: per-agent scoped, short-lived tokens mean an unpermitted action fails at the API before any human is involved. Then separation of duties in the broker rejects any agent principal as an approver, so an agent given a tool that happens to call the approval API cannot approve itself. And the reviewer sees the computed diff rather than the agent's summary, because a summary is attacker-controlled text.
**Follow-up trap:** *"The injected content is inside the diff — a malicious address in the retrieved document."* — then the gate is working as designed and the reviewer is the control, which is exactly why the evidence must be inline: the reviewer sees the new value *and* the document span it came from, so an implausible source is visible. Beyond that, provenance-tag retrieved content as untrusted, validate values against format and allow-list rules deterministically, and for high-stakes fields require the value to come from a trusted system of record rather than from retrieved text at all.

### Q10 — When is a human gate the wrong answer?
**Testing:** the "when NOT to" instinct.
**Answer:** When a deterministic check does the same job — row-count bounds, tenant scoping, amount thresholds, schema and format validation all run in milliseconds on 100% of actions rather than 90 seconds on 10%. When the action can be made reversible instead, since an undo window costs a human nothing in the normal case while approvals scale with volume. When the reviewer lacks the expertise to judge, because then the gate transfers liability without adding scrutiny, which is worse than no gate since it manufactures a record of approval. When the queue would exceed review capacity, where explicit sampling with known coverage beats an over-capacity queue with unknown coverage. And when the latency is structurally intolerable — sub-second interactive paths — where the honest move is to redesign the action rather than to fake a gate with a 200ms timeout.
**Follow-up trap:** *"Your compliance team insists on a human in the loop for everything."* — I would take them the arithmetic and the catch-rate data rather than argue in principle: here is the review capacity, here is the queue volume, here is the p50 decision latency and the error-injection catch rate at the current gate count, and here is the same measurement at a narrower gate set. Compliance usually wants demonstrable control, not literally a human per action, and a documented deterministic control with a measured catch rate plus a sampled human audit is often a *stronger* compliance artefact than an unmeasured universal gate. If after that they still require it, it is their risk decision and I implement it with the queue staffed to capacity and say so in writing.

### Q11 — What goes in the escalation design?
**Testing:** completeness on the operational object.
**Answer:** Six explicit decisions. Timeout and default per tier, fail-closed for irreversible and financial, fail-open only for reversible bounded actions and logged distinctly. Request expiry, with preconditions re-validated at execution, because an approval binds to a specific diff and not to an intent. Who may approve, enforced as separation of duties with the approver holding the underlying permission in their own right and the agent never holding the approval credential. Tiering with target response times: operator on shift, then domain owner, then the accountable executive for the top band, each with a named fallback. Batching rules: batch presentation is fine for homogeneous reversible actions, per-item decisions are mandatory for irreversible ones, and never a select-all across a heterogeneous batch. And a tested kill switch that halts an agent class immediately and leaves in-flight work resumable, which Article 14 requires and every enterprise security questionnaire asks for by name.
**Follow-up trap:** *"How do you know the kill switch works?"* — you exercise it in a game day, in production, on a schedule, and you measure time-to-halt and whether in-flight runs resumed cleanly afterwards. An untested kill switch is a comment in a runbook. And I would check the failure mode nobody tests: whether halting mid-run leaves partial side effects, which is a compensating-transaction design problem and not a switch problem.

### Q12 — Who is accountable when an agent does something wrong?
**Testing:** whether you will give a straight answer.
**Answer:** A named human. Every agent has an owner, and actions are attributed through the delegation chain to a person — the principal on whose behalf it acted, the reviewer who approved, and the owner who deployed it with those permissions. "The AI did it" is never a resolution, and regulators are explicit: deployer duties under Article 26 cannot be delegated to a vendor or to a model. Practically that means the audit record must carry the delegation chain, the owner is on the incident rota for their agent, and post-incident review covers the *policy* that permitted the action rather than only the model's behaviour, because the model behaving unexpectedly is the expected case and the gate not catching it is the finding.
**Follow-up trap:** *"The reviewer approved it in three seconds. Is it their fault?"* — no, or at least not primarily. A three-second p50 on a decision designed to take a minute is a design failure: the queue was over capacity, or the UI showed intent instead of a diff, or there was a bulk-approve affordance that should not exist. Blaming the reviewer is how organisations avoid fixing the system, and it is also how you lose the reviewer. The accountable party is the owner of the oversight design, and the corrective action is on the design.

### Q13 — Rank oversight investments by protection per unit of cost.
**Testing:** prioritisation.
**Answer:** 1) **Remove the action** from the toolset where there is no legitimate agent use — free and absolute. 2) **Scoped, short-lived per-agent credentials**, so unpermitted actions fail at the API and never reach a human. 3) **Deterministic invariant checks and dry-run diffs**, milliseconds on 100% of actions and they catch most of what a reviewer would. 4) **Reversibility** — soft deletes, delayed sends, flagged config — which converts approvals into undos. 5) **Rate caps**, cheap and the only thing that bounds a runaway loop. 6) **Narrow, well-designed approval gates** with diffs and inline evidence on the genuinely irreversible set. 7) **Immutable audit with evidence digest and decision latency**, which is how you find out any of this is working. 8) **Error-injection catch-rate measurement**, which is how you keep it working. Dead last: adding more gates. It is the intuitive move and past the capacity limit it reduces total protection.
**Follow-up trap:** *"Why is audit only seventh if it's what regulators ask for?"* — it is ranked by *protection*, and audit is detective rather than preventive: it tells you what happened, it does not stop it. For a compliance deliverable it moves to the top, and I would build it in parallel rather than sequentially since it is cheap and it is the substrate every other item's measurement depends on. Ranking by protection and sequencing by dependency are different questions, and it is worth saying which one you are answering.

---

## Red flags that fail you

- Gating everything, with no reference to review capacity or the value the automation was supposed to create.
- Not knowing that rubber-stamping is the dominant failure mode, or having no way to detect it.
- Showing the reviewer the agent's stated intent instead of the computed diff.
- No error-injection measurement, so the gate's effectiveness is an assumption.
- A bulk-approve control on an irreversible action class.
- Fail-open defaults on financial or destructive actions.
- Implementing the gate in the prompt rather than in the harness at the tool boundary.
- No separation of duties, so an agent can approve its own request.
- Treating a human gate as a substitute for grounding checks, confidence thresholds, and constrained schemas.
- Audit record with no evidence bundle, no decision latency, and no policy version.
- "The AI did it" as an accountability answer.
- Not knowing the 2 August 2026 EU AI Act Article 14 date, or believing it is a staffing rather than a design obligation.

## Cheat card

```
GATE = f(irreversibility, blast radius, externality)  ⨯ rate cap.  NOT f(scary tool name).
  reversible + small          → AUTO + LOG (+ sample for audit)
  reversible + bounded        → NOTIFY-AND-PROCEED + undo window
  irreversible OR external-visible OR financial → SYNCHRONOUS APPROVAL w/ DIFF
  irreversible + multi-record / high value      → DUAL APPROVAL (four-eyes)
  unbounded destructive       → PROHIBITED (not in the toolset)
  DELETE STAYS GATED AT EVERY AUTONOMY LEVEL. No ratchet.
  Externality > reversibility: you cannot un-send an email.
  Tier is a property of the ACTION, never of the instruction (prompt injection).

REGISTER PER TOOL  class(read_only|write|financial|destructive) · reversibility(trivial|
  compensating|none) · max_blast(one|bounded|unbounded) · externality · rate_risk + cap

BEST PATTERNS (before you reach for a human)
  1 remove the action from the toolset
  2 scoped short-lived per-agent credentials → fails at the API, no human involved
  3 DRY RUN + DIFF + deterministic invariants (ms, 100% of actions, catches most of it)
  4 REVERSIBILITY instead of approval (soft delete, delayed send, feature flag)
  5 RATE CAPS — the only thing that bounds a runaway loop; a human can't review 900 emails
  6 then narrow, well-designed approval gates

MEANINGFUL REVIEW  show the DIFF not the intent · evidence INLINE at the decision point ·
  "no" is one click AND respected (no instant re-propose) · bounded queue ·
  NO bulk-approve on irreversible classes · measured by ERROR INJECTION catch rate

RUBBER-STAMP DETECTORS   approval p50 < 5s on a 45-90s decision · override rate ≈ 0% ·
  queue > capacity (= unplanned sampling, unknown coverage) · bulk-approve usage > 0
  catch rate DECAYS over time → that's a design signal, not a training problem
BASE RATES  2,992 alerts/day, 63% unaddressed (Vectra '26) · 46% false positives (MS SOC '26)
  73% name FPs top challenge, 76% cite alert fatigue (SANS '25) · 71% analyst burnout (Tines)
  EU Commission 2025: oversight degenerates into "ritual supervision"

ESCALATION  timeout default per tier: FAIL-CLOSED for irreversible/financial, fail-open only
  for reversible+bounded and LOG IT AS timeout-not-approval · request EXPIRY + re-validate
  preconditions at execution (approval binds to a DIFF, not an intent) · SoD: requester ≠
  approver, agent can never approve itself · tiers w/ target response times · TESTED kill switch

AUDIT RECORD  agent@ver · prompt@ver · model@ver · principal + credential scope · params +
  computed diff · POLICY id@VERSION · reviewer · decision · reason code · DECISION LATENCY ·
  overrides · result · rollback · ★ THE EVIDENCE BUNDLE THE REVIEWER WAS SHOWN (or its hash)
  ← the two starred/bolded fields are what distinguish informed approval from a rubber stamp

REGULATION  EU AI Act Art 14 (high-risk) applies 2 Aug 2026 — a DESIGN obligation:
  understand capacities+limits · be aware of AUTOMATION BIAS (named in the text) ·
  interpret output correctly · disregard/override/reverse · STOP BUTTON or equivalent
  Art 26 deployer duties (competent trained oversight persons) · Art 50 + GPAI docs same day
  penalties to €35M / 6-7% global turnover · also NIST AI RMF, ISO/IEC 42001
  ⇒ a rubber-stamped queue is a COMPLIANCE finding, not just a quality problem
BUYER CHECKLIST  tested kill switch · scoped per-agent creds · exportable immutable audit +
  retention · RBAC + SoD on approvals · documented risk tiers · data residency · named owner

ECONOMICS  net = S − g·R − wait_cost ;  break-even g = S/R
  S=10 R=1.5 → keep 85% ✅ · S=10 R=5 → 50% · S=2 R=1.5 → 25% and rubber-stamping is CERTAIN
  wait_cost: a synchronous gate BLOCKS the run → durable checkpointing is a PREREQUISITE
RESOLUTION  evidence-based autonomy ratchet: gated → notify after N clean runs, auto-demote
            on incident. Deletes never ratchet.
ACCOUNTABILITY  named human owner per agent · attribute through the delegation chain ·
  "the AI did it" is never a resolution · deployer duties cannot be delegated to a vendor
```

## Sources

- [Article 14: Human Oversight — EU Artificial Intelligence Act](https://artificialintelligenceact.eu/article/14/) — accessed 2026-07-26
- [Human Oversight EU AI Act Compliance: Article 14 Requirements Guide 2026 (ActProof)](https://actproof.ai/blog/human-oversight-ai-act-compliance) — accessed 2026-07-26
- [EU AI Act Article 14: What Human Oversight Means for AI Systems in Production (DeepInspect)](https://www.deepinspect.ai/blog/eu-ai-act-article-14-human-oversight) — accessed 2026-07-26
- [The Meaning—and Illusion—of Human Oversight of AI](https://mediate.com/the-meaning-and-illusion-of-human-oversight-of-ai/) — accessed 2026-07-26
- [AI Explainability: How to Avoid Rubber-Stamping Recommendations — MIT Sloan Management Review](https://sloanreview.mit.edu/article/ai-explainability-how-to-avoid-rubber-stamping-recommendations/) — accessed 2026-07-26
- [Exploring automation bias in human–AI collaboration: a review and implications for explainable AI (AI & Society)](https://dl.acm.org/doi/10.1007/s00146-025-02422-7) — accessed 2026-07-26
- [Automation Bias in Large Language Model Assisted Diagnostic Reasoning Among AI-Trained Physicians (medRxiv)](https://www.medrxiv.org/content/10.1101/2025.08.23.25334280.full.pdf) — accessed 2026-07-26
- [Alert fatigue: causes, real cost, and how to fix it (Vectra AI)](https://www.vectra.ai/topics/alert-fatigue) — accessed 2026-07-26
- [What the 2025 SANS Detection & Response Survey Reveals: False Positives & Alert Fatigue Are Worsening](https://www.stamus-networks.com/blog/what-the-2025-sans-detection-response-survey-reveals-false-positives-alert-fatigue-are-worsening) — accessed 2026-07-26
- [Human-in-the-Loop: A 2026 Guide to AI Oversight (Strata)](https://www.strata.io/blog/agentic-identity/practicing-the-human-in-the-loop/) — accessed 2026-07-26
- [AI Agent Governance and Compliance in 2026: Frameworks, Audit Trails, and the Regulatory Reckoning (Zylos)](https://zylos.ai/research/2026-05-01-ai-agent-governance-compliance-2026/) — accessed 2026-07-26
- [The Complete Guide to AI Agent Security for Enterprises 2026 (NeuralTrust)](https://neuraltrust.ai/blog/ai-agent-security-enterprises-complete-guide) — accessed 2026-07-26
- [Human-in-the-Loop AI Agents: Approvals, Permissions, and Audit Trails (TeamCopilot)](https://teamcopilot.ai/blog/human-in-the-loop-ai-agents-approvals-permissions-audit-trails) — accessed 2026-07-26
- [International AI Safety Report 2026 (arXiv:2602.21012)](https://arxiv.org/pdf/2602.21012) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
