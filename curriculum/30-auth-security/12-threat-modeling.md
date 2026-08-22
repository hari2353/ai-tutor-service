# Threat Modeling: STRIDE, Attack Trees, Trust Boundaries, Doing It in 45 Minutes

> **Track:** T30 Auth & Application Security · **Time:** 2h · **Prereqs:** `T30-web-attacks`, `T30-api-security`, `T21-architecture-principles` · **Updated:** 2026-07-26
> **Module id:** `T30-threat-modeling` · **Tags:** process

## The 30-second version

Threat modeling is STRIDE applied per element of a data-flow diagram (Spoofing, Tampering, Repudiation, Information Disclosure, Denial of Service, Elevation of Privilege), walked specifically at every trust boundary — the lines on the diagram where privilege, network zone, or identity changes across an arrow. Attack trees take the highest-value threats found that way and decompose them into AND/OR paths from a root goal ("exfiltrate all user PII") down to concrete, rankable leaf actions, so you can see which path is actually cheapest for an attacker rather than treating every threat as equally likely. DREAD — the damage/reproducibility/exploitability/affected-users/discoverability scoring rubric Microsoft shipped alongside STRIDE — fell out of favor because it gives false precision: five people scoring the same threat produce five different numbers, and averaging ordinal 1-10 guesses as if they were interval measurements doesn't make the result more objective, it just makes disagreement harder to see. The fix that actually works under time pressure is a hard 45-minute box: draw or confirm the diagram, run STRIDE per element, rank threats on a coarse likelihood-by-impact grid instead of DREAD math, and end with 5-8 tickets with owners — not a document. Threat modeling only earns its keep in design review if it's triggered specifically by "does this add a trust boundary, a new external integration, or a new class of sensitive data" — not run as a blanket ritual on every PR, and not skipped entirely because "we'll get to it before launch."

## Why this gets asked

Because nearly everyone can recite the STRIDE acronym and almost nobody has actually run a threat model that produced work instead of a document. The interviewer has sat through both failure modes: the unbounded whiteboard session that burns an afternoon and ends with a list of forty theoretical threats nobody triages, and the compliance-driven threat-model doc that gets written once before a security sign-off, filed away, and is completely stale six months and thirty PRs later when the actual incident happens. What they want to see is whether you treat threat modeling as a working engineering practice with a time box and an output contract, or as either security theater or an open-ended academic exercise. At staff/principal level they're also probing whether you know where the boundaries actually are on a real system — not whether you can draw the classic three boxes from a textbook.

---

## Lineage: past → present → future

**What came before.** Before a named process existed, security review was ad hoc: a senior engineer or a dedicated security team looked at a design in a hallway conversation or a pre-launch checklist, with no structured way to guarantee coverage across a system's attack surface, and outcomes depended entirely on which reviewer you happened to get. Microsoft formalized STRIDE and DREAD together as part of its Security Development Lifecycle (SDL) in the early-to-mid 2000s, pairing a structured threat-identification taxonomy (STRIDE) with a structured scoring rubric (DREAD) specifically to make review outcomes less reviewer-dependent. The pain that killed DREAD specifically was that the scoring didn't actually remove the subjectivity it was designed to remove — Microsoft's own internal teams found that DREAD ratings were inconsistent between reviewers scoring identical threats, since "how discoverable is this" and "how much damage" are judgment calls dressed up as numbers, and treating the resulting 1-10 scores as if they could be meaningfully averaged or summed produced a false sense of rigor that didn't survive contact with a second reviewer.

**Where it stands now.** STRIDE-per-element plus attack trees plus explicit trust-boundary marking is the working combination in most serious practice: STRIDE (or PASTA for a more business-risk-driven variant, or LINDDUN specifically for privacy threats) identifies *what kinds* of threats are possible at each part of the system, and attack trees chain the interesting ones into concrete attacker paths worth actually pricing out. DREAD is still used informally at some shops for lack of anything else, but the more common replacement is a coarse categorical likelihood-by-impact grid, because a 3x3 or 4x4 bucket with defined anchors produces more consistent triage than pretending five sub-scores multiply into a precise number. The live disagreement in 2026 is how much of the *initial* pass — drafting the DFD, generating a candidate threat list — can be handed to an AI assistant (tools like `stride-gpt` exist specifically for this) versus requiring a human who actually knows the org's trust boundaries and constraints to do it; early results are that AI-assisted first drafts save real time on enumeration but still need a human to catch the org-specific stuff (which vendor is actually trusted, which team owns which boundary) that isn't written down anywhere the model can read it.

**Where it's heading.** The clear direction of travel is shift-left tooling: threat-model triggers embedded directly into design-doc templates and PR templates so the question gets asked at the point a trust boundary is proposed, not retrofitted before a launch date. AI-assisted first-pass threat generation from an architecture diagram or ADR is real and shipping in various forms, used to accelerate the STRIDE-per-element enumeration step specifically, with a human curating for prioritization and org context. More speculatively, there's movement toward continuous, automated threat-model diffing tied to architecture-as-code (a DFD expressed in a repo as a Structurizr/Mermaid diagram that gets re-evaluated whenever the underlying architecture file changes) — treat this as a direction of travel rather than settled practice; most orgs in 2026 still re-run threat models manually, triggered by design review rather than by an automated diagram diff.

---

## Mental model

Draw the system as boxes (processes), cylinders (data stores), arrows (data flows), and stick figures (external entities) — then draw a dashed line wherever an arrow crosses a change in trust: unauthenticated to authenticated, your network to a vendor's, your process to a database credential with narrower scope. The threats worth spending time on cluster on those dashed lines, not inside a box that never talks to anything untrusted.

```
[Client]  ══HTTPS══▶ ┊ [API Gateway + Auth] ══▶ [App Service] ══▶ [Postgres]
   (untrusted)        ┊    (your infra)                           (data tier)
                       ┊                              │
              trust boundary #1:                       ┊ trust boundary #2:
              public internet → your network           app process → data store
                                                         │
                                                         ▼
                                              [Third-Party Payment API]
                                                         ┊
                                              trust boundary #3:
                                              your org → external vendor
```

Every arrow crossing a dashed line is a candidate for the full STRIDE-per-element pass. Arrows that stay entirely inside one trust zone are lower priority — not zero, but lower.

---

## How it actually works

### STRIDE, defined precisely

| Letter | Threat | Property violated | One-line example |
|---|---|---|---|
| **S** | Spoofing | Authentication | Attacker presents a forged or stolen credential as someone else |
| **T** | Tampering | Integrity | Attacker modifies data in transit or at rest without authorization |
| **R** | Repudiation | Non-repudiation | An action happens with no reliable log tying it to an actor, so it can be denied |
| **I** | Information Disclosure | Confidentiality | Data is exposed to someone not authorized to see it |
| **D** | Denial of Service | Availability | A resource becomes unavailable to legitimate users |
| **E** | Elevation of Privilege | Authorization | An actor gains capabilities beyond what they should have |

### STRIDE-per-element — the mapping that makes it tractable

Running all six categories against the *whole system* at once produces a wall of undifferentiated notes. STRIDE-per-element restricts which categories are even worth asking, based on the kind of DFD element:

```
External Entity  →  S, R          (can it be impersonated; is its action deniable)
Process          →  S,T,R,I,D,E   (all six — a process is where logic and trust live)
Data Store       →  T, I, D       (+ R only if the store itself does authoritative logging)
Data Flow        →  T, I, D       (a flow doesn't authenticate or authorize, it moves bytes)
```

This isn't arbitrary — a data store, by itself, doesn't "authenticate" anyone (spoofing doesn't apply directly to it) and doesn't "elevate privilege" (that's a decision a process makes, not a property of storage), so asking those questions against a data store produces noise. Restricting the questions to what's mechanically possible for each element is what makes a full STRIDE pass finishable in 15 minutes instead of an hour.

### Attack trees

An attack tree starts from a root goal, not from a mechanism:

```
GOAL: Exfiltrate all user PII from the database          (OR)
├── SQL injection via an unsanitized API parameter        (leaf, cheap, high feasibility)
├── Compromise app service credentials                    (AND)
│     ├── Phish an engineer with prod access
│     └── Obtain DB credentials from the secrets vault
├── Compromise the third-party payment integration        (AND)
│     ├── Vendor-side breach of their API key store
│     └── That API key is reused with broader DB scope than needed
└── Insider: DB admin exports the table directly           (leaf, low feasibility, high impact)
```

`OR` means any one child achieves the goal; `AND` means every child must succeed. The point of building the tree is not to enumerate every conceivable path — it's to find the *cheapest* leaf for an attacker, because that's where you spend mitigation budget first. In the tree above, the unsanitized parameter is a single-step leaf while the phishing path requires two independent successes; all else equal, the single-step leaf is priority one.

### Trust boundaries — how to actually find them on a real diagram

A trust boundary exists wherever an arrow crosses one of:
- **Network zone** (public internet → your VPC, your VPC → a partner's VPC)
- **Authentication state** (unauthenticated request → authenticated session)
- **Privilege level** (app-tier service account → DBA-level credential)
- **Organizational control** (your code → a vendor's API you don't control or audit)

The single most commonly missed boundary in real systems is the third one — organizational control at a third-party integration. Teams draw the client→API boundary reliably because it's the one everyone's taught first, and then skip the outbound call to a payment processor or notification vendor because "that's just an API call we make," forgetting that a *webhook coming back in* from that vendor is an external entity crossing back into your trust zone and needs the same scrutiny as the client request did.

### DREAD, and precisely why it fell out of favor

DREAD scores a threat on five axes — **D**amage, **R**eproducibility, **E**xploitability, **A**ffected users, **D**iscoverability — each typically 1-10, summed or averaged into a single number used to rank threats. The documented failure is that these are subjective judgment calls wearing numbers as a costume: "how discoverable is this" depends entirely on what the scorer imagines an attacker already knows, and two reasonable engineers will produce meaningfully different scores for the same threat. Microsoft's own internal teams moved away from DREAD for exactly this reason — the scores didn't converge between reviewers, and false precision (a threat scored 7.4 versus one scored 6.8) drove arguments about decimal points instead of decisions about what to fix first. The practical replacement most teams use now is a coarse categorical grid — likelihood (low/medium/high) by impact (low/medium/high) — with written anchors for what each bucket means in this specific system, which produces less precise-looking but more *actually* consistent triage.

### The 45-minute procedure

This is the part that turns threat modeling from a ritual into working output. Time-box it strictly:

1. **(5 min) Confirm the DFD.** If one exists, spend the time checking it's current, not redrawing it. If none exists, whiteboard the minimum: processes, data stores, external entities, data flows, and — critically — draw the trust boundaries as you go, don't defer them.
2. **(15 min) STRIDE-per-element pass.** Go element by element using the restricted category list above. Write threats as one-liners on a shared doc/whiteboard, not paragraphs — "webhook has no signature check" not a three-sentence essay. Anyone drafting prose here is stealing time from the next step.
3. **(10 min) Coarse ranking.** Likelihood × impact grid, not DREAD math. Existing mitigations count as a discount — a tampering threat against a data store that's already encrypted-at-rest with strict IAM is lower priority than the same threat against an unencrypted store with a shared credential.
4. **(10 min) Top 5-8, one action line each.** For each: mitigate now / accept the risk explicitly / transfer (e.g., contractually push to the vendor) / spike (need more investigation before deciding). Assign an owner by name, not by team.
5. **(5 min) Ticket it.** Each action becomes a ticket referencing the specific element/boundary it came from. The output of the session is the ticket queue, not a write-up — a document nobody re-reads has zero effect on the system; a ticket in someone's sprint does.

If step 2 runs long, that's a signal the diagram from step 1 was too coarse or too large for one session — split the system rather than let the session balloon past 45 minutes.

### Folding it into design review

Threat modeling should be a required section of a design doc template, not a standalone artifact with its own lifecycle (which is exactly how it goes stale). The trigger for re-running it should be specific and mechanical, not calendar-based:
- A new trust boundary is being introduced (new external integration, new network zone, new auth flow).
- The system starts handling a new class of sensitive data (PII, payment data, health data).
- An authentication or authorization mechanism changes.
- A design doc otherwise proposes a materially different architecture, not an incremental change within the existing boundaries.

A design doc that doesn't cross any of these doesn't need a fresh 45-minute session — a one-line "no new trust boundaries, prior threat model at [link] still applies" is a legitimate and correct answer.

---

## Build it from scratch

There's no "runtime" to threat modeling, but the mechanical piece worth automating is the STRIDE-per-element checklist generation itself, so the 15-minute window in step 2 above is spent finding threats, not remembering which categories apply to which element type:

```python
# untested sketch — no external deps, pure enumeration
from dataclasses import dataclass, field
from enum import Enum

class Kind(Enum):
    EXTERNAL_ENTITY = "external_entity"
    PROCESS = "process"
    DATA_STORE = "data_store"
    DATA_FLOW = "data_flow"

STRIDE_BY_KIND = {
    Kind.EXTERNAL_ENTITY: ["Spoofing", "Repudiation"],
    Kind.PROCESS: ["Spoofing", "Tampering", "Repudiation",
                   "Information Disclosure", "Denial of Service", "Elevation of Privilege"],
    Kind.DATA_STORE: ["Tampering", "Information Disclosure", "Denial of Service"],
    Kind.DATA_FLOW: ["Tampering", "Information Disclosure", "Denial of Service"],
}

@dataclass
class Element:
    name: str
    kind: Kind
    crosses_trust_boundary: bool = False
    notes: list = field(default_factory=list)

def stride_checklist(elements: list[Element]) -> list[str]:
    lines = []
    # elements crossing a trust boundary are listed first — that's where the 15 minutes should go
    ordered = sorted(elements, key=lambda e: not e.crosses_trust_boundary)
    for el in ordered:
        flag = "  [TRUST BOUNDARY]" if el.crosses_trust_boundary else ""
        lines.append(f"\n{el.name} ({el.kind.value}){flag}")
        for cat in STRIDE_BY_KIND[el.kind]:
            lines.append(f"  [ ] {cat}: ?")
    return lines

dfd = [
    Element("Client", Kind.EXTERNAL_ENTITY, crosses_trust_boundary=True),
    Element("API Gateway + Auth", Kind.PROCESS, crosses_trust_boundary=True),
    Element("App Service", Kind.PROCESS),
    Element("Postgres", Kind.DATA_STORE, crosses_trust_boundary=True),
    Element("Third-Party Payment API", Kind.EXTERNAL_ENTITY, crosses_trust_boundary=True),
]

for line in stride_checklist(dfd):
    print(line)
```

This is deliberately small — the point isn't to build a threat-modeling platform, it's to walk into the 45-minute session with the STRIDE-per-element skeleton already generated so the group's time goes into filling in real answers, not recalling which categories apply to a data store versus a process.

---

## How it's done in production

| Symptom | Cause | Fix |
|---|---|---|
| Threat-model doc from 8 months ago doesn't mention the payment integration added last quarter | Threat model was written once at design time with its own document lifecycle, never re-triggered | Tie re-runs to mechanical triggers (new trust boundary, new sensitive data class, new auth flow), not a calendar or a doc-review cycle |
| A 3-hour whiteboard session produces 40 theoretical threats and no action items | No time box; team tried to enumerate every conceivable threat instead of the highest-value ones | Hard 45-minute box, cap output at 5-8 actioned threats, push the rest to a backlog without further debate in the room |
| Two reviewers score the same threat 8/10 and 4/10 under DREAD | Ordinal, subjective sub-scores treated as precise interval measurements | Drop DREAD for a coarse likelihood×impact grid with anchors defined for this specific system |
| A forged webhook triggers fraudulent refunds | The inbound webhook from a third-party vendor was never drawn as a trust boundary — team treated the *outbound* call to the vendor as the only boundary that mattered | Explicitly threat-model every inbound callback from a third party as an external entity crossing back into your trust zone, not just the outbound call |
| Security team becomes the bottleneck for every design review across 50 teams | Threat modeling requires a specialist to run every session | Push the 45-minute STRIDE-per-element procedure to the team that owns the system, with security as an escalation path for the top-ranked findings only, not a gate on every session |

---

## Tradeoffs & when NOT to use it

- **Don't run a full session for a change with no new trust boundary.** An internal CRUD endpoint that doesn't touch a new data class or new external actor doesn't need 45 minutes; "no new boundary, prior model at [link] still holds" is a legitimate answer.
- **Don't use DREAD for prioritization on a fast-moving team.** The false precision creates arguments about scores instead of decisions about fixes; a coarse grid with anchors ranks just as usefully and doesn't invite decimal-point debates.
- **Don't run attack trees on every threat found in the STRIDE pass.** Reserve them for the handful of highest-value attacker goals (exfiltrate PII, move money, take over an account) — building a full AND/OR tree for a low-value target burns time you don't get back.
- **Don't skip threat modeling on a "prototype" that touches real payment or PII data.** A large share of real breaches trace back to a system that was threat-modeled "later," after it had already shipped with real user data flowing through it.
- **Don't let a compliance requirement turn this into a document exercise.** If the output is a PDF filed for an auditor and not a set of tickets someone is actually working, the process has failed regardless of whether it satisfies the compliance checkbox.

---

## Interview questions

### Q1 — What does STRIDE stand for, and give one concrete example of each.
**Testing:** baseline recall plus whether examples are concrete rather than restated definitions.
**Answer:** Spoofing (a stolen session token used to impersonate a user), Tampering (modifying an order total in a request body before it's re-validated server-side), Repudiation (an admin action with no audit log tying it to a specific account), Information Disclosure (a verbose stack trace leaking internal file paths), Denial of Service (an unauthenticated endpoint with no rate limit), Elevation of Privilege (a JWT role claim trusted without re-checking against the current database state, letting a demoted user retain admin access until token expiry).
**Follow-up trap:** *"Which of these applies to a database by itself?"* — Tampering, Information Disclosure, and Denial of Service; Spoofing and Elevation of Privilege are properties of a process making an authentication/authorization decision, not of storage itself.

### Q2 — Why doesn't a data store typically get scored for Repudiation?
**Testing:** whether STRIDE-per-element is understood mechanically, not just memorized as six letters.
**Answer:** Repudiation is about whether an *action* can be reliably tied to an actor — that's a property of logging and audit trail, which lives in the process that writes to the store, not in the store itself. A data store only gets Repudiation added to its checklist if it independently implements authoritative transaction logging that a process can't bypass or falsify.
**Follow-up trap:** *"So when would you add it back?"* — when the data store itself is the source of truth for an audit log (e.g., an append-only ledger table with row-level integrity guarantees) rather than just holding application data that a process logs separately.

### Q3 — What's a trust boundary, and how do you find them on a real architecture diagram?
**Testing:** whether the candidate can operationalize the concept, not just define it.
**Answer:** A trust boundary is any point where privilege level, network zone, authentication state, or organizational control changes across a data flow arrow. Find them by walking every arrow and asking: does this cross from unauthenticated to authenticated, from your network to someone else's, from an app-tier credential to a more privileged one? The most commonly missed one in practice is a third-party integration's *inbound* callback (a webhook), which is an external entity crossing back into your trust zone and needs the same scrutiny as any other untrusted input.
**Follow-up trap:** *"Give me a boundary most teams miss."* — the webhook-back-in case specifically; teams reliably threat-model the outbound call to a vendor but forget the vendor calling back is itself an untrusted external entity that needs signature verification and its own STRIDE pass.

### Q4 — Why did Microsoft deprecate DREAD internally, and is it still used?
**Testing:** whether the candidate knows this is a real, documented shift rather than assuming DREAD is still the default.
**Answer:** DREAD's five sub-scores are subjective judgment calls dressed as 1-10 numbers, and different reviewers scoring the identical threat produced meaningfully different results — the scoring didn't remove the inconsistency it was built to remove. Microsoft moved away from it internally for that reason. It's still used informally at some organizations for lack of a simpler alternative, but the more common current replacement is a coarse categorical likelihood-by-impact grid with anchors defined for the specific system.
**Follow-up trap:** *"If a candidate at another company still uses DREAD, is that wrong?"* — not necessarily wrong, but worth probing whether they're aware of the subjectivity problem and have calibrated anchors across reviewers, versus using it uncritically as if the numbers were objective.

### Q5 — Walk me through a 45-minute threat model for an API with auth, a database, and a third-party payment integration.
**Testing:** whether the candidate has an actual repeatable procedure, not an ad hoc approach.
**Answer:** 5 minutes confirming or drawing the DFD with trust boundaries marked (client→gateway, app→DB, app↔vendor). 15 minutes running STRIDE-per-element, prioritizing elements that cross a boundary — the auth process gets all six categories, the DB gets T/I/D, the vendor integration gets special attention to the inbound webhook as an external entity. 10 minutes ranking findings on a likelihood×impact grid — a forged webhook without signature verification ranks highest because it's both easy to attempt and directly enables fraud. 10 minutes turning the top 5-8 into one-line actions with owners. 5 minutes filing them as tickets referencing the specific boundary they came from.
**Follow-up trap:** *"What if the STRIDE pass surfaces 25 threats in 15 minutes?"* — that's fine; the ranking step is what cuts 25 down to the actionable top 5-8. Don't try to compress ranking into the enumeration step, that's how sessions run long.

### Q6 — Explain an attack tree. What's the difference between an AND node and an OR node?
**Testing:** whether the candidate can use attack trees for prioritization, not just describe the shape.
**Answer:** An attack tree starts from an attacker's goal at the root and decomposes it into paths. An OR node means any one child branch achieves the goal (e.g., "exfiltrate PII" via SQL injection OR via compromised credentials OR via insider export) — the attacker only needs one to succeed. An AND node means every child must succeed for that branch to work (e.g., "compromise app credentials" requires both phishing an engineer AND finding DB credentials in the vault). Ranking leaves by feasibility tells you which branch to close first — a single-step OR leaf is generally higher priority to fix than a multi-step AND branch, all else equal.
**Follow-up trap:** *"Does a longer AND chain mean you can ignore it?"* — no, just that it's lower priority relative to a cheaper path, not risk-free; a sufficiently high-impact AND chain (e.g., leading to full financial fraud) can still warrant mitigation even if it requires two steps, especially if either step is individually plausible (a successful phishing campaign is not rare).

### Q7 — When would you use PASTA instead of STRIDE?
**Testing:** whether the candidate knows STRIDE isn't the only framework and has a reason to pick between them.
**Answer:** PASTA (Process for Attack Simulation and Threat Analysis) is a risk-centric, business-impact-driven methodology that ties threats explicitly back to business objectives and includes an attack-simulation stage, which suits organizations that need threat modeling output framed for business/risk stakeholders rather than engineers. STRIDE is faster and more mechanical, better suited to an engineering team running a time-boxed session against a concrete architecture diagram. For most engineering design reviews, STRIDE-per-element is the pragmatic default; PASTA earns its overhead when the audience and stakes are explicitly business-risk framed (e.g., feeding into a formal risk register for leadership).
**Follow-up trap:** *"Could you use both?"* — yes, and it's common to use STRIDE for the engineering-level enumeration and roll the highest-ranked findings into a PASTA-style business-risk narrative for stakeholders who need cost/impact framing rather than a threat checklist.

### Q8 — How do you fold threat modeling into design review without it becoming a bottleneck for every team?
**Testing:** organizational judgment at staff/principal level.
**Answer:** Make it a required section of the design doc template with a mechanical trigger, not a security-team gate on every doc: a new trust boundary, a new sensitive data class, or a changed auth mechanism requires a fresh 45-minute session; anything else can state "no new boundary, prior model still applies" and move on. Push the actual session facilitation to the team that owns the system rather than requiring a central security reviewer for every instance — reserve the specialist's time for reviewing the top-ranked findings from teams' own sessions, not running every session personally.
**Follow-up trap:** *"What happens when a team self-certifies 'no new boundary' incorrectly?"* — spot-check via periodic security audit sampling, and make the mechanical triggers specific and checkable enough (new external integration, new data class, new auth flow) that misclassifying them is an easily caught process failure, not a judgment call with room to hide in.

### Q9 — Give a concrete threat you'd flag for a system with a third-party webhook integration, and its priority.
**Testing:** whether the candidate can apply the framework to a specific, common real-world pattern.
**Answer:** A webhook endpoint accepting a callback from a payment vendor without verifying an HMAC signature on the payload is a Spoofing threat against the webhook treated as an external entity — anyone who can guess or discover the URL can forge a "payment succeeded" event and trigger fraudulent order fulfillment or refunds. This ranks high-likelihood/high-impact on a coarse grid: the attack requires no special access (the endpoint is internet-facing by design) and the impact is direct financial loss.
**Follow-up trap:** *"Signature verification alone enough?"* — no; also need replay protection (a valid, previously-seen signed event resent by an attacker who intercepted it) and idempotency on the receiving side, since a signature check alone doesn't stop a captured, legitimate event being replayed.

### Q10 — What's the difference between a threat model and a penetration test?
**Testing:** whether the candidate conflates design-time analysis with runtime verification.
**Answer:** A threat model is a design-time, structured reasoning exercise over an architecture — it identifies *what could go wrong* based on the system's design, before or independent of any specific implementation bug. A pentest is a runtime, adversarial exercise against an actual running system, looking for specific exploitable vulnerabilities. They're complementary: a threat model tells you where to point pentest effort (the highest-ranked boundaries and attack-tree leaves), and a pentest validates whether the mitigations the threat model produced actually hold up against a real attacker.
**Follow-up trap:** *"Can a pentest replace threat modeling?"* — no; a pentest only finds what it happens to probe, and without a threat model's systematic per-element coverage, entire classes of design-level risk (e.g., an architecturally missing trust boundary) can go completely untested because nobody thought to point the pentest there.

### Q11 — How do you decide when an existing threat model still holds versus needs a re-run?
**Testing:** staff-level judgment on maintaining a living process rather than a one-time artifact.
**Answer:** Re-run on the mechanical triggers: a new trust boundary, a new class of sensitive data, or a changed authentication/authorization mechanism. Absent those, incremental changes within the existing boundaries don't need a fresh session — but the design doc for that change should explicitly state which prior model it relies on and confirm none of the triggers apply, rather than silently assuming it's covered.
**Follow-up trap:** *"What if triggers accumulate gradually across many small PRs, none individually crossing a boundary?"* — this is the real failure mode: cumulative drift where the system looks materially different after fifty small changes even though no single PR tripped a trigger. The mitigation is a periodic (not per-PR) architecture review that re-draws the DFD from scratch and compares it against the last threat model's diagram, specifically to catch boundary creep that no individual change flagged.

### Q12 — A system evolves through many small PRs, none of which individually adds a new trust boundary, but the cumulative architecture is unrecognizable from the last threat model. How do you catch that?
**Testing:** the same drift problem as Q11, probed directly — checking for a real answer versus a restated principle.
**Answer:** Mechanical per-PR triggers are necessary but not sufficient for catching gradual architectural drift, because no single PR trips them. The fix is a periodic full re-draw of the DFD (on a cadence tied to major release cycles or a fixed calendar interval, not per-change) that's compared side-by-side against the diagram from the last full threat model, specifically looking for new boxes, new arrows, or arrows that have quietly started crossing a boundary they didn't before.
**Follow-up trap:** *"Isn't that just going back to calendar-based re-runs, which you said were a smell?"* — the distinction is that mechanical per-PR triggers stay as the primary mechanism for anything obviously boundary-crossing; the periodic full re-draw is a coarser-grained safety net specifically for drift that no individual trigger caught, not a replacement for the trigger-based process.

### Q13 — How would you scale threat modeling across 50 teams without the security team becoming the bottleneck?
**Testing:** principal-level organizational scaling judgment.
**Answer:** Distribute the 45-minute procedure itself to the teams that own each system — it's a repeatable, teachable mechanical process, not something that inherently requires a security specialist in the room. Reserve the central security team's time for: training teams on the procedure once, reviewing the top-ranked findings that come out of each session (not attending every session), and auditing a sample of "no new boundary" self-certifications to catch misclassification. This turns the central team into a force multiplier and escalation path rather than a gate every design has to wait behind.
**Follow-up trap:** *"What if teams run the procedure badly without oversight?"* — build a lightweight rubric/checklist into the design-doc template itself (the STRIDE-per-element categories, the trust-boundary trigger list) so the process is self-guiding even without a facilitator in the room, and spot-check a sample of completed sessions periodically rather than gating every one.

### Q14 — What's the actual output artifact you want at the end of a threat model, and why is a document the wrong default?
**Testing:** whether the candidate understands the core failure mode this module is built around.
**Answer:** A prioritized backlog of tickets, each referencing the specific element/boundary it came from, with an owner and an action (mitigate/accept/transfer/spike) — not a written report. A document has no mechanism forcing anyone to act on it and no mechanism keeping it current as the system changes; it rots silently. A ticket lives in a sprint, gets triaged against other work, and either gets done or gets explicitly deprioritized in a visible way — either outcome is more honest than a stale PDF that implies coverage nobody's checked in months.
**Follow-up trap:** *"Isn't some document necessary for audit/compliance purposes?"* — yes, but the compliance artifact should be a *summary generated from* the ticket queue and its resolution history (what was found, what was done about it, when), not the primary work product — treating the document as the deliverable rather than a byproduct is exactly how the document ends up stale and disconnected from what the tickets actually did.

### Q15 — STRIDE assumes a clean data-flow diagram. What do you do for a legacy system with no diagram and genuinely tangled architecture?
**Testing:** whether the candidate can adapt the procedure to a messier real-world starting point rather than insisting on ideal preconditions.
**Answer:** Spend the first 5 minutes of the session (or a short prior working session if the system is large) whiteboarding the minimum viable DFD from what's actually known — don't try to fully document the legacy system, just capture enough boxes/stores/flows/boundaries to run the STRIDE pass meaningfully. It's fine and expected for this initial diagram to be incomplete; the threat model itself, run against that incomplete-but-honest diagram, is more valuable than delaying the whole exercise until a perfect diagram exists (which, for a genuinely tangled legacy system, may never happen).
**Follow-up trap:** *"Doesn't an incomplete diagram mean you'll miss threats?"* — yes, and that's an acceptable tradeoff against never running the exercise at all; note explicitly in the output which parts of the system weren't modeled due to diagram gaps, so that gap itself becomes a visible, trackable item rather than a silent blind spot.

---

## Red flags that fail you

- Presenting DREAD sub-scores as objective, precise numbers rather than acknowledging the subjectivity problem that got it deprecated.
- Listing fewer than all six STRIDE categories for a process, or applying all six uniformly to a data store without knowing why that's wrong.
- Treating threat modeling as a one-time document produced before launch rather than a process re-triggered by specific architectural changes.
- Running an unbounded session with no time box and no output contract, producing a long threat list with no ranking or ownership.
- Missing the inbound-webhook-as-external-entity case for a third-party integration — drawing only the outbound call as the trust boundary.
- Confusing a threat model with a penetration test, or claiming one substitutes for the other.
- Proposing a threat-modeling process that requires a security specialist in every single session, with no path to scale across an organization.

---

## Cheat card

```
STRIDE: Spoof(authn) Tamper(integrity) Repudiation(non-repud/logs)
        InfoDisclosure(confidentiality) DoS(availability) EoP(authz)
STRIDE-per-element: ExternalEntity=S,R | Process=all 6 | DataStore=T,I,D(+R if authoritative log)
                     | DataFlow=T,I,D
Trust boundary = arrow crosses: network zone, auth state, privilege level, org control
  most-missed boundary: inbound webhook FROM a vendor (it's an external entity, not "just a call")
DREAD (Damage,Reproducibility,Exploitability,AffectedUsers,Discoverability):
  deprecated internally by MS — subjective sub-scores, no reviewer convergence
  replacement: coarse likelihood x impact grid w/ written anchors, not summed numbers
Attack tree: root=attacker goal, OR=any child suffices, AND=all children required,
  rank leaves by feasibility -> cheapest leaf gets mitigation budget first
45-MIN PROCEDURE: 5min confirm DFD+boundaries -> 15min STRIDE-per-element ->
  10min coarse rank -> 10min top 5-8 w/ action+owner -> 5min file as tickets
OUTPUT = prioritized ticket backlog, NOT a standalone document
Re-trigger on: new trust boundary | new external integration | new sensitive
  data class | authn/authz change  (NOT calendar-based)
Periodic full re-draw catches cumulative drift that no single PR trigger caught
Threat model != pentest: design-time reasoning vs runtime adversarial verification
```

## Sources

- [STRIDE Threat Model: The Complete Guide to Microsoft's Security Framework](https://trent.ai/blog/stride-threat-model/) — accessed 2026-07-26
- [DREAD vs STRIDE vs PASTA Threat Modeling — Blue Goat Cyber](https://bluegoatcyber.com/blog/comparing-dread-stride-and-pasta-threat-models-which-is-most-effective) — accessed 2026-07-26
- [STRIDE vs DREAD vs PASTA: Threat Modeling Framework Comparison (2026) — SoftwareSecured](https://www.softwaresecured.com/post/comparison-of-stride-dread-pasta) — accessed 2026-07-26
- [Threat Modeling — OWASP Cheat Sheet Series](https://cheatsheetseries.owasp.org/cheatsheets/Threat_Modeling_Cheat_Sheet.html) — accessed 2026-07-26
- [Threat Modeling Guide for Software Teams — Martin Fowler](https://martinfowler.com/articles/agile-threat-modelling.html) — accessed 2026-07-26
- [How to approach threat modeling — AWS Security Blog](https://aws.amazon.com/blogs/security/how-to-approach-threat-modeling/) — accessed 2026-07-26
- [55 Threat Modeling Interview Questions & Answers for 2026 — Practical DevSecOps](https://www.practical-devsecops.com/threat-modeling-interview-questions-and-answers/) — accessed 2026-07-26
- [DREAD Threat Modeling — Threat-Modeling.com](https://threat-modeling.com/dread-threat-modeling/) — accessed 2026-07-26

## Changelog
- 2026-07-26 — created
